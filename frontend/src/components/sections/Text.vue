<template>
  <SectionBase :section-key="effectiveKey" :section-data="section">
    <template #admin-content>
    </template>
  </SectionBase>
</template>

<script setup>
import { computed } from "vue";
import { useStore } from "../../store/store.js";

import SectionBase from "./_BaseSection.vue";

const props = defineProps({
  sectionKey: { type: String, default: 'text' },
  sectionData: { type: Object, default: null }
});

const { state } = useStore();

const effectiveKey = computed(() => props.sectionKey);

const section = computed(() => {
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});
</script>
