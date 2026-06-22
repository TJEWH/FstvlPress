export const COLOR_VARIATION_OPTIONS = [100, 80, 50, 20];
export const DEFAULT_COLOR_VARIATION = 100;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function normalizeColorVariation(value) {
  const asNumber = Number.parseInt(value, 10);
  if (!Number.isFinite(asNumber)) return DEFAULT_COLOR_VARIATION;
  return COLOR_VARIATION_OPTIONS.includes(asNumber) ? asNumber : DEFAULT_COLOR_VARIATION;
}

function parseHexColor(color) {
  const raw = color.trim().replace(/^#/, "");
  if (/^[0-9a-fA-F]{3}$/.test(raw)) {
    return {
      r: Number.parseInt(raw[0] + raw[0], 16),
      g: Number.parseInt(raw[1] + raw[1], 16),
      b: Number.parseInt(raw[2] + raw[2], 16),
      a: 1,
    };
  }
  if (/^[0-9a-fA-F]{4}$/.test(raw)) {
    return {
      r: Number.parseInt(raw[0] + raw[0], 16),
      g: Number.parseInt(raw[1] + raw[1], 16),
      b: Number.parseInt(raw[2] + raw[2], 16),
      a: Number.parseInt(raw[3] + raw[3], 16) / 255,
    };
  }
  if (/^[0-9a-fA-F]{6}$/.test(raw)) {
    return {
      r: Number.parseInt(raw.slice(0, 2), 16),
      g: Number.parseInt(raw.slice(2, 4), 16),
      b: Number.parseInt(raw.slice(4, 6), 16),
      a: 1,
    };
  }
  if (/^[0-9a-fA-F]{8}$/.test(raw)) {
    return {
      r: Number.parseInt(raw.slice(0, 2), 16),
      g: Number.parseInt(raw.slice(2, 4), 16),
      b: Number.parseInt(raw.slice(4, 6), 16),
      a: Number.parseInt(raw.slice(6, 8), 16) / 255,
    };
  }
  return null;
}

function parseRgbColor(color) {
  const match = color.trim().match(/^rgba?\(([^)]+)\)$/i);
  if (!match) return null;
  const parts = match[1].split(",").map((part) => part.trim());
  if (parts.length < 3) return null;
  const r = Number.parseFloat(parts[0]);
  const g = Number.parseFloat(parts[1]);
  const b = Number.parseFloat(parts[2]);
  const alphaRaw = parts.length >= 4 ? Number.parseFloat(parts[3]) : 1;
  if (![r, g, b, alphaRaw].every((v) => Number.isFinite(v))) return null;
  return {
    r: clamp(Math.round(r), 0, 255),
    g: clamp(Math.round(g), 0, 255),
    b: clamp(Math.round(b), 0, 255),
    a: clamp(alphaRaw, 0, 1),
  };
}

function formatAlpha(alpha) {
  if (!Number.isFinite(alpha)) return "1";
  return String(Number(alpha.toFixed(3)));
}

function parseColor(colorValue) {
  if (typeof colorValue !== "string") return null;
  const raw = colorValue.trim();
  if (!raw) return null;
  if (raw.startsWith("#")) return parseHexColor(raw);
  return parseRgbColor(raw);
}

export function applyColorVariation(colorValue, variationPercent) {
  const normalizedVariation = normalizeColorVariation(variationPercent);
  if (typeof colorValue !== "string") return colorValue;
  const raw = colorValue.trim();
  if (!raw) return colorValue;
  if (raw === "transparent" || raw === "__high_contrast__") return colorValue;
  if (normalizedVariation === DEFAULT_COLOR_VARIATION) return colorValue;

  const parsed = parseColor(raw);
  if (!parsed) return colorValue;

  const alpha = clamp(parsed.a * (normalizedVariation / 100), 0, 1);
  return `rgba(${parsed.r}, ${parsed.g}, ${parsed.b}, ${formatAlpha(alpha)})`;
}

