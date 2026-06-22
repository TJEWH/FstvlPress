from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Body, File, Form, UploadFile
from pymongo import ReturnDocument

from app.collection_names import (
    CSS_SNIPPETS_COLLECTION,
    DESIGN_CONFIG_COLLECTION,
    DESIGN_EDITOR_CONFIG_COLLECTION,
    DESIGN_VERSIONS_COLLECTION,
)
from app.db import get_client
from app.deps import require_permission, get_current_user
from app.font_cache import (
    BrowserUploadedFontFile,
    get_font_family_cache_status,
    queue_font_family_cache_via_browser,
)
from app.public_cache import invalidate_ttl_cache_key, invalidate_ttl_cache_prefix
from app.responsive_config import DEFAULT_RESPONSIVE_CONFIG, normalize_responsive_config
from app.security import KeycloakUser
from app.settings import settings

router = APIRouter(prefix="/admin/design-config", tags=["admin"])

ADMIN_CONFIG_KEY = DESIGN_EDITOR_CONFIG_COLLECTION
DESIGN_SETTINGS_KEY = "global"


def _db():
    return get_client()[settings.mongo_db]


def _design_config_coll():
    return _db()[DESIGN_CONFIG_COLLECTION]


def _design_editor_config_coll():
    return _db()[DESIGN_EDITOR_CONFIG_COLLECTION]


def _require_design_writer(user: KeycloakUser) -> None:
    if user.has_permission("design:write") or user.has_permission("admin:design"):
        return
    raise HTTPException(
        status_code=403,
        detail="Missing required permissions: design:write",
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


DEFAULT_SECTION_ORDER = ["header", "layout", "sections", "colors", "buttons", "fonts", "versions", "customCss"]

DEFAULT_PARAM_ORDER = {
    "layout": ["fullWidth", "navigationMenuView", "outerSpacingNonSection", "outerSpacingSection", "sectionSpacing", "contentPaddingTop", "contentPaddingBottom"],
    "fonts": [
        "heroTitleFontSize", "heroTitleLineHeight", "heroTitleLetterSpacing",
        "heroSubtitleFontSize", "heroSubtitleLineHeight", "heroSubtitleLetterSpacing",
        "bodyFontFamily", "bodyFontWeight", "bodyLetterSpacing", "bodyLineHeight",
        "linkTextDecoration", "linkHoverTextDecoration",
        "headerFontFamily", "headerTextDecoration", "headingLinearScaling",
        "h1FontSize", "h1FontWeight", "h1LetterSpacing", "h1LineHeight",
        "h2FontSize", "h2FontWeight", "h2LetterSpacing", "h2LineHeight",
        "h3FontSize", "h3FontWeight", "h3LetterSpacing", "h3LineHeight",
        "h4FontSize", "h4FontWeight", "h4LetterSpacing", "h4LineHeight",
        "h5FontSize", "h5FontWeight", "h5LetterSpacing", "h5LineHeight",
        "h6FontSize", "h6FontWeight", "h6LetterSpacing", "h6LineHeight",
    ],
    "colors": [
        "primaryColor", "secondaryColor", "backgroundPrimaryColor", "backgroundSecondaryColor", "accentColor",
        "topbarBgColor", "topbarItemColor", "topbarItemHoverColor",
        "heroTitleColor", "heroSubtitleColor",
        "backgroundColor", "sectionBackgroundColor",
        "sidebarBgColor", "sidebarItemColor", "sidebarItemHoverColor",
        "paragraphColor", "headingColor",
        "h1Color", "h2Color", "h3Color", "h4Color",
        "linkColor", "linkHoverColor",
        "adminAccentColor", "adminPrimaryColor", "adminDangerColor", "adminWarningColor", "adminFavoriteColor",
        "highContrastDark", "highContrastLight",
    ],
    "sections": [
        "sectionBorderRadius", "sectionPadding", "sectionContentAlign", "sectionBoxShadow",
        "sectionBorderWidth", "sectionBorderColor", "sectionBorderStyle",
        "hardBoxShadowEnabled", "hardBoxShadowOffsetSource", "hardBoxShadowOffsetCustom", "hardBoxShadowBrightness",
        "sectionBgPattern", "sectionBgOpacity1", "sectionBgOpacity2", "sectionBgColor1", "sectionBgColor2",
    ],
    "buttons": [
        "buttonBorderRadius",
        "buttonBorderWidth",
        "buttonBorderColor",
        "buttonBgColor",
        "buttonColor",
        "buttonHoverBorderColor",
        "buttonHoverBgColor",
        "buttonHoverColor",
        "buttonFontSize",
        "buttonPaddingX",
        "buttonPaddingY",
    ],
    "header": ["heroHeight", "headerInner", "heroContentAlign", "heroOverlayPosition", "heroOverlaySize", "heroOverlayParallax", "heroOverlayParallaxDirection", "heroSeparator", "heroParallax"],
    "customCss": ["globalCustomCss"],
    "versions": [],
}


def _reorder_known_items(current: list[str], preferred: list[str]) -> list[str]:
    current_list = _string_list(current)
    current_set = set(current_list)
    preferred_set = set(preferred)
    ordered = [item for item in preferred if item in current_set]
    ordered.extend(item for item in current_list if item not in preferred_set and item not in ordered)
    return ordered


def _get_default_config() -> dict:
    """Return the default admin design configuration."""
    base_colors = [
        "primaryColor",
        "secondaryColor",
        "backgroundPrimaryColor",
        "backgroundSecondaryColor",
        "accentColor",
        "transparent",
        "highContrast",
    ]

    return {
        "key": ADMIN_CONFIG_KEY,
        "sectionOrder": list(DEFAULT_SECTION_ORDER),
        "paramOrder": deepcopy(DEFAULT_PARAM_ORDER),
        "fontFamilies": [
            {"value": "system-ui, -apple-system, sans-serif", "label": "System UI"},
            {"value": '"Inter", sans-serif', "label": "Inter"},
            {"value": '"Roboto", sans-serif', "label": "Roboto"},
            {"value": '"Open Sans", sans-serif', "label": "Open Sans"},
            {"value": '"Lato", sans-serif', "label": "Lato"},
            {"value": '"Montserrat", sans-serif', "label": "Montserrat"},
            {"value": '"Poppins", sans-serif', "label": "Poppins"},
            {"value": '"Playfair Display", serif', "label": "Playfair Display"},
            {"value": '"Merriweather", serif', "label": "Merriweather"},
            {"value": '"Georgia", serif', "label": "Georgia"},
            {"value": '"Source Code Pro", monospace', "label": "Source Code Pro"},
        ],
        "colorLinks": {
            "backgroundColor": "backgroundPrimaryColor",
            "sectionBackgroundColor": "backgroundSecondaryColor",
        },
        "baseColors": base_colors,
        "baseColorHighContrast": {},
        "colorVariations": {},
        "showColorVariationDropdowns": True,
        "buttonInstances": [
            {"id": "primary", "label": "Primary", "enabled": True},
            {"id": "secondary", "label": "Secondary", "enabled": True},
            {"id": "ghost", "label": "Ghost", "enabled": False},
        ],
        "buttonPerTypeParams": ["bgColor", "color", "borderColor"],
        "responsive": deepcopy(DEFAULT_RESPONSIVE_CONFIG),
        "sectionOverrideParams": {
            "generic": [
                "sectionBackgroundColor", "sectionBorderRadius",
                "sectionContentAlign", "sectionBoxShadow", "hardBoxShadowMode", "headerColor",
                "headerFontFamily", "headerFontWeight",
                "h1FontSize", "h1LetterSpacing", "h1LineHeight",
                "h2FontSize", "h2LetterSpacing", "h2LineHeight",
                "h3FontSize", "h3LetterSpacing", "h3LineHeight",
                "h4FontSize", "h4LetterSpacing", "h4LineHeight",
                "textColor", "textFontFamily", "textFontSize", "textFontWeight"
            ],
            "constants": [
                "hideSectionHeader",
                "hideSectionDescription",
                "removeSectionPadding",
                "removeSectionBackground",
                "hideSectionIfListEmptyPublic",
            ],
            "byType": {
                "tiles": ["checkerColor1", "checkerColor2"],
                "video": [],
                "text": [],
                "text_image": [],
                "faq": [],
                "links": [],
                "blog": [],
            },
            "header": [
                "heroHeight", "headerInner", "heroContentAlign", "heroSeparator", "heroParallax", "heroOverlayParallax", "heroOverlayParallaxDirection",
                "heroTitleFontSize", "heroTitleLineHeight", "heroTitleLetterSpacing", "heroTitleColor",
                "heroSubtitleFontSize", "heroSubtitleLineHeight", "heroSubtitleLetterSpacing", "heroSubtitleColor",
                "heroOverlayPosition", "heroOverlaySize"
            ]
        },
        "parameters": {
            # Layout
            "fullWidth": {"visible": True, "favorite": False, "section": "layout", "type": "checkbox", "label": "Full Width Mode"},
            "navigationMenuView": {"visible": True, "favorite": False, "section": "layout", "type": "dropdown", "label": "Menu View", "subsection": "Navigation", "enabledOptions": ["sidebar", "below_topbar"]},
            "outerSpacingNonSection": {"visible": True, "favorite": False, "section": "layout", "type": "slider", "label": "Outer Spacing — Header, Footer", "min": 0, "max": 48, "step": 4, "unit": "px"},
            "outerSpacingSection": {"visible": True, "favorite": False, "section": "layout", "type": "slider", "label": "Outer Spacing — Sections", "min": 0, "max": 48, "step": 4, "unit": "px"},
            "contentPaddingTop": {"visible": True, "favorite": False, "section": "layout", "type": "slider", "label": "Content Padding Top", "min": 0, "max": 80, "step": 2, "unit": "px"},
            "contentPaddingBottom": {"visible": True, "favorite": False, "section": "layout", "type": "slider", "label": "Content Padding Bottom", "min": 0, "max": 80, "step": 2, "unit": "px"},

            # Typography - Headers (shared)
            "headerFontFamily": {"visible": True, "favorite": False, "section": "fonts", "type": "fontfamily", "label": "Font Family", "subsection": "Headings"},
            "headerTextDecoration": {"visible": True, "favorite": False, "section": "fonts", "type": "dropdown", "label": "Text Decoration", "subsection": "Headings", "enabledOptions": ["none", "underline"]},
            "headingLinearScaling": {"visible": True, "favorite": False, "section": "fonts", "type": "checkbox", "label": "Linear Scaling", "subsection": "Headings"},

            # Per-heading typography — H1
            "h1FontSize": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Font Size", "subsection": "H1", "min": 24, "max": 96, "step": 1, "unit": "px"},
            "h1FontWeight": {"visible": True, "favorite": False, "section": "fonts", "type": "dropdown", "label": "Font Weight", "subsection": "H1", "enabledOptions": ["300", "400", "500", "600", "700", "800", "900"]},
            "h1LetterSpacing": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Letter Spacing", "subsection": "H1", "min": -0.05, "max": 0.2, "step": 0.01, "unit": "em"},
            "h1LineHeight": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Line Height", "subsection": "H1", "min": 0.8, "max": 2, "step": 0.05, "unit": ""},
            # Per-heading typography — H2
            "h2FontSize": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Font Size", "subsection": "H2", "min": 18, "max": 72, "step": 1, "unit": "px"},
            "h2FontWeight": {"visible": True, "favorite": False, "section": "fonts", "type": "dropdown", "label": "Font Weight", "subsection": "H2", "enabledOptions": ["300", "400", "500", "600", "700", "800", "900"]},
            "h2LetterSpacing": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Letter Spacing", "subsection": "H2", "min": -0.05, "max": 0.2, "step": 0.01, "unit": "em"},
            "h2LineHeight": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Line Height", "subsection": "H2", "min": 0.8, "max": 2, "step": 0.05, "unit": ""},
            # Per-heading typography — H3
            "h3FontSize": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Font Size", "subsection": "H3", "min": 14, "max": 60, "step": 1, "unit": "px"},
            "h3FontWeight": {"visible": True, "favorite": False, "section": "fonts", "type": "dropdown", "label": "Font Weight", "subsection": "H3", "enabledOptions": ["300", "400", "500", "600", "700", "800", "900"]},
            "h3LetterSpacing": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Letter Spacing", "subsection": "H3", "min": -0.05, "max": 0.2, "step": 0.01, "unit": "em"},
            "h3LineHeight": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Line Height", "subsection": "H3", "min": 0.8, "max": 2, "step": 0.05, "unit": ""},
            # Per-heading typography — H4
            "h4FontSize": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Font Size", "subsection": "H4", "min": 12, "max": 48, "step": 1, "unit": "px"},
            "h4FontWeight": {"visible": True, "favorite": False, "section": "fonts", "type": "dropdown", "label": "Font Weight", "subsection": "H4", "enabledOptions": ["300", "400", "500", "600", "700", "800", "900"]},
            "h4LetterSpacing": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Letter Spacing", "subsection": "H4", "min": -0.05, "max": 0.2, "step": 0.01, "unit": "em"},
            "h4LineHeight": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Line Height", "subsection": "H4", "min": 0.8, "max": 2, "step": 0.05, "unit": ""},
            # Per-heading typography — H5
            "h5FontSize": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Font Size", "subsection": "H5", "min": 10, "max": 36, "step": 1, "unit": "px"},
            "h5FontWeight": {"visible": True, "favorite": False, "section": "fonts", "type": "dropdown", "label": "Font Weight", "subsection": "H5", "enabledOptions": ["300", "400", "500", "600", "700", "800", "900"]},
            "h5LetterSpacing": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Letter Spacing", "subsection": "H5", "min": -0.05, "max": 0.2, "step": 0.01, "unit": "em"},
            "h5LineHeight": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Line Height", "subsection": "H5", "min": 0.8, "max": 2, "step": 0.05, "unit": ""},
            # Per-heading typography — H6
            "h6FontSize": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Font Size", "subsection": "H6", "min": 8, "max": 28, "step": 1, "unit": "px"},
            "h6FontWeight": {"visible": True, "favorite": False, "section": "fonts", "type": "dropdown", "label": "Font Weight", "subsection": "H6", "enabledOptions": ["300", "400", "500", "600", "700", "800", "900"]},
            "h6LetterSpacing": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Letter Spacing", "subsection": "H6", "min": -0.05, "max": 0.2, "step": 0.01, "unit": "em"},
            "h6LineHeight": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Line Height", "subsection": "H6", "min": 0.8, "max": 2, "step": 0.05, "unit": ""},

            # Typography - Body
            "bodyFontFamily": {"visible": True, "favorite": False, "section": "fonts", "type": "fontfamily", "label": "Font Family", "subsection": "Paragraph"},
            "bodyFontWeight": {"visible": True, "favorite": False, "section": "fonts", "type": "dropdown", "label": "Font Weight", "subsection": "Paragraph", "enabledOptions": ["300", "400", "500", "600", "700", "800", "900"]},
            "bodyLetterSpacing": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Letter Spacing", "subsection": "Paragraph", "min": -0.02, "max": 0.1, "step": 0.005, "unit": "em"},
            "bodyLineHeight": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Line Height", "subsection": "Paragraph", "min": 1.2, "max": 2.2, "step": 0.05, "unit": ""},

            # Links
            "linkTextDecoration": {"visible": True, "favorite": False, "section": "fonts", "type": "dropdown", "label": "Text Decoration", "subsection": "Links", "enabledOptions": ["none", "underline"]},
            "linkHoverTextDecoration": {"visible": True, "favorite": False, "section": "fonts", "type": "dropdown", "label": "Hover Decoration", "subsection": "Links", "enabledOptions": ["none", "underline"]},

            # Colors
            "primaryColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Primary Color", "isBase": True, "subsection": "Base Vars"},
            "secondaryColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Secondary Color", "isBase": True, "subsection": "Base Vars"},
            "backgroundPrimaryColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Background Primary", "isBase": True, "subsection": "Base Vars"},
            "backgroundSecondaryColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Background Secondary", "isBase": True, "subsection": "Base Vars"},
            "accentColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Accent Color", "isBase": True, "subsection": "Base Vars"},
            "backgroundColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Page Background", "subsection": "Background", "linkable": True, "showLinkInPanel": True},
            "sectionBackgroundColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Section Background", "subsection": "Background", "linkable": True, "showLinkInPanel": True},
            "paragraphColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Paragraph Color", "subsection": "Typography"},
            "headingColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Heading Color (Fallback)", "subsection": "Typography", "linkable": True, "showLinkInPanel": True},
            "h1Color": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "H1 Color", "subsection": "Typography", "linkable": True, "showLinkInPanel": True},
            "h2Color": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "H2 Color", "subsection": "Typography", "linkable": True, "showLinkInPanel": True},
            "h3Color": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "H3 Color", "subsection": "Typography", "linkable": True, "showLinkInPanel": True},
            "h4Color": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "H4 Color", "subsection": "Typography", "linkable": True, "showLinkInPanel": True},
            "topbarBgColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Topbar Background", "subsection": "Topbar", "linkable": True, "showLinkInPanel": True},
            "topbarItemColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Topbar Item", "subsection": "Topbar", "linkable": True, "showLinkInPanel": True},
            "topbarItemHoverColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Topbar Item Hover", "subsection": "Topbar", "linkable": True, "showLinkInPanel": True},
            "sidebarBgColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Sidebar Background", "subsection": "Menus", "linkable": True, "showLinkInPanel": True},
            "sidebarItemColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Sidebar Item", "subsection": "Menus", "linkable": True, "showLinkInPanel": True},
            "sidebarItemHoverColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Sidebar Item Hover Text", "subsection": "Menus", "linkable": True, "showLinkInPanel": True},
            "linkColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Link Color", "subsection": "Links", "linkable": True, "showLinkInPanel": True},
            "linkHoverColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Link Hover Color", "subsection": "Links", "linkable": True, "showLinkInPanel": True},
            "adminAccentColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Admin Accent Color", "subsection": "Admin UI", "linkable": True, "showLinkInPanel": False, "showInPanel": False, "default": "#cb00e6"},
            "adminPrimaryColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Admin Primary Color", "subsection": "Admin UI", "linkable": False, "showLinkInPanel": False, "showInPanel": False},
            "adminDangerColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Admin Danger Color", "subsection": "Admin UI", "linkable": False, "showLinkInPanel": False, "showInPanel": False},
            "adminWarningColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Admin Warning Color", "subsection": "Admin UI", "linkable": False, "showLinkInPanel": False, "showInPanel": False},
            "adminFavoriteColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Admin Favorite Color", "subsection": "Admin UI", "linkable": False, "showLinkInPanel": False, "showInPanel": False},
            "highContrastDark": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Dark", "subsection": "High Contrast"},
            "highContrastLight": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Light", "subsection": "High Contrast"},

            # Section Background Pattern
            "sectionBgPattern": {"visible": True, "favorite": False, "section": "sections", "subsection": "Background Pattern", "type": "dropdown", "label": "Pattern", "enabledOptions": ["none", "alternating", "gradient", "gradient_shuffled", "alpha_gradient", "alpha_gradient_shuffled"]},
            "sectionBgOpacity1": {"visible": True, "favorite": False, "section": "sections", "subsection": "Background Pattern", "type": "slider", "label": "Start Opacity", "min": 0, "max": 1, "step": 0.05, "unit": ""},
            "sectionBgOpacity2": {"visible": True, "favorite": False, "section": "sections", "subsection": "Background Pattern", "type": "slider", "label": "End Opacity", "min": 0, "max": 1, "step": 0.05, "unit": ""},
            "sectionBgColor1": {"visible": True, "favorite": False, "section": "sections", "subsection": "Background Pattern", "type": "color", "label": "Start Color"},
            "sectionBgColor2": {"visible": True, "favorite": False, "section": "sections", "subsection": "Background Pattern", "type": "color", "label": "End Color"},
            # Sections
            "sectionBorderRadius": {"visible": True, "favorite": False, "section": "sections", "type": "slider", "label": "Border Radius", "subsection": "Container", "min": 0, "max": 32, "step": 1, "unit": "px"},
            "sectionSpacing": {"visible": True, "favorite": False, "section": "layout", "type": "slider", "label": "Grid Spacing", "subsection": "Inner Spacing", "min": 0, "max": 40, "step": 2, "unit": "px"},
            "sectionPadding": {"visible": True, "favorite": False, "section": "sections", "type": "slider", "label": "Section Padding", "subsection": "Container", "min": 8, "max": 40, "step": 2, "unit": "px"},
            "sectionContentAlign": {"visible": True, "favorite": False, "section": "sections", "type": "dropdown", "label": "Content Align", "subsection": "Container", "enabledOptions": ["left", "center", "right"]},
            "sectionBoxShadow": {"visible": True, "favorite": False, "section": "sections", "type": "dropdown", "label": "Box Shadow", "subsection": "Container", "enabledOptions": ["none", "0 2px 8px rgba(0, 0, 0, 0.04)", "0 6px 20px rgba(17, 24, 39, 0.08)", "0 10px 30px rgba(17, 24, 39, 0.12)", "0 16px 40px rgba(17, 24, 39, 0.16)"]},
            "sectionBorderWidth": {"visible": True, "favorite": False, "section": "sections", "type": "slider", "label": "Border Width", "subsection": "Border", "min": 0, "max": 10, "step": 1, "unit": "px"},
            "sectionBorderColor": {"visible": True, "favorite": False, "section": "sections", "type": "color", "label": "Border Color", "subsection": "Border"},
            "sectionBorderStyle": {"visible": True, "favorite": False, "section": "sections", "type": "dropdown", "label": "Border Style", "subsection": "Border", "enabledOptions": ["solid", "dashed", "dotted", "double", "none"]},
            "hardBoxShadowEnabled": {"visible": True, "favorite": False, "section": "sections", "type": "checkbox", "label": "Enable Hard Shadow", "subsection": "Hardbox Shadow"},
            "hardBoxShadowOffsetSource": {"visible": True, "favorite": False, "section": "sections", "type": "dropdown", "label": "Offset Source", "subsection": "Hardbox Shadow", "enabledOptions": ["padding", "spacing", "custom"]},
            "hardBoxShadowOffsetCustom": {"visible": True, "favorite": False, "section": "sections", "type": "slider", "label": "Custom Offset", "subsection": "Hardbox Shadow", "min": 0, "max": 60, "step": 1, "unit": "px"},
            "hardBoxShadowBrightness": {"visible": True, "favorite": False, "section": "sections", "type": "slider", "label": "Shadow Brightness", "subsection": "Hardbox Shadow", "min": -60, "max": 60, "step": 1, "unit": "%"},

            # Buttons (shared defaults)
            "buttonBorderRadius": {"visible": True, "favorite": False, "section": "buttons", "type": "slider", "label": "Border Radius", "min": 0, "max": 24, "step": 1, "unit": "px"},
            "buttonBorderWidth": {"visible": True, "favorite": False, "section": "buttons", "type": "slider", "label": "Border Width", "min": 0, "max": 4, "step": 1, "unit": "px"},
            "buttonBorderColor": {"visible": True, "favorite": False, "section": "buttons", "type": "color", "label": "Border Color"},
            "buttonBgColor": {"visible": True, "favorite": False, "section": "buttons", "type": "color", "label": "Background Color"},
            "buttonColor": {"visible": True, "favorite": False, "section": "buttons", "type": "color", "label": "Text Color"},
            "buttonHoverBorderColor": {"visible": True, "favorite": False, "section": "buttons", "type": "color", "label": "Hover Border Color"},
            "buttonHoverBgColor": {"visible": True, "favorite": False, "section": "buttons", "type": "color", "label": "Hover Background Color"},
            "buttonHoverColor": {"visible": True, "favorite": False, "section": "buttons", "type": "color", "label": "Hover Text Color"},
            "buttonFontSize": {"visible": True, "favorite": False, "section": "buttons", "type": "slider", "label": "Font Size", "min": 10, "max": 32, "step": 1, "unit": "px"},
            "buttonPaddingX": {"visible": True, "favorite": False, "section": "buttons", "type": "slider", "label": "Horizontal Padding", "min": 8, "max": 32, "step": 2, "unit": "px"},
            "buttonPaddingY": {"visible": True, "favorite": False, "section": "buttons", "type": "slider", "label": "Vertical Padding", "min": 4, "max": 20, "step": 2, "unit": "px"},

            # Custom CSS
            "globalCustomCss": {"visible": True, "favorite": False, "section": "customCss", "type": "textarea", "label": "Global Custom CSS"},

            # Hero Title & Subtitle typography (in Typography section)
            "heroTitleFontSize": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Font Size", "subsection": "Hero Title", "min": 16, "max": 96, "step": 1, "unit": "px"},
            "heroTitleLineHeight": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Line Height", "subsection": "Hero Title", "min": 0.8, "max": 2, "step": 0.05, "unit": ""},
            "heroTitleLetterSpacing": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Letter Spacing", "subsection": "Hero Title", "min": -0.05, "max": 0.2, "step": 0.01, "unit": "em"},
            "heroSubtitleFontSize": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Font Size", "subsection": "Hero Subtitle", "min": 10, "max": 36, "step": 1, "unit": "px"},
            "heroSubtitleLineHeight": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Line Height", "subsection": "Hero Subtitle", "min": 1, "max": 2.5, "step": 0.05, "unit": ""},
            "heroSubtitleLetterSpacing": {"visible": True, "favorite": False, "section": "fonts", "type": "slider", "label": "Letter Spacing", "subsection": "Hero Subtitle", "min": -0.02, "max": 0.1, "step": 0.005, "unit": "em"},

            # Hero Title & Subtitle colors (in Colors section)
            "heroTitleColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Hero Title Color", "subsection": "Header Titles"},
            "heroSubtitleColor": {"visible": True, "favorite": False, "section": "colors", "type": "color", "label": "Hero Subtitle Color", "subsection": "Header Titles"},

            # Header/Hero
            "heroHeight": {"visible": True, "favorite": False, "section": "header", "type": "slider", "label": "Header Height", "subsection": "Layout", "min": 200, "max": 800, "step": 10, "unit": "px"},
            "headerInner": {"visible": True, "favorite": False, "section": "header", "type": "slider", "label": "Header Inner", "subsection": "Container", "min": 0, "max": 140, "step": 2, "unit": "px"},
            "heroContentAlign": {"visible": True, "favorite": False, "section": "header", "type": "buttongroup", "label": "Alignment", "subsection": "Layout", "enabledOptions": ["left", "center", "right"]},
            "heroOverlayPosition": {"visible": True, "favorite": False, "section": "header", "type": "positiongrid", "label": "Position", "subsection": "Overlay Image"},
            "heroOverlaySize": {"visible": True, "favorite": False, "section": "header", "type": "slider", "label": "Size", "subsection": "Overlay Image", "min": 50, "max": 500, "step": 10, "unit": "px"},
            "heroSeparator": {"visible": True, "favorite": False, "section": "header", "type": "dropdown", "label": "Style", "subsection": "Bottom Separator", "enabledOptions": ["none", "inward-shadow", "border"]},
            "heroParallax": {"visible": True, "favorite": False, "section": "header", "type": "checkbox", "label": "Parallax Background", "subsection": "Effects"},
            "heroOverlayParallax": {"visible": True, "favorite": False, "section": "header", "type": "checkbox", "label": "Parallax Overlay", "subsection": "Overlay Image"},
            "heroOverlayParallaxDirection": {"visible": True, "favorite": False, "section": "header", "type": "dropdown", "label": "Overlay Direction", "subsection": "Parallax Effect", "enabledOptions": ["down", "parabola"]},
        },
    }


def _merge_defaults_into_config(doc: dict) -> dict:
    """Merge any new default parameters/options into an existing stored config.
    
    This ensures that when new params are added in code, they appear
    in already-stored configs without requiring a manual reset.
    """
    defaults = _get_default_config()

    # Merge new parameters that don't exist yet in stored config.
    # Stored admin config is user-editable and importable, so keep this path
    # tolerant of old or partially malformed documents.
    stored_params = doc.get("parameters")
    if not isinstance(stored_params, dict):
        stored_params = {}
    legacy_background_was_base = (
        isinstance(stored_params.get("backgroundColor"), dict)
        and stored_params.get("backgroundColor", {}).get("isBase") is True
    )
    legacy_section_background_was_base = (
        isinstance(stored_params.get("sectionBackgroundColor"), dict)
        and stored_params.get("sectionBackgroundColor", {}).get("isBase") is True
    )
    default_params = defaults.get("parameters", {})
    for key, default_val in default_params.items():
        if key not in stored_params or not isinstance(stored_params.get(key), dict):
            stored_params[key] = deepcopy(default_val)
            continue

        param = stored_params[key]
        if not isinstance(default_val, dict):
            continue

        # Sync structural fields from defaults.
        # Label and subsection are user-editable so we don't overwrite them.
        for sync_field in ("section", "type", "showInPanel", "linkable", "showLinkInPanel", "isBase"):
            if sync_field in default_val:
                param[sync_field] = default_val[sync_field]
            elif sync_field in param and sync_field not in default_val:
                del param[sync_field]
        # For dropdowns, merge any new enabledOptions into existing list.
        if "enabledOptions" in default_val:
            if not isinstance(param.get("enabledOptions"), list):
                param["enabledOptions"] = list(default_val.get("enabledOptions") or [])
            else:
                stored_opts = set(param["enabledOptions"])
                for opt in default_val["enabledOptions"]:
                    if opt not in stored_opts:
                        param["enabledOptions"].append(opt)
    doc["parameters"] = stored_params
    doc["responsive"] = normalize_responsive_config(doc.get("responsive"))

    removed_design_panel_params = {"topbarLogoUrl"}
    for removed_param in removed_design_panel_params:
        stored_params.pop(removed_param, None)

    def set_default_subsection(param_key: str, subsection: str, legacy_values: set[Any]) -> None:
        param = stored_params.get(param_key)
        if not isinstance(param, dict):
            return
        current = param.get("subsection")
        if current == subsection or current in legacy_values:
            param["subsection"] = subsection

    for param_key in ("headerFontFamily", "headerTextDecoration", "headingLinearScaling"):
        set_default_subsection(param_key, "Headings", {None, "", "Headings (h1 – h6)"})
    for param_key in ("bodyFontFamily", "bodyFontWeight", "bodyLetterSpacing", "bodyLineHeight"):
        set_default_subsection(param_key, "Paragraph", {None, "", "Body Text", "Typography"})
    for param_key in ("heroTitleColor", "heroSubtitleColor"):
        set_default_subsection(param_key, "Header Titles", {None, "", "text header", "Text Header", "Header Text", "Hero Titles"})
    for param_key in ("sidebarBgColor", "sidebarItemColor", "sidebarItemHoverColor"):
        set_default_subsection(param_key, "Menus", {None, "", "Sidebar"})
    for param_key in ("topbarBgColor", "topbarItemColor", "topbarItemHoverColor"):
        set_default_subsection(param_key, "Topbar", {None, "", "Container"})
    for param_key in ("sectionBorderRadius", "sectionPadding", "sectionContentAlign", "sectionBoxShadow"):
        set_default_subsection(param_key, "Container", {None, ""})
    for param_key in ("sectionBorderWidth", "sectionBorderColor", "sectionBorderStyle"):
        set_default_subsection(param_key, "Border", {None, ""})
    for param_key in ("hardBoxShadowEnabled", "hardBoxShadowOffsetSource", "hardBoxShadowOffsetCustom", "hardBoxShadowBrightness"):
        set_default_subsection(param_key, "Hardbox Shadow", {None, "", "Hard Box-Shadow"})

    admin_accent_param = stored_params.get("adminAccentColor")
    if isinstance(admin_accent_param, dict) and admin_accent_param.get("default") in (None, "", "#4f46e5"):
        admin_accent_param["default"] = "#cb00e6"

    # Migration: move sectionSpacing from "sections" to "layout" and align grouping label.
    spacing_param = stored_params.get("sectionSpacing")
    if isinstance(spacing_param, dict):
        spacing_param["section"] = "layout"
        if spacing_param.get("subsection") in (None, "", "Container"):
            spacing_param["subsection"] = "Inner Spacing"
        if spacing_param.get("label") in (None, "", "Section Spacing"):
            spacing_param["label"] = "Grid Spacing"

    # Migration: topbar background is configured from Colors now (no longer Header section).
    topbar_bg_param = stored_params.get("topbarBgColor")
    if isinstance(topbar_bg_param, dict):
        topbar_bg_param["section"] = "colors"
        if topbar_bg_param.get("subsection") in (None, "", "Container"):
            topbar_bg_param["subsection"] = "Topbar"
        if topbar_bg_param.get("label") in (None, "", "Background"):
            topbar_bg_param["label"] = "Topbar Background"

    # Migration: page/section backgrounds are linkable colors, with dedicated base vars.
    background_primary_param = stored_params.get("backgroundPrimaryColor")
    if isinstance(background_primary_param, dict):
        background_primary_param["section"] = "colors"
        background_primary_param["type"] = "color"
        background_primary_param["isBase"] = True
        background_primary_param["subsection"] = "Base Vars"
        if background_primary_param.get("label") in (None, "", "Background Primary Color"):
            background_primary_param["label"] = "Background Primary"

    background_secondary_param = stored_params.get("backgroundSecondaryColor")
    if isinstance(background_secondary_param, dict):
        background_secondary_param["section"] = "colors"
        background_secondary_param["type"] = "color"
        background_secondary_param["isBase"] = True
        background_secondary_param["subsection"] = "Base Vars"
        if background_secondary_param.get("label") in (None, "", "Background Secondary Color"):
            background_secondary_param["label"] = "Background Secondary"

    background_param = stored_params.get("backgroundColor")
    if isinstance(background_param, dict):
        background_param["section"] = "colors"
        background_param["type"] = "color"
        background_param["isBase"] = False
        background_param["linkable"] = True
        background_param["showLinkInPanel"] = True
        if background_param.get("subsection") in (None, "", "Container", "Base Vars"):
            background_param["subsection"] = "Background"
        if background_param.get("label") in (None, "", "Background Color"):
            background_param["label"] = "Page Background"

    section_background_param = stored_params.get("sectionBackgroundColor")
    if isinstance(section_background_param, dict):
        section_background_param["section"] = "colors"
        section_background_param["type"] = "color"
        section_background_param["isBase"] = False
        section_background_param["linkable"] = True
        section_background_param["showLinkInPanel"] = True
        if section_background_param.get("subsection") in (None, "", "Container", "Base Vars"):
            section_background_param["subsection"] = "Background"

    # Migration: body typography controls now live under Paragraph subsection.
    for body_param_key in ("bodyFontFamily", "bodyFontWeight", "bodyLetterSpacing", "bodyLineHeight"):
        body_param = stored_params.get(body_param_key)
        if not isinstance(body_param, dict):
            continue
        if body_param.get("subsection") in (None, "", "Body Text", "Typography"):
            body_param["subsection"] = "Paragraph"

    # Migration: sidebar item background controls were removed.
    for removed_sidebar_param in ("sidebarItemBgColor", "sidebarItemHoverBgColor"):
        if removed_sidebar_param in stored_params:
            del stored_params[removed_sidebar_param]

    # Migration: move section background pattern controls under sections/background pattern.
    background_pattern_params = [
        "sectionBgPattern",
        "sectionBgOpacity1",
        "sectionBgOpacity2",
        "sectionBgColor1",
        "sectionBgColor2",
    ]
    for param_key in background_pattern_params:
        pattern_param = stored_params.get(param_key)
        if not isinstance(pattern_param, dict):
            continue
        pattern_param["section"] = "sections"
        pattern_param["subsection"] = "Background Pattern"

    # Migration: move overlay parallax direction under dedicated Parallax Effect subsection
    # and align label text.
    overlay_direction_param = stored_params.get("heroOverlayParallaxDirection")
    if isinstance(overlay_direction_param, dict):
        overlay_direction_param["subsection"] = "Parallax Effect"
        overlay_direction_param["label"] = "Overlay Direction"

    # Merge paramOrder - ensure new params are added to order
    default_order = defaults.get("paramOrder", {})
    stored_order = doc.get("paramOrder")
    if not isinstance(stored_order, dict):
        stored_order = {}
    for section_key, default_params_list in default_order.items():
        if section_key not in stored_order or not isinstance(stored_order.get(section_key), list):
            stored_order[section_key] = list(default_params_list)
        else:
            stored_order[section_key] = _string_list(stored_order[section_key])
            # Add any new params that aren't in the stored order
            stored_set = set(stored_order[section_key])
            for param_key in default_params_list:
                if param_key not in stored_set:
                    stored_order[section_key].append(param_key)
    # Migration: ensure sectionSpacing is ordered under layout and removed from sections.
    layout_order = stored_order.setdefault("layout", [])
    if not isinstance(layout_order, list):
        layout_order = []
        stored_order["layout"] = layout_order
    if "sectionSpacing" not in layout_order:
        layout_order.append("sectionSpacing")
    if "sections" in stored_order and isinstance(stored_order["sections"], list):
        stored_order["sections"] = [p for p in _string_list(stored_order["sections"]) if p != "sectionSpacing"]

    # Migration: topbar background moved to Colors ordering.
    if "header" in stored_order and isinstance(stored_order["header"], list):
        stored_order["header"] = [
            p
            for p in _string_list(stored_order["header"])
            if p not in {"topbarBgColor", *removed_design_panel_params}
        ]
    colors_order = stored_order.setdefault("colors", [])
    if not isinstance(colors_order, list):
        colors_order = []
        stored_order["colors"] = colors_order
    if isinstance(colors_order, list) and "topbarBgColor" not in colors_order:
        colors_order.append("topbarBgColor")
    if isinstance(colors_order, list):
        for color_key in ("backgroundPrimaryColor", "backgroundSecondaryColor", "backgroundColor", "sectionBackgroundColor"):
            if color_key not in colors_order:
                colors_order.append(color_key)
        deduped_colors_order = []
        seen_colors = set()
        for param_key in _string_list(colors_order):
            if param_key in {"sidebarItemBgColor", "sidebarItemHoverBgColor"}:
                continue
            if param_key in seen_colors:
                continue
            seen_colors.add(param_key)
            deduped_colors_order.append(param_key)
        stored_order["colors"] = deduped_colors_order

    # Ensure background pattern params live under sections.
    for section_key, section_params in list(stored_order.items()):
        if not isinstance(section_params, list) or section_key == "sections":
            continue
        stored_order[section_key] = [
            param_key
            for param_key in _string_list(section_params)
            if (
                param_key not in background_pattern_params
                and param_key not in {"sidebarItemBgColor", "sidebarItemHoverBgColor"}
                and param_key not in removed_design_panel_params
            )
        ]

    sections_order = stored_order.setdefault("sections", [])
    if not isinstance(sections_order, list):
        sections_order = []
    sections_order = _string_list(sections_order)

    # Remove duplicates while preserving order.
    deduped_sections_order = []
    seen = set()
    for param_key in sections_order:
        if param_key in seen:
            continue
        seen.add(param_key)
        deduped_sections_order.append(param_key)
    sections_order = deduped_sections_order

    existing_pattern_order = [param_key for param_key in sections_order if param_key in background_pattern_params]
    if existing_pattern_order:
        # Respect existing order; only append newly introduced pattern params.
        missing_pattern_params = [param_key for param_key in background_pattern_params if param_key not in existing_pattern_order]
        sections_order.extend(missing_pattern_params)
    else:
        source_order = list(background_pattern_params)
        insert_at = sections_order.index("sectionBorderWidth") if "sectionBorderWidth" in sections_order else len(sections_order)
        sections_order[insert_at:insert_at] = source_order

    stored_order["sections"] = sections_order
    for section_key, preferred_order in DEFAULT_PARAM_ORDER.items():
        if isinstance(stored_order.get(section_key), list):
            stored_order[section_key] = _reorder_known_items(stored_order[section_key], preferred_order)
    doc["paramOrder"] = stored_order

    # Merge sectionOverrideParams
    if "sectionOverrideParams" not in doc or not isinstance(doc.get("sectionOverrideParams"), dict):
        doc["sectionOverrideParams"] = deepcopy(defaults.get("sectionOverrideParams", {}))
    else:
        default_sop = defaults.get("sectionOverrideParams", {})
        stored_sop = doc["sectionOverrideParams"]
        default_generic = default_sop.get("generic", [])
        stored_generic = stored_sop.get("generic")
        if not isinstance(stored_generic, list):
            stored_sop["generic"] = list(default_generic)
        else:
            stored_sop["generic"] = _string_list(stored_generic)

        default_constants = default_sop.get("constants", [])
        stored_constants = stored_sop.get("constants")
        if not isinstance(stored_constants, list):
            stored_sop["constants"] = list(default_constants)
        else:
            stored_constants = _string_list(stored_constants)
            stored_sop["constants"] = stored_constants
            existing_constants = set(stored_constants)
            for param_key in default_constants:
                if param_key not in existing_constants:
                    stored_constants.append(param_key)

        default_by_type = default_sop.get("byType", {})
        stored_by_type = stored_sop.get("byType")
        if not isinstance(stored_by_type, dict):
            stored_by_type = {}
        for section_type, params in default_by_type.items():
            existing = stored_by_type.get(section_type)
            if not isinstance(existing, list):
                stored_by_type[section_type] = list(params)
            else:
                stored_by_type[section_type] = _string_list(existing)
        # Keep TV color as section-local control only (not an override param).
        if isinstance(stored_by_type.get("video"), list):
            stored_by_type["video"] = [
                param for param in stored_by_type["video"] if param != "tvColor"
            ]
        stored_sop["byType"] = stored_by_type

        default_header = default_sop.get("header", [])
        stored_header = stored_sop.get("header")
        if not isinstance(stored_header, list):
            stored_sop["header"] = list(default_header)
        else:
            stored_header = _string_list(stored_header)
            stored_header = [
                param_key
                for param_key in stored_header
                if param_key not in removed_design_panel_params
            ]
            stored_sop["header"] = stored_header
            existing_header = set(stored_header)
            for param_key in default_header:
                if param_key not in existing_header:
                    stored_header.append(param_key)

    # Merge buttonPerTypeParams (add if missing)
    if "buttonPerTypeParams" not in doc or not isinstance(doc.get("buttonPerTypeParams"), list):
        doc["buttonPerTypeParams"] = list(defaults.get("buttonPerTypeParams", []))
    else:
        doc["buttonPerTypeParams"] = _string_list(doc["buttonPerTypeParams"])

    default_base_colors = defaults.get("baseColors", [])
    if not isinstance(doc.get("baseColors"), list):
        doc["baseColors"] = list(default_base_colors)
    else:
        normalized_base_colors = [
            key for key in _string_list(doc["baseColors"])
            if key not in {"backgroundColor", "sectionBackgroundColor"}
        ]
        for key in default_base_colors:
            if key not in normalized_base_colors:
                normalized_base_colors.append(key)
        doc["baseColors"] = normalized_base_colors

    # Base-color specific high-contrast overrides map
    if not isinstance(doc.get("baseColorHighContrast"), dict):
        doc["baseColorHighContrast"] = deepcopy(defaults.get("baseColorHighContrast", {}))
    else:
        base_hc = doc["baseColorHighContrast"]
        if "backgroundColor" in base_hc and "backgroundPrimaryColor" not in base_hc:
            base_hc["backgroundPrimaryColor"] = base_hc.get("backgroundColor")
        if "sectionBackgroundColor" in base_hc and "backgroundSecondaryColor" not in base_hc:
            base_hc["backgroundSecondaryColor"] = base_hc.get("sectionBackgroundColor")
        base_hc.pop("backgroundColor", None)
        base_hc.pop("sectionBackgroundColor", None)

        for entry in base_hc.values():
            if not isinstance(entry, dict):
                continue
            linked_base = entry.get("linkedBaseColor")
            if linked_base == "backgroundColor":
                entry["linkedBaseColor"] = "backgroundPrimaryColor"
            elif linked_base == "sectionBackgroundColor":
                entry["linkedBaseColor"] = "backgroundSecondaryColor"
    if not isinstance(doc.get("colorLinks"), dict):
        doc["colorLinks"] = deepcopy(defaults.get("colorLinks", {}))
    else:
        sanitized_color_links: dict[str, str] = {}
        legacy_base_key_map = {
            "backgroundColor": "backgroundPrimaryColor",
            "sectionBackgroundColor": "backgroundSecondaryColor",
        }
        for param_key, base_key in doc.get("colorLinks", {}).items():
            if not isinstance(param_key, str) or not isinstance(base_key, str):
                continue
            param_cfg = stored_params.get(param_key)
            if not isinstance(param_cfg, dict):
                continue
            if param_cfg.get("type") != "color" or param_cfg.get("isBase") is True:
                continue
            if param_cfg.get("linkable") is False:
                continue
            normalized_base_key = legacy_base_key_map.get(base_key, base_key)
            if normalized_base_key not in {"transparent", "highContrast"}:
                base_cfg = stored_params.get(normalized_base_key)
                if not isinstance(base_cfg, dict):
                    continue
                if base_cfg.get("type") != "color" or base_cfg.get("isBase") is not True:
                    continue
            sanitized_color_links[param_key] = normalized_base_key

        def _can_link_param(param_key: str) -> bool:
            cfg = stored_params.get(param_key)
            if not isinstance(cfg, dict):
                return False
            if cfg.get("type") != "color" or cfg.get("isBase") is True:
                return False
            return cfg.get("linkable") is not False

        if legacy_background_was_base and "backgroundColor" not in sanitized_color_links and _can_link_param("backgroundColor"):
            sanitized_color_links["backgroundColor"] = "backgroundPrimaryColor"
        if (
            legacy_section_background_was_base
            and "sectionBackgroundColor" not in sanitized_color_links
            and _can_link_param("sectionBackgroundColor")
        ):
            sanitized_color_links["sectionBackgroundColor"] = "backgroundSecondaryColor"
        doc["colorLinks"] = sanitized_color_links
    if not isinstance(doc.get("colorVariations"), dict):
        doc["colorVariations"] = deepcopy(defaults.get("colorVariations", {}))
    else:
        doc["colorVariations"].pop("sidebarItemBgColor", None)
        doc["colorVariations"].pop("sidebarItemHoverBgColor", None)
    if not isinstance(doc.get("showColorVariationDropdowns"), bool):
        doc["showColorVariationDropdowns"] = defaults.get("showColorVariationDropdowns", True)

    # Merge new buttonInstances (add any missing default instances).
    stored_button_instances = doc.get("buttonInstances")
    if not isinstance(stored_button_instances, list):
        stored_button_instances = []
    stored_button_instances = [
        button
        for button in stored_button_instances
        if isinstance(button, dict) and str(button.get("id") or "").strip()
    ]
    stored_ids = {str(button.get("id") or "").strip() for button in stored_button_instances}
    for inst in defaults.get("buttonInstances", []):
        if inst["id"] not in stored_ids:
            stored_button_instances.append(deepcopy(inst))
    doc["buttonInstances"] = stored_button_instances

    # Preserve non-default/custom parameters instead of deleting them.
    # This keeps user edits (e.g. renamed labels) for params that may exist
    # in frontend config but are not yet present in backend defaults.

    # Append new sections to sectionOrder
    stored_section_order = doc.get("sectionOrder", [])
    if not isinstance(stored_section_order, list):
        stored_section_order = []
    stored_section_order = _string_list(stored_section_order)
    for sec in defaults.get("sectionOrder", []):
        if sec not in stored_section_order:
            stored_section_order.append(sec)
    doc["sectionOrder"] = _reorder_known_items(stored_section_order, DEFAULT_SECTION_ORDER)

    return doc


# -------------------------
# CRUD endpoints
# -------------------------


@router.get("")
async def get_design_editor_config(
    _: KeycloakUser = Depends(require_permission("admin:design")),
):
    """Get the admin design configuration (creates default if not exists).
    
    Merges any new default parameters into the stored config so that
    newly added params appear automatically without requiring a reset.
    """
    coll = _design_editor_config_coll()
    doc = await coll.find_one({"key": ADMIN_CONFIG_KEY})

    if not doc:
        now = datetime.utcnow()
        defaults = _get_default_config()
        doc = {**defaults, "created_at": now, "updated_at": now}
        result = await coll.insert_one(doc)
        doc["_id"] = result.inserted_id
    else:
        doc = _merge_defaults_into_config(doc)

    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


@router.post("/font-cache/family-status")
async def get_design_font_family_cache_status(
    payload: dict = Body(default={}),
    user: KeycloakUser = Depends(get_current_user),
):
    """Read-only family cache status for admin font health checks."""
    _require_design_writer(user)
    if not isinstance(payload, dict):
        payload = {}

    family = str(payload.get("family") or "").strip()
    try:
        status = await get_font_family_cache_status(family)
        return {"ok": True, **status}
    except Exception as exc:
        return {
            "ok": False,
            "family": family,
            "cacheable": False,
            "local_candidate": False,
            "cache_status": "error",
            "stylesheet_url": "",
            "can_cache_via_browser": False,
            "message": f"Failed to check font cache health: {exc}",
            "weights": [],
        }


@router.post("/font-cache/cache-via-browser")
async def cache_design_font_family_via_browser(
    family: str = Form(...),
    source_css_url: str = Form(...),
    css_text: str = Form(...),
    source_urls: list[str] = Form([]),
    files: list[UploadFile] = File([]),
    user: KeycloakUser = Depends(get_current_user),
):
    """Queue browser-downloaded Google font assets for local server cache storage."""
    _require_design_writer(user)

    uploaded_files: list[BrowserUploadedFontFile] = []
    for upload in files:
        file_bytes = await upload.read()
        uploaded_files.append(
            BrowserUploadedFontFile(
                source_url="",
                filename=str(upload.filename or ""),
                content_type=str(upload.content_type or ""),
                data=file_bytes,
            )
        )

    try:
        result = await queue_font_family_cache_via_browser(
            family_name=family,
            source_css_url=source_css_url,
            css_text=css_text,
            source_urls=source_urls,
            files=uploaded_files,
        )
        return {"ok": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to queue browser font cache upload: {exc}")


@router.patch(
    "",
    dependencies=[Depends(require_permission("admin:design"))],
)
async def update_design_editor_config(payload: dict = Body(...)):
    """Update admin design config (partial update)."""
    coll = _design_editor_config_coll()

    current = await coll.find_one({"key": ADMIN_CONFIG_KEY})
    if not current:
        now = datetime.utcnow()
        defaults = _get_default_config()
        current = {**defaults, "created_at": now, "updated_at": now}
        result = await coll.insert_one(current)
        current["_id"] = result.inserted_id

    allowed_keys = {
        "parameters",
        "sectionOrder",
        "paramOrder",
        "fontFamilies",
        "colorLinks",
        "colorVariations",
        "showColorVariationDropdowns",
        "buttonInstances",
        "buttonPerTypeParams",
        "baseColors",
        "baseColorHighContrast",
        "sectionOverrideParams",
        "hiddenSections",
        "responsive",
    }
    patch = {k: v for k, v in payload.items() if k in allowed_keys}
    if not patch:
        raise HTTPException(400, "No valid fields to update")
    if "responsive" in patch:
        patch["responsive"] = normalize_responsive_config(patch["responsive"])

    patch["updated_at"] = datetime.utcnow()

    doc = await coll.find_one_and_update(
        {"key": ADMIN_CONFIG_KEY},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


@router.put(
    "",
    dependencies=[Depends(require_permission("admin:design"))],
)
async def replace_design_editor_config(payload: dict = Body(...)):
    """Replace admin design config entirely."""
    coll = _design_editor_config_coll()

    current = await coll.find_one({"key": ADMIN_CONFIG_KEY})
    now = datetime.utcnow()

    safe_payload = {k: v for k, v in payload.items() if k not in ("_id", "id", "key")}
    if "responsive" in safe_payload:
        safe_payload["responsive"] = normalize_responsive_config(safe_payload["responsive"])
    else:
        safe_payload["responsive"] = deepcopy(DEFAULT_RESPONSIVE_CONFIG)
    safe_payload["key"] = ADMIN_CONFIG_KEY
    safe_payload["updated_at"] = now

    if current:
        safe_payload["created_at"] = current.get("created_at", now)
        doc = await coll.find_one_and_update(
            {"key": ADMIN_CONFIG_KEY},
            {"$set": safe_payload},
            return_document=ReturnDocument.AFTER,
        )
    else:
        safe_payload["created_at"] = now
        result = await coll.insert_one(safe_payload)
        doc = safe_payload
        doc["_id"] = result.inserted_id

    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


# -------------------------
# Reset to defaults
# -------------------------

@router.post(
    "/reset",
    dependencies=[Depends(require_permission("admin:design"))],
)
async def reset_design_editor_config():
    """Reset admin design config to defaults."""
    coll = _design_editor_config_coll()
    now = datetime.utcnow()
    defaults = _get_default_config()
    defaults["updated_at"] = now

    current = await coll.find_one({"key": ADMIN_CONFIG_KEY})
    if current:
        defaults["created_at"] = current.get("created_at", now)
        doc = await coll.find_one_and_update(
            {"key": ADMIN_CONFIG_KEY},
            {"$set": defaults},
            return_document=ReturnDocument.AFTER,
        )
    else:
        defaults["created_at"] = now
        result = await coll.insert_one(defaults)
        doc = defaults
        doc["_id"] = result.inserted_id

    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


def _strip_meta(doc: dict | None) -> dict | None:
    """Remove MongoDB metadata fields from a design/admin document."""
    if not doc:
        return None
    clean = dict(doc)
    clean.pop("_id", None)
    clean.pop("id", None)
    clean.pop("key", None)
    clean.pop("revision_id", None)
    clean.pop("created_at", None)
    clean.pop("updated_at", None)
    clean.pop(DESIGN_COMPARISON_VERSION_FIELD, None)
    return clean


# -------------------------
# CSS Snippets
# -------------------------

def _format_snippet(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


@router.get("/css-snippets")
async def list_css_snippets(
    scope: str = "global",
    template_key: str | None = None,
    _: KeycloakUser = Depends(require_permission("admin:design")),
):
    """List all CSS snippets, ordered by creation date descending."""
    coll = _db()[CSS_SNIPPETS_COLLECTION]
    normalized_scope = str(scope or "global").strip().lower()
    if normalized_scope not in {"global", "template"}:
        raise HTTPException(400, "Invalid scope. Expected 'global' or 'template'.")

    query: dict = {}
    if normalized_scope == "global":
        query = {"scope": "global"}
    else:
        query = {"scope": "template"}
        if template_key and str(template_key).strip():
            query["template_key"] = str(template_key).strip()

    cursor = coll.find(query).sort("created_at", -1)
    snippets = []
    async for doc in cursor:
        snippets.append(_format_snippet(doc))
    return {"snippets": snippets}


@router.post(
    "/css-snippets",
    dependencies=[Depends(require_permission("admin:design"))],
)
async def create_css_snippet(
    payload: dict = Body(...),
    user: KeycloakUser = Depends(get_current_user),
):
    """Create a new CSS snippet."""
    label = payload.get("label", "").strip()
    css = payload.get("css", "").strip()
    if not css:
        raise HTTPException(400, "CSS content is required")

    scope = str(payload.get("scope") or "global").strip().lower()
    if scope not in {"global", "template"}:
        raise HTTPException(400, "Invalid scope. Expected 'global' or 'template'.")

    now = datetime.utcnow()
    doc = {
        "label": label or f"Snippet {now.strftime('%Y-%m-%d %H:%M')}",
        "css": css,
        "active": payload.get("active", True),
        "created_by": user.name or user.username or user.sub,
        "created_at": now,
        "updated_at": now,
        "scope": scope,
    }
    if scope == "template":
        template_key = str(payload.get("template_key") or "").strip()
        if not template_key:
            raise HTTPException(400, "template_key is required for template snippets")
        doc["template_key"] = template_key
    context_key = payload.get("context_key")
    if isinstance(context_key, str) and context_key.strip():
        doc["context_key"] = context_key.strip()
    # Optional media_scope: 'tablet' | 'mobile' | None (desktop/all)
    media_scope = payload.get("media_scope")
    if media_scope in ("tablet", "mobile"):
        doc["media_scope"] = media_scope
    result = await _db()[CSS_SNIPPETS_COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _format_snippet(doc)


@router.patch(
    "/css-snippets/{snippet_id}",
    dependencies=[Depends(require_permission("admin:design"))],
)
async def update_css_snippet(snippet_id: str, payload: dict = Body(...)):
    """Update a CSS snippet (label, css, active, media_scope, context_key)."""
    from bson import ObjectId

    allowed = {
        "label",
        "css",
        "active",
        "media_scope",
        "context_key",
        "scope",
        "template_key",
    }
    patch = {k: v for k, v in payload.items() if k in allowed}
    # Validate media_scope if present
    if "media_scope" in patch and patch["media_scope"] not in (None, "tablet", "mobile"):
        del patch["media_scope"]
    if "context_key" in patch:
        if isinstance(patch["context_key"], str):
            patch["context_key"] = patch["context_key"].strip()
        if not patch["context_key"]:
            del patch["context_key"]
    if "scope" in patch:
        normalized_scope = str(patch["scope"] or "").strip().lower()
        if normalized_scope not in {"global", "template"}:
            del patch["scope"]
        else:
            patch["scope"] = normalized_scope
    if "template_key" in patch:
        if isinstance(patch["template_key"], str):
            patch["template_key"] = patch["template_key"].strip()
        if not patch.get("template_key"):
            patch.pop("template_key", None)
    if not patch:
        raise HTTPException(400, "No valid fields to update")

    patch["updated_at"] = datetime.utcnow()

    try:
        doc = await _db()[CSS_SNIPPETS_COLLECTION].find_one_and_update(
            {"_id": ObjectId(snippet_id)},
            {"$set": patch},
            return_document=ReturnDocument.AFTER,
        )
    except Exception:
        raise HTTPException(400, "Invalid snippet ID")

    if not doc:
        raise HTTPException(404, "Snippet not found")

    return _format_snippet(doc)


@router.delete(
    "/css-snippets/{snippet_id}",
    dependencies=[Depends(require_permission("admin:design"))],
)
async def delete_css_snippet(snippet_id: str):
    """Delete a CSS snippet."""
    from bson import ObjectId

    try:
        result = await _db()[CSS_SNIPPETS_COLLECTION].delete_one({"_id": ObjectId(snippet_id)})
    except Exception:
        raise HTTPException(400, "Invalid snippet ID")

    if result.deleted_count == 0:
        raise HTTPException(404, "Snippet not found")

    return {"deleted": True}


# -------------------------
# Design Versions
# -------------------------

VERSIONS_COLLECTION = DESIGN_VERSIONS_COLLECTION
DESIGN_COMPARISON_VERSION_FIELD = "comparison_version_id"
VERSION_COMPARE_EXCLUDED_KEYS = {
    "_id",
    "id",
    "key",
    "revision_id",
    "created_at",
    "updated_at",
    DESIGN_COMPARISON_VERSION_FIELD,
}
VERSION_LARGE_CHANGE_THRESHOLD = 5


def _invalidate_public_design_version_cache() -> None:
    invalidate_ttl_cache_key("public:design-settings")
    invalidate_ttl_cache_prefix("public:page-bundle:")


def _compute_version_hash(design_settings: dict | None) -> str:
    """Compute a short hash from the design data for URL-safe previews."""
    payload = json.dumps(
        {"d": design_settings},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


async def _resolve_version(doc: dict) -> dict | None:
    """Return the full design_settings snapshot stored for a version."""
    return doc.get("design_settings")


def _normalize_version_compare_payload(design_settings: dict | None) -> dict:
    if not isinstance(design_settings, dict):
        return {}
    payload = deepcopy(design_settings)
    return {
        key: value
        for key, value in payload.items()
        if key not in VERSION_COMPARE_EXCLUDED_KEYS
    }


def _stable_version_compare_value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _compute_version_changed_keys(base: dict | None, current: dict | None) -> list[str]:
    base_payload = _normalize_version_compare_payload(base)
    current_payload = _normalize_version_compare_payload(current)
    changed: list[str] = []
    for key in sorted(set(base_payload.keys()) | set(current_payload.keys())):
        if _stable_version_compare_value(base_payload.get(key)) != _stable_version_compare_value(current_payload.get(key)):
            changed.append(f"design_settings.{key}")
    return changed


def _comparison_diff_summary(base: dict | None, current: dict | None) -> dict:
    changed_keys = _compute_version_changed_keys(base, current)
    return {
        "changed_keys": changed_keys,
        "change_count": len(changed_keys),
        "large_change": len(changed_keys) > VERSION_LARGE_CHANGE_THRESHOLD,
    }


async def _set_design_comparison_version(version_id: Any) -> None:
    normalized = str(version_id or "").strip()
    if not normalized:
        return
    await _design_config_coll().update_one(
        {"key": DESIGN_SETTINGS_KEY},
        {"$set": {DESIGN_COMPARISON_VERSION_FIELD: normalized}},
    )


async def _clear_design_comparison_version(version_id: Any | None = None) -> None:
    query = {"key": DESIGN_SETTINGS_KEY}
    normalized = str(version_id or "").strip()
    if normalized:
        query[DESIGN_COMPARISON_VERSION_FIELD] = normalized
    await _design_config_coll().update_one(
        query,
        {"$unset": {DESIGN_COMPARISON_VERSION_FIELD: ""}},
    )


def _version_list_item(doc: dict) -> dict:
    """Format a version document for the list response (no bulky payloads)."""
    item = dict(doc)
    item["id"] = str(item["_id"])
    del item["_id"]
    item.pop("parent_id", None)
    item["is_published"] = bool(item.get("is_published"))
    item.pop("design_settings", None)
    item.pop("admin_config", None)
    changelog = _sanitize_version_changelog(item.get("changelog"))
    if changelog:
        item["changelog"] = changelog
    else:
        item.pop("changelog", None)
    return item


def _comparison_baseline_item(version_doc: dict, current_design: dict | None, source: str) -> dict:
    design_settings = _normalize_version_compare_payload(version_doc.get("design_settings"))
    diff = _comparison_diff_summary(design_settings, current_design)
    return {
        "id": str(version_doc["_id"]),
        "title": version_doc.get("title") or "",
        "source": source,
        "design_settings": design_settings,
        "diff": diff,
        "changed_keys": diff["changed_keys"],
        "change_count": diff["change_count"],
        "large_change": diff["large_change"],
    }


async def _build_comparison_baseline(version_docs: list[dict], design_doc: dict | None) -> dict | None:
    if not version_docs:
        return None

    current_design = _strip_meta(design_doc)
    persisted_id = str((design_doc or {}).get(DESIGN_COMPARISON_VERSION_FIELD) or "").strip()
    if persisted_id:
        for doc in version_docs:
            if str(doc.get("_id")) == persisted_id:
                return _comparison_baseline_item(doc, current_design, "persisted")
        await _clear_design_comparison_version(persisted_id)

    best_doc: dict | None = None
    best_count: int | None = None
    for doc in version_docs:
        change_count = len(_compute_version_changed_keys(doc.get("design_settings"), current_design))
        if best_count is None or change_count < best_count:
            best_doc = doc
            best_count = change_count

    if not best_doc:
        return None
    if best_count == 0:
        await _set_design_comparison_version(best_doc["_id"])
    return _comparison_baseline_item(best_doc, current_design, "similar")


def _sanitize_version_changelog(value: Any) -> dict | None:
    """Normalize optional changelog payload for version metadata."""
    if not isinstance(value, dict):
        return None

    base_version_id = value.get("base_version_id")
    base_version_title = value.get("base_version_title")
    changed_keys_raw = value.get("changed_keys")
    change_count_raw = value.get("change_count")

    changed_keys: list[str] = []
    if isinstance(changed_keys_raw, list):
        seen = set()
        for key in changed_keys_raw:
            if not isinstance(key, str):
                continue
            normalized = key.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            changed_keys.append(normalized)

    if isinstance(change_count_raw, (int, float)):
        change_count = max(0, int(change_count_raw))
    else:
        change_count = len(changed_keys)

    result: dict[str, Any] = {
        "changed_keys": changed_keys,
        "change_count": change_count,
    }
    if isinstance(base_version_id, str) and base_version_id.strip():
        result["base_version_id"] = base_version_id.strip()
    if isinstance(base_version_title, str) and base_version_title.strip():
        result["base_version_title"] = base_version_title.strip()

    if not changed_keys and "base_version_id" not in result and "base_version_title" not in result:
        return None
    return result


async def _promote_latest_version_to_published(coll) -> dict | None:
    """Ensure there is a published version by promoting the latest one."""
    latest = await coll.find_one({}, sort=[("created_at", -1)])
    if not latest:
        return None

    now = datetime.utcnow()
    await coll.update_many({"is_published": True}, {"$set": {"is_published": False}})
    updated = await coll.find_one_and_update(
        {"_id": latest["_id"]},
        {"$set": {"is_published": True, "published_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    _invalidate_public_design_version_cache()
    return updated


async def _ensure_published_version_exists(coll) -> dict | None:
    """Return current published version, promoting latest if none is published."""
    published = await coll.find_one({"is_published": True}, sort=[("published_at", -1), ("created_at", -1)])
    if published:
        return published
    return await _promote_latest_version_to_published(coll)


@router.get("/versions")
async def list_design_versions(
    _: KeycloakUser = Depends(require_permission("admin:design")),
):
    """List all saved design versions, newest first."""
    coll = _db()[VERSIONS_COLLECTION]
    await _ensure_published_version_exists(coll)
    cursor = coll.find().sort("created_at", -1)
    versions = []
    version_docs = []
    async for doc in cursor:
        version_docs.append(doc)
        versions.append(_version_list_item(doc))
    design_doc = await _design_config_coll().find_one({"key": DESIGN_SETTINGS_KEY})
    comparison_baseline = await _build_comparison_baseline(version_docs, design_doc)
    return {"versions": versions, "comparison_baseline": comparison_baseline}


@router.post(
    "/versions",
    dependencies=[Depends(require_permission("admin:design"))],
)
async def create_design_version(
    payload: dict = Body(...),
    user: KeycloakUser = Depends(get_current_user),
):
    """Save a full design version snapshot.

    Uses the design_settings provided in the payload (i.e. the current
    in-memory state from the frontend) so unsaved experiments can be
    versioned without publishing them. Falls back to the DB state only if
    not provided.
    """
    design_coll = _design_config_coll()
    coll_v = _db()[VERSIONS_COLLECTION]

    if payload.get("parent_id"):
        raise HTTPException(400, "Subversions are no longer supported")

    title = (payload.get("title") or "").strip()
    description = (payload.get("description") or "").strip()
    rating = payload.get("rating", 0)
    if not isinstance(rating, (int, float)):
        rating = 0
    rating = max(0, min(10, rating))

    # Prefer client-supplied data (current in-memory state) over DB
    design_data = payload.get("design_settings")

    if design_data is None:
        design_doc = await design_coll.find_one({"key": "global"})
        design_data = _strip_meta(design_doc)

    # Hash is always computed from the full resolved data for stable preview URLs
    version_hash = _compute_version_hash(design_data)

    now = datetime.utcnow()
    published_exists = await coll_v.find_one({"is_published": True}, projection={"_id": 1})
    created_by = user.name or user.username or user.sub
    is_published = published_exists is None
    doc = {
        "title": title or f"Version {now.strftime('%Y-%m-%d %H:%M')}",
        "description": description,
        "rating": rating,
        "hash": version_hash,
        "created_at": now,
        "created_by": created_by,
        "is_published": is_published,
        "design_settings": design_data,
    }
    changelog = _sanitize_version_changelog(payload.get("changelog"))
    if changelog:
        doc["changelog"] = changelog
    if is_published:
        doc["published_at"] = now
        doc["published_by"] = created_by
    result = await coll_v.insert_one(doc)
    if is_published:
        _invalidate_public_design_version_cache()
    await _set_design_comparison_version(result.inserted_id)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    doc.pop("design_settings", None)
    doc.pop("admin_config", None)
    return doc


@router.post(
    "/versions/{version_id}/publish",
    dependencies=[Depends(require_permission("admin:design"))],
    )
async def publish_design_version(
    version_id: str,
    user: KeycloakUser = Depends(get_current_user),
):
    """Publish one design version (and unpublish all others)."""
    from bson import ObjectId

    coll = _db()[VERSIONS_COLLECTION]

    try:
        oid = ObjectId(version_id)
    except Exception:
        raise HTTPException(400, "Invalid version ID")

    exists = await coll.find_one({"_id": oid}, projection={"_id": 1})
    if not exists:
        raise HTTPException(404, "Version not found")

    now = datetime.utcnow()
    published_by = user.name or user.username or user.sub
    await coll.update_many({"is_published": True, "_id": {"$ne": oid}}, {"$set": {"is_published": False}})
    doc = await coll.find_one_and_update(
        {"_id": oid},
        {"$set": {"is_published": True, "published_at": now, "published_by": published_by}},
        return_document=ReturnDocument.AFTER,
    )
    _invalidate_public_design_version_cache()
    return _version_list_item(doc)


@router.patch(
    "/versions/{version_id}",
    dependencies=[Depends(require_permission("admin:design"))],
)
async def update_design_version(
    version_id: str,
    payload: dict = Body(...),
    user: KeycloakUser = Depends(get_current_user),
):
    """Update a design version's metadata or full design snapshot."""
    from bson import ObjectId

    allowed = {"title", "description", "rating"}
    patch = {k: v for k, v in payload.items() if k in allowed}
    if "rating" in patch:
        r = patch["rating"]
        if not isinstance(r, (int, float)):
            r = 0
        patch["rating"] = max(0, min(10, r))

    unset: dict[str, str] = {}
    if "design_settings" in payload:
        design_data = payload.get("design_settings")
        if design_data is not None and not isinstance(design_data, dict):
            raise HTTPException(400, "design_settings must be an object")
        now = datetime.utcnow()
        patch.update(
            {
                "design_settings": design_data,
                "hash": _compute_version_hash(design_data),
                "updated_at": now,
                "updated_by": user.name or user.username or user.sub,
            }
        )
        unset["admin_config"] = ""
        unset["parent_id"] = ""

    if "changelog" in payload:
        changelog = _sanitize_version_changelog(payload.get("changelog"))
        if changelog:
            patch["changelog"] = changelog
        else:
            unset["changelog"] = ""

    if not patch and not unset:
        raise HTTPException(400, "No valid fields to update")

    update_doc: dict[str, dict] = {}
    if patch:
        update_doc["$set"] = patch
    if unset:
        update_doc["$unset"] = unset

    try:
        doc = await _db()[VERSIONS_COLLECTION].find_one_and_update(
            {"_id": ObjectId(version_id)},
            update_doc,
            return_document=ReturnDocument.AFTER,
        )
    except Exception:
        raise HTTPException(400, "Invalid version ID")

    if not doc:
        raise HTTPException(404, "Version not found")

    if "design_settings" in payload:
        await _set_design_comparison_version(version_id)

    if bool(doc.get("is_published")) and "design_settings" in payload:
        _invalidate_public_design_version_cache()

    return _version_list_item(doc)


@router.delete(
    "/versions/{version_id}",
    dependencies=[Depends(require_permission("admin:design"))],
)
async def delete_design_version(version_id: str):
    """Delete one saved design version."""
    from bson import ObjectId

    coll = _db()[VERSIONS_COLLECTION]

    try:
        oid = ObjectId(version_id)
    except Exception:
        raise HTTPException(400, "Invalid version ID")

    target = await coll.find_one({"_id": oid}, projection={"_id": 1, "is_published": 1})
    if not target:
        raise HTTPException(404, "Version not found")
    if bool(target.get("is_published")):
        raise HTTPException(400, "Published version cannot be deleted")

    await coll.delete_one({"_id": oid})
    await _clear_design_comparison_version(version_id)

    return {"deleted": True}


@router.post(
    "/versions/{version_id}/load",
    dependencies=[Depends(require_permission("admin:design"))],
)
async def load_design_version(version_id: str):
    """Restore design settings from a saved full version snapshot."""
    from bson import ObjectId

    coll_v = _db()[VERSIONS_COLLECTION]
    design_coll = _design_config_coll()

    try:
        version_doc = await coll_v.find_one({"_id": ObjectId(version_id)})
    except Exception:
        raise HTTPException(400, "Invalid version ID")

    if not version_doc:
        raise HTTPException(404, "Version not found")

    design_data = await _resolve_version(version_doc)
    now = datetime.utcnow()

    if design_data:
        design_data = dict(design_data)
        design_data["key"] = "global"
        design_data["updated_at"] = now
        design_data[DESIGN_COMPARISON_VERSION_FIELD] = version_id
        current = await design_coll.find_one({"key": "global"})
        if current:
            design_data["created_at"] = current.get("created_at", now)
            await design_coll.update_one({"key": "global"}, {"$set": design_data})
        else:
            design_data["created_at"] = now
            await design_coll.insert_one(design_data)

    return {"loaded": True, "version_id": version_id}
