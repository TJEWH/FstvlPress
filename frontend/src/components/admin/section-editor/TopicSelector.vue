<template>
  <div v-if="mode === 'catalog'" class="topic-panel">
    <div class="topic-panel__header">
      <div class="topic-panel__title">{{ title || t.topicFilter || t.scope || t.tag }}</div>
      <button class="btn-secondary small" type="button" @click="toggleCatalogEditor">
        {{ catalogOpen ? t.close : t.edit }}
      </button>
    </div>

    <div v-if="showSelection" class="topic-filter-list">
      <label class="topic-filter-option topic-filter-option--all">
        <input
          type="checkbox"
          :checked="normalizedSelectedTopics.length === 0"
          @change="clearSelection"
        />
        <span>{{ t.allTopics }}</span>
      </label>
      <label
        v-for="(topic, idx) in normalizedSelectionTopics"
        :key="`topic-filter-${idx}-${getTagKey(topic)}`"
        class="topic-filter-option"
      >
        <input
          type="checkbox"
          :checked="isTopicSelected(topic)"
          @change="setTopicSelected(topic, $event.target.checked)"
        />
        <span>{{ localizedText(topic) || `#${idx + 1}` }}</span>
      </label>
    </div>

    <div v-if="catalogOpen" class="topic-editor-list">
      <SectionListEditor
        class="topic-list-editor"
        :items="localTopics"
        :selected-index="selectedTopicIndex"
        :remove-label="t.remove"
        :save-label="t.save"
        :show-clear="false"
        :show-reorder-toggle="false"
        :save-on-remove="false"
        @select="selectedTopicIndex = $event"
        @add="addTopic"
        @save="saveCatalog"
        @remove="removeTopic"
      >
        <template #item="{ item, index }">
          <div class="topic-row">
            <span class="topic-row-label">{{ localizedText(item) || `#${index + 1}` }}</span>
          </div>
        </template>
        <template #editor="{ item }">
          <div class="topic-fields">
            <label class="topic-field">
              <span class="field-label">Topic Title (DE)</span>
              <input v-model="item.de" class="field small" placeholder="Topic Title (DE)" />
            </label>
            <label class="topic-field">
              <span class="field-label">Topic Title (EN)</span>
              <input v-model="item.en" class="field small" placeholder="Topic Title (EN)" />
            </label>
          </div>
        </template>
        <template #add>
          <div class="topic-add-row">
            <span class="thumb-empty">+</span>
          </div>
        </template>
      </SectionListEditor>
    </div>
  </div>

  <div v-else class="topic-field-control">
    <label v-if="label" class="field-label">{{ label }}</label>
    <select
      class="field topic-select"
      :value="selectedTopicIndexForField"
      :disabled="disabled"
      :title="disabled ? disabledTitle : undefined"
      @change="setFieldTopic($event.target.value)"
    >
      <option value="-1">— {{ t.selectTag }} —</option>
      <option
        v-for="(topic, idx) in normalizedTopics"
        :key="`topic-option-${idx}-${getTagKey(topic)}`"
        :value="idx"
      >
        {{ localizedText(topic) || `#${idx + 1}` }}
      </option>
    </select>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useStore } from "../../../store/store.js";
import {
  getTagKey,
  normalizeTag,
  normalizeScopes,
  tagMatches,
  uniqueTags,
} from "../../../utils/topics.js";
import SectionListEditor from "./SectionListEditor.vue";

const props = defineProps({
  mode: { type: String, default: "field" },
  title: { type: String, default: "" },
  topics: { type: Array, default: () => [] },
  selectionTopics: { type: Array, default: null },
  selectedTopics: { type: Array, default: () => [] },
  showSelection: { type: Boolean, default: false },
  modelValue: { type: Object, default: () => ({ de: "", en: "" }) },
  label: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
  disabledTitle: { type: String, default: "" },
});

const emit = defineEmits([
  "update:topics",
  "update:selectedTopics",
  "update:modelValue",
  "save-catalog",
]);

const { t, localizedText } = useStore();

const catalogOpen = ref(false);
const selectedTopicIndex = ref(-1);
const localTopics = ref([]);
const originalTopics = ref([]);

const normalizedTopics = computed(() => uniqueTags(props.topics));
const normalizedSelectedTopics = computed(() => normalizeScopes(props.selectedTopics));
const normalizedSelectionTopics = computed(() => {
  const sourceTopics = Array.isArray(props.selectionTopics)
    ? props.selectionTopics
    : props.topics;
  return uniqueTags([
    ...sourceTopics,
    ...normalizedSelectedTopics.value,
  ]);
});
const selectedTopicKeySet = computed(() =>
  new Set(normalizedSelectedTopics.value.map((topic) => getTagKey(topic)))
);
const selectedTopicIndexForField = computed(() => {
  const current = normalizeTag(props.modelValue);
  const idx = normalizedTopics.value.findIndex((topic) => tagMatches(topic, current));
  return idx >= 0 ? idx : -1;
});

watch(
  () => props.topics,
  (topics) => {
    if (catalogOpen.value) return;
    localTopics.value = cloneTopics(topics);
  },
  { immediate: true, deep: true }
);

function cloneTopics(topics) {
  return (Array.isArray(topics) ? topics : []).map((topic) => ({ ...normalizeTag(topic) }));
}

function setFieldTopic(value) {
  const topicIndex = Number.parseInt(value, 10);
  if (Number.isInteger(topicIndex) && topicIndex >= 0 && topicIndex < normalizedTopics.value.length) {
    emit("update:modelValue", { ...normalizedTopics.value[topicIndex] });
    return;
  }
  emit("update:modelValue", { de: "", en: "" });
}

function isTopicSelected(topic) {
  return selectedTopicKeySet.value.has(getTagKey(topic));
}

function setTopicSelected(topic, selected) {
  const normalized = normalizeTag(topic);
  const nextTopics = normalizedSelectedTopics.value.filter((selectedTopic) => !tagMatches(selectedTopic, normalized));
  if (selected) nextTopics.push(normalized);
  emit("update:selectedTopics", normalizeScopes(nextTopics));
}

function clearSelection() {
  emit("update:selectedTopics", []);
}

function toggleCatalogEditor() {
  if (catalogOpen.value) {
    selectedTopicIndex.value = -1;
    saveCatalog();
    catalogOpen.value = false;
    return;
  }
  localTopics.value = cloneTopics(props.topics);
  originalTopics.value = cloneTopics(props.topics);
  catalogOpen.value = true;
}

function addTopic() {
  localTopics.value.push({ de: "", en: "" });
  selectedTopicIndex.value = localTopics.value.length - 1;
}

function removeTopic(index) {
  const numericIndex = Number(index);
  if (!Number.isInteger(numericIndex) || numericIndex < 0 || numericIndex >= localTopics.value.length) return;
  localTopics.value.splice(numericIndex, 1);
  if (selectedTopicIndex.value === numericIndex) {
    selectedTopicIndex.value = -1;
  } else if (selectedTopicIndex.value > numericIndex) {
    selectedTopicIndex.value -= 1;
  }
  saveCatalog();
}

function topicsEqual(a, b) {
  const left = uniqueTags(a);
  const right = uniqueTags(b);
  if (left.length !== right.length) return false;
  return left.every((topic, index) => tagMatches(topic, right[index]));
}

function saveCatalog() {
  const nextTopics = uniqueTags(localTopics.value);
  localTopics.value = cloneTopics(nextTopics);
  const previousTopics = cloneTopics(originalTopics.value);
  originalTopics.value = cloneTopics(nextTopics);
  if (topicsEqual(nextTopics, previousTopics)) return;
  emit("update:topics", cloneTopics(nextTopics));
  emit("save-catalog", {
    topics: cloneTopics(nextTopics),
    originalTopics: previousTopics,
  });
}
</script>

<style scoped>
.topic-panel {
  display: grid;
  gap: 8px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.12));
  border-radius: 10px;
  padding: 10px;
  background: rgba(248, 250, 252, 0.9);
}

.topic-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.topic-panel__title {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted, #64748b);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.topic-filter-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.topic-filter-option {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 6px 10px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.12));
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
}

.topic-filter-option input {
  margin: 0;
}

.topic-filter-option--all {
  color: var(--muted, #64748b);
}

.topic-editor-list {
  display: grid;
  gap: 10px;
}

.topic-list-editor :deep(.item-grid) {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.topic-row,
.topic-add-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-width: 0;
  padding: 4px 12px;
}

.topic-row-label {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.topic-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.topic-field,
.topic-field-control {
  display: grid;
  gap: 6px;
}

.topic-add-row {
  justify-content: center;
  color: var(--accent, #4f46e5);
  font-weight: 800;
}

.field-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted, #64748b);
  text-transform: uppercase;
  letter-spacing: 0.05em;
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

.field.small {
  padding: 8px 10px;
  font-size: 12px;
}

.topic-select {
  min-width: 0;
}

@media (max-width: 900px) {
  .topic-list-editor :deep(.item-grid) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .topic-fields {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 520px) {
  .topic-list-editor :deep(.item-grid) {
    grid-template-columns: 1fr;
  }
}
</style>
