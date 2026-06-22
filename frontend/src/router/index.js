import { createRouter, createWebHistory } from "vue-router";
import BasePage from "../pages/BasePage.vue";

const AdminLayout = () => import("../pages/admin/AdminLayout.vue");
const Design = () => import("../pages/admin/Design.vue");
const Database = () => import("../pages/admin/Database.vue");
const Devops = () => import("../pages/admin/Devops.vue");
const Sitemap = () => import("../pages/admin/Sitemap.vue");
const Integrations = () => import("../pages/admin/Integrations.vue");
const Users = () => import("../pages/admin/Permissions.vue");
const Media = () => import("../pages/admin/Media.vue");
const Templates = () => import("../pages/admin/Templates.vue");
const TempLogin = () => import("../pages/TempLogin.vue");

const INTERNAL_ROLE_ORDER = ['no_access', 'content', 'design', 'admin_design', 'admin_general'];
const INTERNAL_ROLE_RANK = INTERNAL_ROLE_ORDER.reduce((acc, role, index) => {
    acc[role] = index;
    return acc;
}, {});

function normalizeRole(role) {
    const value = String(role || '').trim().toLowerCase();
    return INTERNAL_ROLE_ORDER.includes(value) ? value : 'no_access';
}

function highestRequiredRole(matchedRoutes) {
    const requested = matchedRoutes
        .map(record => record.meta?.minInternalRole)
        .filter(Boolean)
        .map(normalizeRole);

    if (!requested.length) return null;
    return requested.reduce((highest, role) => {
        if ((INTERNAL_ROLE_RANK[role] ?? -1) > (INTERNAL_ROLE_RANK[highest] ?? -1)) {
            return role;
        }
        return highest;
    }, 'no_access');
}

function normalizeRouteSlug(value, fallback = 'unknown') {
    const raw = Array.isArray(value) ? value.join('/') : String(value || '');
    const normalized = raw
        .split('?')[0]
        .split('#')[0]
        .replace(/\\/g, '/')
        .replace(/^\/+|\/+$/g, '')
        .trim();
    return normalized || fallback;
}

function redirectWithQuery(path) {
    return (to) => ({ path, query: to.query, hash: to.hash });
}

function redirectSitemapTab(to) {
    const query = { ...to.query };
    const requestedTab = String(query.tab || '').trim();
    delete query.tab;
    const tab = ['redirects', 'robots', 'caching', 'stats'].includes(requestedTab) ? requestedTab : 'pages';
    return { path: `/admin/sitemap/${tab}`, query, hash: to.hash };
}

const router = createRouter({
    history: createWebHistory(),
    routes: [
        { path: "/", name: "landing", component: BasePage, props: { slug: "landing", defaultHasHeader: true } },
        { path: "/en", name: "landing-en", component: BasePage, props: { slug: "landing", defaultHasHeader: true } },
        { path: "/temp-login", name: "temp-login", component: TempLogin },
        {
            path: "/admin",
            component: AdminLayout,
            meta: { requiresAuth: true, minInternalRole: "content" },
            children: [
                { path: "", redirect: "/admin/sitemap/pages" },
                { path: "sitemap", redirect: redirectSitemapTab, meta: { minInternalRole: "content" } },
                { path: "sitemap/pages", name: "admin-sitemap-pages", component: Sitemap, meta: { minInternalRole: "content" } },
                { path: "sitemap/sitemap", redirect: "/admin/sitemap/pages", meta: { minInternalRole: "content" } },
                { path: "sitemap/redirects", name: "admin-sitemap-redirects", component: Sitemap, meta: { minInternalRole: "content" } },
                { path: "sitemap/robots", name: "admin-sitemap-robots", component: Sitemap, meta: { minInternalRole: "content" } },
                { path: "sitemap/caching", name: "admin-sitemap-caching", component: Sitemap, meta: { minInternalRole: "content" } },
                { path: "sitemap/stats", name: "admin-sitemap-stats", component: Sitemap, meta: { minInternalRole: "content" } },
                { path: "sitemap/:pathMatch(.*)*", redirect: "/admin/sitemap/pages", meta: { minInternalRole: "content" } },
                { path: "media", redirect: redirectWithQuery("/admin/media/library"), meta: { minInternalRole: "content" } },
                { path: "media/import", name: "admin-media-import", component: Media, meta: { minInternalRole: "content" } },
                { path: "media/library", name: "admin-media-library", component: Media, meta: { minInternalRole: "content" } },
                { path: "media/config", name: "admin-media-config", component: Media, meta: { minInternalRole: "content" } },
                { path: "media/cropping", redirect: redirectWithQuery("/admin/media/config"), meta: { minInternalRole: "content" } },
                { path: "media/meta-data", redirect: redirectWithQuery("/admin/media/config"), meta: { minInternalRole: "content" } },
                { path: "media/tags", name: "admin-media-tags", component: Media, meta: { minInternalRole: "content" } },
                { path: "media/:pathMatch(.*)*", redirect: "/admin/media/library", meta: { minInternalRole: "content" } },
                { path: "templates", redirect: "/admin/templates/sections", meta: { minInternalRole: "content" } },
                { path: "templates/sections", name: "admin-templates-sections", component: Templates, meta: { minInternalRole: "content" } },
                { path: "templates/sections/:sectionType", name: "admin-templates-section-default", component: Templates, meta: { minInternalRole: "content" } },
                { path: "templates/sections/:sectionType/:templateName", name: "admin-templates-section-template", component: Templates, meta: { minInternalRole: "content" } },
                { path: "templates/containers", name: "admin-templates-containers", component: Templates, meta: { minInternalRole: "content" } },
                { path: "templates/containers/:templateName", name: "admin-templates-container-template", component: Templates, meta: { minInternalRole: "content" } },
                { path: "templates/pages", name: "admin-templates-pages", component: Templates, meta: { minInternalRole: "content" } },
                { path: "templates/pages/:pathMatch(.*)*", name: "admin-templates-page-template", component: Templates, meta: { minInternalRole: "content" } },
                { path: "design", redirect: redirectWithQuery("/admin/design/sections"), meta: { minInternalRole: "admin_design" } },
                { path: "design/sections", name: "admin-design-sections", component: Design, meta: { minInternalRole: "admin_design" } },
                { path: "design/parameters", name: "admin-design-parameters", component: Design, meta: { minInternalRole: "admin_design" } },
                { path: "design/overrides", name: "admin-design-overrides", component: Design, meta: { minInternalRole: "admin_design" } },
                { path: "design/panel-sections", redirect: redirectWithQuery("/admin/design/sections"), meta: { minInternalRole: "admin_design" } },
                { path: "design/panel-parameters", redirect: redirectWithQuery("/admin/design/parameters"), meta: { minInternalRole: "admin_design" } },
                { path: "design/panel-overrides", redirect: redirectWithQuery("/admin/design/overrides"), meta: { minInternalRole: "admin_design" } },
                { path: "design/section-order", redirect: redirectWithQuery("/admin/design/sections"), meta: { minInternalRole: "admin_design" } },
                { path: "design/design-parameters", redirect: redirectWithQuery("/admin/design/parameters"), meta: { minInternalRole: "admin_design" } },
                { path: "design/design-overrides", redirect: redirectWithQuery("/admin/design/overrides"), meta: { minInternalRole: "admin_design" } },
                { path: "design/fonts", name: "admin-design-fonts", component: Design, meta: { minInternalRole: "admin_design" } },
                { path: "design/buttons", name: "admin-design-buttons", component: Design, meta: { minInternalRole: "admin_design" } },
                { path: "design/colors", name: "admin-design-colors", component: Design, meta: { minInternalRole: "admin_design" } },
                { path: "design/responsive", name: "admin-design-responsive", component: Design, meta: { minInternalRole: "admin_design" } },
                { path: "design/font-families", redirect: redirectWithQuery("/admin/design/fonts"), meta: { minInternalRole: "admin_design" } },
                { path: "design/button-types", redirect: redirectWithQuery("/admin/design/buttons"), meta: { minInternalRole: "admin_design" } },
                { path: "design/color-linking", redirect: redirectWithQuery("/admin/design/colors"), meta: { minInternalRole: "admin_design" } },
                { path: "design/reset", name: "admin-design-reset", component: Design, meta: { minInternalRole: "admin_design" } },
                { path: "design/:pathMatch(.*)*", redirect: redirectWithQuery("/admin/design/sections"), meta: { minInternalRole: "admin_design" } },
                { path: "database", redirect: redirectWithQuery("/admin/database/overview"), meta: { minInternalRole: "admin_general" } },
                { path: "database/overview", name: "admin-database-overview", component: Database, meta: { minInternalRole: "admin_general" } },
                { path: "database/backups", name: "admin-database-backups", component: Database, meta: { minInternalRole: "admin_general" } },
                { path: "database/collections", name: "admin-database-collections", component: Database, meta: { minInternalRole: "admin_general" } },
                { path: "database/migration", name: "admin-database-migration", component: Database, meta: { minInternalRole: "admin_general" } },
                { path: "database/revisions", name: "admin-database-revisions", component: Database, meta: { minInternalRole: "admin_general" } },
                { path: "database/cleaning", name: "admin-database-cleaning", component: Database, meta: { minInternalRole: "admin_general" } },
                { path: "database/reset", name: "admin-database-reset", component: Database, meta: { minInternalRole: "admin_general" } },
                { path: "database/:pathMatch(.*)*", redirect: "/admin/database/overview", meta: { minInternalRole: "admin_general" } },
                { path: "devops", redirect: redirectWithQuery("/admin/devops/changelog"), meta: { minInternalRole: "content" } },
                { path: "devops/changelog", name: "admin-devops-changelog", component: Devops, meta: { minInternalRole: "content" } },
                { path: "devops/todos", name: "admin-devops-todos", component: Devops, meta: { minInternalRole: "content" } },
                { path: "devops/all-todos", redirect: redirectWithQuery("/admin/devops/todos"), meta: { minInternalRole: "content" } },
                { path: "devops/planning", name: "admin-devops-planning", component: Devops, meta: { minInternalRole: "content" } },
                {
                    path: "devops/planning-it",
                    redirect: (to) => ({ path: "/admin/devops/planning", query: { ...to.query, area: "it" }, hash: to.hash }),
                    meta: { minInternalRole: "content" },
                },
                {
                    path: "devops/planning-content",
                    redirect: (to) => ({ path: "/admin/devops/planning", query: { ...to.query, area: "content" }, hash: to.hash }),
                    meta: { minInternalRole: "content" },
                },
                { path: "devops/tutorials", name: "admin-devops-tutorials", component: Devops, meta: { minInternalRole: "content" } },
                { path: "devops/tags", name: "admin-devops-tags", component: Devops, meta: { minInternalRole: "content" } },
                { path: "devops/:pathMatch(.*)*", redirect: "/admin/devops/changelog", meta: { minInternalRole: "content" } },
                { path: "backup", redirect: "/admin/database/backups", meta: { minInternalRole: "admin_general" } },
                { path: "integrations", redirect: redirectWithQuery("/admin/integrations/base"), meta: { minInternalRole: "admin_general" } },
                { path: "integrations/base", name: "admin-integrations-base", component: Integrations, meta: { minInternalRole: "admin_general" } },
                { path: "integrations/compose", name: "admin-integrations-compose", component: Integrations, meta: { minInternalRole: "admin_general" } },
                { path: "integrations/composable", redirect: "/admin/integrations/compose", meta: { minInternalRole: "admin_general" } },
                { path: "integrations/edit", name: "admin-integrations-edit", component: Integrations, meta: { minInternalRole: "admin_general" } },
                { path: "integrations/manage", redirect: redirectWithQuery("/admin/integrations/edit"), meta: { minInternalRole: "admin_general" } },
                { path: "integrations/review", name: "admin-integrations-review", component: Integrations, meta: { minInternalRole: "admin_general" } },
                { path: "integrations/expose", name: "admin-integrations-expose", component: Integrations, meta: { minInternalRole: "admin_general" } },
                { path: "integrations/export", redirect: "/admin/integrations/expose", meta: { minInternalRole: "admin_general" } },
                { path: "integrations/connect", redirect: "/admin/integrations/expose", meta: { minInternalRole: "admin_general" } },
                { path: "integrations/:pathMatch(.*)*", redirect: "/admin/integrations/base", meta: { minInternalRole: "admin_general" } },
                { path: "permissions", name: "admin-permissions", component: Users, meta: { minInternalRole: "admin_general" } },
                { path: "users", redirect: "/admin/permissions", meta: { minInternalRole: "admin_general" } },
                { path: ":pathMatch(.*)*", redirect: "/admin/sitemap/pages", meta: { minInternalRole: "content" } },
            ],
        },
        { 
            path: "/en/:slug", 
            name: "page-en", 
            component: BasePage,
            props: route => ({ slug: normalizeRouteSlug(route.params.slug) })
        },
        { 
            path: "/en/:pathMatch(.*)*", 
            name: "dynamic-page-en", 
            component: BasePage,
            props: route => {
                return { slug: normalizeRouteSlug(route.params.pathMatch) };
            }
        },
        { 
            path: "/:slug", 
            name: "page", 
            component: BasePage,
            props: route => ({ slug: normalizeRouteSlug(route.params.slug) })
        },
        { 
            path: "/:pathMatch(.*)*", 
            name: "dynamic-page", 
            component: BasePage,
            props: route => {
                return { slug: normalizeRouteSlug(route.params.pathMatch) };
            }
        }
    ],
    scrollBehavior() {
        return { top: 0 };
    }
});

router.beforeEach(async (to, from) => {
    const requiredRole = highestRequiredRole(to.matched);
    if (requiredRole) {
        const { hasInternalRole, initAuth, authState, login, getHighestAllowedAdminPath } = await import("../services/auth.js");
        if (!authState.initialized) {
            await initAuth();
        }
        if (!authState.authenticated) {
            login(window.location.origin + to.fullPath);
            return false;
        }
        if (!hasInternalRole(requiredRole)) {
            const redirectTarget = getHighestAllowedAdminPath();
            if (redirectTarget && redirectTarget !== to.path) {
                return { path: redirectTarget };
            }
            return { path: "/" };
        }
    }

    // Warn about unsaved design changes when navigating away
    if (from.path !== to.path) {
        const { useStore } = await import("../store/store.js");
        const { state, confirmUnsavedDesignChanges } = useStore();
        if (state.designDirty) {
            const { loadDesignSettings } = useStore();
            const result = await confirmUnsavedDesignChanges();
            if (result === 'cancel') return false;
            if (result === 'discard') {
                await loadDesignSettings();
            }
        }
    }
});

export default router;
