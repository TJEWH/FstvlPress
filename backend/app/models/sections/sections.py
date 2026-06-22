"""
Section Type Schemas

Defines all section types and their data schemas.
Each section type can have additional fields beyond the base section fields.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from app.models.sections.common import BilingualText, SectionBase, ItemBase


# --- Section Type Identifiers ---

SectionType = Literal[
    "text",
    "text_image",
    "video",
    "faq",
    "links",
    "ticker",
    "gallery",
    "blog",
    "markdown",
    "html",
    "map",
    "tiles",
    "program",
]


# --- Text Section ---


class TextSection(SectionBase):
    """Basic text section with body content."""

    body: BilingualText = Field(default_factory=BilingualText)


class TextImageSection(SectionBase):
    """Text section with an optional image and section-local image layout settings."""

    body: BilingualText = Field(default_factory=BilingualText)
    image_url: str = ""
    image_author: str = ""
    image_click_url: str = ""
    image_interaction: Literal["none", "link", "zoom"] = "zoom"
    image_layout: Literal["above", "below", "left", "right", "background"] = "left"
    image_layout_responsive: dict[
        str, Literal["above", "below", "left", "right", "background"]
    ] = Field(default_factory=dict)
    image_align_x: Literal["left", "center", "right"] = "center"
    image_max_width_percent: float = Field(default=30.0, ge=0.0, le=100.0)
    image_max_width_percent_responsive: dict[str, float] = Field(default_factory=dict)
    image_max_height_vh: float = Field(default=70.0, ge=0.0, le=100.0)
    image_max_height_vh_responsive: dict[str, float] = Field(default_factory=dict)
    image_width_px: float = Field(default=0.0, ge=0.0, le=2000.0)
    image_min_width_px: float = Field(default=0.0, ge=0.0, le=2000.0)
    image_target_width_percent: float = Field(default=100.0, ge=0.0, le=100.0)
    image_max_width_px: float = Field(default=0.0, ge=0.0, le=2000.0)
    image_height_px: float = Field(default=0.0, ge=0.0, le=2000.0)
    image_text_gap: float | None = Field(default=20.0, ge=0.0, le=120.0)
    image_text_gap_responsive: dict[str, float] = Field(default_factory=dict)
    image_border_radius: float = Field(default=5.0, ge=0.0, le=80.0)
    image_border_radius_responsive: dict[str, float] = Field(default_factory=dict)
    image_bg_opacity: float = Field(default=0.72, ge=0.0, le=1.0)
    image_aspect_ratio: Literal["16:9", "1:1", "3:4", "none"] = "16:9"
    image_aspect_ratio_responsive: dict[str, Literal["16:9", "1:1", "3:4", "none"]] = (
        Field(default_factory=dict)
    )
    image_bg_zoom: float = Field(default=1.0, ge=1.0, le=4.0)
    image_bg_focal_x: float = Field(default=50.0, ge=0.0, le=100.0)
    image_bg_focal_y: float = Field(default=50.0, ge=0.0, le=100.0)
    image_bg_rotation: float = Field(default=0.0, ge=-180.0, le=180.0)


# --- Map Section ---


class MapSection(SectionBase):
    """Interactive SVG map section."""

    body: BilingualText = Field(default_factory=BilingualText)
    svg_url: str = ""
    asset_id: str = ""
    alt: BilingualText = Field(default_factory=BilingualText)


# --- Video Section ---


class VideoSection(SectionBase):
    """Video section with embed URL."""

    body: BilingualText = Field(default_factory=BilingualText)
    video_id: str = ""
    video_provider: Literal["youtube", "vimeo"] = "youtube"
    wrapper: Literal["tv", "minimal"] = "tv"
    tv_color: str | None = None
    tv_color_link: str | None = None

    @field_validator("video_provider", mode="before")
    @classmethod
    def _normalize_video_provider(cls, value):
        provider = str(value or "").strip().lower()
        return provider if provider in {"youtube", "vimeo"} else "youtube"


# --- FAQ Section ---


class FAQItem(ItemBase):
    """Individual FAQ item."""

    question: BilingualText = Field(default_factory=BilingualText)
    answer: BilingualText = Field(default_factory=BilingualText)
    tag: BilingualText = Field(default_factory=BilingualText)
    start_date: str = ""  # Optional YYYY-MM-DD
    end_date: str = ""  # Optional YYYY-MM-DD


class FAQSection(SectionBase):
    """FAQ section with question/answer items."""

    body: BilingualText = Field(default_factory=BilingualText)
    faqs: list[FAQItem] = Field(default_factory=list)
    scope: BilingualText | None = None
    scopes: list[BilingualText] = Field(default_factory=list)
    more_link: str | None = None
    questionColor: str | None = None
    questionColorLink: str | None = None
    answerColor: str | None = None
    answerColorLink: str | None = None
    separatorColor: str | None = None
    separatorColorLink: str | None = None
    groupTitleColor: str | None = None
    groupTitleColorLink: str | None = None


# --- Links Section ---


class LinkItem(ItemBase):
    """Individual link item (image or icon, title, link)."""

    title: BilingualText = Field(default_factory=BilingualText)
    image_url: str = ""
    responsive_variants: list[dict[str, Any]] = Field(default_factory=list)
    icon: str = ""
    icon_pack: Literal["brands", "solid"] = "brands"
    link_url: str | None = None


class LinksSection(SectionBase):
    """Links section with a reorderable list of image/icon links."""

    body: BilingualText = Field(default_factory=BilingualText)
    items: list[LinkItem] = Field(default_factory=list)
    hide_item_title: bool = False
    alignment: Literal["left", "center", "right"] = "center"
    item_max_height: int = Field(default=100, ge=20, le=400)
    non_social_item_max_width: int = Field(default=0, ge=0, le=1200)
    item_spacing: int = Field(default=16, ge=0, le=120)
    social_mode: bool = False
    hide_icons_without_links: bool = False
    icon_color: str | None = None
    icon_color_link: str | None = None
    links_integration_mapping: dict = Field(default_factory=dict)


# --- Ticker Section ---


class TickerItem(ItemBase):
    """Individual ticker item."""

    text: BilingualText = Field(default_factory=BilingualText)
    timestamp: str = ""


class TickerSection(SectionBase):
    """Ticker section with scrolling items."""

    items: list[TickerItem] = Field(default_factory=list)
    view_mode: Literal["ticker", "updates"] = "ticker"
    separator_image_url: str | None = None
    separator_image_responsive_variants: list[dict[str, Any]] = Field(default_factory=list)
    pin_to_header: bool = False
    share_items_with_tickers: bool = False
    shared_ticker_master_section_id: str | None = None


# --- Gallery Section ---


class GalleryImage(ItemBase):
    """Individual gallery image."""

    asset_id: str = ""
    image_url: str = ""
    image_author: str = ""
    zoom: float = Field(default=1.0, ge=1.0, le=4.0)
    focal_x: float = Field(default=50.0, ge=0.0, le=100.0)
    focal_y: float = Field(default=50.0, ge=0.0, le=100.0)
    rotation: float = Field(default=0.0, ge=-180.0, le=180.0)
    alt: BilingualText = Field(default_factory=BilingualText)
    caption: BilingualText = Field(default_factory=BilingualText)


class GalleryMediaTagBinding(ItemBase):
    """Dynamic media tag rule for gallery images."""

    enabled: bool = True
    prefix: str = ""
    prefix_source_path: str = ""
    value_source_path: str = ""
    resolved_tag: str = ""


class GallerySection(SectionBase):
    """Image gallery section."""

    body: BilingualText = Field(default_factory=BilingualText)
    images: list[GalleryImage] = Field(default_factory=list)
    media_tag_bindings: list[GalleryMediaTagBinding] = Field(default_factory=list)
    show_captions: bool = True
    layout: Literal["grid", "carousel", "masonry"] = "grid"
    aspect_ratio: Literal["1:1", "3:2", "4:3", "16:9"] = "4:3"
    orientation: Literal["landscape", "portrait"] = "landscape"


# --- Blog Section ---


class BlogSection(SectionBase):
    """Blog section. Items are shared globally from blog_shared API."""

    body: BilingualText = Field(default_factory=BilingualText)
    video_url: str | None = None
    scope: BilingualText | None = None
    access: Literal["admin", "public"] = "public"
    item_parent_route: str = ""
    item_page_template_path: str = ""


# --- Markdown Section ---


class MarkdownSection(SectionBase):
    """Markdown section with raw source and rendered output."""

    raw_markdown: str = ""
    rendered_html: str = ""


class HtmlSection(SectionBase):
    """HTML section with fetch/embed/raw modes."""

    mode: Literal["fetch", "embed", "raw"] = "fetch"
    fetch_url: str = ""
    fetch_selector: str = ""
    fetched_html: str = ""
    raw_html: str = ""
    raw_css: str = ""
    raw_js: str = ""
    embed_code: str = ""
    embed_provider: Literal["youtube", "instagram", ""] = ""


# --- Tiles Section ---


class TileItem(ItemBase):
    """Individual tile item in a tiles grid."""

    model_config = ConfigDict(extra="allow")

    image_url: str = ""
    zoom: float = Field(default=1.0, ge=1.0, le=4.0)
    focal_x: float = Field(default=50.0, ge=0.0, le=100.0)
    focal_y: float = Field(default=50.0, ge=0.0, le=100.0)
    rotation: float = Field(default=0.0, ge=-180.0, le=180.0)
    title: BilingualText = Field(default_factory=BilingualText)
    subtitle: BilingualText = Field(default_factory=BilingualText)
    location: str = ""
    time: str = ""


class ProgramTileOverride(BaseModel):
    """Tile-local image transform override for Program-backed tiles."""

    zoom: float = Field(default=1.0, ge=1.0, le=4.0)
    focal_x: float = Field(default=50.0, ge=0.0, le=100.0)
    focal_y: float = Field(default=50.0, ge=0.0, le=100.0)
    rotation: float = Field(default=0.0, ge=-180.0, le=180.0)


class TileListFilter(BaseModel):
    """Public tile list filter configuration."""

    id: str = ""
    name: str = ""
    target_path: str = ""
    manual_options: list[str] = Field(default_factory=list)
    enabled: bool = True


class TilesSection(SectionBase):
    """Tiles grid section with expandable image tiles."""

    body: BilingualText = Field(default_factory=BilingualText)
    parent_route: str = ""
    grid_mode: Literal["fixed", "columns", "auto"] = "auto"
    rows: int = 2
    columns: int = 3
    tile_min_width: int = Field(default=220, ge=80, le=1600)
    tile_max_width: int = Field(default=360, ge=80, le=1600)
    aspect_ratio: Literal["1:1", "3:2", "4:3", "16:9"] = "1:1"
    direction: Literal["landscape", "portrait"] = "landscape"
    checker_color1: str | None = None
    checker_color2: str | None = None
    title_gradient_color: str | None = None
    title_gradient_color_link: str | None = None
    artist_button_type: str | None = None
    always_show_title: bool = False
    tile_show_reset_button: bool = False
    tile_top_info_align: Literal["left", "right"] = "right"
    tile_bottom_info_align: Literal["left", "center", "right"] = "left"
    tile_sort_mode: Literal["manual", "title"] = "title"
    use_program_gigs: bool = True
    filters: list[TileListFilter] = Field(default_factory=list)
    filter_control_style: Literal["dropdowns", "pills", "segmented"] = "dropdowns"
    filter_control_order: list[str] = Field(default_factory=list)
    program_tile_order: list[str] = Field(default_factory=list)
    program_tile_overrides: dict[str, ProgramTileOverride] = Field(default_factory=dict)
    tiles: list[TileItem] = Field(default_factory=list)


# --- Program Section ---

_PROGRAM_GIG_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PROGRAM_GIG_TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")
_PROGRAM_GIG_DATETIME_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})[T\s](\d{2}:\d{2})")
_PROGRAM_GIG_TZ_SUFFIX_PATTERN = re.compile(r"(Z|[+-]\d{2}:\d{2})$", re.IGNORECASE)
_BERLIN_TZ = ZoneInfo("Europe/Berlin")


def _datetime_to_berlin_wall_value(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(_BERLIN_TZ)
    return value.strftime("%Y-%m-%dT%H:%M")


def _normalize_program_gig_datetime(value: object) -> str:
    if isinstance(value, datetime):
        return _datetime_to_berlin_wall_value(value)
    raw = str(value or "").strip()
    if not raw:
        return ""
    if _PROGRAM_GIG_TZ_SUFFIX_PATTERN.search(raw):
        try:
            normalized_raw = f"{raw[:-1]}+00:00" if raw.lower().endswith("z") else raw
            parsed = datetime.fromisoformat(normalized_raw)
            return _datetime_to_berlin_wall_value(parsed)
        except ValueError:
            return ""
    match = _PROGRAM_GIG_DATETIME_PATTERN.match(raw)
    if not match:
        return ""
    return f"{match.group(1)}T{match.group(2)}"


def _build_program_gig_datetime(day_value: object, time_value: object) -> str:
    day = str(day_value or "").strip()
    time = str(time_value or "").strip()
    if not _PROGRAM_GIG_DATE_PATTERN.fullmatch(day):
        return ""
    if not _PROGRAM_GIG_TIME_PATTERN.fullmatch(time):
        return ""
    return f"{day}T{time}"


def _normalize_program_gig_datetime_from_fields(
    source: dict,
    field_name: str,
    *,
    fallback_day: object,
    fallback_time_key: str,
) -> str:
    return (
        _normalize_program_gig_datetime(source.get(field_name))
        or _build_program_gig_datetime(fallback_day, source.get(fallback_time_key))
    )


def _normalize_program_string_list(value: object) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()

    def visit(entry: object) -> None:
        if isinstance(entry, list):
            for nested in entry:
                visit(nested)
            return
        if entry is None:
            return
        normalized = str(entry).strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        values.append(normalized)

    visit(value)
    return values


class ProgramGig(ItemBase):
    """Individual gig/performance in the program."""

    model_config = ConfigDict(extra="allow")

    title: BilingualText = Field(default_factory=BilingualText)
    start: str = ""  # DD.MM.YY, HH.mm format
    end: str = ""  # DD.MM.YY, HH.mm format
    stage: str = ""  # stage id reference
    gig_type: str = ""
    genre: BilingualText = Field(default_factory=BilingualText)
    genre_selection: list[str] = Field(default_factory=list)
    description: BilingualText = Field(default_factory=BilingualText)
    image_url: str = ""  # optional image for the gig
    image_responsive_variants: list[dict[str, Any]] = Field(default_factory=list)
    image_zoom: float = Field(default=1.0, ge=1.0, le=4.0)
    image_focal_x: float = Field(default=50.0, ge=0.0, le=100.0)
    image_focal_y: float = Field(default=50.0, ge=0.0, le=100.0)
    image_rotation: float = Field(default=0.0, ge=-180.0, le=180.0)
    register_changes: bool = False
    highlight_changes: bool = False
    canceled: bool = False
    previous_start: str = ""  # DD.MM.YY, HH.mm format
    previous_end: str = ""  # DD.MM.YY, HH.mm format
    previous_stage: str = ""
    page_slug: str = ""
    item_url: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_schedule_fields(cls, value):
        if not isinstance(value, dict):
            return value

        source = dict(value)
        if not isinstance(source.get("title"), dict):
            for legacy_title_key in ("artist_name", "artistName", "gig_title", "gigTitle", "name"):
                legacy_title = source.get(legacy_title_key)
                if isinstance(legacy_title, dict):
                    source["title"] = legacy_title
                    break
        for legacy_title_key in ("artist_name", "artistName", "gig_title", "gigTitle"):
            source.pop(legacy_title_key, None)
        day_value = str(source.get("day") or "").strip()
        previous_day_value = str(source.get("previous_day") or "").strip() or day_value
        source["genre_selection"] = _normalize_program_string_list(
            source.get("genre_selection", source.get("genreSelection"))
        )
        source.pop("genreSelection", None)

        source["start"] = _normalize_program_gig_datetime_from_fields(
            source,
            "start",
            fallback_day=day_value,
            fallback_time_key="start_time",
        )
        source["end"] = _normalize_program_gig_datetime_from_fields(
            source,
            "end",
            fallback_day=day_value,
            fallback_time_key="end_time",
        )
        source["previous_start"] = _normalize_program_gig_datetime_from_fields(
            source,
            "previous_start",
            fallback_day=previous_day_value,
            fallback_time_key="previous_start_time",
        )
        source["previous_end"] = _normalize_program_gig_datetime_from_fields(
            source,
            "previous_end",
            fallback_day=previous_day_value,
            fallback_time_key="previous_end_time",
        )

        for legacy_key in (
            "day",
            "start_time",
            "end_time",
            "previous_day",
            "previous_start_time",
            "previous_end_time",
        ):
            source.pop(legacy_key, None)

        return source


class ProgramStage(ItemBase):
    """Stage/location in the program."""

    model_config = ConfigDict(extra="allow")

    name: BilingualText = Field(default_factory=BilingualText)
    description: BilingualText = Field(default_factory=BilingualText)
    image_url: str = ""
    image_responsive_variants: list[dict[str, Any]] = Field(default_factory=list)
    color: str = ""  # empty means "auto stage color" in the frontend
    color_link: str | None = None
    page_slug: str = ""
    item_url: str = ""


class ProgramRouteViewConfig(ItemBase):
    """Route-scoped rendering and filter rule for Program sections."""

    route_pattern: str = ""  # Prefix pattern, supports <stage> token.
    grouping_mode: Literal["inherit", "day", "stage"] = "inherit"
    view_mode: Literal["inherit", "gantt", "timeline"] = "inherit"
    stage_filter_mode: Literal["none", "fixed", "route_stage"] = "none"
    stage_filter_value: str = ""  # stage id when stage_filter_mode == "fixed"
    day_filter: str = ""


class ProgramSection(SectionBase):
    """Program/schedule section with Gantt chart display."""

    body: BilingualText = Field(default_factory=BilingualText)
    gigs: list[ProgramGig] = Field(default_factory=list)
    gig_ids: list[str] = Field(default_factory=list)
    route_view_configs: list[ProgramRouteViewConfig] = Field(default_factory=list)
    default_grouping: Literal["day", "stage"] = "day"
    fixed_stage_id: str = ""
    fixed_day: str = ""
    fixed_gig_id: str = ""
    stage_parent_route: str = ""
    gig_parent_route: str = ""
    stage_item_page_template_path: str = ""
    gig_item_page_template_path: str = ""
    allow_group_toggle: bool = True
    allow_day_selection: bool = True
    allow_stage_filter: bool = True
    show_view_toggle: bool = True
    show_gig_description_button: bool = False
    default_view_mode: Literal["gantt", "timeline", "changes", "now"] = "gantt"
    time_slot_minutes: int = 15
    show_genre: bool = True
    show_description: bool = False
    show_changes: bool = False
    day_start_hour: int = 10  # Hour when day starts (0-23), e.g. 10 for 10:00
    day_end_hour: int = 6  # Hour when day ends (1-30), e.g. 6 means 06:00 next day
    max_visible_hours: int = 6  # Max hours visible before gantt chart scrolls
    date_selection_color: str | None = None
    date_selection_color_link: str | None = None
    stage_row_height: int = Field(default=120, ge=100, le=220)


# --- Layout Settings ---


class LayoutSettings(SectionBase):
    """Page layout configuration."""

    order: list[str] = Field(
        default_factory=lambda: [
            "blog",
            "video",
            "text",
            "faq",
            "links",
        ]
    )
    hidden: dict[str, bool] = Field(default_factory=dict)
    grid_cols: int = Field(default=3, ge=1, le=4)
    full_width: bool = False


# --- Section Schema Registry ---

SECTION_TYPE_SCHEMAS: dict[str, type[BaseModel]] = {
    "text": TextSection,
    "text_image": TextImageSection,
    "video": VideoSection,
    "faq": FAQSection,
    "links": LinksSection,
    "ticker": TickerSection,
    "gallery": GallerySection,
    "blog": BlogSection,
    "markdown": MarkdownSection,
    "html": HtmlSection,
    "map": MapSection,
    "tiles": TilesSection,
    "program": ProgramSection,
}


_DOCUMENT_SHARED_META_KEYS = (
    "cta_buttons",
    "section_generic",
    "admin_notes",
    "admin_todos",
)
_HTML_TAG_HINT_RE = re.compile(
    r"<\s*(?:html|head|body|script|style|iframe|div|section|article|main|table)\b",
    re.IGNORECASE,
)
_HTML_HOST_ALLOWLIST = {
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
_EMBED_ATTR_URL_RE = re.compile(
    r"\b(?:src|href|data-instgrm-permalink)\s*=\s*[\"']((?:https?:)?//[^\"'<>]+)[\"']",
    re.IGNORECASE,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _extract_document_shared_meta(type_data: dict) -> dict:
    if not isinstance(type_data, dict):
        return {}
    shared: dict = {}
    for key in _DOCUMENT_SHARED_META_KEYS:
        if key in type_data:
            shared[key] = deepcopy(type_data[key])
    return shared


def _looks_like_html(raw_text: str) -> bool:
    text = _as_text(raw_text)
    if not text.strip():
        return False
    if _HTML_TAG_HINT_RE.search(text):
        return True
    lowered = text.lower()
    return "<iframe" in lowered or "<script" in lowered or "<style" in lowered


def _extract_embed_attribute_urls(embed_code: str) -> list[str]:
    urls: list[str] = []
    text = _as_text(embed_code)
    for match in _EMBED_ATTR_URL_RE.finditer(text):
        url = str(match.group(1) or "").strip()
        if url:
            urls.append(url)
    return urls


def _detect_embed_provider(embed_code: str, explicit_provider: str | None = None) -> str:
    requested = str(explicit_provider or "").strip().lower()
    if requested in _HTML_HOST_ALLOWLIST:
        provider_hosts = _HTML_HOST_ALLOWLIST[requested]
    else:
        provider_hosts = None

    urls = _extract_embed_attribute_urls(embed_code)
    detected: set[str] = set()
    unsupported = False
    for url in urls:
        normalized = str(url).strip().lower()
        if normalized.startswith("//"):
            normalized = normalized[2:]
        if "://" in normalized:
            normalized = normalized.split("://", 1)[1]
        host = normalized
        host = host.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].split(":", 1)[0]
        if not host:
            continue
        matched = False
        for provider, allowed_hosts in _HTML_HOST_ALLOWLIST.items():
            if any(host == allowed_host or host.endswith(f".{allowed_host}") for allowed_host in allowed_hosts):
                detected.add(provider)
                matched = True
                break
        if not matched:
            unsupported = True

    if provider_hosts is not None and unsupported:
        return ""

    if requested in _HTML_HOST_ALLOWLIST and requested in detected:
        return requested
    if len(detected) == 1:
        return next(iter(detected))
    if requested in _HTML_HOST_ALLOWLIST and not detected and not unsupported:
        return requested
    return ""


def normalize_markdown_type_data(type_data: dict | None) -> dict:
    source = type_data if isinstance(type_data, dict) else {}
    shared = _extract_document_shared_meta(source)
    raw_markdown = _as_text(source.get("raw_markdown"))
    if not raw_markdown:
        raw_markdown = _as_text(source.get("raw_content"))
    rendered_html = _as_text(source.get("rendered_html"))
    return {
        "raw_markdown": raw_markdown,
        "rendered_html": rendered_html,
        **shared,
    }


def normalize_html_type_data(type_data: dict | None) -> dict:
    source = type_data if isinstance(type_data, dict) else {}
    shared = _extract_document_shared_meta(source)

    requested_mode = str(source.get("mode") or "").strip().lower()
    fetch_url = _as_text(source.get("fetch_url"))
    if not fetch_url:
        fetch_url = _as_text(source.get("source_url"))
    fetch_selector = _as_text(source.get("fetch_selector"))
    if not fetch_selector:
        fetch_selector = _as_text(source.get("html_selector"))
    fetched_html = _as_text(source.get("fetched_html"))
    raw_html = _as_text(source.get("raw_html"))
    raw_css = _as_text(source.get("raw_css"))
    raw_js = _as_text(source.get("raw_js"))
    embed_code = _as_text(source.get("embed_code"))
    embed_provider = _detect_embed_provider(embed_code, explicit_provider=_as_text(source.get("embed_provider")))

    legacy_source_type = str(source.get("source_type") or "").strip().lower()
    legacy_raw_content = _as_text(source.get("raw_content"))
    legacy_rendered_html = _as_text(source.get("rendered_html"))

    if requested_mode == "fetch":
        mode = "fetch"
    elif requested_mode == "embed":
        mode = "embed"
    elif requested_mode == "raw":
        mode = "raw"
    elif embed_code.strip():
        mode = "embed"
    elif fetch_url.strip():
        mode = "fetch"
    elif raw_html.strip() or raw_css.strip() or raw_js.strip():
        mode = "raw"
    elif legacy_source_type == "html" and fetch_url.strip():
        mode = "fetch"
    elif legacy_source_type == "html":
        mode = "raw"
    elif _looks_like_html(legacy_raw_content):
        mode = "raw"
    else:
        mode = "raw"

    if mode == "fetch":
        if not fetched_html:
            fetched_html = legacy_rendered_html
    elif mode == "raw":
        if not raw_html:
            if legacy_source_type == "html" and legacy_raw_content:
                raw_html = legacy_raw_content
            elif _looks_like_html(legacy_raw_content):
                raw_html = legacy_raw_content
            elif legacy_rendered_html:
                raw_html = legacy_rendered_html

    if mode != "embed":
        embed_provider = ""

    return {
        "mode": mode,
        "fetch_url": fetch_url,
        "fetch_selector": fetch_selector,
        "fetched_html": fetched_html,
        "raw_html": raw_html,
        "raw_css": raw_css,
        "raw_js": raw_js,
        "embed_code": embed_code,
        "embed_provider": embed_provider,
        **shared,
    }


def markdown_payload_should_migrate_to_html(type_data: dict | None) -> bool:
    if not isinstance(type_data, dict):
        return False

    mode = str(type_data.get("mode") or "").strip().lower()
    if mode in {"fetch", "embed", "raw"}:
        return True

    source_type = str(type_data.get("source_type") or "").strip().lower()
    source_url = _as_text(type_data.get("source_url")).strip()
    html_selector = _as_text(type_data.get("html_selector")).strip()
    raw_content = _as_text(type_data.get("raw_content"))

    if _as_text(type_data.get("embed_code")).strip() or _as_text(type_data.get("embed_provider")).strip():
        return True
    if _as_text(type_data.get("raw_html")).strip() or _as_text(type_data.get("raw_css")).strip() or _as_text(type_data.get("raw_js")).strip():
        return True
    if _as_text(type_data.get("fetch_url")).strip() or _as_text(type_data.get("fetch_selector")).strip():
        return True

    if source_type == "html":
        return True
    if html_selector:
        return True
    if source_url and source_type not in {"", "markdown"}:
        return True
    if source_type == "raw" and _looks_like_html(raw_content):
        return True

    return False


def migrate_document_section_payload(
    section_type: str,
    type_data: dict | None,
) -> tuple[str, dict]:
    normalized_section_type = str(section_type or "").strip().lower()
    if normalized_section_type == "markdown":
        if markdown_payload_should_migrate_to_html(type_data):
            return "html", normalize_html_type_data(type_data)
        return "markdown", normalize_markdown_type_data(type_data)
    if normalized_section_type == "html":
        return "html", normalize_html_type_data(type_data)
    if normalized_section_type == "text_image":
        normalized_type_data = type_data if isinstance(type_data, dict) else {}
        if (
            "image_max_width_percent" not in normalized_type_data
            and "image_width_percent" in normalized_type_data
        ):
            normalized_type_data = dict(normalized_type_data)
            normalized_type_data["image_max_width_percent"] = normalized_type_data.get(
                "image_width_percent"
            )
        if (
            "image_max_width_px" not in normalized_type_data
            and "image_width_px" in normalized_type_data
        ):
            normalized_type_data = dict(normalized_type_data)
            normalized_type_data["image_max_width_px"] = normalized_type_data.get(
                "image_width_px"
            )
        return "text_image", normalized_type_data
    return normalized_section_type, type_data if isinstance(type_data, dict) else {}


def get_type_schema(section_type: str) -> type[BaseModel]:
    """Get the schema class for a given section type."""
    return SECTION_TYPE_SCHEMAS.get(section_type, TextSection)


def validate_type_data(section_type: str, data: dict) -> BaseModel:
    """Validate and parse section data according to its schema."""
    schema_class = get_type_schema(section_type)
    return schema_class(**data)


def get_default_type_data(section_type: str) -> dict:
    """Get default data for a section type without persisting UI placeholders as content."""
    schema_class = get_type_schema(section_type)
    base_data = schema_class().model_dump()

    placeholder_content = {
        "text": {
            "body": {"de": "", "en": ""}
        },
        "text_image": {
            "body": {"de": "", "en": ""},
            "image_url": "",
            "image_author": "",
            "image_click_url": "",
            "image_interaction": "zoom",
            "image_layout": "left",
            "image_layout_responsive": {},
            "image_align_x": "center",
            "image_max_width_percent": 30.0,
            "image_max_width_percent_responsive": {},
            "image_max_height_vh": 70.0,
            "image_max_height_vh_responsive": {},
            "image_width_px": 0.0,
            "image_min_width_px": 0.0,
            "image_target_width_percent": 100.0,
            "image_max_width_px": 0.0,
            "image_height_px": 0.0,
            "image_text_gap": 20.0,
            "image_text_gap_responsive": {},
            "image_border_radius": 5.0,
            "image_border_radius_responsive": {},
            "image_bg_opacity": 0.72,
            "image_aspect_ratio": "16:9",
            "image_aspect_ratio_responsive": {},
            "image_bg_zoom": 1.0,
            "image_bg_focal_x": 50.0,
            "image_bg_focal_y": 50.0,
            "image_bg_rotation": 0.0,
        },
        "video": {
            "body": {"de": "", "en": ""},
            "video_id": "",
            "video_provider": "youtube",
        },
        "faq": {
            "body": {"de": "", "en": ""},
            "scopes": [],
        },
        "links": {
            "body": {"de": "", "en": ""},
            "items": [],
            "hide_item_title": False,
            "alignment": "center",
            "item_max_height": 100,
            "non_social_item_max_width": 0,
            "item_spacing": 16,
            "social_mode": False,
            "hide_icons_without_links": False,
            "icon_color": None,
            "icon_color_link": None,
            "links_integration_mapping": {},
        },
        "ticker": {
            "view_mode": "ticker",
            "items": [
                {
                    "id": "ticker-1",
                    "text": {
                        "de": "Willkommen!",
                        "en": "Welcome!",
                    },
                }
            ],
        },
        "gallery": {
            "body": {"de": "", "en": ""},
            "media_tag_bindings": [],
            "show_captions": True,
        },
        "blog": {
            "body": {"de": "", "en": ""},
            "scope": None,
            "access": "public",
        },
        "markdown": {
            "raw_markdown": "",
            "rendered_html": "",
        },
        "html": {
            "mode": "fetch",
            "fetch_url": "",
            "fetch_selector": "",
            "fetched_html": "",
            "raw_html": "",
            "raw_css": "",
            "raw_js": "",
            "embed_code": "",
            "embed_provider": "",
        },
        "map": {
            "body": {"de": "", "en": ""},
            "svg_url": "",
            "asset_id": "",
            "alt": {"de": "", "en": ""},
        },
        "tiles": {
            "body": {"de": "", "en": ""},
            "parent_route": "",
            "grid_mode": "auto",
            "rows": 2,
            "columns": 3,
            "tile_min_width": 220,
            "tile_max_width": 360,
            "aspect_ratio": "1:1",
            "direction": "landscape",
            "title_gradient_color": None,
            "title_gradient_color_link": None,
            "artist_button_type": None,
            "always_show_title": False,
            "tile_show_reset_button": False,
            "tile_top_info_align": "right",
            "tile_bottom_info_align": "left",
            "tile_sort_mode": "title",
            "use_program_gigs": True,
            "filters": [],
            "filter_control_style": "dropdowns",
            "filter_control_order": [],
            "program_tile_order": [],
            "program_tile_overrides": {},
            "tiles": [],
        },
        "program": {
            "body": {"de": "", "en": ""},
            "gigs": [],
            "gig_ids": [],
            "default_grouping": "day",
            "fixed_stage_id": "",
            "fixed_day": "",
            "fixed_gig_id": "",
            "stage_parent_route": "",
            "gig_parent_route": "",
            "stage_item_page_template_path": "",
            "gig_item_page_template_path": "",
            "allow_group_toggle": True,
            "allow_day_selection": True,
            "allow_stage_filter": True,
            "show_view_toggle": True,
            "show_gig_description_button": False,
            "default_view_mode": "gantt",
        },
    }

    if section_type in placeholder_content:
        base_data.update(placeholder_content[section_type])
    if section_type == "faq":
        base_data.pop("faqs", None)
        base_data.pop("scope", None)

    return base_data


def get_default_title(section_type: str) -> dict:
    """Get default bilingual title for a section type."""
    titles = {
        "text": {"de": "Text", "en": ""},
        "text_image": {"de": "Text mit Bild", "en": "Text Image"},
        "video": {"de": "Video", "en": ""},
        "faq": {"de": "FAQ", "en": ""},
        "links": {"de": "Links", "en": ""},
        "ticker": {"de": "Ticker", "en": ""},
        "gallery": {"de": "Galerie", "en": "Gallery"},
        "blog": {"de": "Blog", "en": ""},
        "markdown": {"de": "Markdown", "en": ""},
        "html": {"de": "HTML", "en": ""},
        "map": {"de": "Karte", "en": "Map"},
        "tiles": {"de": "Kacheln", "en": "Tiles"},
        "program": {"de": "Programm", "en": "Program"},
    }
    return titles.get(
        section_type, {"de": section_type.title(), "en": section_type.title()}
    )
