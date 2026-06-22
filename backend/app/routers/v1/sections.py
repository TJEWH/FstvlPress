from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse

import httpx
import markdown
from bs4 import BeautifulSoup
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from pymongo import ReturnDocument

from app.db import get_client
from app.deps import get_current_user, require_permission
from app.security import KeycloakUser
from app.settings import settings
from app.models.cms import (
    SectionCreate,
    SectionDB,
    SectionUpdate,
    RevisionStatusResponse,
)
from app.models.sections.sections import (
    get_default_type_data,
    migrate_document_section_payload,
    normalize_html_type_data,
    normalize_markdown_type_data,
    SECTION_TYPE_SCHEMAS,
)
from app.models.sections.normalization import normalize_section_description_payload
from app.media_tags import normalize_media_tag_part
from app.media_responsive import (
    collect_raster_image_urls_from_payload,
    enrich_raster_payload_with_asset_docs,
    fetch_asset_docs_by_urls,
)
from app.item_page_jobs import get_item_page_generation_job
from app.revisioning import (
    REVISION_HISTORY_LIMIT,
    apply_faq_shared_content,
    apply_program_shared_content,
    build_revision_history_payload,
    apply_blog_shared_content,
    apply_section_design_state,
    as_object_id,
    build_section_content_snapshot,
    build_section_revision_snapshot,
    capture_faq_shared_content,
    capture_blog_shared_content,
    capture_program_shared_content,
    capture_section_design_state,
    DEFAULT_SECTION_CONTENT_EXCLUDE_KEYS,
    get_or_create_revision_config,
    get_section_design_type_data_keys,
    get_section_revision_options,
    normalize_saved_at_label,
    parse_section_revision_snapshot,
    push_faq_shared_content_revisions,
    push_blog_shared_content_revisions,
    push_program_shared_content_revisions,
    push_revision_entry,
    resolve_effective_change_kind,
    section_revision_history_enabled,
    snapshots_equal,
)
from app.template_sync import (
    SECTION_TEMPLATE_SYNC_FIELDS,
    cleanup_blog_generated_pages_for_route,
    cleanup_program_generated_pages_for_section,
    normalize_section_integration_mapping,
    normalize_template_section_design_overrides,
    normalize_parent_route,
    resolve_active_item_page_template,
    sync_blog_item_page_by_id,
    sync_all_blog_items_for_section,
    sync_all_blog_items_for_section_report,
    sync_generated_item_page_review_overrides_for_saved_targets,
    sync_program_gig_section_pages_report,
    sync_program_stage_section_pages_report,
    resolve_section_template_sync_context,
)


# Markdown parser instance with common extensions
md_parser = markdown.Markdown(
    extensions=[
        "tables",
        "fenced_code",
        "codehilite",
        "toc",
        "nl2br",
        "sane_lists",
    ]
)

router = APIRouter(prefix="/sections", tags=["sections"])
logger = logging.getLogger(__name__)

MAX_HISTORY = REVISION_HISTORY_LIMIT

SECTION_REVISION_EXCLUDE_KEYS = frozenset(
    DEFAULT_SECTION_CONTENT_EXCLUDE_KEYS | {"shared"}
)
BLOG_SECTION_TYPE = "blog"
FAQ_SECTION_TYPE = "faq"
PROGRAM_SECTION_TYPE = "program"
FAQ_TYPE_DATA_SHARED_PAYLOAD_KEYS = (
    "faqs",
    "faqItems",
    "faq_items",
    "faqTags",
    "faq_tags",
    "items",
    "tags",
    "scope",
)
FAQ_TYPE_DATA_CACHE_STATE_KEYS = (
    "section_integration_mapping_cache_state",
    "sectionIntegrationMappingCacheState",
    "faq_integration_mapping_cache_state",
    "faqIntegrationMappingCacheState",
    "integration_mapping_cache_state",
    "integrationMappingCacheState",
)
FAQ_TOP_LEVEL_CACHE_STATE_KEYS = (
    "section_integration_mapping_cache_state",
    "sectionIntegrationMappingCacheState",
    "faq_integration_mapping_cache_state",
    "faqIntegrationMappingCacheState",
    "integration_mapping_cache_state",
    "integrationMappingCacheState",
)
HTML_EMBED_PROVIDER_HOSTS: dict[str, tuple[str, ...]] = {
    "youtube": (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "www.youtu.be",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
    ),
    "instagram": (
        "instagram.com",
        "www.instagram.com",
        "instagr.am",
        "www.instagr.am",
        "platform.instagram.com",
    ),
}
EMBED_ATTR_URL_RE = re.compile(
    r"\b(?:src|href|data-instgrm-permalink)\s*=\s*[\"']((?:https?:)?//[^\"'<>]+)[\"']",
    re.IGNORECASE,
)
MARKDOWN_FETCH_MAX_BYTES = 2_000_000


def _is_non_public_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _normalize_fetch_source_url(raw_url: str) -> str:
    source_url = str(raw_url or "").strip()
    if not source_url:
        raise HTTPException(400, "source_url is required")

    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(400, "source_url must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise HTTPException(400, "source_url must not include credentials")

    host = str(parsed.hostname or "").strip().strip(".").lower()
    if not host:
        raise HTTPException(400, "source_url host is missing")
    if host == "localhost" or host.endswith(".local"):
        raise HTTPException(400, "source_url host is not allowed")

    try:
        ip_addr = ipaddress.ip_address(host)
        if _is_non_public_ip(ip_addr):
            raise HTTPException(400, "source_url host must be publicly routable")
    except ValueError:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            resolved = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror:
            raise HTTPException(400, "source_url host could not be resolved")

        for entry in resolved:
            sockaddr = entry[4]
            if not sockaddr:
                continue
            ip_text = str(sockaddr[0] or "").strip()
            if not ip_text:
                continue
            try:
                resolved_ip = ipaddress.ip_address(ip_text)
            except ValueError:
                continue
            if _is_non_public_ip(resolved_ip):
                raise HTTPException(400, "source_url host resolves to a non-public IP")

    return source_url

def _infer_change_kind_from_patch(section_type: str, patch: dict) -> str:
    """Infer revision kind when frontend does not provide one."""
    type_data = patch.get("type_data")
    if not isinstance(type_data, dict):
        return "content"

    keys = {str(k) for k in type_data.keys()}
    if not keys:
        return "content"

    design_keys = get_section_design_type_data_keys(section_type)
    if design_keys:
        if keys.issubset(design_keys):
            return "design"
        if keys & design_keys:
            return "both"
        return "content"

    return "content"


def _normalize_percent(value, default: float = 50.0) -> float:
    try:
        parsed = float(value)
        if parsed != parsed:
            return default
        return max(0.0, min(100.0, parsed))
    except Exception:
        return default


def _normalize_zoom(value, default: float = 1.0) -> float:
    try:
        parsed = float(value)
        if parsed != parsed:
            return default
        return max(1.0, min(4.0, parsed))
    except Exception:
        return default


def _normalize_rotation(value, default: float = 0.0) -> float:
    try:
        parsed = float(value)
        if parsed != parsed:
            return default
        return max(-180.0, min(180.0, parsed))
    except Exception:
        return default


def _normalize_tile_width(value, default: int = 220) -> int:
    try:
        parsed = int(float(value))
        return max(80, min(1600, parsed))
    except Exception:
        return default


def _normalize_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    return default


def _normalize_gallery_type_data(type_data: dict) -> dict:
    if not isinstance(type_data, dict):
        return {}
    images = type_data.get("images")
    normalized_images: list[dict] = []
    raw_media_tag_bindings = (
        type_data.get("media_tag_bindings")
        if isinstance(type_data.get("media_tag_bindings"), list)
        else type_data.get("mediaTagBindings")
    )
    normalized_media_tag_bindings: list[dict] = []

    if isinstance(images, list):
        for index, raw_item in enumerate(images):
            if not isinstance(raw_item, dict):
                continue
            item = deepcopy(raw_item)
            item["asset_id"] = str(item.get("asset_id") or "").strip()
            item["image_url"] = str(item.get("image_url") or "").strip()
            item["image_author"] = str(
                item.get("image_author")
                or item.get("imageAuthor")
                or ""
            ).strip()
            item.pop("imageAuthor", None)
            item.pop("original_asset_id", None)
            if "id" not in item:
                item["id"] = f"gallery-{index + 1}"
            item["zoom"] = _normalize_zoom(item.get("zoom"), default=1.0)
            item["focal_x"] = _normalize_percent(item.get("focal_x"), default=50.0)
            item["focal_y"] = _normalize_percent(item.get("focal_y"), default=50.0)
            item["rotation"] = _normalize_rotation(item.get("rotation"), default=0.0)
            item["alt"] = _normalize_bilingual_text(
                item.get("alt") if isinstance(item.get("alt"), dict) else None
            )
            item["caption"] = _normalize_bilingual_text(
                item.get("caption") if isinstance(item.get("caption"), dict) else None
            )
            normalized_images.append(item)

    if isinstance(raw_media_tag_bindings, list):
        for index, raw_binding in enumerate(raw_media_tag_bindings):
            if not isinstance(raw_binding, dict):
                continue
            prefix = normalize_media_tag_part(
                raw_binding.get("prefix")
                or raw_binding.get("prefixValue")
                or ""
            )
            prefix_source_path = str(
                raw_binding.get("prefix_source_path")
                or raw_binding.get("prefixSourcePath")
                or ""
            ).strip()
            value_source_path = str(
                raw_binding.get("value_source_path")
                or raw_binding.get("valueSourcePath")
                or ""
            ).strip()
            resolved_tag = str(
                raw_binding.get("resolved_tag")
                or raw_binding.get("resolvedTag")
                or ""
            ).strip()
            enabled = _normalize_bool(raw_binding.get("enabled"), default=True)
            if not (prefix or prefix_source_path or value_source_path or resolved_tag):
                continue
            normalized_media_tag_bindings.append(
                {
                    "id": str(raw_binding.get("id") or f"media-tag-binding-{index + 1}"),
                    "enabled": enabled,
                    "prefix": prefix,
                    "prefix_source_path": prefix_source_path,
                    "value_source_path": value_source_path,
                    "resolved_tag": resolved_tag,
                }
            )

    next_type_data = dict(type_data)
    next_type_data["images"] = normalized_images
    next_type_data["media_tag_bindings"] = normalized_media_tag_bindings
    if next_type_data.get("layout") not in {"grid", "carousel", "masonry"}:
        next_type_data["layout"] = "grid"
    if next_type_data.get("aspect_ratio") not in {"1:1", "3:2", "4:3", "16:9"}:
        next_type_data["aspect_ratio"] = "4:3"
    orientation = next_type_data.get("orientation")
    next_type_data["orientation"] = orientation if orientation in {"landscape", "portrait"} else "landscape"
    next_type_data["show_captions"] = _normalize_bool(next_type_data.get("show_captions"), default=True)
    return next_type_data


def _normalize_tiles_type_data(type_data: dict) -> dict:
    if not isinstance(type_data, dict):
        return {}
    tiles = type_data.get("tiles")

    next_type_data = dict(type_data)

    grid_mode = str(next_type_data.get("grid_mode") or "auto").strip().lower()
    if grid_mode not in {"fixed", "columns", "auto"}:
        grid_mode = "auto"
    next_type_data["grid_mode"] = grid_mode

    tile_min_width = _normalize_tile_width(next_type_data.get("tile_min_width"), default=220)
    tile_max_width = _normalize_tile_width(next_type_data.get("tile_max_width"), default=360)
    if tile_max_width < tile_min_width:
        tile_max_width = tile_min_width
    next_type_data["tile_min_width"] = tile_min_width
    next_type_data["tile_max_width"] = tile_max_width

    if "tiles" in next_type_data:
        normalized_tiles: list[dict] = []
        if isinstance(tiles, list):
            for index, raw_item in enumerate(tiles):
                if not isinstance(raw_item, dict):
                    continue
                item = deepcopy(raw_item)
                if "id" not in item:
                    item["id"] = f"tile-{index + 1}"
                item["zoom"] = _normalize_zoom(item.get("zoom"), default=1.0)
                item["focal_x"] = _normalize_percent(item.get("focal_x"), default=50.0)
                item["focal_y"] = _normalize_percent(item.get("focal_y"), default=50.0)
                item["rotation"] = _normalize_rotation(item.get("rotation"), default=0.0)
                normalized_tiles.append(item)
        next_type_data["tiles"] = normalized_tiles

    if "always_show_title" in next_type_data:
        always_show_title_raw = next_type_data.get("always_show_title")
        next_type_data["always_show_title"] = (
            bool(always_show_title_raw) if always_show_title_raw is not None else False
        )

    if "tile_show_reset_button" in next_type_data:
        tile_show_reset_button_raw = next_type_data.get("tile_show_reset_button")
        next_type_data["tile_show_reset_button"] = (
            bool(tile_show_reset_button_raw) if tile_show_reset_button_raw is not None else False
        )

    tile_sort_mode = str(next_type_data.get("tile_sort_mode") or "title").strip().lower()
    if tile_sort_mode not in {"manual", "title"}:
        tile_sort_mode = "title"
    next_type_data["tile_sort_mode"] = tile_sort_mode

    if "use_program_gigs" in next_type_data:
        use_program_gigs_raw = next_type_data.get("use_program_gigs")
        next_type_data["use_program_gigs"] = (
            bool(use_program_gigs_raw) if use_program_gigs_raw is not None else True
        )

    if "filters" in next_type_data:
        raw_filters = next_type_data.get("filters")
        normalized_filters: list[dict] = []
        seen_filter_ids: set[str] = set()
        if isinstance(raw_filters, list):
            for index, raw_filter in enumerate(raw_filters):
                if not isinstance(raw_filter, dict):
                    continue
                filter_id = str(
                    raw_filter.get("id")
                    or ""
                ).strip()
                if not filter_id:
                    filter_id = f"filter-{index + 1}"
                if filter_id in seen_filter_ids:
                    suffix = 2
                    candidate = f"{filter_id}-{suffix}"
                    while candidate in seen_filter_ids:
                        suffix += 1
                        candidate = f"{filter_id}-{suffix}"
                    filter_id = candidate
                seen_filter_ids.add(filter_id)

                filter_name = str(raw_filter.get("name") or "").strip()
                target_path = str(
                    raw_filter.get("target_path")
                    or ""
                ).strip()
                raw_manual_options = (
                    raw_filter.get("manual_options")
                )
                manual_options: list[str] = []
                if isinstance(raw_manual_options, list):
                    seen_manual_options: set[str] = set()
                    for raw_option in raw_manual_options:
                        if not isinstance(raw_option, str):
                            continue
                        normalized_option = raw_option.strip()
                        if not normalized_option or normalized_option in seen_manual_options:
                            continue
                        seen_manual_options.add(normalized_option)
                        manual_options.append(normalized_option)
                elif isinstance(raw_manual_options, str):
                    seen_manual_options: set[str] = set()
                    for raw_option in raw_manual_options.split(","):
                        normalized_option = str(raw_option or "").strip()
                        if not normalized_option or normalized_option in seen_manual_options:
                            continue
                        seen_manual_options.add(normalized_option)
                        manual_options.append(normalized_option)
                enabled_raw = raw_filter.get("enabled")
                enabled = bool(enabled_raw) if enabled_raw is not None else True
                if not filter_name and target_path:
                    filter_name = target_path
                normalized_filters.append(
                    {
                        "id": filter_id,
                        "name": filter_name,
                        "target_path": target_path,
                        "manual_options": manual_options,
                        "enabled": enabled,
                    }
                )
        next_type_data["filters"] = normalized_filters

    filter_control_style = str(
        next_type_data.get("filter_control_style")
        or "dropdowns"
    ).strip().lower()
    if filter_control_style not in {"dropdowns", "pills", "segmented"}:
        filter_control_style = "dropdowns"
    next_type_data["filter_control_style"] = filter_control_style

    tile_top_info_align = str(
        next_type_data.get("tile_top_info_align")
        or "right"
    ).strip().lower()
    if tile_top_info_align not in {"left", "right"}:
        tile_top_info_align = "right"
    next_type_data["tile_top_info_align"] = tile_top_info_align

    tile_bottom_info_align = str(
        next_type_data.get("tile_bottom_info_align")
        or "left"
    ).strip().lower()
    if tile_bottom_info_align not in {"left", "center", "right"}:
        tile_bottom_info_align = "left"
    next_type_data["tile_bottom_info_align"] = tile_bottom_info_align

    if "filter_control_order" in next_type_data or "filters" in next_type_data:
        raw_filter_control_order = next_type_data.get("filter_control_order")
        filter_ids = [
            str(item.get("id") or "").strip()
            for item in next_type_data.get("filters", [])
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        ]
        known_filter_ids = set(filter_ids)
        allow_filter_reset = bool(next_type_data.get("tile_show_reset_button")) and len(filter_ids) > 1
        filter_control_order: list[str] = []

        def add_filter_control_id(raw_id) -> None:
            control_id = str(raw_id or "").strip()
            if not control_id or control_id in filter_control_order:
                return
            if control_id == "__reset__":
                if allow_filter_reset:
                    filter_control_order.append(control_id)
                return
            if control_id not in known_filter_ids:
                return
            filter_control_order.append(control_id)

        if isinstance(raw_filter_control_order, list):
            for raw_control_id in raw_filter_control_order:
                add_filter_control_id(raw_control_id)
        for filter_id in filter_ids:
            add_filter_control_id(filter_id)
        if allow_filter_reset:
            add_filter_control_id("__reset__")
        next_type_data["filter_control_order"] = filter_control_order

    if "program_tile_order" in next_type_data:
        raw_program_tile_order = next_type_data.get("program_tile_order")
        program_tile_order: list[str] = []
        if isinstance(raw_program_tile_order, list):
            seen_program_tile_ids: set[str] = set()
            for raw_tile_id in raw_program_tile_order:
                tile_id = str(raw_tile_id or "").strip()
                if not tile_id or tile_id in seen_program_tile_ids:
                    continue
                seen_program_tile_ids.add(tile_id)
                program_tile_order.append(tile_id)
        next_type_data["program_tile_order"] = program_tile_order

    if "program_tile_overrides" in next_type_data:
        raw_program_tile_overrides = next_type_data.get("program_tile_overrides")
        program_tile_overrides: dict[str, dict] = {}
        if isinstance(raw_program_tile_overrides, dict):
            for raw_tile_id, raw_override in raw_program_tile_overrides.items():
                tile_id = str(raw_tile_id or "").strip()
                if not tile_id or not isinstance(raw_override, dict):
                    continue
                program_tile_overrides[tile_id] = {
                    "zoom": _normalize_zoom(raw_override.get("zoom"), default=1.0),
                    "focal_x": _normalize_percent(
                        raw_override.get("focal_x"),
                        default=50.0,
                    ),
                    "focal_y": _normalize_percent(
                        raw_override.get("focal_y"),
                        default=50.0,
                    ),
                    "rotation": _normalize_rotation(raw_override.get("rotation"), default=0.0),
                }
        next_type_data["program_tile_overrides"] = program_tile_overrides

    if "parent_route" in next_type_data:
        raw_parent_route = str(
            next_type_data.get("parent_route")
            or ""
        ).strip()
        if raw_parent_route in {"", "/"}:
            next_type_data["parent_route"] = ""
        else:
            normalized_segments = [
                re.sub(r"[^a-z0-9-]+", "-", segment.lower()).strip("-")
                for segment in raw_parent_route.strip("/").split("/")
            ]
            normalized_segments = [segment for segment in normalized_segments if segment]
            next_type_data["parent_route"] = (
                f"/{'/'.join(normalized_segments)}" if normalized_segments else ""
            )

    if "aspect_ratio" in next_type_data:
        aspect_ratio = next_type_data.get("aspect_ratio")
        next_type_data["aspect_ratio"] = (
            aspect_ratio if aspect_ratio in {"1:1", "3:2", "4:3", "16:9"} else "1:1"
        )

    if "direction" in next_type_data:
        if next_type_data.get("direction") not in {"landscape", "portrait"}:
            next_type_data["direction"] = "landscape"
    return next_type_data


def _normalize_faq_topic_value(value) -> dict[str, str]:
    source = value if isinstance(value, dict) else {}
    return {
        "de": str(source.get("de") or "").strip(),
        "en": str(source.get("en") or "").strip(),
    }


def _normalize_faq_scopes(value) -> list[dict[str, str]]:
    raw_items = value if isinstance(value, list) else [value]
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw_item in raw_items:
        topic = _normalize_faq_topic_value(raw_item)
        key = (topic["de"], topic["en"])
        if not key[0] and not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        normalized.append(topic)
    return normalized


def _normalize_faq_type_data(type_data: dict) -> dict:
    normalized = deepcopy(type_data) if isinstance(type_data, dict) else {}
    raw_scopes = (
        normalized.get("scopes")
        if isinstance(normalized.get("scopes"), list)
        else normalized.get("scope")
    )
    normalized["scopes"] = _normalize_faq_scopes(raw_scopes)
    for key in FAQ_TYPE_DATA_SHARED_PAYLOAD_KEYS + FAQ_TYPE_DATA_CACHE_STATE_KEYS:
        normalized.pop(key, None)
    return normalized


def _normalize_ticker_item_payload(item: dict, index: int) -> dict:
    fallback_id = f"ticker-{index + 1}"
    item_id = str(item.get("id") or fallback_id).strip() or fallback_id
    raw_text = item.get("text")
    if isinstance(raw_text, dict):
        text_payload = {
            "de": str(raw_text.get("de") or ""),
            "en": str(raw_text.get("en") or ""),
        }
    else:
        mirrored = str(raw_text or "")
        text_payload = {"de": mirrored, "en": mirrored}
    return {
        "id": item_id,
        "text": text_payload,
        "timestamp": str(item.get("timestamp") or "").strip(),
    }


def _normalize_ticker_items_payload(items: object) -> list[dict]:
    source = items if isinstance(items, list) else []
    return [
        _normalize_ticker_item_payload(item, index)
        for index, item in enumerate(source)
        if isinstance(item, dict)
    ]


def _has_ticker_item_content(item: dict) -> bool:
    if str(item.get("timestamp") or "").strip():
        return True
    text = item.get("text")
    if not isinstance(text, dict):
        return bool(str(text or "").strip())
    return bool(
        str(text.get("de") or "").strip() or str(text.get("en") or "").strip()
    )


def _normalize_ticker_type_data(type_data: dict) -> dict:
    normalized = deepcopy(type_data) if isinstance(type_data, dict) else {}
    view_mode = str(
        normalized.get("view_mode") or "ticker"
    ).strip().lower()
    view_mode = "updates" if view_mode == "updates" else "ticker"
    items = _normalize_ticker_items_payload(normalized.get("items"))
    legacy_update_items = _normalize_ticker_items_payload(
        normalized.get("update_items")
        if "update_items" in normalized
        else normalized.get("updateItems")
    )

    items_have_content = any(_has_ticker_item_content(item) for item in items)
    legacy_items_have_content = any(
        _has_ticker_item_content(item) for item in legacy_update_items
    )
    if view_mode == "updates" and legacy_items_have_content:
        resolved_items = legacy_update_items
    elif items_have_content or items:
        resolved_items = items
    else:
        resolved_items = legacy_update_items

    normalized["view_mode"] = view_mode
    normalized["items"] = resolved_items
    normalized.pop("update_items", None)
    normalized.pop("updateItems", None)
    normalized.pop("viewMode", None)
    return normalized


def _normalize_section_type_data_for_response(section_type: str, type_data: dict) -> dict:
    if not isinstance(type_data, dict):
        return {}
    normalized_section_type = str(section_type or "").strip().lower()
    if normalized_section_type == "faq":
        return _normalize_faq_type_data(type_data)
    if normalized_section_type == "ticker":
        return _normalize_ticker_type_data(type_data)
    if normalized_section_type == "program":
        normalized = deepcopy(type_data)
        normalized.pop("stages", None)
        normalized.pop("program_gigs_integration_mapping", None)
        normalized.pop("programGigsIntegrationMapping", None)
        normalized.pop("program_gigs_integration_mapping_cache_state", None)
        normalized.pop("programGigsIntegrationMappingCacheState", None)
        normalized.pop("program_stages_integration_mapping", None)
        normalized.pop("programStagesIntegrationMapping", None)
        normalized.pop("program_stages_integration_mapping_cache_state", None)
        normalized.pop("programStagesIntegrationMappingCacheState", None)
        return normalized
    if normalized_section_type == "blog":
        normalized = deepcopy(type_data)
        normalized.pop("items", None)
        normalized.pop("tags", None)
        normalized.pop("blog_items", None)
        normalized.pop("blogItems", None)
        normalized.pop("blog_tags", None)
        normalized.pop("blogTags", None)
        return normalized
    if section_type == "markdown":
        return normalize_markdown_type_data(type_data)
    if section_type == "html":
        return normalize_html_type_data(type_data)
    if section_type == "gallery":
        return _normalize_gallery_type_data(type_data)
    if section_type == "tiles":
        return _normalize_tiles_type_data(type_data)
    return type_data


async def _enrich_section_docs_type_data_with_asset_media(
    db,
    section_docs: list[dict],
) -> None:
    if not isinstance(section_docs, list) or not section_docs:
        return

    image_urls: set[str] = set()
    for section_doc in section_docs:
        if not isinstance(section_doc, dict):
            continue
        type_data = section_doc.get("type_data")
        if not isinstance(type_data, dict):
            continue
        image_urls.update(collect_raster_image_urls_from_payload(type_data))

    if not image_urls:
        return

    asset_docs_by_url = await fetch_asset_docs_by_urls(db, image_urls)
    if not asset_docs_by_url:
        return

    for section_doc in section_docs:
        if not isinstance(section_doc, dict):
            continue
        type_data = section_doc.get("type_data")
        if not isinstance(type_data, dict):
            continue
        enrich_raster_payload_with_asset_docs(type_data, asset_docs_by_url)


def _validate_html_embed_payload(section_type: str, type_data: dict) -> None:
    if str(section_type or "").strip().lower() != "html":
        return
    if not isinstance(type_data, dict):
        return

    mode = str(type_data.get("mode") or "").strip().lower()
    if mode != "embed":
        return

    embed_code = str(type_data.get("embed_code") or "").strip()
    embed_provider = str(type_data.get("embed_provider") or "").strip().lower()
    if not embed_code:
        raise HTTPException(400, "Embed mode requires embed_code")
    allowed_hosts = HTML_EMBED_PROVIDER_HOSTS.get(embed_provider)
    if not allowed_hosts:
        raise HTTPException(400, "Only YouTube and Instagram embeds are allowed")

    matches = EMBED_ATTR_URL_RE.findall(embed_code)
    urls = [str(match or "").strip() for match in matches if str(match or "").strip()]
    if not urls:
        raise HTTPException(400, "Embed code must include at least one valid provider URL")

    for raw_url in urls:
        normalized = raw_url if not raw_url.startswith("//") else f"https:{raw_url}"
        parsed = urlparse(normalized)
        host = str(parsed.hostname or "").strip().lower()
        if not host:
            raise HTTPException(400, "Embed URL host is missing")
        if not any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts):
            raise HTTPException(400, "Embed code contains unsupported host(s)")



def _require_design_write(user: KeycloakUser) -> None:
    if user.has_permission("design:write"):
        return
    raise HTTPException(
        status_code=403,
        detail="Missing required permissions: design:write",
    )


def _db():
    return get_client()[settings.mongo_db]


def _normalize_bilingual_text(value: dict | None) -> dict:
    source = value if isinstance(value, dict) else {}
    return {
        "de": str(source.get("de") or ""),
        "en": str(source.get("en") or ""),
    }


def _serialize_section_doc(doc: dict) -> dict:
    serialized = deepcopy(doc)
    if "_id" in serialized:
        serialized["_id"] = str(serialized["_id"])
    serialized["shared"] = bool(serialized.get("shared", False))
    section_type = str(serialized.get("section_type") or "")
    if section_type == FAQ_SECTION_TYPE:
        for key in FAQ_TOP_LEVEL_CACHE_STATE_KEYS:
            serialized.pop(key, None)
    serialized["type_data"] = _normalize_section_type_data_for_response(
        section_type,
        serialized.get("type_data")
        if isinstance(serialized.get("type_data"), dict)
        else {},
    )
    return serialized


async def _resolve_template_sync_context(db, section_doc: dict) -> tuple[str, str, dict, dict, list[str]]:
    try:
        return await resolve_section_template_sync_context(
            db,
            section_doc,
            type_data_normalizer=_normalize_section_type_data_for_response,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


async def _apply_section_template_design_overrides(
    db,
    *,
    section_id: str,
    section_doc: dict,
    design_overrides: dict | None,
    user: KeycloakUser,
) -> dict:
    _require_design_write(user)

    sections = db["sections"]
    revisions = db["revisions"]
    normalized_overrides = normalize_template_section_design_overrides(design_overrides)
    current_overrides = normalize_template_section_design_overrides(
        section_doc.get("design_overrides")
    )
    if current_overrides == normalized_overrides:
        return section_doc

    patch_set: dict[str, object] = {"updated_at": datetime.utcnow()}
    patch_unset: dict[str, str] = {}

    revision_config = await get_or_create_revision_config(db)
    section_options = get_section_revision_options(
        revision_config,
        section_doc.get("section_type", "text"),
    )
    if section_revision_history_enabled(section_options) and section_options["include_design"]:
        design_snapshot = await capture_section_design_state(
            db,
            section_id,
            section_doc=section_doc,
        )
        revision_data = build_section_revision_snapshot(
            content=None,
            design=design_snapshot,
        )
        new_revision_id = await push_revision_entry(
            revisions,
            entity_type="section",
            entity_id=section_id,
            current_data=revision_data,
            revision_id=as_object_id(section_doc.get("revision_id")),
            saved_by=user.username,
            change_kind="design",
            max_history=REVISION_HISTORY_LIMIT,
        )
        if new_revision_id and new_revision_id != str(section_doc.get("revision_id") or ""):
            patch_set["revision_id"] = new_revision_id

    if normalized_overrides is None:
        patch_unset["design_overrides"] = ""
    else:
        patch_set["design_overrides"] = normalized_overrides

    update: dict[str, dict] = {"$set": patch_set}
    if patch_unset:
        update["$unset"] = patch_unset

    updated = await sections.find_one_and_update(
        {"_id": ObjectId(section_id)},
        update,
        return_document=ReturnDocument.AFTER,
    )
    if not isinstance(updated, dict):
        raise HTTPException(404, "Section not found after design sync")
    return updated


def _parse_saved_at_for_match(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _datetime_to_timestamp_for_match(value: datetime) -> float:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).timestamp()
    return value.timestamp()


def _saved_at_matches(entry_saved_at, target_saved_at) -> bool:
    normalized_entry = normalize_saved_at_label(entry_saved_at)
    normalized_target = normalize_saved_at_label(target_saved_at)
    if normalized_entry and normalized_target and normalized_entry == normalized_target:
        return True

    entry_dt = _parse_saved_at_for_match(entry_saved_at)
    target_dt = _parse_saved_at_for_match(target_saved_at)
    if entry_dt is None or target_dt is None:
        return False
    return (
        abs(
            _datetime_to_timestamp_for_match(entry_dt)
            - _datetime_to_timestamp_for_match(target_dt)
        )
        < 0.001
    )


def _extract_blog_shared_snapshot_from_entry(entry: dict) -> dict | None:
    if not isinstance(entry, dict):
        return None
    content_snapshot, _ = parse_section_revision_snapshot(entry.get("data"))
    if not isinstance(content_snapshot, dict):
        return None
    shared_snapshot = content_snapshot.get("shared_blog_data")
    if not isinstance(shared_snapshot, dict):
        return None
    return deepcopy(shared_snapshot)


def _extract_faq_shared_snapshot_from_entry(entry: dict) -> dict | None:
    if not isinstance(entry, dict):
        return None
    content_snapshot, _ = parse_section_revision_snapshot(entry.get("data"))
    if not isinstance(content_snapshot, dict):
        return None
    shared_snapshot = content_snapshot.get("shared_faq_data")
    if not isinstance(shared_snapshot, dict):
        return None
    return deepcopy(shared_snapshot)


def _extract_program_shared_snapshot_from_entry(entry: dict) -> dict | None:
    if not isinstance(entry, dict):
        return None
    content_snapshot, _ = parse_section_revision_snapshot(entry.get("data"))
    if not isinstance(content_snapshot, dict):
        return None
    shared_snapshot = content_snapshot.get("shared_program_data")
    if not isinstance(shared_snapshot, dict):
        return None
    return deepcopy(shared_snapshot)


async def _resolve_blog_revert_snapshot(
    revisions,
    *,
    section_id: str,
    reverted_from_saved_at: str | None,
) -> dict | None:
    if not reverted_from_saved_at:
        return None

    revision_doc = await revisions.find_one(
        {"entity_type": "section", "entity_id": section_id}
    )
    if not isinstance(revision_doc, dict):
        return None

    stream_order = ("content_history", "content_future", "history", "future")
    for stream_key in stream_order:
        entries = revision_doc.get(stream_key, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            shared_snapshot = _extract_blog_shared_snapshot_from_entry(entry)
            if not isinstance(shared_snapshot, dict):
                continue
            if _saved_at_matches(entry.get("saved_at"), reverted_from_saved_at):
                return shared_snapshot

    return None


async def _resolve_faq_revert_snapshot(
    revisions,
    *,
    section_id: str,
    reverted_from_saved_at: str | None,
) -> dict | None:
    if not reverted_from_saved_at:
        return None

    revision_doc = await revisions.find_one(
        {"entity_type": "section", "entity_id": section_id}
    )
    if not isinstance(revision_doc, dict):
        return None

    stream_order = ("content_history", "content_future", "history", "future")
    for stream_key in stream_order:
        entries = revision_doc.get(stream_key, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            shared_snapshot = _extract_faq_shared_snapshot_from_entry(entry)
            if not isinstance(shared_snapshot, dict):
                continue
            if _saved_at_matches(entry.get("saved_at"), reverted_from_saved_at):
                return shared_snapshot

    return None


async def _resolve_program_revert_snapshot(
    revisions,
    *,
    section_id: str,
    reverted_from_saved_at: str | None,
) -> dict | None:
    if not reverted_from_saved_at:
        return None

    revision_doc = await revisions.find_one(
        {"entity_type": "section", "entity_id": section_id}
    )
    if not isinstance(revision_doc, dict):
        return None

    stream_order = ("content_history", "content_future", "history", "future")
    for stream_key in stream_order:
        entries = revision_doc.get(stream_key, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            shared_snapshot = _extract_program_shared_snapshot_from_entry(entry)
            if not isinstance(shared_snapshot, dict):
                continue
            if _saved_at_matches(entry.get("saved_at"), reverted_from_saved_at):
                return shared_snapshot

    return None


async def _build_section_revision_data(
    db,
    section_doc: dict,
    *,
    include_content: bool,
    include_design: bool,
    blog_shared_content_override: dict | None = None,
    faq_shared_content_override: dict | None = None,
    program_shared_content_override: dict | None = None,
) -> dict:
    content_snapshot = None
    if include_content:
        shared_blog_content = None
        shared_faq_content = None
        shared_program_content = None
        if str(section_doc.get("section_type") or "") == BLOG_SECTION_TYPE:
            if isinstance(blog_shared_content_override, dict):
                shared_blog_content = deepcopy(blog_shared_content_override)
            else:
                shared_blog_content = await capture_blog_shared_content(db)
        if str(section_doc.get("section_type") or "") == FAQ_SECTION_TYPE:
            if isinstance(faq_shared_content_override, dict):
                shared_faq_content = deepcopy(faq_shared_content_override)
            else:
                shared_faq_content = await capture_faq_shared_content(db)
        if str(section_doc.get("section_type") or "") == PROGRAM_SECTION_TYPE:
            if isinstance(program_shared_content_override, dict):
                shared_program_content = deepcopy(program_shared_content_override)
            else:
                shared_program_content = await capture_program_shared_content(db)
        content_snapshot = build_section_content_snapshot(
            section_doc,
            exclude_keys=SECTION_REVISION_EXCLUDE_KEYS,
            shared_blog_content=shared_blog_content,
            shared_faq_content=shared_faq_content,
            shared_program_content=shared_program_content,
        )
    design_snapshot = None
    if include_design:
        design_snapshot = await capture_section_design_state(
            db,
            str(section_doc["_id"]),
            section_doc=section_doc,
        )
    return build_section_revision_snapshot(
        content=content_snapshot,
        design=design_snapshot,
    )


async def _push_to_history(
    section_id: str,
    current_data: dict,
    revision_id: str | None,
    saved_by: str | None = None,
    change_kind: str | None = None,
    reverted_from_saved_at: str | None = None,
):
    """Push current state to history, clear future, trim to MAX_HISTORY."""
    revisions = _db()["revisions"]
    return await push_revision_entry(
        revisions,
        entity_type="section",
        entity_id=section_id,
        current_data=current_data,
        revision_id=as_object_id(revision_id),
        saved_by=saved_by,
        change_kind=change_kind,
        reverted_from_saved_at=reverted_from_saved_at,
        max_history=MAX_HISTORY,
    )


# -------------------------
# CRUD endpoints
# -------------------------


@router.get(
    "/types",
    dependencies=[Depends(require_permission("content:read"))],
)
async def list_section_types():
    """Get all available section types and their schemas."""
    types_info = []
    for type_name, schema_class in SECTION_TYPE_SCHEMAS.items():
        types_info.append(
            {
                "type": type_name,
                "schema": schema_class.model_json_schema(),
                "default_data": get_default_type_data(type_name),
            }
        )
    return {"types": types_info}


# -------------------------
# Markdown parsing endpoint
# -------------------------


class MarkdownParseRequest(BaseModel):
    """Request body for markdown parsing."""

    source_url: str | None = None  # URL to fetch markdown/HTML from
    raw_content: str | None = None  # Raw markdown/HTML content
    source_type: str = "markdown"  # "markdown", "html", or "raw"
    html_selector: str | None = (
        None  # CSS selector to scope HTML (e.g., "main", "#content")
    )


class MarkdownParseResponse(BaseModel):
    """Response with rendered HTML."""

    rendered_html: str
    source_type: str
    selector_found: bool = True  # Whether the selector was found (if specified)


def extract_html_by_selector(html_content: str, selector: str) -> tuple[str, bool]:
    """Extract HTML content matching a CSS selector.

    Args:
        html_content: The full HTML content
        selector: CSS selector (e.g., "main", "#content", ".article-body")

    Returns:
        Tuple of (extracted HTML string, whether selector was found)
    """
    soup = BeautifulSoup(html_content, "lxml")

    # Try to find the element matching the selector
    element = soup.select_one(selector)

    if element:
        # Return the inner HTML of the matched element
        return str(element), True
    else:
        # Selector not found, return original content
        return html_content, False


@router.post(
    "/parse-markdown",
    response_model=MarkdownParseResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def parse_markdown(payload: MarkdownParseRequest):
    """Parse markdown or HTML content and return rendered HTML.

    Accepts either a URL to fetch content from, or raw content directly.
    For HTML files, the content is returned as-is (sanitized).
    For markdown, it's converted to HTML.

    If html_selector is provided and source is HTML, only content matching
    the selector will be extracted (e.g., "main" to get only <main> content).
    """
    content = ""
    source_type = payload.source_type

    # Fetch content from URL if provided
    if payload.source_url:
        try:
            source_url = _normalize_fetch_source_url(payload.source_url)
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(source_url)
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > MARKDOWN_FETCH_MAX_BYTES:
                            raise HTTPException(
                                400,
                                f"Fetched content is too large (max {MARKDOWN_FETCH_MAX_BYTES} bytes)",
                            )
                    except ValueError:
                        pass

                raw_bytes = response.content
                if len(raw_bytes) > MARKDOWN_FETCH_MAX_BYTES:
                    raise HTTPException(
                        400, f"Fetched content is too large (max {MARKDOWN_FETCH_MAX_BYTES} bytes)"
                    )
                content = response.text

                # Auto-detect type from URL extension if not specified
                url_lower = source_url.lower()
                if url_lower.endswith(".html") or url_lower.endswith(".htm"):
                    source_type = "html"
                elif url_lower.endswith(".md") or url_lower.endswith(".markdown"):
                    source_type = "markdown"
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                400, f"Failed to fetch URL: HTTP {e.response.status_code}"
            )
        except httpx.RequestError as e:
            raise HTTPException(400, f"Failed to fetch URL: {str(e)}")
    elif payload.raw_content:
        content = payload.raw_content
    else:
        raise HTTPException(400, "Either source_url or raw_content must be provided")

    selector_found = True

    # Parse content based on type
    if source_type == "html":
        # Apply selector if provided
        if payload.html_selector and payload.html_selector.strip():
            content, selector_found = extract_html_by_selector(
                content, payload.html_selector.strip()
            )
        rendered_html = content
    else:
        # For markdown, convert to HTML
        md_parser.reset()
        rendered_html = md_parser.convert(content)

    return MarkdownParseResponse(
        rendered_html=rendered_html,
        source_type=source_type,
        selector_found=selector_found,
    )


@router.post(
    "",
    response_model=SectionDB,
    dependencies=[Depends(require_permission("content:write"))],
)
async def create_section(payload: SectionCreate):
    """Create a new standalone section."""
    db = _db()
    sections = db["sections"]

    now = datetime.utcnow()
    title_dict = payload.title.model_dump() if payload.title else {"de": "", "en": ""}
    section_type = payload.section_type or "text"
    type_data = (
        payload.type_data if payload.type_data else get_default_type_data(section_type)
    )
    section_type, type_data = migrate_document_section_payload(section_type, type_data)
    type_data = normalize_section_description_payload(section_type, type_data)
    type_data = _normalize_section_type_data_for_response(section_type, type_data)
    _validate_html_embed_payload(section_type, type_data)

    doc = {
        "section_type": section_type,
        "shared": bool(payload.shared),
        "section_template_name": "default",
        "title_placeholder": payload.title_placeholder,
        "title": title_dict,
        "type_data": type_data,
        "section_integration_mapping": normalize_section_integration_mapping(
            payload.section_integration_mapping
        ),
        "revision_id": None,
        "created_at": now,
        "updated_at": now,
    }
    res = await sections.insert_one(doc)
    doc["_id"] = res.inserted_id

    if section_type == BLOG_SECTION_TYPE:
        await sync_all_blog_items_for_section(db, doc)

    doc["_id"] = str(doc["_id"])
    await _enrich_section_docs_type_data_with_asset_media(db, [doc])
    return doc


@router.get("", response_model=list[SectionDB])
async def list_sections(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None, description="ISO datetime for pagination"),
    search: str | None = Query(default=None, description="Search in title_placeholder"),
    section_type: str | None = Query(
        default=None, description="Filter by section type"
    ),
    shared_only: bool = Query(default=False, description="Only return shared reusable sections"),
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    """List all sections with optional filtering."""
    db = _db()
    sections = db["sections"]

    q: dict = {}
    if cursor:
        q["updated_at"] = {"$lt": datetime.fromisoformat(cursor)}
    if search:
        q["title_placeholder"] = {"$regex": search, "$options": "i"}
    if section_type:
        q["section_type"] = section_type
    if shared_only:
        q["shared"] = True

    docs = (
        await sections.find(q).sort("updated_at", -1).limit(limit).to_list(length=limit)
    )
    for d in docs:
        d["_id"] = str(d["_id"])
        d["shared"] = bool(d.get("shared", False))
        section_type = str(d.get("section_type") or "")
        d["type_data"] = _normalize_section_type_data_for_response(
            section_type,
            d.get("type_data") if isinstance(d.get("type_data"), dict) else {},
        )
    await _enrich_section_docs_type_data_with_asset_media(db, docs)
    return docs


@router.get("/with-usage")
async def list_sections_with_usage(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, description="Search in title_placeholder"),
    section_type: str | None = Query(
        default=None, description="Filter by section type"
    ),
    shared_only: bool = Query(default=False, description="Only return shared reusable sections"),
    sort_by: str = Query(
        default="updated_at",
        description="Sort field: created_at, updated_at, name, or legacy field_direction value.",
    ),
    sort_direction: str = Query(default="desc", description="Sort direction: asc or desc"),
    include_total: bool = Query(default=False),
    type_data_mode: str = Query(
        default="admin_todos",
        alias="type_data",
        description="Payload detail for type_data: admin_todos, none, or full.",
    ),
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    """List all sections with usage information (which pages use them)."""
    db = _db()
    sections_coll = db["sections"]
    pages_coll = db["pages"]
    normalized_type_data_mode = str(type_data_mode or "admin_todos").strip().lower()
    if normalized_type_data_mode not in {"admin_todos", "none", "full"}:
        raise HTTPException(400, "type_data must be one of: admin_todos, none, full")

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
        "name": "title_placeholder",
        "title": "title_placeholder",
    }
    sort_field = sort_field_map.get(normalized_sort_by)
    if sort_field is None:
        raise HTTPException(400, "sort_by must be one of: created_at, updated_at, name")
    if normalized_sort_direction not in {"asc", "desc"}:
        raise HTTPException(400, "sort_direction must be asc or desc")
    sort_order = 1 if normalized_sort_direction == "asc" else -1
    sort_spec = [(sort_field, sort_order)]
    if sort_field == "title_placeholder":
        sort_spec = [
            ("title_placeholder", sort_order),
            ("title.de", sort_order),
            ("title.en", sort_order),
            ("updated_at", -1),
        ]

    # Build query for sections
    q: dict = {}
    if search:
        q["title_placeholder"] = {"$regex": search, "$options": "i"}
    if section_type:
        q["section_type"] = section_type
    if shared_only:
        q["shared"] = True
    total_count = await sections_coll.count_documents(q) if include_total else None

    # Get sections. DevOps only needs todo metadata, so keep the default
    # response small enough for constrained deployment containers.
    section_projection = None
    if normalized_type_data_mode != "full":
        section_projection = {
            "section_type": 1,
            "shared": 1,
            "title_placeholder": 1,
            "title": 1,
            "created_at": 1,
            "updated_at": 1,
        }
        if normalized_type_data_mode == "admin_todos":
            section_projection["type_data.admin_todos"] = 1

    section_cursor = (
        sections_coll.find(q, section_projection)
        if section_projection is not None
        else sections_coll.find(q)
    )
    sections = (
        await section_cursor
        .sort(sort_spec)
        .skip(offset)
        .limit(limit)
        .to_list(length=limit)
    )

    # Get all pages to find section usage
    pages = await pages_coll.find(
        {},
        {
            "slug": 1,
            "sections": 1,
            "template_managed": 1,
            "template_managed_section_ids": 1,
        },
    ).to_list(length=1000)

    # Build a map of section_id -> list of pages that use it
    section_usage: dict[str, list[dict]] = {}
    generated_section_ids: set[str] = set()
    for page in pages:
        page_slug = page.get("slug", "")
        page_sections = page.get("sections")
        is_generated_page = page.get("template_managed") is True
        managed_section_ids = page.get("template_managed_section_ids")
        if is_generated_page and isinstance(managed_section_ids, list):
            for section_id in managed_section_ids:
                normalized_section_id = str(section_id or "").strip()
                if normalized_section_id:
                    generated_section_ids.add(normalized_section_id)
        if not isinstance(page_sections, list):
            continue
        for ref in page_sections:
            if not isinstance(ref, dict):
                continue
            section_id = str(ref.get("section_id") or "").strip()
            if section_id:
                if is_generated_page and not isinstance(managed_section_ids, list):
                    generated_section_ids.add(section_id)
                if section_id not in section_usage:
                    section_usage[section_id] = []
                section_usage[section_id].append(
                    {
                        "slug": page_slug,
                        "visible": ref.get("visible", True),
                        "order": ref.get("order", 0),
                    }
                )

    # Enrich sections with usage info.
    if normalized_type_data_mode == "full":
        for section in sections:
            section_type = str(section.get("section_type") or "")
            section["type_data"] = _normalize_section_type_data_for_response(
                section_type,
                section.get("type_data") if isinstance(section.get("type_data"), dict) else {},
            )
        await _enrich_section_docs_type_data_with_asset_media(db, sections)
    else:
        for section in sections:
            type_data = section.get("type_data") if isinstance(section.get("type_data"), dict) else {}
            admin_todos = type_data.get("admin_todos") if isinstance(type_data.get("admin_todos"), list) else []
            section["type_data"] = (
                {"admin_todos": admin_todos}
                if normalized_type_data_mode == "admin_todos"
                else {}
            )

    result = []
    for section in sections:
        section_id = str(section["_id"])
        section["_id"] = section_id
        section["shared"] = bool(section.get("shared", False))
        usage = section_usage.get(section_id, [])
        result.append(
            {
                **section,
                "is_generated": section_id in generated_section_ids,
                "usage": usage,
                "usage_count": len(usage),
            }
        )

    if include_total:
        return {
            "items": result,
            "total": total_count if total_count is not None else len(result),
            "limit": limit,
            "offset": offset,
        }

    return result


def _section_ids_to_object_ids(section_ids: list) -> list[ObjectId]:
    object_ids: list[ObjectId] = []
    for section_id in section_ids:
        section_id_str = str(section_id or "").strip()
        if ObjectId.is_valid(section_id_str):
            object_ids.append(ObjectId(section_id_str))
    return object_ids


async def _build_unused_sections_query(db) -> dict:
    pages = db["pages"]
    page_section_ids = await pages.distinct(
        "sections.section_id",
        {"sections.section_id": {"$nin": [None, ""]}},
    )
    used_section_oids = _section_ids_to_object_ids(page_section_ids)

    q: dict = {"shared": {"$ne": True}}
    if used_section_oids:
        q["_id"] = {"$nin": used_section_oids}
    return q


@router.get(
    "/unused/count",
    dependencies=[Depends(require_permission("content:write"))],
)
async def count_unused_sections():
    """Count sections that are not shared and are not referenced by any page."""
    db = _db()
    q = await _build_unused_sections_query(db)
    count = await db["sections"].count_documents(q)
    return {"count": count}


@router.delete(
    "/unused",
    dependencies=[Depends(require_permission("content:write"))],
)
async def delete_unused_sections():
    """Delete sections that are not shared and are not referenced by any page."""
    db = _db()
    sections = db["sections"]
    revisions = db["revisions"]
    pages = db["pages"]

    q = await _build_unused_sections_query(db)
    candidates = await sections.find(q, {"_id": 1}).to_list(length=None)
    section_oids = [doc["_id"] for doc in candidates]
    if not section_oids:
        return {"deleted_count": 0, "deleted_ids": []}

    deleted_ids: list[str] = []
    for section_oid in section_oids:
        section_id = str(section_oid)
        if await pages.find_one({"sections.section_id": section_id}, {"_id": 1}):
            continue
        deleted = await sections.find_one_and_delete(
            {"_id": section_oid, "shared": {"$ne": True}},
            projection={"_id": 1},
        )
        if deleted:
            deleted_ids.append(section_id)

    if deleted_ids:
        await revisions.delete_many({"entity_type": "section", "entity_id": {"$in": deleted_ids}})

    return {"deleted_count": len(deleted_ids), "deleted_ids": deleted_ids}


@router.get("/{section_id}/usage")
async def get_section_usage(
    section_id: str,
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    """Get detailed usage information for a section (which pages use it)."""
    db = _db()
    sections_coll = db["sections"]
    pages_coll = db["pages"]

    # Verify section exists
    section = await sections_coll.find_one({"_id": ObjectId(section_id)})
    if not section:
        raise HTTPException(404, "Section not found")

    # Find all pages that reference this section
    pages = await pages_coll.find({"sections.section_id": section_id}).to_list(
        length=100
    )

    usage = []
    for page in pages:
        page_sections = page.get("sections", [])
        for ref in page_sections:
            if ref.get("section_id") == section_id:
                usage.append(
                    {
                        "page_id": str(page["_id"]),
                        "slug": page.get("slug", ""),
                        "visible": ref.get("visible", True),
                        "order": ref.get("order", 0),
                    }
                )
                break

    return {
        "section_id": section_id,
        "usage": usage,
        "usage_count": len(usage),
        "can_delete": len(usage) == 0,
    }


@router.get("/{section_id}", response_model=SectionDB)
async def get_section(
    section_id: str,
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    """Get a single section by ID."""
    db = _db()
    sections = db["sections"]
    doc = await sections.find_one({"_id": ObjectId(section_id)})
    if not doc:
        raise HTTPException(404, "Section not found")
    doc = _serialize_section_doc(doc)
    await _enrich_section_docs_type_data_with_asset_media(db, [doc])
    return doc


@router.get(
    "/{section_id}/template-sync-preview",
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_section_template_sync_preview(section_id: str):
    db = _db()
    sections = db["sections"]
    try:
        oid = ObjectId(section_id)
    except Exception as exc:
        raise HTTPException(400, "Invalid section ID") from exc

    section_doc = await sections.find_one({"_id": oid})
    if not isinstance(section_doc, dict):
        raise HTTPException(404, "Section not found")

    (
        section_type,
        template_name,
        _template_payload,
        _current_payload,
        changed_fields,
    ) = await _resolve_template_sync_context(db, section_doc)

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


@router.post(
    "/{section_id}/sync-from-template",
    dependencies=[Depends(require_permission("content:write"))],
)
async def sync_section_from_template(
    section_id: str,
    user: KeycloakUser = Depends(get_current_user),
):
    db = _db()
    sections = db["sections"]
    try:
        oid = ObjectId(section_id)
    except Exception as exc:
        raise HTTPException(400, "Invalid section ID") from exc

    section_doc = await sections.find_one({"_id": oid})
    if not isinstance(section_doc, dict):
        raise HTTPException(404, "Section not found")

    (
        section_type,
        template_name,
        template_payload,
        _current_payload,
        changed_fields,
    ) = await _resolve_template_sync_context(db, section_doc)

    if not changed_fields:
        serialized_section = _serialize_section_doc(section_doc)
        await _enrich_section_docs_type_data_with_asset_media(db, [serialized_section])
        return {
            "updated": False,
            "changed_fields": [],
            "template_ref": f"{section_type}/{template_name}",
            "section": serialized_section,
        }

    design_changed = "design_overrides" in changed_fields
    if design_changed:
        _require_design_write(user)

    content_changed_fields = [
        field for field in changed_fields if field != "design_overrides"
    ]
    updated_raw_doc = section_doc
    if content_changed_fields:
        payload = SectionCreate(
            section_type=section_type,
            title_placeholder=template_payload["title_placeholder"],
            title=template_payload["title"],
            type_data=template_payload["type_data"],
            section_integration_mapping=template_payload["section_integration_mapping"],
        )
        updated = await replace_section(section_id, payload, user)
        refreshed = await sections.find_one({"_id": oid})
        if isinstance(refreshed, dict):
            updated_raw_doc = refreshed
        elif isinstance(updated, dict):
            updated_raw_doc = updated

    if design_changed:
        updated_raw_doc = await _apply_section_template_design_overrides(
            db,
            section_id=section_id,
            section_doc=updated_raw_doc,
            design_overrides=template_payload.get("design_overrides"),
            user=user,
        )

    updated_doc = _serialize_section_doc(updated_raw_doc)
    await _enrich_section_docs_type_data_with_asset_media(db, [updated_doc])

    return {
        "updated": True,
        "changed_fields": changed_fields,
        "template_ref": f"{section_type}/{template_name}",
        "section": updated_doc,
    }


@router.put(
    "/{section_id}",
    response_model=SectionDB,
    dependencies=[Depends(require_permission("content:write"))],
)
async def replace_section(
    section_id: str,
    payload: SectionCreate,
    user: KeycloakUser = Depends(get_current_user),
):
    """Replace a section entirely, saving current state to history."""
    db = _db()
    sections = db["sections"]

    current = await sections.find_one({"_id": ObjectId(section_id)})
    if not current:
        raise HTTPException(404, "Section not found")

    revision_id = current.get("revision_id")
    new_revision_id = None

    revision_config = await get_or_create_revision_config(db)
    section_options = get_section_revision_options(
        revision_config,
        current.get("section_type", "text"),
    )
    include_content_snapshot = bool(section_options["include_content"])
    include_design_snapshot = False

    now = datetime.utcnow()
    title_dict = payload.title.model_dump() if payload.title else {"de": "", "en": ""}
    section_type = payload.section_type or current.get("section_type", "text")
    type_data = (
        payload.type_data if payload.type_data else get_default_type_data(section_type)
    )
    section_type, type_data = migrate_document_section_payload(section_type, type_data)
    type_data = normalize_section_description_payload(section_type, type_data)
    type_data = _normalize_section_type_data_for_response(section_type, type_data)
    _validate_html_embed_payload(section_type, type_data)

    patch = {
        "section_type": section_type,
        "title_placeholder": payload.title_placeholder,
        "title": title_dict,
        "type_data": type_data,
        "section_integration_mapping": normalize_section_integration_mapping(
            payload.section_integration_mapping
        ),
        "updated_at": now,
    }
    if "shared" in payload.model_fields_set:
        patch["shared"] = bool(payload.shared)
    if section_revision_history_enabled(section_options) and (
        include_content_snapshot or include_design_snapshot
    ):
        current_data = await _build_section_revision_data(
            db,
            current,
            include_content=include_content_snapshot,
            include_design=include_design_snapshot,
        )
        next_doc = deepcopy(current)
        next_doc.update(patch)
        next_data = await _build_section_revision_data(
            db,
            next_doc,
            include_content=include_content_snapshot,
            include_design=include_design_snapshot,
        )
        if not snapshots_equal(current_data, next_data):
            new_revision_id = await _push_to_history(
                section_id,
                current_data,
                revision_id,
                saved_by=user.username,
                change_kind="content",
            )
    if new_revision_id:
        patch["revision_id"] = new_revision_id

    doc = await sections.find_one_and_update(
        {"_id": ObjectId(section_id)},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )

    if str(doc.get("section_type") or "") == BLOG_SECTION_TYPE:
        await sync_all_blog_items_for_section(db, doc)

    doc = _serialize_section_doc(doc)
    await _enrich_section_docs_type_data_with_asset_media(db, [doc])
    return doc


@router.patch(
    "/{section_id}",
    response_model=SectionDB,
    dependencies=[Depends(require_permission("content:write"))],
)
async def update_section(
    section_id: str,
    payload: SectionUpdate,
    user: KeycloakUser = Depends(get_current_user),
):
    """Partially update a section, saving current state to history."""
    db = _db()
    sections = db["sections"]
    revisions = db["revisions"]

    current = await sections.find_one({"_id": ObjectId(section_id)})
    if not current:
        raise HTTPException(404, "Section not found")

    # Build patch from provided fields
    patch: dict = {}
    if payload.section_type is not None:
        patch["section_type"] = payload.section_type
    if payload.title_placeholder is not None:
        patch["title_placeholder"] = payload.title_placeholder
    if payload.title is not None:
        patch["title"] = payload.title.model_dump()
    if payload.section_integration_mapping is not None:
        patch["section_integration_mapping"] = normalize_section_integration_mapping(
            payload.section_integration_mapping
        )
    if payload.shared is not None:
        patch["shared"] = bool(payload.shared)
    incoming_type_data = payload.type_data if isinstance(payload.type_data, dict) else None
    target_section_type = payload.section_type or current.get("section_type", "text")
    normalized_incoming_type_data = None
    if payload.type_data is not None:
        # PATCH semantics: merge incoming type_data into existing payload
        # so content updates do not wipe design keys and vice versa.
        merged_type_data = (
            deepcopy(current.get("type_data"))
            if isinstance(current.get("type_data"), dict)
            else {}
        )
        if isinstance(incoming_type_data, dict):
            for key, value in incoming_type_data.items():
                merged_type_data[key] = value
        target_section_type, merged_type_data = migrate_document_section_payload(
            target_section_type,
            merged_type_data,
        )
        merged_type_data = normalize_section_description_payload(
            target_section_type,
            merged_type_data,
        )
        patch["section_type"] = target_section_type
        merged_type_data = _normalize_section_type_data_for_response(
            target_section_type,
            merged_type_data,
        )
        _validate_html_embed_payload(target_section_type, merged_type_data)
        patch["type_data"] = merged_type_data
        normalized_incoming_type_data = merged_type_data

    if not patch:
        raise HTTPException(400, "No fields to update")

    revision_id = current.get("revision_id")
    new_revision_id = None
    requested_change_kind = payload.revision_change_kind or _infer_change_kind_from_patch(
        current.get("section_type", ""),
        {"type_data": normalized_incoming_type_data}
        if normalized_incoming_type_data is not None
        else patch,
    )
    if requested_change_kind in {"design", "both"}:
        _require_design_write(user)

    revision_config = await get_or_create_revision_config(db)
    section_options = get_section_revision_options(
        revision_config,
        current.get("section_type", "text"),
    )
    include_content_snapshot = bool(section_options["include_content"])
    include_design_snapshot = bool(section_options["include_design"])
    reverted_blog_shared_snapshot = None
    reverted_faq_shared_snapshot = None
    reverted_program_shared_snapshot = None
    if (
        str(current.get("section_type") or "") == FAQ_SECTION_TYPE
        and bool(payload.revision_reverted_from_saved_at)
        and include_content_snapshot
    ):
        reverted_faq_shared_snapshot = await _resolve_faq_revert_snapshot(
            revisions,
            section_id=section_id,
            reverted_from_saved_at=payload.revision_reverted_from_saved_at,
        )
    if (
        str(current.get("section_type") or "") == BLOG_SECTION_TYPE
        and bool(payload.revision_reverted_from_saved_at)
        and include_content_snapshot
    ):
        reverted_blog_shared_snapshot = await _resolve_blog_revert_snapshot(
            revisions,
            section_id=section_id,
            reverted_from_saved_at=payload.revision_reverted_from_saved_at,
        )
    if (
        str(current.get("section_type") or "") == PROGRAM_SECTION_TYPE
        and bool(payload.revision_reverted_from_saved_at)
        and include_content_snapshot
    ):
        reverted_program_shared_snapshot = await _resolve_program_revert_snapshot(
            revisions,
            section_id=section_id,
            reverted_from_saved_at=payload.revision_reverted_from_saved_at,
        )

    if section_revision_history_enabled(section_options) and (
        include_content_snapshot or include_design_snapshot
    ):
        current_data = await _build_section_revision_data(
            db,
            current,
            include_content=include_content_snapshot,
            include_design=include_design_snapshot,
        )
        next_doc = deepcopy(current)
        next_doc.update(patch)
        next_data = await _build_section_revision_data(
            db,
            next_doc,
            include_content=include_content_snapshot,
            include_design=include_design_snapshot,
            blog_shared_content_override=reverted_blog_shared_snapshot,
            faq_shared_content_override=reverted_faq_shared_snapshot,
            program_shared_content_override=reverted_program_shared_snapshot,
        )
        if not snapshots_equal(current_data, next_data):
            effective_change_kind = resolve_effective_change_kind(
                current_data=current_data,
                next_data=next_data,
                parse_snapshot=parse_section_revision_snapshot,
                requested_kind=requested_change_kind,
            )
            if effective_change_kind in {"design", "both"}:
                _require_design_write(user)

            include_content_for_entry = (
                include_content_snapshot
                and effective_change_kind in {"content", "both"}
            )
            include_design_for_entry = (
                include_design_snapshot
                and effective_change_kind in {"design", "both"}
            )
            current_content_snapshot, current_design_snapshot = parse_section_revision_snapshot(
                current_data
            )
            current_data_for_history = build_section_revision_snapshot(
                content=(
                    current_content_snapshot
                    if include_content_for_entry and isinstance(current_content_snapshot, dict)
                    else None
                ),
                design=(
                    current_design_snapshot
                    if include_design_for_entry and isinstance(current_design_snapshot, dict)
                    else None
                ),
            )
            shared_blog_changed = False
            shared_faq_changed = False
            if (
                str(current.get("section_type") or "") == BLOG_SECTION_TYPE
                and include_content_for_entry
                and isinstance(reverted_blog_shared_snapshot, dict)
            ):
                current_shared_blog_snapshot = (
                    current_content_snapshot.get("shared_blog_data")
                    if isinstance(current_content_snapshot, dict)
                    else None
                )
                shared_blog_changed = (
                    isinstance(current_shared_blog_snapshot, dict)
                    and not snapshots_equal(
                        current_shared_blog_snapshot,
                        reverted_blog_shared_snapshot,
                    )
                )
            if (
                str(current.get("section_type") or "") == FAQ_SECTION_TYPE
                and include_content_for_entry
                and isinstance(reverted_faq_shared_snapshot, dict)
            ):
                current_shared_faq_snapshot = (
                    current_content_snapshot.get("shared_faq_data")
                    if isinstance(current_content_snapshot, dict)
                    else None
                )
                shared_faq_changed = (
                    isinstance(current_shared_faq_snapshot, dict)
                    and not snapshots_equal(
                        current_shared_faq_snapshot,
                        reverted_faq_shared_snapshot,
                    )
                )
            shared_program_changed = False
            if (
                str(current.get("section_type") or "") == PROGRAM_SECTION_TYPE
                and include_content_for_entry
                and isinstance(reverted_program_shared_snapshot, dict)
            ):
                current_shared_program_snapshot = (
                    current_content_snapshot.get("shared_program_data")
                    if isinstance(current_content_snapshot, dict)
                    else None
                )
                shared_program_changed = (
                    isinstance(current_shared_program_snapshot, dict)
                    and not snapshots_equal(
                        current_shared_program_snapshot,
                        reverted_program_shared_snapshot,
                    )
                )
            if shared_blog_changed:
                await push_blog_shared_content_revisions(
                    db,
                    saved_by=user.username,
                    max_history=MAX_HISTORY,
                    exclude_section_ids={section_id},
                )
            if shared_faq_changed:
                await push_faq_shared_content_revisions(
                    db,
                    saved_by=user.username,
                    max_history=MAX_HISTORY,
                    exclude_section_ids={section_id},
                )
            if shared_program_changed:
                await push_program_shared_content_revisions(
                    db,
                    saved_by=user.username,
                    max_history=MAX_HISTORY,
                    exclude_section_ids={section_id},
                )
            if include_content_for_entry or include_design_for_entry:
                new_revision_id = await _push_to_history(
                    section_id,
                    current_data_for_history,
                    revision_id,
                    saved_by=user.username,
                    change_kind=effective_change_kind,
                    reverted_from_saved_at=payload.revision_reverted_from_saved_at,
                )

    if new_revision_id:
        patch["revision_id"] = new_revision_id
    content_fields_updated = any(
        field in patch
        for field in (
            "section_type",
            "title_placeholder",
            "title",
            "type_data",
            "section_integration_mapping",
        )
    )
    patch["updated_at"] = datetime.utcnow()

    doc = await sections.find_one_and_update(
        {"_id": ObjectId(section_id)},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    if isinstance(reverted_blog_shared_snapshot, dict):
        await apply_blog_shared_content(
            db,
            reverted_blog_shared_snapshot,
        )
    if isinstance(reverted_faq_shared_snapshot, dict):
        await apply_faq_shared_content(
            db,
            reverted_faq_shared_snapshot,
        )
    if isinstance(reverted_program_shared_snapshot, dict):
        await apply_program_shared_content(
            db,
            reverted_program_shared_snapshot,
        )

    if content_fields_updated and str(doc.get("section_type") or "") == BLOG_SECTION_TYPE:
        await sync_all_blog_items_for_section(db, doc)

    try:
        await sync_generated_item_page_review_overrides_for_saved_targets(
            db,
            collection="section",
            document_id=section_id,
            saved_doc=doc,
            updated_paths=set(patch.keys()),
        )
    except Exception:
        logger.warning(
            "generated_item_page.review_override_section_sync_failed section_id=%s",
            section_id,
            exc_info=True,
        )

    doc = _serialize_section_doc(doc)
    await _enrich_section_docs_type_data_with_asset_media(db, [doc])
    return doc


@router.post(
    "/{section_id}/item-pages/generate",
    dependencies=[Depends(require_permission("content:write"))],
)
async def generate_section_item_pages(
    section_id: str,
    item_kind: str | None = Query(default=None),
    item_id: str | None = Query(default=None),
    force_rebuild: bool = Query(default=False),
    sync_mode: str | None = Query(default=None),
):
    db = _db()
    sections = db["sections"]
    try:
        oid = ObjectId(section_id)
    except Exception as exc:
        raise HTTPException(400, "Invalid section ID") from exc
    section = await sections.find_one({"_id": oid})
    if not section:
        raise HTTPException(404, "Section not found")

    section_type = str(section.get("section_type") or "")

    if section_type == BLOG_SECTION_TYPE:
        normalized_item_id = str(item_id or "").strip()
        if normalized_item_id:
            active_template = await resolve_active_item_page_template(db, "blog", "item")
            parent_route = (
                normalize_parent_route(active_template.get("effective_parent_route"))
                if isinstance(active_template, dict)
                else None
            )
            if not parent_route:
                return {
                    "section_id": section_id,
                    "section_type": BLOG_SECTION_TYPE,
                    "generated_count": 0,
                    "warnings": [],
                    "parent_route": None,
                    "item_kind": "item",
                    "item_id": normalized_item_id,
                    "slug": None,
                    "skipped": True,
                }
            generated_slug = await sync_blog_item_page_by_id(
                db,
                normalized_item_id,
                force_rebuild=force_rebuild,
            )
            warnings: list[dict] = []
            if not generated_slug:
                warnings.append(
                    {
                        "code": "item_generation_skipped",
                        "message": f'No generated page could be created for blog item "{normalized_item_id}".',
                    }
                )
            return {
                "section_id": section_id,
                "section_type": BLOG_SECTION_TYPE,
                "generated_count": 1 if generated_slug else 0,
                "warnings": warnings,
                "parent_route": parent_route,
                "item_kind": "item",
                "item_id": normalized_item_id,
                "slug": generated_slug,
            }

        report = await sync_all_blog_items_for_section_report(
            db,
            section,
            force_rebuild=force_rebuild,
        )
        return {
            "section_id": section_id,
            "section_type": BLOG_SECTION_TYPE,
            **report,
        }

    if section_type == PROGRAM_SECTION_TYPE:
        normalized_kind = str(item_kind or "").strip().lower()
        normalized_item_id = str(item_id or "").strip()
        if normalized_kind and normalized_kind not in {"all", "stage", "gig"}:
            raise HTTPException(400, "item_kind must be 'stage', 'gig', or 'all'.")
        if normalized_item_id and normalized_kind not in {"stage", "gig"}:
            raise HTTPException(
                400,
                "item_kind must be 'stage' or 'gig' when item_id is provided.",
            )
        if normalized_kind == "stage":
            report = await sync_program_stage_section_pages_report(
                db,
                section,
                item_id=normalized_item_id or None,
                force_rebuild=force_rebuild,
                sync_mode=sync_mode or "",
            )
            return {
                "section_id": section_id,
                "section_type": PROGRAM_SECTION_TYPE,
                **report,
            }
        if normalized_kind == "gig":
            report = await sync_program_gig_section_pages_report(
                db,
                section,
                item_id=normalized_item_id or None,
                force_rebuild=force_rebuild,
                sync_mode=sync_mode or "",
            )
            return {
                "section_id": section_id,
                "section_type": PROGRAM_SECTION_TYPE,
                **report,
            }

        stage_report = await sync_program_stage_section_pages_report(
            db,
            section,
            force_rebuild=force_rebuild,
            sync_mode=sync_mode or "",
        )
        gig_report = await sync_program_gig_section_pages_report(
            db,
            section,
            force_rebuild=force_rebuild,
            sync_mode=sync_mode or "",
        )
        return {
            "section_id": section_id,
            "section_type": PROGRAM_SECTION_TYPE,
            "item_kind": "all",
            "generated_count": int(stage_report.get("generated_count", 0) or 0)
            + int(gig_report.get("generated_count", 0) or 0),
            "warnings": [
                *(
                    stage_report.get("warnings")
                    if isinstance(stage_report.get("warnings"), list)
                    else []
                ),
                *(
                    gig_report.get("warnings")
                    if isinstance(gig_report.get("warnings"), list)
                    else []
                ),
            ],
            "stage": stage_report,
            "gig": gig_report,
        }

    raise HTTPException(400, "Item-page generation is supported only for blog and program sections")


@router.post(
    "/{section_id}/item-pages/cleanup",
    dependencies=[Depends(require_permission("content:write"))],
)
async def cleanup_section_item_pages(
    section_id: str,
    item_kind: str | None = Query(default=None),
):
    db = _db()
    sections = db["sections"]
    try:
        oid = ObjectId(section_id)
    except Exception as exc:
        raise HTTPException(400, "Invalid section ID") from exc
    section = await sections.find_one({"_id": oid})
    if not section:
        raise HTTPException(404, "Section not found")

    section_type = str(section.get("section_type") or "")
    if section_type == BLOG_SECTION_TYPE:
        active_template = await resolve_active_item_page_template(db, "blog", "item")
        parent_route = (
            normalize_parent_route(active_template.get("effective_parent_route"))
            if isinstance(active_template, dict)
            else None
        )
        if not parent_route:
            return {
                "section_id": section_id,
                "section_type": BLOG_SECTION_TYPE,
                "parent_route": None,
                "removed_count": 0,
            }
        report = await cleanup_blog_generated_pages_for_route(db, parent_route)
        return {
            "section_id": section_id,
            "section_type": BLOG_SECTION_TYPE,
            **report,
        }

    if section_type == PROGRAM_SECTION_TYPE:
        normalized_kind = str(item_kind or "").strip().lower()
        if normalized_kind and normalized_kind not in {"all", "stage", "gig"}:
            raise HTTPException(400, "item_kind must be 'stage', 'gig', or 'all'.")
        if normalized_kind == "stage":
            report = await cleanup_program_generated_pages_for_section(
                db,
                section,
                kind="stage",
            )
            return {
                "section_id": section_id,
                "section_type": PROGRAM_SECTION_TYPE,
                **report,
            }
        if normalized_kind == "gig":
            report = await cleanup_program_generated_pages_for_section(
                db,
                section,
                kind="gig",
            )
            return {
                "section_id": section_id,
                "section_type": PROGRAM_SECTION_TYPE,
                **report,
            }
        report = await cleanup_program_generated_pages_for_section(db, section, kind=None)
        return {
            "section_id": section_id,
            "section_type": PROGRAM_SECTION_TYPE,
            **report,
        }

    raise HTTPException(400, "Item-page cleanup is supported only for blog and program sections")


@router.get(
    "/item-pages/jobs/{job_id}",
    dependencies=[Depends(require_permission("content:write"))],
)
async def get_section_item_page_generation_job(job_id: str):
    return await get_item_page_generation_job(_db(), job_id, ensure_progress=True)


@router.delete(
    "/{section_id}", dependencies=[Depends(require_permission("content:write"))]
)
async def delete_section(section_id: str, force: bool = Query(default=False)):
    """Delete a section and its revision document.

    By default, sections that are still used on pages cannot be deleted.
    Use force=true to delete anyway (not recommended).
    """
    db = _db()
    sections = db["sections"]
    pages = db["pages"]
    revisions = db["revisions"]

    # Check if section exists
    section = await sections.find_one({"_id": ObjectId(section_id)})
    if not section:
        raise HTTPException(404, "Section not found")

    # Check if section is used on any pages
    if not force:
        pages_using = await pages.count_documents({"sections.section_id": section_id})
        if pages_using > 0:
            raise HTTPException(
                400,
                f"Section is still used on {pages_using} page(s). Remove it from all pages first, or use force=true to delete anyway.",
            )

    res = await sections.delete_one({"_id": ObjectId(section_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Section not found")

    # Delete associated revision document
    await revisions.delete_one({"entity_type": "section", "entity_id": section_id})

    return {"ok": True}


# -------------------------
# Undo/Redo endpoints
# -------------------------


@router.get("/{section_id}/revisions")
async def list_section_revision_history(
    section_id: str,
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    """List section revisions for history UI (current + history + future metadata)."""
    db = _db()
    sections = db["sections"]
    revisions = db["revisions"]

    section = await sections.find_one({"_id": ObjectId(section_id)})
    if not section:
        return {
            "enabled": False,
            "current": None,
            "history": [],
            "future": [],
            "options": {
                "include_content": False,
                "include_design": False,
                "section_type": None,
            },
        }

    revision_config = await get_or_create_revision_config(db)
    section_options = get_section_revision_options(
        revision_config,
        section.get("section_type", "text"),
    )
    if not section_revision_history_enabled(section_options):
        return {
            "enabled": False,
            "current": None,
            "history": [],
            "future": [],
            "options": {
                "include_content": bool(section_options.get("include_content")),
                "include_design": bool(section_options.get("include_design")),
                "section_type": section.get("section_type", "text"),
            },
        }

    revision_doc = await revisions.find_one({"entity_type": "section", "entity_id": section_id})
    current_data = await _build_section_revision_data(
        db,
        section,
        include_content=section_options["include_content"],
        include_design=section_options["include_design"],
    )
    history_payload = build_revision_history_payload(
        revision_doc=revision_doc,
        current_data=current_data,
        entity_updated_at=section.get("updated_at"),
        parse_snapshot=parse_section_revision_snapshot,
        max_history=MAX_HISTORY,
    )

    return {
        "enabled": True,
        "current": history_payload["current"],
        "history": history_payload["history"],
        "future": history_payload["future"],
        "options": {
            "include_content": bool(section_options.get("include_content")),
            "include_design": bool(section_options.get("include_design")),
            "section_type": section.get("section_type", "text"),
        },
    }


@router.get("/{section_id}/revisions/status", response_model=RevisionStatusResponse)
async def get_revision_status(
    section_id: str,
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    """Get undo/redo status for a section."""
    db = _db()
    sections = db["sections"]
    revisions = db["revisions"]

    section = await sections.find_one({"_id": ObjectId(section_id)})
    if not section:
        return RevisionStatusResponse(
            enabled=False,
            can_undo=False,
            can_redo=False,
            history_count=0,
            future_count=0,
        )

    revision_config = await get_or_create_revision_config(db)
    section_options = get_section_revision_options(
        revision_config,
        section.get("section_type", "text"),
    )
    if not section_revision_history_enabled(section_options):
        return RevisionStatusResponse(
            enabled=False,
            can_undo=False,
            can_redo=False,
            history_count=0,
            future_count=0,
        )

    doc = await revisions.find_one({"entity_type": "section", "entity_id": section_id})
    if not doc:
        return RevisionStatusResponse(
            enabled=True,
            can_undo=False,
            can_redo=False,
            history_count=0,
            future_count=0,
        )

    content_history = doc.get("content_history", [])
    design_history = doc.get("design_history", [])
    content_future = doc.get("content_future", [])
    design_future = doc.get("design_future", [])
    history_count = len(content_history) + len(design_history)
    future_count = len(content_future) + len(design_future)

    return RevisionStatusResponse(
        enabled=True,
        can_undo=history_count > 0,
        can_redo=future_count > 0,
        history_count=history_count,
        future_count=future_count,
        last_saved_by=doc.get("last_saved_by") or "unknown",
        last_saved_at=doc.get("last_saved_at"),
    )


@router.post(
    "/{section_id}/undo",
    response_model=SectionDB,
    dependencies=[Depends(require_permission("content:write"))],
)
async def undo_section(
    section_id: str,
    user: KeycloakUser = Depends(get_current_user),
):
    """Undo the last change to a section."""
    db = _db()
    sections = db["sections"]
    revisions = db["revisions"]

    # Get current section
    current = await sections.find_one({"_id": ObjectId(section_id)})
    if not current:
        raise HTTPException(404, "Section not found")

    revision_config = await get_or_create_revision_config(db)
    section_options = get_section_revision_options(
        revision_config,
        current.get("section_type", "text"),
    )
    if not section_revision_history_enabled(section_options):
        raise HTTPException(400, "Revisions are disabled for this section type")

    # Get revision document
    revision_doc = await revisions.find_one(
        {"entity_type": "section", "entity_id": section_id}
    )
    if not revision_doc or not revision_doc.get("history"):
        raise HTTPException(400, "Nothing to undo")

    history = revision_doc["history"]
    future = revision_doc.get("future", [])

    prev_entry = history.pop()
    prev_content, prev_design = parse_section_revision_snapshot(prev_entry.get("data"))
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

    current_data = await _build_section_revision_data(
        db,
        current,
        include_content=(
            bool(section_options["include_content"])
            and prev_change_kind in {"content", "both"}
        ),
        include_design=(
            bool(section_options["include_design"])
            and prev_change_kind in {"design", "both"}
        ),
    )
    future.append({
        "saved_at": revision_doc.get("last_saved_at") or datetime.utcnow(),
        "saved_by": revision_doc.get("last_saved_by"),
        "data": current_data,
        "change_kind": prev_change_kind,
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

    doc = current
    if section_options["include_content"] and isinstance(prev_content, dict):
        reverted_blog_shared_snapshot = (
            deepcopy(prev_content.get("shared_blog_data"))
            if isinstance(prev_content.get("shared_blog_data"), dict)
            else None
        )
        reverted_faq_shared_snapshot = (
            deepcopy(prev_content.get("shared_faq_data"))
            if isinstance(prev_content.get("shared_faq_data"), dict)
            else None
        )
        reverted_program_shared_snapshot = (
            deepcopy(prev_content.get("shared_program_data"))
            if isinstance(prev_content.get("shared_program_data"), dict)
            else None
        )
        content_patch = deepcopy(prev_content)
        content_patch.pop("shared_blog_data", None)
        content_patch.pop("shared_faq_data", None)
        content_patch.pop("shared_program_data", None)
        patch = {
            **content_patch,
            "updated_at": datetime.utcnow(),
        }
        doc = await sections.find_one_and_update(
            {"_id": ObjectId(section_id)},
            {"$set": patch},
            return_document=ReturnDocument.AFTER,
        )
        if isinstance(reverted_blog_shared_snapshot, dict):
            await apply_blog_shared_content(db, reverted_blog_shared_snapshot)
        if isinstance(reverted_faq_shared_snapshot, dict):
            await apply_faq_shared_content(db, reverted_faq_shared_snapshot)
        if isinstance(reverted_program_shared_snapshot, dict):
            await apply_program_shared_content(db, reverted_program_shared_snapshot)

    if section_options["include_design"] and isinstance(prev_design, dict):
        await apply_section_design_state(db, section_id, prev_design)

    if not doc:
        doc = await sections.find_one({"_id": ObjectId(section_id)})
        if not doc:
            raise HTTPException(404, "Section not found")
    doc = _serialize_section_doc(doc)
    await _enrich_section_docs_type_data_with_asset_media(db, [doc])
    return doc


@router.post(
    "/{section_id}/redo",
    response_model=SectionDB,
    dependencies=[Depends(require_permission("content:write"))],
)
async def redo_section(
    section_id: str,
    user: KeycloakUser = Depends(get_current_user),
):
    """Redo a previously undone change to a section."""
    db = _db()
    sections = db["sections"]
    revisions = db["revisions"]

    # Get current section
    current = await sections.find_one({"_id": ObjectId(section_id)})
    if not current:
        raise HTTPException(404, "Section not found")

    revision_config = await get_or_create_revision_config(db)
    section_options = get_section_revision_options(
        revision_config,
        current.get("section_type", "text"),
    )
    if not section_revision_history_enabled(section_options):
        raise HTTPException(400, "Revisions are disabled for this section type")

    # Get revision document
    revision_doc = await revisions.find_one(
        {"entity_type": "section", "entity_id": section_id}
    )
    if not revision_doc or not revision_doc.get("future"):
        raise HTTPException(400, "Nothing to redo")

    history = revision_doc.get("history", [])
    future = revision_doc["future"]

    next_entry = future.pop()
    next_content, next_design = parse_section_revision_snapshot(next_entry.get("data"))
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

    current_data = await _build_section_revision_data(
        db,
        current,
        include_content=(
            bool(section_options["include_content"])
            and next_change_kind in {"content", "both"}
        ),
        include_design=(
            bool(section_options["include_design"])
            and next_change_kind in {"design", "both"}
        ),
    )
    history.append({
        "saved_at": revision_doc.get("last_saved_at") or datetime.utcnow(),
        "saved_by": revision_doc.get("last_saved_by"),
        "data": current_data,
        "change_kind": next_change_kind,
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

    doc = current
    if section_options["include_content"] and isinstance(next_content, dict):
        reverted_blog_shared_snapshot = (
            deepcopy(next_content.get("shared_blog_data"))
            if isinstance(next_content.get("shared_blog_data"), dict)
            else None
        )
        reverted_faq_shared_snapshot = (
            deepcopy(next_content.get("shared_faq_data"))
            if isinstance(next_content.get("shared_faq_data"), dict)
            else None
        )
        reverted_program_shared_snapshot = (
            deepcopy(next_content.get("shared_program_data"))
            if isinstance(next_content.get("shared_program_data"), dict)
            else None
        )
        content_patch = deepcopy(next_content)
        content_patch.pop("shared_blog_data", None)
        content_patch.pop("shared_faq_data", None)
        content_patch.pop("shared_program_data", None)
        patch = {
            **content_patch,
            "updated_at": datetime.utcnow(),
        }
        doc = await sections.find_one_and_update(
            {"_id": ObjectId(section_id)},
            {"$set": patch},
            return_document=ReturnDocument.AFTER,
        )
        if isinstance(reverted_blog_shared_snapshot, dict):
            await apply_blog_shared_content(db, reverted_blog_shared_snapshot)
        if isinstance(reverted_faq_shared_snapshot, dict):
            await apply_faq_shared_content(db, reverted_faq_shared_snapshot)
        if isinstance(reverted_program_shared_snapshot, dict):
            await apply_program_shared_content(db, reverted_program_shared_snapshot)

    if section_options["include_design"] and isinstance(next_design, dict):
        await apply_section_design_state(db, section_id, next_design)

    if not doc:
        doc = await sections.find_one({"_id": ObjectId(section_id)})
        if not doc:
            raise HTTPException(404, "Section not found")
    doc = _serialize_section_doc(doc)
    await _enrich_section_docs_type_data_with_asset_media(db, [doc])
    return doc
