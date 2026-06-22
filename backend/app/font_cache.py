from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.collection_names import FONT_CACHE_FILES_COLLECTION, FONT_CACHE_VARIANTS_COLLECTION
from app.db import get_client
from app.settings import settings
from app.storage.ftp import FTPStorage
from app.storage.s3 import S3Storage

CANONICAL_FAMILY_VARIANT_WEIGHTS = (
    100,
    200,
    300,
    400,
    500,
    600,
    700,
    800,
    900,
)

GOOGLE_CSS_HOST = "fonts.googleapis.com"
GOOGLE_FILE_HOST = "fonts.gstatic.com"

MAX_FONT_FILE_BYTES = 20 * 1024 * 1024
MAX_UPLOAD_TOTAL_BYTES = 120 * 1024 * 1024
MAX_UPLOAD_FILE_COUNT = 256

URL_PATTERN = re.compile(r"url\((?P<quote>['\"]?)(?P<url>[^)\"']+)(?P=quote)\)")

GENERIC_FONT_FAMILIES = frozenset(
    {
        "serif",
        "sans-serif",
        "monospace",
        "cursive",
        "fantasy",
        "system-ui",
        "ui-serif",
        "ui-sans-serif",
        "ui-monospace",
        "ui-rounded",
        "emoji",
        "math",
        "fangsong",
        "inherit",
        "initial",
        "revert",
        "revert-layer",
        "unset",
    }
)

COMMON_LOCAL_FONT_FAMILIES = frozenset(
    {
        "-apple-system",
        "blinkmacsystemfont",
        "segoe ui",
        "arial",
        "helvetica",
        "helvetica neue",
        "times new roman",
        "georgia",
        "courier new",
        "menlo",
        "monaco",
        "consolas",
        "tahoma",
        "verdana",
    }
)

ALLOWED_FONT_EXTENSIONS = {"woff2", "woff", "ttf", "otf"}
ALLOWED_FONT_CONTENT_TYPES = {
    "font/woff2",
    "application/font-woff2",
    "font/woff",
    "application/font-woff",
    "application/x-font-woff",
    "font/ttf",
    "application/font-sfnt",
    "font/otf",
    "application/x-font-ttf",
    "application/x-font-otf",
    "application/octet-stream",
}

_inflight_variant_tasks: dict[str, asyncio.Task] = {}


@dataclass(frozen=True)
class FontVariantRequest:
    family: str
    weights: tuple[int, ...]


@dataclass(frozen=True)
class BrowserUploadedFontFile:
    source_url: str
    filename: str
    content_type: str
    data: bytes


def _db():
    return get_client()[settings.mongo_db]


def _get_storage():
    if settings.storage_backend == "ftp":
        return FTPStorage()
    return S3Storage()


def _split_font_family_list(font_value: str) -> list[str]:
    source = str(font_value or "").strip()
    if not source:
        return []
    parts: list[str] = []
    current = ""
    quote = None
    for ch in source:
        if quote:
            if ch == quote:
                quote = None
            current += ch
            continue
        if ch == '"' or ch == "'":
            quote = ch
            current += ch
            continue
        if ch == ",":
            token = current.strip()
            if token:
                parts.append(token)
            current = ""
            continue
        current += ch
    tail = current.strip()
    if tail:
        parts.append(tail)
    return parts


def _unwrap_quoted_font_family(token: str) -> str:
    value = str(token or "").strip()
    if len(value) < 2:
        return value
    first = value[0]
    last = value[-1]
    if (first == '"' or first == "'") and last == first:
        return value[1:-1].strip()
    return value


def _extract_primary_family_name(font_value: str) -> str:
    first_token = _split_font_family_list(font_value)[:1]
    if not first_token:
        return ""
    return _unwrap_quoted_font_family(first_token[0])


def _normalize_family_name(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalize_family_probe_input(family_name: str) -> str:
    raw = _normalize_family_name(str(family_name or ""))
    if not raw:
        return ""
    primary = _extract_primary_family_name(raw) or raw
    primary = _normalize_family_name(_unwrap_quoted_font_family(primary))
    if ":" in primary:
        primary = primary.split(":", 1)[0].strip()
    return _normalize_family_name(primary)


def _should_cache_family(family_name: str) -> bool:
    normalized = _normalize_family_name(family_name).lower()
    if not normalized:
        return False
    if normalized in GENERIC_FONT_FAMILIES:
        return False
    if normalized in COMMON_LOCAL_FONT_FAMILIES:
        return False
    if normalized.startswith("ui-"):
        return False
    if "var(" in normalized:
        return False
    if "--" in normalized:
        return False
    return True


def _is_local_candidate_family(family_name: str) -> bool:
    normalized = _normalize_family_name(family_name).lower()
    if not normalized:
        return False
    if normalized in GENERIC_FONT_FAMILIES:
        return True
    if normalized in COMMON_LOCAL_FONT_FAMILIES:
        return True
    if normalized.startswith("ui-"):
        return True
    return False


def _family_slug(family_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _normalize_family_name(family_name).lower()).strip("-")
    return slug or "custom"


def _build_variant_key(family_name: str, weights: tuple[int, ...]) -> str:
    payload = f"{_normalize_family_name(family_name).lower()}|{','.join(str(w) for w in weights)}"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    return f"{_family_slug(family_name)}-{digest[:20]}"


def _canonical_variant_key(family_name: str) -> str:
    return _build_variant_key(family_name, CANONICAL_FAMILY_VARIANT_WEIGHTS)


def _normalize_css_source_url(source_url: str) -> str:
    normalized = str(source_url or "").strip()
    if not normalized:
        return ""
    if normalized.startswith("//"):
        return f"https:{normalized}"
    return normalized


def _extract_css_urls(css_text: str) -> list[str]:
    parsed_urls = [
        _normalize_css_source_url(match.group("url").strip())
        for match in URL_PATTERN.finditer(str(css_text or ""))
    ]
    return list(dict.fromkeys([url for url in parsed_urls if url]))


def _normalize_content_type(value: str) -> str:
    return str(value or "").split(";", 1)[0].strip().lower()


def _url_host(url: str) -> str:
    parsed = urlparse(str(url or ""))
    return (parsed.hostname or "").lower().strip()


def _is_https_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    return parsed.scheme.lower() == "https" and bool(parsed.netloc)


def _is_google_css_url(url: str) -> bool:
    return _is_https_url(url) and _url_host(url) == GOOGLE_CSS_HOST


def _is_google_font_file_url(url: str) -> bool:
    return _is_https_url(url) and _url_host(url) == GOOGLE_FILE_HOST


def _guess_extension_from_content_type(content_type: str) -> str | None:
    lowered = _normalize_content_type(content_type)
    if "woff2" in lowered:
        return "woff2"
    if "woff" in lowered:
        return "woff"
    if "truetype" in lowered or lowered.endswith("/ttf"):
        return "ttf"
    if "opentype" in lowered or lowered.endswith("/otf"):
        return "otf"
    return None


def _guess_extension_from_name_or_url(filename: str, source_url: str) -> str | None:
    filename_ext = Path(str(filename or "").strip()).suffix.lower().lstrip(".")
    if filename_ext in ALLOWED_FONT_EXTENSIONS:
        return filename_ext
    path = urlparse(str(source_url or "")).path or ""
    source_ext = Path(path).suffix.lower().lstrip(".")
    if source_ext in ALLOWED_FONT_EXTENSIONS:
        return source_ext
    return None


def _is_valid_signature(ext: str, data: bytes) -> bool:
    prefix = bytes(data[:4])
    if ext == "woff2":
        return prefix == b"wOF2"
    if ext == "woff":
        return prefix == b"wOFF"
    if ext == "ttf":
        return prefix == b"\x00\x01\x00\x00" or prefix == b"true"
    if ext == "otf":
        return prefix == b"OTTO"
    return False


def _detect_font_extension(*, source_url: str, filename: str, content_type: str, data: bytes) -> str:
    ext = _guess_extension_from_content_type(content_type) or _guess_extension_from_name_or_url(
        filename,
        source_url,
    )
    if ext is None:
        # Last resort: infer from signature.
        for candidate in ("woff2", "woff", "ttf", "otf"):
            if _is_valid_signature(candidate, data):
                ext = candidate
                break
    if ext is None or ext not in ALLOWED_FONT_EXTENSIONS:
        raise ValueError("Unsupported font file type. Allowed: woff2, woff, ttf, otf.")
    if not _is_valid_signature(ext, data):
        raise ValueError("Uploaded font file has invalid binary signature.")
    return ext


def _mime_type_for_extension(ext: str, content_type: str) -> str:
    normalized = _normalize_content_type(content_type)
    if normalized and normalized in ALLOWED_FONT_CONTENT_TYPES:
        return normalized
    guessed = mimetypes.guess_type(f"x.{ext}")[0]
    if guessed:
        return guessed
    if ext == "woff2":
        return "font/woff2"
    if ext == "woff":
        return "font/woff"
    if ext == "ttf":
        return "font/ttf"
    if ext == "otf":
        return "font/otf"
    return "application/octet-stream"


async def _storage_key_exists(
    storage: FTPStorage | S3Storage,
    key: str,
    cache: dict[str, bool] | None = None,
) -> bool:
    normalized_key = str(key or "").strip()
    if not normalized_key:
        return False
    if cache is not None and normalized_key in cache:
        return cache[normalized_key]
    try:
        content = await storage.get(key=normalized_key)
        exists = content is not None
    except Exception:
        exists = False
    if cache is not None:
        cache[normalized_key] = exists
    return exists


async def _reuse_existing_cached_file_if_available(
    *,
    existing_doc: dict | None,
    files_coll,
    storage: FTPStorage | S3Storage,
    now: datetime,
    key_exists_cache: dict[str, bool] | None = None,
) -> str | None:
    if not isinstance(existing_doc, dict):
        return None
    key = str(existing_doc.get("key") or "").strip()
    url = str(existing_doc.get("url") or "").strip()
    if not key or not url:
        return None
    if not await _storage_key_exists(storage, key, key_exists_cache):
        return None
    await files_coll.update_one(
        {"_id": existing_doc["_id"]},
        {
            "$set": {
                "last_seen_at": now,
                "updated_at": now,
            }
        },
    )
    return url


async def _variant_assets_exist(
    variant_doc: dict,
    *,
    files_coll,
    storage: FTPStorage | S3Storage,
    key_exists_cache: dict[str, bool] | None = None,
) -> bool:
    stylesheet_key = str(variant_doc.get("stylesheet_key") or "").strip()
    stylesheet_url = str(variant_doc.get("stylesheet_url") or "").strip()
    if not stylesheet_key or not stylesheet_url:
        return False
    if not await _storage_key_exists(storage, stylesheet_key, key_exists_cache):
        return False

    raw_file_urls = variant_doc.get("file_urls")
    if not isinstance(raw_file_urls, list):
        return True

    seen_urls: set[str] = set()
    for raw_url in raw_file_urls:
        file_url = str(raw_url or "").strip()
        if not file_url or file_url in seen_urls:
            continue
        seen_urls.add(file_url)
        file_doc = await files_coll.find_one({"url": file_url})
        if not isinstance(file_doc, dict):
            return False
        file_key = str(file_doc.get("key") or "").strip()
        if not file_key:
            return False
        if not await _storage_key_exists(storage, file_key, key_exists_cache):
            return False
    return True


async def _get_or_create_cached_font_file(
    *,
    source_url: str,
    source_bytes: bytes,
    content_type: str,
    family_name: str,
    variant_key: str,
    sequence: int,
    extension: str,
) -> str:
    db = _db()
    files_coll = db[FONT_CACHE_FILES_COLLECTION]
    source_url_hash = hashlib.sha1(source_url.encode("utf-8")).hexdigest()
    content_sha256 = hashlib.sha256(source_bytes).hexdigest()
    now = datetime.utcnow()
    storage = _get_storage()
    key_exists_cache: dict[str, bool] = {}

    existing_by_content = await files_coll.find_one({"content_sha256": content_sha256})
    reused_by_content = await _reuse_existing_cached_file_if_available(
        existing_doc=existing_by_content,
        files_coll=files_coll,
        storage=storage,
        now=now,
        key_exists_cache=key_exists_cache,
    )
    if reused_by_content:
        return reused_by_content

    existing_by_url = await files_coll.find_one({"source_url_hash": source_url_hash})
    # Only reuse URL-based cache hits when the stored bytes match the current
    # upload. A shared Google URL can change over time, and blindly reusing by
    # URL can keep serving stale or corrupt binaries indefinitely.
    existing_url_content_hash = ""
    if isinstance(existing_by_url, dict):
        existing_url_content_hash = str(existing_by_url.get("content_sha256") or "").strip()
    if existing_url_content_hash and existing_url_content_hash == content_sha256:
        reused_by_url = await _reuse_existing_cached_file_if_available(
            existing_doc=existing_by_url,
            files_coll=files_coll,
            storage=storage,
            now=now,
            key_exists_cache=key_exists_cache,
        )
        if reused_by_url:
            return reused_by_url

    preferred_key = ""
    if isinstance(existing_by_content, dict):
        preferred_key = str(existing_by_content.get("key") or "").strip()
    if not preferred_key and isinstance(existing_by_url, dict):
        preferred_key = str(existing_by_url.get("key") or "").strip()
    key = preferred_key or f"fonts/{_family_slug(family_name)}/{variant_key}/file-{sequence}.{extension}"

    stored = await storage.put(
        data=source_bytes,
        key=key,
        content_type=_mime_type_for_extension(extension, content_type),
        filename=f"{_family_slug(family_name)}-{sequence}.{extension}",
    )

    doc = {
        "source_url": source_url,
        "source_url_hash": source_url_hash,
        "content_sha256": content_sha256,
        "key": stored.key,
        "url": stored.url,
        "content_type": stored.content_type,
        "size": stored.size,
        "updated_at": now,
        "last_seen_at": now,
    }
    await files_coll.update_one(
        {"source_url_hash": source_url_hash},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return stored.url


def _queue_browser_upload_task(
    *,
    variant_key: str,
    family_name: str,
    source_css_url: str,
    css_text: str,
    css_source_urls: list[str],
    uploaded_files_by_source: dict[str, BrowserUploadedFontFile],
) -> None:
    running = _inflight_variant_tasks.get(variant_key)
    if running and not running.done():
        return

    loop = asyncio.get_running_loop()
    task = loop.create_task(
        _process_browser_upload_variant(
            variant_key=variant_key,
            family_name=family_name,
            source_css_url=source_css_url,
            css_text=css_text,
            css_source_urls=css_source_urls,
            uploaded_files_by_source=uploaded_files_by_source,
        )
    )
    _inflight_variant_tasks[variant_key] = task

    def _cleanup(done_task: asyncio.Task) -> None:
        current = _inflight_variant_tasks.get(variant_key)
        if current is done_task:
            _inflight_variant_tasks.pop(variant_key, None)

    task.add_done_callback(_cleanup)


async def _process_browser_upload_variant(
    *,
    variant_key: str,
    family_name: str,
    source_css_url: str,
    css_text: str,
    css_source_urls: list[str],
    uploaded_files_by_source: dict[str, BrowserUploadedFontFile],
) -> None:
    db = _db()
    variants_coll = db[FONT_CACHE_VARIANTS_COLLECTION]

    started_at = datetime.utcnow()
    await variants_coll.update_one(
        {"variant_key": variant_key},
        {
            "$set": {
                "family": family_name,
                "family_normalized": family_name.lower(),
                "weights": list(CANONICAL_FAMILY_VARIANT_WEIGHTS),
                "status": "pending",
                "google_css_url": source_css_url,
                "updated_at": started_at,
                "last_attempted_at": started_at,
                "error_message": None,
            },
            "$setOnInsert": {"created_at": started_at},
        },
        upsert=True,
    )

    try:
        replacement_by_source: dict[str, str] = {}
        for index, source_url in enumerate(css_source_urls, start=1):
            uploaded = uploaded_files_by_source.get(source_url)
            if not uploaded:
                raise RuntimeError(f"Missing uploaded file for CSS URL: {source_url}")
            extension = _detect_font_extension(
                source_url=uploaded.source_url,
                filename=uploaded.filename,
                content_type=uploaded.content_type,
                data=uploaded.data,
            )
            local_url = await _get_or_create_cached_font_file(
                source_url=uploaded.source_url,
                source_bytes=uploaded.data,
                content_type=uploaded.content_type,
                family_name=family_name,
                variant_key=variant_key,
                sequence=index,
                extension=extension,
            )
            replacement_by_source[source_url] = local_url

        rewritten_css = URL_PATTERN.sub(
            lambda match: (
                f"url('{replacement_by_source.get(_normalize_css_source_url(match.group('url').strip()), match.group('url').strip())}')"
            ),
            css_text,
        )

        css_key = f"fonts/{_family_slug(family_name)}/{variant_key}/stylesheet.css"
        storage = _get_storage()
        stored_css = await storage.put(
            data=rewritten_css.encode("utf-8"),
            key=css_key,
            content_type="text/css",
            filename=f"{_family_slug(family_name)}.css",
        )

        ready_at = datetime.utcnow()
        await variants_coll.update_one(
            {"variant_key": variant_key},
            {
                "$set": {
                    "status": "ready",
                    "stylesheet_key": stored_css.key,
                    "stylesheet_url": stored_css.url,
                    "file_urls": list(dict.fromkeys(replacement_by_source.values())),
                    "google_css_url": source_css_url,
                    "updated_at": ready_at,
                    "last_ready_at": ready_at,
                    "error_message": None,
                }
            },
            upsert=True,
        )
    except asyncio.CancelledError:
        failed_at = datetime.utcnow()
        await variants_coll.update_one(
            {"variant_key": variant_key},
            {
                "$set": {
                    "status": "error",
                    "updated_at": failed_at,
                    "error_message": "Caching job was cancelled before completion.",
                }
            },
            upsert=True,
        )
        raise
    except Exception as exc:
        failed_at = datetime.utcnow()
        await variants_coll.update_one(
            {"variant_key": variant_key},
            {
                "$set": {
                    "status": "error",
                    "updated_at": failed_at,
                    "error_message": str(exc),
                }
            },
            upsert=True,
        )


def _dedupe_families(families: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in families:
        normalized = _normalize_family_probe_input(raw)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def extract_font_variant_requests_from_design(design_settings: dict | None) -> list[FontVariantRequest]:
    if not isinstance(design_settings, dict):
        return []

    header_family = _extract_primary_family_name(
        str(design_settings.get("header_font_family") or "")
    )
    body_family = _extract_primary_family_name(
        str(design_settings.get("body_font_family") or "")
    )

    families = _dedupe_families([header_family, body_family])
    requests: list[FontVariantRequest] = []
    for family in families:
        if not _should_cache_family(family):
            continue
        requests.append(
            FontVariantRequest(
                family=family,
                weights=CANONICAL_FAMILY_VARIANT_WEIGHTS,
            )
        )
    return requests


def extract_font_variant_requests_from_families_payload(
    families_payload: Any,
) -> list[FontVariantRequest]:
    if not isinstance(families_payload, list):
        return []

    families: list[str] = []
    for item in families_payload:
        if isinstance(item, str):
            families.append(item)
            continue
        if not isinstance(item, dict):
            continue
        raw_family = (
            item.get("family")
            or item.get("label")
            or item.get("value")
            or ""
        )
        if raw_family:
            families.append(str(raw_family))

    requests: list[FontVariantRequest] = []
    for family in _dedupe_families(families):
        if not _should_cache_family(family):
            continue
        requests.append(
            FontVariantRequest(
                family=family,
                weights=CANONICAL_FAMILY_VARIANT_WEIGHTS,
            )
        )
    return requests


async def get_font_family_cache_status(family_name: str) -> dict[str, Any]:
    normalized_family = _normalize_family_probe_input(family_name)
    if not normalized_family:
        return {
            "family": "",
            "cacheable": False,
            "local_candidate": False,
            "cache_status": "invalid",
            "stylesheet_url": "",
            "can_cache_via_browser": False,
            "message": "Font family is empty.",
            "weights": list(CANONICAL_FAMILY_VARIANT_WEIGHTS),
        }

    cacheable = _should_cache_family(normalized_family)
    local_candidate = _is_local_candidate_family(normalized_family)
    if not cacheable:
        message = (
            "This font family is treated as local/system and is not cached."
            if local_candidate
            else "This font family is not eligible for caching."
        )
        return {
            "family": normalized_family,
            "cacheable": False,
            "local_candidate": local_candidate,
            "cache_status": "not_cacheable",
            "stylesheet_url": "",
            "can_cache_via_browser": False,
            "message": message,
            "weights": list(CANONICAL_FAMILY_VARIANT_WEIGHTS),
        }

    db = _db()
    variants_coll = db[FONT_CACHE_VARIANTS_COLLECTION]
    files_coll = db[FONT_CACHE_FILES_COLLECTION]
    storage = _get_storage()
    key_exists_cache: dict[str, bool] = {}

    variant_key = _canonical_variant_key(normalized_family)
    variant_doc = await variants_coll.find_one({"variant_key": variant_key})

    status = str((variant_doc or {}).get("status") or "").strip().lower()
    stylesheet_url = str((variant_doc or {}).get("stylesheet_url") or "").strip()

    cache_status = "missing"
    can_cache_via_browser = True
    message = "Font is not cached yet. Click Cache via browser."

    if status == "ready" and stylesheet_url:
        assets_ok = await _variant_assets_exist(
            variant_doc or {},
            files_coll=files_coll,
            storage=storage,
            key_exists_cache=key_exists_cache,
        )
        if assets_ok:
            cache_status = "ready"
            can_cache_via_browser = False
            message = "Font is cached and ready."
        else:
            cache_status = "missing"
            message = "Cached font assets are missing. Re-run Cache via browser."
    elif status == "pending":
        running_task = _inflight_variant_tasks.get(variant_key)
        if running_task and not running_task.done():
            cache_status = "pending"
            can_cache_via_browser = False
            message = "Font cache upload is queued and processing."
        else:
            cache_status = "error"
            can_cache_via_browser = True
            message = (
                "Previous cache upload did not finish (stale pending state). "
                "Please click Cache via browser again."
            )
    elif status == "error":
        cache_status = "error"
        can_cache_via_browser = True
        error_message = str((variant_doc or {}).get("error_message") or "").strip()
        message = error_message or "Last cache upload failed. Please retry Cache via browser."

    return {
        "family": normalized_family,
        "cacheable": True,
        "local_candidate": local_candidate,
        "cache_status": cache_status,
        "stylesheet_url": stylesheet_url if cache_status == "ready" else "",
        "can_cache_via_browser": can_cache_via_browser,
        "message": message,
        "weights": list(CANONICAL_FAMILY_VARIANT_WEIGHTS),
    }


async def queue_font_family_cache_via_browser(
    *,
    family_name: str,
    source_css_url: str,
    css_text: str,
    source_urls: list[str],
    files: list[BrowserUploadedFontFile],
) -> dict[str, Any]:
    normalized_family = _normalize_family_probe_input(family_name)
    if not normalized_family:
        raise ValueError("Font family is empty.")
    if not _should_cache_family(normalized_family):
        raise ValueError("This font family is not eligible for caching.")

    normalized_css_url = _normalize_css_source_url(source_css_url)
    if not normalized_css_url:
        raise ValueError("source_css_url is required.")
    if not _is_google_css_url(normalized_css_url):
        raise ValueError("source_css_url must use https://fonts.googleapis.com.")

    normalized_css_text = str(css_text or "")
    if not normalized_css_text.strip():
        raise ValueError("css_text is empty.")

    css_urls = _extract_css_urls(normalized_css_text)
    if not css_urls:
        raise ValueError("No font file URLs found in css_text.")
    if len(css_urls) > MAX_UPLOAD_FILE_COUNT:
        raise ValueError(
            f"css_text references too many font files ({len(css_urls)}). "
            f"Max allowed is {MAX_UPLOAD_FILE_COUNT}."
        )

    for css_url in css_urls:
        if not _is_google_font_file_url(css_url):
            raise ValueError(
                "css_text may only reference https://fonts.gstatic.com font URLs."
            )

    if len(source_urls) != len(files):
        raise ValueError("source_urls and files must have the same length.")
    if not files:
        raise ValueError("At least one uploaded font file is required.")
    if len(files) > MAX_UPLOAD_FILE_COUNT:
        raise ValueError(f"Too many files uploaded ({len(files)}). Max allowed is {MAX_UPLOAD_FILE_COUNT}.")

    css_url_set = set(css_urls)
    uploaded_files_by_source: dict[str, BrowserUploadedFontFile] = {}
    total_upload_bytes = 0

    for index, source_url_raw in enumerate(source_urls):
        normalized_source_url = _normalize_css_source_url(source_url_raw)
        if not normalized_source_url:
            raise ValueError(f"source_urls[{index}] is empty.")
        if normalized_source_url in uploaded_files_by_source:
            raise ValueError(f"Duplicate source URL in upload: {normalized_source_url}")
        if normalized_source_url not in css_url_set:
            raise ValueError(
                f"Uploaded source URL is not referenced in css_text: {normalized_source_url}"
            )
        if not _is_google_font_file_url(normalized_source_url):
            raise ValueError("source_urls must use https://fonts.gstatic.com.")

        uploaded = files[index]
        file_bytes = bytes(uploaded.data or b"")
        if not file_bytes:
            raise ValueError(f"Uploaded file is empty for source URL: {normalized_source_url}")
        if len(file_bytes) > MAX_FONT_FILE_BYTES:
            raise ValueError(
                f"Uploaded file exceeds 20MB limit for source URL: {normalized_source_url}"
            )
        total_upload_bytes += len(file_bytes)
        if total_upload_bytes > MAX_UPLOAD_TOTAL_BYTES:
            raise ValueError("Total upload payload exceeds 120MB.")

        normalized_content_type = _normalize_content_type(uploaded.content_type)
        if normalized_content_type and normalized_content_type not in ALLOWED_FONT_CONTENT_TYPES:
            raise ValueError(
                f"Unsupported content type '{normalized_content_type}' for source URL: {normalized_source_url}"
            )

        _detect_font_extension(
            source_url=normalized_source_url,
            filename=uploaded.filename,
            content_type=normalized_content_type,
            data=file_bytes,
        )

        uploaded_files_by_source[normalized_source_url] = BrowserUploadedFontFile(
            source_url=normalized_source_url,
            filename=uploaded.filename,
            content_type=normalized_content_type,
            data=file_bytes,
        )

    missing_uploads = [url for url in css_urls if url not in uploaded_files_by_source]
    if missing_uploads:
        preview = ", ".join(missing_uploads[:3])
        suffix = "" if len(missing_uploads) <= 3 else f", +{len(missing_uploads) - 3} more"
        raise ValueError(
            "Every CSS font URL must have an uploaded file. "
            f"Missing: {preview}{suffix}"
        )

    variant_key = _canonical_variant_key(normalized_family)
    db = _db()
    variants_coll = db[FONT_CACHE_VARIANTS_COLLECTION]
    now = datetime.utcnow()

    await variants_coll.update_one(
        {"variant_key": variant_key},
        {
            "$set": {
                "family": normalized_family,
                "family_normalized": normalized_family.lower(),
                "weights": list(CANONICAL_FAMILY_VARIANT_WEIGHTS),
                "status": "pending",
                "google_css_url": normalized_css_url,
                "updated_at": now,
                "last_attempted_at": now,
                "error_message": None,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    _queue_browser_upload_task(
        variant_key=variant_key,
        family_name=normalized_family,
        source_css_url=normalized_css_url,
        css_text=normalized_css_text,
        css_source_urls=css_urls,
        uploaded_files_by_source=uploaded_files_by_source,
    )

    return {
        "family": normalized_family,
        "variant_key": variant_key,
        "cache_status": "pending",
        "queued": True,
        "message": "Font upload accepted and queued for processing.",
    }


async def resolve_font_cache_for_requests(
    requests: list[FontVariantRequest],
    *,
    queue_missing: bool = True,
    force_retry_errors: bool = False,
    resolve_inline: bool = False,
) -> dict[str, Any]:
    # This resolver is intentionally read-only. The flags are accepted for
    # compatibility with old callsites and ignored.
    del queue_missing, force_retry_errors, resolve_inline

    db = _db()
    variants_coll = db[FONT_CACHE_VARIANTS_COLLECTION]
    files_coll = db[FONT_CACHE_FILES_COLLECTION]
    storage = _get_storage()
    key_exists_cache: dict[str, bool] = {}

    stylesheet_urls: list[str] = []
    pending_families: set[str] = set()
    cached_families: set[str] = set()
    unavailable_families: set[str] = set()

    for request in requests:
        family_name = _normalize_family_probe_input(request.family)
        if not family_name or not _should_cache_family(family_name):
            continue

        variant_key = _canonical_variant_key(family_name)
        variant_doc = await variants_coll.find_one({"variant_key": variant_key})
        status = str((variant_doc or {}).get("status") or "").strip().lower()
        stylesheet_url = str((variant_doc or {}).get("stylesheet_url") or "").strip()

        if status == "ready" and stylesheet_url:
            assets_ok = await _variant_assets_exist(
                variant_doc or {},
                files_coll=files_coll,
                storage=storage,
                key_exists_cache=key_exists_cache,
            )
            if assets_ok:
                stylesheet_urls.append(stylesheet_url)
                cached_families.add(family_name)
                continue

        if status == "pending":
            running_task = _inflight_variant_tasks.get(variant_key)
            if running_task and not running_task.done():
                pending_families.add(family_name)
                continue

        unavailable_families.add(family_name)

    return {
        "font_stylesheet_urls": list(dict.fromkeys(stylesheet_urls)),
        "pending_families": sorted(pending_families),
        "cached_families": sorted(cached_families),
        "unavailable_families": sorted(unavailable_families),
    }


async def resolve_font_cache_for_design(
    design_settings: dict | None,
    *,
    queue_missing: bool = True,
    force_retry_errors: bool = False,
    resolve_inline: bool = False,
) -> dict[str, Any]:
    requests = extract_font_variant_requests_from_design(design_settings)
    return await resolve_font_cache_for_requests(
        requests,
        queue_missing=queue_missing,
        force_retry_errors=force_retry_errors,
        resolve_inline=resolve_inline,
    )


async def resolve_font_cache_for_families_payload(
    families_payload: Any,
    *,
    queue_missing: bool = True,
    force_retry_errors: bool = False,
    resolve_inline: bool = False,
) -> dict[str, Any]:
    requests = extract_font_variant_requests_from_families_payload(families_payload)
    return await resolve_font_cache_for_requests(
        requests,
        queue_missing=queue_missing,
        force_retry_errors=force_retry_errors,
        resolve_inline=resolve_inline,
    )
