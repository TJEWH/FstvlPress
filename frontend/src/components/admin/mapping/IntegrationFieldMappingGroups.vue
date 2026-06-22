<template>
  <div class="integration-field-mapping-groups">
    <div
      v-for="(group, groupIndex) in groups"
      :key="groupKey(group, groupIndex)"
      class="ifmg-group-card"
      :class="{ 'ifmg-group-card--muted': isGroupMuted(group) }"
    >
      <div class="ifmg-group-head">
        <div class="ifmg-group-title">
          <strong>{{ groupLabel(group) }}</strong>
          <small v-if="group.subtitle">{{ group.subtitle }}</small>
        </div>
        <div class="ifmg-group-actions">
          <slot name="group-actions" :group="group" />
        </div>
      </div>

      <div
        v-if="readonlyGroupsForGroup(group).length"
        class="ifmg-readonly-groups"
      >
        <div
          v-for="readonlyGroup in readonlyGroupsForGroup(group)"
          :key="`readonly-${groupKey(group, groupIndex)}-${readonlyGroup.key || readonlyGroup.label}`"
          class="ifmg-readonly-group"
        >
          <div class="ifmg-readonly-title">
            <strong>{{ readonlyGroup.label }}</strong>
            <small v-if="readonlyGroup.integrationLabel">{{ readonlyGroup.integrationLabel }}</small>
          </div>
          <div class="ifmg-row-head ifmg-row-head--readonly">
            <span>{{ readonlyGroup.sourceColumnLabel || "Source" }}</span>
            <span>{{ readonlyGroup.targetColumnLabel || "Target" }}</span>
            <span aria-hidden="true"></span>
          </div>
          <div
            v-for="(mapping, readonlyIndex) in readonlyMappings(readonlyGroup)"
            :key="`readonly-row-${groupKey(group, groupIndex)}-${readonlyGroup.key || readonlyGroup.label}-${readonlyIndex}`"
            class="ifmg-row ifmg-row--readonly"
          >
            <div class="ifmg-readonly-value">
              <span class="ifmg-field-label ifmg-field-label--readonly">
                <span class="ifmg-label-text">
                  <span class="ifmg-label-prefix">
                    {{ plainLabelDisplay(mapping.sourceLabel).prefix }}
                  </span>
                  <span class="ifmg-label-leaf">{{ plainLabelDisplay(mapping.sourceLabel).leaf }}</span>
                </span>
                <span v-if="plainLabelDisplay(mapping.sourceLabel).type" class="ifmg-label-type">
                  {{ plainLabelDisplay(mapping.sourceLabel).type }}
                </span>
              </span>
            </div>
            <div class="ifmg-readonly-value">
              <span class="ifmg-field-label ifmg-field-label--readonly">
                <span class="ifmg-label-text">
                  <span class="ifmg-label-prefix">
                    {{ plainLabelDisplay(mapping.targetLabel).prefix }}
                  </span>
                  <span class="ifmg-label-leaf">{{ plainLabelDisplay(mapping.targetLabel).leaf }}</span>
                </span>
                <span v-if="plainLabelDisplay(mapping.targetLabel).type" class="ifmg-label-type">
                  {{ plainLabelDisplay(mapping.targetLabel).type }}
                </span>
              </span>
            </div>
            <span aria-hidden="true"></span>
          </div>
        </div>
      </div>

      <div class="ifmg-row-head">
        <span>{{ sourceColumnLabel }}</span>
        <span>{{ resolveTargetColumnLabel(group) }}</span>
        <span aria-hidden="true"></span>
      </div>

      <div
        v-for="mappingRow in completeMappingRows(group)"
        :key="`mapping-row-${groupKey(group, groupIndex)}-${mappingRow.index}`"
        class="ifmg-row ifmg-row--locked"
      >
        <div class="ifmg-readonly-value">
          <span class="ifmg-field-label ifmg-field-label--readonly">
            <span class="ifmg-label-text">
              <span class="ifmg-label-prefix">
                {{ sourceMappingDisplay(mappingRow.mapping.source_path).prefix }}
              </span>
              <span class="ifmg-label-leaf">{{ sourceMappingDisplay(mappingRow.mapping.source_path).leaf }}</span>
            </span>
            <span class="ifmg-label-side">
              <span
                v-if="sourceMappingDisplay(mappingRow.mapping.source_path).hasOptions"
                class="ifmg-options-badge"
              >
                Options
              </span>
              <span
                v-if="sourceMappingDisplay(mappingRow.mapping.source_path).status"
                class="ifmg-status-badge"
              >
                {{ sourceMappingDisplay(mappingRow.mapping.source_path).status }}
              </span>
              <span
                v-if="sourceMappingDisplay(mappingRow.mapping.source_path).type"
                class="ifmg-label-type"
              >
                {{ sourceMappingDisplay(mappingRow.mapping.source_path).type }}
              </span>
            </span>
          </span>
        </div>
        <div class="ifmg-readonly-value">
          <span class="ifmg-field-label ifmg-field-label--readonly">
            <span class="ifmg-label-text">
              <span class="ifmg-label-prefix">
                {{ targetMappingDisplay(group, mappingRow.mapping).prefix }}
              </span>
              <span class="ifmg-label-leaf">{{ targetMappingDisplay(group, mappingRow.mapping).leaf }}</span>
            </span>
            <span class="ifmg-label-side">
              <span
                v-if="targetMappingDisplay(group, mappingRow.mapping).hasOptions"
                class="ifmg-options-badge"
              >
                Options
              </span>
              <span
                v-if="targetMappingDisplay(group, mappingRow.mapping).status"
                class="ifmg-status-badge"
              >
                {{ targetMappingDisplay(group, mappingRow.mapping).status }}
              </span>
              <span
                v-if="targetMappingDisplay(group, mappingRow.mapping).type"
                class="ifmg-label-type"
              >
                {{ targetMappingDisplay(group, mappingRow.mapping).type }}
              </span>
            </span>
          </span>
        </div>
        <button
          :class="removeButtonClass"
          type="button"
          @click="removeMapping(group, mappingRow.index)"
        >
          Remove
        </button>
      </div>

      <div class="ifmg-row ifmg-add-row">
        <div class="ifmg-search-cell">
          <input
            class="ifmg-search-input"
            type="text"
            :value="draftFor(groupKey(group, groupIndex)).sourceQuery"
            placeholder="Search source..."
            @focus="setDraftFocus(groupKey(group, groupIndex), 'source', true)"
            @blur="setDraftFocus(groupKey(group, groupIndex), 'source', false)"
            @input="updateDraftQuery(group, groupIndex, 'source', $event.target.value)"
          />
          <div
            v-if="draftFor(groupKey(group, groupIndex)).selectedSourceLabel"
            class="ifmg-selection"
          >
            <span class="ifmg-field-label">
              <span class="ifmg-label-text">
                <span class="ifmg-label-prefix">
                  {{ draftSourceDisplay(group, groupIndex).prefix }}
                </span>
                <span class="ifmg-label-leaf">{{ draftSourceDisplay(group, groupIndex).leaf }}</span>
              </span>
              <span class="ifmg-label-side">
                <span
                  v-if="draftSourceDisplay(group, groupIndex).hasOptions"
                  class="ifmg-options-badge"
                >
                  Options
                </span>
                <span
                  v-if="draftSourceDisplay(group, groupIndex).type"
                  class="ifmg-label-type"
                >
                  {{ draftSourceDisplay(group, groupIndex).type }}
                </span>
              </span>
            </span>
            <button
              type="button"
              aria-label="Clear source selection"
              @click="clearDraftSelection(group, groupIndex, 'source')"
            >
              &times;
            </button>
          </div>
          <div
            v-if="shouldShowResults(group, groupIndex, 'source')"
            class="ifmg-result-list"
          >
            <template
              v-for="resultGroup in groupedSourceResults(group, groupIndex)"
              :key="`src-group-${groupKey(group, groupIndex)}-${resultGroup.key}`"
            >
              <div v-if="resultGroup.options.length" class="ifmg-result-group-label">
                {{ resultGroup.label }}
              </div>
              <button
                v-for="option in resultGroup.options"
                :key="`src-option-${groupKey(group, groupIndex)}-${option.value}`"
                class="ifmg-result-button"
                type="button"
                :disabled="option.disabled"
                @mousedown.prevent="selectDraftOption(group, groupIndex, 'source', option)"
              >
                <span class="ifmg-field-label">
                  <span class="ifmg-label-text">
                    <span class="ifmg-label-prefix">
                      {{ fieldLabelDisplay(option).prefix }}
                    </span>
                    <span class="ifmg-label-leaf">{{ fieldLabelDisplay(option).leaf }}</span>
                  </span>
                  <span class="ifmg-label-side">
                    <span
                      v-if="fieldLabelDisplay(option).hasOptions"
                      class="ifmg-options-badge"
                    >
                      Options
                    </span>
                    <span
                      v-if="fieldLabelDisplay(option).status"
                      class="ifmg-status-badge"
                    >
                      {{ fieldLabelDisplay(option).status }}
                    </span>
                    <span
                      v-if="fieldLabelDisplay(option).type"
                      class="ifmg-label-type"
                    >
                      {{ fieldLabelDisplay(option).type }}
                    </span>
                  </span>
                </span>
              </button>
            </template>
            <div
              v-if="groupedSourceResults(group, groupIndex).every((entry) => entry.options.length === 0)"
              class="ifmg-result-empty"
            >
              No source fields found.
            </div>
          </div>
        </div>

        <div class="ifmg-search-cell">
          <input
            class="ifmg-search-input"
            type="text"
            :value="draftFor(groupKey(group, groupIndex)).targetQuery"
            placeholder="Search target..."
            @focus="setDraftFocus(groupKey(group, groupIndex), 'target', true)"
            @blur="setDraftFocus(groupKey(group, groupIndex), 'target', false)"
            @input="updateDraftQuery(group, groupIndex, 'target', $event.target.value)"
          />
          <div
            v-if="draftFor(groupKey(group, groupIndex)).selectedTargetLabel"
            class="ifmg-selection"
          >
            <span class="ifmg-field-label">
              <span class="ifmg-label-text">
                <span class="ifmg-label-prefix">
                  {{ draftTargetDisplay(group, groupIndex).prefix }}
                </span>
                <span class="ifmg-label-leaf">{{ draftTargetDisplay(group, groupIndex).leaf }}</span>
              </span>
              <span class="ifmg-label-side">
                <span
                  v-if="draftTargetDisplay(group, groupIndex).hasOptions"
                  class="ifmg-options-badge"
                >
                  Options
                </span>
                <span
                  v-if="draftTargetDisplay(group, groupIndex).status"
                  class="ifmg-status-badge"
                >
                  {{ draftTargetDisplay(group, groupIndex).status }}
                </span>
                <span
                  v-if="draftTargetDisplay(group, groupIndex).type"
                  class="ifmg-label-type"
                >
                  {{ draftTargetDisplay(group, groupIndex).type }}
                </span>
              </span>
            </span>
            <button
              type="button"
              aria-label="Clear target selection"
              @click="clearDraftSelection(group, groupIndex, 'target')"
            >
              &times;
            </button>
          </div>
          <div
            v-if="shouldShowResults(group, groupIndex, 'target')"
            class="ifmg-result-list"
          >
            <template
              v-for="resultGroup in groupedTargetResults(group, groupIndex)"
              :key="`target-group-${groupKey(group, groupIndex)}-${resultGroup.key}`"
            >
              <div v-if="resultGroup.options.length" class="ifmg-result-group-label">
                {{ resultGroup.label }}
              </div>
              <button
                v-for="option in resultGroup.options"
                :key="`target-option-${groupKey(group, groupIndex)}-${option.value}`"
                class="ifmg-result-button"
                type="button"
                :disabled="option.disabled"
                @mousedown.prevent="selectDraftOption(group, groupIndex, 'target', option)"
              >
                <span class="ifmg-field-label">
                  <span class="ifmg-label-text">
                    <span class="ifmg-label-prefix">
                      {{ fieldLabelDisplay(option).prefix }}
                    </span>
                    <span class="ifmg-label-leaf">{{ fieldLabelDisplay(option).leaf }}</span>
                  </span>
                  <span class="ifmg-label-side">
                    <span
                      v-if="fieldLabelDisplay(option).hasOptions"
                      class="ifmg-options-badge"
                    >
                      Options
                    </span>
                    <span
                      v-if="fieldLabelDisplay(option).status"
                      class="ifmg-status-badge"
                    >
                      {{ fieldLabelDisplay(option).status }}
                    </span>
                    <span
                      v-if="fieldLabelDisplay(option).type"
                      class="ifmg-label-type"
                    >
                      {{ fieldLabelDisplay(option).type }}
                    </span>
                  </span>
                </span>
              </button>
            </template>
            <div
              v-if="groupedTargetResults(group, groupIndex).every((entry) => entry.options.length === 0)"
              class="ifmg-result-empty"
            >
              No target fields found.
            </div>
          </div>
        </div>

        <span class="ifmg-action-spacer" aria-hidden="true"></span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from "vue";

const RESULT_LIMIT = 30;

const props = defineProps({
  groups: { type: Array, default: () => [] },
  sourceOptions: { type: Array, default: () => [] },
  sourceColumnLabel: { type: String, default: "Source" },
  targetColumnLabel: { type: String, default: "Target" },
  targetColumnLabelForGroup: { type: Function, default: null },
  targetOptionsForGroup: { type: Function, default: null },
  readonlyGroups: { type: Array, default: () => [] },
  removeButtonClass: { type: String, default: "btn-danger btn-sm" },
});

const emit = defineEmits(["add-mapping", "remove-mapping", "changed"]);

const drafts = reactive({});
const blurTimers = {};

function emptyDraft() {
  return {
    sourceQuery: "",
    targetQuery: "",
    sourceFocused: false,
    targetFocused: false,
    selectedSourceValue: "",
    selectedSourceLabel: "",
    selectedSourceOption: null,
    selectedTargetValue: "",
    selectedTargetLabel: "",
    selectedTargetOption: null,
  };
}

function groupKey(group, index = 0) {
  return String(group?.path || group?.key || `group-${index}`).trim() || `group-${index}`;
}

function draftFor(key) {
  const normalizedKey = String(key || "").trim();
  if (!drafts[normalizedKey]) {
    drafts[normalizedKey] = emptyDraft();
  }
  return drafts[normalizedKey];
}

function groupLabel(group) {
  return String(group?.label || group?.path || "Mapping Group").trim();
}

function isGroupMuted(group) {
  return group?.muted === true || group?.isMuted === true;
}

function resolveTargetColumnLabel(group) {
  if (typeof props.targetColumnLabelForGroup === "function") {
    const value = props.targetColumnLabelForGroup(group);
    if (value != null && String(value).trim()) return String(value).trim();
  }
  return String(props.targetColumnLabel || "Target").trim() || "Target";
}

function readonlyGroupsForGroup(group) {
  const groupPath = String(group?.path || "").trim();
  const direct = Array.isArray(group?.readonlyGroups)
    ? group.readonlyGroups
    : Array.isArray(group?.inheritedMappingGroups)
      ? group.inheritedMappingGroups
      : [];
  const external = props.readonlyGroups
    .filter((entry) => String(entry?.groupPath || entry?.path || "").trim() === groupPath)
    .flatMap((entry) => Array.isArray(entry?.groups) ? entry.groups : [entry]);
  return [...direct, ...external].filter(Boolean);
}

function readonlyMappings(readonlyGroup) {
  return Array.isArray(readonlyGroup?.mappings)
    ? readonlyGroup.mappings.filter((mapping) => mapping?.sourceLabel || mapping?.targetLabel)
    : [];
}

function normalizeOption(option) {
  const path = String(option?.path || "").trim();
  const value = String(option?.value || path).trim();
  const label = String(option?.label || value || path).trim();
  if (!value || !label) return null;
  return {
    ...option,
    path,
    value,
    label,
    required: Boolean(option?.required),
    collectsOptions: Boolean(option?.collectsOptions || option?.collect_options || option?.collectOptions),
    disabled: Boolean(option?.disabled),
  };
}

function typeLabel(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) return "";
  if (normalized === "url") return "URL";
  if (normalized === "json") return "JSON";
  if (normalized === "datetime") return "Datetime";
  if (normalized === "date") return "Date";
  if (normalized === "image") return "Image";
  if (normalized === "number") return "Number";
  if (normalized === "boolean") return "Boolean";
  if (normalized === "list") return "List";
  if (normalized === "text" || normalized === "string") return "Text";
  return normalized
    .replace(/[_-]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());
}

function typeFromLabel(label) {
  const match = String(label || "").match(/\(([^()]+)\)\s*(?:\[[^\]]+\])?\s*$/);
  return match ? typeLabel(match[1]) : "";
}

function statusFromLabel(label) {
  const match = String(label || "").match(/\[([^\]]+)\]\s*$/);
  return match ? String(match[1] || "").trim() : "";
}

function stripLabelDecorations(label) {
  return String(label || "")
    .replace(/\s*\[[^\]]+\]\s*$/, "")
    .replace(/\s*\([^()]+\)\s*$/, "")
    .replace(/^Integration:\s*/i, "")
    .replace(/^Item:\s*/i, "")
    .trim();
}

function displayPath(value) {
  return String(value || "")
    .trim()
    .replace(/^integration\./, "")
    .replace(/^item\./, "")
    .replace(/\[(\d+)\]/g, ".$1");
}

function formatPathToken(value) {
  const normalized = String(value || "")
    .replace(/[_-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!normalized) return "";
  return normalized.replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());
}

function labelPartsFromPath(path) {
  const normalizedPath = displayPath(path);
  const tokens = normalizedPath
    .split(".")
    .map((token) => formatPathToken(token))
    .filter(Boolean);
  if (!tokens.length) return null;
  return {
    prefix: tokens.slice(0, -1).join(" "),
    leaf: tokens[tokens.length - 1],
  };
}

function labelPartsFromLabel(label) {
  const cleanLabel = stripLabelDecorations(label);
  if (!cleanLabel) return { prefix: "", leaf: "" };
  const parts = cleanLabel
    .split(">")
    .map((entry) => entry.trim())
    .filter(Boolean);
  if (parts.length > 1) {
    return {
      prefix: parts.slice(0, -1).join(" "),
      leaf: parts[parts.length - 1],
    };
  }
  return {
    prefix: "",
    leaf: cleanLabel,
  };
}

function fieldLabelDisplay(option) {
  const normalizedOption = normalizeOption(option) || {};
  const pathParts = labelPartsFromPath(normalizedOption.path || normalizedOption.value);
  const labelParts = pathParts || labelPartsFromLabel(normalizedOption.label || normalizedOption.value);
  const type = typeLabel(
    normalizedOption.type
    || normalizedOption.kind
    || normalizedOption.fieldType
    || normalizedOption.effective_type
    || normalizedOption.effectiveType
  ) || typeFromLabel(normalizedOption.label);
  return {
    prefix: String(labelParts?.prefix || "").trim(),
    leaf: String(labelParts?.leaf || normalizedOption.label || normalizedOption.value || "").trim(),
    type,
    status: statusFromLabel(normalizedOption.label),
    required: Boolean(normalizedOption.required),
    hasOptions: Boolean(normalizedOption.collectsOptions),
  };
}

function plainLabelDisplay(label) {
  const labelParts = labelPartsFromLabel(label);
  return {
    prefix: String(labelParts?.prefix || "").trim(),
    leaf: String(labelParts?.leaf || label || "").trim(),
    type: typeFromLabel(label),
    status: statusFromLabel(label),
    required: false,
    hasOptions: false,
  };
}

function normalizeOptions(options) {
  const seen = new Set();
  return (Array.isArray(options) ? options : [])
    .map(normalizeOption)
    .filter(Boolean)
    .filter((option) => {
      if (seen.has(option.value)) return false;
      seen.add(option.value);
      return true;
    });
}

function sourceOptions() {
  return normalizeOptions(props.sourceOptions);
}

function targetOptions(group, sourcePath = "", targetPath = "") {
  if (typeof props.targetOptionsForGroup === "function") {
    return normalizeOptions(props.targetOptionsForGroup(group, sourcePath, targetPath));
  }
  return normalizeOptions(group?.targetOptions);
}

function optionMatches(option, query) {
  const normalizedQuery = String(query || "").trim().toLowerCase();
  if (!normalizedQuery) return true;
  return [
    option.label,
    option.path,
    option.value,
  ].some((value) => String(value || "").toLowerCase().includes(normalizedQuery));
}

function sortOptionList(options) {
  return [...options].sort((a, b) => {
    if (a.required !== b.required) return a.required ? -1 : 1;
    return String(a.label || a.value).localeCompare(String(b.label || b.value));
  });
}

function limitedGroupedResults(options, query) {
  const matches = sortOptionList(options)
    .filter((option) => !option.disabled)
    .filter((option) => optionMatches(option, query))
    .slice(0, RESULT_LIMIT);
  return [
    {
      key: "required",
      label: "Required",
      options: matches.filter((option) => option.required),
    },
    {
      key: "optional",
      label: "Optional",
      options: matches.filter((option) => !option.required),
    },
  ];
}

function groupedSourceResults(group, groupIndex) {
  const draft = draftFor(groupKey(group, groupIndex));
  return limitedGroupedResults(sourceOptions(), draft.sourceQuery);
}

function groupedTargetResults(group, groupIndex) {
  const draft = draftFor(groupKey(group, groupIndex));
  return limitedGroupedResults(
    targetOptions(group, draft.selectedSourceValue, draft.selectedTargetValue),
    draft.targetQuery,
  );
}

function shouldShowResults(group, groupIndex, side) {
  const draft = draftFor(groupKey(group, groupIndex));
  if (side === "source") return draft.sourceFocused || Boolean(String(draft.sourceQuery || "").trim());
  return draft.targetFocused || Boolean(String(draft.targetQuery || "").trim());
}

function setDraftFocus(key, side, focused) {
  const draft = draftFor(key);
  const focusKey = side === "source" ? "sourceFocused" : "targetFocused";
  const timerKey = `${key}:${side}`;
  if (blurTimers[timerKey]) {
    clearTimeout(blurTimers[timerKey]);
    delete blurTimers[timerKey];
  }
  if (focused) {
    draft[focusKey] = true;
    return;
  }
  blurTimers[timerKey] = setTimeout(() => {
    draft[focusKey] = false;
    delete blurTimers[timerKey];
  }, 120);
}

function updateDraftQuery(group, groupIndex, side, value) {
  const draft = draftFor(groupKey(group, groupIndex));
  if (side === "source") {
    draft.sourceQuery = String(value || "");
    draft.selectedSourceValue = "";
    draft.selectedSourceLabel = "";
    draft.selectedSourceOption = null;
    return;
  }
  draft.targetQuery = String(value || "");
  draft.selectedTargetValue = "";
  draft.selectedTargetLabel = "";
  draft.selectedTargetOption = null;
}

function clearDraftSelection(group, groupIndex, side) {
  const draft = draftFor(groupKey(group, groupIndex));
  if (side === "source") {
    draft.sourceQuery = "";
    draft.selectedSourceValue = "";
    draft.selectedSourceLabel = "";
    draft.selectedSourceOption = null;
    draft.selectedTargetValue = "";
    draft.selectedTargetLabel = "";
    draft.selectedTargetOption = null;
    return;
  }
  draft.targetQuery = "";
  draft.selectedTargetValue = "";
  draft.selectedTargetLabel = "";
  draft.selectedTargetOption = null;
}

function resetDraft(group, groupIndex) {
  const key = groupKey(group, groupIndex);
  Object.keys(blurTimers)
    .filter((timerKey) => timerKey.startsWith(`${key}:`))
    .forEach((timerKey) => {
      clearTimeout(blurTimers[timerKey]);
      delete blurTimers[timerKey];
    });
  Object.assign(draftFor(key), emptyDraft());
}

function selectDraftOption(group, groupIndex, side, option) {
  const normalizedOption = normalizeOption(option);
  if (!normalizedOption || normalizedOption.disabled) return;
  const draft = draftFor(groupKey(group, groupIndex));
  if (side === "source") {
    draft.selectedSourceValue = normalizedOption.value;
    draft.selectedSourceLabel = normalizedOption.label;
    draft.selectedSourceOption = normalizedOption;
    draft.sourceQuery = "";
    const nextTargetOptions = targetOptions(group, draft.selectedSourceValue, draft.selectedTargetValue);
    if (
      draft.selectedTargetValue
      && !nextTargetOptions.some((entry) => entry.value === draft.selectedTargetValue)
    ) {
      draft.selectedTargetValue = "";
      draft.selectedTargetLabel = "";
      draft.selectedTargetOption = null;
      draft.targetQuery = "";
    }
  } else {
    draft.selectedTargetValue = normalizedOption.value;
    draft.selectedTargetLabel = normalizedOption.label;
    draft.selectedTargetOption = normalizedOption;
    draft.targetQuery = "";
  }
  commitDraftIfComplete(group, groupIndex);
}

function commitDraftIfComplete(group, groupIndex) {
  const key = groupKey(group, groupIndex);
  const draft = draftFor(key);
  const sourcePath = String(draft.selectedSourceValue || "").trim();
  const targetPath = String(draft.selectedTargetValue || "").trim();
  if (!sourcePath || !targetPath) return;
  resetDraft(group, groupIndex);
  emit("add-mapping", {
    groupPath: String(group?.path || "").trim(),
    source_path: sourcePath,
    target_path: targetPath,
  });
  emit("changed");
  Object.assign(draftFor(key), emptyDraft());
}

function completeMappingRows(group) {
  const mappings = Array.isArray(group?.mappings) ? group.mappings : [];
  return mappings
    .map((mapping, index) => ({ mapping, index }))
    .filter((entry) =>
      String(entry.mapping?.source_path || "").trim()
      && String(entry.mapping?.target_path || "").trim()
    );
}

function findOptionByValue(options, value) {
  const normalizedValue = String(value || "").trim();
  if (!normalizedValue) return null;
  return options.find((option) => option.value === normalizedValue || option.path === normalizedValue) || null;
}

function formatPathFallback(value) {
  const normalized = String(value || "").trim();
  if (!normalized) return "";
  return normalized
    .replace(/^integration\./, "Integration.")
    .replace(/^item\./, "Item.")
    .replace(/\[(\d+)\]/g, ".$1")
    .split(".")
    .filter(Boolean)
    .map((token) =>
      token
        .replace(/[_-]/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .replace(/(^|\s)\S/g, (letter) => letter.toUpperCase())
    )
    .join(" > ");
}

function draftSourceDisplay(group, groupIndex) {
  const draft = draftFor(groupKey(group, groupIndex));
  return fieldLabelDisplay(
    draft.selectedSourceOption
    || { label: draft.selectedSourceLabel, value: draft.selectedSourceValue }
  );
}

function draftTargetDisplay(group, groupIndex) {
  const draft = draftFor(groupKey(group, groupIndex));
  return fieldLabelDisplay(
    draft.selectedTargetOption
    || { label: draft.selectedTargetLabel, value: draft.selectedTargetValue }
  );
}

function sourceMappingDisplay(sourcePath) {
  const option = findOptionByValue(sourceOptions(), sourcePath);
  return fieldLabelDisplay(
    option
    || { label: formatPathFallback(sourcePath), value: sourcePath, path: sourcePath }
  );
}

function targetMappingDisplay(group, mapping) {
  const sourcePath = String(mapping?.source_path || "").trim();
  const targetPath = String(mapping?.target_path || "").trim();
  const option = findOptionByValue(targetOptions(group, sourcePath, targetPath), targetPath);
  return fieldLabelDisplay(
    option
    || { label: formatPathFallback(targetPath), value: targetPath, path: targetPath }
  );
}

function removeMapping(group, index) {
  emit("remove-mapping", {
    groupPath: String(group?.path || "").trim(),
    index,
  });
  emit("changed");
}
</script>

<style scoped>
.integration-field-mapping-groups {
  --ifmg-row-action-width: 86px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ifmg-group-card {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 10px;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ifmg-group-card--muted {
  border-color: #e2e8f0;
  background: #f8fafc;
  opacity: 0.68;
}

.ifmg-group-card--muted:focus-within,
.ifmg-group-card--muted:hover {
  opacity: 1;
}

.ifmg-group-card--muted .ifmg-group-title strong,
.ifmg-group-card--muted .ifmg-row-head,
.ifmg-group-card--muted .ifmg-label-leaf {
  color: #64748b;
}

.ifmg-group-card--muted .ifmg-readonly-value,
.ifmg-group-card--muted .ifmg-search-input,
.ifmg-group-card--muted .ifmg-result-button {
  background: #f8fafc;
}

.ifmg-group-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.ifmg-group-title,
.ifmg-readonly-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.ifmg-group-title strong,
.ifmg-readonly-title strong {
  color: #0f172a;
  font-size: 13px;
}

.ifmg-group-title small,
.ifmg-readonly-title small {
  color: #64748b;
  font-size: 12px;
}

.ifmg-group-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ifmg-readonly-groups {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.ifmg-readonly-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ifmg-row-head,
.ifmg-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) var(--ifmg-row-action-width);
  gap: 8px;
}

.ifmg-row-head {
  align-items: end;
  font-size: 12px;
  color: #334155;
  font-weight: 600;
}

.ifmg-row-head > span:last-child,
.ifmg-action-spacer {
  width: var(--ifmg-row-action-width);
}

.ifmg-row {
  align-items: start;
}

.ifmg-row--locked {
  align-items: stretch;
}

.ifmg-row > .btn-sm {
  width: var(--ifmg-row-action-width);
}

.ifmg-row--locked > .btn-sm {
  align-self: stretch;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: auto;
}

.ifmg-row--readonly {
  opacity: 0.72;
}

.ifmg-row-head--readonly {
  color: #64748b;
}

.ifmg-readonly-value {
  min-height: 34px;
  display: flex;
  align-items: center;
  min-width: 0;
  padding: 7px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  color: #64748b;
  background: #f1f5f9;
  font-size: 13px;
  line-height: 1.25;
  word-break: break-word;
}

.ifmg-add-row {
  padding-top: 2px;
}

.ifmg-search-cell {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.ifmg-search-input {
  width: 100%;
  min-height: 36px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 8px 10px;
  background: #ffffff;
  color: #0f172a;
  font-size: 13px;
}

.ifmg-search-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.ifmg-selection {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 32px;
  padding: 6px 8px;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  background: #eff6ff;
  color: #1e3a8a;
  font-size: 12px;
}

.ifmg-selection > .ifmg-field-label {
  min-width: 0;
  word-break: break-word;
}

.ifmg-selection button {
  border: 0;
  background: transparent;
  color: #1d4ed8;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}

.ifmg-result-list {
  display: grid;
  gap: 6px;
  max-height: 260px;
  overflow: auto;
  padding: 6px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
  z-index: 2;
}

.ifmg-result-group-label {
  padding: 2px 2px 0;
  color: #475569;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.ifmg-result-button {
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-radius: 8px;
  background: #ffffff;
  text-align: left;
  padding: 8px 10px;
  display: grid;
  gap: 4px;
  cursor: pointer;
}

.ifmg-result-button:hover:not(:disabled),
.ifmg-result-button:focus-visible:not(:disabled) {
  border-color: #93c5fd;
  background: #eff6ff;
}

.ifmg-result-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ifmg-field-label {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-width: 0;
}

.ifmg-field-label--readonly {
  align-items: center;
}

.ifmg-label-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 1px;
}

.ifmg-label-prefix {
  display: block;
  min-height: 12.65px;
  color: #64748b;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.15;
  word-break: break-word;
}

.ifmg-label-leaf {
  color: #0f172a;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
  word-break: break-word;
}

.ifmg-label-side {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 5px;
  min-width: 0;
  text-align: right;
}

.ifmg-label-type {
  color: #64748b;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.15;
  white-space: nowrap;
}

.ifmg-options-badge {
  display: inline-flex;
  align-items: center;
  min-height: 18px;
  padding: 2px 6px;
  border-radius: 999px;
  background: #dcfce7;
  color: #166534;
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
}

.ifmg-status-badge {
  display: inline-flex;
  align-items: center;
  min-height: 18px;
  padding: 2px 6px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}

.ifmg-result-empty {
  padding: 8px 10px;
  color: #64748b;
  font-size: 12px;
}

@media (max-width: 900px) {
  .ifmg-group-head {
    flex-direction: column;
    align-items: stretch;
  }

  .ifmg-row-head,
  .ifmg-row {
    grid-template-columns: minmax(0, 1fr);
  }

  .ifmg-row-head > span:last-child,
  .ifmg-action-spacer {
    display: none;
  }

  .ifmg-row > .btn-sm {
    width: auto;
    min-width: var(--ifmg-row-action-width);
  }
}
</style>
