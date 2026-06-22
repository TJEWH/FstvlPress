<template>
  <div class="tf-dropdown" ref="rootRef">
    <div class="tf-label">{{ label }}</div>
    <button
      type="button"
      class="tf-trigger"
      :class="{ 'tf-trigger--open': open }"
      @click="toggle"
    >
      <span class="tf-trigger-text">{{ selectedLabel }}</span>
      <font-awesome-icon :icon="faChevronDown" class="tf-arrow" :class="{ 'tf-arrow--open': open }" aria-hidden="true" />
    </button>
    <div v-if="open" class="tf-menu">
      <button
        type="button"
        class="tf-option"
        :class="{ 'tf-option--active': modelValue === '' }"
        @click="select('')"
      >All</button>
      <button
        v-for="opt in options"
        :key="opt"
        type="button"
        class="tf-option"
        :class="{ 'tf-option--active': modelValue === opt }"
        @click="select(opt)"
      >{{ opt }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { faChevronDown } from "@fortawesome/free-solid-svg-icons";

const props = defineProps({
  modelValue: { type: String, default: "" },
  options: { type: Array, default: () => [] },
  label: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue"]);

const open = ref(false);
const rootRef = ref(null);

const selectedLabel = computed(() =>
  props.modelValue ? props.modelValue : "All"
);

function toggle() {
  open.value = !open.value;
}

function select(value) {
  emit("update:modelValue", value);
  open.value = false;
}

function onClickOutside(e) {
  if (rootRef.value && !rootRef.value.contains(e.target)) {
    open.value = false;
  }
}

onMounted(() => document.addEventListener("pointerdown", onClickOutside, true));
onBeforeUnmount(() => document.removeEventListener("pointerdown", onClickOutside, true));
</script>

<style scoped>
.tf-dropdown {
  position: relative;
  display: grid;
  gap: 6px;
  min-width: 200px;
}

.tf-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--tile-title-base-color, #0f172a);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.tf-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0 14px;
  min-height: var(--tile-filter-height, 50px);
  border-radius: 0px;
  border: none;
  background: var(--tile-title-base-color, #0f172a);
  color: var(--tile-title-color, #fff);
  font-weight: 600;
  cursor: pointer;
  outline: none;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
  width: 100%;
  text-align: left;
}

.tf-trigger:focus-visible {
  border-color: rgba(255, 255, 255, 0.75);
  box-shadow: 0 0 0 2px rgba(15, 23, 42, 0.28);
}

.tf-trigger-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tf-arrow {
  flex-shrink: 0;
  font-size: 11px;
  transition: transform 0.15s ease;
  opacity: 0.7;
}

.tf-arrow--open {
  transform: rotate(180deg);
}

.tf-menu {
  position: absolute;
  top: calc(100% + 10px);
  left: 0;
  min-width: 100%;
  z-index: 40;
  background: var(--tile-title-base-color, #0f172a);
  border: none;
  border-radius: 0px;
  box-shadow: 0px 20px 30px rgba(255, 255, 255, 0.8);
  overflow: visible;
}

.tf-option {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: var(--tile-filter-item-height, var(--tile-filter-height, 50px));
  padding: 0 14px;
  text-align: left;
  background: transparent;
  border: none;
  color: var(--tile-title-color, #fff);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.tf-option:last-child {
  border-bottom: none;
}

.tf-option:hover {
  background: rgba(255, 255, 255, 0.08);
}

.tf-option--active {
  font-weight: 700;
  background: rgba(255, 255, 255, 0.12);
}
</style>
