from __future__ import annotations

import re
from typing import Any, Iterable, Mapping


RASTER_URL_KEY_HINTS = (
    "image",
    "logo",
    "thumb",
    "thumbnail",
    "cover",
    "poster",
    "banner",
    "media",
)

RASTER_URL_KEY_EXCLUDE = {
    "link_url",
    "item_url",
    "video_url",
    "fetch_url",
    "source_url",
    "redirect_to",
    "image_click_url",
}

LEGACY_RESPONSIVE_VARIANT_NAMES = {"small"}
LEGACY_SMALL_VARIANT_URL_PATTERN = re.compile(
    r"_small\.(?:avif|gif|jpe?g|png|webp)$",
    re.IGNORECASE,
)


def _is_raster_url_key(raw_key: str) -> bool:
    key = str(raw_key or "").strip().lower()
    if not key.endswith("_url"):
        return False
    if key in RASTER_URL_KEY_EXCLUDE:
        return False
    return any(hint in key for hint in RASTER_URL_KEY_HINTS)


def _is_legacy_responsive_variant(name: str, url: str) -> bool:
    normalized_name = str(name or "").strip().lower()
    if normalized_name in LEGACY_RESPONSIVE_VARIANT_NAMES:
        return True
    path = str(url or "").strip().split("#", 1)[0].split("?", 1)[0]
    return bool(LEGACY_SMALL_VARIANT_URL_PATTERN.search(path))


def normalize_variant_entry(
    raw_entry: Any,
    fallback_name: str = "",
) -> dict[str, Any] | None:
    if isinstance(raw_entry, str):
        return None
    if not isinstance(raw_entry, dict):
        return None

    url = str(raw_entry.get("url") or raw_entry.get("href") or raw_entry.get("src") or "").strip()
    if not url:
        return None

    width_raw = raw_entry.get("width")
    try:
        width = int(width_raw)
    except Exception:
        width = 0
    if width <= 0:
        return None

    name = str(raw_entry.get("name") or raw_entry.get("variant") or fallback_name or "").strip()
    if _is_legacy_responsive_variant(name, url):
        return None

    entry: dict[str, Any] = {
        "url": url,
        "width": width,
    }
    if name:
        entry["name"] = name

    height_raw = raw_entry.get("height")
    try:
        height = int(height_raw) if height_raw is not None else None
    except Exception:
        height = None
    if isinstance(height, int) and height > 0:
        entry["height"] = height
    return entry


def normalize_media_variant_entries(raw_variants: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    if isinstance(raw_variants, list):
        for raw_entry in raw_variants:
            entry = normalize_variant_entry(raw_entry)
            if entry:
                normalized.append(entry)
    elif isinstance(raw_variants, dict):
        if any(field in raw_variants for field in ("url", "href", "src")):
            entry = normalize_variant_entry(raw_variants)
            if entry:
                normalized.append(entry)
        else:
            for variant_name, raw_entry in raw_variants.items():
                entry = normalize_variant_entry(raw_entry, fallback_name=str(variant_name or "").strip())
                if entry:
                    normalized.append(entry)

    normalized.sort(key=lambda item: int(item.get("width") or 0))
    return normalized


def build_asset_responsive_variants(variants_doc: Any) -> list[dict[str, Any]]:
    return normalize_media_variant_entries(variants_doc)


def merge_media_variant_entries(
    existing_variants: list[dict[str, Any]],
    imported_variants: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}

    for entry in [*existing_variants, *imported_variants]:
        url = str(entry.get("url") or "").strip()
        if not url:
            continue
        current = by_url.get(url)
        if current is None:
            by_url[url] = entry
            continue
        try:
            current_width = int(current.get("width") or 0)
        except Exception:
            current_width = 0
        try:
            next_width = int(entry.get("width") or 0)
        except Exception:
            next_width = 0
        if next_width > current_width:
            by_url[url] = entry

    merged = list(by_url.values())
    merged.sort(key=lambda item: int(item.get("width") or 0))
    return merged


def _extract_primary_author_from_asset_doc(asset_doc: Any) -> str:
    if not isinstance(asset_doc, dict):
        return ""
    metadata = asset_doc.get("metadata")
    if isinstance(metadata, dict):
        raw_authors = metadata.get("authors")
        if isinstance(raw_authors, list):
            for entry in raw_authors:
                candidate = str(entry or "").strip()
                if candidate:
                    return candidate
    raw_tags = asset_doc.get("tags")
    if isinstance(raw_tags, list):
        for raw_tag in raw_tags:
            tag = str(raw_tag or "").strip()
            if not tag.lower().startswith("author::"):
                continue
            slug = tag.split("::", 1)[1] if "::" in tag else ""
            slug = str(slug or "").strip()
            if not slug or slug.lower() == "missing":
                continue
            fallback = " ".join(part for part in slug.replace("_", "-").split("-") if part).strip()
            if fallback:
                return fallback
    return ""


def _iter_raster_targets(payload: Any):
    if isinstance(payload, dict):
        for key, value in list(payload.items()):
            if isinstance(value, str) and _is_raster_url_key(key):
                image_url = str(value or "").strip()
                if image_url:
                    yield payload, str(key), image_url
            if isinstance(value, (dict, list)):
                yield from _iter_raster_targets(value)
        return

    if isinstance(payload, list):
        for item in payload:
            yield from _iter_raster_targets(item)


def collect_raster_image_urls_from_payload(payload: Any) -> set[str]:
    urls: set[str] = set()
    for _target, _key, image_url in _iter_raster_targets(payload):
        urls.add(image_url)
    return urls


def enrich_raster_payload_with_asset_docs(
    payload: Any,
    asset_docs_by_url: Mapping[str, dict[str, Any]],
) -> None:
    if not payload or not isinstance(asset_docs_by_url, Mapping):
        return

    for target, key, image_url in _iter_raster_targets(payload):
        asset_doc = asset_docs_by_url.get(image_url)
        if not isinstance(asset_doc, dict):
            continue

        key_lower = key.strip().lower()
        prefix = key_lower[:-4] if key_lower.endswith("_url") else key_lower
        if not prefix:
            continue

        variants_key = f"{prefix}_responsive_variants"
        author_key = f"{prefix}_author"

        existing_variants = normalize_media_variant_entries(target.get(variants_key))
        if prefix == "image":
            existing_variants = merge_media_variant_entries(
                existing_variants,
                normalize_media_variant_entries(target.get("responsive_variants")),
            )

        imported_variants = build_asset_responsive_variants(asset_doc.get("variants"))
        merged_variants = merge_media_variant_entries(existing_variants, imported_variants)
        if merged_variants:
            target[variants_key] = merged_variants
            if prefix == "image" and (
                "responsive_variants" in target
                or "link_url" in target
                or "icon" in target
            ):
                target["responsive_variants"] = merged_variants

        author = _extract_primary_author_from_asset_doc(asset_doc)
        if author:
            target[author_key] = author


async def fetch_asset_docs_by_urls(
    db,
    image_urls: Iterable[str],
) -> dict[str, dict[str, Any]]:
    urls = sorted({str(url or "").strip() for url in image_urls if str(url or "").strip()})
    if not urls:
        return {}

    assets_coll = db["assets"]
    asset_docs_by_url: dict[str, dict[str, Any]] = {}
    async for asset_doc in assets_coll.find(
        {"url": {"$in": urls}},
        {"url": 1, "variants": 1, "metadata": 1, "tags": 1},
    ):
        if not isinstance(asset_doc, dict):
            continue
        url = str(asset_doc.get("url") or "").strip()
        if not url:
            continue
        asset_docs_by_url[url] = asset_doc
    return asset_docs_by_url
