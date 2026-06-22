<template>
  <article class="card" :data-section-key="effectiveKey">
    <slot name="background" :section="section" :section-key="effectiveKey" />
    <div v-if="showPublicHiddenBadge" class="section-public-hidden-badge">public hidden</div>
    <div
      v-if="props.titleOutsideTextLayout && !titleHidden"
      class="section-header"
    >
      <div :class="{ 'hidden-hint': titleHiddenAdmin }">
        <EditableText
            :model-value="section?.title"
            :is-admin="state.isAdmin"
            as="h2"
            :plain-view="!state.isAdmin"
            :disabled="titleIntegrationLocked"
            :disabled-hint="integrationLockedHint"
            @update:model-value="updateTitle"
        >
          {{ sectionTitleDisplay }}
        </EditableText>
      </div>
    </div>
    <slot name="before-text" :section="section" :section-key="effectiveKey" />
    <div class="section-text-layout">
      <slot name="media-left" :section="section" :section-key="effectiveKey" />
      <div class="section-text-layout__text">
        <div v-if="!props.titleOutsideTextLayout" class="section-header">
          <div v-if="!titleHidden" :class="{ 'hidden-hint': titleHiddenAdmin }">
            <EditableText
                :model-value="section?.title"
                :is-admin="state.isAdmin"
                as="h2"
                :plain-view="!state.isAdmin"
                :disabled="titleIntegrationLocked"
                :disabled-hint="integrationLockedHint"
                @update:model-value="updateTitle"
            >
              {{ sectionTitleDisplay }}
            </EditableText>
          </div>
        </div>
        <div v-if="props.showDescription && !bodyHidden" class="section-description" :class="{ 'hidden-hint': bodyHiddenAdmin }">
          <EditableRichText
              :model-value="section?.body"
              :is-admin="state.isAdmin"
              as="div"
              display-class="p"
              :plain-view="!state.isAdmin"
              :placeholder="bodyPlaceholder"
              :disabled="bodyIntegrationLocked"
              :disabled-hint="integrationLockedHint"
              @update:model-value="updateBody"
          />
        </div>
      </div>
      <slot name="media-right" :section="section" :section-key="effectiveKey" />
    </div>
    <slot name="after-text" :section="section" :section-key="effectiveKey" />
    <div class="section-content">
      <slot :section="section" :section-key="effectiveKey" />
    </div>
    <div
      v-if="sectionCtaButtons.length > 0"
      class="section-cta-actions"
      :style="sectionCtaAlignmentStyle"
    >
      <EditableButton
        v-for="(btn, index) in sectionCtaButtons"
        :key="`section-cta-${index}`"
        :model-value="btn"
        :is-admin="false"
        :button-class="ctaButtonClass(btn, index)"
        :button-style="ctaButtonStyle(btn, index)"
        placeholder="Button"
      />
    </div>
    <SectionAdminTabs
      v-if="showAdminTabs"
      :section-key="effectiveKey"
      :simple-design-body="adminSimpleDesignBody"
      :show-section-generic="adminShowSectionGeneric"
      :show-design="adminShowDesign && (state.canDesign || isTemplateBuilderPage)"
      :show-content="adminShowContent"
      :show-output="showSectionTemplateOutput"
      :show-template="!!$slots['admin-template']"
      :show-history="adminShowHistory"
      :show-notes="adminShowNotes"
    >
      <template v-if="$slots['admin-design-params']" #design-params>
        <slot name="admin-design-params" />
      </template>
      <template v-if="$slots['admin-design-colors']" #design-colors>
        <slot name="admin-design-colors" />
      </template>
      <template v-if="$slots['admin-design']" #design>
        <slot name="admin-design" />
      </template>
      <template #content>
        <SectionIntegrationImporter
          v-if="showIntegrationImporter"
          :section-key="effectiveKey"
          :section-data="section"
          :section-type="section?.sectionType"
          :apply-content-patch="adminIntegrationApplyContentPatch"
          :persist-mapping-patch="adminIntegrationPersistMappingPatch"
        />
        <slot name="admin-content">
          <p class="admin-empty-hint">Edit this section inline in the preview.</p>
        </slot>
        <details class="admin-section section-cta-editor-wrap">
          <summary class="admin-section-title">CTA Buttons</summary>
          <div class="admin-section-content">
            <SectionListEditor
              :items="sectionCtaDraft"
              :selected-index="sectionCtaExpandedItem"
              :add-label="t.add"
              :save-label="t.save"
              :remove-label="t.remove"
              :add-disabled="sectionCtaAddDisabled"
              :min-item-width="160"
              @select="sectionCtaExpandedItem = $event"
              @add="addSectionCtaItem"
              @save="saveSectionCtaItems"
              @remove="removeSectionCtaItem"
            >
              <template #item="{ item, index }">
                <div class="item-thumb section-cta-thumb">
                  <span class="section-cta-thumb__title">
                    {{ item.text.de || item.text.en || `Button ${index + 1}` }}
                  </span>
                  <span class="section-cta-thumb__meta">{{ sectionCtaStyleLabel(item.buttonType, index) }}</span>
                </div>
              </template>

              <template #editor="{ item, index }">
                <div class="section-cta-editor">
                  <div class="section-cta-editor__lang-grid">
                    <div class="section-cta-editor__lang">
                      <label class="section-cta-editor__label">{{ t.german }} (DE)</label>
                      <input
                        v-model="item.text.de"
                        class="section-cta-editor__field"
                        type="text"
                        placeholder="Button label..."
                        :disabled="isCtaFieldLocked(index, 'text.de')"
                        :title="isCtaFieldLocked(index, 'text.de') ? integrationLockedHint : undefined"
                      />
                    </div>
                    <div class="section-cta-editor__lang">
                      <label class="section-cta-editor__label">{{ t.english }} (EN)</label>
                      <input
                        v-model="item.text.en"
                        class="section-cta-editor__field"
                        type="text"
                        placeholder="Button label..."
                        :disabled="isCtaFieldLocked(index, 'text.en')"
                        :title="isCtaFieldLocked(index, 'text.en') ? integrationLockedHint : undefined"
                      />
                    </div>
                  </div>

                  <div class="section-cta-editor__meta-grid">
                    <div class="section-cta-editor__lang">
                      <label class="section-cta-editor__label">Link URL</label>
                      <input
                        v-model="item.url"
                        class="section-cta-editor__field"
                        type="url"
                        placeholder="https://..."
                        :disabled="isCtaFieldLocked(index, 'url')"
                        :title="isCtaFieldLocked(index, 'url') ? integrationLockedHint : undefined"
                      />
                      <div class="section-cta-download-picker">
                        <button
                          type="button"
                          class="section-cta-download-picker__load"
                          :disabled="sectionCtaDownloadLinksLoading || isCtaFieldLocked(index, 'url')"
                          @click="loadSectionCtaDownloadLinks"
                        >
                          {{ sectionCtaDownloadLinksLoading ? "Loading..." : (sectionCtaDownloadLinksLoaded ? "Refresh downloads" : "Choose download") }}
                        </button>
                        <select
                          v-if="sectionCtaDownloadLinkOptions.length"
                          class="section-cta-editor__field"
                          :value="item.url"
                          :disabled="isCtaFieldLocked(index, 'url')"
                          @focus="loadSectionCtaDownloadLinks"
                          @change="applySectionCtaDownloadLink(item, $event.target.value)"
                        >
                          <option value="">Select existing download...</option>
                          <option
                            v-for="option in sectionCtaDownloadLinkOptions"
                            :key="option.id"
                            :value="option.url"
                          >
                            {{ option.label }}
                          </option>
                        </select>
                        <p
                          v-else-if="sectionCtaDownloadLinksLoaded && !sectionCtaDownloadLinksLoading"
                          class="section-cta-download-picker__empty"
                        >
                          No downloadable media links found.
                        </p>
                      </div>
                    </div>
                    <div class="section-cta-editor__lang">
                      <label class="section-cta-editor__label">Button Style</label>
                      <select
                        v-model="item.buttonType"
                        class="section-cta-editor__field"
                        :disabled="isCtaFieldLocked(index, 'buttonType')"
                        :title="isCtaFieldLocked(index, 'buttonType') ? integrationLockedHint : undefined"
                      >
                        <option
                          v-for="opt in sectionCtaButtonStyleOptions"
                          :key="opt.id"
                          :value="opt.id"
                        >
                          {{ opt.label }}
                        </option>
                      </select>
                    </div>
                  </div>
                </div>
              </template>
            </SectionListEditor>
          </div>
        </details>
      </template>
      <template #output>
        <slot name="admin-output">
          <SectionTemplateOutputMapping
            :section-key="effectiveKey"
            :section-data="section"
          />
        </slot>
      </template>
      <template #template>
        <slot name="admin-template" />
      </template>
    </SectionAdminTabs>
  </article>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useStore } from "../../store/store.js";
import EditableText from "../ui/EditableText.vue";
import EditableRichText from "../ui/EditableRichText.vue";
import EditableButton from "../ui/EditableButton.vue";
import SectionAdminTabs from "../admin/section-editor/SectionAdminTabs.vue";
import SectionIntegrationImporter from "../admin/section-editor/SectionIntegrationImporter.vue";
import SectionTemplateOutputMapping from "../admin/section-editor/SectionTemplateOutputMapping.vue";
import SectionListEditor from "../admin/section-editor/SectionListEditor.vue";
import { isSectionHiddenInPublicBecauseEmptyList } from "../../utils/sectionVisibilityRules.js";
import { getButtonTypeClassName, getButtonTypeInlineStyle } from "../../utils/buttonTypeStyle.js";
import { isSectionIntegrationFieldLocked } from "../../utils/sectionIntegrationFieldState.js";
import { listAssets } from "../../services/api.js";

const props = defineProps({
  sectionKey: { type: String, required: true },
  sectionData: { type: Object, default: null },
  adminTabsVisible: { type: Boolean, default: true },
  adminSimpleDesignBody: { type: Boolean, default: false },
  adminShowSectionGeneric: { type: Boolean, default: true },
  adminShowDesign: { type: Boolean, default: true },
  adminShowContent: { type: Boolean, default: true },
  adminShowIntegrationImporter: { type: Boolean, default: true },
  adminIntegrationApplyContentPatch: { type: Function, default: null },
  adminIntegrationPersistMappingPatch: { type: Function, default: null },
  adminShowHistory: { type: Boolean, default: true },
  adminShowNotes: { type: Boolean, default: true },
  showDescription: { type: Boolean, default: true },
  titleOutsideTextLayout: { type: Boolean, default: false },
});

const { state, updateSection, saveSectionByKey, t } = useStore();

const SECTION_MAX_CTA_BUTTONS = 4;
const integrationLockedHint = "Managed by integration import.";
const CTA_BUTTON_META_FLAG_KEYS = ["__autoBlogShowAllCta"];
const sectionCtaDraft = ref([]);
const sectionCtaExpandedItem = ref(-1);
const sectionCtaDownloadLinksLoading = ref(false);
const sectionCtaDownloadLinksLoaded = ref(false);
const sectionCtaDownloadLinkOptions = ref([]);

const effectiveKey = computed(() => props.sectionKey);
const isTemplateBuilderPage = computed(() =>
  String(state.pageSlug || "").startsWith("__template_")
);
const isTemplateSectionBuilderPage = computed(() =>
  String(state.pageSlug || "").startsWith("__template_section__/")
);

// Default titles by section type (fallback if backend doesn't provide one)
const DEFAULT_TITLES = {
  text: { de: "Text", en: "" },
  text_image: { de: "Text mit Bild", en: "Text Image" },
  video: { de: "Video", en: "" },
  faq: { de: "FAQ", en: "FAQ" },
  links: { de: "Links", en: "Links" },
  ticker: { de: "Ticker", en: "" },
  gallery: { de: "Galerie", en: "Gallery" },
  blog: { de: "Blog", en: "" },
  markdown: { de: "Markdown", en: "" },
  html: { de: "HTML", en: "" },
  map: { de: "Karte", en: "Map" },
  tiles: { de: "Kacheln", en: "Tiles" },
  program: { de: "Programm", en: "Program" },
};

const section = computed(() => {
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});

const sectionTitleDisplay = computed(() => {
  const title = section.value?.title;
  const titleDe = String(title?.de ?? "").trim();
  const titleEn = String(title?.en ?? "").trim();
  if (titleDe || titleEn) {
    if (state.lang === "de") return titleDe || titleEn;
    return titleEn || titleDe;
  }

  const sectionType = section.value?.sectionType || props.sectionKey.split("_")[0];
  const fallback = DEFAULT_TITLES[sectionType] || { de: sectionType, en: sectionType };
  const fallbackDe = String(fallback.de ?? "").trim();
  const fallbackEn = String(fallback.en ?? "").trim();
  if (state.lang === "de") return fallbackDe || fallbackEn;
  return fallbackEn || fallbackDe;
});

const overrides = computed(() => {
  const ov = state.sectionDesignOverrides?.[props.sectionKey];
  if (!ov || ov._active === false) return null;
  return ov;
});

function getSectionHideState(constantKey) {
  const generic = section.value?.sectionGeneric;
  if (!generic || typeof generic !== "object") return 0;
  if (constantKey === "hideSectionHeader" && generic.hideSectionHeaderHard === true) return 2;
  if (constantKey === "hideSectionDescription" && generic.hideSectionDescriptionHard === true) return 2;
  if (generic[constantKey] === true) return 1;
  return 0;
}

const titleHideState = computed(() => getSectionHideState("hideSectionHeader"));
const bodyHideState = computed(() => getSectionHideState("hideSectionDescription"));
const titleHiddenOverride = computed(() => titleHideState.value > 0);
const bodyHiddenOverride = computed(() => bodyHideState.value > 0);
const titleHardHiddenOverride = computed(() => titleHideState.value === 2);
const bodyHardHiddenOverride = computed(() => bodyHideState.value === 2);

const titleHidden = computed(() => {
  if (state.isAdmin) return titleHardHiddenOverride.value;
  return titleHiddenOverride.value;
});
const bodyHidden = computed(() => {
  if (state.isAdmin) return bodyHardHiddenOverride.value;
  return bodyHiddenOverride.value;
});
const titleHiddenAdmin = computed(() =>
  state.isAdmin && !titleHardHiddenOverride.value && titleHiddenOverride.value
);
const bodyHiddenAdmin = computed(() =>
  state.isAdmin && !bodyHardHiddenOverride.value && bodyHiddenOverride.value
);
const bodyPlaceholder = computed(() =>
  state.lang === "de" ? "Keine Beschreibung verfügbar" : "No description available"
);
const showAdminTabs = computed(() => state.isAdmin && props.adminTabsVisible);
const showIntegrationImporter = computed(() =>
  state.isAdmin
  && state.canAdminGeneral
  && props.adminShowContent
  && props.adminShowIntegrationImporter
);
const showSectionTemplateOutput = computed(() =>
  state.isAdmin
  && state.canAdminGeneral
  && isTemplateSectionBuilderPage.value
);
const showPublicHiddenBadge = computed(() =>
  state.isAdmin
  && !state.previewMode
  && isSectionHiddenInPublicBecauseEmptyList(effectiveKey.value, state, section.value)
);
const titleIntegrationLocked = computed(() =>
  isSectionFieldLocked("title", { includeDescendants: true })
);
const bodyIntegrationLocked = computed(() =>
  isSectionFieldLocked("body", { includeDescendants: true })
);
const sectionCtaAddDisabled = computed(() =>
  sectionCtaDraft.value.length >= SECTION_MAX_CTA_BUTTONS
);
const sectionCtaButtons = computed(() => {
  const source = Array.isArray(section.value?.ctaButtons) ? section.value.ctaButtons : [];
  return source
    .map((item, index) => normalizeSectionCtaButton(item, index))
    .filter((item) => Boolean(item.text.de || item.text.en || item.url));
});
const sectionCtaButtonStyleOptions = computed(() => {
  const options = new Map();
  const instances = Array.isArray(state.adminDesignConfig?.buttonInstances)
    ? state.adminDesignConfig.buttonInstances
    : [];
  instances
    .filter((item) => item?.enabled && String(item?.id || "").trim())
    .forEach((item) => {
      const id = String(item.id).trim();
      options.set(id, String(item.label || id));
    });

  if (!options.size) {
    options.set("primary", "Primary");
    options.set("secondary", "Secondary");
  }
  if (!options.has("ghost")) options.set("ghost", "Ghost");

  (sectionCtaDraft.value || []).forEach((item, index) => {
    const type = normalizeCtaButtonType(item?.buttonType, index);
    if (!options.has(type)) options.set(type, formatButtonTypeLabel(type));
  });

  return Array.from(options.entries()).map(([id, label]) => ({ id, label }));
});
const sectionCtaAlignment = computed(() => {
  const value = String(section.value?.sectionGeneric?.buttonAlignment || "").trim().toLowerCase();
  return value === "left" || value === "right" ? value : "center";
});
const sectionCtaAlignmentStyle = computed(() => {
  const alignment = sectionCtaAlignment.value;
  if (alignment === "left") return { justifyContent: "flex-start", textAlign: "left" };
  if (alignment === "right") return { justifyContent: "flex-end", textAlign: "right" };
  return { justifyContent: "center", textAlign: "center" };
});

watch(
  () => section.value?.ctaButtons,
  () => {
    syncSectionCtaDraftFromSection();
  },
  { immediate: true, deep: true }
);

function updateTitle(value) {
  if (titleIntegrationLocked.value) return;
  updateSection(effectiveKey.value, { title: value });
}

function updateBody(value) {
  if (bodyIntegrationLocked.value) return;
  updateSection(effectiveKey.value, { body: value });
}

function isSectionFieldLocked(path, options = {}) {
  return state.isAdmin && isSectionIntegrationFieldLocked(section.value, path, options);
}

function ctaFieldPath(index, path) {
  const numericIndex = Number(index);
  const resolvedIndex = Number.isInteger(numericIndex) && numericIndex >= 0 ? numericIndex : 0;
  const normalizedPath = String(path || "").trim();
  return normalizedPath
    ? `ctaButtons[${resolvedIndex}].${normalizedPath}`
    : `ctaButtons[${resolvedIndex}]`;
}

function isCtaFieldLocked(index, path, options = {}) {
  return isSectionFieldLocked(ctaFieldPath(index, path), options);
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

function createSectionCtaDraftId() {
  return `section-cta-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function defaultCtaButtonType(index = 0) {
  return index === 0 ? "primary" : "secondary";
}

function normalizeCtaButtonType(type, index = 0) {
  const normalized = String(type || "").trim();
  return normalized || defaultCtaButtonType(index);
}

function readCtaButtonMetaFlags(item) {
  const source = item && typeof item === "object" ? item : {};
  const flags = {};
  for (const key of CTA_BUTTON_META_FLAG_KEYS) {
    if (source[key] === true) {
      flags[key] = true;
    }
  }
  return flags;
}

function formatButtonTypeLabel(type) {
  const normalized = String(type || "").trim();
  if (!normalized) return "Button";
  return normalized
    .replace(/[_-]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function normalizeSectionCtaButton(button, index = 0) {
  const item = button && typeof button === "object" ? button : {};
  return {
    id: String(item.id || createSectionCtaDraftId()),
    text: normalizeBilingualText(item.text),
    url: String(item.url || ""),
    buttonType: normalizeCtaButtonType(item.buttonType, index),
    ...readCtaButtonMetaFlags(item),
  };
}

function formatAssetDownloadOption(asset) {
  const filename = String(asset?.filename || "").trim();
  const fallback = String(asset?.download_url || asset?.url || "").trim();
  const label = filename || fallback || "Download";
  return {
    id: String(asset?.id || asset?.download_url || fallback || ""),
    label,
    url: String(asset?.download_url || "").trim(),
  };
}

async function loadSectionCtaDownloadLinks() {
  if (sectionCtaDownloadLinksLoading.value) return;
  sectionCtaDownloadLinksLoading.value = true;
  try {
    const options = [];
    let page = 1;
    let hasMore = true;
    while (hasMore && page <= 5) {
      const response = await listAssets({ page, pageSize: 100 });
      const items = Array.isArray(response?.items) ? response.items : [];
      for (const asset of items) {
        if (!asset?.downloadable || !String(asset?.download_url || "").trim()) continue;
        const option = formatAssetDownloadOption(asset);
        if (option.url && !options.some((entry) => entry.url === option.url)) {
          options.push(option);
        }
      }
      hasMore = Boolean(response?.has_more);
      page += 1;
    }
    sectionCtaDownloadLinkOptions.value = options;
    sectionCtaDownloadLinksLoaded.value = true;
  } catch (error) {
    console.error("Failed to load download links:", error);
    sectionCtaDownloadLinksLoaded.value = true;
  } finally {
    sectionCtaDownloadLinksLoading.value = false;
  }
}

function applySectionCtaDownloadLink(item, value) {
  const selectedUrl = String(value || "").trim();
  if (!item || !selectedUrl) return;
  item.url = selectedUrl;
}

function syncSectionCtaDraftFromSection() {
  const source = Array.isArray(section.value?.ctaButtons) ? section.value.ctaButtons : [];
  sectionCtaDraft.value = source.map((item, index) => normalizeSectionCtaButton(item, index));
  if (sectionCtaExpandedItem.value >= sectionCtaDraft.value.length) {
    sectionCtaExpandedItem.value = sectionCtaDraft.value.length - 1;
  }
  if (!sectionCtaDraft.value.length) {
    sectionCtaExpandedItem.value = -1;
  }
}

function addSectionCtaItem() {
  if (sectionCtaDraft.value.length >= SECTION_MAX_CTA_BUTTONS) return;
  sectionCtaDraft.value.push(
    normalizeSectionCtaButton(
      {
        text: { de: "", en: "" },
        url: "",
        buttonType: defaultCtaButtonType(sectionCtaDraft.value.length),
      },
      sectionCtaDraft.value.length
    )
  );
  sectionCtaExpandedItem.value = sectionCtaDraft.value.length - 1;
  saveSectionCtaItems({ flush: true });
}

function removeSectionCtaItem(index) {
  if (index < 0 || index >= sectionCtaDraft.value.length) return;
  sectionCtaDraft.value.splice(index, 1);
  if (sectionCtaExpandedItem.value === index) {
    sectionCtaExpandedItem.value = sectionCtaDraft.value.length
      ? Math.min(index, sectionCtaDraft.value.length - 1)
      : -1;
  } else if (sectionCtaExpandedItem.value > index) {
    sectionCtaExpandedItem.value -= 1;
  }
}

function saveSectionCtaItems(options = {}) {
  updateSection(
    effectiveKey.value,
    {
      ctaButtons: sectionCtaDraft.value.map((item, index) => ({
        text: normalizeBilingualText(item.text),
        url: String(item.url || ""),
        buttonType: normalizeCtaButtonType(item.buttonType, index),
        ...readCtaButtonMetaFlags(item),
      })),
    },
    { revisionKind: "content" }
  );
  if (options?.flush) {
    void saveSectionByKey(effectiveKey.value, { revisionKind: "content" });
  }
  syncSectionCtaDraftFromSection();
}

function sectionCtaStyleLabel(type, index = 0) {
  const normalizedType = normalizeCtaButtonType(type, index);
  const fromOptions = sectionCtaButtonStyleOptions.value.find((item) => item.id === normalizedType);
  return fromOptions?.label || formatButtonTypeLabel(normalizedType);
}

function ctaButtonClass(btn, index) {
  return getButtonTypeClassName(normalizeCtaButtonType(btn?.buttonType, index));
}

function ctaButtonStyle(btn, index) {
  return getButtonTypeInlineStyle(normalizeCtaButtonType(btn?.buttonType, index));
}
</script>


<style scoped>
.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: var(--section-content-justify, flex-start);
  position: relative;
  z-index: 10;
  text-align: var(--section-content-align, left);
}

.card {
  position: relative;
}

.section-public-hidden-badge {
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

.section-text-layout {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.section-text-layout__text {
  min-width: 0;
  flex: 1 1 auto;
}

.section-header :deep(h2) {
  margin: 0;
}

.hidden-hint {
  position: relative;
}

/* Keep the editor UI readable; only mute the rendered result text. */
.hidden-hint :deep(.editable .view),
.hidden-hint :deep(.editable-plain--admin) {
  opacity: 0.3;
}
.hidden-hint::after {
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

.admin-empty-hint {
  margin: 0;
  color: var(--admin-text-muted, #64748b);
  font-size: 12px;
}

.section-cta-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
  padding-top: 8px;
}

.section-cta-editor-wrap {
  margin-top: 12px;
}

.admin-section:not(:last-child) {
  margin-bottom: 0;
}

.admin-section-title {
  font-weight: 600;
  color: #374151;
  cursor: pointer;
  padding: 0.75rem;
  background: white;
  border-radius: 8px;
  list-style: none;
}

.admin-section-title::-webkit-details-marker {
  display: none;
}

.admin-section-title::before {
  content: "▸ ";
  color: #9ca3af;
}

details[open] .admin-section-title::before {
  content: "▾ ";
}

.admin-section-content {
  padding: 1rem;
  background: white;
  border-radius: 0 0 8px 8px;
  margin-top: -4px;
  gap: 10px;
  display: grid;
}

.section-cta-thumb {
  display: grid;
  gap: 4px;
}

.section-cta-thumb__title {
  font-size: 12px;
  font-weight: 700;
  color: var(--admin-text, #0f172a);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.section-cta-thumb__meta {
  font-size: 11px;
  color: var(--admin-text-muted, #64748b);
}

.section-cta-editor {
  display: grid;
  gap: 10px;
}

.section-cta-editor__lang-grid,
.section-cta-editor__meta-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
}

.section-cta-editor__lang {
  display: grid;
  gap: 6px;
}

.section-cta-editor__label {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: var(--admin-text-muted, #64748b);
}

.section-cta-editor__field {
  width: 100%;
  border: 1px solid var(--admin-border, #cbd5e1);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--admin-surface, #fff);
  color: var(--admin-text, #0f172a);
  font-size: 13px;
}

.section-cta-download-picker {
  display: grid;
  gap: 6px;
}

.section-cta-download-picker__load {
  justify-self: flex-start;
  border: 1px solid var(--admin-border, #cbd5e1);
  border-radius: 8px;
  padding: 6px 9px;
  background: var(--admin-surface, #fff);
  color: var(--admin-text, #0f172a);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.section-cta-download-picker__load:disabled {
  opacity: 0.65;
  cursor: wait;
}

.section-cta-download-picker__empty {
  margin: 0;
  color: var(--admin-text-muted, #64748b);
  font-size: 12px;
}
</style>
