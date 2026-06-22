"""Program shared catalog API (global gigs + stages)."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from app.case_utils import ensure_snake_case_keys
from app.db import get_client
from app.deps import get_current_user, require_permission
from app.item_page_jobs import enqueue_program_item_page_generation
from app.media_responsive import (
    build_asset_responsive_variants,
    merge_media_variant_entries,
    normalize_media_variant_entries,
)
from app.models.sections.common import BilingualText
from app.models.sections.sections import ProgramGig, ProgramStage
from app import program_catalog
from app.public_cache import (
    get_or_set_ttl_cache,
    get_ttl_cache,
    set_public_cache_headers,
)
from app.routers.v1.pages import get_page_with_sections
from app.revisioning import (
    apply_program_shared_content,
    capture_program_shared_content,
    normalize_program_shared_content_snapshot,
    push_program_shared_content_revisions,
    sanitize_program_shared_content_for_revision,
    snapshots_equal,
)
from app.security import KeycloakUser
from app.settings import settings
from app.template_sync import (
    build_program_item_page_source_hashes_for_freshness,
    build_program_stage_titles_lookup,
    cleanup_generated_item_page_for_source,
    get_generated_item_page_template_freshness_map,
    normalize_program_stage_lookup_key,
    resolve_active_item_page_template,
)

router = APIRouter(prefix="/program", tags=["program"])

PUBLIC_PROGRAM_FEED_CACHE_SECONDS = 15
PROGRAM_GENERATION_COMPARE_IGNORED_KEYS = {
    "__integration_source_id",
    "page_slug",
    "item_url",
}

logger = logging.getLogger(__name__)


def _db():
    return get_client()[settings.mongo_db]


async def _enrich_program_snapshot_with_asset_media(db, snapshot: dict) -> dict:
    normalized = normalize_program_shared_content_snapshot(snapshot)
    gigs = normalized.get("gigs") if isinstance(normalized.get("gigs"), list) else []
    stages = normalized.get("stages") if isinstance(normalized.get("stages"), list) else []
    gig_image_urls = sorted(
        {
            str(gig.get("image_url") or "").strip()
            for gig in gigs
            if isinstance(gig, dict) and str(gig.get("image_url") or "").strip()
        }
    )
    stage_image_urls = sorted(
        {
            str(stage.get("image_url") or "").strip()
            for stage in stages
            if isinstance(stage, dict) and str(stage.get("image_url") or "").strip()
        }
    )
    all_image_urls = sorted(set([*gig_image_urls, *stage_image_urls]))
    if not all_image_urls:
        return normalized

    assets_coll = db["assets"]
    asset_docs_by_url: dict[str, dict[str, Any]] = {}
    async for asset_doc in assets_coll.find(
        {"url": {"$in": all_image_urls}},
        {"url": 1, "variants": 1},
    ):
        if not isinstance(asset_doc, dict):
            continue
        asset_url = str(asset_doc.get("url") or "").strip()
        if not asset_url:
            continue
        asset_docs_by_url[asset_url] = asset_doc

    if not asset_docs_by_url:
        return normalized

    for gig in gigs:
        if not isinstance(gig, dict):
            continue
        gig_image_url = str(gig.get("image_url") or "").strip()
        if not gig_image_url:
            continue
        asset_doc = asset_docs_by_url.get(gig_image_url)
        if not isinstance(asset_doc, dict):
            continue

        existing_variants = normalize_media_variant_entries(gig.get("image_responsive_variants"))
        imported_variants = build_asset_responsive_variants(asset_doc.get("variants"))
        merged_variants = merge_media_variant_entries(existing_variants, imported_variants)
        gig["image_responsive_variants"] = merged_variants

    for stage in stages:
        if not isinstance(stage, dict):
            continue
        stage_image_url = str(stage.get("image_url") or "").strip()
        if not stage_image_url:
            continue
        asset_doc = asset_docs_by_url.get(stage_image_url)
        if not isinstance(asset_doc, dict):
            continue

        existing_variants = normalize_media_variant_entries(stage.get("image_responsive_variants"))
        imported_variants = build_asset_responsive_variants(asset_doc.get("variants"))
        merged_variants = merge_media_variant_entries(existing_variants, imported_variants)
        stage["image_responsive_variants"] = merged_variants

    return normalized


def _normalize_program_integration_state_value(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _resolve_program_integration_state(
    snapshot: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    source = snapshot if isinstance(snapshot, dict) else {}
    return {
        "program_stages_integration_mapping": _normalize_program_integration_state_value(
            source.get("program_stages_integration_mapping")
        ),
        "program_stages_integration_mapping_cache_state": _normalize_program_integration_state_value(
            source.get("program_stages_integration_mapping_cache_state")
        ),
        "program_gigs_integration_mapping": _normalize_program_integration_state_value(
            source.get("program_gigs_integration_mapping")
        ),
        "program_gigs_integration_mapping_cache_state": _normalize_program_integration_state_value(
            source.get("program_gigs_integration_mapping_cache_state")
        ),
    }


def _normalize_public_page_slug(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw or raw == "/":
        return "landing"
    normalized = raw.split("?", 1)[0].split("#", 1)[0].strip()
    normalized = normalized.replace("\\", "/").strip("/")
    return normalized or "landing"


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_program_datetime_text(value: Any) -> str:
    parsed = _parse_program_datetime(value)
    if not parsed:
        return ""
    return parsed.strftime("%Y-%m-%dT%H:%M")


def _parse_program_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = raw.replace(" ", "T")
    if len(candidate) >= 16:
        candidate = candidate[:16]
    try:
        return datetime.strptime(candidate, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def _extract_program_date_part(value: Any) -> str:
    normalized = _normalize_program_datetime_text(value)
    return normalized[:10] if normalized else ""


def _extract_program_time_part(value: Any) -> str:
    normalized = _normalize_program_datetime_text(value)
    return normalized[11:16] if normalized else ""


def _compose_program_datetime(day_value: Any, time_value: Any) -> str:
    day = str(day_value or "").strip()
    time = str(time_value or "").strip()
    if not day or not time:
        return ""
    try:
        datetime.strptime(f"{day}T{time}", "%Y-%m-%dT%H:%M")
    except ValueError:
        return ""
    return f"{day}T{time}"


def _subtract_days(day_value: str, days: int) -> str:
    try:
        parsed = datetime.strptime(day_value, "%Y-%m-%d")
    except ValueError:
        return day_value
    return (parsed - timedelta(days=days)).strftime("%Y-%m-%d")


def _normalize_stage_lookup_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value).strip()
    if isinstance(value, list):
        for entry in value:
            normalized = _normalize_stage_lookup_text(entry)
            if normalized:
                return normalized
        return ""
    if isinstance(value, dict):
        raw_id = value.get("id")
        if isinstance(raw_id, (str, int, float, bool)):
            normalized = str(raw_id).strip()
            if normalized:
                return normalized
        raw_option = value.get("value")
        if isinstance(raw_option, (str, int, float, bool)):
            normalized = str(raw_option).strip()
            if normalized:
                return normalized
        raw_name = value.get("name")
        if isinstance(raw_name, (str, int, float, bool)):
            normalized = str(raw_name).strip()
            if normalized:
                return normalized
        if isinstance(raw_name, dict):
            normalized = _normalize_stage_lookup_text(raw_name)
            if normalized:
                return normalized
        raw_title = value.get("title")
        if isinstance(raw_title, (str, int, float, bool)):
            normalized = str(raw_title).strip()
            if normalized:
                return normalized
        raw_label = value.get("label")
        if isinstance(raw_label, (str, int, float, bool)):
            normalized = str(raw_label).strip()
            if normalized:
                return normalized
        raw_stage = value.get("stage")
        if isinstance(raw_stage, dict):
            normalized = _normalize_stage_lookup_text(raw_stage)
            if normalized:
                return normalized
        if isinstance(raw_stage, (str, int, float, bool)):
            normalized = str(raw_stage).strip()
            if normalized:
                return normalized
        if "de" in value or "en" in value:
            return str(value.get("de") or value.get("en") or "").strip()
    return str(value).strip()


def _resolve_program_gig_range(gig: dict[str, Any]) -> tuple[datetime, datetime] | None:
    start_value = (
        gig.get("start")
        or _compose_program_datetime(gig.get("day"), gig.get("start_time"))
    )
    start = _parse_program_datetime(start_value)
    end_value = (
        gig.get("end")
        or _compose_program_datetime(
            _extract_program_date_part(gig.get("start")) or gig.get("day"),
            gig.get("end_time"),
        )
    )
    end = _parse_program_datetime(end_value)
    if not start or not end:
        return None
    normalized_end = end
    if normalized_end <= start:
        normalized_end = normalized_end + timedelta(days=1)
    return start, normalized_end


def _program_gig_sort_key(gig: dict[str, Any]) -> tuple[int, datetime, str]:
    date_range = _resolve_program_gig_range(gig)
    gig_id = str(gig.get("id") or "").strip()
    if not date_range:
        return (1, datetime.max, gig_id)
    return (0, date_range[0], gig_id)


def _resolve_program_logical_day(
    gig: dict[str, Any],
    *,
    day_start_hour: int,
    day_end_hour: int,
) -> str:
    gig_day = _extract_program_date_part(gig.get("start")) or str(gig.get("day") or "").strip()
    gig_start_time = _extract_program_time_part(gig.get("start")) or str(gig.get("start_time") or "").strip()
    if not gig_day or not gig_start_time:
        return gig_day

    try:
        gig_hour = int(gig_start_time.split(":", 1)[0])
    except ValueError:
        return gig_day

    effective_end_hour = day_end_hour - 24 if day_end_hour > 24 else day_end_hour
    day_wraps = day_end_hour > 24 or day_end_hour <= day_start_hour

    if day_wraps:
        if gig_hour < effective_end_hour:
            return _subtract_days(gig_day, 1)
        if gig_hour < day_start_hour and gig_hour >= effective_end_hour:
            return gig_day
    elif gig_hour < day_start_hour and day_start_hour > 0:
        return _subtract_days(gig_day, 1)

    return gig_day


def _resolve_program_previous_day(gig: dict[str, Any], current_day: str) -> str:
    previous_day = str(gig.get("previous_day") or "").strip()
    if previous_day:
        return previous_day
    if current_day:
        return current_day
    return str(gig.get("day") or "").strip()


def _has_program_gig_time_change(gig: dict[str, Any]) -> bool:
    current_start = _normalize_program_datetime_text(
        gig.get("start")
        or _compose_program_datetime(gig.get("day"), gig.get("start_time"))
    )
    current_day = _extract_program_date_part(current_start)
    current_end = _normalize_program_datetime_text(
        gig.get("end")
        or _compose_program_datetime(current_day or gig.get("day"), gig.get("end_time"))
    )

    previous_day = _resolve_program_previous_day(gig, current_day)
    previous_start = _normalize_program_datetime_text(
        gig.get("previous_start")
        or _compose_program_datetime(previous_day, gig.get("previous_start_time"))
    )
    previous_end = _normalize_program_datetime_text(
        gig.get("previous_end")
        or _compose_program_datetime(previous_day, gig.get("previous_end_time"))
    )
    previous_day_from_start = _extract_program_date_part(previous_start)

    return bool(
        (previous_day_from_start and previous_day_from_start != current_day)
        or (previous_start and previous_start != current_start)
        or (previous_end and previous_end != current_end)
    )


def _has_program_gig_stage_change(gig: dict[str, Any]) -> bool:
    previous_stage = _normalize_stage_lookup_text(gig.get("previous_stage"))
    current_stage = _normalize_stage_lookup_text(gig.get("stage"))
    return bool(previous_stage and previous_stage != current_stage)


def _is_program_gig_changed(gig: dict[str, Any]) -> bool:
    if not bool(gig.get("register_changes")):
        return False
    if bool(gig.get("canceled")):
        return True
    if _has_program_gig_time_change(gig):
        return True
    if _has_program_gig_stage_change(gig):
        return True
    return bool(gig.get("highlight_changes"))


def _serialize_public_value(value: Any) -> Any:
    if isinstance(value, BilingualText):
        return {
            "de": str(value.de or ""),
            "en": str(value.en or ""),
        }
    if isinstance(value, (dict, list)):
        return deepcopy(value)
    return value


def _project_public_gig_payload(gig: dict[str, Any]) -> dict[str, Any]:
    start_value = _normalize_program_datetime_text(
        gig.get("start")
        or _compose_program_datetime(gig.get("day"), gig.get("start_time"))
    )
    current_day = _extract_program_date_part(start_value)
    end_value = _normalize_program_datetime_text(
        gig.get("end")
        or _compose_program_datetime(current_day or gig.get("day"), gig.get("end_time"))
    )
    previous_day = _resolve_program_previous_day(gig, current_day)
    previous_start_value = _normalize_program_datetime_text(
        gig.get("previous_start")
        or _compose_program_datetime(previous_day, gig.get("previous_start_time"))
    )
    previous_end_value = _normalize_program_datetime_text(
        gig.get("previous_end")
        or _compose_program_datetime(previous_day, gig.get("previous_end_time"))
    )
    title_source = gig.get("title")
    if title_source is None or title_source == "":
        title_source = gig.get("artist_name")

    return {
        "start": start_value,
        "end": end_value,
        "stage": _normalize_stage_lookup_text(gig.get("stage")),
        "gig_type": str(gig.get("gig_type") or ""),
        "genre": _serialize_public_value(gig.get("genre")),
        "genre_selection": _serialize_public_value(gig.get("genre_selection")),
        "previous_start": previous_start_value,
        "previous_end": previous_end_value,
        "item_url": str(gig.get("item_url") or ""),
        "title": _serialize_public_value(title_source),
        "duration": _serialize_public_value(gig.get("duration")),
        "genre_custom": _serialize_public_value(gig.get("genre_custom")),
        "previous_stage": _normalize_stage_lookup_text(gig.get("previous_stage")),
        "register_changes": bool(gig.get("register_changes")),
        "canceled": bool(gig.get("canceled")),
    }


def _build_public_changes_payload(
    *,
    gigs: list[dict[str, Any]],
    stages: list[dict[str, Any]],
    day_start_hour: int,
    day_end_hour: int,
) -> list[dict[str, Any]]:
    del stages  # Group labels are not part of the public feed contract.

    sortable_rows: list[tuple[str, str, tuple[int, datetime, str], dict[str, Any]]] = []
    for gig in gigs:
        if not isinstance(gig, dict):
            continue
        if not _is_program_gig_changed(gig):
            continue

        logical_day = (
            _resolve_program_logical_day(
                gig,
                day_start_hour=day_start_hour,
                day_end_hour=day_end_hour,
            )
            or str(gig.get("day") or "").strip()
            or "unknown"
        )
        stage_key = _normalize_stage_lookup_text(gig.get("stage"))
        sortable_rows.append(
            (
                logical_day,
                stage_key,
                _program_gig_sort_key(gig),
                _project_public_gig_payload(gig),
            )
        )

    sortable_rows.sort(key=lambda row: (row[0], row[1], row[2]))
    return [row[3] for row in sortable_rows]


def _build_public_now_playing_payload(
    *,
    gigs: list[dict[str, Any]],
    stages: list[dict[str, Any]],
    now_local: datetime,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        stage_id = str(stage.get("id") or "").strip()
        stage_key = normalize_program_stage_lookup_key(stage_id)
        stage_gigs = [
            gig
            for gig in gigs
            if isinstance(gig, dict)
            and not bool(gig.get("canceled"))
            and (
                _normalize_stage_lookup_text(gig.get("stage")) == stage_id
                or (
                    bool(stage_key)
                    and normalize_program_stage_lookup_key(gig.get("stage")) == stage_key
                )
            )
        ]
        stage_gigs.sort(key=_program_gig_sort_key)

        current_gig: dict[str, Any] | None = None
        next_gig: dict[str, Any] | None = None
        for gig in stage_gigs:
            date_range = _resolve_program_gig_range(gig)
            if not date_range:
                continue
            start, end = date_range
            if start <= now_local < end:
                current_gig = _project_public_gig_payload(gig)
            elif start > now_local and next_gig is None:
                next_gig = _project_public_gig_payload(gig)

        result.append(
            {
                "stage": _serialize_public_value(stage.get("name")),
                "description": _serialize_public_value(stage.get("description")),
                "item_url": str(stage.get("item_url") or ""),
                "current": current_gig,
                "next": next_gig,
            }
        )
    return result


def _section_type_data(section: dict[str, Any]) -> dict[str, Any]:
    payload = section.get("type_data")
    return payload if isinstance(payload, dict) else {}


def _section_value(
    section: dict[str, Any],
    *,
    snake_key: str,
    camel_key: str | None = None,
    default: Any = None,
) -> Any:
    type_data = _section_type_data(section)
    if snake_key in type_data:
        return type_data.get(snake_key)
    if camel_key and camel_key in type_data:
        return type_data.get(camel_key)
    if snake_key in section:
        return section.get(snake_key)
    if camel_key and camel_key in section:
        return section.get(camel_key)
    return default


def _resolve_ticker_view_mode(section: dict[str, Any]) -> str:
    raw = str(
        _section_value(
            section,
            snake_key="view_mode",
            camel_key="viewMode",
            default="ticker",
        )
        or ""
    ).strip().lower()
    return "updates" if raw == "updates" else "ticker"


def _parse_update_timestamp(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = raw.replace(" ", "T")
    if len(candidate) == 16:
        candidate = f"{candidate}:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _normalize_ticker_update_items(items: Any) -> list[dict[str, Any]]:
    source = items if isinstance(items, list) else []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(source):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or f"update-{index + 1}").strip() or f"update-{index + 1}"
        raw_text = item.get("text")
        if isinstance(raw_text, dict):
            text_payload = {
                "de": str(raw_text.get("de") or ""),
                "en": str(raw_text.get("en") or ""),
            }
        else:
            mirrored = str(raw_text or "")
            text_payload = {"de": mirrored, "en": mirrored}
        normalized.append(
            {
                "id": item_id,
                "timestamp": str(item.get("timestamp") or "").strip(),
                "text": text_payload,
            }
        )

    normalized.sort(
        key=lambda entry: _parse_update_timestamp(entry.get("timestamp")) or datetime.min,
        reverse=True,
    )
    return normalized[:5]


def _has_ticker_update_item_content(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if str(item.get("timestamp") or "").strip():
        return True
    raw_text = item.get("text")
    if isinstance(raw_text, dict):
        return bool(
            str(raw_text.get("de") or "").strip()
            or str(raw_text.get("en") or "").strip()
        )
    return bool(str(raw_text or "").strip())


def _resolve_ticker_payload_from_sections(
    sections: list[dict[str, Any]],
) -> dict[str, Any] | None:
    ticker_sections_all = [
        section
        for section in (sections if isinstance(sections, list) else [])
        if isinstance(section, dict)
        and str(section.get("section_type") or "").strip() == "ticker"
    ]
    if not ticker_sections_all:
        return None

    # Public feed should expose ticker data only from updates mode sections.
    ticker_sections = [
        section
        for section in ticker_sections_all
        if _resolve_ticker_view_mode(section) == "updates"
    ]
    if not ticker_sections:
        return None

    selected_ticker = ticker_sections[0]
    canonical_items = _section_value(
        selected_ticker,
        snake_key="items",
        camel_key="items",
        default=[],
    )
    legacy_update_items = _section_value(
        selected_ticker,
        snake_key="update_items",
        camel_key="updateItems",
        default=[],
    )
    legacy_has_content = (
        isinstance(legacy_update_items, list)
        and any(_has_ticker_update_item_content(item) for item in legacy_update_items)
    )
    source_items = (
        legacy_update_items
        if legacy_has_content
        else canonical_items
        if isinstance(canonical_items, list) and canonical_items
        else legacy_update_items
    )
    resolved_items = _normalize_ticker_update_items(source_items)

    return {
        "items": resolved_items,
    }


def _resolve_program_day_bounds(
    sections: list[dict[str, Any]],
) -> tuple[int, int]:
    for section in (sections if isinstance(sections, list) else []):
        if not isinstance(section, dict):
            continue
        if str(section.get("section_type") or "").strip() != "program":
            continue
        day_start_hour = _coerce_int(
            _section_value(
                section,
                snake_key="day_start_hour",
                camel_key="dayStartHour",
                default=10,
            ),
            10,
        )
        day_end_hour = _coerce_int(
            _section_value(
                section,
                snake_key="day_end_hour",
                camel_key="dayEndHour",
                default=6,
            ),
            6,
        )
        return day_start_hour, day_end_hour
    return 10, 6


class ProgramPublicGigPayload(BaseModel):
    start: str = ""
    end: str = ""
    stage: str = ""
    gig_type: str = ""
    genre: Any = None
    genre_selection: Any = None
    previous_start: str = ""
    previous_end: str = ""
    item_url: str = ""
    title: Any = None
    duration: Any = None
    genre_custom: Any = None
    previous_stage: str = ""
    register_changes: bool = False
    canceled: bool = False


class ProgramPublicNowPlayingGroup(BaseModel):
    stage: Any = None
    description: Any = None
    item_url: str = ""
    current: ProgramPublicGigPayload | None = None
    next: ProgramPublicGigPayload | None = None


class ProgramPublicTickerPayload(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)


class ProgramPublicFeedMeta(BaseModel):
    computed_at: str
    page: str | None = None
    day_start_hour: int = 10
    day_end_hour: int = 6


class ProgramPublicFeedResponse(BaseModel):
    changes: list[ProgramPublicGigPayload] = Field(default_factory=list)
    now_playing: list[ProgramPublicNowPlayingGroup] = Field(default_factory=list)
    ticker: ProgramPublicTickerPayload | None = None
    meta: ProgramPublicFeedMeta


def _program_item_link_missing(entry) -> bool:
    if not isinstance(entry, dict):
        return False
    page_slug = str(entry.get("page_slug") or "").strip()
    item_url = str(entry.get("item_url") or "").strip()
    return not page_slug or not item_url


def _collect_missing_program_item_ids(snapshot: dict) -> tuple[list[str], list[str]]:
    missing_stage_ids: list[str] = []
    missing_gig_ids: list[str] = []
    seen_stage_ids: set[str] = set()
    seen_gig_ids: set[str] = set()

    for stage in snapshot.get("stages", []) if isinstance(snapshot.get("stages"), list) else []:
        stage_id = str(stage.get("id") or "").strip() if isinstance(stage, dict) else ""
        if stage_id and stage_id not in seen_stage_ids and _program_item_link_missing(stage):
            seen_stage_ids.add(stage_id)
            missing_stage_ids.append(stage_id)

    for gig in snapshot.get("gigs", []) if isinstance(snapshot.get("gigs"), list) else []:
        gig_id = str(gig.get("id") or "").strip() if isinstance(gig, dict) else ""
        if gig_id and gig_id not in seen_gig_ids and _program_item_link_missing(gig):
            seen_gig_ids.add(gig_id)
            missing_gig_ids.append(gig_id)

    return missing_stage_ids, missing_gig_ids


def _collect_program_item_ids(snapshot: dict) -> tuple[set[str], set[str]]:
    stage_ids: set[str] = set()
    gig_ids: set[str] = set()

    for stage in snapshot.get("stages", []) if isinstance(snapshot.get("stages"), list) else []:
        stage_id = str(stage.get("id") or "").strip() if isinstance(stage, dict) else ""
        if stage_id:
            stage_ids.add(stage_id)

    for gig in snapshot.get("gigs", []) if isinstance(snapshot.get("gigs"), list) else []:
        gig_id = str(gig.get("id") or "").strip() if isinstance(gig, dict) else ""
        if gig_id:
            gig_ids.add(gig_id)

    return stage_ids, gig_ids


def _normalize_program_item_for_generation_compare(row: dict) -> dict:
    normalized = deepcopy(row) if isinstance(row, dict) else {}
    for key in list(normalized.keys()):
        normalized_key = str(key or "")
        if normalized_key in PROGRAM_GENERATION_COMPARE_IGNORED_KEYS:
            normalized.pop(key, None)
            continue
        if normalized_key.startswith("item_page_"):
            normalized.pop(key, None)
    return normalized


def _collect_changed_program_item_ids(
    previous_snapshot: dict,
    next_snapshot: dict,
) -> tuple[list[str], list[str]]:
    previous_stages = {
        str(stage.get("id") or "").strip(): _normalize_program_item_for_generation_compare(stage)
        for stage in (previous_snapshot.get("stages") if isinstance(previous_snapshot.get("stages"), list) else [])
        if isinstance(stage, dict) and str(stage.get("id") or "").strip()
    }
    next_stages = {
        str(stage.get("id") or "").strip(): _normalize_program_item_for_generation_compare(stage)
        for stage in (next_snapshot.get("stages") if isinstance(next_snapshot.get("stages"), list) else [])
        if isinstance(stage, dict) and str(stage.get("id") or "").strip()
    }
    changed_stage_ids = [
        stage_id
        for stage_id in next_stages
        if stage_id in previous_stages and previous_stages[stage_id] != next_stages[stage_id]
    ]

    previous_gigs = {
        str(gig.get("id") or "").strip(): _normalize_program_item_for_generation_compare(gig)
        for gig in (previous_snapshot.get("gigs") if isinstance(previous_snapshot.get("gigs"), list) else [])
        if isinstance(gig, dict) and str(gig.get("id") or "").strip()
    }
    next_gigs = {
        str(gig.get("id") or "").strip(): _normalize_program_item_for_generation_compare(gig)
        for gig in (next_snapshot.get("gigs") if isinstance(next_snapshot.get("gigs"), list) else [])
        if isinstance(gig, dict) and str(gig.get("id") or "").strip()
    }
    changed_gig_ids = [
        gig_id
        for gig_id in next_gigs
        if gig_id in previous_gigs and previous_gigs[gig_id] != next_gigs[gig_id]
    ]
    return changed_stage_ids, changed_gig_ids


def _collect_duplicate_program_item_ids(rows: list[dict] | None) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("id") or "").strip()
        if not item_id:
            continue
        if item_id in seen:
            duplicates.add(item_id)
            continue
        seen.add(item_id)
    return sorted(duplicates)


def _program_item_external_key(row: dict) -> str:
    if not isinstance(row, dict):
        return ""
    for key in (
        "integration_item_key",
        "integrationItemKey",
        "template_integration_item_key",
        "templateIntegrationItemKey",
        "review_item_key",
        "reviewItemKey",
        "external_id",
        "externalId",
    ):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _collect_duplicate_program_integration_item_keys(
    rows: list[dict] | None,
) -> list[dict[str, Any]]:
    ids_by_key: dict[str, set[str]] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        item_key = _program_item_external_key(row)
        item_id = str(row.get("id") or "").strip()
        if not item_key or not item_id:
            continue
        ids_by_key.setdefault(item_key, set()).add(item_id)
    return [
        {"key": item_key, "ids": sorted(item_ids)}
        for item_key, item_ids in sorted(ids_by_key.items())
        if len(item_ids) > 1
    ]


def _raise_duplicate_program_integration_item_keys(
    duplicate_gig_keys: list[dict[str, Any]],
) -> None:
    if not duplicate_gig_keys:
        return
    raise HTTPException(
        status_code=400,
        detail={
            "code": "duplicate_program_integration_item_keys",
            "message": (
                "Duplicate Program gigs from the same integration item are not allowed. "
                "Use one shared gig ID per integration item before saving."
            ),
            "gigs": duplicate_gig_keys,
        },
    )


async def _collect_program_items_with_missing_generated_pages(
    db,
    snapshot: dict,
) -> tuple[list[str], list[str]]:
    normalized_snapshot = normalize_program_shared_content_snapshot(snapshot)
    stage_source_pairs = [
        (str(stage.get("id") or "").strip(), f"program:stage:{str(stage.get('id') or '').strip()}")
        for stage in normalized_snapshot.get("stages", [])
        if isinstance(stage, dict)
        and str(stage.get("id") or "").strip()
        and not _program_item_link_missing(stage)
    ]
    gig_source_pairs = [
        (str(gig.get("id") or "").strip(), f"program:gig:{str(gig.get('id') or '').strip()}")
        for gig in normalized_snapshot.get("gigs", [])
        if isinstance(gig, dict)
        and str(gig.get("id") or "").strip()
        and not _program_item_link_missing(gig)
    ]

    stage_source_ids = list(dict.fromkeys([source_id for _, source_id in stage_source_pairs]))
    gig_source_ids = list(dict.fromkeys([source_id for _, source_id in gig_source_pairs]))

    existing_stage_source_ids: set[str] = set()
    existing_gig_source_ids: set[str] = set()
    if stage_source_ids:
        async for doc in db["pages"].find(
            {
                "template_managed": True,
                "template_source_type": "program_stage",
                "template_source_id": {"$in": stage_source_ids},
            },
            {"template_source_id": 1},
        ):
            source_id = str(doc.get("template_source_id") or "").strip()
            if source_id:
                existing_stage_source_ids.add(source_id)
    if gig_source_ids:
        async for doc in db["pages"].find(
            {
                "template_managed": True,
                "template_source_type": "program_gig",
                "template_source_id": {"$in": gig_source_ids},
            },
            {"template_source_id": 1},
        ):
            source_id = str(doc.get("template_source_id") or "").strip()
            if source_id:
                existing_gig_source_ids.add(source_id)

    missing_stage_ids = list(
        dict.fromkeys(
            stage_id
            for stage_id, source_id in stage_source_pairs
            if source_id not in existing_stage_source_ids
        )
    )
    missing_gig_ids = list(
        dict.fromkeys(
            gig_id
            for gig_id, source_id in gig_source_pairs
            if source_id not in existing_gig_source_ids
        )
    )
    return missing_stage_ids, missing_gig_ids


def _collect_program_item_generation_candidates(
    previous_snapshot: dict,
    next_snapshot: dict,
    *,
    missing_stage_page_ids: list[str] | None = None,
    missing_gig_page_ids: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    previous_stage_ids, previous_gig_ids = _collect_program_item_ids(previous_snapshot)
    missing_stage_ids, missing_gig_ids = _collect_missing_program_item_ids(next_snapshot)
    changed_stage_ids, changed_gig_ids = _collect_changed_program_item_ids(
        previous_snapshot,
        next_snapshot,
    )

    stage_candidates = list(
        dict.fromkeys(
            [
                *missing_stage_ids,
                *(missing_stage_page_ids or []),
                *changed_stage_ids,
            ]
        )
    )
    gig_candidates = list(
        dict.fromkeys(
            [
                *missing_gig_ids,
                *(missing_gig_page_ids or []),
                *changed_gig_ids,
            ]
        )
    )

    for stage in next_snapshot.get("stages", []) if isinstance(next_snapshot.get("stages"), list) else []:
        if not isinstance(stage, dict):
            continue
        stage_id = str(stage.get("id") or "").strip()
        if not stage_id or stage_id in previous_stage_ids:
            continue
        if stage_id not in stage_candidates:
            stage_candidates.append(stage_id)

    for gig in next_snapshot.get("gigs", []) if isinstance(next_snapshot.get("gigs"), list) else []:
        if not isinstance(gig, dict):
            continue
        gig_id = str(gig.get("id") or "").strip()
        if not gig_id or gig_id in previous_gig_ids:
            continue
        if gig_id not in gig_candidates:
            gig_candidates.append(gig_id)

    return stage_candidates, gig_candidates


def _collect_removed_program_item_ids(
    previous_snapshot: dict,
    next_snapshot: dict,
) -> tuple[list[str], list[str]]:
    previous_stage_ids, previous_gig_ids = _collect_program_item_ids(previous_snapshot)
    next_stage_ids, next_gig_ids = _collect_program_item_ids(next_snapshot)
    removed_stage_ids = sorted(previous_stage_ids - next_stage_ids)
    removed_gig_ids = sorted(previous_gig_ids - next_gig_ids)
    return removed_stage_ids, removed_gig_ids


async def _attach_program_item_page_template_freshness(
    db,
    snapshot: dict,
) -> dict:
    normalized_snapshot = normalize_program_shared_content_snapshot(snapshot)
    stage_titles_by_id = build_program_stage_titles_lookup(
        normalized_snapshot.get("stages", [])
    )

    stage_ids = [
        str(stage.get("id") or "").strip()
        for stage in normalized_snapshot.get("stages", [])
        if isinstance(stage, dict) and str(stage.get("id") or "").strip()
    ]
    gig_ids = [
        str(gig.get("id") or "").strip()
        for gig in normalized_snapshot.get("gigs", [])
        if isinstance(gig, dict) and str(gig.get("id") or "").strip()
    ]

    stage_source_ids = [f"program:stage:{stage_id}" for stage_id in stage_ids]
    gig_source_ids = [f"program:gig:{gig_id}" for gig_id in gig_ids]
    stage_source_hashes = await build_program_item_page_source_hashes_for_freshness(
        db,
        kind="stage",
        rows=normalized_snapshot.get("stages", []),
    )
    gig_source_hashes = await build_program_item_page_source_hashes_for_freshness(
        db,
        kind="gig",
        rows=normalized_snapshot.get("gigs", []),
        stage_titles_by_id=stage_titles_by_id,
    )

    stage_freshness = await get_generated_item_page_template_freshness_map(
        db,
        source_type="program_stage",
        source_ids=stage_source_ids,
        source_payload_hashes=stage_source_hashes,
    )
    gig_freshness = await get_generated_item_page_template_freshness_map(
        db,
        source_type="program_gig",
        source_ids=gig_source_ids,
        source_payload_hashes=gig_source_hashes,
    )
    stage_item_pages_active = bool(await resolve_active_item_page_template(db, "program", "stage"))
    gig_item_pages_active = bool(await resolve_active_item_page_template(db, "program", "gig"))
    stage_existing_sources = set(stage_freshness.keys())
    gig_existing_sources = set(gig_freshness.keys())

    for stage in normalized_snapshot.get("stages", []):
        if not isinstance(stage, dict):
            continue
        stage_id = str(stage.get("id") or "").strip()
        source_id = f"program:stage:{stage_id}" if stage_id else ""
        has_links = not _program_item_link_missing(stage)
        item_page_missing = bool(
            stage_item_pages_active and has_links and source_id and source_id not in stage_existing_sources
        )
        freshness_entry = stage_freshness.get(source_id) or {}
        mapped_fields_synced = freshness_entry.get("item_page_mapped_fields_synced")
        stage["item_page_template_outdated"] = bool(
            freshness_entry.get("item_page_template_outdated")
        )
        stage["item_page_missing"] = item_page_missing
        stage["item_page_mapped_fields_synced"] = bool(
            mapped_fields_synced
            if isinstance(mapped_fields_synced, bool)
            else source_id in stage_existing_sources
        )

    for gig in normalized_snapshot.get("gigs", []):
        if not isinstance(gig, dict):
            continue
        gig_id = str(gig.get("id") or "").strip()
        source_id = f"program:gig:{gig_id}" if gig_id else ""
        has_links = not _program_item_link_missing(gig)
        item_page_missing = bool(
            gig_item_pages_active and has_links and source_id and source_id not in gig_existing_sources
        )
        freshness_entry = gig_freshness.get(source_id) or {}
        mapped_fields_synced = freshness_entry.get("item_page_mapped_fields_synced")
        gig["item_page_template_outdated"] = bool(
            freshness_entry.get("item_page_template_outdated")
        )
        gig["item_page_missing"] = item_page_missing
        gig["item_page_mapped_fields_synced"] = bool(
            mapped_fields_synced
            if isinstance(mapped_fields_synced, bool)
            else source_id in gig_existing_sources
        )

    return normalized_snapshot


class ProgramItemPageGenerationJob(BaseModel):
    job_id: str
    status: str
    source_type: str
    source_id: str
    source_key: str
    slug: str | None = None
    error: str | None = None


class ProgramSharedResponse(BaseModel):
    gigs: list[ProgramGig] = Field(default_factory=list)
    gig_ids: list[str] = Field(default_factory=list)
    stages: list[ProgramStage] = Field(default_factory=list)
    program_stages_integration_mapping: dict[str, Any] = Field(default_factory=dict)
    program_stages_integration_mapping_cache_state: dict[str, Any] = Field(default_factory=dict)
    program_gigs_integration_mapping: dict[str, Any] = Field(default_factory=dict)
    program_gigs_integration_mapping_cache_state: dict[str, Any] = Field(default_factory=dict)
    item_page_generation_jobs: list[ProgramItemPageGenerationJob] = Field(default_factory=list)


class ProgramSharedUpdate(BaseModel):
    gigs: list[ProgramGig] | None = None
    gig_ids: list[str] | None = None
    stages: list[ProgramStage] | None = None
    program_stages_integration_mapping: dict[str, Any] | None = None
    program_stages_integration_mapping_cache_state: dict[str, Any] | None = None
    program_gigs_integration_mapping: dict[str, Any] | None = None
    program_gigs_integration_mapping_cache_state: dict[str, Any] | None = None


class ProgramSharedGigUpdate(BaseModel):
    gig: ProgramGig


class ProgramSharedGigUpdateResponse(BaseModel):
    gig: ProgramGig
    item_page_generation_jobs: list[ProgramItemPageGenerationJob] = Field(default_factory=list)


@router.get(
    "/public-feed",
    response_model=ProgramPublicFeedResponse,
)
async def get_program_public_feed(
    response: Response,
    include_ticker: bool = Query(default=False, alias="includeTicker"),
    page: str | None = Query(default=None),
):
    requested_page = str(page or "").strip()
    normalized_page = _normalize_public_page_slug(requested_page) if requested_page else None

    if include_ticker and not requested_page:
        raise HTTPException(
            status_code=400,
            detail="Query parameter 'page' is required when includeTicker=true.",
        )

    cache_key = f"public:program-feed:{1 if include_ticker else 0}:{normalized_page or ''}"
    cached = get_ttl_cache(cache_key)
    if cached is not None:
        set_public_cache_headers(
            response,
            max_age=PUBLIC_PROGRAM_FEED_CACHE_SECONDS,
            stale_while_revalidate=15,
        )
        response.headers["X-Backend-Cache-Status"] = "HIT"
        return cached

    async def build_public_feed() -> dict:
        sections_payload: list[dict[str, Any]] = []
        day_start_hour = 10
        day_end_hour = 6

        if requested_page:
            page_payload = await get_page_with_sections(
                normalized_page,
                include_hidden=False,
                user=None,
            )
            sections_payload = (
                page_payload.get("sections")
                if isinstance(page_payload, dict) and isinstance(page_payload.get("sections"), list)
                else []
            )
            day_start_hour, day_end_hour = _resolve_program_day_bounds(sections_payload)

        db = _db()
        snapshot = normalize_program_shared_content_snapshot(await capture_program_shared_content(db))
        stages = [
            deepcopy(stage)
            for stage in (snapshot.get("stages") if isinstance(snapshot.get("stages"), list) else [])
            if isinstance(stage, dict)
        ]
        gigs = [
            deepcopy(gig)
            for gig in (snapshot.get("gigs") if isinstance(snapshot.get("gigs"), list) else [])
            if isinstance(gig, dict)
        ]

        now_local = datetime.now()
        changes_payload = _build_public_changes_payload(
            gigs=gigs,
            stages=stages,
            day_start_hour=day_start_hour,
            day_end_hour=day_end_hour,
        )
        now_playing_payload = _build_public_now_playing_payload(
            gigs=gigs,
            stages=stages,
            now_local=now_local,
        )
        ticker_payload = (
            _resolve_ticker_payload_from_sections(sections_payload)
            if include_ticker
            else None
        )

        payload = ProgramPublicFeedResponse(
            changes=changes_payload,
            now_playing=now_playing_payload,
            ticker=ticker_payload,
            meta=ProgramPublicFeedMeta(
                computed_at=datetime.now().astimezone().isoformat(),
                page=normalized_page,
                day_start_hour=day_start_hour,
                day_end_hour=day_end_hour,
            ),
        )
        return payload.model_dump(mode="json")

    result = await get_or_set_ttl_cache(
        cache_key,
        PUBLIC_PROGRAM_FEED_CACHE_SECONDS,
        build_public_feed,
    )
    set_public_cache_headers(
        response,
        max_age=PUBLIC_PROGRAM_FEED_CACHE_SECONDS,
        stale_while_revalidate=15,
    )
    response.headers["X-Backend-Cache-Status"] = "MISS"
    return result


@router.get(
    "/shared",
    response_model=ProgramSharedResponse,
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_program_shared(
    day: str | None = Query(default=None),
    stage_id: str | None = Query(default=None, alias="stage_id"),
    gig_id: str | None = Query(default=None, alias="gig_id"),
    ids: list[str] | None = Query(default=None),
    day_start_hour: int = Query(default=10, ge=0, le=23, alias="day_start_hour"),
    day_end_hour: int = Query(default=6, ge=1, le=30, alias="day_end_hour"),
):
    db = _db()
    snapshot = await capture_program_shared_content(
        db,
        ids=ids,
        gig_id=gig_id,
        stage_id=stage_id,
        day=day,
        day_start_hour=day_start_hour,
        day_end_hour=day_end_hour,
    )
    enriched_snapshot = await _enrich_program_snapshot_with_asset_media(db, snapshot)
    normalized = await _attach_program_item_page_template_freshness(db, enriched_snapshot)
    integration_state = _resolve_program_integration_state(normalized)
    return ProgramSharedResponse(
        **{**normalized, **integration_state},
        item_page_generation_jobs=[],
    )


@router.patch(
    "/shared/gigs/{gig_id}",
    response_model=ProgramSharedGigUpdateResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def patch_program_shared_gig(
    gig_id: str,
    request: Request,
    payload: ProgramSharedGigUpdate,
    user: KeycloakUser = Depends(get_current_user),
):
    raw_payload = await request.json()
    if isinstance(raw_payload, dict):
        ensure_snake_case_keys(raw_payload, root_label="payload")

    normalized_gig_id = str(gig_id or "").strip()
    if not normalized_gig_id:
        raise HTTPException(status_code=400, detail="Missing gig ID")

    db = _db()
    current_snapshot = normalize_program_shared_content_snapshot(
        await capture_program_shared_content(db)
    )
    current_gigs = current_snapshot.get("gigs") if isinstance(current_snapshot.get("gigs"), list) else []
    current_gig = next(
        (
            gig
            for gig in current_gigs
            if isinstance(gig, dict)
            and str(gig.get("id") or "").strip() == normalized_gig_id
        ),
        None,
    )

    incoming_gig = payload.gig.model_dump()
    incoming_gig["id"] = normalized_gig_id
    normalized_update = normalize_program_shared_content_snapshot(
        {
            "stages": [],
            "gigs": [incoming_gig],
            "program_stages_integration_mapping": {},
            "program_stages_integration_mapping_cache_state": {},
            "program_gigs_integration_mapping": current_snapshot.get(
                "program_gigs_integration_mapping",
                {},
            ),
            "program_gigs_integration_mapping_cache_state": current_snapshot.get(
                "program_gigs_integration_mapping_cache_state",
                {},
            ),
        }
    )
    next_gig = (
        normalized_update.get("gigs", [])[0]
        if isinstance(normalized_update.get("gigs"), list)
        and normalized_update.get("gigs")
        else None
    )
    if not isinstance(next_gig, dict):
        raise HTTPException(status_code=400, detail="Invalid program gig payload")
    next_gig["id"] = normalized_gig_id

    is_new_gig = not isinstance(current_gig, dict)
    merged_gigs = [
        deepcopy(next_gig)
        if isinstance(gig, dict)
        and str(gig.get("id") or "").strip() == normalized_gig_id
        else deepcopy(gig)
        for gig in current_gigs
        if isinstance(gig, dict)
    ]
    if is_new_gig:
        merged_gigs.append(deepcopy(next_gig))
    _raise_duplicate_program_integration_item_keys(
        _collect_duplicate_program_integration_item_keys(merged_gigs)
    )
    merged_snapshot = {
        **current_snapshot,
        "gigs": merged_gigs,
        "gig_ids": [
            str(gig.get("id") or "").strip()
            for gig in merged_gigs
            if isinstance(gig, dict) and str(gig.get("id") or "").strip()
        ],
    }

    changed = is_new_gig or not snapshots_equal(current_gig, next_gig)
    if changed:
        await push_program_shared_content_revisions(
            db,
            saved_by=user.username,
        )
        next_gig = await program_catalog.update_program_gig(db, normalized_gig_id, next_gig)

    queued_jobs: list[dict] = []
    missing_stage_page_ids, missing_gig_page_ids = await _collect_program_items_with_missing_generated_pages(
        db,
        {
            **merged_snapshot,
            "stages": [],
            "gigs": [next_gig],
        },
    )
    # Single-gig PATCH is used by the Program editor's autosave path. Keep it
    # lightweight: missing generated pages may be restored, but mapped-field
    # refreshes and template rebuilds stay behind the explicit UI actions.
    generation_needed = normalized_gig_id in (missing_gig_page_ids or [])
    if generation_needed:
        logger.info(
            "program.shared.gig.patch.item_page_candidate gig_id=%s changed=%s missing_gig_page=%s",
            normalized_gig_id,
            changed,
            normalized_gig_id in (missing_gig_page_ids or []),
        )
        job_payload = await enqueue_program_item_page_generation(
            db,
            kind="gig",
            item_id=normalized_gig_id,
        )
        if job_payload:
            queued_jobs.append(job_payload)

    return ProgramSharedGigUpdateResponse(
        gig=next_gig,
        item_page_generation_jobs=queued_jobs,
    )


@router.put(
    "/shared",
    response_model=ProgramSharedResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def put_program_shared(
    request: Request,
    payload: ProgramSharedUpdate,
    user: KeycloakUser = Depends(get_current_user),
):
    raw_payload = await request.json()
    if isinstance(raw_payload, dict):
        ensure_snake_case_keys(raw_payload, root_label="payload")

    db = _db()
    current_snapshot = normalize_program_shared_content_snapshot(
        await capture_program_shared_content(db)
    )

    incoming_gigs = (
        [
            entry.model_dump() if isinstance(entry, BaseModel) else entry
            for entry in (payload.gigs or [])
        ]
        if payload.gigs is not None
        else None
    )
    incoming_gig_ids = (
        [
            str(entry or "").strip()
            for entry in (payload.gig_ids or [])
            if str(entry or "").strip()
        ]
        if payload.gig_ids is not None
        else None
    )
    incoming_stages = (
        [
            entry.model_dump() if isinstance(entry, BaseModel) else entry
            for entry in (payload.stages or [])
        ]
        if payload.stages is not None
        else None
    )
    incoming_stage_mapping = (
        _normalize_program_integration_state_value(payload.program_stages_integration_mapping)
        if payload.program_stages_integration_mapping is not None
        else None
    )
    incoming_stage_cache_state = (
        _normalize_program_integration_state_value(payload.program_stages_integration_mapping_cache_state)
        if payload.program_stages_integration_mapping_cache_state is not None
        else None
    )
    incoming_gig_mapping = (
        _normalize_program_integration_state_value(payload.program_gigs_integration_mapping)
        if payload.program_gigs_integration_mapping is not None
        else None
    )
    incoming_gig_cache_state = (
        _normalize_program_integration_state_value(payload.program_gigs_integration_mapping_cache_state)
        if payload.program_gigs_integration_mapping_cache_state is not None
        else None
    )
    duplicate_stage_ids = _collect_duplicate_program_item_ids(incoming_stages)
    duplicate_gig_ids = _collect_duplicate_program_item_ids(incoming_gigs)
    if duplicate_stage_ids or duplicate_gig_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "duplicate_program_item_ids",
                "message": "Duplicate stage or gig IDs are not allowed. Use unique IDs before saving.",
                "stages": duplicate_stage_ids,
                "gigs": duplicate_gig_ids,
            },
        )

    merged_snapshot = normalize_program_shared_content_snapshot(
        {
            "gigs": incoming_gigs if incoming_gigs is not None else current_snapshot.get("gigs", []),
            "gig_ids": (
                incoming_gig_ids
                if incoming_gig_ids is not None
                else current_snapshot.get("gig_ids", [])
            ),
            "stages": incoming_stages if incoming_stages is not None else current_snapshot.get("stages", []),
            "program_stages_integration_mapping": (
                incoming_stage_mapping
                if incoming_stage_mapping is not None
                else current_snapshot.get("program_stages_integration_mapping", {})
            ),
            "program_stages_integration_mapping_cache_state": (
                incoming_stage_cache_state
                if incoming_stage_cache_state is not None
                else current_snapshot.get("program_stages_integration_mapping_cache_state", {})
            ),
            "program_gigs_integration_mapping": (
                incoming_gig_mapping
                if incoming_gig_mapping is not None
                else current_snapshot.get("program_gigs_integration_mapping", {})
            ),
            "program_gigs_integration_mapping_cache_state": (
                incoming_gig_cache_state
                if incoming_gig_cache_state is not None
                else current_snapshot.get("program_gigs_integration_mapping_cache_state", {})
            ),
        }
    )
    _raise_duplicate_program_integration_item_keys(
        _collect_duplicate_program_integration_item_keys(
            merged_snapshot.get("gigs") if isinstance(merged_snapshot.get("gigs"), list) else []
        )
    )

    if not snapshots_equal(current_snapshot, merged_snapshot):
        if not snapshots_equal(
            sanitize_program_shared_content_for_revision(current_snapshot),
            sanitize_program_shared_content_for_revision(merged_snapshot),
        ):
            await push_program_shared_content_revisions(
                db,
                saved_by=user.username,
            )
        await apply_program_shared_content(db, merged_snapshot)

    removed_stage_ids, removed_gig_ids = _collect_removed_program_item_ids(
        current_snapshot,
        merged_snapshot,
    )
    for stage_id in removed_stage_ids:
        await cleanup_generated_item_page_for_source(
            db,
            source_type="program_stage",
            source_id=f"program:stage:{stage_id}",
        )
    for gig_id in removed_gig_ids:
        await cleanup_generated_item_page_for_source(
            db,
            source_type="program_gig",
            source_id=f"program:gig:{gig_id}",
        )

    snapshot_after_save = normalize_program_shared_content_snapshot(
        await capture_program_shared_content(db)
    )
    missing_stage_page_ids, missing_gig_page_ids = await _collect_program_items_with_missing_generated_pages(
        db,
        snapshot_after_save,
    )
    stage_generation_candidates, gig_generation_candidates = _collect_program_item_generation_candidates(
        current_snapshot,
        snapshot_after_save,
        missing_stage_page_ids=missing_stage_page_ids,
        missing_gig_page_ids=missing_gig_page_ids,
    )
    if stage_generation_candidates or gig_generation_candidates:
        logger.info(
            "program.shared.save.item_page_candidates stages=%d gigs=%d missing_stage_pages=%d missing_gig_pages=%d",
            len(stage_generation_candidates),
            len(gig_generation_candidates),
            len(missing_stage_page_ids),
            len(missing_gig_page_ids),
        )
    queued_jobs: list[dict] = []
    for stage_id in stage_generation_candidates:
        job_payload = await enqueue_program_item_page_generation(
            db,
            kind="stage",
            item_id=stage_id,
        )
        if job_payload:
            queued_jobs.append(job_payload)
    for gig_id in gig_generation_candidates:
        job_payload = await enqueue_program_item_page_generation(
            db,
            kind="gig",
            item_id=gig_id,
        )
        if job_payload:
            queued_jobs.append(job_payload)

    latest_snapshot = await _attach_program_item_page_template_freshness(
        db,
        await _enrich_program_snapshot_with_asset_media(
            db,
            await capture_program_shared_content(db),
        ),
    )
    integration_state = _resolve_program_integration_state(latest_snapshot)
    return ProgramSharedResponse(
        **{**latest_snapshot, **integration_state},
        item_page_generation_jobs=queued_jobs,
    )
