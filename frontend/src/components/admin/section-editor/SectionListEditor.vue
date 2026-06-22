<template>
  <div class="section-list-editor">
    <AutosaveToast :message="autosaveToastMessage" :tone="autosaveToastTone" />

    <div v-if="showControlRow" class="reorder-controls">
      <slot name="control-primary" :can-reorder="canReorder" :reorder-active="isReorderActive" />
      <label v-if="showReorderToggle && canReorder" class="reorder-checkbox">
        <input
          type="checkbox"
          :checked="reorderMode"
          @change="setReorderMode($event.target.checked)"
        />
        <span>{{ reorderLabel }}</span>
      </label>
      <span v-if="isReorderActive" class="reorder-hint">Drag items to set the order.</span>
      <button
        v-if="showClear"
        type="button"
        class="btn-secondary btn-small clear-all-btn"
        :disabled="clearDisabled || !hasItems"
        @click="handleClearAll"
      >
        {{ clearLabel }}
      </button>
    </div>

    <div
      v-if="!isReorderActive"
      class="item-grid item-grid--inline-editor"
      :style="{ '--list-item-min-width': normalizedMinItemWidth }"
    >
      <template v-for="(item, index) in items" :key="resolveDraggableKey(item)">
        <button
          type="button"
          class="item-card"
          :class="{ 'item-card--open': index === selectedIndex }"
          @click="handleSelect(index)"
        >
          <div class="item-card__content">
            <slot name="item" :item="item" :index="index" :selected="index === selectedIndex" />
          </div>
        </button>

        <div
          v-if="index === selectedIndex"
          :key="`editor-${resolveDraggableKey(item)}`"
          class="editor editor--inline"
        >
          <div class="item-fields" :class="itemFieldsClass">
            <slot name="editor" :item="item" :index="index" />
          </div>
          <div class="editor-footer">
            <div v-if="showRemove" class="actions">
              <button
                class="btn-danger"
                type="button"
                :disabled="removeDisabled"
                @click="handleRemove"
              >
                {{ removeLabel }}
              </button>
            </div>
            <slot name="footer-actions" :item="item" :index="index" />
          </div>
        </div>
      </template>

      <button
        v-if="showAdd"
        type="button"
        class="item-card item-card--add"
        :disabled="addDisabled"
        @click="handleAdd"
      >
        <slot name="add">
          <div class="item-thumb item-thumb--add">
            <div class="thumb-empty">+</div>
            <!--span class="thumb-label">{{ addLabel }}</span-->
          </div>
        </slot>
      </button>
    </div>

    <draggable
      v-else
      :list="items"
      :item-key="resolveDraggableKey"
      class="item-grid item-grid--reorder"
      :style="{ '--list-item-min-width': normalizedMinItemWidth }"
      :disabled="!isReorderActive"
      ghost-class="item-card--ghost"
      chosen-class="item-card--chosen"
      drag-class="item-card--drag"
      @start="handleDragStart"
      @end="handleDragEnd"
    >
      <template #item="{ element: item, index }">
        <button
          type="button"
          class="item-card"
          :class="{ 'item-card--open': index === selectedIndex }"
          @click="handleSelect(index)"
        >
          <span
            class="item-card__drag-handle"
            title="Drag to reorder"
            aria-hidden="true"
          >⋮⋮</span>
          <div class="item-card__content item-card__content--reorder">
            <slot name="item" :item="item" :index="index" :selected="index === selectedIndex" />
          </div>
        </button>
      </template>
      <template #footer>
        <button
          v-if="showAdd"
          type="button"
          class="item-card item-card--add"
          :disabled="addDisabled"
          @click="handleAdd"
        >
          <slot name="add">
            <div class="item-thumb item-thumb--add">
              <div class="thumb-empty">+</div>
              <!--span class="thumb-label">{{ addLabel }}</span-->
            </div>
          </slot>
        </button>
      </template>
    </draggable>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch, useSlots } from "vue";
import draggable from "vuedraggable";
import AutosaveToast from "../AutosaveToast.vue";

const props = defineProps({
  items: { type: Array, default: () => [] },
  selectedIndex: { type: Number, default: -1 },
  addLabel: { type: String, default: "Add item" },
  saveLabel: { type: String, default: "Save" },
  removeLabel: { type: String, default: "Remove" },
  clearLabel: { type: String, default: "Clear" },
  saveDisabled: { type: Boolean, default: false },
  removeDisabled: { type: Boolean, default: false },
  clearDisabled: { type: Boolean, default: false },
  showSave: { type: Boolean, default: true },
  showRemove: { type: Boolean, default: true },
  showClear: { type: Boolean, default: false },
  showAdd: { type: Boolean, default: true },
  addDisabled: { type: Boolean, default: false },
  saveOnRemove: { type: Boolean, default: true },
  saveOnReorder: { type: Boolean, default: true },
  allowReorder: { type: Boolean, default: true },
  forceReorderMode: { type: Boolean, default: false },
  showReorderToggle: { type: Boolean, default: true },
  reorderLabel: { type: String, default: "Reorder" },
  clearConfirmMessage: { type: String, default: "Remove all list items? This can be undone in history tab." },
  minItemWidth: { type: [Number, String], default: 110 },
  itemFieldsClass: { type: [String, Array, Object], default: "" },
});

const emit = defineEmits(["select", "add", "save", "remove", "clear", "reorder"]);
const slots = useSlots();

const hasSelection = computed(
  () => props.selectedIndex >= 0 && props.selectedIndex < props.items.length
);
const selectedItem = computed(() =>
  hasSelection.value ? props.items[props.selectedIndex] : null
);
const normalizedMinItemWidth = computed(() => {
  if (typeof props.minItemWidth === "number") return `${props.minItemWidth}px`;
  return props.minItemWidth || "110px";
});
const hasItems = computed(() => Array.isArray(props.items) && props.items.length > 0);
const canReorder = computed(
  () => props.allowReorder && Array.isArray(props.items) && props.items.length > 1
);
const hasPrimaryControlSlot = computed(() => Boolean(slots["control-primary"]));
const isReorderActive = computed(() =>
  canReorder.value && (props.forceReorderMode || reorderMode.value)
);
const showControlRow = computed(() =>
  (canReorder.value && (props.showReorderToggle || props.forceReorderMode))
  || props.showClear
  || hasPrimaryControlSlot.value
);
const reorderMode = ref(false);
const dragSelectedItem = ref(null);
const selectedItemSnapshot = ref("");
const autosaveToastMessage = ref("");
const autosaveToastTone = ref("idle");
const fallbackItemKeys = new WeakMap();
let fallbackItemKeyCount = 0;
let autosaveToastTimer = null;

watch(canReorder, (enabled) => {
  if (!enabled) reorderMode.value = false;
}, { immediate: true });

function handlePageHide() {
  autosaveCurrentSelection({ showToast: false });
}

onMounted(() => {
  window.addEventListener("pagehide", handlePageHide);
});

onBeforeUnmount(() => {
  window.removeEventListener("pagehide", handlePageHide);
  autosaveCurrentSelection({ showToast: false });
  clearAutosaveToastTimer();
});

watch(reorderMode, (enabled) => {
  if (enabled) saveAndCloseEditor();
});

watch(
  () => props.forceReorderMode,
  (enabled, previous) => {
    if (enabled && !previous) saveAndCloseEditor();
  },
  { immediate: true }
);

watch(
  () => props.selectedIndex,
  () => {
    selectedItemSnapshot.value = hasSelection.value
      ? snapshotListEditorItem(selectedItem.value)
      : "";
  },
  { immediate: true }
);

function normalizeSnapshotValue(value) {
  if (Array.isArray(value)) {
    return value.map((entry) => normalizeSnapshotValue(entry));
  }
  if (!value || typeof value !== "object") {
    return value;
  }
  return Object.keys(value)
    .sort()
    .reduce((result, key) => {
      result[key] = normalizeSnapshotValue(value[key]);
      return result;
    }, {});
}

function snapshotListEditorItem(item) {
  try {
    return JSON.stringify(normalizeSnapshotValue(item));
  } catch {
    return String(item ?? "");
  }
}

function setReorderMode(checked) {
  if (props.forceReorderMode) return;
  reorderMode.value = canReorder.value && Boolean(checked);
}

function saveAndCloseEditor() {
  autosaveCurrentSelection();
  emit("select", -1);
}

function handleSelect(index) {
  if (isReorderActive.value) return;
  autosaveCurrentSelection();
  const nextIndex = Number.parseInt(index, 10);
  const currentIndex = Number.parseInt(props.selectedIndex, 10);
  if (!Number.isFinite(nextIndex)) {
    emit("select", -1);
    return;
  }
  emit("select", currentIndex === nextIndex ? -1 : nextIndex);
}

function handleAdd() {
  if (props.addDisabled) return;
  emit("add");
}

function autosaveCurrentSelection({ showToast = true } = {}) {
  if (hasSelection.value && !props.saveDisabled) {
    const nextSnapshot = snapshotListEditorItem(selectedItem.value);
    if (nextSnapshot === selectedItemSnapshot.value) {
      return;
    }
    selectedItemSnapshot.value = nextSnapshot;
    if (showToast) showAutosaveToast("Saving item changes...", "saving");
    emit("save", props.selectedIndex);
  }
}

function clearAutosaveToastTimer() {
  if (autosaveToastTimer) {
    clearTimeout(autosaveToastTimer);
    autosaveToastTimer = null;
  }
}

function showAutosaveToast(message, tone = "saving") {
  clearAutosaveToastTimer();
  autosaveToastMessage.value = message;
  autosaveToastTone.value = tone;
  autosaveToastTimer = setTimeout(() => {
    autosaveToastMessage.value = "";
    autosaveToastTone.value = "idle";
    autosaveToastTimer = null;
  }, 3000);
}

function resolveDraggableKey(item) {
  const id = item?.id;
  if (id !== undefined && id !== null && String(id).trim() !== "") return String(id);
  if (item && typeof item === "object") {
    if (!fallbackItemKeys.has(item)) {
      fallbackItemKeyCount += 1;
      fallbackItemKeys.set(item, `list-item-${fallbackItemKeyCount}`);
    }
    return fallbackItemKeys.get(item);
  }
  return `list-item-${String(item)}`;
}

function handleDragStart() {
  dragSelectedItem.value = hasSelection.value ? selectedItem.value : null;
}

function handleDragEnd(event) {
  const oldIndex = Number.parseInt(event?.oldIndex, 10);
  const newIndex = Number.parseInt(event?.newIndex, 10);
  if (!Number.isFinite(oldIndex) || !Number.isFinite(newIndex) || oldIndex < 0 || newIndex < 0 || oldIndex === newIndex) {
    return;
  }

  emit("reorder", { oldIndex, newIndex, items: props.items });

  if (props.saveOnReorder && !props.saveDisabled) {
    emit("save");
  }

  if (dragSelectedItem.value) {
    const nextIndex = props.items.indexOf(dragSelectedItem.value);
    emit("select", nextIndex >= 0 ? nextIndex : -1);
  }
}

function handleRemove() {
  if (props.removeDisabled) return;
  const index = props.selectedIndex;
  if (index < 0 || index >= props.items.length) return;
  // Remove should immediately persist so the live section view updates as expected.
  // Parents can disable this by passing :save-on-remove="false".
  if (props.saveOnRemove) {
    emit("remove", index);
    emit("save");
    return;
  }
  emit("remove", index);
}

function handleClearAll() {
  if (!props.showClear) return;
  if (props.clearDisabled || !hasItems.value) return;
  const message = String(props.clearConfirmMessage || "Remove all list items?");
  if (!window.confirm(message)) return;
  emit("clear");
}
</script>

<style scoped>
.section-list-editor {
  display: grid;
  gap: 12px;
}

.reorder-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.reorder-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text, #2b0c5c);
  cursor: pointer;
}

.reorder-checkbox input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.reorder-hint {
  font-size: 12px;
  color: var(--muted, #64748b);
}

.clear-all-btn {
  margin-left: auto;
}

.editor {
  position: relative;
  display: grid;
  gap: 10px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.12));
  border-radius: 12px;
  padding: 24px;
  background: #f8fafc;
}

.editor--inline {
  grid-column: 1 / -1;
  z-index: 3;
}

.item-fields {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.item-fields :deep(input::placeholder),
.item-fields :deep(textarea::placeholder),
.item-fields :deep(.dp__input::placeholder) {
  color: var(--admin-text-muted, var(--muted, #64748b));
  opacity: 0.58;
}

.item-fields--source-locked :deep(.field-group--disabled) {
  opacity: 0.72;
}

.item-fields--source-locked :deep(.field-group--disabled .field-label) {
  color: #64748b;
}

.item-fields--source-locked :deep(.field-group--disabled .field:disabled),
.item-fields--source-locked :deep(.field-group--disabled .field-textarea:disabled),
.item-fields--source-locked :deep(.field-group--disabled select:disabled),
.item-fields--source-locked :deep(.field-group--disabled input:disabled),
.item-fields--source-locked :deep(.field-group--disabled textarea:disabled) {
  border-color: #cbd5e1;
  background: #f1f5f9;
  color: #64748b;
  cursor: not-allowed;
  -webkit-text-fill-color: #64748b;
}

.item-fields--source-locked :deep(.field-group--disabled .program-datetime-picker .dp__input) {
  border-color: #cbd5e1;
  background: #f1f5f9;
  color: #64748b;
  cursor: not-allowed;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.editor-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.item-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(var(--list-item-min-width, 110px), 1fr));
  gap: 10px;
}

.item-grid--inline-editor {
  grid-auto-flow: dense;
}

.item-card {
  position: relative;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.03);
  border: 1px solid var(--border, rgba(43, 12, 92, 0.12));
  cursor: pointer;
  transition: box-shadow 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
  overflow: hidden;
  text-align: left;
  padding: 0;
  color: inherit;
}

.item-card:hover:not(:disabled):not(.item-card--open) {
  border-color: var(--accent, #4f46e5);
  box-shadow: 0 0 0 1px var(--accent, #4f46e5);
  transform: translateY(-1px);
}

.item-grid--reorder .item-card {
  cursor: grab;
}

.item-grid--reorder .item-card:hover:not(:disabled):not(.item-card--open) {
  transform: none;
}

.item-grid--reorder .item-card:active {
  cursor: grabbing;
}

.item-card--open {
  border-color: var(--accent, #4f46e5);
  box-shadow: 0 0 0 1px var(--accent, #4f46e5);
}

.item-card--ghost {
  opacity: 0.45;
}

.item-card--chosen {
  border-color: var(--accent, #4f46e5);
  box-shadow: 0 0 0 1px var(--accent, #4f46e5);
}

.item-card--drag {
  cursor: grabbing;
}

.item-card--add {
  border-style: dashed;
  border-color: color-mix(in srgb, var(--accent, #4f46e5) 45%, transparent);
  background: color-mix(in srgb, var(--accent, #4f46e5) 4%, transparent);
}

.item-card--add:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
}

.item-card__drag-handle {
  position: absolute;
  top: 6px;
  right: 8px;
  font-size: 15px;
  line-height: 1;
  letter-spacing: -1px;
  color: var(--muted, #64748b);
  cursor: grab;
  user-select: none;
  touch-action: none;
  z-index: 2;
}

.item-card__drag-handle:active {
  cursor: grabbing;
}

.item-card__content {
  width: 100%;
}

.item-card__content--reorder {
  pointer-events: none;
}

:deep(.item-thumb) {
  padding: 10px;
  min-width: 0;
}

:deep(.item-thumb--media) {
  display: grid;
  place-items: center;
  gap: 6px;
}

:deep(.item-thumb--text) {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
}

:deep(.thumb-img-wrap) {
  width: 80px;
  height: 60px;
  border-radius: 8px;
  overflow: hidden;
  background-color: #f8fafc;
  background-image:
    linear-gradient(45deg, rgba(148, 163, 184, 0.24) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(148, 163, 184, 0.24) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(148, 163, 184, 0.24) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(148, 163, 184, 0.24) 75%);
  background-size: 12px 12px;
  background-position: 0 0, 0 6px, 6px -6px, -6px 0;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: outline 0.15s ease, opacity 0.15s ease;
  outline: 2px solid transparent;
  flex-shrink: 0;
}

:deep(.thumb-img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

:deep(.thumb-empty) {
  font-size: 20px;
  font-weight: 700;
  color: var(--muted, #94a3b8);
  opacity: 0.5;
}

:deep(.thumb-label) {
  font-size: 11px;
  font-weight: 600;
  color: var(--muted, #64748b);
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.item-thumb--add {
  display: grid;
  place-items: center;
  gap: 6px;
}

.thumb-empty {
  color: var(--accent, #4f46e5);
  opacity: 0.9;
}

.thumb-label {
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
</style>
