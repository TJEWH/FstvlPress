<template>
  <div class="icon-picker">
    <div class="icon-grid">
      <button
        v-for="icon in curatedIcons"
        :key="`${icon.pack}-${icon.name}`"
        type="button"
        class="icon-tile"
        :class="{ selected: isSelected(icon) }"
        :title="icon.label"
        :disabled="disabled"
        @click="selectCurated(icon)"
      >
        <font-awesome-icon :icon="[icon.pack === 'brands' ? 'fab' : 'fas', icon.name]" />
        <span class="icon-label">{{ icon.label }}</span>
      </button>
      <button
        type="button"
        class="icon-tile"
        :class="{ selected: showCustomRow }"
        title="Custom"
        :disabled="disabled"
        @click="selectCustom"
      >
        <font-awesome-icon :icon="['fas', 'pen']" />
        <span class="icon-label">Custom</span>
      </button>
    </div>

    <div v-if="showCustomRow" class="custom-row">
      <div class="custom-preview">
        <font-awesome-icon v-if="hasPreview" :icon="previewIcon" />
        <span v-else class="muted">?</span>
      </div>
      <div class="custom-fields">
        <div class="custom-inputs">
          <input
            v-model="customName"
            class="field"
            placeholder="e.g. facebook, envelope"
            :disabled="disabled"
            @input="applyCustom"
          />
          <select v-model="customPack" class="field select-field" :disabled="disabled" @change="applyCustom">
            <option value="brands">Brands</option>
            <option value="solid">Solid</option>
          </select>
          <button
            type="button"
            class="btn-danger small custom-clear-btn"
            :disabled="disabled"
            @click="clear"
          >
            Clear
          </button>
        </div>
        <div class="hint">
          Custom Icon Name. Use any Font Awesome icon name (without the <code>fa-</code> prefix).
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
  },
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue"]);

const CURATED_ICONS = [
  { name: "instagram", pack: "brands", label: "Instagram" },
  { name: "facebook", pack: "brands", label: "Facebook" },
  { name: "youtube", pack: "brands", label: "YouTube" },
  { name: "tiktok", pack: "brands", label: "TikTok" },
  { name: "spotify", pack: "brands", label: "Spotify" },
  { name: "soundcloud", pack: "brands", label: "SoundCloud" },
  { name: "bandcamp", pack: "brands", label: "Bandcamp" },
  { name: "vimeo", pack: "brands", label: "Vimeo" },
  { name: "globe", pack: "solid", label: "Website" },
];

const curatedIcons = CURATED_ICONS;

const customName = ref("");
const customPack = ref("brands");
const customMode = ref(false);

const hasCustomModelValue = computed(() => {
  const name = String(props.modelValue.icon || "").trim();
  if (!name) return false;
  return !isCurated(name, props.modelValue.iconPack);
});
const showCustomRow = computed(() => customMode.value || hasCustomModelValue.value);

watch(
  () => [props.modelValue.icon, props.modelValue.iconPack],
  ([name, pack]) => {
    const normalizedName = String(name || "").trim();
    const normalizedPack = pack || "brands";
    if (normalizedName && !isCurated(normalizedName, normalizedPack)) {
      customMode.value = true;
      customName.value = normalizedName;
      customPack.value = normalizedPack;
      return;
    }
    if (normalizedName && isCurated(normalizedName, normalizedPack)) {
      customMode.value = false;
      customName.value = "";
      customPack.value = normalizedPack;
      return;
    }
    if (!customMode.value) {
      customName.value = "";
      customPack.value = normalizedPack;
    }
  },
  { immediate: true },
);

function isCurated(name, pack) {
  if (!name) return false;
  return CURATED_ICONS.some((i) => i.name === name && i.pack === (pack || "brands"));
}

function isSelected(icon) {
  return (
    props.modelValue.icon === icon.name
    && (props.modelValue.iconPack || "brands") === icon.pack
  );
}

function selectCurated(icon) {
  if (props.disabled) return;
  customMode.value = false;
  emit("update:modelValue", {
    ...props.modelValue,
    icon: icon.name,
    iconPack: icon.pack,
  });
}

function selectCustom() {
  if (props.disabled) return;
  customMode.value = true;
  if (!hasCustomModelValue.value) {
    customName.value = "";
    customPack.value = "brands";
  }
  emit("update:modelValue", {
    ...props.modelValue,
    icon: hasCustomModelValue.value ? props.modelValue.icon : "",
    iconPack: hasCustomModelValue.value ? (props.modelValue.iconPack || "brands") : "brands",
  });
}

function applyCustom() {
  if (props.disabled) return;
  customMode.value = true;
  const name = String(customName.value || "").trim();
  emit("update:modelValue", {
    ...props.modelValue,
    icon: name,
    iconPack: customPack.value || "brands",
  });
}

function clear() {
  if (props.disabled) return;
  customMode.value = false;
  customName.value = "";
  customPack.value = "brands";
  emit("update:modelValue", {
    ...props.modelValue,
    icon: "",
    iconPack: "brands",
  });
}

const hasPreview = computed(() => Boolean(String(customName.value || "").trim()));
const previewIcon = computed(() => {
  const pack = (customPack.value || "brands") === "brands" ? "fab" : "fas";
  return [pack, customName.value];
});
</script>

<style scoped>
.icon-picker {
  display: grid;
  gap: 10px;
}

.icon-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(78px, 1fr));
  gap: 6px;
}

.icon-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 8px 4px;
  font-size: 18px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.20));
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.icon-tile:hover {
  border-color: var(--accent, #4f46e5);
}

.icon-tile.selected {
  border-color: var(--accent, #4f46e5);
  background: rgba(79, 70, 229, 0.08);
}

.icon-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--muted, #64748b);
  text-align: center;
  line-height: 1.1;
}

.custom-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding-top: 6px;
  border-top: 1px dashed var(--border, rgba(43, 12, 92, 0.18));
}

.custom-preview {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.20));
  flex-shrink: 0;
}

.custom-preview .muted {
  color: var(--muted, #94a3b8);
  font-weight: 700;
}

.custom-fields {
  flex: 1;
  display: grid;
  gap: 4px;
  min-width: 0;
}

.custom-inputs {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.custom-input-label {
  flex: none;
  white-space: nowrap;
}

.field {
  flex: 1;
  min-width: 0;
  border-radius: 8px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.20));
  background: #fff;
  padding: 8px 12px;
  outline: none;
  color: var(--text, #2b0c5c);
}

.select-field {
  flex: none;
  width: auto;
  min-width: 110px;
  cursor: pointer;
}

.custom-clear-btn {
  flex: none;
}

.field-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted, rgba(43, 12, 92, 0.55));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.hint {
  font-size: 11px;
  color: var(--muted, #64748b);
}

.hint code {
  background: #f1f5f9;
  padding: 1px 4px;
  border-radius: 3px;
}

</style>
