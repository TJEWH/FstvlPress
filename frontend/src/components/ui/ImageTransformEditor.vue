<template>
  <div class="transform-editor">
    <div class="transform-editor__layout">
      <div class="transform-editor__preview-column">
        <div class="transform-preview-stack" :style="frameStyle">
          <div
            ref="frameRef"
            class="transform-frame"
            :class="{ 'transform-frame--empty': !hasImage, 'transform-frame--disabled': disabled || focalDisabled }"
            @mousedown.prevent="startDrag"
            @touchstart.prevent="startDrag"
          >
            <TransformedImage
              v-if="hasImage"
              :src="imageUrl"
              alt=""
              :show-transparency-grid="true"
              :zoom="safeZoom"
              :focal-x="safeFocalX"
              :focal-y="safeFocalY"
              :rotation="safeRotation"
              :ratio="safeRatio"
              :direction="safeDirection"
              fit="cover"
              loading="eager"
              decoding="sync"
            />
            <span v-else class="transform-placeholder">Select an image to adjust</span>
            <div v-if="hasImage" class="transform-crosshair" :style="crosshairStyle"></div>
            <div v-if="hasImage" class="transform-focus-hint">Drag to set focus point</div>
          </div>

          <div
            v-if="showUrlField && showImageActions"
            class="transform-media-actions"
            :class="{ 'transform-media-actions--empty': !hasImage }"
          >
            <button
              class="btn transform-btn--primary small"
              type="button"
              :disabled="imageUrlEditDisabled"
              @click.stop="chooseImage"
            >
              {{ hasImage ? replaceImageLabel : selectImageLabel }}
            </button>
            <button
              v-if="hasImage && allowClearImage"
              class="btn-danger small"
              type="button"
              :disabled="imageUrlEditDisabled"
              @click.stop="clearImage"
            >
              {{ clearImageLabel }}
            </button>
          </div>
        </div>
      </div>

      <div ref="controlsRef" class="transform-controls">
        <label class="transform-range">
          <span class="transform-label">Zoom</span>
          <strong class="transform-value">{{ safeZoom.toFixed(2) }}x</strong>
          <input
            type="range"
            :min="minZoom"
            :max="maxZoom"
            :step="zoomStep"
            :value="safeZoom"
            :disabled="!hasImage || zoomInputDisabled"
            @input="onZoomInput($event.target.value)"
            @change="emitCommit"
          />
        </label>

        <label class="transform-range">
          <span class="transform-label">Rotation</span>
          <strong class="transform-value">{{ safeRotation.toFixed(0) }}deg</strong>
          <input
            type="range"
            min="-180"
            max="180"
            :step="rotationStep"
            :value="safeRotation"
            :disabled="!hasImage || rotationInputDisabled"
            @input="onRotationInput($event.target.value)"
            @change="emitCommit"
          />
        </label>

        <div class="transform-buttons">
          <button class="transform-btn small" type="button" :disabled="!hasImage || focalInputDisabled" @click="centerFocus">Center</button>
          <button class="transform-btn small" type="button" :disabled="!hasImage || resetDisabled" @click="resetTransform">Reset</button>
        </div>

        <label v-if="showRatio" class="transform-select">
          <span class="transform-label">Ratio</span>
          <select :value="safeRatio" :disabled="disabled || ratioDisabled" @change="onRatioInput($event.target.value)">
            <option v-for="option in normalizedRatioOptions" :key="option.id" :value="option.id">
              {{ option.label }}
            </option>
          </select>
        </label>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import TransformedImage from "./TransformedImage.vue";
import { clamp, normalizeRatio } from "../../utils/imageTransform.js";

const props = defineProps({
  imageUrl: { type: String, default: "" },
  zoom: { type: Number, default: 1 },
  focalX: { type: Number, default: 50 },
  focalY: { type: Number, default: 50 },
  rotation: { type: Number, default: 0 },
  ratio: { type: String, default: "16:9" },
  direction: { type: String, default: "landscape" },
  ratioOptions: { type: Array, default: () => [
    { id: "1:1", label: "1:1" },
    { id: "3:2", label: "3:2" },
    { id: "4:3", label: "4:3" },
    { id: "16:9", label: "16:9" },
    { id: "2:3", label: "2:3" },
  ] },
  showRatio: { type: Boolean, default: false },
  minZoom: { type: Number, default: 1 },
  maxZoom: { type: Number, default: 4 },
  zoomStep: { type: Number, default: 0.05 },
  rotationStep: { type: Number, default: 1 },
  previewMaxHeight: { type: [Number, String], default: null },
  previewAspect: { type: [Number, String], default: null },
  viewContext: { type: String, default: "default" },
  enforceViewportMaxHeight: { type: Boolean, default: true },
  viewportMaxHeightVh: { type: Number, default: 50 },
  disabled: { type: Boolean, default: false },
  imageUrlDisabled: { type: Boolean, default: false },
  zoomDisabled: { type: Boolean, default: false },
  focalDisabled: { type: Boolean, default: false },
  rotationDisabled: { type: Boolean, default: false },
  ratioDisabled: { type: Boolean, default: false },
  showUrlField: { type: Boolean, default: true },
  allowManualUrlEdit: { type: Boolean, default: true },
  urlPlaceholder: { type: String, default: "https://..." },
  showImageActions: { type: Boolean, default: true },
  allowClearImage: { type: Boolean, default: true },
  selectImageLabel: { type: String, default: "Select" },
  replaceImageLabel: { type: String, default: "Replace" },
  clearImageLabel: { type: String, default: "Clear" },
});

const emit = defineEmits([
  "update:zoom",
  "update:focal-x",
  "update:focal-y",
  "update:rotation",
  "update:ratio",
  "update:image-url",
  "commit",
  "choose-image",
  "clear-image",
]);

const frameRef = ref(null);
const controlsRef = ref(null);
const hasImage = computed(() => String(props.imageUrl || "").trim().length > 0);
const safeZoom = computed(() => clamp(props.zoom, props.minZoom, props.maxZoom, 1));
const safeFocalX = computed(() => clamp(props.focalX, 0, 100, 50));
const safeFocalY = computed(() => clamp(props.focalY, 0, 100, 50));
const safeRotation = computed(() => clamp(props.rotation, -180, 180, 0));
const safeRatio = computed(() => normalizeRatio(props.ratio || "16:9"));
const safeDirection = computed(() => (String(props.direction || "").toLowerCase() === "portrait" ? "portrait" : "landscape"));
const imageUrlEditDisabled = computed(() => props.disabled || props.imageUrlDisabled);
const zoomInputDisabled = computed(() => props.disabled || props.zoomDisabled);
const focalInputDisabled = computed(() => props.disabled || props.focalDisabled);
const rotationInputDisabled = computed(() => props.disabled || props.rotationDisabled);
const resetDisabled = computed(() =>
  props.disabled || props.zoomDisabled || props.focalDisabled || props.rotationDisabled
);

const UNBOUNDED_PREVIEW_MAX_HEIGHT = 100000;
const DESKTOP_LAYOUT_MIN_WIDTH = 721;
const viewportHeightPx = ref(0);
const controlsHeightPx = ref(0);
const desktopLayoutActive = ref(false);

const normalizedRatioOptions = computed(() => {
  if (!Array.isArray(props.ratioOptions) || props.ratioOptions.length === 0) {
    return [{ id: "16:9", label: "16:9" }];
  }
  return props.ratioOptions
    .map((entry) => {
      const id = normalizeRatio(entry?.id || entry?.value || entry || "16:9");
      const label = String(entry?.label || id);
      return { id, label };
    })
    .filter((entry, index, arr) => arr.findIndex((x) => x.id === entry.id) === index);
});

function getRatioParts(ratio, direction) {
  const safe = normalizeRatio(ratio || "16:9");
  const map = {
    "1:1": [1, 1],
    "3:2": [3, 2],
    "4:3": [4, 3],
    "16:9": [16, 9],
    "2:3": [2, 3],
    "3:4": [3, 4],
    "4:5": [4, 5],
  };
  const base = map[safe] || [16, 9];
  if (String(direction || "").toLowerCase() === "portrait") {
    return { w: base[1], h: base[0] };
  }
  return { w: base[0], h: base[1] };
}

function normalizePreviewMaxHeight(value, fallback) {
  const raw = Number(value);
  if (!Number.isFinite(raw)) return fallback;
  return Math.max(160, Math.min(UNBOUNDED_PREVIEW_MAX_HEIGHT, Math.round(raw)));
}

const resolvedPreviewMaxHeight = computed(() => {
  return normalizePreviewMaxHeight(props.previewMaxHeight, UNBOUNDED_PREVIEW_MAX_HEIGHT);
});

const resolvedViewportMaxHeightVh = computed(() => {
  const raw = Number(props.viewportMaxHeightVh);
  if (!Number.isFinite(raw)) return 50;
  return clamp(raw, 20, 95, 50);
});

const resolvedPreviewAspect = computed(() => {
  const raw = Number(props.previewAspect);
  if (!Number.isFinite(raw) || raw <= 0) return null;
  return clamp(raw, 0.2, 5, 16 / 9);
});

const frameStyle = computed(() => {
  const ratio = resolvedPreviewAspect.value
    ? { w: resolvedPreviewAspect.value, h: 1 }
    : getRatioParts(safeRatio.value, safeDirection.value);
  const maxHeight = resolvedPreviewMaxHeight.value;
  const viewportCap = props.enforceViewportMaxHeight && viewportHeightPx.value > 0
    ? (viewportHeightPx.value * resolvedViewportMaxHeightVh.value) / 100
    : UNBOUNDED_PREVIEW_MAX_HEIGHT;
  const controlsCap = desktopLayoutActive.value && controlsHeightPx.value > 0
    ? controlsHeightPx.value
    : UNBOUNDED_PREVIEW_MAX_HEIGHT;
  const resolvedCapPx = Math.min(maxHeight, viewportCap, controlsCap);
  const resolvedHeightPx = Math.max(1, resolvedCapPx);
  const resolvedWidthPx = (resolvedHeightPx * ratio.w) / ratio.h;
  return {
    "--editor-ratio": `${ratio.w} / ${ratio.h}`,
    "--editor-max-height": `${Math.round(resolvedHeightPx)}px`,
    "--editor-max-width": `${Math.round(resolvedWidthPx)}px`,
  };
});

const crosshairStyle = computed(() => ({
  left: `${safeFocalX.value}%`,
  top: `${safeFocalY.value}%`,
}));

function onZoomInput(value) {
  if (zoomInputDisabled.value) return;
  emit("update:zoom", clamp(value, props.minZoom, props.maxZoom, 1));
}

function onRotationInput(value) {
  if (rotationInputDisabled.value) return;
  emit("update:rotation", clamp(value, -180, 180, 0));
}

function onRatioInput(value) {
  if (props.disabled || props.ratioDisabled) return;
  emit("update:ratio", normalizeRatio(value));
  emitCommit();
}

function centerFocus() {
  if (focalInputDisabled.value) return;
  emit("update:focal-x", 50);
  emit("update:focal-y", 50);
  emitCommit();
}

function resetTransform() {
  if (resetDisabled.value) return;
  emit("update:zoom", 1);
  emit("update:focal-x", 50);
  emit("update:focal-y", 50);
  emit("update:rotation", 0);
  emitCommit();
}

function emitCommit() {
  emit("commit");
}

function chooseImage() {
  if (imageUrlEditDisabled.value) return;
  emit("choose-image");
}

function clearImage() {
  if (imageUrlEditDisabled.value || !hasImage.value || !props.allowClearImage) return;
  emit("clear-image");
}

function measureControlsHeight() {
  if (!desktopLayoutActive.value) {
    controlsHeightPx.value = 0;
    return;
  }
  const el = controlsRef.value;
  if (!el) {
    controlsHeightPx.value = 0;
    return;
  }
  const rect = el.getBoundingClientRect();
  const next = Math.round(Number(rect.height || 0));
  controlsHeightPx.value = Number.isFinite(next) && next > 0 ? next : 0;
}

function updateDesktopLayoutState() {
  if (typeof window === "undefined") {
    desktopLayoutActive.value = false;
    controlsHeightPx.value = 0;
    return;
  }
  desktopLayoutActive.value = Number(window.innerWidth || 0) >= DESKTOP_LAYOUT_MIN_WIDTH;
  measureControlsHeight();
}

function updateViewportHeight() {
  if (typeof window === "undefined") {
    viewportHeightPx.value = 0;
    return;
  }
  const next = Number(window.innerHeight || 0);
  viewportHeightPx.value = Number.isFinite(next) ? next : 0;
}

function updateLayoutMetrics() {
  updateViewportHeight();
  updateDesktopLayoutState();
}

function getPoint(event) {
  if (event?.touches?.length) return event.touches[0];
  if (event?.changedTouches?.length) return event.changedTouches[0];
  return event;
}

function emitFromPointer(event) {
  if (!hasImage.value || focalInputDisabled.value) return;
  const frame = frameRef.value;
  if (!frame) return;
  const rect = frame.getBoundingClientRect();
  const point = getPoint(event);
  if (!point || rect.width <= 0 || rect.height <= 0) return;
  const x = ((point.clientX - rect.left) / rect.width) * 100;
  const y = ((point.clientY - rect.top) / rect.height) * 100;
  emit("update:focal-x", Math.round(clamp(x, 0, 100, 50) * 10) / 10);
  emit("update:focal-y", Math.round(clamp(y, 0, 100, 50) * 10) / 10);
}

let dragging = false;

function startDrag(event) {
  if (!hasImage.value || focalInputDisabled.value) return;
  dragging = true;
  emitFromPointer(event);
  window.addEventListener("mousemove", onDragMove);
  window.addEventListener("mouseup", stopDrag);
  window.addEventListener("touchmove", onDragMove, { passive: false });
  window.addEventListener("touchend", stopDrag);
}

function onDragMove(event) {
  if (!dragging) return;
  event.preventDefault?.();
  emitFromPointer(event);
}

function stopDrag() {
  const wasDragging = dragging;
  dragging = false;
  window.removeEventListener("mousemove", onDragMove);
  window.removeEventListener("mouseup", stopDrag);
  window.removeEventListener("touchmove", onDragMove);
  window.removeEventListener("touchend", stopDrag);
  if (wasDragging) emitCommit();
}

onBeforeUnmount(stopDrag);
let controlsResizeObserver = null;
onMounted(() => {
  updateLayoutMetrics();
  if (typeof window === "undefined") return;
  window.addEventListener("resize", updateLayoutMetrics, { passive: true });
  if (typeof ResizeObserver !== "undefined" && controlsRef.value) {
    controlsResizeObserver = new ResizeObserver(measureControlsHeight);
    controlsResizeObserver.observe(controlsRef.value);
  }
  window.requestAnimationFrame?.(measureControlsHeight);
});
onBeforeUnmount(() => {
  controlsResizeObserver?.disconnect();
  controlsResizeObserver = null;
  if (typeof window === "undefined") return;
  window.removeEventListener("resize", updateLayoutMetrics);
});
</script>

<style scoped>
.transform-editor {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.transform-editor__layout {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(170px, 3fr);
  gap: 10px;
}

.transform-editor__preview-column {
  min-width: 0;
}

.transform-preview-stack {
  display: grid;
  gap: 8px;
  width: var(--editor-max-width, 100%);
  max-width: 100%;
  margin: 0 auto;
}

.transform-frame {
  position: relative;
  width: 100%;
  max-width: 100%;
  aspect-ratio: var(--editor-ratio, 16 / 9);
  max-height: var(--editor-max-height, 50vh);
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  overflow: hidden;
  background-color: #f8fafc;
  background-image:
    linear-gradient(45deg, rgba(148, 163, 184, 0.24) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(148, 163, 184, 0.24) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(148, 163, 184, 0.24) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(148, 163, 184, 0.24) 75%);
  background-size: 14px 14px;
  background-position: 0 0, 0 7px, 7px -7px, -7px 0;
  cursor: crosshair;
  user-select: none;
}

.transform-frame--empty {
  display: grid;
  place-items: center;
  cursor: default;
}

.transform-frame--disabled {
  cursor: default;
}

.transform-placeholder {
  text-align: center;
  font-size: 0.82rem;
  color: #64748b;
}

.transform-crosshair {
  position: absolute;
  width: 16px;
  height: 16px;
  border: 2px solid #fff;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  box-shadow: 0 0 0 2px rgba(15, 23, 42, 0.45);
  pointer-events: none;
}

.transform-crosshair::before,
.transform-crosshair::after {
  content: "";
  position: absolute;
  background: rgba(255, 255, 255, 0.9);
}

.transform-crosshair::before {
  left: 50%;
  top: -7px;
  width: 1px;
  height: 26px;
  transform: translateX(-50%);
}

.transform-crosshair::after {
  top: 50%;
  left: -7px;
  width: 26px;
  height: 1px;
  transform: translateY(-50%);
}

.transform-focus-hint {
  position: absolute;
  left: 10px;
  bottom: 10px;
  z-index: 2;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  color: rgba(241, 245, 249, 0.95);
  background: rgba(15, 23, 42, 0.6);
  pointer-events: none;
  backdrop-filter: blur(2px);
}

.transform-media-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  width: 100%;
}

.transform-media-actions--empty {
  grid-template-columns: 1fr;
}

.transform-media-actions button {
  display: block;
  width: 100%;
  min-width: 0;
}

.transform-media-actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.transform-controls {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.transform-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #475569;
}

.transform-value {
  font-size: 0.75rem;
  font-weight: 700;
  color: #1f2937;
}

.transform-range {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 4px 8px;
  font-size: 0.75rem;
  color: #334155;
  padding: 6px 8px 8px;
  border: 1px solid rgba(203, 213, 225, 0.9);
  border-radius: 8px;
  background: #fff;
}

.transform-range input[type="range"] {
  grid-column: 1 / -1;
  width: 100%;
  margin: 0;
}

.transform-select {
  display: grid;
  gap: 4px;
  font-size: 0.75rem;
  color: #334155;
  min-width: 0;
}

.transform-select select {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  background: #fff;
  color: #334155;
  padding: 5px 8px;
  height: 30px;
}

.transform-buttons {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.transform-btn {
  width: 100%;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  border-radius: 7px;
  padding: 5px 10px;
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
}

.transform-btn--primary {
  background: #0f172a;
  border-color: #0f172a;
  color: #f8fafc;
}

.transform-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .transform-editor__layout {
    grid-template-columns: 1fr;
  }

  .transform-preview-stack {
    width: 100%;
  }

  .transform-select {
    width: 100%;
  }

  .transform-buttons {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
