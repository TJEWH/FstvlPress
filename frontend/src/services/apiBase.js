const DEFAULT_API_BASE = "/api/v1";
const TRUE_VALUES = new Set(["1", "true", "yes", "on"]);

function normalizeApiBase(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed) return DEFAULT_API_BASE;

  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed.replace(/\/+$/, "");
  }

  const withLeadingSlash = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  return withLeadingSlash.replace(/\/+$/, "") || DEFAULT_API_BASE;
}

export function resolveApiBase() {
  const configuredRaw = import.meta.env.VITE_API_BASE ?? DEFAULT_API_BASE;
  const configuredBase = normalizeApiBase(configuredRaw);
  const allowCrossOriginApi = TRUE_VALUES.has(
    String(import.meta.env.VITE_ALLOW_CROSS_ORIGIN_API ?? "").trim().toLowerCase(),
  );

  if (!/^https?:\/\//i.test(configuredBase)) {
    return configuredBase;
  }

  let configuredUrl;
  try {
    configuredUrl = new URL(configuredBase);
  } catch {
    return DEFAULT_API_BASE;
  }

  if (configuredUrl.origin !== window.location.origin && !allowCrossOriginApi) {
    const sameOriginBase = normalizeApiBase(configuredUrl.pathname || DEFAULT_API_BASE);
    console.warn(
      `[API] Ignoring cross-origin VITE_API_BASE "${configuredBase}" and using "${sameOriginBase}". ` +
        "Set VITE_ALLOW_CROSS_ORIGIN_API=true to allow cross-origin API calls.",
    );
    return sameOriginBase;
  }

  return configuredBase;
}
