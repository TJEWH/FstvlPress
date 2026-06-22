<template>
  <SectionBase
    :section-key="effectiveKey"
    :section-data="section"
    class="markdown-section"
    :admin-tabs-visible="state.isAdmin && (!state.previewMode || isTemplateBuilderPage)"
    :show-description="false"
  >
    <div v-if="sanitizedHtml" class="markdown-content" v-html="sanitizedHtml"></div>
    <div v-else-if="!state.isAdmin" class="empty-content">
      <span class="empty-icon"><font-awesome-icon :icon="faFileLines" /></span>
      <span>No markdown content configured</span>
    </div>

    <template #admin-content>
      <div class="markdown-controls">
        <div
          class="drop-zone"
          :class="{ dragging: isDragging }"
          @dragover.prevent="isDragging = true"
          @dragleave="isDragging = false"
          @drop.prevent="handleFileDrop"
        >
          <span class="drop-icon"><font-awesome-icon :icon="faFile" /></span>
          <span class="drop-text">Drag and drop a .md file here</span>
          <span class="drop-hint">Imported content replaces the markdown source below.</span>
        </div>

        <textarea
          v-model="rawMarkdown"
          class="raw-textarea"
          placeholder="# Markdown content here...

Write your **markdown** content directly."
          rows="12"
          :disabled="markdownContentLocked"
          :title="markdownContentLocked ? integrationLockedHint : undefined"
        ></textarea>

        <button
          type="button"
          class="render-btn"
          :disabled="isLoading || markdownContentLocked"
          @click="renderAndSave"
        >
          {{ isLoading ? "Rendering..." : "Render & Save" }}
        </button>

        <div v-if="error" class="error-message">{{ error }}</div>
      </div>
    </template>
  </SectionBase>
</template>

<script setup>
import DOMPurify from "dompurify";
import { ref, computed, watch, onMounted } from "vue";
import { faFile, faFileLines } from "@fortawesome/free-solid-svg-icons";
import { marked } from "marked";
import { useStore } from "../../store/store.js";
import * as api from "../../services/api.js";
import { isSectionIntegrationFieldLocked } from "../../utils/sectionIntegrationFieldState.js";

import SectionBase from "./_BaseSection.vue";

const props = defineProps({
  sectionKey: { type: String, default: "markdown" },
  sectionData: { type: Object, default: null },
});

const { state } = useStore();

const rawMarkdown = ref("");
const renderedHtml = ref("");
const isLoading = ref(false);
const isDragging = ref(false);
const error = ref("");
const integrationLockedHint = "Managed by integration import.";

const effectiveKey = computed(() => props.sectionKey);
const section = computed(() => {
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});
const isTemplateBuilderPage = computed(() =>
  String(state.pageSlug || "").startsWith("__template_")
);
const markdownContentLocked = computed(() =>
  state.isAdmin
  && [
    "rawMarkdown",
    "raw_markdown",
    "type_data.rawMarkdown",
    "type_data.raw_markdown",
    "renderedHtml",
    "rendered_html",
    "type_data.renderedHtml",
    "type_data.rendered_html",
  ].some((path) => isSectionIntegrationFieldLocked(section.value, path))
);

const sanitizedHtml = computed(() => {
  if (!renderedHtml.value) return "";
  return DOMPurify.sanitize(renderedHtml.value, {
    ADD_TAGS: ["iframe"],
    ADD_ATTR: ["allowfullscreen", "frameborder", "target"],
  });
});

function initFromSectionData() {
  const typeData = section.value?.type_data || {};
  rawMarkdown.value = String(typeData.raw_markdown || typeData.raw_content || "");
  renderedHtml.value = String(typeData.rendered_html || "");

  if (!renderedHtml.value && rawMarkdown.value) {
    renderedHtml.value = marked(rawMarkdown.value);
  }
}

watch(
  () => JSON.stringify(section.value?.type_data || {}),
  () => {
    initFromSectionData();
  },
  { immediate: true }
);

onMounted(() => {
  initFromSectionData();
});

async function handleFileDrop(event) {
  isDragging.value = false;
  if (markdownContentLocked.value) return;
  const files = event.dataTransfer?.files;
  if (!files || files.length === 0) return;

  const file = files[0];
  const fileName = String(file.name || "").toLowerCase();
  if (!fileName.endsWith(".md") && !fileName.endsWith(".markdown")) {
    error.value = "Please drop a .md file";
    return;
  }

  isLoading.value = true;
  error.value = "";
  try {
    rawMarkdown.value = await file.text();
    renderedHtml.value = marked(rawMarkdown.value);
    await saveTypeData({
      raw_markdown: rawMarkdown.value,
      rendered_html: renderedHtml.value,
    });
  } catch (err) {
    error.value = err.message || "Failed to import markdown file";
    console.error("Failed to import markdown file:", err);
  } finally {
    isLoading.value = false;
  }
}

async function renderAndSave() {
  if (markdownContentLocked.value) return;
  isLoading.value = true;
  error.value = "";
  try {
    renderedHtml.value = rawMarkdown.value ? marked(rawMarkdown.value) : "";
    await saveTypeData({
      raw_markdown: rawMarkdown.value,
      rendered_html: renderedHtml.value,
    });
  } catch (err) {
    error.value = err.message || "Failed to render markdown";
    console.error("Failed to render markdown:", err);
  } finally {
    isLoading.value = false;
  }
}

async function saveTypeData(typeData) {
  const sectionId = state.sectionIds?.[effectiveKey.value];
  if (!sectionId) {
    console.warn("No section ID found for key:", effectiveKey.value);
    return;
  }

  const existingTypeData = section.value?.type_data || {};
  const nextTypeData = {
    ...existingTypeData,
    ...typeData,
  };
  delete nextTypeData.body;
  delete nextTypeData.description;
  delete nextTypeData.source_url;
  delete nextTypeData.source_type;
  delete nextTypeData.raw_content;
  delete nextTypeData.html_selector;
  delete nextTypeData.mode;
  delete nextTypeData.fetch_url;
  delete nextTypeData.fetch_selector;
  delete nextTypeData.fetched_html;
  delete nextTypeData.raw_html;
  delete nextTypeData.raw_css;
  delete nextTypeData.raw_js;
  delete nextTypeData.embed_code;
  delete nextTypeData.embed_provider;

  await api.updateSection(sectionId, {
    type_data: nextTypeData,
    revision_change_kind: "content",
  });
}
</script>

<style scoped>
.markdown-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.markdown-controls {
  background: var(--surface-2);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.drop-zone {
  border: 2px dashed var(--border);
  border-radius: 12px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  background: #fff;
  transition: all 0.2s ease;
}

.drop-zone.dragging {
  border-color: var(--accent, #5b2fe3);
  background: color-mix(in srgb, var(--accent, #5b2fe3) 8%, white);
}

.drop-icon {
  font-size: 32px;
}

.drop-text {
  font-weight: 600;
  font-size: 14px;
  color: var(--text);
}

.drop-hint {
  font-size: 12px;
  color: var(--muted);
}

.raw-textarea {
  width: 100%;
  padding: 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s ease;
}

.raw-textarea:focus {
  border-color: var(--accent, #5b2fe3);
}

.render-btn {
  padding: 12px 20px;
  border-radius: 10px;
  background: var(--accent, #5b2fe3);
  color: #fff;
  border: none;
  font-weight: 700;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.render-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--accent, #5b2fe3) 85%, black);
}

.render-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-message {
  padding: 10px 14px;
  border-radius: 8px;
  background: #fee2e2;
  color: #dc2626;
  font-size: 13px;
  font-weight: 500;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4),
.markdown-content :deep(h5),
.markdown-content :deep(h6) {
  margin-top: 1.5em;
  margin-bottom: 0.5em;
  font-family: var(--header-font-family);
  font-weight: var(--header-font-weight);
  letter-spacing: var(--header-letter-spacing);
  line-height: var(--header-line-height);
}

.markdown-content :deep(h1) {
  font-size: 1.75em;
}

.markdown-content :deep(h2) {
  font-size: 1.5em;
}

.markdown-content :deep(h3) {
  font-size: 1.25em;
}

.markdown-content :deep(p) {
  margin-bottom: 1em;
  font-family: var(--body-font-family);
  line-height: var(--body-line-height);
  letter-spacing: var(--body-letter-spacing);
  color: var(--secondary-color);
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin-bottom: 1em;
  padding-left: 1.5em;
}

.markdown-content :deep(li) {
  margin-bottom: 0.25em;
}

.markdown-content :deep(code) {
  background: var(--surface-2);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.9em;
}

.markdown-content :deep(pre) {
  background: var(--surface-2);
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin-bottom: 1em;
}

.markdown-content :deep(pre code) {
  background: none;
  padding: 0;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid var(--accent, #5b2fe3);
  padding-left: 16px;
  margin: 1em 0;
  color: var(--muted);
  font-style: italic;
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1em;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid var(--border);
  padding: 10px 14px;
  text-align: left;
}

.markdown-content :deep(th) {
  background: var(--surface-2);
  font-weight: 700;
}

.markdown-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}

.markdown-content :deep(a) {
  color: var(--accent, #5b2fe3);
  text-decoration: underline;
}

.markdown-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 2em 0;
}

.empty-content {
  padding: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--muted);
  font-size: 14px;
  background: var(--surface-2);
  border-radius: 12px;
}

.empty-icon {
  font-size: 32px;
  opacity: 0.5;
}
</style>
