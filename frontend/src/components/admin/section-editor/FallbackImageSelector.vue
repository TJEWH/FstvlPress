<template>
  <details class="fallback-selector">
    <summary class="fallback-selector-title">{{ title }}</summary>
    <div class="fallback-selector-content">
      <p v-if="description" class="field-hint">
        {{ description }}
      </p>
      <div class="import-controls-row">
        <div class="import-field">
          <label class="field-label">{{ mergedLabels.mediaTag }}</label>
          <select v-model="selectedMediaTag" class="integration-select">
            <option value="">{{ mergedLabels.mediaTagPlaceholder }}</option>
            <option v-for="tag in mediaTagOptions" :key="`fallback-media-tag-${tag}`" :value="tag">
              {{ tag }}
            </option>
          </select>
        </div>
        <div class="import-field import-field--compact">
          <label class="field-label">{{ mergedLabels.mode }}</label>
          <select v-model="importMode" class="integration-select">
            <option value="replace">{{ mergedLabels.replace }}</option>
            <option value="append">{{ mergedLabels.append }}</option>
          </select>
        </div>
        <button
          type="button"
          class="btn-secondary small"
          @click="loadMediaTags"
          :disabled="loadingMediaTags"
        >
          {{ loadingMediaTags ? mergedLabels.loading : mergedLabels.refresh }}
        </button>
      </div>
      <div class="import-actions">
        <button
          class="btn-primary small"
          type="button"
          @click="importFallbacksFromMediaTag"
          :disabled="!selectedMediaTag || importing"
        >
          {{ importing ? mergedLabels.importing : mergedLabels.importButton }}
        </button>
        <button
          class="btn-secondary small"
          type="button"
          @click="openMediaLibrary"
        >
          {{ mergedLabels.selectFromLibrary }}
        </button>
        <button
          class="btn-secondary small"
          type="button"
          @click="clearFallbackImages"
          :disabled="fallbackImagePool.length === 0"
        >
          {{ mergedLabels.clear }}
        </button>
        <span v-if="status" class="import-status" :class="status.type">
          {{ status.message }}
        </span>
      </div>
      <p class="field-hint" v-if="fallbackImagePool.length > 0">
        {{ loadedHint }}
      </p>
      <div v-if="fallbackImagePool.length > 0" class="fallback-preview-grid">
        <div
          v-for="(fallbackImage, index) in fallbackImagePool"
          :key="fallbackImage.id || `fallback-preview-${index}`"
          class="fallback-preview-item"
        >
          <TransformedImage
            :src="fallbackImage.imageUrl"
            alt=""
            class="fallback-preview-image"
            :ratio="aspectRatio"
            :direction="direction"
            :zoom="1"
            :focal-x="50"
            :focal-y="50"
            :rotation="0"
            fit="cover"
            loading="lazy"
            decoding="async"
          />
        </div>
      </div>
      <ImageTransformEditor
        :image-url="previewImageUrl"
        :zoom="zoom"
        :focal-x="focalX"
        :focal-y="focalY"
        :rotation="rotation"
        :ratio="aspectRatio"
        :direction="direction"
        view-context="section_item"
        :show-url-field="false"
        :show-image-actions="false"
        :allow-manual-url-edit="false"
        :allow-clear-image="false"
        @update:zoom="(v) => emit('update-transform', { zoom: v })"
        @update:focal-x="(v) => emit('update-transform', { focalX: v })"
        @update:focal-y="(v) => emit('update-transform', { focalY: v })"
        @update:rotation="(v) => emit('update-transform', { rotation: v })"
      />
      <MediaLibrary
        :is-open="showMediaPicker"
        :current-url="previewImageUrl"
        :source-context="sourceContext"
        @close="closeMediaLibrary"
        @select="applyMediaLibrarySelection"
      />
    </div>
  </details>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import * as api from "../../../services/api.js";
import {
  normalizeFallbackImageList,
  resolveFallbackImagePool,
} from "../../../utils/fallbackImages.js";
import ImageTransformEditor from "../../ui/ImageTransformEditor.vue";
import MediaLibrary from "../../ui/MediaLibrary.vue";
import TransformedImage from "../../ui/TransformedImage.vue";

const props = defineProps({
  images: { type: Array, default: () => [] },
  mediaTag: { type: String, default: "" },
  legacyImageUrl: { type: String, default: "" },
  zoom: { type: Number, default: 1 },
  focalX: { type: Number, default: 50 },
  focalY: { type: Number, default: 50 },
  rotation: { type: Number, default: 0 },
  aspectRatio: { type: String, default: "1:1" },
  direction: { type: String, default: "landscape" },
  title: { type: String, default: "Fallback" },
  description: { type: String, default: "" },
  labels: { type: Object, default: () => ({}) },
  sourceContext: { type: String, default: "media.fallback.image" },
});

const emit = defineEmits([
  "apply-images",
  "clear-images",
  "update-transform",
]);

const defaultLabels = {
  mediaTag: "Media Tag",
  mediaTagPlaceholder: "-- Select a media tag --",
  mode: "Mode",
  replace: "Replace Fallbacks",
  append: "Append Fallbacks",
  refresh: "Refresh",
  loading: "Loading...",
  importButton: "Import Fallbacks from Media Tag",
  importing: "Importing...",
  selectFromLibrary: "Select",
  clear: "Clear",
  loadedSingular: "fallback image loaded.",
  loadedPlural: "fallback images loaded.",
};

const selectedMediaTag = ref("");
const importMode = ref("replace");
const mediaTagOptions = ref([]);
const loadingMediaTags = ref(false);
const importing = ref(false);
const showMediaPicker = ref(false);
const status = ref(null);

const mergedLabels = computed(() => ({
  ...defaultLabels,
  ...(props.labels && typeof props.labels === "object" ? props.labels : {}),
}));

const fallbackImagePool = computed(() =>
  resolveFallbackImagePool(props.images, props.legacyImageUrl)
);

const previewImageUrl = computed(() =>
  String(fallbackImagePool.value?.[0]?.imageUrl || "")
);

const loadedHint = computed(() => {
  const count = fallbackImagePool.value.length;
  const label = count === 1
    ? mergedLabels.value.loadedSingular
    : mergedLabels.value.loadedPlural;
  return `${count} ${label}`;
});

watch(
  () => props.mediaTag,
  (tag) => {
    const normalizedTag = String(tag || "").trim();
    if (selectedMediaTag.value === normalizedTag) return;
    selectedMediaTag.value = normalizedTag;
  },
  { immediate: true }
);

onMounted(() => {
  void loadMediaTags();
});

async function loadMediaTags() {
  loadingMediaTags.value = true;
  try {
    const response = await api.listAssetTags();
    mediaTagOptions.value = Array.isArray(response?.tags)
      ? response.tags.map((tag) => String(tag || "").trim()).filter(Boolean)
      : [];
  } catch (err) {
    console.error("Failed to load media tags:", err);
    mediaTagOptions.value = [];
  } finally {
    loadingMediaTags.value = false;
  }
}

async function listAllAssetsByTag(tag) {
  const cleanTag = String(tag || "").trim();
  if (!cleanTag) return [];
  const maxPages = 40;
  const pageSize = 100;
  let page = 1;
  let hasMore = true;
  const collected = [];

  while (hasMore && page <= maxPages) {
    const response = await api.listAssets({ page, pageSize, tag: cleanTag });
    const items = Array.isArray(response?.items) ? response.items : [];
    collected.push(...items);
    hasMore = Boolean(response?.has_more);
    page += 1;
  }

  return collected;
}

function clearFallbackImages() {
  emit("clear-images");
  status.value = null;
}

function openMediaLibrary() {
  showMediaPicker.value = true;
}

function closeMediaLibrary() {
  showMediaPicker.value = false;
}

function applyMediaLibrarySelection(selection) {
  const selectedFallbacks = normalizeFallbackImageList([
    {
      ...(selection && typeof selection === "object" ? selection : {}),
      id: `fallback-library-${Date.now()}`,
    },
  ]);

  if (selectedFallbacks.length === 0) {
    status.value = {
      type: "error",
      message: "Selected media item does not have a usable image URL.",
    };
    showMediaPicker.value = false;
    return;
  }

  const seedFallbacks = importMode.value === "append"
    ? fallbackImagePool.value
    : [];
  const nextFallbacks = normalizeFallbackImageList([...seedFallbacks, ...selectedFallbacks]);
  const nextMediaTag = importMode.value === "append"
    ? String(props.mediaTag || "").trim() || null
    : null;

  emit("apply-images", {
    images: nextFallbacks,
    mediaTag: nextMediaTag,
  });

  status.value = {
    type: "success",
    message: importMode.value === "append"
      ? "Added selected media item to fallback images."
      : "Replaced fallback images with selected media item.",
  };
  showMediaPicker.value = false;
}

async function importFallbacksFromMediaTag() {
  if (!selectedMediaTag.value) return;

  importing.value = true;
  status.value = null;
  try {
    const assets = await listAllAssetsByTag(selectedMediaTag.value);
    const importedFallbacks = normalizeFallbackImageList(
      assets.map((asset, index) => ({
        ...asset,
        id: `fallback-tag-${Date.now()}-${index}`,
      }))
    );

    if (importedFallbacks.length === 0) {
      status.value = {
        type: "error",
        message: "No media assets with usable URLs found for this tag.",
      };
      return;
    }

    const seedFallbacks = importMode.value === "append"
      ? fallbackImagePool.value
      : [];
    const nextFallbacks = normalizeFallbackImageList([...seedFallbacks, ...importedFallbacks]);
    const normalizedTag = String(selectedMediaTag.value || "").trim();

    emit("apply-images", {
      images: nextFallbacks,
      mediaTag: normalizedTag || null,
    });

    status.value = {
      type: "success",
      message: importMode.value === "append"
        ? `Imported ${importedFallbacks.length} fallback images from media tag "${normalizedTag}".`
        : `Replaced fallback images with ${nextFallbacks.length} items from media tag "${normalizedTag}".`,
    };
  } catch (err) {
    console.error("Failed to import fallback images from media tag:", err);
    status.value = {
      type: "error",
      message: err?.message || "Failed to import fallback images from media tag.",
    };
  } finally {
    importing.value = false;
  }
}
</script>

<style scoped>
.fallback-selector {
  border: 1px solid #0001;
  border-radius: 8px;
  background: transparent;
}

.fallback-selector-title {
  font-weight: 600;
  color: #374151;
  cursor: pointer;
  padding: 0.75rem;
  background: white;
  border-radius: 8px;
  list-style: none;
}

.fallback-selector-title::-webkit-details-marker {
  display: none;
}

.fallback-selector-title::before {
  content: "▸ ";
  color: #9ca3af;
}

.fallback-selector[open] .fallback-selector-title::before {
  content: "▾ ";
}

.fallback-selector-content {
  display: grid;
  gap: 10px;
  padding: 1rem;
  background: white;
  border-radius: 0 0 8px 8px;
  margin-top: -4px;
}

.field-hint {
  margin: 0;
  color: var(--muted, #64748b);
  font-size: 12px;
  line-height: 1.45;
}

.field-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted, #64748b);
}

.import-controls-row {
  display: flex;
  gap: 8px;
  align-items: end;
  flex-wrap: wrap;
}

.import-field {
  display: grid;
  gap: 4px;
  min-width: 260px;
  flex: 1;
}

.import-field--compact {
  min-width: 180px;
  max-width: 220px;
}

.integration-select {
  border-radius: 8px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.2));
  background: #fff;
  padding: 7px 10px;
}

.import-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.import-status {
  font-size: 12px;
  font-weight: 600;
}

.import-status.success {
  color: #166534;
}

.import-status.error {
  color: #b91c1c;
}

.fallback-preview-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
}

.fallback-preview-item {
  border: 1px solid var(--border, rgba(43, 12, 92, 0.2));
  border-radius: 8px;
  overflow: hidden;
  aspect-ratio: 1 / 1;
  background: rgba(255, 255, 255, 0.82);
}

.fallback-preview-image {
  width: 100%;
  height: 100%;
}
</style>
