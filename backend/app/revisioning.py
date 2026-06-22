from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
from typing import Any, Callable

from bson import BSON, ObjectId
from pydantic import BaseModel
from pymongo.errors import WriteError

from app import program_catalog
from app.collection_names import (
    BLOG_CONFIG_COLLECTION,
    BLOG_SHARED_COLLECTION,
    CHANGELOG_COLLECTION,
    FAQ_SHARED_COLLECTION,
    REVISION_CONFIG_COLLECTION,
    REVISIONS_COLLECTION,
)
from app.media_responsive import merge_media_variant_entries, normalize_media_variant_entries
from app.models.faq import FAQSharedItem

REVISION_CONFIG_KEY = "global"

DEFAULT_SHOW_GLOBAL_DESIGN_REVISIONS = True
DEFAULT_SECTION_REVISION_OPTIONS = {
    "include_content": True,
    "include_design": True,
}
DEFAULT_HEADER_REVISION_OPTIONS = {
    "include_content": True,
    "include_design": True,
}

REVISION_HISTORY_LIMIT = 5
REVISION_DOCUMENT_BSON_BUDGET = 15 * 1024 * 1024
MONGO_BSON_TOO_LARGE_CODE = 10334
PROGRAM_SHARED_DOC_ID = program_catalog.PROGRAM_SHARED_DOC_ID
FAQ_SHARED_DOC_ID = "shared"
PROGRAM_SHARED_REVISION_CACHE_STATE_KEYS = frozenset(
    {
        "cache_id",
        "fetched_at",
        "import_mode",
        "integration_id",
        "integration_output_primary_key_path",
        "list_primary_key_paths",
        "overwritten_paths",
        "source_changed",
        "source_changed_paths",
        "source_etag",
        "source_hash",
    }
)
PROGRAM_SECTION_SHARED_CONTENT_FIELDS = frozenset(
    {
        "stages",
        "program_stages_integration_mapping",
        "programStagesIntegrationMapping",
        "program_stages_integration_mapping_cache_state",
        "programStagesIntegrationMappingCacheState",
        "program_gigs_integration_mapping",
        "programGigsIntegrationMapping",
        "program_gigs_integration_mapping_cache_state",
        "programGigsIntegrationMappingCacheState",
    }
)


def snapshot_document(doc: dict, *, exclude_keys: set[str] | frozenset[str] | None = None) -> dict:
    """Create a deep-copied revision snapshot from a MongoDB document."""
    excluded = set(exclude_keys or set())
    return deepcopy({k: v for k, v in doc.items() if k not in excluded})


def _sanitize_program_section_doc_for_content_snapshot(section_doc: dict) -> dict:
    if str(section_doc.get("section_type") or "").strip().lower() != "program":
        return section_doc

    type_data = section_doc.get("type_data")
    if not isinstance(type_data, dict):
        return section_doc

    sanitized_type_data: dict[str, Any] = {}
    changed = False
    for key, value in type_data.items():
        if key in PROGRAM_SECTION_SHARED_CONTENT_FIELDS:
            changed = True
            continue
        sanitized_type_data[key] = value

    if not changed:
        return section_doc
    return {
        **section_doc,
        "type_data": sanitized_type_data,
    }


def normalize_section_revision_options(options: dict[str, Any] | None) -> dict[str, bool]:
    source = options or {}
    return {
        "include_content": bool(
            source.get(
                "include_content",
                DEFAULT_SECTION_REVISION_OPTIONS["include_content"],
            )
        ),
        "include_design": bool(
            source.get(
                "include_design",
                DEFAULT_SECTION_REVISION_OPTIONS["include_design"],
            )
        ),
    }


def normalize_revision_config(doc: dict | None) -> dict:
    source = doc or {}
    normalized_section_types: dict[str, dict[str, bool]] = {}

    raw_section_types = source.get("section_types", {})
    if isinstance(raw_section_types, dict):
        for section_type, section_options in raw_section_types.items():
            if not isinstance(section_type, str) or not section_type.strip():
                continue
            normalized_section_types[section_type] = normalize_section_revision_options(
                section_options if isinstance(section_options, dict) else None
            )

    raw_header = source.get("header")

    return {
        "key": REVISION_CONFIG_KEY,
        "show_global_design_revisions": bool(
            source.get(
                "show_global_design_revisions",
                DEFAULT_SHOW_GLOBAL_DESIGN_REVISIONS,
            )
        ),
        "header": normalize_header_revision_options(
            raw_header if isinstance(raw_header, dict) else None
        ),
        "section_types": normalized_section_types,
    }


def normalize_header_revision_options(options: dict[str, Any] | None) -> dict[str, bool]:
    source = options or {}
    return {
        "include_content": bool(
            source.get(
                "include_content",
                DEFAULT_HEADER_REVISION_OPTIONS["include_content"],
            )
        ),
        "include_design": bool(
            source.get(
                "include_design",
                DEFAULT_HEADER_REVISION_OPTIONS["include_design"],
            )
        ),
    }


async def get_or_create_revision_config(db) -> dict:
    """Load revision config, creating a normalized default document when missing."""
    coll = db[REVISION_CONFIG_COLLECTION]
    doc = await coll.find_one({"key": REVISION_CONFIG_KEY})
    if doc:
        return normalize_revision_config(doc)

    now = datetime.utcnow()
    normalized = normalize_revision_config(None)
    await coll.insert_one(
        {
            **normalized,
            "created_at": now,
            "updated_at": now,
        }
    )
    return normalized


async def save_revision_config(db, config: dict) -> dict:
    """Persist revision config and return the normalized payload."""
    coll = db[REVISION_CONFIG_COLLECTION]
    now = datetime.utcnow()
    normalized = normalize_revision_config(config)
    await coll.update_one(
        {"key": REVISION_CONFIG_KEY},
        {
            "$set": {
                **normalized,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return normalized


def get_section_revision_options(config: dict | None, section_type: str) -> dict[str, bool]:
    normalized = normalize_revision_config(config)
    raw_options = normalized.get("section_types", {}).get(section_type)
    return normalize_section_revision_options(raw_options)


def section_revision_history_enabled(options: dict[str, bool] | None) -> bool:
    normalized = normalize_section_revision_options(options)
    return bool(normalized["include_content"] or normalized["include_design"])


def get_header_revision_options(config: dict | None) -> dict[str, bool]:
    normalized = normalize_revision_config(config)
    raw_options = normalized.get("header")
    return normalize_header_revision_options(raw_options)


def header_revisions_enabled(options: dict[str, bool] | None) -> bool:
    normalized = normalize_header_revision_options(options)
    return bool(normalized["include_content"] or normalized["include_design"])


def is_global_design_revisions_enabled(config: dict | None) -> bool:
    normalized = normalize_revision_config(config)
    return bool(normalized["show_global_design_revisions"])


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _stable_value(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_stable_value(v) for v in value]
    return value


def snapshots_equal(left: Any, right: Any) -> bool:
    return _stable_value(left) == _stable_value(right)


def _is_bson_too_large_error(exc: WriteError) -> bool:
    message = str(exc).lower()
    return (
        getattr(exc, "code", None) == MONGO_BSON_TOO_LARGE_CODE
        or "bsonobj size" in message
        or "too large" in message
    )


def _revision_history_limit_for_entry(entry: dict, max_history: int) -> int:
    """Shrink retained history for large snapshots so one revision doc stays below BSON limits."""
    try:
        entry_size = len(BSON.encode({"history": [entry]}))
    except Exception:
        return max(1, max_history)
    if entry_size >= REVISION_DOCUMENT_BSON_BUDGET:
        return 0
    return max(1, min(max_history, REVISION_DOCUMENT_BSON_BUDGET // max(entry_size, 1)))


def as_object_id(value: str | ObjectId | None) -> ObjectId | None:
    if not value:
        return None
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def normalize_saved_at_label(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _changelog_bilingual_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    for lang in ("de", "en"):
        text = str(value.get(lang) or "").strip()
        if text:
            return text
    for raw in value.values():
        text = str(raw or "").strip()
        if text:
            return text
    return ""


def _humanize_changelog_section_type(section_type: Any) -> str:
    text = str(section_type or "section").strip() or "section"
    return " ".join(part.capitalize() for part in re.split(r"[_-]+", text) if part) or "Section"


def _resolve_changelog_section_label(section_doc: dict | None, entity_id: str) -> str:
    if isinstance(section_doc, dict):
        title = _changelog_bilingual_text(section_doc.get("title"))
        if title:
            return title
        placeholder = str(section_doc.get("title_placeholder") or "").strip()
        if placeholder:
            return placeholder
        return (
            f"{_humanize_changelog_section_type(section_doc.get('section_type'))} "
            f"({str(entity_id or '')[-6:]})"
        )
    return f"Section ({str(entity_id or '')[-6:]})"


async def append_global_changelog_entry(
    revisions,
    *,
    entity_type: str,
    entity_id: str,
    revision_doc_id: str | ObjectId | None,
    revision_entry: dict,
) -> None:
    """Append compact metadata for global section revision browsing."""
    if entity_type != "section":
        return

    db = revisions.database
    section_doc = None
    section_oid = as_object_id(entity_id)
    if section_oid is not None:
        section_doc = await db["sections"].find_one(
            {"_id": section_oid},
            {"section_type": 1, "title": 1, "title_placeholder": 1},
        )

    saved_at = revision_entry.get("saved_at")
    if not isinstance(saved_at, datetime):
        saved_at = datetime.utcnow()

    doc = {
        "entry_type": "section_revision",
        "entity_type": "section",
        "entity_id": str(entity_id),
        "revision_id": str(revision_doc_id) if revision_doc_id else None,
        "saved_at": saved_at,
        "saved_by": revision_entry.get("saved_by"),
        "change_kind": revision_entry.get("change_kind"),
        "reverted_from_saved_at": normalize_saved_at_label(
            revision_entry.get("reverted_from_saved_at")
        ),
        "section_type": str((section_doc or {}).get("section_type") or ""),
        "section_label": _resolve_changelog_section_label(section_doc, str(entity_id)),
        "created_at": datetime.utcnow(),
    }
    await db[CHANGELOG_COLLECTION].insert_one(doc)


async def push_revision_entry(
    revisions,
    *,
    entity_type: str,
    entity_id: str,
    current_data: dict,
    revision_id: str | ObjectId | None = None,
    saved_by: str | None = None,
    change_kind: str | None = None,
    reverted_from_saved_at: Any = None,
    max_history: int = REVISION_HISTORY_LIMIT,
) -> str | None:
    """Push a revision entry into history, clearing future and trimming size."""
    now = datetime.utcnow()
    normalized_kind = change_kind if change_kind in {"content", "design", "both"} else None
    entry = {"saved_at": now, "saved_by": saved_by, "data": deepcopy(current_data)}
    if normalized_kind:
        entry["change_kind"] = normalized_kind
    normalized_reverted_from = normalize_saved_at_label(reverted_from_saved_at)
    if normalized_reverted_from:
        entry["reverted_from_saved_at"] = normalized_reverted_from
    use_split_streams = entity_type in {"section", "header"} and normalized_kind in {"content", "design"}

    existing_doc = None
    revision_oid = as_object_id(revision_id)
    if revision_oid is not None:
        existing_doc = await revisions.find_one({"_id": revision_oid})
    if not existing_doc:
        existing_doc = await revisions.find_one(
            {"entity_type": entity_type, "entity_id": entity_id}
        )
    history_limit = _revision_history_limit_for_entry(entry, max_history)
    if history_limit <= 0:
        return str(existing_doc["_id"]) if existing_doc else None

    if existing_doc:
        if use_split_streams:
            history_key = f"{normalized_kind}_history"
            future_key = f"{normalized_kind}_future"
            kind_last_saved_by_key = f"{normalized_kind}_last_saved_by"
            kind_last_saved_at_key = f"{normalized_kind}_last_saved_at"

            history = existing_doc.get(history_key, [])
            if history:
                last_entry = history[-1]
                if snapshots_equal(last_entry.get("data"), entry["data"]):
                    await revisions.update_one(
                        {"_id": existing_doc["_id"]},
                        {
                            "$set": {
                                future_key: [],
                            }
                        },
                    )
                    return str(existing_doc["_id"])

            try:
                await revisions.update_one(
                    {"_id": existing_doc["_id"]},
                    {
                        "$push": {history_key: {"$each": [entry], "$slice": -history_limit}},
                        "$set": {
                            future_key: [],
                            "last_saved_by": saved_by,
                            "last_saved_at": now,
                            kind_last_saved_by_key: saved_by,
                            kind_last_saved_at_key: now,
                        },
                    },
                )
            except WriteError as exc:
                if _is_bson_too_large_error(exc):
                    return str(existing_doc["_id"])
                raise
            await append_global_changelog_entry(
                revisions,
                entity_type=entity_type,
                entity_id=entity_id,
                revision_doc_id=existing_doc["_id"],
                revision_entry=entry,
            )
            return str(existing_doc["_id"])

        history = existing_doc.get("history", [])
        if history:
            last_entry = history[-1]
            if snapshots_equal(last_entry.get("data"), entry["data"]):
                # Data is unchanged; keep a clean redo stack and fresh metadata.
                await revisions.update_one(
                    {"_id": existing_doc["_id"]},
                    {
                        "$set": {
                            "future": [],
                        }
                    },
                )
                return str(existing_doc["_id"])

        try:
            await revisions.update_one(
                {"_id": existing_doc["_id"]},
                {
                    "$push": {"history": {"$each": [entry], "$slice": -history_limit}},
                    "$set": {
                        "future": [],
                        "last_saved_by": saved_by,
                        "last_saved_at": now,
                    },
                },
            )
        except WriteError as exc:
            if _is_bson_too_large_error(exc):
                return str(existing_doc["_id"])
            raise
        await append_global_changelog_entry(
            revisions,
            entity_type=entity_type,
            entity_id=entity_id,
            revision_doc_id=existing_doc["_id"],
            revision_entry=entry,
        )
        return str(existing_doc["_id"])

    if use_split_streams:
        history_key = f"{normalized_kind}_history"
        future_key = f"{normalized_kind}_future"
        kind_last_saved_by_key = f"{normalized_kind}_last_saved_by"
        kind_last_saved_at_key = f"{normalized_kind}_last_saved_at"
        new_doc = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "history": [],
            "future": [],
            "content_history": [],
            "content_future": [],
            "design_history": [],
            "design_future": [],
            history_key: [entry],
            future_key: [],
            "last_saved_by": saved_by,
            "last_saved_at": now,
            kind_last_saved_by_key: saved_by,
            kind_last_saved_at_key: now,
        }
    else:
        new_doc = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "history": [entry],
            "future": [],
            "last_saved_by": saved_by,
            "last_saved_at": now,
        }
    try:
        result = await revisions.insert_one(new_doc)
    except WriteError as exc:
        if _is_bson_too_large_error(exc):
            return None
        raise
    await append_global_changelog_entry(
        revisions,
        entity_type=entity_type,
        entity_id=entity_id,
        revision_doc_id=result.inserted_id,
        revision_entry=entry,
    )
    return str(result.inserted_id)


def build_section_revision_snapshot(
    *,
    content: dict | None = None,
    design: dict | None = None,
) -> dict:
    snapshot = {"schema_version": 2}
    if content is not None:
        snapshot["content"] = deepcopy(content)
    if design is not None:
        snapshot["design"] = deepcopy(design)
    return snapshot


def parse_section_revision_snapshot(data: Any) -> tuple[dict | None, dict | None]:
    """Parse section revision snapshots in schema v2 format."""
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


TICKER_DESIGN_TYPE_DATA_KEYS = frozenset(
    {
        "bg_color",
        "bg_color_link",
        "text_color",
        "text_color_link",
        "separator",
        "separator_image_url",
        "separator_image_responsive_variants",
        "speed",
        "font_size",
        "pin_to_header",
        "view_mode",
    }
)

TEXT_IMAGE_DESIGN_TYPE_DATA_KEYS = frozenset(
    {
        "image_layout",
        "image_layout_responsive",
        "image_align_x",
        "image_width_percent",
        "image_max_width_percent",
        "image_max_width_percent_responsive",
        "image_max_height_vh",
        "image_max_height_vh_responsive",
        "image_width_px",
        "image_min_width_px",
        "image_target_width_percent",
        "image_max_width_px",
        "image_height_px",
        "image_text_gap",
        "image_text_gap_responsive",
        "image_border_radius",
        "image_border_radius_responsive",
        "image_bg_opacity",
        "image_aspect_ratio",
        "image_aspect_ratio_responsive",
        "image_interaction",
        "image_bg_zoom",
        "image_bg_focal_x",
        "image_bg_focal_y",
        "image_bg_rotation",
    }
)

GALLERY_DESIGN_TYPE_DATA_KEYS = frozenset(
    {
        "layout",
        "aspect_ratio",
        "orientation",
        "direction",
    }
)

TILES_DESIGN_TYPE_DATA_KEYS = frozenset(
    {
        "grid_mode",
        "rows",
        "columns",
        "tile_min_width",
        "tile_max_width",
        "aspect_ratio",
        "direction",
        "always_show_title",
        "checker_color1",
        "checker_color2",
        "checker_color1_link",
        "checker_color2_link",
        "title_gradient_color",
        "title_gradient_color_link",
        "artist_button_type",
        "tile_show_reset_button",
    }
)

PROGRAM_DESIGN_TYPE_DATA_KEYS = frozenset(
    {
        "max_visible_hours",
        "default_grouping",
        "fixed_stage_id",
        "fixed_day",
        "fixed_gig_id",
        "allow_group_toggle",
        "allow_day_selection",
        "allow_stage_filter",
        "date_selection_color",
        "date_selection_color_link",
        "stage_row_height",
        "show_view_toggle",
        "show_gig_description_button",
        "default_view_mode",
    }
)

VIDEO_DESIGN_TYPE_DATA_KEYS = frozenset(
    {
        "tv_color",
        "tv_color_link",
        "wrapper",
        "device_wrappers",
    }
)

FAQ_DESIGN_TYPE_DATA_KEYS = frozenset(
    {
        "question_color",
        "question_color_link",
        "answer_color",
        "answer_color_link",
        "separator_color",
        "separator_color_link",
        "group_title_color",
        "group_title_color_link",
        "group_title_color_variation",
    }
)

BLOG_DESIGN_TYPE_DATA_KEYS = frozenset(
    {
        "filter_enabled",
        "display_style",
        "two_column_non_cards",
        "target_route",
        "show_more_button_type",
        "item_bg_color",
        "item_bg_color_link",
        "title_color",
        "title_color_link",
        "desc_color",
        "desc_color_link",
        "meta_color",
        "meta_color_link",
        "separator_color",
        "separator_color_link",
        "show_separators",
        "slidable_on_mobile",
        "image_ratio",
    }
)

SECTION_TYPE_DATA_DESIGN_KEYS: dict[str, frozenset[str]] = {
    "ticker": TICKER_DESIGN_TYPE_DATA_KEYS,
    "text_image": TEXT_IMAGE_DESIGN_TYPE_DATA_KEYS,
    "gallery": GALLERY_DESIGN_TYPE_DATA_KEYS,
    "tiles": TILES_DESIGN_TYPE_DATA_KEYS,
    "program": PROGRAM_DESIGN_TYPE_DATA_KEYS,
    "video": VIDEO_DESIGN_TYPE_DATA_KEYS,
    "faq": FAQ_DESIGN_TYPE_DATA_KEYS,
    "blog": BLOG_DESIGN_TYPE_DATA_KEYS,
}
GENERIC_SECTION_TYPE_DATA_KEY = "section_generic"
DEFAULT_SECTION_CONTENT_EXCLUDE_KEYS = frozenset(
    {"_id", "revision_id", "created_at", "updated_at"}
)


def get_section_design_type_data_keys(section_type: str) -> frozenset[str]:
    if not isinstance(section_type, str):
        return frozenset()
    return SECTION_TYPE_DATA_DESIGN_KEYS.get(section_type, frozenset())


def extract_section_design_type_data(section_doc: dict) -> dict | None:
    """Extract design-only type_data keys for section-local design state."""
    section_type = str(section_doc.get("section_type") or "")
    design_keys = get_section_design_type_data_keys(section_type)

    type_data = section_doc.get("type_data")
    source = type_data if isinstance(type_data, dict) else {}
    if not design_keys and GENERIC_SECTION_TYPE_DATA_KEY not in source:
        return None

    # Keep a stable key set so explicit clears (null values) can be restored.
    snapshot = {key: deepcopy(source.get(key)) for key in sorted(design_keys)}
    if GENERIC_SECTION_TYPE_DATA_KEY in source:
        snapshot[GENERIC_SECTION_TYPE_DATA_KEY] = deepcopy(
            source.get(GENERIC_SECTION_TYPE_DATA_KEY)
        )
    return snapshot


def build_section_content_snapshot(
    section_doc: dict,
    *,
    exclude_keys: set[str] | frozenset[str] | None = None,
    shared_blog_content: dict | None = None,
    shared_faq_content: dict | None = None,
    shared_program_content: dict | None = None,
) -> dict:
    """Extract content-only snapshot from a section document."""
    section_doc_for_snapshot = _sanitize_program_section_doc_for_content_snapshot(section_doc)
    snapshot = snapshot_document(
        section_doc_for_snapshot,
        exclude_keys=exclude_keys or DEFAULT_SECTION_CONTENT_EXCLUDE_KEYS,
    )
    section_type = str(snapshot.get("section_type") or "")
    design_keys = get_section_design_type_data_keys(section_type)

    type_data = snapshot.get("type_data")
    if design_keys and isinstance(type_data, dict):
        snapshot["type_data"] = {
            key: deepcopy(value)
            for key, value in type_data.items()
            if key not in design_keys
        }

    if section_type == "blog" and isinstance(shared_blog_content, dict):
        snapshot["shared_blog_data"] = deepcopy(shared_blog_content)
    if section_type == "faq" and isinstance(shared_faq_content, dict):
        snapshot["shared_faq_data"] = deepcopy(shared_faq_content)
    if section_type == "program" and isinstance(shared_program_content, dict):
        snapshot["shared_program_data"] = sanitize_program_shared_content_for_revision(
            shared_program_content
        )

    return snapshot


def _safe_float_for_snapshot(value: Any, default: float) -> float:
    try:
        parsed = float(value)
        if parsed != parsed:
            return default
        return parsed
    except Exception:
        return default


def _normalize_bilingual_value(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"de": "", "en": ""}
    return {
        "de": str(value.get("de") or ""),
        "en": str(value.get("en") or ""),
    }


def _normalize_blog_media_variants_for_snapshot(source: Any) -> list[dict[str, Any]]:
    if not isinstance(source, dict):
        return []
    candidates: list[Any] = [
        source.get("image_responsive_variants"),
        source.get("responsive_variants"),
        source.get("imageResponsiveVariants"),
        source.get("responsiveVariants"),
        source.get("variants"),
    ]
    image_payload = source.get("image")
    if isinstance(image_payload, dict):
        candidates.extend(
            [
                image_payload.get("image_responsive_variants"),
                image_payload.get("responsive_variants"),
                image_payload.get("imageResponsiveVariants"),
                image_payload.get("responsiveVariants"),
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


def normalize_blog_shared_content_snapshot(shared_content: Any) -> dict:
    source = shared_content if isinstance(shared_content, dict) else {}
    normalized_items: list[dict[str, Any]] = []
    raw_items = source.get("items")
    if isinstance(raw_items, list):
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            normalized_items.append(
                {
                    "id": str(raw_item.get("id") or ""),
                    "image_url": str(raw_item.get("image_url") or ""),
                    "image_responsive_variants": _normalize_blog_media_variants_for_snapshot(raw_item),
                    "image_zoom": _safe_float_for_snapshot(raw_item.get("image_zoom"), 1.0),
                    "image_focal_x": _safe_float_for_snapshot(raw_item.get("image_focal_x"), 50.0),
                    "image_focal_y": _safe_float_for_snapshot(raw_item.get("image_focal_y"), 50.0),
                    "image_rotation": _safe_float_for_snapshot(raw_item.get("image_rotation"), 0.0),
                    "date": str(raw_item.get("date") or ""),
                    "tag": _normalize_bilingual_value(raw_item.get("tag")),
                    "title": _normalize_bilingual_value(raw_item.get("title")),
                    "text": _normalize_bilingual_value(raw_item.get("text")),
                    "page_slug": str(raw_item.get("page_slug") or ""),
                }
            )

    normalized_tags: list[dict[str, str]] = []
    raw_tags = source.get("tags")
    if isinstance(raw_tags, list):
        for raw_tag in raw_tags:
            if not isinstance(raw_tag, dict):
                continue
            normalized_tags.append(_normalize_bilingual_value(raw_tag))

    return {
        "items": normalized_items,
        "tags": normalized_tags,
    }


async def capture_blog_shared_content(db) -> dict:
    """Capture shared blog data (items + tags) for revision snapshots."""
    items_coll = db[BLOG_SHARED_COLLECTION]
    config_coll = db[BLOG_CONFIG_COLLECTION]
    items: list[dict[str, Any]] = []

    async for doc in items_coll.find({}).sort([("date", -1), ("_id", -1)]):
        oid = doc.get("_id")
        items.append(
            {
                "id": str(oid) if oid is not None else "",
                "image_url": doc.get("image_url", ""),
                "image_responsive_variants": _normalize_blog_media_variants_for_snapshot(doc),
                "image_zoom": _safe_float_for_snapshot(doc.get("image_zoom"), 1.0),
                "image_focal_x": _safe_float_for_snapshot(doc.get("image_focal_x"), 50.0),
                "image_focal_y": _safe_float_for_snapshot(doc.get("image_focal_y"), 50.0),
                "image_rotation": _safe_float_for_snapshot(doc.get("image_rotation"), 0.0),
                "date": doc.get("date", ""),
                "tag": _normalize_bilingual_value(doc.get("tag")),
                "title": _normalize_bilingual_value(doc.get("title")),
                "text": _normalize_bilingual_value(doc.get("text")),
                "page_slug": doc.get("page_slug", ""),
            }
        )

    config_doc = await config_coll.find_one({"_id": "config"})
    return normalize_blog_shared_content_snapshot(
        {
            "items": items,
            "tags": config_doc.get("tags", []) if isinstance(config_doc, dict) else [],
        }
    )


async def apply_blog_shared_content(db, shared_content: Any) -> bool:
    """Restore shared blog data from a snapshot."""
    normalized = normalize_blog_shared_content_snapshot(shared_content)
    current = await capture_blog_shared_content(db)
    if snapshots_equal(current, normalized):
        return False

    items_coll = db[BLOG_SHARED_COLLECTION]
    config_coll = db[BLOG_CONFIG_COLLECTION]
    now = datetime.utcnow()
    item_docs: list[dict[str, Any]] = []
    seen_ids: set[ObjectId] = set()

    for raw_item in normalized.get("items", []):
        if not isinstance(raw_item, dict):
            continue
        item_doc: dict[str, Any] = {
            "image_url": str(raw_item.get("image_url") or ""),
            "image_responsive_variants": _normalize_blog_media_variants_for_snapshot(raw_item),
            "image_zoom": _safe_float_for_snapshot(raw_item.get("image_zoom"), 1.0),
            "image_focal_x": _safe_float_for_snapshot(raw_item.get("image_focal_x"), 50.0),
            "image_focal_y": _safe_float_for_snapshot(raw_item.get("image_focal_y"), 50.0),
            "image_rotation": _safe_float_for_snapshot(raw_item.get("image_rotation"), 0.0),
            "date": str(raw_item.get("date") or ""),
            "tag": _normalize_bilingual_value(raw_item.get("tag")),
            "title": _normalize_bilingual_value(raw_item.get("title")),
            "text": _normalize_bilingual_value(raw_item.get("text")),
            "page_slug": str(raw_item.get("page_slug") or ""),
            "created_at": now,
            "updated_at": now,
        }
        item_id = as_object_id(raw_item.get("id"))
        if item_id is not None and item_id not in seen_ids:
            item_doc["_id"] = item_id
            seen_ids.add(item_id)
        item_docs.append(item_doc)

    await items_coll.delete_many({})
    if item_docs:
        await items_coll.insert_many(item_docs)

    await config_coll.update_one(
        {"_id": "config"},
        {"$set": {"tags": deepcopy(normalized.get("tags", []))}},
        upsert=True,
    )
    return True


async def push_blog_shared_content_revisions(
    db,
    *,
    saved_by: str | None,
    max_history: int = REVISION_HISTORY_LIMIT,
    exclude_section_ids: set[str] | frozenset[str] | None = None,
) -> int:
    """Push current shared blog content snapshot into section revision history."""
    sections = db["sections"]
    revisions = db[REVISIONS_COLLECTION]
    excluded = {str(value) for value in (exclude_section_ids or set()) if str(value)}

    revision_config = await get_or_create_revision_config(db)
    section_options = get_section_revision_options(
        revision_config,
        "blog",
    )
    if not (
        section_revision_history_enabled(section_options)
        and bool(section_options.get("include_content"))
    ):
        return 0

    shared_blog_content = await capture_blog_shared_content(db)
    pushed_count = 0
    async for section_doc in sections.find({"section_type": "blog"}):
        section_id = str(section_doc.get("_id") or "")
        if not section_id or section_id in excluded:
            continue

        content_snapshot = build_section_content_snapshot(
            section_doc,
            shared_blog_content=shared_blog_content,
        )
        current_data = build_section_revision_snapshot(
            content=content_snapshot,
            design=None,
        )
        revision_id = section_doc.get("revision_id")
        new_revision_id = await push_revision_entry(
            revisions,
            entity_type="section",
            entity_id=section_id,
            current_data=current_data,
            revision_id=as_object_id(revision_id),
            saved_by=saved_by,
            change_kind="content",
            max_history=max_history,
        )
        if new_revision_id and new_revision_id != revision_id:
            await sections.update_one(
                {"_id": section_doc.get("_id")},
                {"$set": {"revision_id": new_revision_id}},
            )
        pushed_count += 1

    return pushed_count


def _normalize_faq_shared_item(raw_item: Any, index: int) -> dict[str, Any]:
    if isinstance(raw_item, BaseModel):
        source = raw_item.model_dump()
    elif isinstance(raw_item, dict):
        source = raw_item
    else:
        source = {}

    try:
        normalized = FAQSharedItem.model_validate(source).model_dump()
    except Exception:
        normalized = FAQSharedItem().model_dump()

    item_id = str(normalized.get("id") or source.get("id") or f"faq-{index + 1}").strip()
    normalized["id"] = item_id or f"faq-{index + 1}"
    normalized["question"] = _normalize_bilingual_value(normalized.get("question"))
    normalized["answer"] = _normalize_bilingual_value(normalized.get("answer"))
    normalized["tag"] = _normalize_bilingual_value(normalized.get("tag"))
    normalized["start_date"] = str(normalized.get("start_date") or "")
    normalized["end_date"] = str(normalized.get("end_date") or "")
    normalized.pop("created_at", None)
    normalized.pop("updated_at", None)
    return normalized


def normalize_faq_shared_content_snapshot(shared_content: Any) -> dict:
    source = shared_content if isinstance(shared_content, dict) else {}
    normalized_items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    raw_items = source.get("items")
    if isinstance(raw_items, list):
        for index, raw_item in enumerate(raw_items):
            normalized_item = _normalize_faq_shared_item(raw_item, index)
            item_id = str(normalized_item.get("id") or "").strip()
            if not item_id or item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            normalized_items.append(normalized_item)

    normalized_tags: list[dict[str, str]] = []
    raw_tags = source.get("tags")
    if isinstance(raw_tags, list):
        for raw_tag in raw_tags:
            if not isinstance(raw_tag, dict):
                continue
            normalized_tags.append(_normalize_bilingual_value(raw_tag))

    return {
        "items": normalized_items,
        "tags": normalized_tags,
    }


def _faq_shared_snapshot_has_data(snapshot: dict | None) -> bool:
    if not isinstance(snapshot, dict):
        return False
    return bool(snapshot.get("items") or snapshot.get("tags"))


def _faq_shared_exact_dedup_key(item: dict[str, Any]) -> tuple[str, str, str, str, str, str, str, str]:
    question = _normalize_bilingual_value(item.get("question"))
    answer = _normalize_bilingual_value(item.get("answer"))
    tag = _normalize_bilingual_value(item.get("tag"))
    return (
        question["de"],
        question["en"],
        answer["de"],
        answer["en"],
        tag["de"],
        tag["en"],
        str(item.get("start_date") or ""),
        str(item.get("end_date") or ""),
    )


async def _derive_faq_shared_content_from_sections(db) -> dict:
    sections = db["sections"]
    merged_items: list[dict[str, Any]] = []
    seen_exact_payloads: set[tuple[str, str, str, str, str, str, str, str]] = set()
    seen_item_ids: set[str] = set()
    seen_tag_keys: set[tuple[str, str]] = set()
    merged_tags: list[dict[str, str]] = []

    async for section_doc in sections.find({"section_type": "faq"}):
        type_data = section_doc.get("type_data") if isinstance(section_doc.get("type_data"), dict) else {}
        raw_faqs = type_data.get("faqs")
        if not isinstance(raw_faqs, list):
            continue
        for index, raw_item in enumerate(raw_faqs):
            normalized_item = _normalize_faq_shared_item(raw_item, index)
            dedup_key = _faq_shared_exact_dedup_key(normalized_item)
            if dedup_key in seen_exact_payloads:
                continue
            seen_exact_payloads.add(dedup_key)
            base_id = str(normalized_item.get("id") or "").strip() or f"faq-{len(merged_items) + 1}"
            item_id = base_id
            if item_id in seen_item_ids:
                item_id = f"{base_id}-{len(merged_items) + 1}"
            seen_item_ids.add(item_id)
            normalized_item["id"] = item_id
            merged_items.append(normalized_item)

            tag_value = _normalize_bilingual_value(normalized_item.get("tag"))
            tag_key = (tag_value.get("de", ""), tag_value.get("en", ""))
            if tag_key not in seen_tag_keys and (tag_key[0] or tag_key[1]):
                seen_tag_keys.add(tag_key)
                merged_tags.append(tag_value)

    return normalize_faq_shared_content_snapshot(
        {
            "items": merged_items,
            "tags": merged_tags,
        }
    )


async def _ensure_faq_shared_content_initialized(db) -> dict:
    shared_coll = db[FAQ_SHARED_COLLECTION]
    existing_doc = await shared_coll.find_one({"_id": FAQ_SHARED_DOC_ID})
    existing_snapshot = normalize_faq_shared_content_snapshot(existing_doc or {})
    if _faq_shared_snapshot_has_data(existing_snapshot):
        return existing_snapshot

    migrated_snapshot = await _derive_faq_shared_content_from_sections(db)
    normalized_migrated = normalize_faq_shared_content_snapshot(migrated_snapshot)
    now = datetime.utcnow()
    await shared_coll.update_one(
        {"_id": FAQ_SHARED_DOC_ID},
        {
            "$set": {
                **deepcopy(normalized_migrated),
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )
    return normalized_migrated


async def capture_faq_shared_content(db) -> dict:
    """Capture shared FAQ data (items + tags) for revision snapshots."""
    return await _ensure_faq_shared_content_initialized(db)


async def apply_faq_shared_content(db, shared_content: Any) -> bool:
    """Restore shared FAQ data from a snapshot."""
    normalized = normalize_faq_shared_content_snapshot(shared_content)
    current = await capture_faq_shared_content(db)
    if snapshots_equal(current, normalized):
        return False

    shared_coll = db[FAQ_SHARED_COLLECTION]
    now = datetime.utcnow()
    await shared_coll.update_one(
        {"_id": FAQ_SHARED_DOC_ID},
        {
            "$set": {
                **deepcopy(normalized),
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )
    return True


async def push_faq_shared_content_revisions(
    db,
    *,
    saved_by: str | None,
    max_history: int = REVISION_HISTORY_LIMIT,
    exclude_section_ids: set[str] | frozenset[str] | None = None,
) -> int:
    """Push current shared FAQ content snapshot into section revision history."""
    sections = db["sections"]
    revisions = db[REVISIONS_COLLECTION]
    excluded = {str(value) for value in (exclude_section_ids or set()) if str(value)}

    revision_config = await get_or_create_revision_config(db)
    section_options = get_section_revision_options(
        revision_config,
        "faq",
    )
    if not (
        section_revision_history_enabled(section_options)
        and bool(section_options.get("include_content"))
    ):
        return 0

    shared_faq_content = await capture_faq_shared_content(db)
    pushed_count = 0
    async for section_doc in sections.find({"section_type": "faq"}):
        section_id = str(section_doc.get("_id") or "")
        if not section_id or section_id in excluded:
            continue

        content_snapshot = build_section_content_snapshot(
            section_doc,
            shared_faq_content=shared_faq_content,
        )
        current_data = build_section_revision_snapshot(
            content=content_snapshot,
            design=None,
        )
        revision_id = section_doc.get("revision_id")
        new_revision_id = await push_revision_entry(
            revisions,
            entity_type="section",
            entity_id=section_id,
            current_data=current_data,
            revision_id=as_object_id(revision_id),
            saved_by=saved_by,
            change_kind="content",
            max_history=max_history,
        )
        if new_revision_id and new_revision_id != revision_id:
            await sections.update_one(
                {"_id": section_doc.get("_id")},
                {"$set": {"revision_id": new_revision_id}},
            )
        pushed_count += 1

    return pushed_count


def normalize_program_shared_content_snapshot(shared_content: Any) -> dict:
    return program_catalog.normalize_program_shared_content_snapshot(shared_content)


def _sanitize_program_cache_state_for_revision(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: deepcopy(value[key])
        for key in sorted(PROGRAM_SHARED_REVISION_CACHE_STATE_KEYS)
        if key in value
    }


def sanitize_program_shared_content_for_revision(shared_content: Any) -> dict:
    source = shared_content if isinstance(shared_content, dict) else {}
    normalized = normalize_program_shared_content_snapshot(
        {
            "stages": source.get("stages"),
            "gig_ids": source.get("gig_ids"),
            "gigs": source.get("gigs"),
            "program_stages_integration_mapping": source.get(
                "program_stages_integration_mapping"
            ),
            "program_stages_integration_mapping_cache_state": {},
            "program_gigs_integration_mapping": source.get(
                "program_gigs_integration_mapping"
            ),
            "program_gigs_integration_mapping_cache_state": {},
        }
    )
    normalized["program_gigs_integration_mapping_cache_state"] = (
        _sanitize_program_cache_state_for_revision(
            source.get("program_gigs_integration_mapping_cache_state")
        )
    )
    normalized["program_stages_integration_mapping_cache_state"] = (
        _sanitize_program_cache_state_for_revision(
            source.get("program_stages_integration_mapping_cache_state")
        )
    )
    return normalized


async def capture_program_shared_content(db, **kwargs) -> dict:
    """Capture shared program data (gigs + stages) for revision snapshots."""
    return await program_catalog.capture_program_shared_content(db, **kwargs)


async def apply_program_shared_content(db, shared_content: Any) -> bool:
    """Restore shared program data from a snapshot."""
    return await program_catalog.apply_program_shared_content(db, shared_content)


async def push_program_shared_content_revisions(
    db,
    *,
    saved_by: str | None,
    max_history: int = REVISION_HISTORY_LIMIT,
    exclude_section_ids: set[str] | frozenset[str] | None = None,
) -> int:
    """Push current shared program content snapshot into section revision history."""
    sections = db["sections"]
    revisions = db[REVISIONS_COLLECTION]
    excluded = {str(value) for value in (exclude_section_ids or set()) if str(value)}

    revision_config = await get_or_create_revision_config(db)
    section_options = get_section_revision_options(
        revision_config,
        "program",
    )
    if not (
        section_revision_history_enabled(section_options)
        and bool(section_options.get("include_content"))
    ):
        return 0

    shared_program_content = sanitize_program_shared_content_for_revision(
        await capture_program_shared_content(db)
    )
    pushed_count = 0
    async for section_doc in sections.find({"section_type": "program"}):
        section_id = str(section_doc.get("_id") or "")
        if not section_id or section_id in excluded:
            continue

        content_snapshot = build_section_content_snapshot(
            section_doc,
            shared_program_content=shared_program_content,
        )
        current_data = build_section_revision_snapshot(
            content=content_snapshot,
            design=None,
        )
        revision_id = section_doc.get("revision_id")
        new_revision_id = await push_revision_entry(
            revisions,
            entity_type="section",
            entity_id=section_id,
            current_data=current_data,
            revision_id=as_object_id(revision_id),
            saved_by=saved_by,
            change_kind="content",
            max_history=max_history,
        )
        if new_revision_id and new_revision_id != revision_id:
            await sections.update_one(
                {"_id": section_doc.get("_id")},
                {"$set": {"revision_id": new_revision_id}},
            )
        pushed_count += 1

    return pushed_count


_DIFF_PREFIX_IGNORE_KEYS = {
    "type_data",
    "section_type_data",
    "design_overrides",
    "content",
    "design",
    "shared_faq_data",
    "shared_blog_data",
    "shared_program_data",
}
_LIST_IDENTIFIER_KEYS = ("id", "_id", "key", "slug")
_OVERRIDE_DIFF_ROOT_KEYS = frozenset({"page_overrides", "design_overrides"})
_GENERIC_DIFF_ROOT = ("section_type_data", "section_generic")


def _snake_to_camel_key(value: str) -> str:
    source = str(value or "")
    if "_" not in source:
        return source
    head, *tail = source.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail if part)


def _normalize_param_name(path_parts: list[str]) -> str:
    parts = [str(part) for part in path_parts if str(part)]
    while parts and parts[0] in _DIFF_PREFIX_IGNORE_KEYS:
        parts = parts[1:]
    if not parts:
        return "value"
    return _snake_to_camel_key(parts[0])


def _scalar_identifier(value: Any) -> str | None:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return None


def _extract_named_identifier(item: Any, index: int) -> str:
    if isinstance(item, dict):
        for key in _LIST_IDENTIFIER_KEYS:
            identifier = _scalar_identifier(item.get(key))
            if identifier:
                return identifier

        for key in ("name", "title", "label"):
            value = item.get(key)
            if isinstance(value, dict):
                for locale_key in ("id", "slug", "de", "en"):
                    identifier = _scalar_identifier(value.get(locale_key))
                    if identifier:
                        return identifier
            identifier = _scalar_identifier(value)
            if identifier:
                return identifier

    return f"#{index + 1}"


def _extract_strict_list_id(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in _LIST_IDENTIFIER_KEYS:
        identifier = _scalar_identifier(item.get(key))
        if identifier:
            return identifier
    return None


def _append_diff_label(labels: list[str], seen: set[str], label: str) -> None:
    cleaned = str(label or "").strip()
    if not cleaned or cleaned in seen:
        return
    seen.add(cleaned)
    labels.append(cleaned)


def _format_context_param_label(context: str, parameter: str | None = None) -> str:
    context_name = str(context or "").strip() or "Change"
    parameter_name = str(parameter or "").strip() or "value"
    return f"{context_name}: {parameter_name}"


def _override_param_index(path_parts: list[str]) -> int | None:
    if not path_parts:
        return None
    root = str(path_parts[0] or "")
    if root == "page_overrides":
        # page_overrides.<slug>.<param>
        return 2
    if root == "design_overrides":
        # design_overrides.<param>
        return 1
    return None


def _format_override_diff_label(path_parts: list[str]) -> str:
    index = _override_param_index(path_parts)
    if index is None or len(path_parts) <= index:
        return _format_context_param_label("Override")
    param_name = _snake_to_camel_key(str(path_parts[index] or "").strip())
    if not param_name:
        return _format_context_param_label("Override")
    return _format_context_param_label("Override", param_name)


def _is_generic_diff_path(path_parts: list[str]) -> bool:
    if len(path_parts) < 2:
        return False
    return (
        str(path_parts[0] or "") == _GENERIC_DIFF_ROOT[0]
        and str(path_parts[1] or "") == _GENERIC_DIFF_ROOT[1]
    )


def _format_generic_diff_label(path_parts: list[str]) -> str:
    if len(path_parts) <= 2:
        return _format_context_param_label("Generic")
    param_name = _snake_to_camel_key(str(path_parts[2] or "").strip())
    if not param_name:
        return _format_context_param_label("Generic")
    return _format_context_param_label("Generic", param_name)


def _is_type_specific_diff_path(path_parts: list[str]) -> bool:
    if not path_parts:
        return False
    if str(path_parts[0] or "") != "section_type_data":
        return False
    return not _is_generic_diff_path(path_parts)


def _format_type_specific_diff_label(path_parts: list[str]) -> str:
    if len(path_parts) <= 1:
        return _format_context_param_label("Type specific")
    param_name = _snake_to_camel_key(str(path_parts[1] or "").strip())
    if not param_name:
        return _format_context_param_label("Type specific")
    return _format_context_param_label("Type specific", param_name)


def _append_list_diff_labels(
    labels: list[str],
    seen: set[str],
    path_parts: list[str],
    before_list: list[Any],
    after_list: list[Any],
) -> None:
    list_name = _normalize_param_name(path_parts)

    before_ids = [_extract_strict_list_id(item) for item in before_list]
    after_ids = [_extract_strict_list_id(item) for item in after_list]
    before_has_ids = all(identifier is not None for identifier in before_ids)
    after_has_ids = all(identifier is not None for identifier in after_ids)

    if before_has_ids and after_has_ids:
        before_map = {identifier: item for identifier, item in zip(before_ids, before_list)}
        after_map = {identifier: item for identifier, item in zip(after_ids, after_list)}
        if len(before_map) == len(before_list) and len(after_map) == len(after_list):
            before_key_set = set(before_map.keys())
            after_key_set = set(after_map.keys())

            for identifier in sorted(before_key_set - after_key_set):
                _append_diff_label(labels, seen, f"{list_name}[{identifier}] removed")
            for identifier in sorted(after_key_set - before_key_set):
                _append_diff_label(labels, seen, f"{list_name}[{identifier}] added")
            for identifier in sorted(before_key_set & after_key_set):
                if not snapshots_equal(before_map[identifier], after_map[identifier]):
                    _append_diff_label(labels, seen, f"{list_name}[{identifier}] updated")
            return

    max_len = max(len(before_list), len(after_list))
    for idx in range(max_len):
        if idx >= len(before_list):
            identifier = _extract_named_identifier(after_list[idx], idx)
            _append_diff_label(labels, seen, f"{list_name}[{identifier}] added")
            continue
        if idx >= len(after_list):
            identifier = _extract_named_identifier(before_list[idx], idx)
            _append_diff_label(labels, seen, f"{list_name}[{identifier}] removed")
            continue
        if snapshots_equal(before_list[idx], after_list[idx]):
            continue
        identifier = _extract_named_identifier(after_list[idx], idx)
        _append_diff_label(labels, seen, f"{list_name}[{identifier}] updated")


def _collect_param_diff_labels(
    labels: list[str],
    seen: set[str],
    before: Any,
    after: Any,
    path_parts: list[str],
) -> None:
    if snapshots_equal(before, after):
        return

    path = [str(part) for part in path_parts if str(part)]
    if path and str(path[0]) in _OVERRIDE_DIFF_ROOT_KEYS:
        param_index = _override_param_index(path)
        if param_index is not None and len(path) <= param_index:
            before_map = before if isinstance(before, dict) else {}
            after_map = after if isinstance(after, dict) else {}
            if before_map or after_map:
                for key in sorted(set(before_map.keys()) | set(after_map.keys())):
                    _collect_param_diff_labels(
                        labels,
                        seen,
                        before_map.get(key),
                        after_map.get(key),
                        [*path, str(key)],
                    )
                return
            _append_diff_label(labels, seen, _format_context_param_label("Override"))
            return

        _append_diff_label(labels, seen, _format_override_diff_label(path))
        return

    if _is_generic_diff_path(path):
        if len(path) <= 2:
            before_map = before if isinstance(before, dict) else {}
            after_map = after if isinstance(after, dict) else {}
            if before_map or after_map:
                for key in sorted(set(before_map.keys()) | set(after_map.keys())):
                    _collect_param_diff_labels(
                        labels,
                        seen,
                        before_map.get(key),
                        after_map.get(key),
                        [*path, str(key)],
                    )
                return
            _append_diff_label(labels, seen, _format_context_param_label("Generic"))
            return

        _append_diff_label(labels, seen, _format_generic_diff_label(path))
        return

    if _is_type_specific_diff_path(path):
        if len(path) <= 1:
            before_map = before if isinstance(before, dict) else {}
            after_map = after if isinstance(after, dict) else {}
            if before_map or after_map:
                for key in sorted(set(before_map.keys()) | set(after_map.keys())):
                    _collect_param_diff_labels(
                        labels,
                        seen,
                        before_map.get(key),
                        after_map.get(key),
                        [*path, str(key)],
                    )
                return
            _append_diff_label(
                labels,
                seen,
                _format_context_param_label("Type specific"),
            )
            return

        _append_diff_label(labels, seen, _format_type_specific_diff_label(path))
        return

    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before.keys()) | set(after.keys())):
            _collect_param_diff_labels(
                labels,
                seen,
                before.get(key),
                after.get(key),
                [*path_parts, str(key)],
            )
        return

    if isinstance(before, list) and isinstance(after, list):
        _append_list_diff_labels(labels, seen, path_parts, before, after)
        return

    _append_diff_label(labels, seen, _normalize_param_name(path_parts))


def compute_param_diffs(previous_snapshot: Any, current_snapshot: Any) -> list[str]:
    """Compute human-readable changed parameter labels between snapshots."""
    if not isinstance(previous_snapshot, dict) and not isinstance(current_snapshot, dict):
        return []

    left = previous_snapshot if isinstance(previous_snapshot, dict) else {}
    right = current_snapshot if isinstance(current_snapshot, dict) else {}
    labels: list[str] = []
    seen: set[str] = set()
    _collect_param_diff_labels(labels, seen, left, right, [])
    return labels


def _infer_fallback_param_name(previous_snapshot: Any, current_snapshot: Any) -> str | None:
    for snapshot in (previous_snapshot, current_snapshot):
        if not isinstance(snapshot, dict):
            continue
        for key in sorted(snapshot.keys()):
            name = _normalize_param_name([str(key)])
            if name and name != "value":
                return name
    return None


def compute_revision_param_diffs(
    previous_snapshot: Any,
    current_snapshot: Any,
    *,
    reverted_from_saved_at: Any = None,
    fallback_context: str | None = None,
) -> list[str]:
    reverted_label = normalize_saved_at_label(reverted_from_saved_at)
    if reverted_label:
        return [f"Reverted: {reverted_label}"]
    labels = compute_param_diffs(previous_snapshot, current_snapshot)
    if labels:
        return labels
    if snapshots_equal(previous_snapshot, current_snapshot):
        return []
    fallback_param = _infer_fallback_param_name(previous_snapshot, current_snapshot)
    if fallback_context:
        return [_format_context_param_label(fallback_context, fallback_param)]
    return [_format_context_param_label("Change", fallback_param)]


def sanitize_revision_snapshot(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {k: sanitize_revision_snapshot(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_revision_snapshot(item) for item in value]
    return deepcopy(value)


def normalize_revision_change_kind(
    raw_kind: str | None,
    *,
    has_content: bool,
    has_design: bool,
) -> str | None:
    if raw_kind in {"content", "design", "both"}:
        return raw_kind
    if has_content and has_design:
        return "both"
    if has_design:
        return "design"
    if has_content:
        return "content"
    return None


def build_revision_entry_meta(
    entry: dict | None,
    *,
    parse_snapshot: Callable[[Any], tuple[dict | None, dict | None]],
    sanitize_snapshot: Callable[[Any], Any] = sanitize_revision_snapshot,
) -> dict[str, Any]:
    if not isinstance(entry, dict):
        return {
            "saved_at": None,
            "saved_by": "unknown",
            "has_content": False,
            "has_design": False,
            "content_snapshot": None,
            "design_snapshot": None,
            "content_changed": False,
            "design_changed": False,
            "change_kind": None,
        }

    content, design = parse_snapshot(entry.get("data"))
    has_content = isinstance(content, dict)
    has_design = isinstance(design, dict)
    change_kind = normalize_revision_change_kind(
        entry.get("change_kind"),
        has_content=has_content,
        has_design=has_design,
    )
    return {
        "saved_at": entry.get("saved_at"),
        "saved_by": entry.get("saved_by") or "unknown",
        "has_content": has_content,
        "has_design": has_design,
        "content_snapshot": (
            sanitize_snapshot(content) if has_content else None
        ),
        "design_snapshot": (
            sanitize_snapshot(design) if has_design else None
        ),
        "content_changed": change_kind in {"content", "both"},
        "design_changed": change_kind in {"design", "both"},
        "change_kind": change_kind,
    }


def resolve_effective_change_kind(
    *,
    current_data: Any,
    next_data: Any,
    parse_snapshot: Callable[[Any], tuple[dict | None, dict | None]],
    requested_kind: str | None = None,
) -> str | None:
    current_content, current_design = parse_snapshot(current_data)
    next_content, next_design = parse_snapshot(next_data)

    content_changed = (
        isinstance(current_content, dict)
        and isinstance(next_content, dict)
        and not snapshots_equal(current_content, next_content)
    )
    design_changed = (
        isinstance(current_design, dict)
        and isinstance(next_design, dict)
        and not snapshots_equal(current_design, next_design)
    )

    if content_changed and design_changed:
        return "both"
    if design_changed:
        return "design"
    if content_changed:
        return "content"
    if requested_kind in {"content", "design", "both"}:
        return requested_kind
    return None


def has_split_revision_streams(revision_doc: dict | None) -> bool:
    if not isinstance(revision_doc, dict):
        return False
    return bool(
        revision_doc.get("content_history")
        or revision_doc.get("design_history")
        or revision_doc.get("content_future")
        or revision_doc.get("design_future")
    )


def _as_revision_entries(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _revision_saved_at_timestamp(entry: dict) -> float:
    value = entry.get("saved_at")
    if isinstance(value, datetime):
        return value.timestamp()
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.timestamp()
    except Exception:
        return 0.0


def sort_revision_entries_newest(entries: list[dict]) -> list[dict]:
    return sorted(entries, key=_revision_saved_at_timestamp, reverse=True)


def _stream_entries_to_meta(
    raw_entries: list[dict],
    *,
    kind: str,
    current_snapshot: dict | None,
    parse_snapshot: Callable[[Any], tuple[dict | None, dict | None]],
    max_history: int,
    sanitize_snapshot: Callable[[Any], Any],
    assign_current_diffs: bool = False,
) -> tuple[list[dict], list[str]]:
    reversed_entries = list(reversed(raw_entries))
    reversed_entries = reversed_entries[:max_history]

    reference_snapshot = deepcopy(current_snapshot) if isinstance(current_snapshot, dict) else None
    reference_meta: dict | None = None
    current_diffs: list[str] = []
    out: list[dict] = []

    for entry in reversed_entries:
        meta = build_revision_entry_meta(
            entry,
            parse_snapshot=parse_snapshot,
            sanitize_snapshot=sanitize_snapshot,
        )
        if meta.get("change_kind") not in {kind, "both"}:
            continue

        entry_content, entry_design = parse_snapshot(entry.get("data"))
        snapshot = (
            entry_content
            if kind == "content"
            else entry_design
        )
        if not isinstance(snapshot, dict):
            continue

        param_diffs = compute_revision_param_diffs(
            snapshot,
            reference_snapshot,
            reverted_from_saved_at=entry.get("reverted_from_saved_at"),
            fallback_context="Content" if kind == "content" else "Design",
        )
        if reference_meta is None:
            if assign_current_diffs:
                current_diffs = param_diffs
        else:
            reference_meta["param_diffs"] = param_diffs
            reference_meta["content_param_diffs"] = (
                param_diffs if kind == "content" else []
            )
            reference_meta["design_param_diffs"] = (
                param_diffs if kind == "design" else []
            )

        meta["param_diffs"] = []
        meta["content_param_diffs"] = []
        meta["design_param_diffs"] = []
        reference_snapshot = deepcopy(snapshot)
        reference_meta = meta
        out.append(meta)

    if out and not out[0].get("param_diffs") and current_diffs:
        out[0]["param_diffs"] = list(current_diffs)
        out[0]["content_param_diffs"] = (
            list(current_diffs) if kind == "content" else []
        )
        out[0]["design_param_diffs"] = (
            list(current_diffs) if kind == "design" else []
        )

    return out, current_diffs


def _mark_stream_init_state(entries: list[dict], kind: str) -> None:
    if not entries:
        return

    oldest = entries[-1]
    scoped_key = "content_param_diffs" if kind == "content" else "design_param_diffs"
    scoped_diffs = oldest.get(scoped_key)
    if isinstance(scoped_diffs, list) and scoped_diffs:
        return

    oldest[scoped_key] = ["init state"]
    oldest["param_diffs"] = ["init state"]


def _resolve_kind_current_meta(
    *,
    revision_doc: dict | None,
    kind: str,
    entity_updated_at: datetime | None,
    parse_snapshot: Callable[[Any], tuple[dict | None, dict | None]],
) -> tuple[datetime | None, str]:
    if not isinstance(revision_doc, dict):
        return entity_updated_at, "unknown"

    kind_saved_at = revision_doc.get(f"{kind}_last_saved_at")
    kind_saved_by = revision_doc.get(f"{kind}_last_saved_by") or "unknown"
    if kind_saved_at is None:
        stream = _as_revision_entries(revision_doc.get(f"{kind}_history"))
        if stream:
            last_entry = stream[-1]
            kind_saved_at = last_entry.get("saved_at")
            kind_saved_by = last_entry.get("saved_by") or kind_saved_by
    return kind_saved_at, kind_saved_by


def build_revision_history_payload(
    *,
    revision_doc: dict | None,
    current_data: Any,
    entity_updated_at: datetime | None,
    parse_snapshot: Callable[[Any], tuple[dict | None, dict | None]],
    max_history: int = REVISION_HISTORY_LIMIT,
    sanitize_snapshot: Callable[[Any], Any] = sanitize_revision_snapshot,
) -> dict[str, Any]:
    revision_data = revision_doc if isinstance(revision_doc, dict) else {}
    content_history_raw = _as_revision_entries(revision_data.get("content_history"))
    design_history_raw = _as_revision_entries(revision_data.get("design_history"))
    content_future_raw = _as_revision_entries(revision_data.get("content_future"))
    design_future_raw = _as_revision_entries(revision_data.get("design_future"))

    current_content, current_design = parse_snapshot(current_data)
    current_content_saved_at, current_content_saved_by = _resolve_kind_current_meta(
        revision_doc=revision_doc,
        kind="content",
        entity_updated_at=entity_updated_at,
        parse_snapshot=parse_snapshot,
    )
    current_design_saved_at, current_design_saved_by = _resolve_kind_current_meta(
        revision_doc=revision_doc,
        kind="design",
        entity_updated_at=entity_updated_at,
        parse_snapshot=parse_snapshot,
    )

    current_meta = {
        "saved_at": revision_data.get("last_saved_at") or entity_updated_at,
        "saved_by": revision_data.get("last_saved_by") or "unknown",
        "content_saved_at": current_content_saved_at,
        "content_saved_by": current_content_saved_by,
        "design_saved_at": current_design_saved_at,
        "design_saved_by": current_design_saved_by,
        "has_content": isinstance(current_content, dict),
        "has_design": isinstance(current_design, dict),
        "content_snapshot": (
            sanitize_snapshot(current_content) if isinstance(current_content, dict) else None
        ),
        "design_snapshot": (
            sanitize_snapshot(current_design) if isinstance(current_design, dict) else None
        ),
        "content_changed": False,
        "design_changed": False,
        "change_kind": None,
        "param_diffs": [],
        "content_param_diffs": [],
        "design_param_diffs": [],
    }

    content_history, current_content_param_diffs = _stream_entries_to_meta(
        content_history_raw,
        kind="content",
        current_snapshot=current_content if isinstance(current_content, dict) else None,
        parse_snapshot=parse_snapshot,
        max_history=max_history,
        sanitize_snapshot=sanitize_snapshot,
        assign_current_diffs=True,
    )
    design_history, current_design_param_diffs = _stream_entries_to_meta(
        design_history_raw,
        kind="design",
        current_snapshot=current_design if isinstance(current_design, dict) else None,
        parse_snapshot=parse_snapshot,
        max_history=max_history,
        sanitize_snapshot=sanitize_snapshot,
        assign_current_diffs=True,
    )
    content_future, _ = _stream_entries_to_meta(
        content_future_raw,
        kind="content",
        current_snapshot=current_content if isinstance(current_content, dict) else None,
        parse_snapshot=parse_snapshot,
        max_history=max_history,
        sanitize_snapshot=sanitize_snapshot,
    )
    design_future, _ = _stream_entries_to_meta(
        design_future_raw,
        kind="design",
        current_snapshot=current_design if isinstance(current_design, dict) else None,
        parse_snapshot=parse_snapshot,
        max_history=max_history,
        sanitize_snapshot=sanitize_snapshot,
    )

    current_meta["content_param_diffs"] = current_content_param_diffs
    current_meta["design_param_diffs"] = current_design_param_diffs
    current_meta["param_diffs"] = list(
        dict.fromkeys([*current_content_param_diffs, *current_design_param_diffs])
    )

    _mark_stream_init_state(content_history, "content")
    _mark_stream_init_state(design_history, "design")

    if not current_content_param_diffs and not content_history and not content_future:
        current_meta["content_param_diffs"] = ["init state"]
    if not current_design_param_diffs and not design_history and not design_future:
        current_meta["design_param_diffs"] = ["init state"]
    current_meta["param_diffs"] = list(
        dict.fromkeys(
            [
                *current_meta["content_param_diffs"],
                *current_meta["design_param_diffs"],
            ]
        )
    )

    return {
        "current": current_meta,
        "history": sort_revision_entries_newest([*content_history, *design_history]),
        "future": sort_revision_entries_newest([*content_future, *design_future]),
    }


async def capture_section_design_state(
    db,
    section_id: str,
    *,
    section_doc: dict | None = None,
) -> dict:
    """Capture full section design state (page overrides + section-local design type_data)."""
    pages = db["pages"]
    sections = db["sections"]
    overrides_by_slug: dict[str, Any] = {}

    async for page in pages.find(
        {"sections.section_id": section_id},
        {"slug": 1, "sections": 1},
    ):
        slug = page.get("slug")
        if not slug:
            continue

        override_value = None
        for section_ref in page.get("sections", []):
            if section_ref.get("section_id") != section_id:
                continue
            if section_ref.get("design_overrides") is not None:
                override_value = deepcopy(section_ref.get("design_overrides"))
            break

        overrides_by_slug[slug] = override_value

    if not isinstance(section_doc, dict):
        section_oid = as_object_id(section_id)
        section_doc = (
            await sections.find_one(
                {"_id": section_oid},
                {"section_type": 1, "type_data": 1},
            )
            if section_oid is not None
            else None
        )

    snapshot: dict[str, Any] = {"page_overrides": overrides_by_slug}
    if isinstance(section_doc, dict):
        snapshot["design_overrides"] = deepcopy(section_doc.get("design_overrides"))
        section_type_data = extract_section_design_type_data(section_doc)
        if section_type_data is not None:
            snapshot["section_type_data"] = section_type_data

    return snapshot


async def apply_section_design_state(db, section_id: str, design_state: dict | None) -> int:
    """Restore per-page design overrides for a section."""
    if not isinstance(design_state, dict):
        return 0

    raw_map = design_state.get("page_overrides", {})
    overrides_by_slug = raw_map if isinstance(raw_map, dict) else {}

    pages = db["pages"]
    sections = db["sections"]
    updated_pages = 0

    async for page in pages.find(
        {"sections.section_id": section_id},
        {"slug": 1, "sections": 1},
    ):
        slug = page.get("slug")
        if not slug:
            continue

        target_override = (
            deepcopy(overrides_by_slug[slug]) if slug in overrides_by_slug else None
        )

        section_refs = deepcopy(page.get("sections", []))
        changed = False
        for section_ref in section_refs:
            if section_ref.get("section_id") != section_id:
                continue

            current_override = (
                section_ref.get("design_overrides")
                if "design_overrides" in section_ref
                else None
            )
            if target_override is None:
                if current_override is not None:
                    section_ref["design_overrides"] = None
                    changed = True
            elif current_override != target_override:
                section_ref["design_overrides"] = deepcopy(target_override)
                changed = True

        if changed:
            await pages.update_one(
                {"_id": page["_id"]},
                {
                    "$set": {
                        "sections": section_refs,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            updated_pages += 1

    section_type_data = (
        design_state.get("section_type_data")
        if isinstance(design_state.get("section_type_data"), dict)
        else None
    )
    section_doc_overrides_present = "design_overrides" in design_state
    if isinstance(section_type_data, dict):
        section_oid = as_object_id(section_id)
        section_doc = (
            await sections.find_one({"_id": section_oid}, {"type_data": 1})
            if section_oid is not None
            else None
        )
        if section_doc:
            current_type_data = (
                deepcopy(section_doc.get("type_data"))
                if isinstance(section_doc.get("type_data"), dict)
                else {}
            )
            changed = False
            for key, value in section_type_data.items():
                next_value = deepcopy(value)
                if current_type_data.get(key) != next_value:
                    current_type_data[key] = next_value
                    changed = True
            if changed:
                await sections.update_one(
                    {"_id": section_doc["_id"]},
                    {"$set": {"type_data": current_type_data, "updated_at": datetime.utcnow()}},
                )

    if section_doc_overrides_present:
        section_oid = as_object_id(section_id)
        target_overrides = design_state.get("design_overrides")
        if section_oid is not None:
            if target_overrides is None:
                await sections.update_one(
                    {"_id": section_oid},
                    {
                        "$unset": {"design_overrides": ""},
                        "$set": {"updated_at": datetime.utcnow()},
                    },
                )
            else:
                await sections.update_one(
                    {"_id": section_oid},
                    {
                        "$set": {
                            "design_overrides": deepcopy(target_overrides),
                            "updated_at": datetime.utcnow(),
                        },
                    },
                )

    return updated_pages
