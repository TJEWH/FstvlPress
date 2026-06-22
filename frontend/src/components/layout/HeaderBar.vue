<template>
  <header class="header">
    <div class="container header-inner">
      <div class="brand" @click="goHome" role="button" tabindex="0">
        <ResponsiveImage
          v-if="resolvedLogo"
          class="brand-logo"
          :src="resolvedLogo"
          :image-data="topbarLogoImageData"
          :style="topbarLogoStyle"
          :slot-width="110"
          :alt="appDisplayLogoAlt"
          loading="eager"
          fetchpriority="high"
          decoding="async"
        />
        <div class="brand-text">
          <div class="logo-text">{{ appDisplayName }}</div>
        </div>
      </div>

      <div class="actions">
        <div id="tutorial-launcher-slot" class="tutorial-launcher-slot" />

        <!-- Preview toggle (visible when admin or in preview mode) -->
        <button
            v-if="state.isAdmin || previewMode"
            class="preview-btn"
            :class="{ active: previewMode }"
            type="button"
            @click="$emit('toggle-preview')"
            :title="previewMode ? 'Exit preview' : 'Preview as visitor'"
            :aria-label="previewMode ? 'Exit preview' : 'Preview as visitor'"
        >
          <font-awesome-icon :icon="previewMode ? faEyeSlash : faEye" />
        </button>

        <!-- Viewport simulation controls (visible when admin or in preview mode) -->
        <template v-if="state.isAdmin || previewMode">
          <span class="divider sim-divider" />
          <button
              class="sim-btn sim-btn-mobile"
              :class="{ active: state.simulatedViewport === 'mobile' }"
              type="button"
              @click="toggleViewportSim('mobile')"
              :title="viewportSimTitle('mobile')"
          >
            <font-awesome-icon :icon="faMobileScreenButton" />
          </button>
          <button
              class="sim-btn sim-btn-tablet"
              :class="{ active: state.simulatedViewport === 'tablet' }"
              type="button"
              @click="toggleViewportSim('tablet')"
              :title="viewportSimTitle('tablet')"
          >
            <font-awesome-icon :icon="faTabletScreenButton" />
          </button>
          <span class="divider sim-divider" />
        </template>

        <div
            v-if="showPageStatusControl"
            class="page-status-control"
        >
          <label class="page-status-control__label" for="topbar-page-status">Page</label>
          <select
              id="topbar-page-status"
              class="page-status-control__select"
              :value="selectedPageStatus"
              :disabled="pageStatusSaving"
              :title="pageStatusSelectTitle"
              aria-label="Change current page status"
              @change="handlePageStatusChange"
          >
            <option
                v-for="option in pageStatusOptions"
                :key="option.value"
                :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </div>

        <a
            v-if="authState.authenticated && state.canAdminGeneral"
            class="admin-link-btn"
            href="/admin/devops/changelog"
            @click.prevent="goAdminDevops"
            title="Open Admin DevOps"
            aria-label="Open Admin DevOps"
        >
          Admin
        </a>

        <!-- Login button (only visible when not authenticated) -->
        <button
            v-if="!authState.authenticated"
            class="login-btn"
            type="button"
            @click="handleLogin"
            title="Login"
            aria-label="Login"
        >
          <font-awesome-icon :icon="faRightToBracket" />
        </button>

        <!-- Logout button (visible when authenticated) -->
        <button
            v-if="authState.authenticated"
            class="logout-btn"
            type="button"
            @click="$emit('logout')"
            title="Logout"
            aria-label="Logout"
        >
          <font-awesome-icon :icon="faRightFromBracket" />
        </button>
        
        <LanguageSwitch />
        <button
            v-if="!hideMenuToggle"
            class="icon-btn burger-btn"
            type="button"
            @click="$emit('toggle-sidebar')"
            :aria-expanded="sidebarOpen"
            aria-label="Menü öffnen"
        >
          <span class="burger" :class="{ open: sidebarOpen }" aria-hidden="true">
            <span class="line l1" />
            <span class="line l2" />
            <span class="line l3" />
          </span>
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import {
  faEye,
  faEyeSlash,
  faMobileScreenButton,
  faRightFromBracket,
  faRightToBracket,
  faTabletScreenButton,
} from "@fortawesome/free-solid-svg-icons";
import { useRouter } from "vue-router";
import { useStore } from "../../store/store.js";
import { useAuth } from "../../services/auth.js";
import * as api from "../../services/api.js";
import { getResponsivePreviewSize } from "../../utils/responsiveViewport.js";
import LanguageSwitch from "../ui/LanguageSwitch.vue";
import ResponsiveImage from "../ui/ResponsiveImage.vue";
import { isVectorOrPngImageUrl } from "../../utils/imageFormat.js";
import { getAppDisplayName } from "../../utils/appConfig.js";

const { state, setSimulatedViewport, updateCurrentPageStatus } = useStore();
const { state: authState, login } = useAuth();
const appDisplayName = computed(() => getAppDisplayName());
const appDisplayLogoAlt = computed(() => `${appDisplayName.value} Logo`);
const topbarLogoUrl = ref(null);
const topbarLogoResponsiveVariants = ref([]);

function normalizeTopbarLogoUrl(value) {
  const normalized = String(value || "").trim();
  return normalized || null;
}

function normalizeTopbarLogoResponsiveVariants(value) {
  if (!Array.isArray(value)) return [];
  return value.filter((entry) => entry && typeof entry === "object" && !Array.isArray(entry));
}

function applyTopbarLogoPayload(payload) {
  topbarLogoUrl.value = normalizeTopbarLogoUrl(payload?.topbar_logo_url);
  topbarLogoResponsiveVariants.value = normalizeTopbarLogoResponsiveVariants(payload?.topbar_logo_responsive_variants);
}

function applyPublicTopbarLogoPayload() {
  applyTopbarLogoPayload({
    topbar_logo_url: window.__SSC_PUBLIC_TOPBAR_LOGO_URL,
    topbar_logo_responsive_variants: window.__SSC_PUBLIC_TOPBAR_LOGO_RESPONSIVE_VARIANTS,
  });
}

async function loadTopbarLogo() {
  try {
    const usePublicCache = !state.isAdmin && !state.previewMode;
    if (usePublicCache) {
      applyPublicTopbarLogoPayload();
      return;
    }

    const navigationConfig = await api.getSitemapNavigationLinks();
    applyTopbarLogoPayload(navigationConfig);
  } catch (err) {
    console.error("Failed to load topbar logo:", err);
    applyTopbarLogoPayload({});
  }
}

function handlePublicTopbarUpdate() {
  if (state.isAdmin || state.previewMode) return;
  applyPublicTopbarLogoPayload();
}

const resolvedLogo = computed(() => topbarLogoUrl.value);
const topbarLogoImageData = computed(() => ({
  imageUrl: String(resolvedLogo.value || "").trim(),
  responsiveVariants: normalizeTopbarLogoResponsiveVariants(topbarLogoResponsiveVariants.value),
}));

const topbarLogoStyle = computed(() => ({
  filter: isVectorOrPngImageUrl(resolvedLogo.value)
    ? "var(--topbar-logo-filter, none)"
    : "none",
}));
const pageStatusSaving = ref(false);
const pageStatusError = ref("");
const BASE_PAGE_STATUS_OPTIONS = Object.freeze([
  { value: "hidden", label: "Hidden" },
  { value: "under_construction", label: "Under Construction" },
  { value: "published", label: "Public" },
]);
const INIT_PAGE_STATUS_OPTION = Object.freeze({ value: "init", label: "Init (new)" });

defineProps({
  sidebarOpen: { type: Boolean, default: false },
  previewMode: { type: Boolean, default: false },
  hideMenuToggle: { type: Boolean, default: false }
});
defineEmits(["toggle-sidebar", "logout", "toggle-preview"]);

const router = useRouter();
const goHome = () => router.push("/");
const goAdminDevops = () => router.push("/admin/devops/changelog");

watch(() => [state.isAdmin, state.previewMode], () => {
  void loadTopbarLogo();
});

onMounted(() => {
  void loadTopbarLogo();
  window.addEventListener("fstvlpress-public-topbar-updated", handlePublicTopbarUpdate);
});

onUnmounted(() => {
  window.removeEventListener("fstvlpress-public-topbar-updated", handlePublicTopbarUpdate);
});

const showPageStatusControl = computed(() => {
  return state.isAdmin && Boolean(state.pageSlug) && Boolean(state.currentPageStatus);
});

const selectedPageStatus = computed(() => {
  return normalizePageStatusValue(state.currentPageStatus) || "hidden";
});

const pageStatusOptions = computed(() => {
  return selectedPageStatus.value === "init"
    ? [INIT_PAGE_STATUS_OPTION, ...BASE_PAGE_STATUS_OPTIONS]
    : BASE_PAGE_STATUS_OPTIONS;
});

const pageStatusSelectTitle = computed(() => {
  if (pageStatusError.value) return pageStatusError.value;
  if (pageStatusSaving.value) return "Saving page status...";
  return "Change current page status";
});

async function handleLogin() {
  await login(window.location.href);
}

function normalizePageStatusValue(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (raw === "public") return "published";
  if (raw === "init" || raw === "hidden" || raw === "under_construction" || raw === "published") return raw;
  return null;
}

async function handlePageStatusChange(event) {
  const target = event?.target;
  const previousStatus = selectedPageStatus.value;
  const nextStatus = normalizePageStatusValue(target?.value);
  if (!nextStatus || nextStatus === previousStatus) {
    if (target) target.value = previousStatus;
    return;
  }

  pageStatusSaving.value = true;
  pageStatusError.value = "";
  try {
    await updateCurrentPageStatus(nextStatus);
  } catch (err) {
    console.error("Failed to update page status:", err);
    pageStatusError.value = err?.message || "Failed to update page status";
    if (target) target.value = previousStatus;
  } finally {
    pageStatusSaving.value = false;
  }
}

function toggleViewportSim(device) {
  if (state.simulatedViewport === device) {
    setSimulatedViewport(null);
  } else {
    setSimulatedViewport(device);
  }
}

function viewportSimTitle(device) {
  const size = getResponsivePreviewSize(state.adminDesignConfig?.responsive, device);
  const label = device.charAt(0).toUpperCase() + device.slice(1);
  return size?.width ? `Simulate ${device} viewport (${size.width}px)` : `Simulate ${label} viewport`;
}
</script>

<style scoped>
.header {
  position: fixed;
  inset: 0 0 auto 0;
  height: 64px;
  z-index: 50;
  background: var(--topbar-bg-color, var(--section-background-color, #ffffff));
  backdrop-filter: blur(8px);
  box-shadow: 0 6px 20px rgba(17, 24, 39, 0.08);
  color: var(--topbar-text-color, var(--text));
}

.header-inner {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  user-select: none;
  color: var(--topbar-item-color, var(--topbar-text-color, var(--text)));
}

.brand-logo {
  width: 110px;
  height: 38px;
  object-fit: contain;
  display: block;
  filter: none;
  /* kein Border */
}

.logo-text {
  font-family: var(--header-font-family);
  font-weight: var(--header-font-weight);
  letter-spacing: var(--header-letter-spacing);
  color: var(--topbar-item-color, var(--topbar-text-color, var(--primary-color)));
}

.tagline {
  font-size: 12px;
  color: var(--topbar-muted-color, var(--muted));
  margin-top: 2px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tutorial-launcher-slot {
  display: inline-flex;
  align-items: center;
  min-width: 0;
}

.page-status-control {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.page-status-control__label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--topbar-muted-color, rgba(15, 23, 42, 0.65));
}

.page-status-control__select {
  height: 32px;
  border: 1px solid color-mix(in srgb, var(--topbar-muted-color, rgba(15, 23, 42, 0.35)) 40%, transparent);
  border-radius: 8px;
  padding: 0 8px;
  background: color-mix(in srgb, var(--topbar-bg-color, #ffffff) 88%, #ffffff);
  color: var(--topbar-text-color, #0f172a);
  font-size: 12px;
  font-weight: 600;
  max-width: 152px;
}

.page-status-control__select:disabled {
  opacity: 0.7;
  cursor: wait;
}

.login-btn,
.logout-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--topbar-item-color, var(--topbar-muted-color, rgba(15, 23, 42, 0.65)));
  transition: color 0.15s, background 0.15s;
}

.preview-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--topbar-item-color, var(--topbar-muted-color, rgba(15, 23, 42, 0.65)));
  transition: color 0.15s, background 0.15s;
}

.preview-btn:hover {
  color: var(--topbar-item-hover-color, var(--accent, #4f46e5));
  background: color-mix(in srgb, var(--topbar-item-hover-color, var(--accent, #4f46e5)) 8%, transparent);
}

.preview-btn.active {
  color: var(--topbar-item-hover-color, var(--accent, #4f46e5));
  background: color-mix(in srgb, var(--topbar-item-hover-color, var(--accent, #4f46e5)) 12%, transparent);
}

.login-btn:hover {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.08);
}

.logout-btn:hover {
  color: #dc2626;
  background: rgba(220, 38, 38, 0.08);
}

/* Responsive controls */
.divider {
  display: block;
  width: 1px;
  height: 20px;
  background: var(--topbar-muted-color, rgba(15, 23, 42, 0.18));
  margin: 0 2px;
}

.sim-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--topbar-item-color, var(--topbar-muted-color, rgba(15, 23, 42, 0.65)));
  transition: color 0.15s, background 0.15s;
}

.sim-btn:hover {
  color: var(--topbar-item-hover-color, var(--accent, #4f46e5));
  background: color-mix(in srgb, var(--topbar-item-hover-color, var(--accent, #4f46e5)) 8%, transparent);
}

.sim-btn.active {
  color: var(--topbar-item-hover-color, var(--accent, #4f46e5));
  background: color-mix(in srgb, var(--topbar-item-hover-color, var(--accent, #4f46e5)) 12%, transparent);
}

.admin-link-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 64px;
  height: 32px;
  border: 1px solid color-mix(in srgb, var(--topbar-muted-color, rgba(15, 23, 42, 0.35)) 40%, transparent);
  background: color-mix(in srgb, var(--topbar-bg-color, #ffffff) 88%, #ffffff);
  border-radius: 8px;
  cursor: pointer;
  color: var(--topbar-item-color, var(--topbar-text-color, #0f172a));
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.01em;
  padding: 0 10px;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.admin-link-btn:hover {
  color: var(--topbar-item-hover-color, var(--accent, #4f46e5));
  border-color: color-mix(in srgb, var(--topbar-item-hover-color, var(--accent, #4f46e5)) 45%, #cbd5e1);
  background: color-mix(in srgb, var(--topbar-item-hover-color, var(--accent, #4f46e5)) 10%, #ffffff);
}

/* Burger stable */
.burger {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  position: relative;
}

.line {
  position: absolute;
  left: 2px;
  right: 2px;
  height: 2px;
  border-radius: 999px;
  background: var(--topbar-item-color, var(--topbar-text-color, rgba(15, 23, 42, 0.92)));
  opacity: 0.85;
  transition: transform 220ms cubic-bezier(.2,.8,.2,1),
  opacity 180ms ease,
  top 220ms cubic-bezier(.2,.8,.2,1);
}

.l1 { top: 5px; }
.l2 { top: 9px; }
.l3 { top: 13px; }

.burger.open .l1 { top: 9px; transform: rotate(45deg); }
.burger.open .l2 { opacity: 0; transform: scaleX(0.6); }
.burger.open .l3 { top: 9px; transform: rotate(-45deg); }

.brand-text { display: none }

/* Real tablet view - hide tablet simulation button */
@media (min-width: 768px) and (max-width: 1119px) {
  .sim-btn-tablet {
    display: none;
  }
}

/* Real mobile view - hide all simulation buttons and dividers */
@media (max-width: 767px) {
  .sim-btn,
  .sim-divider {
    display: none;
  }
  .page-status-control {
    display: none;
  }
  .admin-link-btn {
    min-width: 56px;
    padding: 0 8px;
  }
}
</style>
