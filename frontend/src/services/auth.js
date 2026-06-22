/**
 * Authentication service with Keycloak integration.
 *
 * The website is publicly accessible without login.
 * Keycloak login is triggered explicitly via the /login route.
 * 
 * Local development modes:
 * - Default: Keycloak is bypassed on localhost, granting admin rights automatically.
 * - Local Keycloak: Set VITE_USE_LOCAL_KEYCLOAK=true to use a local Keycloak instance
 *   for testing authentication flows. See docker/docker-compose.keycloak-only.yml.
 */
import Keycloak from 'keycloak-js';
import { reactive, readonly } from 'vue';
import { resolveApiBase } from './apiBase.js';

const state = reactive({
  initialized: false,
  authenticated: false,
  user: null,
  token: null,
  apiToken: null,
  error: null,
  isLocalDev: false,
  keycloakAdminRole: null,
  internalRole: 'no_access',
  accessSource: null,
  capabilities: {
    is_admin: false,
    can_content: false,
    can_design: false,
    can_admin_design: false,
    can_admin_general: false,
  },
});

let keycloak = null;
let refreshInterval = null;
let initPromise = null; // Prevents concurrent initialization

const DEV_USER = {
  sub: 'dev-user-00000000-0000-0000-0000-000000000000',
  username: 'dev-admin',
  email: 'dev@localhost',
  emailVerified: true,
  name: 'Development Admin',
  givenName: 'Development',
  familyName: 'Admin',
  roles: ['admin', 'editor'],
  realmRoles: ['admin', 'editor'],
  groups: ['/admins', '/editors'],
};

const INTERNAL_ROLE_ORDER = ['no_access', 'content', 'design', 'admin_design', 'admin_general'];
const INTERNAL_ROLE_RANK = INTERNAL_ROLE_ORDER.reduce((acc, role, index) => {
  acc[role] = index;
  return acc;
}, {});

function normalizeInternalRole(role) {
  const value = String(role || '').trim().toLowerCase();
  return INTERNAL_ROLE_ORDER.includes(value) ? value : 'no_access';
}

function roleAtLeast(role, requiredRole) {
  const roleRank = INTERNAL_ROLE_RANK[normalizeInternalRole(role)] ?? -1;
  const requiredRank = INTERNAL_ROLE_RANK[normalizeInternalRole(requiredRole)] ?? -1;
  return roleRank >= requiredRank;
}

function capabilitiesForRole(role) {
  const normalized = normalizeInternalRole(role);
  return {
    is_admin: roleAtLeast(normalized, 'content'),
    can_content: roleAtLeast(normalized, 'content'),
    can_design: roleAtLeast(normalized, 'design'),
    can_admin_design: roleAtLeast(normalized, 'admin_design'),
    can_admin_general: roleAtLeast(normalized, 'admin_general'),
  };
}

function applyInternalRole(role, capabilities = null, accessSource = null) {
  const normalizedRole = normalizeInternalRole(role);
  const defaults = capabilitiesForRole(normalizedRole);
  const nextCapabilities = {
    ...defaults,
    ...(capabilities && typeof capabilities === 'object' ? capabilities : {}),
  };

  state.internalRole = normalizedRole;
  state.capabilities = {
    is_admin: Boolean(nextCapabilities.is_admin),
    can_content: Boolean(nextCapabilities.can_content),
    can_design: Boolean(nextCapabilities.can_design),
    can_admin_design: Boolean(nextCapabilities.can_admin_design),
    can_admin_general: Boolean(nextCapabilities.can_admin_general),
  };
  state.accessSource = accessSource || null;
}

// ---------------------------------------------------------------------------
// Configuration helpers
// ---------------------------------------------------------------------------

/**
 * Check if local Keycloak testing is enabled via URL param, sessionStorage,
 * runtime config, or build-time env.
 */
function useLocalKeycloak() {
  const urlParam = new URLSearchParams(window.location.search).get('useLocalKeycloak');

  if (urlParam === 'true') { sessionStorage.setItem('useLocalKeycloak', 'true'); return true; }
  if (urlParam === 'false') { sessionStorage.removeItem('useLocalKeycloak'); return false; }
  if (sessionStorage.getItem('useLocalKeycloak') === 'true') return true;

  const rc = window.APP_CONFIG || {};
  if (rc.USE_LOCAL_KEYCLOAK === true || rc.USE_LOCAL_KEYCLOAK === 'true') return true;
  if (import.meta.env.VITE_USE_LOCAL_KEYCLOAK === 'true') return true;

  return false;
}

function isLocalDev() {
  const hostname = window.location.hostname;
  const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
  return isLocalhost && !useLocalKeycloak();
}

function getKeycloakConfig() {
  const rc = window.APP_CONFIG || {};

  if (useLocalKeycloak()) {
    return {
      url:      rc.LOCAL_KEYCLOAK_URL       || import.meta.env.VITE_LOCAL_KEYCLOAK_URL       || 'http://localhost:8180',
      realm:    rc.LOCAL_KEYCLOAK_REALM     || import.meta.env.VITE_LOCAL_KEYCLOAK_REALM     || 'FstvlPressLocal',
      clientId: rc.LOCAL_KEYCLOAK_CLIENT_ID || import.meta.env.VITE_LOCAL_KEYCLOAK_CLIENT_ID || 'fstvlpress-web',
    };
  }

  // Browser apps must use public OIDC clients; never expose client secrets.
  return {
    url:          rc.OIDC_URL           || import.meta.env.VITE_OIDC_URL           || '',
    realm:        rc.OIDC_REALM_NAME    || import.meta.env.VITE_OIDC_REALM_NAME    || '',
    clientId:     rc.OIDC_CLIENT_ID     || import.meta.env.VITE_OIDC_CLIENT_ID     || '',
  };
}

function getKeycloakInstance() {
  if (!keycloak) {
    const config = getKeycloakConfig();
    installTokenInterceptor(config);
    keycloak = new Keycloak({ url: config.url, realm: config.realm, clientId: config.clientId });
    keycloak.onTokenExpired = () => {
      keycloak.updateToken(30).then(refreshed => {
        if (refreshed) {
          storeTokens();
          exchangeAppToken(keycloak.token);
        }
      }).catch(() => {
        console.warn('[Auth] Token expired and refresh failed');
        clearStoredTokens();
        clearAuthState();
      });
    };
  }
  return keycloak;
}

/**
 * The production Keycloak server may not return CORS headers for our origin.
 *
 * This interceptor patches window.fetch to:
 *  1. Rewrite cross-origin token-endpoint URLs through /oidc-proxy/ (nginx
 *     reverse-proxies to the real Keycloak server, avoiding CORS).
 *
 * Login redirects are full-page navigations and unaffected by CORS.
 */
let interceptorInstalled = false;
function installTokenInterceptor({ url: oidcUrl }) {
  if (interceptorInstalled) return;
  interceptorInstalled = true;
  const originalFetch = window.fetch;
  window.fetch = function (input, init) {
    let url = typeof input === 'string' ? input : input?.url;
    if (url?.includes('/protocol/openid-connect/token')) {
      // Rewrite cross-origin Keycloak URL through same-origin nginx proxy
      if (oidcUrl && url.startsWith(oidcUrl)) {
        url = url.replace(oidcUrl, '/oidc-proxy');
        input = typeof input === 'string' ? url : new Request(url, input);
      }
    }
    return originalFetch.call(this, input, init);
  };
}

// ---------------------------------------------------------------------------
// Token persistence (localStorage – survives refresh + new tabs)
// ---------------------------------------------------------------------------

function storeTokens() {
  if (keycloak?.token && keycloak?.refreshToken) {
    localStorage.setItem('kc_token', keycloak.token);
    localStorage.setItem('kc_refresh_token', keycloak.refreshToken);
  }
}

function storeAppToken(token) {
  if (!token) return;
  state.apiToken = token;
  localStorage.setItem('fstvlpress_api_token', token);
}

function clearStoredTokens() {
  localStorage.removeItem('kc_token');
  localStorage.removeItem('kc_refresh_token');
  localStorage.removeItem('fstvlpress_api_token');
  state.apiToken = null;
}

function decodeJwtPayload(token) {
  try {
    const payload = token.split('.')[1];
    if (!payload) return null;
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(normalized));
  } catch {
    return null;
  }
}

function isExpiredToken(token, skewSeconds = 30) {
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return false;
  return Math.floor(Date.now() / 1000) >= (payload.exp - skewSeconds);
}

function isAppTokenPayload(payload) {
  return Boolean(payload && payload.typ === 'fstvlpress-app' && payload.iss === 'fstvlpress-backend');
}

function isTempCredentialAppTokenPayload(payload) {
  return isAppTokenPayload(payload) && payload.access_source === 'temp_credential';
}

function buildUserFromAppTokenPayload(payload) {
  const username = String(payload?.preferred_username || '').trim() || null;
  const sub = String(payload?.sub || '').trim() || 'app-token-user';
  const internalRole = normalizeInternalRole(payload?.internal_role);
  const impliedRoles = [];
  if (roleAtLeast(internalRole, 'admin_general')) impliedRoles.push('admin');
  else if (roleAtLeast(internalRole, 'content')) impliedRoles.push('editor');
  if (payload?.access_source === 'temp_credential') impliedRoles.push('temp_user');

  return {
    sub,
    username,
    email: payload?.email || null,
    emailVerified: false,
    name: username || 'Temporary User',
    givenName: username || '',
    familyName: '',
    roles: impliedRoles,
    realmRoles: impliedRoles,
    groups: [],
  };
}

async function exchangeAppToken(sourceToken) {
  if (!sourceToken) return null;
  try {
    const apiBase = resolveApiBase();
    const res = await fetch(`${apiBase}/auth/app-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keycloak_token: sourceToken }),
      credentials: 'omit',
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (data?.access_token) {
      storeAppToken(data.access_token);
      return data.access_token;
    }
  } catch {
    // Non-fatal: fallback remains Keycloak token
  }
  return null;
}

// ---------------------------------------------------------------------------
// Admin config (fetched from backend)
// ---------------------------------------------------------------------------

async function fetchAdminConfig(authToken = null) {
  try {
    const apiBase = resolveApiBase();
    const headers = authToken ? { Authorization: `Bearer ${authToken}` } : undefined;
    const res = await fetch(`${apiBase}/auth/config`, { headers });
    if (res.ok) {
      const cfg = await res.json();
      state.keycloakAdminRole = cfg.keycloak_admin_role || null;
      const internalRole = normalizeInternalRole(cfg.internal_role);
      applyInternalRole(internalRole, cfg.capabilities, cfg.access_source);
      return true;
    }
  } catch {
    // Ignore network/config errors and fall back to no access.
  }
  state.keycloakAdminRole = null;
  applyInternalRole('no_access', null, null);
  return false;
}

export function isUserAdmin() {
  return Boolean(state.authenticated && state.capabilities?.can_content);
}

// ---------------------------------------------------------------------------
// Core auth lifecycle
// ---------------------------------------------------------------------------

export async function initAuth() {
  // Already initialized - return immediately
  if (state.initialized) return state.authenticated;
  
  // If initialization is already in progress, wait for it
  if (initPromise) {
    return initPromise;
  }

  // Start initialization and store the promise
  initPromise = doInitAuth();
  
  try {
    return await initPromise;
  } finally {
    // Clear promise after completion (success or failure)
    initPromise = null;
  }
}

async function doInitAuth() {
  state.isLocalDev = isLocalDev();
  const savedAppToken = localStorage.getItem('fstvlpress_api_token');
  const savedAppPayload = savedAppToken ? decodeJwtPayload(savedAppToken) : null;
  if (savedAppToken && !isExpiredToken(savedAppToken) && isTempCredentialAppTokenPayload(savedAppPayload)) {
    state.apiToken = savedAppToken;
  }

  // Dev bypass – no Keycloak at all
  if (state.isLocalDev) {
    state.user = { ...DEV_USER };
    state.token = 'dev-token-not-validated';
    state.authenticated = true;
    await fetchAdminConfig();
    state.initialized = true;
    return true;
  }

  // Restore temporary-user sessions from backend app token without Keycloak.
  if (
    savedAppToken
    && !isExpiredToken(savedAppToken)
    && isTempCredentialAppTokenPayload(savedAppPayload)
  ) {
    state.user = buildUserFromAppTokenPayload(savedAppPayload);
    state.token = savedAppToken;
    const configOk = await fetchAdminConfig(savedAppToken);
    if (configOk) {
      state.authenticated = true;
      state.initialized = true;
      return true;
    }
    clearStoredTokens();
    clearAuthState();
  }

  // Keycloak mode
  const kc = getKeycloakInstance();
  
  // Check if Keycloak was already initialized (can happen on HMR)
  // didInitialize exists in keycloak-js v18+
  if (kc.didInitialize) {
    if (kc.authenticated) {
      updateUserFromToken();
      await fetchAdminConfig(kc.token);
      await exchangeAppToken(kc.token);
      state.authenticated = true;
      startTokenRefresh();
    }
    state.initialized = true;
    return state.authenticated;
  }
  
  const savedToken = localStorage.getItem('kc_token');
  const savedRefreshToken = localStorage.getItem('kc_refresh_token');

  try {
    const initOpts = { checkLoginIframe: false };
    if (savedToken && savedRefreshToken) {
      initOpts.token = savedToken;
      initOpts.refreshToken = savedRefreshToken;
    }

    const authenticated = await kc.init(initOpts);

    if (authenticated) {
      // Validate restored tokens are still good
      if (savedToken) {
        try {
          await kc.updateToken(30);
        } catch {
          clearStoredTokens();
          state.initialized = true;
          return false;
        }
      }
      updateUserFromToken();
      await fetchAdminConfig(kc.token);
      storeTokens();
      await exchangeAppToken(kc.token);
      startTokenRefresh();
      state.authenticated = true;
      cleanUrlParams();
    } else if (savedToken) {
      clearStoredTokens();
    }
  } catch (error) {
    console.error('[Auth] Keycloak init failed:', error);
    clearStoredTokens();
    state.error = error.message || 'Keycloak init failed';
  }

  state.initialized = true;
  return state.authenticated;
}

export async function login(redirectUri) {
  if (state.isLocalDev) {
    state.user = { ...DEV_USER };
    state.token = 'dev-token-not-validated';
    state.authenticated = true;
    applyInternalRole('admin_general', null, 'dev_mode');
    return;
  }

  const kc = getKeycloakInstance();
  if (!kc.authServerUrl) {
    try { await kc.init({ checkLoginIframe: false }); } catch { /* proceed anyway */ }
  }

  kc.login({
    redirectUri: redirectUri || window.location.href,
    prompt: 'login',
  });
}

export async function loginWithTempCredentials(username, password) {
  const normalizedUsername = String(username || '').trim().toLowerCase();
  const rawPassword = String(password || '');
  if (!normalizedUsername || !rawPassword) {
    throw new Error('Username and password are required.');
  }

  const apiBase = resolveApiBase();
  const res = await fetch(`${apiBase}/auth/temp-login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: normalizedUsername,
      password: rawPassword,
    }),
    credentials: 'omit',
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Temporary login failed' }));
    throw new Error(error.detail || 'Temporary login failed');
  }
  const payload = await res.json();
  const accessToken = payload?.access_token ? String(payload.access_token) : '';
  if (!accessToken) {
    throw new Error('Temporary login failed: missing access token.');
  }

  const claims = decodeJwtPayload(accessToken);
  if (!isTempCredentialAppTokenPayload(claims)) {
    throw new Error('Temporary login failed: invalid token source.');
  }

  storeAppToken(accessToken);
  state.user = buildUserFromAppTokenPayload(claims);
  state.token = accessToken;
  const configOk = await fetchAdminConfig(accessToken);
  if (!configOk) {
    clearStoredTokens();
    clearAuthState();
    throw new Error('Temporary credentials are inactive or expired.');
  }
  state.authenticated = true;
  return true;
}

export function logout(redirectUri) {
  stopTokenRefresh();
  clearStoredTokens();

  if (state.isLocalDev) {
    clearAuthState();
    return;
  }

  clearAuthState();
  keycloak?.logout({ redirectUri: redirectUri || window.location.origin });
}

// ---------------------------------------------------------------------------
// Token / user helpers
// ---------------------------------------------------------------------------

function updateUserFromToken() {
  if (!keycloak?.tokenParsed) return;
  const t = keycloak.tokenParsed;
  const realmRoles  = t.realm_access?.roles || [];
  const clientRoles = t.resource_access?.[keycloak.clientId]?.roles || [];
  const allRoles    = [...new Set([...realmRoles, ...clientRoles])];

  state.user = {
    sub: t.sub,
    username: t.preferred_username,
    email: t.email,
    emailVerified: t.email_verified || false,
    name: t.name,
    givenName: t.given_name,
    familyName: t.family_name,
    roles: allRoles,
    realmRoles,
    groups: t.groups || [],
  };
  state.token = keycloak.token;
}

function startTokenRefresh() {
  stopTokenRefresh();
  refreshInterval = setInterval(() => {
    if (!keycloak?.authenticated) return;
    keycloak.updateToken(70).then(refreshed => {
      if (refreshed) {
        storeTokens();
        updateUserFromToken();
        exchangeAppToken(keycloak.token);
      }
    }).catch(() => {
      console.warn('[Auth] Token refresh failed');
      clearStoredTokens();
    });
  }, 60000);
}

function stopTokenRefresh() {
  if (refreshInterval) { clearInterval(refreshInterval); refreshInterval = null; }
}

function clearAuthState() {
  state.authenticated = false;
  state.user = null;
  state.token = null;
  state.apiToken = null;
  state.keycloakAdminRole = null;
  applyInternalRole('no_access', null, null);
}

function cleanUrlParams() {
  const url = new URL(window.location.href);
  let changed = false;
  for (const p of ['state', 'session_state', 'code', 'iss']) {
    if (url.searchParams.has(p)) { url.searchParams.delete(p); changed = true; }
  }
  if (changed) window.history.replaceState({}, document.title, url.pathname + url.search + url.hash);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function getToken() {
  if (state.isLocalDev) return state.token;
  if (state.apiToken && !isExpiredToken(state.apiToken)) return state.apiToken;
  if (state.apiToken && isExpiredToken(state.apiToken)) {
    localStorage.removeItem('fstvlpress_api_token');
    state.apiToken = null;
  }
  return keycloak?.token || null;
}

export function getUser()          { return state.user; }
export function hasRole(role)      { return state.user?.roles?.includes(role) || false; }
export function hasAnyRole(roles)  { return roles.some(r => hasRole(r)); }
export function getInternalRole()  { return normalizeInternalRole(state.internalRole); }
export function hasInternalRole(requiredRole) { return roleAtLeast(state.internalRole, requiredRole); }
export function getCapabilities()  { return { ...state.capabilities }; }
export function canContent()       { return hasInternalRole('content'); }
export function canDesign()        { return hasInternalRole('design'); }
export function canAdminDesign()   { return hasInternalRole('admin_design'); }
export function canAdminGeneral()  { return hasInternalRole('admin_general'); }
export function isAdmin()          { return canContent(); }
export function isEditor()         { return canContent(); }

export function getHighestAllowedAdminPath() {
  if (canAdminGeneral()) return '/admin/permissions';
  if (canAdminDesign()) return '/admin/design/sections';
  if (canContent()) return '/admin/sitemap/pages';
  return '/';
}

export async function refreshToken() {
  if (state.isLocalDev) return true;
  if (state.apiToken) {
    if (isExpiredToken(state.apiToken)) {
      clearStoredTokens();
      clearAuthState();
      return false;
    }
    return true;
  }
  if (!keycloak) return false;
  try {
    await keycloak.updateToken(-1);
    updateUserFromToken();
    storeTokens();
    await exchangeAppToken(keycloak.token);
    return true;
  } catch (error) {
    console.error('[Auth] Token refresh failed:', error);
    return false;
  }
}

export function accountManagement() {
  if (!state.isLocalDev) keycloak?.accountManagement();
}

/**
 * Full reset – clears all stored auth data and reloads.
 * Development/testing helper (trash-can button in header on localhost).
 */
export function resetAuth() {
  stopTokenRefresh();
  sessionStorage.clear();
  clearStoredTokens();
  document.cookie.split(';').forEach(c => {
    document.cookie = c.split('=')[0].trim() + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/';
  });

  if (keycloak?.authenticated) {
    keycloak.logout({ redirectUri: window.location.origin + window.location.pathname });
    return;
  }
  keycloak = null;
  window.location.href = window.location.pathname;
}

// ---------------------------------------------------------------------------
// Vue composable
// ---------------------------------------------------------------------------

export function useAuth() {
  return {
    state: readonly(state),
    getToken, getUser, hasRole, hasAnyRole,
    getInternalRole, hasInternalRole, getCapabilities,
    canContent, canDesign, canAdminDesign, canAdminGeneral,
    getHighestAllowedAdminPath,
    isAdmin, isEditor, isUserAdmin,
    login, loginWithTempCredentials, logout, accountManagement, refreshToken,
    initAuth, resetAuth,
  };
}

export { state as authState };
