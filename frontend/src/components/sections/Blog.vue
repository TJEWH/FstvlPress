<template>
  <SectionBase
    :section-key="effectiveKey"
    :section-data="sectionForIntegration"
    :admin-integration-apply-content-patch="applyBlogIntegrationImportPatch"
  >
    <div @mouseenter="hover=true" @mouseleave="hover=false">
      <!-- Filter bar (when enabled) -->
      <div v-if="effectiveFilterEnabled && availableTags.length > 0" class="filter-bar">
        <button
          type="button"
          class="filter-btn"
          :class="{ active: !activeFilter }"
          @click="activeFilter = null"
        >All</button>
        <button
          v-for="tag in availableTags"
          :key="getScopeKey(tag)"
          type="button"
          class="filter-btn"
          :class="{ active: activeFilter && tagMatches(activeFilter, tag) }"
          @click="activeFilter = tag"
        >{{ localizedText(tag) }}</button>
      </div>

      <!-- VIEW -->
      <div
          class="blog-list"
          :class="[
            displayStyleClass,
            imageRatioClass,
            {
              'blog-list--empty': filteredItems.length === 0,
              'blog-list--slidable': slidableOnMobile && displayStyle === 'cards' && !isCappedThreeLayout,
              'blog-list--capped-three': isCappedThreeLayout,
              'blog-list--two-columns': useTwoColumnNonCardLayout
            }
          ]"
          :style="blogListStyle"
      >
        <article
            v-for="(item, index) in filteredItems"
            :key="item.id"
            class="blog"
            :style="[itemStyle, cappedThreeItemStyle]"
        >
          <div class="blog__media">
            <router-link
              v-if="resolveBlogItemImageUrl(item, index) && item.pageSlug && displayStyle === 'cards'"
              :to="toPagePath(item.pageSlug)"
              class="blog__media-link"
              :aria-label="localizedText(item.title)"
              @click.stop
            >
              <TransformedImage
                  :src="resolveBlogItemImageUrl(item, index)"
                  :alt="localizedText(item.title)"
                  class="blog__img blog__img--interactive"
                  :zoom="resolveBlogItemImageZoom(item, index)"
                  :focal-x="resolveBlogItemImageFocalX(item, index)"
                  :focal-y="resolveBlogItemImageFocalY(item, index)"
                  :rotation="resolveBlogItemImageRotation(item, index)"
                  :responsive-variants="resolveBlogItemResponsiveVariants(item, index)"
                  fit="cover"
                  loading="lazy"
                  decoding="async"
              />
            </router-link>
            <TransformedImage
                v-else-if="resolveBlogItemImageUrl(item, index)"
                :src="resolveBlogItemImageUrl(item, index)"
                :alt="localizedText(item.title)"
                class="blog__img"
                :zoom="resolveBlogItemImageZoom(item, index)"
                :focal-x="resolveBlogItemImageFocalX(item, index)"
                :focal-y="resolveBlogItemImageFocalY(item, index)"
                :rotation="resolveBlogItemImageRotation(item, index)"
                :responsive-variants="resolveBlogItemResponsiveVariants(item, index)"
                fit="cover"
                loading="lazy"
                decoding="async"
            />
            <div v-else class="blog__placeholder">No image</div>
            <div v-if="displayStyle === 'cards' && blogItemAuthorOverlay(item)" class="blog__author-overlay">
              {{ blogItemAuthorOverlay(item) }}
            </div>
          </div>
          <div
            class="blog__content"
            :class="{ 'has-separators': showSeparators && displayStyle === 'cards' }"
            :style="separatorStyle"
          >
            <h3 class="blog__title" :style="titleStyle">
              <router-link
                v-if="item.pageSlug"
                :to="toPagePath(item.pageSlug)"
                class="blog__title-link"
                @click.stop
              >
                {{ localizedText(item.title) }}
              </router-link>
              <span v-else>{{ localizedText(item.title) }}</span>
            </h3>
            <div class="blog__meta" :style="metaStyle">
              <span v-if="localizedText(item.tag)" class="blog__tag">{{ localizedText(item.tag) }}</span>
              <span v-if="localizedText(item.tag) && item.date" class="blog__sep">·</span>
              <time v-if="item.date" class="blog__date">{{ formatDate(item.date) }}</time>
            </div>
            <div
              v-if="displayStyle === 'list' && blogTextHtml(item.text)"
              class="blog__text rich-render"
              :style="descStyle"
              v-html="blogTextHtml(item.text)"
            ></div>
            <router-link
              v-if="item.pageSlug && displayStyle !== 'cards'"
              :to="toPagePath(item.pageSlug)"
              class="blog__read-more"
              :style="readMoreStyle"
              @click.stop
            >
              {{ t.readMore }}
            </router-link>
          </div>
        </article>

        <p v-if="filteredItems.length === 0" class="p empty-hint">
          {{ t.noItems }} {{ state.isAdmin ? t.clickToAdd : '' }}
        </p>
      </div>
    </div>

    <template #admin-design-params>
      <div class="blog-design-controls">
        <div class="admin-controls-row blog-design-row">
          <div v-if="!isOnTargetRoute" class="ctrl-item">
            <span class="ctrl-label">{{ t.displayCount }}</span>
            <div class="limit-toggle">
              <input
                :value="limitInput"
                type="number"
                min="1"
                step="1"
                class="field ctrl-input limit-input"
                placeholder="n"
                @change="onLimitInputChange($event)"
              />
              <button type="button" class="limit-btn" :class="{ active: !hasLimit }" @click="setLimit(null)">{{ t.limitAll }}</button>
            </div>
          </div>
          <div v-if="!hasLimit" class="ctrl-item">
            <span class="ctrl-label">Filter</span>
            <select
              v-model="filterEnabled"
              class="field ctrl-select"
              @change="saveFilterEnabled"
            >
              <option :value="false">Disabled</option>
              <option :value="true">Enabled</option>
            </select>
          </div>
          <div class="ctrl-item">
            <span class="ctrl-label">Display</span>
            <select v-model="displayStyle" class="field ctrl-select" @change="saveDisplayStyle">
              <option value="list">List</option>
              <option value="cards">Cards</option>
              <option value="compact">Compact</option>
            </select>
          </div>
          <label v-if="displayStyle === 'compact' || (displayStyle !== 'cards' && !hasLimit)" class="ctrl checkbox-ctrl">
            <input type="checkbox" v-model="twoColumnNonCards" @change="saveTwoColumnNonCards" />
            <span class="ctrl-label">2 Columns</span>
          </label>
          <label v-if="displayStyle === 'cards'" class="ctrl checkbox-ctrl">
            <input type="checkbox" v-model="showSeparators" @change="saveSeparators" />
            <span class="ctrl-label">Separators</span>
          </label>
          <label v-if="displayStyle === 'cards'" class="ctrl checkbox-ctrl">
            <input type="checkbox" v-model="slidableOnMobile" @change="saveSlidable" />
            <span class="ctrl-label">Slidable (Mobile)</span>
          </label>
        </div>
        <div class="admin-controls-row blog-design-row blog-design-row--independent">
          <div class="ctrl ctrl-item">
            <span class="ctrl-label">Ratio</span>
            <select v-model="imageRatio" class="field ctrl-select" @change="saveImageRatio">
              <option value="1:1">1:1</option>
              <option value="16:9">16:9</option>
              <option value="2:3">2:3</option>
            </select>
          </div>
        </div>
      </div>
    </template>

    <template #admin-design-colors>
      <div class="admin-controls-row color-controls-row">
            <div class="ctrl color-link-control">
              <span class="ctrl-label">Item Background</span>
              <VueColorPicker
                :model-value="hexOrDefault(itemBgColor, '#ffffff')"
                fallback-color="#ffffff"
                :preview-style="swatchStyle(resolvedItemBgColor, { rawColor: itemBgColor, linkKey: itemBgColorLink, treatEmptyAsHighContrast: true, baseRefColor: state.design.sectionBackgroundColor || '#ffffff', baseRefKey: 'sectionBackgroundColor', adminConfig: state.adminDesignConfig })"
                :size="28"
                @update:model-value="setItemBgColor($event)"
              />
              <ColorLinkPicker :model-value="itemBgColorLink" :options="itemBgColorOptions" @link="applyColorLink('itemBg', $event)" />
              <select
                class="variation-select"
                :value="itemBgColorVariation"
                @change="setColorVariation('itemBg', $event.target.value)"
              >
                <option v-for="variation in colorVariationOptions" :key="`item-bg-${variation}`" :value="variation">
                  {{ variation }}%
                </option>
              </select>
              <button v-if="itemBgColor" class="clear-btn" type="button" title="Clear" @click="setItemBgColor(null)">&times;</button>
            </div>
            <div class="ctrl color-link-control">
              <span class="ctrl-label">Title</span>
              <VueColorPicker
                :model-value="hexOrDefault(titleColor, '#0f172a')"
                fallback-color="#0f172a"
                :preview-style="swatchStyle(resolveTextColor(titleColor, titleColorVariation), { rawColor: titleColor, linkKey: titleColorLink, treatEmptyAsHighContrast: true, baseRefColor: textContrastBaseRefColor, baseRefKey: itemBgColorLink || null, adminConfig: state.adminDesignConfig })"
                :size="28"
                @update:model-value="setTitleColor($event)"
              />
              <ColorLinkPicker :model-value="titleColorLink" :options="textColorOptions" @link="applyColorLink('title', $event)" />
              <select
                class="variation-select"
                :value="titleColorVariation"
                @change="setColorVariation('title', $event.target.value)"
              >
                <option v-for="variation in colorVariationOptions" :key="`title-${variation}`" :value="variation">
                  {{ variation }}%
                </option>
              </select>
              <button v-if="titleColor" class="clear-btn" type="button" title="Clear" @click="setTitleColor(null)">&times;</button>
            </div>
            <div class="ctrl color-link-control">
              <span class="ctrl-label">Description</span>
              <VueColorPicker
                :model-value="hexOrDefault(descColor, '#64748b')"
                fallback-color="#64748b"
                :preview-style="swatchStyle(resolveTextColor(descColor, descColorVariation), { rawColor: descColor, linkKey: descColorLink, treatEmptyAsHighContrast: true, baseRefColor: textContrastBaseRefColor, baseRefKey: itemBgColorLink || null, adminConfig: state.adminDesignConfig })"
                :size="28"
                @update:model-value="setDescColor($event)"
              />
              <ColorLinkPicker :model-value="descColorLink" :options="textColorOptions" @link="applyColorLink('desc', $event)" />
              <select
                class="variation-select"
                :value="descColorVariation"
                @change="setColorVariation('desc', $event.target.value)"
              >
                <option v-for="variation in colorVariationOptions" :key="`desc-${variation}`" :value="variation">
                  {{ variation }}%
                </option>
              </select>
              <button v-if="descColor" class="clear-btn" type="button" title="Clear" @click="setDescColor(null)">&times;</button>
            </div>
            <div class="ctrl color-link-control">
              <span class="ctrl-label">Meta</span>
              <VueColorPicker
                :model-value="hexOrDefault(metaColor, '#4f46e5')"
                fallback-color="#4f46e5"
                :preview-style="swatchStyle(resolveTextColor(metaColor, metaColorVariation), { rawColor: metaColor, linkKey: metaColorLink, treatEmptyAsHighContrast: true, baseRefColor: textContrastBaseRefColor, baseRefKey: itemBgColorLink || null, adminConfig: state.adminDesignConfig })"
                :size="28"
                @update:model-value="setMetaColor($event)"
              />
              <ColorLinkPicker :model-value="metaColorLink" :options="textColorOptions" @link="applyColorLink('meta', $event)" />
              <select
                class="variation-select"
                :value="metaColorVariation"
                @change="setColorVariation('meta', $event.target.value)"
              >
                <option v-for="variation in colorVariationOptions" :key="`meta-${variation}`" :value="variation">
                  {{ variation }}%
                </option>
              </select>
              <button v-if="metaColor" class="clear-btn" type="button" title="Clear" @click="setMetaColor(null)">&times;</button>
            </div>
            <div class="ctrl color-link-control">
              <span class="ctrl-label">Read More</span>
              <VueColorPicker
                :model-value="hexOrDefault(readMoreColor, '#4f46e5')"
                fallback-color="#4f46e5"
                :preview-style="swatchStyle(resolveTextColor(readMoreColor, readMoreColorVariation), { rawColor: readMoreColor, linkKey: readMoreColorLink, treatEmptyAsHighContrast: true, baseRefColor: textContrastBaseRefColor, baseRefKey: itemBgColorLink || null, adminConfig: state.adminDesignConfig })"
                :size="28"
                @update:model-value="setReadMoreColor($event)"
              />
              <ColorLinkPicker :model-value="readMoreColorLink" :options="textColorOptions" @link="applyColorLink('readMore', $event)" />
              <select
                class="variation-select"
                :value="readMoreColorVariation"
                @change="setColorVariation('readMore', $event.target.value)"
              >
                <option v-for="variation in colorVariationOptions" :key="`read-more-${variation}`" :value="variation">
                  {{ variation }}%
                </option>
              </select>
              <button v-if="readMoreColor" class="clear-btn" type="button" title="Clear" @click="setReadMoreColor(null)">&times;</button>
            </div>
            <div v-if="displayStyle === 'cards' && showSeparators" class="ctrl color-link-control">
              <span class="ctrl-label">Separator</span>
              <VueColorPicker
                :model-value="hexOrDefault(separatorColor, '#4f46e5')"
                fallback-color="#4f46e5"
                :preview-style="swatchStyle(resolveTextColor(separatorColor, separatorColorVariation), { rawColor: separatorColor, linkKey: separatorColorLink, treatEmptyAsHighContrast: true, baseRefColor: textContrastBaseRefColor, baseRefKey: itemBgColorLink || null, adminConfig: state.adminDesignConfig })"
                :size="28"
                @update:model-value="setSeparatorColor($event)"
              />
              <ColorLinkPicker :model-value="separatorColorLink" :options="separatorColorOptions" @link="applyColorLink('separator', $event)" />
              <select
                class="variation-select"
                :value="separatorColorVariation"
                @change="setColorVariation('separator', $event.target.value)"
              >
                <option v-for="variation in colorVariationOptions" :key="`separator-${variation}`" :value="variation">
                  {{ variation }}%
                </option>
              </select>
              <button v-if="separatorColor" class="clear-btn" type="button" title="Clear" @click="setSeparatorColor(null)">&times;</button>
            </div>
      </div>
    </template>

    <template #admin-content>
      <MediaLibrary
            v-if="editing"
            :is-open="showMediaPicker"
            :current-url="''"
            source-context="section.blog.item_image"
            @close="closeMediaPicker"
            @select="onMediaSelect"
      />

      <div v-if="editing" class="editor">
        <TopicSelector
          v-model:topics="draftTags"
          mode="catalog"
          title="Blog Topics"
          @save-catalog="saveBlogTopicCatalog"
        />

        <SectionListEditor
          :items="draft"
          :selected-index="expandedItem"
          :add-label="t.add"
          :save-label="t.save"
          :remove-label="t.remove"
          :save-disabled="saving"
          :remove-disabled="saving"
          :save-on-reorder="false"
          @select="expandedItem = $event"
          @add="addItem"
          @save="save"
          @remove="removeItem"
          @reorder="reorderItems"
        >
          <template #item="{ item, index }">
            <div class="item-thumb item-thumb--media">
              <div
                class="thumb-img-wrap"
                :style="blogEditorThumbStyle"
                title="Click to browse images"
              >
                <TransformedImage
                  v-if="item.imageUrl"
                  :src="item.imageUrl"
                  alt=""
                  class="thumb-img"
                  :ratio="imageRatio"
                  direction="landscape"
                  :zoom="normalizeImageZoom(item.imageZoom)"
                  :focal-x="normalizeImageFocal(item.imageFocalX)"
                  :focal-y="normalizeImageFocal(item.imageFocalY)"
                  :rotation="normalizeImageRotation(item.imageRotation)"
                  :responsive-variants="item.responsiveVariants"
                  fit="cover"
                  loading="lazy"
                  decoding="async"
                />
                <div v-else class="thumb-empty">+</div>
              </div>
              <span class="thumb-label">{{ item.title.de || item.title.en || `#${index + 1}` }}</span>
              <span v-if="item.date" class="thumb-date">{{ item.date }}</span>
            </div>
          </template>

          <template #editor="{ item, index }">
              <ImageTransformEditor
                :image-url="item.imageUrl || ''"
                :zoom="item.imageZoom ?? 1"
                :focal-x="item.imageFocalX ?? 50"
                :focal-y="item.imageFocalY ?? 50"
                :rotation="item.imageRotation ?? 0"
                :ratio="imageRatio"
                view-context="section_item"
                :image-url-disabled="isBlogItemFieldLocked(index, 'imageUrl')"
                :zoom-disabled="isBlogItemFieldLocked(index, 'imageZoom')"
                :focal-disabled="isBlogItemFieldLocked(index, 'imageFocalX') || isBlogItemFieldLocked(index, 'imageFocalY')"
                :rotation-disabled="isBlogItemFieldLocked(index, 'imageRotation')"
                @update:image-url="(value) => setItemImageUrl(index, value)"
                @update:zoom="(value) => setItemImageZoom(index, value)"
                @update:focal-x="(value) => setItemImageFocalX(index, value)"
                @update:focal-y="(value) => setItemImageFocalY(index, value)"
                @update:rotation="(value) => setItemImageRotation(index, value)"
                @choose-image="openMediaPicker(index, { direct: false })"
                @clear-image="clearItemImage(index)"
              />

              <div class="blog-meta-edit-row">
                <TopicSelector
                  mode="field"
                  :topics="draftTags"
                  :model-value="item.tag"
                  :label="t.tag"
                  :disabled="isBlogItemFieldLocked(index, 'tag', { includeDescendants: true })"
                  :disabled-title="isBlogItemFieldLocked(index, 'tag', { includeDescendants: true }) ? integrationLockedHint : ''"
                  @update:model-value="(tag) => setItemTag(index, tag)"
                />
                <div class="field-row">
                  <label class="field-label">
                    {{ t.date }}
                  </label>
                  <VueDatePicker
                    :model-value="serverDateOnlyToLocalDate(item.date)"
                    class="section-date-picker"
                    :enable-time-picker="false"
                    :clearable="true"
                    :text-input="DATE_PICKER_DATE_ONLY_TEXT_INPUT_OPTIONS"
                    :formats="DATE_PICKER_DATE_ONLY_DISPLAY_FORMATS"
                    :teleport="true"
                    auto-apply
                    placeholder="Select date"
                    :disabled="isBlogItemFieldLocked(index, 'date')"
                    :title="isBlogItemFieldLocked(index, 'date') ? integrationLockedHint : undefined"
                    @update:model-value="item.date = localDateToServerDateOnly($event)"
                  />
                </div>
              </div>

              <div class="lang-section">
                <div class="lang-header">
                  {{ t.german }} (DE)
                </div>
                <input
                  v-model="item.title.de"
                  class="field"
                  :placeholder="t.title + ' (DE)'"
                  :disabled="isBlogItemFieldLocked(index, 'title.de')"
                  :title="isBlogItemFieldLocked(index, 'title.de') ? integrationLockedHint : undefined"
                />
                <div class="field-rich">
                  <QuillEditor
                    v-model:content="item.text.de"
                    content-type="html"
                    theme="snow"
                    :toolbar="blogTextToolbar"
                    :placeholder="t.text + ' (DE)'"
                    :read-only="isBlogItemFieldLocked(index, 'text.de')"
                  />
                </div>
              </div>
              <div class="lang-section">
                <div class="lang-header">
                  {{ t.english }} (EN)
                </div>
                <input
                  v-model="item.title.en"
                  class="field"
                  :placeholder="t.title + ' (EN)'"
                  :disabled="isBlogItemFieldLocked(index, 'title.en')"
                  :title="isBlogItemFieldLocked(index, 'title.en') ? integrationLockedHint : undefined"
                />
                <div class="field-rich">
                  <QuillEditor
                    v-model:content="item.text.en"
                    content-type="html"
                    theme="snow"
                    :toolbar="blogTextToolbar"
                    :placeholder="t.text + ' (EN)'"
                    :read-only="isBlogItemFieldLocked(index, 'text.en')"
                  />
                </div>
              </div>

              <div v-if="!hasBlogPublicSlugTitle(item)" class="item-page-title-info">
                Public item-page slug is finalized on first publish. Set a title before publishing.
              </div>
          </template>
          <template #footer-actions="{ item }">
            <div class="item-field-actions">
              <button
                class="btn-secondary small"
                type="button"
                :disabled="!item.pageSlug"
                @click.stop="openBlogItemPage(item)"
              >
                Open Item Page
              </button>
              <button
                v-if="showBlogItemRegenerateButton(item)"
                class="btn-secondary small"
                type="button"
                :disabled="isBlogItemTemplateRegenerationBusy(item) || isBlogItemPageGenerationPending(item)"
                @click.stop="regenerateBlogItemPage(item)"
              >
                {{ isBlogItemTemplateRegenerationBusy(item) ? "Regenerating..." : "Regenerate Item Page" }}
              </button>
              <span v-if="isBlogItemPageGenerationPending(item)" class="field-hint">
                Item page is being generated. The open button will activate automatically.
              </span>
              <span v-else-if="blogItemPageGenerationError(item)" class="field-hint field-hint--error">
                {{ blogItemPageGenerationError(item) }}
              </span>
            </div>
          </template>
        </SectionListEditor>
      </div>
    </template>

  </SectionBase>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from "vue";
import DOMPurify from "dompurify";
import { useRoute } from "vue-router";
import { useStore } from "../../store/store.js";
import * as api from "../../services/api.js";
import { useListEditorMediaPicker } from "../../composables/useListEditorMediaPicker.js";
import {
  buildColorLinkOptions,
  isBaseColorLinkKey,
  resolveLinkedColor,
  HIGH_CONTRAST_TOKEN,
  resolveHighContrastColorForBackground,
} from "../../utils/colorLinkOptions.js";
import {
  COLOR_VARIATION_OPTIONS,
  DEFAULT_COLOR_VARIATION,
  applyColorVariation,
  normalizeColorVariation,
} from "../../utils/colorVariations.js";
import { ratioToCss } from "../../utils/imageTransform.js";
import {
  resolveBackendResponsiveImagePayload,
} from "../../utils/responsiveImages.js";
import { resolveFallbackImageForIndex } from "../../utils/fallbackImages.js";
import {
  DATE_PICKER_DATE_ONLY_DISPLAY_FORMATS,
  DATE_PICKER_DATE_ONLY_TEXT_INPUT_OPTIONS,
  formatServerDateOnly,
  getCurrentServerDateISO,
  localDateToServerDateOnly,
  serverDateOnlyToLocalDate,
} from "../../utils/revisionTime.js";
import { isSectionIntegrationFieldLocked } from "../../utils/sectionIntegrationFieldState.js";
import { convertKeysToCamel } from "../../utils/caseConversion.js";
import {
  getTagKey,
  hasTagValue,
  normalizeTag,
  tagMatches,
  uniqueTags,
} from "../../utils/topics.js";
import { QuillEditor } from "@vueup/vue-quill";
import "@vueup/vue-quill/dist/vue-quill.snow.css";
import { VueDatePicker } from "@vuepic/vue-datepicker";
import "@vuepic/vue-datepicker/dist/main.css";

import SectionBase from "./_BaseSection.vue";
import { getBaseSectionSwatchStyle } from "./_baseSectionSwatchStyle.js";
import SectionListEditor from "../admin/section-editor/SectionListEditor.vue";
import TopicSelector from "../admin/section-editor/TopicSelector.vue";
import ColorLinkPicker from "../ui/color/ColorLinkPicker.vue";
import VueColorPicker from "../ui/color/VueColorPicker.vue";
import MediaLibrary from "../ui/MediaLibrary.vue";
import ImageTransformEditor from "../ui/ImageTransformEditor.vue";
import TransformedImage from "../ui/TransformedImage.vue";

const props = defineProps({
  sectionKey: { type: String, default: 'blog' },
  sectionData: { type: Object, default: null }
});

const { state, t, localizedText, updateSection, updateSectionLimit, fetchBlogData } = useStore();
const route = useRoute();
const integrationLockedHint = "Managed by integration import.";

const effectiveKey = computed(() => props.sectionKey);
const currentAdminTab = computed(() => state.sectionAdminActiveTabs?.[effectiveKey.value] || "");

const section = computed(() => {
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});
const sectionForIntegration = computed(() => {
  const base = section.value && typeof section.value === "object"
    ? { ...section.value }
    : {};
  base.blogItems = Array.isArray(state.blogItems) ? state.blogItems : [];
  return base;
});
function blogFieldPath(index, fieldPath) {
  const normalizedFieldPath = String(fieldPath || "").trim();
  const numericIndex = Number(index);
  const resolvedIndex = Number.isInteger(numericIndex) && numericIndex >= 0 ? numericIndex : 0;
  return normalizedFieldPath
    ? `blogItems[${resolvedIndex}].${normalizedFieldPath}`
    : `blogItems[${resolvedIndex}]`;
}

function isBlogItemFieldLocked(index, fieldPath, options = {}) {
  if (!state.isAdmin) return false;
  const normalizedFieldPath = String(fieldPath || "").trim();
  const numericIndex = Number(index);
  const resolvedIndex = Number.isInteger(numericIndex) && numericIndex >= 0 ? numericIndex : 0;
  const fallbackPath = normalizedFieldPath
    ? `items[${resolvedIndex}].${normalizedFieldPath}`
    : `items[${resolvedIndex}]`;
  return (
    isSectionIntegrationFieldLocked(sectionForIntegration.value, blogFieldPath(index, fieldPath), options)
    || isSectionIntegrationFieldLocked(sectionForIntegration.value, fallbackPath, options)
  );
}

function scopeMatches(itemTag, sectionScope) {
  if (!hasTagValue(sectionScope)) return true;
  return tagMatches(itemTag, sectionScope);
}

const allItems = computed(() => {
  let items = state.blogItems || [];
  const access = section.value?.access || "public";
  if (access === "admin") {
    const scope = section.value?.scope;
    if (scope && (scope.de || scope.en)) {
      items = items.filter((it) => scopeMatches(it.tag, scope));
    }
  }
  // Order comes from the server (sort_order field). No client-side sort.
  return [...items];
});

function normalizeLimitValue(value) {
  if (value == null) return null;
  if (typeof value === "number") {
    return Number.isInteger(value) && value > 0 ? value : null;
  }
  const raw = String(value).trim();
  if (!raw) return null;
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed <= 0) return null;
  return parsed;
}

const limit = computed(() => {
  return normalizeLimitValue(section.value?.limit);
});

const hasLimit = computed(() => limit.value != null);

const visibleItems = computed(() => {
  const items = allItems.value;
  const n = limit.value;
  if (n == null) return items;
  return items.slice(0, n);
});

const isCapped = computed(() => limit.value != null && allItems.value.length > limit.value);

const filterEnabled = ref(false);
const displayStyle = ref('list');
const twoColumnNonCards = ref(false);
const activeFilter = ref(null);
const limitInput = ref("");
const defaultShowMoreButtonText = Object.freeze({ de: "Mehr anzeigen", en: "Show more" });
const articleParentRoute = ref("");
const itemPagesBusy = ref(false);
const itemPagesStatus = ref({ type: "", message: "" });
const blogItemTemplateInfo = ref(null);
const blogItemPageJobs = ref({});
const blogItemTemplateRegenerationBusy = ref({});
const blogItemPagePollTimers = new Map();
let blogItemSaveQueue = Promise.resolve();
let blogItemSaveRequestId = 0;
const BLOG_ITEM_JOB_POLL_INTERVAL_MS = 1200;
const BLOG_ITEM_JOB_POLL_MAX_ATTEMPTS = 90;
const BLOG_AUTO_SHOW_ALL_CTA_FLAG = "__autoBlogShowAllCta";
const blogShowAllCtaSyncInFlight = ref(false);

function normalizeItemPageSubroutePath(value) {
  const raw = String(value || "").trim();
  if (!raw || raw === "/") return "";
  const normalized = raw.replace(/^\/+|\/+$/g, "");
  return normalized ? `/${normalized}` : "";
}

function composeEffectiveItemRoute(parentRoute, subroute = "") {
  const parent = normalizeArticleParentRoutePath(parentRoute);
  if (!parent) return "";
  const child = normalizeItemPageSubroutePath(subroute);
  return child ? `${parent}${child}` : parent;
}

async function loadBlogItemTemplateInfo() {
  try {
    const config = await api.getGlobalItemPageConfig();
    const path = String(config?.blog_item_template_path || "").trim();
    if (!path) {
      blogItemTemplateInfo.value = null;
      articleParentRoute.value = "";
      return;
    }
    const template = await api.getPageTemplate(path);
    const parentRoute = normalizeArticleParentRoutePath(template?.parent_route || "");
    const effectiveRoute = composeEffectiveItemRoute(parentRoute, template?.item_page_subroute || "");
    blogItemTemplateInfo.value = {
      path: String(template?.path || path).trim(),
      parentRoute,
      effectiveRoute,
    };
    articleParentRoute.value = parentRoute;
  } catch (err) {
    console.error("Failed to load blog item template info:", err);
    blogItemTemplateInfo.value = null;
  }
}

function normalizeBilingualText(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return {
      de: String(value.de ?? ""),
      en: String(value.en ?? ""),
    };
  }
  if (typeof value === "string") {
    return { de: value, en: value };
  }
  return { de: "", en: "" };
}

function normalizeShowMoreButtonText(value) {
  const source = normalizeBilingualText(value);
  return {
    de: String(source.de ?? "").trim() || defaultShowMoreButtonText.de,
    en: String(source.en ?? "").trim() || defaultShowMoreButtonText.en,
  };
}


const availableTags = computed(() => {
  const tags = [];
  const seen = new Set();
  for (const item of allItems.value) {
    if (item.tag && (item.tag.de || item.tag.en)) {
      const key = getScopeKey(item.tag);
      if (!seen.has(key)) {
        seen.add(key);
        tags.push(item.tag);
      }
    }
  }
  return tags;
});

const effectiveFilterEnabled = computed(() => filterEnabled.value && !hasLimit.value);

const filteredItems = computed(() => {
  let items = visibleItems.value;
  if (effectiveFilterEnabled.value && activeFilter.value) {
    items = items.filter(item => tagMatches(item.tag, activeFilter.value));
  }
  return items;
});

const isCappedThreeLayout = computed(() =>
  displayStyle.value === 'cards' && limit.value === 3 && filteredItems.value.length === 3
);

const useTwoColumnNonCardLayout = computed(() =>
  displayStyle.value !== 'cards' && twoColumnNonCards.value && (
    displayStyle.value === 'compact' || !hasLimit.value
  )
);

const blogListStyle = computed(() => {
  const style = {
    '--blog-accent-color': state.design.accentColor || '#4f46e5',
    '--blog-muted-color': state.design.secondaryColor || '#64748b',
  };
  if (!isCappedThreeLayout.value) return style;
  return {
    ...style,
    display: 'flex',
    flexWrap: 'wrap',
    gap: '24px',
    gridTemplateColumns: 'none',
  };
});

const displayStyleClass = computed(() => `blog-list--${displayStyle.value}`);

const effectiveTargetRoute = computed(() => {
  const r = String(articleParentRoute.value || '').trim();
  return r && r !== '/' ? r : '';
});

const isOnTargetRoute = computed(() => {
  const current = route.path;
  const target = effectiveTargetRoute.value;
  if (!target) return false;
  return current === target || current === target + '/';
});

const shouldIncludeAutoShowAllCta = computed(() =>
  Boolean(isCapped.value && effectiveTargetRoute.value && !isOnTargetRoute.value)
);

function normalizeBlogCtaButtonType(value, index = 0) {
  const normalized = String(value || "").trim();
  if (normalized) return normalized;
  return index === 0 ? "primary" : "secondary";
}

function normalizeBlogCtaButton(value, index = 0) {
  const source = value && typeof value === "object" ? value : {};
  const normalized = {
    text: normalizeBilingualText(source.text),
    url: String(source.url || "").trim(),
    buttonType: normalizeBlogCtaButtonType(source.buttonType, index),
  };
  if (source[BLOG_AUTO_SHOW_ALL_CTA_FLAG] === true) {
    normalized[BLOG_AUTO_SHOW_ALL_CTA_FLAG] = true;
  }
  return normalized;
}

function normalizeBlogCtaButtons(value) {
  if (!Array.isArray(value)) return [];
  return value.map((entry, index) => normalizeBlogCtaButton(entry, index));
}

function comparableBlogCtaButton(value, index = 0) {
  const normalized = normalizeBlogCtaButton(value, index);
  return {
    text: {
      de: String(normalized.text.de || "").trim(),
      en: String(normalized.text.en || "").trim(),
    },
    url: String(normalized.url || "").trim(),
    buttonType: normalizeBlogCtaButtonType(normalized.buttonType, index),
  };
}

function isSameComparableBlogCtaButton(a, b) {
  return a.text.de === b.text.de
    && a.text.en === b.text.en
    && a.url === b.url
    && a.buttonType === b.buttonType;
}

function buildBlogShowAllCtaButton(index = 0) {
  const configuredType = String(section.value?.showMoreButtonType || "").trim();
  return normalizeBlogCtaButton(
    {
      text: normalizeShowMoreButtonText(section.value?.showMoreButtonText),
      url: effectiveTargetRoute.value,
      buttonType: configuredType || "primary",
      [BLOG_AUTO_SHOW_ALL_CTA_FLAG]: true,
    },
    index
  );
}

function toPersistedBlogCtaButtons(buttons) {
  return buttons.map((entry, index) => {
    const normalized = normalizeBlogCtaButton(entry, index);
    const output = {
      text: normalizeBilingualText(normalized.text),
      url: String(normalized.url || ""),
      buttonType: normalizeBlogCtaButtonType(normalized.buttonType, index),
    };
    if (normalized[BLOG_AUTO_SHOW_ALL_CTA_FLAG] === true) {
      output[BLOG_AUTO_SHOW_ALL_CTA_FLAG] = true;
    }
    return output;
  });
}

function findBlogAutoShowAllCtaIndex(buttons, comparablePrefill) {
  const markedIndex = buttons.findIndex((entry) => entry?.[BLOG_AUTO_SHOW_ALL_CTA_FLAG] === true);
  if (markedIndex >= 0) return markedIndex;
  return buttons.findIndex((entry, index) =>
    isSameComparableBlogCtaButton(comparableBlogCtaButton(entry, index), comparablePrefill)
  );
}

function syncBlogShowAllCtaButton() {
  if (blogShowAllCtaSyncInFlight.value) return;
  if (!section.value || typeof section.value !== "object") return;

  const currentButtons = normalizeBlogCtaButtons(section.value?.ctaButtons);
  const prefillButton = buildBlogShowAllCtaButton(currentButtons.length);
  const comparablePrefill = comparableBlogCtaButton(prefillButton, currentButtons.length);
  const hasTargetRoute = Boolean(comparablePrefill.url);
  const shouldInclude = shouldIncludeAutoShowAllCta.value && hasTargetRoute;
  const autoIndex = hasTargetRoute
    ? findBlogAutoShowAllCtaIndex(currentButtons, comparablePrefill)
    : -1;

  let nextButtons = currentButtons;
  let changed = false;

  if (shouldInclude) {
    if (autoIndex < 0) {
      nextButtons = [...currentButtons, prefillButton];
      changed = true;
    } else {
      const existing = currentButtons[autoIndex];
      const comparableExisting = comparableBlogCtaButton(existing, autoIndex);
      if (
        existing?.[BLOG_AUTO_SHOW_ALL_CTA_FLAG] !== true
        && isSameComparableBlogCtaButton(comparableExisting, comparablePrefill)
      ) {
        nextButtons = [...currentButtons];
        nextButtons[autoIndex] = {
          ...normalizeBlogCtaButton(existing, autoIndex),
          [BLOG_AUTO_SHOW_ALL_CTA_FLAG]: true,
        };
        changed = true;
      }
    }
  } else if (autoIndex >= 0) {
    const existing = currentButtons[autoIndex];
    const comparableExisting = comparableBlogCtaButton(existing, autoIndex);
    if (
      existing?.[BLOG_AUTO_SHOW_ALL_CTA_FLAG] === true
      || isSameComparableBlogCtaButton(comparableExisting, comparablePrefill)
    ) {
      nextButtons = currentButtons.filter((_, index) => index !== autoIndex);
      changed = true;
    }
  }

  if (!changed) return;

  blogShowAllCtaSyncInFlight.value = true;
  try {
    updateSection(
      effectiveKey.value,
      { ctaButtons: toPersistedBlogCtaButtons(nextButtons) },
      { revisionKind: "content" }
    );
  } finally {
    blogShowAllCtaSyncInFlight.value = false;
  }
}

const hover = ref(false);
const editing = ref(false);
const expandedItem = ref(-1);
const draft = ref([]);
const draftTags = ref([]);
const {
  showMediaPicker,
  openMediaPicker,
  closeMediaPicker,
  consumeMediaPickerSelectionContext,
} = useListEditorMediaPicker();
const saving = ref(false);

const blogTextToolbar = [
  ["bold", "italic", "underline"],
  [{ list: "ordered" }, { list: "bullet" }],
  ["link"],
  ["clean"],
];

watch(section, (s) => {
  filterEnabled.value = s?.filterEnabled ?? false;
  displayStyle.value = s?.displayStyle || "list";
  twoColumnNonCards.value = s?.twoColumnNonCards ?? false;
  if (!blogItemTemplateInfo.value?.parentRoute) {
    articleParentRoute.value = normalizeArticleParentRoutePath(s?.itemParentRoute || "");
  }
}, { immediate: true });

watch(
  () => limit.value,
  (nextLimit) => {
    limitInput.value = nextLimit == null ? "" : String(nextLimit);
    if (nextLimit == null) return;
    activeFilter.value = null;
    if (filterEnabled.value === false) return;
    filterEnabled.value = false;
    if (section.value?.filterEnabled === false) return;
    updateSection(effectiveKey.value, { filterEnabled: false });
  },
  { immediate: true }
);

watch(
  () => effectiveFilterEnabled.value,
  (enabled) => {
    if (!enabled) activeFilter.value = null;
  },
  { immediate: true }
);

watch(
  [
    () => section.value?.ctaButtons,
    () => section.value?.showMoreButtonText,
    () => section.value?.showMoreButtonType,
    () => shouldIncludeAutoShowAllCta.value,
    () => effectiveTargetRoute.value,
    () => isOnTargetRoute.value,
  ],
  () => {
    syncBlogShowAllCtaButton();
  },
  { immediate: true, deep: true }
);

function getScopeKey(tag) {
  return getTagKey(tag);
}

function todayISO() {
  return getCurrentServerDateISO();
}

watch(() => state.isAdmin, (val) => {
  if (!val && editing.value) editing.value = false;
});

watch(currentAdminTab, (tab) => {
  if (!state.isAdmin) return;
  if (tab === 'content') {
    startEdit();
    void loadBlogItemTemplateInfo();
  }
  else editing.value = false;
}, { immediate: true });

watch(
  () => JSON.stringify(state.blogItems || []),
  () => {
    if (!state.isAdmin) return;
    if (currentAdminTab.value !== "content") return;
    if (saving.value) return;
    const prevExpanded = expandedItem.value;
    startEdit();
    if (prevExpanded >= 0 && prevExpanded < draft.value.length) {
      expandedItem.value = prevExpanded;
    }
  }
);

function formatDate(isoStr) {
  return formatServerDateOnly(
    isoStr,
    { day: "2-digit", month: "2-digit", year: "numeric" },
    { fallback: isoStr }
  );
}

function toPagePath(slug) {
  const normalized = (slug || '').trim().replace(/^\/+/, '');
  return normalized ? `/${normalized}` : '/';
}

function isLikelyHtml(value) {
  return /<\/?[a-z][\s\S]*>/i.test(String(value ?? ""));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function toSafeHtml(value) {
  const raw = String(value ?? "");
  if (!raw.trim()) return "";
  const html = isLikelyHtml(raw) ? raw : escapeHtml(raw).replace(/\n/g, "<br>");
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
}

function blogTextHtml(value) {
  return toSafeHtml(localizedText(value));
}

function normalizeEditorContent(value) {
  const html = String(value ?? "");
  const textOnly = html
    .replace(/<[^>]*>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/\u00a0/g, " ")
    .trim();
  return textOnly ? html : "";
}

function openBlogItemPage(item) {
  const slug = String(item?.pageSlug || "").trim();
  if (!slug) return;
  if (typeof window === "undefined") return;
  window.open(toPagePath(slug), "_blank", "noopener,noreferrer");
}

function resolveBlogSectionId() {
  return String(
    state.sectionIds?.[effectiveKey.value]
    || section.value?._id
    || section.value?.id
    || ""
  ).trim();
}

function setBlogItemTemplateRegenerationBusy(itemId, isBusy) {
  const normalizedId = String(itemId || "").trim();
  if (!normalizedId) return;
  const next = { ...(blogItemTemplateRegenerationBusy.value || {}) };
  if (isBusy) {
    next[normalizedId] = true;
  } else {
    delete next[normalizedId];
  }
  blogItemTemplateRegenerationBusy.value = next;
}

function isBlogItemTemplateRegenerationBusy(item) {
  const itemId = String(item?.id || "").trim();
  if (!itemId) return false;
  return Boolean(blogItemTemplateRegenerationBusy.value[itemId]);
}

function showBlogItemRegenerateButton(item) {
  return Boolean(item?.id) && Boolean(item?.itemPageTemplateOutdated);
}

function hasBlogPublicSlugTitle(item) {
  const titleDe = String(item?.title?.de || "").trim();
  const titleEn = String(item?.title?.en || "").trim();
  return Boolean(titleDe || titleEn);
}

async function regenerateBlogItemPage(item) {
  const itemId = String(item?.id || "").trim();
  if (!itemId) return;
  if (isBlogItemTemplateRegenerationBusy(item)) return;
  const sectionId = resolveBlogSectionId();
  if (!sectionId) {
    itemPagesStatus.value = {
      type: "error",
      message: "Section ID not found. Please reload the page.",
    };
    return;
  }

  setBlogItemTemplateRegenerationBusy(itemId, true);
  try {
    await save({ throwOnError: true });
    await api.generateSectionItemPages(sectionId, {
      itemKind: "item",
      itemId,
      forceRebuild: true,
    });
    await fetchBlogData();
    itemPagesStatus.value = {
      type: "success",
      message: `Regenerated item page for "${localizedText(item?.title) || itemId}".`,
    };
  } catch (err) {
    console.error("Failed to regenerate blog item page:", err);
    itemPagesStatus.value = {
      type: "error",
      message: err?.message || "Failed to regenerate item page.",
    };
  } finally {
    setBlogItemTemplateRegenerationBusy(itemId, false);
  }
}

function normalizeArticleParentRoutePath(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const normalized = raw.replace(/^\/+|\/+$/g, "");
  if (!normalized) return "";
  return `/${normalized}`;
}

function normalizeImageZoom(value) {
  const raw = Number(value);
  if (!Number.isFinite(raw)) return 1;
  return Math.max(1, Math.min(4, raw));
}

function normalizeImageFocal(value) {
  const raw = Number(value);
  if (!Number.isFinite(raw)) return 50;
  return Math.max(0, Math.min(100, raw));
}

function normalizeImageRotation(value) {
  const raw = Number(value);
  if (!Number.isFinite(raw)) return 0;
  return Math.max(-180, Math.min(180, raw));
}

function normalizeImageAuthor(value) {
  return String(value || "").trim();
}

function resolveSelectionImageAuthor(selection) {
  const direct = normalizeImageAuthor(
    selection?.imageAuthor
    || selection?.image_author
    || selection?.author
  );
  if (direct) return direct;
  if (!Array.isArray(selection?.authors)) return "";
  return normalizeImageAuthor(
    selection.authors.find((entry) => normalizeImageAuthor(entry))
  );
}

function blogItemAuthorOverlay(item) {
  const author = normalizeImageAuthor(item?.imageAuthor);
  return author ? `© ${author}` : "";
}

function resolveBlogItemImageMedia(item, index = null) {
  const imageUrl = String(item?.imageUrl || "").trim();
  if (imageUrl) {
    return {
      url: imageUrl,
      responsiveVariants: Array.isArray(item?.responsiveVariants) ? item.responsiveVariants : [],
      zoom: normalizeImageZoom(item?.imageZoom),
      focalX: normalizeImageFocal(item?.imageFocalX),
      focalY: normalizeImageFocal(item?.imageFocalY),
      rotation: normalizeImageRotation(item?.imageRotation),
    };
  }
  if (index === null || index === undefined) {
    return {
      url: "",
      responsiveVariants: [],
      zoom: 1,
      focalX: 50,
      focalY: 50,
      rotation: 0,
    };
  }
  const fallback = resolveFallbackImageForIndex(state.mediaFallbacks, index);
  if (!fallback?.imageUrl) {
    return {
      url: "",
      responsiveVariants: [],
      zoom: 1,
      focalX: 50,
      focalY: 50,
      rotation: 0,
    };
  }
  return {
    url: fallback.imageUrl,
    responsiveVariants: Array.isArray(fallback.responsiveVariants) ? fallback.responsiveVariants : [],
    zoom: fallback.zoom,
    focalX: fallback.focalX,
    focalY: fallback.focalY,
    rotation: fallback.rotation,
  };
}

function resolveBlogItemImageUrl(item, index = null) {
  return resolveBlogItemImageMedia(item, index).url;
}

function resolveBlogItemResponsiveVariants(item, index = null) {
  if (index !== null && index !== undefined) {
    return resolveBlogItemImageMedia(item, index).responsiveVariants;
  }
  const source = item && typeof item === "object" ? item : {};
  return Array.isArray(source.responsiveVariants) ? source.responsiveVariants : [];
}

function resolveBlogItemImageZoom(item, index = null) {
  return resolveBlogItemImageMedia(item, index).zoom;
}

function resolveBlogItemImageFocalX(item, index = null) {
  return resolveBlogItemImageMedia(item, index).focalX;
}

function resolveBlogItemImageFocalY(item, index = null) {
  return resolveBlogItemImageMedia(item, index).focalY;
}

function resolveBlogItemImageRotation(item, index = null) {
  return resolveBlogItemImageMedia(item, index).rotation;
}

function applyBlogItemMediaPayload(item, payload) {
  if (!item || typeof item !== "object") return;
  const source = payload && typeof payload === "object" ? payload : {};
  const media = resolveBackendResponsiveImagePayload(source, {
    urlKeys: ["image_url", "url", "src", "href"],
  });
  item.imageUrl = String(media.url || item.imageUrl || "").trim();
  item.responsiveVariants = media.responsiveVariants;
  item.imageAuthor = normalizeImageAuthor(
    source.image_author
    || source.imageAuthor
    || source.author
    || item.imageAuthor
  );
}

function toBlogItemPayload(item) {
  const text = item?.text || {};
  return {
    image_url: item.imageUrl || '',
    image_responsive_variants: resolveBlogItemResponsiveVariants(item),
    image_author: normalizeImageAuthor(item.imageAuthor),
    image_zoom: normalizeImageZoom(item.imageZoom),
    image_focal_x: normalizeImageFocal(item.imageFocalX),
    image_focal_y: normalizeImageFocal(item.imageFocalY),
    image_rotation: normalizeImageRotation(item.imageRotation),
    date: item.date || '',
    tag: normalizeTag(item.tag),
    title: item.title || { de: '', en: '' },
    text: {
      de: normalizeEditorContent(text.de),
      en: normalizeEditorContent(text.en),
    },
    page_slug: item.pageSlug || '',
  };
}

function normalizeImportedBlogItem(item = {}) {
  const source = convertKeysToCamel(item && typeof item === "object" ? item : {});
  const media = resolveBackendResponsiveImagePayload(source, {
    urlKeys: ["imageUrl", "url", "src", "href"],
    variantKeys: ["responsiveVariants", "imageResponsiveVariants", "variants", "imageVariants"],
  });
  return {
    id: String(source.id || item?._id || "").trim(),
    imageUrl: String(media.url || "").trim(),
    responsiveVariants: Array.isArray(media.responsiveVariants) ? media.responsiveVariants : [],
    imageAuthor: normalizeImageAuthor(source.imageAuthor || source.author),
    imageZoom: normalizeImageZoom(source.imageZoom),
    imageFocalX: normalizeImageFocal(source.imageFocalX),
    imageFocalY: normalizeImageFocal(source.imageFocalY),
    imageRotation: normalizeImageRotation(source.imageRotation),
    date: String(source.date || ""),
    tag: normalizeBilingualText(source.tag),
    title: normalizeBilingualText(source.title),
    text: normalizeBilingualText(source.text),
    pageSlug: String(source.pageSlug || ""),
    itemPageTemplateOutdated: Boolean(source.itemPageTemplateOutdated),
  };
}

function blogImportSignature(item) {
  const normalized = normalizeImportedBlogItem(item);
  const date = String(normalized.date || "").trim();
  const titleDE = String(normalized.title?.de || "").trim().toLowerCase();
  const titleEN = String(normalized.title?.en || "").trim().toLowerCase();
  if (!date || (!titleDE && !titleEN)) return "";
  return `${date}::${titleDE}::${titleEN}`;
}

async function saveImportedBlogItems(importedItems = []) {
  const rows = (Array.isArray(importedItems) ? importedItems : [])
    .map((item) => normalizeImportedBlogItem(item))
    .filter((item) => String(item.id || "").trim() || shouldCreateBlogItem(item));
  if (rows.length === 0) return;

  saving.value = true;
  try {
    const existingBySignature = new Map();
    (Array.isArray(state.blogItems) ? state.blogItems : []).forEach((item) => {
      const signature = blogImportSignature(item);
      const id = String(item?.id || "").trim();
      if (signature && id && !existingBySignature.has(signature)) {
        existingBySignature.set(signature, id);
      }
    });

    for (const row of rows) {
      const payload = toBlogItemPayload(row);
      const explicitId = String(row.id || "").trim();
      const matchedId = explicitId || existingBySignature.get(blogImportSignature(row)) || "";
      if (matchedId) {
        const updated = await api.updateBlogItem(matchedId, payload);
        registerBlogItemPageGenerationJob(matchedId, updated);
      } else {
        const created = await api.createBlogItem(payload);
        const createdId = String(created?.id || "").trim();
        if (createdId) {
          registerBlogItemPageGenerationJob(createdId, created);
        }
      }
    }
    await fetchBlogData();
  } finally {
    saving.value = false;
  }
}

async function applyBlogIntegrationImportPatch(patch) {
  const normalizedPatch = patch && typeof patch === "object" ? patch : {};
  const importedItems = Array.isArray(normalizedPatch.blogItems)
    ? normalizedPatch.blogItems
    : null;
  const sectionPatch = { ...normalizedPatch };
  delete sectionPatch.blogItems;
  delete sectionPatch.blogTags;

  if (Object.keys(sectionPatch).length > 0) {
    updateSection(effectiveKey.value, sectionPatch, { revisionKind: "content" });
  }
  if (importedItems) {
    await saveImportedBlogItems(importedItems);
  }
}

function clearBlogItemPagePollTimer(itemId) {
  const normalizedId = String(itemId || "").trim();
  if (!normalizedId) return;
  const existing = blogItemPagePollTimers.get(normalizedId);
  if (existing) {
    clearTimeout(existing);
    blogItemPagePollTimers.delete(normalizedId);
  }
}

function clearAllBlogItemPagePollTimers() {
  for (const timer of blogItemPagePollTimers.values()) {
    clearTimeout(timer);
  }
  blogItemPagePollTimers.clear();
}

function setBlogItemPageJob(itemId, job) {
  const normalizedId = String(itemId || "").trim();
  if (!normalizedId) return;
  const next = { ...(blogItemPageJobs.value || {}) };
  next[normalizedId] = {
    ...(next[normalizedId] || {}),
    ...(job || {}),
  };
  blogItemPageJobs.value = next;
}

function applyBlogItemPageSlug(itemId, slug) {
  const normalizedId = String(itemId || "").trim();
  const normalizedSlug = String(slug || "").trim();
  if (!normalizedId || !normalizedSlug) return;
  for (const item of draft.value) {
    if (String(item?.id || "").trim() !== normalizedId) continue;
    item.pageSlug = normalizedSlug;
  }
}

function isBlogItemPageGenerationPending(item) {
  const itemId = String(item?.id || "").trim();
  if (!itemId) return false;
  const job = blogItemPageJobs.value[itemId];
  const status = String(job?.status || "").trim().toLowerCase();
  return status === "queued" || status === "running";
}

function blogItemPageGenerationError(item) {
  const itemId = String(item?.id || "").trim();
  if (!itemId) return "";
  const job = blogItemPageJobs.value[itemId];
  if (!job) return "";
  const status = String(job?.status || "").trim().toLowerCase();
  if (status !== "failed") return "";
  return String(job?.error || "Item page generation failed.").trim();
}

async function pollBlogItemPageGenerationJob(itemId, jobId, attempt = 0) {
  const normalizedItemId = String(itemId || "").trim();
  const normalizedJobId = String(jobId || "").trim();
  if (!normalizedItemId || !normalizedJobId) return;

  try {
    const result = await api.getSectionItemPageGenerationJob(normalizedJobId);
    setBlogItemPageJob(normalizedItemId, result);
    const status = String(result?.status || "").trim().toLowerCase();
    const slug = String(result?.slug || "").trim();
    if (slug) {
      applyBlogItemPageSlug(normalizedItemId, slug);
    }
    if (status === "completed" || status === "failed") {
      clearBlogItemPagePollTimer(normalizedItemId);
      return;
    }
  } catch (err) {
    console.error("Failed to poll blog item-page generation job:", err);
  }

  if (attempt >= BLOG_ITEM_JOB_POLL_MAX_ATTEMPTS) {
    clearBlogItemPagePollTimer(normalizedItemId);
    return;
  }
  clearBlogItemPagePollTimer(normalizedItemId);
  const timer = setTimeout(() => {
    blogItemPagePollTimers.delete(normalizedItemId);
    void pollBlogItemPageGenerationJob(normalizedItemId, normalizedJobId, attempt + 1);
  }, BLOG_ITEM_JOB_POLL_INTERVAL_MS);
  blogItemPagePollTimers.set(normalizedItemId, timer);
}

function registerBlogItemPageGenerationJob(itemId, apiPayload) {
  const normalizedItemId = String(itemId || "").trim();
  if (!normalizedItemId || !apiPayload || typeof apiPayload !== "object") return;
  const jobId = String(apiPayload.item_page_generation_job_id || "").trim();
  const status = String(apiPayload.item_page_generation_status || "").trim().toLowerCase() || "queued";
  if (!jobId) return;
  setBlogItemPageJob(normalizedItemId, {
    job_id: jobId,
    status,
    error: null,
    slug: String(apiPayload.page_slug || "").trim() || null,
  });
  void pollBlogItemPageGenerationJob(normalizedItemId, jobId, 0);
}

onUnmounted(() => {
  clearAllBlogItemPagePollTimers();
});

async function runBulkItemPageAction(action) {
  void action;
  if (itemPagesBusy.value) return;
  const sectionId = String(
    state.sectionIds?.[effectiveKey.value]
    || section.value?._id
    || section.value?.id
    || ""
  ).trim();
  if (!sectionId) {
    itemPagesStatus.value = {
      type: "error",
      message: "Section ID not found. Please reload the page.",
    };
    return;
  }

  itemPagesBusy.value = true;
  itemPagesStatus.value = { type: "", message: "" };
  try {
    await save({ throwOnError: true });

    const result = await api.cleanupSectionItemPages(sectionId);

    await fetchBlogData();

    const removedCount = Number(result?.removed_count || 0);
    const parentRoute = normalizeArticleParentRoutePath(
      result?.parent_route || articleParentRoute.value
    );
    itemPagesStatus.value = {
      type: "success",
      message: `Cleaned up ${removedCount} generated page${removedCount === 1 ? "" : "s"} under route "${parentRoute}".`,
    };
  } catch (err) {
    console.error("Failed to run item-page action:", err);
    itemPagesStatus.value = {
      type: "error",
      message: err?.message || "Failed to run item-page action.",
    };
  } finally {
    itemPagesBusy.value = false;
  }
}


function saveFilterEnabled() {
  if (hasLimit.value) {
    if (filterEnabled.value !== false) filterEnabled.value = false;
    updateSection(effectiveKey.value, { filterEnabled: false });
    return;
  }
  updateSection(effectiveKey.value, { filterEnabled: filterEnabled.value });
}

function saveDisplayStyle() {
  updateSection(effectiveKey.value, { displayStyle: displayStyle.value });
}

function saveTwoColumnNonCards() {
  updateSection(effectiveKey.value, { twoColumnNonCards: twoColumnNonCards.value });
}

// --- Color controls ---
const textColorOptions = computed(() => {
  return buildColorLinkOptions(state.design, {
    includeHighContrast: true,
    parameterConfigs: state.adminDesignConfig?.parameters,
  });
});
const separatorColorOptions = computed(() => {
  return buildColorLinkOptions(state.design, {
    includeHighContrast: true,
    parameterConfigs: state.adminDesignConfig?.parameters,
  });
});
const itemBgColorOptions = computed(() => {
  return buildColorLinkOptions(state.design, {
    parameterConfigs: state.adminDesignConfig?.parameters,
  });
});

function sectionVal(prop) {
  const key = effectiveKey.value;
  const fromState = state.sectionsData?.[key]?.[prop];
  if (fromState !== undefined) return fromState ?? null;
  return section.value?.[prop] ?? null;
}

const titleColor = computed(() => sectionVal('titleColor'));
const titleColorLink = computed(() => sectionVal('titleColorLink'));
const descColor = computed(() => sectionVal('descColor'));
const descColorLink = computed(() => sectionVal('descColorLink'));
const metaColor = computed(() => sectionVal('metaColor'));
const metaColorLink = computed(() => sectionVal('metaColorLink'));
const readMoreColor = computed(() => sectionVal('readMoreColor'));
const readMoreColorLink = computed(() => sectionVal('readMoreColorLink'));
const separatorColor = computed(() => sectionVal('separatorColor'));
const separatorColorLink = computed(() => sectionVal('separatorColorLink'));
const itemBgColor = computed(() => sectionVal('itemBgColor'));
const itemBgColorLink = computed(() => sectionVal('itemBgColorLink'));
const titleColorVariation = computed(() => normalizeColorVariation(sectionVal('titleColorVariation')));
const descColorVariation = computed(() => normalizeColorVariation(sectionVal('descColorVariation')));
const metaColorVariation = computed(() => normalizeColorVariation(sectionVal('metaColorVariation')));
const readMoreColorVariation = computed(() => normalizeColorVariation(sectionVal('readMoreColorVariation')));
const separatorColorVariation = computed(() => normalizeColorVariation(sectionVal('separatorColorVariation')));
const itemBgColorVariation = computed(() => normalizeColorVariation(sectionVal('itemBgColorVariation')));
const colorVariationOptions = COLOR_VARIATION_OPTIONS;
const showSeparators = ref(true);
const slidableOnMobile = ref(false);
const imageRatio = ref('1:1');

const imageRatioClass = computed(() => `blog-list--ratio-${imageRatio.value.replace(':', '-')}`);
const blogEditorThumbStyle = computed(() => ({
  aspectRatio: ratioToCss(imageRatio.value, "landscape"),
  width: "80px",
  height: "auto",
}));

watch(section, (s) => {
  showSeparators.value = s?.showSeparators !== false;
  slidableOnMobile.value = s?.slidableOnMobile ?? false;
  imageRatio.value = s?.imageRatio || '1:1';
}, { immediate: true });

function resolveBaseColor(linkKey) {
  return resolveLinkedColor(state.design, linkKey, state.adminDesignConfig?.parameters);
}

watch(() => [state.design.primaryColor, state.design.secondaryColor, state.design.backgroundColor, state.design.accentColor, state.design.sectionBackgroundColor], () => {
  if (itemBgColorLink.value) {
    const resolved = resolveBaseColor(itemBgColorLink.value);
    if (resolved !== null) updateSection(effectiveKey.value, { itemBgColor: resolved });
  }
  if (titleColorLink.value) {
    const resolved = resolveBaseColor(titleColorLink.value);
    if (resolved !== null) updateSection(effectiveKey.value, { titleColor: resolved });
  }
  if (descColorLink.value) {
    const resolved = resolveBaseColor(descColorLink.value);
    if (resolved !== null) updateSection(effectiveKey.value, { descColor: resolved });
  }
  if (metaColorLink.value) {
    const resolved = resolveBaseColor(metaColorLink.value);
    if (resolved !== null) updateSection(effectiveKey.value, { metaColor: resolved });
  }
  if (readMoreColorLink.value) {
    const resolved = resolveBaseColor(readMoreColorLink.value);
    if (resolved !== null) updateSection(effectiveKey.value, { readMoreColor: resolved });
  }
  if (separatorColorLink.value) {
    const resolved = resolveBaseColor(separatorColorLink.value);
    if (resolved !== null) updateSection(effectiveKey.value, { separatorColor: resolved });
  }
});

function setTitleColor(val) {
  updateSection(effectiveKey.value, { titleColor: val, titleColorLink: null });
}
function setItemBgColor(val) {
  updateSection(effectiveKey.value, { itemBgColor: val, itemBgColorLink: null });
}
function setDescColor(val) {
  updateSection(effectiveKey.value, { descColor: val, descColorLink: null });
}
function setMetaColor(val) {
  updateSection(effectiveKey.value, { metaColor: val, metaColorLink: null });
}
function setReadMoreColor(val) {
  updateSection(effectiveKey.value, { readMoreColor: val, readMoreColorLink: null });
}
function setSeparatorColor(val) {
  updateSection(effectiveKey.value, { separatorColor: val, separatorColorLink: null });
}
function saveSeparators() {
  updateSection(effectiveKey.value, { showSeparators: showSeparators.value });
}
function saveSlidable() {
  updateSection(effectiveKey.value, { slidableOnMobile: slidableOnMobile.value });
}
function saveImageRatio() {
  updateSection(effectiveKey.value, { imageRatio: imageRatio.value });
}

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

function normalizeHexColor(value) {
  if (typeof value !== 'string') return null;
  const raw = value.trim();
  if (!raw) return null;
  const clean = raw.startsWith('#') ? raw.slice(1) : raw;
  if (/^[0-9a-fA-F]{3}$/.test(clean)) {
    return `#${clean.split('').map((c) => c + c).join('').toLowerCase()}`;
  }
  if (/^[0-9a-fA-F]{6}$/.test(clean)) {
    return `#${clean.toLowerCase()}`;
  }
  return null;
}

function hexToLuminance(hexColor) {
  const clean = hexColor.replace('#', '');
  const r = parseInt(clean.substring(0, 2), 16) / 255;
  const g = parseInt(clean.substring(2, 4), 16) / 255;
  const b = parseInt(clean.substring(4, 6), 16) / 255;
  const toLinear = (v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
  return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
}

function oppositeHighContrastColor(color) {
  const dark = state.design.highContrastDark || '#0b1220';
  const light = state.design.highContrastLight || '#f8fafc';

  const normalizedColor = normalizeHexColor(color);
  const normalizedDark = normalizeHexColor(dark);
  const normalizedLight = normalizeHexColor(light);

  if (normalizedColor && normalizedDark && normalizedColor === normalizedDark) return light;
  if (normalizedColor && normalizedLight && normalizedColor === normalizedLight) return dark;

  if (normalizedColor) {
    return hexToLuminance(normalizedColor) > 0.4 ? dark : light;
  }

  return light;
}

function resolveTextColor(colorVal, variation = DEFAULT_COLOR_VARIATION) {
  let resolved;
  if (!colorVal || colorVal === HIGH_CONTRAST_TOKEN) {
    const itemBgBaseKey = isBaseColorLinkKey(itemBgColorLink.value, state.adminDesignConfig?.parameters) ? itemBgColorLink.value : null;
    const contrastBg = resolveItemBackgroundColor(itemBgColor.value, DEFAULT_COLOR_VARIATION)
      || (itemBgColor.value && itemBgColor.value !== HIGH_CONTRAST_TOKEN
        ? itemBgColor.value
        : (state.design.sectionBackgroundColor || '#ffffff'));
    resolved = contrastColor(contrastBg, itemBgBaseKey);
  } else {
    resolved = colorVal;
  }
  return applyColorVariation(resolved, variation);
}

function resolveItemBackgroundColor(colorVal, variation = DEFAULT_COLOR_VARIATION) {
  let resolved;
  if (!colorVal || colorVal === HIGH_CONTRAST_TOKEN) {
    const sectionBg = state.design.sectionBackgroundColor || '#ffffff';
    const sectionTextContrast = contrastColor(sectionBg, 'sectionBackgroundColor');
    resolved = oppositeHighContrastColor(sectionTextContrast);
  } else {
    resolved = colorVal;
  }
  return applyColorVariation(resolved, variation);
}

const resolvedItemBgColor = computed(() =>
  resolveItemBackgroundColor(itemBgColor.value, itemBgColorVariation.value)
);
const textContrastBaseRefColor = computed(() =>
  resolveItemBackgroundColor(itemBgColor.value, DEFAULT_COLOR_VARIATION)
    || (itemBgColor.value && itemBgColor.value !== HIGH_CONTRAST_TOKEN
      ? itemBgColor.value
      : (state.design.sectionBackgroundColor || "#ffffff"))
);

const itemStyle = computed(() => {
  const s = {};
  s.background = resolvedItemBgColor.value;
  return s;
});

const cappedThreeItemStyle = computed(() => {
  if (!isCappedThreeLayout.value) return {};
  return {
    flex: '1 1 150px',
    maxWidth: '450px',
  };
});

const titleStyle = computed(() => {
  const s = {};
  s.color = resolveTextColor(titleColor.value, titleColorVariation.value);
  return s;
});

const descStyle = computed(() => {
  const s = {};
  s.color = resolveTextColor(descColor.value, descColorVariation.value);
  return s;
});

const metaStyle = computed(() => {
  const s = {};
  s.color = resolveTextColor(metaColor.value, metaColorVariation.value);
  return s;
});

const readMoreStyle = computed(() => {
  const s = {};
  s.color = resolveTextColor(readMoreColor.value, readMoreColorVariation.value);
  return s;
});

const separatorStyle = computed(() => {
  const s = {};
  if (showSeparators.value) {
    s['--blog-separator-color'] = resolveTextColor(separatorColor.value, separatorColorVariation.value);
  }
  return s;
});

function hexOrDefault(val, fallback) {
  if (val && /^#[0-9a-fA-F]{6}$/.test(val)) return val;
  return fallback;
}

function swatchStyle(previewColor, options = {}) {
  return getBaseSectionSwatchStyle(state.design, previewColor, options);
}

function applyColorLink(which, key) {
  const resolved = resolveBaseColor(key);
  if (which === 'itemBg') {
    updateSection(effectiveKey.value, { itemBgColor: resolved, itemBgColorLink: key });
  } else if (which === 'separator') {
    updateSection(effectiveKey.value, { separatorColor: resolved, separatorColorLink: key });
  } else if (which === 'title') {
    updateSection(effectiveKey.value, { titleColor: resolved, titleColorLink: key });
  } else if (which === 'desc') {
    updateSection(effectiveKey.value, { descColor: resolved, descColorLink: key });
  } else if (which === 'meta') {
    updateSection(effectiveKey.value, { metaColor: resolved, metaColorLink: key });
  } else if (which === 'readMore') {
    updateSection(effectiveKey.value, { readMoreColor: resolved, readMoreColorLink: key });
  }
}

function setColorVariation(which, variation) {
  const normalized = normalizeColorVariation(variation);
  const value = normalized === DEFAULT_COLOR_VARIATION ? null : normalized;
  if (which === 'itemBg') {
    updateSection(effectiveKey.value, { itemBgColorVariation: value });
  } else if (which === 'separator') {
    updateSection(effectiveKey.value, { separatorColorVariation: value });
  } else if (which === 'title') {
    updateSection(effectiveKey.value, { titleColorVariation: value });
  } else if (which === 'desc') {
    updateSection(effectiveKey.value, { descColorVariation: value });
  } else if (which === 'meta') {
    updateSection(effectiveKey.value, { metaColorVariation: value });
  } else if (which === 'readMore') {
    updateSection(effectiveKey.value, { readMoreColorVariation: value });
  }
}

function startEdit() {
  expandedItem.value = -1;
  itemPagesStatus.value = { type: "", message: "" };
  draft.value = (state.blogItems || []).map((x) => {
    return {
      id: x.id,
      imageUrl: String(x.imageUrl || "").trim(),
      responsiveVariants: Array.isArray(x.responsiveVariants) ? x.responsiveVariants : [],
      imageAuthor: normalizeImageAuthor(x.imageAuthor),
      imageZoom: normalizeImageZoom(x.imageZoom),
      imageFocalX: normalizeImageFocal(x.imageFocalX),
      imageFocalY: normalizeImageFocal(x.imageFocalY),
      imageRotation: normalizeImageRotation(x.imageRotation),
      date: x.date || "",
      tag: normalizeTag(x.tag),
      title: { de: x.title?.de ?? "", en: x.title?.en ?? "" },
      text: { de: x.text?.de ?? "", en: x.text?.en ?? "" },
      pageSlug: x.pageSlug || "",
      itemPageTemplateOutdated: Boolean(x.itemPageTemplateOutdated),
    };
  });
  const activeIds = new Set(draft.value.map((item) => String(item?.id || "").trim()).filter(Boolean));
  const nextJobs = {};
  for (const [itemId, job] of Object.entries(blogItemPageJobs.value || {})) {
    if (!activeIds.has(String(itemId || "").trim())) continue;
    nextJobs[itemId] = job;
  }
  blogItemPageJobs.value = nextJobs;
  const nextRegenerationBusy = {};
  for (const itemId of Object.keys(blogItemTemplateRegenerationBusy.value || {})) {
    if (!activeIds.has(String(itemId || "").trim())) continue;
    nextRegenerationBusy[itemId] = true;
  }
  blogItemTemplateRegenerationBusy.value = nextRegenerationBusy;
  draftTags.value = uniqueTags([
    ...(Array.isArray(state.blogTags) ? state.blogTags : []),
    ...draft.value.map((item) => item.tag),
  ]);
  editing.value = true;
}

function setItemTag(itemIdx, tag) {
  if (isBlogItemFieldLocked(itemIdx, "tag", { includeDescendants: true })) return;
  if (itemIdx >= 0 && itemIdx < draft.value.length) {
    draft.value[itemIdx].tag = normalizeTag(tag);
  }
}

function replaceDraftItemTopic(previousTag, nextTag = null) {
  const previous = normalizeTag(previousTag);
  if (!hasTagValue(previous)) return;
  const replacement = nextTag && hasTagValue(nextTag) ? normalizeTag(nextTag) : null;
  draft.value = draft.value.map((item) => {
    if (!tagMatches(item?.tag, previous)) return item;
    return {
      ...item,
      tag: replacement ? { ...replacement } : { de: "", en: "" },
    };
  });
}

function replaceSectionScopeTopic(previousTag, nextTag = null) {
  const previous = normalizeTag(previousTag);
  if (!hasTagValue(previous) || !tagMatches(section.value?.scope, previous)) return;
  const replacement = nextTag && hasTagValue(nextTag) ? normalizeTag(nextTag) : null;
  updateSection(
    effectiveKey.value,
    { scope: replacement ? { ...replacement } : null },
    { revisionKind: "content" }
  );
}

async function saveBlogTopicCatalog(payload = {}) {
  const nextTopics = uniqueTags(payload.topics || draftTags.value);
  const originalTopics = Array.isArray(payload.originalTopics) ? payload.originalTopics : [];
  const maxLength = Math.max(originalTopics.length, nextTopics.length);
  for (let index = 0; index < maxLength; index += 1) {
    const previousTag = normalizeTag(originalTopics[index]);
    const nextTag = normalizeTag(nextTopics[index]);
    if (!hasTagValue(previousTag)) continue;
    if (hasTagValue(nextTag) && !tagMatches(previousTag, nextTag)) {
      replaceDraftItemTopic(previousTag, nextTag);
      replaceSectionScopeTopic(previousTag, nextTag);
    } else if (!hasTagValue(nextTag)) {
      replaceDraftItemTopic(previousTag, null);
      replaceSectionScopeTopic(previousTag, null);
    }
  }
  draftTags.value = nextTopics;
  await save();
}

function setLimit(value) {
  const normalized = normalizeLimitValue(value);
  if (limit.value === normalized) return;
  updateSectionLimit(state.pageSlug || "landing", effectiveKey.value, normalized);
}

function onLimitInputChange(event) {
  const normalized = normalizeLimitValue(event?.target?.value);
  limitInput.value = normalized == null ? "" : String(normalized);
  setLimit(normalized);
}

function addItem() {
  const scope = section.value?.scope;
  const defaultTag = hasTagValue(scope) ? normalizeTag(scope) : (draftTags.value[0] ? { ...draftTags.value[0] } : { de: "", en: "" });
  draft.value.push({
    id: "",
    imageUrl: "",
    responsiveVariants: [],
    imageAuthor: "",
    imageZoom: 1,
    imageFocalX: 50,
    imageFocalY: 50,
    imageRotation: 0,
    date: todayISO(),
    tag: defaultTag,
    title: { de: "", en: "" },
    text: { de: "", en: "" },
    pageSlug: "",
    itemPageTemplateOutdated: false,
  });
  expandedItem.value = draft.value.length - 1;
}

function removeItem(i) {
  if (i < 0 || i >= draft.value.length) return;
  const removed = draft.value[i];
  draft.value.splice(i, 1);
  if (expandedItem.value === i) {
    expandedItem.value = -1;
  } else if (expandedItem.value > i) {
    expandedItem.value -= 1;
  }
  if (removed?.id) {
    clearBlogItemPagePollTimer(removed.id);
    const nextJobs = { ...(blogItemPageJobs.value || {}) };
    const nextRegenerationBusy = { ...(blogItemTemplateRegenerationBusy.value || {}) };
    delete nextJobs[String(removed.id || "").trim()];
    delete nextRegenerationBusy[String(removed.id || "").trim()];
    blogItemPageJobs.value = nextJobs;
    blogItemTemplateRegenerationBusy.value = nextRegenerationBusy;
    const sourceItem = (state.blogItems || []).find((entry) => entry.id === removed.id);
    if (!sourceItem?.pageSlug) {
      itemPagesStatus.value = { type: "", message: "" };
    }
  }
}

function onMediaSelect(selection) {
  const { index, direct } = consumeMediaPickerSelectionContext();
  if (index >= 0 && index < draft.value.length) {
    if (isBlogItemFieldLocked(index, "imageUrl")) {
      closeMediaPicker();
      return;
    }
    const item = draft.value[index];
    const media = resolveBackendResponsiveImagePayload(selection, {
      urlKeys: ["url", "src", "href"],
    });
    item.imageUrl = String(media.url || "").trim();
    item.responsiveVariants = media.responsiveVariants;
    item.imageAuthor = resolveSelectionImageAuthor(selection);
    item.imageZoom = normalizeImageZoom(item.imageZoom);
    item.imageFocalX = normalizeImageFocal(item.imageFocalX);
    item.imageFocalY = normalizeImageFocal(item.imageFocalY);
    item.imageRotation = normalizeImageRotation(item.imageRotation);
    if (direct && !saving.value) void save();
  }
  closeMediaPicker();
}

function setItemImageZoom(index, value) {
  if (index < 0 || index >= draft.value.length) return;
  if (isBlogItemFieldLocked(index, "imageZoom")) return;
  draft.value[index].imageZoom = normalizeImageZoom(value);
}

function setItemImageUrl(index, value) {
  if (index < 0 || index >= draft.value.length) return;
  if (isBlogItemFieldLocked(index, "imageUrl")) return;
  draft.value[index].imageUrl = String(value || "");
  draft.value[index].responsiveVariants = [];
  draft.value[index].imageAuthor = "";
}

function clearItemImage(index) {
  if (index < 0 || index >= draft.value.length) return;
  if (isBlogItemFieldLocked(index, "imageUrl")) return;
  draft.value[index].imageUrl = "";
  draft.value[index].responsiveVariants = [];
  draft.value[index].imageAuthor = "";
}

function setItemImageFocalX(index, value) {
  if (index < 0 || index >= draft.value.length) return;
  if (isBlogItemFieldLocked(index, "imageFocalX")) return;
  draft.value[index].imageFocalX = normalizeImageFocal(value);
}

function setItemImageFocalY(index, value) {
  if (index < 0 || index >= draft.value.length) return;
  if (isBlogItemFieldLocked(index, "imageFocalY")) return;
  draft.value[index].imageFocalY = normalizeImageFocal(value);
}

function setItemImageRotation(index, value) {
  if (index < 0 || index >= draft.value.length) return;
  if (isBlogItemFieldLocked(index, "imageRotation")) return;
  draft.value[index].imageRotation = normalizeImageRotation(value);
}

async function reorderItems() {
  // draft is already mutated in-place by vuedraggable. Persist the new order.
  const ids = draft.value.map((x) => x.id).filter(Boolean);
  if (!ids.length) return;
  try {
    await api.reorderBlogItems(ids);
    // Update the store order to match without a full refetch
    const byId = new Map((state.blogItems || []).map((x) => [x.id, x]));
    const reordered = ids.map((id) => byId.get(id)).filter(Boolean);
    const rest = (state.blogItems || []).filter((x) => !ids.includes(x.id));
    state.blogItems = [...reordered, ...rest];
  } catch (err) {
    console.error("Failed to save reorder:", err);
  }
}

function shouldCreateBlogItem(item) {
  return Boolean(
    item?.title?.de?.trim?.()
    || item?.title?.en?.trim?.()
    || normalizeEditorContent(item?.text?.de)
    || normalizeEditorContent(item?.text?.en)
    || item?.imageUrl?.trim?.()
  );
}

async function performBlogSave(requestId, { throwOnError = false } = {}) {
  saving.value = true;
  try {
    const snapshotEntries = (draft.value || []).map((item) => ({
      ref: item,
      item: JSON.parse(JSON.stringify(item || {})),
    }));
    const sectionSnapshot = section.value && typeof section.value === "object"
      ? JSON.parse(JSON.stringify(section.value))
      : {};
    sectionSnapshot.blogItems = snapshotEntries.map((entry) => JSON.parse(JSON.stringify(entry.item)));
    const preparedItems = Array.isArray(sectionSnapshot.blogItems)
      ? sectionSnapshot.blogItems
      : snapshotEntries.map((entry) => entry.item);

    for (let index = 0; index < snapshotEntries.length; index += 1) {
      const entry = snapshotEntries[index];
      const liveItem = entry.ref;
      const snapshotItem = entry.item;
      const preparedItem = preparedItems[index] || snapshotItem;
      const payload = toBlogItemPayload(preparedItem);
      const existingId = String(snapshotItem.id || liveItem?.id || "").trim();
      if (existingId) {
        const updated = await api.updateBlogItem(existingId, payload);
        if (liveItem && typeof liveItem === "object") {
          applyBlogItemMediaPayload(liveItem, updated);
          if (updated?.page_slug) {
            liveItem.pageSlug = updated.page_slug;
          }
        }
        registerBlogItemPageGenerationJob(existingId, updated);
      } else if (shouldCreateBlogItem(snapshotItem)) {
        const created = await api.createBlogItem(payload);
        const createdId = String(created?.id || "").trim();
        if (liveItem && typeof liveItem === "object" && createdId) {
          liveItem.id = createdId;
        }
        if (liveItem && typeof liveItem === "object") {
          applyBlogItemMediaPayload(liveItem, created);
          if (created?.page_slug) {
            liveItem.pageSlug = created.page_slug;
          }
        }
        if (createdId) {
          registerBlogItemPageGenerationJob(createdId, created);
        }
      }
    }
    const savedIds = new Set(
      snapshotEntries
        .map((entry) => String(entry.ref?.id || entry.item?.id || "").trim())
        .filter(Boolean)
    );
    const toDelete = (state.blogItems || []).filter(
      (old) => String(old?.id || "").trim() && !savedIds.has(String(old.id || "").trim())
    );
    for (const old of toDelete) {
      if (old.id) await api.deleteBlogItem(old.id);
    }
    await api.updateBlogConfig(JSON.parse(JSON.stringify(uniqueTags(draftTags.value || []))));
    const hasUnsavedDraftRows = draft.value.some(
      (item) => !String(item?.id || "").trim()
    );
    if (requestId === blogItemSaveRequestId && !hasUnsavedDraftRows) {
      await fetchBlogData();
    }
  } catch (err) {
    console.error("Failed to save blog items:", err);
    if (throwOnError) throw err;
  } finally {
    if (requestId === blogItemSaveRequestId) {
      saving.value = false;
    }
  }
}

function save(options = {}) {
  const requestId = ++blogItemSaveRequestId;
  const runSave = () => performBlogSave(requestId, options);
  blogItemSaveQueue = blogItemSaveQueue.then(runSave, runSave);
  return blogItemSaveQueue;
}

</script>

<style scoped>
.blog-list { position: relative; margin-top: 16px; display: grid; gap: 20px; }
.blog-list--empty { min-height: 80px; padding: 20px; display: flex; align-items: center; justify-content: center; }

.blog { 
  display: grid; 
  grid-template-columns: 160px 1fr; 
  gap: 16px; 
  align-items: start; 
  padding: 14px;
  background: color-mix(in srgb, var(--blog-accent-color, var(--accent, #4f46e5)) 4%, transparent);
}

.blog__media {
  position: relative;
  aspect-ratio: 1/1;
  border-radius: 10px;
  overflow: hidden;
  background: color-mix(in srgb, var(--blog-accent-color, var(--accent, #4f46e5)) 8%, transparent);
  padding: 5%;
  box-sizing: border-box;
}

.blog__author-overlay {
  position: absolute;
  top: 10px;
  right: 28px;
  z-index: 3;
  max-width: min(78%, 320px);
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

.blog-list--list .blog__media {
  max-height: 270px;
  width: 100%;
}

.blog__media-link {
  display: block;
  width: 100%;
  height: 100%;
  color: inherit;
}

.blog__img {
  width: 100%;
  height: 100%;
}

.blog__img--interactive {
  transition: transform 0.2s ease, filter 0.2s ease;
  will-change: transform;
}

.blog__img :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.blog__placeholder { width: 100%; height: 100%; display: grid; place-items: center; font-size: 12px; color: var(--blog-muted-color, var(--secondary-color, #64748b)); }
.blog__content { width: 100%; display: flex; flex-direction: column; gap: 8px; min-width: 0; height: 100%; }
.blog__title { font-family: var(--header-font-family); font-weight: var(--header-font-weight); font-size: 1.25rem; line-height: 1.3; color: var(--primary-color); margin: 0; }
.blog__title-link { color: inherit; text-decoration: none; border-bottom: 1px solid transparent; transition: border-color 0.15s ease; }
.blog__title-link:hover { border-bottom-color: currentColor; }
.blog__text { font-size: 0.9rem; line-height: var(--body-line-height); color: var(--secondary-color); margin: 0; margin-top: auto; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.blog__text :deep(p) { margin: 0 0 0.75em; }
.blog__text :deep(p:last-child) { margin-bottom: 0; }
.blog__text :deep(ul),
.blog__text :deep(ol) { margin: 0.4em 0; padding-left: 1.4em; }
.blog__text :deep(a) { text-decoration: underline; }
.blog__meta { display: flex; align-items: center; justify-content: var(--section-content-justify, flex-start); gap: 6px; flex-wrap: wrap; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--accent); margin-top: 0; }
.blog__tag { }
.blog__sep { }
.blog__date { }
.blog__read-more {
  align-self: var(--section-content-justify, flex-start);
  margin-top: 6px;
  font-size: 12px;
  font-weight: 700;
  color: var(--accent, #4f46e5);
  text-decoration: none;
}
.blog__read-more:hover { text-decoration: underline; }

/* Separators between content elements */
.blog__content.has-separators .blog__title {
  padding-bottom: 8px;
  border-bottom: 2px solid var(--blog-separator-color, color-mix(in srgb, var(--accent) 20%, transparent));
}
.blog__content.has-separators .blog__text {
  padding-bottom: 8px;
  border-bottom: 2px solid var(--blog-separator-color, color-mix(in srgb, var(--accent) 20%, transparent));
}

.blog-design-controls {
  display: grid;
  gap: 10px;
}

.admin-controls-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  margin-top: 0;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.blog-design-row {
  margin-bottom: 0;
}

.blog-design-row--independent {
  align-items: flex-start;
}

.ctrl-item { display: flex; flex-direction: column; gap: 3px; }
.ctrl-label { font-size: 10px; font-weight: 700; color: var(--admin-text-muted, #64748b); text-transform: uppercase; letter-spacing: 0.05em; }
.ctrl-select { width: auto; min-width: 110px; padding: 5px 8px; font-size: 12px; }
.ctrl-help { font-size: 11px; color: var(--admin-text-muted, #64748b); line-height: 1.2; max-width: 190px; }
.ctrl-item.is-disabled .ctrl-label { color: color-mix(in srgb, var(--admin-text-muted, #64748b) 85%, #9ca3af); }
.ctrl-select:disabled {
  opacity: 0.65;
  cursor: not-allowed;
  background: color-mix(in srgb, var(--surface, #f8fafc) 80%, #e2e8f0);
}
.ctrl-input { width: auto; min-width: 100px; max-width: 140px; padding: 5px 8px; font-size: 12px; border: none !important; }

/* Color controls row */
.color-controls-row { margin-top: 8px; }
.color-link-control {
  display: flex;
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
.color-swatch {
  width: 22px;
  height: 22px;
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

.checkbox-ctrl {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}
.checkbox-ctrl input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}


.limit-toggle { display: flex; gap: 0; border-radius: 6px; overflow: hidden; border: 1px solid var(--border, #e2e8f0); }
.limit-input {
  min-width: 72px;
  max-width: 84px;
  border: none;
  border-radius: 0;
}
.limit-input:focus {
  outline: none;
}
.limit-btn {
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
  border: none;
  background: #fff;
  color: var(--muted, #64748b);
  cursor: pointer;
  transition: all 0.15s ease;
}
.limit-btn + .limit-btn { border-left: 1px solid var(--border, #e2e8f0); }
.limit-btn:hover:not(.active) { background: var(--surface-2, #f1f5f9); }
.limit-btn.active { background: var(--accent, #4f46e5); color: #fff; }

.empty-hint { margin-top: 12px; color: var(--admin-text-muted); }

.thumb-date {
  font-size: 10px;
  color: var(--admin-text-muted, #94a3b8);
}

.item-pages-actions {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.item-pages-status {
  font-size: 12px;
  color: var(--admin-text-muted, #64748b);
}

.item-pages-status.success {
  color: #15803d;
}

.item-pages-status.warn {
  color: #b45309;
}

.item-pages-status.error {
  color: #b91c1c;
}

.item-field-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.item-page-title-info {
  border: 1px solid #f59e0b;
  background: #fffbeb;
  color: #92400e;
  border-radius: 8px;
  padding: 0.5rem 0.65rem;
  font-size: 0.78rem;
}

.field-hint--error {
  color: #b91c1c;
}

.field-row, .lang-section { display: grid; gap: 4px; }
.field-label, .lang-header { font-size: 11px; font-weight: 700; color: var(--admin-text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.field { width: 100%; border-radius: 8px; border: 1px solid var(--border); background: rgba(255,255,255,0.92); padding: 8px 12px; outline: none; color: var(--primary-color); }
.field.textarea { resize: vertical; min-height: 60px; }
.blog-meta-edit-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.field-rich {
  display: grid;
  min-width: 0;
}
.field-rich :deep(.ql-toolbar) {
  border-radius: 8px 8px 0 0;
  border-color: var(--border, #d6dce6);
  background: rgba(255,255,255,0.96);
}
.field-rich :deep(.ql-container) {
  border-radius: 0 0 8px 8px;
  border-color: var(--border, #d6dce6);
  background: rgba(255,255,255,0.92);
  min-height: 110px;
  height: auto;
}
.field-rich :deep(.ql-editor) {
  min-height: 110px;
}
.section-date-picker {
  width: 100%;
}
.section-date-picker :deep(.dp__input_wrap) {
  width: 100%;
}
.section-date-picker :deep(.dp__input) {
  width: 100%;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.92);
  outline: none;
  color: var(--primary-color);
  font: inherit;
}
.section-date-picker :deep(.dp__input:focus) {
  border-color: rgba(59, 130, 246, 0.55);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
.item-page-route {
  min-height: 32px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 7px 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: var(--secondary-color);
  background: rgba(255, 255, 255, 0.92);
}
.item-page-route--empty { color: var(--muted, #94a3b8); font-style: italic; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.spacer { flex: 1; }
/* Filter bar */
.filter-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
  margin-bottom: 8px;
}
.filter-btn {
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  border-radius: 20px;
  border: 1px solid var(--border, #e2e8f0);
  background: #fff;
  color: var(--muted, #64748b);
  cursor: pointer;
  transition: all 0.15s ease;
}
.filter-btn:hover:not(.active) {
  background: var(--surface-2, #f1f5f9);
  border-color: var(--accent, #4f46e5);
}
.filter-btn.active {
  background: var(--accent, #4f46e5);
  color: #fff;
  border-color: var(--accent, #4f46e5);
}

/* Display style: List (default) */
.blog-list--list .blog {
  display: grid;
  grid-template-columns: 20% 1fr;
  gap: 16px;
  align-items: stretch;
}
.blog-list--list .blog__text {
  display: block;
  -webkit-line-clamp: unset;
  -webkit-box-orient: initial;
  overflow: visible;
  margin-top: 0;
}
.blog-list.blog-list--two-columns {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px 24px;
  align-items: start;
}
.blog-list.blog-list--two-columns .empty-hint {
  grid-column: 1 / -1;
  justify-self: center;
}

/* Display style: Cards */
.blog-list--cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 24px;
}
.blog-list--cards.blog-list--capped-three {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  grid-template-columns: none;
}
.blog-list--cards .blog {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0;
  overflow: hidden;
  background: color-mix(in srgb, var(--blog-accent-color, var(--accent, #4f46e5)) 4%, transparent);
  border: 1px solid color-mix(in srgb, var(--blog-accent-color, var(--accent, #4f46e5)) 12%, transparent);
  border-radius: var(--section-border-radius);
}
.blog-list--cards.blog-list--capped-three .blog {
  flex: 1 0;
  max-width: 375px;
}
.blog-list--cards .blog__media {
  width: 100%;
  flex-shrink: 0;
  border-radius: 0;
  border-top-left-radius: calc(var(--section-border-radius) - 1px);
  border-top-right-radius: calc(var(--section-border-radius) - 1px);
}
.blog-list--cards .blog__content {
  padding: 16px;
  gap: 10px;
  flex: 1;
  display: flex;
  flex-direction: column;
}
.blog-list--cards .blog__title {
  font-size: 1.4rem;
}
.blog-list--cards .blog__text {
  -webkit-line-clamp: 4;
}
.blog-list--cards .blog__meta {
  font-size: 12px;
  margin-top: 0;
}
.blog-list--cards .blog__media-link:hover .blog__img--interactive,
.blog-list--cards .blog__media-link:focus-visible .blog__img--interactive {
  transform: scale(1.03);
  filter: saturate(1.03);
}
/* Slidable cards on mobile */
@media (max-width: 600px) {
  .blog-list--cards.blog-list--slidable {
    display: flex;
    flex-wrap: nowrap;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    -webkit-overflow-scrolling: touch;
    gap: 16px;
    padding: 0 calc((100% - 85%) / 2) 8px;
    scrollbar-width: none;
  }
  .blog-list--cards.blog-list--slidable::-webkit-scrollbar {
    display: none;
  }
  .blog-list--cards.blog-list--slidable .blog {
    flex: 0 0 85%;
    min-width: 260px;
    max-width: 320px;
    scroll-snap-align: center;
  }
}

/* Image ratio variants */
.blog-list--ratio-1-1 .blog__media { aspect-ratio: 1/1; }
.blog-list--ratio-16-9 .blog__media { aspect-ratio: 16/9; }
.blog-list--ratio-2-3 .blog__media { aspect-ratio: 2/3; }

/* Display style: Compact */
.blog-list--compact {
  display: grid;
  gap: 12px;
}
.blog-list--compact .blog {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 12px;
  padding: 10px;
  align-items: center;
}
.blog-list--compact .blog__media {
  aspect-ratio: 1;
  border-radius: 8px;
}
.blog-list--compact .blog__content {
  gap: 4px;
  height: 100%;
}
.blog-list--compact .blog__title {
  font-size: 1rem;
}
.blog-list--compact .blog__meta {
  gap: 4px;
  margin-top: 0;
  font-size: 10px;
}
.blog-list--compact .blog__tag,
.blog-list--compact .blog__sep {
  display: none;
}

@media (max-width: 600px) {
  .blog-list.blog-list--two-columns {
    grid-template-columns: 1fr;
  }
  .blog-meta-edit-row {
    grid-template-columns: 1fr;
  }
  .blog-list--list .blog { grid-template-columns: 1fr; }
  .blog-list--compact .blog { grid-template-columns: 60px 1fr; }
}
</style>
