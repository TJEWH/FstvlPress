<template>
  <div class="color-link-picker" :style="triggerStyle">
    <button
      ref="triggerRef"
      class="color-link-picker-btn"
      :class="{ linked: !!modelValue }"
      type="button"
      :title="buttonTitle"
      :disabled="disabled"
      @click.stop="toggleMenu"
    >
      <svg :width="iconSize" :height="iconSize" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
      </svg>
    </button>
    <Teleport to="body">
      <div v-if="showMenu" ref="menuRef" class="color-link-picker-menu" :style="menuStyle" @click.stop>
        <button
          v-for="option in menuOptions"
          :key="option.key"
          class="color-link-picker-item"
          :class="{ active: isOptionActive(option), 'reset-option': option.isReset }"
          @click="emitLink(option.key)"
        >
          <span
            v-if="!option.isReset"
            class="color-link-picker-dot"
            :class="option.dotClass"
            :style="option.dotStyle"
          ></span>
          {{ option.label }}
        </button>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  modelValue: { type: String, default: null },
  options: { type: Array, default: () => [] },
  title: { type: String, default: "Link to base color" },
  disabled: { type: Boolean, default: false },
  buttonSize: { type: Number, default: 22 },
  menuMinWidth: { type: Number, default: 180 },
  showResetOption: { type: Boolean, default: true },
});

const emit = defineEmits(["link"]);

const showMenu = ref(false);
const triggerRef = ref(null);
const menuRef = ref(null);
const menuStyle = ref({});
const COLOR_LINK_MENU_Z_INDEX = "2147483646";
const RESET_OPTION_KEY = "__reset__";

const iconSize = computed(() => (props.buttonSize >= 24 ? 14 : 12));
const triggerStyle = computed(() => ({ "--color-link-picker-btn-size": `${props.buttonSize}px` }));
const menuOptions = computed(() => {
  const options = [...props.options];
  if (props.showResetOption) {
    options.unshift({ key: RESET_OPTION_KEY, label: "Reset", isReset: true });
  }
  return options;
});

const buttonTitle = computed(() => {
  if (!props.modelValue) return props.title;
  const opt = props.options.find((item) => item.key === props.modelValue);
  return `Linked to ${opt?.label || props.modelValue}`;
});

function closeMenu() {
  showMenu.value = false;
}

function updateMenuPosition() {
  if (!showMenu.value || !triggerRef.value || !menuRef.value) return;
  const rect = triggerRef.value.getBoundingClientRect();
  const viewportW = window.innerWidth;
  const viewportH = window.innerHeight;
  const menuW = Math.max(props.menuMinWidth, menuRef.value.offsetWidth || props.menuMinWidth);
  const menuH = menuRef.value.offsetHeight || menuOptions.value.length * 36 + 8;
  const gap = 6;

  const spaceRight = viewportW - rect.right - 8;
  const spaceLeft = rect.left - 8;
  const openToRight = spaceRight >= menuW + gap || spaceRight >= spaceLeft;
  const left = openToRight
    ? Math.min(viewportW - menuW - 8, rect.right + gap)
    : Math.max(8, rect.left - menuW - gap);

  const centeredTop = rect.top + (rect.height - menuH) / 2;
  const top = Math.max(8, Math.min(viewportH - menuH - 8, centeredTop));

  menuStyle.value = {
    position: "fixed",
    left: `${left}px`,
    top: `${top}px`,
    zIndex: COLOR_LINK_MENU_Z_INDEX,
    minWidth: `${props.menuMinWidth}px`,
    visibility: "visible",
  };
}

function waitForPaint() {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

async function openMenu() {
  if (props.disabled) return;
  menuStyle.value = {
    position: "fixed",
    left: "-9999px",
    top: "-9999px",
    zIndex: COLOR_LINK_MENU_Z_INDEX,
    minWidth: `${props.menuMinWidth}px`,
    visibility: "hidden",
  };
  showMenu.value = true;
  await nextTick();
  await waitForPaint();
  updateMenuPosition();
}

function toggleMenu() {
  if (showMenu.value) {
    closeMenu();
    return;
  }
  openMenu();
}

function emitLink(key) {
  emit("link", key === RESET_OPTION_KEY ? null : key);
  closeMenu();
}

function isOptionActive(option) {
  if (option?.isReset) return !props.modelValue;
  return props.modelValue === option?.key;
}

function onDocumentClick(event) {
  if (!showMenu.value) return;
  const target = event.target;
  if (triggerRef.value?.contains(target) || menuRef.value?.contains(target)) return;
  closeMenu();
}

function onWindowChange() {
  if (!showMenu.value) return;
  updateMenuPosition();
}

function onEscape(event) {
  if (event.key === "Escape") closeMenu();
}

watch(
  () => [menuOptions.value, props.modelValue],
  async () => {
    if (!showMenu.value) return;
    await nextTick();
    updateMenuPosition();
  },
  { deep: true }
);

onMounted(() => {
  document.addEventListener("click", onDocumentClick, true);
  document.addEventListener("keydown", onEscape);
  window.addEventListener("resize", onWindowChange);
  window.addEventListener("scroll", onWindowChange, true);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", onDocumentClick, true);
  document.removeEventListener("keydown", onEscape);
  window.removeEventListener("resize", onWindowChange);
  window.removeEventListener("scroll", onWindowChange, true);
});
</script>

<style scoped>
.color-link-picker {
  display: inline-flex;
}

.color-link-picker-btn {
  width: var(--color-link-picker-btn-size);
  height: var(--color-link-picker-btn-size);
  display: inline-grid;
  place-items: center;
  border-radius: 5px;
  border: 1px solid var(--border, #e2e8f0);
  background: #fff;
  cursor: pointer;
  color: var(--muted, #94a3b8);
  flex-shrink: 0;
  transition: all 0.15s ease;
}
.color-link-picker-btn:hover {
  background: #eef2ff;
  border-color: #c7d2fe;
  color: #4f46e5;
}
.color-link-picker-btn.linked {
  background: #eef2ff;
  border-color: #a5b4fc;
  color: #4f46e5;
}
.color-link-picker-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.color-link-picker-menu {
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.14);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  max-height: 60vh;
  overflow-y: auto;
  padding: 4px 0;
}

.color-link-picker-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  color: #0f172a;
  transition: background 0.1s;
}
.color-link-picker-item:hover {
  background: #f1f5f9;
}
.color-link-picker-item.active {
  background: #eef2ff;
  font-weight: 600;
}

.color-link-picker-item.reset-option {
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 2px;
}

.color-link-picker-dot {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  flex-shrink: 0;
}
</style>
