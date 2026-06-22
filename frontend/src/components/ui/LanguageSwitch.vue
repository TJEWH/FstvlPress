<template>
  <button class="lang" type="button" @click="toggle">
    {{ state.lang.toUpperCase() }}
  </button>
</template>

<script setup>
import { useRoute, useRouter } from "vue-router";
import { useStore } from "../../store/store.js";
import { useAuth } from "../../services/auth.js";

const { state, setLang } = useStore();
const { state: authState } = useAuth();
const route = useRoute();
const router = useRouter();

function currentPublicSlug(path) {
  const normalized = String(path || "").replace(/^\/+|\/+$/g, "");
  if (!normalized) return "";
  if (normalized === "en") return "";
  if (normalized.startsWith("en/")) return normalized.slice(3);
  return normalized;
}

function toggle() {
  const nextLang = state.lang === "de" ? "en" : "de";
  setLang(nextLang);

  if (authState.authenticated || route.path.startsWith("/admin")) {
    return;
  }

  const slug = currentPublicSlug(route.path);
  const nextPath = nextLang === "en"
    ? (slug ? `/en/${slug}` : "/en")
    : (slug ? `/${slug}` : "/");

  if (nextPath !== route.path) {
    router.push({
      path: nextPath,
      query: route.query,
      hash: route.hash,
    });
  }
}
</script>

<style scoped>
.lang {
  height: 32px;
  min-width: 40px;
  padding: 0 10px;
  border: none;
  background: transparent;
  border-radius: 6px;
  font-weight: 800;
  cursor: pointer;
  color: var(--topbar-item-color, var(--topbar-muted-color, var(--text)));
  transition: color 0.15s, background 0.15s;
}
.lang:hover {
  color: var(--topbar-item-hover-color, var(--accent, #4f46e5));
  background: color-mix(in srgb, var(--topbar-item-hover-color, var(--accent, #4f46e5)) 8%, transparent);
}
</style>
