const DEFAULT_APP_DISPLAY_NAME = typeof __APP_DISPLAY_NAME__ === "string"
  ? __APP_DISPLAY_NAME__
  : "FstvlPress";

function normalizeConfigString(value) {
  const normalized = String(value || "").trim();
  return normalized || "";
}

export function getRuntimeAppConfig() {
  if (typeof window === "undefined" || !window.APP_CONFIG || typeof window.APP_CONFIG !== "object") {
    return {};
  }
  return window.APP_CONFIG;
}

export function getAppDisplayName() {
  const runtimeName = normalizeConfigString(getRuntimeAppConfig().APP_DISPLAY_NAME);
  const buildName = normalizeConfigString(import.meta.env.VITE_APP_DISPLAY_NAME);
  return runtimeName || buildName || DEFAULT_APP_DISPLAY_NAME;
}
