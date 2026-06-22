import { getCurrentServerDateISO } from "./revisionTime.js";

export const LIST_EMPTY_PUBLIC_SECTION_GENERIC_KEY = "hideSectionIfListEmptyPublic";
export const SHOW_SECTION_IF_VIDEO_EMPTY_PUBLIC_SECTION_GENERIC_KEY = "showSectionIfVideoEmptyPublic";

const LIST_EDITOR_SECTION_TYPES = new Set([
  "faq",
  "links",
  "gallery",
  "tiles",
  "program",
  "ticker",
]);

function normalizeSectionType(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/-/g, "_");
}

function stripHtmlToText(value) {
  return String(value ?? "")
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function hasAnyTextValue(value) {
  if (value == null) return false;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return stripHtmlToText(value).length > 0;
  }
  if (typeof value === "object") {
    const de = stripHtmlToText(value.de);
    const en = stripHtmlToText(value.en);
    return de.length > 0 || en.length > 0;
  }
  return false;
}

function hasTickerItemContent(item, sectionData = null) {
  if (hasAnyTextValue(item?.text)) return true;
  if (sectionData?.viewMode === "updates") {
    return hasNonEmptyScalarValue(item?.timestamp);
  }
  return false;
}

function hasNonEmptyScalarValue(value) {
  if (value == null || typeof value === "object") return false;
  const text = String(value).trim();
  return Boolean(text && text !== "[object Object]" && text.toLowerCase() !== "null");
}

function hasLinkItemUrl(item) {
  return hasNonEmptyScalarValue(item?.linkUrl)
    || hasNonEmptyScalarValue(item?.href)
    || hasNonEmptyScalarValue(item?.url);
}

function hasLinkItemContent(item, sectionData) {
  const imageUrl = hasNonEmptyScalarValue(item?.imageUrl)
    || hasNonEmptyScalarValue(item?.logoUrl)
    || hasNonEmptyScalarValue(item?.thumbnailUrl);
  if (imageUrl) return true;

  if (Boolean(sectionData?.socialMode) && hasNonEmptyScalarValue(item?.icon)) {
    if (Boolean(sectionData?.hideIconsWithoutLinks)) return hasLinkItemUrl(item);
    return true;
  }

  return !Boolean(sectionData?.hideItemTitle)
    && hasAnyTextValue(item?.title ?? item?.name)
    && hasLinkItemUrl(item);
}

function isLinksSectionHiddenBySocialLinkFilter(sectionData) {
  if (!Boolean(sectionData?.socialMode) || !Boolean(sectionData?.hideIconsWithoutLinks)) return false;
  const items = Array.isArray(sectionData?.items) ? sectionData.items : [];
  return !items.some((item) => hasLinkItemContent(item, sectionData));
}

function hasVideoContent(sectionData) {
  return String(sectionData?.videoId || "").trim().length > 0;
}

function getBerlinTodayISO() {
  return getCurrentServerDateISO();
}

function normalizeDateOnly(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : "";
}

function tagMatches(a, b) {
  if (!a || !b) return false;
  return String(a.de || "") === String(b.de || "") && String(a.en || "") === String(b.en || "");
}

function hasSectionScope(scope) {
  if (!scope || typeof scope !== "object") return false;
  return String(scope.de || "").trim().length > 0 || String(scope.en || "").trim().length > 0;
}

function faqItemMatchesScope(item, scope) {
  if (!hasSectionScope(scope)) return true;
  return tagMatches(item?.tag, scope);
}

function faqItemMatchesScheduleNow(item, todayIso) {
  const start = normalizeDateOnly(item?.startDate);
  const end = normalizeDateOnly(item?.endDate);
  if (start && start > todayIso) return false;
  if (end && end < todayIso) return false;
  return true;
}

function getFaqSourceItems(state, sectionData) {
  if (Array.isArray(state?.faqItems) && (state?.faqItems.length > 0 || state?.faqSharedLoaded)) {
    return state.faqItems;
  }
  return Array.isArray(sectionData?.faqItems) ? sectionData.faqItems : [];
}

function resolveTickerSourceItems(sectionKey, state, sectionData) {
  if (sectionData?.viewMode === "updates" || !sectionData?.shareItemsWithTickers) {
    return Array.isArray(sectionData?.items) ? sectionData.items : [];
  }

  const masterSectionId = String(sectionData?.sharedTickerMasterSectionId || "").trim();
  if (!masterSectionId) return [];

  const sectionIds = state?.sectionIds || {};
  const masterKey = Object.keys(sectionIds).find((key) => String(sectionIds[key] || "").trim() === masterSectionId);
  if (!masterKey || masterKey === sectionKey) return [];

  const masterItems = state?.sectionsData?.[masterKey]?.items;
  return Array.isArray(masterItems) ? masterItems : [];
}

function hasTileItemContent(tile) {
  if (!tile || typeof tile !== "object") return false;
  const tileImageUrl = String(tile.imageUrl || "").trim();
  if (tileImageUrl) return true;
  if (hasAnyTextValue(tile.title)) return true;
  if (hasAnyTextValue(tile.subtitle)) return true;
  if (hasAnyTextValue(tile.location)) return true;
  if (hasAnyTextValue(tile.time || tile.dateTime)) return true;
  return false;
}

function getProgramItems(state, sectionData) {
  const shared = Array.isArray(state?.programSharedGigs) ? state.programSharedGigs : [];
  if (shared.length > 0 || state?.programSharedLoaded) return shared;
  return Array.isArray(sectionData?.gigs) ? sectionData.gigs : [];
}

function getSectionType(sectionKey, state, sectionData) {
  const explicitType = normalizeSectionType(sectionData?.sectionType);
  if (explicitType) return explicitType;
  const metaType = normalizeSectionType(state?.sectionMeta?.[sectionKey]?.sectionType);
  if (metaType) return metaType;
  return normalizeSectionType(String(sectionKey || "").split("_")[0]);
}

export function sectionSupportsListEmptyPublicToggle(sectionType) {
  return LIST_EDITOR_SECTION_TYPES.has(normalizeSectionType(sectionType));
}

export function isHideEmptyListInPublicEnabled(sectionData) {
  const generic = sectionData?.sectionGeneric;
  return Boolean(generic && typeof generic === "object" && generic[LIST_EMPTY_PUBLIC_SECTION_GENERIC_KEY] === true);
}

function isShowSectionIfVideoEmptyPublicEnabled(sectionData) {
  const generic = sectionData?.sectionGeneric;
  return Boolean(
    generic
    && typeof generic === "object"
    && generic[SHOW_SECTION_IF_VIDEO_EMPTY_PUBLIC_SECTION_GENERIC_KEY] === true
  );
}

export function sectionHasListEditorContent(sectionKey, state, sectionData = null, explicitType = "") {
  const data = sectionData || state?.sectionsData?.[sectionKey] || null;
  if (!data || typeof data !== "object") return false;

  const sectionType = normalizeSectionType(explicitType || getSectionType(sectionKey, state, data));
  if (!sectionSupportsListEmptyPublicToggle(sectionType)) return true;

  if (sectionType === "faq") {
    const todayIso = getBerlinTodayISO();
    const scopedItems = getFaqSourceItems(state, data)
      .filter((item) => faqItemMatchesScope(item, data?.scope))
      .filter((item) => faqItemMatchesScheduleNow(item, todayIso));
    return scopedItems.some((item) =>
      hasAnyTextValue(item?.q) || hasAnyTextValue(item?.a)
    );
  }

  if (sectionType === "links") {
    const items = Array.isArray(data.items) ? data.items : [];
    return items.some((item) => hasLinkItemContent(item, data));
  }

  if (sectionType === "gallery") {
    const images = Array.isArray(data.images) ? data.images : [];
    if (images.some((image) =>
      String(image?.imageUrl || "").trim().length > 0
    )) {
      return true;
    }
    const mediaTagBindings = Array.isArray(data.mediaTagBindings)
      ? data.mediaTagBindings
      : [];
    return mediaTagBindings.some((binding) => {
      if (!binding || typeof binding !== "object") return false;
      if (binding.enabled === false) return false;
      return Boolean(String(binding.resolvedTag || "").trim());
    });
  }

  if (sectionType === "tiles") {
    if (Boolean(data.useProgramGigs ?? true)) {
      const sharedGigs = Array.isArray(state?.programSharedGigs) ? state.programSharedGigs : [];
      return sharedGigs.length > 0;
    }
    const tiles = Array.isArray(data.tiles) ? data.tiles : [];
    return tiles.some((tile) => hasTileItemContent(tile));
  }

  if (sectionType === "program") {
    return getProgramItems(state, data).length > 0;
  }

  if (sectionType === "ticker") {
    const items = resolveTickerSourceItems(sectionKey, state, data);
    return items.some((item) => hasTickerItemContent(item, data));
  }

  return true;
}

export function isSectionHiddenInPublicBecauseEmptyList(sectionKey, state, sectionData = null) {
  const data = sectionData || state?.sectionsData?.[sectionKey] || null;
  if (!data || typeof data !== "object") return false;

  const sectionType = getSectionType(sectionKey, state, data);
  if (sectionType === "links" && isLinksSectionHiddenBySocialLinkFilter(data)) {
    return true;
  }
  if (sectionSupportsListEmptyPublicToggle(sectionType)) {
    if (!isHideEmptyListInPublicEnabled(data)) return false;
    return !sectionHasListEditorContent(sectionKey, state, data, sectionType);
  }
  if (sectionType === "video") {
    if (hasVideoContent(data)) return false;
    return !isShowSectionIfVideoEmptyPublicEnabled(data);
  }
  return false;
}
