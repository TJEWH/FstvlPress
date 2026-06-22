import { reactive, computed } from "vue";
import * as api from "../services/api.js";
import { DEFAULT_DESIGN, mapBackendToFrontendDesign, mapDesignToBackendFull } from "../designDefs.js";
import {
    buildResponsiveCssVars,
    buildResponsiveMediaQuery,
    getEffectiveResponsiveDevice,
    getResponsivePreviewSize,
    normalizeResponsiveConfig,
} from "../utils/responsiveViewport.js";
import { BASE_VARS_SUBSECTION, isBaseColorLinkKey, resolveHighContrastColorForBackground } from "../utils/colorLinkOptions.js";
import { applyColorVariation, normalizeColorVariation } from "../utils/colorVariations.js";
import {
    resolveBackendResponsiveImagePayload,
    resolveFrontendResponsiveImagePayload,
} from "../utils/responsiveImages.js";
import { normalizeFallbackImageConfig } from "../utils/fallbackImages.js";
import {
    buildSectionContainerMaps,
    deriveSectionOrderFromStructure,
    buildSectionStructureFromEntries,
    buildSectionStructureFromOrder,
} from "../utils/sectionContainers.js";

const state = reactive({
    lang: "de",
    isAdmin: false,
    internalRole: "no_access",
    canContent: false,
    canDesign: false,
    canAdminDesign: false,
    canAdminGeneral: false,
    previewMode: false,
    loading: false,
    error: null,
    initialized: false,

    _debug: {
        enabled: false,
        events: []
    },

    // Page management
    pageSlug: null,
    pageTitle: { de: "", en: "" },
    currentPageStatus: null,
    currentPageEffectiveStatus: null,
    currentPageIsVisible: null,
    pageTemplateStyleRef: null,
    pageTemplateStyleLinked: false,
    pageTemplateStyleLock: false,
    
    // Design settings
    design: { ...DEFAULT_DESIGN },
    designFontStylesheetUrls: [],
    simulatedViewport: null,
    viewportWidth: typeof window !== "undefined" ? window.innerWidth : 1024,
    viewportHeight: typeof window !== "undefined" ? window.innerHeight : 768,
    hideResponsiveUI: false,
    designPanelVisibleInSim: true,
    
    // Section data
    tickerItems: [],
    faqItems: [],
    faqTags: [],    // Shared FAQ topics
    faqSharedLoaded: false,
    faqSharedSource: "",
    blogItems: [],   // Shared across all blog sections
    blogTags: [],    // From blog config API
    programSharedGigs: [],   // Shared across all program sections
    programSharedStages: [], // Shared across all program sections
    programSharedStagesIntegrationMapping: {},
    programSharedStagesIntegrationMappingCacheState: {},
    programSharedGigsIntegrationMapping: {},
    programSharedGigsIntegrationMappingCacheState: {},
    programSharedLoaded: false,
    programSharedScope: "none",
    sectionsData: {},    // New section storage by unique key (supports multiple instances)
    sectionIds: {},
    sectionMeta: {},
    landingLayout: {
        order: [],
        structure: [],
        hidden: {},
        widths: {},
        deviceVisibility: {},
        gridCols: 1,
        fullWidth: false,
        sectionBgPinnedStartKey: '',
        sectionBgPinnedEndKey: ''
    },
    sectionDesignOverrides: {},  // { [sectionKey]: { sectionBackgroundColor, sectionBorderRadius, ... } }
    sectionCustomCssDrafts: {},  // transient live CSS by sectionKey (not persisted)
    publicCssSnippets: [],       // active public CSS snippets hydrated from the public page bundle
    mediaFallbacks: normalizeFallbackImageConfig(),
    activeSectionDesignKey: null,  // section key whose design panel is open
    sectionAdminActiveTabs: {}, // { [sectionKey]: "design" | "content" | "history" | "notes" }
    sectionAdminPinnedEditors: [], // [{ id, sectionKey, label }]
    sectionAdminPinnedActiveId: "",
    sectionAdminPinnedSharedTab: "",
    sectionAdminPinnedSharedHeightPx: null,
    
    // Revision status for undo/redo
    revisionStatus: {},  // { [sectionKey]: { canUndo, canRedo, lastSavedBy } }
    sectionSaveStatus: {}, // { [sectionKey]: { status, error } }
    headerRevisionStatus: { enabled: true, canUndo: false, canRedo: false, lastSavedBy: null },
    headerId: null,
    headerEnabledFields: [],
    
    // Design revision status
    designId: null,
    designRevisionStatus: { enabled: true, canUndo: false, canRedo: false, lastSavedBy: null },
    templatePageDesignMeta: null,
    templatePagePublishedDesign: null,

    // Admin design config (loaded from backend)
    adminDesignConfig: null,

    // Dirty tracking for unsaved changes
    designDirty: false,
    _designSnapshot: null,
});

function logDebug(type, data = {}) {
    if (!state._debug?.enabled) return;
    state._debug.events.unshift({ ts: new Date().toISOString(), type, data });
    if (state._debug.events.length > 80) state._debug.events.length = 80;
}

function hashString(value) {
    const source = String(value || '');
    let hash = 0;
    for (let i = 0; i < source.length; i += 1) {
        hash = (hash * 31 + source.charCodeAt(i)) | 0;
    }
    return String(Math.abs(hash));
}

function localFontLinkId(url) {
    return `fstvlpress-cached-font-${hashString(url)}`;
}

function normalizeFontStylesheetUrls(urls) {
    if (!Array.isArray(urls)) return [];
    const normalized = [];
    const seen = new Set();
    for (const raw of urls) {
        const value = String(raw || '').trim();
        if (!value || seen.has(value)) continue;
        seen.add(value);
        normalized.push(value);
    }
    return normalized;
}

function ensureCachedFontStylesheetsLoaded(urls) {
    if (typeof document === 'undefined') return;
    const normalized = normalizeFontStylesheetUrls(urls);
    const targetSet = new Set(normalized);

    document.querySelectorAll('link[data-fstvlpress-font-cache="true"]').forEach((node) => {
        const href = String(node.getAttribute('href') || '').trim();
        if (!targetSet.has(href)) {
            node.remove();
        }
    });

    for (const url of normalized) {
        const linkId = localFontLinkId(url);
        if (document.getElementById(linkId)) continue;
        const link = document.createElement('link');
        link.id = linkId;
        link.rel = 'stylesheet';
        link.href = url;
        link.setAttribute('data-fstvlpress-font-cache', 'true');
        document.head.appendChild(link);
    }
}

function setDesignFontStylesheetUrls(urls) {
    state.designFontStylesheetUrls = normalizeFontStylesheetUrls(urls);
    ensureCachedFontStylesheetsLoaded(state.designFontStylesheetUrls);
}

function applyMediaFallbacks(payload) {
    state.mediaFallbacks = normalizeFallbackImageConfig(payload);
}

// -------------------------
// Case conversion utilities
// -------------------------

function toSnakeCase(str) {
    return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
}

function toCamelCase(str) {
    return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function toCamelCasePreserveUnderscorePrefix(str) {
    const raw = String(str || "");
    if (!raw.startsWith("_")) return toCamelCase(raw);
    const match = raw.match(/^_+/);
    const prefix = match ? match[0] : "_";
    const rest = raw.slice(prefix.length);
    if (!rest) return raw;
    return `${prefix}${toCamelCase(rest)}`;
}

function convertKeysToSnake(obj) {
    if (Array.isArray(obj)) return obj.map(convertKeysToSnake);
    if (obj !== null && typeof obj === 'object') {
        return Object.fromEntries(
            Object.entries(obj).map(([key, val]) => [toSnakeCase(key), convertKeysToSnake(val)])
        );
    }
    return obj;
}

function convertKeysToCamel(obj) {
    if (Array.isArray(obj)) return obj.map(convertKeysToCamel);
    if (obj !== null && typeof obj === 'object') {
        return Object.fromEntries(
            Object.entries(obj).map(([key, val]) => [toCamelCase(key), convertKeysToCamel(val)])
        );
    }
    return obj;
}

function convertKeysToCamelPreserveUnderscorePrefix(obj) {
    if (Array.isArray(obj)) return obj.map(convertKeysToCamelPreserveUnderscorePrefix);
    if (obj !== null && typeof obj === 'object') {
        return Object.fromEntries(
            Object.entries(obj).map(([key, val]) => [
                toCamelCasePreserveUnderscorePrefix(key),
                convertKeysToCamelPreserveUnderscorePrefix(val),
            ])
        );
    }
    return obj;
}

function normalizeSectionGenericForBackend(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
    return convertKeysToSnake(value);
}

function normalizeSectionGenericForFrontend(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
    return convertKeysToCamel(value);
}

function normalizeBilingualText(value) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
        return {
            de: String(value.de ?? ""),
            en: String(value.en ?? ""),
        };
    }
    if (typeof value === "string") {
        return { de: value, en: value };
    }
    return { de: "", en: "" };
}

function normalizeTickerItem(value, index = 0) {
    const item = value && typeof value === "object" && !Array.isArray(value) ? value : {};
    const fallbackId = `ticker-${index + 1}`;
    const id = String(item.id || fallbackId).trim() || fallbackId;
    return {
        id,
        text: normalizeBilingualText(item.text),
        timestamp: String(item.timestamp || "").trim(),
    };
}

function hasTickerItemPayloadContent(item) {
    if (String(item?.timestamp || "").trim()) return true;
    const text = item?.text;
    if (!text || typeof text !== "object" || Array.isArray(text)) return false;
    return Boolean(String(text.de || "").trim() || String(text.en || "").trim());
}

function normalizeSectionCtaButtonsForBackend(value) {
    if (!Array.isArray(value)) return [];
    return value.map((entry) => {
        const item = entry && typeof entry === "object" ? entry : {};
        return {
            text: normalizeBilingualText(item.text),
            url: String(item.url || ""),
            button_type: item.buttonType == null ? null : String(item.buttonType),
        };
    });
}

function normalizeSectionCtaButtonsForFrontend(value) {
    if (!Array.isArray(value)) return [];
    return value.map((entry) => {
        const item = entry && typeof entry === "object" ? entry : {};
        return {
            text: normalizeBilingualText(item.text),
            url: String(item.url || ""),
            buttonType: item.button_type == null ? null : String(item.button_type),
        };
    });
}

function normalizeProgramTileOverridesForBackend(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
    const normalized = {};
    for (const [tileIdRaw, overrideRaw] of Object.entries(value)) {
        const tileId = String(tileIdRaw || "").trim();
        if (!tileId || !overrideRaw || typeof overrideRaw !== "object" || Array.isArray(overrideRaw)) continue;
        normalized[tileId] = convertKeysToSnake(overrideRaw);
    }
    return normalized;
}

function normalizeProgramTileOverridesForFrontend(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
    const normalized = {};
    for (const [tileIdRaw, overrideRaw] of Object.entries(value)) {
        const tileId = String(tileIdRaw || "").trim();
        if (!tileId || !overrideRaw || typeof overrideRaw !== "object" || Array.isArray(overrideRaw)) continue;
        normalized[tileId] = convertKeysToCamel(overrideRaw);
    }
    return normalized;
}

function normalizeSectionDesignOverridesForFrontend(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
    return convertKeysToCamelPreserveUnderscorePrefix(value);
}

function normalizeSectionDesignOverridesForBackend(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
    return convertKeysToSnake(value);
}

function normalizeValueForBackend(value) {
    if (Array.isArray(value)) return convertKeysToSnake(value);
    if (value !== null && typeof value === 'object') return convertKeysToSnake(value);
    return value;
}

function normalizeFrontendResponsiveImageFields(value, options = {}) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return value;
    const source = { ...value };
    const media = resolveFrontendResponsiveImagePayload(source, {
        urlKeys: Array.isArray(options.urlKeys) && options.urlKeys.length
            ? options.urlKeys
            : ["imageUrl", "url", "src", "href"],
        variantKeys: Array.isArray(options.variantKeys) && options.variantKeys.length
            ? options.variantKeys
            : ["responsiveVariants", "imageResponsiveVariants", "variants", "imageVariants"],
    });

    source.imageUrl = String(media.url || "").trim();
    source.responsiveVariants = media.responsiveVariants;
    return source;
}

// Section type configuration for special field handling
// Fields not listed here will be auto-converted using snake_case <-> camelCase
const SECTION_TYPE_CONFIG = {
    faq: {
        // Rename mappings: frontendKey -> backendKey
        renames: { faqItems: 'faqs' },
        // Array fields with nested item transformations
        arrays: {
            faqItems: {
                backendKey: 'faqs',
                toBackend: item => ({
                    id: item.id,
                    question: item.q,
                    answer: item.a,
                    tag: item.tag || { de: '', en: '' },
                    start_date: item.startDate || '',
                    end_date: item.endDate || '',
                }),
                toFrontend: item => ({
                    id: item.id,
                    q: item.question || { de: '', en: '' },
                    a: item.answer || { de: '', en: '' },
                    tag: item.tag || { de: '', en: '' },
                    startDate: item.start_date || '',
                    endDate: item.end_date || '',
                })
            }
        },
        // Default values for loading (when field is missing/null)
        defaults: { borderWidth: 1, borderRadius: 14 },
        // Side effects on load
        onLoad: (data) => {
            if (
                !state.faqSharedLoaded
                && Array.isArray(data.faqItems)
                && data.faqItems.length > 0
                && (!Array.isArray(state.faqItems) || state.faqItems.length === 0)
            ) {
                state.faqItems = data.faqItems;
            }
        }
    },
    links: {
        arrays: {
            items: {
                backendKey: 'items',
                toBackend: item => convertKeysToSnake(
                    normalizeFrontendResponsiveImageFields(item, {
                        urlKeys: ["imageUrl", "logoUrl", "thumbnailUrl"],
                    })
                ),
                toFrontend: item => normalizeFrontendResponsiveImageFields(
                    convertKeysToCamel(item),
                    {
                        urlKeys: ["imageUrl", "logoUrl", "thumbnailUrl"],
                    }
                )
            }
        },
        defaults: {
            hideItemTitle: false,
            alignment: 'center',
            itemMaxHeight: 100,
            nonSocialItemMaxWidth: 0,
            itemSpacing: 16,
            socialMode: false,
            hideIconsWithoutLinks: false,
            iconColor: null,
            iconColorLink: null,
        },
    },
    tiles: {
        arrays: {
            tiles: {
                backendKey: 'tiles',
                toBackend: item => convertKeysToSnake(
                    normalizeFrontendResponsiveImageFields(item)
                ),
                toFrontend: item => {
                    const converted = normalizeFrontendResponsiveImageFields(
                        convertKeysToCamel(item)
                    );
                    return {
                        ...converted,
                        zoom: Number.isFinite(Number(converted.zoom)) ? Math.max(1, Math.min(4, Number(converted.zoom))) : 1,
                        focalX: Number.isFinite(Number(converted.focalX)) ? Math.max(0, Math.min(100, Number(converted.focalX))) : 50,
                        focalY: Number.isFinite(Number(converted.focalY)) ? Math.max(0, Math.min(100, Number(converted.focalY))) : 50,
                        rotation: Number.isFinite(Number(converted.rotation)) ? Math.max(-180, Math.min(180, Number(converted.rotation))) : 0,
                    };
                }
            },
            filters: {
                backendKey: 'filters',
                toBackend: item => convertKeysToSnake(item),
                toFrontend: item => convertKeysToCamel(item),
            }
        },
        defaults: {
            gridMode: 'auto',
            rows: 2,
            columns: 3,
            tileMinWidth: 220,
            tileMaxWidth: 360,
            aspectRatio: '1:1',
            direction: 'landscape',
            parentRoute: '',
            alwaysShowTitle: false,
            tileShowResetButton: false,
            tileTopInfoAlign: 'right',
            tileBottomInfoAlign: 'left',
            tileSortMode: 'title',
            useProgramGigs: true,
            filters: [],
            filterControlStyle: 'dropdowns',
            filterControlOrder: [],
            programTileOrder: [],
            programTileOverrides: {},
        }
    },
    gallery: {
        arrays: {
            images: {
                backendKey: 'images',
                toBackend: item => convertKeysToSnake(
                    normalizeFrontendResponsiveImageFields(item)
                ),
                toFrontend: item => {
                    const converted = normalizeFrontendResponsiveImageFields(
                        convertKeysToCamel(item)
                    );
                    return {
                        ...converted,
                        zoom: Number.isFinite(Number(converted.zoom)) ? Math.max(1, Math.min(4, Number(converted.zoom))) : 1,
                        focalX: Number.isFinite(Number(converted.focalX)) ? Math.max(0, Math.min(100, Number(converted.focalX))) : 50,
                        focalY: Number.isFinite(Number(converted.focalY)) ? Math.max(0, Math.min(100, Number(converted.focalY))) : 50,
                        rotation: Number.isFinite(Number(converted.rotation)) ? Math.max(-180, Math.min(180, Number(converted.rotation))) : 0,
                    };
                }
            }
        },
        defaults: { layout: 'grid', aspectRatio: '4:3', orientation: 'landscape', direction: 'landscape', showCaptions: true }
    },
    ticker: {
        arrays: {
            items: {
                backendKey: 'items',
                toBackend: (item, index) => normalizeTickerItem(item, index),
                toFrontend: (item, index) => normalizeTickerItem(item, index)
            }
        },
        defaults: { viewMode: 'ticker', items: [] },
        onLoad: (data) => {
            const viewMode = data.viewMode === "updates" ? "updates" : "ticker";
            const items = Array.isArray(data.items)
                ? data.items.map((item, index) => normalizeTickerItem(item, index))
                : [];
            const legacyUpdateItems = Array.isArray(data.updateItems)
                ? data.updateItems.map((item, index) => normalizeTickerItem(item, index))
                : [];
            const itemsHaveContent = items.some(hasTickerItemPayloadContent);
            const legacyItemsHaveContent = legacyUpdateItems.some(hasTickerItemPayloadContent);

            data.viewMode = viewMode;
            if (viewMode === "updates" && legacyItemsHaveContent) {
                data.items = legacyUpdateItems;
            } else if (itemsHaveContent || items.length > 0) {
                data.items = items;
            } else {
                data.items = legacyUpdateItems;
            }
            delete data.updateItems;
        },
    },
    video: {
        defaults: { wrapper: 'tv' }
    },
    text_image: {
        defaults: {
            imageLayout: 'left',
            imageLayoutResponsive: {},
            imageAlignX: 'center',
            imageMaxWidthPercent: 30,
            imageMaxWidthPercentResponsive: {},
            imageMaxHeightVh: 70,
            imageMaxHeightVhResponsive: {},
            imageWidthPx: 0,
            imageMinWidthPx: 0,
            imageTargetWidthPercent: 100,
            imageMaxWidthPx: 0,
            imageHeightPx: 0,
            imageTextGap: 20,
            imageTextGapResponsive: {},
            imageBorderRadius: 5,
            imageBorderRadiusResponsive: {},
            imageBgOpacity: 0.72,
            imageAspectRatio: '16:9',
            imageAspectRatioResponsive: {},
            imageInteraction: 'zoom',
            imageClickUrl: '',
            imageBgZoom: 1,
            imageBgFocalX: 50,
            imageBgFocalY: 50,
            imageBgRotation: 0,
        },
        onLoad: (data, td) => {
            const rawInteraction = String(td?.image_interaction || '').trim();
            data.imageInteraction = ['none', 'link', 'zoom'].includes(rawInteraction)
                ? rawInteraction
                : (String(data.imageClickUrl || '').trim() ? 'link' : 'zoom');
            const hasClampWidth = td?.image_min_width_px !== undefined
                || td?.image_target_width_percent !== undefined
                || td?.image_max_width_px !== undefined;
            if (!hasClampWidth && Number(data.imageWidthPx) > 0) {
                data.imageMaxWidthPx = Math.max(0, Math.min(2000, Math.round(Number(data.imageWidthPx))));
            }
        }
    },
    blog: {
        defaults: { access: 'public' }
    },
    markdown: {
        // Pass type_data directly without conversion
        passthrough: true
    },
    html: {
        // Pass type_data directly without conversion
        passthrough: true
    },
    program: {
        arrays: {
            gigs: {
                backendKey: 'gigs',
                toBackend: item => item,
                toFrontend: item => item
            }
        },
        defaults: {
            timeSlotMinutes: 15,
            showGenre: true,
            showDescription: false,
            defaultGrouping: 'day',
            fixedStageId: '',
            fixedDay: '',
            fixedGigId: '',
            stageParentRoute: '',
            artistParentRoute: '',
            stageItemPageTemplatePath: '',
            artistItemPageTemplatePath: '',
            allowGroupToggle: true,
            allowDaySelection: true,
            allowStageFilter: true,
            showViewToggle: true,
            showGigDescriptionButton: false,
            defaultViewMode: 'gantt',
            dayStartHour: 10,
            dayEndHour: 6,
            maxVisibleHours: 6,
            dateSelectionColor: null,
            dateSelectionColorLink: null,
            stageRowHeight: 120,
        }
    }
};

// Fields to exclude from auto-conversion (handled specially or not part of type_data).
const EXCLUDED_FROM_TYPE_DATA = [
    'title',
    'sectionType',
    'sectionIntegrationMapping',
    'sectionOutputMapping',
    'icon',
    'blocks',
    'stages',
    'programStagesIntegrationMapping',
    'program_stages_integration_mapping',
    'programStagesIntegrationMappingCacheState',
    'program_stages_integration_mapping_cache_state',
    'programGigsIntegrationMapping',
    'program_gigs_integration_mapping',
    'programGigsIntegrationMappingCacheState',
    'program_gigs_integration_mapping_cache_state',
];

// -------------------------
// Section saving
// -------------------------

const saveSectionTimers = {};
const saveSectionGenerations = {};
const sectionSaveStatusTimers = {};
const pendingSectionRevisionKinds = {};
const SAVE_DEBOUNCE_MS = 500;

function normalizeRevisionKind(kind) {
    if (kind === 'design' || kind === 'content' || kind === 'both') return kind;
    return 'content';
}

function mergeRevisionKind(existingKind, nextKind) {
    const existing = normalizeRevisionKind(existingKind);
    const next = normalizeRevisionKind(nextKind);
    if (existing === next) return existing;
    // Keep revision streams scoped: latest intent wins instead of mixed entries.
    return next;
}

const CONTENT_PRIORITY_KEYS = new Set([
    'title',
    'body',
    'ctaButtons',
    'titlePlaceholder',
    'title_placeholder',
    'adminNotes',
    'adminTodos',
]);

function inferRevisionKind(sectionKey, patch, options = {}) {
    const requestedKind = typeof options === 'string' ? options : options?.revisionKind;
    if (requestedKind) return normalizeRevisionKind(requestedKind);

    const patchKeys = patch && typeof patch === 'object' ? Object.keys(patch) : [];
    if (patchKeys.some((key) => CONTENT_PRIORITY_KEYS.has(key))) return 'content';

    const activeTab = state.sectionAdminActiveTabs?.[sectionKey];
    if (activeTab === 'design') return 'design';
    if (activeTab === 'content') return 'content';
    return 'content';
}

function transformToBackendFormat(key, sectionData) {
    const backendData = {};
    
    // Extract base key for keys like "text_123abc" -> "text"
    const baseKey = key.includes('_') ? key.split('_')[0] : key;
    const sectionType = sectionData.sectionType || baseKey;
    const config = SECTION_TYPE_CONFIG[sectionType] || SECTION_TYPE_CONFIG[baseKey] || {};
    
    // Handle title separately (not part of type_data)
    if (sectionData.title !== undefined) {
        backendData.title = sectionData.title;
    }
    if (sectionData.sectionIntegrationMapping !== undefined) {
        backendData.section_integration_mapping = normalizeValueForBackend(
            sectionData.sectionIntegrationMapping
        );
    }
    if (sectionData.sectionOutputMapping !== undefined) {
        backendData.section_output_mapping = normalizeValueForBackend(
            sectionData.sectionOutputMapping
        );
    }
    
    // For markdown/passthrough sections, keep type_data mostly untouched
    // but strip description fields and persist shared admin metadata.
    if (config.passthrough) {
        const passthroughTypeData = { ...(sectionData.type_data || {}) };
        delete passthroughTypeData.body;
        delete passthroughTypeData.description;
        delete passthroughTypeData.icon;
        delete passthroughTypeData.blocks;
        if (sectionData.ctaButtons !== undefined) {
            passthroughTypeData.cta_buttons = normalizeSectionCtaButtonsForBackend(sectionData.ctaButtons);
        } else if (Array.isArray(passthroughTypeData.cta_buttons)) {
            passthroughTypeData.cta_buttons = normalizeSectionCtaButtonsForBackend(
                normalizeSectionCtaButtonsForFrontend(passthroughTypeData.cta_buttons)
            );
        }
        if (sectionData.sectionGeneric !== undefined) {
            passthroughTypeData.section_generic = normalizeSectionGenericForBackend(sectionData.sectionGeneric);
        } else if (passthroughTypeData.section_generic && typeof passthroughTypeData.section_generic === "object") {
            passthroughTypeData.section_generic = normalizeSectionGenericForBackend(passthroughTypeData.section_generic);
        }
        if (sectionData.adminNotes !== undefined) {
            passthroughTypeData.admin_notes = sectionData.adminNotes;
        }
        if (sectionData.adminTodos !== undefined) {
            passthroughTypeData.admin_todos = sectionData.adminTodos;
        }
        backendData.type_data = passthroughTypeData;
        return backendData;
    }
    
    const typeData = {};
    const arrayConfigs = config.arrays || {};
    const renames = config.renames || {};
    
    // Process each field in sectionData
    for (const [frontendKey, value] of Object.entries(sectionData)) {
        if (value === undefined) continue;
        if (
            sectionType === 'blog'
            && (
                frontendKey === 'items'
                || frontendKey === 'tags'
                || frontendKey === 'blogItems'
                || frontendKey === 'blogTags'
            )
        ) continue;
        if (
            sectionType === 'faq'
            && (
                frontendKey === 'faqItems'
                || frontendKey === 'faqTags'
                || frontendKey === 'scope'
            )
        ) continue;
        if (sectionType === 'ticker' && frontendKey === 'updateItems') continue;
        if (EXCLUDED_FROM_TYPE_DATA.includes(frontendKey)) continue;
        
        // Check if this field has a custom array transformation
        if (arrayConfigs[frontendKey] && Array.isArray(value)) {
            const arrConfig = arrayConfigs[frontendKey];
            typeData[arrConfig.backendKey] = value.map(arrConfig.toBackend);
            continue;
        }
        
        // Check for simple rename (without transformation)
        if (renames[frontendKey]) {
            typeData[renames[frontendKey]] = normalizeValueForBackend(value);
            continue;
        }
        
        // Skip array fields that are renames but not in arrayConfigs (already handled above)
        if (Object.values(renames).includes(frontendKey)) continue;

        if (frontendKey === "sectionGeneric") {
            typeData.section_generic = normalizeSectionGenericForBackend(value);
            continue;
        }
        if (frontendKey === "ctaButtons") {
            typeData.cta_buttons = normalizeSectionCtaButtonsForBackend(value);
            continue;
        }
        if (frontendKey === "programTileOverrides") {
            typeData.program_tile_overrides = normalizeProgramTileOverridesForBackend(value);
            continue;
        }
        
        // Default: auto-convert key to snake_case
        const backendKey = toSnakeCase(frontendKey);
        typeData[backendKey] = normalizeValueForBackend(value);
    }
    
    if (Object.keys(typeData).length > 0) {
        backendData.type_data = typeData;
    }
    
    logDebug("transformToBackendFormat", { key, sectionType, typeDataKeys: Object.keys(typeData) });
    return backendData;
}

async function saveSection(sectionId, data) {
    logDebug("saveSection.start", { sectionId });
    try {
        await api.updateSection(sectionId, data);
        logDebug("saveSection.success", { sectionId });
        return true;
    } catch (err) {
        logDebug("saveSection.error", { sectionId, error: err.message });
        console.error(`Failed to save section ${sectionId}:`, err);
        return false;
    }
}

function clearSectionSaveStatusTimer(key) {
    if (sectionSaveStatusTimers[key]) {
        clearTimeout(sectionSaveStatusTimers[key]);
        delete sectionSaveStatusTimers[key];
    }
}

function setSectionSaveStatus(key, status, error = "") {
    if (!key) return;
    clearSectionSaveStatusTimer(key);
    state.sectionSaveStatus[key] = { status, error };
}

function markSectionSaveSaved(key) {
    if (!key) return;
    setSectionSaveStatus(key, "saved");
    sectionSaveStatusTimers[key] = setTimeout(() => {
        if (state.sectionSaveStatus?.[key]?.status === "saved") {
            delete state.sectionSaveStatus[key];
        }
        delete sectionSaveStatusTimers[key];
    }, 3000);
}

function markSectionSaveError(key, error = "Failed to save section.") {
    if (!key) return;
    setSectionSaveStatus(key, "error", error);
    sectionSaveStatusTimers[key] = setTimeout(() => {
        if (state.sectionSaveStatus?.[key]?.status === "error") {
            delete state.sectionSaveStatus[key];
        }
        delete sectionSaveStatusTimers[key];
    }, 3000);
}

async function saveSectionByKey(key, { revisionKind = null, revertedFromSavedAt = null } = {}) {
    const sectionId = state.sectionIds?.[key];
    if (!sectionId) return false;

    // Prevent stale debounced writes from overriding an explicit revision restore/save.
    saveSectionGenerations[key] = (saveSectionGenerations[key] || 0) + 1;
    if (saveSectionTimers[key]) {
        clearTimeout(saveSectionTimers[key]);
        delete saveSectionTimers[key];
    }
    delete pendingSectionRevisionKinds[key];

    const sectionData = state.sectionsData?.[key];
    if (!sectionData) return false;

    const backendData = transformToBackendFormat(key, sectionData);
    if (revisionKind) {
        backendData.revision_change_kind = normalizeRevisionKind(revisionKind);
    }
    if (revertedFromSavedAt) {
        backendData.revision_reverted_from_saved_at = String(revertedFromSavedAt);
    }

    setSectionSaveStatus(key, "saving");
    const saved = await saveSection(sectionId, backendData);
    if (saved) {
        markSectionSaveSaved(key);
        refreshRevisionStatus(key);
    } else {
        markSectionSaveError(key);
    }
    return saved;
}

function debouncedSaveSection(key) {
    const sectionId = state.sectionIds?.[key];
    if (!sectionId) {
        logDebug("debouncedSaveSection.noId", { key });
        return;
    }
    
    if (saveSectionTimers[key]) {
        clearTimeout(saveSectionTimers[key]);
    }
    
    const generation = (saveSectionGenerations[key] || 0) + 1;
    saveSectionGenerations[key] = generation;
    setSectionSaveStatus(key, "queued");

    saveSectionTimers[key] = setTimeout(async () => {
        if (saveSectionGenerations[key] !== generation) return;
        const sectionData = state.sectionsData?.[key];
        if (!sectionData) {
            logDebug("debouncedSaveSection.noData", { key });
            return;
        }
        
        const backendData = transformToBackendFormat(key, sectionData);
        const revisionKind = pendingSectionRevisionKinds[key];
        if (revisionKind) backendData.revision_change_kind = revisionKind;
        setSectionSaveStatus(key, "saving");
        const saved = await saveSection(sectionId, backendData);
        if (saved) {
            console.info("[FstvlPress Save] Section changes persisted", {
                sectionKey: key,
                sectionId,
                revisionKind: revisionKind || "content",
                changes: backendData,
            });
            markSectionSaveSaved(key);
        } else {
            markSectionSaveError(key);
        }
        delete pendingSectionRevisionKinds[key];
        // Refresh revision status after save
        refreshRevisionStatus(key);
    }, SAVE_DEBOUNCE_MS);
}

async function saveTickerItems() {
    const tickerSectionId = state.sectionIds?.ticker;
    if (!tickerSectionId) {
        logDebug("saveTickerItems.noId");
        return;
    }
    
    logDebug("saveTickerItems.start", { sectionId: tickerSectionId });
    try {
        const payload = {
            type_data: {
                items: state.tickerItems.map(item => ({
                    id: item.id || String(Date.now()),
                    text: item.text || { de: "", en: "" },
                    timestamp: String(item.timestamp || "").trim(),
                }))
            },
            revision_change_kind: "content",
        };
        await api.updateSection(tickerSectionId, payload);
        console.info("[FstvlPress Save] Section changes persisted", {
            sectionKey: "ticker",
            sectionId: tickerSectionId,
            revisionKind: "content",
            changes: payload,
        });
        logDebug("saveTickerItems.success");
    } catch (err) {
        logDebug("saveTickerItems.error", { error: err.message });
        console.error("Failed to save ticker items:", err);
    }
}

function normalizeFaqDate(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : "";
}

function normalizeFaqSharedPayload(payload) {
    const source = payload && typeof payload === 'object' ? payload : {};
    const rawItems = Array.isArray(source.items) ? source.items : [];
    const rawTags = Array.isArray(source.tags) ? source.tags : [];
    return {
        items: rawItems.map((item, index) => {
            const sourceItem = item && typeof item === 'object' ? item : {};
            const normalizedItem = convertKeysToCamel(sourceItem);
            const question = normalizedItem.question ?? normalizedItem.q ?? {};
            const answer = normalizedItem.answer ?? normalizedItem.a ?? {};
            return {
                id: String(sourceItem.id || "").trim() || `faq-${index + 1}`,
                q: {
                    de: String(question?.de || ""),
                    en: String(question?.en || ""),
                },
                a: {
                    de: String(answer?.de || ""),
                    en: String(answer?.en || ""),
                },
                tag: normalizedItem.tag || { de: "", en: "" },
                startDate: normalizeFaqDate(normalizedItem.startDate),
                endDate: normalizeFaqDate(normalizedItem.endDate),
            };
        }),
        tags: rawTags
            .filter((tag) => tag && typeof tag === 'object')
            .map((tag) => ({
                de: String(tag.de || ""),
                en: String(tag.en || ""),
            })),
    };
}

function toFaqSharedBackendItems(items) {
    return (Array.isArray(items) ? items : []).map((item) => {
        const sourceItem = item && typeof item === 'object' ? item : {};
        const normalizedItem = convertKeysToCamel(sourceItem);
        const question = normalizedItem.q ?? normalizedItem.question ?? {};
        const answer = normalizedItem.a ?? normalizedItem.answer ?? {};
        return {
            id: String(sourceItem.id || "").trim(),
            question: {
                de: String(question?.de || ""),
                en: String(question?.en || ""),
            },
            answer: {
                de: String(answer?.de || ""),
                en: String(answer?.en || ""),
            },
            tag: normalizedItem.tag || { de: "", en: "" },
            start_date: normalizeFaqDate(normalizedItem.startDate),
            end_date: normalizeFaqDate(normalizedItem.endDate),
        };
    });
}

function applyFaqSharedData(payload, options = {}) {
    const normalized = normalizeFaqSharedPayload(payload);
    state.faqItems = normalized.items;
    state.faqTags = normalized.tags;
    const source = String(options?.source || "shared").trim() || "shared";
    state.faqSharedSource = source;
    state.faqSharedLoaded = source === "shared" || source === "local";
    logDebug("applyFaqSharedData.success", {
        items: state.faqItems.length,
        tags: state.faqTags.length,
        source,
        loaded: state.faqSharedLoaded,
    });
}

async function fetchFaqSharedData() {
    try {
        const payload = await api.getFaqShared();
        applyFaqSharedData(payload, { source: "shared" });
        return {
            items: state.faqItems,
            tags: state.faqTags,
        };
    } catch (err) {
        logDebug("fetchFaqSharedData.error", { error: err.message });
        console.error("Failed to fetch shared FAQ data:", err);
        state.faqItems = [];
        state.faqTags = [];
        state.faqSharedLoaded = false;
        state.faqSharedSource = "";
        return { items: [], tags: [] };
    }
}

async function saveFaqSharedData(payload) {
    const source = payload && typeof payload === 'object' ? payload : {};
    const hasItems = Object.prototype.hasOwnProperty.call(source, "items");
    const hasTags = Object.prototype.hasOwnProperty.call(source, "tags");
    const normalizedItems = hasItems
        ? normalizeFaqSharedPayload({ items: source.items, tags: [] }).items
        : (Array.isArray(state.faqItems) ? state.faqItems : []);
    const normalizedTags = hasTags
        ? normalizeFaqSharedPayload({ items: [], tags: source.tags }).tags
        : (Array.isArray(state.faqTags) ? state.faqTags : []);

    applyFaqSharedData({
        items: normalizedItems,
        tags: normalizedTags,
    }, { source: "shared" });

    try {
        const result = await api.updateFaqShared({
            items: toFaqSharedBackendItems(normalizedItems),
            tags: normalizedTags,
        });
        applyFaqSharedData(result, { source: "shared" });
        return {
            items: state.faqItems,
            tags: state.faqTags,
        };
    } catch (err) {
        logDebug("saveFaqSharedData.error", { error: err.message });
        console.error("Failed to save shared FAQ data:", err);
        throw err;
    }
}

function mapBlogSharedItem(it) {
    const source = it && typeof it === "object" ? it : {};
    const normalizedSource = convertKeysToCamel(source);
    const media = resolveBackendResponsiveImagePayload(source, {
        urlKeys: ["image_url", "url", "src", "href"],
    });
    const responsiveVariants = media.responsiveVariants;
    return {
        id: String(source.id || ""),
        imageUrl: String(media.url || "").trim(),
        responsiveVariants,
        imageAuthor: String(normalizedSource.imageAuthor || normalizedSource.author || "").trim(),
        imageZoom: Number.isFinite(Number(source.image_zoom))
            ? Math.max(1, Math.min(4, Number(source.image_zoom)))
            : 1,
        imageFocalX: Number.isFinite(Number(source.image_focal_x))
            ? Math.max(0, Math.min(100, Number(source.image_focal_x)))
            : 50,
        imageFocalY: Number.isFinite(Number(source.image_focal_y))
            ? Math.max(0, Math.min(100, Number(source.image_focal_y)))
            : 50,
        imageRotation: Number.isFinite(Number(source.image_rotation))
            ? Math.max(-180, Math.min(180, Number(source.image_rotation)))
            : 0,
        date: String(source.date || "").trim(),
        tag: source.tag || { de: "", en: "" },
        title: source.title || { de: "", en: "" },
        text: source.text || { de: "", en: "" },
        pageSlug: String(source.page_slug || "").trim(),
        itemPageTemplateOutdated: Boolean(source.item_page_template_outdated),
    };
}

async function fetchBlogData() {
    try {
        const [itemsRes, configRes] = await Promise.all([
            api.listBlogItems(),
            api.getBlogConfig()
        ]);
        state.blogItems = (itemsRes.items || []).map((it) => mapBlogSharedItem(it));
        state.blogTags = configRes.tags || [];
        logDebug("fetchBlogData.success", { count: state.blogItems.length });
    } catch (err) {
        logDebug("fetchBlogData.error", { error: err.message });
        console.error("Failed to fetch blog data:", err);
        state.blogItems = [];
        state.blogTags = [];
    }
}

function normalizeProgramSharedPayload(payload) {
    const source = payload && typeof payload === 'object' ? payload : {};
    const rawGigs = Array.isArray(source.gigs) ? source.gigs : [];
    const rawStages = Array.isArray(source.stages) ? source.stages : [];
    const rawStageMapping = source.programStagesIntegrationMapping
        ?? source.program_stages_integration_mapping
        ?? {};
    const rawStageCacheState = source.programStagesIntegrationMappingCacheState
        ?? source.program_stages_integration_mapping_cache_state
        ?? {};
    const rawGigMapping = source.programGigsIntegrationMapping
        ?? source.program_gigs_integration_mapping
        ?? {};
    const rawGigCacheState = source.programGigsIntegrationMappingCacheState
        ?? source.program_gigs_integration_mapping_cache_state
        ?? {};
    const rawScope = String(source.scope || source.program_scope || "").trim().toLowerCase();
    return {
        gigs: rawGigs.map((gig) => ({ ...gig })),
        gigIds: Array.isArray(source.gig_ids)
            ? source.gig_ids.map((id) => String(id || "").trim()).filter(Boolean)
            : rawGigs.map((gig) => String(gig?.id || "").trim()).filter(Boolean),
        stages: rawStages.map((stage) => ({ ...stage })),
        programStagesIntegrationMapping: rawStageMapping && typeof rawStageMapping === "object"
            ? rawStageMapping
            : {},
        programStagesIntegrationMappingCacheState: rawStageCacheState && typeof rawStageCacheState === "object"
            ? rawStageCacheState
            : {},
        programGigsIntegrationMapping: rawGigMapping && typeof rawGigMapping === "object"
            ? rawGigMapping
            : {},
        programGigsIntegrationMappingCacheState: rawGigCacheState && typeof rawGigCacheState === "object"
            ? rawGigCacheState
            : {},
        scope: rawScope === "partial" ? "partial" : rawScope === "none" ? "none" : "full",
    };
}

const PROGRAM_SHARED_VOLATILE_ITEM_KEYS = new Set([
    "item_page_template_outdated",
    "item_page_missing",
    "item_page_mapped_fields_synced",
    "day",
    "start_time",
    "end_time",
    "previous_day",
    "previous_start_time",
    "previous_end_time",
    "__source",
    "__base",
    "__change",
    "__canceled",
    "__changed",
]);

function stripProgramSharedVolatileItemFields(row) {
    if (!row || typeof row !== "object" || Array.isArray(row)) return row;
    const next = {};
    Object.entries(row).forEach(([key, value]) => {
        if (PROGRAM_SHARED_VOLATILE_ITEM_KEYS.has(key)) return;
        next[key] = value;
    });
    return next;
}

function normalizeProgramSharedSavePayload(payload, {
    includeGigs = true,
    includeStages = true,
    includeStageMapping = false,
    includeStageCacheState = false,
    includeGigMapping = false,
    includeGigCacheState = false,
} = {}) {
    const normalized = normalizeProgramSharedPayload(payload);
    const result = {};
    if (includeGigs) {
        result.gigs = normalized.gigs.map((gig) => stripProgramSharedVolatileItemFields(gig));
    }
    if (includeStages) {
        result.stages = normalized.stages.map((stage) => stripProgramSharedVolatileItemFields(stage));
    }
    if (includeStageMapping) {
        result.program_stages_integration_mapping = cloneProgramSharedMetadata(
            normalized.programStagesIntegrationMapping
        );
    }
    if (includeStageCacheState) {
        result.program_stages_integration_mapping_cache_state = cloneProgramSharedMetadata(
            normalized.programStagesIntegrationMappingCacheState
        );
    }
    if (includeGigMapping) {
        result.program_gigs_integration_mapping = cloneProgramSharedMetadata(
            normalized.programGigsIntegrationMapping
        );
    }
    if (includeGigCacheState) {
        result.program_gigs_integration_mapping_cache_state = cloneProgramSharedMetadata(
            normalized.programGigsIntegrationMappingCacheState
        );
    }
    return result;
}

function normalizeStableProgramSharedValue(value) {
    if (Array.isArray(value)) {
        return value.map((entry) => normalizeStableProgramSharedValue(entry));
    }
    if (!value || typeof value !== "object") {
        return value;
    }
    return Object.keys(value)
        .sort()
        .reduce((result, key) => {
            result[key] = normalizeStableProgramSharedValue(value[key]);
            return result;
        }, {});
}

function stableProgramSharedString(value) {
    try {
        return JSON.stringify(normalizeStableProgramSharedValue(value));
    } catch {
        return "";
    }
}

function cloneProgramSharedMetadata(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    try {
        return JSON.parse(JSON.stringify(value));
    } catch {
        return { ...value };
    }
}

function hasProgramSharedPayloadKey(source, ...keys) {
    if (!source || typeof source !== "object") return false;
    return keys.some((key) => Object.prototype.hasOwnProperty.call(source, key));
}

function applyProgramSharedData(payload, options = {}) {
    const normalized = normalizeProgramSharedPayload(payload);
    state.programSharedGigs = normalized.gigs;
    state.programSharedStages = normalized.stages;
    state.programSharedStagesIntegrationMapping = normalized.programStagesIntegrationMapping;
    state.programSharedStagesIntegrationMappingCacheState = normalized.programStagesIntegrationMappingCacheState;
    state.programSharedGigsIntegrationMapping = normalized.programGigsIntegrationMapping;
    state.programSharedGigsIntegrationMappingCacheState = normalized.programGigsIntegrationMappingCacheState;
    state.programSharedLoaded = true;
    const requestedScope = String(options.scope || "").trim().toLowerCase();
    state.programSharedScope = requestedScope === "partial"
        ? "partial"
        : requestedScope === "none"
            ? "none"
            : normalized.scope;
    logDebug("applyProgramSharedData.success", {
        gigs: state.programSharedGigs.length,
        stages: state.programSharedStages.length,
        scope: state.programSharedScope,
    });
}

async function fetchProgramSharedData() {
    try {
        const payload = await api.getProgramShared();
        applyProgramSharedData(payload, { scope: "full" });
        const itemPageGenerationJobs = Array.isArray(payload?.item_page_generation_jobs)
            ? payload.item_page_generation_jobs
            : [];
        return {
            gigs: state.programSharedGigs,
            stages: state.programSharedStages,
            programStagesIntegrationMapping: state.programSharedStagesIntegrationMapping,
            programStagesIntegrationMappingCacheState: state.programSharedStagesIntegrationMappingCacheState,
            programGigsIntegrationMapping: state.programSharedGigsIntegrationMapping,
            programGigsIntegrationMappingCacheState: state.programSharedGigsIntegrationMappingCacheState,
            itemPageGenerationJobs,
        };
    } catch (err) {
        logDebug("fetchProgramSharedData.error", { error: err.message });
        console.error("Failed to fetch shared program data:", err);
        state.programSharedGigs = [];
        state.programSharedStages = [];
        state.programSharedStagesIntegrationMapping = {};
        state.programSharedStagesIntegrationMappingCacheState = {};
        state.programSharedGigsIntegrationMapping = {};
        state.programSharedGigsIntegrationMappingCacheState = {};
        state.programSharedLoaded = false;
        state.programSharedScope = "none";
        return {
            gigs: [],
            stages: [],
            programStagesIntegrationMapping: {},
            programStagesIntegrationMappingCacheState: {},
            programGigsIntegrationMapping: {},
            programGigsIntegrationMappingCacheState: {},
            itemPageGenerationJobs: [],
        };
    }
}

async function saveProgramSharedData(payload) {
    if (state.programSharedLoaded && state.programSharedScope !== "full") {
        await fetchProgramSharedData();
    }
    const source = payload && typeof payload === "object" ? payload : {};
    const normalized = normalizeProgramSharedPayload(payload);
    const hasGigsPayload = hasProgramSharedPayloadKey(source, "gigs");
    const hasStagesPayload = hasProgramSharedPayloadKey(source, "stages");
    if ((!hasGigsPayload || !hasStagesPayload) && !state.programSharedLoaded) {
        await fetchProgramSharedData();
    }
    const hasStageMappingPayload = hasProgramSharedPayloadKey(
        source,
        "programStagesIntegrationMapping",
        "program_stages_integration_mapping",
    );
    const hasStageCacheStatePayload = hasProgramSharedPayloadKey(
        source,
        "programStagesIntegrationMappingCacheState",
        "program_stages_integration_mapping_cache_state",
    );
    const hasGigMappingPayload = hasProgramSharedPayloadKey(
        source,
        "programGigsIntegrationMapping",
        "program_gigs_integration_mapping",
    );
    const hasGigCacheStatePayload = hasProgramSharedPayloadKey(
        source,
        "programGigsIntegrationMappingCacheState",
        "program_gigs_integration_mapping_cache_state",
    );
    const payloadForSave = {
        ...normalized,
        gigs: hasGigsPayload
            ? normalized.gigs
            : state.programSharedGigs.map((gig) => ({ ...gig })),
        stages: hasStagesPayload
            ? normalized.stages
            : state.programSharedStages.map((stage) => ({ ...stage })),
        programStagesIntegrationMapping: hasStageMappingPayload
            ? normalized.programStagesIntegrationMapping
            : cloneProgramSharedMetadata(state.programSharedStagesIntegrationMapping),
        programStagesIntegrationMappingCacheState: hasStageCacheStatePayload
            ? normalized.programStagesIntegrationMappingCacheState
            : cloneProgramSharedMetadata(state.programSharedStagesIntegrationMappingCacheState),
        programGigsIntegrationMapping: hasGigMappingPayload
            ? normalized.programGigsIntegrationMapping
            : cloneProgramSharedMetadata(state.programSharedGigsIntegrationMapping),
        programGigsIntegrationMappingCacheState: hasGigCacheStatePayload
            ? normalized.programGigsIntegrationMappingCacheState
            : cloneProgramSharedMetadata(state.programSharedGigsIntegrationMappingCacheState),
    };
    const requestPayload = normalizeProgramSharedSavePayload(payloadForSave, {
        includeGigs: hasGigsPayload,
        includeStages: hasStagesPayload,
        includeStageMapping: hasStageMappingPayload,
        includeStageCacheState: hasStageCacheStatePayload,
        includeGigMapping: hasGigMappingPayload,
        includeGigCacheState: hasGigCacheStatePayload,
    });
    if (state.programSharedLoaded) {
        const currentComparablePayload = normalizeProgramSharedSavePayload(
            {
                gigs: state.programSharedGigs,
                stages: state.programSharedStages,
                programStagesIntegrationMapping: state.programSharedStagesIntegrationMapping,
                programStagesIntegrationMappingCacheState: state.programSharedStagesIntegrationMappingCacheState,
                programGigsIntegrationMapping: state.programSharedGigsIntegrationMapping,
                programGigsIntegrationMappingCacheState: state.programSharedGigsIntegrationMappingCacheState,
            },
            {
                includeGigs: hasGigsPayload,
                includeStages: hasStagesPayload,
                includeStageMapping: hasStageMappingPayload,
                includeStageCacheState: hasStageCacheStatePayload,
                includeGigMapping: hasGigMappingPayload,
                includeGigCacheState: hasGigCacheStatePayload,
            },
        );
        if (
            stableProgramSharedString(requestPayload)
            === stableProgramSharedString(currentComparablePayload)
        ) {
            logDebug("saveProgramSharedData.skipped_no_changes", {
                gigs: state.programSharedGigs.length,
                stages: state.programSharedStages.length,
                sentMapping: hasGigMappingPayload,
                sentCacheState: hasGigCacheStatePayload,
            });
            return {
                gigs: state.programSharedGigs,
                stages: state.programSharedStages,
                programStagesIntegrationMapping: state.programSharedStagesIntegrationMapping,
                programStagesIntegrationMappingCacheState: state.programSharedStagesIntegrationMappingCacheState,
                programGigsIntegrationMapping: state.programSharedGigsIntegrationMapping,
                programGigsIntegrationMappingCacheState: state.programSharedGigsIntegrationMappingCacheState,
                itemPageGenerationJobs: [],
            };
        }
    }
    // Optimistic local update so all Program sections stay in sync immediately.
    applyProgramSharedData(payloadForSave);
    try {
        const result = await api.updateProgramShared(requestPayload);
        applyProgramSharedData(result);
        const itemPageGenerationJobs = Array.isArray(result?.item_page_generation_jobs)
            ? result.item_page_generation_jobs
            : [];
        return {
            gigs: state.programSharedGigs,
            stages: state.programSharedStages,
            programStagesIntegrationMapping: state.programSharedStagesIntegrationMapping,
            programStagesIntegrationMappingCacheState: state.programSharedStagesIntegrationMappingCacheState,
            programGigsIntegrationMapping: state.programSharedGigsIntegrationMapping,
            programGigsIntegrationMappingCacheState: state.programSharedGigsIntegrationMappingCacheState,
            itemPageGenerationJobs,
        };
    } catch (err) {
        logDebug("saveProgramSharedData.error", { error: err.message });
        console.error("Failed to save shared program data:", err);
        throw err;
    }
}

async function saveProgramSharedGig(gig) {
    const requestPayload = normalizeProgramSharedSavePayload({
        gigs: [gig],
        stages: [],
    });
    const normalizedGig = requestPayload.gigs[0];
    const normalizedGigId = String(normalizedGig?.id || "").trim();
    if (!normalizedGigId) {
        throw new Error("Missing program gig ID");
    }

    const currentIndex = Array.isArray(state.programSharedGigs)
        ? state.programSharedGigs.findIndex(
            (entry) => String(entry?.id || "").trim() === normalizedGigId
        )
        : -1;
    if (state.programSharedLoaded && currentIndex >= 0) {
        const currentComparablePayload = normalizeProgramSharedSavePayload({
            gigs: [state.programSharedGigs[currentIndex]],
            stages: [],
        });
        if (
            stableProgramSharedString(requestPayload)
            === stableProgramSharedString(currentComparablePayload)
        ) {
            logDebug("saveProgramSharedGig.skipped_no_changes", {
                gigId: normalizedGigId,
            });
            return {
                gig: state.programSharedGigs[currentIndex],
                itemPageGenerationJobs: [],
            };
        }
    }

    const applyLocalGig = (gigPayload) => {
        const normalizedPayload = normalizeProgramSharedPayload({
            gigs: [gigPayload],
            stages: [],
        });
        const nextGig = normalizedPayload.gigs[0] || gigPayload;
        const nextGigs = Array.isArray(state.programSharedGigs)
            ? state.programSharedGigs.slice()
            : [];
        const index = nextGigs.findIndex(
            (entry) => String(entry?.id || "").trim() === normalizedGigId
        );
        if (index >= 0) {
            nextGigs[index] = nextGig;
        } else {
            nextGigs.push(nextGig);
        }
        state.programSharedGigs = nextGigs;
        state.programSharedLoaded = true;
        return nextGig;
    };

    applyLocalGig(normalizedGig);
    try {
        const result = await api.updateProgramSharedGig(normalizedGigId, {
            gig: normalizedGig,
        });
        const syncedGig = result?.gig && typeof result.gig === "object"
            ? applyLocalGig(result.gig)
            : normalizedGig;
        const itemPageGenerationJobs = Array.isArray(result?.item_page_generation_jobs)
            ? result.item_page_generation_jobs
            : [];
        return {
            gig: syncedGig,
            itemPageGenerationJobs,
        };
    } catch (err) {
        logDebug("saveProgramSharedGig.error", { gigId: normalizedGigId, error: err.message });
        console.error("Failed to save shared program gig:", err);
        throw err;
    }
}

async function updateSectionVisibility(pageSlug, sectionKey, visible) {
    const sectionId = state.sectionIds?.[sectionKey];
    if (!sectionId) {
        logDebug("updateSectionVisibility.noId", { sectionKey });
        return;
    }
    
    try {
        await api.updatePageSectionRef(pageSlug, sectionId, { visible });
        logDebug("updateSectionVisibility.success", { sectionKey, visible });
    } catch (err) {
        logDebug("updateSectionVisibility.error", { sectionKey, error: err.message });
        console.error(`Failed to update section visibility for ${sectionKey}:`, err);
    }
}

async function updateSectionLimit(pageSlug, sectionKey, limit) {
    const sectionId = state.sectionIds?.[sectionKey];
    if (!sectionId) {
        logDebug("updateSectionLimit.noId", { sectionKey });
        return;
    }
    const numericLimit = Number(limit);
    const normalizedLimit = Number.isInteger(numericLimit) && numericLimit > 0 ? numericLimit : null;
    const limitVal = normalizedLimit ?? 0;
    try {
        await api.updatePageSectionRef(pageSlug, sectionId, { limit: limitVal });
        if (state.sectionsData?.[sectionKey]) {
            state.sectionsData[sectionKey].limit = normalizedLimit;
        }
        logDebug("updateSectionLimit.success", { sectionKey, limit: normalizedLimit });
    } catch (err) {
        logDebug("updateSectionLimit.error", { sectionKey, error: err.message });
        console.error(`Failed to update section limit for ${sectionKey}:`, err);
    }
}

async function updateSectionOrder(pageSlug, order) {
    if (!state.sectionIds || Object.keys(state.sectionIds).length === 0) {
        logDebug("updateSectionOrder.noIds");
        return;
    }
    
    try {
        for (let i = 0; i < order.length; i++) {
            const sectionKey = order[i];
            const sectionId = state.sectionIds[sectionKey];
            if (sectionId) {
                await api.updatePageSectionRef(pageSlug, sectionId, { order: i });
            }
        }
        logDebug("updateSectionOrder.success", { order });
    } catch (err) {
        logDebug("updateSectionOrder.error", { error: err.message });
        console.error("Failed to update section order:", err);
    }
}

async function updateSectionWidth(pageSlug, sectionKey, width) {
    const sectionId = state.sectionIds?.[sectionKey];
    if (!sectionId) {
        logDebug("updateSectionWidth.noId", { sectionKey });
        return;
    }
    
    try {
        await api.updatePageSectionRef(pageSlug, sectionId, { width });
        logDebug("updateSectionWidth.success", { sectionKey, width });
    } catch (err) {
        logDebug("updateSectionWidth.error", { sectionKey, error: err.message });
        console.error(`Failed to update section width for ${sectionKey}:`, err);
    }
}

async function updateSectionDeviceVisibility(pageSlug, sectionKey, deviceVisibility) {
    const sectionId = state.sectionIds?.[sectionKey];
    if (!sectionId) {
        logDebug("updateSectionDeviceVisibility.noId", { sectionKey });
        return;
    }
    
    try {
        await api.updatePageSectionRef(pageSlug, sectionId, { device_visibility: deviceVisibility });
        logDebug("updateSectionDeviceVisibility.success", { sectionKey, deviceVisibility });
    } catch (err) {
        logDebug("updateSectionDeviceVisibility.error", { sectionKey, error: err.message });
        console.error(`Failed to update device visibility for ${sectionKey}:`, err);
    }
}

// -------------------------
// UI translations
// -------------------------

const dict = {
    de: {
        edit: "Bearbeiten",
        save: "Speichern",
        cancel: "Abbrechen",
        add: "Hinzufügen",
        remove: "Entfernen",
        close: "Schließen",
        readMore: "Mehr",
        readLess: "Weniger",
        german: "Deutsch",
        english: "Englisch",
        question: "Frage",
        answer: "Antwort",
        tickerText: "Ticker Text",
        tickets: "Tickets",
        newsletter: "Newsletter",
        ticker: "ticker",
        faq: "FAQ",
        blog: "Blog",
        date: "Datum",
        tag: "Thema",
        title: "Titel",
        text: "Text",
        noImage: "Kein Bild",
        browse: "Auswählen",
        noItems: "Noch keine Einträge.",
        clickToAdd: "Klicken Sie zum Bearbeiten.",
        showMore: "Mehr anzeigen",
        limitLabel: "Anzahl anzeigen",
        limitAll: "Alle",
        displayCount: "Anzeige",
        scope: "Thema",
        allTopics: "Alle",
        otherTopic: "Sonstige",
        access: "Sichtbarkeit",
        scopeConfig: "Thema filterbar",
        public: "Nein (öffentlich)",
        adminOnly: "Ja (nur Admin)",
        sharedItems: "Gemeinsame Einträge",
        selectTag: "Thema wählen",
        loading: "Lädt...",
        saving: "Speichert...",
        error: "Fehler",
        undo: "Rückgängig",
        redo: "Wiederholen"
    },
    en: {
        edit: "Edit",
        save: "Save",
        cancel: "Cancel",
        add: "Add",
        remove: "Remove",
        close: "Close",
        readMore: "Read more",
        readLess: "Less",
        german: "German",
        english: "English",
        question: "Question",
        answer: "Answer",
        tickerText: "Ticker Text",
        tickets: "Tickets",
        newsletter: "Newsletter",
        ticker: "ticker",
        faq: "FAQ",
        blog: "Blog",
        date: "Date",
        tag: "Topic",
        title: "Title",
        text: "Text",
        noImage: "No image",
        browse: "Browse",
        noItems: "No entries yet.",
        clickToAdd: "Click to edit.",
        showMore: "Show more",
        limitLabel: "Display count",
        limitAll: "All",
        displayCount: "Display",
        scope: "Topic",
        allTopics: "All",
        otherTopic: "Other",
        access: "Visibility",
        scopeConfig: "Scope filterable",
        public: "No (public)",
        adminOnly: "Yes (admin only)",
        sharedItems: "Shared items",
        selectTag: "Select topic",
        loading: "Loading...",
        saving: "Saving...",
        error: "Error",
        undo: "Undo",
        redo: "Redo"
    }
};

const t = computed(() => dict[state.lang] || dict.de);

/**
 * Get localized text with fallback to German if current language is empty.
 * @param {Object} obj - Bilingual object with {de, en} properties
 * @returns {string} Localized text or fallback
 */
function localizedText(obj) {
    if (!obj || typeof obj !== "object") return String(obj ?? "");
    const value = obj[state.lang];
    // Fallback to German if current language value is empty/missing
    if (!value || (typeof value === "string" && value.trim() === "")) {
        return obj.de || "";
    }
    return value;
}

// -------------------------
// State mutations
// -------------------------

function setLang(lang) {
    state.lang = lang === "en" ? "en" : "de";
    logDebug("setLang", { value: state.lang });
}

function setPageSlug(slug) {
    state.pageSlug = slug;
    logDebug("setPageSlug", { value: slug });
}

const PAGE_STATUS_VALUES = new Set(["init", "hidden", "under_construction", "published"]);

function normalizePageStatusValue(value, fallback = null) {
    const raw = String(value || "").trim().toLowerCase();
    if (raw === "public") return "published";
    if (PAGE_STATUS_VALUES.has(raw)) return raw;
    const fallbackRaw = String(fallback || "").trim().toLowerCase();
    return PAGE_STATUS_VALUES.has(fallbackRaw) ? fallbackRaw : null;
}

function setCurrentPageStatusMeta(meta = null) {
    if (!meta || typeof meta !== "object") {
        state.currentPageStatus = null;
        state.currentPageEffectiveStatus = null;
        state.currentPageIsVisible = null;
        return;
    }

    const normalizedStatus = normalizePageStatusValue(meta.status, null);

    let effectiveStatusValue = null;
    if (Object.prototype.hasOwnProperty.call(meta, "effective_status")) {
        effectiveStatusValue = meta.effective_status;
    } else if (Object.prototype.hasOwnProperty.call(meta, "effectiveStatus")) {
        effectiveStatusValue = meta.effectiveStatus;
    }
    const normalizedEffectiveStatus = normalizePageStatusValue(
        effectiveStatusValue,
        normalizedStatus,
    );

    let rawVisibility = null;
    let hasVisibility = false;
    if (Object.prototype.hasOwnProperty.call(meta, "is_visible")) {
        rawVisibility = meta.is_visible;
        hasVisibility = true;
    } else if (Object.prototype.hasOwnProperty.call(meta, "isVisible")) {
        rawVisibility = meta.isVisible;
        hasVisibility = true;
    }

    state.currentPageStatus = normalizedStatus;
    state.currentPageEffectiveStatus = normalizedEffectiveStatus;
    state.currentPageIsVisible = hasVisibility
        ? rawVisibility === true
        : normalizedEffectiveStatus === "published";
}

async function updateCurrentPageStatus(nextStatus) {
    const slug = String(state.pageSlug || "").trim();
    if (!slug || slug === "unknown") {
        throw new Error("Cannot update page status without an active page.");
    }

    const normalizedStatus = normalizePageStatusValue(nextStatus, null);
    if (!normalizedStatus) {
        throw new Error("Invalid page status.");
    }

    const result = await api.updatePage(slug, { status: normalizedStatus });
    setCurrentPageStatusMeta({
        status: result?.status,
        effectiveStatus: result?.effective_status,
        isVisible: result?.is_visible,
    });
    return result;
}

function updateSection(key, patch, options = {}) {
    const sectionData = state.sectionsData?.[key];
    if (!sectionData) {
        logDebug("updateSection.noData", { key });
        return;
    }

    const explicitKind = typeof options === "string" ? options : options?.revisionKind;
    if (explicitKind) {
        pendingSectionRevisionKinds[key] = normalizeRevisionKind(explicitKind);
    } else {
        const nextKind = inferRevisionKind(key, patch, options);
        const pendingKind = pendingSectionRevisionKinds[key];
        pendingSectionRevisionKinds[key] = pendingKind
            ? mergeRevisionKind(pendingKind, nextKind)
            : nextKind;
    }
    
    // Apply each property individually to ensure Vue reactivity triggers
    for (const [k, v] of Object.entries(patch)) {
        sectionData[k] = v;
    }

    // Also update sectionsData if it exists there (same object, but ensures proxy set trap fires)
    if (state.sectionsData?.[key] && state.sectionsData[key] !== sectionData) {
        for (const [k, v] of Object.entries(patch)) {
            state.sectionsData[key][k] = v;
        }
    }

    logDebug("updateSection", { key, patch });
    debouncedSaveSection(key);
}

function setSectionAdminActiveTab(sectionKey, tabKey) {
    if (!sectionKey) return;
    const tab = String(tabKey || '').trim();
    if (!tab) {
        delete state.sectionAdminActiveTabs[sectionKey];
        return;
    }
    state.sectionAdminActiveTabs[sectionKey] = tab;
}

function upsertSectionAdminPinnedEditor(editor = {}, options = {}) {
    const id = String(editor?.id || '').trim();
    if (!id) return;

    const sectionKey = String(editor?.sectionKey || '').trim();
    const fallbackLabel = sectionKey || "section";
    const label = String(editor?.label || fallbackLabel).trim() || fallbackLabel;

    const nextEntry = { id, sectionKey, label };
    const existingIndex = state.sectionAdminPinnedEditors.findIndex((entry) => entry.id === id);
    if (existingIndex >= 0) {
        state.sectionAdminPinnedEditors[existingIndex] = {
            ...state.sectionAdminPinnedEditors[existingIndex],
            ...nextEntry,
        };
    } else {
        state.sectionAdminPinnedEditors.push(nextEntry);
    }

    const shouldActivate = options?.activate !== false;
    const activeStillExists = state.sectionAdminPinnedEditors.some((entry) => entry.id === state.sectionAdminPinnedActiveId);
    if (shouldActivate || !activeStillExists) {
        state.sectionAdminPinnedActiveId = id;
    }
}

function removeSectionAdminPinnedEditor(editorId) {
    const id = String(editorId || '').trim();
    if (!id) return;

    const index = state.sectionAdminPinnedEditors.findIndex((entry) => entry.id === id);
    if (index < 0) return;
    state.sectionAdminPinnedEditors.splice(index, 1);

    if (state.sectionAdminPinnedActiveId === id) {
        state.sectionAdminPinnedActiveId = state.sectionAdminPinnedEditors[0]?.id || "";
    }
    if (state.sectionAdminPinnedEditors.length === 0) {
        state.sectionAdminPinnedSharedTab = "";
        state.sectionAdminPinnedSharedHeightPx = null;
    }
}

function setSectionAdminPinnedActiveEditor(editorId) {
    const id = String(editorId || '').trim();
    if (!id) {
        state.sectionAdminPinnedActiveId = state.sectionAdminPinnedEditors[0]?.id || "";
        return;
    }
    if (!state.sectionAdminPinnedEditors.some((entry) => entry.id === id)) return;
    state.sectionAdminPinnedActiveId = id;
}

function setSectionAdminPinnedSharedTab(tabKey) {
    const tab = String(tabKey || '').trim();
    state.sectionAdminPinnedSharedTab = tab;
}

function setSectionAdminPinnedSharedHeightPx(heightPx) {
    if (heightPx == null || heightPx === "") {
        state.sectionAdminPinnedSharedHeightPx = null;
        return;
    }
    const parsed = Number(heightPx);
    state.sectionAdminPinnedSharedHeightPx = Number.isFinite(parsed)
        ? Math.max(0, Math.round(parsed))
        : null;
}

function setTickerItems(items, saveToBackend = true) {
    state.tickerItems = items;
    logDebug("setTickerItems", { count: items?.length });
    if (saveToBackend) saveTickerItems();
}

function setFaqItems(items, saveToBackend = true, sectionKey = 'faq') {
    const faqItems = Array.isArray(items) ? items : [];
    
    // Keep a shared FAQ cache for admin tooling and rendering.
    state.faqItems = faqItems;
    state.faqSharedLoaded = true;
    state.faqSharedSource = "local";
    
    // Also update sectionsData if the section exists there
    if (state.sectionsData?.[sectionKey]) {
        state.sectionsData[sectionKey].faqItems = faqItems;
    }
    
    logDebug("setFaqItems", { count: faqItems.length, sectionKey });
    
    if (saveToBackend) {
        const importedTags = faqItems
            .map((item) => item?.tag)
            .filter((tag) => tag && typeof tag === "object");
        saveFaqSharedData({
            items: faqItems,
            tags: [
                ...(Array.isArray(state.faqTags) ? state.faqTags : []),
                ...importedTags,
            ],
        }).catch((err) => {
            console.error("Failed to persist shared FAQ items:", err);
        });
    }
}

function toggleSectionHidden(key, pageSlug = "landing") {
    if (!state.landingLayout)     state.landingLayout = { order: [], structure: [], hidden: {}, widths: {}, gridCols: 1, fullWidth: false };
    if (!state.landingLayout.hidden) state.landingLayout.hidden = {};
    
    const newValue = !state.landingLayout.hidden[key];
    state.landingLayout.hidden[key] = newValue;
    logDebug("toggleSectionHidden", { key, hidden: newValue });
    updateSectionVisibility(pageSlug, key, !newValue);
}

function setSectionOrder(order, sectionKeys, pageSlug = "landing") {
    if (!state.landingLayout) state.landingLayout = { order: [], structure: [], hidden: {}, widths: {}, gridCols: 1, fullWidth: false };
    
    const keys = Array.isArray(sectionKeys) ? sectionKeys : Object.keys(state.sectionIds || {});
    const seen = new Set();
    const cleaned = (Array.isArray(order) ? order : [])
        .filter(k => keys.includes(k))
        .filter(k => !seen.has(k) && seen.add(k));

    for (const k of keys) {
        if (!seen.has(k)) cleaned.push(k);
    }

    state.landingLayout.order = cleaned;
    const existingStructure = Array.isArray(state.landingLayout.structure) ? state.landingLayout.structure : [];
    if (existingStructure.length > 0) {
        const maps = buildSectionContainerMaps(cleaned, existingStructure, state.sectionIds || {});
        state.landingLayout.structure = buildSectionStructureFromEntries(
            maps.nodes,
            state.sectionIds || {},
            cleaned,
        );
    } else {
        state.landingLayout.structure = buildSectionStructureFromOrder(cleaned, state.sectionIds || {});
    }
    logDebug("setSectionOrder", { order: cleaned });
    return updateSectionOrder(pageSlug, cleaned);
}

async function setSectionStructure(structure, pageSlug = "landing") {
    if (!state.landingLayout) {
        state.landingLayout = { order: [], structure: [], hidden: {}, widths: {}, gridCols: 1, fullWidth: false };
    }
    const knownKeys = Object.keys(state.sectionIds || {});
    const currentOrder = Array.isArray(state.landingLayout.order) ? state.landingLayout.order : [];
    const normalizedCurrentOrder = currentOrder.filter((key) => knownKeys.includes(key));
    const fallbackOrder = [
        ...normalizedCurrentOrder,
        ...knownKeys.filter((key) => !normalizedCurrentOrder.includes(key)),
    ];
    const incomingOrder = deriveSectionOrderFromStructure(
        structure,
        state.sectionIds || {},
        fallbackOrder,
    );
    const maps = buildSectionContainerMaps(incomingOrder, structure, state.sectionIds || {});
    const flattenedOrder = Array.isArray(maps.flattenedKeys) && maps.flattenedKeys.length
        ? maps.flattenedKeys
        : incomingOrder;
    const normalizedStructure = buildSectionStructureFromEntries(
        maps.nodes,
        state.sectionIds || {},
        flattenedOrder,
    );
    state.landingLayout.order = flattenedOrder;
    state.landingLayout.structure = normalizedStructure;
    logDebug("setSectionStructure", { order: flattenedOrder, structure: normalizedStructure });
    try {
        return await api.updatePage(pageSlug, { section_structure: normalizedStructure });
    } catch (err) {
        logDebug("setSectionStructure.error", { error: err.message });
        console.error("Failed to save section structure:", err);
        throw err;
    }
}

function setSectionWidth(key, width, pageSlug = "landing") {
    if (!state.landingLayout) state.landingLayout = { order: [], structure: [], hidden: {}, widths: {}, gridCols: 1, fullWidth: false };
    if (!state.landingLayout.widths) state.landingLayout.widths = {};
    const d = Math.max(1, Math.min(5, Number(width?.d) || 1));
    const n = Math.max(1, Math.min(d, Number(width?.n) || 1));
    const w = { n: Math.min(n, d), d };
    state.landingLayout.widths[key] = w;
    logDebug("setSectionWidth", { key, width: w });
    return updateSectionWidth(pageSlug, key, w);
}

function setSectionDeviceVisibility(key, device, visible, pageSlug = "landing") {
    if (!state.landingLayout) state.landingLayout = { order: [], structure: [], hidden: {}, widths: {}, gridCols: 1, fullWidth: false, deviceVisibility: {} };
    if (!state.landingLayout.deviceVisibility) state.landingLayout.deviceVisibility = {};
    if (!state.landingLayout.deviceVisibility[key]) {
        state.landingLayout.deviceVisibility[key] = { mobile: true, tablet: true, desktop: true };
    }
    state.landingLayout.deviceVisibility[key][device] = visible;
    logDebug("setSectionDeviceVisibility", { key, device, visible });
    return updateSectionDeviceVisibility(pageSlug, key, state.landingLayout.deviceVisibility[key]);
}

function setSectionBgPinnedKey(which, sectionKey, pageSlug = "landing") {
    if (state.pageTemplateStyleLock && !api.isTemplateBuilderContextActive?.()) {
        logDebug("setSectionBgPinnedKey.blocked", { which, sectionKey, reason: "template_style_lock" });
        return;
    }
    if (!state.landingLayout) state.landingLayout = { order: [], structure: [], hidden: {}, widths: {}, gridCols: 1, fullWidth: false, sectionBgPinnedStartKey: '', sectionBgPinnedEndKey: '' };
    
    const field = which === 'start' ? 'sectionBgPinnedStartKey' : 'sectionBgPinnedEndKey';
    state.landingLayout[field] = sectionKey || '';
    logDebug("setSectionBgPinnedKey", { which, sectionKey, pageSlug });
    
    // Save to backend
    updateSectionBgPinnedKeys(pageSlug, state.landingLayout.sectionBgPinnedStartKey, state.landingLayout.sectionBgPinnedEndKey);
}

async function updateSectionBgPinnedKeys(pageSlug, startKey, endKey) {
    if (state.pageTemplateStyleLock && !api.isTemplateBuilderContextActive?.()) {
        logDebug("updateSectionBgPinnedKeys.blocked", { pageSlug, reason: "template_style_lock" });
        return;
    }
    try {
        await api.updatePage(pageSlug, {
            section_bg_pinned_start_key: startKey || '',
            section_bg_pinned_end_key: endKey || ''
        });
        logDebug("updateSectionBgPinnedKeys saved", { pageSlug, startKey, endKey });
    } catch (err) {
        console.error("Failed to save section bg pinned keys:", err);
    }
}

function initPageState(pageDefaults) {
    const defaults = structuredClone(pageDefaults);
    
    Object.keys(defaults).forEach(key => {
        if (!(key in state) || state[key] === undefined || state[key] === null) {
            state[key] = defaults[key];
        } else if (typeof defaults[key] === 'object' && !Array.isArray(defaults[key])) {
            state[key] = { ...defaults[key], ...state[key] };
        }
    });
    logDebug("initPageState", { keys: Object.keys(defaults) });
}

// -------------------------
// Undo/Redo
// -------------------------

async function refreshRevisionStatus(sectionKey) {
    const sectionId = state.sectionIds?.[sectionKey];
    if (!sectionId) return;
    
    try {
        const status = await api.getSectionRevisionStatus(sectionId);
        state.revisionStatus[sectionKey] = {
            enabled: status.enabled !== false,
            canUndo: status.can_undo,
            canRedo: status.can_redo,
            lastSavedBy: status.last_saved_by || null,
            lastSavedAt: status.last_saved_at || null,
        };
    } catch (err) {
        console.error(`Failed to get revision status for ${sectionKey}:`, err);
    }
}

async function refreshAllRevisionStatus() {
    for (const key of Object.keys(state.sectionIds)) {
        await refreshRevisionStatus(key);
    }
    if (state.headerId) {
        await refreshHeaderRevisionStatus();
    }
}

async function refreshHeaderRevisionStatus() {
    if (!state.headerId) return;
    
    try {
        const status = await api.getHeaderRevisionStatus(state.headerId);
        state.headerRevisionStatus = {
            enabled: status.enabled !== false,
            canUndo: status.can_undo,
            canRedo: status.can_redo,
            lastSavedBy: status.last_saved_by || null,
            lastSavedAt: status.last_saved_at || null,
        };
    } catch (err) {
        console.error("Failed to get header revision status:", err);
    }
}

function buildRestoredSectionData(updated) {
    const td = updated.type_data || {};
    const sectionType = updated.section_type;
    const config = SECTION_TYPE_CONFIG[sectionType] || {};
    
    // Start with base fields
    const data = {
        title: updated.title,
        sectionType: sectionType,
        sectionIntegrationMapping: updated.section_integration_mapping || {},
    };
    if (Object.prototype.hasOwnProperty.call(updated, "section_output_mapping")) {
        data.sectionOutputMapping = updated.section_output_mapping || { mode: "default", exposed_target_paths: [] };
    }
    
    // Handle passthrough sections (like markdown)
    if (config.passthrough) {
        const passthroughTypeData = { ...td };
        delete passthroughTypeData.body;
        delete passthroughTypeData.description;
        delete passthroughTypeData.icon;
        delete passthroughTypeData.blocks;
        data.type_data = passthroughTypeData;
        if (td.cta_buttons !== undefined) {
            data.ctaButtons = normalizeSectionCtaButtonsForFrontend(td.cta_buttons);
        }
        if (td.section_generic !== undefined) {
            data.sectionGeneric = normalizeSectionGenericForFrontend(td.section_generic);
        }
        if (td.admin_notes !== undefined) data.adminNotes = td.admin_notes;
        if (td.admin_todos !== undefined) data.adminTodos = td.admin_todos;
        return data;
    }

    data.body = td.body;
    
    const arrayConfigs = config.arrays || {};
    const renames = config.renames || {};
    const defaults = config.defaults || {};
    
    // Build reverse renames map: backendKey -> frontendKey
    const reverseRenames = {};
    for (const [fKey, bKey] of Object.entries(renames)) {
        reverseRenames[bKey] = fKey;
    }
    
    // Build set of backend keys handled by arrays
    const arrayBackendKeys = new Set(Object.values(arrayConfigs).map(c => c.backendKey));
    
    // Process each field in type_data
    for (const [backendKey, value] of Object.entries(td)) {
        if (backendKey === 'body') continue; // Already handled
        if (
            sectionType === 'blog'
            && (
                backendKey === 'items'
                || backendKey === 'tags'
                || backendKey === 'blog_items'
                || backendKey === 'blog_tags'
            )
        ) continue;
        if (
            backendKey === 'title'
            || backendKey === 'icon'
            || backendKey === 'blocks'
            || backendKey === 'stages'
            || backendKey === 'program_stages_integration_mapping'
            || backendKey === 'programStagesIntegrationMapping'
            || backendKey === 'program_stages_integration_mapping_cache_state'
            || backendKey === 'programStagesIntegrationMappingCacheState'
            || backendKey === 'program_gigs_integration_mapping'
            || backendKey === 'programGigsIntegrationMapping'
            || backendKey === 'program_gigs_integration_mapping_cache_state'
            || backendKey === 'programGigsIntegrationMappingCacheState'
        ) continue;
        if (backendKey === 'section_generic') {
            data.sectionGeneric = normalizeSectionGenericForFrontend(value);
            continue;
        }
        if (backendKey === "cta_buttons") {
            data.ctaButtons = normalizeSectionCtaButtonsForFrontend(value);
            continue;
        }
        if (backendKey === "program_tile_overrides") {
            data.programTileOverrides = normalizeProgramTileOverridesForFrontend(value);
            continue;
        }
        
        // Check if this is an array field with custom transformation
        const arrayEntry = Object.entries(arrayConfigs).find(([, cfg]) => cfg.backendKey === backendKey);
        if (arrayEntry && Array.isArray(value)) {
            const [frontendKey, arrConfig] = arrayEntry;
            data[frontendKey] = value.map(arrConfig.toFrontend);
            continue;
        }
        
        // Check for reverse rename
        if (reverseRenames[backendKey]) {
            data[reverseRenames[backendKey]] = value;
            continue;
        }
        
        // Skip keys handled by array configs
        if (arrayBackendKeys.has(backendKey)) continue;
        
        // Default: auto-convert key to camelCase
        const frontendKey = toCamelCase(backendKey);
        data[frontendKey] = value;
    }
    
    // Apply defaults for missing fields
    for (const [key, defaultVal] of Object.entries(defaults)) {
        if (data[key] === undefined || data[key] === null) {
            data[key] = defaultVal;
        }
    }
    
    // Run any side effects (like updating global state)
    if (config.onLoad) {
        config.onLoad(data, td);
    }

    return data;
}

function cloneRevisionValue(value) {
    if (value == null) return value;
    try {
        return structuredClone(value);
    } catch {
        return JSON.parse(JSON.stringify(value));
    }
}

function applyRestoredSectionData(sectionKey, restoredData) {
    if (!sectionKey || !restoredData) return;

    if (!state.sectionsData) state.sectionsData = {};
    state.sectionsData[sectionKey] = restoredData;
}

function applyBackendSectionByKey(sectionKey, backendSection) {
    if (!sectionKey || !backendSection || typeof backendSection !== "object") return;

    const sectionType = String(backendSection.section_type || "").trim().toLowerCase().replace(/-/g, "_");
    const templateName = String(backendSection.section_template_name || "default").trim() || "default";
    const restoredData = buildRestoredSectionData(backendSection);
    const currentData = state.sectionsData?.[sectionKey] || {};
    applyRestoredSectionData(sectionKey, {
        ...currentData,
        ...restoredData,
    });

    if (!state.sectionMeta || typeof state.sectionMeta !== "object") {
        state.sectionMeta = {};
    }
    const currentMeta = state.sectionMeta?.[sectionKey] && typeof state.sectionMeta[sectionKey] === "object"
        ? state.sectionMeta[sectionKey]
        : {};
    const normalizedCurrentMeta = convertKeysToCamel(currentMeta);
    const titlePlaceholder = String(
        backendSection.title_placeholder
        || normalizedCurrentMeta.titlePlaceholder
        || sectionKey
        || "section"
    ).trim();
    const normalizedSectionType = String(
        sectionType
        || normalizedCurrentMeta.sectionType
        || ""
    ).trim();
    state.sectionMeta[sectionKey] = {
        ...currentMeta,
        titlePlaceholder,
        title_placeholder: titlePlaceholder,
        sectionType: normalizedSectionType,
        section_type: normalizedSectionType,
        sectionTemplateName: templateName,
        section_template_name: templateName,
        sectionTemplateRef: normalizedSectionType && templateName
            ? `${normalizedSectionType}/${templateName}`
            : "",
        section_template_ref: normalizedSectionType && templateName
            ? `${normalizedSectionType}/${templateName}`
            : "",
        shared: backendSection.shared === true,
    };
}

function applySectionRevisionPreview(
    sectionKey,
    {
        contentSnapshot = undefined,
        designSnapshot = undefined,
        applyContent = true,
        applyDesign = true,
    } = {},
) {
    if (!sectionKey) return;

    if (applyContent && contentSnapshot && typeof contentSnapshot === "object") {
        const currentSection = state.sectionsData?.[sectionKey] || {};
        const backendLikeDoc = {
            section_type: contentSnapshot.section_type || "text",
            title: contentSnapshot.title || currentSection.title || { de: "", en: "" },
            type_data: contentSnapshot.type_data || currentSection.type_data || {},
            title_placeholder: contentSnapshot.title_placeholder ?? "",
        };
        const restored = buildRestoredSectionData(backendLikeDoc);
        applyRestoredSectionData(sectionKey, {
            ...currentSection,
            ...restored,
        });

        const sharedFaqData = contentSnapshot.shared_faq_data;
        if (sharedFaqData && typeof sharedFaqData === "object") {
            applyFaqSharedData(sharedFaqData);
        }
        const sharedBlogData = contentSnapshot.shared_blog_data;
        if (sharedBlogData && typeof sharedBlogData === "object") {
            const rawItems = Array.isArray(sharedBlogData.items) ? sharedBlogData.items : [];
            const rawTags = Array.isArray(sharedBlogData.tags) ? sharedBlogData.tags : [];
            state.blogItems = rawItems
                .filter((item) => item && typeof item === "object")
                .map((it) => mapBlogSharedItem(it));
            state.blogTags = rawTags
                .filter((tag) => tag && typeof tag === "object")
                .map((tag) => ({
                    de: String(tag.de || ""),
                    en: String(tag.en || ""),
                }));
        }
        const sharedProgramData = contentSnapshot.shared_program_data;
        if (sharedProgramData && typeof sharedProgramData === "object") {
            applyProgramSharedData(sharedProgramData);
        }
    }

    if (applyDesign) {
        if (!state.sectionDesignOverrides) state.sectionDesignOverrides = {};

        if (designSnapshot === null) {
            delete state.sectionDesignOverrides[sectionKey];
            return;
        }

        if (designSnapshot && typeof designSnapshot === "object") {
            const sectionTypeData = designSnapshot.section_type_data;
            if (sectionTypeData && typeof sectionTypeData === "object") {
                const sectionData = state.sectionsData?.[sectionKey];
                if (sectionData) {
                    const designPatch = {};
                    for (const [backendKey, value] of Object.entries(sectionTypeData)) {
                        if (backendKey === "section_generic") {
                            designPatch.sectionGeneric = cloneRevisionValue(
                                normalizeSectionGenericForFrontend(value)
                            );
                            continue;
                        }
                        if (backendKey === "program_tile_overrides") {
                            designPatch.programTileOverrides = cloneRevisionValue(
                                normalizeProgramTileOverridesForFrontend(value)
                            );
                            continue;
                        }
                        const frontendKey = toCamelCase(backendKey);
                        designPatch[frontendKey] = cloneRevisionValue(value);
                    }
                    for (const [k, v] of Object.entries(designPatch)) {
                        sectionData[k] = v;
                    }
                }
            }

            const slug = state.pageSlug || "landing";
            const pageOverrides = designSnapshot.page_overrides;
            if (pageOverrides && typeof pageOverrides === "object" && Object.prototype.hasOwnProperty.call(pageOverrides, slug)) {
                const override = pageOverrides[slug];
                const normalizedOverride = normalizeSectionDesignOverridesForFrontend(
                    cloneRevisionValue(override)
                );
                if (normalizedOverride == null) delete state.sectionDesignOverrides[sectionKey];
                else state.sectionDesignOverrides[sectionKey] = normalizedOverride;
            } else {
                delete state.sectionDesignOverrides[sectionKey];
            }
        }
    }
}

async function refreshSectionDesignOverrideFromPage(sectionKey, pageSlug = state.pageSlug || "landing") {
    const sectionId = state.sectionIds?.[sectionKey];
    if (!sectionId || !pageSlug) return;

    try {
        const page = await api.getPageFull(pageSlug, true);
        const pageSections = page?.sections || [];
        const match = pageSections.find((section) => {
            const id = section?._id || section?.id;
            return id === sectionId;
        });

        if (!state.sectionDesignOverrides) state.sectionDesignOverrides = {};
        if (match?.design_overrides) {
            const normalizedOverride = normalizeSectionDesignOverridesForFrontend(match.design_overrides);
            if (normalizedOverride == null) {
                delete state.sectionDesignOverrides[sectionKey];
            } else {
                state.sectionDesignOverrides[sectionKey] = normalizedOverride;
            }
        } else {
            delete state.sectionDesignOverrides[sectionKey];
        }
    } catch (err) {
        console.error(`Failed to refresh design overrides for ${sectionKey}:`, err);
    }
}

async function undoSectionChange(sectionKey) {
    const sectionId = state.sectionIds?.[sectionKey];
    if (!sectionId) return false;
    
    try {
        const updated = await api.undoSection(sectionId);
        const restoredData = buildRestoredSectionData(updated);
        applyRestoredSectionData(sectionKey, restoredData);
        if (String(updated?.section_type || "").trim().toLowerCase() === "faq") {
            await fetchFaqSharedData();
        }
        
        await refreshSectionDesignOverrideFromPage(sectionKey);
        await refreshRevisionStatus(sectionKey);
        logDebug("undoSection.success", { sectionKey });
        return true;
    } catch (err) {
        logDebug("undoSection.error", { sectionKey, error: err.message });
        console.error(`Failed to undo ${sectionKey}:`, err);
        return false;
    }
}

async function redoSectionChange(sectionKey) {
    const sectionId = state.sectionIds?.[sectionKey];
    if (!sectionId) return false;
    
    try {
        const updated = await api.redoSection(sectionId);
        const restoredData = buildRestoredSectionData(updated);
        applyRestoredSectionData(sectionKey, restoredData);
        if (String(updated?.section_type || "").trim().toLowerCase() === "faq") {
            await fetchFaqSharedData();
        }
        
        await refreshSectionDesignOverrideFromPage(sectionKey);
        await refreshRevisionStatus(sectionKey);
        logDebug("redoSection.success", { sectionKey });
        return true;
    } catch (err) {
        logDebug("redoSection.error", { sectionKey, error: err.message });
        console.error(`Failed to redo ${sectionKey}:`, err);
        return false;
    }
}

async function undoHeaderChange() {
    if (!state.headerId) return;
    
    try {
        await api.undoHeader(state.headerId);
        await refreshHeaderRevisionStatus();
        logDebug("undoHeader.success");
        return true; // Signal to reload header data
    } catch (err) {
        logDebug("undoHeader.error", { error: err.message });
        console.error("Failed to undo header:", err);
        return false;
    }
}

async function redoHeaderChange() {
    if (!state.headerId) return;
    
    try {
        await api.redoHeader(state.headerId);
        await refreshHeaderRevisionStatus();
        logDebug("redoHeader.success");
        return true;
    } catch (err) {
        logDebug("redoHeader.error", { error: err.message });
        console.error("Failed to redo header:", err);
        return false;
    }
}

// -------------------------
// Design Settings
// -------------------------


function updateDesignSetting(key, value) {
    if (key !== 'buttonTypeStyles' && key !== 'responsiveValues' && key !== 'selectedUnits' && !(key in DEFAULT_DESIGN)) {
        console.warn(`Unknown design setting: ${key}`);
        return;
    }
    state.design[key] = value;
    state.designDirty = true;
    applyDesignCSS();
    logDebug("updateDesignSetting", { key, value });
}

function setTemplatePagePublishedDesignFromBackend(payload) {
    state.templatePagePublishedDesign = payload && typeof payload === "object"
        ? mapBackendToFrontendDesign(payload)
        : null;
}

function getTemplatePageDesignPath() {
    const templateContext = api.getTemplateBuilderContext?.();
    if (templateContext?.kind === "page" && templateContext.path) {
        return String(templateContext.path).trim();
    }
    if (state.pageTemplateStyleLock && state.pageTemplateStyleRef) {
        return String(state.pageTemplateStyleRef || "").trim();
    }
    return "";
}


async function saveDesignSettings() {
    try {
        // Snapshot the exact payload we are saving so concurrent UI edits
        // during the request are not incorrectly marked as persisted.
        const designSnapshot = JSON.parse(JSON.stringify(state.design || {}));
        const snapshotJson = JSON.stringify(designSnapshot);
        const templatePageDesignPath = getTemplatePageDesignPath();
        if (templatePageDesignPath) {
            const backendData = mapDesignToBackendFull(designSnapshot);
            const result = await api.updatePageTemplateDesignCurrent(templatePageDesignPath, backendData);
            const updatedAtRaw = result?.updated_at ?? null;
            const publishedAtRaw = result?.published_at ?? null;
            const persistedPublishedAt = state.templatePageDesignMeta?.publishedAt ?? null;
            state.templatePageDesignMeta = {
                path: String(result?.path || templatePageDesignPath || ""),
                updatedAt: updatedAtRaw || new Date().toISOString(),
                publishedAt: publishedAtRaw != null ? publishedAtRaw : persistedPublishedAt,
                initializedFromGlobalVersionId:
                    state.templatePageDesignMeta?.initializedFromGlobalVersionId || null,
            };
            if (Object.prototype.hasOwnProperty.call(result || {}, "published")) {
                setTemplatePagePublishedDesignFromBackend(result.published);
            }
            state.designRevisionStatus = {
                enabled: true,
                canUndo: false,
                canRedo: false,
                lastSavedBy: "template draft",
                lastSavedAt: result?.updated_at || null,
            };
            state._designSnapshot = snapshotJson;
            state.designDirty = JSON.stringify(state.design) !== snapshotJson;
            logDebug("saveDesignSettings.success", { scope: "template_page" });
            return;
        }

        const backendData = mapDesignToBackendFull(designSnapshot);
        await api.updateDesignSettings(backendData);
        state._designSnapshot = snapshotJson;
        state.designDirty = JSON.stringify(state.design) !== snapshotJson;
        await refreshDesignRevisionStatus();
        logDebug("saveDesignSettings.success");
    } catch (err) {
        logDebug("saveDesignSettings.error", { error: err.message });
        console.error("Failed to save design settings:", err);
        throw err;
    }
}

async function resetDesignSettingsToDefaults() {
    try {
        const templatePageDesignPath = getTemplatePageDesignPath();
        if (templatePageDesignPath) {
            const templateDesignState = await api.getPageTemplateDesignState(templatePageDesignPath);
            const publishedPayload = templateDesignState?.published || {};
            await api.updatePageTemplateDesignCurrent(templatePageDesignPath, publishedPayload);
            state.design = mapBackendToFrontendDesign(publishedPayload);
            setDesignFontStylesheetUrls(publishedPayload?.font_stylesheet_urls || []);
            state.designId = `template:${templateDesignState?.path || templatePageDesignPath}`;
            state.templatePageDesignMeta = {
                path: String(templateDesignState?.path || templatePageDesignPath || ""),
                updatedAt: new Date().toISOString(),
                publishedAt: templateDesignState?.published_at || null,
                initializedFromGlobalVersionId: templateDesignState?.initialized_from_global_version_id || null,
            };
            setTemplatePagePublishedDesignFromBackend(publishedPayload);
            state.designRevisionStatus = {
                enabled: true,
                canUndo: false,
                canRedo: false,
                lastSavedBy: "template draft",
                lastSavedAt: state.templatePageDesignMeta.updatedAt,
            };
            applyDesignCSS();
            state._designSnapshot = JSON.stringify(state.design);
            state.designDirty = false;
            logDebug("resetDesignSettings.success", { scope: "template_page" });
            return;
        }

        const result = await api.resetDesignSettings();
        state.design = mapBackendToFrontendDesign(result);
        setDesignFontStylesheetUrls(result?.font_stylesheet_urls || []);
        state.designId = result.id;
        state.templatePagePublishedDesign = null;
        applyDesignCSS();
        await refreshDesignRevisionStatus();
        logDebug("resetDesignSettings.success");
    } catch (err) {
        logDebug("resetDesignSettings.error", { error: err.message });
        console.error("Failed to reset design settings:", err);
    }
}

function resolveColor(value, fallback, bgHex, bgBaseKey = null) {
    if (value === '__high_contrast__') {
        return resolveHighContrastColorForBackground(
            state.design,
            state.adminDesignConfig,
            {
                backgroundColor: bgHex || '#ffffff',
                backgroundBaseKey: bgBaseKey,
            }
        );
    }
    if (value === 'transparent') return 'transparent';
    if (!value) return fallback;
    return value;
}

function hasNonEmptyColorValue(value) {
    if (value === undefined || value === null) return false;
    if (typeof value === "string" && value.trim() === "") return false;
    return true;
}

function normalizeButtonContrastContext(
    backgroundColor,
    backgroundBaseKey,
    fallbackBackgroundColor = null,
    fallbackBackgroundBaseKey = null
) {
    if (typeof backgroundColor === "string" && backgroundColor.trim().toLowerCase() === "transparent") {
        return {
            backgroundColor: fallbackBackgroundColor,
            backgroundBaseKey: fallbackBackgroundBaseKey,
        };
    }
    return { backgroundColor, backgroundBaseKey };
}

function resolveBaseLinkedColorKey(paramKey) {
    if (!paramKey) return null;
    const linkKey = state.adminDesignConfig?.colorLinks?.[paramKey];
    if (!linkKey) return null;
    return isBaseColorLinkKey(linkKey, state.adminDesignConfig?.parameters) ? linkKey : null;
}

function getColorVariationPercent(paramKey) {
    if (!paramKey) return 100;
    const designMap = (state.design?.colorVariations && typeof state.design.colorVariations === "object")
        ? state.design.colorVariations
        : {};
    const configMap = (state.adminDesignConfig?.colorVariations && typeof state.adminDesignConfig.colorVariations === "object")
        ? state.adminDesignConfig.colorVariations
        : {};
    const source = Object.prototype.hasOwnProperty.call(designMap, paramKey)
        ? designMap[paramKey]
        : configMap[paramKey];
    return normalizeColorVariation(source);
}

function applyDesignColorVariation(paramKey, colorValue) {
    return applyColorVariation(colorValue, getColorVariationPercent(paramKey));
}

function hexToLuminance(hex) {
    const c = hex.replace('#', '');
    const r = parseInt(c.substring(0, 2), 16) / 255;
    const g = parseInt(c.substring(2, 4), 16) / 255;
    const b = parseInt(c.substring(4, 6), 16) / 255;
    const toLinear = (v) => v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
}

function rgbToLuminance(rgb) {
    const r = (rgb?.r ?? 0) / 255;
    const g = (rgb?.g ?? 0) / 255;
    const b = (rgb?.b ?? 0) / 255;
    const toLinear = (v) => v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
}

function autoContrastColor(bgHex) {
    const rgb = parseColorToRgb(bgHex);
    if (!rgb) return '#0b1220';
    return rgbToLuminance(rgb) > 0.4 ? '#0b1220' : '#f8fafc';
}

function autoDesignContrastColor(bgHex) {
    const rgb = parseColorToRgb(bgHex);
    if (!rgb) return state.design?.highContrastDark || '#0b1220';
    return rgbToLuminance(rgb) > 0.4
        ? (state.design?.highContrastDark || '#0b1220')
        : (state.design?.highContrastLight || '#f8fafc');
}

function autoHoverBackgroundColor(bgHex) {
    const rgb = parseColorToRgb(bgHex);
    if (!rgb) return bgHex;
    return adjustBrightness(bgHex, rgbToLuminance(rgb) > 0.4 ? -8 : 12, bgHex);
}

function autoContrastMuted(bgHex) {
    const rgb = parseColorToRgb(bgHex);
    if (!rgb) return 'rgba(15, 23, 42, 0.65)';
    return rgbToLuminance(rgb) > 0.4 ? 'rgba(15, 23, 42, 0.65)' : 'rgba(248, 250, 252, 0.7)';
}

function autoContrastLogoFilter(bgHex) {
    const rgb = parseColorToRgb(bgHex);
    if (!rgb) return 'none';
    // Logos are usually dark by default; on dark topbars we invert to a light variant.
    return rgbToLuminance(rgb) > 0.4 ? 'none' : 'brightness(0) saturate(100%) invert(1)';
}

function getParamAliasValue(source, paramKey) {
    if (!source || typeof source !== "object") return undefined;
    if (source[paramKey] != null) return source[paramKey];
    const snakeKey = toSnakeCase(paramKey);
    if (source[snakeKey] != null) return source[snakeKey];
    return undefined;
}

function getSelectedUnit(paramKey, fallbackUnit = 'px') {
    const selectedUnit = getParamAliasValue(state.design.selectedUnits, paramKey);
    if (selectedUnit != null) return selectedUnit;
    // Check admin config for default unit (use != null to preserve empty string for unitless values)
    const paramConfig = state.adminDesignConfig?.parameters?.[paramKey];
    if (paramConfig?.defaultUnit != null) return paramConfig.defaultUnit;
    if (paramConfig?.unitConfigs?.[0]?.unit != null) return paramConfig.unitConfigs[0].unit;
    if (paramConfig?.unit != null) return paramConfig.unit;
    return fallbackUnit;
}

function getEffectiveViewportDevice() {
    return getEffectiveResponsiveDevice(
        state.simulatedViewport,
        state.viewportWidth,
        state.adminDesignConfig?.responsive
    );
}

function updateViewportSize(width, height) {
    const nextWidth = Number.isFinite(width) ? width : (typeof window !== "undefined" ? window.innerWidth : state.viewportWidth);
    const nextHeight = Number.isFinite(height) ? height : (typeof window !== "undefined" ? window.innerHeight : state.viewportHeight);
    state.viewportWidth = nextWidth;
    state.viewportHeight = nextHeight;
}

// Helper to get responsive value for discrete (non-CSS-variable) params
function getResponsiveDiscreteValue(paramKey, baseValue) {
    const device = getEffectiveViewportDevice();
    if (device === 'desktop') return baseValue;
    const paramRv = getParamAliasValue(state.design.responsiveValues, paramKey);
    if (paramRv?.currentMode !== 'media') return baseValue;
    const deviceVal = paramRv.media?.[device];
    return deviceVal ?? baseValue;
}

function formatCSSValue(paramKey, value, fallbackUnit = 'px', defaultValue = null) {
    if (value == null) return defaultValue;
    // If value is a string (advanced CSS like calc()), use it directly
    // but convert viewport units during simulation
    if (typeof value === 'string') {
        return convertViewportUnits(value);
    }
    // Otherwise append the selected unit
    const unit = getSelectedUnit(paramKey, fallbackUnit);
    const formatted = `${value}${unit}`;
    // Convert viewport units (vh, vw) to pixels during simulation
    return convertViewportUnits(formatted);
}

function resolveResponsiveCSSValue(paramKey, baseValue, fallbackUnit) {
    const unit = getSelectedUnit(paramKey, fallbackUnit);
    const all = getParamAliasValue(state.design.responsiveValues, paramKey);
    if (!all) return null;
    const mode = all.currentMode;
    if (!mode) return null;
    const sim = state.simulatedViewport;

    if (mode === 'clamp') {
        const rv = all.clamp;
        if (rv && rv.min != null && rv.preferred != null && rv.max != null) {
            // If values are strings (advanced CSS), use them directly without units
            const minVal = typeof rv.min === 'string' ? rv.min : `${rv.min}${rv.minUnit ?? unit ?? ''}`;
            const prefVal = typeof rv.preferred === 'string' ? rv.preferred : `${rv.preferred}${rv.preferredUnit || 'vw'}`;
            const maxVal = typeof rv.max === 'string' ? rv.max : `${rv.max}${rv.maxUnit ?? unit ?? ''}`;
            
            // During simulation, convert vw/vh units to pixels based on simulated viewport
            if (sim && sim !== 'desktop') {
                const convertedPref = convertViewportUnits(prefVal);
                const convertedMin = convertViewportUnits(minVal);
                const convertedMax = convertViewportUnits(maxVal);
                return `clamp(${convertedMin}, ${convertedPref}, ${convertedMax})`;
            }
            return `clamp(${minVal}, ${prefVal}, ${maxVal})`;
        }
    }

    // Handle media query mode during viewport simulation
    if (mode === 'media') {
        if (sim && sim !== 'desktop') {
            const rv = all.media;
            const deviceVal = rv?.[sim];
            if (deviceVal != null) {
                const formatted = typeof deviceVal === 'string' ? deviceVal : `${deviceVal}${unit}`;
                // Convert viewport units if present
                return convertViewportUnits(formatted);
            }
        }
    }

    return null;
}

const RESPONSIVE_CSS_VAR_MAP = {
    sectionBorderRadius: ['--section-border-radius', 'px'],
    sectionSpacing: ['--section-spacing', 'px'],
    sectionPadding: ['--section-padding', 'px'],
    outerSpacingSection: ['--outer-spacing-section', 'px'],
    outerSpacingNonSection: ['--outer-spacing-non-section', 'px'],
    contentPaddingTop: ['--content-padding-top', 'px'],
    contentPaddingBottom: ['--content-padding-bottom', 'px'],
    buttonBorderRadius: ['--button-border-radius', 'px'],
    buttonBorderWidth: ['--button-border-width', 'px'],
    buttonFontSize: ['--button-font-size', 'px'],
    buttonPaddingX: ['--button-padding-x', 'px'],
    buttonPaddingY: ['--button-padding-y', 'px'],
    heroOverlaySize: ['--hero-overlay-size', 'px'],
    heroHeight: ['--hero-height', 'px'],
    headerInner: ['--header-inner', 'px'],
    heroTitleFontSize: ['--hero-title-font-size', 'px'],
    heroSubtitleFontSize: ['--hero-subtitle-font-size', 'px'],
    headerFontSizeMax: null,
    headerFontSizeMin: null,
    headerLetterSpacing: null,
    headerLineHeight: null,
    h1FontSize: ['--h1-font-size', 'px'], h2FontSize: ['--h2-font-size', 'px'], h3FontSize: ['--h3-font-size', 'px'],
    h4FontSize: ['--h4-font-size', 'px'], h5FontSize: ['--h5-font-size', 'px'], h6FontSize: ['--h6-font-size', 'px'],
    h1LetterSpacing: ['--h1-letter-spacing', 'em'], h2LetterSpacing: ['--h2-letter-spacing', 'em'], h3LetterSpacing: ['--h3-letter-spacing', 'em'],
    h4LetterSpacing: ['--h4-letter-spacing', 'em'], h5LetterSpacing: ['--h5-letter-spacing', 'em'], h6LetterSpacing: ['--h6-letter-spacing', 'em'],
    h1LineHeight: ['--h1-line-height', ''], h2LineHeight: ['--h2-line-height', ''], h3LineHeight: ['--h3-line-height', ''],
    h4LineHeight: ['--h4-line-height', ''], h5LineHeight: ['--h5-line-height', ''], h6LineHeight: ['--h6-line-height', ''],
    bodyLetterSpacing: ['--body-letter-spacing', 'em'],
    bodyLineHeight: ['--body-line-height', ''],
    heroTitleLineHeight: ['--hero-title-line-height', ''],
    heroSubtitleLineHeight: ['--hero-subtitle-line-height', ''],
    heroTitleLetterSpacing: ['--hero-title-letter-spacing', 'em'],
    heroSubtitleLetterSpacing: ['--hero-subtitle-letter-spacing', 'em'],
    sectionBorderWidth: ['--section-border-width', 'px'],
};

// Map for discrete (non-numeric) parameters that can be responsive via media query
// These use CSS custom properties but don't need units
const RESPONSIVE_DISCRETE_CSS_MAP = {
    heroContentAlign: (val) => [
        ['--hero-content-align', val === 'center' ? 'center' : val === 'right' ? 'flex-end' : 'flex-start'],
        ['--hero-text-align', val],
    ],
    sectionContentAlign: (val) => [
        ['--section-content-align', val === 'center' ? 'center' : val === 'right' ? 'right' : 'left'],
        ['--section-content-justify', val === 'center' ? 'center' : val === 'right' ? 'flex-end' : 'flex-start'],
    ],
    headerTextDecoration: (val) => [['--header-text-decoration', val]],
    linkTextDecoration: (val) => [['--link-text-decoration', val]],
    linkHoverTextDecoration: (val) => [['--link-hover-text-decoration', val]],
    sectionBorderStyle: (val) => [['--section-border-style', val]],
    // Font weights (per-heading + shared header var)
    headerFontWeight: (val) => [['--header-font-weight', val]],
    h1FontWeight: (val) => [['--h1-font-weight', val], ['--header-font-weight', val]],
    h2FontWeight: (val) => [['--h2-font-weight', val]],
    h3FontWeight: (val) => [['--h3-font-weight', val]],
    h4FontWeight: (val) => [['--h4-font-weight', val]],
    h5FontWeight: (val) => [['--h5-font-weight', val]],
    h6FontWeight: (val) => [['--h6-font-weight', val]],
    bodyFontWeight: (val) => [['--body-font-weight', val]],
    // Box shadow
    sectionBoxShadow: (val) => [['--section-box-shadow', val || '0 6px 20px rgba(17, 24, 39, 0.08)']],
};

function buildResponsiveMediaStyles() {
    const allRv = state.design.responsiveValues || {};
    const sim = state.simulatedViewport;
    const responsiveConfig = state.adminDesignConfig?.responsive;

    // Helper to format value - if string (advanced CSS), use directly; else append unit
    const formatVal = (v, unit) => typeof v === 'string' ? v : `${v}${unit}`;

    if (sim && sim !== 'desktop') {
        const overrides = [];
        for (const [key, paramRv] of Object.entries(allRv)) {
            if (paramRv.currentMode !== 'media') continue;
            const vals = paramRv.media;
            if (!vals) continue;
            const v = vals[sim];
            if (v == null) continue;
            const normalizedKey = key.replace(/_([a-z0-9])/g, (_, ch) => ch.toUpperCase());

            // Check numeric CSS var map first
            const mapping = RESPONSIVE_CSS_VAR_MAP[normalizedKey];
            if (mapping) {
                const [varName, fallbackUnit] = mapping;
                const unit = getSelectedUnit(normalizedKey, fallbackUnit);
                overrides.push(`${varName}: ${formatVal(v, unit)} !important;`);
                continue;
            }

            // Check discrete CSS var map
            const discreteFn = RESPONSIVE_DISCRETE_CSS_MAP[normalizedKey];
            if (discreteFn) {
                const props = discreteFn(v);
                for (const [varName, varVal] of props) {
                    overrides.push(`${varName}: ${varVal} !important;`);
                }
            }
        }
        return overrides.length ? `:root { ${overrides.join(' ')} }\n` : '';
    }

    const mobile = [];
    const tablet = [];

    for (const [key, paramRv] of Object.entries(allRv)) {
        if (paramRv.currentMode !== 'media') continue;
        const vals = paramRv.media;
        if (!vals) continue;
        const normalizedKey = key.replace(/_([a-z0-9])/g, (_, ch) => ch.toUpperCase());

        // Check numeric CSS var map first
        const mapping = RESPONSIVE_CSS_VAR_MAP[normalizedKey];
        if (mapping) {
            const [varName, fallbackUnit] = mapping;
            const unit = getSelectedUnit(normalizedKey, fallbackUnit);
            if (vals.mobile != null) mobile.push(`${varName}: ${formatVal(vals.mobile, unit)} !important;`);
            if (vals.tablet != null) tablet.push(`${varName}: ${formatVal(vals.tablet, unit)} !important;`);
            continue;
        }

        // Check discrete CSS var map
        const discreteFn = RESPONSIVE_DISCRETE_CSS_MAP[normalizedKey];
        if (discreteFn) {
            if (vals.mobile != null) {
                const props = discreteFn(vals.mobile);
                for (const [varName, varVal] of props) {
                    mobile.push(`${varName}: ${varVal} !important;`);
                }
            }
            if (vals.tablet != null) {
                const props = discreteFn(vals.tablet);
                for (const [varName, varVal] of props) {
                    tablet.push(`${varName}: ${varVal} !important;`);
                }
            }
        }
    }

    let css = '';
    const tabletQuery = buildResponsiveMediaQuery("tablet", responsiveConfig);
    const mobileQuery = buildResponsiveMediaQuery("mobile", responsiveConfig);
    if (tablet.length && tabletQuery) css += `@media ${tabletQuery} { :root { ${tablet.join(' ')} } }\n`;
    if (mobile.length && mobileQuery) css += `@media ${mobileQuery} { :root { ${mobile.join(' ')} } }\n`;
    return css;
}

function normalizeSimulatedViewport(device) {
    return device === 'mobile' || device === 'tablet' ? device : null;
}

function setSimulatedViewport(device) {
    state.simulatedViewport = normalizeSimulatedViewport(device);
    applyDesignCSS();
}

function setHideResponsiveUI(hide) {
    state.hideResponsiveUI = hide;
}

// Convert viewport units (vw, vh) to pixels based on simulated viewport
function convertViewportUnits(value) {
    const sim = state.simulatedViewport;
    if (!sim || !value || typeof value !== 'string') return value;
    
    const viewport = getResponsivePreviewSize(state.adminDesignConfig?.responsive, sim);
    if (!viewport) return value;
    
    // Replace vw units with calculated pixel values
    let result = value.replace(/(\d+(?:\.\d+)?)\s*vw/gi, (match, num) => {
        const px = (parseFloat(num) / 100) * viewport.width;
        return `${px}px`;
    });
    
    // Replace vh units with calculated pixel values
    result = result.replace(/(\d+(?:\.\d+)?)\s*vh/gi, (match, num) => {
        const px = (parseFloat(num) / 100) * viewport.height;
        return `${px}px`;
    });
    
    return result;
}

function applyDesignCSS() {
    const root = document.documentElement;
    const d = state.design;
    const responsiveConfig = normalizeResponsiveConfig(state.adminDesignConfig?.responsive);

    ensureCachedFontStylesheetsLoaded(state.designFontStylesheetUrls);
    for (const [name, value] of Object.entries(buildResponsiveCssVars(responsiveConfig))) {
        root.style.setProperty(name, value);
    }
    
    // Typography - Headers (shared)
    root.style.setProperty('--header-font-family', d.headerFontFamily);
    root.style.setProperty('--header-text-decoration', d.headerTextDecoration || 'none');

    // Per-heading typography
    if (d.headingLinearScaling) {
        // Linearly interpolate h2-h5 from h1 and h6 for font-size, letter-spacing, line-height
        const h1Size = d.h1FontSize ?? 48;
        const h6Size = d.h6FontSize ?? 14;
        const h1LS = d.h1LetterSpacing ?? -0.02;
        const h6LS = d.h6LetterSpacing ?? 0;
        const h1LH = d.h1LineHeight ?? 1.2;
        const h6LH = d.h6LineHeight ?? 1.3;
        for (let i = 1; i <= 6; i++) {
            const t = (6 - i) / 5; // 1.0, 0.8, 0.6, 0.4, 0.2, 0
            const size = Math.round(h6Size + (h1Size - h6Size) * t);
            const ls = +(h6LS + (h1LS - h6LS) * t).toFixed(3);
            const lh = +(h6LH + (h1LH - h6LH) * t).toFixed(2);
            root.style.setProperty(`--h${i}-font-size`, resolveResponsiveCSSValue(`h${i}FontSize`, size, 'px') || `${size}px`);
            root.style.setProperty(`--h${i}-letter-spacing`, `${ls}em`);
            root.style.setProperty(`--h${i}-line-height`, String(lh));
        }
    } else {
        for (let i = 1; i <= 6; i++) {
            const size = d[`h${i}FontSize`];
            const ls = d[`h${i}LetterSpacing`];
            const lh = d[`h${i}LineHeight`];
            root.style.setProperty(`--h${i}-font-size`, resolveResponsiveCSSValue(`h${i}FontSize`, size, 'px') || `${size}px`);
            root.style.setProperty(`--h${i}-letter-spacing`, resolveResponsiveCSSValue(`h${i}LetterSpacing`, ls, 'em') || `${ls}em`);
            root.style.setProperty(`--h${i}-line-height`, resolveResponsiveCSSValue(`h${i}LineHeight`, lh, '') || String(lh));
        }
    }
    // Font weight is always per-heading (not part of linear scaling)
    for (let i = 1; i <= 6; i++) {
        root.style.setProperty(`--h${i}-font-weight`, d[`h${i}FontWeight`] || '800');
    }
    // Shared header vars point to H1 values
    root.style.setProperty('--header-font-weight', d.h1FontWeight || '800');
    root.style.setProperty('--header-letter-spacing', `${d.h1LetterSpacing ?? -0.02}em`);
    root.style.setProperty('--header-line-height', String(d.h1LineHeight ?? 1.2));
    
    // Typography - Body
    root.style.setProperty('--body-font-family', d.bodyFontFamily);
    root.style.setProperty('--body-font-weight', d.bodyFontWeight);
    root.style.setProperty('--body-letter-spacing', resolveResponsiveCSSValue('bodyLetterSpacing', d.bodyLetterSpacing, 'em') || `${d.bodyLetterSpacing}em`);
    root.style.setProperty('--body-line-height', resolveResponsiveCSSValue('bodyLineHeight', d.bodyLineHeight, '') || d.bodyLineHeight);
    
    // Colors
    const backgroundPrimary = d.backgroundPrimaryColor || '#f6f7fb';
    const backgroundSecondary = d.backgroundSecondaryColor || '#ffffff';
    const pageBgBaseKey = resolveBaseLinkedColorKey('backgroundColor') || 'backgroundPrimaryColor';
    const sectionBgBaseKey = resolveBaseLinkedColorKey('sectionBackgroundColor') || 'backgroundSecondaryColor';
    const pageBg = resolveColor(
        d.backgroundColor,
        backgroundPrimary,
        backgroundPrimary,
        pageBgBaseKey
    );
    const sectionBg = resolveColor(
        d.sectionBackgroundColor,
        backgroundSecondary,
        backgroundSecondary,
        sectionBgBaseKey
    );
    root.style.setProperty('--primary-color', d.primaryColor);
    root.style.setProperty('--secondary-color', d.secondaryColor);
    root.style.setProperty('--background-primary-color', backgroundPrimary);
    root.style.setProperty('--background-secondary-color', backgroundSecondary);
    root.style.setProperty('--bg', pageBg);
    root.style.setProperty('--accent', d.accentColor);
    root.style.setProperty('--section-background-color', sectionBg);
    root.style.setProperty(
        '--hero-page-background-contrast-color',
        resolveHighContrastColorForBackground(
            d,
            state.adminDesignConfig,
            {
                backgroundColor: pageBg,
                backgroundBaseKey: pageBgBaseKey,
            }
        )
    );
    const defaultHeadingColor = resolveColor(
        '__high_contrast__',
        d.primaryColor,
        sectionBg,
        sectionBgBaseKey
    );
    const headingColor = applyDesignColorVariation(
        'headingColor',
        resolveColor(d.headingColor, defaultHeadingColor, sectionBg, sectionBgBaseKey)
    );
    root.style.setProperty('--heading-color', headingColor);
    for (let i = 1; i <= 4; i += 1) {
        const paramKey = `h${i}Color`;
        const headingVar = `--h${i}-color`;
        const resolved = applyDesignColorVariation(
            paramKey,
            resolveColor(d[paramKey], headingColor, sectionBg, sectionBgBaseKey)
        );
        root.style.setProperty(headingVar, resolved);
    }
    root.style.setProperty(
        '--paragraph-color',
        applyDesignColorVariation(
            'paragraphColor',
            resolveColor(d.paragraphColor, d.secondaryColor, sectionBg, sectionBgBaseKey)
        )
    );
    // Sections
    root.style.setProperty('--section-border-radius', resolveResponsiveCSSValue('sectionBorderRadius', d.sectionBorderRadius, 'px') || formatCSSValue('sectionBorderRadius', d.sectionBorderRadius, 'px', '0px'));
    root.style.setProperty('--section-spacing', resolveResponsiveCSSValue('sectionSpacing', d.sectionSpacing, 'px') || formatCSSValue('sectionSpacing', d.sectionSpacing, 'px', '0px'));
    root.style.setProperty('--section-box-shadow', d.sectionBoxShadow || '0 6px 20px rgba(17, 24, 39, 0.08)');
    root.style.setProperty('--section-padding', resolveResponsiveCSSValue('sectionPadding', d.sectionPadding, 'px') || formatCSSValue('sectionPadding', d.sectionPadding ?? 18, 'px', '18px'));
    const sectionContentAlign = d.sectionContentAlign || 'left';
    root.style.setProperty('--section-content-align', sectionContentAlign === 'center' ? 'center' : sectionContentAlign === 'right' ? 'right' : 'left');
    root.style.setProperty('--section-content-justify', sectionContentAlign === 'center' ? 'center' : sectionContentAlign === 'right' ? 'flex-end' : 'flex-start');
    
    // Section border
    root.style.setProperty('--section-border-width', resolveResponsiveCSSValue('sectionBorderWidth', d.sectionBorderWidth, 'px') || formatCSSValue('sectionBorderWidth', d.sectionBorderWidth ?? 0, 'px', '0px'));
    root.style.setProperty('--section-border-color', applyDesignColorVariation('sectionBorderColor', d.sectionBorderColor || '#0b1220'));
    root.style.setProperty('--section-border-style', d.sectionBorderStyle || 'solid');

    // Global custom CSS (desktop/all + tablet + mobile with media queries)
    let globalCssEl = document.getElementById('global-custom-css');
    const hasAnyCss = d.globalCustomCss || d.globalCustomCssTablet || d.globalCustomCssMobile;
    if (hasAnyCss) {
        if (!globalCssEl) {
            globalCssEl = document.createElement('style');
            globalCssEl.id = 'global-custom-css';
            document.head.appendChild(globalCssEl);
        }
        let cssContent = '';
        // Desktop/All CSS (no media query wrapper)
        if (d.globalCustomCss) {
            cssContent += `/* Desktop/All */\n${d.globalCustomCss}\n`;
        }
        const tabletQuery = buildResponsiveMediaQuery('tablet', responsiveConfig);
        const mobileQuery = buildResponsiveMediaQuery('mobile', responsiveConfig);
        // Tablet CSS
        if (d.globalCustomCssTablet) {
            cssContent += `/* Tablet */\n@media ${tabletQuery} {\n${d.globalCustomCssTablet}\n}\n`;
        }
        // Mobile CSS
        if (d.globalCustomCssMobile) {
            cssContent += `/* Mobile */\n@media ${mobileQuery} {\n${d.globalCustomCssMobile}\n}\n`;
        }
        // During viewport simulation, also apply the simulated viewport's CSS directly
        // (media queries don't trigger because the actual browser width doesn't change)
        const sim = state.simulatedViewport;
        if (sim === 'tablet' && d.globalCustomCssTablet) {
            cssContent += `/* Tablet (simulated) */\n${d.globalCustomCssTablet}\n`;
        } else if (sim === 'mobile' && d.globalCustomCssMobile) {
            cssContent += `/* Mobile (simulated) */\n${d.globalCustomCssMobile}\n`;
        }
        globalCssEl.textContent = cssContent;
    } else if (globalCssEl) {
        globalCssEl.textContent = '';
    }

    // Layout
    root.style.setProperty('--outer-spacing-section', resolveResponsiveCSSValue('outerSpacingSection', d.outerSpacingSection, 'px') || formatCSSValue('outerSpacingSection', d.outerSpacingSection ?? 0, 'px', '0px'));
    root.style.setProperty('--outer-spacing-non-section-desktop', formatCSSValue('outerSpacingNonSection', d.outerSpacingNonSection ?? 0, 'px', '0px'));
    root.style.setProperty('--outer-spacing-non-section', resolveResponsiveCSSValue('outerSpacingNonSection', d.outerSpacingNonSection, 'px') || formatCSSValue('outerSpacingNonSection', d.outerSpacingNonSection ?? 0, 'px', '0px'));
    root.style.setProperty('--content-padding-top', resolveResponsiveCSSValue('contentPaddingTop', d.contentPaddingTop, 'px') || formatCSSValue('contentPaddingTop', d.contentPaddingTop ?? 22, 'px', '22px'));
    root.style.setProperty('--content-padding-bottom', resolveResponsiveCSSValue('contentPaddingBottom', d.contentPaddingBottom, 'px') || formatCSSValue('contentPaddingBottom', d.contentPaddingBottom ?? 26, 'px', '26px'));
    
    // Links
    root.style.setProperty('--link-text-decoration', d.linkTextDecoration || 'none');
    root.style.setProperty('--link-hover-text-decoration', d.linkHoverTextDecoration || 'underline');
    if (hasNonEmptyColorValue(d.linkColor)) {
        root.style.setProperty(
            '--link-color',
            applyDesignColorVariation(
                'linkColor',
                resolveColor(d.linkColor, 'inherit', sectionBg, sectionBgBaseKey)
            )
        );
    } else {
        root.style.removeProperty('--link-color');
    }
    if (hasNonEmptyColorValue(d.linkHoverColor)) {
        root.style.setProperty(
            '--link-hover-color',
            applyDesignColorVariation(
                'linkHoverColor',
                resolveColor(d.linkHoverColor, 'inherit', sectionBg, sectionBgBaseKey)
            )
        );
    } else {
        root.style.removeProperty('--link-hover-color');
    }

    // Buttons (shared for all button types)
    root.style.setProperty('--button-border-radius', resolveResponsiveCSSValue('buttonBorderRadius', d.buttonBorderRadius, 'px') || formatCSSValue('buttonBorderRadius', d.buttonBorderRadius ?? 12, 'px', '12px'));
    root.style.setProperty('--button-border-width', resolveResponsiveCSSValue('buttonBorderWidth', d.buttonBorderWidth, 'px') || formatCSSValue('buttonBorderWidth', d.buttonBorderWidth ?? 1, 'px', '1px'));
    root.style.setProperty('--button-font-size', resolveResponsiveCSSValue('buttonFontSize', d.buttonFontSize, 'px') || formatCSSValue('buttonFontSize', d.buttonFontSize ?? 16, 'px', '16px'));
    root.style.setProperty('--button-padding-x', resolveResponsiveCSSValue('buttonPaddingX', d.buttonPaddingX, 'px') || formatCSSValue('buttonPaddingX', d.buttonPaddingX ?? 12, 'px', '12px'));
    root.style.setProperty('--button-padding-y', resolveResponsiveCSSValue('buttonPaddingY', d.buttonPaddingY, 'px') || formatCSSValue('buttonPaddingY', d.buttonPaddingY ?? 10, 'px', '10px'));

    // Hero / Header
    const heroAlign = d.heroContentAlign || 'left';
    root.style.setProperty('--hero-content-align', heroAlign === 'center' ? 'center' : heroAlign === 'right' ? 'flex-end' : 'flex-start');
    root.style.setProperty('--hero-text-align', heroAlign);

    root.style.setProperty('--hero-title-font-size', resolveResponsiveCSSValue('heroTitleFontSize', d.heroTitleFontSize, 'px') || (d.heroTitleFontSize ? formatCSSValue('heroTitleFontSize', d.heroTitleFontSize, 'px') : 'clamp(34px, 4vw, 56px)'));
    root.style.setProperty('--hero-title-line-height', d.heroTitleLineHeight ? String(d.heroTitleLineHeight) : 'var(--header-line-height)');
    if (d.heroTitleLetterSpacing != null) root.style.setProperty('--hero-title-letter-spacing', formatCSSValue('heroTitleLetterSpacing', d.heroTitleLetterSpacing, 'em'));
    else root.style.removeProperty('--hero-title-letter-spacing');
    if (d.heroTitleColor) root.style.setProperty('--hero-title-color', applyDesignColorVariation('heroTitleColor', d.heroTitleColor));
    else root.style.removeProperty('--hero-title-color');

    // Hero title text shadow
    if (d.heroTitleTextShadowEnabled) {
      const offset = (d.heroTitleTextShadowOffset ?? 4) + 'px';
      const color = applyDesignColorVariation('heroTitleTextShadowColor', d.heroTitleTextShadowColor || 'rgba(0,0,0,0.3)');
      root.style.setProperty('--hero-title-text-shadow', `${offset} ${offset} ${color}`);
    } else {
      root.style.setProperty('--hero-title-text-shadow', 'none');
    }

    root.style.setProperty('--hero-subtitle-font-size', resolveResponsiveCSSValue('heroSubtitleFontSize', d.heroSubtitleFontSize, 'px') || (d.heroSubtitleFontSize ? formatCSSValue('heroSubtitleFontSize', d.heroSubtitleFontSize, 'px') : '16px'));
    root.style.setProperty('--hero-subtitle-line-height', d.heroSubtitleLineHeight ? String(d.heroSubtitleLineHeight) : 'var(--body-line-height)');
    if (d.heroSubtitleLetterSpacing != null) root.style.setProperty('--hero-subtitle-letter-spacing', formatCSSValue('heroSubtitleLetterSpacing', d.heroSubtitleLetterSpacing, 'em'));
    else root.style.removeProperty('--hero-subtitle-letter-spacing');
    if (d.heroSubtitleColor) root.style.setProperty('--hero-subtitle-color', applyDesignColorVariation('heroSubtitleColor', d.heroSubtitleColor));
    else root.style.removeProperty('--hero-subtitle-color');

    const sharedButtonBgRaw = resolveColor(d.buttonBgColor, d.accentColor, sectionBg, sectionBgBaseKey);
    const sharedButtonBgBaseKey = resolveBaseLinkedColorKey('buttonBgColor') || sectionBgBaseKey;
    const sharedBgContrast = normalizeButtonContrastContext(
        sharedButtonBgRaw,
        sharedButtonBgBaseKey,
        sectionBg,
        sectionBgBaseKey
    );
    const sharedButtonColorRaw = resolveColor(
        d.buttonColor,
        '#fff',
        sharedBgContrast.backgroundColor,
        sharedBgContrast.backgroundBaseKey
    );
    const sharedButtonBorderRaw = resolveColor(
        d.buttonBorderColor || 'transparent',
        'transparent',
        sharedBgContrast.backgroundColor,
        sharedBgContrast.backgroundBaseKey
    );
    const sharedButtonHoverBgBaseKey = resolveBaseLinkedColorKey('buttonHoverBgColor') || sharedButtonBgBaseKey;
    const sharedButtonHoverBgRaw = resolveColor(
        d.buttonHoverBgColor,
        sharedButtonBgRaw,
        sectionBg,
        sectionBgBaseKey
    );
    const sharedHoverBgContrast = normalizeButtonContrastContext(
        sharedButtonHoverBgRaw,
        sharedButtonHoverBgBaseKey,
        sectionBg,
        sectionBgBaseKey
    );
    const sharedButtonHoverColorRaw = resolveColor(
        d.buttonHoverColor,
        sharedButtonColorRaw,
        sharedHoverBgContrast.backgroundColor,
        sharedHoverBgContrast.backgroundBaseKey
    );
    const sharedButtonHoverBorderRaw = resolveColor(
        d.buttonHoverBorderColor || sharedButtonBorderRaw,
        sharedButtonBorderRaw,
        sharedHoverBgContrast.backgroundColor,
        sharedHoverBgContrast.backgroundBaseKey
    );

    root.style.setProperty('--button-border-color', applyDesignColorVariation('buttonBorderColor', sharedButtonBorderRaw));
    if (hasNonEmptyColorValue(d.buttonBgColor)) {
        root.style.setProperty('--button-bg-color', applyDesignColorVariation('buttonBgColor', sharedButtonBgRaw));
    } else {
        root.style.removeProperty('--button-bg-color');
    }
    if (hasNonEmptyColorValue(d.buttonColor)) {
        root.style.setProperty('--button-color', applyDesignColorVariation('buttonColor', sharedButtonColorRaw));
    } else {
        root.style.removeProperty('--button-color');
    }
    if (hasNonEmptyColorValue(d.buttonHoverBgColor)) {
        root.style.setProperty('--button-hover-bg-color', applyDesignColorVariation('buttonHoverBgColor', sharedButtonHoverBgRaw));
    } else {
        root.style.removeProperty('--button-hover-bg-color');
    }
    if (hasNonEmptyColorValue(d.buttonHoverColor)) {
        root.style.setProperty('--button-hover-color', applyDesignColorVariation('buttonHoverColor', sharedButtonHoverColorRaw));
    } else {
        root.style.removeProperty('--button-hover-color');
    }
    if (hasNonEmptyColorValue(d.buttonHoverBorderColor)) {
        root.style.setProperty('--button-hover-border-color', applyDesignColorVariation('buttonHoverBorderColor', sharedButtonHoverBorderRaw));
    } else {
        root.style.removeProperty('--button-hover-border-color');
    }

    // Per-type button overrides
    const typeStyles = d.buttonTypeStyles || {};
    const colorLinks = state.adminDesignConfig?.colorLinks || {};
    const cssParamMap = {
      bgColor: 'bg-color', color: 'color', borderColor: 'border-color',
      hoverBgColor: 'hover-bg-color', hoverColor: 'hover-color', hoverBorderColor: 'hover-border-color',
      borderRadius: 'border-radius', borderWidth: 'border-width',
      fontSize: 'font-size', paddingX: 'padding-x', paddingY: 'padding-y',
    };
    const pxParams = new Set(['borderRadius', 'borderWidth', 'fontSize', 'paddingX', 'paddingY']);
    for (const [typeId, overridesRaw] of Object.entries(typeStyles)) {
      const overrides = (overridesRaw && typeof overridesRaw === 'object') ? overridesRaw : {};
      const typeBgParamKey = `btnType_${typeId}_bgColor`;
      const typeBgBaseKey = isBaseColorLinkKey(colorLinks[typeBgParamKey], state.adminDesignConfig?.parameters)
          ? colorLinks[typeBgParamKey]
          : sharedButtonBgBaseKey;
      const typeBgRaw = resolveColor(
          overrides.bgColor,
          sharedButtonBgRaw,
          sectionBg,
          sectionBgBaseKey
      );
      const typeBgContrast = normalizeButtonContrastContext(
          typeBgRaw,
          typeBgBaseKey,
          sectionBg,
          sectionBgBaseKey
      );
      const typeColorRaw = resolveColor(
          overrides.color,
          sharedButtonColorRaw,
          typeBgContrast.backgroundColor,
          typeBgContrast.backgroundBaseKey
      );
      const typeBorderRaw = resolveColor(
          overrides.borderColor,
          sharedButtonBorderRaw,
          typeBgContrast.backgroundColor,
          typeBgContrast.backgroundBaseKey
      );

      const typeHoverBgParamKey = `btnType_${typeId}_hoverBgColor`;
      const typeHoverBgBaseKey = isBaseColorLinkKey(colorLinks[typeHoverBgParamKey], state.adminDesignConfig?.parameters)
          ? colorLinks[typeHoverBgParamKey]
          : typeBgBaseKey;
      const typeHoverBgRaw = resolveColor(
          overrides.hoverBgColor,
          typeBgRaw,
          sectionBg,
          sectionBgBaseKey
      );
      const typeHoverBgContrast = normalizeButtonContrastContext(
          typeHoverBgRaw,
          typeHoverBgBaseKey,
          sectionBg,
          sectionBgBaseKey
      );
      const typeHoverColorRaw = resolveColor(
          overrides.hoverColor,
          typeColorRaw,
          typeHoverBgContrast.backgroundColor,
          typeHoverBgContrast.backgroundBaseKey
      );
      const typeHoverBorderRaw = resolveColor(
          overrides.hoverBorderColor,
          typeBorderRaw,
          typeHoverBgContrast.backgroundColor,
          typeHoverBgContrast.backgroundBaseKey
      );

      for (const [param, val] of Object.entries(overrides)) {
        const cssProp = cssParamMap[param];
        if (!cssProp) continue;
        const varName = `--button-${typeId}-${cssProp}`;
        if (val == null) {
          root.style.removeProperty(varName);
        } else {
          if (pxParams.has(param)) {
            root.style.setProperty(varName, `${val}px`);
          } else {
            const variationKey = `btnType_${typeId}_${param}`;
            const fallbackByParam = {
              bgColor: sharedButtonBgRaw,
              color: sharedButtonColorRaw,
              borderColor: sharedButtonBorderRaw,
              hoverBgColor: typeBgRaw,
              hoverColor: typeColorRaw,
              hoverBorderColor: typeBorderRaw,
            };
            const contrastBgByParam = {
              bgColor: sectionBg,
              color: typeBgContrast.backgroundColor,
              borderColor: typeBgContrast.backgroundColor,
              hoverBgColor: sectionBg,
              hoverColor: typeHoverBgContrast.backgroundColor,
              hoverBorderColor: typeHoverBgContrast.backgroundColor,
            };
            const contrastBaseKeyByParam = {
              bgColor: sectionBgBaseKey,
              color: typeBgContrast.backgroundBaseKey,
              borderColor: typeBgContrast.backgroundBaseKey,
              hoverBgColor: sectionBgBaseKey,
              hoverColor: typeHoverBgContrast.backgroundBaseKey,
              hoverBorderColor: typeHoverBgContrast.backgroundBaseKey,
            };
            const fallbackColor = fallbackByParam[param] ?? sharedButtonBgRaw;
            const contrastBg = contrastBgByParam[param] ?? sectionBg;
            const contrastBaseKey = contrastBaseKeyByParam[param] ?? sectionBgBaseKey;
            const resolvedColor = resolveColor(val, fallbackColor, contrastBg, contrastBaseKey);
            root.style.setProperty(varName, applyDesignColorVariation(variationKey, resolvedColor));
          }
        }
      }
    }

    root.style.setProperty('--hero-overlay-size', resolveResponsiveCSSValue('heroOverlaySize', d.heroOverlaySize, 'px') || formatCSSValue('heroOverlaySize', d.heroOverlaySize ?? 150, 'px', '150px'));
    const heroHeightValue = resolveResponsiveCSSValue('heroHeight', d.heroHeight, 'px') || formatCSSValue('heroHeight', d.heroHeight ?? 400, 'px', '400px');
    root.style.setProperty('--hero-height', heroHeightValue);
    root.style.setProperty('--header-inner', resolveResponsiveCSSValue('headerInner', d.headerInner, 'px') || formatCSSValue('headerInner', d.headerInner ?? 44, 'px', '44px'));

    // Topbar
    const topbarBgBaseKey = resolveBaseLinkedColorKey('topbarBgColor') || sectionBgBaseKey;
    const topbarBg = applyDesignColorVariation(
        'topbarBgColor',
        resolveColor(
            d.topbarBgColor,
            sectionBg,
            sectionBg,
            sectionBgBaseKey
        )
    );
    const topbarItemColor = applyDesignColorVariation(
        'topbarItemColor',
        resolveColor(
            d.topbarItemColor,
            autoContrastColor(topbarBg),
            topbarBg,
            topbarBgBaseKey
        )
    );
    const topbarItemHoverColor = applyDesignColorVariation(
        'topbarItemHoverColor',
        resolveColor(
            d.topbarItemHoverColor,
            d.accentColor || topbarItemColor,
            topbarBg,
            topbarBgBaseKey
        )
    );
    root.style.setProperty('--topbar-bg-color', topbarBg);
    root.style.setProperty('--topbar-text-color', topbarItemColor);
    root.style.setProperty('--topbar-item-color', topbarItemColor);
    root.style.setProperty('--topbar-item-hover-color', topbarItemHoverColor);
    root.style.setProperty('--topbar-muted-color', autoContrastMuted(topbarBg));
    root.style.setProperty('--topbar-logo-filter', autoContrastLogoFilter(topbarBg));

    // Sidebar
    const sidebarBgBaseKey = resolveBaseLinkedColorKey('sidebarBgColor') || sectionBgBaseKey;
    const sidebarBg = applyDesignColorVariation(
        'sidebarBgColor',
        resolveColor(
            d.sidebarBgColor,
            'rgba(255,255,255,0.96)',
            sectionBg,
            sectionBgBaseKey
        )
    );
    const sidebarItemColor = applyDesignColorVariation(
        'sidebarItemColor',
        resolveColor(
            d.sidebarItemColor,
            '#111827',
            sidebarBg,
            sidebarBgBaseKey
        )
    );
    const sidebarItemHoverColor = applyDesignColorVariation(
        'sidebarItemHoverColor',
        resolveColor(
            d.sidebarItemHoverColor,
            d.accentColor || sidebarItemColor,
            sidebarBg,
            sidebarBgBaseKey
        )
    );
    root.style.setProperty('--sidebar-bg-color', sidebarBg);
    root.style.setProperty('--sidebar-item-color', sidebarItemColor);
    root.style.setProperty('--sidebar-item-bg-color', 'transparent');
    root.style.setProperty('--sidebar-item-hover-color', sidebarItemHoverColor);
    root.style.setProperty('--sidebar-item-hover-bg-color', 'transparent');

    // Admin palette
    const adminAccent = applyDesignColorVariation(
        'adminAccentColor',
        resolveColor(d.adminAccentColor, '#cb00e6', sectionBg, sectionBgBaseKey)
    );
    const adminPrimary = applyDesignColorVariation(
        'adminPrimaryColor',
        resolveColor(d.adminPrimaryColor, adminAccent, sectionBg, sectionBgBaseKey)
    );
    const adminDanger = applyDesignColorVariation(
        'adminDangerColor',
        resolveColor(d.adminDangerColor, '#dc2626', sectionBg, sectionBgBaseKey)
    );
    const adminWarning = applyDesignColorVariation(
        'adminWarningColor',
        resolveColor(d.adminWarningColor, '#d97706', sectionBg, sectionBgBaseKey)
    );
    const adminFavorite = applyDesignColorVariation(
        'adminFavoriteColor',
        resolveColor(d.adminFavoriteColor, '#b45309', sectionBg, sectionBgBaseKey)
    );
    const adminPrimaryHover = autoHoverBackgroundColor(adminPrimary);
    const adminDangerHover = autoHoverBackgroundColor(adminDanger);
    root.style.setProperty('--admin-accent', adminAccent);
    root.style.setProperty('--admin-primary-color', adminPrimary);
    root.style.setProperty('--admin-primary-text-color', autoDesignContrastColor(adminPrimary));
    root.style.setProperty('--admin-primary-hover-color', adminPrimaryHover);
    root.style.setProperty('--admin-primary-hover-text-color', autoDesignContrastColor(adminPrimaryHover));
    root.style.setProperty('--admin-danger-color', adminDanger);
    root.style.setProperty('--admin-danger-text-color', autoDesignContrastColor(adminDanger));
    root.style.setProperty('--admin-danger-hover-color', adminDangerHover);
    root.style.setProperty('--admin-danger-hover-text-color', autoDesignContrastColor(adminDangerHover));
    root.style.setProperty('--admin-warning-color', adminWarning);
    root.style.setProperty('--admin-warning-text-color', autoDesignContrastColor(adminWarning));
    root.style.setProperty('--admin-favorite-color', adminFavorite);

    // Responsive media query overrides
    let mediaEl = document.getElementById('responsive-media-css');
    const mediaCss = buildResponsiveMediaStyles();
    if (mediaCss) {
        if (!mediaEl) {
            mediaEl = document.createElement('style');
            mediaEl.id = 'responsive-media-css';
            document.head.appendChild(mediaEl);
        }
        mediaEl.textContent = mediaCss;
    } else if (mediaEl) {
        mediaEl.textContent = '';
    }

}

async function loadDesignSettings() {
    try {
        const templatePageDesignPath = getTemplatePageDesignPath();
        if (templatePageDesignPath) {
            const result = await api.getPageTemplateDesignState(templatePageDesignPath);
            const currentPayload = result?.current && typeof result.current === "object" ? result.current : {};
            const publishedPayload = result?.published && typeof result.published === "object" ? result.published : {};
            state.design = mapBackendToFrontendDesign(currentPayload);
            setDesignFontStylesheetUrls(currentPayload?.font_stylesheet_urls || []);
            syncCustomBaseColorsFromAdminConfig();
            state.designId = `template:${result?.path || templatePageDesignPath}`;
            state.templatePageDesignMeta = {
                path: String(result?.path || templatePageDesignPath || ""),
                updatedAt: result?.updated_at || null,
                publishedAt: result?.published_at || null,
                initializedFromGlobalVersionId: result?.initialized_from_global_version_id || null,
            };
            setTemplatePagePublishedDesignFromBackend(publishedPayload);
            state.designRevisionStatus = {
                enabled: true,
                canUndo: false,
                canRedo: false,
                lastSavedBy: "template draft",
                lastSavedAt: result?.updated_at || null,
            };
            state.designDirty = false;
            state._designSnapshot = JSON.stringify(state.design);
            applyDesignCSS();
            logDebug("loadDesignSettings.success", { scope: "template_page", path: templatePageDesignPath });
            return;
        }

        const result = await api.getDesignSettings();
        state.design = mapBackendToFrontendDesign(result);
        setDesignFontStylesheetUrls(result?.font_stylesheet_urls || []);
        syncCustomBaseColorsFromAdminConfig();
        state.designId = result.id;
        state.templatePageDesignMeta = null;
        state.templatePagePublishedDesign = null;
        state.designDirty = false;
        state._designSnapshot = JSON.stringify(state.design);
        applyDesignCSS();
        await refreshDesignRevisionStatus();
        logDebug("loadDesignSettings.success", { id: result.id });
    } catch (err) {
        logDebug("loadDesignSettings.error", { error: err.message });
        console.error("Failed to load design settings:", err);
    }
}

async function loadGlobalDesignIntoTemplateDraft() {
    const templatePageDesignPath = getTemplatePageDesignPath();
    if (!templatePageDesignPath) {
        return false;
    }

    const globalDesign = await api.getDesignSettings();
    const nextDesign = mapBackendToFrontendDesign(globalDesign || {});
    const backendData = mapDesignToBackendFull(nextDesign);
    if (Array.isArray(globalDesign?.font_stylesheet_urls)) {
        backendData.font_stylesheet_urls = [...globalDesign.font_stylesheet_urls];
    }

    const result = await api.updatePageTemplateDesignCurrent(templatePageDesignPath, backendData);
    const currentPayload = result?.current && typeof result.current === "object"
        ? result.current
        : backendData;
    const publishedPayload = result?.published && typeof result.published === "object"
        ? result.published
        : null;

    state.design = mapBackendToFrontendDesign(currentPayload);
    setDesignFontStylesheetUrls(currentPayload?.font_stylesheet_urls || globalDesign?.font_stylesheet_urls || []);
    syncCustomBaseColorsFromAdminConfig();
    state.designId = `template:${result?.path || templatePageDesignPath}`;
    const publishedAtRaw = result?.published_at ?? null;
    const persistedPublishedAt = state.templatePageDesignMeta?.publishedAt ?? null;
    state.templatePageDesignMeta = {
        path: String(result?.path || templatePageDesignPath || ""),
        updatedAt: result?.updated_at || new Date().toISOString(),
        publishedAt: publishedAtRaw != null ? publishedAtRaw : persistedPublishedAt,
        initializedFromGlobalVersionId:
            state.templatePageDesignMeta?.initializedFromGlobalVersionId || null,
    };
    if (publishedPayload) {
        setTemplatePagePublishedDesignFromBackend(publishedPayload);
    }
    state.designRevisionStatus = {
        enabled: true,
        canUndo: false,
        canRedo: false,
        lastSavedBy: "template draft",
        lastSavedAt: result?.updated_at || null,
    };
    state._designSnapshot = JSON.stringify(state.design);
    state.designDirty = false;
    applyDesignCSS();
    logDebug("loadGlobalDesignIntoTemplateDraft.success", { path: templatePageDesignPath });
    return true;
}

function normalizePublicColorConfig(rawConfig) {
    if (!rawConfig || typeof rawConfig !== "object") return null;
    const parameters = rawConfig.parameters && typeof rawConfig.parameters === "object"
        ? rawConfig.parameters
        : {};
    const colorLinks = rawConfig.colorLinks && typeof rawConfig.colorLinks === "object"
        ? rawConfig.colorLinks
        : rawConfig.color_links && typeof rawConfig.color_links === "object"
            ? rawConfig.color_links
            : {};
    const baseColorHighContrast = rawConfig.baseColorHighContrast && typeof rawConfig.baseColorHighContrast === "object"
        ? rawConfig.baseColorHighContrast
        : rawConfig.base_color_high_contrast && typeof rawConfig.base_color_high_contrast === "object"
            ? rawConfig.base_color_high_contrast
            : {};
    const colorVariations = rawConfig.colorVariations && typeof rawConfig.colorVariations === "object"
        ? rawConfig.colorVariations
        : rawConfig.color_variations && typeof rawConfig.color_variations === "object"
            ? rawConfig.color_variations
            : {};
    const responsive = normalizeResponsiveConfig(rawConfig.responsive);

    if (
        Object.keys(parameters).length === 0
        && Object.keys(colorLinks).length === 0
        && Object.keys(baseColorHighContrast).length === 0
        && Object.keys(colorVariations).length === 0
        && !rawConfig.responsive
    ) {
        return null;
    }

    return {
        __publicColorContext: true,
        parameters,
        colorLinks,
        baseColorHighContrast,
        colorVariations,
        responsive,
    };
}

function resolvePublicColorConfigPayload(payload) {
    if (!payload || typeof payload !== "object") return null;
    if (payload.public_color_config) return payload.public_color_config;
    return payload.publicColorConfig;
}

function applyPublicColorConfig(payload) {
    const publicColorConfig = normalizePublicColorConfig(
        resolvePublicColorConfigPayload(payload)
    );
    if (!publicColorConfig) return false;

    const existing = state.adminDesignConfig;
    const hasPrivateAdminConfig = Boolean(
        existing
        && typeof existing === "object"
        && existing.__publicColorContext !== true
        && (Array.isArray(existing.sectionOrder) || Array.isArray(existing.buttonInstances))
    );

    if (hasPrivateAdminConfig && (state.canDesign || state.canAdminDesign)) {
        return false;
    }

    state.adminDesignConfig = publicColorConfig;
    return true;
}

function applyPublicDesignSettings(payload) {
    if (!payload || typeof payload !== "object") {
        return;
    }
    state.design = mapBackendToFrontendDesign(payload);
    setDesignFontStylesheetUrls(payload?.font_stylesheet_urls || []);
    const publicColorConfigApplied = applyPublicColorConfig(payload);
    syncCustomBaseColorsFromAdminConfig();
    if (publicColorConfigApplied) {
        applyColorLinksFromConfig();
    }
    state.designId = payload.id || state.designId;
    state.templatePagePublishedDesign = null;
    state.designDirty = false;
    state._designSnapshot = JSON.stringify(state.design);
    applyDesignCSS();
}

// Design revision status
async function refreshDesignRevisionStatus() {
    try {
        const templatePageDesignPath = getTemplatePageDesignPath();
        if (templatePageDesignPath) {
            const result = await api.getPageTemplateDesignState(templatePageDesignPath);
            state.designRevisionStatus = {
                enabled: true,
                canUndo: false,
                canRedo: false,
                lastSavedBy: "template draft",
                lastSavedAt: result?.updated_at || null,
            };
            state.templatePageDesignMeta = {
                path: String(result?.path || templatePageDesignPath || ""),
                updatedAt: result?.updated_at || null,
                publishedAt: result?.published_at || null,
                initializedFromGlobalVersionId: result?.initialized_from_global_version_id || null,
            };
            if (Object.prototype.hasOwnProperty.call(result || {}, "published")) {
                setTemplatePagePublishedDesignFromBackend(result.published);
            }
            return;
        }
        const status = await api.getDesignRevisionStatus();
        state.designRevisionStatus = {
            enabled: status.enabled !== false,
            canUndo: status.can_undo,
            canRedo: status.can_redo,
            lastSavedBy: status.last_saved_by || null,
            lastSavedAt: status.last_saved_at || null,
        };
    } catch (err) {
        console.error("Failed to get design revision status:", err);
    }
}

async function undoDesignChange() {
    if (getTemplatePageDesignPath()) {
        logDebug("undoDesign.skip", { scope: "template_page" });
        return false;
    }
    try {
        const result = await api.undoDesign();
        state.design = mapBackendToFrontendDesign(result);
        setDesignFontStylesheetUrls(result?.font_stylesheet_urls || []);
        applyDesignCSS();
        await refreshDesignRevisionStatus();
        logDebug("undoDesign.success");
        return true;
    } catch (err) {
        logDebug("undoDesign.error", { error: err.message });
        console.error("Failed to undo design:", err);
        return false;
    }
}

async function redoDesignChange() {
    if (getTemplatePageDesignPath()) {
        logDebug("redoDesign.skip", { scope: "template_page" });
        return false;
    }
    try {
        const result = await api.redoDesign();
        state.design = mapBackendToFrontendDesign(result);
        setDesignFontStylesheetUrls(result?.font_stylesheet_urls || []);
        applyDesignCSS();
        await refreshDesignRevisionStatus();
        logDebug("redoDesign.success");
        return true;
    } catch (err) {
        logDebug("redoDesign.error", { error: err.message });
        console.error("Failed to redo design:", err);
        return false;
    }
}

function getUnsavedDesignChanges() {
    if (!state.designDirty || !state._designSnapshot) return [];
    try {
        const snapshot = JSON.parse(state._designSnapshot);
        const changes = [];
        for (const [key, val] of Object.entries(state.design)) {
            if (JSON.stringify(val) !== JSON.stringify(snapshot[key])) {
                changes.push(key);
            }
        }
        return changes;
    } catch {
        return [];
    }
}

const SECTION_LABELS = {
    layout: 'Layout',
    fonts: 'Fonts',
    colors: 'Colors',
    sections: 'Sections',
    buttons: 'Buttons',
    header: 'Header',
};

function getGroupedUnsavedDesignChanges() {
    const changedKeys = getUnsavedDesignChanges();
    if (changedKeys.length === 0) return {};

    const params = state.adminDesignConfig?.parameters || {};
    const groups = {};

    for (const key of changedKeys) {
        if (key === 'buttonTypeStyles') {
            const section = 'buttons';
            const label = SECTION_LABELS[section];
            if (!groups[label]) groups[label] = [];
            groups[label].push('Button type styles');
            continue;
        }

        const cfg = params[key];
        const section = cfg?.section || _guessSection(key);
        const sectionLabel = SECTION_LABELS[section] || section || 'Other';
        const paramLabel = cfg?.label || _humanize(key);

        if (!groups[sectionLabel]) groups[sectionLabel] = [];
        groups[sectionLabel].push(paramLabel);
    }

    return groups;
}

function _guessSection(key) {
    if (key.startsWith('header') || key.startsWith('body') || key.startsWith('link')) return 'fonts';
    if (key.startsWith('hero')) return 'header';
    if (key.startsWith('button')) return 'buttons';
    if (key.startsWith('sectionBg') || key.startsWith('hardBox')) return 'sections';
    if (key.startsWith('section') || key === 'globalCustomCss') return 'sections';
    if (key === 'fullWidth' || key.startsWith('outer') || key.startsWith('content')) return 'layout';
    if (key.endsWith('Color')) return 'colors';
    return 'other';
}

function _humanize(key) {
    return key.replace(/([A-Z])/g, ' $1').replace(/^./, s => s.toUpperCase()).trim();
}

let _unsavedChangesDialogFn = null;

function registerUnsavedChangesDialog(showFn) {
    _unsavedChangesDialogFn = showFn;
}

async function confirmUnsavedDesignChanges() {
    const groups = getGroupedUnsavedDesignChanges();
    if (Object.keys(groups).length === 0) return 'discard';
    if (_unsavedChangesDialogFn) {
        const result = await _unsavedChangesDialogFn(groups);
        if (result) return result;
    }
    const msg = Object.entries(groups)
        .map(([sec, items]) => `${sec}: ${items.join(', ')}`)
        .join('\n');
    return window.confirm(`Unsaved design changes:\n\n${msg}\n\nLeave without saving?`) ? 'discard' : 'cancel';
}

// -------------------------
// Admin Design Config
// -------------------------

async function loadAdminDesignConfig() {
    try {
        const result = await api.getAdminDesignConfig();
        normalizeBaseColorSubsections(result);
        normalizeTypographySubsections(result);
        normalizeDesignPanelSectionOrder(result);
        result.responsive = normalizeResponsiveConfig(result?.responsive);
        state.adminDesignConfig = result;
        syncCustomBaseColorsFromAdminConfig();
        applyColorLinksFromConfig();
        applyDesignCSS();
        logDebug("loadAdminDesignConfig.success");
    } catch (err) {
        logDebug("loadAdminDesignConfig.error", { error: err.message });
        console.error("Failed to load admin design config:", err);
    }
}

function normalizeBaseColorSubsections(config) {
    const params = config?.parameters;
    if (!params || typeof params !== "object") return;
    for (const param of Object.values(params)) {
        if (param?.type !== "color" || !param?.isBase) continue;
        if (param.subsection !== BASE_VARS_SUBSECTION) {
            param.subsection = BASE_VARS_SUBSECTION;
        }
    }
}

const DESIGN_PANEL_SECTION_ORDER = ["header", "layout", "sections", "colors", "buttons", "fonts", "versions", "customCss"];

function reorderKnownItems(items, preferred) {
    if (!Array.isArray(items)) return [...preferred];
    const preferredSet = new Set(preferred);
    const seen = new Set();
    const current = items.filter((item) => typeof item === "string");
    const currentSet = new Set(current);
    const ordered = [];
    for (const item of preferred) {
        if (!currentSet.has(item) || seen.has(item)) continue;
        seen.add(item);
        ordered.push(item);
    }
    for (const item of current) {
        if (preferredSet.has(item) || seen.has(item)) continue;
        seen.add(item);
        ordered.push(item);
    }
    return ordered;
}

function normalizeDesignPanelSectionOrder(config) {
    if (!config || typeof config !== "object") return;
    config.sectionOrder = reorderKnownItems(config.sectionOrder, DESIGN_PANEL_SECTION_ORDER);
}

function normalizeTypographySubsections(config) {
    const params = config?.parameters;
    if (!params || typeof params !== "object") return;

    const setDefaultSubsection = (key, subsection, legacyValues) => {
        const param = params[key];
        if (!param || typeof param !== "object") return;
        const current = param.subsection ?? null;
        if (current === subsection || legacyValues.includes(current)) {
            param.subsection = subsection;
        }
    };

    for (const key of ["headerFontFamily", "headerTextDecoration", "headingLinearScaling"]) {
        setDefaultSubsection(key, "Headings", [null, "", "Headings (h1 – h6)"]);
    }
    for (const key of ["bodyFontFamily", "bodyFontWeight", "bodyLetterSpacing", "bodyLineHeight"]) {
        setDefaultSubsection(key, "Paragraph", [null, "", "Body Text", "Typography"]);
    }
    for (const key of ["heroTitleColor", "heroSubtitleColor"]) {
        setDefaultSubsection(key, "Header Titles", [null, "", "text header", "Text Header", "Header Text", "Hero Titles"]);
    }
    for (const key of ["sidebarBgColor", "sidebarItemColor", "sidebarItemHoverColor"]) {
        setDefaultSubsection(key, "Menus", [null, "", "Sidebar"]);
    }
    for (const key of ["hardBoxShadowEnabled", "hardBoxShadowOffsetSource", "hardBoxShadowOffsetCustom", "hardBoxShadowBrightness"]) {
        setDefaultSubsection(key, "Hardbox Shadow", [null, "", "Hard Box-Shadow"]);
    }
}

function syncCustomBaseColorsFromAdminConfig() {
    const params = state.adminDesignConfig?.parameters;
    if (!params || typeof params !== "object") return;
    for (const [key, cfg] of Object.entries(params)) {
        if (key in DEFAULT_DESIGN) continue;
        if (cfg?.type !== "color" || !cfg?.isBase) continue;
        const rawDefault = cfg?.default;
        if (typeof rawDefault !== "string") continue;
        const normalized = rawDefault.trim();
        if (!normalized) continue;
        const current = state.design?.[key];
        if (current !== undefined && current !== null && String(current).trim() !== "") {
            continue;
        }
        state.design[key] = normalized;
    }
}

function resolveBaseColorFromAdminConfig(baseKey) {
    if (!baseKey) return null;
    const fromDesign = state.design?.[baseKey];
    if (fromDesign !== undefined && fromDesign !== null && String(fromDesign).trim() !== "") {
        return fromDesign;
    }
    const fromParamDefault = state.adminDesignConfig?.parameters?.[baseKey]?.default;
    if (fromParamDefault !== undefined && fromParamDefault !== null && String(fromParamDefault).trim() !== "") {
        return fromParamDefault;
    }
    return null;
}

function applyColorLinksFromConfig() {
    const links = state.adminDesignConfig?.colorLinks;
    if (!links) return;
    for (const [colorKey, baseKey] of Object.entries(links)) {
        if (!Object.prototype.hasOwnProperty.call(state.design || {}, colorKey)) continue;
        if (baseKey === 'transparent') {
            state.design[colorKey] = 'transparent';
        } else if (baseKey === 'highContrast') {
            state.design[colorKey] = '__high_contrast__';
        } else {
            const resolved = resolveBaseColorFromAdminConfig(baseKey);
            if (resolved !== null) {
                state.design[colorKey] = resolved;
            }
        }
    }
    applyDesignCSS();
}

// -------------------------
// Section Design Overrides
// -------------------------

function openSectionDesignPanel(sectionKey) {
    if (state.pageTemplateStyleLock && !api.isTemplateBuilderContextActive?.()) {
        logDebug("openSectionDesignPanel.blocked", { sectionKey, reason: "template_style_lock" });
        return;
    }
    state.activeSectionDesignKey = sectionKey;
    logDebug("openSectionDesignPanel", { sectionKey });
    if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('ssc:open-design-override', { detail: { sectionKey } }));
    }
}

function setPageTemplateStyleContext(context = null) {
    const next = context && typeof context === "object" ? context : {};
    const ref = String(next.ref || "").trim();
    const linked = next.linked === true || Boolean(ref);
    const locked = linked && next.locked === true;
    state.pageTemplateStyleRef = ref || null;
    state.pageTemplateStyleLinked = linked;
    state.pageTemplateStyleLock = locked;
}

async function saveSectionDesignOverrides(sectionKey, pageSlug, options = {}) {
    if (state.pageTemplateStyleLock && !api.isTemplateBuilderContextActive?.()) {
        logDebug("saveSectionDesignOverrides.blocked", { sectionKey, reason: "template_style_lock" });
        return;
    }
    const slug = pageSlug || state.pageSlug || "landing";
    const revertedFromSavedAt = options?.revertedFromSavedAt || null;

    if (sectionKey === '__header__') {
        if (!state.headerId) return;
        const overrides = normalizeSectionDesignOverridesForBackend(
            state.sectionDesignOverrides['__header__'] || null
        );
        try {
            await api.updateHeaderDesignOverrides(slug, overrides, { revertedFromSavedAt });
            await refreshHeaderRevisionStatus();
            logDebug("saveSectionDesignOverrides.success", { sectionKey: '__header__' });
        } catch (err) {
            logDebug("saveSectionDesignOverrides.error", { sectionKey: '__header__', error: err.message });
            console.error("Failed to save header design overrides:", err);
        }
        return;
    }

    const sectionId = state.sectionIds?.[sectionKey];
    if (!sectionId) return;
    let overrides = state.sectionDesignOverrides[sectionKey] || null;
    if (overrides && typeof overrides === "object") {
        // Section custom CSS is transient/snippet-based and should never be persisted
        // as design overrides.
        const cleaned = { ...overrides };
        if (Object.prototype.hasOwnProperty.call(cleaned, "customCss")) {
            delete cleaned.customCss;
        }
        const keys = Object.keys(cleaned);
        const hasOnlyInactiveFlag = keys.length === 1 && keys[0] === "_active";
        overrides = (keys.length === 0 || hasOnlyInactiveFlag) ? null : cleaned;
    }
    overrides = normalizeSectionDesignOverridesForBackend(overrides);
    try {
        await api.updateSectionDesignOverrides(slug, sectionId, overrides, { revertedFromSavedAt });
        await refreshRevisionStatus(sectionKey);
        logDebug("saveSectionDesignOverrides.success", { sectionKey });
    } catch (err) {
        logDebug("saveSectionDesignOverrides.error", { sectionKey, error: err.message });
        console.error(`Failed to save design overrides for ${sectionKey}:`, err);
    }
}

/**
 * Compute the background color for a section at a given index based on the global pattern.
 * Returns null if no pattern is active (use default section background).
 */
function computeSectionBgColor(visibleIndex, totalVisible, sectionKey) {
    const pattern = state.design.sectionBgPattern;
    if (pattern === 'none' || !pattern) return null;
    
    const c1 = applyDesignColorVariation('sectionBgColor1', state.design.sectionBgColor1 || '#ffffff');
    const c2 = applyDesignColorVariation('sectionBgColor2', state.design.sectionBgColor2 || '#f0f0f0');
    // Read pinned keys from page-specific landingLayout (not global design)
    const pinnedStartKey = state.landingLayout?.sectionBgPinnedStartKey || '';
    const pinnedEndKey = state.landingLayout?.sectionBgPinnedEndKey || '';

    if (pattern === 'alternating') {
        return visibleIndex % 2 === 0 ? c1 : c2;
    }
    
    // Resolve pin indices for gradient patterns
    const visibleKeys = _getVisibleKeys();
    const startIdx = pinnedStartKey ? visibleKeys.indexOf(pinnedStartKey) : -1;
    const endIdx = pinnedEndKey ? visibleKeys.indexOf(pinnedEndKey) : -1;

    if (pattern === 'gradient') {
        if (totalVisible <= 1) return c1;
        // Clamp: everything before start → start color, everything after end → end color
        if (startIdx >= 0 && visibleIndex < startIdx) return c1;
        if (endIdx >= 0 && visibleIndex > endIdx) return c2;
        const effStart = startIdx >= 0 ? startIdx : 0;
        const effEnd = endIdx >= 0 ? endIdx : totalVisible - 1;
        if (effEnd <= effStart) return c1;
        const t = (visibleIndex - effStart) / (effEnd - effStart);
        return interpolateColor(c1, c2, Math.max(0, Math.min(1, t)));
    }
    
    if (pattern === 'gradient_shuffled') {
        if (totalVisible <= 1) return c1;
        // Pinned start/end get fixed colors, rest shuffled
        if (pinnedStartKey && sectionKey === pinnedStartKey) return c1;
        if (pinnedEndKey && sectionKey === pinnedEndKey) return c2;

        const cacheKey = `gs_${c1}_${c2}_${totalVisible}_${pinnedStartKey}_${pinnedEndKey}`;
        if (_shuffledCache.key !== cacheKey) {
            const steps = [];
            for (let i = 0; i < totalVisible; i++) {
                steps.push(interpolateColor(c1, c2, i / (totalVisible - 1)));
            }
            // Remove the fixed slots from shuffle pool
            const fixedSlots = new Set();
            if (startIdx >= 0) fixedSlots.add(startIdx);
            if (endIdx >= 0) fixedSlots.add(endIdx);
            const shuffleable = steps.filter((_, i) => !fixedSlots.has(i));
            for (let i = shuffleable.length - 1; i > 0; i--) {
                const j = (i * 2654435761 + totalVisible) % (i + 1);
                [shuffleable[i], shuffleable[j]] = [shuffleable[j], shuffleable[i]];
            }
            let si = 0;
            const result = steps.map((s, i) => {
                if (fixedSlots.has(i)) return s;
                return shuffleable[si++];
            });
            if (startIdx >= 0) result[startIdx] = c1;
            if (endIdx >= 0) result[endIdx] = c2;
            _shuffledCache = { key: cacheKey, steps: result };
        }
        return _shuffledCache.steps[visibleIndex] || c1;
    }

    // Alpha gradient patterns
    if (pattern === 'alpha_gradient' || pattern === 'alpha_gradient_shuffled') {
        const baseBg = state.design.sectionBackgroundColor || state.design.backgroundSecondaryColor || '#ffffff';
        const o1 = state.design.sectionBgOpacity1 ?? 1.0;
        const o2 = state.design.sectionBgOpacity2 ?? 0.3;

        if (totalVisible <= 1) return hexToRgba(baseBg, o1);

        if (pattern === 'alpha_gradient') {
            // Clamp before start / after end
            if (startIdx >= 0 && visibleIndex < startIdx) return hexToRgba(baseBg, o1);
            if (endIdx >= 0 && visibleIndex > endIdx) return hexToRgba(baseBg, o2);
            const effStart = startIdx >= 0 ? startIdx : 0;
            const effEnd = endIdx >= 0 ? endIdx : totalVisible - 1;
            if (effEnd <= effStart) return hexToRgba(baseBg, o1);
            const t = (visibleIndex - effStart) / (effEnd - effStart);
            return hexToRgba(baseBg, o1 + (o2 - o1) * Math.max(0, Math.min(1, t)));
        }

        // alpha_gradient_shuffled: pinned start/end fixed, rest shuffled
        if (pinnedStartKey && sectionKey === pinnedStartKey) return hexToRgba(baseBg, o1);
        if (pinnedEndKey && sectionKey === pinnedEndKey) return hexToRgba(baseBg, o2);

        const cacheKey = `ags_${baseBg}_${o1}_${o2}_${totalVisible}_${pinnedStartKey}_${pinnedEndKey}`;
        if (_shuffledCache.key !== cacheKey) {
            const steps = [];
            for (let i = 0; i < totalVisible; i++) {
                const t = i / (totalVisible - 1);
                steps.push(hexToRgba(baseBg, o1 + (o2 - o1) * t));
            }
            const fixedSlots = new Set();
            if (startIdx >= 0) fixedSlots.add(startIdx);
            if (endIdx >= 0) fixedSlots.add(endIdx);
            const shuffleable = steps.filter((_, i) => !fixedSlots.has(i));
            for (let i = shuffleable.length - 1; i > 0; i--) {
                const j = (i * 2654435761 + totalVisible) % (i + 1);
                [shuffleable[i], shuffleable[j]] = [shuffleable[j], shuffleable[i]];
            }
            let si = 0;
            const result = steps.map((s, i) => {
                if (fixedSlots.has(i)) return s;
                return shuffleable[si++];
            });
            if (startIdx >= 0) result[startIdx] = hexToRgba(baseBg, o1);
            if (endIdx >= 0) result[endIdx] = hexToRgba(baseBg, o2);
            _shuffledCache = { key: cacheKey, steps: result };
        }
        return _shuffledCache.steps[visibleIndex] || hexToRgba(baseBg, o1);
    }
    
    return null;
}

function _getVisibleKeys() {
    const order = state.landingLayout?.order || [];
    const hidden = state.landingLayout?.hidden || {};
    return order.filter(k => !hidden[k]);
}

function hexToRgba(hex, alpha) {
    const c = hex.replace('#', '');
    const r = parseInt(c.substring(0, 2), 16);
    const g = parseInt(c.substring(2, 4), 16);
    const b = parseInt(c.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${Math.max(0, Math.min(1, alpha)).toFixed(2)})`;
}

let _shuffledCache = { key: null, steps: [] };

function parseColorToRgb(color) {
    if (typeof color !== 'string') return null;
    const c = color.trim();
    if (!c) return null;

    if (c.startsWith('#')) {
        const raw = c.slice(1);
        if (/^[0-9a-fA-F]{3,4}$/.test(raw)) {
            const r = parseInt(raw[0] + raw[0], 16);
            const g = parseInt(raw[1] + raw[1], 16);
            const b = parseInt(raw[2] + raw[2], 16);
            return { r, g, b };
        }
        if (/^[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/.test(raw)) {
            const r = parseInt(raw.slice(0, 2), 16);
            const g = parseInt(raw.slice(2, 4), 16);
            const b = parseInt(raw.slice(4, 6), 16);
            return { r, g, b };
        }
        return null;
    }

    const rgbMatch = c.match(/^rgba?\(([^)]+)\)$/i);
    if (!rgbMatch) return null;
    const parts = rgbMatch[1].split(',').map((v) => Number.parseFloat(v.trim()));
    if (parts.length < 3 || parts.slice(0, 3).some((v) => !Number.isFinite(v))) return null;
    return {
        r: Math.min(255, Math.max(0, Math.round(parts[0]))),
        g: Math.min(255, Math.max(0, Math.round(parts[1]))),
        b: Math.min(255, Math.max(0, Math.round(parts[2]))),
    };
}

function adjustBrightness(color, percent, fallbackColor = '#ffffff') {
    const rgb = parseColorToRgb(color) || parseColorToRgb(fallbackColor) || { r: 255, g: 255, b: 255 };
    const { r, g, b } = rgb;
    const adjust = (ch) => {
        if (percent > 0) return Math.round(ch + (255 - ch) * (percent / 100));
        return Math.round(ch * (1 + percent / 100));
    };
    const nr = Math.min(255, Math.max(0, adjust(r)));
    const ng = Math.min(255, Math.max(0, adjust(g)));
    const nb = Math.min(255, Math.max(0, adjust(b)));
    return `#${nr.toString(16).padStart(2, '0')}${ng.toString(16).padStart(2, '0')}${nb.toString(16).padStart(2, '0')}`;
}

function computeHardBoxShadow(sectionBgColor, overrides) {
    const d = state.design;

    // Per-section override: 'off' disables, 'on' forces on with local settings
    const mode = overrides?.hardBoxShadowMode;
    if (mode === 'off') return null;
    // Check responsive value for hardBoxShadowEnabled during simulation
    const hardBoxShadowEnabled = getResponsiveDiscreteValue('hardBoxShadowEnabled', d.hardBoxShadowEnabled);
    if (mode !== 'on' && !hardBoxShadowEnabled) return null;

    const brightness = (mode === 'on' && overrides?.hardBoxShadowBrightness != null)
        ? overrides.hardBoxShadowBrightness
        : (d.hardBoxShadowBrightness ?? -15);

    const offsetSource = (mode === 'on' && overrides?.hardBoxShadowOffsetSource)
        ? overrides.hardBoxShadowOffsetSource
        : (d.hardBoxShadowOffsetSource || 'padding');

    const offsetCustom = (mode === 'on' && overrides?.hardBoxShadowOffsetCustom != null)
        ? overrides.hardBoxShadowOffsetCustom
        : (d.hardBoxShadowOffsetCustom ?? 18);

    let offset;
    if (offsetSource === 'spacing') offset = d.sectionSpacing ?? 14;
    else if (offsetSource === 'custom') offset = offsetCustom;
    else offset = d.sectionPadding ?? 18;

    const fallbackSectionBg = d.sectionBackgroundColor || d.backgroundSecondaryColor || '#ffffff';
    const bgColor = sectionBgColor || fallbackSectionBg;
    const shadowColor = adjustBrightness(bgColor, brightness, fallbackSectionBg);
    return `${offset}px ${offset}px 0 ${shadowColor}`;
}

function interpolateColor(hex1, hex2, t) {
    const r1 = parseInt(hex1.slice(1, 3), 16);
    const g1 = parseInt(hex1.slice(3, 5), 16);
    const b1 = parseInt(hex1.slice(5, 7), 16);
    const r2 = parseInt(hex2.slice(1, 3), 16);
    const g2 = parseInt(hex2.slice(3, 5), 16);
    const b2 = parseInt(hex2.slice(5, 7), 16);
    const r = Math.round(r1 + (r2 - r1) * t);
    const g = Math.round(g1 + (g2 - g1) * t);
    const b = Math.round(b1 + (b2 - b1) * t);
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

// -------------------------
// Export
// -------------------------

export function useStore() {
    return {
        state,
        t,
        localizedText,
        logDebug,

        initPageState,
        setPageSlug,
        setCurrentPageStatusMeta,
        updateCurrentPageStatus,
        setPageTemplateStyleContext,
        fetchFaqSharedData,
        saveFaqSharedData,
        applyFaqSharedData,
        fetchBlogData,
        fetchProgramSharedData,
        saveProgramSharedData,
        saveProgramSharedGig,
        applyProgramSharedData,
        applyMediaFallbacks,
        updateSectionLimit,

        setLang,
        updateSection,
        saveSectionByKey,
        applyBackendSectionByKey,
        setSectionAdminActiveTab,
        upsertSectionAdminPinnedEditor,
        removeSectionAdminPinnedEditor,
        setSectionAdminPinnedActiveEditor,
        setSectionAdminPinnedSharedTab,
        setSectionAdminPinnedSharedHeightPx,
        setTickerItems,
        setFaqItems,
        toggleSectionHidden,
        setSectionOrder,
        setSectionStructure,
        setSectionWidth,
        setSectionDeviceVisibility,
        setSectionBgPinnedKey,
        
        // Undo/Redo
        refreshRevisionStatus,
        refreshHeaderRevisionStatus,
        undoSectionChange,
        redoSectionChange,
        applySectionRevisionPreview,
        undoHeaderChange,
        redoHeaderChange,
        
        // Design
        updateDesignSetting,
        saveDesignSettings,
        resetDesignSettings: resetDesignSettingsToDefaults,
        loadDesignSettings,
        loadGlobalDesignIntoTemplateDraft,
        applyPublicDesignSettings,
        applyDesignCSS,
        transformSectionToBackendFormat: transformToBackendFormat,
        undoDesignChange,
        redoDesignChange,
        loadAdminDesignConfig,
        getUnsavedDesignChanges,
        getGroupedUnsavedDesignChanges,
        registerUnsavedChangesDialog,
        confirmUnsavedDesignChanges,
        
        setSimulatedViewport,
        getEffectiveViewportDevice,
        updateViewportSize,
        setHideResponsiveUI,

        // Section design overrides
        openSectionDesignPanel,
        saveSectionDesignOverrides,
        computeSectionBgColor,
        computeHardBoxShadow,
        
        // Section data utilities (for use in page components)
        SECTION_TYPE_CONFIG,
        toCamelCase,
        toSnakeCase,
        convertKeysToCamel,
        convertKeysToSnake,
    };
}
