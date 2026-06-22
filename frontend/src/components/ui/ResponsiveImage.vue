<template>
  <img
    ref="imgRef"
    v-bind="$attrs"
    :src="resolvedSrc"
    :srcset="imgSrcset || undefined"
    :sizes="imgSrcset ? imgSizes : undefined"
    :alt="alt"
    :loading="loading"
    :decoding="decoding"
    :draggable="draggable"
  />
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  buildResponsiveSrcset,
  mergeResponsiveVariants,
} from "../../utils/responsiveImages.js";

defineOptions({ inheritAttrs: false });

const props = defineProps({
  src: { type: String, default: "" },
  alt: { type: String, default: "" },
  loading: { type: String, default: "lazy" },
  decoding: { type: String, default: "async" },
  draggable: { type: Boolean, default: false },
  responsiveVariants: { type: Array, default: () => [] },
  imageData: { type: Object, default: null },
  renderScale: { type: Number, default: 1 },
  // Optional slot width hint (CSS px) used before ResizeObserver measurements are available.
  slotWidth: { type: Number, default: 0 },
});

const imgRef = ref(null);
const measuredWidth = ref(0);
let resizeObserver = null;

function updateMeasuredWidth() {
  const el = imgRef.value;
  measuredWidth.value = Number(el?.clientWidth || 0);
}

onMounted(() => {
  updateMeasuredWidth();
  if (typeof window === "undefined" || typeof window.ResizeObserver !== "function") return;
  resizeObserver = new window.ResizeObserver(() => updateMeasuredWidth());
  if (imgRef.value) resizeObserver.observe(imgRef.value);
});

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});

const normalizedImageData = computed(() => (
  props.imageData && typeof props.imageData === "object"
    ? props.imageData
    : {}
));

const resolvedSrc = computed(() => {
  const explicitSrc = String(props.src || "").trim();
  if (explicitSrc) return explicitSrc;
  return String(normalizedImageData.value.imageUrl || "").trim();
});

const resolvedVariants = computed(() => {
  return mergeResponsiveVariants([
    Array.isArray(normalizedImageData.value.responsiveVariants)
      ? normalizedImageData.value.responsiveVariants
      : [],
    Array.isArray(props.responsiveVariants) ? props.responsiveVariants : [],
  ]);
});

const imgSrcset = computed(() => buildResponsiveSrcset(resolvedVariants.value));

const imgSizes = computed(() => {
  const safeScale = Number.isFinite(props.renderScale) && props.renderScale > 0
    ? props.renderScale
    : 1;
  const widthHint = Number.isFinite(props.slotWidth) && props.slotWidth > 0
    ? props.slotWidth
    : 0;
  const resolvedWidth = measuredWidth.value > 0 ? measuredWidth.value : widthHint;
  if (resolvedWidth <= 0) {
    // Avoid hard-coding 100vw during first paint, which often causes oversized fetches.
    // For lazy images, omit the `sizes` attribute until a concrete width is known.
    return props.loading === "lazy" ? undefined : "100vw";
  }
  const effectiveWidth = Math.max(1, Math.round(resolvedWidth * safeScale));
  return `${effectiveWidth}px`;
});
</script>
