<template>
  <div class="admin-users admin-page">
    <AutosaveToast :message="mappingAutosaveToastMessage" :tone="mappingAutosaveStatus" />

    <header class="page-header">
      <h1>Permissions</h1>
      <p class="page-subtitle">Manage internal access roles for non-Keycloak-admin users by username and Keycloak role.</p>
    </header>

    <section class="card">
      <h2>Implicit Keycloak Admin Role</h2>
      <p class="hint">
        This role is read from environment and always resolves to <code>admin_general</code>. It cannot be edited here.
      </p>
      <div class="pill">{{ keycloakAdminRole || "Not configured" }}</div>
    </section>

    <section class="card">
      <div class="card-head">
        <h2>Keycloak Role Mappings</h2>
        <button class="btn-secondary" type="button" @click="addRoleMapping">Add Keycloak Role</button>
      </div>
      <p class="hint">All matching roles are evaluated; the highest internal role wins.</p>
      <div v-if="roleMappings.length === 0" class="empty">No Keycloak role mappings configured.</div>
      <div v-else class="mapping-list">
        <div v-for="(entry, index) in roleMappings" :key="`role-${index}`" class="mapping-row">
          <input
            v-model="entry.keycloak_role"
            class="field"
            type="text"
            placeholder="keycloak role"
            autocomplete="off"
            :disabled="loading || saving"
            @input="markMappingsDirty"
            @blur="saveConfig"
            @keydown.enter.prevent="saveConfig"
          />
          <select
            v-model="entry.internal_role"
            class="field select"
            :disabled="loading || saving"
            @change="saveConfig"
          >
            <option v-for="role in roleOptions" :key="`kc-role-${role}`" :value="role">
              {{ role }}
            </option>
          </select>
          <button
            class="btn-danger"
            type="button"
            :disabled="loading || saving"
            @click="removeRoleMapping(index)"
          >
            Remove
          </button>
        </div>
      </div>
    </section>

    <section class="card">
      <div class="card-head">
        <h2>Username Mappings</h2>
        <button class="btn-secondary" type="button" @click="addUsernameMapping">Add Username</button>
      </div>
      <p class="hint">Username mappings override Keycloak role mappings.</p>
      <div v-if="usernameMappings.length === 0" class="empty">No username mappings configured.</div>
      <div v-else class="mapping-list">
        <div v-for="(entry, index) in usernameMappings" :key="`user-${index}`" class="mapping-row">
          <input
            v-model="entry.username"
            class="field"
            type="text"
            placeholder="username"
            autocomplete="off"
            :disabled="loading || saving"
            @input="markMappingsDirty"
            @blur="saveConfig"
            @keydown.enter.prevent="saveConfig"
          />
          <select
            v-model="entry.internal_role"
            class="field select"
            :disabled="loading || saving"
            @change="saveConfig"
          >
            <option v-for="role in roleOptions" :key="`user-role-${role}`" :value="role">
              {{ role }}
            </option>
          </select>
          <button
            class="btn-danger"
            type="button"
            :disabled="loading || saving"
            @click="removeUsernameMapping(index)"
          >
            Remove
          </button>
        </div>
      </div>
    </section>

    <section class="card">
      <div class="card-head">
        <h2>Temporary Access Credentials</h2>
      </div>
      <p class="hint">
        Generate credentials for temporary users who are not present in Keycloak. These users can log in via <code>/temp-login</code>.
      </p>

      <div class="temp-create-grid">
        <input
          v-model="tempUsername"
          class="field"
          type="text"
          autocomplete="off"
          placeholder="temporary username"
          :disabled="loading || tempCreating"
          @keydown.enter.prevent="createTemporaryCredential"
        />
        <select v-model="tempInternalRole" class="field select" :disabled="loading || tempCreating">
          <option v-for="role in roleOptions" :key="`temp-role-${role}`" :value="role">
            {{ role }}
          </option>
        </select>
        <VueDatePicker
          :model-value="tempDateTimePickerModel(tempExpiresAtLocal)"
          class="temp-datetime-picker"
          :enable-time-picker="true"
          :is-24="true"
          :clearable="true"
          :text-input="DATE_PICKER_TEXT_INPUT_OPTIONS"
          :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
          :teleport="true"
          auto-apply
          placeholder="Select expiry"
          :disabled="loading || tempCreating"
          @update:model-value="setTempExpiresAtLocal"
          @keydown.enter.prevent="createTemporaryCredential"
        />
        <button class="btn-primary" type="button" :disabled="loading || tempCreating" @click="createTemporaryCredential">
          {{ tempCreating ? "Generating..." : "Generate Credential" }}
        </button>
      </div>

      <div v-if="generatedCredential" class="generated-card">
        <div class="generated-card__head">
          <strong>Credential Generated</strong>
          <span class="generated-warning">Shown once. Copy now.</span>
        </div>
        <div class="generated-grid">
          <div>
            <div class="generated-label">Username</div>
            <code>{{ generatedCredential.credential.username }}</code>
          </div>
          <button class="btn-secondary btn-sm" type="button" @click="copyToClipboard(generatedCredential.credential.username)">
            Copy Username
          </button>
          <div>
            <div class="generated-label">Password</div>
            <code>{{ generatedCredential.generated_password }}</code>
          </div>
          <button class="btn-secondary btn-sm" type="button" @click="copyToClipboard(generatedCredential.generated_password)">
            Copy Password
          </button>
        </div>
        <button class="btn-secondary btn-sm" type="button" @click="copyGeneratedBundle">
          Copy Username + Password
        </button>
      </div>

      <div v-if="tempCredentials.length === 0" class="empty">
        No temporary credentials configured.
      </div>
      <div v-else class="credential-table-wrap">
        <table class="credential-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Role</th>
              <th>Status</th>
              <th>Expires</th>
              <th>Created</th>
              <th class="actions-col">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="entry in tempCredentials" :key="entry.id">
              <td>
                <input
                  v-model="entry.username"
                  class="field table-field"
                  type="text"
                  autocomplete="off"
                  :disabled="loading || Boolean(tempActionId) || entry.saving"
                  @blur="saveTemporaryCredential(entry, ['username'])"
                  @keydown.enter.prevent="saveTemporaryCredential(entry, ['username'])"
                />
              </td>
              <td>
                <select
                  v-model="entry.internal_role"
                  class="field select table-field"
                  :disabled="loading || Boolean(tempActionId) || entry.saving"
                  @change="saveTemporaryCredential(entry, ['internal_role'])"
                >
                  <option v-for="role in roleOptions" :key="`credential-${entry.id}-role-${role}`" :value="role">
                    {{ role }}
                  </option>
                </select>
              </td>
              <td>
                <span :class="['status-pill', tempStatusClass(entry)]">{{ tempStatusLabel(entry) }}</span>
              </td>
              <td>
                <VueDatePicker
                  :model-value="tempDateTimePickerModel(entry.expires_at_local)"
                  class="temp-datetime-picker temp-datetime-picker--table"
                  :enable-time-picker="true"
                  :is-24="true"
                  :clearable="true"
                  :text-input="DATE_PICKER_TEXT_INPUT_OPTIONS"
                  :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
                  :teleport="true"
                  auto-apply
                  placeholder="Select expiry"
                  :disabled="loading || Boolean(tempActionId) || entry.saving"
                  @update:model-value="setTempCredentialExpiry(entry, $event)"
                  @keydown.enter.prevent="saveTemporaryCredential(entry, ['expires_at'])"
                />
              </td>
              <td>{{ formatDateTime(entry.created_at) }}</td>
              <td class="actions-col">
                <span v-if="entry.saving" class="row-save-status">Saving...</span>
                <span v-else-if="entry.save_error" class="row-save-status row-save-status--error">
                  {{ entry.save_error }}
                </span>
                <button
                  class="btn-secondary btn-sm"
                  type="button"
                  :disabled="loading || Boolean(tempActionId) || !isTempCredentialActive(entry)"
                  @click="revokeTemporaryCredential(entry)"
                >
                  Revoke
                </button>
                <button
                  class="btn-danger btn-sm"
                  type="button"
                  :disabled="loading || Boolean(tempActionId)"
                  @click="deleteTemporaryCredential(entry)"
                >
                  Delete
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <p v-if="errorMessage" class="message error">{{ errorMessage }}</p>
    <p v-else-if="successMessage" class="message success">{{ successMessage }}</p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { VueDatePicker } from "@vuepic/vue-datepicker";
import "@vuepic/vue-datepicker/dist/main.css";
import * as api from "../../services/api.js";
import AutosaveToast from "../../components/admin/AutosaveToast.vue";
import {
  DATE_PICKER_DATE_TIME_DISPLAY_FORMATS,
  DATE_PICKER_TEXT_INPUT_OPTIONS,
  formatDateTimeLocalForServerTimezone,
  formatInstantInServerTimezone,
  localDateToServerWallDateTime,
  serverWallDateTimeToInstantDate,
  serverWallDateTimeToLocalDate,
} from "../../utils/revisionTime.js";

const loading = ref(false);
const saving = ref(false);
const tempCreating = ref(false);
const tempActionId = ref("");
const errorMessage = ref("");
const successMessage = ref("");
const mappingAutosaveStatus = ref("idle");
const mappingAutosaveError = ref("");
const mappingsSaveQueued = ref(false);
const mappingsLastSavedSignature = ref("");
let mappingAutosaveStatusTimer = null;

const keycloakAdminRole = ref("");
const roleOptions = ref(["content", "design", "admin_design", "admin_general"]);
const defaultRole = ref("content");

const usernameMappings = ref([]);
const roleMappings = ref([]);
const tempCredentials = ref([]);
const generatedCredential = ref(null);
const tempUsername = ref("");
const tempInternalRole = ref("content");
const tempExpiresAtLocal = ref("");

function emptyUsernameMapping() {
  return { username: "", internal_role: defaultRole.value };
}

function emptyRoleMapping() {
  return { keycloak_role: "", internal_role: defaultRole.value };
}

function normalizeUsername(value) {
  return String(value || "").trim().toLowerCase();
}

function normalizeKeycloakRole(value) {
  return String(value || "").trim().toLowerCase();
}

function normalizeRole(value) {
  const candidate = String(value || "").trim().toLowerCase();
  return roleOptions.value.includes(candidate) ? candidate : defaultRole.value;
}

function toDateTimeLocalValue(date) {
  return formatDateTimeLocalForServerTimezone(date);
}

function defaultTempExpiryLocalValue() {
  const now = new Date();
  const expiry = new Date(now.getTime() + (7 * 24 * 60 * 60 * 1000));
  return toDateTimeLocalValue(expiry);
}

function localDateTimeToIso(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const parsed = serverWallDateTimeToInstantDate(raw);
  if (!parsed || Number.isNaN(parsed.getTime())) {
    throw new Error("Invalid expiry date.");
  }
  return parsed.toISOString();
}

function tempDateTimePickerModel(value) {
  return serverWallDateTimeToLocalDate(value);
}

function setTempExpiresAtLocal(value) {
  tempExpiresAtLocal.value = localDateToServerWallDateTime(value);
}

function setTempCredentialExpiry(entry, value) {
  entry.expires_at_local = localDateToServerWallDateTime(value);
  void saveTemporaryCredential(entry, ["expires_at"]);
}

function hydrateFromConfig(config) {
  keycloakAdminRole.value = String(config?.keycloak_admin_role || "").trim();
  roleOptions.value = Array.isArray(config?.editable_internal_roles) && config.editable_internal_roles.length
    ? config.editable_internal_roles
    : ["content", "design", "admin_design", "admin_general"];
  defaultRole.value = roleOptions.value.includes(config?.default_internal_role)
    ? config.default_internal_role
    : roleOptions.value[0];

  usernameMappings.value = Array.isArray(config?.username_mappings)
    ? config.username_mappings.map((entry) => ({
      username: normalizeUsername(entry?.username),
      internal_role: normalizeRole(entry?.internal_role),
    }))
    : [];

  roleMappings.value = Array.isArray(config?.keycloak_role_mappings)
    ? config.keycloak_role_mappings.map((entry) => ({
      keycloak_role: normalizeKeycloakRole(entry?.keycloak_role),
      internal_role: normalizeRole(entry?.internal_role),
    }))
    : [];

  if (!roleOptions.value.includes(tempInternalRole.value)) {
    tempInternalRole.value = defaultRole.value;
  }
}

function markTempCredentialSavedBaseline(entry) {
  entry._saved_username = normalizeUsername(entry.username);
  entry._saved_internal_role = normalizeRole(entry.internal_role);
  entry._saved_expires_at_local = String(entry.expires_at_local || "").trim();
}

function normalizeTempCredentialEntry(entry) {
  const expiresAt = entry?.expires_at || null;
  const normalized = {
    id: String(entry?.id || ""),
    username: normalizeUsername(entry?.username),
    internal_role: normalizeRole(entry?.internal_role),
    active: Boolean(entry?.active),
    is_expired: Boolean(entry?.is_expired),
    expires_at: expiresAt,
    expires_at_local: expiresAt ? toDateTimeLocalValue(expiresAt) : "",
    created_at: entry?.created_at || null,
    updated_at: entry?.updated_at || null,
    revoked_at: entry?.revoked_at || null,
    saving: false,
    save_error: "",
    save_queued: [],
  };
  markTempCredentialSavedBaseline(normalized);
  return normalized;
}

function hydrateTempCredentials(entries) {
  tempCredentials.value = Array.isArray(entries)
    ? entries.map((entry) => normalizeTempCredentialEntry(entry))
    : [];
}

async function loadConfig() {
  loading.value = true;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    const [config, credentialItems] = await Promise.all([
      api.getPermissionConfig(),
      api.listTempCredentials(),
    ]);
    hydrateFromConfig(config);
    markMappingsAutosaveBaseline();
    hydrateTempCredentials(credentialItems);
  } catch (err) {
    errorMessage.value = err?.message || "Failed to load permissions config.";
  } finally {
    loading.value = false;
  }
}

function addUsernameMapping() {
  usernameMappings.value.push(emptyUsernameMapping());
  markMappingsDirty();
}

async function removeUsernameMapping(index) {
  usernameMappings.value.splice(index, 1);
  await saveConfig();
}

function addRoleMapping() {
  roleMappings.value.push(emptyRoleMapping());
  markMappingsDirty();
}

async function removeRoleMapping(index) {
  roleMappings.value.splice(index, 1);
  await saveConfig();
}

function validateMappings(normalizedUserMappings, normalizedRoleMappings) {
  const usernameSeen = new Set();
  for (const entry of normalizedUserMappings) {
    if (!entry.username) {
      return "Each username mapping needs a username.";
    }
    if (usernameSeen.has(entry.username)) {
      return `Duplicate username mapping: ${entry.username}`;
    }
    usernameSeen.add(entry.username);
  }

  const roleSeen = new Set();
  for (const entry of normalizedRoleMappings) {
    if (!entry.keycloak_role) {
      return "Each Keycloak role mapping needs a role name.";
    }
    if (keycloakAdminRole.value && entry.keycloak_role === keycloakAdminRole.value.toLowerCase()) {
      return `The Keycloak admin role "${keycloakAdminRole.value}" is immutable and cannot be mapped here.`;
    }
    if (roleSeen.has(entry.keycloak_role)) {
      return `Duplicate Keycloak role mapping: ${entry.keycloak_role}`;
    }
    roleSeen.add(entry.keycloak_role);
  }
  return "";
}

function buildPermissionPayload() {
  return {
    username_mappings: usernameMappings.value.map((entry) => ({
      username: normalizeUsername(entry.username),
      internal_role: normalizeRole(entry.internal_role),
    })),
    keycloak_role_mappings: roleMappings.value.map((entry) => ({
      keycloak_role: normalizeKeycloakRole(entry.keycloak_role),
      internal_role: normalizeRole(entry.internal_role),
    })),
  };
}

function permissionPayloadSignature(payload) {
  try {
    return JSON.stringify(payload || {});
  } catch {
    return "";
  }
}

function markMappingsAutosaveBaseline() {
  const payload = buildPermissionPayload();
  mappingsLastSavedSignature.value = permissionPayloadSignature(payload);
  mappingsSaveQueued.value = false;
  setMappingAutosaveStatus("idle");
}

function markMappingsDirty() {
  clearMappingAutosaveStatusTimer();
  if (mappingAutosaveStatus.value !== "saving") {
    mappingAutosaveStatus.value = "idle";
  }
  mappingAutosaveError.value = "";
  successMessage.value = "";
}

const mappingAutosaveToastMessage = computed(() => {
  if (mappingAutosaveStatus.value === "saving") return "Saving permissions...";
  if (mappingAutosaveStatus.value === "saved") return "Permissions saved.";
  if (mappingAutosaveStatus.value === "error") {
    return `Permissions autosave failed: ${mappingAutosaveError.value || "unknown error"}`;
  }
  return "";
});

function clearMappingAutosaveStatusTimer() {
  if (mappingAutosaveStatusTimer) {
    clearTimeout(mappingAutosaveStatusTimer);
    mappingAutosaveStatusTimer = null;
  }
}

function setMappingAutosaveStatus(status, error = "") {
  clearMappingAutosaveStatusTimer();
  mappingAutosaveStatus.value = status;
  mappingAutosaveError.value = error;
  if (status === "saved" || status === "error") {
    mappingAutosaveStatusTimer = setTimeout(() => {
      mappingAutosaveStatus.value = "idle";
      mappingAutosaveError.value = "";
      mappingAutosaveStatusTimer = null;
    }, 3000);
  }
}

async function saveConfig() {
  if (saving.value) {
    mappingsSaveQueued.value = true;
    return;
  }

  errorMessage.value = "";
  successMessage.value = "";

  const payload = buildPermissionPayload();

  const validationError = validateMappings(payload.username_mappings, payload.keycloak_role_mappings);
  if (validationError) {
    errorMessage.value = validationError;
    setMappingAutosaveStatus("error", validationError);
    return;
  }

  const signature = permissionPayloadSignature(payload);
  if (signature && signature === mappingsLastSavedSignature.value) {
    setMappingAutosaveStatus("saved");
    return;
  }

  saving.value = true;
  setMappingAutosaveStatus("saving");
  try {
    const saved = await api.replacePermissionConfig(payload);
    hydrateFromConfig(saved);
    mappingsLastSavedSignature.value = permissionPayloadSignature(buildPermissionPayload());
    setMappingAutosaveStatus("saved");
    successMessage.value = "Access mappings updated.";
  } catch (err) {
    const message = err?.message || "Failed to save permissions config.";
    errorMessage.value = message;
    setMappingAutosaveStatus("error", message);
  } finally {
    saving.value = false;
    if (mappingsSaveQueued.value) {
      mappingsSaveQueued.value = false;
      void saveConfig();
    }
  }
}

async function createTemporaryCredential() {
  errorMessage.value = "";
  successMessage.value = "";
  const normalized = normalizeUsername(tempUsername.value);
  if (!normalized) {
    errorMessage.value = "Temporary credentials require a username.";
    return;
  }

  let expiresAt = null;
  try {
    expiresAt = localDateTimeToIso(tempExpiresAtLocal.value);
  } catch (err) {
    errorMessage.value = err?.message || "Invalid expiry date.";
    return;
  }

  tempCreating.value = true;
  try {
    const created = await api.createTempCredential({
      username: normalized,
      internal_role: normalizeRole(tempInternalRole.value),
      expires_at: expiresAt,
    });
    generatedCredential.value = created;
    tempUsername.value = "";
    tempInternalRole.value = defaultRole.value;
    tempExpiresAtLocal.value = defaultTempExpiryLocalValue();
    const credentials = await api.listTempCredentials();
    hydrateTempCredentials(credentials);
    successMessage.value = "Temporary credential generated.";
  } catch (err) {
    errorMessage.value = err?.message || "Failed to generate temporary credential.";
  } finally {
    tempCreating.value = false;
  }
}

function applyTempCredentialUpdate(target, rawEntry) {
  const wasSaving = Boolean(target.saving);
  const queuedFields = Array.isArray(target.save_queued) ? [...target.save_queued] : [];
  Object.assign(target, normalizeTempCredentialEntry(rawEntry), {
    saving: wasSaving,
    save_queued: queuedFields,
  });
}

function mergeTempCredentialSaveFields(currentFields, nextFields) {
  return Array.from(new Set([
    ...(Array.isArray(currentFields) ? currentFields : []),
    ...(Array.isArray(nextFields) ? nextFields : []),
  ]));
}

function buildTempCredentialPatch(entry, requestedFields = []) {
  const requested = new Set(Array.isArray(requestedFields) ? requestedFields : []);
  const payload = {};

  const username = normalizeUsername(entry.username);
  if (requested.has("username") || username !== entry._saved_username) {
    if (!username) {
      throw new Error("Temporary credentials require a username.");
    }
    payload.username = username;
  }

  const internalRole = normalizeRole(entry.internal_role);
  if (requested.has("internal_role") || internalRole !== entry._saved_internal_role) {
    payload.internal_role = internalRole;
  }

  const expiresAtLocal = String(entry.expires_at_local || "").trim();
  if (requested.has("expires_at") || expiresAtLocal !== entry._saved_expires_at_local) {
    if (!expiresAtLocal) {
      throw new Error("Temporary credential expiry is required.");
    }
    payload.expires_at = localDateTimeToIso(expiresAtLocal);
  }

  return payload;
}

async function saveTemporaryCredential(entry, requestedFields = []) {
  const credentialId = String(entry?.id || "").trim();
  if (!credentialId) return;

  if (entry.saving) {
    entry.save_queued = mergeTempCredentialSaveFields(entry.save_queued, requestedFields);
    return;
  }

  errorMessage.value = "";
  successMessage.value = "";
  let payload = {};
  try {
    payload = buildTempCredentialPatch(entry, requestedFields);
  } catch (err) {
    const message = err?.message || "Failed to prepare temporary credential update.";
    entry.save_error = message;
    errorMessage.value = message;
    return;
  }

  if (Object.keys(payload).length === 0) {
    entry.save_error = "";
    return;
  }

  entry.saving = true;
  entry.save_error = "";
  try {
    const saved = await api.patchTempCredential(credentialId, payload);
    applyTempCredentialUpdate(entry, saved);
    successMessage.value = `Credential "${saved.username}" updated.`;
  } catch (err) {
    const message = err?.message || "Failed to update temporary credential.";
    entry.save_error = message;
    errorMessage.value = message;
  } finally {
    const queuedFields = Array.isArray(entry.save_queued) ? [...entry.save_queued] : [];
    entry.save_queued = [];
    entry.saving = false;
    if (queuedFields.length) {
      void saveTemporaryCredential(entry, queuedFields);
    }
  }
}

function isTempCredentialActive(entry) {
  return Boolean(entry?.active) && !Boolean(entry?.is_expired);
}

function tempStatusLabel(entry) {
  if (!entry?.active) return "revoked";
  if (entry?.is_expired) return "expired";
  return "active";
}

function tempStatusClass(entry) {
  if (!entry?.active) return "status-revoked";
  if (entry?.is_expired) return "status-expired";
  return "status-active";
}

function formatDateTime(value) {
  return formatInstantInServerTimezone(value, {}, { fallback: "—" });
}

async function revokeTemporaryCredential(entry) {
  errorMessage.value = "";
  successMessage.value = "";
  const credentialId = String(entry?.id || "").trim();
  if (!credentialId) return;
  tempActionId.value = `revoke:${credentialId}`;
  try {
    await api.revokeTempCredential(credentialId);
    const credentials = await api.listTempCredentials();
    hydrateTempCredentials(credentials);
    successMessage.value = `Credential "${entry.username}" revoked.`;
  } catch (err) {
    errorMessage.value = err?.message || "Failed to revoke temporary credential.";
  } finally {
    tempActionId.value = "";
  }
}

async function deleteTemporaryCredential(entry) {
  errorMessage.value = "";
  successMessage.value = "";
  const credentialId = String(entry?.id || "").trim();
  if (!credentialId) return;
  if (!window.confirm(`Delete temporary credential "${entry.username}" permanently?`)) {
    return;
  }
  tempActionId.value = `delete:${credentialId}`;
  try {
    await api.deleteTempCredential(credentialId);
    const credentials = await api.listTempCredentials();
    hydrateTempCredentials(credentials);
    successMessage.value = `Credential "${entry.username}" deleted.`;
  } catch (err) {
    errorMessage.value = err?.message || "Failed to delete temporary credential.";
  } finally {
    tempActionId.value = "";
  }
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(String(text || ""));
    successMessage.value = "Copied to clipboard.";
    errorMessage.value = "";
  } catch {
    errorMessage.value = "Copy failed. Please copy manually.";
  }
}

async function copyGeneratedBundle() {
  if (!generatedCredential.value) return;
  const username = generatedCredential.value?.credential?.username || "";
  const password = generatedCredential.value?.generated_password || "";
  await copyToClipboard(`username: ${username}\npassword: ${password}`);
}

onMounted(async () => {
  tempExpiresAtLocal.value = defaultTempExpiryLocalValue();
  await loadConfig();
});

onBeforeUnmount(() => {
  clearMappingAutosaveStatusTimer();
});
</script>

<style scoped>
.card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
}

.card h2 {
  margin: 0;
  font-size: 18px;
  color: var(--admin-text);
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  color: var(--admin-text);
}

.hint {
  margin: 8px 0 12px;
  color: #64748b;
  font-size: 13px;
}

.pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: #eef2ff;
  color: #3730a3;
  font-weight: 700;
  font-size: 12px;
}

.mapping-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mapping-row {
  display: grid;
  grid-template-columns: 1fr 170px auto;
  gap: 10px;
}

.field {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 9px 10px;
  font-size: 14px;
}

.select {
  background: #fff;
}

.table-field {
  min-width: 150px;
  padding: 7px 8px;
  font-size: 13px;
}

.table-field--schedule {
  min-width: 190px;
}

.temp-datetime-picker {
  width: 100%;
  min-width: 0;
}

.temp-datetime-picker--table {
  min-width: 190px;
}

.temp-datetime-picker :deep(.dp__input_wrap) {
  width: 100%;
}

.temp-datetime-picker :deep(.dp__input) {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
  font: inherit;
  color: #0f172a;
  background: #fff;
}

.temp-datetime-picker--table :deep(.dp__input) {
  font-size: 13px;
}

.temp-datetime-picker :deep(.dp__input:focus) {
  border-color: rgba(59, 130, 246, 0.55);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.empty {
  color: #64748b;
  font-size: 14px;
}

.message {
  margin: 0;
  font-size: 14px;
}

.message.error {
  color: #b91c1c;
}

.message.success {
  color: #047857;
}

.temp-create-grid {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) 160px 210px auto;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}

.generated-card {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}

.generated-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.generated-warning {
  font-size: 12px;
  font-weight: 700;
  color: #9a3412;
}

.generated-grid {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px 10px;
  margin-bottom: 10px;
  align-items: center;
}

.generated-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #334155;
  font-weight: 700;
}

.credential-table-wrap {
  overflow-x: auto;
}

.credential-table {
  width: 100%;
  border-collapse: collapse;
}

.credential-table th,
.credential-table td {
  text-align: left;
  padding: 9px 8px;
  border-bottom: 1px solid #e2e8f0;
  font-size: 13px;
}

.credential-table th {
  color: #475569;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.actions-col {
  text-align: right;
  white-space: nowrap;
}

.actions-col .btn-secondary,
.actions-col .btn-danger {
  margin-left: 6px;
}

.row-save-status {
  display: inline-flex;
  margin-right: 8px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  vertical-align: middle;
}

.row-save-status--error {
  color: #b91c1c;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.status-active {
  background: #dcfce7;
  color: #166534;
}

.status-expired {
  background: color-mix(in srgb, var(--admin-warning-color, #d97706) 16%, #ffffff);
  color: color-mix(in srgb, var(--admin-warning-color, #d97706) 90%, #0f172a);
}

.status-revoked {
  background: #e2e8f0;
  color: #334155;
}

@media (max-width: 1200px) {
  .temp-create-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 900px) {
  .mapping-row {
    grid-template-columns: 1fr;
  }

  .temp-create-grid {
    grid-template-columns: 1fr;
  }

  .generated-grid {
    grid-template-columns: 1fr;
  }

  .actions-col {
    text-align: left;
  }

  .actions-col .btn-secondary,
  .actions-col .btn-danger {
    margin-left: 0;
    margin-right: 6px;
    margin-top: 6px;
  }
}
</style>
