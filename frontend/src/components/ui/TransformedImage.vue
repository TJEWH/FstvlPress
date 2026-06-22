<template>
  <div
    ref="rootRef"
    class="transformed-image"
    :class="{ 'transformed-image--checker': showTransparencyGrid }"
    :style="wrapperStyle"
  >
    <div v-if="src" class="transformed-image__viewport" :style="viewportStyle">
      <img
        ref="imgRef"
        :src="src"
        :srcset="imgSrcset || undefined"
        :sizes="imgSrcset ? imgSizes : undefined"
        :alt="alt"
        :class="imgClass"
        :style="imageStyle"
        :loading="loading"
        :decoding="decoding"
        :fetchpriority="fetchPriority || undefined"
        @load="handleImageLoad"
        draggable="false"
      />
    </div>
    <slot v-else name="empty" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  buildImageTransformStyle,
  calculateRotationGuardScale,
  normalizeRatio,
  normalizeTransform,
  parseAspectRatio,
  ratioToCss,
} from "../../utils/imageTransform.js";
import {
  buildResponsiveSrcset,
  mergeResponsiveVariants,
} from "../../utils/responsiveImages.js";

const props = defineProps({
  src: { type: String, default: "" },
  alt: { type: String, default: "" },
  zoom: { type: Number, default: 1 },
  focalX: { type: Number, default: 50 },
  focalY: { type: Number, default: 50 },
  rotation: { type: Number, default: 0 },
  ratio: { type: String, default: "" },
  direction: { type: String, default: "landscape" },
  fit: { type: String, default: "cover" },
  loading: { type: String, default: "lazy" },
  decoding: { type: String, default: "async" },
  fetchPriority: { type: String, default: "" },
  imgClass: { type: String, default: "" },
  showTransparencyGrid: { type: Boolean, default: false },
  useObjectPosition: { type: Boolean, default: true },
  // Each entry: { url: string, width: number }
  responsiveVariants: { type: Array, default: () => [] },
  // Optional image-like object carrying frontend responsive image metadata.
  imageData: { type: Object, default: null },
  // Multiplies measured CSS width when computing `sizes`.
  // Useful when a parent visually scales this image with CSS transforms.
  renderScale: { type: Number, default: 1 },
  // Optional initial render scale used before upgrading to `renderScale`.
  initialRenderScale: { type: Number, default: 0 },
  // When true, upgrades from `initialRenderScale` to `renderScale`
  // after the first image load and an idle callback.
  lazyRenderScaleUpgrade: { type: Boolean, default: false },
  // Optional slot width hint (CSS px) used before ResizeObserver measurements are available.
  slotWidth: { type: Number, default: 0 },
});

const rootRef = ref(null);
const imgRef = ref(null);
const measuredAspect = ref(0);
const measuredWidth = ref(0);
let resizeObserver = null;
let upgradeIdleId = null;
let upgradeTimerId = null;
const baseImageLoaded = ref(false);
const renderScaleUpgraded = ref(true);

function updateMeasuredAspect() {
  const el = rootRef.value;
  if (!el) {
    measuredAspect.value = 0;
    measuredWidth.value = 0;
    return;
  }
  const width = Number(el.clientWidth || 0);
  const height = Number(el.clientHeight || 0);
  measuredWidth.value = width;
  if (width > 0 && height > 0) {
    measuredAspect.value = width / height;
    return;
  }
  measuredAspect.value = 0;
}

function isSvgImageUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return false;
  if (/^data:image\/svg\+xml[;,]/i.test(raw)) return true;
  const path = raw.split("#", 1)[0].split("?", 1)[0].trim().toLowerCase();
  return path.endsWith(".svg");
}

onMounted(() => {
  updateMeasuredAspect();
  if (typeof window === "undefined" || typeof window.ResizeObserver !== "function") return;
  resizeObserver = new window.ResizeObserver(() => updateMeasuredAspect());
  if (rootRef.value) resizeObserver.observe(rootRef.value);
});

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  cancelRenderScaleUpgradeSchedule();
});

const wrapperStyle = computed(() => {
  const style = {
    "--transformed-fit": props.fit || "cover",
  };
  const ratio = String(props.ratio || "").trim();
  if (ratio) {
    style.aspectRatio = ratioToCss(normalizeRatio(ratio), props.direction);
  }
  return style;
});

const safeTransform = computed(() =>
  normalizeTransform({
    zoom: props.zoom,
    focalX: props.focalX,
    focalY: props.focalY,
    rotation: props.rotation,
  })
);

const resolvedAspect = computed(() => {
  if (measuredAspect.value > 0) return measuredAspect.value;
  const ratioCss = ratioToCss(normalizeRatio(String(props.ratio || "").trim() || "16:9"), props.direction);
  return parseAspectRatio(ratioCss, 16 / 9);
});

const rotationGuardScale = computed(() =>
  (() => {
    const base = calculateRotationGuardScale(safeTransform.value.rotation, resolvedAspect.value);
    if (safeTransform.value.rotation === 0) return 1;
    // Small guard margin prevents sub-pixel corner clipping when focus shifts after rotation.
    return base * 1.02;
  })()
);

const viewportStyle = computed(() => {
  const transforms = [];
  if (safeTransform.value.rotation !== 0) {
    transforms.push(`rotate(${safeTransform.value.rotation}deg)`);
  }
  if (rotationGuardScale.value !== 1) {
    transforms.push(`scale(${rotationGuardScale.value})`);
  }
  return {
    transform: transforms.length ? transforms.join(" ") : "none",
    // Keep rotation anchored to center so changing focus later does not introduce persistent clipping.
    transformOrigin: "50% 50%",
  };
});

const imageStyle = computed(() => {
  const style = buildImageTransformStyle({
    zoom: safeTransform.value.zoom / rotationGuardScale.value,
    focalX: safeTransform.value.focalX,
    focalY: safeTransform.value.focalY,
  });
  if (!props.useObjectPosition) {
    delete style.objectPosition;
  }
  return style;
});

// Emit srcset as soon as variants are available so the browser can choose
// a responsive candidate on first paint instead of fetching the original src.
const imgSrcset = computed(() => {
  if (isSvgImageUrl(props.src)) return "";
  const imageData = props.imageData && typeof props.imageData === "object"
    ? props.imageData
    : {};
  const variants = mergeResponsiveVariants([
    Array.isArray(imageData.responsiveVariants) ? imageData.responsiveVariants : [],
    Array.isArray(props.responsiveVariants) ? props.responsiveVariants : [],
  ]);
  return buildResponsiveSrcset(variants);
});

const targetRenderScale = computed(() => (
  Number.isFinite(props.renderScale) && props.renderScale > 0
    ? props.renderScale
    : 1
));

const baseRenderScale = computed(() => {
  const requested = Number.isFinite(props.initialRenderScale) && props.initialRenderScale > 0
    ? props.initialRenderScale
    : targetRenderScale.value;
  return Math.min(requested, targetRenderScale.value);
});

const supportsLazyRenderScaleUpgrade = computed(() => (
  Boolean(props.lazyRenderScaleUpgrade)
    && baseRenderScale.value > 0
    && targetRenderScale.value > baseRenderScale.value
));

const activeRenderScale = computed(() => (
  supportsLazyRenderScaleUpgrade.value && !renderScaleUpgraded.value
    ? baseRenderScale.value
    : targetRenderScale.value
));

// sizes reflects the effective rendered width in CSS pixels.
// We include render scale and image zoom so visually upscaled or zoomed
// elements request a larger candidate from srcset.
// The browser multiplies this by DPR internally.
const imgSizes = computed(() => {
  const safeZoom = Number.isFinite(safeTransform.value.zoom) && safeTransform.value.zoom > 0
    ? safeTransform.value.zoom
    : 1;
  const effectiveScale = activeRenderScale.value * safeZoom;
  const widthHint = Number.isFinite(props.slotWidth) && props.slotWidth > 0
    ? props.slotWidth
    : 0;
  const resolvedWidth = measuredWidth.value > 0 ? measuredWidth.value : widthHint;
  if (resolvedWidth <= 0) {
    // Avoid hard-coding 100vw during first paint, which often causes oversized fetches.
    // For lazy images, omit sizes until width is known.
    return props.loading === "lazy" ? undefined : "100vw";
  }
  const effectiveWidth = Math.max(1, Math.round(resolvedWidth * effectiveScale));
  return `${effectiveWidth}px`;
});

function cancelRenderScaleUpgradeSchedule() {
  if (typeof window !== "undefined" && upgradeIdleId != null && typeof window.cancelIdleCallback === "function") {
    window.cancelIdleCallback(upgradeIdleId);
  }
  if (upgradeTimerId != null) {
    clearTimeout(upgradeTimerId);
  }
  upgradeIdleId = null;
  upgradeTimerId = null;
}

function queueRenderScaleUpgrade() {
  if (!supportsLazyRenderScaleUpgrade.value) return;
  if (renderScaleUpgraded.value) return;
  if (!baseImageLoaded.value) return;
  if (!imgSrcset.value) return;
  if (upgradeIdleId != null || upgradeTimerId != null) return;

  const applyUpgrade = () => {
    upgradeIdleId = null;
    upgradeTimerId = null;
    renderScaleUpgraded.value = true;
  };

  if (typeof window !== "undefined" && typeof window.requestIdleCallback === "function") {
    upgradeIdleId = window.requestIdleCallback(() => applyUpgrade(), { timeout: 1800 });
    return;
  }
  upgradeTimerId = setTimeout(() => applyUpgrade(), 250);
}

function resetRenderScaleUpgradeState() {
  cancelRenderScaleUpgradeSchedule();
  const imageEl = imgRef.value;
  baseImageLoaded.value = Boolean(imageEl?.complete && Number(imageEl?.naturalWidth || 0) > 0);
  renderScaleUpgraded.value = !supportsLazyRenderScaleUpgrade.value;
  queueRenderScaleUpgrade();
}

function handleImageLoad() {
  baseImageLoaded.value = true;
  queueRenderScaleUpgrade();
}

watch(
  () => [
    props.src,
    props.renderScale,
    props.initialRenderScale,
    props.lazyRenderScaleUpgrade,
    imgSrcset.value,
  ],
  () => {
    resetRenderScaleUpgradeState();
  },
  { immediate: true }
);
</script>

<style scoped>
.transformed-image {
  position: relative;
  overflow: hidden;
  width: 100%;
  height: 100%;
}

.transformed-image--checker {
  background-color: #f8fafc;
  background-image:
    linear-gradient(45deg, rgba(148, 163, 184, 0.24) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(148, 163, 184, 0.24) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(148, 163, 184, 0.24) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(148, 163, 184, 0.24) 75%);
  background-size: 14px 14px;
  background-position: 0 0, 0 7px, 7px -7px, -7px 0;
}

.transformed-image__viewport {
  width: 100%;
  height: 100%;
  transform-origin: center center;
}

.transformed-image__viewport > img {
  width: 100%;
  height: 100%;
  object-fit: var(--transformed-fit, cover);
  display: block;
  user-select: none;
}
</style>
