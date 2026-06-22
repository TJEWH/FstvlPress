<template>
  <div class="temp-login-page">
    <div class="temp-login-card">
      <h1>Temporary Access Login</h1>
      <p class="subtitle">
        Use the temporary username and password provided by an administrator.
      </p>

      <form class="temp-login-form" @submit.prevent="submitLogin">
        <label class="field-label" for="temp-username">Username</label>
        <input
          id="temp-username"
          v-model="username"
          class="field"
          type="text"
          autocomplete="username"
          placeholder="temporary username"
          :disabled="submitting"
        />

        <label class="field-label" for="temp-password">Password</label>
        <input
          id="temp-password"
          v-model="password"
          class="field"
          type="password"
          autocomplete="current-password"
          placeholder="temporary password"
          :disabled="submitting"
        />

        <button class="submit-btn" type="submit" :disabled="submitting">
          {{ submitting ? "Signing in..." : "Sign In" }}
        </button>
      </form>

      <p class="hint">
        This login path is only for temporary users that do not exist in Keycloak.
      </p>
      <p v-if="errorMessage" class="message error">{{ errorMessage }}</p>
      <router-link class="back-link" to="/">Back to Site</router-link>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuth } from "../services/auth.js";
import { useStore } from "../store/store.js";

const router = useRouter();
const route = useRoute();
const { state: authState, initAuth, loginWithTempCredentials, getHighestAllowedAdminPath } = useAuth();
const { loadDesignSettings, loadAdminDesignConfig } = useStore();

const username = ref("");
const password = ref("");
const submitting = ref(false);
const errorMessage = ref("");

function resolveRedirectTarget() {
  const redirectQuery = route.query?.redirect;
  const redirectPath = typeof redirectQuery === "string" ? redirectQuery.trim() : "";
  if (redirectPath && redirectPath.startsWith("/admin")) {
    return redirectPath;
  }
  return getHighestAllowedAdminPath();
}

async function submitLogin() {
  errorMessage.value = "";
  submitting.value = true;
  try {
    await loginWithTempCredentials(username.value, password.value);
    if (authState.capabilities?.can_content) {
      await loadDesignSettings();
      if (authState.capabilities?.can_admin_design) {
        await loadAdminDesignConfig();
      }
    }
    const target = resolveRedirectTarget();
    await router.replace(target || "/admin/sitemap/pages");
  } catch (err) {
    errorMessage.value = err?.message || "Temporary login failed.";
  } finally {
    submitting.value = false;
  }
}

onMounted(async () => {
  await initAuth();
  if (authState.authenticated) {
    const target = getHighestAllowedAdminPath();
    await router.replace(target || "/");
  }
});
</script>

<style scoped>
.temp-login-page {
  min-height: calc(100vh - 64px);
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    radial-gradient(circle at 15% 20%, rgba(30, 64, 175, 0.14), transparent 42%),
    radial-gradient(circle at 85% 0%, rgba(2, 132, 199, 0.13), transparent 36%),
    linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
}

.temp-login-card {
  width: min(460px, 100%);
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  box-shadow: 0 16px 34px rgba(15, 23, 42, 0.11);
  padding: 24px;
}

h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.15;
  color: #0f172a;
}

.subtitle {
  margin: 10px 0 18px;
  color: #475569;
  font-size: 14px;
}

.temp-login-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field-label {
  font-size: 12px;
  font-weight: 700;
  color: #334155;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.field {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 11px 12px;
  font-size: 14px;
  color: #0f172a;
  background: #fff;
}

.field:focus {
  outline: none;
  border-color: #1d4ed8;
  box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.16);
}

.submit-btn {
  margin-top: 8px;
  border: 0;
  border-radius: 10px;
  padding: 11px 14px;
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #1d4ed8, #0369a1);
  cursor: pointer;
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.hint {
  margin: 14px 0 0;
  color: #64748b;
  font-size: 13px;
}

.message.error {
  margin: 12px 0 0;
  color: #b91c1c;
  font-size: 14px;
  font-weight: 600;
}

.back-link {
  display: inline-block;
  margin-top: 18px;
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}

.back-link:hover {
  text-decoration: underline;
}

@media (max-width: 640px) {
  .temp-login-page {
    padding: 16px;
  }

  .temp-login-card {
    padding: 18px;
    border-radius: 14px;
  }

  h1 {
    font-size: 24px;
  }
}
</style>
