<template>
  <div ref="rootRef" class="todo-icon-select" :class="{ 'is-open': open, 'is-disabled': disabled }">
    <button
      ref="triggerRef"
      type="button"
      class="todo-icon-select__trigger"
      :class="{ 'has-icon': Boolean(selectedOption?.icon) }"
      :disabled="disabled"
      :title="selectedOption?.iconLabel || selectedOption?.label || ariaLabel"
      :aria-label="ariaLabel || selectedOption?.iconLabel || selectedOption?.label"
      :aria-expanded="open ? 'true' : 'false'"
      :aria-controls="menuId"
      aria-haspopup="listbox"
      @click="toggle"
      @keydown="onTriggerKeydown"
    >
      <font-awesome-icon
        v-if="selectedOption?.icon"
        :icon="selectedOption.icon"
        class="todo-icon-select__selected-icon"
        aria-hidden="true"
      />
      <span class="todo-icon-select__selected-label">{{ selectedOption?.label || placeholder }}</span>
      <font-awesome-icon
        :icon="['fas', 'angle-down']"
        class="todo-icon-select__arrow"
        :class="{ 'is-open': open }"
        aria-hidden="true"
      />
    </button>

    <Teleport to="body">
      <div
        v-if="open"
        ref="menuRef"
        :id="menuId"
        class="todo-icon-select__menu"
        :style="menuStyle"
        role="listbox"
        :aria-label="ariaLabel"
        @keydown="onMenuKeydown"
      >
        <button
          v-for="(option, index) in normalizedOptions"
          :key="String(option.value)"
          type="button"
          class="todo-icon-select__option"
          :class="{
            'is-selected': option.value === modelValue,
            'is-active': index === activeIndex,
          }"
          role="option"
          :aria-selected="option.value === modelValue ? 'true' : 'false'"
          :title="option.iconLabel || option.label"
          @click="selectOption(option)"
          @mouseenter="activeIndex = index"
        >
          <font-awesome-icon
            v-if="option.icon"
            :icon="option.icon"
            class="todo-icon-select__option-icon"
            aria-hidden="true"
          />
          <span v-else class="todo-icon-select__option-icon-spacer" aria-hidden="true"></span>
          <span class="todo-icon-select__option-label">{{ option.label }}</span>
          <font-awesome-icon
            v-if="option.value === modelValue"
            :icon="['fas', 'check']"
            class="todo-icon-select__check"
            aria-hidden="true"
          />
        </button>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  ref,
  watch,
} from "vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: "Select" },
  ariaLabel: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue"]);

const open = ref(false);
const activeIndex = ref(-1);
const rootRef = ref(null);
const triggerRef = ref(null);
const menuRef = ref(null);
const menuStyle = ref({});
const menuId = `todo-icon-select-${Math.random().toString(36).slice(2, 9)}`;

const normalizedOptions = computed(() =>
  props.options.map((option) => {
    if (option && typeof option === "object") {
      const value = String(option.value ?? "");
      return {
        value,
        label: String(option.label ?? value),
        icon: option.icon || null,
        iconLabel: option.iconLabel ? String(option.iconLabel) : "",
      };
    }
    const value = String(option ?? "");
    return { value, label: value, icon: null, iconLabel: "" };
  }),
);

const selectedOption = computed(() =>
  normalizedOptions.value.find((option) => option.value === props.modelValue)
  || normalizedOptions.value[0]
  || null
);

watch(
  () => props.modelValue,
  () => {
    activeIndex.value = selectedIndex();
  },
);

watch(open, async (isOpen) => {
  if (!isOpen) {
    removePositionListeners();
    return;
  }
  activeIndex.value = selectedIndex();
  await nextTick();
  updateMenuPosition();
  addPositionListeners();
});

function selectedIndex() {
  const index = normalizedOptions.value.findIndex((option) => option.value === props.modelValue);
  return index >= 0 ? index : 0;
}

function toggle() {
  if (props.disabled) return;
  open.value ? close() : openMenu();
}

function openMenu() {
  if (props.disabled || normalizedOptions.value.length === 0) return;
  open.value = true;
}

function close() {
  open.value = false;
}

function selectOption(option) {
  emit("update:modelValue", option.value);
  close();
  nextTick(() => triggerRef.value?.focus());
}

function moveActive(direction) {
  const total = normalizedOptions.value.length;
  if (total === 0) return;
  const current = activeIndex.value >= 0 ? activeIndex.value : selectedIndex();
  activeIndex.value = (current + direction + total) % total;
}

function onTriggerKeydown(event) {
  if (event.key === "ArrowDown") {
    event.preventDefault();
    if (!open.value) openMenu();
    else moveActive(1);
    return;
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    if (!open.value) openMenu();
    else moveActive(-1);
    return;
  }
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (!open.value) openMenu();
    else selectActive();
    return;
  }
  if (event.key === "Escape") {
    close();
    return;
  }
  if (event.key === "Tab") {
    close();
  }
}

function onMenuKeydown(event) {
  onTriggerKeydown(event);
}

function selectActive() {
  const option = normalizedOptions.value[activeIndex.value];
  if (option) selectOption(option);
}

function updateMenuPosition() {
  const trigger = triggerRef.value;
  if (!trigger) return;
  const rect = trigger.getBoundingClientRect();
  const gap = 4;
  const viewportPadding = 8;
  const optionHeight = 36;
  const menuHeight = Math.min(
    Math.max(normalizedOptions.value.length, 1) * optionHeight,
    240,
  );
  const spaceBelow = window.innerHeight - rect.bottom - viewportPadding;
  const spaceAbove = rect.top - viewportPadding;
  const openAbove = spaceBelow < menuHeight && spaceAbove > spaceBelow;
  const maxHeight = Math.max(
    120,
    Math.min(240, (openAbove ? spaceAbove : spaceBelow) - gap),
  );

  menuStyle.value = {
    position: "fixed",
    left: `${Math.max(viewportPadding, rect.left)}px`,
    top: openAbove ? "auto" : `${rect.bottom + gap}px`,
    bottom: openAbove ? `${window.innerHeight - rect.top + gap}px` : "auto",
    width: `${rect.width}px`,
    maxHeight: `${maxHeight}px`,
    zIndex: 100000,
  };
}

function onDocumentPointerDown(event) {
  const target = event.target;
  if (rootRef.value?.contains(target) || menuRef.value?.contains(target)) return;
  close();
}

function onWindowChange() {
  if (open.value) updateMenuPosition();
}

function addPositionListeners() {
  document.addEventListener("pointerdown", onDocumentPointerDown, true);
  window.addEventListener("resize", onWindowChange);
  window.addEventListener("scroll", onWindowChange, true);
}

function removePositionListeners() {
  document.removeEventListener("pointerdown", onDocumentPointerDown, true);
  window.removeEventListener("resize", onWindowChange);
  window.removeEventListener("scroll", onWindowChange, true);
}

onBeforeUnmount(removePositionListeners);
</script>

<style scoped>
.todo-icon-select {
  min-width: 0;
  width: 100%;
}

.todo-icon-select__trigger {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  min-width: 0;
  min-height: 32px;
  border: 1px solid #cbd5e1;
  border-radius: 9px;
  background: #ffffff;
  color: var(--admin-text, #0f172a);
  padding: 7px 9px;
  font: inherit;
  font-size: 12px;
  line-height: 1.2;
  text-align: left;
  cursor: pointer;
}

.todo-icon-select__trigger:hover {
  border-color: #cbd5e1;
}

.todo-icon-select__trigger:focus-visible,
.todo-icon-select.is-open .todo-icon-select__trigger {
  outline: none;
  border-color: #94a3b8;
  box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.22);
}

.todo-icon-select__selected-icon,
.todo-icon-select__option-icon,
.todo-icon-select__option-icon-spacer {
  flex: 0 0 auto;
  width: 0.95em;
  color: currentColor;
}

.todo-icon-select__selected-icon {
  color: var(--admin-text-muted, #64748b);
}

.todo-icon-select__selected-label,
.todo-icon-select__option-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-icon-select__selected-label {
  flex: 1 1 auto;
}

.todo-icon-select__arrow {
  flex: 0 0 auto;
  width: 0.85em;
  color: var(--admin-text-muted, #64748b);
  transition: transform 0.15s ease;
}

.todo-icon-select__arrow.is-open {
  transform: rotate(180deg);
}

.todo-icon-select__menu {
  box-sizing: border-box;
  display: grid;
  align-content: start;
  min-width: 0;
  padding: 4px;
  border: 1px solid #cbd5e1;
  border-radius: 9px;
  background: #ffffff;
  color: var(--admin-text, #0f172a);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.18);
  overflow-y: auto;
  overscroll-behavior: contain;
}

.todo-icon-select__option {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  min-width: 0;
  min-height: 34px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: inherit;
  padding: 7px 8px;
  font: inherit;
  font-size: 12px;
  line-height: 1.2;
  text-align: left;
  cursor: pointer;
}

.todo-icon-select__option:hover,
.todo-icon-select__option.is-active {
  background: color-mix(in srgb, var(--admin-accent, var(--accent, #4f46e5)) 10%, transparent);
}

.todo-icon-select__option.is-selected {
  color: var(--admin-accent, var(--accent, #4f46e5));
  font-weight: 700;
}

.todo-icon-select__check {
  flex: 0 0 auto;
  width: 0.9em;
  margin-left: auto;
}
</style>
