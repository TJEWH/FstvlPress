"""
Integrations Router

Manages external API/crawler integrations for importing data into sections.
"""

from __future__ import annotations

import asyncio
import base64
import copy
import csv
import hashlib
import io
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Literal, NamedTuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from app.collection_names import (
    INTEGRATION_CONFIG_COLLECTION,
    INTEGRATION_DATA_COLLECTION,
    INTEGRATION_EXPOSURE_CONFIG_COLLECTION,
    INTEGRATION_ITEM_OVERRIDES_COLLECTION,
    INTEGRATION_ITEM_REVIEWS_COLLECTION,
    INTEGRATION_JOBS_COLLECTION,
    INTEGRATION_LOCAL_ITEMS_COLLECTION,
    INTEGRATION_MEDIA_REGISTRY_COLLECTION,
    INTEGRATION_SCHEMAS_COLLECTION,
    INTEGRATION_SECTION_CACHE_VERSIONS_COLLECTION,
)
from app.db import get_client
from app.deps import require_permission
from app.job_retention import job_expires_at
from app.media_responsive import build_asset_responsive_variants
from app.models.cms import (
    IntegrationCreate,
    IntegrationDataPreview,
    IntegrationDataResponse,
    IntegrationHealthResponse,
    IntegrationResponse,
    IntegrationUpdate,
)
from app.program_catalog import capture_program_shared_content
from app.settings import settings
from app.integration_review import (
    IntegrationReviewError,
    get_effective_integration_data_doc as get_shared_effective_integration_data_doc,
    upsert_integration_review_override,
)
from app.routers.v1.assets import import_asset_from_url_payload
from app.template_sync import (
    build_template_key_for_page,
    capture_item_page_routes,
    compose_page_template_path,
    effective_item_page_parent_route_for_template,
    normalize_parent_route,
    normalize_page_template_path_value,
    normalize_section_integration_mapping,
    normalize_template_name,
    parse_builder_section_id,
    parse_page_template_path,
    resolve_active_item_page_template,
    sync_generated_item_pages_for_integration_review_change,
)


class IntegrationDraftHealthRequest(BaseModel):
    """Request body for draft health checks before saving."""

    url: str | None = None
    type: str = "api"
    auth_type: str = "none"
    key_name: str | None = None


class IntegrationDraftInspectRequest(BaseModel):
    """Request body for draft inspect calls before saving."""

    url: str | None = None
    type: str = "api"
    auth_type: str = "none"
    key_name: str | None = None
    response_type: str = "json"
    response_path: str | None = None
    crawler_pagination_config: dict[str, Any] | None = None


class IntegrationDraftInspectResponse(BaseModel):
    """Response body for draft inspect calls."""

    data: Any
    item_count: int


IntegrationReviewSchemaFieldType = Literal[
    "text",
    "number",
    "boolean",
    "date",
    "datetime",
    "url",
    "image",
    "list",
    "json",
    "null",
    "undefined",
]
IntegrationReviewItemState = Literal["open", "in_progress", "done"]
REVIEW_ITEM_STATES: tuple[IntegrationReviewItemState, ...] = ("open", "in_progress", "done")
REVIEW_BADGE_TAG_FILTER_INCOMPLETE = "__badge:incomplete"
REVIEW_BADGE_TAG_FILTER_OVERRIDE = "__badge:override"
REVIEW_BADGE_TAG_FILTER_LOCAL = "__badge:local"
REVIEW_PAGE_STATE_TAG_FILTER_PREFIX = "__page:"
REVIEW_PAGE_STATE_TAG_FILTER_MISSING = "__page:missing"
REVIEW_PAGE_STATE_TAG_FILTER_STATUSES = ("init", "hidden", "published", "under_construction", "unknown")
REVIEW_PAGE_STATE_TAG_FILTER_LABELS = {
    REVIEW_PAGE_STATE_TAG_FILTER_MISSING: "No page",
    "__page:init": "Page: Init",
    "__page:hidden": "Page: Hidden",
    "__page:published": "Page: Published",
    "__page:under_construction": "Page: Under construction",
    "__page:unknown": "Page: Unknown",
}


class IntegrationReviewItemPatchRequest(BaseModel):
    """Field-level local override for an integration item."""

    item_key: str = Field(min_length=1)
    field_path: str = Field(min_length=1)
    value: Any = None


class IntegrationReviewItemMetaPatchRequest(BaseModel):
    """Item-level review workflow metadata."""

    item_key: str = Field(min_length=1)
    state: IntegrationReviewItemState | None = None
    tags: list[str] | None = None


class IntegrationReviewItemCreateRequest(BaseModel):
    """Local-only review item generated from schema field values."""

    values: dict[str, Any] = Field(default_factory=dict)
    item_key: str | None = None


class IntegrationReviewSyncSettingsPatchRequest(BaseModel):
    """Integration-level item page sync settings from review."""

    item_page_sync_blocked: bool = False


class IntegrationSchemaUpdateRequest(BaseModel):
    """Manual schema settings keyed by integration field path."""

    manual_types: dict[str, IntegrationReviewSchemaFieldType | None] = Field(default_factory=dict)
    collect_options: dict[str, bool | None] = Field(default_factory=dict)
    cache_media: dict[str, bool | None] = Field(default_factory=dict)
    required_fields: dict[str, bool | None] = Field(default_factory=dict)
    item_label_path: str | None = None
    page_slug_path: str | None = None
    output_primary_key_path: str | None = None


IntegrationVisibility = Literal["disabled", "template_only", "enabled"]
DEFAULT_DISABLED_INTEGRATION_SECTION_TYPES = {
    "text",
    "text_image",
    "video",
    "blog",
    "markdown",
    "html",
}


class IntegrationTemplateRule(BaseModel):
    """Template-level integration behavior controls."""

    integration_visibility: IntegrationVisibility | None = None
    integrations_enabled: bool | None = None
    expected_return_type: Literal["auto", "list", "object"] = "auto"


class IntegrationConnectionConfigResponse(BaseModel):
    """Response body for integration connection config."""

    exposed_integration_ids: list[str] = Field(default_factory=list)
    template_integration_rules: dict[str, IntegrationTemplateRule] = Field(default_factory=dict)


class IntegrationConnectionConfigUpdate(BaseModel):
    """Update payload for integration connection config."""

    exposed_integration_ids: list[str] | None = None
    template_integration_rules: dict[str, IntegrationTemplateRule] | None = None


class IntegrationsForSectionContextResponse(BaseModel):
    """Resolved template context used for integration filtering."""

    template_key: str
    integration_visibility: IntegrationVisibility = "enabled"
    integrations_enabled: bool = True
    expected_return_type: Literal["auto", "list", "object"] = "auto"


class IntegrationsForSectionResponse(BaseModel):
    """Integrations list + resolved context metadata."""

    integrations: list[IntegrationResponse] = Field(default_factory=list)
    context: IntegrationsForSectionContextResponse


class IntegrationDeepFetchJobResponse(BaseModel):
    """Response body for deep fetch background job state."""

    job_id: str
    integration_id: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    fetched_at: datetime | None = None
    item_count: int | None = None
    error: str | None = None

class SectionIntegrationCacheDiffEntry(BaseModel):
    """Single changed source path between previous/new cache payloads."""

    path: str
    old_value: Any | None = None
    new_value: Any | None = None


class SectionIntegrationCacheResponse(BaseModel):
    """Section integration cache payload with compare metadata."""

    cache_id: str
    section_id: str
    section_type: str
    integration_id: str
    integration_name: str
    mapping_storage_key: str
    fetched_at: datetime
    source_etag: str | None = None
    source_hash: str
    source_changed: bool = True
    changed_paths: list[str] = Field(default_factory=list)
    changed_entries: list[SectionIntegrationCacheDiffEntry] = Field(default_factory=list)
    changed_count: int = 0
    media_items_imported: int = 0
    media_items_reused: int = 0
    media_items_total: int = 0
    cached_data: Any = None


class SectionIntegrationMediaImportRequest(BaseModel):
    """Payload to localize/import media links for a section integration mapping context."""

    section_id: str = Field(min_length=1)
    section_type: str = Field(default="text")
    integration_id: str = Field(min_length=1)
    mapping_storage_key: str = Field(default="sectionIntegrationMapping")
    mapped_source_paths: list[str] | None = None
    enable_metadata_extraction_tagging: bool = True


class SectionIntegrationMediaImportabilityResponse(BaseModel):
    """Whether an integration currently has importable media URLs in transformed data."""

    integration_id: str
    has_media_urls: bool = False
    media_url_count: int = 0
    fetched_at: datetime | None = None


class SectionIntegrationMediaImportResponse(BaseModel):
    """Result payload for section media import/localization."""

    section_id: str
    section_type: str
    integration_id: str
    integration_name: str
    mapping_storage_key: str
    fetched_at: datetime | None = None
    source_etag: str | None = None
    has_media_urls: bool = False
    media_url_count: int = 0
    media_items_imported: int = 0
    media_items_reused: int = 0
    media_items_queued: int = 0
    media_items_localized_now: int = 0
    media_items_fallback_raw: int = 0
    media_items_total: int = 0
    media_entries: list[dict[str, Any]] = Field(default_factory=list)
    original_data: Any = None
    localized_data: Any = None
    options: dict[str, list[Any]] = Field(default_factory=dict)
    option_types: dict[str, Literal["single_choice", "multi_choice"]] = Field(default_factory=dict)


class IntegrationMediaCacheResponse(BaseModel):
    """Result payload for integration-level media caching."""

    integration_id: str
    fetched_at: datetime | None = None
    has_media_urls: bool = False
    media_url_count: int = 0
    media_items_imported: int = 0
    media_items_reused: int = 0
    media_items_queued: int = 0
    media_items_localized_now: int = 0
    media_items_fallback_raw: int = 0
    media_items_total: int = 0
    media_entries: list[dict[str, Any]] = Field(default_factory=list)
    data: Any = None
    options: dict[str, list[Any]] = Field(default_factory=dict)
    option_types: dict[str, Literal["single_choice", "multi_choice"]] = Field(default_factory=dict)


router = APIRouter(prefix="/integrations", tags=["integrations"])
INTEGRATIONS_CONNECTION_CONFIG_KEY = INTEGRATION_EXPOSURE_CONFIG_COLLECTION
DEEP_FETCH_RUNNING_STATUSES = {"queued", "running"}
_DEEP_FETCH_TASKS: set[asyncio.Task[Any]] = set()
_SECTION_MEDIA_IMPORT_TASKS: dict[str, asyncio.Task[Any]] = {}
SCHEMA_MEDIA_IMPORT_CONCURRENCY = 4
IntegrationOptionChoiceType = Literal["single_choice", "multi_choice"]
COMPOSABLE_INTEGRATION_TYPES = {"composable"}
REVIEW_ROOT_ITEM_KEY = "$root"
REVIEW_SCHEMA_FIELD_TYPES: set[str] = set(IntegrationReviewSchemaFieldType.__args__)
_REVIEW_MISSING = object()


class IntegrationDataPayload(NamedTuple):
    data: Any
    options: dict[str, list[Any]]
    option_types: dict[str, IntegrationOptionChoiceType]
    media_entries: list[dict[str, Any]]


def _normalize_integration_type(raw_type: Any) -> str:
    integration_type = str(raw_type or "api").strip().lower()
    if integration_type in {"api", "crawler", "composable"}:
        return integration_type
    return "api"


def _is_composable_integration_type(raw_type: Any) -> bool:
    return str(raw_type or "").strip().lower() in COMPOSABLE_INTEGRATION_TYPES


def _is_composable_integration_doc(integration_doc: dict[str, Any] | None) -> bool:
    return isinstance(integration_doc, dict) and _is_composable_integration_type(integration_doc.get("type"))


def _normalize_integration_option_types(
    raw_option_types: Any,
    options: Any | None = None,
) -> dict[str, IntegrationOptionChoiceType]:
    normalized: dict[str, IntegrationOptionChoiceType] = {}
    if isinstance(raw_option_types, dict):
        for key, value in raw_option_types.items():
            normalized_key = str(key or "").strip()
            normalized_value = str(value or "").strip().lower()
            if not normalized_key:
                continue
            if normalized_value in {"multi_choice", "multi", "list"}:
                normalized[normalized_key] = "multi_choice"
            elif normalized_value in {"single_choice", "single", "scalar"}:
                normalized[normalized_key] = "single_choice"
    if isinstance(options, dict):
        for key in options.keys():
            normalized_key = str(key or "").strip()
            if normalized_key and normalized_key not in normalized:
                normalized[normalized_key] = "single_choice"
    return normalized


def _normalize_integration_options(raw_options: Any) -> dict[str, list[Any]]:
    if not isinstance(raw_options, dict):
        return {}
    normalized: dict[str, list[Any]] = {}
    for key, value in raw_options.items():
        normalized_key = str(key or "").strip()
        if not normalized_key or not isinstance(value, list):
            continue
        normalized[normalized_key] = copy.deepcopy(value)
    return normalized


def _option_value_token(value: Any) -> str:
    return str(value)


def _add_option_values(target: dict[str, list[Any]], path: str, values: list[Any]) -> None:
    normalized_path = str(path or "").strip()
    if not normalized_path:
        return
    if normalized_path not in target:
        target[normalized_path] = []
    seen = {_option_value_token(value) for value in target[normalized_path]}
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        token = _option_value_token(value)
        if token in seen:
            continue
        seen.add(token)
        target[normalized_path].append(copy.deepcopy(value))


def _merge_option_type(
    current_type: IntegrationOptionChoiceType | None,
    incoming_type: IntegrationOptionChoiceType | None,
) -> IntegrationOptionChoiceType:
    if current_type == "multi_choice" or incoming_type == "multi_choice":
        return "multi_choice"
    return "single_choice"


def _is_removed_option_path(path: str, removed_path: str | None) -> bool:
    normalized_path = str(path or "").strip()
    normalized_removed_path = str(removed_path or "").strip()
    if not normalized_path or not normalized_removed_path:
        return False
    return normalized_path == normalized_removed_path or normalized_path.startswith(f"{normalized_removed_path}.")


def _merge_integration_option_metadata(
    target_options: dict[str, list[Any]],
    target_option_types: dict[str, IntegrationOptionChoiceType],
    source_options: Any,
    source_option_types: Any,
    *,
    path_prefix: str | None = None,
    removed_path: str | None = None,
) -> None:
    normalized_source_options = _normalize_integration_options(source_options)
    normalized_source_option_types = _normalize_integration_option_types(
        source_option_types,
        normalized_source_options,
    )
    normalized_prefix = str(path_prefix or "").strip()
    for source_path, source_values in normalized_source_options.items():
        if _is_removed_option_path(source_path, removed_path):
            continue
        target_path = f"{normalized_prefix}.{source_path}" if normalized_prefix else source_path
        _add_option_values(target_options, target_path, source_values)
        target_option_types[target_path] = _merge_option_type(
            target_option_types.get(target_path),
            normalized_source_option_types.get(source_path, "single_choice"),
        )


def _db():
    return get_client()[settings.mongo_db]


def _safe_object_id(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _integrations_coll():
    return _db()[INTEGRATION_CONFIG_COLLECTION]


def _data_coll():
    return _db()[INTEGRATION_DATA_COLLECTION]


def _overrides_coll():
    return _db()[INTEGRATION_ITEM_OVERRIDES_COLLECTION]


def _item_reviews_coll():
    return _db()[INTEGRATION_ITEM_REVIEWS_COLLECTION]


def _local_items_coll():
    return _db()[INTEGRATION_LOCAL_ITEMS_COLLECTION]


def _schemas_coll():
    return _db()[INTEGRATION_SCHEMAS_COLLECTION]


def _jobs_coll():
    return _db()[INTEGRATION_JOBS_COLLECTION]


def _settings_coll():
    return _db()[INTEGRATION_EXPOSURE_CONFIG_COLLECTION]


def _section_cache_coll():
    return _db()[INTEGRATION_SECTION_CACHE_VERSIONS_COLLECTION]


def _media_registry_coll():
    return _db()[INTEGRATION_MEDIA_REGISTRY_COLLECTION]


async def _resolve_asset_media_metadata(
    asset_id: str,
    cache: dict[str, dict[str, Any] | None],
) -> dict[str, Any] | None:
    normalized_asset_id = str(asset_id or "").strip()
    if not normalized_asset_id:
        return None
    if normalized_asset_id in cache:
        return cache.get(normalized_asset_id)
    try:
        asset_oid = ObjectId(normalized_asset_id)
    except Exception:
        cache[normalized_asset_id] = None
        return None

    assets_coll = _db()["assets"]
    asset_doc = await assets_coll.find_one(
        {"_id": asset_oid},
        {
            "_id": 1,
            "width": 1,
            "height": 1,
            "variants": 1,
        },
    )
    if not isinstance(asset_doc, dict):
        cache[normalized_asset_id] = None
        return None

    width_raw = asset_doc.get("width")
    height_raw = asset_doc.get("height")
    try:
        width = int(width_raw) if width_raw is not None else None
    except Exception:
        width = None
    try:
        height = int(height_raw) if height_raw is not None else None
    except Exception:
        height = None

    metadata: dict[str, Any] = {
        "responsive_variants": build_asset_responsive_variants(asset_doc.get("variants")),
    }
    if isinstance(width, int) and width > 0:
        metadata["width"] = width
    if isinstance(height, int) and height > 0:
        metadata["height"] = height

    cache[normalized_asset_id] = metadata
    return metadata


def _coerce_datetime(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, str):
        raw = value.strip()
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except Exception:
            return fallback
    return fallback


def _normalize_section_type_value(raw_section_type: Any, *, default: str = "text") -> str:
    section_type = str(raw_section_type or "").strip().lower().replace("-", "_")
    section_type = re.sub(r"[^a-z0-9_]+", "_", section_type).strip("_")
    return section_type or default


def _normalize_template_name_value(raw_template_name: Any, *, default: str = "default") -> str:
    template_name = str(raw_template_name or "").strip().lower()
    template_name = re.sub(r"[^a-z0-9_-]+", "-", template_name).strip("-")
    return template_name or default


def _normalize_expected_return_type(raw_value: Any) -> Literal["auto", "list", "object"]:
    value = str(raw_value or "").strip().lower()
    if value in {"list", "object"}:
        return value
    return "auto"


def _compose_section_template_rule_key(section_type: Any, template_name: Any = "default") -> str:
    return (
        "section/"
        f"{_normalize_section_type_value(section_type)}/"
        f"{_normalize_template_name_value(template_name)}"
    )


def _compose_page_template_rule_key(template_path: Any) -> str:
    normalized_path = normalize_page_template_path_value(template_path)
    if not normalized_path:
        return ""
    return f"page/{normalized_path}"


def _normalize_template_rule_key(raw_key: Any) -> str:
    normalized = str(raw_key or "").strip().lower().replace("\\", "/")
    if not normalized:
        return ""

    if normalized.startswith("section:"):
        normalized = normalized.replace("section:", "section/", 1).replace(":", "/")
    if normalized.startswith("section/"):
        parts = [part for part in normalized.split("/") if part]
        if len(parts) < 3:
            return ""
        return _compose_section_template_rule_key(parts[1], parts[2])

    if normalized.startswith("page/"):
        return _compose_page_template_rule_key(normalized[len("page/") :])
    return ""


def _normalize_integration_id_list(raw_ids: Any) -> list[str]:
    """Normalize an integration id list into a unique ordered string list."""
    if not isinstance(raw_ids, list):
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for raw_id in raw_ids:
        integration_id = str(raw_id or "").strip()
        if not integration_id or integration_id in seen:
            continue
        seen.add(integration_id)
        normalized.append(integration_id)
    return normalized


def _normalize_integration_visibility(
    raw_value: Any,
    *,
    default: IntegrationVisibility | None = "enabled",
) -> IntegrationVisibility | None:
    value = str(raw_value or "").strip().lower().replace("-", "_")
    if value == "disabled":
        return "disabled"
    if value == "template_only":
        return "template_only"
    if value == "enabled":
        return "enabled"
    return default


def _default_template_integration_visibility(template_key: str) -> IntegrationVisibility:
    normalized_key = _normalize_template_rule_key(template_key)
    if not normalized_key:
        return "template_only"
    if normalized_key.startswith("section/program/"):
        return "template_only"
    if normalized_key.startswith("section/"):
        parts = [part for part in normalized_key.split("/") if part]
        section_type = _normalize_section_type_value(parts[1], default="") if len(parts) > 1 else ""
        if section_type in DEFAULT_DISABLED_INTEGRATION_SECTION_TYPES:
            return "disabled"
    return "template_only"


def _coerce_bool(raw_value: Any, *, default: bool = True) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    if raw_value is None:
        return default
    if isinstance(raw_value, str):
        value = raw_value.strip().lower()
        if value in {"false", "0", "no", "off", "disabled"}:
            return False
        if value in {"true", "1", "yes", "on", "enabled"}:
            return True
    return bool(raw_value)


def _resolve_raw_template_rule_visibility(
    raw_rule: dict[str, Any],
    template_key: str,
) -> IntegrationVisibility:
    explicit_visibility = _normalize_integration_visibility(
        raw_rule.get("integration_visibility"),
        default=None,
    )
    if explicit_visibility:
        return explicit_visibility
    if raw_rule.get("integrations_enabled") is not None:
        return (
            "enabled"
            if _coerce_bool(raw_rule.get("integrations_enabled"), default=True)
            else "disabled"
        )
    return _default_template_integration_visibility(template_key)


def _normalize_template_integration_rules(
    raw_rules: Any,
) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_rules, dict):
        return {}

    normalized: dict[str, dict[str, Any]] = {}
    for raw_key, raw_rule in raw_rules.items():
        template_key = _normalize_template_rule_key(raw_key)
        if not template_key:
            continue
        if not isinstance(raw_rule, dict):
            continue
        integration_visibility = _resolve_raw_template_rule_visibility(raw_rule, template_key)
        if template_key.startswith("section/program/") and integration_visibility == "disabled":
            integration_visibility = "template_only"
        normalized[template_key] = {
            "integration_visibility": integration_visibility,
            "integrations_enabled": integration_visibility != "disabled",
            "expected_return_type": _normalize_expected_return_type(
                raw_rule.get("expected_return_type"),
            ),
        }
    return normalized


def _resolve_template_rule(
    rules: dict[str, dict[str, Any]],
    template_key: str,
) -> dict[str, Any]:
    rule = rules.get(template_key)
    if not isinstance(rule, dict):
        integration_visibility = _default_template_integration_visibility(template_key)
        return {
            "integration_visibility": integration_visibility,
            "integrations_enabled": integration_visibility != "disabled",
            "expected_return_type": "auto",
        }
    integration_visibility = _normalize_integration_visibility(
        rule.get("integration_visibility"),
        default=_default_template_integration_visibility(template_key),
    )
    return {
        "integration_visibility": integration_visibility,
        "integrations_enabled": integration_visibility != "disabled",
        "expected_return_type": _normalize_expected_return_type(rule.get("expected_return_type")),
    }


def _compose_page_template_rule_key_from_doc(template_doc: dict | None) -> str:
    if not isinstance(template_doc, dict):
        return ""
    template_name = str(template_doc.get("template_name") or "").strip()
    if not template_name:
        return ""
    try:
        template_path = compose_page_template_path(template_name, template_doc.get("parent_route"))
    except Exception:
        return ""
    return _compose_page_template_rule_key(template_path)


async def _resolve_template_rule_key(
    section_type: str,
    section_id: str | None,
    item_page_template_path: str | None = None,
) -> str:
    explicit_item_page_key = _compose_page_template_rule_key(item_page_template_path)
    if explicit_item_page_key:
        return explicit_item_page_key

    fallback_key = _compose_section_template_rule_key(section_type, "default")
    raw_section_id = str(section_id or "").strip()
    if not raw_section_id:
        return fallback_key

    try:
        builder_kind, owner_id, embedded_id = parse_builder_section_id(raw_section_id)
    except Exception:
        builder_kind = ""
        owner_id = ""
        embedded_id = None

    if builder_kind == "section" and owner_id:
        try:
            template_oid = ObjectId(owner_id)
        except Exception:
            return fallback_key
        template_doc = await _db()["template_sections"].find_one({"_id": template_oid})
        if isinstance(template_doc, dict):
            return _compose_section_template_rule_key(
                template_doc.get("section_type") or section_type,
                template_doc.get("template_name") or "default",
            )
        return fallback_key

    if builder_kind == "page" and owner_id:
        try:
            template_oid = ObjectId(owner_id)
        except Exception:
            return fallback_key
        template_doc = await _db()["template_pages"].find_one({"_id": template_oid})
        page_key = _compose_page_template_rule_key_from_doc(template_doc)
        return page_key or fallback_key

    if builder_kind == "container" and owner_id and embedded_id:
        try:
            container_oid = ObjectId(owner_id)
        except Exception:
            return fallback_key
        container_doc = await _db()["template_containers"].find_one({"_id": container_oid})
        if isinstance(container_doc, dict):
            sections = container_doc.get("sections")
            if isinstance(sections, list):
                for embedded_section in sections:
                    if not isinstance(embedded_section, dict):
                        continue
                    if str(embedded_section.get("id") or "").strip() != embedded_id:
                        continue
                    return _compose_section_template_rule_key(
                        embedded_section.get("section_type") or section_type,
                        "default",
                    )

    try:
        oid = ObjectId(raw_section_id)
    except Exception:
        return fallback_key

    section_doc = await _db()["sections"].find_one({"_id": oid})
    if not isinstance(section_doc, dict):
        return fallback_key

    return _compose_section_template_rule_key(
        section_doc.get("section_type") or section_type,
        section_doc.get("section_template_name") or "default",
    )


def _is_template_integration_context(
    section_id: str | None,
    item_page_template_path: str | None = None,
) -> bool:
    if _compose_page_template_rule_key(item_page_template_path):
        return True

    raw_section_id = str(section_id or "").strip()
    if not raw_section_id:
        return False

    try:
        builder_kind, _owner_id, _embedded_id = parse_builder_section_id(raw_section_id)
    except Exception:
        return False
    return builder_kind in {"section", "page", "container"}


async def _resolve_source_route_ref_for_item_page_context(
    *,
    explicit_source_route_ref: str | None = None,
    item_page_template_path: str | None = None,
) -> str | None:
    normalized_explicit = str(explicit_source_route_ref or "").strip()
    if normalized_explicit:
        return normalized_explicit

    normalized_template_path = normalize_page_template_path_value(item_page_template_path)
    if not normalized_template_path:
        return None
    try:
        template_name, parent_route = parse_page_template_path(normalized_template_path)
    except Exception:
        return None

    template_doc = await _db()["template_pages"].find_one(
        {
            "template_name": template_name,
            "parent_route": parent_route,
        }
    )
    if not isinstance(template_doc, dict):
        return None

    source_route_ref = str(template_doc.get("source_route_ref") or "").strip()
    if source_route_ref:
        return source_route_ref

    # Fallback for templates that no longer persist source_route_ref:
    # resolve from shared routes using source type/kind + parent route.
    source_type = str(template_doc.get("source_type") or "").strip().lower()
    source_kind = str(template_doc.get("source_kind") or "").strip().lower()
    template_parent_route = str(template_doc.get("parent_route") or "").strip()
    if not source_type or not template_parent_route:
        return None

    routes = await capture_item_page_routes(_db())
    for route_entry in routes:
        if str(route_entry.get("source_type") or "").strip().lower() != source_type:
            continue
        if str(route_entry.get("parent_route") or "").strip() != template_parent_route:
            continue
        route_kind = str(route_entry.get("source_kind") or "").strip().lower()
        if source_kind and route_kind and route_kind != source_kind:
            continue
        resolved_ref = str(route_entry.get("source_route_ref") or "").strip()
        if resolved_ref:
            return resolved_ref
    return None


def _collect_integration_id_from_mapping_payload(raw_mapping: Any) -> str | None:
    normalized = normalize_section_integration_mapping(raw_mapping)
    selected_id = str(normalized.get("selected_integration_id") or "").strip()
    return selected_id or None


async def _resolve_source_used_integration_ids(source_route_ref: str | None) -> set[str]:
    normalized_ref = str(source_route_ref or "").strip()
    if not normalized_ref:
        return set()

    routes = await capture_item_page_routes(_db())
    route_entry = next(
        (
            entry
            for entry in routes
            if str(entry.get("source_route_ref") or "").strip() == normalized_ref
        ),
        None,
    )
    if not isinstance(route_entry, dict):
        return set()

    section_template_ref = str(route_entry.get("section_template_ref") or "").strip() or "blog/default"
    section_type_raw, _, template_name_raw = section_template_ref.partition("/")
    section_type = _normalize_section_type_value(section_type_raw, default="blog")
    template_name = _normalize_template_name_value(template_name_raw, default="default")

    template_doc = await _db()["template_sections"].find_one(
        {
            "section_type": section_type,
            "template_name": template_name,
        }
    )
    if not isinstance(template_doc, dict):
        return set()

    used_ids: set[str] = set()
    base_mapping_id = _collect_integration_id_from_mapping_payload(
        template_doc.get("section_integration_mapping"),
    )
    if base_mapping_id:
        used_ids.add(base_mapping_id)

    if section_type == "program":
        source_kind = str(route_entry.get("source_kind") or "").strip().lower()
        if source_kind in {"", "stage"}:
            shared_doc = await capture_program_shared_content(_db())
            mapping_id = _collect_integration_id_from_mapping_payload(
                shared_doc.get("program_stages_integration_mapping")
                if isinstance(shared_doc, dict)
                else None
            )
            if mapping_id:
                used_ids.add(mapping_id)
        if source_kind in {"", "gig"}:
            shared_doc = await capture_program_shared_content(_db())
            mapping_id = _collect_integration_id_from_mapping_payload(
                shared_doc.get("program_gigs_integration_mapping")
                if isinstance(shared_doc, dict)
                else None
            )
            if mapping_id:
                used_ids.add(mapping_id)

    return used_ids


async def _resolve_template_source_kind_for_item_page_context(
    item_page_template_path: str | None,
) -> str:
    normalized_template_path = normalize_page_template_path_value(item_page_template_path)
    if not normalized_template_path:
        return ""
    try:
        template_name, parent_route = parse_page_template_path(normalized_template_path)
    except Exception:
        return ""
    template_doc = await _db()["template_pages"].find_one(
        {
            "template_name": template_name,
            "parent_route": parent_route,
        },
        {"source_kind": 1},
    )
    if not isinstance(template_doc, dict):
        return ""
    return str(template_doc.get("source_kind") or "").strip().lower()


async def _resolve_source_used_integration_ids_from_section(
    source_section_id: str | None,
    *,
    source_kind: str | None = None,
) -> set[str]:
    section_oid = _safe_object_id(source_section_id)
    if section_oid is None:
        return set()
    section_doc = await _db()["sections"].find_one({"_id": section_oid})
    if not isinstance(section_doc, dict):
        return set()

    used_ids: set[str] = set()
    base_mapping_id = _collect_integration_id_from_mapping_payload(
        section_doc.get("section_integration_mapping"),
    )
    if base_mapping_id:
        used_ids.add(base_mapping_id)

    if str(section_doc.get("section_type") or "").strip().lower() == "program":
        normalized_kind = str(source_kind or "").strip().lower()
        if normalized_kind in {"", "stage"}:
            shared_doc = await capture_program_shared_content(_db())
            mapping_id = _collect_integration_id_from_mapping_payload(
                shared_doc.get("program_stages_integration_mapping")
                if isinstance(shared_doc, dict)
                else None
            )
            if mapping_id:
                used_ids.add(mapping_id)
        if normalized_kind in {"", "gig"}:
            shared_doc = await capture_program_shared_content(_db())
            mapping_id = _collect_integration_id_from_mapping_payload(
                shared_doc.get("program_gigs_integration_mapping")
                if isinstance(shared_doc, dict)
                else None
            )
            if mapping_id:
                used_ids.add(mapping_id)

    return used_ids


def _derive_return_type_from_data(data: Any) -> Literal["list", "object", "unknown"]:
    if isinstance(data, list):
        return "list"
    if isinstance(data, dict):
        return "object"
    return "unknown"


def _format_deep_fetch_job(doc: dict[str, Any]) -> IntegrationDeepFetchJobResponse:
    """Normalize integration deep-fetch job documents for API responses."""
    return IntegrationDeepFetchJobResponse(
        job_id=str(doc.get("_id")),
        integration_id=str(doc.get("integration_id") or ""),
        status=str(doc.get("status") or "queued"),
        created_at=doc.get("created_at") or datetime.utcnow(),
        started_at=doc.get("started_at"),
        finished_at=doc.get("finished_at"),
        fetched_at=doc.get("fetched_at"),
        item_count=doc.get("item_count"),
        error=str(doc.get("error") or "").strip() or None,
    )


def _stringify_error_detail(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, (dict, list)):
        try:
            return json.dumps(detail, ensure_ascii=False)
        except Exception:
            return str(detail)
    return str(detail)


def _track_deep_fetch_task(task: asyncio.Task[Any]) -> None:
    _DEEP_FETCH_TASKS.add(task)

    def _cleanup(done_task: asyncio.Task[Any]) -> None:
        _DEEP_FETCH_TASKS.discard(done_task)

    task.add_done_callback(_cleanup)


def _validate_removed_transform_ops(transform_steps: list[dict[str, Any]]) -> None:
    """Reject transform operations that are no longer supported."""
    removed_ops = {"insert_by_value", "flatten_list"}
    for index, step in enumerate(transform_steps):
        op = str(step.get("op") or "").strip()
        if op in removed_ops:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Transform step #{index + 1}: '{op}' is no longer supported. "
                    "Use keep_keys/remove_keys/ensure_keys/group_by/replace_nested_item/filter operations instead."
                ),
            )


def _normalize_stored_transform_steps(raw_steps: Any) -> list[dict[str, Any]]:
    """Normalize persisted transform config to the current schema."""
    if not isinstance(raw_steps, list):
        return []

    normalized_steps: list[dict[str, Any]] = []
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            continue

        step = copy.deepcopy(raw_step)
        op = str(step.get("op") or "").strip()
        if op == "rename_key":
            source_key = str(step.get("source_key") or "").strip()
            target_key = str(step.get("target_key") or "").strip()
            normalized_steps.append(
                {
                    "op": "rename_keys",
                    "enabled": step.get("enabled", True),
                    "mappings": [
                        {
                            "source_key": source_key,
                            "target_key": target_key,
                        }
                    ],
                }
            )
            continue

        if op == "rename_keys":
            raw_mappings = step.get("mappings")
            if not isinstance(raw_mappings, list):
                raw_mappings = step.get("rename_mappings")
            mappings: list[dict[str, str]] = []
            if isinstance(raw_mappings, list):
                for raw_mapping in raw_mappings:
                    if not isinstance(raw_mapping, dict):
                        continue
                    mappings.append(
                        {
                            "source_key": str(
                                raw_mapping.get("source_key") or raw_mapping.get("old_key") or ""
                            ).strip(),
                            "target_key": str(
                                raw_mapping.get("target_key") or raw_mapping.get("new_key") or ""
                            ).strip(),
                        }
                    )
            step["mappings"] = mappings
            step.pop("rename_mappings", None)

        normalized_steps.append(step)

    return normalized_steps


def _get_integration_transform_steps(integration_doc: dict[str, Any]) -> list[dict[str, Any]]:
    return _normalize_stored_transform_steps(integration_doc.get("transform_steps"))


def _is_collect_distinct_transform_step(step: Any) -> bool:
    return isinstance(step, dict) and str(step.get("op") or "").strip() == "collect_distinct_values"


def _collect_option_paths_from_transform_steps(transform_steps: list[dict[str, Any]] | None) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for step in transform_steps or []:
        if not _is_collect_distinct_transform_step(step) or step.get("enabled", True) is False:
            continue
        path = _normalize_review_field_path(step.get("key"))
        if not path or path in seen:
            continue
        seen.add(path)
        paths.append(path)
    return paths


def _strip_collect_distinct_transform_steps(transform_steps: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(step)
        for step in transform_steps or []
        if not _is_collect_distinct_transform_step(step)
    ]


def _parse_csv(content: str) -> list[dict]:
    """Parse CSV content into a list of dictionaries."""
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


def _xml_to_dict(element: ET.Element) -> dict | str:
    """Recursively convert XML element to dictionary."""
    if len(element) == 0:
        return element.text or ""

    result: dict[str, Any] = {}
    for child in element:
        child_data = _xml_to_dict(child)
        tag = child.tag

        if tag in result:
            if not isinstance(result[tag], list):
                result[tag] = [result[tag]]
            result[tag].append(child_data)
        else:
            result[tag] = child_data

    return result


def _parse_xml(content: str) -> list[dict]:
    """Parse XML content into a list of dictionaries."""
    root = ET.fromstring(content)

    items: list[dict] = []
    for child in root:
        child_data = _xml_to_dict(child)
        if isinstance(child_data, dict):
            items.append(child_data)

    if items:
        return items

    root_data = _xml_to_dict(root)
    if isinstance(root_data, dict):
        return [root_data]
    return []


def _format_integration(doc: dict, data_info: dict | None = None) -> dict:
    """Format integration document for response."""
    integration_type = _normalize_integration_type(doc.get("type"))
    container_config = doc.get("container_config")
    if isinstance(container_config, dict):
        normalized_container_config = dict(container_config)
        raw_sources = normalized_container_config.get("sources")
        if isinstance(raw_sources, list):
            normalized_sources: list[dict[str, Any]] = []
            for source_row in raw_sources:
                if not isinstance(source_row, dict):
                    continue
                normalized_source = dict(source_row)
                source_key_path = str(normalized_source.get("source_key_path") or "").strip() or None
                target_key_path = str(normalized_source.get("target_key_path") or "").strip() or None
                normalized_source["source_key_path"] = source_key_path
                normalized_source["target_key_path"] = target_key_path
                normalized_source["keep_target_key"] = bool(normalized_source.get("keep_target_key", False))
                normalized_sources.append(normalized_source)
            normalized_container_config["sources"] = normalized_sources
        container_config = normalized_container_config

    result = {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "url": doc.get("url", ""),
        "type": integration_type,
        "auth_type": doc.get("auth_type", "none"),
        "key_name": doc.get("key_name"),
        "response_type": doc.get("response_type", "json"),
        "response_path": doc.get("response_path"),
        "crawler_pagination_config": doc.get("crawler_pagination_config"),
        "allowed_sections": doc.get("allowed_sections", []),
        "description": doc.get("description"),
        "favorite": bool(doc.get("favorite", False)),
        "transform_steps": _strip_collect_distinct_transform_steps(_get_integration_transform_steps(doc)),
        "output_primary_key_path": str(doc.get("output_primary_key_path") or "").strip() or None,
        "item_page_sync_blocked": bool(doc.get("item_page_sync_blocked", False)),
        "container_config": container_config,
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
        "last_fetched": None,
        "data_count": None,
        "return_type": "unknown",
    }
    if data_info:
        result["last_fetched"] = data_info.get("fetched_at")
        data = data_info.get("data")
        result["return_type"] = _derive_return_type_from_data(data)
        if isinstance(data, list):
            result["data_count"] = len(data)
        elif data is not None:
            result["data_count"] = 1
    return result


def _cache_hash_payload(value: Any) -> str:
    try:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        serialized = json.dumps(str(value), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _cache_value_token(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        return json.dumps(str(value), ensure_ascii=False, separators=(",", ":"))


def _cache_order_insensitive_list_value(value: Any) -> Any:
    if isinstance(value, list):
        normalized_items = [
            _cache_order_insensitive_list_value(entry)
            for entry in value
            if not (isinstance(entry, str) and entry.strip() == "")
        ]
        return sorted(normalized_items, key=_cache_value_token)
    if isinstance(value, dict):
        return {
            str(key): _cache_order_insensitive_list_value(child)
            for key, child in sorted(value.items(), key=lambda entry: str(entry[0]))
        }
    return value


def _cache_review_value_token(value: Any) -> str:
    return _cache_value_token(_cache_order_insensitive_list_value(value))


def _remove_empty_string_list_items(value: Any) -> Any:
    if isinstance(value, list):
        return [
            _remove_empty_string_list_items(entry)
            for entry in value
            if not (isinstance(entry, str) and entry.strip() == "")
        ]
    if isinstance(value, dict):
        return {
            key: _remove_empty_string_list_items(child)
            for key, child in value.items()
        }
    return value


def _cache_path_from_tokens(tokens: list[Any]) -> str:
    if not tokens:
        return "$"
    parts: list[str] = []
    for token in tokens:
        if isinstance(token, int):
            if not parts:
                parts.append(f"[{token}]")
            else:
                parts[-1] = f"{parts[-1]}[{token}]"
            continue
        key = str(token or "").strip()
        if not key:
            continue
        parts.append(key)
    return ".".join(parts) if parts else "$"


def _cache_set_by_tokens(root: Any, tokens: list[Any], value: Any) -> None:
    if not tokens:
        return
    current = root
    for index, token in enumerate(tokens):
        is_last = index == len(tokens) - 1
        next_token = tokens[index + 1] if index + 1 < len(tokens) else None

        if isinstance(token, int):
            if not isinstance(current, list):
                return
            while len(current) <= token:
                current.append({} if not isinstance(next_token, int) else [])
            if is_last:
                current[token] = value
                return
            if not isinstance(current[token], (dict, list)):
                current[token] = {} if not isinstance(next_token, int) else []
            current = current[token]
            continue

        key = str(token or "").strip()
        if not key or not isinstance(current, dict):
            return
        if is_last:
            current[key] = value
            return
        if key not in current or not isinstance(current[key], (dict, list)):
            current[key] = {} if not isinstance(next_token, int) else []
        current = current[key]


def _cache_flatten_leaf_paths(
    value: Any,
    *,
    tokens: list[Any] | None = None,
    out: dict[str, Any] | None = None,
    depth: int = 0,
    max_depth: int = 9,
    max_entries: int = 5000,
    unordered_lists: bool = False,
) -> dict[str, Any]:
    current_tokens = list(tokens or [])
    output = out if isinstance(out, dict) else {}
    if len(output) >= max_entries:
        return output
    if depth > max_depth:
        output[_cache_path_from_tokens(current_tokens)] = value
        return output

    if isinstance(value, dict):
        if not value:
            output[_cache_path_from_tokens(current_tokens)] = {}
            return output
        for key, child in value.items():
            child_key = str(key or "").strip()
            if not child_key:
                continue
            _cache_flatten_leaf_paths(
                child,
                tokens=[*current_tokens, child_key],
                out=output,
                depth=depth + 1,
                max_depth=max_depth,
                max_entries=max_entries,
                unordered_lists=unordered_lists,
            )
            if len(output) >= max_entries:
                break
        return output

    if isinstance(value, list):
        if unordered_lists:
            output[_cache_path_from_tokens(current_tokens)] = value
            return output
        if not value:
            output[_cache_path_from_tokens(current_tokens)] = []
            return output
        for idx, child in enumerate(value):
            _cache_flatten_leaf_paths(
                child,
                tokens=[*current_tokens, idx],
                out=output,
                depth=depth + 1,
                max_depth=max_depth,
                max_entries=max_entries,
                unordered_lists=unordered_lists,
            )
            if len(output) >= max_entries:
                break
        return output

    output[_cache_path_from_tokens(current_tokens)] = value
    return output


def _compute_cache_payload_diff(
    previous_value: Any,
    next_value: Any,
    *,
    unordered_lists: bool = False,
) -> tuple[list[str], list[dict[str, Any]]]:
    previous_flat = _cache_flatten_leaf_paths(previous_value, unordered_lists=unordered_lists)
    next_flat = _cache_flatten_leaf_paths(next_value, unordered_lists=unordered_lists)
    all_paths = sorted(set(previous_flat.keys()) | set(next_flat.keys()))
    changed_paths: list[str] = []
    changed_entries: list[dict[str, Any]] = []
    for path in all_paths:
        token_for_value = _cache_review_value_token if unordered_lists else _cache_value_token
        old_token = token_for_value(previous_flat.get(path))
        new_token = token_for_value(next_flat.get(path))
        if old_token == new_token:
            continue
        changed_paths.append(path)
        if len(changed_entries) < 300:
            changed_entries.append(
                {
                    "path": path,
                    "old_value": previous_flat.get(path),
                    "new_value": next_flat.get(path),
                }
            )
    return changed_paths, changed_entries


def _normalize_review_field_path(raw_path: Any) -> str:
    path = str(raw_path or "").strip()
    if path.lower().startswith("in "):
        path = path[3:].strip()
    return path


def _normalize_review_item_key(raw_value: Any) -> str:
    if raw_value is None:
        return ""
    if isinstance(raw_value, str):
        return raw_value.strip()
    if isinstance(raw_value, (int, float, bool)):
        return str(raw_value).strip()
    return ""


def _review_item_key_for_row(row: Any, output_primary_key_path: str | None) -> str:
    normalized_path = str(output_primary_key_path or "").strip()
    if not normalized_path or not isinstance(row, dict):
        return ""
    return _normalize_review_item_key(_extract_value_from_path(row, normalized_path))


def _review_value_from_item(item: Any, field_path: str) -> tuple[bool, Any]:
    normalized_path = _normalize_review_field_path(field_path)
    if not normalized_path:
        return False, None
    if normalized_path == "$":
        return True, item
    value = _extract_value_from_path_with_missing(item, normalized_path, _REVIEW_MISSING)
    if value is _REVIEW_MISSING:
        return False, None
    return True, value


def _review_set_value_on_item(item: Any, field_path: str, value: Any) -> bool:
    normalized_path = _normalize_review_field_path(field_path)
    if not normalized_path or normalized_path == "$" or not isinstance(item, dict):
        return False
    _set_value_at_path(item, normalized_path, copy.deepcopy(value))
    return True


def _flatten_review_field_paths(
    value: Any,
    *,
    base_path: str = "",
    out: set[str] | None = None,
    depth: int = 0,
    max_depth: int = 8,
) -> set[str]:
    output = out if isinstance(out, set) else set()
    if depth > max_depth:
        if base_path:
            output.add(base_path)
        return output

    if isinstance(value, dict):
        if not value and base_path:
            output.add(base_path)
            return output
        for key, child in value.items():
            clean_key = str(key or "").strip()
            if not clean_key:
                continue
            next_path = f"{base_path}.{clean_key}" if base_path else clean_key
            _flatten_review_field_paths(
                child,
                base_path=next_path,
                out=output,
                depth=depth + 1,
                max_depth=max_depth,
            )
        return output

    if base_path:
        output.add(base_path)
    elif value is not None:
        output.add("$")
    return output


def _review_label_from_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("de", "en", "label", "name", "title", "value"):
            label = _review_label_from_value(value.get(key))
            if label:
                return label
        return ""
    if isinstance(value, list):
        labels = [_review_label_from_value(entry) for entry in value]
        return ", ".join(label for label in labels if label)
    if value is None:
        return ""
    label = str(value).strip()
    return label


def _review_item_label_for_row(
    item: Any,
    index: int,
    item_key: str,
    item_label_path: str | None,
) -> str:
    normalized_label_path = _normalize_review_field_path(item_label_path)
    if normalized_label_path and isinstance(item, dict):
        label = _review_label_from_value(_extract_value_from_path(item, normalized_label_path))
        if label:
            return label
    return _preview_option_label_from_value(item, index) or item_key


def _review_rows_for_data(
    data: Any,
    output_primary_key_path: str | None,
    item_label_path: str | None = None,
    *,
    local_item_keys: set[str] | None = None,
) -> tuple[list[dict[str, Any]], int, bool]:
    local_keys = local_item_keys if isinstance(local_item_keys, set) else set()
    if isinstance(data, list):
        normalized_primary_key = str(output_primary_key_path or "").strip()
        if not normalized_primary_key:
            return [], len(data), False

        rows: list[dict[str, Any]] = []
        missing_key_count = 0
        seen: set[str] = set()
        for index, item in enumerate(data):
            item_key = _review_item_key_for_row(item, normalized_primary_key)
            if not item_key or item_key in seen:
                missing_key_count += 1
                continue
            seen.add(item_key)
            rows.append(
                {
                    "item_key": item_key,
                    "index": index,
                    "item": item,
                    "label": _review_item_label_for_row(item, index, item_key, item_label_path),
                    "is_local_item": item_key in local_keys,
                }
            )
        return rows, missing_key_count, True

    if isinstance(data, dict):
        return [
            {
                "item_key": REVIEW_ROOT_ITEM_KEY,
                "index": 0,
                "item": data,
                "label": _review_item_label_for_row(data, 0, REVIEW_ROOT_ITEM_KEY, item_label_path),
                "is_local_item": False,
            }
        ], 0, True

    return [], 0, False


def _review_row_map_for_data(
    data: Any,
    output_primary_key_path: str | None,
    item_label_path: str | None = None,
    *,
    local_item_keys: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    rows, _missing_key_count, _can_review = _review_rows_for_data(
        data,
        output_primary_key_path,
        item_label_path,
        local_item_keys=local_item_keys,
    )
    return {row["item_key"]: row for row in rows}


def _compute_review_data_change_metadata(
    previous_data: Any,
    next_data: Any,
    output_primary_key_path: str | None,
) -> dict[str, Any]:
    if previous_data is None:
        return {
            "changed_paths": [],
            "changed_entries": [],
            "changed_item_keys": [],
            "changed_count": 0,
        }

    changed_paths: list[str] = []
    changed_entries: list[dict[str, Any]] = []
    changed_item_keys: set[str] = set()

    if isinstance(previous_data, list) and isinstance(next_data, list) and str(output_primary_key_path or "").strip():
        previous_by_key = _review_row_map_for_data(previous_data, output_primary_key_path)
        next_by_key = _review_row_map_for_data(next_data, output_primary_key_path)
        for item_key in sorted(set(previous_by_key.keys()) | set(next_by_key.keys())):
            previous_row = previous_by_key.get(item_key)
            next_row = next_by_key.get(item_key)
            if previous_row is None:
                changed_item_keys.add(item_key)
                path = f"{item_key}.$item"
                changed_paths.append(path)
                if len(changed_entries) < 300:
                    changed_entries.append(
                        {
                            "item_key": item_key,
                            "path": "$item",
                            "old_value": None,
                            "new_value": copy.deepcopy(next_row.get("item") if next_row else None),
                        }
                    )
                continue
            if next_row is None:
                changed_item_keys.add(item_key)
                path = f"{item_key}.$item"
                changed_paths.append(path)
                if len(changed_entries) < 300:
                    changed_entries.append(
                        {
                            "item_key": item_key,
                            "path": "$item",
                            "old_value": copy.deepcopy(previous_row.get("item")),
                            "new_value": None,
                        }
                    )
                continue

            row_changed_paths, row_changed_entries = _compute_cache_payload_diff(
                previous_row.get("item"),
                next_row.get("item"),
                unordered_lists=True,
            )
            if row_changed_paths:
                changed_item_keys.add(item_key)
            for row_path in row_changed_paths:
                changed_paths.append(f"{item_key}.{row_path}")
            for entry in row_changed_entries:
                if len(changed_entries) >= 300:
                    break
                changed_entries.append(
                    {
                        "item_key": item_key,
                        "path": entry.get("path"),
                        "old_value": entry.get("old_value"),
                        "new_value": entry.get("new_value"),
                    }
                )
        return {
            "changed_paths": changed_paths,
            "changed_entries": changed_entries,
            "changed_item_keys": sorted(changed_item_keys),
            "changed_count": len(changed_paths),
        }

    item_key = REVIEW_ROOT_ITEM_KEY if isinstance(next_data, dict) else ""
    payload_changed_paths, payload_changed_entries = _compute_cache_payload_diff(
        previous_data,
        next_data,
        unordered_lists=True,
    )
    if payload_changed_paths and item_key:
        changed_item_keys.add(item_key)
    return {
        "changed_paths": payload_changed_paths,
        "changed_entries": [
            {
                "item_key": item_key,
                "path": entry.get("path"),
                "old_value": entry.get("old_value"),
                "new_value": entry.get("new_value"),
            }
            for entry in payload_changed_entries
        ],
        "changed_item_keys": sorted(changed_item_keys),
        "changed_count": len(payload_changed_paths),
    }


def _is_review_override_conflicted(override_doc: dict[str, Any], current_item: Any) -> bool:
    field_path = _normalize_review_field_path(override_doc.get("field_path"))
    has_current, current_value = _review_value_from_item(current_item, field_path)
    base_missing = bool(override_doc.get("base_missing", False))
    if not has_current:
        return not base_missing
    if base_missing:
        return True
    return _cache_review_value_token(current_value) != _cache_review_value_token(override_doc.get("base_fetched_value"))


def _apply_review_overrides_to_data(
    data: Any,
    output_primary_key_path: str | None,
    overrides: list[dict[str, Any]],
) -> Any:
    effective_data = copy.deepcopy(data)
    if not overrides:
        return effective_data

    if isinstance(effective_data, list):
        index_by_key: dict[str, int] = {}
        normalized_primary_key = str(output_primary_key_path or "").strip()
        if not normalized_primary_key:
            return effective_data
        for index, row in enumerate(effective_data):
            item_key = _review_item_key_for_row(row, normalized_primary_key)
            if item_key and item_key not in index_by_key:
                index_by_key[item_key] = index
        for override in overrides:
            item_key = str(override.get("item_key") or "").strip()
            if item_key not in index_by_key:
                continue
            row = effective_data[index_by_key[item_key]]
            _review_set_value_on_item(row, str(override.get("field_path") or ""), override.get("local_value"))
        return effective_data

    if isinstance(effective_data, dict):
        for override in overrides:
            if str(override.get("item_key") or "").strip() != REVIEW_ROOT_ITEM_KEY:
                continue
            _review_set_value_on_item(
                effective_data,
                str(override.get("field_path") or ""),
                override.get("local_value"),
            )
    return effective_data


async def _load_integration_doc_or_404(integration_id: str) -> dict[str, Any]:
    try:
        integration_oid = ObjectId(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

    doc = await _integrations_coll().find_one({"_id": integration_oid})
    if not isinstance(doc, dict):
        raise HTTPException(status_code=404, detail="Integration not found")
    return doc


async def _load_integration_data_doc_or_404(integration_id: str) -> dict[str, Any]:
    data_doc = await _data_coll().find_one(
        {"integration_id": str(integration_id or "").strip()},
        sort=[("fetched_at", -1)],
    )
    if not isinstance(data_doc, dict):
        raise HTTPException(status_code=404, detail="No data fetched yet")
    return data_doc


async def _load_review_overrides(integration_id: str) -> list[dict[str, Any]]:
    overrides: list[dict[str, Any]] = []
    async for doc in _overrides_coll().find({"integration_id": str(integration_id or "").strip()}):
        if isinstance(doc, dict):
            overrides.append(doc)
    return overrides


def _normalize_review_item_state(raw_state: Any, *, default: IntegrationReviewItemState = "open") -> IntegrationReviewItemState:
    value = str(raw_state or "").strip().lower().replace(" ", "_").replace("-", "_")
    if value in REVIEW_ITEM_STATES:
        return value  # type: ignore[return-value]
    return default


def _normalize_review_tags(raw_tags: Any) -> list[str]:
    if not isinstance(raw_tags, list):
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in raw_tags:
        tag = str(raw_tag or "").strip()
        if not tag:
            continue
        token = tag.lower()
        if token in seen:
            continue
        seen.add(token)
        tags.append(tag)
    return tags[:50]


def _format_review_item_meta(doc: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "state": _normalize_review_item_state(doc.get("state") if isinstance(doc, dict) else None),
        "tags": _normalize_review_tags(doc.get("tags") if isinstance(doc, dict) else []),
        "updated_at": doc.get("updated_at") if isinstance(doc, dict) else None,
    }


def _hide_generated_local_review_tags(tags: list[str], *, is_local_item: bool) -> list[str]:
    if not is_local_item:
        return tags
    return [tag for tag in tags if str(tag or "").strip().lower() != "custom"]


def _is_review_required_value_missing(has_value: bool, value: Any) -> bool:
    if not has_value:
        return True
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, dict):
        return len(value) == 0
    return False


def _missing_required_schema_paths(item: Any, schema_fields: dict[str, dict[str, Any]]) -> list[str]:
    missing_paths: list[str] = []
    for path, field in sorted(schema_fields.items(), key=lambda entry: entry[0].lower()):
        if not bool(field.get("required", False)):
            continue
        has_value, value = _review_value_from_item(item, path)
        if _is_review_required_value_missing(has_value, value):
            missing_paths.append(path)
    return missing_paths


def _effective_review_item_for_overrides(
    item: Any,
    *,
    item_key: str,
    output_primary_key_path: str | None,
    overrides: list[dict[str, Any]],
) -> Any:
    effective_item = copy.deepcopy(item)
    if effective_item is None or not overrides:
        return effective_item
    if isinstance(effective_item, dict):
        payload = (
            [effective_item]
            if str(item_key or "").strip() != REVIEW_ROOT_ITEM_KEY
            else effective_item
        )
        effective_payload = _apply_review_overrides_to_data(
            payload,
            output_primary_key_path,
            overrides,
        )
        if isinstance(effective_payload, list):
            return effective_payload[0] if effective_payload else effective_item
        return effective_payload
    return effective_item


async def _load_review_item_meta_map(integration_id: str) -> dict[str, dict[str, Any]]:
    meta_by_key: dict[str, dict[str, Any]] = {}
    async for doc in _item_reviews_coll().find({"integration_id": str(integration_id or "").strip()}):
        if not isinstance(doc, dict):
            continue
        item_key = str(doc.get("item_key") or "").strip()
        if not item_key:
            continue
        meta_by_key[item_key] = doc
    return meta_by_key


async def _load_local_review_items(integration_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    async for doc in _local_items_coll().find({"integration_id": str(integration_id or "").strip()}).sort("created_at", 1):
        if isinstance(doc, dict):
            items.append(doc)
    return items


def _local_review_items_as_data(local_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for doc in local_docs:
        item = doc.get("item")
        if isinstance(item, dict):
            data.append(copy.deepcopy(item))
    return data


def _combine_fetched_and_local_review_data(data: Any, local_docs: list[dict[str, Any]]) -> Any:
    if not isinstance(data, list):
        return data
    local_items = _local_review_items_as_data(local_docs)
    if not local_items:
        return data
    return [*copy.deepcopy(data), *local_items]


async def _get_effective_integration_data_doc(
    integration_id: str,
    *,
    integration_doc: dict[str, Any] | None = None,
    data_doc: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Any, dict[str, list[Any]], dict[str, IntegrationOptionChoiceType]]:
    try:
        integration, current_data_doc, effective_data = await get_shared_effective_integration_data_doc(
            _db(),
            integration_id,
            integration_doc=integration_doc,
            data_doc=data_doc,
        )
    except IntegrationReviewError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    options = _normalize_integration_options(current_data_doc.get("options"))
    option_types = _normalize_integration_option_types(current_data_doc.get("option_types"), options)
    options, option_types = await _apply_schema_collected_options(
        integration_id,
        effective_data,
        options,
        option_types,
    )
    return integration, current_data_doc, effective_data, options, option_types


def _detect_schema_value_type(path: str, value: Any) -> IntegrationReviewSchemaFieldType:
    if value is _REVIEW_MISSING:
        return "undefined"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "json"
    if isinstance(value, str):
        raw = value.strip()
        if _looks_like_media_url(raw):
            return "image"
        if raw.startswith("http://") or raw.startswith("https://"):
            return "url"
        if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
            return "date"
        if re.match(r"^\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$", raw):
            return "datetime"
        return "text"
    return "undefined"


def _sample_schema_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        try:
            serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
            if len(serialized) > 240:
                return f"{serialized[:237]}..."
            return copy.deepcopy(value)
        except Exception:
            return str(value)
    return copy.deepcopy(value)


def _collect_schema_field_values(row: Any, base_path: str = "", out: dict[str, Any] | None = None) -> dict[str, Any]:
    values = out if isinstance(out, dict) else {}
    if isinstance(row, dict):
        if not row and base_path:
            values[base_path] = {}
            return values
        for key, child in row.items():
            clean_key = str(key or "").strip()
            if not clean_key:
                continue
            next_path = f"{base_path}.{clean_key}" if base_path else clean_key
            _collect_schema_field_values(child, next_path, values)
        return values
    if base_path:
        values[base_path] = row
    return values


def _detect_integration_schema_fields(data: Any) -> dict[str, dict[str, Any]]:
    if isinstance(data, list):
        rows = [row for row in data if isinstance(row, dict)]
    elif isinstance(data, dict):
        rows = [data]
    else:
        rows = []

    item_count = len(rows)
    observed_by_path: dict[str, list[Any]] = {}
    for row in rows:
        flattened = _collect_schema_field_values(row)
        for path, value in flattened.items():
            observed_by_path.setdefault(path, []).append(value)

    fields: dict[str, dict[str, Any]] = {}
    for path in sorted(observed_by_path.keys()):
        values = observed_by_path[path]
        present_values = [value for value in values if value is not None]
        type_counts: dict[str, int] = {}
        samples: list[Any] = []
        seen_samples: set[str] = set()
        for value in values:
            value_type = _detect_schema_value_type(path, value)
            type_counts[value_type] = type_counts.get(value_type, 0) + 1
            token = _cache_value_token(value)
            if token not in seen_samples and len(samples) < 5:
                seen_samples.add(token)
                samples.append(_sample_schema_value(value))

        non_null_types = {key for key in type_counts.keys() if key != "null"}
        inconsistent = len(non_null_types) > 1
        if inconsistent:
            detected_type: IntegrationReviewSchemaFieldType = "undefined"
        elif len(non_null_types) == 1:
            detected_type = next(iter(non_null_types))  # type: ignore[assignment]
        elif type_counts.get("null"):
            detected_type = "null"
        else:
            detected_type = "undefined"

        fields[path] = {
            "path": path,
            "detected_type": detected_type,
            "effective_type": detected_type,
            "manual_type": None,
            "occurrence_count": len(present_values),
            "missing_count": max(0, item_count - len(present_values)),
            "type_counts": type_counts,
            "inconsistent": inconsistent,
            "sample_values": samples,
        }
    return fields


def _normalize_manual_schema_types(raw_manual_types: Any) -> dict[str, IntegrationReviewSchemaFieldType]:
    normalized: dict[str, IntegrationReviewSchemaFieldType] = {}
    if not isinstance(raw_manual_types, dict):
        return normalized
    for raw_path, raw_type in raw_manual_types.items():
        path = _normalize_review_field_path(raw_path)
        value = str(raw_type or "").strip().lower()
        if not path or value not in REVIEW_SCHEMA_FIELD_TYPES:
            continue
        normalized[path] = value  # type: ignore[assignment]
    return normalized


def _normalize_schema_collect_options(raw_collect_options: Any) -> dict[str, bool]:
    normalized: dict[str, bool] = {}
    if not isinstance(raw_collect_options, dict):
        return normalized
    for raw_path, enabled in raw_collect_options.items():
        path = _normalize_review_field_path(raw_path)
        if not path:
            continue
        normalized[path] = bool(enabled)
    return normalized


def _normalize_schema_cache_media(raw_cache_media: Any) -> dict[str, bool]:
    normalized: dict[str, bool] = {}
    if not isinstance(raw_cache_media, dict):
        return normalized
    for raw_path, enabled in raw_cache_media.items():
        path = _normalize_review_field_path(raw_path)
        if not path:
            continue
        normalized[path] = bool(enabled)
    return normalized


def _normalize_schema_required_fields(raw_required_fields: Any) -> dict[str, bool]:
    normalized: dict[str, bool] = {}
    if not isinstance(raw_required_fields, dict):
        return normalized
    for raw_path, required in raw_required_fields.items():
        path = _normalize_review_field_path(raw_path)
        if not path:
            continue
        normalized[path] = bool(required)
    return normalized


def _choose_schema_item_label_path(
    fields: list[dict[str, Any]],
    output_primary_key_path: str | None = None,
) -> str | None:
    paths = [str(field.get("path") or "").strip() for field in fields if str(field.get("path") or "").strip()]
    if not paths:
        return None

    path_set = set(paths)
    preferred_exact = (
        "name",
        "title",
        "label",
        "display_name",
        "displayName",
        "gig_title",
        "gigTitle",
        "artist_name",
        "artistName",
        "slug",
    )
    for preferred in preferred_exact:
        if preferred in path_set:
            return preferred

    preferred_leafs = {"name", "title", "label", "display_name", "displayName"}
    for path in paths:
        if path.split(".")[-1] in preferred_leafs:
            return path

    primary_key_path = _normalize_review_field_path(output_primary_key_path)
    if primary_key_path and primary_key_path in path_set:
        return primary_key_path

    text_paths = [
        path
        for path in paths
        if str(next((field for field in fields if field.get("path") == path), {}).get("effective_type") or "").lower() == "text"
    ]
    if text_paths:
        return sorted(text_paths, key=lambda value: value.lower())[0]

    return sorted(paths, key=lambda value: value.lower())[0]


async def _seed_schema_collect_options(integration_id: str, paths: list[str]) -> None:
    normalized_paths = [
        path
        for path in dict.fromkeys(_normalize_review_field_path(path) for path in paths)
        if path
    ]
    if not normalized_paths:
        return

    existing = await _schemas_coll().find_one({"integration_id": integration_id})
    detected_fields = (
        existing.get("detected_fields")
        if isinstance(existing, dict) and isinstance(existing.get("detected_fields"), dict)
        else {}
    )
    manual_types = _normalize_manual_schema_types(existing.get("manual_types") if isinstance(existing, dict) else {})
    collect_options = _normalize_schema_collect_options(existing.get("collect_options") if isinstance(existing, dict) else {})
    cache_media = _normalize_schema_cache_media(existing.get("cache_media") if isinstance(existing, dict) else {})
    required_fields = _normalize_schema_required_fields(existing.get("required_fields") if isinstance(existing, dict) else {})
    item_label_path = _normalize_review_field_path(existing.get("item_label_path") if isinstance(existing, dict) else None) or None
    for path in normalized_paths:
        collect_options[path] = True

    now = datetime.utcnow()
    await _schemas_coll().update_one(
        {"integration_id": integration_id},
        {
            "$set": {
                "integration_id": integration_id,
                "detected_fields": detected_fields,
                "manual_types": manual_types,
                "collect_options": collect_options,
                "cache_media": cache_media,
                "required_fields": required_fields,
                "item_label_path": item_label_path,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now, "detected_at": now},
        },
        upsert=True,
    )


def _schema_configured_field_paths(schema_doc: dict[str, Any] | None) -> set[str]:
    if not isinstance(schema_doc, dict):
        return set()
    paths: set[str] = set()
    for key in ("detected_fields", "manual_types", "collect_options", "cache_media", "required_fields"):
        raw_map = schema_doc.get(key)
        if not isinstance(raw_map, dict):
            continue
        paths.update(
            path
            for path in (_normalize_review_field_path(raw_path) for raw_path in raw_map.keys())
            if path
        )
    return paths


def _is_legacy_page_slug_path(field_path: Any, schema_field_paths: set[str]) -> bool:
    normalized_path = _normalize_review_field_path(field_path)
    return normalized_path == "page_slug" and normalized_path not in schema_field_paths


def _parse_review_page_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
        if not isinstance(parsed, datetime):
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _normalize_review_generated_page_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw == "draft":
        return "hidden"
    if raw in {"init", "hidden", "published", "under_construction"}:
        return raw
    return "unknown"


def _compute_review_generated_page_effective_status(page_doc: dict[str, Any]) -> str:
    base_status = _normalize_review_generated_page_status(page_doc.get("status"))
    if base_status == "unknown":
        return "unknown"

    now = datetime.now(timezone.utc)
    publish_at = _parse_review_page_datetime(page_doc.get("publish_at"))
    unpublish_at = _parse_review_page_datetime(page_doc.get("unpublish_at"))

    if unpublish_at and unpublish_at <= now:
        return "hidden"
    if publish_at:
        if publish_at > now:
            return "hidden"
        if base_status in {"init", "hidden"}:
            return "published"
    if base_status == "init":
        return "hidden"
    return base_status


def _is_review_item_page_template_doc(template_doc: dict[str, Any]) -> bool:
    template_kind = str(template_doc.get("template_kind") or "").strip().lower()
    source_type = str(template_doc.get("source_type") or "").strip().lower()
    return template_kind == "item_page" or source_type in {"blog", "program", "tiles"}


def _review_item_page_template_source_context(template_doc: dict[str, Any]) -> tuple[str, str] | None:
    source_type = str(template_doc.get("source_type") or "").strip().lower()
    source_kind = str(template_doc.get("source_kind") or "").strip().lower()
    if source_type == "blog":
        return "blog", "item"
    if source_type == "program":
        return "program", "stage" if source_kind == "stage" else "gig"
    if source_type == "tiles":
        return "tiles", "item"
    return None


async def _load_active_review_item_page_template_ids_by_context() -> dict[tuple[str, str], set[str]]:
    active_by_context: dict[tuple[str, str], set[str]] = {}
    for source_type, source_kind in (
        ("blog", "item"),
        ("program", "stage"),
        ("program", "gig"),
    ):
        active_template = await resolve_active_item_page_template(
            _db(),
            source_type,
            source_kind,
        )
        template_doc = active_template.get("template") if isinstance(active_template, dict) else None
        template_id = str(template_doc.get("_id") or "").strip() if isinstance(template_doc, dict) else ""
        active_by_context[(source_type, source_kind)] = {template_id} if template_id else set()

    tile_template_ids: set[str] = set()
    tile_parent_routes: set[str] = set()
    async for section_doc in _db()["sections"].find(
        {"section_type": "tiles"},
        {
            "type_data.item_page_template_path": 1,
            "type_data.itemPageTemplatePath": 1,
            "type_data.parent_route": 1,
        },
    ):
        type_data = section_doc.get("type_data") if isinstance(section_doc.get("type_data"), dict) else {}
        template_path = normalize_page_template_path_value(
            type_data.get("item_page_template_path")
            if type_data.get("item_page_template_path") is not None
            else type_data.get("itemPageTemplatePath")
        )
        if template_path:
            try:
                template_name, parent_route = parse_page_template_path(template_path)
            except Exception:
                continue
            template_doc = await _db()["template_pages"].find_one(
                {
                    "template_name": template_name,
                    "parent_route": parent_route,
                },
                {"_id": 1},
            )
            template_id = str(template_doc.get("_id") or "").strip() if isinstance(template_doc, dict) else ""
            if template_id:
                tile_template_ids.add(template_id)
            continue
        parent_route = normalize_parent_route(type_data.get("parent_route"))
        if parent_route:
            tile_parent_routes.add(parent_route)

    if tile_parent_routes:
        async for template_doc in _db()["template_pages"].find(
            {
                "source_type": "tiles",
                "parent_route": {"$in": sorted(tile_parent_routes)},
            },
            {"_id": 1},
        ):
            template_id = str(template_doc.get("_id") or "").strip()
            if template_id:
                tile_template_ids.add(template_id)
    active_by_context[("tiles", "item")] = tile_template_ids
    return active_by_context


def _format_review_item_page_template_label(template_name: str, parent_route: str | None) -> str:
    if parent_route:
        return f"{parent_route.strip('/')}/{template_name}"
    return template_name


def _build_review_item_page_template_ref(template_doc: dict[str, Any]) -> dict[str, Any]:
    template_name = normalize_template_name(template_doc.get("template_name") or "default", default="default")
    parent_route = normalize_parent_route(template_doc.get("parent_route"))
    effective_parent_route = effective_item_page_parent_route_for_template(template_doc) or parent_route
    template_path = compose_page_template_path(template_name, parent_route)
    template_key = build_template_key_for_page(template_name, parent_route)
    match_parent_routes = {
        route
        for route in (parent_route, effective_parent_route)
        if route
    }
    if not match_parent_routes:
        match_parent_routes.add(None)
    return {
        "template_key": template_key,
        "template_name": template_name,
        "parent_route": effective_parent_route or parent_route,
        "template_path": template_path,
        "template_label": _format_review_item_page_template_label(
            template_name,
            effective_parent_route or parent_route,
        ),
        "_match_parent_routes": match_parent_routes,
    }


def _review_page_matches_template_ref(page_doc: dict[str, Any], template_ref: dict[str, Any]) -> bool:
    template_key = str(template_ref.get("template_key") or "").strip()
    if template_key and str(page_doc.get("template_key") or "").strip() == template_key:
        return True

    template_path = str(template_ref.get("template_path") or "").strip()
    page_template_path = normalize_page_template_path_value(page_doc.get("template_style_ref"))
    if template_path and page_template_path == template_path:
        return True

    raw_page_template_name = str(page_doc.get("template_template_name") or "").strip()
    if not raw_page_template_name:
        return False
    try:
        page_template_name = normalize_template_name(raw_page_template_name, default="default")
    except Exception:
        return False
    if page_template_name != str(template_ref.get("template_name") or "").strip():
        return False
    page_parent_route = normalize_parent_route(page_doc.get("template_parent_route"))
    match_parent_routes = template_ref.get("_match_parent_routes")
    if isinstance(match_parent_routes, set):
        return page_parent_route in match_parent_routes
    return page_parent_route == normalize_parent_route(template_ref.get("parent_route"))


def _review_page_has_template_identity(page_doc: dict[str, Any]) -> bool:
    return bool(
        str(page_doc.get("template_key") or "").strip()
        or normalize_page_template_path_value(page_doc.get("template_style_ref"))
        or str(page_doc.get("template_template_name") or "").strip()
    )


def _review_page_slug_matches_template_route(page_doc: dict[str, Any], template_ref: dict[str, Any]) -> bool:
    if _review_page_has_template_identity(page_doc):
        return False
    slug = str(page_doc.get("slug") or "").strip().strip("/")
    parent_route = normalize_parent_route(template_ref.get("parent_route"))
    if not slug or not parent_route:
        return False
    parent_slug = parent_route.strip("/")
    return slug == parent_slug or slug.startswith(f"{parent_slug}/")


def _review_generated_page_sort_token(page_doc: dict[str, Any]) -> datetime:
    parsed = _parse_review_page_datetime(page_doc.get("updated_at")) or _parse_review_page_datetime(page_doc.get("created_at"))
    return parsed or datetime.min.replace(tzinfo=timezone.utc)


def _format_review_generated_page_entry(
    template_ref: dict[str, Any],
    page_doc: dict[str, Any] | None,
) -> dict[str, Any]:
    base = {
        "template_key": template_ref.get("template_key"),
        "template_name": template_ref.get("template_name"),
        "parent_route": template_ref.get("parent_route"),
        "template_label": template_ref.get("template_label"),
        "item_page_sync_blocked": bool(template_ref.get("item_page_sync_blocked", False)),
    }
    if not isinstance(page_doc, dict):
        return {
            **base,
            "exists": False,
            "slug": None,
            "status": None,
            "effective_status": None,
            "is_visible": False,
            "syncs_with_review_overrides": False,
            "updated_at": None,
        }

    status = _normalize_review_generated_page_status(page_doc.get("status"))
    effective_status = _compute_review_generated_page_effective_status(page_doc)
    item_page_sync_blocked = bool(base.get("item_page_sync_blocked", False))
    return {
        **base,
        "exists": True,
        "slug": str(page_doc.get("slug") or "").strip() or None,
        "status": status,
        "effective_status": effective_status,
        "is_visible": effective_status in {"published", "under_construction"},
        "syncs_with_review_overrides": not item_page_sync_blocked,
        "updated_at": page_doc.get("updated_at"),
    }


def _summarize_review_generated_pages(generated_pages: list[dict[str, Any]]) -> dict[str, bool]:
    return {
        "has_generated_page": any(bool(page.get("exists")) for page in generated_pages),
        "has_missing_generated_page": any(not bool(page.get("exists")) for page in generated_pages),
        "has_non_syncing_generated_page": any(
            bool(page.get("exists")) and not bool(page.get("syncs_with_review_overrides"))
            for page in generated_pages
        ),
    }


def _normalize_review_page_state_tag_filter(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not raw.startswith(REVIEW_PAGE_STATE_TAG_FILTER_PREFIX):
        return ""
    token = raw[len(REVIEW_PAGE_STATE_TAG_FILTER_PREFIX):]
    if token in {"no_page", "missing_page"}:
        token = "missing"
    if token == "missing":
        return REVIEW_PAGE_STATE_TAG_FILTER_MISSING
    if token in REVIEW_PAGE_STATE_TAG_FILTER_STATUSES:
        return f"{REVIEW_PAGE_STATE_TAG_FILTER_PREFIX}{token}"
    return ""


def _review_page_state_tag_filters_for_generated_pages(generated_pages: list[dict[str, Any]]) -> set[str]:
    filters: set[str] = set()
    for page in generated_pages:
        if not isinstance(page, dict):
            continue
        if not page.get("exists"):
            filters.add(REVIEW_PAGE_STATE_TAG_FILTER_MISSING)
            continue
        status = _normalize_review_generated_page_status(page.get("status"))
        filters.add(f"{REVIEW_PAGE_STATE_TAG_FILTER_PREFIX}{status}")
    return filters


def _format_review_page_state_tag_filter_options(counts: dict[str, int]) -> list[dict[str, Any]]:
    ordered_values = [
        REVIEW_PAGE_STATE_TAG_FILTER_MISSING,
        *(
            f"{REVIEW_PAGE_STATE_TAG_FILTER_PREFIX}{status}"
            for status in REVIEW_PAGE_STATE_TAG_FILTER_STATUSES
        ),
    ]
    return [
        {
            "value": value,
            "label": REVIEW_PAGE_STATE_TAG_FILTER_LABELS.get(value, value),
            "count": int(counts.get(value) or 0),
        }
        for value in ordered_values
        if int(counts.get(value) or 0) > 0
    ]


async def _load_review_item_page_template_refs(integration_id: str) -> list[dict[str, Any]]:
    normalized_integration_id = str(integration_id or "").strip()
    if not normalized_integration_id:
        return []
    docs = await _db()["template_pages"].find(
        {
            "page_integration_mapping.selected_integration_id": normalized_integration_id,
            "$or": [
                {"template_kind": "item_page"},
                {"source_type": {"$in": ["blog", "program", "tiles"]}},
            ],
        },
        {
            "_id": 1,
            "template_name": 1,
            "parent_route": 1,
            "item_page_subroute": 1,
            "template_kind": 1,
            "source_type": 1,
        },
    ).to_list(length=500)
    active_template_ids_by_context = await _load_active_review_item_page_template_ids_by_context()
    refs: list[dict[str, Any]] = []
    for doc in docs:
        if not isinstance(doc, dict) or not _is_review_item_page_template_doc(doc):
            continue
        source_context = _review_item_page_template_source_context(doc)
        if source_context is None:
            continue
        active_template_ids = active_template_ids_by_context.get(source_context, set())
        if str(doc.get("_id") or "").strip() not in active_template_ids:
            continue
        try:
            refs.append(_build_review_item_page_template_ref(doc))
        except Exception:
            continue
    refs.sort(
        key=lambda ref: (
            str(ref.get("template_label") or "").lower(),
            str(ref.get("template_key") or "").lower(),
        )
    )
    return refs


async def _load_review_generated_pages_by_item(
    integration_id: str,
    item_keys: list[str] | set[str] | tuple[str, ...],
    template_refs: list[dict[str, Any]],
    *,
    item_page_sync_blocked: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    normalized_integration_id = str(integration_id or "").strip()
    normalized_item_keys = sorted(
        {
            str(item_key or "").strip()
            for item_key in item_keys
            if str(item_key or "").strip()
        }
    )
    if not normalized_integration_id or not normalized_item_keys or not template_refs:
        return {item_key: [] for item_key in normalized_item_keys}

    page_docs = await _db()["pages"].find(
        {
            "template_managed": True,
            "template_integration_id": normalized_integration_id,
            "template_integration_item_key": {"$in": normalized_item_keys},
        },
        {
            "_id": 1,
            "slug": 1,
            "status": 1,
            "publish_at": 1,
            "unpublish_at": 1,
            "updated_at": 1,
            "created_at": 1,
            "template_key": 1,
            "template_style_ref": 1,
            "template_template_name": 1,
            "template_parent_route": 1,
            "template_integration_item_key": 1,
        },
    ).to_list(length=max(100, len(normalized_item_keys) * max(1, len(template_refs)) * 4))

    page_docs_by_item: dict[str, list[dict[str, Any]]] = {item_key: [] for item_key in normalized_item_keys}
    for page_doc in page_docs:
        if not isinstance(page_doc, dict):
            continue
        item_key = str(page_doc.get("template_integration_item_key") or "").strip()
        if item_key not in page_docs_by_item:
            continue
        page_docs_by_item[item_key].append(page_doc)
    for item_page_docs in page_docs_by_item.values():
        item_page_docs.sort(key=_review_generated_page_sort_token, reverse=True)

    entries_by_item: dict[str, list[dict[str, Any]]] = {}
    for item_key in normalized_item_keys:
        item_page_docs = page_docs_by_item.get(item_key, [])
        entries: list[dict[str, Any]] = []
        for template_ref in template_refs:
            template_ref_with_sync = {
                **template_ref,
                "item_page_sync_blocked": bool(item_page_sync_blocked),
            }
            matching_page = next(
                (
                    page_doc
                    for page_doc in item_page_docs
                    if _review_page_matches_template_ref(page_doc, template_ref_with_sync)
                ),
                None,
            )
            if matching_page is None:
                matching_page = next(
                    (
                        page_doc
                        for page_doc in item_page_docs
                        if _review_page_slug_matches_template_route(page_doc, template_ref_with_sync)
                    ),
                    None,
                )
            entries.append(_format_review_generated_page_entry(template_ref_with_sync, matching_page))
        entries_by_item[item_key] = entries
    return entries_by_item


async def _migrate_collect_distinct_steps_to_schema(
    integration_id: str,
    integration_doc: dict[str, Any],
    *,
    strip_from_doc: bool = False,
) -> None:
    transform_steps = _get_integration_transform_steps(integration_doc)
    collect_paths = _collect_option_paths_from_transform_steps(transform_steps)
    if collect_paths:
        await _seed_schema_collect_options(integration_id, collect_paths)

    if not strip_from_doc or not any(_is_collect_distinct_transform_step(step) for step in transform_steps):
        return

    stripped_steps = _strip_collect_distinct_transform_steps(transform_steps)
    await _integrations_coll().update_one(
        {"_id": integration_doc.get("_id")},
        {
            "$set": {
                "transform_steps": stripped_steps,
                "updated_at": datetime.utcnow(),
            }
        },
    )
    integration_doc["transform_steps"] = stripped_steps


def _format_schema_response(
    integration_id: str,
    schema_doc: dict[str, Any] | None,
    detected_fields: dict[str, dict[str, Any]] | None = None,
    output_primary_key_path: str | None = None,
) -> dict[str, Any]:
    detected = (
        copy.deepcopy(detected_fields)
        if isinstance(detected_fields, dict)
        else copy.deepcopy(schema_doc.get("detected_fields") if isinstance(schema_doc, dict) else {})
    )
    if not isinstance(detected, dict):
        detected = {}
    manual_types = _normalize_manual_schema_types(
        schema_doc.get("manual_types") if isinstance(schema_doc, dict) else {}
    )
    collect_options = _normalize_schema_collect_options(
        schema_doc.get("collect_options") if isinstance(schema_doc, dict) else {}
    )
    cache_media = _normalize_schema_cache_media(
        schema_doc.get("cache_media") if isinstance(schema_doc, dict) else {}
    )
    required_fields = _normalize_schema_required_fields(
        schema_doc.get("required_fields") if isinstance(schema_doc, dict) else {}
    )
    normalized_output_primary_key_path = _normalize_review_field_path(output_primary_key_path)
    page_slug_path = _normalize_review_field_path(
        schema_doc.get("page_slug_path") if isinstance(schema_doc, dict) else None
    )
    schema_field_paths = _schema_configured_field_paths(
        {
            "detected_fields": detected,
            "manual_types": manual_types,
            "collect_options": collect_options,
            "cache_media": cache_media,
            "required_fields": required_fields,
        }
    )
    if normalized_output_primary_key_path:
        schema_field_paths.add(normalized_output_primary_key_path)
    if page_slug_path and page_slug_path not in schema_field_paths:
        page_slug_path = ""
    all_paths = sorted(
        schema_field_paths
    )
    fields: list[dict[str, Any]] = []
    for path in all_paths:
        detected_entry = detected.get(path)
        if not isinstance(detected_entry, dict):
            detected_entry = {
                "path": path,
                "detected_type": "undefined",
                "effective_type": "undefined",
                "manual_type": None,
                "occurrence_count": 0,
                "missing_count": 0,
                "type_counts": {},
                "inconsistent": False,
                "sample_values": [],
            }
        manual_type = manual_types.get(path)
        detected_type = str(detected_entry.get("detected_type") or "undefined").strip().lower()
        if detected_type not in REVIEW_SCHEMA_FIELD_TYPES:
            detected_type = "undefined"
        fields.append(
            {
                **detected_entry,
                "path": path,
                "detected_type": detected_type,
                "manual_type": manual_type,
                "effective_type": manual_type or detected_type,
                "collect_options": bool(collect_options.get(path, False)),
                "cache_media": bool(cache_media.get(path, False)),
                "required": bool(required_fields.get(path, False)),
                "is_output_primary_key": bool(
                    normalized_output_primary_key_path and path == normalized_output_primary_key_path
                ),
                "is_page_slug": bool(page_slug_path and path == page_slug_path),
            }
        )
    item_label_path = _normalize_review_field_path(
        schema_doc.get("item_label_path") if isinstance(schema_doc, dict) else None
    )
    if item_label_path not in {str(field.get("path") or "").strip() for field in fields}:
        item_label_path = _choose_schema_item_label_path(fields, output_primary_key_path) or ""
    for field in fields:
        field["is_item_label"] = bool(item_label_path and str(field.get("path") or "").strip() == item_label_path)

    return {
        "integration_id": integration_id,
        "fields": fields,
        "manual_types": manual_types,
        "collect_options": collect_options,
        "cache_media": cache_media,
        "required_fields": {str(field.get("path")): bool(field.get("required")) for field in fields},
        "item_label_path": item_label_path or None,
        "page_slug_path": page_slug_path or None,
        "output_primary_key_path": normalized_output_primary_key_path or None,
        "detected_at": schema_doc.get("detected_at") if isinstance(schema_doc, dict) else None,
        "updated_at": schema_doc.get("updated_at") if isinstance(schema_doc, dict) else None,
    }


async def _persist_detected_schema_for_integration_data(
    integration_id: str,
    integration_doc: dict[str, Any],
    data: Any,
) -> dict[str, Any]:
    detected = _detect_integration_schema_fields(data)
    existing = await _schemas_coll().find_one({"integration_id": integration_id})
    manual_types = _normalize_manual_schema_types(existing.get("manual_types") if isinstance(existing, dict) else {})
    collect_options = _normalize_schema_collect_options(existing.get("collect_options") if isinstance(existing, dict) else {})
    cache_media = _normalize_schema_cache_media(existing.get("cache_media") if isinstance(existing, dict) else {})
    required_fields = _normalize_schema_required_fields(existing.get("required_fields") if isinstance(existing, dict) else {})
    schema_preview = _format_schema_response(
        integration_id,
        {
            "detected_fields": detected,
            "manual_types": manual_types,
            "collect_options": collect_options,
            "cache_media": cache_media,
            "required_fields": required_fields,
            "item_label_path": existing.get("item_label_path") if isinstance(existing, dict) else None,
            "page_slug_path": existing.get("page_slug_path") if isinstance(existing, dict) else None,
        },
        detected,
        output_primary_key_path=str(integration_doc.get("output_primary_key_path") or "").strip(),
    )
    item_label_path = schema_preview.get("item_label_path")
    now = datetime.utcnow()
    await _schemas_coll().update_one(
        {"integration_id": integration_id},
        {
            "$set": {
                "integration_id": integration_id,
                "detected_fields": detected,
                "manual_types": manual_types,
                "collect_options": collect_options,
                "cache_media": cache_media,
                "required_fields": required_fields,
                "item_label_path": item_label_path,
                "page_slug_path": schema_preview.get("page_slug_path"),
                "detected_at": now,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    schema_doc = await _schemas_coll().find_one({"integration_id": integration_id})
    return _format_schema_response(
        integration_id,
        schema_doc,
        detected,
        output_primary_key_path=str(integration_doc.get("output_primary_key_path") or "").strip(),
    )


def _enrich_schema_response_with_options(
    schema_response: dict[str, Any],
    options: dict[str, list[Any]] | None,
    option_types: dict[str, IntegrationOptionChoiceType] | None,
) -> dict[str, Any]:
    """Attach collected option values to schema fields that opted into collection."""
    response = copy.deepcopy(schema_response) if isinstance(schema_response, dict) else {}
    normalized_options = _normalize_integration_options(options)
    normalized_option_types = _normalize_integration_option_types(option_types, normalized_options)
    fields = response.get("fields")
    if isinstance(fields, list):
        for field in fields:
            if not isinstance(field, dict):
                continue
            path = str(field.get("path") or "").strip()
            collects_options = bool(field.get("collect_options", False))
            field["options"] = copy.deepcopy(normalized_options.get(path, [])) if collects_options else []
            field["option_type"] = normalized_option_types.get(path) if collects_options else None
    response["options"] = copy.deepcopy(normalized_options)
    response["option_types"] = copy.deepcopy(normalized_option_types)
    return response


async def _get_schema_response_for_integration(
    integration_id: str,
    *,
    integration_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    integration = integration_doc if isinstance(integration_doc, dict) else await _load_integration_doc_or_404(integration_id)
    schema_doc = await _schemas_coll().find_one({"integration_id": str(integration_id or "").strip()})
    return _format_schema_response(
        str(integration_id or "").strip(),
        schema_doc,
        output_primary_key_path=str(integration.get("output_primary_key_path") or "").strip(),
    )


async def _get_schema_field_map(integration_id: str) -> dict[str, dict[str, Any]]:
    response = await _get_schema_response_for_integration(str(integration_id or "").strip())
    return {
        str(field.get("path") or "").strip(): field
        for field in response.get("fields", [])
        if str(field.get("path") or "").strip()
    }


async def _get_schema_item_label_path(
    integration_id: str,
    *,
    integration_doc: dict[str, Any] | None = None,
) -> str | None:
    response = await _get_schema_response_for_integration(integration_id, integration_doc=integration_doc)
    return str(response.get("item_label_path") or "").strip() or None


def _looks_like_media_url(value: Any) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    if not (raw.startswith("http://") or raw.startswith("https://")):
        return False
    lowered = raw.lower().split("?", 1)[0].split("#", 1)[0]
    media_extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".bmp",
        ".avif",
        ".heic",
        ".mp4",
        ".webm",
        ".mov",
        ".m4v",
        ".ogg",
        ".pdf",
    )
    return lowered.endswith(media_extensions)


def _normalize_mapped_source_paths(raw_paths: Any) -> list[str]:
    if not isinstance(raw_paths, list):
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for raw_path in raw_paths:
        path = str(raw_path or "").strip()
        if not path or path in seen:
            continue
        seen.add(path)
        normalized.append(path)
    return normalized


def _tokenize_object_path(path: Any) -> list[Any]:
    raw = str(path or "").strip()
    if raw.lower().startswith("in "):
        raw = raw[3:].strip()
    if not raw:
        return []

    tokens: list[Any] = []
    for raw_part in raw.split("."):
        part = str(raw_part or "")
        if not part:
            continue
        while "[" in part:
            bracket_index = part.index("[")
            head = part[:bracket_index]
            if head:
                tokens.append(head)
            rest = part[bracket_index + 1 :]
            close_index = rest.find("]")
            if close_index < 0:
                part = rest
                break
            index_text = rest[:close_index].strip()
            if index_text:
                if index_text.lstrip("-").isdigit():
                    try:
                        tokens.append(int(index_text))
                    except Exception:
                        tokens.append(index_text)
                else:
                    tokens.append(index_text)
            part = rest[close_index + 1 :]
            if part.startswith("."):
                part = part[1:]
        if part:
            tokens.append(part)
    return tokens


def _strip_leading_index_tokens(tokens: list[Any]) -> list[Any]:
    if not tokens:
        return []
    idx = 0
    while idx < len(tokens) and isinstance(tokens[idx], int):
        idx += 1
    return tokens[idx:]


def _tokens_start_with(candidate: list[Any], prefix: list[Any]) -> bool:
    if not prefix or len(prefix) > len(candidate):
        return False
    for index, token in enumerate(prefix):
        if candidate[index] != token:
            return False
    return True


def _media_tokens_match_mapped_source_paths(
    media_tokens: list[Any],
    mapped_source_path_tokens: list[list[Any]],
) -> bool:
    if not mapped_source_path_tokens:
        return False

    row_relative_tokens = _strip_leading_index_tokens(list(media_tokens or []))
    row_relative_no_indices = [
        token for token in row_relative_tokens if not isinstance(token, int)
    ]

    for source_tokens in mapped_source_path_tokens:
        if not source_tokens:
            continue
        if _tokens_start_with(row_relative_tokens, source_tokens):
            return True

        # Allow index-agnostic matching for list paths (e.g. [0].image_url vs image_url).
        if any(isinstance(token, int) for token in source_tokens):
            continue
        source_no_indices = [
            token for token in source_tokens if not isinstance(token, int)
        ]
        if source_no_indices and _tokens_start_with(row_relative_no_indices, source_no_indices):
            return True

    return False


def _collect_media_url_entries(
    value: Any,
    *,
    tokens: list[Any] | None = None,
    out: list[dict[str, Any]] | None = None,
    mapped_source_path_tokens: list[list[Any]] | None = None,
    depth: int = 0,
    max_depth: int = 9,
) -> list[dict[str, Any]]:
    current_tokens = list(tokens or [])
    output = out if isinstance(out, list) else []
    if depth > max_depth:
        return output

    if isinstance(value, str):
        if _looks_like_media_url(value):
            if (
                mapped_source_path_tokens is not None
                and not _media_tokens_match_mapped_source_paths(
                    current_tokens,
                    mapped_source_path_tokens,
                )
            ):
                return output
            output.append(
                {
                    "path": _cache_path_from_tokens(current_tokens),
                    "tokens": current_tokens,
                    "url": value.strip(),
                }
            )
        return output

    if isinstance(value, list):
        for idx, child in enumerate(value):
            _collect_media_url_entries(
                child,
                tokens=[*current_tokens, idx],
                out=output,
                mapped_source_path_tokens=mapped_source_path_tokens,
                depth=depth + 1,
                max_depth=max_depth,
            )
        return output

    if isinstance(value, dict):
        for key, child in value.items():
            child_key = str(key or "").strip()
            if not child_key:
                continue
            _collect_media_url_entries(
                child,
                tokens=[*current_tokens, child_key],
                out=output,
                mapped_source_path_tokens=mapped_source_path_tokens,
                depth=depth + 1,
                max_depth=max_depth,
            )
    return output


async def _fetch_etag_for_url(url: str) -> str | None:
    target = str(url or "").strip()
    if not target:
        return None
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            response = await client.head(target)
            if response.status_code >= 400 or response.status_code == 405:
                response = await client.get(target, headers={"Range": "bytes=0-0"})
    except Exception:
        return None

    for key in ("etag", "x-amz-version-id", "last-modified"):
        value = str(response.headers.get(key) or "").strip()
        if value:
            return value
    return None


def _source_url_hash(source_url: str) -> str:
    normalized = str(source_url or "").strip()
    if not normalized:
        return ""
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _has_local_media_registry_url(entry: dict[str, Any] | None) -> bool:
    return bool(str((entry or {}).get("local_url") or "").strip())


async def _has_usable_media_registry_entry(entry: dict[str, Any] | None) -> bool:
    if not isinstance(entry, dict) or not _has_local_media_registry_url(entry):
        return False
    asset_id = str(entry.get("asset_id") or "").strip()
    if not asset_id:
        return True
    try:
        asset_oid = ObjectId(asset_id)
    except Exception:
        return False
    asset_doc = await _db()["assets"].find_one({"_id": asset_oid}, {"_id": 1})
    return isinstance(asset_doc, dict)


async def _find_media_asset_entry_by_source_url(original_url: str) -> dict[str, Any] | None:
    normalized_url = str(original_url or "").strip()
    source_hash = _source_url_hash(normalized_url)
    if not normalized_url or not source_hash:
        return None

    asset_doc = await _db()["assets"].find_one(
        {
            "$or": [
                {"source_url_hash": source_hash},
                {"resolved_source_url_hash": source_hash},
                {"source_url": normalized_url},
                {"resolved_source_url": normalized_url},
            ]
        },
        {
            "_id": 1,
            "url": 1,
        },
        sort=[("created_at", -1)],
    )
    if not isinstance(asset_doc, dict):
        return None
    local_url = str(asset_doc.get("url") or "").strip()
    asset_id = str(asset_doc.get("_id") or "").strip()
    if not local_url or not asset_id:
        return None

    return {
        "original_url": normalized_url,
        "etag": None,
        "local_url": local_url,
        "asset_id": asset_id,
    }


async def _find_media_registry_entry(original_url: str, etag: str | None = None) -> dict[str, Any] | None:
    normalized_url = str(original_url or "").strip()
    normalized_etag = str(etag or "").strip()
    if not normalized_url:
        return None

    coll = _media_registry_coll()
    if normalized_etag:
        # Strict URL+ETag reuse: if ETag is known, only a matching tuple may be reused.
        etag_doc = await coll.find_one(
            {"original_url": normalized_url, "etag": normalized_etag},
            sort=[("updated_at", -1)],
        )
        if await _has_usable_media_registry_entry(etag_doc):
            return etag_doc
        asset_entry = await _find_media_asset_entry_by_source_url(normalized_url)
        if isinstance(asset_entry, dict):
            await _upsert_media_registry_entry(
                original_url=normalized_url,
                etag=normalized_etag,
                local_url=str(asset_entry.get("local_url") or ""),
                asset_id=str(asset_entry.get("asset_id") or ""),
            )
            asset_entry["etag"] = normalized_etag
            return asset_entry
        if isinstance(etag_doc, dict) and not _has_local_media_registry_url(etag_doc):
            return etag_doc
        return None

    # Fallback for sources without ETag support.
    no_etag_doc = await coll.find_one(
        {"original_url": normalized_url, "etag": {"$in": [None, ""]}},
        sort=[("updated_at", -1)],
    )
    if await _has_usable_media_registry_entry(no_etag_doc):
        return no_etag_doc

    latest_doc = await coll.find_one(
        {"original_url": normalized_url},
        sort=[("updated_at", -1)],
    )
    if await _has_usable_media_registry_entry(latest_doc):
        return latest_doc

    asset_entry = await _find_media_asset_entry_by_source_url(normalized_url)
    if isinstance(asset_entry, dict):
        await _upsert_media_registry_entry(
            original_url=normalized_url,
            etag=None,
            local_url=str(asset_entry.get("local_url") or ""),
            asset_id=str(asset_entry.get("asset_id") or ""),
        )
        return asset_entry

    if isinstance(no_etag_doc, dict):
        if _has_local_media_registry_url(no_etag_doc):
            return None
        return no_etag_doc
    if isinstance(latest_doc, dict) and not _has_local_media_registry_url(latest_doc):
        return latest_doc
    return None


async def _import_media_url_now(
    *,
    original_url: str,
    enable_metadata_extraction_tagging: bool,
) -> dict[str, Any] | None:
    normalized_url = str(original_url or "").strip()
    if not normalized_url:
        return None

    etag: str | None = None
    local_url = ""
    asset_id = ""
    imported = False
    try:
        etag = await _fetch_etag_for_url(normalized_url)
        previous = await _find_media_registry_entry(normalized_url, etag)
        if isinstance(previous, dict):
            local_url = str(previous.get("local_url") or "").strip()
            asset_id = str(previous.get("asset_id") or "").strip()

        if not local_url:
            try:
                imported_asset = await import_asset_from_url_payload(
                    {
                        "url": normalized_url,
                        "source_context": "integration",
                        "enable_metadata_extraction_tagging": bool(enable_metadata_extraction_tagging),
                        "defer_required_metadata_validation": True,
                    }
                )
                local_url = str(getattr(imported_asset, "url", "") or "").strip()
                asset_id = str(getattr(imported_asset, "asset_id", "") or "").strip()
                imported = bool(local_url)
            except Exception:
                local_url = ""
                asset_id = ""

    finally:
        try:
            await _upsert_media_registry_entry(
                original_url=normalized_url,
                etag=etag,
                local_url=local_url,
                asset_id=asset_id,
            )
        except Exception:
            return None

    if not local_url:
        return None
    return {
        "original_url": normalized_url,
        "etag": etag,
        "local_url": local_url,
        "asset_id": asset_id,
        "_imported": imported,
    }


async def _import_media_url_in_background(
    *,
    original_url: str,
    section_type: str,
    enable_metadata_extraction_tagging: bool,
) -> None:
    await _import_media_url_now(
        original_url=original_url,
        enable_metadata_extraction_tagging=bool(enable_metadata_extraction_tagging),
    )


def _ensure_background_media_import_task(
    *,
    original_url: str,
    section_type: str,
    enable_metadata_extraction_tagging: bool,
) -> bool:
    normalized_url = str(original_url or "").strip()
    if not normalized_url:
        return False

    task_key = normalized_url
    existing_task = _SECTION_MEDIA_IMPORT_TASKS.get(task_key)
    if isinstance(existing_task, asyncio.Task) and not existing_task.done():
        return True

    task = asyncio.create_task(
        _import_media_url_in_background(
            original_url=normalized_url,
            section_type=section_type,
            enable_metadata_extraction_tagging=bool(enable_metadata_extraction_tagging),
        )
    )
    _SECTION_MEDIA_IMPORT_TASKS[task_key] = task

    def _cleanup(done_task: asyncio.Task[Any]) -> None:
        current_task = _SECTION_MEDIA_IMPORT_TASKS.get(task_key)
        if current_task is done_task:
            _SECTION_MEDIA_IMPORT_TASKS.pop(task_key, None)

    task.add_done_callback(_cleanup)
    return True


async def _upsert_media_registry_entry(
    *,
    original_url: str,
    etag: str | None,
    local_url: str | None,
    asset_id: str | None,
) -> None:
    normalized_url = str(original_url or "").strip()
    normalized_etag = str(etag or "").strip()
    normalized_local_url = str(local_url or "").strip()
    normalized_asset_id = str(asset_id or "").strip()
    if not normalized_url:
        return

    coll = _media_registry_coll()
    now = datetime.utcnow()
    query = {"original_url": normalized_url}
    if normalized_etag:
        query["etag"] = normalized_etag
    else:
        query["etag"] = {"$in": [None, ""]}

    await coll.update_one(
        query,
        {
            "$set": {
                "original_url": normalized_url,
                "etag": normalized_etag or None,
                "local_url": normalized_local_url,
                "asset_id": normalized_asset_id or None,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )


async def _localize_media_links_for_cached_payload(
    payload: Any,
    *,
    section_type: str,
    enable_metadata_extraction_tagging: bool,
    mapped_source_paths: list[str] | None = None,
    import_missing_now: bool = False,
) -> tuple[Any, list[dict[str, Any]], int, int, int, int, int]:
    localized_payload = copy.deepcopy(payload)
    mapped_source_path_tokens: list[list[Any]] | None = None
    if mapped_source_paths is not None:
        normalized_paths = _normalize_mapped_source_paths(mapped_source_paths)
        mapped_source_path_tokens = [
            tokens
            for tokens in (_tokenize_object_path(path) for path in normalized_paths)
            if tokens
        ]

    media_rows = _collect_media_url_entries(
        localized_payload,
        mapped_source_path_tokens=mapped_source_path_tokens,
    )
    if not media_rows:
        return localized_payload, [], 0, 0, 0, 0, 0

    media_entries: list[dict[str, Any]] = []
    request_queued_urls: set[str] = set()
    request_imported_urls: set[str] = set()
    registry_entry_by_url: dict[str, dict[str, Any] | None] = {}
    asset_metadata_by_asset_id: dict[str, dict[str, Any] | None] = {}
    imported_count = 0
    reused_count = 0
    queued_count = 0
    localized_now_count = 0
    fallback_raw_count = 0

    if import_missing_now:
        unique_urls = list(
            dict.fromkeys(
                str(row.get("url") or "").strip()
                for row in media_rows
                if str(row.get("url") or "").strip()
            )
        )
        request_imported_urls.update(unique_urls)
        semaphore = asyncio.Semaphore(SCHEMA_MEDIA_IMPORT_CONCURRENCY)

        async def import_unique_url(url: str) -> tuple[str, dict[str, Any] | None]:
            async with semaphore:
                return url, await _import_media_url_now(
                    original_url=url,
                    enable_metadata_extraction_tagging=bool(enable_metadata_extraction_tagging),
                )

        import_results = await asyncio.gather(
            *(import_unique_url(url) for url in unique_urls),
            return_exceptions=True,
        )
        for result in import_results:
            if isinstance(result, Exception):
                continue
            url, imported_entry = result
            registry_entry_by_url[url] = imported_entry
            if isinstance(imported_entry, dict) and bool(imported_entry.get("_imported")):
                imported_count += 1

    for row in media_rows:
        original_url = str(row.get("url") or "").strip()
        tokens = row.get("tokens") if isinstance(row.get("tokens"), list) else []
        if not original_url:
            continue

        if original_url not in registry_entry_by_url:
            registry_entry_by_url[original_url] = await _find_media_registry_entry(original_url)
        previous = registry_entry_by_url.get(original_url)
        etag = str(previous.get("etag") or "").strip() if isinstance(previous, dict) else ""

        asset_id = ""
        local_url = ""
        reused = False
        if isinstance(previous, dict):
            local_url = str(previous.get("local_url") or "").strip()
            asset_id = str(previous.get("asset_id") or "").strip()
            reused = bool(local_url)

        if not local_url:
            queued_for_background = False
            if import_missing_now:
                imported_entry = None
                if original_url not in request_imported_urls:
                    request_imported_urls.add(original_url)
                    imported_entry = await _import_media_url_now(
                        original_url=original_url,
                        enable_metadata_extraction_tagging=bool(enable_metadata_extraction_tagging),
                    )
                    registry_entry_by_url[original_url] = imported_entry
                    if isinstance(imported_entry, dict) and bool(imported_entry.get("_imported")):
                        imported_count += 1
                else:
                    imported_entry = registry_entry_by_url.get(original_url)

                if isinstance(imported_entry, dict):
                    local_url = str(imported_entry.get("local_url") or "").strip()
                    asset_id = str(imported_entry.get("asset_id") or "").strip()
                    etag = str(imported_entry.get("etag") or "").strip()
                    reused = bool(local_url) and not bool(imported_entry.get("_imported"))
                    if reused:
                        reused_count += 1
            elif original_url not in request_queued_urls:
                request_queued_urls.add(original_url)
                queued_for_background = _ensure_background_media_import_task(
                    original_url=original_url,
                    section_type=section_type,
                    enable_metadata_extraction_tagging=bool(enable_metadata_extraction_tagging),
                )
                if queued_for_background:
                    imported_count += 1
                    queued_count += 1
        else:
            queued_for_background = False
            reused_count += 1

        if local_url:
            _cache_set_by_tokens(localized_payload, tokens, local_url)
            localized_now_count += 1
        else:
            # Fallback keeps the original external URL in localized payload.
            _cache_set_by_tokens(localized_payload, tokens, original_url)
            fallback_raw_count += 1

        asset_media_metadata = None
        if asset_id:
            asset_media_metadata = await _resolve_asset_media_metadata(
                asset_id,
                asset_metadata_by_asset_id,
            )

        media_entries.append(
            {
                "path": str(row.get("path") or ""),
                "original_url": original_url,
                "local_url": local_url or None,
                "resolved_url": local_url or original_url,
                "asset_id": asset_id or None,
                "etag": etag or None,
                "reused": reused,
                "queued": queued_for_background,
                "width": (
                    int((asset_media_metadata or {}).get("width"))
                    if isinstance((asset_media_metadata or {}).get("width"), int)
                    else None
                ),
                "height": (
                    int((asset_media_metadata or {}).get("height"))
                    if isinstance((asset_media_metadata or {}).get("height"), int)
                    else None
                ),
                "responsive_variants": (
                    list((asset_media_metadata or {}).get("responsive_variants") or [])
                ),
            }
        )

    return (
        localized_payload,
        media_entries,
        imported_count,
        reused_count,
        queued_count,
        localized_now_count,
        fallback_raw_count,
    )


def _dedupe_media_entries(entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        token = "|".join(
            str(entry.get(key) or "").strip()
            for key in ("path", "original_url", "local_url", "resolved_url", "asset_id")
        )
        if not token.strip("|") or token in seen:
            continue
        seen.add(token)
        deduped.append(copy.deepcopy(entry))
    return deduped


async def _get_schema_cache_media_paths(
    integration_id: str,
    *,
    integration_doc: dict[str, Any] | None = None,
) -> list[str]:
    try:
        response = await _get_schema_response_for_integration(
            integration_id,
            integration_doc=integration_doc,
        )
    except HTTPException:
        return []
    paths: list[str] = []
    for field in response.get("fields", []):
        if not isinstance(field, dict):
            continue
        path = _normalize_review_field_path(field.get("path"))
        if not path:
            continue
        if str(field.get("effective_type") or "").strip().lower() != "image":
            continue
        if not bool(field.get("cache_media")):
            continue
        paths.append(path)
    return list(dict.fromkeys(paths))


async def _cache_schema_media_for_integration_data(
    integration_id: str,
    data: Any,
    *,
    integration_doc: dict[str, Any] | None = None,
    base_media_entries: list[dict[str, Any]] | None = None,
    enable_metadata_extraction_tagging: bool = True,
    import_missing_now: bool = False,
) -> tuple[Any, list[dict[str, Any]], dict[str, int]]:
    cache_paths = await _get_schema_cache_media_paths(
        integration_id,
        integration_doc=integration_doc,
    )
    base_entries = _dedupe_media_entries(base_media_entries)
    if not cache_paths:
        return copy.deepcopy(data), base_entries, {
            "media_url_count": 0,
            "media_items_imported": 0,
            "media_items_reused": 0,
            "media_items_queued": 0,
            "media_items_localized_now": 0,
            "media_items_fallback_raw": 0,
            "media_items_total": len(base_entries),
        }

    (
        localized_data,
        media_entries,
        media_items_imported,
        media_items_reused,
        media_items_queued,
        media_items_localized_now,
        media_items_fallback_raw,
    ) = await _localize_media_links_for_cached_payload(
        data,
        section_type="integration",
        enable_metadata_extraction_tagging=bool(enable_metadata_extraction_tagging),
        mapped_source_paths=cache_paths,
        import_missing_now=bool(import_missing_now),
    )
    merged_entries = _dedupe_media_entries([*base_entries, *media_entries])
    media_url_count = _media_url_count(data, mapped_source_paths=cache_paths)
    return localized_data, merged_entries, {
        "media_url_count": media_url_count,
        "media_items_imported": media_items_imported,
        "media_items_reused": media_items_reused,
        "media_items_queued": media_items_queued,
        "media_items_localized_now": media_items_localized_now,
        "media_items_fallback_raw": media_items_fallback_raw,
        "media_items_total": len(media_entries),
    }


def _format_media_cache_stats(media_stats: dict[str, Any] | None) -> dict[str, int]:
    stats = media_stats if isinstance(media_stats, dict) else {}

    def as_int(key: str) -> int:
        try:
            return int(stats.get(key) or 0)
        except Exception:
            return 0

    fallback = as_int("media_items_fallback_raw")
    return {
        "found": as_int("media_url_count"),
        "imported": as_int("media_items_imported"),
        "reused": as_int("media_items_reused"),
        "localized": as_int("media_items_localized_now"),
        "queued": as_int("media_items_queued"),
        "fallback": fallback,
        "skipped": fallback,
        "total": as_int("media_items_total"),
    }


async def _fetch_integration_source_etag(integration_doc: dict[str, Any]) -> str | None:
    if _is_composable_integration_doc(integration_doc):
        return None
    url = str(integration_doc.get("url") or "").strip()
    if not url:
        return None
    headers = _get_auth_headers(integration_doc)
    headers["Accept"] = "*/*"
    headers["User-Agent"] = "FstvlPress/1.0"
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            response = await client.head(url, headers=headers)
            if response.status_code >= 400 or response.status_code == 405:
                response = await client.get(url, headers={**headers, "Range": "bytes=0-0"})
    except Exception:
        return None
    for key in ("etag", "x-amz-version-id", "last-modified"):
        value = str(response.headers.get(key) or "").strip()
        if value:
            return value
    return None


def _format_section_cache_response(doc: dict[str, Any]) -> SectionIntegrationCacheResponse:
    changed_entries_raw = doc.get("changed_entries")
    changed_entries = [
        SectionIntegrationCacheDiffEntry(
            path=str(entry.get("path") or ""),
            old_value=entry.get("old_value"),
            new_value=entry.get("new_value"),
        )
        for entry in (changed_entries_raw if isinstance(changed_entries_raw, list) else [])
        if isinstance(entry, dict) and str(entry.get("path") or "").strip()
    ]
    changed_paths = [
        str(path or "").strip()
        for path in (doc.get("changed_paths") if isinstance(doc.get("changed_paths"), list) else [])
        if str(path or "").strip()
    ]
    return SectionIntegrationCacheResponse(
        cache_id=str(doc.get("_id") or ""),
        section_id=str(doc.get("section_id") or ""),
        section_type=_normalize_section_type_value(doc.get("section_type"), default="text"),
        integration_id=str(doc.get("integration_id") or ""),
        integration_name=str(doc.get("integration_name") or ""),
        mapping_storage_key=str(doc.get("mapping_storage_key") or "sectionIntegrationMapping"),
        fetched_at=doc.get("fetched_at") or doc.get("created_at") or datetime.utcnow(),
        source_etag=str(doc.get("source_etag") or "").strip() or None,
        source_hash=str(doc.get("source_hash") or ""),
        source_changed=bool(doc.get("source_changed", True)),
        changed_paths=changed_paths,
        changed_entries=changed_entries,
        changed_count=int(doc.get("changed_count") or len(changed_paths)),
        media_items_imported=int(doc.get("media_items_imported") or 0),
        media_items_reused=int(doc.get("media_items_reused") or 0),
        media_items_total=int(doc.get("media_items_total") or 0),
        cached_data=doc.get("cached_data"),
    )


async def _get_latest_transformed_integration_data(
    integration_id: str,
) -> tuple[Any, datetime | None, dict[str, list[Any]], dict[str, IntegrationOptionChoiceType]]:
    data_doc = await _data_coll().find_one(
        {"integration_id": str(integration_id or "").strip()},
        sort=[("fetched_at", -1)],
    )
    if not isinstance(data_doc, dict):
        return None, None, {}, {}
    options = _normalize_integration_options(data_doc.get("options"))
    option_types = _normalize_integration_option_types(data_doc.get("option_types"), options)
    return (
        copy.deepcopy(data_doc.get("data")),
        data_doc.get("fetched_at"),
        copy.deepcopy(options),
        copy.deepcopy(option_types),
    )


def _media_url_count(payload: Any, *, mapped_source_paths: list[str] | None = None) -> int:
    mapped_source_path_tokens: list[list[Any]] | None = None
    if mapped_source_paths is not None:
        normalized_paths = _normalize_mapped_source_paths(mapped_source_paths)
        mapped_source_path_tokens = [
            tokens
            for tokens in (_tokenize_object_path(path) for path in normalized_paths)
            if tokens
        ]

    rows = _collect_media_url_entries(
        payload,
        mapped_source_path_tokens=mapped_source_path_tokens,
    )
    unique_urls = {
        str(row.get("url") or "").strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("url") or "").strip()
    }
    return len(unique_urls)


def _extract_from_path(data: Any, path: str | None) -> Any:
    """Extract data from a dot-separated path, returning original data when path is missing."""
    if not path:
        return data

    current = data
    for key in path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return data
    return current


def _normalize_path(path: str | None) -> list[str]:
    raw = str(path or "").strip()
    if raw.lower().startswith("in "):
        raw = raw[3:].strip()
    return [segment for segment in raw.split(".") if segment]


def _extract_value_from_path(data: Any, path: str | None) -> Any:
    parts = _normalize_path(path)
    if not parts:
        return None

    current = data
    for key in parts:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def _extract_values_from_path(data: Any, path: str | None) -> list[Any]:
    parts = _normalize_path(path)
    if not parts:
        return []

    def visit(current: Any, index: int) -> list[Any]:
        if index >= len(parts):
            return [current]
        if isinstance(current, list):
            values: list[Any] = []
            for entry in current:
                values.extend(visit(entry, index))
            return values
        key = parts[index]
        if isinstance(current, dict) and key in current:
            return visit(current[key], index + 1)
        return []

    return visit(data, 0)


def _extract_value_from_path_with_missing(data: Any, path: str | None, missing: Any) -> Any:
    """Extract value from a dot path while preserving a custom missing sentinel."""
    parts = _normalize_path(path)
    if not parts:
        return missing

    current = data
    for key in parts:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return missing
    return current


def _remove_value_from_path(data: Any, path: str | None) -> None:
    """Remove a value at a dot path from a dict, pruning empty parent dicts."""
    parts = _normalize_path(path)
    if not parts or not isinstance(data, dict):
        return

    current: Any = data
    parents: list[tuple[dict[str, Any], str]] = []
    for key in parts[:-1]:
        if not isinstance(current, dict) or key not in current:
            return
        parents.append((current, key))
        current = current[key]

    leaf_key = parts[-1]
    if not isinstance(current, dict) or leaf_key not in current:
        return
    current.pop(leaf_key, None)

    # Remove empty intermediary dicts created by key removal.
    for parent, parent_key in reversed(parents):
        child = parent.get(parent_key)
        if isinstance(child, dict) and not child:
            parent.pop(parent_key, None)
        else:
            break


def _set_value_at_path(data: Any, path: str | None, value: Any) -> None:
    """Set a value at a dot path on a dict, creating intermediate objects as needed."""
    parts = _normalize_path(path)
    if not parts or not isinstance(data, dict):
        return

    current: Any = data
    for key in parts[:-1]:
        if not isinstance(current, dict):
            return
        next_value = current.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
            current[key] = next_value
        current = next_value

    if isinstance(current, dict):
        current[parts[-1]] = value


def _collect_distinct_values_for_path(data: Any, path: str) -> tuple[list[Any], IntegrationOptionChoiceType]:
    seen: set[str] = set()
    distinct: list[Any] = []
    option_type: IntegrationOptionChoiceType = "single_choice"

    def add_value(value: Any) -> None:
        nonlocal option_type
        if isinstance(value, list):
            option_type = "multi_choice"
            for entry in value:
                add_value(entry)
            return
        if value is None:
            return
        if isinstance(value, str) and value.strip() == "":
            return
        token = str(value)
        if token in seen:
            return
        seen.add(token)
        distinct.append(value)

    for extracted_value in _extract_values_from_path(data, path):
        add_value(extracted_value)

    return distinct, option_type


async def _apply_schema_collected_options(
    integration_id: str,
    data: Any,
    options: dict[str, list[Any]] | None,
    option_types: dict[str, IntegrationOptionChoiceType] | None,
) -> tuple[dict[str, list[Any]], dict[str, IntegrationOptionChoiceType]]:
    next_options = _normalize_integration_options(options)
    next_option_types = _normalize_integration_option_types(option_types, next_options)
    try:
        schema_doc = await _schemas_coll().find_one({"integration_id": str(integration_id or "").strip()})
        collect_options = _normalize_schema_collect_options(
            schema_doc.get("collect_options") if isinstance(schema_doc, dict) else {}
        )
        for path, enabled in collect_options.items():
            if enabled:
                continue
            next_options.pop(path, None)
            next_option_types.pop(path, None)
        for path in sorted(path for path, enabled in collect_options.items() if enabled):
            values, option_type = _collect_distinct_values_for_path(data, path)
            next_options[path] = values
            next_option_types[path] = option_type
    except Exception:
        # Schema option collection should never block fetch/import/preview flows.
        return next_options, next_option_types
    return next_options, next_option_types


async def _remove_integration_metadata_option_paths(integration_id: str, paths: list[str]) -> None:
    removed_paths = [
        _normalize_review_field_path(path)
        for path in paths
        if _normalize_review_field_path(path)
    ]
    if not removed_paths:
        return

    data_coll = _data_coll()
    data_doc = await data_coll.find_one({"integration_id": integration_id})
    if not isinstance(data_doc, dict):
        return

    options = _normalize_integration_options(data_doc.get("options"))
    option_types = _normalize_integration_option_types(data_doc.get("option_types"), options)
    for option_path in list(options.keys()):
        if any(_is_removed_option_path(option_path, removed_path) for removed_path in removed_paths):
            options.pop(option_path, None)
            option_types.pop(option_path, None)
    for option_path in list(option_types.keys()):
        if any(_is_removed_option_path(option_path, removed_path) for removed_path in removed_paths):
            option_types.pop(option_path, None)

    await data_coll.update_one(
        {"_id": data_doc.get("_id")},
        {
            "$set": {
                "options": copy.deepcopy(options),
                "option_types": copy.deepcopy(option_types),
                "updated_at": datetime.utcnow(),
            }
        },
    )


def _normalize_transform_keys(raw_keys: Any) -> list[str]:
    """Normalize transform key lists into de-duplicated trimmed strings."""
    if not isinstance(raw_keys, list):
        return []

    seen: set[str] = set()
    normalized: list[str] = []
    for raw_key in raw_keys:
        key = str(raw_key or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized


def _coerce_allowed_scalar(value: Any) -> Any:
    """Convert common scalar string literals to typed values for filter matching."""
    if not isinstance(value, str):
        return value

    raw = value.strip()
    if raw == "":
        return ""

    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None

    # Keep ambiguous leading-zero numbers as strings (e.g. "086").
    if (raw.isdigit() and (raw == "0" or not raw.startswith("0"))) or (
        raw.startswith("-")
        and raw[1:].isdigit()
        and (raw == "-0" or not raw.startswith("-0"))
    ):
        try:
            return int(raw)
        except ValueError:
            pass

    if any(ch in raw.lower() for ch in [".", "e"]):
        try:
            return float(raw)
        except ValueError:
            pass

    return raw


def _value_matches_allowed(value: Any, allowed_values: list[Any]) -> bool:
    for allowed in allowed_values:
        if value == allowed:
            return True

        # Lenient scalar fallback for mixed-type configs (e.g. int 86 vs string "86").
        if (
            isinstance(value, (str, int, float, bool))
            and isinstance(allowed, (str, int, float, bool))
            and str(value).strip().lower() == str(allowed).strip().lower()
        ):
            return True

    return False


def _is_empty_filter_value(value: Any) -> bool:
    """Whether a value should be treated as empty for disallowed filtering."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _group_key_token(value: Any) -> str:
    """Build a stable token for grouping values, including non-hashable values."""
    try:
        return f"{type(value).__name__}:{json.dumps(value, sort_keys=True, ensure_ascii=False)}"
    except TypeError:
        return f"{type(value).__name__}:{str(value)}"


_MISSING_VALUE = object()


def _parse_selector_path(path: str | None) -> list[dict[str, Any]]:
    """
    Parse selector paths supporting list selection segments like `[id=81]`.

    Example: `add_fields.[id=81].name`
    """
    raw = str(path or "").strip()
    if raw.lower().startswith("in "):
        raw = raw[3:].strip()
    if not raw:
        return []

    tokens = [
        token.strip()
        for token in raw.replace("[", ".[")
        .split(".")
        if token.strip()
    ]

    segments: list[dict[str, Any]] = []
    for token in tokens:
        if ("[" in token or "]" in token) and not (token.startswith("[") and token.endswith("]")):
            raise ValueError("selector segments must use balanced [key=value] syntax")

        if token.startswith("[") and token.endswith("]"):
            expression = token[1:-1].strip()
            if not expression or "=" not in expression:
                raise ValueError("selector segments must be formatted like [key=value]")

            raw_key_path, raw_expected = expression.split("=", 1)
            key_path = str(raw_key_path or "").strip()
            if not key_path:
                raise ValueError("selector key path cannot be empty")

            expected_raw = str(raw_expected or "").strip()
            if (
                (expected_raw.startswith('"') and expected_raw.endswith('"'))
                or (expected_raw.startswith("'") and expected_raw.endswith("'"))
            ) and len(expected_raw) >= 2:
                expected_raw = expected_raw[1:-1]

            segments.append(
                {
                    "type": "selector",
                    "key_path": key_path,
                    "expected": _coerce_allowed_scalar(expected_raw),
                }
            )
            continue

        segments.append({"type": "field", "name": token})

    return segments


def _extract_value_from_selector_path(data: Any, path: str | None, missing: Any = None) -> Any:
    """Resolve selector paths with `[key=value]` segments against nested dict/list data."""
    segments = _parse_selector_path(path)
    if not segments:
        return missing

    current: Any = data
    for segment in segments:
        if segment.get("type") == "field":
            field = str(segment.get("name") or "").strip()
            if not isinstance(current, dict) or field not in current:
                return missing
            current = current[field]
            continue

        if segment.get("type") != "selector":
            return missing
        if not isinstance(current, list):
            return missing

        selector_key_path = str(segment.get("key_path") or "").strip()
        expected_value = segment.get("expected")
        matched_item = missing
        for list_item in current:
            if not isinstance(list_item, dict):
                continue
            candidate_value = _extract_value_from_path_with_missing(
                list_item,
                selector_key_path,
                _MISSING_VALUE,
            )
            if candidate_value is _MISSING_VALUE:
                continue
            if _value_matches_allowed(candidate_value, [expected_value]):
                matched_item = list_item
                break

        if matched_item is missing:
            return missing
        current = matched_item

    return current


def _apply_transform_step(items: list[Any], step: dict, step_index: int) -> Any:
    op = str(step.get("op") or "").strip()

    if op == "keep_keys":
        allowed_keys = _normalize_transform_keys(step.get("keys"))
        transformed: list[Any] = []
        for item in items:
            if isinstance(item, dict):
                kept_item: dict[str, Any] = {}
                for key in allowed_keys:
                    # Allow explicit top-level keys containing dots as-is.
                    if key in item:
                        kept_item[key] = item[key]
                        continue

                    value = _extract_value_from_path_with_missing(item, key, _MISSING_VALUE)
                    if value is _MISSING_VALUE:
                        continue
                    _set_value_at_path(kept_item, key, value)
                transformed.append(kept_item)
            else:
                transformed.append(item)
        return transformed

    if op == "remove_keys":
        blocked_keys = _normalize_transform_keys(step.get("keys"))
        transformed: list[Any] = []
        for item in items:
            if isinstance(item, dict):
                updated_item = copy.deepcopy(item)
                for key in blocked_keys:
                    # Allow explicit top-level keys containing dots as-is.
                    if key in updated_item:
                        updated_item.pop(key, None)
                        continue
                    _remove_value_from_path(updated_item, key)
                transformed.append(updated_item)
            else:
                transformed.append(item)
        return transformed

    if op == "ensure_keys":
        required_keys = _normalize_transform_keys(step.get("keys"))
        transformed: list[Any] = []
        for item in items:
            if not isinstance(item, dict):
                transformed.append(item)
                continue

            updated_item = copy.deepcopy(item)
            for key in required_keys:
                # Allow explicit top-level keys containing dots as-is.
                if key in updated_item:
                    continue

                value = _extract_value_from_path_with_missing(updated_item, key, _MISSING_VALUE)
                if value is not _MISSING_VALUE:
                    continue

                path_segments = _normalize_path(key)
                if not path_segments:
                    continue

                container: Any = updated_item
                can_set = True
                for segment in path_segments[:-1]:
                    if not isinstance(container, dict):
                        can_set = False
                        break
                    next_value = container.get(segment)
                    if next_value is None:
                        next_value = {}
                        container[segment] = next_value
                    elif not isinstance(next_value, dict):
                        # Avoid clobbering non-object intermediary values.
                        can_set = False
                        break
                    container = next_value

                if can_set and isinstance(container, dict) and path_segments[-1] not in container:
                    container[path_segments[-1]] = None

            transformed.append(updated_item)
        return transformed

    if op == "group_by":
        key_path = str(step.get("key_path") or "").strip()
        if not key_path:
            raise HTTPException(
                status_code=400,
                detail=f"Transform step #{step_index + 1}: 'key_path' is required for group_by",
            )

        key_segments = _normalize_path(key_path)
        group_key_field = key_segments[-1] if key_segments else "group_key"
        items_key = str(step.get("items_key") or "").strip() or "grouped_documents"
        if items_key == group_key_field:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Transform step #{step_index + 1}: 'items_key' must be different "
                    "from the resolved group key field name"
                ),
            )
        grouped: list[dict[str, Any]] = []
        group_index_by_token: dict[str, int] = {}
        for item in items:
            if not isinstance(item, dict):
                continue

            key_value = _extract_value_from_path(item, key_path)
            token = _group_key_token(key_value)
            grouped_item = copy.deepcopy(item)
            _remove_value_from_path(grouped_item, key_path)
            existing_index = group_index_by_token.get(token)
            if existing_index is None:
                grouped.append(
                    {
                        group_key_field: key_value,
                        items_key: [grouped_item],
                    }
                )
                group_index_by_token[token] = len(grouped) - 1
            else:
                grouped[existing_index][items_key].append(grouped_item)

        return grouped

    if op == "filter_by_allowed_values":
        raw_allowed = step.get("allowed_values")
        if raw_allowed is None:
            raw_allowed = {}
        if not isinstance(raw_allowed, dict):
            raise HTTPException(
                status_code=400,
                detail=f"Transform step #{step_index + 1}: 'allowed_values' must be an object",
            )

        normalized: dict[str, list[Any]] = {}
        for raw_key, raw_values in raw_allowed.items():
            key_path = str(raw_key or "").strip()
            if not key_path:
                continue
            if isinstance(raw_values, list):
                normalized[key_path] = [_coerce_allowed_scalar(value) for value in raw_values]
            else:
                normalized[key_path] = [_coerce_allowed_scalar(raw_values)]

        if not normalized:
            return items

        filtered: list[Any] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            is_allowed = True
            for key_path, allowed_values in normalized.items():
                value = _extract_value_from_path(item, key_path)
                if not _value_matches_allowed(value, allowed_values):
                    is_allowed = False
                    break
            if is_allowed:
                filtered.append(item)

        return filtered

    if op == "filter_by_disallowed_values":
        raw_disallowed = step.get("disallowed_values")
        if raw_disallowed is None:
            raw_disallowed = {}
        if not isinstance(raw_disallowed, dict):
            raise HTTPException(
                status_code=400,
                detail=f"Transform step #{step_index + 1}: 'disallowed_values' must be an object",
            )

        normalized: dict[str, list[Any]] = {}
        for raw_key, raw_values in raw_disallowed.items():
            key_path = str(raw_key or "").strip()
            if not key_path:
                continue
            if isinstance(raw_values, list):
                normalized[key_path] = [_coerce_allowed_scalar(value) for value in raw_values]
            else:
                normalized[key_path] = [_coerce_allowed_scalar(raw_values)]

        if not normalized:
            return items

        filtered: list[Any] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            should_exclude = False
            for key_path, disallowed_values in normalized.items():
                value = _extract_value_from_path(item, key_path)
                if _is_empty_filter_value(value):
                    should_exclude = True
                    break
                if disallowed_values and _value_matches_allowed(value, disallowed_values):
                    should_exclude = True
                    break
            if not should_exclude:
                filtered.append(item)

        return filtered

    if op == "replace_nested_item":
        raw_mappings = step.get("mappings")
        if not isinstance(raw_mappings, list) or len(raw_mappings) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Transform step #{step_index + 1}: 'mappings' must contain at least one entry",
            )

        static_route = str(step.get("static_route") or "").strip()
        mappings: list[tuple[str | None, Any, Any | None, str | None, str | None]] = []
        for mapping_index, mapping in enumerate(raw_mappings):
            if not isinstance(mapping, dict):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Transform step #{step_index + 1}: mappings[{mapping_index + 1}] "
                        "must be an object"
                    ),
                )

            item_key_path = str(mapping.get("item_key_path") or "").strip() or None
            match_value = mapping.get("match_value")
            renamed_value = mapping.get("renamed_value")
            source_value_path = str(mapping.get("source_value_path") or "").strip() or None
            target_key = str(mapping.get("target_key") or "").strip() or None

            if match_value is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Transform step #{step_index + 1}: mappings[{mapping_index + 1}].match_value "
                        "is required"
                    ),
                )

            mappings.append(
                (
                    item_key_path,
                    _coerce_allowed_scalar(match_value),
                    _coerce_allowed_scalar(renamed_value),
                    source_value_path,
                    target_key,
                )
            )

        if not static_route:
            raise HTTPException(
                status_code=400,
                detail=f"Transform step #{step_index + 1}: 'static_route' is required",
            )

        transformed: list[Any] = []
        for item in items:
            if not isinstance(item, dict):
                transformed.append(item)
                continue

            updated_item = copy.deepcopy(item)
            target_container = _extract_value_from_path_with_missing(updated_item, static_route, _MISSING_VALUE)
            if target_container is _MISSING_VALUE:
                transformed.append(updated_item)
                continue

            for item_key_path, match_value, renamed_value, source_value_path, target_key in mappings:
                if isinstance(target_container, list):
                    match_index: int | None = None
                    match_item: Any = None
                    match_item_value: Any = _MISSING_VALUE
                    for candidate_index, candidate_item in enumerate(target_container):
                        candidate_value = candidate_item
                        if item_key_path:
                            candidate_value = _extract_value_from_path_with_missing(
                                candidate_item,
                                item_key_path,
                                _MISSING_VALUE,
                            )
                            if candidate_value is _MISSING_VALUE:
                                continue
                        if _value_matches_allowed(candidate_value, [match_value]):
                            match_index = candidate_index
                            match_item = candidate_item
                            match_item_value = candidate_value
                            break

                    if match_index is None:
                        continue

                    popped_item = target_container.pop(match_index)
                    if target_key:
                        mapped_value: Any = popped_item
                        if renamed_value is not None:
                            mapped_value = renamed_value
                        elif source_value_path:
                            resolved_mapped_value = _extract_value_from_path_with_missing(
                                popped_item,
                                source_value_path,
                                _MISSING_VALUE,
                            )
                            if resolved_mapped_value is _MISSING_VALUE:
                                continue
                            mapped_value = resolved_mapped_value
                        elif item_key_path:
                            mapped_value = match_item_value
                        _set_value_at_path(updated_item, target_key, mapped_value)
                    else:
                        # Without a target key, promote matched nested item fields into the root object.
                        if isinstance(match_item, dict):
                            updated_item.update(match_item)
                    continue

                if isinstance(target_container, dict):
                    candidate_value = target_container
                    if item_key_path:
                        candidate_value = _extract_value_from_path_with_missing(
                            target_container,
                            item_key_path,
                            _MISSING_VALUE,
                        )
                        if candidate_value is _MISSING_VALUE:
                            continue
                    if not _value_matches_allowed(candidate_value, [match_value]):
                        continue

                    if target_key:
                        mapped_value = target_container
                        if renamed_value is not None:
                            mapped_value = renamed_value
                        elif source_value_path:
                            resolved_mapped_value = _extract_value_from_path_with_missing(
                                target_container,
                                source_value_path,
                                _MISSING_VALUE,
                            )
                            if resolved_mapped_value is _MISSING_VALUE:
                                continue
                            mapped_value = resolved_mapped_value
                        elif item_key_path:
                            mapped_value = candidate_value
                        _set_value_at_path(updated_item, target_key, mapped_value)
                    else:
                        updated_item.update(target_container)

                    if item_key_path:
                        _remove_value_from_path(target_container, item_key_path)
                    else:
                        _remove_value_from_path(updated_item, static_route)
                    continue

                if item_key_path:
                    continue
                if not _value_matches_allowed(target_container, [match_value]):
                    continue
                if target_key:
                    mapped_value = renamed_value if renamed_value is not None else target_container
                    _set_value_at_path(updated_item, target_key, mapped_value)
                _remove_value_from_path(updated_item, static_route)
            transformed.append(updated_item)

        return transformed

    if op == "split_values_to_list":
        key = str(step.get("key") or "").strip()
        separator = str(step.get("separator") or "")
        if not key:
            raise HTTPException(
                status_code=400,
                detail=f"Transform step #{step_index + 1}: 'key' is required for split_values_to_list.",
            )
        if not separator:
            raise HTTPException(
                status_code=400,
                detail=f"Transform step #{step_index + 1}: 'separator' is required for split_values_to_list.",
            )
        transformed = []
        for item in items:
            if isinstance(item, dict):
                raw_value = _extract_value_from_path(item, key)
                if isinstance(raw_value, str):
                    parts = raw_value.split(separator)
                    updated_item = dict(item)
                    _set_value_at_path(updated_item, key, parts)
                    transformed.append(updated_item)
                else:
                    transformed.append(item)
            else:
                transformed.append(item)
        return transformed

    if op == "rename_keys":
        raw_mappings = step.get("mappings")
        if not isinstance(raw_mappings, list) or len(raw_mappings) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Transform step #{step_index + 1}: 'mappings' must contain at least one entry",
            )

        mappings: list[tuple[str, str]] = []
        for mapping_index, mapping in enumerate(raw_mappings):
            if not isinstance(mapping, dict):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Transform step #{step_index + 1}: mappings[{mapping_index + 1}] "
                        "must be an object"
                    ),
                )

            source_key = str(mapping.get("source_key") or mapping.get("old_key") or "").strip()
            target_key = str(mapping.get("target_key") or mapping.get("new_key") or "").strip()
            if not source_key:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Transform step #{step_index + 1}: mappings[{mapping_index + 1}].source_key "
                        "is required for rename_keys."
                    ),
                )
            if not target_key:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Transform step #{step_index + 1}: mappings[{mapping_index + 1}].target_key "
                        "is required for rename_keys."
                    ),
                )
            mappings.append((source_key, target_key))

        transformed = []
        for item in items:
            if isinstance(item, dict):
                updated_item = copy.deepcopy(item)
                for source_key, target_key in mappings:
                    value = _extract_value_from_path(updated_item, source_key)
                    _remove_value_from_path(updated_item, source_key)
                    _set_value_at_path(updated_item, target_key, value)
                transformed.append(updated_item)
            else:
                transformed.append(item)
        return transformed

    raise HTTPException(
        status_code=400,
        detail=f"Transform step #{step_index + 1}: unsupported op '{op}'",
    )


def _apply_transform_steps(
    data: Any,
    steps: list[dict] | None,
    *,
    initial_options: dict[str, list[Any]] | None = None,
    initial_option_types: dict[str, IntegrationOptionChoiceType] | None = None,
) -> tuple[Any, dict[str, list[Any]], dict[str, IntegrationOptionChoiceType]]:
    options = _normalize_integration_options(initial_options)
    option_types = _normalize_integration_option_types(initial_option_types, options)
    if not steps:
        return data, options, option_types

    transformed: Any = data
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise HTTPException(
                status_code=400,
                detail=f"Transform step #{index + 1} must be an object",
            )

        if not bool(step.get("enabled", True)):
            continue

        op = str(step.get("op") or "").strip()
        if op == "collect_distinct_values":
            key = str(step.get("key") or "").strip()
            if not key:
                raise HTTPException(
                    status_code=400,
                    detail=f"Transform step #{index + 1}: 'key' is required for collect_distinct_values.",
                )
            values, option_type = _collect_distinct_values_for_path(transformed, key)
            options[key] = values
            option_types[key] = option_type
            continue

        if not isinstance(transformed, list):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Transform step #{index + 1} ('{op or 'unknown'}') requires list input. "
                    "A previous step changed the result structure."
                ),
            )

        transformed = _apply_transform_step(transformed, step, index)

    return transformed, options, option_types


def _get_auth_headers(integration: dict) -> dict:
    """Get authentication headers for an integration."""
    auth_type = integration.get("auth_type", "none")
    key_name = integration.get("key_name")

    if auth_type == "none" or not key_name:
        return {}

    credential = os.environ.get(str(key_name), "").strip()
    if not credential:
        return {}

    if auth_type == "api_key":
        return {"X-API-Key": credential}
    if auth_type == "bearer":
        return {"Authorization": f"Bearer {credential}"}
    if auth_type == "token":
        return {"Authorization": f"Token {credential}"}
    if auth_type == "basic":
        encoded = base64.b64encode(credential.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    return {}


async def _run_health_check(integration: dict) -> IntegrationHealthResponse:
    if _is_composable_integration_doc(integration):
        return IntegrationHealthResponse(ok=True, status_code=200, response_time_ms=0)

    url = str(integration.get("url") or "").strip()
    if not url:
        return IntegrationHealthResponse(ok=False, error="URL is required for health checks")

    headers = _get_auth_headers(integration)
    headers["Accept"] = "application/json"
    headers["User-Agent"] = "FstvlPress/1.0"

    try:
        start = time.time()
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
        elapsed = int((time.time() - start) * 1000)

        return IntegrationHealthResponse(
            ok=response.status_code < 400,
            status_code=response.status_code,
            response_time_ms=elapsed,
        )
    except httpx.TimeoutException:
        return IntegrationHealthResponse(ok=False, error="Connection timeout")
    except Exception as exc:
        return IntegrationHealthResponse(ok=False, error=str(exc))


async def _validate_container_config(
    coll,
    container_config: dict | None,
    *,
    current_integration_id: str | None = None,
) -> None:
    if not isinstance(container_config, dict):
        raise HTTPException(status_code=400, detail="container_config is required for composable integrations")

    sources = container_config.get("sources")
    if not isinstance(sources, list) or len(sources) < 2:
        raise HTTPException(status_code=400, detail="container_config.sources must contain at least 2 integrations")

    seen_ids: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise HTTPException(status_code=400, detail=f"container_config.sources[{index}] must be an object")

        source_id = str(source.get("integration_id") or "").strip()
        if not source_id:
            raise HTTPException(status_code=400, detail=f"container_config.sources[{index}].integration_id is required")

        source_merge_style = str(source.get("merge_style") or "flat").strip().lower()
        if source_merge_style not in {"flat", "nested"}:
            raise HTTPException(
                status_code=400,
                detail=f"container_config.sources[{index}].merge_style must be 'flat' or 'nested'",
            )
        source_nested_key = str(source.get("nested_key") or "").strip() or None
        if source_merge_style == "nested" and not source_nested_key:
            raise HTTPException(
                status_code=400,
                detail=f"container_config.sources[{index}].nested_key is required when merge_style is 'nested'",
            )
        source_keep_target_key = bool(source.get("keep_target_key", False))
        source["merge_style"] = source_merge_style
        source["nested_key"] = source_nested_key
        source["keep_target_key"] = source_keep_target_key
        source_key_path = str(source.get("source_key_path") or "").strip() or None
        target_key_path = str(source.get("target_key_path") or "").strip() or None
        source["source_key_path"] = source_key_path
        source["target_key_path"] = target_key_path

        if source_id in seen_ids:
            raise HTTPException(status_code=400, detail=f"Duplicate source integration_id '{source_id}'")
        seen_ids.add(source_id)

        if current_integration_id and source_id == current_integration_id:
            raise HTTPException(status_code=400, detail="Composable integrations cannot reference themselves")

        try:
            source_oid = ObjectId(source_id)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source integration_id at index {index}: {source_id}",
            ) from exc

        source_doc = await coll.find_one({"_id": source_oid})
        if not source_doc:
            raise HTTPException(status_code=400, detail=f"Source integration not found: {source_id}")

        if (
            current_integration_id
            and _is_composable_integration_doc(source_doc)
            and await _container_reaches_target(coll, source_id, current_integration_id, set())
        ):
            raise HTTPException(
                status_code=400,
                detail="Composable graph cycle detected: source composable eventually references this composable",
            )

    target_source_id = str(container_config.get("target_source_integration_id") or "").strip()
    if target_source_id and target_source_id not in seen_ids:
        raise HTTPException(
            status_code=400,
            detail="container_config.target_source_integration_id must reference one of container_config.sources",
        )
    if target_source_id:
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                continue
            source_id = str(source.get("integration_id") or "").strip()
            if source_id == target_source_id:
                continue
            if not str(source.get("target_key_path") or "").strip():
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"container_config.sources[{index}].target_key_path is required when "
                        "target_source_integration_id is set"
                    ),
                )
            if not str(source.get("source_key_path") or "").strip():
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"container_config.sources[{index}].source_key_path is required when "
                        "target_source_integration_id is set"
                    ),
                )


def _container_source_rows(container_config: dict | None) -> list[dict]:
    if not isinstance(container_config, dict):
        return []
    sources = container_config.get("sources")
    if not isinstance(sources, list):
        return []
    return [entry for entry in sources if isinstance(entry, dict)]


def _container_source_id(source_row: dict) -> str:
    return str(source_row.get("integration_id") or "").strip()


async def _container_reaches_target(
    coll,
    start_container_id: str,
    target_container_id: str,
    visited: set[str],
) -> bool:
    if start_container_id == target_container_id:
        return True
    if start_container_id in visited:
        return False
    visited.add(start_container_id)

    try:
        start_oid = ObjectId(start_container_id)
    except Exception:
        return False

    start_doc = await coll.find_one({"_id": start_oid})
    if not _is_composable_integration_doc(start_doc):
        return False

    for source_row in _container_source_rows(start_doc.get("container_config")):
        source_id = _container_source_id(source_row)
        if not source_id:
            continue
        if source_id == target_container_id:
            return True
        if await _container_reaches_target(coll, source_id, target_container_id, visited):
            return True

    return False


def _build_url_with_query_param(url: str, param_name: str, value: Any) -> str:
    split_url = urlsplit(url)
    query_dict = dict(parse_qsl(split_url.query, keep_blank_values=True))
    query_dict[str(param_name)] = str(value)
    encoded_query = urlencode(query_dict, doseq=True)
    return urlunsplit((split_url.scheme, split_url.netloc, split_url.path, encoded_query, split_url.fragment))


def _parse_positive_int(raw_value: Any, label: str, *, allow_zero: bool = False) -> int:
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{label} must be an integer") from exc

    if allow_zero:
        if parsed < 0:
            raise HTTPException(status_code=400, detail=f"{label} must be >= 0")
    else:
        if parsed <= 0:
            raise HTTPException(status_code=400, detail=f"{label} must be > 0")
    return parsed


async def _fetch_and_parse_response(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    response_type: str,
    response_path: str | None,
) -> tuple[Any, Any]:
    response = await client.get(url, headers=headers)
    response.raise_for_status()

    if response_type == "json":
        raw_data = response.json()
        return raw_data, _extract_from_path(raw_data, response_path)
    if response_type == "csv":
        parsed = _parse_csv(response.text)
        return parsed, parsed
    if response_type == "xml":
        parsed = _parse_xml(response.text)
        return parsed, parsed

    raw_data = response.json()
    return raw_data, _extract_from_path(raw_data, response_path)


async def _fetch_remote_integration_data(integration_doc: dict) -> Any:
    headers = _get_auth_headers(integration_doc)
    response_type = str(integration_doc.get("response_type", "json") or "json").strip()
    response_path = integration_doc.get("response_path")
    pagination_config = integration_doc.get("crawler_pagination_config")
    base_url = str(integration_doc.get("url") or "").strip()

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            if not isinstance(pagination_config, dict):
                _, parsed_data = await _fetch_and_parse_response(client, base_url, headers, response_type, response_path)
                return parsed_data

            strategy = str(pagination_config.get("strategy") or "").strip()
            query_loop_key = str(pagination_config.get("query_loop_key") or "").strip()
            raw_query_loop_values = pagination_config.get("query_loop_values")
            query_loop_values: list[str] = []
            if isinstance(raw_query_loop_values, list):
                query_loop_values = [
                    str(entry).strip()
                    for entry in raw_query_loop_values
                    if str(entry).strip()
                ]
            elif raw_query_loop_values not in (None, ""):
                query_loop_values = [str(raw_query_loop_values).strip()]

            if query_loop_values and not query_loop_key:
                raise HTTPException(
                    status_code=400,
                    detail="crawler_pagination_config.query_loop_key is required when query_loop_values are provided",
                )
            if query_loop_key and not query_loop_values:
                raise HTTPException(
                    status_code=400,
                    detail="crawler_pagination_config.query_loop_values is required when query_loop_key is provided",
                )

            query_base_urls = [base_url]
            if query_loop_key and query_loop_values:
                query_base_urls = [
                    _build_url_with_query_param(base_url, query_loop_key, value)
                    for value in query_loop_values
                ]

            if strategy not in {"page_count", "next_page", "query_loop", ""}:
                raise HTTPException(
                    status_code=400,
                    detail="crawler_pagination_config.strategy must be 'page_count', 'next_page', or 'query_loop'",
                )

            if response_type != "json":
                raise HTTPException(
                    status_code=400,
                    detail="crawler pagination currently supports only JSON responses",
                )

            if strategy in {"query_loop", ""}:
                if len(query_base_urls) == 1:
                    _, parsed_data = await _fetch_and_parse_response(
                        client,
                        query_base_urls[0],
                        headers,
                        response_type,
                        response_path,
                    )
                    return parsed_data

                aggregated: list[Any] = []
                for query_url in query_base_urls:
                    _, query_data = await _fetch_and_parse_response(
                        client,
                        query_url,
                        headers,
                        response_type,
                        response_path,
                    )
                    if isinstance(query_data, list):
                        aggregated.extend(query_data)
                    elif query_data not in (None, ""):
                        aggregated.append(query_data)
                return aggregated

            if strategy == "page_count":
                page_query_param = str(pagination_config.get("page_query_param") or "").strip()
                page_count_field = str(pagination_config.get("page_count_field") or "").strip()
                max_page_visits = _parse_positive_int(
                    pagination_config.get("max_page_visits", 25),
                    "crawler_pagination_config.max_page_visits",
                )

                if not page_query_param:
                    raise HTTPException(
                        status_code=400,
                        detail="crawler_pagination_config.page_query_param is required for page_count strategy",
                    )
                if not page_count_field:
                    raise HTTPException(
                        status_code=400,
                        detail="crawler_pagination_config.page_count_field is required for page_count strategy",
                    )

                aggregated: list[Any] = []
                for query_base_url in query_base_urls:
                    first_page_url = _build_url_with_query_param(query_base_url, page_query_param, 1)
                    raw_first, first_items = await _fetch_and_parse_response(
                        client,
                        first_page_url,
                        headers,
                        response_type,
                        response_path,
                    )
                    if not isinstance(first_items, list):
                        raise HTTPException(
                            status_code=400,
                            detail="page_count pagination requires response_path to resolve to a list",
                        )
                    if not first_items:
                        continue

                    total_items_raw = _extract_value_from_path(raw_first, page_count_field)
                    total_items = _parse_positive_int(
                        total_items_raw,
                        "crawler_pagination_config.page_count_field result",
                        allow_zero=True,
                    )
                    if total_items == 0:
                        continue

                    page_size = len(first_items)
                    total_pages = (total_items + page_size - 1) // page_size
                    pages_to_visit = min(total_pages, max_page_visits)

                    aggregated.extend(first_items)
                    for page_number in range(2, pages_to_visit + 1):
                        page_url = _build_url_with_query_param(query_base_url, page_query_param, page_number)
                        _, page_items = await _fetch_and_parse_response(
                            client,
                            page_url,
                            headers,
                            response_type,
                            response_path,
                        )
                        if not isinstance(page_items, list):
                            raise HTTPException(
                                status_code=400,
                                detail=f"Pagination page {page_number} did not return a list",
                            )
                        aggregated.extend(page_items)
                        if not page_items:
                            break

                return aggregated

            next_page_field = str(pagination_config.get("next_page_field") or "").strip()
            max_page_visits = _parse_positive_int(
                pagination_config.get("max_page_visits", 25),
                "crawler_pagination_config.max_page_visits",
            )
            if not next_page_field:
                raise HTTPException(
                    status_code=400,
                    detail="crawler_pagination_config.next_page_field is required for next_page strategy",
                )

            aggregated: list[Any] = []
            for query_base_url in query_base_urls:
                current_url = query_base_url
                visited_pages = 0

                while current_url and visited_pages < max_page_visits:
                    raw_data, page_items = await _fetch_and_parse_response(
                        client,
                        current_url,
                        headers,
                        response_type,
                        response_path,
                    )
                    visited_pages += 1

                    if not isinstance(page_items, list):
                        raise HTTPException(
                            status_code=400,
                            detail="next_page pagination requires response_path to resolve to a list",
                        )
                    aggregated.extend(page_items)

                    next_page_value = _extract_value_from_path(raw_data, next_page_field)
                    if next_page_value in (None, ""):
                        break

                    next_url = str(next_page_value).strip()
                    if not next_url:
                        break
                    if next_url.startswith(("http://", "https://")):
                        current_url = next_url
                    else:
                        current_url = urljoin(query_base_url, next_url)

            return aggregated

    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Connection timeout") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream error: {exc.response.status_code}") from exc
    except ET.ParseError as exc:
        raise HTTPException(status_code=502, detail=f"XML parsing failed: {str(exc)}") from exc
    except csv.Error as exc:
        raise HTTPException(status_code=502, detail=f"CSV parsing failed: {str(exc)}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Fetch failed: {str(exc)}") from exc


async def _store_integration_data(
    data_coll,
    integration_id: str,
    data: Any,
    *,
    raw_data: Any | None = None,
    options: dict[str, list[Any]] | None = None,
    option_types: dict[str, IntegrationOptionChoiceType] | None = None,
    media_entries: list[dict[str, Any]] | None = None,
    output_primary_key_path: str | None = None,
) -> datetime:
    now = datetime.utcnow()
    data = _remove_empty_string_list_items(data)
    normalized_options = _normalize_integration_options(options)
    previous_doc = await data_coll.find_one(
        {"integration_id": integration_id},
        sort=[("fetched_at", -1)],
    )
    previous_data = copy.deepcopy(previous_doc.get("data")) if isinstance(previous_doc, dict) else None
    previous_raw_data = copy.deepcopy(previous_doc.get("raw_data")) if isinstance(previous_doc, dict) else None
    previous_fetched_at = previous_doc.get("fetched_at") if isinstance(previous_doc, dict) else None
    previous_hash = (
        str(previous_doc.get("data_hash") or "").strip()
        if isinstance(previous_doc, dict)
        else ""
    ) or (_cache_hash_payload(previous_data) if isinstance(previous_doc, dict) else "")
    data_hash = _cache_hash_payload(data)
    change_metadata = _compute_review_data_change_metadata(
        previous_data,
        data,
        output_primary_key_path,
    )

    await data_coll.delete_many({"integration_id": integration_id})
    await data_coll.insert_one(
        {
            "integration_id": integration_id,
            "data": data,
            "data_hash": data_hash,
            "options": normalized_options,
            "option_types": _normalize_integration_option_types(option_types, normalized_options),
            "media_entries": copy.deepcopy(media_entries or []),
            "raw_data": raw_data,
            "raw_data_hash": _cache_hash_payload(raw_data),
            "fetched_at": now,
            "previous_data": previous_data,
            "previous_raw_data": previous_raw_data,
            "previous_hash": previous_hash or None,
            "previous_fetched_at": previous_fetched_at,
            "source_changed": bool(previous_doc) and data_hash != previous_hash,
            "changed_paths": change_metadata.get("changed_paths", []),
            "changed_entries": change_metadata.get("changed_entries", []),
            "changed_item_keys": change_metadata.get("changed_item_keys", []),
            "changed_count": int(change_metadata.get("changed_count") or 0),
            "output_primary_key_path": str(output_primary_key_path or "").strip() or None,
        }
    )
    return now


async def _fetch_cached_integration_payload(data_coll, source_id: str, source_name: str) -> IntegrationDataPayload:
    source_data_doc = await data_coll.find_one(
        {"integration_id": source_id},
        sort=[("fetched_at", -1)],
    )
    if not source_data_doc:
        raise HTTPException(
            status_code=400,
            detail=f"Source integration '{source_name}' has no cached fetched data",
        )
    options = _normalize_integration_options(source_data_doc.get("options"))
    option_types = _normalize_integration_option_types(source_data_doc.get("option_types"), options)
    options, option_types = await _apply_schema_collected_options(
        source_id,
        source_data_doc.get("data"),
        options,
        option_types,
    )
    return IntegrationDataPayload(
        data=source_data_doc.get("data"),
        options=options,
        option_types=option_types,
        media_entries=copy.deepcopy(source_data_doc.get("media_entries") or []),
    )


async def _fetch_cached_integration_data(data_coll, source_id: str, source_name: str) -> Any:
    return (await _fetch_cached_integration_payload(data_coll, source_id, source_name)).data


async def _fetch_deep_data_for_integration(
    integration_id: str,
    integration_doc: dict,
    coll,
    data_coll,
    *,
    call_stack: set[str],
    deep_cache: dict[str, IntegrationDataPayload],
) -> IntegrationDataPayload:
    if integration_id in deep_cache:
        return deep_cache[integration_id]

    if integration_id in call_stack:
        raise HTTPException(
            status_code=400,
            detail=f"Composable cycle detected while deep fetching integration '{integration_id}'",
        )

    call_stack.add(integration_id)
    try:
        await _migrate_collect_distinct_steps_to_schema(integration_id, integration_doc, strip_from_doc=True)
        raw_payload: IntegrationDataPayload | None = None
        if _is_composable_integration_doc(integration_doc):
            raw_payload = await _fetch_container_payload(
                integration_id,
                integration_doc,
                coll,
                data_coll,
                deep=True,
                call_stack=call_stack,
                deep_cache=deep_cache,
            )
            raw_data = raw_payload.data
            initial_options = raw_payload.options
            initial_option_types = raw_payload.option_types
        else:
            raw_data = await _fetch_remote_integration_data(integration_doc)
            initial_options = {}
            initial_option_types = {}

        transformed_data, options, option_types = _apply_transform_steps(
            raw_data,
            _get_integration_transform_steps(integration_doc),
            initial_options=initial_options,
            initial_option_types=initial_option_types,
        )
        transformed_data = _remove_empty_string_list_items(transformed_data)
        await _persist_detected_schema_for_integration_data(
            integration_id,
            integration_doc,
            transformed_data,
        )
        transformed_data, media_entries, _media_stats = await _cache_schema_media_for_integration_data(
            integration_id,
            transformed_data,
            integration_doc=integration_doc,
            base_media_entries=raw_payload.media_entries if raw_payload is not None else [],
            import_missing_now=True,
        )
        options, option_types = await _apply_schema_collected_options(
            integration_id,
            transformed_data,
            options,
            option_types,
        )
        await _store_integration_data(
            data_coll,
            integration_id,
            transformed_data,
            raw_data=raw_data,
            options=options,
            option_types=option_types,
            media_entries=media_entries,
            output_primary_key_path=str(integration_doc.get("output_primary_key_path") or "").strip(),
        )
        payload = IntegrationDataPayload(
            data=transformed_data,
            options=options,
            option_types=option_types,
            media_entries=media_entries,
        )
        deep_cache[integration_id] = payload
        return payload
    finally:
        call_stack.discard(integration_id)


async def _execute_deep_fetch_job(job_id: str, integration_id: str) -> None:
    jobs_coll = _jobs_coll()
    coll = _integrations_coll()
    data_coll = _data_coll()

    try:
        job_oid = ObjectId(job_id)
    except Exception:
        return

    now = datetime.utcnow()
    await jobs_coll.update_one(
        {"_id": job_oid},
        {
            "$set": {
                "status": "running",
                "started_at": now,
                "updated_at": now,
                "expires_at": job_expires_at("running", now),
            }
        },
    )

    try:
        try:
            integration_oid = ObjectId(integration_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

        doc = await coll.find_one({"_id": integration_oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Integration not found")
        if not _is_composable_integration_doc(doc):
            raise HTTPException(status_code=400, detail="Deep fetch is only available for composable integrations")

        payload = await _fetch_deep_data_for_integration(
            integration_id,
            doc,
            coll,
            data_coll,
            call_stack=set(),
            deep_cache={},
        )
        data = payload.data

        latest_data_doc = await data_coll.find_one(
            {"integration_id": integration_id},
            sort=[("fetched_at", -1)],
        )
        fetched_at = latest_data_doc["fetched_at"] if latest_data_doc else datetime.utcnow()
        item_count = len(data) if isinstance(data, list) else (0 if data is None else 1)
        now = datetime.utcnow()

        await jobs_coll.update_one(
            {"_id": job_oid},
            {
                "$set": {
                    "status": "succeeded",
                    "fetched_at": fetched_at,
                    "item_count": item_count,
                    "finished_at": now,
                    "updated_at": now,
                    "expires_at": job_expires_at("succeeded", now),
                    "error": None,
                }
            },
        )
    except HTTPException as exc:
        now = datetime.utcnow()
        await jobs_coll.update_one(
            {"_id": job_oid},
            {
                "$set": {
                    "status": "failed",
                    "error": _stringify_error_detail(exc.detail),
                    "finished_at": now,
                    "updated_at": now,
                    "expires_at": job_expires_at("failed", now),
                }
            },
        )
    except Exception as exc:
        now = datetime.utcnow()
        await jobs_coll.update_one(
            {"_id": job_oid},
            {
                "$set": {
                    "status": "failed",
                    "error": str(exc),
                    "finished_at": now,
                    "updated_at": now,
                    "expires_at": job_expires_at("failed", now),
                }
            },
        )


async def _enqueue_or_get_deep_fetch_job(integration_id: str) -> IntegrationDeepFetchJobResponse:
    """Create/reuse a deep-fetch background job and return its current state."""
    coll = _integrations_coll()
    jobs_coll = _jobs_coll()

    try:
        oid = ObjectId(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Integration not found")
    if not _is_composable_integration_doc(doc):
        raise HTTPException(status_code=400, detail="Deep fetch is only available for composable integrations")

    now = datetime.utcnow()
    existing_job = await jobs_coll.find_one(
        {
            "integration_id": integration_id,
            "status": {"$in": list(DEEP_FETCH_RUNNING_STATUSES)},
            "$or": [
                {"expires_at": {"$exists": False}},
                {"expires_at": None},
                {"expires_at": {"$gt": now}},
            ],
        },
        sort=[("created_at", -1)],
    )
    if existing_job:
        return _format_deep_fetch_job(existing_job)

    insert_result = await jobs_coll.insert_one(
        {
            "integration_id": integration_id,
            "status": "queued",
            "error": None,
            "item_count": None,
            "fetched_at": None,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "updated_at": now,
            "expires_at": job_expires_at("queued", now),
        }
    )
    job_id = str(insert_result.inserted_id)
    task = asyncio.create_task(_execute_deep_fetch_job(job_id, integration_id))
    _track_deep_fetch_task(task)

    created_job = await jobs_coll.find_one({"_id": insert_result.inserted_id})
    if not created_job:
        raise HTTPException(status_code=500, detail="Failed to create deep fetch job")
    return _format_deep_fetch_job(created_job)


async def _fetch_container_payload(
    integration_id: str,
    integration_doc: dict,
    coll,
    data_coll,
    *,
    deep: bool = False,
    call_stack: set[str] | None = None,
    deep_cache: dict[str, IntegrationDataPayload] | None = None,
) -> IntegrationDataPayload:
    container_config = integration_doc.get("container_config")
    if not isinstance(container_config, dict):
        raise HTTPException(status_code=400, detail="Composable integration is missing container_config")

    sources = container_config.get("sources")
    target_source_id = str(container_config.get("target_source_integration_id") or "").strip()

    if not isinstance(sources, list) or len(sources) < 2:
        raise HTTPException(status_code=400, detail="Composable integration requires at least 2 source integrations")

    prepared_sources: list[dict[str, Any]] = []

    for source in sources:
        if not isinstance(source, dict):
            continue

        source_id = str(source.get("integration_id") or "").strip()
        if not source_id:
            continue

        if source_id == integration_id:
            raise HTTPException(status_code=400, detail="Composable integrations cannot reference themselves")

        try:
            source_oid = ObjectId(source_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid source integration id: {source_id}") from exc

        source_doc = await coll.find_one({"_id": source_oid})
        if not source_doc:
            raise HTTPException(status_code=400, detail=f"Source integration not found: {source_id}")

        if deep:
            next_call_stack = call_stack if call_stack is not None else set()
            next_deep_cache = deep_cache if deep_cache is not None else {}
            source_payload = await _fetch_deep_data_for_integration(
                source_id,
                source_doc,
                coll,
                data_coll,
                call_stack=next_call_stack,
                deep_cache=next_deep_cache,
            )
        else:
            source_payload = await _fetch_cached_integration_payload(
                data_coll,
                source_id,
                str(source_doc.get("name") or source_id),
            )
        source_data = source_payload.data

        if not isinstance(source_data, list):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Source integration '{source_doc.get('name', source_id)}' data must be a list "
                    "to be merged in a composable"
                ),
            )

        source_merge_style = str(source.get("merge_style") or "flat").strip().lower()
        if source_merge_style not in {"flat", "nested"}:
            raise HTTPException(
                status_code=400,
                detail=f"Source integration {source_id} has unsupported merge_style '{source_merge_style}'",
            )
        source_nested_key = str(source.get("nested_key") or "").strip() or None
        source_keep_target_key = bool(source.get("keep_target_key", False))
        if source_merge_style == "nested" and not source_nested_key:
            raise HTTPException(
                status_code=400,
                detail=f"Source integration {source_id} requires nested_key when merge_style is 'nested'",
            )

        source_key_path = str(source.get("source_key_path") or "").strip() or None
        target_key_path = str(source.get("target_key_path") or "").strip() or None

        prepared_sources.append(
            {
                "source_id": source_id,
                "data": source_data,
                "source_key_path": source_key_path,
                "target_key_path": target_key_path,
                "merge_style": source_merge_style,
                "nested_key": source_nested_key,
                "keep_target_key": source_keep_target_key,
                "options": source_payload.options,
                "option_types": source_payload.option_types,
                "media_entries": copy.deepcopy(source_payload.media_entries),
            }
        )

    container_options: dict[str, list[Any]] = {}
    container_option_types: dict[str, IntegrationOptionChoiceType] = {}
    container_media_entries: list[dict[str, Any]] = []

    if not target_source_id:
        concatenated: list[Any] = []
        for source_entry in prepared_sources:
            source_data = source_entry.get("data")
            if isinstance(source_data, list):
                concatenated.extend(source_data)
            container_media_entries.extend(copy.deepcopy(source_entry.get("media_entries") or []))
            _merge_integration_option_metadata(
                container_options,
                container_option_types,
                source_entry.get("options"),
                source_entry.get("option_types"),
            )
        return IntegrationDataPayload(
            data=concatenated,
            options=container_options,
            option_types=container_option_types,
            media_entries=container_media_entries,
        )

    if not prepared_sources:
        return IntegrationDataPayload(data=[], options={}, option_types={}, media_entries=[])

    target_source_entry = next(
        (
            source_entry
            for source_entry in prepared_sources
            if str(source_entry.get("source_id") or "").strip() == target_source_id
        ),
        None,
    )
    if not target_source_entry:
        raise HTTPException(status_code=400, detail="target_source_integration_id source is missing or invalid")

    target_rows_raw = target_source_entry.get("data")
    if not isinstance(target_rows_raw, list):
        return IntegrationDataPayload(data=[], options={}, option_types={}, media_entries=[])

    container_media_entries.extend(copy.deepcopy(target_source_entry.get("media_entries") or []))
    _merge_integration_option_metadata(
        container_options,
        container_option_types,
        target_source_entry.get("options"),
        target_source_entry.get("option_types"),
    )

    merged_rows: list[Any] = []
    for target_item in target_rows_raw:
        if isinstance(target_item, dict):
            merged_rows.append(dict(target_item))
        else:
            merged_rows.append(target_item)

    for source_entry in prepared_sources:
        if source_entry.get("source_id") == target_source_id:
            continue

        container_media_entries.extend(copy.deepcopy(source_entry.get("media_entries") or []))
        source_key_path = str(source_entry.get("source_key_path") or "").strip()
        target_key_path = str(source_entry.get("target_key_path") or "").strip()
        if not source_key_path:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Source integration {source_entry.get('source_id')} requires source_key_path "
                    "when target_source_integration_id is set"
                ),
            )
        if not target_key_path:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Source integration {source_entry.get('source_id')} requires target_key_path "
                    "when target_source_integration_id is set"
                ),
            )

        source_data = source_entry.get("data")
        if not isinstance(source_data, list):
            continue

        source_merge_style = str(source_entry.get("merge_style") or "flat").strip().lower()
        source_nested_key = str(source_entry.get("nested_key") or "").strip()
        _merge_integration_option_metadata(
            container_options,
            container_option_types,
            source_entry.get("options"),
            source_entry.get("option_types"),
            path_prefix=source_nested_key if source_merge_style == "nested" else None,
            removed_path=source_key_path,
        )

        source_rows_by_key: dict[str, dict[str, Any]] = {}
        for source_item in source_data:
            if not isinstance(source_item, dict):
                continue

            source_key_value = _extract_value_from_path(source_item, source_key_path)
            if source_key_value in (None, ""):
                continue

            key_token = str(source_key_value)
            merge_item = dict(source_item)
            _remove_value_from_path(merge_item, source_key_path)
            if key_token in source_rows_by_key:
                source_rows_by_key[key_token].update(merge_item)
            else:
                source_rows_by_key[key_token] = merge_item

        source_merge_style = str(source_entry.get("merge_style") or "flat").strip().lower()
        source_nested_key = str(source_entry.get("nested_key") or "").strip()
        source_keep_target_key = bool(source_entry.get("keep_target_key", False))
        next_rows: list[Any] = []
        for merged_item in merged_rows:
            if not isinstance(merged_item, dict):
                next_rows.append(merged_item)
                continue

            combined = dict(merged_item)
            target_key_value = _extract_value_from_path(combined, target_key_path)
            source_match = None if target_key_value in (None, "") else source_rows_by_key.get(str(target_key_value))
            if source_match:
                target_alias_path: str | None = None
                if source_keep_target_key and target_key_value not in (None, ""):
                    target_key_parts = _normalize_path(target_key_path)
                    if target_key_parts:
                        target_alias_path = ".".join(
                                [
                                    *target_key_parts[:-1],
                                    f"{target_key_parts[-1]}_id",
                                ]
                            )

                if source_merge_style == "nested":
                    if not source_nested_key:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Source integration {source_entry.get('source_id')} "
                                "requires nested_key when merge_style is 'nested'"
                            ),
                        )
                    if target_alias_path:
                        _set_value_at_path(combined, target_alias_path, target_key_value)
                    _remove_value_from_path(combined, target_key_path)
                    # Later source wins by source order.
                    combined[source_nested_key] = source_match
                else:
                    # Later source wins by source order.
                    combined.update(source_match)
                    if target_alias_path:
                        _set_value_at_path(combined, target_alias_path, target_key_value)
            next_rows.append(combined)
        merged_rows = next_rows

    return IntegrationDataPayload(
        data=merged_rows,
        options=container_options,
        option_types=container_option_types,
        media_entries=container_media_entries,
    )


async def _fetch_container_data(
    integration_id: str,
    integration_doc: dict,
    coll,
    data_coll,
    *,
    deep: bool = False,
    call_stack: set[str] | None = None,
    deep_cache: dict[str, IntegrationDataPayload] | None = None,
) -> list[Any]:
    return (
        await _fetch_container_payload(
            integration_id,
            integration_doc,
            coll,
            data_coll,
            deep=deep,
            call_stack=call_stack,
            deep_cache=deep_cache,
        )
    ).data


# -------------------------
# CRUD Endpoints
# -------------------------


@router.get("")
async def list_integrations(
    _=Depends(require_permission("admin:general")),
) -> list[IntegrationResponse]:
    """List all integrations."""
    coll = _integrations_coll()
    data_coll = _data_coll()

    integrations = []
    async for doc in coll.find().sort("name", 1):
        data_doc = await data_coll.find_one(
            {"integration_id": str(doc["_id"])},
            sort=[("fetched_at", -1)],
        )
        integrations.append(_format_integration(doc, data_doc))

    return integrations


@router.post("")
async def create_integration(
    payload: IntegrationCreate,
    _=Depends(require_permission("admin:general")),
) -> IntegrationResponse:
    """Create a new integration."""
    coll = _integrations_coll()

    doc_type = _normalize_integration_type(payload.type)
    url = str(payload.url or "").strip()
    description = str(payload.description or "").strip() or None
    output_primary_key_path = str(payload.output_primary_key_path or "").strip() or None

    submitted_transform_steps = [step.model_dump() for step in payload.transform_steps]
    _validate_removed_transform_ops(submitted_transform_steps)
    collect_option_paths = _collect_option_paths_from_transform_steps(submitted_transform_steps)
    transform_steps = _strip_collect_distinct_transform_steps(submitted_transform_steps)
    container_config = payload.container_config.model_dump() if payload.container_config else None
    crawler_pagination_config = (
        payload.crawler_pagination_config.model_dump()
        if payload.crawler_pagination_config
        else None
    )

    if _is_composable_integration_type(doc_type):
        await _validate_container_config(coll, container_config)
        url = ""
        auth_type = "none"
        key_name = None
        response_type = "json"
        response_path = None
        crawler_pagination_config = None
    else:
        if not url:
            raise HTTPException(status_code=400, detail="url is required for API/crawler integrations")
        auth_type = payload.auth_type
        key_name = payload.key_name
        response_type = payload.response_type
        response_path = payload.response_path
        container_config = None
        if doc_type != "crawler":
            crawler_pagination_config = None
        elif crawler_pagination_config and response_type != "json":
            raise HTTPException(
                status_code=400,
                detail="crawler_pagination_config requires response_type 'json'",
            )

    now = datetime.utcnow()
    doc = {
        "name": payload.name,
        "url": url,
        "type": doc_type,
        "auth_type": auth_type,
        "key_name": key_name,
        "response_type": response_type,
        "response_path": response_path,
        "crawler_pagination_config": crawler_pagination_config,
        "allowed_sections": payload.allowed_sections,
        "description": description,
        "favorite": bool(payload.favorite),
        "transform_steps": transform_steps,
        "output_primary_key_path": output_primary_key_path,
        "item_page_sync_blocked": bool(payload.item_page_sync_blocked),
        "container_config": container_config,
        "created_at": now,
        "updated_at": now,
    }

    result = await coll.insert_one(doc)
    doc["_id"] = result.inserted_id
    if collect_option_paths:
        await _seed_schema_collect_options(str(result.inserted_id), collect_option_paths)

    return _format_integration(doc)


@router.post("/health/draft")
async def health_check_draft(
    payload: IntegrationDraftHealthRequest,
    _=Depends(require_permission("admin:general")),
) -> IntegrationHealthResponse:
    """Run health check on an unsaved integration draft."""
    integration_doc = {
        "url": str(payload.url or "").strip(),
        "type": str(payload.type or "api").strip(),
        "auth_type": str(payload.auth_type or "none").strip(),
        "key_name": payload.key_name,
    }
    return await _run_health_check(integration_doc)


@router.post("/inspect/draft")
async def inspect_draft(
    payload: IntegrationDraftInspectRequest,
    _=Depends(require_permission("admin:general")),
) -> IntegrationDraftInspectResponse:
    """Fetch draft integration data without persisting it."""
    integration_type = str(payload.type or "api").strip()
    if _is_composable_integration_type(integration_type):
        raise HTTPException(status_code=400, detail="Draft inspect supports only API/crawler integrations")

    integration_doc = {
        "url": str(payload.url or "").strip(),
        "type": integration_type,
        "auth_type": str(payload.auth_type or "none").strip(),
        "key_name": payload.key_name,
        "response_type": str(payload.response_type or "json").strip(),
        "response_path": payload.response_path,
        "crawler_pagination_config": payload.crawler_pagination_config,
    }
    data = await _fetch_remote_integration_data(integration_doc)
    item_count = len(data) if isinstance(data, list) else (0 if data is None else 1)
    return IntegrationDraftInspectResponse(data=data, item_count=item_count)


@router.get("/connection/config")
async def get_connection_config(
    _=Depends(require_permission("admin:general")),
) -> IntegrationConnectionConfigResponse:
    """Get global integrations exposure + template-level integration rules."""
    config_doc = await _settings_coll().find_one({"key": INTEGRATIONS_CONNECTION_CONFIG_KEY})
    exposed_integration_ids: list[str] = []
    template_integration_rules: dict[str, dict[str, Any]] = {}
    if isinstance(config_doc, dict):
        exposed_integration_ids = _normalize_integration_id_list(
            config_doc.get("exposed_integration_ids"),
        )
        template_integration_rules = _normalize_template_integration_rules(
            config_doc.get("template_integration_rules"),
        )
    return IntegrationConnectionConfigResponse(
        exposed_integration_ids=exposed_integration_ids,
        template_integration_rules=template_integration_rules,
    )


@router.patch("/connection/config")
async def update_connection_config(
    payload: IntegrationConnectionConfigUpdate,
    _=Depends(require_permission("admin:general")),
) -> IntegrationConnectionConfigResponse:
    """Update global integrations exposure + template-level integration rules."""
    existing_doc = await _settings_coll().find_one({"key": INTEGRATIONS_CONNECTION_CONFIG_KEY})
    existing_exposed = _normalize_integration_id_list(
        existing_doc.get("exposed_integration_ids") if isinstance(existing_doc, dict) else [],
    )
    existing_template_rules = _normalize_template_integration_rules(
        existing_doc.get("template_integration_rules") if isinstance(existing_doc, dict) else {},
    )
    exposed_integration_ids = (
        _normalize_integration_id_list(payload.exposed_integration_ids)
        if payload.exposed_integration_ids is not None
        else existing_exposed
    )
    template_integration_rules = (
        _normalize_template_integration_rules(
            {
                key: rule.model_dump()
                for key, rule in (payload.template_integration_rules or {}).items()
            }
        )
        if payload.template_integration_rules is not None
        else existing_template_rules
    )
    now = datetime.utcnow()
    await _settings_coll().update_one(
        {"key": INTEGRATIONS_CONNECTION_CONFIG_KEY},
        {
            "$set": {
                "key": INTEGRATIONS_CONNECTION_CONFIG_KEY,
                "exposed_integration_ids": exposed_integration_ids,
                "template_integration_rules": template_integration_rules,
                "updated_at": now,
            },
            "$unset": {
                "enabled_for_all_instances": "",
                "section_template_integration_map": "",
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return IntegrationConnectionConfigResponse(
        exposed_integration_ids=exposed_integration_ids,
        template_integration_rules=template_integration_rules,
    )


@router.get("/{integration_id}")
async def get_integration(
    integration_id: str,
    _=Depends(require_permission("admin:general")),
) -> IntegrationResponse:
    """Get a single integration."""
    coll = _integrations_coll()
    data_coll = _data_coll()

    try:
        oid = ObjectId(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Integration not found")

    data_doc = await data_coll.find_one(
        {"integration_id": integration_id},
        sort=[("fetched_at", -1)],
    )

    return _format_integration(doc, data_doc)


@router.patch("/{integration_id}")
async def update_integration(
    integration_id: str,
    payload: IntegrationUpdate,
    _=Depends(require_permission("admin:general")),
) -> IntegrationResponse:
    """Update an integration."""
    coll = _integrations_coll()
    data_coll = _data_coll()

    try:
        oid = ObjectId(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Integration not found")

    update_data = payload.model_dump(exclude_unset=True)
    collect_option_paths: list[str] = []
    if "transform_steps" in update_data and isinstance(update_data["transform_steps"], list):
        _validate_removed_transform_ops(update_data["transform_steps"])
        collect_option_paths = _collect_option_paths_from_transform_steps(update_data["transform_steps"])
        update_data["transform_steps"] = _strip_collect_distinct_transform_steps(update_data["transform_steps"])

    if "transform_steps" in update_data and update_data["transform_steps"] is None:
        update_data["transform_steps"] = []
    if "description" in update_data:
        update_data["description"] = str(update_data.get("description") or "").strip() or None
    if "output_primary_key_path" in update_data:
        update_data["output_primary_key_path"] = str(update_data.get("output_primary_key_path") or "").strip() or None

    target_type = _normalize_integration_type(update_data.get("type", doc.get("type", "api")))
    update_data["type"] = target_type

    if _is_composable_integration_type(target_type):
        container_config = update_data.get("container_config", doc.get("container_config"))
        if isinstance(container_config, BaseModel):
            container_config = container_config.model_dump()
        await _validate_container_config(coll, container_config, current_integration_id=integration_id)

        update_data["container_config"] = container_config
        update_data["url"] = ""
        update_data["auth_type"] = "none"
        update_data["key_name"] = None
        update_data["response_type"] = "json"
        update_data["response_path"] = None
        update_data["crawler_pagination_config"] = None
    else:
        next_url = str(update_data.get("url", doc.get("url") or "")).strip()
        if not next_url:
            raise HTTPException(status_code=400, detail="url is required for API/crawler integrations")

        crawler_pagination_config = update_data.get(
            "crawler_pagination_config",
            doc.get("crawler_pagination_config"),
        )
        if isinstance(crawler_pagination_config, BaseModel):
            crawler_pagination_config = crawler_pagination_config.model_dump()

        next_response_type = str(update_data.get("response_type", doc.get("response_type", "json")) or "json").strip()
        if target_type != "crawler":
            crawler_pagination_config = None
        elif crawler_pagination_config and next_response_type != "json":
            raise HTTPException(
                status_code=400,
                detail="crawler_pagination_config requires response_type 'json'",
            )

        update_data["url"] = next_url
        update_data["crawler_pagination_config"] = crawler_pagination_config
        update_data["container_config"] = None

    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await coll.update_one({"_id": oid}, {"$set": update_data})
        doc = await coll.find_one({"_id": oid})
    if collect_option_paths:
        await _seed_schema_collect_options(integration_id, collect_option_paths)

    data_doc = await data_coll.find_one(
        {"integration_id": integration_id},
        sort=[("fetched_at", -1)],
    )

    return _format_integration(doc, data_doc)


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: str,
    _=Depends(require_permission("admin:general")),
) -> dict:
    """Delete an integration and its data."""
    coll = _integrations_coll()
    data_coll = _data_coll()

    try:
        oid = ObjectId(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Integration not found")

    await coll.delete_one({"_id": oid})
    await data_coll.delete_many({"integration_id": integration_id})
    await _overrides_coll().delete_many({"integration_id": integration_id})
    await _item_reviews_coll().delete_many({"integration_id": integration_id})
    await _local_items_coll().delete_many({"integration_id": integration_id})
    await _schemas_coll().delete_many({"integration_id": integration_id})

    return {"ok": True, "deleted_id": integration_id}


# -------------------------
# Health Check & Fetch
# -------------------------


@router.post("/{integration_id}/health")
async def health_check(
    integration_id: str,
    _=Depends(require_permission("admin:general")),
) -> IntegrationHealthResponse:
    """Test connection to integration endpoint."""
    coll = _integrations_coll()

    try:
        oid = ObjectId(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Integration not found")

    return await _run_health_check(doc)


@router.post("/{integration_id}/fetch")
async def fetch_data(
    integration_id: str,
    _=Depends(require_permission("admin:general")),
) -> IntegrationDataResponse:
    """Fetch data from integration and store it."""
    coll = _integrations_coll()
    data_coll = _data_coll()

    try:
        oid = ObjectId(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Integration not found")
    await _migrate_collect_distinct_steps_to_schema(integration_id, doc, strip_from_doc=True)

    if _is_composable_integration_doc(doc):
        container_payload = await _fetch_container_payload(integration_id, doc, coll, data_coll)
        raw_data: Any = container_payload.data
        initial_options = container_payload.options
        initial_option_types = container_payload.option_types
    else:
        raw_data = await _fetch_remote_integration_data(doc)
        initial_options = {}
        initial_option_types = {}

    data, options, option_types = _apply_transform_steps(
        raw_data,
        _get_integration_transform_steps(doc),
        initial_options=initial_options,
        initial_option_types=initial_option_types,
    )
    data = _remove_empty_string_list_items(data)
    await _persist_detected_schema_for_integration_data(
        integration_id,
        doc,
        data,
    )
    data, media_entries, media_stats = await _cache_schema_media_for_integration_data(
        integration_id,
        data,
        integration_doc=doc,
        base_media_entries=container_payload.media_entries if _is_composable_integration_doc(doc) else [],
        import_missing_now=True,
    )
    options, option_types = await _apply_schema_collected_options(
        integration_id,
        data,
        options,
        option_types,
    )
    now = await _store_integration_data(
        data_coll,
        integration_id,
        data,
        raw_data=raw_data,
        options=options,
        option_types=option_types,
        media_entries=media_entries,
        output_primary_key_path=str(doc.get("output_primary_key_path") or "").strip(),
    )

    item_count = len(data) if isinstance(data, list) else 1

    return IntegrationDataResponse(
        integration_id=integration_id,
        data=data,
        options=options,
        option_types=option_types,
        media_entries=media_entries,
        media_cache_stats=_format_media_cache_stats(media_stats),
        fetched_at=now,
        item_count=item_count,
    )


@router.post("/{integration_id}/fetch/deep/async")
async def enqueue_fetch_data_deep(
    integration_id: str,
    _=Depends(require_permission("admin:general")),
) -> IntegrationDeepFetchJobResponse:
    """
    Start a deep fetch job in the background and return immediately.

    This avoids long-lived HTTP requests that can hit gateway/proxy timeouts.
    """
    return await _enqueue_or_get_deep_fetch_job(integration_id)


@router.get("/fetch-jobs/{job_id}")
async def get_fetch_job(
    job_id: str,
    _=Depends(require_permission("admin:general")),
) -> IntegrationDeepFetchJobResponse:
    """Get current status of a background deep fetch job."""
    jobs_coll = _jobs_coll()
    try:
        job_oid = ObjectId(job_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid job ID") from exc

    job_doc = await jobs_coll.find_one({"_id": job_oid})
    if not job_doc:
        raise HTTPException(status_code=404, detail="Fetch job not found")
    return _format_deep_fetch_job(job_doc)


@router.post("/{integration_id}/reprocess")
async def reprocess_data(
    integration_id: str,
    _=Depends(require_permission("admin:general")),
) -> IntegrationDataResponse:
    """Re-run configured transform steps on cached base data without upstream fetch."""
    coll = _integrations_coll()
    data_coll = _data_coll()

    try:
        oid = ObjectId(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Integration not found")
    await _migrate_collect_distinct_steps_to_schema(integration_id, doc, strip_from_doc=True)

    data_doc = await data_coll.find_one(
        {"integration_id": integration_id},
        sort=[("fetched_at", -1)],
    )
    if not data_doc:
        raise HTTPException(status_code=404, detail="No cached data available to reprocess")

    if _is_composable_integration_doc(doc):
        container_payload = await _fetch_container_payload(integration_id, doc, coll, data_coll)
        raw_data = container_payload.data
        initial_options = container_payload.options
        initial_option_types = container_payload.option_types
    elif "raw_data" in data_doc:
        raw_data: Any = copy.deepcopy(data_doc.get("raw_data"))
        initial_options = {}
        initial_option_types = {}
    else:
        raw_data = copy.deepcopy(data_doc.get("data"))
        initial_options = {}
        initial_option_types = {}

    transformed_data, options, option_types = _apply_transform_steps(
        raw_data,
        _get_integration_transform_steps(doc),
        initial_options=initial_options,
        initial_option_types=initial_option_types,
    )
    transformed_data = _remove_empty_string_list_items(transformed_data)
    await _persist_detected_schema_for_integration_data(
        integration_id,
        doc,
        transformed_data,
    )
    transformed_data, media_entries, media_stats = await _cache_schema_media_for_integration_data(
        integration_id,
        transformed_data,
        integration_doc=doc,
        base_media_entries=container_payload.media_entries if _is_composable_integration_doc(doc) else [],
        import_missing_now=True,
    )
    options, option_types = await _apply_schema_collected_options(
        integration_id,
        transformed_data,
        options,
        option_types,
    )
    now = await _store_integration_data(
        data_coll,
        integration_id,
        transformed_data,
        raw_data=raw_data,
        options=options,
        option_types=option_types,
        media_entries=media_entries,
        output_primary_key_path=str(doc.get("output_primary_key_path") or "").strip(),
    )
    item_count = len(transformed_data) if isinstance(transformed_data, list) else 1

    return IntegrationDataResponse(
        integration_id=integration_id,
        data=transformed_data,
        options=options,
        option_types=option_types,
        media_entries=media_entries,
        media_cache_stats=_format_media_cache_stats(media_stats),
        fetched_at=now,
        item_count=item_count,
    )


@router.get("/{integration_id}/data")
async def get_data(
    integration_id: str,
    _=Depends(require_permission("admin:general")),
) -> IntegrationDataResponse:
    """Get stored integration data."""
    coll = _integrations_coll()
    data_coll = _data_coll()

    try:
        oid = ObjectId(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Integration not found")

    data_doc = await data_coll.find_one(
        {"integration_id": integration_id},
        sort=[("fetched_at", -1)],
    )

    if not data_doc:
        raise HTTPException(status_code=404, detail="No data fetched yet")

    data = data_doc["data"]
    options = _normalize_integration_options(data_doc.get("options"))
    option_types = _normalize_integration_option_types(data_doc.get("option_types"), options)
    options, option_types = await _apply_schema_collected_options(
        integration_id,
        data,
        options,
        option_types,
    )
    item_count = len(data) if isinstance(data, list) else 1

    return IntegrationDataResponse(
        integration_id=integration_id,
        data=data,
        options=copy.deepcopy(options),
        option_types=copy.deepcopy(option_types),
        media_entries=copy.deepcopy(data_doc.get("media_entries") or []),
        fetched_at=data_doc["fetched_at"],
        item_count=item_count,
    )


@router.get("/{integration_id}/data/effective")
async def get_effective_data(
    integration_id: str,
    _=Depends(require_permission("admin:general")),
) -> IntegrationDataResponse:
    """Get integration data with active local review overrides applied."""
    integration_doc, data_doc, effective_data, options, option_types = await _get_effective_integration_data_doc(
        integration_id,
    )
    item_count = len(effective_data) if isinstance(effective_data, list) else (0 if effective_data is None else 1)
    return IntegrationDataResponse(
        integration_id=integration_id,
        data=effective_data,
        options=copy.deepcopy(options),
        option_types=copy.deepcopy(option_types),
        media_entries=copy.deepcopy(data_doc.get("media_entries") or []),
        fetched_at=data_doc["fetched_at"],
        item_count=item_count,
    )


def _preview_option_label_from_value(value: Any, index: int) -> str:
    if not isinstance(value, dict):
        return f"Item #{index + 1}"

    for key in (
        "gig_title",
        "gigTitle",
        "title",
        "name",
        "artist_name",
        "artistName",
        "display_name",
        "displayName",
        "label",
    ):
        raw = value.get(key)
        if isinstance(raw, dict):
            label = str(raw.get("de") or raw.get("en") or "").strip()
            if label:
                return label
        else:
            label = str(raw or "").strip()
            if label:
                return label

    for key in ("id", "_id", "slug", "page_slug"):
        label = str(value.get(key) or "").strip()
        if label:
            return label

    return f"Item #{index + 1}"


def _build_preview_options(data: Any, output_primary_key_path: str | None = None) -> list[dict[str, Any]]:
    max_items = 200
    if isinstance(data, list):
        options: list[dict[str, Any]] = []
        for index, item in enumerate(data[:max_items]):
            option = {
                "index": index,
                "label": _preview_option_label_from_value(item, index),
            }
            item_key = _review_item_key_for_row(item, output_primary_key_path)
            if item_key:
                option["item_key"] = item_key
            options.append(option)
        return options
    if isinstance(data, dict):
        return [{"index": 0, "label": _preview_option_label_from_value(data, 0)}]
    return []


@router.get("/{integration_id}/data/preview")
async def get_data_preview(
    integration_id: str,
    item_index: int | None = Query(default=None, ge=0),
    item_key: str | None = Query(default=None),
    _=Depends(require_permission("admin:design")),
) -> IntegrationDataPreview:
    """Get preview of integration data (selected item and available keys)."""
    coll = _integrations_coll()
    data_coll = _data_coll()

    try:
        oid = ObjectId(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Integration not found")

    data_doc = await data_coll.find_one(
        {"integration_id": integration_id},
        sort=[("fetched_at", -1)],
    )

    if not data_doc:
        return IntegrationDataPreview(
            integration_id=integration_id,
            preview_item=None,
            available_keys=[],
            options={},
            option_types={},
            fetched_at=None,
            total_items=0,
            selected_index=None,
            selected_item_key=None,
            preview_options=[],
        )

    data = data_doc["data"]
    output_primary_key_path = str(doc.get("output_primary_key_path") or "").strip()
    options = _normalize_integration_options(data_doc.get("options"))
    option_types = _normalize_integration_option_types(data_doc.get("option_types"), options)
    options, option_types = await _apply_schema_collected_options(
        integration_id,
        data,
        options,
        option_types,
    )
    preview_item = None
    available_keys: list[str] = []
    total_items = 0
    selected_index: int | None = None
    selected_item_key: str | None = None
    preview_options = _build_preview_options(data, output_primary_key_path)

    if isinstance(data, list) and data:
        total_items = len(data)
        normalized_item_key = _normalize_review_item_key(item_key)
        if normalized_item_key and output_primary_key_path:
            for index, item in enumerate(data):
                if _review_item_key_for_row(item, output_primary_key_path) == normalized_item_key:
                    selected_index = index
                    preview_item = item
                    selected_item_key = normalized_item_key
                    break
        elif normalized_item_key:
            selected_item_key = normalized_item_key
        if selected_index is None and not normalized_item_key:
            selected_index = min(item_index or 0, total_items - 1)
            preview_item = data[selected_index]
            selected_item_key = _review_item_key_for_row(preview_item, output_primary_key_path) or None
        if isinstance(preview_item, dict):
            available_keys = list(preview_item.keys())
    elif isinstance(data, dict):
        preview_item = data
        total_items = 1
        selected_index = 0
        selected_item_key = REVIEW_ROOT_ITEM_KEY
        available_keys = list(data.keys())

    return IntegrationDataPreview(
        integration_id=integration_id,
        preview_item=preview_item,
        available_keys=available_keys,
        options=copy.deepcopy(options),
        option_types=copy.deepcopy(option_types),
        fetched_at=data_doc["fetched_at"],
        total_items=total_items,
        selected_index=selected_index,
        selected_item_key=selected_item_key,
        preview_options=preview_options,
    )


# -------------------------
# Integration Review + Schema
# -------------------------


@router.patch("/{integration_id}/review/sync-settings")
async def update_review_sync_settings(
    integration_id: str,
    payload: IntegrationReviewSyncSettingsPatchRequest,
    _=Depends(require_permission("admin:general")),
) -> IntegrationResponse:
    """Update item-page sync settings used by integration review."""
    coll = _integrations_coll()
    data_coll = _data_coll()

    try:
        oid = ObjectId(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Integration not found")

    now = datetime.utcnow()
    updated = await coll.find_one_and_update(
        {"_id": oid},
        {
            "$set": {
                "item_page_sync_blocked": bool(payload.item_page_sync_blocked),
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    data_doc = await data_coll.find_one(
        {"integration_id": integration_id},
        sort=[("fetched_at", -1)],
    )
    return _format_integration(updated or doc, data_doc)


@router.get("/{integration_id}/review/items")
async def list_review_items(
    integration_id: str,
    state: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    _=Depends(require_permission("admin:general")),
) -> dict[str, Any]:
    """List ID-keyed integration items with override/conflict status."""
    normalized_state_filter: IntegrationReviewItemState | None = None
    if str(state or "").strip():
        normalized_state_filter = _normalize_review_item_state(state)
        if normalized_state_filter != str(state or "").strip().lower().replace(" ", "_").replace("-", "_"):
            raise HTTPException(status_code=400, detail="Unsupported review state filter")
    normalized_tag_filter = str(tag or "").strip()
    page_state_tag_filter = _normalize_review_page_state_tag_filter(normalized_tag_filter)
    badge_tag_filter = (
        normalized_tag_filter
        if (
            normalized_tag_filter
            and not page_state_tag_filter
            and normalized_tag_filter
            in {
                REVIEW_BADGE_TAG_FILTER_INCOMPLETE,
                REVIEW_BADGE_TAG_FILTER_OVERRIDE,
                REVIEW_BADGE_TAG_FILTER_LOCAL,
            }
        )
        else ""
    )
    custom_tag_filter = "" if badge_tag_filter or page_state_tag_filter else normalized_tag_filter
    integration_doc = await _load_integration_doc_or_404(integration_id)
    data_doc = await _load_integration_data_doc_or_404(integration_id)
    data = data_doc.get("data")
    output_primary_key_path = str(integration_doc.get("output_primary_key_path") or "").strip()
    item_label_path = await _get_schema_item_label_path(integration_id, integration_doc=integration_doc)
    schema_response = await _get_schema_response_for_integration(integration_id, integration_doc=integration_doc)
    schema_field_paths = {
        str(field.get("path") or "").strip()
        for field in schema_response.get("fields", [])
        if str(field.get("path") or "").strip()
    }
    local_docs = await _load_local_review_items(integration_id)
    local_item_keys = {
        str(doc.get("item_key") or "").strip()
        for doc in local_docs
        if str(doc.get("item_key") or "").strip()
    }
    review_data = _combine_fetched_and_local_review_data(data, local_docs)
    return_type = _derive_return_type_from_data(data)
    rows, missing_key_count, can_review = _review_rows_for_data(
        review_data,
        output_primary_key_path,
        item_label_path,
        local_item_keys=local_item_keys,
    )
    previous_rows_by_key = _review_row_map_for_data(
        data_doc.get("previous_data"),
        output_primary_key_path,
        item_label_path,
    )
    review_change_metadata = _compute_review_data_change_metadata(
        data_doc.get("previous_data"),
        data,
        output_primary_key_path,
    )
    changed_item_keys = {
        str(item_key or "").strip()
        for item_key in review_change_metadata.get("changed_item_keys", [])
        if str(item_key or "").strip()
    }
    review_changed_count = int(review_change_metadata.get("changed_count") or 0)
    overrides = [
        override
        for override in await _load_review_overrides(integration_id)
        if not _is_legacy_page_slug_path(override.get("field_path"), schema_field_paths)
    ]
    overrides_by_item: dict[str, list[dict[str, Any]]] = {}
    for override in overrides:
        item_key = str(override.get("item_key") or "").strip()
        if not item_key:
            continue
        overrides_by_item.setdefault(item_key, []).append(override)
    item_review_meta_by_key = await _load_review_item_meta_map(integration_id)
    options = _normalize_integration_options(data_doc.get("options"))
    option_types = _normalize_integration_option_types(data_doc.get("option_types"), options)
    effective_review_data = _apply_review_overrides_to_data(
        review_data,
        output_primary_key_path,
        overrides,
    )
    options, option_types = await _apply_schema_collected_options(
        integration_id,
        effective_review_data,
        options,
        option_types,
    )
    schema_response = _enrich_schema_response_with_options(schema_response, options, option_types)
    schema_fields = {
        str(field.get("path") or "").strip(): field
        for field in schema_response.get("fields", [])
        if str(field.get("path") or "").strip()
    }
    item_page_template_refs = await _load_review_item_page_template_refs(integration_id)
    generated_pages_by_item = await _load_review_generated_pages_by_item(
        integration_id,
        [str(row.get("item_key") or "").strip() for row in rows],
        item_page_template_refs,
        item_page_sync_blocked=bool(integration_doc.get("item_page_sync_blocked", False)),
    )

    all_items: list[dict[str, Any]] = []
    state_counts: dict[str, int] = {state_value: 0 for state_value in REVIEW_ITEM_STATES}
    available_tags: set[str] = set()
    for row in rows:
        item_key = row["item_key"]
        item_overrides = overrides_by_item.get(item_key, [])
        review_meta = _format_review_item_meta(item_review_meta_by_key.get(item_key))
        review_state = review_meta["state"]
        is_local_item = bool(row.get("is_local_item", False))
        tags = _hide_generated_local_review_tags(review_meta["tags"], is_local_item=is_local_item)
        state_counts[review_state] = state_counts.get(review_state, 0) + 1
        available_tags.update(tags)
        has_conflict = any(_is_review_override_conflicted(override, row.get("item")) for override in item_overrides)
        changed_path_count = 0
        previous_row = previous_rows_by_key.get(item_key)
        if previous_row is not None:
            changed_path_count = len(
                _compute_cache_payload_diff(
                    previous_row.get("item"),
                    row.get("item"),
                    unordered_lists=True,
                )[0]
            )
        elif item_key in changed_item_keys:
            changed_path_count = 1
        effective_item = _effective_review_item_for_overrides(
            row.get("item"),
            item_key=item_key,
            output_primary_key_path=output_primary_key_path,
            overrides=item_overrides,
        )
        missing_required_paths = _missing_required_schema_paths(effective_item, schema_fields)
        generated_pages = generated_pages_by_item.get(item_key, [])
        generated_page_summary = _summarize_review_generated_pages(generated_pages)
        all_items.append(
            {
                "item_key": item_key,
                "label": row.get("label") or item_key,
                "index": row.get("index"),
                "is_local_item": is_local_item,
                "is_incomplete": bool(missing_required_paths),
                "missing_required_paths": missing_required_paths,
                "state": review_state,
                "tags": tags,
                "review_updated_at": review_meta.get("updated_at"),
                "has_override": len(item_overrides) > 0,
                "override_count": len(item_overrides),
                "has_conflict": has_conflict,
                "source_changed": bool(item_key in changed_item_keys and not row.get("is_local_item", False)),
                "changed_path_count": changed_path_count,
                "generated_pages": generated_pages,
                **generated_page_summary,
            }
        )

    all_items.sort(
        key=lambda item: (
            str(item.get("label") or item.get("item_key") or "").lower(),
            str(item.get("item_key") or "").lower(),
        )
    )
    available_page_state_filter_counts: dict[str, int] = {}
    for item in all_items:
        for filter_value in _review_page_state_tag_filters_for_generated_pages(
            item.get("generated_pages") if isinstance(item.get("generated_pages"), list) else []
        ):
            available_page_state_filter_counts[filter_value] = (
                available_page_state_filter_counts.get(filter_value, 0) + 1
            )

    items = [
        item
        for item in all_items
        if (
            normalized_state_filter is None
            or item.get("state") == normalized_state_filter
        )
        and (
            not custom_tag_filter
            or custom_tag_filter in item.get("tags", [])
        )
        and (
            not page_state_tag_filter
            or page_state_tag_filter in _review_page_state_tag_filters_for_generated_pages(
                item.get("generated_pages") if isinstance(item.get("generated_pages"), list) else []
            )
        )
        and (
            not badge_tag_filter
            or (
                badge_tag_filter == REVIEW_BADGE_TAG_FILTER_INCOMPLETE
                and item.get("is_incomplete")
            )
            or (
                badge_tag_filter == REVIEW_BADGE_TAG_FILTER_OVERRIDE
                and item.get("has_override")
            )
            or (
                badge_tag_filter == REVIEW_BADGE_TAG_FILTER_LOCAL
                and item.get("is_local_item")
            )
        )
    ]

    return {
        "integration_id": integration_id,
        "return_type": return_type,
        "requires_primary_key": return_type == "list",
        "output_primary_key_path": output_primary_key_path or None,
        "page_slug_path": schema_response.get("page_slug_path"),
        "can_review": bool(can_review and (return_type != "list" or output_primary_key_path)),
        "item_count": len(data) if isinstance(data, list) else (1 if isinstance(data, dict) else 0),
        "local_item_count": len(local_item_keys),
        "reviewable_item_count": len(all_items),
        "filtered_item_count": len(items),
        "missing_key_count": missing_key_count,
        "fetched_at": data_doc.get("fetched_at"),
        "previous_fetched_at": data_doc.get("previous_fetched_at"),
        "data_hash": data_doc.get("data_hash"),
        "previous_hash": data_doc.get("previous_hash"),
        "source_changed": bool(review_changed_count),
        "changed_count": review_changed_count,
        "item_page_template_count": len(item_page_template_refs),
        "item_page_templates_active": bool(item_page_template_refs),
        "item_page_sync_blocked": bool(integration_doc.get("item_page_sync_blocked", False)),
        "state_counts": state_counts,
        "available_tags": sorted(available_tags, key=lambda value: value.lower()),
        "available_page_state_filters": _format_review_page_state_tag_filter_options(
            available_page_state_filter_counts
        ),
        "schema_fields": schema_response.get("fields", []),
        "options": copy.deepcopy(options),
        "option_types": copy.deepcopy(option_types),
        "item_label_path": schema_response.get("item_label_path"),
        "state_filter": normalized_state_filter,
        "tag_filter": normalized_tag_filter or None,
        "items": items,
    }


@router.post("/{integration_id}/review/items")
async def create_review_item(
    integration_id: str,
    payload: IntegrationReviewItemCreateRequest,
    _=Depends(require_permission("admin:general")),
) -> dict[str, Any]:
    """Create a local-only review item from schema field values."""
    integration_doc = await _load_integration_doc_or_404(integration_id)
    data_doc = await _load_integration_data_doc_or_404(integration_id)
    data = data_doc.get("data")
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="Local review items are only supported for list integrations")

    output_primary_key_path = str(integration_doc.get("output_primary_key_path") or "").strip()
    if not output_primary_key_path:
        raise HTTPException(status_code=400, detail="ID is required before adding review items")

    schema_response = await _get_schema_response_for_integration(
        integration_id,
        integration_doc=integration_doc,
    )
    schema_fields = {
        str(field.get("path") or "").strip(): field
        for field in schema_response.get("fields", [])
        if str(field.get("path") or "").strip()
    }
    if not schema_fields:
        raise HTTPException(status_code=400, detail="Detect a schema before adding review items")
    item_label_path = _normalize_review_field_path(schema_response.get("item_label_path"))
    if not item_label_path or item_label_path not in schema_fields:
        raise HTTPException(status_code=400, detail="Item name field is required before adding review items")

    item: dict[str, Any] = {}
    values = payload.values if isinstance(payload.values, dict) else {}
    for raw_path, value in values.items():
        path = _normalize_review_field_path(raw_path)
        if not path or path not in schema_fields:
            continue
        _set_value_at_path(item, path, copy.deepcopy(value))

    has_item_name, item_name = _review_value_from_item(item, item_label_path)
    if _is_review_required_value_missing(has_item_name, item_name):
        raise HTTPException(status_code=400, detail=f"Item name is required: {item_label_path}")

    item_key = _normalize_review_item_key(payload.item_key)
    if not item_key:
        item_key = _review_item_key_for_row(item, output_primary_key_path)
    if not item_key:
        item_key = f"custom-{ObjectId()}"
    _set_value_at_path(item, output_primary_key_path, item_key)

    fetched_rows = _review_row_map_for_data(data, output_primary_key_path)
    local_docs = await _load_local_review_items(integration_id)
    local_keys = {
        str(doc.get("item_key") or "").strip()
        for doc in local_docs
        if str(doc.get("item_key") or "").strip()
    }
    if item_key in fetched_rows or item_key in local_keys:
        raise HTTPException(status_code=409, detail="Review item key already exists")

    now = datetime.utcnow()
    await _local_items_coll().insert_one(
        {
            "integration_id": integration_id,
            "item_key": item_key,
            "item": item,
            "created_at": now,
            "updated_at": now,
        }
    )
    await _item_reviews_coll().update_one(
        {"integration_id": integration_id, "item_key": item_key},
        {
            "$set": {
                "integration_id": integration_id,
                "item_key": item_key,
                "state": "open",
                "tags": [],
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return await get_review_item(integration_id, item_key, _)


@router.get("/{integration_id}/review/item")
async def get_review_item(
    integration_id: str,
    item_key: str = Query(..., min_length=1),
    _=Depends(require_permission("admin:general")),
) -> dict[str, Any]:
    """Return side-by-side field review data for one integration item."""
    integration_doc = await _load_integration_doc_or_404(integration_id)
    data_doc = await _load_integration_data_doc_or_404(integration_id)
    output_primary_key_path = str(integration_doc.get("output_primary_key_path") or "").strip()
    normalized_item_key = str(item_key or "").strip()
    item_label_path = await _get_schema_item_label_path(integration_id, integration_doc=integration_doc)
    local_docs = await _load_local_review_items(integration_id)
    local_item_keys = {
        str(doc.get("item_key") or "").strip()
        for doc in local_docs
        if str(doc.get("item_key") or "").strip()
    }
    review_data = _combine_fetched_and_local_review_data(data_doc.get("data"), local_docs)
    current_rows = _review_row_map_for_data(
        review_data,
        output_primary_key_path,
        item_label_path,
        local_item_keys=local_item_keys,
    )
    previous_rows = _review_row_map_for_data(data_doc.get("previous_data"), output_primary_key_path, item_label_path)
    current_row = current_rows.get(normalized_item_key)
    previous_row = previous_rows.get(normalized_item_key)
    if current_row is None and previous_row is None:
        raise HTTPException(status_code=404, detail="Review item not found")

    current_item = current_row.get("item") if current_row else None
    previous_item = previous_row.get("item") if previous_row else None
    schema_response = await _get_schema_response_for_integration(
        integration_id,
        integration_doc=integration_doc,
    )
    schema_fields = {
        str(field.get("path") or "").strip(): field
        for field in schema_response.get("fields", [])
        if str(field.get("path") or "").strip()
    }
    schema_field_paths = set(schema_fields.keys())
    all_override_docs = [
        doc
        for doc in await _load_review_overrides(integration_id)
        if not _is_legacy_page_slug_path(doc.get("field_path"), schema_field_paths)
    ]
    override_docs = [
        doc
        for doc in all_override_docs
        if str(doc.get("item_key") or "").strip() == normalized_item_key
    ]
    overrides_by_path = {
        _normalize_review_field_path(doc.get("field_path")): doc
        for doc in override_docs
        if _normalize_review_field_path(doc.get("field_path"))
    }
    options = _normalize_integration_options(data_doc.get("options"))
    option_types = _normalize_integration_option_types(data_doc.get("option_types"), options)
    effective_review_data = _apply_review_overrides_to_data(
        review_data,
        output_primary_key_path,
        all_override_docs,
    )
    options, option_types = await _apply_schema_collected_options(
        integration_id,
        effective_review_data,
        options,
        option_types,
    )
    item_review_meta = _format_review_item_meta(
        (await _load_review_item_meta_map(integration_id)).get(normalized_item_key)
    )

    paths = set(schema_fields.keys())
    if current_item is not None:
        paths.update(_flatten_review_field_paths(current_item))
    if previous_item is not None:
        paths.update(_flatten_review_field_paths(previous_item))
    paths.update(overrides_by_path.keys())
    paths = {
        path
        for path in paths
        if not _is_legacy_page_slug_path(path, schema_field_paths)
    }

    effective_item = _effective_review_item_for_overrides(
        current_item,
        item_key=normalized_item_key,
        output_primary_key_path=output_primary_key_path,
        overrides=override_docs,
    )
    missing_required_paths = _missing_required_schema_paths(effective_item, schema_fields)
    missing_required_path_set = set(missing_required_paths)
    is_local_item = bool((current_row or {}).get("is_local_item", False))
    item_review_tags = _hide_generated_local_review_tags(
        item_review_meta["tags"],
        is_local_item=is_local_item,
    )
    item_page_template_refs = await _load_review_item_page_template_refs(integration_id)
    generated_pages_by_item = await _load_review_generated_pages_by_item(
        integration_id,
        [normalized_item_key],
        item_page_template_refs,
        item_page_sync_blocked=bool(integration_doc.get("item_page_sync_blocked", False)),
    )
    generated_pages = generated_pages_by_item.get(normalized_item_key, [])
    generated_page_summary = _summarize_review_generated_pages(generated_pages)

    fields: list[dict[str, Any]] = []
    has_previous_snapshot = data_doc.get("previous_fetched_at") is not None
    for path in sorted(path for path in paths if path):
        has_current, current_value = _review_value_from_item(current_item, path)
        has_previous, previous_value = _review_value_from_item(previous_item, path)
        override_doc = overrides_by_path.get(path)
        has_override = isinstance(override_doc, dict)
        local_value = override_doc.get("local_value") if has_override else None
        has_effective, effective_value = _review_value_from_item(effective_item, path)
        schema_field = schema_fields.get(path) or {}
        history = []
        if has_override:
            raw_history = override_doc.get("history")
            history = copy.deepcopy(raw_history[-5:] if isinstance(raw_history, list) else [])
        fields.append(
            {
                "path": path,
                "schema_type": schema_field.get("effective_type") or "undefined",
                "detected_type": schema_field.get("detected_type") or "undefined",
                "manual_type": schema_field.get("manual_type"),
                "collect_options": bool(schema_field.get("collect_options", False)),
                "options": (
                    copy.deepcopy(options.get(path, []))
                    if bool(schema_field.get("collect_options", False))
                    else []
                ),
                "option_type": (
                    option_types.get(path)
                    if bool(schema_field.get("collect_options", False))
                    else None
                ),
                "required": bool(schema_field.get("required", False)) if path in schema_fields else False,
                "missing_required": bool(path in missing_required_path_set),
                "has_current_value": has_current,
                "current_value": current_value,
                "has_previous_value": has_previous,
                "previous_value": previous_value,
                "source_changed": bool(
                    has_previous_snapshot
                    and (
                        has_current != has_previous
                        or _cache_review_value_token(current_value) != _cache_review_value_token(previous_value)
                    )
                ),
                "has_override": has_override,
                "local_value": local_value,
                "has_effective_value": has_effective,
                "effective_value": effective_value,
                "has_conflict": _is_review_override_conflicted(override_doc, current_item) if has_override else False,
                "override_updated_at": override_doc.get("updated_at") if has_override else None,
                "history": history,
            }
        )

    return {
        "integration_id": integration_id,
        "item_key": normalized_item_key,
        "label": (current_row or previous_row or {}).get("label") or normalized_item_key,
        "is_local_item": is_local_item,
        "is_incomplete": bool(missing_required_paths),
        "missing_required_paths": missing_required_paths,
        "state": item_review_meta["state"],
        "tags": item_review_tags,
        "review_updated_at": item_review_meta.get("updated_at"),
        "output_primary_key_path": output_primary_key_path or None,
        "page_slug_path": schema_response.get("page_slug_path"),
        "fetched_at": data_doc.get("fetched_at"),
        "previous_fetched_at": data_doc.get("previous_fetched_at"),
        "current_item": current_item,
        "previous_item": previous_item,
        "effective_item": effective_item,
        "item_page_template_count": len(item_page_template_refs),
        "item_page_templates_active": bool(item_page_template_refs),
        "item_page_sync_blocked": bool(integration_doc.get("item_page_sync_blocked", False)),
        "generated_pages": generated_pages,
        **generated_page_summary,
        "fields": fields,
        "options": copy.deepcopy(options),
        "option_types": copy.deepcopy(option_types),
    }


@router.patch("/{integration_id}/review/item/meta")
async def update_review_item_meta(
    integration_id: str,
    payload: IntegrationReviewItemMetaPatchRequest,
    _=Depends(require_permission("admin:general")),
) -> dict[str, Any]:
    """Create or update item-level review state and tags."""
    integration_doc = await _load_integration_doc_or_404(integration_id)
    data_doc = await _load_integration_data_doc_or_404(integration_id)
    output_primary_key_path = str(integration_doc.get("output_primary_key_path") or "").strip()
    normalized_item_key = str(payload.item_key or "").strip()
    if not normalized_item_key:
        raise HTTPException(status_code=400, detail="item_key is required")

    local_docs = await _load_local_review_items(integration_id)
    review_data = _combine_fetched_and_local_review_data(data_doc.get("data"), local_docs)
    current_rows = _review_row_map_for_data(review_data, output_primary_key_path)
    previous_rows = _review_row_map_for_data(data_doc.get("previous_data"), output_primary_key_path)
    if normalized_item_key not in current_rows and normalized_item_key not in previous_rows:
        raise HTTPException(status_code=404, detail="Review item not found")

    existing = await _item_reviews_coll().find_one(
        {"integration_id": integration_id, "item_key": normalized_item_key}
    )
    fields_set = getattr(payload, "model_fields_set", set())
    next_state = (
        _normalize_review_item_state(payload.state)
        if "state" in fields_set
        else _normalize_review_item_state(existing.get("state") if isinstance(existing, dict) else None)
    )
    next_tags = (
        _normalize_review_tags(payload.tags)
        if "tags" in fields_set
        else _normalize_review_tags(existing.get("tags") if isinstance(existing, dict) else [])
    )
    now = datetime.utcnow()
    await _item_reviews_coll().update_one(
        {"integration_id": integration_id, "item_key": normalized_item_key},
        {
            "$set": {
                "integration_id": integration_id,
                "item_key": normalized_item_key,
                "state": next_state,
                "tags": next_tags,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return await get_review_item(integration_id, normalized_item_key, _)


@router.patch("/{integration_id}/review/item")
async def update_review_item_override(
    integration_id: str,
    payload: IntegrationReviewItemPatchRequest,
    _=Depends(require_permission("admin:general")),
) -> dict[str, Any]:
    """Create or update one field-level local override for an integration item."""
    integration_doc = await _load_integration_doc_or_404(integration_id)
    data_doc = await _load_integration_data_doc_or_404(integration_id)
    normalized_item_key = str(payload.item_key or "").strip()
    field_path = _normalize_review_field_path(payload.field_path)
    if not normalized_item_key or not field_path or field_path == "$":
        raise HTTPException(status_code=400, detail="item_key and editable field_path are required")
    try:
        await upsert_integration_review_override(
            _db(),
            integration_id=integration_id,
            item_key=normalized_item_key,
            field_path=field_path,
            value=payload.value,
            integration_doc=integration_doc,
            data_doc=data_doc,
        )
    except IntegrationReviewError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    generated_page_sync = await sync_generated_item_pages_for_integration_review_change(
        _db(),
        integration_id=integration_id,
        item_key=normalized_item_key,
        field_paths={field_path},
    )
    detail = await get_review_item(integration_id, normalized_item_key, _)
    detail["generated_page_sync"] = generated_page_sync
    return detail


@router.delete("/{integration_id}/review/item/field")
async def delete_review_item_override(
    integration_id: str,
    item_key: str = Query(..., min_length=1),
    field_path: str = Query(..., min_length=1),
    _=Depends(require_permission("admin:general")),
) -> dict[str, Any]:
    """Clear one field-level local override."""
    await _load_integration_doc_or_404(integration_id)
    normalized_item_key = str(item_key or "").strip()
    normalized_field_path = _normalize_review_field_path(field_path)
    await _overrides_coll().delete_one(
        {
            "integration_id": integration_id,
            "item_key": normalized_item_key,
            "field_path": normalized_field_path,
        }
    )
    generated_page_sync = await sync_generated_item_pages_for_integration_review_change(
        _db(),
        integration_id=integration_id,
        item_key=normalized_item_key,
        field_paths={normalized_field_path},
    )
    detail = await get_review_item(integration_id, normalized_item_key, _)
    detail["generated_page_sync"] = generated_page_sync
    return detail


@router.get("/{integration_id}/schema")
async def get_integration_schema(
    integration_id: str,
    _=Depends(require_permission("admin:general")),
) -> dict[str, Any]:
    """Return detected/manual schema metadata for an integration."""
    integration_doc = await _load_integration_doc_or_404(integration_id)
    await _migrate_collect_distinct_steps_to_schema(integration_id, integration_doc, strip_from_doc=True)
    schema_doc = await _schemas_coll().find_one({"integration_id": integration_id})
    if not isinstance(schema_doc, dict):
        try:
            data_doc = await _load_integration_data_doc_or_404(integration_id)
            detected = _detect_integration_schema_fields(data_doc.get("data"))
        except HTTPException:
            detected = {}
        return _format_schema_response(
            integration_id,
            None,
            detected,
            output_primary_key_path=str(integration_doc.get("output_primary_key_path") or "").strip(),
        )
    return _format_schema_response(
        integration_id,
        schema_doc,
        output_primary_key_path=str(integration_doc.get("output_primary_key_path") or "").strip(),
    )


@router.post("/{integration_id}/schema/detect")
async def detect_integration_schema(
    integration_id: str,
    _=Depends(require_permission("admin:general")),
) -> dict[str, Any]:
    """Detect and persist integration field schema metadata from current fetched data."""
    integration_doc = await _load_integration_doc_or_404(integration_id)
    await _migrate_collect_distinct_steps_to_schema(integration_id, integration_doc, strip_from_doc=True)
    data_doc = await _load_integration_data_doc_or_404(integration_id)
    return await _persist_detected_schema_for_integration_data(
        integration_id,
        integration_doc,
        data_doc.get("data"),
    )


@router.patch("/{integration_id}/schema")
async def update_integration_schema(
    integration_id: str,
    payload: IntegrationSchemaUpdateRequest,
    _=Depends(require_permission("admin:general")),
) -> dict[str, Any]:
    """Update manual schema field types and option collection settings."""
    integration_doc = await _load_integration_doc_or_404(integration_id)
    await _migrate_collect_distinct_steps_to_schema(integration_id, integration_doc, strip_from_doc=True)
    existing = await _schemas_coll().find_one({"integration_id": integration_id})
    if isinstance(existing, dict):
        detected_fields = existing.get("detected_fields") if isinstance(existing.get("detected_fields"), dict) else {}
        manual_types = _normalize_manual_schema_types(existing.get("manual_types"))
        collect_options = _normalize_schema_collect_options(existing.get("collect_options"))
        cache_media = _normalize_schema_cache_media(existing.get("cache_media"))
        required_fields = _normalize_schema_required_fields(existing.get("required_fields"))
    else:
        try:
            data_doc = await _load_integration_data_doc_or_404(integration_id)
            detected_fields = _detect_integration_schema_fields(data_doc.get("data"))
        except HTTPException:
            detected_fields = {}
        manual_types = {}
        collect_options = {}
        cache_media = {}
        required_fields = {}

    for raw_path, raw_type in payload.manual_types.items():
        path = _normalize_review_field_path(raw_path)
        if not path:
            continue
        if raw_type is None:
            manual_types.pop(path, None)
            continue
        value = str(raw_type or "").strip().lower()
        if value in REVIEW_SCHEMA_FIELD_TYPES:
            manual_types[path] = value  # type: ignore[assignment]

    removed_collect_option_paths: list[str] = []
    for raw_path, enabled in payload.collect_options.items():
        path = _normalize_review_field_path(raw_path)
        if not path:
            continue
        if enabled is None:
            collect_options.pop(path, None)
            removed_collect_option_paths.append(path)
        else:
            collect_options[path] = bool(enabled)
            if not enabled:
                removed_collect_option_paths.append(path)

    for raw_path, enabled in payload.cache_media.items():
        path = _normalize_review_field_path(raw_path)
        if not path:
            continue
        if enabled is None:
            cache_media.pop(path, None)
        else:
            cache_media[path] = bool(enabled)

    for raw_path, required in payload.required_fields.items():
        path = _normalize_review_field_path(raw_path)
        if not path:
            continue
        if required is None:
            required_fields.pop(path, None)
        else:
            required_fields[path] = bool(required)

    item_label_path = existing.get("item_label_path") if isinstance(existing, dict) else None
    if "item_label_path" in getattr(payload, "model_fields_set", set()):
        item_label_path = _normalize_review_field_path(payload.item_label_path)

    page_slug_path = existing.get("page_slug_path") if isinstance(existing, dict) else None
    if "page_slug_path" in getattr(payload, "model_fields_set", set()):
        page_slug_path = _normalize_review_field_path(payload.page_slug_path)
        latest_return_type = str(integration_doc.get("return_type") or "").strip().lower()
        if not latest_return_type:
            try:
                data_doc_for_return_type = await _load_integration_data_doc_or_404(integration_id)
                latest_return_type = _derive_return_type_from_data(data_doc_for_return_type.get("data"))
            except HTTPException:
                latest_return_type = "unknown"
        if page_slug_path and latest_return_type not in {"list", "unknown"}:
            raise HTTPException(status_code=400, detail="Page Slug can only be set for list integrations")

    output_primary_key_path = str(integration_doc.get("output_primary_key_path") or "").strip()
    if "output_primary_key_path" in getattr(payload, "model_fields_set", set()):
        output_primary_key_path = _normalize_review_field_path(payload.output_primary_key_path)
        latest_return_type = str(integration_doc.get("return_type") or "").strip().lower()
        if not latest_return_type:
            try:
                data_doc_for_return_type = await _load_integration_data_doc_or_404(integration_id)
                latest_return_type = _derive_return_type_from_data(data_doc_for_return_type.get("data"))
            except HTTPException:
                latest_return_type = "unknown"
        if output_primary_key_path and latest_return_type not in {"list", "unknown"}:
            raise HTTPException(status_code=400, detail="ID can only be set for list integrations")

    schema_preview = _format_schema_response(
        integration_id,
        {
            "detected_fields": detected_fields,
            "manual_types": manual_types,
            "collect_options": collect_options,
            "cache_media": cache_media,
            "required_fields": required_fields,
            "item_label_path": item_label_path,
            "page_slug_path": page_slug_path,
        },
        output_primary_key_path=output_primary_key_path,
    )
    item_label_path = schema_preview.get("item_label_path")
    page_slug_path = schema_preview.get("page_slug_path")
    output_primary_key_path = str(schema_preview.get("output_primary_key_path") or "").strip()

    now = datetime.utcnow()
    await _schemas_coll().update_one(
        {"integration_id": integration_id},
        {
            "$set": {
                "integration_id": integration_id,
                "detected_fields": detected_fields,
                "manual_types": manual_types,
                "collect_options": collect_options,
                "cache_media": cache_media,
                "required_fields": required_fields,
                "item_label_path": item_label_path,
                "page_slug_path": page_slug_path,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now, "detected_at": now},
        },
        upsert=True,
    )
    if "output_primary_key_path" in getattr(payload, "model_fields_set", set()):
        await _integrations_coll().update_one(
            {"_id": integration_doc.get("_id")},
            {
                "$set": {
                    "output_primary_key_path": output_primary_key_path or None,
                    "updated_at": now,
                }
            },
        )
        integration_doc["output_primary_key_path"] = output_primary_key_path or None
    if removed_collect_option_paths:
        await _remove_integration_metadata_option_paths(integration_id, removed_collect_option_paths)
    schema_doc = await _schemas_coll().find_one({"integration_id": integration_id})
    return _format_schema_response(
        integration_id,
        schema_doc,
        output_primary_key_path=str(integration_doc.get("output_primary_key_path") or "").strip(),
    )


@router.post("/{integration_id}/media/cache")
async def cache_integration_schema_media(
    integration_id: str,
    _=Depends(require_permission("admin:general")),
) -> IntegrationMediaCacheResponse:
    """Cache media for schema image fields enabled for integration-level media caching."""
    integration_doc = await _load_integration_doc_or_404(integration_id)
    data_doc = await _load_integration_data_doc_or_404(integration_id)
    data_coll = _data_coll()

    localized_data, media_entries, media_stats = await _cache_schema_media_for_integration_data(
        integration_id,
        copy.deepcopy(data_doc.get("data")),
        integration_doc=integration_doc,
        base_media_entries=copy.deepcopy(data_doc.get("media_entries") or []),
        import_missing_now=True,
    )
    options = _normalize_integration_options(data_doc.get("options"))
    option_types = _normalize_integration_option_types(data_doc.get("option_types"), options)
    options, option_types = await _apply_schema_collected_options(
        integration_id,
        localized_data,
        options,
        option_types,
    )
    await data_coll.update_one(
        {"_id": data_doc.get("_id")},
        {
            "$set": {
                "data": localized_data,
                "data_hash": _cache_hash_payload(localized_data),
                "options": copy.deepcopy(options),
                "option_types": copy.deepcopy(option_types),
                "media_entries": copy.deepcopy(media_entries),
                "updated_at": datetime.utcnow(),
            }
        },
    )
    return IntegrationMediaCacheResponse(
        integration_id=integration_id,
        fetched_at=data_doc.get("fetched_at"),
        has_media_urls=media_stats.get("media_url_count", 0) > 0,
        media_url_count=int(media_stats.get("media_url_count") or 0),
        media_items_imported=int(media_stats.get("media_items_imported") or 0),
        media_items_reused=int(media_stats.get("media_items_reused") or 0),
        media_items_queued=int(media_stats.get("media_items_queued") or 0),
        media_items_localized_now=int(media_stats.get("media_items_localized_now") or 0),
        media_items_fallback_raw=int(media_stats.get("media_items_fallback_raw") or 0),
        media_items_total=int(media_stats.get("media_items_total") or 0),
        media_entries=copy.deepcopy(media_entries),
        data=localized_data,
        options=copy.deepcopy(options),
        option_types=copy.deepcopy(option_types),
    )


# -------------------------
# Section Integration Cache
# -------------------------


async def _execute_section_media_import(
    *,
    section_id: str,
    section_type: str,
    integration_id: str,
    mapping_storage_key: str,
    mapped_source_paths: list[str] | None,
    enable_metadata_extraction_tagging: bool,
) -> SectionIntegrationMediaImportResponse:
    section_id = str(section_id or "").strip()
    if not section_id:
        raise HTTPException(status_code=400, detail="section_id is required")

    integration_id = str(integration_id or "").strip()
    if not integration_id:
        raise HTTPException(status_code=400, detail="integration_id is required")

    mapping_storage_key = str(mapping_storage_key or "").strip() or "sectionIntegrationMapping"
    section_type = _normalize_section_type_value(section_type, default="text")
    normalized_mapped_source_paths = (
        _normalize_mapped_source_paths(mapped_source_paths)
        if mapped_source_paths is not None
        else None
    )

    coll = _integrations_coll()

    try:
        integration_oid = ObjectId(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

    integration_doc = await coll.find_one({"_id": integration_oid})
    if not integration_doc:
        raise HTTPException(status_code=404, detail="Integration not found")

    _integration_doc, data_doc, transformed_data, options, option_types = await _get_effective_integration_data_doc(
        integration_id,
        integration_doc=integration_doc,
    )
    if transformed_data is None:
        raise HTTPException(status_code=404, detail="No cached integration data available for media import")

    (
        localized_data,
        media_entries,
        media_items_imported,
        media_items_reused,
        media_items_queued,
        media_items_localized_now,
        media_items_fallback_raw,
    ) = await _localize_media_links_for_cached_payload(
        transformed_data,
        section_type=section_type,
        enable_metadata_extraction_tagging=bool(enable_metadata_extraction_tagging),
        mapped_source_paths=normalized_mapped_source_paths,
    )
    media_url_count = _media_url_count(
        transformed_data,
        mapped_source_paths=normalized_mapped_source_paths,
    )
    source_etag = await _fetch_integration_source_etag(integration_doc)

    return SectionIntegrationMediaImportResponse(
        section_id=section_id,
        section_type=section_type,
        integration_id=integration_id,
        integration_name=str(integration_doc.get("name") or integration_id),
        mapping_storage_key=mapping_storage_key,
        fetched_at=data_doc.get("fetched_at"),
        source_etag=source_etag,
        has_media_urls=media_url_count > 0,
        media_url_count=media_url_count,
        media_items_imported=media_items_imported,
        media_items_reused=media_items_reused,
        media_items_queued=media_items_queued,
        media_items_localized_now=media_items_localized_now,
        media_items_fallback_raw=media_items_fallback_raw,
        media_items_total=len(media_entries),
        media_entries=media_entries,
        original_data=transformed_data,
        localized_data=localized_data,
        options=options,
        option_types=option_types,
    )


@router.get("/{integration_id}/media-importability")
async def get_media_importability(
    integration_id: str,
    _=Depends(require_permission("admin:design")),
) -> SectionIntegrationMediaImportabilityResponse:
    """Return whether the latest transformed integration payload contains media URLs."""
    try:
        integration_oid = ObjectId(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid integration ID") from exc

    integration_doc = await _integrations_coll().find_one({"_id": integration_oid}, {"_id": 1})
    if not isinstance(integration_doc, dict):
        raise HTTPException(status_code=404, detail="Integration not found")

    try:
        integration_doc, data_doc, transformed_data, _options, _option_types = await _get_effective_integration_data_doc(
            integration_id,
        )
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        return SectionIntegrationMediaImportabilityResponse(
            integration_id=integration_id,
            has_media_urls=False,
            media_url_count=0,
            fetched_at=None,
        )
    if transformed_data is None:
        return SectionIntegrationMediaImportabilityResponse(
            integration_id=integration_id,
            has_media_urls=False,
            media_url_count=0,
            fetched_at=None,
        )

    media_count = _media_url_count(transformed_data)
    return SectionIntegrationMediaImportabilityResponse(
        integration_id=integration_id,
        has_media_urls=media_count > 0,
        media_url_count=media_count,
        fetched_at=data_doc.get("fetched_at"),
    )


@router.post("/section-media/import")
async def import_section_integration_media(
    payload: SectionIntegrationMediaImportRequest,
    _=Depends(require_permission("admin:design")),
) -> SectionIntegrationMediaImportResponse:
    """Localize/import media URLs from latest transformed integration payload (no upstream refetch)."""
    return await _execute_section_media_import(
        section_id=payload.section_id,
        section_type=payload.section_type,
        integration_id=payload.integration_id,
        mapping_storage_key=payload.mapping_storage_key,
        mapped_source_paths=payload.mapped_source_paths,
        enable_metadata_extraction_tagging=payload.enable_metadata_extraction_tagging,
    )


@router.get("/section-cache/latest")
async def get_latest_section_integration_cache(
    section_id: str = Query(..., description="Section id or builder section id"),
    integration_id: str = Query(..., description="Integration id"),
    mapping_storage_key: str = Query(
        default="sectionIntegrationMapping",
        description="Mapping storage key used by the section importer",
    ),
    _=Depends(require_permission("admin:design")),
) -> SectionIntegrationCacheResponse:
    """Return latest persisted section integration cache entry for the requested section/integration mapping scope."""
    normalized_section_id = str(section_id or "").strip()
    normalized_integration_id = str(integration_id or "").strip()
    normalized_mapping_storage_key = str(mapping_storage_key or "").strip() or "sectionIntegrationMapping"
    if not normalized_section_id or not normalized_integration_id:
        raise HTTPException(status_code=400, detail="section_id and integration_id are required")

    cache_doc = await _section_cache_coll().find_one(
        {
            "section_id": normalized_section_id,
            "integration_id": normalized_integration_id,
            "mapping_storage_key": normalized_mapping_storage_key,
        },
        sort=[("created_at", -1)],
    )
    if not isinstance(cache_doc, dict):
        raise HTTPException(status_code=404, detail="No section integration cache entry found")
    return _format_section_cache_response(cache_doc)


# -------------------------
# List integrations for sections
# -------------------------


@router.get("/for-section/{section_type}")
async def list_integrations_for_section(
    section_type: str,
    section_id: str | None = Query(default=None, description="Optional section instance id"),
    item_page_template_path: str | None = Query(
        default=None,
        description="Optional item-page template path for mapping-editor context",
    ),
    source_route_ref: str | None = Query(
        default=None,
        description="Optional shared source-route reference for item-page template context",
    ),
    source_section_id: str | None = Query(
        default=None,
        description="Optional source section instance id for item-page template context",
    ),
    source_integrations_only: bool = Query(
        default=False,
        description="When true, restrict item-page template integrations to those used by the selected source route's section template",
    ),
    _=Depends(require_permission("admin:design")),
) -> IntegrationsForSectionResponse:
    """List integrations for section imports with context-aware template rule filtering."""
    normalized_section_type = _normalize_section_type_value(section_type)
    coll = _integrations_coll()
    data_coll = _data_coll()
    config_doc = await _settings_coll().find_one({"key": INTEGRATIONS_CONNECTION_CONFIG_KEY})

    exposed_integration_ids: list[str] = []
    template_integration_rules: dict[str, dict[str, Any]] = {}
    if isinstance(config_doc, dict):
        exposed_integration_ids = _normalize_integration_id_list(
            config_doc.get("exposed_integration_ids"),
        )
        template_integration_rules = _normalize_template_integration_rules(
            config_doc.get("template_integration_rules"),
        )

    template_key = await _resolve_template_rule_key(
        normalized_section_type,
        section_id,
        item_page_template_path=item_page_template_path,
    )
    resolved_rule = _resolve_template_rule(template_integration_rules, template_key)
    integration_visibility = _normalize_integration_visibility(
        resolved_rule.get("integration_visibility"),
        default=_default_template_integration_visibility(template_key),
    )
    is_template_context = _is_template_integration_context(
        section_id,
        item_page_template_path=item_page_template_path,
    )
    integrations_enabled = integration_visibility == "enabled" or (
        integration_visibility == "template_only" and is_template_context
    )
    context = IntegrationsForSectionContextResponse(
        template_key=template_key,
        integration_visibility=integration_visibility or "enabled",
        integrations_enabled=integrations_enabled,
        expected_return_type=_normalize_expected_return_type(
            resolved_rule.get("expected_return_type"),
        ),
    )

    if not context.integrations_enabled or not exposed_integration_ids:
        return IntegrationsForSectionResponse(integrations=[], context=context)

    allowed_integration_ids = set(exposed_integration_ids)
    resolved_source_route_ref = await _resolve_source_route_ref_for_item_page_context(
        explicit_source_route_ref=source_route_ref,
        item_page_template_path=item_page_template_path,
    )
    if source_integrations_only:
        if source_section_id:
            source_kind = await _resolve_template_source_kind_for_item_page_context(
                item_page_template_path,
            )
            source_used_integration_ids = await _resolve_source_used_integration_ids_from_section(
                source_section_id,
                source_kind=source_kind,
            )
        else:
            source_used_integration_ids = await _resolve_source_used_integration_ids(
                resolved_source_route_ref,
            )
        if not source_used_integration_ids:
            return IntegrationsForSectionResponse(integrations=[], context=context)
        allowed_integration_ids &= source_used_integration_ids
        if not allowed_integration_ids:
            return IntegrationsForSectionResponse(integrations=[], context=context)

    integrations = []
    async for doc in coll.find().sort("name", 1):
        doc_id = str(doc["_id"])
        if doc_id not in allowed_integration_ids:
            continue
        data_doc = await data_coll.find_one(
            {"integration_id": doc_id},
            sort=[("fetched_at", -1)],
        )
        formatted = _format_integration(doc, data_doc)
        expected_return_type = context.expected_return_type
        if expected_return_type in {"list", "object"}:
            if str(formatted.get("return_type") or "unknown") != expected_return_type:
                continue
        integrations.append(formatted)

    return IntegrationsForSectionResponse(integrations=integrations, context=context)
