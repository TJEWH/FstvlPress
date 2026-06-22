<template>
  <SectionAdminTabs
    :visible="visible"
    :active-tab="activeTab"
    :force-aux-tabs="true"
    :simple-design-body="true"
    :show-section-generic="false"
    :show-design="showDesign"
    :show-content="true"
    :show-history="showHistory"
    :show-template="showTemplate"
    :show-notes="showNotes"
    :design-label="designLabel"
    :content-label="contentLabel"
    :history-label="historyLabel"
    :template-label="templateLabel"
    :notes-label="notesLabel"
    :editor-label="editorLabel"
    :autosave-message="autosaveMessage"
    :autosave-tone="autosaveTone"
    @update:activeTab="(tab) => emit('update:activeTab', tab)"
    @tab-change="(tab) => emit('tab-change', tab)"
  >
    <template #design><slot name="design" /></template>
    <template #content><slot name="content" /></template>
    <template #history><slot name="history" /></template>
    <template #template><slot name="template" /></template>
    <template #notes><slot name="notes" /></template>
  </SectionAdminTabs>
</template>

<script setup>
import SectionAdminTabs from "./SectionAdminTabs.vue";

defineProps({
  visible: { type: Boolean, default: true },
  activeTab: { type: String, default: "" },
  showDesign: { type: Boolean, default: true },
  showHistory: { type: Boolean, default: true },
  showTemplate: { type: Boolean, default: false },
  showNotes: { type: Boolean, default: true },
  designLabel: { type: String, default: "Design" },
  contentLabel: { type: String, default: "Content" },
  historyLabel: { type: String, default: "History" },
  templateLabel: { type: String, default: "Template" },
  notesLabel: { type: String, default: "Notes" },
  editorLabel: { type: String, default: "Header" },
  autosaveMessage: { type: String, default: "" },
  autosaveTone: { type: String, default: "idle" },
});

const emit = defineEmits(["update:activeTab", "tab-change"]);
</script>
