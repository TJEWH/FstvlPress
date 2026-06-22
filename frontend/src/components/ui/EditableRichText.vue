<template>
  <template v-if="plainView && !editing">
    <component
      v-if="displayHtml"
      :is="asTag"
      :class="[displayClass, 'rich-render', { 'editable-plain--admin': isAdmin && !disabled, 'editable-plain--disabled': disabled }]"
      :title="disabled ? disabledHint : undefined"
      v-html="displayHtml"
      @click="isAdmin && !disabled && start()"
    />
    <component
      v-else
      :is="asTag"
      :class="[displayClass, { 'editable-plain--admin': isAdmin && !disabled, 'editable-plain--disabled': disabled }]"
      :title="disabled ? disabledHint : undefined"
      @click="isAdmin && !disabled && start()"
    >
      <span v-if="placeholder && isAdmin" class="editable-placeholder">{{ placeholder }}</span>
    </component>
  </template>
  <div
    v-else
    class="editable"
    :class="{ 'editable--admin': isAdmin && !editing && !disabled, 'editable--disabled': disabled }"
    :title="disabled ? disabledHint : undefined"
    @mouseenter="hover = true"
    @mouseleave="hover = false"
    @click="isAdmin && !editing && !disabled && start()"
  >
    <div v-if="!editing" class="view">
      <component
        v-if="displayHtml"
        :is="asTag"
        :class="[displayClass, 'rich-render']"
        v-html="displayHtml"
      />
      <component v-else :is="asTag" :class="displayClass">
        <span v-if="placeholder && isAdmin" class="editable-placeholder">{{ placeholder }}</span>
      </component>
    </div>

    <div v-else class="editor admin-editor-wrap" @click.stop>
      <div class="lang-field">
        <label class="lang-label">{{ t.german }} (DE)</label>
        <QuillEditor
          v-model:content="draftDe"
          content-type="html"
          theme="snow"
          :toolbar="quillToolbar"
          :placeholder="placeholder || '...'"
        />
      </div>

      <div class="lang-field">
        <label class="lang-label">{{ t.english }} (EN)</label>
        <QuillEditor
          v-model:content="draftEn"
          content-type="html"
          theme="snow"
          :toolbar="quillToolbar"
          :placeholder="placeholder || '...'"
        />
      </div>

      <div class="row">
        <button class="btn" type="button" @click="save">{{ t.save }}</button>
        <button class="btn-secondary" type="button" @click="cancel">{{ t.cancel }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import DOMPurify from "dompurify";
import { QuillEditor, Quill } from "@vueup/vue-quill";
import "@vueup/vue-quill/dist/vue-quill.snow.css";

import { useStore } from "../../store/store.js";

try {
  const globalKey = "__sscQuillDivBlockRegistered";
  if (!globalThis[globalKey]) {
    const Block = Quill.import("blots/block");
    class DivBlock extends Block {}

    DivBlock.tagName = "DIV";
    // true means overwrite the default blot
    Quill.register("blots/block", DivBlock, true);
    globalThis[globalKey] = true;
  }
} catch (error) {
  console.warn("Failed to register Quill DIV block override:", error);
}

const props = defineProps({
  modelValue: { type: Object, default: () => ({ de: "", en: "" }) },
  isAdmin: { type: Boolean, default: false },
  as: { type: String, default: "div" },
  displayClass: { type: String, default: "" },
  plainView: { type: Boolean, default: false },
  placeholder: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
  disabledHint: { type: String, default: "Managed by integration import." },
});

const emit = defineEmits(["update:modelValue"]);
const { state, t, logDebug } = useStore();

const hover = ref(false);
const editing = ref(false);
const draftDe = ref("");
const draftEn = ref("");

const quillToolbar = [
  [{ header: [1, 2, 3, false] }],
  ["bold", "italic", "underline", "strike"],
  [{ list: "ordered" }, { list: "bullet" }],
  [{ indent: "-1" }, { indent: "+1" }],
  [{ align: [] }],
  ["blockquote", "link", "image", "video"],
  ["clean"],
];

const asTag = computed(() => props.as || "div");
const plainView = computed(() => props.plainView === true);

watch(
  () => props.isAdmin,
  (value) => {
    if (!value && editing.value) {
      cancel();
    }
  }
);

watch(
  () => props.disabled,
  (value) => {
    if (value && editing.value) {
      cancel();
    }
  }
);

watch(
  () => props.modelValue,
  (value) => {
    if (!editing.value) {
      draftDe.value = getI18nValue(value, "de");
      draftEn.value = getI18nValue(value, "en");
    }
  },
  { immediate: true }
);

const currentText = computed(() => getI18nValue(props.modelValue, state.lang, true));
const displayHtml = computed(() => toSafeHtml(currentText.value));

function getI18nValue(obj, lang, fallbackToDE = false) {
  if (!obj || typeof obj !== "object") return String(obj ?? "");
  const value = obj[lang];
  if (fallbackToDE && !value && lang !== "de") {
    return obj.de || "";
  }
  return value || "";
}

function isLikelyHtml(value) {
  return /<\/?[a-z][\s\S]*>/i.test(value);
}

function escapeHtml(value) {
  return value
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

  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
  });
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

function start() {
  if (props.disabled) return;
  draftDe.value = getI18nValue(props.modelValue, "de");
  draftEn.value = getI18nValue(props.modelValue, "en");
  editing.value = true;
}

function save() {
  if (props.disabled) {
    cancel();
    return;
  }
  const next = {
    de: normalizeEditorContent(draftDe.value),
    en: normalizeEditorContent(draftEn.value),
  };

  if (state._debug?.enabled) {
    logDebug("EditableRichText.save", { prev: props.modelValue, next });
  }

  emit("update:modelValue", next);
  editing.value = false;
}

function cancel() {
  draftDe.value = getI18nValue(props.modelValue, "de");
  draftEn.value = getI18nValue(props.modelValue, "en");
  editing.value = false;
}
</script>

<style scoped>
.editable {
  position: relative;
  border-radius: 12px;
}

.editable-plain--admin {
  cursor: pointer;
}

.editable-plain--disabled,
.editable--disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

.editable--admin {
  cursor: pointer;
  margin: -4px;
  padding: 4px;
}

.editable--admin::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  mix-blend-mode: difference;
  background:
    linear-gradient(90deg, #fff 50%, transparent 50%) top,
    linear-gradient(90deg, #fff 50%, transparent 50%) bottom,
    linear-gradient(0deg, #fff 50%, transparent 50%) left,
    linear-gradient(0deg, #fff 50%, transparent 50%) right;
  background-size: 8px 2px, 8px 2px, 2px 8px, 2px 8px;
  background-repeat: repeat-x, repeat-x, repeat-y, repeat-y;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.editable--admin:hover::before {
  opacity: 1;
  animation: marching-ants 0.4s linear infinite;
}

@keyframes marching-ants {
  0% {
    background-position: 0 0, 0 100%, 0 0, 100% 0;
  }
  100% {
    background-position: 8px 0, -8px 100%, 0 -8px, 100% 8px;
  }
}

.editor {
  display: grid;
  gap: 14px;
}

.lang-field {
  display: grid;
  gap: 6px;
}

.lang-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.lang-field :deep(.ql-toolbar) {
  border-radius: 12px 12px 0 0;
  border-color: var(--border, #e2e8f0);
}

.lang-field :deep(.ql-container) {
  min-height: 140px;
  border-radius: 0 0 12px 12px;
  border-color: var(--border, #e2e8f0);
  background: #fff;
}

.lang-field :deep(.ql-editor) {
  min-height: 140px;
  color: var(--text);
}

.row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
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

.editable-placeholder {
  opacity: 0.5;
  font-style: italic;
}

@media (max-width: 640px) {
  .editor {
    position: fixed;
    inset: 0;
    z-index: 1000;
    background: var(--surface, #fff);
    padding: 16px;
    padding-top: env(safe-area-inset-top, 16px);
    padding-bottom: env(safe-area-inset-bottom, 16px);
    overflow-y: auto;
    border-radius: 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .editor .lang-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .editor .lang-field :deep(.ql-container) {
    min-height: 180px;
  }

  .editor .lang-field :deep(.ql-editor) {
    min-height: 180px;
  }

  .editor .row {
    margin-top: auto;
    padding-top: 12px;
    border-top: 1px solid var(--border, #e2e8f0);
  }

  .editor .row .btn {
    flex: 1;
    padding: 14px;
    font-size: 16px;
  }
}
</style>
