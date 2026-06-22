<template>
  <div class="admin-layout">
    <nav class="admin-nav">
      <router-link to="/" class="admin-back" title="Back to site">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>
        <span class="admin-back-text">Back to Site</span>
      </router-link>
      <div class="admin-nav-title">Admin</div>
      
      <!-- Desktop nav links -->
      <div class="admin-nav-links desktop-only">
        <template
          v-for="link in navLinks"
          :key="`desktop-${link.to}`"
        >
          <router-link
            :to="link.to"
            class="admin-nav-link"
            :class="{ active: isNavLinkActive(link) }"
          >
            {{ link.label }}
          </router-link>
        </template>
      </div>
      
      <!-- Mobile menu button -->
      <button class="mobile-menu-btn mobile-only" @click="mobileMenuOpen = !mobileMenuOpen" :class="{ open: mobileMenuOpen }">
        <svg v-if="!mobileMenuOpen" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
        <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </nav>
    
    <!-- Mobile dropdown menu -->
    <div v-if="mobileMenuOpen" class="mobile-nav-dropdown mobile-only" @click="mobileMenuOpen = false">
        <router-link
        v-for="link in navLinks"
        :key="`mobile-${link.to}`"
        :to="link.to"
        class="mobile-nav-link"
        :class="{ active: isNavLinkActive(link) }"
      >
        {{ link.label }}
      </router-link>
    </div>
    
    <main class="admin-content">
      <router-view />
      <DesignPanel v-if="showDesignPanelInAdmin" />
    </main>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useStore } from '../../store/store.js';
import DesignPanel from '../../components/admin/panels/DesignPanel.vue';

const mobileMenuOpen = ref(false);
const { state } = useStore();
const route = useRoute();

const TEMPLATE_BUILDER_ROUTE_NAMES = new Set([
  'admin-templates-section-default',
  'admin-templates-section-template',
  'admin-templates-container-template',
  'admin-templates-page-template',
]);

const showDesignPanelInAdmin = computed(() =>
  TEMPLATE_BUILDER_ROUTE_NAMES.has(String(route.name || ''))
);

const navLinks = computed(() => {
  return [
    state.canContent
      ? {
          to: '/admin/devops/changelog',
          label: state.canAdminGeneral ? 'DevOps' : 'Changelog',
          activePrefix: '/admin/devops',
          showTutorialLauncher: true,
        }
      : null,
    state.canAdminGeneral
      ? { to: '/admin/integrations/base', label: 'Integrations', activePrefix: '/admin/integrations' }
      : null,
    state.canAdminDesign
      ? { to: '/admin/templates/sections', label: 'Templates', activePrefix: '/admin/templates' }
      : null,
    { to: '/admin/sitemap/pages', label: 'Sitemap', activePrefix: '/admin/sitemap' },
    state.canAdminDesign
      ? { to: '/admin/design/sections', label: 'Design', activePrefix: '/admin/design' }
      : null,
    { to: '/admin/media/library', label: 'Media', activePrefix: '/admin/media' },
    state.canAdminGeneral
      ? { to: '/admin/database/overview', label: 'Database', activePrefix: '/admin/database' }
      : null,
    state.canAdminGeneral
      ? { to: '/admin/permissions', label: 'Permissions', activePrefix: '/admin/permissions' }
      : null,
  ].filter(Boolean);
});

function isNavLinkActive(link) {
  const prefix = String(link?.activePrefix || link?.to || '').replace(/\/+$/g, '');
  const path = String(route.path || '').replace(/\/+$/g, '');
  return path === prefix || path.startsWith(`${prefix}/`);
}
</script>

<style scoped>
.admin-layout {
  min-height: 100vh;
  background: #f1f5f9;
  display: flex;
  flex-direction: column;
}

.admin-nav {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 0 24px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.admin-back {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #64748b;
  text-decoration: none;
  transition: color 0.15s;
}
.admin-back:hover { color: #0f172a; }

.admin-nav-title {
  font-weight: 800;
  font-size: 15px;
  color: #0f172a;
  padding-left: 12px;
  border-left: 1px solid #e2e8f0;
}

.admin-nav-links {
  display: flex;
  gap: 4px;
  margin-left: auto;
}

.admin-nav-link {
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  text-decoration: none;
  border-radius: 6px;
  transition: all 0.15s;
}
.admin-nav-link:hover { background: #f1f5f9; color: #0f172a; }
.admin-nav-link.active { background: #4f46e5; color: #fff; }

.admin-content {
  flex: 1;
  padding: 24px;
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
}

/* Mobile menu button */
.mobile-menu-btn {
  margin-left: auto;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
}

.mobile-menu-btn:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.mobile-menu-btn.open {
  background: #4f46e5;
  border-color: #4f46e5;
  color: #fff;
}

/* Mobile dropdown menu */
.mobile-nav-dropdown {
  position: absolute;
  top: 56px;
  left: 0;
  right: 0;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  padding: 8px;
  z-index: 49;
  display: flex;
  flex-direction: column;
  gap: 4px;
  animation: slideDown 0.15s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.mobile-nav-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  text-decoration: none;
  border-radius: 8px;
  transition: all 0.15s;
}

.mobile-nav-link:hover {
  background: #f8fafc;
}

.mobile-nav-link.active {
  background: #eef2ff;
  color: #4f46e5;
}

.mobile-nav-link svg {
  flex-shrink: 0;
  opacity: 0.7;
}

.mobile-nav-link.active svg {
  opacity: 1;
}

/* Responsive visibility classes */
.mobile-only {
  display: none;
}

.desktop-only {
  display: flex;
}

/* Mobile breakpoint */
@media (max-width: 640px) {
  .mobile-only {
    display: flex;
  }
  
  .desktop-only {
    display: none;
  }
  
  .admin-nav {
    padding: 0 12px;
    gap: 12px;
  }
  
  .admin-back-text {
    display: none;
  }
  
  .admin-nav-title {
    padding-left: 8px;
    font-size: 14px;
  }
  
  .admin-content {
    padding: 16px;
  }
  
  .mobile-nav-dropdown {
    padding: 12px;
  }
}

/* Tablet - show condensed desktop nav */
@media (min-width: 641px) and (max-width: 768px) {
  .admin-nav-link {
    padding: 6px 10px;
    font-size: 12px;
  }
  
  .admin-back-text {
    display: none;
  }
}
</style>
