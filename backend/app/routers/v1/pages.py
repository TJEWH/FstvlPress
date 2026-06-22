from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from pymongo import ReturnDocument, UpdateOne

from app.collection_names import (
    BLOG_CONFIG_COLLECTION,
    BLOG_SHARED_COLLECTION,
    CSS_SNIPPETS_COLLECTION,
    DESIGN_CONFIG_COLLECTION,
    DESIGN_EDITOR_CONFIG_COLLECTION,
    MEDIA_CONFIG_COLLECTION,
    DESIGN_VERSIONS_COLLECTION,
    PAGE_HIT_DAYS_COLLECTION,
    PROGRAM_SHARED_COLLECTION,
    SECTIONS_COLLECTION,
    TEMPLATE_PAGES_COLLECTION,
    TEMPLATE_SECTIONS_COLLECTION,
)
from app.db import get_client
from app.deps import get_current_user, get_optional_user, require_permission
from app.font_cache import resolve_font_cache_for_design
from app.responsive_config import normalize_responsive_config, responsive_media_query
from app.security import KeycloakUser
from app.settings import settings
from app.models.cms import (
    PageCreate,
    PageUpdate,
    PageSectionRef,
    PageResponse,
    PageFullResponse,
    HeaderCreate,
    HeaderResponse,
    SectionCreate,
)
from app.sitemap import (
    find_active_redirect_doc,
    get_navigation_links_config,
    increment_redirect_anonymous_hit_count,
    normalize_internal_path,
    request_has_auth_credentials,
    upsert_generated_gone_redirect_for_slug,
    upsert_generated_redirects_for_slug_mapping,
)
from app.models.sections.sections import get_default_type_data, get_default_title
from app.models.sections.normalization import normalize_section_description_payload
from app import program_catalog
from app.template_sync import (
    build_template_key_for_section,
    normalize_template_name,
    normalize_slug,
    normalize_section_integration_mapping,
    normalize_section_template_doc,
    parse_page_template_path,
    resolve_global_published_design_snapshot,
    slugify_segment,
    sync_generated_item_page_integration_page_slug,
    sync_generated_item_page_from_template_state,
    sync_generated_item_page_review_overrides_for_saved_targets,
)
from app.revisioning import (
    REVISION_HISTORY_LIMIT,
    as_object_id,
    build_section_revision_snapshot,
    capture_faq_shared_content,
    capture_program_shared_content,
    capture_section_design_state,
    get_or_create_revision_config,
    get_header_revision_options,
    get_section_revision_options,
    header_revisions_enabled,
    normalize_saved_at_label,
    push_revision_entry,
    resolve_effective_change_kind,
    section_revision_history_enabled,
    snapshots_equal,
    snapshot_document,
)
from app.media_responsive import (
    collect_raster_image_urls_from_payload,
    enrich_raster_payload_with_asset_docs,
    fetch_asset_docs_by_urls,
)
from app.routers.v1.admin_media import MEDIA_CONFIG_KEY, _normalize_config as normalize_media_config
from app.public_cache import (
    get_or_set_ttl_cache,
    get_ttl_cache,
    set_public_cache_headers,
)
from app.section_structure import (
    apply_section_order_from_structure,
    build_section_structure_from_container_membership,
    extract_container_membership_from_structure,
    resolve_section_structure,
    strip_legacy_container_override,
)


def _format_datetime_response(dt) -> str | None:
    """Format datetime for API response, ensuring UTC timezone."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


router = APIRouter(prefix="/pages", tags=["pages"])
logger = logging.getLogger(__name__)

SECTION_REVISION_EXCLUDE_KEYS = frozenset(
    {"_id", "revision_id", "created_at", "updated_at"}
)
ADMIN_CONFIG_KEY = DESIGN_EDITOR_CONFIG_COLLECTION
TEMPLATE_STYLE_LOCK_ERROR = "Style is controlled by linked page template; page/header/section design overrides are locked"
PROGRAM_SHARED_DOC_ID = "shared"


class MoveSubtreePayload(BaseModel):
    target_parent_slug: str | None = None


class RenamePagePayload(BaseModel):
    new_slug: str = Field(
        min_length=1,
        max_length=200,
        pattern=r"^[a-z0-9]+(?:[-/][a-z0-9]+)*$",
    )


class PublicPageAvailabilityRequest(BaseModel):
    slugs: list[str] = Field(default_factory=list)


class PublicPageAvailabilityResponse(BaseModel):
    availability_by_slug: dict[str, bool] = Field(default_factory=dict)


class PageStatusAvailabilityRequest(BaseModel):
    slugs: list[str] = Field(default_factory=list)


class PageStatusAvailabilityEntry(BaseModel):
    exists: bool = False
    status: str = "hidden"
    effective_status: str = "hidden"
    is_visible: bool = False


class PageStatusAvailabilityResponse(BaseModel):
    status_by_slug: dict[str, PageStatusAvailabilityEntry] = Field(default_factory=dict)


def _db():
    return get_client()[settings.mongo_db]


def _safe_object_id(value: str | ObjectId | None) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return None


async def _resolve_unique_page_slug(
    pages_coll,
    desired_slug: str,
    *,
    exclude_page_id: ObjectId | None = None,
) -> str:
    base_slug = normalize_slug(desired_slug)
    candidate = base_slug
    counter = 2

    while True:
        query: dict[str, object] = {"slug": candidate}
        if exclude_page_id is not None:
            query["_id"] = {"$ne": exclude_page_id}
        existing = await pages_coll.find_one(query, {"_id": 1})
        if not existing:
            return candidate
        candidate = f"{base_slug}-{counter}"
        counter += 1


def _is_public_or_under_construction(status: str) -> bool:
    return status in {"published", "under_construction"}


def _is_hidden_like_page_status(status: str) -> bool:
    return status in {"hidden", "init"}


def _extract_page_title_for_slug(page_payload: dict | None) -> str:
    payload = page_payload if isinstance(page_payload, dict) else {}
    title = payload.get("title") if isinstance(payload.get("title"), dict) else {}
    return str(title.get("de") or title.get("en") or "").strip()


async def _finalize_pending_template_item_slug_on_publish(
    db,
    *,
    current_page: dict,
    patch: dict,
    provided_fields: set[str],
) -> tuple[str, str] | None:
    next_status = _normalize_page_status(
        patch.get("status"),
        fallback=_normalize_page_status(current_page.get("status"), fallback="hidden"),
    )
    has_explicit_public_status_change = (
        "status" in provided_fields and _is_public_or_under_construction(next_status)
    )
    has_publish_schedule = (
        "publish_at" in provided_fields and patch.get("publish_at") is not None
    )
    if not has_explicit_public_status_change and not has_publish_schedule:
        return None

    pending_canonical_slug = str(
        current_page.get("template_pending_canonical_slug") or ""
    ).strip()
    if not pending_canonical_slug:
        return None

    next_title_payload = (
        patch.get("title")
        if isinstance(patch.get("title"), dict)
        else current_page.get("title")
        if isinstance(current_page.get("title"), dict)
        else {}
    )
    title_for_slug = _extract_page_title_for_slug({"title": next_title_payload})
    if not title_for_slug:
        raise HTTPException(
            status_code=400,
            detail="Set a page title before publishing or scheduling item pages so a public slug can be finalized.",
        )

    source_type = str(current_page.get("template_source_type") or "").strip().lower()
    if source_type == "blog":
        # Blog item pages should promote from temporary date slug to the
        # configured blog slug-source canonical path on first publish.
        desired_canonical_slug = normalize_slug(pending_canonical_slug)
    else:
        title_slug = normalize_slug(title_for_slug).split("/")[-1]
        if not title_slug:
            raise HTTPException(
                status_code=400,
                detail="Page title must include letters or numbers before publishing item pages.",
            )
        parent_route = str(current_page.get("template_parent_route") or "").strip().strip("/")
        desired_canonical_slug = normalize_slug(
            f"{parent_route}/{title_slug}" if parent_route else title_slug
        )

    pages_coll = db["pages"]
    finalized_slug = await _resolve_unique_page_slug(
        pages_coll,
        desired_canonical_slug,
        exclude_page_id=current_page.get("_id"),
    )
    current_slug = str(current_page.get("slug") or "").strip()
    patch["slug"] = finalized_slug
    patch["template_pending_canonical_slug"] = None
    return current_slug, finalized_slug


async def _sync_template_source_link_for_page_slug(db, page_doc: dict) -> None:
    if not isinstance(page_doc, dict):
        return
    slug = str(page_doc.get("slug") or "").strip()
    if not slug:
        return

    source_type = str(page_doc.get("template_source_type") or "").strip().lower()
    source_id = str(page_doc.get("template_source_id") or "").strip()
    if not source_type or not source_id:
        return

    try:
        await sync_generated_item_page_integration_page_slug(db, page_doc)
    except Exception:
        logger.warning(
            "generated_item_page.integration_page_slug_sync_failed slug=%s",
            slug,
            exc_info=True,
        )

    now = datetime.utcnow()
    if source_type == "blog":
        oid = _safe_object_id(source_id)
        if oid is None:
            return
        await db[BLOG_SHARED_COLLECTION].update_one(
            {"_id": oid},
            {"$set": {"page_slug": slug, "updated_at": now}},
        )
        return

    if source_type == "program_stage" and source_id.startswith("program:stage:"):
        item_id = str(source_id.removeprefix("program:stage:") or "").strip()
        if not item_id:
            return
        await db[PROGRAM_SHARED_COLLECTION].update_one(
            {"_id": PROGRAM_SHARED_DOC_ID, "stages.id": item_id},
            {
                "$set": {
                    "stages.$.page_slug": slug,
                    "stages.$.item_url": f"/{slug}",
                    "updated_at": now,
                }
            },
        )
        return

    if source_type == "program_gig" and source_id.startswith("program:gig:"):
        item_id = str(source_id.removeprefix("program:gig:") or "").strip()
        if not item_id:
            return
        await program_catalog.update_program_gig_link(
            db,
            item_id,
            slug=slug,
            item_url=f"/{slug}",
        )
        return

    if source_type == "tiles" and source_id.startswith("tiles:"):
        try:
            _, section_id, tile_id = source_id.split(":", 2)
        except ValueError:
            return
        section_oid = _safe_object_id(section_id)
        if section_oid is None or not tile_id:
            return
        await db[SECTIONS_COLLECTION].update_one(
            {"_id": section_oid, "type_data.tiles.id": tile_id},
            {
                "$set": {
                    "type_data.tiles.$.page_slug": slug,
                    "updated_at": now,
                }
            },
        )


def _normalize_page_sections_and_structure(
    sections: list[dict] | None,
    section_structure: list[dict] | None,
) -> tuple[list[dict], list[dict]]:
    refs = [deepcopy(ref) for ref in (sections if isinstance(sections, list) else []) if isinstance(ref, dict)]
    refs.sort(key=lambda ref: int(ref.get("order", 0) or 0))

    for ref in refs:
        overrides = strip_legacy_container_override(ref.get("design_overrides"))
        if overrides is None:
            ref.pop("design_overrides", None)
        else:
            ref["design_overrides"] = overrides

    ordered_ids = [str(ref.get("section_id") or "").strip() for ref in refs if str(ref.get("section_id") or "").strip()]
    normalized_structure = resolve_section_structure(
        section_structure,
        ordered_ids,
    )
    normalized_refs = apply_section_order_from_structure(
        refs,
        normalized_structure,
        section_id_field="section_id",
    )
    return normalized_refs, normalized_structure


def _safe_float(value, default: float) -> float:
    try:
        parsed = float(value)
        if parsed != parsed:  # NaN guard
            return default
        return parsed
    except Exception:
        return default


def _wrap_css_snippet_for_media_scope(
    css_text: str,
    media_scope: str | None,
    responsive_config: dict | None = None,
) -> str:
    css = str(css_text or "").strip()
    if not css:
        return ""
    query = responsive_media_query(media_scope, responsive_config)
    if query:
        return f"@media {query} {{\n{css}\n}}"
    return css


async def _build_section_template_custom_css(
    db,
    *,
    section_type: str,
    template_name: str,
) -> str:
    template_key = build_template_key_for_section(section_type, template_name)
    admin_doc = await db[DESIGN_EDITOR_CONFIG_COLLECTION].find_one(
        {"key": ADMIN_CONFIG_KEY},
        {"responsive": 1},
    )
    responsive_config = admin_doc.get("responsive") if isinstance(admin_doc, dict) else None
    cursor = (
        db[CSS_SNIPPETS_COLLECTION]
        .find(
            {
                "scope": "template",
                "template_key": template_key,
                "active": {"$ne": False},
            }
        )
        .sort("created_at", 1)
    )
    snippets = await cursor.to_list(length=500)
    chunks: list[str] = []
    for snippet in snippets:
        css_block = _wrap_css_snippet_for_media_scope(
            snippet.get("css"),
            snippet.get("media_scope"),
            responsive_config,
        )
        if css_block:
            chunks.append(css_block)
    return "\n\n".join(chunks).strip()


def _is_template_style_linked(page_doc: dict | None) -> bool:
    if not isinstance(page_doc, dict):
        return False
    if page_doc.get("template_style_linked") is True:
        return True
    return bool(str(page_doc.get("template_style_ref") or "").strip())


def _is_template_style_locked(page_doc: dict | None) -> bool:
    if not isinstance(page_doc, dict):
        return False
    if not _is_template_style_linked(page_doc):
        return False
    return page_doc.get("template_style_lock") is True


def _ensure_template_style_not_locked_for_design(page_doc: dict | None) -> None:
    if _is_template_style_locked(page_doc):
        raise HTTPException(409, TEMPLATE_STYLE_LOCK_ERROR)


async def _get_template_style_design_settings_for_page(
    db,
    page_doc: dict | None,
) -> dict | None:
    if not _is_template_style_linked(page_doc):
        return None
    template_ref = str(page_doc.get("template_style_ref") or "").strip().strip("/")
    if not template_ref:
        return None

    try:
        template_name, parent_route = parse_page_template_path(template_ref)
    except ValueError:
        return None

    template_doc = await db[TEMPLATE_PAGES_COLLECTION].find_one(
        {
            "template_name": template_name,
            "parent_route": parent_route,
        }
    )
    if not isinstance(template_doc, dict):
        return None

    published = template_doc.get("template_design_published")
    current = template_doc.get("template_design_current")
    source = published if isinstance(published, dict) else current if isinstance(current, dict) else None
    if not isinstance(source, dict):
        base_design, base_version_id = await resolve_global_published_design_snapshot(db)
        source = deepcopy(base_design) if isinstance(base_design, dict) else {}
        now = datetime.utcnow()
        await db[TEMPLATE_PAGES_COLLECTION].update_one(
            {"_id": template_doc["_id"]},
            {
                "$set": {
                    "template_design_current": deepcopy(source),
                    "template_design_published": deepcopy(source),
                    "template_design_initialized_from_global_version_id": base_version_id,
                    "template_design_updated_at": now,
                    "template_design_published_at": now,
                    "page_design_overrides": None,
                    "updated_at": now,
                }
            },
        )
    admin_doc = await db[DESIGN_EDITOR_CONFIG_COLLECTION].find_one({"key": ADMIN_CONFIG_KEY})
    source_with_context = _inject_selected_units_from_admin_config(source, admin_doc)
    formatted = _format_public_design_payload(source_with_context)
    enriched = await _enrich_payload_with_asset_media(db, formatted)
    return await _enrich_design_payload_with_font_cache(enriched)


def _parse_design_override_payload(payload: dict | None) -> tuple[dict | None, str | None]:
    if not isinstance(payload, dict):
        return None, None
    if "overrides" in payload or "revision_reverted_from_saved_at" in payload:
        raw_overrides = payload.get("overrides")
        normalized_override = raw_overrides if isinstance(raw_overrides, dict) else None
        reverted_from_saved_at = normalize_saved_at_label(
            payload.get("revision_reverted_from_saved_at")
        )
        return normalized_override, reverted_from_saved_at
    return payload, None


def _format_header_response(doc: dict, *, include_admin_fields: bool = False) -> dict:
    """Format a header document for the response."""
    enabled = doc.get("enabled_fields", ["title", "subtitle", "cta_buttons", "overlay_image", "background_image"])
    result = {
        "id": str(doc["_id"]),
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
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }
    if include_admin_fields:
        result["admin_notes"] = doc.get("admin_notes")
        result["admin_todos"] = doc.get("admin_todos", [])
    return result


def _can_view_hidden_content(user: KeycloakUser | None) -> bool:
    """Return True when request is authenticated with content write/admin access."""
    if not user:
        return False
    permissions = set(user.permissions or set())
    return bool({"content:write", "content:admin"} & permissions)


def _require_design_write(user: KeycloakUser) -> None:
    if user.has_permission("design:write"):
        return
    raise HTTPException(
        status_code=403,
        detail="Missing required permissions: design:write",
    )


def _parse_header_revision_snapshot(data: dict) -> tuple[dict | None, dict | None]:
    if not isinstance(data, dict):
        return None, None
    content = data.get("content")
    design = data.get("design")
    return (
        deepcopy(content) if isinstance(content, dict) else None,
        deepcopy(design) if isinstance(design, dict) else None,
    )


def _resolve_effective_header_change_kind(
    current_data: dict,
    next_data: dict,
    requested_kind: str | None,
) -> str | None:
    return resolve_effective_change_kind(
        current_data=current_data,
        next_data=next_data,
        parse_snapshot=_parse_header_revision_snapshot,
        requested_kind=requested_kind,
    )


MENU_ITEMS_FETCH_LIMIT = 5000
PUBLIC_PAGE_BUNDLE_CACHE_SECONDS = 60
PUBLIC_PAGE_PARTS_CACHE_SECONDS = 300
PUBLIC_PROGRAM_BUNDLE_CACHE_SECONDS = 60


def _path_from_slug(slug: str | None) -> str:
    value = str(slug or "").strip()
    if not value or value == "landing":
        return "/"
    return f"/{value}"


def _format_internal_navigation_item(page_doc: dict) -> dict:
    item = _format_page_response(page_doc)
    item["kind"] = "internal"
    item["external_url"] = None
    item["external_icon"] = None
    item["external_label"] = None
    item["link_target"] = {
        "type": "internal",
        "slug": item.get("slug"),
        "path": _path_from_slug(item.get("slug")),
    }
    return item


def _format_external_navigation_item(link_doc: dict) -> dict:
    label = link_doc.get("label") if isinstance(link_doc.get("label"), dict) else None
    icon = str(link_doc.get("icon") or "").strip() or None
    return {
        "id": str(link_doc.get("id") or ""),
        "kind": "external",
        "slug": None,
        "title": {"de": "", "en": ""},
        "menu_title": None,
        "menu_parent_title": None,
        "url": str(link_doc.get("url") or "").strip(),
        "label": label,
        "icon": icon,
        "order": int(link_doc.get("order", 0) or 0),
        "is_visible": True,
        "external_url": str(link_doc.get("url") or "").strip(),
        "external_icon": icon,
        "external_label": label,
        "link_target": {
            "type": "external",
            "url": str(link_doc.get("url") or "").strip(),
        },
    }


async def _get_navigation_external_items(location: str) -> list[dict]:
    config = await get_navigation_links_config(_db())
    key = "nav_external_links" if location == "menu" else "footer_external_links"
    links = config.get(key) if isinstance(config, dict) else []
    raw_links = links if isinstance(links, list) else []
    return [_format_external_navigation_item(link) for link in raw_links]


async def _get_menu_internal_items(*, include_hidden: bool) -> list[dict]:
    pages = _db()["pages"]
    docs = await pages.find({"in_menu": True}).sort([("menu_order", 1), ("slug", 1)]).to_list(length=MENU_ITEMS_FETCH_LIMIT)
    result = []
    for doc in docs:
        if not include_hidden and not _is_page_visible(doc):
            continue
        result.append(_format_internal_navigation_item(doc))
    return result


async def _get_footer_internal_items(*, include_hidden: bool) -> list[dict]:
    pages = _db()["pages"]
    docs = await pages.find({"in_footer": True}).sort([("footer_order", 1), ("slug", 1)]).to_list(length=MENU_ITEMS_FETCH_LIMIT)
    result = []
    for doc in docs:
        if not include_hidden and not _is_page_visible(doc):
            continue
        result.append(_format_internal_navigation_item(doc))
    return result


async def _get_public_menu_items() -> list[dict]:
    """Return publicly reachable menu items for public page navigation."""
    cache_key = "public:menu-items"

    async def build_menu_items() -> list[dict]:
        internal_items = await _get_menu_internal_items(include_hidden=False)
        external_items = await _get_navigation_external_items("menu")
        return internal_items + external_items

    return await get_or_set_ttl_cache(
        cache_key,
        PUBLIC_PAGE_PARTS_CACHE_SECONDS,
        build_menu_items,
    )


async def _get_public_footer_items() -> list[dict]:
    """Return publicly reachable footer items for public footer links."""
    cache_key = "public:footer-items"

    async def build_footer_items() -> list[dict]:
        internal_items = await _get_footer_internal_items(include_hidden=False)
        external_items = await _get_navigation_external_items("footer")
        return external_items + internal_items

    return await get_or_set_ttl_cache(
        cache_key,
        PUBLIC_PAGE_PARTS_CACHE_SECONDS,
        build_footer_items,
    )


def _normalize_public_slug_input(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw or raw == "/":
        return "landing"
    normalized = raw.split("?", 1)[0].split("#", 1)[0].strip()
    normalized = normalized.replace("\\", "/")
    normalized = normalized.strip("/")
    return normalized or "landing"


@router.post(
    "/public-availability",
    response_model=PublicPageAvailabilityResponse,
)
async def get_public_pages_availability(payload: PublicPageAvailabilityRequest):
    """
    Resolve whether each slug is publicly available without surfacing 404 errors.

    Returns `false` for:
    - missing pages
    - hidden pages
    - under_construction pages
    """
    requested = payload.slugs if isinstance(payload.slugs, list) else []
    ordered_slugs: list[str] = []
    seen: set[str] = set()
    for raw_slug in requested[:500]:
        slug = _normalize_public_slug_input(raw_slug)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        ordered_slugs.append(slug)

    if not ordered_slugs:
        return PublicPageAvailabilityResponse(availability_by_slug={})

    pages = _db()["pages"]
    docs = await pages.find(
        {"slug": {"$in": ordered_slugs}},
        {
            "slug": 1,
            "status": 1,
            "publish_at": 1,
            "unpublish_at": 1,
        },
    ).to_list(length=len(ordered_slugs))
    docs_by_slug = {str(doc.get("slug") or "").strip(): doc for doc in docs}

    availability_by_slug: dict[str, bool] = {}
    for slug in ordered_slugs:
        doc = docs_by_slug.get(slug)
        if not doc:
            availability_by_slug[slug] = False
            continue
        availability_by_slug[slug] = _compute_effective_status(doc) == "published"

    return PublicPageAvailabilityResponse(availability_by_slug=availability_by_slug)


@router.post(
    "/statuses",
    response_model=PageStatusAvailabilityResponse,
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_pages_statuses(payload: PageStatusAvailabilityRequest):
    requested = payload.slugs if isinstance(payload.slugs, list) else []
    ordered_slugs: list[str] = []
    seen: set[str] = set()
    for raw_slug in requested[:500]:
        slug = _normalize_public_slug_input(raw_slug)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        ordered_slugs.append(slug)

    if not ordered_slugs:
        return PageStatusAvailabilityResponse(status_by_slug={})

    pages = _db()["pages"]
    docs = await pages.find(
        {"slug": {"$in": ordered_slugs}},
        {
            "slug": 1,
            "status": 1,
            "publish_at": 1,
            "unpublish_at": 1,
        },
    ).to_list(length=len(ordered_slugs))
    docs_by_slug = {str(doc.get("slug") or "").strip(): doc for doc in docs}

    status_by_slug: dict[str, PageStatusAvailabilityEntry] = {}
    for slug in ordered_slugs:
        doc = docs_by_slug.get(slug)
        if not doc:
            status_by_slug[slug] = PageStatusAvailabilityEntry(
                exists=False,
                status="hidden",
                effective_status="hidden",
                is_visible=False,
            )
            continue

        status = _normalize_page_status(doc.get("status"), fallback="hidden")
        effective_status = _compute_effective_status(doc)
        status_by_slug[slug] = PageStatusAvailabilityEntry(
            exists=True,
            status=status,
            effective_status=effective_status,
            is_visible=effective_status == "published",
        )

    return PageStatusAvailabilityResponse(status_by_slug=status_by_slug)


@router.post(
    "",
    response_model=PageResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def create_page(payload: PageCreate):
    db = _db()
    pages = db["pages"]
    headers = db["headers"]
    now = datetime.utcnow()

    # Verify header exists if header_id is provided
    header_id = payload.header_id
    has_header = payload.has_header

    if header_id:
        header_doc = await headers.find_one({"_id": ObjectId(header_id)})
        if not header_doc:
            raise HTTPException(404, "Header not found")
        has_header = True

    template_style_ref = str(payload.template_style_ref or "").strip() or None
    template_style_linked = bool(payload.template_style_linked or template_style_ref)
    template_style_lock = bool(payload.template_style_lock) if template_style_linked else False
    # Convert sections list to dicts and normalize structure/order.
    sections_list = [s.model_dump() for s in payload.sections]
    if template_style_linked:
        for section_ref in sections_list:
            if isinstance(section_ref, dict):
                section_ref.pop("design_overrides", None)
    sections_list, normalized_section_structure = _normalize_page_sections_and_structure(
        sections_list,
        payload.section_structure,
    )

    doc = {
        "slug": payload.slug,
        "title": payload.title.model_dump(),
        "has_header": has_header,
        "header_id": header_id,
        "sections": sections_list,
        "section_structure": normalized_section_structure,
        "status": _normalize_page_status(payload.status),
        "publish_at": payload.publish_at,
        "unpublish_at": payload.unpublish_at,
        "in_menu": payload.in_menu,
        "in_footer": payload.in_footer,
        "hide_in_admin_sitemap": payload.hide_in_admin_sitemap,
        "hide_from_sitemap": payload.hide_from_sitemap,
        "hide_subtree_from_sitemap": payload.hide_subtree_from_sitemap,
        "sitemap_priority": payload.sitemap_priority,
        "sitemap_changefreq": payload.sitemap_changefreq,
        "generated_from_blog": payload.generated_from_blog,
        "menu_title": payload.menu_title.model_dump() if payload.menu_title else None,
        "menu_parent_title": payload.menu_parent_title.model_dump() if payload.menu_parent_title else None,
        "menu_show_as_top_level": payload.menu_show_as_top_level,
        "menu_order": payload.menu_order,
        "footer_order": payload.footer_order,
        "redirect_to": payload.redirect_to,
        "page_design_overrides": None if template_style_linked else payload.page_design_overrides,
        "template_style_ref": template_style_ref,
        "template_style_linked": template_style_linked,
        "template_style_lock": template_style_lock,
        "anonymous_hit_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    try:
        res = await pages.insert_one(doc)
    except Exception:
        raise HTTPException(409, "Slug already exists")

    doc["_id"] = str(res.inserted_id)
    return _format_page_response(doc)


@router.get(
    "",
    response_model=list[PageResponse],
    dependencies=[Depends(require_permission("content:read"))],
)
async def list_pages(
    limit: int = Query(default=30, ge=1, le=5000),
    cursor: str | None = Query(
        default=None, description="ISO datetime string of updated_at for pagination"
    ),
    include_hidden: bool = Query(default=False),
    user: KeycloakUser = Depends(get_current_user),
):
    pages = _db()["pages"]
    can_view_hidden = _can_view_hidden_content(user)
    if include_hidden and not can_view_hidden:
        raise HTTPException(403, "Viewing hidden pages requires authentication")

    q: dict = {}
    if cursor:
        q["updated_at"] = {"$lt": datetime.fromisoformat(cursor)}

    docs = await pages.find(q).sort("updated_at", -1).limit(limit).to_list(length=limit)
    if not include_hidden:
        docs = [doc for doc in docs if _is_page_visible(doc)]

    return [_format_page_response(doc) for doc in docs]


@router.get(
    "/menu/items",
    response_model=list[dict],
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_menu_items(
    include_hidden: bool = Query(default=False),
    user: KeycloakUser = Depends(get_current_user),
):
    """
    Get all pages marked for inclusion in the navigation menu.
    
    By default, only returns pages that are currently publicly reachable
    (published or under_construction, including schedule-triggered visibility).
    
    Set include_hidden=true to include all menu items regardless of visibility
    (useful for admin preview).
    """
    if include_hidden and not _can_view_hidden_content(user):
        raise HTTPException(403, "Viewing hidden pages requires authentication")
    internal_items = await _get_menu_internal_items(include_hidden=include_hidden)
    external_items = await _get_navigation_external_items("menu")
    return internal_items + external_items


@router.get(
    "/footer/items",
    response_model=list[dict],
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_footer_items(
    include_hidden: bool = Query(default=False),
    user: KeycloakUser = Depends(get_current_user),
):
    """
    Get all pages marked for inclusion in footer links.

    By default, only returns pages that are currently publicly reachable
    (published or under_construction, including schedule-triggered visibility).

    Set include_hidden=true to include all footer items regardless of visibility
    (useful for admin preview).
    """
    if include_hidden and not _can_view_hidden_content(user):
        raise HTTPException(403, "Viewing hidden pages requires authentication")
    internal_items = await _get_footer_internal_items(include_hidden=include_hidden)
    external_items = await _get_navigation_external_items("footer")
    return external_items + internal_items


@router.get(
    "/{slug:path}/full",
    response_model=PageFullResponse,
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_page_with_sections(
    slug: str,
    include_hidden: bool = Query(default=False),
    user: KeycloakUser | None = Depends(get_optional_user),
):
    """Get a page with all its sections and header populated.

    Args:
        slug: The page slug
        include_hidden: If False (default), only returns visible sections
    """
    db = _db()
    pages = db["pages"]
    sections_coll = db[SECTIONS_COLLECTION]
    headers_coll = db["headers"]

    page = await pages.find_one({"slug": slug})
    if not page:
        raise HTTPException(404, "Page not found")
    effective_status = _compute_effective_status(page)
    can_view_hidden = _can_view_hidden_content(user)
    if include_hidden and not can_view_hidden:
        raise HTTPException(403, "Viewing hidden sections requires authentication")
    if not can_view_hidden and not _is_page_visible(page):
        raise HTTPException(404, "Page not found")
    hide_public_content = not can_view_hidden and effective_status == "under_construction"

    page_id = str(page["_id"])
    template_style_linked = _is_template_style_linked(page)
    template_style_lock = _is_template_style_locked(page)
    template_style_ref = str(page.get("template_style_ref") or "").strip() or None
    effective_design_settings = await _get_template_style_design_settings_for_page(db, page)

    # Populate header if has_header is true and header_id exists
    header_data = None
    if (not hide_public_content) and page.get("has_header") and page.get("header_id"):
        try:
            header_doc = await headers_coll.find_one({"_id": ObjectId(page["header_id"])})
            if header_doc:
                header_data = _format_header_response(
                    header_doc,
                    include_admin_fields=can_view_hidden,
                )
        except Exception:
            # Invalid header_id, skip header loading
            pass

    # Get section references (with order and visibility)
    section_refs = [] if hide_public_content else page.get("sections", [])

    # Filter by visibility if needed
    if not include_hidden:
        section_refs = [ref for ref in section_refs if ref.get("visible", True)]

    # Sort by order
    section_refs = sorted(section_refs, key=lambda x: x.get("order", 0))
    section_refs, normalized_section_structure = _normalize_page_sections_and_structure(
        section_refs,
        page.get("section_structure"),
    )

    populated_sections = []
    if section_refs:
        # Fetch all referenced sections (skip invalid ObjectIds)
        section_ids = [ref["section_id"] for ref in section_refs if ref.get("section_id")]
        object_ids = []
        for sid in section_ids:
            try:
                object_ids.append(ObjectId(sid))
            except Exception:
                pass
        
        section_docs = await sections_coll.find({"_id": {"$in": object_ids}}).to_list(
            length=500
        ) if object_ids else []

        # Create map for lookup
        sections_map = {}
        for s in section_docs:
            s["_id"] = str(s["_id"])
            s["shared"] = bool(s.get("shared", False))
            # Remove internal revision references from public/admin page payloads.
            s.pop("revision_ids", None)
            s.pop("revision_id", None)
            sections_map[s["_id"]] = s

        # Build populated sections list with order/visibility metadata
        for ref in section_refs:
            section_data = sections_map.get(ref["section_id"])
            if section_data:
                merged = {
                    **section_data,
                    "order": ref.get("order", 0),
                    "visible": ref.get("visible", True),
                    "width_n": ref.get("width_n", 1),
                    "width_d": ref.get("width_d", 1),
                }
                if "limit" in ref:
                    merged["limit"] = ref["limit"]
                if (not template_style_linked) and ref.get("design_overrides"):
                    merged["design_overrides"] = ref["design_overrides"]
                populated_sections.append(merged)

    image_urls: set[str] = set()
    for section in populated_sections:
        if not isinstance(section, dict):
            continue
        type_data = section.get("type_data")
        if isinstance(type_data, dict):
            image_urls.update(collect_raster_image_urls_from_payload(type_data))
    if isinstance(header_data, dict):
        image_urls.update(collect_raster_image_urls_from_payload(header_data))

    if image_urls:
        asset_docs_by_url = await fetch_asset_docs_by_urls(db, image_urls)
        if asset_docs_by_url:
            for section in populated_sections:
                if not isinstance(section, dict):
                    continue
                type_data = section.get("type_data")
                if isinstance(type_data, dict):
                    enrich_raster_payload_with_asset_docs(type_data, asset_docs_by_url)
            if isinstance(header_data, dict):
                enrich_raster_payload_with_asset_docs(header_data, asset_docs_by_url)

    media_fallbacks = await _get_public_media_fallbacks(db)

    # Get schedule times and ensure they're timezone-aware
    now = datetime.now(timezone.utc)
    publish_at = _parse_datetime(page.get("publish_at"))
    unpublish_at = _parse_datetime(page.get("unpublish_at"))
    
    # Clear schedule times only after they've successfully triggered their intended effect:
    # - publish_at: clear only if it triggered AND page is now published
    # - unpublish_at: clear only if it triggered AND page is now hidden (due to unpublish)
    publish_triggered = publish_at and publish_at <= now and effective_status == "published"
    unpublish_triggered = unpublish_at and unpublish_at <= now and effective_status == "hidden"
    
    publish_at_response = None if publish_triggered else _format_datetime_response(publish_at)
    unpublish_at_response = None if unpublish_triggered else _format_datetime_response(unpublish_at)
    
    return {
        "id": page_id,
        "slug": page.get("slug"),
        "title": page.get("title", {"de": "", "en": ""}),
        "has_header": page.get("has_header", False),
        "header_id": page.get("header_id"),
        "header": header_data,
        "sections": populated_sections,
        "section_structure": normalized_section_structure,
        "status": _normalize_page_status(page.get("status")),
        "effective_status": effective_status,
        "is_visible": effective_status == "published",
        "publish_at": publish_at_response,
        "unpublish_at": unpublish_at_response,
        "in_menu": page.get("in_menu", False),
        "in_footer": page.get("in_footer", False),
        "hide_in_admin_sitemap": page.get("hide_in_admin_sitemap", False),
        "hide_from_sitemap": page.get("hide_from_sitemap", False),
        "hide_subtree_from_sitemap": page.get("hide_subtree_from_sitemap", False),
        "sitemap_priority": page.get("sitemap_priority"),
        "sitemap_changefreq": page.get("sitemap_changefreq"),
        "generated_from_blog": page.get("generated_from_blog", False),
        "menu_title": page.get("menu_title"),
        "menu_parent_title": page.get("menu_parent_title"),
        "menu_show_as_top_level": page.get("menu_show_as_top_level", False),
        "menu_order": page.get("menu_order", 0),
        "footer_order": page.get("footer_order", 0),
        "redirect_to": page.get("redirect_to"),
        "section_bg_pinned_start_key": page.get("section_bg_pinned_start_key", ""),
        "section_bg_pinned_end_key": page.get("section_bg_pinned_end_key", ""),
        "page_design_overrides": None if template_style_linked else page.get("page_design_overrides"),
        "template_style_ref": template_style_ref,
        "template_style_linked": template_style_linked,
        "template_style_lock": template_style_lock,
        "template_managed": bool(page.get("template_managed", False)),
        "template_source_type": str(page.get("template_source_type") or "").strip() or None,
        "template_source_id": str(page.get("template_source_id") or "").strip() or None,
        "template_integration_id": str(page.get("template_integration_id") or "").strip() or None,
        "template_integration_item_key": str(page.get("template_integration_item_key") or "").strip() or None,
        "effective_design_settings": effective_design_settings,
        "media_fallbacks": media_fallbacks,
        "created_at": _format_datetime_response(page.get("created_at")),
        "updated_at": _format_datetime_response(page.get("updated_at")),
    }


@router.get(
    "/{slug:path}/sync-from-template/conflicts",
    dependencies=[Depends(require_permission("content:write"))],
)
async def get_page_template_sync_conflicts(slug: str):
    """Check mapped-field conflicts for a generated item page without writing changes."""
    db = _db()
    page = await db["pages"].find_one({"slug": slug})
    if not page:
        raise HTTPException(404, "Page not found")
    if page.get("template_managed") is not True:
        raise HTTPException(400, "Page is not managed by an item-page template")

    try:
        return await sync_generated_item_page_from_template_state(
            db,
            page,
            sync_mode="keep_source",
            check_conflicts_only=True,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post(
    "/{slug:path}/sync-from-template",
    dependencies=[Depends(require_permission("content:write"))],
)
async def sync_page_from_template(
    slug: str,
    sync_mode: str | None = Query(default=None),
    force_rebuild: bool = Query(default=False),
):
    """Sync a generated item page's managed section grid/mapping from its template."""
    db = _db()
    page = await db["pages"].find_one({"slug": slug})
    if not page:
        raise HTTPException(404, "Page not found")
    if page.get("template_managed") is not True:
        raise HTTPException(400, "Page is not managed by an item-page template")

    try:
        result = await sync_generated_item_page_from_template_state(
            db,
            page,
            sync_mode=sync_mode if sync_mode is not None else "keep_source",
            force_rebuild=force_rebuild,
        )
        if str(page.get("template_source_type") or "").strip().lower() == "program_gig":
            refreshed_page = await db["pages"].find_one({"_id": page.get("_id")})
            if isinstance(refreshed_page, dict):
                await _sync_template_source_link_for_page_slug(db, refreshed_page)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _format_public_blog_item(doc: dict) -> dict:
    oid = doc.get("_id")
    return {
        "id": str(oid) if oid else "",
        "image_url": doc.get("image_url", ""),
        "image_zoom": _safe_float(doc.get("image_zoom"), 1.0),
        "image_focal_x": _safe_float(doc.get("image_focal_x"), 50.0),
        "image_focal_y": _safe_float(doc.get("image_focal_y"), 50.0),
        "image_rotation": _safe_float(doc.get("image_rotation"), 0.0),
        "date": doc.get("date", ""),
        "tag": doc.get("tag", {"de": "", "en": ""}),
        "title": doc.get("title", {"de": "", "en": ""}),
        "text": doc.get("text", {"de": "", "en": ""}),
        "page_slug": doc.get("page_slug", ""),
        "created_at": _format_datetime_response(doc.get("created_at")),
        "updated_at": _format_datetime_response(doc.get("updated_at")),
    }


def _dedupe_public_blog_items(items: list[dict]) -> list[dict]:
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


async def _get_public_blog_bundle() -> dict:
    cache_key = "public:blog-bundle"

    async def build_blog_bundle() -> dict:
        db = _db()
        items_coll = db[BLOG_SHARED_COLLECTION]
        config_coll = db[BLOG_CONFIG_COLLECTION]

        items = []
        async for doc in items_coll.find({}).sort("date", -1):
            items.append(_format_public_blog_item(doc))
        items = _dedupe_public_blog_items(items)

        config = await config_coll.find_one({"_id": "config"})
        tags = (
            config.get("tags", [])
            if config
            else [
                {"de": "Aktuelles", "en": "News"},
                {"de": "Veranstaltung", "en": "Event"},
                {"de": "Interview", "en": "Interview"},
            ]
        )
        return {"items": items, "tags": tags}

    return await get_or_set_ttl_cache(
        cache_key,
        PUBLIC_PAGE_PARTS_CACHE_SECONDS,
        build_blog_bundle,
    )


def _format_public_faq_item(item: dict) -> dict:
    return {
        "id": str(item.get("id") or ""),
        "question": item.get("question", {"de": "", "en": ""}),
        "answer": item.get("answer", {"de": "", "en": ""}),
        "tag": item.get("tag", {"de": "", "en": ""}),
        "start_date": str(item.get("start_date") or ""),
        "end_date": str(item.get("end_date") or ""),
    }


def _dedupe_public_faq_items(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for item in items:
        key = (
            (item.get("question") or {}).get("de", ""),
            (item.get("question") or {}).get("en", ""),
            (item.get("answer") or {}).get("de", ""),
            (item.get("answer") or {}).get("en", ""),
            (item.get("tag") or {}).get("de", ""),
            (item.get("tag") or {}).get("en", ""),
            item.get("start_date", ""),
            item.get("end_date", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


async def _get_public_faq_bundle() -> dict:
    cache_key = "public:faq-bundle"

    async def build_faq_bundle() -> dict:
        snapshot = await capture_faq_shared_content(_db())
        raw_items = snapshot.get("items") if isinstance(snapshot, dict) else []
        items = []
        if isinstance(raw_items, list):
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                items.append(_format_public_faq_item(item))
        items = _dedupe_public_faq_items(items)
        raw_tags = snapshot.get("tags") if isinstance(snapshot, dict) else []
        tags = [tag for tag in raw_tags if isinstance(tag, dict)]
        return {"items": items, "tags": tags}

    return await get_or_set_ttl_cache(
        cache_key,
        PUBLIC_PAGE_PARTS_CACHE_SECONDS,
        build_faq_bundle,
    )


def _coerce_program_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _program_section_type_data(section: dict) -> dict:
    type_data = section.get("type_data")
    return type_data if isinstance(type_data, dict) else {}


def _resolve_public_program_scope(section: dict) -> dict[str, Any] | None:
    section_type = str(section.get("section_type") or "").strip()
    type_data = _program_section_type_data(section)
    if section_type == "tiles":
        return {"all": True} if bool(type_data.get("use_program_gigs", True)) else None
    if section_type != "program":
        return None

    fixed_gig_id = str(type_data.get("fixed_gig_id") or "").strip()
    if fixed_gig_id:
        return {"gig_id": fixed_gig_id}

    fixed_day = str(type_data.get("fixed_day") or "").strip()
    fixed_stage_id = str(type_data.get("fixed_stage_id") or "").strip()
    if not fixed_day and not fixed_stage_id:
        return {"all": True}

    return {
        "day": fixed_day,
        "stage_id": fixed_stage_id,
        "day_start_hour": _coerce_program_int(
            type_data.get("day_start_hour", type_data.get("dayStartHour", 10)),
            10,
        ),
        "day_end_hour": _coerce_program_int(
            type_data.get("day_end_hour", type_data.get("dayEndHour", 6)),
            6,
        ),
    }


def _resolve_public_program_scopes(sections: list[dict]) -> list[dict[str, Any]] | None:
    scopes: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()
    for section in sections if isinstance(sections, list) else []:
        if not isinstance(section, dict):
            continue
        scope = _resolve_public_program_scope(section)
        if not scope:
            continue
        if scope.get("all"):
            return None
        signature = json.dumps(scope, sort_keys=True, separators=(",", ":"))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        scopes.append(scope)
    return scopes or None


def _program_gig_lookup_text_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        values = [
            str(value.get("de") or "").strip(),
            str(value.get("en") or "").strip(),
        ]
    elif isinstance(value, list):
        values = []
        for entry in value:
            values.extend(_program_gig_lookup_text_values(entry))
    elif isinstance(value, (str, int, float, bool)):
        values = [str(value).strip()]
    else:
        values = []

    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        token = text.lower()
        if token in seen:
            continue
        seen.add(token)
        result.append(text)
    return result


def _program_gig_lookup_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    for text in _program_gig_lookup_text_values(value):
        normalized = str(text or "").strip().lower()
        if normalized:
            tokens.add(normalized)
        slug = slugify_segment(text, fallback="")
        if slug:
            tokens.add(slug)
    return tokens


def _program_gig_alias_matches(gig: dict, lookup_value: Any) -> bool:
    lookup_tokens = _program_gig_lookup_tokens(lookup_value)
    if not lookup_tokens:
        return False
    gig_tokens: set[str] = set()
    for value in (
        gig.get("id"),
        gig.get("artist_name"),
        gig.get("title"),
        gig.get("name"),
    ):
        gig_tokens.update(_program_gig_lookup_tokens(value))
    return bool(lookup_tokens & gig_tokens)


async def _resolve_public_program_bundle_for_gig_scope(
    db,
    *,
    gig_id: str,
) -> dict:
    payload = await capture_program_shared_content(db, gig_id=gig_id)
    if payload.get("gigs"):
        return payload

    all_payload = await capture_program_shared_content(db)
    all_gigs = all_payload.get("gigs") if isinstance(all_payload.get("gigs"), list) else []
    matches = [
        gig
        for gig in all_gigs
        if isinstance(gig, dict) and _program_gig_alias_matches(gig, gig_id)
    ]
    if len(matches) != 1:
        return payload

    matched_gig = matches[0]
    matched_id = str(matched_gig.get("id") or "").strip()
    return {
        **all_payload,
        "gigs": [matched_gig],
        "gig_ids": [matched_id] if matched_id else [],
    }


async def _get_public_program_bundle(scopes: list[dict[str, Any]] | None = None) -> dict:
    cache_scope = "all"
    if scopes:
        cache_scope = json.dumps(scopes, sort_keys=True, separators=(",", ":"))
    cache_key = f"public:program-bundle:{cache_scope}"

    async def build_program_bundle() -> dict:
        db = _db()
        if not scopes:
            payload = await capture_program_shared_content(db)
            return {**payload, "scope": "full"}

        base_payload: dict[str, Any] | None = None
        gigs_by_id: dict[str, dict[str, Any]] = {}
        ordered_ids: list[str] = []
        for scope in scopes:
            scope_gig_id = str(scope.get("gig_id") or "").strip()
            if scope_gig_id:
                payload = await _resolve_public_program_bundle_for_gig_scope(
                    db,
                    gig_id=scope_gig_id,
                )
            else:
                payload = await capture_program_shared_content(
                    db,
                    stage_id=str(scope.get("stage_id") or "").strip() or None,
                    day=str(scope.get("day") or "").strip() or None,
                    day_start_hour=_coerce_program_int(scope.get("day_start_hour"), 0),
                    day_end_hour=_coerce_program_int(scope.get("day_end_hour"), 24),
                )
            if base_payload is None:
                base_payload = payload
            for gig in payload.get("gigs", []) if isinstance(payload.get("gigs"), list) else []:
                if not isinstance(gig, dict):
                    continue
                gig_id = str(gig.get("id") or "").strip()
                if not gig_id or gig_id in gigs_by_id:
                    continue
                gigs_by_id[gig_id] = gig
                ordered_ids.append(gig_id)

        if base_payload is None:
            base_payload = await capture_program_shared_content(db, ids=[])
        return {
            **base_payload,
            "gigs": [gigs_by_id[gig_id] for gig_id in ordered_ids],
            "gig_ids": ordered_ids,
            "scope": "partial",
        }

    return await get_or_set_ttl_cache(
        cache_key,
        PUBLIC_PROGRAM_BUNDLE_CACHE_SECONDS,
        build_program_bundle,
    )


async def _resolve_design_version_snapshot(versions_coll, doc: dict) -> dict | None:
    """Return the full design snapshot stored for a version."""
    return doc.get("design_settings")


def _format_public_design_payload(payload: dict | None, source_id: ObjectId | None = None) -> dict | None:
    if not payload:
        return None
    result = {k: v for k, v in payload.items() if k not in {"_id", "key", "revision_id", "comparison_version_id"}}
    if source_id:
        result["id"] = str(source_id)
    return result


async def _enrich_design_payload_with_font_cache(payload: dict | None) -> dict | None:
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
    resolved = None
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
    resolved_stylesheet_urls = resolved.get("font_stylesheet_urls")
    if not isinstance(resolved_stylesheet_urls, list):
        resolved_stylesheet_urls = fallback_stylesheet_urls
    resolved_pending_families = resolved.get("pending_families")
    if not isinstance(resolved_pending_families, list):
        resolved_pending_families = fallback_pending_families
    return {
        **payload,
        "font_stylesheet_urls": resolved_stylesheet_urls,
        "font_cache_pending_families": resolved_pending_families,
    }


async def _enrich_payload_with_asset_media(db, payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return payload
    image_urls = collect_raster_image_urls_from_payload(payload)
    if not image_urls:
        return payload
    asset_docs_by_url = await fetch_asset_docs_by_urls(db, image_urls)
    if not asset_docs_by_url:
        return payload
    enrich_raster_payload_with_asset_docs(payload, asset_docs_by_url)
    return payload


async def _get_public_media_fallbacks(db) -> dict[str, Any]:
    doc = await db[MEDIA_CONFIG_COLLECTION].find_one({"key": MEDIA_CONFIG_KEY})
    normalized = normalize_media_config(doc, strict_custom_tags=False)
    fallback_images = normalized.get("fallback_images")
    return fallback_images if isinstance(fallback_images, dict) else {}


def _inject_selected_units_from_admin_config(
    design_settings: dict | None,
    admin_config: dict | None,
) -> dict | None:
    """
    Public rendering does not load admin config, so we must persist effective units
    and color-variation defaults inside design payloads to avoid regressions
    (e.g. 60vh -> 60px fallback in published pages).
    """
    if not isinstance(design_settings, dict):
        return design_settings

    result = dict(design_settings)
    selected_units_raw = result.get("selected_units")
    selected_units = dict(selected_units_raw) if isinstance(selected_units_raw, dict) else {}

    parameters = admin_config.get("parameters") if isinstance(admin_config, dict) else None
    if isinstance(parameters, dict):
        for param_key, cfg in parameters.items():
            if not isinstance(param_key, str) or not param_key:
                continue
            if param_key in selected_units:
                continue
            if not isinstance(cfg, dict):
                continue
            unit = None
            default_unit = cfg.get("defaultUnit")
            if isinstance(default_unit, str):
                unit = default_unit
            if unit is None:
                unit_configs = cfg.get("unitConfigs")
                if isinstance(unit_configs, list):
                    for candidate in unit_configs:
                        if not isinstance(candidate, dict):
                            continue
                        candidate_unit = candidate.get("unit")
                        if isinstance(candidate_unit, str):
                            unit = candidate_unit
                            break
            if isinstance(unit, str):
                selected_units[param_key] = unit

    if selected_units:
        result["selected_units"] = selected_units

    design_variations_raw = result.get("color_variations")
    design_variations = (
        dict(design_variations_raw)
        if isinstance(design_variations_raw, dict)
        else {}
    )
    admin_variations = None
    if isinstance(admin_config, dict):
        admin_variations = admin_config.get("colorVariations")
        if not isinstance(admin_variations, dict):
            admin_variations = admin_config.get("color_variations")
    if isinstance(admin_variations, dict):
        for param_key, value in admin_variations.items():
            if param_key not in design_variations:
                design_variations[param_key] = value
    if design_variations:
        result["color_variations"] = design_variations

    public_color_config = _build_public_color_config(admin_config)
    if public_color_config:
        result["public_color_config"] = public_color_config

    return result


def _config_get(config: dict | None, camel_key: str, snake_key: str | None = None):
    if not isinstance(config, dict):
        return None
    if camel_key in config:
        return config.get(camel_key)
    if snake_key and snake_key in config:
        return config.get(snake_key)
    return None


def _build_public_color_config(admin_config: dict | None) -> dict | None:
    if not isinstance(admin_config, dict):
        return None

    parameters = _config_get(admin_config, "parameters")
    color_links = _config_get(admin_config, "colorLinks", "color_links")
    base_high_contrast = _config_get(admin_config, "baseColorHighContrast", "base_color_high_contrast")
    color_variations = _config_get(admin_config, "colorVariations", "color_variations")
    responsive = _config_get(admin_config, "responsive")

    public_parameters: dict[str, dict] = {}
    if isinstance(parameters, dict):
        for key, cfg in parameters.items():
            if not isinstance(key, str) or not isinstance(cfg, dict):
                continue
            if cfg.get("type") != "color" or cfg.get("isBase") is not True:
                continue
            public_parameters[key] = {
                field: deepcopy(cfg[field])
                for field in ("type", "isBase", "label", "default")
                if field in cfg
            }

    public_config: dict[str, dict] = {}
    if public_parameters:
        public_config["parameters"] = public_parameters
    if isinstance(color_links, dict):
        public_config["colorLinks"] = deepcopy(color_links)
    if isinstance(base_high_contrast, dict):
        public_config["baseColorHighContrast"] = deepcopy(base_high_contrast)
    if isinstance(color_variations, dict):
        public_config["colorVariations"] = deepcopy(color_variations)
    public_config["responsive"] = normalize_responsive_config(responsive)

    return public_config or None


async def _get_public_design_settings() -> dict | None:
    cache_key = "public:design-settings"

    async def build_design_settings() -> dict | None:
        db = _db()
        versions_coll = db[DESIGN_VERSIONS_COLLECTION]
        admin_doc = await db[DESIGN_EDITOR_CONFIG_COLLECTION].find_one({"key": ADMIN_CONFIG_KEY})

        # Prefer the explicitly published version for public rendering.
        published_version = await versions_coll.find_one(
            {"is_published": True},
            sort=[("published_at", -1), ("created_at", -1)],
        )
        if published_version:
            design_settings = await _resolve_design_version_snapshot(versions_coll, published_version)
            effective_design = _inject_selected_units_from_admin_config(design_settings, admin_doc)
            formatted = _format_public_design_payload(effective_design, published_version.get("_id"))
            if formatted:
                enriched = await _enrich_payload_with_asset_media(db, formatted)
                return await _enrich_design_payload_with_font_cache(enriched)

        # If versions exist but no one is explicitly published yet, use the newest snapshot.
        latest_version = await versions_coll.find_one({}, sort=[("created_at", -1)])
        if latest_version:
            design_settings = await _resolve_design_version_snapshot(versions_coll, latest_version)
            effective_design = _inject_selected_units_from_admin_config(design_settings, admin_doc)
            formatted = _format_public_design_payload(effective_design, latest_version.get("_id"))
            if formatted:
                enriched = await _enrich_payload_with_asset_media(db, formatted)
                return await _enrich_design_payload_with_font_cache(enriched)

        # Fallback when no design version exists: use the current global design doc.
        design_doc = await db[DESIGN_CONFIG_COLLECTION].find_one({"key": "global"})
        if not design_doc:
            return None

        effective_design = _inject_selected_units_from_admin_config(design_doc, admin_doc)
        formatted = _format_public_design_payload(effective_design, design_doc.get("_id"))
        enriched = await _enrich_payload_with_asset_media(db, formatted)
        return await _enrich_design_payload_with_font_cache(enriched)

    return await get_or_set_ttl_cache(
        cache_key,
        PUBLIC_PAGE_PARTS_CACHE_SECONDS,
        build_design_settings,
    )


def _public_section_snippet_contexts(page: dict | None) -> set[str]:
    contexts: set[str] = set()
    sections = page.get("sections") if isinstance(page, dict) else []
    for section in (sections if isinstance(sections, list) else []):
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("_id") or section.get("id") or "").strip()
        if section_id:
            contexts.add(f"section:{section_id}")
    return contexts


def _format_public_css_snippet(doc: dict, allowed_contexts: set[str]) -> dict | None:
    css = str(doc.get("css") or "").strip()
    if not css:
        return None

    context_key = str(doc.get("context_key") or "").strip()
    if context_key and context_key not in allowed_contexts:
        return None

    media_scope = doc.get("media_scope")
    return {
        "css": css,
        "media_scope": media_scope if media_scope in {"tablet", "mobile"} else None,
        "context_key": context_key or None,
    }


async def _get_public_css_snippets(page: dict | None) -> list[dict]:
    allowed_contexts = _public_section_snippet_contexts(page)
    slug = str((page if isinstance(page, dict) else {}).get("slug") or "").strip()
    cache_key = f"public:css-snippets:{slug}:{','.join(sorted(allowed_contexts))}"

    async def build_css_snippets() -> list[dict]:
        db = _db()
        context_conditions: list[dict] = [
            {"context_key": {"$exists": False}},
            {"context_key": None},
            {"context_key": ""},
        ]
        if allowed_contexts:
            context_conditions.append({"context_key": {"$in": sorted(allowed_contexts)}})

        cursor = (
            db[CSS_SNIPPETS_COLLECTION]
            .find(
                {
                    "$and": [
                        {
                            "$or": [
                                {"scope": "global"},
                                {"scope": {"$exists": False}},
                                {"scope": None},
                            ]
                        },
                        {"active": {"$ne": False}},
                        {"$or": context_conditions},
                    ]
                }
            )
            .sort("created_at", -1)
        )

        snippets: list[dict] = []
        async for doc in cursor:
            formatted = _format_public_css_snippet(doc, allowed_contexts)
            if formatted:
                snippets.append(formatted)
        return snippets

    return await get_or_set_ttl_cache(
        cache_key,
        PUBLIC_PAGE_PARTS_CACHE_SECONDS,
        build_css_snippets,
    )


async def _build_public_page_bundle(normalized_slug: str, request: Request) -> dict:
    """
    Build the public, crawler-friendly page bundle without cache wrapping.
    """
    try:
        page = await get_page_with_sections(normalized_slug, include_hidden=False, user=None)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise

        # If route redirect rules explicitly mark this URL as removed, return HTTP 410.
        source_path = "/" if normalized_slug in {"", "landing"} else f"/{normalized_slug}"
        try:
            source_path = normalize_internal_path(source_path)
        except ValueError:
            source_path = "/" if source_path == "/" else source_path.rstrip("/") or "/"

        redirect_doc = await find_active_redirect_doc(_db(), source_path=source_path)
        if redirect_doc and int(redirect_doc.get("status_code", 301)) == 410:
            if (
                str(redirect_doc.get("kind") or "custom") == "custom"
                and not request_has_auth_credentials(request)
            ):
                await increment_redirect_anonymous_hit_count(_db(), redirect_doc=redirect_doc)
            raise HTTPException(status_code=410, detail="Page removed (410 Gone)")
        raise
    menu_items = await _get_public_menu_items()
    footer_items = await _get_public_footer_items()
    navigation_links_config = await get_navigation_links_config(_db())
    topbar_logo_url = None
    topbar_logo_responsive_variants: list[dict[str, Any]] = []
    footer_logo_url = None
    footer_logo_responsive_variants: list[dict[str, Any]] = []
    if isinstance(navigation_links_config, dict):
        raw_topbar_logo_url = navigation_links_config.get("topbar_logo_url")
        if raw_topbar_logo_url:
            topbar_logo_url = str(raw_topbar_logo_url).strip() or None
        raw_topbar_logo_responsive_variants = navigation_links_config.get("topbar_logo_responsive_variants")
        if isinstance(raw_topbar_logo_responsive_variants, list):
            topbar_logo_responsive_variants = [
                entry for entry in raw_topbar_logo_responsive_variants if isinstance(entry, dict)
            ]
        raw_footer_logo_url = navigation_links_config.get("footer_logo_url")
        if raw_footer_logo_url:
            footer_logo_url = str(raw_footer_logo_url).strip() or None
        raw_footer_logo_responsive_variants = navigation_links_config.get("footer_logo_responsive_variants")
        if isinstance(raw_footer_logo_responsive_variants, list):
            footer_logo_responsive_variants = [
                entry for entry in raw_footer_logo_responsive_variants if isinstance(entry, dict)
            ]
    design_settings = (
        page.get("effective_design_settings")
        if isinstance(page.get("effective_design_settings"), dict)
        else None
    )
    if not isinstance(design_settings, dict):
        design_settings = await _get_public_design_settings()
    has_faq_section = any(
        section.get("section_type") == "faq"
        for section in page.get("sections", [])
    )
    has_blog_section = any(
        section.get("section_type") == "blog"
        for section in page.get("sections", [])
    )
    has_program_section = any(
        (
            section.get("section_type") == "program"
            or (
                section.get("section_type") == "tiles"
                and bool(
                    (
                        section.get("type_data")
                        if isinstance(section.get("type_data"), dict)
                        else {}
                    ).get("use_program_gigs", True)
                )
            )
        )
        for section in page.get("sections", [])
    )
    faq = await _get_public_faq_bundle() if has_faq_section else None
    blog = await _get_public_blog_bundle() if has_blog_section else None
    program_scopes = _resolve_public_program_scopes(page.get("sections", [])) if has_program_section else None
    program = await _get_public_program_bundle(program_scopes) if has_program_section else None
    css_snippets = await _get_public_css_snippets(page)
    media_fallbacks = page.get("media_fallbacks") if isinstance(page.get("media_fallbacks"), dict) else {}
    bundle = {
        "page": page,
        "menu_items": menu_items,
        "footer_items": footer_items,
        "topbar_logo_url": topbar_logo_url,
        "topbar_logo_responsive_variants": topbar_logo_responsive_variants,
        "footer_logo_url": footer_logo_url,
        "footer_logo_responsive_variants": footer_logo_responsive_variants,
        "design_settings": design_settings,
        "css_snippets": css_snippets,
        "faq": faq,
        "blog": blog,
        "program": program,
        "media_fallbacks": media_fallbacks,
        "seo": {
            "slug": page.get("slug"),
            "title": page.get("title"),
            "menu_title": page.get("menu_title"),
            "menu_parent_title": page.get("menu_parent_title"),
            "is_visible": page.get("is_visible", False),
            "updated_at": page.get("updated_at"),
        },
    }
    return bundle


@router.get("/public/{slug:path}")
async def get_public_page_bundle(slug: str, request: Request, response: Response):
    """
    Public, crawler-friendly bundle endpoint.

    Returns one composed payload for page rendering without exposing
    admin/private metadata.
    """
    normalized_slug = _normalize_public_slug_input(slug)
    use_shared_cache = not request_has_auth_credentials(request)
    if not use_shared_cache:
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Backend-Cache-Status"] = "BYPASS"
        return await _build_public_page_bundle(normalized_slug, request)

    cache_key = f"public:page-bundle:{normalized_slug}"
    cached = get_ttl_cache(cache_key)
    if cached is not None:
        set_public_cache_headers(
            response,
            max_age=PUBLIC_PAGE_BUNDLE_CACHE_SECONDS,
            stale_while_revalidate=30,
        )
        response.headers["X-Backend-Cache-Status"] = "HIT"
        return cached

    async def build_bundle() -> dict:
        return await _build_public_page_bundle(normalized_slug, request)

    bundle = await get_or_set_ttl_cache(
        cache_key,
        PUBLIC_PAGE_BUNDLE_CACHE_SECONDS,
        build_bundle,
    )
    set_public_cache_headers(
        response,
        max_age=PUBLIC_PAGE_BUNDLE_CACHE_SECONDS,
        stale_while_revalidate=30,
    )
    response.headers["X-Backend-Cache-Status"] = "MISS"
    return bundle


@router.post("/public-hit/{slug:path}", status_code=204)
async def record_public_page_hit(slug: str, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    if request_has_auth_credentials(request):
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    normalized_slug = _normalize_public_slug_input(slug)
    db = _db()
    pages = db["pages"]
    doc = await pages.find_one(
        {"slug": normalized_slug},
        {
            "_id": 1,
            "status": 1,
            "publish_at": 1,
            "unpublish_at": 1,
        },
    )
    if not doc or _compute_effective_status(doc) != "published":
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    now = datetime.now(timezone.utc)
    day = now.date().isoformat()
    await pages.update_one(
        {"_id": doc["_id"]},
        {
            "$inc": {"anonymous_hit_count": 1},
            "$set": {"anonymous_last_hit_at": now},
        },
    )
    await db[PAGE_HIT_DAYS_COLLECTION].update_one(
        {
            "page_id": doc["_id"],
            "day": day,
        },
        {
            "$setOnInsert": {
                "created_at": now,
            },
            "$set": {
                "slug": normalized_slug,
                "updated_at": now,
            },
            "$inc": {"count": 1},
        },
        upsert=True,
    )
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.patch(
    "/{slug:path}/sections/{section_id}",
    response_model=PageResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def update_page_section_ref(
    slug: str,
    section_id: str,
    order: int | None = Query(default=None),
    visible: bool | None = Query(default=None),
    limit: int | None = Query(
        default=None, ge=0, description="Positive integer cap, 0=show all. Omit to skip."
    ),
    width_n: int | None = Query(default=None, ge=1, le=5),
    width_d: int | None = Query(default=None, ge=1, le=5),
    device_mobile: bool | None = Query(default=None),
    device_tablet: bool | None = Query(default=None),
    device_desktop: bool | None = Query(default=None),
):
    """Update order, visibility, limit, or width ratio of a section within a page."""
    pages = _db()["pages"]

    page = await pages.find_one({"slug": slug})
    if not page:
        raise HTTPException(404, "Page not found")

    sections = page.get("sections", [])
    found = False
    for ref in sections:
        if ref["section_id"] == section_id:
            if order is not None:
                ref["order"] = order
            if visible is not None:
                ref["visible"] = visible
            if limit is not None:
                ref["limit"] = int(limit) if int(limit) > 0 else None
            if width_n is not None:
                ref["width_n"] = width_n
            if width_d is not None:
                ref["width_d"] = width_d
            if ref.get("width_n") and ref.get("width_d"):
                ref["width_n"] = min(ref["width_n"], ref["width_d"])
            if (
                device_mobile is not None
                or device_tablet is not None
                or device_desktop is not None
            ):
                current_device_visibility = (
                    ref.get("device_visibility")
                    if isinstance(ref.get("device_visibility"), dict)
                    else {}
                )
                ref["device_visibility"] = {
                    "mobile": (
                        device_mobile
                        if device_mobile is not None
                        else current_device_visibility.get("mobile", True)
                    ),
                    "tablet": (
                        device_tablet
                        if device_tablet is not None
                        else current_device_visibility.get("tablet", True)
                    ),
                    "desktop": (
                        device_desktop
                        if device_desktop is not None
                        else current_device_visibility.get("desktop", True)
                    ),
                }
            found = True
            break

    if not found:
        raise HTTPException(404, "Section not found in page")

    if order is not None:
        ordered_refs = sorted(
            [ref for ref in sections if isinstance(ref, dict)],
            key=lambda ref: int(ref.get("order", 0) or 0),
        )
        ordered_ids = [
            str(ref.get("section_id") or "").strip()
            for ref in ordered_refs
            if str(ref.get("section_id") or "").strip()
        ]
        membership = extract_container_membership_from_structure(page.get("section_structure"))
        next_structure = build_section_structure_from_container_membership(
            ordered_ids,
            section_to_container_id=membership,
        )
        sections, normalized_section_structure = _normalize_page_sections_and_structure(
            sections,
            next_structure,
        )
    else:
        sections, normalized_section_structure = _normalize_page_sections_and_structure(
            sections,
            page.get("section_structure"),
        )

    res = await pages.find_one_and_update(
        {"slug": slug},
        {
            "$set": {
                "sections": sections,
                "section_structure": normalized_section_structure,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    return _format_page_response(res)


@router.patch(
    "/{slug:path}/sections/{section_id}/design",
    response_model=PageResponse,
    dependencies=[Depends(require_permission("design:write"))],
)
async def update_section_design_overrides(
    slug: str,
    section_id: str,
    payload: dict | None = Body(default=None),
    user: KeycloakUser = Depends(get_current_user),
):
    """Update or clear per-section design overrides."""
    db = _db()
    pages = db["pages"]
    sections_coll = db[SECTIONS_COLLECTION]
    revisions = db["revisions"]

    page = await pages.find_one({"slug": slug})
    if not page:
        raise HTTPException(404, "Page not found")
    _ensure_template_style_not_locked_for_design(page)

    sections = page.get("sections", [])
    found = False
    target_ref = None
    normalized_override, reverted_from_saved_at = _parse_design_override_payload(payload)
    if isinstance(normalized_override, dict):
        normalized_override = strip_legacy_container_override(normalized_override)
    normalized_override = normalized_override if normalized_override else None
    for ref in sections:
        if ref["section_id"] == section_id:
            target_ref = ref
            found = True
            break

    if not found:
        raise HTTPException(404, "Section not found in page")

    current_override = (
        target_ref.get("design_overrides")
        if target_ref and "design_overrides" in target_ref
        else None
    )
    if current_override == normalized_override:
        return _format_page_response(page)

    section_doc = await sections_coll.find_one({"_id": ObjectId(section_id)})
    if not section_doc:
        raise HTTPException(404, "Section not found")

    revision_config = await get_or_create_revision_config(db)
    section_options = get_section_revision_options(
        revision_config,
        section_doc.get("section_type", "text"),
    )
    if section_revision_history_enabled(section_options) and section_options["include_design"]:
        # Design override updates should only store design-state snapshots.
        content_snapshot = None
        design_snapshot = await capture_section_design_state(
            db,
            section_id,
            section_doc=section_doc,
        )
        revision_data = build_section_revision_snapshot(
            content=content_snapshot,
            design=design_snapshot,
        )
        revision_id = section_doc.get("revision_id")
        new_revision_id = await push_revision_entry(
            revisions,
            entity_type="section",
            entity_id=section_id,
            current_data=revision_data,
            revision_id=as_object_id(revision_id),
            saved_by=user.username,
            change_kind="design",
            reverted_from_saved_at=reverted_from_saved_at,
            max_history=REVISION_HISTORY_LIMIT,
        )
        if new_revision_id and new_revision_id != revision_id:
            await sections_coll.update_one(
                {"_id": section_doc["_id"]},
                {"$set": {"revision_id": new_revision_id}},
            )

    target_ref["design_overrides"] = normalized_override
    sections, normalized_section_structure = _normalize_page_sections_and_structure(
        sections,
        page.get("section_structure"),
    )

    res = await pages.find_one_and_update(
        {"slug": slug},
        {
            "$set": {
                "sections": sections,
                "section_structure": normalized_section_structure,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    return _format_page_response(res)


@router.post(
    "/{slug:path}/sections",
    response_model=PageResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def add_section_to_page(slug: str, section_ref: PageSectionRef):
    """Add a section reference to a page."""
    db = _db()
    pages = db["pages"]
    sections_coll = db[SECTIONS_COLLECTION]

    # Verify section exists
    section = await sections_coll.find_one({"_id": ObjectId(section_ref.section_id)})
    if not section:
        raise HTTPException(404, "Section not found")

    page = await pages.find_one({"slug": slug})
    if not page:
        raise HTTPException(404, "Page not found")
    page_style_linked = _is_template_style_linked(page)

    sections = page.get("sections", [])

    # Check if section already exists in page
    for ref in sections:
        if ref["section_id"] == section_ref.section_id:
            raise HTTPException(409, "Section already exists in page")

    next_ref = section_ref.model_dump()
    if page_style_linked:
        # Linked template-style pages may still change structure/content, but not carry local design overrides.
        next_ref.pop("design_overrides", None)
    elif isinstance(next_ref.get("design_overrides"), dict):
        next_ref["design_overrides"] = strip_legacy_container_override(next_ref.get("design_overrides"))
    sections.append(next_ref)
    sections, normalized_section_structure = _normalize_page_sections_and_structure(
        sections,
        page.get("section_structure"),
    )

    res = await pages.find_one_and_update(
        {"slug": slug},
        {
            "$set": {
                "sections": sections,
                "section_structure": normalized_section_structure,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    return _format_page_response(res)


@router.delete(
    "/{slug:path}/sections/{section_id}",
    response_model=PageResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def remove_section_from_page(slug: str, section_id: str):
    """Remove a section reference from a page (does not delete the section itself)."""
    pages = _db()["pages"]

    page = await pages.find_one({"slug": slug})
    if not page:
        raise HTTPException(404, "Page not found")

    sections = page.get("sections", [])
    original_count = len(sections)
    sections = [ref for ref in sections if ref["section_id"] != section_id]

    if len(sections) == original_count:
        raise HTTPException(404, "Section not found in page")

    sections, normalized_section_structure = _normalize_page_sections_and_structure(
        sections,
        page.get("section_structure"),
    )

    res = await pages.find_one_and_update(
        {"slug": slug},
        {
            "$set": {
                "sections": sections,
                "section_structure": normalized_section_structure,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    return _format_page_response(res)


@router.post(
    "/{slug:path}/sections/create",
    response_model=PageFullResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def create_and_add_section(
    slug: str,
    payload: SectionCreate,
    template_name: str | None = Query(default=None),
    user: KeycloakUser = Depends(get_current_user),
):
    """Create a new section from a template and add it to the page.

    This endpoint combines section creation and page attachment in one call.
    If type_data is not provided, default data for the section type will be used.
    """
    db = _db()
    pages = db["pages"]
    sections_coll = db[SECTIONS_COLLECTION]

    # Verify page exists
    page = await pages.find_one({"slug": slug})
    if not page:
        raise HTTPException(404, "Page not found")
    page_style_linked = _is_template_style_linked(page)

    now = datetime.utcnow()
    section_type = payload.section_type or "text"
    requested_template_name = str(template_name or "").strip()
    resolved_template_name = (
        normalize_template_name(requested_template_name, default="default")
        if requested_template_name
        else "default"
    )
    explicit_template_requested = bool(requested_template_name)

    template_doc = await db[TEMPLATE_SECTIONS_COLLECTION].find_one(
        {"section_type": section_type, "template_name": resolved_template_name}
    )
    if explicit_template_requested and template_doc is None:
        # Resiliency path: after destructive resets, default templates may not
        # exist yet although callers request template_name=default by default.
        if resolved_template_name == "default":
            normalized_default = normalize_section_template_doc(
                section_type,
                "default",
                payload=None,
                seed_list_target_visibility_presets=True,
            )
            await db[TEMPLATE_SECTIONS_COLLECTION].update_one(
                {"section_type": section_type, "template_name": "default"},
                {
                    "$setOnInsert": {
                        **normalized_default,
                        "created_at": now,
                        "updated_at": now,
                    }
                },
                upsert=True,
            )
            template_doc = await db[TEMPLATE_SECTIONS_COLLECTION].find_one(
                {"section_type": section_type, "template_name": "default"}
            )
        if template_doc is None:
            raise HTTPException(404, "Section template not found")
    template_title = (
        template_doc.get("title")
        if isinstance(template_doc, dict) and isinstance(template_doc.get("title"), dict)
        else None
    )

    # Use default title if not provided or empty
    if payload.title:
        title_dict = payload.title.model_dump()
        # Check if both de and en are empty
        if not title_dict.get("de") and not title_dict.get("en"):
            if template_title:
                title_dict = {
                    "de": str(template_title.get("de") or ""),
                    "en": str(template_title.get("en") or ""),
                }
            else:
                title_dict = get_default_title(section_type)
    else:
        if template_title:
            title_dict = {
                "de": str(template_title.get("de") or ""),
                "en": str(template_title.get("en") or ""),
            }
        else:
            title_dict = get_default_title(section_type)

    template_type_data = (
        deepcopy(template_doc.get("type_data"))
        if isinstance(template_doc, dict) and isinstance(template_doc.get("type_data"), dict)
        else None
    )
    template_title_placeholder = (
        str(template_doc.get("title_placeholder") or "").strip()
        if isinstance(template_doc, dict)
        else ""
    )
    template_design_overrides = (
        deepcopy(template_doc.get("design_overrides"))
        if (not page_style_linked) and isinstance(template_doc, dict) and isinstance(template_doc.get("design_overrides"), dict)
        else None
    )
    template_section_integration_mapping = (
        normalize_section_integration_mapping(
            deepcopy(template_doc.get("section_integration_mapping"))
        )
        if isinstance(template_doc, dict)
        else {}
    )
    template_custom_css = (
        await _build_section_template_custom_css(
            db,
            section_type=section_type,
            template_name=resolved_template_name,
        )
        if (not page_style_linked) and isinstance(template_doc, dict)
        else ""
    )

    if payload.type_data:
        if isinstance(template_type_data, dict):
            type_data = {**template_type_data, **payload.type_data}
        else:
            type_data = payload.type_data
    elif isinstance(template_type_data, dict):
        type_data = template_type_data
    else:
        type_data = get_default_type_data(section_type)
    type_data = normalize_section_description_payload(section_type, type_data)

    # Create the section
    section_doc = {
        "section_type": section_type,
        "shared": bool(payload.shared),
        "section_template_name": resolved_template_name or "default",
        "title_placeholder": payload.title_placeholder
        or template_title_placeholder
        or section_type.replace("_", " ").title(),
        "title": title_dict,
        "type_data": type_data,
        "section_integration_mapping": (
            normalize_section_integration_mapping(payload.section_integration_mapping)
            if payload.section_integration_mapping is not None
            else template_section_integration_mapping
        ),
        "revision_id": None,
        "created_at": now,
        "updated_at": now,
    }
    section_res = await sections_coll.insert_one(section_doc)
    section_id = str(section_res.inserted_id)

    # Calculate next order
    existing_sections = page.get("sections", [])
    max_order = max([ref.get("order", 0) for ref in existing_sections], default=-1)

    # Add section to page
    new_ref = {
        "section_id": section_id,
        "order": max_order + 1,
        "visible": True,
    }
    merged_design_overrides = (
        deepcopy(template_design_overrides)
        if isinstance(template_design_overrides, dict)
        else {}
    )
    if template_custom_css:
        merged_design_overrides["_templateCustomCss"] = template_custom_css
    if merged_design_overrides:
        new_ref["design_overrides"] = strip_legacy_container_override(merged_design_overrides)
    existing_sections.append(new_ref)
    existing_sections, normalized_section_structure = _normalize_page_sections_and_structure(
        existing_sections,
        page.get("section_structure"),
    )

    await pages.update_one(
        {"slug": slug},
        {
            "$set": {
                "sections": existing_sections,
                "section_structure": normalized_section_structure,
                "updated_at": now,
            }
        },
    )

    # Return full page response with populated sections
    return await get_page_with_sections(
        slug,
        include_hidden=True,
        user=user,
    )


# --- Header attachment endpoints ---


@router.put(
    "/{slug:path}/header",
    response_model=HeaderResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def attach_or_create_header(
    slug: str,
    payload: HeaderCreate,
    user: KeycloakUser = Depends(get_current_user),
):
    """Create a new header and attach it to the page, or update existing header.

    If the page already has a header, the existing header is updated.
    If the page has no header, a new header is created and attached.
    """
    db = _db()
    pages = db["pages"]
    headers = db["headers"]

    page = await pages.find_one({"slug": slug})
    if not page:
        raise HTTPException(404, "Page not found")
    if _is_template_style_locked(page) and payload.design_overrides is not None:
        raise HTTPException(409, TEMPLATE_STYLE_LOCK_ERROR)

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

    header_data = {
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
        "updated_at": now,
    }
    if "shared" in payload.model_fields_set:
        header_data["shared"] = bool(payload.shared)
    if payload.design_overrides is not None:
        header_data["design_overrides"] = payload.design_overrides

    # Check if page already has a header
    if page.get("has_header") and page.get("header_id"):
        # Update existing header
        header_id = page["header_id"]
        header_oid = as_object_id(header_id)
        current = await headers.find_one({"_id": header_oid}) if header_oid else None

        if current:
            # Push current state to revision history before updating
            revision_config = await get_or_create_revision_config(db)
            header_options = get_header_revision_options(revision_config)
            revision_id = current.get("revision_id")
            if header_revisions_enabled(header_options):
                current_data = {
                    "schema_version": 2,
                    "content": snapshot_document(
                        current,
                        exclude_keys={"_id", "revision_id", "created_at", "updated_at", "design_overrides", "shared"},
                    ) if header_options["include_content"] else None,
                    "design": {"design_overrides": current.get("design_overrides")}
                    if header_options["include_design"] else None,
                }
                next_doc = deepcopy(current)
                next_doc.update(header_data)
                next_data = {
                    "schema_version": 2,
                    "content": snapshot_document(
                        next_doc,
                        exclude_keys={"_id", "revision_id", "created_at", "updated_at", "design_overrides", "shared"},
                    ) if header_options["include_content"] else None,
                    "design": {"design_overrides": next_doc.get("design_overrides")}
                    if header_options["include_design"] else None,
                }
                requested_change_kind = payload.revision_change_kind
                if requested_change_kind not in {"content", "design", "both"}:
                    requested_change_kind = "design" if payload.design_overrides is not None else "content"
                if snapshots_equal(current_data, next_data):
                    header_data["revision_id"] = revision_id
                else:
                    effective_change_kind = _resolve_effective_header_change_kind(
                        current_data,
                        next_data,
                        requested_change_kind,
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
                        max_history=REVISION_HISTORY_LIMIT,
                    )
                    header_data["revision_id"] = new_revision_id or revision_id
            else:
                header_data["revision_id"] = revision_id

            header_doc = await headers.find_one_and_update(
                {"_id": header_oid},
                {"$set": header_data},
                return_document=ReturnDocument.AFTER,
            )
        else:
            # Header was deleted, create new one
            header_data.setdefault("shared", False)
            header_data["revision_id"] = None
            header_data["created_at"] = now
            res = await headers.insert_one(header_data)
            header_data["_id"] = res.inserted_id
            header_doc = header_data

            # Update page with new header_id
            await pages.update_one(
                {"slug": slug},
                {"$set": {"header_id": str(res.inserted_id), "updated_at": now}},
            )
    else:
        # Create new header
        header_data.setdefault("shared", False)
        header_data["revision_id"] = None
        header_data["created_at"] = now
        res = await headers.insert_one(header_data)
        header_data["_id"] = res.inserted_id
        header_doc = header_data

        # Attach header to page
        await pages.update_one(
            {"slug": slug},
            {
                "$set": {
                    "has_header": True,
                    "header_id": str(res.inserted_id),
                    "updated_at": now,
                }
            },
        )

    try:
        await sync_generated_item_page_review_overrides_for_saved_targets(
            db,
            collection="header",
            document_id=str(header_doc.get("_id") or ""),
            saved_doc=header_doc,
            updated_paths=set(header_data.keys()),
        )
    except Exception:
        logger.warning(
            "generated_item_page.review_override_header_sync_failed slug=%s header_id=%s",
            slug,
            str(header_doc.get("_id") or ""),
            exc_info=True,
        )

    return _format_header_response(header_doc, include_admin_fields=True)


@router.patch(
    "/{slug:path}/header/design",
    dependencies=[Depends(require_permission("design:write"))],
)
async def update_header_design_overrides(
    slug: str,
    payload: dict | None = Body(default=None),
    user: KeycloakUser = Depends(get_current_user),
):
    """Update design overrides for the page's header."""
    db = _db()
    pages = db["pages"]
    headers = db["headers"]
    revisions = db["revisions"]

    page = await pages.find_one({"slug": slug})
    if not page:
        raise HTTPException(404, "Page not found")
    _ensure_template_style_not_locked_for_design(page)
    if not page.get("header_id"):
        raise HTTPException(404, "Page has no header")

    header_id = page["header_id"]
    header_oid = as_object_id(header_id)
    current = await headers.find_one({"_id": header_oid}) if header_oid else None
    if not current:
        raise HTTPException(404, "Header not found")
    overrides, reverted_from_saved_at = _parse_design_override_payload(payload)
    if current.get("design_overrides") == overrides:
        return {"ok": True}

    revision_config = await get_or_create_revision_config(db)
    header_options = get_header_revision_options(revision_config)
    revision_id = current.get("revision_id")
    if header_revisions_enabled(header_options) and header_options["include_design"]:
        current_data = {
            "schema_version": 2,
            "content": None,
            "design": {"design_overrides": current.get("design_overrides")},
        }
        new_revision_id = await push_revision_entry(
            revisions,
            entity_type="header",
            entity_id=header_id,
            current_data=current_data,
            revision_id=revision_id,
            saved_by=user.username,
            change_kind="design",
            reverted_from_saved_at=reverted_from_saved_at,
            max_history=REVISION_HISTORY_LIMIT,
        )
    else:
        new_revision_id = revision_id

    await headers.update_one(
        {"_id": ObjectId(header_id)},
        {
            "$set": {
                "design_overrides": overrides,
                "updated_at": datetime.utcnow(),
                "revision_id": new_revision_id or revision_id,
            }
        },
    )
    return {"ok": True}


@router.patch(
    "/{slug:path}/header/attach",
    response_model=PageResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def attach_existing_header(slug: str, header_id: str = Query(...)):
    """Attach an existing header to a page (replacing any current header reference)."""
    db = _db()
    pages = db["pages"]
    headers = db["headers"]

    page = await pages.find_one({"slug": slug})
    if not page:
        raise HTTPException(404, "Page not found")

    header_doc = await headers.find_one({"_id": ObjectId(header_id)})
    if not header_doc:
        raise HTTPException(404, "Header not found")

    res = await pages.find_one_and_update(
        {"slug": slug},
        {
            "$set": {
                "has_header": True,
                "header_id": header_id,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    return _format_page_response(res)


@router.delete(
    "/{slug:path}/header",
    dependencies=[Depends(require_permission("content:write"))],
)
async def detach_header(slug: str):
    """Detach header from page (does not delete the header itself)."""
    pages = _db()["pages"]

    page = await pages.find_one({"slug": slug})
    if not page:
        raise HTTPException(404, "Page not found")

    await pages.update_one(
        {"slug": slug},
        {
            "$set": {
                "has_header": False,
                "header_id": None,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    return {"ok": True}


@router.delete("/{slug:path}", dependencies=[Depends(require_permission("content:admin"))])
async def delete_page(slug: str):
    db = _db()
    pages = db["pages"]

    doc = await pages.find_one({"slug": slug})
    if not doc:
        raise HTTPException(404, "Not found")

    was_public = _is_page_visible(doc)

    # Note: Sections and headers are standalone and not deleted with the page
    # They can be reused across pages or deleted separately
    await pages.delete_one({"_id": doc["_id"]})
    redirect_result = None
    if was_public:
        redirect_result = await upsert_generated_gone_redirect_for_slug(db, doc.get("slug") or slug)
    return {"ok": True, "gone_redirect": redirect_result}


@router.post(
    "/{slug:path}/move-subtree",
    dependencies=[Depends(require_permission("content:write"))],
)
async def move_subtree(slug: str, payload: MoveSubtreePayload):
    """
    Move a page subtree under a new parent route by updating slugs.

    Example:
      source: "festival/program"
      target_parent_slug: "archive/2026"
      result root: "archive/2026/program"
      descendants are rewritten with the same suffix.
    """
    db = _db()
    pages = db["pages"]

    source_slug = slug.strip("/")
    if not source_slug:
        raise HTTPException(400, "Invalid source slug")
    if source_slug == "landing":
        raise HTTPException(400, "The landing page cannot be moved")

    target_parent = (payload.target_parent_slug or "").strip("/")
    if target_parent == "landing":
        # Keep root migration explicit; "landing" is not treated as a parent path.
        target_parent = ""

    source_doc = await pages.find_one({"slug": source_slug})
    if not source_doc:
        raise HTTPException(404, "Page not found")

    if target_parent:
        parent_doc = await pages.find_one({"slug": target_parent})
        if not parent_doc:
            raise HTTPException(404, "Target parent page not found")
        if target_parent == source_slug or target_parent.startswith(source_slug + "/"):
            raise HTTPException(400, "Cannot move a subtree into itself")

    source_leaf = source_slug.split("/")[-1]
    new_root_slug = f"{target_parent}/{source_leaf}" if target_parent else source_leaf
    if new_root_slug == source_slug:
        return {"ok": True, "old_root_slug": source_slug, "new_root_slug": new_root_slug, "updated_count": 0}

    return await _rewrite_subtree_slugs(
        db,
        source_slug=source_slug,
        new_root_slug=new_root_slug,
    )


@router.post(
    "/{slug:path}/rename",
    dependencies=[Depends(require_permission("content:write"))],
)
async def rename_page_route(slug: str, payload: RenamePagePayload):
    """
    Rename a page route (slug). Descendant routes are rewritten accordingly.
    Permanent generated redirects are created from old paths to new paths.
    """
    db = _db()
    pages = db["pages"]

    source_slug = slug.strip("/")
    if not source_slug:
        raise HTTPException(400, "Invalid source slug")
    if source_slug == "landing":
        raise HTTPException(400, "The landing page cannot be renamed")

    new_root_slug = str(payload.new_slug or "").strip("/")
    if not new_root_slug:
        raise HTTPException(400, "New slug is required")
    if new_root_slug == "landing":
        raise HTTPException(400, "Renaming to landing is not supported")
    if new_root_slug.startswith(source_slug + "/"):
        raise HTTPException(400, "Cannot rename a page into its own subtree")

    source_doc = await pages.find_one({"slug": source_slug})
    if not source_doc:
        raise HTTPException(404, "Page not found")

    if new_root_slug == source_slug:
        return {
            "ok": True,
            "old_root_slug": source_slug,
            "new_root_slug": new_root_slug,
            "updated_count": 0,
        }

    return await _rewrite_subtree_slugs(
        db,
        source_slug=source_slug,
        new_root_slug=new_root_slug,
    )


async def _rewrite_subtree_slugs(
    db,
    *,
    source_slug: str,
    new_root_slug: str,
) -> dict:
    pages = db["pages"]

    subtree_query = {
        "$or": [
            {"slug": source_slug},
            {"slug": {"$regex": f"^{re.escape(source_slug)}/"}},
        ]
    }
    subtree_docs = await pages.find(subtree_query).to_list(length=5000)
    if not subtree_docs:
        raise HTTPException(404, "Subtree not found")

    subtree_ids = [doc["_id"] for doc in subtree_docs]
    slug_mapping: dict[str, str] = {}
    for doc in subtree_docs:
        old_slug = doc["slug"]
        if old_slug == source_slug:
            slug_mapping[old_slug] = new_root_slug
        else:
            suffix = old_slug[len(source_slug):]
            slug_mapping[old_slug] = f"{new_root_slug}{suffix}"

    new_slugs = list(slug_mapping.values())
    if len(set(new_slugs)) != len(new_slugs):
        raise HTTPException(409, "Slug conflict in destination subtree")

    conflict = await pages.find_one(
        {
            "_id": {"$nin": subtree_ids},
            "slug": {"$in": new_slugs},
        }
    )
    if conflict:
        raise HTTPException(409, f"Destination path already exists: {conflict.get('slug')}")

    now = datetime.utcnow()
    ops = []
    for doc in subtree_docs:
        old_slug = doc["slug"]
        new_slug = slug_mapping[old_slug]
        if old_slug == new_slug:
            continue
        ops.append(
            UpdateOne(
                {"_id": doc["_id"]},
                {"$set": {"slug": new_slug, "updated_at": now}},
            )
        )

    if ops:
        await pages.bulk_write(ops, ordered=False)
        await upsert_generated_redirects_for_slug_mapping(db, slug_mapping)

    return {
        "ok": True,
        "old_root_slug": source_slug,
        "new_root_slug": new_root_slug,
        "updated_count": len(ops),
    }


# IMPORTANT: These catch-all routes must be defined LAST to avoid matching more specific routes
# Routes like /{slug:path}/full, /{slug:path}/sections/*, etc. must be defined BEFORE these

@router.patch(
    "/{slug:path}",
    response_model=PageResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def update_page(
    slug: str,
    payload: PageUpdate,
    user: KeycloakUser = Depends(get_current_user),
):
    """Update a page by its slug. Supports nested slugs with slashes (e.g., 'festival/program')."""
    db = _db()
    pages = db["pages"]
    headers = db["headers"]
    current_page = await pages.find_one({"slug": slug})
    if not current_page:
        raise HTTPException(404, "Not found")
    page_style_locked = _is_template_style_locked(current_page)

    # Use model_fields_set to detect which fields were explicitly provided
    provided = payload.model_fields_set
    needs_design_write = False

    patch = {}
    if "title" in provided and payload.title is not None:
        patch["title"] = payload.title.model_dump()
    if "has_header" in provided:
        patch["has_header"] = payload.has_header
    if "header_id" in provided and payload.header_id is not None:
        # Verify header exists
        header_doc = await headers.find_one({"_id": ObjectId(payload.header_id)})
        if not header_doc:
            raise HTTPException(404, "Header not found")
        patch["header_id"] = payload.header_id
        patch["has_header"] = True

    has_incoming_sections = "sections" in provided and payload.sections is not None
    has_incoming_structure = "section_structure" in provided
    if "sections" in provided and payload.sections is not None:
        next_sections = [s.model_dump() for s in payload.sections]
        section_design_touched = any(
            isinstance(section_ref, dict) and section_ref.get("design_overrides") is not None
            for section_ref in next_sections
        )
        if page_style_locked:
            # Linked template-style pages can still update structure/content,
            # but incoming per-section overrides are ignored.
            for section_ref in next_sections:
                if isinstance(section_ref, dict):
                    section_ref.pop("design_overrides", None)
        elif section_design_touched:
            needs_design_write = True
        patch["sections"] = next_sections
    if has_incoming_sections or has_incoming_structure:
        base_sections = (
            patch.get("sections")
            if isinstance(patch.get("sections"), list)
            else deepcopy(current_page.get("sections"))
            if isinstance(current_page.get("sections"), list)
            else []
        )
        requested_structure = (
            payload.section_structure
            if has_incoming_structure
            else current_page.get("section_structure")
        )
        normalized_sections, normalized_section_structure = _normalize_page_sections_and_structure(
            base_sections,
            requested_structure,
        )
        if page_style_locked:
            for section_ref in normalized_sections:
                if isinstance(section_ref, dict):
                    section_ref.pop("design_overrides", None)
        patch["sections"] = normalized_sections
        patch["section_structure"] = normalized_section_structure
    if "status" in provided:
        if payload.status is not None:
            current_status = _normalize_page_status(current_page.get("status"), fallback="hidden")
            next_status = _normalize_page_status(payload.status, fallback=current_status)
            if next_status == "init" and current_status != "init":
                raise HTTPException(
                    status_code=409,
                    detail="Status 'init' is reserved for newly generated item pages and cannot be restored once changed.",
                )
            patch["status"] = next_status
    if "publish_at" in provided:
        patch["publish_at"] = payload.publish_at  # can be None to clear
    if "unpublish_at" in provided:
        patch["unpublish_at"] = payload.unpublish_at  # can be None to clear
    if "in_menu" in provided:
        patch["in_menu"] = payload.in_menu
    if "in_footer" in provided:
        patch["in_footer"] = payload.in_footer
    if "hide_in_admin_sitemap" in provided:
        patch["hide_in_admin_sitemap"] = payload.hide_in_admin_sitemap
    if "hide_from_sitemap" in provided:
        patch["hide_from_sitemap"] = payload.hide_from_sitemap
    if "hide_subtree_from_sitemap" in provided:
        patch["hide_subtree_from_sitemap"] = payload.hide_subtree_from_sitemap
    if "sitemap_priority" in provided:
        patch["sitemap_priority"] = payload.sitemap_priority
    if "sitemap_changefreq" in provided:
        patch["sitemap_changefreq"] = payload.sitemap_changefreq
    if "generated_from_blog" in provided:
        patch["generated_from_blog"] = payload.generated_from_blog
    if "menu_title" in provided:
        patch["menu_title"] = (
            payload.menu_title.model_dump() if payload.menu_title is not None else None
        )
    if "menu_parent_title" in provided:
        patch["menu_parent_title"] = (
            payload.menu_parent_title.model_dump() if payload.menu_parent_title is not None else None
        )
    if "menu_show_as_top_level" in provided:
        patch["menu_show_as_top_level"] = bool(payload.menu_show_as_top_level)
    if "menu_order" in provided:
        patch["menu_order"] = payload.menu_order
    if "footer_order" in provided:
        patch["footer_order"] = payload.footer_order
    if "redirect_to" in provided:
        patch["redirect_to"] = payload.redirect_to  # can be None to clear
    if "section_bg_pinned_start_key" in provided:
        if page_style_locked:
            raise HTTPException(409, TEMPLATE_STYLE_LOCK_ERROR)
        patch["section_bg_pinned_start_key"] = payload.section_bg_pinned_start_key or ""
        needs_design_write = True
    if "section_bg_pinned_end_key" in provided:
        if page_style_locked:
            raise HTTPException(409, TEMPLATE_STYLE_LOCK_ERROR)
        patch["section_bg_pinned_end_key"] = payload.section_bg_pinned_end_key or ""
        needs_design_write = True
    if "page_design_overrides" in provided:
        if page_style_locked:
            raise HTTPException(409, TEMPLATE_STYLE_LOCK_ERROR)
        patch["page_design_overrides"] = payload.page_design_overrides
        needs_design_write = True

    if not patch:
        raise HTTPException(400, "No fields to update")

    if needs_design_write:
        _require_design_write(user)

    slug_finalize_mapping = await _finalize_pending_template_item_slug_on_publish(
        db,
        current_page=current_page,
        patch=patch,
        provided_fields=provided,
    )

    patch["updated_at"] = datetime.utcnow()

    res = await pages.find_one_and_update(
        {"_id": current_page["_id"]},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    if not res:
        raise HTTPException(404, "Not found")

    if slug_finalize_mapping:
        old_slug, new_slug = slug_finalize_mapping
        if old_slug and new_slug and old_slug != new_slug:
            await upsert_generated_redirects_for_slug_mapping(
                db,
                {old_slug: new_slug},
                reason="template_item_publish_slug_finalize",
            )
        await _sync_template_source_link_for_page_slug(db, res)

    try:
        await sync_generated_item_page_review_overrides_for_saved_targets(
            db,
            collection="page",
            document_id=res.get("_id"),
            saved_doc=res,
            updated_paths=set(patch.keys()),
        )
    except Exception:
        logger.warning(
            "generated_item_page.review_override_page_sync_failed slug=%s",
            str(res.get("slug") or slug),
            exc_info=True,
        )

    return _format_page_response(res)


@router.get(
    "/{slug:path}",
    response_model=PageResponse,
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_page(slug: str):
    """Get a page by its slug. Supports nested slugs with slashes (e.g., 'festival/program')."""
    db = _db()
    pages = db["pages"]
    
    doc = await pages.find_one({"slug": slug})
    if not doc:
        raise HTTPException(404, "Not found")
    
    return _format_page_response(doc)


def _parse_datetime(dt) -> datetime | None:
    """Parse datetime from various formats, ensuring UTC timezone."""
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _normalize_page_status(status, *, fallback: str = "hidden") -> str:
    raw = str(status or "").strip().lower()
    if raw == "draft":
        return "hidden"
    if raw in {"init", "hidden", "published", "under_construction"}:
        return raw
    return fallback


def _compute_effective_status(doc: dict) -> str:
    """
    Compute the effective status of a page based on scheduling.

    Rules:
    - Base status is normalized ("draft" behaves like "hidden")
    - unpublish_at takes precedence: if in the past, page becomes hidden
    - If publish_at is set and in the future, page is hidden until that time
    - If publish_at is set and in the past while base status is hidden/init, page becomes published
    - Otherwise use the normalized base status
    """
    now = datetime.now(timezone.utc)
    base_status = _normalize_page_status(doc.get("status"), fallback="hidden")
    publish_at = _parse_datetime(doc.get("publish_at"))
    unpublish_at = _parse_datetime(doc.get("unpublish_at"))

    # Check unpublish first (takes precedence)
    if unpublish_at and unpublish_at <= now:
        return "hidden"

    # Check publish scheduling
    if publish_at:
        if publish_at > now:
            return "hidden"
        # Scheduled hidden/init/draft pages become published once publish_at is reached.
        if _is_hidden_like_page_status(base_status):
            return "published"

    if base_status == "init":
        return "hidden"

    return base_status


def _is_page_visible(doc: dict) -> bool:
    """Check if a page is currently publicly reachable."""
    return _compute_effective_status(doc) in {"published", "under_construction"}


def _format_page_response(doc: dict) -> dict:
    """Format a page document for the response."""
    now = datetime.now(timezone.utc)
    status = _normalize_page_status(doc.get("status"), fallback="hidden")
    effective_status = _compute_effective_status(doc)
    template_style_linked = _is_template_style_linked(doc)
    sections_payload = (
        deepcopy(doc.get("sections"))
        if isinstance(doc.get("sections"), list)
        else []
    )
    sections_payload, normalized_section_structure = _normalize_page_sections_and_structure(
        sections_payload,
        doc.get("section_structure"),
    )
    if template_style_linked:
        for section_ref in sections_payload:
            if isinstance(section_ref, dict):
                section_ref.pop("design_overrides", None)
    
    # Get schedule times and ensure they're timezone-aware
    publish_at = _parse_datetime(doc.get("publish_at"))
    unpublish_at = _parse_datetime(doc.get("unpublish_at"))
    
    # Clear schedule times only after they've successfully triggered their intended effect:
    # - publish_at: clear only if it triggered AND page is now published
    # - unpublish_at: clear only if it triggered AND page is now hidden (due to unpublish)
    publish_triggered = publish_at and publish_at <= now and effective_status == "published"
    unpublish_triggered = unpublish_at and unpublish_at <= now and effective_status == "hidden"
    
    publish_at_response = None if publish_triggered else _format_datetime_response(publish_at)
    unpublish_at_response = None if unpublish_triggered else _format_datetime_response(unpublish_at)
    
    return {
        "id": str(doc["_id"]),
        "slug": doc.get("slug"),
        "title": doc.get("title", {"de": "", "en": ""}),
        "has_header": doc.get("has_header", False),
        "header_id": doc.get("header_id"),
        "sections": sections_payload,
        "section_structure": normalized_section_structure,
        "status": status,
        "effective_status": effective_status,
        "is_visible": effective_status == "published",
        "publish_at": publish_at_response,
        "unpublish_at": unpublish_at_response,
        "in_menu": doc.get("in_menu", False),
        "in_footer": doc.get("in_footer", False),
        "hide_in_admin_sitemap": doc.get("hide_in_admin_sitemap", False),
        "hide_from_sitemap": doc.get("hide_from_sitemap", False),
        "hide_subtree_from_sitemap": doc.get("hide_subtree_from_sitemap", False),
        "sitemap_priority": doc.get("sitemap_priority"),
        "sitemap_changefreq": doc.get("sitemap_changefreq"),
        "generated_from_blog": doc.get("generated_from_blog", False),
        "menu_title": doc.get("menu_title"),
        "menu_parent_title": doc.get("menu_parent_title"),
        "menu_show_as_top_level": doc.get("menu_show_as_top_level", False),
        "menu_order": doc.get("menu_order", 0),
        "footer_order": doc.get("footer_order", 0),
        "redirect_to": doc.get("redirect_to"),
        "section_bg_pinned_start_key": doc.get("section_bg_pinned_start_key", ""),
        "section_bg_pinned_end_key": doc.get("section_bg_pinned_end_key", ""),
        "page_design_overrides": None if template_style_linked else doc.get("page_design_overrides"),
        "template_style_ref": str(doc.get("template_style_ref") or "").strip() or None,
        "template_style_linked": template_style_linked,
        "template_style_lock": _is_template_style_locked(doc),
        "template_managed": bool(doc.get("template_managed", False)),
        "template_source_type": str(doc.get("template_source_type") or "").strip() or None,
        "template_source_id": str(doc.get("template_source_id") or "").strip() or None,
        "template_integration_id": str(doc.get("template_integration_id") or "").strip() or None,
        "template_integration_item_key": str(doc.get("template_integration_item_key") or "").strip() or None,
        "anonymous_hit_count": max(0, int(doc.get("anonymous_hit_count") or 0)),
        "created_at": _format_datetime_response(doc.get("created_at")),
        "updated_at": _format_datetime_response(doc.get("updated_at")),
    }
