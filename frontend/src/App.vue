<template>
  <div v-if="isAdminRoute" class="admin-shell" :class="adminShellClasses">
    <router-view />
  </div>
  <div v-else class="app-shell" :class="appShellClasses" :style="appShellStyle">
    <HeaderBar
        :sidebar-open="sidebarOpen"
        :preview-mode="state.previewMode"
        :hide-menu-toggle="belowTopbarMenuActive"
        @toggle-sidebar="toggleSidebar"
        @toggle-preview="togglePreview"
        @logout="doLogout"
    />

    <BelowTopbarMenu
        v-if="belowTopbarMenuActive"
        @submenu-row-change="belowTopbarSubmenuVisible = $event"
    />

    <SidebarMenu :open="sidebarOpen" @close="closeSidebar" />

    <main class="content">
      <router-view />
      
      <!-- Admin-only panels (components guard themselves with v-if="state.isAdmin") -->
      <DesignPanel />
    </main>

    <FooterBar />

    <!-- Preview mode banner -->
    <div v-if="state.previewMode" class="preview-banner" @click="togglePreview">
      <span>Preview Mode</span>
      <span class="preview-exit">Click to exit</span>
    </div>
  </div>

  <AdminTutorialOverlay v-if="authState.authenticated && state.canContent" />

  <!-- Always mounted so it's available during route transitions -->
  <UnsavedChangesDialog ref="unsavedDialogRef" />
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import { useStore } from "./store/store.js";
import { useAuth } from "./services/auth.js";
import { startServerClockSync, stopServerClockSync } from "./utils/revisionTime.js";
import { getResponsivePreviewSize } from "./utils/responsiveViewport.js";

import HeaderBar from "./components/layout/HeaderBar.vue";
import BelowTopbarMenu from "./components/layout/BelowTopbarMenu.vue";
import SidebarMenu from "./components/layout/SidebarMenu.vue";
import FooterBar from "./components/layout/FooterBar.vue";
import DesignPanel from "./components/admin/panels/DesignPanel.vue";
import AdminTutorialOverlay from "./components/admin/AdminTutorialOverlay.vue";
import UnsavedChangesDialog from "./components/admin/UnsavedChangesDialog.vue";

const route = useRoute();
const { state, loadDesignSettings, loadAdminDesignConfig, registerUnsavedChangesDialog, updateViewportSize, setLang } = useStore();

const unsavedDialogRef = ref(null);
const { state: authState, initAuth, logout, getInternalRole, getCapabilities } = useAuth();

const sidebarOpen = ref(false);
const isAdminRoute = computed(() => route.path.startsWith('/admin'));
const simulatedPreviewDevice = computed(() => (
  state.simulatedViewport === 'mobile' || state.simulatedViewport === 'tablet'
    ? state.simulatedViewport
    : null
));

const appShellClasses = computed(() => ({
  'full-width': state.design.fullWidth,
  'viewport-sim': !!simulatedPreviewDevice.value,
  'admin-view': state.isAdmin,
  'with-below-topbar-menu': belowTopbarMenuActive.value,
  'with-below-topbar-submenu': belowTopbarSubmenuVisible.value,
}));

const adminShellClasses = computed(() => ({
  'admin-view': state.isAdmin,
}));

const appShellStyle = computed(() => {
  const previewSize = getResponsivePreviewSize(state.adminDesignConfig?.responsive, simulatedPreviewDevice.value);
  if (!previewSize?.width) return {};
  return { maxWidth: `${previewSize.width}px`, margin: '0 auto' };
});

const belowTopbarMenuActive = computed(() => state.design.navigationMenuView === "below_topbar");
const belowTopbarSubmenuVisible = ref(false);

let designHydrationPromise = null;
let designHydrationQueued = false;

async function syncAdminStateAndHydrateDesign() {
  syncAdminState();

  // Content editors also need current global design settings for accurate page editing.
  if (!state.canContent) {
    designHydrationQueued = false;
    return;
  }

  designHydrationQueued = true;
  if (designHydrationPromise) {
    await designHydrationPromise;
    return;
  }

  designHydrationPromise = (async () => {
    while (designHydrationQueued) {
      designHydrationQueued = false;
      await loadDesignSettings();
      if (state.canAdminDesign) {
        await loadAdminDesignConfig();
      }
    }
  })();

  try {
    await designHydrationPromise;
  } finally {
    designHydrationPromise = null;
  }
}

// Initialize app
onMounted(async () => {
  // Initialize auth first so we can avoid private API calls for public visitors.
  await initAuth();
  await syncAdminStateAndHydrateDesign();
  void startServerClockSync();

  registerUnsavedChangesDialog((groups) => unsavedDialogRef.value?.show(groups));
});

// Watch auth state changes and sync admin status
watch(
  () => [
    authState.authenticated,
    authState.internalRole,
    authState.capabilities?.can_content,
    authState.capabilities?.can_design,
    authState.capabilities?.can_admin_design,
    authState.capabilities?.can_admin_general,
  ],
  () => {
    void syncAdminStateAndHydrateDesign();
  },
  { immediate: true }
);

watch(
  [() => route.path, () => authState.authenticated],
  ([path, authenticated]) => {
    if (authenticated || path.startsWith("/admin")) return;
    const isEnglishPath = path === "/en" || path.startsWith("/en/");
    setLang(isEnglishPath ? "en" : "de");
  },
  { immediate: true }
);

watch(
  () => state.lang,
  (lang) => {
    if (typeof document === "undefined") return;
    document.documentElement.setAttribute("lang", lang === "en" ? "en" : "de");
  },
  { immediate: true }
);

/**
 * Sync isAdmin based on current auth state and role/group requirements.
 * Uses backend-configured KEYCLOAK_ADMIN_ROLES / KEYCLOAK_ADMIN_GROUPS.
 * If neither is set, any authenticated user gets admin rights.
 */
function syncAdminState() {
  const internalRole = getInternalRole();
  const capabilities = getCapabilities();
  state.internalRole = internalRole;
  state.canContent = Boolean(capabilities.can_content);
  state.canDesign = Boolean(capabilities.can_design);
  state.canAdminDesign = Boolean(capabilities.can_admin_design);
  state.canAdminGeneral = Boolean(capabilities.can_admin_general);
  state.isAdmin = Boolean(capabilities.can_content);
  state.previewMode = false;
}

function togglePreview() {
  if (state.previewMode) {
    state.previewMode = false;
    syncAdminState();
  } else {
    state.previewMode = true;
    state.isAdmin = false;
  }
}

function doLogout() {
  state.isAdmin = false;
  state.previewMode = false;
  logout(window.location.origin);
}

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value;
}
function closeSidebar() {
  sidebarOpen.value = false;
}

function onBeforeUnload(e) {
  if (state.designDirty) {
    e.preventDefault();
    e.returnValue = '';
  }
}

function handleViewportResize() {
  updateViewportSize(window.innerWidth, window.innerHeight);
}

onMounted(() => {
  handleViewportResize();
  window.addEventListener('resize', handleViewportResize);
  window.addEventListener('orientationchange', handleViewportResize);
});

onMounted(() => window.addEventListener('beforeunload', onBeforeUnload));
onBeforeUnmount(() => {
  stopServerClockSync();
  window.removeEventListener('beforeunload', onBeforeUnload);
  window.removeEventListener('resize', handleViewportResize);
  window.removeEventListener('orientationchange', handleViewportResize);
});

function onKeydown(e) {
  if (e.key === "Escape") closeSidebar();
}
watch(sidebarOpen, (open) => {
  if (open) window.addEventListener("keydown", onKeydown);
  else window.removeEventListener("keydown", onKeydown);
});

watch(belowTopbarMenuActive, (active) => {
  if (active) closeSidebar();
  else belowTopbarSubmenuVisible.value = false;
});
</script>

<style scoped>
.admin-shell {
  min-height: 100vh;
}

.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.content {
  flex: 1;
  padding-top: calc(64px + var(--below-topbar-nav-offset, 0px)); /* header height + optional nav strip */
  overflow: hidden;
}

.app-shell.with-below-topbar-menu {
  --below-topbar-nav-height: 58px;
  --below-topbar-nav-offset: var(--below-topbar-nav-height);
}

.app-shell.with-below-topbar-menu.with-below-topbar-submenu {
  --below-topbar-nav-height: 98px;
}

.app-shell.viewport-sim {
  box-shadow: 0 0 0 1px rgba(79, 70, 229, 0.3), 0 0 40px rgba(79, 70, 229, 0.08);
  overflow-x: hidden;
  transition: max-width 0.3s ease;
}

/* Preview Mode Banner */
.preview-banner {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 10px 20px;
  background: var(--accent, #4f46e5);
  color: #fff;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.preview-banner:hover {
  opacity: 0.92;
}

.preview-exit {
  font-weight: 400;
  opacity: 0.8;
  font-size: 12px;
}

@media (max-width: 767px) {
  .app-shell.with-below-topbar-menu {
    --below-topbar-nav-height: 104px;
  }

  .app-shell.with-below-topbar-menu.with-below-topbar-submenu {
    --below-topbar-nav-height: 148px;
  }
}

</style>
