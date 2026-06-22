<template>
  <Transition name="autosave-toast-fade">
    <div
      v-if="message"
      class="autosave-toast"
      :class="`autosave-toast--${normalizedTone}`"
      :role="normalizedTone === 'error' ? 'alert' : 'status'"
      aria-live="polite"
    >
      <span class="autosave-toast__dot" aria-hidden="true"></span>
      <span class="autosave-toast__message">{{ message }}</span>
    </div>
  </Transition>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  message: { type: String, default: "" },
  tone: { type: String, default: "idle" },
});

const normalizedTone = computed(() => {
  const tone = String(props.tone || "idle").trim();
  return ["queued", "saving", "saved", "error"].includes(tone) ? tone : "idle";
});
</script>

<style scoped>
.autosave-toast {
  position: fixed;
  top: calc(env(safe-area-inset-top, 0px) + var(--autosave-toast-top-offset, 72px));
  right: calc(env(safe-area-inset-right, 0px) + 16px);
  z-index: 10000;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: min(360px, calc(100vw - 32px));
  padding: 9px 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  color: #1d4ed8;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.18);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.3;
  pointer-events: none;
}

.autosave-toast--saved {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #15803d;
}

.autosave-toast--error {
  border-color: #fecaca;
  background: #fef2f2;
  color: #dc2626;
}

.autosave-toast__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: currentColor;
  flex: 0 0 auto;
}

.autosave-toast__message {
  min-width: 0;
  overflow-wrap: anywhere;
}

.autosave-toast-fade-enter-active,
.autosave-toast-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.autosave-toast-fade-enter-from,
.autosave-toast-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
