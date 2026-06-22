<template>
  <div 
      ref="tickerRef"
      :data-section-key="effectiveKey"
      class="ticker" 
      :class="{ 'ticker--pinned-header': isPinnedToHeader }"
      :style="tickerStyle"
  >
    <div v-if="viewMode !== 'updates'" class="viewport" aria-label="Ticker">
      <div class="track" :style="{ animationDuration: duration + 's' }">
        <div class="seq">
          <template v-for="it in filledItems" :key="it._k">
            <span class="item" :style="itemStyle">{{ localizedText(it.text) }}</span>
            <template v-if="separatorImageUrl">
              <ResponsiveImage
                class="sep-image"
                :style="sepImageStyle"
                :src="separatorImageUrl"
                :image-data="separatorImageAssetData"
                alt=""
                loading="lazy"
                decoding="async"
              />
            </template>
            <span v-else class="sep" :style="sepStyle">{{ separator }}</span>
          </template>
        </div>
        <div class="seq" aria-hidden="true">
          <template v-for="it in filledItems" :key="it._k + '_dup'">
            <span class="item" :style="itemStyle">{{ localizedText(it.text) }}</span>
            <template v-if="separatorImageUrl">
              <ResponsiveImage
                class="sep-image"
                :style="sepImageStyle"
                :src="separatorImageUrl"
                :image-data="separatorImageAssetData"
                alt=""
                loading="lazy"
                decoding="async"
              />
            </template>
            <span v-else class="sep" :style="sepStyle">{{ separator }}</span>
          </template>
        </div>
      </div>
    </div>
    <ul v-else class="updates-stack" role="list" aria-label="Updates">
      <template v-if="groupedUpdates.length > 0">
        <template v-for="group in groupedUpdates" :key="group.dayKey">
          <li class="update-day-header" :style="dayLabelStyle" role="styling">{{ group.dayLabel }}</li>
          <li v-for="item in group.items" :key="item.id" class="update-item" :style="itemStyle">
            <span class="update-bullet" aria-hidden="true">•</span>
            <div class="update-body">
              <span class="update-time">{{ formatUpdateTime(item.timestamp) }}</span>
              <span class="update-desc">{{ localizedText(item.text) }}</span>
            </div>
          </li>
        </template>
      </template>
      <li v-else class="update-empty" :style="itemStyle">—</li>
    </ul>
    <div v-if="showPublicHiddenBadge" class="ticker-public-hidden-badge">public hidden</div>

    <MediaLibrary
      :is-open="showSeparatorMediaPicker"
      :current-url="separatorImageUrl || ''"
      source-context="section.ticker.separator_image"
      @close="showSeparatorMediaPicker = false"
      @select="onSeparatorImageSelect"
    />

    <SectionAdminTabs
      v-if="state.isAdmin"
      :section-key="effectiveKey"
      :show-section-generic="true"
      :show-output="showSectionTemplateOutput"
      v-model:active-tab="adminTab"
      @tab-change="onAdminTabChange"
    >
      <template #design-colors>
        <div class="ticker-admin-controls">
          <div class="ticker-admin-grid">
            <div class="ctrl-group">
              <div class="ctrl-list">
                <div class="ctrl color-ctrl">
                  <span class="ctrl-label">Background</span>
                  <VueColorPicker
                    :model-value="bgColorValue"
                    fallback-color="#f1f5f9"
                    :preview-style="bgSwatchStyle"
                    :size="28"
                    @update:model-value="setBgColor($event)"
                  />
                  <ColorLinkPicker :model-value="bgColorLink" :options="bgLinkOptions" @link="linkBgColor" />
                  <select
                    class="variation-select"
                    :value="bgColorVariation"
                    @change="setBgColorVariation($event.target.value)"
                  >
                    <option v-for="variation in colorVariationOptions" :key="`ticker-bg-${variation}`" :value="variation">
                      {{ variation }}%
                    </option>
                  </select>
                  <button v-if="bgColor || bgColorLink" class="clear-btn" type="button" title="Clear" @click="clearBgColor">&times;</button>
                </div>
                <div class="ctrl color-ctrl">
                  <span class="ctrl-label">Text</span>
                  <VueColorPicker
                    :model-value="textColorValue"
                    fallback-color="#0b1220"
                    :preview-style="textSwatchStyle"
                    :size="28"
                    @update:model-value="setTextColor($event)"
                  />
                  <ColorLinkPicker :model-value="textColorLink" :options="textLinkOptions" @link="linkTextColor" />
                  <select
                    class="variation-select"
                    :value="textColorVariation"
                    @change="setTextColorVariation($event.target.value)"
                  >
                    <option v-for="variation in colorVariationOptions" :key="`ticker-text-${variation}`" :value="variation">
                      {{ variation }}%
                    </option>
                  </select>
                  <button v-if="textColor || textColorLink" class="clear-btn" type="button" title="Clear" @click="clearTextColor">&times;</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <template #design-params>
        <div class="ticker-admin-controls">
          <div class="ticker-admin-grid">
            <div class="ctrl-group">
              <div class="ctrl-group-title">Layout</div>
              <div class="ctrl-list">
                <div class="ctrl">
                  <span class="ctrl-label">View Mode</span>
                  <select
                    class="ctrl-select"
                    :value="viewMode"
                    :disabled="isTickerSectionFieldLocked('viewMode')"
                    :title="isTickerSectionFieldLocked('viewMode') ? integrationLockedHint : undefined"
                    @change="setViewMode($event.target.value)"
                  >
                    <option value="ticker">Ticker (scrolling)</option>
                    <option value="updates">Updates (stack)</option>
                  </select>
                </div>
                <div class="ctrl">
                  <label class="pin-toggle">
                    <input type="checkbox" :checked="isPinnedToHeader" @change="togglePinToHeader($event.target.checked)" />
                    <span>Pin to header bottom</span>
                  </label>
                </div>
              </div>
            </div>

            <div class="ctrl-group">
              <div class="ctrl-group-title">Appearance</div>
              <div class="ctrl-list">
                <div class="ctrl">
                  <span class="ctrl-label">Font Size</span>
                  <div class="speed-control">
                    <input
                      v-model.number="fontSize"
                      type="range"
                      min="12"
                      max="48"
                      step="1"
                      class="speed-slider"
                      :disabled="isTickerSectionFieldLocked('fontSize')"
                      :title="isTickerSectionFieldLocked('fontSize') ? integrationLockedHint : undefined"
                      @input="saveFontSize"
                    />
                    <span class="speed-value">{{ fontSize }} px</span>
                  </div>
                </div>
                <div class="ctrl">
                  <span class="ctrl-label">Font Family</span>
                  <select
                    class="ctrl-select"
                    :value="fontFamily || ''"
                    :disabled="isTickerSectionFieldLocked('fontFamily')"
                    :title="isTickerSectionFieldLocked('fontFamily') ? integrationLockedHint : undefined"
                    @change="saveFontFamily($event.target.value)"
                  >
                    <option value="">Body Text (Global)</option>
                    <option v-for="font in tickerFontFamilyOptions" :key="font.value" :value="font.value">
                      {{ font.label }}
                    </option>
                  </select>
                </div>
              </div>
            </div>

            <div class="ctrl-group">
              <div class="ctrl-group-title">Separator</div>
              <div class="ctrl-list">
                <div v-if="!separatorImageUrl" class="ctrl">
                  <span class="ctrl-label">Character</span>
                  <select
                    v-model="separator"
                    class="ctrl-select"
                    :disabled="isTickerSectionFieldLocked('separator')"
                    :title="isTickerSectionFieldLocked('separator') ? integrationLockedHint : undefined"
                    @change="saveSeparator"
                  >
                    <option value="·">· (dot)</option>
                    <option value="—">— (dash)</option>
                    <option value="|">| (pipe)</option>
                    <option value="*">* (star)</option>
                    <option value="◆">◆ (diamond)</option>
                    <option value="//"> // (slashes)</option>
                    <option value="+++">+++ (plus)</option>
                  </select>
                </div>
                <div class="ctrl">
                  <span class="ctrl-label">Image</span>
                  <div class="sep-image-controls">
                    <input
                      v-model="separatorImageUrl"
                      class="ctrl-input"
                      type="url"
                      placeholder="https://..."
                      :disabled="isTickerSectionFieldLocked('separatorImageUrl')"
                      :title="isTickerSectionFieldLocked('separatorImageUrl') ? integrationLockedHint : undefined"
                      @change="saveSeparatorImageUrl"
                    />
                    <button
                      class="btn-secondary small"
                      type="button"
                      :disabled="isTickerSectionFieldLocked('separatorImageUrl')"
                      @click="openSeparatorMediaPicker"
                    >Browse</button>
                    <button
                      v-if="separatorImageUrl"
                      class="clear-btn"
                      type="button"
                      title="Clear separator image"
                      :disabled="isTickerSectionFieldLocked('separatorImageUrl')"
                      @click="clearSeparatorImageUrl"
                    >&times;</button>
                  </div>
                </div>
              </div>
            </div>

            <div class="ctrl-group">
              <div class="ctrl-group-title">Motion</div>
              <div class="ctrl-list">
                <div class="ctrl">
                  <span class="ctrl-label">Speed</span>
                  <div class="speed-control">
                    <input
                      v-model.number="speed"
                      type="range"
                      min="16"
                      max="90"
                      step="1"
                      class="speed-slider"
                      :disabled="isTickerSectionFieldLocked('speed')"
                      :title="isTickerSectionFieldLocked('speed') ? integrationLockedHint : undefined"
                      @input="saveSpeed"
                    />
                    <span class="speed-value">{{ speed }} px/s</span>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </template>

      <template #content>
        <div class="editor" @click.stop>
          <SectionIntegrationImporter
            ref="integrationImporterRef"
            :section-key="effectiveKey"
            :section-data="section"
            :section-type="section?.sectionType"
            :show-clear-button="false"
          />

          <label v-if="viewMode !== 'updates' && showShareItemsToggle" class="share-toggle">
            <input
              type="checkbox"
              :checked="isSlaveTicker"
              :disabled="!isSlaveTicker && masterOptions.length === 0"
              @change="saveShareMode($event.target.checked)"
            />
            <span>Use entries from a master ticker on this page</span>
          </label>
          <div v-if="viewMode !== 'updates' && isSlaveTicker" class="slave-config">
            <div v-if="showMasterSelect" class="field-group">
              <label class="field-label">Master Ticker</label>
              <select
                class="ctrl-select"
                :value="resolvedMasterSectionId"
                @change="saveMasterSelection($event.target.value)"
              >
                <option v-for="option in masterOptions" :key="`master-${option.sectionId}`" :value="option.sectionId">
                  {{ option.label }}
                </option>
              </select>
            </div>
            <p v-else-if="resolvedMasterLabel" class="slave-hint">
              This ticker is following: <strong>{{ resolvedMasterLabel }}</strong>
            </p>
            <p v-else class="slave-hint">
              No master ticker available. Disable sharing or create another master ticker.
            </p>
          </div>
          <SectionListEditor
            v-else
            :items="draft"
            :selected-index="expandedItem"
            :add-label="t.add"
            :save-label="t.save"
            :remove-label="t.remove"
            clear-label="Clear All"
            :show-clear="true"
            @select="expandedItem = $event"
            @add="add"
            @save="save"
            @remove="remove"
            @clear="clearAllTickerItems"
          >
            <template #item="{ item, index }">
              <div class="item-thumb item-thumb--text">
                <span class="thumb-num">{{ index + 1 }}</span>
                <span class="thumb-label">{{ tickerEditorItemLabel(item, index) }}</span>
              </div>
            </template>

            <template #editor="{ item, index }">
                <div v-if="viewMode === 'updates'" class="lang-section">
                  <div class="lang-header">Timestamp</div>
                  <VueDatePicker
                    :model-value="serverWallDateTimeToLocalDate(item.timestamp)"
                    class="ticker-datetime-picker"
                    :enable-time-picker="true"
                    :is-24="true"
                    :clearable="true"
                    :text-input="DATE_PICKER_TEXT_INPUT_OPTIONS"
                    :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
                    :teleport="true"
                    auto-apply
                    placeholder="Select timestamp"
                    :disabled="isTickerItemFieldLocked(index, 'timestamp')"
                    :title="isTickerItemFieldLocked(index, 'timestamp') ? integrationLockedHint : undefined"
                    @update:model-value="item.timestamp = localDateToServerWallDateTime($event)"
                  />
                </div>
                <div class="lang-section">
                  <div class="lang-header">
                    {{ t.german }} (DE)
                  </div>
                  <input
                    v-model="item.text.de"
                    class="field"
                    :placeholder="t.tickerText + '...'"
                    :disabled="isTickerItemFieldLocked(index, 'text.de')"
                    :title="isTickerItemFieldLocked(index, 'text.de') ? integrationLockedHint : undefined"
                  />
                </div>
                <div class="lang-section">
                  <div class="lang-header">
                    {{ t.english }} (EN)
                  </div>
                  <input
                    v-model="item.text.en"
                    class="field"
                    :placeholder="t.tickerText + '...'"
                    :disabled="isTickerItemFieldLocked(index, 'text.en')"
                    :title="isTickerItemFieldLocked(index, 'text.en') ? integrationLockedHint : undefined"
                  />
                </div>
            </template>
          </SectionListEditor>
        </div>
      </template>
      <template #output>
        <SectionTemplateOutputMapping
          :section-key="effectiveKey"
          :section-data="section"
        />
      </template>
    </SectionAdminTabs>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from "vue";
import { VueDatePicker } from "@vuepic/vue-datepicker";
import "@vuepic/vue-datepicker/dist/main.css";
import { useStore } from "../../store/store.js";
import {
  buildColorLinkOptions,
  HIGH_CONTRAST_LINK_KEY,
  HIGH_CONTRAST_TOKEN,
  isBaseColorLinkKey,
  resolveLinkedColor,
  resolveHighContrastColorForBackground,
} from "../../utils/colorLinkOptions.js";
import {
  COLOR_VARIATION_OPTIONS,
  DEFAULT_COLOR_VARIATION,
  applyColorVariation,
  normalizeColorVariation,
} from "../../utils/colorVariations.js";
import {
  resolveBackendResponsiveImagePayload,
  mergeResponsiveVariants,
} from "../../utils/responsiveImages.js";
import { getBaseSectionSwatchStyle } from "./_baseSectionSwatchStyle.js";
import { isSectionHiddenInPublicBecauseEmptyList } from "../../utils/sectionVisibilityRules.js";
import {
  DATE_PICKER_DATE_TIME_DISPLAY_FORMATS,
  DATE_PICKER_TEXT_INPUT_OPTIONS,
  formatInstantInServerTimezone,
  formatServerDateOnly,
  formatServerWallTime,
  getCurrentServerWallDate,
  localDateToServerWallDateTime,
  parseRevisionTimestamp,
  serverWallDateTimeToLocalDate,
} from "../../utils/revisionTime.js";
import { isSectionIntegrationFieldLocked } from "../../utils/sectionIntegrationFieldState.js";

import SectionAdminTabs from "../admin/section-editor/SectionAdminTabs.vue";
import SectionListEditor from "../admin/section-editor/SectionListEditor.vue";
import SectionIntegrationImporter from "../admin/section-editor/SectionIntegrationImporter.vue";
import SectionTemplateOutputMapping from "../admin/section-editor/SectionTemplateOutputMapping.vue";
import ColorLinkPicker from "../ui/color/ColorLinkPicker.vue";
import VueColorPicker from "../ui/color/VueColorPicker.vue";
import MediaLibrary from "../ui/MediaLibrary.vue";
import ResponsiveImage from "../ui/ResponsiveImage.vue";

const props = defineProps({
  sectionKey: { type: String, default: 'ticker' },
  sectionData: { type: Object, default: null },
  forcePinnedDisplay: { type: Boolean, default: false }
});

const { state, t, localizedText, updateSection, saveSectionByKey } = useStore();
const integrationLockedHint = "Managed by integration import.";

const tickerRef = ref(null);
const containerWidth = ref(1200);
const adminTab = ref("design");
const integrationImporterRef = ref(null);
const draft = ref([]);
const expandedItem = ref(-1);
const shareItemsWithTickers = ref(false);
const sharedTickerMasterSectionId = ref("");
const viewMode = ref("ticker");

const effectiveKey = computed(() => props.sectionKey);
const showSectionTemplateOutput = computed(() =>
  state.isAdmin
  && state.canAdminGeneral
  && String(state.pageSlug || "").startsWith("__template_section__/")
);

const section = computed(() => {
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});
const publicView = computed(() => !state.isAdmin || state.previewMode);
const showPublicHiddenBadge = computed(() =>
  state.isAdmin
  && !state.previewMode
  && isSectionHiddenInPublicBecauseEmptyList(effectiveKey.value, state, section.value)
);
function tickerFieldPath(index, fieldPath) {
  const normalizedFieldPath = String(fieldPath || "").trim();
  const numericIndex = Number(index);
  const resolvedIndex = Number.isInteger(numericIndex) && numericIndex >= 0 ? numericIndex : 0;
  return normalizedFieldPath
    ? `items[${resolvedIndex}].${normalizedFieldPath}`
    : `items[${resolvedIndex}]`;
}

function isTickerSectionFieldLocked(path, options = {}) {
  return state.isAdmin && isSectionIntegrationFieldLocked(section.value, path, options);
}

function isTickerItemFieldLocked(index, fieldPath, options = {}) {
  return state.isAdmin && isSectionIntegrationFieldLocked(section.value, tickerFieldPath(index, fieldPath), options);
}

function clearAllTickerItems() {
  if (viewMode.value !== "updates" && isSlaveTicker.value) return;
  draft.value = [];
  expandedItem.value = -1;
  save();
}

// Section-specific parameters
const bgColor = ref(null);
const bgColorLink = ref(null);
const textColor = ref(null);
const textColorLink = ref(null);
const bgColorVariation = ref(DEFAULT_COLOR_VARIATION);
const textColorVariation = ref(DEFAULT_COLOR_VARIATION);
const separator = ref('·');
const separatorImageUrl = ref(null);
const separatorImageResponsiveVariants = ref([]);
const speed = ref(38);
const fontSize = ref(16);
const fontFamily = ref(null);
const pinToHeader = ref(false);
const showSeparatorMediaPicker = ref(false);
const colorVariationOptions = COLOR_VARIATION_OPTIONS;
const DEFAULT_FONT_FAMILY = 'system-ui, -apple-system, sans-serif';

const fallbackTickerFontFamilies = [
  { value: DEFAULT_FONT_FAMILY, label: 'System UI' },
  { value: '"Inter", sans-serif', label: 'Inter' },
  { value: '"Roboto", sans-serif', label: 'Roboto' },
  { value: '"Open Sans", sans-serif', label: 'Open Sans' },
  { value: '"Lato", sans-serif', label: 'Lato' },
  { value: '"Montserrat", sans-serif', label: 'Montserrat' },
  { value: '"Poppins", sans-serif', label: 'Poppins' },
  { value: '"Playfair Display", serif', label: 'Playfair Display' },
  { value: '"Merriweather", serif', label: 'Merriweather' },
  { value: '"Georgia", serif', label: 'Georgia' },
  { value: '"Source Code Pro", monospace', label: 'Source Code Pro' },
];

function normalizeSpeedValue(rawSpeed) {
  if (typeof rawSpeed === 'number' && Number.isFinite(rawSpeed)) {
    return Math.max(16, Math.min(90, Math.round(rawSpeed)));
  }
  if (rawSpeed === 'slow') return 28;
  if (rawSpeed === 'fast') return 55;
  return 38;
}

function normalizeFontSizeValue(rawSize) {
  if (typeof rawSize === 'number' && Number.isFinite(rawSize)) {
    return Math.max(12, Math.min(48, Math.round(rawSize)));
  }
  return 16;
}

function resolveTickerSeparatorImagePayload(source) {
  const normalized = source && typeof source === "object" ? source : {};
  return {
    url: String(normalized.separatorImageUrl || normalized.separatorUrl || "").trim(),
    responsiveVariants: Array.isArray(normalized.separatorImageResponsiveVariants)
      ? normalized.separatorImageResponsiveVariants
      : Array.isArray(normalized.separatorResponsiveVariants)
        ? normalized.separatorResponsiveVariants
        : [],
  };
}

// Initialize from section data
watch(section, (s) => {
  const separatorMedia = resolveTickerSeparatorImagePayload(s);
  bgColor.value = s?.bgColor || null;
  bgColorLink.value = s?.bgColorLink || null;
  textColor.value = s?.textColor || null;
  textColorLink.value = s?.textColorLink || null;
  bgColorVariation.value = normalizeColorVariation(s?.bgColorVariation);
  textColorVariation.value = normalizeColorVariation(s?.textColorVariation);
  separator.value = s?.separator || '·';
  separatorImageUrl.value = separatorMedia.url || null;
  separatorImageResponsiveVariants.value = mergeResponsiveVariants([
    Array.isArray(separatorMedia.responsiveVariants)
      ? separatorMedia.responsiveVariants
      : [],
  ]);
  speed.value = normalizeSpeedValue(s?.speed);
  fontSize.value = normalizeFontSizeValue(s?.fontSize);
  fontFamily.value = String(s?.fontFamily || "").trim() || null;
  pinToHeader.value = s?.pinToHeader === true;
  shareItemsWithTickers.value = s?.shareItemsWithTickers === true;
  sharedTickerMasterSectionId.value = String(s?.sharedTickerMasterSectionId || "").trim();
  viewMode.value = s?.viewMode === "updates" ? "updates" : "ticker";
}, { immediate: true });

const tickerFontFamilyOptions = computed(() => {
  const source = Array.isArray(state.adminDesignConfig?.fontFamilies) && state.adminDesignConfig.fontFamilies.length
    ? state.adminDesignConfig.fontFamilies
    : fallbackTickerFontFamilies;
  const seen = new Set();
  const options = [];
  for (const font of source) {
    const value = String(font?.value || "").trim();
    if (!value || seen.has(value)) continue;
    seen.add(value);
    options.push({
      value,
      label: String(font?.label || value).trim() || value,
    });
  }
  if (fontFamily.value && !seen.has(fontFamily.value)) {
    options.unshift({ value: fontFamily.value, label: `Custom (${fontFamily.value})` });
  }
  return options;
});

const effectiveFontFamily = computed(() => (
  fontFamily.value
  || state.design.bodyFontFamily
  || DEFAULT_FONT_FAMILY
));

function onAdminTabChange(tab) {
  if (tab !== "content") return;
  if (viewMode.value !== "updates" && isSlaveTicker.value) {
    expandedItem.value = -1;
    draft.value = [];
    return;
  }
  startEdit();
}

// ResizeObserver for container width
let resizeObserver = null;

onMounted(() => {
  if (tickerRef.value) {
    containerWidth.value = tickerRef.value.offsetWidth || 1200;
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        containerWidth.value = entry.contentRect.width || 1200;
      }
    });
    resizeObserver.observe(tickerRef.value);
  }
});

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
  }
});

// Base colors for linking
const bgLinkOptions = computed(() =>
  buildColorLinkOptions(state.design, {
    parameterConfigs: state.adminDesignConfig?.parameters,
  })
);
const textLinkOptions = computed(() =>
  buildColorLinkOptions(state.design, {
    includeHighContrast: true,
    parameterConfigs: state.adminDesignConfig?.parameters,
  })
);

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

// Resolve linked color to actual value
function resolveColor(directColor, linkKey, forText = false, contrastBg = null, contrastBgBaseKey = null) {
  if (linkKey === 'transparent') return 'transparent';
  if (linkKey === HIGH_CONTRAST_LINK_KEY || directColor === HIGH_CONTRAST_TOKEN) {
    return contrastColor(
      contrastBg || state.design.sectionBackgroundColor || "#ffffff",
      contrastBgBaseKey || (forText ? null : "sectionBackgroundColor")
    );
  }
  if (linkKey) {
    const linked = resolveLinkedColor(state.design, linkKey, state.adminDesignConfig?.parameters);
    if (linked) return linked;
  }
  if (directColor) return directColor;
  return contrastColor(
    contrastBg || state.design.sectionBackgroundColor || "#ffffff",
    contrastBgBaseKey || (forText ? null : "sectionBackgroundColor")
  );
}

function getBackgroundBaseKeyFromLink(linkKey) {
  if (!linkKey) return null;
  return isBaseColorLinkKey(linkKey, state.adminDesignConfig?.parameters) ? linkKey : null;
}

// Speed in pixels per second (keeps perceived speed consistent across viewports)
const DEFAULT_SPEED_PX_PER_SEC = 38;

// Computed colors
const resolvedBgBaseColor = computed(() => resolveColor(bgColor.value, bgColorLink.value));
const resolvedTextBaseColor = computed(() =>
  resolveColor(
    textColor.value,
    textColorLink.value,
    true,
    resolvedBgBaseColor.value,
    getBackgroundBaseKeyFromLink(bgColorLink.value)
  )
);
const effectiveBgColor = computed(() =>
  applyColorVariation(resolvedBgBaseColor.value, bgColorVariation.value)
);
const effectiveTextColor = computed(() =>
  applyColorVariation(resolvedTextBaseColor.value, textColorVariation.value)
);
const isPinnedToHeader = computed(() => props.forcePinnedDisplay || pinToHeader.value);

// Swatch styles
const bgSwatchStyle = computed(() =>
  getBaseSectionSwatchStyle(state.design, effectiveBgColor.value, {
    rawColor: bgColor.value,
    linkKey: bgColorLink.value,
    treatEmptyAsHighContrast: true,
    baseRefColor: state.design.sectionBackgroundColor || "#ffffff",
    baseRefKey: "sectionBackgroundColor",
    adminConfig: state.adminDesignConfig,
  })
);

const textSwatchStyle = computed(() =>
  getBaseSectionSwatchStyle(state.design, effectiveTextColor.value, {
    rawColor: textColor.value,
    linkKey: textColorLink.value,
    treatEmptyAsHighContrast: true,
    baseRefColor: resolvedBgBaseColor.value || state.design.sectionBackgroundColor || "#ffffff",
    baseRefKey: getBackgroundBaseKeyFromLink(bgColorLink.value) || "sectionBackgroundColor",
    adminConfig: state.adminDesignConfig,
  })
);

// Color picker values (for the native picker)
const HEX_RE = /^#[0-9a-fA-F]{6}$/;
const bgColorValue = computed(() => (HEX_RE.test(resolvedBgBaseColor.value || "") ? resolvedBgBaseColor.value : '#f1f5f9'));
const textColorValue = computed(() => (HEX_RE.test(resolvedTextBaseColor.value || "") ? resolvedTextBaseColor.value : '#0b1220'));

// Computed styles
const tickerStyle = computed(() => {
  const style = {};
  if (effectiveBgColor.value) style.background = effectiveBgColor.value;
  if (effectiveFontFamily.value) style.fontFamily = effectiveFontFamily.value;
  return style;
});

const itemStyle = computed(() => {
  const style = {};
  if (effectiveTextColor.value) style.color = effectiveTextColor.value;
  style.fontSize = `${fontSize.value}px`;
  return style;
});

const sepStyle = computed(() => {
  const style = {};
  if (effectiveTextColor.value) style.color = effectiveTextColor.value;
  style.fontSize = `${fontSize.value}px`;
  style.opacity = 0.5;
  return style;
});

const sepImageStyle = computed(() => ({
  width: `${fontSize.value}px`,
  height: `${fontSize.value}px`,
}));
const separatorImageAssetData = computed(() => ({
  imageUrl: String(separatorImageUrl.value || "").trim(),
  responsiveVariants: Array.isArray(separatorImageResponsiveVariants.value)
    ? separatorImageResponsiveVariants.value
    : [],
}));

// Save functions
function setBgColor(val) {
  bgColor.value = val;
  bgColorLink.value = null;
  updateSection(effectiveKey.value, { bgColor: val, bgColorLink: null }, { revisionKind: "design" });
}

function setTextColor(val) {
  textColor.value = val;
  textColorLink.value = null;
  updateSection(effectiveKey.value, { textColor: val, textColorLink: null }, { revisionKind: "design" });
}

function setBgColorVariation(value) {
  const normalized = normalizeColorVariation(value);
  bgColorVariation.value = normalized;
  updateSection(
    effectiveKey.value,
    { bgColorVariation: normalized === DEFAULT_COLOR_VARIATION ? null : normalized },
    { revisionKind: "design" }
  );
}

function setTextColorVariation(value) {
  const normalized = normalizeColorVariation(value);
  textColorVariation.value = normalized;
  updateSection(
    effectiveKey.value,
    { textColorVariation: normalized === DEFAULT_COLOR_VARIATION ? null : normalized },
    { revisionKind: "design" }
  );
}

function linkBgColor(key) {
  bgColorLink.value = key;
  bgColor.value = null;
  updateSection(effectiveKey.value, { bgColor: null, bgColorLink: key }, { revisionKind: "design" });
}

function linkTextColor(key) {
  textColorLink.value = key;
  textColor.value = null;
  updateSection(effectiveKey.value, { textColor: null, textColorLink: key }, { revisionKind: "design" });
}

function clearBgColor() {
  bgColor.value = null;
  bgColorLink.value = null;
  updateSection(effectiveKey.value, { bgColor: null, bgColorLink: null }, { revisionKind: "design" });
}

function clearTextColor() {
  textColor.value = null;
  textColorLink.value = null;
  updateSection(effectiveKey.value, { textColor: null, textColorLink: null }, { revisionKind: "design" });
}

function saveSeparator() {
  if (isTickerSectionFieldLocked("separator")) return;
  updateSection(effectiveKey.value, { separator: separator.value }, { revisionKind: "design" });
}

function saveSeparatorImageUrl() {
  if (isTickerSectionFieldLocked("separatorImageUrl")) return;
  const normalized = String(separatorImageUrl.value || '').trim() || null;
  const previous = String(section.value?.separatorImageUrl || "").trim() || null;
  separatorImageUrl.value = normalized;
  const nextPatch = {
    separatorImageUrl: normalized,
    separatorImageResponsiveVariants: Array.isArray(separatorImageResponsiveVariants.value)
      ? separatorImageResponsiveVariants.value
      : [],
  };
  if (normalized !== previous) {
    nextPatch.separatorImageResponsiveVariants = [];
    separatorImageResponsiveVariants.value = [];
  }
  updateSection(effectiveKey.value, nextPatch, { revisionKind: "design" });
}

function openSeparatorMediaPicker() {
  if (isTickerSectionFieldLocked("separatorImageUrl")) return;
  showSeparatorMediaPicker.value = true;
}

function onSeparatorImageSelect(selection) {
  if (isTickerSectionFieldLocked("separatorImageUrl")) {
    showSeparatorMediaPicker.value = false;
    return;
  }
  const normalized = selection && typeof selection === "object" ? selection : {};
  const media = resolveBackendResponsiveImagePayload(normalized, {
    urlKeys: ["url", "src", "href"],
  });
  separatorImageUrl.value = media.url || null;
  separatorImageResponsiveVariants.value = media.responsiveVariants;
  updateSection(
    effectiveKey.value,
    {
      separatorImageUrl: separatorImageUrl.value,
      separatorImageResponsiveVariants: Array.isArray(separatorImageResponsiveVariants.value)
        ? separatorImageResponsiveVariants.value
        : [],
    },
    { revisionKind: "design" }
  );
  showSeparatorMediaPicker.value = false;
}

function clearSeparatorImageUrl() {
  if (isTickerSectionFieldLocked("separatorImageUrl")) return;
  separatorImageUrl.value = null;
  separatorImageResponsiveVariants.value = [];
  updateSection(
    effectiveKey.value,
    {
      separatorImageUrl: null,
      separatorImageResponsiveVariants: [],
    },
    { revisionKind: "design" }
  );
}

function saveSpeed() {
  if (isTickerSectionFieldLocked("speed")) return;
  speed.value = normalizeSpeedValue(speed.value);
  updateSection(effectiveKey.value, { speed: speed.value }, { revisionKind: "design" });
}

function saveFontSize() {
  if (isTickerSectionFieldLocked("fontSize")) return;
  fontSize.value = normalizeFontSizeValue(fontSize.value);
  updateSection(effectiveKey.value, { fontSize: fontSize.value }, { revisionKind: "design" });
}

function saveFontFamily(rawValue) {
  if (isTickerSectionFieldLocked("fontFamily")) return;
  const normalized = String(rawValue || "").trim() || null;
  fontFamily.value = normalized;
  updateSection(effectiveKey.value, { fontFamily: normalized }, { revisionKind: "design" });
}

function tickerKeys() {
  return Object.keys(state.sectionsData || {}).filter((key) => {
    const sectionType = state.sectionsData?.[key]?.sectionType;
    return sectionType === 'ticker';
  });
}

const tickerInstanceKeys = computed(() => tickerKeys());
const hasOtherTickerInstance = computed(() =>
  tickerInstanceKeys.value.some((key) => key !== effectiveKey.value)
);
const isSlaveTicker = computed(() => shareItemsWithTickers.value === true);
const showShareItemsToggle = computed(() => hasOtherTickerInstance.value || isSlaveTicker.value);

const tickerInstances = computed(() =>
  tickerInstanceKeys.value
    .map((key, index) => {
      const data = state.sectionsData?.[key] || null;
      const sectionId = String(state.sectionIds?.[key] || "").trim();
      const label = localizedText(data?.title || {})
        || state.sectionMeta?.[key]?.title_placeholder
        || `Ticker ${index + 1}`;
      return {
        key,
        sectionId,
        data,
        label,
      };
    })
    .filter((entry) => entry.sectionId)
);

const masterOptions = computed(() =>
  tickerInstances.value.filter(
    (entry) => entry.key !== effectiveKey.value && entry.data?.shareItemsWithTickers !== true
  )
);

const resolvedMasterSectionId = computed(() => {
  if (!isSlaveTicker.value) return "";
  const selected = String(sharedTickerMasterSectionId.value || "").trim();
  if (selected && masterOptions.value.some((option) => option.sectionId === selected)) {
    return selected;
  }
  return masterOptions.value[0]?.sectionId || "";
});

const resolvedMasterOption = computed(() =>
  masterOptions.value.find((option) => option.sectionId === resolvedMasterSectionId.value) || null
);
const resolvedMasterLabel = computed(() => String(resolvedMasterOption.value?.label || "").trim());
const showMasterSelect = computed(() => isSlaveTicker.value && masterOptions.value.length > 1);

const masterSourceItems = computed(() => {
  if (!isSlaveTicker.value) return [];
  const masterItems = resolvedMasterOption.value?.data?.items;
  return cloneTickerItems(masterItems);
});

function togglePinToHeader(enabled) {
  pinToHeader.value = enabled;

  if (enabled) {
    for (const key of tickerKeys()) {
      if (key !== effectiveKey.value && state.sectionsData?.[key]?.pinToHeader) {
        updateSection(key, { pinToHeader: false }, { revisionKind: "design" });
      }
    }
  }

  updateSection(effectiveKey.value, { pinToHeader: enabled }, { revisionKind: "design" });
}

function cloneTickerItems(items) {
  const source = Array.isArray(items) ? items : [];
  return source.map((item, index) => {
    const id = String(item?.id || `ticker-${index + 1}`).trim();
    return {
      id: id || `ticker-${index + 1}`,
      timestamp: String(item?.timestamp || "").trim(),
      text: {
        de: String(item?.text?.de ?? ""),
        en: String(item?.text?.en ?? ""),
      },
    };
  });
}

const editableItems = computed(() => cloneTickerItems(section.value?.items));

function hasTickerTextContent(item) {
  return String(item?.text?.de ?? "").trim().length > 0
    || String(item?.text?.en ?? "").trim().length > 0;
}

function hasTickerContent(item) {
  return String(item?.timestamp ?? "").trim().length > 0
    || hasTickerTextContent(item);
}

function toPersistedTickerItems(items) {
  const source = Array.isArray(items) ? items : [];
  return cloneTickerItems(source);
}

function isTickerDraftInSyncWithSection() {
  return JSON.stringify(toPersistedTickerItems(editableItems.value))
    === JSON.stringify(toPersistedTickerItems(draft.value));
}

const baseItems = computed(() => {
  const items = viewMode.value !== "updates" && isSlaveTicker.value
    ? masterSourceItems.value
    : editableItems.value;
  const visibleItems = publicView.value ? items.filter((item) => hasTickerTextContent(item)) : items;
  if (visibleItems.length) return visibleItems;
  return publicView.value ? [] : [{ id: "x", text: { de: "...", en: "..." } }];
});

watch(
  () => JSON.stringify(editableItems.value || []),
  () => {
    if (!state.isAdmin) return;
    if (adminTab.value !== "content") return;
    if (viewMode.value !== "updates" && isSlaveTicker.value) return;
    if (isTickerDraftInSyncWithSection()) return;
    const prevExpanded = expandedItem.value;
    startEdit();
    if (prevExpanded >= 0 && prevExpanded < draft.value.length) {
      expandedItem.value = prevExpanded;
    }
  }
);

// Estimate sequence metrics for seamless looping + responsive speed calculation
const sequenceMetrics = computed(() => {
  const base = baseItems.value;
  const fs = normalizeFontSizeValue(fontSize.value);
  const avgCharWidth = Math.max(6, fs * 0.58);
  const sepWidth = separatorImageUrl.value ? fs + 26 : fs + 28;
  
  // Estimate total width of one sequence
  let seqWidthBase = 0;
  for (const item of base) {
    const text = localizedText(item.text) || '';
    seqWidthBase += text.length * avgCharWidth + sepWidth;
  }
  
  // We need at least 2x container width to ensure seamless looping
  const targetWidth = containerWidth.value * 2.5;
  const repeatCount = Math.max(2, Math.ceil(targetWidth / Math.max(seqWidthBase, 100)));
  const sequenceDistance = Math.max(200, seqWidthBase * repeatCount);

  return { repeatCount, sequenceDistance };
});

// Duration is derived from the actual distance for consistent px/sec speed
const duration = computed(() => {
  const pxPerSec = normalizeSpeedValue(speed.value) || DEFAULT_SPEED_PX_PER_SEC;
  const rawDuration = sequenceMetrics.value.sequenceDistance / pxPerSec;
  // Keep practical bounds to avoid too-fast/too-slow edge cases
  return Math.max(24, Math.min(220, rawDuration));
});

// Calculate repeated items for seamless loop
const filledItems = computed(() => {
  const base = baseItems.value;
  const repeatCount = sequenceMetrics.value.repeatCount;
  
  const out = [];
  for (let r = 0; r < repeatCount; r++) {
    for (let i = 0; i < base.length; i++) {
      const it = base[i];
      out.push({ ...it, _k: `${it.id}_${r}_${i}` });
    }
  }
  return out;
});

function startEdit() {
  expandedItem.value = -1;
  draft.value = editableItems.value.map((x) => ({
    id: x.id,
    timestamp: String(x.timestamp || "").trim(),
    text: {
      de: x.text?.de ?? "",
      en: x.text?.en ?? "",
    },
  }));
}

function currentServerWallDateTime() {
  const now = getCurrentServerWallDate();
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

function add() {
  draft.value.push({
    id: String(Date.now() + Math.random()),
    timestamp: currentServerWallDateTime(),
    text: { de: "", en: "" },
  });
  expandedItem.value = draft.value.length - 1;
  save({ flush: true });
}

function remove(i) {
  if (i < 0 || i >= draft.value.length) return;
  draft.value.splice(i, 1);
  if (expandedItem.value === i) {
    expandedItem.value = draft.value.length ? Math.min(i, draft.value.length - 1) : -1;
  } else if (expandedItem.value > i) {
    expandedItem.value -= 1;
  }
}

function save(options = {}) {
  if (viewMode.value !== "updates" && isSlaveTicker.value) return;
  const filtered = toPersistedTickerItems(draft.value);

  updateSection(
    effectiveKey.value,
    {
      items: filtered,
      shareItemsWithTickers: false,
      sharedTickerMasterSectionId: null,
    },
    { revisionKind: "content" }
  );
  if (options?.flush) {
    void saveSectionByKey(effectiveKey.value, { revisionKind: "content" });
  }
}

function saveShareMode(enabled) {
  const nextEnabled = enabled === true;
  shareItemsWithTickers.value = nextEnabled;
  if (nextEnabled) {
    const nextMasterId = resolvedMasterSectionId.value || masterOptions.value[0]?.sectionId || "";
    if (!nextMasterId) {
      shareItemsWithTickers.value = false;
      return;
    }
    sharedTickerMasterSectionId.value = nextMasterId;
    expandedItem.value = -1;
    draft.value = [];
    updateSection(
      effectiveKey.value,
      {
        shareItemsWithTickers: true,
        sharedTickerMasterSectionId: nextMasterId || null,
      },
      { revisionKind: "content" }
    );
    return;
  }

  const seededItems = cloneTickerItems(baseItems.value).filter((item) =>
    String(item.text?.de ?? "").trim().length > 0 || String(item.text?.en ?? "").trim().length > 0
  );
  sharedTickerMasterSectionId.value = "";
  updateSection(
    effectiveKey.value,
    {
      shareItemsWithTickers: false,
      sharedTickerMasterSectionId: null,
      items: seededItems,
    },
    { revisionKind: "content" }
  );
  if (adminTab.value === "content") {
    startEdit();
  }
}

// ── Updates mode ────────────────────────────────────────────────────────────

const MAX_UPDATES = 5;

function parseUpdateTimestamp(ts) {
  return serverWallDateTimeToLocalDate(ts) || parseRevisionTimestamp(ts);
}

const sortedUpdates = computed(() => {
  const visibleItems = publicView.value
    ? editableItems.value.filter((item) => hasTickerContent(item))
    : editableItems.value;
  return [...visibleItems]
    .sort((a, b) => {
      const tA = a.timestamp ? parseUpdateTimestamp(a.timestamp)?.getTime() || 0 : 0;
      const tB = b.timestamp ? parseUpdateTimestamp(b.timestamp)?.getTime() || 0 : 0;
      return tB - tA; // newest first
    })
    .slice(0, MAX_UPDATES);
});

const groupedUpdates = computed(() => {
  const groupMap = new Map();
  for (const item of sortedUpdates.value) {
    let dayKey = "—";
    let dayLabel = "—";
    if (item.timestamp) {
      try {
        const d = parseUpdateTimestamp(item.timestamp);
        if (!isNaN(d.getTime())) {
          dayKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
          dayLabel = formatServerDateOnly(
            dayKey,
            { day: "numeric", month: "long", year: "numeric" },
            { locale: state.lang === "de" ? "de-DE" : "en-US", fallback: dayKey }
          );
        }
      } catch { /* ignore */ }
    }
    if (!groupMap.has(dayKey)) groupMap.set(dayKey, { dayKey, dayLabel, items: [] });
    groupMap.get(dayKey).items.push(item);
  }
  return [...groupMap.values()].sort((a, b) => b.dayKey.localeCompare(a.dayKey));
});

const dayLabelStyle = computed(() => ({
  color: effectiveTextColor.value || undefined,
  fontSize: `${Math.max(10, Math.round((fontSize.value || 16) * 0.72))}px`,
}));

function formatUpdateTime(ts) {
  if (!ts) return "";
  try {
    const wallTime = formatServerWallTime(
      ts,
      { timeStyle: "short" },
      { locale: state.lang === "de" ? "de-DE" : "en-US" }
    );
    if (wallTime) return wallTime;
    return formatInstantInServerTimezone(
      ts,
      { timeStyle: "short" },
      { locale: state.lang === "de" ? "de-DE" : "en-US" }
    );
  } catch {
    return "";
  }
}

// kept for use in admin item thumb label
function formatUpdateTimestamp(ts) {
  if (!ts) return "";
  try {
    const d = parseUpdateTimestamp(ts);
    if (!d || isNaN(d.getTime())) return ts;
    const dayKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const date = formatServerDateOnly(
      dayKey,
      { dateStyle: "short" },
      { locale: state.lang === "de" ? "de-DE" : "en-US", fallback: dayKey }
    );
    const time = formatServerWallTime(
      ts,
      { timeStyle: "short" },
      { locale: state.lang === "de" ? "de-DE" : "en-US" }
    ) || formatInstantInServerTimezone(
      ts,
      { timeStyle: "short" },
      { locale: state.lang === "de" ? "de-DE" : "en-US" }
    );
    return [date, time].filter(Boolean).join(", ");
  } catch {
    return ts;
  }
}

function tickerEditorItemLabel(item, index) {
  return item?.text?.de
    || item?.text?.en
    || (viewMode.value === "updates" ? formatUpdateTimestamp(item?.timestamp) : "")
    || `#${index + 1}`;
}

function setViewMode(mode) {
  if (isTickerSectionFieldLocked("viewMode")) return;
  viewMode.value = mode === "updates" ? "updates" : "ticker";
  updateSection(effectiveKey.value, { viewMode: viewMode.value }, { revisionKind: "design" });
  if (adminTab.value === "content") {
    if (viewMode.value !== "updates" && isSlaveTicker.value) {
      expandedItem.value = -1;
      draft.value = [];
    } else {
      startEdit();
    }
  }
}

function saveMasterSelection(nextMasterSectionId) {
  if (!isSlaveTicker.value) return;
  const normalizedId = String(nextMasterSectionId || "").trim();
  if (!normalizedId) return;
  if (!masterOptions.value.some((option) => option.sectionId === normalizedId)) return;
  sharedTickerMasterSectionId.value = normalizedId;
  updateSection(
    effectiveKey.value,
    {
      shareItemsWithTickers: true,
      sharedTickerMasterSectionId: normalizedId,
    },
    { revisionKind: "content" }
  );
}
</script>

<style scoped>
.ticker {
  position: relative;
  width: 100%;
  padding: 12px 2px;
  overflow: hidden;
  background: var(--surface-2);
}

.ticker-public-hidden-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 20;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--accent, #4f46e5);
  background: rgba(79, 70, 229, 0.08);
  border-radius: 3px;
  padding: 2px 6px;
}

.ticker--pinned-header {
  border-radius: 0;
}

/* Admin Controls */
.ticker-admin-controls {
  display: block;
  padding: 2px;
  cursor: default;
}

.ticker-admin-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
}

.ctrl-group {
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 10px;
  padding: 9px;
  background: #fff;
}

.ctrl-group-title {
  font-size: 10px;
  font-weight: 800;
  color: var(--admin-text-muted, #64748b);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 8px;
}

.ctrl-list {
  display: grid;
  gap: 8px;
}

.ctrl {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.pin-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.share-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 12px;
  color: #334155;
}

.slave-config {
  margin-bottom: 12px;
  padding: 10px;
  border: 1px dashed var(--border, #cbd5e1);
  border-radius: 8px;
  background: #f8fafc;
}

.slave-hint {
  margin: 0;
  font-size: 12px;
  color: #475569;
}

.ctrl-label {
  font-size: 10px;
  font-weight: 700;
  color: var(--admin-text-muted, #64748b);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.ctrl-select {
  padding: 5px 8px;
  font-size: 12px;
  border-radius: 6px;
  border: 1px solid var(--border, #e2e8f0);
  background: #fff;
  min-width: 90px;
}

.ctrl-input {
  padding: 5px 8px;
  font-size: 12px;
  border-radius: 6px;
  border: 1px solid var(--border, #e2e8f0);
  background: #fff;
  min-width: 180px;
}

.sep-image-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 6px;
  width: 100%;
  min-width: 0;
}

.sep-image-controls .ctrl-input {
  min-width: 0;
  width: 100%;
}

.speed-control {
  display: flex;
  align-items: center;
  gap: 8px;
}

.speed-slider {
  width: 130px;
}

.speed-value {
  font-size: 11px;
  color: var(--admin-text-muted, #64748b);
  min-width: 52px;
  text-align: right;
}

.color-ctrl {
  flex-direction: row;
  align-items: center;
  gap: 6px;
}

.variation-select {
  min-width: 68px;
  padding: 4px 6px;
  border-radius: 8px;
  border: 1px solid var(--border, #e2e8f0);
  background: #fff;
  font-size: 12px;
}

.color-ctrl .pin-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.ctrl-label {
  min-width: 70px;
}

.color-swatch {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  border: 1px solid var(--border, #e2e8f0);
  cursor: pointer;
  flex-shrink: 0;
}

.color-input-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.viewport { overflow: hidden; }

/* Updates stack */
.updates-stack {
  list-style: none;
  margin: 0;
  padding: 10px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.update-day-header {
  font-weight: 800;
  opacity: 0.35;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-top: 6px;
  padding-bottom: 2px;
  border-bottom: 1px solid currentColor;
}

.update-day-header:first-child {
  margin-top: 0;
}

.update-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.update-bullet {
  flex-shrink: 0;
  font-weight: 700;
  opacity: 0.6;
  line-height: 1;
}

.update-body {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 10px;
  min-width: 0;
}

.update-time {
  flex-shrink: 0;
  font-size: 0.78em;
  font-weight: 700;
  opacity: 0.55;
  white-space: nowrap;
}

.update-desc {
  font-weight: 600;
  line-height: 1.35;
}

.update-empty {
  opacity: 0.45;
  font-weight: 600;
  padding: 2px 0;
}

.track {
  display: flex;
  width: max-content;
  animation-name: marquee-left;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}

.seq {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}

.item {
  color: var(--text);
  font-weight: 600;
}

.sep {
  color: var(--muted-2);
  margin: 0 14px;
  font-weight: 600;
}

.sep-image {
  width: 18px;
  height: 18px;
  object-fit: contain;
  margin: 0 12px;
  flex: 0 0 auto;
  opacity: 0.95;
}

@media (max-width: 760px) {
  .ticker-admin-grid {
    grid-template-columns: 1fr;
  }
}

@keyframes marquee-left {
  0%   { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

.thumb-num {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--surface-2, #eef2f7);
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 800;
  color: var(--muted, #64748b);
  flex-shrink: 0;
}

.lang-section {
  display: grid;
  gap: 4px;
}

.lang-header {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field {
  width: 100%;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: #fff;
  padding: 10px 12px;
  outline: none;
  color: var(--text);
}

.ticker-datetime-picker {
  width: 100%;
}

.ticker-datetime-picker :deep(.dp__input_wrap) {
  width: 100%;
}

.ticker-datetime-picker :deep(.dp__input) {
  width: 100%;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: #fff;
  outline: none;
  color: var(--text);
  font: inherit;
}

.ticker-datetime-picker :deep(.dp__input:focus) {
  border-color: rgba(59, 130, 246, 0.55);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
</style>
