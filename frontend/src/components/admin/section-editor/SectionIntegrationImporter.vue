<template>
  <details
    v-if="state.canAdminGeneral && integrationContextLoaded && !isIntegrationDisabled"
    class="integration-import-panel"
    :class="{ 'integration-import-panel--template-only': isTemplateOnlyImportPanel }"
    :open="shouldOpenByDefault"
  >
    <summary class="integration-import-title">{{ panelTitle }}</summary>
    <div v-if="!isIntegrationEnabled" class="integration-import-content">
      <div class="integration-import-notice">
        <strong>{{ integrationUnavailableTitle }}</strong>
        <p>{{ integrationUnavailableMessage }}</p>
        <p>
          Change this in the
          <router-link :to="integrationsExposeRoute">Admin Integrations Expose tab</router-link>:
          find this section/template rule, set the import visibility to
          <strong>Enabled</strong> to allow imports on page instances, or <strong>Template only</strong> to keep imports limited to templates,
          then save the connection settings.
        </p>
        <p v-if="isProgramSection">
          Program gigs are added and edited in
          <router-link :to="selectedIntegrationReviewRoute">Integration Review</router-link>
          before they are imported here.
        </p>
      </div>
    </div>
    <div v-else class="integration-import-content">
      <div class="mapping-row">
        <div class="field-group">
          <label class="field-label">Select Integration</label>
          <select v-model="selectedIntegration" class="integration-select">
            <option value="">-- Select an integration --</option>
            <option v-for="integration in availableIntegrations" :key="integration.id" :value="integration.id">
              {{ integration.name }} ({{ integration.return_type || "unknown" }}, {{ integration.data_count || 0 }} items)
            </option>
          </select>
        </div>
        <div class="field-group field-group-actions">
          <button class="btn-secondary" type="button" @click="loadAvailableIntegrations" :disabled="loadingIntegrations">
            {{ loadingIntegrations ? "Loading..." : "Refresh" }}
          </button>
        </div>
      </div>

      <div class="integration-preview">
        <div v-if="integrationPreview" class="preview-live">
          <div class="preview-header">
            <strong>Preview (first item of {{ integrationPreview.total_items || 0 }})</strong>
          </div>
          <div v-if="selectedIntegration && loadingMediaImportability" class="preview-keys">
            Checking media URLs...
          </div>
          <div v-else-if="selectedIntegration && hasMediaUrls" class="preview-keys">
            <strong>Importable Media URLs:</strong> {{ mediaUrlCount }}
          </div>
          <div v-else-if="selectedIntegration" class="preview-keys">
            <strong>Importable Media URLs:</strong> none found
          </div>
          <pre class="preview-json">{{ JSON.stringify(integrationPreview.preview_item, null, 2) }}</pre>
        </div>
        <div v-else class="empty-state compact">
          Select an integration to load preview data.
        </div>
      </div>

      <div v-if="showListMappingPanel" class="mapping-panel">
        <div class="mapping-panel-header">
          <h4>List Item Mapping</h4>
        </div>
        <div v-if="listMappingGroups.length === 0" class="empty-state compact">
          This section has no list fields available for mapping.
        </div>
        <IntegrationFieldMappingGroups
          v-else
          :groups="listMappingGroups"
          :source-options="listItemSourceOptions"
          source-column-label="Source (import)"
          target-column-label="Target (List Item)"
          :target-options-for-group="listMappingTargetOptionsForGroup"
          @add-mapping="handleListMappingAdd"
          @remove-mapping="handleListMappingRemove"
        />
        <div
          v-if="canEditListTargetVisibility && listTargetVisibilityGroups.length > 0"
          class="mapping-panel nested"
        >
          <div class="mapping-panel-header">
            <h5>List Target Field Visibility</h5>
          </div>
          <p class="visibility-hint">
            Define which list target fields should appear in mapping dropdowns for this section template.
          </p>
          <div class="list-target-visibility-groups">
            <div v-for="group in listTargetVisibilityGroups" :key="`visibility-${group.path}`" class="collection-card">
              <div class="collection-group-header">
                <h5>{{ group.label }}</h5>
              </div>
              <div class="list-target-visibility-grid">
                <label
                  v-for="option in group.options"
                  :key="`visibility-${group.path}-${option.path}`"
                  class="visibility-option"
                >
                  <input
                    type="checkbox"
                    :checked="!option.hidden"
                    @change="handleListTargetVisibilityChange(group.path, option.path, $event.target.checked)"
                  />
                  <span>{{ option.label }}</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>

      <template v-if="showObjectMappingPanel">
        <div class="mapping-panel">
          <div class="mapping-panel-header">
            <h4>Object Field Mapping</h4>
            <button class="btn-secondary btn-sm" type="button" @click="addScalarMapping">Add Field</button>
          </div>
          <div v-if="scalarMappings.length === 0" class="empty-state compact">No scalar mappings yet.</div>
          <div v-for="(mapping, index) in scalarMappings" :key="`scalar-${index}`" class="mapping-row mapping-row-align-end">
            <div class="field-group">
              <label class="field-label">Integration Field</label>
              <select v-model="mapping.source_path" class="mapping-select">
                <option value="">-- Select source path --</option>
                <option v-for="option in integrationLeafOptions" :key="`scalar-src-${index}-${option.path}`" :value="option.path">
                  {{ option.label }}
                </option>
              </select>
            </div>
            <div class="field-group">
              <label class="field-label">Section Field</label>
              <select v-model="mapping.target_path" class="mapping-select">
                <option value="">-- Select target path --</option>
                <option v-for="option in scalarTargetOptions" :key="`scalar-target-${index}-${option.path}`" :value="option.path">
                  {{ option.label }}
                </option>
              </select>
            </div>
            <button class="btn-secondary btn-sm" type="button" @click="removeScalarMapping(index)">Remove</button>
          </div>
        </div>
      </template>

      <div class="form-actions">
        <button class="btn" type="button" @click="importFromIntegration" :disabled="!selectedIntegration || importing">
          {{ importing ? "Importing..." : "Import Mapped Data" }}
        </button>
        <router-link
          v-if="isProgramSection && selectedIntegration"
          class="btn-secondary integration-review-link"
          :to="selectedIntegrationReviewRoute"
        >
          Open Integration Review
        </router-link>
        <button v-if="showClearButton" class="btn-secondary" type="button" @click="clearImporter" :disabled="importing">
          Clear
        </button>
        <span v-if="importStatus" class="import-status" :class="importStatus.type">
          {{ importStatus.message }}
        </span>
      </div>
    </div>
  </details>
</template>

<script setup>
import { computed, toRef } from "vue";

import IntegrationFieldMappingGroups from "../mapping/IntegrationFieldMappingGroups.vue";
import { useStore } from "../../../store/store.js";
import { useSectionIntegrationImporter } from "../../../composables/useSectionIntegrationImporter.js";

const props = defineProps({
  sectionKey: { type: String, required: true },
  sectionData: { type: Object, default: null },
  sectionType: { type: String, default: "" },
  panelTitle: { type: String, default: "Import from Integration" },
  forcedMode: { type: String, default: "" },
  fixedCollectionPaths: { type: Array, default: () => [] },
  mappingStorageKey: { type: String, default: "sectionIntegrationMapping" },
  applyContentPatch: { type: Function, default: null },
  persistMappingPatch: { type: Function, default: null },
  showClearButton: { type: Boolean, default: true },
});

const { state } = useStore();

const sectionTypeRef = computed(() =>
  String(props.sectionType || props.sectionData?.sectionType || "text")
);
const panelTitle = computed(() => String(props.panelTitle || "Import from Integration").trim() || "Import from Integration");

const {
  availableIntegrations,
  selectedIntegration,
  integrationContext,
  integrationContextLoaded,
  isIntegrationEnabled,
  isListMode,
  isObjectMode,
  hasMediaUrls,
  mediaUrlCount,
  integrationPreview,
  loadingIntegrations,
  loadingMediaImportability,
  importing,
  importStatus,
  scalarMappings,
  listMappingGroups,
  listTargetVisibilityGroups,
  canEditListTargetVisibility,
  scalarTargetOptions,
  integrationLeafOptions,
  listItemSourceOptions,
  loadAvailableIntegrations,
  importFromIntegration,
  clearImporter,
  addScalarMapping,
  removeScalarMapping,
  addListMappingRow,
  removeListMappingRow,
  setListTargetPathHidden,
} = useSectionIntegrationImporter({
  sectionKey: toRef(props, "sectionKey"),
  sectionData: toRef(props, "sectionData"),
  sectionType: sectionTypeRef,
  forcedMode: toRef(props, "forcedMode"),
  fixedCollectionPaths: toRef(props, "fixedCollectionPaths"),
  mappingStorageKey: toRef(props, "mappingStorageKey"),
  applyContentPatch: toRef(props, "applyContentPatch"),
  persistMappingPatch: toRef(props, "persistMappingPatch"),
});

const isProgramSection = computed(() =>
  String(sectionTypeRef.value || "").trim().toLowerCase() === "program"
);
const selectedIntegrationReviewRoute = computed(() => {
  const integrationId = String(selectedIntegration.value || integrationContext.value?.integration_id || "").trim();
  return integrationId
    ? { path: "/admin/integrations/review", query: { integrationId } }
    : { path: "/admin/integrations/review" };
});
const integrationsExposeRoute = computed(() => ({ name: "admin-integrations-expose" }));
const showListMappingPanel = computed(() => isListMode.value);
const showObjectMappingPanel = computed(() => isObjectMode.value);
const isBusy = computed(() =>
  Boolean(importing.value || loadingIntegrations.value || loadingMediaImportability.value)
);
const integrationVisibility = computed(() => {
  const value = String(integrationContext.value?.integration_visibility || "").trim().toLowerCase();
  return ["disabled", "template_only", "enabled"].includes(value) ? value : "enabled";
});
const isIntegrationDisabled = computed(() => integrationVisibility.value === "disabled");
const isTemplateOnlyImportPanel = computed(() => integrationVisibility.value === "template_only");
const shouldOpenByDefault = computed(() =>
  !isIntegrationEnabled.value && !isTemplateOnlyImportPanel.value
);
const integrationUnavailableTitle = computed(() =>
  isProgramSection.value
    ? "Program import requires integration review"
    : integrationVisibility.value === "disabled"
    ? "Integration import is deactivated"
    : "Integration import is template-only"
);
const integrationUnavailableMessage = computed(() => {
  if (isProgramSection.value) {
    return "Program gigs are owned by the selected integration. Enable the Program template for integration import, then edit or add gigs in integration review and import the reviewed list here.";
  }
  if (integrationVisibility.value === "disabled") {
    return "This section is connected to an integration rule where importing is disabled, so mapped data cannot be imported here.";
  }
  if (integrationVisibility.value === "template_only") {
    return "This section can only import integration data while editing its template. Page instances can use inherited mappings, but cannot run the import directly.";
  }
  return "Integration import is not available for this section with the current connection settings.";
});

function handleListTargetVisibilityChange(collectionPath, targetPath, visible) {
  setListTargetPathHidden(collectionPath, targetPath, !visible);
}

function listMappingTargetOptionsForGroup(group) {
  return Array.isArray(group?.targetOptions) ? group.targetOptions : [];
}

function handleListMappingAdd(payload) {
  addListMappingRow(payload?.groupPath, {
    source_path: payload?.source_path,
    target_path: payload?.target_path,
  });
}

function handleListMappingRemove(payload) {
  removeListMappingRow(payload?.groupPath, Number(payload?.index));
}

defineExpose({
  clearImporter,
  isBusy,
});
</script>

<style scoped>
.integration-import-panel {
  margin-bottom: 16px;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  background: #f8fafc;
  overflow: hidden;
}

.integration-import-panel--template-only {
  border-color: #e2e8f0;
  background: #f8fafc;
}

.integration-import-title {
  cursor: pointer;
  padding: 12px 14px;
  font-weight: 600;
  color: #1e293b;
  list-style: none;
}

.integration-import-panel--template-only .integration-import-title {
  color: #64748b;
  font-weight: 500;
}

.integration-import-title::-webkit-details-marker {
  display: none;
}

.integration-import-title::before {
  content: "▸";
  margin-right: 8px;
  color: #2563eb;
}

.integration-import-panel--template-only .integration-import-title::before {
  color: #94a3b8;
}

.integration-import-panel[open] .integration-import-title::before {
  content: "▾";
}

.integration-import-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 14px 14px;
}

.integration-import-notice {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border: 1px solid #fbbf24;
  border-radius: 10px;
  background: #fffbeb;
  color: #78350f;
  padding: 12px;
  font-size: 13px;
  line-height: 1.45;
}

.integration-import-panel--template-only .integration-import-notice {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #475569;
}

.integration-import-notice p {
  margin: 0;
}

.integration-import-notice a {
  color: #92400e;
  font-weight: 700;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.integration-import-panel--template-only .integration-import-notice a {
  color: #475569;
}

.mapping-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr)) auto;
  gap: 10px;
}

.mapping-row-align-end {
  align-items: end;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-group-actions {
  justify-content: end;
  align-items: end;
}

.field-label {
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
}

.integration-select,
.mapping-select {
  min-height: 36px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  padding: 8px 10px;
  background: #ffffff;
}

.integration-preview {
  border: 1px solid #dbeafe;
  background: #ffffff;
  border-radius: 10px;
  padding: 10px;
}

.integration-preview:has(.empty-state) {
  display: none;
}

.preview-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.preview-header {
  margin-bottom: 8px;
  color: #1e293b;
  font-size: 13px;
}

.preview-keys {
  margin-bottom: 8px;
  font-size: 12px;
  color: #334155;
}

.preview-json {
  margin: 0;
  max-height: 220px;
  overflow: auto;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  font-size: 12px;
  overflow-x: hidden;
  overflow-y: auto;
}

.mapping-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  border: 1px solid #dbeafe;
  border-radius: 10px;
  background: #ffffff;
  padding: 10px;
}

.mapping-panel.nested {
  border-style: dashed;
  background: #f8fafc;
}

.mapping-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.mapping-panel-header h4,
.mapping-panel-header h5 {
  margin: 0;
  font-size: 13px;
  color: #1e293b;
}

.collection-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 10px;
}

.collection-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.collection-group-header h5 {
  margin: 0;
  font-size: 13px;
  color: #1e293b;
}

.visibility-hint {
  margin: 0;
  font-size: 12px;
  color: #334155;
}

.list-target-visibility-groups {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.list-target-visibility-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px;
}

.visibility-option {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #1e293b;
}

.visibility-option input[type="checkbox"] {
  width: 14px;
  height: 14px;
}

.form-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.compare-table {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.compare-head,
.compare-row {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) minmax(120px, 1fr) minmax(120px, 1fr);
  gap: 8px;
  align-items: start;
}

.compare-head {
  font-size: 11px;
  font-weight: 700;
  color: #334155;
  text-transform: uppercase;
}

.compare-row {
  padding: 6px 8px;
  border-radius: 8px;
  background: #f8fafc;
}

.compare-row.changed {
  background: #fff7ed;
}

.compare-row code {
  font-size: 11px;
  color: #0f172a;
  white-space: pre-wrap;
  word-break: break-word;
}

.import-status {
  font-size: 12px;
  font-weight: 600;
}

.import-status.success {
  color: #166534;
}

.import-status.error {
  color: #b91c1c;
}

@media (max-width: 900px) {
  .mapping-row {
    grid-template-columns: 1fr;
  }
}
</style>
