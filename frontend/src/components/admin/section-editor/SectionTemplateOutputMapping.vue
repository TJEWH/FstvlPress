<template>
  <div class="section-output">
    <div class="section-output__head">
      <div>
        <h4>Output Fields</h4>
        <p>{{ visibleCount }} / {{ outputOptions.length }} exposed</p>
      </div>
      <button
        class="section-output__reset"
        type="button"
        :disabled="outputMode === 'default'"
        @click="resetDefaultOutput"
      >
        Reset default
      </button>
    </div>

    <div v-if="outputOptions.length === 0" class="section-output__empty">
      No output fields available.
    </div>
    <div v-else class="section-output__groups">
      <section
        v-for="group in outputOptionGroups"
        :key="`section-output-group-${group.key}`"
        class="section-output__group"
      >
        <div class="section-output__group-head">
          <strong>{{ group.label }}</strong>
          <small>{{ exposedCountForOptions(group.options) }} / {{ group.options.length }} exposed</small>
        </div>
        <div class="section-output__grid">
          <label
            v-for="option in group.options"
            :key="`section-output-${option.path}`"
            class="section-output__option"
          >
            <input
              type="checkbox"
              :checked="isOptionExposed(option)"
              @change="setPathExposed(option.path, $event.target.checked)"
            />
            <span class="section-output__field-label">
              <span v-if="fieldDisplay(option).prefix" class="section-output__label-prefix">
                {{ fieldDisplay(option).prefix }}
              </span>
              <span class="section-output__label-row">
                <strong class="section-output__label-leaf">{{ fieldDisplay(option).leaf }}</strong>
                <span v-if="fieldDisplay(option).type" class="section-output__label-type">
                  {{ fieldDisplay(option).type }}
                </span>
              </span>
            </span>
          </label>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

import { useStore } from "../../../store/store.js";
import {
  buildSectionOutputFieldOptions,
  defaultSectionOutputExposedPaths,
  groupSectionOutputOptions,
  isDefaultSectionOutputPathExposed,
  normalizeSectionOutputMapping,
  sectionOutputFieldLabelDisplay,
  serializeSectionOutputMapping,
} from "../../../utils/sectionOutputMapping.js";

const props = defineProps({
  sectionKey: { type: String, required: true },
  sectionData: { type: Object, default: null },
  designOverrides: { type: Object, default: null },
});

const { state, updateSection } = useStore();

const resolvedDesignOverrides = computed(() =>
  props.designOverrides || state.sectionDesignOverrides?.[props.sectionKey] || null
);

const outputFieldDetails = computed(() =>
  buildSectionOutputFieldOptions(props.sectionData || {}, {
    designOverrides: resolvedDesignOverrides.value,
  })
);

const outputOptions = computed(() =>
  outputFieldDetails.value.targetOptions
);

const outputOptionGroups = computed(() =>
  groupSectionOutputOptions(outputOptions.value)
);

const outputMapping = computed(() =>
  normalizeSectionOutputMapping(props.sectionData?.sectionOutputMapping)
);

const outputMode = computed(() => outputMapping.value.mode);
const customExposedPathSet = computed(() => new Set(outputMapping.value.exposedTargetPaths));
const allOptionPaths = computed(() =>
  outputOptions.value.map((option) => String(option?.path || "").trim()).filter(Boolean)
);
const defaultExposedPathSet = computed(() =>
  new Set(defaultSectionOutputExposedPaths(outputOptions.value))
);

const visibleCount = computed(() =>
  outputMode.value === "custom"
    ? outputOptions.value.filter((option) => customExposedPathSet.value.has(String(option?.path || "").trim())).length
    : outputOptions.value.filter((option) => isDefaultSectionOutputPathExposed(option)).length
);

function exposedCountForOptions(options) {
  const entries = Array.isArray(options) ? options : [];
  if (outputMode.value !== "custom") {
    return entries.filter((option) => isDefaultSectionOutputPathExposed(option)).length;
  }
  return entries.filter((option) => customExposedPathSet.value.has(String(option?.path || "").trim())).length;
}

function fieldDisplay(option) {
  return sectionOutputFieldLabelDisplay(option);
}

function persistMapping(mapping) {
  updateSection(
    props.sectionKey,
    { sectionOutputMapping: serializeSectionOutputMapping(mapping) },
    { revisionKind: "content" },
  );
}

function resetDefaultOutput() {
  if (outputMode.value === "default") return;
  persistMapping({
    mode: "default",
    exposedTargetPaths: [],
  });
}

function isOptionExposed(option) {
  const path = option?.path;
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return false;
  if (outputMode.value !== "custom") return isDefaultSectionOutputPathExposed(option);
  return customExposedPathSet.value.has(normalizedPath);
}

function setPathExposed(path, exposed) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return;
  const nextPaths = outputMode.value === "custom"
    ? outputMapping.value.exposedTargetPaths.filter((entry) => allOptionPaths.value.includes(entry))
    : allOptionPaths.value.filter((entry) => defaultExposedPathSet.value.has(entry));
  const nextSet = new Set(nextPaths);
  if (exposed) {
    nextSet.add(normalizedPath);
  } else {
    nextSet.delete(normalizedPath);
  }
  persistMapping({
    mode: "custom",
    exposedTargetPaths: allOptionPaths.value.filter((entry) => nextSet.has(entry)),
  });
}
</script>

<style scoped>
.section-output {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-output__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-output__head h4,
.section-output__head p {
  margin: 0;
}

.section-output__head h4 {
  font-size: 14px;
  color: #0f172a;
}

.section-output__head p {
  margin-top: 3px;
  font-size: 12px;
  color: #64748b;
}

.section-output__reset {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  padding: 8px 10px;
  color: #0f172a;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.section-output__reset:disabled {
  cursor: default;
  opacity: 0.45;
}

.section-output__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px;
}

.section-output__groups,
.section-output__group {
  display: flex;
  flex-direction: column;
}

.section-output__groups {
  gap: 12px;
}

.section-output__group {
  gap: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 10px;
}

.section-output__group-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
}

.section-output__group-head strong {
  font-size: 13px;
  color: #0f172a;
}

.section-output__group-head small {
  font-size: 11px;
  color: #64748b;
}

.section-output__option {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  min-width: 0;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  padding: 9px 10px;
  cursor: pointer;
}

.section-output__option input {
  margin-top: 3px;
}

.section-output__field-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.section-output__label-prefix {
  font-size: 10px;
  font-weight: 650;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  overflow-wrap: anywhere;
}

.section-output__label-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.section-output__label-leaf {
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
  overflow-wrap: anywhere;
}

.section-output__label-type {
  flex: 0 0 auto;
  border-radius: 999px;
  background: #e0f2fe;
  padding: 2px 6px;
  font-size: 10px;
  font-weight: 700;
  color: #0369a1;
}

.section-output__empty {
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  padding: 14px;
  color: #64748b;
  font-size: 13px;
}
</style>
