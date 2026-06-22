from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from pymongo import ReturnDocument

from app.collection_names import (
    TEMPLATE_CONTAINERS_COLLECTION,
    TEMPLATE_PAGES_COLLECTION,
    TEMPLATE_SECTIONS_COLLECTION,
)
from app.db import get_client
from app.deps import get_current_user, require_permission
from app.font_cache import resolve_font_cache_for_design
from app.security import KeycloakUser
from app.section_structure import (
    apply_section_order_from_structure,
    resolve_section_structure,
    strip_legacy_container_override,
)
from app.settings import settings
from app.template_sync import (
    SECTION_TEMPLATE_SYNC_FIELDS,
    apply_item_page_routes,
    get_item_page_config,
    set_item_page_config,
    build_builder_header_id_for_page,
    build_header_document_from_template_header,
    build_template_key_for_container,
    build_template_key_for_page,
    build_template_key_for_section,
    build_section_document_from_embedded_section,
    build_page_full_payload_for_template_container,
    build_page_full_payload_for_template_page,
    build_page_full_payload_for_template_section,
    capture_item_page_routes,
    changed_item_page_mapping_target_keys,
    cleanup_generated_item_pages_for_template,
    compose_page_template_path,
    compose_item_page_effective_parent_route,
    ensure_container_template_section_structure,
    effective_item_page_parent_route_for_template,
    format_embedded_section_for_builder,
    item_page_config_key_prefix,
    item_page_source_type_key,
    normalize_page_template_path_value,
    page_template_path_matches_item_effective_route,
    normalize_container_template_doc,
    normalize_embedded_section,
    normalize_embedded_sections_and_structure,
    normalize_page_template_doc,
    normalize_item_page_slug_field,
    normalize_item_page_source_context,
    normalize_item_page_subroute,
    normalize_section_template_ref,
    normalize_parent_route,
    normalize_fixed_gig_page_mapping_sources,
    normalize_section_template_doc,
    normalize_template_name,
    page_mapping_fixed_gig_needs_primary_fallback,
    page_mapping_has_fixed_gig_target,
    migrate_generated_item_pages_parent_route,
    parse_builder_header_id,
    parse_builder_section_id,
    parse_page_template_path,
    resolve_page_integration_mapping_for_template_doc,
    resolve_global_published_design_snapshot,
    regenerate_all_item_pages_for_template,
    resolve_section_template_sync_context,
    sync_all_blog_items_for_route,
    sync_init_generated_item_pages_for_template,
    preview_item_page_mapping_from_template_state,
)

router = APIRouter(prefix="/admin/templates", tags=["admin-templates"])

CONTAINER_TEMPLATE_LOCK_KEY = "_templateContainerLock"
CONTAINER_TEMPLATE_NAME_KEY = "_templateContainerName"


def _db():
    return get_client()[settings.mongo_db]


def _require_design_write(user: KeycloakUser) -> None:
    if user.has_permission("design:write"):
        return
    raise HTTPException(
        status_code=403,
        detail="Missing required permissions: design:write",
    )


def _safe_object_id(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _normalize_page_status(value: Any, *, fallback: str = "hidden") -> str:
    raw = str(value or "").strip().lower()
    if raw == "draft":
        return "hidden"
    if raw in {"init", "hidden", "published", "under_construction"}:
        return raw
    return fallback


def _effective_page_status_from_stored(value: Any) -> str:
    normalized = _normalize_page_status(value, fallback="hidden")
    return "hidden" if normalized == "init" else normalized


def _format_doc(doc: dict) -> dict:
    result = dict(doc)
    if "_id" in result:
        result["id"] = str(result["_id"])
        del result["_id"]
    if "template_name" in result and "parent_route" in result:
        result["path"] = compose_page_template_path(
            str(result.get("template_name") or ""),
            result.get("parent_route"),
        )
        page_integration_mapping = resolve_page_integration_mapping_for_template_doc(result)
        result["page_integration_mapping"] = page_integration_mapping
    return result


async def _generated_item_page_count_for_template_doc(db, template_doc: dict | None) -> int:
    if not _is_item_page_template_doc(template_doc):
        return 0
    template_name = normalize_template_name(
        template_doc.get("template_name") or "default",
        default="default",
    )
    parent_route = normalize_parent_route(template_doc.get("parent_route"))
    template_path = compose_page_template_path(template_name, parent_route)
    template_key = build_template_key_for_page(template_name, parent_route)
    effective_parent_route = effective_item_page_parent_route_for_template(template_doc)
    parent_routes = [
        route
        for route in {
            normalize_parent_route(parent_route),
            normalize_parent_route(effective_parent_route),
        }
        if route
    ]

    identity_filters: list[dict[str, Any]] = [
        {"template_key": template_key},
        {"template_style_ref": template_path},
    ]
    if parent_routes:
        identity_filters.append(
            {
                "template_template_name": template_name,
                "template_parent_route": {"$in": parent_routes},
            }
        )

    query: dict[str, Any] = {
        "template_managed": True,
        "$or": identity_filters,
    }
    return int(await db["pages"].count_documents(query))


async def _format_page_template_doc(db, doc: dict) -> dict:
    result = _format_doc(doc)
    result["generated_item_page_count"] = await _generated_item_page_count_for_template_doc(db, doc)
    return result


async def _apply_page_mapping_fixed_gig_primary_key_sources(db, page_doc: dict) -> None:
    if not isinstance(page_doc, dict):
        return
    page_integration_mapping = resolve_page_integration_mapping_for_template_doc(page_doc)
    if not page_mapping_has_fixed_gig_target(page_integration_mapping):
        page_doc["page_integration_mapping"] = page_integration_mapping
        return

    integration_id = str(page_integration_mapping.get("selected_integration_id") or "").strip()
    integration_oid = _safe_object_id(integration_id)
    integration_doc = (
        await db["integration_config"].find_one(
            {"_id": integration_oid},
            {"output_primary_key_path": 1},
        )
        if integration_oid is not None
        else None
    )
    output_primary_key_path = (
        str((integration_doc or {}).get("output_primary_key_path") or "").strip()
        if isinstance(integration_doc, dict)
        else ""
    )
    if (
        not output_primary_key_path
        and page_mapping_fixed_gig_needs_primary_fallback(page_integration_mapping)
    ):
        raise HTTPException(
            400,
            "Fixed gig mappings require an External ID on the selected integration",
        )
    page_doc["page_integration_mapping"] = normalize_fixed_gig_page_mapping_sources(
        page_integration_mapping,
        output_primary_key_path,
    )


async def _sync_init_generated_pages_for_template_doc(db, template_doc: dict | None) -> None:
    if isinstance(template_doc, dict):
        await sync_init_generated_item_pages_for_template(db, template_doc)


async def _sync_init_generated_pages_for_template_doc_scoped(
    db,
    template_doc: dict | None,
    mapped_target_keys: set[str] | list[str] | tuple[str, ...] | None,
) -> None:
    if isinstance(template_doc, dict):
        normalized_keys = (
            {str(key or "").strip() for key in mapped_target_keys if str(key or "").strip()}
            if isinstance(mapped_target_keys, (set, list, tuple))
            else None
        )
        await sync_init_generated_item_pages_for_template(
            db,
            template_doc,
            mapped_target_keys=normalized_keys,
        )


def _queue_init_generated_pages_sync(
    background_tasks: BackgroundTasks,
    db,
    template_doc: dict | None,
    *,
    mapped_target_keys: set[str] | list[str] | tuple[str, ...] | None = None,
) -> None:
    if isinstance(template_doc, dict):
        background_tasks.add_task(
            _sync_init_generated_pages_for_template_doc_scoped,
            db,
            deepcopy(template_doc),
            list(mapped_target_keys) if isinstance(mapped_target_keys, (set, list, tuple)) else None,
        )


def _normalize_builder_structure_ids(
    section_structure: Any,
    *,
    sections: Any,
    owner_kind: str,
    owner_id: Any,
) -> Any:
    if not isinstance(section_structure, list):
        return section_structure

    embedded_ids = {
        str(section.get("id") or "").strip()
        for section in sections if isinstance(section, dict)
        if str(section.get("id") or "").strip()
    }
    owner_id_text = str(owner_id or "").strip()
    normalized_nodes: list[dict[str, Any]] = []

    for node in section_structure:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type") or "").strip().lower()
        if node_type == "section":
            raw_section_id = str(node.get("section_id") or "").strip()
            if not raw_section_id:
                continue
            normalized_section_id = raw_section_id
            if raw_section_id not in embedded_ids:
                try:
                    parsed_kind, parsed_owner_id, parsed_embedded_id = parse_builder_section_id(raw_section_id)
                except ValueError:
                    parsed_kind = parsed_owner_id = parsed_embedded_id = None
                if (
                    parsed_kind == owner_kind
                    and str(parsed_owner_id or "").strip() == owner_id_text
                    and str(parsed_embedded_id or "").strip()
                ):
                    normalized_section_id = str(parsed_embedded_id).strip()
            normalized_nodes.append(
                {
                    "type": "section",
                    "section_id": normalized_section_id,
                }
            )
            continue
        if node_type != "container":
            continue
        normalized_members: list[str] = []
        raw_members = node.get("section_ids") if isinstance(node.get("section_ids"), list) else []
        for raw_member in raw_members:
            raw_member_id = str(raw_member or "").strip()
            if not raw_member_id:
                continue
            normalized_member_id = raw_member_id
            if raw_member_id not in embedded_ids:
                try:
                    parsed_kind, parsed_owner_id, parsed_embedded_id = parse_builder_section_id(raw_member_id)
                except ValueError:
                    parsed_kind = parsed_owner_id = parsed_embedded_id = None
                if (
                    parsed_kind == owner_kind
                    and str(parsed_owner_id or "").strip() == owner_id_text
                    and str(parsed_embedded_id or "").strip()
                ):
                    normalized_member_id = str(parsed_embedded_id).strip()
            normalized_members.append(normalized_member_id)
        normalized_nodes.append(
            {
                "type": "container",
                "container_id": str(node.get("container_id") or "").strip() or _new_container_instance_id(),
                "section_ids": normalized_members,
            }
        )

    return normalized_nodes


def _normalize_builder_embedded_sections(
    sections: Any,
    section_structure: Any,
    *,
    owner_kind: str,
    owner_id: Any,
) -> tuple[list[dict], list[dict]]:
    normalized_input_structure = _normalize_builder_structure_ids(
        section_structure,
        sections=sections,
        owner_kind=owner_kind,
        owner_id=owner_id,
    )
    normalized_sections, normalized_structure = normalize_embedded_sections_and_structure(
        sections,
        normalized_input_structure,
    )
    if owner_kind == "container":
        ordered_ids = [
            str(section.get("id") or "").strip()
            for section in normalized_sections
            if isinstance(section, dict) and str(section.get("id") or "").strip()
        ]
        normalized_structure = ensure_container_template_section_structure(
            normalized_structure,
            ordered_ids,
        )
        normalized_sections = apply_section_order_from_structure(
            normalized_sections,
            normalized_structure,
            section_id_field="id",
        )
    for section in normalized_sections:
        if not isinstance(section, dict):
            continue
        overrides = strip_legacy_container_override(section.get("design_overrides"))
        if overrides is None:
            section.pop("design_overrides", None)
        else:
            section["design_overrides"] = overrides
    return normalized_sections, normalized_structure


def _coerce_builder_page_preview_sections(
    sections: Any,
    *,
    owner_id: Any,
) -> list[dict]:
    if not isinstance(sections, list):
        return []
    owner_id_text = str(owner_id or "").strip()
    coerced: list[dict] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        next_section = deepcopy(section)
        embedded_id = str(next_section.get("template_embedded_section_id") or "").strip()
        if not embedded_id:
            raw_id = str(next_section.get("id") or next_section.get("_id") or "").strip()
            try:
                parsed_kind, parsed_owner_id, parsed_embedded_id = parse_builder_section_id(raw_id)
            except ValueError:
                parsed_kind = parsed_owner_id = parsed_embedded_id = None
            if (
                parsed_kind == "page"
                and str(parsed_owner_id or "").strip() == owner_id_text
                and str(parsed_embedded_id or "").strip()
            ):
                embedded_id = str(parsed_embedded_id).strip()
        if embedded_id:
            next_section["id"] = embedded_id
        coerced.append(next_section)
    return coerced


def _builder_page_preview_request_template_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}
    for key in ("template", "builder_payload", "template_payload"):
        value = payload.get(key)
        if isinstance(value, dict):
            return deepcopy(value)
    return deepcopy(payload)


async def _normalize_builder_page_mapping_preview_doc(
    db,
    *,
    path: str,
    saved_doc: dict,
    payload: dict,
) -> dict:
    template_name, parent_route = parse_page_template_path(path)
    normalized_path = compose_page_template_path(template_name, parent_route)
    request_template = _builder_page_preview_request_template_payload(payload)
    request_mapping = payload.get("page_integration_mapping") if isinstance(payload, dict) else None
    merged = {
        **deepcopy(saved_doc),
        **request_template,
        "template_name": template_name,
        "parent_route": parent_route,
    }
    if isinstance(request_mapping, dict):
        merged["page_integration_mapping"] = deepcopy(request_mapping)

    owner_id = saved_doc.get("_id") or request_template.get("id") or request_template.get("_id")
    if isinstance(request_template.get("sections"), list):
        merged["sections"] = _coerce_builder_page_preview_sections(
            request_template.get("sections"),
            owner_id=owner_id,
        )
    if "section_structure" in request_template:
        merged["section_structure"] = _normalize_builder_structure_ids(
            request_template.get("section_structure"),
            sections=merged.get("sections") if isinstance(merged.get("sections"), list) else saved_doc.get("sections"),
            owner_kind="page",
            owner_id=owner_id,
        )

    normalized = normalize_page_template_doc(normalized_path, merged)
    normalized["_id"] = saved_doc.get("_id") or _safe_object_id(request_template.get("id")) or ObjectId()
    normalized["created_at"] = saved_doc.get("created_at")
    normalized["updated_at"] = saved_doc.get("updated_at")
    normalized["template_design_current"] = (
        deepcopy(request_template.get("template_design_current"))
        if isinstance(request_template.get("template_design_current"), dict)
        else deepcopy(saved_doc.get("template_design_current"))
        if isinstance(saved_doc.get("template_design_current"), dict)
        else None
    )
    normalized["template_design_published"] = (
        deepcopy(request_template.get("template_design_published"))
        if isinstance(request_template.get("template_design_published"), dict)
        else deepcopy(saved_doc.get("template_design_published"))
        if isinstance(saved_doc.get("template_design_published"), dict)
        else None
    )
    normalized["template_design_initialized_from_global_version_id"] = (
        str(
            request_template.get("template_design_initialized_from_global_version_id")
            or saved_doc.get("template_design_initialized_from_global_version_id")
            or ""
        ).strip()
        or None
    )
    normalized["template_design_updated_at"] = (
        saved_doc.get("template_design_updated_at")
        if isinstance(saved_doc.get("template_design_updated_at"), datetime)
        else None
    )
    normalized["template_design_published_at"] = (
        saved_doc.get("template_design_published_at")
        if isinstance(saved_doc.get("template_design_published_at"), datetime)
        else None
    )
    normalized["page_design_overrides"] = None
    return normalized


def _template_sync_preview_response(
    section_id: str,
    section_type: str,
    template_name: str,
    changed_fields: list[str],
) -> dict:
    return {
        "section_id": section_id,
        "section_type": section_type,
        "template_name": template_name,
        "template_ref": f"{section_type}/{template_name}",
        "has_changes": bool(changed_fields),
        "changed_fields": changed_fields,
        "field_status": [
            {
                "field": field,
                "changed": field in changed_fields,
            }
            for field in SECTION_TEMPLATE_SYNC_FIELDS
        ],
    }


async def _resolve_builder_section_template_sync_context(
    db,
    *,
    kind: str,
    section_id: str,
) -> tuple[str, str, str, ObjectId, dict, list[dict], int, str, str, dict, dict, list[str]]:
    try:
        owner_kind, owner_id, embedded_id = parse_builder_section_id(section_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if owner_kind != kind:
        raise HTTPException(400, "Section owner does not match builder kind")
    if owner_kind not in {"page", "container"} or not embedded_id:
        raise HTTPException(400, "Template sync is only available for embedded template sections")

    target_coll_name = TEMPLATE_PAGES_COLLECTION if owner_kind == "page" else TEMPLATE_CONTAINERS_COLLECTION
    oid = _safe_object_id(owner_id)
    if oid is None:
        raise HTTPException(400, "Invalid template id")

    doc = await db[target_coll_name].find_one({"_id": oid})
    if not isinstance(doc, dict):
        raise HTTPException(404, "Template not found")

    sections = doc.get("sections") if isinstance(doc.get("sections"), list) else []
    target_index = next(
        (
            idx
            for idx, section in enumerate(sections)
            if isinstance(section, dict) and str(section.get("id")) == embedded_id
        ),
        None,
    )
    if target_index is None:
        raise HTTPException(404, "Section not found in template")

    current_section = sections[target_index]
    try:
        (
            section_type,
            template_name,
            template_payload,
            current_payload,
            changed_fields,
        ) = await resolve_section_template_sync_context(db, current_section)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc

    return (
        owner_kind,
        embedded_id,
        target_coll_name,
        oid,
        doc,
        sections,
        target_index,
        section_type,
        template_name,
        template_payload,
        current_payload,
        changed_fields,
    )


def _new_container_instance_id() -> str:
    return f"tplc_{ObjectId()}"


def _compose_page_template_style_ref(template_name: str, parent_route: str | None) -> str:
    return compose_page_template_path(template_name, parent_route)


async def _ensure_template_page_design_state(
    db,
    template_doc: dict,
    *,
    base_design: dict | None = None,
    base_version_id: str | None = None,
) -> dict:
    if not isinstance(template_doc, dict):
        return template_doc

    now = datetime.utcnow()
    current_design = (
        deepcopy(template_doc.get("template_design_current"))
        if isinstance(template_doc.get("template_design_current"), dict)
        else None
    )
    published_design = (
        deepcopy(template_doc.get("template_design_published"))
        if isinstance(template_doc.get("template_design_published"), dict)
        else None
    )
    base_snapshot = deepcopy(base_design) if isinstance(base_design, dict) else {}

    if current_design is None and published_design is None:
        seeded = deepcopy(base_snapshot)
        current_design = deepcopy(seeded)
        published_design = deepcopy(seeded)
    elif current_design is None and published_design is not None:
        current_design = deepcopy(published_design)
    elif published_design is None and current_design is not None:
        published_design = deepcopy(current_design)

    initialized_version_id = (
        str(template_doc.get("template_design_initialized_from_global_version_id") or "").strip() or None
    )
    if initialized_version_id is None and base_version_id:
        initialized_version_id = str(base_version_id).strip() or None

    template_design_updated_at = template_doc.get("template_design_updated_at")
    if not isinstance(template_design_updated_at, datetime):
        template_design_updated_at = now
    template_design_published_at = template_doc.get("template_design_published_at")
    if not isinstance(template_design_published_at, datetime):
        template_design_published_at = now

    next_doc = {
        **template_doc,
        "template_design_current": current_design if isinstance(current_design, dict) else {},
        "template_design_published": published_design if isinstance(published_design, dict) else {},
        "template_design_initialized_from_global_version_id": initialized_version_id,
        "template_design_updated_at": template_design_updated_at,
        "template_design_published_at": template_design_published_at,
        "page_design_overrides": None,
    }

    changed = (
        template_doc.get("template_design_current") != next_doc["template_design_current"]
        or template_doc.get("template_design_published") != next_doc["template_design_published"]
        or (template_doc.get("template_design_initialized_from_global_version_id") or None)
        != next_doc["template_design_initialized_from_global_version_id"]
        or template_doc.get("page_design_overrides") is not None
    )
    if not changed:
        return next_doc

    await db[TEMPLATE_PAGES_COLLECTION].update_one(
        {"_id": template_doc["_id"]},
        {"$set": {
            "template_design_current": next_doc["template_design_current"],
            "template_design_published": next_doc["template_design_published"],
            "template_design_initialized_from_global_version_id": next_doc["template_design_initialized_from_global_version_id"],
            "template_design_updated_at": next_doc["template_design_updated_at"],
            "template_design_published_at": next_doc["template_design_published_at"],
            "page_design_overrides": None,
            "updated_at": now,
        }},
    )
    next_doc["updated_at"] = now
    return next_doc


async def _copy_template_snippets(from_key: str, to_key: str) -> None:
    source_key = str(from_key or "").strip()
    target_key = str(to_key or "").strip()
    if not source_key or not target_key:
        return
    if source_key == target_key:
        return

    coll = _db()["css_snippets"]
    docs = await coll.find(
        {
            "scope": "template",
            "template_key": source_key,
        }
    ).to_list(length=2000)
    if not docs:
        return

    now = datetime.utcnow()
    inserts: list[dict[str, Any]] = []
    for row in docs:
        snippet = _strip_mongo_meta(row)
        if not isinstance(snippet, dict):
            continue
        snippet["scope"] = "template"
        snippet["template_key"] = target_key
        snippet["created_at"] = now
        snippet["updated_at"] = now
        inserts.append(snippet)

    if inserts:
        await coll.insert_many(inserts)


async def _move_template_snippets(from_key: str, to_key: str) -> None:
    source_key = str(from_key or "").strip()
    target_key = str(to_key or "").strip()
    if not source_key or not target_key:
        return
    if source_key == target_key:
        return
    await _db()["css_snippets"].update_many(
        {
            "scope": "template",
            "template_key": source_key,
        },
        {
            "$set": {
                "template_key": target_key,
                "updated_at": datetime.utcnow(),
            }
        },
    )


def _normalize_bilingual_text(value: Any, fallback: dict | None = None) -> dict:
    fallback_value = fallback if isinstance(fallback, dict) else {"de": "", "en": ""}
    if not isinstance(value, dict):
        value = {}
    return {
        "de": str(value.get("de") or fallback_value.get("de") or ""),
        "en": str(value.get("en") or fallback_value.get("en") or ""),
    }


def _strip_mongo_meta(value: Any) -> Any:
    if isinstance(value, list):
        return [_strip_mongo_meta(entry) for entry in value]
    if not isinstance(value, dict):
        return value
    cleaned = {}
    for key, entry in value.items():
        if key == "_id":
            continue
        cleaned[key] = _strip_mongo_meta(entry)
    return cleaned


def _merge_dict(base: dict | None, patch: dict | None) -> dict:
    merged = deepcopy(base) if isinstance(base, dict) else {}
    if not isinstance(patch, dict):
        return merged
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged.get(key), value)
        else:
            merged[key] = deepcopy(value)
    return merged


async def _create_section_document_from_template(
    db,
    section_payload: dict,
    *,
    now: datetime,
) -> str:
    doc = build_section_document_from_embedded_section(section_payload, now=now)
    result = await db["sections"].insert_one(doc)
    return str(result.inserted_id)


async def _create_header_document_from_template(
    db,
    header_payload: dict | None,
    *,
    now: datetime,
) -> str | None:
    doc = build_header_document_from_template_header(header_payload, now=now)
    if doc is None:
        return None
    result = await db["headers"].insert_one(doc)
    return str(result.inserted_id)


def _parse_section_builder_path(path: str) -> tuple[str, str]:
    raw = str(path or "").strip().strip("/")
    parts = [part for part in raw.split("/") if part]
    if not parts:
        raise ValueError("Section template path is required")
    section_type = _normalize_section_type(parts[0], default="text")
    template_name = normalize_template_name(parts[1], default="default") if len(parts) > 1 else "default"
    return section_type, template_name


def _normalize_source_route_ref(value: Any) -> str | None:
    raw = str(value or "").strip()
    return raw or None


async def _resolve_source_route_by_ref(db, source_route_ref: Any) -> dict | None:
    normalized_ref = _normalize_source_route_ref(source_route_ref)
    if not normalized_ref:
        return None
    routes = await capture_item_page_routes(db)
    for route_entry in routes:
        if str(route_entry.get("source_route_ref") or "") == normalized_ref:
            return route_entry
    return None


async def _build_page_template_path_for_payload(db, payload: dict) -> str:
    source_route_ref = _normalize_source_route_ref(payload.get("source_route_ref"))
    template_name = normalize_template_name(payload.get("template_name"), default="default")
    if not source_route_ref:
        requested_path = payload.get("path")
        if requested_path:
            normalized_requested_path = normalize_page_template_path_value(requested_path)
            if not normalized_requested_path:
                raise HTTPException(400, "Invalid template path")
            return normalized_requested_path
        parent_route = normalize_parent_route(payload.get("parent_route"))
        return compose_page_template_path(template_name, parent_route)

    route_entry = await _resolve_source_route_by_ref(db, source_route_ref)
    if not isinstance(route_entry, dict):
        raise HTTPException(400, f'Unknown source_route_ref "{source_route_ref}"')
    parent_route = normalize_parent_route(route_entry.get("parent_route"))
    if not parent_route:
        raise HTTPException(400, f'Source route "{source_route_ref}" has no valid parent_route')
    return compose_page_template_path(template_name, parent_route)


async def _inject_source_route_payload_fields(db, payload: dict, normalized: dict) -> dict:
    source_route_ref = _normalize_source_route_ref(
        payload.get("source_route_ref")
        if payload.get("source_route_ref") is not None
        else normalized.get("source_route_ref")
    )
    if not source_route_ref:
        return normalized

    route_entry = await _resolve_source_route_by_ref(db, source_route_ref)
    if not isinstance(route_entry, dict):
        raise HTTPException(400, f'Unknown source_route_ref "{source_route_ref}"')

    source_type = str(route_entry.get("source_type") or "").strip().lower()
    source_kind = str(route_entry.get("source_kind") or "").strip().lower()
    parent_route = normalize_parent_route(route_entry.get("parent_route"))
    if source_type not in {"blog", "program"}:
        raise HTTPException(400, "source_route_ref must point to blog/program route")
    if source_kind not in {"item", "stage", "gig"}:
        source_kind = "item" if source_type == "blog" else "gig"

    normalized["source_route_ref"] = source_route_ref
    normalized["source_type"] = source_type
    normalized["source_kind"] = source_kind
    normalized["parent_route"] = parent_route
    if not normalized.get("section_template_ref"):
        normalized["section_template_ref"] = (
            normalize_section_template_ref(route_entry.get("section_template_ref"))
            or normalize_section_template_ref(f"{source_type}/default")
        )
    return normalized


async def _validate_source_route_ref_matches_template_path(db, normalized: dict) -> None:
    source_route_ref = _normalize_source_route_ref(normalized.get("source_route_ref"))
    if not source_route_ref:
        return
    route_entry = await _resolve_source_route_by_ref(db, source_route_ref)
    if not isinstance(route_entry, dict):
        raise HTTPException(400, f'Unknown source_route_ref "{source_route_ref}"')
    route_parent = normalize_parent_route(route_entry.get("parent_route"))
    template_parent = normalize_parent_route(normalized.get("parent_route"))
    if route_parent != template_parent:
        raise HTTPException(
            400,
            "source_route_ref parent route does not match the template path route",
        )


def _parse_container_builder_path(path: str) -> str:
    raw = str(path or "").strip().strip("/")
    if not raw:
        raise ValueError("Container template path is required")
    return normalize_template_name(raw)


def _normalize_section_type(value: Any, *, default: str = "text") -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    raw = re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")
    return raw or default


def _page_template_query(template_name: str, parent_route: str | None) -> dict:
    if parent_route is None:
        return {"template_name": template_name, "parent_route": None}
    return {"template_name": template_name, "parent_route": parent_route}


async def _find_item_template_for_effective_route_path(
    db,
    path: str,
    *,
    exclude_id: Any = None,
) -> dict | None:
    try:
        parse_page_template_path(path)
    except ValueError:
        return None

    query = {
        "$or": [
            {"template_kind": "item_page"},
            {"source_type": {"$in": ["blog", "program", "tiles"]}},
            {"parent_route": {"$ne": None}},
        ],
    }
    projection = {
        "_id": 1,
        "template_name": 1,
        "parent_route": 1,
        "template_kind": 1,
        "source_type": 1,
        "source_kind": 1,
        "item_page_subroute": 1,
    }
    docs = await db[TEMPLATE_PAGES_COLLECTION].find(query, projection).to_list(length=1000)
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        if exclude_id is not None and doc.get("_id") == exclude_id:
            continue
        if page_template_path_matches_item_effective_route(path, doc):
            return doc
    return None


def _item_template_conflict_detail(path: str, template_doc: dict) -> str:
    template_name = normalize_template_name(
        template_doc.get("template_name") or "default",
        default="default",
    )
    template_path = compose_page_template_path(
        template_name,
        normalize_parent_route(template_doc.get("parent_route")),
    )
    effective_route = effective_item_page_parent_route_for_template(template_doc)
    source_context = normalize_item_page_source_context(
        template_doc.get("source_type"),
        template_doc.get("source_kind"),
    )
    if source_context == ("program", "gig"):
        source_label = "program gig"
    elif source_context == ("program", "stage"):
        source_label = "program stage"
    elif source_context == ("blog", "item"):
        source_label = "blog"
    else:
        source_label = str(template_doc.get("source_type") or "item-page").strip() or "item-page"
    normalized_path = normalize_page_template_path_value(path) or str(path or "").strip().strip("/")
    return (
        f'Page template path "{normalized_path}" matches the generated route '
        f'"{effective_route}" for the {source_label} template "{template_path}". '
        f'Use "{template_path}" as the template path, and keep the subroute in routing settings.'
    )


async def _raise_if_page_template_path_is_item_route(
    db,
    path: str,
    *,
    exclude_id: Any = None,
) -> None:
    template_doc = await _find_item_template_for_effective_route_path(
        db,
        path,
        exclude_id=exclude_id,
    )
    if template_doc:
        raise HTTPException(409, _item_template_conflict_detail(path, template_doc))


def _is_item_page_template_doc(template_doc: dict | None) -> bool:
    if not isinstance(template_doc, dict):
        return False
    template_kind = str(template_doc.get("template_kind") or "").strip().lower()
    if template_kind == "item_page":
        return True
    if normalize_parent_route(template_doc.get("parent_route")):
        return True
    source_type = str(template_doc.get("source_type") or "").strip().lower()
    return source_type in {"blog", "program", "tiles"}


def _item_page_section_type_for_source(source_type: str, source_kind: str) -> str | None:
    source_context = normalize_item_page_source_context(source_type, source_kind)
    if not source_context:
        return None
    return source_context[0]


def _source_type_key_for_template_doc(template_doc: dict) -> str | None:
    source_type = str(template_doc.get("source_type") or "").strip().lower()
    source_kind = str(template_doc.get("source_kind") or "").strip().lower()
    return item_page_source_type_key(source_type, source_kind)


ITEM_PAGE_CONFIG_TEMPLATE_SPECS = (
    ("blog_item_template_path", "blog", "item"),
    ("program_stage_template_path", "program", "stage"),
    ("program_gig_template_path", "program", "gig"),
)


def _template_doc_matches_item_config_source(
    template_doc: dict | None,
    source_type: str,
    source_kind: str,
) -> bool:
    if not isinstance(template_doc, dict):
        return False
    return normalize_item_page_source_context(
        template_doc.get("source_type"),
        template_doc.get("source_kind"),
    ) == normalize_item_page_source_context(source_type, source_kind)


async def _validated_item_page_config(db, config: dict, *, persist: bool = False) -> dict:
    next_config = dict(config or {})
    patch: dict[str, str] = {}
    for key, source_type, source_kind in ITEM_PAGE_CONFIG_TEMPLATE_SPECS:
        path = normalize_page_template_path_value(next_config.get(key))
        if not path:
            next_config[key] = ""
            continue
        try:
            template_name, parent_route = parse_page_template_path(path)
        except Exception:
            next_config[key] = ""
            patch[key] = ""
            continue
        template_doc = await db[TEMPLATE_PAGES_COLLECTION].find_one(
            _page_template_query(template_name, parent_route)
        )
        if not _template_doc_matches_item_config_source(template_doc, source_type, source_kind):
            next_config[key] = ""
            patch[key] = ""
            continue
        normalized_path = compose_page_template_path(template_name, parent_route)
        next_config[key] = normalized_path
        if normalized_path != path:
            patch[key] = normalized_path
    if persist and patch:
        return await set_item_page_config(db, patch)
    return next_config


async def _get_page_template_by_path(path: str) -> dict | None:
    template_name, parent_route = parse_page_template_path(path)
    return await _db()[TEMPLATE_PAGES_COLLECTION].find_one(
        _page_template_query(template_name, parent_route)
    )


async def _get_hydrated_page_template_by_path(db, path: str) -> tuple[tuple[str, str | None], dict | None]:
    template_name, parent_route = parse_page_template_path(path)
    doc = await db[TEMPLATE_PAGES_COLLECTION].find_one(_page_template_query(template_name, parent_route))
    if not doc:
        return (template_name, parent_route), None
    hydrated = await _ensure_template_page_design_state(db, doc)
    return (template_name, parent_route), hydrated


async def _ensure_section_template(section_type: str, template_name: str) -> dict:
    coll = _db()[TEMPLATE_SECTIONS_COLLECTION]
    doc = await coll.find_one({"section_type": section_type, "template_name": template_name})
    if doc:
        return doc
    now = datetime.utcnow()
    normalized = normalize_section_template_doc(
        section_type,
        template_name,
        payload=None,
        seed_list_target_visibility_presets=True,
    )
    normalized["created_at"] = now
    normalized["updated_at"] = now
    inserted = await coll.insert_one(normalized)
    normalized["_id"] = inserted.inserted_id
    return normalized


async def _ensure_container_template(template_name: str) -> dict:
    coll = _db()[TEMPLATE_CONTAINERS_COLLECTION]
    doc = await coll.find_one({"template_name": template_name})
    if doc:
        return doc
    now = datetime.utcnow()
    normalized = normalize_container_template_doc(template_name, payload=None)
    normalized["created_at"] = now
    normalized["updated_at"] = now
    inserted = await coll.insert_one(normalized)
    normalized["_id"] = inserted.inserted_id
    return normalized


async def _ensure_page_template(path: str) -> dict:
    db = _db()
    coll = db[TEMPLATE_PAGES_COLLECTION]
    doc = await _get_page_template_by_path(path)
    if doc:
        return await _ensure_template_page_design_state(db, doc)

    await _raise_if_page_template_path_is_item_route(db, path)

    now = datetime.utcnow()
    normalized = normalize_page_template_doc(
        path,
        payload=None,
        seed_page_target_visibility_presets=True,
    )
    base_design, base_version_id = await resolve_global_published_design_snapshot(db)
    normalized["template_design_current"] = deepcopy(base_design)
    normalized["template_design_published"] = deepcopy(base_design)
    normalized["template_design_initialized_from_global_version_id"] = base_version_id
    normalized["template_design_updated_at"] = now
    normalized["template_design_published_at"] = now
    normalized["page_design_overrides"] = None
    normalized["created_at"] = now
    normalized["updated_at"] = now
    inserted = await coll.insert_one(normalized)
    normalized["_id"] = inserted.inserted_id
    return normalized


async def _resolve_builder_doc(kind: str, path: str, *, auto_create: bool = False) -> tuple[str, dict]:
    db = _db()

    if kind == "section":
        try:
            section_type, template_name = _parse_section_builder_path(path)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        doc = await db[TEMPLATE_SECTIONS_COLLECTION].find_one(
            {"section_type": section_type, "template_name": template_name}
        )
        if doc is None and auto_create:
            doc = await _ensure_section_template(section_type, template_name)
        if doc is None:
            raise HTTPException(404, "Section template not found")
        return "section", doc

    if kind == "container":
        try:
            template_name = _parse_container_builder_path(path)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        doc = await db[TEMPLATE_CONTAINERS_COLLECTION].find_one({"template_name": template_name})
        if doc is None and auto_create:
            doc = await _ensure_container_template(template_name)
        if doc is None:
            raise HTTPException(404, "Container template not found")
        return "container", doc

    if kind == "page":
        try:
            template_name, parent_route = parse_page_template_path(path)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        doc = await db[TEMPLATE_PAGES_COLLECTION].find_one(
            _page_template_query(template_name, parent_route)
        )
        if doc is not None:
            await _raise_if_page_template_path_is_item_route(
                db,
                path,
                exclude_id=doc.get("_id"),
            )
        if doc is None and auto_create:
            doc = await _ensure_page_template(path)
        if doc is None:
            raise HTTPException(404, "Page template not found")
        doc = await _ensure_template_page_design_state(db, doc)
        return "page", doc

    raise HTTPException(400, "Unsupported builder kind")


def _normalize_template_header_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None

    enabled_fields = payload.get("enabled_fields")
    if not isinstance(enabled_fields, list):
        enabled_fields = ["title", "subtitle", "cta_buttons", "overlay_image", "background_image"]

    title = payload.get("hero_title") if isinstance(payload.get("hero_title"), dict) else {"de": "", "en": ""}
    subtitle = payload.get("hero_subtitle") if isinstance(payload.get("hero_subtitle"), dict) else {"de": "", "en": ""}
    cta_buttons = payload.get("cta_buttons") if isinstance(payload.get("cta_buttons"), list) else []

    return {
        "header_type": str(payload.get("header_type") or "hero"),
        "enabled_fields": enabled_fields,
        "background_media_url": payload.get("background_media_url"),
        "background_zoom": float(payload.get("background_zoom", 1.0) or 1.0),
        "background_focal_x": float(payload.get("background_focal_x", 50.0) or 50.0),
        "background_focal_y": float(payload.get("background_focal_y", 50.0) or 50.0),
        "background_rotation": float(payload.get("background_rotation", 0.0) or 0.0),
        "overlay_image_url": payload.get("overlay_image_url"),
        "overlay_zoom": float(payload.get("overlay_zoom", 1.0) or 1.0),
        "overlay_focal_x": float(payload.get("overlay_focal_x", 50.0) or 50.0),
        "overlay_focal_y": float(payload.get("overlay_focal_y", 50.0) or 50.0),
        "overlay_rotation": float(payload.get("overlay_rotation", 0.0) or 0.0),
        "hero_title": {
            "de": str(title.get("de") or ""),
            "en": str(title.get("en") or ""),
        },
        "hero_subtitle": {
            "de": str(subtitle.get("de") or ""),
            "en": str(subtitle.get("en") or ""),
        },
        "cta_buttons": [
            {
                "text": {
                    "de": str((button.get("text") or {}).get("de") or ""),
                    "en": str((button.get("text") or {}).get("en") or ""),
                },
                "url": str(button.get("url") or "") or None,
                "button_type": button.get("button_type"),
            }
            for button in cta_buttons
            if isinstance(button, dict)
        ],
        "design_overrides": deepcopy(payload.get("design_overrides"))
        if isinstance(payload.get("design_overrides"), dict)
        else None,
    }


def _format_template_header_for_builder(page_doc: dict) -> dict | None:
    header = page_doc.get("header") if isinstance(page_doc.get("header"), dict) else None
    if not header:
        return None
    header_id = build_builder_header_id_for_page(str(page_doc.get("_id") or ""))
    return {"id": header_id, **deepcopy(header)}


def _builder_page_response(full_payload: dict) -> dict:
    page_integration_mapping = resolve_page_integration_mapping_for_template_doc(full_payload)
    return {
        "id": full_payload.get("id"),
        "slug": full_payload.get("slug"),
        "title": full_payload.get("title") if isinstance(full_payload.get("title"), dict) else {"de": "", "en": ""},
        "has_header": bool(full_payload.get("has_header", False)),
        "header_id": full_payload.get("header_id"),
        "sections": [
            {
                "section_id": section.get("_id"),
                "order": int(section.get("order", 0) or 0),
                "visible": bool(section.get("visible", True)),
                "limit": section.get("limit"),
                "width_n": int(section.get("width_n", 1) or 1),
                "width_d": int(section.get("width_d", 1) or 1),
                "device_visibility": section.get("device_visibility")
                if isinstance(section.get("device_visibility"), dict)
                else {"mobile": True, "tablet": True, "desktop": True},
                "design_overrides": section.get("design_overrides")
                if isinstance(section.get("design_overrides"), dict)
                else None,
            }
            for section in (full_payload.get("sections") if isinstance(full_payload.get("sections"), list) else [])
        ],
        "section_structure": deepcopy(full_payload.get("section_structure"))
        if isinstance(full_payload.get("section_structure"), list)
        else [],
        "status": _normalize_page_status(full_payload.get("status"), fallback="hidden"),
        "effective_status": _effective_page_status_from_stored(full_payload.get("status")),
        "is_visible": False,
        "publish_at": None,
        "unpublish_at": None,
        "in_menu": bool(full_payload.get("in_menu", False)),
        "in_footer": bool(full_payload.get("in_footer", False)),
        "hide_in_admin_sitemap": bool(full_payload.get("hide_in_admin_sitemap", True)),
        "hide_from_sitemap": bool(full_payload.get("hide_from_sitemap", True)),
        "hide_subtree_from_sitemap": bool(full_payload.get("hide_subtree_from_sitemap", True)),
        "sitemap_priority": full_payload.get("sitemap_priority"),
        "sitemap_changefreq": full_payload.get("sitemap_changefreq"),
        "generated_from_blog": False,
        "menu_title": full_payload.get("menu_title") if isinstance(full_payload.get("menu_title"), dict) else None,
        "menu_order": int(full_payload.get("menu_order", 0) or 0),
        "footer_order": int(full_payload.get("footer_order", 0) or 0),
        "redirect_to": full_payload.get("redirect_to"),
        "section_bg_pinned_start_key": str(full_payload.get("section_bg_pinned_start_key") or ""),
        "section_bg_pinned_end_key": str(full_payload.get("section_bg_pinned_end_key") or ""),
        "template_kind": full_payload.get("template_kind"),
        "source_type": full_payload.get("source_type"),
        "source_kind": full_payload.get("source_kind"),
        "source_route_ref": str(full_payload.get("source_route_ref") or "").strip() or None,
        "section_template_ref": normalize_section_template_ref(full_payload.get("section_template_ref")),
        "page_integration_mapping": page_integration_mapping,
        "integration_match_mappings": deepcopy(full_payload.get("integration_match_mappings"))
        if isinstance(full_payload.get("integration_match_mappings"), list)
        else [],
        "auto_match_rules": deepcopy(full_payload.get("auto_match_rules"))
        if isinstance(full_payload.get("auto_match_rules"), dict)
        else {},
        "template_design_current": deepcopy(full_payload.get("template_design_current"))
        if isinstance(full_payload.get("template_design_current"), dict)
        else None,
        "template_design_published": deepcopy(full_payload.get("template_design_published"))
        if isinstance(full_payload.get("template_design_published"), dict)
        else None,
        "template_design_initialized_from_global_version_id": (
            str(full_payload.get("template_design_initialized_from_global_version_id") or "").strip() or None
        ),
        "template_design_updated_at": full_payload.get("template_design_updated_at"),
        "template_design_published_at": full_payload.get("template_design_published_at"),
        "page_design_overrides": None,
        "created_at": full_payload.get("created_at"),
        "updated_at": full_payload.get("updated_at"),
    }


# -------------------------
# Section Templates CRUD
# -------------------------


@router.get("/sections", dependencies=[Depends(require_permission("content:write"))])
async def list_section_templates(
    section_type: str | None = Query(default=None),
):
    coll = _db()[TEMPLATE_SECTIONS_COLLECTION]
    query: dict[str, Any] = {}
    if section_type:
        query["section_type"] = _normalize_section_type(section_type, default="text")

    docs = await coll.find(query).sort([("section_type", 1), ("template_name", 1)]).to_list(length=1000)
    return {"templates": [_format_doc(doc) for doc in docs]}


@router.post("/sections", dependencies=[Depends(require_permission("content:write"))])
async def create_section_template(
    payload: dict = Body(...),
):
    section_type = _normalize_section_type(payload.get("section_type"), default="text")
    template_name = normalize_template_name(payload.get("template_name"), default="default")
    normalized = normalize_section_template_doc(
        section_type,
        template_name,
        payload,
        seed_list_target_visibility_presets=True,
    )

    now = datetime.utcnow()
    normalized["created_at"] = now
    normalized["updated_at"] = now

    coll = _db()[TEMPLATE_SECTIONS_COLLECTION]
    try:
        result = await coll.insert_one(normalized)
    except Exception:
        raise HTTPException(409, "Section template already exists")

    normalized["_id"] = result.inserted_id
    return _format_doc(normalized)


@router.get("/sections/{section_type}/{template_name}", dependencies=[Depends(require_permission("content:write"))])
async def get_section_template(section_type: str, template_name: str):
    normalized_type = _normalize_section_type(section_type, default="text")
    normalized_name = normalize_template_name(template_name, default="default")

    doc = await _db()[TEMPLATE_SECTIONS_COLLECTION].find_one(
        {"section_type": normalized_type, "template_name": normalized_name}
    )
    if not doc:
        raise HTTPException(404, "Section template not found")
    return _format_doc(doc)


@router.put("/sections/{section_type}/{template_name}", dependencies=[Depends(require_permission("content:write"))])
async def upsert_section_template(section_type: str, template_name: str, payload: dict = Body(...)):
    normalized_type = _normalize_section_type(section_type, default="text")
    normalized_name = normalize_template_name(template_name, default="default")

    coll = _db()[TEMPLATE_SECTIONS_COLLECTION]
    existing = await coll.find_one(
        {"section_type": normalized_type, "template_name": normalized_name}
    )
    normalized = normalize_section_template_doc(
        normalized_type,
        normalized_name,
        payload,
        seed_list_target_visibility_presets=existing is None,
    )
    if existing and "favorite" not in payload:
        normalized["favorite"] = bool(existing.get("favorite", False))
    normalized["updated_at"] = datetime.utcnow()
    if existing:
        normalized["created_at"] = existing.get("created_at", normalized["updated_at"])
        updated = await coll.find_one_and_update(
            {"_id": existing["_id"]},
            {"$set": normalized},
            return_document=ReturnDocument.AFTER,
        )
        return _format_doc(updated)

    normalized["created_at"] = normalized["updated_at"]
    try:
        result = await coll.insert_one(normalized)
    except Exception:
        raise HTTPException(409, "Section template already exists")
    normalized["_id"] = result.inserted_id
    return _format_doc(normalized)


@router.patch("/sections/{section_type}/{template_name}", dependencies=[Depends(require_permission("content:write"))])
async def update_section_template_metadata(section_type: str, template_name: str, payload: dict = Body(...)):
    payload = payload if isinstance(payload, dict) else {}
    normalized_type = _normalize_section_type(section_type, default="text")
    normalized_name = normalize_template_name(template_name, default="default")

    updates: dict[str, Any] = {}
    if "favorite" in payload:
        updates["favorite"] = bool(payload.get("favorite", False))
    if not updates:
        raise HTTPException(400, "No supported section template metadata fields provided")

    updates["updated_at"] = datetime.utcnow()
    updated = await _db()[TEMPLATE_SECTIONS_COLLECTION].find_one_and_update(
        {"section_type": normalized_type, "template_name": normalized_name},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(404, "Section template not found")
    return _format_doc(updated)


@router.delete("/sections/{section_type}/{template_name}", dependencies=[Depends(require_permission("content:write"))])
async def delete_section_template(section_type: str, template_name: str):
    normalized_type = _normalize_section_type(section_type, default="text")
    normalized_name = normalize_template_name(template_name, default="default")
    if normalized_name == "default":
        raise HTTPException(400, "Default section templates cannot be deleted")

    result = await _db()[TEMPLATE_SECTIONS_COLLECTION].delete_one(
        {"section_type": normalized_type, "template_name": normalized_name}
    )
    if result.deleted_count == 0:
        raise HTTPException(404, "Section template not found")
    return {"ok": True}


@router.post("/sections/{section_type}/{template_name}/rename", dependencies=[Depends(require_permission("content:write"))])
async def rename_section_template(section_type: str, template_name: str, payload: dict = Body(...)):
    normalized_type = _normalize_section_type(section_type, default="text")
    source_name = normalize_template_name(template_name, default="default")
    if source_name == "default":
        raise HTTPException(400, "Default section templates cannot be renamed")

    try:
        target_name = normalize_template_name(payload.get("template_name"))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if target_name == "default":
        raise HTTPException(400, 'Section template name "default" is reserved')

    coll = _db()[TEMPLATE_SECTIONS_COLLECTION]
    source_doc = await coll.find_one({"section_type": normalized_type, "template_name": source_name})
    if not source_doc:
        raise HTTPException(404, "Section template not found")

    if source_name == target_name:
        return _format_doc(source_doc)

    existing_target = await coll.find_one({"section_type": normalized_type, "template_name": target_name})
    if existing_target:
        raise HTTPException(409, "Section template already exists")

    now = datetime.utcnow()
    updated = await coll.find_one_and_update(
        {"_id": source_doc["_id"]},
        {"$set": {"template_name": target_name, "updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    await _move_template_snippets(
        build_template_key_for_section(normalized_type, source_name),
        build_template_key_for_section(normalized_type, target_name),
    )
    return _format_doc(updated)


@router.post("/sections/{section_type}/{template_name}/duplicate", dependencies=[Depends(require_permission("content:write"))])
async def duplicate_section_template(section_type: str, template_name: str, payload: dict = Body(...)):
    normalized_type = _normalize_section_type(section_type, default="text")
    source_name = normalize_template_name(template_name, default="default")
    try:
        target_name = normalize_template_name(payload.get("template_name"))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if target_name == "default":
        raise HTTPException(400, 'Section template name "default" is reserved')

    coll = _db()[TEMPLATE_SECTIONS_COLLECTION]
    source_doc = await coll.find_one({"section_type": normalized_type, "template_name": source_name})
    if not source_doc:
        raise HTTPException(404, "Section template not found")
    existing_target = await coll.find_one({"section_type": normalized_type, "template_name": target_name})
    if existing_target:
        raise HTTPException(409, "Section template already exists")

    normalized = normalize_section_template_doc(
        normalized_type,
        target_name,
        _strip_mongo_meta(source_doc),
    )
    now = datetime.utcnow()
    normalized["created_at"] = now
    normalized["updated_at"] = now
    result = await coll.insert_one(normalized)
    normalized["_id"] = result.inserted_id
    await _copy_template_snippets(
        build_template_key_for_section(normalized_type, source_name),
        build_template_key_for_section(normalized_type, target_name),
    )
    return _format_doc(normalized)


# -------------------------
# Container Templates CRUD
# -------------------------


@router.get("/containers", dependencies=[Depends(require_permission("content:write"))])
async def list_container_templates():
    docs = await _db()[TEMPLATE_CONTAINERS_COLLECTION].find({}).sort("template_name", 1).to_list(length=1000)
    return {"templates": [_format_doc(doc) for doc in docs]}


@router.post("/containers", dependencies=[Depends(require_permission("content:write"))])
async def create_container_template(payload: dict = Body(...)):
    template_name = normalize_template_name(payload.get("template_name"))
    normalized = normalize_container_template_doc(template_name, payload)

    now = datetime.utcnow()
    normalized["created_at"] = now
    normalized["updated_at"] = now

    coll = _db()[TEMPLATE_CONTAINERS_COLLECTION]
    try:
        result = await coll.insert_one(normalized)
    except Exception:
        raise HTTPException(409, "Container template already exists")

    normalized["_id"] = result.inserted_id
    return _format_doc(normalized)


@router.get("/containers/{template_name}", dependencies=[Depends(require_permission("content:write"))])
async def get_container_template(template_name: str):
    normalized_name = normalize_template_name(template_name)
    doc = await _db()[TEMPLATE_CONTAINERS_COLLECTION].find_one({"template_name": normalized_name})
    if not doc:
        raise HTTPException(404, "Container template not found")
    return _format_doc(doc)


@router.put("/containers/{template_name}", dependencies=[Depends(require_permission("content:write"))])
async def upsert_container_template(template_name: str, payload: dict = Body(...)):
    normalized_name = normalize_template_name(template_name)
    normalized = normalize_container_template_doc(normalized_name, payload)
    normalized["updated_at"] = datetime.utcnow()

    coll = _db()[TEMPLATE_CONTAINERS_COLLECTION]
    existing = await coll.find_one({"template_name": normalized_name})
    if existing:
        normalized["created_at"] = existing.get("created_at", normalized["updated_at"])
        updated = await coll.find_one_and_update(
            {"_id": existing["_id"]},
            {"$set": normalized},
            return_document=ReturnDocument.AFTER,
        )
        return _format_doc(updated)

    normalized["created_at"] = normalized["updated_at"]
    try:
        result = await coll.insert_one(normalized)
    except Exception:
        raise HTTPException(409, "Container template already exists")
    normalized["_id"] = result.inserted_id
    return _format_doc(normalized)


@router.delete("/containers/{template_name}", dependencies=[Depends(require_permission("content:write"))])
async def delete_container_template(template_name: str):
    normalized_name = normalize_template_name(template_name)
    result = await _db()[TEMPLATE_CONTAINERS_COLLECTION].delete_one({"template_name": normalized_name})
    if result.deleted_count == 0:
        raise HTTPException(404, "Container template not found")
    return {"ok": True}


@router.post("/containers/{template_name}/rename", dependencies=[Depends(require_permission("content:write"))])
async def rename_container_template(template_name: str, payload: dict = Body(...)):
    try:
        source_name = normalize_template_name(template_name)
        target_name = normalize_template_name(payload.get("template_name"))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if source_name == target_name:
        doc = await _db()[TEMPLATE_CONTAINERS_COLLECTION].find_one({"template_name": source_name})
        if not doc:
            raise HTTPException(404, "Container template not found")
        return _format_doc(doc)

    coll = _db()[TEMPLATE_CONTAINERS_COLLECTION]
    source_doc = await coll.find_one({"template_name": source_name})
    if not source_doc:
        raise HTTPException(404, "Container template not found")
    existing_target = await coll.find_one({"template_name": target_name})
    if existing_target:
        raise HTTPException(409, "Container template already exists")

    now = datetime.utcnow()
    update_payload: dict[str, Any] = {
        "template_name": target_name,
        "updated_at": now,
    }
    source_composition_name = str(source_doc.get("composition_name") or "").strip()
    if not source_composition_name or source_composition_name == source_name:
        update_payload["composition_name"] = target_name

    updated = await coll.find_one_and_update(
        {"_id": source_doc["_id"]},
        {"$set": update_payload},
        return_document=ReturnDocument.AFTER,
    )
    await _move_template_snippets(
        build_template_key_for_container(source_name),
        build_template_key_for_container(target_name),
    )
    return _format_doc(updated)


@router.post("/containers/{template_name}/duplicate", dependencies=[Depends(require_permission("content:write"))])
async def duplicate_container_template(template_name: str, payload: dict = Body(...)):
    try:
        source_name = normalize_template_name(template_name)
        target_name = normalize_template_name(payload.get("template_name"))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    coll = _db()[TEMPLATE_CONTAINERS_COLLECTION]
    source_doc = await coll.find_one({"template_name": source_name})
    if not source_doc:
        raise HTTPException(404, "Container template not found")
    existing_target = await coll.find_one({"template_name": target_name})
    if existing_target:
        raise HTTPException(409, "Container template already exists")

    normalized = normalize_container_template_doc(target_name, _strip_mongo_meta(source_doc))
    normalized["created_at"] = datetime.utcnow()
    normalized["updated_at"] = normalized["created_at"]
    composition_name = str(normalized.get("composition_name") or "").strip()
    if not composition_name or composition_name == source_name:
        normalized["composition_name"] = target_name

    inserted = await coll.insert_one(normalized)
    normalized["_id"] = inserted.inserted_id
    await _copy_template_snippets(
        build_template_key_for_container(source_name),
        build_template_key_for_container(target_name),
    )
    return _format_doc(normalized)


# -------------------------
# Page Templates CRUD
# -------------------------


@router.get("/pages", dependencies=[Depends(require_permission("content:write"))])
async def list_page_templates(
    source_type: str | None = Query(default=None),
):
    db = _db()
    query: dict[str, Any] = {}
    if source_type:
        normalized_source = str(source_type).strip().lower()
        if normalized_source in {"blog", "tiles", "program"}:
            query["source_type"] = normalized_source
        elif normalized_source == "normal":
            query["parent_route"] = None

    docs = await db[TEMPLATE_PAGES_COLLECTION].find(query).sort([
        ("parent_route", 1),
        ("template_name", 1),
    ]).to_list(length=1000)
    base_design, base_version_id = await resolve_global_published_design_snapshot(db)
    hydrated_docs: list[dict] = []
    for doc in docs:
        hydrated_docs.append(
            await _ensure_template_page_design_state(
                db,
                doc,
                base_design=base_design,
                base_version_id=base_version_id,
            )
        )
    return {"templates": [await _format_page_template_doc(db, doc) for doc in hydrated_docs]}


@router.get("/item-page-source-routes", dependencies=[Depends(require_permission("content:write"))])
async def list_item_page_source_routes():
    routes = await capture_item_page_routes(_db())
    return {"routes": routes}


@router.put("/item-page-source-routes", dependencies=[Depends(require_permission("content:write"))])
async def put_item_page_source_routes(payload: dict = Body(default_factory=dict)):
    routes_payload = payload.get("routes") if isinstance(payload, dict) else None
    routes = await apply_item_page_routes(_db(), routes_payload)
    return {"routes": routes}


@router.get("/item-page-parent-candidates", dependencies=[Depends(require_permission("content:write"))])
async def list_item_page_parent_candidates(
    source_type: str = Query(...),
    source_kind: str = Query(default="item"),
):
    source_context = normalize_item_page_source_context(source_type, source_kind)
    if not source_context:
        raise HTTPException(400, "source_type/source_kind must be blog:item, program:stage, or program:gig")
    section_type = _item_page_section_type_for_source(*source_context)
    if not section_type:
        return {"candidates": []}

    db = _db()
    section_projection = {
        "_id": 1,
        "section_type": 1,
        "title_placeholder": 1,
        "title": 1,
    }
    candidates: list[dict] = []
    async for page in db["pages"].find(
        {"template_managed": {"$ne": True}},
        {
            "_id": 1,
            "slug": 1,
            "title": 1,
            "sections": 1,
            "status": 1,
        },
    ).sort([("slug", 1)]):
        slug = str(page.get("slug") or "").strip().strip("/")
        if not slug or slug.startswith("__template_"):
            continue
        parent_route = normalize_parent_route(f"/{slug}")
        if not parent_route:
            continue
        page_title = page.get("title") if isinstance(page.get("title"), dict) else {}
        page_label = str(page_title.get("de") or page_title.get("en") or "").strip() or parent_route
        section_refs = page.get("sections") if isinstance(page.get("sections"), list) else []
        section_ids = [
            _safe_object_id(ref.get("section_id"))
            for ref in section_refs
            if isinstance(ref, dict) and str(ref.get("section_id") or "").strip()
        ]
        section_ids = [section_id for section_id in section_ids if section_id is not None]
        sections_by_id: dict[str, dict] = {}
        if section_ids:
            section_docs = await db["sections"].find(
                {
                    "_id": {"$in": section_ids},
                    "section_type": section_type,
                },
                section_projection,
            ).to_list(length=len(section_ids))
            sections_by_id = {str(doc.get("_id")): doc for doc in section_docs if isinstance(doc, dict)}
        candidate = {
            "id": parent_route,
            "parent_route": parent_route,
            "page_id": str(page.get("_id") or ""),
            "page_slug": slug,
            "page_title": page_label,
            "page_status": str(page.get("status") or ""),
            "has_related_section": False,
            "label": f"{parent_route} ({page_label})",
        }
        for ref_index, ref in enumerate(section_refs):
            if not isinstance(ref, dict):
                continue
            section_id = str(ref.get("section_id") or "").strip()
            section_doc = sections_by_id.get(section_id)
            if not isinstance(section_doc, dict):
                continue
            title_value = section_doc.get("title") if isinstance(section_doc.get("title"), dict) else {}
            section_label = (
                str(section_doc.get("title_placeholder") or "").strip()
                or str(title_value.get("de") or title_value.get("en") or "").strip()
                or section_type.title()
            )
            candidate.update(
                {
                    "has_related_section": True,
                    "section_id": section_id,
                    "section_type": section_type,
                    "section_index": ref_index,
                    "section_label": section_label,
                    "label": f"{parent_route} ({page_label})",
                }
            )
            break
        candidates.append(candidate)

    return {"candidates": candidates}


@router.get("/global-item-page-config", dependencies=[Depends(require_permission("content:write"))])
async def get_item_page_config_route():
    db = _db()
    config = await get_item_page_config(db)
    return await _validated_item_page_config(db, config, persist=True)


@router.put("/global-item-page-config", dependencies=[Depends(require_permission("content:write"))])
async def put_item_page_config_route(payload: dict = Body(default_factory=dict)):
    db = _db()
    config = await set_item_page_config(db, payload)
    config = await _validated_item_page_config(db, config, persist=True)
    return {
        **config,
        "migrations": [],
        "migration_summary": {
            "migrated_page_count": 0,
            "redirect_count": 0,
        },
    }


@router.post("/pages", dependencies=[Depends(require_permission("content:write"))])
async def create_page_template(payload: dict = Body(...)):
    db = _db()
    source_route_ref = _normalize_source_route_ref(payload.get("source_route_ref"))
    path = payload.get("path")
    if source_route_ref or not path:
        path = await _build_page_template_path_for_payload(db, payload)
    await _raise_if_page_template_path_is_item_route(db, path)
    normalized = normalize_page_template_doc(
        path,
        payload,
        seed_page_target_visibility_presets=True,
    )
    normalized = await _inject_source_route_payload_fields(db, payload, normalized)
    await _apply_page_mapping_fixed_gig_primary_key_sources(db, normalized)
    now = datetime.utcnow()
    base_design, base_version_id = await resolve_global_published_design_snapshot(db)
    normalized["template_design_current"] = deepcopy(base_design)
    normalized["template_design_published"] = deepcopy(base_design)
    normalized["template_design_initialized_from_global_version_id"] = base_version_id
    normalized["template_design_updated_at"] = now
    normalized["template_design_published_at"] = now
    normalized["page_design_overrides"] = None
    normalized["created_at"] = now
    normalized["updated_at"] = now

    coll = db[TEMPLATE_PAGES_COLLECTION]
    try:
        result = await coll.insert_one(normalized)
    except Exception:
        if normalized.get("parent_route"):
            raise HTTPException(409, "Page template already exists for this route and name")
        raise HTTPException(409, "Page template already exists")

    normalized["_id"] = result.inserted_id

    if normalized.get("source_type") == "blog" and normalized.get("parent_route"):
        await sync_all_blog_items_for_route(db, normalized["parent_route"])

    return _format_doc(normalized)


@router.get("/pages/{template_path:path}/design", dependencies=[Depends(require_permission("content:write"))])
async def get_page_template_design_state_route(template_path: str):
    return await _get_page_template_design_state_impl(template_path)


@router.put("/pages/{template_path:path}/design/current", dependencies=[Depends(require_permission("content:write"))])
async def update_page_template_design_current_route(
    template_path: str,
    payload: dict = Body(default_factory=dict),
    user: KeycloakUser = Depends(get_current_user),
):
    return await _update_page_template_design_current_impl(template_path, payload, user)


@router.get("/pages/{template_path:path}", dependencies=[Depends(require_permission("content:write"))])
async def get_page_template(template_path: str):
    db = _db()
    template_name, parent_route = parse_page_template_path(template_path)
    doc = await db[TEMPLATE_PAGES_COLLECTION].find_one(
        _page_template_query(template_name, parent_route)
    )
    if not doc:
        raise HTTPException(404, "Page template not found")
    base_design, base_version_id = await resolve_global_published_design_snapshot(db)
    hydrated = await _ensure_template_page_design_state(
        db,
        doc,
        base_design=base_design,
        base_version_id=base_version_id,
    )
    return await _format_page_template_doc(db, hydrated)


@router.put("/pages/{template_path:path}/routing", dependencies=[Depends(require_permission("content:write"))])
async def update_page_template_item_routing(template_path: str, payload: dict = Body(default_factory=dict)):
    db = _db()
    template_name, current_parent_route = parse_page_template_path(template_path)
    coll = db[TEMPLATE_PAGES_COLLECTION]
    current = await coll.find_one(_page_template_query(template_name, current_parent_route))
    if not isinstance(current, dict):
        raise HTTPException(404, "Page template not found")
    if not _is_item_page_template_doc(current):
        raise HTTPException(400, "Routing can only be edited for item-page templates")

    source_type = str(current.get("source_type") or "").strip().lower()
    source_kind = str(current.get("source_kind") or "").strip().lower()
    source_context = normalize_item_page_source_context(source_type, source_kind)
    if not source_context:
        raise HTTPException(400, "Routing is supported only for blog and program item templates")
    source_type, source_kind = source_context
    section_type = _item_page_section_type_for_source(source_type, source_kind)

    next_parent_route = (
        normalize_parent_route(payload.get("parent_route"))
        if "parent_route" in payload
        else normalize_parent_route(current.get("parent_route"))
    )
    next_subroute = (
        normalize_item_page_subroute(payload.get("item_page_subroute"))
        if "item_page_subroute" in payload
        else normalize_item_page_subroute(current.get("item_page_subroute"))
    )
    next_slug_field = normalize_item_page_slug_field(
        source_type,
        source_kind,
        payload.get("item_page_slug_field")
        if "item_page_slug_field" in payload
        else current.get("item_page_slug_field"),
    )
    next_source_section_id = (
        str(payload.get("item_page_source_section_id") or "").strip() or None
        if "item_page_source_section_id" in payload
        else str(current.get("item_page_source_section_id") or "").strip() or None
    )

    if next_parent_route:
        page_slug = next_parent_route.strip("/")
        page_doc = await db["pages"].find_one(
            {
                "slug": page_slug,
                "template_managed": {"$ne": True},
            },
            {"_id": 1, "sections": 1},
        )
        if not isinstance(page_doc, dict) or page_slug.startswith("__template_"):
            raise HTTPException(400, "Selected parent page does not exist")

        if next_source_section_id and section_type:
            section_oid = _safe_object_id(next_source_section_id)
            if section_oid is None:
                raise HTTPException(400, "Selected source section does not match the item-page type")
            section_doc = await db["sections"].find_one({"_id": section_oid})
            if not isinstance(section_doc, dict) or str(section_doc.get("section_type") or "") != section_type:
                raise HTTPException(400, "Selected source section does not match the item-page type")
            page_section_ids = {
                str(ref.get("section_id") or "").strip()
                for ref in (page_doc.get("sections") if isinstance(page_doc.get("sections"), list) else [])
                if isinstance(ref, dict)
            }
            if str(section_doc["_id"]) not in page_section_ids:
                raise HTTPException(400, "Selected source section is not on the selected parent page")
    elif not next_parent_route:
        next_source_section_id = None

    existing_target = await coll.find_one(_page_template_query(template_name, next_parent_route))
    if existing_target and existing_target.get("_id") != current.get("_id"):
        raise HTTPException(409, "Page template already exists for this route and name")

    old_template_path = compose_page_template_path(template_name, current_parent_route)
    old_template_key = build_template_key_for_page(template_name, current_parent_route)
    old_effective_route = effective_item_page_parent_route_for_template(current)
    next_effective_route = compose_item_page_effective_parent_route(next_parent_route, next_subroute)
    next_template_path = compose_page_template_path(template_name, next_parent_route)
    next_template_key = build_template_key_for_page(template_name, next_parent_route)
    if next_subroute and next_effective_route:
        shadow_template_name, shadow_parent_route = parse_page_template_path(
            next_effective_route.strip("/")
        )
        shadow_doc = await coll.find_one(_page_template_query(shadow_template_name, shadow_parent_route))
        if shadow_doc and shadow_doc.get("_id") != current.get("_id"):
            raise HTTPException(
                409,
                (
                    f'Item page route "{next_effective_route}" conflicts with page template '
                    f'"{compose_page_template_path(shadow_template_name, shadow_parent_route)}". '
                    "Rename or delete that template before using this subroute."
                ),
            )
    now = datetime.utcnow()

    update_payload = {
        "parent_route": next_parent_route,
        "item_page_subroute": next_subroute,
        "item_page_slug_field": next_slug_field,
        "item_page_source_section_id": next_source_section_id,
        "source_type": source_type,
        "source_kind": source_kind,
        "template_kind": "item_page",
        "updated_at": now,
    }
    updated = await coll.find_one_and_update(
        {"_id": current["_id"]},
        {"$set": update_payload},
        return_document=ReturnDocument.AFTER,
    )
    if not isinstance(updated, dict):
        raise HTTPException(500, "Failed to update template routing")

    if old_template_key != next_template_key:
        await _move_template_snippets(old_template_key, next_template_key)

    source_type_key = _source_type_key_for_template_doc(updated)
    migration = {
        "updated_count": 0,
        "redirect_count": 0,
        "old_parent_route": old_effective_route,
        "new_parent_route": next_effective_route,
    }
    if source_type_key and old_effective_route and next_effective_route and old_effective_route != next_effective_route:
        migration = await migrate_generated_item_pages_parent_route(
            db,
            source_type=source_type_key,
            old_parent_route=old_effective_route,
            new_parent_route=next_effective_route,
            template_name=template_name,
            template_style_ref=old_template_path,
            template_key=old_template_key,
            new_template_style_ref=next_template_path,
            new_template_key=next_template_key,
        )
    elif old_template_path != next_template_path or old_template_key != next_template_key:
        identity_filters = [
            {"template_style_ref": old_template_path},
            {"template_key": old_template_key},
        ]
        await db["pages"].update_many(
            {
                "template_managed": True,
                "$or": identity_filters,
            },
            {
                "$set": {
                    "template_style_ref": next_template_path,
                    "template_key": next_template_key,
                    "template_template_name": template_name,
                    "template_parent_route": next_effective_route,
                    "template_source_parent_id": next_effective_route,
                    "updated_at": now,
                }
            },
        )

    config_prefix = item_page_config_key_prefix(source_type, source_kind)
    if config_prefix:
        global_cfg = await get_item_page_config(db)
        active_path = normalize_page_template_path_value(global_cfg.get(f"{config_prefix}_template_path"))
        if active_path == old_template_path and next_template_path != old_template_path:
            await set_item_page_config(db, {f"{config_prefix}_template_path": next_template_path})

    hydrated = await _ensure_template_page_design_state(db, updated)
    return {
        "template": _format_doc(hydrated),
        "path": next_template_path,
        "old_path": old_template_path,
        "parent_route": next_parent_route,
        "item_page_subroute": next_subroute,
        "effective_parent_route": next_effective_route,
        "item_page_slug_field": next_slug_field,
        "item_page_source_section_id": next_source_section_id,
        "migration": migration,
    }


@router.put("/pages/{template_path:path}", dependencies=[Depends(require_permission("content:write"))])
async def upsert_page_template(template_path: str, payload: dict = Body(...)):
    db = _db()
    await _raise_if_page_template_path_is_item_route(db, template_path)
    normalized = normalize_page_template_doc(template_path, payload)
    normalized = await _inject_source_route_payload_fields(db, payload, normalized)
    await _apply_page_mapping_fixed_gig_primary_key_sources(db, normalized)
    await _validate_source_route_ref_matches_template_path(db, normalized)
    normalized["updated_at"] = datetime.utcnow()

    coll = db[TEMPLATE_PAGES_COLLECTION]
    existing = await coll.find_one(
        _page_template_query(normalized["template_name"], normalized.get("parent_route"))
    )
    if existing:
        merged = {**existing, **payload}
        normalized = normalize_page_template_doc(template_path, merged)
        normalized = await _inject_source_route_payload_fields(db, merged, normalized)
        await _apply_page_mapping_fixed_gig_primary_key_sources(db, normalized)
        await _validate_source_route_ref_matches_template_path(db, normalized)
        normalized["updated_at"] = datetime.utcnow()
        normalized["created_at"] = existing.get("created_at", normalized["updated_at"])
        normalized["template_design_current"] = (
            deepcopy(existing.get("template_design_current"))
            if isinstance(existing.get("template_design_current"), dict)
            else deepcopy(normalized.get("template_design_current"))
            if isinstance(normalized.get("template_design_current"), dict)
            else {}
        )
        normalized["template_design_published"] = (
            deepcopy(existing.get("template_design_published"))
            if isinstance(existing.get("template_design_published"), dict)
            else deepcopy(normalized.get("template_design_published"))
            if isinstance(normalized.get("template_design_published"), dict)
            else deepcopy(normalized["template_design_current"])
        )
        normalized["template_design_initialized_from_global_version_id"] = (
            str(existing.get("template_design_initialized_from_global_version_id") or "").strip()
            or str(normalized.get("template_design_initialized_from_global_version_id") or "").strip()
            or None
        )
        normalized["template_design_updated_at"] = (
            existing.get("template_design_updated_at")
            if isinstance(existing.get("template_design_updated_at"), datetime)
            else normalized["updated_at"]
        )
        normalized["template_design_published_at"] = (
            existing.get("template_design_published_at")
            if isinstance(existing.get("template_design_published_at"), datetime)
            else normalized["updated_at"]
        )
        normalized["page_design_overrides"] = None
        mapped_target_keys = changed_item_page_mapping_target_keys(existing, normalized)
        updated = await coll.find_one_and_update(
            {"_id": existing["_id"]},
            {"$set": normalized},
            return_document=ReturnDocument.AFTER,
        )
        if normalized.get("source_type") == "blog" and normalized.get("parent_route"):
            await sync_all_blog_items_for_route(db, normalized["parent_route"])
        await _sync_init_generated_pages_for_template_doc_scoped(
            db,
            updated,
            mapped_target_keys,
        )
        hydrated = await _ensure_template_page_design_state(db, updated)
        return _format_doc(hydrated)

    normalized = normalize_page_template_doc(
        template_path,
        payload,
        seed_page_target_visibility_presets=True,
    )
    normalized = await _inject_source_route_payload_fields(db, payload, normalized)
    await _apply_page_mapping_fixed_gig_primary_key_sources(db, normalized)
    await _validate_source_route_ref_matches_template_path(db, normalized)
    normalized["updated_at"] = datetime.utcnow()
    base_design, base_version_id = await resolve_global_published_design_snapshot(db)
    normalized["template_design_current"] = deepcopy(base_design)
    normalized["template_design_published"] = deepcopy(base_design)
    normalized["template_design_initialized_from_global_version_id"] = base_version_id
    normalized["template_design_updated_at"] = normalized["updated_at"]
    normalized["template_design_published_at"] = normalized["updated_at"]
    normalized["page_design_overrides"] = None
    normalized["created_at"] = normalized["updated_at"]
    try:
        result = await coll.insert_one(normalized)
    except Exception:
        if normalized.get("parent_route"):
            raise HTTPException(409, "Page template already exists for this route and name")
        raise HTTPException(409, "Page template already exists")

    normalized["_id"] = result.inserted_id
    if normalized.get("source_type") == "blog" and normalized.get("parent_route"):
        await sync_all_blog_items_for_route(db, normalized["parent_route"])
    await _sync_init_generated_pages_for_template_doc_scoped(db, normalized, set())
    return _format_doc(normalized)


@router.patch("/pages/{template_path:path}", dependencies=[Depends(require_permission("content:write"))])
async def patch_page_template(
    template_path: str,
    payload: dict = Body(...),
):
    db = _db()
    template_name, parent_route = parse_page_template_path(template_path)
    coll = db[TEMPLATE_PAGES_COLLECTION]
    current = await coll.find_one(_page_template_query(template_name, parent_route))
    if not current:
        raise HTTPException(404, "Page template not found")

    merged = {**current, **payload}
    normalized = normalize_page_template_doc(template_path, merged)
    normalized = await _inject_source_route_payload_fields(db, merged, normalized)
    await _apply_page_mapping_fixed_gig_primary_key_sources(db, normalized)
    await _validate_source_route_ref_matches_template_path(db, normalized)
    normalized["updated_at"] = datetime.utcnow()
    normalized["created_at"] = current.get("created_at", normalized["updated_at"])
    normalized["template_design_current"] = (
        deepcopy(current.get("template_design_current"))
        if isinstance(current.get("template_design_current"), dict)
        else deepcopy(normalized.get("template_design_current"))
        if isinstance(normalized.get("template_design_current"), dict)
        else {}
    )
    normalized["template_design_published"] = (
        deepcopy(current.get("template_design_published"))
        if isinstance(current.get("template_design_published"), dict)
        else deepcopy(normalized.get("template_design_published"))
        if isinstance(normalized.get("template_design_published"), dict)
        else deepcopy(normalized["template_design_current"])
    )
    normalized["template_design_initialized_from_global_version_id"] = (
        str(current.get("template_design_initialized_from_global_version_id") or "").strip()
        or str(normalized.get("template_design_initialized_from_global_version_id") or "").strip()
        or None
    )
    normalized["template_design_updated_at"] = (
        current.get("template_design_updated_at")
        if isinstance(current.get("template_design_updated_at"), datetime)
        else normalized["updated_at"]
    )
    normalized["template_design_published_at"] = (
        current.get("template_design_published_at")
        if isinstance(current.get("template_design_published_at"), datetime)
        else normalized["updated_at"]
    )
    normalized["page_design_overrides"] = None
    mapped_target_keys = changed_item_page_mapping_target_keys(current, normalized)

    updated = await coll.find_one_and_update(
        {"_id": current["_id"]},
        {"$set": normalized},
        return_document=ReturnDocument.AFTER,
    )
    if normalized.get("source_type") == "blog" and normalized.get("parent_route"):
        await sync_all_blog_items_for_route(db, normalized["parent_route"])
    await _sync_init_generated_pages_for_template_doc_scoped(
        db,
        updated,
        mapped_target_keys,
    )
    hydrated = await _ensure_template_page_design_state(db, updated)
    return _format_doc(hydrated)


@router.post("/pages/{template_path:path}/regenerate-all", dependencies=[Depends(require_permission("content:write"))])
async def regenerate_all_item_pages_for_page_template(template_path: str):
    db = _db()
    template_name, parent_route = parse_page_template_path(template_path)
    template_doc = await db[TEMPLATE_PAGES_COLLECTION].find_one(
        _page_template_query(template_name, parent_route)
    )
    if not template_doc:
        raise HTTPException(404, "Page template not found")

    try:
        return await regenerate_all_item_pages_for_template(db, template_doc)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/pages/{template_path:path}/rename", dependencies=[Depends(require_permission("content:write"))])
async def rename_page_template(template_path: str, payload: dict = Body(...)):
    db = _db()
    source_template_name, source_parent_route = parse_page_template_path(template_path)

    try:
        target_template_name = normalize_template_name(payload.get("template_name"))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    coll = db[TEMPLATE_PAGES_COLLECTION]
    source_doc = await coll.find_one(_page_template_query(source_template_name, source_parent_route))
    if not source_doc:
        raise HTTPException(404, "Page template not found")

    if source_template_name == target_template_name:
        hydrated_source = await _ensure_template_page_design_state(db, source_doc)
        return _format_doc(hydrated_source)

    target_path = compose_page_template_path(target_template_name, source_parent_route)
    await _raise_if_page_template_path_is_item_route(db, target_path, exclude_id=source_doc.get("_id"))

    existing_target = await coll.find_one(_page_template_query(target_template_name, source_parent_route))
    if existing_target:
        raise HTTPException(409, "Page template already exists")

    now = datetime.utcnow()
    updated = await coll.find_one_and_update(
        {"_id": source_doc["_id"]},
        {"$set": {"template_name": target_template_name, "updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )

    source_style_ref = _compose_page_template_style_ref(source_template_name, source_parent_route)
    target_style_ref = _compose_page_template_style_ref(target_template_name, source_parent_route)
    source_template_key = build_template_key_for_page(source_template_name, source_parent_route)
    target_template_key = build_template_key_for_page(target_template_name, source_parent_route)

    await db["pages"].update_many(
        {"template_style_ref": source_style_ref},
        {
            "$set": {
                "template_style_ref": target_style_ref,
                "template_style_linked": True,
                "template_style_lock": True,
                "template_key": target_template_key,
                "template_template_name": target_template_name,
                "template_parent_route": source_parent_route,
                "page_design_overrides": None,
                "updated_at": now,
            }
        },
    )
    await _move_template_snippets(source_template_key, target_template_key)

    hydrated = await _ensure_template_page_design_state(db, updated)
    if hydrated.get("source_type") == "blog" and hydrated.get("parent_route"):
        await sync_all_blog_items_for_route(db, hydrated["parent_route"])

    return _format_doc(hydrated)


@router.post("/pages/{template_path:path}/duplicate", dependencies=[Depends(require_permission("content:write"))])
async def duplicate_page_template(template_path: str, payload: dict = Body(...)):
    db = _db()
    source_template_name, source_parent_route = parse_page_template_path(template_path)

    try:
        target_template_name = normalize_template_name(payload.get("template_name"))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    coll = db[TEMPLATE_PAGES_COLLECTION]
    source_doc = await coll.find_one(_page_template_query(source_template_name, source_parent_route))
    if not source_doc:
        raise HTTPException(404, "Page template not found")

    if source_template_name == target_template_name:
        raise HTTPException(409, "Page template already exists")

    target_path = compose_page_template_path(target_template_name, source_parent_route)
    await _raise_if_page_template_path_is_item_route(db, target_path, exclude_id=source_doc.get("_id"))

    existing_target = await coll.find_one(_page_template_query(target_template_name, source_parent_route))
    if existing_target:
        raise HTTPException(409, "Page template already exists")

    normalized = normalize_page_template_doc(target_path, _strip_mongo_meta(source_doc))
    normalized = await _inject_source_route_payload_fields(db, normalized, normalized)
    await _apply_page_mapping_fixed_gig_primary_key_sources(db, normalized)
    await _validate_source_route_ref_matches_template_path(db, normalized)

    now = datetime.utcnow()
    normalized["created_at"] = now
    normalized["updated_at"] = now
    if isinstance(normalized.get("template_design_current"), dict):
        normalized["template_design_current"] = deepcopy(normalized["template_design_current"])
    if isinstance(normalized.get("template_design_published"), dict):
        normalized["template_design_published"] = deepcopy(normalized["template_design_published"])
    normalized["template_design_updated_at"] = now
    normalized["template_design_published_at"] = now
    normalized["page_design_overrides"] = None

    try:
        result = await coll.insert_one(normalized)
    except Exception as exc:
        if normalized.get("parent_route"):
            raise HTTPException(409, "Page template already exists for this route and name") from exc
        raise HTTPException(409, "Page template already exists") from exc
    normalized["_id"] = result.inserted_id

    await _copy_template_snippets(
        build_template_key_for_page(source_template_name, source_parent_route),
        build_template_key_for_page(target_template_name, source_parent_route),
    )

    hydrated = await _ensure_template_page_design_state(db, normalized)
    return _format_doc(hydrated)


async def _with_cached_font_stylesheets(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {}

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


async def _get_page_template_design_state_impl(template_path: str):
    db = _db()
    (template_name, parent_route), template_doc = await _get_hydrated_page_template_by_path(db, template_path)
    if not template_doc:
        raise HTTPException(404, "Page template not found")

    current_payload = await _with_cached_font_stylesheets(
        deepcopy(template_doc.get("template_design_current"))
        if isinstance(template_doc.get("template_design_current"), dict)
        else {}
    )
    published_payload = await _with_cached_font_stylesheets(
        deepcopy(template_doc.get("template_design_published"))
        if isinstance(template_doc.get("template_design_published"), dict)
        else {}
    )

    return {
        "path": _compose_page_template_style_ref(template_name, parent_route),
        "template_name": template_name,
        "parent_route": parent_route,
        "current": current_payload,
        "published": published_payload,
        "initialized_from_global_version_id": (
            str(template_doc.get("template_design_initialized_from_global_version_id") or "").strip() or None
        ),
        "updated_at": template_doc.get("template_design_updated_at") or template_doc.get("updated_at"),
        "published_at": template_doc.get("template_design_published_at"),
    }


async def _update_page_template_design_current_impl(
    template_path: str,
    payload: dict,
    user: KeycloakUser,
):
    _require_design_write(user)
    db = _db()
    (template_name, parent_route), template_doc = await _get_hydrated_page_template_by_path(db, template_path)
    if not template_doc:
        raise HTTPException(404, "Page template not found")

    next_design = deepcopy(payload) if isinstance(payload, dict) else {}
    now = datetime.utcnow()
    updated = await db[TEMPLATE_PAGES_COLLECTION].find_one_and_update(
        {"_id": template_doc["_id"]},
        {
            "$set": {
                "template_design_current": next_design,
                "template_design_updated_at": now,
                "updated_at": now,
                "page_design_overrides": None,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    hydrated = await _ensure_template_page_design_state(db, updated)
    current_payload = await _with_cached_font_stylesheets(
        deepcopy(hydrated.get("template_design_current"))
        if isinstance(hydrated.get("template_design_current"), dict)
        else {}
    )
    published_payload = await _with_cached_font_stylesheets(
        deepcopy(hydrated.get("template_design_published"))
        if isinstance(hydrated.get("template_design_published"), dict)
        else {}
    )
    return {
        "ok": True,
        "path": _compose_page_template_style_ref(template_name, parent_route),
        "current": current_payload,
        "published": published_payload,
        "updated_at": hydrated.get("template_design_updated_at") or hydrated.get("updated_at"),
        "published_at": hydrated.get("template_design_published_at"),
    }


@router.post("/pages/{template_path:path}/design/publish", dependencies=[Depends(require_permission("content:write"))])
async def publish_page_template_design_current(
    template_path: str,
    user: KeycloakUser = Depends(get_current_user),
):
    _require_design_write(user)
    db = _db()
    (template_name, parent_route), template_doc = await _get_hydrated_page_template_by_path(db, template_path)
    if not template_doc:
        raise HTTPException(404, "Page template not found")

    now = datetime.utcnow()
    published_payload = (
        deepcopy(template_doc.get("template_design_current"))
        if isinstance(template_doc.get("template_design_current"), dict)
        else {}
    )
    updated = await db[TEMPLATE_PAGES_COLLECTION].find_one_and_update(
        {"_id": template_doc["_id"]},
        {
            "$set": {
                "template_design_published": published_payload,
                "template_design_published_at": now,
                "updated_at": now,
                "page_design_overrides": None,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    hydrated = await _ensure_template_page_design_state(db, updated)
    current_payload = await _with_cached_font_stylesheets(
        deepcopy(hydrated.get("template_design_current"))
        if isinstance(hydrated.get("template_design_current"), dict)
        else {}
    )
    published_payload = await _with_cached_font_stylesheets(
        deepcopy(hydrated.get("template_design_published"))
        if isinstance(hydrated.get("template_design_published"), dict)
        else {}
    )

    if hydrated.get("source_type") == "blog" and hydrated.get("parent_route"):
        await sync_all_blog_items_for_route(db, hydrated["parent_route"])

    return {
        "ok": True,
        "path": _compose_page_template_style_ref(template_name, parent_route),
        "current": current_payload,
        "published": published_payload,
        "updated_at": hydrated.get("template_design_updated_at") or hydrated.get("updated_at"),
        "published_at": hydrated.get("template_design_published_at"),
    }


@router.delete("/pages/{template_path:path}", dependencies=[Depends(require_permission("content:write"))])
async def delete_page_template(template_path: str):
    db = _db()
    template_name, parent_route = parse_page_template_path(template_path)
    coll = db[TEMPLATE_PAGES_COLLECTION]
    doc = await coll.find_one(_page_template_query(template_name, parent_route))
    if not doc:
        raise HTTPException(404, "Page template not found")

    linked_ref = _compose_page_template_style_ref(template_name, parent_route)
    removed_item_pages_count = 0
    template_kind = str(doc.get("template_kind") or "").strip().lower()
    source_type = str(doc.get("source_type") or "").strip().lower()
    is_item_page_template = template_kind == "item_page" or bool(parent_route) or source_type in {"blog", "tiles", "program"}
    if is_item_page_template:
        cleanup_report = await cleanup_generated_item_pages_for_template(db, doc)
        removed_item_pages_count = int(cleanup_report.get("removed_count", 0) or 0)

    linked_count = await db["pages"].count_documents(
        {
            "template_style_ref": linked_ref,
            "$or": [
                {"template_style_linked": True},
                {"template_style_linked": {"$exists": False}},
            ],
        }
    )
    if linked_count > 0:
        raise HTTPException(
            409,
            f'Cannot delete page template "{linked_ref}" while {linked_count} non-generated linked page(s) still reference it',
        )

    await coll.delete_one({"_id": doc["_id"]})
    config_prefix = item_page_config_key_prefix(doc.get("source_type"), doc.get("source_kind"))
    if config_prefix:
        config_key = f"{config_prefix}_template_path"
        global_cfg = await get_item_page_config(db)
        active_path = normalize_page_template_path_value(global_cfg.get(config_key))
        if active_path == linked_ref:
            await set_item_page_config(db, {config_key: ""})
    return {"ok": True, "removed_item_pages_count": removed_item_pages_count}


@router.post("/pages/{template_path:path}/instantiate", dependencies=[Depends(require_permission("content:write"))])
async def instantiate_page_template(
    template_path: str,
    payload: dict = Body(default_factory=dict),
):
    db = _db()
    template_name, parent_route = parse_page_template_path(template_path)
    if parent_route:
        raise HTTPException(400, "Item-page templates cannot be instantiated as static pages")

    template_doc = await db[TEMPLATE_PAGES_COLLECTION].find_one(
        _page_template_query(template_name, parent_route)
    )
    if not template_doc:
        raise HTTPException(404, "Page template not found")
    template_doc = await _ensure_template_page_design_state(db, template_doc)

    if str(template_doc.get("template_kind") or "").strip().lower() == "item_page":
        raise HTTPException(400, "Item-page templates cannot be instantiated as static pages")

    slug = str(payload.get("slug") or "").strip().strip("/")
    if not slug:
        raise HTTPException(400, "slug is required")
    if not re.fullmatch(r"[a-z0-9]+(?:[-/][a-z0-9]+)*", slug):
        raise HTTPException(400, "Invalid slug format")

    pages_coll = db["pages"]
    existing_page = await pages_coll.find_one({"slug": slug}, {"_id": 1})
    if existing_page:
        raise HTTPException(409, "Slug already exists")

    now = datetime.utcnow()
    header_id = None
    if bool(template_doc.get("has_header")):
        header_id = await _create_header_document_from_template(
            db,
            template_doc.get("header") if isinstance(template_doc.get("header"), dict) else None,
            now=now,
        )

    sections_payload = (
        template_doc.get("sections")
        if isinstance(template_doc.get("sections"), list)
        else []
    )
    sorted_sections = sorted(
        [normalize_embedded_section(section) for section in sections_payload if isinstance(section, dict)],
        key=lambda section: int(section.get("order", 0) or 0),
    )
    section_refs: list[dict] = []
    embedded_to_page_section_id: dict[str, str] = {}
    for order_index, section in enumerate(sorted_sections):
        section_id = await _create_section_document_from_template(db, section, now=now)
        embedded_id = str(section.get("id") or "").strip()
        if embedded_id:
            embedded_to_page_section_id[embedded_id] = section_id
        ref = {
            "section_id": section_id,
            "order": order_index,
            "visible": bool(section.get("visible", True)),
            "width_n": max(1, min(5, int(section.get("width_n", 1) or 1))),
            "width_d": max(1, min(5, int(section.get("width_d", 1) or 1))),
            "device_visibility": (
                deepcopy(section.get("device_visibility"))
                if isinstance(section.get("device_visibility"), dict)
                else {"mobile": True, "tablet": True, "desktop": True}
            ),
        }
        if ref["width_n"] > ref["width_d"]:
            ref["width_n"] = ref["width_d"]
        if section.get("limit") not in (None, "", 0, "0"):
            try:
                limit_value = int(section.get("limit"))
                if limit_value > 0:
                    ref["limit"] = limit_value
            except Exception:
                pass
        section_refs.append(ref)
    ordered_ids = [
        str(ref.get("section_id") or "").strip()
        for ref in sorted(section_refs, key=lambda ref: int(ref.get("order", 0) or 0))
        if str(ref.get("section_id") or "").strip()
    ]
    mapped_structure_seed: list[dict[str, Any]] = []
    raw_template_structure = (
        template_doc.get("section_structure")
        if isinstance(template_doc.get("section_structure"), list)
        else []
    )
    for node in raw_template_structure:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type") or "").strip().lower()
        if node_type == "section":
            template_section_id = str(node.get("section_id") or "").strip()
            mapped_section_id = embedded_to_page_section_id.get(template_section_id)
            if mapped_section_id:
                mapped_structure_seed.append(
                    {
                        "type": "section",
                        "section_id": mapped_section_id,
                    }
                )
            continue
        if node_type != "container":
            continue
        mapped_members = []
        raw_members = node.get("section_ids") if isinstance(node.get("section_ids"), list) else []
        for raw_member in raw_members:
            mapped_member = embedded_to_page_section_id.get(str(raw_member or "").strip())
            if mapped_member:
                mapped_members.append(mapped_member)
        if mapped_members:
            mapped_structure_seed.append(
                {
                    "type": "container",
                    "container_id": str(node.get("container_id") or "").strip() or _new_container_instance_id(),
                    "section_ids": mapped_members,
                }
            )
    normalized_section_structure = resolve_section_structure(
        mapped_structure_seed,
        ordered_ids,
    )
    section_refs = apply_section_order_from_structure(
        section_refs,
        normalized_section_structure,
        section_id_field="section_id",
    )

    provided_title = payload.get("title") if isinstance(payload.get("title"), dict) else None
    fallback_title = template_doc.get("title") if isinstance(template_doc.get("title"), dict) else {"de": "", "en": ""}
    title = _normalize_bilingual_text(provided_title or fallback_title, fallback=fallback_title)

    doc = {
        "slug": slug,
        "title": title,
        "has_header": bool(header_id),
        "header_id": header_id,
        "sections": section_refs,
        "section_structure": normalized_section_structure,
        "status": _normalize_page_status(
            payload.get("status") or template_doc.get("status"),
            fallback="hidden",
        ),
        "publish_at": None,
        "unpublish_at": None,
        "in_menu": bool(payload.get("in_menu", template_doc.get("in_menu", False))),
        "in_footer": bool(payload.get("in_footer", template_doc.get("in_footer", False))),
        "hide_in_admin_sitemap": bool(
            payload.get("hide_in_admin_sitemap", template_doc.get("hide_in_admin_sitemap", True))
        ),
        "hide_from_sitemap": bool(
            payload.get("hide_from_sitemap", template_doc.get("hide_from_sitemap", True))
        ),
        "hide_subtree_from_sitemap": bool(
            payload.get(
                "hide_subtree_from_sitemap",
                template_doc.get("hide_subtree_from_sitemap", True),
            )
        ),
        "sitemap_priority": payload.get("sitemap_priority", template_doc.get("sitemap_priority")),
        "sitemap_changefreq": payload.get("sitemap_changefreq", template_doc.get("sitemap_changefreq")),
        "generated_from_blog": False,
        "menu_title": deepcopy(template_doc.get("menu_title"))
        if isinstance(template_doc.get("menu_title"), dict)
        else None,
        "menu_order": int(payload.get("menu_order", template_doc.get("menu_order", 0)) or 0),
        "footer_order": int(payload.get("footer_order", template_doc.get("footer_order", 0)) or 0),
        "redirect_to": payload.get("redirect_to", template_doc.get("redirect_to")),
        "section_bg_pinned_start_key": str(
            payload.get(
                "section_bg_pinned_start_key",
                template_doc.get("section_bg_pinned_start_key", ""),
            )
            or ""
        ),
        "section_bg_pinned_end_key": str(
            payload.get(
                "section_bg_pinned_end_key",
                template_doc.get("section_bg_pinned_end_key", ""),
            )
            or ""
        ),
        "page_design_overrides": None,
        "template_style_ref": _compose_page_template_style_ref(template_name, parent_route),
        "template_style_linked": True,
        "template_style_lock": True,
        "created_at": now,
        "updated_at": now,
    }
    result = await pages_coll.insert_one(doc)
    return {"ok": True, "slug": slug, "page_id": str(result.inserted_id)}


@router.post("/containers/{template_name}/instantiate", dependencies=[Depends(require_permission("content:write"))])
async def instantiate_container_template(
    template_name: str,
    payload: dict = Body(...),
):
    page_slug = str(payload.get("slug") or "").strip().strip("/")
    if not page_slug:
        raise HTTPException(400, "slug is required")

    normalized_name = normalize_template_name(template_name)
    db = _db()
    container_doc = await db[TEMPLATE_CONTAINERS_COLLECTION].find_one({"template_name": normalized_name})
    if not container_doc:
        raise HTTPException(404, "Container template not found")

    pages_coll = db["pages"]
    page = await pages_coll.find_one({"slug": page_slug})
    if not page:
        raise HTTPException(404, "Page not found")

    sections_payload = (
        container_doc.get("sections")
        if isinstance(container_doc.get("sections"), list)
        else []
    )
    if not sections_payload:
        return {"ok": True, "added_section_ids": [], "container_id": None}

    now = datetime.utcnow()
    container_instance_id = _new_container_instance_id()
    section_refs = list(page.get("sections") if isinstance(page.get("sections"), list) else [])
    existing_ordered_refs = sorted(
        [ref for ref in section_refs if isinstance(ref, dict)],
        key=lambda ref: int(ref.get("order", 0) or 0),
    )
    existing_ordered_ids = [
        str(ref.get("section_id") or "").strip()
        for ref in existing_ordered_refs
        if str(ref.get("section_id") or "").strip()
    ]

    created_ids: list[str] = []
    sorted_sections = sorted(
        [normalize_embedded_section(section) for section in sections_payload if isinstance(section, dict)],
        key=lambda section: int(section.get("order", 0) or 0),
    )
    next_order = max([int(ref.get("order", 0) or 0) for ref in section_refs], default=-1) + 1
    for index, section in enumerate(sorted_sections):
        section_id = await _create_section_document_from_template(db, section, now=now)
        created_ids.append(section_id)
        ref_overrides = _merge_dict(
            section.get("design_overrides") if isinstance(section.get("design_overrides"), dict) else None,
            {
                CONTAINER_TEMPLATE_LOCK_KEY: True,
                CONTAINER_TEMPLATE_NAME_KEY: normalized_name,
            },
        )
        ref_overrides = strip_legacy_container_override(ref_overrides)
        ref = {
            "section_id": section_id,
            "order": next_order + index,
            "visible": bool(section.get("visible", True)),
            "width_n": max(1, min(5, int(section.get("width_n", 1) or 1))),
            "width_d": max(1, min(5, int(section.get("width_d", 1) or 1))),
            "device_visibility": (
                deepcopy(section.get("device_visibility"))
                if isinstance(section.get("device_visibility"), dict)
                else {"mobile": True, "tablet": True, "desktop": True}
            ),
            "design_overrides": ref_overrides,
        }
        if ref["width_n"] > ref["width_d"]:
            ref["width_n"] = ref["width_d"]
        if section.get("limit") not in (None, "", 0, "0"):
            try:
                limit_value = int(section.get("limit"))
                if limit_value > 0:
                    ref["limit"] = limit_value
            except Exception:
                pass
        section_refs.append(ref)

    ordered_refs = sorted(
        [ref for ref in section_refs if isinstance(ref, dict)],
        key=lambda ref: int(ref.get("order", 0) or 0),
    )
    ordered_ids = [
        str(ref.get("section_id") or "").strip()
        for ref in ordered_refs
        if str(ref.get("section_id") or "").strip()
    ]
    current_structure = resolve_section_structure(
        page.get("section_structure"),
        existing_ordered_ids,
    )
    next_structure_seed = [
        *current_structure,
        {
            "type": "container",
            "container_id": container_instance_id,
            "section_ids": created_ids,
        },
    ]
    normalized_structure = resolve_section_structure(
        next_structure_seed,
        ordered_ids,
    )
    section_refs = apply_section_order_from_structure(
        ordered_refs,
        normalized_structure,
        section_id_field="section_id",
    )

    await pages_coll.update_one(
        {"_id": page["_id"]},
        {
            "$set": {
                "sections": section_refs,
                "section_structure": normalized_structure,
                "updated_at": now,
            }
        },
    )
    return {
        "ok": True,
        "template_name": normalized_name,
        "container_id": container_instance_id,
        "added_section_ids": created_ids,
    }


# -------------------------
# Builder Endpoints
# -------------------------


@router.get("/builder/{kind}/full", dependencies=[Depends(require_permission("content:write"))])
async def get_builder_full(kind: str, path: str = Query(...)):
    resolved_kind, doc = await _resolve_builder_doc(kind, path, auto_create=True)

    if resolved_kind == "section":
        section_type, template_name = _parse_section_builder_path(path)
        return build_page_full_payload_for_template_section(section_type, template_name, doc)

    if resolved_kind == "container":
        template_name = _parse_container_builder_path(path)
        return build_page_full_payload_for_template_container(template_name, doc)

    template_name, parent_route = parse_page_template_path(path)
    normalized_path = compose_page_template_path(template_name, parent_route)
    return build_page_full_payload_for_template_page(normalized_path, doc)


@router.post("/builder/page/mapping-preview", dependencies=[Depends(require_permission("content:write"))])
async def preview_builder_page_mapping(path: str = Query(...), payload: dict = Body(default_factory=dict)):
    db = _db()
    template_name, parent_route = parse_page_template_path(path)
    doc = await db[TEMPLATE_PAGES_COLLECTION].find_one(
        _page_template_query(template_name, parent_route)
    )
    if not isinstance(doc, dict):
        raise HTTPException(404, "Page template not found")
    normalized_doc = await _normalize_builder_page_mapping_preview_doc(
        db,
        path=path,
        saved_doc=doc,
        payload=payload or {},
    )
    page_mapping = resolve_page_integration_mapping_for_template_doc(normalized_doc)
    preview_item_key = (
        str(payload.get("preview_item_key") or "").strip()
        if isinstance(payload, dict)
        else ""
    ) or str(page_mapping.get("preview_item_key") or "").strip()
    preview_item_index = (
        payload.get("preview_item_index")
        if isinstance(payload, dict) and "preview_item_index" in payload
        else page_mapping.get("preview_item_index")
    )
    result = await preview_item_page_mapping_from_template_state(
        db,
        normalized_doc,
        preview_item_key=preview_item_key,
        preview_item_index=preview_item_index,
    )
    return result


@router.post("/builder/{kind}", dependencies=[Depends(require_permission("content:write"))])
async def create_builder_page(kind: str, path: str = Query(...), payload: dict = Body(default_factory=dict)):
    db = _db()
    now = datetime.utcnow()

    if kind == "section":
        section_type, template_name = _parse_section_builder_path(path)
        existing = await db[TEMPLATE_SECTIONS_COLLECTION].find_one(
            {"section_type": section_type, "template_name": template_name}
        )
        if existing:
            return build_page_full_payload_for_template_section(section_type, template_name, existing)
        normalized = normalize_section_template_doc(
            section_type,
            template_name,
            payload,
            seed_list_target_visibility_presets=True,
        )
        normalized["created_at"] = now
        normalized["updated_at"] = now
        inserted = await db[TEMPLATE_SECTIONS_COLLECTION].insert_one(normalized)
        normalized["_id"] = inserted.inserted_id
        return build_page_full_payload_for_template_section(section_type, template_name, normalized)

    if kind == "container":
        template_name = _parse_container_builder_path(path)
        existing = await db[TEMPLATE_CONTAINERS_COLLECTION].find_one({"template_name": template_name})
        if existing:
            return build_page_full_payload_for_template_container(template_name, existing)
        normalized = normalize_container_template_doc(template_name, payload)
        normalized["created_at"] = now
        normalized["updated_at"] = now
        inserted = await db[TEMPLATE_CONTAINERS_COLLECTION].insert_one(normalized)
        normalized["_id"] = inserted.inserted_id
        return build_page_full_payload_for_template_container(template_name, normalized)

    if kind == "page":
        template_name, parent_route = parse_page_template_path(path)
        query = _page_template_query(template_name, parent_route)
        existing = await db[TEMPLATE_PAGES_COLLECTION].find_one(query)
        if existing:
            hydrated = await _ensure_template_page_design_state(db, existing)
            return build_page_full_payload_for_template_page(compose_page_template_path(template_name, parent_route), hydrated)
        await _raise_if_page_template_path_is_item_route(db, path)

        merged_payload = {
            **(payload or {}),
            "template_name": template_name,
            "parent_route": parent_route,
        }
        normalized = normalize_page_template_doc(
            compose_page_template_path(template_name, parent_route),
            merged_payload,
            seed_page_target_visibility_presets=True,
        )
        normalized = await _inject_source_route_payload_fields(db, merged_payload, normalized)
        await _apply_page_mapping_fixed_gig_primary_key_sources(db, normalized)
        await _validate_source_route_ref_matches_template_path(db, normalized)
        base_design, base_version_id = await resolve_global_published_design_snapshot(db)
        normalized["template_design_current"] = deepcopy(base_design)
        normalized["template_design_published"] = deepcopy(base_design)
        normalized["template_design_initialized_from_global_version_id"] = base_version_id
        normalized["template_design_updated_at"] = now
        normalized["template_design_published_at"] = now
        normalized["page_design_overrides"] = None
        normalized["created_at"] = now
        normalized["updated_at"] = now
        inserted = await db[TEMPLATE_PAGES_COLLECTION].insert_one(normalized)
        normalized["_id"] = inserted.inserted_id
        if normalized.get("source_type") == "blog" and normalized.get("parent_route"):
            await sync_all_blog_items_for_route(db, normalized["parent_route"])
        return build_page_full_payload_for_template_page(compose_page_template_path(template_name, parent_route), normalized)

    raise HTTPException(400, "Unsupported builder kind")


@router.patch("/builder/{kind}", dependencies=[Depends(require_permission("content:write"))])
async def update_builder_page(kind: str, path: str = Query(...), payload: dict = Body(...)):
    db = _db()
    resolved_kind, doc = await _resolve_builder_doc(kind, path, auto_create=True)
    patch = dict(payload or {})
    now = datetime.utcnow()

    if resolved_kind == "section":
        allowed_keys = {
            "title",
            "title_placeholder",
            "type_data",
            "design_overrides",
            "section_integration_mapping",
            "section_output_mapping",
        }
        patch = {key: value for key, value in patch.items() if key in allowed_keys}
        merged = {**doc, **patch}
        normalized = normalize_section_template_doc(doc.get("section_type", "text"), doc.get("template_name", "default"), merged)
        normalized["created_at"] = doc.get("created_at", now)
        normalized["updated_at"] = now
        updated = await db[TEMPLATE_SECTIONS_COLLECTION].find_one_and_update(
            {"_id": doc["_id"]},
            {"$set": normalized},
            return_document=ReturnDocument.AFTER,
        )
        section_type, template_name = _parse_section_builder_path(path)
        return _builder_page_response(build_page_full_payload_for_template_section(section_type, template_name, updated))

    if resolved_kind == "container":
        allowed_keys = {
            "title",
            "composition_name",
            "sections",
            "section_structure",
            "status",
            "in_menu",
            "in_footer",
            "hide_in_admin_sitemap",
            "hide_from_sitemap",
            "hide_subtree_from_sitemap",
            "sitemap_priority",
            "sitemap_changefreq",
            "menu_title",
            "menu_order",
            "footer_order",
            "redirect_to",
            "section_bg_pinned_start_key",
            "section_bg_pinned_end_key",
        }
        patch = {key: value for key, value in patch.items() if key in allowed_keys}
        if "section_structure" in patch:
            patch["section_structure"] = _normalize_builder_structure_ids(
                patch.get("section_structure"),
                sections=patch.get("sections") if isinstance(patch.get("sections"), list) else doc.get("sections"),
                owner_kind="container",
                owner_id=doc.get("_id"),
            )
        merged = {**doc, **patch}
        normalized = normalize_container_template_doc(doc.get("template_name", "container"), merged)
        normalized["created_at"] = doc.get("created_at", now)
        normalized["updated_at"] = now
        updated = await db[TEMPLATE_CONTAINERS_COLLECTION].find_one_and_update(
            {"_id": doc["_id"]},
            {"$set": normalized},
            return_document=ReturnDocument.AFTER,
        )
        template_name = _parse_container_builder_path(path)
        return _builder_page_response(build_page_full_payload_for_template_container(template_name, updated))

    allowed_keys = {
        "title",
        "has_header",
        "header",
        "sections",
        "section_structure",
        "status",
        "in_menu",
        "in_footer",
        "hide_in_admin_sitemap",
        "hide_from_sitemap",
        "hide_subtree_from_sitemap",
        "sitemap_priority",
        "sitemap_changefreq",
        "menu_title",
        "menu_order",
        "footer_order",
        "redirect_to",
        "section_bg_pinned_start_key",
        "section_bg_pinned_end_key",
        "template_kind",
        "source_type",
        "source_kind",
        "source_route_ref",
        "section_template_ref",
        "page_integration_mapping",
        "integration_match_mappings",
        "auto_match_rules",
    }
    patch = {key: value for key, value in patch.items() if key in allowed_keys}
    if "section_structure" in patch:
        patch["section_structure"] = _normalize_builder_structure_ids(
            patch.get("section_structure"),
            sections=patch.get("sections") if isinstance(patch.get("sections"), list) else doc.get("sections"),
            owner_kind="page",
            owner_id=doc.get("_id"),
        )
    merged = {**doc, **patch}
    template_name, parent_route = parse_page_template_path(path)
    normalized_path = compose_page_template_path(template_name, parent_route)
    normalized = normalize_page_template_doc(normalized_path, merged)
    normalized = await _inject_source_route_payload_fields(db, merged, normalized)
    await _apply_page_mapping_fixed_gig_primary_key_sources(db, normalized)
    await _validate_source_route_ref_matches_template_path(db, normalized)
    normalized["created_at"] = doc.get("created_at", now)
    normalized["updated_at"] = now
    normalized["template_design_current"] = (
        deepcopy(doc.get("template_design_current"))
        if isinstance(doc.get("template_design_current"), dict)
        else {}
    )
    normalized["template_design_published"] = (
        deepcopy(doc.get("template_design_published"))
        if isinstance(doc.get("template_design_published"), dict)
        else deepcopy(normalized["template_design_current"])
    )
    normalized["template_design_initialized_from_global_version_id"] = (
        str(doc.get("template_design_initialized_from_global_version_id") or "").strip() or None
    )
    normalized["template_design_updated_at"] = (
        doc.get("template_design_updated_at")
        if isinstance(doc.get("template_design_updated_at"), datetime)
        else normalized["updated_at"]
    )
    normalized["template_design_published_at"] = (
        doc.get("template_design_published_at")
        if isinstance(doc.get("template_design_published_at"), datetime)
        else normalized["updated_at"]
    )
    normalized["page_design_overrides"] = None
    mapped_target_keys = changed_item_page_mapping_target_keys(doc, normalized)
    updated = await db[TEMPLATE_PAGES_COLLECTION].find_one_and_update(
        {"_id": doc["_id"]},
        {"$set": normalized},
        return_document=ReturnDocument.AFTER,
    )

    if normalized.get("source_type") == "blog" and normalized.get("parent_route"):
        await sync_all_blog_items_for_route(db, normalized["parent_route"])
    await _sync_init_generated_pages_for_template_doc_scoped(
        db,
        updated,
        mapped_target_keys,
    )
    return _builder_page_response(build_page_full_payload_for_template_page(normalized_path, updated))


@router.post("/builder/{kind}/sections/create", dependencies=[Depends(require_permission("content:write"))])
async def create_builder_section(
    kind: str,
    background_tasks: BackgroundTasks,
    path: str = Query(...),
    payload: dict = Body(...),
):
    db = _db()
    resolved_kind, doc = await _resolve_builder_doc(kind, path, auto_create=True)
    now = datetime.utcnow()

    section_payload = normalize_embedded_section(payload)

    if resolved_kind == "section":
        normalized = normalize_section_template_doc(doc.get("section_type", "text"), doc.get("template_name", "default"), section_payload)
        normalized["created_at"] = doc.get("created_at", now)
        normalized["updated_at"] = now
        updated = await db[TEMPLATE_SECTIONS_COLLECTION].find_one_and_update(
            {"_id": doc["_id"]},
            {"$set": normalized},
            return_document=ReturnDocument.AFTER,
        )
        section_type, template_name = _parse_section_builder_path(path)
        return build_page_full_payload_for_template_section(section_type, template_name, updated)

    target_coll_name = TEMPLATE_PAGES_COLLECTION if resolved_kind == "page" else TEMPLATE_CONTAINERS_COLLECTION
    sections = doc.get("sections") if isinstance(doc.get("sections"), list) else []
    next_order = max([int(section.get("order", 0) or 0) for section in sections], default=-1) + 1
    section_payload["order"] = next_order
    sections.append(section_payload)
    sections, normalized_section_structure = _normalize_builder_embedded_sections(
        sections,
        doc.get("section_structure"),
        owner_kind=resolved_kind,
        owner_id=doc.get("_id"),
    )

    updated = await db[target_coll_name].find_one_and_update(
        {"_id": doc["_id"]},
        {
            "$set": {
                "sections": sections,
                "section_structure": normalized_section_structure,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    if resolved_kind == "container":
        template_name = _parse_container_builder_path(path)
        return build_page_full_payload_for_template_container(template_name, updated)

    template_name, parent_route = parse_page_template_path(path)
    normalized_path = compose_page_template_path(template_name, parent_route)
    _queue_init_generated_pages_sync(
        background_tasks,
        db,
        updated,
        mapped_target_keys=set(),
    )
    return build_page_full_payload_for_template_page(normalized_path, updated)


@router.post("/builder/{kind}/sections", dependencies=[Depends(require_permission("content:write"))])
async def add_existing_builder_section(
    kind: str,
    background_tasks: BackgroundTasks,
    path: str = Query(...),
    payload: dict = Body(...),
):
    section_id = str(payload.get("section_id") or "").strip()
    if not section_id:
        raise HTTPException(400, "section_id is required")

    try:
        owner_kind, owner_id, _ = parse_builder_section_id(section_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if owner_kind != "section":
        raise HTTPException(400, "Only section template references can be added")

    section_doc = await _db()[TEMPLATE_SECTIONS_COLLECTION].find_one({"_id": _safe_object_id(owner_id)})
    if not section_doc:
        raise HTTPException(404, "Section template not found")

    embedded = normalize_embedded_section(
        {
            "section_type": section_doc.get("section_type", "text"),
            "section_template_name": section_doc.get("template_name", "default"),
            "title_placeholder": section_doc.get("title_placeholder"),
            "title": deepcopy(section_doc.get("title")),
            "type_data": deepcopy(section_doc.get("type_data")),
            "design_overrides": deepcopy(section_doc.get("design_overrides")),
            "section_integration_mapping": deepcopy(section_doc.get("section_integration_mapping")),
        }
    )
    return await create_builder_section(kind, background_tasks, path=path, payload=embedded)


@router.patch("/builder/{kind}/sections/{section_id}/content", dependencies=[Depends(require_permission("content:write"))])
async def update_builder_section(kind: str, section_id: str, payload: dict = Body(...)):
    db = _db()
    now = datetime.utcnow()

    try:
        owner_kind, owner_id, embedded_id = parse_builder_section_id(section_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if owner_kind == "section":
        oid = _safe_object_id(owner_id)
        if oid is None:
            raise HTTPException(400, "Invalid section template id")

        current = await db[TEMPLATE_SECTIONS_COLLECTION].find_one({"_id": oid})
        if not current:
            raise HTTPException(404, "Section template not found")

        merged = {**current, **(payload or {})}
        normalized = normalize_section_template_doc(
            current.get("section_type", "text"),
            current.get("template_name", "default"),
            merged,
        )
        normalized["created_at"] = current.get("created_at", now)
        normalized["updated_at"] = now

        updated = await db[TEMPLATE_SECTIONS_COLLECTION].find_one_and_update(
            {"_id": oid},
            {"$set": normalized},
            return_document=ReturnDocument.AFTER,
        )
        section_type = updated.get("section_type", "text")
        return format_embedded_section_for_builder(
            updated.get("_id"),
            {
                "id": embedded_id or "single",
                "section_type": section_type,
                "title_placeholder": updated.get("title_placeholder"),
                "title": deepcopy(updated.get("title")),
                "type_data": deepcopy(updated.get("type_data")),
                "design_overrides": deepcopy(updated.get("design_overrides")),
                "section_integration_mapping": deepcopy(updated.get("section_integration_mapping")),
                "section_output_mapping": deepcopy(updated.get("section_output_mapping")),
                "order": 0,
                "visible": True,
                "width_n": 1,
                "width_d": 1,
            },
            kind="section",
        )

    target_coll_name = TEMPLATE_PAGES_COLLECTION if owner_kind == "page" else TEMPLATE_CONTAINERS_COLLECTION
    oid = _safe_object_id(owner_id)
    if oid is None or not embedded_id:
        raise HTTPException(400, "Invalid embedded section id")

    doc = await db[target_coll_name].find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Template not found")

    sections = doc.get("sections") if isinstance(doc.get("sections"), list) else []
    target_index = next((idx for idx, section in enumerate(sections) if str(section.get("id")) == embedded_id), None)
    if target_index is None:
        raise HTTPException(404, "Section not found in template")

    current = sections[target_index]
    merged = {**current, **(payload or {})}
    normalized = normalize_embedded_section(merged)
    normalized["id"] = embedded_id
    normalized["order"] = int(current.get("order", 0) or 0)
    normalized["visible"] = bool(current.get("visible", True))
    normalized["limit"] = current.get("limit")
    normalized["width_n"] = int(current.get("width_n", 1) or 1)
    normalized["width_d"] = int(current.get("width_d", 1) or 1)
    normalized["device_visibility"] = (
        deepcopy(current.get("device_visibility"))
        if isinstance(current.get("device_visibility"), dict)
        else {"mobile": True, "tablet": True, "desktop": True}
    )
    normalized["design_overrides"] = (
        deepcopy(current.get("design_overrides"))
        if isinstance(current.get("design_overrides"), dict)
        else None
    )
    normalized["design_overrides"] = strip_legacy_container_override(normalized.get("design_overrides"))

    sections[target_index] = normalized
    sections, normalized_section_structure = _normalize_builder_embedded_sections(
        sections,
        doc.get("section_structure"),
        owner_kind=owner_kind,
        owner_id=owner_id,
    )

    await db[target_coll_name].update_one(
        {"_id": oid},
        {
            "$set": {
                "sections": sections,
                "section_structure": normalized_section_structure,
                "updated_at": now,
            }
        },
    )
    if owner_kind == "page":
        updated_doc = await db[target_coll_name].find_one({"_id": oid})
        await _sync_init_generated_pages_for_template_doc_scoped(
            db,
            updated_doc,
            set(),
        )
    updated_section = next(
        (section for section in sections if str(section.get("id")) == embedded_id),
        normalized,
    )
    return format_embedded_section_for_builder(oid, updated_section, kind=owner_kind)


@router.get(
    "/builder/{kind}/sections/{section_id}/template-sync-preview",
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_builder_section_template_sync_preview(kind: str, section_id: str):
    (
        _owner_kind,
        _embedded_id,
        _target_coll_name,
        _oid,
        _doc,
        _sections,
        _target_index,
        section_type,
        template_name,
        _template_payload,
        _current_payload,
        changed_fields,
    ) = await _resolve_builder_section_template_sync_context(
        _db(),
        kind=kind,
        section_id=section_id,
    )
    return _template_sync_preview_response(
        section_id,
        section_type,
        template_name,
        changed_fields,
    )


@router.post(
    "/builder/{kind}/sections/{section_id}/sync-from-template",
    dependencies=[Depends(require_permission("content:write"))],
)
async def sync_builder_section_from_template(
    kind: str,
    section_id: str,
    user: KeycloakUser = Depends(get_current_user),
):
    db = _db()
    now = datetime.utcnow()
    (
        owner_kind,
        embedded_id,
        target_coll_name,
        oid,
        doc,
        sections,
        target_index,
        section_type,
        template_name,
        template_payload,
        _current_payload,
        changed_fields,
    ) = await _resolve_builder_section_template_sync_context(
        db,
        kind=kind,
        section_id=section_id,
    )

    if not changed_fields:
        return {
            "updated": False,
            "changed_fields": [],
            "template_ref": f"{section_type}/{template_name}",
            "section": format_embedded_section_for_builder(
                oid,
                sections[target_index],
                kind=owner_kind,
            ),
        }

    design_changed = "design_overrides" in changed_fields
    if design_changed:
        _require_design_write(user)

    content_changed_fields = [
        field for field in changed_fields if field != "design_overrides"
    ]
    current_section = deepcopy(sections[target_index])
    next_section = deepcopy(current_section)
    if content_changed_fields:
        for field in (
            "title_placeholder",
            "title",
            "type_data",
            "section_integration_mapping",
        ):
            next_section[field] = deepcopy(template_payload.get(field))
    if design_changed:
        next_section["design_overrides"] = deepcopy(
            template_payload.get("design_overrides")
        )

    normalized = normalize_embedded_section(next_section)
    normalized["id"] = embedded_id
    normalized["order"] = int(current_section.get("order", 0) or 0)
    normalized["visible"] = bool(current_section.get("visible", True))
    normalized["limit"] = current_section.get("limit")
    normalized["width_n"] = int(current_section.get("width_n", 1) or 1)
    normalized["width_d"] = int(current_section.get("width_d", 1) or 1)
    normalized["device_visibility"] = (
        deepcopy(current_section.get("device_visibility"))
        if isinstance(current_section.get("device_visibility"), dict)
        else {"mobile": True, "tablet": True, "desktop": True}
    )

    next_sections = list(sections)
    next_sections[target_index] = normalized
    next_sections, normalized_section_structure = _normalize_builder_embedded_sections(
        next_sections,
        doc.get("section_structure"),
        owner_kind=owner_kind,
        owner_id=oid,
    )

    await db[target_coll_name].update_one(
        {"_id": oid},
        {
            "$set": {
                "sections": next_sections,
                "section_structure": normalized_section_structure,
                "updated_at": now,
            }
        },
    )
    if owner_kind == "page":
        updated_doc = await db[target_coll_name].find_one({"_id": oid})
        await _sync_init_generated_pages_for_template_doc_scoped(
            db,
            updated_doc,
            set(),
        )

    updated_section = next(
        (section for section in next_sections if str(section.get("id")) == embedded_id),
        normalized,
    )
    return {
        "updated": True,
        "changed_fields": changed_fields,
        "template_ref": f"{section_type}/{template_name}",
        "section": format_embedded_section_for_builder(
            oid,
            updated_section,
            kind=owner_kind,
        ),
    }


@router.patch("/builder/{kind}/sections/{section_id}/design", dependencies=[Depends(require_permission("content:write"))])
async def update_builder_section_design(
    kind: str,
    section_id: str,
    payload: dict | None = Body(default=None),
    user: KeycloakUser = Depends(get_current_user),
):
    overrides = payload
    if isinstance(payload, dict) and "overrides" in payload:
        overrides = payload.get("overrides")

    if overrides is not None and not isinstance(overrides, dict):
        overrides = None

    _require_design_write(user)

    return await update_builder_section(kind, section_id, payload={"design_overrides": overrides})


@router.patch("/builder/{kind}/sections/{section_id}", dependencies=[Depends(require_permission("content:write"))])
async def update_builder_section_ref(
    kind: str,
    section_id: str,
    order: int | None = Query(default=None),
    visible: bool | None = Query(default=None),
    limit: int | None = Query(default=None),
    width_n: int | None = Query(default=None, ge=1, le=5),
    width_d: int | None = Query(default=None, ge=1, le=5),
    device_mobile: bool | None = Query(default=None),
    device_tablet: bool | None = Query(default=None),
    device_desktop: bool | None = Query(default=None),
):
    # This endpoint mirrors /pages/{slug}/sections/{section_id} update semantics.
    db = _db()
    now = datetime.utcnow()

    try:
        owner_kind, owner_id, embedded_id = parse_builder_section_id(section_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if owner_kind == "section":
        raise HTTPException(400, "Section template references do not support page-level ref updates")

    if owner_kind != kind:
        raise HTTPException(400, "Section owner does not match builder kind")

    target_coll_name = TEMPLATE_PAGES_COLLECTION if owner_kind == "page" else TEMPLATE_CONTAINERS_COLLECTION
    oid = _safe_object_id(owner_id)
    if oid is None or not embedded_id:
        raise HTTPException(400, "Invalid embedded section id")

    doc = await db[target_coll_name].find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Template not found")

    sections = doc.get("sections") if isinstance(doc.get("sections"), list) else []
    target = next((section for section in sections if str(section.get("id")) == embedded_id), None)
    if target is None:
        raise HTTPException(404, "Section not found in template")

    if order is not None:
        target["order"] = int(order)
    if visible is not None:
        target["visible"] = bool(visible)
    if limit is not None:
        target["limit"] = int(limit) if int(limit) > 0 else None
    if width_n is not None:
        target["width_n"] = int(width_n)
    if width_d is not None:
        target["width_d"] = int(width_d)
    if int(target.get("width_n", 1) or 1) > int(target.get("width_d", 1) or 1):
        target["width_n"] = int(target.get("width_d", 1) or 1)

    if device_mobile is not None or device_tablet is not None or device_desktop is not None:
        current_device_visibility = target.get("device_visibility") if isinstance(target.get("device_visibility"), dict) else {}
        target["device_visibility"] = {
            "mobile": bool(device_mobile if device_mobile is not None else current_device_visibility.get("mobile", True)),
            "tablet": bool(device_tablet if device_tablet is not None else current_device_visibility.get("tablet", True)),
            "desktop": bool(device_desktop if device_desktop is not None else current_device_visibility.get("desktop", True)),
        }

    sections, normalized_section_structure = _normalize_builder_embedded_sections(
        sections,
        doc.get("section_structure"),
        owner_kind=owner_kind,
        owner_id=owner_id,
    )

    await db[target_coll_name].update_one(
        {"_id": oid},
        {
            "$set": {
                "sections": sections,
                "section_structure": normalized_section_structure,
                "updated_at": now,
            }
        },
    )
    if owner_kind == "page":
        updated_doc = await db[target_coll_name].find_one({"_id": oid})
        await _sync_init_generated_pages_for_template_doc_scoped(
            db,
            updated_doc,
            set(),
        )

    return {"ok": True}


@router.delete("/builder/{kind}/sections/{section_id}", dependencies=[Depends(require_permission("content:write"))])
async def delete_builder_section(kind: str, section_id: str, background_tasks: BackgroundTasks):
    db = _db()
    now = datetime.utcnow()

    try:
        owner_kind, owner_id, embedded_id = parse_builder_section_id(section_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if owner_kind == "section":
        raise HTTPException(400, "Cannot remove the root section from a section template")

    if owner_kind != kind:
        raise HTTPException(400, "Section owner does not match builder kind")

    target_coll_name = TEMPLATE_PAGES_COLLECTION if owner_kind == "page" else TEMPLATE_CONTAINERS_COLLECTION
    oid = _safe_object_id(owner_id)
    if oid is None or not embedded_id:
        raise HTTPException(400, "Invalid embedded section id")

    doc = await db[target_coll_name].find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Template not found")

    sections = doc.get("sections") if isinstance(doc.get("sections"), list) else []
    next_sections = [section for section in sections if str(section.get("id")) != embedded_id]
    if len(next_sections) == len(sections):
        raise HTTPException(404, "Section not found in template")
    next_sections, normalized_section_structure = _normalize_builder_embedded_sections(
        next_sections,
        doc.get("section_structure"),
        owner_kind=owner_kind,
        owner_id=owner_id,
    )

    updated_doc = await db[target_coll_name].find_one_and_update(
        {"_id": oid},
        {
            "$set": {
                "sections": next_sections,
                "section_structure": normalized_section_structure,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not updated_doc:
        raise HTTPException(404, "Template not found")
    if owner_kind == "page":
        _queue_init_generated_pages_sync(
            background_tasks,
            db,
            updated_doc,
            mapped_target_keys=set(),
        )
        normalized_path = compose_page_template_path(
            str(updated_doc.get("template_name") or ""),
            updated_doc.get("parent_route"),
        )
        return build_page_full_payload_for_template_page(normalized_path, updated_doc)

    template_name = str(updated_doc.get("template_name") or "container")
    return build_page_full_payload_for_template_container(template_name, updated_doc)


@router.put("/builder/{kind}/header", dependencies=[Depends(require_permission("content:write"))])
async def upsert_builder_header(
    kind: str,
    path: str = Query(...),
    payload: dict = Body(...),
    user: KeycloakUser = Depends(get_current_user),
):
    db = _db()
    resolved_kind, doc = await _resolve_builder_doc(kind, path, auto_create=True)
    now = datetime.utcnow()

    if resolved_kind != "page":
        raise HTTPException(400, "Only page templates support headers")

    normalized_header = _normalize_template_header_payload(payload)
    if normalized_header and normalized_header.get("design_overrides") is not None:
        _require_design_write(user)

    updated = await db[TEMPLATE_PAGES_COLLECTION].find_one_and_update(
        {"_id": doc["_id"]},
        {
            "$set": {
                "has_header": True,
                "header": normalized_header,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    header_payload = _format_template_header_for_builder(updated)
    if not header_payload:
        raise HTTPException(500, "Failed to update template header")

    if updated.get("source_type") == "blog" and updated.get("parent_route"):
        await sync_all_blog_items_for_route(db, updated["parent_route"])
    await _sync_init_generated_pages_for_template_doc_scoped(db, updated, set())

    return header_payload


@router.patch("/builder/{kind}/header/design", dependencies=[Depends(require_permission("content:write"))])
async def update_builder_header_design(
    kind: str,
    path: str = Query(...),
    payload: dict | None = Body(default=None),
    user: KeycloakUser = Depends(get_current_user),
):
    _require_design_write(user)
    overrides = payload
    if isinstance(payload, dict) and "overrides" in payload:
        overrides = payload.get("overrides")
    if overrides is not None and not isinstance(overrides, dict):
        overrides = None

    if kind != "page":
        raise HTTPException(400, "Only page templates support headers")

    resolved_kind, doc = await _resolve_builder_doc(kind, path, auto_create=True)
    if resolved_kind != "page":
        raise HTTPException(400, "Only page templates support headers")

    header_payload = deepcopy(doc.get("header")) if isinstance(doc.get("header"), dict) else {}
    header_payload["design_overrides"] = deepcopy(overrides)

    return await upsert_builder_header(kind, path=path, payload=header_payload, user=user)


@router.get("/builder/header/{header_id}", dependencies=[Depends(require_permission("content:write"))])
async def get_builder_header(header_id: str):
    owner_kind, owner_id = parse_builder_header_id(header_id)
    if owner_kind != "page":
        raise HTTPException(400, "Unsupported template header kind")

    oid = _safe_object_id(owner_id)
    if oid is None:
        raise HTTPException(400, "Invalid template header id")

    page_doc = await _db()[TEMPLATE_PAGES_COLLECTION].find_one({"_id": oid})
    if not page_doc:
        raise HTTPException(404, "Page template not found")

    header_payload = _format_template_header_for_builder(page_doc)
    if not header_payload:
        raise HTTPException(404, "Template header not found")
    return header_payload


@router.patch("/builder/header/{header_id}", dependencies=[Depends(require_permission("content:write"))])
async def patch_builder_header(
    header_id: str,
    payload: dict = Body(...),
    user: KeycloakUser = Depends(get_current_user),
):
    owner_kind, owner_id = parse_builder_header_id(header_id)
    if owner_kind != "page":
        raise HTTPException(400, "Unsupported template header kind")

    oid = _safe_object_id(owner_id)
    if oid is None:
        raise HTTPException(400, "Invalid template header id")

    coll = _db()[TEMPLATE_PAGES_COLLECTION]
    current = await coll.find_one({"_id": oid})
    if not current:
        raise HTTPException(404, "Page template not found")

    header_payload = current.get("header") if isinstance(current.get("header"), dict) else {}
    merged = {**header_payload, **payload}
    normalized = _normalize_template_header_payload(merged)
    if normalized and normalized.get("design_overrides") is not None:
        _require_design_write(user)

    updated = await coll.find_one_and_update(
        {"_id": oid},
        {
            "$set": {
                "header": normalized,
                "has_header": True,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    header_result = _format_template_header_for_builder(updated)
    if not header_result:
        raise HTTPException(500, "Failed to update template header")

    if updated.get("source_type") == "blog" and updated.get("parent_route"):
        await sync_all_blog_items_for_route(_db(), updated["parent_route"])

    return header_result


@router.get("/builder/sections/{section_id}", dependencies=[Depends(require_permission("content:write"))])
async def get_builder_section(section_id: str):
    try:
        owner_kind, owner_id, embedded_id = parse_builder_section_id(section_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    db = _db()
    if owner_kind == "section":
        oid = _safe_object_id(owner_id)
        if oid is None:
            raise HTTPException(400, "Invalid section template id")
        doc = await db[TEMPLATE_SECTIONS_COLLECTION].find_one({"_id": oid})
        if not doc:
            raise HTTPException(404, "Section template not found")
        return format_embedded_section_for_builder(
            doc.get("_id"),
            {
                "id": embedded_id or "single",
                "section_type": doc.get("section_type", "text"),
                "title_placeholder": doc.get("title_placeholder"),
                "title": deepcopy(doc.get("title")),
                "type_data": deepcopy(doc.get("type_data")),
                "design_overrides": deepcopy(doc.get("design_overrides")),
                "order": 0,
                "visible": True,
                "width_n": 1,
                "width_d": 1,
            },
            kind="section",
        )

    coll_name = TEMPLATE_PAGES_COLLECTION if owner_kind == "page" else TEMPLATE_CONTAINERS_COLLECTION
    oid = _safe_object_id(owner_id)
    if oid is None or not embedded_id:
        raise HTTPException(400, "Invalid embedded section id")

    doc = await db[coll_name].find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Template not found")

    section = next((entry for entry in (doc.get("sections") or []) if str(entry.get("id")) == embedded_id), None)
    if not section:
        raise HTTPException(404, "Section not found in template")

    return format_embedded_section_for_builder(oid, section, kind=owner_kind)


# -------------------------
# Scoped CSS Snippets
# -------------------------


@router.get("/css-snippets", dependencies=[Depends(require_permission("content:write"))])
async def list_template_css_snippets(
    template_key: str = Query(...),
):
    coll = _db()["css_snippets"]
    cursor = coll.find(
        {
            "scope": "template",
            "template_key": str(template_key).strip(),
        }
    ).sort("created_at", -1)
    snippets = []
    async for doc in cursor:
        snippets.append(_format_doc(doc))
    return {"snippets": snippets}


@router.post("/css-snippets", dependencies=[Depends(require_permission("content:write"))])
async def create_template_css_snippet(
    payload: dict = Body(...),
    user: KeycloakUser = Depends(get_current_user),
):
    _require_design_write(user)

    css = str(payload.get("css") or "").strip()
    template_key = str(payload.get("template_key") or "").strip()
    if not css:
        raise HTTPException(400, "CSS content is required")
    if not template_key:
        raise HTTPException(400, "template_key is required")

    now = datetime.utcnow()
    doc = {
        "label": str(payload.get("label") or f"Template Snippet {now.strftime('%Y-%m-%d %H:%M')}").strip(),
        "css": css,
        "active": payload.get("active", True) is not False,
        "created_by": user.name or user.username or user.sub,
        "created_at": now,
        "updated_at": now,
        "scope": "template",
        "template_key": template_key,
    }
    media_scope = payload.get("media_scope")
    if media_scope in {"tablet", "mobile"}:
        doc["media_scope"] = media_scope
    context_key = payload.get("context_key")
    if isinstance(context_key, str) and context_key.strip():
        doc["context_key"] = context_key.strip()

    result = await _db()["css_snippets"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _format_doc(doc)


@router.patch("/css-snippets/{snippet_id}", dependencies=[Depends(require_permission("content:write"))])
async def update_template_css_snippet(
    snippet_id: str,
    payload: dict = Body(...),
    user: KeycloakUser = Depends(get_current_user),
):
    _require_design_write(user)

    oid = _safe_object_id(snippet_id)
    if oid is None:
        raise HTTPException(400, "Invalid snippet id")

    allowed = {"label", "css", "active", "media_scope", "context_key"}
    patch = {key: value for key, value in payload.items() if key in allowed}
    if "media_scope" in patch and patch["media_scope"] not in (None, "tablet", "mobile"):
        patch.pop("media_scope", None)
    if "context_key" in patch:
        if isinstance(patch["context_key"], str):
            patch["context_key"] = patch["context_key"].strip()
        if not patch.get("context_key"):
            patch.pop("context_key", None)
    if not patch:
        raise HTTPException(400, "No valid fields to update")

    patch["updated_at"] = datetime.utcnow()

    updated = await _db()["css_snippets"].find_one_and_update(
        {
            "_id": oid,
            "scope": "template",
        },
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(404, "Template snippet not found")
    return _format_doc(updated)


@router.delete("/css-snippets/{snippet_id}", dependencies=[Depends(require_permission("content:write"))])
async def delete_template_css_snippet(
    snippet_id: str,
    user: KeycloakUser = Depends(get_current_user),
):
    _require_design_write(user)

    oid = _safe_object_id(snippet_id)
    if oid is None:
        raise HTTPException(400, "Invalid snippet id")

    result = await _db()["css_snippets"].delete_one(
        {"_id": oid, "scope": "template"}
    )
    if result.deleted_count == 0:
        raise HTTPException(404, "Template snippet not found")
    return {"deleted": True}
