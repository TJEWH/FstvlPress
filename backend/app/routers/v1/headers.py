from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo import ReturnDocument

from app.db import get_client
from app.deps import get_current_user, require_permission
from app.revisioning import (
    REVISION_HISTORY_LIMIT,
    build_revision_history_payload,
    get_or_create_revision_config,
    get_header_revision_options,
    header_revisions_enabled,
    push_revision_entry,
    resolve_effective_change_kind,
    snapshots_equal,
)
from app.security import KeycloakUser
from app.settings import settings
from app.template_sync import sync_generated_item_page_review_overrides_for_saved_targets
from app.models.cms import (
    HeaderCreate,
    HeaderUpdate,
    HeaderResponse,
    RevisionStatusResponse,
)

router = APIRouter(prefix="/headers", tags=["headers"])
logger = logging.getLogger(__name__)


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


ALL_HEADER_FIELDS = ["title", "subtitle", "cta_buttons", "overlay_image", "background_image"]


def _infer_header_change_kind_from_patch(patch: dict) -> str:
    if not isinstance(patch, dict):
        return "content"
    keys = {str(k) for k in patch.keys()}
    if not keys:
        return "content"
    if keys == {"design_overrides"}:
        return "design"
    if "design_overrides" in keys:
        return "both"
    return "content"


def _require_design_write(user: KeycloakUser) -> None:
    if user.has_permission("design:write"):
        return
    raise HTTPException(
        status_code=403,
        detail="Missing required permissions: design:write",
    )


def _extract_header_content(doc: dict) -> dict:
    return {
        "name": doc.get("name"),
        "header_type": doc.get("header_type", "hero"),
        "enabled_fields": doc.get("enabled_fields", ALL_HEADER_FIELDS),
        "background_media_url": doc.get("background_media_url"),
        "background_zoom": _safe_float(doc.get("background_zoom"), 1.0),
        "background_focal_x": _safe_float(doc.get("background_focal_x"), 50.0),
        "background_focal_y": _safe_float(doc.get("background_focal_y"), 50.0),
        "background_rotation": _safe_float(doc.get("background_rotation"), 0.0),
        "overlay_image_url": doc.get("overlay_image_url"),
        "overlay_zoom": _safe_float(doc.get("overlay_zoom"), 1.0),
        "overlay_focal_x": _safe_float(doc.get("overlay_focal_x"), 50.0),
        "overlay_focal_y": _safe_float(doc.get("overlay_focal_y"), 50.0),
        "overlay_rotation": _safe_float(doc.get("overlay_rotation"), 0.0),
        "hero_title": doc.get("hero_title", {"de": "", "en": ""}),
        "hero_subtitle": doc.get("hero_subtitle", {"de": "", "en": ""}),
        "cta_buttons": doc.get("cta_buttons", []),
        "admin_notes": doc.get("admin_notes"),
        "admin_todos": doc.get("admin_todos", []),
    }


def _extract_header_design(doc: dict) -> dict:
    return {
        "design_overrides": deepcopy(doc.get("design_overrides")),
    }


def _build_header_revision_snapshot(
    doc: dict,
    *,
    include_content: bool,
    include_design: bool,
) -> dict:
    snapshot = {"schema_version": 2}
    if include_content:
        snapshot["content"] = _extract_header_content(doc)
    if include_design:
        snapshot["design"] = _extract_header_design(doc)
    return snapshot


def _parse_header_revision_snapshot(data: dict) -> tuple[dict | None, dict | None]:
    if not isinstance(data, dict):
        return None, None

    if "content" in data or "design" in data:
        content = data.get("content")
        design = data.get("design")
        return (
            deepcopy(content) if isinstance(content, dict) else None,
            deepcopy(design) if isinstance(design, dict) else None,
        )
    return None, None


def _format_header_response(doc: dict) -> dict:
    """Format a header document for the response."""
    enabled = doc.get("enabled_fields", ALL_HEADER_FIELDS)
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name"),
        "shared": bool(doc.get("shared", False)),
        "header_type": doc.get("header_type", "hero"),
        "enabled_fields": enabled,
        "background_media_url": doc.get("background_media_url"),
        "background_zoom": _safe_float(doc.get("background_zoom"), 1.0),
        "background_focal_x": _safe_float(doc.get("background_focal_x"), 50.0),
        "background_focal_y": _safe_float(doc.get("background_focal_y"), 50.0),
        "background_rotation": _safe_float(doc.get("background_rotation"), 0.0),
        "overlay_image_url": doc.get("overlay_image_url"),
        "overlay_zoom": _safe_float(doc.get("overlay_zoom"), 1.0),
        "overlay_focal_x": _safe_float(doc.get("overlay_focal_x"), 50.0),
        "overlay_focal_y": _safe_float(doc.get("overlay_focal_y"), 50.0),
        "overlay_rotation": _safe_float(doc.get("overlay_rotation"), 0.0),
        "hero_title": doc.get("hero_title", {"de": "", "en": ""}),
        "hero_subtitle": doc.get("hero_subtitle", {"de": "", "en": ""}),
        "cta_buttons": doc.get("cta_buttons", []),
        "design_overrides": doc.get("design_overrides"),
        "admin_notes": doc.get("admin_notes"),
        "admin_todos": doc.get("admin_todos", []),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


# -------------------------
# CRUD endpoints
# -------------------------


@router.post(
    "",
    response_model=HeaderResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def create_header(
    payload: HeaderCreate,
    user: KeycloakUser = Depends(get_current_user),
):
    """Create a new header."""
    headers = _db()["headers"]

    if payload.design_overrides is not None or payload.revision_change_kind in {"design", "both"}:
        _require_design_write(user)

    now = datetime.utcnow()
    enabled = payload.enabled_fields

    hero_title_dict = (
        payload.hero_title.model_dump() if payload.hero_title else {"de": "", "en": ""}
    ) if "title" in enabled else None
    hero_subtitle_dict = (
        payload.hero_subtitle.model_dump()
        if payload.hero_subtitle
        else {"de": "", "en": ""}
    ) if "subtitle" in enabled else None

    doc = {
        "name": payload.name,
        "shared": bool(payload.shared),
        "header_type": payload.header_type,
        "enabled_fields": enabled,
        "background_media_url": payload.background_media_url if "background_image" in enabled else None,
        "background_zoom": float(payload.background_zoom if "background_image" in enabled else 1.0),
        "background_focal_x": float(payload.background_focal_x if "background_image" in enabled else 50.0),
        "background_focal_y": float(payload.background_focal_y if "background_image" in enabled else 50.0),
        "background_rotation": float(payload.background_rotation if "background_image" in enabled else 0.0),
        "overlay_image_url": payload.overlay_image_url if "overlay_image" in enabled else None,
        "overlay_zoom": float(payload.overlay_zoom if "overlay_image" in enabled else 1.0),
        "overlay_focal_x": float(payload.overlay_focal_x if "overlay_image" in enabled else 50.0),
        "overlay_focal_y": float(payload.overlay_focal_y if "overlay_image" in enabled else 50.0),
        "overlay_rotation": float(payload.overlay_rotation if "overlay_image" in enabled else 0.0),
        "hero_title": hero_title_dict,
        "hero_subtitle": hero_subtitle_dict,
        "cta_buttons": [btn.model_dump() for btn in payload.cta_buttons] if "cta_buttons" in enabled else [],
        "admin_notes": payload.admin_notes,
        "admin_todos": payload.admin_todos or [],
        "revision_id": None,
        "created_at": now,
        "updated_at": now,
    }
    res = await headers.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return _format_header_response(doc)


@router.get("", response_model=list[HeaderResponse])
async def list_headers(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None, description="ISO datetime for pagination"),
    header_type: str | None = Query(default=None, description="Filter by header type"),
    shared_only: bool = Query(default=False, description="Only return shared reusable headers"),
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    """List all headers with optional filtering."""
    headers = _db()["headers"]

    q: dict = {}
    if cursor:
        q["updated_at"] = {"$lt": datetime.fromisoformat(cursor)}
    if header_type:
        q["header_type"] = header_type
    if shared_only:
        q["shared"] = True

    docs = (
        await headers.find(q).sort("updated_at", -1).limit(limit).to_list(length=limit)
    )
    return [_format_header_response(d) for d in docs]


@router.get("/with-usage")
async def list_headers_with_usage(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    header_type: str | None = Query(default=None, description="Filter by header type"),
    shared_only: bool = Query(default=False, description="Only return shared reusable headers"),
    sort_by: str = Query(
        default="updated_at",
        description="Sort field: created_at, updated_at, name, or legacy field_direction value.",
    ),
    sort_direction: str = Query(default="desc", description="Sort direction: asc or desc"),
    include_total: bool = Query(default=False),
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    """List all headers with usage information (which pages use them)."""
    db = _db()
    headers_coll = db["headers"]
    pages_coll = db["pages"]

    normalized_sort_by = str(sort_by or "updated_at").strip().lower()
    normalized_sort_direction = str(sort_direction or "desc").strip().lower()
    legacy_sort_parts = normalized_sort_by.rsplit("_", 1)
    if len(legacy_sort_parts) == 2 and legacy_sort_parts[1] in {"asc", "desc"}:
        normalized_sort_by = legacy_sort_parts[0]
        normalized_sort_direction = legacy_sort_parts[1]
    sort_field_map = {
        "created": "created_at",
        "created_at": "created_at",
        "updated": "updated_at",
        "updated_at": "updated_at",
        "name": "name",
        "title": "name",
    }
    sort_field = sort_field_map.get(normalized_sort_by)
    if sort_field is None:
        raise HTTPException(400, "sort_by must be one of: created_at, updated_at, name")
    if normalized_sort_direction not in {"asc", "desc"}:
        raise HTTPException(400, "sort_direction must be asc or desc")
    sort_order = 1 if normalized_sort_direction == "asc" else -1
    sort_spec = [(sort_field, sort_order)]
    if sort_field == "name":
        sort_spec = [
            ("name", sort_order),
            ("hero_title.de", sort_order),
            ("hero_title.en", sort_order),
            ("updated_at", -1),
        ]

    q: dict = {}
    if header_type:
        q["header_type"] = header_type
    if shared_only:
        q["shared"] = True
    total_count = await headers_coll.count_documents(q) if include_total else None

    docs = (
        await headers_coll.find(q)
        .sort(sort_spec)
        .skip(offset)
        .limit(limit)
        .to_list(length=limit)
    )

    pages = await pages_coll.find(
        {},
        {
            "slug": 1,
            "header_id": 1,
            "has_header": 1,
            "template_managed": 1,
        },
    ).to_list(length=1000)

    header_usage: dict[str, list[dict]] = {}
    generated_header_ids: set[str] = set()
    for page in pages:
        hid = page.get("header_id")
        if hid:
            header_id = str(hid)
            if page.get("template_managed") is True:
                generated_header_ids.add(header_id)
            if header_id not in header_usage:
                header_usage[header_id] = []
            header_usage[header_id].append(
                {
                    "slug": page.get("slug", ""),
                    "has_header": page.get("has_header", False),
                }
            )

    result = []
    for doc in docs:
        header_id = str(doc["_id"])
        usage = header_usage.get(header_id, [])
        formatted = _format_header_response(doc)
        formatted["is_generated"] = header_id in generated_header_ids
        formatted["usage"] = usage
        formatted["usage_count"] = len(usage)
        result.append(formatted)

    if include_total:
        return {
            "items": result,
            "total": total_count if total_count is not None else len(result),
            "limit": limit,
            "offset": offset,
        }

    return result


@router.get("/{header_id}/usage")
async def get_header_usage(
    header_id: str,
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    """Get detailed usage information for a header (which pages use it)."""
    db = _db()
    headers_coll = db["headers"]
    pages_coll = db["pages"]

    header = await headers_coll.find_one({"_id": ObjectId(header_id)})
    if not header:
        raise HTTPException(404, "Header not found")

    pages = await pages_coll.find({"header_id": header_id}).to_list(length=100)

    usage = []
    for page in pages:
        usage.append(
            {
                "page_id": str(page["_id"]),
                "slug": page.get("slug", ""),
                "has_header": page.get("has_header", False),
            }
        )

    return {
        "header_id": header_id,
        "usage": usage,
        "usage_count": len(usage),
        "can_delete": len(usage) == 0,
    }


@router.get("/{header_id}", response_model=HeaderResponse)
async def get_header(
    header_id: str,
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    """Get a single header by ID."""
    headers = _db()["headers"]
    doc = await headers.find_one({"_id": ObjectId(header_id)})
    if not doc:
        raise HTTPException(404, "Header not found")
    return _format_header_response(doc)


@router.put(
    "/{header_id}",
    response_model=HeaderResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def replace_header(
    header_id: str,
    payload: HeaderCreate,
    user: KeycloakUser = Depends(get_current_user),
):
    """Replace a header entirely, saving current state to history."""
    db = _db()
    headers = db["headers"]

    current = await headers.find_one({"_id": ObjectId(header_id)})
    if not current:
        raise HTTPException(404, "Header not found")

    revision_config = await get_or_create_revision_config(db)
    header_options = get_header_revision_options(revision_config)
    revisions_enabled = header_revisions_enabled(header_options)

    revision_id = current.get("revision_id")
    new_revision_id = None
    patch_change_kind = payload.revision_change_kind or _infer_header_change_kind_from_patch(
        {
            "name": payload.name,
            "header_type": payload.header_type,
            "enabled_fields": payload.enabled_fields,
            "background_media_url": payload.background_media_url,
            "background_zoom": payload.background_zoom,
            "background_focal_x": payload.background_focal_x,
            "background_focal_y": payload.background_focal_y,
            "background_rotation": payload.background_rotation,
            "overlay_image_url": payload.overlay_image_url,
            "overlay_zoom": payload.overlay_zoom,
            "overlay_focal_x": payload.overlay_focal_x,
            "overlay_focal_y": payload.overlay_focal_y,
            "overlay_rotation": payload.overlay_rotation,
            "hero_title": payload.hero_title.model_dump() if payload.hero_title else None,
            "hero_subtitle": payload.hero_subtitle.model_dump() if payload.hero_subtitle else None,
            "cta_buttons": [btn.model_dump() for btn in payload.cta_buttons],
            "design_overrides": payload.design_overrides,
            "admin_notes": payload.admin_notes,
            "admin_todos": payload.admin_todos,
        }
    )
    if patch_change_kind in {"design", "both"}:
        _require_design_write(user)

    now = datetime.utcnow()
    enabled = payload.enabled_fields
    hero_title_dict = (
        payload.hero_title.model_dump() if payload.hero_title else {"de": "", "en": ""}
    ) if "title" in enabled else None
    hero_subtitle_dict = (
        payload.hero_subtitle.model_dump()
        if payload.hero_subtitle
        else {"de": "", "en": ""}
    ) if "subtitle" in enabled else None

    patch = {
        "name": payload.name,
        "shared": bool(payload.shared),
        "header_type": payload.header_type,
        "enabled_fields": enabled,
        "background_media_url": payload.background_media_url if "background_image" in enabled else None,
        "background_zoom": float(payload.background_zoom if "background_image" in enabled else 1.0),
        "background_focal_x": float(payload.background_focal_x if "background_image" in enabled else 50.0),
        "background_focal_y": float(payload.background_focal_y if "background_image" in enabled else 50.0),
        "background_rotation": float(payload.background_rotation if "background_image" in enabled else 0.0),
        "overlay_image_url": payload.overlay_image_url if "overlay_image" in enabled else None,
        "overlay_zoom": float(payload.overlay_zoom if "overlay_image" in enabled else 1.0),
        "overlay_focal_x": float(payload.overlay_focal_x if "overlay_image" in enabled else 50.0),
        "overlay_focal_y": float(payload.overlay_focal_y if "overlay_image" in enabled else 50.0),
        "overlay_rotation": float(payload.overlay_rotation if "overlay_image" in enabled else 0.0),
        "hero_title": hero_title_dict,
        "hero_subtitle": hero_subtitle_dict,
        "cta_buttons": [btn.model_dump() for btn in payload.cta_buttons] if "cta_buttons" in enabled else [],
        "admin_notes": payload.admin_notes,
        "admin_todos": payload.admin_todos or [],
        "revision_id": new_revision_id or revision_id,
        "updated_at": now,
    }
    if payload.design_overrides is not None:
        patch["design_overrides"] = payload.design_overrides
    if revisions_enabled:
        current_data = _build_header_revision_snapshot(
            current,
            include_content=header_options["include_content"],
            include_design=header_options["include_design"],
        )
        next_doc = deepcopy(current)
        next_doc.update(patch)
        next_data = _build_header_revision_snapshot(
            next_doc,
            include_content=header_options["include_content"],
            include_design=header_options["include_design"],
        )
        if not snapshots_equal(current_data, next_data):
            effective_change_kind = resolve_effective_change_kind(
                current_data=current_data,
                next_data=next_data,
                parse_snapshot=_parse_header_revision_snapshot,
                requested_kind=patch_change_kind,
            )
            new_revision_id = await push_revision_entry(
                db["revisions"],
                entity_type="header",
                entity_id=header_id,
                current_data=current_data,
                revision_id=revision_id,
                saved_by=user.username,
                change_kind=effective_change_kind,
                reverted_from_saved_at=payload.revision_reverted_from_saved_at,
            )

    doc = await headers.find_one_and_update(
        {"_id": ObjectId(header_id)},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    try:
        await sync_generated_item_page_review_overrides_for_saved_targets(
            db,
            collection="header",
            document_id=header_id,
            saved_doc=doc,
            updated_paths=set(patch.keys()),
        )
    except Exception:
        logger.warning(
            "generated_item_page.review_override_header_sync_failed header_id=%s",
            header_id,
            exc_info=True,
        )
    return _format_header_response(doc)


@router.patch(
    "/{header_id}",
    response_model=HeaderResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def update_header(
    header_id: str,
    payload: HeaderUpdate,
    user: KeycloakUser = Depends(get_current_user),
):
    """Partially update a header, saving current state to history."""
    db = _db()
    headers = db["headers"]

    current = await headers.find_one({"_id": ObjectId(header_id)})
    if not current:
        raise HTTPException(404, "Header not found")

    patch: dict = {}
    if payload.name is not None:
        patch["name"] = payload.name
    if payload.shared is not None:
        patch["shared"] = bool(payload.shared)
    if payload.header_type is not None:
        patch["header_type"] = payload.header_type
    if payload.enabled_fields is not None:
        patch["enabled_fields"] = payload.enabled_fields
    if payload.background_media_url is not None:
        patch["background_media_url"] = payload.background_media_url
    if payload.background_zoom is not None:
        patch["background_zoom"] = float(payload.background_zoom)
    if payload.background_focal_x is not None:
        patch["background_focal_x"] = float(payload.background_focal_x)
    if payload.background_focal_y is not None:
        patch["background_focal_y"] = float(payload.background_focal_y)
    if payload.background_rotation is not None:
        patch["background_rotation"] = float(payload.background_rotation)
    if payload.overlay_image_url is not None:
        patch["overlay_image_url"] = payload.overlay_image_url
    if payload.overlay_zoom is not None:
        patch["overlay_zoom"] = float(payload.overlay_zoom)
    if payload.overlay_focal_x is not None:
        patch["overlay_focal_x"] = float(payload.overlay_focal_x)
    if payload.overlay_focal_y is not None:
        patch["overlay_focal_y"] = float(payload.overlay_focal_y)
    if payload.overlay_rotation is not None:
        patch["overlay_rotation"] = float(payload.overlay_rotation)
    if payload.hero_title is not None:
        patch["hero_title"] = payload.hero_title.model_dump()
    if payload.hero_subtitle is not None:
        patch["hero_subtitle"] = payload.hero_subtitle.model_dump()
    if payload.cta_buttons is not None:
        patch["cta_buttons"] = [btn.model_dump() for btn in payload.cta_buttons]
    if payload.design_overrides is not None:
        patch["design_overrides"] = payload.design_overrides
    if payload.admin_notes is not None:
        patch["admin_notes"] = payload.admin_notes
    if payload.admin_todos is not None:
        patch["admin_todos"] = payload.admin_todos

    if not patch:
        raise HTTPException(400, "No fields to update")

    revision_config = await get_or_create_revision_config(db)
    header_options = get_header_revision_options(revision_config)
    revisions_enabled = header_revisions_enabled(header_options)

    revision_id = current.get("revision_id")
    new_revision_id = None
    patch_change_kind = payload.revision_change_kind or _infer_header_change_kind_from_patch(patch)
    if patch_change_kind in {"design", "both"}:
        _require_design_write(user)
    if revisions_enabled:
        current_data = _build_header_revision_snapshot(
            current,
            include_content=header_options["include_content"],
            include_design=header_options["include_design"],
        )
        next_doc = deepcopy(current)
        next_doc.update(patch)
        next_data = _build_header_revision_snapshot(
            next_doc,
            include_content=header_options["include_content"],
            include_design=header_options["include_design"],
        )
        if not snapshots_equal(current_data, next_data):
            effective_change_kind = resolve_effective_change_kind(
                current_data=current_data,
                next_data=next_data,
                parse_snapshot=_parse_header_revision_snapshot,
                requested_kind=patch_change_kind,
            )
            new_revision_id = await push_revision_entry(
                db["revisions"],
                entity_type="header",
                entity_id=header_id,
                current_data=current_data,
                revision_id=revision_id,
                saved_by=user.username,
                change_kind=effective_change_kind,
                reverted_from_saved_at=payload.revision_reverted_from_saved_at,
            )

    patch["revision_id"] = new_revision_id or revision_id
    patch["updated_at"] = datetime.utcnow()

    doc = await headers.find_one_and_update(
        {"_id": ObjectId(header_id)},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    try:
        await sync_generated_item_page_review_overrides_for_saved_targets(
            db,
            collection="header",
            document_id=header_id,
            saved_doc=doc,
            updated_paths=set(patch.keys()),
        )
    except Exception:
        logger.warning(
            "generated_item_page.review_override_header_sync_failed header_id=%s",
            header_id,
            exc_info=True,
        )
    return _format_header_response(doc)


async def _build_unused_headers_query(db) -> dict:
    pages = db["pages"]
    page_header_ids = await pages.distinct("header_id", {"header_id": {"$nin": [None, ""]}})
    used_header_oids = []
    for header_id in page_header_ids:
        header_id_str = str(header_id or "").strip()
        if ObjectId.is_valid(header_id_str):
            used_header_oids.append(ObjectId(header_id_str))

    q: dict = {"shared": {"$ne": True}}
    if used_header_oids:
        q["_id"] = {"$nin": used_header_oids}
    return q


@router.get(
    "/unused/count",
    dependencies=[Depends(require_permission("content:write"))],
)
async def count_unused_headers():
    """Count headers that are not shared and are not referenced by any page."""
    db = _db()
    q = await _build_unused_headers_query(db)
    count = await db["headers"].count_documents(q)
    return {"count": count}


@router.delete(
    "/unused",
    dependencies=[Depends(require_permission("content:write"))],
)
async def delete_unused_headers():
    """Delete headers that are not shared and are not referenced by any page."""
    db = _db()
    headers = db["headers"]
    revisions = db["revisions"]
    pages = db["pages"]

    q = await _build_unused_headers_query(db)

    candidates = await headers.find(q, {"_id": 1}).to_list(length=None)
    header_oids = [doc["_id"] for doc in candidates]
    if not header_oids:
        return {"deleted_count": 0, "deleted_ids": []}

    deleted_ids: list[str] = []
    for header_oid in header_oids:
        header_id = str(header_oid)
        if await pages.find_one({"header_id": header_id}, {"_id": 1}):
            continue
        deleted = await headers.find_one_and_delete(
            {"_id": header_oid, "shared": {"$ne": True}},
            projection={"_id": 1},
        )
        if deleted:
            deleted_ids.append(header_id)

    if deleted_ids:
        await revisions.delete_many({"entity_type": "header", "entity_id": {"$in": deleted_ids}})

    return {"deleted_count": len(deleted_ids), "deleted_ids": deleted_ids}


@router.delete(
    "/{header_id}",
    dependencies=[Depends(require_permission("content:write"))],
)
async def delete_header(header_id: str):
    """Delete a header and its revision document."""
    db = _db()
    headers = db["headers"]
    revisions = db["revisions"]
    pages = db["pages"]

    page_using_header = await pages.find_one({"header_id": header_id})
    if page_using_header:
        raise HTTPException(
            400,
            f"Cannot delete header: it is used by page '{page_using_header.get('slug')}'",
        )

    res = await headers.delete_one({"_id": ObjectId(header_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Header not found")

    await revisions.delete_one({"entity_type": "header", "entity_id": header_id})

    return {"ok": True}


# -------------------------
# Undo/Redo endpoints
# -------------------------


@router.get("/{header_id}/revisions")
async def list_header_revisions(
    header_id: str,
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    """List header revisions for history UI (current + history + future metadata)."""
    db = _db()
    headers = db["headers"]
    revisions = db["revisions"]

    header = await headers.find_one({"_id": ObjectId(header_id)})
    if not header:
        return {
            "enabled": False,
            "current": None,
            "history": [],
            "future": [],
            "options": {
                "include_content": False,
                "include_design": False,
            },
        }

    revision_config = await get_or_create_revision_config(db)
    header_options = get_header_revision_options(revision_config)
    if not header_revisions_enabled(header_options):
        return {
            "enabled": False,
            "current": None,
            "history": [],
            "future": [],
            "options": {
                "include_content": bool(header_options.get("include_content")),
                "include_design": bool(header_options.get("include_design")),
            },
        }

    revision_doc = await revisions.find_one({"entity_type": "header", "entity_id": header_id})
    current_data = _build_header_revision_snapshot(
        header,
        include_content=bool(header_options["include_content"]),
        include_design=bool(header_options["include_design"]),
    )
    history_payload = build_revision_history_payload(
        revision_doc=revision_doc,
        current_data=current_data,
        entity_updated_at=header.get("updated_at"),
        parse_snapshot=_parse_header_revision_snapshot,
        max_history=REVISION_HISTORY_LIMIT,
    )

    return {
        "enabled": True,
        "current": history_payload["current"],
        "history": history_payload["history"],
        "future": history_payload["future"],
        "options": {
            "include_content": bool(header_options.get("include_content")),
            "include_design": bool(header_options.get("include_design")),
        },
    }


@router.get("/{header_id}/revisions/status", response_model=RevisionStatusResponse)
async def get_revision_status(
    header_id: str,
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    """Get undo/redo status for a header."""
    db = _db()
    revisions = db["revisions"]

    revision_config = await get_or_create_revision_config(db)
    header_options = get_header_revision_options(revision_config)
    if not header_revisions_enabled(header_options):
        return RevisionStatusResponse(
            enabled=False,
            can_undo=False,
            can_redo=False,
            history_count=0,
            future_count=0,
        )

    doc = await revisions.find_one({"entity_type": "header", "entity_id": header_id})
    if not doc:
        return RevisionStatusResponse(
            can_undo=False, can_redo=False, history_count=0, future_count=0
        )

    content_history = doc.get("content_history", [])
    design_history = doc.get("design_history", [])
    content_future = doc.get("content_future", [])
    design_future = doc.get("design_future", [])
    history_count = len(content_history) + len(design_history)
    future_count = len(content_future) + len(design_future)

    return RevisionStatusResponse(
        can_undo=history_count > 0,
        can_redo=future_count > 0,
        history_count=history_count,
        future_count=future_count,
        last_saved_by=doc.get("last_saved_by") or "unknown",
        last_saved_at=doc.get("last_saved_at"),
    )


@router.post(
    "/{header_id}/undo",
    response_model=HeaderResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def undo_header(
    header_id: str,
    user: KeycloakUser = Depends(get_current_user),
):
    """Undo the last change to a header."""
    db = _db()
    headers = db["headers"]
    revisions = db["revisions"]

    current = await headers.find_one({"_id": ObjectId(header_id)})
    if not current:
        raise HTTPException(404, "Header not found")

    revision_config = await get_or_create_revision_config(db)
    header_options = get_header_revision_options(revision_config)
    if not header_revisions_enabled(header_options):
        raise HTTPException(400, "Header revisions are disabled for this header type")

    revision_doc = await revisions.find_one(
        {"entity_type": "header", "entity_id": header_id}
    )
    if not revision_doc or not revision_doc.get("history"):
        raise HTTPException(400, "Nothing to undo")

    history = revision_doc["history"]
    future = revision_doc.get("future", [])

    prev_entry = history.pop()
    prev_content, prev_design = _parse_header_revision_snapshot(prev_entry.get("data", {}))
    prev_change_kind = prev_entry.get("change_kind")
    if prev_change_kind not in {"content", "design", "both"}:
        if isinstance(prev_content, dict) and isinstance(prev_design, dict):
            prev_change_kind = "both"
        elif isinstance(prev_design, dict):
            prev_change_kind = "design"
        elif isinstance(prev_content, dict):
            prev_change_kind = "content"
        else:
            prev_change_kind = None
    if prev_change_kind in {"design", "both"}:
        _require_design_write(user)

    current_data = _build_header_revision_snapshot(
        current,
        include_content=header_options["include_content"],
        include_design=header_options["include_design"],
    )
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

    patch = {"updated_at": datetime.utcnow()}
    if header_options["include_content"] and isinstance(prev_content, dict):
        patch.update(
            {
                "header_type": prev_content.get("header_type", "hero"),
                "enabled_fields": prev_content.get("enabled_fields", ALL_HEADER_FIELDS),
                "background_media_url": prev_content.get("background_media_url"),
                "background_zoom": _safe_float(prev_content.get("background_zoom"), 1.0),
                "background_focal_x": _safe_float(prev_content.get("background_focal_x"), 50.0),
                "background_focal_y": _safe_float(prev_content.get("background_focal_y"), 50.0),
                "background_rotation": _safe_float(prev_content.get("background_rotation"), 0.0),
                "overlay_image_url": prev_content.get("overlay_image_url"),
                "overlay_zoom": _safe_float(prev_content.get("overlay_zoom"), 1.0),
                "overlay_focal_x": _safe_float(prev_content.get("overlay_focal_x"), 50.0),
                "overlay_focal_y": _safe_float(prev_content.get("overlay_focal_y"), 50.0),
                "overlay_rotation": _safe_float(prev_content.get("overlay_rotation"), 0.0),
                "hero_title": prev_content.get("hero_title", {"de": "", "en": ""}),
                "hero_subtitle": prev_content.get("hero_subtitle", {"de": "", "en": ""}),
                "cta_buttons": prev_content.get("cta_buttons", []),
                "admin_notes": prev_content.get("admin_notes"),
                "admin_todos": prev_content.get("admin_todos", []),
            }
        )
    if header_options["include_design"] and isinstance(prev_design, dict):
        patch["design_overrides"] = prev_design.get("design_overrides")

    doc = await headers.find_one_and_update(
        {"_id": ObjectId(header_id)},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    return _format_header_response(doc)


@router.post(
    "/{header_id}/redo",
    response_model=HeaderResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def redo_header(
    header_id: str,
    user: KeycloakUser = Depends(get_current_user),
):
    """Redo a previously undone change to a header."""
    db = _db()
    headers = db["headers"]
    revisions = db["revisions"]

    current = await headers.find_one({"_id": ObjectId(header_id)})
    if not current:
        raise HTTPException(404, "Header not found")

    revision_config = await get_or_create_revision_config(db)
    header_options = get_header_revision_options(revision_config)
    if not header_revisions_enabled(header_options):
        raise HTTPException(400, "Header revisions are disabled for this header type")

    revision_doc = await revisions.find_one(
        {"entity_type": "header", "entity_id": header_id}
    )
    if not revision_doc or not revision_doc.get("future"):
        raise HTTPException(400, "Nothing to redo")

    history = revision_doc.get("history", [])
    future = revision_doc["future"]

    next_entry = future.pop()
    next_content, next_design = _parse_header_revision_snapshot(next_entry.get("data", {}))
    next_change_kind = next_entry.get("change_kind")
    if next_change_kind not in {"content", "design", "both"}:
        if isinstance(next_content, dict) and isinstance(next_design, dict):
            next_change_kind = "both"
        elif isinstance(next_design, dict):
            next_change_kind = "design"
        elif isinstance(next_content, dict):
            next_change_kind = "content"
        else:
            next_change_kind = None
    if next_change_kind in {"design", "both"}:
        _require_design_write(user)

    current_data = _build_header_revision_snapshot(
        current,
        include_content=header_options["include_content"],
        include_design=header_options["include_design"],
    )
    history.append({
        "saved_at": revision_doc.get("last_saved_at") or datetime.utcnow(),
        "saved_by": revision_doc.get("last_saved_by"),
        "data": current_data,
    })

    if len(history) > REVISION_HISTORY_LIMIT:
        history = history[-REVISION_HISTORY_LIMIT:]

    await revisions.update_one(
        {"_id": revision_doc["_id"]},
        {"$set": {
            "history": history,
            "future": future,
            "last_saved_by": next_entry.get("saved_by"),
            "last_saved_at": next_entry.get("saved_at"),
        }},
    )

    patch = {"updated_at": datetime.utcnow()}
    if header_options["include_content"] and isinstance(next_content, dict):
        patch.update(
            {
                "header_type": next_content.get("header_type", "hero"),
                "enabled_fields": next_content.get("enabled_fields", ALL_HEADER_FIELDS),
                "background_media_url": next_content.get("background_media_url"),
                "background_zoom": _safe_float(next_content.get("background_zoom"), 1.0),
                "background_focal_x": _safe_float(next_content.get("background_focal_x"), 50.0),
                "background_focal_y": _safe_float(next_content.get("background_focal_y"), 50.0),
                "background_rotation": _safe_float(next_content.get("background_rotation"), 0.0),
                "overlay_image_url": next_content.get("overlay_image_url"),
                "overlay_zoom": _safe_float(next_content.get("overlay_zoom"), 1.0),
                "overlay_focal_x": _safe_float(next_content.get("overlay_focal_x"), 50.0),
                "overlay_focal_y": _safe_float(next_content.get("overlay_focal_y"), 50.0),
                "overlay_rotation": _safe_float(next_content.get("overlay_rotation"), 0.0),
                "hero_title": next_content.get("hero_title", {"de": "", "en": ""}),
                "hero_subtitle": next_content.get("hero_subtitle", {"de": "", "en": ""}),
                "cta_buttons": next_content.get("cta_buttons", []),
                "admin_notes": next_content.get("admin_notes"),
                "admin_todos": next_content.get("admin_todos", []),
            }
        )
    if header_options["include_design"] and isinstance(next_design, dict):
        patch["design_overrides"] = next_design.get("design_overrides")

    doc = await headers.find_one_and_update(
        {"_id": ObjectId(header_id)},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    return _format_header_response(doc)
