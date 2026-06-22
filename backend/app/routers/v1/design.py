from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import get_args

from fastapi import APIRouter, Depends, HTTPException
from pymongo import ReturnDocument

from app.collection_names import DESIGN_CONFIG_COLLECTION, DESIGN_VERSIONS_COLLECTION, REVISIONS_COLLECTION
from app.db import get_client
from app.deps import get_current_user, require_permission
from app.font_cache import resolve_font_cache_for_design
from app.security import KeycloakUser
from app.settings import settings
from app.models.cms import (
    DesignSettingsCreate,
    DesignSettingsUpdate,
    DesignSettingsResponse,
    RevisionStatusResponse,
)
from app.media_responsive import (
    collect_raster_image_urls_from_payload,
    enrich_raster_payload_with_asset_docs,
    fetch_asset_docs_by_urls,
)
from app.revisioning import (
    REVISION_HISTORY_LIMIT,
    as_object_id,
    get_or_create_revision_config,
    is_global_design_revisions_enabled,
    push_revision_entry,
    snapshot_document,
)

# Fields where None is a valid DB value (e.g. "use default color").
# Derived from DesignSettingsCreate: only fields typed as `X | None` qualify.
_NULLABLE_DESIGN_FIELDS = frozenset(
    name
    for name, field in DesignSettingsCreate.model_fields.items()
    if type(None) in get_args(field.annotation)
)


router = APIRouter(prefix="/design", tags=["design"])

MAX_HISTORY = REVISION_HISTORY_LIMIT

# Singleton design settings ID
DESIGN_SETTINGS_KEY = "global"
VERSIONS_COLLECTION = DESIGN_VERSIONS_COLLECTION


def _db():
    return get_client()[settings.mongo_db]


_DESIGN_DEFAULTS = DesignSettingsCreate().model_dump()
_DESIGN_REVISION_EXCLUDE_KEYS = frozenset(
    {"_id", "key", "revision_id", "created_at", "updated_at", "comparison_version_id"}
)


def _extract_design_data(doc: dict) -> dict:
    """Extract revisable data from a design settings document."""
    result = snapshot_document(doc, exclude_keys=_DESIGN_REVISION_EXCLUDE_KEYS)
    # Backfill fields that may be missing.
    for key, default in _DESIGN_DEFAULTS.items():
        result.setdefault(key, default)
    return result


async def _push_to_history(
    design_id: str,
    current_data: dict,
    revision_id: str | None,
    saved_by: str | None = None,
):
    """Push current state to history, clear future, trim to MAX_HISTORY."""
    revisions = _db()[REVISIONS_COLLECTION]
    return await push_revision_entry(
        revisions,
        entity_type="design",
        entity_id=design_id,
        current_data=current_data,
        revision_id=as_object_id(revision_id),
        saved_by=saved_by,
        max_history=MAX_HISTORY,
    )


def _ensure_design_doc_complete(doc: dict) -> dict:
    """Backfill any missing fields in doc."""
    if "background_primary_color" not in doc:
        legacy_page_bg = doc.get("background_color")
        if isinstance(legacy_page_bg, str) and legacy_page_bg.strip():
            doc["background_primary_color"] = legacy_page_bg
        else:
            doc["background_primary_color"] = _DESIGN_DEFAULTS.get("background_primary_color")
    if "background_secondary_color" not in doc:
        legacy_section_bg = doc.get("section_background_color")
        if isinstance(legacy_section_bg, str) and legacy_section_bg.strip():
            doc["background_secondary_color"] = legacy_section_bg
        else:
            doc["background_secondary_color"] = _DESIGN_DEFAULTS.get("background_secondary_color")

    for key, default_val in _DESIGN_DEFAULTS.items():
        if key not in doc:
            doc[key] = default_val
    return doc


def _get_default_settings() -> dict:
    """Return default design settings derived from DesignSettingsCreate."""
    return dict(_DESIGN_DEFAULTS)


def _strip_snapshot_meta(doc: dict | None) -> dict | None:
    if not doc:
        return None
    return {
        key: value
        for key, value in doc.items()
        if key not in {"_id", "id", "key", "revision_id", "created_at", "updated_at", "comparison_version_id"}
    }


async def _inject_cached_font_stylesheets(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return payload

    fallback_stylesheet_urls = (
        payload.get("font_stylesheet_urls")
        if isinstance(payload.get("font_stylesheet_urls"), list)
        else []
    )
    fallback_pending_families = (
        payload.get("font_cache_pending_families")
        if isinstance(payload.get("font_cache_pending_families"), list)
        else []
    )

    try:
        resolved = await resolve_font_cache_for_design(
            payload,
            queue_missing=False,
            force_retry_errors=False,
            resolve_inline=False,
        )
    except Exception:
        resolved = {
            "font_stylesheet_urls": fallback_stylesheet_urls,
            "pending_families": fallback_pending_families,
        }

    resolved_stylesheet_urls = (
        resolved.get("font_stylesheet_urls")
        if isinstance(resolved.get("font_stylesheet_urls"), list)
        else fallback_stylesheet_urls
    )
    resolved_pending_families = (
        resolved.get("pending_families")
        if isinstance(resolved.get("pending_families"), list)
        else fallback_pending_families
    )

    return {
        **payload,
        "font_stylesheet_urls": resolved_stylesheet_urls,
        "font_cache_pending_families": resolved_pending_families,
    }


async def _enrich_design_payload_with_asset_media(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return payload

    image_urls = collect_raster_image_urls_from_payload(payload)
    if not image_urls:
        return payload

    asset_docs_by_url = await fetch_asset_docs_by_urls(_db(), image_urls)
    if not asset_docs_by_url:
        return payload

    enrich_raster_payload_with_asset_docs(payload, asset_docs_by_url)
    return payload


def _compute_version_hash(design_settings: dict | None) -> str:
    payload = json.dumps(
        {"d": design_settings},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


async def _ensure_published_design_version_exists(before_design_doc: dict | None) -> None:
    """Guarantee a published version snapshot exists independently of mutable global draft."""
    db = _db()
    versions = db[VERSIONS_COLLECTION]

    published = await versions.find_one({"is_published": True}, projection={"_id": 1})
    if published:
        return

    # Recovery path: versions exist but none is currently marked published.
    latest = await versions.find_one({}, sort=[("created_at", -1)])
    if latest:
        now = datetime.utcnow()
        await versions.update_many({"is_published": True}, {"$set": {"is_published": False}})
        await versions.update_one(
            {"_id": latest["_id"]},
            {
                "$set": {
                    "is_published": True,
                    "published_at": now,
                    "published_by": "system:auto-bootstrap",
                }
            },
        )
        return

    design_settings = _strip_snapshot_meta(before_design_doc)
    if not design_settings:
        return

    now = datetime.utcnow()
    versions_doc = {
        "title": "Initial Published Snapshot",
        "description": "Auto-generated baseline before draft edits",
        "rating": 0,
        "hash": _compute_version_hash(design_settings),
        "created_at": now,
        "created_by": "system:auto-bootstrap",
        "is_published": True,
        "published_at": now,
        "published_by": "system:auto-bootstrap",
        "design_settings": design_settings,
        "auto_bootstrap": True,
    }
    await versions.insert_one(versions_doc)


# -------------------------
# CRUD endpoints
# -------------------------


@router.get(
    "",
    response_model=DesignSettingsResponse,
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_design_settings():
    """Get the global design settings (creates default if not exists)."""
    design_coll = _db()["design_config"]

    doc = await design_coll.find_one({"key": DESIGN_SETTINGS_KEY})

    if not doc:
        # Create default settings
        now = datetime.utcnow()
        defaults = _get_default_settings()
        doc = {
            "key": DESIGN_SETTINGS_KEY,
            **defaults,
            "revision_id": None,
            "created_at": now,
            "updated_at": now,
        }
        result = await design_coll.insert_one(doc)
        doc["_id"] = result.inserted_id
    else:
        doc = _ensure_design_doc_complete(doc)

    doc["id"] = str(doc["_id"])
    doc = await _enrich_design_payload_with_asset_media(doc)
    return await _inject_cached_font_stylesheets(doc)


@router.patch(
    "",
    response_model=DesignSettingsResponse,
    dependencies=[Depends(require_permission("design:write"))],
)
async def update_design_settings(
    payload: DesignSettingsUpdate,
    user: KeycloakUser = Depends(get_current_user),
):
    """Update design settings (partial update), saving current state to history."""
    db = _db()
    design_coll = db[DESIGN_CONFIG_COLLECTION]
    revision_config = await get_or_create_revision_config(db)
    revisions_enabled = is_global_design_revisions_enabled(revision_config)

    # Get or create current settings
    current = await design_coll.find_one({"key": DESIGN_SETTINGS_KEY})

    if not current:
        # Create default settings first
        now = datetime.utcnow()
        defaults = _get_default_settings()
        current = {
            "key": DESIGN_SETTINGS_KEY,
            **defaults,
            "revision_id": None,
            "created_at": now,
            "updated_at": now,
        }
        result = await design_coll.insert_one(current)
        current["_id"] = result.inserted_id

    await _ensure_published_design_version_exists(current)

    # exclude_unset=True so explicitly-sent None can clear nullable fields
    patch: dict = {}
    payload_dict = payload.model_dump(exclude_unset=True)

    for key, value in payload_dict.items():
        if value is None and key not in _NULLABLE_DESIGN_FIELDS:
            continue
        patch[key] = value

    if not patch:
        raise HTTPException(400, "No fields to update")

    revision_id = current.get("revision_id")
    if revisions_enabled:
        current_data = _extract_design_data(current)
        new_revision_id = await _push_to_history(
            str(current["_id"]),
            current_data,
            revision_id,
            saved_by=user.username,
        )
        patch["revision_id"] = new_revision_id or revision_id
    patch["updated_at"] = datetime.utcnow()

    doc = await design_coll.find_one_and_update(
        {"key": DESIGN_SETTINGS_KEY},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    doc = _ensure_design_doc_complete(doc)
    doc["id"] = str(doc["_id"])
    doc = await _enrich_design_payload_with_asset_media(doc)
    return await _inject_cached_font_stylesheets(doc)


@router.put(
    "",
    response_model=DesignSettingsResponse,
    dependencies=[Depends(require_permission("design:write"))],
)
async def replace_design_settings(
    payload: DesignSettingsCreate,
    user: KeycloakUser = Depends(get_current_user),
):
    """Replace all design settings, saving current state to history."""
    db = _db()
    design_coll = db[DESIGN_CONFIG_COLLECTION]
    revision_config = await get_or_create_revision_config(db)
    revisions_enabled = is_global_design_revisions_enabled(revision_config)

    current = await design_coll.find_one({"key": DESIGN_SETTINGS_KEY})
    baseline_doc = current or {"key": DESIGN_SETTINGS_KEY, **_get_default_settings()}
    await _ensure_published_design_version_exists(baseline_doc)

    now = datetime.utcnow()

    if current:
        revision_id = current.get("revision_id")
        patch = payload.model_dump()
        if revisions_enabled:
            current_data = _extract_design_data(current)
            new_revision_id = await _push_to_history(
                str(current["_id"]),
                current_data,
                revision_id,
                saved_by=user.username,
            )
            patch["revision_id"] = new_revision_id or revision_id
        patch["updated_at"] = now

        doc = await design_coll.find_one_and_update(
            {"key": DESIGN_SETTINGS_KEY},
            {"$set": patch},
            return_document=ReturnDocument.AFTER,
        )
    else:
        # Create new
        doc = {
            "key": DESIGN_SETTINGS_KEY,
            **payload.model_dump(),
            "revision_id": None,
            "created_at": now,
            "updated_at": now,
        }
        result = await design_coll.insert_one(doc)
        doc["_id"] = result.inserted_id

    doc["id"] = str(doc["_id"])
    doc = await _enrich_design_payload_with_asset_media(doc)
    return await _inject_cached_font_stylesheets(doc)


@router.post(
    "/reset",
    response_model=DesignSettingsResponse,
    dependencies=[Depends(require_permission("design:write"))],
)
async def reset_design_settings(
    user: KeycloakUser = Depends(get_current_user),
):
    """Reset design settings to defaults, saving current state to history."""
    db = _db()
    design_coll = db[DESIGN_CONFIG_COLLECTION]
    revision_config = await get_or_create_revision_config(db)
    revisions_enabled = is_global_design_revisions_enabled(revision_config)

    current = await design_coll.find_one({"key": DESIGN_SETTINGS_KEY})
    baseline_doc = current or {"key": DESIGN_SETTINGS_KEY, **_get_default_settings()}
    await _ensure_published_design_version_exists(baseline_doc)

    now = datetime.utcnow()
    defaults = _get_default_settings()

    if current:
        revision_id = current.get("revision_id")
        patch = {
            **defaults,
            "updated_at": now,
        }
        if revisions_enabled:
            current_data = _extract_design_data(current)
            new_revision_id = await _push_to_history(
                str(current["_id"]),
                current_data,
                revision_id,
                saved_by=user.username,
            )
            patch["revision_id"] = new_revision_id or revision_id

        doc = await design_coll.find_one_and_update(
            {"key": DESIGN_SETTINGS_KEY},
            {"$set": patch},
            return_document=ReturnDocument.AFTER,
        )
    else:
        doc = {
            "key": DESIGN_SETTINGS_KEY,
            **defaults,
            "revision_id": None,
            "created_at": now,
            "updated_at": now,
        }
        result = await design_coll.insert_one(doc)
        doc["_id"] = result.inserted_id

    doc = _ensure_design_doc_complete(doc)
    doc["id"] = str(doc["_id"])
    doc = await _enrich_design_payload_with_asset_media(doc)
    return await _inject_cached_font_stylesheets(doc)


# -------------------------
# Undo/Redo endpoints
# -------------------------


@router.get("/revisions/status", response_model=RevisionStatusResponse)
async def get_revision_status(
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    """Get undo/redo status for design settings."""
    db = _db()
    design_coll = db[DESIGN_CONFIG_COLLECTION]
    revisions = db[REVISIONS_COLLECTION]
    revision_config = await get_or_create_revision_config(db)
    revisions_enabled = is_global_design_revisions_enabled(revision_config)

    if not revisions_enabled:
        return RevisionStatusResponse(
            enabled=False,
            can_undo=False,
            can_redo=False,
            history_count=0,
            future_count=0,
        )

    current = await design_coll.find_one({"key": DESIGN_SETTINGS_KEY})
    if not current:
        return RevisionStatusResponse(
            enabled=True,
            can_undo=False, can_redo=False, history_count=0, future_count=0
        )

    doc = await revisions.find_one(
        {"entity_type": "design", "entity_id": str(current["_id"])}
    )
    if not doc:
        return RevisionStatusResponse(
            enabled=True,
            can_undo=False, can_redo=False, history_count=0, future_count=0
        )

    history = doc.get("history", [])
    future = doc.get("future", [])

    return RevisionStatusResponse(
        enabled=True,
        can_undo=len(history) > 0,
        can_redo=len(future) > 0,
        history_count=len(history),
        future_count=len(future),
        last_saved_by=doc.get("last_saved_by") or "unknown",
        last_saved_at=doc.get("last_saved_at"),
    )


@router.post(
    "/undo",
    response_model=DesignSettingsResponse,
    dependencies=[Depends(require_permission("design:write"))],
)
async def undo_design():
    """Undo the last change to design settings."""
    db = _db()
    design_coll = db[DESIGN_CONFIG_COLLECTION]
    revisions = db[REVISIONS_COLLECTION]
    revision_config = await get_or_create_revision_config(db)
    if not is_global_design_revisions_enabled(revision_config):
        raise HTTPException(400, "Global design revisions are disabled")

    current = await design_coll.find_one({"key": DESIGN_SETTINGS_KEY})
    if not current:
        raise HTTPException(404, "Design settings not found")

    revision_doc = await revisions.find_one(
        {"entity_type": "design", "entity_id": str(current["_id"])}
    )
    if not revision_doc or not revision_doc.get("history"):
        raise HTTPException(400, "Nothing to undo")

    history = revision_doc["history"]
    future = revision_doc.get("future", [])

    prev_entry = history.pop()

    current_data = _extract_design_data(current)
    future.append({
        "saved_at": revision_doc.get("last_saved_at") or datetime.utcnow(),
        "saved_by": revision_doc.get("last_saved_by"),
        "data": current_data,
    })

    await revisions.update_one(
        {"_id": revision_doc["_id"]},
        {"$set": {
            "history": history,
            "future": future,
            "last_saved_by": prev_entry.get("saved_by"),
            "last_saved_at": prev_entry.get("saved_at"),
        }},
    )

    prev_data = prev_entry["data"]
    patch = {
        **prev_data,
        "updated_at": datetime.utcnow(),
    }

    doc = await design_coll.find_one_and_update(
        {"key": DESIGN_SETTINGS_KEY},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    doc = _ensure_design_doc_complete(doc)
    doc["id"] = str(doc["_id"])
    doc = await _enrich_design_payload_with_asset_media(doc)
    return await _inject_cached_font_stylesheets(doc)


@router.post(
    "/redo",
    response_model=DesignSettingsResponse,
    dependencies=[Depends(require_permission("design:write"))],
)
async def redo_design():
    """Redo a previously undone change to design settings."""
    db = _db()
    design_coll = db[DESIGN_CONFIG_COLLECTION]
    revisions = db[REVISIONS_COLLECTION]
    revision_config = await get_or_create_revision_config(db)
    if not is_global_design_revisions_enabled(revision_config):
        raise HTTPException(400, "Global design revisions are disabled")

    current = await design_coll.find_one({"key": DESIGN_SETTINGS_KEY})
    if not current:
        raise HTTPException(404, "Design settings not found")

    revision_doc = await revisions.find_one(
        {"entity_type": "design", "entity_id": str(current["_id"])}
    )
    if not revision_doc or not revision_doc.get("future"):
        raise HTTPException(400, "Nothing to redo")

    history = revision_doc.get("history", [])
    future = revision_doc["future"]

    next_entry = future.pop()

    current_data = _extract_design_data(current)
    history.append({
        "saved_at": revision_doc.get("last_saved_at") or datetime.utcnow(),
        "saved_by": revision_doc.get("last_saved_by"),
        "data": current_data,
    })

    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    await revisions.update_one(
        {"_id": revision_doc["_id"]},
        {"$set": {
            "history": history,
            "future": future,
            "last_saved_by": next_entry.get("saved_by"),
            "last_saved_at": next_entry.get("saved_at"),
        }},
    )

    next_data = next_entry["data"]
    patch = {
        **next_data,
        "updated_at": datetime.utcnow(),
    }

    doc = await design_coll.find_one_and_update(
        {"key": DESIGN_SETTINGS_KEY},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    doc = _ensure_design_doc_complete(doc)
    doc["id"] = str(doc["_id"])
    doc = await _enrich_design_payload_with_asset_media(doc)
    return await _inject_cached_font_stylesheets(doc)
