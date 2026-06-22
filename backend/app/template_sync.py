from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import re
import unicodedata
from typing import Any
from zoneinfo import ZoneInfo

from bson import ObjectId

from app import program_catalog
from app.case_utils import normalize_keys_to_snake
from app.collection_names import (
    DESIGN_CONFIG_COLLECTION,
    DESIGN_EDITOR_CONFIG_COLLECTION,
    DESIGN_VERSIONS_COLLECTION,
    ITEM_PAGE_CONFIG_COLLECTION,
    ITEM_PAGE_ROUTES_COLLECTION,
    PROGRAM_SHARED_COLLECTION,
    TEMPLATE_PAGES_COLLECTION,
    TEMPLATE_SECTIONS_COLLECTION,
)
from app.integration_review import (
    IntegrationReviewError,
    REVIEW_ROOT_ITEM_KEY,
    get_effective_integration_data_doc,
    normalize_review_field_path,
    review_item_key_for_row,
    set_value_at_path as set_integration_review_value_at_path,
    upsert_integration_review_override,
)
from app.media_tags import build_media_tag, media_tag_text_value, normalize_media_tag_part
from app.models.sections.normalization import normalize_section_description_payload
from app.models.sections.sections import (
    ProgramGig,
    ProgramStage,
    get_default_title,
    get_default_type_data,
    migrate_document_section_payload,
)
from app.revisioning import (
    GENERIC_SECTION_TYPE_DATA_KEY,
    get_section_design_type_data_keys,
    snapshots_equal,
)
from app.section_structure import (
    apply_section_order_from_structure,
    resolve_section_structure,
    strip_legacy_container_override,
)
from app.sitemap import upsert_generated_redirects_for_slug_mapping

SECTION_TEMPLATE_ID_PREFIX = "ts__"
PAGE_SECTION_ID_PREFIX = "tp__"
CONTAINER_SECTION_ID_PREFIX = "tc__"
PAGE_HEADER_ID_PREFIX = "th__p__"

_TEMPLATE_NAME_RE = re.compile(r"[^a-z0-9_-]+")
_ROUTE_SEGMENT_RE = re.compile(r"[^a-z0-9-]+")
_SECTION_TYPE_RE = re.compile(r"[^a-z0-9_]+")
ADMIN_CONFIG_KEY = DESIGN_EDITOR_CONFIG_COLLECTION
PROGRAM_SHARED_DOC_ID = program_catalog.PROGRAM_SHARED_DOC_ID
SHARED_ITEM_PAGE_ROUTES_DOC_ID = "global"
GLOBAL_ITEM_PAGE_CONFIG_DOC_ID = "default"

# Keys used in the global config document. Parent routes and slug fields used to
# live here; they are kept in the normalized response for old clients, but item
# page routing is now owned by the active page template.
GLOBAL_ITEM_PAGE_ROUTING_VERSION = 3
_GLOBAL_CFG_PARENT_ROUTE_KEYS = {
    "blog_item_parent_route",
    "program_stage_parent_route",
    "program_gig_parent_route",
}
_GLOBAL_CFG_TEMPLATE_PATH_KEYS = {
    "blog_item_template_path",
    "program_stage_template_path",
    "program_gig_template_path",
}
_GLOBAL_CFG_SLUG_FIELD_DEFAULTS = {
    "blog_item_slug_field": "title",
    "program_stage_slug_field": "name",
    "program_gig_slug_field": "title",
}
_GLOBAL_CFG_SLUG_FIELD_ALLOWED_VALUES = {
    "blog_item_slug_field": {
        "title",
        "title.de",
        "title.en",
        "date",
        "id",
    },
    "program_stage_slug_field": {
        "name",
        "name.de",
        "name.en",
        "id",
    },
    "program_gig_slug_field": {
        "title",
        "title.de",
        "title.en",
        "artist_name",
        "artist_name.de",
        "artist_name.en",
        "id",
    },
}
_ITEM_PAGE_TYPE_PREFIXES: dict[tuple[str, str], str] = {
    ("blog", "item"): "blog_item",
    ("program", "stage"): "program_stage",
    ("program", "gig"): "program_gig",
}
_ITEM_PAGE_PREFIX_SOURCE: dict[str, tuple[str, str]] = {
    prefix: source for source, prefix in _ITEM_PAGE_TYPE_PREFIXES.items()
}
_ITEM_PAGE_SOURCE_TYPE_KEYS: dict[tuple[str, str], str] = {
    ("blog", "item"): "blog",
    ("program", "stage"): "program_stage",
    ("program", "gig"): "program_gig",
}
ITEM_PAGE_SYNC_MODE_KEEP_SOURCE = "keep_source"
ITEM_PAGE_SYNC_MODE_KEEP_LOCAL = "keep_local"
ITEM_PAGE_SYNC_MODES = {
    ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
    ITEM_PAGE_SYNC_MODE_KEEP_LOCAL,
}
ITEM_PAGE_MAPPED_TARGET_VALUES_KEY = "template_mapped_target_values"
ITEM_PAGE_LOCAL_MAPPED_OVERRIDES_KEY = "template_local_mapped_overrides"
QUILL_SINGLE_PLAIN_BLOCK_RE = re.compile(r"^\s*<(div|p)\b[^>]*>(.*?)</\1>\s*$", re.IGNORECASE | re.DOTALL)
HTML_TAG_RE = re.compile(r"</?[a-z][^>]*>", re.IGNORECASE)
LIST_TARGET_VISIBILITY_PRESET_FIELD_PATHS = (
    "zoom",
    "focal_x",
    "focal_y",
    "rotation",
    "image_zoom",
    "image_focal_x",
    "image_focal_y",
    "image_rotation",
)
LIST_TARGET_VISIBILITY_PRESET_COLLECTION_PATHS_BY_SECTION_TYPE: dict[str, tuple[str, ...]] = {
    "gallery": ("images",),
    "tiles": ("tiles",),
    "program": ("gigs", "stages"),
}
PAGE_TARGET_VISIBILITY_PRESET_PATHS_BY_COLLECTION_PATH: dict[str, tuple[str, ...]] = {
    "page": ("slug",),
    "header": (
        "background_zoom",
        "background_focal_x",
        "background_focal_y",
        "background_rotation",
        "overlay_zoom",
        "overlay_focal_x",
        "overlay_focal_y",
        "overlay_rotation",
    ),
}
SECTION_OUTPUT_MAPPING_MODES = {"default", "custom"}
PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS = "shared_items"
PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION = "integration"
PAGE_MAPPING_SOURCE_PROVIDERS = {
    PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS,
    PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION,
}
SECTION_TEMPLATE_SYNC_FIELDS = (
    "title_placeholder",
    "title",
    "type_data",
    "section_integration_mapping",
    "design_overrides",
)

_PAGE_MAPPING_SECTION_COLLECTION_RE = re.compile(r"^sections\[([^\]]+)\]$")
_PAGE_MAPPING_SECTION_TARGET_RE = re.compile(r"^sections\[([^\]]+)\]\.(.+)$")
_PAGE_MAPPING_SECTION_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_LINKS_SOCIAL_ITEM_KEY_PATH_RE = re.compile(r"^type_data\.items\.([^.]+)(\..+)?$")
_YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def normalize_section_type_value(value: Any, *, default: str | None = None) -> str | None:
    raw = str(value or "").strip().lower().replace("-", "_")
    raw = _SECTION_TYPE_RE.sub("_", raw).strip("_")
    if raw:
        return raw
    if default is not None:
        return normalize_section_type_value(default)
    return None


def normalize_section_template_ref(value: Any) -> str | None:
    raw = str(value or "").strip().strip("/")
    if not raw:
        return None
    parts = [part for part in raw.split("/") if part]
    if not parts:
        return None

    section_type = normalize_section_type_value(parts[0])
    if not section_type:
        return None
    template_name = normalize_template_name(parts[1] if len(parts) > 1 else "default", default="default")
    return f"{section_type}/{template_name}"


def parse_section_template_ref(value: Any) -> tuple[str | None, str | None]:
    normalized = normalize_section_template_ref(value)
    if not normalized:
        return None, None
    section_type, template_name = normalized.split("/", 1)
    return section_type, template_name


def _normalize_section_integration_mapping_rows(raw_rows: Any) -> list[dict]:
    if not isinstance(raw_rows, list):
        return []
    rows: list[dict] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        source_path = str(row.get("source_path") or "").strip()
        target_path = str(row.get("target_path") or "").strip()
        if not source_path or not target_path:
            continue
        rows.append(
            {
                "source_path": source_path,
                "target_path": target_path,
            }
        )
    return rows


def _normalize_section_integration_list_filters(raw_filters: Any) -> list[dict]:
    if not isinstance(raw_filters, list):
        return []

    normalized_filters: list[dict] = []
    seen_ids: set[str] = set()
    for index, raw_filter in enumerate(raw_filters):
        if not isinstance(raw_filter, dict):
            continue

        filter_id = str(
            raw_filter.get("id")
            or ""
        ).strip()
        if not filter_id:
            filter_id = f"filter-{index + 1}"

        if filter_id in seen_ids:
            suffix = 2
            candidate = f"{filter_id}-{suffix}"
            while candidate in seen_ids:
                suffix += 1
                candidate = f"{filter_id}-{suffix}"
            filter_id = candidate
        seen_ids.add(filter_id)

        source_path = str(
            raw_filter.get("source_path")
            or ""
        ).strip()
        target_path = str(
            raw_filter.get("target_path")
            or ""
        ).strip()
        name = str(raw_filter.get("name") or "").strip()
        if not name and source_path:
            name = source_path

        enabled_raw = raw_filter.get("enabled")
        enabled = bool(enabled_raw) if enabled_raw is not None else True

        admin_scope_value_raw = raw_filter.get("admin_scope_value")
        admin_scope_value = str(admin_scope_value_raw or "").strip() or None

        normalized_filters.append(
            {
                "id": filter_id,
                "name": name,
                "source_path": source_path,
                "target_path": target_path,
                "enabled": enabled,
                "admin_scope_value": admin_scope_value,
            }
        )

    return normalized_filters


def _normalize_hidden_list_target_paths_by_collection_path(raw_map: Any) -> dict[str, list[str]]:
    if not isinstance(raw_map, dict):
        return {}

    normalized_map: dict[str, list[str]] = {}
    for raw_collection_path, raw_hidden_paths in raw_map.items():
        collection_path = str(raw_collection_path or "").strip()
        if not collection_path or not isinstance(raw_hidden_paths, list):
            continue

        hidden_paths: list[str] = []
        seen_paths: set[str] = set()
        for raw_hidden_path in raw_hidden_paths:
            hidden_path = str(raw_hidden_path or "").strip()
            if not hidden_path or hidden_path in seen_paths:
                continue
            seen_paths.add(hidden_path)
            hidden_paths.append(hidden_path)

        if hidden_paths:
            normalized_map[collection_path] = hidden_paths

    return normalized_map


def normalize_section_output_mapping(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {
            "mode": "default",
            "exposed_target_paths": [],
        }

    mode = str(raw.get("mode") or "default").strip().lower()
    if mode not in SECTION_OUTPUT_MAPPING_MODES:
        mode = "default"

    raw_paths = raw.get("exposed_target_paths")
    if raw_paths is None:
        raw_paths = raw.get("exposedTargetPaths")

    exposed_paths: list[str] = []
    seen_paths: set[str] = set()
    if isinstance(raw_paths, list):
        for raw_path in raw_paths:
            path = str(raw_path or "").strip()
            if not path or path in seen_paths:
                continue
            seen_paths.add(path)
            exposed_paths.append(path)

    return {
        "mode": mode,
        "exposed_target_paths": exposed_paths,
    }


def _is_hidden_list_target_visibility_config_present(raw_mapping: Any) -> bool:
    if not isinstance(raw_mapping, dict):
        return False
    return (
        "hidden_list_target_paths_by_collection_path" in raw_mapping
        or "hiddenListTargetPathsByCollectionPath" in raw_mapping
    )


def apply_hidden_list_target_visibility_presets(
    section_type: str,
    section_integration_mapping: dict | None,
    *,
    visibility_config_present: bool = False,
) -> dict:
    normalized_mapping = (
        section_integration_mapping
        if isinstance(section_integration_mapping, dict)
        else {}
    )
    if visibility_config_present:
        return normalized_mapping
    if normalized_mapping.get("hidden_list_target_paths_by_collection_path") is not None:
        return normalized_mapping

    normalized_section_type = normalize_section_type_value(section_type, default="text") or "text"
    preset_collection_paths = LIST_TARGET_VISIBILITY_PRESET_COLLECTION_PATHS_BY_SECTION_TYPE.get(
        normalized_section_type
    )
    if not preset_collection_paths:
        return normalized_mapping

    next_mapping = dict(normalized_mapping)
    next_mapping["hidden_list_target_paths_by_collection_path"] = {
        collection_path: list(LIST_TARGET_VISIBILITY_PRESET_FIELD_PATHS)
        for collection_path in preset_collection_paths
    }
    return next_mapping


def normalize_section_integration_mapping(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {}

    active_mode = str(raw.get("active_mode") or "auto").strip().lower()
    if active_mode not in {"auto", "list", "object"}:
        active_mode = "auto"

    selected_integration_id = str(
        raw.get("selected_integration_id")
        or ""
    ).strip() or None

    scalar_mappings = _normalize_section_integration_mapping_rows(
        raw.get("scalar_mappings")
    )

    raw_list_map = raw.get("list_mappings_by_collection_path")
    list_mappings_by_collection_path: dict[str, list[dict]] = {}
    if isinstance(raw_list_map, dict):
        for raw_collection_path, raw_rows in raw_list_map.items():
            collection_path = str(raw_collection_path or "").strip()
            if not collection_path:
                continue
            rows = _normalize_section_integration_mapping_rows(raw_rows)
            if rows:
                list_mappings_by_collection_path[collection_path] = rows

    raw_list_filters = raw.get("list_filters")
    list_filters = _normalize_section_integration_list_filters(raw_list_filters)
    raw_hidden_list_targets_by_collection_path = (
        raw.get("hidden_list_target_paths_by_collection_path")
        if raw.get("hidden_list_target_paths_by_collection_path") is not None
        else raw.get("hiddenListTargetPathsByCollectionPath")
    )
    hidden_list_target_paths_by_collection_path = _normalize_hidden_list_target_paths_by_collection_path(
        raw_hidden_list_targets_by_collection_path
    )

    if (
        active_mode == "auto"
        and selected_integration_id is None
        and not scalar_mappings
        and not list_mappings_by_collection_path
        and not list_filters
        and not hidden_list_target_paths_by_collection_path
    ):
        return {}

    normalized = {
        "active_mode": active_mode,
        "selected_integration_id": selected_integration_id,
        "scalar_mappings": scalar_mappings,
        "list_mappings_by_collection_path": list_mappings_by_collection_path,
        "list_filters": list_filters,
    }
    if hidden_list_target_paths_by_collection_path:
        normalized["hidden_list_target_paths_by_collection_path"] = hidden_list_target_paths_by_collection_path
    return normalized


def _normalize_section_integration_mapping_payload(raw: Any) -> dict:
    normalized_raw = raw
    if isinstance(raw, dict):
        normalized_raw, _stats = normalize_keys_to_snake(raw)
    return normalize_section_integration_mapping(normalized_raw)


def _normalize_page_mapping_section_token(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.isdigit():
        return str(int(raw))
    if not _PAGE_MAPPING_SECTION_TOKEN_RE.fullmatch(raw):
        return ""
    return raw


def _is_numeric_page_mapping_section_token(value: Any) -> bool:
    token = str(value or "").strip()
    return bool(token and token.isdigit())


def _compose_page_mapping_section_collection_path(section_token: Any) -> str:
    token = _normalize_page_mapping_section_token(section_token)
    return f"sections[{token}]" if token else ""


def _extract_page_mapping_section_token(collection_path: Any) -> str:
    normalized = str(collection_path or "").strip()
    match = _PAGE_MAPPING_SECTION_COLLECTION_RE.fullmatch(normalized)
    if not match:
        return ""
    return _normalize_page_mapping_section_token(match.group(1))


def _normalize_page_mapping_row_template_section_id(row: Any, collection_path: Any) -> str:
    row_payload = row if isinstance(row, dict) else {}
    token = _normalize_page_mapping_section_token(row_payload.get("template_section_id"))
    if token and not _is_numeric_page_mapping_section_token(token):
        return token
    collection_token = _extract_page_mapping_section_token(collection_path)
    if collection_token and not _is_numeric_page_mapping_section_token(collection_token):
        return collection_token
    return ""


def _normalize_page_mapping_collection_path(value: Any) -> str:
    normalized = str(value or "").strip()
    if normalized in {"page", "header"}:
        return normalized
    match = _PAGE_MAPPING_SECTION_COLLECTION_RE.fullmatch(normalized)
    if not match:
        return ""
    return _compose_page_mapping_section_collection_path(match.group(1))


def _split_page_mapping_target_path(value: Any) -> tuple[str, str] | tuple[None, None]:
    normalized = str(value or "").strip()
    if not normalized:
        return None, None
    if normalized.startswith("page."):
        target_path = normalized[5:].strip()
        return ("page", target_path) if target_path else (None, None)
    if normalized.startswith("header."):
        target_path = normalized[7:].strip()
        return ("header", target_path) if target_path else (None, None)
    section_match = _PAGE_MAPPING_SECTION_TARGET_RE.fullmatch(normalized)
    if section_match:
        section_token = _normalize_page_mapping_section_token(section_match.group(1))
        target_path = str(section_match.group(2) or "").strip()
        return (_compose_page_mapping_section_collection_path(section_token), target_path) if section_token and target_path else (None, None)
    return ("page", normalized)


def _normalize_page_mapping_target_path_for_collection(
    collection_path: str,
    target_path: Any,
) -> str:
    normalized_collection = _normalize_page_mapping_collection_path(collection_path)
    if not normalized_collection:
        return ""

    raw_target_path = _canonicalize_page_mapping_target_path(target_path)
    if not raw_target_path:
        return ""

    if (
        not raw_target_path.startswith("page.")
        and not raw_target_path.startswith("header.")
        and not raw_target_path.startswith("sections[")
    ):
        return raw_target_path

    split_collection, split_target_path = _split_page_mapping_target_path(raw_target_path)
    if split_collection and split_target_path:
        if split_collection == normalized_collection:
            return split_target_path
        return ""
    return ""


def _canonicalize_page_mapping_target_path(value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    fixed_gig_tokens = {"fixedGigId", "fixed_gig_id"}
    type_data_tokens = {"typeData", "type_data"}
    parts = normalized.split(".")
    if parts[-1] in fixed_gig_tokens:
        if len(parts) >= 2 and parts[-2] in type_data_tokens:
            parts[-2:] = ["type_data", "fixed_gig_id"]
        else:
            parts[-1:] = ["type_data", "fixed_gig_id"]
        return ".".join(parts)
    return normalized


def _is_fixed_gig_mapping_target_path(value: Any) -> bool:
    normalized = _canonicalize_page_mapping_target_path(value)
    return normalized == "type_data.fixed_gig_id" or normalized.endswith(".type_data.fixed_gig_id")


def _normalize_page_mapping_source_provider(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in PAGE_MAPPING_SOURCE_PROVIDERS else ""


def _normalize_page_mapping_source_path(
    value: Any,
    *,
    source_provider: str = PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION,
) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    provider = _normalize_page_mapping_source_provider(source_provider) or PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
    if provider == PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS:
        if normalized.startswith("item.") or normalized.startswith("integration."):
            return normalized
        return f"item.{normalized}"
    if normalized.startswith("integration."):
        return normalized
    if normalized.startswith("item."):
        item_path = normalized[5:].strip()
        return f"integration.{item_path}" if item_path else ""
    return f"integration.{normalized}"


def _integration_primary_key_source_path(output_primary_key_path: Any) -> str:
    normalized = str(output_primary_key_path or "").strip()
    return f"integration.{normalized}" if normalized else ""


def _page_mapping_source_path_for_target(
    source_path: Any,
    target_path: Any,
    *,
    integration_primary_key_path: Any = None,
    source_provider: str = PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION,
) -> str:
    provider = _normalize_page_mapping_source_provider(source_provider) or PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
    if _is_fixed_gig_mapping_target_path(target_path):
        primary_key_source_path = _integration_primary_key_source_path(integration_primary_key_path)
        raw_source_path = str(source_path or "").strip()
        if (
            provider == PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
            and primary_key_source_path
            and raw_source_path in {"", "id", "item.id"}
        ):
            return primary_key_source_path
    return _normalize_page_mapping_source_path(source_path, source_provider=provider)


def _fixed_gig_source_requires_primary_fallback(source_path: Any) -> bool:
    raw_source_path = str(source_path or "").strip()
    return raw_source_path in {"", "id", "item.id", "integration.id"}


def page_mapping_has_fixed_gig_target(page_integration_mapping: Any) -> bool:
    raw_mapping = page_integration_mapping if isinstance(page_integration_mapping, dict) else {}
    raw_rows_by_collection = raw_mapping.get("list_mappings_by_collection_path")
    if isinstance(raw_rows_by_collection, dict):
        for raw_collection_path, rows in raw_rows_by_collection.items():
            collection_path = _normalize_page_mapping_collection_path(raw_collection_path)
            if not collection_path or not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                target_path = _normalize_page_mapping_target_path_for_collection(
                    collection_path,
                    row.get("target_path"),
                )
                if _is_fixed_gig_mapping_target_path(target_path):
                    return True

    mapping = normalize_page_integration_mapping(page_integration_mapping)
    rows_by_collection = mapping.get("list_mappings_by_collection_path")
    if not isinstance(rows_by_collection, dict):
        return False
    for rows in rows_by_collection.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and _is_fixed_gig_mapping_target_path(row.get("target_path")):
                return True
    return False


def page_mapping_fixed_gig_needs_primary_fallback(page_integration_mapping: Any) -> bool:
    raw_mapping = page_integration_mapping if isinstance(page_integration_mapping, dict) else {}
    raw_rows_by_collection = raw_mapping.get("list_mappings_by_collection_path")
    if not isinstance(raw_rows_by_collection, dict):
        raw_rows_by_collection = (
            normalize_page_integration_mapping(page_integration_mapping)
            .get("list_mappings_by_collection_path")
        )
    if not isinstance(raw_rows_by_collection, dict):
        return False

    for raw_collection_path, rows in raw_rows_by_collection.items():
        collection_path = _normalize_page_mapping_collection_path(raw_collection_path)
        if not collection_path or not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            target_path = _normalize_page_mapping_target_path_for_collection(
                collection_path,
                row.get("target_path"),
            )
            if (
                _is_fixed_gig_mapping_target_path(target_path)
                and _fixed_gig_source_requires_primary_fallback(row.get("source_path"))
            ):
                return True
    return False


def normalize_fixed_gig_page_mapping_sources(
    page_integration_mapping: Any,
    output_primary_key_path: Any,
) -> dict:
    mapping = normalize_page_integration_mapping(page_integration_mapping)
    source_provider = _normalize_page_mapping_source_provider(mapping.get("source_provider")) or PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION

    raw_mapping = page_integration_mapping if isinstance(page_integration_mapping, dict) else {}
    raw_rows_by_collection = raw_mapping.get("list_mappings_by_collection_path")
    if not isinstance(raw_rows_by_collection, dict):
        raw_rows_by_collection = mapping.get("list_mappings_by_collection_path")
    if not isinstance(raw_rows_by_collection, dict):
        return mapping

    next_rows_by_collection: dict[str, list[dict]] = {}
    changed = False
    for raw_collection_path, rows in raw_rows_by_collection.items():
        collection_path = _normalize_page_mapping_collection_path(raw_collection_path)
        if not collection_path:
            continue
        if not isinstance(rows, list):
            continue
        next_rows: list[dict] = []
        for raw_row in rows:
            if not isinstance(raw_row, dict):
                continue
            target_path = _normalize_page_mapping_target_path_for_collection(
                collection_path,
                raw_row.get("target_path"),
            )
            source_path = _page_mapping_source_path_for_target(
                raw_row.get("source_path"),
                target_path,
                integration_primary_key_path=output_primary_key_path,
                source_provider=source_provider,
            )
            if not source_path or not target_path:
                continue
            next_row = {
                "source_path": source_path,
                "target_path": target_path,
            }
            template_section_id = _normalize_page_mapping_row_template_section_id(
                raw_row,
                collection_path,
            )
            if template_section_id:
                next_row["template_section_id"] = template_section_id
            normalized_original_source = _normalize_page_mapping_source_path(
                raw_row.get("source_path"),
                source_provider=source_provider,
            )
            if source_path != normalized_original_source:
                changed = True
            next_rows.append(next_row)
        if next_rows:
            next_rows_by_collection[collection_path] = next_rows

    if not changed:
        return mapping
    next_mapping = dict(mapping)
    next_mapping["list_mappings_by_collection_path"] = next_rows_by_collection
    return next_mapping


def _clear_program_fixed_gig_scope_fields(root: dict, section_index: int | None) -> None:
    if section_index is None:
        return
    sections = root.get("sections")
    if not isinstance(sections, list) or section_index < 0 or section_index >= len(sections):
        return
    section_payload = sections[section_index]
    if not isinstance(section_payload, dict):
        return
    section_type = normalize_section_type_value(section_payload.get("section_type"), default="") or ""
    if section_type != "program":
        return
    type_data = section_payload.get("type_data")
    if not isinstance(type_data, dict):
        type_data = {}
        section_payload["type_data"] = type_data
    type_data["fixed_day"] = ""
    type_data["fixed_stage_id"] = ""


def _strip_shared_section_type_data(section_type: str, type_data: Any) -> dict:
    normalized = deepcopy(type_data) if isinstance(type_data, dict) else {}
    normalized_section_type = str(section_type or "").strip().lower()
    if normalized_section_type == "blog":
        normalized.pop("items", None)
        normalized.pop("tags", None)
        return normalized
    if normalized_section_type != "program":
        return normalized
    for key in (
        "stages",
        "program_gigs_integration_mapping",
        "programGigsIntegrationMapping",
        "program_gigs_integration_mapping_cache_state",
        "programGigsIntegrationMappingCacheState",
        "program_stages_integration_mapping",
        "programStagesIntegrationMapping",
        "program_stages_integration_mapping_cache_state",
        "programStagesIntegrationMappingCacheState",
    ):
        normalized.pop(key, None)
    return normalized


def _normalize_links_social_platform_key(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    normalized = re.sub(r"[^a-z0-9_-]+", "-", raw)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized


def _build_links_social_platform_index_map(section_payload: Any) -> dict[str, int]:
    if not isinstance(section_payload, dict):
        return {}
    section_type = normalize_section_type_value(section_payload.get("section_type"), default="") or ""
    if section_type != "links":
        return {}
    type_data = section_payload.get("type_data")
    if not isinstance(type_data, dict) or not bool(type_data.get("social_mode")):
        return {}
    items = type_data.get("items")
    if not isinstance(items, list):
        return {}
    platform_index_by_key: dict[str, int] = {}
    for index, entry in enumerate(items):
        if not isinstance(entry, dict):
            continue
        platform_key = _normalize_links_social_platform_key(entry.get("icon"))
        if not platform_key or platform_key in platform_index_by_key:
            continue
        platform_index_by_key[platform_key] = index
    return platform_index_by_key


def _resolve_links_social_target_path(section_payload: Any, target_path: Any) -> str:
    normalized_target_path = str(target_path or "").strip()
    if not normalized_target_path:
        return ""
    match = _LINKS_SOCIAL_ITEM_KEY_PATH_RE.fullmatch(normalized_target_path)
    if not match:
        return normalized_target_path
    platform_key = _normalize_links_social_platform_key(match.group(1))
    if not platform_key:
        return ""
    platform_index_by_key = _build_links_social_platform_index_map(section_payload)
    if platform_key not in platform_index_by_key:
        return ""
    suffix = str(match.group(2) or "")
    return f"type_data.items[{platform_index_by_key[platform_key]}]{suffix}"


def _extract_video_id_from_mapping_value(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if _YOUTUBE_VIDEO_ID_RE.fullmatch(raw) or re.fullmatch(r"\d+", raw):
        return raw
    short_match = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", raw)
    if short_match:
        return short_match.group(1)
    watch_match = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", raw)
    if watch_match:
        return watch_match.group(1)
    embed_match = re.search(r"/embed/([A-Za-z0-9_-]{11})", raw)
    if embed_match:
        return embed_match.group(1)
    vimeo_match = re.search(r"vimeo\.com/(?:.*/)?(\d+)(?:$|[?#])", raw, re.IGNORECASE)
    if vimeo_match:
        return vimeo_match.group(1)
    return raw


def _normalize_page_mapping_rows(
    rows: Any,
    *,
    collection_path: str,
    source_provider: str = PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION,
) -> list[dict]:
    if not isinstance(rows, list):
        return []
    next_rows: list[dict] = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            continue
        target_path = _normalize_page_mapping_target_path_for_collection(
            collection_path,
            raw_row.get("target_path"),
        )
        source_path = _page_mapping_source_path_for_target(
            raw_row.get("source_path"),
            target_path,
            source_provider=source_provider,
        )
        if not source_path or not target_path:
            continue
        next_row = {
            "source_path": source_path,
            "target_path": target_path,
        }
        template_section_id = _normalize_page_mapping_row_template_section_id(
            raw_row,
            collection_path,
        )
        if template_section_id:
            next_row["template_section_id"] = template_section_id
        next_rows.append(next_row)
    return next_rows


def _normalize_page_hidden_list_target_paths_by_collection_path(
    raw_map: Any,
) -> dict[str, list[str]]:
    normalized_hidden = _normalize_hidden_list_target_paths_by_collection_path(raw_map)
    next_hidden: dict[str, list[str]] = {}
    for raw_collection_path, raw_hidden_paths in normalized_hidden.items():
        collection_path = _normalize_page_mapping_collection_path(raw_collection_path)
        if not collection_path:
            continue
        if collection_path not in {"page", "header"}:
            continue
        normalized_hidden_paths: list[str] = []
        seen_hidden_paths: set[str] = set()
        for raw_hidden_path in raw_hidden_paths:
            hidden_path = _normalize_page_mapping_target_path_for_collection(
                collection_path,
                raw_hidden_path,
            )
            if not hidden_path or hidden_path in seen_hidden_paths:
                continue
            seen_hidden_paths.add(hidden_path)
            normalized_hidden_paths.append(hidden_path)
        if normalized_hidden_paths:
            next_hidden[collection_path] = normalized_hidden_paths
    return next_hidden


def _is_page_hidden_target_visibility_config_present(raw_mapping: Any) -> bool:
    if not isinstance(raw_mapping, dict):
        return False
    return "hidden_list_target_paths_by_collection_path" in raw_mapping


def apply_page_hidden_target_visibility_presets(
    page_integration_mapping: dict | None,
    *,
    visibility_config_present: bool = False,
) -> dict:
    normalized_mapping = (
        page_integration_mapping
        if isinstance(page_integration_mapping, dict)
        else {}
    )
    if visibility_config_present:
        return normalized_mapping
    if normalized_mapping.get("hidden_list_target_paths_by_collection_path") is not None:
        return normalized_mapping

    next_mapping = dict(normalized_mapping)
    next_mapping["hidden_list_target_paths_by_collection_path"] = {
        collection_path: list(hidden_paths)
        for collection_path, hidden_paths in PAGE_TARGET_VISIBILITY_PRESET_PATHS_BY_COLLECTION_PATH.items()
    }
    return next_mapping


def _normalize_preview_item_index(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except Exception:
        return None
    return parsed if parsed >= 0 else None


def _normalize_preview_item_key(value: Any) -> str:
    return str(value or "").strip()


def normalize_page_integration_mapping(raw: Any) -> dict:
    has_structured_mapping = isinstance(raw, dict)
    raw_mapping = raw if has_structured_mapping else {}
    active_mode = str(raw_mapping.get("active_mode") or "list").strip().lower()
    if active_mode not in {"auto", "list", "object"}:
        active_mode = "list"

    selected_integration_id = str(raw_mapping.get("selected_integration_id") or "").strip() or None
    source_provider = _normalize_page_mapping_source_provider(raw_mapping.get("source_provider"))
    if not source_provider and selected_integration_id:
        source_provider = PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
    if source_provider == PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS:
        selected_integration_id = None
    source_path_provider = source_provider or PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
    raw_list_map = raw_mapping.get("list_mappings_by_collection_path")
    list_mappings_by_collection_path: dict[str, list[dict]] = {}
    if isinstance(raw_list_map, dict):
        for raw_collection_path, raw_rows in raw_list_map.items():
            collection_path = _normalize_page_mapping_collection_path(raw_collection_path)
            if not collection_path:
                continue
            rows = _normalize_page_mapping_rows(
                raw_rows,
                collection_path=collection_path,
                source_provider=source_path_provider,
            )
            if rows:
                list_mappings_by_collection_path[collection_path] = rows

    raw_hidden_paths = raw_mapping.get("hidden_list_target_paths_by_collection_path")
    hidden_list_target_paths_by_collection_path = _normalize_page_hidden_list_target_paths_by_collection_path(
        raw_hidden_paths
    )
    preview_item_index = _normalize_preview_item_index(raw_mapping.get("preview_item_index"))
    preview_item_key = _normalize_preview_item_key(raw_mapping.get("preview_item_key"))

    if (
        active_mode == "list"
        and selected_integration_id is None
        and not list_mappings_by_collection_path
        and not hidden_list_target_paths_by_collection_path
        and preview_item_index is None
        and not preview_item_key
        and not source_provider
    ):
        return {}

    normalized = {
        "active_mode": active_mode,
        "selected_integration_id": selected_integration_id,
        "list_mappings_by_collection_path": list_mappings_by_collection_path,
    }
    if source_provider:
        normalized["source_provider"] = source_provider
    if hidden_list_target_paths_by_collection_path:
        normalized["hidden_list_target_paths_by_collection_path"] = hidden_list_target_paths_by_collection_path
    if preview_item_index is not None:
        normalized["preview_item_index"] = preview_item_index
    if preview_item_key:
        normalized["preview_item_key"] = preview_item_key
    return normalized


def resolve_page_integration_mapping_for_template_doc(template_doc: dict) -> dict:
    if not isinstance(template_doc, dict):
        return {}
    raw_mapping = template_doc.get("page_integration_mapping")
    if isinstance(raw_mapping, dict) and not _normalize_page_mapping_source_provider(
        raw_mapping.get("source_provider")
    ):
        inferred_provider = _infer_page_mapping_source_provider_for_template_doc(template_doc)
        if inferred_provider:
            raw_mapping = {
                **raw_mapping,
                "source_provider": inferred_provider,
            }
    return normalize_page_integration_mapping(raw_mapping)


def _page_mapping_has_integration_source_paths(page_mapping: dict | None) -> bool:
    raw_map = (
        page_mapping.get("list_mappings_by_collection_path")
        if isinstance(page_mapping, dict)
        else {}
    )
    if not isinstance(raw_map, dict):
        return False
    for rows in raw_map.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and str(row.get("source_path") or "").strip().startswith("integration."):
                return True
    return False


def item_page_mapping_source_provider_for_template_doc(template_doc: dict | None) -> str:
    if not isinstance(template_doc, dict):
        return PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
    page_mapping = resolve_page_integration_mapping_for_template_doc(template_doc)
    explicit_provider = _normalize_page_mapping_source_provider(
        page_mapping.get("source_provider") if isinstance(page_mapping, dict) else ""
    )
    if explicit_provider:
        return explicit_provider
    if str((page_mapping or {}).get("selected_integration_id") or "").strip():
        return PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
    if _page_mapping_has_integration_source_paths(page_mapping):
        return PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
    source_type = str(template_doc.get("source_type") or "").strip().lower()
    if source_type == "blog":
        return PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS
    return PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION


def _infer_page_mapping_source_provider_for_template_doc(template_doc: dict | None) -> str:
    if not isinstance(template_doc, dict):
        return ""
    raw_mapping = template_doc.get("page_integration_mapping")
    raw_mapping = raw_mapping if isinstance(raw_mapping, dict) else {}
    explicit_provider = _normalize_page_mapping_source_provider(raw_mapping.get("source_provider"))
    if explicit_provider:
        return explicit_provider
    if str(raw_mapping.get("selected_integration_id") or "").strip():
        return PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
    if _page_mapping_has_integration_source_paths(raw_mapping):
        return PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
    source_type = str(template_doc.get("source_type") or "").strip().lower()
    if source_type == "blog":
        return PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS
    return ""


def _item_page_mapping_uses_shared_items(template_doc: dict | None) -> bool:
    return (
        item_page_mapping_source_provider_for_template_doc(template_doc)
        == PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS
    )


def normalize_template_name(value: str, *, default: str | None = None) -> str:
    raw = str(value or "").strip().lower()
    raw = _TEMPLATE_NAME_RE.sub("-", raw).strip("-")
    if raw:
        return raw
    if default is not None:
        return normalize_template_name(default)
    raise ValueError("Template name is required")


def _normalize_shared_item_source_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"blog", "program"}:
        return normalized
    return ""


def _normalize_shared_item_source_kind(source_type: str, value: Any) -> str:
    normalized_source = _normalize_shared_item_source_type(source_type)
    normalized_kind = str(value or "").strip().lower()
    if normalized_source == "program":
        if normalized_kind in {"stage", "gigs", "gig"}:
            return "stage" if normalized_kind == "stage" else "gig"
        return "gig"
    if normalized_source == "blog":
        return "item"
    return ""


def _compose_shared_item_page_route_ref(source_type: str, source_kind: str, parent_route: str | None) -> str:
    normalized_source = _normalize_shared_item_source_type(source_type)
    normalized_kind = _normalize_shared_item_source_kind(normalized_source, source_kind)
    normalized_route = normalize_parent_route(parent_route)
    if not normalized_source or not normalized_kind or not normalized_route:
        return ""
    route_token = normalized_route.strip("/").replace("/", "__") or "root"
    return f"{normalized_source}:{normalized_kind}:{route_token}"


def normalize_item_page_routes_snapshot(raw_routes: Any) -> list[dict]:
    if isinstance(raw_routes, dict):
        candidate_rows = raw_routes.get("routes")
    else:
        candidate_rows = raw_routes
    if not isinstance(candidate_rows, list):
        return []

    normalized_rows: list[dict] = []
    seen_refs: set[str] = set()
    for raw_row in candidate_rows:
        if not isinstance(raw_row, dict):
            continue
        source_type = _normalize_shared_item_source_type(raw_row.get("source_type"))
        if not source_type:
            continue
        source_kind = _normalize_shared_item_source_kind(source_type, raw_row.get("source_kind"))
        if not source_kind:
            continue
        parent_route = normalize_parent_route(raw_row.get("parent_route"))
        if not parent_route:
            continue
        source_route_ref = str(raw_row.get("source_route_ref") or raw_row.get("id") or "").strip()
        if not source_route_ref:
            source_route_ref = _compose_shared_item_page_route_ref(source_type, source_kind, parent_route)
        if not source_route_ref or source_route_ref in seen_refs:
            continue
        seen_refs.add(source_route_ref)

        section_template_ref = normalize_section_template_ref(
            raw_row.get("section_template_ref")
            if raw_row.get("section_template_ref") is not None
            else f"{source_type}/default"
        ) or normalize_section_template_ref(f"{source_type}/default")

        label = str(raw_row.get("label") or "").strip()
        if not label:
            source_label = "program" if source_type == "program" else "blog"
            kind_label = "stage" if source_kind == "stage" else "gig" if source_kind == "gig" else "item"
            label = f"{source_label}:{kind_label} -- {parent_route}"

        normalized_rows.append(
            {
                "source_route_ref": source_route_ref,
                "parent_route": parent_route,
                "source_type": source_type,
                "source_kind": source_kind,
                "section_template_ref": section_template_ref,
                "label": label,
            }
        )

    normalized_rows.sort(
        key=lambda row: (
            str(row.get("source_type") or ""),
            str(row.get("source_kind") or ""),
            str(row.get("parent_route") or ""),
        )
    )
    return normalized_rows


def slugify_segment(value: Any, *, fallback: str = "item") -> str:
    raw = str(value or "").strip().lower()
    raw = raw.replace("$", "s")
    raw = (
        raw.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    raw = raw.encode("ascii", "ignore").decode("ascii")
    raw = _ROUTE_SEGMENT_RE.sub("-", raw).strip("-")
    return raw or fallback


def normalize_parent_route(value: str | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw == "/":
        return None
    segments = [slugify_segment(segment, fallback="") for segment in raw.strip("/").split("/")]
    segments = [segment for segment in segments if segment]
    if not segments:
        return None
    return "/" + "/".join(segments)


def normalize_item_page_subroute(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw or raw == "/":
        return ""
    segments = [slugify_segment(segment, fallback="") for segment in raw.strip("/").split("/")]
    segments = [segment for segment in segments if segment]
    return "/" + "/".join(segments) if segments else ""


def compose_item_page_effective_parent_route(
    parent_route: Any,
    item_page_subroute: Any = "",
) -> str | None:
    parent = normalize_parent_route(parent_route)
    if not parent:
        return None
    subroute = normalize_item_page_subroute(item_page_subroute)
    if not subroute:
        return parent
    return normalize_parent_route(f"{parent.rstrip('/')}/{subroute.strip('/')}")


def normalize_item_page_source_context(
    source_type: Any,
    source_kind: Any = None,
) -> tuple[str, str] | None:
    normalized_source = str(source_type or "").strip().lower()
    normalized_kind = str(source_kind or "").strip().lower()
    if normalized_source == "blog":
        return "blog", "item"
    if normalized_source == "program":
        if normalized_kind == "stage":
            return "program", "stage"
        return "program", "gig"
    return None


def item_page_config_key_prefix(source_type: Any, source_kind: Any = None) -> str | None:
    source_context = normalize_item_page_source_context(source_type, source_kind)
    if not source_context:
        return None
    return _ITEM_PAGE_TYPE_PREFIXES.get(source_context)


def item_page_source_type_key(source_type: Any, source_kind: Any = None) -> str | None:
    source_context = normalize_item_page_source_context(source_type, source_kind)
    if not source_context:
        return None
    return _ITEM_PAGE_SOURCE_TYPE_KEYS.get(source_context)


def default_item_page_slug_field(source_type: Any, source_kind: Any = None) -> str:
    prefix = item_page_config_key_prefix(source_type, source_kind) or "blog_item"
    return _GLOBAL_CFG_SLUG_FIELD_DEFAULTS.get(f"{prefix}_slug_field", "title")


def normalize_item_page_slug_field(
    source_type: Any,
    source_kind: Any = None,
    value: Any = None,
) -> str:
    prefix = item_page_config_key_prefix(source_type, source_kind) or "blog_item"
    default_value = _GLOBAL_CFG_SLUG_FIELD_DEFAULTS.get(f"{prefix}_slug_field", "title")
    allowed_values = _GLOBAL_CFG_SLUG_FIELD_ALLOWED_VALUES.get(f"{prefix}_slug_field") or {default_value}
    raw = str(value or "").strip()
    return raw if raw in allowed_values else default_value


def effective_item_page_parent_route_for_template(template_doc: dict | None) -> str | None:
    if not isinstance(template_doc, dict):
        return None
    return compose_item_page_effective_parent_route(
        template_doc.get("parent_route"),
        template_doc.get("item_page_subroute"),
    )


def normalize_slug(value: str | None) -> str:
    raw = str(value or "").strip().strip("/")
    if not raw:
        raise ValueError("Slug is required")
    segments = [slugify_segment(segment, fallback="") for segment in raw.split("/")]
    segments = [segment for segment in segments if segment]
    if not segments:
        raise ValueError("Slug is required")
    return "/".join(segments)


def normalize_page_status(value: Any, *, fallback: str = "hidden") -> str:
    raw = str(value or "").strip().lower()
    if raw == "draft":
        return "hidden"
    if raw in {"init", "hidden", "published", "under_construction"}:
        return raw
    return fallback


def is_hidden_like_page_status(value: Any) -> bool:
    normalized = normalize_page_status(value, fallback="hidden")
    return normalized in {"hidden", "init"}


def effective_page_status_from_stored(value: Any) -> str:
    normalized = normalize_page_status(value, fallback="hidden")
    return "hidden" if normalized == "init" else normalized


def parse_page_template_path(path: str) -> tuple[str, str | None]:
    raw = str(path or "").strip().strip("/")
    segments = [segment for segment in raw.split("/") if segment]
    if not segments:
        raise ValueError("Template path is required")
    if len(segments) == 1:
        return normalize_template_name(segments[0]), None
    template_name = normalize_template_name(segments[-1])
    parent_route = normalize_parent_route("/" + "/".join(segments[:-1]))
    if parent_route is None:
        raise ValueError("Parent route is required for item-page templates")
    return template_name, parent_route


def compose_page_template_path(template_name: str, parent_route: str | None) -> str:
    name = normalize_template_name(template_name)
    parent = normalize_parent_route(parent_route)
    if not parent:
        return name
    return f"{parent.strip('/')}/{name}"


def normalize_page_template_path_value(value: Any) -> str | None:
    raw = str(value or "").strip().strip("/")
    if not raw:
        return None
    try:
        template_name, parent_route = parse_page_template_path(raw)
    except Exception:
        return None
    return compose_page_template_path(template_name, parent_route)


def page_template_path_as_item_route(path: Any) -> str | None:
    try:
        template_name, parent_route = parse_page_template_path(str(path or ""))
    except Exception:
        return None
    if not parent_route:
        return None
    return normalize_parent_route(f"{parent_route.rstrip('/')}/{template_name}")


def page_template_path_matches_item_effective_route(path: Any, template_doc: dict | None) -> bool:
    if not isinstance(template_doc, dict):
        return False
    route_from_path = page_template_path_as_item_route(path)
    effective_route = effective_item_page_parent_route_for_template(template_doc)
    if not route_from_path or route_from_path != normalize_parent_route(effective_route):
        return False

    candidate_path = normalize_page_template_path_value(path)
    template_name = normalize_template_name(
        template_doc.get("template_name") or "default",
        default="default",
    )
    template_path = compose_page_template_path(
        template_name,
        normalize_parent_route(template_doc.get("parent_route")),
    )
    return bool(candidate_path and candidate_path != template_path)


def build_template_key_for_page(template_name: str, parent_route: str | None) -> str:
    route = normalize_parent_route(parent_route)
    name = normalize_template_name(template_name)
    if route:
        return f"page:{route}:{name}"
    return f"page:{name}"


def build_template_key_for_section(section_type: str, template_name: str) -> str:
    return f"section:{str(section_type or '').strip().lower()}:{normalize_template_name(template_name)}"


def build_template_key_for_container(template_name: str) -> str:
    return f"container:{normalize_template_name(template_name)}"


def _new_embedded_section_id() -> str:
    return f"sec_{ObjectId()}"


def normalize_embedded_section(section: dict, *, fallback_section_type: str | None = None) -> dict:
    if not isinstance(section, dict):
        section = {}
    section_type = str(section.get("section_type") or fallback_section_type or "text").strip().lower() or "text"
    section_template_name = normalize_template_name(
        section.get("section_template_name") or "default",
        default="default",
    )
    title_placeholder = str(section.get("title_placeholder") or section_type.title()).strip() or section_type.title()
    title = section.get("title") if isinstance(section.get("title"), dict) else get_default_title(section_type)
    type_data = section.get("type_data") if isinstance(section.get("type_data"), dict) else get_default_type_data(section_type)
    section_type, type_data = migrate_document_section_payload(section_type, deepcopy(type_data))
    normalized_type_data = normalize_section_description_payload(section_type, deepcopy(type_data))
    normalized_type_data = _strip_shared_section_type_data(section_type, normalized_type_data)

    embedded_id = str(section.get("id") or "").strip() or _new_embedded_section_id()
    visible = bool(section.get("visible", True))
    width_n = max(1, min(5, int(section.get("width_n", 1) or 1)))
    width_d = max(1, min(5, int(section.get("width_d", 1) or 1)))
    width_n = min(width_n, width_d)
    order = int(section.get("order", 0) or 0)

    device_visibility = section.get("device_visibility")
    if not isinstance(device_visibility, dict):
        device_visibility = {"mobile": True, "tablet": True, "desktop": True}
    else:
        device_visibility = {
            "mobile": bool(device_visibility.get("mobile", True)),
            "tablet": bool(device_visibility.get("tablet", True)),
            "desktop": bool(device_visibility.get("desktop", True)),
        }

    limit_value = section.get("limit")
    if limit_value in (None, "", 0, "0"):
        limit = None
    else:
        try:
            parsed_limit = int(limit_value)
            limit = parsed_limit if parsed_limit > 0 else None
        except Exception:
            limit = None

    design_overrides = section.get("design_overrides") if isinstance(section.get("design_overrides"), dict) else None
    section_integration_mapping = normalize_section_integration_mapping(
        section.get("section_integration_mapping")
        if section.get("section_integration_mapping") is not None
        else section.get("sectionIntegrationMapping")
    )

    return {
        "id": embedded_id,
        "section_type": section_type,
        "section_template_name": section_template_name,
        "title_placeholder": title_placeholder,
        "title": {
            "de": str(title.get("de") or ""),
            "en": str(title.get("en") or ""),
        },
        "type_data": normalized_type_data,
        "order": order,
        "visible": visible,
        "limit": limit,
        "width_n": width_n,
        "width_d": width_d,
        "device_visibility": device_visibility,
        "design_overrides": deepcopy(design_overrides),
        "section_integration_mapping": section_integration_mapping,
    }


def normalize_embedded_sections_and_structure(
    raw_sections: Any,
    raw_structure: Any,
) -> tuple[list[dict], list[dict]]:
    sections_payload = raw_sections if isinstance(raw_sections, list) else []
    normalized_sections: list[dict] = []
    for index, section in enumerate(sections_payload):
        normalized = normalize_embedded_section(section if isinstance(section, dict) else {})
        normalized["order"] = index
        normalized_sections.append(normalized)

    for normalized in normalized_sections:
        overrides = strip_legacy_container_override(normalized.get("design_overrides"))
        if overrides is None:
            normalized.pop("design_overrides", None)
        else:
            normalized["design_overrides"] = overrides

    ordered_ids = [str(section.get("id") or "").strip() for section in normalized_sections if str(section.get("id") or "").strip()]
    normalized_structure = resolve_section_structure(
        raw_structure,
        ordered_ids,
    )
    normalized_sections = apply_section_order_from_structure(
        normalized_sections,
        normalized_structure,
        section_id_field="id",
    )
    return normalized_sections, normalized_structure


def normalize_template_section_design_overrides(value: Any) -> dict | None:
    return strip_legacy_container_override(value)


def normalize_template_header_design_overrides(value: Any) -> dict | None:
    return strip_legacy_container_override(value)


def _normalize_template_sync_bilingual_text(value: dict | None) -> dict:
    source = value if isinstance(value, dict) else {}
    return {
        "de": str(source.get("de") or ""),
        "en": str(source.get("en") or ""),
    }


def build_template_sync_section_payload(
    section_type: str,
    doc: dict | None,
    *,
    type_data_normalizer=None,
) -> dict:
    source = doc if isinstance(doc, dict) else {}
    normalized_section_type = normalize_section_type_value(
        section_type,
        default="text",
    ) or "text"
    readable_type = (
        str(normalized_section_type or "")
        .replace("_", " ")
        .strip()
        .title()
        or "Section"
    )
    raw_type_data = (
        deepcopy(source.get("type_data"))
        if isinstance(source.get("type_data"), dict)
        else get_default_type_data(normalized_section_type)
    )
    normalized_type_data = normalize_section_description_payload(
        normalized_section_type,
        raw_type_data,
    )
    if not isinstance(normalized_type_data, dict):
        normalized_type_data = {}
    if callable(type_data_normalizer):
        normalized_type_data = type_data_normalizer(
            normalized_section_type,
            normalized_type_data,
        )
        if not isinstance(normalized_type_data, dict):
            normalized_type_data = {}
    else:
        normalized_type_data = _strip_shared_section_type_data(
            normalized_section_type,
            normalized_type_data,
        )

    return {
        "title_placeholder": (
            str(source.get("title_placeholder") or readable_type).strip()
            or readable_type
        ),
        "title": _normalize_template_sync_bilingual_text(
            source.get("title") if isinstance(source.get("title"), dict) else None
        ),
        "type_data": normalized_type_data,
        "section_integration_mapping": normalize_section_integration_mapping(
            source.get("section_integration_mapping")
        ),
        "design_overrides": normalize_template_section_design_overrides(
            source.get("design_overrides")
        ),
    }


def get_section_template_sync_changed_fields(
    current_payload: dict,
    template_payload: dict,
) -> list[str]:
    return [
        field
        for field in SECTION_TEMPLATE_SYNC_FIELDS
        if not snapshots_equal(
            current_payload.get(field),
            template_payload.get(field),
        )
    ]


async def resolve_section_template_sync_context(
    db,
    section_doc: dict,
    *,
    type_data_normalizer=None,
) -> tuple[str, str, dict, dict, list[str]]:
    section_type = normalize_section_type_value(
        section_doc.get("section_type"),
        default="text",
    ) or "text"
    template_name = normalize_template_name(
        section_doc.get("section_template_name") or "default",
        default="default",
    )
    template_doc = await db[TEMPLATE_SECTIONS_COLLECTION].find_one(
        {
            "section_type": section_type,
            "template_name": template_name,
        }
    )
    if not isinstance(template_doc, dict):
        raise LookupError(f'Section template "{section_type}/{template_name}" not found')

    current_payload = build_template_sync_section_payload(
        section_type,
        section_doc,
        type_data_normalizer=type_data_normalizer,
    )
    template_payload = build_template_sync_section_payload(
        section_type,
        template_doc,
        type_data_normalizer=type_data_normalizer,
    )
    changed_fields = get_section_template_sync_changed_fields(
        current_payload,
        template_payload,
    )
    return (
        section_type,
        template_name,
        template_payload,
        current_payload,
        changed_fields,
    )


def _normalize_section_type_data(section_type: str, type_data: Any) -> dict:
    raw_type_data = deepcopy(type_data) if isinstance(type_data, dict) else {}
    _, migrated_type_data = migrate_document_section_payload(section_type, raw_type_data)
    normalized = normalize_section_description_payload(section_type, migrated_type_data)
    return _strip_shared_section_type_data(section_type, normalized)


def merge_template_section_config_type_data(
    section_type: str,
    current_type_data: Any,
    template_type_data: Any,
) -> dict:
    merged = _normalize_section_type_data(section_type, current_type_data)
    template_config = _normalize_section_type_data(section_type, template_type_data)
    config_keys = set(get_section_design_type_data_keys(section_type))
    config_keys.add(GENERIC_SECTION_TYPE_DATA_KEY)
    if str(section_type or "").strip().lower() == "gallery":
        config_keys.add("media_tag_bindings")

    for key in config_keys:
        if key in template_config:
            merged[key] = deepcopy(template_config[key])
        else:
            merged.pop(key, None)

    return normalize_section_description_payload(section_type, merged)


def ensure_container_template_section_structure(
    section_structure: Any,
    ordered_section_ids: list[Any],
) -> list[dict[str, Any]]:
    ordered_ids: list[str] = []
    seen: set[str] = set()
    raw_ids = ordered_section_ids if isinstance(ordered_section_ids, list) else []
    for raw_id in raw_ids:
        section_id = str(raw_id or "").strip()
        if not section_id or section_id in seen:
            continue
        seen.add(section_id)
        ordered_ids.append(section_id)

    normalized_structure = resolve_section_structure(section_structure, ordered_ids)
    if len(ordered_ids) < 2:
        return normalized_structure

    container_id = ""
    for node in normalized_structure:
        if not isinstance(node, dict):
            continue
        if str(node.get("type") or "").strip().lower() != "container":
            continue
        container_id = str(node.get("container_id") or "").strip()
        if container_id:
            break

    return [
        {
            "type": "container",
            "container_id": container_id or f"container_{ObjectId()}",
            "section_ids": ordered_ids,
        }
    ]


def normalize_section_template_doc(
    section_type: str,
    template_name: str,
    payload: dict | None,
    *,
    seed_list_target_visibility_presets: bool = False,
) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    raw_mapping_payload = (
        payload.get("section_integration_mapping")
        if payload.get("section_integration_mapping") is not None
        else payload.get("sectionIntegrationMapping")
    )
    has_explicit_visibility_config = _is_hidden_list_target_visibility_config_present(
        raw_mapping_payload
    )
    normalized_section = normalize_embedded_section(
        {
            **payload,
            "section_type": section_type,
        },
        fallback_section_type=section_type,
    )
    resolved_section_type = str(normalized_section.get("section_type") or section_type).strip().lower() or "text"
    section_integration_mapping = normalize_section_integration_mapping(
        normalized_section.get("section_integration_mapping")
    )
    raw_output_mapping = (
        payload.get("section_output_mapping")
        if payload.get("section_output_mapping") is not None
        else payload.get("sectionOutputMapping")
    )
    section_output_mapping = normalize_section_output_mapping(raw_output_mapping)
    if seed_list_target_visibility_presets:
        section_integration_mapping = apply_hidden_list_target_visibility_presets(
            resolved_section_type,
            section_integration_mapping,
            visibility_config_present=has_explicit_visibility_config,
        )
    return {
        "section_type": resolved_section_type,
        "template_name": normalize_template_name(template_name, default="default"),
        "favorite": bool(payload.get("favorite", False)),
        "title_placeholder": normalized_section["title_placeholder"],
        "title": normalized_section["title"],
        "type_data": normalized_section["type_data"],
        "design_overrides": normalize_template_section_design_overrides(
            normalized_section.get("design_overrides")
        ),
        "section_integration_mapping": section_integration_mapping,
        "section_output_mapping": section_output_mapping,
    }


def normalize_container_template_doc(template_name: str, payload: dict | None) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    normalized_name = normalize_template_name(template_name)
    normalized_sections, normalized_section_structure = normalize_embedded_sections_and_structure(
        payload.get("sections"),
        payload.get("section_structure"),
    )
    ordered_ids = [
        str(section.get("id") or "").strip()
        for section in normalized_sections
        if str(section.get("id") or "").strip()
    ]
    normalized_section_structure = ensure_container_template_section_structure(
        normalized_section_structure,
        ordered_ids,
    )
    normalized_sections = apply_section_order_from_structure(
        normalized_sections,
        normalized_section_structure,
        section_id_field="id",
    )

    return {
        "template_name": normalized_name,
        "composition_name": str(payload.get("composition_name") or normalized_name).strip() or normalized_name,
        "title": payload.get("title") if isinstance(payload.get("title"), dict) else {"de": "", "en": ""},
        # Containers are sections-only compositions.
        "has_header": False,
        "header": None,
        "sections": normalized_sections,
        "section_structure": normalized_section_structure,
    }


def _normalize_template_kind(
    value: Any,
    *,
    parent_route: str | None,
    source_type: str | None,
) -> str:
    kind = str(value or "").strip().lower()
    if kind in {"static_page", "item_page"}:
        return kind
    if parent_route is not None or source_type in {"blog", "tiles", "program"}:
        return "item_page"
    return "static_page"


def _normalize_auto_match_rules(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, Any] = {}
    if "enabled" in raw:
        normalized["enabled"] = bool(raw.get("enabled"))
    if "prefer_exact_key" in raw:
        normalized["prefer_exact_key"] = bool(raw.get("prefer_exact_key"))
    if "prefer_localized_fields" in raw:
        normalized["prefer_localized_fields"] = bool(raw.get("prefer_localized_fields"))
    if isinstance(raw.get("key_aliases"), dict):
        aliases: dict[str, list[str]] = {}
        for key, value in raw.get("key_aliases", {}).items():
            key_name = str(key or "").strip()
            if not key_name:
                continue
            if isinstance(value, list):
                normalized_values = [
                    str(item).strip()
                    for item in value
                    if str(item or "").strip()
                ]
                if normalized_values:
                    aliases[key_name] = normalized_values
        if aliases:
            normalized["key_aliases"] = aliases
    return normalized


def _normalize_integration_match_mappings(raw: Any) -> list[dict]:
    mappings: list[dict] = []
    if not isinstance(raw, list):
        return mappings
    for mapping in raw:
        if not isinstance(mapping, dict):
            continue
        source_path = str(mapping.get("source_path") or "").strip()
        integration_path = str(mapping.get("integration_path") or "").strip()
        if not source_path or not integration_path:
            continue
        mappings.append(
            {
                "source_path": source_path,
                "integration_path": integration_path,
            }
        )
    return mappings


def _strip_design_snapshot_meta(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    return {
        key: value
        for key, value in payload.items()
        if key not in {"_id", "key", "revision_id", "comparison_version_id"}
    }


async def _resolve_design_version_snapshot(versions_coll, doc: dict) -> dict | None:
    return doc.get("design_settings")


def _inject_selected_units_from_admin_config(
    design_settings: dict | None,
    admin_config: dict | None,
) -> dict | None:
    if not isinstance(design_settings, dict):
        return design_settings

    result = deepcopy(design_settings)
    selected_units_raw = result.get("selected_units")
    selected_units = dict(selected_units_raw) if isinstance(selected_units_raw, dict) else {}

    parameters = admin_config.get("parameters") if isinstance(admin_config, dict) else None
    if isinstance(parameters, dict):
        for param_key, cfg in parameters.items():
            if not isinstance(param_key, str) or not param_key or param_key in selected_units:
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

    return public_config or None


async def resolve_global_published_design_snapshot(db) -> tuple[dict, str | None]:
    versions_coll = db[DESIGN_VERSIONS_COLLECTION]
    admin_doc = await db[DESIGN_EDITOR_CONFIG_COLLECTION].find_one({"key": ADMIN_CONFIG_KEY})

    published_version = await versions_coll.find_one(
        {"is_published": True},
        sort=[("published_at", -1), ("created_at", -1)],
    )
    if published_version:
        design_settings = await _resolve_design_version_snapshot(versions_coll, published_version)
        effective_design = _inject_selected_units_from_admin_config(design_settings, admin_doc)
        return (_strip_design_snapshot_meta(effective_design) or {}, str(published_version.get("_id")))

    latest_version = await versions_coll.find_one({}, sort=[("created_at", -1)])
    if latest_version:
        design_settings = await _resolve_design_version_snapshot(versions_coll, latest_version)
        effective_design = _inject_selected_units_from_admin_config(design_settings, admin_doc)
        return (_strip_design_snapshot_meta(effective_design) or {}, str(latest_version.get("_id")))

    design_doc = await db[DESIGN_CONFIG_COLLECTION].find_one({"key": "global"})
    if not isinstance(design_doc, dict):
        return ({}, None)
    effective_design = _inject_selected_units_from_admin_config(design_doc, admin_doc)
    source_id = design_doc.get("_id")
    return (_strip_design_snapshot_meta(effective_design) or {}, str(source_id) if source_id else None)


def normalize_page_template_doc(
    path: str,
    payload: dict | None,
    *,
    seed_page_target_visibility_presets: bool = False,
) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    template_name, parent_route = parse_page_template_path(path)
    explicit_template_kind = str(payload.get("template_kind") or "").strip().lower()
    source_type = str(payload.get("source_type") or "").strip().lower() or None
    if source_type not in {None, "blog", "tiles", "program"}:
        source_type = None
    source_route_ref = str(payload.get("source_route_ref") or "").strip() or None
    source_kind = str(payload.get("source_kind") or "").strip().lower() or None
    if source_kind not in {None, "item", "stage", "gig"}:
        source_kind = None
    section_template_ref = normalize_section_template_ref(payload.get("section_template_ref"))
    ref_section_type, _ = parse_section_template_ref(section_template_ref)
    if ref_section_type in {"blog", "tiles", "program"}:
        source_type = ref_section_type

    if parent_route is not None:
        is_item_page_template = True
    elif explicit_template_kind == "item_page":
        is_item_page_template = True
    elif explicit_template_kind == "static_page":
        is_item_page_template = False
    else:
        is_item_page_template = source_type in {"blog", "tiles", "program"}

    if is_item_page_template:
        source_type = source_type or "blog"
        source_context = normalize_item_page_source_context(source_type, source_kind)
        if source_context:
            source_type, source_kind = source_context
        elif source_type == "tiles":
            source_kind = "item"
        if section_template_ref is None:
            section_template_ref = normalize_section_template_ref(f"{source_type}/default")
    else:
        source_type = None
        source_kind = None
        section_template_ref = None

    raw_page_mapping_payload = payload.get("page_integration_mapping")
    has_explicit_page_visibility_config = _is_page_hidden_target_visibility_config_present(
        raw_page_mapping_payload
    )
    page_integration_mapping = resolve_page_integration_mapping_for_template_doc(
        {
            "source_type": source_type,
            "page_integration_mapping": raw_page_mapping_payload,
        }
    )
    if seed_page_target_visibility_presets:
        page_integration_mapping = apply_page_hidden_target_visibility_presets(
            page_integration_mapping,
            visibility_config_present=has_explicit_page_visibility_config,
        )
    integration_match_mappings = _normalize_integration_match_mappings(
        payload.get("integration_match_mappings")
    )
    normalized_sections, normalized_section_structure = normalize_embedded_sections_and_structure(
        payload.get("sections"),
        payload.get("section_structure"),
    )

    title = payload.get("title") if isinstance(payload.get("title"), dict) else {"de": "", "en": ""}
    menu_title = payload.get("menu_title") if isinstance(payload.get("menu_title"), dict) else None
    template_design_current = (
        deepcopy(payload.get("template_design_current"))
        if isinstance(payload.get("template_design_current"), dict)
        else None
    )
    template_design_published = (
        deepcopy(payload.get("template_design_published"))
        if isinstance(payload.get("template_design_published"), dict)
        else None
    )
    template_design_initialized_from_global_version_id = (
        str(payload.get("template_design_initialized_from_global_version_id") or "").strip() or None
    )
    template_design_updated_at = payload.get("template_design_updated_at")
    if not isinstance(template_design_updated_at, datetime):
        template_design_updated_at = None
    template_design_published_at = payload.get("template_design_published_at")
    if not isinstance(template_design_published_at, datetime):
        template_design_published_at = None
    auto_match_rules = _normalize_auto_match_rules(payload.get("auto_match_rules"))
    template_kind = _normalize_template_kind(
        payload.get("template_kind"),
        parent_route=parent_route,
        source_type=source_type,
    )
    item_page_default_status_input = payload.get("item_page_default_status")
    item_page_default_status = normalize_page_status(
        item_page_default_status_input,
        fallback="hidden",
    )
    item_page_subroute = (
        normalize_item_page_subroute(payload.get("item_page_subroute"))
        if is_item_page_template
        else ""
    )
    item_page_slug_field = (
        normalize_item_page_slug_field(source_type, source_kind, payload.get("item_page_slug_field"))
        if is_item_page_template and source_type in {"blog", "program"}
        else ""
    )
    item_page_source_section_id = (
        str(payload.get("item_page_source_section_id") or "").strip() or None
        if is_item_page_template and source_type in {"blog", "program"}
        else None
    )

    return {
        "template_name": template_name,
        "parent_route": parent_route,
        "template_kind": template_kind,
        "source_type": source_type,
        "source_kind": source_kind,
        "source_route_ref": source_route_ref,
        "section_template_ref": section_template_ref,
        "item_page_subroute": item_page_subroute,
        "item_page_slug_field": item_page_slug_field,
        "item_page_source_section_id": item_page_source_section_id,
        "page_integration_mapping": page_integration_mapping,
        "integration_match_mappings": integration_match_mappings,
        "auto_match_rules": auto_match_rules,
        "page_design_overrides": None,
        "template_design_current": template_design_current,
        "template_design_published": template_design_published,
        "template_design_initialized_from_global_version_id": template_design_initialized_from_global_version_id,
        "template_design_updated_at": template_design_updated_at,
        "template_design_published_at": template_design_published_at,
        "title": {
            "de": str(title.get("de") or ""),
            "en": str(title.get("en") or ""),
        },
        "has_header": bool(payload.get("has_header", False)),
        "header": deepcopy(payload.get("header")) if isinstance(payload.get("header"), dict) else None,
        "sections": normalized_sections,
        "section_structure": normalized_section_structure,
        "status": normalize_page_status(payload.get("status"), fallback="hidden"),
        "item_page_default_status": item_page_default_status,
        "in_menu": bool(payload.get("in_menu", False)),
        "in_footer": bool(payload.get("in_footer", False)),
        "hide_in_admin_sitemap": bool(payload.get("hide_in_admin_sitemap", True)),
        "hide_from_sitemap": bool(payload.get("hide_from_sitemap", True)),
        "hide_subtree_from_sitemap": bool(payload.get("hide_subtree_from_sitemap", True)),
        "sitemap_priority": payload.get("sitemap_priority"),
        "sitemap_changefreq": payload.get("sitemap_changefreq"),
        "menu_title": menu_title,
        "menu_order": int(payload.get("menu_order", 0) or 0),
        "footer_order": int(payload.get("footer_order", 0) or 0),
        "redirect_to": payload.get("redirect_to"),
        "section_bg_pinned_start_key": str(payload.get("section_bg_pinned_start_key") or ""),
        "section_bg_pinned_end_key": str(payload.get("section_bg_pinned_end_key") or ""),
    }


def _tokenize_path(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for part in str(path or "").split("."):
        if not part:
            continue
        while "[" in part:
            head, rest = part.split("[", 1)
            if head:
                tokens.append(head)
            idx_str, tail = rest.split("]", 1)
            if idx_str.isdigit():
                tokens.append(int(idx_str))
            if not tail:
                part = ""
                break
            if tail.startswith("."):
                part = tail[1:]
            else:
                part = tail
        if part:
            tokens.append(part)
    return tokens


def _deep_get(data: Any, path: str) -> Any:
    current = data
    for token in _tokenize_path(path):
        if isinstance(token, int):
            if not isinstance(current, list) or token < 0 or token >= len(current):
                return None
            current = current[token]
            continue
        if not isinstance(current, dict) or token not in current:
            return None
        current = current[token]
    return current


def _ensure_list_size(target: list, index: int) -> None:
    while len(target) <= index:
        target.append({})


def _deep_set(data: dict, path: str, value: Any) -> None:
    tokens = _tokenize_path(path)
    if not tokens:
        return

    current: Any = data
    for index, token in enumerate(tokens):
        is_last = index == len(tokens) - 1
        if isinstance(token, int):
            if not isinstance(current, list):
                return
            _ensure_list_size(current, token)
            if is_last:
                current[token] = deepcopy(value)
                return
            next_token = tokens[index + 1]
            if current[token] is None or not isinstance(current[token], (dict, list)):
                current[token] = [] if isinstance(next_token, int) else {}
            current = current[token]
            continue

        if not isinstance(current, dict):
            return

        if is_last:
            current[token] = deepcopy(value)
            return

        next_token = tokens[index + 1]
        if token not in current or current[token] is None or not isinstance(current[token], (dict, list)):
            current[token] = [] if isinstance(next_token, int) else {}
        current = current[token]


def _unwrap_quill_plain_block_for_review(value: Any) -> Any:
    if isinstance(value, str):
        match = QUILL_SINGLE_PLAIN_BLOCK_RE.fullmatch(value)
        if not match:
            return value
        inner = match.group(2)
        return value if HTML_TAG_RE.search(inner) else inner
    if isinstance(value, list):
        return [_unwrap_quill_plain_block_for_review(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _unwrap_quill_plain_block_for_review(nested_value)
            for key, nested_value in value.items()
        }
    return value


def normalize_item_page_sync_mode(value: Any, *, default: str = ITEM_PAGE_SYNC_MODE_KEEP_SOURCE) -> str:
    raw = str(value or "").strip().lower()
    alias_map = {
        "": default,
        "default": default,
        "keep_source": ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
        "source": ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
        "gig": ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
        "keep_gig": ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
        "keep_item": ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
        "item": ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
        "keep_local": ITEM_PAGE_SYNC_MODE_KEEP_LOCAL,
        "local": ITEM_PAGE_SYNC_MODE_KEEP_LOCAL,
    }
    normalized = alias_map.get(raw, raw)
    return normalized if normalized in ITEM_PAGE_SYNC_MODES else default


def _mapped_values_payload(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _mapped_target_values_for_page(page_doc: dict, key: str) -> dict[str, Any]:
    if not isinstance(page_doc, dict):
        return {}
    return _mapped_values_payload(page_doc.get(key))


def _mapped_values_equal(left: Any, right: Any) -> bool:
    return _normalize_source_payload_for_hash(left) == _normalize_source_payload_for_hash(right)


def _item_page_target_key(
    *,
    collection_path: str,
    target_path: str,
    resolved_target_path: str | None = None,
    source_section: dict | None = None,
    section_index: int | None = None,
    target: dict | None = None,
) -> str:
    normalized_collection = str(collection_path or "").strip()
    normalized_target = str(resolved_target_path or target_path or "").strip()
    if normalized_collection in {"page", "header"}:
        return f"{normalized_collection}.{normalized_target}"
    if normalized_collection.startswith("sections["):
        embedded_id = str(
            (source_section or {}).get("id")
            or (target or {}).get("template_section_id")
            or _extract_page_mapping_section_token(normalized_collection)
            or ""
        ).strip()
        if not embedded_id and section_index is not None:
            embedded_id = str(section_index)
        return f"sections[{embedded_id}].{normalized_target}" if embedded_id else ""
    return ""


def _is_local_mapped_conflict(
    *,
    current_value: Any,
    generated_value: Any,
    previous_generated_value: Any,
    has_previous_generated_value: bool,
) -> bool:
    if has_previous_generated_value:
        return not _mapped_values_equal(current_value, previous_generated_value)
    return current_value is not None and not _mapped_values_equal(current_value, generated_value)


def _selected_mapping_integration_id(template_doc: dict | None) -> str:
    page_mapping = resolve_page_integration_mapping_for_template_doc(template_doc or {})
    return str(page_mapping.get("selected_integration_id") or "").strip()


async def _load_selected_mapping_integration_primary_key_path(db, template_doc: dict | None) -> str:
    integration_id = _selected_mapping_integration_id(template_doc)
    integration_oid = _safe_object_id(integration_id)
    if integration_oid is None:
        return ""
    integration_doc = await db["integration_config"].find_one(
        {"_id": integration_oid},
        {"output_primary_key_path": 1},
    )
    if not isinstance(integration_doc, dict):
        return ""
    return str(integration_doc.get("output_primary_key_path") or "").strip()


async def _integration_item_page_sync_blocked(db, integration_id: Any) -> bool:
    normalized_integration_id = str(integration_id or "").strip()
    integration_oid = _safe_object_id(normalized_integration_id)
    if integration_oid is None:
        return False
    integration_doc = await db["integration_config"].find_one(
        {"_id": integration_oid},
        {"item_page_sync_blocked": 1},
    )
    return bool(isinstance(integration_doc, dict) and integration_doc.get("item_page_sync_blocked", False))


async def _load_integration_schema_page_slug_path(db, integration_id: Any) -> str:
    normalized_id = str(integration_id or "").strip()
    if not normalized_id:
        return ""
    schema_doc = await db["integration_schemas"].find_one(
        {"integration_id": normalized_id},
        {
            "page_slug_path": 1,
            "detected_fields": 1,
            "manual_types": 1,
            "collect_options": 1,
            "cache_media": 1,
            "required_fields": 1,
        },
    )
    if not isinstance(schema_doc, dict):
        return ""
    page_slug_path = normalize_review_field_path(schema_doc.get("page_slug_path"))
    if not page_slug_path:
        return ""
    schema_paths: set[str] = set()
    for key in ("detected_fields", "manual_types", "collect_options", "cache_media", "required_fields"):
        raw_map = schema_doc.get(key)
        if not isinstance(raw_map, dict):
            continue
        schema_paths.update(
            path
            for path in (normalize_review_field_path(raw_path) for raw_path in raw_map.keys())
            if path
        )
    return page_slug_path if page_slug_path in schema_paths else ""


def _is_page_slug_storage_path(path: Any) -> bool:
    normalized = normalize_review_field_path(path)
    if not normalized:
        return False
    last_segment = str(normalized.split(".")[-1] or "").strip()
    normalized_last = _path_to_snake(last_segment).lower()
    return normalized_last in {"page_slug", "slug"}


def _page_slug_write_path_for_schema_path(path: Any) -> str:
    source_path = normalize_review_field_path(path)
    if not source_path:
        return ""
    if _is_page_slug_storage_path(source_path):
        return source_path
    return ""


async def _load_integration_page_slug_write_path(db, integration_id: Any) -> str:
    page_slug_path = await _load_integration_schema_page_slug_path(db, integration_id)
    return _page_slug_write_path_for_schema_path(page_slug_path)


def _slug_values_equivalent(left: Any, right: Any) -> bool:
    left_text = _stringify_slug_source_field_value(left)
    right_text = _stringify_slug_source_field_value(right)
    if not left_text or not right_text:
        return False
    try:
        return normalize_slug(left_text) == normalize_slug(right_text)
    except Exception:
        return left_text.strip().strip("/") == right_text.strip().strip("/")


async def _cleanup_legacy_page_slug_source_override(
    db,
    *,
    integration_id: Any,
    item_key: Any,
    slug: Any,
) -> bool:
    normalized_integration_id = str(integration_id or "").strip()
    normalized_item_key = str(item_key or "").strip()
    normalized_slug = str(slug or "").strip()
    if not normalized_integration_id or not normalized_item_key or not normalized_slug:
        return False

    page_slug_path = await _load_integration_schema_page_slug_path(db, normalized_integration_id)
    write_path = _page_slug_write_path_for_schema_path(page_slug_path)
    if not page_slug_path or not write_path or page_slug_path == write_path:
        return False

    overrides_coll = db["integration_item_overrides"]
    existing = await overrides_coll.find_one(
        {
            "integration_id": normalized_integration_id,
            "item_key": normalized_item_key,
            "field_path": page_slug_path,
        }
    )
    if not isinstance(existing, dict):
        return False
    if not _slug_values_equivalent(existing.get("local_value"), normalized_slug):
        return False

    result = await overrides_coll.delete_one({"_id": existing.get("_id")})
    return bool(getattr(result, "deleted_count", 0))


async def _resolve_integration_review_locator_for_mapping(
    db,
    *,
    template_doc: dict,
    integration_payload: dict | None,
) -> tuple[str, str, dict | None]:
    integration_id = _selected_mapping_integration_id(template_doc)
    if not integration_id or not isinstance(integration_payload, dict):
        return "", "", None

    integration_oid = _safe_object_id(integration_id)
    if integration_oid is None:
        return "", "", None
    integration_doc = await db["integration_config"].find_one({"_id": integration_oid})
    if not isinstance(integration_doc, dict):
        return "", "", None

    output_primary_key_path = str(integration_doc.get("output_primary_key_path") or "").strip()
    item_key = (
        review_item_key_for_row(integration_payload, output_primary_key_path)
        if output_primary_key_path
        else REVIEW_ROOT_ITEM_KEY
    )
    return integration_id, item_key, integration_doc


async def _write_integration_review_page_slug_override(
    db,
    *,
    integration_id: str,
    item_key: str,
    slug: str,
    integration_doc: dict | None = None,
    warning_collector: list[dict] | None = None,
    source_id: str | None = None,
    source_type: str | None = None,
) -> bool:
    normalized_integration_id = str(integration_id or "").strip()
    normalized_item_key = str(item_key or "").strip()
    normalized_slug = str(slug or "").strip()
    if not normalized_integration_id or not normalized_item_key or not normalized_slug:
        return False

    page_slug_path = await _load_integration_schema_page_slug_path(db, normalized_integration_id)
    page_slug_write_path = _page_slug_write_path_for_schema_path(page_slug_path)
    if not page_slug_write_path:
        return False

    resolved_integration_doc = integration_doc
    if not isinstance(resolved_integration_doc, dict):
        integration_oid = _safe_object_id(normalized_integration_id)
        resolved_integration_doc = (
            await db["integration_config"].find_one({"_id": integration_oid})
            if integration_oid is not None
            else None
        )
    if not isinstance(resolved_integration_doc, dict):
        return False

    try:
        await upsert_integration_review_override(
            db,
            integration_id=normalized_integration_id,
            item_key=normalized_item_key,
            field_path=page_slug_write_path,
            value=normalized_slug,
            integration_doc=resolved_integration_doc,
        )
    except IntegrationReviewError as exc:
        _append_sync_warning(
            warning_collector,
            code="integration_review_page_slug_write_failed",
            message=str(exc),
            source_id=source_id,
            source_type=source_type,
        )
        return False

    await _cleanup_legacy_page_slug_source_override(
        db,
        integration_id=normalized_integration_id,
        item_key=normalized_item_key,
        slug=normalized_slug,
    )
    return True


async def _sync_integration_review_page_slug_for_mapping(
    db,
    *,
    template_doc: dict,
    integration_payload: dict | None,
    slug: str,
    warning_collector: list[dict] | None = None,
    source_id: str | None = None,
    source_type: str | None = None,
) -> tuple[str, str]:
    integration_id, item_key, integration_doc = await _resolve_integration_review_locator_for_mapping(
        db,
        template_doc=template_doc,
        integration_payload=integration_payload,
    )
    if integration_id and item_key:
        await _write_integration_review_page_slug_override(
            db,
            integration_id=integration_id,
            item_key=item_key,
            slug=slug,
            integration_doc=integration_doc,
            warning_collector=warning_collector,
            source_id=source_id,
            source_type=source_type,
        )
    return integration_id, item_key


async def _resolve_integration_page_slug_for_mapping(
    db,
    *,
    template_doc: dict,
    integration_payload: dict | None,
    parent_route: str | None = None,
) -> str:
    integration_id = _selected_mapping_integration_id(template_doc)
    if not integration_id or not isinstance(integration_payload, dict):
        return ""
    page_slug_path = await _load_integration_schema_page_slug_path(db, integration_id)
    if not page_slug_path:
        return ""
    raw_value = _deep_get(integration_payload, page_slug_path)
    slug_value = _stringify_slug_source_field_value(raw_value)
    if not slug_value:
        return ""
    normalized_slug = normalize_slug(slug_value)
    if not normalized_slug:
        return ""
    if "/" in normalized_slug:
        return normalized_slug
    return _compose_slug_with_parent_route(parent_route or "", normalized_slug)


async def sync_generated_item_page_integration_page_slug(db, page_doc: dict) -> bool:
    if not isinstance(page_doc, dict) or page_doc.get("template_managed") is not True:
        return False
    slug = str(page_doc.get("slug") or "").strip()
    if not slug:
        return False

    template_doc = await _resolve_template_doc_for_generated_page(db, page_doc)
    if not isinstance(template_doc, dict) or _item_page_mapping_uses_shared_items(template_doc):
        return False

    stored_integration_id = str(page_doc.get("template_integration_id") or "").strip()
    stored_item_key = str(page_doc.get("template_integration_item_key") or "").strip()
    if stored_integration_id and stored_item_key:
        return await _write_integration_review_page_slug_override(
            db,
            integration_id=stored_integration_id,
            item_key=stored_item_key,
            slug=slug,
            source_id=str(page_doc.get("template_source_id") or ""),
            source_type=str(page_doc.get("template_source_type") or ""),
        )

    source_payload = await _resolve_source_payload_for_generated_page(db, page_doc)
    if not isinstance(source_payload, dict):
        return False

    warnings: list[dict] = []
    source_id = str(page_doc.get("template_source_id") or "")
    source_type = str(page_doc.get("template_source_type") or "")
    integration_rows = await _load_integration_rows_for_template(
        db,
        template_doc,
        warning_collector=warnings,
        source_id=source_id,
        source_type=source_type,
    )
    integration_payload = _resolve_integration_row_for_source(
        template_doc,
        source_payload,
        integration_rows,
        warning_collector=warnings,
        source_id=source_id,
        source_type=source_type,
    )
    if not isinstance(integration_payload, dict):
        return False

    integration_id, item_key = await _sync_integration_review_page_slug_for_mapping(
        db,
        template_doc=template_doc,
        integration_payload=integration_payload,
        slug=slug,
        warning_collector=warnings,
        source_id=source_id,
        source_type=source_type,
    )
    if integration_id and item_key:
        await db["pages"].update_one(
            {"_id": page_doc.get("_id")},
            {
                "$set": {
                    "template_integration_id": integration_id,
                    "template_integration_item_key": item_key,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return True
    return False


def _source_payload_from_blog_item(item_doc: dict) -> dict:
    title = item_doc.get("title") if isinstance(item_doc.get("title"), dict) else {"de": "", "en": ""}
    text = item_doc.get("text") if isinstance(item_doc.get("text"), dict) else {"de": "", "en": ""}
    tag = item_doc.get("tag") if isinstance(item_doc.get("tag"), dict) else {"de": "", "en": ""}
    image_url = str(item_doc.get("image_url") or "")
    page_slug = str(item_doc.get("page_slug") or "")
    payload = {
        "id": str(item_doc.get("_id") or ""),
        "date": str(item_doc.get("date") or ""),
        "title": {"de": str(title.get("de") or ""), "en": str(title.get("en") or "")},
        "text": {"de": str(text.get("de") or ""), "en": str(text.get("en") or "")},
        "tag": {"de": str(tag.get("de") or ""), "en": str(tag.get("en") or "")},
        "image_url": image_url,
        "image_zoom": item_doc.get("image_zoom", 1.0),
        "image_focal_x": item_doc.get("image_focal_x", 50.0),
        "image_focal_y": item_doc.get("image_focal_y", 50.0),
        "image_rotation": item_doc.get("image_rotation", 0.0),
        "page_slug": page_slug,
    }
    return payload


def _blog_preview_item_label(item_doc: dict | None) -> dict:
    if not isinstance(item_doc, dict):
        return {}
    title = item_doc.get("title") if isinstance(item_doc.get("title"), dict) else {"de": "", "en": ""}
    return {
        "title": {
            "de": str(title.get("de") or title.get("en") or "").strip(),
            "en": str(title.get("en") or title.get("de") or "").strip(),
        },
        "date": str(item_doc.get("date") or "").strip(),
    }


def _blog_item_for_preview_selection(
    items: list[dict],
    *,
    preview_item_key: str | None = None,
    preview_item_index: int | None = None,
) -> tuple[dict | None, int | None]:
    normalized_preview_key = str(preview_item_key or "").strip()
    normalized_items = [item for item in items if isinstance(item, dict)]
    if not normalized_items:
        return None, None
    if normalized_preview_key:
        for index, item in enumerate(normalized_items):
            if str(item.get("_id") or "").strip() == normalized_preview_key:
                return item, index
    if preview_item_index is not None and 0 <= preview_item_index < len(normalized_items):
        return normalized_items[preview_item_index], preview_item_index
    return normalized_items[0], 0


def _source_payload_from_tile(section_doc: dict, tile: dict) -> dict:
    title = (
        tile.get("title")
        if isinstance(tile.get("title"), dict)
        else tile.get("overlay_text")
        if isinstance(tile.get("overlay_text"), dict)
        else {"de": "", "en": ""}
    )
    subtitle = (
        tile.get("subtitle")
        if isinstance(tile.get("subtitle"), dict)
        else tile.get("genre")
        if isinstance(tile.get("genre"), dict)
        else tile.get("genre_text")
        if isinstance(tile.get("genre_text"), dict)
        else {"de": "", "en": ""}
    )
    detail = (
        tile.get("description")
        if isinstance(tile.get("description"), dict)
        else tile.get("detail_text")
        if isinstance(tile.get("detail_text"), dict)
        else {"de": "", "en": ""}
    )
    page_slug = str(tile.get("page_slug") or "")
    image_url = str(tile.get("image_url") or "")
    location = str(
        tile.get("location")
        or tile.get("stage")
        or tile.get("stage_text")
        or ""
    )
    time = str(tile.get("time") or tile.get("time_text") or "")
    payload = {
        "id": str(tile.get("id") or ""),
        "section_id": str(section_doc.get("_id") or ""),
        "title": {"de": str(title.get("de") or ""), "en": str(title.get("en") or "")},
        "subtitle": {"de": str(subtitle.get("de") or ""), "en": str(subtitle.get("en") or "")},
        "location": location,
        "genre": {"de": str(subtitle.get("de") or ""), "en": str(subtitle.get("en") or "")},
        "description": {"de": str(detail.get("de") or ""), "en": str(detail.get("en") or "")},
        "overlay_text": {"de": str(title.get("de") or ""), "en": str(title.get("en") or "")},
        "genre_text": {"de": str(subtitle.get("de") or ""), "en": str(subtitle.get("en") or "")},
        "detail_text": {"de": str(detail.get("de") or ""), "en": str(detail.get("en") or "")},
        "image_url": image_url,
        "zoom": tile.get("zoom", tile.get("image_zoom", 1.0)),
        "focal_x": tile.get("focal_x", 50.0),
        "focal_y": tile.get("focal_y", 50.0),
        "rotation": tile.get("rotation", 0.0),
        "stage": location,
        "time": time,
        "page_slug": page_slug,
    }
    return payload


def _to_bilingual_payload(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        de = str(value.get("de") or value.get("en") or "").strip()
        en = str(value.get("en") or value.get("de") or "").strip()
        return {"de": de, "en": en}
    text = str(value or "").strip()
    return {"de": text, "en": text}


def _has_bilingual_text(value: dict[str, str] | None) -> bool:
    if not isinstance(value, dict):
        return False
    return bool(str(value.get("de") or "").strip() or str(value.get("en") or "").strip())


_PROGRAM_GIG_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PROGRAM_GIG_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_PROGRAM_GIG_DATETIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[T\s](\d{2}:\d{2})")
_PROGRAM_GIG_TZ_SUFFIX_RE = re.compile(r"(Z|[+-]\d{2}:\d{2})$", re.IGNORECASE)
_BERLIN_TZ = ZoneInfo("Europe/Berlin")


def _datetime_to_berlin_wall_value(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(_BERLIN_TZ)
    return value.strftime("%Y-%m-%dT%H:%M")


def _normalize_program_gig_datetime_value(value: Any) -> str:
    if isinstance(value, datetime):
        return _datetime_to_berlin_wall_value(value)
    raw = str(value or "").strip()
    if not raw:
        return ""
    if _PROGRAM_GIG_TZ_SUFFIX_RE.search(raw):
        try:
            normalized_raw = f"{raw[:-1]}+00:00" if raw.lower().endswith("z") else raw
            parsed = datetime.fromisoformat(normalized_raw)
            return _datetime_to_berlin_wall_value(parsed)
        except ValueError:
            return ""
    match = _PROGRAM_GIG_DATETIME_RE.match(raw)
    if not match:
        return ""
    return f"{match.group(1)}T{match.group(2)}"


def _compose_program_gig_datetime_value(day_value: Any, time_value: Any) -> str:
    day = str(day_value or "").strip()
    time = str(time_value or "").strip()
    if not _PROGRAM_GIG_DAY_RE.fullmatch(day):
        return ""
    if not _PROGRAM_GIG_TIME_RE.fullmatch(time):
        return ""
    return f"{day}T{time}"


def _split_program_gig_datetime_value(value: str) -> tuple[str, str]:
    match = _PROGRAM_GIG_DATETIME_RE.match(str(value or "").strip())
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def _normalize_source_payload_row(value: Any) -> dict:
    source = value.model_dump() if hasattr(value, "model_dump") else value
    if not isinstance(source, dict):
        return {}
    normalized, _stats = normalize_keys_to_snake(source)
    return normalized if isinstance(normalized, dict) else {}


def _source_payload_from_program_stage(stage: dict) -> dict:
    stage = _normalize_source_payload_row(stage)
    title = _to_bilingual_payload(stage.get("name"))
    if not _has_bilingual_text(title):
        title = _to_bilingual_payload(stage.get("title"))
    description = _to_bilingual_payload(stage.get("description"))
    image_url = str(stage.get("image_url") or "").strip()
    payload = {
        **deepcopy(stage),
        "id": str(stage.get("id") or "").strip(),
        "title": title,
        "name": title,
        "subtitle": {"de": "", "en": ""},
        "description": description,
        "image_url": image_url,
        "color": str(stage.get("color") or "").strip(),
        "page_slug": str(stage.get("page_slug") or "").strip(),
        "item_url": str(stage.get("item_url") or "").strip(),
    }
    return payload


def _normalize_program_stage_lookup_key(value: Any) -> str:
    payload = _to_bilingual_payload(value)
    raw = str(payload.get("de") or payload.get("en") or value or "").strip().lower()
    if not raw:
        return ""
    normalized = unicodedata.normalize("NFD", raw)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def normalize_program_stage_lookup_key(value: Any) -> str:
    return _normalize_program_stage_lookup_key(value)


def build_program_stage_titles_lookup(stages: list[dict]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for raw_stage in (stages if isinstance(stages, list) else []):
        stage = _normalize_source_payload_row(raw_stage)
        stage_id = str(stage.get("id") or "").strip()
        if not stage_id:
            continue
        title = _to_bilingual_payload(stage.get("name"))
        if not _has_bilingual_text(title):
            title = _to_bilingual_payload(stage.get("title"))
        aliases = [
            stage_id,
            stage.get("name"),
            stage.get("title"),
            title.get("de"),
            title.get("en"),
        ]
        for alias in aliases:
            if alias is None:
                continue
            exact_key = str(alias).strip() if not isinstance(alias, dict) else ""
            if exact_key:
                lookup.setdefault(exact_key, title)
            normalized_key = _normalize_program_stage_lookup_key(alias)
            if normalized_key:
                lookup.setdefault(normalized_key, title)
    return lookup


def _source_payload_from_program_gig(
    gig: dict,
    *,
    stage_titles_by_id: dict[str, dict[str, str]] | None = None,
) -> dict:
    gig = _normalize_source_payload_row(gig)
    title = _to_bilingual_payload(gig.get("title"))
    if not _has_bilingual_text(title):
        title = _to_bilingual_payload(gig.get("artist_name"))
    subtitle = _to_bilingual_payload(gig.get("genre"))
    description = _to_bilingual_payload(gig.get("description"))
    stage_id = str(gig.get("stage") or "").strip()
    stage_title_source = None
    if stage_id and isinstance(stage_titles_by_id, dict):
        stage_title_source = stage_titles_by_id.get(stage_id)
        if stage_title_source is None:
            stage_title_source = stage_titles_by_id.get(_normalize_program_stage_lookup_key(stage_id))
    stage_title = _to_bilingual_payload(stage_title_source)
    if not _has_bilingual_text(stage_title) and stage_id:
        stage_title = _to_bilingual_payload(stage_id)
    fallback_day = str(gig.get("day") or "").strip()
    start_value = (
        _normalize_program_gig_datetime_value(gig.get("start"))
        or _compose_program_gig_datetime_value(fallback_day, gig.get("start_time"))
    )
    end_value = (
        _normalize_program_gig_datetime_value(gig.get("end"))
        or _compose_program_gig_datetime_value(fallback_day, gig.get("end_time"))
    )

    day_value, start_time = _split_program_gig_datetime_value(start_value)
    if not day_value:
        day_value = fallback_day
    if not start_time:
        start_time = str(gig.get("start_time") or "").strip()
    if not end_value and day_value and str(gig.get("end_time") or "").strip():
        end_value = _compose_program_gig_datetime_value(day_value, gig.get("end_time"))
    _, end_time = _split_program_gig_datetime_value(end_value)
    if not end_time:
        end_time = str(gig.get("end_time") or "").strip()

    previous_fallback_day = str(gig.get("previous_day") or day_value).strip()
    previous_start_value = (
        _normalize_program_gig_datetime_value(gig.get("previous_start"))
        or _compose_program_gig_datetime_value(previous_fallback_day, gig.get("previous_start_time"))
    )
    previous_end_value = (
        _normalize_program_gig_datetime_value(gig.get("previous_end"))
        or _compose_program_gig_datetime_value(previous_fallback_day, gig.get("previous_end_time"))
    )
    previous_day_value, previous_start_time = _split_program_gig_datetime_value(previous_start_value)
    if not previous_day_value:
        previous_day_value = previous_fallback_day
    if not previous_start_time:
        previous_start_time = str(gig.get("previous_start_time") or "").strip()
    _, previous_end_time = _split_program_gig_datetime_value(previous_end_value)
    if not previous_end_time:
        previous_end_time = str(gig.get("previous_end_time") or "").strip()

    time_value = ""
    if start_time and end_time:
        time_value = f"{start_time} - {end_time}"
    elif start_time:
        time_value = start_time
    payload = {
        **deepcopy(gig),
        "id": str(gig.get("id") or "").strip(),
        "title": title,
        "artist_name": title,
        "subtitle": subtitle,
        "genre": subtitle,
        "description": description,
        "gig_type": str(gig.get("gig_type") or "").strip(),
        "start": start_value,
        "end": end_value,
        "day": day_value,
        "date": day_value,
        "start_time": start_time,
        "end_time": end_time,
        "stage": stage_id,
        "stage_title": stage_title,
        "location": stage_title,
        "time": time_value,
        "image_url": str(gig.get("image_url") or "").strip(),
        "image_zoom": gig.get("image_zoom", 1.0),
        "image_focal_x": gig.get("image_focal_x", 50.0),
        "image_focal_y": gig.get("image_focal_y", 50.0),
        "image_rotation": gig.get("image_rotation", 0.0),
        "page_slug": str(gig.get("page_slug") or "").strip(),
        "item_url": str(gig.get("item_url") or "").strip(),
        "register_changes": bool(gig.get("register_changes", False)),
        "highlight_changes": bool(gig.get("highlight_changes", False)),
        "canceled": bool(gig.get("canceled", False)),
        "previous_start": previous_start_value,
        "previous_end": previous_end_value,
        "previous_day": previous_day_value,
        "previous_start_time": previous_start_time,
        "previous_end_time": previous_end_time,
        "previous_stage": str(gig.get("previous_stage") or "").strip(),
    }
    return payload


_SOURCE_PAYLOAD_HASH_IGNORED_KEYS = {
    "id",
    "page_slug",
    "item_url",
    "integration_item_key",
    "integrationItemKey",
    "template_integration_item_key",
    "review_item_key",
    "reviewItemKey",
    "_item_index",
    "__integration_source_id",
}


def _normalize_source_payload_for_hash(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_source_payload_for_hash(item) for item in value]
    if not isinstance(value, dict):
        return value

    normalized: dict[str, Any] = {}
    for key, nested_value in value.items():
        normalized_key = str(key or "")
        if normalized_key in _SOURCE_PAYLOAD_HASH_IGNORED_KEYS:
            continue
        if normalized_key.startswith("item_page_"):
            continue
        normalized[normalized_key] = _normalize_source_payload_for_hash(nested_value)
    return normalized


def _compute_source_payload_hash(payload: dict | None) -> str:
    normalized_payload = _normalize_source_payload_for_hash(payload if isinstance(payload, dict) else {})
    encoded = json.dumps(
        normalized_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _compute_item_page_source_payload_hash(
    source_payload: dict | None,
    integration_payload: dict | None = None,
) -> str:
    payload: dict[str, Any] = {
        "item": source_payload if isinstance(source_payload, dict) else {},
    }
    if isinstance(integration_payload, dict):
        payload["integration"] = integration_payload
    return _compute_source_payload_hash(payload)


def build_program_stage_item_page_source_hash(stage: dict) -> str:
    return _compute_source_payload_hash(_source_payload_from_program_stage(stage))


def build_program_gig_item_page_source_hash(
    gig: dict,
    *,
    stage_titles_by_id: dict[str, dict[str, str]] | None = None,
) -> str:
    return _compute_source_payload_hash(
        _source_payload_from_program_gig(
            gig,
            stage_titles_by_id=stage_titles_by_id,
        )
    )


async def build_program_item_page_source_hashes_for_freshness(
    db,
    *,
    kind: str,
    rows: list[dict],
    stage_titles_by_id: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    normalized_kind = "stage" if str(kind or "").strip().lower() == "stage" else "gig"
    active_template = await resolve_active_item_page_template(
        db,
        "program",
        normalized_kind,
    )
    template_doc = active_template.get("template") if isinstance(active_template, dict) else None
    integration_rows = (
        await _load_integration_rows_for_template(
            db,
            template_doc,
            source_type="program",
        )
        if isinstance(template_doc, dict)
        else []
    )
    source_type = "program_stage" if normalized_kind == "stage" else "program_gig"
    hashes: dict[str, str] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("id") or "").strip()
        if not item_id:
            continue
        source_id = f"program:{normalized_kind}:{item_id}"
        source_payload = (
            _source_payload_from_program_stage(row)
            if normalized_kind == "stage"
            else _source_payload_from_program_gig(
                row,
                stage_titles_by_id=stage_titles_by_id,
            )
        )
        integration_payload = (
            _resolve_integration_row_for_source(
                template_doc,
                source_payload,
                integration_rows,
                source_id=source_id,
                source_type=source_type,
            )
            if isinstance(template_doc, dict)
            else None
        )
        hashes[source_id] = _compute_item_page_source_payload_hash(
            source_payload,
            integration_payload if isinstance(integration_payload, dict) else None,
        )
    return hashes

def _append_sync_warning(
    warning_collector: list[dict] | None,
    *,
    code: str,
    message: str,
    source_id: str | None = None,
    source_type: str | None = None,
    source_path: str | None = None,
    integration_path: str | None = None,
    template_name: str | None = None,
    parent_route: str | None = None,
) -> None:
    if warning_collector is None:
        return
    if len(warning_collector) >= 200:
        return
    warning: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if source_id:
        warning["source_id"] = source_id
    if source_type:
        warning["source_type"] = source_type
    if source_path:
        warning["source_path"] = source_path
    if integration_path:
        warning["integration_path"] = integration_path
    if template_name:
        warning["template_name"] = template_name
    if parent_route:
        warning["parent_route"] = parent_route
    warning_collector.append(warning)


def _is_scalar_value(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def _values_match(left: Any, right: Any) -> bool:
    if left == right:
        return True

    def _collect_scalar_candidates(value: Any, *, depth: int = 0) -> list[str]:
        if depth > 3:
            return []
        if _is_scalar_value(value):
            return [str(value).strip().lower()]
        if isinstance(value, dict):
            candidates: list[str] = []
            if "de" in value:
                candidates.extend(_collect_scalar_candidates(value.get("de"), depth=depth + 1))
            if "en" in value:
                candidates.extend(_collect_scalar_candidates(value.get("en"), depth=depth + 1))
            if candidates:
                return [candidate for candidate in candidates if candidate]
            for nested in value.values():
                candidates.extend(_collect_scalar_candidates(nested, depth=depth + 1))
            return [candidate for candidate in candidates if candidate]
        if isinstance(value, list):
            candidates: list[str] = []
            for nested in value:
                candidates.extend(_collect_scalar_candidates(nested, depth=depth + 1))
            return [candidate for candidate in candidates if candidate]
        return []

    left_candidates = _collect_scalar_candidates(left)
    right_candidates = _collect_scalar_candidates(right)
    if not left_candidates or not right_candidates:
        return False
    right_set = set(right_candidates)
    return any(candidate in right_set for candidate in left_candidates)


def _strip_mapping_item_prefix(source_path: str) -> str:
    normalized = str(source_path or "").strip()
    if normalized.startswith("item."):
        return normalized[5:]
    return normalized


def _strip_mapping_integration_prefix(integration_path: str) -> str:
    normalized = str(integration_path or "").strip()
    if normalized.startswith("integration."):
        return normalized[12:]
    return normalized


def _path_token_to_snake(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", raw)
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized)
    return normalized.replace("-", "_").lower()


def _path_to_snake(value: Any) -> str:
    tokens = _tokenize_path(str(value or "").strip())
    if not tokens:
        return ""
    parts: list[str] = []
    for token in tokens:
        if isinstance(token, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{token}]"
            continue
        normalized_token = _path_token_to_snake(token)
        if normalized_token:
            parts.append(normalized_token)
    return ".".join(parts)


def _strip_collection_prefix_from_mapping_path(path: Any, collection_path: Any = "") -> str:
    normalized = str(path or "").strip()
    if not normalized:
        return ""
    normalized = re.sub(r"^\$root\.", "", normalized)

    collection_tokens = [
        token
        for token in _tokenize_path(str(collection_path or "").strip())
        if isinstance(token, str)
    ]
    collection_name = str(collection_tokens[-1] if collection_tokens else "").strip()
    collection_candidates = [collection_name] if collection_name else []
    if collection_name == "gigs":
        collection_candidates.append("gig")
    elif collection_name == "stages":
        collection_candidates.append("stage")
    else:
        collection_candidates.extend(["gigs", "stages"])

    for candidate in collection_candidates:
        if not candidate:
            continue
        normalized = re.sub(
            rf"^{re.escape(candidate)}(?:\[(?:\*|\d+)\])?\.",
            "",
            normalized,
            flags=re.IGNORECASE,
        )
    return normalized


def _mapping_source_signature(path: Any, collection_path: Any = "") -> str:
    normalized = _strip_collection_prefix_from_mapping_path(path, collection_path)
    return _path_to_snake(normalized)


def _snake_key_to_camel(value: str) -> str:
    return re.sub(r"_([a-z])", lambda match: match.group(1).upper(), value)


def _source_payload_path_value(source_payload: dict, path: Any, *, collection_path: Any = "") -> Any:
    normalized_path = _strip_collection_prefix_from_mapping_path(path, collection_path)
    for candidate in (
        normalized_path,
        _path_to_snake(normalized_path),
    ):
        if not candidate:
            continue
        value = _deep_get(source_payload, candidate)
        if value is not None:
            return value
    return None


def _resolve_mapping_source_value_from_item_integration_mapping(
    source_path: str,
    source_payload: dict,
    item_integration_mapping: dict | None,
) -> Any:
    mapping = _normalize_section_integration_mapping_payload(item_integration_mapping)
    list_mappings_by_collection_path = mapping.get("list_mappings_by_collection_path")
    if not isinstance(list_mappings_by_collection_path, dict):
        return None

    normalized_source_path = _strip_mapping_integration_prefix(source_path)
    for collection_path, rows in list_mappings_by_collection_path.items():
        if not isinstance(rows, list):
            continue
        source_signature = _mapping_source_signature(
            normalized_source_path,
            collection_path,
        )
        if not source_signature:
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_source_signature = _mapping_source_signature(
                row.get("source_path"),
                collection_path,
            )
            if row_source_signature != source_signature:
                continue
            value = _source_payload_path_value(
                source_payload,
                row.get("target_path"),
                collection_path=collection_path,
            )
            if value is not None:
                return value
    return None


def _resolve_mapping_source_value(
    source_path: str,
    source_payload: dict,
    integration_payload: dict | None,
    item_integration_mapping: dict | None = None,
) -> Any:
    normalized = str(source_path or "").strip()
    if not normalized:
        return None
    if normalized.startswith("item."):
        return _source_payload_path_value(source_payload, normalized[5:])
    if normalized.startswith("integration."):
        if not isinstance(integration_payload, dict):
            return None
        return _deep_get(integration_payload, normalized[12:])
    return _source_payload_path_value(source_payload, normalized)


def _source_payload_item_index(source_payload: dict) -> int | None:
    if not isinstance(source_payload, dict):
        return None
    for key in ("_item_index", "_source_index", "item_index", "source_index"):
        try:
            index = int(source_payload.get(key))
        except Exception:
            continue
        if index >= 0:
            return index
    return None


def _integration_row_for_source_index(
    source_payload: dict,
    integration_rows: list[dict],
) -> dict | None:
    source_index = _source_payload_item_index(source_payload)
    if source_index is None:
        return None
    if source_index < 0 or source_index >= len(integration_rows):
        return None
    row = integration_rows[source_index]
    return row if isinstance(row, dict) else None


def _normalize_integration_rows(raw_data: Any) -> list[dict]:
    if isinstance(raw_data, list):
        return [row for row in raw_data if isinstance(row, dict)]
    if isinstance(raw_data, dict):
        return [raw_data]
    return []


def _find_template_section_index_by_embedded_id(
    sections_payload: Any,
    embedded_id: Any,
) -> int | None:
    token = _normalize_page_mapping_section_token(embedded_id)
    if not token or _is_numeric_page_mapping_section_token(token):
        return None
    sections = sections_payload if isinstance(sections_payload, list) else []
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        section_id = _normalize_page_mapping_section_token(section.get("id"))
        if section_id and section_id == token:
            return index
    return None


def _section_supports_page_mapping_target_path(
    section_payload: Any,
    target_path: Any,
) -> bool:
    if not isinstance(section_payload, dict):
        return False
    normalized_target_path = str(target_path or "").strip()
    if not normalized_target_path:
        return False
    resolved_target_path = _resolve_links_social_target_path(
        section_payload,
        normalized_target_path,
    )
    if not resolved_target_path:
        return False
    return _deep_get(section_payload, resolved_target_path) is not None


def _infer_page_mapping_section_index_by_target_path(
    sections_payload: Any,
    target_path: Any,
) -> int | None:
    sections = sections_payload if isinstance(sections_payload, list) else []
    matches: list[int] = []
    for index, section in enumerate(sections):
        if _section_supports_page_mapping_target_path(section, target_path):
            matches.append(index)
    return matches[0] if len(matches) == 1 else None


def _resolve_page_mapping_section_index(
    sections_payload: Any,
    collection_path: Any,
    mapping_row: Any = None,
) -> int | None:
    row_section_id = _normalize_page_mapping_row_template_section_id(
        mapping_row,
        collection_path,
    )
    resolved_by_row = _find_template_section_index_by_embedded_id(
        sections_payload,
        row_section_id,
    )
    if resolved_by_row is not None:
        return resolved_by_row

    collection_token = _extract_page_mapping_section_token(collection_path)
    resolved_by_collection = _find_template_section_index_by_embedded_id(
        sections_payload,
        collection_token,
    )
    if resolved_by_collection is not None:
        return resolved_by_collection

    if not _is_numeric_page_mapping_section_token(collection_token):
        return None
    row_payload = mapping_row if isinstance(mapping_row, dict) else {}
    target_path = _normalize_page_mapping_target_path_for_collection(
        collection_path,
        row_payload.get("target_path"),
    )
    inferred_by_target = _infer_page_mapping_section_index_by_target_path(
        sections_payload,
        target_path,
    )
    if inferred_by_target is not None:
        return inferred_by_target
    section_index = int(collection_token)
    sections = sections_payload if isinstance(sections_payload, list) else []
    if section_index < 0 or section_index >= len(sections):
        return None
    return section_index


async def _load_integration_rows_for_template(
    db,
    template_doc: dict,
    *,
    warning_collector: list[dict] | None = None,
    source_id: str | None = None,
    source_type: str | None = None,
) -> list[dict]:
    if _item_page_mapping_uses_shared_items(template_doc):
        return []

    page_mapping = resolve_page_integration_mapping_for_template_doc(template_doc)
    integration_id = str(page_mapping.get("selected_integration_id") or "").strip()
    if not integration_id:
        _append_sync_warning(
            warning_collector,
            code="integration_missing_reference",
            message="Template has no selected integration configured.",
            source_id=source_id,
            source_type=source_type,
            template_name=str(template_doc.get("template_name") or ""),
            parent_route=normalize_parent_route(template_doc.get("parent_route")),
        )
        return []

    try:
        _integration_doc, _data_doc, effective_data = await get_effective_integration_data_doc(
            db,
            integration_id,
        )
    except IntegrationReviewError:
        _append_sync_warning(
            warning_collector,
            code="integration_data_missing",
            message=f'No cached integration data found for integration "{integration_id}".',
            source_id=source_id,
            source_type=source_type,
            template_name=str(template_doc.get("template_name") or ""),
            parent_route=normalize_parent_route(template_doc.get("parent_route")),
        )
        return []

    rows = _normalize_integration_rows(effective_data)
    if not rows:
        _append_sync_warning(
            warning_collector,
            code="integration_data_empty",
            message=f'Integration "{integration_id}" has no mappable rows.',
            source_id=source_id,
            source_type=source_type,
            template_name=str(template_doc.get("template_name") or ""),
            parent_route=normalize_parent_route(template_doc.get("parent_route")),
        )
        return []
    return rows


def _resolve_integration_row_for_source(
    template_doc: dict,
    source_payload: dict,
    integration_rows: list[dict],
    *,
    warning_collector: list[dict] | None = None,
    source_id: str | None = None,
    source_type: str | None = None,
) -> dict | None:
    if not integration_rows:
        return None

    explicit_match_mappings = _normalize_integration_match_mappings(
        template_doc.get("integration_match_mappings")
    )
    match_mappings = explicit_match_mappings
    if not match_mappings:
        indexed_row = _integration_row_for_source_index(source_payload, integration_rows)
        if indexed_row is not None:
            _append_sync_warning(
                warning_collector,
                code="integration_match_index_fallback",
                message="Template has no integration match rules; using the integration row at the item index.",
                source_id=source_id,
                source_type=source_type,
                template_name=str(template_doc.get("template_name") or ""),
                parent_route=normalize_parent_route(template_doc.get("parent_route")),
            )
            return indexed_row
        if len(integration_rows) == 1:
            _append_sync_warning(
                warning_collector,
                code="integration_match_single_row_fallback",
                message="Template has no integration match rules; using the only available integration row.",
                source_id=source_id,
                source_type=source_type,
                template_name=str(template_doc.get("template_name") or ""),
                parent_route=normalize_parent_route(template_doc.get("parent_route")),
            )
            return integration_rows[0]
        _append_sync_warning(
            warning_collector,
            code="integration_match_mapping_missing",
            message="Template has integration data but no usable match rules were found.",
            source_id=source_id,
            source_type=source_type,
            template_name=str(template_doc.get("template_name") or ""),
            parent_route=normalize_parent_route(template_doc.get("parent_route")),
        )
        return None

    prepared_match_rules: list[tuple[Any, str, str]] = []
    for mapping in match_mappings:
        source_path = _strip_mapping_item_prefix(mapping.get("source_path"))
        integration_path = _strip_mapping_integration_prefix(mapping.get("integration_path"))
        source_value = _deep_get(source_payload, source_path)
        if source_value is None:
            continue
        prepared_match_rules.append((source_value, source_path, integration_path))

    if not prepared_match_rules:
        indexed_row = _integration_row_for_source_index(source_payload, integration_rows)
        if indexed_row is not None:
            _append_sync_warning(
                warning_collector,
                code="integration_match_source_index_fallback",
                message="Integration match rules resolved no source values; using the integration row at the item index.",
                source_id=source_id,
                source_type=source_type,
                template_name=str(template_doc.get("template_name") or ""),
                parent_route=normalize_parent_route(template_doc.get("parent_route")),
            )
            return indexed_row
        if len(integration_rows) == 1:
            _append_sync_warning(
                warning_collector,
                code="integration_match_no_source_values_single_row_fallback",
                message="Integration match rules resolved no source values; using the only available integration row.",
                source_id=source_id,
                source_type=source_type,
                template_name=str(template_doc.get("template_name") or ""),
                parent_route=normalize_parent_route(template_doc.get("parent_route")),
            )
            return integration_rows[0]
        _append_sync_warning(
            warning_collector,
            code="integration_match_source_missing",
            message="None of the integration match rules resolved a value on the item payload.",
            source_id=source_id,
            source_type=source_type,
            template_name=str(template_doc.get("template_name") or ""),
            parent_route=normalize_parent_route(template_doc.get("parent_route")),
        )
        return None

    matching_rows: list[dict] = []
    for row in integration_rows:
        matches = True
        for source_value, _, integration_path in prepared_match_rules:
            integration_value = _deep_get(row, integration_path)
            if integration_value is None or not _values_match(source_value, integration_value):
                matches = False
                break
        if matches:
            matching_rows.append(row)

    if not matching_rows:
        if len(integration_rows) == 1:
            _append_sync_warning(
                warning_collector,
                code="integration_row_not_found_single_row_fallback",
                message="No integration row matched the configured rules; using the only available integration row.",
                source_id=source_id,
                source_type=source_type,
                template_name=str(template_doc.get("template_name") or ""),
                parent_route=normalize_parent_route(template_doc.get("parent_route")),
            )
            return integration_rows[0]
        _append_sync_warning(
            warning_collector,
            code="integration_row_not_found",
            message="No integration row matched the configured template match rules.",
            source_id=source_id,
            source_type=source_type,
            template_name=str(template_doc.get("template_name") or ""),
            parent_route=normalize_parent_route(template_doc.get("parent_route")),
        )
        return None

    if len(matching_rows) > 1:
        _append_sync_warning(
            warning_collector,
            code="integration_row_ambiguous",
            message="Multiple integration rows matched; using the first row.",
            source_id=source_id,
            source_type=source_type,
            template_name=str(template_doc.get("template_name") or ""),
            parent_route=normalize_parent_route(template_doc.get("parent_route")),
        )

    return matching_rows[0]


def _integration_row_for_review_item_key(
    integration_rows: list[dict],
    *,
    output_primary_key_path: str | None,
    item_key: str | None,
) -> dict | None:
    normalized_item_key = str(item_key or "").strip()
    if not normalized_item_key:
        return None
    primary_key_path = str(output_primary_key_path or "").strip()
    if not primary_key_path:
        if normalized_item_key == REVIEW_ROOT_ITEM_KEY and len(integration_rows) == 1:
            return integration_rows[0]
        return None
    for row in integration_rows:
        if not isinstance(row, dict):
            continue
        row_key = review_item_key_for_row(row, primary_key_path)
        if str(row_key or "").strip() == normalized_item_key:
            return row
    return None


def _program_review_item_key_from_source_identity(
    *,
    source_type: str | None,
    source_id: str | None,
    source_payload: dict | None = None,
    integration_primary_key_path: str | None = None,
) -> str:
    normalized_source_type = str(source_type or "").strip().lower()
    if normalized_source_type in {"program_gig", "program_stage"} and isinstance(source_payload, dict):
        primary_key_path = str(integration_primary_key_path or "").strip()
        for candidate in (
            review_item_key_for_row(source_payload, primary_key_path)
            if primary_key_path
            else "",
            str(source_payload.get("integration_item_key") or "").strip(),
            str(source_payload.get("integrationItemKey") or "").strip(),
            str(source_payload.get("template_integration_item_key") or "").strip(),
            str(source_payload.get("review_item_key") or "").strip(),
            str(source_payload.get("reviewItemKey") or "").strip(),
        ):
            if candidate:
                return candidate
    return ""


def _fixed_gig_lookup_text_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        values = [
            str(value.get("de") or "").strip(),
            str(value.get("en") or "").strip(),
        ]
    elif isinstance(value, list):
        values = []
        for entry in value:
            values.extend(_fixed_gig_lookup_text_values(entry))
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


def _fixed_gig_lookup_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    for text in _fixed_gig_lookup_text_values(value):
        normalized = str(text or "").strip().lower()
        if normalized:
            tokens.add(normalized)
        slug = slugify_segment(text, fallback="")
        if slug:
            tokens.add(slug)
    return tokens


def _program_gig_source_payload_tokens(
    source_payload: dict | None,
    *,
    integration_payload: dict | None = None,
    integration_primary_key_path: str | None = None,
) -> set[str]:
    if not isinstance(source_payload, dict):
        return set()
    values: list[Any] = [
        source_payload.get("id"),
        source_payload.get("artist_name"),
        source_payload.get("title"),
        source_payload.get("name"),
    ]
    if isinstance(integration_payload, dict):
        values.extend(
            [
                integration_payload.get("id"),
                integration_payload.get("artist_name"),
                integration_payload.get("title"),
                integration_payload.get("name"),
            ]
        )
        primary_path = str(integration_primary_key_path or "").strip()
        if primary_path:
            values.append(_deep_get(integration_payload, primary_path))

    tokens: set[str] = set()
    for value in values:
        tokens.update(_fixed_gig_lookup_tokens(value))
    return tokens


def _source_payload_looks_like_program_gig(source_payload: dict | None) -> bool:
    if not isinstance(source_payload, dict):
        return False
    return any(
        key in source_payload
        for key in ("title", "artist_name", "gig_type", "start", "start_time", "genre")
    )


def _program_gig_id_for_fixed_gig_target(
    *,
    source_payload: dict | None,
    source_id: str | None,
    source_type: str | None,
    mapped_value: Any = None,
    integration_payload: dict | None = None,
    integration_primary_key_path: str | None = None,
    warning_collector: list[dict] | None = None,
    template_doc: dict | None = None,
) -> str:
    normalized_source_type = str(source_type or "").strip().lower()
    normalized_source_id = str(source_id or "").strip()
    if normalized_source_type == "program_gig" and normalized_source_id.startswith("program:gig:"):
        item_id = str(normalized_source_id.removeprefix("program:gig:") or "").strip()
        if item_id:
            return item_id
    if not isinstance(source_payload, dict):
        return ""

    item_id = str(source_payload.get("id") or "").strip()
    if not item_id:
        return ""
    if normalized_source_type == "program_gig":
        return item_id
    if not _source_payload_looks_like_program_gig(source_payload):
        return ""

    mapped_tokens = _fixed_gig_lookup_tokens(mapped_value)
    if not mapped_tokens:
        return ""
    source_tokens = _program_gig_source_payload_tokens(
        source_payload,
    )
    if mapped_tokens & source_tokens:
        return item_id
    integration_tokens = _program_gig_source_payload_tokens(
        {},
        integration_payload=integration_payload,
        integration_primary_key_path=integration_primary_key_path,
    )
    if mapped_tokens & integration_tokens:
        _append_sync_warning(
            warning_collector,
            code="fixed_gig_match_ambiguous",
            message="Fixed gig mapping skipped because the mapped value matched integration row tokens but not the source gig identity.",
            source_id=normalized_source_id,
            source_type=normalized_source_type,
            template_name=str((template_doc or {}).get("template_name") or ""),
            parent_route=normalize_parent_route((template_doc or {}).get("parent_route")),
        )
    return ""


def _normalize_media_tag_binding_source_path(value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if normalized.startswith("integration."):
        return normalized
    if normalized.startswith("item."):
        return ""
    return f"integration.{normalized}"


def _normalize_gallery_media_tag_bindings(raw_bindings: Any) -> list[dict]:
    if not isinstance(raw_bindings, list):
        return []
    normalized: list[dict] = []
    for index, raw_binding in enumerate(raw_bindings):
        if not isinstance(raw_binding, dict):
            continue
        prefix = normalize_media_tag_part(
            raw_binding.get("prefix")
            or ""
        )
        prefix_source_path = _normalize_media_tag_binding_source_path(
            raw_binding.get("prefix_source_path")
        )
        value_source_path = _normalize_media_tag_binding_source_path(
            raw_binding.get("value_source_path")
        )
        resolved_tag = str(
            raw_binding.get("resolved_tag") or ""
        ).strip()
        enabled = raw_binding.get("enabled")
        enabled = enabled if isinstance(enabled, bool) else str(enabled).strip().lower() not in {"0", "false", "no", "off"}
        if not (prefix or prefix_source_path or value_source_path or resolved_tag):
            continue
        normalized.append(
            {
                "id": str(raw_binding.get("id") or f"media-tag-binding-{index + 1}"),
                "enabled": enabled,
                "prefix": prefix,
                "prefix_source_path": prefix_source_path,
                "value_source_path": value_source_path,
                "resolved_tag": resolved_tag,
            }
        )
    return normalized


def _resolve_gallery_media_tag_bindings_for_item_page(
    template_doc: dict,
    sections_payload: list[dict],
    *,
    source_payload: dict,
    integration_payload: dict | None = None,
    item_integration_mapping: dict | None = None,
    warning_collector: list[dict] | None = None,
    source_id: str | None = None,
    source_type: str | None = None,
) -> None:
    if not isinstance(sections_payload, list):
        return
    for section_index, section in enumerate(sections_payload):
        if not isinstance(section, dict):
            continue
        section_type = normalize_section_type_value(section.get("section_type"), default="") or ""
        if section_type != "gallery":
            continue
        type_data = section.get("type_data") if isinstance(section.get("type_data"), dict) else {}
        bindings = _normalize_gallery_media_tag_bindings(type_data.get("media_tag_bindings"))
        if not bindings:
            continue
        next_bindings: list[dict] = []
        for binding_index, binding in enumerate(bindings):
            next_binding = dict(binding)
            next_binding["resolved_tag"] = ""
            if not binding.get("enabled", True):
                next_bindings.append(next_binding)
                continue

            prefix = normalize_media_tag_part(binding.get("prefix"))
            prefix_source_path = str(binding.get("prefix_source_path") or "").strip()
            value_source_path = str(binding.get("value_source_path") or "").strip()
            prefix_value = (
                prefix
                or (
                    _resolve_mapping_source_value(
                        prefix_source_path,
                        source_payload,
                        integration_payload,
                        item_integration_mapping,
                    )
                    if prefix_source_path
                    else None
                )
            )
            value_value = (
                _resolve_mapping_source_value(
                    value_source_path,
                    source_payload,
                    integration_payload,
                    item_integration_mapping,
                )
                if value_source_path
                else None
            )
            prefix_text = media_tag_text_value(prefix_value)
            value_text = media_tag_text_value(value_value)
            if not prefix_text:
                _append_sync_warning(
                    warning_collector,
                    code="gallery_media_tag_prefix_missing",
                    message=f"Gallery media tag binding #{binding_index + 1} has no configured media tag prefix.",
                    source_id=source_id,
                    source_type=source_type,
                    source_path=prefix_source_path,
                    template_name=str(template_doc.get("template_name") or ""),
                    parent_route=normalize_parent_route(template_doc.get("parent_route")),
                )
                next_bindings.append(next_binding)
                continue
            if not value_text:
                _append_sync_warning(
                    warning_collector,
                    code="gallery_media_tag_value_missing",
                    message=f'Gallery media tag binding #{binding_index + 1} source "{value_source_path}" returned no tag value.',
                    source_id=source_id,
                    source_type=source_type,
                    source_path=value_source_path,
                    template_name=str(template_doc.get("template_name") or ""),
                    parent_route=normalize_parent_route(template_doc.get("parent_route")),
                )
                next_bindings.append(next_binding)
                continue
            next_binding["prefix"] = normalize_media_tag_part(prefix_value)
            next_binding["resolved_tag"] = build_media_tag(prefix_value, value_value)
            next_bindings.append(next_binding)
        type_data["media_tag_bindings"] = next_bindings
        section["type_data"] = type_data


def _apply_item_mappings(
    template_doc: dict,
    source_payload: dict,
    *,
    integration_payload: dict | None = None,
    integration_primary_key_path: str | None = None,
    item_integration_mapping: dict | None = None,
    warning_collector: list[dict] | None = None,
    mapped_target_collector: set[str] | None = None,
    source_id: str | None = None,
    source_type: str | None = None,
) -> tuple[dict, dict | None, list[dict]]:
    page_payload = {
        "title": deepcopy(template_doc.get("title") or {"de": "", "en": ""}),
        "status": normalize_page_status(
            template_doc.get("status"),
            fallback="hidden",
        ),
        "in_menu": bool(template_doc.get("in_menu", False)),
        "in_footer": bool(template_doc.get("in_footer", False)),
        "hide_in_admin_sitemap": bool(template_doc.get("hide_in_admin_sitemap", True)),
        "hide_from_sitemap": bool(template_doc.get("hide_from_sitemap", True)),
        "hide_subtree_from_sitemap": bool(template_doc.get("hide_subtree_from_sitemap", True)),
        "sitemap_priority": template_doc.get("sitemap_priority"),
        "sitemap_changefreq": template_doc.get("sitemap_changefreq"),
        "menu_title": deepcopy(template_doc.get("menu_title")),
        "menu_order": int(template_doc.get("menu_order", 0) or 0),
        "footer_order": int(template_doc.get("footer_order", 0) or 0),
        "redirect_to": template_doc.get("redirect_to"),
        "section_bg_pinned_start_key": str(template_doc.get("section_bg_pinned_start_key") or ""),
        "section_bg_pinned_end_key": str(template_doc.get("section_bg_pinned_end_key") or ""),
    }
    header_payload = deepcopy(template_doc.get("header")) if isinstance(template_doc.get("header"), dict) else None
    sections_payload = deepcopy(template_doc.get("sections") or [])

    root = {
        "page": page_payload,
        "header": header_payload if isinstance(header_payload, dict) else {},
        "sections": sections_payload,
    }

    page_integration_mapping = resolve_page_integration_mapping_for_template_doc(template_doc)
    source_provider = item_page_mapping_source_provider_for_template_doc(template_doc)
    raw_mappings_by_collection_path = (
        page_integration_mapping.get("list_mappings_by_collection_path")
        if isinstance(page_integration_mapping, dict)
        else {}
    )

    def _coerce_value_for_target(target_path: str, raw_value: Any) -> Any:
        if raw_value is None:
            return None
        normalized_target = str(target_path or "").strip()
        if not normalized_target:
            return raw_value
        if normalized_target.endswith(".fixed_gig_id"):
            fixed_gig_id = _program_gig_id_for_fixed_gig_target(
                source_payload=source_payload,
                source_id=source_id,
                source_type=source_type,
                warning_collector=warning_collector,
                template_doc=template_doc,
            )
            if fixed_gig_id:
                return fixed_gig_id
            return str(raw_value or "").strip()
        if normalized_target.endswith(".video_id"):
            return _extract_video_id_from_mapping_value(raw_value)
        if normalized_target.endswith(".de") or normalized_target.endswith(".en"):
            return raw_value

        existing_target = _deep_get(root, normalized_target)
        if isinstance(existing_target, dict) and (
            "de" in existing_target or "en" in existing_target
        ):
            if isinstance(raw_value, dict):
                raw_de = str(raw_value.get("de") or raw_value.get("en") or "").strip()
                raw_en = str(raw_value.get("en") or raw_value.get("de") or "").strip()
                return {"de": raw_de, "en": raw_en}
            if isinstance(raw_value, (str, int, float, bool)):
                text_value = str(raw_value).strip()
                return {"de": text_value, "en": text_value}
        return raw_value

    for raw_collection_path, raw_rows in raw_mappings_by_collection_path.items():
        collection_path = _normalize_page_mapping_collection_path(raw_collection_path)
        if not collection_path or not isinstance(raw_rows, list):
            continue
        for mapping in raw_rows:
            target_path = _normalize_page_mapping_target_path_for_collection(
                collection_path,
                mapping.get("target_path"),
            )
            fixed_gig_id_value = ""
            if _is_fixed_gig_mapping_target_path(target_path):
                fixed_gig_id_value = _program_gig_id_for_fixed_gig_target(
                    source_payload=source_payload,
                    source_id=source_id,
                    source_type=source_type,
                    warning_collector=warning_collector,
                    template_doc=template_doc,
                )
            if (
                _is_fixed_gig_mapping_target_path(target_path)
                and not str(integration_primary_key_path or "").strip()
                and _fixed_gig_source_requires_primary_fallback(mapping.get("source_path"))
                and not fixed_gig_id_value
            ):
                _append_sync_warning(
                    warning_collector,
                    code="integration_primary_key_missing",
                    message="Fixed gig mappings require an External ID on the selected integration.",
                    source_id=source_id,
                    source_type=source_type,
                    template_name=str(template_doc.get("template_name") or ""),
                    parent_route=normalize_parent_route(template_doc.get("parent_route")),
                )
                continue
            source_path = _page_mapping_source_path_for_target(
                mapping.get("source_path"),
                target_path,
                integration_primary_key_path=integration_primary_key_path,
                source_provider=source_provider,
            )
            if not source_path or not target_path:
                continue
            resolved_target_path = target_path
            section_index = None
            if collection_path.startswith("sections["):
                section_index = _resolve_page_mapping_section_index(
                    root.get("sections"),
                    collection_path,
                    mapping,
                )
                section_payload = (
                    root["sections"][section_index]
                    if (
                        section_index is not None
                        and isinstance(root.get("sections"), list)
                        and section_index < len(root["sections"])
                        and isinstance(root["sections"][section_index], dict)
                    )
                    else {}
                )
                resolved_target_path = _resolve_links_social_target_path(
                    section_payload,
                    target_path,
                )
            if not resolved_target_path:
                continue
            value = None
            if _is_fixed_gig_mapping_target_path(resolved_target_path):
                fixed_gig_id_value = _program_gig_id_for_fixed_gig_target(
                    source_payload=source_payload,
                    source_id=source_id,
                    source_type=source_type,
                    warning_collector=warning_collector,
                    template_doc=template_doc,
                )
            if fixed_gig_id_value:
                value = fixed_gig_id_value
            else:
                value = _resolve_mapping_source_value(
                    source_path,
                    source_payload,
                    integration_payload,
                    item_integration_mapping,
                )
                if value is not None and _is_fixed_gig_mapping_target_path(resolved_target_path):
                    resolved_fixed_gig_id = _program_gig_id_for_fixed_gig_target(
                        source_payload=source_payload,
                        source_id=source_id,
                        source_type=source_type,
                        mapped_value=value,
                        integration_payload=integration_payload,
                        integration_primary_key_path=integration_primary_key_path,
                        warning_collector=warning_collector,
                        template_doc=template_doc,
                    )
                    if resolved_fixed_gig_id:
                        value = resolved_fixed_gig_id
            if value is None:
                _append_sync_warning(
                    warning_collector,
                    code="item_mapping_source_missing",
                    message=f'Mapped source path "{source_path}" returned no value.',
                    source_id=source_id,
                    source_type=source_type,
                    source_path=source_path,
                    template_name=str(template_doc.get("template_name") or ""),
                    parent_route=normalize_parent_route(template_doc.get("parent_route")),
                )
                continue

            if collection_path == "page":
                full_target_path = f"page.{resolved_target_path}"
            elif collection_path == "header":
                full_target_path = f"header.{resolved_target_path}"
            else:
                if section_index is None:
                    continue
                full_target_path = f"sections[{section_index}].{resolved_target_path}"
            coerced_value = _coerce_value_for_target(full_target_path, value)
            if collection_path == "header":
                if root["header"] is None:
                    root["header"] = {}
                _deep_set(root, full_target_path, coerced_value)
            else:
                _deep_set(root, full_target_path, coerced_value)
                if _is_fixed_gig_mapping_target_path(resolved_target_path):
                    _clear_program_fixed_gig_scope_fields(root, section_index)
            if mapped_target_collector is not None:
                mapped_target_collector.add(full_target_path)

    _resolve_gallery_media_tag_bindings_for_item_page(
        template_doc,
        sections_payload,
        source_payload=source_payload,
        integration_payload=integration_payload,
        item_integration_mapping=item_integration_mapping,
        warning_collector=warning_collector,
        source_id=source_id,
        source_type=source_type,
    )

    source_title = source_payload.get("title") if isinstance(source_payload.get("title"), dict) else None
    if isinstance(source_title, dict):
        current_title = page_payload.get("title") if isinstance(page_payload.get("title"), dict) else {"de": "", "en": ""}
        if not str(current_title.get("de") or "").strip() and not str(current_title.get("en") or "").strip():
            page_payload["title"] = {
                "de": str(source_title.get("de") or source_title.get("en") or ""),
                "en": str(source_title.get("en") or source_title.get("de") or ""),
            }

    if isinstance(root.get("header"), dict):
        header_payload = root["header"]

    return page_payload, header_payload, sections_payload


def _normalize_mapping_preview_item_index(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed >= 0 else None


def _header_title_target_was_mapped(mapped_targets: set[str]) -> bool:
    for raw_target in mapped_targets:
        target = str(raw_target or "").strip()
        if (
            target == "header.hero_title"
            or target.startswith("header.hero_title.")
            or target == "header.heroTitle"
            or target.startswith("header.heroTitle.")
            or target == "header.title"
            or target.startswith("header.title.")
        ):
            return True
    return False


def _preview_effective_design_settings(template_doc: dict) -> dict | None:
    current = template_doc.get("template_design_current")
    if isinstance(current, dict):
        return deepcopy(current)
    published = template_doc.get("template_design_published")
    if isinstance(published, dict):
        return deepcopy(published)
    return None


def _preview_warning(
    warning_collector: list[dict] | None,
    *,
    code: str,
    message: str,
    source_id: str | None = None,
    source_type: str | None = None,
    template_doc: dict | None = None,
) -> None:
    _append_sync_warning(
        warning_collector,
        code=code,
        message=message,
        source_id=source_id,
        source_type=source_type,
        template_name=str((template_doc or {}).get("template_name") or ""),
        parent_route=normalize_parent_route((template_doc or {}).get("parent_route")),
    )


def _integration_row_for_preview_selection(
    integration_rows: list[dict],
    *,
    output_primary_key_path: str | None,
    preview_item_key: str | None,
    preview_item_index: int | None,
    warning_collector: list[dict] | None = None,
    template_doc: dict | None = None,
) -> tuple[dict | None, str, int | None]:
    normalized_key = str(preview_item_key or "").strip()
    if normalized_key:
        row = _integration_row_for_review_item_key(
            integration_rows,
            output_primary_key_path=output_primary_key_path,
            item_key=normalized_key,
        )
        if isinstance(row, dict):
            index = next(
                (
                    idx
                    for idx, candidate in enumerate(integration_rows)
                    if candidate is row
                ),
                None,
            )
            return row, normalized_key, index
        _preview_warning(
            warning_collector,
            code="preview_integration_item_not_found",
            message=f'Preview integration item "{normalized_key}" could not be resolved.',
            template_doc=template_doc,
        )

    if preview_item_index is not None and 0 <= preview_item_index < len(integration_rows):
        row = integration_rows[preview_item_index]
        if isinstance(row, dict):
            item_key = (
                review_item_key_for_row(row, str(output_primary_key_path or "").strip())
                if str(output_primary_key_path or "").strip()
                else REVIEW_ROOT_ITEM_KEY
            )
            return row, str(item_key or "").strip(), preview_item_index

    if integration_rows:
        row = integration_rows[0]
        item_key = (
            review_item_key_for_row(row, str(output_primary_key_path or "").strip())
            if str(output_primary_key_path or "").strip()
            else REVIEW_ROOT_ITEM_KEY
        )
        if preview_item_index is not None:
            _preview_warning(
                warning_collector,
                code="preview_integration_index_fallback",
                message="Preview integration item index was out of range; using the first integration row.",
                template_doc=template_doc,
            )
        return row, str(item_key or "").strip(), 0

    return None, "", None


def _preview_identity_tokens_from_values(values: list[Any]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict) or isinstance(value, list):
            tokens.update(_fixed_gig_lookup_tokens(value))
            continue
        text = str(value or "").strip()
        if not text:
            continue
        tokens.add(text.lower())
        slug = slugify_segment(text, fallback="")
        if slug:
            tokens.add(slug)
    return tokens


def _preview_program_identity_tokens(
    payload: dict | None,
    *,
    primary_key_path: str | None = None,
    include_title_values: bool = False,
    include_id: bool = False,
) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    primary_path = str(primary_key_path or "").strip()
    values: list[Any] = [
        _deep_get(payload, primary_path) if primary_path else None,
        payload.get("integration_item_key"),
        payload.get("integrationItemKey"),
        payload.get("template_integration_item_key"),
        payload.get("templateIntegrationItemKey"),
        payload.get("review_item_key"),
        payload.get("reviewItemKey"),
        payload.get("external_id"),
        payload.get("externalId"),
    ]
    if include_id:
        values.append(payload.get("id"))
    if include_title_values:
        values.extend(
            [
                payload.get("title"),
                payload.get("artist_name"),
                payload.get("artistName"),
                payload.get("gig_title"),
                payload.get("gigTitle"),
                payload.get("name"),
            ]
        )
    return _preview_identity_tokens_from_values(values)


def _integration_preview_identity_tokens(
    integration_payload: dict | None,
    *,
    primary_key_path: str | None,
    item_key: str | None,
    include_title_values: bool = False,
    include_id: bool = False,
) -> set[str]:
    values: list[Any] = [item_key]
    if isinstance(integration_payload, dict):
        primary_path = str(primary_key_path or "").strip()
        values.extend(
            [
                _deep_get(integration_payload, primary_path) if primary_path else None,
                integration_payload.get("integration_item_key"),
                integration_payload.get("integrationItemKey"),
                integration_payload.get("template_integration_item_key"),
                integration_payload.get("templateIntegrationItemKey"),
                integration_payload.get("review_item_key"),
                integration_payload.get("reviewItemKey"),
                integration_payload.get("external_id"),
                integration_payload.get("externalId"),
            ]
        )
        if include_id:
            values.append(integration_payload.get("id"))
        if include_title_values:
            values.extend(
                [
                    integration_payload.get("title"),
                    integration_payload.get("artist_name"),
                    integration_payload.get("artistName"),
                    integration_payload.get("gig_title"),
                    integration_payload.get("gigTitle"),
                    integration_payload.get("name"),
                ]
            )
    return _preview_identity_tokens_from_values(values)


def _find_program_preview_row_for_integration(
    rows: list[dict],
    integration_payload: dict | None,
    *,
    primary_key_path: str | None,
    item_key: str | None,
) -> dict | None:
    if not isinstance(integration_payload, dict):
        return None

    key_tokens = _integration_preview_identity_tokens(
        integration_payload,
        primary_key_path=primary_key_path,
        item_key=item_key,
    )
    if key_tokens:
        for row in rows:
            row_tokens = _preview_program_identity_tokens(
                row,
                primary_key_path=primary_key_path,
            )
            if key_tokens & row_tokens:
                return row

    id_tokens = _integration_preview_identity_tokens(
        integration_payload,
        primary_key_path=primary_key_path,
        item_key=item_key,
        include_id=True,
    )
    if id_tokens:
        for row in rows:
            row_tokens = _preview_program_identity_tokens(
                row,
                primary_key_path=primary_key_path,
                include_id=True,
            )
            if id_tokens & row_tokens:
                return row

    title_tokens = _integration_preview_identity_tokens(
        integration_payload,
        primary_key_path=primary_key_path,
        item_key=item_key,
        include_title_values=True,
    )
    if not title_tokens:
        return None
    for row in rows:
        row_tokens = _preview_program_identity_tokens(
            row,
            primary_key_path=primary_key_path,
            include_title_values=True,
        )
        if title_tokens & row_tokens:
            return row
    return None


async def _resolve_program_preview_source(
    db,
    *,
    template_doc: dict,
    kind: str,
    integration_payload: dict | None,
    integration_primary_key_path: str | None,
    integration_item_key: str | None,
    preview_item_index: int | None,
    warning_collector: list[dict],
) -> tuple[dict | None, str, str, dict | None, dict]:
    normalized_kind = "stage" if str(kind or "").strip().lower() == "stage" else "gig"
    source_type = "program_stage" if normalized_kind == "stage" else "program_gig"
    shared_doc = await db[PROGRAM_SHARED_COLLECTION].find_one({"_id": PROGRAM_SHARED_DOC_ID})
    normalized_shared = program_catalog.normalize_program_shared_content_snapshot(shared_doc or {})
    raw_stages = (
        normalized_shared.get("stages")
        if isinstance(normalized_shared.get("stages"), list)
        else []
    )
    raw_gigs = (
        normalized_shared.get("gigs")
        if isinstance(normalized_shared.get("gigs"), list)
        else []
    )
    shared_gig_primary_key_path = program_catalog.integration_output_primary_key_path_from_cache_state(
        normalized_shared.get("program_gigs_integration_mapping_cache_state")
    )
    shared_gig_selected_integration_id = program_catalog.integration_selected_id_from_mapping(
        normalized_shared.get("program_gigs_integration_mapping")
    )
    ordered_gig_ids = [
        str(gig_id or "").strip()
        for gig_id in (
            normalized_shared.get("gig_ids")
            if isinstance(normalized_shared.get("gig_ids"), list)
            else []
        )
        if str(gig_id or "").strip()
    ]
    if ordered_gig_ids:
        raw_gigs = await program_catalog.load_program_gig_docs(
            db,
            ordered_gig_ids=ordered_gig_ids,
            primary_key_path=shared_gig_primary_key_path,
            selected_integration_id=shared_gig_selected_integration_id,
        )
    elif not raw_gigs:
        raw_gigs = await program_catalog.load_program_gig_docs(
            db,
            primary_key_path=shared_gig_primary_key_path,
            selected_integration_id=shared_gig_selected_integration_id,
        )
    stages = [
        _normalize_program_stage_for_sync(raw_stage, index)
        for index, raw_stage in enumerate(raw_stages)
    ]
    gigs = [
        _normalize_program_gig_for_sync(
            raw_gig,
            index,
            primary_key_path=shared_gig_primary_key_path or integration_primary_key_path,
            selected_integration_id=shared_gig_selected_integration_id,
        )
        for index, raw_gig in enumerate(raw_gigs)
    ]
    rows = stages if normalized_kind == "stage" else gigs

    selected_row = _find_program_preview_row_for_integration(
        rows,
        integration_payload,
        primary_key_path=shared_gig_primary_key_path or integration_primary_key_path,
        item_key=integration_item_key,
    )
    if selected_row is None and preview_item_index is not None and 0 <= preview_item_index < len(rows):
        selected_row = rows[preview_item_index]
        _preview_warning(
            warning_collector,
            code="preview_program_item_index_fallback",
            message="Preview program item matched by selected item index.",
            source_type=source_type,
            template_doc=template_doc,
        )
    if selected_row is None and len(rows) == 1:
        selected_row = rows[0]
        _preview_warning(
            warning_collector,
            code="preview_program_single_item_fallback",
            message="Preview program item matched by the only available shared program item.",
            source_type=source_type,
            template_doc=template_doc,
        )

    if selected_row is None and isinstance(integration_payload, dict):
        selected_row = (
            _normalize_program_stage_for_sync(integration_payload, preview_item_index or 0)
            if normalized_kind == "stage"
            else _normalize_program_gig_for_sync(
                integration_payload,
                preview_item_index or 0,
                primary_key_path=integration_primary_key_path,
                selected_integration_id=_selected_mapping_integration_id(template_doc),
            )
        )
        _preview_warning(
            warning_collector,
            code="preview_program_source_integration_fallback",
            message="Preview used the selected integration row because no matching shared Program item was found.",
            source_type=source_type,
            template_doc=template_doc,
        )

    if not isinstance(selected_row, dict):
        _preview_warning(
            warning_collector,
            code="preview_program_source_missing",
            message="No shared Program item could be resolved for preview.",
            source_type=source_type,
            template_doc=template_doc,
        )
        return None, source_type, "", None, {
            "source_type": source_type,
            "source_id": "",
            "integration_item_key": integration_item_key or "",
            "preview_item_index": preview_item_index,
        }

    item_id = str(selected_row.get("id") or "").strip() or f"{normalized_kind}-{(preview_item_index or 0) + 1}"
    source_id = f"program:{normalized_kind}:{item_id}"
    stage_titles_by_id = build_program_stage_titles_lookup(stages)
    source_payload = (
        _source_payload_from_program_stage(selected_row)
        if normalized_kind == "stage"
        else _source_payload_from_program_gig(
            selected_row,
            stage_titles_by_id=stage_titles_by_id,
        )
    )
    item_mapping_key = (
        "program_stages_integration_mapping"
        if normalized_kind == "stage"
        else "program_gigs_integration_mapping"
    )
    item_mapping = _normalize_section_integration_mapping_payload(
        normalized_shared.get(item_mapping_key)
    )
    return source_payload, source_type, source_id, item_mapping, {
        "source_type": source_type,
        "source_id": source_id,
        "item_id": item_id,
        "integration_item_key": integration_item_key or str(selected_row.get("integration_item_key") or ""),
        "preview_item_index": preview_item_index,
    }


async def _resolve_preview_source_payload(
    db,
    *,
    template_doc: dict,
    integration_payload: dict | None,
    integration_primary_key_path: str | None,
    integration_item_key: str | None,
    preview_item_index: int | None,
    warning_collector: list[dict],
) -> tuple[dict | None, str, str, dict | None, dict]:
    source_type = str(template_doc.get("source_type") or "").strip().lower()
    source_kind = str(template_doc.get("source_kind") or "").strip().lower()

    if source_type == "program":
        return await _resolve_program_preview_source(
            db,
            template_doc=template_doc,
            kind=source_kind,
            integration_payload=integration_payload,
            integration_primary_key_path=integration_primary_key_path,
            integration_item_key=integration_item_key,
            preview_item_index=preview_item_index,
            warning_collector=warning_collector,
        )

    if source_type == "blog":
        source_payload = deepcopy(integration_payload) if isinstance(integration_payload, dict) else {}
        source_payload = _source_payload_from_blog_item(source_payload) if source_payload else None
        source_id = str((source_payload or {}).get("id") or integration_item_key or "preview-blog-item")
        return source_payload, "blog", source_id, None, {
            "source_type": "blog",
            "source_id": source_id,
            "integration_item_key": integration_item_key or "",
            "preview_item_index": preview_item_index,
        }

    if source_type == "tiles":
        source_payload = deepcopy(integration_payload) if isinstance(integration_payload, dict) else {}
        if source_payload:
            source_payload.setdefault("id", integration_item_key or "preview-tile")
            source_payload.setdefault("section_id", "preview-section")
        source_id = f"tiles:preview-section:{source_payload.get('id')}" if source_payload else ""
        return source_payload or None, "tiles", source_id, None, {
            "source_type": "tiles",
            "source_id": source_id,
            "integration_item_key": integration_item_key or "",
            "preview_item_index": preview_item_index,
        }

    source_payload = deepcopy(integration_payload) if isinstance(integration_payload, dict) else None
    source_id = str((source_payload or {}).get("id") or integration_item_key or "")
    return source_payload, source_type or "item", source_id, None, {
        "source_type": source_type or "item",
        "source_id": source_id,
        "integration_item_key": integration_item_key or "",
        "preview_item_index": preview_item_index,
    }


async def _resolve_item_page_mapping_context(
    db,
    *,
    template_doc: dict,
    source_payload: dict,
    source_type: str,
    source_id: str,
    integration_rows: list[dict] | None = None,
    item_integration_mapping: dict | None = None,
    warning_collector: list[dict] | None = None,
    existing_page: dict | None = None,
    force_rebuild: bool = False,
    cleaned_legacy_page_slug_override: bool = False,
    preferred_integration_payload: dict | None = None,
    preferred_integration_item_key: str | None = None,
    precomputed_integration_primary_key_path: str | None = None,
    precomputed_selected_mapping_integration_id: str | None = None,
    precomputed_source_identity_item_key: str | None = None,
    warning_parent_route: str | None = None,
    mapped_target_collector: set[str] | None = None,
) -> dict | None:
    normalized_source_type = str(source_type or "").strip().lower()
    normalized_source_id = str(source_id or "").strip()
    uses_shared_items = _item_page_mapping_uses_shared_items(template_doc)
    normalized_warning_parent_route = normalize_parent_route(
        template_doc.get("parent_route") if warning_parent_route is None else warning_parent_route
    )
    integration_primary_key_path = ""
    if not uses_shared_items:
        integration_primary_key_path = (
            str(precomputed_integration_primary_key_path or "").strip()
            if precomputed_integration_primary_key_path is not None
            else await _load_selected_mapping_integration_primary_key_path(
                db,
                template_doc,
            )
        )
    selected_mapping_integration_id = ""
    if not uses_shared_items:
        selected_mapping_integration_id = (
            str(precomputed_selected_mapping_integration_id or "").strip()
            if precomputed_selected_mapping_integration_id is not None
            else _selected_mapping_integration_id(template_doc)
        )
    source_identity_item_key = ""
    if not uses_shared_items:
        source_identity_item_key = (
            str(precomputed_source_identity_item_key or "").strip()
            if precomputed_source_identity_item_key is not None
            else _program_review_item_key_from_source_identity(
                source_type=normalized_source_type,
                source_id=normalized_source_id,
                source_payload=source_payload,
                integration_primary_key_path=integration_primary_key_path,
            )
        )
    resolved_integration_rows = (
        []
        if uses_shared_items
        else [row for row in integration_rows if isinstance(row, dict)]
        if isinstance(integration_rows, list) and not cleaned_legacy_page_slug_override
        else await _load_integration_rows_for_template(
            db,
            template_doc,
            warning_collector=warning_collector,
            source_id=source_id,
            source_type=source_type,
        )
    )
    stored_integration_item_key = (
        str(existing_page.get("template_integration_item_key") or "").strip()
        if isinstance(existing_page, dict) and not uses_shared_items
        else ""
    )
    source_identity_payload = (
        _integration_row_for_review_item_key(
            resolved_integration_rows,
            output_primary_key_path=integration_primary_key_path,
            item_key=source_identity_item_key,
        )
        if source_identity_item_key
        else None
    )

    if (
        isinstance(existing_page, dict)
        and force_rebuild
        and stored_integration_item_key
        and source_identity_item_key
        and source_identity_payload is not None
        and stored_integration_item_key != source_identity_item_key
    ):
        _append_sync_warning(
            warning_collector,
            code="integration_item_key_mismatch",
            message="Generated page regeneration skipped because its stored integration item key does not match the program item identity.",
            source_id=normalized_source_id,
            source_type=normalized_source_type,
            template_name=str(template_doc.get("template_name") or ""),
            parent_route=normalized_warning_parent_route,
        )
        return None

    integration_payload = None
    if stored_integration_item_key:
        integration_payload = _integration_row_for_review_item_key(
            resolved_integration_rows,
            output_primary_key_path=integration_primary_key_path,
            item_key=stored_integration_item_key,
        )
        if integration_payload is None:
            _append_sync_warning(
                warning_collector,
                code="integration_item_key_mismatch",
                message="Generated page regeneration skipped because its stored integration item key could not be resolved.",
                source_id=normalized_source_id,
                source_type=normalized_source_type,
                template_name=str(template_doc.get("template_name") or ""),
                parent_route=normalized_warning_parent_route,
            )
            return None

    if integration_payload is None and source_identity_payload is not None:
        integration_payload = source_identity_payload

    normalized_preferred_item_key = (
        str(preferred_integration_item_key or "").strip()
        if not uses_shared_items
        else ""
    )
    if integration_payload is None and normalized_preferred_item_key:
        integration_payload = _integration_row_for_review_item_key(
            resolved_integration_rows,
            output_primary_key_path=integration_primary_key_path,
            item_key=normalized_preferred_item_key,
        )
        if integration_payload is None and isinstance(preferred_integration_payload, dict):
            integration_payload = preferred_integration_payload

    if integration_payload is None and not uses_shared_items and isinstance(preferred_integration_payload, dict):
        integration_payload = preferred_integration_payload

    if integration_payload is None and not uses_shared_items:
        if (
            isinstance(existing_page, dict)
            and force_rebuild
            and normalized_source_type == "program_gig"
            and selected_mapping_integration_id
            and resolved_integration_rows
        ):
            _append_sync_warning(
                warning_collector,
                code="integration_item_key_mismatch",
                message="Generated gig page regeneration skipped because no exact integration item key could be resolved.",
                source_id=normalized_source_id,
                source_type=normalized_source_type,
                template_name=str(template_doc.get("template_name") or ""),
                parent_route=normalized_warning_parent_route,
            )
            return None
        integration_payload = _resolve_integration_row_for_source(
            template_doc,
            source_payload,
            resolved_integration_rows,
            warning_collector=warning_collector,
            source_id=normalized_source_id,
            source_type=normalized_source_type,
        )

    if uses_shared_items:
        template_integration_id, template_integration_item_key, template_integration_doc = "", "", None
    else:
        template_integration_id, template_integration_item_key, template_integration_doc = (
            await _resolve_integration_review_locator_for_mapping(
                db,
                template_doc=template_doc,
                integration_payload=integration_payload,
            )
        )
    if (
        stored_integration_item_key
        and template_integration_item_key
        and stored_integration_item_key != str(template_integration_item_key or "").strip()
    ):
        _append_sync_warning(
            warning_collector,
            code="integration_item_key_mismatch",
            message="Generated page regeneration skipped because the resolved integration row does not match its stored item key.",
            source_id=normalized_source_id,
            source_type=normalized_source_type,
            template_name=str(template_doc.get("template_name") or ""),
            parent_route=normalized_warning_parent_route,
        )
        return None

    mapped_targets = mapped_target_collector if mapped_target_collector is not None else set()
    page_payload, header_payload, sections_payload = _apply_item_mappings(
        template_doc,
        source_payload,
        integration_payload=integration_payload,
        integration_primary_key_path=integration_primary_key_path,
        item_integration_mapping=item_integration_mapping,
        warning_collector=warning_collector,
        mapped_target_collector=mapped_targets,
        source_id=source_id,
        source_type=source_type,
    )
    return {
        "integration_primary_key_path": integration_primary_key_path,
        "integration_rows": resolved_integration_rows,
        "integration_payload": integration_payload,
        "template_integration_id": template_integration_id,
        "template_integration_item_key": template_integration_item_key,
        "template_integration_doc": template_integration_doc,
        "page_payload": page_payload,
        "header_payload": header_payload,
        "sections_payload": sections_payload,
        "source_payload_hash": _compute_item_page_source_payload_hash(
            source_payload,
            integration_payload,
        ),
        "generated_mapped_target_values": _collect_generated_mapped_target_values(
            template_doc,
            page_payload=page_payload,
            header_payload=header_payload,
            sections_payload=sections_payload,
        ),
        "mapped_targets": mapped_targets,
    }


def _build_unmapped_preview_payload(
    template_doc: dict,
    *,
    warnings: list[dict],
    selected_preview_item: dict | None = None,
) -> dict:
    template_name = normalize_template_name(
        template_doc.get("template_name") or "default",
        default="default",
    )
    parent_route = normalize_parent_route(template_doc.get("parent_route"))
    template_path = compose_page_template_path(template_name, parent_route)
    full_payload = build_page_full_payload_for_template_page(template_path, template_doc)
    effective_design = _preview_effective_design_settings(template_doc)
    page_payload = {
        "slug": str(full_payload.get("slug") or ""),
        "title": deepcopy(full_payload.get("title")) if isinstance(full_payload.get("title"), dict) else {"de": "", "en": ""},
        "status": normalize_page_status(full_payload.get("status"), fallback="hidden"),
        "section_structure": deepcopy(full_payload.get("section_structure"))
        if isinstance(full_payload.get("section_structure"), list)
        else [],
        "template_style_ref": template_path,
        "template_style_linked": True,
        "template_style_lock": True,
        "effective_design_settings": effective_design,
        "section_bg_pinned_start_key": str(full_payload.get("section_bg_pinned_start_key") or ""),
        "section_bg_pinned_end_key": str(full_payload.get("section_bg_pinned_end_key") or ""),
    }
    full_payload["page"] = page_payload
    full_payload["template_style_ref"] = template_path
    full_payload["template_style_linked"] = True
    full_payload["template_style_lock"] = True
    full_payload["effective_design_settings"] = effective_design
    full_payload["warnings"] = warnings
    full_payload["selected_preview_item"] = selected_preview_item or {}
    return full_payload


async def preview_item_page_mapping_from_template_state(
    db,
    template_doc: dict,
    *,
    preview_item_key: str | None = None,
    preview_item_index: Any = None,
) -> dict:
    if not isinstance(template_doc, dict):
        raise ValueError("Template payload is required")

    warnings: list[dict] = []
    normalized_preview_item_index = _normalize_mapping_preview_item_index(preview_item_index)
    if _item_page_mapping_uses_shared_items(template_doc):
        source_type = str(template_doc.get("source_type") or "").strip().lower()
        if source_type == "blog":
            blog_items = await db["blog_shared"].find({}).sort("date", -1).to_list(length=5000)
            item_doc, selected_index = _blog_item_for_preview_selection(
                blog_items,
                preview_item_key=preview_item_key,
                preview_item_index=normalized_preview_item_index,
            )
            selected_preview_item = {
                "source_type": "blog",
                "source_id": str((item_doc or {}).get("_id") or ""),
                "preview_item_key": str((item_doc or {}).get("_id") or ""),
                "preview_item_index": selected_index,
                **_blog_preview_item_label(item_doc),
            }
            if not isinstance(item_doc, dict):
                _append_sync_warning(
                    warnings,
                    code="blog_items_empty",
                    message="No shared blog items are available for mapping preview.",
                    source_type="blog",
                    template_name=str(template_doc.get("template_name") or ""),
                    parent_route=normalize_parent_route(template_doc.get("parent_route")),
                )
                return _build_unmapped_preview_payload(
                    template_doc,
                    warnings=warnings,
                    selected_preview_item=selected_preview_item,
                )

            source_payload = _source_payload_from_blog_item(item_doc)
            mapped_targets: set[str] = set()
            mapping_context = await _resolve_item_page_mapping_context(
                db,
                template_doc=template_doc,
                source_payload=source_payload,
                source_type="blog",
                source_id=str(item_doc.get("_id") or ""),
                integration_rows=[],
                warning_collector=warnings,
                preferred_integration_payload=None,
                preferred_integration_item_key=None,
                precomputed_integration_primary_key_path="",
                precomputed_selected_mapping_integration_id="",
                precomputed_source_identity_item_key="",
                mapped_target_collector=mapped_targets,
            )
            if mapping_context is None:
                return _build_unmapped_preview_payload(
                    template_doc,
                    warnings=warnings,
                    selected_preview_item=selected_preview_item,
                )

            page_payload = mapping_context["page_payload"]
            header_payload = mapping_context["header_payload"]
            sections_payload = mapping_context["sections_payload"]
            preview_doc = {
                **deepcopy(template_doc),
                **deepcopy(page_payload),
                "has_header": bool(template_doc.get("has_header", False)),
                "header": deepcopy(header_payload) if isinstance(header_payload, dict) else None,
                "sections": deepcopy(sections_payload) if isinstance(sections_payload, list) else [],
            }
            full_payload = _build_unmapped_preview_payload(
                preview_doc,
                warnings=warnings,
                selected_preview_item=selected_preview_item,
            )
            full_payload["page"] = {
                **full_payload.get("page", {}),
                **deepcopy(page_payload),
                "effective_design_settings": _preview_effective_design_settings(preview_doc),
            }
            full_payload["header"] = deepcopy(header_payload) if isinstance(header_payload, dict) else None
            full_payload["sections"] = deepcopy(sections_payload) if isinstance(sections_payload, list) else []
            full_payload["mapped_targets"] = sorted(mapped_targets)
            return full_payload

    integration_primary_key_path = await _load_selected_mapping_integration_primary_key_path(
        db,
        template_doc,
    )
    integration_rows = await _load_integration_rows_for_template(
        db,
        template_doc,
        warning_collector=warnings,
        source_type=str(template_doc.get("source_type") or ""),
    )
    integration_payload, integration_item_key, selected_index = _integration_row_for_preview_selection(
        integration_rows,
        output_primary_key_path=integration_primary_key_path,
        preview_item_key=preview_item_key,
        preview_item_index=normalized_preview_item_index,
        warning_collector=warnings,
        template_doc=template_doc,
    )
    source_payload, source_type, source_id, item_integration_mapping, selected_preview_item = (
        await _resolve_preview_source_payload(
            db,
            template_doc=template_doc,
            integration_payload=integration_payload,
            integration_primary_key_path=integration_primary_key_path,
            integration_item_key=integration_item_key,
            preview_item_index=selected_index
            if selected_index is not None
            else normalized_preview_item_index,
            warning_collector=warnings,
        )
    )
    if not isinstance(source_payload, dict):
        return _build_unmapped_preview_payload(
            template_doc,
            warnings=warnings,
            selected_preview_item=selected_preview_item,
        )

    mapped_targets: set[str] = set()
    mapping_context = await _resolve_item_page_mapping_context(
        db,
        template_doc=template_doc,
        source_payload=source_payload,
        source_type=source_type,
        source_id=source_id,
        integration_rows=integration_rows,
        item_integration_mapping=item_integration_mapping,
        warning_collector=warnings,
        preferred_integration_payload=integration_payload,
        preferred_integration_item_key=integration_item_key,
        precomputed_integration_primary_key_path=integration_primary_key_path,
        mapped_target_collector=mapped_targets,
    )
    if mapping_context is None:
        return _build_unmapped_preview_payload(
            template_doc,
            warnings=warnings,
            selected_preview_item=selected_preview_item,
        )

    resolved_integration_id = str(mapping_context.get("template_integration_id") or "").strip()
    resolved_integration_item_key = str(mapping_context.get("template_integration_item_key") or "").strip()
    if resolved_integration_item_key:
        selected_preview_item["integration_item_key"] = resolved_integration_item_key
    if resolved_integration_id:
        selected_preview_item["integration_id"] = resolved_integration_id

    page_payload = mapping_context["page_payload"]
    header_payload = mapping_context["header_payload"]
    sections_payload = mapping_context["sections_payload"]

    preview_doc = {
        **deepcopy(template_doc),
        **deepcopy(page_payload),
        "has_header": bool(template_doc.get("has_header", False)),
        "header": deepcopy(header_payload) if isinstance(header_payload, dict) else None,
        "sections": deepcopy(sections_payload) if isinstance(sections_payload, list) else [],
    }
    full_payload = _build_unmapped_preview_payload(
        preview_doc,
        warnings=warnings,
        selected_preview_item=selected_preview_item,
    )
    full_payload["page"] = {
        **full_payload["page"],
        **deepcopy(page_payload),
        "slug": str(full_payload.get("slug") or ""),
        "section_structure": deepcopy(full_payload.get("section_structure"))
        if isinstance(full_payload.get("section_structure"), list)
        else [],
        "template_style_ref": full_payload.get("template_style_ref"),
        "template_style_linked": True,
        "template_style_lock": True,
        "effective_design_settings": full_payload.get("effective_design_settings"),
    }
    full_payload["__mapped_header_title"] = _header_title_target_was_mapped(mapped_targets)
    full_payload["mapped_targets"] = sorted(mapped_targets)
    return full_payload


async def _resolve_unique_slug(pages_coll, desired_slug: str, *, exclude_page_id: ObjectId | None = None) -> str:
    base_slug = normalize_slug(desired_slug)
    candidate = base_slug
    counter = 2

    while True:
        query: dict[str, Any] = {"slug": candidate}
        if exclude_page_id is not None:
            query["_id"] = {"$ne": exclude_page_id}
        existing = await pages_coll.find_one(query, {"_id": 1})
        if not existing:
            return candidate
        candidate = f"{base_slug}-{counter}"
        counter += 1


def _build_generated_item_temporary_slug(
    *,
    source_type: str,
    source_id: str,
    parent_route: str | None = None,
) -> str:
    normalized_parent_route = normalize_parent_route(parent_route)
    source_segment = slugify_segment(source_type, fallback="item")
    digest = hashlib.sha1(
        f"{source_type}:{source_id}".encode("utf-8")
    ).hexdigest()[:10]
    tail = f"tmp-{source_segment}-{digest}"
    if normalized_parent_route:
        return normalize_slug(f"{normalized_parent_route.strip('/')}/{tail}")
    return normalize_slug(tail)


def _build_blog_item_temporary_slug(
    *,
    source_payload: dict | None,
    source_id: str,
    parent_route: str | None = None,
) -> str:
    normalized_parent_route = normalize_parent_route(parent_route)
    payload = source_payload if isinstance(source_payload, dict) else {}
    date_value = str(payload.get("date") or "").strip()
    date_value = date_value.split("T", 1)[0].split(" ", 1)[0].strip()
    date_segment = slugify_segment(date_value, fallback="")
    if not date_segment:
        return _build_generated_item_temporary_slug(
            source_type="blog",
            source_id=source_id,
            parent_route=parent_route,
        )
    tail = f"tmp-blog-{date_segment}"
    if normalized_parent_route:
        return normalize_slug(f"{normalized_parent_route.strip('/')}/{tail}")
    return normalize_slug(tail)


def _safe_object_id(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return None


async def _delete_managed_page_resources(db, page_doc: dict) -> None:
    sections_coll = db["sections"]
    headers_coll = db["headers"]

    section_ids = page_doc.get("template_managed_section_ids")
    if isinstance(section_ids, list):
        object_ids = [_safe_object_id(section_id) for section_id in section_ids]
        object_ids = [oid for oid in object_ids if oid is not None]
        if object_ids:
            await sections_coll.delete_many({"_id": {"$in": object_ids}})

    header_id = _safe_object_id(page_doc.get("template_managed_header_id"))
    if header_id is not None:
        await headers_coll.delete_one({"_id": header_id})


def _build_page_section_ref_from_embedded_section(
    section: dict,
    *,
    section_id: str,
    order_index: int,
) -> dict:
    page_ref = {
        "section_id": section_id,
        "order": order_index,
        "visible": bool(section.get("visible", True)),
        "width_n": max(1, min(5, int(section.get("width_n", 1) or 1))),
        "width_d": max(1, min(5, int(section.get("width_d", 1) or 1))),
        "device_visibility": section.get("device_visibility")
        if isinstance(section.get("device_visibility"), dict)
        else {"mobile": True, "tablet": True, "desktop": True},
    }
    if page_ref["width_n"] > page_ref["width_d"]:
        page_ref["width_n"] = page_ref["width_d"]
    if section.get("limit") not in (None, "", 0, "0"):
        try:
            parsed_limit = int(section.get("limit"))
            if parsed_limit > 0:
                page_ref["limit"] = parsed_limit
        except Exception:
            pass
    return page_ref


def build_section_document_from_embedded_section(section: dict, *, now: datetime) -> dict:
    normalized = normalize_embedded_section(section)
    embedded_id = str(normalized.get("id") or "").strip()
    section_type = str(normalized.get("section_type") or "text").strip().lower() or "text"
    section_template_name = normalize_template_name(
        normalized.get("section_template_name") or "default",
        default="default",
    )
    doc = {
        "section_type": section_type,
        "shared": False,
        "section_template_name": section_template_name,
        "title_placeholder": normalized["title_placeholder"],
        "title": normalized["title"],
        "type_data": _normalize_section_type_data(
            section_type,
            normalized.get("type_data"),
        ),
        "section_integration_mapping": normalize_section_integration_mapping(
            normalized.get("section_integration_mapping")
        ),
        "revision_id": None,
        "created_at": now,
        "updated_at": now,
    }
    design_overrides = normalize_template_section_design_overrides(
        normalized.get("design_overrides")
    )
    if design_overrides is not None:
        doc["design_overrides"] = deepcopy(design_overrides)
    if embedded_id:
        doc["template_embedded_section_id"] = embedded_id
    return doc


def _build_section_document_from_embedded_section(section: dict, *, now: datetime) -> dict:
    return build_section_document_from_embedded_section(section, now=now)


def build_section_config_update_from_embedded_section(
    section: dict,
    existing_doc: dict | None,
    *,
    now: datetime,
) -> dict:
    normalized = normalize_embedded_section(section)
    section_type = str(normalized.get("section_type") or "text").strip().lower() or "text"
    previous_type = str(
        (existing_doc or {}).get("section_type") or section_type
    ).strip().lower() or section_type
    section_template_name = normalize_template_name(
        normalized.get("section_template_name") or "default",
        default="default",
    )
    set_patch: dict[str, Any] = {
        "section_type": section_type,
        "section_template_name": section_template_name,
        "section_integration_mapping": normalize_section_integration_mapping(
            normalized.get("section_integration_mapping")
        ),
        "template_embedded_section_id": str(normalized.get("id") or "").strip(),
        "updated_at": now,
    }
    unset_patch: dict[str, str] = {}

    if previous_type != section_type:
        set_patch.update(
            {
                "title_placeholder": normalized["title_placeholder"],
                "title": normalized["title"],
                "type_data": _normalize_section_type_data(
                    section_type,
                    normalized.get("type_data"),
                ),
            }
        )
    else:
        current_type_data = (
            (existing_doc or {}).get("type_data")
            if isinstance((existing_doc or {}).get("type_data"), dict)
            else {}
        )
        set_patch["type_data"] = merge_template_section_config_type_data(
            section_type,
            current_type_data,
            normalized.get("type_data"),
        )

    design_overrides = normalize_template_section_design_overrides(
        normalized.get("design_overrides")
    )
    if design_overrides is None:
        unset_patch["design_overrides"] = ""
    else:
        set_patch["design_overrides"] = deepcopy(design_overrides)

    update: dict[str, dict] = {"$set": set_patch}
    if unset_patch:
        update["$unset"] = unset_patch
    return update


async def _create_managed_section_from_embedded_section(
    db,
    section: dict,
    *,
    now: datetime,
) -> str:
    inserted = await db["sections"].insert_one(
        _build_section_document_from_embedded_section(section, now=now)
    )
    return str(inserted.inserted_id)


async def _materialize_sections(
    db,
    sections_payload: list[dict],
) -> tuple[list[dict], list[str], dict[str, str]]:
    sections_coll = db["sections"]
    now = datetime.utcnow()

    page_sections: list[dict] = []
    managed_ids: list[str] = []
    managed_id_map: dict[str, str] = {}

    sorted_sections = sorted(
        [normalize_embedded_section(section) for section in sections_payload],
        key=lambda section: section.get("order", 0),
    )

    for order_index, section in enumerate(sorted_sections):
        section_doc = _build_section_document_from_embedded_section(section, now=now)
        inserted = await sections_coll.insert_one(section_doc)
        section_id = str(inserted.inserted_id)
        embedded_id = str(section.get("id") or "").strip()
        if embedded_id:
            managed_id_map[embedded_id] = section_id
        managed_ids.append(section_id)

        page_sections.append(
            _build_page_section_ref_from_embedded_section(
                section,
                section_id=section_id,
                order_index=order_index,
            )
        )

    return page_sections, managed_ids, managed_id_map


async def _apply_template_section_config_to_existing_managed_sections(
    db,
    existing_page: dict,
    sections_payload: list[dict],
    *,
    now: datetime,
) -> int:
    sections_coll = db["sections"]
    template_sections = sorted(
        [
            normalize_embedded_section(section)
            for section in sections_payload
            if isinstance(section, dict)
        ],
        key=lambda section: int(section.get("order", 0) or 0),
    )
    existing_map = _resolve_existing_managed_section_id_map(
        existing_page,
        template_sections,
    )
    updated_count = 0

    for section in template_sections:
        embedded_id = str(section.get("id") or "").strip()
        if not embedded_id:
            continue
        section_id = str(existing_map.get(embedded_id) or "").strip()
        section_oid = _safe_object_id(section_id)
        if section_oid is None:
            continue
        existing_section_doc = await sections_coll.find_one({"_id": section_oid})
        if not isinstance(existing_section_doc, dict):
            continue
        await sections_coll.update_one(
            {"_id": section_oid},
            build_section_config_update_from_embedded_section(
                section,
                existing_section_doc,
                now=now,
            ),
        )
        updated_count += 1

    return updated_count


def _normalize_header_payload(header_payload: dict | None) -> dict | None:
    if not isinstance(header_payload, dict):
        return None

    enabled_fields = header_payload.get("enabled_fields")
    if not isinstance(enabled_fields, list):
        enabled_fields = ["title", "subtitle", "cta_buttons", "overlay_image", "background_image"]

    title = header_payload.get("hero_title") if isinstance(header_payload.get("hero_title"), dict) else {"de": "", "en": ""}
    subtitle = header_payload.get("hero_subtitle") if isinstance(header_payload.get("hero_subtitle"), dict) else {"de": "", "en": ""}
    cta_buttons = header_payload.get("cta_buttons") if isinstance(header_payload.get("cta_buttons"), list) else []

    return {
        "header_type": str(header_payload.get("header_type") or "hero"),
        "enabled_fields": enabled_fields,
        "background_media_url": header_payload.get("background_media_url"),
        "background_zoom": float(header_payload.get("background_zoom", 1.0) or 1.0),
        "background_focal_x": float(header_payload.get("background_focal_x", 50.0) or 50.0),
        "background_focal_y": float(header_payload.get("background_focal_y", 50.0) or 50.0),
        "background_rotation": float(header_payload.get("background_rotation", 0.0) or 0.0),
        "overlay_image_url": header_payload.get("overlay_image_url"),
        "overlay_zoom": float(header_payload.get("overlay_zoom", 1.0) or 1.0),
        "overlay_focal_x": float(header_payload.get("overlay_focal_x", 50.0) or 50.0),
        "overlay_focal_y": float(header_payload.get("overlay_focal_y", 50.0) or 50.0),
        "overlay_rotation": float(header_payload.get("overlay_rotation", 0.0) or 0.0),
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
        "design_overrides": normalize_template_header_design_overrides(
            header_payload.get("design_overrides")
        ),
    }


def build_header_document_from_template_header(
    header_payload: dict | None,
    *,
    now: datetime,
) -> dict | None:
    normalized_header = _normalize_header_payload(header_payload)
    if normalized_header is None:
        return None
    return {
        **normalized_header,
        "revision_id": None,
        "created_at": now,
        "updated_at": now,
    }


def build_header_config_update_from_template_header(
    header_payload: dict | None,
    *,
    now: datetime,
) -> dict | None:
    normalized_header = _normalize_header_payload(header_payload)
    if normalized_header is None:
        return None

    set_patch: dict[str, Any] = {
        "header_type": normalized_header["header_type"],
        "enabled_fields": deepcopy(normalized_header["enabled_fields"]),
        "updated_at": now,
    }
    unset_patch: dict[str, str] = {}

    design_overrides = normalized_header.get("design_overrides")
    if design_overrides is None:
        unset_patch["design_overrides"] = ""
    else:
        set_patch["design_overrides"] = deepcopy(design_overrides)

    update: dict[str, dict] = {"$set": set_patch}
    if unset_patch:
        update["$unset"] = unset_patch
    return update


async def _materialize_header(db, header_payload: dict | None, *, existing_header_id: str | None = None) -> str | None:
    normalized_header = _normalize_header_payload(header_payload)
    if normalized_header is None:
        return None

    headers_coll = db["headers"]
    now = datetime.utcnow()
    patch = {
        **normalized_header,
        "updated_at": now,
    }

    existing_oid = _safe_object_id(existing_header_id)
    if existing_oid is not None:
        updated = await headers_coll.find_one_and_update(
            {"_id": existing_oid},
            {"$set": patch},
        )
        if updated:
            return str(existing_oid)

    create_doc = {
        **patch,
        "created_at": now,
        "revision_id": None,
    }
    inserted = await headers_coll.insert_one(create_doc)
    return str(inserted.inserted_id)


async def _apply_template_header_config_to_existing_managed_header(
    db,
    existing_page: dict,
    header_payload: dict | None,
    *,
    now: datetime,
) -> str | None:
    if not isinstance(header_payload, dict):
        return None

    headers_coll = db["headers"]
    header_id = str(
        existing_page.get("template_managed_header_id")
        or existing_page.get("header_id")
        or ""
    ).strip()
    header_oid = _safe_object_id(header_id)

    if header_oid is None:
        return await _materialize_header(db, header_payload, existing_header_id=None)

    existing_header_doc = await headers_coll.find_one({"_id": header_oid})
    if not isinstance(existing_header_doc, dict):
        return await _materialize_header(db, header_payload, existing_header_id=None)

    update = build_header_config_update_from_template_header(header_payload, now=now)
    if update is not None:
        await headers_coll.update_one({"_id": header_oid}, update)
    return str(header_oid)


def _collect_item_page_mapping_targets(
    template_doc: dict,
    *,
    integration_primary_key_path: str | None = None,
) -> list[dict]:
    mapping = resolve_page_integration_mapping_for_template_doc(template_doc)
    source_provider = item_page_mapping_source_provider_for_template_doc(template_doc)
    raw_map = (
        mapping.get("list_mappings_by_collection_path")
        if isinstance(mapping, dict)
        else {}
    )
    targets: list[dict] = []
    if not isinstance(raw_map, dict):
        return targets

    for raw_collection_path, raw_rows in raw_map.items():
        collection_path = _normalize_page_mapping_collection_path(raw_collection_path)
        if not collection_path or not isinstance(raw_rows, list):
            continue
        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            target_path = _normalize_page_mapping_target_path_for_collection(
                collection_path,
                row.get("target_path"),
            )
            if not target_path:
                continue
            source_path = _page_mapping_source_path_for_target(
                row.get("source_path"),
                target_path,
                integration_primary_key_path=integration_primary_key_path,
                source_provider=source_provider,
            )
            target = {
                "collection_path": collection_path,
                "target_path": target_path,
                "source_path": source_path,
            }
            template_section_id = _normalize_page_mapping_row_template_section_id(
                row,
                collection_path,
            )
            if template_section_id:
                target["template_section_id"] = template_section_id
            targets.append(target)
    return targets


def _item_page_mapping_target_key_for_template_doc(
    template_doc: dict,
    target: dict,
) -> str:
    collection_path = str(target.get("collection_path") or "").strip()
    target_path = str(target.get("target_path") or "").strip()
    if not collection_path or not target_path:
        return ""
    if collection_path in {"page", "header"}:
        return _item_page_target_key(
            collection_path=collection_path,
            target_path=target_path,
        )
    if not collection_path.startswith("sections["):
        return ""

    sections_payload = (
        template_doc.get("sections")
        if isinstance(template_doc.get("sections"), list)
        else []
    )
    section_index = _resolve_page_mapping_section_index(
        sections_payload,
        collection_path,
        target,
    )
    source_section = (
        sections_payload[section_index]
        if section_index is not None
        and section_index < len(sections_payload)
        and isinstance(sections_payload[section_index], dict)
        else {}
    )
    resolved_target_path = _resolve_links_social_target_path(source_section, target_path)
    if not resolved_target_path:
        resolved_target_path = target_path
    return _item_page_target_key(
        collection_path=collection_path,
        target_path=target_path,
        resolved_target_path=resolved_target_path,
        source_section=source_section,
        section_index=section_index,
        target=target,
    )


def _item_page_mapping_target_signatures_by_key(
    template_doc: dict | None,
) -> dict[str, tuple[str, str, str, str]]:
    if not isinstance(template_doc, dict):
        return {}
    signatures: dict[str, tuple[str, str, str, str]] = {}
    for target in _collect_item_page_mapping_targets(template_doc):
        key = _item_page_mapping_target_key_for_template_doc(template_doc, target)
        if not key:
            continue
        signatures[key] = (
            str(target.get("collection_path") or "").strip(),
            str(target.get("target_path") or "").strip(),
            str(target.get("source_path") or "").strip(),
            str(target.get("template_section_id") or "").strip(),
        )
    return signatures


def changed_item_page_mapping_target_keys(
    previous_template_doc: dict | None,
    next_template_doc: dict | None,
) -> set[str]:
    previous_mapping = resolve_page_integration_mapping_for_template_doc(
        previous_template_doc or {}
    )
    next_mapping = resolve_page_integration_mapping_for_template_doc(
        next_template_doc or {}
    )
    next_signatures = _item_page_mapping_target_signatures_by_key(next_template_doc)

    if previous_mapping.get("selected_integration_id") != next_mapping.get("selected_integration_id"):
        return set(next_signatures)
    if previous_mapping.get("active_mode") != next_mapping.get("active_mode"):
        return set(next_signatures)
    if _normalize_integration_match_mappings(
        (previous_template_doc or {}).get("integration_match_mappings")
    ) != _normalize_integration_match_mappings(
        (next_template_doc or {}).get("integration_match_mappings")
    ):
        return set(next_signatures)

    previous_signatures = _item_page_mapping_target_signatures_by_key(previous_template_doc)
    changed_keys: set[str] = set()
    for key, signature in next_signatures.items():
        if previous_signatures.get(key) != signature:
            changed_keys.add(key)
    return changed_keys


def _collect_generated_mapped_target_values(
    template_doc: dict,
    *,
    page_payload: dict,
    header_payload: dict | None,
    sections_payload: list[dict],
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    disallowed_page_paths = {"slug", "status", "publish_at", "unpublish_at"}
    for target in _collect_item_page_mapping_targets(template_doc):
        collection_path = str(target.get("collection_path") or "").strip()
        target_path = str(target.get("target_path") or "").strip()
        if not collection_path or not target_path:
            continue
        if collection_path == "page":
            if target_path in disallowed_page_paths:
                continue
            value = _deep_get(page_payload, target_path)
            target_key = _item_page_target_key(
                collection_path=collection_path,
                target_path=target_path,
            )
        elif collection_path == "header":
            value = _deep_get(header_payload or {}, target_path)
            target_key = _item_page_target_key(
                collection_path=collection_path,
                target_path=target_path,
            )
        elif collection_path.startswith("sections["):
            section_index = _resolve_page_mapping_section_index(
                sections_payload,
                collection_path,
                target,
            )
            if section_index is None:
                continue
            source_section = (
                sections_payload[section_index]
                if section_index < len(sections_payload) and isinstance(sections_payload[section_index], dict)
                else {}
            )
            resolved_target_path = _resolve_links_social_target_path(source_section, target_path)
            if not resolved_target_path:
                continue
            value = _deep_get(source_section, resolved_target_path)
            target_key = _item_page_target_key(
                collection_path=collection_path,
                target_path=target_path,
                resolved_target_path=resolved_target_path,
                source_section=source_section,
                section_index=section_index,
                target=target,
            )
        else:
            continue
        if target_key and value is not None:
            values[target_key] = deepcopy(value)
    return values


def _resolve_existing_managed_section_ids(existing_page: dict) -> list[str]:
    managed_ids = existing_page.get("template_managed_section_ids")
    if isinstance(managed_ids, list) and managed_ids:
        normalized = [str(item or "").strip() for item in managed_ids if str(item or "").strip()]
        if normalized:
            return normalized
    page_sections = existing_page.get("sections") if isinstance(existing_page.get("sections"), list) else []
    return [
        str(entry.get("section_id") or "").strip()
        for entry in page_sections
        if isinstance(entry, dict) and str(entry.get("section_id") or "").strip()
    ]


def _resolve_existing_managed_section_id_map(
    existing_page: dict,
    template_sections: list[dict],
) -> dict[str, str]:
    raw_map = existing_page.get("template_managed_section_id_map")
    resolved: dict[str, str] = {}
    if isinstance(raw_map, dict):
        for raw_embedded_id, raw_section_id in raw_map.items():
            embedded_id = str(raw_embedded_id or "").strip()
            section_id = str(raw_section_id or "").strip()
            if embedded_id and section_id:
                resolved[embedded_id] = section_id

    fallback_ids = _resolve_existing_managed_section_ids(existing_page)
    for index, section in enumerate(template_sections):
        embedded_id = str(section.get("id") or "").strip()
        if not embedded_id or embedded_id in resolved:
            continue
        if index < len(fallback_ids) and fallback_ids[index]:
            resolved[embedded_id] = fallback_ids[index]

    return resolved


def _map_template_section_structure_to_page_structure(
    raw_structure: Any,
    embedded_to_page_section_id: dict[str, str],
    ordered_page_section_ids: list[str],
) -> list[dict]:
    mapped_seed: list[dict] = []

    for node in raw_structure if isinstance(raw_structure, list) else []:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type") or "").strip().lower()
        if node_type == "section":
            embedded_id = str(node.get("section_id") or "").strip()
            mapped_section_id = embedded_to_page_section_id.get(embedded_id)
            if mapped_section_id:
                mapped_seed.append(
                    {
                        "type": "section",
                        "section_id": mapped_section_id,
                    }
                )
            continue
        if node_type != "container":
            continue

        mapped_members: list[str] = []
        raw_members = node.get("section_ids") if isinstance(node.get("section_ids"), list) else []
        for raw_member in raw_members:
            mapped_member = embedded_to_page_section_id.get(str(raw_member or "").strip())
            if mapped_member:
                mapped_members.append(mapped_member)
        if mapped_members:
            mapped_seed.append(
                {
                    "type": "container",
                    "container_id": str(node.get("container_id") or "").strip()
                    or f"container_{ObjectId()}",
                    "section_ids": mapped_members,
                }
            )

    return resolve_section_structure(mapped_seed, ordered_page_section_ids)


async def _patch_existing_generated_page_mapped_targets(
    db,
    *,
    existing_page: dict,
    template_doc: dict,
    page_payload: dict,
    header_payload: dict | None,
    sections_payload: list[dict],
    source_payload: dict | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    integration_payload: dict | None = None,
    integration_primary_key_path: str | None = None,
    item_integration_mapping: dict | None = None,
    sync_mode: str = ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
    managed_section_id_map: dict[str, str] | None = None,
    mapped_target_keys: set[str] | None = None,
    dry_run: bool = False,
) -> dict:
    if mapped_target_keys is not None and not mapped_target_keys:
        return {"conflict_count": 0}

    targets = _collect_item_page_mapping_targets(
        template_doc,
        integration_primary_key_path=integration_primary_key_path,
    )
    if not targets:
        return {"conflict_count": 0}

    normalized_sync_mode = normalize_item_page_sync_mode(sync_mode)
    previous_generated_values = _mapped_target_values_for_page(
        existing_page,
        ITEM_PAGE_MAPPED_TARGET_VALUES_KEY,
    )
    previous_local_overrides = _mapped_target_values_for_page(
        existing_page,
        ITEM_PAGE_LOCAL_MAPPED_OVERRIDES_KEY,
    )
    next_generated_values = deepcopy(previous_generated_values)
    next_local_overrides = deepcopy(previous_local_overrides)
    conflict_count = 0

    def resolve_value(
        target_key: str,
        current_value: Any,
        generated_value: Any,
    ) -> tuple[Any, bool]:
        nonlocal conflict_count
        has_previous = target_key in previous_generated_values
        previous_value = previous_generated_values.get(target_key)
        has_conflict = _is_local_mapped_conflict(
            current_value=current_value,
            generated_value=generated_value,
            previous_generated_value=previous_value,
            has_previous_generated_value=has_previous,
        )
        next_generated_values[target_key] = deepcopy(generated_value)
        if not has_conflict:
            next_local_overrides.pop(target_key, None)
            return generated_value, True

        conflict_count += 1
        if normalized_sync_mode == ITEM_PAGE_SYNC_MODE_KEEP_LOCAL:
            next_local_overrides[target_key] = deepcopy(current_value)
            return current_value, False

        next_local_overrides.pop(target_key, None)
        return generated_value, True

    page_updates: dict[str, Any] = {}
    disallowed_page_paths = {"slug", "status", "publish_at", "unpublish_at"}
    for target in targets:
        if target.get("collection_path") != "page":
            continue
        target_path = str(target.get("target_path") or "").strip()
        if target_path in disallowed_page_paths:
            continue
        value = _deep_get(page_payload, target_path)
        if value is None:
            continue
        target_key = _item_page_target_key(
            collection_path="page",
            target_path=target_path,
        )
        if not target_key:
            continue
        if mapped_target_keys is not None and target_key not in mapped_target_keys:
            continue
        current_value = _deep_get(existing_page, target_path)
        resolved_value, should_write = resolve_value(
            target_key,
            current_value,
            value,
        )
        if should_write:
            page_updates[target_path] = deepcopy(resolved_value)
    if page_updates and not dry_run:
        await db["pages"].update_one(
            {"_id": existing_page.get("_id")},
            {"$set": {**page_updates, "updated_at": datetime.utcnow()}},
        )

    header_updates: dict[str, Any] = {}
    header_id = _safe_object_id(
        existing_page.get("template_managed_header_id")
        or existing_page.get("header_id")
    )
    header_doc = (
        await db["headers"].find_one({"_id": header_id})
        if header_id is not None
        else None
    )
    for target in targets:
        if target.get("collection_path") != "header":
            continue
        target_path = str(target.get("target_path") or "").strip()
        value = _deep_get(header_payload or {}, target_path)
        if value is None:
            continue
        target_key = _item_page_target_key(
            collection_path="header",
            target_path=target_path,
        )
        if not target_key:
            continue
        if mapped_target_keys is not None and target_key not in mapped_target_keys:
            continue
        current_value = _deep_get(header_doc or {}, target_path)
        resolved_value, should_write = resolve_value(
            target_key,
            current_value,
            value,
        )
        if should_write:
            header_updates[target_path] = deepcopy(resolved_value)
    if header_updates and not dry_run:
        if header_id is not None:
            await db["headers"].update_one(
                {"_id": header_id},
                {"$set": {**header_updates, "updated_at": datetime.utcnow()}},
            )

    managed_section_ids = _resolve_existing_managed_section_ids(existing_page)
    for target in targets:
        collection_path = str(target.get("collection_path") or "").strip()
        if not collection_path.startswith("sections["):
            continue
        section_index = _resolve_page_mapping_section_index(
            sections_payload,
            collection_path,
            target,
        )
        if section_index is None:
            continue
        source_section = (
            sections_payload[section_index]
            if section_index < len(sections_payload) and isinstance(sections_payload[section_index], dict)
            else {}
        )
        section_id = ""
        if isinstance(managed_section_id_map, dict):
            embedded_id = str(
                source_section.get("id")
                or target.get("template_section_id")
                or ""
            ).strip()
            section_id = str(managed_section_id_map.get(embedded_id) or "").strip()
        if not section_id:
            if section_index < 0 or section_index >= len(managed_section_ids):
                continue
            section_id = str(managed_section_ids[section_index] or "").strip()
        section_oid = _safe_object_id(section_id)
        if section_oid is None:
            continue
        section_doc = await db["sections"].find_one({"_id": section_oid})
        section_updates: dict[str, Any] = {}
        target_path = str(target.get("target_path") or "").strip()
        resolved_target_path = _resolve_links_social_target_path(source_section, target_path)
        if not resolved_target_path:
            continue
        value = _deep_get(source_section, resolved_target_path)
        if value is None:
            continue
        target_key = _item_page_target_key(
            collection_path=collection_path,
            target_path=target_path,
            resolved_target_path=resolved_target_path,
            source_section=source_section,
            section_index=section_index,
            target=target,
        )
        if not target_key:
            continue
        if mapped_target_keys is not None and target_key not in mapped_target_keys:
            continue
        current_value = _deep_get(section_doc or {}, resolved_target_path)
        resolved_value, should_write = resolve_value(
            target_key,
            current_value,
            value,
        )
        if should_write:
            section_updates[resolved_target_path] = deepcopy(resolved_value)
            if _is_fixed_gig_mapping_target_path(resolved_target_path):
                section_type = normalize_section_type_value(source_section.get("section_type"), default="") or ""
                if section_type == "program":
                    section_updates["type_data.fixed_day"] = ""
                    section_updates["type_data.fixed_stage_id"] = ""
        if section_updates and not dry_run:
            await db["sections"].update_one(
                {"_id": section_oid},
                {"$set": {**section_updates, "updated_at": datetime.utcnow()}},
            )

    if dry_run:
        return {"conflict_count": conflict_count}

    mapped_state_update: dict[str, Any] = {
        ITEM_PAGE_MAPPED_TARGET_VALUES_KEY: next_generated_values,
        "template_mapped_target_values_updated_at": datetime.utcnow(),
    }
    mapped_state_unset: dict[str, str] = {}
    if next_local_overrides:
        mapped_state_update[ITEM_PAGE_LOCAL_MAPPED_OVERRIDES_KEY] = next_local_overrides
    else:
        mapped_state_unset[ITEM_PAGE_LOCAL_MAPPED_OVERRIDES_KEY] = ""
    update_doc: dict[str, dict] = {"$set": mapped_state_update}
    if mapped_state_unset:
        update_doc["$unset"] = mapped_state_unset
    await db["pages"].update_one({"_id": existing_page.get("_id")}, update_doc)
    return {"conflict_count": conflict_count}


def _path_intersects_updated_paths(target_path: Any, updated_paths: set[str] | None) -> bool:
    if not updated_paths:
        return True
    normalized_target = str(target_path or "").strip()
    if not normalized_target:
        return False
    for raw_path in updated_paths:
        updated_path = str(raw_path or "").strip()
        if not updated_path:
            continue
        if (
            normalized_target == updated_path
            or normalized_target.startswith(f"{updated_path}.")
            or updated_path.startswith(f"{normalized_target}.")
        ):
            return True
    return False


async def _load_generated_page_for_mapped_document(
    db,
    *,
    collection: str,
    document_id: Any,
    page_doc: dict | None = None,
) -> list[dict]:
    if collection == "page":
        if isinstance(page_doc, dict):
            return [page_doc]
        page_oid = _safe_object_id(document_id)
        if page_oid is None:
            return []
        doc = await db["pages"].find_one({"_id": page_oid})
        return [doc] if isinstance(doc, dict) else []

    normalized_id = str(document_id or "").strip()
    if not normalized_id:
        return []
    if collection == "header":
        query = {
            "template_managed": True,
            "$or": [
                {"template_managed_header_id": normalized_id},
                {"header_id": normalized_id},
            ],
        }
    elif collection == "section":
        query = {
            "template_managed": True,
            "$or": [
                {"template_managed_section_ids": normalized_id},
                {"sections.section_id": normalized_id},
            ],
        }
    else:
        return []
    return await db["pages"].find(query).to_list(length=50)


async def _sync_generated_page_review_overrides_for_saved_targets(
    db,
    page_doc: dict,
    *,
    collection: str,
    document_id: Any = None,
    saved_doc: dict | None = None,
    updated_paths: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(page_doc, dict) or page_doc.get("template_managed") is not True:
        return {"write_count": 0, "warnings": []}

    template_doc = await _resolve_template_doc_for_generated_page(db, page_doc)
    if not isinstance(template_doc, dict):
        return {"write_count": 0, "warnings": [{"code": "template_missing"}]}
    if _item_page_mapping_uses_shared_items(template_doc):
        return {"write_count": 0, "warnings": []}
    source_payload = await _resolve_source_payload_for_generated_page(db, page_doc)
    if not isinstance(source_payload, dict):
        return {"write_count": 0, "warnings": [{"code": "source_missing"}]}

    warnings: list[dict] = []
    integration_rows = await _load_integration_rows_for_template(
        db,
        template_doc,
        warning_collector=warnings,
        source_id=str(page_doc.get("template_source_id") or ""),
        source_type=str(page_doc.get("template_source_type") or ""),
    )
    integration_id = _selected_mapping_integration_id(template_doc)
    integration_oid = _safe_object_id(integration_id)
    integration_doc = (
        await db["integration_config"].find_one({"_id": integration_oid})
        if integration_oid is not None
        else None
    )
    if not isinstance(integration_doc, dict):
        return {"write_count": 0, "warnings": warnings}
    if bool(integration_doc.get("item_page_sync_blocked", False)):
        return {"write_count": 0, "warnings": warnings, "blocked": True}

    output_primary_key_path = str(integration_doc.get("output_primary_key_path") or "").strip()
    stored_item_key = str(page_doc.get("template_integration_item_key") or "").strip()
    integration_payload = _integration_row_for_review_item_key(
        integration_rows,
        output_primary_key_path=output_primary_key_path,
        item_key=stored_item_key,
    )
    if integration_payload is None and stored_item_key:
        return {
            "write_count": 0,
            "warnings": [
                *warnings,
                {
                    "code": "integration_row_key_missing",
                    "message": "Generated page review writeback skipped because its stored integration item key could not be resolved.",
                },
            ],
        }
    if integration_payload is None:
        integration_payload = _resolve_integration_row_for_source(
            template_doc,
            source_payload,
            integration_rows,
            warning_collector=warnings,
            source_id=str(page_doc.get("template_source_id") or ""),
            source_type=str(page_doc.get("template_source_type") or ""),
        )
    if not isinstance(integration_payload, dict):
        return {"write_count": 0, "warnings": warnings}

    item_key = (
        review_item_key_for_row(integration_payload, output_primary_key_path)
        if output_primary_key_path
        else REVIEW_ROOT_ITEM_KEY
    )
    if not item_key:
        return {"write_count": 0, "warnings": warnings}

    targets = _collect_item_page_mapping_targets(
        template_doc,
        integration_primary_key_path=output_primary_key_path,
    )
    if not targets:
        return {"write_count": 0, "warnings": warnings}

    normalized_collection = str(collection or "").strip().lower()
    normalized_document_id = str(document_id or (saved_doc or {}).get("_id") or "").strip()
    header_doc: dict | None = None
    section_docs_by_id: dict[str, dict] = {}
    managed_section_ids = _resolve_existing_managed_section_ids(page_doc)
    managed_section_id_map = (
        page_doc.get("template_managed_section_id_map")
        if isinstance(page_doc.get("template_managed_section_id_map"), dict)
        else {}
    )
    sections_payload = template_doc.get("sections") if isinstance(template_doc.get("sections"), list) else []
    next_generated_values = _mapped_target_values_for_page(
        page_doc,
        ITEM_PAGE_MAPPED_TARGET_VALUES_KEY,
    )
    next_local_overrides = _mapped_target_values_for_page(
        page_doc,
        ITEM_PAGE_LOCAL_MAPPED_OVERRIDES_KEY,
    )
    write_count = 0

    for target in targets:
        source_path = str(target.get("source_path") or "").strip()
        if not source_path.startswith("integration."):
            continue
        field_path = _strip_mapping_integration_prefix(source_path)
        if not field_path:
            continue

        collection_path = str(target.get("collection_path") or "").strip()
        target_path = str(target.get("target_path") or "").strip()
        target_doc: dict | None = None
        target_key = ""
        resolved_target_path = target_path

        if normalized_collection == "page" and collection_path == "page":
            if target_path in {"slug", "status", "publish_at", "unpublish_at"}:
                continue
            target_doc = saved_doc if isinstance(saved_doc, dict) else page_doc
            target_key = _item_page_target_key(
                collection_path="page",
                target_path=target_path,
            )
        elif normalized_collection == "header" and collection_path == "header":
            if header_doc is None:
                header_oid = _safe_object_id(
                    page_doc.get("template_managed_header_id") or page_doc.get("header_id")
                )
                header_doc = (
                    await db["headers"].find_one({"_id": header_oid})
                    if header_oid is not None
                    else {}
                )
            target_doc = saved_doc if isinstance(saved_doc, dict) else header_doc
            target_key = _item_page_target_key(
                collection_path="header",
                target_path=target_path,
            )
        elif normalized_collection == "section" and collection_path.startswith("sections["):
            section_index = _resolve_page_mapping_section_index(
                sections_payload,
                collection_path,
                target,
            )
            if section_index is None:
                continue
            source_section = (
                sections_payload[section_index]
                if section_index < len(sections_payload) and isinstance(sections_payload[section_index], dict)
                else {}
            )
            section_id = str(
                managed_section_id_map.get(str(source_section.get("id") or target.get("template_section_id") or "").strip())
                or ""
            ).strip()
            if not section_id and section_index < len(managed_section_ids):
                section_id = str(managed_section_ids[section_index] or "").strip()
            if not section_id or section_id != normalized_document_id:
                continue
            resolved_target_path = _resolve_links_social_target_path(source_section, target_path)
            if not resolved_target_path:
                continue
            if isinstance(saved_doc, dict):
                target_doc = saved_doc
            else:
                if section_id not in section_docs_by_id:
                    section_oid = _safe_object_id(section_id)
                    section_docs_by_id[section_id] = (
                        await db["sections"].find_one({"_id": section_oid})
                        if section_oid is not None
                        else {}
                    ) or {}
                target_doc = section_docs_by_id.get(section_id)
            target_key = _item_page_target_key(
                collection_path=collection_path,
                target_path=target_path,
                resolved_target_path=resolved_target_path,
                source_section=source_section,
                section_index=section_index,
                target=target,
            )
        else:
            continue

        if not target_key or not isinstance(target_doc, dict):
            continue
        if _is_fixed_gig_mapping_target_path(resolved_target_path):
            continue
        if not _path_intersects_updated_paths(resolved_target_path, updated_paths):
            continue
        current_value = _deep_get(target_doc, resolved_target_path)
        if current_value is None:
            continue
        review_value = _unwrap_quill_plain_block_for_review(current_value)

        try:
            await upsert_integration_review_override(
                db,
                integration_id=integration_id,
                item_key=item_key,
                field_path=field_path,
                value=review_value,
                integration_doc=integration_doc,
            )
        except IntegrationReviewError as exc:
            warnings.append(
                {
                    "code": "integration_review_override_write_failed",
                    "message": str(exc),
                    "source_path": source_path,
                }
            )
            continue

        set_integration_review_value_at_path(integration_payload, field_path, review_value)
        next_generated_values[target_key] = deepcopy(review_value)
        next_local_overrides.pop(target_key, None)
        write_count += 1

    if write_count:
        mapped_state_update: dict[str, Any] = {
            ITEM_PAGE_MAPPED_TARGET_VALUES_KEY: next_generated_values,
            "template_mapped_target_values_updated_at": datetime.utcnow(),
            "template_mapped_source_hash": _compute_item_page_source_payload_hash(
                source_payload,
                integration_payload,
            ),
        }
        mapped_state_unset: dict[str, str] = {}
        if next_local_overrides:
            mapped_state_update[ITEM_PAGE_LOCAL_MAPPED_OVERRIDES_KEY] = next_local_overrides
        else:
            mapped_state_unset[ITEM_PAGE_LOCAL_MAPPED_OVERRIDES_KEY] = ""
        update_doc: dict[str, dict] = {"$set": mapped_state_update}
        if mapped_state_unset:
            update_doc["$unset"] = mapped_state_unset
        await db["pages"].update_one({"_id": page_doc.get("_id")}, update_doc)

    return {"write_count": write_count, "warnings": warnings}


async def sync_generated_item_page_review_overrides_for_saved_targets(
    db,
    *,
    collection: str,
    document_id: Any,
    saved_doc: dict | None = None,
    updated_paths: set[str] | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    normalized_paths = (
        {str(path or "").strip() for path in updated_paths if str(path or "").strip()}
        if isinstance(updated_paths, (set, list, tuple))
        else None
    )
    page_docs = await _load_generated_page_for_mapped_document(
        db,
        collection=str(collection or "").strip().lower(),
        document_id=document_id,
        page_doc=saved_doc if str(collection or "").strip().lower() == "page" else None,
    )
    total_writes = 0
    blocked_count = 0
    warnings: list[dict] = []
    for page_doc in page_docs:
        result = await _sync_generated_page_review_overrides_for_saved_targets(
            db,
            page_doc,
            collection=str(collection or "").strip().lower(),
            document_id=document_id,
            saved_doc=saved_doc,
            updated_paths=normalized_paths,
        )
        total_writes += int(result.get("write_count") or 0)
        if result.get("blocked"):
            blocked_count += 1
        result_warnings = result.get("warnings")
        if isinstance(result_warnings, list):
            warnings.extend(result_warnings)
    return {"write_count": total_writes, "blocked_count": blocked_count, "warnings": warnings[:50]}


def _is_item_page_template_doc(template_doc: dict | None) -> bool:
    if not isinstance(template_doc, dict):
        return False
    template_kind = str(template_doc.get("template_kind") or "").strip().lower()
    if template_kind == "item_page":
        return True
    if normalize_parent_route(template_doc.get("parent_route")):
        return True
    source_type = str(template_doc.get("source_type") or "").strip().lower()
    return source_type in {"blog", "tiles", "program"}


async def _resolve_template_doc_for_generated_page(db, page_doc: dict) -> dict | None:
    candidates: list[tuple[str, str | None]] = []

    template_style_ref = str(page_doc.get("template_style_ref") or "").strip().strip("/")
    if template_style_ref:
        try:
            candidates.append(parse_page_template_path(template_style_ref))
        except Exception:
            pass

    template_name = str(page_doc.get("template_template_name") or "").strip().lower()
    if template_name:
        candidates.append(
            (
                normalize_template_name(template_name, default="default"),
                normalize_parent_route(page_doc.get("template_parent_route")),
            )
        )

    seen: set[tuple[str, str | None]] = set()
    for candidate_name, candidate_parent_route in candidates:
        key = (candidate_name, candidate_parent_route)
        if key in seen:
            continue
        seen.add(key)
        doc = await db[TEMPLATE_PAGES_COLLECTION].find_one(
            {
                "template_name": candidate_name,
                "parent_route": candidate_parent_route,
            }
        )
        if isinstance(doc, dict):
            return doc
    return None


async def _resolve_source_payload_for_generated_page(db, page_doc: dict) -> dict | None:
    source_type = str(page_doc.get("template_source_type") or "").strip().lower()
    source_id = str(page_doc.get("template_source_id") or "").strip()
    if not source_type or not source_id:
        return None

    if source_type == "blog":
        oid = _safe_object_id(source_id)
        if oid is None:
            return None
        item_doc = await db["blog_shared"].find_one({"_id": oid})
        return _source_payload_from_blog_item(item_doc) if isinstance(item_doc, dict) else None

    if source_type == "tiles" and source_id.startswith("tiles:"):
        try:
            _, section_id, tile_id = source_id.split(":", 2)
        except ValueError:
            return None
        section_oid = _safe_object_id(section_id)
        if section_oid is None or not tile_id:
            return None
        section_doc = await db["sections"].find_one({"_id": section_oid})
        if not isinstance(section_doc, dict):
            return None
        type_data = section_doc.get("type_data") if isinstance(section_doc.get("type_data"), dict) else {}
        tiles = type_data.get("tiles") if isinstance(type_data.get("tiles"), list) else []
        tile = next(
            (
                item
                for item in tiles
                if isinstance(item, dict) and str(item.get("id") or "").strip() == tile_id
            ),
            None,
        )
        return _source_payload_from_tile(section_doc, tile) if isinstance(tile, dict) else None

    source_program_gig_id = (
        str(source_id.removeprefix("program:gig:") or "").strip()
        if source_type == "program_gig" and source_id.startswith("program:gig:")
        else None
    )
    shared_doc = await program_catalog.capture_program_shared_content(
        db,
        gig_id=source_program_gig_id,
    )
    raw_stages = (
        shared_doc.get("stages")
        if isinstance(shared_doc, dict) and isinstance(shared_doc.get("stages"), list)
        else []
    )
    raw_gigs = (
        shared_doc.get("gigs")
        if isinstance(shared_doc, dict) and isinstance(shared_doc.get("gigs"), list)
        else []
    )
    shared_gig_primary_key_path = program_catalog.integration_output_primary_key_path_from_cache_state(
        shared_doc.get("program_gigs_integration_mapping_cache_state")
        if isinstance(shared_doc, dict)
        else None
    )
    shared_gig_selected_integration_id = program_catalog.integration_selected_id_from_mapping(
        shared_doc.get("program_gigs_integration_mapping")
        if isinstance(shared_doc, dict)
        else None
    )
    gig_index_by_id = {
        str(gig_id or "").strip(): index
        for index, gig_id in enumerate(
            shared_doc.get("gig_ids")
            if isinstance(shared_doc, dict) and isinstance(shared_doc.get("gig_ids"), list)
            else []
        )
        if str(gig_id or "").strip()
    }
    stages = [
        _normalize_program_stage_for_sync(raw_stage, index)
        for index, raw_stage in enumerate(raw_stages)
    ]
    gigs = []
    for index, raw_gig in enumerate(raw_gigs):
        normalized_id = ""
        if isinstance(raw_gig, dict):
            normalized_id = str(raw_gig.get("id") or raw_gig.get("_id") or "").strip()
        normalized_index = gig_index_by_id.get(normalized_id, index)
        gigs.append(
            _normalize_program_gig_for_sync(
                raw_gig,
                normalized_index,
                primary_key_path=shared_gig_primary_key_path,
                selected_integration_id=shared_gig_selected_integration_id,
            )
        )

    if source_type == "program_stage" and source_id.startswith("program:stage:"):
        item_id = str(source_id.removeprefix("program:stage:") or "").strip()
        stage = next(
            (
                item
                for item in stages
                if isinstance(item, dict) and str(item.get("id") or "").strip() == item_id
            ),
            None,
        )
        return _source_payload_from_program_stage(stage) if isinstance(stage, dict) else None

    if source_type == "program_gig" and source_id.startswith("program:gig:"):
        item_id = str(source_id.removeprefix("program:gig:") or "").strip()
        stage_titles_by_id = build_program_stage_titles_lookup(stages)
        gig = next(
            (
                item
                for item in gigs
                if isinstance(item, dict) and str(item.get("id") or "").strip() == item_id
            ),
            None,
        )
        return (
            _source_payload_from_program_gig(gig, stage_titles_by_id=stage_titles_by_id)
            if isinstance(gig, dict)
            else None
        )

    return None


async def sync_generated_item_page_from_template_state(
    db,
    page_doc: dict,
    *,
    template_doc: dict | None = None,
    sync_mode: str = ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
    mapped_target_keys: set[str] | None = None,
    force_rebuild: bool = False,
    check_conflicts_only: bool = False,
) -> dict:
    if not isinstance(page_doc, dict) or page_doc.get("template_managed") is not True:
        raise ValueError("Page is not a generated template-managed item page")

    resolved_template = (
        template_doc
        if isinstance(template_doc, dict)
        else await _resolve_template_doc_for_generated_page(db, page_doc)
    )
    if not isinstance(resolved_template, dict):
        raise ValueError("Source item-page template was not found")
    if not _is_item_page_template_doc(resolved_template):
        raise ValueError("Source template is not an item-page template")
    uses_shared_items = _item_page_mapping_uses_shared_items(resolved_template)

    now = datetime.utcnow()
    pages_coll = db["pages"]
    sections_coll = db["sections"]
    working_page = page_doc
    warnings: list[dict] = []
    template_integration_id = (
        ""
        if uses_shared_items
        else str(page_doc.get("template_integration_id") or "").strip()
    )
    template_integration_item_key = (
        ""
        if uses_shared_items
        else str(page_doc.get("template_integration_item_key") or "").strip()
    )
    if not check_conflicts_only and template_integration_id and template_integration_item_key:
        await _cleanup_legacy_page_slug_source_override(
            db,
            integration_id=template_integration_id,
            item_key=template_integration_item_key,
            slug=str(working_page.get("slug") or "").strip(),
        )

    source_payload = await _resolve_source_payload_for_generated_page(db, page_doc)
    if check_conflicts_only:
        force_rebuild = False

    if force_rebuild:
        if not isinstance(source_payload, dict):
            raise ValueError("Source item data was not found")

        source_type = str(page_doc.get("template_source_type") or "").strip().lower()
        source_id = str(page_doc.get("template_source_id") or "").strip()
        source_parent_id = str(
            page_doc.get("template_source_parent_id")
            or page_doc.get("template_parent_route")
            or ""
        ).strip()
        effective_parent_route = normalize_parent_route(
            source_parent_id
            or effective_item_page_parent_route_for_template(resolved_template)
            or resolved_template.get("parent_route")
        )
        desired_slug = str(page_doc.get("slug") or "").strip()
        if source_type == "program_stage":
            desired_slug = _preferred_slug_for_program_stage(
                source_payload,
                effective_parent_route,
                slug_source_field=normalize_item_page_slug_field(
                    "program",
                    "stage",
                    resolved_template.get("item_page_slug_field"),
                ),
            )
        elif source_type == "program_gig":
            desired_slug = _preferred_slug_for_program_gig(
                source_payload,
                effective_parent_route,
                slug_source_field=normalize_item_page_slug_field(
                    "program",
                    "gig",
                    resolved_template.get("item_page_slug_field"),
                ),
            )

        item_integration_mapping = None
        if source_type == "program_stage":
            item_integration_mapping = await _load_program_item_integration_mapping_for_sync(
                db,
                None,
                kind="stage",
            )
        elif source_type == "program_gig":
            item_integration_mapping = await _load_program_item_integration_mapping_for_sync(
                db,
                None,
                kind="gig",
            )

        final_slug = await _sync_generated_page_from_template(
            db,
            template_doc=resolved_template,
            source_payload=source_payload,
            source_type=source_type,
            source_id=source_id,
            desired_slug=desired_slug,
            source_parent_id=effective_parent_route,
            item_integration_mapping=item_integration_mapping,
            warning_collector=warnings,
            force_rebuild=True,
            sync_mode=sync_mode,
        )
        refreshed_page = await pages_coll.find_one({"_id": page_doc.get("_id")})
        if isinstance(refreshed_page, dict):
            working_page = refreshed_page
        template_name = normalize_template_name(
            resolved_template.get("template_name") or "default",
            default="default",
        )
        parent_route = normalize_parent_route(resolved_template.get("parent_route"))
        return {
            "ok": bool(final_slug),
            "page_id": str(working_page.get("_id") or page_doc.get("_id") or ""),
            "slug": str(final_slug or working_page.get("slug") or page_doc.get("slug") or ""),
            "template_path": compose_page_template_path(template_name, parent_route),
            "managed_section_count": len(_resolve_existing_managed_section_ids(working_page)),
            "created_section_count": 0,
            "updated_section_count": 0,
            "removed_section_count": 0,
            "warnings": warnings,
            "force_rebuild": True,
        }

    if isinstance(source_payload, dict):
        source_type = str(page_doc.get("template_source_type") or "").strip().lower()
        source_id = str(page_doc.get("template_source_id") or "").strip()
        integration_rows: list[dict] = []
        integration_primary_key_path = ""
        integration_payload = None
        if not uses_shared_items:
            integration_rows = await _load_integration_rows_for_template(
                db,
                resolved_template,
                warning_collector=warnings,
                source_id=source_id,
                source_type=source_type,
            )
            integration_primary_key_path = await _load_selected_mapping_integration_primary_key_path(
                db,
                resolved_template,
            )
            stored_integration_item_key = str(page_doc.get("template_integration_item_key") or "").strip()
            integration_payload = _integration_row_for_review_item_key(
                integration_rows,
                output_primary_key_path=integration_primary_key_path,
                item_key=stored_integration_item_key,
            )
        if integration_payload is None and mapped_target_keys is not None:
            if not uses_shared_items:
                _append_sync_warning(
                    warnings,
                    code="integration_row_key_missing",
                    message="Generated page mapped-field sync skipped because its stored integration item key could not be resolved.",
                    source_id=source_id,
                    source_type=source_type,
                    template_name=str(resolved_template.get("template_name") or ""),
                    parent_route=normalize_parent_route(resolved_template.get("parent_route")),
                )
                template_name = normalize_template_name(
                    resolved_template.get("template_name") or "default",
                    default="default",
                )
                parent_route = normalize_parent_route(resolved_template.get("parent_route"))
                return {
                    "ok": True,
                    "page_id": str(working_page.get("_id") or ""),
                    "slug": str(working_page.get("slug") or ""),
                    "template_path": compose_page_template_path(template_name, parent_route),
                    "managed_section_count": len(_resolve_existing_managed_section_ids(working_page)),
                    "created_section_count": 0,
                    "updated_section_count": 0,
                    "removed_section_count": 0,
                    "warnings": warnings,
                    "skipped": True,
                }
        if integration_payload is None and not uses_shared_items:
            integration_payload = _resolve_integration_row_for_source(
                resolved_template,
                source_payload,
                integration_rows,
                warning_collector=warnings,
                source_id=source_id,
                source_type=source_type,
            )
        if not uses_shared_items:
            resolved_integration_id, resolved_integration_item_key, _integration_doc = (
                await _resolve_integration_review_locator_for_mapping(
                    db,
                    template_doc=resolved_template,
                    integration_payload=integration_payload,
                )
            )
            template_integration_id = resolved_integration_id or template_integration_id
            template_integration_item_key = resolved_integration_item_key or template_integration_item_key
        if template_integration_id and template_integration_item_key and isinstance(integration_payload, dict):
            page_slug_path = await _load_integration_page_slug_write_path(db, template_integration_id)
            if page_slug_path:
                set_integration_review_value_at_path(
                    integration_payload,
                    page_slug_path,
                    str(working_page.get("slug") or "").strip(),
                )
        item_integration_mapping = None
        if source_type == "program_stage":
            item_integration_mapping = await _load_program_item_integration_mapping_for_sync(
                db,
                None,
                kind="stage",
            )
        elif source_type == "program_gig":
            item_integration_mapping = await _load_program_item_integration_mapping_for_sync(
                db,
                None,
                kind="gig",
            )
        page_payload, header_payload, sections_payload = _apply_item_mappings(
            resolved_template,
            source_payload,
            integration_payload=integration_payload,
            integration_primary_key_path=integration_primary_key_path,
            item_integration_mapping=item_integration_mapping,
            warning_collector=warnings,
            source_id=source_id,
            source_type=source_type,
        )
        managed_map_for_mapped_targets = _resolve_existing_managed_section_id_map(
            working_page,
            [
                normalize_embedded_section(section)
                for section in sections_payload
                if isinstance(section, dict)
            ],
        )
        mapped_sync_report = await _patch_existing_generated_page_mapped_targets(
            db,
            existing_page=working_page,
            template_doc=resolved_template,
            page_payload=page_payload,
            header_payload=header_payload,
            sections_payload=sections_payload,
            source_payload=source_payload,
            source_type=source_type,
            source_id=source_id,
            integration_payload=integration_payload,
            integration_primary_key_path=integration_primary_key_path,
            item_integration_mapping=item_integration_mapping,
            sync_mode=sync_mode,
            managed_section_id_map=managed_map_for_mapped_targets,
            mapped_target_keys=mapped_target_keys,
            dry_run=check_conflicts_only,
        )
        refreshed = await pages_coll.find_one({"_id": working_page.get("_id")})
        if isinstance(refreshed, dict):
            working_page = refreshed
        if check_conflicts_only or mapped_target_keys is not None:
            template_name = normalize_template_name(
                resolved_template.get("template_name") or "default",
                default="default",
            )
            parent_route = normalize_parent_route(resolved_template.get("parent_route"))
            conflict_count = int(mapped_sync_report.get("conflict_count", 0) or 0)
            return {
                "ok": True,
                "page_id": str(working_page.get("_id") or ""),
                "slug": str(working_page.get("slug") or ""),
                "template_path": compose_page_template_path(template_name, parent_route),
                "managed_section_count": len(_resolve_existing_managed_section_ids(working_page)),
                "created_section_count": 0,
                "updated_section_count": 0,
                "removed_section_count": 0,
                "conflict_count": conflict_count,
                "mapped_sync_report": mapped_sync_report,
                "warnings": warnings,
                "check_only": bool(check_conflicts_only),
            }
    else:
        if check_conflicts_only or mapped_target_keys is not None:
            template_name = normalize_template_name(
                resolved_template.get("template_name") or "default",
                default="default",
            )
            parent_route = normalize_parent_route(resolved_template.get("parent_route"))
            return {
                "ok": True,
                "page_id": str(working_page.get("_id") or ""),
                "slug": str(working_page.get("slug") or ""),
                "template_path": compose_page_template_path(template_name, parent_route),
                "managed_section_count": len(_resolve_existing_managed_section_ids(working_page)),
                "created_section_count": 0,
                "updated_section_count": 0,
                "removed_section_count": 0,
                "conflict_count": 0,
                "mapped_sync_report": {"conflict_count": 0},
                "warnings": [{"code": "source_missing"}],
                "check_only": bool(check_conflicts_only),
            }
        header_payload = (
            deepcopy(resolved_template.get("header"))
            if isinstance(resolved_template.get("header"), dict)
            else None
        )
        sections_payload = deepcopy(resolved_template.get("sections") or [])

    managed_header_id = None
    if bool(resolved_template.get("has_header")):
        managed_header_id = await _apply_template_header_config_to_existing_managed_header(
            db,
            working_page,
            header_payload,
            now=now,
        )

    template_sections = sorted(
        [
            normalize_embedded_section(section)
            for section in sections_payload
            if isinstance(section, dict)
        ],
        key=lambda section: int(section.get("order", 0) or 0),
    )
    existing_map = _resolve_existing_managed_section_id_map(
        working_page,
        template_sections,
    )
    existing_refs = (
        working_page.get("sections")
        if isinstance(working_page.get("sections"), list)
        else []
    )
    old_managed_ids = set(_resolve_existing_managed_section_ids(working_page))

    next_refs: list[dict] = []
    next_managed_ids: list[str] = []
    next_managed_id_map: dict[str, str] = {}
    created_count = 0
    updated_count = 0

    for order_index, section in enumerate(template_sections):
        embedded_id = str(section.get("id") or "").strip()
        if not embedded_id:
            continue

        section_id = str(existing_map.get(embedded_id) or "").strip()
        section_oid = _safe_object_id(section_id)
        existing_section_doc = None
        if section_oid is not None:
            existing_section_doc = await sections_coll.find_one({"_id": section_oid})

        if not section_id or section_oid is None or not isinstance(existing_section_doc, dict):
            section_id = await _create_managed_section_from_embedded_section(
                db,
                section,
                now=now,
            )
            created_count += 1
        else:
            await sections_coll.update_one(
                {"_id": section_oid},
                build_section_config_update_from_embedded_section(
                    section,
                    existing_section_doc,
                    now=now,
                ),
            )
            updated_count += 1

        next_managed_ids.append(section_id)
        next_managed_id_map[embedded_id] = section_id
        next_refs.append(
            _build_page_section_ref_from_embedded_section(
                section,
                section_id=section_id,
                order_index=order_index,
            )
        )

    next_managed_id_set = set(next_managed_ids)
    extra_refs: list[dict] = []
    for ref in sorted(existing_refs, key=lambda item: int(item.get("order", 0) or 0) if isinstance(item, dict) else 0):
        if not isinstance(ref, dict):
            continue
        section_id = str(ref.get("section_id") or "").strip()
        if not section_id or section_id in next_managed_id_set or section_id in old_managed_ids:
            continue
        extra_ref = deepcopy(ref)
        extra_ref["order"] = len(next_refs) + len(extra_refs)
        extra_refs.append(extra_ref)

    next_refs.extend(extra_refs)
    ordered_ids = [
        str(ref.get("section_id") or "").strip()
        for ref in next_refs
        if str(ref.get("section_id") or "").strip()
    ]
    normalized_section_structure = _map_template_section_structure_to_page_structure(
        resolved_template.get("section_structure"),
        next_managed_id_map,
        ordered_ids,
    )
    next_refs = apply_section_order_from_structure(
        next_refs,
        normalized_section_structure,
        section_id_field="section_id",
    )

    stale_managed_ids = old_managed_ids - next_managed_id_set
    stale_object_ids = [
        oid
        for oid in (_safe_object_id(section_id) for section_id in stale_managed_ids)
        if oid is not None
    ]
    if stale_object_ids:
        await sections_coll.delete_many({"_id": {"$in": stale_object_ids}})

    template_name = str(resolved_template.get("template_name") or "default").strip().lower() or "default"
    parent_route = normalize_parent_route(resolved_template.get("parent_route"))
    page_patch: dict[str, Any] = {
        "sections": next_refs,
        "section_structure": normalized_section_structure,
        "template_style_ref": compose_page_template_path(template_name, parent_route),
        "template_style_linked": True,
        "template_style_lock": True,
        "template_managed": True,
        "template_key": build_template_key_for_page(template_name, parent_route),
        "template_template_name": template_name,
        "template_integration_id": template_integration_id or None,
        "template_integration_item_key": template_integration_item_key or None,
        "template_managed_section_ids": next_managed_ids,
        "template_managed_section_id_map": next_managed_id_map,
        "template_source_updated_at": _template_doc_timestamp(resolved_template) or now,
        "template_synced_at": now,
        "updated_at": now,
    }
    if managed_header_id:
        page_patch["has_header"] = True
        page_patch["header_id"] = managed_header_id
        page_patch["template_managed_header_id"] = managed_header_id
    if isinstance(source_payload, dict):
        page_patch["template_mapped_source_hash"] = _compute_item_page_source_payload_hash(
            source_payload,
            integration_payload if isinstance(locals().get("integration_payload"), dict) else None,
        )
    if "mapped_sync_report" in locals():
        page_patch["template_last_mapped_sync_report"] = deepcopy(mapped_sync_report)

    await pages_coll.update_one(
        {"_id": working_page["_id"]},
        {"$set": page_patch},
    )
    if template_integration_id and template_integration_item_key:
        await sync_generated_item_page_integration_page_slug(
            db,
            {**working_page, **page_patch},
        )

    return {
        "ok": True,
        "page_id": str(working_page.get("_id") or ""),
        "slug": str(working_page.get("slug") or ""),
        "template_path": compose_page_template_path(template_name, parent_route),
        "managed_section_count": len(next_managed_ids),
        "created_section_count": created_count,
        "updated_section_count": updated_count,
        "removed_section_count": len(stale_object_ids),
        "warnings": warnings,
    }


async def sync_init_generated_item_pages_for_template(
    db,
    template_doc: dict,
    *,
    mapped_target_keys: set[str] | None = None,
) -> dict:
    if not _is_item_page_template_doc(template_doc):
        return {"matched_count": 0, "synced_count": 0, "warnings": []}
    content_sync_only = mapped_target_keys is not None
    if content_sync_only and not mapped_target_keys:
        return {
            "matched_count": 0,
            "synced_count": 0,
            "warnings": [],
            "skipped": True,
        }

    template_name = normalize_template_name(
        template_doc.get("template_name") or "default",
        default="default",
    )
    parent_route = normalize_parent_route(template_doc.get("parent_route"))
    template_path = compose_page_template_path(template_name, parent_route)
    source_type = str(template_doc.get("source_type") or "").strip().lower()
    source_kind = str(template_doc.get("source_kind") or "").strip().lower()
    effective_parent_route = effective_item_page_parent_route_for_template(template_doc)
    if source_type in {"blog", "program"}:
        active_template = await resolve_active_item_page_template(db, source_type, source_kind)
        if (
            not active_template
            or str(active_template.get("template_path") or "") != template_path
        ):
            return {
                "matched_count": 0,
                "synced_count": 0,
                "warnings": [],
                "skipped": True,
            }
        effective_parent_route = normalize_parent_route(active_template.get("effective_parent_route"))
    if source_type in {"blog", "program"} and not effective_parent_route:
        return {
            "matched_count": 0,
            "synced_count": 0,
            "warnings": [],
            "skipped": True,
        }
    template_key = build_template_key_for_page(template_name, parent_route)
    filters = [
        {"template_key": template_key},
        {"template_style_ref": template_path},
        {
            "template_template_name": template_name,
            "template_parent_route": effective_parent_route or parent_route,
        },
    ]

    if content_sync_only and await _integration_item_page_sync_blocked(
        db,
        _selected_mapping_integration_id(template_doc),
    ):
        return {
            "matched_count": 0,
            "synced_count": 0,
            "warnings": [],
            "blocked": True,
        }

    page_query: dict[str, Any] = {
        "template_managed": True,
        "$or": filters,
    }
    if not content_sync_only:
        page_query["status"] = "init"

    pages = await db["pages"].find(page_query).to_list(length=5000 if content_sync_only else 2000)

    synced_count = 0
    warnings: list[dict] = []
    for page_doc in pages:
        try:
            result = await sync_generated_item_page_from_template_state(
                db,
                page_doc,
                template_doc=template_doc,
                mapped_target_keys=mapped_target_keys,
            )
            result_warnings = result.get("warnings")
            if isinstance(result_warnings, list):
                warnings.extend(result_warnings)
            synced_count += 1
        except Exception as exc:
            warnings.append(
                {
                    "code": "generated_page_template_sync_failed",
                    "message": str(exc),
                    "slug": str(page_doc.get("slug") or ""),
                }
            )

    return {
        "matched_count": len(pages),
        "synced_count": synced_count,
        "warnings": warnings[:200],
    }


def _generated_page_allows_review_mapping_sync(page_doc: dict) -> bool:
    if not isinstance(page_doc, dict):
        return False
    return page_doc.get("template_managed") is True


def _item_page_template_identity_filters(template_doc: dict) -> list[dict]:
    template_name = normalize_template_name(
        template_doc.get("template_name") or "default",
        default="default",
    )
    parent_route = normalize_parent_route(template_doc.get("parent_route"))
    template_path = compose_page_template_path(template_name, parent_route)
    filters: list[dict] = [
        {"template_key": build_template_key_for_page(template_name, parent_route)},
        {"template_style_ref": template_path},
        {
            "template_template_name": template_name,
            "template_parent_route": parent_route,
        },
    ]
    return filters


def _item_page_template_identity_filters_for_effective_parent(
    template_doc: dict,
    *,
    effective_parent_route: str | None = None,
) -> list[dict]:
    filters = _item_page_template_identity_filters(template_doc)
    template_name = normalize_template_name(
        template_doc.get("template_name") or "default",
        default="default",
    )
    normalized_effective_parent = normalize_parent_route(effective_parent_route)
    normalized_template_parent = normalize_parent_route(template_doc.get("parent_route"))
    if normalized_effective_parent != normalized_template_parent:
        effective_filter = {
            "template_template_name": template_name,
            "template_parent_route": normalized_effective_parent,
        }
        if effective_filter not in filters:
            filters.append(effective_filter)
    return filters


async def _find_existing_generated_page_for_template_source(
    pages_coll,
    template_doc: dict,
    *,
    source_type: str,
    source_id: str,
    source_parent_id: str | None = None,
    effective_parent_route: str | None = None,
    template_integration_id: str | None = None,
    template_integration_item_key: str | None = None,
    warning_collector: list[dict] | None = None,
) -> tuple[dict | None, bool]:
    normalized_source_type = str(source_type or "").strip().lower()
    normalized_source_id = str(source_id or "").strip()
    if not normalized_source_type or not normalized_source_id:
        return None, False

    query: dict[str, Any] = {
        "template_managed": True,
        "template_source_type": normalized_source_type,
        "template_source_id": normalized_source_id,
        "$or": _item_page_template_identity_filters_for_effective_parent(
            template_doc,
            effective_parent_route=effective_parent_route,
        ),
    }
    normalized_source_parent_id = str(source_parent_id or "").strip()
    if normalized_source_parent_id:
        query["template_source_parent_id"] = normalized_source_parent_id

    candidates = await pages_coll.find(
        query,
    ).sort([("updated_at", -1), ("created_at", -1)]).to_list(length=2)
    if len(candidates) > 1:
        _append_sync_warning(
            warning_collector,
            code="generated_page_identity_ambiguous",
            message="Generated page regeneration skipped because multiple pages matched the same template/source identity.",
            source_id=normalized_source_id,
            source_type=normalized_source_type,
            template_name=str(template_doc.get("template_name") or ""),
            parent_route=normalize_parent_route(effective_parent_route or template_doc.get("parent_route")),
        )
        return None, True
    if candidates:
        return candidates[0], False

    normalized_integration_id = str(template_integration_id or "").strip()
    normalized_item_key = str(template_integration_item_key or "").strip()
    if not normalized_integration_id or not normalized_item_key:
        return None, False

    integration_query: dict[str, Any] = {
        "template_managed": True,
        "template_source_type": normalized_source_type,
        "template_integration_id": normalized_integration_id,
        "template_integration_item_key": normalized_item_key,
        "$or": _item_page_template_identity_filters_for_effective_parent(
            template_doc,
            effective_parent_route=effective_parent_route,
        ),
    }
    if normalized_source_parent_id:
        integration_query["template_source_parent_id"] = normalized_source_parent_id

    integration_candidates = await pages_coll.find(
        integration_query,
    ).sort([("updated_at", -1), ("created_at", -1)]).to_list(length=2)
    if len(integration_candidates) > 1:
        _append_sync_warning(
            warning_collector,
            code="generated_page_identity_ambiguous",
            message="Generated page regeneration skipped because multiple pages matched the same template/integration item identity.",
            source_id=normalized_source_id,
            source_type=normalized_source_type,
            template_name=str(template_doc.get("template_name") or ""),
            parent_route=normalize_parent_route(effective_parent_route or template_doc.get("parent_route")),
        )
        return None, True
    return (integration_candidates[0] if integration_candidates else None), False


def _mapped_target_keys_for_review_field_paths(
    template_doc: dict,
    *,
    integration_primary_key_path: str,
    field_paths: set[str],
) -> set[str]:
    target_keys: set[str] = set()
    for target in _collect_item_page_mapping_targets(
        template_doc,
        integration_primary_key_path=integration_primary_key_path,
    ):
        source_path = str(target.get("source_path") or "").strip()
        if not source_path.startswith("integration."):
            continue
        source_field_path = _strip_mapping_integration_prefix(source_path)
        if not source_field_path:
            continue
        if not _path_intersects_updated_paths(source_field_path, field_paths):
            continue
        target_key = _item_page_mapping_target_key_for_template_doc(template_doc, target)
        if target_key:
            target_keys.add(target_key)
    return target_keys


async def sync_generated_item_pages_for_integration_review_change(
    db,
    *,
    integration_id: Any,
    item_key: Any,
    field_paths: set[str] | list[str] | tuple[str, ...],
) -> dict[str, Any]:
    normalized_integration_id = str(integration_id or "").strip()
    normalized_item_key = str(item_key or "").strip()
    normalized_field_paths: set[str] = set()
    for field_path in field_paths:
        normalized_field_path = normalize_review_field_path(field_path)
        if not normalized_field_path or normalized_field_path == "$":
            continue
        normalized_field_paths.add(normalized_field_path)
    if not normalized_integration_id or not normalized_item_key or not normalized_field_paths:
        return {"matched_count": 0, "synced_count": 0, "warnings": []}

    integration_oid = _safe_object_id(normalized_integration_id)
    integration_doc = (
        await db["integration_config"].find_one({"_id": integration_oid})
        if integration_oid is not None
        else None
    )
    if not isinstance(integration_doc, dict):
        return {
            "matched_count": 0,
            "synced_count": 0,
            "warnings": [{"code": "integration_missing"}],
        }
    if bool(integration_doc.get("item_page_sync_blocked", False)):
        return {
            "matched_count": 0,
            "synced_count": 0,
            "warnings": [],
            "blocked": True,
        }
    output_primary_key_path = str(
        integration_doc.get("output_primary_key_path") or ""
    ).strip()
    page_slug_path = await _load_integration_schema_page_slug_path(
        db,
        normalized_integration_id,
    )
    page_slug_changed = bool(
        page_slug_path and _path_intersects_updated_paths(page_slug_path, normalized_field_paths)
    )

    template_docs = await db[TEMPLATE_PAGES_COLLECTION].find(
        {
            "page_integration_mapping.selected_integration_id": normalized_integration_id,
            "$or": [
                {"template_kind": "item_page"},
                {"source_type": {"$in": ["blog", "program", "tiles"]}},
            ],
        }
    ).to_list(length=500)

    matched_count = 0
    synced_count = 0
    warnings: list[dict[str, Any]] = []

    for template_doc in template_docs:
        if not isinstance(template_doc, dict):
            continue
        target_keys = _mapped_target_keys_for_review_field_paths(
            template_doc,
            integration_primary_key_path=output_primary_key_path,
            field_paths=normalized_field_paths,
        )
        if not target_keys and not page_slug_changed:
            continue

        page_query = {
            "template_managed": True,
            "template_integration_id": normalized_integration_id,
            "template_integration_item_key": normalized_item_key,
            "$or": _item_page_template_identity_filters(template_doc),
        }
        page_docs = await db["pages"].find(page_query).to_list(length=5000)
        if not page_docs:
            continue

        integration_rows = await _load_integration_rows_for_template(
            db,
            template_doc,
            warning_collector=warnings,
        )
        for page_doc in page_docs:
            if not _generated_page_allows_review_mapping_sync(page_doc):
                continue
            source_payload = await _resolve_source_payload_for_generated_page(db, page_doc)
            if not isinstance(source_payload, dict):
                continue
            source_id = str(page_doc.get("template_source_id") or "").strip()
            source_type = str(page_doc.get("template_source_type") or "").strip()
            integration_payload = _integration_row_for_review_item_key(
                integration_rows,
                output_primary_key_path=output_primary_key_path,
                item_key=normalized_item_key,
            )
            if not isinstance(integration_payload, dict):
                warnings.append(
                    {
                        "code": "integration_row_key_missing",
                        "message": "Generated page review sync skipped because the review item key could not be resolved in integration data.",
                        "source_id": source_id,
                        "source_type": source_type,
                    }
                )
                continue
            matched_count += 1
            try:
                if page_slug_changed:
                    item_integration_mapping = None
                    if source_type == "program_stage":
                        item_integration_mapping = await _load_program_item_integration_mapping_for_sync(
                            db,
                            None,
                            kind="stage",
                        )
                    elif source_type == "program_gig":
                        item_integration_mapping = await _load_program_item_integration_mapping_for_sync(
                            db,
                            None,
                            kind="gig",
                        )
                    final_slug = await _sync_generated_page_from_template(
                        db,
                        template_doc=template_doc,
                        source_payload=source_payload,
                        source_type=source_type,
                        source_id=source_id,
                        desired_slug=str(page_doc.get("slug") or ""),
                        source_parent_id=str(page_doc.get("template_source_parent_id") or ""),
                        integration_rows=[integration_payload],
                        item_integration_mapping=item_integration_mapping,
                        warning_collector=warnings,
                        sync_mode=ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
                    )
                    refreshed_page = await db["pages"].find_one({"_id": page_doc.get("_id")})
                    if isinstance(refreshed_page, dict):
                        await _sync_generated_item_page_source_link(db, refreshed_page)
                    if final_slug:
                        synced_count += 1
                    continue

                result = await sync_generated_item_page_from_template_state(
                    db,
                    page_doc,
                    template_doc=template_doc,
                    sync_mode=ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
                    mapped_target_keys=target_keys,
                )
                result_warnings = result.get("warnings")
                if isinstance(result_warnings, list):
                    warnings.extend(result_warnings)
                synced_count += 1
            except Exception as exc:
                warnings.append(
                    {
                        "code": "generated_page_review_sync_failed",
                        "message": str(exc),
                        "slug": str(page_doc.get("slug") or ""),
                    }
                )

    return {
        "matched_count": matched_count,
        "synced_count": synced_count,
        "warnings": warnings[:100],
    }


async def _sync_generated_page_from_template(
    db,
    *,
    template_doc: dict,
    source_payload: dict,
    source_type: str,
    source_id: str,
    desired_slug: str,
    source_parent_id: str | None = None,
    integration_rows: list[dict] | None = None,
    item_integration_mapping: dict | None = None,
    warning_collector: list[dict] | None = None,
    force_rebuild: bool = False,
    reset_status_to_init: bool = False,
    sync_mode: str = ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
) -> str:
    pages_coll = db["pages"]
    now = datetime.utcnow()
    normalized_source_type = str(source_type or "").strip().lower()
    normalized_source_id = str(source_id or "").strip()
    normalized_source_parent_id = str(source_parent_id or "").strip()
    uses_shared_items = _item_page_mapping_uses_shared_items(template_doc)
    effective_template_parent_route = normalize_parent_route(template_doc.get("parent_route"))
    # Program/blog generation may override parent route at section level; persist the effective route
    # so follow-up cleanup/filtering targets the newly generated pages correctly.
    if normalized_source_type in {"program_stage", "program_gig", "blog"} and normalized_source_parent_id:
        effective_template_parent_route = normalize_parent_route(normalized_source_parent_id)
    integration_primary_key_path = ""
    if not uses_shared_items:
        integration_primary_key_path = await _load_selected_mapping_integration_primary_key_path(
            db,
            template_doc,
        )
    selected_mapping_integration_id = (
        ""
        if uses_shared_items
        else _selected_mapping_integration_id(template_doc)
    )
    source_identity_item_key = (
        ""
        if uses_shared_items
        else _program_review_item_key_from_source_identity(
            source_type=normalized_source_type,
            source_id=normalized_source_id,
            source_payload=source_payload,
            integration_primary_key_path=integration_primary_key_path,
        )
    )
    template_source_updated_at = (
        template_doc.get("updated_at")
        if isinstance(template_doc.get("updated_at"), datetime)
        else template_doc.get("created_at")
        if isinstance(template_doc.get("created_at"), datetime)
        else now
    )

    existing_page, page_identity_ambiguous = await _find_existing_generated_page_for_template_source(
        pages_coll,
        template_doc,
        source_type=normalized_source_type,
        source_id=normalized_source_id,
        source_parent_id=normalized_source_parent_id,
        effective_parent_route=effective_template_parent_route,
        template_integration_id=selected_mapping_integration_id,
        template_integration_item_key=source_identity_item_key,
        warning_collector=warning_collector,
    )
    if page_identity_ambiguous:
        return ""

    exclude_id = existing_page.get("_id") if isinstance(existing_page, dict) else None
    cleaned_legacy_page_slug_override = False
    if isinstance(existing_page, dict) and not uses_shared_items:
        stored_integration_id = str(existing_page.get("template_integration_id") or "").strip()
        stored_item_key = str(existing_page.get("template_integration_item_key") or "").strip()
        if stored_integration_id and stored_item_key:
            cleaned_legacy_page_slug_override = await _cleanup_legacy_page_slug_source_override(
                db,
                integration_id=stored_integration_id,
                item_key=stored_item_key,
                slug=str(existing_page.get("slug") or "").strip(),
            )

    mapping_context = await _resolve_item_page_mapping_context(
        db,
        template_doc=template_doc,
        source_payload=source_payload,
        source_type=source_type,
        source_id=source_id,
        integration_rows=integration_rows,
        item_integration_mapping=item_integration_mapping,
        warning_collector=warning_collector,
        existing_page=existing_page,
        force_rebuild=force_rebuild,
        cleaned_legacy_page_slug_override=cleaned_legacy_page_slug_override,
        precomputed_integration_primary_key_path=integration_primary_key_path,
        precomputed_selected_mapping_integration_id=selected_mapping_integration_id,
        precomputed_source_identity_item_key=source_identity_item_key,
        warning_parent_route=effective_template_parent_route,
    )
    if mapping_context is None:
        return ""

    integration_payload = mapping_context["integration_payload"]
    template_integration_id = mapping_context["template_integration_id"]
    template_integration_item_key = mapping_context["template_integration_item_key"]
    template_integration_doc = mapping_context["template_integration_doc"]
    page_payload = mapping_context["page_payload"]
    header_payload = mapping_context["header_payload"]
    sections_payload = mapping_context["sections_payload"]
    source_payload_hash = mapping_context["source_payload_hash"]
    generated_mapped_target_values = mapping_context["generated_mapped_target_values"]
    old_slug = str(existing_page.get("slug") or "") if isinstance(existing_page, dict) else ""

    if isinstance(existing_page, dict) and not force_rebuild:
        # Existing generated pages are patched only on mapped targets.
        # This preserves custom page/header/section edits outside mapping paths.
        managed_map_for_mapped_targets = _resolve_existing_managed_section_id_map(
            existing_page,
            [
                normalize_embedded_section(section)
                for section in sections_payload
                if isinstance(section, dict)
            ],
        )
        mapped_sync_report = await _patch_existing_generated_page_mapped_targets(
            db,
            existing_page=existing_page,
            template_doc=template_doc,
            page_payload=page_payload,
            header_payload=header_payload,
            sections_payload=sections_payload,
            source_payload=source_payload,
            source_type=source_type,
            source_id=source_id,
            integration_payload=integration_payload,
            integration_primary_key_path=integration_primary_key_path,
            item_integration_mapping=item_integration_mapping,
            sync_mode=sync_mode,
            managed_section_id_map=managed_map_for_mapped_targets,
        )
        source_payload_hash = _compute_item_page_source_payload_hash(source_payload, integration_payload)
        refreshed = await pages_coll.find_one({"_id": existing_page.get("_id")})
        if isinstance(refreshed, dict):
            existing_page = refreshed
        await _apply_template_section_config_to_existing_managed_sections(
            db,
            existing_page,
            sections_payload,
            now=now,
        )
        managed_header_id = None
        if bool(template_doc.get("has_header")):
            managed_header_id = await _apply_template_header_config_to_existing_managed_header(
                db,
                existing_page,
                header_payload,
                now=now,
            )
        page_sections = (
            deepcopy(existing_page.get("sections"))
            if isinstance(existing_page.get("sections"), list)
            else []
        )
        managed_section_ids = _resolve_existing_managed_section_ids(existing_page)
        if not managed_header_id:
            managed_header_id = str(
                existing_page.get("template_managed_header_id")
                or existing_page.get("header_id")
                or ""
            ).strip() or None
    else:
        if isinstance(existing_page, dict) and force_rebuild:
            await _delete_managed_page_resources(db, existing_page)
        page_sections, managed_section_ids, managed_section_id_map = await _materialize_sections(
            db,
            sections_payload,
        )
        managed_header_id = await _materialize_header(
            db,
            header_payload if template_doc.get("has_header") else None,
            existing_header_id=None,
        )
        ordered_ids = [
            str(ref.get("section_id") or "").strip()
            for ref in page_sections
            if str(ref.get("section_id") or "").strip()
        ]
        normalized_section_structure = _map_template_section_structure_to_page_structure(
            template_doc.get("section_structure"),
            managed_section_id_map,
            ordered_ids,
        )
        page_sections = apply_section_order_from_structure(
            page_sections,
            normalized_section_structure,
            section_id_field="section_id",
        )

    is_program_generated_page = normalized_source_type in {"program_stage", "program_gig"}

    integration_fixed_slug = await _resolve_integration_page_slug_for_mapping(
        db,
        template_doc=template_doc,
        integration_payload=integration_payload,
        parent_route=effective_template_parent_route,
    )
    mapped_slug = str(page_payload.get("slug") or "").strip()
    desired_canonical_slug = integration_fixed_slug or mapped_slug or desired_slug
    canonical_slug = normalize_slug(desired_canonical_slug)
    temporary_slug = _build_generated_item_temporary_slug(
        source_type=source_type,
        source_id=source_id,
        parent_route=effective_template_parent_route,
    )
    if normalized_source_type == "blog":
        temporary_slug = _build_blog_item_temporary_slug(
            source_payload=source_payload,
            source_id=source_id,
            parent_route=effective_template_parent_route,
        )

    existing_pending_canonical_slug = (
        str(existing_page.get("template_pending_canonical_slug") or "").strip()
        if isinstance(existing_page, dict)
        else ""
    )
    is_existing_pending = bool(existing_pending_canonical_slug)

    enable_hidden_first_flow = normalized_source_type in {
        "blog",
        "program_stage",
        "program_gig",
        "tiles",
    }
    initial_page_title = _to_bilingual_payload(page_payload.get("title"))
    if normalized_source_type == "program_stage" and not _has_bilingual_text(initial_page_title):
        # Stage pages should use the stage item title for slug derivation even when
        # page-title mapping is not explicitly configured in the template.
        source_title = _to_bilingual_payload(source_payload.get("title"))
        if not _has_bilingual_text(source_title):
            source_title = _to_bilingual_payload(source_payload.get("name"))
        if _has_bilingual_text(source_title):
            initial_page_title = source_title
    if normalized_source_type == "program_gig" and not _has_bilingual_text(initial_page_title):
        # Gig pages should use the gig item title for slug derivation even when
        # page-title mapping is not explicitly configured in the template.
        source_title = _to_bilingual_payload(source_payload.get("title"))
        if not _has_bilingual_text(source_title):
            source_title = _to_bilingual_payload(source_payload.get("artist_name"))
        if _has_bilingual_text(source_title):
            initial_page_title = source_title
    has_title_for_initial_slug = _has_bilingual_text(initial_page_title)
    if has_title_for_initial_slug and not integration_fixed_slug:
        title_slug_tail = slugify_segment(
            initial_page_title.get("de") or initial_page_title.get("en"),
            fallback="",
        )
        if title_slug_tail:
            if effective_template_parent_route:
                canonical_slug = normalize_slug(
                    f"{effective_template_parent_route.strip('/')}/{title_slug_tail}"
                )
            else:
                canonical_slug = normalize_slug(title_slug_tail)

    has_fixed_canonical_slug = bool(integration_fixed_slug)
    if enable_hidden_first_flow:
        # Hidden-first flow:
        # - New pages are always created with initial "init" status.
        # - If a title is already available at first creation, use the canonical title slug directly.
        # - Otherwise use a temporary slug and promote to canonical title slug on explicit publish.
        # - Existing non-pending pages keep their current canonical behavior.
        if isinstance(existing_page, dict):
            resolved_status = normalize_page_status(existing_page.get("status"), fallback="hidden")
            if is_existing_pending and is_hidden_like_page_status(resolved_status) and not has_fixed_canonical_slug:
                desired_slug_for_write = temporary_slug
                pending_canonical_slug = canonical_slug
            else:
                desired_slug_for_write = canonical_slug
                pending_canonical_slug = None
        else:
            resolved_status = "init"
            if has_title_for_initial_slug or has_fixed_canonical_slug:
                desired_slug_for_write = canonical_slug
                pending_canonical_slug = None
            else:
                desired_slug_for_write = temporary_slug
                pending_canonical_slug = canonical_slug
    else:
        if isinstance(existing_page, dict):
            resolved_status = normalize_page_status(existing_page.get("status"), fallback="hidden")
        else:
            resolved_status = normalize_page_status(page_payload.get("status"), fallback="hidden")
        desired_slug_for_write = canonical_slug
        pending_canonical_slug = None

    if reset_status_to_init:
        resolved_status = "init"

    final_slug = await _resolve_unique_slug(
        pages_coll,
        desired_slug_for_write,
        exclude_page_id=exclude_id,
    )
    if template_integration_id and template_integration_item_key and isinstance(integration_payload, dict):
        page_slug_path = await _load_integration_page_slug_write_path(db, template_integration_id)
        if page_slug_path:
            set_integration_review_value_at_path(
                integration_payload,
                page_slug_path,
                final_slug,
            )
            source_payload_hash = _compute_item_page_source_payload_hash(
                source_payload,
                integration_payload,
            )

    hide_in_admin_sitemap = bool(page_payload.get("hide_in_admin_sitemap", False))
    hide_from_sitemap = bool(page_payload.get("hide_from_sitemap", False))
    hide_subtree_from_sitemap = bool(page_payload.get("hide_subtree_from_sitemap", False))
    if is_program_generated_page:
        # Program-generated detail pages should be directly reachable and indexed.
        hide_in_admin_sitemap = False
        hide_from_sitemap = False
        hide_subtree_from_sitemap = False

    if isinstance(existing_page, dict):
        existing_header_id = str(existing_page.get("header_id") or "").strip() or None
        if force_rebuild:
            next_header_id = managed_header_id
            next_has_header = bool(template_doc.get("has_header") and managed_header_id)
        else:
            next_header_id = existing_header_id or managed_header_id
            next_has_header = bool(
                template_doc.get("has_header") and next_header_id
            ) or bool(existing_page.get("has_header", False))
        if force_rebuild:
            next_page_title = (
                page_payload.get("title")
                if isinstance(page_payload.get("title"), dict)
                else {"de": "", "en": ""}
            )
            next_menu_title = (
                page_payload.get("menu_title")
                if isinstance(page_payload.get("menu_title"), dict)
                else None
            )
        else:
            next_page_title = (
                existing_page.get("title")
                if isinstance(existing_page.get("title"), dict)
                else {"de": "", "en": ""}
            )
            next_menu_title = (
                existing_page.get("menu_title")
                if isinstance(existing_page.get("menu_title"), dict)
                else None
            )
        page_doc = {
            "slug": final_slug,
            "title": next_page_title,
            "has_header": next_has_header,
            "header_id": next_header_id,
            "sections": page_sections,
            "section_structure": normalized_section_structure
            if force_rebuild
            else existing_page.get("section_structure")
            if isinstance(existing_page.get("section_structure"), list)
            else [],
            "status": resolved_status,
            "publish_at": existing_page.get("publish_at"),
            "unpublish_at": existing_page.get("unpublish_at"),
            "in_menu": bool(existing_page.get("in_menu", False)),
            "in_footer": bool(existing_page.get("in_footer", False)),
            "hide_in_admin_sitemap": bool(existing_page.get("hide_in_admin_sitemap", hide_in_admin_sitemap)),
            "hide_from_sitemap": bool(existing_page.get("hide_from_sitemap", hide_from_sitemap)),
            "hide_subtree_from_sitemap": bool(existing_page.get("hide_subtree_from_sitemap", hide_subtree_from_sitemap)),
            "sitemap_priority": existing_page.get("sitemap_priority"),
            "sitemap_changefreq": existing_page.get("sitemap_changefreq"),
            "generated_from_blog": source_type == "blog",
            "menu_title": next_menu_title,
            "menu_order": int(existing_page.get("menu_order", 0) or 0),
            "footer_order": int(existing_page.get("footer_order", 0) or 0),
            "redirect_to": existing_page.get("redirect_to"),
            "section_bg_pinned_start_key": str(existing_page.get("section_bg_pinned_start_key") or ""),
            "section_bg_pinned_end_key": str(existing_page.get("section_bg_pinned_end_key") or ""),
            "page_design_overrides": existing_page.get("page_design_overrides"),
            "template_style_ref": compose_page_template_path(
                template_doc.get("template_name", "default"),
                template_doc.get("parent_route"),
            ),
            "template_style_linked": True,
            "template_style_lock": True,
            "template_managed": True,
            "template_key": build_template_key_for_page(template_doc["template_name"], template_doc.get("parent_route")),
            "template_template_name": template_doc["template_name"],
            "template_parent_route": effective_template_parent_route,
            "template_source_type": source_type,
            "template_source_id": source_id,
            "template_source_parent_id": source_parent_id,
            "template_integration_id": template_integration_id or None,
            "template_integration_item_key": template_integration_item_key or None,
            "template_pending_canonical_slug": pending_canonical_slug,
            "template_managed_section_ids": managed_section_ids,
            "template_managed_section_id_map": managed_section_id_map
            if force_rebuild
            else existing_page.get("template_managed_section_id_map")
            if isinstance(existing_page.get("template_managed_section_id_map"), dict)
            else {},
            "template_managed_header_id": managed_header_id,
            "template_mapped_source_hash": source_payload_hash,
            ITEM_PAGE_MAPPED_TARGET_VALUES_KEY: generated_mapped_target_values
            if force_rebuild
            else existing_page.get(ITEM_PAGE_MAPPED_TARGET_VALUES_KEY, {}),
            ITEM_PAGE_LOCAL_MAPPED_OVERRIDES_KEY: {}
            if force_rebuild
            else existing_page.get(ITEM_PAGE_LOCAL_MAPPED_OVERRIDES_KEY, {}),
            "template_source_updated_at": (
                template_source_updated_at
                if force_rebuild
                else existing_page.get("template_source_updated_at")
            ),
            "template_synced_at": now,
            "template_last_mapped_sync_report": deepcopy(mapped_sync_report)
            if "mapped_sync_report" in locals()
            else existing_page.get("template_last_mapped_sync_report"),
            "updated_at": now,
        }
    else:
        page_doc = {
            "slug": final_slug,
            "title": page_payload.get("title") if isinstance(page_payload.get("title"), dict) else {"de": "", "en": ""},
            "has_header": bool(template_doc.get("has_header") and managed_header_id),
            "header_id": managed_header_id,
            "sections": page_sections,
            "section_structure": normalized_section_structure,
            "status": resolved_status,
            "publish_at": None,
            "unpublish_at": None,
            "in_menu": bool(page_payload.get("in_menu", False)),
            "in_footer": bool(page_payload.get("in_footer", False)),
            "hide_in_admin_sitemap": hide_in_admin_sitemap,
            "hide_from_sitemap": hide_from_sitemap,
            "hide_subtree_from_sitemap": hide_subtree_from_sitemap,
            "sitemap_priority": page_payload.get("sitemap_priority"),
            "sitemap_changefreq": page_payload.get("sitemap_changefreq"),
            "generated_from_blog": source_type == "blog",
            "menu_title": page_payload.get("menu_title") if isinstance(page_payload.get("menu_title"), dict) else None,
            "menu_order": int(page_payload.get("menu_order", 0) or 0),
            "footer_order": int(page_payload.get("footer_order", 0) or 0),
            "redirect_to": page_payload.get("redirect_to"),
            "section_bg_pinned_start_key": str(page_payload.get("section_bg_pinned_start_key") or ""),
            "section_bg_pinned_end_key": str(page_payload.get("section_bg_pinned_end_key") or ""),
            "page_design_overrides": None,
            "template_style_ref": compose_page_template_path(
                template_doc.get("template_name", "default"),
                template_doc.get("parent_route"),
            ),
            "template_style_linked": True,
            "template_style_lock": True,
            "template_managed": True,
            "template_key": build_template_key_for_page(template_doc["template_name"], template_doc.get("parent_route")),
            "template_template_name": template_doc["template_name"],
            "template_parent_route": effective_template_parent_route,
            "template_source_type": source_type,
            "template_source_id": source_id,
            "template_source_parent_id": source_parent_id,
            "template_integration_id": template_integration_id or None,
            "template_integration_item_key": template_integration_item_key or None,
            "template_pending_canonical_slug": pending_canonical_slug,
            "template_managed_section_ids": managed_section_ids,
            "template_managed_section_id_map": managed_section_id_map,
            "template_managed_header_id": managed_header_id,
            "template_mapped_source_hash": source_payload_hash,
            ITEM_PAGE_MAPPED_TARGET_VALUES_KEY: generated_mapped_target_values,
            "template_source_updated_at": template_source_updated_at,
            "template_synced_at": now,
            "updated_at": now,
        }

    if isinstance(existing_page, dict):
        await pages_coll.update_one({"_id": existing_page["_id"]}, {"$set": page_doc})
        if old_slug and old_slug != final_slug:
            await upsert_generated_redirects_for_slug_mapping(
                db,
                {old_slug: final_slug},
                reason="template_item_slug_change",
            )
    else:
        await pages_coll.insert_one({**page_doc, "created_at": now})

    if template_integration_id and template_integration_item_key:
        await _write_integration_review_page_slug_override(
            db,
            integration_id=template_integration_id,
            item_key=template_integration_item_key,
            slug=final_slug,
            integration_doc=template_integration_doc,
            warning_collector=warning_collector,
            source_id=source_id,
            source_type=source_type,
        )

    return final_slug


async def _delete_generated_pages_for_query(db, query: dict) -> None:
    pages_coll = db["pages"]
    docs = await pages_coll.find(query).to_list(length=2000)
    for doc in docs:
        await _delete_managed_page_resources(db, doc)
    if docs:
        ids = [doc["_id"] for doc in docs]
        await pages_coll.delete_many({"_id": {"$in": ids}})


def _extract_item_page_template_path(type_data: dict | None) -> str | None:
    if not isinstance(type_data, dict):
        return None
    raw_value = type_data.get("item_page_template_path")
    if raw_value is None:
        raw_value = type_data.get("itemPageTemplatePath")
    return normalize_page_template_path_value(raw_value)


async def _resolve_section_template(
    db,
    *,
    source_type: str,
    type_data: dict | None = None,
    fallback_parent_route: str | None = None,
    warning_collector: list[dict] | None = None,
) -> tuple[dict | None, str | None]:
    source_type_value = str(source_type or "").strip().lower()
    if source_type_value not in {"blog", "tiles", "program"}:
        return None, normalize_parent_route(fallback_parent_route)

    template_path = _extract_item_page_template_path(type_data)
    if template_path:
        try:
            template_name, parent_route = parse_page_template_path(template_path)
            template_doc = await db[TEMPLATE_PAGES_COLLECTION].find_one(
                {
                    "template_name": template_name,
                    "parent_route": parent_route,
                }
            )
            if isinstance(template_doc, dict):
                template_kind = str(template_doc.get("template_kind") or "").strip().lower()
                if template_kind and template_kind != "item_page":
                    _append_sync_warning(
                        warning_collector,
                        code="selected_template_not_item_page",
                        message=f'Selected template "{template_path}" is not an item-page template.',
                        source_type=source_type_value,
                        template_name=template_name,
                        parent_route=parent_route,
                    )
                    return None, normalize_parent_route(parent_route)
                return template_doc, normalize_parent_route(parent_route)
            _append_sync_warning(
                warning_collector,
                code="selected_template_missing",
                message=f'Selected {source_type_value} item-page template "{template_path}" was not found.',
                source_type=source_type_value,
                template_name=template_name,
                parent_route=parent_route,
            )
        except Exception:
            _append_sync_warning(
                warning_collector,
                code="selected_template_invalid",
                message=f'Selected template path "{template_path}" is invalid.',
                source_type=source_type_value,
            )

    normalized_parent_route = normalize_parent_route(fallback_parent_route)
    if normalized_parent_route:
        fallback_query: dict[str, Any] = {
            "parent_route": normalized_parent_route,
        }
        if source_type_value in {"blog", "tiles", "program"}:
            fallback_query["source_type"] = source_type_value
        template_doc = await db[TEMPLATE_PAGES_COLLECTION].find_one(fallback_query)
        if isinstance(template_doc, dict):
            return template_doc, normalized_parent_route

    return None, normalized_parent_route


def _resolve_slug_source_field_raw_value(item_doc: dict, slug_source_field: str | None) -> Any:
    if not isinstance(item_doc, dict):
        return None
    normalized_field = str(slug_source_field or "").strip()
    if not normalized_field:
        return None
    if normalized_field in {"id", "_id"}:
        return item_doc.get("id") or item_doc.get("_id")

    current: Any = item_doc
    for path_segment in normalized_field.split("."):
        key = str(path_segment or "").strip()
        if not key:
            return None
        if not isinstance(current, dict):
            return None
        if key not in current:
            return None
        current = current.get(key)
    return current


def _stringify_slug_source_field_value(value: Any, *, depth: int = 0) -> str:
    if value is None or depth > 5:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value).strip()
    if isinstance(value, dict):
        if "de" in value or "en" in value:
            return str(value.get("de") or value.get("en") or "").strip()
        preferred_keys = ("name", "title", "label", "text", "value", "id")
        for key in preferred_keys:
            if key not in value:
                continue
            nested = _stringify_slug_source_field_value(value.get(key), depth=depth + 1)
            if nested:
                return nested
        return ""
    if isinstance(value, list):
        for entry in value:
            nested = _stringify_slug_source_field_value(entry, depth=depth + 1)
            if nested:
                return nested
        return ""
    return str(value).strip()


def _resolve_slug_source_field_value(item_doc: dict, slug_source_field: str | None) -> str:
    raw_value = _resolve_slug_source_field_raw_value(item_doc, slug_source_field)
    return _stringify_slug_source_field_value(raw_value)


def _preferred_slug_for_blog_item(
    item_doc: dict,
    parent_route: str | None,
    *,
    slug_source_field: str | None = None,
) -> str:
    title = item_doc.get("title") if isinstance(item_doc.get("title"), dict) else {}
    configured_slug_value = _resolve_slug_source_field_value(item_doc, slug_source_field)
    slug_tail = slugify_segment(
        configured_slug_value
        or title.get("de")
        or title.get("en")
        or item_doc.get("date")
        or item_doc.get("_id")
        or "blog"
    )
    if parent_route:
        return normalize_slug(f"{parent_route.strip('/')}/{slug_tail}")
    return normalize_slug(slug_tail)


def _preferred_slug_for_tile(tile: dict, parent_route: str | None) -> str:
    title = (
        tile.get("title")
        if isinstance(tile.get("title"), dict)
        else tile.get("overlay_text")
        if isinstance(tile.get("overlay_text"), dict)
        else {}
    )
    slug_tail = slugify_segment(
        title.get("de")
        or title.get("en")
        or tile.get("id")
        or "tile"
    )
    if parent_route:
        return normalize_slug(f"{parent_route.strip('/')}/{slug_tail}")
    return normalize_slug(slug_tail)


def _choose_blog_template_for_item(
    templates: list[dict],
    item_doc: dict,
    *,
    force_parent_route: str | None = None,
) -> dict | None:
    if not templates:
        return None

    normalized_force_route = normalize_parent_route(force_parent_route)
    if normalized_force_route:
        for template in templates:
            if normalize_parent_route(template.get("parent_route")) == normalized_force_route:
                return template

    current_slug = str(item_doc.get("page_slug") or "").strip().strip("/")
    if current_slug:
        for template in templates:
            route = normalize_parent_route(template.get("parent_route"))
            if not route:
                continue
            route_prefix = route.strip("/") + "/"
            if current_slug.startswith(route_prefix):
                return template

    templates_sorted = sorted(
        templates,
        key=lambda template: (
            len(str(template.get("parent_route") or "")),
            str(template.get("parent_route") or ""),
        ),
    )
    return templates_sorted[0] if templates_sorted else None


async def _sync_blog_item_with_template(
    db,
    item_doc: dict,
    template_doc: dict,
    *,
    override_parent_route: str | None = None,
    slug_source_field: str | None = None,
    integration_rows: list[dict] | None = None,
    warning_collector: list[dict] | None = None,
    force_rebuild: bool = False,
    reset_status_to_init: bool = False,
) -> str | None:
    items_coll = db["blog_shared"]

    if not isinstance(item_doc, dict) or not isinstance(template_doc, dict):
        return None

    parent_route = normalize_parent_route(override_parent_route) if override_parent_route else normalize_parent_route(template_doc.get("parent_route"))
    if not parent_route:
        return None

    preferred_slug = _preferred_slug_for_blog_item(
        item_doc,
        parent_route,
        slug_source_field=slug_source_field,
    )
    source_id = str(item_doc.get("_id") or "")
    if not source_id:
        return None

    final_slug = await _sync_generated_page_from_template(
        db,
        template_doc=template_doc,
        source_payload=_source_payload_from_blog_item(item_doc),
        source_type="blog",
        source_id=source_id,
        desired_slug=preferred_slug,
        source_parent_id=parent_route,
        integration_rows=integration_rows,
        warning_collector=warning_collector,
        force_rebuild=force_rebuild,
        reset_status_to_init=reset_status_to_init,
    )
    if not final_slug:
        return None

    if str(item_doc.get("page_slug") or "") != final_slug:
        await items_coll.update_one(
            {"_id": item_doc["_id"]},
            {"$set": {"page_slug": final_slug, "updated_at": datetime.utcnow()}},
        )

    await _delete_generated_pages_for_query(
        db,
        {
            "template_managed": True,
            "template_source_type": "blog",
            "template_source_id": source_id,
            "$or": _template_identity_filters(template_doc),
            "template_parent_route": {"$ne": parent_route},
        },
    )

    return final_slug


async def sync_blog_item_page(
    db,
    item_doc: dict,
    *,
    force_parent_route: str | None = None,
    slug_source_field: str | None = None,
    force_rebuild: bool = False,
    reset_status_to_init: bool = False,
) -> str | None:
    active_template = await resolve_active_item_page_template(db, "blog", "item")
    if not active_template:
        return None
    chosen_template = active_template["template"]
    effective_parent_route = normalize_parent_route(active_template.get("effective_parent_route"))
    resolved_slug_source_field = str(active_template.get("slug_source_field") or "").strip()
    if slug_source_field:
        resolved_slug_source_field = normalize_item_page_slug_field("blog", "item", slug_source_field)
    integration_rows = await _load_integration_rows_for_template(
        db,
        chosen_template,
        source_id=str(item_doc.get("_id") or ""),
        source_type="blog",
    )
    return await _sync_blog_item_with_template(
        db,
        item_doc,
        chosen_template,
        override_parent_route=effective_parent_route,
        slug_source_field=resolved_slug_source_field,
        integration_rows=integration_rows,
        force_rebuild=force_rebuild,
        reset_status_to_init=reset_status_to_init,
    )


async def sync_blog_item_page_by_id(
    db,
    item_id: str,
    *,
    force_parent_route: str | None = None,
    force_slug_source_field: str | None = None,
    force_rebuild: bool = False,
    reset_status_to_init: bool = False,
) -> str | None:
    oid = _safe_object_id(item_id)
    if oid is None:
        return None
    item_doc = await db["blog_shared"].find_one({"_id": oid})
    if not item_doc:
        return None
    return await sync_blog_item_page(
        db,
        item_doc,
        force_parent_route=force_parent_route,
        slug_source_field=force_slug_source_field,
        force_rebuild=force_rebuild,
        reset_status_to_init=reset_status_to_init,
    )


async def _sync_all_blog_items_with_template_report(
    db,
    template: dict | None,
    *,
    override_parent_route: str | None = None,
    slug_source_field: str | None = None,
    force_rebuild: bool = False,
    reset_status_to_init: bool = False,
) -> dict:
    template_parent_route = normalize_parent_route(template.get("parent_route")) if isinstance(template, dict) else None
    parent_route = normalize_parent_route(override_parent_route) if override_parent_route else template_parent_route
    if not isinstance(template, dict) or not parent_route:
        return {
            "generated_count": 0,
            "warnings": [
                {
                    "code": "template_missing",
                    "message": "No valid blog item-page template resolved.",
                    "parent_route": parent_route,
                }
            ],
            "parent_route": parent_route,
        }

    warnings: list[dict] = []
    integration_rows = await _load_integration_rows_for_template(
        db,
        template,
        warning_collector=warnings,
        source_type="blog",
    )
    items = await db["blog_shared"].find({}).sort("date", -1).to_list(length=5000)
    synced = 0
    for index, item in enumerate(items):
        source_id = str(item.get("_id") or "").strip() if isinstance(item, dict) else ""
        try:
            result = await _sync_blog_item_with_template(
                db,
                item,
                template,
                override_parent_route=override_parent_route,
                slug_source_field=slug_source_field,
                integration_rows=integration_rows,
                warning_collector=warnings,
                force_rebuild=force_rebuild,
                reset_status_to_init=reset_status_to_init,
            )
        except Exception as exc:
            item_label = source_id or f"#{index + 1}"
            _append_sync_warning(
                warnings,
                code="generated_page_regeneration_failed",
                message=f"Failed to regenerate generated page for blog item {item_label}: {exc}",
                source_id=source_id,
                source_type="blog",
                template_name=str(template.get("template_name") or "default"),
                parent_route=parent_route,
            )
            continue
        if result:
            synced += 1
    return {
        "generated_count": synced,
        "warnings": warnings,
        "parent_route": parent_route,
        "template_path": compose_page_template_path(
            str(template.get("template_name") or "default"),
            template.get("parent_route"),
        ),
    }


async def sync_all_blog_items_for_section_report(
    db,
    section_doc: dict,
    *,
    force_rebuild: bool = False,
    reset_status_to_init: bool = False,
) -> dict:
    if not isinstance(section_doc, dict):
        return {
            "generated_count": 0,
            "warnings": [{"code": "section_invalid", "message": "Section payload is invalid."}],
            "parent_route": None,
        }

    active_template = await resolve_active_item_page_template(db, "blog", "item")
    if not active_template:
        return {
            "generated_count": 0,
            "warnings": [],
            "parent_route": None,
            "skipped": True,
        }

    template = active_template["template"]
    explicit_parent_route = normalize_parent_route(active_template.get("effective_parent_route"))
    blog_slug_source_field = str(active_template.get("slug_source_field") or "").strip()
    report = await _sync_all_blog_items_with_template_report(
        db,
        template,
        override_parent_route=explicit_parent_route or None,
        slug_source_field=blog_slug_source_field,
        force_rebuild=force_rebuild,
        reset_status_to_init=reset_status_to_init,
    )
    return report


async def sync_all_blog_items_for_section(db, section_doc: dict) -> int:
    report = await sync_all_blog_items_for_section_report(db, section_doc)
    return int(report.get("generated_count", 0) or 0)


async def sync_all_blog_items_for_route_report(
    db,
    parent_route: str,
    *,
    force_rebuild: bool = False,
    reset_status_to_init: bool = False,
) -> dict:
    normalized_route = normalize_parent_route(parent_route)
    if not normalized_route:
        return {
            "generated_count": 0,
            "warnings": [],
            "parent_route": None,
        }

    active_template = await resolve_active_item_page_template(db, "blog", "item")
    if not active_template:
        return {
            "generated_count": 0,
            "warnings": [],
            "parent_route": None,
            "skipped": True,
        }
    template = active_template["template"]
    effective_parent_route = normalize_parent_route(active_template.get("effective_parent_route"))
    template_parent_route = normalize_parent_route(template.get("parent_route"))
    if normalized_route not in {effective_parent_route, template_parent_route}:
        return {
            "generated_count": 0,
            "warnings": [],
            "parent_route": normalized_route,
            "skipped": True,
        }
    blog_slug_source_field = str(active_template.get("slug_source_field") or "").strip()

    return await _sync_all_blog_items_with_template_report(
        db,
        template,
        override_parent_route=effective_parent_route,
        slug_source_field=blog_slug_source_field,
        force_rebuild=force_rebuild,
        reset_status_to_init=reset_status_to_init,
    )


async def sync_all_blog_items_for_route(db, parent_route: str) -> int:
    report = await sync_all_blog_items_for_route_report(db, parent_route)
    return int(report.get("generated_count", 0) or 0)


async def cleanup_blog_item_generated_pages(db, item_id: str) -> None:
    await _delete_generated_pages_for_query(
        db,
        {
            "template_managed": True,
            "template_source_type": "blog",
            "template_source_id": str(item_id),
        },
    )


async def cleanup_blog_generated_pages_for_route(db, parent_route: str) -> dict:
    normalized_route = normalize_parent_route(parent_route)
    if not normalized_route:
        return {"removed_count": 0, "parent_route": None}

    pages_coll = db["pages"]
    route_prefix = normalized_route.strip("/") + "/"
    docs = await pages_coll.find(
        {
            "template_managed": True,
            "template_source_type": "blog",
            "template_parent_route": normalized_route,
        }
    ).to_list(length=5000)

    if not docs:
        return {"removed_count": 0, "parent_route": normalized_route}

    source_ids: list[str] = []
    for doc in docs:
        source_id = str(doc.get("template_source_id") or "").strip()
        if source_id:
            source_ids.append(source_id)
        await _delete_managed_page_resources(db, doc)

    await pages_coll.delete_many({"_id": {"$in": [doc["_id"] for doc in docs]}})

    if source_ids:
        blog_item_oids = [
            oid
            for oid in [_safe_object_id(source_id) for source_id in source_ids]
            if oid is not None
        ]
        if blog_item_oids:
            await db["blog_shared"].update_many(
                {
                    "_id": {"$in": blog_item_oids},
                    "$or": [
                        {"page_slug": {"$regex": f"^{re.escape(route_prefix)}"}},
                        {"page_slug": normalized_route.strip("/")},
                    ],
                },
                {"$set": {"page_slug": "", "updated_at": datetime.utcnow()}},
            )

    return {"removed_count": len(docs), "parent_route": normalized_route}


async def cleanup_generated_item_page_for_source(
    db,
    *,
    source_type: str,
    source_id: str,
) -> int:
    normalized_source_type = str(source_type or "").strip().lower()
    normalized_source_id = str(source_id or "").strip()
    if not normalized_source_type or not normalized_source_id:
        return 0

    pages_coll = db["pages"]
    docs = await pages_coll.find(
        {
            "template_managed": True,
            "template_source_type": normalized_source_type,
            "template_source_id": normalized_source_id,
        }
    ).to_list(length=100)
    if not docs:
        return 0

    for doc in docs:
        await _delete_managed_page_resources(db, doc)
    await pages_coll.delete_many({"_id": {"$in": [doc["_id"] for doc in docs]}})
    return len(docs)


def _first_datetime_value(*values: Any) -> datetime | None:
    for value in values:
        if isinstance(value, datetime):
            return value
    return None


def _page_template_sync_timestamp(page_doc: dict) -> datetime | None:
    if not isinstance(page_doc, dict):
        return None
    return _first_datetime_value(
        page_doc.get("template_source_updated_at"),
        page_doc.get("created_at"),
    )


def _template_doc_timestamp(template_doc: dict) -> datetime | None:
    if not isinstance(template_doc, dict):
        return None
    return _first_datetime_value(
        template_doc.get("updated_at"),
        template_doc.get("created_at"),
    )


async def get_generated_item_page_template_freshness_map(
    db,
    *,
    source_type: str,
    source_ids: list[str],
    source_payload_hashes: dict[str, str] | None = None,
) -> dict[str, dict]:
    normalized_source_type = str(source_type or "").strip().lower()
    if not normalized_source_type:
        return {}

    normalized_source_ids: list[str] = []
    seen_source_ids: set[str] = set()
    for raw_source_id in source_ids if isinstance(source_ids, list) else []:
        source_id = str(raw_source_id or "").strip()
        if not source_id or source_id in seen_source_ids:
            continue
        seen_source_ids.add(source_id)
        normalized_source_ids.append(source_id)
    if not normalized_source_ids:
        return {}

    active_template_path: str | None = None
    if normalized_source_type == "blog":
        active_template = await resolve_active_item_page_template(db, "blog", "item")
        if not active_template:
            return {}
        active_template_path = str(active_template.get("template_path") or "").strip() or None
    elif normalized_source_type == "program_stage":
        active_template = await resolve_active_item_page_template(db, "program", "stage")
        if not active_template:
            return {}
        active_template_path = str(active_template.get("template_path") or "").strip() or None
    elif normalized_source_type == "program_gig":
        active_template = await resolve_active_item_page_template(db, "program", "gig")
        if not active_template:
            return {}
        active_template_path = str(active_template.get("template_path") or "").strip() or None

    page_query: dict[str, Any] = {
        "template_managed": True,
        "template_source_type": normalized_source_type,
        "template_source_id": {"$in": normalized_source_ids},
    }
    if active_template_path:
        page_query["template_style_ref"] = active_template_path

    pages = await db["pages"].find(
        page_query,
        {
            "_id": 1,
            "slug": 1,
            "template_source_id": 1,
            "template_style_ref": 1,
            "template_key": 1,
            "template_template_name": 1,
            "template_parent_route": 1,
            "template_mapped_source_hash": 1,
            "template_source_updated_at": 1,
            "template_synced_at": 1,
            "updated_at": 1,
            "created_at": 1,
        },
    ).to_list(length=max(100, len(normalized_source_ids) * 2))

    if not pages:
        return {}

    template_filters: list[dict] = []
    seen_template_keys: set[str] = set()
    for page_doc in pages:
        raw_template_name = str(page_doc.get("template_template_name") or "").strip().lower()
        if not raw_template_name:
            continue
        normalized_parent_route = normalize_parent_route(page_doc.get("template_parent_route"))
        template_style_ref = str(page_doc.get("template_style_ref") or "").strip().strip("/")
        if template_style_ref:
            try:
                raw_template_name, normalized_parent_route = parse_page_template_path(template_style_ref)
            except Exception:
                raw_template_name = raw_template_name
        template_key = build_template_key_for_page(raw_template_name, normalized_parent_route)
        if template_key in seen_template_keys:
            continue
        seen_template_keys.add(template_key)
        template_filters.append(
            {
                "template_name": raw_template_name,
                "parent_route": normalized_parent_route,
            }
        )

    template_map: dict[str, dict] = {}
    if template_filters:
        template_docs = await db[TEMPLATE_PAGES_COLLECTION].find(
            {"$or": template_filters},
            {
                "_id": 1,
                "template_name": 1,
                "parent_route": 1,
                "updated_at": 1,
                "created_at": 1,
            },
        ).to_list(length=max(20, len(template_filters) * 2))
        for template_doc in template_docs:
            raw_template_name = str(template_doc.get("template_name") or "").strip().lower()
            if not raw_template_name:
                continue
            normalized_parent_route = normalize_parent_route(template_doc.get("parent_route"))
            template_key = build_template_key_for_page(raw_template_name, normalized_parent_route)
            template_map[template_key] = template_doc

    freshness_by_source: dict[str, dict] = {}
    freshness_sort_ts: dict[str, datetime] = {}
    for page_doc in pages:
        source_id = str(page_doc.get("template_source_id") or "").strip()
        if not source_id:
            continue

        raw_template_name = str(page_doc.get("template_template_name") or "").strip().lower()
        normalized_parent_route = normalize_parent_route(page_doc.get("template_parent_route"))
        template_style_ref = str(page_doc.get("template_style_ref") or "").strip().strip("/")
        if template_style_ref:
            try:
                raw_template_name, normalized_parent_route = parse_page_template_path(template_style_ref)
            except Exception:
                pass
        template_key = (
            build_template_key_for_page(raw_template_name, normalized_parent_route)
            if raw_template_name
            else None
        )
        template_doc = template_map.get(template_key) if template_key else None
        template_timestamp = _template_doc_timestamp(template_doc) if template_doc else None
        page_sync_timestamp = _page_template_sync_timestamp(page_doc)
        is_outdated = bool(
            template_timestamp
            and (not page_sync_timestamp or template_timestamp > page_sync_timestamp)
        )

        candidate_sort_ts = _first_datetime_value(
            page_doc.get("updated_at"),
            page_doc.get("created_at"),
            page_doc.get("template_synced_at"),
        ) or datetime.min
        previous_sort_ts = freshness_sort_ts.get(source_id)
        if previous_sort_ts is not None and candidate_sort_ts <= previous_sort_ts:
            continue
        expected_source_hash = str(
            (source_payload_hashes or {}).get(source_id) or ""
        ).strip()
        current_source_hash = str(
            page_doc.get("template_mapped_source_hash") or ""
        ).strip()
        if expected_source_hash:
            mapped_fields_synced = current_source_hash == expected_source_hash
        elif isinstance(source_payload_hashes, dict) and source_id in source_payload_hashes:
            mapped_fields_synced = False
        else:
            mapped_fields_synced = True
        freshness_sort_ts[source_id] = candidate_sort_ts
        freshness_by_source[source_id] = {
            "item_page_template_outdated": is_outdated,
            "item_page_slug": str(page_doc.get("slug") or "").strip(),
            "item_page_mapped_fields_synced": mapped_fields_synced,
        }

    return freshness_by_source


def _strip_parent_route_prefix(slug: str, parent_route: str) -> str:
    normalized_slug = normalize_slug(slug)
    normalized_parent = normalize_parent_route(parent_route)
    if not normalized_slug or not normalized_parent:
        return ""
    parent_token = normalized_parent.strip("/")
    if not parent_token:
        return normalized_slug
    prefix = f"{parent_token}/"
    if normalized_slug.startswith(prefix):
        return normalized_slug[len(prefix):]
    if normalized_slug == parent_token:
        return ""
    return ""


def _compose_slug_with_parent_route(parent_route: str, tail: str) -> str:
    normalized_parent = normalize_parent_route(parent_route)
    normalized_tail = normalize_slug(tail)
    if not normalized_parent:
        return normalized_tail
    if not normalized_tail:
        return normalize_slug(normalized_parent)
    return normalize_slug(f"{normalized_parent.strip('/')}/{normalized_tail}")


async def _sync_generated_item_page_source_link(db, page_doc: dict) -> None:
    if not isinstance(page_doc, dict):
        return
    slug = str(page_doc.get("slug") or "").strip()
    if not slug:
        return
    source_type = str(page_doc.get("template_source_type") or "").strip().lower()
    source_id = str(page_doc.get("template_source_id") or "").strip()
    if not source_type or not source_id:
        return

    await sync_generated_item_page_integration_page_slug(db, page_doc)

    now = datetime.utcnow()
    if source_type == "blog":
        oid = _safe_object_id(source_id)
        if oid is None:
            return
        await db["blog_shared"].update_one(
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
        await db["sections"].update_one(
            {"_id": section_oid, "type_data.tiles.id": tile_id},
            {
                "$set": {
                    "type_data.tiles.$.page_slug": slug,
                    "updated_at": now,
                }
            },
        )


async def migrate_generated_item_pages_parent_route(
    db,
    *,
    source_type: str,
    old_parent_route: str,
    new_parent_route: str,
    template_name: str | None = None,
    template_style_ref: str | None = None,
    template_key: str | None = None,
    new_template_style_ref: str | None = None,
    new_template_key: str | None = None,
) -> dict:
    normalized_source_type = str(source_type or "").strip().lower()
    normalized_old_parent = normalize_parent_route(old_parent_route)
    normalized_new_parent = normalize_parent_route(new_parent_route)
    if not normalized_source_type:
        return {
            "source_type": normalized_source_type,
            "old_parent_route": normalized_old_parent,
            "new_parent_route": normalized_new_parent,
            "updated_count": 0,
            "redirect_count": 0,
        }
    if not normalized_old_parent or not normalized_new_parent or normalized_old_parent == normalized_new_parent:
        return {
            "source_type": normalized_source_type,
            "old_parent_route": normalized_old_parent,
            "new_parent_route": normalized_new_parent,
            "updated_count": 0,
            "redirect_count": 0,
        }

    pages_coll = db["pages"]
    query: dict[str, Any] = {
        "template_managed": True,
        "template_source_type": normalized_source_type,
        "template_parent_route": normalized_old_parent,
    }
    identity_filters: list[dict[str, Any]] = []
    try:
        normalized_template_name = normalize_template_name(template_name) if str(template_name or "").strip() else ""
    except Exception:
        normalized_template_name = ""
    if normalized_template_name:
        identity_filters.append({"template_template_name": normalized_template_name})
    normalized_template_style_ref = normalize_page_template_path_value(template_style_ref)
    if normalized_template_style_ref:
        identity_filters.append({"template_style_ref": normalized_template_style_ref})
    normalized_template_key = str(template_key or "").strip()
    if normalized_template_key:
        identity_filters.append({"template_key": normalized_template_key})
    if identity_filters:
        query["$or"] = identity_filters

    docs = await pages_coll.find(query).to_list(length=5000)
    if not docs:
        return {
            "source_type": normalized_source_type,
            "old_parent_route": normalized_old_parent,
            "new_parent_route": normalized_new_parent,
            "updated_count": 0,
            "redirect_count": 0,
        }

    redirect_mapping: dict[str, str] = {}
    updated_count = 0

    for doc in docs:
        page_id = doc.get("_id")
        old_slug = str(doc.get("slug") or "").strip()
        old_pending_slug = str(doc.get("template_pending_canonical_slug") or "").strip()
        current_tail = _strip_parent_route_prefix(old_slug, normalized_old_parent)
        if not current_tail:
            source_tail = str(doc.get("template_source_id") or "").strip().split(":")[-1]
            current_tail = slugify_segment(source_tail, fallback="item")
        desired_slug = _compose_slug_with_parent_route(normalized_new_parent, current_tail)
        unique_slug = await _resolve_unique_slug(
            pages_coll,
            desired_slug,
            exclude_page_id=page_id,
        )

        next_pending_slug = None
        if old_pending_slug:
            pending_tail = _strip_parent_route_prefix(old_pending_slug, normalized_old_parent)
            if pending_tail:
                next_pending_slug = _compose_slug_with_parent_route(
                    normalized_new_parent,
                    pending_tail,
                )
            else:
                next_pending_slug = _compose_slug_with_parent_route(
                    normalized_new_parent,
                    old_pending_slug,
                )

        update_payload: dict[str, Any] = {
            "slug": unique_slug,
            "template_parent_route": normalized_new_parent,
            "template_source_parent_id": normalized_new_parent,
            "template_pending_canonical_slug": next_pending_slug,
            "updated_at": datetime.utcnow(),
        }
        normalized_new_style_ref = normalize_page_template_path_value(new_template_style_ref)
        if normalized_new_style_ref:
            update_payload["template_style_ref"] = normalized_new_style_ref
        normalized_new_template_key = str(new_template_key or "").strip()
        if normalized_new_template_key:
            update_payload["template_key"] = normalized_new_template_key
        if normalized_template_name:
            update_payload["template_template_name"] = normalized_template_name

        await pages_coll.update_one(
            {"_id": page_id},
            {"$set": update_payload},
        )

        updated_doc = await pages_coll.find_one({"_id": page_id})
        if isinstance(updated_doc, dict):
            await _sync_generated_item_page_source_link(db, updated_doc)

        updated_count += 1
        if old_slug and old_slug != unique_slug:
            redirect_mapping[old_slug] = unique_slug

    if redirect_mapping:
        await upsert_generated_redirects_for_slug_mapping(
            db,
            redirect_mapping,
            reason="item_parent_route_migration",
        )

    return {
        "source_type": normalized_source_type,
        "old_parent_route": normalized_old_parent,
        "new_parent_route": normalized_new_parent,
        "updated_count": updated_count,
        "redirect_count": len(redirect_mapping),
    }


async def _sync_tiles_section_pages_impl(db, section_doc: dict) -> dict:
    if not isinstance(section_doc, dict):
        return {"generated_count": 0, "warnings": [], "parent_route": None}

    section_id = str(section_doc.get("_id") or "")
    if not section_id:
        return {"generated_count": 0, "warnings": [], "parent_route": None}

    type_data = section_doc.get("type_data") if isinstance(section_doc.get("type_data"), dict) else {}
    fallback_parent_route = normalize_parent_route(
        type_data.get("parent_route")
        or ""
    )
    warnings: list[dict] = []

    template, resolved_parent_route = await _resolve_section_template(
        db,
        source_type="tiles",
        type_data=type_data,
        fallback_parent_route=fallback_parent_route,
        warning_collector=warnings,
    )
    parent_route = normalize_parent_route(
        (template.get("parent_route") if isinstance(template, dict) else None)
        or resolved_parent_route
    )

    if not parent_route:
        return {
            "generated_count": 0,
            "warnings": [],
            "parent_route": None,
            "skipped": True,
        }

    if not template:
        selected_template_path = _extract_item_page_template_path(type_data)
        combined_warnings = [
            *warnings,
            {
                "code": "template_missing",
                "message": (
                    f'Selected tiles item-page template "{selected_template_path}" was not found.'
                    if selected_template_path
                    else (
                        f'No tiles item-page template found for route "{parent_route}".'
                        if parent_route
                        else "No tiles item-page template selected."
                    )
                ),
                "parent_route": parent_route,
            },
        ]
        return {
            "generated_count": 0,
            "warnings": combined_warnings,
            "parent_route": parent_route,
        }

    tiles = type_data.get("tiles") if isinstance(type_data.get("tiles"), list) else []
    normalized_tiles = [tile for tile in tiles if isinstance(tile, dict)]
    integration_rows = await _load_integration_rows_for_template(
        db,
        template,
        warning_collector=warnings,
        source_type="tiles",
    )

    active_source_ids: set[str] = set()
    next_tiles: list[dict] = []
    synced = 0

    for tile in normalized_tiles:
        tile_id = str(tile.get("id") or "").strip()
        if not tile_id:
            overlay_title = (
                tile.get("title")
                if isinstance(tile.get("title"), dict)
                else tile.get("overlay_text")
                if isinstance(tile.get("overlay_text"), dict)
                else {}
            )
            tile_id = slugify_segment(
                overlay_title.get("de")
                if isinstance(overlay_title, dict)
                else "tile"
            )
            tile_id = tile_id or str(ObjectId())
            tile["id"] = tile_id

        source_id = f"tiles:{section_id}:{tile_id}"
        active_source_ids.add(source_id)

        preferred_slug = _preferred_slug_for_tile(tile, parent_route)
        final_slug = await _sync_generated_page_from_template(
            db,
            template_doc=template,
            source_payload=_source_payload_from_tile(section_doc, tile),
            source_type="tiles",
            source_id=source_id,
            desired_slug=preferred_slug,
            source_parent_id=section_id,
            integration_rows=integration_rows,
            warning_collector=warnings,
        )
        if not final_slug:
            next_tiles.append(tile)
            continue

        if str(tile.get("page_slug") or "") != final_slug:
            canonical_slug = final_slug
        else:
            canonical_slug = str(tile.get("page_slug") or final_slug)
        tile["page_slug"] = canonical_slug
        next_tiles.append(tile)
        synced += 1

    await _delete_generated_pages_for_query(
        db,
        {
            "template_managed": True,
            "template_source_type": "tiles",
            "template_source_parent_id": section_id,
            "$or": _template_identity_filters(template),
            "template_source_id": {"$nin": list(active_source_ids) if active_source_ids else ["__none__"]},
        },
    )

    await db["sections"].update_one(
        {"_id": section_doc["_id"]},
        {
            "$set": {
                "type_data.tiles": next_tiles,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    return {
        "generated_count": synced,
        "warnings": warnings,
        "parent_route": parent_route,
    }


async def sync_tiles_section_pages_report(db, section_doc: dict) -> dict:
    return await _sync_tiles_section_pages_impl(db, section_doc)


async def sync_tiles_section_pages(db, section_doc: dict) -> int:
    report = await _sync_tiles_section_pages_impl(db, section_doc)
    return int(report.get("generated_count", 0) or 0)


async def cleanup_tiles_generated_pages_for_section(db, section_doc: dict) -> dict:
    if not isinstance(section_doc, dict):
        return {"removed_count": 0}

    section_id = str(section_doc.get("_id") or "").strip()
    if not section_id:
        return {"removed_count": 0}

    type_data = section_doc.get("type_data") if isinstance(section_doc.get("type_data"), dict) else {}
    tiles = type_data.get("tiles") if isinstance(type_data.get("tiles"), list) else []
    tile_page_slugs: list[str] = []
    for tile in tiles:
        if not isinstance(tile, dict):
            continue
        raw_slug = str(tile.get("page_slug") or "").strip()
        if not raw_slug:
            continue
        try:
            tile_page_slugs.append(normalize_slug(raw_slug))
        except Exception:
            continue

    query_or: list[dict] = [
        {"template_source_parent_id": section_id},
        {"template_source_id": {"$regex": f"^tiles:{re.escape(section_id)}:"}},
    ]
    if tile_page_slugs:
        query_or.append({"slug": {"$in": tile_page_slugs}})

    pages_coll = db["pages"]
    docs = await pages_coll.find(
        {
            "template_managed": True,
            "template_source_type": "tiles",
            "$or": query_or,
        }
    ).to_list(length=5000)
    for doc in docs:
        await _delete_managed_page_resources(db, doc)
    if docs:
        await pages_coll.delete_many({"_id": {"$in": [doc["_id"] for doc in docs]}})

    next_tiles: list[dict] = []
    for tile in tiles:
        if not isinstance(tile, dict):
            continue
        next_tile = deepcopy(tile)
        next_tile["page_slug"] = ""
        next_tiles.append(next_tile)

    if isinstance(section_doc.get("_id"), ObjectId):
        await db["sections"].update_one(
            {"_id": section_doc["_id"]},
            {
                "$set": {
                    "type_data.tiles": next_tiles,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    return {
        "removed_count": len(docs),
        "section_id": section_id,
    }


def _normalize_program_stage_for_sync(raw_stage: Any, index: int) -> dict:
    source = (
        raw_stage.model_dump()
        if isinstance(raw_stage, ProgramStage)
        else raw_stage
        if isinstance(raw_stage, dict)
        else {}
    )
    try:
        normalized = ProgramStage.model_validate(source).model_dump()
    except Exception:
        normalized = ProgramStage().model_dump()
    stage_id = str(normalized.get("id") or "").strip()
    if not stage_id:
        normalized["id"] = f"stage-{index + 1}"
    normalized["_item_index"] = index
    return normalized


def _normalize_program_gig_for_sync(
    raw_gig: Any,
    index: int,
    *,
    primary_key_path: str | None = None,
    selected_integration_id: str | None = None,
) -> dict:
    source = (
        raw_gig.model_dump()
        if isinstance(raw_gig, ProgramGig)
        else raw_gig
        if isinstance(raw_gig, dict)
        else {}
    )
    try:
        normalized = program_catalog.normalize_program_gig_for_storage(
            source,
            index,
            primary_key_path=primary_key_path,
            selected_integration_id=selected_integration_id,
        )
    except Exception:
        normalized = ProgramGig().model_dump()
    gig_id = str(normalized.get("id") or "").strip()
    if not gig_id:
        normalized["id"] = f"gig-{index + 1}"
    normalized["_item_index"] = index
    return normalized


def _strip_program_sync_internal_fields(row: dict) -> dict:
    payload = deepcopy(row) if isinstance(row, dict) else {}
    payload.pop("_item_index", None)
    return payload


def _strip_program_sync_internal_rows(rows: list[dict]) -> list[dict]:
    return [
        _strip_program_sync_internal_fields(row)
        for row in rows
        if isinstance(row, dict)
    ]


def _extract_parent_route_from_template_path(template_path: Any) -> str | None:
    normalized_path = normalize_page_template_path_value(template_path)
    if not normalized_path:
        return None
    try:
        _, parent_route = parse_page_template_path(normalized_path)
    except Exception:
        return None
    return normalize_parent_route(parent_route)


def _extract_program_parent_route(type_data: dict | None, *, kind: str) -> str | None:
    if not isinstance(type_data, dict):
        return None
    normalized_kind = "stage" if str(kind or "").strip().lower() == "stage" else "gig"
    if normalized_kind == "stage":
        raw_parent_route = type_data.get("stage_parent_route")
        if raw_parent_route is None:
            raw_parent_route = _extract_parent_route_from_template_path(
                type_data.get("stage_item_page_template_path")
            )
    else:
        raw_parent_route = type_data.get("gig_parent_route")
        if raw_parent_route is None:
            raw_parent_route = _extract_parent_route_from_template_path(
                type_data.get("gig_item_page_template_path")
            )
    return normalize_parent_route(raw_parent_route)


def _build_route_entry(
    *,
    source_type: str,
    source_kind: str,
    parent_route: str | None,
    section_template_ref: str | None = None,
) -> dict | None:
    normalized_source = _normalize_shared_item_source_type(source_type)
    normalized_kind = _normalize_shared_item_source_kind(normalized_source, source_kind)
    normalized_parent_route = normalize_parent_route(parent_route)
    if not normalized_source or not normalized_kind or not normalized_parent_route:
        return None
    route_ref = _compose_shared_item_page_route_ref(
        normalized_source,
        normalized_kind,
        normalized_parent_route,
    )
    if not route_ref:
        return None
    return {
        "source_route_ref": route_ref,
        "parent_route": normalized_parent_route,
        "source_type": normalized_source,
        "source_kind": normalized_kind,
        "section_template_ref": normalize_section_template_ref(
            section_template_ref if section_template_ref is not None else f"{normalized_source}/default"
        ),
    }


async def _derive_item_page_routes_from_sections(db) -> list[dict]:
    sections_coll = db["sections"]
    candidates: list[dict] = []

    async for section_doc in sections_coll.find({"section_type": "blog"}):
        template_name = normalize_template_name(
            section_doc.get("section_template_name")
            if section_doc.get("section_template_name") is not None
            else section_doc.get("sectionTemplateName"),
            default="default",
        )
        type_data = section_doc.get("type_data") if isinstance(section_doc.get("type_data"), dict) else {}
        parent_route = normalize_parent_route(
            type_data.get("item_parent_route")
            if type_data.get("item_parent_route") is not None
            else type_data.get("itemParentRoute")
        ) or _extract_parent_route_from_template_path(
            type_data.get("item_page_template_path")
            if type_data.get("item_page_template_path") is not None
            else type_data.get("itemPageTemplatePath")
        )
        route_entry = _build_route_entry(
            source_type="blog",
            source_kind="item",
            parent_route=parent_route,
            section_template_ref=f"blog/{template_name}",
        )
        if route_entry:
            candidates.append(route_entry)

    async for section_doc in sections_coll.find({"section_type": "program"}):
        template_name = normalize_template_name(
            section_doc.get("section_template_name")
            if section_doc.get("section_template_name") is not None
            else section_doc.get("sectionTemplateName"),
            default="default",
        )
        type_data = section_doc.get("type_data") if isinstance(section_doc.get("type_data"), dict) else {}
        stage_route_entry = _build_route_entry(
            source_type="program",
            source_kind="stage",
            parent_route=_extract_program_parent_route(type_data, kind="stage"),
            section_template_ref=f"program/{template_name}",
        )
        if stage_route_entry:
            candidates.append(stage_route_entry)
        gig_route_entry = _build_route_entry(
            source_type="program",
            source_kind="gig",
            parent_route=_extract_program_parent_route(type_data, kind="gig"),
            section_template_ref=f"program/{template_name}",
        )
        if gig_route_entry:
            candidates.append(gig_route_entry)

    return normalize_item_page_routes_snapshot(candidates)


async def capture_item_page_routes(db) -> list[dict]:
    routes_coll = db[ITEM_PAGE_ROUTES_COLLECTION]
    existing_doc = await routes_coll.find_one({"_id": SHARED_ITEM_PAGE_ROUTES_DOC_ID})
    existing_routes = normalize_item_page_routes_snapshot(existing_doc or {})
    derived_routes = await _derive_item_page_routes_from_sections(db)
    merged_routes = normalize_item_page_routes_snapshot([*existing_routes, *derived_routes])
    if merged_routes != existing_routes:
        now = datetime.utcnow()
        await routes_coll.update_one(
            {"_id": SHARED_ITEM_PAGE_ROUTES_DOC_ID},
            {
                "$set": {
                    "routes": deepcopy(merged_routes),
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
        )
    return merged_routes


async def apply_item_page_routes(db, routes: Any) -> list[dict]:
    normalized_routes = normalize_item_page_routes_snapshot(routes)
    now = datetime.utcnow()
    await db[ITEM_PAGE_ROUTES_COLLECTION].update_one(
        {"_id": SHARED_ITEM_PAGE_ROUTES_DOC_ID},
        {
            "$set": {
                "routes": deepcopy(normalized_routes),
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )
    return normalized_routes


# ---------------------------------------------------------------------------
# Global item-page config — active template path per entity type
# ---------------------------------------------------------------------------

def _normalize_active_item_page_template_path(value: Any) -> str:
    raw = str(value or "").strip()
    if raw.lower() in {"", "none", "null", "undefined"}:
        return ""
    return normalize_page_template_path_value(raw) or ""


def _normalize_item_page_config(raw: Any) -> dict:
    """Return a clean config dict with only the known fields."""
    if not isinstance(raw, dict):
        raw = {}
    result: dict = {}
    for key in _GLOBAL_CFG_PARENT_ROUTE_KEYS:
        result[key] = ""
    for key in _GLOBAL_CFG_TEMPLATE_PATH_KEYS:
        result[key] = _normalize_active_item_page_template_path(raw.get(key))
    for key, default_value in _GLOBAL_CFG_SLUG_FIELD_DEFAULTS.items():
        allowed_values = _GLOBAL_CFG_SLUG_FIELD_ALLOWED_VALUES.get(key) or {default_value}
        raw_value = str(raw.get(key) or "").strip()
        result[key] = raw_value if raw_value in allowed_values else default_value
    result["routing_version"] = GLOBAL_ITEM_PAGE_ROUTING_VERSION
    return result


async def get_item_page_config(db) -> dict:
    doc = await db[ITEM_PAGE_CONFIG_COLLECTION].find_one(
        {"_id": GLOBAL_ITEM_PAGE_CONFIG_DOC_ID}
    )
    return _normalize_item_page_config(doc or {})


async def set_item_page_config(db, updates: dict) -> dict:
    if not isinstance(updates, dict):
        return await get_item_page_config(db)
    patch: dict = {}
    for key in _GLOBAL_CFG_PARENT_ROUTE_KEYS:
        if key in updates:
            patch[key] = ""
    for key in _GLOBAL_CFG_TEMPLATE_PATH_KEYS:
        if key in updates:
            patch[key] = _normalize_active_item_page_template_path(updates[key])
    for key, default_value in _GLOBAL_CFG_SLUG_FIELD_DEFAULTS.items():
        if key not in updates:
            continue
        allowed_values = _GLOBAL_CFG_SLUG_FIELD_ALLOWED_VALUES.get(key) or {default_value}
        raw_value = str(updates[key] or "").strip()
        patch[key] = raw_value if raw_value in allowed_values else default_value
    if not patch:
        return await get_item_page_config(db)
    now = datetime.utcnow()
    await db[ITEM_PAGE_CONFIG_COLLECTION].update_one(
        {"_id": GLOBAL_ITEM_PAGE_CONFIG_DOC_ID},
        {
            "$set": {
                **patch,
                "routing_version": GLOBAL_ITEM_PAGE_ROUTING_VERSION,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return await get_item_page_config(db)


async def resolve_active_item_page_template(
    db,
    source_type: Any,
    source_kind: Any = None,
) -> dict | None:
    source_context = normalize_item_page_source_context(source_type, source_kind)
    if not source_context:
        return None
    prefix = _ITEM_PAGE_TYPE_PREFIXES.get(source_context)
    if not prefix:
        return None
    global_cfg = await get_item_page_config(db)
    template_path = _normalize_active_item_page_template_path(
        global_cfg.get(f"{prefix}_template_path")
    )
    if not template_path:
        return None
    try:
        template_name, parent_route = parse_page_template_path(template_path)
    except Exception:
        return None
    template_doc = await db[TEMPLATE_PAGES_COLLECTION].find_one(
        {
            "template_name": template_name,
            "parent_route": parent_route,
        }
    )
    if not isinstance(template_doc, dict):
        return None
    template_source_context = normalize_item_page_source_context(
        template_doc.get("source_type"),
        template_doc.get("source_kind"),
    )
    if template_source_context != source_context:
        return None
    effective_parent_route = effective_item_page_parent_route_for_template(template_doc)
    if not effective_parent_route:
        return None
    slug_source_field = normalize_item_page_slug_field(
        source_context[0],
        source_context[1],
        template_doc.get("item_page_slug_field"),
    )
    return {
        "template": template_doc,
        "template_path": compose_page_template_path(template_name, parent_route),
        "parent_route": parent_route,
        "effective_parent_route": effective_parent_route,
        "slug_source_field": slug_source_field,
        "source_type": source_context[0],
        "source_kind": source_context[1],
        "config_key_prefix": prefix,
    }


async def _load_program_catalog_for_sync(
    db,
    _section_doc: dict,
) -> tuple[list[dict], list[dict], dict]:
    shared_doc = await program_catalog.capture_program_shared_content(db)
    shared_gig_primary_key_path = program_catalog.integration_output_primary_key_path_from_cache_state(
        shared_doc.get("program_gigs_integration_mapping_cache_state")
        if isinstance(shared_doc, dict)
        else None
    )
    shared_gig_selected_integration_id = program_catalog.integration_selected_id_from_mapping(
        shared_doc.get("program_gigs_integration_mapping")
        if isinstance(shared_doc, dict)
        else None
    )
    shared_metadata = {
        "gig_primary_key_path": shared_gig_primary_key_path,
        "gig_selected_integration_id": shared_gig_selected_integration_id,
    }
    raw_shared_stages = (
        shared_doc.get("stages")
        if isinstance(shared_doc, dict) and isinstance(shared_doc.get("stages"), list)
        else []
    )
    raw_shared_gigs = (
        shared_doc.get("gigs")
        if isinstance(shared_doc, dict) and isinstance(shared_doc.get("gigs"), list)
        else []
    )
    normalized_shared_stages = [
        _normalize_program_stage_for_sync(raw_stage, index)
        for index, raw_stage in enumerate(raw_shared_stages)
    ]
    normalized_shared_gigs = [
        _normalize_program_gig_for_sync(
            raw_gig,
            index,
            primary_key_path=shared_gig_primary_key_path,
            selected_integration_id=shared_gig_selected_integration_id,
        )
        for index, raw_gig in enumerate(raw_shared_gigs)
    ]

    return normalized_shared_stages, normalized_shared_gigs, shared_metadata


async def _load_program_item_integration_mapping_for_sync(
    db,
    section_doc: dict | None,
    *,
    kind: str,
) -> dict:
    normalized_kind = "stage" if str(kind or "").strip().lower() == "stage" else "gig"

    if normalized_kind == "gig":
        shared_doc = await program_catalog.capture_program_shared_content(db)
        shared_mapping = _normalize_section_integration_mapping_payload(
            shared_doc.get("program_gigs_integration_mapping")
            if isinstance(shared_doc, dict)
            else None
        )
        return shared_mapping

    shared_doc = await program_catalog.capture_program_shared_content(db)
    shared_mapping = _normalize_section_integration_mapping_payload(
        shared_doc.get("program_stages_integration_mapping")
        if isinstance(shared_doc, dict)
        else None
    )
    return shared_mapping


def _preferred_slug_for_program_stage(
    stage: dict,
    parent_route: str | None = None,
    *,
    slug_source_field: str | None = None,
) -> str:
    title = _to_bilingual_payload(stage.get("name"))
    if not _has_bilingual_text(title):
        title = _to_bilingual_payload(stage.get("title"))
    configured_slug_value = _resolve_slug_source_field_value(stage, slug_source_field)
    slug_tail = slugify_segment(
        configured_slug_value
        or title.get("de")
        or title.get("en")
        or stage.get("id")
        or "stage"
    )
    normalized_parent_route = normalize_parent_route(parent_route)
    if normalized_parent_route:
        return normalize_slug(f"{normalized_parent_route.strip('/')}/{slug_tail}")
    return normalize_slug(slug_tail)


def _preferred_slug_for_program_gig(
    gig: dict,
    parent_route: str | None = None,
    *,
    slug_source_field: str | None = None,
) -> str:
    gig_title = _to_bilingual_payload(gig.get("title"))
    if not _has_bilingual_text(gig_title):
        gig_title = _to_bilingual_payload(gig.get("artist_name"))
    configured_slug_value = _resolve_slug_source_field_value(gig, slug_source_field)
    slug_tail = slugify_segment(
        configured_slug_value
        or gig_title.get("de")
        or gig_title.get("en")
        or gig.get("id")
        or "gig"
    )
    normalized_parent_route = normalize_parent_route(parent_route)
    if normalized_parent_route:
        return normalize_slug(f"{normalized_parent_route.strip('/')}/{slug_tail}")
    return normalize_slug(slug_tail)


async def _sync_program_section_pages_impl(
    db,
    section_doc: dict,
    *,
    kind: str,
    item_id: str | None = None,
    force_rebuild: bool = False,
    sync_mode: str = ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
) -> dict:
    if not isinstance(section_doc, dict):
        return {"generated_count": 0, "warnings": []}

    normalized_kind = "stage" if str(kind or "").strip().lower() == "stage" else "gig"
    section_id = str(section_doc.get("_id") or "").strip()
    if not section_id:
        return {"generated_count": 0, "warnings": []}

    warnings: list[dict] = []
    normalized_item_id = str(item_id or "").strip()
    active_template = await resolve_active_item_page_template(
        db,
        "program",
        normalized_kind,
    )
    if not active_template:
        return {
            "generated_count": 0,
            "warnings": [],
            "parent_route": None,
            "item_kind": normalized_kind,
            "item_id": normalized_item_id or None,
            "skipped": True,
        }

    template = active_template["template"]
    parent_route = normalize_parent_route(active_template.get("effective_parent_route"))
    slug_source_field = str(active_template.get("slug_source_field") or "").strip()

    (
        shared_stages,
        shared_gigs,
        _catalog_metadata,
    ) = await _load_program_catalog_for_sync(db, section_doc)
    item_integration_mapping = await _load_program_item_integration_mapping_for_sync(
        db,
        section_doc,
        kind=normalized_kind,
    )
    stage_titles_by_id = build_program_stage_titles_lookup(shared_stages)

    integration_rows = await _load_integration_rows_for_template(
        db,
        template,
        warning_collector=warnings,
        source_type="program",
    )
    source_type_key = "program_stage" if normalized_kind == "stage" else "program_gig"
    rows = shared_stages if normalized_kind == "stage" else shared_gigs
    synced = 0
    active_source_ids: set[str] = set()
    next_rows: list[dict] = []
    target_found = False
    target_item_id_for_write = normalized_item_id
    target_page_slug = ""
    target_item_url = ""

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("id") or "").strip()
        if not item_id:
            if normalized_kind == "stage":
                item_id = f"stage-{index + 1}"
            else:
                item_id = f"gig-{index + 1}"
        next_row = deepcopy(row)
        next_row["id"] = item_id
        next_row_for_write = _strip_program_sync_internal_fields(next_row)
        row_external_item_key = str(row.get("integration_item_key") or "").strip()
        if (
            normalized_item_id
            and item_id != normalized_item_id
            and row_external_item_key != normalized_item_id
        ):
            continue

        target_found = True
        target_item_id_for_write = item_id
        source_id = f"program:{normalized_kind}:{item_id}"
        active_source_ids.add(source_id)
        desired_slug = (
            _preferred_slug_for_program_stage(
                row,
                parent_route,
                slug_source_field=slug_source_field,
            )
            if normalized_kind == "stage"
            else _preferred_slug_for_program_gig(
                row,
                parent_route,
                slug_source_field=slug_source_field,
            )
        )
        source_payload = (
            _source_payload_from_program_stage(row)
            if normalized_kind == "stage"
            else _source_payload_from_program_gig(
                row,
                stage_titles_by_id=stage_titles_by_id,
            )
        )
        final_slug = await _sync_generated_page_from_template(
            db,
            template_doc=template,
            source_payload=source_payload,
            source_type=source_type_key,
            source_id=source_id,
            desired_slug=desired_slug,
            source_parent_id=parent_route,
            integration_rows=integration_rows,
            item_integration_mapping=item_integration_mapping,
            warning_collector=warnings,
            force_rebuild=force_rebuild,
            sync_mode=sync_mode,
        )
        if not final_slug:
            next_rows.append(next_row_for_write)
            continue
        target_page_slug = str(final_slug or "").strip()
        target_item_url = f"/{final_slug}" if final_slug else ""
        next_row_for_write["page_slug"] = target_page_slug
        next_row_for_write["item_url"] = target_item_url
        next_rows.append(next_row_for_write)
        synced += 1

    if normalized_item_id and not target_found:
        warnings.append(
            {
                "code": "item_not_found",
                "message": f'No {normalized_kind} item found with id "{normalized_item_id}".',
            }
        )
        return {
            "generated_count": 0,
            "warnings": warnings,
            "template_path": compose_page_template_path(
                str(template.get("template_name") or "default"),
                template.get("parent_route"),
            ),
            "parent_route": parent_route,
            "item_kind": normalized_kind,
            "item_id": normalized_item_id,
        }

    if not normalized_item_id:
        cleanup_query: dict[str, Any] = {
            "template_managed": True,
            "template_source_type": source_type_key,
            "$and": [{"$or": _template_identity_filters(template)}],
            "template_source_id": {"$nin": list(active_source_ids) if active_source_ids else ["__none__"]},
        }
        if parent_route:
            cleanup_query["template_parent_route"] = parent_route
        else:
            cleanup_query["$and"].append(
                {
                    "$or": [
                        {"template_parent_route": None},
                        {"template_parent_route": {"$exists": False}},
                    ]
                }
            )
        await _delete_generated_pages_for_query(db, cleanup_query)

    if active_source_ids and parent_route:
        await _delete_generated_pages_for_query(
            db,
            {
                "template_managed": True,
                "template_source_type": source_type_key,
                "template_source_id": {"$in": list(active_source_ids)},
                "$or": _template_identity_filters(template),
                "template_parent_route": {"$ne": parent_route},
            },
        )

    now = datetime.utcnow()
    if normalized_item_id:
        if target_page_slug:
            if normalized_kind == "stage":
                await db[PROGRAM_SHARED_COLLECTION].update_one(
                    {"_id": PROGRAM_SHARED_DOC_ID, "stages.id": target_item_id_for_write},
                    {
                        "$set": {
                            "stages.$.page_slug": target_page_slug,
                            "stages.$.item_url": target_item_url,
                            "updated_at": now,
                        }
                    },
                )
            else:
                await program_catalog.update_program_gig_link(
                    db,
                    target_item_id_for_write,
                    slug=target_page_slug,
                    item_url=target_item_url,
                )
    else:
        shared_update_payload: dict[str, Any] = {"updated_at": now}
        if normalized_kind == "stage":
            shared_update_payload["stages"] = next_rows
            shared_update_payload["gig_ids"] = [
                str(gig.get("id") or "").strip()
                for gig in _strip_program_sync_internal_rows(shared_gigs)
                if str(gig.get("id") or "").strip()
            ]
        else:
            shared_update_payload["stages"] = _strip_program_sync_internal_rows(shared_stages)
            shared_update_payload["gig_ids"] = [
                str(gig.get("id") or "").strip()
                for gig in next_rows
                if str(gig.get("id") or "").strip()
            ]
            for row in next_rows:
                item_id = str(row.get("id") or "").strip()
                if not item_id:
                    continue
                await program_catalog.update_program_gig(db, item_id, row)
        await db[PROGRAM_SHARED_COLLECTION].update_one(
            {"_id": PROGRAM_SHARED_DOC_ID},
            {
                "$set": shared_update_payload,
                "$unset": {"gigs": ""},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    return {
        "generated_count": synced,
        "warnings": warnings,
        "template_path": compose_page_template_path(
            str(template.get("template_name") or "default"),
            template.get("parent_route"),
        ),
        "parent_route": parent_route,
        "item_kind": normalized_kind,
        "item_id": normalized_item_id or None,
    }


async def sync_program_stage_section_pages_report(
    db,
    section_doc: dict,
    *,
    item_id: str | None = None,
    force_rebuild: bool = False,
    sync_mode: str = ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
) -> dict:
    return await _sync_program_section_pages_impl(
        db,
        section_doc,
        kind="stage",
        item_id=item_id,
        force_rebuild=force_rebuild,
        sync_mode=sync_mode,
    )


async def sync_program_gig_section_pages_report(
    db,
    section_doc: dict,
    *,
    item_id: str | None = None,
    force_rebuild: bool = False,
    sync_mode: str = ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
) -> dict:
    return await _sync_program_section_pages_impl(
        db,
        section_doc,
        kind="gig",
        item_id=item_id,
        force_rebuild=force_rebuild,
        sync_mode=sync_mode,
    )


async def sync_program_stage_section_pages(db, section_doc: dict) -> int:
    report = await sync_program_stage_section_pages_report(db, section_doc)
    return int(report.get("generated_count", 0) or 0)


async def sync_program_gig_section_pages(db, section_doc: dict) -> int:
    report = await sync_program_gig_section_pages_report(db, section_doc)
    return int(report.get("generated_count", 0) or 0)


def _template_identity_filters(template_doc: dict) -> list[dict]:
    template_name = normalize_template_name(
        template_doc.get("template_name") or "default",
        default="default",
    )
    parent_route = normalize_parent_route(template_doc.get("parent_route"))
    template_path = compose_page_template_path(template_name, parent_route)
    template_key = build_template_key_for_page(template_name, parent_route)
    return [
        {"template_key": template_key},
        {"template_style_ref": template_path},
        {
            "template_template_name": template_name,
            "template_parent_route": parent_route,
        },
    ]


async def _clear_deleted_item_page_source_links(db, page_docs: list[dict]) -> None:
    if not page_docs:
        return

    deleted_slugs = {
        str(doc.get("slug") or "").strip().strip("/")
        for doc in page_docs
        if str(doc.get("slug") or "").strip()
    }
    now = datetime.utcnow()
    blog_item_oids: list[ObjectId] = []
    program_stage_ids: set[str] = set()
    program_gig_ids: set[str] = set()
    tile_ids_by_section_id: dict[str, set[str]] = {}

    for doc in page_docs:
        source_type = str(doc.get("template_source_type") or "").strip().lower()
        source_id = str(doc.get("template_source_id") or "").strip()
        if not source_type or not source_id:
            continue

        if source_type == "blog":
            oid = _safe_object_id(source_id)
            if oid is not None:
                blog_item_oids.append(oid)
            continue

        if source_type == "program_stage":
            item_id = source_id.removeprefix("program:stage:").strip()
            if item_id:
                program_stage_ids.add(item_id)
            continue

        if source_type == "program_gig":
            item_id = source_id.removeprefix("program:gig:").strip()
            if item_id:
                program_gig_ids.add(item_id)
            continue

        if source_type == "tiles" and source_id.startswith("tiles:"):
            try:
                _, section_id, tile_id = source_id.split(":", 2)
            except ValueError:
                continue
            if section_id and tile_id:
                tile_ids_by_section_id.setdefault(section_id, set()).add(tile_id)

    if blog_item_oids:
        blog_query: dict[str, Any] = {"_id": {"$in": blog_item_oids}}
        if deleted_slugs:
            blog_query["page_slug"] = {"$in": list(deleted_slugs)}
        await db["blog_shared"].update_many(
            blog_query,
            {"$set": {"page_slug": "", "updated_at": now}},
        )

    if program_gig_ids:
        await program_catalog.clear_program_gig_links(
            db,
            program_gig_ids,
            deleted_slugs=deleted_slugs,
        )

    if program_stage_ids:
        shared_doc = await db[PROGRAM_SHARED_COLLECTION].find_one({"_id": PROGRAM_SHARED_DOC_ID})
        if isinstance(shared_doc, dict):
            stages = (
                deepcopy(shared_doc.get("stages"))
                if isinstance(shared_doc.get("stages"), list)
                else []
            )
            changed = False

            def should_clear_link(row: dict) -> bool:
                if not deleted_slugs:
                    return True
                page_slug = str(row.get("page_slug") or "").strip().strip("/")
                item_url = str(row.get("item_url") or "").strip().strip("/")
                return page_slug in deleted_slugs or item_url in deleted_slugs

            for stage in stages:
                if (
                    isinstance(stage, dict)
                    and str(stage.get("id") or "").strip() in program_stage_ids
                    and should_clear_link(stage)
                ):
                    stage["page_slug"] = ""
                    stage["item_url"] = ""
                    changed = True

            if changed:
                await db[PROGRAM_SHARED_COLLECTION].update_one(
                    {"_id": PROGRAM_SHARED_DOC_ID},
                    {"$set": {"stages": stages, "updated_at": now}, "$unset": {"gigs": ""}},
                )

    for section_id, tile_ids in tile_ids_by_section_id.items():
        section_oid = _safe_object_id(section_id)
        if section_oid is None or not tile_ids:
            continue
        section_doc = await db["sections"].find_one({"_id": section_oid})
        if not isinstance(section_doc, dict):
            continue
        type_data = section_doc.get("type_data") if isinstance(section_doc.get("type_data"), dict) else {}
        tiles = type_data.get("tiles") if isinstance(type_data.get("tiles"), list) else []
        next_tiles: list[Any] = []
        changed = False
        for tile in tiles:
            if not isinstance(tile, dict):
                next_tiles.append(tile)
                continue
            next_tile = deepcopy(tile)
            tile_id = str(next_tile.get("id") or "").strip()
            page_slug = str(next_tile.get("page_slug") or "").strip().strip("/")
            if tile_id in tile_ids and (not deleted_slugs or page_slug in deleted_slugs):
                next_tile["page_slug"] = ""
                changed = True
            next_tiles.append(next_tile)
        if changed:
            await db["sections"].update_one(
                {"_id": section_oid},
                {
                    "$set": {
                        "type_data.tiles": next_tiles,
                        "updated_at": now,
                    }
                },
            )


async def cleanup_generated_item_pages_for_template(db, template_doc: dict) -> dict:
    if not _is_item_page_template_doc(template_doc):
        raise ValueError("Template is not an item-page template")

    template_name = normalize_template_name(
        template_doc.get("template_name") or "default",
        default="default",
    )
    parent_route = normalize_parent_route(template_doc.get("parent_route"))
    template_path = compose_page_template_path(template_name, parent_route)
    pages_coll = db["pages"]
    docs = await pages_coll.find(
        {
            "template_managed": True,
            "$or": _template_identity_filters(template_doc),
        }
    ).to_list(length=5000)

    if not docs:
        return {
            "ok": True,
            "template_path": template_path,
            "removed_count": 0,
        }

    for doc in docs:
        await _delete_managed_page_resources(db, doc)
    await pages_coll.delete_many({"_id": {"$in": [doc["_id"] for doc in docs]}})
    await _clear_deleted_item_page_source_links(db, docs)

    return {
        "ok": True,
        "template_path": template_path,
        "removed_count": len(docs),
    }


async def _regenerate_program_items_for_template(
    db,
    template_doc: dict,
    *,
    kind: str,
    warnings: list[dict],
) -> dict:
    normalized_kind = "stage" if str(kind or "").strip().lower() == "stage" else "gig"
    source_type_key = "program_stage" if normalized_kind == "stage" else "program_gig"
    template_name = normalize_template_name(
        template_doc.get("template_name") or "default",
        default="default",
    )
    parent_route = normalize_parent_route(template_doc.get("parent_route"))
    template_path = compose_page_template_path(template_name, parent_route)
    active_template = await resolve_active_item_page_template(
        db,
        "program",
        normalized_kind,
    )
    if not active_template or str(active_template.get("template_path") or "") != template_path:
        return {
            "generated_count": 0,
            "item_kind": normalized_kind,
            "parent_route": None,
            "skipped": True,
        }
    parent_route = normalize_parent_route(active_template.get("effective_parent_route"))
    slug_source_field = str(active_template.get("slug_source_field") or "").strip()

    shared_doc = await program_catalog.capture_program_shared_content(db)
    shared_gig_primary_key_path = program_catalog.integration_output_primary_key_path_from_cache_state(
        shared_doc.get("program_gigs_integration_mapping_cache_state")
        if isinstance(shared_doc, dict)
        else None
    )
    shared_gig_selected_integration_id = program_catalog.integration_selected_id_from_mapping(
        shared_doc.get("program_gigs_integration_mapping")
        if isinstance(shared_doc, dict)
        else None
    )
    raw_stages = (
        shared_doc.get("stages")
        if isinstance(shared_doc, dict) and isinstance(shared_doc.get("stages"), list)
        else []
    )
    raw_gigs = (
        shared_doc.get("gigs")
        if isinstance(shared_doc, dict) and isinstance(shared_doc.get("gigs"), list)
        else []
    )
    stages = [
        _normalize_program_stage_for_sync(raw_stage, index)
        for index, raw_stage in enumerate(raw_stages)
    ]
    gigs = [
        _normalize_program_gig_for_sync(
            raw_gig,
            index,
            primary_key_path=shared_gig_primary_key_path,
            selected_integration_id=shared_gig_selected_integration_id,
        )
        for index, raw_gig in enumerate(raw_gigs)
    ]
    stage_titles_by_id = build_program_stage_titles_lookup(stages)

    integration_rows = await _load_integration_rows_for_template(
        db,
        template_doc,
        warning_collector=warnings,
        source_type="program",
    )
    item_integration_mapping = await _load_program_item_integration_mapping_for_sync(
        db,
        None,
        kind=normalized_kind,
    )
    rows = stages if normalized_kind == "stage" else gigs
    next_rows: list[dict] = []
    generated_count = 0
    active_source_ids: set[str] = set()

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("id") or "").strip() or (
            f"stage-{index + 1}" if normalized_kind == "stage" else f"gig-{index + 1}"
        )
        next_row = deepcopy(row)
        next_row["id"] = item_id
        next_row_for_write = _strip_program_sync_internal_fields(next_row)
        source_id = f"program:{normalized_kind}:{item_id}"
        active_source_ids.add(source_id)
        try:
            desired_slug = (
                _preferred_slug_for_program_stage(
                    next_row,
                    parent_route,
                    slug_source_field=slug_source_field,
                )
                if normalized_kind == "stage"
                else _preferred_slug_for_program_gig(
                    next_row,
                    parent_route,
                    slug_source_field=slug_source_field,
                )
            )
            source_payload = (
                _source_payload_from_program_stage(next_row)
                if normalized_kind == "stage"
                else _source_payload_from_program_gig(
                    next_row,
                    stage_titles_by_id=stage_titles_by_id,
                )
            )
            final_slug = await _sync_generated_page_from_template(
                db,
                template_doc=template_doc,
                source_payload=source_payload,
                source_type=source_type_key,
                source_id=source_id,
                desired_slug=desired_slug,
                source_parent_id=parent_route,
                integration_rows=integration_rows,
                item_integration_mapping=item_integration_mapping,
                warning_collector=warnings,
                force_rebuild=True,
                reset_status_to_init=True,
            )
        except Exception as exc:
            _append_sync_warning(
                warnings,
                code="generated_page_regeneration_failed",
                message=f"Failed to regenerate generated page for {source_type_key} item {item_id}: {exc}",
                source_id=source_id,
                source_type=source_type_key,
                template_name=template_name,
                parent_route=parent_route,
            )
            next_rows.append(next_row_for_write)
            continue
        if not final_slug:
            next_rows.append(next_row_for_write)
            continue
        next_row_for_write["page_slug"] = str(final_slug or "").strip()
        next_row_for_write["item_url"] = f"/{final_slug}" if final_slug else ""
        next_rows.append(next_row_for_write)
        generated_count += 1

    cleanup_query: dict[str, Any] = {
        "template_managed": True,
        "template_source_type": source_type_key,
        "$or": _template_identity_filters(template_doc),
        "template_source_id": {"$nin": list(active_source_ids) if active_source_ids else ["__none__"]},
    }
    await _delete_generated_pages_for_query(db, cleanup_query)

    now = datetime.utcnow()
    update_payload: dict[str, Any] = {"updated_at": now}
    if normalized_kind == "stage":
        update_payload["stages"] = next_rows
        update_payload["gig_ids"] = [
            str(gig.get("id") or "").strip()
            for gig in _strip_program_sync_internal_rows(gigs)
            if str(gig.get("id") or "").strip()
        ]
    else:
        update_payload["stages"] = _strip_program_sync_internal_rows(stages)
        update_payload["gig_ids"] = [
            str(gig.get("id") or "").strip()
            for gig in next_rows
            if str(gig.get("id") or "").strip()
        ]
        for row in next_rows:
            item_id = str(row.get("id") or "").strip()
            if not item_id:
                continue
            await program_catalog.update_program_gig(db, item_id, row)
    await db[PROGRAM_SHARED_COLLECTION].update_one(
        {"_id": PROGRAM_SHARED_DOC_ID},
        {
            "$set": update_payload,
            "$unset": {"gigs": ""},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    return {
        "generated_count": generated_count,
        "item_kind": normalized_kind,
        "parent_route": parent_route,
    }


async def _regenerate_tile_items_for_template(
    db,
    template_doc: dict,
    *,
    warnings: list[dict],
) -> dict:
    template_name = normalize_template_name(
        template_doc.get("template_name") or "default",
        default="default",
    )
    parent_route = normalize_parent_route(template_doc.get("parent_route"))
    template_path = compose_page_template_path(template_name, parent_route)
    if not parent_route:
        return {
            "generated_count": 0,
            "section_count": 0,
            "parent_route": None,
            "skipped": True,
        }
    integration_rows = await _load_integration_rows_for_template(
        db,
        template_doc,
        warning_collector=warnings,
        source_type="tiles",
    )

    section_ids: set[ObjectId] = set()
    async for section_doc in db["sections"].find({"section_type": "tiles"}):
        type_data = section_doc.get("type_data") if isinstance(section_doc.get("type_data"), dict) else {}
        selected_template_path = _extract_item_page_template_path(type_data)
        if selected_template_path == template_path and isinstance(section_doc.get("_id"), ObjectId):
            section_ids.add(section_doc["_id"])

    existing_pages = await db["pages"].find(
        {
            "template_managed": True,
            "template_source_type": "tiles",
            "$or": _template_identity_filters(template_doc),
        },
        {"template_source_parent_id": 1},
    ).to_list(length=5000)
    for page_doc in existing_pages:
        oid = _safe_object_id(page_doc.get("template_source_parent_id"))
        if oid is not None:
            section_ids.add(oid)

    generated_count = 0
    active_source_ids: set[str] = set()
    for section_oid in section_ids:
        section_doc = await db["sections"].find_one({"_id": section_oid})
        if not isinstance(section_doc, dict):
            continue
        section_id = str(section_doc.get("_id") or "").strip()
        type_data = section_doc.get("type_data") if isinstance(section_doc.get("type_data"), dict) else {}
        tiles = type_data.get("tiles") if isinstance(type_data.get("tiles"), list) else []
        next_tiles: list[dict] = []
        for tile in tiles:
            if not isinstance(tile, dict):
                continue
            next_tile = deepcopy(tile)
            tile_id = str(next_tile.get("id") or "").strip()
            if not tile_id:
                overlay_title = (
                    next_tile.get("title")
                    if isinstance(next_tile.get("title"), dict)
                    else next_tile.get("overlay_text")
                    if isinstance(next_tile.get("overlay_text"), dict)
                    else {}
                )
                tile_id = slugify_segment(
                    overlay_title.get("de") if isinstance(overlay_title, dict) else "tile",
                    fallback=str(ObjectId()),
                )
                next_tile["id"] = tile_id
            source_id = f"tiles:{section_id}:{tile_id}"
            active_source_ids.add(source_id)
            try:
                final_slug = await _sync_generated_page_from_template(
                    db,
                    template_doc=template_doc,
                    source_payload=_source_payload_from_tile(section_doc, next_tile),
                    source_type="tiles",
                    source_id=source_id,
                    desired_slug=_preferred_slug_for_tile(next_tile, parent_route),
                    source_parent_id=section_id,
                    integration_rows=integration_rows,
                    warning_collector=warnings,
                    force_rebuild=True,
                    reset_status_to_init=True,
                )
            except Exception as exc:
                _append_sync_warning(
                    warnings,
                    code="generated_page_regeneration_failed",
                    message=f"Failed to regenerate generated page for tile item {tile_id}: {exc}",
                    source_id=source_id,
                    source_type="tiles",
                    template_name=template_name,
                    parent_route=parent_route,
                )
                next_tiles.append(next_tile)
                continue
            if not final_slug:
                next_tiles.append(next_tile)
                continue
            next_tile["page_slug"] = str(final_slug or "").strip()
            next_tiles.append(next_tile)
            generated_count += 1
        await db["sections"].update_one(
            {"_id": section_oid},
            {
                "$set": {
                    "type_data.tiles": next_tiles,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    await _delete_generated_pages_for_query(
        db,
        {
            "template_managed": True,
            "template_source_type": "tiles",
            "$or": _template_identity_filters(template_doc),
            "template_source_id": {"$nin": list(active_source_ids) if active_source_ids else ["__none__"]},
        },
    )

    return {
        "generated_count": generated_count,
        "section_count": len(section_ids),
        "parent_route": parent_route,
    }


async def regenerate_all_item_pages_for_template(db, template_doc: dict) -> dict:
    if not _is_item_page_template_doc(template_doc):
        raise ValueError("Template is not an item-page template")

    source_type = str(template_doc.get("source_type") or "").strip().lower()
    source_kind = str(template_doc.get("source_kind") or "").strip().lower()
    template_name = normalize_template_name(
        template_doc.get("template_name") or "default",
        default="default",
    )
    parent_route = normalize_parent_route(template_doc.get("parent_route"))
    template_path = compose_page_template_path(template_name, parent_route)
    warnings: list[dict] = []

    if source_type == "blog":
        active_template = await resolve_active_item_page_template(db, "blog", "item")
        if not active_template or str(active_template.get("template_path") or "") != template_path:
            return {
                "ok": True,
                "template_path": template_path,
                "source_type": source_type,
                "generated_count": 0,
                "status": "init",
                "warnings": [],
                "skipped": True,
                "item_kind": "item",
            }
        effective_parent_route = normalize_parent_route(active_template.get("effective_parent_route"))
        report = await _sync_all_blog_items_with_template_report(
            db,
            template_doc,
            override_parent_route=effective_parent_route,
            slug_source_field=str(active_template.get("slug_source_field") or "").strip(),
            force_rebuild=True,
            reset_status_to_init=True,
        )
        warnings.extend(report.get("warnings") if isinstance(report.get("warnings"), list) else [])
        generated_count = int(report.get("generated_count", 0) or 0)
        detail = {"item_kind": "item"}
    elif source_type == "program":
        normalized_kind = "stage" if source_kind == "stage" else "gig"
        report = await _regenerate_program_items_for_template(
            db,
            template_doc,
            kind=normalized_kind,
            warnings=warnings,
        )
        generated_count = int(report.get("generated_count", 0) or 0)
        detail = {"item_kind": normalized_kind}
    elif source_type == "tiles":
        report = await _regenerate_tile_items_for_template(
            db,
            template_doc,
            warnings=warnings,
        )
        generated_count = int(report.get("generated_count", 0) or 0)
        detail = {"section_count": int(report.get("section_count", 0) or 0)}
    else:
        raise ValueError("Template source type does not support generated item pages")

    return {
        "ok": True,
        "template_path": template_path,
        "source_type": source_type,
        "generated_count": generated_count,
        "status": "init",
        "warnings": warnings[:200],
        **detail,
    }


async def cleanup_program_generated_pages_for_section(
    db,
    section_doc: dict,
    *,
    kind: str | None = None,
) -> dict:
    if not isinstance(section_doc, dict):
        return {"removed_count": 0}

    normalized_kind = str(kind or "").strip().lower()
    if normalized_kind == "stage":
        source_types = ["program_stage"]
    elif normalized_kind == "gig":
        source_types = ["program_gig"]
    else:
        source_types = ["program_stage", "program_gig"]
    target_routes: list[str] = []
    if "program_stage" in source_types:
        active_stage = await resolve_active_item_page_template(db, "program", "stage")
        stage_parent_route = (
            normalize_parent_route(active_stage.get("effective_parent_route"))
            if isinstance(active_stage, dict)
            else None
        )
        if stage_parent_route:
            target_routes.append(stage_parent_route)
    if "program_gig" in source_types:
        active_gig = await resolve_active_item_page_template(db, "program", "gig")
        gig_parent_route = (
            normalize_parent_route(active_gig.get("effective_parent_route"))
            if isinstance(active_gig, dict)
            else None
        )
        if gig_parent_route:
            target_routes.append(gig_parent_route)
    target_routes = [route for route in dict.fromkeys(target_routes) if route]
    if not target_routes:
        return {
            "removed_count": 0,
            "parent_routes": [],
            "parent_route": None,
        }

    pages_coll = db["pages"]
    query: dict[str, Any] = {
        "template_managed": True,
        "template_source_type": {"$in": source_types},
    }
    if target_routes:
        query["template_parent_route"] = {"$in": target_routes}
    docs = await pages_coll.find(query).to_list(length=5000)
    for doc in docs:
        await _delete_managed_page_resources(db, doc)
    if docs:
        await pages_coll.delete_many({"_id": {"$in": [doc["_id"] for doc in docs]}})

    shared_doc = await program_catalog.capture_program_shared_content(db)
    shared_stages = (
        [
            _normalize_program_stage_for_sync(raw_stage, index)
            for index, raw_stage in enumerate(shared_doc.get("stages") or [])
        ]
        if isinstance(shared_doc, dict)
        else []
    )
    if "program_stage" in source_types:
        for stage in shared_stages:
            stage["page_slug"] = ""
            stage["item_url"] = ""
    if "program_gig" in source_types:
        gig_ids = {
            str(raw_gig.get("id") or "").strip()
            for raw_gig in shared_doc.get("gigs", [])
            if isinstance(raw_gig, dict) and str(raw_gig.get("id") or "").strip()
        }
        await program_catalog.clear_program_gig_links(db, gig_ids)
    now = datetime.utcnow()
    await db[PROGRAM_SHARED_COLLECTION].update_one(
        {"_id": PROGRAM_SHARED_DOC_ID},
        {
            "$set": {
                "stages": shared_stages,
                "gig_ids": [
                    str(raw_gig.get("id") or "").strip()
                    for raw_gig in shared_doc.get("gigs", [])
                    if isinstance(raw_gig, dict) and str(raw_gig.get("id") or "").strip()
                ],
                "updated_at": now,
            },
            "$unset": {"gigs": ""},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    return {
        "removed_count": len(docs),
        "item_kind": normalized_kind or "all",
        "parent_routes": target_routes,
        "parent_route": target_routes[0] if len(target_routes) == 1 else None,
    }


def build_builder_section_id(kind: str, owner_id: str, embedded_id: str | None = None) -> str:
    owner = str(owner_id or "").strip()
    embedded = str(embedded_id or "").strip()
    if kind == "section":
        return f"{SECTION_TEMPLATE_ID_PREFIX}{owner}"
    if kind == "page":
        return f"{PAGE_SECTION_ID_PREFIX}{owner}__{embedded}"
    if kind == "container":
        return f"{CONTAINER_SECTION_ID_PREFIX}{owner}__{embedded}"
    raise ValueError("Unsupported builder section kind")


def parse_builder_section_id(section_id: str) -> tuple[str, str, str | None]:
    value = str(section_id or "")
    if value.startswith(SECTION_TEMPLATE_ID_PREFIX):
        return "section", value[len(SECTION_TEMPLATE_ID_PREFIX):], None
    if value.startswith(PAGE_SECTION_ID_PREFIX):
        payload = value[len(PAGE_SECTION_ID_PREFIX):]
        owner_id, _, embedded_id = payload.partition("__")
        if owner_id and embedded_id:
            return "page", owner_id, embedded_id
    if value.startswith(CONTAINER_SECTION_ID_PREFIX):
        payload = value[len(CONTAINER_SECTION_ID_PREFIX):]
        owner_id, _, embedded_id = payload.partition("__")
        if owner_id and embedded_id:
            return "container", owner_id, embedded_id
    raise ValueError("Unsupported template section id")


def build_builder_header_id_for_page(page_doc_id: str) -> str:
    return f"{PAGE_HEADER_ID_PREFIX}{str(page_doc_id).strip()}"


def parse_builder_header_id(header_id: str) -> tuple[str, str]:
    value = str(header_id or "")
    if value.startswith(PAGE_HEADER_ID_PREFIX):
        return "page", value[len(PAGE_HEADER_ID_PREFIX):]
    raise ValueError("Unsupported template header id")


def format_template_section_for_builder(doc: dict) -> dict:
    section_id = build_builder_section_id("section", str(doc.get("_id") or ""))
    section_integration_mapping = normalize_section_integration_mapping(
        doc.get("section_integration_mapping")
    )
    return {
        "_id": section_id,
        "id": section_id,
        "section_type": doc.get("section_type", "text"),
        "section_template_name": normalize_template_name(
            doc.get("template_name"),
            default="default",
        ),
        "title_placeholder": doc.get("title_placeholder", ""),
        "title": doc.get("title") if isinstance(doc.get("title"), dict) else {"de": "", "en": ""},
        "type_data": doc.get("type_data") if isinstance(doc.get("type_data"), dict) else {},
        "order": 0,
        "visible": True,
        "limit": None,
        "width_n": 1,
        "width_d": 1,
        "device_visibility": {"mobile": True, "tablet": True, "desktop": True},
        "design_overrides": deepcopy(doc.get("design_overrides")) if isinstance(doc.get("design_overrides"), dict) else None,
        "section_integration_mapping": section_integration_mapping,
        "section_output_mapping": normalize_section_output_mapping(
            doc.get("section_output_mapping")
        ),
    }


def format_embedded_section_for_builder(doc_id: Any, section: dict, *, kind: str) -> dict:
    embedded_section_id = str(section.get("id") or "").strip()
    section_id = build_builder_section_id(kind, str(doc_id), embedded_section_id)
    normalized = normalize_embedded_section(section)
    section_integration_mapping = normalize_section_integration_mapping(
        normalized.get("section_integration_mapping")
    )
    payload = {
        "_id": section_id,
        "id": section_id,
        "template_embedded_section_id": embedded_section_id or normalized.get("id"),
        "section_type": normalized["section_type"],
        "section_template_name": normalized.get("section_template_name"),
        "title_placeholder": normalized["title_placeholder"],
        "title": normalized["title"],
        "type_data": normalized.get("type_data") if isinstance(normalized.get("type_data"), dict) else {},
        "order": int(normalized.get("order", 0) or 0),
        "visible": bool(normalized.get("visible", True)),
        "limit": normalized.get("limit"),
        "width_n": int(normalized.get("width_n", 1) or 1),
        "width_d": int(normalized.get("width_d", 1) or 1),
        "device_visibility": normalized.get("device_visibility")
        if isinstance(normalized.get("device_visibility"), dict)
        else {"mobile": True, "tablet": True, "desktop": True},
        "design_overrides": deepcopy(normalized.get("design_overrides"))
        if isinstance(normalized.get("design_overrides"), dict)
        else None,
        "section_integration_mapping": section_integration_mapping,
    }
    if kind == "section":
        payload["section_output_mapping"] = normalize_section_output_mapping(
            section.get("section_output_mapping")
            if isinstance(section, dict)
            else None
        )
    return payload


def _map_section_structure_ids_for_builder(
    raw_structure: Any,
    *,
    embedded_to_builder_id: dict[str, str],
    ordered_builder_ids: list[str],
) -> list[dict]:
    mapped_seed: list[dict] = []
    for node in raw_structure if isinstance(raw_structure, list) else []:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type") or "").strip().lower()
        if node_type == "section":
            mapped_section_id = embedded_to_builder_id.get(str(node.get("section_id") or "").strip())
            if mapped_section_id:
                mapped_seed.append(
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
            mapped_member = embedded_to_builder_id.get(str(raw_member or "").strip())
            if mapped_member:
                mapped_members.append(mapped_member)
        if mapped_members:
            mapped_seed.append(
                {
                    "type": "container",
                    "container_id": str(node.get("container_id") or "").strip() or f"builder_container_{ObjectId()}",
                    "section_ids": mapped_members,
                }
            )
    return resolve_section_structure(mapped_seed, ordered_builder_ids)


def build_page_full_payload_for_template_page(path: str, page_doc: dict) -> dict:
    template_name, parent_route = parse_page_template_path(path)
    builder_slug = f"__template_page__/{compose_page_template_path(template_name, parent_route)}"

    sections_payload = page_doc.get("sections") if isinstance(page_doc.get("sections"), list) else []
    sections = []
    embedded_to_builder_id: dict[str, str] = {}
    for section in sections_payload:
        if not isinstance(section, dict):
            continue
        formatted = format_embedded_section_for_builder(page_doc.get("_id"), section, kind="page")
        sections.append(formatted)
        embedded_id = str(section.get("id") or "").strip()
        builder_id = str(formatted.get("id") or "").strip()
        if embedded_id and builder_id:
            embedded_to_builder_id[embedded_id] = builder_id
    sections.sort(key=lambda section: int(section.get("order", 0) or 0))
    ordered_builder_ids = [str(section.get("id") or "").strip() for section in sections if str(section.get("id") or "").strip()]
    section_structure = _map_section_structure_ids_for_builder(
        page_doc.get("section_structure"),
        embedded_to_builder_id=embedded_to_builder_id,
        ordered_builder_ids=ordered_builder_ids,
    )
    page_integration_mapping = resolve_page_integration_mapping_for_template_doc(page_doc)

    header_payload = deepcopy(page_doc.get("header")) if isinstance(page_doc.get("header"), dict) else None
    header_id = build_builder_header_id_for_page(str(page_doc.get("_id") or "")) if header_payload else None

    return {
        "id": str(page_doc.get("_id") or ""),
        "slug": builder_slug,
        "title": deepcopy(page_doc.get("title")) if isinstance(page_doc.get("title"), dict) else {"de": "", "en": ""},
        "has_header": bool(page_doc.get("has_header", False)),
        "header_id": header_id,
        "header": {
            "id": header_id,
            **header_payload,
        }
        if header_payload
        else None,
        "sections": sections,
        "section_structure": section_structure,
        "status": normalize_page_status(page_doc.get("status"), fallback="hidden"),
        "effective_status": effective_page_status_from_stored(page_doc.get("status")),
        "is_visible": False,
        "publish_at": None,
        "unpublish_at": None,
        "in_menu": bool(page_doc.get("in_menu", False)),
        "in_footer": bool(page_doc.get("in_footer", False)),
        "hide_in_admin_sitemap": bool(page_doc.get("hide_in_admin_sitemap", True)),
        "hide_from_sitemap": bool(page_doc.get("hide_from_sitemap", True)),
        "hide_subtree_from_sitemap": bool(page_doc.get("hide_subtree_from_sitemap", True)),
        "sitemap_priority": page_doc.get("sitemap_priority"),
        "sitemap_changefreq": page_doc.get("sitemap_changefreq"),
        "generated_from_blog": False,
        "menu_title": deepcopy(page_doc.get("menu_title")) if isinstance(page_doc.get("menu_title"), dict) else None,
        "menu_order": int(page_doc.get("menu_order", 0) or 0),
        "footer_order": int(page_doc.get("footer_order", 0) or 0),
        "redirect_to": page_doc.get("redirect_to"),
        "section_bg_pinned_start_key": str(page_doc.get("section_bg_pinned_start_key") or ""),
        "section_bg_pinned_end_key": str(page_doc.get("section_bg_pinned_end_key") or ""),
        "template_kind": str(
            page_doc.get("template_kind")
            or (
                "item_page"
                if (
                    parent_route
                    or str(page_doc.get("source_type") or "").strip().lower() in {"blog", "tiles", "program"}
                )
                else "static_page"
            )
        ),
        "source_type": page_doc.get("source_type"),
        "source_kind": page_doc.get("source_kind"),
        "source_route_ref": str(page_doc.get("source_route_ref") or "").strip() or None,
        "section_template_ref": normalize_section_template_ref(page_doc.get("section_template_ref")),
        "page_integration_mapping": page_integration_mapping,
        "integration_match_mappings": deepcopy(page_doc.get("integration_match_mappings"))
        if isinstance(page_doc.get("integration_match_mappings"), list)
        else [],
        "auto_match_rules": deepcopy(page_doc.get("auto_match_rules"))
        if isinstance(page_doc.get("auto_match_rules"), dict)
        else {},
        "template_design_current": deepcopy(page_doc.get("template_design_current"))
        if isinstance(page_doc.get("template_design_current"), dict)
        else None,
        "template_design_published": deepcopy(page_doc.get("template_design_published"))
        if isinstance(page_doc.get("template_design_published"), dict)
        else None,
        "template_design_initialized_from_global_version_id": (
            str(page_doc.get("template_design_initialized_from_global_version_id") or "").strip() or None
        ),
        "template_design_updated_at": page_doc.get("template_design_updated_at"),
        "template_design_published_at": page_doc.get("template_design_published_at"),
        "page_design_overrides": None,
        "created_at": page_doc.get("created_at"),
        "updated_at": page_doc.get("updated_at"),
    }


def build_page_full_payload_for_template_section(section_type: str, template_name: str, section_doc: dict) -> dict:
    name = normalize_template_name(template_name, default="default")
    builder_slug = f"__template_section__/{section_type}/{name}"
    section_payload = format_template_section_for_builder(section_doc)

    return {
        "id": str(section_doc.get("_id") or ""),
        "slug": builder_slug,
        "title": deepcopy(section_doc.get("title")) if isinstance(section_doc.get("title"), dict) else get_default_title(section_type),
        "has_header": False,
        "header_id": None,
        "header": None,
        "sections": [section_payload],
        "section_structure": [
            {
                "type": "section",
                "section_id": str(section_payload.get("id") or ""),
            }
        ],
        "status": "hidden",
        "effective_status": "hidden",
        "is_visible": False,
        "publish_at": None,
        "unpublish_at": None,
        "in_menu": False,
        "in_footer": False,
        "hide_in_admin_sitemap": True,
        "hide_from_sitemap": True,
        "hide_subtree_from_sitemap": True,
        "sitemap_priority": None,
        "sitemap_changefreq": None,
        "generated_from_blog": False,
        "menu_title": None,
        "menu_order": 0,
        "footer_order": 0,
        "redirect_to": None,
        "section_bg_pinned_start_key": "",
        "section_bg_pinned_end_key": "",
        "section_output_mapping": normalize_section_output_mapping(
            section_doc.get("section_output_mapping")
        ),
        "created_at": section_doc.get("created_at"),
        "updated_at": section_doc.get("updated_at"),
    }


def build_page_full_payload_for_template_container(template_name: str, container_doc: dict) -> dict:
    name = normalize_template_name(template_name)
    builder_slug = f"__template_container__/{name}"

    sections_payload = container_doc.get("sections") if isinstance(container_doc.get("sections"), list) else []
    sections = []
    embedded_to_builder_id: dict[str, str] = {}
    for section in sections_payload:
        if not isinstance(section, dict):
            continue
        formatted = format_embedded_section_for_builder(container_doc.get("_id"), section, kind="container")
        sections.append(formatted)
        embedded_id = str(section.get("id") or "").strip()
        builder_id = str(formatted.get("id") or "").strip()
        if embedded_id and builder_id:
            embedded_to_builder_id[embedded_id] = builder_id
    sections.sort(key=lambda section: int(section.get("order", 0) or 0))
    ordered_builder_ids = [str(section.get("id") or "").strip() for section in sections if str(section.get("id") or "").strip()]
    section_structure = _map_section_structure_ids_for_builder(
        container_doc.get("section_structure"),
        embedded_to_builder_id=embedded_to_builder_id,
        ordered_builder_ids=ordered_builder_ids,
    )
    section_structure = ensure_container_template_section_structure(
        section_structure,
        ordered_builder_ids,
    )

    return {
        "id": str(container_doc.get("_id") or ""),
        "slug": builder_slug,
        "title": deepcopy(container_doc.get("title")) if isinstance(container_doc.get("title"), dict) else {"de": "", "en": ""},
        "has_header": False,
        "header_id": None,
        "header": None,
        "sections": sections,
        "section_structure": section_structure,
        "status": "hidden",
        "effective_status": "hidden",
        "is_visible": False,
        "publish_at": None,
        "unpublish_at": None,
        "in_menu": False,
        "in_footer": False,
        "hide_in_admin_sitemap": True,
        "hide_from_sitemap": True,
        "hide_subtree_from_sitemap": True,
        "sitemap_priority": None,
        "sitemap_changefreq": None,
        "generated_from_blog": False,
        "menu_title": None,
        "menu_order": 0,
        "footer_order": 0,
        "redirect_to": None,
        "section_bg_pinned_start_key": "",
        "section_bg_pinned_end_key": "",
        "created_at": container_doc.get("created_at"),
        "updated_at": container_doc.get("updated_at"),
    }
