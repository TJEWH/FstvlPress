<template>
  <div class="panel-position-control">
    <button
      type="button"
      class="panel-position-trigger"
      :title="`Move panel: ${currentPositionLabel}`"
      @click.stop="openPicker"
    >
      <span class="panel-position-trigger-icon" aria-hidden="true">
        <span class="panel-position-trigger-frame"></span>
        <span class="panel-position-trigger-dot" :class="`is-${normalizedValue}`"></span>
      </span>
      <span class="panel-position-trigger-text">{{ currentPositionLabel }}</span>
    </button>

    <Teleport to="body">
      <div
        v-if="showPicker"
        class="panel-position-overlay"
        :aria-label="ariaLabel"
        @click.self="closePicker"
      >
        <button
          v-for="option in PANEL_POSITION_OPTIONS"
          :key="`panel_position_${option.value}`"
          type="button"
          class="panel-position-zone"
          :class="[`panel-position-zone--${option.value}`, { active: normalizedValue === option.value }]"
          :aria-label="`Move panel to ${option.label}`"
          @click="choosePosition(option.value)"
        >
          <span class="panel-position-zone-label">{{ option.label }}</span>
        </button>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import {
  PANEL_POSITION_OPTIONS,
  normalizePanelPosition,
} from "../../../composables/usePanelPosition.js";

const props = defineProps({
  modelValue: {
    type: String,
    default: "bottom-left",
  },
  ariaLabel: {
    type: String,
    default: "Choose panel position",
  },
  fallback: {
    type: String,
    default: "bottom-left",
  },
});

const emit = defineEmits(["update:modelValue"]);

const showPicker = ref(false);
const normalizedValue = computed(() => normalizePanelPosition(props.modelValue, props.fallback));
const currentPositionLabel = computed(() => (
  PANEL_POSITION_OPTIONS.find((option) => option.value === normalizedValue.value)?.label || "Panel Corner"
));

function openPicker() {
  showPicker.value = true;
}

function closePicker() {
  showPicker.value = false;
}

function choosePosition(value) {
  emit("update:modelValue", normalizePanelPosition(value, props.fallback));
  closePicker();
}
</script>

<style scoped>
.panel-position-control {
  display: flex;
  width: 100%;
}

.panel-position-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
  color: var(--text, #0f172a);
  font-size: 11px;
  font-weight: 700;
  padding: 7px 10px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.panel-position-trigger:hover {
  color: var(--text, #0f172a);
  background: var(--surface-2, #f3f4f6);
}

.panel-position-trigger-icon {
  position: relative;
  width: 19px;
  height: 19px;
  flex: 0 0 auto;
}

.panel-position-trigger-frame {
  position: absolute;
  inset: 2px;
  border: 1px solid var(--border, #cbd5e1);
  border-radius: 5px;
}

.panel-position-trigger-dot {
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--accent, #4f46e5);
  box-shadow: 0 0 0 2px #fff;
}

.panel-position-trigger-dot.is-top-left {
  top: 0;
  left: 0;
}

.panel-position-trigger-dot.is-top-right {
  top: 0;
  right: 0;
}

.panel-position-trigger-dot.is-bottom-left {
  bottom: 0;
  left: 0;
}

.panel-position-trigger-dot.is-bottom-right {
  right: 0;
  bottom: 0;
}

.panel-position-trigger-text {
  min-width: 0;
}

.panel-position-overlay {
  position: fixed;
  inset: 0;
  z-index: 5000;
  background: rgba(15, 23, 42, 0.22);
  backdrop-filter: blur(1px);
}

.panel-position-zone {
  position: fixed;
  width: min(360px, calc(100vw - 28px));
  height: min(220px, calc(50vh - 24px));
  border: 2px solid rgba(79, 70, 229, 0.58);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.88);
  color: var(--text, #0f172a);
  box-shadow: 0 16px 44px rgba(15, 23, 42, 0.18);
  cursor: pointer;
  transition: transform 0.15s ease, border-color 0.15s ease, background 0.15s ease;
}

.panel-position-zone:hover {
  transform: translateY(-1px);
  border-color: var(--accent, #4f46e5);
  background: rgba(248, 250, 252, 0.96);
}

.panel-position-zone.active {
  border-color: var(--accent, #4f46e5);
  background: rgba(238, 242, 255, 0.95);
}

.panel-position-zone--top-left {
  top: 5px;
  left: 5px;
}

.panel-position-zone--top-right {
  top: 5px;
  right: 5px;
}

.panel-position-zone--bottom-left {
  bottom: 5px;
  left: 5px;
}

.panel-position-zone--bottom-right {
  right: 5px;
  bottom: 5px;
}

.panel-position-zone-label {
  position: absolute;
  inset: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed rgba(79, 70, 229, 0.35);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 800;
}

@media (max-width: 760px) {
  .panel-position-zone {
    width: calc(50vw - 12px);
    height: min(190px, calc(50vh - 18px));
  }

  .panel-position-zone-label {
    inset: 6px;
    text-align: center;
  }
}
</style>
