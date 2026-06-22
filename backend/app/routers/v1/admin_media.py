from __future__ import annotations

from datetime import datetime
import re
import unicodedata
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pymongo import ReturnDocument

from app.collection_names import MEDIA_CONFIG_COLLECTION
from app.db import get_client
from app.deps import require_permission
from app.media_responsive import normalize_media_variant_entries
from app.public_cache import invalidate_ttl_cache_prefix
from app.security import KeycloakUser
from app.settings import settings

router = APIRouter(prefix="/admin/media-config", tags=["admin"])

MEDIA_CONFIG_KEY = MEDIA_CONFIG_COLLECTION
MAX_TAG_LENGTH = 64
ALLOWED_TAG_SPECIAL_CHARS = frozenset({":", "_", "-"})
SYSTEM_BASE_TAGS = {"cropped", "auto"}
RETIRED_INTEGRATION_TAG_PREFIX = "integration"
DEFAULT_CONFIG = {
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
    "fallback_images": {
        "images": [],
        "media_tag": "",
        "image_url": "",
        "image_zoom": 1.0,
        "image_focal_x": 50.0,
        "image_focal_y": 50.0,
        "image_rotation": 0.0,
    },
}


def _db():
    return get_client()[settings.mongo_db]


def _is_valid_tag(tag: str) -> bool:
    if not tag or len(tag) > MAX_TAG_LENGTH:
        return False
    if not tag[0].isalnum():
        return False
    return all(char.isalnum() or char in ALLOWED_TAG_SPECIAL_CHARS for char in tag)


def _normalize_tag(raw: str) -> str:
    tag = unicodedata.normalize("NFC", str(raw or "").strip()).lower()
    if not tag:
        return ""
    if not _is_valid_tag(tag):
        raise HTTPException(400, f"Invalid tag '{raw}'")
    return tag


def _normalize_tag_list(values) -> list[str]:
    tags = []
    for raw in values or []:
        tag = _normalize_tag(raw)
        if tag:
            tags.append(tag)
    return sorted(set(tags))


def _normalize_source_tag_prefix(raw) -> str:
    return _normalize_tag_prefix(raw, default="source", field_name="source_tag_prefix")


def _normalize_tag_prefix(raw, *, default: str, field_name: str) -> str:
    prefix = str(raw or default).strip().lower()
    if not prefix:
        prefix = default
    if prefix.endswith(":"):
        prefix = prefix.rstrip(":")
    tag = _normalize_tag(prefix)
    if "::" in tag:
        raise HTTPException(400, f"{field_name} must not contain '::'")
    return tag


def _normalize_int(raw, field_name: str, min_value: int, max_value: int, default_value: int) -> int:
    try:
        value = int(raw)
    except Exception:
        value = default_value
    if value < min_value or value > max_value:
        raise HTTPException(400, f"{field_name} must be between {min_value} and {max_value}")
    return value


def _normalize_bool(raw, default_value: bool) -> bool:
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
    return default_value


def _normalize_float(raw, field_name: str, min_value: float, max_value: float, default_value: float) -> float:
    try:
        value = float(raw)
    except Exception:
        value = default_value
    if value < min_value or value > max_value:
        raise HTTPException(400, f"{field_name} must be between {min_value:g} and {max_value:g}")
    return value


def _normalize_variant_id(raw: str) -> str:
    variant_id = re.sub(r"[^a-z0-9_-]+", "-", str(raw or "").strip().lower())
    variant_id = re.sub(r"-+", "-", variant_id).strip("-")[:48]
    if not variant_id or not variant_id[0].isalnum():
        return ""
    return variant_id


def _normalize_upload_variants(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise HTTPException(400, "upload_variants must be an object")

    defaults = DEFAULT_CONFIG["upload_variants"]
    fixed_variant_names = ("mobile", "thumb", "tablet", "desktop")
    raw_custom_variants = raw.get("custom") if isinstance(raw.get("custom"), list) else None
    if raw_custom_variants is None:
        raw_custom_variants = defaults["custom"]
    thumb_custom = next(
        (
            entry
            for entry in raw_custom_variants
            if isinstance(entry, dict) and _normalize_variant_id(entry.get("id")) == "thumb"
        ),
        None,
    )

    def normalize_variant(name: str) -> dict:
        source = raw.get(name) if isinstance(raw.get(name), dict) else {}
        if name == "thumb" and not source and isinstance(thumb_custom, dict):
            source = thumb_custom
        default_entry = defaults[name]
        enabled = source.get("enabled", default_entry["enabled"])
        width_raw = source.get("width", default_entry["width"])
        return {
            "enabled": _normalize_bool(enabled, default_entry["enabled"]),
            "width": _normalize_int(width_raw, f"upload_variants.{name}.width", 64, 4096, default_entry["width"]),
        }

    custom_variants = []
    seen_custom_ids: set[str] = set()
    for entry in raw_custom_variants:
        if not isinstance(entry, dict):
            continue
        variant_id = _normalize_variant_id(entry.get("id")) or _normalize_variant_id(entry.get("label"))
        if not variant_id or variant_id in fixed_variant_names or variant_id == "small" or variant_id in seen_custom_ids:
            continue
        seen_custom_ids.add(variant_id)
        label = str(entry.get("label") or variant_id.replace("_", " ").replace("-", " ").title()).strip()
        custom_variants.append(
            {
                "id": variant_id,
                "label": label[:80] or variant_id,
                "enabled": _normalize_bool(entry.get("enabled"), True),
                "width": _normalize_int(entry.get("width"), f"upload_variants.custom.{variant_id}.width", 64, 4096, 480),
            }
        )

    max_original_width = _normalize_int(
        raw.get("max_original_width", defaults["max_original_width"]),
        "upload_variants.max_original_width",
        256,
        4096,
        defaults["max_original_width"],
    )

    return {
        "mobile": normalize_variant("mobile"),
        "thumb": normalize_variant("thumb"),
        "tablet": normalize_variant("tablet"),
        "desktop": normalize_variant("desktop"),
        "custom": custom_variants,
        "max_original_width": max_original_width,
    }


def _normalize_metadata_mappings(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise HTTPException(400, "metadata_mappings must be an object")

    defaults = DEFAULT_CONFIG["metadata_mappings"]
    allowed_fields = {"author", "rights", "keyword", "tool", "credit"}

    enabled = _normalize_bool(raw.get("enabled"), defaults["enabled"])
    author_tag_prefix = _normalize_tag_prefix(
        raw.get("author_tag_prefix"),
        default=defaults["author_tag_prefix"],
        field_name="metadata_mappings.author_tag_prefix",
    )
    rights_tag_prefix = _normalize_tag_prefix(
        raw.get("rights_tag_prefix"),
        default=defaults["rights_tag_prefix"],
        field_name="metadata_mappings.rights_tag_prefix",
    )
    keyword_tag_prefix = _normalize_tag_prefix(
        raw.get("keyword_tag_prefix"),
        default=defaults["keyword_tag_prefix"],
        field_name="metadata_mappings.keyword_tag_prefix",
    )
    require_author = _normalize_bool(raw.get("require_author"), defaults["require_author"])
    require_rights = _normalize_bool(raw.get("require_rights"), defaults["require_rights"])

    mappings = []
    seen = set()
    raw_mappings = raw.get("value_mappings") if isinstance(raw.get("value_mappings"), list) else []
    for entry in raw_mappings:
        if not isinstance(entry, dict):
            continue
        field = str(entry.get("field", "")).strip().lower()
        match = str(entry.get("match", "")).strip().lower()
        if field not in allowed_fields or not match:
            continue
        tag = _normalize_tag(entry.get("tag", ""))
        if not tag:
            continue
        key = (field, match, tag)
        if key in seen:
            continue
        seen.add(key)
        mappings.append({"field": field, "match": match, "tag": tag})

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

    return {
        "enabled": enabled,
        "author_tag_prefix": author_tag_prefix,
        "rights_tag_prefix": rights_tag_prefix,
        "keyword_tag_prefix": keyword_tag_prefix,
        "require_author": require_author,
        "require_rights": require_rights,
        "key_mappings": key_mappings,
        "value_mappings": mappings,
    }


def _normalize_program_tagging(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise HTTPException(400, "program_tagging must be an object")

    defaults = DEFAULT_CONFIG["program_tagging"]
    artist_tag_prefix = _normalize_tag_prefix(
        raw.get("artist_tag_prefix"),
        default=defaults["artist_tag_prefix"],
        field_name="program_tagging.artist_tag_prefix",
    )
    stage_tag_prefix = _normalize_tag_prefix(
        raw.get("stage_tag_prefix"),
        default=defaults["stage_tag_prefix"],
        field_name="program_tagging.stage_tag_prefix",
    )
    date_tag_prefix = _normalize_tag_prefix(
        raw.get("date_tag_prefix"),
        default=defaults["date_tag_prefix"],
        field_name="program_tagging.date_tag_prefix",
    )
    return {
        "artist_tag_prefix": artist_tag_prefix,
        "stage_tag_prefix": stage_tag_prefix,
        "date_tag_prefix": date_tag_prefix,
    }


def _normalize_cropping_tags(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise HTTPException(400, "cropping_tags must be an object")

    base_tags = _normalize_tag_list(raw.get("base_tags") if isinstance(raw.get("base_tags"), list) else [])
    base_set = set(base_tags)
    base_set.update(SYSTEM_BASE_TAGS)

    pattern = str(raw.get("profile_tag_pattern") or "profile-{profile_id}").strip().lower()
    if "{profile_id}" not in pattern:
        raise HTTPException(400, "cropping_tags.profile_tag_pattern must include '{profile_id}'")
    # Validate by substituting a sample profile id.
    _normalize_tag(pattern.replace("{profile_id}", "sample"))

    raw_overrides = raw.get("profile_overrides") if isinstance(raw.get("profile_overrides"), dict) else {}
    overrides: dict[str, str] = {}
    for profile_id, value in raw_overrides.items():
        profile_key = str(profile_id or "").strip().lower()
        if not profile_key:
            continue
        tag = _normalize_tag(value)
        if not tag:
            continue
        overrides[profile_key] = tag

    return {
        "base_tags": sorted(base_set),
        "profile_tag_pattern": pattern,
        "profile_overrides": dict(sorted(overrides.items(), key=lambda item: item[0])),
    }


def _normalize_fallback_image_entry(raw_entry: Any, index: int = 0) -> dict[str, Any] | None:
    if not isinstance(raw_entry, dict):
        return None

    image_url = str(
        raw_entry.get("image_url")
        or raw_entry.get("url")
        or raw_entry.get("src")
        or raw_entry.get("href")
        or ""
    ).strip()
    if not image_url:
        return None

    raw_variants = (
        raw_entry.get("responsiveVariants")
        if "responsiveVariants" in raw_entry
        else raw_entry.get("responsive_variants")
        if "responsive_variants" in raw_entry
        else raw_entry.get("image_responsive_variants")
    )
    return {
        "id": str(raw_entry.get("id") or f"fallback-{index + 1}").strip() or f"fallback-{index + 1}",
        "image_url": image_url,
        "responsive_variants": normalize_media_variant_entries(raw_variants),
    }


def _normalize_fallback_images(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raw = {}

    defaults = DEFAULT_CONFIG["fallback_images"]
    seen_urls: set[str] = set()
    images: list[dict[str, Any]] = []
    raw_images = raw.get("images") if isinstance(raw.get("images"), list) else []
    for index, raw_entry in enumerate(raw_images):
        entry = _normalize_fallback_image_entry(raw_entry, index)
        if not entry:
            continue
        image_url = entry["image_url"]
        if image_url in seen_urls:
            continue
        seen_urls.add(image_url)
        images.append(entry)

    def pick(*keys: str):
        for key in keys:
            if key in raw:
                return raw.get(key)
        return None

    direct_image_url = str(
        pick("image_url", "legacyImageUrl") or defaults["image_url"]
    ).strip()
    primary_image = None
    if direct_image_url:
        primary_image = next((entry for entry in images if entry["image_url"] == direct_image_url), None)
        if primary_image is None:
            primary_image = _normalize_fallback_image_entry(
                {
                    "id": str(raw.get("id") or "fallback-global").strip() or "fallback-global",
                    "image_url": direct_image_url,
                    "responsive_variants": (
                        raw.get("responsiveVariants")
                        if "responsiveVariants" in raw
                        else raw.get("responsive_variants")
                        if "responsive_variants" in raw
                        else raw.get("image_responsive_variants")
                    ),
                },
                0,
            )
    if primary_image is None and images:
        primary_image = images[0]

    single_images = [primary_image] if primary_image else []
    image_url = primary_image["image_url"] if primary_image else ""

    return {
        "images": single_images,
        "media_tag": "",
        "image_url": image_url,
        "image_zoom": _normalize_float(pick("image_zoom", "imageZoom", "zoom"), "fallback_images.image_zoom", 1, 4, defaults["image_zoom"]),
        "image_focal_x": _normalize_float(pick("image_focal_x", "imageFocalX", "focalX"), "fallback_images.image_focal_x", 0, 100, defaults["image_focal_x"]),
        "image_focal_y": _normalize_float(pick("image_focal_y", "imageFocalY", "focalY"), "fallback_images.image_focal_y", 0, 100, defaults["image_focal_y"]),
        "image_rotation": _normalize_float(pick("image_rotation", "imageRotation", "rotation"), "fallback_images.image_rotation", -180, 180, defaults["image_rotation"]),
    }


def _invalidate_public_media_fallback_cache() -> None:
    invalidate_ttl_cache_prefix("public:page-bundle:")


def _build_default_doc(now: datetime) -> dict:
    return {
        "key": MEDIA_CONFIG_KEY,
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
        "fallback_images": {
            "images": [],
            "media_tag": "",
            "image_url": "",
            "image_zoom": 1.0,
            "image_focal_x": 50.0,
            "image_focal_y": 50.0,
            "image_rotation": 0.0,
        },
        "created_at": now,
        "updated_at": now,
    }


def _normalize_config(doc: dict | None, *, strict_custom_tags: bool = True) -> dict:
    source = doc or {}
    custom_tags = _normalize_tag_list(source.get("custom_tags") if isinstance(source.get("custom_tags"), list) else [])
    source_tag_prefix = _normalize_source_tag_prefix(source.get("source_tag_prefix"))
    upload_variants = _normalize_upload_variants(
        source.get("upload_variants")
        if isinstance(source.get("upload_variants"), dict)
        else DEFAULT_CONFIG["upload_variants"]
    )
    metadata_mappings = _normalize_metadata_mappings(
        source.get("metadata_mappings")
        if isinstance(source.get("metadata_mappings"), dict)
        else DEFAULT_CONFIG["metadata_mappings"]
    )
    program_tagging = _normalize_program_tagging(
        source.get("program_tagging")
        if isinstance(source.get("program_tagging"), dict)
        else DEFAULT_CONFIG["program_tagging"]
    )
    cropping_tags = _normalize_cropping_tags(
        source.get("cropping_tags") if isinstance(source.get("cropping_tags"), dict) else DEFAULT_CONFIG["cropping_tags"]
    )
    fallback_images = _normalize_fallback_images(
        source.get("fallback_images") if isinstance(source.get("fallback_images"), dict) else DEFAULT_CONFIG["fallback_images"]
    )

    reserved = set(cropping_tags["base_tags"]) | set(cropping_tags["profile_overrides"].values())
    pattern = cropping_tags["profile_tag_pattern"]
    prefix = _normalize_tag(pattern.split("{profile_id}", 1)[0] or "profile-")
    metadata_prefixes = {
        metadata_mappings["author_tag_prefix"],
        metadata_mappings["rights_tag_prefix"],
        metadata_mappings["keyword_tag_prefix"],
    }
    program_prefixes = {
        program_tagging["artist_tag_prefix"],
        program_tagging["stage_tag_prefix"],
        program_tagging["date_tag_prefix"],
    }
    normalized_custom_tags: list[str] = []
    for tag in custom_tags:
        conflict_message = ""
        if tag in reserved or (prefix and tag.startswith(prefix)):
            conflict_message = f"Custom tag '{tag}' conflicts with reserved cropping tags"
        elif tag.startswith(f"{RETIRED_INTEGRATION_TAG_PREFIX}::"):
            conflict_message = f"Custom tag '{tag}' uses retired integration-tag prefix"
        elif tag.startswith(f"{source_tag_prefix}::"):
            conflict_message = f"Custom tag '{tag}' conflicts with source-tag prefix"
        elif any(tag.startswith(f"{meta_prefix}::") for meta_prefix in metadata_prefixes if meta_prefix):
            conflict_message = f"Custom tag '{tag}' conflicts with metadata tag prefix"
        elif any(tag.startswith(f"{program_prefix}::") for program_prefix in program_prefixes if program_prefix):
            conflict_message = f"Custom tag '{tag}' conflicts with program tag prefix"

        if conflict_message:
            if strict_custom_tags:
                raise HTTPException(400, conflict_message)
            continue

        normalized_custom_tags.append(tag)

    custom_tags = sorted(set(normalized_custom_tags))

    return {
        "custom_tags": custom_tags,
        "source_tag_prefix": source_tag_prefix,
        "upload_variants": upload_variants,
        "metadata_mappings": metadata_mappings,
        "program_tagging": program_tagging,
        "cropping_tags": cropping_tags,
        "fallback_images": fallback_images,
    }


@router.get("")
async def get_media_config(
    _: KeycloakUser = Depends(require_permission("assets:read")),
):
    coll = _db()[MEDIA_CONFIG_COLLECTION]
    now = datetime.utcnow()
    doc = await coll.find_one({"key": MEDIA_CONFIG_KEY})
    if not doc:
        doc = _build_default_doc(now)
        res = await coll.insert_one(doc)
        doc["_id"] = res.inserted_id

    normalized = _normalize_config(doc, strict_custom_tags=False)
    if (
        normalized["custom_tags"] != (doc.get("custom_tags") or [])
        or normalized["source_tag_prefix"] != str(doc.get("source_tag_prefix") or "source")
        or normalized["upload_variants"] != (doc.get("upload_variants") or {})
        or normalized["metadata_mappings"] != (doc.get("metadata_mappings") or {})
        or normalized["program_tagging"] != (doc.get("program_tagging") or {})
        or normalized["cropping_tags"] != (doc.get("cropping_tags") or {})
        or normalized["fallback_images"] != (doc.get("fallback_images") or {})
    ):
        doc = await coll.find_one_and_update(
            {"key": MEDIA_CONFIG_KEY},
            {
                "$set": {
                    "custom_tags": normalized["custom_tags"],
                    "source_tag_prefix": normalized["source_tag_prefix"],
                    "upload_variants": normalized["upload_variants"],
                    "metadata_mappings": normalized["metadata_mappings"],
                    "program_tagging": normalized["program_tagging"],
                    "cropping_tags": normalized["cropping_tags"],
                    "fallback_images": normalized["fallback_images"],
                    "updated_at": now,
                },
                "$unset": {"source_tags": ""},
            },
            return_document=ReturnDocument.AFTER,
        )
        _invalidate_public_media_fallback_cache()

    return {
        "id": str(doc["_id"]),
        "custom_tags": normalized["custom_tags"],
        "source_tag_prefix": normalized["source_tag_prefix"],
        "upload_variants": normalized["upload_variants"],
        "metadata_mappings": normalized["metadata_mappings"],
        "program_tagging": normalized["program_tagging"],
        "cropping_tags": normalized["cropping_tags"],
        "fallback_images": normalized["fallback_images"],
        "updated_at": doc.get("updated_at"),
        "created_at": doc.get("created_at"),
    }


@router.patch("", dependencies=[Depends(require_permission("assets:write"))])
async def update_media_config(payload: dict = Body(...)):
    coll = _db()[MEDIA_CONFIG_COLLECTION]
    now = datetime.utcnow()
    current = await coll.find_one({"key": MEDIA_CONFIG_KEY})
    if not current:
        current = _build_default_doc(now)
        res = await coll.insert_one(current)
        current["_id"] = res.inserted_id

    next_doc = {
        "custom_tags": payload.get("custom_tags", current.get("custom_tags", [])),
        "source_tag_prefix": payload.get("source_tag_prefix", current.get("source_tag_prefix", "source")),
        "upload_variants": payload.get("upload_variants", current.get("upload_variants", DEFAULT_CONFIG["upload_variants"])),
        "metadata_mappings": payload.get(
            "metadata_mappings", current.get("metadata_mappings", DEFAULT_CONFIG["metadata_mappings"])
        ),
        "program_tagging": payload.get(
            "program_tagging", current.get("program_tagging", DEFAULT_CONFIG["program_tagging"])
        ),
        "cropping_tags": payload.get("cropping_tags", current.get("cropping_tags", DEFAULT_CONFIG["cropping_tags"])),
        "fallback_images": payload.get("fallback_images", current.get("fallback_images", DEFAULT_CONFIG["fallback_images"])),
    }
    normalized = _normalize_config(next_doc)

    doc = await coll.find_one_and_update(
        {"key": MEDIA_CONFIG_KEY},
        {
            "$set": {
                "custom_tags": normalized["custom_tags"],
                "source_tag_prefix": normalized["source_tag_prefix"],
                "upload_variants": normalized["upload_variants"],
                "metadata_mappings": normalized["metadata_mappings"],
                "program_tagging": normalized["program_tagging"],
                "cropping_tags": normalized["cropping_tags"],
                "fallback_images": normalized["fallback_images"],
                "updated_at": now,
            },
            "$unset": {"source_tags": ""},
        },
        return_document=ReturnDocument.AFTER,
    )
    _invalidate_public_media_fallback_cache()

    return {
        "id": str(doc["_id"]),
        "custom_tags": normalized["custom_tags"],
        "source_tag_prefix": normalized["source_tag_prefix"],
        "upload_variants": normalized["upload_variants"],
        "metadata_mappings": normalized["metadata_mappings"],
        "program_tagging": normalized["program_tagging"],
        "cropping_tags": normalized["cropping_tags"],
        "fallback_images": normalized["fallback_images"],
        "updated_at": doc.get("updated_at"),
        "created_at": doc.get("created_at"),
    }
