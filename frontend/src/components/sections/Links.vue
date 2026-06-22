<template>
  <SectionBase :section-key="effectiveKey" :section-data="section">
    <div>
      <!-- Display links -->
      <div
        v-if="displayItems.length"
        class="links-grid"
        :style="gridStyle"
      >
        <a
          v-for="(item, index) in displayItems"
          :key="item.id || item.imageUrl || item.icon"
          :href="linkHref(item.linkUrl)"
          :target="linkTarget(item.linkUrl)"
          :rel="linkRel(item.linkUrl)"
          class="link-item"
          :class="{
            'no-link': !hasHref(item.linkUrl),
            'link-item--non-social': !socialMode,
            'link-item--admin-hidden': isAdminHiddenLinkIcon(item),
          }"
          :style="itemStyle"
          @click="handleClick($event, item.linkUrl)"
        >
          <font-awesome-icon
            v-if="showIcon(item)"
            :icon="resolveFaIcon(item)"
            class="link-icon"
            :style="iconStyle"
            :title="localizedText(item.title) || undefined"
          />
          <ResponsiveImage
            v-else-if="resolveLinkItemImageUrl(item, index)"
            class="link-image"
            :src="resolveLinkItemImageUrl(item, index)"
            :image-data="resolveLinkItemImageData(item, index)"
            :alt="localizedText(item.title) || ''"
            :style="imgStyle"
            loading="lazy"
            decoding="async"
          />
          <span v-if="!hideItemTitle && localizedText(item.title)" class="link-title">
            {{ localizedText(item.title) }}
          </span>
        </a>
      </div>

      <div v-else-if="state.isAdmin" class="links-grid links-grid--empty">
        <span class="empty-hint">+ Add Links</span>
      </div>

      <!-- Media Library Modal -->
      <MediaLibrary
        :is-open="showMediaPicker"
        :current-url="''"
        source-context="section.links.image"
        @close="closeMediaPicker"
        @select="onMediaSelect"
      />
    </div>

    <template #admin-design-params>
      <div class="design-controls">
        <div class="design-group">
          <div class="design-group-title">{{ socialMode ? "Social Mode" : "Standard Mode" }}</div>

          <label class="design-checkbox">
            <input type="checkbox" :checked="socialMode" @change="setDesign('socialMode', $event.target.checked)" />
            <span>Social media mode</span>
          </label>

          <template v-if="socialMode">
            <label class="design-checkbox">
              <input
                type="checkbox"
                :checked="hideIconsWithoutLinks"
                @change="setDesign('hideIconsWithoutLinks', $event.target.checked)"
              />
              <span>Hide icons without links</span>
            </label>
          </template>

          <template v-else>
            <div class="design-field">
              <label class="field-label">Item max-width (px)</label>
              <div class="slider-row">
                <input
                  type="range"
                  min="0"
                  max="1200"
                  step="5"
                  :value="nonSocialItemMaxWidth"
                  @input="setDesign('nonSocialItemMaxWidth', Number($event.target.value))"
                />
                <input
                  type="number"
                  min="0"
                  max="1200"
                  :value="nonSocialItemMaxWidth"
                  class="field number-field"
                  @input="setDesign('nonSocialItemMaxWidth', clampNonSocialItemMaxWidth($event.target.value))"
                />
              </div>
              <div class="field-hint">0 = no max-width.</div>
            </div>
          </template>
        </div>

        <div class="design-group">
          <div class="design-group-title">General</div>
          <label class="design-checkbox">
            <input type="checkbox" :checked="hideItemTitle" @change="setDesign('hideItemTitle', $event.target.checked)" />
            <span>Hide item title</span>
          </label>

          <div class="design-field">
            <label class="field-label">Alignment</label>
            <div class="radio-row">
              <label v-for="opt in ALIGNMENT_OPTIONS" :key="opt" class="radio-option">
                <input type="radio" :value="opt" :checked="alignment === opt" @change="setDesign('alignment', opt)" />
                <span>{{ opt }}</span>
              </label>
            </div>
          </div>

          <div class="design-field-row">
            <div class="design-field">
              <label class="field-label">Item spacing (px)</label>
              <div class="slider-row">
                <input
                  type="range"
                  min="0"
                  max="120"
                  step="1"
                  :value="itemSpacing"
                  @input="setDesign('itemSpacing', Number($event.target.value))"
                />
                <input
                  type="number"
                  min="0"
                  max="120"
                  :value="itemSpacing"
                  class="field number-field"
                  @input="setDesign('itemSpacing', clampItemSpacing($event.target.value))"
                />
              </div>
            </div>
            <div class="design-field">
              <label class="field-label">Item max-height (px)</label>
              <div class="slider-row">
                <input
                  type="range"
                  min="20"
                  max="400"
                  step="5"
                  :value="itemMaxHeight"
                  @input="setDesign('itemMaxHeight', Number($event.target.value))"
                />
                <input
                  type="number"
                  min="20"
                  max="400"
                  :value="itemMaxHeight"
                  class="field number-field"
                  @input="setDesign('itemMaxHeight', clampMaxHeight($event.target.value))"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template v-if="socialMode" #admin-design-colors>
      <div class="design-controls">
        <div class="design-group">
          <div class="design-group-title">Social Mode</div>
          <div class="design-field">
            <label class="field-label">Icon color</label>
            <div class="color-control-row">
              <VueColorPicker
                :model-value="hexOrDefault(iconColor, '#334155')"
                fallback-color="#334155"
                :size="28"
                @update:model-value="setIconColor($event)"
              />
              <ColorLinkPicker
                :model-value="iconColorLink"
                :options="baseColorOptions"
                :button-size="24"
                @link="applyIconColorLink($event)"
              />
              <button
                v-if="iconColor || iconColorLink"
                class="clear-btn"
                type="button"
                title="Clear"
                @click="setIconColor(null)"
              >
                &times;
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template #admin-content>
      <div v-if="editing" class="editor">
        <SectionListEditor
          :items="draft"
          :selected-index="expandedItem"
          :add-label="t.add"
          :save-label="t.save"
          :remove-label="t.remove"
          clear-label="Clear All"
          :show-clear="true"
          @select="expandedItem = $event"
          @add="addItem"
          @save="saveItems"
          @remove="removeItem"
          @clear="clearAll"
          @reorder="onReorder"
        >
          <template #item="{ item, index }">
            <div class="item-thumb item-thumb--media">
              <div class="thumb-img-wrap" title="Click to expand">
                <font-awesome-icon
                  v-if="socialMode && item.icon"
                  :icon="resolveFaIcon(item)"
                  class="thumb-icon"
                />
                <ResponsiveImage
                  v-else-if="item.imageUrl"
                  :src="item.imageUrl"
                  :image-data="item"
                  alt=""
                  class="thumb-img"
                  loading="lazy"
                  decoding="async"
                />
                <div v-else class="thumb-empty">+</div>
              </div>
              <span class="thumb-label">
                {{ item.title?.de || item.title?.en || `#${index + 1}` }}
              </span>
            </div>
          </template>

          <template #editor="{ item, index }">
            <div v-if="socialMode" class="icon-field">
              <label class="field-label">
                Icon
              </label>
              <LinkIconPicker
                v-model="draft[index]"
                :disabled="isLinkItemFieldLocked(index, 'icon') || isLinkItemFieldLocked(index, 'iconPack')"
              />
            </div>

            <div class="title-fields-row">
              <div class="lang-section">
                <div class="lang-header">
                  {{ t.german }} (DE)
                </div>
                <input
                  v-model="item.title.de"
                  class="field"
                  placeholder="Title (DE) — also used as alt text"
                  :disabled="isLinkItemFieldLocked(index, 'title.de')"
                  :title="isLinkItemFieldLocked(index, 'title.de') ? integrationLockedHint : undefined"
                />
              </div>
              <div class="lang-section">
                <div class="lang-header">
                  {{ t.english }} (EN)
                </div>
                <input
                  v-model="item.title.en"
                  class="field"
                  placeholder="Title (EN) — also used as alt text"
                  :disabled="isLinkItemFieldLocked(index, 'title.en')"
                  :title="isLinkItemFieldLocked(index, 'title.en') ? integrationLockedHint : undefined"
                />
              </div>
            </div>

            <div class="image-field">
              <label class="field-label">
                Link URL (optional)
              </label>
              <input
                v-model="item.linkUrl"
                class="field"
                placeholder="https://..."
                :disabled="isLinkItemFieldLocked(index, 'linkUrl')"
                :title="isLinkItemFieldLocked(index, 'linkUrl') ? integrationLockedHint : undefined"
              />
            </div>

            <div v-if="!socialMode" class="image-field">
              <label class="field-label">
                Image
              </label>
              <div class="image-actions">
                <button
                  class="btn-primary small"
                  type="button"
                  :disabled="isLinkItemFieldLocked(index, 'imageUrl')"
                  :title="isLinkItemFieldLocked(index, 'imageUrl') ? integrationLockedHint : undefined"
                  @click="openMediaPicker(index, { direct: false })"
                >
                  {{ item.imageUrl ? "Replace" : "Select" }}
                </button>
                <button
                  v-if="item.imageUrl"
                  class="btn-secondary small"
                  type="button"
                  :disabled="isLinkItemFieldLocked(index, 'imageUrl')"
                  :title="isLinkItemFieldLocked(index, 'imageUrl') ? integrationLockedHint : undefined"
                  @click="clearItemImage(index)"
                >
                  Clear
                </button>
              </div>
            </div>
          </template>
        </SectionListEditor>
      </div>
    </template>
  </SectionBase>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useStore } from "../../store/store.js";
import { useListEditorMediaPicker } from "../../composables/useListEditorMediaPicker.js";
import { buildColorLinkOptions, resolveLinkedColor } from "../../utils/colorLinkOptions.js";
import { resolveBackendResponsiveImagePayload } from "../../utils/responsiveImages.js";
import { resolveFallbackImageForIndex } from "../../utils/fallbackImages.js";
import { isSectionIntegrationFieldLocked } from "../../utils/sectionIntegrationFieldState.js";

import SectionBase from "./_BaseSection.vue";
import SectionListEditor from "../admin/section-editor/SectionListEditor.vue";
import LinkIconPicker from "../admin/section-editor/LinkIconPicker.vue";
import MediaLibrary from "../ui/MediaLibrary.vue";
import ResponsiveImage from "../ui/ResponsiveImage.vue";
import ColorLinkPicker from "../ui/color/ColorLinkPicker.vue";
import VueColorPicker from "../ui/color/VueColorPicker.vue";

const ALIGNMENT_OPTIONS = ["left", "center", "right"];

const props = defineProps({
  sectionKey: { type: String, default: "links" },
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

function linkItemFieldPath(index, fieldPath) {
  const normalizedFieldPath = String(fieldPath || "").trim();
  const numericIndex = Number(index);
  const resolvedIndex = Number.isInteger(numericIndex) && numericIndex >= 0 ? numericIndex : 0;
  return normalizedFieldPath
    ? `items[${resolvedIndex}].${normalizedFieldPath}`
    : `items[${resolvedIndex}]`;
}

function isLinkItemFieldLocked(index, fieldPath, options = {}) {
  return state.isAdmin && isSectionIntegrationFieldLocked(section.value, linkItemFieldPath(index, fieldPath), options);
}

const hideItemTitle = computed(() => Boolean(section.value?.hideItemTitle));
const alignment = computed(() => {
  const a = section.value?.alignment;
  return ALIGNMENT_OPTIONS.includes(a) ? a : "center";
});
const itemMaxHeight = computed(() => {
  const n = Number(section.value?.itemMaxHeight);
  return Number.isFinite(n) && n > 0 ? Math.max(20, Math.min(400, n)) : 100;
});
const itemSpacing = computed(() => {
  const n = Number(section.value?.itemSpacing);
  return Number.isFinite(n) ? Math.max(0, Math.min(120, Math.round(n))) : 16;
});
const nonSocialItemMaxWidth = computed(() => {
  const n = Number(section.value?.nonSocialItemMaxWidth);
  return Number.isFinite(n) ? Math.max(0, Math.min(1200, Math.round(n))) : 0;
});
const socialMode = computed(() => Boolean(section.value?.socialMode));
const hideIconsWithoutLinks = computed(() => Boolean(section.value?.hideIconsWithoutLinks));
const showAdminHiddenLinkHints = computed(() =>
  state.isAdmin && !state.previewMode
);

function sectionVal(prop) {
  const key = effectiveKey.value;
  const fromState = state.sectionsData?.[key]?.[prop];
  if (fromState !== undefined) return fromState ?? null;
  return section.value?.[prop] ?? null;
}

const iconColor = computed(() => sectionVal("iconColor"));
const iconColorLink = computed(() => sectionVal("iconColorLink"));

const baseColorOptions = computed(() =>
  buildColorLinkOptions(state.design, {
    includeTransparent: false,
    parameterConfigs: state.adminDesignConfig?.parameters,
  })
);

function resolveBaseColor(linkKey) {
  return resolveLinkedColor(state.design, linkKey, state.adminDesignConfig?.parameters);
}

const resolvedIconColor = computed(() => {
  if (iconColorLink.value) {
    const linked = resolveBaseColor(iconColorLink.value);
    if (linked) return linked;
  }
  const raw = String(iconColor.value || "").trim();
  return raw || null;
});

const gridStyle = computed(() => ({
  justifyContent: alignment.value === "left" ? "flex-start"
    : alignment.value === "right" ? "flex-end"
    : "center",
  gap: `${itemSpacing.value}px`,
}));

const itemStyle = computed(() => ({
  "--link-max-height": `${itemMaxHeight.value}px`,
  "--link-item-max-width": !socialMode.value && nonSocialItemMaxWidth.value > 0
    ? `${nonSocialItemMaxWidth.value}px`
    : "none",
}));

const imgStyle = computed(() => ({
  height: `${itemMaxHeight.value}px`,
  width: "auto",
  maxHeight: `${itemMaxHeight.value}px`,
  maxWidth: "100%",
  objectFit: "contain",
  display: "block",
}));

const iconStyle = computed(() => {
  const style = {
    fontSize: `${Math.round(itemMaxHeight.value * 0.7)}px`,
    lineHeight: 1,
  };
  if (resolvedIconColor.value) {
    style.color = resolvedIconColor.value;
  }
  return style;
});

const editing = ref(false);
const expandedItem = ref(-1);
const draft = ref([]);
const {
  showMediaPicker,
  openMediaPicker,
  closeMediaPicker,
  consumeMediaPickerSelectionContext,
} = useListEditorMediaPicker();

watch(() => state.isAdmin, (val) => {
  if (!val && editing.value) {
    // Keep draft values until unmount autosave has completed; clearing here
    // can race with SectionListEditor autosave and persist an empty list.
    editing.value = false;
  }
});

watch(currentAdminTab, (tab) => {
  if (!state.isAdmin) return;
  if (tab === "content") startEdit();
  else editing.value = false;
}, { immediate: true });

watch(
  () => JSON.stringify(section.value?.items || []),
  () => {
    if (!state.isAdmin) return;
    if (currentAdminTab.value !== "content") return;
    if (isLinkDraftInSyncWithSection()) return;
    const prev = expandedItem.value;
    startEdit();
    if (prev >= 0 && prev < draft.value.length) expandedItem.value = prev;
  }
);

function fieldPath(index, path) {
  const idx = Number.isInteger(Number(index)) && Number(index) >= 0 ? Number(index) : 0;
  return path ? `items[${idx}].${path}` : `items[${idx}]`;
}

const displayItems = computed(() => {
  return normalizeEditableLinkItems(section.value?.items)
    .filter((item) => shouldDisplayLinkItem(item));
});

function firstNonEmptyString(...values) {
  for (const value of values) {
    if (value !== null && typeof value === "object") continue;
    const text = String(value ?? "").trim();
    if (text === "[object Object]" || text.toLowerCase() === "null") continue;
    if (text) return text;
  }
  return "";
}

function normalizeLinkTitle(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return {
      de: String(value.de || "").trim(),
      en: String(value.en || "").trim(),
    };
  }
  const text = String(value || "").trim();
  return { de: text, en: text };
}

function normalizeLinkItem(item, fallbackId = "") {
  const source = item && typeof item === "object" ? item : {};
  const iconPackValue = firstNonEmptyString(source.iconPack);
  return {
    id: firstNonEmptyString(source.id, fallbackId),
    imageUrl: firstNonEmptyString(source.imageUrl, source.logoUrl, source.thumbnailUrl),
    responsiveVariants: Array.isArray(source.responsiveVariants) ? source.responsiveVariants : [],
    icon: firstNonEmptyString(source.icon),
    iconPack: iconPackValue === "solid" ? "solid" : "brands",
    title: normalizeLinkTitle(source.title ?? source.name),
    linkUrl: firstNonEmptyString(source.linkUrl, source.href, source.url),
  };
}

function normalizeEditableLinkItems(items) {
  const source = Array.isArray(items) ? items : [];
  return source.map((item, index) => normalizeLinkItem(item, `link-${index + 1}`));
}

function hasPersistableLinkItemContent(item) {
  return Boolean(
    item?.id
    || item?.imageUrl
    || item?.icon
    || item?.linkUrl
    || item?.title?.de
    || item?.title?.en
  );
}

function shouldDisplayLinkItem(item) {
  if (item?.imageUrl) return true;
  if (item?.icon && showIcon(item)) return true;
  return !hideItemTitle.value
    && Boolean(localizedText(item?.title))
    && hasLinkUrl(item?.linkUrl);
}

function resolveLinkItemImageData(item, index = 0) {
  const imageUrl = String(item?.imageUrl || "").trim();
  if (imageUrl) return item;
  if (String(item?.icon || "").trim()) {
    return {
      ...item,
      imageUrl: "",
      responsiveVariants: [],
    };
  }
  const fallback = resolveFallbackImageForIndex(state.mediaFallbacks, index);
  if (!fallback?.imageUrl) {
    return {
      ...item,
      imageUrl: "",
      responsiveVariants: [],
    };
  }
  return {
    ...item,
    imageUrl: fallback.imageUrl,
    responsiveVariants: Array.isArray(fallback.responsiveVariants) ? fallback.responsiveVariants : [],
  };
}

function resolveLinkItemImageUrl(item, index = 0) {
  return String(resolveLinkItemImageData(item, index)?.imageUrl || "").trim();
}

function toPersistedLinkItems(items) {
  return normalizeEditableLinkItems(items).filter((item) => hasPersistableLinkItemContent(item));
}

function isLinkDraftInSyncWithSection() {
  return JSON.stringify(toPersistedLinkItems(section.value?.items))
    === JSON.stringify(toPersistedLinkItems(draft.value));
}

function resolveMediaSelectionImageUrl(selection) {
  const payload = resolveBackendResponsiveImagePayload(selection, {
    urlKeys: ["url", "src", "href"],
  });
  return payload.url || "";
}

function showIcon(item) {
  if (!socialMode.value || !item?.icon) return false;
  if (isAdminHiddenLinkIcon(item)) return true;
  if (!hideIconsWithoutLinks.value) return true;
  return hasLinkUrl(item.linkUrl);
}

function isAdminHiddenLinkIcon(item) {
  return showAdminHiddenLinkHints.value
    && socialMode.value
    && hideIconsWithoutLinks.value
    && Boolean(item?.icon)
    && !hasLinkUrl(item?.linkUrl);
}

function resolveFaIcon(item) {
  const pack = (item.iconPack || "brands") === "brands" ? "fab" : "fas";
  return [pack, item.icon];
}

function clampMaxHeight(raw) {
  const n = Number(raw);
  if (!Number.isFinite(n)) return 100;
  return Math.max(20, Math.min(400, Math.round(n)));
}

function clampItemSpacing(raw) {
  const n = Number(raw);
  if (!Number.isFinite(n)) return 16;
  return Math.max(0, Math.min(120, Math.round(n)));
}

function clampNonSocialItemMaxWidth(raw) {
  const n = Number(raw);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(1200, Math.round(n)));
}

function normalizeHref(url) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  if (/^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(raw) || raw.startsWith("//")) return raw;
  if (raw.startsWith("/") || raw.startsWith("#") || raw.startsWith("?")) return raw;
  return `https://${raw}`;
}

function hasLinkUrl(url) {
  return Boolean(normalizeHref(url));
}

function hasHref(url) {
  return !state.isAdmin && hasLinkUrl(url);
}
function linkHref(url) {
  const href = normalizeHref(url);
  return state.isAdmin || !href ? undefined : href;
}
function linkTarget(url) {
  return hasHref(url) ? "_blank" : undefined;
}
function linkRel(url) {
  return hasHref(url) ? "noopener noreferrer" : undefined;
}
function handleClick(e, url) {
  if (!hasHref(url)) e.preventDefault();
}

function startEdit() {
  expandedItem.value = -1;
  draft.value = normalizeEditableLinkItems(section.value?.items);
  editing.value = true;
}

function addItem() {
  draft.value.push({
    id: String(Date.now() + Math.random()),
    imageUrl: "",
    icon: "",
    iconPack: "brands",
    title: { de: "", en: "" },
    linkUrl: "",
  });
  expandedItem.value = draft.value.length - 1;
  saveItems({ flush: true });
}

function removeItem(index) {
  if (index < 0 || index >= draft.value.length) return;
  draft.value.splice(index, 1);
  if (expandedItem.value === index) {
    expandedItem.value = draft.value.length ? Math.min(index, draft.value.length - 1) : -1;
  } else if (expandedItem.value > index) {
    expandedItem.value -= 1;
  }
}

function onReorder({ items }) {
  if (Array.isArray(items)) {
    draft.value = items;
    saveItems();
  }
}

function onMediaSelect(selection) {
  const { index, direct } = consumeMediaPickerSelectionContext();
  if (index >= 0 && index < draft.value.length) {
    if (isLinkItemFieldLocked(index, "imageUrl")) {
      closeMediaPicker();
      return;
    }
    const payload = resolveBackendResponsiveImagePayload(selection, {
      urlKeys: ["url", "src", "href"],
    });
    draft.value[index].imageUrl = resolveMediaSelectionImageUrl(selection);
    draft.value[index].responsiveVariants = payload.responsiveVariants;
    if (direct) saveItems();
  }
  closeMediaPicker();
}

function clearItemImage(index) {
  if (index < 0 || index >= draft.value.length) return;
  if (isLinkItemFieldLocked(index, "imageUrl")) return;
  draft.value[index].imageUrl = "";
  draft.value[index].responsiveVariants = [];
}

function saveItems(options = {}) {
  const filtered = toPersistedLinkItems(draft.value);
  updateSection(effectiveKey.value, { items: filtered });
  if (options?.flush) {
    void saveSectionByKey(effectiveKey.value, { revisionKind: "content" });
  }
}

function clearAll() {
  draft.value = [];
  expandedItem.value = -1;
  saveItems();
}

function setDesign(key, value) {
  updateSection(effectiveKey.value, { [key]: value }, { revisionKind: "design" });
}

function hexOrDefault(value, fallback) {
  const raw = String(value || "").trim();
  if (/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(raw)) return raw;
  return fallback;
}

function setIconColor(value) {
  updateSection(
    effectiveKey.value,
    { iconColor: value, iconColorLink: null },
    { revisionKind: "design" }
  );
}

function applyIconColorLink(baseKey) {
  const resolved = resolveBaseColor(baseKey);
  updateSection(
    effectiveKey.value,
    { iconColor: resolved, iconColorLink: baseKey || null },
    { revisionKind: "design" }
  );
}
</script>

<style scoped>
.links-grid {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
}

.links-grid--empty {
  min-height: 80px;
  justify-content: center;
}

.empty-hint {
  font-size: 13px;
  font-weight: 600;
  color: var(--muted, #64748b);
}

.link-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-decoration: none;
  transition: transform 0.2s ease;
  color: inherit;
  position: relative;
}

.link-item--non-social {
  max-width: var(--link-item-max-width, none);
}

.link-item.no-link {
  cursor: default;
}

.link-item--admin-hidden .link-icon,
.link-item--admin-hidden .link-title {
  opacity: 0.3;
}

.link-item--admin-hidden::after {
  content: 'hidden';
  position: absolute;
  top: 2px;
  right: 0;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--accent, #4f46e5);
  background: rgba(79, 70, 229, 0.08);
  padding: 1px 5px;
  border-radius: 3px;
}

.link-item:hover {
  transform: scale(1.05);
}

.link-item img {
  max-width: 100%;
  display: block;
}

.link-image {
  min-width: 1px;
  min-height: 1px;
}

.link-icon {
  color: currentColor;
}

.link-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted, #64748b);
  text-align: center;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-thumb--media {
  display: flex;
  align-items: center;
  gap: 8px;
}

.thumb-img-wrap {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  border-radius: 6px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.15));
  flex-shrink: 0;
  font-size: 20px;
}

.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.thumb-empty {
  color: var(--muted, #94a3b8);
  font-size: 22px;
  font-weight: 600;
}

.thumb-icon {
  color: var(--text, #2b0c5c);
}

.thumb-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text, #2b0c5c);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.design-controls {
  display: grid;
  gap: 14px;
  padding: 8px 0;
}

.design-group {
  display: grid;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.12));
  border-radius: 10px;
  background: #fff;
}

.design-group-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted, rgba(43, 12, 92, 0.6));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.design-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text, #2b0c5c);
  cursor: pointer;
}

.design-checkbox input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.design-field {
  display: grid;
  gap: 6px;
}

.design-field-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.radio-row {
  display: flex;
  gap: 16px;
}

.radio-option {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  text-transform: capitalize;
  cursor: pointer;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.slider-row input[type="range"] {
  flex: 1;
}

.color-control-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.number-field {
  width: 80px;
  flex: none;
}

@media (max-width: 720px) {
  .design-field-row {
    grid-template-columns: minmax(0, 1fr);
  }
}

.clear-btn {
  width: 24px;
  height: 24px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.2));
  border-radius: 6px;
  background: #fff;
  color: var(--text, #2b0c5c);
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  display: inline-grid;
  place-items: center;
}

.field-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted, rgba(43, 12, 92, 0.55));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field-hint {
  font-size: 11px;
  color: var(--muted, #64748b);
}

.editor {
  display: grid;
  gap: 10px;
}

.image-field,
.icon-field {
  display: grid;
  gap: 4px;
}

.title-fields-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.image-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.lang-section {
  display: grid;
  gap: 4px;
}

.lang-header {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted, rgba(43, 12, 92, 0.55));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field {
  flex: 1;
  min-width: 0;
  border-radius: 8px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.20));
  background: #fff;
  padding: 8px 12px;
  outline: none;
  color: var(--text, #2b0c5c);
}

@media (max-width: 640px) {
  .title-fields-row {
    grid-template-columns: 1fr;
  }

  .image-actions {
    align-items: stretch;
  }

  .image-actions button {
    width: 100%;
  }
}
</style>
