export const MOBILE_MAX_WIDTH = 767;
export const DESKTOP_MIN_WIDTH = 1120;
export const TABLET_MAX_WIDTH = DESKTOP_MIN_WIDTH - 1;

export const DEFAULT_RESPONSIVE_CONFIG = {
  mobile: {
    maxWidth: MOBILE_MAX_WIDTH,
    previewWidth: 375,
    previewHeight: 667,
  },
  tablet: {
    minWidth: MOBILE_MAX_WIDTH + 1,
    maxWidth: TABLET_MAX_WIDTH,
    previewWidth: 768,
    previewHeight: 1024,
  },
  desktop: {
    minWidth: DESKTOP_MIN_WIDTH,
    previewWidth: 1120,
    previewHeight: 768,
  },
};

const LEGACY_DESKTOP_PREVIEW_WIDTH = 1024;
const LEGACY_DESKTOP_MIN_WIDTH = 1024;

function clampInt(value, fallback, min, max) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, Math.round(parsed)));
}

function desktopPreviewWidthSource(raw) {
  const parsed = Number(raw);
  if (Number.isFinite(parsed) && Math.round(parsed) === LEGACY_DESKTOP_PREVIEW_WIDTH) {
    return DEFAULT_RESPONSIVE_CONFIG.desktop.previewWidth;
  }
  return raw;
}

function desktopMinWidthSource(raw) {
  const parsed = Number(raw);
  if (Number.isFinite(parsed) && Math.round(parsed) === LEGACY_DESKTOP_MIN_WIDTH) {
    return DEFAULT_RESPONSIVE_CONFIG.desktop.minWidth;
  }
  return raw;
}

export function normalizeResponsiveConfig(raw) {
  const source = raw && typeof raw === "object" ? raw : {};
  const mobileSource = source.mobile && typeof source.mobile === "object" ? source.mobile : {};
  const tabletSource = source.tablet && typeof source.tablet === "object" ? source.tablet : {};
  const desktopSource = source.desktop && typeof source.desktop === "object" ? source.desktop : {};

  const mobileMax = clampInt(
    mobileSource.maxWidth,
    DEFAULT_RESPONSIVE_CONFIG.mobile.maxWidth,
    240,
    4094
  );
  const desktopMin = clampInt(
    desktopMinWidthSource(desktopSource.minWidth),
    Math.max(DEFAULT_RESPONSIVE_CONFIG.desktop.minWidth, mobileMax + 2),
    mobileMax + 2,
    4096
  );
  const tabletMin = mobileMax + 1;
  const tabletMax = desktopMin - 1;

  return {
    mobile: {
      maxWidth: mobileMax,
      previewWidth: clampInt(
        mobileSource.previewWidth,
        DEFAULT_RESPONSIVE_CONFIG.mobile.previewWidth,
        64,
        4096
      ),
      previewHeight: clampInt(
        mobileSource.previewHeight,
        DEFAULT_RESPONSIVE_CONFIG.mobile.previewHeight,
        64,
        8192
      ),
    },
    tablet: {
      minWidth: tabletMin,
      maxWidth: tabletMax,
      previewWidth: clampInt(
        tabletSource.previewWidth,
        DEFAULT_RESPONSIVE_CONFIG.tablet.previewWidth,
        64,
        4096
      ),
      previewHeight: clampInt(
        tabletSource.previewHeight,
        DEFAULT_RESPONSIVE_CONFIG.tablet.previewHeight,
        64,
        8192
      ),
    },
    desktop: {
      minWidth: desktopMin,
      previewWidth: clampInt(
        desktopPreviewWidthSource(desktopSource.previewWidth),
        DEFAULT_RESPONSIVE_CONFIG.desktop.previewWidth,
        64,
        4096
      ),
      previewHeight: clampInt(
        desktopSource.previewHeight,
        DEFAULT_RESPONSIVE_CONFIG.desktop.previewHeight,
        64,
        8192
      ),
    },
  };
}

export function getDeviceFromWidth(width, responsiveConfig = null) {
  const parsed = Number(width);
  const cfg = normalizeResponsiveConfig(responsiveConfig);
  if (Number.isFinite(parsed)) {
    if (parsed <= cfg.mobile.maxWidth) return "mobile";
    if (parsed <= cfg.tablet.maxWidth) return "tablet";
  }
  return "desktop";
}

export function getEffectiveResponsiveDevice(simulatedViewport, viewportWidth, responsiveConfig = null) {
  if (simulatedViewport === "mobile" || simulatedViewport === "tablet" || simulatedViewport === "desktop") {
    return simulatedViewport;
  }
  return getDeviceFromWidth(viewportWidth, responsiveConfig);
}

export function getResponsivePreviewSize(responsiveConfig, device) {
  const cfg = normalizeResponsiveConfig(responsiveConfig);
  const entry = cfg?.[device];
  if (!entry) return null;
  return {
    width: entry.previewWidth,
    height: entry.previewHeight,
  };
}

export function buildResponsiveMediaQuery(device, responsiveConfig = null) {
  const cfg = normalizeResponsiveConfig(responsiveConfig);
  if (device === "mobile") return `(max-width: ${cfg.mobile.maxWidth}px)`;
  if (device === "tablet") return `(min-width: ${cfg.tablet.minWidth}px) and (max-width: ${cfg.tablet.maxWidth}px)`;
  if (device === "desktop") return `(min-width: ${cfg.desktop.minWidth}px)`;
  return "";
}

export function getResponsiveDeviceLabel(device, responsiveConfig = null) {
  const cfg = normalizeResponsiveConfig(responsiveConfig);
  if (device === "mobile") return `Mobile (<=${cfg.mobile.maxWidth}px)`;
  if (device === "tablet") return `Tablet (${cfg.tablet.minWidth}-${cfg.tablet.maxWidth}px)`;
  if (device === "desktop") return `Desktop (>=${cfg.desktop.minWidth}px)`;
  return "";
}

export function buildResponsiveCssVars(responsiveConfig = null) {
  const cfg = normalizeResponsiveConfig(responsiveConfig);
  return {
    "--responsive-mobile-max": `${cfg.mobile.maxWidth}px`,
    "--responsive-mobile-preview-width": `${cfg.mobile.previewWidth}px`,
    "--responsive-mobile-preview-height": `${cfg.mobile.previewHeight}px`,
    "--responsive-tablet-min": `${cfg.tablet.minWidth}px`,
    "--responsive-tablet-max": `${cfg.tablet.maxWidth}px`,
    "--responsive-tablet-preview-width": `${cfg.tablet.previewWidth}px`,
    "--responsive-tablet-preview-height": `${cfg.tablet.previewHeight}px`,
    "--responsive-desktop-min": `${cfg.desktop.minWidth}px`,
    "--responsive-desktop-preview-width": `${cfg.desktop.previewWidth}px`,
    "--responsive-desktop-preview-height": `${cfg.desktop.previewHeight}px`,
  };
}
