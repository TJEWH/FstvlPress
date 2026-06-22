"""Blog items API - shared list used by all blog sections."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from app.db import get_client
from app.deps import get_current_user, require_permission
from app.item_page_jobs import enqueue_blog_item_page_generation
from app.media_responsive import (
    build_asset_responsive_variants,
    merge_media_variant_entries,
    normalize_media_variant_entries,
)
from app.security import KeycloakUser
from app.settings import settings
from app.models.blog import BlogItem, BlogConfig
from app.revisioning import (
    push_blog_shared_content_revisions,
    snapshots_equal,
)
from app.template_sync import (
    cleanup_blog_item_generated_pages,
    get_generated_item_page_template_freshness_map,
)

router = APIRouter(prefix="/blog", tags=["blog"])

CONFIG_ID = "config"
MIGRATION_LOCK_ID = "migration_lock_blog_items_v1"


def _db():
    return get_client()[settings.mongo_db]


def _safe_float(value, default: float) -> float:
    try:
        parsed = float(value)
        if parsed != parsed:  # NaN guard
            return default
        return parsed
    except Exception:
        return default


def _items_coll():
    return _db()["blog_shared"]


def _config_coll():
    return _db()["blog_config"]


def _resolve_media_variants(source: Any) -> list[dict[str, Any]]:
    if not isinstance(source, dict):
        return []
    candidates: list[Any] = [
        source.get("image_responsive_variants"),
        source.get("responsive_variants"),
        source.get("variants"),
    ]
    image_payload = source.get("image")
    if isinstance(image_payload, dict):
        candidates.extend(
            [
                image_payload.get("image_responsive_variants"),
                image_payload.get("responsive_variants"),
                image_payload.get("variants"),
            ]
        )

    merged: list[dict[str, Any]] = []
    for candidate in candidates:
        merged = merge_media_variant_entries(
            merged,
            normalize_media_variant_entries(candidate),
        )
    return merged


def _has_any_media_variant_key(source: Any) -> bool:
    if not isinstance(source, dict):
        return False
    keys = (
        "image_responsive_variants",
        "responsive_variants",
        "variants",
    )
    if any(key in source for key in keys):
        return True
    image_payload = source.get("image")
    if not isinstance(image_payload, dict):
        return False
    return any(key in image_payload for key in keys)


def _first_present_media_value(source: Any, keys: tuple[str, ...]) -> tuple[Any, bool]:
    if not isinstance(source, dict):
        return None, False
    for key in keys:
        if key in source:
            return source.get(key), True
    image_payload = source.get("image")
    if isinstance(image_payload, dict):
        for key in keys:
            if key in image_payload:
                return image_payload.get(key), True
    return None, False


def _extract_primary_author(source: Any) -> str:
    metadata = source.get("metadata") if isinstance(source, dict) else None
    if isinstance(metadata, dict):
        raw_authors = metadata.get("authors")
        if isinstance(raw_authors, list):
            for entry in raw_authors:
                candidate = str(entry or "").strip()
                if candidate:
                    return candidate
    raw_tags = source.get("tags") if isinstance(source, dict) else None
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


async def _enrich_blog_item_docs_with_asset_media(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not docs:
        return docs

    image_urls = sorted(
        {
            str(doc.get("image_url") or "").strip()
            for doc in docs
            if isinstance(doc, dict) and str(doc.get("image_url") or "").strip()
        }
    )
    if not image_urls:
        return docs

    assets_coll = _db()["assets"]
    asset_docs_by_url: dict[str, dict[str, Any]] = {}
    async for asset_doc in assets_coll.find(
        {"url": {"$in": image_urls}},
        {"url": 1, "variants": 1, "metadata": 1, "tags": 1},
    ):
        if not isinstance(asset_doc, dict):
            continue
        asset_url = str(asset_doc.get("url") or "").strip()
        if not asset_url:
            continue
        asset_docs_by_url[asset_url] = asset_doc

    if not asset_docs_by_url:
        return docs

    for doc in docs:
        if not isinstance(doc, dict):
            continue
        image_url = str(doc.get("image_url") or "").strip()
        if not image_url:
            continue
        asset_doc = asset_docs_by_url.get(image_url)
        if not isinstance(asset_doc, dict):
            continue

        existing_variants = _resolve_media_variants(doc)
        imported_variants = build_asset_responsive_variants(asset_doc.get("variants"))
        merged_variants = merge_media_variant_entries(existing_variants, imported_variants)
        doc["image_responsive_variants"] = merged_variants

        asset_author = _extract_primary_author(asset_doc)
        if asset_author:
            doc["image_author"] = asset_author

    return docs


def _format_item(doc: dict) -> dict:
    oid = doc.get("_id")
    image_responsive_variants = _resolve_media_variants(doc)
    result = {
        "id": str(oid) if oid else "",
        "image_url": doc.get("image_url", ""),
        "image_responsive_variants": image_responsive_variants,
        "responsive_variants": image_responsive_variants,
        "image_author": str(doc.get("image_author") or ""),
        "image_zoom": _safe_float(doc.get("image_zoom"), 1.0),
        "image_focal_x": _safe_float(doc.get("image_focal_x"), 50.0),
        "image_focal_y": _safe_float(doc.get("image_focal_y"), 50.0),
        "image_rotation": _safe_float(doc.get("image_rotation"), 0.0),
        "date": doc.get("date", ""),
        "tag": doc.get("tag", {"de": "", "en": ""}),
        "title": doc.get("title", {"de": "", "en": ""}),
        "text": doc.get("text", {"de": "", "en": ""}),
        "page_slug": doc.get("page_slug", ""),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }
    return result


def _with_item_page_job_metadata(item_payload: dict, job_payload: dict | None) -> dict:
    result = dict(item_payload or {})
    if not isinstance(job_payload, dict):
        return result
    job_id = str(job_payload.get("job_id") or "").strip()
    if job_id:
        result["item_page_generation_job_id"] = job_id
    status = str(job_payload.get("status") or "").strip()
    if status:
        result["item_page_generation_status"] = status
    slug = str(job_payload.get("slug") or "").strip()
    if slug:
        result["page_slug"] = slug
    return result


def _dedupe_items(items: list[dict]) -> list[dict]:
    """Remove duplicates by (date, title.de, title.en, tag.de, tag.en), keep first occurrence."""
    seen = set()
    out = []
    for it in items:
        key = (
            it.get("date", ""),
            (it.get("title") or {}).get("de", ""),
            (it.get("title") or {}).get("en", ""),
            (it.get("tag") or {}).get("de", ""),
            (it.get("tag") or {}).get("en", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


@router.get(
    "/items",
    dependencies=[Depends(require_permission("content:read"))],
)
async def list_blog_items():
    """List all shared blog items, sorted by explicit sort_order then date descending."""
    coll = _items_coll()
    # Primary sort: explicit sort_order (ascending, items without it sort last via None → large value).
    # Secondary sort: date descending (tiebreak / fallback for items with no sort_order).
    cursor = coll.find({}).sort([("sort_order", 1), ("date", -1)])
    docs: list[dict] = []
    async for doc in cursor:
        docs.append(doc)
    if not docs:
        migrated = await _migrate_from_sections()
        if migrated:
            cursor = coll.find({}).sort([("sort_order", 1), ("date", -1)])
            async for doc in cursor:
                docs.append(doc)
    docs = await _enrich_blog_item_docs_with_asset_media(docs)

    source_ids = [
        str(doc.get("_id") or "").strip()
        for doc in docs
        if str(doc.get("_id") or "").strip()
    ]
    freshness_map = await get_generated_item_page_template_freshness_map(
        _db(),
        source_type="blog",
        source_ids=source_ids,
    )
    items: list[dict] = []
    for doc in docs:
        source_id = str(doc.get("_id") or "").strip()
        doc["_id"] = source_id
        item_payload = _format_item(doc)
        item_payload["item_page_template_outdated"] = bool(
            (freshness_map.get(source_id) or {}).get("item_page_template_outdated")
        )
        items.append(item_payload)

    items = _dedupe_items(items)
    return {"items": items}


def _item_dedup_key(it: dict) -> tuple:
    """Key for deduplicating items during migration."""
    title = it.get("title") or {}
    return (
        it.get("date", ""),
        title.get("de", ""),
        title.get("en", ""),
        (it.get("tag") or {}).get("de", ""),
        (it.get("tag") or {}).get("en", ""),
    )


async def _unset_legacy_blog_section_type_data() -> None:
    await _db()["sections"].update_many(
        {
            "section_type": "blog",
            "$or": [
                {"type_data.items": {"$exists": True}},
                {"type_data.tags": {"$exists": True}},
            ],
        },
        {
            "$unset": {
                "type_data.items": "",
                "type_data.tags": "",
            },
            "$set": {"updated_at": datetime.utcnow()},
        },
    )


async def _migrate_from_sections() -> bool:
    """One-time migration: copy items from blog sections to blog_shared (deduplicated).
    Uses a MongoDB lock document to ensure only one concurrent request performs the migration."""
    items_coll = _items_coll()
    config_coll = _config_coll()

    if await items_coll.count_documents({}) > 0:
        await _unset_legacy_blog_section_type_data()
        return False

    try:
        await config_coll.insert_one({"_id": MIGRATION_LOCK_ID, "created_at": datetime.utcnow()})
    except DuplicateKeyError:
        for _ in range(50):
            await asyncio.sleep(0.1)
            if await items_coll.count_documents({}) > 0:
                await _unset_legacy_blog_section_type_data()
                return True
        return False

    if await items_coll.count_documents({}) > 0:
        await _unset_legacy_blog_section_type_data()
        return False

    sections = _db()["sections"]
    cursor = sections.find({"section_type": "blog"})
    seen_tags = set()
    seen_items = set()
    async for sec in cursor:
        type_data = sec.get("type_data") or {}
        for it in type_data.get("items") or []:
            key = _item_dedup_key(it)
            if key in seen_items:
                continue
            seen_items.add(key)
            tag = it.get("tag") or {"de": "", "en": ""}
            tag_key = (tag.get("de", ""), tag.get("en", ""))
            if tag_key not in seen_tags and (tag.get("de") or tag.get("en")):
                seen_tags.add(tag_key)
            doc = {
                "image_url": it.get("image_url", ""),
                "image_responsive_variants": _resolve_media_variants(it),
                "image_author": str(it.get("image_author") or ""),
                "image_zoom": float(it.get("image_zoom", 1.0)),
                "image_focal_x": float(it.get("image_focal_x", 50.0)),
                "image_focal_y": float(it.get("image_focal_y", 50.0)),
                "image_rotation": float(it.get("image_rotation", 0.0)),
                "date": it.get("date", ""),
                "tag": tag,
                "title": it.get("title") or {"de": "", "en": ""},
                "text": it.get("text") or {"de": "", "en": ""},
                "page_slug": "",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            await items_coll.insert_one(doc)
        for t in type_data.get("tags") or []:
            tag_key = (t.get("de", ""), t.get("en", ""))
            if tag_key not in seen_tags and (t.get("de") or t.get("en")):
                seen_tags.add(tag_key)
    if seen_tags:
        tags = [{"de": de, "en": en} for de, en in seen_tags]
        await config_coll.update_one(
            {"_id": CONFIG_ID},
            {"$set": {"tags": tags}},
            upsert=True,
        )
    await _unset_legacy_blog_section_type_data()
    return True


@router.get(
    "/config",
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_blog_config():
    """Get blog config (tags list)."""
    coll = _config_coll()
    doc = await coll.find_one({"_id": CONFIG_ID})  # string id
    if not doc:
        return {
            "tags": [
                {"de": "Aktuelles", "en": "News"},
                {"de": "Veranstaltung", "en": "Event"},
                {"de": "Interview", "en": "Interview"},
            ]
        }
    return {"tags": doc.get("tags", [])}


@router.post(
    "/items",
    dependencies=[Depends(require_permission("content:write"))],
)
async def create_blog_item(
    payload: BlogItem,
    user: KeycloakUser = Depends(get_current_user),
):
    """Create a blog item (admin only)."""
    await push_blog_shared_content_revisions(_db(), saved_by=user.username)
    coll = _items_coll()
    now = datetime.utcnow()
    payload_data = payload.model_dump()
    image_responsive_variants = _resolve_media_variants(payload_data)
    doc = {
        "image_url": payload.image_url or "",
        "image_responsive_variants": image_responsive_variants,
        "image_author": str(payload.image_author or "").strip(),
        "image_zoom": _safe_float(payload.image_zoom, 1.0)
        if payload.image_zoom is not None
        else 1.0,
        "image_focal_x": _safe_float(payload.image_focal_x, 50.0)
        if payload.image_focal_x is not None
        else 50.0,
        "image_focal_y": _safe_float(payload.image_focal_y, 50.0)
        if payload.image_focal_y is not None
        else 50.0,
        "image_rotation": _safe_float(payload.image_rotation, 0.0)
        if payload.image_rotation is not None
        else 0.0,
        "date": payload.date or "",
        "tag": payload.tag.model_dump() if payload.tag else {"de": "", "en": ""},
        "title": payload.title.model_dump() if payload.title else {"de": "", "en": ""},
        "text": payload.text.model_dump() if payload.text else {"de": "", "en": ""},
        "page_slug": payload.page_slug or "",
        "created_at": now,
        "updated_at": now,
    }
    result = await coll.insert_one(doc)
    doc["_id"] = result.inserted_id

    job_payload = await enqueue_blog_item_page_generation(_db(), str(result.inserted_id))
    return _with_item_page_job_metadata(_format_item(doc), job_payload)


@router.patch(
    "/items/{item_id}",
    dependencies=[Depends(require_permission("content:write"))],
)
async def update_blog_item(
    item_id: str,
    payload: BlogItem,
    user: KeycloakUser = Depends(get_current_user),
):
    """Update a blog item (admin only)."""
    coll = _items_coll()
    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(400, "Invalid item ID")
    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Item not found")
    payload_data_unset = payload.model_dump(exclude_unset=True)

    next_image_responsive_variants = (
        _resolve_media_variants(payload_data_unset)
        if _has_any_media_variant_key(payload_data_unset)
        else _resolve_media_variants(doc)
    )
    raw_image_author, has_image_author = _first_present_media_value(
        payload_data_unset,
        ("image_author", "imageAuthor", "author"),
    )
    next_values = {
        "image_url": payload.image_url if payload.image_url is not None else doc.get("image_url", ""),
        "image_responsive_variants": next_image_responsive_variants,
        "image_author": (
            str(raw_image_author or "").strip()
            if has_image_author
            else str(doc.get("image_author") or "")
        ),
        "image_zoom": _safe_float(payload.image_zoom, 1.0)
        if payload.image_zoom is not None
        else _safe_float(doc.get("image_zoom"), 1.0),
        "image_focal_x": _safe_float(payload.image_focal_x, 50.0)
        if payload.image_focal_x is not None
        else _safe_float(doc.get("image_focal_x"), 50.0),
        "image_focal_y": _safe_float(payload.image_focal_y, 50.0)
        if payload.image_focal_y is not None
        else _safe_float(doc.get("image_focal_y"), 50.0),
        "image_rotation": _safe_float(payload.image_rotation, 0.0)
        if payload.image_rotation is not None
        else _safe_float(doc.get("image_rotation"), 0.0),
        "date": payload.date if payload.date is not None else doc.get("date", ""),
        "tag": payload.tag.model_dump() if payload.tag is not None else doc.get("tag", {"de": "", "en": ""}),
        "title": payload.title.model_dump() if payload.title is not None else doc.get("title", {"de": "", "en": ""}),
        "text": payload.text.model_dump() if payload.text is not None else doc.get("text", {"de": "", "en": ""}),
        "page_slug": payload.page_slug if payload.page_slug is not None else doc.get("page_slug", ""),
    }
    current_values = {
        "image_url": doc.get("image_url", ""),
        "image_responsive_variants": _resolve_media_variants(doc),
        "image_author": str(doc.get("image_author") or ""),
        "image_zoom": _safe_float(doc.get("image_zoom"), 1.0),
        "image_focal_x": _safe_float(doc.get("image_focal_x"), 50.0),
        "image_focal_y": _safe_float(doc.get("image_focal_y"), 50.0),
        "image_rotation": _safe_float(doc.get("image_rotation"), 0.0),
        "date": doc.get("date", ""),
        "tag": doc.get("tag", {"de": "", "en": ""}),
        "title": doc.get("title", {"de": "", "en": ""}),
        "text": doc.get("text", {"de": "", "en": ""}),
        "page_slug": doc.get("page_slug", ""),
    }
    if snapshots_equal(current_values, next_values):
        return _format_item(doc)

    await push_blog_shared_content_revisions(_db(), saved_by=user.username)
    await coll.update_one({"_id": oid}, {"$set": {**next_values, "updated_at": datetime.utcnow()}})
    updated = await coll.find_one({"_id": oid})
    job_payload = await enqueue_blog_item_page_generation(_db(), item_id)
    updated_payload = _format_item(updated)
    return _with_item_page_job_metadata(updated_payload, job_payload)


@router.delete(
    "/items/{item_id}",
    dependencies=[Depends(require_permission("content:write"))],
)
async def delete_blog_item(
    item_id: str,
    user: KeycloakUser = Depends(get_current_user),
):
    """Delete a blog item (admin only)."""
    coll = _items_coll()
    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(400, "Invalid item ID")
    if not await coll.find_one({"_id": oid}):
        raise HTTPException(404, "Item not found")
    await push_blog_shared_content_revisions(_db(), saved_by=user.username)
    result = await coll.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(404, "Item not found")
    await cleanup_blog_item_generated_pages(_db(), item_id)
    return {"ok": True}


@router.put(
    "/items/reorder",
    dependencies=[Depends(require_permission("content:write"))],
)
async def reorder_blog_items(payload: dict):
    """Persist a manual sort order. Payload: { ids: [<id>, ...] } in desired display order."""
    raw_ids = payload.get("ids") if isinstance(payload, dict) else None
    if not isinstance(raw_ids, list):
        raise HTTPException(400, "payload must contain an 'ids' list")
    coll = _items_coll()
    now = datetime.utcnow()
    for position, raw_id in enumerate(raw_ids):
        try:
            oid = ObjectId(str(raw_id))
        except Exception:
            continue
        await coll.update_one(
            {"_id": oid},
            {"$set": {"sort_order": position, "updated_at": now}},
        )
    return {"ok": True}


@router.put(
    "/config",
    dependencies=[Depends(require_permission("content:write"))],
)
async def update_blog_config(
    payload: BlogConfig,
    user: KeycloakUser = Depends(get_current_user),
):
    """Update blog config (tags)."""
    coll = _config_coll()
    tags = [t.model_dump() if hasattr(t, "model_dump") else t for t in payload.tags]
    existing = await coll.find_one({"_id": CONFIG_ID})
    current_tags = existing.get("tags", []) if isinstance(existing, dict) else []
    if snapshots_equal(current_tags, tags):
        return {"tags": current_tags}

    await push_blog_shared_content_revisions(_db(), saved_by=user.username)
    await coll.update_one(
        {"_id": CONFIG_ID},
        {"$set": {"tags": tags}},
        upsert=True,
    )
    doc = await coll.find_one({"_id": CONFIG_ID})
    return {"tags": doc.get("tags", [])}
