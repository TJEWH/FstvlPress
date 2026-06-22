from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, get_args

from pydantic import AliasChoices, BaseModel, Field, create_model, field_validator

from app.case_utils import list_camelcase_key_paths
from app.models.sections.common import BilingualText


class DBModel(BaseModel):
    id: str | None = Field(default=None, alias="_id")


# --- Page Header (optional hero section)


class CTAButton(BaseModel):
    """Call-to-action button for page header."""

    text: BilingualText = Field(default_factory=BilingualText)
    url: str | None = None
    button_type: str | None = None


# --- Headers (stored in separate collection)


class HeaderCreate(BaseModel):
    """Create payload for a new header."""

    name: str | None = None
    shared: bool = False
    header_type: str = "hero"
    enabled_fields: list[str] = Field(
        default_factory=lambda: ["title", "subtitle", "cta_buttons", "overlay_image", "background_image"]
    )
    background_media_url: str | None = None
    background_zoom: float = Field(default=1.0, ge=1.0, le=4.0)
    background_focal_x: float = Field(default=50.0, ge=0.0, le=100.0)
    background_focal_y: float = Field(default=50.0, ge=0.0, le=100.0)
    background_rotation: float = Field(default=0.0, ge=-180.0, le=180.0)
    overlay_image_url: str | None = None
    overlay_zoom: float = Field(default=1.0, ge=1.0, le=4.0)
    overlay_focal_x: float = Field(default=50.0, ge=0.0, le=100.0)
    overlay_focal_y: float = Field(default=50.0, ge=0.0, le=100.0)
    overlay_rotation: float = Field(default=0.0, ge=-180.0, le=180.0)
    hero_title: BilingualText | None = None
    hero_subtitle: BilingualText | None = None
    cta_buttons: list[CTAButton] = Field(default_factory=list, max_length=4)
    design_overrides: dict[str, Any] | None = None
    admin_notes: str | None = None
    admin_todos: list[dict[str, Any]] = Field(default_factory=list)
    revision_change_kind: Literal["content", "design", "both"] | None = None
    revision_reverted_from_saved_at: str | None = None


class HeaderUpdate(BaseModel):
    """Update payload for a header (partial updates)."""

    name: str | None = None
    shared: bool | None = None
    header_type: str | None = None
    enabled_fields: list[str] | None = None
    background_media_url: str | None = None
    background_zoom: float | None = Field(default=None, ge=1.0, le=4.0)
    background_focal_x: float | None = Field(default=None, ge=0.0, le=100.0)
    background_focal_y: float | None = Field(default=None, ge=0.0, le=100.0)
    background_rotation: float | None = Field(default=None, ge=-180.0, le=180.0)
    overlay_image_url: str | None = None
    overlay_zoom: float | None = Field(default=None, ge=1.0, le=4.0)
    overlay_focal_x: float | None = Field(default=None, ge=0.0, le=100.0)
    overlay_focal_y: float | None = Field(default=None, ge=0.0, le=100.0)
    overlay_rotation: float | None = Field(default=None, ge=-180.0, le=180.0)
    hero_title: BilingualText | None = None
    hero_subtitle: BilingualText | None = None
    cta_buttons: list[CTAButton] | None = None
    design_overrides: dict[str, Any] | None = None
    admin_notes: str | None = None
    admin_todos: list[dict[str, Any]] | None = None
    revision_change_kind: Literal["content", "design", "both"] | None = None
    revision_reverted_from_saved_at: str | None = None


class HeaderDB(DBModel):
    """Header document stored in headers collection."""

    name: str | None = None
    shared: bool = False
    header_type: str = "hero"
    enabled_fields: list[str] = Field(
        default_factory=lambda: ["title", "subtitle", "cta_buttons", "overlay_image", "background_image"]
    )
    background_media_url: str | None = None
    background_zoom: float = Field(default=1.0, ge=1.0, le=4.0)
    background_focal_x: float = Field(default=50.0, ge=0.0, le=100.0)
    background_focal_y: float = Field(default=50.0, ge=0.0, le=100.0)
    background_rotation: float = Field(default=0.0, ge=-180.0, le=180.0)
    overlay_image_url: str | None = None
    overlay_zoom: float = Field(default=1.0, ge=1.0, le=4.0)
    overlay_focal_x: float = Field(default=50.0, ge=0.0, le=100.0)
    overlay_focal_y: float = Field(default=50.0, ge=0.0, le=100.0)
    overlay_rotation: float = Field(default=0.0, ge=-180.0, le=180.0)
    hero_title: BilingualText = Field(default_factory=BilingualText)
    hero_subtitle: BilingualText = Field(default_factory=BilingualText)
    cta_buttons: list[CTAButton] = Field(default_factory=list, max_length=4)
    design_overrides: dict[str, Any] | None = None
    admin_notes: str | None = None
    admin_todos: list[dict[str, Any]] = Field(default_factory=list)
    revision_id: str | None = None
    created_at: datetime
    updated_at: datetime


class HeaderResponse(BaseModel):
    """Response model for header data."""

    id: str
    name: str | None = None
    shared: bool = False
    header_type: str
    enabled_fields: list[str] = Field(default_factory=list)
    background_media_url: str | None = None
    background_zoom: float = Field(default=1.0, ge=1.0, le=4.0)
    background_focal_x: float = Field(default=50.0, ge=0.0, le=100.0)
    background_focal_y: float = Field(default=50.0, ge=0.0, le=100.0)
    background_rotation: float = Field(default=0.0, ge=-180.0, le=180.0)
    overlay_image_url: str | None = None
    overlay_zoom: float = Field(default=1.0, ge=1.0, le=4.0)
    overlay_focal_x: float = Field(default=50.0, ge=0.0, le=100.0)
    overlay_focal_y: float = Field(default=50.0, ge=0.0, le=100.0)
    overlay_rotation: float = Field(default=0.0, ge=-180.0, le=180.0)
    hero_title: BilingualText | None = None
    hero_subtitle: BilingualText | None = None
    cta_buttons: list[CTAButton] = Field(default_factory=list)
    design_overrides: dict[str, Any] | None = None
    admin_notes: str | None = None
    admin_todos: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# --- Revisions (unified for headers and sections)


class RevisionEntry(BaseModel):
    """A single revision snapshot."""

    saved_at: datetime
    saved_by: str | None = None
    data: dict  # The actual content snapshot


class RevisionDocument(BaseModel):
    """Revision document with history and future stacks for undo/redo."""

    id: str | None = Field(default=None, alias="_id")
    entity_type: Literal["section", "header"]
    entity_id: str
    history: list[RevisionEntry] = Field(default_factory=list, max_length=5)
    future: list[RevisionEntry] = Field(default_factory=list)


class RevisionStatusResponse(BaseModel):
    """Response model for revision undo/redo status."""

    enabled: bool = True
    can_undo: bool
    can_redo: bool
    history_count: int
    future_count: int
    last_saved_by: str | None = None
    last_saved_at: datetime | None = None


# --- Sections (generic)


class SectionCreate(BaseModel):
    section_type: str = (
        "text"  # type identifier (text, video, faq, links, etc.)
    )
    shared: bool = False
    title_placeholder: str = ""  # default text when no title is given in frontend
    title: BilingualText = Field(default_factory=BilingualText)
    type_data: dict = Field(
        default_factory=dict
    )  # type-specific data (validated by section_type schema)
    section_integration_mapping: dict[str, Any] | None = None

    @field_validator("type_data")
    @classmethod
    def validate_type_data_snake_case(cls, value: dict) -> dict:
        violations = list_camelcase_key_paths(value, root_path="type_data")
        if violations:
            shown = ", ".join(violations[:20])
            suffix = "" if len(violations) <= 20 else f" (+{len(violations) - 20} more)"
            raise ValueError(
                f"type_data must use snake_case keys. Offending paths: {shown}{suffix}"
            )
        return value

    @field_validator("section_integration_mapping")
    @classmethod
    def validate_section_mapping_snake_case(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        violations = list_camelcase_key_paths(
            value,
            root_path="section_integration_mapping",
        )
        if violations:
            shown = ", ".join(violations[:20])
            suffix = "" if len(violations) <= 20 else f" (+{len(violations) - 20} more)"
            raise ValueError(
                "section_integration_mapping must use snake_case keys. "
                f"Offending paths: {shown}{suffix}"
            )
        return value


class SectionUpdate(BaseModel):
    section_type: str | None = None
    shared: bool | None = None
    title_placeholder: str | None = None
    title: BilingualText | None = None
    type_data: dict | None = None
    section_integration_mapping: dict[str, Any] | None = None
    revision_change_kind: Literal["content", "design", "both"] | None = None
    revision_reverted_from_saved_at: str | None = None

    @field_validator("type_data")
    @classmethod
    def validate_type_data_snake_case(cls, value: dict | None) -> dict | None:
        if value is None:
            return value
        violations = list_camelcase_key_paths(value, root_path="type_data")
        if violations:
            shown = ", ".join(violations[:20])
            suffix = "" if len(violations) <= 20 else f" (+{len(violations) - 20} more)"
            raise ValueError(
                f"type_data must use snake_case keys. Offending paths: {shown}{suffix}"
            )
        return value

    @field_validator("section_integration_mapping")
    @classmethod
    def validate_section_mapping_snake_case(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        violations = list_camelcase_key_paths(
            value,
            root_path="section_integration_mapping",
        )
        if violations:
            shown = ", ".join(violations[:20])
            suffix = "" if len(violations) <= 20 else f" (+{len(violations) - 20} more)"
            raise ValueError(
                "section_integration_mapping must use snake_case keys. "
                f"Offending paths: {shown}{suffix}"
            )
        return value


class SectionDB(DBModel):
    section_type: str = "text"  # type identifier
    shared: bool = False
    section_template_name: str = "default"
    title_placeholder: str = ""
    title: BilingualText = Field(default_factory=BilingualText)
    type_data: dict = Field(default_factory=dict)  # type-specific data
    section_integration_mapping: dict[str, Any] = Field(default_factory=dict)
    design_overrides: dict[str, Any] | None = None
    revision_id: str | None = None  # reference to single revision document
    created_at: datetime
    updated_at: datetime


# --- Page Section Reference (for ordering and visibility per page)


class PageSectionRef(BaseModel):
    """Reference to a section with page-specific order and visibility."""

    section_id: str
    order: int = 0
    visible: bool = True
    limit: int | None = None
    width_n: int = 1
    width_d: int = 1
    device_visibility: dict[str, bool] | None = None
    design_overrides: dict[str, Any] | None = None


# --- Pages (generic)

PageStatus = Literal["init", "hidden", "published", "under_construction"]
PageStatusInput = Literal["init", "hidden", "published", "under_construction", "draft"]
SitemapChangefreq = Literal[
    "always",
    "hourly",
    "daily",
    "weekly",
    "monthly",
    "yearly",
    "never",
]


class PageCreate(BaseModel):
    slug: str = Field(
        min_length=1, max_length=200, pattern=r"^[a-z0-9]+(?:[-/][a-z0-9]+)*$"
    )
    title: BilingualText = Field(default_factory=BilingualText)
    has_header: bool = True
    header_id: str | None = None  # reference to headers collection
    sections: list[PageSectionRef] = Field(default_factory=list)
    section_structure: list[dict[str, Any]] = Field(default_factory=list)
    status: PageStatusInput = "hidden"
    publish_at: datetime | None = None  # scheduled publish time
    unpublish_at: datetime | None = None  # scheduled unpublish time
    in_menu: bool = False  # include in nav menu
    in_footer: bool = False  # include in footer menu
    hide_in_admin_sitemap: bool = False  # exclude page from admin sitemap page lists
    hide_from_sitemap: bool = False  # exclude this page from public sitemap.xml
    hide_subtree_from_sitemap: bool = False  # exclude this page + descendants from sitemap.xml
    sitemap_priority: float | None = Field(default=None, ge=0.0, le=1.0)
    sitemap_changefreq: SitemapChangefreq | None = None
    generated_from_blog: bool = False  # mark pages auto-generated from blog items
    menu_title: BilingualText | None = None  # optional alternative menu title
    menu_parent_title: BilingualText | None = None  # optional alternative title when page is used as a menu parent node
    menu_show_as_top_level: bool = False  # force nested route to render as top-level menu item
    menu_order: int = 0  # order in navigation menu (lower = first)
    footer_order: int = 0  # order in footer links (lower = first)
    redirect_to: str | None = None  # redirect URL (internal slug or external URL)
    page_design_overrides: dict[str, Any] | None = None
    template_style_ref: str | None = None
    template_style_linked: bool = False
    template_style_lock: bool = False


class PageUpdate(BaseModel):
    title: BilingualText | None = None
    has_header: bool | None = None
    header_id: str | None = None
    sections: list[PageSectionRef] | None = None
    section_structure: list[dict[str, Any]] | None = None
    status: PageStatusInput | None = None
    publish_at: datetime | None = None
    unpublish_at: datetime | None = None
    in_menu: bool | None = None
    in_footer: bool | None = None
    hide_in_admin_sitemap: bool | None = None
    hide_from_sitemap: bool | None = None
    hide_subtree_from_sitemap: bool | None = None
    sitemap_priority: float | None = Field(default=None, ge=0.0, le=1.0)
    sitemap_changefreq: SitemapChangefreq | None = None
    generated_from_blog: bool | None = None
    menu_title: BilingualText | None = None
    menu_parent_title: BilingualText | None = None
    menu_show_as_top_level: bool | None = None
    menu_order: int | None = None
    footer_order: int | None = None
    redirect_to: str | None = None
    section_bg_pinned_start_key: str | None = None
    section_bg_pinned_end_key: str | None = None
    page_design_overrides: dict[str, Any] | None = None
    template_style_ref: str | None = None
    template_style_linked: bool | None = None
    template_style_lock: bool | None = None


class PageDB(DBModel):
    slug: str
    title: BilingualText = Field(default_factory=BilingualText)
    has_header: bool = False
    header_id: str | None = None  # reference to headers collection
    sections: list[PageSectionRef] = Field(
        default_factory=list
    )  # ordered refs with visibility
    section_structure: list[dict[str, Any]] = Field(default_factory=list)
    status: PageStatus = "hidden"
    publish_at: datetime | None = None
    unpublish_at: datetime | None = None
    in_menu: bool = False
    in_footer: bool = False
    hide_in_admin_sitemap: bool = False
    hide_from_sitemap: bool = False
    hide_subtree_from_sitemap: bool = False
    sitemap_priority: float | None = None
    sitemap_changefreq: SitemapChangefreq | None = None
    generated_from_blog: bool = False
    menu_title: BilingualText | None = None
    menu_parent_title: BilingualText | None = None
    menu_show_as_top_level: bool = False
    menu_order: int = 0
    footer_order: int = 0
    redirect_to: str | None = None
    section_bg_pinned_start_key: str = ""
    section_bg_pinned_end_key: str = ""
    page_design_overrides: dict[str, Any] | None = None
    template_style_ref: str | None = None
    template_style_linked: bool = False
    template_style_lock: bool = False
    created_at: datetime
    updated_at: datetime


class PageResponse(BaseModel):
    """Response model for page data."""

    id: str
    slug: str
    title: BilingualText = Field(default_factory=BilingualText)
    has_header: bool = False
    header_id: str | None = None
    sections: list[PageSectionRef] = Field(default_factory=list)
    section_structure: list[dict[str, Any]] = Field(default_factory=list)
    status: PageStatus = "hidden"
    effective_status: PageStatus = "hidden"  # computed from scheduling
    is_visible: bool = False  # whether actual page content is currently visible to public
    publish_at: datetime | None = None
    unpublish_at: datetime | None = None
    in_menu: bool = False
    in_footer: bool = False
    hide_in_admin_sitemap: bool = False
    hide_from_sitemap: bool = False
    hide_subtree_from_sitemap: bool = False
    sitemap_priority: float | None = None
    sitemap_changefreq: SitemapChangefreq | None = None
    generated_from_blog: bool = False
    menu_title: BilingualText | None = None
    menu_parent_title: BilingualText | None = None
    menu_show_as_top_level: bool = False
    menu_order: int = 0
    footer_order: int = 0
    redirect_to: str | None = None
    section_bg_pinned_start_key: str = ""
    section_bg_pinned_end_key: str = ""
    page_design_overrides: dict[str, Any] | None = None
    template_style_ref: str | None = None
    template_style_linked: bool = False
    template_style_lock: bool = False
    template_managed: bool = False
    template_source_type: str | None = None
    template_source_id: str | None = None
    template_integration_id: str | None = None
    template_integration_item_key: str | None = None
    anonymous_hit_count: int = 0
    created_at: datetime
    updated_at: datetime


class PageFullResponse(BaseModel):
    """Response model for page with populated header and sections."""

    id: str
    slug: str
    title: BilingualText = Field(default_factory=BilingualText)
    has_header: bool = False
    header_id: str | None = None
    header: HeaderResponse | None = None  # populated header if has_header is true
    sections: list[dict] = Field(default_factory=list)  # populated section documents
    section_structure: list[dict[str, Any]] = Field(default_factory=list)
    status: PageStatus = "hidden"
    effective_status: PageStatus = "hidden"  # computed from scheduling
    is_visible: bool = False  # whether actual page content is currently visible to public
    publish_at: datetime | None = None
    unpublish_at: datetime | None = None
    in_menu: bool = False
    in_footer: bool = False
    hide_in_admin_sitemap: bool = False
    hide_from_sitemap: bool = False
    hide_subtree_from_sitemap: bool = False
    sitemap_priority: float | None = None
    sitemap_changefreq: SitemapChangefreq | None = None
    generated_from_blog: bool = False
    menu_title: BilingualText | None = None
    menu_parent_title: BilingualText | None = None
    menu_show_as_top_level: bool = False
    menu_order: int = 0
    footer_order: int = 0
    redirect_to: str | None = None
    section_bg_pinned_start_key: str = ""
    section_bg_pinned_end_key: str = ""
    page_design_overrides: dict[str, Any] | None = None
    template_style_ref: str | None = None
    template_style_linked: bool = False
    template_style_lock: bool = False
    template_managed: bool = False
    template_source_type: str | None = None
    template_source_id: str | None = None
    template_integration_id: str | None = None
    template_integration_item_key: str | None = None
    effective_design_settings: dict[str, Any] | None = None
    media_fallbacks: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


# --- Design Settings


class DesignSettingsBase(BaseModel):
    """Single source of truth for all design setting fields and their defaults.

    Every other design-related model (Create, Update, DB, Response) derives
    from this base so that adding a new field only requires editing one place.
    """

    # Typography – Headers (shared)
    header_font_family: str = "system-ui, -apple-system, sans-serif"
    header_font_weight: str = "800"
    header_font_size_max: float = 48
    header_font_size_min: float = 14
    header_letter_spacing: float = -0.02
    header_line_height: float = 1.2
    header_text_decoration: str = "none"
    heading_linear_scaling: bool = True

    # Per-heading typography
    h1_font_size: float | None = None
    h1_font_weight: str | None = None
    h1_letter_spacing: float | None = None
    h1_line_height: float | None = None
    h2_font_size: float | None = None
    h2_font_weight: str | None = None
    h2_letter_spacing: float | None = None
    h2_line_height: float | None = None
    h3_font_size: float | None = None
    h3_font_weight: str | None = None
    h3_letter_spacing: float | None = None
    h3_line_height: float | None = None
    h4_font_size: float | None = None
    h4_font_weight: str | None = None
    h4_letter_spacing: float | None = None
    h4_line_height: float | None = None
    h5_font_size: float | None = None
    h5_font_weight: str | None = None
    h5_letter_spacing: float | None = None
    h5_line_height: float | None = None
    h6_font_size: float | None = None
    h6_font_weight: str | None = None
    h6_letter_spacing: float | None = None
    h6_line_height: float | None = None

    # Typography – Body
    body_font_family: str = "system-ui, -apple-system, sans-serif"
    body_font_weight: str = "400"
    body_letter_spacing: float = 0
    body_line_height: float = 1.65

    # Colors
    primary_color: str = "#0b1220"
    secondary_color: str = "#334155"
    background_primary_color: str = "#f6f7fb"
    background_secondary_color: str = "#ffffff"
    background_color: str = "#f6f7fb"
    accent_color: str = "#4f46e5"
    section_background_color: str = "#ffffff"
    heading_color: str = "#0b1220"
    h1_color: str | None = None
    h2_color: str | None = None
    h3_color: str | None = None
    h4_color: str | None = None
    paragraph_color: str = "#334155"

    # Section background pattern
    section_bg_pattern: str = "none"
    section_bg_color_1: str = "#ffffff"
    section_bg_color_2: str = "#f0f0f0"
    section_bg_opacity_1: float = 1.0
    section_bg_opacity_2: float = 0.3
    section_bg_pinned_start_key: str = ""
    section_bg_pinned_end_key: str = ""

    # Hard box-shadow
    hard_box_shadow_enabled: bool = False
    hard_box_shadow_brightness: float = -15
    hard_box_shadow_offset_source: str = "padding"
    hard_box_shadow_offset_custom: float = 18

    # Section styling
    section_border_radius: float = 14
    section_spacing: float = 14
    section_box_shadow: str = "0 6px 20px rgba(17, 24, 39, 0.08)"
    section_padding: float = 18
    section_border_width: float = 0
    section_border_color: str = "#0b1220"
    section_border_style: str = "solid"
    global_custom_css: str = ""

    # Layout
    full_width: bool = False
    navigation_menu_view: str = "sidebar"
    outer_spacing_section: float = 0
    outer_spacing_non_section: float = 0
    content_padding_top: float = 22
    content_padding_bottom: float = 26

    # Buttons (shared defaults)
    button_border_radius: float = 12
    button_border_width: float = 1
    button_border_color: str | None = None
    button_bg_color: str | None = None
    button_color: str | None = None
    button_hover_border_color: str | None = None
    button_hover_bg_color: str | None = None
    button_hover_color: str | None = None
    button_font_size: float = 16
    button_padding_x: float = 12
    button_padding_y: float = 10

    # Links
    link_text_decoration: str = "none"
    link_hover_text_decoration: str = "underline"
    link_color: str | None = None
    link_hover_color: str | None = None

    # Header section
    hero_title_font_size: float | None = None
    hero_title_line_height: float | None = None
    hero_title_letter_spacing: float | None = None
    hero_subtitle_font_size: float | None = None
    hero_subtitle_line_height: float | None = None
    hero_subtitle_letter_spacing: float | None = None
    hero_title_color: str | None = None
    hero_subtitle_color: str | None = None
    hero_height: float = 400
    header_inner: float = 44
    hero_overlay_position: str = "bottom-right"
    hero_overlay_size: float = 150
    hero_content_align: str = "left"
    hero_separator: str = "none"
    hero_parallax: bool = False
    hero_overlay_parallax: bool = False
    hero_overlay_parallax_direction: str = "down"
    hero_title_text_shadow_enabled: bool = False
    hero_title_text_shadow_offset: float | None = None
    hero_title_text_shadow_color: str | None = None

    # High contrast
    high_contrast_dark: str = "#0b1220"
    high_contrast_light: str = "#f8fafc"
    color_variations: dict = Field(default_factory=dict)

    # Topbar
    topbar_bg_color: str | None = None
    topbar_item_color: str | None = None
    topbar_item_hover_color: str | None = None
    topbar_logo_url: str | None = None

    # Sidebar
    sidebar_bg_color: str | None = None
    sidebar_item_color: str | None = None
    sidebar_item_hover_color: str | None = None

    # Admin UI
    admin_accent_color: str | None = "#cb00e6"
    admin_primary_color: str | None = "#4f46e5"
    admin_danger_color: str | None = "#dc2626"
    admin_warning_color: str | None = "#d97706"
    admin_favorite_color: str | None = "#b45309"

    # Per-type button overrides (nested: { typeId: { paramName: value } })
    button_type_styles: dict | None = None

    # Responsive overrides (nested: { paramKey: { min, preferred, preferredUnit, max } or { mobile, tablet, desktop } })
    responsive_values: dict | None = None

    # Selected units per parameter (for multi-unit sliders)
    selected_units: dict | None = None


class DesignSettingsCreate(DesignSettingsBase):
    """Create/replace payload for design settings."""


# Auto-generate the partial-update model: every field becomes Optional with default None.
_update_fields: dict = {}
for _name, _field in DesignSettingsBase.model_fields.items():
    _ann = _field.annotation
    if type(None) not in get_args(_ann):
        _update_fields[_name] = (_ann | None, None)
    else:
        _update_fields[_name] = (_ann, None)

DesignSettingsUpdate = create_model("DesignSettingsUpdate", **_update_fields)


class DesignSettingsDB(DBModel, DesignSettingsBase):
    """Design settings document stored in design_config collection."""

    revision_id: str | None = None
    created_at: datetime
    updated_at: datetime


class DesignSettingsResponse(DesignSettingsBase):
    """Response model for design settings."""

    id: str
    created_at: datetime
    updated_at: datetime
    topbar_logo_responsive_variants: list[dict[str, Any]] = Field(default_factory=list)
    font_stylesheet_urls: list[str] = Field(default_factory=list)
    font_cache_pending_families: list[str] = Field(default_factory=list)


# --- Assets


class AssetCreateResult(BaseModel):
    asset_id: str
    url: str
    download_url: str | None = None
    key: str
    content_type: str
    size: int
    width: int | None = None
    height: int | None = None
    downloadable: bool = False
    media_hash: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None
    responsive_variants: list[dict[str, Any]] = Field(default_factory=list)


class AssetDB(DBModel):
    key: str
    filename: str
    content_type: str
    size: int
    url: str
    width: int | None = None
    height: int | None = None
    alt: BilingualText = Field(default_factory=BilingualText)
    caption: BilingualText = Field(default_factory=BilingualText)
    tags: list[str] = Field(default_factory=list)
    downloadable: bool = False
    media_hash: str | None = None
    created_at: datetime


class AssetListItem(BaseModel):
    id: str
    filename: str
    content_type: str
    url: str
    download_url: str | None = None
    width: int | None = None
    height: int | None = None
    downloadable: bool = False
    media_hash: str | None = None
    alt: BilingualText = Field(default_factory=BilingualText)
    caption: BilingualText = Field(default_factory=BilingualText)
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    responsive_variants: list[dict[str, Any]] = Field(default_factory=list)


class AssetListResponse(BaseModel):
    items: list[AssetListItem]
    total: int
    page: int
    page_size: int
    has_more: bool


class AdminMediaCroppingTags(BaseModel):
    base_tags: list[str] = Field(default_factory=lambda: ["cropped", "auto"])
    profile_tag_pattern: str = "profile-{profile_id}"
    profile_overrides: dict[str, str] = Field(default_factory=dict)


class AdminMediaUploadVariant(BaseModel):
    enabled: bool = True
    width: int = Field(default=375, ge=64, le=4096)


class AdminMediaCustomUploadVariant(AdminMediaUploadVariant):
    id: str = "custom"
    label: str = "Custom"


class AdminMediaUploadVariants(BaseModel):
    mobile: AdminMediaUploadVariant = Field(default_factory=lambda: AdminMediaUploadVariant(enabled=True, width=375))
    thumb: AdminMediaUploadVariant = Field(default_factory=lambda: AdminMediaUploadVariant(enabled=True, width=150))
    tablet: AdminMediaUploadVariant = Field(default_factory=lambda: AdminMediaUploadVariant(enabled=True, width=768))
    desktop: AdminMediaUploadVariant = Field(default_factory=lambda: AdminMediaUploadVariant(enabled=True, width=1120))
    custom: list[AdminMediaCustomUploadVariant] = Field(default_factory=list)
    max_original_width: int = Field(default=2000, ge=256, le=4096)


class AdminMediaMetadataValueMapping(BaseModel):
    field: str = "keyword"
    match: str = ""
    tag: str = ""


class AdminMediaMetadataKeyMapping(BaseModel):
    source_key: str = ""
    target_field: str = "author"


class AdminMediaMetadataMappings(BaseModel):
    enabled: bool = True
    author_tag_prefix: str = "author"
    rights_tag_prefix: str = "rights"
    keyword_tag_prefix: str = "meta"
    require_author: bool = False
    require_rights: bool = False
    key_mappings: list[AdminMediaMetadataKeyMapping] = Field(default_factory=list)
    value_mappings: list[AdminMediaMetadataValueMapping] = Field(default_factory=list)


class AdminMediaProgramTagging(BaseModel):
    artist_tag_prefix: str = "artist"
    stage_tag_prefix: str = "stage"
    date_tag_prefix: str = "date"


class AdminMediaConfig(BaseModel):
    custom_tags: list[str] = Field(default_factory=list)
    source_tag_prefix: str = "source"
    upload_variants: AdminMediaUploadVariants = Field(default_factory=AdminMediaUploadVariants)
    metadata_mappings: AdminMediaMetadataMappings = Field(default_factory=AdminMediaMetadataMappings)
    program_tagging: AdminMediaProgramTagging = Field(default_factory=AdminMediaProgramTagging)
    cropping_tags: AdminMediaCroppingTags = Field(default_factory=AdminMediaCroppingTags)


# --- Integrations (external API/crawler data sources)

IntegrationType = Literal["api", "crawler", "composable"]
IntegrationAuthType = Literal["none", "api_key", "bearer", "token", "basic"]
IntegrationResponseType = Literal["json", "csv", "xml"]
IntegrationDataReturnType = Literal["list", "object", "unknown"]
IntegrationTransformOp = Literal[
    "keep_keys",
    "remove_keys",
    "ensure_keys",
    "group_by",
    "replace_nested_item",
    "filter_by_allowed_values",
    "filter_by_disallowed_values",
    "split_values_to_list",
    "collect_distinct_values",
    "rename_keys",
]


class IntegrationTransformKeepKeysStep(BaseModel):
    op: Literal["keep_keys"] = "keep_keys"
    enabled: bool = True
    keys: list[str] = Field(default_factory=list)


class IntegrationTransformRemoveKeysStep(BaseModel):
    op: Literal["remove_keys"] = "remove_keys"
    enabled: bool = True
    keys: list[str] = Field(default_factory=list)


class IntegrationTransformEnsureKeysStep(BaseModel):
    op: Literal["ensure_keys"] = "ensure_keys"
    enabled: bool = True
    keys: list[str] = Field(default_factory=list)


class IntegrationTransformGroupByStep(BaseModel):
    op: Literal["group_by"] = "group_by"
    enabled: bool = True
    key_path: str = Field(min_length=1)
    items_key: str = Field(default="grouped_documents", min_length=1)


class IntegrationTransformReplaceNestedItemMapping(BaseModel):
    item_key_path: str | None = None
    match_value: Any | None = None
    source_value_path: str | None = None
    renamed_value: Any | None = None
    target_key: str | None = None


class IntegrationTransformReplaceNestedItemStep(BaseModel):
    op: Literal["replace_nested_item"] = "replace_nested_item"
    enabled: bool = True
    static_route: str | None = None
    mappings: list[IntegrationTransformReplaceNestedItemMapping] = Field(default_factory=list)


class IntegrationTransformFilterByAllowedValuesStep(BaseModel):
    op: Literal["filter_by_allowed_values"] = "filter_by_allowed_values"
    enabled: bool = True
    allowed_values: dict[str, list[Any]] = Field(default_factory=dict)


class IntegrationTransformFilterByDisallowedValuesStep(BaseModel):
    op: Literal["filter_by_disallowed_values"] = "filter_by_disallowed_values"
    enabled: bool = True
    disallowed_values: dict[str, list[Any]] = Field(default_factory=dict)


class IntegrationTransformSplitValuesToListStep(BaseModel):
    op: Literal["split_values_to_list"] = "split_values_to_list"
    enabled: bool = True
    key: str
    separator: str


class IntegrationTransformCollectDistinctValuesStep(BaseModel):
    op: Literal["collect_distinct_values"] = "collect_distinct_values"
    enabled: bool = True
    key: str


class IntegrationTransformRenameKeysMapping(BaseModel):
    source_key: str = Field(validation_alias=AliasChoices("source_key", "old_key"))
    target_key: str = Field(validation_alias=AliasChoices("target_key", "new_key"))


class IntegrationTransformRenameKeysStep(BaseModel):
    op: Literal["rename_keys"] = "rename_keys"
    enabled: bool = True
    mappings: list[IntegrationTransformRenameKeysMapping] = Field(default_factory=list)


IntegrationTransformStep = (
    IntegrationTransformKeepKeysStep
    | IntegrationTransformRemoveKeysStep
    | IntegrationTransformEnsureKeysStep
    | IntegrationTransformGroupByStep
    | IntegrationTransformReplaceNestedItemStep
    | IntegrationTransformFilterByAllowedValuesStep
    | IntegrationTransformFilterByDisallowedValuesStep
    | IntegrationTransformSplitValuesToListStep
    | IntegrationTransformCollectDistinctValuesStep
    | IntegrationTransformRenameKeysStep
)


class IntegrationCrawlerPaginationByPageCountConfig(BaseModel):
    strategy: Literal["page_count"] = "page_count"
    page_query_param: str = Field(min_length=1)
    page_count_field: str = Field(min_length=1)
    max_page_visits: int = Field(default=25, ge=1, le=1000)
    query_loop_key: str | None = None
    query_loop_values: list[str] = Field(default_factory=list)


class IntegrationCrawlerPaginationByNextPageConfig(BaseModel):
    strategy: Literal["next_page"] = "next_page"
    next_page_field: str = Field(min_length=1)
    max_page_visits: int = Field(default=25, ge=1, le=1000)
    query_loop_key: str | None = None
    query_loop_values: list[str] = Field(default_factory=list)


class IntegrationCrawlerQueryLoopConfig(BaseModel):
    strategy: Literal["query_loop"] = "query_loop"
    query_loop_key: str = Field(min_length=1)
    query_loop_values: list[str] = Field(default_factory=list, min_length=1)


IntegrationCrawlerPaginationConfig = (
    IntegrationCrawlerPaginationByPageCountConfig
    | IntegrationCrawlerPaginationByNextPageConfig
    | IntegrationCrawlerQueryLoopConfig
)


class IntegrationContainerSource(BaseModel):
    integration_id: str = Field(min_length=1)
    source_key_path: str | None = None
    target_key_path: str | None = None
    merge_style: Literal["flat", "nested"] = "flat"
    nested_key: str | None = None
    keep_target_key: bool = False


class IntegrationContainerConfig(BaseModel):
    sources: list[IntegrationContainerSource] = Field(default_factory=list, min_length=2)
    target_source_integration_id: str | None = None
    merge_mode: Literal["full_outer"] = "full_outer"
    conflict_mode: Literal["last_wins"] = "last_wins"


class IntegrationCreate(BaseModel):
    """Create a new integration."""

    name: str = Field(min_length=1, max_length=100)
    url: str | None = None
    type: IntegrationType = "api"
    auth_type: IntegrationAuthType = "none"
    key_name: str | None = None
    response_type: IntegrationResponseType = "json"
    response_path: str | None = None  # dot-separated path to data list (e.g., "results" or "data.items")
    crawler_pagination_config: IntegrationCrawlerPaginationConfig | None = None
    allowed_sections: list[str] = Field(default_factory=lambda: ["program"])
    description: str | None = None
    favorite: bool = False
    transform_steps: list[IntegrationTransformStep] = Field(default_factory=list)
    output_primary_key_path: str | None = None
    item_page_sync_blocked: bool = False
    container_config: IntegrationContainerConfig | None = None


class IntegrationUpdate(BaseModel):
    """Update an existing integration."""

    name: str | None = None
    url: str | None = None
    type: IntegrationType | None = None
    auth_type: IntegrationAuthType | None = None
    key_name: str | None = None
    response_type: IntegrationResponseType | None = None
    response_path: str | None = None
    crawler_pagination_config: IntegrationCrawlerPaginationConfig | None = None
    allowed_sections: list[str] | None = None
    description: str | None = None
    favorite: bool | None = None
    transform_steps: list[IntegrationTransformStep] | None = None
    output_primary_key_path: str | None = None
    item_page_sync_blocked: bool | None = None
    container_config: IntegrationContainerConfig | None = None


class IntegrationDB(DBModel):
    """Integration document in database."""

    name: str
    url: str
    type: IntegrationType
    auth_type: IntegrationAuthType = "none"
    key_name: str | None = None
    response_type: IntegrationResponseType = "json"
    response_path: str | None = None
    crawler_pagination_config: IntegrationCrawlerPaginationConfig | None = None
    allowed_sections: list[str] = Field(default_factory=list)
    description: str | None = None
    favorite: bool = False
    transform_steps: list[IntegrationTransformStep] = Field(default_factory=list)
    output_primary_key_path: str | None = None
    item_page_sync_blocked: bool = False
    container_config: IntegrationContainerConfig | None = None
    created_at: datetime
    updated_at: datetime


class IntegrationResponse(BaseModel):
    """Integration response with fetched data info."""

    id: str
    name: str
    url: str
    type: IntegrationType
    auth_type: IntegrationAuthType
    key_name: str | None = None
    response_type: IntegrationResponseType = "json"
    response_path: str | None = None
    crawler_pagination_config: IntegrationCrawlerPaginationConfig | None = None
    allowed_sections: list[str]
    description: str | None = None
    favorite: bool = False
    transform_steps: list[IntegrationTransformStep] = Field(default_factory=list)
    output_primary_key_path: str | None = None
    item_page_sync_blocked: bool = False
    container_config: IntegrationContainerConfig | None = None
    created_at: datetime
    updated_at: datetime
    last_fetched: datetime | None = None
    data_count: int | None = None
    return_type: IntegrationDataReturnType = "unknown"


class IntegrationDataDB(DBModel):
    """Fetched integration data stored in database."""

    integration_id: str
    data: Any
    options: dict[str, list[Any]] = Field(default_factory=dict)
    option_types: dict[str, Literal["single_choice", "multi_choice"]] = Field(default_factory=dict)
    fetched_at: datetime


class IntegrationDataResponse(BaseModel):
    """Response with integration data."""

    integration_id: str
    data: Any
    options: dict[str, list[Any]] = Field(default_factory=dict)
    option_types: dict[str, Literal["single_choice", "multi_choice"]] = Field(default_factory=dict)
    media_entries: list[dict[str, Any]] = Field(default_factory=list)
    media_cache_stats: dict[str, int] = Field(default_factory=dict)
    fetched_at: datetime
    item_count: int


class IntegrationDataPreview(BaseModel):
    """Preview of integration data."""

    integration_id: str
    preview_item: Any | None = None
    available_keys: list[str] = Field(default_factory=list)
    options: dict[str, list[Any]] = Field(default_factory=dict)
    option_types: dict[str, Literal["single_choice", "multi_choice"]] = Field(default_factory=dict)
    fetched_at: datetime | None = None
    total_items: int = 0
    selected_index: int | None = None
    selected_item_key: str | None = None
    preview_options: list[dict[str, Any]] = Field(default_factory=list)


class IntegrationHealthResponse(BaseModel):
    """Health check response."""

    ok: bool
    status_code: int | None = None
    error: str | None = None
    response_time_ms: int | None = None
