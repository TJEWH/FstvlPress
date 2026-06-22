<template>
  <Transition name="overlay">
    <div v-if="open" class="overlay" @click="$emit('close')" />
  </Transition>

  <Transition name="sidebar">
    <aside v-if="open" class="sidebar" aria-label="Sidebar">
      <div class="sidebar-header">
        <div class="title">Menu</div>
        <button class="icon-btn" @click="$emit('close')" :aria-label="t.close">
          <font-awesome-icon :icon="faXmark" />
        </button>
      </div>

      <label class="sidebar-search">
        <font-awesome-icon :icon="faMagnifyingGlass" class="sidebar-search-icon" />
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
          class="sidebar-search-clear"
          aria-label="Clear menu search"
          title="Clear menu search"
          @click="searchQuery = ''"
        >
          <font-awesome-icon :icon="faXmark" />
        </button>
      </label>

      <nav class="nav">
        <div v-if="loading" class="loading">Loading menu...</div>
        <ul v-else class="list">
          <template v-for="(item, idx) in filteredMenuTree" :key="item.slug">
            <li class="item">
              <!-- Item with children -->
              <template v-if="item.children && item.children.length > 0">
                <button
                  class="row"
                  type="button"
                  :aria-expanded="isGroupOpen(item)"
                  @click="toggle(item.slug)"
                  :class="{ 'not-visible': state.isAdmin && isMenuItemHidden(item) }"
                >
                  <span>{{ getMenuNodeTitle(item) }}</span>
                  <span v-if="state.isAdmin && getMenuItemStatusBadge(item)" class="draft-badge" :class="`draft-badge--${getMenuItemStatusClass(item)}`">
                    {{ getMenuItemStatusBadge(item) }}
                  </span>
                  <span class="chev" :class="{ open: isGroupOpen(item) }">▾</span>
                </button>
                <Transition name="collapse">
                  <ul v-if="isGroupOpen(item)" class="sub">
                    <!-- Parent page link if it has content -->
                    <li class="sublink" v-if="item.hasOwnPage && (!hasSearchQuery || item._parentMatches)">
                      <a
                        class="sublink-link"
                        :href="getPagePath(item.slug)"
                        @click.prevent="navigate(getPagePath(item.slug))"
                        :class="{ 'not-visible': state.isAdmin && isMenuItemHidden(item) }"
                      >
                        {{ getMenuPageTitle(item) }}
                        <span v-if="state.isAdmin && getMenuItemStatusBadge(item)" class="draft-badge" :class="`draft-badge--${getMenuItemStatusClass(item)}`">
                          {{ getMenuItemStatusBadge(item) }}
                        </span>
                      </a>
                    </li>
                    <!-- Child pages -->
                    <li class="sublink" v-for="child in item.children" :key="child.slug">
                      <a
                        class="sublink-link"
                        :href="getPagePath(child.slug)"
                        @click.prevent="navigate(getPagePath(child.slug))"
                        :class="{ 'not-visible': state.isAdmin && isMenuItemHidden(child) }"
                      >
                        {{ getMenuPageTitle(child) }}
                        <span v-if="state.isAdmin && getMenuItemStatusBadge(child)" class="draft-badge" :class="`draft-badge--${getMenuItemStatusClass(child)}`">
                          {{ getMenuItemStatusBadge(child) }}
                        </span>
                      </a>
                    </li>
                  </ul>
                </Transition>
              </template>
              <!-- Item without children -->
              <template v-else>
                <a
                  class="link"
                  :href="getPagePath(item.slug)"
                  @click.prevent="navigate(getPagePath(item.slug))"
                  :class="{ 'not-visible': state.isAdmin && isMenuItemHidden(item) }"
                >
                  {{ getMenuPageTitle(item) }}
                  <span v-if="state.isAdmin && getMenuItemStatusBadge(item)" class="draft-badge" :class="`draft-badge--${getMenuItemStatusClass(item)}`">
                    {{ getMenuItemStatusBadge(item) }}
                  </span>
                </a>
              </template>
            </li>
            <li v-if="idx < filteredMenuTree.length - 1" class="divider"></li>
          </template>

          <li v-if="filteredMenuTree.length > 0 && filteredExternalMenuLinks.length > 0" class="divider"></li>
          <template v-for="(item, idx) in filteredExternalMenuLinks" :key="item.id">
            <li class="item">
              <a
                class="link"
                :href="item.href"
                :title="item.title"
                :aria-label="item.title"
                @click.prevent="navigate(item.href, { external: true })"
              >
                <font-awesome-icon
                  v-if="item.icon && item.icon !== 'other'"
                  :icon="['fab', resolveBrandIconName(item.icon)]"
                  class="link-icon"
                />
                <font-awesome-icon
                  v-else-if="item.icon === 'other'"
                  :icon="faArrowUpRightFromSquare"
                  class="link-icon"
                />
                <span>{{ item.label }}</span>
              </a>
            </li>
            <li v-if="idx < filteredExternalMenuLinks.length - 1" class="divider"></li>
          </template>
          
          <!-- Empty state -->
          <li v-if="filteredMenuTree.length === 0 && filteredExternalMenuLinks.length === 0 && !loading" class="empty">
            {{ hasSearchQuery ? "No matching menu items." : "No menu items configured yet." }}
          </li>
        </ul>
      </nav>

      <div v-if="state.isAdmin" class="sidebar-footer">
        <div class="admin-btns">
          <button class="admin-btn admin-btn-primary" @click="navigate('/admin/sitemap/pages')">
            <font-awesome-icon :icon="faGear" />
            Pages
          </button>
        </div>

        <!--div class="hint">Manage pages in Admin → Sitemap</div-->
      </div>
    </aside>
  </Transition>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRouter } from "vue-router";
import { faArrowUpRightFromSquare, faGear, faMagnifyingGlass, faXmark } from "@fortawesome/free-solid-svg-icons";
import { useStore } from "../../store/store.js";
import { resolveBrandIconName, useNavigationMenu } from "../../composables/useNavigationMenu.js";

const props = defineProps({ open: { type: Boolean, default: false } });
const emit = defineEmits(["close"]);

const router = useRouter();
const { state, t } = useStore();

const openGroup = ref(null);
const searchQuery = ref("");
const {
  filteredMenuTree,
  filteredExternalMenuLinks,
  loading,
  loadMenuItems,
  hasSearchQuery,
  getMenuNodeTitle,
  getMenuPageTitle,
  getMenuItemStatusBadge,
  getMenuItemStatusClass,
  getPagePath,
  isMenuItemHidden,
} = useNavigationMenu({ searchQuery });

function toggle(group) {
  openGroup.value = openGroup.value === group ? null : group;
}

function isGroupOpen(item) {
  if (hasSearchQuery.value && item.children?.length) return true;
  return openGroup.value === item.slug;
}

function navigate(to, options = {}) {
  const target = String(to || '').trim();
  if (!target) return;
  searchQuery.value = "";
  openGroup.value = null;
  if (options.external) {
    window.open(target, '_blank', 'noopener,noreferrer');
    emit("close");
    return;
  }
  router.push(target);
  emit("close");
}

// Load menu items when sidebar opens (always refresh to ensure latest data)
watch(() => props.open, (isOpen) => {
  if (isOpen) {
    loadMenuItems();
  } else {
    searchQuery.value = "";
    openGroup.value = null;
  }
});

watch(searchQuery, () => {
  if (hasSearchQuery.value) return;
  openGroup.value = null;
});
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(17,24,39,0.30);
  z-index: 60;
}

.sidebar {
  position: fixed;
  top: 0;
  right: 0;
  height: 100vh;
  width: min(360px, 92vw);
  z-index: 70;
  background: var(--sidebar-bg-color, rgba(255,255,255,0.96));
  box-shadow: -10px 0 30px rgba(17,24,39,0.10);
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 14px 14px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  font-weight: 800;
}

.nav {
  padding: 8px 14px;
  overflow: auto;
  flex: 1;
}

.sidebar-search {
  margin: 0 14px 8px;
  height: 38px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px 0 10px;
  border: 1px solid color-mix(in srgb, var(--sidebar-item-color, #111827) 16%, transparent);
  border-radius: 8px;
  background: color-mix(in srgb, var(--sidebar-bg-color, #ffffff) 88%, #ffffff);
  color: color-mix(in srgb, var(--sidebar-item-color, #111827) 55%, transparent);
}

.sidebar-search input {
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

.sidebar-search input::placeholder {
  color: color-mix(in srgb, var(--sidebar-item-color, #111827) 45%, transparent);
}

.sidebar-search-icon {
  flex: 0 0 auto;
  font-size: 12px;
}

.sidebar-search-clear {
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

.sidebar-search-clear:hover {
  color: var(--sidebar-item-hover-color, var(--accent));
  background: var(--sidebar-item-hover-bg-color, transparent);
}

.loading, .empty {
  padding: 20px 0;
  text-align: center;
  color: color-mix(in srgb, var(--sidebar-item-color, #111827) 55%, transparent);
  font-size: 14px;
}

.list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.item { padding: 6px 0; }

.divider {
  height: 1px;
  background: color-mix(in srgb, var(--sidebar-item-color, #111827) 12%, transparent);
  margin: 8px 0;
}

.link, .row {
  width: 100%;
  padding: 10px 0;
  border: 0;
  background: var(--sidebar-item-bg-color, transparent);
  cursor: pointer;
  text-align: left;
  font-weight: 650;
  color: var(--sidebar-item-color, #111827);
  border-radius: 8px;
  padding-left: 10px;
  padding-right: 10px;
}
.link {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
}

.link-icon {
  font-size: 1rem;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.chev {
  width: 20px;
  text-align: center;
  transition: transform 160ms ease;
  color: color-mix(in srgb, var(--sidebar-item-color, #111827) 55%, transparent);
}
.chev.open { transform: rotate(180deg); }

.sub {
  list-style: none;
  padding: 6px 0 0 10px;
  margin: 0;
  display: grid;
  gap: 6px;
}

.sublink {
  list-style: none;
}
.sublink-link {
  width: 100%;
  border: 0;
  background: var(--sidebar-item-bg-color, transparent);
  cursor: pointer;
  text-align: left;
  padding: 8px 10px;
  border-radius: 8px;
  color: var(--sidebar-item-color, #111827);
  font-weight: 550;
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
}
.sublink-link:hover, .link:hover, .row:hover {
  color: var(--sidebar-item-hover-color, var(--accent));
  background: var(--sidebar-item-hover-bg-color, transparent);
}

/* Not visible items (admin preview) */
.not-visible {
  opacity: 0.5;
}
.draft-badge {
  display: inline-block;
  font-size: 10px;
  padding: 2px 6px;
  background: #fef3c7;
  color: #92400e;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-left: auto;
}
.draft-badge--under-construction {
  background: #ffedd5;
  color: #9a3412;
}
.row .draft-badge {
  margin-right: 8px;
}

.sidebar-footer {
  padding: 12px 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.admin-btns {
  display: flex;
  gap: 8px;
}

.admin-btn {
  flex: 1;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: background 0.15s ease, transform 0.1s ease;
}
.admin-btn:active {
  transform: scale(0.98);
}
.admin-btn.secondary {
  background: #f1f5f9;
  color: #0f172a;
}
.admin-btn.secondary:hover {
  background: #e2e8f0;
}
.admin-btn.primary {
  background: #0f172a;
  color: #fff;
}
.admin-btn.primary:hover {
  background: #1e293b;
}

.hint {
  font-size: 12px;
  color: rgba(17,24,39,0.55);
  line-height: 1.4;
  text-align: center;
}

/* Transitions */
.overlay-enter-active, .overlay-leave-active { transition: opacity 220ms ease; }
.overlay-enter-from, .overlay-leave-to { opacity: 0; }

.sidebar-enter-active, .sidebar-leave-active {
  transition: transform 260ms cubic-bezier(.2,.8,.2,1), opacity 260ms ease;
}
.sidebar-enter-from, .sidebar-leave-to {
  transform: translateX(14px);
  opacity: 0;
}

.collapse-enter-active, .collapse-leave-active { transition: all 180ms ease; }
.collapse-enter-from, .collapse-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
