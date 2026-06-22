/**
 * Single source of truth for all design parameters.
 * 
 * Add a parameter here and it automatically:
 * - Gets snake_case backend key derived from camelCase
 * - Appears in DesignPanel under the specified section
 * - Uses the specified UI control type
 * - Is available for section design overrides if overridable: true
 */

// Utility: convert camelCase to snake_case
function toSnakeCase(str) {
    return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
}

function toCamelCase(str) {
    return String(str || "").replace(/_([a-z0-9])/g, (_, letter) => letter.toUpperCase());
}

// Some backend fields include an underscore before trailing numeric suffixes.
// Keep explicit mappings here so read/write paths stay consistent.
const BACKEND_KEY_OVERRIDES = {
    sectionBgColor1: 'section_bg_color_1',
    sectionBgColor2: 'section_bg_color_2',
    sectionBgOpacity1: 'section_bg_opacity_1',
    sectionBgOpacity2: 'section_bg_opacity_2',
};

export function toBackendKey(frontKey) {
    return BACKEND_KEY_OVERRIDES[frontKey] || toSnakeCase(frontKey);
}

function normalizeDesignParamKey(rawKey) {
    const key = String(rawKey || "").trim();
    if (!key) return key;
    if (Object.prototype.hasOwnProperty.call(DESIGN_PARAMS, key)) return key;
    const camelKey = toCamelCase(key);
    if (Object.prototype.hasOwnProperty.call(DESIGN_PARAMS, camelKey)) return camelKey;
    return key;
}

function normalizeParamKeyMap(rawMap) {
    if (!rawMap || typeof rawMap !== "object" || Array.isArray(rawMap)) return {};
    const normalized = {};
    for (const [rawKey, value] of Object.entries(rawMap)) {
        const key = normalizeDesignParamKey(rawKey);
        if (!Object.prototype.hasOwnProperty.call(normalized, key) || key === rawKey) {
            normalized[key] = value;
        }
    }
    return normalized;
}

/**
 * Design parameter definitions.
 * 
 * Required fields:
 *   - default: Default value
 *   - section: Panel section ('fonts', 'colors', 'sections', 'header', 'layout', 'buttons', 'customCss')
 *   - type: UI control type ('slider', 'color', 'checkbox', 'dropdown', 'fontfamily', 'buttongroup', 'positiongrid', 'textarea', 'image')
 *   - label: Display label
 * 
 * Optional fields:
 *   - subsection: Group within section
 *   - min, max, step, unit: For sliders
 *   - enabledOptions: For dropdowns
 *   - overridable: true if available in section design overrides
 *   - hidden: Function(design) => boolean for conditional visibility
 */
export const DESIGN_PARAMS = {
    // ═══════════════════════════════════════════════════════════════════════════
    // TYPOGRAPHY - HEADINGS
    // ═══════════════════════════════════════════════════════════════════════════
    headerFontFamily: {
        default: 'system-ui, -apple-system, sans-serif',
        section: 'fonts', type: 'fontfamily', label: 'Font Family',
        subsection: 'Headings',
    },
    headerTextDecoration: {
        default: 'none',
        section: 'fonts', type: 'dropdown', label: 'Text Decoration',
        subsection: 'Headings', enabledOptions: ['none', 'underline'],
    },
    headingLinearScaling: {
        default: true,
        section: 'fonts', type: 'checkbox', label: 'Linear Scaling',
        subsection: 'Headings',
    },
    // Shared heading defaults (used for derived heading scaling logic)
    headerFontWeight: { default: '800', section: null },
    headerFontSizeMax: { default: 48, section: null },
    headerFontSizeMin: { default: 14, section: null },
    headerLetterSpacing: { default: -0.02, section: null },
    headerLineHeight: { default: 1.2, section: null },

    // Per-heading typography (H1)
    h1FontSize: { default: 48, section: 'fonts', type: 'slider', label: 'Font Size', subsection: 'H1', min: 24, max: 96, step: 1, unit: 'px' },
    h1FontWeight: { default: '800', section: 'fonts', type: 'dropdown', label: 'Font Weight', subsection: 'H1' },
    h1LetterSpacing: { default: -0.02, section: 'fonts', type: 'slider', label: 'Letter Spacing', subsection: 'H1', min: -0.05, max: 0.2, step: 0.01, unit: 'em' },
    h1LineHeight: { default: 1.2, section: 'fonts', type: 'slider', label: 'Line Height', subsection: 'H1', min: 0.8, max: 2, step: 0.05, unit: '' },
    // H2
    h2FontSize: { default: 41, section: 'fonts', type: 'slider', label: 'Font Size', subsection: 'H2', min: 20, max: 72, step: 1, unit: 'px' },
    h2FontWeight: { default: '800', section: 'fonts', type: 'dropdown', label: 'Font Weight', subsection: 'H2' },
    h2LetterSpacing: { default: -0.02, section: 'fonts', type: 'slider', label: 'Letter Spacing', subsection: 'H2', min: -0.05, max: 0.2, step: 0.01, unit: 'em' },
    h2LineHeight: { default: 1.2, section: 'fonts', type: 'slider', label: 'Line Height', subsection: 'H2', min: 0.8, max: 2, step: 0.05, unit: '' },
    // H3
    h3FontSize: { default: 34, section: 'fonts', type: 'slider', label: 'Font Size', subsection: 'H3', min: 18, max: 56, step: 1, unit: 'px' },
    h3FontWeight: { default: '800', section: 'fonts', type: 'dropdown', label: 'Font Weight', subsection: 'H3' },
    h3LetterSpacing: { default: -0.02, section: 'fonts', type: 'slider', label: 'Letter Spacing', subsection: 'H3', min: -0.05, max: 0.2, step: 0.01, unit: 'em' },
    h3LineHeight: { default: 1.2, section: 'fonts', type: 'slider', label: 'Line Height', subsection: 'H3', min: 0.8, max: 2, step: 0.05, unit: '' },
    // H4
    h4FontSize: { default: 28, section: 'fonts', type: 'slider', label: 'Font Size', subsection: 'H4', min: 16, max: 48, step: 1, unit: 'px' },
    h4FontWeight: { default: '700', section: 'fonts', type: 'dropdown', label: 'Font Weight', subsection: 'H4' },
    h4LetterSpacing: { default: -0.01, section: 'fonts', type: 'slider', label: 'Letter Spacing', subsection: 'H4', min: -0.05, max: 0.2, step: 0.01, unit: 'em' },
    h4LineHeight: { default: 1.25, section: 'fonts', type: 'slider', label: 'Line Height', subsection: 'H4', min: 0.8, max: 2, step: 0.05, unit: '' },
    // H5
    h5FontSize: { default: 21, section: 'fonts', type: 'slider', label: 'Font Size', subsection: 'H5', min: 14, max: 36, step: 1, unit: 'px' },
    h5FontWeight: { default: '700', section: 'fonts', type: 'dropdown', label: 'Font Weight', subsection: 'H5' },
    h5LetterSpacing: { default: 0, section: 'fonts', type: 'slider', label: 'Letter Spacing', subsection: 'H5', min: -0.05, max: 0.2, step: 0.01, unit: 'em' },
    h5LineHeight: { default: 1.3, section: 'fonts', type: 'slider', label: 'Line Height', subsection: 'H5', min: 0.8, max: 2, step: 0.05, unit: '' },
    // H6
    h6FontSize: { default: 14, section: 'fonts', type: 'slider', label: 'Font Size', subsection: 'H6', min: 8, max: 28, step: 1, unit: 'px' },
    h6FontWeight: { default: '700', section: 'fonts', type: 'dropdown', label: 'Font Weight', subsection: 'H6' },
    h6LetterSpacing: { default: 0, section: 'fonts', type: 'slider', label: 'Letter Spacing', subsection: 'H6', min: -0.05, max: 0.2, step: 0.01, unit: 'em' },
    h6LineHeight: { default: 1.3, section: 'fonts', type: 'slider', label: 'Line Height', subsection: 'H6', min: 0.8, max: 2, step: 0.05, unit: '' },

    // ═══════════════════════════════════════════════════════════════════════════
    // TYPOGRAPHY - BODY
    // ═══════════════════════════════════════════════════════════════════════════
    bodyFontFamily: { default: 'system-ui, -apple-system, sans-serif', section: 'fonts', type: 'fontfamily', label: 'Font Family', subsection: 'Paragraph' },
    bodyFontWeight: { default: '400', section: 'fonts', type: 'dropdown', label: 'Font Weight', subsection: 'Paragraph' },
    bodyLetterSpacing: { default: 0, section: 'fonts', type: 'slider', label: 'Letter Spacing', subsection: 'Paragraph', min: -0.02, max: 0.1, step: 0.005, unit: 'em' },
    bodyLineHeight: { default: 1.65, section: 'fonts', type: 'slider', label: 'Line Height', subsection: 'Paragraph', min: 1, max: 2.5, step: 0.05, unit: '' },

    // ═══════════════════════════════════════════════════════════════════════════
    // TYPOGRAPHY - LINKS
    // ═══════════════════════════════════════════════════════════════════════════
    linkTextDecoration: { default: 'none', section: 'fonts', type: 'dropdown', label: 'Text Decoration', subsection: 'Links', enabledOptions: ['none', 'underline'] },
    linkHoverTextDecoration: { default: 'underline', section: 'fonts', type: 'dropdown', label: 'Hover Decoration', subsection: 'Links', enabledOptions: ['none', 'underline'] },

    // ═══════════════════════════════════════════════════════════════════════════
    // TYPOGRAPHY - HERO
    // ═══════════════════════════════════════════════════════════════════════════
    heroTitleFontSize: { default: null, section: 'fonts', type: 'slider', label: 'Font Size', subsection: 'Hero Title', min: 24, max: 120, step: 1, unit: 'px' },
    heroTitleLineHeight: { default: null, section: 'fonts', type: 'slider', label: 'Line Height', subsection: 'Hero Title', min: 0.8, max: 2, step: 0.05, unit: '' },
    heroTitleLetterSpacing: { default: null, section: 'fonts', type: 'slider', label: 'Letter Spacing', subsection: 'Hero Title', min: -0.05, max: 0.2, step: 0.01, unit: 'em' },
    heroSubtitleFontSize: { default: null, section: 'fonts', type: 'slider', label: 'Font Size', subsection: 'Hero Subtitle', min: 12, max: 48, step: 1, unit: 'px' },
    heroSubtitleLineHeight: { default: null, section: 'fonts', type: 'slider', label: 'Line Height', subsection: 'Hero Subtitle', min: 0.8, max: 2, step: 0.05, unit: '' },
    heroSubtitleLetterSpacing: { default: null, section: 'fonts', type: 'slider', label: 'Letter Spacing', subsection: 'Hero Subtitle', min: -0.02, max: 0.1, step: 0.005, unit: 'em' },

    // ═══════════════════════════════════════════════════════════════════════════
    // COLORS
    // ═══════════════════════════════════════════════════════════════════════════
    primaryColor: { default: '#0b1220', section: 'colors', type: 'color', label: 'Primary Color', isBase: true, subsection: 'Base Vars' },
    secondaryColor: { default: '#334155', section: 'colors', type: 'color', label: 'Secondary Color', isBase: true, subsection: 'Base Vars' },
    backgroundPrimaryColor: { default: '#f6f7fb', section: 'colors', type: 'color', label: 'Background Primary', isBase: true, subsection: 'Base Vars' },
    backgroundSecondaryColor: { default: '#ffffff', section: 'colors', type: 'color', label: 'Background Secondary', isBase: true, subsection: 'Base Vars' },
    accentColor: { default: '#4f46e5', section: 'colors', type: 'color', label: 'Accent Color', isBase: true, subsection: 'Base Vars' },
    backgroundColor: { default: '#f6f7fb', section: 'colors', type: 'color', label: 'Page Background', linkable: true, showLinkInPanel: true, subsection: 'Background' },
    sectionBackgroundColor: { default: '#ffffff', section: 'colors', type: 'color', label: 'Section Background', linkable: true, showLinkInPanel: true, subsection: 'Background', overridable: true },
    topbarBgColor: { default: null, section: 'colors', type: 'color', label: 'Topbar Background', subsection: 'Topbar', linkable: true, showLinkInPanel: true },
    topbarItemColor: { default: null, section: 'colors', type: 'color', label: 'Topbar Item', subsection: 'Topbar', linkable: true, showLinkInPanel: true },
    topbarItemHoverColor: { default: null, section: 'colors', type: 'color', label: 'Topbar Item Hover', subsection: 'Topbar', linkable: true, showLinkInPanel: true },
    sidebarBgColor: { default: null, section: 'colors', type: 'color', label: 'Sidebar Background', subsection: 'Menus', linkable: true, showLinkInPanel: true },
    sidebarItemColor: { default: null, section: 'colors', type: 'color', label: 'Sidebar Item', subsection: 'Menus', linkable: true, showLinkInPanel: true },
    sidebarItemHoverColor: { default: null, section: 'colors', type: 'color', label: 'Sidebar Item Hover Text', subsection: 'Menus', linkable: true, showLinkInPanel: true },
    headingColor: { default: '#0b1220', section: 'colors', type: 'color', label: 'Heading Color (Fallback)', subsection: 'Typography', linkable: true, showLinkInPanel: true },
    h1Color: { default: null, section: 'colors', type: 'color', label: 'H1 Color', subsection: 'Typography', linkable: true, showLinkInPanel: true },
    h2Color: { default: null, section: 'colors', type: 'color', label: 'H2 Color', subsection: 'Typography', linkable: true, showLinkInPanel: true },
    h3Color: { default: null, section: 'colors', type: 'color', label: 'H3 Color', subsection: 'Typography', linkable: true, showLinkInPanel: true },
    h4Color: { default: null, section: 'colors', type: 'color', label: 'H4 Color', subsection: 'Typography', linkable: true, showLinkInPanel: true },
    paragraphColor: { default: '#334155', section: 'colors', type: 'color', label: 'Paragraph Color', subsection: 'Typography' },
    linkColor: { default: null, section: 'colors', type: 'color', label: 'Link Color', subsection: 'Links', linkable: true, showLinkInPanel: true },
    linkHoverColor: { default: null, section: 'colors', type: 'color', label: 'Link Hover Color', subsection: 'Links', linkable: true, showLinkInPanel: true },
    adminAccentColor: { default: '#cb00e6', section: 'colors', type: 'color', label: 'Admin Accent Color', subsection: 'Admin UI', linkable: true, showLinkInPanel: false, showInPanel: false },
    adminPrimaryColor: { default: '#4f46e5', section: 'colors', type: 'color', label: 'Admin Primary Color', subsection: 'Admin UI', linkable: false, showLinkInPanel: false, showInPanel: false },
    adminDangerColor: { default: '#dc2626', section: 'colors', type: 'color', label: 'Admin Danger Color', subsection: 'Admin UI', linkable: false, showLinkInPanel: false, showInPanel: false },
    adminWarningColor: { default: '#d97706', section: 'colors', type: 'color', label: 'Admin Warning Color', subsection: 'Admin UI', linkable: false, showLinkInPanel: false, showInPanel: false },
    adminFavoriteColor: { default: '#b45309', section: 'colors', type: 'color', label: 'Admin Favorite Color', subsection: 'Admin UI', linkable: false, showLinkInPanel: false, showInPanel: false },
    heroTitleColor: { default: null, section: 'colors', type: 'color', label: 'Hero Title Color', subsection: 'Header Titles' },
    heroSubtitleColor: { default: null, section: 'colors', type: 'color', label: 'Hero Subtitle Color', subsection: 'Header Titles' },
    highContrastDark: { default: '#0b1220', section: 'colors', type: 'color', label: 'Dark', subsection: 'High Contrast' },
    highContrastLight: { default: '#f8fafc', section: 'colors', type: 'color', label: 'Light', subsection: 'High Contrast' },
    // Internal map: { [paramKey]: 100 | 80 | 50 | 20 }
    colorVariations: { default: {}, section: null },

    // ═══════════════════════════════════════════════════════════════════════════
    // SECTION BACKGROUND PATTERN
    // ═══════════════════════════════════════════════════════════════════════════
    sectionBgPattern: { default: 'none', section: 'sections', type: 'dropdown', label: 'Pattern', subsection: 'Background Pattern' },
    sectionBgColor1: { default: '#ffffff', section: 'sections', type: 'color', label: 'Start Color', subsection: 'Background Pattern' },
    sectionBgColor2: { default: '#f0f0f0', section: 'sections', type: 'color', label: 'End Color', subsection: 'Background Pattern' },
    sectionBgOpacity1: { default: 1.0, section: 'sections', type: 'slider', label: 'Start Opacity', subsection: 'Background Pattern', min: 0, max: 1, step: 0.05, unit: '' },
    sectionBgOpacity2: { default: 0.3, section: 'sections', type: 'slider', label: 'End Opacity', subsection: 'Background Pattern', min: 0, max: 1, step: 0.05, unit: '' },
    sectionBgPinnedStartKey: { default: '', section: null },
    sectionBgPinnedEndKey: { default: '', section: null },

    // ═══════════════════════════════════════════════════════════════════════════
    // SECTIONS STYLING
    // ═══════════════════════════════════════════════════════════════════════════
    sectionBorderRadius: { default: 14, section: 'sections', type: 'slider', label: 'Border Radius', subsection: 'Container', min: 0, max: 48, step: 1, unit: 'px', overridable: true },
    sectionSpacing: { default: 14, section: 'layout', type: 'slider', label: 'Grid Spacing', subsection: 'Inner Spacing', min: 0, max: 48, step: 1, unit: 'px' },
    sectionPadding: { default: 18, section: 'sections', type: 'slider', label: 'Section Padding', subsection: 'Container', min: 0, max: 64, step: 1, unit: 'px', overridable: true },
    sectionContentAlign: { default: 'left', section: 'sections', type: 'dropdown', label: 'Content Align', subsection: 'Container', enabledOptions: ['left', 'center', 'right'], overridable: true },
    sectionBoxShadow: { default: '0 6px 20px rgba(17, 24, 39, 0.08)', section: 'sections', type: 'dropdown', label: 'Box Shadow', subsection: 'Container', overridable: true },
    sectionBorderWidth: { default: 0, section: 'sections', type: 'slider', label: 'Border Width', subsection: 'Border', min: 0, max: 10, step: 1, unit: 'px', overridable: true },
    sectionBorderColor: { default: '#0b1220', section: 'sections', type: 'color', label: 'Border Color', subsection: 'Border', overridable: true },
    sectionBorderStyle: { default: 'solid', section: 'sections', type: 'dropdown', label: 'Border Style', subsection: 'Border', enabledOptions: ['solid', 'dashed', 'dotted', 'double', 'none'], overridable: true },
    hardBoxShadowEnabled: { default: false, section: 'sections', type: 'checkbox', label: 'Enable Hard Box-Shadow', subsection: 'Hardbox Shadow', overridable: true },
    hardBoxShadowBrightness: { default: -15, section: 'sections', type: 'slider', label: 'Brightness', subsection: 'Hardbox Shadow', min: -50, max: 50, step: 5, unit: '%', overridable: true },
    hardBoxShadowOffsetSource: { default: 'padding', section: 'sections', type: 'dropdown', label: 'Offset Source', subsection: 'Hardbox Shadow', overridable: true },
    hardBoxShadowOffsetCustom: { default: 18, section: 'sections', type: 'slider', label: 'Custom Offset', subsection: 'Hardbox Shadow', min: 0, max: 48, step: 1, unit: 'px', overridable: true },

    // ═══════════════════════════════════════════════════════════════════════════
    // CUSTOM CSS
    // ═══════════════════════════════════════════════════════════════════════════
    globalCustomCss: { default: '', section: 'customCss', type: 'textarea', label: 'Global Custom CSS' },
    globalCustomCssTablet: { default: '', section: 'customCss', type: 'textarea', label: 'Tablet CSS' },
    globalCustomCssMobile: { default: '', section: 'customCss', type: 'textarea', label: 'Mobile CSS' },

    // ═══════════════════════════════════════════════════════════════════════════
    // LAYOUT
    // ═══════════════════════════════════════════════════════════════════════════
    fullWidth: { default: false, section: 'layout', type: 'checkbox', label: 'Full Width Layout' },
    navigationMenuView: { default: 'sidebar', section: 'layout', type: 'dropdown', label: 'Menu View', subsection: 'Navigation', enabledOptions: ['sidebar', 'below_topbar'] },
    outerSpacingSection: { default: 0, section: 'layout', type: 'slider', label: 'Outer Spacing (Sections)', min: 0, max: 64, step: 1, unit: 'px' },
    outerSpacingNonSection: { default: 0, section: 'layout', type: 'slider', label: 'Outer Spacing (Non-Section)', min: 0, max: 64, step: 1, unit: 'px' },
    contentPaddingTop: { default: 22, section: 'layout', type: 'slider', label: 'Content Padding Top', min: 0, max: 100, step: 1, unit: 'px' },
    contentPaddingBottom: { default: 26, section: 'layout', type: 'slider', label: 'Content Padding Bottom', min: 0, max: 100, step: 1, unit: 'px' },

    // ═══════════════════════════════════════════════════════════════════════════
    // BUTTONS
    // ═══════════════════════════════════════════════════════════════════════════
    buttonBorderRadius: { default: 12, section: 'buttons', type: 'slider', label: 'Border Radius', min: 0, max: 24, step: 1, unit: 'px' },
    buttonBorderWidth: { default: 1, section: 'buttons', type: 'slider', label: 'Border Width', min: 0, max: 4, step: 1, unit: 'px' },
    buttonBorderColor: { default: null, section: 'buttons', type: 'color', label: 'Border Color' },
    buttonBgColor: { default: null, section: 'buttons', type: 'color', label: 'Background' },
    buttonColor: { default: null, section: 'buttons', type: 'color', label: 'Text Color' },
    buttonHoverBorderColor: { default: null, section: 'buttons', type: 'color', label: 'Hover Border Color' },
    buttonHoverBgColor: { default: null, section: 'buttons', type: 'color', label: 'Hover Background' },
    buttonHoverColor: { default: null, section: 'buttons', type: 'color', label: 'Hover Text Color' },
    buttonFontSize: { default: 16, section: 'buttons', type: 'slider', label: 'Font Size', min: 10, max: 32, step: 1, unit: 'px' },
    buttonPaddingX: { default: 12, section: 'buttons', type: 'slider', label: 'Horizontal Padding', min: 8, max: 32, step: 2, unit: 'px' },
    buttonPaddingY: { default: 10, section: 'buttons', type: 'slider', label: 'Vertical Padding', min: 4, max: 20, step: 2, unit: 'px' },

    // ═══════════════════════════════════════════════════════════════════════════
    // HEADER
    // ═══════════════════════════════════════════════════════════════════════════
    heroHeight: { default: 400, section: 'header', type: 'slider', label: 'Header Height', min: 200, max: 800, step: 10, unit: 'px' },
    headerInner: { default: 44, section: 'header', type: 'slider', label: 'Header Inner', subsection: 'Container', min: 0, max: 200, step: 2, unit: 'px' },
    heroContentAlign: { default: 'left', section: 'header', type: 'buttongroup', label: 'Content Alignment' },
    heroOverlayPosition: { default: 'bottom-right', section: 'header', type: 'positiongrid', label: 'Position', subsection: 'Overlay Image' },
    heroOverlaySize: { default: 150, section: 'header', type: 'slider', label: 'Size', subsection: 'Overlay Image', min: 50, max: 500, step: 10, unit: 'px' },
    heroOverlayParallax: { default: false, section: 'header', type: 'checkbox', label: 'Parallax Overlay', subsection: 'Overlay Image' },
    heroOverlayParallaxDirection: { default: 'down', section: 'header', type: 'dropdown', label: 'Overlay Direction', subsection: 'Parallax Effect', enabledOptions: ['down', 'parabola'] },
    heroSeparator: { default: 'none', section: 'header', type: 'dropdown', label: 'Style', subsection: 'Bottom Separator' },
    heroParallax: { default: false, section: 'header', type: 'checkbox', label: 'Parallax Background' },
    heroTitleTextShadowEnabled: { default: false, section: 'header', type: 'checkbox', label: 'Enable Text Shadow', subsection: 'Hero Title Shadow' },
    heroTitleTextShadowOffset: { default: 4, section: 'header', type: 'slider', label: 'Offset', subsection: 'Hero Title Shadow', min: 0, max: 20, step: 1, unit: 'px' },
    heroTitleTextShadowColor: { default: null, section: 'header', type: 'color', label: 'Color', subsection: 'Hero Title Shadow' },
};

function prettifyOptionLabel(value) {
    const raw = String(value ?? "");
    if (!raw) return "";
    return raw
        .replace(/[_-]+/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());
}

export const DESIGN_PARAM_OPTIONS = {
    navigationMenuView: [
        { value: "sidebar", label: "Sidebar" },
        { value: "below_topbar", label: "Below Topbar" },
    ],
    sectionBgPattern: [
        { value: "none", label: "None (uniform)" },
        { value: "alternating", label: "Alternating" },
        { value: "gradient", label: "Gradient" },
        { value: "gradient_shuffled", label: "Gradient Shuffled" },
        { value: "alpha_gradient", label: "Alpha Gradient" },
        { value: "alpha_gradient_shuffled", label: "Alpha Gradient Shuffled" },
    ],
    hardBoxShadowMode: [
        { value: "", label: "Inherit Global" },
        { value: "on", label: "Force On" },
        { value: "off", label: "Force Off" },
    ],
    hardBoxShadowOffsetSource: [
        { value: "padding", label: "Section Padding" },
        { value: "spacing", label: "Section Spacing" },
        { value: "custom", label: "Custom" },
    ],
    sectionBoxShadow: [
        { value: "none", label: "None" },
        { value: "0 2px 8px rgba(0, 0, 0, 0.04)", label: "Subtle" },
        { value: "0 6px 20px rgba(17, 24, 39, 0.08)", label: "Soft (Default)" },
        { value: "0 10px 30px rgba(17, 24, 39, 0.12)", label: "Medium" },
        { value: "0 16px 40px rgba(17, 24, 39, 0.16)", label: "Strong" },
    ],
    heroSeparator: [
        { value: "none", label: "None" },
        { value: "inward-shadow", label: "Inward Shadow" },
        { value: "border", label: "Border" },
    ],
    heroOverlayParallaxDirection: [
        { value: "down", label: "Downward" },
        { value: "parabola", label: "Parabola" },
    ],
    sectionBorderStyle: [
        { value: "solid", label: "Solid" },
        { value: "dashed", label: "Dashed" },
        { value: "dotted", label: "Dotted" },
        { value: "double", label: "Double" },
        { value: "none", label: "None" },
    ],
    sectionContentAlign: [
        { value: "left", label: "Left" },
        { value: "center", label: "Center" },
        { value: "right", label: "Right" },
    ],
    heroContentAlign: [
        { value: "left", label: "Left" },
        { value: "center", label: "Center" },
        { value: "right", label: "Right" },
    ],
    headerTextDecoration: [
        { value: "none", label: "None" },
        { value: "underline", label: "Underline" },
    ],
    linkTextDecoration: [
        { value: "none", label: "None" },
        { value: "underline", label: "Underline" },
    ],
    linkHoverTextDecoration: [
        { value: "none", label: "None" },
        { value: "underline", label: "Underline" },
    ],
    headerFontWeight: [
        { value: "300", label: "Light (300)" },
        { value: "400", label: "Regular (400)" },
        { value: "500", label: "Medium (500)" },
        { value: "600", label: "Semi-Bold (600)" },
        { value: "700", label: "Bold (700)" },
        { value: "800", label: "Extra-Bold (800)" },
        { value: "900", label: "Black (900)" },
    ],
    bodyFontWeight: [
        { value: "300", label: "Light (300)" },
        { value: "400", label: "Regular (400)" },
        { value: "500", label: "Medium (500)" },
        { value: "600", label: "Semi-Bold (600)" },
        { value: "700", label: "Bold (700)" },
        { value: "800", label: "Extra-Bold (800)" },
        { value: "900", label: "Black (900)" },
    ],
};

const _weightOpts = DESIGN_PARAM_OPTIONS.headerFontWeight;
for (let i = 1; i <= 6; i++) {
    DESIGN_PARAM_OPTIONS[`h${i}FontWeight`] = _weightOpts;
}
DESIGN_PARAM_OPTIONS.textFontWeight = DESIGN_PARAM_OPTIONS.bodyFontWeight;

export function getParamOptionDefs(paramKey, enabledOptions = null) {
    const all = DESIGN_PARAM_OPTIONS[paramKey];
    if (Array.isArray(all)) {
        if (!Array.isArray(enabledOptions)) return all;
        const enabledSet = new Set(enabledOptions);
        const filtered = all.filter((opt) => enabledSet.has(opt.value));
        for (const value of enabledOptions) {
            if (!filtered.some((opt) => opt.value === value)) {
                filtered.push({ value, label: prettifyOptionLabel(value) });
            }
        }
        return filtered;
    }
    if (Array.isArray(enabledOptions)) {
        return enabledOptions.map((value) => ({ value, label: prettifyOptionLabel(value) }));
    }
    return [];
}

export function getParamOptionValues(paramKey, fallback = []) {
    const all = DESIGN_PARAM_OPTIONS[paramKey];
    if (Array.isArray(all)) return all.map((opt) => opt.value);
    return Array.isArray(fallback) ? fallback : [];
}

export function getParamOptionLabel(paramKey, value) {
    const all = DESIGN_PARAM_OPTIONS[paramKey];
    if (Array.isArray(all)) {
        const found = all.find((opt) => opt.value === value);
        if (found) return found.label;
    }
    return prettifyOptionLabel(value);
}

// ═══════════════════════════════════════════════════════════════════════════════
// DERIVED EXPORTS - Auto-generated from DESIGN_PARAMS
// ═══════════════════════════════════════════════════════════════════════════════

/** Format: { camelCase: [snake_case, default] } */
export const DESIGN_FIELD_DEFS = Object.fromEntries(
    Object.entries(DESIGN_PARAMS).map(([key, cfg]) => [key, [toBackendKey(key), cfg.default]])
);

/** Default design settings keyed by camelCase frontend names. */
export const DEFAULT_DESIGN = Object.fromEntries(
    Object.entries(DESIGN_PARAMS).map(([key, cfg]) => [key, cfg.default])
);

/** UI configs for DesignPanel, keyed by param name */
export const PARAM_CONFIGS = Object.fromEntries(
    Object.entries(DESIGN_PARAMS)
        .filter(([, cfg]) => cfg.section !== null && cfg.type)
        .map(([key, cfg]) => {
            const config = {
                visible: true,
                favorite: false,
                section: cfg.section,
                type: cfg.type,
                label: cfg.label || key,
            };
            if (cfg.subsection) config.subsection = cfg.subsection;
            if (cfg.min !== undefined) config.min = cfg.min;
            if (cfg.max !== undefined) config.max = cfg.max;
            if (cfg.step !== undefined) config.step = cfg.step;
            if (cfg.unit !== undefined) config.unit = cfg.unit;
            if (cfg.enabledOptions) config.enabledOptions = cfg.enabledOptions;
            if (cfg.isBase) config.isBase = cfg.isBase;
            if (cfg.linkable !== undefined) config.linkable = cfg.linkable;
            if (cfg.showLinkInPanel !== undefined) config.showLinkInPanel = cfg.showLinkInPanel;
            if (cfg.showInPanel !== undefined) config.showInPanel = cfg.showInPanel;
            return [key, config];
        })
);

/** Parameters grouped by section for DesignPanel */
export const PARAMS_BY_SECTION = (() => {
    const result = {};
    for (const [key, cfg] of Object.entries(DESIGN_PARAMS)) {
        if (cfg.section) {
            if (!result[cfg.section]) result[cfg.section] = [];
            result[cfg.section].push(key);
        }
    }
    return result;
})();

/** Parameters available for section design overrides */
export const OVERRIDABLE_PARAMS = Object.entries(DESIGN_PARAMS)
    .filter(([, cfg]) => cfg.overridable)
    .map(([key]) => key);

/**
 * Convert a backend snake_case response object to a frontend camelCase design object.
 * Missing or null non-nullable fields fall back to their declared default.
 */
export function mapBackendToFrontendDesign(backendData) {
    const result = {};
    for (const [frontKey, cfg] of Object.entries(DESIGN_PARAMS)) {
        const backKey = toBackendKey(frontKey);
        result[frontKey] = backendData[backKey] ?? cfg.default;
    }

    if (backendData.button_type_styles) {
        result.buttonTypeStyles = backendData.button_type_styles;
    }
    if (backendData.responsive_values) {
        result.responsiveValues = normalizeParamKeyMap(backendData.responsive_values);
    }
    if (backendData.selected_units) {
        result.selectedUnits = normalizeParamKeyMap(backendData.selected_units);
    }
    if (result.colorVariations && typeof result.colorVariations === "object" && !Array.isArray(result.colorVariations)) {
        result.colorVariations = normalizeParamKeyMap(result.colorVariations);
    } else {
        result.colorVariations = {};
    }
    return result;
}

/**
 * Convert a frontend camelCase design object to backend snake_case format.
 */
export function mapDesignToBackendFull(design) {
    const backend = {};
    for (const frontKey of Object.keys(DESIGN_PARAMS)) {
        const backKey = toBackendKey(frontKey);
        if (design[frontKey] !== undefined) {
            backend[backKey] = design[frontKey];
        }
    }
    if (design.buttonTypeStyles && Object.keys(design.buttonTypeStyles).length > 0) {
        backend.button_type_styles = design.buttonTypeStyles;
    } else {
        backend.button_type_styles = null;
    }
    if (design.responsiveValues && Object.keys(design.responsiveValues).length > 0) {
        backend.responsive_values = design.responsiveValues;
    } else {
        backend.responsive_values = null;
    }
    if (design.selectedUnits && Object.keys(design.selectedUnits).length > 0) {
        backend.selected_units = design.selectedUnits;
    } else {
        backend.selected_units = null;
    }
    return backend;
}
