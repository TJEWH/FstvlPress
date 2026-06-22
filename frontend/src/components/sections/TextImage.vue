<template>
  <SectionBase
    ref="sectionRootRef"
    :section-key="effectiveKey"
    :section-data="section"
    :style="sectionStyleVars"
    class="text-image-section"
    :class="{
      'text-image-section--background': isBackgroundLayout,
      'text-image-section--side': isSideLayout,
      'text-image-section--stacked': isStackedLayout,
    }"
    :admin-tabs-visible="state.isAdmin && (!state.previewMode || isTemplateBuilderPage)"
    title-outside-text-layout
  >
    <template #before-text>
      <div
        v-if="showInlineImage && imageLayoutValue === 'above'"
        class="text-image-section__media text-image-section__media--above"
        :style="inlineMediaStyle"
      >
        <div
          ref="inlineMediaBoxRef"
          class="text-image-section__media-box"
          :class="{ 'text-image-section__media-box--no-crop': !hasFixedAspectRatio }"
        >
          <component
            :is="hasImageLinkValue ? 'a' : 'div'"
            v-if="imageUrlValue"
            class="text-image-section__media-link"
            v-bind="imageLinkAttrsValue"
          >
            <TransformedImage
              :src="imageUrlValue"
              alt="Section image"
              :ratio="inlineImageRatioValue"
              :zoom="imageBgZoomValue"
              :focal-x="imageBgFocalXValue"
              :focal-y="imageBgFocalYValue"
              :rotation="imageBgRotationValue"
              :responsive-variants="imageResponsiveVariantsValue"
              :fit="inlineImageFitValue"
              :use-object-position="false"
              loading="lazy"
              decoding="async"
            />
          </component>
          <div
            v-if="showInlineImageOverlays"
            class="text-image-section__overlay-frame"
            :style="inlineImageOverlayFrameStyle"
          >
            <div v-if="showInlineImageAuthorOverlay" class="text-image-author-overlay">
              {{ imageAuthorOverlayValue }}
            </div>
            <button
              v-if="showInlineImageZoomButton"
              class="text-image-section__zoom-button"
              type="button"
              aria-label="Show image full size"
              title="Show image full size"
              @click.prevent.stop="openImageLightbox"
            >
              <font-awesome-icon :icon="faMagnifyingGlass" aria-hidden="true" />
            </button>
          </div>
          <div v-if="!imageUrlValue && state.isAdmin" class="text-image-section__media-empty">
            Select an image in the Content tab.
          </div>
        </div>
      </div>
    </template>

    <template #after-text>
      <div
        v-if="showInlineImage && imageLayoutValue === 'below'"
        class="text-image-section__media text-image-section__media--below"
        :style="inlineMediaStyle"
      >
        <div
          ref="inlineMediaBoxRef"
          class="text-image-section__media-box"
          :class="{ 'text-image-section__media-box--no-crop': !hasFixedAspectRatio }"
        >
          <component
            :is="hasImageLinkValue ? 'a' : 'div'"
            v-if="imageUrlValue"
            class="text-image-section__media-link"
            v-bind="imageLinkAttrsValue"
          >
            <TransformedImage
              :src="imageUrlValue"
              alt="Section image"
              :ratio="inlineImageRatioValue"
              :zoom="imageBgZoomValue"
              :focal-x="imageBgFocalXValue"
              :focal-y="imageBgFocalYValue"
              :rotation="imageBgRotationValue"
              :responsive-variants="imageResponsiveVariantsValue"
              :fit="inlineImageFitValue"
              :use-object-position="false"
              loading="lazy"
              decoding="async"
            />
          </component>
          <div
            v-if="showInlineImageOverlays"
            class="text-image-section__overlay-frame"
            :style="inlineImageOverlayFrameStyle"
          >
            <div v-if="showInlineImageAuthorOverlay" class="text-image-author-overlay">
              {{ imageAuthorOverlayValue }}
            </div>
            <button
              v-if="showInlineImageZoomButton"
              class="text-image-section__zoom-button"
              type="button"
              aria-label="Show image full size"
              title="Show image full size"
              @click.prevent.stop="openImageLightbox"
            >
              <font-awesome-icon :icon="faMagnifyingGlass" aria-hidden="true" />
            </button>
          </div>
          <div v-if="!imageUrlValue && state.isAdmin" class="text-image-section__media-empty">
            Select an image in the Content tab.
          </div>
        </div>
      </div>
    </template>

    <template #media-left>
      <div
        v-if="showInlineImage && imageLayoutValue === 'left'"
        class="text-image-section__media text-image-section__media--side text-image-section__media--left"
        :style="sideMediaStyle"
      >
        <div
          ref="inlineMediaBoxRef"
          class="text-image-section__media-box"
          :class="{ 'text-image-section__media-box--no-crop': !hasFixedAspectRatio }"
        >
          <component
            :is="hasImageLinkValue ? 'a' : 'div'"
            v-if="imageUrlValue"
            class="text-image-section__media-link"
            v-bind="imageLinkAttrsValue"
          >
            <TransformedImage
              :src="imageUrlValue"
              alt="Section image"
              :ratio="inlineImageRatioValue"
              :zoom="imageBgZoomValue"
              :focal-x="imageBgFocalXValue"
              :focal-y="imageBgFocalYValue"
              :rotation="imageBgRotationValue"
              :responsive-variants="imageResponsiveVariantsValue"
              :fit="inlineImageFitValue"
              :use-object-position="false"
              loading="lazy"
              decoding="async"
            />
          </component>
          <div
            v-if="showInlineImageOverlays"
            class="text-image-section__overlay-frame"
            :style="inlineImageOverlayFrameStyle"
          >
            <div v-if="showInlineImageAuthorOverlay" class="text-image-author-overlay">
              {{ imageAuthorOverlayValue }}
            </div>
            <button
              v-if="showInlineImageZoomButton"
              class="text-image-section__zoom-button"
              type="button"
              aria-label="Show image full size"
              title="Show image full size"
              @click.prevent.stop="openImageLightbox"
            >
              <font-awesome-icon :icon="faMagnifyingGlass" aria-hidden="true" />
            </button>
          </div>
          <div v-if="!imageUrlValue && state.isAdmin" class="text-image-section__media-empty">
            Select an image in the Content tab.
          </div>
        </div>
      </div>
    </template>

    <template #media-right>
      <div
        v-if="showInlineImage && imageLayoutValue === 'right'"
        class="text-image-section__media text-image-section__media--side text-image-section__media--right"
        :style="sideMediaStyle"
      >
        <div
          ref="inlineMediaBoxRef"
          class="text-image-section__media-box"
          :class="{ 'text-image-section__media-box--no-crop': !hasFixedAspectRatio }"
        >
          <component
            :is="hasImageLinkValue ? 'a' : 'div'"
            v-if="imageUrlValue"
            class="text-image-section__media-link"
            v-bind="imageLinkAttrsValue"
          >
            <TransformedImage
              :src="imageUrlValue"
              alt="Section image"
              :ratio="inlineImageRatioValue"
              :zoom="imageBgZoomValue"
              :focal-x="imageBgFocalXValue"
              :focal-y="imageBgFocalYValue"
              :rotation="imageBgRotationValue"
              :responsive-variants="imageResponsiveVariantsValue"
              :fit="inlineImageFitValue"
              :use-object-position="false"
              loading="lazy"
              decoding="async"
            />
          </component>
          <div
            v-if="showInlineImageOverlays"
            class="text-image-section__overlay-frame"
            :style="inlineImageOverlayFrameStyle"
          >
            <div v-if="showInlineImageAuthorOverlay" class="text-image-author-overlay">
              {{ imageAuthorOverlayValue }}
            </div>
            <button
              v-if="showInlineImageZoomButton"
              class="text-image-section__zoom-button"
              type="button"
              aria-label="Show image full size"
              title="Show image full size"
              @click.prevent.stop="openImageLightbox"
            >
              <font-awesome-icon :icon="faMagnifyingGlass" aria-hidden="true" />
            </button>
          </div>
          <div v-if="!imageUrlValue && state.isAdmin" class="text-image-section__media-empty">
            Select an image in the Content tab.
          </div>
        </div>
      </div>
    </template>

    <template #admin-design-params>
      <div class="text-image-admin-grid">
        <div class="text-image-admin-group">
          <div class="text-image-admin-group-title">Layout</div>
          <div class="text-image-admin-top-row">
            <label class="text-image-admin-field">
              <span>Image placement</span>
              <select
                :value="imageLayoutValue"
                :disabled="isTextImageFieldLocked('imageLayout')"
                :title="isTextImageFieldLocked('imageLayout') ? integrationLockedHint : undefined"
                @change="setImageLayout($event.target.value)"
              >
                <option value="above">Above text</option>
                <option value="below">Below text</option>
                <option value="left">Left to text</option>
                <option value="right">Right to text</option>
                <option value="background">Section background</option>
              </select>
            </label>

            <label v-if="isStackedLayout" class="text-image-admin-field">
              <span>Horizontal align (inline only)</span>
              <select
                :value="imageAlignXValue"
                :disabled="isTextImageFieldLocked('imageAlignX')"
                :title="isTextImageFieldLocked('imageAlignX') ? integrationLockedHint : undefined"
                @change="setImageAlignX($event.target.value)"
              >
                <option value="left">Left</option>
                <option value="center">Center</option>
                <option value="right">Right</option>
              </select>
            </label>

            <label v-if="!isBackgroundMode" class="text-image-admin-field">
              <span>Image interaction</span>
              <select
                :value="imageInteractionValue"
                :disabled="isTextImageFieldLocked('imageInteraction')"
                :title="isTextImageFieldLocked('imageInteraction') ? integrationLockedHint : undefined"
                @change="setImageInteraction($event.target.value)"
              >
                <option value="none">None</option>
                <option value="link">Link</option>
                <option value="zoom">Zoom</option>
              </select>
            </label>

            <label v-if="!isBackgroundMode" class="text-image-admin-field">
              <span>Image crop</span>
              <select
                :value="imageAspectRatioValue"
                :disabled="isTextImageFieldLocked('imageAspectRatio')"
                :title="isTextImageFieldLocked('imageAspectRatio') ? integrationLockedHint : undefined"
                @change="setImageAspectRatio($event.target.value)"
              >
                <option value="16:9">16:9</option>
                <option value="1:1">1:1</option>
                <option value="3:4">3:4</option>
                <option value="none">No fixed crop</option>
              </select>
            </label>

            <label v-if="showImageClickUrlControl" class="text-image-admin-field">
              <span>Image click URL</span>
              <input
                type="text"
                :value="imageClickUrlValue"
                placeholder="https://..."
                :disabled="isTextImageFieldLocked('imageClickUrl')"
                :title="isTextImageFieldLocked('imageClickUrl') ? integrationLockedHint : undefined"
                @input="setImageClickUrl($event.target.value)"
              />
            </label>
          </div>
        </div>

        <div v-if="!isBackgroundMode" class="text-image-admin-group">
          <div class="text-image-admin-group-title">Inline Size</div>
          <div class="text-image-admin-group-grid">
            <label class="text-image-admin-field">
              <span>Image wrapper width</span>
              <div class="text-image-admin-range">
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  :value="imageMaxWidthPercentValue"
                  :disabled="isTextImageFieldLocked('imageMaxWidthPercent')"
                  :title="isTextImageFieldLocked('imageMaxWidthPercent') ? integrationLockedHint : undefined"
                  @input="setImageMaxWidthPercent($event.target.value)"
                />
                <span>{{ imageWrapperWidthPercentDisplay }}</span>
              </div>
            </label>

            <label class="text-image-admin-field">
              <span>Image width</span>
              <div class="text-image-admin-range">
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  :value="imageTargetWidthPercentValue"
                  :disabled="isTextImageFieldLocked('imageTargetWidthPercent')"
                  :title="isTextImageFieldLocked('imageTargetWidthPercent') ? integrationLockedHint : undefined"
                  @input="setImageTargetWidthPercent($event.target.value)"
                />
                <span>{{ imageTargetWidthPercentValue }}%</span>
              </div>
            </label>

            <label class="text-image-admin-field">
              <span>Image min width</span>
              <div class="text-image-admin-range">
                <input
                  type="range"
                  min="0"
                  max="2000"
                  step="1"
                  :value="imageMinWidthPxValue"
                  :disabled="isTextImageFieldLocked('imageMinWidthPx')"
                  :title="isTextImageFieldLocked('imageMinWidthPx') ? integrationLockedHint : undefined"
                  @input="setImageMinWidthPx($event.target.value)"
                />
                <span>{{ imageMinWidthPxDisplay }}</span>
              </div>
            </label>

            <label class="text-image-admin-field">
              <span>Image max width</span>
              <div class="text-image-admin-range">
                <input
                  type="range"
                  min="0"
                  max="2000"
                  step="1"
                  :value="imageMaxWidthPxValue"
                  :disabled="isTextImageFieldLocked('imageMaxWidthPx')"
                  :title="isTextImageFieldLocked('imageMaxWidthPx') ? integrationLockedHint : undefined"
                  @input="setImageMaxWidthPx($event.target.value)"
                />
                <span>{{ imageMaxWidthPxDisplay }}</span>
              </div>
            </label>

            <label v-if="showInlineHeightControls" class="text-image-admin-field">
              <span>Image height</span>
              <div class="text-image-admin-range">
                <input
                  type="range"
                  min="0"
                  max="2000"
                  step="1"
                  :value="imageHeightPxValue"
                  :disabled="isTextImageFieldLocked('imageHeightPx')"
                  :title="isTextImageFieldLocked('imageHeightPx') ? integrationLockedHint : undefined"
                  @input="setImageHeightPx($event.target.value)"
                />
                <span>{{ imageHeightPxDisplay }}</span>
              </div>
            </label>

            <label v-if="showInlineHeightControls" class="text-image-admin-field">
              <span>Image max height</span>
              <div class="text-image-admin-range">
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  :value="imageMaxHeightVhValue"
                  :disabled="isTextImageFieldLocked('imageMaxHeightVh')"
                  :title="isTextImageFieldLocked('imageMaxHeightVh') ? integrationLockedHint : undefined"
                  @input="setImageMaxHeightVh($event.target.value)"
                />
                <span>{{ imageMaxHeightVhDisplay }}</span>
              </div>
            </label>

            <label class="text-image-admin-field">
              <span>Space between text and image</span>
              <div class="text-image-admin-range">
                <input
                  type="range"
                  min="0"
                  max="80"
                  step="1"
                  :value="imageTextGapValue"
                  :disabled="isTextImageFieldLocked('imageTextGap')"
                  :title="isTextImageFieldLocked('imageTextGap') ? integrationLockedHint : undefined"
                  @input="setImageTextGap($event.target.value)"
                />
                <span>{{ imageTextGapValue }}%</span>
              </div>
            </label>

            <label v-if="showImageBorderRadiusControl" class="text-image-admin-field">
              <span>Image border radius</span>
              <div class="text-image-admin-range">
                <input
                  type="range"
                  min="0"
                  max="499"
                  step="1"
                  :value="imageBorderRadiusValue"
                  :disabled="isTextImageFieldLocked('imageBorderRadius')"
                  :title="isTextImageFieldLocked('imageBorderRadius') ? integrationLockedHint : undefined"
                  @input="setImageBorderRadius($event.target.value)"
                />
                <span>{{ imageBorderRadiusValue }}px</span>
              </div>
            </label>
          </div>
        </div>

        <div v-if="isBackgroundMode" class="text-image-admin-group">
          <div class="text-image-admin-group-title">Background</div>
          <div class="text-image-admin-group-grid">
            <label v-if="showImageBorderRadiusControl" class="text-image-admin-field">
              <span>Image border radius</span>
              <div class="text-image-admin-range">
                <input
                  type="range"
                  min="0"
                  max="499"
                  step="1"
                  :value="imageBorderRadiusValue"
                  :disabled="isTextImageFieldLocked('imageBorderRadius')"
                  :title="isTextImageFieldLocked('imageBorderRadius') ? integrationLockedHint : undefined"
                  @input="setImageBorderRadius($event.target.value)"
                />
                <span>{{ imageBorderRadiusValue }}px</span>
              </div>
            </label>

            <label class="text-image-admin-field">
              <span>Background image opacity</span>
              <div class="text-image-admin-range">
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  :value="imageBgOpacityValue"
                  :disabled="isTextImageFieldLocked('imageBgOpacity')"
                  :title="isTextImageFieldLocked('imageBgOpacity') ? integrationLockedHint : undefined"
                  @input="setImageBgOpacity($event.target.value)"
                />
                <span>{{ imageBgOpacityValue.toFixed(2) }}</span>
              </div>
            </label>
          </div>
        </div>

      </div>
    </template>

    <template #admin-content>
      <div class="text-image-admin-content">
        <div class="text-image-admin-preview-card" :class="{ 'text-image-admin-preview-card--background': isBackgroundMode }">
          <div class="text-image-admin-preview-head">
            <span class="text-image-admin-preview-title">Section image</span>
            <span class="text-image-admin-preview-mode">{{ isBackgroundMode ? "Background mode" : "Inline mode" }}</span>
          </div>
          <ImageTransformEditor
            :image-url="imageUrlValue"
            :zoom="imageBgZoomValue"
            :focal-x="imageBgFocalXValue"
            :focal-y="imageBgFocalYValue"
            :rotation="imageBgRotationValue"
            :ratio="isBackgroundMode ? '16:9' : imageEditorRatioValue"
            :preview-aspect="isBackgroundMode ? backgroundPreviewAspect : null"
            view-context="section"
            :image-url-disabled="isTextImageFieldLocked('imageUrl')"
            :zoom-disabled="isTextImageFieldLocked('imageBgZoom')"
            :focal-disabled="isTextImageFieldLocked('imageBgFocalX') || isTextImageFieldLocked('imageBgFocalY')"
            :rotation-disabled="isTextImageFieldLocked('imageBgRotation')"
            @update:image-url="setImageUrl"
            @update:zoom="setImageBgZoom"
            @update:focal-x="setImageBgFocalX"
            @update:focal-y="setImageBgFocalY"
            @update:rotation="setImageBgRotation"
            @choose-image="openImagePicker"
            @clear-image="setImageUrl('', [], '')"
          />
        </div>
        <MediaLibrary
          :is-open="showMediaPicker"
          :current-url="imageUrlValue"
          source-context="section.text_image.image"
          :allow-clear-selection="true"
          @close="closeImagePicker"
          @select="onMediaSelect"
        />
      </div>
    </template>
  </SectionBase>

  <Teleport to="body">
    <div
      v-if="imageLightboxOpen && imageInteractionValue === 'zoom' && !isBackgroundMode"
      class="text-image-lightbox"
      @click.self="closeImageLightbox"
    >
      <button
        class="text-image-lightbox__close"
        type="button"
        aria-label="Close full-size image"
        @click="closeImageLightbox"
      >
        &#10005;
      </button>
      <div
        class="text-image-lightbox__content"
        :class="{ 'text-image-lightbox__content--svg': isLightboxSvgImage }"
      >
        <img
          class="text-image-lightbox__image"
          :class="{ 'text-image-lightbox__image--svg': isLightboxSvgImage }"
          :src="imageUrlValue"
          alt="Section image"
          decoding="async"
        />
        <div
          v-if="imageAuthorOverlayValue"
          class="text-image-author-overlay text-image-author-overlay--lightbox"
        >
          {{ imageAuthorOverlayValue }}
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { faMagnifyingGlass } from "@fortawesome/free-solid-svg-icons";
import { useStore } from "../../store/store.js";
import { convertKeysToCamel } from "../../utils/caseConversion.js";
import { resolveBackendResponsiveImagePayload } from "../../utils/responsiveImages.js";
import { isSectionIntegrationFieldLocked } from "../../utils/sectionIntegrationFieldState.js";

import SectionBase from "./_BaseSection.vue";
import MediaLibrary from "../ui/MediaLibrary.vue";
import ImageTransformEditor from "../ui/ImageTransformEditor.vue";
import TransformedImage from "../ui/TransformedImage.vue";

const props = defineProps({
  sectionKey: { type: String, required: true },
  sectionData: { type: Object, default: null }
});

const DEFAULT_IMAGE_TEXT_GAP_PERCENT = 5;
const DEFAULT_IMAGE_MAX_WIDTH_PERCENT = 30;
const DEFAULT_IMAGE_MAX_HEIGHT_VH = 70;
const DEFAULT_IMAGE_MIN_WIDTH_PX = 0;
const DEFAULT_IMAGE_TARGET_WIDTH_PERCENT = 100;
const DEFAULT_IMAGE_MAX_WIDTH_PX = 0;
const DEFAULT_IMAGE_HEIGHT_PX = 0;
const INLINE_AUTHOR_OVERLAY_MIN_HEIGHT = 150;
const INLINE_ZOOM_BUTTON_MIN_HEIGHT = 50;
const integrationLockedHint = "Managed by integration import.";
const { state, updateSection } = useStore();

const effectiveKey = computed(() => props.sectionKey);

const section = computed(() => {
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});
const isTemplateBuilderPage = computed(() =>
  String(state.pageSlug || "").startsWith("__template_")
);

function isTextImageFieldLocked(path, options = {}) {
  return state.isAdmin && isSectionIntegrationFieldLocked(section.value, path, options);
}

const showMediaPicker = ref(false);
const imageLightboxOpen = ref(false);
const sectionRootRef = ref(null);
const inlineMediaBoxRef = ref(null);
const inlineImageOverlayFrame = ref({ left: 0, top: 0, width: 0, height: 0 });
const backgroundPreviewAspect = ref(16 / 9);
let sectionResizeObserver = null;
let inlineOverlayResizeObserver = null;
let inlineOverlayMeasureFrame = null;
let inlineOverlayImageCleanup = null;

function normalizeUrlCandidate(value) {
  return typeof value === "string" ? value.trim() : "";
}

function isSvgImageUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return false;
  if (/^data:image\/svg\+xml[;,]/i.test(raw)) return true;
  const path = raw.split("#", 1)[0].split("?", 1)[0].trim().toLowerCase();
  return path.endsWith(".svg");
}

function normalizeImageAuthor(value) {
  return String(value || "").trim();
}

function formatImageAuthorOverlay(value) {
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
  return normalizeImageAuthor(
    source.authors.find((entry) => normalizeImageAuthor(entry))
  );
}

const imageUrlValue = computed(() => {
  const candidates = [
    section.value?.imageUrl,
  ];
  for (const candidate of candidates) {
    const normalized = normalizeUrlCandidate(candidate);
    if (normalized) return normalized;
  }
  return "";
});
const imageAuthorValue = computed(() =>
  normalizeImageAuthor(convertKeysToCamel(section.value || {}).imageAuthor)
);
const imageAuthorOverlayValue = computed(() => formatImageAuthorOverlay(imageAuthorValue.value));
const isLightboxSvgImage = computed(() => isSvgImageUrl(imageUrlValue.value));

function normalizeLayout(value) {
  if (value === "below" || value === "left" || value === "right" || value === "background") return value;
  return "above";
}

function normalizeAlignX(value) {
  if (value === "left" || value === "right") return value;
  return "center";
}

function normalizeAspectRatio(value) {
  if (value === "1:1" || value === "3:4" || value === "none") return value;
  return "16:9";
}

function normalizeImageInteraction(value) {
  if (value === "link" || value === "zoom") return value;
  return "none";
}

function normalizeImageHref(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (raw.startsWith("//")) return `https:${raw}`;
  if (raw.startsWith("/") || raw.startsWith("#") || raw.startsWith("?")) return raw;
  if (/^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(raw)) {
    const scheme = raw.split(":", 1)[0].toLowerCase();
    if (scheme === "http" || scheme === "https" || scheme === "mailto" || scheme === "tel") {
      return raw;
    }
    return "";
  }
  return `https://${raw}`;
}

const imageAlignXValue = computed(() => normalizeAlignX(section.value?.imageAlignX));
const imageLayoutValue = computed(() => normalizeLayout(section.value?.imageLayout));
const imageMaxWidthPercentValue = computed(() => {
  const raw = Number(section.value?.imageMaxWidthPercent ?? section.value?.imageWidthPercent);
  if (!Number.isFinite(raw)) return DEFAULT_IMAGE_MAX_WIDTH_PERCENT;
  return Math.max(0, Math.min(100, Math.round(raw)));
});
const imageMaxHeightVhValue = computed(() => {
  const raw = Number(section.value?.imageMaxHeightVh);
  if (!Number.isFinite(raw)) return DEFAULT_IMAGE_MAX_HEIGHT_VH;
  return Math.max(0, Math.min(100, Math.round(raw)));
});
const imageMinWidthPxValue = computed(() => {
  const raw = Number(section.value?.imageMinWidthPx);
  if (!Number.isFinite(raw)) return DEFAULT_IMAGE_MIN_WIDTH_PX;
  return Math.max(0, Math.min(2000, Math.round(raw)));
});
const imageTargetWidthPercentValue = computed(() => {
  const raw = Number(section.value?.imageTargetWidthPercent);
  if (!Number.isFinite(raw)) return DEFAULT_IMAGE_TARGET_WIDTH_PERCENT;
  return Math.max(0, Math.min(100, Math.round(raw)));
});
const imageMaxWidthPxValue = computed(() => {
  const raw = Number(section.value?.imageMaxWidthPx ?? section.value?.imageWidthPx);
  if (!Number.isFinite(raw)) return DEFAULT_IMAGE_MAX_WIDTH_PX;
  return Math.max(0, Math.min(2000, Math.round(raw)));
});
const imageHeightPxValue = computed(() => {
  const raw = Number(section.value?.imageHeightPx);
  if (!Number.isFinite(raw)) return DEFAULT_IMAGE_HEIGHT_PX;
  return Math.max(0, Math.min(2000, Math.round(raw)));
});
const imageTextGapValue = computed(() => {
  const raw = Number(section.value?.imageTextGap);
  if (!Number.isFinite(raw)) return DEFAULT_IMAGE_TEXT_GAP_PERCENT;
  return Math.max(0, Math.min(80, Math.round(raw)));
});
const imageBorderRadiusValue = computed(() => {
  const raw = Number(section.value?.imageBorderRadius);
  if (!Number.isFinite(raw)) return 14;
  return Math.max(0, Math.min(499, Math.round(raw)));
});
const imageAspectRatioValue = computed(() =>
  normalizeAspectRatio(section.value?.imageAspectRatio)
);
const imageInteractionValue = computed(() =>
  normalizeImageInteraction(section.value?.imageInteraction)
);
const imageWrapperWidthPercentDisplay = computed(() =>
  imageMaxWidthPercentValue.value <= 0
    ? "100%"
    : `${imageMaxWidthPercentValue.value}%`
);
const imageMaxHeightVhDisplay = computed(() =>
  imageMaxHeightVhValue.value <= 0
    ? "none"
    : `${imageMaxHeightVhValue.value}vh`
);
const imageMinWidthPxDisplay = computed(() =>
  imageMinWidthPxValue.value <= 0
    ? "auto"
    : `${imageMinWidthPxValue.value}px`
);
const imageMaxWidthPxDisplay = computed(() =>
  imageMaxWidthPxValue.value <= 0
    ? "none"
    : `${imageMaxWidthPxValue.value}px`
);
const imageHeightPxDisplay = computed(() =>
  imageHeightPxValue.value <= 0
    ? "auto"
    : `${imageHeightPxValue.value}px`
);
const imageBgOpacityValue = computed(() => {
  const raw = Number(section.value?.imageBgOpacity);
  if (!Number.isFinite(raw)) return 0.72;
  return Math.max(0, Math.min(1, raw));
});
const imageBgZoomValue = computed(() => {
  const raw = Number(section.value?.imageBgZoom);
  if (!Number.isFinite(raw)) return 1;
  return Math.max(1, Math.min(4, raw));
});
const imageBgFocalXValue = computed(() => {
  const raw = Number(section.value?.imageBgFocalX);
  if (!Number.isFinite(raw)) return 50;
  return Math.max(0, Math.min(100, raw));
});
const imageBgFocalYValue = computed(() => {
  const raw = Number(section.value?.imageBgFocalY);
  if (!Number.isFinite(raw)) return 50;
  return Math.max(0, Math.min(100, raw));
});
const imageBgRotationValue = computed(() => {
  const raw = Number(section.value?.imageBgRotation);
  if (!Number.isFinite(raw)) return 0;
  return Math.max(-180, Math.min(180, raw));
});
const imageEditorRatioValue = computed(() => {
  if (imageAspectRatioValue.value === "none") return "16:9";
  return imageAspectRatioValue.value;
});
const hasFixedAspectRatio = computed(() => imageAspectRatioValue.value !== "none");
const effectiveImageBorderRadiusValue = computed(() =>
  hasFixedAspectRatio.value ? imageBorderRadiusValue.value : 0
);
const inlineImageRatioValue = computed(() =>
  hasFixedAspectRatio.value ? imageAspectRatioValue.value : ""
);
const inlineImageFitValue = computed(() =>
  hasFixedAspectRatio.value ? "cover" : "contain"
);
const imageAspectRatioCssValue = computed(() => {
  if (imageAspectRatioValue.value === "1:1") return "1 / 1";
  if (imageAspectRatioValue.value === "3:4") return "3 / 4";
  if (imageAspectRatioValue.value === "none") return "auto";
  return "16 / 9";
});
const imageResponsiveVariantsValue = computed(() => {
  if (isSvgImageUrl(imageUrlValue.value)) return [];
  const v = section.value?.imageResponsiveVariants;
  return Array.isArray(v) ? v : [];
});
const imageClickUrlValue = computed(() => {
  const candidates = [
    section.value?.imageClickUrl,
    section.value?.image_click_url,
  ];
  for (const candidate of candidates) {
    const normalized = normalizeUrlCandidate(candidate);
    if (normalized) return normalized;
  }
  return "";
});
const imageLinkHrefValue = computed(() => {
  if (imageInteractionValue.value !== "link") return "";
  if (state.isAdmin) return "";
  return normalizeImageHref(imageClickUrlValue.value);
});
const hasImageLinkValue = computed(() => Boolean(imageLinkHrefValue.value));
const imageLinkAttrsValue = computed(() =>
  hasImageLinkValue.value
    ? {
      href: imageLinkHrefValue.value,
      target: "_blank",
      rel: "noopener noreferrer",
    }
    : {}
);
const isBackgroundMode = computed(() => imageLayoutValue.value === "background");
const isSideLayout = computed(() =>
  imageLayoutValue.value === "left" || imageLayoutValue.value === "right"
);
const isStackedLayout = computed(() =>
  imageLayoutValue.value === "above" || imageLayoutValue.value === "below"
);
const showInlineHeightControls = computed(() =>
  !isBackgroundMode.value && !hasFixedAspectRatio.value
);
const showImageBorderRadiusControl = computed(() =>
  isBackgroundMode.value || hasFixedAspectRatio.value
);

const isBackgroundLayout = computed(() =>
  isBackgroundMode.value && !!imageUrlValue.value
);

const showInlineImage = computed(() =>
  imageLayoutValue.value !== "background" && (state.isAdmin || !!imageUrlValue.value)
);
const hasInlineImageOverlayFrame = computed(() =>
  Boolean(imageUrlValue.value)
  && !isBackgroundMode.value
  && inlineImageOverlayFrame.value.width > 0
  && inlineImageOverlayFrame.value.height > 0
);
const showInlineImageAuthorOverlay = computed(() =>
  Boolean(imageAuthorOverlayValue.value)
  && hasInlineImageOverlayFrame.value
  && inlineImageOverlayFrame.value.height >= INLINE_AUTHOR_OVERLAY_MIN_HEIGHT
);
const showInlineImageZoomButton = computed(() =>
  imageInteractionValue.value === "zoom"
  && Boolean(imageUrlValue.value)
  && hasInlineImageOverlayFrame.value
  && inlineImageOverlayFrame.value.height >= INLINE_ZOOM_BUTTON_MIN_HEIGHT
);
const showInlineImageOverlays = computed(() =>
  showInlineImageAuthorOverlay.value || showInlineImageZoomButton.value
);
const showImageClickUrlControl = computed(() =>
  !isBackgroundMode.value && imageInteractionValue.value === "link"
);
const inlineImageOverlayFrameStyle = computed(() => ({
  left: `${inlineImageOverlayFrame.value.left}px`,
  top: `${inlineImageOverlayFrame.value.top}px`,
  width: `${inlineImageOverlayFrame.value.width}px`,
  height: `${inlineImageOverlayFrame.value.height}px`,
}));

const stackedMarginInlineValue = computed(() => {
  if (imageAlignXValue.value === "right") return "auto 0";
  if (imageAlignXValue.value === "center") return "auto";
  return "0 auto";
});
const stackedTextAlignValue = computed(() => {
  if (imageAlignXValue.value === "right") return "right";
  if (imageAlignXValue.value === "center") return "center";
  return "left";
});
const inlineImageHeightCssValue = computed(() =>
  hasFixedAspectRatio.value || imageHeightPxValue.value <= 0
    ? "auto"
    : `${imageHeightPxValue.value}px`
);
const inlineImageHeightCapCssValue = computed(() =>
  hasFixedAspectRatio.value || imageHeightPxValue.value <= 0
    ? "99999px"
    : `${imageHeightPxValue.value}px`
);
const inlineImageMaxHeightCapCssValue = computed(() =>
  hasFixedAspectRatio.value || imageMaxHeightVhValue.value <= 0
    ? "99999px"
    : `${imageMaxHeightVhValue.value}vh`
);
const imageWrapperWidthCssValue = computed(() =>
  imageMaxWidthPercentValue.value <= 0 ? "100%" : `${imageMaxWidthPercentValue.value}%`
);
const imageBoxWidthCssValue = computed(() => {
  const minWidth = `${imageMinWidthPxValue.value}px`;
  const targetWidth = `${imageTargetWidthPercentValue.value}%`;
  const maxWidth = imageMaxWidthPxValue.value <= 0 ? "100%" : `${imageMaxWidthPxValue.value}px`;
  return `clamp(${minWidth}, ${targetWidth}, ${maxWidth})`;
});

const sectionStyleVars = computed(() => ({
  "--text-image-content-gap": `${imageTextGapValue.value}%`,
  "--text-image-wrapper-width": imageWrapperWidthCssValue.value,
  "--text-image-box-width": imageBoxWidthCssValue.value,
  "--text-image-max-height-vh-cap": inlineImageMaxHeightCapCssValue.value,
  "--text-image-height-px": inlineImageHeightCssValue.value,
  "--text-image-height-px-cap": inlineImageHeightCapCssValue.value,
  "--text-image-border-radius": `${effectiveImageBorderRadiusValue.value}px`,
  "--text-image-stacked-margin-inline": stackedMarginInlineValue.value,
  "--text-image-stacked-text-align": stackedTextAlignValue.value,
}));

const inlineMediaStyle = computed(() => ({
  "--text-image-content-gap": `${imageTextGapValue.value}%`,
  "--text-image-wrapper-width": imageWrapperWidthCssValue.value,
  "--text-image-box-width": imageBoxWidthCssValue.value,
  "--text-image-max-height-vh-cap": inlineImageMaxHeightCapCssValue.value,
  "--text-image-height-px": inlineImageHeightCssValue.value,
  "--text-image-height-px-cap": inlineImageHeightCapCssValue.value,
  "--text-image-border-radius": `${effectiveImageBorderRadiusValue.value}px`,
  "--text-image-aspect-ratio": imageAspectRatioCssValue.value,
  "--text-image-stacked-margin-inline": stackedMarginInlineValue.value,
}));

const sideMediaStyle = computed(() => ({
  "--text-image-content-gap": `${imageTextGapValue.value}%`,
  "--text-image-wrapper-width": imageWrapperWidthCssValue.value,
  "--text-image-box-width": imageBoxWidthCssValue.value,
  "--text-image-max-height-vh-cap": inlineImageMaxHeightCapCssValue.value,
  "--text-image-height-px": inlineImageHeightCssValue.value,
  "--text-image-height-px-cap": inlineImageHeightCapCssValue.value,
  "--text-image-border-radius": `${effectiveImageBorderRadiusValue.value}px`,
  "--text-image-aspect-ratio": imageAspectRatioCssValue.value,
}));

function updateBackgroundPreviewAspect() {
  const el = sectionRootRef.value?.$el || sectionRootRef.value;
  if (!el) return;
  const width = Number(el.clientWidth || 0);
  const height = Number(el.clientHeight || 0);
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return;
  const ratio = width / height;
  if (!Number.isFinite(ratio) || ratio <= 0) return;
  backgroundPreviewAspect.value = Math.max(0.2, Math.min(5, ratio));
}

onMounted(() => {
  updateBackgroundPreviewAspect();
  nextTick(refreshInlineOverlayTracking);
  if (typeof window === "undefined") return;
  window.addEventListener("resize", scheduleInlineOverlayMeasure, { passive: true });
  if (typeof window.ResizeObserver === "function") {
    sectionResizeObserver = new window.ResizeObserver(() => {
      updateBackgroundPreviewAspect();
    });
    const el = sectionRootRef.value?.$el || sectionRootRef.value;
    if (el) sectionResizeObserver.observe(el);
  }
});

onBeforeUnmount(() => {
  if (sectionResizeObserver) {
    sectionResizeObserver.disconnect();
    sectionResizeObserver = null;
  }
  cleanupInlineOverlayTracking();
  if (inlineOverlayMeasureFrame != null && typeof window !== "undefined") {
    window.cancelAnimationFrame(inlineOverlayMeasureFrame);
    inlineOverlayMeasureFrame = null;
  }
  if (typeof window !== "undefined") {
    window.removeEventListener("resize", scheduleInlineOverlayMeasure);
    window.removeEventListener("keydown", onImageLightboxKey);
  }
});

watch(
  () => [
    showInlineImage.value,
    imageLayoutValue.value,
    imageUrlValue.value,
    imageAspectRatioValue.value,
    imageMaxWidthPercentValue.value,
    imageMinWidthPxValue.value,
    imageTargetWidthPercentValue.value,
    imageMaxWidthPxValue.value,
    imageMaxHeightVhValue.value,
    imageHeightPxValue.value,
    imageBgZoomValue.value,
    imageBgFocalXValue.value,
    imageBgFocalYValue.value,
    imageBgRotationValue.value,
  ],
  () => {
    nextTick(refreshInlineOverlayTracking);
  },
  { flush: "post" }
);

function resolveInlineMediaBox() {
  const current = inlineMediaBoxRef.value;
  if (Array.isArray(current)) return current.find(Boolean) || null;
  return current || null;
}

function resetInlineOverlayFrame() {
  inlineImageOverlayFrame.value = { left: 0, top: 0, width: 0, height: 0 };
}

function cleanupInlineOverlayTracking() {
  if (inlineOverlayResizeObserver) {
    inlineOverlayResizeObserver.disconnect();
    inlineOverlayResizeObserver = null;
  }
  if (typeof inlineOverlayImageCleanup === "function") {
    inlineOverlayImageCleanup();
    inlineOverlayImageCleanup = null;
  }
}

function refreshInlineOverlayTracking() {
  cleanupInlineOverlayTracking();
  const box = resolveInlineMediaBox();
  if (!box || !imageUrlValue.value || isBackgroundMode.value) {
    resetInlineOverlayFrame();
    return;
  }
  const image = box.querySelector(".transformed-image__viewport > img");
  if (typeof window !== "undefined" && typeof window.ResizeObserver === "function") {
    inlineOverlayResizeObserver = new window.ResizeObserver(scheduleInlineOverlayMeasure);
    inlineOverlayResizeObserver.observe(box);
    const transformedImage = box.querySelector(".transformed-image");
    const viewport = box.querySelector(".transformed-image__viewport");
    if (transformedImage) inlineOverlayResizeObserver.observe(transformedImage);
    if (viewport) inlineOverlayResizeObserver.observe(viewport);
    if (image) inlineOverlayResizeObserver.observe(image);
  }
  if (image) {
    image.addEventListener("load", scheduleInlineOverlayMeasure);
    inlineOverlayImageCleanup = () => {
      image.removeEventListener("load", scheduleInlineOverlayMeasure);
    };
  }
  scheduleInlineOverlayMeasure();
}

function scheduleInlineOverlayMeasure() {
  if (typeof window === "undefined") {
    measureInlineOverlayFrame();
    return;
  }
  if (inlineOverlayMeasureFrame != null) return;
  inlineOverlayMeasureFrame = window.requestAnimationFrame(() => {
    inlineOverlayMeasureFrame = null;
    measureInlineOverlayFrame();
  });
}

function measureInlineOverlayFrame() {
  const box = resolveInlineMediaBox();
  if (!box || !imageUrlValue.value || isBackgroundMode.value) {
    resetInlineOverlayFrame();
    return;
  }
  const image = box.querySelector(".transformed-image__viewport > img");
  const transformedImage = box.querySelector(".transformed-image");
  if (!image || !transformedImage) {
    resetInlineOverlayFrame();
    return;
  }
  const boxRect = box.getBoundingClientRect();
  const imageFrameRect = transformedImage.getBoundingClientRect();
  let left = imageFrameRect.left;
  let top = imageFrameRect.top;
  let width = Math.max(0, imageFrameRect.width);
  let height = Math.max(0, imageFrameRect.height);
  if (inlineImageFitValue.value === "contain") {
    const naturalWidth = Number(image.naturalWidth || 0);
    const naturalHeight = Number(image.naturalHeight || 0);
    if (naturalWidth <= 0 || naturalHeight <= 0) {
      resetInlineOverlayFrame();
      return;
    }
    const naturalAspect = naturalWidth / naturalHeight;
    const frameAspect = width / height;
    if (Number.isFinite(naturalAspect) && naturalAspect > 0 && Number.isFinite(frameAspect) && frameAspect > 0) {
      if (frameAspect > naturalAspect) {
        const renderedWidth = height * naturalAspect;
        left += (width - renderedWidth) / 2;
        width = renderedWidth;
      } else {
        const renderedHeight = width / naturalAspect;
        top += (height - renderedHeight) / 2;
        height = renderedHeight;
      }
    }
  }
  if (boxRect.width <= 0 || boxRect.height <= 0 || width <= 0 || height <= 0) {
    resetInlineOverlayFrame();
    return;
  }
  inlineImageOverlayFrame.value = {
    left: left - boxRect.left,
    top: top - boxRect.top,
    width,
    height,
  };
}

function openImageLightbox(event) {
  event?.preventDefault?.();
  event?.stopPropagation?.();
  if (!imageUrlValue.value || imageInteractionValue.value !== "zoom" || isBackgroundMode.value) return;
  imageLightboxOpen.value = true;
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", onImageLightboxKey);
  }
}

function closeImageLightbox() {
  imageLightboxOpen.value = false;
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", onImageLightboxKey);
  }
}

function onImageLightboxKey(event) {
  if (!imageLightboxOpen.value) return;
  if (event.key === "Escape") {
    closeImageLightbox();
  }
}

function setImageUrl(url, variants, imageAuthor = null) {
  if (isTextImageFieldLocked("imageUrl")) return;
  const normalized = String(url || "").trim();
  const patch = { imageUrl: normalized };
  const currentUrl = normalizeUrlCandidate(imageUrlValue.value);
  const urlChanged = normalized !== currentUrl;
  const nextAuthor = imageAuthor === null
    ? (urlChanged ? "" : imageAuthorValue.value)
    : imageAuthor;
  patch.imageAuthor = normalizeImageAuthor(normalized ? nextAuthor : "");
  if (isSvgImageUrl(normalized)) {
    patch.imageResponsiveVariants = [];
  } else if (Array.isArray(variants)) {
    patch.imageResponsiveVariants = variants;
  } else if (!normalized || urlChanged) {
    patch.imageResponsiveVariants = [];
  }
  updateSection(effectiveKey.value, patch, { revisionKind: "content" });
}

function setImageLayout(value) {
  if (isTextImageFieldLocked("imageLayout")) return;
  const next = normalizeLayout(value);
  if (next === "background") closeImageLightbox();
  updateSection(effectiveKey.value, { imageLayout: next }, { revisionKind: "design" });
}

function setImageAlignX(value) {
  if (isTextImageFieldLocked("imageAlignX")) return;
  updateSection(effectiveKey.value, { imageAlignX: normalizeAlignX(value) }, { revisionKind: "design" });
}

function setImageMaxWidthPercent(value) {
  if (isTextImageFieldLocked("imageMaxWidthPercent")) return;
  const raw = Number(value);
  const next = Number.isFinite(raw)
    ? Math.max(0, Math.min(100, Math.round(raw)))
    : DEFAULT_IMAGE_MAX_WIDTH_PERCENT;
  updateSection(effectiveKey.value, { imageMaxWidthPercent: next }, { revisionKind: "design" });
}

function setImageMaxHeightVh(value) {
  if (isTextImageFieldLocked("imageMaxHeightVh")) return;
  const raw = Number(value);
  const next = Number.isFinite(raw)
    ? Math.max(0, Math.min(100, Math.round(raw)))
    : DEFAULT_IMAGE_MAX_HEIGHT_VH;
  updateSection(effectiveKey.value, { imageMaxHeightVh: next }, { revisionKind: "design" });
}

function setImageMinWidthPx(value) {
  if (isTextImageFieldLocked("imageMinWidthPx")) return;
  const raw = Number(value);
  const next = Number.isFinite(raw)
    ? Math.max(0, Math.min(2000, Math.round(raw)))
    : DEFAULT_IMAGE_MIN_WIDTH_PX;
  updateSection(effectiveKey.value, { imageMinWidthPx: next }, { revisionKind: "design" });
}

function setImageTargetWidthPercent(value) {
  if (isTextImageFieldLocked("imageTargetWidthPercent")) return;
  const raw = Number(value);
  const next = Number.isFinite(raw)
    ? Math.max(0, Math.min(100, Math.round(raw)))
    : DEFAULT_IMAGE_TARGET_WIDTH_PERCENT;
  updateSection(effectiveKey.value, { imageTargetWidthPercent: next }, { revisionKind: "design" });
}

function setImageMaxWidthPx(value) {
  if (isTextImageFieldLocked("imageMaxWidthPx")) return;
  const raw = Number(value);
  const next = Number.isFinite(raw)
    ? Math.max(0, Math.min(2000, Math.round(raw)))
    : DEFAULT_IMAGE_MAX_WIDTH_PX;
  updateSection(effectiveKey.value, { imageMaxWidthPx: next }, { revisionKind: "design" });
}

function setImageHeightPx(value) {
  if (isTextImageFieldLocked("imageHeightPx")) return;
  const raw = Number(value);
  const next = Number.isFinite(raw)
    ? Math.max(0, Math.min(2000, Math.round(raw)))
    : DEFAULT_IMAGE_HEIGHT_PX;
  updateSection(effectiveKey.value, { imageHeightPx: next }, { revisionKind: "design" });
}

function setImageTextGap(value) {
  if (isTextImageFieldLocked("imageTextGap")) return;
  const raw = Number(value);
  const next = Number.isFinite(raw)
    ? Math.max(0, Math.min(80, Math.round(raw)))
    : DEFAULT_IMAGE_TEXT_GAP_PERCENT;
  updateSection(effectiveKey.value, { imageTextGap: next }, { revisionKind: "design" });
}

function setImageBgOpacity(value) {
  if (isTextImageFieldLocked("imageBgOpacity")) return;
  const raw = Number(value);
  const next = Number.isFinite(raw) ? Math.max(0, Math.min(1, raw)) : 0.72;
  updateSection(effectiveKey.value, { imageBgOpacity: next }, { revisionKind: "design" });
}

function setImageBorderRadius(value) {
  if (isTextImageFieldLocked("imageBorderRadius")) return;
  const raw = Number(value);
  const next = Number.isFinite(raw) ? Math.max(0, Math.min(499, Math.round(raw))) : 14;
  updateSection(effectiveKey.value, { imageBorderRadius: next }, { revisionKind: "design" });
}

function setImageBgZoom(value) {
  if (isTextImageFieldLocked("imageBgZoom")) return;
  const raw = Number(value);
  const next = Number.isFinite(raw) ? Math.max(1, Math.min(4, raw)) : 1;
  updateSection(effectiveKey.value, { imageBgZoom: next }, { revisionKind: "design" });
}

function setImageBgFocalX(value) {
  if (isTextImageFieldLocked("imageBgFocalX")) return;
  const raw = Number(value);
  const next = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) : 50;
  updateSection(effectiveKey.value, { imageBgFocalX: next }, { revisionKind: "design" });
}

function setImageBgFocalY(value) {
  if (isTextImageFieldLocked("imageBgFocalY")) return;
  const raw = Number(value);
  const next = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) : 50;
  updateSection(effectiveKey.value, { imageBgFocalY: next }, { revisionKind: "design" });
}

function setImageBgRotation(value) {
  if (isTextImageFieldLocked("imageBgRotation")) return;
  const raw = Number(value);
  const next = Number.isFinite(raw) ? Math.max(-180, Math.min(180, raw)) : 0;
  updateSection(effectiveKey.value, { imageBgRotation: next }, { revisionKind: "design" });
}

function setImageAspectRatio(value) {
  if (isTextImageFieldLocked("imageAspectRatio")) return;
  updateSection(
    effectiveKey.value,
    { imageAspectRatio: normalizeAspectRatio(value) },
    { revisionKind: "design" }
  );
}

function setImageInteraction(value) {
  if (isTextImageFieldLocked("imageInteraction")) return;
  const next = normalizeImageInteraction(value);
  if (next !== "zoom") closeImageLightbox();
  updateSection(
    effectiveKey.value,
    { imageInteraction: next },
    { revisionKind: "design" }
  );
}

function setImageClickUrl(value) {
  if (isTextImageFieldLocked("imageClickUrl")) return;
  updateSection(
    effectiveKey.value,
    { imageClickUrl: String(value || "").trim() },
    { revisionKind: "content" }
  );
}

function openImagePicker() {
  showMediaPicker.value = true;
}

function closeImagePicker() {
  showMediaPicker.value = false;
}

function onMediaSelect(selection) {
  const media = resolveBackendResponsiveImagePayload(selection, {
    urlKeys: ["url", "src", "href"],
  });
  const nextUrl = String(media.url || "").trim();
  setImageUrl(nextUrl, media.responsiveVariants, resolveSelectionImageAuthor(selection));
  closeImagePicker();
}
</script>

<style scoped>
.text-image-section {
  background-color: var(--section-background-color, #ffffff);
}

.text-image-section--background {
  isolation: isolate;
  background-color: transparent;
}

.text-image-section--background::before {
  content: none;
}

.text-image-section--stacked :deep(.section-text-layout__text) {
  text-align: var(--text-image-stacked-text-align, left);
}

.text-image-section--stacked .text-image-section__media-box {
  margin-inline: 0;
}

.text-image-section__media {
  display: flex;
  align-items: center;
  justify-content: center;
  width: min(100%, var(--text-image-wrapper-width, 100%));
  max-width: 100%;
}

.text-image-section__media--side {
  display: flex;
  width: min(100%, var(--text-image-wrapper-width, 100%));
  flex: 0 0 min(100%, var(--text-image-wrapper-width, 100%));
}

.text-image-section__media--side .text-image-section__media-box {
  width: min(100%, var(--text-image-box-width, 100%));
  /* Preserve selected ratio when width gets small. */
  min-height: 0;
}

.text-image-section__media-box {
  display: block;
  position: relative;
  width: min(100%, var(--text-image-box-width, 100%));
  height: var(--text-image-height-px, auto);
  max-height: min(var(--text-image-max-height-vh-cap, 70vh), var(--text-image-height-px-cap, 99999px));
  aspect-ratio: var(--text-image-aspect-ratio, 16 / 9);
  min-height: min(180px, var(--text-image-height-px-cap, 180px));
  overflow: hidden;
  border-radius: var(--text-image-border-radius, 14px);
}

.text-image-section__media-box--no-crop {
  aspect-ratio: auto;
  min-height: 0;
  overflow: visible;
}

.text-image-section__media-link {
  display: block;
  position: relative;
  width: 100%;
  height: 100%;
  color: inherit;
  text-decoration: none;
}

.text-image-section__overlay-frame {
  position: absolute;
  z-index: 4;
  overflow: hidden;
  pointer-events: none;
}

.text-image-section__zoom-button {
  position: absolute;
  left: 50%;
  bottom: 10px;
  z-index: 5;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.92);
  color: #0f172a;
  cursor: pointer;
  opacity: 0.5;
  pointer-events: auto;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.18);
  transform: translateX(-50%);
  transition: background 0.15s ease, opacity 0.15s ease, transform 0.15s ease, height 0.15s ease, width 0.15s ease;
}

.text-image-section__media-box:hover .text-image-section__zoom-button,
.text-image-section__zoom-button:focus-visible {
  opacity: 0.8;
  width: 38px;
  height: 38px;
}

.text-image-section__zoom-button:hover,
.text-image-section__zoom-button:focus-visible {
  background: #fff;
  transform: translateX(-50%) translateY(-1px);
}

.text-image-section__zoom-button:focus-visible {
  outline: 2px solid rgba(79, 70, 229, 0.78);
  outline-offset: 2px;
}

.text-image-author-overlay {
  position: absolute;
  top: 10px;
  right: 28px;
  z-index: 3;
  max-width: min(78%, 360px);
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

.text-image-author-overlay--lightbox {
  top: 14px;
  right: 34px;
  max-width: min(65vw, 540px);
  font-size: 12px;
}

.text-image-section__media-box--no-crop .text-image-section__media-link {
  display: flex;
  justify-content: center;
  align-items: center;
  height: auto;
}

.text-image-section__media--above {
  margin: 0 0 var(--text-image-content-gap, 5%);
  margin-inline: var(--text-image-stacked-margin-inline, 0 auto);
  justify-content: center;
}

.text-image-section__media--below {
  margin: var(--text-image-content-gap, 5%) 0 0;
  margin-inline: var(--text-image-stacked-margin-inline, 0 auto);
  justify-content: center;
}

.text-image-section__media :deep(.editable) {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: var(--text-image-border-radius, 14px);
}

.text-image-section__media :deep(.transformed-image),
.text-image-section__media :deep(.transformed-image__viewport) {
  display: block;
  width: 100%;
  height: 100%;
}

.text-image-section__media :deep(.transformed-image__viewport > img) {
  border-radius: var(--text-image-border-radius, 14px);
}

.text-image-section__media-box--no-crop :deep(.editable) {
  height: auto;
}

.text-image-section__media-box--no-crop :deep(.transformed-image),
.text-image-section__media-box--no-crop :deep(.transformed-image__viewport) {
  display: block;
  width: 100%;
  max-width: 100%;
  height: auto;
  max-height: min(var(--text-image-max-height-vh-cap, 70vh), var(--text-image-height-px-cap, 99999px));
}

.text-image-section__media-box--no-crop :deep(.transformed-image__viewport > img) {
  width: 100%;
  max-width: 100%;
  height: auto;
  object-fit: contain;
  max-height: min(var(--text-image-max-height-vh-cap, 70vh), var(--text-image-height-px-cap, 99999px));
}

.text-image-section__media-empty {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  min-height: 140px;
  color: var(--muted, #64748b);
  background: rgba(255, 255, 255, 0.5);
  border: 1px dashed rgba(148, 163, 184, 0.45);
  border-radius: var(--text-image-border-radius, 14px);
  font-size: 12px;
}

.text-image-lightbox {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.88);
}

.text-image-lightbox__content {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  max-width: 90vw;
  max-height: 85vh;
  overflow: hidden;
  border-radius: 6px;
  user-select: none;
}

.text-image-lightbox__content--svg {
  width: min(90vw, 1440px);
  height: 80vh;
}

.text-image-lightbox__image {
  display: block;
  max-width: 90vw;
  max-height: 80vh;
  object-fit: contain;
  border-radius: 0;
}

.text-image-lightbox__image--svg {
  width: 100%;
  height: 100%;
  max-width: 100%;
  max-height: 100%;
}

.text-image-lightbox__close {
  position: absolute;
  top: 16px;
  right: 20px;
  z-index: 1;
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  cursor: pointer;
  font-size: 18px;
}

.text-image-admin-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: minmax(0, 1fr);
}

.text-image-admin-group {
  display: grid;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--admin-border, #e5e7eb);
  border-radius: 8px;
  background: #fff;
}

.text-image-admin-group-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted, rgba(43, 12, 92, 0.6));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.text-image-admin-group-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.text-image-admin-top-row {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}

.text-image-admin-field {
  display: grid;
  gap: 6px;
  font-size: 13px;
}

.text-image-admin-field span {
  font-weight: 600;
}

.text-image-admin-field select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border, #d1d5db);
  border-radius: 8px;
  background: #fff;
}

.text-image-admin-field input[type="text"] {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border, #d1d5db);
  border-radius: 8px;
  background: #fff;
}

.text-image-admin-range {
  display: flex;
  align-items: center;
  gap: 8px;
}

.text-image-admin-range input[type="range"] {
  flex: 1;
}

.text-image-admin-content {
  display: grid;
  gap: 10px;
}

.text-image-admin-preview-card {
  display: grid;
  gap: 8px;
  border: 1px solid var(--border, #d1d5db);
  border-radius: 10px;
  padding: 10px;
  background: #fff;
}

.text-image-admin-preview-card--background {
  background: linear-gradient(180deg, rgba(148, 163, 184, 0.08), #fff);
}

.text-image-admin-preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.text-image-admin-preview-title {
  font-size: 12px;
  font-weight: 700;
}

.text-image-admin-preview-mode {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted, #64748b);
  background: rgba(148, 163, 184, 0.15);
  border-radius: 499px;
  padding: 2px 7px;
}

@media (min-width: 721px) {
  .text-image-section--side :deep(.section-text-layout) {
  align-items: flex-start;
  gap: var(--text-image-content-gap, 5%);
}
}

@media (max-width: 720px) {
  .text-image-section--side :deep(.section-text-layout) {
    flex-direction: column;
  }

  .text-image-section__media--side {
    width: 100%;
    min-width: 0;
    flex-basis: 100%;
  }
}
</style>
