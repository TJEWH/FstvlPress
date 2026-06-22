from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from datetime import datetime
from typing import Any

from app.collection_names import (
    ASSETS_COLLECTION,
    BLOG_SHARED_COLLECTION,
    DESIGN_CONFIG_COLLECTION,
    DESIGN_EDITOR_CONFIG_COLLECTION,
    HEADERS_COLLECTION,
    MEDIA_CONFIG_COLLECTION,
    PAGES_COLLECTION,
    PROGRAM_SHARED_COLLECTION,
    REVISIONS_COLLECTION,
    SECTIONS_COLLECTION,
    SITEMAP_CONFIG_COLLECTION,
    TEMPLATE_CONTAINERS_COLLECTION,
    TEMPLATE_PAGES_COLLECTION,
    TEMPLATE_SECTIONS_COLLECTION,
)
from app.media_responsive import normalize_media_variant_entries


LEGACY_ASSET_FIELDS = ("key_half", "key_thumb", "url_half", "url_thumb")
LEGACY_CONTENT_SUFFIXES = {
    "_url_half": ("half", 1024),
    "_url_thumb": ("thumb", 150),
}
LEGACY_CONTENT_EXACT_KEYS = {
    "url_half": ("half", 1024, "responsive_variants"),
    "url_thumb": ("thumb", 150, "responsive_variants"),
}
CONTENT_COLLECTIONS = (
    SECTIONS_COLLECTION,
    TEMPLATE_SECTIONS_COLLECTION,
    TEMPLATE_CONTAINERS_COLLECTION,
    TEMPLATE_PAGES_COLLECTION,
    PAGES_COLLECTION,
    HEADERS_COLLECTION,
    BLOG_SHARED_COLLECTION,
    PROGRAM_SHARED_COLLECTION,
    DESIGN_CONFIG_COLLECTION,
    DESIGN_EDITOR_CONFIG_COLLECTION,
    SITEMAP_CONFIG_COLLECTION,
    REVISIONS_COLLECTION,
)


def _coerce_width(raw: Any, fallback: int) -> int:
    try:
        width = int(raw)
    except Exception:
        width = fallback
    return width if width > 0 else fallback


def _coerce_bool(raw: Any, fallback: bool) -> bool:
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
    return fallback


def _variant_identity(entry: dict[str, Any]) -> tuple[str, str]:
    return (
        str(entry.get("url") or "").strip(),
        str(entry.get("key") or "").strip(),
    )


def _asset_variant_exists(variants: dict[str, Any], entry: dict[str, Any]) -> bool:
    next_url, next_key = _variant_identity(entry)
    for existing in variants.values():
        if not isinstance(existing, dict):
            continue
        existing_url, existing_key = _variant_identity(existing)
        if next_url and existing_url == next_url:
            return True
        if next_key and existing_key == next_key:
            return True
    return False


def _insert_asset_variant(
    variants: dict[str, Any],
    name: str,
    entry: dict[str, Any],
) -> None:
    if _asset_variant_exists(variants, entry):
        return
    target_name = name
    suffix = 2
    while target_name in variants:
        target_name = f"{name}_{suffix}"
        suffix += 1
    variants[target_name] = entry


def migrate_asset_document(doc: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    migrated = deepcopy(doc)
    variants = migrated.get("variants")
    if not isinstance(variants, dict):
        variants = {}
    else:
        variants = deepcopy(variants)

    half_url = str(migrated.get("url_half") or "").strip()
    half_key = str(migrated.get("key_half") or "").strip()
    if half_url or half_key:
        entry: dict[str, Any] = {"name": "half", "width": 1024}
        if half_url:
            entry["url"] = half_url
        if half_key:
            entry["key"] = half_key
        _insert_asset_variant(variants, "half", entry)

    thumb_url = str(migrated.get("url_thumb") or "").strip()
    thumb_key = str(migrated.get("key_thumb") or "").strip()
    if thumb_url or thumb_key:
        entry = {"name": "thumb", "width": 150}
        if thumb_url:
            entry["url"] = thumb_url
        if thumb_key:
            entry["key"] = thumb_key
        _insert_asset_variant(variants, "thumb", entry)

    changed = variants != migrated.get("variants") or any(field in migrated for field in LEGACY_ASSET_FIELDS)
    migrated["variants"] = variants
    for field in LEGACY_ASSET_FIELDS:
        migrated.pop(field, None)
    return migrated, changed


def _content_variant_exists(variants: list[dict[str, Any]], url: str) -> bool:
    normalized_url = str(url or "").strip()
    return bool(normalized_url) and any(str(entry.get("url") or "").strip() == normalized_url for entry in variants)


def _append_content_variant(
    target: dict[str, Any],
    variants_key: str,
    *,
    name: str,
    url: str,
    width: int,
) -> None:
    normalized_url = str(url or "").strip()
    if not normalized_url:
        return
    variants = normalize_media_variant_entries(target.get(variants_key))
    if not _content_variant_exists(variants, normalized_url):
        variants.append({"name": name, "url": normalized_url, "width": width})
    variants.sort(key=lambda entry: int(entry.get("width") or 0))
    target[variants_key] = variants


def migrate_content_media_fields(value: Any) -> tuple[Any, bool]:
    if isinstance(value, list):
        changed = False
        next_list = []
        for item in value:
            migrated_item, item_changed = migrate_content_media_fields(item)
            changed = changed or item_changed
            next_list.append(migrated_item)
        return next_list, changed

    if not isinstance(value, dict):
        return value, False

    target = deepcopy(value)
    changed = False

    for key in list(target.keys()):
        exact = LEGACY_CONTENT_EXACT_KEYS.get(key)
        if exact:
            name, width, variants_key = exact
            _append_content_variant(target, variants_key, name=name, url=target.get(key), width=width)
            target.pop(key, None)
            changed = True
            continue

        for suffix, (name, width) in LEGACY_CONTENT_SUFFIXES.items():
            if not key.endswith(suffix):
                continue
            prefix = key[: -len(suffix)]
            variants_key = f"{prefix}_responsive_variants" if prefix else "responsive_variants"
            _append_content_variant(target, variants_key, name=name, url=target.get(key), width=width)
            target.pop(key, None)
            changed = True
            break

    for key, item in list(target.items()):
        if isinstance(item, (dict, list)):
            migrated_item, item_changed = migrate_content_media_fields(item)
            if item_changed:
                target[key] = migrated_item
                changed = True

    return target, changed


def migrate_media_config_document(doc: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    migrated = deepcopy(doc)
    upload_variants = migrated.get("upload_variants")
    if not isinstance(upload_variants, dict):
        return migrated, False

    changed = False
    custom = upload_variants.get("custom")
    raw_custom_variants = [dict(entry) for entry in custom if isinstance(entry, dict)] if isinstance(custom, list) else []
    custom_variants = []
    custom_thumb = None
    for entry in raw_custom_variants:
        variant_id = str(entry.get("id") or "").strip().lower()
        if variant_id == "thumb":
            custom_thumb = custom_thumb or entry
            continue
        if variant_id == "small":
            continue
        custom_variants.append(entry)

    existing_thumb = upload_variants.get("thumb") if isinstance(upload_variants.get("thumb"), dict) else {}
    thumb_source = existing_thumb or custom_thumb or {}
    thumb_width_raw = (
        upload_variants.get("thumb_width")
        if "thumb_width" in upload_variants
        else thumb_source.get("width")
    )
    upload_variants["thumb"] = {
        "enabled": _coerce_bool(thumb_source.get("enabled"), True),
        "width": _coerce_width(thumb_width_raw, 150),
    }

    if (
        "thumb_width" in upload_variants
        or "small" in upload_variants
        or upload_variants.get("custom") != custom_variants
        or existing_thumb != upload_variants["thumb"]
    ):
        changed = True

    upload_variants["custom"] = custom_variants
    upload_variants.pop("thumb_width", None)
    upload_variants.pop("small", None)
    migrated["upload_variants"] = upload_variants
    return migrated, changed


async def migrate_media_variant_structure(db=None, *, dry_run: bool = False) -> dict[str, int]:
    if db is None:
        from app.db import get_client
        from app.settings import settings

        database = get_client()[settings.mongo_db]
    else:
        database = db
    summary = {
        "assets_checked": 0,
        "assets_updated": 0,
        "configs_checked": 0,
        "configs_updated": 0,
        "documents_checked": 0,
        "documents_updated": 0,
    }

    assets = database[ASSETS_COLLECTION]
    async for doc in assets.find({}):
        summary["assets_checked"] += 1
        migrated, changed = migrate_asset_document(doc)
        if not changed:
            continue
        summary["assets_updated"] += 1
        if not dry_run:
            migrated["updated_at"] = datetime.utcnow()
            await assets.replace_one({"_id": doc["_id"]}, migrated)

    media_config = database[MEDIA_CONFIG_COLLECTION]
    async for doc in media_config.find({}):
        summary["configs_checked"] += 1
        migrated, changed = migrate_media_config_document(doc)
        if not changed:
            continue
        summary["configs_updated"] += 1
        if not dry_run:
            migrated["updated_at"] = datetime.utcnow()
            await media_config.replace_one({"_id": doc["_id"]}, migrated)

    for collection_name in CONTENT_COLLECTIONS:
        collection = database[collection_name]
        async for doc in collection.find({}):
            summary["documents_checked"] += 1
            migrated, changed = migrate_content_media_fields(doc)
            if not changed:
                continue
            summary["documents_updated"] += 1
            if not dry_run:
                if isinstance(migrated, dict):
                    migrated["updated_at"] = datetime.utcnow()
                await collection.replace_one({"_id": doc["_id"]}, migrated)

    return summary


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Migrate media crop URLs into responsive variant arrays.")
    parser.add_argument("--dry-run", action="store_true", help="Count changes without writing to MongoDB.")
    args = parser.parse_args()
    summary = await migrate_media_variant_structure(dry_run=args.dry_run)
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    asyncio.run(_main())
