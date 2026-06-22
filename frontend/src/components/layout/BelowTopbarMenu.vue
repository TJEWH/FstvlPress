<template>
  <nav class="below-topbar-menu" :class="{ 'has-submenu-row': hasSubmenuRow }" aria-label="Main menu">
    <div class="container below-topbar-menu__inner">
      <div class="below-topbar-menu__items" :class="{ 'is-loading': loading }">
        <div v-if="loading" class="below-topbar-menu__state">Loading menu...</div>
        <template v-else>
          <template v-for="item in filteredMenuTree" :key="item.slug">
            <div class="below-topbar-menu__item" :class="{ 'has-children': item.children?.length }">
              <button
                v-if="item.children && item.children.length > 0"
                class="below-topbar-menu__link below-topbar-menu__button"
                type="button"
                :class="{ 'not-visible': state.isAdmin && isMenuItemHidden(item) }"
                :aria-expanded="isSubmenuOpen(item)"
                @click="toggleSubmenu(item.slug)"
              >
                <span>{{ getMenuNodeTitle(item) }}</span>
                <span
                  v-if="state.isAdmin && getMenuItemStatusBadge(item)"
                  class="draft-badge"
                  :class="`draft-badge--${getMenuItemStatusClass(item)}`"
                >
                  {{ getMenuItemStatusBadge(item) }}
                </span>
                <font-awesome-icon :icon="faChevronDown" class="below-topbar-menu__chev" :class="{ open: isSubmenuOpen(item) }" />
              </button>
              <a
                v-else
                class="below-topbar-menu__link"
                :href="getPagePath(item.slug)"
                :class="{ 'not-visible': state.isAdmin && isMenuItemHidden(item) }"
                @click.prevent="navigate(getPagePath(item.slug))"
              >
                <span>{{ getMenuPageTitle(item) }}</span>
                <span
                  v-if="state.isAdmin && getMenuItemStatusBadge(item)"
                  class="draft-badge"
                  :class="`draft-badge--${getMenuItemStatusClass(item)}`"
                >
                  {{ getMenuItemStatusBadge(item) }}
                </span>
              </a>

            </div>
          </template>

          <template v-for="item in filteredExternalMenuLinks" :key="item.id">
            <a
              class="below-topbar-menu__link below-topbar-menu__external"
              :href="item.href"
              :title="item.title"
              :aria-label="item.title"
              @click.prevent="navigate(item.href, { external: true })"
            >
              <font-awesome-icon
                v-if="item.icon && item.icon !== 'other'"
                :icon="['fab', resolveBrandIconName(item.icon)]"
                class="below-topbar-menu__link-icon"
              />
              <font-awesome-icon
                v-else-if="item.icon === 'other'"
                :icon="faArrowUpRightFromSquare"
                class="below-topbar-menu__link-icon"
              />
              <span>{{ item.label }}</span>
            </a>
          </template>

          <div
            v-if="filteredMenuTree.length === 0 && filteredExternalMenuLinks.length === 0"
            class="below-topbar-menu__state"
          >
            {{ hasSearchQuery ? "No matching menu items." : "No menu items configured yet." }}
          </div>
        </template>
      </div>

      <label class="below-topbar-menu__search">
        <font-awesome-icon :icon="faMagnifyingGlass" class="below-topbar-menu__search-icon" />
        <input
          v-model="searchQuery"
          type="search"
          placeholder="Search menu"
          aria-label="Search menu items"
          @keydown.esc="searchQuery = ''"
        />
        <button
          v-if="searchQuery"
          type="button"
          class="below-topbar-menu__search-clear"
          aria-label="Clear menu search"
          title="Clear menu search"
          @click="searchQuery = ''"
        >
          <font-awesome-icon :icon="faXmark" />
        </button>
      </label>

      <div v-if="hasSubmenuRow" class="below-topbar-menu__submenu-row" aria-label="Sub menu">
        <template v-for="(group, groupIndex) in activeSubmenuGroups" :key="group.key">
          <span
            v-if="groupIndex > 0"
            class="below-topbar-menu__submenu-separator"
            aria-hidden="true"
          ></span>
          <a
            v-if="group.includeParent"
            class="below-topbar-menu__submenu-link"
            :href="getPagePath(group.item.slug)"
            :class="{ 'not-visible': state.isAdmin && isMenuItemHidden(group.item) }"
            @click.prevent="navigate(getPagePath(group.item.slug))"
          >
            <span>{{ getMenuPageTitle(group.item) }}</span>
            <span
              v-if="state.isAdmin && getMenuItemStatusBadge(group.item)"
              class="draft-badge"
              :class="`draft-badge--${getMenuItemStatusClass(group.item)}`"
            >
              {{ getMenuItemStatusBadge(group.item) }}
            </span>
          </a>
          <a
            v-for="child in group.children"
            :key="`${group.key}:${child.slug}`"
            class="below-topbar-menu__submenu-link"
            :href="getPagePath(child.slug)"
            :class="{ 'not-visible': state.isAdmin && isMenuItemHidden(child) }"
            @click.prevent="navigate(getPagePath(child.slug))"
          >
            <span>{{ getMenuPageTitle(child) }}</span>
            <span
              v-if="state.isAdmin && getMenuItemStatusBadge(child)"
              class="draft-badge"
              :class="`draft-badge--${getMenuItemStatusClass(child)}`"
            >
              {{ getMenuItemStatusBadge(child) }}
            </span>
          </a>
        </template>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  faArrowUpRightFromSquare,
  faChevronDown,
  faMagnifyingGlass,
  faXmark,
} from "@fortawesome/free-solid-svg-icons";
import { useStore } from "../../store/store.js";
import { resolveBrandIconName, useNavigationMenu } from "../../composables/useNavigationMenu.js";

const emit = defineEmits(["submenu-row-change"]);
const router = useRouter();
const { state } = useStore();
const searchQuery = ref("");
const {
  filteredMenuTree,
  filteredExternalMenuLinks,
  loading,
  hasSearchQuery,
  getMenuNodeTitle,
  getMenuPageTitle,
  getMenuItemStatusBadge,
  getMenuItemStatusClass,
  getPagePath,
  isMenuItemHidden,
} = useNavigationMenu({ searchQuery });

const openSubmenu = ref(null);

function isSubmenuOpen(item) {
  if (hasSearchQuery.value && item.children?.length) return true;
  return openSubmenu.value === item.slug;
}

function toggleSubmenu(slug) {
  openSubmenu.value = openSubmenu.value === slug ? null : slug;
}

const activeSubmenuGroups = computed(() => {
  if (hasSearchQuery.value) {
    return filteredMenuTree.value
      .filter((item) => item.children?.length)
      .map((item) => ({
        key: item.slug,
        label: getMenuNodeTitle(item),
        item,
        includeParent: false,
        children: item.children || [],
      }));
  }

  const item = filteredMenuTree.value.find((candidate) =>
    candidate.slug === openSubmenu.value && candidate.children?.length
  );
  if (!item) return [];
  return [{
    key: item.slug,
    label: getMenuNodeTitle(item),
    item,
    includeParent: Boolean(item.hasOwnPage),
    children: item.children || [],
  }];
});

const hasSubmenuRow = computed(() => activeSubmenuGroups.value.length > 0);

function navigate(to, options = {}) {
  const target = String(to || "").trim();
  if (!target) return;
  searchQuery.value = "";
  openSubmenu.value = null;
  if (options.external) {
    window.open(target, "_blank", "noopener,noreferrer");
    return;
  }
  router.push(target);
}

watch(searchQuery, () => {
  if (hasSearchQuery.value) return;
  openSubmenu.value = null;
});

watch(hasSubmenuRow, (visible) => {
  emit("submenu-row-change", visible);
}, { immediate: true });

onBeforeUnmount(() => {
  emit("submenu-row-change", false);
});
</script>

<style scoped>
.below-topbar-menu {
  position: fixed;
  inset: 64px 0 auto 0;
  height: var(--below-topbar-nav-height, 58px);
  z-index: 49;
  background: var(--sidebar-bg-color, rgba(255,255,255,0.96));
  color: var(--sidebar-item-color, #111827);
  border-top: 1px solid color-mix(in srgb, var(--sidebar-item-color, #111827) 12%, transparent);
  border-bottom: 1px solid color-mix(in srgb, var(--sidebar-item-color, #111827) 16%, transparent);
  box-shadow: 0 10px 24px rgba(17, 24, 39, 0.06);
}

.below-topbar-menu__inner {
  height: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(180px, 260px);
  grid-template-areas: "items search";
  align-items: center;
  gap: 12px;
}

.below-topbar-menu.has-submenu-row .below-topbar-menu__inner {
  grid-template-rows: 58px 40px;
  grid-template-areas:
    "items search"
    "submenu submenu";
  gap: 0 12px;
}

.below-topbar-menu__items {
  grid-area: items;
  min-width: 0;
  height: 100%;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  overflow-y: visible;
  scrollbar-width: thin;
}

.below-topbar-menu__items.is-loading {
  overflow: hidden;
}

.below-topbar-menu__item {
  position: relative;
  flex: 0 0 auto;
}

.below-topbar-menu__link {
  height: 38px;
  border: 0;
  border-radius: 8px;
  background: var(--sidebar-item-bg-color, transparent);
  color: var(--sidebar-item-color, #111827);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
  text-decoration: none;
  white-space: nowrap;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}

.below-topbar-menu__link:hover,
.below-topbar-menu__button[aria-expanded="true"] {
  color: var(--sidebar-item-hover-color, var(--accent, #4f46e5));
  background: var(--sidebar-item-hover-bg-color, transparent);
}

.below-topbar-menu__chev {
  width: 10px;
  font-size: 11px;
  transition: transform 160ms ease;
  opacity: 0.7;
}

.below-topbar-menu__chev.open {
  transform: rotate(180deg);
}

.below-topbar-menu__submenu-row {
  grid-area: submenu;
  min-width: 0;
  height: 40px;
  border-top: 1px solid color-mix(in srgb, var(--sidebar-item-color, #111827) 12%, transparent);
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
}

.below-topbar-menu__submenu-separator {
  flex: 0 0 auto;
  width: 1px;
  height: 22px;
  margin: 0 5px;
  background: color-mix(in srgb, var(--sidebar-item-color, #111827) 18%, transparent);
}

.below-topbar-menu__submenu-link {
  min-height: 30px;
  border-radius: 8px;
  padding: 6px 10px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--sidebar-item-bg-color, transparent);
  color: var(--sidebar-item-color, #111827);
  font-size: 13px;
  font-weight: 650;
  text-decoration: none;
  white-space: nowrap;
  transition: color 0.15s, background 0.15s;
}

.below-topbar-menu__submenu-link:hover {
  color: var(--sidebar-item-hover-color, var(--accent, #4f46e5));
  background: var(--sidebar-item-hover-bg-color, transparent);
}

.below-topbar-menu__submenu-link > span:first-child {
  overflow: hidden;
  text-overflow: ellipsis;
}

.below-topbar-menu__external {
  font-weight: 650;
}

.below-topbar-menu__link-icon {
  flex: 0 0 auto;
  font-size: 0.95rem;
}

.below-topbar-menu__search {
  grid-area: search;
  min-width: 0;
  height: 36px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px 0 10px;
  border: 1px solid color-mix(in srgb, var(--sidebar-item-color, #111827) 16%, transparent);
  border-radius: 8px;
  background: color-mix(in srgb, var(--sidebar-bg-color, #ffffff) 88%, #ffffff);
  color: color-mix(in srgb, var(--sidebar-item-color, #111827) 55%, transparent);
}

.below-topbar-menu__search input {
  min-width: 0;
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--sidebar-item-color, #111827);
  font: inherit;
  font-size: 13px;
  font-weight: 600;
}

.below-topbar-menu__search input::placeholder {
  color: color-mix(in srgb, var(--sidebar-item-color, #111827) 45%, transparent);
}

.below-topbar-menu__search-icon {
  flex: 0 0 auto;
  font-size: 12px;
}

.below-topbar-menu__search-clear {
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: color-mix(in srgb, var(--sidebar-item-color, #111827) 55%, transparent);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.below-topbar-menu__search-clear:hover {
  color: var(--sidebar-item-hover-color, var(--accent, #4f46e5));
  background: var(--sidebar-item-hover-bg-color, transparent);
}

.below-topbar-menu__state {
  flex: 0 0 auto;
  padding: 0 10px;
  color: color-mix(in srgb, var(--sidebar-item-color, #111827) 55%, transparent);
  font-size: 13px;
  font-weight: 650;
}

.not-visible {
  opacity: 0.5;
}

.draft-badge {
  display: inline-block;
  flex: 0 0 auto;
  font-size: 9px;
  padding: 2px 5px;
  background: #fef3c7;
  color: #92400e;
  border-radius: 4px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0;
}

.draft-badge--under-construction {
  background: #ffedd5;
  color: #9a3412;
}

@media (max-width: 767px) {
  .below-topbar-menu {
    height: var(--below-topbar-nav-height, 104px);
  }

  .below-topbar-menu__inner {
    grid-template-columns: 1fr;
    grid-template-rows: 46px 40px;
    grid-template-areas:
      "items"
      "search";
    align-content: center;
    gap: 6px;
    padding-top: 6px;
    padding-bottom: 6px;
  }

  .below-topbar-menu__items {
    height: 46px;
  }

  .below-topbar-menu__search {
    height: 38px;
  }

  .below-topbar-menu.has-submenu-row .below-topbar-menu__inner {
    grid-template-rows: 42px 38px 48px;
    grid-template-areas:
      "items"
      "search"
      "submenu";
    gap: 4px;
  }

  .below-topbar-menu__submenu-row {
    height: 48px;
  }

  .below-topbar-menu__link {
    max-width: 72vw;
  }
}
</style>
