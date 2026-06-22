/**
 * API service for interacting with the backend.
 */
import { getToken } from './auth.js';
import { resolveApiBase } from './apiBase.js';

const API_BASE = resolveApiBase();
const TEMPLATE_BUILDER_KINDS = new Set(['section', 'container', 'page']);
const PUBLIC_AVAILABILITY_CACHE_TTL_MS = 60 * 1000;
const MAX_PUBLIC_AVAILABILITY_CACHE_ENTRIES = 1000;
const PUBLIC_HIT_SESSION_PREFIX = 'fstvlpress-public-hit:';

let templateBuilderContext = null;
const publicAvailabilityCache = new Map();

function slugifyTemplateSegment(value, fallback = 'item') {
  const text = String(value ?? '').trim().toLowerCase();
  const slug = text
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || fallback;
}

function normalizeTemplateName(value, fallback = 'default') {
  const text = String(value ?? '').trim().toLowerCase();
  const slug = text
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || fallback;
}

function normalizeTemplateSectionType(value, fallback = 'text') {
  const text = String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '_');
  const normalized = text
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '');
  return normalized || fallback;
}

function normalizeTemplateParentRoute(value) {
  const text = String(value ?? '').trim();
  if (!text || text === '/') return null;
  const normalized = text
    .split('/')
    .map((part) => slugifyTemplateSegment(part, ''))
    .filter(Boolean)
    .join('/');
  return normalized ? `/${normalized}` : null;
}

function resolveTemplateKeyFromContext(context) {
  const kind = String(context?.kind || '').trim().toLowerCase();
  const rawPath = String(context?.path || '').trim().replace(/^\/+|\/+$/g, '');
  if (!rawPath) return null;

  if (kind === 'section') {
    const [sectionTypeRaw, templateNameRaw] = rawPath.split('/');
    const sectionType = normalizeTemplateSectionType(sectionTypeRaw, 'text');
    const templateName = normalizeTemplateName(templateNameRaw || 'default', 'default');
    return `section:${sectionType}:${templateName}`;
  }

  if (kind === 'container') {
    return `container:${normalizeTemplateName(rawPath)}`;
  }

  if (kind === 'page') {
    const parts = rawPath.split('/').filter(Boolean);
    if (!parts.length) return null;
    const templateName = normalizeTemplateName(parts[parts.length - 1]);
    if (parts.length === 1) return `page:${templateName}`;
    const parentRoute = normalizeTemplateParentRoute(`/${parts.slice(0, -1).join('/')}`);
    if (parentRoute) return `page:${parentRoute}:${templateName}`;
    return `page:${templateName}`;
  }

  return null;
}

function normalizeTemplateBuilderContext(context) {
  if (!context || typeof context !== 'object') return null;
  const kind = String(context.kind || '').trim().toLowerCase();
  if (!TEMPLATE_BUILDER_KINDS.has(kind)) return null;
  const path = String(context.path || '').trim().replace(/^\/+|\/+$/g, '');
  if (!path) return null;

  const normalized = {
    kind,
    path,
  };
  normalized.template_key = String(context.template_key || '').trim() || resolveTemplateKeyFromContext(normalized) || null;
  return normalized;
}

function getTemplateContextOrThrow() {
  if (!templateBuilderContext) {
    throw new Error('Template builder context is not configured.');
  }
  return templateBuilderContext;
}

function buildTemplateBuilderUrl(suffix = '', { includePath = true, kind = null } = {}) {
  const context = getTemplateContextOrThrow();
  const resolvedKind = kind || context.kind;
  const params = new URLSearchParams();
  if (includePath) params.set('path', context.path);
  const query = params.toString();
  return `${API_BASE}/admin/templates/builder/${resolvedKind}${suffix}${query ? `?${query}` : ''}`;
}

function parseTemplateSectionBuilderId(sectionId) {
  const raw = String(sectionId || '').trim();
  if (!raw) return null;

  // Current backend format:
  // - section root:   ts__<ownerId>
  // - page embedded:  tp__<ownerId>__<embeddedId>
  // - container emb.: tc__<ownerId>__<embeddedId>
  if (raw.startsWith('ts__')) {
    const ownerId = String(raw.slice('ts__'.length) || '').trim();
    if (!ownerId) return null;
    return { kind: 'section', ownerId, embeddedId: null };
  }

  if (raw.startsWith('tp__') || raw.startsWith('tc__')) {
    const kind = raw.startsWith('tp__') ? 'page' : 'container';
    const payload = raw.slice(4);
    const sep = payload.indexOf('__');
    if (sep <= 0) return null;
    const ownerId = String(payload.slice(0, sep) || '').trim();
    const embeddedId = String(payload.slice(sep + 2) || '').trim();
    if (!ownerId || !embeddedId) return null;
    return { kind, ownerId, embeddedId };
  }
  return null;
}

function isTemplateHeaderBuilderId(headerId) {
  const raw = String(headerId || '').trim();
  return raw.startsWith('th__p__');
}

export function setTemplateBuilderContext(context) {
  templateBuilderContext = normalizeTemplateBuilderContext(context);
}

export function clearTemplateBuilderContext() {
  templateBuilderContext = null;
}

export function getTemplateBuilderContext() {
  return templateBuilderContext ? { ...templateBuilderContext } : null;
}

export function isTemplateBuilderContextActive() {
  return Boolean(templateBuilderContext);
}

/**
 * Get auth headers for API requests.
 * Uses the auth service to get the current token (from Keycloak or dev mode).
 * @param {Object} [options]
 * @param {boolean} [options.includeAuth=true] - Include Authorization header
 * @param {boolean} [options.includeContentType=true] - Include JSON Content-Type
 * @returns {Object} Headers object
 */
function getHeaders({ includeAuth = true, includeContentType = true } = {}) {
  const headers = {};
  if (includeContentType) {
    headers['Content-Type'] = 'application/json';
  }
  // Get token from auth service (Keycloak or dev mock token)
  const token = getToken();
  if (includeAuth && token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

const _origFetch = window.fetch;
window.fetch = async function (input, init = {}) {
  const url = typeof input === 'string' ? input : input?.url;
  let finalInit = init;
  if (url?.includes('/api/') && finalInit.credentials === undefined) {
    // API uses Bearer auth; omitting cookies avoids oversized request headers
    // for users with large auth/session cookie sets.
    finalInit = { ...finalInit, credentials: 'omit' };
  }

  const response = await _origFetch.call(this, input, finalInit);
  if (response.status === 401 && url?.includes('/api/')) {
    const safePath = String(url).split('?')[0];
    console.error(`[API] 401 on ${safePath}`);
  }
  return response;
};

/**
 * Get headers for form data (file uploads).
 * Uses the auth service to get the current token.
 * @returns {Object} Headers object without Content-Type
 */
function getFormHeaders() {
  const headers = {};
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

function normalizePublicSlugForClientCache(value) {
  const raw = String(value || '').trim();
  if (!raw || raw === '/') return 'landing';
  const normalized = raw
    .split('?', 1)[0]
    .split('#', 1)[0]
    .replace(/\\/g, '/')
    .replace(/^\/+|\/+$/g, '');
  return normalized || 'landing';
}

function prunePublicAvailabilityCache(now = Date.now()) {
  for (const [slug, entry] of publicAvailabilityCache.entries()) {
    if (!entry || Number(entry.expiresAt || 0) <= now) {
      publicAvailabilityCache.delete(slug);
    }
  }

  while (publicAvailabilityCache.size > MAX_PUBLIC_AVAILABILITY_CACHE_ENTRIES) {
    const oldestKey = publicAvailabilityCache.keys().next().value;
    if (!oldestKey) break;
    publicAvailabilityCache.delete(oldestKey);
  }
}

function hasRecordedPublicHitInSession(slug) {
  if (typeof window === 'undefined' || !window.sessionStorage) return false;
  try {
    return window.sessionStorage.getItem(`${PUBLIC_HIT_SESSION_PREFIX}${slug}`) === '1';
  } catch {
    return false;
  }
}

function markPublicHitRecordedInSession(slug) {
  if (typeof window === 'undefined' || !window.sessionStorage) return;
  try {
    window.sessionStorage.setItem(`${PUBLIC_HIT_SESSION_PREFIX}${slug}`, '1');
  } catch {
    // Ignore storage quota/privacy errors; hit tracking is best effort.
  }
}

function resolveErrorDetailMessage(errorPayload, fallbackMessage) {
  const fallback = String(fallbackMessage || 'Request failed');
  const detail = errorPayload?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail.trim();
  if (Array.isArray(detail) && detail.length > 0) {
    const parts = detail
      .map((entry) => {
        if (typeof entry === 'string') return entry.trim();
        if (!entry || typeof entry !== 'object') return '';
        const message = String(entry.msg || entry.message || '').trim();
        const location = Array.isArray(entry.loc)
          ? entry.loc.map((segment) => String(segment || '').trim()).filter(Boolean).join('.')
          : '';
        if (message && location) return `${location}: ${message}`;
        return message || '';
      })
      .filter(Boolean);
    if (parts.length > 0) return parts.join('; ');
  }
  if (detail && typeof detail === 'object') {
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }
  return fallback;
}

// -------------------------
// Assets API
// -------------------------

/**
 * Upload a media file to the media library.
 * @param {File} file - The file to upload
 * @param {Object} [options]
 * @param {string} [options.sourceContext]
 * @param {boolean} [options.bypassAutocropTransparentPadding]
 * @param {boolean} [options.deferRequiredMetadataValidation]
 * @returns {Promise<Object>} Upload result with URLs
 */
export async function uploadImage(file, options = {}) {
  const formData = new FormData();
  formData.append('file', file);
  const sourceContext = String(options?.sourceContext || '').trim();
  const bypassAutocropTransparentPadding = Boolean(options?.bypassAutocropTransparentPadding);
  const deferRequiredMetadataValidation = Boolean(options?.deferRequiredMetadataValidation);
  if (sourceContext) {
    formData.append('source_context', sourceContext);
  }
  formData.append('bypass_autocrop_transparent_padding', bypassAutocropTransparentPadding ? '1' : '0');
  formData.append('defer_required_metadata_validation', deferRequiredMetadataValidation ? '1' : '0');

  const response = await fetch(`${API_BASE}/assets/upload`, {
    method: 'POST',
    headers: getFormHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail || 'Upload failed');
  }

  return response.json();
}

/**
 * List assets from the media library.
 * @param {Object} options - Query options
 * @param {number} options.page - Page number (default 1)
 * @param {number} options.pageSize - Items per page (default 50)
 * @param {string} options.search - Search query (optional)
 * @returns {Promise<Object>} List response with items and pagination
 */
export async function listAssets({ page = 1, pageSize = 50, search = '', tag = '' } = {}) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  
  if (search) {
    params.append('search', search);
  }
  if (tag) {
    params.append('tag', tag);
  }

  const response = await fetch(`${API_BASE}/assets?${params}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch assets' }));
    throw new Error(error.detail || 'Failed to fetch assets');
  }

  return response.json();
}

export async function listPublicAssetsByTag(tag, { pageSize = 100, maxPages = 10 } = {}) {
  const cleanTag = String(tag || '').trim();
  if (!cleanTag) return [];

  const collected = [];
  const boundedPageSize = Math.max(1, Math.min(100, Number(pageSize) || 100));
  const boundedMaxPages = Math.max(1, Math.min(40, Number(maxPages) || 10));
  let page = 1;
  let hasMore = true;

  while (hasMore && page <= boundedMaxPages) {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(boundedPageSize),
      tag: cleanTag,
    });
    const response = await fetch(`${API_BASE}/assets/public?${params.toString()}`, {
      method: 'GET',
      headers: getHeaders({ includeAuth: false }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to fetch assets' }));
      throw new Error(error.detail || 'Failed to fetch assets');
    }

    const payload = await response.json();
    const items = Array.isArray(payload?.items) ? payload.items : [];
    collected.push(...items);
    hasMore = Boolean(payload?.has_more);
    page += 1;
  }

  return collected;
}

/**
 * Delete an asset from the media library.
 * @param {string} assetId - The asset ID to delete
 * @returns {Promise<Object>} Delete confirmation
 */
export async function deleteAsset(assetId) {
  const response = await fetch(`${API_BASE}/assets/${assetId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Delete failed' }));
    throw new Error(error.detail || 'Delete failed');
  }

  return response.json();
}

/**
 * Regenerate generated thumbnails and responsive variants for all image assets.
 * @param {Object} options
 * @param {boolean} [options.bypass_autocrop_transparent_padding]
 * @returns {Promise<{processed:number,regenerated:number,skipped:number,failed:number,errors:Array}>}
 */
export async function regenerateAssetVariants(options = {}) {
  const response = await fetch(`${API_BASE}/assets/regenerate-variants`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      bypass_autocrop_transparent_padding: Boolean(options?.bypass_autocrop_transparent_padding),
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Regenerate failed' }));
    throw new Error(error.detail || 'Regenerate failed');
  }

  return response.json();
}

/**
 * Rename an asset in the media library.
 * @param {string} assetId - The asset ID to rename
 * @param {string} filename - The new filename
 * @returns {Promise<Object>} Rename confirmation
 */
export async function renameAsset(assetId, filename) {
  const response = await fetch(`${API_BASE}/assets/${assetId}/rename`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify({ filename }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Rename failed' }));
    throw new Error(error.detail || 'Rename failed');
  }

  return response.json();
}

/**
 * Update tags for an asset.
 * @param {string} assetId - The asset ID
 * @param {string[]} tags - Array of tag strings
 * @returns {Promise<Object>} Updated tags
 */
export async function updateAssetTags(assetId, tags) {
  const response = await fetch(`${API_BASE}/assets/${assetId}/tags`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify({ tags }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update tags' }));
    throw new Error(error.detail || 'Failed to update tags');
  }

  return response.json();
}

/**
 * Update bilingual alt/caption text for an asset.
 * @param {string} assetId - The asset ID
 * @param {{ alt?: {de?: string, en?: string}, caption?: {de?: string, en?: string} }} payload
 * @returns {Promise<Object>} Updated text payload
 */
export async function updateAssetText(assetId, payload) {
  const response = await fetch(`${API_BASE}/assets/${assetId}/text`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update image text' }));
    throw new Error(error.detail || 'Failed to update image text');
  }

  return response.json();
}

/**
 * Toggle downloadability for an asset.
 * @param {string} assetId - The asset ID
 * @param {boolean} downloadable - Whether public download route is enabled
 * @returns {Promise<{status:string, asset_id:string, downloadable:boolean, media_hash:string, download_url:string|null}>}
 */
export async function updateAssetDownloadable(assetId, downloadable) {
  const response = await fetch(`${API_BASE}/assets/${assetId}/downloadable`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify({ downloadable: Boolean(downloadable) }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update downloadable state' }));
    throw new Error(error.detail || 'Failed to update downloadable state');
  }

  return response.json();
}

/**
 * Get all distinct tags used across assets.
 * @returns {Promise<Object>} Object with tags array
 */
export async function listAssetTags() {
  const response = await fetch(`${API_BASE}/assets/tags`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch tags' }));
    throw new Error(error.detail || 'Failed to fetch tags');
  }

  return response.json();
}

/**
 * Import a remote media URL into the media library.
 * @param {string} url - Remote media URL
 * @param {string} [filename] - Optional filename override
 * @param {Object} [options]
 * @param {string} [options.sourceContext]
 * @param {boolean} [options.bypassAutocropTransparentPadding]
 * @param {boolean} [options.deferRequiredMetadataValidation]
 * @returns {Promise<Object>} Imported asset payload
 */
export async function importAssetFromUrl(url, filename = '', options = {}) {
  const sourceContext = String(options?.sourceContext || '').trim();
  const bypassAutocropTransparentPadding = Boolean(options?.bypassAutocropTransparentPadding);
  const deferRequiredMetadataValidation = Boolean(options?.deferRequiredMetadataValidation);
  const response = await fetch(`${API_BASE}/assets/import-url`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      url,
      filename,
      source_context: sourceContext || undefined,
      bypass_autocrop_transparent_padding: bypassAutocropTransparentPadding,
      defer_required_metadata_validation: deferRequiredMetadataValidation,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to import media URL' }));
    throw new Error(error.detail || 'Failed to import media URL');
  }

  return response.json();
}

export async function renameAssetTag(fromTag, toTag) {
  const response = await fetch(`${API_BASE}/assets/tags/rename`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ from_tag: fromTag, to_tag: toTag }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to rename tag' }));
    throw new Error(error.detail || 'Failed to rename tag');
  }

  return response.json();
}

export async function deleteAssetTag(tag) {
  const response = await fetch(`${API_BASE}/assets/tags/delete`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ tag }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete tag' }));
    throw new Error(error.detail || 'Failed to delete tag');
  }

  return response.json();
}

export async function getAdminMediaConfig() {
  const response = await fetch(`${API_BASE}/admin/media-config`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch admin media config' }));
    throw new Error(error.detail || 'Failed to fetch admin media config');
  }

  return response.json();
}

export async function updateAdminMediaConfig(data) {
  const response = await fetch(`${API_BASE}/admin/media-config`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update admin media config' }));
    throw new Error(error.detail || 'Failed to update admin media config');
  }

  return response.json();
}

// -------------------------
// Pages API
// -------------------------

/**
 * Get a page by slug.
 * @param {string} slug - The page slug
 * @returns {Promise<Object>} Page data
 */
export async function getPage(slug) {
  const encodedSlug = encodeURIComponent(slug);
  const response = await fetch(`${API_BASE}/pages/${encodedSlug}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch page' }));
    // Include status code in error message for better error detection
    const statusText = response.status === 404 ? 'Page not found' : `HTTP ${response.status}`;
    throw new Error(error.detail || statusText);
  }

  return response.json();
}

/**
 * Get a page with all its sections and header populated.
 * @param {string} slug - The page slug
 * @param {boolean} includeHidden - Whether to include hidden sections (default false)
 * @returns {Promise<Object>} Page with populated header and sections
 */
export async function getPageFull(slug, includeHidden = false) {
  if (templateBuilderContext) {
    const response = await fetch(buildTemplateBuilderUrl('/full'), {
      method: 'GET',
      headers: getHeaders(),
      cache: 'no-store',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to fetch template builder page' }));
      const statusText = response.status === 404 ? 'Template not found' : `HTTP ${response.status}`;
      throw new Error(error.detail || statusText);
    }
    return response.json();
  }

  const encodedSlug = encodeURIComponent(slug);
  const params = new URLSearchParams();
  if (includeHidden) {
    params.append('include_hidden', 'true');
  }

  const url = `${API_BASE}/pages/${encodedSlug}/full${params.toString() ? '?' + params : ''}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch page' }));
    // Include status code in error message for better error detection
    const statusText = response.status === 404 ? 'Page not found' : `HTTP ${response.status}`;
    throw new Error(error.detail || statusText);
  }

  return response.json();
}

/**
 * Get a public, SEO-friendly page bundle.
 * @param {string} slug - The page slug
 * @returns {Promise<Object>} Bundle { page, menu_items, footer_items, design_settings, css_snippets, faq, blog, program, seo }
 */
export async function getPublicPageBundle(slug) {
  const encodedSlug = encodeURIComponent(slug);
  const response = await fetch(`${API_BASE}/pages/public/${encodedSlug}`, {
    method: 'GET',
    headers: getHeaders({ includeAuth: false }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch public page bundle' }));
    const statusText = response.status === 404 ? 'Page not found' : `HTTP ${response.status}`;
    throw new Error(error.detail || statusText);
  }

  return response.json();
}

export function recordPublicPageHit(slug) {
  const normalizedSlug = normalizePublicSlugForClientCache(slug);
  if (hasRecordedPublicHitInSession(normalizedSlug)) return;
  markPublicHitRecordedInSession(normalizedSlug);

  const encodedSlug = encodeURIComponent(normalizedSlug);
  const url = `${API_BASE}/pages/public-hit/${encodedSlug}`;

  if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    try {
      if (navigator.sendBeacon(url)) return;
    } catch {
      // Fall through to fetch.
    }
  }

  fetch(url, {
    method: 'POST',
    credentials: 'omit',
    keepalive: true,
  }).catch(() => {});
}

/**
 * Resolve public availability for multiple page slugs in one request.
 * Hidden, under-construction, or missing pages resolve to false.
 * @param {string[]} slugs
 * @returns {Promise<Object<string, boolean>>}
 */
export async function getPublicPagesAvailability(slugs = []) {
  const requestedSlugs = Array.isArray(slugs)
    ? Array.from(
        new Set(
          slugs
            .map((slug) => normalizePublicSlugForClientCache(slug))
            .filter(Boolean),
        ),
      )
    : [];
  if (requestedSlugs.length === 0) return {};

  const now = Date.now();
  prunePublicAvailabilityCache(now);

  const result = {};
  const missingSlugs = [];
  for (const slug of requestedSlugs) {
    const cached = publicAvailabilityCache.get(slug);
    if (cached && Number(cached.expiresAt || 0) > now) {
      result[slug] = cached.value === true;
      continue;
    }
    publicAvailabilityCache.delete(slug);
    missingSlugs.push(slug);
  }

  if (missingSlugs.length === 0) {
    return result;
  }

  const response = await fetch(`${API_BASE}/pages/public-availability`, {
    method: 'POST',
    headers: getHeaders({ includeAuth: false }),
    body: JSON.stringify({
      slugs: missingSlugs,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch public page availability' }));
    throw new Error(error.detail || 'Failed to fetch public page availability');
  }

  const data = await response.json();
  const availability = data?.availability_by_slug;
  const availabilityBySlug = availability && typeof availability === 'object' ? availability : {};
  const expiresAt = Date.now() + PUBLIC_AVAILABILITY_CACHE_TTL_MS;
  for (const slug of missingSlugs) {
    const value = availabilityBySlug?.[slug] === true;
    publicAvailabilityCache.set(slug, { value, expiresAt });
    result[slug] = value;
  }
  prunePublicAvailabilityCache();
  return result;
}

/**
 * Resolve page status metadata for multiple page slugs.
 * @param {string[]} slugs
 * @returns {Promise<Object<string, {exists:boolean,status:string,effective_status:string,is_visible:boolean}>>}
 */
export async function getPagesStatusMeta(slugs = []) {
  const response = await fetch(`${API_BASE}/pages/statuses`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      slugs: Array.isArray(slugs) ? slugs : [],
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch page status metadata' }));
    throw new Error(error.detail || 'Failed to fetch page status metadata');
  }

  const data = await response.json();
  const statusBySlug = data?.status_by_slug;
  return statusBySlug && typeof statusBySlug === 'object' ? statusBySlug : {};
}

// -------------------------
// FAQ API (shared catalog across all faq sections)
// -------------------------

/**
 * Get global shared FAQ data.
 * @returns {Promise<Object>} { items, tags }
 */
export async function getFaqShared() {
  const response = await fetch(`${API_BASE}/faq/shared`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch shared FAQ data' }));
    throw new Error(error.detail || 'Failed to fetch shared FAQ data');
  }

  return response.json();
}

/**
 * Update global shared FAQ data.
 * @param {Object} payload - Partial or full update payload with items/tags
 * @returns {Promise<Object>} { items, tags }
 */
export async function updateFaqShared(payload) {
  const response = await fetch(`${API_BASE}/faq/shared`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update shared FAQ data' }));
    throw new Error(error.detail || 'Failed to update shared FAQ data');
  }

  return response.json();
}

// -------------------------
// Program API (shared catalog across all program sections)
// -------------------------

/**
 * Get global shared program data.
 * @returns {Promise<Object>} { gigs, stages, program_*_integration_mapping, program_*_integration_mapping_cache_state }
 */
export async function getProgramShared({
  day = '',
  stageId = '',
  gigId = '',
  ids = [],
  dayStartHour = null,
  dayEndHour = null,
} = {}) {
  const params = new URLSearchParams();
  if (day) params.set('day', String(day));
  if (stageId) params.set('stage_id', String(stageId));
  if (gigId) params.set('gig_id', String(gigId));
  (Array.isArray(ids) ? ids : []).forEach((id) => {
    const normalized = String(id || '').trim();
    if (normalized) params.append('ids', normalized);
  });
  if (dayStartHour !== null && dayStartHour !== undefined) {
    params.set('day_start_hour', String(dayStartHour));
  }
  if (dayEndHour !== null && dayEndHour !== undefined) {
    params.set('day_end_hour', String(dayEndHour));
  }
  const query = params.toString();
  const response = await fetch(`${API_BASE}/program/shared${query ? `?${query}` : ''}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch shared program data' }));
    throw new Error(error.detail || 'Failed to fetch shared program data');
  }

  return response.json();
}

/**
 * Get public program feed payload for changes + now playing, optionally with ticker.
 * @param {Object} options
 * @param {boolean} options.includeTicker - Include ticker payload from the requested page
 * @param {string} options.page - Public page slug used for ticker lookup and page context
 * @returns {Promise<Object>} { changes, now_playing, ticker, meta }
 */
export async function getProgramPublicFeed({ includeTicker = false, page = '' } = {}) {
  const params = new URLSearchParams();
  params.set('includeTicker', includeTicker ? 'true' : 'false');
  const normalizedPage = String(page || '').trim();
  if (normalizedPage) {
    params.set('page', normalizedPage);
  }

  const response = await fetch(`${API_BASE}/program/public-feed?${params.toString()}`, {
    method: 'GET',
    headers: getHeaders({ includeAuth: false }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch public program feed' }));
    throw new Error(error.detail || 'Failed to fetch public program feed');
  }

  return response.json();
}

/**
 * Update global shared program data.
 * @param {Object} payload - Partial or full update payload with gigs/stages and shared integration metadata
 * @returns {Promise<Object>} { gigs, stages, program_*_integration_mapping, program_*_integration_mapping_cache_state }
 */
export async function updateProgramShared(payload) {
  const response = await fetch(`${API_BASE}/program/shared`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update shared program data' }));
    const detailPayload = Object.prototype.hasOwnProperty.call(error || {}, "detail")
      ? error.detail
      : error;
    const message = typeof detailPayload === "string"
      ? detailPayload
      : (typeof detailPayload?.message === "string" && detailPayload.message.trim())
        ? detailPayload.message.trim()
      : (error?.message || 'Failed to update shared program data');
    const enriched = new Error(message || 'Failed to update shared program data');
    enriched.detail_payload = detailPayload;
    enriched.status_code = response.status;
    throw enriched;
  }

  return response.json();
}

/**
 * Update one shared program gig.
 * @param {string} gigId - Shared program gig id
 * @param {Object} payload - { gig }
 * @returns {Promise<Object>} { gig, item_page_generation_jobs }
 */
export async function updateProgramSharedGig(gigId, payload) {
  const normalizedGigId = String(gigId || '').trim();
  if (!normalizedGigId) {
    throw new Error('Missing program gig ID');
  }
  const response = await fetch(`${API_BASE}/program/shared/gigs/${encodeURIComponent(normalizedGigId)}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update shared program gig' }));
    const detailPayload = Object.prototype.hasOwnProperty.call(error || {}, "detail")
      ? error.detail
      : error;
    const message = typeof detailPayload === "string"
      ? detailPayload
      : (typeof detailPayload?.message === "string" && detailPayload.message.trim())
        ? detailPayload.message.trim()
      : (error?.message || 'Failed to update shared program gig');
    const enriched = new Error(message || 'Failed to update shared program gig');
    enriched.detail_payload = detailPayload;
    enriched.status_code = response.status;
    throw enriched;
  }

  return response.json();
}

/**
 * Create a new page.
 * @param {Object} data - Page data with slug
 * @returns {Promise<Object>} Created page
 */
export async function createPage(data) {
  if (templateBuilderContext) {
    const response = await fetch(buildTemplateBuilderUrl('', { includePath: true }), {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data || {}),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to create template builder page' }));
      throw new Error(error.detail || 'Failed to create template builder page');
    }
    return response.json();
  }

  const response = await fetch(`${API_BASE}/pages`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create page' }));
    throw new Error(error.detail || 'Failed to create page');
  }

  return response.json();
}

/**
 * Update a page.
 * @param {string} slug - The page slug
 * @param {Object} data - Page update data
 * @returns {Promise<Object>} Updated page
 */
export async function updatePage(slug, data) {
  if (templateBuilderContext) {
    const response = await fetch(buildTemplateBuilderUrl('', { includePath: true }), {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(data || {}),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to update template page' }));
      throw new Error(error.detail || 'Failed to update template page');
    }
    return response.json();
  }

  const encodedSlug = encodeURIComponent(slug);
  const response = await fetch(`${API_BASE}/pages/${encodedSlug}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update page' }));
    throw new Error(error.detail || 'Failed to update page');
  }

  return response.json();
}

/**
 * Sync a generated item page's managed section grid/mapping from its source template.
 * @param {string} slug - The page slug
 * @param {Object} options
 * @param {string} options.syncMode - Optional mapped-field conflict policy
 * @param {boolean} options.forceRebuild - Rebuild the generated page from template/source data
 * @returns {Promise<Object>} Sync report
 */
export async function syncPageFromTemplate(slug, { syncMode = '', forceRebuild = false } = {}) {
  if (templateBuilderContext) {
    throw new Error('Template sync is not available in template mode.');
  }

  const encodedSlug = encodeURIComponent(slug);
  const params = new URLSearchParams();
  const normalizedSyncMode = String(syncMode || '').trim();
  if (normalizedSyncMode) params.set('sync_mode', normalizedSyncMode);
  if (forceRebuild) params.set('force_rebuild', '1');
  const query = params.toString();
  const response = await fetch(`${API_BASE}/pages/${encodedSlug}/sync-from-template${query ? `?${query}` : ''}`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to sync page from template' }));
    throw new Error(resolveErrorDetailMessage(error, 'Failed to sync page from template'));
  }

  return response.json();
}

/**
 * Check mapped-field conflicts for a generated item page without writing changes.
 * @param {string} slug - The page slug
 * @returns {Promise<Object>} Conflict report
 */
export async function getPageTemplateSyncConflicts(slug) {
  if (templateBuilderContext) {
    throw new Error('Template sync conflict checks are not available in template mode.');
  }

  const encodedSlug = encodeURIComponent(slug);
  const response = await fetch(`${API_BASE}/pages/${encodedSlug}/sync-from-template/conflicts`, {
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to check page sync conflicts' }));
    throw new Error(resolveErrorDetailMessage(error, 'Failed to check page sync conflicts'));
  }

  return response.json();
}

/**
 * Move a page subtree to a new parent route (updates slug paths).
 * @param {string} slug - Root slug of the subtree to move
 * @param {Object} data
 * @param {string|null} [data.target_parent_slug] - New parent slug, or null for root
 * @returns {Promise<Object>} Move result
 */
export async function movePageSubtree(slug, data = {}) {
  const encodedSlug = encodeURIComponent(slug);
  const response = await fetch(`${API_BASE}/pages/${encodedSlug}/move-subtree`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to move subtree' }));
    throw new Error(error.detail || 'Failed to move subtree');
  }

  return response.json();
}

/**
 * Rename a page route (slug). Descendants are rewritten accordingly.
 * Permanent generated redirects are created from old to new routes.
 * @param {string} slug - Current page slug
 * @param {Object} data
 * @param {string} data.new_slug - New page slug
 * @returns {Promise<Object>} Rename result
 */
export async function renamePageRoute(slug, data = {}) {
  const encodedSlug = encodeURIComponent(slug);
  const response = await fetch(`${API_BASE}/pages/${encodedSlug}/rename`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to rename page route' }));
    throw new Error(error.detail || 'Failed to rename page route');
  }

  return response.json();
}

/**
 * List all pages.
 * @param {Object} options - Query options
 * @param {number} options.limit - Items per page (default 30)
 * @param {string} options.cursor - Pagination cursor (optional)
 * @returns {Promise<Array>} List of pages
 */
export async function listPages({ limit = 30, cursor = null, includeHidden = false } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) {
    params.append('cursor', cursor);
  }
  if (includeHidden) {
    params.append('include_hidden', 'true');
  }

  const response = await fetch(`${API_BASE}/pages?${params}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list pages' }));
    throw new Error(error.detail || 'Failed to list pages');
  }

  return response.json();
}

/**
 * Get pages marked for inclusion in the navigation menu.
 * @param {Object} options - Query options
 * @param {boolean} options.includeHidden - Include non-visible pages (for admin preview)
 * @returns {Promise<Array>} List of internal/external menu items
 */
export async function getMenuItems({ includeHidden = false } = {}) {
  const params = new URLSearchParams();
  if (includeHidden) {
    params.append('include_hidden', 'true');
  }
  
  const url = `${API_BASE}/pages/menu/items${params.toString() ? '?' + params : ''}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get menu items' }));
    throw new Error(error.detail || 'Failed to get menu items');
  }

  return response.json();
}

/**
 * Get pages marked for inclusion in footer links.
 * @param {Object} options - Query options
 * @param {boolean} options.includeHidden - Include non-visible pages (for admin preview)
 * @returns {Promise<Array>} List of internal/external footer items
 */
export async function getFooterItems({ includeHidden = false } = {}) {
  const params = new URLSearchParams();
  if (includeHidden) {
    params.append('include_hidden', 'true');
  }

  const url = `${API_BASE}/pages/footer/items${params.toString() ? '?' + params : ''}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get footer items' }));
    throw new Error(error.detail || 'Failed to get footer items');
  }

  return response.json();
}

/**
 * Get configurable external navigation/footer links from sitemap admin config.
 * @returns {Promise<{nav_external_links:Array, footer_external_links:Array, topbar_logo_url:string|null, topbar_logo_responsive_variants:Array, footer_logo_url:string|null, footer_logo_responsive_variants:Array}>}
 */
export async function getSitemapNavigationLinks() {
  const response = await fetch(`${API_BASE}/sitemap/navigation-links`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch sitemap navigation links' }));
    throw new Error(error.detail || 'Failed to fetch sitemap navigation links');
  }

  return response.json();
}

/**
 * Replace configurable external navigation/footer links.
 * @param {Object} payload
 * @param {Array} payload.nav_external_links
 * @param {Array} payload.footer_external_links
 * @param {string|null} payload.topbar_logo_url
 * @param {string|null} payload.footer_logo_url
 * @returns {Promise<{nav_external_links:Array, footer_external_links:Array, topbar_logo_url:string|null, topbar_logo_responsive_variants:Array, footer_logo_url:string|null, footer_logo_responsive_variants:Array}>}
 */
export async function updateSitemapNavigationLinks(payload = {}) {
  const rawTopbarLogoUrl = payload.topbar_logo_url;
  const normalizedTopbarLogoUrl = rawTopbarLogoUrl == null
    ? null
    : String(rawTopbarLogoUrl).trim();
  const rawFooterLogoUrl = payload.footer_logo_url;
  const normalizedFooterLogoUrl = rawFooterLogoUrl == null
    ? null
    : String(rawFooterLogoUrl).trim();

  const response = await fetch(`${API_BASE}/sitemap/navigation-links`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify({
      nav_external_links: Array.isArray(payload.nav_external_links) ? payload.nav_external_links : [],
      footer_external_links: Array.isArray(payload.footer_external_links) ? payload.footer_external_links : [],
      topbar_logo_url: normalizedTopbarLogoUrl || null,
      footer_logo_url: normalizedFooterLogoUrl || null,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update sitemap navigation links' }));
    throw new Error(error.detail || 'Failed to update sitemap navigation links');
  }

  return response.json();
}

/**
 * Get sitemap summary and generation metadata.
 * @returns {Promise<Object>} Sitemap summary payload
 */
export async function getSitemapSummary() {
  const response = await fetch(`${API_BASE}/sitemap/summary`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch sitemap summary' }));
    throw new Error(error.detail || 'Failed to fetch sitemap summary');
  }

  return response.json();
}

/**
 * Trigger a sitemap.xml regeneration run.
 * @returns {Promise<Object>} Regeneration result
 */
export async function regenerateSitemap() {
  const response = await fetch(`${API_BASE}/sitemap/regenerate`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to regenerate sitemap' }));
    throw new Error(error.detail || 'Failed to regenerate sitemap');
  }

  return response.json();
}

/**
 * Get sitemap page-hit stats for admin charts.
 * @param {Object} options
 * @param {number|string} options.days
 * @returns {Promise<Object>} Stats payload
 */
export async function getSitemapStats({ days = 30 } = {}) {
  const params = new URLSearchParams();
  params.set('days', String(days || 30));
  const response = await fetch(`${API_BASE}/sitemap/stats?${params.toString()}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch sitemap stats' }));
    throw new Error(error.detail || 'Failed to fetch sitemap stats');
  }

  return response.json();
}

/**
 * Reset all sitemap page-hit stats.
 * @returns {Promise<Object>} Reset result
 */
export async function resetSitemapStats() {
  const response = await fetch(`${API_BASE}/sitemap/stats/reset`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to reset sitemap stats' }));
    throw new Error(error.detail || 'Failed to reset sitemap stats');
  }

  return response.json();
}

/**
 * Get robots.txt generation payload for admin.
 * @returns {Promise<Object>} Robots payload
 */
export async function getSitemapRobots() {
  const response = await fetch(`${API_BASE}/sitemap/robots`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch robots config' }));
    throw new Error(error.detail || 'Failed to fetch robots config');
  }

  return response.json();
}

/**
 * Update custom robots.txt content.
 * @param {string} customRobotsTxt
 * @returns {Promise<Object>} Updated robots payload
 */
export async function updateSitemapRobots(customRobotsTxt) {
  const response = await fetch(`${API_BASE}/sitemap/robots`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify({ custom_robots_txt: String(customRobotsTxt || '') }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update robots config' }));
    throw new Error(error.detail || 'Failed to update robots config');
  }

  return response.json();
}

/**
 * Get generated .htaccess client caching rules for admin.
 * @returns {Promise<{rules:Array, defaults:Object, htaccess_text:string}>}
 */
export async function getSitemapCaching() {
  const response = await fetch(`${API_BASE}/sitemap/caching`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch caching config' }));
    throw new Error(error.detail || 'Failed to fetch caching config');
  }

  return response.json();
}

/**
 * Update generated .htaccess client caching rules.
 * @param {Object} payload
 * @param {Array} payload.rules
 * @returns {Promise<{rules:Array, defaults:Object, htaccess_text:string}>}
 */
export async function updateSitemapCaching(payload = {}) {
  const response = await fetch(`${API_BASE}/sitemap/caching`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify({
      rules: Array.isArray(payload.rules) ? payload.rules : [],
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update caching config' }));
    throw new Error(error.detail || 'Failed to update caching config');
  }

  return response.json();
}

/**
 * List custom + generated redirects managed by sitemap tooling.
 * @param {Object} options
 * @param {boolean} options.includeExpired
 * @returns {Promise<Array>} Redirect list
 */
export async function listSitemapRedirects({ includeExpired = true } = {}) {
  const params = new URLSearchParams();
  if (includeExpired) {
    params.append('include_expired', 'true');
  } else {
    params.append('include_expired', 'false');
  }
  const response = await fetch(`${API_BASE}/sitemap/redirects?${params.toString()}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list redirects' }));
    throw new Error(error.detail || 'Failed to list redirects');
  }

  return response.json();
}

/**
 * Create a custom redirect.
 * @param {Object} data
 * @returns {Promise<Object>} Created redirect
 */
export async function createSitemapRedirect(data) {
  const response = await fetch(`${API_BASE}/sitemap/redirects`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create redirect' }));
    throw new Error(error.detail || 'Failed to create redirect');
  }

  return response.json();
}

/**
 * Update a redirect.
 * @param {string} redirectId
 * @param {Object} data
 * @returns {Promise<Object>} Updated redirect
 */
export async function updateSitemapRedirect(redirectId, data) {
  const response = await fetch(`${API_BASE}/sitemap/redirects/${encodeURIComponent(redirectId)}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update redirect' }));
    throw new Error(error.detail || 'Failed to update redirect');
  }

  return response.json();
}

/**
 * Delete a redirect.
 * @param {string} redirectId
 * @returns {Promise<Object>} Delete confirmation
 */
export async function deleteSitemapRedirect(redirectId) {
  const response = await fetch(`${API_BASE}/sitemap/redirects/${encodeURIComponent(redirectId)}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete redirect' }));
    throw new Error(error.detail || 'Failed to delete redirect');
  }

  return response.json();
}

/**
 * Resolve an active redirect for an internal path.
 * Public endpoint (no auth required).
 * @param {string} path - Internal path, e.g. /old/path
 * @returns {Promise<{found: boolean, redirect?: Object}>}
 */
export async function resolveSitemapRedirect(path) {
  const params = new URLSearchParams({ path: String(path || '') });
  const response = await fetch(`${API_BASE}/sitemap/redirects/resolve?${params.toString()}`, {
    method: 'GET',
    headers: getHeaders({ includeAuth: true }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to resolve redirect' }));
    throw new Error(error.detail || 'Failed to resolve redirect');
  }

  return response.json();
}

/**
 * Delete a page.
 * @param {string} slug - The page slug
 * @returns {Promise<Object>} Delete confirmation
 */
export async function deletePage(slug) {
  const encodedSlug = encodeURIComponent(slug);
  const response = await fetch(`${API_BASE}/pages/${encodedSlug}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete page' }));
    throw new Error(error.detail || 'Failed to delete page');
  }

  return response.json();
}

// -------------------------
// Page Header API
// -------------------------

/**
 * Create or update the header for a page.
 * If the page already has a header, it will be updated.
 * If not, a new header will be created and attached.
 * @param {string} slug - The page slug
 * @param {Object} data - Header data
 * @returns {Promise<Object>} Header data
 */
export async function updatePageHeader(slug, data) {
  if (templateBuilderContext) {
    const response = await fetch(buildTemplateBuilderUrl('/header', { includePath: true }), {
      method: 'PUT',
      headers: getHeaders(),
      body: JSON.stringify(data || {}),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to update template header' }));
      throw new Error(error.detail || 'Failed to update template header');
    }

    return response.json();
  }

  const encodedSlug = encodeURIComponent(slug);
  const response = await fetch(`${API_BASE}/pages/${encodedSlug}/header`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update header' }));
    throw new Error(error.detail || 'Failed to update header');
  }

  return response.json();
}

/**
 * Detach header from a page (does not delete the header).
 * @param {string} slug - The page slug
 * @returns {Promise<Object>} Confirmation
 */
export async function detachPageHeader(slug) {
  const encodedSlug = encodeURIComponent(slug);
  const response = await fetch(`${API_BASE}/pages/${encodedSlug}/header`, {
    method: 'DELETE',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to detach header' }));
    throw new Error(error.detail || 'Failed to detach header');
  }

  return response.json();
}

// -------------------------
// Headers API
// -------------------------

/**
 * Get a header by ID.
 * @param {string} headerId - The header ID
 * @returns {Promise<Object>} Header data
 */
export async function getHeader(headerId) {
  if (isTemplateHeaderBuilderId(headerId) || templateBuilderContext) {
    const encodedHeaderId = encodeURIComponent(String(headerId || ''));
    const response = await fetch(`${API_BASE}/admin/templates/builder/header/${encodedHeaderId}`, {
      method: 'GET',
      headers: getHeaders(),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to fetch template header' }));
      throw new Error(error.detail || 'Failed to fetch template header');
    }

    return response.json();
  }

  const response = await fetch(`${API_BASE}/headers/${headerId}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch header' }));
    throw new Error(error.detail || 'Failed to fetch header');
  }

  return response.json();
}

/**
 * Create a new header.
 * @param {Object} data - Header data
 * @returns {Promise<Object>} Created header
 */
export async function createHeader(data) {
  if (templateBuilderContext) {
    throw new Error('Header library is not available in template mode. Use page header editing directly.');
  }

  const response = await fetch(`${API_BASE}/headers`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create header' }));
    throw new Error(error.detail || 'Failed to create header');
  }

  return response.json();
}

/**
 * Update a header by ID.
 * @param {string} headerId - The header ID
 * @param {Object} data - Header data
 * @returns {Promise<Object>} Updated header
 */
export async function updateHeader(headerId, data) {
  if (isTemplateHeaderBuilderId(headerId) || templateBuilderContext) {
    const encodedHeaderId = encodeURIComponent(String(headerId || ''));
    const response = await fetch(`${API_BASE}/admin/templates/builder/header/${encodedHeaderId}`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(data || {}),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to update template header' }));
      throw new Error(error.detail || 'Failed to update template header');
    }

    return response.json();
  }

  const response = await fetch(`${API_BASE}/headers/${headerId}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update header' }));
    throw new Error(error.detail || 'Failed to update header');
  }

  return response.json();
}

/**
 * Delete a header by ID.
 * @param {string} headerId - The header ID
 * @returns {Promise<Object>} Delete confirmation
 */
export async function deleteHeader(headerId) {
  if (templateBuilderContext) {
    throw new Error('Header library delete is not available in template mode.');
  }

  const response = await fetch(`${API_BASE}/headers/${headerId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete header' }));
    throw new Error(error.detail || 'Failed to delete header');
  }

  return response.json();
}

/**
 * Count headers that are neither shared nor used on any page.
 * @returns {Promise<Object>} Count result { count }
 */
export async function getUnusedHeadersCount() {
  if (templateBuilderContext) {
    return { count: 0 };
  }

  const response = await fetch(`${API_BASE}/headers/unused/count`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to count unused headers' }));
    throw new Error(error.detail || 'Failed to count unused headers');
  }

  return response.json();
}

/**
 * Delete headers that are neither shared nor used on any page.
 * @returns {Promise<Object>} Delete result { deleted_count, deleted_ids }
 */
export async function deleteUnusedHeaders() {
  if (templateBuilderContext) {
    throw new Error('Header library delete is not available in template mode.');
  }

  const response = await fetch(`${API_BASE}/headers/unused`, {
    method: 'DELETE',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete unused headers' }));
    throw new Error(error.detail || 'Failed to delete unused headers');
  }

  return response.json();
}

/**
 * List all headers with usage information (which pages use them).
 * @param {Object} options - Query options
 * @param {number} options.limit - Items per page (default 100)
 * @param {number} options.offset - Result offset (default 0)
 * @param {string} options.headerType - Filter by header type (optional)
 * @param {string} options.sortBy - Sort field (created_at, updated_at, name)
 * @param {string} options.sortDirection - Sort direction (asc or desc)
 * @param {boolean} options.sharedOnly - Only return shared reusable headers
 * @param {boolean} options.includeTotal - Return { items, total, limit, offset }
 * @returns {Promise<Array|Object>} List of headers with usage info, or paged result
 */
export async function listHeadersWithUsage({
  limit = 100,
  offset = 0,
  headerType = '',
  sortBy = '',
  sortDirection = '',
  sharedOnly = false,
  includeTotal = false,
} = {}) {
  if (templateBuilderContext) {
    if (includeTotal) {
      return { items: [], total: 0, limit, offset };
    }
    return [];
  }

  const params = new URLSearchParams({ limit: String(limit) });
  params.set('offset', String(offset));
  if (headerType) {
    params.set('header_type', headerType);
  }
  if (sortBy) {
    params.set('sort_by', sortBy);
  }
  if (sortDirection) {
    params.set('sort_direction', sortDirection);
  }
  if (sharedOnly) {
    params.set('shared_only', 'true');
  }
  if (includeTotal) {
    params.set('include_total', 'true');
  }

  const response = await fetch(`${API_BASE}/headers/with-usage?${params}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list headers' }));
    throw new Error(error.detail || 'Failed to list headers');
  }

  return response.json();
}

/**
 * Get usage information for a header (which pages use it).
 * @param {string} headerId - The header ID
 * @returns {Promise<Object>} Usage info { header_id, usage, usage_count, can_delete }
 */
export async function getHeaderUsage(headerId) {
  if (templateBuilderContext) {
    return { header_id: String(headerId || ''), usage: [], usage_count: 0, can_delete: false };
  }

  const response = await fetch(`${API_BASE}/headers/${headerId}/usage`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get header usage' }));
    throw new Error(error.detail || 'Failed to get header usage');
  }

  return response.json();
}

/**
 * Attach an existing header to a page (replacing current header reference).
 * @param {string} slug - The page slug
 * @param {string} headerId - The header ID to attach
 * @returns {Promise<Object>} Updated page
 */
export async function attachHeaderToPage(slug, headerId) {
  if (templateBuilderContext) {
    throw new Error('Attaching existing headers is not available in template mode.');
  }

  const encodedSlug = encodeURIComponent(slug);
  const params = new URLSearchParams({ header_id: headerId });

  const response = await fetch(`${API_BASE}/pages/${encodedSlug}/header/attach?${params}`, {
    method: 'PATCH',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to attach header' }));
    throw new Error(error.detail || 'Failed to attach header');
  }

  return response.json();
}

/**
 * Get header revision history.
 * @param {string} headerId - The header ID
 * @returns {Promise<Array>} List of revisions
 */
export async function getHeaderRevisions(headerId) {
  if (templateBuilderContext || isTemplateHeaderBuilderId(headerId)) {
    return { enabled: false, current: null, history: [], future: [] };
  }

  const response = await fetch(`${API_BASE}/headers/${headerId}/revisions`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch revisions' }));
    throw new Error(error.detail || 'Failed to fetch revisions');
  }

  return response.json();
}

// -------------------------
// Sections API
// -------------------------

/**
 * Get a section by ID.
 * @param {string} sectionId - The section ID
 * @returns {Promise<Object>} Section data
 */
export async function getSection(sectionId) {
  const templateRef = parseTemplateSectionBuilderId(sectionId);
  if (templateRef || templateBuilderContext) {
    const encodedId = encodeURIComponent(String(sectionId || ''));
    const response = await fetch(`${API_BASE}/admin/templates/builder/sections/${encodedId}`, {
      method: 'GET',
      headers: getHeaders(),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to fetch template section' }));
      throw new Error(error.detail || 'Failed to fetch template section');
    }

    return response.json();
  }

  const response = await fetch(`${API_BASE}/sections/${sectionId}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch section' }));
    throw new Error(error.detail || 'Failed to fetch section');
  }

  return response.json();
}

/**
 * Preview template-managed field differences for a section instance.
 * @param {string} sectionId - The section ID
 * @returns {Promise<Object>} Diff metadata
 */
export async function getSectionTemplateSyncPreview(sectionId) {
  const templateRef = parseTemplateSectionBuilderId(sectionId);
  if (templateRef || templateBuilderContext) {
    const resolvedKind = templateRef?.kind || getTemplateContextOrThrow().kind;
    const encodedId = encodeURIComponent(String(sectionId || ''));
    const response = await fetch(
      `${API_BASE}/admin/templates/builder/${resolvedKind}/sections/${encodedId}/template-sync-preview`,
      {
        method: 'GET',
        headers: getHeaders(),
      },
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to preview section template sync' }));
      throw new Error(error.detail || 'Failed to preview section template sync');
    }

    return response.json();
  }

  const response = await fetch(`${API_BASE}/sections/${sectionId}/template-sync-preview`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to preview section template sync' }));
    throw new Error(error.detail || 'Failed to preview section template sync');
  }

  return response.json();
}

/**
 * Sync template-managed fields from the source section template to an instance section.
 * @param {string} sectionId - The section ID
 * @returns {Promise<Object>} Sync result
 */
export async function syncSectionFromTemplate(sectionId) {
  const templateRef = parseTemplateSectionBuilderId(sectionId);
  if (templateRef || templateBuilderContext) {
    const resolvedKind = templateRef?.kind || getTemplateContextOrThrow().kind;
    const encodedId = encodeURIComponent(String(sectionId || ''));
    const response = await fetch(
      `${API_BASE}/admin/templates/builder/${resolvedKind}/sections/${encodedId}/sync-from-template`,
      {
        method: 'POST',
        headers: getHeaders(),
      },
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to sync section from template' }));
      throw new Error(error.detail || 'Failed to sync section from template');
    }

    return response.json();
  }

  const response = await fetch(`${API_BASE}/sections/${sectionId}/sync-from-template`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to sync section from template' }));
    throw new Error(error.detail || 'Failed to sync section from template');
  }

  return response.json();
}

/**
 * Create a new section.
 * @param {Object} data - Section data
 * @returns {Promise<Object>} Created section
 */
export async function createSection(data) {
  if (templateBuilderContext) {
    throw new Error('Standalone section creation is not available in template mode.');
  }

  const response = await fetch(`${API_BASE}/sections`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create section' }));
    throw new Error(error.detail || 'Failed to create section');
  }

  return response.json();
}

/**
 * Update a section by ID (partial update).
 * @param {string} sectionId - The section ID
 * @param {Object} data - Section data
 * @returns {Promise<Object>} Updated section
 */
export async function updateSection(sectionId, data) {
  const templateRef = parseTemplateSectionBuilderId(sectionId);
  if (templateRef || templateBuilderContext) {
    const resolvedKind = templateRef?.kind || getTemplateContextOrThrow().kind;
    const encodedId = encodeURIComponent(String(sectionId || ''));
    const response = await fetch(`${API_BASE}/admin/templates/builder/${resolvedKind}/sections/${encodedId}/content`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(data || {}),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to update template section' }));
      throw new Error(resolveErrorDetailMessage(error, 'Failed to update template section'));
    }

    return response.json();
  }

  const response = await fetch(`${API_BASE}/sections/${sectionId}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update section' }));
    throw new Error(resolveErrorDetailMessage(error, 'Failed to update section'));
  }

  return response.json();
}

/**
 * Generate managed item pages for a section.
 * @param {string} sectionId
 * @param {Object} options
 * @param {string} options.itemKind - Optional kind filter (e.g. stage, gig, all)
 * @param {string} options.itemId - Optional single-item ID for targeted regeneration
 * @param {boolean} options.forceRebuild - Optional explicit full rebuild for template-refresh actions
 * @param {string} options.syncMode - Optional mapped-field conflict policy
 * @returns {Promise<Object>}
 */
export async function generateSectionItemPages(
  sectionId,
  { itemKind = '', itemId = '', forceRebuild = false, syncMode = '' } = {},
) {
  const params = new URLSearchParams();
  const normalizedKind = String(itemKind || '').trim();
  const normalizedItemId = String(itemId || '').trim();
  const normalizedSyncMode = String(syncMode || '').trim();
  if (normalizedKind) {
    params.set('item_kind', normalizedKind);
  }
  if (normalizedItemId) {
    params.set('item_id', normalizedItemId);
  }
  if (forceRebuild) {
    params.set('force_rebuild', '1');
  }
  if (normalizedSyncMode) {
    params.set('sync_mode', normalizedSyncMode);
  }
  const query = params.toString();
  const response = await fetch(`${API_BASE}/sections/${sectionId}/item-pages/generate${query ? `?${query}` : ''}`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to generate item pages' }));
    throw new Error(error.detail || 'Failed to generate item pages');
  }

  return response.json();
}

/**
 * Cleanup managed item pages for a section.
 * @param {string} sectionId
 * @param {Object} options
 * @param {string} options.itemKind - Optional kind filter (e.g. stage, gig, all)
 * @returns {Promise<Object>}
 */
export async function cleanupSectionItemPages(sectionId, { itemKind = '' } = {}) {
  const params = new URLSearchParams();
  const normalizedKind = String(itemKind || '').trim();
  if (normalizedKind) {
    params.set('item_kind', normalizedKind);
  }
  const query = params.toString();
  const response = await fetch(`${API_BASE}/sections/${sectionId}/item-pages/cleanup${query ? `?${query}` : ''}`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to cleanup item pages' }));
    throw new Error(error.detail || 'Failed to cleanup item pages');
  }

  return response.json();
}

/**
 * Poll item-page generation job status.
 * @param {string} jobId
 * @returns {Promise<Object>}
 */
export async function getSectionItemPageGenerationJob(jobId) {
  const normalizedJobId = String(jobId || '').trim();
  if (!normalizedJobId) {
    throw new Error('Missing item-page generation job id');
  }
  const response = await fetch(`${API_BASE}/sections/item-pages/jobs/${normalizedJobId}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch item-page generation job' }));
    throw new Error(error.detail || 'Failed to fetch item-page generation job');
  }

  return response.json();
}

/**
 * Delete a section by ID.
 * @param {string} sectionId - The section ID
 * @returns {Promise<Object>} Delete confirmation
 */
export async function deleteSection(sectionId) {
  if (templateBuilderContext) {
    throw new Error('Deleting standalone sections is not available in template mode.');
  }

  const response = await fetch(`${API_BASE}/sections/${sectionId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete section' }));
    throw new Error(error.detail || 'Failed to delete section');
  }

  return response.json();
}

/**
 * Count sections that are neither shared nor used on any page.
 * @returns {Promise<Object>} Count result { count }
 */
export async function getUnusedSectionsCount() {
  if (templateBuilderContext) {
    return { count: 0 };
  }

  const response = await fetch(`${API_BASE}/sections/unused/count`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to count unused sections' }));
    throw new Error(error.detail || 'Failed to count unused sections');
  }

  return response.json();
}

/**
 * Delete sections that are neither shared nor used on any page.
 * @returns {Promise<Object>} Delete result { deleted_count, deleted_ids }
 */
export async function deleteUnusedSections() {
  if (templateBuilderContext) {
    throw new Error('Section library delete is not available in template mode.');
  }

  const response = await fetch(`${API_BASE}/sections/unused`, {
    method: 'DELETE',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete unused sections' }));
    throw new Error(error.detail || 'Failed to delete unused sections');
  }

  return response.json();
}

/**
 * List all sections with optional filtering.
 * @param {Object} options - Query options
 * @param {number} options.limit - Items per page (default 50)
 * @param {string} options.cursor - Pagination cursor (optional)
 * @param {string} options.search - Search query (optional)
 * @param {string} options.sectionType - Filter by section type (optional)
 * @param {boolean} options.sharedOnly - Only return shared reusable sections
 * @returns {Promise<Array>} List of sections
 */
export async function listSections({ limit = 50, cursor = null, search = '', sectionType = '', sharedOnly = false } = {}) {
  if (templateBuilderContext) {
    return [];
  }

  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) {
    params.append('cursor', cursor);
  }
  if (search) {
    params.append('search', search);
  }
  if (sectionType) {
    params.append('section_type', sectionType);
  }
  if (sharedOnly) {
    params.append('shared_only', 'true');
  }

  const response = await fetch(`${API_BASE}/sections?${params}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list sections' }));
    throw new Error(error.detail || 'Failed to list sections');
  }

  return response.json();
}

/**
 * List all sections with usage information (which pages use them).
 * @param {Object} options - Query options
 * @param {number} options.limit - Items per page (default 100)
 * @param {number} options.offset - Result offset (default 0)
 * @param {string} options.search - Search query (optional)
 * @param {string} options.sectionType - Filter by section type (optional)
 * @param {string} options.sortBy - Sort field (created_at, updated_at, name)
 * @param {string} options.sortDirection - Sort direction (asc or desc)
 * @param {boolean} options.includeTotal - Return { items, total, limit, offset }
 * @param {boolean} options.sharedOnly - Only return shared reusable sections
 * @param {string} options.typeData - type_data detail: admin_todos, none, or full
 * @returns {Promise<Array|Object>} List of sections with usage info, or paged result
 */
export async function listSectionsWithUsage({
  limit = 100,
  offset = 0,
  search = '',
  sectionType = '',
  sortBy = '',
  sortDirection = '',
  includeTotal = false,
  sharedOnly = false,
  typeData = 'admin_todos',
} = {}) {
  if (templateBuilderContext) {
    if (includeTotal) {
      return { items: [], total: 0, limit, offset };
    }
    return [];
  }

  const params = new URLSearchParams({ limit: String(limit) });
  params.set('offset', String(offset));
  params.set('type_data', typeData);
  if (sortBy) {
    params.set('sort_by', sortBy);
  }
  if (sortDirection) {
    params.set('sort_direction', sortDirection);
  }
  if (includeTotal) {
    params.set('include_total', 'true');
  }
  if (sharedOnly) {
    params.set('shared_only', 'true');
  }
  if (search) {
    params.append('search', search);
  }
  if (sectionType) {
    params.append('section_type', sectionType);
  }

  const response = await fetch(`${API_BASE}/sections/with-usage?${params}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list sections' }));
    throw new Error(error.detail || 'Failed to list sections');
  }

  return response.json();
}

/**
 * Get usage information for a section (which pages use it).
 * @param {string} sectionId - The section ID
 * @returns {Promise<Object>} Usage info { section_id, usage, usage_count, can_delete }
 */
export async function getSectionUsage(sectionId) {
  if (templateBuilderContext) {
    return { section_id: String(sectionId || ''), usage: [], usage_count: 0, can_delete: false };
  }

  const response = await fetch(`${API_BASE}/sections/${sectionId}/usage`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get section usage' }));
    throw new Error(error.detail || 'Failed to get section usage');
  }

  return response.json();
}

/**
 * Get revision entries for a section (current + history + future).
 * @param {string} sectionId - The section ID
 * @returns {Promise<Object>} Revision lists for history UI
 */
export async function getSectionRevisions(sectionId) {
  if (templateBuilderContext || parseTemplateSectionBuilderId(sectionId)) {
    return { enabled: false, current: null, history: [], future: [] };
  }

  const response = await fetch(`${API_BASE}/sections/${sectionId}/revisions`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch section revisions' }));
    throw new Error(error.detail || 'Failed to fetch section revisions');
  }

  return response.json();
}

/**
 * Get undo/redo status for a section.
 * @param {string} sectionId - The section ID
 * @returns {Promise<Object>} Revision status { can_undo, can_redo, history_count, future_count }
 */
export async function getSectionRevisionStatus(sectionId) {
  if (templateBuilderContext || parseTemplateSectionBuilderId(sectionId)) {
    return { enabled: false, can_undo: false, can_redo: false, history_count: 0, future_count: 0 };
  }

  const response = await fetch(`${API_BASE}/sections/${sectionId}/revisions/status`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    return { enabled: true, can_undo: false, can_redo: false, history_count: 0, future_count: 0 };
  }

  return response.json();
}

/**
 * Undo the last change to a section.
 * @param {string} sectionId - The section ID
 * @returns {Promise<Object>} Updated section
 */
export async function undoSection(sectionId) {
  if (templateBuilderContext || parseTemplateSectionBuilderId(sectionId)) {
    throw new Error('Undo is not available in template mode.');
  }

  const response = await fetch(`${API_BASE}/sections/${sectionId}/undo`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to undo' }));
    throw new Error(error.detail || 'Failed to undo');
  }

  return response.json();
}

/**
 * Redo a previously undone change to a section.
 * @param {string} sectionId - The section ID
 * @returns {Promise<Object>} Updated section
 */
export async function redoSection(sectionId) {
  if (templateBuilderContext || parseTemplateSectionBuilderId(sectionId)) {
    throw new Error('Redo is not available in template mode.');
  }

  const response = await fetch(`${API_BASE}/sections/${sectionId}/redo`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to redo' }));
    throw new Error(error.detail || 'Failed to redo');
  }

  return response.json();
}

/**
 * Get undo/redo status for a header.
 * @param {string} headerId - The header ID
 * @returns {Promise<Object>} Revision status { can_undo, can_redo, history_count, future_count }
 */
export async function getHeaderRevisionStatus(headerId) {
  if (templateBuilderContext || isTemplateHeaderBuilderId(headerId)) {
    return { enabled: false, can_undo: false, can_redo: false, history_count: 0, future_count: 0 };
  }

  const response = await fetch(`${API_BASE}/headers/${headerId}/revisions/status`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    return { enabled: true, can_undo: false, can_redo: false, history_count: 0, future_count: 0 };  }

  return response.json();
}

/**
 * Undo the last change to a header.
 * @param {string} headerId - The header ID
 * @returns {Promise<Object>} Updated header
 */
export async function undoHeader(headerId) {
  if (templateBuilderContext || isTemplateHeaderBuilderId(headerId)) {
    throw new Error('Undo is not available in template mode.');
  }

  const response = await fetch(`${API_BASE}/headers/${headerId}/undo`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to undo' }));
    throw new Error(error.detail || 'Failed to undo');
  }

  return response.json();
}

/**
 * Redo a previously undone change to a header.
 * @param {string} headerId - The header ID
 * @returns {Promise<Object>} Updated header
 */
export async function redoHeader(headerId) {
  if (templateBuilderContext || isTemplateHeaderBuilderId(headerId)) {
    throw new Error('Redo is not available in template mode.');
  }

  const response = await fetch(`${API_BASE}/headers/${headerId}/redo`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to redo' }));
    throw new Error(error.detail || 'Failed to redo');
  }

  return response.json();
}

/**
 * Get available section types and their schemas.
 * @returns {Promise<Object>} Section types info
 */
export async function getSectionTypes() {
  const response = await fetch(`${API_BASE}/sections/types`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch section types' }));
    throw new Error(error.detail || 'Failed to fetch section types');
  }

  return response.json();
}

// -------------------------
// Page Sections Management API
// -------------------------

/**
 * Add a section reference to a page.
 * @param {string} slug - The page slug
 * @param {Object} sectionRef - Section reference with section_id, order, visible
 * @returns {Promise<Object>} Updated page
 */
export async function addSectionToPage(slug, sectionRef) {
  if (templateBuilderContext) {
    const response = await fetch(buildTemplateBuilderUrl('/sections', { includePath: true }), {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(sectionRef || {}),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to add section to template' }));
      throw new Error(error.detail || 'Failed to add section to template');
    }

    return response.json();
  }

  const encodedSlug = encodeURIComponent(slug);
  const response = await fetch(`${API_BASE}/pages/${encodedSlug}/sections`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(sectionRef),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to add section to page' }));
    throw new Error(error.detail || 'Failed to add section to page');
  }

  return response.json();
}

/**
 * Update a section reference in a page (order/visibility/limit).
 * @param {string} slug - The page slug
 * @param {string} sectionId - The section ID
 * @param {Object} options - Update options
 * @param {number} options.order - New order (optional)
 * @param {boolean} options.visible - New visibility (optional)
 * @param {number|null} options.limit - For blog: any positive integer caps items, 0 or null shows all (optional)
 * @returns {Promise<Object>} Updated page
 */
export async function updatePageSectionRef(slug, sectionId, { order, visible, limit, width, device_visibility: deviceVisibility } = {}) {
  if (templateBuilderContext || parseTemplateSectionBuilderId(sectionId)) {
    const templateRef = parseTemplateSectionBuilderId(sectionId);
    const resolvedKind = templateRef?.kind || getTemplateContextOrThrow().kind;
    const params = new URLSearchParams();
    if (order !== undefined) params.append('order', String(order));
    if (visible !== undefined) params.append('visible', String(visible));
    if (limit !== undefined) params.append('limit', String(limit));
    if (width !== undefined && width !== null) {
      params.append('width_n', String(width.n ?? 1));
      params.append('width_d', String(width.d ?? 1));
    }
    if (deviceVisibility && typeof deviceVisibility === 'object') {
      if (deviceVisibility.mobile !== undefined) params.append('device_mobile', String(deviceVisibility.mobile));
      if (deviceVisibility.tablet !== undefined) params.append('device_tablet', String(deviceVisibility.tablet));
      if (deviceVisibility.desktop !== undefined) params.append('device_desktop', String(deviceVisibility.desktop));
    }

    const encodedSectionId = encodeURIComponent(String(sectionId || ''));
    const response = await fetch(`${API_BASE}/admin/templates/builder/${resolvedKind}/sections/${encodedSectionId}?${params.toString()}`, {
      method: 'PATCH',
      headers: getHeaders(),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to update template section reference' }));
      throw new Error(error.detail || 'Failed to update template section reference');
    }

    return response.json();
  }

  const encodedSlug = encodeURIComponent(slug);
  const params = new URLSearchParams();
  const changes = {};
  if (order !== undefined) {
    params.append('order', String(order));
    changes.order = order;
  }
  if (visible !== undefined) {
    params.append('visible', String(visible));
    changes.visible = visible;
  }
  if (limit !== undefined) {
    params.append('limit', String(limit));
    changes.limit = limit;
  }
  if (width !== undefined && width !== null) {
    params.append('width_n', String(width.n ?? 1));
    params.append('width_d', String(width.d ?? 1));
    changes.width = width;
  }
  if (deviceVisibility && typeof deviceVisibility === 'object') {
    if (deviceVisibility.mobile !== undefined) {
      params.append('device_mobile', String(deviceVisibility.mobile));
    }
    if (deviceVisibility.tablet !== undefined) {
      params.append('device_tablet', String(deviceVisibility.tablet));
    }
    if (deviceVisibility.desktop !== undefined) {
      params.append('device_desktop', String(deviceVisibility.desktop));
    }
    changes.device_visibility = deviceVisibility;
  }

  const response = await fetch(`${API_BASE}/pages/${encodedSlug}/sections/${sectionId}?${params}`, {
    method: 'PATCH',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update section reference' }));
    throw new Error(error.detail || 'Failed to update section reference');
  }

  return response.json();
}

/**
 * Update header design overrides.
 */
export async function updateHeaderDesignOverrides(slug, overrides, options = {}) {
  if (templateBuilderContext) {
    const revertedFromSavedAt = options?.revertedFromSavedAt || null;
    const payload = revertedFromSavedAt
      ? { overrides, revision_reverted_from_saved_at: String(revertedFromSavedAt) }
      : overrides;
    const response = await fetch(buildTemplateBuilderUrl('/header/design', { includePath: true }), {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to update template header design overrides' }));
      throw new Error(error.detail || 'Failed to update template header design overrides');
    }

    return response.json();
  }

  const encodedSlug = encodeURIComponent(slug);
  const revertedFromSavedAt = options?.revertedFromSavedAt || null;
  const payload = revertedFromSavedAt
    ? { overrides, revision_reverted_from_saved_at: String(revertedFromSavedAt) }
    : overrides;
  const response = await fetch(`${API_BASE}/pages/${encodedSlug}/header/design`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update header design overrides' }));
    throw new Error(error.detail || 'Failed to update header design overrides');
  }

  return response.json();
}

/**
 * Update per-section design overrides.
 */
export async function updateSectionDesignOverrides(slug, sectionId, overrides, options = {}) {
  if (templateBuilderContext || parseTemplateSectionBuilderId(sectionId)) {
    const templateRef = parseTemplateSectionBuilderId(sectionId);
    const resolvedKind = templateRef?.kind || getTemplateContextOrThrow().kind;
    const revertedFromSavedAt = options?.revertedFromSavedAt || null;
    const payload = revertedFromSavedAt
      ? { overrides, revision_reverted_from_saved_at: String(revertedFromSavedAt) }
      : overrides;
    const encodedSectionId = encodeURIComponent(String(sectionId || ''));
    const response = await fetch(`${API_BASE}/admin/templates/builder/${resolvedKind}/sections/${encodedSectionId}/design`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to update template section design overrides' }));
      throw new Error(error.detail || 'Failed to update template section design overrides');
    }

    return response.json();
  }

  const encodedSlug = encodeURIComponent(slug);
  const revertedFromSavedAt = options?.revertedFromSavedAt || null;
  const payload = revertedFromSavedAt
    ? { overrides, revision_reverted_from_saved_at: String(revertedFromSavedAt) }
    : overrides;
  const response = await fetch(`${API_BASE}/pages/${encodedSlug}/sections/${sectionId}/design`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update section design overrides' }));
    throw new Error(error.detail || 'Failed to update section design overrides');
  }

  return response.json();
}

/**
 * Remove a section reference from a page (does not delete the section).
 * @param {string} slug - The page slug
 * @param {string} sectionId - The section ID
 * @returns {Promise<Object>} Updated page
 */
export async function removeSectionFromPage(slug, sectionId) {
  if (templateBuilderContext || parseTemplateSectionBuilderId(sectionId)) {
    const templateRef = parseTemplateSectionBuilderId(sectionId);
    const resolvedKind = templateRef?.kind || getTemplateContextOrThrow().kind;
    const encodedSectionId = encodeURIComponent(String(sectionId || ''));
    const response = await fetch(`${API_BASE}/admin/templates/builder/${resolvedKind}/sections/${encodedSectionId}`, {
      method: 'DELETE',
      headers: getHeaders(),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to remove section from template' }));
      throw new Error(error.detail || 'Failed to remove section from template');
    }

    return response.json();
  }

  const encodedSlug = encodeURIComponent(slug);
  const response = await fetch(`${API_BASE}/pages/${encodedSlug}/sections/${sectionId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to remove section from page' }));
    throw new Error(error.detail || 'Failed to remove section from page');
  }

  return response.json();
}

/**
 * Create a new section from a template and add it to a page.
 * This combines section creation and page attachment in one call.
 * @param {string} slug - The page slug
 * @param {Object} sectionData - Section data
 * @param {string} sectionData.section_type - Type of section (text, faq, etc.)
 * @param {string} sectionData.title_placeholder - Placeholder title
 * @param {Object} sectionData.title - Bilingual title { de, en }
 * @param {Object} sectionData.type_data - Type-specific data (optional)
 * @returns {Promise<Object>} Updated page with all sections
 */
export async function createAndAddSection(slug, sectionData) {
  if (templateBuilderContext) {
    const response = await fetch(buildTemplateBuilderUrl('/sections/create', { includePath: true }), {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(sectionData || {}),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to create template section' }));
      throw new Error(error.detail || 'Failed to create template section');
    }

    return response.json();
  }

  const encodedSlug = encodeURIComponent(slug);
  const params = new URLSearchParams();
  if (sectionData && sectionData.template_name) {
    params.set('template_name', String(sectionData.template_name));
  }
  const url = `${API_BASE}/pages/${encodedSlug}/sections/create${params.toString() ? `?${params.toString()}` : ''}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(sectionData),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create section' }));
    throw new Error(error.detail || 'Failed to create section');
  }

  return response.json();
}

/**
 * Parse markdown or HTML content on the server
 * @param {Object} options - Parse options
 * @param {string} [options.source_url] - URL to fetch content from
 * @param {string} [options.raw_content] - Raw markdown/HTML content
 * @param {string} [options.source_type] - Type of source: "markdown", "html", or "raw"
 * @param {string} [options.html_selector] - CSS selector to scope HTML content (e.g., "main", "#content")
 * @returns {Promise<Object>} Parsed result with rendered_html, source_type, and selector_found
 */
export async function parseMarkdown({ source_url, raw_content, source_type = 'markdown', html_selector = '' } = {}) {
  const response = await fetch(`${API_BASE}/sections/parse-markdown`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ source_url, raw_content, source_type, html_selector }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to parse markdown' }));
    throw new Error(error.detail || 'Failed to parse markdown');
  }

  return response.json();
}

// -------------------------
// Blog API (shared items across all blog sections)
// -------------------------

/**
 * List all shared blog items.
 * @returns {Promise<{items: Array}>}
 */
export async function listBlogItems() {
  const response = await fetch(`${API_BASE}/blog/items`, { headers: getHeaders() });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch blog items' }));
    throw new Error(error.detail || 'Failed to fetch blog items');
  }
  return response.json();
}

/**
 * Get blog config (tags list).
 * @returns {Promise<{tags: Array}>}
 */
export async function getBlogConfig() {
  const response = await fetch(`${API_BASE}/blog/config`, { headers: getHeaders() });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch blog config' }));
    throw new Error(error.detail || 'Failed to fetch blog config');
  }
  return response.json();
}

/**
 * Create a blog item (admin only).
 */
export async function createBlogItem(item) {
  const response = await fetch(`${API_BASE}/blog/items`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(item),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create blog item' }));
    throw new Error(error.detail || 'Failed to create blog item');
  }
  return response.json();
}

/**
 * Update a blog item (admin only).
 */
export async function updateBlogItem(itemId, item) {
  const response = await fetch(`${API_BASE}/blog/items/${itemId}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(item),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update blog item' }));
    throw new Error(error.detail || 'Failed to update blog item');
  }
  return response.json();
}

/**
 * Delete a blog item (admin only).
 */
export async function deleteBlogItem(itemId) {
  const response = await fetch(`${API_BASE}/blog/items/${itemId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete blog item' }));
    throw new Error(error.detail || 'Failed to delete blog item');
  }
  return response.json();
}

/**
 * Persist manual sort order for blog items.
 * @param {string[]} ids - Item IDs in the desired display order.
 */
export async function reorderBlogItems(ids) {
  const response = await fetch(`${API_BASE}/blog/items/reorder`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify({ ids }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to reorder blog items' }));
    throw new Error(error.detail || 'Failed to reorder blog items');
  }
  return response.json();
}

/**
 * Update blog config (tags).
 */
export async function updateBlogConfig(tags) {
  const response = await fetch(`${API_BASE}/blog/config`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify({ tags }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update blog config' }));
    throw new Error(error.detail || 'Failed to update blog config');
  }
  return response.json();
}

// -------------------------
// Admin Design Config API
// -------------------------

export async function getAdminDevopsConfig() {
  const response = await fetch(`${API_BASE}/admin/devops-config`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch admin devops config' }));
    throw new Error(error.detail || 'Failed to fetch admin devops config');
  }
  return response.json();
}

export async function getAdminDevopsChangelog({ limit = 50, offset = 0, pageSlug = '' } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  params.set('offset', String(offset));
  const normalizedPageSlug = String(pageSlug || '').trim();
  if (normalizedPageSlug) {
    params.set('page_slug', normalizedPageSlug);
  }
  const response = await fetch(`${API_BASE}/admin/devops-config/changelog?${params}`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch admin devops changelog' }));
    throw new Error(error.detail || 'Failed to fetch admin devops changelog');
  }
  return response.json();
}

export async function getAdminDevopsTutorials() {
  const response = await fetch(`${API_BASE}/admin/devops-config/tutorials`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch admin devops tutorials' }));
    throw new Error(resolveErrorDetailMessage(error, 'Failed to fetch admin devops tutorials'));
  }
  return response.json();
}

export async function createAdminDevopsTutorial(data) {
  const response = await fetch(`${API_BASE}/admin/devops-config/tutorials`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create admin devops tutorial' }));
    throw new Error(resolveErrorDetailMessage(error, 'Failed to create admin devops tutorial'));
  }
  return response.json();
}

export async function updateAdminDevopsTutorial(tutorialId, data) {
  const response = await fetch(`${API_BASE}/admin/devops-config/tutorials/${encodeURIComponent(tutorialId)}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update admin devops tutorial' }));
    throw new Error(resolveErrorDetailMessage(error, 'Failed to update admin devops tutorial'));
  }
  return response.json();
}

export async function deleteAdminDevopsTutorial(tutorialId) {
  const response = await fetch(`${API_BASE}/admin/devops-config/tutorials/${encodeURIComponent(tutorialId)}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete admin devops tutorial' }));
    throw new Error(resolveErrorDetailMessage(error, 'Failed to delete admin devops tutorial'));
  }
  return response.json();
}

export async function updateAdminDevopsConfig(data) {
  const response = await fetch(`${API_BASE}/admin/devops-config`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update admin devops config' }));
    throw new Error(error.detail || 'Failed to update admin devops config');
  }
  return response.json();
}

export async function getPermissionConfig() {
  const response = await fetch(`${API_BASE}/admin/users`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch admin users config' }));
    throw new Error(error.detail || 'Failed to fetch admin users config');
  }
  return response.json();
}

export async function patchPermissionConfig(data) {
  const response = await fetch(`${API_BASE}/admin/users`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update admin users config' }));
    throw new Error(error.detail || 'Failed to update admin users config');
  }
  return response.json();
}

export async function replacePermissionConfig(data) {
  const response = await fetch(`${API_BASE}/admin/users`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to replace admin users config' }));
    throw new Error(error.detail || 'Failed to replace admin users config');
  }
  return response.json();
}

export async function listTempCredentials() {
  const response = await fetch(`${API_BASE}/admin/users/temp-credentials`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list temp credentials' }));
    throw new Error(error.detail || 'Failed to list temp credentials');
  }
  const payload = await response.json();
  return Array.isArray(payload?.items) ? payload.items : [];
}

export async function createTempCredential(data) {
  const response = await fetch(`${API_BASE}/admin/users/temp-credentials`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create temp credential' }));
    throw new Error(error.detail || 'Failed to create temp credential');
  }
  return response.json();
}

export async function patchTempCredential(credentialId, data) {
  const safeId = encodeURIComponent(String(credentialId || '').trim());
  const response = await fetch(`${API_BASE}/admin/users/temp-credentials/${safeId}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update temp credential' }));
    throw new Error(error.detail || 'Failed to update temp credential');
  }
  return response.json();
}

export async function revokeTempCredential(credentialId) {
  const safeId = encodeURIComponent(String(credentialId || '').trim());
  const response = await fetch(`${API_BASE}/admin/users/temp-credentials/${safeId}/revoke`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to revoke temp credential' }));
    throw new Error(error.detail || 'Failed to revoke temp credential');
  }
  return response.json();
}

export async function deleteTempCredential(credentialId) {
  const safeId = encodeURIComponent(String(credentialId || '').trim());
  const response = await fetch(`${API_BASE}/admin/users/temp-credentials/${safeId}`, {
    method: 'DELETE',
    headers: getHeaders({ includeContentType: false }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete temp credential' }));
    throw new Error(error.detail || 'Failed to delete temp credential');
  }
}

export async function getAdminDesignConfig() {
  const response = await fetch(`${API_BASE}/admin/design-config`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch admin design config' }));
    throw new Error(error.detail || 'Failed to fetch admin design config');
  }
  return response.json();
}

export async function updateAdminDesignConfig(data) {
  const response = await fetch(`${API_BASE}/admin/design-config`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update admin design config' }));
    throw new Error(error.detail || 'Failed to update admin design config');
  }
  return response.json();
}

export async function resetAdminDesignConfig() {
  const response = await fetch(`${API_BASE}/admin/design-config/reset`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to reset admin design config' }));
    throw new Error(error.detail || 'Failed to reset admin design config');
  }
  return response.json();
}

// -------------------------
// CSS Snippets API
// -------------------------

export async function listCssSnippets() {
  if (templateBuilderContext) {
    const templateKey = templateBuilderContext.template_key;
    if (!templateKey) {
      throw new Error('Template key is missing for template CSS snippets.');
    }
    const params = new URLSearchParams({ template_key: templateKey });
    const response = await fetch(`${API_BASE}/admin/templates/css-snippets?${params.toString()}`, {
      method: 'GET',
      headers: getHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to list template CSS snippets' }));
      throw new Error(error.detail || 'Failed to list template CSS snippets');
    }
    return response.json();
  }

  const response = await fetch(`${API_BASE}/admin/design-config/css-snippets`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list CSS snippets' }));
    throw new Error(error.detail || 'Failed to list CSS snippets');
  }
  return response.json();
}

export async function createCssSnippet(data) {
  if (templateBuilderContext) {
    const templateKey = templateBuilderContext.template_key;
    if (!templateKey) {
      throw new Error('Template key is missing for template CSS snippets.');
    }
    const response = await fetch(`${API_BASE}/admin/templates/css-snippets`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ ...(data || {}), template_key: templateKey }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to create template CSS snippet' }));
      throw new Error(error.detail || 'Failed to create template CSS snippet');
    }
    return response.json();
  }

  const response = await fetch(`${API_BASE}/admin/design-config/css-snippets`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create CSS snippet' }));
    throw new Error(error.detail || 'Failed to create CSS snippet');
  }
  return response.json();
}

export async function updateCssSnippet(snippetId, data) {
  if (templateBuilderContext) {
    const response = await fetch(`${API_BASE}/admin/templates/css-snippets/${snippetId}`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(data || {}),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to update template CSS snippet' }));
      throw new Error(error.detail || 'Failed to update template CSS snippet');
    }
    return response.json();
  }

  const response = await fetch(`${API_BASE}/admin/design-config/css-snippets/${snippetId}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update CSS snippet' }));
    throw new Error(error.detail || 'Failed to update CSS snippet');
  }
  return response.json();
}

export async function deleteCssSnippet(snippetId) {
  if (templateBuilderContext) {
    const response = await fetch(`${API_BASE}/admin/templates/css-snippets/${snippetId}`, {
      method: 'DELETE',
      headers: getHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to delete template CSS snippet' }));
      throw new Error(error.detail || 'Failed to delete template CSS snippet');
    }
    return response.json();
  }

  const response = await fetch(`${API_BASE}/admin/design-config/css-snippets/${snippetId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete CSS snippet' }));
    throw new Error(error.detail || 'Failed to delete CSS snippet');
  }
  return response.json();
}

// -------------------------
// Admin Templates API
// -------------------------

export async function listSectionTemplates({ sectionType = '' } = {}) {
  const params = new URLSearchParams();
  if (sectionType) params.set('section_type', String(sectionType));
  const response = await fetch(`${API_BASE}/admin/templates/sections${params.toString() ? `?${params.toString()}` : ''}`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list section templates' }));
    throw new Error(error.detail || 'Failed to list section templates');
  }
  return response.json();
}

export async function createSectionTemplate(data) {
  const response = await fetch(`${API_BASE}/admin/templates/sections`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create section template' }));
    throw new Error(error.detail || 'Failed to create section template');
  }
  return response.json();
}

export async function deleteSectionTemplate(sectionType, templateName) {
  const response = await fetch(
    `${API_BASE}/admin/templates/sections/${encodeURIComponent(sectionType)}/${encodeURIComponent(templateName)}`,
    {
      method: 'DELETE',
      headers: getHeaders(),
    }
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete section template' }));
    throw new Error(error.detail || 'Failed to delete section template');
  }
  return response.json();
}

export async function renameSectionTemplate(sectionType, templateName, nextTemplateName) {
  const response = await fetch(
    `${API_BASE}/admin/templates/sections/${encodeURIComponent(sectionType)}/${encodeURIComponent(templateName)}/rename`,
    {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ template_name: String(nextTemplateName || '') }),
    }
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to rename section template' }));
    throw new Error(error.detail || 'Failed to rename section template');
  }
  return response.json();
}

export async function updateSectionTemplateMetadata(sectionType, templateName, data) {
  const response = await fetch(
    `${API_BASE}/admin/templates/sections/${encodeURIComponent(sectionType)}/${encodeURIComponent(templateName)}`,
    {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify(data || {}),
    }
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update section template metadata' }));
    throw new Error(error.detail || 'Failed to update section template metadata');
  }
  return response.json();
}

export async function duplicateSectionTemplate(sectionType, templateName, nextTemplateName) {
  const response = await fetch(
    `${API_BASE}/admin/templates/sections/${encodeURIComponent(sectionType)}/${encodeURIComponent(templateName)}/duplicate`,
    {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ template_name: String(nextTemplateName || '') }),
    }
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to duplicate section template' }));
    throw new Error(error.detail || 'Failed to duplicate section template');
  }
  return response.json();
}

export async function listContainerTemplates() {
  const response = await fetch(`${API_BASE}/admin/templates/containers`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list container templates' }));
    throw new Error(error.detail || 'Failed to list container templates');
  }
  return response.json();
}

export async function createContainerTemplate(data) {
  const response = await fetch(`${API_BASE}/admin/templates/containers`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create container template' }));
    throw new Error(error.detail || 'Failed to create container template');
  }
  return response.json();
}

export async function deleteContainerTemplate(templateName) {
  const response = await fetch(`${API_BASE}/admin/templates/containers/${encodeURIComponent(templateName)}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete container template' }));
    throw new Error(error.detail || 'Failed to delete container template');
  }
  return response.json();
}

export async function renameContainerTemplate(templateName, nextTemplateName) {
  const response = await fetch(
    `${API_BASE}/admin/templates/containers/${encodeURIComponent(templateName)}/rename`,
    {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ template_name: String(nextTemplateName || '') }),
    }
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to rename container template' }));
    throw new Error(error.detail || 'Failed to rename container template');
  }
  return response.json();
}

export async function duplicateContainerTemplate(templateName, nextTemplateName) {
  const response = await fetch(
    `${API_BASE}/admin/templates/containers/${encodeURIComponent(templateName)}/duplicate`,
    {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ template_name: String(nextTemplateName || '') }),
    }
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to duplicate container template' }));
    throw new Error(error.detail || 'Failed to duplicate container template');
  }
  return response.json();
}

export async function listPageTemplates({ sourceType = '' } = {}) {
  const params = new URLSearchParams();
  if (sourceType) params.set('source_type', String(sourceType));
  const response = await fetch(`${API_BASE}/admin/templates/pages${params.toString() ? `?${params.toString()}` : ''}`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list page templates' }));
    throw new Error(error.detail || 'Failed to list page templates');
  }
  return response.json();
}

/**
 * List global shared source routes for item-page templates.
 * @returns {Promise<Object>} { routes: Array<{ source_route_ref, parent_route, source_type, source_kind, section_template_ref, label }> }
 */
export async function listItemPageSourceRoutes() {
  const response = await fetch(`${API_BASE}/admin/templates/item-page-source-routes`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list item-page source routes' }));
    throw new Error(error.detail || 'Failed to list item-page source routes');
  }
  return response.json();
}

/**
 * Replace global shared source routes for item-page templates.
 * @param {Array|Object} routesPayload - Array of route entries or payload object with { routes }
 * @returns {Promise<Object>} { routes: Array }
 */
export async function updateItemPageSourceRoutes(routesPayload) {
  const payload = Array.isArray(routesPayload)
    ? { routes: routesPayload }
    : (routesPayload && typeof routesPayload === 'object')
      ? routesPayload
      : { routes: [] };
  const response = await fetch(`${API_BASE}/admin/templates/item-page-source-routes`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update item-page source routes' }));
    throw new Error(error.detail || 'Failed to update item-page source routes');
  }
  return response.json();
}

/**
 * Get the global item-page config (active template path per entity type).
 * @returns {Promise<Object>} { blog_item_template_path, program_stage_template_path, program_gig_template_path, ... }
 */
export async function getGlobalItemPageConfig() {
  const response = await fetch(`${API_BASE}/admin/templates/global-item-page-config`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to load global item-page config' }));
    throw new Error(error.detail || 'Failed to load global item-page config');
  }
  return response.json();
}

/**
 * Update the global item-page config.
 * @param {Object} updates - Partial updates to merge, e.g. { blog_item_template_path: 'program/gig-template' }
 * @returns {Promise<Object>} Updated config
 */
export async function setGlobalItemPageConfig(updates) {
  const response = await fetch(`${API_BASE}/admin/templates/global-item-page-config`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(updates || {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to save global item-page config' }));
    throw new Error(error.detail || 'Failed to save global item-page config');
  }
  return response.json();
}

export async function listItemPageParentCandidates({ sourceType, sourceKind } = {}) {
  const params = new URLSearchParams();
  params.set('source_type', String(sourceType || ''));
  if (sourceKind) params.set('source_kind', String(sourceKind));
  const response = await fetch(`${API_BASE}/admin/templates/item-page-parent-candidates?${params.toString()}`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to load item-page parent candidates' }));
    throw new Error(error.detail || 'Failed to load item-page parent candidates');
  }
  return response.json();
}

export async function createPageTemplate(data) {
  const response = await fetch(`${API_BASE}/admin/templates/pages`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create page template' }));
    throw new Error(error.detail || 'Failed to create page template');
  }
  return response.json();
}

function encodeTemplatePath(path) {
  return String(path || '')
    .split('/')
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join('/');
}

export async function getPageTemplate(path) {
  const safePath = encodeTemplatePath(path);
  const response = await fetch(`${API_BASE}/admin/templates/pages/${safePath}`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch page template' }));
    throw new Error(error.detail || 'Failed to fetch page template');
  }
  return response.json();
}

export async function patchPageTemplate(path, data) {
  const safePath = encodeTemplatePath(path);
  const response = await fetch(`${API_BASE}/admin/templates/pages/${safePath}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to patch page template' }));
    throw new Error(error.detail || 'Failed to patch page template');
  }
  return response.json();
}

export async function previewPageTemplateMapping(path, data) {
  const params = new URLSearchParams();
  params.set('path', String(path || '').trim());
  const response = await fetch(`${API_BASE}/admin/templates/builder/page/mapping-preview?${params.toString()}`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to preview page template mapping' }));
    throw new Error(resolveErrorDetailMessage(error, 'Failed to preview page template mapping'));
  }
  return response.json();
}

export async function updatePageTemplateRouting(path, data) {
  const safePath = encodeTemplatePath(path);
  const response = await fetch(`${API_BASE}/admin/templates/pages/${safePath}/routing`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update page template routing' }));
    throw new Error(error.detail || 'Failed to update page template routing');
  }
  return response.json();
}

export async function deletePageTemplate(path) {
  const safePath = encodeTemplatePath(path);
  const response = await fetch(`${API_BASE}/admin/templates/pages/${safePath}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete page template' }));
    throw new Error(error.detail || 'Failed to delete page template');
  }
  return response.json();
}

export async function renamePageTemplate(path, nextTemplateName) {
  const safePath = encodeTemplatePath(path);
  const response = await fetch(`${API_BASE}/admin/templates/pages/${safePath}/rename`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ template_name: String(nextTemplateName || '') }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to rename page template' }));
    throw new Error(error.detail || 'Failed to rename page template');
  }
  return response.json();
}

export async function duplicatePageTemplate(path, nextTemplateName) {
  const safePath = encodeTemplatePath(path);
  const response = await fetch(`${API_BASE}/admin/templates/pages/${safePath}/duplicate`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ template_name: String(nextTemplateName || '') }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to duplicate page template' }));
    throw new Error(error.detail || 'Failed to duplicate page template');
  }
  return response.json();
}

export async function instantiatePageFromTemplate(path, data) {
  const safePath = encodeTemplatePath(path);
  const response = await fetch(`${API_BASE}/admin/templates/pages/${safePath}/instantiate`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to instantiate page template' }));
    throw new Error(error.detail || 'Failed to instantiate page template');
  }
  return response.json();
}

export async function regeneratePageTemplateItemPages(path) {
  const safePath = encodeTemplatePath(path);
  const response = await fetch(`${API_BASE}/admin/templates/pages/${safePath}/regenerate-all`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to regenerate item pages' }));
    throw new Error(resolveErrorDetailMessage(error, 'Failed to regenerate item pages'));
  }
  return response.json();
}

export async function getPageTemplateDesignState(path) {
  const safePath = encodeTemplatePath(path);
  const response = await fetch(`${API_BASE}/admin/templates/pages/${safePath}/design`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch page template design state' }));
    throw new Error(error.detail || 'Failed to fetch page template design state');
  }
  return response.json();
}

export async function updatePageTemplateDesignCurrent(path, data) {
  const safePath = encodeTemplatePath(path);
  const response = await fetch(`${API_BASE}/admin/templates/pages/${safePath}/design/current`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update page template design draft' }));
    throw new Error(error.detail || 'Failed to update page template design draft');
  }
  return response.json();
}

export async function publishPageTemplateDesign(path) {
  const safePath = encodeTemplatePath(path);
  const response = await fetch(`${API_BASE}/admin/templates/pages/${safePath}/design/publish`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to publish page template design' }));
    throw new Error(error.detail || 'Failed to publish page template design');
  }
  return response.json();
}

export async function instantiateContainerTemplate(templateName, slug) {
  const response = await fetch(`${API_BASE}/admin/templates/containers/${encodeURIComponent(templateName)}/instantiate`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ slug }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to instantiate container template' }));
    throw new Error(error.detail || 'Failed to instantiate container template');
  }
  return response.json();
}

// -------------------------
// Design Versions API
// -------------------------

export async function listDesignVersions() {
  const response = await fetch(`${API_BASE}/admin/design-config/versions`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list versions' }));
    throw new Error(error.detail || 'Failed to list versions');
  }
  return response.json();
}

export async function createDesignVersion(data) {
  const response = await fetch(`${API_BASE}/admin/design-config/versions`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create version' }));
    throw new Error(error.detail || 'Failed to create version');
  }
  return response.json();
}

export async function updateDesignVersion(versionId, data) {
  const response = await fetch(`${API_BASE}/admin/design-config/versions/${versionId}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update version' }));
    throw new Error(error.detail || 'Failed to update version');
  }
  return response.json();
}

export async function deleteDesignVersion(versionId) {
  const response = await fetch(`${API_BASE}/admin/design-config/versions/${versionId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete version' }));
    throw new Error(error.detail || 'Failed to delete version');
  }
  return response.json();
}

export async function publishDesignVersion(versionId) {
  const response = await fetch(`${API_BASE}/admin/design-config/versions/${versionId}/publish`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to publish version' }));
    throw new Error(error.detail || 'Failed to publish version');
  }
  return response.json();
}

export async function getFontFamilyCacheStatus(payload = {}) {
  const response = await fetch(`${API_BASE}/admin/design-config/font-cache/family-status`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload || {}),
  });
  if (!response.ok) {
    const raw = await response.text().catch(() => "");
    let detail = "";
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        detail = String(parsed?.detail || parsed?.message || "").trim();
      } catch {
        detail = raw.trim();
      }
    }
    const fallback = `Failed to check font cache health (HTTP ${response.status})`;
    throw new Error(detail || fallback);
  }
  return response.json();
}

export async function cacheFontFamilyViaBrowser(payload = {}) {
  const formData = new FormData();
  const family = String(payload?.family || '').trim();
  const sourceCssUrl = String(payload?.sourceCssUrl || '').trim();
  const cssText = String(payload?.cssText || '');
  const sourceUrls = Array.isArray(payload?.sourceUrls) ? payload.sourceUrls : [];
  const files = Array.isArray(payload?.files) ? payload.files : [];

  formData.append('family', family);
  formData.append('source_css_url', sourceCssUrl);
  formData.append('css_text', cssText);
  sourceUrls.forEach((url) => {
    formData.append('source_urls', String(url || ''));
  });
  files.forEach((file) => {
    formData.append('files', file);
  });

  const headers = getHeaders();
  delete headers['Content-Type'];

  const response = await fetch(`${API_BASE}/admin/design-config/font-cache/cache-via-browser`, {
    method: 'POST',
    headers,
    body: formData,
  });
  if (!response.ok) {
    const raw = await response.text().catch(() => "");
    let detail = "";
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        detail = String(parsed?.detail || parsed?.message || "").trim();
      } catch {
        detail = raw.trim();
      }
    }
    throw new Error(detail || 'Failed to cache font via browser');
  }
  return response.json();
}

export async function loadDesignVersion(versionId) {
  const response = await fetch(`${API_BASE}/admin/design-config/versions/${versionId}/load`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to load version' }));
    throw new Error(error.detail || 'Failed to load version');
  }
  return response.json();
}

// -------------------------
// Design Settings API
// -------------------------

/**
 * Get the global design settings.
 * @returns {Promise<Object>} Design settings
 */
export async function getDesignSettings() {
  const response = await fetch(`${API_BASE}/design`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch design settings' }));
    throw new Error(error.detail || 'Failed to fetch design settings');
  }

  return response.json();
}

/**
 * Update design settings (partial update).
 * @param {Object} data - Design settings to update
 * @returns {Promise<Object>} Updated design settings
 */
export async function updateDesignSettings(data) {
  const response = await fetch(`${API_BASE}/design`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update design settings' }));
    const detail = error?.detail;
    const message = typeof detail === 'string'
      ? detail
      : detail
        ? JSON.stringify(detail)
        : 'Failed to update design settings';
    throw new Error(message);
  }

  return response.json();
}

/**
 * Replace all design settings.
 * @param {Object} data - Complete design settings
 * @returns {Promise<Object>} Updated design settings
 */
export async function replaceDesignSettings(data) {
  const response = await fetch(`${API_BASE}/design`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to replace design settings' }));
    throw new Error(error.detail || 'Failed to replace design settings');
  }

  return response.json();
}

/**
 * Reset design settings to defaults.
 * @returns {Promise<Object>} Default design settings
 */
export async function resetDesignSettings() {
  const response = await fetch(`${API_BASE}/design/reset`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to reset design settings' }));
    throw new Error(error.detail || 'Failed to reset design settings');
  }

  return response.json();
}

/**
 * Get undo/redo status for design settings.
 * @returns {Promise<Object>} Revision status { can_undo, can_redo, history_count, future_count }
 */
export async function getDesignRevisionStatus() {
  const response = await fetch(`${API_BASE}/design/revisions/status`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    return { enabled: true, can_undo: false, can_redo: false, history_count: 0, future_count: 0 };
  }

  return response.json();
}

/**
 * Undo the last change to design settings.
 * @returns {Promise<Object>} Updated design settings
 */
export async function undoDesign() {
  const response = await fetch(`${API_BASE}/design/undo`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to undo' }));
    throw new Error(error.detail || 'Failed to undo');
  }

  return response.json();
}

/**
 * Redo a previously undone change to design settings.
 * @returns {Promise<Object>} Updated design settings
 */
export async function redoDesign() {
  const response = await fetch(`${API_BASE}/design/redo`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to redo' }));
    throw new Error(error.detail || 'Failed to redo');
  }

  return response.json();
}

/**
 * Get current server time - useful for scheduling UI.
 * @returns {Promise<Object>} Server time info { server_time, server_timezone }
 */
export async function getServerTime() {
  const response = await fetch(`${API_BASE}/system/time`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    throw new Error('Failed to get server time');
  }

  return response.json();
}

// =====================
// Integrations API
// =====================

/**
 * List all integrations.
 * @returns {Promise<Array>} Array of integration objects
 */
export async function listIntegrations() {
  const response = await fetch(`${API_BASE}/integrations`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list integrations' }));
    throw new Error(error.detail || 'Failed to list integrations');
  }

  return response.json();
}

/**
 * Get global integrations connection config.
 * @returns {Promise<Object>} {
 *   exposed_integration_ids: string[],
 *   template_integration_rules: Record<string, {
 *     integration_visibility: "disabled" | "template_only" | "enabled",
 *     integrations_enabled: boolean,
 *     expected_return_type: "auto" | "list" | "object"
 *   }>
 * }
 */
export async function getIntegrationConnectionConfig() {
  const response = await fetch(`${API_BASE}/integrations/connection/config`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to load integration connection config' }));
    throw new Error(error.detail || 'Failed to load integration connection config');
  }

  return response.json();
}

/**
 * Update global integrations connection config.
 * @param {Object} data - {
 *   exposed_integration_ids?: string[],
 *   template_integration_rules?: Record<string, {
 *     integration_visibility: "disabled" | "template_only" | "enabled",
 *     integrations_enabled: boolean,
 *     expected_return_type: "auto" | "list" | "object"
 *   }>
 * }
 * @returns {Promise<Object>} Updated connection config
 */
export async function updateIntegrationConnectionConfig(data) {
  const response = await fetch(`${API_BASE}/integrations/connection/config`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update integration connection config' }));
    throw new Error(error.detail || 'Failed to update integration connection config');
  }

  return response.json();
}

/**
 * Create a new integration.
 * @param {Object} data - Integration data
 * @returns {Promise<Object>} Created integration
 */
export async function createIntegration(data) {
  const response = await fetch(`${API_BASE}/integrations`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create integration' }));
    const detail = error.detail;
    throw new Error(Array.isArray(detail) ? detail.map(e => e.msg || JSON.stringify(e)).join('; ') : (detail || 'Failed to create integration'));
  }

  return response.json();
}

/**
 * Get a single integration.
 * @param {string} id - Integration ID
 * @returns {Promise<Object>} Integration object
 */
export async function getIntegration(id) {
  const response = await fetch(`${API_BASE}/integrations/${id}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Integration not found' }));
    throw new Error(error.detail || 'Integration not found');
  }

  return response.json();
}

/**
 * Update an integration.
 * @param {string} id - Integration ID
 * @param {Object} data - Fields to update
 * @returns {Promise<Object>} Updated integration
 */
export async function updateIntegration(id, data) {
  const response = await fetch(`${API_BASE}/integrations/${id}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update integration' }));
    const detail = error.detail;
    throw new Error(Array.isArray(detail) ? detail.map(e => e.msg || JSON.stringify(e)).join('; ') : (detail || 'Failed to update integration'));
  }

  return response.json();
}

/**
 * Delete an integration.
 * @param {string} id - Integration ID
 * @returns {Promise<Object>} Deletion result
 */
export async function deleteIntegration(id) {
  const response = await fetch(`${API_BASE}/integrations/${id}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete integration' }));
    throw new Error(error.detail || 'Failed to delete integration');
  }

  return response.json();
}

/**
 * Run health check on an integration.
 * @param {Object} payload - Draft integration config { url, type, auth_type, key_name }
 * @returns {Promise<Object>} Health check result { ok, status_code, error, response_time_ms }
 */
export async function healthCheckIntegrationDraft(payload) {
  const response = await fetch(`${API_BASE}/integrations/health/draft`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Draft health check failed' }));
    throw new Error(error.detail || 'Draft health check failed');
  }

  return response.json();
}

/**
 * Inspect raw output for an unsaved integration draft (does not persist data).
 * @param {Object} payload - Draft integration config { url, type, auth_type, key_name, response_type, response_path }
 * @returns {Promise<Object>} Inspect result { data, item_count }
 */
export async function inspectIntegrationDraft(payload) {
  const response = await fetch(`${API_BASE}/integrations/inspect/draft`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Draft inspect failed' }));
    throw new Error(error.detail || 'Draft inspect failed');
  }

  return response.json();
}

/**
 * Run health check on an integration.
 * @param {string} id - Integration ID
 * @returns {Promise<Object>} Health check result { ok, status_code, error, response_time_ms }
 */
export async function healthCheckIntegration(id) {
  const response = await fetch(`${API_BASE}/integrations/${id}/health`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Health check failed' }));
    throw new Error(error.detail || 'Health check failed');
  }

  return response.json();
}

/**
 * Fetch data from an integration and store it.
 * @param {string} id - Integration ID
 * @returns {Promise<Object>} Fetched data { integration_id, data, fetched_at, item_count }
 */
export async function fetchIntegrationData(id) {
  const response = await fetch(`${API_BASE}/integrations/${id}/fetch`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch data' }));
    throw new Error(error.detail || 'Failed to fetch data');
  }

  return response.json();
}

/**
 * Start a background deep fetch job for a composable integration.
 * @param {string} id - Integration ID (composable)
 * @returns {Promise<Object>} Job state { job_id, integration_id, status, ... }
 */
export async function startIntegrationDeepFetch(id) {
  const response = await fetch(`${API_BASE}/integrations/${id}/fetch/deep/async`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to start deep fetch' }));
    throw new Error(error.detail || 'Failed to start deep fetch');
  }

  return response.json();
}

/**
 * Get status of a background integration deep fetch job.
 * @param {string} jobId - Deep fetch job ID
 * @returns {Promise<Object>} Job state { job_id, integration_id, status, ... }
 */
export async function getIntegrationDeepFetchJob(jobId) {
  const response = await fetch(`${API_BASE}/integrations/fetch-jobs/${jobId}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to load deep fetch job status' }));
    throw new Error(error.detail || 'Failed to load deep fetch job status');
  }

  return response.json();
}

/**
 * Re-run processing steps on cached integration data without refetching upstream source data.
 * @param {string} id - Integration ID
 * @returns {Promise<Object>} Reprocessed data { integration_id, data, fetched_at, item_count }
 */
export async function reprocessIntegrationData(id) {
  const response = await fetch(`${API_BASE}/integrations/${id}/reprocess`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to reprocess data' }));
    throw new Error(error.detail || 'Failed to reprocess data');
  }

  return response.json();
}

/**
 * Get stored integration data.
 * @param {string} id - Integration ID
 * @returns {Promise<Object>} Stored data { integration_id, data, options, option_types, fetched_at, item_count }
 */
export async function getIntegrationData(id) {
  const response = await fetch(`${API_BASE}/integrations/${id}/data`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'No data available' }));
    throw new Error(error.detail || 'No data available');
  }

  return response.json();
}

/**
 * Get stored integration data with local review overrides applied.
 * @param {string} id - Integration ID
 * @returns {Promise<Object>} Stored effective data { integration_id, data, options, option_types, media_entries, fetched_at, item_count }
 */
export async function getEffectiveIntegrationData(id) {
  const response = await fetch(`${API_BASE}/integrations/${id}/data/effective`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'No effective data available' }));
    throw new Error(error.detail || 'No effective data available');
  }

  return response.json();
}

/**
 * List reviewable items for an integration.
 * @param {string} id - Integration ID
 * @param {Object} [options]
 * @param {string} [options.state] - Review state filter
 * @param {string} [options.tag] - Review tag filter
 * @returns {Promise<Object>} Review item summary payload
 */
export async function listIntegrationReviewItems(id, options = {}) {
  const params = new URLSearchParams();
  if (String(options?.state || '').trim()) {
    params.append('state', String(options.state).trim());
  }
  if (String(options?.tag || '').trim()) {
    params.append('tag', String(options.tag).trim());
  }
  const suffix = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`${API_BASE}/integrations/${id}/review/items${suffix}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to load integration review items' }));
    throw new Error(error.detail || 'Failed to load integration review items');
  }

  return response.json();
}

/**
 * Load one integration review item.
 * @param {string} id - Integration ID
 * @param {string} itemKey - Stable item key
 * @returns {Promise<Object>} Review item detail
 */
export async function getIntegrationReviewItem(id, itemKey) {
  const params = new URLSearchParams();
  params.append('item_key', String(itemKey || ''));
  const response = await fetch(`${API_BASE}/integrations/${id}/review/item?${params.toString()}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to load integration review item' }));
    throw new Error(error.detail || 'Failed to load integration review item');
  }

  return response.json();
}

/**
 * Update integration review item-page sync settings.
 * @param {string} id - Integration ID
 * @param {Object} payload - { item_page_sync_blocked }
 * @returns {Promise<Object>} Updated integration
 */
export async function updateIntegrationReviewSyncSettings(id, payload) {
  const response = await fetch(`${API_BASE}/integrations/${id}/review/sync-settings`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update integration review sync settings' }));
    throw new Error(error.detail || 'Failed to update integration review sync settings');
  }

  return response.json();
}

/**
 * Create a local-only review item from schema-shaped values.
 * @param {string} id - Integration ID
 * @param {Object} payload - { values, item_key }
 * @returns {Promise<Object>} Created review item detail
 */
export async function createIntegrationReviewItem(id, payload) {
  const response = await fetch(`${API_BASE}/integrations/${id}/review/items`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create integration review item' }));
    throw new Error(error.detail || 'Failed to create integration review item');
  }

  return response.json();
}

/**
 * Save a field-level local override for an integration item.
 * @param {string} id - Integration ID
 * @param {Object} payload - { item_key, field_path, value }
 * @returns {Promise<Object>} Updated review item detail
 */
export async function updateIntegrationReviewItem(id, payload) {
  const response = await fetch(`${API_BASE}/integrations/${id}/review/item`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to save integration review override' }));
    throw new Error(error.detail || 'Failed to save integration review override');
  }

  return response.json();
}

/**
 * Save item-level review metadata.
 * @param {string} id - Integration ID
 * @param {Object} payload - { item_key, state, tags }
 * @returns {Promise<Object>} Updated review item detail
 */
export async function updateIntegrationReviewItemMeta(id, payload) {
  const response = await fetch(`${API_BASE}/integrations/${id}/review/item/meta`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to save integration review metadata' }));
    throw new Error(error.detail || 'Failed to save integration review metadata');
  }

  return response.json();
}

/**
 * Clear a field-level local override for an integration item.
 * @param {string} id - Integration ID
 * @param {Object} payload - { item_key, field_path }
 * @returns {Promise<Object>} Updated review item detail
 */
export async function deleteIntegrationReviewFieldOverride(id, payload) {
  const params = new URLSearchParams();
  params.append('item_key', String(payload?.item_key || ''));
  params.append('field_path', String(payload?.field_path || ''));
  const response = await fetch(`${API_BASE}/integrations/${id}/review/item/field?${params.toString()}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to clear integration review override' }));
    throw new Error(error.detail || 'Failed to clear integration review override');
  }

  return response.json();
}

/**
 * Get integration schema metadata.
 * @param {string} id - Integration ID
 * @returns {Promise<Object>} Schema payload
 */
export async function getIntegrationSchema(id) {
  const response = await fetch(`${API_BASE}/integrations/${id}/schema`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to load integration schema' }));
    throw new Error(error.detail || 'Failed to load integration schema');
  }

  return response.json();
}

/**
 * Detect and persist integration schema metadata.
 * @param {string} id - Integration ID
 * @returns {Promise<Object>} Schema payload
 */
export async function detectIntegrationSchema(id) {
  const response = await fetch(`${API_BASE}/integrations/${id}/schema/detect`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to detect integration schema' }));
    throw new Error(error.detail || 'Failed to detect integration schema');
  }

  return response.json();
}

/**
 * Update manual integration schema settings.
 * @param {string} id - Integration ID
 * @param {Object} payload - { manual_types, collect_options, cache_media, required_fields, item_label_path, output_primary_key_path }
 * @returns {Promise<Object>} Schema payload
 */
export async function updateIntegrationSchema(id, payload) {
  const response = await fetch(`${API_BASE}/integrations/${id}/schema`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update integration schema' }));
    throw new Error(error.detail || 'Failed to update integration schema');
  }

  return response.json();
}

/**
 * Cache media for schema image fields enabled on an integration.
 * @param {string} id - Integration ID
 * @returns {Promise<Object>} Media cache result with refreshed data, options, option_types, and media_entries
 */
export async function cacheIntegrationSchemaMedia(id) {
  const response = await fetch(`${API_BASE}/integrations/${id}/media/cache`, {
    method: 'POST',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to cache integration media' }));
    throw new Error(error.detail || 'Failed to cache integration media');
  }

  return response.json();
}

/**
 * Get preview of integration data.
 * @param {string} id - Integration ID
 * @param {Object} [options]
 * @param {number|null} [options.itemIndex] - Optional list item index to preview
 * @param {string|null} [options.itemKey] - Optional external item key to preview
 * @returns {Promise<Object>} Preview { integration_id, preview_item, available_keys, options, option_types, fetched_at, total_items }
 */
export async function getIntegrationDataPreview(id, { itemIndex = null, itemKey = null } = {}) {
  const params = new URLSearchParams();
  if (itemKey !== null && itemKey !== undefined && itemKey !== '') {
    params.append('item_key', String(itemKey));
  }
  if (itemIndex !== null && itemIndex !== undefined && itemIndex !== '') {
    params.append('item_index', String(itemIndex));
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`${API_BASE}/integrations/${id}/data/preview${query}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get preview' }));
    throw new Error(error.detail || 'Failed to get preview');
  }

  return response.json();
}

/**
 * List integrations available for a specific section type.
 * @param {string} sectionType - Section type (e.g., 'program')
 * @param {Object} [options]
 * @param {string|null} [options.sectionId] - Optional section instance id for section-specific mapping
 * @param {string|null} [options.itemPageTemplatePath] - Optional item-page template path context
 * @returns {Promise<Object>} {
 *   integrations: Array,
 *   context: {
 *     template_key: string,
 *     integration_visibility: "disabled" | "template_only" | "enabled",
 *     integrations_enabled: boolean,
 *     expected_return_type: "auto" | "list" | "object"
 *   }
 * }
 */
export async function listIntegrationsForSection(
  sectionType,
  {
    sectionId = null,
    itemPageTemplatePath = null,
    sourceRouteRef = null,
  } = {},
) {
  const params = new URLSearchParams();
  if (sectionId) {
    params.append('section_id', String(sectionId));
  }
  if (itemPageTemplatePath) {
    params.append('item_page_template_path', String(itemPageTemplatePath));
  }
  if (sourceRouteRef) {
    params.append('source_route_ref', String(sourceRouteRef));
  }
  const query = params.toString() ? `?${params}` : '';

  const response = await fetch(`${API_BASE}/integrations/for-section/${sectionType}${query}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to list integrations' }));
    throw new Error(error.detail || 'Failed to list integrations');
  }

  const payload = await response.json();
  if (Array.isArray(payload)) {
    return {
      integrations: payload,
      context: {
        template_key: '',
        integration_visibility: 'enabled',
        integrations_enabled: true,
        expected_return_type: 'auto',
      },
    };
  }
  return {
    integrations: Array.isArray(payload?.integrations) ? payload.integrations : [],
    context: {
      template_key: String(payload?.context?.template_key || ''),
      integration_visibility: ['disabled', 'template_only', 'enabled'].includes(payload?.context?.integration_visibility)
        ? payload.context.integration_visibility
        : 'enabled',
      integrations_enabled: payload?.context?.integrations_enabled !== false,
      expected_return_type: ['auto', 'list', 'object'].includes(payload?.context?.expected_return_type)
        ? payload.context.expected_return_type
        : 'auto',
    },
  };
}

/**
 * Return whether an integration currently contains importable media URLs.
 * @param {string} integrationId
 * @returns {Promise<Object>}
 */
export async function getIntegrationMediaImportability(integrationId) {
  const response = await fetch(`${API_BASE}/integrations/${integrationId}/media-importability`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to resolve integration media importability' }));
    throw new Error(error.detail || 'Failed to resolve integration media importability');
  }

  return response.json();
}

/**
 * Localize/import media URLs for a section integration mapping context.
 * Uses latest transformed integration payload (no upstream refetch).
 * @param {Object} payload
 * @param {string} payload.section_id
 * @param {string} payload.section_type
 * @param {string} payload.integration_id
 * @param {string} [payload.mapping_storage_key]
 * @param {string[]} [payload.mapped_source_paths]
 * @param {boolean} [payload.enable_metadata_extraction_tagging]
 * @returns {Promise<Object>} Section media import payload with options and option_types metadata
 */
export async function importSectionIntegrationMedia(payload) {
  const response = await fetch(`${API_BASE}/integrations/section-media/import`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to import section integration media' }));
    throw new Error(error.detail || 'Failed to import section integration media');
  }

  return response.json();
}

/**
 * Get latest section integration cache record for current section/integration mapping scope.
 * @param {Object} options
 * @param {string} options.sectionId
 * @param {string} options.integrationId
 * @param {string} [options.mappingStorageKey]
 * @returns {Promise<Object>} Latest cache payload
 */
export async function getLatestSectionIntegrationCache({
  sectionId,
  integrationId,
  mappingStorageKey = 'sectionIntegrationMapping',
} = {}) {
  const params = new URLSearchParams();
  if (sectionId) params.append('section_id', String(sectionId));
  if (integrationId) params.append('integration_id', String(integrationId));
  if (mappingStorageKey) params.append('mapping_storage_key', String(mappingStorageKey));
  const query = params.toString() ? `?${params}` : '';

  const response = await fetch(`${API_BASE}/integrations/section-cache/latest${query}`, {
    method: 'GET',
    headers: getHeaders(),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to load latest section integration cache' }));
    throw new Error(error.detail || 'Failed to load latest section integration cache');
  }

  return response.json();
}
