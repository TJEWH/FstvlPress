from __future__ import annotations

import mimetypes
from datetime import datetime
import uuid
from urllib.parse import urlparse, unquote
import re
import hashlib
import unicodedata

from bson import ObjectId
import httpx
from fastapi import APIRouter, Body, Depends, File, UploadFile, HTTPException, Query, Form, Request
from pymongo.errors import DuplicateKeyError
from typing import Optional

from app.collection_names import DESIGN_EDITOR_CONFIG_COLLECTION, MEDIA_CONFIG_COLLECTION
from app.db import get_client
from app.deps import require_permission
from app.image_processing import (
    process_image,
    process_svg,
    is_image,
)
from app.media_responsive import build_asset_responsive_variants
from app.media_metadata import extract_image_metadata
from app.models.cms import AssetCreateResult, AssetListItem, AssetListResponse
from app.responsive_config import responsive_preview_widths
from app.settings import settings
from app.storage.s3 import S3Storage
from app.storage.ftp import FTPStorage
from app.sitemap import resolve_public_base_url_from_request

router = APIRouter(prefix="/assets", tags=["assets"])

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB (increased for videos)
MEDIA_CONFIG_KEY = MEDIA_CONFIG_COLLECTION
ADMIN_CONFIG_KEY = DESIGN_EDITOR_CONFIG_COLLECTION
DEFAULT_MEDIA_CONFIG = {
    "custom_tags": [],
    "source_tag_prefix": "source",
    "upload_variants": {
        "mobile": {"enabled": True, "width": 375},
        "thumb": {"enabled": True, "width": 150},
        "tablet": {"enabled": True, "width": 768},
        "desktop": {"enabled": True, "width": 1120},
        "custom": [],
        "max_original_width": 2000,
    },
    "metadata_mappings": {
        "enabled": True,
        "author_tag_prefix": "author",
        "rights_tag_prefix": "rights",
        "keyword_tag_prefix": "meta",
        "require_author": False,
        "require_rights": False,
        "key_mappings": [
            {"source_key": "raw_exif.exif:copyright", "target_field": "author"},
        ],
        "value_mappings": [],
    },
    "program_tagging": {
        "artist_tag_prefix": "artist",
        "stage_tag_prefix": "stage",
        "date_tag_prefix": "date",
    },
    "cropping_tags": {
        "base_tags": ["cropped", "auto"],
        "profile_tag_pattern": "profile-{profile_id}",
        "profile_overrides": {},
    },
}
ALLOWED_NON_IMAGE_TYPES = frozenset({
    "application/pdf",
    "video/mp4",
    "video/webm",
    "video/quicktime",  # .mov
    "video/ogg",
    "video/x-m4v",
})
BLOCKED_CONTENT_TYPES = frozenset(
    {
        "application/x-php",
        "application/x-msdownload",
        "text/html",
        "application/javascript",
    }
)


MAX_TAG_LENGTH = 64
ALLOWED_TAG_SPECIAL_CHARS = frozenset({":", "_", "-"})
MEDIA_HASH_LENGTH = 24
FILE_TYPE_TAG_PREFIX = "type"
RETIRED_INTEGRATION_TAG_PREFIX = "integration"
FILE_TYPE_EXTENSION_ALIASES = {
    "jpeg": "jpg",
    "jpe": "jpg",
}
CONTENT_TYPE_FILE_TYPE_OVERRIDES = {
    "image/jpeg": "jpg",
    "image/svg+xml": "svg",
    "video/quicktime": "mov",
    "video/x-m4v": "m4v",
}


def _db():
    return get_client()[settings.mongo_db]


def _is_valid_tag(tag: str) -> bool:
    if not tag or len(tag) > MAX_TAG_LENGTH:
        return False
    if not tag[0].isalnum():
        return False
    return all(char.isalnum() or char in ALLOWED_TAG_SPECIAL_CHARS for char in tag)


def get_storage():
    if settings.storage_backend == "ftp":
        return FTPStorage()
    return S3Storage()


def _infer_filename_from_url(media_url: str) -> str:
    parsed = urlparse(media_url)
    path = unquote(parsed.path or "").strip()
    name = path.split("/")[-1] if path else ""
    if name:
        return name
    return f"imported-{uuid.uuid4().hex}"


def _source_url_hash(source_url: str) -> str:
    normalized = str(source_url or "").strip()
    if not normalized:
        return ""
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _resolve_import_source_url(source_url: str, request: Request) -> str:
    raw = str(source_url or "").strip()
    if raw.startswith("/") and not raw.startswith("//"):
        return f"{resolve_public_base_url_from_request(request)}{raw}"
    return raw


def _normalize_tag(value: str) -> str:
    tag = unicodedata.normalize("NFC", str(value or "").strip()).lower()
    if not tag:
        return ""
    if not _is_valid_tag(tag):
        raise HTTPException(400, f"Invalid tag '{value}'")
    return tag


def _normalize_tag_list(values) -> list[str]:
    if not values:
        return []
    tags = []
    for raw in values:
        normalized = _normalize_tag(str(raw or ""))
        if normalized:
            tags.append(normalized)
    return sorted(set(tags))


def _normalize_file_type_extension(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_-]", "", str(value or "").strip().lower().lstrip("."))
    if not normalized:
        return ""
    return FILE_TYPE_EXTENSION_ALIASES.get(normalized, normalized)


def _infer_file_type_extension(filename: str | None, content_type: str | None) -> str:
    if filename and "." in filename:
        extension_from_filename = _normalize_file_type_extension(filename.rsplit(".", 1)[-1])
        if extension_from_filename:
            return extension_from_filename

    normalized_content_type = str(content_type or "").split(";", 1)[0].strip().lower()
    if not normalized_content_type:
        return ""

    override = CONTENT_TYPE_FILE_TYPE_OVERRIDES.get(normalized_content_type)
    if override:
        return override

    guessed_ext = mimetypes.guess_extension(normalized_content_type) or ""
    guessed = _normalize_file_type_extension(guessed_ext)
    if guessed:
        return guessed

    subtype = normalized_content_type.split("/", 1)[1] if "/" in normalized_content_type else ""
    if subtype:
        subtype = subtype.split("+", 1)[0]
        if subtype.startswith("x-"):
            subtype = subtype[2:]
    return _normalize_file_type_extension(subtype)


def _build_file_type_tag(filename: str | None, content_type: str | None) -> str:
    extension = _infer_file_type_extension(filename, content_type)
    if not extension:
        return ""
    try:
        return _normalize_tag(f"{FILE_TYPE_TAG_PREFIX}::{extension}")
    except HTTPException:
        return ""


async def _get_media_config() -> dict:
    coll = _db()[MEDIA_CONFIG_COLLECTION]
    now = datetime.utcnow()
    doc = await coll.find_one({"key": MEDIA_CONFIG_KEY})
    if doc:
        return doc
    defaults = {
        "key": MEDIA_CONFIG_KEY,
        **DEFAULT_MEDIA_CONFIG,
        "created_at": now,
        "updated_at": now,
    }
    await coll.insert_one(defaults)
    return defaults


async def _get_admin_responsive_config() -> dict | None:
    coll = _db()[DESIGN_EDITOR_CONFIG_COLLECTION]
    doc = await coll.find_one({"key": ADMIN_CONFIG_KEY}, {"responsive": 1})
    if not isinstance(doc, dict):
        return None
    responsive = doc.get("responsive")
    return responsive if isinstance(responsive, dict) else None


def _get_source_tag_prefix(config: dict) -> str:
    raw = ""
    if isinstance(config, dict):
        raw = config.get("source_tag_prefix")
    prefix = str(raw or "source").strip().lower().rstrip(":")
    try:
        normalized = _normalize_tag(prefix or "source")
    except HTTPException:
        normalized = "source"
    if "::" in normalized:
        normalized = normalized.split("::", 1)[0] or "source"
    return normalized


def _normalize_source_context_slug(source_context: str | None) -> str:
    raw = str(source_context or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug or "unknown"


def _coerce_bool(raw, default: bool) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        lowered = raw.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _coerce_int(raw, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(raw)
    except Exception:
        value = default
    return max(min_value, min(max_value, value))


def _normalize_bilingual_text(value, fallback: str = "") -> dict[str, str]:
    fallback_text = str(fallback or "").strip()
    if isinstance(value, dict):
        de = str(value.get("de") or "").strip()
        en = str(value.get("en") or "").strip()
        return {"de": de, "en": en}
    if isinstance(value, str):
        text = value.strip()
        return {"de": text, "en": text}
    if isinstance(value, (int, float, bool)):
        text = str(value).strip()
        return {"de": text, "en": text}
    return {"de": fallback_text, "en": fallback_text}


async def _sync_gallery_asset_caption(
    asset_id: str,
    caption: dict[str, str],
    *,
    media_urls: list[str] | None = None,
) -> None:
    normalized_asset_id = str(asset_id or "").strip()
    if not normalized_asset_id:
        return
    payload = _normalize_bilingual_text(caption, "")
    normalized_urls = [
        str(url or "").strip()
        for url in (media_urls or [])
        if str(url or "").strip()
    ]
    match_clauses = [{"type_data.images.asset_id": normalized_asset_id}]
    if normalized_urls:
        match_clauses.extend(
            [
                {"type_data.images.image_url": {"$in": normalized_urls}},
            ]
        )
    array_filter_clauses = [{"img.asset_id": normalized_asset_id}]
    if normalized_urls:
        array_filter_clauses.extend(
            [
                {"img.image_url": {"$in": normalized_urls}},
            ]
        )
    now = datetime.utcnow()
    for collection_name in ("sections", "template_sections"):
        collection = _db()[collection_name]
        await collection.update_many(
            {"section_type": "gallery", "$or": match_clauses},
            {
                "$set": {
                    "type_data.images.$[img].caption": payload,
                    "updated_at": now,
                }
            },
            array_filters=[{"$or": array_filter_clauses}],
        )


def _asset_default_alt(filename: str) -> dict[str, str]:
    text = str(filename or "").strip()
    return {"de": text, "en": text}


def _normalize_filename_for_download(value: str, fallback: str = "media") -> str:
    raw = str(value or "").replace("\\", "/").split("/")[-1].strip()
    if not raw:
        raw = fallback
    raw = re.sub(r"[\r\n]+", " ", raw).strip()
    return raw or fallback


def _slugify_download_stem(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip())
    ascii_text = normalized.encode("ascii", errors="ignore").decode("ascii")
    lowered = ascii_text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "media"


def _infer_download_extension(filename: str, content_type: str) -> str:
    normalized_filename = _normalize_filename_for_download(filename)
    ext = ""
    if "." in normalized_filename:
        ext = normalized_filename.rsplit(".", 1)[-1].strip().lower()
        ext = re.sub(r"[^a-z0-9]+", "", ext)
    if ext:
        return ext
    guessed = mimetypes.guess_extension(str(content_type or "").strip().lower()) or ""
    guessed_ext = guessed.lstrip(".").strip().lower()
    guessed_ext = re.sub(r"[^a-z0-9]+", "", guessed_ext)
    return guessed_ext or "bin"


def _download_url_path(*, asset_ref: str, filename: str, content_type: str) -> str:
    normalized_filename = _normalize_filename_for_download(filename)
    if "." in normalized_filename:
        stem = normalized_filename.rsplit(".", 1)[0]
    else:
        stem = normalized_filename
    stem_slug = _slugify_download_stem(stem)
    ext = _infer_download_extension(normalized_filename, content_type)
    return f"/download/{asset_ref}/{stem_slug}.{ext}"


def _generate_media_hash(seed: str | None = None) -> str:
    payload = seed or f"{uuid.uuid4().hex}:{datetime.utcnow().isoformat()}"
    return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()[:MEDIA_HASH_LENGTH]


def _resolve_download_url(
    doc: dict,
    *,
    media_hash: str | None = None,
    public_base_url: str | None = None,
) -> str | None:
    resolved_hash = str(media_hash or doc.get("media_hash") or "").strip()
    asset_ref = str(doc.get("_id") or "").strip() or resolved_hash
    downloadable = _coerce_bool(doc.get("downloadable"), False)
    if not downloadable or not asset_ref:
        return None
    download_path = _download_url_path(
        asset_ref=asset_ref,
        filename=str(doc.get("filename") or ""),
        content_type=str(doc.get("content_type") or ""),
    )
    return download_path


async def _ensure_asset_media_hash(doc: dict, *, assets_coll) -> str | None:
    existing = str(doc.get("media_hash") or "").strip()
    if existing:
        return existing

    asset_id = doc.get("_id")
    if asset_id is None:
        return None

    missing_filter = {
        "_id": asset_id,
        "$or": [
            {"media_hash": {"$exists": False}},
            {"media_hash": ""},
            {"media_hash": None},
        ],
    }

    for _ in range(8):
        candidate = _generate_media_hash(f"{asset_id}:{uuid.uuid4().hex}")
        try:
            result = await assets_coll.update_one(missing_filter, {"$set": {"media_hash": candidate}})
        except DuplicateKeyError:
            continue

        if result.modified_count > 0:
            doc["media_hash"] = candidate
            return candidate

        refreshed = await assets_coll.find_one({"_id": asset_id}, {"media_hash": 1})
        resolved = str((refreshed or {}).get("media_hash") or "").strip()
        if resolved:
            doc["media_hash"] = resolved
            return resolved

    return None


async def _asset_list_item_from_doc(
    doc: dict,
    *,
    assets_coll,
    metadata_cfg: dict,
    ensure_media_hash: bool = True,
) -> AssetListItem:
    media_hash = (
        await _ensure_asset_media_hash(doc, assets_coll=assets_coll)
        if ensure_media_hash
        else str(doc.get("media_hash") or "").strip() or None
    )
    downloadable = _coerce_bool(doc.get("downloadable"), False)
    download_url = _resolve_download_url(
        doc,
        media_hash=media_hash,
    )
    resolved_fields = _resolve_metadata_fields(doc.get("metadata"), metadata_cfg)
    resolved_tags = _filter_retired_integration_context_tags(doc.get("tags", []))
    resolved_authors = resolved_fields["author"] or _extract_author_values_from_tags(
        resolved_tags,
        metadata_cfg.get("author_tag_prefix", "author"),
    )
    return AssetListItem(
        id=str(doc["_id"]),
        filename=doc.get("filename", ""),
        content_type=doc.get("content_type", ""),
        url=doc.get("url", ""),
        download_url=download_url,
        width=doc.get("width"),
        height=doc.get("height"),
        downloadable=downloadable,
        media_hash=media_hash,
        alt=_normalize_bilingual_text(doc.get("alt"), doc.get("filename", "")),
        caption=_normalize_bilingual_text(doc.get("caption"), ""),
        authors=resolved_authors,
        tags=resolved_tags,
        created_at=doc.get("created_at", datetime.utcnow()),
        responsive_variants=build_asset_responsive_variants(doc.get("variants")),
    )


def _normalize_upload_variant_id(raw: str) -> str:
    variant_id = re.sub(r"[^a-z0-9_-]+", "-", str(raw or "").strip().lower())
    variant_id = re.sub(r"-+", "-", variant_id).strip("-")[:48]
    if not variant_id or not variant_id[0].isalnum():
        return ""
    return variant_id


def _resolve_custom_upload_variants(raw: dict, defaults: dict) -> list[dict]:
    fixed_names = {"mobile", "thumb", "tablet", "desktop", "small"}
    raw_custom = raw.get("custom") if isinstance(raw.get("custom"), list) else None
    if raw_custom is None:
        raw_custom = defaults["custom"]

    custom: list[dict] = []
    seen: set[str] = set()
    for entry in raw_custom:
        if not isinstance(entry, dict):
            continue
        variant_id = _normalize_upload_variant_id(entry.get("id")) or _normalize_upload_variant_id(entry.get("label"))
        if not variant_id or variant_id in fixed_names or variant_id in seen:
            continue
        seen.add(variant_id)
        label = str(entry.get("label") or variant_id.replace("_", " ").replace("-", " ").title()).strip()
        custom.append(
            {
                "id": variant_id,
                "label": label[:80] or variant_id,
                "enabled": _coerce_bool(entry.get("enabled"), True),
                "width": _coerce_int(entry.get("width"), 480, 64, 4096),
            }
        )
    return custom


def _resolve_upload_variants_config(config: dict, responsive_config: dict | None = None) -> dict:
    defaults = DEFAULT_MEDIA_CONFIG["upload_variants"]
    raw = config.get("upload_variants") if isinstance(config, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    device_widths = responsive_preview_widths(responsive_config)
    raw_custom = raw.get("custom") if isinstance(raw.get("custom"), list) else []
    thumb_custom = next(
        (
            entry
            for entry in raw_custom
            if isinstance(entry, dict) and _normalize_upload_variant_id(entry.get("id")) == "thumb"
        ),
        None,
    )

    def variant_entry(name: str) -> dict:
        default_entry = defaults[name]
        entry_raw = raw.get(name)
        if not isinstance(entry_raw, dict):
            entry_raw = {}
        if name == "thumb" and not entry_raw and isinstance(thumb_custom, dict):
            entry_raw = thumb_custom
        width = (
            device_widths.get(name, default_entry["width"])
            if name in {"mobile", "tablet", "desktop"}
            else _coerce_int(entry_raw.get("width"), default_entry["width"], 64, 4096)
        )
        return {
            "enabled": _coerce_bool(entry_raw.get("enabled"), default_entry["enabled"]),
            "width": width,
        }

    custom_variants = _resolve_custom_upload_variants(raw, defaults)
    return {
        "mobile": variant_entry("mobile"),
        "thumb": variant_entry("thumb"),
        "tablet": variant_entry("tablet"),
        "desktop": variant_entry("desktop"),
        "custom": custom_variants,
        "max_original_width": _coerce_int(
            raw.get("max_original_width"), defaults["max_original_width"], 256, 4096
        ),
    }


def _build_responsive_widths(upload_variants_cfg: dict) -> dict[str, int]:
    responsive_widths: dict[str, int] = {}
    for variant_id in ("mobile", "thumb", "tablet", "desktop"):
        variant_cfg = upload_variants_cfg.get(variant_id, {})
        if variant_cfg.get("enabled"):
            responsive_widths[variant_id] = variant_cfg.get("width")
    for variant_cfg in upload_variants_cfg.get("custom", []):
        variant_id = str(variant_cfg.get("id") or "").strip()
        if variant_id and variant_cfg.get("enabled"):
            responsive_widths[variant_id] = variant_cfg.get("width")
    return responsive_widths


def _split_asset_storage_key(key: str | None, _content_type: str | None) -> tuple[str, str]:
    raw = str(key or "").strip()
    if "." in raw.rsplit("/", 1)[-1]:
        base, ext = raw.rsplit(".", 1)
        return base, ext.lower()
    return raw, ""


def _generated_variant_keys(doc: dict) -> set[str]:
    keys: set[str] = set()
    variants = doc.get("variants")
    if isinstance(variants, dict):
        for variant in variants.values():
            if isinstance(variant, dict):
                key = str(variant.get("key") or "").strip()
                if key:
                    keys.add(key)
    return keys


async def _delete_storage_keys(storage, keys: set[str]) -> None:
    for key in sorted(key for key in keys if key):
        try:
            await storage.delete(key=key)
        except Exception:
            pass


async def _process_and_store_image_variants(
    storage,
    *,
    data: bytes,
    content_type: str,
    base_key: str,
    ext: str,
    filename: str | None,
    upload_variants_cfg: dict,
    trim_transparent_padding: bool,
) -> dict:
    responsive_widths = _build_responsive_widths(upload_variants_cfg)
    variants = process_image(
        data,
        content_type,
        responsive_widths=responsive_widths,
        max_original_dim=upload_variants_cfg["max_original_width"],
        trim_transparent_padding=trim_transparent_padding,
    )

    suffix = f".{ext}" if ext else ""
    key_original = f"{base_key}{suffix}"
    stored_original = await storage.put(
        data=variants.original,
        key=key_original,
        content_type=content_type,
        filename=filename or key_original,
    )

    stored_responsive: dict[str, dict] = {}
    for variant_id, variant_bytes in variants.responsive.items():
        key_variant = f"{base_key}_{variant_id}{suffix}"
        stored_variant = await storage.put(
            data=variant_bytes,
            key=key_variant,
            content_type=content_type,
            filename=f"{variant_id}_{filename}" if filename else key_variant,
        )
        dims = variants.responsive_dimensions.get(variant_id)
        stored_responsive[variant_id] = {
            "key": stored_variant.key,
            "url": stored_variant.url,
            "width": dims[0] if dims else None,
            "height": dims[1] if dims else None,
        }

    return {
        "processed": variants,
        "stored_original": stored_original,
        "stored_responsive": stored_responsive,
    }


def _stored_image_generated_keys(stored_image: dict) -> set[str]:
    keys: set[str] = set()
    for entry in (stored_image.get("stored_responsive") or {}).values():
        if isinstance(entry, dict):
            keys.add(str(entry.get("key") or "").strip())
    return {key for key in keys if key}


def _normalize_tag_prefix(raw, default: str) -> str:
    prefix = str(raw or default).strip().lower().rstrip(":")
    if not prefix:
        prefix = default
    try:
        normalized = _normalize_tag(prefix)
    except HTTPException:
        normalized = default
    if "::" in normalized:
        normalized = normalized.split("::", 1)[0] or default
    return normalized


def _resolve_metadata_mappings_config(config: dict) -> dict:
    defaults = DEFAULT_MEDIA_CONFIG["metadata_mappings"]
    raw = config.get("metadata_mappings") if isinstance(config, dict) else {}
    if not isinstance(raw, dict):
        raw = {}

    enabled = _coerce_bool(raw.get("enabled"), defaults["enabled"])
    require_author = _coerce_bool(raw.get("require_author"), defaults["require_author"])
    require_rights = _coerce_bool(raw.get("require_rights"), defaults["require_rights"])
    author_tag_prefix = _normalize_tag_prefix(raw.get("author_tag_prefix"), defaults["author_tag_prefix"])
    rights_tag_prefix = _normalize_tag_prefix(raw.get("rights_tag_prefix"), defaults["rights_tag_prefix"])
    keyword_tag_prefix = _normalize_tag_prefix(raw.get("keyword_tag_prefix"), defaults["keyword_tag_prefix"])

    allowed_fields = {"author", "rights", "keyword", "tool", "credit"}

    key_mappings = []
    seen_key_mappings = set()
    raw_key_mappings = (
        raw.get("key_mappings")
        if isinstance(raw.get("key_mappings"), list)
        else defaults.get("key_mappings") if isinstance(defaults.get("key_mappings"), list) else []
    )
    for entry in raw_key_mappings:
        if not isinstance(entry, dict):
            continue
        source_key = str(entry.get("source_key", "")).strip().lower()
        target_field = str(entry.get("target_field", "")).strip().lower()
        if not source_key or target_field not in allowed_fields:
            continue
        key = (source_key, target_field)
        if key in seen_key_mappings:
            continue
        seen_key_mappings.add(key)
        key_mappings.append({"source_key": source_key, "target_field": target_field})

    value_mappings = []
    seen = set()
    raw_rules = raw.get("value_mappings") if isinstance(raw.get("value_mappings"), list) else []
    for entry in raw_rules:
        if not isinstance(entry, dict):
            continue
        field = str(entry.get("field", "")).strip().lower()
        match = str(entry.get("match", "")).strip().lower()
        tag_value = str(entry.get("tag", "")).strip().lower()
        if field not in allowed_fields or not match or not tag_value:
            continue
        try:
            tag = _normalize_tag(tag_value)
        except HTTPException:
            continue
        key = (field, match, tag)
        if key in seen:
            continue
        seen.add(key)
        value_mappings.append({"field": field, "match": match, "tag": tag})

    return {
        "enabled": enabled,
        "author_tag_prefix": author_tag_prefix,
        "rights_tag_prefix": rights_tag_prefix,
        "keyword_tag_prefix": keyword_tag_prefix,
        "require_author": require_author,
        "require_rights": require_rights,
        "key_mappings": key_mappings,
        "value_mappings": value_mappings,
    }


def _metadata_values_for_field(metadata: dict, field: str) -> list[str]:
    if field == "author":
        return [str(item) for item in (metadata.get("authors") or [])]
    if field == "rights":
        return [str(item) for item in (metadata.get("rights") or [])]
    if field == "tool":
        return [str(item) for item in (metadata.get("tools") or [])]
    if field == "credit":
        return [str(item) for item in (metadata.get("credits") or [])]
    return [str(item) for item in (metadata.get("keywords") or [])]


def _dedupe_metadata_values(values) -> list[str]:
    seen = set()
    result = []
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _normalized_metadata_key(value: str) -> str:
    return str(value or "").strip().lower()


def _metadata_values_for_source_key(metadata: dict, source_key: str) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    raw_key = _normalized_metadata_key(source_key)
    if not raw_key:
        return []

    segments = [segment for segment in raw_key.split(".") if segment]
    if not segments:
        return []

    current = metadata
    for segment in segments:
        if not isinstance(current, dict):
            return []
        next_value = None
        for key, value in current.items():
            if _normalized_metadata_key(key) == segment:
                next_value = value
                break
        if next_value is None:
            return []
        current = next_value

    if isinstance(current, (list, tuple, set)):
        return _dedupe_metadata_values(current)
    return _dedupe_metadata_values([current])


def _resolve_metadata_fields(metadata: dict, cfg: dict) -> dict[str, list[str]]:
    source = metadata if isinstance(metadata, dict) else {}
    authors = [str(item).strip() for item in (source.get("authors") or []) if str(item).strip()]
    rights = [str(item).strip() for item in (source.get("rights") or []) if str(item).strip()]
    keywords = [str(item).strip() for item in (source.get("keywords") or []) if str(item).strip()]
    tools = [str(item).strip() for item in (source.get("tools") or []) if str(item).strip()]
    credits = [str(item).strip() for item in (source.get("credits") or []) if str(item).strip()]

    fields = {
        "author": authors,
        "rights": rights,
        "keyword": keywords,
        "tool": tools,
        "credit": credits,
    }
    for mapping in (cfg.get("key_mappings") or []):
        target_field = mapping.get("target_field")
        source_key = mapping.get("source_key")
        if target_field not in fields:
            continue
        mapped_values = _metadata_values_for_source_key(source, source_key)
        if mapped_values:
            fields[target_field].extend(mapped_values)

    return {
        "author": _dedupe_metadata_values(fields["author"]),
        "rights": _dedupe_metadata_values(fields["rights"]),
        "keyword": _dedupe_metadata_values(fields["keyword"]),
        "tool": _dedupe_metadata_values(fields["tool"]),
        "credit": _dedupe_metadata_values(fields["credit"]),
    }


def _extract_author_values_from_tags(tags: object, author_prefix: str) -> list[str]:
    if not isinstance(tags, list):
        return []
    prefix = str(author_prefix or "").strip().lower().rstrip(":")
    if not prefix:
        prefix = "author"
    marker = f"{prefix}::"
    extracted: list[str] = []
    seen: set[str] = set()
    for raw_tag in tags:
        tag = str(raw_tag or "").strip()
        if not tag:
            continue
        if not tag.lower().startswith(marker):
            continue
        slug = tag.split("::", 1)[1] if "::" in tag else ""
        slug = str(slug or "").strip()
        if not slug or slug.lower() == "missing":
            continue
        candidate = re.sub(r"[-_]+", " ", slug).strip()
        if not candidate:
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        extracted.append(candidate)
    return extracted


def _slugify_metadata_value(value: str) -> str:
    raw = unicodedata.normalize("NFC", str(value or "").strip())
    if not raw:
        return ""
    lowered = raw.lower()
    lowered = re.sub(r"[^\w]+", "-", lowered, flags=re.UNICODE)
    lowered = lowered.replace("_", "-").strip("-")
    lowered = re.sub(r"-{2,}", "-", lowered)
    if not lowered:
        lowered = f"id-{hashlib.sha1(raw.encode('utf-8', errors='ignore')).hexdigest()[:12]}"
    return lowered


def _build_metadata_tags(metadata: dict, media_config: dict) -> tuple[list[str], dict]:
    cfg = _resolve_metadata_mappings_config(media_config)
    if not cfg["enabled"]:
        return [], {"missing_author": False, "missing_rights": False, "cfg": cfg}

    fields = _resolve_metadata_fields(metadata, cfg)
    authors = fields["author"]
    rights = fields["rights"]
    keywords = fields["keyword"]
    tools = fields["tool"]
    credits = fields["credit"]
    metadata_for_rules = {
        "authors": authors,
        "rights": rights,
        "keywords": keywords,
        "tools": tools,
        "credits": credits,
    }

    tags: list[str] = []

    author_prefix = cfg["author_tag_prefix"]
    keyword_prefix = cfg["keyword_tag_prefix"]

    if authors:
        max_slug_len = max(1, 64 - len(author_prefix) - 2)
        for author in authors[:12]:
            slug = _slugify_metadata_value(author)
            if not slug:
                continue
            if len(slug) > max_slug_len:
                slug = slug[:max_slug_len].strip("-")
            if slug:
                tags.append(f"{author_prefix}::{slug}")
    else:
        tags.append(f"{author_prefix}::missing")

    max_keyword_slug_len = max(1, 64 - len(keyword_prefix) - 2)
    for keyword in keywords[:30]:
        slug = _slugify_metadata_value(keyword)
        if not slug:
            continue
        if len(slug) > max_keyword_slug_len:
            slug = slug[:max_keyword_slug_len].strip("-")
        if slug:
            tags.append(f"{keyword_prefix}::{slug}")

    for rule in cfg["value_mappings"]:
        values = _metadata_values_for_field(metadata_for_rules, rule["field"])
        match = rule["match"]
        if any(match in value.lower() for value in values):
            tags.append(rule["tag"])

    return _normalize_tag_list(tags), {
        "missing_author": len(authors) == 0,
        "missing_rights": len(rights) == 0,
        "cfg": cfg,
    }


def _resolve_source_context_tags(config: dict, source_context: str | None) -> list[str]:
    context = str(source_context or "").strip().lower()
    if not context:
        return []
    prefix = _get_source_tag_prefix(config)
    context_slug = _normalize_source_context_slug(context)
    max_slug_len = max(1, 64 - len(prefix) - 2)
    if len(context_slug) > max_slug_len:
        context_slug = context_slug[:max_slug_len].rstrip("-")
    if not context_slug:
        context_slug = "unknown"
    return _normalize_tag_list([f"{prefix}::{context_slug}"])


def _is_reserved_cropping_tag(config: dict, tag: str) -> bool:
    normalized = _normalize_tag(tag)
    cropping = (config or {}).get("cropping_tags") if isinstance(config, dict) else None
    if not isinstance(cropping, dict):
        cropping = DEFAULT_MEDIA_CONFIG["cropping_tags"]

    base_tags = set(_normalize_tag_list(cropping.get("base_tags")))
    if normalized in base_tags:
        return True

    overrides = cropping.get("profile_overrides") if isinstance(cropping.get("profile_overrides"), dict) else {}
    override_tags = set()
    for value in overrides.values():
        if isinstance(value, str) and value.strip():
            override_tags.add(_normalize_tag(value))
    if normalized in override_tags:
        return True

    pattern = str(cropping.get("profile_tag_pattern") or "profile-{profile_id}")
    if "{profile_id}" in pattern:
        prefix = _normalize_tag(pattern.split("{profile_id}", 1)[0] or "profile-")
        if prefix and normalized.startswith(prefix):
            return True
    return False


def _is_source_context_tag(config: dict, tag: str) -> bool:
    normalized = _normalize_tag(tag)
    prefix = _get_source_tag_prefix(config)
    return normalized.startswith(f"{prefix}::")


def _is_retired_integration_context_tag(tag: str) -> bool:
    normalized = str(tag or "").strip().lower()
    return normalized.startswith(f"{RETIRED_INTEGRATION_TAG_PREFIX}::")


def _filter_retired_integration_context_tags(tags) -> list[str]:
    return [
        tag
        for tag in (tags or [])
        if isinstance(tag, str) and not _is_retired_integration_context_tag(tag)
    ]


def _is_metadata_mapping_tag(config: dict, tag: str) -> bool:
    normalized = _normalize_tag(tag)
    metadata_cfg = _resolve_metadata_mappings_config(config)
    prefixes = {
        metadata_cfg["author_tag_prefix"],
        metadata_cfg["rights_tag_prefix"],
        metadata_cfg["keyword_tag_prefix"],
    }
    return any(normalized.startswith(f"{prefix}::") for prefix in prefixes if prefix)


def _resolve_program_tagging_prefixes(config: dict) -> set[str]:
    defaults = DEFAULT_MEDIA_CONFIG["program_tagging"]
    raw = config.get("program_tagging") if isinstance(config, dict) and isinstance(config.get("program_tagging"), dict) else {}
    prefixes: set[str] = set()
    for key, default in (
        ("artist_tag_prefix", defaults["artist_tag_prefix"]),
        ("stage_tag_prefix", defaults["stage_tag_prefix"]),
        ("date_tag_prefix", defaults["date_tag_prefix"]),
    ):
        candidate = str(raw.get(key) or default).strip().lower().rstrip(":")
        try:
            normalized = _normalize_tag(candidate or default)
        except HTTPException:
            normalized = default
        if "::" in normalized:
            normalized = normalized.split("::", 1)[0] or default
        if normalized:
            prefixes.add(normalized)
    return prefixes


def _is_program_tag(config: dict, tag: str) -> bool:
    normalized = _normalize_tag(tag)
    prefixes = _resolve_program_tagging_prefixes(config)
    return any(normalized.startswith(f"{prefix}::") for prefix in prefixes if prefix)


async def _sync_custom_tags_from_asset_tags(config: dict, tags: list[str]) -> None:
    existing_raw = _normalize_tag_list(config.get("custom_tags") if isinstance(config, dict) else [])
    merged = set()
    for tag in existing_raw:
        if _is_reserved_cropping_tag(config, tag):
            continue
        if _is_retired_integration_context_tag(tag):
            continue
        if _is_source_context_tag(config, tag):
            continue
        if _is_metadata_mapping_tag(config, tag):
            continue
        if _is_program_tag(config, tag):
            continue
        merged.add(tag)

    for tag in _normalize_tag_list(tags):
        if _is_reserved_cropping_tag(config, tag):
            continue
        if _is_retired_integration_context_tag(tag):
            continue
        if _is_source_context_tag(config, tag):
            continue
        if _is_metadata_mapping_tag(config, tag):
            continue
        if _is_program_tag(config, tag):
            continue
        merged.add(tag)

    next_custom_tags = sorted(merged)
    if next_custom_tags == existing_raw:
        return

    coll = _db()[MEDIA_CONFIG_COLLECTION]
    await coll.update_one(
        {"key": MEDIA_CONFIG_KEY},
        {"$set": {"custom_tags": next_custom_tags, "updated_at": datetime.utcnow()}},
        upsert=True,
    )


@router.post(
    "/upload",
    response_model=AssetCreateResult,
    dependencies=[Depends(require_permission("assets:write"))],
)
async def upload_asset(
    file: UploadFile = File(...),
    source_context: str | None = Form(default=None),
    bypass_autocrop_transparent_padding: str | bool | None = Form(default=None),
    defer_required_metadata_validation: str | bool | None = Form(default=None),
):
    if not file.content_type:
        raise HTTPException(400, "Missing content-type")

    content_type = file.content_type.split(";")[0].strip().lower()
    if content_type in BLOCKED_CONTENT_TYPES:
        raise HTTPException(400, "File type not allowed")

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(400, "Empty file")

    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, "File too large (max 20 MB)")

    ext = (
        (file.filename or "").split(".")[-1].lower()
        if file.filename and "." in file.filename
        else ""
    )
    base_key = f"{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}"

    storage = get_storage()
    media_config = await _get_media_config()
    source_tags = _resolve_source_context_tags(media_config, source_context)
    file_type_tag = _build_file_type_tag(file.filename, content_type)
    should_trim_transparent_padding = not _coerce_bool(bypass_autocrop_transparent_padding, False)
    should_defer_required_metadata_validation = _coerce_bool(defer_required_metadata_validation, False)

    # Check if this is an image that should be processed
    if is_image(content_type):
        image_metadata = extract_image_metadata(data, content_type)
        metadata_tags, metadata_checks = _build_metadata_tags(image_metadata, media_config)
        metadata_cfg = metadata_checks["cfg"]
        if (
            not should_defer_required_metadata_validation
            and metadata_cfg.get("require_author")
            and metadata_checks.get("missing_author")
        ):
            raise HTTPException(400, "Image metadata is missing authorship information")
        if (
            not should_defer_required_metadata_validation
            and metadata_cfg.get("require_rights")
            and metadata_checks.get("missing_rights")
        ):
            raise HTTPException(400, "Image metadata is missing media rights information")

        responsive_config = await _get_admin_responsive_config()
        upload_variants_cfg = _resolve_upload_variants_config(media_config, responsive_config)
        stored_image = await _process_and_store_image_variants(
            storage,
            data=data,
            content_type=content_type,
            base_key=base_key,
            ext=ext,
            filename=file.filename,
            upload_variants_cfg=upload_variants_cfg,
            trim_transparent_padding=should_trim_transparent_padding,
        )
        variants = stored_image["processed"]
        stored_original = stored_image["stored_original"]
        stored_responsive = stored_image["stored_responsive"]

        assets = _db()["assets"]
        media_hash = _generate_media_hash(f"{stored_original.key}:{uuid.uuid4().hex}")
        doc = {
            "key": stored_original.key,
            "filename": stored_original.filename,
            "content_type": stored_original.content_type,
            "size": stored_original.size,
            "url": stored_original.url,
            "variants": stored_responsive,
            "width": variants.width,
            "height": variants.height,
            "alt": _asset_default_alt(stored_original.filename),
            "caption": {"de": "", "en": ""},
            "tags": _normalize_tag_list(source_tags + metadata_tags + [file_type_tag]),
            "metadata": image_metadata,
            "downloadable": False,
            "media_hash": media_hash,
            "created_at": datetime.utcnow(),
        }
        res = await assets.insert_one(doc)

        return AssetCreateResult(
            asset_id=str(res.inserted_id),
            url=stored_original.url,
            key=stored_original.key,
            content_type=stored_original.content_type,
            size=stored_original.size,
            width=variants.width,
            height=variants.height,
            downloadable=False,
            media_hash=media_hash,
            download_url=None,
            tags=doc["tags"],
            metadata=image_metadata,
            responsive_variants=build_asset_responsive_variants(stored_responsive),
        )
    elif content_type == "image/svg+xml":
        processed_svg = process_svg(data)
        key = f"{base_key}{('.' + ext) if ext else '.svg'}"
        stored = await storage.put(
            data=processed_svg.data,
            key=key,
            content_type=content_type,
            filename=file.filename or key,
        )

        assets = _db()["assets"]
        media_hash = _generate_media_hash(f"{stored.key}:{uuid.uuid4().hex}")
        doc = {
            "key": stored.key,
            "filename": stored.filename,
            "content_type": stored.content_type,
            "size": stored.size,
            "url": stored.url,
            "width": processed_svg.width,
            "height": processed_svg.height,
            "alt": _asset_default_alt(stored.filename),
            "caption": {"de": "", "en": ""},
            "tags": _normalize_tag_list(source_tags + [file_type_tag]),
            "downloadable": False,
            "media_hash": media_hash,
            "created_at": datetime.utcnow(),
        }
        res = await assets.insert_one(doc)

        return AssetCreateResult(
            asset_id=str(res.inserted_id),
            url=stored.url,
            key=stored.key,
            content_type=stored.content_type,
            size=stored.size,
            width=processed_svg.width,
            height=processed_svg.height,
            downloadable=False,
            media_hash=media_hash,
            download_url=None,
            tags=doc["tags"],
        )
    elif content_type in ALLOWED_NON_IMAGE_TYPES:
        # Non-image file - upload as-is (PDF, etc.)
        key = f"{base_key}{('.' + ext) if ext else ''}"
        stored = await storage.put(
            data=data,
            key=key,
            content_type=content_type,
            filename=file.filename or key,
        )

        assets = _db()["assets"]
        media_hash = _generate_media_hash(f"{stored.key}:{uuid.uuid4().hex}")
        doc = {
            "key": stored.key,
            "filename": stored.filename,
            "content_type": stored.content_type,
            "size": stored.size,
            "url": stored.url,
            "alt": _asset_default_alt(stored.filename),
            "caption": {"de": "", "en": ""},
            "tags": _normalize_tag_list(source_tags + [file_type_tag]),
            "downloadable": False,
            "media_hash": media_hash,
            "created_at": datetime.utcnow(),
        }
        res = await assets.insert_one(doc)

        return AssetCreateResult(
            asset_id=str(res.inserted_id),
            url=stored.url,
            key=stored.key,
            content_type=stored.content_type,
            size=stored.size,
            downloadable=False,
            media_hash=media_hash,
            download_url=None,
            tags=doc["tags"],
        )
    else:
        raise HTTPException(400, "File type not allowed (images, videos, or PDF only)")


async def import_asset_from_url_payload(
    payload: dict,
    *,
    request: Request | None = None,
) -> AssetCreateResult:
    """Import a remote media file by URL and store it as an asset."""
    source_url = str(payload.get("url", "")).strip()
    custom_filename = str(payload.get("filename", "")).strip()
    source_context = str(payload.get("source_context", "")).strip().lower() or None
    enable_metadata_extraction_tagging = _coerce_bool(
        payload.get("enable_metadata_extraction_tagging"),
        True,
    )
    bypass_autocrop_transparent_padding = _coerce_bool(
        payload.get("bypass_autocrop_transparent_padding"),
        False,
    )
    should_defer_required_metadata_validation = _coerce_bool(
        payload.get("defer_required_metadata_validation"),
        False,
    )
    if not source_url:
        raise HTTPException(400, "url is required")

    fetch_url = _resolve_import_source_url(source_url, request) if request is not None else source_url

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as client:
            resp = await client.get(fetch_url)
    except httpx.HTTPError as exc:
        raise HTTPException(400, f"Failed to fetch URL: {exc}") from exc

    if resp.status_code >= 400:
        raise HTTPException(400, f"Failed to fetch URL (HTTP {resp.status_code})")

    data = resp.content or b""
    if len(data) == 0:
        raise HTTPException(400, "Remote file is empty")
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, "File too large (max 20 MB)")

    resolved_source_url = str(resp.url or "").strip()
    filename = custom_filename or _infer_filename_from_url(resolved_source_url or source_url)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
    if not content_type or content_type == "application/octet-stream":
        guessed_type, _ = mimetypes.guess_type(filename)
        if guessed_type:
            content_type = guessed_type.lower()

    if ext == "svg" and content_type in {"", "application/xml", "text/xml", "text/plain"}:
        content_type = "image/svg+xml"

    if content_type in BLOCKED_CONTENT_TYPES:
        raise HTTPException(400, "File type not allowed")

    base_key = f"{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}"
    storage = get_storage()
    media_config = await _get_media_config()
    source_tags = _resolve_source_context_tags(media_config, source_context)
    file_type_tag = _build_file_type_tag(filename, content_type)

    if is_image(content_type):
        image_metadata = None
        metadata_tags: list[str] = []
        if enable_metadata_extraction_tagging:
            image_metadata = extract_image_metadata(data, content_type)
            metadata_tags, metadata_checks = _build_metadata_tags(image_metadata, media_config)
            metadata_cfg = metadata_checks["cfg"]
            if (
                not should_defer_required_metadata_validation
                and metadata_cfg.get("require_author")
                and metadata_checks.get("missing_author")
            ):
                raise HTTPException(400, "Image metadata is missing authorship information")
            if (
                not should_defer_required_metadata_validation
                and metadata_cfg.get("require_rights")
                and metadata_checks.get("missing_rights")
            ):
                raise HTTPException(400, "Image metadata is missing media rights information")

        responsive_config = await _get_admin_responsive_config()
        upload_variants_cfg = _resolve_upload_variants_config(media_config, responsive_config)
        stored_image = await _process_and_store_image_variants(
            storage,
            data=data,
            content_type=content_type,
            base_key=base_key,
            ext=ext,
            filename=filename,
            upload_variants_cfg=upload_variants_cfg,
            trim_transparent_padding=not bypass_autocrop_transparent_padding,
        )
        variants = stored_image["processed"]
        stored_original = stored_image["stored_original"]
        stored_responsive = stored_image["stored_responsive"]

        assets = _db()["assets"]
        media_hash = _generate_media_hash(f"{stored_original.key}:{uuid.uuid4().hex}")
        doc = {
            "key": stored_original.key,
            "filename": stored_original.filename,
            "content_type": stored_original.content_type,
            "size": stored_original.size,
            "url": stored_original.url,
            "variants": stored_responsive,
            "width": variants.width,
            "height": variants.height,
            "alt": _asset_default_alt(stored_original.filename),
            "caption": {"de": "", "en": ""},
            "tags": _normalize_tag_list(source_tags + metadata_tags + [file_type_tag]),
            "metadata": image_metadata,
            "source_url": source_url,
            "source_url_hash": _source_url_hash(source_url),
            "resolved_source_url": resolved_source_url or None,
            "resolved_source_url_hash": _source_url_hash(resolved_source_url),
            "downloadable": False,
            "media_hash": media_hash,
            "created_at": datetime.utcnow(),
        }
        res = await assets.insert_one(doc)

        return AssetCreateResult(
            asset_id=str(res.inserted_id),
            url=stored_original.url,
            key=stored_original.key,
            content_type=stored_original.content_type,
            size=stored_original.size,
            width=variants.width,
            height=variants.height,
            downloadable=False,
            media_hash=media_hash,
            download_url=None,
            tags=doc["tags"],
            metadata=image_metadata,
            responsive_variants=build_asset_responsive_variants(stored_responsive),
        )
    if content_type == "image/svg+xml":
        processed_svg = process_svg(data)
        key = f"{base_key}{('.' + ext) if ext else '.svg'}"
        stored = await storage.put(
            data=processed_svg.data,
            key=key,
            content_type=content_type,
            filename=filename or key,
        )

        assets = _db()["assets"]
        media_hash = _generate_media_hash(f"{stored.key}:{uuid.uuid4().hex}")
        doc = {
            "key": stored.key,
            "filename": stored.filename,
            "content_type": stored.content_type,
            "size": stored.size,
            "url": stored.url,
            "width": processed_svg.width,
            "height": processed_svg.height,
            "alt": _asset_default_alt(stored.filename),
            "caption": {"de": "", "en": ""},
            "tags": _normalize_tag_list(source_tags + [file_type_tag]),
            "source_url": source_url,
            "source_url_hash": _source_url_hash(source_url),
            "resolved_source_url": resolved_source_url or None,
            "resolved_source_url_hash": _source_url_hash(resolved_source_url),
            "downloadable": False,
            "media_hash": media_hash,
            "created_at": datetime.utcnow(),
        }
        res = await assets.insert_one(doc)

        return AssetCreateResult(
            asset_id=str(res.inserted_id),
            url=stored.url,
            key=stored.key,
            content_type=stored.content_type,
            size=stored.size,
            width=processed_svg.width,
            height=processed_svg.height,
            downloadable=False,
            media_hash=media_hash,
            download_url=None,
            tags=doc["tags"],
        )
    if content_type in ALLOWED_NON_IMAGE_TYPES:
        key = f"{base_key}{('.' + ext) if ext else ''}"
        stored = await storage.put(
            data=data,
            key=key,
            content_type=content_type,
            filename=filename or key,
        )

        assets = _db()["assets"]
        media_hash = _generate_media_hash(f"{stored.key}:{uuid.uuid4().hex}")
        doc = {
            "key": stored.key,
            "filename": stored.filename,
            "content_type": stored.content_type,
            "size": stored.size,
            "url": stored.url,
            "alt": _asset_default_alt(stored.filename),
            "caption": {"de": "", "en": ""},
            "tags": _normalize_tag_list(source_tags + [file_type_tag]),
            "source_url": source_url,
            "source_url_hash": _source_url_hash(source_url),
            "resolved_source_url": resolved_source_url or None,
            "resolved_source_url_hash": _source_url_hash(resolved_source_url),
            "downloadable": False,
            "media_hash": media_hash,
            "created_at": datetime.utcnow(),
        }
        res = await assets.insert_one(doc)

        return AssetCreateResult(
            asset_id=str(res.inserted_id),
            url=stored.url,
            key=stored.key,
            content_type=stored.content_type,
            size=stored.size,
            downloadable=False,
            media_hash=media_hash,
            download_url=None,
            tags=doc["tags"],
        )

    raise HTTPException(400, "File type not allowed (images, videos, or PDF only)")


@router.post(
    "/import-url",
    response_model=AssetCreateResult,
    dependencies=[Depends(require_permission("assets:write"))],
)
async def import_asset_from_url(request: Request, payload: dict = Body(...)):
    return await import_asset_from_url_payload(payload, request=request)


@router.post(
    "/regenerate-variants",
    dependencies=[Depends(require_permission("assets:write"))],
)
async def regenerate_asset_variants(payload: dict | None = Body(default=None)):
    """Regenerate thumbnails and responsive variants for all raster image assets."""
    options = payload if isinstance(payload, dict) else {}
    trim_transparent_padding = not _coerce_bool(
        options.get("bypass_autocrop_transparent_padding"),
        False,
    )

    assets = _db()["assets"]
    storage = get_storage()
    media_config = await _get_media_config()
    responsive_config = await _get_admin_responsive_config()
    upload_variants_cfg = _resolve_upload_variants_config(media_config, responsive_config)

    query = {
        "content_type": {
            "$in": ["image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"],
        }
    }
    summary = {
        "processed": 0,
        "regenerated": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
    }

    async for doc in assets.find(query):
        summary["processed"] += 1
        asset_id = str(doc.get("_id") or "")
        filename = str(doc.get("filename") or "")
        key = str(doc.get("key") or "").strip()
        content_type = str(doc.get("content_type") or "").split(";", 1)[0].strip().lower()
        if not key or not content_type or not is_image(content_type):
            summary["skipped"] += 1
            continue

        data = await storage.get(key=key)
        if not data:
            summary["skipped"] += 1
            summary["errors"].append({
                "asset_id": asset_id,
                "filename": filename,
                "error": "Original file could not be read from storage",
            })
            continue

        try:
            base_key, ext = _split_asset_storage_key(key, content_type)
            previous_generated_keys = _generated_variant_keys(doc)
            stored_image = await _process_and_store_image_variants(
                storage,
                data=data,
                content_type=content_type,
                base_key=base_key,
                ext=ext,
                filename=filename,
                upload_variants_cfg=upload_variants_cfg,
                trim_transparent_padding=trim_transparent_padding,
            )
            variants = stored_image["processed"]
            stored_original = stored_image["stored_original"]
            stored_responsive = stored_image["stored_responsive"]
            new_generated_keys = _stored_image_generated_keys(stored_image)
            stale_keys = previous_generated_keys - new_generated_keys - {stored_original.key}
            await _delete_storage_keys(storage, stale_keys)

            media_hash = _generate_media_hash(f"{stored_original.key}:{uuid.uuid4().hex}")
            await assets.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "key": stored_original.key,
                        "content_type": stored_original.content_type,
                        "size": stored_original.size,
                        "url": stored_original.url,
                        "variants": stored_responsive,
                        "width": variants.width,
                        "height": variants.height,
                        "media_hash": media_hash,
                        "updated_at": datetime.utcnow(),
                    },
                },
            )
            summary["regenerated"] += 1
        except Exception as exc:
            summary["failed"] += 1
            summary["errors"].append({
                "asset_id": asset_id,
                "filename": filename,
                "error": str(exc)[:300] or exc.__class__.__name__,
            })

    return summary


@router.get(
    "",
    response_model=AssetListResponse,
    dependencies=[Depends(require_permission("assets:read"))],
)
async def list_assets(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: str = Query("", description="Search by filename"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
):
    """List all assets with pagination and optional search/tag filter."""
    assets = _db()["assets"]
    media_config = await _get_media_config()
    metadata_cfg = _resolve_metadata_mappings_config(media_config)

    # Build query
    query = {}
    if search:
        query["filename"] = {"$regex": search, "$options": "i"}
    if tag:
        query["tags"] = tag

    # Get total count
    total = await assets.count_documents(query)

    # Get paginated results
    skip = (page - 1) * page_size
    cursor = assets.find(query).sort("created_at", -1).skip(skip).limit(page_size)

    items = []
    async for doc in cursor:
        items.append(
            await _asset_list_item_from_doc(
                doc,
                assets_coll=assets,
                metadata_cfg=metadata_cfg,
            )
        )

    return AssetListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(skip + len(items)) < total,
    )


@router.get("/public", response_model=AssetListResponse)
async def list_public_assets_by_tag(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    tag: str = Query(..., min_length=1, description="Filter by exact media tag"),
):
    """Public, tag-scoped asset lookup for generated page galleries."""
    normalized_tag = _normalize_tag(tag)
    assets = _db()["assets"]
    media_config = await _get_media_config()
    metadata_cfg = _resolve_metadata_mappings_config(media_config)
    query = {"tags": normalized_tag}

    total = await assets.count_documents(query)
    skip = (page - 1) * page_size
    cursor = assets.find(query).sort("created_at", -1).skip(skip).limit(page_size)

    items = []
    async for doc in cursor:
        items.append(
            await _asset_list_item_from_doc(
                doc,
                assets_coll=assets,
                metadata_cfg=metadata_cfg,
                ensure_media_hash=False,
            )
        )

    return AssetListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(skip + len(items)) < total,
    )


@router.get(
    "/tags",
    dependencies=[Depends(require_permission("assets:read"))],
)
async def list_tags():
    """Return all distinct tags used across assets."""
    assets = _db()["assets"]
    asset_tags = [
        t
        for t in await assets.distinct("tags")
        if isinstance(t, str) and not _is_retired_integration_context_tag(t)
    ]
    media_config = await _get_media_config()
    custom_tags = _filter_retired_integration_context_tags(
        _normalize_tag_list(media_config.get("custom_tags"))
    )
    return {"tags": sorted(set(asset_tags) | set(custom_tags))}


@router.patch(
    "/{asset_id}/tags",
    dependencies=[Depends(require_permission("assets:write"))],
)
async def update_asset_tags(asset_id: str, tags: list[str] = Body(..., embed=True)):
    """Set the tags for an asset (replaces existing tags)."""
    assets = _db()["assets"]

    try:
        doc = await assets.find_one({"_id": ObjectId(asset_id)})
    except Exception:
        raise HTTPException(400, "Invalid asset ID")

    if not doc:
        raise HTTPException(404, "Asset not found")

    clean_tags = _normalize_tag_list(tags)

    await assets.update_one(
        {"_id": ObjectId(asset_id)},
        {"$set": {"tags": clean_tags}},
    )

    media_config = await _get_media_config()
    await _sync_custom_tags_from_asset_tags(media_config, clean_tags)

    return {"status": "updated", "asset_id": asset_id, "tags": clean_tags}


@router.patch(
    "/{asset_id}/text",
    dependencies=[Depends(require_permission("assets:write"))],
)
async def update_asset_text(asset_id: str, payload: dict = Body(...)):
    """Set bilingual alt/caption text for an asset."""
    assets = _db()["assets"]

    try:
        doc = await assets.find_one({"_id": ObjectId(asset_id)})
    except Exception:
        raise HTTPException(400, "Invalid asset ID")

    if not doc:
        raise HTTPException(404, "Asset not found")

    payload_obj = payload if isinstance(payload, dict) else {}
    has_alt = "alt" in payload_obj
    has_caption = "caption" in payload_obj

    alt = (
        _normalize_bilingual_text(payload_obj.get("alt"), doc.get("filename", ""))
        if has_alt
        else _normalize_bilingual_text(doc.get("alt"), doc.get("filename", ""))
    )
    caption = (
        _normalize_bilingual_text(payload_obj.get("caption"), "")
        if has_caption
        else _normalize_bilingual_text(doc.get("caption"), "")
    )

    await assets.update_one(
        {"_id": ObjectId(asset_id)},
        {"$set": {"alt": alt, "caption": caption}},
    )

    if has_caption:
        await _sync_gallery_asset_caption(
            asset_id,
            caption,
            media_urls=[
                doc.get("url"),
            ],
        )

    return {"status": "updated", "asset_id": asset_id, "alt": alt, "caption": caption}


@router.patch(
    "/{asset_id}/downloadable",
    dependencies=[Depends(require_permission("assets:write"))],
)
async def update_asset_downloadable(
    asset_id: str,
    request: Request,
    downloadable: bool = Body(..., embed=True),
):
    """Toggle whether an asset is available via the public /download proxy route."""
    assets = _db()["assets"]

    try:
        doc = await assets.find_one({"_id": ObjectId(asset_id)})
    except Exception:
        raise HTTPException(400, "Invalid asset ID")

    if not doc:
        raise HTTPException(404, "Asset not found")

    media_hash = await _ensure_asset_media_hash(doc, assets_coll=assets)
    if not media_hash:
        raise HTTPException(500, "Failed to generate media hash for asset")

    enabled = bool(downloadable)
    await assets.update_one(
        {"_id": ObjectId(asset_id)},
        {"$set": {"downloadable": enabled, "media_hash": media_hash}},
    )

    doc["downloadable"] = enabled
    doc["media_hash"] = media_hash
    return {
        "status": "updated",
        "asset_id": asset_id,
        "downloadable": enabled,
        "media_hash": media_hash,
        "download_url": _resolve_download_url(
            doc,
            media_hash=media_hash,
        ),
    }


@router.post(
    "/tags/rename",
    dependencies=[Depends(require_permission("assets:write"))],
)
async def rename_tag(payload: dict = Body(...)):
    assets = _db()["assets"]
    media_config = await _get_media_config()

    from_tag = _normalize_tag(payload.get("from_tag", ""))
    to_tag = _normalize_tag(payload.get("to_tag", ""))
    if not from_tag or not to_tag:
        raise HTTPException(400, "from_tag and to_tag are required")
    if from_tag == to_tag:
        raise HTTPException(400, "from_tag and to_tag must be different")
    if _is_reserved_cropping_tag(media_config, from_tag):
        raise HTTPException(400, f"Tag '{from_tag}' is reserved and cannot be renamed")
    if _is_reserved_cropping_tag(media_config, to_tag):
        raise HTTPException(400, f"Tag '{to_tag}' is reserved and cannot be used")

    updated = 0
    cursor = assets.find({"tags": from_tag}, {"tags": 1})
    async for doc in cursor:
        current = _normalize_tag_list(doc.get("tags", []))
        if from_tag not in current:
            continue
        next_tags = _normalize_tag_list([to_tag if tag == from_tag else tag for tag in current])
        await assets.update_one({"_id": doc["_id"]}, {"$set": {"tags": next_tags}})
        updated += 1

    current_custom_tags = _normalize_tag_list(media_config.get("custom_tags"))
    if from_tag in current_custom_tags:
        next_custom_tags = _normalize_tag_list([to_tag if tag == from_tag else tag for tag in current_custom_tags])
        await _db()[MEDIA_CONFIG_COLLECTION].update_one(
            {"key": MEDIA_CONFIG_KEY},
            {"$set": {"custom_tags": next_custom_tags, "updated_at": datetime.utcnow()}},
            upsert=True,
        )
    return {"ok": True, "from_tag": from_tag, "to_tag": to_tag, "updated_assets": updated}


@router.post(
    "/tags/delete",
    dependencies=[Depends(require_permission("assets:write"))],
)
async def delete_tag(payload: dict = Body(...)):
    assets = _db()["assets"]
    media_config = await _get_media_config()

    tag = _normalize_tag(payload.get("tag", ""))
    if not tag:
        raise HTTPException(400, "tag is required")
    if _is_reserved_cropping_tag(media_config, tag):
        raise HTTPException(400, f"Tag '{tag}' is reserved and cannot be deleted")

    updated = 0
    cursor = assets.find({"tags": tag}, {"tags": 1})
    async for doc in cursor:
        current = _normalize_tag_list(doc.get("tags", []))
        if tag not in current:
            continue
        next_tags = [entry for entry in current if entry != tag]
        await assets.update_one({"_id": doc["_id"]}, {"$set": {"tags": next_tags}})
        updated += 1

    current_custom_tags = _normalize_tag_list(media_config.get("custom_tags"))
    if tag in current_custom_tags:
        next_custom_tags = [entry for entry in current_custom_tags if entry != tag]
        await _db()[MEDIA_CONFIG_COLLECTION].update_one(
            {"key": MEDIA_CONFIG_KEY},
            {"$set": {"custom_tags": next_custom_tags, "updated_at": datetime.utcnow()}},
            upsert=True,
        )
    return {"ok": True, "tag": tag, "updated_assets": updated}


@router.patch(
    "/{asset_id}/rename",
    dependencies=[Depends(require_permission("assets:write"))],
)
async def rename_asset(asset_id: str, filename: str = Body(..., embed=True)):
    """Rename an asset's filename."""
    assets = _db()["assets"]

    try:
        doc = await assets.find_one({"_id": ObjectId(asset_id)})
    except Exception:
        raise HTTPException(400, "Invalid asset ID")

    if not doc:
        raise HTTPException(404, "Asset not found")

    new_filename = filename.strip()
    if not new_filename:
        raise HTTPException(400, "Filename cannot be empty")

    await assets.update_one(
        {"_id": ObjectId(asset_id)},
        {"$set": {"filename": new_filename}},
    )

    return {"status": "renamed", "asset_id": asset_id, "filename": new_filename}


@router.delete(
    "/{asset_id}",
    dependencies=[Depends(require_permission("assets:write"))],
)
async def delete_asset(asset_id: str):
    """Delete an asset and all its variants from storage."""
    assets = _db()["assets"]

    # Find the asset
    try:
        doc = await assets.find_one({"_id": ObjectId(asset_id)})
    except Exception:
        raise HTTPException(400, "Invalid asset ID")

    if not doc:
        raise HTTPException(404, "Asset not found")

    storage = get_storage()

    # Delete the original and generated responsive variants from storage.
    keys_to_delete = [doc.get("key")]
    variants = doc.get("variants")
    if isinstance(variants, dict):
        for variant in variants.values():
            if isinstance(variant, dict):
                key = variant.get("key")
                if key:
                    keys_to_delete.append(key)

    for key in keys_to_delete:
        if key:
            try:
                await storage.delete(key=key)
            except Exception:
                # Log but don't fail if storage deletion fails
                pass

    # Delete from database
    await assets.delete_one({"_id": ObjectId(asset_id)})

    return {"status": "deleted", "asset_id": asset_id}
