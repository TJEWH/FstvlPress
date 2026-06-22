<template>
  <div class="wrap">
    <div class="slot">
      <slot />
    </div>

    <div v-if="isAdmin" class="admin-toolbar">
      <slot name="admin-actions" />
      <button
        class="edit-bg-btn"
        type="button"
        @click.stop="openLibrary"
        :title="'Edit Background Media'"
      >
        <font-awesome-icon :icon="faImage" class="edit-bg-icon" />
        <span>Background</span>
      </button>
    </div>

    <MediaLibrary
      :is-open="libraryOpen"
      :current-url="modelValue"
      :source-context="sourceContext"
      :allow-clear-selection="true"
      @close="closeLibrary"
      @select="onLibrarySelect"
    />
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { faImage } from "@fortawesome/free-solid-svg-icons";
import MediaLibrary from "./MediaLibrary.vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  isAdmin: { type: Boolean, default: false },
  sourceContext: { type: String, default: "section.unknown.background" },
});

const emit = defineEmits(["update:modelValue", "update:urls"]);

const libraryOpen = ref(false);

watch(() => props.isAdmin, (val) => {
  if (!val) {
    closeLibrary();
  }
});

function openLibrary() {
  libraryOpen.value = true;
}

function closeLibrary() {
  libraryOpen.value = false;
}

function onLibrarySelect(selection) {
  const url = String(selection?.url || "").trim();
  emit("update:modelValue", url);
  emit("update:urls", {
    url,
    responsive_variants: Array.isArray(selection?.responsive_variants) ? selection.responsive_variants : [],
  });
  closeLibrary();
}
</script>

<style scoped>
.wrap { position: relative; overflow: hidden; }
.slot { position: relative; z-index: 1; }

/* Admin toolbar - top-right corner */
.admin-toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 4px;
  opacity: 0;
  transform: translateY(-4px);
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.edit-bg-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.9);
  background-color: transparent;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  backdrop-filter: blur(8px);
}

.edit-bg-btn::before {
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

.edit-bg-icon {
  font-size: 14px;
}

.wrap:hover .admin-toolbar {
  opacity: 1;
  transform: translateY(0);
}

.wrap:hover .edit-bg-btn::before {
  opacity: 1;
  animation: marching-ants 0.4s linear infinite;
}

.edit-bg-btn:hover {
  background: rgba(0, 0, 0, 0.85);
}

@keyframes marching-ants {
  0% {
    background-position: 0 0, 0 100%, 0 0, 100% 0;
  }
  100% {
    background-position: 8px 0, -8px 100%, 0 -8px, 100% 8px;
  }
}
</style>
