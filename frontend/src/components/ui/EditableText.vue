<template>
  <template v-if="plainView && !editing">
    <component
      :is="asTag"
      :class="[displayClass, { 'editable-plain--admin': isAdmin && !disabled, 'editable-plain--disabled': disabled }]"
      :title="disabled ? disabledHint : undefined"
      @click="isAdmin && !disabled && start()"
    >
      <template v-if="hasSlot">
        <slot />
      </template>
      <template v-else>
        <span v-if="displayText">{{ displayText }}</span>
        <span v-else-if="placeholder && isAdmin" class="editable-placeholder">{{ placeholder }}</span>
      </template>
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
      <component :is="asTag" :class="displayClass">
        <template v-if="hasSlot">
          <slot />
        </template>

        <template v-else>
          <span v-if="displayText" >{{ displayText }}</span>
          <span v-else-if="placeholder && isAdmin" class="editable-placeholder">{{ placeholder }}</span>
        </template>
      </component>

      <button
          v-if="showReadMore"
          class="readmore"
          type="button"
          @click="expanded = !expanded"
      >
        {{ expanded ? (t.readLess || "Weniger") : (t.readMore || "Mehr") }}
      </button>
    </div>

    <div v-else class="editor admin-editor-wrap" @click.stop>
      <!-- German input -->
      <div class="lang-field">
        <label class="lang-label">{{ t.german }} (DE)</label>
        <textarea
            v-if="multiline"
            ref="fieldRefDe"
            v-model="draftDe"
            class="field"
            rows="4"
            :placeholder="placeholder || '...'"
        ></textarea>
        <input
            v-else
            ref="fieldRefDe"
            v-model="draftDe"
            class="field"
            type="text"
            :placeholder="placeholder || '...'"
        />
      </div>

      <!-- English input -->
      <div class="lang-field">
        <label class="lang-label">{{ t.english }} (EN)</label>
        <textarea
            v-if="multiline"
            v-model="draftEn"
            class="field"
            rows="4"
            :placeholder="placeholder || '...'"
        ></textarea>
        <input
            v-else
            v-model="draftEn"
            class="field"
            type="text"
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
import { ref, watch, computed, useSlots, nextTick } from "vue";
import { useStore } from "../../store/store.js";

const props = defineProps({
  // modelValue is now an i18n object: { de: string, en: string }
  modelValue: { type: Object, default: () => ({ de: "", en: "" }) },
  multiline: { type: Boolean, default: false },
  isAdmin: { type: Boolean, default: false },

  as: { type: String, default: "div" },
  displayClass: { type: String, default: "" },

  collapsible: { type: Boolean, default: false },
  maxChars: { type: Number, default: 260 },
  plainView: { type: Boolean, default: false },
  
  placeholder: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
  disabledHint: { type: String, default: "Managed by integration import." }
});

const emit = defineEmits(["update:modelValue"]);
const { state, t, logDebug } = useStore();

const slots = useSlots();
const hasSlot = computed(() => !!slots.default);

const hover = ref(false);
const editing = ref(false);
const draftDe = ref("");
const draftEn = ref("");
const fieldRefDe = ref(null);

const expanded = ref(false);

const asTag = computed(() => props.as || "div");
const plainView = computed(() => props.plainView === true);

// Close editing when admin rights are revoked (logout / preview)
watch(() => props.isAdmin, (val) => {
  if (!val && editing.value) {
    cancel();
  }
});

watch(() => props.disabled, (val) => {
  if (val && editing.value) {
    cancel();
  }
});

// Helper to safely get i18n value with fallback to German
function getI18nValue(obj, lang, fallbackToDE = false) {
  if (!obj || typeof obj !== "object") return String(obj ?? "");
  const value = obj[lang];
  // If fallback enabled and current language is empty, try German
  if (fallbackToDE && !value && lang !== "de") {
    return obj["de"] || "";
  }
  return value || "";
}

// Get current language text for display (with fallback to German)
const currentText = computed(() => getI18nValue(props.modelValue, state.lang, true));

// Sync drafts with modelValue when not editing
watch(
    () => props.modelValue,
    (v) => {
      if (!editing.value) {
        draftDe.value = getI18nValue(v, "de");
        draftEn.value = getI18nValue(v, "en");
      }
    },
    { immediate: true }
);

const canCollapse = computed(() => {
  if (hasSlot.value) return false;
  if (!props.collapsible) return false;
  return currentText.value.length > props.maxChars;
});

const showReadMore = computed(() => canCollapse.value);

const displayText = computed(() => {
  const txt = currentText.value;
  if (!canCollapse.value) return txt;
  if (expanded.value) return txt;
  return txt.slice(0, props.maxChars).trimEnd() + "…";
});

function start() {
  if (props.disabled) return;
  draftDe.value = getI18nValue(props.modelValue, "de");
  draftEn.value = getI18nValue(props.modelValue, "en");
  editing.value = true;
  nextTick(() => {
    fieldRefDe.value?.focus();
  });
}

function save() {
  if (props.disabled) {
    cancel();
    return;
  }
  const next = {
    de: String(draftDe.value ?? ""),
    en: String(draftEn.value ?? "")
  };

  if (state._debug?.enabled) {
    logDebug("EditableText.save", { prev: props.modelValue, next });
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

.editable:has(.admin-editor-wrap) {
  z-index: 500000;
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

.editor { display: grid; gap: 14px; }

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
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  
  .editor .lang-field textarea.field {
    flex: 1;
    min-height: 120px;
    resize: none;
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

.lang-field { display: grid; gap: 6px; }

.lang-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field {
  width: 100%;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: #fff;
  padding: 10px 12px;
  outline: none;
  color: var(--text);
}

.row { display: flex; gap: 10px; flex-wrap: wrap; }

.readmore {
  margin-top: 8px;
  background: transparent;
  border: 0;
  padding: 0;
  cursor: pointer;
  color: rgba(255,255,255,0.92);
  text-decoration: underline;
  text-decoration-color: rgba(255,255,255,0.55);
  font-weight: 800;
}

.editable-placeholder {
  opacity: 0.5;
  font-style: italic;
}
</style>
