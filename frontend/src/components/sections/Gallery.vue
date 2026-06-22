<template>
  <SectionBase :section-key="effectiveKey" :section-data="section">
    <div>
      <div v-if="displayImages.length && currentLayout === 'grid'" class="gallery-grid">
        <div
          v-for="(img, i) in displayImages"
          :key="img.id || i"
          class="gallery-item"
          @click="openLightbox(i)"
        >
          <TransformedImage
            class="gallery-item__image"
            :src="img.imageUrl"
            :alt="localizedText(img.alt)"
            :ratio="currentRatio"
            :direction="currentDirection"
            :zoom="img.zoom"
            :focal-x="img.focalX"
            :focal-y="img.focalY"
            :rotation="img.rotation"
            :responsive-variants="img.responsiveVariants"
            fit="cover"
            loading="lazy"
            decoding="async"
          />
          <div v-if="formatAuthorOverlay(img.imageAuthor)" class="gallery-author-overlay">
            {{ formatAuthorOverlay(img.imageAuthor) }}
          </div>
          <div v-if="showCaptions && localizedText(img.caption)" class="gallery-caption">{{ localizedText(img.caption) }}</div>
        </div>
      </div>

      <div v-if="displayImages.length && currentLayout === 'masonry'" class="gallery-masonry">
        <div
          v-for="(img, i) in displayImages"
          :key="img.id || i"
          class="masonry-item"
          @click="openLightbox(i)"
        >
          <TransformedImage
            class="gallery-item__image"
            :src="img.imageUrl"
            :alt="localizedText(img.alt)"
            :ratio="currentRatio"
            :direction="currentDirection"
            :zoom="img.zoom"
            :focal-x="img.focalX"
            :focal-y="img.focalY"
            :rotation="img.rotation"
            :responsive-variants="img.responsiveVariants"
            fit="cover"
            loading="lazy"
            decoding="async"
          />
          <div v-if="formatAuthorOverlay(img.imageAuthor)" class="gallery-author-overlay">
            {{ formatAuthorOverlay(img.imageAuthor) }}
          </div>
          <div v-if="showCaptions && localizedText(img.caption)" class="gallery-caption">{{ localizedText(img.caption) }}</div>
        </div>
      </div>

      <div v-if="displayImages.length && currentLayout === 'carousel'" class="carousel-wrap">
        <div ref="carouselRef" class="carousel-track" @scroll="onCarouselScroll">
          <div
            v-for="(img, i) in displayImages"
            :key="img.id || i"
            class="carousel-slide"
            @click="openLightbox(i)"
          >
            <TransformedImage
              class="gallery-item__image"
              :src="img.imageUrl"
              :alt="localizedText(img.alt)"
              :ratio="currentRatio"
              :direction="currentDirection"
              :zoom="img.zoom"
              :focal-x="img.focalX"
              :focal-y="img.focalY"
              :rotation="img.rotation"
              :responsive-variants="img.responsiveVariants"
              fit="cover"
              loading="lazy"
              decoding="async"
            />
            <div v-if="formatAuthorOverlay(img.imageAuthor)" class="gallery-author-overlay">
              {{ formatAuthorOverlay(img.imageAuthor) }}
            </div>
            <div v-if="showCaptions && localizedText(img.caption)" class="carousel-caption">{{ localizedText(img.caption) }}</div>
          </div>
        </div>
        <div v-if="displayImages.length > 1" class="carousel-dots">
          <span
            v-for="(_, i) in displayImages"
            :key="i"
            class="carousel-dot"
            :class="{ active: i === activeSlide }"
            @click="scrollToSlide(i)"
          ></span>
        </div>
      </div>

      <div v-if="displayImages.length === 0 && state.isAdmin" class="display--empty">
        <span class="empty-hint">+ Add Images</span>
      </div>
      <p v-else-if="displayImages.length === 0" class="p" style="margin-top: 10px;">
        No images yet.
      </p>

      <Teleport to="body">
        <div v-if="lightboxOpen" class="lightbox" @click.self="closeLightbox">
          <button class="lightbox-close" @click="closeLightbox">&#10005;</button>
          <button
            v-if="displayImages.length > 1"
            type="button"
            class="lightbox-nav lightbox-prev"
            aria-label="Previous image"
            @click.stop="lightboxNav(-1)"
          >
            <font-awesome-icon :icon="faChevronLeft" aria-hidden="true" />
          </button>
          <div
            class="lightbox-content"
            @pointerdown="onLightboxPointerStart"
            @pointerup="onLightboxPointerEnd"
            @pointercancel="onLightboxPointerCancel"
            @pointerleave="onLightboxPointerCancel"
          >
            <img
              :src="displayImages[lightboxIndex]?.imageUrl"
              :alt="localizedText(displayImages[lightboxIndex]?.alt)"
              decoding="async"
            />
            <div v-if="formatAuthorOverlay(displayImages[lightboxIndex]?.imageAuthor)" class="gallery-author-overlay gallery-author-overlay--lightbox">
              {{ formatAuthorOverlay(displayImages[lightboxIndex]?.imageAuthor) }}
            </div>
            <div v-if="showCaptions && localizedText(displayImages[lightboxIndex]?.caption)" class="lightbox-caption">
              {{ localizedText(displayImages[lightboxIndex]?.caption) }}
            </div>
          </div>
          <button
            v-if="displayImages.length > 1"
            type="button"
            class="lightbox-nav lightbox-next"
            aria-label="Next image"
            @click.stop="lightboxNav(1)"
          >
            <font-awesome-icon :icon="faChevronRight" aria-hidden="true" />
          </button>
        </div>
      </Teleport>

      <MediaLibrary
        :is-open="showMediaPicker"
        :current-url="''"
        source-context="section.gallery.image"
        @close="closeMediaPicker"
        @select="onMediaSelect"
      />
    </div>

    <template #admin-design-params>
      <div class="editor-controls">
        <label class="ctrl-field">
          <span class="field-label">Layout</span>
          <select
            :value="currentLayout"
            class="field ctrl-select"
            :disabled="isGallerySectionFieldLocked('layout')"
            :title="isGallerySectionFieldLocked('layout') ? integrationLockedHint : undefined"
            @change="setLayout($event.target.value)"
          >
            <option value="grid">Grid</option>
            <option value="carousel">Carousel</option>
            <option value="masonry">Masonry</option>
          </select>
        </label>

        <label class="ctrl-field">
          <span class="field-label">Ratio</span>
          <select
            :value="currentRatio"
            class="field ctrl-select"
            :disabled="isGallerySectionFieldLocked('aspectRatio')"
            :title="isGallerySectionFieldLocked('aspectRatio') ? integrationLockedHint : undefined"
            @change="setRatio($event.target.value)"
          >
            <option value="1:1">1:1 Square</option>
            <option value="3:2">3:2</option>
            <option value="4:3">4:3</option>
            <option value="16:9">16:9</option>
          </select>
        </label>

        <label class="ctrl-field">
          <span class="field-label">Direction</span>
          <select
            :value="currentDirection"
            class="field ctrl-select"
            :disabled="isGallerySectionFieldLocked('direction')"
            :title="isGallerySectionFieldLocked('direction') ? integrationLockedHint : undefined"
            @change="setDirection($event.target.value)"
          >
            <option value="landscape">Landscape</option>
            <option value="portrait">Portrait</option>
          </select>
        </label>

        <label class="caption-toggle">
          <input
            type="checkbox"
            :checked="showCaptions"
            :disabled="isGallerySectionFieldLocked('showCaptions')"
            @change="setShowCaptions($event.target.checked)"
          />
          <span>Show caption text overlay</span>
        </label>
      </div>
    </template>

    <template #admin-content>
      <div v-if="editing" class="editor">
        <details v-if="state.canAdminGeneral" class="media-tag-import-panel">
          <summary class="media-tag-import-title">Import Images by Media Tag</summary>
          <div class="media-tag-import-content">
            <div class="import-controls-row">
              <div class="import-field">
                <label class="field-label">Media Tag</label>
                <select v-model="selectedMediaTag" class="integration-select">
                  <option value="">-- Select a media tag --</option>
                  <option v-for="tag in mediaTagOptions" :key="`gallery-tag-${tag}`" :value="tag">
                    {{ tag }}
                  </option>
                </select>
              </div>
              <div class="import-field import-field--compact">
                <label class="field-label">Mode</label>
                <select v-model="mediaTagImportMode" class="integration-select">
                  <option value="replace">Replace Images</option>
                  <option value="append">Append Images</option>
                </select>
              </div>
              <button
                type="button"
                class="btn-secondary small"
                @click="loadMediaTags"
                :disabled="loadingMediaTags"
              >
                {{ loadingMediaTags ? "Loading..." : "Refresh" }}
              </button>
            </div>
            <div class="import-actions">
              <button
                class="btn"
                type="button"
                @click="importImagesFromMediaTag"
                :disabled="!selectedMediaTag || importingFromMediaTag"
              >
                {{ importingFromMediaTag ? "Importing..." : "Import from Media Tag" }}
              </button>
              <span v-if="mediaTagImportStatus" class="import-status" :class="mediaTagImportStatus.type">
                {{ mediaTagImportStatus.message }}
              </span>
            </div>
          </div>
        </details>

        <details v-if="showDynamicMediaTagPanel" class="media-tag-import-panel">
          <summary class="media-tag-import-title">Dynamic Media Tags</summary>
          <div class="media-tag-import-content">
            <div v-if="dynamicTagContextError" class="import-status error">
              {{ dynamicTagContextError }}
            </div>
            <div v-else-if="loadingDynamicTagContext" class="import-status">
              Loading fields...
            </div>
            <div v-else-if="!selectedPageMappingIntegrationId" class="import-status error">
              Select an item-page mapping integration first.
            </div>
            <div v-for="(binding, index) in mediaTagBindings" :key="binding.id || index" class="dynamic-tag-binding-row">
              <label class="dynamic-tag-binding-enabled">
                <input
                  type="checkbox"
                  :checked="binding.enabled"
                  @change="updateMediaTagBinding(index, { enabled: $event.target.checked })"
                />
                <span>Enabled</span>
              </label>
              <label class="import-field">
                <span class="field-label">Prefix</span>
                <select
                  class="integration-select"
                  :value="binding.prefix"
                  :disabled="dynamicTagPrefixOptions.length === 0"
                  @change="updateMediaTagBinding(index, { prefix: $event.target.value, prefixSourcePath: '' })"
                >
                  <option value="">Select media prefix</option>
                  <option
                    v-for="option in dynamicTagPrefixOptions"
                    :key="`dynamic-tag-prefix-${index}-${option.value}`"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </label>
              <label class="import-field">
                <span class="field-label">Value Field</span>
                <select
                  class="integration-select"
                  :value="binding.valueSourcePath"
                  :disabled="dynamicTagSourceOptions.length === 0"
                  @change="updateMediaTagBinding(index, { valueSourcePath: $event.target.value })"
                >
                  <option value="">Select integration field</option>
                  <option
                    v-for="option in dynamicTagSourceOptions"
                    :key="`dynamic-tag-value-${index}-${option.value}`"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </label>
              <span class="dynamic-tag-preview">
                {{ previewMediaTagForBinding(binding) || binding.resolvedTag || "No preview" }}
              </span>
              <button class="btn-secondary small" type="button" @click="removeMediaTagBinding(index)">
                Remove
              </button>
            </div>
            <div class="import-actions">
              <button class="btn-secondary small" type="button" @click="addMediaTagBinding">
                Add Tag Binding
              </button>
            </div>
          </div>
        </details>

        <SectionListEditor
          :items="draftImages"
          :selected-index="expandedItem"
          :add-label="t.add"
          :save-label="t.save"
          :remove-label="t.remove"
          clear-label="Clear All"
          :show-clear="true"
          @select="expandedItem = $event"
          @add="addImage"
          @save="saveGallery"
          @remove="removeImage"
          @clear="clearAllGalleryImages"
        >
          <template #item="{ item, index }">
            <div class="item-thumb item-thumb--media">
              <div
                class="thumb-img-wrap"
                :style="thumbRatioStyle"
                title="Click to browse images"
              >
                <TransformedImage
                  v-if="item.imageUrl"
                  :src="item.imageUrl"
                  alt=""
                  class="thumb-img"
                  :ratio="currentRatio"
                  :direction="currentDirection"
                  :zoom="item.zoom"
                  :focal-x="item.focalX"
                  :focal-y="item.focalY"
                  :rotation="item.rotation"
                  fit="cover"
                  loading="lazy"
                  decoding="async"
                />
                <div v-else class="thumb-empty">+</div>
              </div>
              <span class="thumb-label">{{ item.caption.de || item.alt.de || `#${index + 1}` }}</span>
            </div>
          </template>

          <template #editor="{ item, index }">
              <ImageTransformEditor
                :image-url="item.imageUrl"
                :zoom="item.zoom"
                :focal-x="item.focalX"
                :focal-y="item.focalY"
                :rotation="item.rotation"
                :ratio="currentRatio"
                :direction="currentDirection"
                view-context="section_item"
                :image-url-disabled="isGalleryImageFieldLocked(index, 'imageUrl')"
                :zoom-disabled="isGalleryImageFieldLocked(index, 'zoom')"
                :focal-disabled="isGalleryImageFieldLocked(index, 'focalX') || isGalleryImageFieldLocked(index, 'focalY')"
                :rotation-disabled="isGalleryImageFieldLocked(index, 'rotation')"
                @update:image-url="(value) => setDraftTransform(index, { imageUrl: value })"
                @update:zoom="(value) => setDraftTransform(index, { zoom: value })"
                @update:focal-x="(value) => setDraftTransform(index, { focalX: value })"
                @update:focal-y="(value) => setDraftTransform(index, { focalY: value })"
                @update:rotation="(value) => setDraftTransform(index, { rotation: value })"
                @choose-image="openMediaPicker(index, { direct: false })"
                @clear-image="setDraftTransform(index, { imageUrl: '', imageAuthor: '' })"
              />
              <div class="lang-section">
                <span class="lang-header">Caption</span>
                <span class="caption-sync-hint">Synced with the media library caption.</span>
                <div class="alt-row">
                  <input
                    :value="item.caption?.de || ''"
                    class="field"
                    type="text"
                    placeholder="Caption (DE)"
                    :disabled="isGalleryImageFieldLocked(index, 'caption.de')"
                    :title="isGalleryImageFieldLocked(index, 'caption.de') ? integrationLockedHint : undefined"
                    @input="setDraftCaption(index, 'de', $event.target.value)"
                  />
                  <input
                    :value="item.caption?.en || ''"
                    class="field"
                    type="text"
                    placeholder="Caption (EN)"
                    :disabled="isGalleryImageFieldLocked(index, 'caption.en')"
                    :title="isGalleryImageFieldLocked(index, 'caption.en') ? integrationLockedHint : undefined"
                    @input="setDraftCaption(index, 'en', $event.target.value)"
                  />
                </div>
              </div>
          </template>
        </SectionListEditor>
      </div>
    </template>
  </SectionBase>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { faChevronLeft, faChevronRight } from "@fortawesome/free-solid-svg-icons";
import { useStore } from "../../store/store.js";
import * as api from "../../services/api.js";
import { useListEditorMediaPicker } from "../../composables/useListEditorMediaPicker.js";
import { clamp, normalizeRatio, ratioToCss } from "../../utils/imageTransform.js";
import { convertKeysToCamel } from "../../utils/caseConversion.js";
import { buildIntegrationMappingKeys } from "../../utils/integrationMappingKeys.js";
import { buildMediaTag, normalizeMediaTagPart } from "../../utils/mediaTags.js";
import {
  resolveBackendResponsiveImagePayload,
} from "../../utils/responsiveImages.js";
import { resolveFallbackImageForIndex } from "../../utils/fallbackImages.js";
import { isSectionIntegrationFieldLocked } from "../../utils/sectionIntegrationFieldState.js";

import SectionBase from "./_BaseSection.vue";
import SectionListEditor from "../admin/section-editor/SectionListEditor.vue";
import MediaLibrary from "../ui/MediaLibrary.vue";
import ImageTransformEditor from "../ui/ImageTransformEditor.vue";
import TransformedImage from "../ui/TransformedImage.vue";

const props = defineProps({
  sectionKey: { type: String, default: "gallery" },
  sectionData: { type: Object, default: null },
});

const { state, t, localizedText, updateSection, saveSectionByKey } = useStore();
const integrationLockedHint = "Managed by integration import.";

const effectiveKey = computed(() => props.sectionKey);
const currentAdminTab = computed(() => state.sectionAdminActiveTabs?.[effectiveKey.value] || "");

const section = computed(() => {
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});

function galleryImageFieldPath(index, fieldPath) {
  const normalizedFieldPath = String(fieldPath || "").trim();
  const numericIndex = Number(index);
  const resolvedIndex = Number.isInteger(numericIndex) && numericIndex >= 0 ? numericIndex : 0;
  return normalizedFieldPath
    ? `images[${resolvedIndex}].${normalizedFieldPath}`
    : `images[${resolvedIndex}]`;
}

function isGallerySectionFieldLocked(path, options = {}) {
  return state.isAdmin && isSectionIntegrationFieldLocked(section.value, path, options);
}

function isGalleryImageFieldLocked(index, fieldPath, options = {}) {
  return state.isAdmin && isSectionIntegrationFieldLocked(section.value, galleryImageFieldPath(index, fieldPath), options);
}

function normalizeLayout(value) {
  return ["grid", "carousel", "masonry"].includes(value) ? value : "grid";
}

function normalizeDirection(value) {
  return value === "portrait" ? "portrait" : "landscape";
}

function normalizeShowCaptions(value) {
  return value === false ? false : true;
}

function normalizeBilingualValue(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return {
      de: String(value.de || ""),
      en: String(value.en || ""),
    };
  }
  return { de: "", en: "" };
}

function normalizeImageAuthor(value) {
  return String(value || "").trim();
}

function formatAuthorOverlay(value) {
  const author = normalizeImageAuthor(value);
  return author ? `© ${author}` : "";
}

function resolveSelectionImageAuthor(selection) {
  const source = selection && typeof selection === "object" ? convertKeysToCamel(selection) : {};
  const direct = normalizeImageAuthor(
    source.imageAuthor
    || source.author
  );
  if (direct) return direct;
  if (!Array.isArray(source.authors)) return "";
  return normalizeImageAuthor(source.authors.find((entry) => normalizeImageAuthor(entry)));
}

function normalizeImage(item = {}, fallbackId) {
  const source = item && typeof item === "object" ? convertKeysToCamel(item) : {};
  const zoomValue = source.zoom;
  const focalXValue = source.focalX;
  const focalYValue = source.focalY;
  const rotationValue = source.rotation;

  return {
    id: source.id || fallbackId,
    assetId: String(source.assetId || "").trim(),
    imageUrl: String(source.imageUrl || "").trim(),
    zoom: clamp(zoomValue, 1, 4, 1),
    focalX: clamp(focalXValue, 0, 100, 50),
    focalY: clamp(focalYValue, 0, 100, 50),
    rotation: clamp(rotationValue, -180, 180, 0),
    imageAuthor: normalizeImageAuthor(source.imageAuthor),
    alt: normalizeBilingualValue(source.alt),
    caption: normalizeBilingualValue(source.caption),
    responsiveVariants: Array.isArray(source.responsiveVariants)
      ? source.responsiveVariants
      : [],
  };
}

function normalizeIntegrationSourcePath(path) {
  const normalized = String(path || "").trim();
  if (!normalized) return "";
  if (normalized.startsWith("integration.")) return normalized;
  if (normalized.startsWith("item.")) return "";
  return `integration.${normalized}`;
}

function prefixFromResolvedMediaTag(tag) {
  const raw = String(tag || "").trim();
  const separatorIndex = raw.indexOf("::");
  return separatorIndex > 0 ? normalizeMediaTagPart(raw.slice(0, separatorIndex)) : "";
}

function normalizeMediaTagBinding(entry = {}, fallbackId = "") {
  const source = entry && typeof entry === "object" ? convertKeysToCamel(entry) : {};
  const resolvedTag = String(source.resolvedTag || "").trim();
  return {
    id: String(source.id || fallbackId || "").trim(),
    enabled: source.enabled !== false,
    prefix: normalizeMediaTagPart(source.prefix || source.prefixValue || prefixFromResolvedMediaTag(resolvedTag)),
    prefixSourcePath: normalizeIntegrationSourcePath(source.prefixSourcePath),
    valueSourcePath: normalizeIntegrationSourcePath(source.valueSourcePath),
    resolvedTag,
  };
}

function normalizeMediaTagBindings(items) {
  const source = Array.isArray(items) ? items : [];
  return source
    .map((entry, index) => normalizeMediaTagBinding(entry, `media-tag-binding-${index + 1}`));
}

function toPersistedMediaTagBindings(items) {
  return normalizeMediaTagBindings(items).map((entry) => ({
    id: entry.id,
    enabled: entry.enabled,
    prefix: entry.prefix,
    prefixSourcePath: entry.prefix ? "" : entry.prefixSourcePath,
    valueSourcePath: entry.valueSourcePath,
    resolvedTag: entry.resolvedTag,
  }));
}

function normalizeGalleryDraftImages(items) {
  const source = Array.isArray(items) ? items : [];
  return source.map((img, index) => normalizeImage(img, img?.id || `gallery-${index + 1}`));
}

function toPersistedGalleryImages(items) {
  return normalizeGalleryDraftImages(items);
}

function isGalleryDraftInSyncWithSection() {
  return JSON.stringify(toPersistedGalleryImages(section.value?.images))
    === JSON.stringify(toPersistedGalleryImages(draftImages.value));
}

function galleryImageDedupeKey(image) {
  const assetId = String(image?.assetId || "").trim();
  if (assetId) return `asset:${assetId}`;
  const imageUrl = String(image?.imageUrl || "").trim();
  return imageUrl ? `url:${imageUrl}` : "";
}

function mergeGalleryImages(images) {
  const seen = new Set();
  const merged = [];
  images.forEach((image, index) => {
    const normalized = normalizeImage(image, image?.id || `gallery-${index + 1}`);
    const key = galleryImageDedupeKey(normalized);
    if (key && seen.has(key)) return;
    if (key) seen.add(key);
    merged.push(normalized);
  });
  return merged;
}

const dynamicMediaTagImagesByTag = ref({});
const dynamicMediaTagLoading = ref(false);

const staticDisplayImages = computed(() =>
  normalizeGalleryDraftImages(section.value?.images)
);

const mediaTagBindings = computed(() =>
  normalizeMediaTagBindings(section.value?.mediaTagBindings)
);

const resolvedDynamicMediaTags = computed(() => {
  const seen = new Set();
  return mediaTagBindings.value
    .filter((entry) => entry.enabled && entry.resolvedTag)
    .map((entry) => entry.resolvedTag)
    .filter((tag) => {
      if (seen.has(tag)) return false;
      seen.add(tag);
      return true;
    });
});

const dynamicDisplayImages = computed(() => {
  const images = [];
  const imagesByTag = dynamicMediaTagImagesByTag.value || {};
  resolvedDynamicMediaTags.value.forEach((tag) => {
    const tagImages = Array.isArray(imagesByTag[tag]) ? imagesByTag[tag] : [];
    images.push(...tagImages);
  });
  return images;
});

function resolveGalleryImageForDisplay(image, index = 0) {
  const normalized = normalizeImage(image, image?.id || `gallery-${index + 1}`);
  if (String(normalized.imageUrl || "").trim()) return normalized;
  const fallback = resolveFallbackImageForIndex(state.mediaFallbacks, index);
  if (!fallback?.imageUrl) return normalized;
  return {
    ...normalized,
    imageUrl: fallback.imageUrl,
    responsiveVariants: Array.isArray(fallback.responsiveVariants) ? fallback.responsiveVariants : [],
    zoom: fallback.zoom,
    focalX: fallback.focalX,
    focalY: fallback.focalY,
    rotation: fallback.rotation,
  };
}

const displayImages = computed(() =>
  mergeGalleryImages([
    ...staticDisplayImages.value
      .filter((image) => String(image.imageUrl || "").trim())
      .map((image, index) => resolveGalleryImageForDisplay(image, index)),
    ...dynamicDisplayImages.value,
  ]).filter((image) => String(image.imageUrl || "").trim())
);

const currentLayout = computed(() => normalizeLayout(section.value?.layout));
const currentRatio = computed(() => normalizeRatio(section.value?.aspectRatio || "4:3", "4:3"));
const currentDirection = computed(() =>
  normalizeDirection(section.value?.direction || "landscape")
);
const showCaptions = computed(() => normalizeShowCaptions(section.value?.showCaptions));

const thumbRatioStyle = computed(() => ({
  aspectRatio: ratioToCss(currentRatio.value, currentDirection.value),
  width: "80px",
  height: "auto",
}));

const editing = ref(false);
const expandedItem = ref(-1);
const draftImages = ref([]);
const mediaTagOptions = ref([]);
const loadingMediaTags = ref(false);
const selectedMediaTag = ref("");
const mediaTagImportMode = ref("replace");
const importingFromMediaTag = ref(false);
const mediaTagImportStatus = ref(null);
const templateBuilderContext = ref(api.getTemplateBuilderContext?.() || null);
const dynamicTagTemplateInfo = ref(null);
const dynamicTagIntegrationPreview = ref(null);
const dynamicTagMediaConfig = ref(null);
const loadingDynamicTagContext = ref(false);
const dynamicTagContextError = ref("");
const {
  showMediaPicker,
  openMediaPicker,
  closeMediaPicker,
  consumeMediaPickerSelectionContext,
} = useListEditorMediaPicker();

const carouselRef = ref(null);
const activeSlide = ref(0);

const lightboxOpen = ref(false);
const lightboxIndex = ref(0);
const lightboxPointerStartX = ref(null);
const lightboxPointerStartY = ref(null);
const LIGHTBOX_SWIPE_THRESHOLD = 40;
const ASSET_CAPTION_SYNC_DEBOUNCE_MS = 450;
const assetCaptionSyncTimers = new Map();
let dynamicMediaTagRequestId = 0;

const isPageTemplateBuilder = computed(() =>
  String(templateBuilderContext.value?.kind || "").trim().toLowerCase() === "page"
);
const isItemPageTemplateBuilder = computed(() => {
  if (!isPageTemplateBuilder.value) return false;
  const template = dynamicTagTemplateInfo.value;
  const templateKind = String(template?.template_kind || "").trim().toLowerCase();
  const sourceType = String(template?.source_type || "").trim();
  return templateKind === "item_page" || Boolean(sourceType);
});
const selectedPageMappingIntegrationId = computed(() =>
  String(dynamicTagTemplateInfo.value?.page_integration_mapping?.selected_integration_id || "").trim()
);
const showDynamicMediaTagPanel = computed(() =>
  Boolean(
    state.canAdminGeneral
    && isPageTemplateBuilder.value
    && (
      isItemPageTemplateBuilder.value
      || loadingDynamicTagContext.value
      || dynamicTagContextError.value
    )
  )
);
const dynamicTagPrefixOptions = computed(() => {
  const optionsByValue = new Map();
  collectMediaTagPrefixOptions(dynamicTagMediaConfig.value).forEach((option) => {
    if (!option.value || optionsByValue.has(option.value)) return;
    optionsByValue.set(option.value, option);
  });
  mediaTagOptions.value.forEach((tag) => {
    const prefix = prefixFromResolvedMediaTag(tag);
    if (!prefix || optionsByValue.has(prefix)) return;
    optionsByValue.set(prefix, {
      value: prefix,
      label: `${prefix} [Media tag]`,
    });
  });
  mediaTagBindings.value.forEach((binding) => {
    const prefix = normalizeMediaTagPart(binding.prefix);
    if (!prefix || optionsByValue.has(prefix)) return;
    optionsByValue.set(prefix, {
      value: prefix,
      label: `${prefix} [Unavailable]`,
    });
  });
  return Array.from(optionsByValue.values()).sort((a, b) => a.label.localeCompare(b.label));
});
const dynamicTagSourceOptions = computed(() => {
  const optionsByValue = new Map();
  buildIntegrationMappingKeys(dynamicTagIntegrationPreview.value, { leafOnly: true })
    .forEach((path) => {
      const value = `integration.${path}`;
      optionsByValue.set(value, {
        value,
        label: formatIntegrationSourcePathLabel(path),
      });
    });
  mediaTagBindings.value.forEach((binding) => {
    [binding.valueSourcePath].forEach((sourcePath) => {
      const value = normalizeIntegrationSourcePath(sourcePath);
      if (!value || optionsByValue.has(value)) return;
      optionsByValue.set(value, {
        value,
        label: `${formatIntegrationSourcePathLabel(value.slice(12))} [Unavailable]`,
      });
    });
  });
  return Array.from(optionsByValue.values()).sort((a, b) => a.label.localeCompare(b.label));
});

watch(
  () => state.isAdmin,
  (val) => {
    if (!val) {
      // Keep draft values until unmount autosave has completed; clearing here
      // can race with SectionListEditor autosave and persist an empty list.
      editing.value = false;
      return;
    }
    if (currentAdminTab.value === "content") {
      startEdit();
      if (state.canAdminGeneral) loadMediaTags();
      loadDynamicTagContext();
    }
  }
);

watch(
  currentAdminTab,
  (tab) => {
    if (!state.isAdmin) return;
    if (tab === "content") {
      startEdit();
      if (state.canAdminGeneral) loadMediaTags();
      loadDynamicTagContext();
    }
    else editing.value = false;
  },
  { immediate: true }
);

watch(
  () => JSON.stringify(section.value?.images || []),
  () => {
    if (!state.isAdmin) return;
    if (currentAdminTab.value !== "content") return;
    if (isGalleryDraftInSyncWithSection()) return;
    const prevExpanded = expandedItem.value;
    startEdit();
    if (prevExpanded >= 0 && prevExpanded < draftImages.value.length) {
      expandedItem.value = prevExpanded;
    }
  }
);

watch(
  () => resolvedDynamicMediaTags.value.join("\n"),
  () => {
    loadDynamicMediaTagImages();
  },
  { immediate: true }
);

function formatIntegrationSourcePathLabel(path) {
  return String(path || "")
    .split(".")
    .map((part) => part.replace(/[_-]+/g, " "))
    .filter(Boolean)
    .join(" / ");
}

function formatMediaPrefixPathLabel(path) {
  return String(path || "")
    .split(".")
    .map((part) => part.replace(/[_-]+/g, " "))
    .filter(Boolean)
    .join(" / ");
}

function collectMediaTagPrefixOptions(config) {
  const options = [];
  const seen = new Set();
  const addOption = (rawPrefix, rawLabel) => {
    const prefix = normalizeMediaTagPart(rawPrefix);
    if (!prefix || seen.has(prefix)) return;
    seen.add(prefix);
    options.push({
      value: prefix,
      label: rawLabel ? `${rawLabel}: ${prefix}` : prefix,
    });
  };
  const visit = (node, path = "") => {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) {
      if (path.endsWith("custom_tags")) {
        node.forEach((tag) => {
          const prefix = prefixFromResolvedMediaTag(tag);
          if (prefix) addOption(prefix, "Custom tag");
        });
      }
      return;
    }
    Object.entries(node).forEach(([key, value]) => {
      const nextPath = path ? `${path}.${key}` : key;
      if (
        typeof value === "string"
        && (key === "source_tag_prefix" || key.endsWith("_tag_prefix"))
      ) {
        addOption(value, formatMediaPrefixPathLabel(nextPath));
        return;
      }
      visit(value, nextPath);
    });
  };
  visit(config);
  return options;
}

function deepGetPath(source, path) {
  const parts = String(path || "")
    .split(".")
    .map((part) => part.trim())
    .filter(Boolean);
  if (!parts.length || !source || typeof source !== "object") return undefined;
  let current = source;
  for (const part of parts) {
    if (!current || typeof current !== "object" || !(part in current)) return undefined;
    current = current[part];
  }
  return current;
}

function stripIntegrationSourcePrefix(path) {
  const normalized = normalizeIntegrationSourcePath(path);
  return normalized.startsWith("integration.") ? normalized.slice(12) : "";
}

function resolveDynamicTagPreviewValue(sourcePath) {
  const path = stripIntegrationSourcePrefix(sourcePath);
  if (!path) return undefined;
  return deepGetPath(dynamicTagIntegrationPreview.value?.preview_item, path);
}

function previewMediaTagForBinding(binding) {
  if (binding?.resolvedTag) return binding.resolvedTag;
  return buildMediaTag(
    binding?.prefix || resolveDynamicTagPreviewValue(binding?.prefixSourcePath),
    resolveDynamicTagPreviewValue(binding?.valueSourcePath),
  );
}

function saveMediaTagBindings(nextBindings) {
  updateSection(
    effectiveKey.value,
    { mediaTagBindings: toPersistedMediaTagBindings(nextBindings) },
    { revisionKind: "content" },
  );
}

function addMediaTagBinding() {
  saveMediaTagBindings([
    ...mediaTagBindings.value,
    {
      id: `media-tag-binding-${Date.now()}`,
      enabled: true,
      prefix: "",
      prefixSourcePath: "",
      valueSourcePath: "",
      resolvedTag: "",
    },
  ]);
}

function updateMediaTagBinding(index, patch) {
  if (index < 0 || index >= mediaTagBindings.value.length) return;
  const next = mediaTagBindings.value.map((entry, entryIndex) => {
    if (entryIndex !== index) return entry;
    return normalizeMediaTagBinding(
      {
        ...entry,
        ...patch,
        resolvedTag: "",
      },
      entry.id || `media-tag-binding-${entryIndex + 1}`,
    );
  });
  saveMediaTagBindings(next);
}

function removeMediaTagBinding(index) {
  if (index < 0 || index >= mediaTagBindings.value.length) return;
  saveMediaTagBindings(mediaTagBindings.value.filter((_, entryIndex) => entryIndex !== index));
}

function mapAssetToGalleryImage(asset, fallbackId) {
  const media = resolveBackendResponsiveImagePayload(asset, {
    urlKeys: ["url", "src", "href"],
  });
  const url = String(media.url || "").trim();
  if (!url) return null;
  const filename = String(asset?.filename || "").trim();
  const alt = normalizeBilingualValue(asset?.alt);
  const caption = normalizeBilingualValue(asset?.caption);
  return normalizeImage(
    {
      id: fallbackId,
      assetId: String(asset?.id || "").trim(),
      imageUrl: url,
      responsiveVariants: media.responsiveVariants,
      zoom: 1,
      focalX: 50,
      focalY: 50,
      rotation: 0,
      imageAuthor: resolveSelectionImageAuthor(asset),
      alt: {
        de: alt.de || filename,
        en: alt.en || filename,
      },
      caption,
      responsiveVariants: media.responsiveVariants,
    },
    fallbackId,
  );
}

async function loadDynamicTagContext() {
  templateBuilderContext.value = api.getTemplateBuilderContext?.() || null;
  if (!isPageTemplateBuilder.value || loadingDynamicTagContext.value) return;
  loadingDynamicTagContext.value = true;
  dynamicTagContextError.value = "";
  try {
    const templatePath = String(templateBuilderContext.value?.path || "").trim();
    if (!templatePath) {
      dynamicTagTemplateInfo.value = null;
      dynamicTagIntegrationPreview.value = null;
      dynamicTagMediaConfig.value = null;
      return;
    }
    const [template, mediaConfig] = await Promise.all([
      api.getPageTemplate(templatePath),
      api.getAdminMediaConfig(),
    ]);
    dynamicTagTemplateInfo.value = template || null;
    dynamicTagMediaConfig.value = mediaConfig || null;
    const integrationId = String(template?.page_integration_mapping?.selected_integration_id || "").trim();
    dynamicTagIntegrationPreview.value = integrationId
      ? await api.getIntegrationDataPreview(integrationId)
      : null;
  } catch (error) {
    console.error("Failed to load dynamic media tag context:", error);
    dynamicTagTemplateInfo.value = null;
    dynamicTagIntegrationPreview.value = null;
    dynamicTagMediaConfig.value = null;
    dynamicTagContextError.value = error?.message || "Failed to load dynamic media tag fields.";
  } finally {
    loadingDynamicTagContext.value = false;
  }
}

async function loadDynamicMediaTagImages() {
  const tags = resolvedDynamicMediaTags.value;
  const requestId = dynamicMediaTagRequestId + 1;
  dynamicMediaTagRequestId = requestId;
  if (!tags.length) {
    dynamicMediaTagImagesByTag.value = {};
    dynamicMediaTagLoading.value = false;
    return;
  }

  dynamicMediaTagLoading.value = true;
  try {
    const entries = await Promise.all(
      tags.map(async (tag) => {
        const assets = await api.listPublicAssetsByTag(tag);
        return [
          tag,
          assets
            .map((asset, index) => mapAssetToGalleryImage(asset, `gallery-dynamic-${tag}-${index + 1}`))
            .filter(Boolean),
        ];
      }),
    );
    if (dynamicMediaTagRequestId !== requestId) return;
    dynamicMediaTagImagesByTag.value = Object.fromEntries(entries);
  } catch (error) {
    if (dynamicMediaTagRequestId !== requestId) return;
    console.error("Failed to load dynamic gallery media tag images:", error);
    dynamicMediaTagImagesByTag.value = {};
  } finally {
    if (dynamicMediaTagRequestId === requestId) {
      dynamicMediaTagLoading.value = false;
    }
  }
}

function setLayout(value) {
  if (isGallerySectionFieldLocked("layout")) return;
  updateSection(effectiveKey.value, { layout: normalizeLayout(value) }, { revisionKind: "design" });
}

function setRatio(value) {
  if (isGallerySectionFieldLocked("aspectRatio")) return;
  updateSection(effectiveKey.value, { aspectRatio: normalizeRatio(value, "4:3") }, { revisionKind: "design" });
}

function setDirection(value) {
  if (isGallerySectionFieldLocked("direction")) return;
  const direction = normalizeDirection(value);
  updateSection(
    effectiveKey.value,
    { orientation: direction, direction },
    { revisionKind: "design" }
  );
}

function setShowCaptions(value) {
  if (isGallerySectionFieldLocked("showCaptions")) return;
  updateSection(
    effectiveKey.value,
    { showCaptions: value === true },
    { revisionKind: "content" }
  );
}

function startEdit() {
  expandedItem.value = -1;
  draftImages.value = normalizeGalleryDraftImages(section.value?.images);
  editing.value = true;
}

function addImage() {
  draftImages.value.push(
    normalizeImage(
      {
        id: String(Date.now() + Math.random()),
        assetId: "",
        imageUrl: "",
        zoom: 1,
        focalX: 50,
        focalY: 50,
        rotation: 0,
        imageAuthor: "",
        alt: { de: "", en: "" },
        caption: { de: "", en: "" },
      },
      `gallery-${draftImages.value.length + 1}`
    )
  );
  expandedItem.value = draftImages.value.length - 1;
  saveGallery({ flush: true });
}

function removeImage(index) {
  if (index < 0 || index >= draftImages.value.length) return;
  draftImages.value.splice(index, 1);
  if (expandedItem.value === index) {
    expandedItem.value = draftImages.value.length ? Math.min(index, draftImages.value.length - 1) : -1;
  } else if (expandedItem.value > index) {
    expandedItem.value -= 1;
  }
}

function onMediaSelect(selection) {
  const { index, direct } = consumeMediaPickerSelectionContext();
  if (index >= 0 && index < draftImages.value.length) {
    if (isGalleryImageFieldLocked(index, "imageUrl")) {
      closeMediaPicker();
      return;
    }
    const media = resolveBackendResponsiveImagePayload(selection, {
      urlKeys: ["url", "src", "href"],
    });
    const current = draftImages.value[index];
    const normalizedSelectionAlt = normalizeBilingualValue(selection?.alt);
    const normalizedSelectionCaption = normalizeBilingualValue(selection?.caption);
    const filenameFallback = String(selection?.filename || "").trim();
    const resolvedAlt = {
      de: normalizedSelectionAlt.de || filenameFallback,
      en: normalizedSelectionAlt.en || filenameFallback,
    };
    const resolvedCaption = {
      de: normalizedSelectionCaption.de,
      en: normalizedSelectionCaption.en,
    };
    const resolvedAuthor = resolveSelectionImageAuthor(selection);
    draftImages.value[index] = normalizeImage({
      ...current,
      assetId: String(selection?.id || current.assetId || "").trim(),
      imageUrl: media.url || "",
      imageAuthor: resolvedAuthor,
      alt: resolvedAlt,
      caption: resolvedCaption,
      responsiveVariants: media.responsiveVariants,
    }, current.id || `gallery-${index + 1}`);
    syncDraftCaptionByMediaKey(index, resolvedCaption);
    if (direct) saveGallery();
  }
  closeMediaPicker();
}

function setDraftTransform(index, patch) {
  if (index < 0 || index >= draftImages.value.length) return;
  const item = draftImages.value[index];
  const nextPatch = { ...patch };
  Object.keys(nextPatch).forEach((key) => {
    if (isGalleryImageFieldLocked(index, key)) {
      delete nextPatch[key];
    }
  });
  if (!Object.keys(nextPatch).length) return;
  if (Object.prototype.hasOwnProperty.call(nextPatch, "imageUrl")) {
    const nextUrl = String(nextPatch.imageUrl || "").trim();
    const currentUrl = String(item.imageUrl || "").trim();
    if (nextUrl !== currentUrl && !Object.prototype.hasOwnProperty.call(nextPatch, "imageAuthor")) {
      nextPatch.imageAuthor = "";
    }
  }
  draftImages.value[index] = normalizeImage({ ...item, ...nextPatch }, item.id || `gallery-${index + 1}`);
}

function resolveDraftMediaSyncKey(item) {
  const assetId = String(item?.assetId || "").trim();
  if (assetId) return `asset:${assetId}`;
  const imageUrl = String(item?.imageUrl || "").trim();
  if (!imageUrl) return "";
  return `url:${imageUrl}`;
}

function scheduleAssetCaptionSync(assetId, caption) {
  const normalizedAssetId = String(assetId || "").trim();
  if (!normalizedAssetId) return;
  const nextCaption = normalizeBilingualValue(caption);
  const existing = assetCaptionSyncTimers.get(normalizedAssetId);
  if (existing) clearTimeout(existing);
  const timer = setTimeout(async () => {
    assetCaptionSyncTimers.delete(normalizedAssetId);
    try {
      await api.updateAssetText(normalizedAssetId, { caption: nextCaption });
    } catch (error) {
      console.error("Failed to sync gallery caption to media asset:", error);
    }
  }, ASSET_CAPTION_SYNC_DEBOUNCE_MS);
  assetCaptionSyncTimers.set(normalizedAssetId, timer);
}

function syncDraftCaptionByMediaKey(index, caption) {
  if (index < 0 || index >= draftImages.value.length) return;
  const source = draftImages.value[index];
  const syncKey = resolveDraftMediaSyncKey(source);
  const nextCaption = normalizeBilingualValue(caption);

  if (!syncKey) {
    draftImages.value[index] = normalizeImage(
      { ...source, caption: nextCaption },
      source.id || `gallery-${index + 1}`
    );
    return;
  }

  draftImages.value = draftImages.value.map((entry, entryIndex) => {
    if (resolveDraftMediaSyncKey(entry) !== syncKey) return entry;
    return normalizeImage(
      { ...entry, caption: nextCaption },
      entry.id || `gallery-${entryIndex + 1}`
    );
  });
}

function setDraftCaption(index, lang, value) {
  if (index < 0 || index >= draftImages.value.length) return;
  if (lang !== "de" && lang !== "en") return;
  if (isGalleryImageFieldLocked(index, `caption.${lang}`)) return;
  const item = draftImages.value[index];
  const caption = normalizeBilingualValue(item.caption);
  caption[lang] = String(value || "");
  syncDraftCaptionByMediaKey(index, caption);
  if (item.assetId) scheduleAssetCaptionSync(item.assetId, caption);
}

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

async function importImagesFromMediaTag() {
  if (!selectedMediaTag.value) return;

  importingFromMediaTag.value = true;
  mediaTagImportStatus.value = null;
  try {
    const assets = await listAllAssetsByTag(selectedMediaTag.value);
    const importedImages = assets
      .map((asset, index) => mapAssetToGalleryImage(asset, `gallery-tag-${Date.now()}-${index}`))
      .filter(Boolean);

    if (importedImages.length === 0) {
      mediaTagImportStatus.value = {
        type: "error",
        message: "No media assets with usable URLs found for this tag.",
      };
      return;
    }

    const existingImages = Array.isArray(section.value?.images)
      ? section.value.images.map((img, index) => normalizeImage(img, img?.id || `gallery-${index + 1}`))
      : [];
    const nextImages = mediaTagImportMode.value === "append"
      ? [...existingImages, ...importedImages]
      : importedImages;

    updateSection(effectiveKey.value, { images: nextImages }, { revisionKind: "content" });
    startEdit();
    mediaTagImportStatus.value = {
      type: "success",
      message: `Imported ${importedImages.length} images from media tag "${selectedMediaTag.value}".`,
    };
  } catch (err) {
    console.error("Failed to import gallery images from media tag:", err);
    mediaTagImportStatus.value = {
      type: "error",
      message: err?.message || "Failed to import images from media tag.",
    };
  } finally {
    importingFromMediaTag.value = false;
  }
}

function clearAllGalleryImages() {
  draftImages.value = [];
  expandedItem.value = -1;
  saveGallery();
}

function saveGallery(options = {}) {
  const normalized = toPersistedGalleryImages(draftImages.value);
  updateSection(effectiveKey.value, { images: normalized }, { revisionKind: "content" });
  if (options?.flush) {
    void saveSectionByKey(effectiveKey.value, { revisionKind: "content" });
  }
}

function onCarouselScroll() {
  const el = carouselRef.value;
  if (!el) return;
  const slides = Array.from(el.querySelectorAll(".carousel-slide"));
  if (!slides.length) return;
  const trackCenter = el.scrollLeft + (el.clientWidth / 2);
  let closestIndex = 0;
  let closestDistance = Number.POSITIVE_INFINITY;
  slides.forEach((slide, index) => {
    const slideCenter = slide.offsetLeft + (slide.offsetWidth / 2);
    const distance = Math.abs(trackCenter - slideCenter);
    if (distance < closestDistance) {
      closestDistance = distance;
      closestIndex = index;
    }
  });
  activeSlide.value = closestIndex;
}

function scrollToSlide(index) {
  const el = carouselRef.value;
  if (!el) return;
  const slides = Array.from(el.querySelectorAll(".carousel-slide"));
  const target = slides[index];
  if (!target) return;
  const centeredLeft = target.offsetLeft - ((el.clientWidth - target.offsetWidth) / 2);
  el.scrollTo({ left: Math.max(0, centeredLeft), behavior: "smooth" });
  activeSlide.value = index;
}

function openLightbox(index) {
  if (state.isAdmin && !state.previewMode) return;
  lightboxIndex.value = index;
  lightboxOpen.value = true;
  document.body.style.overflow = "hidden";
}

function closeLightbox() {
  lightboxOpen.value = false;
  document.body.style.overflow = "";
}

function lightboxNav(dir) {
  const length = displayImages.value.length;
  if (!length) return;
  lightboxIndex.value = (lightboxIndex.value + dir + length) % length;
}

function onLightboxPointerStart(event) {
  if (displayImages.value.length <= 1) return;
  lightboxPointerStartX.value = Number.isFinite(event?.clientX) ? event.clientX : null;
  lightboxPointerStartY.value = Number.isFinite(event?.clientY) ? event.clientY : null;
}

function onLightboxPointerEnd(event) {
  if (displayImages.value.length <= 1) return;
  if (lightboxPointerStartX.value === null || lightboxPointerStartY.value === null) return;
  const endX = Number.isFinite(event?.clientX) ? event.clientX : null;
  const endY = Number.isFinite(event?.clientY) ? event.clientY : null;
  if (endX === null || endY === null) {
    onLightboxPointerCancel();
    return;
  }

  const deltaX = endX - lightboxPointerStartX.value;
  const deltaY = endY - lightboxPointerStartY.value;
  onLightboxPointerCancel();
  if (Math.abs(deltaX) < LIGHTBOX_SWIPE_THRESHOLD) return;
  if (Math.abs(deltaY) > Math.abs(deltaX)) return;
  lightboxNav(deltaX > 0 ? -1 : 1);
}

function onLightboxPointerCancel() {
  lightboxPointerStartX.value = null;
  lightboxPointerStartY.value = null;
}

function onLightboxKey(event) {
  if (!lightboxOpen.value) return;
  if (event.key === "Escape") closeLightbox();
  if (event.key === "ArrowLeft") lightboxNav(-1);
  if (event.key === "ArrowRight") lightboxNav(1);
}

watch(lightboxOpen, (open) => {
  if (open) window.addEventListener("keydown", onLightboxKey);
  else window.removeEventListener("keydown", onLightboxKey);
});

onBeforeUnmount(() => {
  dynamicMediaTagRequestId += 1;
  for (const timer of assetCaptionSyncTimers.values()) {
    clearTimeout(timer);
  }
  assetCaptionSyncTimers.clear();
  window.removeEventListener("keydown", onLightboxKey);
  document.body.style.overflow = "";
});
</script>

<style scoped>
.display--empty {
  min-height: 80px;
  display: grid;
  place-items: center;
  margin-top: 14px;
}

.empty-hint {
  font-size: 13px;
  font-weight: 600;
  color: var(--muted, #64748b);
}

.gallery-grid {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.gallery-item,
.masonry-item,
.carousel-slide {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  background: rgba(0, 0, 0, 0.02);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.gallery-item:hover,
.masonry-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

.gallery-item__image {
  width: 100%;
}

.gallery-author-overlay {
  position: absolute;
  top: 10px;
  right: 28px;
  z-index: 2;
  max-width: min(80%, 320px);
  padding: 4px 9px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  letter-spacing: 0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
  transform: rotate(-90deg);
  transform-origin: top right;
  pointer-events: none;
}

.gallery-author-overlay--lightbox {
  top: 14px;
  right: 34px;
  max-width: min(65vw, 540px);
  font-size: 12px;
}

.gallery-caption {
  position: absolute;
  inset: auto 0 0 0;
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.62);
  backdrop-filter: blur(1px);
  -webkit-backdrop-filter: blur(1px);
  color: #fff;
  font-size: 14px;
  line-height: 1.4;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
  pointer-events: none;
  z-index: 1;
}

.gallery-masonry {
  margin-top: 14px;
  columns: 3;
  column-gap: 12px;
}

.masonry-item {
  break-inside: avoid;
  margin-bottom: 12px;
}

.carousel-wrap {
  margin-top: 14px;
  position: relative;
}

.carousel-track {
  display: flex;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
  gap: 12px;
  border-radius: 10px;
  scrollbar-width: none;
}

.carousel-track::-webkit-scrollbar {
  display: none;
}

.carousel-slide {
  flex: 0 0 100%;
  scroll-snap-align: start;
  position: relative;
}

.carousel-caption {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 10px 16px;
  background: rgba(0, 0, 0, 0.62);
  backdrop-filter: blur(1px);
  -webkit-backdrop-filter: blur(1px);
  color: #fff;
  font-size: 14px;
  line-height: 1.4;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
  pointer-events: none;
}

.carousel-dots {
  display: flex;
  justify-content: center;
  gap: 6px;
  margin-top: 10px;
}

.carousel-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.15);
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
}

.carousel-dot.active {
  background: var(--accent, #4f46e5);
  transform: scale(1.3);
}

.lightbox {
  position: fixed;
  inset: 0;
  z-index: 10000;
  background: rgba(0, 0, 0, 0.88);
  display: flex;
  align-items: center;
  justify-content: center;
}

.lightbox-content {
  max-width: 90vw;
  max-height: 85vh;
  position: relative;
  overflow: hidden;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  touch-action: pan-y;
  user-select: none;
}

.lightbox-content img {
  max-width: 90vw;
  max-height: 80vh;
  object-fit: contain;
  border-radius: 0;
}

.lightbox-caption {
  position: absolute;
  inset: auto 0 0 0;
  margin-top: 0;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.64);
  backdrop-filter: blur(1px);
  -webkit-backdrop-filter: blur(1px);
  color: rgba(255, 255, 255, 0.92);
  font-size: 14px;
  text-align: center;
  max-width: none;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
  pointer-events: none;
}

.lightbox-close {
  position: absolute;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  cursor: pointer;
  display: grid;
  place-items: center;
}

.lightbox-close {
  top: 16px;
  right: 20px;
  font-size: 18px;
}

.lightbox-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  cursor: pointer;
  display: grid;
  place-items: center;
  font-size: 20px;
  z-index: 1;
  transition: background 0.15s ease;
}

.lightbox-nav:hover,
.lightbox-nav:focus-visible {
  background: rgba(255, 255, 255, 0.24);
}

.lightbox-prev {
  left: 24px;
}

.lightbox-next {
  right: 24px;
}

.editor-controls {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.ctrl-field {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ctrl-select {
  max-width: 150px;
}

.caption-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text, #2b0c5c);
}

.caption-sync-hint {
  font-size: 12px;
  color: var(--muted, rgba(43, 12, 92, 0.55));
}

.field-label,
.lang-header {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted, rgba(43, 12, 92, 0.55));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.lang-section {
  display: grid;
  gap: 4px;
}

.alt-row {
  display: flex;
  gap: 8px;
}

.alt-row .field {
  flex: 1;
  min-width: 0;
}

.field {
  flex: 1;
  min-width: 0;
  border-radius: 8px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.2));
  background: #fff;
  padding: 8px 12px;
  outline: none;
  color: var(--text, #2b0c5c);
}

.media-tag-import-panel {
  border: 0;
  border-radius: 8px;
  background: transparent;
  margin-bottom: 12px;
}

.media-tag-import-title {
  font-weight: 600;
  color: #374151;
  cursor: pointer;
  padding: 0.75rem;
  background: white;
  border-radius: 8px;
  list-style: none;
}

.media-tag-import-title::-webkit-details-marker {
  display: none;
}

.media-tag-import-title::before {
  content: "▸ ";
  color: #9ca3af;
}

.media-tag-import-panel[open] .media-tag-import-title::before {
  content: "▾ ";
}

.media-tag-import-content {
  display: grid;
  gap: 10px;
  padding: 1rem;
  background: white;
  border-radius: 0 0 8px 8px;
  margin-top: -4px;
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
  flex: 0 0 180px;
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

.dynamic-tag-binding-row {
  display: grid;
  grid-template-columns: minmax(90px, auto) minmax(220px, 1fr) minmax(220px, 1fr) minmax(160px, auto) auto;
  gap: 8px;
  align-items: end;
}

.dynamic-tag-binding-enabled {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  font-size: 13px;
  font-weight: 600;
}

.dynamic-tag-preview {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 12px;
  font-weight: 700;
  color: var(--muted, #5d4c73);
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

@media (max-width: 768px) {
  .dynamic-tag-binding-row {
    grid-template-columns: 1fr;
  }

  .gallery-masonry {
    columns: 2;
  }
}

@media (max-width: 600px) {
  .lightbox-nav {
    width: 40px;
    height: 40px;
    font-size: 17px;
  }

  .lightbox-prev {
    left: 10px;
  }

  .lightbox-next {
    right: 10px;
  }

  .carousel-track {
    gap: 16px;
    padding: 0 calc((100% - 85%) / 2) 8px;
    scroll-snap-type: x mandatory;
  }

  .carousel-slide {
    flex: 0 0 85%;
    min-width: 260px;
    max-width: 420px;
    scroll-snap-align: center;
  }

  .gallery-grid {
    grid-template-columns: 1fr;
  }

  .gallery-masonry {
    columns: 1;
  }
}
</style>
