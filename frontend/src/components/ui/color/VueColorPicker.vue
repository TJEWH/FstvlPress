<template>
  <div class="vcp-root" :class="{ 'high-contrast': isHighContrastPreview }" ref="rootRef">
    <button
      ref="triggerRef"
      class="vcp-trigger"
      type="button"
      :style="triggerStyle"
      @click.stop="togglePanel"
      :aria-label="label || 'Open color picker'"
      :title="label || currentHex"
    >
      <span :class="swatchClass" :style="swatchPreviewStyle"></span>
    </button>

    <Teleport to="body">
      <div
        v-if="isOpen"
        ref="panelRef"
        class="vcp-panel"
        :style="panelStyle"
        @mousedown.stop
      >
        <div class="vcp-mode-tabs">
          <button
            type="button"
            class="vcp-tab"
            :class="{ active: mode === 'wheel' }"
            @click="mode = 'wheel'"
          >
            Wheel
          </button>
          <button
            type="button"
            class="vcp-tab"
            :class="{ active: mode === 'sliders' }"
            @click="mode = 'sliders'"
          >
            Sliders
          </button>
        </div>

        <div v-if="mode === 'wheel'" class="vcp-wheel-wrap">
          <div
            class="vcp-wheel-container"
            :style="{ width: `${wheelSize}px`, height: `${wheelSize}px` }"
          >
            <canvas
              ref="wheelRef"
              class="vcp-wheel"
              :width="wheelSize"
              :height="wheelSize"
              @pointerdown.prevent="onWheelPointerDown"
            ></canvas>
            <span class="vcp-wheel-marker" :style="wheelMarkerStyle"></span>
          </div>
          <div class="vcp-slider-row">
            <span class="vcp-slider-label">V</span>
            <input
              class="vcp-slider"
              type="range"
              min="0"
              max="100"
              :value="hsv.v"
              :style="valueSliderStyle"
              @input="onHsvInput('v', $event.target.value)"
            />
            <input
              class="vcp-slider-value"
              type="number"
              inputmode="numeric"
              min="0"
              max="100"
              step="1"
              :value="hsv.v"
              aria-label="Value"
              @focus="$event.target.select()"
              @input="onHsvInput('v', $event.target.value)"
            />
          </div>
        </div>

        <div v-else class="vcp-slider-group">
          <div class="vcp-slider-row">
            <span class="vcp-slider-label">H</span>
            <input
              class="vcp-slider"
              type="range"
              min="0"
              max="360"
              :value="hsv.h"
              :style="hueSliderStyle"
              @input="onHsvInput('h', $event.target.value)"
            />
            <input
              class="vcp-slider-value"
              type="number"
              inputmode="numeric"
              min="0"
              max="360"
              step="1"
              :value="hsv.h"
              aria-label="Hue"
              @focus="$event.target.select()"
              @input="onHsvInput('h', $event.target.value)"
            />
          </div>
          <div class="vcp-slider-row">
            <span class="vcp-slider-label">S</span>
            <input
              class="vcp-slider"
              type="range"
              min="0"
              max="100"
              :value="hsv.s"
              :style="saturationSliderStyle"
              @input="onHsvInput('s', $event.target.value)"
            />
            <input
              class="vcp-slider-value"
              type="number"
              inputmode="numeric"
              min="0"
              max="100"
              step="1"
              :value="hsv.s"
              aria-label="Saturation"
              @focus="$event.target.select()"
              @input="onHsvInput('s', $event.target.value)"
            />
          </div>
          <div class="vcp-slider-row">
            <span class="vcp-slider-label">V</span>
            <input
              class="vcp-slider"
              type="range"
              min="0"
              max="100"
              :value="hsv.v"
              :style="valueSliderStyle"
              @input="onHsvInput('v', $event.target.value)"
            />
            <input
              class="vcp-slider-value"
              type="number"
              inputmode="numeric"
              min="0"
              max="100"
              step="1"
              :value="hsv.v"
              aria-label="Value"
              @focus="$event.target.select()"
              @input="onHsvInput('v', $event.target.value)"
            />
          </div>
        </div>

        <div class="vcp-slider-group">
          <div class="vcp-slider-row">
            <span class="vcp-slider-label">R</span>
            <input
              class="vcp-slider"
              type="range"
              min="0"
              max="255"
              :value="rgb.r"
              :style="redSliderStyle"
              @input="onRgbInput('r', $event.target.value)"
            />
            <input
              class="vcp-slider-value"
              type="number"
              inputmode="numeric"
              min="0"
              max="255"
              step="1"
              :value="rgb.r"
              aria-label="Red"
              @focus="$event.target.select()"
              @input="onRgbInput('r', $event.target.value)"
            />
          </div>
          <div class="vcp-slider-row">
            <span class="vcp-slider-label">G</span>
            <input
              class="vcp-slider"
              type="range"
              min="0"
              max="255"
              :value="rgb.g"
              :style="greenSliderStyle"
              @input="onRgbInput('g', $event.target.value)"
            />
            <input
              class="vcp-slider-value"
              type="number"
              inputmode="numeric"
              min="0"
              max="255"
              step="1"
              :value="rgb.g"
              aria-label="Green"
              @focus="$event.target.select()"
              @input="onRgbInput('g', $event.target.value)"
            />
          </div>
          <div class="vcp-slider-row">
            <span class="vcp-slider-label">B</span>
            <input
              class="vcp-slider"
              type="range"
              min="0"
              max="255"
              :value="rgb.b"
              :style="blueSliderStyle"
              @input="onRgbInput('b', $event.target.value)"
            />
            <input
              class="vcp-slider-value"
              type="number"
              inputmode="numeric"
              min="0"
              max="255"
              step="1"
              :value="rgb.b"
              aria-label="Blue"
              @focus="$event.target.select()"
              @input="onRgbInput('b', $event.target.value)"
            />
          </div>
        </div>

        <label v-if="showHexInput" class="vcp-hex-row">
          <span class="vcp-slider-label">HEX</span>
          <input
            v-model="hexInput"
            class="vcp-hex-input"
            type="text"
            placeholder="#AABBCC"
            @keydown.enter.prevent="commitHexInput"
            @blur="commitHexInput"
          />
        </label>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  fallbackColor: { type: String, default: "#ffffff" },
  previewStyle: { type: Object, default: null },
  label: { type: String, default: "" },
  size: { type: Number, default: 30 },
  showHexInput: { type: Boolean, default: true },
});

const emit = defineEmits(["update:modelValue"]);
const VCP_PANEL_Z_INDEX = "2147483645";

const rootRef = ref(null);
const triggerRef = ref(null);
const panelRef = ref(null);
const wheelRef = ref(null);
const isOpen = ref(false);
const mode = ref("wheel");
const hexInput = ref("#FFFFFF");
const panelStyle = ref({
  position: "fixed",
  top: "0px",
  left: "0px",
  zIndex: VCP_PANEL_Z_INDEX,
});

const wheelSize = 180;
const rgb = reactive({ r: 255, g: 255, b: 255 });
const hsv = reactive({ h: 0, s: 0, v: 100 });
let draggingWheel = false;

const currentHex = computed(() => rgbToHex(rgb.r, rgb.g, rgb.b));

const previewPaintStyle = computed(() => {
  if (props.previewStyle && typeof props.previewStyle === "object") {
    const {
      triggerBorder,
      previewClass,
      highContrast,
      ...style
    } = props.previewStyle;
    return style;
  }
  return { background: currentHex.value };
});

const triggerStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  ...(!isHighContrastPreview.value ? previewPaintStyle.value : {}),
  ...(triggerBorderStyle.value || {}),
}));

const triggerBorderStyle = computed(() => {
  const borderColor =
    props.previewStyle && typeof props.previewStyle === "object" && typeof props.previewStyle.triggerBorder === "string"
      ? props.previewStyle.triggerBorder.trim()
      : "";
  if (!borderColor) return null;
  return {
    border: `solid 5px ${borderColor}`,
    boxSizing: "border-box",
  };
});

const isHighContrastPreview = computed(() => {
  if (!props.previewStyle || typeof props.previewStyle !== "object") return false;
  if (props.previewStyle.highContrast === true) return true;
  if (typeof props.previewStyle.previewClass !== "string") return false;
  return props.previewStyle.previewClass
    .split(/\s+/)
    .map((entry) => entry.trim())
    .filter(Boolean)
    .includes("high-contrast");
});

const swatchClass = computed(() => {
  const classes = ["vcp-swatch"];
  if (!props.previewStyle || typeof props.previewStyle !== "object") return classes;
  if (typeof props.previewStyle.previewClass === "string" && props.previewStyle.previewClass.trim()) {
    classes.push(...props.previewStyle.previewClass.split(/\s+/).map((entry) => entry.trim()).filter(Boolean));
  }
  if (props.previewStyle.highContrast === true && !classes.includes("high-contrast")) {
    classes.push("high-contrast");
  }
  return classes;
});

const swatchPreviewStyle = computed(() => (isHighContrastPreview.value ? previewPaintStyle.value : {}));

const hueSliderStyle = computed(() => ({
  background:
    "linear-gradient(90deg, #ff0000 0%, #ffff00 16.6%, #00ff00 33.2%, #00ffff 49.8%, #0000ff 66.4%, #ff00ff 83%, #ff0000 100%)",
}));

const saturationSliderStyle = computed(() => ({
  background: `linear-gradient(90deg, ${hsvToHex(hsv.h, 0, hsv.v)}, ${hsvToHex(hsv.h, 100, hsv.v)})`,
}));

const valueSliderStyle = computed(() => ({
  background: `linear-gradient(90deg, #000000, ${hsvToHex(hsv.h, hsv.s, 100)})`,
}));

const redSliderStyle = computed(() => ({
  background: `linear-gradient(90deg, rgb(0, ${rgb.g}, ${rgb.b}), rgb(255, ${rgb.g}, ${rgb.b}))`,
}));

const greenSliderStyle = computed(() => ({
  background: `linear-gradient(90deg, rgb(${rgb.r}, 0, ${rgb.b}), rgb(${rgb.r}, 255, ${rgb.b}))`,
}));

const blueSliderStyle = computed(() => ({
  background: `linear-gradient(90deg, rgb(${rgb.r}, ${rgb.g}, 0), rgb(${rgb.r}, ${rgb.g}, 255))`,
}));

const wheelMarkerStyle = computed(() => {
  const radius = wheelSize / 2;
  const angle = (hsv.h * Math.PI) / 180;
  const distance = (hsv.s / 100) * radius;
  const x = radius + Math.cos(angle) * distance;
  const y = radius + Math.sin(angle) * distance;
  return {
    left: `${x}px`,
    top: `${y}px`,
    borderColor: hsv.v < 55 ? "#ffffff" : "#0f172a",
    boxShadow: "0 0 0 1px rgba(15, 23, 42, 0.2)",
  };
});

watch(
  () => props.modelValue,
  (next) => {
    const parsed = parseColor(next) || parseColor(props.fallbackColor) || { r: 255, g: 255, b: 255 };
    setFromRgb(parsed.r, parsed.g, parsed.b, false);
  },
  { immediate: true }
);

watch(
  () => [hsv.v, mode.value, isOpen.value],
  async () => {
    if (!isOpen.value) return;
    await nextTick();
    updatePanelPosition();
    if (mode.value === "wheel") {
      drawWheel();
    }
  }
);

function togglePanel() {
  if (isOpen.value) {
    closePanel();
    return;
  }
  isOpen.value = true;
  nextTick(() => {
    updatePanelPosition();
    if (mode.value === "wheel") drawWheel();
  });
}

function closePanel() {
  isOpen.value = false;
}

function onRgbInput(channel, nextValue) {
  const value = clampInt(nextValue, 0, 255);
  rgb[channel] = value;
  const nextHsv = rgbToHsv(rgb.r, rgb.g, rgb.b);
  hsv.h = nextHsv.h;
  hsv.s = nextHsv.s;
  hsv.v = nextHsv.v;
  emitColor();
}

function onHsvInput(channel, nextValue) {
  if (channel === "h") hsv.h = clampInt(nextValue, 0, 360);
  if (channel === "s") hsv.s = clampInt(nextValue, 0, 100);
  if (channel === "v") hsv.v = clampInt(nextValue, 0, 100);
  const nextRgb = hsvToRgb(hsv.h, hsv.s, hsv.v);
  rgb.r = nextRgb.r;
  rgb.g = nextRgb.g;
  rgb.b = nextRgb.b;
  emitColor();
}

function commitHexInput() {
  const parsed = parseColor(hexInput.value);
  if (!parsed) {
    hexInput.value = currentHex.value.toUpperCase();
    return;
  }
  setFromRgb(parsed.r, parsed.g, parsed.b, true);
}

function setFromRgb(r, g, b, emitUpdate) {
  rgb.r = clampInt(r, 0, 255);
  rgb.g = clampInt(g, 0, 255);
  rgb.b = clampInt(b, 0, 255);
  const nextHsv = rgbToHsv(rgb.r, rgb.g, rgb.b);
  hsv.h = nextHsv.h;
  hsv.s = nextHsv.s;
  hsv.v = nextHsv.v;
  if (emitUpdate) emitColor();
  else hexInput.value = currentHex.value.toUpperCase();
}

function emitColor() {
  const hex = currentHex.value;
  hexInput.value = hex.toUpperCase();
  if ((props.modelValue || "").toLowerCase() !== hex.toLowerCase()) {
    emit("update:modelValue", hex);
  }
}

function updatePanelPosition() {
  const rect = triggerRef.value?.getBoundingClientRect();
  if (!rect) return;
  const panelWidth = 320;
  const panelHeight = mode.value === "wheel" ? 510 : 560;
  const margin = 8;
  const viewportW = window.innerWidth;
  const viewportH = window.innerHeight;
  const openAbove = viewportH - rect.bottom < panelHeight && rect.top > panelHeight;
  const top = openAbove ? Math.max(margin, rect.top - panelHeight - 6) : Math.min(viewportH - panelHeight - margin, rect.bottom + 6);
  const left = Math.min(
    Math.max(margin, rect.left),
    Math.max(margin, viewportW - panelWidth - margin)
  );
  panelStyle.value = {
    position: "fixed",
    top: `${Math.round(top)}px`,
    left: `${Math.round(left)}px`,
    zIndex: VCP_PANEL_Z_INDEX,
  };
}

function onWheelPointerDown(event) {
  draggingWheel = true;
  updateFromWheelPointer(event);
  window.addEventListener("pointermove", onWheelPointerMove);
  window.addEventListener("pointerup", onWheelPointerUp);
}

function onWheelPointerMove(event) {
  if (!draggingWheel) return;
  updateFromWheelPointer(event);
}

function onWheelPointerUp() {
  draggingWheel = false;
  window.removeEventListener("pointermove", onWheelPointerMove);
  window.removeEventListener("pointerup", onWheelPointerUp);
}

function updateFromWheelPointer(event) {
  const canvas = wheelRef.value;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const radius = wheelSize / 2;
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  const dx = x - radius;
  const dy = y - radius;
  const distance = Math.sqrt(dx * dx + dy * dy);
  const clamped = Math.min(distance, radius);
  const saturation = Math.round((clamped / radius) * 100);
  const hue = Math.round((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
  hsv.h = hue;
  hsv.s = saturation;
  const nextRgb = hsvToRgb(hsv.h, hsv.s, hsv.v);
  rgb.r = nextRgb.r;
  rgb.g = nextRgb.g;
  rgb.b = nextRgb.b;
  emitColor();
}

function drawWheel() {
  const canvas = wheelRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const radius = wheelSize / 2;
  const image = ctx.createImageData(wheelSize, wheelSize);
  for (let y = 0; y < wheelSize; y += 1) {
    for (let x = 0; x < wheelSize; x += 1) {
      const dx = x - radius;
      const dy = y - radius;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const idx = (y * wheelSize + x) * 4;
      if (dist > radius) {
        image.data[idx + 3] = 0;
        continue;
      }
      const saturation = clamp(dist / radius, 0, 1) * 100;
      const hue = ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
      const pixel = hsvToRgb(hue, saturation, hsv.v);
      image.data[idx] = pixel.r;
      image.data[idx + 1] = pixel.g;
      image.data[idx + 2] = pixel.b;
      image.data[idx + 3] = 255;
    }
  }
  ctx.putImageData(image, 0, 0);
}

function onGlobalPointerDown(event) {
  if (!isOpen.value) return;
  const target = event.target;
  const inRoot = rootRef.value?.contains(target);
  const inPanel = panelRef.value?.contains(target);
  if (!inRoot && !inPanel) {
    closePanel();
  }
}

function onGlobalEscape(event) {
  if (event.key === "Escape" && isOpen.value) {
    closePanel();
  }
}

function onViewportChange() {
  if (!isOpen.value) return;
  updatePanelPosition();
}

onMounted(() => {
  document.addEventListener("pointerdown", onGlobalPointerDown, true);
  document.addEventListener("keydown", onGlobalEscape, true);
  window.addEventListener("resize", onViewportChange, true);
  window.addEventListener("scroll", onViewportChange, true);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onGlobalPointerDown, true);
  document.removeEventListener("keydown", onGlobalEscape, true);
  window.removeEventListener("resize", onViewportChange, true);
  window.removeEventListener("scroll", onViewportChange, true);
  window.removeEventListener("pointermove", onWheelPointerMove);
  window.removeEventListener("pointerup", onWheelPointerUp);
});

function parseColor(value) {
  if (typeof value !== "string") return null;
  const raw = value.trim();
  if (!raw) return null;
  const match6 = raw.match(/^#([0-9a-fA-F]{6})$/);
  if (match6) {
    const hex = match6[1];
    return {
      r: parseInt(hex.slice(0, 2), 16),
      g: parseInt(hex.slice(2, 4), 16),
      b: parseInt(hex.slice(4, 6), 16),
    };
  }
  const match3 = raw.match(/^#([0-9a-fA-F]{3})$/);
  if (match3) {
    const hex = match3[1];
    return {
      r: parseInt(hex[0] + hex[0], 16),
      g: parseInt(hex[1] + hex[1], 16),
      b: parseInt(hex[2] + hex[2], 16),
    };
  }
  return null;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, Number(value) || 0));
}

function clampInt(value, min, max) {
  return Math.round(clamp(value, min, max));
}

function rgbToHex(r, g, b) {
  const toHex = (n) => clampInt(n, 0, 255).toString(16).padStart(2, "0");
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function rgbToHsv(r, g, b) {
  const rn = clamp(r, 0, 255) / 255;
  const gn = clamp(g, 0, 255) / 255;
  const bn = clamp(b, 0, 255) / 255;
  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const delta = max - min;
  let h = 0;
  if (delta !== 0) {
    if (max === rn) h = 60 * (((gn - bn) / delta) % 6);
    else if (max === gn) h = 60 * ((bn - rn) / delta + 2);
    else h = 60 * ((rn - gn) / delta + 4);
  }
  if (h < 0) h += 360;
  const s = max === 0 ? 0 : (delta / max) * 100;
  const v = max * 100;
  return {
    h: Math.round(h),
    s: Math.round(s),
    v: Math.round(v),
  };
}

function hsvToRgb(h, s, v) {
  const hue = ((Number(h) % 360) + 360) % 360;
  const sat = clamp(s, 0, 100) / 100;
  const val = clamp(v, 0, 100) / 100;
  const c = val * sat;
  const x = c * (1 - Math.abs(((hue / 60) % 2) - 1));
  const m = val - c;
  let r1 = 0;
  let g1 = 0;
  let b1 = 0;
  if (hue < 60) {
    r1 = c; g1 = x; b1 = 0;
  } else if (hue < 120) {
    r1 = x; g1 = c; b1 = 0;
  } else if (hue < 180) {
    r1 = 0; g1 = c; b1 = x;
  } else if (hue < 240) {
    r1 = 0; g1 = x; b1 = c;
  } else if (hue < 300) {
    r1 = x; g1 = 0; b1 = c;
  } else {
    r1 = c; g1 = 0; b1 = x;
  }
  return {
    r: Math.round((r1 + m) * 255),
    g: Math.round((g1 + m) * 255),
    b: Math.round((b1 + m) * 255),
  };
}

function hsvToHex(h, s, v) {
  const next = hsvToRgb(h, s, v);
  return rgbToHex(next.r, next.g, next.b);
}
</script>

<style scoped>
.vcp-root {
  display: inline-flex;
  position: relative;
  border: solid #0007 1px;
  border-radius: 5px;
}

.vcp-trigger {
  padding: 0;
  border: 1px solid #fff5;
  border-radius: 4px;
  cursor: pointer;
}

.vcp-swatch {
  display: block;
  width: 100%;
  height: 100%;
}

.vcp-panel {
  width: 320px;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.25);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.vcp-mode-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.vcp-tab {
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  color: #334155;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 10px;
  cursor: pointer;
}

.vcp-tab.active {
  background: #e2e8f0;
  border-color: #94a3b8;
  color: #0f172a;
}

.vcp-slider-group {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.vcp-slider-row {
  display: grid;
  grid-template-columns: 28px 1fr 48px;
  align-items: center;
  gap: 8px;
}

.vcp-slider-label {
  font-size: 11px;
  font-weight: 700;
  color: #334155;
}

.vcp-slider {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  appearance: none;
  border: 1px solid #cbd5e1;
  cursor: pointer;
}

.vcp-slider::-webkit-slider-thumb {
  appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1px solid #0f172a33;
  background: #ffffff;
}

.vcp-slider::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1px solid #0f172a33;
  background: #ffffff;
}

.vcp-slider-value {
  width: 48px;
  min-width: 0;
  padding: 3px 4px;
  border: 1px solid #cbd5e1;
  border-radius: 5px;
  background: #ffffff;
  text-align: right;
  font-size: 11px;
  color: #475569;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.vcp-slider-value:focus {
  outline: none;
  border-color: #64748b;
  box-shadow: 0 0 0 2px rgba(100, 116, 139, 0.16);
}

.vcp-slider-value::-webkit-outer-spin-button,
.vcp-slider-value::-webkit-inner-spin-button {
  margin: 0;
}

.vcp-hex-row {
  display: grid;
  grid-template-columns: 34px 1fr;
  align-items: center;
  gap: 8px;
}

.vcp-hex-input {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 12px;
  padding: 7px 9px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  text-transform: uppercase;
}

.vcp-hex-input:focus {
  outline: none;
  border-color: #64748b;
}

.vcp-wheel-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.vcp-wheel-container {
  position: relative;
  margin: 0 auto;
}

.vcp-wheel {
  display: block;
  border-radius: 50%;
  border: 1px solid #cbd5e1;
  touch-action: none;
  cursor: crosshair;
}

.vcp-wheel-marker {
  position: absolute;
  width: 13px;
  height: 13px;
  border-width: 2px;
  border-style: solid;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
}
</style>
