import { computed, onMounted, onUnmounted, ref, unref, watch } from "vue";
import { useStore } from "../store/store.js";
import * as api from "../services/api.js";

const EXTERNAL_ICON_LABELS = Object.freeze({
  other: "External Link",
  facebook: "Facebook",
  instagram: "Instagram",
  twitter: "Twitter",
  youtube: "YouTube",
  tiktok: "TikTok",
});

function normalizePageStatus(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (raw === "draft") return "hidden";
  if (raw === "init" || raw === "published" || raw === "under_construction" || raw === "hidden") return raw;
  return "hidden";
}

function isForcedTopLevelMenuItem(page) {
  const slug = String(page?.slug || "").trim();
  if (!slug || slug === "landing") return false;
  return Boolean(page?.menu_show_as_top_level);
}

function formatSlugAsTitle(slug) {
  const lastPart = String(slug || "").split("/").pop() || "";
  return lastPart
    .split("-")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function sortMenuNodes(nodes) {
  nodes.sort((a, b) => {
    const orderA = a.menu_order ?? 0;
    const orderB = b.menu_order ?? 0;
    if (orderA !== orderB) return orderA - orderB;

    if (a.slug === "landing") return -1;
    if (b.slug === "landing") return 1;

    return String(a.slug || "").localeCompare(String(b.slug || ""));
  });

  nodes.forEach((node) => {
    if (node.children?.length) sortMenuNodes(node.children);
  });

  return nodes;
}

function buildMenuTree(pages) {
  if (!pages.length) return [];

  const nodeMap = new Map();
  const virtualParentMap = new Map();
  for (const page of pages) {
    nodeMap.set(page.slug, {
      slug: page.slug,
      title: page.title,
      menu_title: page.menu_title,
      menu_parent_title: page.menu_parent_title,
      children: [],
      hasOwnPage: true,
      is_visible: page.is_visible !== false,
      status: normalizePageStatus(page.status),
      effective_status: normalizePageStatus(page.effective_status || page.status),
      menu_order: page.menu_order ?? 0,
    });
  }

  const tree = [];
  for (const page of pages) {
    const node = nodeMap.get(page.slug);
    const parts = String(page.slug || "").split("/");

    if (parts.length === 1 || isForcedTopLevelMenuItem(page)) {
      tree.push(node);
      continue;
    }

    const parentSlug = parts.slice(0, -1).join("/");
    const parent = nodeMap.get(parentSlug);

    if (parent) {
      parent.children.push(node);
      continue;
    }

    let virtualParent = virtualParentMap.get(parentSlug);
    if (!virtualParent) {
      virtualParent = {
        slug: parentSlug,
        title: null,
        menu_title: null,
        menu_parent_title: null,
        children: [],
        hasOwnPage: false,
        is_visible: false,
        status: "hidden",
        effective_status: "hidden",
        menu_order: node.menu_order ?? 0,
      };
      virtualParentMap.set(parentSlug, virtualParent);
      tree.push(virtualParent);
    } else if ((node.menu_order ?? 0) < (virtualParent.menu_order ?? 0)) {
      virtualParent.menu_order = node.menu_order ?? 0;
    }

    virtualParent.children.push(node);
  }

  return sortMenuNodes(tree);
}

export function resolveBrandIconName(iconName) {
  const normalized = String(iconName || "").trim().toLowerCase();
  if (normalized === "twitter") return "x-twitter";
  return normalized || "x-twitter";
}

export function useNavigationMenu(options = {}) {
  const { state } = useStore();
  const menuPages = ref([]);
  const loading = ref(false);
  const searchQuery = options.searchQuery || ref("");

  const internalMenuPages = computed(() => {
    return (Array.isArray(menuPages.value) ? menuPages.value : [])
      .filter((item) => String(item?.kind || "").trim().toLowerCase() !== "external")
      .filter((item) => Boolean(item?.slug));
  });

  const externalMenuLinks = computed(() => {
    return (Array.isArray(menuPages.value) ? menuPages.value : [])
      .filter((item) => String(item?.kind || "").trim().toLowerCase() === "external")
      .sort((a, b) => {
        const orderA = Number(a?.order ?? 0);
        const orderB = Number(b?.order ?? 0);
        if (orderA !== orderB) return orderA - orderB;
        return String(a?.id || "").localeCompare(String(b?.id || ""));
      })
      .map((item) => {
        const href = String(item?.external_url || item?.url || "").trim();
        const icon = String(item?.icon || "").trim().toLowerCase() || null;
        const label = resolveExternalItemLabel(item);
        return {
          id: String(item?.id || href || `external-${item?.order ?? 0}`),
          href,
          icon,
          label,
          title: label,
        };
      })
      .filter((item) => Boolean(item.href));
  });

  const menuTree = computed(() => buildMenuTree(internalMenuPages.value));

  function resolveLocalizedMenuText(textValue, fallbackSlug) {
    const value = textValue?.[state.lang] || textValue?.de || textValue?.en || "";
    const normalized = String(value || "").trim();
    if (normalized) return normalized;
    return formatSlugAsTitle(fallbackSlug);
  }

  function getMenuNodeTitle(item) {
    const title = item.menu_parent_title || item.menu_title || item.title;
    if (!title) return formatSlugAsTitle(item.slug);
    return resolveLocalizedMenuText(title, item.slug);
  }

  function getMenuPageTitle(item) {
    const title = item.menu_title || item.title;
    if (!title) return formatSlugAsTitle(item.slug);
    return resolveLocalizedMenuText(title, item.slug);
  }

  function resolveExternalItemLabel(item) {
    const label = item?.label && typeof item.label === "object" ? item.label : null;
    const localizedLabel = label?.[state.lang] || label?.de || label?.en || "";
    const normalized = String(localizedLabel || "").trim();
    if (normalized) return normalized;
    const icon = String(item?.icon || "").trim().toLowerCase();
    if (icon && EXTERNAL_ICON_LABELS[icon]) return EXTERNAL_ICON_LABELS[icon];
    return String(item?.url || item?.external_url || "").trim();
  }

  function getMenuItemEffectiveStatus(item) {
    const normalized = normalizePageStatus(item?.effective_status || item?.status);
    return normalized === "init" ? "hidden" : normalized;
  }

  function isMenuItemHidden(item) {
    return getMenuItemEffectiveStatus(item) === "hidden";
  }

  function isMenuItemUnderConstruction(item) {
    return getMenuItemEffectiveStatus(item) === "under_construction";
  }

  function getMenuItemStatusBadge(item) {
    if (isMenuItemUnderConstruction(item)) return "Under Construction";
    if (isMenuItemHidden(item)) return "Hidden";
    return "";
  }

  function getMenuItemStatusClass(item) {
    if (isMenuItemUnderConstruction(item)) return "under-construction";
    if (isMenuItemHidden(item)) return "hidden";
    return "published";
  }

  const normalizedSearchQuery = computed(() => String(unref(searchQuery) || "").trim().toLowerCase());
  const hasSearchQuery = computed(() => normalizedSearchQuery.value.length > 0);

  function matchesQuery(...values) {
    const query = normalizedSearchQuery.value;
    if (!query) return true;
    return values.some((value) => String(value || "").toLowerCase().includes(query));
  }

  function menuItemMatches(item) {
    return matchesQuery(
      getMenuNodeTitle(item),
      getMenuPageTitle(item),
      item?.slug
    );
  }

  function childItemMatches(item) {
    return matchesQuery(
      getMenuPageTitle(item),
      getMenuNodeTitle(item),
      item?.slug
    );
  }

  const filteredMenuTree = computed(() => {
    if (!hasSearchQuery.value) return menuTree.value;

    return menuTree.value
      .map((item) => {
        const children = Array.isArray(item.children) ? item.children : [];
        const parentMatches = menuItemMatches(item);
        const matchingChildren = children.filter((child) => childItemMatches(child));

        if (parentMatches) {
          return { ...item, children, _parentMatches: true };
        }
        if (matchingChildren.length > 0) {
          return { ...item, children: matchingChildren, _parentMatches: false };
        }
        return null;
      })
      .filter(Boolean);
  });

  const filteredExternalMenuLinks = computed(() => {
    if (!hasSearchQuery.value) return externalMenuLinks.value;
    return externalMenuLinks.value.filter((item) =>
      matchesQuery(item.label, item.title, item.href)
    );
  });

  function getPagePath(slug) {
    const basePath = slug === "landing" ? "/" : `/${slug}`;
    const isPublicLikeView = !state.isAdmin || state.previewMode;
    if (!isPublicLikeView || state.lang !== "en") return basePath;
    if (basePath === "/en" || basePath.startsWith("/en/")) return basePath;
    if (basePath === "/") return "/en";
    return `/en${basePath}`;
  }

  async function loadMenuItems() {
    loading.value = true;
    try {
      if (state.previewMode) {
        menuPages.value = await api.getMenuItems({ includeHidden: false });
        return;
      }

      if (!state.isAdmin) {
        const cachedMenu = window.__FSTVLPRESS_PUBLIC_MENU_ITEMS;
        menuPages.value = Array.isArray(cachedMenu) ? cachedMenu : [];
        return;
      }

      menuPages.value = await api.getMenuItems({ includeHidden: state.isAdmin });
    } catch (err) {
      console.error("Failed to load menu items:", err);
      menuPages.value = [];
    } finally {
      loading.value = false;
    }
  }

  function handlePublicMenuUpdate() {
    if (state.isAdmin || state.previewMode) return;
    const cachedMenu = window.__FSTVLPRESS_PUBLIC_MENU_ITEMS;
    if (Array.isArray(cachedMenu)) {
      menuPages.value = cachedMenu;
    }
  }

  watch(() => [state.isAdmin, state.previewMode], () => {
    loadMenuItems();
  });

  onMounted(() => {
    loadMenuItems();
    window.addEventListener("fstvlpress-public-menu-updated", handlePublicMenuUpdate);
  });

  onUnmounted(() => {
    window.removeEventListener("fstvlpress-public-menu-updated", handlePublicMenuUpdate);
  });

  return {
    menuPages,
    menuTree,
    externalMenuLinks,
    filteredMenuTree,
    filteredExternalMenuLinks,
    loading,
    loadMenuItems,
    normalizedSearchQuery,
    hasSearchQuery,
    matchesQuery,
    menuItemMatches,
    childItemMatches,
    getMenuNodeTitle,
    getMenuPageTitle,
    getMenuItemStatusBadge,
    getMenuItemStatusClass,
    getPagePath,
    isMenuItemHidden,
  };
}
