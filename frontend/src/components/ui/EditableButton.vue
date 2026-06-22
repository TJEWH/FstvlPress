<template>
  <div 
      ref="rootEl"
      class="editable-button" 
      :class="{ 'editable-button--admin': isAdmin && !editing }"
      @mouseenter="hover = true" 
      @mouseleave="hover = false"
  >
    <!-- Display Mode -->
    <a
        :href="modelValue.url"
        :target="isExternal ? '_blank' : undefined"
        :rel="isExternal ? 'noopener noreferrer' : undefined"
        class="btn"
        :class="[buttonClass, { 'btn--empty': !displayText }]"
        :style="buttonStyle || {}"
        @click.prevent="isAdmin ? start() : navigateToUrl()"
    >
      {{ displayText || placeholder }}
    </a>

    <!-- Teleported popup: always above all content -->
    <Teleport to="body">
      <template v-if="editing">
        <div class="editor-backdrop" @click="close"></div>
        <div class="editor admin-editor-wrap" :style="editorPos" @click.stop>
          <div class="lang-field">
            <label class="lang-label">{{ t.german }} (DE) - Text</label>
            <input
                ref="fieldRefDe"
                v-model="draftTextDe"
                class="field"
                type="text"
                placeholder="Button Text..."
                @input="emitChange"
            />
          </div>

          <div class="lang-field">
            <label class="lang-label">{{ t.english }} (EN) - Text</label>
            <input
                v-model="draftTextEn"
                class="field"
                type="text"
                placeholder="Button Text..."
                @input="emitChange"
            />
          </div>

          <div class="lang-field">
            <label class="lang-label">Link URL</label>
            <input
                v-model="draftUrl"
                class="field"
                type="url"
                placeholder="https://..."
                @input="emitChange"
            />
          </div>

          <div v-if="buttonInstances.length > 0" class="lang-field">
            <label class="lang-label">Button Style</label>
            <select v-model="draftButtonType" class="field" @change="emitChange">
              <option v-for="inst in buttonInstances" :key="inst.id" :value="inst.id">{{ inst.label }}</option>
            </select>
          </div>

          <button
              v-if="removable"
              class="btn-secondary btn-remove-bottom"
              type="button"
              @click="remove"
          >
            {{ t.remove }}
          </button>
        </div>
      </template>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, watch, computed, nextTick, onBeforeUnmount } from "vue";
import { useStore } from "../../store/store.js";

const props = defineProps({
  // modelValue: { text: { de: string, en: string }, url: string }
  modelValue: { 
    type: Object, 
    default: () => ({ text: { de: "", en: "" }, url: "" }) 
  },
  isAdmin: { type: Boolean, default: false },
  buttonClass: { type: String, default: "" },
  buttonStyle: { type: Object, default: () => ({}) },
  placeholder: { type: String, default: "Button" },
  removable: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "remove"]);
const { state, t, logDebug } = useStore();

const hover = ref(false);
const editing = ref(false);
const draftTextDe = ref("");
const draftTextEn = ref("");
const draftUrl = ref("");
const draftButtonType = ref("secondary");
const fieldRefDe = ref(null);
const rootEl = ref(null);
const editorPos = ref({});

const buttonInstances = computed(() => {
  const instances = state.adminDesignConfig?.buttonInstances || [];
  const enabled = instances.filter(i => i.enabled);
  return enabled.length > 0 ? enabled : [
    { id: 'primary', label: 'Primary' },
    { id: 'secondary', label: 'Secondary' },
  ];
});

function inferButtonType() {
  if (props.modelValue?.buttonType) return props.modelValue.buttonType;
  const cls = props.buttonClass || "";
  if (cls.includes("ghost")) return "ghost";
  if (cls.includes("secondary")) return "secondary";
  return "secondary";
}

// Close editing when admin rights are revoked (logout / preview)
watch(() => props.isAdmin, (val) => {
  if (!val && editing.value) {
    close();
  }
});

// Helper to safely get i18n value
function getI18nValue(obj, lang) {
  if (!obj || typeof obj !== "object") return String(obj ?? "");
  return obj[lang] || "";
}

// Get current language text for display
const displayText = computed(() => {
  return getI18nValue(props.modelValue?.text, state.lang);
});

// Check if URL is external
const isExternal = computed(() => {
  const url = props.modelValue?.url || "";
  return url.startsWith("http://") || url.startsWith("https://");
});

// Sync drafts with modelValue when not editing
watch(
    () => props.modelValue,
    (v) => {
      if (!editing.value) {
        draftTextDe.value = getI18nValue(v?.text, "de");
        draftTextEn.value = getI18nValue(v?.text, "en");
        draftUrl.value = v?.url || "";
        draftButtonType.value = inferButtonType();
      }
    },
    { immediate: true, deep: true }
);

function start() {
  draftTextDe.value = getI18nValue(props.modelValue?.text, "de");
  draftTextEn.value = getI18nValue(props.modelValue?.text, "en");
  draftUrl.value = props.modelValue?.url || "";
  draftButtonType.value = inferButtonType();
  updateEditorPos();
  editing.value = true;
  window.addEventListener('scroll', updateEditorPos, true);
  nextTick(() => {
    fieldRefDe.value?.focus();
  });
}

function stopScrollListener() {
  window.removeEventListener('scroll', updateEditorPos, true);
}

function updateEditorPos() {
  const el = rootEl.value;
  if (!el) return;
  const rect = el.getBoundingClientRect();
  editorPos.value = {
    position: 'fixed',
    top: `${rect.bottom + 8}px`,
    left: `${Math.max(8, rect.left)}px`,
  };
}

function emitChange() {
  const next = {
    text: {
      de: String(draftTextDe.value ?? ""),
      en: String(draftTextEn.value ?? "")
    },
    url: String(draftUrl.value ?? ""),
    buttonType: draftButtonType.value || "secondary",
  };
  emit("update:modelValue", next);
}

function close() {
  emitChange();
  stopScrollListener();
  editing.value = false;
}

function remove() {
  stopScrollListener();
  emit("remove");
  editing.value = false;
}

onBeforeUnmount(stopScrollListener);

function navigateToUrl() {
  const url = props.modelValue?.url;
  if (url) {
    if (isExternal.value) {
      window.open(url, "_blank", "noopener,noreferrer");
    } else {
      window.location.href = url;
    }
  }
}
</script>

<style scoped>
.editable-button {
  position: relative;
  display: inline-block;
}

.editable-button--admin {
  cursor: pointer;
  margin: -4px;
  padding: 4px;
}

.editable-button--admin .btn::before {
  content: '';
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

.editable-button--admin:hover .btn::before {
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

.btn {
  position: relative;
  display: inline-block; /* Ensure consistent display for both <a> and <button> */
}

.btn--empty {
  opacity: 0.6;
  border-style: dashed;
}

.editor-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9998;
}

.editor {
  position: fixed;
  z-index: 9999;
  display: grid;
  gap: 12px;
  min-width: 300px;
  text-align: left;
}

.editor-header {
  display: flex;
  align-items: center;
}

.btn-remove-bottom {
  width: 100%;
  color: #dc2626 !important;
  border-color: #fecaca !important;
  background: #fef2f2 !important;
}

.btn-remove-bottom:hover {
  background: #fee2e2 !important;
}

.lang-field {
  display: grid;
  gap: 6px;
}

.lang-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted, #64748b);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field {
  width: 100%;
  border-radius: 8px;
  border: 1px solid var(--border, #e2e8f0);
  background: #fff;
  padding: 8px 12px;
  outline: none;
  color: var(--text, #1e293b);
  font-size: 14px;
}

.field:focus {
  border-color: var(--accent, #5b2fe3);
  box-shadow: 0 0 0 3px rgba(91, 47, 227, 0.1);
}
</style>
