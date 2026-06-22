import { ref, watch } from "vue";

export const PANEL_POSITION_OPTIONS = Object.freeze([
  { value: "top-left", label: "Top Left" },
  { value: "top-right", label: "Top Right" },
  { value: "bottom-left", label: "Bottom Left" },
  { value: "bottom-right", label: "Bottom Right" },
]);

export function normalizePanelPosition(rawValue, fallback = "bottom-left") {
  const value = String(rawValue || "").trim();
  if (PANEL_POSITION_OPTIONS.some((option) => option.value === value)) return value;
  return fallback;
}

export function usePanelPosition(storageKey, fallback = "bottom-left") {
  const panelPosition = ref(
    normalizePanelPosition(localStorage.getItem(storageKey), fallback)
  );

  watch(
    panelPosition,
    (value) => {
      const normalized = normalizePanelPosition(value, fallback);
      if (normalized !== value) {
        panelPosition.value = normalized;
        return;
      }
      localStorage.setItem(storageKey, normalized);
    },
    { immediate: true }
  );

  return { panelPosition };
}
