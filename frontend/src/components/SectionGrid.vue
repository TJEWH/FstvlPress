<template>
  <div class="content">
    <div class="container page-container">
      <div class="section-grid-frame">
        <div
          v-if="previewPayloadAvailable"
          class="section-grid-preview-stick"
          aria-live="polite"
        >
          <button
            class="section-grid-preview-button"
            :class="{ 'section-grid-preview-button--active': previewPayloadActive }"
            type="button"
            :disabled="previewPayloadButtonDisabled"
            :title="previewPayloadButtonTitle"
            @click="emit('preview-payload-click')"
          >
            <font-awesome-icon
              class="section-grid-preview-button__icon"
              :icon="previewPayloadActive ? faPause : faPlay"
            />
            <span class="section-grid-preview-button__label">{{ previewPayloadButtonLabel }}</span>
            <span
              v-if="previewPayloadActive && previewPayloadWarningCount"
              class="section-grid-preview-button__badge"
            >
              {{ previewPayloadWarningCount }}
            </span>
          </button>
        </div>

        <div class="grid" :class="{ 'border-collapse': shouldCollapsesBorders }">
          <section
            v-for="entry in renderedEntries"
            :key="entry.id"
            class="grid-item"
            :class="[
              entry.type === 'container' ? 'grid-container' : '',
              getSectionWidthClass(getEntryPrimaryKey(entry)),
              getDeviceVisibilityClasses(getEntryPrimaryKey(entry)),
            ]"
            :style="getEntryShellStyle(entry)"
          >
            <TransformedImage
              v-if="textImageGridBackgroundsByKey[getEntryPrimaryKey(entry)]"
              class="grid-item-background-media"
              :src="textImageGridBackgroundsByKey[getEntryPrimaryKey(entry)].src"
              alt=""
              :style="textImageGridBackgroundsByKey[getEntryPrimaryKey(entry)].style"
              :zoom="textImageGridBackgroundsByKey[getEntryPrimaryKey(entry)].zoom"
              :focal-x="textImageGridBackgroundsByKey[getEntryPrimaryKey(entry)].focalX"
              :focal-y="textImageGridBackgroundsByKey[getEntryPrimaryKey(entry)].focalY"
              :rotation="textImageGridBackgroundsByKey[getEntryPrimaryKey(entry)].rotation"
              :responsive-variants="textImageGridBackgroundsByKey[getEntryPrimaryKey(entry)].responsiveVariants"
              fit="cover"
              loading="lazy"
              decoding="async"
            />
            <template v-if="entry.type === 'container'">
              <template v-for="(memberKey, memberIndex) in entry.members" :key="memberKey">
                <div class="section-admin-tabs-host" :data-section-key="memberKey"></div>
                <div
                  class="grid-item-content"
                  :class="{
                    'grid-item-content--container-first': memberIndex === 0,
                    'grid-item-content--container-last': memberIndex === entry.members.length - 1,
                  }"
                  :data-section-key="memberKey"
                  :data-section-id="getSectionId(memberKey)"
                  :style="getSectionStyle(memberKey, visibleIndexByKey[memberKey] ?? 0)"
                >
                  <component
                    v-if="getComponent(memberKey)"
                    :is="getComponent(memberKey)"
                    :section-key="memberKey"
                    :section-data="getSectionData(memberKey)"
                  />
                  <div v-else class="card unknown-section">
                    <p class="unknown-hint">Unknown section type: {{ memberKey }}</p>
                  </div>
                </div>
              </template>
            </template>
            <template v-else>
              <div class="section-admin-tabs-host" :data-section-key="entry.key"></div>
              <div
                class="grid-item-content"
                :data-section-key="entry.key"
                :data-section-id="getSectionId(entry.key)"
                :style="getSectionStyle(entry.key, visibleIndexByKey[entry.key] ?? 0)"
              >
                <component
                  v-if="getComponent(entry.key)"
                  :is="getComponent(entry.key)"
                  :section-key="entry.key"
                  :section-data="getSectionData(entry.key)"
                />
                <div v-else class="card unknown-section">
                  <p class="unknown-hint">Unknown section type: {{ entry.key }}</p>
                </div>
              </div>
            </template>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from "vue";
import {
  faPause,
  faPlay,
} from "@fortawesome/free-solid-svg-icons";
import { useStore } from "../store/store.js";
import {
  TRANSPARENT_LINK_KEY,
  HIGH_CONTRAST_LINK_KEY,
  HIGH_CONTRAST_TOKEN,
  isBaseColorLinkKey,
  resolveLinkedColor,
  resolveHighContrastColorForBackground,
} from "../utils/colorLinkOptions.js";
import {
  applyColorVariation,
  normalizeColorVariation,
} from "../utils/colorVariations.js";
import {
  buildSectionContainerMaps,
  getContainerLeaderKey,
} from "../utils/sectionContainers.js";
import {
  buildCssSnippetsStyleText,
  buildSectionScopeSelector,
  scopeSectionCustomCss,
} from "../utils/cssSnippets.js";
import { convertKeysToCamel } from "../utils/caseConversion.js";
import { isSectionHiddenInPublicBecauseEmptyList } from "../utils/sectionVisibilityRules.js";
import TransformedImage from "./ui/TransformedImage.vue";

const props = defineProps({
  componentMap: { type: Object, required: true },
  keys: { type: Array, required: true },
  previewPayloadAvailable: { type: Boolean, default: false },
  previewPayloadActive: { type: Boolean, default: false },
  previewPayloadLoading: { type: Boolean, default: false },
  previewPayloadDisabled: { type: Boolean, default: false },
  previewPayloadWarnings: { type: Array, default: () => [] }
});

const emit = defineEmits(["preview-payload-click"]);

const { state, computeSectionBgColor, computeHardBoxShadow, getEffectiveViewportDevice } = useStore();
const SECTION_CUSTOM_CSS_STYLE_ID = "section-custom-css-overrides";
const OVERRIDE_KEY_ALIASES = {
  headingColor: ["headerColor"],
  headerColor: ["headingColor"],
  paragraphColor: ["textColor"],
  textColor: ["paragraphColor"],
  bodyFontFamily: ["textFontFamily"],
  textFontFamily: ["bodyFontFamily"],
  bodyFontSize: ["textFontSize"],
  textFontSize: ["bodyFontSize"],
  bodyFontWeight: ["textFontWeight"],
  textFontWeight: ["bodyFontWeight"],
};

const previewPayloadWarnings = computed(() => (
  Array.isArray(props.previewPayloadWarnings)
    ? props.previewPayloadWarnings.map((warning) => String(warning || "").trim()).filter(Boolean)
    : []
));
const previewPayloadWarningCount = computed(() => previewPayloadWarnings.value.length);
const previewPayloadButtonDisabled = computed(() => (
  Boolean(props.previewPayloadDisabled) || Boolean(props.previewPayloadLoading)
));
const previewPayloadButtonLabel = computed(() => {
  return props.previewPayloadActive ? "Template" : "Preview";
});
const previewPayloadButtonTitle = computed(() => {
  if (!props.previewPayloadActive) return "Preview";
  if (!previewPayloadWarningCount.value) return "Template";
  return [
    `Template (${previewPayloadWarningCount.value} warning${previewPayloadWarningCount.value === 1 ? "" : "s"})`,
    ...previewPayloadWarnings.value,
  ].join("\n");
});

function getOverrideLookupKeys(paramKey) {
  return [paramKey, ...(OVERRIDE_KEY_ALIASES[paramKey] || [])];
}

function getOverrideRawValue(overrides, paramKey) {
  if (!overrides) return undefined;
  for (const key of getOverrideLookupKeys(paramKey)) {
    if (overrides[key] !== undefined) return overrides[key];
  }
  return undefined;
}

function getOverrideResponsiveEntry(overrides, paramKey) {
  if (!overrides?._responsiveValues) return null;
  for (const key of getOverrideLookupKeys(paramKey)) {
    if (overrides._responsiveValues[key] !== undefined) return overrides._responsiveValues[key];
  }
  return null;
}

function getOverrideResponsiveMode(overrides, paramKey) {
  if (!overrides?._responsiveModes) return undefined;
  for (const key of getOverrideLookupKeys(paramKey)) {
    if (overrides._responsiveModes[key] !== undefined) return overrides._responsiveModes[key];
  }
  return undefined;
}

// Helper to check if override has media mode responsive values
function hasMediaModeResponsive(ov, key) {
  if (!ov || !key) return false;
  const explicitMode = getOverrideResponsiveMode(ov, key);
  if (explicitMode !== undefined) {
    return explicitMode === "media";
  }
  const respVal = getOverrideResponsiveEntry(ov, key);
  if (respVal?.currentMode === 'media') return true;
  const media = respVal?.media;
  if (media && typeof media === 'object' && Object.keys(media).length > 0) return true;
  return false;
}

// Helper to get responsive override value for current device (simulation or real viewport)
function getResponsiveOverrideValue(overrides, paramKey, defaultValue) {
  const device = getEffectiveViewportDevice();
  const baseOverrideValue = getOverrideRawValue(overrides, paramKey);
  const baseValue = baseOverrideValue ?? defaultValue;
  
  if (device === 'desktop') return baseValue;
  
  if (hasMediaModeResponsive(overrides, paramKey)) {
    const respVal = getOverrideResponsiveEntry(overrides, paramKey);
    const deviceVal = respVal?.media?.[device];
    if (deviceVal !== undefined) return deviceVal;
  }
  
  return baseValue;
}

function getOverrideMapValue(overrides, mapKey, paramKey) {
  const map = overrides?.[mapKey];
  if (!map || typeof map !== "object") return undefined;
  for (const key of getOverrideLookupKeys(paramKey)) {
    if (map[key] !== undefined) return map[key];
  }
  return undefined;
}

function getGlobalColorVariation(paramKey) {
  const designMap = (state.design?.colorVariations && typeof state.design.colorVariations === "object")
    ? state.design.colorVariations
    : {};
  const adminMap = (state.adminDesignConfig?.colorVariations && typeof state.adminDesignConfig.colorVariations === "object")
    ? state.adminDesignConfig.colorVariations
    : {};
  for (const key of getOverrideLookupKeys(paramKey)) {
    if (Object.prototype.hasOwnProperty.call(designMap, key)) {
      return normalizeColorVariation(designMap[key]);
    }
  }
  for (const key of getOverrideLookupKeys(paramKey)) {
    if (Object.prototype.hasOwnProperty.call(adminMap, key)) {
      return normalizeColorVariation(adminMap[key]);
    }
  }
  return 100;
}

function getOverrideColorVariation(overrides, paramKey) {
  const raw = getOverrideMapValue(overrides, "_colorVariations", paramKey);
  if (raw !== undefined) return normalizeColorVariation(raw);
  return getGlobalColorVariation(paramKey);
}

function resolveOverrideColorBase(overrides, paramKey, { backgroundColor = null, backgroundBaseKey = null } = {}) {
  const rawColorValue = getResponsiveOverrideValue(overrides, paramKey, null);
  const linkKey = getOverrideMapValue(overrides, "_colorLinks", paramKey);
  const linkedValue = linkKey
    ? resolveLinkedColor(state.design, linkKey, state.adminDesignConfig?.parameters)
    : null;
  const colorValue = linkedValue ?? rawColorValue;
  if (colorValue === null || colorValue === undefined || colorValue === "") return null;
  if (colorValue === "transparent") return "transparent";
  if (colorValue === HIGH_CONTRAST_TOKEN || linkKey === HIGH_CONTRAST_LINK_KEY) {
    return contrastColor(
      backgroundColor || state.design.sectionBackgroundColor || "#ffffff",
      backgroundBaseKey || null
    );
  }
  return colorValue;
}

function resolveOverrideColorValue(overrides, paramKey, context = {}) {
  const resolvedBase = resolveOverrideColorBase(overrides, paramKey, context);
  if (resolvedBase == null) return null;
  return applyColorVariation(resolvedBase, getOverrideColorVariation(overrides, paramKey));
}

function resolveLinkedOrRawColor(rawValue, linkKey) {
  const linkedValue = linkKey
    ? resolveLinkedColor(state.design, linkKey, state.adminDesignConfig?.parameters)
    : null;
  return linkedValue ?? rawValue;
}

function isTransparentColorValue(value, linkKey = null) {
  return value === "transparent" || linkKey === TRANSPARENT_LINK_KEY;
}

function isHighContrastColorValue(value, linkKey = null) {
  return value === HIGH_CONTRAST_TOKEN || linkKey === HIGH_CONTRAST_LINK_KEY;
}

const shouldCollapsesBorders = computed(() => {
  const padding = state.design.sectionPadding ?? 18;
  const borderWidth = state.design.sectionBorderWidth ?? 0;
  return padding === 0 && borderWidth > 0;
});

const isPublicLikeView = computed(() => !state.isAdmin || state.previewMode);

function isPublicHiddenByEmptyContent(key) {
  if (!isPublicLikeView.value) return false;
  return isSectionHiddenInPublicBecauseEmptyList(
    key,
    state,
    getSectionData(key),
  );
}

const orderedKeys = computed(() => {
  const availableKeys = props.keys.filter((key) => !isPublicHiddenByEmptyContent(key));
  const order = state.landingLayout.order.filter((k) => availableKeys.includes(k));
  for (const k of availableKeys) if (!order.includes(k)) order.push(k);
  return order;
});

const containerMaps = computed(() =>
  buildSectionContainerMaps(
    orderedKeys.value,
    state.landingLayout?.structure || [],
    state.sectionIds || {},
  )
);

const visibleOrderedKeys = computed(() => {
  const hidden = state.landingLayout?.hidden || {};
  return containerMaps.value.flattenedKeys.filter((key) => {
    const containerId = containerMaps.value.sectionToContainerId?.[key];
    if (!containerId) return hidden[key] !== true;
    const members = containerMaps.value.containersById?.[containerId]?.members || [key];
    return !isContainerHidden(members, hidden);
  });
});

const visibleIndexByKey = computed(() => {
  const indexByKey = {};
  visibleOrderedKeys.value.forEach((key, index) => {
    indexByKey[key] = index;
  });
  return indexByKey;
});

const textImageGridBackgroundsByKey = computed(() => {
  const backgrounds = {};
  for (const key of visibleOrderedKeys.value) {
    const background = buildTextImageGridBackground(key);
    if (background) backgrounds[key] = background;
  }
  return backgrounds;
});

const renderedEntries = computed(() => {
  const hidden = state.landingLayout?.hidden || {};
  const entries = [];
  const nodes = Array.isArray(containerMaps.value.nodes) ? containerMaps.value.nodes : [];

  for (const node of nodes) {
    if (!node || typeof node !== "object") continue;
    if (node.type === "container") {
      const members = Array.isArray(node.members) ? node.members : [];
      if (!members.length) continue;
      if (isContainerHidden(members, hidden)) continue;
      entries.push({
        id: `container:${node.containerId}`,
        type: "container",
        containerId: node.containerId,
        members,
      });
      continue;
    }
    const key = String(node.key || "");
    if (!key || hidden[key] === true) continue;
    entries.push({
      id: `section:${key}`,
      type: "section",
      key,
    });
  }

  return entries;
});

function isContainerHidden(members, hidden) {
  const keys = Array.isArray(members) ? members : [];
  if (!keys.length) return true;
  return keys.some((key) => hidden?.[key] === true);
}

function getEntryPrimaryKey(entry) {
  if (!entry || typeof entry !== "object") return "";
  if (entry.type === "container") return Array.isArray(entry.members) ? (entry.members[0] || "") : "";
  return String(entry.key || "");
}

function normalizeSectionTypeForKey(key, data) {
  const meta = state.sectionMeta?.[key] && typeof state.sectionMeta[key] === "object"
    ? state.sectionMeta[key]
    : {};
  const rawType = data?.sectionType
    || data?.section_type
    || meta.sectionType
    || meta.section_type
    || "";
  const normalized = String(rawType || "").trim().toLowerCase().replace(/-/g, "_");
  if (normalized) return normalized;
  const rawKey = String(key || "").trim().toLowerCase();
  if (rawKey === "text_image" || rawKey.startsWith("text_image_")) return "text_image";
  return rawKey.split("_", 1)[0] || "";
}

function normalizeTextImageLayout(value) {
  return value === "background" ? "background" : "";
}

function normalizeUrlCandidate(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeReadObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const normalized = convertKeysToCamel(value);
  for (const [key, rawValue] of Object.entries(value)) {
    if (key.includes("_")) continue;
    if (rawValue !== undefined && rawValue !== null && rawValue !== "") {
      normalized[key] = rawValue;
    }
  }
  return normalized;
}

function clampNumber(value, fallback, min, max) {
  const raw = Number(value);
  if (!Number.isFinite(raw)) return fallback;
  return Math.max(min, Math.min(max, raw));
}

function buildTextImageGridBackground(key) {
  const data = normalizeReadObject(getSectionData(key));
  if (!data || normalizeSectionTypeForKey(key, data) !== "text_image") return null;
  if (normalizeTextImageLayout(data.imageLayout) !== "background") return null;

  const src = normalizeUrlCandidate(data.imageUrl);
  if (!src) return null;

  const responsiveVariants = Array.isArray(data.imageResponsiveVariants)
    ? data.imageResponsiveVariants
    : [];

  return {
    src,
    responsiveVariants,
    zoom: clampNumber(data.imageBgZoom, 1, 1, 4),
    focalX: clampNumber(data.imageBgFocalX, 50, 0, 100),
    focalY: clampNumber(data.imageBgFocalY, 50, 0, 100),
    rotation: clampNumber(data.imageBgRotation, 0, -180, 180),
    style: {
      opacity: String(clampNumber(data.imageBgOpacity, 0.72, 0, 1)),
    },
  };
}

function getOverrideUnit(overrides, paramKey, defaultUnit = "px") {
  for (const key of getOverrideLookupKeys(paramKey)) {
    const unit = overrides?._selectedUnits?.[key];
    if (unit !== undefined && unit !== null && unit !== "") return unit;
  }
  return defaultUnit;
}

function getEntryShellStyle(entry) {
  const primaryKey = getEntryPrimaryKey(entry);
  if (!primaryKey) return null;
  const visibleIndex = visibleIndexByKey.value[primaryKey] ?? 0;
  return getSectionStyle(primaryKey, visibleIndex);
}

// Computed property for device visibility to ensure reactivity
const deviceVisibilityMap = computed(() => state.landingLayout?.deviceVisibility || {});

/**
 * Get CSS class name for section width ratio
 * Maps n/d to a class name like "w-half", "w-twoThirds", etc.
 * During mobile/tablet simulation, returns 'w-simulated-full' to force 100% width
 */
function getSectionWidthClass(key) {
  // During mobile/tablet simulation, force full width
  const sim = state.simulatedViewport;
  if (sim === 'mobile' || sim === 'tablet') {
    return 'w-simulated-full';
  }
  
  const w = state.landingLayout.widths?.[key];
  const n = w?.n ?? 1;
  const d = w?.d ?? 1;
  if (n >= d) return 'w-full';
  
  // Map common ratios to class names
  const ratioKey = `${n}/${d}`;
  const ratioClasses = {
    '1/2': 'w-half',
    '1/3': 'w-oneThird',
    '2/3': 'w-twoThirds',
    '1/4': 'w-oneQuarter',
    '3/4': 'w-threeQuarters',
    '1/5': 'w-oneFifth',
    '2/5': 'w-twoFifths',
    '3/5': 'w-threeFifths',
    '4/5': 'w-fourFifths',
    '1/6': 'w-oneSixth',
    '5/6': 'w-fiveSixths',
  };
  
  return ratioClasses[ratioKey] || 'w-full';
}

function getEffectiveBg(sectionBgColor) {
  if (!sectionBgColor || sectionBgColor === 'transparent') {
    return state.design.backgroundColor || state.design.backgroundPrimaryColor || '#f6f7fb';
  }
  // rgba with very low alpha → treat as near-transparent, use page bg
  const rgbaMatch = sectionBgColor.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\)/);
  if (rgbaMatch) {
    const a = rgbaMatch[4] !== undefined ? parseFloat(rgbaMatch[4]) : 1;
    if (a < 0.15) return state.design.backgroundColor || state.design.backgroundPrimaryColor || '#f6f7fb';
    // Blend the rgba onto the page background for an approximate opaque result
    const pageBg = state.design.backgroundColor || state.design.backgroundPrimaryColor || '#f6f7fb';
    const pr = parseInt(pageBg.slice(1, 3), 16);
    const pg = parseInt(pageBg.slice(3, 5), 16);
    const pb = parseInt(pageBg.slice(5, 7), 16);
    const r = Math.round(parseInt(rgbaMatch[1]) * a + pr * (1 - a));
    const g = Math.round(parseInt(rgbaMatch[2]) * a + pg * (1 - a));
    const b = Math.round(parseInt(rgbaMatch[3]) * a + pb * (1 - a));
    return `#${r.toString(16).padStart(2,'0')}${g.toString(16).padStart(2,'0')}${b.toString(16).padStart(2,'0')}`;
  }
  return sectionBgColor;
}

function contrastColor(bgHex, backgroundBaseKey = null) {
  return resolveHighContrastColorForBackground(
    state.design,
    state.adminDesignConfig,
    {
      backgroundColor: bgHex,
      backgroundBaseKey,
    }
  );
}

function getSectionStyle(key, visibleIndex) {
  const style = {};
  const containerId = containerMaps.value.sectionToContainerId?.[key] || null;
  const leaderKey = containerId ? getContainerLeaderKey(containerId, containerMaps.value) : null;
  const rawOverrides = state.sectionDesignOverrides?.[key]
    || (leaderKey ? state.sectionDesignOverrides?.[leaderKey] : null);
  const overrides = rawOverrides;
  const active = !overrides || overrides._active !== false;
  const sectionData = getSectionData(key) || {};
  const sectionGeneric = (sectionData.sectionGeneric && typeof sectionData.sectionGeneric === "object")
    ? sectionData.sectionGeneric
    : {};

  let sectionBgColor = null;
  const removeSectionBackground = Boolean(sectionGeneric.removeSectionBackground);
  const removeSectionPadding = Boolean(sectionGeneric.removeSectionPadding);
  if (removeSectionPadding) {
    style['--section-padding'] = '0px';
  }

  if (removeSectionBackground) {
    sectionBgColor = "transparent";
    style['--section-background-color'] = "transparent";
    style["--section-border-radius"] = "0px";
    style["--section-border-width"] = "0px";
    style["--section-border-style"] = "none";
    style["--section-border-color"] = "transparent";
    style["--section-box-shadow"] = "none";
  } else {
    const bgColorOverride = active
      ? resolveOverrideColorValue(overrides, 'sectionBackgroundColor', {
          backgroundColor: state.design.backgroundColor || state.design.backgroundPrimaryColor || "#f6f7fb",
          backgroundBaseKey: "backgroundColor",
        })
      : null;
    if (bgColorOverride) {
      sectionBgColor = bgColorOverride;
      style['--section-background-color'] = sectionBgColor;
    } else {
      const patternColor = computeSectionBgColor(visibleIndex, visibleOrderedKeys.value.length, key);
      if (patternColor) {
        sectionBgColor = patternColor;
        style['--section-background-color'] = patternColor;
      }
    }
  }

  // Per-section high-contrast: if heading or paragraph color is __high_contrast__,
  // compute contrast against this section's actual background
  const effectiveBg = getEffectiveBg(sectionBgColor || state.design.sectionBackgroundColor || state.design.backgroundSecondaryColor);
  const globalBg = state.design.sectionBackgroundColor || state.design.backgroundSecondaryColor || '#ffffff';
  const bgDiffers = effectiveBg !== globalBg;
  const sectionBgLinkKey = active ? getOverrideMapValue(overrides, "_colorLinks", "sectionBackgroundColor") : null;
  const globalSectionBgLinkKey = state.adminDesignConfig?.colorLinks?.sectionBackgroundColor;
  const overrideBackgroundBaseKey = isBaseColorLinkKey(sectionBgLinkKey, state.adminDesignConfig?.parameters) ? sectionBgLinkKey : null;
  const globalBackgroundBaseKey = isBaseColorLinkKey(globalSectionBgLinkKey, state.adminDesignConfig?.parameters) ? globalSectionBgLinkKey : null;
  const backgroundBaseKey = overrideBackgroundBaseKey || globalBackgroundBaseKey;

  const headingColorOverride = active
    ? resolveOverrideColorValue(overrides, "headingColor", {
        backgroundColor: effectiveBg,
        backgroundBaseKey,
      })
    : null;
  const globalHeadingColorMode = state.design.headingColor || "__high_contrast__";
  if (globalHeadingColorMode === "__high_contrast__" && bgDiffers && headingColorOverride == null) {
    const contrasted = contrastColor(effectiveBg, backgroundBaseKey);
    style['--heading-color'] = contrasted;
    style['--primary-color'] = contrasted;
  }
  const paragraphColorOverride = active
    ? resolveOverrideColorValue(overrides, "paragraphColor", {
        backgroundColor: effectiveBg,
        backgroundBaseKey,
      })
    : null;
  if (state.design.paragraphColor === "__high_contrast__" && bgDiffers && paragraphColorOverride == null) {
    const contrasted = applyColorVariation(
      contrastColor(effectiveBg, backgroundBaseKey),
      getGlobalColorVariation("paragraphColor")
    );
    style['--paragraph-color'] = contrasted;
    style['--secondary-color'] = contrasted;
  }

  // Hard box-shadow
  const hardShadow = removeSectionBackground
    ? null
    : computeHardBoxShadow(sectionBgColor, active ? overrides : undefined);
  if (hardShadow) {
    const baseShadow = (active && overrides?.sectionBoxShadow != null)
      ? overrides.sectionBoxShadow
      : (state.design.sectionBoxShadow || 'none');
    style['--section-box-shadow'] = baseShadow !== 'none'
      ? `${baseShadow}, ${hardShadow}`
      : hardShadow;
  }

  if (!active) return style;

  // Get unit for a param from override's selected units or default
  const getUnit = (paramKey, defaultUnit = 'px') => {
    return getOverrideUnit(overrides, paramKey, defaultUnit);
  };

  // Container overrides with responsive support
  if (!removeSectionBackground) {
    const borderRadius = getResponsiveOverrideValue(overrides, 'sectionBorderRadius', null);
    if (borderRadius != null) {
      style['--section-border-radius'] = `${borderRadius}${getUnit('sectionBorderRadius', 'px')}`;
    }
    const borderWidth = getResponsiveOverrideValue(overrides, "sectionBorderWidth", null);
    if (borderWidth != null) {
      style["--section-border-width"] = `${borderWidth}${getUnit("sectionBorderWidth", "px")}`;
    }
    const borderColor = resolveOverrideColorValue(overrides, "sectionBorderColor", {
      backgroundColor: effectiveBg,
      backgroundBaseKey,
    });
    if (borderColor) {
      style["--section-border-color"] = borderColor;
    }
    const borderStyle = getResponsiveOverrideValue(overrides, "sectionBorderStyle", null);
    if (borderStyle) {
      style["--section-border-style"] = borderStyle;
    }
  }

  const contentAlign = getResponsiveOverrideValue(overrides, 'sectionContentAlign', null);
  if (contentAlign) {
    style['--section-content-align'] = contentAlign === 'center' ? 'center' : contentAlign === 'right' ? 'right' : 'left';
    style['--section-content-justify'] = contentAlign === 'center' ? 'center' : contentAlign === 'right' ? 'flex-end' : 'flex-start';
  }
  
  const padding = getResponsiveOverrideValue(overrides, 'sectionPadding', null);
  if (!removeSectionPadding && padding != null) {
    style['--section-padding'] = `${padding}${getUnit('sectionPadding', 'px')}`;
  }
  
  if (!removeSectionBackground && overrides?.sectionBoxShadow != null && !hardShadow) {
    style['--section-box-shadow'] = overrides.sectionBoxShadow;
  }

  // Header typography overrides with responsive support
  const headerColor = headingColorOverride;
  if (headerColor) {
    style['--heading-color'] = headerColor;
    style['--primary-color'] = headerColor;
  }
  const headerFontFamily = getResponsiveOverrideValue(overrides, 'headerFontFamily', null);
  if (headerFontFamily) {
    style['--header-font-family'] = headerFontFamily;
  }
  // Per-heading overrides (h1-h4)
  for (let i = 1; i <= 4; i++) {
    const fontSize = getResponsiveOverrideValue(overrides, `h${i}FontSize`, null);
    if (fontSize != null) {
      style[`--h${i}-font-size`] = `${fontSize}${getUnit(`h${i}FontSize`, 'px')}`;
    }
    const letterSpacing = getResponsiveOverrideValue(overrides, `h${i}LetterSpacing`, null);
    if (letterSpacing != null) {
      style[`--h${i}-letter-spacing`] = `${letterSpacing}${getUnit(`h${i}LetterSpacing`, 'em')}`;
    }
    const lineHeight = getResponsiveOverrideValue(overrides, `h${i}LineHeight`, null);
    if (lineHeight != null) {
      style[`--h${i}-line-height`] = String(lineHeight);
    }
  }
  const headerFontWeight = getResponsiveOverrideValue(overrides, 'headerFontWeight', null);
  if (headerFontWeight) {
    style['--header-font-weight'] = headerFontWeight;
    for (let i = 1; i <= 6; i++) {
      style[`--h${i}-font-weight`] = headerFontWeight;
    }
  }

  // Body text typography overrides with responsive support
  const textColor = paragraphColorOverride;
  if (textColor) {
    style['--paragraph-color'] = textColor;
    style['--secondary-color'] = textColor;
  }
  const textFontFamily = getResponsiveOverrideValue(overrides, "bodyFontFamily", null);
  if (textFontFamily) {
    style['--body-font-family'] = textFontFamily;
  }
  const textFontSize = getResponsiveOverrideValue(overrides, "bodyFontSize", null);
  if (textFontSize != null) {
    style['--body-font-size'] = `${textFontSize}${getUnit('bodyFontSize', 'px')}`;
  }
  const textFontWeight = getResponsiveOverrideValue(overrides, "bodyFontWeight", null);
  if (textFontWeight) {
    style['--body-font-weight'] = textFontWeight;
  }

  // Section-contextual button high-contrast:
  // For transparent button backgrounds (shared or type-specific), derive text/border
  // contrast from this section's effective background instead of global defaults.
  const colorLinks = state.adminDesignConfig?.colorLinks || {};
  const sectionContrastColor = contrastColor(effectiveBg, backgroundBaseKey);

  const sharedButtonBgLink = getOverrideMapValue(overrides, "_colorLinks", "buttonBgColor") ?? colorLinks.buttonBgColor;
  const sharedButtonBgRaw = getResponsiveOverrideValue(overrides, "buttonBgColor", state.design.buttonBgColor);
  const sharedButtonBgValue = resolveLinkedOrRawColor(sharedButtonBgRaw, sharedButtonBgLink);
  const sharedButtonBgIsTransparent = isTransparentColorValue(sharedButtonBgValue, sharedButtonBgLink);

  const sharedButtonColorLink = getOverrideMapValue(overrides, "_colorLinks", "buttonColor") ?? colorLinks.buttonColor;
  const sharedButtonColorRaw = getResponsiveOverrideValue(overrides, "buttonColor", state.design.buttonColor);
  const sharedButtonColorValue = resolveLinkedOrRawColor(sharedButtonColorRaw, sharedButtonColorLink);

  const sharedButtonBorderLink = getOverrideMapValue(overrides, "_colorLinks", "buttonBorderColor") ?? colorLinks.buttonBorderColor;
  const sharedButtonBorderRaw = getResponsiveOverrideValue(overrides, "buttonBorderColor", state.design.buttonBorderColor);
  const sharedButtonBorderValue = resolveLinkedOrRawColor(sharedButtonBorderRaw, sharedButtonBorderLink);

  const sharedButtonHoverBgLink = getOverrideMapValue(overrides, "_colorLinks", "buttonHoverBgColor") ?? colorLinks.buttonHoverBgColor;
  const sharedButtonHoverBgRaw = getResponsiveOverrideValue(overrides, "buttonHoverBgColor", state.design.buttonHoverBgColor);
  const hasSharedHoverBg = (
    sharedButtonHoverBgRaw !== undefined
    && sharedButtonHoverBgRaw !== null
    && sharedButtonHoverBgRaw !== ""
  ) || Boolean(sharedButtonHoverBgLink);
  const sharedHoverBgEffectiveRaw = hasSharedHoverBg ? sharedButtonHoverBgRaw : sharedButtonBgRaw;
  const sharedHoverBgEffectiveLink = hasSharedHoverBg ? sharedButtonHoverBgLink : sharedButtonBgLink;
  const sharedButtonHoverBgValue = resolveLinkedOrRawColor(sharedHoverBgEffectiveRaw, sharedHoverBgEffectiveLink);
  const sharedButtonHoverBgIsTransparent = isTransparentColorValue(sharedButtonHoverBgValue, sharedHoverBgEffectiveLink);

  const sharedButtonHoverColorLink = getOverrideMapValue(overrides, "_colorLinks", "buttonHoverColor") ?? colorLinks.buttonHoverColor;
  const sharedButtonHoverColorRaw = getResponsiveOverrideValue(overrides, "buttonHoverColor", state.design.buttonHoverColor);
  const hasSharedHoverColor = (
    sharedButtonHoverColorRaw !== undefined
    && sharedButtonHoverColorRaw !== null
    && sharedButtonHoverColorRaw !== ""
  ) || Boolean(sharedButtonHoverColorLink);
  const sharedHoverColorEffectiveRaw = hasSharedHoverColor ? sharedButtonHoverColorRaw : sharedButtonColorRaw;
  const sharedHoverColorEffectiveLink = hasSharedHoverColor ? sharedButtonHoverColorLink : sharedButtonColorLink;
  const sharedButtonHoverColorValue = resolveLinkedOrRawColor(sharedHoverColorEffectiveRaw, sharedHoverColorEffectiveLink);

  const sharedButtonHoverBorderLink = getOverrideMapValue(overrides, "_colorLinks", "buttonHoverBorderColor") ?? colorLinks.buttonHoverBorderColor;
  const sharedButtonHoverBorderRaw = getResponsiveOverrideValue(overrides, "buttonHoverBorderColor", state.design.buttonHoverBorderColor);
  const hasSharedHoverBorder = (
    sharedButtonHoverBorderRaw !== undefined
    && sharedButtonHoverBorderRaw !== null
    && sharedButtonHoverBorderRaw !== ""
  ) || Boolean(sharedButtonHoverBorderLink);
  const sharedHoverBorderEffectiveRaw = hasSharedHoverBorder ? sharedButtonHoverBorderRaw : sharedButtonBorderRaw;
  const sharedHoverBorderEffectiveLink = hasSharedHoverBorder ? sharedButtonHoverBorderLink : sharedButtonBorderLink;
  const sharedButtonHoverBorderValue = resolveLinkedOrRawColor(sharedHoverBorderEffectiveRaw, sharedHoverBorderEffectiveLink);

  if (sharedButtonBgIsTransparent) {
    if (isHighContrastColorValue(sharedButtonColorValue, sharedButtonColorLink)) {
      style["--button-color"] = applyColorVariation(
        sectionContrastColor,
        getOverrideColorVariation(overrides, "buttonColor")
      );
    }
    if (isHighContrastColorValue(sharedButtonBorderValue, sharedButtonBorderLink)) {
      style["--button-border-color"] = applyColorVariation(
        sectionContrastColor,
        getOverrideColorVariation(overrides, "buttonBorderColor")
      );
    }
  }
  if (sharedButtonHoverBgIsTransparent) {
    if (isHighContrastColorValue(sharedButtonHoverColorValue, sharedHoverColorEffectiveLink)) {
      style["--button-hover-color"] = applyColorVariation(
        sectionContrastColor,
        getOverrideColorVariation(overrides, hasSharedHoverColor ? "buttonHoverColor" : "buttonColor")
      );
    }
    if (isHighContrastColorValue(sharedButtonHoverBorderValue, sharedHoverBorderEffectiveLink)) {
      style["--button-hover-border-color"] = applyColorVariation(
        sectionContrastColor,
        getOverrideColorVariation(overrides, hasSharedHoverBorder ? "buttonHoverBorderColor" : "buttonBorderColor")
      );
    }
  }

  const typeStyles = state.design?.buttonTypeStyles || {};
  for (const [typeId, typeOverridesRaw] of Object.entries(typeStyles)) {
    const typeOverrides = typeOverridesRaw && typeof typeOverridesRaw === "object" ? typeOverridesRaw : {};

    const typeBgParamKey = `btnType_${typeId}_bgColor`;
    const typeColorParamKey = `btnType_${typeId}_color`;
    const typeBorderParamKey = `btnType_${typeId}_borderColor`;
    const typeHoverBgParamKey = `btnType_${typeId}_hoverBgColor`;
    const typeHoverColorParamKey = `btnType_${typeId}_hoverColor`;
    const typeHoverBorderParamKey = `btnType_${typeId}_hoverBorderColor`;

    const typeBgLink = colorLinks[typeBgParamKey];
    const typeColorLink = colorLinks[typeColorParamKey];
    const typeBorderLink = colorLinks[typeBorderParamKey];
    const typeHoverBgLink = colorLinks[typeHoverBgParamKey];
    const typeHoverColorLink = colorLinks[typeHoverColorParamKey];
    const typeHoverBorderLink = colorLinks[typeHoverBorderParamKey];

    const hasOwnTypeBg = typeOverrides.bgColor !== undefined || Boolean(typeBgLink);
    const hasOwnTypeColor = typeOverrides.color !== undefined || Boolean(typeColorLink);
    const hasOwnTypeBorder = typeOverrides.borderColor !== undefined || Boolean(typeBorderLink);
    const hasOwnTypeHoverBg = typeOverrides.hoverBgColor !== undefined || Boolean(typeHoverBgLink);
    const hasOwnTypeHoverColor = typeOverrides.hoverColor !== undefined || Boolean(typeHoverColorLink);
    const hasOwnTypeHoverBorder = typeOverrides.hoverBorderColor !== undefined || Boolean(typeHoverBorderLink);

    const typeBgRaw = hasOwnTypeBg ? typeOverrides.bgColor : sharedButtonBgRaw;
    const typeBgEffectiveLink = hasOwnTypeBg ? typeBgLink : sharedButtonBgLink;
    const typeBgValue = resolveLinkedOrRawColor(typeBgRaw, typeBgEffectiveLink);
    const typeBgIsTransparent = isTransparentColorValue(typeBgValue, typeBgEffectiveLink);

    const typeColorRaw = hasOwnTypeColor ? typeOverrides.color : sharedButtonColorRaw;
    const typeColorEffectiveLink = hasOwnTypeColor ? typeColorLink : sharedButtonColorLink;
    const typeBorderRaw = hasOwnTypeBorder ? typeOverrides.borderColor : sharedButtonBorderRaw;
    const typeBorderEffectiveLink = hasOwnTypeBorder ? typeBorderLink : sharedButtonBorderLink;

    if (typeBgIsTransparent) {
      const typeColorValue = resolveLinkedOrRawColor(typeColorRaw, typeColorEffectiveLink);
      if (isHighContrastColorValue(typeColorValue, typeColorEffectiveLink)) {
        style[`--button-${typeId}-color`] = applyColorVariation(
          sectionContrastColor,
          hasOwnTypeColor ? getGlobalColorVariation(typeColorParamKey) : getOverrideColorVariation(overrides, "buttonColor")
        );
      }

      const typeBorderValue = resolveLinkedOrRawColor(typeBorderRaw, typeBorderEffectiveLink);
      if (isHighContrastColorValue(typeBorderValue, typeBorderEffectiveLink)) {
        style[`--button-${typeId}-border-color`] = applyColorVariation(
          sectionContrastColor,
          hasOwnTypeBorder ? getGlobalColorVariation(typeBorderParamKey) : getOverrideColorVariation(overrides, "buttonBorderColor")
        );
      }
    }

    const typeHoverBgRaw = hasOwnTypeHoverBg ? typeOverrides.hoverBgColor : typeBgRaw;
    const typeHoverBgEffectiveLink = hasOwnTypeHoverBg ? typeHoverBgLink : typeBgEffectiveLink;
    const typeHoverBgValue = resolveLinkedOrRawColor(typeHoverBgRaw, typeHoverBgEffectiveLink);
    const typeHoverBgIsTransparent = isTransparentColorValue(typeHoverBgValue, typeHoverBgEffectiveLink);

    if (typeHoverBgIsTransparent) {
      const typeHoverColorRaw = hasOwnTypeHoverColor ? typeOverrides.hoverColor : typeColorRaw;
      const typeHoverColorEffectiveLink = hasOwnTypeHoverColor ? typeHoverColorLink : typeColorEffectiveLink;
      const typeHoverColorValue = resolveLinkedOrRawColor(typeHoverColorRaw, typeHoverColorEffectiveLink);
      if (isHighContrastColorValue(typeHoverColorValue, typeHoverColorEffectiveLink)) {
        const hoverColorVariation = hasOwnTypeHoverColor
          ? getGlobalColorVariation(typeHoverColorParamKey)
          : (
              hasOwnTypeColor
                ? getGlobalColorVariation(typeColorParamKey)
                : getOverrideColorVariation(overrides, hasSharedHoverColor ? "buttonHoverColor" : "buttonColor")
            );
        style[`--button-${typeId}-hover-color`] = applyColorVariation(sectionContrastColor, hoverColorVariation);
      }

      const typeHoverBorderRaw = hasOwnTypeHoverBorder ? typeOverrides.hoverBorderColor : typeBorderRaw;
      const typeHoverBorderEffectiveLink = hasOwnTypeHoverBorder ? typeHoverBorderLink : typeBorderEffectiveLink;
      const typeHoverBorderValue = resolveLinkedOrRawColor(typeHoverBorderRaw, typeHoverBorderEffectiveLink);
      if (isHighContrastColorValue(typeHoverBorderValue, typeHoverBorderEffectiveLink)) {
        const hoverBorderVariation = hasOwnTypeHoverBorder
          ? getGlobalColorVariation(typeHoverBorderParamKey)
          : (
              hasOwnTypeBorder
                ? getGlobalColorVariation(typeBorderParamKey)
                : getOverrideColorVariation(overrides, hasSharedHoverBorder ? "buttonHoverBorderColor" : "buttonBorderColor")
            );
        style[`--button-${typeId}-hover-border-color`] = applyColorVariation(sectionContrastColor, hoverBorderVariation);
      }
    }
  }

  return style;
}

function upsertSectionCustomCssStyle() {
  if (typeof document === "undefined") return;
  const drafts = state.sectionCustomCssDrafts || {};
  let cssText = buildCssSnippetsStyleText(state.publicCssSnippets || [], {
    responsiveConfig: state.adminDesignConfig?.responsive,
  });

  for (const [sectionKey, customCssRaw] of Object.entries(drafts)) {
    if (!sectionKey || sectionKey === "__header__") continue;
    const customCss = String(customCssRaw || "");
    if (!customCss.trim()) continue;
    const sectionId = getSectionId(sectionKey);
    const scopeSelector = buildSectionScopeSelector(sectionId);
    const scopedCss = scopeSectionCustomCss(customCss, scopeSelector);
    if (!scopedCss) continue;
    cssText += `/* ${sectionKey} */\n${scopedCss}\n`;
  }

  let el = document.getElementById(SECTION_CUSTOM_CSS_STYLE_ID);
  if (!cssText) {
    if (el) el.textContent = "";
    return;
  }

  if (!el) {
    el = document.createElement("style");
    el.id = SECTION_CUSTOM_CSS_STYLE_ID;
    document.head.appendChild(el);
  }
  // Keep it at the end of <head> so section custom CSS wins by cascade order.
  if (el.parentNode === document.head && el !== document.head.lastElementChild) {
    document.head.appendChild(el);
  }
  el.textContent = cssText;
}

/**
 * Get the component for a given key.
 * Handles keys with ID suffix (e.g., "text_123abc" -> "text")
 */
function getComponent(key) {
  if (props.componentMap[key]) {
    return props.componentMap[key];
  }
  const baseKey = key.includes('_') ? key.split('_')[0] : key;
  return props.componentMap[baseKey];
}

/**
 * Get section data for a given key from sectionsData.
 */
function getSectionData(key) {
  return state.sectionsData?.[key] || null;
}

function getSectionId(key) {
  return String(state.sectionIds?.[key] || "").trim();
}

/**
 * Get CSS classes for device visibility
 * When simulated viewport is active, we use JS-based hiding instead of CSS media queries
 */
function getDeviceVisibilityClasses(key) {
  // Use computed property to ensure reactivity
  let visibility = deviceVisibilityMap.value[key];
  if (!visibility) {
    const containerId = containerMaps.value.sectionToContainerId?.[key] || null;
    const leaderKey = containerId ? getContainerLeaderKey(containerId, containerMaps.value) : null;
    if (leaderKey) visibility = deviceVisibilityMap.value[leaderKey];
  }
  if (!visibility) return {};
  
  const sim = state.simulatedViewport;
  
  // If simulated viewport is active, hide based on simulated device only
  if (sim) {
    let isHidden = false;
    if (sim === 'mobile') isHidden = visibility.mobile === false;
    else if (sim === 'tablet') isHidden = visibility.tablet === false;
    else if (sim === 'desktop') isHidden = visibility.desktop === false;
    return { 'force-hide': isHidden };
  }
  
  // Default: use CSS media query based hiding
  return {
    'hide-mobile': visibility.mobile === false,
    'hide-tablet': visibility.tablet === false,
    'hide-desktop': visibility.desktop === false,
  };
}

watch(
  () => state.sectionCustomCssDrafts,
  () => {
    upsertSectionCustomCssStyle();
  },
  { deep: true }
);

watch(
  () => state.publicCssSnippets,
  () => {
    upsertSectionCustomCssStyle();
  },
  { deep: true }
);

watch(
  () => state.adminDesignConfig?.responsive,
  () => {
    upsertSectionCustomCssStyle();
  },
  { deep: true }
);

onMounted(() => {
  upsertSectionCustomCssStyle();
});

onBeforeUnmount(() => {
  const el = document.getElementById(SECTION_CUSTOM_CSS_STYLE_ID);
  if (el) el.textContent = "";
});
</script>

<style scoped>
.page-container {
  padding-top: var(--content-padding-top, 16px);
  padding-bottom: var(--content-padding-bottom, 16px);
}

.section-grid-frame {
  position: relative;
}

.section-grid-preview-stick {
  position: sticky;
  top: calc(100vh - 72px);
  top: calc(100dvh - 72px);
  z-index: 30;
  display: flex;
  justify-content: center;
  height: 44px;
  margin-bottom: -44px;
  pointer-events: none;
}

.section-grid-preview-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 38px;
  min-width: 112px;
  max-width: min(100%, 220px);
  padding: 8px 14px;
  border: 1px solid #93c5fd;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.16);
  cursor: pointer;
  pointer-events: auto;
  white-space: nowrap;
}

.section-grid-preview-button:hover {
  border-color: #1d4ed8;
  background: #1d4ed8;
}

.section-grid-preview-button--active {
  border-color: #d97706;
  background: #d97706;
  color: #fff;
}

.section-grid-preview-button--active:hover {
  border-color: #b45309;
  background: #b45309;
}

.section-grid-preview-button:disabled {
  cursor: wait;
  opacity: 0.72;
}

.section-grid-preview-button:disabled:hover {
  border-color: #93c5fd;
  background: #2563eb;
}

.section-grid-preview-button--active:disabled:hover {
  border-color: #d97706;
  background: #d97706;
}

.section-grid-preview-button__icon {
  width: 12px;
  height: 12px;
  flex: 0 0 auto;
}

.section-grid-preview-button__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 8px;
  background: #fff;
  color: #b45309;
  font-size: 11px;
  font-weight: 700;
}

.grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--section-spacing, 14px);
}

/* Border collapse: when section padding is 0 and sections have borders, collapse adjacent borders */
.grid.border-collapse {
  gap: 0;
}

.grid.border-collapse .grid-item {
  border-radius: 0;
  margin-right: calc(var(--section-border-width, 0px) * -1);
  margin-bottom: calc(var(--section-border-width, 0px) * -1);
}

.grid-item {
  min-width: 0;
  box-sizing: border-box;
  width: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  border: var(--section-border-width) var(--section-border-style) var(--section-border-color);
  border-radius: var(--section-border-radius);
  box-shadow: var(--section-box-shadow);
  background: var(--section-background-color);
}

.grid-item-background-media {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

.grid-item-content {
  min-width: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
  position: relative;
  text-align: var(--section-content-align);
  padding: var(--section-padding);
}

.grid-container {
  gap: 0;
  overflow: hidden;
}

.grid-container > .grid-item-content {
  border-radius: 0;
  padding-top: calc(var(--section-padding) * 0.5);
  padding-bottom: calc(var(--section-padding) * 0.5);
}

.grid-container > .grid-item-content--container-first {
  padding-top: var(--section-padding);
}

.grid-container > .grid-item-content--container-last {
  padding-bottom: var(--section-padding);
}

/* Section shell now lives on grid-item-content. Keep the inner section card neutral. */
.grid-item-content > .card:not(.unknown-section) {
  background: transparent;
  padding: 0;
  text-align: inherit;
  box-shadow: none;
  border: 0;
  border-radius: 0;
  height: auto;
  flex: 1 1 auto;
  min-height: 0;
  position: relative;
}

/* Desktop width classes (>= 1120px) */
@media (min-width: 1120px) {
  .grid-item.w-full { width: 100%; }
  .grid-item.w-half { width: calc(1 / 2 * 100% - 1 / 2 * var(--section-spacing, 14px)); }
  .grid-item.w-oneThird { width: calc(1 / 3 * 100% - 2 / 3 * var(--section-spacing, 14px)); }
  .grid-item.w-twoThirds { width: calc(2 / 3 * 100% - 1 / 3 * var(--section-spacing, 14px)); }
  .grid-item.w-oneQuarter { width: calc(1 / 4 * 100% - 3 / 4 * var(--section-spacing, 14px)); }
  .grid-item.w-threeQuarters { width: calc(3 / 4 * 100% - 1 / 4 * var(--section-spacing, 14px)); }
  .grid-item.w-oneFifth { width: calc(1 / 5 * 100% - 4 / 5 * var(--section-spacing, 14px)); }
  .grid-item.w-twoFifths { width: calc(2 / 5 * 100% - 3 / 5 * var(--section-spacing, 14px)); }
  .grid-item.w-threeFifths { width: calc(3 / 5 * 100% - 2 / 5 * var(--section-spacing, 14px)); }
  .grid-item.w-fourFifths { width: calc(4 / 5 * 100% - 1 / 5 * var(--section-spacing, 14px)); }
  .grid-item.w-oneSixth { width: calc(1 / 6 * 100% - 5 / 6 * var(--section-spacing, 14px)); }
  .grid-item.w-fiveSixths { width: calc(5 / 6 * 100% - 1 / 6 * var(--section-spacing, 14px)); }
}

/* Simulated viewport full width (bypasses desktop width classes during mobile/tablet simulation) */
.grid-item.w-simulated-full { width: 100% !important; }

/* Device visibility - hide sections based on screen size */
/* Force hide (used for simulated viewport) */
.grid-item.force-hide { display: none !important; }

/* Mobile: up to 767px */
@media (max-width: 767px) {
  .grid-item.hide-mobile { display: none !important; }

  .section-grid-preview-stick {
    top: calc(100vh - 68px);
    top: calc(100dvh - 68px);
  }

  .section-grid-preview-button {
    max-width: calc(100vw - 32px);
  }
}

/* Tablet: 768px to 1119px */
@media (min-width: 768px) and (max-width: 1119px) {
  .grid-item.hide-tablet { display: none !important; }
}

/* Desktop: 1120px and up */
@media (min-width: 1120px) {
  .grid-item.hide-desktop { display: none !important; }
}

.unknown-section {
  padding: 20px;
  background: #fef3c7;
  border: 1px dashed #d97706;
  border-radius: 12px;
}

.unknown-hint {
  margin: 0;
  color: #92400e;
  font-size: 14px;
}
</style>
