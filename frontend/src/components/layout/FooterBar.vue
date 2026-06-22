<template>
  <footer class="footer" :style="footerStyle">
    <div class="container footer-inner">
      <div v-if="displayedFooterSocialLinks.length" class="footer-row footer-social-row">
        <a
          v-for="link in displayedFooterSocialLinks"
          :key="link.key"
          :href="link.href"
          class="link social-link"
          :title="link.title"
          :aria-label="link.title"
          @click.prevent="navigate(link)"
        >
          <font-awesome-icon
            v-if="link.icon && link.icon !== 'other'"
            :icon="['fab', resolveBrandIconName(link.icon)]"
            class="link-icon"
          />
          <font-awesome-icon
            v-else-if="link.icon === 'other'"
            :icon="faArrowUpRightFromSquare"
            class="link-icon"
          />
          <span v-else>{{ link.label }}</span>
        </a>
      </div>

      <div v-if="displayedFooterBottomLinks.length" class="footer-row footer-links-row">
        <template v-for="(link, index) in displayedFooterBottomLinks" :key="link.key">
          <a
            :href="link.href"
            class="link text-link"
            :title="link.title"
            :aria-label="link.title"
            @click.prevent="navigate(link)"
          >
            <span>{{ link.label }}</span>
          </a>
          <span v-if="index < displayedFooterBottomLinks.length - 1" class="sep">·</span>
        </template>
      </div>

      <div class="footer-row footer-logo-row">
        <a
          :href="homeHref"
          class="footer-brand-link"
          :aria-label="footerBrandLabel"
          @click.prevent="navigateHome"
        >
          <ResponsiveImage
            v-if="footerLogoUrl"
            :src="footerLogoUrl"
            :image-data="footerLogoImageData"
            :style="footerLogoStyle"
            :alt="appDisplayName"
            class="footer-brand-logo"
            :slot-width="220"
            loading="lazy"
            decoding="async"
          />
          <span v-else>{{ appDisplayName }} {{ year }}</span>
        </a>
      </div>
    </div>
  </footer>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { faArrowUpRightFromSquare } from '@fortawesome/free-solid-svg-icons';
import { useStore } from '../../store/store.js';
import * as api from '../../services/api.js';
import ResponsiveImage from '../ui/ResponsiveImage.vue';
import { isVectorOrPngImageUrl } from '../../utils/imageFormat.js';
import { getCurrentServerWallDate } from '../../utils/revisionTime.js';
import { getAppDisplayName } from '../../utils/appConfig.js';

const { state } = useStore();
const router = useRouter();
const year = getCurrentServerWallDate().getFullYear();
const appDisplayName = computed(() => getAppDisplayName());
const footerBrandLabel = computed(() => `${appDisplayName.value} ${year}`);
const footerItems = ref([]);
const footerLogoUrl = ref(null);
const footerLogoResponsiveVariants = ref([]);

const fallbackFooterLinks = Object.freeze([
  { key: 'fallback-datenschutz', href: '/datenschutz', label: 'Datenschutz' },
  { key: 'fallback-impressum', href: '/impressum', label: 'Impressum' },
]);

const EXTERNAL_ICON_LABELS = Object.freeze({
  other: 'External Link',
  facebook: 'Facebook',
  instagram: 'Instagram',
  twitter: 'Twitter',
  youtube: 'YouTube',
  tiktok: 'TikTok',
});

const SOCIAL_ICON_NAMES = Object.freeze([
  'facebook',
  'instagram',
  'twitter',
  'x-twitter',
  'youtube',
  'tiktok',
  'linkedin',
  'threads',
  'discord',
]);

function normalizeFooterLogoUrl(value) {
  const normalized = String(value || '').trim();
  return normalized || null;
}

function normalizeFooterLogoResponsiveVariants(value) {
  if (!Array.isArray(value)) return [];
  return value.filter((entry) => entry && typeof entry === 'object' && !Array.isArray(entry));
}

function applyFooterLogoPayload(payload) {
  footerLogoUrl.value = normalizeFooterLogoUrl(payload?.footer_logo_url);
  footerLogoResponsiveVariants.value = normalizeFooterLogoResponsiveVariants(payload?.footer_logo_responsive_variants);
}

function applyPublicFooterLogoPayload() {
  applyFooterLogoPayload({
    footer_logo_url: window.__SSC_PUBLIC_FOOTER_LOGO_URL,
    footer_logo_responsive_variants: window.__SSC_PUBLIC_FOOTER_LOGO_RESPONSIVE_VARIANTS,
  });
}

function parseColorToRgb(colorValue) {
  const raw = String(colorValue || '').trim();
  if (!raw) return null;

  if (raw.startsWith('#')) {
    const hex = raw.slice(1);
    if (hex.length === 3) {
      const r = parseInt(hex[0] + hex[0], 16);
      const g = parseInt(hex[1] + hex[1], 16);
      const b = parseInt(hex[2] + hex[2], 16);
      if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) return null;
      return { r, g, b };
    }
    if (hex.length === 6) {
      const r = parseInt(hex.slice(0, 2), 16);
      const g = parseInt(hex.slice(2, 4), 16);
      const b = parseInt(hex.slice(4, 6), 16);
      if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) return null;
      return { r, g, b };
    }
    return null;
  }

  const rgbMatch = raw.match(/^rgba?\(([^)]+)\)$/i);
  if (!rgbMatch) return null;
  const parts = rgbMatch[1].split(',').map((part) => part.trim());
  if (parts.length < 3) return null;
  const r = Number(parts[0]);
  const g = Number(parts[1]);
  const b = Number(parts[2]);
  if (![r, g, b].every((value) => Number.isFinite(value))) return null;
  return {
    r: Math.max(0, Math.min(255, r)),
    g: Math.max(0, Math.min(255, g)),
    b: Math.max(0, Math.min(255, b)),
  };
}

function rgbToLuminance(rgb) {
  const r = (rgb?.r ?? 0) / 255;
  const g = (rgb?.g ?? 0) / 255;
  const b = (rgb?.b ?? 0) / 255;
  const toLinear = (value) => value <= 0.03928
    ? value / 12.92
    : Math.pow((value + 0.055) / 1.055, 2.4);
  return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
}

function logoContrastFilter(colorValue) {
  const rgb = parseColorToRgb(colorValue);
  if (!rgb) return 'brightness(0) saturate(100%)';
  // Match logo tone to footer text tone: light text -> light logo, dark text -> dark logo.
  return rgbToLuminance(rgb) > 0.4
    ? 'brightness(0) saturate(100%) invert(1)'
    : 'brightness(0) saturate(100%)';
}

function contrastColor(bgHex) {
  const dark = state.design.highContrastDark || '#0b1220';
  const light = state.design.highContrastLight || '#f8fafc';
  try {
    const c = (bgHex || '#f6f7fb').replace('#', '');
    if (c.length < 6) return dark;
    const r = parseInt(c.substring(0, 2), 16) / 255;
    const g = parseInt(c.substring(2, 4), 16) / 255;
    const b = parseInt(c.substring(4, 6), 16) / 255;
    const toL = (v) => v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    const lum = 0.2126 * toL(r) + 0.7152 * toL(g) + 0.0722 * toL(b);
    return lum > 0.179 ? dark : light;
  } catch { return dark; }
}

const footerStyle = computed(() => {
  const bgColor = state.design.backgroundColor || '#f6f7fb';
  const textColor = contrastColor(bgColor);
  return {
    '--footer-text-color': textColor,
    '--footer-logo-filter': logoContrastFilter(textColor),
  };
});

const footerLogoImageData = computed(() => ({
  imageUrl: String(footerLogoUrl.value || '').trim(),
  responsiveVariants: normalizeFooterLogoResponsiveVariants(footerLogoResponsiveVariants.value),
}));

const footerLogoStyle = computed(() => ({
  filter: isVectorOrPngImageUrl(footerLogoUrl.value)
    ? 'var(--footer-logo-filter, none)'
    : 'none',
}));

function formatSlugAsTitle(slug) {
  const normalized = String(slug || '').trim();
  if (!normalized || normalized === 'landing') return '/';
  const lastPart = normalized.split('/').pop() || normalized;
  return lastPart
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function getFooterLabel(page) {
  const menuTitle = page?.menu_title;
  const title = page?.title;
  const label = menuTitle?.[state.lang] || menuTitle?.de || menuTitle?.en
    || title?.[state.lang] || title?.de || title?.en
    || formatSlugAsTitle(page?.slug);
  return String(label || '').trim() || formatSlugAsTitle(page?.slug);
}

function getPagePath(slug) {
  return slug === 'landing' ? '/' : `/${slug}`;
}

function isExternalItem(item) {
  return String(item?.kind || '').trim().toLowerCase() === 'external';
}

function resolveExternalItemLabel(item) {
  const label = item?.label && typeof item.label === 'object' ? item.label : null;
  const localizedLabel = label?.[state.lang] || label?.de || label?.en || '';
  const normalized = String(localizedLabel || '').trim();
  if (normalized) return normalized;
  const icon = String(item?.icon || '').trim().toLowerCase();
  if (icon && EXTERNAL_ICON_LABELS[icon]) return EXTERNAL_ICON_LABELS[icon];
  return String(item?.url || '').trim();
}

function resolveBrandIconName(iconName) {
  const normalized = String(iconName || '').trim().toLowerCase();
  if (normalized === 'twitter') return 'x-twitter';
  return normalized || 'link';
}

function isSocialExternalLink(link) {
  const icon = String(link?.icon || '').trim().toLowerCase();
  return SOCIAL_ICON_NAMES.includes(icon);
}

function withPublicLangPrefix(path) {
  const target = String(path || '').trim();
  if (!target.startsWith('/')) return target;

  const isPublicLikeView = !state.isAdmin || state.previewMode;
  if (!isPublicLikeView || state.lang !== 'en') return target;
  if (target === '/en' || target.startsWith('/en/')) return target;
  if (target === '/') return '/en';
  return `/en${target}`;
}

const configuredFooterExternalLinks = computed(() => {
  const items = Array.isArray(footerItems.value) ? [...footerItems.value] : [];
  return items
    .filter((item) => isExternalItem(item))
    .sort((a, b) => {
      const orderA = Number(a?.order ?? 0);
      const orderB = Number(b?.order ?? 0);
      if (orderA !== orderB) return orderA - orderB;
      return String(a?.id || '').localeCompare(String(b?.id || ''));
    })
    .map((item) => {
      const href = String(item?.external_url || item?.url || '').trim();
      const icon = String(item?.icon || '').trim().toLowerCase() || null;
      const title = resolveExternalItemLabel(item);
      return {
        key: `footer-external-${item.id || href}`,
        href,
        label: title,
        icon,
        title,
        external: true,
      };
    })
    .filter((item) => Boolean(item.href));
});

const configuredFooterInternalLinks = computed(() => {
  const items = Array.isArray(footerItems.value) ? [...footerItems.value] : [];
  return items
    .filter((item) => !isExternalItem(item))
    .filter((item) => item && item.slug)
    .sort((a, b) => {
      const orderA = Number(a?.footer_order ?? 0);
      const orderB = Number(b?.footer_order ?? 0);
      if (orderA !== orderB) return orderA - orderB;
      if (a?.slug === 'landing') return -1;
      if (b?.slug === 'landing') return 1;
      return String(a?.slug || '').localeCompare(String(b?.slug || ''));
    })
    .map((page) => {
      const href = withPublicLangPrefix(getPagePath(page.slug));
      const title = getFooterLabel(page);
      return {
        key: `footer-${page.id || page.slug}`,
        href,
        label: title,
        icon: null,
        title,
        external: false,
      };
    });
});

const displayedFooterExternalLinks = computed(() => configuredFooterExternalLinks.value);

const displayedFooterSocialLinks = computed(() => (
  displayedFooterExternalLinks.value.filter((link) => isSocialExternalLink(link))
));

const displayedFooterExternalTextLinks = computed(() => (
  displayedFooterExternalLinks.value
    .filter((link) => !isSocialExternalLink(link))
    .map((link) => ({
      ...link,
      label: String(link.label || link.href || '').trim(),
      title: String(link.title || link.label || link.href || '').trim(),
    }))
    .filter((link) => Boolean(link.label))
));

const displayedFooterInternalLinks = computed(() => {
  if (configuredFooterInternalLinks.value.length > 0) return configuredFooterInternalLinks.value;
  if (configuredFooterExternalLinks.value.length > 0) return [];
  return fallbackFooterLinks.map((link) => ({
    ...link,
    href: withPublicLangPrefix(link.href),
    title: link.label,
    external: false,
  }));
});

const displayedFooterBottomLinks = computed(() => ([
  ...displayedFooterExternalTextLinks.value,
  ...displayedFooterInternalLinks.value,
]));

const homeHref = computed(() => withPublicLangPrefix('/'));

function navigate(href) {
  const target = String(href?.href || '').trim();
  if (!target) return;
  if (href?.external) {
    window.open(target, '_blank', 'noopener,noreferrer');
    return;
  }
  if (target.startsWith('http://') || target.startsWith('https://')) {
    window.location.href = target;
    return;
  }
  router.push(withPublicLangPrefix(target));
}

function navigateHome() {
  navigate({ href: homeHref.value, external: false });
}

async function loadFooterItems() {
  try {
    const usePublicCache = !state.isAdmin && !state.previewMode;
    if (usePublicCache) {
      const cachedFooter = window.__SSC_PUBLIC_FOOTER_ITEMS;
      footerItems.value = Array.isArray(cachedFooter) ? cachedFooter : [];
      applyPublicFooterLogoPayload();
      return;
    }

    const [adminFooterItems, navigationConfig] = await Promise.all([
      api.getFooterItems({ includeHidden: state.isAdmin }),
      api.getSitemapNavigationLinks(),
    ]);
    footerItems.value = Array.isArray(adminFooterItems) ? adminFooterItems : [];
    applyFooterLogoPayload(navigationConfig);
  } catch (err) {
    console.error('Failed to load footer items:', err);
    footerItems.value = [];
    applyFooterLogoPayload({});
  }
}

function handlePublicFooterUpdate() {
  if (state.isAdmin || state.previewMode) return;
  const cachedFooter = window.__SSC_PUBLIC_FOOTER_ITEMS;
  if (Array.isArray(cachedFooter)) {
    footerItems.value = cachedFooter;
  }
  applyPublicFooterLogoPayload();
}

watch(() => [state.isAdmin, state.previewMode], () => {
  loadFooterItems();
});

onMounted(() => {
  loadFooterItems();
  window.addEventListener('fstvlpress-public-footer-updated', handlePublicFooterUpdate);
});

onUnmounted(() => {
  window.removeEventListener('fstvlpress-public-footer-updated', handlePublicFooterUpdate);
});
</script>

<style scoped>
.footer {
  padding: 20px 0;
  background: transparent;
}

.footer-inner {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--footer-text-color, var(--secondary-color));
}

.footer-brand-link {
  color: var(--footer-text-color, var(--secondary-color));
  font-weight: 650;
  text-decoration: none;
}

.footer-brand-link:hover {
  color: var(--footer-text-color, var(--secondary-color));
  opacity: 0.9;
}

.footer-brand-logo {
  height: 2.5rem;
  max-width: min(220px, 60vw);
  width: auto;
  object-fit: contain;
  display: block;
  filter: none;
}

.footer-row {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  width: 100%;
  color: var(--footer-text-color, var(--secondary-color));
}

.footer-social-row {
  gap: 10px;
}

.footer-links-row {
  gap: 4px;
}

.link {
  color: var(--footer-text-color, var(--secondary-color));
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.link:hover {
  color: var(--footer-text-color, var(--secondary-color));
  opacity: 0.8;
}


.link-icon {
  font-size: 1.25rem;
  padding: 0 0.25rem;
}

.sep {
  color: var(--footer-text-color, var(--secondary-color));
}
</style>
