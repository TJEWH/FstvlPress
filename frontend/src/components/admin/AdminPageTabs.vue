<template>
  <div class="page-tabs" role="tablist">
    <template v-for="tab in tabs" :key="tab.id">
      <router-link
        v-if="tab.to"
        class="tab-btn"
        :class="{ active: modelValue === tab.id }"
        :to="tab.to"
        role="tab"
        :aria-selected="modelValue === tab.id"
      >
        {{ tab.label }}
      </router-link>
      <button
        v-else
        class="tab-btn"
        :class="{ active: modelValue === tab.id }"
        type="button"
        role="tab"
        :aria-selected="modelValue === tab.id"
        @click="setTab(tab.id)"
      >
        {{ tab.label }}
      </button>
    </template>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  tabs: { type: Array, default: () => [] },
  modelValue: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue"]);

function setTab(id) {
  emit("update:modelValue", id);
}
</script>

<style scoped>
.page-tabs {
  display: inline-flex;
  gap: 6px;
  background: #e2e8f0;
  border-radius: 10px;
  padding: 4px;
  width: 100%;
  overflow-x: auto;
}

.tab-btn {
  border: none;
  background: transparent;
  color: #475569;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  padding: 8px 14px;
  border-radius: 8px;
  cursor: pointer;
  text-decoration: none;
  transition: background 0.15s ease, color 0.15s ease;
  white-space: nowrap;
}

.tab-btn.active {
  background: #fff;
  color: #0f172a;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.12);
}
</style>
