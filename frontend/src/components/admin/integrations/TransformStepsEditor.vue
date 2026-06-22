<template>
  <div class="transform-editor">
    <p class="card-hint integration-case-hint">
      {{ pathRuleHint }} {{ targetRuleHint }}
    </p>

    <div v-if="steps.length === 0" class="empty-state compact">
      No transform steps configured.
    </div>
    <draggable
      v-else
      v-model="model"
      item-key="ui_id"
      class="transform-step-list"
      handle=".drag-handle"
      ghost-class="transform-step--dragging"
      chosen-class="transform-step--dragging"
      :animation="150"
    >
      <template #item="{ element: step, index: stepIndex }">
      <div class="transform-step">
        <div class="transform-step-head">
          <div class="transform-step-title">
            <button
              type="button"
              class="drag-handle"
              title="Drag step"
              aria-label="Drag step"
            >
              <font-awesome-icon :icon="faGripVertical" />
            </button>
            <button
              type="button"
              class="transform-step-collapse"
              :title="step.collapsed ? 'Expand step' : 'Collapse step'"
              :aria-label="step.collapsed ? 'Expand step' : 'Collapse step'"
              @click="step.collapsed = !step.collapsed"
            >
              <font-awesome-icon :icon="step.collapsed ? faChevronRight : faChevronDown" />
            </button>
            <span class="step-index">Step {{ stepIndex + 1 }} - {{ formatTransformOperationTitle(step.op) }}</span>
          </div>
          <div class="transform-step-actions">
            <label class="checkbox-item">
              <input v-model="step.enabled" type="checkbox" />
              <span>Enabled</span>
            </label>
            <button
              type="button"
              class="btn-outline btn-sm danger"
              @click="removeTransformStep(stepIndex)"
            >
              Remove
            </button>
          </div>
        </div>

        <div v-show="!step.collapsed" class="transform-step-body">
          <div class="form-group">
            <label>Operation</label>
            <select v-model="step.op" @change="onTransformOperationChange(step)">
              <option value="keep_keys">keep_keys</option>
              <option value="remove_keys">remove_keys</option>
              <option value="ensure_keys">ensure_keys</option>
              <option value="group_by">group_by</option>
              <option value="replace_nested_item">replace_nested_item</option>
              <option value="filter_by_allowed_values">filter_by_allowed_values</option>
              <option value="filter_by_disallowed_values">filter_by_disallowed_values</option>
              <option value="split_values_to_list">split_values_to_list</option>
              <option value="rename_keys">rename_keys</option>
            </select>
            <span class="form-hint">{{ getTransformOperationDescription(step.op) }}</span>
          </div>

          <template v-if="step.op === 'keep_keys' || step.op === 'remove_keys' || step.op === 'ensure_keys'">
            <div class="form-group">
              <label>
                {{
                  step.op === "remove_keys"
                    ? "Keys to Remove"
                    : (step.op === "ensure_keys" ? "Keys to Ensure" : "Keys to Keep")
                }}
              </label>
              <input v-model="step.keys_input" type="text" placeholder="e.g., id,name,genre.en" />
            </div>
          </template>

          <template v-else-if="step.op === 'filter_by_allowed_values' || step.op === 'filter_by_disallowed_values'">
            <div class="form-group">
              <label>Filter Key Path</label>
              <input
                v-model="step.allowed_key_path"
                type="text"
                placeholder="e.g., status or meta.category"
              />
            </div>
            <div class="form-group">
              <label>
                {{
                  step.op === "filter_by_allowed_values"
                    ? "Allowed Values (comma-separated)"
                    : "Disallowed Values (comma-separated)"
                }}
              </label>
              <input
                v-model="step.allowed_values_input"
                type="text"
                :placeholder="
                  step.op === 'filter_by_allowed_values'
                    ? 'e.g., active,published'
                    : 'e.g., inactive,archived (optional)'
                "
              />
              <span class="form-hint">
                {{
                  step.op === "filter_by_allowed_values"
                    ? "Items are kept only when this key path value matches one of the listed values."
                    : "Items are removed when this key path value matches one of the listed values. Empty/missing values are always removed, even if this list is blank."
                }}
              </span>
            </div>
          </template>

          <template v-else-if="step.op === 'replace_nested_item'">
            <div class="form-group">
              <label>Shared Route (all mappings in this step)</label>
              <input
                v-model="step.static_route"
                type="text"
                placeholder="e.g., add_fields.questions or name"
              />
              <span class="form-hint">
                Shared nested path used by all mappings in this step.
              </span>
            </div>
            <div
              v-if="!Array.isArray(step.replace_mappings) || step.replace_mappings.length === 0"
              class="empty-state compact"
            >
              No replace mappings configured.
            </div>
            <div
              v-for="(mapping, mappingIndex) in (step.replace_mappings || [])"
              :key="mapping.ui_id || `replace-${step.ui_id}-${mappingIndex}`"
              class="mapping-item-block"
            >
              <div class="form-row">
                <div class="form-group">
                  <label>Key Path Specification (optional)</label>
                  <input
                    v-model="mapping.item_key_path"
                    type="text"
                    placeholder="e.g., question or de"
                  />
                </div>
                <div class="form-group">
                  <label>Target Key Path (optional)</label>
                  <input
                    v-model="mapping.target_key"
                    type="text"
                    placeholder="e.g., genre"
                  />
                </div>
                <div class="form-group">
                  <label>Match Value</label>
                  <input
                    v-model="mapping.match_value_input"
                    type="text"
                    placeholder="e.g., 87"
                  />
                </div>
                <div class="form-group">
                  <label>Source Value Path (optional)</label>
                  <input
                    v-model="mapping.source_value_path"
                    type="text"
                    placeholder="e.g., answer"
                  />
                </div>
                <div class="form-group">
                  <label>Renamed Value (optional)</label>
                  <input
                    v-model="mapping.renamed_value"
                    type="text"
                    placeholder="e.g., Techno"
                  />
                </div>
                <div class="form-group form-group-auto-end">
                  <button
                    type="button"
                    class="btn-outline btn-sm danger"
                    @click="removeReplaceNestedMapping(step, mappingIndex)"
                  >
                    Remove
                  </button>
                </div>
              </div>
              <div
                v-if="mappingIndex < (step.replace_mappings || []).length - 1"
                class="mapping-separator"
              ></div>
            </div>
            <div class="form-actions">
              <button type="button" class="btn-outline btn-sm" @click="addReplaceNestedMapping(step)">
                Add Mapping
              </button>
            </div>
            <span class="form-hint">
              Example A: shared route <code>name</code>, key path spec <code>de</code>, target key
              <code>gig_type</code>, match value
              <code>Musiker*innen (Bands &amp; Solokünstler*innen)</code>, renamed value
              <code>Musik</code>.
              Example B: shared route <code>add_fields</code>, key path spec <code>question_id</code>,
              match value <code>87</code>, source value path <code>answer</code>, target key
              <code>genre</code>.
            </span>
          </template>

          <template v-else-if="step.op === 'group_by'">
            <div class="form-group">
              <label>Group Key Path</label>
              <input
                v-model="step.key_path"
                type="text"
                placeholder="e.g., question or meta.external_id"
              />
            </div>
            <div class="form-group">
              <label>Grouped Items Key</label>
              <input
                v-model="step.items_key"
                type="text"
                placeholder="e.g., grouped_documents"
              />
              <span class="form-hint">
                Groups items into a list like: [{ &lt;groupKey&gt;: &lt;value&gt;, &lt;itemsKey&gt;:
                [...] }, ...]. The group key path is removed from each grouped document.
              </span>
            </div>
          </template>

          <template v-else-if="step.op === 'split_values_to_list'">
            <div class="form-group">
              <label>Key</label>
              <input
                v-model="step.split_key"
                type="text"
                placeholder="e.g., tags or meta.categories"
              />
            </div>
            <div class="form-group">
              <label>Separator</label>
              <input
                v-model="step.split_separator"
                type="text"
                placeholder="e.g., , or ;"
              />
              <span class="form-hint">
                Splits each item's string value at the given key by this separator, replacing the value
                with a list of parts.
              </span>
            </div>
          </template>

          <template v-else-if="step.op === 'rename_keys'">
            <div
              v-if="!Array.isArray(step.rename_mappings) || step.rename_mappings.length === 0"
              class="empty-state compact"
            >
              No rename mappings configured.
            </div>
            <div
              v-for="(mapping, mappingIndex) in (step.rename_mappings || [])"
              :key="mapping.ui_id || `rename-${step.ui_id}-${mappingIndex}`"
              class="mapping-item-block"
            >
              <div class="form-row">
                <div class="form-group">
                  <label>Old Key</label>
                  <input
                    v-model="mapping.source_key"
                    type="text"
                    placeholder="e.g., genre.en or meta.title"
                  />
                </div>
                <div class="form-group">
                  <label>New Key</label>
                  <input
                    v-model="mapping.target_key"
                    type="text"
                    placeholder="e.g., title or meta.label"
                  />
                </div>
                <div class="form-group form-group-auto-end">
                  <button
                    type="button"
                    class="btn-outline btn-sm danger"
                    @click="removeRenameKeyMapping(step, mappingIndex)"
                  >
                    Remove
                  </button>
                </div>
              </div>
              <div
                v-if="mappingIndex < (step.rename_mappings || []).length - 1"
                class="mapping-separator"
              ></div>
            </div>
            <div class="form-actions">
              <button type="button" class="btn-outline btn-sm" @click="addRenameKeyMapping(step)">
                Add Mapping
              </button>
            </div>
            <span class="form-hint">
              Moves values from each old key path to its new key path on every item, removing the old
              keys.
            </span>
          </template>
        </div>
      </div>
      </template>
    </draggable>

    <div class="form-actions">
      <button type="button" class="btn-outline btn-sm" @click="addTransformStep">Add Step</button>
    </div>
  </div>
</template>

<script setup>
import { computed, watch } from "vue";
import {
  faChevronDown,
  faChevronRight,
  faGripVertical,
} from "@fortawesome/free-solid-svg-icons";
import draggable from "vuedraggable";

defineProps({
  pathRuleHint: { type: String, default: "" },
  targetRuleHint: { type: String, default: "" },
});

const model = defineModel({ default: () => [] });

let uiSeed = 1;
function makeUiId(prefix = "ui") {
  const id = `${prefix}-${Date.now().toString(36)}-${uiSeed.toString(36)}`;
  uiSeed += 1;
  return id;
}

const steps = computed(() => (Array.isArray(model.value) ? model.value : []));

function createReplaceNestedMapping(mapping = {}) {
  return {
    ui_id: makeUiId("replace-map"),
    item_key_path: String(mapping.item_key_path || "").trim(),
    match_value_input: String(mapping.match_value ?? mapping.match_value_input ?? "").trim(),
    source_value_path: String(mapping.source_value_path || "").trim(),
    renamed_value: String(mapping.renamed_value || "").trim(),
    target_key: String(mapping.target_key || "").trim(),
  };
}

function createRenameKeyMapping(mapping = {}) {
  return {
    ui_id: makeUiId("rename-map"),
    source_key: String(
      mapping.source_key || mapping.old_key || ""
    ).trim(),
    target_key: String(
      mapping.target_key || mapping.new_key || ""
    ).trim(),
  };
}

function createTransformStep(op = "keep_keys") {
  if (op === "keep_keys" || op === "remove_keys" || op === "ensure_keys") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: true,
      keys_input: "",
    };
  }
  if (op === "group_by") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: true,
      key_path: "",
      items_key: "grouped_documents",
    };
  }
  if (op === "replace_nested_item") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: true,
      static_route: "",
      replace_mappings: [createReplaceNestedMapping()],
    };
  }
  if (op === "filter_by_allowed_values" || op === "filter_by_disallowed_values") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: true,
      allowed_key_path: "",
      allowed_values_input: "",
    };
  }
  if (op === "split_values_to_list") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: true,
      split_key: "",
      split_separator: "",
    };
  }
  if (op === "rename_keys") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: true,
      rename_mappings: [createRenameKeyMapping()],
    };
  }
  return createTransformStep("remove_keys");
}

function normalizeTransformStepUi(step) {
  const op = String(step?.op || "keep_keys");
  const normalized = createTransformStep(op);
  normalized.ui_id = String(step?.ui_id || "").trim() || normalized.ui_id;
  normalized.enabled = step?.enabled !== false;
  normalized.collapsed = Boolean(step?.collapsed);

  if (op === "keep_keys" || op === "remove_keys" || op === "ensure_keys") {
    normalized.keys_input = Array.isArray(step?.keys) ? step.keys.join(",") : String(step?.keys_input || "");
    return normalized;
  }
  if (op === "group_by") {
    normalized.key_path = String(step?.key_path || "");
    normalized.items_key = String(step?.items_key || "").trim() || "grouped_documents";
    return normalized;
  }
  if (op === "replace_nested_item") {
    normalized.static_route = String(step?.static_route || "");
    const rawMappings = Array.isArray(step?.mappings)
      ? step.mappings
      : (Array.isArray(step?.replace_mappings) ? step.replace_mappings : []);
    normalized.replace_mappings = rawMappings.length
      ? rawMappings.map((mapping) => createReplaceNestedMapping(mapping))
      : [createReplaceNestedMapping()];
    return normalized;
  }
  if (op === "filter_by_allowed_values" || op === "filter_by_disallowed_values") {
    const keyName = op === "filter_by_allowed_values" ? "allowed_values" : "disallowed_values";
    const rawMap = step?.[keyName] && typeof step[keyName] === "object" && !Array.isArray(step[keyName])
      ? step[keyName]
      : {};
    const [firstEntry] = Object.entries(rawMap);
    const [keyPath, values] = firstEntry || ["", []];
    const normalizedValues = Array.isArray(values) ? values : [values];
    normalized.allowed_key_path = String(keyPath || "").trim();
    normalized.allowed_values_input = normalizedValues
      .map((value) => String(value ?? "").trim())
      .filter(Boolean)
      .join(",");
    return normalized;
  }
  if (op === "split_values_to_list") {
    normalized.split_key = String(step?.key || step?.split_key || "").trim();
    normalized.split_separator = String(step?.separator || step?.split_separator || "");
    return normalized;
  }
  if (op === "rename_keys") {
    const rawMappings = Array.isArray(step?.mappings)
      ? step.mappings
      : (Array.isArray(step?.rename_mappings) ? step.rename_mappings : []);
    normalized.rename_mappings = rawMappings.length
      ? rawMappings.map((mapping) => createRenameKeyMapping(mapping))
      : [createRenameKeyMapping()];
    return normalized;
  }
  return normalized;
}

watch(
  model,
  (nextValue) => {
    if (!Array.isArray(nextValue)) {
      model.value = [];
      return;
    }
    for (let index = 0; index < nextValue.length; index += 1) {
      const step = nextValue[index];
      nextValue[index] = normalizeTransformStepUi(step);
    }
  },
  { immediate: true },
);

function getTransformOperationDescription(op) {
  const descriptions = {
    keep_keys: "Keeps only the listed keys on each result item. Supports nested key paths (e.g. genre.en).",
    remove_keys: "Removes the listed keys from each result item. Supports nested key paths (e.g. genre.en).",
    ensure_keys: "Ensures every listed key exists on each result item. Missing keys are inserted with null values.",
    group_by: "Groups items by one key path into list entries with grouped documents.",
    replace_nested_item: "Finds nested items by key/value, removes matched entries, and can map values into a target key path.",
    filter_by_allowed_values: "Keeps items only when the key path matches one of the allowed values.",
    filter_by_disallowed_values: "Removes items matching disallowed values and always removes empty values.",
    split_values_to_list: "Splits a string value at the given key by a separator substring, replacing the value with a list of parts.",
    rename_keys: "Moves values from multiple old key paths to new key paths on each result item, removing the old keys.",
  };
  return descriptions[String(op || "").trim()] || "";
}

function formatTransformOperationTitle(op) {
  const normalized = String(op || "").trim();
  return normalized || "operation";
}

function addTransformStep() {
  if (!Array.isArray(model.value)) {
    model.value = [];
  }
  model.value.push(createTransformStep());
}

function removeTransformStep(index) {
  if (!Array.isArray(model.value)) return;
  model.value.splice(index, 1);
}

function addReplaceNestedMapping(step) {
  if (!step || typeof step !== "object") return;
  if (!Array.isArray(step.replace_mappings)) {
    step.replace_mappings = [];
  }
  const sourceMapping = step.replace_mappings[step.replace_mappings.length - 1] || {};
  step.replace_mappings.push(createReplaceNestedMapping(sourceMapping));
}

function removeReplaceNestedMapping(step, index) {
  if (!step || typeof step !== "object") return;
  if (!Array.isArray(step.replace_mappings)) return;
  if (index < 0 || index >= step.replace_mappings.length) return;
  step.replace_mappings.splice(index, 1);
}

function addRenameKeyMapping(step) {
  if (!step || typeof step !== "object") return;
  if (!Array.isArray(step.rename_mappings)) {
    step.rename_mappings = [];
  }
  const sourceMapping = step.rename_mappings[step.rename_mappings.length - 1] || {};
  step.rename_mappings.push(createRenameKeyMapping(sourceMapping));
}

function removeRenameKeyMapping(step, index) {
  if (!step || typeof step !== "object") return;
  if (!Array.isArray(step.rename_mappings)) return;
  if (index < 0 || index >= step.rename_mappings.length) return;
  step.rename_mappings.splice(index, 1);
}

function onTransformOperationChange(step) {
  if (!step || typeof step !== "object") return;
  const normalized = normalizeTransformStepUi({
    op: step.op,
    enabled: step.enabled,
    collapsed: step.collapsed,
  });
  normalized.ui_id = step.ui_id || normalized.ui_id;
  step.op = normalized.op;
  step.enabled = normalized.enabled;
  step.collapsed = normalized.collapsed;
  Object.keys(step).forEach((key) => {
    if (!(key in normalized)) {
      delete step[key];
    }
  });
  Object.entries(normalized).forEach(([key, value]) => {
    step[key] = value;
  });
}
</script>

<style scoped>
.transform-editor {
  border: none !important;
  padding: 0 !important;
  background: none !important;
}

.transform-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.transform-editor-header h3 {
  margin: 0;
  font-size: 15px;
  color: var(--admin-text, #0f172a);
}

.card-hint {
  color: #64748b;
  font-size: 13px;
  margin: 0;
}

.integration-case-hint {
  margin-top: 6px;
}

.transform-step-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}

.transform-step {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.transform-step--dragging {
  opacity: 0.58;
  border-color: #93c5fd;
  background: #f8fbff;
}

.transform-step-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.transform-step-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.drag-handle,
.transform-step-collapse {
  width: 28px;
  height: 28px;
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  background: #f8fafc;
  color: #64748b;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.drag-handle {
  cursor: grab;
}

.drag-handle:active {
  cursor: grabbing;
}

.drag-handle:hover,
.transform-step-collapse:hover {
  border-color: #93c5fd;
  color: #2563eb;
  background: #eff6ff;
}

.transform-step-collapse {
  cursor: pointer;
}

.transform-step-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.step-index {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.transform-step-actions {
  display: flex;
  gap: 6px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group-auto-end {
  justify-content: flex-end;
}

.form-group label {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.form-group input,
.form-group select,
.form-group textarea {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.15s, box-shadow 0.15s;
  background: #fff;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.form-hint {
  font-size: 12px;
  color: #64748b;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.mapping-item-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mapping-separator {
  height: 1px;
  width: 100%;
  background: #e2e8f0;
}

.form-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.empty-state {
  text-align: center;
  padding: 32px;
  color: #64748b;
}

.empty-state.compact {
  padding: 14px;
  text-align: left;
}

@media (max-width: 768px) {
  .form-row {
    grid-template-columns: 1fr;
  }

  .transform-step-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
