import {
  getCheckerboardStyle,
  HIGH_CONTRAST_LINK_KEY,
  HIGH_CONTRAST_TOKEN,
  TRANSPARENT_LINK_KEY,
  resolveHighContrastColorForBackground,
} from "../../utils/colorLinkOptions.js";

function withTriggerBorder(style, triggerBorder) {
  if (!triggerBorder) return style;
  return { ...style, triggerBorder };
}

export function getBaseSectionSwatchStyle(
  design,
  previewColor,
  {
    rawColor = null,
    linkKey = null,
    treatEmptyAsHighContrast = false,
    triggerBorder = null,
    baseRefColor = null,
    baseRefKey = null,
    adminConfig = null,
  } = {}
) {
  const isTransparent =
    linkKey === TRANSPARENT_LINK_KEY || rawColor === "transparent" || previewColor === "transparent";
  if (isTransparent) return withTriggerBorder(getCheckerboardStyle(), triggerBorder);

  const isHighContrast =
    linkKey === HIGH_CONTRAST_LINK_KEY ||
    rawColor === HIGH_CONTRAST_TOKEN ||
    previewColor === HIGH_CONTRAST_TOKEN ||
    (treatEmptyAsHighContrast && !rawColor && !linkKey);
  if (isHighContrast || !previewColor) {
    const resolvedBaseRefColor =
      typeof baseRefColor === "string" && baseRefColor.trim()
        ? baseRefColor.trim()
        : design?.sectionBackgroundColor || design?.backgroundSecondaryColor || "#ffffff";
    const resolvedColor =
      typeof previewColor === "string" && previewColor.trim() && previewColor !== HIGH_CONTRAST_TOKEN
        ? previewColor.trim()
        : resolveHighContrastColorForBackground(
            design,
            adminConfig,
            {
              backgroundColor: resolvedBaseRefColor,
              backgroundBaseKey: baseRefKey || null,
            }
          ) || design?.highContrastDark || "#0b1220";
    return withTriggerBorder(
      {
        background: resolvedColor,
        previewClass: "high-contrast",
        highContrast: true,
      },
      resolvedBaseRefColor
    );
  }

  return withTriggerBorder({ background: previewColor }, triggerBorder);
}
