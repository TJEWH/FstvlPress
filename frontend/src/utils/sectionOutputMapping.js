import { convertKeysToSnake } from "./caseConversion.js";
import { DESIGN_PARAMS, OVERRIDABLE_PARAMS, toBackendKey as designParamToBackendKey } from "../designDefs.js";

const LINKS_SECTION_TYPE = "links";
const MAP_SECTION_TYPE = "map";
const LINKS_SOCIAL_ITEM_INDEX_PATH_RE = /^type_data\.items\[(\d+)\](\..+)?$/;

const SECTION_OUTPUT_GROUP_ORDER = {
  content: 0,
  design_tab: 1,
  design_overrides: 2,
};

const DESIGN_SECTION_LABELS = {
  colors: "Colors",
  sections: "Sections",
  fonts: "Fonts",
  layout: "Layout",
  buttons: "Buttons",
  header: "Header",
  customCss: "Custom CSS",
};

const SECTION_GENERIC_OUTPUT_FIELDS = [
  { path: "type_data.section_generic.hide_section_header", kind: "boolean" },
  { path: "type_data.section_generic.hide_section_header_hard", kind: "boolean" },
  { path: "type_data.section_generic.hide_section_description", kind: "boolean" },
  { path: "type_data.section_generic.hide_section_description_hard", kind: "boolean" },
  { path: "type_data.section_generic.remove_section_padding", kind: "boolean" },
  { path: "type_data.section_generic.remove_section_background", kind: "boolean" },
  { path: "type_data.section_generic.button_alignment", kind: "text" },
];

const SECTION_DESIGN_TYPE_DATA_KEYS_BY_TYPE = {
  blog: [
    "filter_enabled",
    "display_style",
    "two_column_non_cards",
    "target_route",
    "show_more_button_type",
    "item_bg_color",
    "item_bg_color_link",
    "item_bg_color_variation",
    "title_color",
    "title_color_link",
    "title_color_variation",
    "desc_color",
    "desc_color_link",
    "desc_color_variation",
    "meta_color",
    "meta_color_link",
    "meta_color_variation",
    "read_more_color",
    "read_more_color_link",
    "read_more_color_variation",
    "separator_color",
    "separator_color_link",
    "separator_color_variation",
    "show_separators",
    "slidable_on_mobile",
    "image_ratio",
  ],
  faq: [
    "question_color",
    "question_color_link",
    "question_color_variation",
    "answer_color",
    "answer_color_link",
    "answer_color_variation",
    "separator_color",
    "separator_color_link",
    "separator_color_variation",
  ],
  gallery: [
    "layout",
    "aspect_ratio",
    "orientation",
    "direction",
  ],
  links: [
    "hide_item_title",
    "alignment",
    "item_max_height",
    "non_social_item_max_width",
    "item_spacing",
    "social_mode",
    "hide_icons_without_links",
    "icon_color",
    "icon_color_link",
    "icon_color_variation",
  ],
  program: [
    "max_visible_hours",
    "default_grouping",
    "fixed_stage_id",
    "fixed_day",
    "fixed_gig_id",
    "allow_group_toggle",
    "allow_day_selection",
    "allow_stage_filter",
    "date_selection_color",
    "date_selection_color_link",
    "date_selection_color_variation",
    "stage_row_height",
    "show_view_toggle",
    "show_gig_description_button",
    "default_view_mode",
  ],
  text_image: [
    "image_layout",
    "image_layout_responsive",
    "image_align_x",
    "image_width_percent",
    "image_max_width_percent",
    "image_max_width_percent_responsive",
    "image_max_height_vh",
    "image_max_height_vh_responsive",
    "image_width_px",
    "image_min_width_px",
    "image_target_width_percent",
    "image_max_width_px",
    "image_height_px",
    "image_text_gap",
    "image_text_gap_responsive",
    "image_border_radius",
    "image_border_radius_responsive",
    "image_bg_opacity",
    "image_aspect_ratio",
    "image_aspect_ratio_responsive",
    "image_interaction",
    "image_click_url",
    "image_bg_zoom",
    "image_bg_focal_x",
    "image_bg_focal_y",
    "image_bg_rotation",
  ],
  ticker: [
    "bg_color",
    "bg_color_link",
    "bg_color_variation",
    "text_color",
    "text_color_link",
    "text_color_variation",
    "separator",
    "separator_image_url",
    "separator_image_responsive_variants",
    "speed",
    "font_size",
    "font_family",
    "pin_to_header",
    "view_mode",
  ],
  tiles: [
    "grid_mode",
    "rows",
    "columns",
    "tile_min_width",
    "tile_max_width",
    "aspect_ratio",
    "direction",
    "always_show_title",
    "checker_color1",
    "checker_color1_link",
    "checker_color1_variation",
    "checker_color2",
    "checker_color2_link",
    "checker_color2_variation",
    "title_gradient_color",
    "title_gradient_color_link",
    "title_gradient_color_variation",
    "artist_button_type",
    "tile_show_reset_button",
  ],
  video: [
    "tv_color",
    "tv_color_link",
    "tv_color_variation",
    "wrapper",
    "device_wrappers",
  ],
};

const FRONTEND_SECTION_OUTPUT_SKIP_KEYS = new Set([
  "_id",
  "id",
  "title",
  "sectionType",
  "section_type",
  "sectionTemplateName",
  "section_template_name",
  "sectionTemplateRef",
  "section_template_ref",
  "titlePlaceholder",
  "title_placeholder",
  "type_data",
  "typeData",
  "sectionIntegrationMapping",
  "section_integration_mapping",
  "sectionOutputMapping",
  "section_output_mapping",
  "order",
  "visible",
  "limit",
  "width_n",
  "widthN",
  "width_d",
  "widthD",
  "device_visibility",
  "deviceVisibility",
  "design_overrides",
  "designOverrides",
  "shared",
]);

const SECTION_OUTPUT_FIELD_PATTERNS_BY_TYPE = {
  text: [
    "title.*",
    "type_data.body.*",
  ],
  text_image: [
    "title.*",
    "type_data.body.*",
    "type_data.image_url",
    "type_data.image_author",
    "type_data.image_click_url",
    "type_data.image_interaction",
    "type_data.image_layout",
    "type_data.image_layout_responsive.*",
    "type_data.image_align_x",
    "type_data.image_max_width_percent",
    "type_data.image_max_width_percent_responsive.*",
    "type_data.image_max_height_vh",
    "type_data.image_max_height_vh_responsive.*",
    "type_data.image_width_px",
    "type_data.image_min_width_px",
    "type_data.image_target_width_percent",
    "type_data.image_max_width_px",
    "type_data.image_height_px",
    "type_data.image_text_gap",
    "type_data.image_text_gap_responsive.*",
    "type_data.image_border_radius",
    "type_data.image_border_radius_responsive.*",
    "type_data.image_bg_opacity",
    "type_data.image_aspect_ratio",
    "type_data.image_aspect_ratio_responsive.*",
    "type_data.image_bg_zoom",
    "type_data.image_bg_focal_x",
    "type_data.image_bg_focal_y",
    "type_data.image_bg_rotation",
  ],
  video: [
    "title.*",
    "type_data.body.*",
    "type_data.video_id",
    "type_data.wrapper",
    "type_data.tv_color",
    "type_data.tv_color_link",
  ],
  faq: [
    "title.*",
    "type_data.body.*",
    "type_data.faqs[*].question.*",
    "type_data.faqs[*].answer.*",
    "type_data.faqs[*].tag.*",
    "type_data.faqs[*].start_date",
    "type_data.faqs[*].end_date",
    "type_data.scope.*",
    "type_data.more_link",
    "type_data.question_color",
    "type_data.question_color_link",
    "type_data.answer_color",
    "type_data.answer_color_link",
    "type_data.separator_color",
    "type_data.separator_color_link",
  ],
  links: [
    "title.*",
    "type_data.body.*",
    "type_data.items[*].title.*",
    "type_data.items[*].image_url",
    "type_data.items[*].icon",
    "type_data.items[*].icon_pack",
    "type_data.items[*].link_url",
    "type_data.items.*.title.*",
    "type_data.items.*.image_url",
    "type_data.items.*.icon",
    "type_data.items.*.icon_pack",
    "type_data.items.*.link_url",
    "type_data.hide_item_title",
    "type_data.alignment",
    "type_data.item_max_height",
    "type_data.non_social_item_max_width",
    "type_data.item_spacing",
    "type_data.social_mode",
    "type_data.hide_icons_without_links",
    "type_data.icon_color",
    "type_data.icon_color_link",
  ],
  ticker: [
    "title.*",
    "type_data.items[*].text.*",
    "type_data.items[*].timestamp",
    "type_data.separator_image_url",
    "type_data.pin_to_header",
  ],
  gallery: [
    "title.*",
    "type_data.body.*",
    "type_data.images[*].image_url",
    "type_data.images[*].image_author",
    "type_data.images[*].zoom",
    "type_data.images[*].focal_x",
    "type_data.images[*].focal_y",
    "type_data.images[*].rotation",
    "type_data.images[*].alt.*",
    "type_data.images[*].caption.*",
    "type_data.show_captions",
    "type_data.layout",
    "type_data.aspect_ratio",
    "type_data.orientation",
  ],
  blog: [
    "title.*",
    "type_data.body.*",
    "type_data.video_url",
    "type_data.scope.*",
    "type_data.access",
  ],
  markdown: [
    "title.*",
    "type_data.raw_markdown",
  ],
  map: [
    "title.*",
    "type_data.body.*",
    "type_data.svg_url",
    "type_data.asset_id",
    "type_data.alt.*",
  ],
  html: [
    "title.*",
    "type_data.mode",
    "type_data.fetch_url",
    "type_data.fetch_selector",
    "type_data.raw_html",
    "type_data.raw_css",
    "type_data.raw_js",
    "type_data.embed_code",
    "type_data.embed_provider",
  ],
  tiles: [
    "title.*",
    "type_data.body.*",
    "type_data.parent_route",
    "type_data.grid_mode",
    "type_data.rows",
    "type_data.columns",
    "type_data.tile_min_width",
    "type_data.tile_max_width",
    "type_data.aspect_ratio",
    "type_data.direction",
    "type_data.checker_color1",
    "type_data.checker_color2",
    "type_data.title_gradient_color",
    "type_data.title_gradient_color_link",
    "type_data.artist_button_type",
    "type_data.always_show_title",
    "type_data.tile_show_reset_button",
    "type_data.tile_top_info_align",
    "type_data.tile_bottom_info_align",
    "type_data.tile_sort_mode",
    "type_data.use_program_gigs",
    "type_data.filters[*].name",
    "type_data.filters[*].target_path",
    "type_data.filters[*].manual_options[*]",
    "type_data.filters[*].enabled",
    "type_data.filter_control_style",
    "type_data.filter_control_order[*]",
    "type_data.tiles[*].image_url",
    "type_data.tiles[*].zoom",
    "type_data.tiles[*].focal_x",
    "type_data.tiles[*].focal_y",
    "type_data.tiles[*].rotation",
    "type_data.tiles[*].title.*",
    "type_data.tiles[*].subtitle.*",
    "type_data.tiles[*].location",
    "type_data.tiles[*].time",
  ],
  program: [
    "title.*",
    "type_data.body.*",
    "type_data.gigs[*].title.*",
    "type_data.gigs[*].start",
    "type_data.gigs[*].end",
    "type_data.gigs[*].stage",
    "type_data.gigs[*].gig_type",
    "type_data.gigs[*].genre.*",
    "type_data.gigs[*].genre_selection[*]",
    "type_data.gigs[*].description.*",
    "type_data.gigs[*].image_url",
    "type_data.gigs[*].image_zoom",
    "type_data.gigs[*].image_focal_x",
    "type_data.gigs[*].image_focal_y",
    "type_data.gigs[*].image_rotation",
    "type_data.gigs[*].highlight_changes",
    "type_data.gigs[*].canceled",
    "type_data.gigs[*].previous_start",
    "type_data.gigs[*].previous_end",
    "type_data.gigs[*].page_slug",
    "type_data.gigs[*].item_url",
    "type_data.route_view_configs[*].route_pattern",
    "type_data.route_view_configs[*].grouping_mode",
    "type_data.route_view_configs[*].view_mode",
    "type_data.route_view_configs[*].stage_filter_mode",
    "type_data.route_view_configs[*].stage_filter_value",
    "type_data.route_view_configs[*].day_filter",
    "type_data.default_grouping",
    "type_data.fixed_stage_id",
    "type_data.fixed_day",
    "type_data.fixed_gig_id",
    "type_data.stage_parent_route",
    "type_data.gig_parent_route",
    "type_data.allow_group_toggle",
    "type_data.allow_day_selection",
    "type_data.allow_stage_filter",
    "type_data.show_view_toggle",
    "type_data.default_view_mode",
    "type_data.time_slot_minutes",
    "type_data.show_genre",
    "type_data.show_description",
    "type_data.show_changes",
    "type_data.day_start_hour",
    "type_data.day_end_hour",
    "type_data.max_visible_hours",
    "type_data.date_selection_color",
    "type_data.date_selection_color_link",
    "type_data.stage_row_height",
  ],
};

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function normalizeSectionType(value, fallback = "text") {
  const text = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/-/g, "_");
  const normalized = text.replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
  return normalized || fallback;
}

function isImagePath(path) {
  const normalized = String(path || "").toLowerCase();
  return (
    normalized.includes("image")
    || normalized.includes("photo")
    || normalized.includes("thumbnail")
    || normalized.includes("cover")
    || normalized.includes("logo")
    || normalized.includes("avatar")
    || normalized.includes("background_media_url")
  );
}

function isIsoDateTimeString(value) {
  const text = String(value || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:?\d{2})?$/.test(text)) {
    return false;
  }
  return Number.isFinite(Date.parse(text));
}

function inferFieldKind(path, value) {
  if (isImagePath(path)) return "image";
  if (typeof value === "number") return "number";
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "string" && isIsoDateTimeString(value)) return "datetime";
  if (isPlainObject(value)) {
    const hasDE = Object.prototype.hasOwnProperty.call(value, "de");
    const hasEN = Object.prototype.hasOwnProperty.call(value, "en");
    if (hasDE || hasEN) return "text";
  }
  return "text";
}

export function sectionOutputFieldKindLabel(kind) {
  const normalized = String(kind || "").trim().toLowerCase();
  if (normalized === "image") return "Image";
  if (normalized === "number") return "Number";
  if (normalized === "boolean") return "Boolean";
  if (normalized === "datetime") return "Datetime";
  if (normalized === "date") return "Date";
  if (normalized === "color") return "Color";
  if (normalized === "url") return "URL";
  if (normalized === "json") return "JSON";
  if (normalized === "list") return "List";
  return "Text";
}

export function formatSectionOutputPathLabel(path) {
  return String(path || "")
    .replace(/\[(\d+)\]/g, " $1 ")
    .replace(/[._]/g, " ")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/(^|\s)\S/g, (value) => value.toUpperCase());
}

function typeLabel(value) {
  return sectionOutputFieldKindLabel(value);
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

function normalizeOutputOption(option) {
  const path = String(option?.path || "").trim();
  const value = String(option?.value || path).trim();
  const label = String(option?.label || value || path).trim();
  if (!value && !path) return null;
  return {
    ...option,
    path,
    value: value || path,
    label,
    required: Boolean(option?.required),
    collectsOptions: Boolean(option?.collectsOptions || option?.collect_options || option?.collectOptions),
    disabled: Boolean(option?.disabled),
  };
}

export function sectionOutputFieldLabelDisplay(option) {
  const normalizedOption = normalizeOutputOption(option) || {};
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

function formatMappingOptionLabel(path, kind) {
  return `${formatSectionOutputPathLabel(path)} (${sectionOutputFieldKindLabel(kind)})`;
}

function escapeRegExp(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeTargetPatternPath(value) {
  return String(value || "").trim().toLowerCase().replace(/[_-]/g, "");
}

function targetPathMatchesPattern(path, pattern) {
  const normalizedPath = normalizeTargetPatternPath(path);
  const normalizedPattern = normalizeTargetPatternPath(pattern);
  if (!normalizedPath || !normalizedPattern) return false;
  const regexSource = escapeRegExp(normalizedPattern)
    .replace(/\\\[\\\*\\\]/g, "\\[[^\\]]+\\]")
    .replace(/\\\*/g, "[^.\\[]+");
  return new RegExp(`^${regexSource}$`).test(normalizedPath);
}

function sectionOutputFieldPatterns(sectionType) {
  const normalizedSectionType = normalizeSectionType(sectionType, "text");
  return SECTION_OUTPUT_FIELD_PATTERNS_BY_TYPE[normalizedSectionType]
    || SECTION_OUTPUT_FIELD_PATTERNS_BY_TYPE.text;
}

function sectionSpecificDesignKeys(sectionType) {
  const normalizedSectionType = normalizeSectionType(sectionType, "text");
  return new Set(SECTION_DESIGN_TYPE_DATA_KEYS_BY_TYPE[normalizedSectionType] || []);
}

function ensureOption(optionsMap, path, kind, meta = {}) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath || optionsMap.has(normalizedPath)) return;
  const normalizedKind = String(kind || "text");
  optionsMap.set(normalizedPath, {
    ...meta,
    path: normalizedPath,
    kind: normalizedKind,
    label: meta.label || formatMappingOptionLabel(normalizedPath, normalizedKind),
  });
}

function collectScalarTargetOptions(node, basePath, optionsMap, depth = 0) {
  if (depth > 6) return;
  if (node == null) {
    ensureOption(optionsMap, basePath, inferFieldKind(basePath, node));
    return;
  }

  if (Array.isArray(node)) {
    node.slice(0, 12).forEach((entry, index) => {
      collectScalarTargetOptions(entry, `${basePath}[${index}]`, optionsMap, depth + 1);
    });
    return;
  }

  if (typeof node === "object") {
    const hasDE = Object.prototype.hasOwnProperty.call(node, "de");
    const hasEN = Object.prototype.hasOwnProperty.call(node, "en");
    if (hasDE || hasEN) {
      if (hasDE) ensureOption(optionsMap, `${basePath}.de`, inferFieldKind(`${basePath}.de`, node.de));
      if (hasEN) ensureOption(optionsMap, `${basePath}.en`, inferFieldKind(`${basePath}.en`, node.en));
      return;
    }
    Object.entries(node).forEach(([key, value]) => {
      const nextPath = basePath ? `${basePath}.${key}` : key;
      collectScalarTargetOptions(value, nextPath, optionsMap, depth + 1);
    });
    return;
  }

  ensureOption(optionsMap, basePath, inferFieldKind(basePath, node));
}

function filterSectionTargetOptions(options, sectionType) {
  const targetPatterns = sectionOutputFieldPatterns(sectionType);
  if (!targetPatterns.length) return [];
  return (Array.isArray(options) ? options : []).filter((option) => {
    const path = String(option?.path || "").trim();
    return path && targetPatterns.some((pattern) => targetPathMatchesPattern(path, pattern));
  });
}

function normalizeLinksSocialPlatformKey(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) return "";
  return raw
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function buildLinksSocialPlatformContext(section) {
  if (!section || typeof section !== "object") return null;
  const rawSectionType = section.section_type !== undefined ? section.section_type : section.sectionType;
  if (normalizeSectionType(rawSectionType, "") !== LINKS_SECTION_TYPE) return null;
  const typeData = (
    section.type_data
    && typeof section.type_data === "object"
    && !Array.isArray(section.type_data)
  ) ? section.type_data : null;
  if (!typeData || !Boolean(typeData.social_mode)) return null;
  const items = Array.isArray(typeData.items) ? typeData.items : [];
  const platformIndexByKey = {};
  const platformKeyByIndex = {};
  items.forEach((entry, index) => {
    if (!entry || typeof entry !== "object") return;
    const platformKey = normalizeLinksSocialPlatformKey(entry.icon);
    if (!platformKey || platformIndexByKey[platformKey] != null) return;
    platformIndexByKey[platformKey] = index;
    platformKeyByIndex[index] = platformKey;
  });
  return {
    platformIndexByKey,
    platformKeyByIndex,
  };
}

export function toLinksSocialKeyPath(path, context) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath || !context) return normalizedPath;
  const match = normalizedPath.match(LINKS_SOCIAL_ITEM_INDEX_PATH_RE);
  if (!match) return normalizedPath;
  const index = Number.parseInt(match[1], 10);
  const platformKey = context.platformKeyByIndex[index];
  if (!platformKey) return normalizedPath;
  const suffix = String(match[2] || "");
  return `type_data.items.${platformKey}${suffix}`;
}

function normalizeSectionTargetOptionsForLinksSocial(options, context) {
  if (!context) return Array.isArray(options) ? options : [];
  const seen = new Set();
  const next = [];
  (Array.isArray(options) ? options : []).forEach((entry) => {
    const path = toLinksSocialKeyPath(entry?.path, context);
    if (!path || seen.has(path)) return;
    seen.add(path);
    const kind = String(entry?.kind || "text");
    next.push({
      ...entry,
      path,
      kind,
      label: formatMappingOptionLabel(path, kind),
    });
  });
  return next;
}

function contentOutputSubgroupLabel(path) {
  const normalized = String(path || "").trim();
  if (normalized.startsWith("title.")) return "Title";
  if (!normalized.startsWith("type_data.")) return "Content";
  const firstToken = normalized
    .slice("type_data.".length)
    .split(".")[0]
    .replace(/\[[^\]]+\]/g, "");
  return formatPathToken(firstToken) || "Type Data";
}

function typeDataPathRootKey(path) {
  const normalized = String(path || "").trim();
  if (!normalized.startsWith("type_data.")) return "";
  return normalized
    .slice("type_data.".length)
    .split(/[.[\]]/, 1)[0]
    .trim();
}

function isSectionSpecificDesignPath(path, sectionType) {
  const normalized = String(path || "").trim();
  if (normalized.startsWith("type_data.section_generic.")) return true;
  const rootKey = typeDataPathRootKey(normalized);
  if (!rootKey) return false;
  return sectionSpecificDesignKeys(sectionType).has(rootKey);
}

function slugifyGroupKey(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "group";
}

function enrichContentOutputOption(option) {
  const subgroupLabel = contentOutputSubgroupLabel(option?.path);
  return {
    ...option,
    sourceTab: "content",
    groupKey: "content",
    groupLabel: "Content",
    subgroupKey: `content-${slugifyGroupKey(subgroupLabel)}`,
    subgroupLabel,
  };
}

function enrichSectionTargetOutputOption(option, sectionType) {
  if (isSectionSpecificDesignPath(option?.path, sectionType)) {
    return {
      ...option,
      sourceTab: "design",
      groupKey: "design_tab",
      groupLabel: "Design Tab",
      subgroupKey: "design-section-parameters",
      subgroupLabel: "Section Parameters",
    };
  }
  return enrichContentOutputOption(option);
}

function designOutputFieldKind(config = {}) {
  const type = String(config.type || "").trim().toLowerCase();
  if (type === "slider") return "number";
  if (type === "checkbox") return "boolean";
  if (type === "color") return "color";
  if (type === "image") return "image";
  if (type === "textarea") return "text";
  return "text";
}

function designOutputSubgroupLabel(config = {}) {
  const sectionLabel = DESIGN_SECTION_LABELS[config.section] || formatPathToken(config.section || "Design");
  const subsection = String(config.subsection || "").trim();
  return subsection ? `${sectionLabel}: ${subsection}` : sectionLabel;
}

function buildDesignOutputFieldOptions() {
  return OVERRIDABLE_PARAMS
    .map((frontKey) => {
      const config = DESIGN_PARAMS[frontKey];
      if (!config) return null;
      const backendKey = designParamToBackendKey(frontKey);
      const path = `design_overrides.${backendKey}`;
      const kind = designOutputFieldKind(config);
      const subgroupLabel = designOutputSubgroupLabel(config);
      return {
        path,
        kind,
        label: `${subgroupLabel} > ${config.label || formatPathToken(frontKey)} (${sectionOutputFieldKindLabel(kind)})`,
        sourceTab: "design",
        groupKey: "design_overrides",
        groupLabel: "Design Overrides",
        subgroupKey: `design-${slugifyGroupKey(subgroupLabel)}`,
        subgroupLabel,
      };
    })
    .filter(Boolean);
}

function inferSectionSpecificDesignFieldKind(path) {
  const normalized = String(path || "").trim().toLowerCase();
  const rootKey = typeDataPathRootKey(normalized) || normalized.split(".").pop() || "";
  if (rootKey.includes("color") && !rootKey.endsWith("_link") && !rootKey.endsWith("_variation")) return "color";
  if (rootKey.includes("image_url")) return "image";
  if (
    rootKey.startsWith("show_")
    || rootKey.startsWith("allow_")
    || rootKey.startsWith("hide_")
    || rootKey.startsWith("remove_")
    || rootKey.startsWith("use_")
    || rootKey === "filter_enabled"
    || rootKey === "social_mode"
    || rootKey === "two_column_non_cards"
    || rootKey === "slidable_on_mobile"
    || rootKey === "always_show_title"
    || rootKey === "tile_show_reset_button"
    || rootKey === "pin_to_header"
  ) {
    return "boolean";
  }
  if (
    rootKey.includes("responsive")
    || rootKey.includes("variants")
    || rootKey === "device_wrappers"
  ) {
    return "json";
  }
  if (
    rootKey.includes("variation")
    || rootKey.includes("height")
    || rootKey.includes("width")
    || rootKey.includes("spacing")
    || rootKey.includes("opacity")
    || rootKey.includes("zoom")
    || rootKey.includes("focal")
    || rootKey.includes("rotation")
    || rootKey.includes("speed")
    || rootKey.includes("font_size")
    || rootKey.includes("gap")
    || rootKey.includes("radius")
    || rootKey.includes("hour")
    || rootKey.includes("minutes")
    || rootKey.includes("visible_hours")
  ) {
    return "number";
  }
  return "text";
}

function buildSectionSpecificDesignOutputFieldOptions(sectionType) {
  const normalizedSectionType = normalizeSectionType(sectionType, "text");
  const designKeys = SECTION_DESIGN_TYPE_DATA_KEYS_BY_TYPE[normalizedSectionType] || [];
  const options = SECTION_GENERIC_OUTPUT_FIELDS.map((entry) => ({
    ...entry,
    label: formatMappingOptionLabel(entry.path, entry.kind),
    sourceTab: "design",
    groupKey: "design_tab",
    groupLabel: "Design Tab",
    subgroupKey: "design-section-generic",
    subgroupLabel: "Section Generic",
  }));
  designKeys.forEach((key) => {
    const path = `type_data.${key}`;
    const kind = inferSectionSpecificDesignFieldKind(path);
    options.push({
      path,
      kind,
      label: formatMappingOptionLabel(path, kind),
      sourceTab: "design",
      groupKey: "design_tab",
      groupLabel: "Design Tab",
      subgroupKey: "design-section-parameters",
      subgroupLabel: "Section Parameters",
    });
  });
  return options;
}

function mergeOutputOptions(options) {
  const byPath = new Map();
  (Array.isArray(options) ? options : []).forEach((option) => {
    const path = String(option?.path || "").trim();
    if (!path) return;
    byPath.set(path, {
      ...(byPath.get(path) || {}),
      ...option,
      path,
    });
  });
  return Array.from(byPath.values());
}

function sectionOutputOptionSort(a, b) {
  const groupA = SECTION_OUTPUT_GROUP_ORDER[a?.groupKey] ?? 99;
  const groupB = SECTION_OUTPUT_GROUP_ORDER[b?.groupKey] ?? 99;
  if (groupA !== groupB) return groupA - groupB;
  const subgroupCompare = String(a?.subgroupLabel || "").localeCompare(String(b?.subgroupLabel || ""));
  if (subgroupCompare !== 0) return subgroupCompare;
  return String(a?.path || "").localeCompare(String(b?.path || ""));
}

export function groupSectionOutputOptions(options) {
  const groups = new Map();
  (Array.isArray(options) ? options : []).forEach((option) => {
    const groupKey = String(option?.groupKey || option?.sourceTab || "content");
    const groupLabel = String(option?.groupLabel || formatPathToken(groupKey) || "Fields");
    const subgroupLabel = String(option?.subgroupLabel || groupLabel);
    const subgroupKey = String(option?.subgroupKey || `${groupKey}-${slugifyGroupKey(subgroupLabel)}`);
    if (!groups.has(groupKey)) {
      groups.set(groupKey, {
        key: groupKey,
        label: groupLabel,
        options: [],
        subgroups: new Map(),
      });
    }
    const group = groups.get(groupKey);
    group.options.push(option);
    if (!group.subgroups.has(subgroupKey)) {
      group.subgroups.set(subgroupKey, {
        key: subgroupKey,
        label: subgroupLabel,
        options: [],
      });
    }
    group.subgroups.get(subgroupKey).options.push(option);
  });

  return Array.from(groups.values())
    .sort((a, b) => {
      const groupA = SECTION_OUTPUT_GROUP_ORDER[a.key] ?? 99;
      const groupB = SECTION_OUTPUT_GROUP_ORDER[b.key] ?? 99;
      if (groupA !== groupB) return groupA - groupB;
      return a.label.localeCompare(b.label);
    })
    .map((group) => ({
      ...group,
      subgroups: Array.from(group.subgroups.values()),
    }));
}

function buildSectionOutputSnapshot(section, options = {}) {
  const source = section && typeof section === "object" ? section : {};
  const rawSectionType = source.section_type !== undefined ? source.section_type : source.sectionType;
  const sectionType = normalizeSectionType(rawSectionType, "text");
  const sourceTypeData = isPlainObject(source.type_data)
    ? source.type_data
    : isPlainObject(source.typeData)
      ? source.typeData
      : null;
  const typeData = sourceTypeData
    ? convertKeysToSnake(sourceTypeData)
    : {};

  if (!sourceTypeData) {
    if (source.body !== undefined) typeData.body = convertKeysToSnake(source.body);
    Object.entries(source).forEach(([key, value]) => {
      if (value === undefined || FRONTEND_SECTION_OUTPUT_SKIP_KEYS.has(key)) return;
      typeData[convertFrontendKeyToTypeDataKey(key)] = convertKeysToSnake(value);
    });
  }

  const sourceDesignOverrides = isPlainObject(options.designOverrides)
    ? options.designOverrides
    : isPlainObject(source.design_overrides)
      ? source.design_overrides
      : isPlainObject(source.designOverrides)
        ? source.designOverrides
        : null;

  return {
    section_type: sectionType,
    title: isPlainObject(source.title) ? convertKeysToSnake(source.title) : { de: "", en: "" },
    type_data: typeData,
    design_overrides: sourceDesignOverrides ? convertKeysToSnake(sourceDesignOverrides) : {},
  };
}

function convertFrontendKeyToTypeDataKey(key) {
  return String(key || "")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1_$2")
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/-/g, "_")
    .toLowerCase();
}

export function buildSectionOutputFieldOptions(section, options = {}) {
  const snapshot = buildSectionOutputSnapshot(section, options);
  const sectionType = normalizeSectionType(snapshot.section_type, "text");
  const withSectionType = (option) => ({
    ...option,
    sectionType,
    section_type: sectionType,
  });
  const optionsMap = new Map();
  if (isPlainObject(snapshot.title)) {
    collectScalarTargetOptions(snapshot.title, "title", optionsMap);
  }
  if (isPlainObject(snapshot.type_data)) {
    collectScalarTargetOptions(snapshot.type_data, "type_data", optionsMap);
  }
  const linksSocialContext = buildLinksSocialPlatformContext(snapshot);
  const targetOptions = normalizeSectionTargetOptionsForLinksSocial(
    filterSectionTargetOptions(
      Array.from(optionsMap.values()),
      sectionType,
    ).sort((a, b) => a.path.localeCompare(b.path)),
    linksSocialContext,
  ).map((option) => withSectionType(enrichSectionTargetOutputOption(option, sectionType)));
  const designTargetOptions = [
    ...buildSectionSpecificDesignOutputFieldOptions(sectionType),
    ...buildDesignOutputFieldOptions(),
  ].map(withSectionType);
  return {
    sectionType,
    linksSocialContext,
    targetOptions: mergeOutputOptions([...targetOptions, ...designTargetOptions]).sort(sectionOutputOptionSort),
  };
}

export function normalizeSectionOutputMapping(rawMapping) {
  const raw = rawMapping && typeof rawMapping === "object" && !Array.isArray(rawMapping)
    ? rawMapping
    : {};
  const mode = String(raw.mode || "default").trim().toLowerCase() === "custom"
    ? "custom"
    : "default";
  const rawPaths = Array.isArray(raw.exposed_target_paths)
    ? raw.exposed_target_paths
    : Array.isArray(raw.exposedTargetPaths)
      ? raw.exposedTargetPaths
      : [];
  const seen = new Set();
  const exposedTargetPaths = [];
  rawPaths.forEach((entry) => {
    const path = String(entry || "").trim();
    if (!path || seen.has(path)) return;
    seen.add(path);
    exposedTargetPaths.push(path);
  });
  return {
    mode,
    exposedTargetPaths,
    exposed_target_paths: exposedTargetPaths,
  };
}

export function serializeSectionOutputMapping(mapping) {
  const normalized = normalizeSectionOutputMapping(mapping);
  return {
    mode: normalized.mode,
    exposed_target_paths: normalized.exposedTargetPaths,
  };
}

function isColorOutputOption(option) {
  const kind = String(option?.kind || option?.type || "").trim().toLowerCase();
  if (kind === "color") return true;
  const path = String(option?.path || "").trim().toLowerCase();
  if (!path) return false;
  return path.split(".").some((token) => token.includes("color"));
}

export function isDefaultSectionOutputPathExposed(option) {
  if (!option || typeof option !== "object") return false;
  const rawSectionType = option.sectionType !== undefined ? option.sectionType : option.section_type;
  if (normalizeSectionType(rawSectionType, "") === MAP_SECTION_TYPE) return false;
  if (String(option.groupKey || "") === "design_overrides") return false;
  if (isColorOutputOption(option)) return false;
  return true;
}

export function defaultSectionOutputExposedPaths(options) {
  return (Array.isArray(options) ? options : [])
    .filter((option) => isDefaultSectionOutputPathExposed(option))
    .map((option) => String(option?.path || "").trim())
    .filter(Boolean);
}

export function effectiveSectionOutputFieldOptions(section, outputMapping = null) {
  const output = buildSectionOutputFieldOptions(section);
  const mapping = normalizeSectionOutputMapping(
    outputMapping
      || section?.section_output_mapping
      || section?.sectionOutputMapping
  );
  if (mapping.mode !== "custom") {
    return {
      ...output,
      targetOptions: output.targetOptions.filter((option) =>
        isDefaultSectionOutputPathExposed(option)
      ),
    };
  }

  const exposedSet = new Set(mapping.exposedTargetPaths);
  return {
    ...output,
    targetOptions: output.targetOptions.filter((option) =>
      exposedSet.has(String(option?.path || "").trim())
    ),
  };
}
