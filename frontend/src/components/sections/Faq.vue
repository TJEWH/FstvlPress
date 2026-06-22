<template>
  <SectionBase :section-key="effectiveKey" :section-data="sectionForIntegration">
    <div @mouseenter="hover=true" @mouseleave="hover=false">
      <!-- VIEW -->
      <div
          class="qa"
      >
        <div
          v-for="group in faqRenderGroups"
          :key="group.key"
          class="faq-group"
          :style="groupStyle"
        >
          <h4 v-if="groupedFaqOutput" class="faq-group-heading">{{ group.label }}</h4>
          <div
            v-for="(it, idx) in group.items"
            :key="it.__renderId"
            class="faq-item"
            :class="{ 'is-open': openItems.has(it.__renderId), 'last-item': idx === group.items.length - 1 }"
            :style="itemStyle"
          >
            <button
              type="button"
              class="faq-question"
              :style="questionStyle"
              @click.stop="toggleFaqItem(it.__renderId)"
            >
              <h4 class="summary-text">{{ localizedText(it.q) }}</h4>
              <svg class="chevron" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
            <div class="answer-wrapper">
              <div class="p answer-content rich-render" :style="answerStyle" v-html="answerHtml(it.a)"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #admin-design-colors>
      <div class="admin-actions">
            <!-- Question color -->
            <div class="ctrl color-link-control">
              <span class="ctrl-label">Question</span>
              <VueColorPicker
                :model-value="hexOrDefault(questionColor, '#4f46e5')"
                fallback-color="#4f46e5"
                :preview-style="swatchStyle(resolveTextColor(questionColor, questionColorVariation), { rawColor: questionColor, linkKey: questionColorLink, treatEmptyAsHighContrast: true, baseRefColor: state.design.sectionBackgroundColor || '#ffffff', baseRefKey: 'sectionBackgroundColor', adminConfig: state.adminDesignConfig })"
                :size="28"
                @update:model-value="setQuestionColor($event)"
              />
              <ColorLinkPicker :model-value="questionColorLink" :options="textColorOptions" :button-size="24" @link="applyColorLink('question', $event)" />
              <select
                class="variation-select"
                :value="questionColorVariation"
                @change="setColorVariation('question', $event.target.value)"
              >
                <option v-for="variation in colorVariationOptions" :key="`question-${variation}`" :value="variation">
                  {{ variation }}%
                </option>
              </select>
              <button v-if="questionColor" class="clear-btn" type="button" title="Clear" @click="setQuestionColor(null)">&times;</button>
            </div>
            <!-- Answer color -->
            <div class="ctrl color-link-control">
              <span class="ctrl-label">Answer</span>
              <VueColorPicker
                :model-value="hexOrDefault(answerColor, '#64748b')"
                fallback-color="#64748b"
                :preview-style="swatchStyle(resolveTextColor(answerColor, answerColorVariation), { rawColor: answerColor, linkKey: answerColorLink, treatEmptyAsHighContrast: true, baseRefColor: state.design.sectionBackgroundColor || '#ffffff', baseRefKey: 'sectionBackgroundColor', adminConfig: state.adminDesignConfig })"
                :size="28"
                @update:model-value="setAnswerColor($event)"
              />
              <ColorLinkPicker :model-value="answerColorLink" :options="textColorOptions" :button-size="24" @link="applyColorLink('answer', $event)" />
              <select
                class="variation-select"
                :value="answerColorVariation"
                @change="setColorVariation('answer', $event.target.value)"
              >
                <option v-for="variation in colorVariationOptions" :key="`answer-${variation}`" :value="variation">
                  {{ variation }}%
                </option>
              </select>
              <button v-if="answerColor" class="clear-btn" type="button" title="Clear" @click="setAnswerColor(null)">&times;</button>
            </div>
            <!-- Separator/Chevron color -->
            <div class="ctrl color-link-control">
              <span class="ctrl-label">Separator</span>
              <VueColorPicker
                :model-value="hexOrDefault(separatorColor, '#4f46e5')"
                fallback-color="#4f46e5"
                :preview-style="swatchStyle(resolveTextColor(separatorColor, separatorColorVariation), { rawColor: separatorColor, linkKey: separatorColorLink, treatEmptyAsHighContrast: true, baseRefColor: state.design.sectionBackgroundColor || '#ffffff', baseRefKey: 'sectionBackgroundColor', adminConfig: state.adminDesignConfig })"
                :size="28"
                @update:model-value="setSeparatorColor($event)"
              />
              <ColorLinkPicker :model-value="separatorColorLink" :options="baseColorOptions" :button-size="24" @link="applyColorLink('separator', $event)" />
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
            <!-- Group title color -->
            <div class="ctrl color-link-control">
              <span class="ctrl-label">Groups</span>
              <VueColorPicker
                :model-value="hexOrDefault(groupTitleColor, '#4f46e5')"
                fallback-color="#4f46e5"
                :preview-style="swatchStyle(resolveGroupTitleColor(), { rawColor: groupTitleColor, linkKey: groupTitleColorLink, treatEmptyAsHighContrast: true, baseRefColor: state.design.sectionBackgroundColor || '#ffffff', baseRefKey: 'sectionBackgroundColor', adminConfig: state.adminDesignConfig })"
                :size="28"
                @update:model-value="setGroupTitleColor($event)"
              />
              <ColorLinkPicker :model-value="groupTitleColorLink" :options="textColorOptions" :button-size="24" @link="applyColorLink('groupTitle', $event)" />
              <select
                class="variation-select"
                :value="groupTitleColorVariation"
                @change="setColorVariation('groupTitle', $event.target.value)"
              >
                <option v-for="variation in colorVariationOptions" :key="`group-title-${variation}`" :value="variation">
                  {{ variation }}%
                </option>
              </select>
              <button v-if="groupTitleColor" class="clear-btn" type="button" title="Clear" @click="setGroupTitleColor(null)">&times;</button>
            </div>
      </div>
    </template>

    <template #admin-content>
      <div class="editor">
        <TopicSelector
          v-model:topics="draftTags"
          mode="catalog"
          title="FAQ Topic Filter"
          :selected-topics="selectedScopeTags"
          :selection-topics="availableScopeTags"
          :show-selection="true"
          @update:selected-topics="saveScopeSelection"
          @save-catalog="saveTopicCatalog"
        />

        <SectionListEditor
          :items="draftVisibleItems"
          :selected-index="expandedItem"
          :add-label="t.add"
          :save-label="t.save"
          :remove-label="t.remove"
          clear-label="Clear All"
          :save-disabled="saving"
          :remove-disabled="saving"
          :clear-disabled="saving"
          :show-clear="showFaqClearButton"
          :show-reorder-toggle="false"
          @select="expandedItem = $event"
          @add="add"
          @save="save"
          @remove="remove"
          @clear="clearAllFaqItems"
        >
          <template #item="{ item, index }">
            <div class="item-thumb item-thumb--text">
              <span class="thumb-num">{{ index + 1 }}</span>
              <span class="thumb-label">{{ item.q.de || item.q.en || `#${index + 1}` }}</span>
            </div>
          </template>

          <template #editor="{ item, index }">
              <TopicSelector
                mode="field"
                :topics="draftTags"
                :model-value="item.tag"
                :label="t.tag"
                :disabled="isFaqItemFieldLocked(index, 'tag', { includeDescendants: true })"
                :disabled-title="isFaqItemFieldLocked(index, 'tag', { includeDescendants: true }) ? integrationLockedHint : ''"
                @update:model-value="(tag) => setItemTag(index, tag)"
              />
              
              <div class="lang-section">
                <div class="lang-header">
                  {{ t.german }} (DE)
                </div>
                <div class="field-group">
                  <input
                    v-model="item.q.de"
                    class="field"
                    :placeholder="t.question + '...'"
                    :disabled="isFaqItemFieldLocked(index, 'q.de')"
                    :title="isFaqItemFieldLocked(index, 'q.de') ? integrationLockedHint : undefined"
                  />
                  <div class="field-rich">
                    <QuillEditor
                      v-model:content="item.a.de"
                      content-type="html"
                      theme="snow"
                      :toolbar="faqAnswerToolbar"
                      :placeholder="t.answer + '...'"
                      :read-only="isFaqItemFieldLocked(index, 'a.de')"
                    />
                  </div>
                </div>
              </div>
              <div class="lang-section">
                <div class="lang-header">
                  {{ t.english }} (EN)
                </div>
                <div class="field-group">
                  <input
                    v-model="item.q.en"
                    class="field"
                    :placeholder="t.question + '...'"
                    :disabled="isFaqItemFieldLocked(index, 'q.en')"
                    :title="isFaqItemFieldLocked(index, 'q.en') ? integrationLockedHint : undefined"
                  />
                  <div class="field-rich">
                    <QuillEditor
                      v-model:content="item.a.en"
                      content-type="html"
                      theme="snow"
                      :toolbar="faqAnswerToolbar"
                      :placeholder="t.answer + '...'"
                      :read-only="isFaqItemFieldLocked(index, 'a.en')"
                    />
                  </div>
                </div>
              </div>
              <div class="field-row faq-schedule-row">
                <div class="faq-schedule-col">
                  <label class="field-label">
                    Release Date
                  </label>
                  <VueDatePicker
                    :model-value="serverDateOnlyToLocalDate(item.startDate)"
                    class="section-date-picker"
                    :enable-time-picker="false"
                    :clearable="true"
                    :text-input="DATE_PICKER_DATE_ONLY_TEXT_INPUT_OPTIONS"
                    :formats="DATE_PICKER_DATE_ONLY_DISPLAY_FORMATS"
                    :teleport="true"
                    auto-apply
                    placeholder="Select start date"
                    :disabled="isFaqItemFieldLocked(index, 'startDate')"
                    :title="isFaqItemFieldLocked(index, 'startDate') ? integrationLockedHint : undefined"
                    @update:model-value="item.startDate = localDateToServerDateOnly($event)"
                  />
                </div>
                <div class="faq-schedule-col">
                  <label class="field-label">
                    Expiry Date
                  </label>
                  <VueDatePicker
                    :model-value="serverDateOnlyToLocalDate(item.endDate)"
                    class="section-date-picker"
                    :enable-time-picker="false"
                    :clearable="true"
                    :text-input="DATE_PICKER_DATE_ONLY_TEXT_INPUT_OPTIONS"
                    :formats="DATE_PICKER_DATE_ONLY_DISPLAY_FORMATS"
                    :teleport="true"
                    auto-apply
                    placeholder="Select end date"
                    :disabled="isFaqItemFieldLocked(index, 'endDate')"
                    :title="isFaqItemFieldLocked(index, 'endDate') ? integrationLockedHint : undefined"
                    @update:model-value="item.endDate = localDateToServerDateOnly($event)"
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
import { ref, computed, watch } from "vue";
import DOMPurify from "dompurify";
import { QuillEditor } from "@vueup/vue-quill";
import "@vueup/vue-quill/dist/vue-quill.snow.css";
import { VueDatePicker } from "@vuepic/vue-datepicker";
import "@vuepic/vue-datepicker/dist/main.css";
import { useStore } from "../../store/store.js";
import {
  buildColorLinkOptions,
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
import { convertKeysToCamel } from "../../utils/caseConversion.js";
import {
  DATE_PICKER_DATE_ONLY_DISPLAY_FORMATS,
  DATE_PICKER_DATE_ONLY_TEXT_INPUT_OPTIONS,
  getCurrentServerDateISO,
  localDateToServerDateOnly,
  serverDateOnlyToLocalDate,
} from "../../utils/revisionTime.js";
import { isSectionIntegrationFieldLocked } from "../../utils/sectionIntegrationFieldState.js";
import {
  getTagKey,
  hasTagValue,
  normalizeScopes,
  normalizeTag,
  tagMatches,
  uniqueTags,
} from "../../utils/topics.js";
import { listIntegrationsForSection } from "../../services/api.js";

import SectionBase from "./_BaseSection.vue";
import { getBaseSectionSwatchStyle } from "./_baseSectionSwatchStyle.js";
import SectionListEditor from "../admin/section-editor/SectionListEditor.vue";
import TopicSelector from "../admin/section-editor/TopicSelector.vue";
import ColorLinkPicker from "../ui/color/ColorLinkPicker.vue";
import VueColorPicker from "../ui/color/VueColorPicker.vue";

const props = defineProps({
  sectionKey: { type: String, default: "faq" },
  sectionData: { type: Object, default: null },
});

const { state, t, localizedText, updateSection, fetchFaqSharedData, saveFaqSharedData } = useStore();
const integrationLockedHint = "Managed by integration import.";

const effectiveKey = computed(() => props.sectionKey);
const currentAdminTab = computed(() => state.sectionAdminActiveTabs?.[effectiveKey.value] || "");

const section = computed(() => {
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});

function normalizeFaqDate(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : "";
}

function getBerlinTodayISO() {
  return getCurrentServerDateISO();
}

function faqMatchesScopes(item, scopes) {
  const normalizedScopes = normalizeScopes(scopes);
  if (normalizedScopes.length === 0) return true;
  return normalizedScopes.some((scope) => tagMatches(item?.tag, scope));
}

function faqMatchesSchedule(item, todayIso) {
  const start = normalizeFaqDate(item?.startDate);
  const end = normalizeFaqDate(item?.endDate);
  if (start && start > todayIso) return false;
  if (end && end < todayIso) return false;
  return true;
}

function normalizeFaqItem(sourceItem, index = 0) {
  const source = sourceItem && typeof sourceItem === "object" ? sourceItem : {};
  const normalizedSource = convertKeysToCamel(source);
  const question = normalizedSource.question ?? normalizedSource.q ?? source.q ?? {};
  const answer = normalizedSource.answer ?? normalizedSource.a ?? source.a ?? {};
  return {
    id: String(normalizedSource.id || source.id || "").trim() || `faq-${index + 1}`,
    q: {
      de: String(question?.de || ""),
      en: String(question?.en || ""),
    },
    a: {
      de: String(answer?.de || ""),
      en: String(answer?.en || ""),
    },
    tag: normalizeTag(normalizedSource.tag),
    startDate: normalizeFaqDate(normalizedSource.startDate),
    endDate: normalizeFaqDate(normalizedSource.endDate),
  };
}

function normalizeFaqItemsForPersistence(items) {
  return (Array.isArray(items) ? items : [])
    .map((item, index) => normalizeFaqItem(item, index))
    .map((item) => ({
      id: item.id,
      q: {
        de: String(item.q?.de || ""),
        en: String(item.q?.en || ""),
      },
      a: {
        de: normalizeEditorContent(item.a?.de),
        en: normalizeEditorContent(item.a?.en),
      },
      tag: normalizeTag(item.tag),
      startDate: normalizeFaqDate(item.startDate),
      endDate: normalizeFaqDate(item.endDate),
    }));
}

function isFaqDraftInSyncWithStore() {
  return JSON.stringify(allFaqItems.value || [])
    === JSON.stringify(normalizeFaqItemsForPersistence(draft.value));
}

const faqItems = computed(() => {
  if (Array.isArray(state.faqItems) && (state.faqItems.length > 0 || state.faqSharedLoaded)) {
    return state.faqItems;
  }
  if (Array.isArray(section.value?.faqItems)) {
    return section.value.faqItems;
  }
  return [];
});

const allFaqItems = computed(() =>
  (Array.isArray(faqItems.value) ? faqItems.value : []).map((item, index) => normalizeFaqItem(item, index))
);

const selectedScopeTags = computed(() => {
  const source = section.value && typeof section.value === "object" ? section.value : {};
  if (Object.prototype.hasOwnProperty.call(source, "scopes")) {
    return normalizeScopes(source.scopes);
  }
  return normalizeScopes(source.scope);
});
const publicView = computed(() => !state.isAdmin || state.previewMode);

function stripHtmlToText(value) {
  return String(value ?? "")
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/\u00a0/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function hasFaqItemContent(item) {
  return Boolean(
    stripHtmlToText(item?.q?.de)
    || stripHtmlToText(item?.q?.en)
    || stripHtmlToText(item?.a?.de)
    || stripHtmlToText(item?.a?.en)
  );
}

const faqViewItems = computed(() => {
  let items = allFaqItems.value.filter((item) => faqMatchesScopes(item, selectedScopeTags.value));
  if (publicView.value) {
    const todayIso = getBerlinTodayISO();
    items = items
      .filter((item) => faqMatchesSchedule(item, todayIso))
      .filter((item) => hasFaqItemContent(item));
  }
  return items;
});

function faqItemStableId(item, index) {
  const numericIndex = Number(index);
  const resolvedIndex = Number.isInteger(numericIndex) && numericIndex >= 0 ? numericIndex : 0;
  const uniqueSuffix = `${resolvedIndex + 1}`;

  const rawId = String(item?.id || "").trim();
  if (rawId) return `${rawId}-${uniqueSuffix}`;

  const de = String(item?.q?.de || "").trim();
  const en = String(item?.q?.en || "").trim();
  const seed = de || en;
  const slug = seed
    ? seed.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")
    : "";

  return `faq-${slug || uniqueSuffix}-${uniqueSuffix}`;
}

function faqGroupKey(item) {
  const tag = normalizeTag(item?.tag);
  return hasTagValue(tag) ? getTagKey(tag) : "__untagged";
}

function faqGroupLabel(item) {
  const tag = normalizeTag(item?.tag);
  if (hasTagValue(tag)) return localizedText(tag) || tag.de || tag.en;
  return t.value?.otherTopic || "Other";
}

const groupedFaqOutput = computed(() => {
  const topicKeys = new Set();
  for (const item of faqViewItems.value) {
    const tag = normalizeTag(item?.tag);
    if (hasTagValue(tag)) topicKeys.add(getTagKey(tag));
  }
  return topicKeys.size > 1;
});

const faqRenderGroups = computed(() => {
  const items = faqViewItems.value;
  if (!groupedFaqOutput.value) {
    return [{
      key: "all",
      label: "",
      items: items.map((item, index) => ({
        ...item,
        __renderId: faqItemStableId(item, index),
      })),
    }];
  }

  const groups = [];
  const groupByKey = new Map();
  items.forEach((item, index) => {
    const key = faqGroupKey(item);
    let group = groupByKey.get(key);
    if (!group) {
      group = {
        key,
        label: faqGroupLabel(item),
        items: [],
      };
      groupByKey.set(key, group);
      groups.push(group);
    }
    group.items.push({
      ...item,
      __renderId: faqItemStableId(item, index),
    });
  });
  return groups;
});

const faqRenderItems = computed(() =>
  faqRenderGroups.value.flatMap((group) => group.items)
);

// Track which FAQ items are open
const openItems = ref(new Set());

function toggleFaqItem(id) {
  if (openItems.value.has(id)) {
    openItems.value.delete(id);
  } else {
    openItems.value.add(id);
  }
  openItems.value = new Set(openItems.value);
}

watch(
  () => faqRenderItems.value.map((item) => item.__renderId).join("|"),
  (nextKeys) => {
    const validIds = new Set(String(nextKeys || "").split("|").filter(Boolean));
    if (validIds.size === 0) {
      openItems.value = new Set();
      return;
    }
    const filtered = new Set();
    openItems.value.forEach((id) => {
      if (validIds.has(id)) filtered.add(id);
    });
    openItems.value = filtered;
  },
  { immediate: true }
);

const hover = ref(false);
const expandedItem = ref(-1);
const draft = ref([]);
const draftTags = ref([]);
const saving = ref(false);
const faqIntegrationVisibility = ref("template_only");
let faqIntegrationVisibilityRequestId = 0;

const faqAnswerToolbar = [
  ["bold", "italic", "underline"],
  [{ list: "ordered" }, { list: "bullet" }],
  ["link"],
  ["clean"],
];

const sectionForIntegration = computed(() => {
  const base = section.value && typeof section.value === "object"
    ? { ...section.value }
    : {};
  base.faqItems = Array.isArray(state.faqItems)
    ? state.faqItems.map((item, index) => normalizeFaqItem(item, index))
    : [];
  return base;
});

function normalizeIntegrationVisibility(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return ["disabled", "template_only", "enabled"].includes(normalized) ? normalized : "template_only";
}

function hasMappingRows(rows) {
  return Array.isArray(rows) && rows.some((row) => {
    if (!row || typeof row !== "object") return false;
    return Boolean(
      String(row.sourcePath || "").trim()
      || String(row.targetPath || "").trim()
    );
  });
}

function hasListMappingRows(listMappingsByCollectionPath) {
  if (!listMappingsByCollectionPath || typeof listMappingsByCollectionPath !== "object") return false;
  return Object.values(listMappingsByCollectionPath).some((rows) => hasMappingRows(rows));
}

function hasHiddenListTargetPaths(hiddenTargetsByCollectionPath) {
  if (!hiddenTargetsByCollectionPath || typeof hiddenTargetsByCollectionPath !== "object") return false;
  return Object.values(hiddenTargetsByCollectionPath).some((paths) =>
    Array.isArray(paths) && paths.some((path) => String(path || "").trim())
  );
}

const isTemplateBuilderPage = computed(() =>
  String(state.pageSlug || "").startsWith("__template_")
);

const faqIntegrationMapping = computed(() => {
  const source = sectionForIntegration.value?.sectionIntegrationMapping
    || section.value?.sectionIntegrationMapping
    || {};
  return source && typeof source === "object" && !Array.isArray(source)
    ? convertKeysToCamel(source)
    : {};
});

const hasActiveFaqIntegrationImport = computed(() => {
  const mapping = faqIntegrationMapping.value;
  return Boolean(
    String(mapping.selectedIntegrationId || "").trim()
    || hasMappingRows(mapping.scalarMappings)
    || hasListMappingRows(mapping.listMappingsByCollectionPath)
    || hasMappingRows(mapping.listFilters)
    || hasHiddenListTargetPaths(mapping.hiddenListTargetPathsByCollectionPath)
  );
});

const normalizedFaqIntegrationVisibility = computed(() =>
  normalizeIntegrationVisibility(faqIntegrationVisibility.value)
);

const showFaqClearButton = computed(() => {
  if (!hasActiveFaqIntegrationImport.value) return true;
  return normalizedFaqIntegrationVisibility.value !== "template_only" || isTemplateBuilderPage.value;
});

const draftRows = computed(() =>
  draft.value.map((item, index) => ({
    index,
    item,
    key: String(item?.id || `faq-row-${index + 1}`),
  }))
);

const draftVisibleRows = computed(() =>
  draftRows.value.filter((row) => faqMatchesScopes(row.item, selectedScopeTags.value))
);

const draftVisibleItems = computed(() => draftVisibleRows.value.map((row) => row.item));

const availableScopeTags = computed(() => {
  const sourceTags = [];
  sourceTags.push(...draftTags.value);
  sourceTags.push(...selectedScopeTags.value);
  if (hasTagValue(section.value?.scope)) sourceTags.push(section.value.scope);
  return uniqueTags(sourceTags);
});

function saveScopeSelection(scopes) {
  updateSection(effectiveKey.value, {
    scopes: normalizeScopes(scopes),
    scope: null,
  }, { revisionKind: "content" });
  expandedItem.value = -1;
}

function resolveDraftIndex(visibleIndex) {
  const numericIndex = Number(visibleIndex);
  if (!Number.isInteger(numericIndex) || numericIndex < 0) return -1;
  const row = draftVisibleRows.value[numericIndex];
  if (row && Number.isInteger(row.index) && row.index >= 0) return row.index;
  return -1;
}

function faqFieldPath(index, fieldPath) {
  const normalizedFieldPath = String(fieldPath || "").trim();
  const resolvedIndex = resolveDraftIndex(index);
  const safeIndex = resolvedIndex >= 0 ? resolvedIndex : 0;
  return normalizedFieldPath
    ? `faqItems[${safeIndex}].${normalizedFieldPath}`
    : `faqItems[${safeIndex}]`;
}

function isFaqItemFieldLocked(index, fieldPath, options = {}) {
  if (!state.isAdmin) return false;
  const normalizedFieldPath = String(fieldPath || "").trim();
  const rawIndex = resolveDraftIndex(index);
  const resolvedIndex = rawIndex >= 0 ? rawIndex : 0;
  const fallbackPath = normalizedFieldPath
    ? `faqs[${resolvedIndex}].${normalizedFieldPath}`
    : `faqs[${resolvedIndex}]`;
  return (
    isSectionIntegrationFieldLocked(sectionForIntegration.value, faqFieldPath(index, fieldPath), options)
    || isSectionIntegrationFieldLocked(sectionForIntegration.value, fallbackPath, options)
  );
}

watch(
  () => [
    state.isAdmin ? "1" : "0",
    state.canAdminGeneral ? "1" : "0",
    String(state.pageSlug || ""),
    String(state.sectionIds?.[effectiveKey.value] || ""),
    String(section.value?.sectionType || "faq"),
    hasActiveFaqIntegrationImport.value ? "1" : "0",
  ],
  () => {
    void loadFaqIntegrationVisibility();
  },
  { immediate: true }
);

watch(
  () => draftVisibleRows.value.length,
  (length) => {
    if (expandedItem.value >= length) {
      expandedItem.value = length > 0 ? length - 1 : -1;
    }
  }
);

watch(currentAdminTab, async (tab) => {
  if (!state.isAdmin) return;
  if (tab !== "content") return;
  if (!state.faqSharedLoaded || state.faqSharedSource === "public") {
    await fetchFaqSharedData();
  }
  startEdit();
}, { immediate: true });

watch(
  () => JSON.stringify(allFaqItems.value || []),
  () => {
    if (!state.isAdmin) return;
    if (currentAdminTab.value !== "content") return;
    if (saving.value) return;
    if (isFaqDraftInSyncWithStore()) return;
    const prevExpanded = expandedItem.value;
    startEdit();
    if (prevExpanded >= 0 && prevExpanded < draftVisibleItems.value.length) {
      expandedItem.value = prevExpanded;
    }
  }
);

// --- Color / border controls ---
const baseColorOptions = computed(() => {
  return buildColorLinkOptions(state.design, {
    parameterConfigs: state.adminDesignConfig?.parameters,
  });
});

const textColorOptions = computed(() => {
  return buildColorLinkOptions(state.design, {
    includeHighContrast: true,
    parameterConfigs: state.adminDesignConfig?.parameters,
  });
});

function sectionVal(prop) {
  const key = effectiveKey.value;
  const fromState = state.sectionsData?.[key]?.[prop];
  if (fromState !== undefined) return fromState ?? null;
  return section.value?.[prop] ?? null;
}

const questionColor = computed(() => sectionVal("questionColor"));
const questionColorLink = computed(() => sectionVal("questionColorLink"));
const answerColor = computed(() => sectionVal("answerColor"));
const answerColorLink = computed(() => sectionVal("answerColorLink"));
const separatorColor = computed(() => sectionVal("separatorColor"));
const separatorColorLink = computed(() => sectionVal("separatorColorLink"));
const groupTitleColor = computed(() => sectionVal("groupTitleColor"));
const groupTitleColorLink = computed(() => sectionVal("groupTitleColorLink"));
const questionColorVariation = computed(() => normalizeColorVariation(sectionVal("questionColorVariation")));
const answerColorVariation = computed(() => normalizeColorVariation(sectionVal("answerColorVariation")));
const separatorColorVariation = computed(() => normalizeColorVariation(sectionVal("separatorColorVariation")));
const groupTitleColorVariation = computed(() => normalizeColorVariation(sectionVal("groupTitleColorVariation")));
const colorVariationOptions = COLOR_VARIATION_OPTIONS;

function resolveBaseColor(linkKey) {
  return resolveLinkedColor(state.design, linkKey, state.adminDesignConfig?.parameters);
}

watch(
  () => [
    state.design.primaryColor,
    state.design.secondaryColor,
    state.design.backgroundColor,
    state.design.accentColor,
    state.design.sectionBackgroundColor,
    state.design.highContrastDark,
    state.design.highContrastLight,
  ],
  () => {
    if (questionColorLink.value) {
      const resolved = resolveBaseColor(questionColorLink.value);
      if (resolved !== null) updateSection(effectiveKey.value, { questionColor: resolved });
    }
    if (answerColorLink.value) {
      const resolved = resolveBaseColor(answerColorLink.value);
      if (resolved !== null) updateSection(effectiveKey.value, { answerColor: resolved });
    }
    if (separatorColorLink.value) {
      const resolved = resolveBaseColor(separatorColorLink.value);
      if (resolved !== null) updateSection(effectiveKey.value, { separatorColor: resolved });
    }
    if (groupTitleColorLink.value) {
      const resolved = resolveBaseColor(groupTitleColorLink.value);
      if (resolved !== null) updateSection(effectiveKey.value, { groupTitleColor: resolved });
    }
  }
);

function setQuestionColor(val) {
  updateSection(effectiveKey.value, { questionColor: val, questionColorLink: null });
}
function setAnswerColor(val) {
  updateSection(effectiveKey.value, { answerColor: val, answerColorLink: null });
}
function setSeparatorColor(val) {
  updateSection(effectiveKey.value, { separatorColor: val, separatorColorLink: null });
}
function setGroupTitleColor(val) {
  updateSection(effectiveKey.value, { groupTitleColor: val, groupTitleColorLink: null });
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

function resolveTextColor(colorVal, variation = DEFAULT_COLOR_VARIATION) {
  let resolved;
  if (!colorVal || colorVal === HIGH_CONTRAST_TOKEN) {
    const sectionBg = state.design.sectionBackgroundColor || "#ffffff";
    resolved = contrastColor(sectionBg, "sectionBackgroundColor");
  } else {
    resolved = colorVal;
  }
  return applyColorVariation(resolved, variation);
}

function resolveGroupTitleColor() {
  if (groupTitleColor.value) {
    return resolveTextColor(groupTitleColor.value, groupTitleColorVariation.value);
  }
  return resolveTextColor(separatorColor.value, separatorColorVariation.value);
}

const itemStyle = computed(() => {
  const s = {};
  s["--faq-separator-color"] = resolveTextColor(separatorColor.value, separatorColorVariation.value);
  return s;
});

const groupStyle = computed(() => ({
  "--faq-group-title-color": resolveGroupTitleColor(),
}));

const questionStyle = computed(() => {
  const s = {};
  s.color = resolveTextColor(questionColor.value, questionColorVariation.value);
  s["--chevron-color"] = resolveTextColor(separatorColor.value, separatorColorVariation.value);
  return s;
});

const answerStyle = computed(() => {
  const s = {};
  s.color = resolveTextColor(answerColor.value, answerColorVariation.value);
  return s;
});

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

function answerHtml(value) {
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

function hexOrDefault(val, fallback) {
  if (val && /^#[0-9a-fA-F]{6}$/.test(val)) return val;
  return fallback;
}

function swatchStyle(previewColor, options = {}) {
  return getBaseSectionSwatchStyle(state.design, previewColor, options);
}

function applyColorLink(which, baseKey) {
  const resolved = resolveBaseColor(baseKey);
  if (which === "question") {
    updateSection(effectiveKey.value, { questionColor: resolved, questionColorLink: baseKey });
  } else if (which === "answer") {
    updateSection(effectiveKey.value, { answerColor: resolved, answerColorLink: baseKey });
  } else if (which === "separator") {
    updateSection(effectiveKey.value, { separatorColor: resolved, separatorColorLink: baseKey });
  } else if (which === "groupTitle") {
    updateSection(effectiveKey.value, { groupTitleColor: resolved, groupTitleColorLink: baseKey });
  }
}

function setColorVariation(which, variation) {
  const normalized = normalizeColorVariation(variation);
  const value = normalized === DEFAULT_COLOR_VARIATION ? null : normalized;
  if (which === "question") {
    updateSection(effectiveKey.value, { questionColorVariation: value });
  } else if (which === "answer") {
    updateSection(effectiveKey.value, { answerColorVariation: value });
  } else if (which === "separator") {
    updateSection(effectiveKey.value, { separatorColorVariation: value });
  } else if (which === "groupTitle") {
    updateSection(effectiveKey.value, { groupTitleColorVariation: value });
  }
}

function startEdit() {
  expandedItem.value = -1;
  draft.value = allFaqItems.value.map((item, index) => normalizeFaqItem(item, index));
  draftTags.value = uniqueTags([
    ...(Array.isArray(state.faqTags) ? state.faqTags : []),
    ...draft.value.map((item) => item.tag),
  ]);
}

function setItemTag(visibleIndex, tag) {
  if (isFaqItemFieldLocked(visibleIndex, "tag", { includeDescendants: true })) return;
  const rawIndex = resolveDraftIndex(visibleIndex);
  if (rawIndex < 0 || rawIndex >= draft.value.length) return;
  draft.value[rawIndex].tag = normalizeTag(tag);
}

function selectedScopesEqual(a, b) {
  return JSON.stringify(normalizeScopes(a)) === JSON.stringify(normalizeScopes(b));
}

function updateSelectedScopesIfChanged(scopes) {
  const normalizedScopes = normalizeScopes(scopes);
  if (selectedScopesEqual(selectedScopeTags.value, normalizedScopes)) return;
  saveScopeSelection(normalizedScopes);
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

function replaceSelectedScopeTopic(previousTag, nextTag = null, scopes = selectedScopeTags.value) {
  const previous = normalizeTag(previousTag);
  if (!hasTagValue(previous)) return normalizeScopes(scopes);
  const replacement = nextTag && hasTagValue(nextTag) ? normalizeTag(nextTag) : null;
  return normalizeScopes(scopes)
    .map((scope) => {
      if (!tagMatches(scope, previous)) return scope;
      return replacement ? { ...replacement } : null;
    })
    .filter(Boolean);
}

async function saveTopicCatalog(payload = {}) {
  const nextTopics = uniqueTags(payload.topics || draftTags.value);
  const originalTopics = Array.isArray(payload.originalTopics) ? payload.originalTopics : [];
  let nextSelectedScopes = normalizeScopes(selectedScopeTags.value);
  const maxLength = Math.max(originalTopics.length, nextTopics.length);
  for (let index = 0; index < maxLength; index += 1) {
    const previousTag = normalizeTag(originalTopics[index]);
    const nextTag = normalizeTag(nextTopics[index]);
    if (!hasTagValue(previousTag)) continue;
    if (hasTagValue(nextTag) && !tagMatches(previousTag, nextTag)) {
      replaceDraftItemTopic(previousTag, nextTag);
      nextSelectedScopes = replaceSelectedScopeTopic(previousTag, nextTag, nextSelectedScopes);
    } else if (!hasTagValue(nextTag)) {
      replaceDraftItemTopic(previousTag, null);
      nextSelectedScopes = replaceSelectedScopeTopic(previousTag, null, nextSelectedScopes);
    }
  }
  draftTags.value = nextTopics;
  updateSelectedScopesIfChanged(nextSelectedScopes);
  await save();
}

function resolveDefaultNewItemTag() {
  if (selectedScopeTags.value.length > 0) return { ...selectedScopeTags.value[0] };
  if (draftTags.value.length > 0 && hasTagValue(draftTags.value[0])) {
    return normalizeTag(draftTags.value[0]);
  }
  return { de: "", en: "" };
}

function add() {
  const nextItem = {
    id: `faq-${Date.now()}-${Math.floor(Math.random() * 100000)}`,
    q: { de: "", en: "" },
    a: { de: "", en: "" },
    tag: resolveDefaultNewItemTag(),
    startDate: "",
    endDate: "",
  };
  draft.value.push(nextItem);
  const rawIndex = draft.value.length - 1;
  const visibleIndex = draftVisibleRows.value.findIndex((row) => row.index === rawIndex);
  expandedItem.value = visibleIndex >= 0 ? visibleIndex : -1;
  void save();
}

function remove(visibleIndex) {
  const rawIndex = resolveDraftIndex(visibleIndex);
  if (rawIndex < 0 || rawIndex >= draft.value.length) return;
  draft.value.splice(rawIndex, 1);
  const nextVisibleCount = draftVisibleRows.value.length;
  expandedItem.value = nextVisibleCount > 0 ? Math.min(visibleIndex, nextVisibleCount - 1) : -1;
}

async function loadFaqIntegrationVisibility() {
  const requestId = ++faqIntegrationVisibilityRequestId;
  if (!state.isAdmin || !hasActiveFaqIntegrationImport.value) {
    faqIntegrationVisibility.value = "enabled";
    return;
  }
  if (!state.canAdminGeneral) {
    faqIntegrationVisibility.value = "template_only";
    return;
  }

  const sectionType = String(section.value?.sectionType || "faq").trim() || "faq";
  const sectionId = String(state.sectionIds?.[effectiveKey.value] || "").trim() || null;

  try {
    const response = await listIntegrationsForSection(sectionType, { sectionId });
    if (requestId !== faqIntegrationVisibilityRequestId) return;
    faqIntegrationVisibility.value = normalizeIntegrationVisibility(response?.context?.integration_visibility);
  } catch (err) {
    if (requestId !== faqIntegrationVisibilityRequestId) return;
    console.error("Failed to load FAQ integration visibility:", err);
    faqIntegrationVisibility.value = "template_only";
  }
}

async function clearAllFaqItems() {
  if (saving.value) return;
  draft.value = [];
  expandedItem.value = -1;
  await save();
}

async function save() {
  saving.value = true;
  const sectionSnapshot = section.value && typeof section.value === "object"
    ? JSON.parse(JSON.stringify(section.value))
    : {};
  sectionSnapshot.faqItems = JSON.parse(JSON.stringify(draft.value || []));
  const preparedItems = Array.isArray(sectionSnapshot.faqItems)
    ? sectionSnapshot.faqItems
    : draft.value;

  const normalizedItems = normalizeFaqItemsForPersistence(preparedItems);

  const normalizedTags = uniqueTags([
    ...draftTags.value,
    ...normalizedItems.map((item) => item.tag),
  ]);

  try {
    await saveFaqSharedData({
      items: normalizedItems,
      tags: normalizedTags,
    });
  } catch (err) {
    console.error("Failed to save shared FAQ items:", err);
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
/* Admin controls */
.admin-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.ctrl {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
}

.ctrl-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
}

.ctrl-unit {
  font-size: 11px;
  color: var(--muted);
}

.num-input {
  width: 48px;
  padding: 4px 8px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  text-align: center;
}

.color-link-control {
  display: flex;
  align-items: center;
  gap: 6px;
  position: relative;
}

.variation-select {
  min-width: 68px;
  padding: 4px 6px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 12px;
}

.color-swatch {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 2px solid var(--border, rgba(15,23,42,0.14));
  cursor: pointer;
  flex-shrink: 0;
}

.color-input-hidden {
  position: absolute;
  width: 0;
  height: 0;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
}

.qa {
  position: relative;
  margin-top: 12px;
  display: grid;
  gap: 0;
  border-radius: 12px;
  padding: 4px;
}

.faq-group {
  display: grid;
  gap: 0;
}

.faq-group + .faq-group {
  margin-top: 18px;
}

.faq-group-heading {
  margin: 0 0 4px;
  font-family: var(--header-font-family);
  font-weight: var(--header-font-weight);
  color: var(--faq-group-title-color, var(--faq-separator-color, var(--accent)));
}

.faq-item {
  padding: 16px 0;
  position: relative;
}

.faq-item::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: color-mix(in srgb, var(--faq-separator-color, var(--accent)) 25%, transparent);
}

.faq-item.last-item::after {
  display: none;
}

.faq-question { 
  cursor: pointer; 
  font-family: var(--header-font-family);
  font-weight: var(--header-font-weight); 
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  background: none;
  border: none;
  padding: 0;
  text-align: left;
  font-size: inherit;
}

.faq-question:focus {
  outline: none;
}

.faq-question:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 4px;
  border-radius: 4px;
}

.summary-text {
  flex: 1;
  margin: 0;
  font-size: inherit;
  color: inherit;
}

.chevron {
  flex-shrink: 0;
  transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  color: var(--chevron-color, var(--accent));
}

.faq-item.is-open .chevron {
  transform: rotate(180deg);
}

.answer-wrapper {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.faq-item.is-open .answer-wrapper {
  grid-template-rows: 1fr;
}

.answer-wrapper > .answer-content {
  overflow: hidden;
}

.answer-content {
  margin-top: 12px;
  padding-top: 4px;
  font-family: var(--body-font-family);
  line-height: var(--body-line-height);
  color: var(--secondary-color);
}

.answer-content :deep(p) {
  color: inherit;
}

.faq-item p {
  margin-top: 12px;
  padding-top: 4px;
  font-family: var(--body-font-family);
  line-height: var(--body-line-height);
  color: var(--secondary-color);
}

.editor {
  display: grid;
  gap: 12px;
}

.field-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field.small {
  padding: 8px 10px;
  font-size: 12px;
}

.faq-schedule-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.faq-schedule-col {
  display: grid;
  gap: 6px;
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

.thumb-num {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--surface-2, #eef2f7);
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 800;
  color: var(--muted, #64748b);
  flex-shrink: 0;
}

.item-field-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.lang-section {
  display: grid;
  gap: 6px;
}

.lang-header {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field-group {
  display: grid;
  gap: 10px;
}

.field {
  width: 100%;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.92);
  padding: 10px 12px;
  outline: none;
  color: var(--primary-color);
}

.field-rich :deep(.ql-toolbar) {
  border-radius: 8px 8px 0 0;
  border-color: var(--border, #d6dce6);
  background: rgba(255,255,255,0.96);
}

.field-rich {
  display: grid;
  min-width: 0;
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

.rich-render :deep(p) {
  margin: 0 0 0.75em;
}

.rich-render :deep(p:last-child) {
  margin-bottom: 0;
}

.rich-render :deep(ul),
.rich-render :deep(ol) {
  margin: 0.4em 0;
  padding-left: 1.4em;
}

.rich-render :deep(a) {
  text-decoration: underline;
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}
.spacer { flex: 1; }

@media (max-width: 900px) {
  .field-rich :deep(.ql-container) { min-height: 90px; }
  .field-rich :deep(.ql-editor) { min-height: 90px; }
  .faq-schedule-row {
    grid-template-columns: 1fr;
  }
}
</style>
