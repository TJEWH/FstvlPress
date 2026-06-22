const CHECKERBOARD_DOT_STYLE = {
  background:
    "linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%), linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%)",
  backgroundSize: "8px 8px",
  backgroundPosition: "0 0, 4px 4px",
};

const DEFAULT_BASE_COLOR_FIELDS = [
  { key: "primaryColor", defaultLabel: "Text Primary Color" },
  { key: "secondaryColor", defaultLabel: "Text Secondary Color" },
  { key: "backgroundPrimaryColor", defaultLabel: "Background Primary" },
  { key: "backgroundSecondaryColor", defaultLabel: "Background Secondary" },
  { key: "accentColor", defaultLabel: "Accent Color" },
];
export const DEFAULT_BASE_COLOR_KEYS = DEFAULT_BASE_COLOR_FIELDS.map((field) => field.key);
export const BASE_VARS_SUBSECTION = "Base Vars";

export const TRANSPARENT_LINK_KEY = "transparent";
export const HIGH_CONTRAST_LINK_KEY = "highContrast";
export const HIGH_CONTRAST_TOKEN = "__high_contrast__";

function getBaseColorFields(parameterConfigs = null) {
  const fields = [...DEFAULT_BASE_COLOR_FIELDS];
  const known = new Set(fields.map((field) => field.key));
  if (!parameterConfigs || typeof parameterConfigs !== "object") return fields;

  for (const [key, cfg] of Object.entries(parameterConfigs)) {
    if (known.has(key)) continue;
    if (cfg?.type !== "color" || !cfg?.isBase) continue;
    fields.push({
      key,
      defaultLabel: typeof cfg.label === "string" && cfg.label.trim() ? cfg.label.trim() : key,
    });
    known.add(key);
  }
  return fields;
}

export function getCheckerboardStyle() {
  return { ...CHECKERBOARD_DOT_STYLE };
}

export function getHighContrastStyle(design) {
  const dark = design?.highContrastDark || "#0b1220";
  const light = design?.highContrastLight || "#f8fafc";
  return { background: `linear-gradient(135deg, ${dark} 50%, ${light} 50%)` };
}

function normalizeColorString(value) {
  if (typeof value !== "string") return "";
  return value.trim().toLowerCase();
}

function normalizeHexColor(value) {
  if (typeof value !== "string") return null;
  const raw = value.trim();
  if (!raw) return null;
  const clean = raw.startsWith("#") ? raw.slice(1) : raw;
  if (/^[0-9a-fA-F]{3}$/.test(clean)) {
    return `#${clean
      .split("")
      .map((c) => c + c)
      .join("")
      .toLowerCase()}`;
  }
  if (/^[0-9a-fA-F]{6}$/.test(clean)) {
    return `#${clean.toLowerCase()}`;
  }
  return null;
}

function hexToLuminance(hexColor) {
  const clean = hexColor.replace("#", "");
  const r = parseInt(clean.substring(0, 2), 16) / 255;
  const g = parseInt(clean.substring(2, 4), 16) / 255;
  const b = parseInt(clean.substring(4, 6), 16) / 255;
  const toLinear = (v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
  return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
}

export function getAutoHighContrastColor(design, backgroundColor) {
  const dark = design?.highContrastDark || "#0b1220";
  const light = design?.highContrastLight || "#f8fafc";
  const normalized = normalizeHexColor(backgroundColor);
  if (!normalized) return dark;
  return hexToLuminance(normalized) > 0.4 ? dark : light;
}

export function getBaseSpecificHighContrastEntry(adminConfig, baseColorKey) {
  if (!baseColorKey) return null;
  const raw = adminConfig?.baseColorHighContrast?.[baseColorKey];
  if (!raw) return null;

  if (typeof raw === "string") {
    const color = raw.trim();
    return color
      ? { mode: "custom", color, sourceBaseColor: null, linkedBaseColor: null }
      : null;
  }

  if (typeof raw === "object") {
    const linkedBaseColor =
      typeof raw.linkedBaseColor === "string" && raw.linkedBaseColor.trim()
        ? raw.linkedBaseColor.trim()
        : null;
    const modeRaw =
      typeof raw.mode === "string" && raw.mode.trim()
        ? raw.mode.trim().toLowerCase()
        : null;

    if ((modeRaw === "baselink" || modeRaw === "link" || linkedBaseColor) && linkedBaseColor) {
      return {
        mode: "baseLink",
        color: null,
        sourceBaseColor: null,
        linkedBaseColor,
      };
    }

    const color = typeof raw.color === "string" ? raw.color.trim() : "";
    if (!color) return null;
    const sourceBaseColor =
      typeof raw.sourceBaseColor === "string" && raw.sourceBaseColor.trim()
        ? raw.sourceBaseColor.trim()
        : null;
    return {
      mode: "custom",
      color,
      sourceBaseColor,
      linkedBaseColor: null,
    };
  }

  return null;
}

export function getBaseSpecificHighContrastColor(adminConfig, baseColorKey, design = null) {
  const entry = getBaseSpecificHighContrastEntry(adminConfig, baseColorKey);
  if (!entry) return null;
  if (entry.mode === "baseLink") {
    const linked = entry.linkedBaseColor;
    if (!linked) return null;
    const linkedValue = design?.[linked];
    if (typeof linkedValue === "string" && linkedValue.trim() !== "") {
      return linkedValue.trim();
    }
    const linkedDefault = adminConfig?.parameters?.[linked]?.default;
    if (typeof linkedDefault === "string" && linkedDefault.trim() !== "") {
      return linkedDefault.trim();
    }
    return null;
  }
  return entry.color || null;
}

export function isSpecificHighContrastStale(adminConfig, design, baseColorKey) {
  const entry = getBaseSpecificHighContrastEntry(adminConfig, baseColorKey);
  if (entry?.mode !== "custom" || !entry?.sourceBaseColor) return false;
  const currentBaseColor = normalizeColorString(design?.[baseColorKey]);
  if (!currentBaseColor) return false;
  return normalizeColorString(entry.sourceBaseColor) !== currentBaseColor;
}

export function isBaseColorLinkKey(linkKey, parameterConfigs = null) {
  if (!linkKey) return false;
  return getBaseColorFields(parameterConfigs).some((field) => field.key === linkKey);
}

export function resolveHighContrastColorForBackground(
  design,
  adminConfig,
  { backgroundColor = null, backgroundBaseKey = null } = {}
) {
  let effectiveBaseKey = null;
  if (backgroundBaseKey && isBaseColorLinkKey(backgroundBaseKey, adminConfig?.parameters)) {
    effectiveBaseKey = backgroundBaseKey;
  } else if (backgroundBaseKey) {
    const linkedBaseKey = adminConfig?.colorLinks?.[backgroundBaseKey];
    if (isBaseColorLinkKey(linkedBaseKey, adminConfig?.parameters)) {
      effectiveBaseKey = linkedBaseKey;
    }
  }

  if (effectiveBaseKey) {
    const specific = getBaseSpecificHighContrastColor(adminConfig, effectiveBaseKey, design);
    if (specific) return specific;
  }
  return getAutoHighContrastColor(design, backgroundColor);
}

export function buildColorLinkOptions(
  design,
  { includeTransparent = true, includeHighContrast = false, parameterConfigs = null } = {}
) {
  const options = getBaseColorFields(parameterConfigs).map((field) => ({
    key: field.key,
    label: resolveBaseColorLabel(field, parameterConfigs),
    dotStyle: { background: design?.[field.key] || parameterConfigs?.[field.key]?.default || "#ccc" },
  }));

  if (includeTransparent) {
    options.push({
      key: TRANSPARENT_LINK_KEY,
      label: "Transparent",
      dotStyle: getCheckerboardStyle(),
      dotClass: "checkerboard",
    });
  }

  if (includeHighContrast) {
    options.push({
      key: HIGH_CONTRAST_LINK_KEY,
      label: "High Contrast",
      dotStyle: getHighContrastStyle(design),
    });
  }

  return options;
}

function resolveBaseColorLabel(field, parameterConfigs) {
  const candidate = parameterConfigs?.[field.key]?.label;
  if (typeof candidate === "string" && candidate.trim() !== "") {
    return candidate.trim();
  }
  return field.defaultLabel;
}

export function resolveLinkedColor(design, linkKey, parameterConfigs = null) {
  if (!linkKey) return null;
  if (linkKey === TRANSPARENT_LINK_KEY) return "transparent";
  if (linkKey === HIGH_CONTRAST_LINK_KEY) return HIGH_CONTRAST_TOKEN;
  const fromDesign = design?.[linkKey];
  if (fromDesign !== undefined && fromDesign !== null && String(fromDesign).trim() !== "") return fromDesign;
  const fromParamDefault = parameterConfigs?.[linkKey]?.default;
  if (fromParamDefault !== undefined && fromParamDefault !== null && String(fromParamDefault).trim() !== "") {
    return fromParamDefault;
  }
  return null;
}
