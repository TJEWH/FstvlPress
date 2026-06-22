<template>
  <SectionBase :section-key="effectiveKey" :section-data="section" class="map-section">
    <div v-if="svgUrl || state.isAdmin" class="map-section__wrap">
      <div
        v-if="svgUrl"
        ref="viewportEl"
        class="map-viewport"
        :class="{ 'map-viewport--dragging': isDragging }"
        tabindex="0"
        role="img"
        :aria-label="altText || sectionTitle"
        @keydown="handleKeydown"
        @pointerdown="handlePointerDown"
        @pointermove="handlePointerMove"
        @pointerup="handlePointerUp"
        @pointercancel="handlePointerUp"
        @lostpointercapture="handlePointerUp"
      >
        <div class="map-pan-layer" :style="panLayerStyle">
          <img
            class="map-image"
            :src="svgUrl"
            :alt="altText"
            draggable="false"
            :style="imageStyle"
            @load="clampCurrentView"
          />
        </div>

        <div class="map-controls" aria-label="Map controls" @pointerdown.stop>
          <button
            class="map-control-btn"
            type="button"
            title="Zoom in"
            aria-label="Zoom in"
            :disabled="!canZoomIn"
            @click="zoomIn"
          >
            <font-awesome-icon :icon="faPlus" />
          </button>
          <button
            class="map-control-btn"
            type="button"
            title="Zoom out"
            aria-label="Zoom out"
            :disabled="!canZoomOut"
            @click="zoomOut"
          >
            <font-awesome-icon :icon="faMinus" />
          </button>
          <button
            class="map-control-btn"
            type="button"
            title="Reset view"
            aria-label="Reset view"
            @click="resetView"
          >
            <font-awesome-icon :icon="faRotateLeft" />
          </button>
        </div>
      </div>

      <div v-else class="map-empty">
        <font-awesome-icon :icon="faMap" class="map-empty__icon" />
        <span>Choose an SVG map</span>
      </div>
    </div>

    <MediaLibrary
      :is-open="showMediaPicker"
      :current-url="svgUrl"
      source-context="section.map.svg"
      @close="closeMediaPicker"
      @select="onMediaSelect"
    />

    <template #admin-content>
      <div class="editor map-editor">
        <div class="map-editor__media">
          <div class="item-thumb item-thumb--media map-editor__thumb">
            <div class="thumb-img-wrap map-editor__thumb-frame">
              <img
                v-if="svgUrl"
                class="thumb-img map-editor__thumb-img"
                :src="svgUrl"
                alt=""
                draggable="false"
              />
              <div v-else class="thumb-empty">
                <font-awesome-icon :icon="faMap" />
              </div>
            </div>
          </div>
          <div class="map-editor__media-body">
            <label class="field-label">SVG map</label>
            <div class="map-editor__filename">{{ mapStatusLabel }}</div>
            <div class="map-editor__actions">
              <button
                class="btn"
                type="button"
                :disabled="isMapFieldLocked('svgUrl') || isMapFieldLocked('svg_url')"
                :title="isMapFieldLocked('svgUrl') || isMapFieldLocked('svg_url') ? integrationLockedHint : undefined"
                @click="openMediaPicker"
              >
                <font-awesome-icon :icon="faImage" />
                <span>Choose SVG</span>
              </button>
              <button
                class="btn-secondary"
                type="button"
                :disabled="!svgUrl || isMapFieldLocked('svgUrl') || isMapFieldLocked('svg_url')"
                :title="isMapFieldLocked('svgUrl') || isMapFieldLocked('svg_url') ? integrationLockedHint : undefined"
                @click="clearMap"
              >
                <font-awesome-icon :icon="faXmark" />
                <span>Clear</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </SectionBase>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  faImage,
  faMap,
  faMinus,
  faPlus,
  faRotateLeft,
  faXmark,
} from "@fortawesome/free-solid-svg-icons";
import { useStore } from "../../store/store.js";
import { isSectionIntegrationFieldLocked } from "../../utils/sectionIntegrationFieldState.js";
import SectionBase from "./_BaseSection.vue";
import MediaLibrary from "../ui/MediaLibrary.vue";

const props = defineProps({
  sectionKey: { type: String, default: "map" },
  sectionData: { type: Object, default: null },
});

const MIN_ZOOM = 1;
const MAX_ZOOM = 4;
const ZOOM_STEP = 0.25;
const KEYBOARD_PAN_STEP = 32;
const integrationLockedHint = "Managed by integration import.";

const { state, localizedText, updateSection } = useStore();

const effectiveKey = computed(() => props.sectionKey);
const section = computed(() => {
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});

const viewportEl = ref(null);
const showMediaPicker = ref(false);
const zoom = ref(MIN_ZOOM);
const offsetX = ref(0);
const offsetY = ref(0);
const isDragging = ref(false);

const activePointers = new Map();
let dragStart = null;
let pinchStart = null;
let resizeObserver = null;

const svgUrl = computed(() => String(section.value?.svgUrl || "").trim());
const altValue = computed(() => normalizeBilingual(section.value?.alt));
const altText = computed(() => localizedText(altValue.value));
const sectionTitle = computed(() => localizedText(section.value?.title) || "Map");
const mapStatusLabel = computed(() => {
  if (!svgUrl.value) return "No SVG selected";
  const decodeFilename = (value) => {
    try {
      return decodeURIComponent(value);
    } catch {
      return value;
    }
  };
  try {
    const baseUrl = typeof window !== "undefined" ? window.location.origin : "http://localhost";
    const parsed = new URL(svgUrl.value, baseUrl);
    const filename = decodeFilename(parsed.pathname.split("/").filter(Boolean).pop() || "");
    return filename || "Selected SVG";
  } catch {
    const filename = decodeFilename(svgUrl.value.split(/[/?#]/).filter(Boolean).pop() || "");
    return filename || "Selected SVG";
  }
});
const canZoomIn = computed(() => zoom.value < MAX_ZOOM);
const canZoomOut = computed(() => zoom.value > MIN_ZOOM);
const panLayerStyle = computed(() => ({
  transform: `translate3d(${offsetX.value}px, ${offsetY.value}px, 0)`,
}));
const imageStyle = computed(() => ({
  transform: `scale(${zoom.value})`,
}));

function normalizeBilingual(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return {
      de: String(value.de || ""),
      en: String(value.en || ""),
    };
  }
  const text = String(value || "");
  return { de: text, en: text };
}

function isMapFieldLocked(path, options = {}) {
  return state.isAdmin && isSectionIntegrationFieldLocked(section.value, path, options);
}

function clamp(value, min, max) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return min;
  return Math.max(min, Math.min(max, numeric));
}

function clampZoom(value) {
  const rounded = Math.round(clamp(value, MIN_ZOOM, MAX_ZOOM) / ZOOM_STEP) * ZOOM_STEP;
  return clamp(Number(rounded.toFixed(2)), MIN_ZOOM, MAX_ZOOM);
}

function clampOffsetPair(xValue, yValue, zoomValue = zoom.value) {
  if (zoomValue <= MIN_ZOOM) return { x: 0, y: 0 };
  const viewport = viewportEl.value;
  const width = Number(viewport?.clientWidth || 0);
  const height = Number(viewport?.clientHeight || 0);
  const maxX = Math.max(0, (width * (zoomValue - 1)) / 2);
  const maxY = Math.max(0, (height * (zoomValue - 1)) / 2);
  return {
    x: clamp(xValue, -maxX, maxX),
    y: clamp(yValue, -maxY, maxY),
  };
}

function setView(nextZoom, nextX = offsetX.value, nextY = offsetY.value) {
  const normalizedZoom = clampZoom(nextZoom);
  const nextOffset = clampOffsetPair(nextX, nextY, normalizedZoom);
  zoom.value = normalizedZoom;
  offsetX.value = nextOffset.x;
  offsetY.value = nextOffset.y;
}

function clampCurrentView() {
  setView(zoom.value, offsetX.value, offsetY.value);
}

function resetView() {
  setView(MIN_ZOOM, 0, 0);
}

function zoomIn() {
  setView(zoom.value + ZOOM_STEP);
}

function zoomOut() {
  setView(zoom.value - ZOOM_STEP);
}

function panBy(deltaX, deltaY) {
  if (zoom.value <= MIN_ZOOM) return;
  setView(zoom.value, offsetX.value + deltaX, offsetY.value + deltaY);
}

function pointerSnapshot(event) {
  return {
    x: Number(event.clientX || 0),
    y: Number(event.clientY || 0),
  };
}

function getPointerValues() {
  return Array.from(activePointers.values());
}

function pointerDistance(left, right) {
  return Math.hypot(right.x - left.x, right.y - left.y);
}

function startDrag(pointer) {
  dragStart = {
    x: pointer.x,
    y: pointer.y,
    offsetX: offsetX.value,
    offsetY: offsetY.value,
  };
  pinchStart = null;
  isDragging.value = true;
}

function startPinch() {
  const pointers = getPointerValues();
  if (pointers.length < 2) return;
  const distance = pointerDistance(pointers[0], pointers[1]);
  if (distance <= 0) return;
  pinchStart = {
    distance,
    zoom: zoom.value,
  };
  dragStart = null;
  isDragging.value = false;
}

function handlePointerDown(event) {
  if (event.pointerType === "mouse" && event.button !== 0) return;
  activePointers.set(event.pointerId, pointerSnapshot(event));
  try {
    event.currentTarget.setPointerCapture(event.pointerId);
  } catch {
    // Ignore browsers that cannot capture this pointer.
  }
  if (activePointers.size >= 2) {
    startPinch();
    return;
  }
  startDrag(pointerSnapshot(event));
}

function handlePointerMove(event) {
  if (!activePointers.has(event.pointerId)) return;
  activePointers.set(event.pointerId, pointerSnapshot(event));

  if (activePointers.size >= 2 && pinchStart) {
    const pointers = getPointerValues();
    const distance = pointerDistance(pointers[0], pointers[1]);
    if (distance > 0) {
      setView(pinchStart.zoom * (distance / pinchStart.distance));
    }
    return;
  }

  if (!dragStart || activePointers.size !== 1) return;
  const pointer = pointerSnapshot(event);
  setView(
    zoom.value,
    dragStart.offsetX + pointer.x - dragStart.x,
    dragStart.offsetY + pointer.y - dragStart.y,
  );
}

function handlePointerUp(event) {
  activePointers.delete(event.pointerId);
  if (activePointers.size >= 2) {
    startPinch();
    return;
  }
  if (activePointers.size === 1) {
    startDrag(getPointerValues()[0]);
    return;
  }
  dragStart = null;
  pinchStart = null;
  isDragging.value = false;
}

function handleKeydown(event) {
  const key = String(event.key || "");
  if (key === "+" || key === "=") {
    event.preventDefault();
    zoomIn();
    return;
  }
  if (key === "-" || key === "_") {
    event.preventDefault();
    zoomOut();
    return;
  }
  if (key === "0" || key === "Home") {
    event.preventDefault();
    resetView();
    return;
  }
  if (key === "ArrowLeft") {
    event.preventDefault();
    panBy(KEYBOARD_PAN_STEP, 0);
    return;
  }
  if (key === "ArrowRight") {
    event.preventDefault();
    panBy(-KEYBOARD_PAN_STEP, 0);
    return;
  }
  if (key === "ArrowUp") {
    event.preventDefault();
    panBy(0, KEYBOARD_PAN_STEP);
    return;
  }
  if (key === "ArrowDown") {
    event.preventDefault();
    panBy(0, -KEYBOARD_PAN_STEP);
  }
}

function openMediaPicker() {
  if (isMapFieldLocked("svgUrl") || isMapFieldLocked("svg_url")) return;
  showMediaPicker.value = true;
}

function closeMediaPicker() {
  showMediaPicker.value = false;
}

function updateMapSection(patch) {
  updateSection(effectiveKey.value, patch, { revisionKind: "content" });
}

function onMediaSelect(selection) {
  if (isMapFieldLocked("svgUrl") || isMapFieldLocked("svg_url")) {
    closeMediaPicker();
    return;
  }
  const selectedUrl = String(selection?.url || "").trim();
  const selectedAlt = normalizeBilingual(selection?.alt);
  const filenameFallback = String(selection?.filename || "").trim();
  const nextAlt = {
    de: selectedAlt.de || filenameFallback || altValue.value.de,
    en: selectedAlt.en || filenameFallback || altValue.value.en,
  };
  updateMapSection({
    svgUrl: selectedUrl,
    assetId: String(selection?.id || "").trim(),
    alt: nextAlt,
  });
  resetView();
  closeMediaPicker();
}

function clearMap() {
  if (isMapFieldLocked("svgUrl") || isMapFieldLocked("svg_url")) return;
  updateMapSection({
    svgUrl: "",
    assetId: "",
  });
  resetView();
}

function observeViewport() {
  if (!resizeObserver) return;
  resizeObserver.disconnect();
  if (viewportEl.value) resizeObserver.observe(viewportEl.value);
}

watch(svgUrl, () => {
  activePointers.clear();
  dragStart = null;
  pinchStart = null;
  isDragging.value = false;
  resetView();
  nextTick(() => {
    observeViewport();
    clampCurrentView();
  });
});

onMounted(() => {
  if (typeof window === "undefined" || typeof window.ResizeObserver !== "function") return;
  resizeObserver = new window.ResizeObserver(() => clampCurrentView());
  observeViewport();
});

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});
</script>

<style scoped>
.map-section__wrap {
  width: 100%;
}

.map-viewport {
  position: relative;
  width: 100%;
  height: min(70vh, 720px);
  min-height: 320px;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--section-border-color, #0b1220) 18%, transparent);
  border-radius: min(var(--section-border-radius, 14px), 12px);
  background:
    linear-gradient(45deg, rgba(15, 23, 42, 0.04) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(15, 23, 42, 0.04) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(15, 23, 42, 0.04) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(15, 23, 42, 0.04) 75%),
    color-mix(in srgb, var(--section-background-color, #ffffff) 88%, #ffffff);
  background-position: 0 0, 0 10px, 10px -10px, -10px 0;
  background-size: 20px 20px;
  cursor: grab;
  touch-action: none;
}

.map-viewport:focus-visible {
  outline: 2px solid var(--button-primary-bg, var(--primary-color, #0b1220));
  outline-offset: 3px;
}

.map-viewport--dragging {
  cursor: grabbing;
}

.map-pan-layer {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  will-change: transform;
}

.map-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  user-select: none;
  pointer-events: none;
  will-change: transform;
  transition: transform 120ms ease;
}

.map-viewport--dragging .map-image {
  transition: none;
}

.map-controls {
  position: absolute;
  left: 50%;
  right: auto;
  bottom: 12px;
  z-index: 2;
  display: inline-flex;
  transform: translateX(-50%);
  gap: 6px;
  padding: 6px;
  border: 1px solid rgba(15, 23, 42, 0.14);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.16);
  backdrop-filter: blur(10px);
}

.map-control-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 6px;
  color: #0f172a;
  background: transparent;
  cursor: pointer;
}

.map-control-btn:hover:not(:disabled),
.map-control-btn:focus-visible {
  background: rgba(15, 23, 42, 0.08);
}

.map-control-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.map-empty {
  display: flex;
  min-height: 220px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1px dashed rgba(15, 23, 42, 0.25);
  border-radius: min(var(--section-border-radius, 14px), 12px);
  color: var(--secondary-color, #334155);
}

.map-empty__icon {
  font-size: 1.3rem;
}

.map-editor {
  display: grid;
  gap: 16px;
}

.map-editor__media {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: center;
}

.map-editor__thumb {
  padding: 0;
}

.map-editor__thumb-frame {
  width: 104px;
  height: 72px;
  border: 1px solid var(--admin-border, #e2e8f0);
  border-radius: 8px;
  overflow: hidden;
  background-color: #f8fafc;
  background-image:
    linear-gradient(45deg, rgba(148, 163, 184, 0.24) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(148, 163, 184, 0.24) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(148, 163, 184, 0.24) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(148, 163, 184, 0.24) 75%);
  background-size: 12px 12px;
  background-position: 0 0, 0 6px, 6px -6px, -6px 0;
  display: grid;
  place-items: center;
}

.map-editor__thumb-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #fff;
}

.thumb-empty {
  display: grid;
  place-items: center;
  color: var(--admin-text-muted, #94a3b8);
  font-size: 22px;
  opacity: 0.7;
}

.map-editor__media-body {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.map-editor__filename {
  min-width: 0;
  color: var(--admin-text-muted, #64748b);
  font-size: 0.86rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.map-editor__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.map-editor__actions .btn,
.map-editor__actions .btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.field-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--admin-text-muted, #64748b);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

@media (max-width: 720px) {
  .map-viewport {
    height: min(62vh, 520px);
    min-height: 280px;
  }

  .map-controls {
    bottom: 8px;
  }

  .map-control-btn {
    width: 36px;
    height: 36px;
  }

  .map-editor__media {
    grid-template-columns: 1fr;
  }
}
</style>
