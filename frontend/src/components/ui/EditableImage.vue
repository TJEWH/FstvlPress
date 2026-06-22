<template>
  <div
    class="editable"
    :class="{ 'editable--admin': isAdmin }"
    @click="isAdmin && openLibrary()"
  >
    <div class="view">
      <img v-if="modelValue" class="img" :src="modelValue" :alt="alt" decoding="async" />
      <div v-else class="placeholder">No image</div>
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
import MediaLibrary from "./MediaLibrary.vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  isAdmin: { type: Boolean, default: false },
  alt: { type: String, default: "Image" },
  sourceContext: { type: String, default: "section.unknown.image" },
});

const emit = defineEmits(["update:modelValue", "update:urls", "edit-start", "edit-end"]);

const libraryOpen = ref(false);

watch(() => props.isAdmin, (val) => {
  if (!val) {
    closeLibrary();
  }
});

function openLibrary() {
  if (libraryOpen.value) return;
  libraryOpen.value = true;
  emit("edit-start");
}

function closeLibrary() {
  if (!libraryOpen.value) return;
  libraryOpen.value = false;
  emit("edit-end");
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
.editable {
  position: relative;
  border-radius: 14px;
  overflow: visible;
}

.editable--admin {
  cursor: pointer;
}

.editable--admin::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  z-index: 1;
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

.view {
  background: transparent;
  border-radius: inherit;
  overflow: hidden;
}

.img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.placeholder {
  display: grid;
  place-items: center;
  height: 100%;
  min-height: 140px;
  color: var(--muted);
  background: rgba(255, 255, 255, 0.18);
}
</style>
