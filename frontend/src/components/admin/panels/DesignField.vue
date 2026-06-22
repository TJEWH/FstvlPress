<template>
  <div class="design-field-wrap">
    <!-- Checkbox -->
    <div v-if="config.type === 'checkbox'" class="field checkbox-field">
      <div class="checkbox-row">
        <input
          type="checkbox"
          :id="`checkbox-${paramKey}`"
          :checked="effectiveCheckboxValue"
          @change="onCheckboxChange($event.target.checked)"
        />
        <label :for="`checkbox-${paramKey}`" class="field-label">
          {{ config.label }}
          <button
            v-if="hasOverrideSources"
            ref="overrideInfoBtnRef"
            class="override-info-icon override-info-btn"
            type="button"
            @click.stop.prevent="toggleOverrideSourceMenu"
            :title="overrideInfo"
            aria-label="Show overriding sections"
          >!</button>
          <span v-else-if="overrideInfo" class="override-info-icon" :title="overrideInfo" aria-label="Override info">!</span>
        </label>
        <!-- Responsive mode toggle (media query only) -->
        <button
          ref="responsiveBtnRef"
          class="responsive-toggle-btn"
          :class="{ active: config.responsive === 'media' }"
          type="button"
          @click="config.responsive === 'media' ? clearResponsiveMode() : setResponsiveMode('media')"
          title="Toggle media query responsiveness"
        >
          <font-awesome-icon :icon="faDisplay" class="responsive-toggle-icon" />
        </button>
        <button
          v-if="config.responsive === 'media'"
          class="responsive-clear-btn"
          type="button"
          @click="clearResponsiveMode"
          title="Clear responsive settings"
        >✕</button>
      </div>
      <button
        v-if="isNullable && value != null"
        class="clear-field-btn clear-corner"
        type="button"
        @click="emit('update', paramKey, null)"
        title="Reset"
      >✕</button>
      <!-- Media query device row -->
      <div v-if="config.responsive === 'media' && !hideResponsive" class="responsive-detail media-detail">
        <div
          v-for="d in devices"
          :key="d.key"
          class="resp-val"
          :class="{ 'resp-active': activeDevice === d.key, 'resp-linked': d.key === 'desktop' && !activeDevice }"
          @click="handleDeviceButtonClick(d.key)"
          :title="d.key === 'desktop' ? 'Desktop (click to end simulation)' : d.label"
        >
          <span class="resp-label">
            <font-awesome-icon :icon="getDeviceIcon(d.key)" class="resp-device-icon" />
          </span>
          <span class="resp-num">{{ getCheckboxLabel(d.key) }}</span>
        </div>
      </div>
    </div>

    <!-- Slider -->
    <label v-else-if="config.type === 'slider'" class="field" @click.prevent>
      <div class="field-label-row">
        <span class="field-label">
          {{ sliderLabel }}
          <button
            v-if="hasOverrideSources"
            ref="overrideInfoBtnRef"
            class="override-info-icon override-info-btn"
            type="button"
            @click.stop.prevent="toggleOverrideSourceMenu"
            :title="overrideInfo"
            aria-label="Show overriding sections"
          >!</button>
          <span v-else-if="overrideInfo" class="override-info-icon" :title="overrideInfo" aria-label="Override info">!</span>
        </span>
        <!-- Responsive mode toggle -->
        <button
          ref="responsiveBtnRef"
          class="responsive-toggle-btn"
          :class="{ active: !!config.responsive }"
          type="button"
          @click="toggleResponsiveMenu"
          :title="config.responsive ? `Responsive: ${config.responsive}` : 'Make responsive'"
        >
          <font-awesome-icon :icon="faDisplay" class="responsive-toggle-icon" />
        </button>
        <button
          v-if="config.responsive"
          class="responsive-clear-btn"
          type="button"
          @click="clearResponsiveMode"
          title="Clear responsive settings"
        >✕</button>
        <Teleport to="body">
          <div v-if="showResponsiveMenu" class="responsive-mode-menu" :style="responsiveMenuPos" @click.stop>
            <button
              class="resp-mode-item"
              :class="{ active: config.responsive === 'clamp' }"
              @click="setResponsiveMode('clamp')"
            >Clamp <span class="resp-mode-hint">min ← rel → max</span></button>
            <button
              class="resp-mode-item"
              :class="{ active: config.responsive === 'media' }"
              @click="setResponsiveMode('media')"
            >Media Query <span class="resp-mode-hint">Mobile / Tablet / Desktop</span></button>
          </div>
        </Teleport>
      </div>

      <div class="range-field" :class="{ 'slider-muted': showResponsiveUI && config.responsive === 'clamp' && !activeClampTab }">
        <!-- Text input mode for advanced values like calc() -->
        <template v-if="config.allowInput">
          <span class="advanced-label">Advanced</span>
          <input
            type="text"
            class="advanced-input"
            :value="effectiveAdvancedValue"
            :placeholder="advancedPlaceholder"
            @input="onAdvancedInput($event.target.value)"
          />
        </template>
        <!-- Standard slider mode -->
        <template v-else>
          <input
            type="range"
            :min="activeUnitConfig.min ?? 0"
            :max="activeUnitConfig.max ?? 100"
            :step="activeUnitConfig.step ?? 1"
            :value="effectiveSliderValue"
            @input="onSliderInput"
          />
          <span class="range-value">{{ formatEffectiveSliderDisplay }}</span>
          <template v-if="config.responsive === 'clamp' && activeClampTab">
            <span class="range-unit">{{ displayedSliderUnit || '' }}</span>
          </template>
          <template v-else>
            <select
              v-if="hasMultipleUnits"
              class="unit-select"
              :value="activeUnit"
              @change="onUnitChange($event.target.value)"
            >
              <option v-for="uc in unitConfigs" :key="uc.unit" :value="uc.unit">{{ uc.unit || 'none' }}</option>
            </select>
            <span v-else class="range-unit">{{ activeUnit }}</span>
          </template>
        </template>

        <button
          v-if="isNullable && value != null"
          class="clear-field-btn"
          :class="{ 'clear-corner': props.forceNullable }"
          type="button"
          @click="emit('update', paramKey, null)"
          title="Reset"
        >✕</button>
      </div>

      <!-- Clamp detail row - similar to media query with selectable tabs -->
      <div v-if="config.responsive === 'clamp' && !hideResponsive" class="responsive-detail clamp-detail">
        <div
          class="resp-val"
          :class="{ 'resp-active': activeClampTab === 'min' }"
          @click="toggleClampTab('min')"
          title="Click to control min value with slider"
        >
          <span class="resp-label">Min</span>
          <span class="resp-num">{{ respVals.min ?? '–' }}</span>
          <select
            v-if="!config.allowInput"
            class="clamp-unit-select"
            :value="respVals.minUnit || activeUnit"
            @click.stop
            @change="updateResponsive({ minUnit: $event.target.value })"
          >
            <option v-for="uc in absoluteUnitConfigs" :key="uc.unit" :value="uc.unit">{{ uc.unit || 'none' }}</option>
          </select>
        </div>
        <div
          class="resp-val"
          :class="{ 'resp-active': activeClampTab === 'preferred' }"
          @click="toggleClampTab('preferred')"
          title="Click to control preferred value with slider"
        >
          <span class="resp-label">Pref</span>
          <span class="resp-num">{{ respVals.preferred ?? '–' }}</span>
          <select
            v-if="!config.allowInput"
            class="clamp-unit-select"
            :value="respVals.preferredUnit || 'vw'"
            @click.stop
            @change="updateResponsive({ preferredUnit: $event.target.value })"
          >
            <option v-for="uc in relativeUnitConfigs" :key="uc.unit" :value="uc.unit">{{ uc.unit }}</option>
          </select>
        </div>
        <div
          class="resp-val"
          :class="{ 'resp-active': activeClampTab === 'max' }"
          @click="toggleClampTab('max')"
          title="Click to control max value with slider"
        >
          <span class="resp-label">Max</span>
          <span class="resp-num">{{ respVals.max ?? '–' }}</span>
          <select
            v-if="!config.allowInput"
            class="clamp-unit-select"
            :value="respVals.maxUnit || activeUnit"
            @click.stop
            @change="updateResponsive({ maxUnit: $event.target.value })"
          >
            <option v-for="uc in absoluteUnitConfigs" :key="uc.unit" :value="uc.unit">{{ uc.unit || 'none' }}</option>
          </select>
        </div>
      </div>

      <!-- Media query detail row -->
      <div v-if="config.responsive === 'media' && !hideResponsive" class="responsive-detail media-detail">
        <div
          v-for="d in devices"
          :key="d.key"
          class="resp-val"
          :class="{ 'resp-active': activeDevice === d.key, 'resp-linked': d.key === 'desktop' && !activeDevice }"
          @click="handleDeviceButtonClick(d.key)"
          :title="d.key === 'desktop' ? 'Desktop (click to end simulation)' : d.label"
        >
          <span class="resp-label">
            <font-awesome-icon :icon="getDeviceIcon(d.key)" class="resp-device-icon" />
          </span>
          <span class="resp-num">{{ d.key === 'desktop' ? (value ?? '–') : (respVals[d.key] ?? '–') }}{{ config.allowInput ? '' : activeUnit }}</span>
        </div>
      </div>
    </label>

    <!-- Color -->
    <label v-else-if="config.type === 'color'" class="field color-field">
      <span class="field-label">
        {{ colorLabel }}
        <button
          v-if="hasOverrideSources"
          ref="overrideInfoBtnRef"
          class="override-info-icon override-info-btn"
          type="button"
          @click.stop.prevent="toggleOverrideSourceMenu"
          :title="overrideInfo"
          aria-label="Show overriding sections"
        >!</button>
        <span v-else-if="overrideInfo" class="override-info-icon" :title="overrideInfo" aria-label="Override info">!</span>
      </span>
      <div
        class="color-input-group"
        :class="{ 'with-corner-clear': props.forceNullable && isNullable && value != null }"
      >
        <VueColorPicker
          :model-value="colorValue"
          :fallback-color="colorValue"
          :preview-style="specialColorPreview"
          :size="32"
          @update:model-value="onColorValueInput"
        />
        <ColorLinkPicker
          v-if="showColorLinkPicker"
          :model-value="currentLink"
          :options="allLinkableColors"
          :button-size="26"
          @link="linkToBaseColor"
        />
        <select
          v-if="supportsColorVariation"
          class="color-variation-select"
          :value="currentColorVariation"
          @change="onColorVariationChange($event.target.value)"
        >
          <option v-for="variation in colorVariationOptions" :key="variation" :value="variation">
            {{ variation }}%
          </option>
        </select>
        <button
          v-if="isNullable && value != null"
          class="clear-field-btn"
          :class="{ 'clear-corner': props.forceNullable }"
          type="button"
          @click="emit('update', paramKey, null)"
          title="Reset"
        >✕</button>
      </div>
    </label>

    <!-- Font Family (no responsive - uses global font definitions) -->
    <label v-else-if="config.type === 'fontfamily'" class="field">
      <span class="field-label">
        {{ config.label }}
        <button
          v-if="hasOverrideSources"
          ref="overrideInfoBtnRef"
          class="override-info-icon override-info-btn"
          type="button"
          @click.stop.prevent="toggleOverrideSourceMenu"
          :title="overrideInfo"
          aria-label="Show overriding sections"
        >!</button>
        <span v-else-if="overrideInfo" class="override-info-icon" :title="overrideInfo" aria-label="Override info">!</span>
      </span>
      <select :value="value" @change="emit('update', paramKey, $event.target.value)">
        <option v-for="font in fontFamilies" :key="font.value" :value="font.value">
          {{ font.label }}
        </option>
      </select>
      <button
        v-if="isNullable && value != null"
        class="clear-field-btn clear-corner"
        type="button"
        @click="emit('update', paramKey, null)"
        title="Reset"
      >✕</button>
    </label>

    <!-- Dropdown -->
    <div v-else-if="config.type === 'dropdown'" class="field">
      <div class="field-label-row">
        <span class="field-label">
          {{ config.label }}
          <button
            v-if="hasOverrideSources"
            ref="overrideInfoBtnRef"
            class="override-info-icon override-info-btn"
            type="button"
            @click.stop.prevent="toggleOverrideSourceMenu"
            :title="overrideInfo"
            aria-label="Show overriding sections"
          >!</button>
          <span v-else-if="overrideInfo" class="override-info-icon" :title="overrideInfo" aria-label="Override info">!</span>
        </span>
        <!-- Responsive mode toggle (media query only) -->
        <button
          ref="responsiveBtnRef"
          class="responsive-toggle-btn"
          :class="{ active: config.responsive === 'media' }"
          type="button"
          @click="config.responsive === 'media' ? clearResponsiveMode() : setResponsiveMode('media')"
          title="Toggle media query responsiveness"
        >
          <font-awesome-icon :icon="faDisplay" class="responsive-toggle-icon" />
        </button>
        <button
          v-if="config.responsive === 'media'"
          class="responsive-clear-btn"
          type="button"
          @click="clearResponsiveMode"
          title="Clear responsive settings"
        >✕</button>
      </div>
      <select :value="effectiveDropdownValue" @change="onDropdownChange($event.target.value)">
        <option
          v-for="opt in dropdownOptions"
          :key="opt.value"
          :value="opt.value"
        >{{ opt.label }}</option>
      </select>
      <button
        v-if="isNullable && value != null"
        class="clear-field-btn clear-corner"
        type="button"
        @click="emit('update', paramKey, null)"
        title="Reset"
      >✕</button>
      <!-- Media query device row -->
      <div v-if="config.responsive === 'media' && !hideResponsive" class="responsive-detail media-detail">
        <div
          v-for="d in devices"
          :key="d.key"
          class="resp-val"
          :class="{ 'resp-active': activeDevice === d.key, 'resp-linked': d.key === 'desktop' && !activeDevice }"
          @click="handleDeviceButtonClick(d.key)"
          :title="d.key === 'desktop' ? 'Desktop (click to end simulation)' : d.label"
        >
          <span class="resp-label">
            <font-awesome-icon :icon="getDeviceIcon(d.key)" class="resp-device-icon" />
          </span>
          <span class="resp-num">{{ getDeviceOptionLabel(d.key) }}</span>
        </div>
      </div>
    </div>

    <!-- Button Group -->
    <div v-else-if="config.type === 'buttongroup'" class="field">
      <div class="field-label-row">
        <span class="field-label">
          {{ config.label }}
          <button
            v-if="hasOverrideSources"
            ref="overrideInfoBtnRef"
            class="override-info-icon override-info-btn"
            type="button"
            @click.stop.prevent="toggleOverrideSourceMenu"
            :title="overrideInfo"
            aria-label="Show overriding sections"
          >!</button>
          <span v-else-if="overrideInfo" class="override-info-icon" :title="overrideInfo" aria-label="Override info">!</span>
        </span>
        <!-- Responsive mode toggle (media query only) -->
        <button
          ref="responsiveBtnRef"
          class="responsive-toggle-btn"
          :class="{ active: config.responsive === 'media' }"
          type="button"
          @click="config.responsive === 'media' ? clearResponsiveMode() : setResponsiveMode('media')"
          title="Toggle media query responsiveness"
        >
          <font-awesome-icon :icon="faDisplay" class="responsive-toggle-icon" />
        </button>
        <button
          v-if="config.responsive === 'media'"
          class="responsive-clear-btn"
          type="button"
          @click="clearResponsiveMode"
          title="Clear responsive settings"
        >✕</button>
      </div>
      <div class="btn-group">
        <button
          v-for="opt in buttonGroupOptions"
          :key="opt.value"
          type="button"
          class="btn-group-item"
          :class="{ active: effectiveButtonGroupValue === opt.value }"
          @click="onButtonGroupClick(opt.value)"
        >{{ opt.label }}</button>
      </div>
      <button
        v-if="isNullable && value != null"
        class="clear-field-btn clear-corner"
        type="button"
        @click="emit('update', paramKey, null)"
        title="Reset"
      >✕</button>
      <!-- Media query device row -->
      <div v-if="config.responsive === 'media' && !hideResponsive" class="responsive-detail media-detail">
        <div
          v-for="d in devices"
          :key="d.key"
          class="resp-val"
          :class="{ 'resp-active': activeDevice === d.key, 'resp-linked': d.key === 'desktop' && !activeDevice }"
          @click="handleDeviceButtonClick(d.key)"
          :title="d.key === 'desktop' ? 'Desktop (click to end simulation)' : d.label"
        >
          <span class="resp-label">
            <font-awesome-icon :icon="getDeviceIcon(d.key)" class="resp-device-icon" />
          </span>
          <span class="resp-num">{{ getDeviceOptionLabel(d.key) }}</span>
        </div>
      </div>
    </div>

    <!-- Textarea -->
    <label v-else-if="config.type === 'textarea'" class="field">
      <span class="field-label">
        {{ config.label }}
        <button
          v-if="hasOverrideSources"
          ref="overrideInfoBtnRef"
          class="override-info-icon override-info-btn"
          type="button"
          @click.stop.prevent="toggleOverrideSourceMenu"
          :title="overrideInfo"
          aria-label="Show overriding sections"
        >!</button>
        <span v-else-if="overrideInfo" class="override-info-icon" :title="overrideInfo" aria-label="Override info">!</span>
      </span>
      <textarea
        class="css-textarea"
        :value="value || ''"
        :placeholder="config.placeholder || 'Enter CSS...'"
        rows="4"
        @input="emit('update', paramKey, $event.target.value || '')"
      ></textarea>
      <button
        v-if="isNullable && value != null"
        class="clear-field-btn clear-corner"
        type="button"
        @click="emit('update', paramKey, null)"
        title="Reset"
      >✕</button>
    </label>

    <!-- Image -->
    <div v-else-if="config.type === 'image'" class="field image-field">
      <span class="field-label">
        {{ config.label }}
        <button
          v-if="hasOverrideSources"
          ref="overrideInfoBtnRef"
          class="override-info-icon override-info-btn"
          type="button"
          @click.stop.prevent="toggleOverrideSourceMenu"
          :title="overrideInfo"
          aria-label="Show overriding sections"
        >!</button>
        <span v-else-if="overrideInfo" class="override-info-icon" :title="overrideInfo" aria-label="Override info">!</span>
      </span>
      <div class="image-field-preview" :class="{ empty: !imagePreviewUrl }">
        <img
          v-if="imagePreviewUrl"
          :src="imagePreviewUrl"
          alt="Selected image"
          class="image-field-preview-img"
          loading="lazy"
          decoding="async"
        />
        <span v-else class="image-field-empty">No image selected</span>
      </div>
      <div class="image-field-actions">
        <button type="button" class="image-field-btn" @click="openImageLibrary">
          {{ imagePreviewUrl ? "Replace image" : "Select image" }}
        </button>
      </div>
      <button
        v-if="isNullable && value != null"
        class="clear-field-btn clear-corner"
        type="button"
        @click="emit('update', paramKey, null)"
        title="Reset"
      >✕</button>
      <MediaLibrary
        :is-open="imageLibraryOpen"
        :current-url="imagePreviewUrl"
        :source-context="imageSourceContext"
        :allow-clear-selection="true"
        @close="closeImageLibrary"
        @select="onImageSelect"
      />
    </div>

    <!-- Position Grid -->
    <div v-else-if="config.type === 'positiongrid'" class="field">
      <div class="field-label-row">
        <span class="field-label">
          {{ config.label }}
          <button
            v-if="hasOverrideSources"
            ref="overrideInfoBtnRef"
            class="override-info-icon override-info-btn"
            type="button"
            @click.stop.prevent="toggleOverrideSourceMenu"
            :title="overrideInfo"
            aria-label="Show overriding sections"
          >!</button>
          <span v-else-if="overrideInfo" class="override-info-icon" :title="overrideInfo" aria-label="Override info">!</span>
        </span>
        <!-- Responsive mode toggle (media query only) -->
        <button
          ref="responsiveBtnRef"
          class="responsive-toggle-btn"
          :class="{ active: config.responsive === 'media' }"
          type="button"
          @click="config.responsive === 'media' ? clearResponsiveMode() : setResponsiveMode('media')"
          title="Toggle media query responsiveness"
        >
          <font-awesome-icon :icon="faDisplay" class="responsive-toggle-icon" />
        </button>
        <button
          v-if="config.responsive === 'media'"
          class="responsive-clear-btn"
          type="button"
          @click="clearResponsiveMode"
          title="Clear responsive settings"
        >✕</button>
      </div>
      <div class="position-grid">
        <button
          v-for="pos in overlayPositions"
          :key="pos.value"
          type="button"
          class="pos-btn"
          :class="{ active: effectivePositionGridValue === pos.value }"
          @click="onPositionGridClick(pos.value)"
          :title="pos.label"
        >{{ pos.icon }}</button>
      </div>
      <button
        v-if="isNullable && value != null"
        class="clear-field-btn clear-corner"
        type="button"
        @click="emit('update', paramKey, null)"
        title="Reset"
      >✕</button>
      <!-- Media query device row -->
      <div v-if="config.responsive === 'media' && !hideResponsive" class="responsive-detail media-detail">
        <div
          v-for="d in devices"
          :key="d.key"
          class="resp-val"
          :class="{ 'resp-active': activeDevice === d.key, 'resp-linked': d.key === 'desktop' && !activeDevice }"
          @click="handleDeviceButtonClick(d.key)"
          :title="d.key === 'desktop' ? 'Desktop (click to end simulation)' : d.label"
        >
          <span class="resp-label">
            <font-awesome-icon :icon="getDeviceIcon(d.key)" class="resp-device-icon" />
          </span>
          <span class="resp-num">{{ getPositionLabel(d.key) }}</span>
        </div>
      </div>
    </div>
    <Teleport to="body">
      <div v-if="showOverrideSourceMenu" class="override-source-menu" :style="overrideSourceMenuPos" @click.stop>
        <button
          v-for="source in overrideSources"
          :key="source.key"
          class="override-source-item"
          @click="openOverrideSource(source.key)"
        >{{ source.label }}</button>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from "vue";
import {
  faDesktop,
  faDisplay,
  faMobileScreenButton,
  faTabletScreenButton,
} from "@fortawesome/free-solid-svg-icons";
import { useStore } from "../../../store/store";
import ColorLinkPicker from "../../ui/color/ColorLinkPicker.vue";
import VueColorPicker from "../../ui/color/VueColorPicker.vue";
import MediaLibrary from "../../ui/MediaLibrary.vue";
import { getParamOptionDefs } from "../../../designDefs.js";
import { getBaseSectionSwatchStyle } from "../../sections/_baseSectionSwatchStyle.js";
import {
  COLOR_VARIATION_OPTIONS,
  DEFAULT_COLOR_VARIATION,
  normalizeColorVariation,
} from "../../../utils/colorVariations.js";
import {
  getDeviceFromWidth,
  getResponsiveDeviceLabel,
} from "../../../utils/responsiveViewport.js";

const props = defineProps({
  paramKey: { type: String, required: true },
  config: { type: Object, required: true },
  value: { default: null },
  designValues: { type: Object, default: () => ({}) },
  responsiveValues: { type: Object, default: () => ({}) },
  selectedUnits: { type: Object, default: () => ({}) },
  fontFamilies: { type: Array, default: () => [] },
  fontWeights: { type: Array, default: () => [] },
  baseColors: { type: Array, default: () => [] },
  colorLinks: { type: Object, default: () => ({}) },
  colorVariations: { type: Object, default: null },
  forceNullable: { type: Boolean, default: false },
  hideResponsive: { type: Boolean, default: false },
  overrideInfo: { type: String, default: "" },
  overrideSources: { type: Array, default: () => [] },
});

const overrideInfo = computed(() => props.overrideInfo || "");
const overrideSources = computed(() => Array.isArray(props.overrideSources) ? props.overrideSources : []);
const hasOverrideSources = computed(() => overrideSources.value.length > 0);

const emit = defineEmits(["update", "update-link", "update-color-variation", "update-responsive", "update-responsive-mode", "update-unit", "device-click", "open-override"]);

const showResponsiveMenu = ref(false);
const responsiveBtnRef = ref(null);
const responsiveMenuPos = ref({});
const showOverrideSourceMenu = ref(false);
const overrideInfoBtnRef = ref(null);
const overrideSourceMenuPos = ref({});
const imageLibraryOpen = ref(false);

const { state } = useStore();

const activeDevice = ref(null);
const activeClampTab = ref(null);

const devices = computed(() => [
  { key: 'mobile', label: getResponsiveDeviceLabel('mobile', state.adminDesignConfig?.responsive) },
  { key: 'tablet', label: getResponsiveDeviceLabel('tablet', state.adminDesignConfig?.responsive) },
  { key: 'desktop', label: getResponsiveDeviceLabel('desktop', state.adminDesignConfig?.responsive) },
]);

function getDeviceIcon(deviceKey) {
  if (deviceKey === "mobile") return faMobileScreenButton;
  if (deviceKey === "tablet") return faTabletScreenButton;
  return faDesktop;
}

// Detect real screen size (not simulated)
const realScreenDevice = ref(null);

function updateRealScreenDevice() {
  const w = window.innerWidth;
  const device = getDeviceFromWidth(w, state.adminDesignConfig?.responsive);
  realScreenDevice.value = device === 'desktop' ? null : device;
}

// Auto-select device tab based on simulation or real screen
function syncActiveDevice() {
  if (props.config.responsive !== 'media') return;
  
  const sim = state.simulatedViewport;
  const real = realScreenDevice.value;
  
  // On real mobile: auto-select mobile tab (no simulation needed)
  if (real === 'mobile') {
    activeDevice.value = 'mobile';
    return;
  }
  
  // On real tablet: auto-select tablet tab, but allow mobile simulation
  if (real === 'tablet') {
    if (sim === 'mobile') {
      activeDevice.value = 'mobile';
    } else {
      activeDevice.value = 'tablet';
    }
    return;
  }
  
  // Desktop: follow simulation state
  activeDevice.value = sim || null;
}

function toggleDevice(key) {
  const wasActive = activeDevice.value === key;
  activeDevice.value = wasActive ? null : key;
  
  // On real mobile: don't trigger simulation at all
  if (realScreenDevice.value === 'mobile') return;
  
  // On real tablet: only trigger simulation for mobile
  if (realScreenDevice.value === 'tablet') {
    if (key === 'mobile') {
      emit('device-click', wasActive ? null : key);
    }
    return;
  }
  
  // On desktop: trigger simulation as usual
  emit('device-click', wasActive ? null : key);
}

function handleDeviceButtonClick(key) {
  if (key === 'desktop') {
    // Desktop click: deselect active device and emit to end simulation
    if (activeDevice.value) {
      activeDevice.value = null;
      // Only emit to end simulation if not on real mobile/tablet
      if (!realScreenDevice.value) {
        emit('device-click', null);
      } else if (realScreenDevice.value === 'tablet' && state.simulatedViewport === 'mobile') {
        emit('device-click', null);
      }
    }
  } else {
    toggleDevice(key);
  }
}

function toggleClampTab(key) {
  activeClampTab.value = activeClampTab.value === key ? null : key;
}

const respVals = computed(() => {
  const all = props.responsiveValues[props.paramKey] || {};
  const mode = props.config.responsive;
  if (mode === 'clamp') return all.clamp || {};
  if (mode === 'media') return all.media || {};
  return {};
});

const nullableParams = new Set();

const isNullable = computed(() => props.forceNullable || nullableParams.has(props.paramKey) || props.paramKey.startsWith('btnType_'));

const currentLink = computed(() => props.colorLinks[props.paramKey] || null);
const showColorLinkPicker = computed(() => {
  if (props.config.type !== "color") return false;
  if (props.config.isBase) return false;
  if (props.config.linkable === false) return false;
  if (props.config.showLinkInPanel === false) return false;
  return (props.baseColors || []).length > 0;
});
const colorVariationOptions = COLOR_VARIATION_OPTIONS;

const adminColorVariationDefaults = computed(() => {
  const raw = state.adminDesignConfig?.colorVariations;
  return raw && typeof raw === "object" ? raw : {};
});

const explicitColorVariationOverrides = computed(() => {
  const raw = props.colorVariations;
  return raw && typeof raw === "object" ? raw : null;
});

const designColorVariationOverrides = computed(() => {
  const raw = props.designValues?.colorVariations;
  return raw && typeof raw === "object" ? raw : {};
});

const supportsColorVariation = computed(() => {
  if (props.config.type !== "color") return false;
  if (props.config.isBase) return false;
  if (props.paramKey === "highContrastDark" || props.paramKey === "highContrastLight") return false;
  if (state.adminDesignConfig?.showColorVariationDropdowns === false) return false;
  if (props.forceNullable) return true;
  return Object.prototype.hasOwnProperty.call(props.designValues || {}, props.paramKey);
});

const currentColorVariation = computed(() => {
  if (
    explicitColorVariationOverrides.value
    && Object.prototype.hasOwnProperty.call(explicitColorVariationOverrides.value, props.paramKey)
  ) {
    return normalizeColorVariation(explicitColorVariationOverrides.value[props.paramKey]);
  }
  if (Object.prototype.hasOwnProperty.call(designColorVariationOverrides.value, props.paramKey)) {
    return normalizeColorVariation(designColorVariationOverrides.value[props.paramKey]);
  }
  const fallback = adminColorVariationDefaults.value?.[props.paramKey];
  return normalizeColorVariation(fallback ?? DEFAULT_COLOR_VARIATION);
});

const allLinkableColors = computed(() => {
  const items = (props.baseColors || []).map(bc => ({
    key: bc.key,
    label: bc.label,
    dotStyle: { background: props.designValues[bc.key] || '#ccc' },
    dotClass: '',
  }));
  items.push({
    key: 'transparent',
    label: 'Transparent',
    dotStyle: { background: 'linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%), linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%)', backgroundSize: '8px 8px', backgroundPosition: '0 0, 4px 4px' },
    dotClass: 'checkerboard',
  });
  const hcDark = props.designValues.highContrastDark || '#0b1220';
  const hcLight = props.designValues.highContrastLight || '#f8fafc';
  items.push({
    key: 'highContrast',
    label: 'High Contrast',
    dotStyle: { background: `linear-gradient(135deg, ${hcDark} 50%, ${hcLight} 50%)` },
    dotClass: '',
  });
  return items;
});

// Multi-unit support
const unitConfigs = computed(() => {
  const cfg = props.config;
  if (cfg.unitConfigs && cfg.unitConfigs.length > 0) {
    return cfg.unitConfigs;
  }
  // Use nullish coalescing to preserve empty string unit (for unitless values like line-height)
  const unit = cfg.unit ?? 'px';
  return [{ unit, min: cfg.min ?? 0, max: cfg.max ?? 100, step: cfg.step ?? 1 }];
});

const hasMultipleUnits = computed(() => unitConfigs.value.length > 1);

const ABSOLUTE_UNITS = new Set(['px', 'pt', 'cm', 'mm', 'in', '']);
const RELATIVE_UNITS = new Set(['%', 'em', 'rem', 'vw', 'vh', 'vmin', 'vmax', 'ch']);

const absoluteUnitConfigs = computed(() => {
  const absolute = unitConfigs.value.filter(uc => ABSOLUTE_UNITS.has(uc.unit));
  // Fallback to first unit config if no absolute units defined
  if (absolute.length === 0 && unitConfigs.value.length > 0) {
    return [unitConfigs.value[0]];
  }
  return absolute;
});

const relativeUnitConfigs = computed(() => {
  // Check for custom relative unit configs from admin
  const customRelative = unitConfigs.value.filter(uc => RELATIVE_UNITS.has(uc.unit));
  const customUnits = new Set(customRelative.map(uc => uc.unit));
  
  // Default configs for relative units (used when no custom config exists)
  const defaultRelativeUnits = [
    { unit: 'vw', min: 0, max: 100, step: 1 },
    { unit: 'vh', min: 0, max: 100, step: 1 },
    { unit: '%', min: 0, max: 100, step: 1 },
    { unit: 'rem', min: 0, max: 100, step: 1 },
    { unit: 'em', min: 0, max: 100, step: 1 },
  ];
  
  // Merge: use custom configs first, then add defaults for missing units
  const result = [...customRelative];
  for (const def of defaultRelativeUnits) {
    if (!customUnits.has(def.unit)) {
      result.push(def);
    }
  }
  return result;
});

const displayedSliderUnit = computed(() => {
  if (props.config.responsive === 'clamp' && activeClampTab.value) {
    const rv = respVals.value;
    if (activeClampTab.value === 'preferred') {
      return rv.preferredUnit ?? 'vw';
    } else if (activeClampTab.value === 'min') {
      return rv.minUnit ?? activeUnit.value;
    } else if (activeClampTab.value === 'max') {
      return rv.maxUnit ?? activeUnit.value;
    }
  }
  return activeUnit.value;
});

const selectedUnit = ref(null);

const activeUnit = computed(() => {
  // Priority: local selection > stored selection > defaultUnit > first unit
  if (selectedUnit.value != null && unitConfigs.value.some(uc => uc.unit === selectedUnit.value)) {
    return selectedUnit.value;
  }
  const storedUnit = props.selectedUnits[props.paramKey];
  if (storedUnit != null && unitConfigs.value.some(uc => uc.unit === storedUnit)) {
    return storedUnit;
  }
  if (props.config.defaultUnit != null && unitConfigs.value.some(uc => uc.unit === props.config.defaultUnit)) {
    return props.config.defaultUnit;
  }
  // Use nullish coalescing to preserve empty string unit
  return unitConfigs.value[0]?.unit ?? 'px';
});

const activeUnitConfig = computed(() => {
  // For clamp mode with active tab, use the appropriate unit config
  if (props.config.responsive === 'clamp' && activeClampTab.value) {
    const rv = respVals.value;
    if (activeClampTab.value === 'preferred') {
      const prefUnit = rv.preferredUnit ?? 'vw';
      // All relative units have the same config (0-100, step 1)
      return relativeUnitConfigs.value.find(uc => uc.unit === prefUnit) || { unit: prefUnit, min: 0, max: 100, step: 1 };
    } else {
      // min or max use absolute unit from existing slider configs
      const absUnit = activeClampTab.value === 'min' ? (rv.minUnit ?? activeUnit.value) : (rv.maxUnit ?? activeUnit.value);
      return absoluteUnitConfigs.value.find(uc => uc.unit === absUnit) ?? unitConfigs.value[0] ?? { unit: '', min: 0, max: 100, step: 1 };
    }
  }
  return unitConfigs.value.find(uc => uc.unit === activeUnit.value) ?? unitConfigs.value[0] ?? { unit: '', min: 0, max: 100, step: 1 };
});

function onUnitChange(unit) {
  selectedUnit.value = unit;
  emit('update-unit', props.paramKey, unit);
}

watch(() => props.paramKey, () => {
  selectedUnit.value = null;
  activeClampTab.value = null;
  activeDevice.value = null;
});

const sliderValue = computed(() => {
  if (props.value != null) return props.value;
  return activeUnitConfig.value.min ?? 0;
});

const showResponsiveUI = computed(() => !!props.config.responsive && !props.hideResponsive);

const effectiveSliderValue = computed(() => {
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    const rv = respVals.value;
    const deviceVal = rv[activeDevice.value];
    if (deviceVal != null) return deviceVal;
  }
  if (showResponsiveUI.value && props.config.responsive === 'clamp' && activeClampTab.value) {
    const rv = respVals.value;
    const tabVal = rv[activeClampTab.value];
    if (tabVal != null) return tabVal;
  }
  return sliderValue.value;
});

const sliderLabel = computed(() => {
  let label = props.config.label || props.paramKey;
  if (props.config.responsive === 'clamp') {
    const rv = respVals.value;
    if (rv.min != null && rv.preferred != null && rv.max != null) {
      if (props.config.allowInput) {
        // In advanced mode, values are raw CSS - don't append units
        //label += `\nclamp(${rv.min}, ${rv.preferred}, ${rv.max})`;
      } else {
        //const minUnit = rv.minUnit ?? activeUnit.value;
        //const maxUnit = rv.maxUnit ?? activeUnit.value;
        //label += `\nclamp(${rv.min}${minUnit}, ${rv.preferred}${rv.preferredUnit ?? 'vw'}, ${rv.max}${maxUnit})`;
      }
    }
  }
  if (isNullable.value && props.value == null && !props.config.responsive) {
    const fallbackKeys = {
      heroTitleFontSize: 'headerFontSizeMax',
      heroTitleLineHeight: 'headerLineHeight',
      heroSubtitleLineHeight: 'bodyLineHeight',
    };
    if (fallbackKeys[props.paramKey]) {
      label += ' (from global)';
    }
  }
  return label;
});

const formatSliderDisplay = computed(() => {
  const v = sliderValue.value;
  if (v === undefined || v === null) return '0';
  const step = props.config.step ?? 1;
  if (step < 0.01) return Number(v).toFixed(3);
  if (step < 0.1) return Number(v).toFixed(2);
  if (step < 1) return Number(v).toFixed(2);
  return String(v);
});

const formatEffectiveSliderDisplay = computed(() => {
  const v = effectiveSliderValue.value;
  if (v === undefined || v === null) return '0';
  const step = props.config.step ?? 1;
  if (step < 0.01) return Number(v).toFixed(3);
  if (step < 0.1) return Number(v).toFixed(2);
  if (step < 1) return Number(v).toFixed(2);
  return String(v);
});

function onSliderInput(e) {
  const step = activeUnitConfig.value.step ?? 1;
  const val = step < 1 ? parseFloat(e.target.value) : parseInt(e.target.value);
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    updateResponsive({ [activeDevice.value]: val });
  } else if (showResponsiveUI.value && props.config.responsive === 'clamp' && activeClampTab.value) {
    updateResponsive({ [activeClampTab.value]: val });
  } else {
    emit('update', props.paramKey, val);
  }
}

const effectiveAdvancedValue = computed(() => {
  // For media query mode with active device
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    const rv = respVals.value;
    return rv[activeDevice.value] ?? '';
  }
  // For clamp mode with active tab
  if (showResponsiveUI.value && props.config.responsive === 'clamp' && activeClampTab.value) {
    const rv = respVals.value;
    return rv[activeClampTab.value] ?? '';
  }
  // Base value
  return props.value ?? '';
});

const advancedPlaceholder = computed(() => {
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    return `${activeDevice.value} value, e.g. calc(50vw - 20px)`;
  }
  if (showResponsiveUI.value && props.config.responsive === 'clamp' && activeClampTab.value) {
    return `${activeClampTab.value} value, e.g. 50vw`;
  }
  return 'e.g. calc(50vw - 20px)';
});

function onAdvancedInput(val) {
  const value = val || null;
  // For media query mode with active device
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    updateResponsive({ [activeDevice.value]: value });
    return;
  }
  // For clamp mode with active tab
  if (showResponsiveUI.value && props.config.responsive === 'clamp' && activeClampTab.value) {
    updateResponsive({ [activeClampTab.value]: value });
    return;
  }
  // Base value
  emit('update', props.paramKey, value);
}

function updateResponsive(patch) {
  const mode = props.config.responsive;
  emit('update-responsive', props.paramKey, mode, { ...respVals.value, ...patch });
}

function toggleResponsiveMenu() {
  if (showResponsiveMenu.value) {
    showResponsiveMenu.value = false;
    return;
  }
  if (responsiveBtnRef.value) {
    const rect = responsiveBtnRef.value.getBoundingClientRect();
    const menuHeight = 120;
    const viewportH = window.innerHeight;
    const spaceBelow = viewportH - rect.bottom - 8;
    const openUpward = spaceBelow < menuHeight && rect.top > menuHeight;
    responsiveMenuPos.value = {
      position: 'fixed',
      left: `${Math.max(8, rect.right - 200)}px`,
      zIndex: '9999',
      ...(openUpward
        ? { bottom: `${viewportH - rect.top + 4}px` }
        : { top: `${rect.bottom + 4}px` }),
    };
  }
  showResponsiveMenu.value = true;
}

function toggleOverrideSourceMenu() {
  if (showOverrideSourceMenu.value) {
    showOverrideSourceMenu.value = false;
    return;
  }
  const rect = overrideInfoBtnRef.value?.getBoundingClientRect();
  if (rect) {
    const viewportH = window.innerHeight;
    const openUpward = viewportH - rect.bottom < 140;
    overrideSourceMenuPos.value = {
      position: 'fixed',
      left: `${Math.max(8, rect.right - 220)}px`,
      zIndex: '9999',
      ...(openUpward
        ? { bottom: `${viewportH - rect.top + 4}px` }
        : { top: `${rect.bottom + 4}px` }),
    };
  }
  showOverrideSourceMenu.value = true;
}

function openOverrideSource(sectionKey) {
  showOverrideSourceMenu.value = false;
  emit('open-override', sectionKey);
}

function setResponsiveMode(mode) {
  showResponsiveMenu.value = false;
  emit('update-responsive-mode', props.paramKey, mode);
}

function clearResponsiveMode() {
  emit('update-responsive-mode', props.paramKey, null);
}

const colorValue = computed(() => {
  if (props.value === '__high_contrast__') {
    return props.designValues.highContrastDark || '#0b1220';
  }
  if (props.value === 'transparent') {
    return '#ffffff';
  }
  if (props.value) return props.value;
  // For override rows, show the current global value instead of plain white.
  const globalColorValue = props.designValues?.[props.paramKey];
  if (globalColorValue === '__high_contrast__') {
    return props.designValues.highContrastDark || '#0b1220';
  }
  if (globalColorValue === 'transparent') {
    return '#ffffff';
  }
  if (globalColorValue) return globalColorValue;
  const fallbackMap = {
    topbarBgColor: 'sectionBackgroundColor',
    heroTitleColor: null,
    heroSubtitleColor: null,
    buttonBgColor: 'accentColor',
    buttonColor: null,
    buttonHoverBgColor: 'buttonBgColor',
    buttonHoverColor: 'buttonColor',
    buttonHoverBorderColor: 'buttonBorderColor',
  };
  if (props.paramKey in fallbackMap) {
    const fk = fallbackMap[props.paramKey];
    return fk ? (props.designValues[fk] || '#ffffff') : '#ffffff';
  }
  return '#ffffff';
});

const specialColorPreview = computed(() => {
  const isHighContrast = props.value === '__high_contrast__' || currentLink.value === 'highContrast';
  const baseRefColor = props.designValues.sectionBackgroundColor || '#ffffff';
  if (isHighContrast || props.value === 'transparent' || currentLink.value === 'transparent') {
    return getBaseSectionSwatchStyle(
      props.designValues,
      isHighContrast ? null : props.value,
      {
        rawColor: props.value,
        linkKey: currentLink.value,
        baseRefColor,
        baseRefKey: 'sectionBackgroundColor',
        adminConfig: state.adminDesignConfig,
      }
    );
  }
  return null;
});

const colorLabel = computed(() => {
  let label = props.config.label || props.paramKey;
  if (isNullable.value && !props.value) {
    label += ' (auto)';
  }
  return label;
});

const dropdownOptions = computed(() => {
  return getParamOptionDefs(props.paramKey, props.config.enabledOptions);
});

const buttonGroupOptions = computed(() => {
  return getParamOptionDefs(props.paramKey, props.config.enabledOptions);
});

// Effective value for dropdown when responsive mode is active
const effectiveDropdownValue = computed(() => {
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    const rv = respVals.value;
    const deviceVal = rv[activeDevice.value];
    if (deviceVal != null) return deviceVal;
  }
  return props.value;
});

// Effective value for buttongroup when responsive mode is active
const effectiveButtonGroupValue = computed(() => {
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    const rv = respVals.value;
    const deviceVal = rv[activeDevice.value];
    if (deviceVal != null) return deviceVal;
  }
  return props.value;
});

// Handle dropdown change - update device value or base
function onDropdownChange(val) {
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    updateResponsive({ [activeDevice.value]: val });
  } else {
    emit('update', props.paramKey, val);
  }
}

// Handle button group click - update device value or base
function onButtonGroupClick(val) {
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    updateResponsive({ [activeDevice.value]: val });
  } else {
    emit('update', props.paramKey, val);
  }
}

// Get the label for a device's value (for dropdown/buttongroup display)
function getDeviceOptionLabel(deviceKey) {
  const val = deviceKey === 'desktop' ? props.value : respVals.value[deviceKey];
  if (val == null) return '–';
  // Try to find label from dropdown options
  const dOpt = dropdownOptions.value.find(o => o.value === val);
  if (dOpt) return dOpt.label;
  // Try button group options
  const bOpt = buttonGroupOptions.value.find(o => o.value === val);
  if (bOpt) return bOpt.label;
  return val;
}

// Effective value for fontfamily when responsive mode is active
const effectiveFontFamilyValue = computed(() => {
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    const rv = respVals.value;
    const deviceVal = rv[activeDevice.value];
    if (deviceVal != null) return deviceVal;
  }
  return props.value;
});

// Handle font family change - update device value or base
function onFontFamilyChange(val) {
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    updateResponsive({ [activeDevice.value]: val });
  } else {
    emit('update', props.paramKey, val);
  }
}

// Get the label for a device's font family value
function getFontFamilyLabel(deviceKey) {
  const val = deviceKey === 'desktop' ? props.value : respVals.value[deviceKey];
  if (val == null) return '–';
  const font = fontFamilies.find(f => f.value === val);
  return font ? font.label : val;
}

// Effective value for positiongrid when responsive mode is active
const effectivePositionGridValue = computed(() => {
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    const rv = respVals.value;
    const deviceVal = rv[activeDevice.value];
    if (deviceVal != null) return deviceVal;
  }
  return props.value;
});

// Handle position grid click - update device value or base
function onPositionGridClick(val) {
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    updateResponsive({ [activeDevice.value]: val });
  } else {
    emit('update', props.paramKey, val);
  }
}

// Get the label for a device's position value
function getPositionLabel(deviceKey) {
  const val = deviceKey === 'desktop' ? props.value : respVals.value[deviceKey];
  if (val == null) return '–';
  const pos = overlayPositions.find(p => p.value === val);
  return pos ? pos.icon : val;
}

// Effective value for checkbox when responsive mode is active
const effectiveCheckboxValue = computed(() => {
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    const rv = respVals.value;
    const deviceVal = rv[activeDevice.value];
    if (deviceVal != null) return deviceVal;
  }
  return props.value;
});

const imagePreviewUrl = computed(() => String(props.value || "").trim());

const imageSourceContext = computed(() => {
  return `design.${props.paramKey}`;
});

// Handle checkbox change - update device value or base
function onCheckboxChange(val) {
  if (showResponsiveUI.value && props.config.responsive === 'media' && activeDevice.value) {
    updateResponsive({ [activeDevice.value]: val });
  } else {
    emit('update', props.paramKey, val);
  }
}

// Get the label for a device's checkbox value
function getCheckboxLabel(deviceKey) {
  const val = deviceKey === 'desktop' ? props.value : respVals.value[deviceKey];
  if (val == null) return '–';
  return val ? '✓' : '✗';
}

const overlayPositions = [
  { value: 'top-left', label: 'Top Left', icon: 'TL' },
  { value: 'top-center', label: 'Top Center', icon: 'TC' },
  { value: 'top-right', label: 'Top Right', icon: 'TR' },
  { value: 'center-left', label: 'Center Left', icon: 'CL' },
  { value: 'center', label: 'Center', icon: 'C' },
  { value: 'center-right', label: 'Center Right', icon: 'CR' },
  { value: 'bottom-left', label: 'Bottom Left', icon: 'BL' },
  { value: 'bottom-center', label: 'Bottom Center', icon: 'BC' },
  { value: 'bottom-right', label: 'Bottom Right', icon: 'BR' },
];

function linkToBaseColor(baseKey) {
  emit('update-link', props.paramKey, baseKey, true);
}

function onColorVariationChange(value) {
  if (!supportsColorVariation.value) return;
  const normalized = normalizeColorVariation(value);
  emit('update-color-variation', props.paramKey, normalized);
}

function onColorValueInput(nextValue) {
  emit('update', props.paramKey, nextValue);
  if (currentLink.value) {
    emit('update-link', props.paramKey, null, false);
  }
}

function openImageLibrary() {
  imageLibraryOpen.value = true;
}

function closeImageLibrary() {
  imageLibraryOpen.value = false;
}

function onImageSelect(selection) {
  const nextUrl = String(selection?.url || "").trim();
  emit('update', props.paramKey, nextUrl || null);
  closeImageLibrary();
}

function onClickOutside() {
  if (showResponsiveMenu.value) showResponsiveMenu.value = false;
  if (showOverrideSourceMenu.value) showOverrideSourceMenu.value = false;
}

onMounted(() => {
  document.addEventListener('click', onClickOutside, true);
  window.addEventListener('resize', updateRealScreenDevice);
  updateRealScreenDevice();
  syncActiveDevice();
});

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside, true);
  window.removeEventListener('resize', updateRealScreenDevice);
});

// Watch for simulation changes
watch(() => state.simulatedViewport, () => {
  syncActiveDevice();
});

// Watch for real screen size changes
watch(realScreenDevice, () => {
  syncActiveDevice();
});

watch(() => state.adminDesignConfig?.responsive, () => {
  updateRealScreenDevice();
  syncActiveDevice();
}, { deep: true });

// Watch for responsive mode changes
watch(() => props.config.responsive, () => {
  syncActiveDevice();
});
</script>

<style scoped>
.design-field-wrap {
  margin-bottom: 12px;
}

.design-field-wrap:last-child {
  margin-bottom: 0;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 0;
  padding: 10px;
  padding-right: 30px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  position: relative;
}

.field + .field {
  margin-top: 6px;
}

.field-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--admin-text, #0f172a);
  white-space: pre-line;
}

.override-info-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  margin-left: 0;
  border-radius: 50%;
  background: #facc15;
  color: #111827;
  font-size: 10px;
  font-weight: 900;
  line-height: 1;
  cursor: help;
  border: 1px solid #f59e0b;
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 2;
}

.override-info-btn {
  border: none;
  padding: 0;
}

.override-source-menu {
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.14);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.18);
  min-width: 200px;
  max-height: 50vh;
  overflow-y: auto;
}

.override-source-item {
  display: block;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}
.override-source-item:hover { background: #f1f5f9; }

.field select {
  padding: 2px;
  border-radius: 5px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 14px;
  cursor: pointer;
}
.field select:focus { outline: none; border-color: var(--accent, #5b2fe3); }

.checkbox-field {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.checkbox-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.checkbox-field input[type="checkbox"] { width: 18px; height: 18px; cursor: pointer; }

.range-field {
  display: flex;
  align-items: center;
  gap: 10px;
}

.advanced-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--accent, #5b2fe3);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.advanced-input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 6px;
  font-size: 12px;
  font-family: ui-monospace, monospace;
  background: var(--card-bg, #fff);
  color: var(--text, #1e293b);
}
.advanced-input:focus {
  outline: none;
  border-color: var(--accent, #5b2fe3);
  box-shadow: 0 0 0 2px rgba(91, 47, 227, 0.1);
}
.advanced-input::placeholder {
  color: var(--muted, #94a3b8);
  font-style: italic;
}

.range-field input[type="range"] {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--border);
  appearance: none;
  cursor: pointer;
}

.range-field input[type="range"]::-webkit-slider-thumb {
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--accent, #5b2fe3);
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

.range-field input[type="range"]::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--accent, #5b2fe3);
  cursor: pointer;
  border: none;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

/* Muted slider for clamp mode when no tab selected */
.range-field.slider-muted input[type="range"] {
  opacity: 0.4;
}
.range-field.slider-muted input[type="range"]::-webkit-slider-thumb {
  background: var(--muted, #94a3b8);
}
.range-field.slider-muted input[type="range"]::-moz-range-thumb {
  background: var(--muted, #94a3b8);
}
.range-field.slider-muted .range-value {
  opacity: 0.5;
}

.range-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  min-width: 40px;
  text-align: right;
  font-family: ui-monospace, monospace;
}

.range-unit {
  font-size: 11px;
  color: var(--muted);
  min-width: 24px;
}

.unit-select {
  padding: 2px 4px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 11px;
  color: var(--muted);
  background: var(--card-bg);
  cursor: pointer;
  min-width: 40px;
}

.unit-select:focus {
  outline: none;
  border-color: var(--accent, #5b2fe3);
}

.unit-select:hover {
  border-color: var(--accent, #5b2fe3);
}

.color-field {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  position: relative;
}

.color-input-group {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
}
.color-input-group.with-corner-clear {
  padding-right: 30px;
}

.color-variation-select {
  min-width: 72px;
  padding: 6px 8px;
  border-radius: 6px;
  border: 1px solid var(--border);
  font-size: 12px;
  background: #fff;
  color: var(--text);
}

.color-variation-select:focus {
  outline: none;
  border-color: var(--accent, #5b2fe3);
}

.clear-field-btn {
  width: 22px;
  height: 22px;
  display: inline-grid;
  place-items: center;
  border-radius: 5px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 10px;
  cursor: pointer;
  color: var(--muted);
  flex-shrink: 0;
  transition: all 0.15s ease;
}
.clear-field-btn:hover { background: #fee2e2; border-color: #fecaca; color: #dc2626; }

.clear-field-btn.clear-corner {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 3;
}

.btn-group {
  display: flex;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border);
}

.btn-group-item {
  flex: 1;
  padding: 7px 4px;
  font-size: 12px;
  font-weight: 600;
  border: none;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s ease;
  color: var(--muted);
}
.btn-group-item + .btn-group-item { border-left: 1px solid var(--border); }
.btn-group-item.active { background: var(--accent, #4f46e5); color: #fff; }
.btn-group-item:hover:not(.active) { background: var(--surface-2); }

.position-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  width: 120px;
}

.pos-btn {
  width: 36px;
  height: 28px;
  display: inline-grid;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: 5px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  color: var(--muted);
  transition: all 0.15s ease;
}
.pos-btn.active { background: var(--accent, #4f46e5); color: #fff; border-color: transparent; }
.pos-btn:hover:not(.active) { background: var(--surface-2); }

.css-textarea {
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  resize: vertical;
  background: #fff;
  color: var(--text);
}
.css-textarea:focus { outline: none; border-color: var(--accent, #5b2fe3); }

.image-field {
  gap: 8px;
}

.image-field-preview {
  width: 100%;
  min-height: 78px;
  border: 1px dashed var(--border, #e2e8f0);
  border-radius: 8px;
  background: var(--surface-2, #f8fafc);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 6px;
}

.image-field-preview.empty {
  padding: 14px 10px;
}

.image-field-preview-img {
  width: 100%;
  max-height: 120px;
  object-fit: contain;
  display: block;
}

.image-field-empty {
  font-size: 12px;
  color: var(--muted, #64748b);
}

.image-field-actions {
  display: flex;
}

.image-field-btn {
  padding: 6px 10px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 7px;
  background: #fff;
  font-size: 12px;
  font-weight: 600;
  color: var(--admin-text, #0f172a);
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.image-field-btn:hover {
  border-color: var(--accent, #5b2fe3);
  color: var(--accent, #5b2fe3);
  background: #eef2ff;
}

/* Responsive: label row with toggle */
.field-label-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.responsive-toggle-btn {
  width: 22px;
  height: 22px;
  box-sizing: border-box;
  display: inline-grid;
  place-items: center;
  padding: 0;
  border-radius: 4px;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  color: var(--muted, #cbd5e1);
  flex-shrink: 0;
  line-height: 1;
  transition: all 0.15s ease;
  opacity: 0.5;
}
.responsive-toggle-btn:hover {
  opacity: 1;
  color: var(--accent, #4f46e5);
  background: #eef2ff;
  border-color: #c7d2fe;
}
.responsive-toggle-btn.active {
  opacity: 1;
  color: var(--accent, #4f46e5);
  background: #eef2ff;
  border-color: #a5b4fc;
}

.responsive-toggle-icon {
  display: block;
  width: 12px;
  height: 12px;
  font-size: 12px;
  line-height: 1;
}

.responsive-clear-btn {
  width: 18px;
  height: 18px;
  display: inline-grid;
  place-items: center;
  border-radius: 3px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--muted, #94a3b8);
  font-size: 10px;
  flex-shrink: 0;
  transition: all 0.15s ease;
}
.responsive-clear-btn:hover {
  color: #ef4444;
  background: #fef2f2;
}

.responsive-mode-menu {
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.14);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.18);
  min-width: 180px;
  overflow: hidden;
}

.resp-mode-item {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
  color: var(--text, #0f172a);
}
.resp-mode-item:hover { background: #f1f5f9; }
.resp-mode-item.active { background: #eef2ff; font-weight: 600; color: var(--accent, #4f46e5); }

.resp-mode-hint {
  font-size: 10px;
  color: var(--muted, #94a3b8);
  margin-left: auto;
  font-weight: 400;
}

/* Responsive: device selector */
/* Responsive: assign buttons */
.assign-btn {
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--border, #e2e8f0);
  background: #fff;
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
  color: var(--muted, #64748b);
  white-space: nowrap;
  transition: all 0.15s ease;
  flex-shrink: 0;
}
.assign-btn:hover {
  background: #eef2ff;
  border-color: #c7d2fe;
  color: var(--accent, #4f46e5);
}

/* Responsive: detail row */
.responsive-detail {
  display: flex;
  gap: 4px;
  padding: 6px 0 0;
}

.resp-val {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 4px 6px;
  border-radius: 5px;
  background: var(--surface-2, #f8fafc);
  cursor: pointer;
  transition: all 0.12s ease;
  min-width: 70px;
}
.resp-val:hover { background: #eef2ff; }
.resp-val.resp-active { background: #eef2ff; outline: 1.5px solid var(--accent, #4f46e5); }
.resp-val.resp-linked { opacity: 0.6; cursor: default; }

.resp-label {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted, #94a3b8);
}

.resp-device-icon {
  font-size: 12px;
}

.resp-num {
  font-size: 11px;
  font-weight: 600;
  font-family: ui-monospace, monospace;
  color: var(--text, #0f172a);
}

/* Clamp detail: unit selectors */
.clamp-detail .resp-val {
  flex-direction: column;
  gap: 2px;
  cursor: pointer;
}

.clamp-detail .resp-num {
  font-size: 12px;
}

.clamp-unit-select {
  padding: 1px 2px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 3px;
  font-size: 9px;
  background: #fff;
  cursor: pointer;
  max-width: 42px;
}
.clamp-unit-select:focus { outline: none; border-color: var(--accent, #5b2fe3); }
</style>
