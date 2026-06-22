<template>
  <Teleport to="body">
    <div v-if="visible" class="ucg-overlay" @click.self="cancel">
      <div class="ucg-dialog">
        <div class="ucg-header">
          <span class="ucg-title">Unsaved Design Changes</span>
        </div>

        <div class="ucg-body">
          <p class="ucg-message">You have unsaved changes that will be lost:</p>

          <div class="ucg-groups">
            <div v-for="(items, section) in groups" :key="section" class="ucg-group">
              <div class="ucg-section-label">{{ section }}</div>
              <ul class="ucg-items">
                <li v-for="item in items" :key="item">{{ item }}</li>
              </ul>
            </div>
          </div>
        </div>

        <div class="ucg-actions">
          <button class="ucg-btn ucg-btn-save" :disabled="saving" @click="save">
            {{ saving ? 'Saving…' : 'Save & Continue' }}
          </button>
          <button class="ucg-btn ucg-btn-discard" @click="discard">Discard & Continue</button>
          <button class="ucg-btn ucg-btn-cancel" @click="cancel">Stay on Page</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, shallowRef } from "vue";
import { useStore } from "../../store/store.js";

const { saveDesignSettings } = useStore();

const visible = ref(false);
const saving = ref(false);
const groups = shallowRef({});
let _resolve = null;

async function save() {
  saving.value = true;
  try {
    await saveDesignSettings();
    visible.value = false;
    _resolve?.('save');
  } catch {
    saving.value = false;
  }
}

function discard() {
  visible.value = false;
  _resolve?.('discard');
}

function cancel() {
  visible.value = false;
  _resolve?.('cancel');
}

function show(groupedChanges) {
  groups.value = groupedChanges;
  saving.value = false;
  visible.value = true;
  return new Promise((resolve) => { _resolve = resolve; });
}

defineExpose({ show });
</script>

<style scoped>
.ucg-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--admin-z-blocking-modal, 12000);
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
}

.ucg-dialog {
  width: min(420px, calc(100vw - 32px));
  max-height: 80vh;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.22);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ucg-header {
  padding: 16px 20px 12px;
  border-bottom: 1px solid #e2e8f0;
}

.ucg-title {
  font-weight: 800;
  font-size: 15px;
  color: #0f172a;
}

.ucg-body {
  padding: 16px 20px;
  overflow-y: auto;
}

.ucg-message {
  font-size: 13px;
  color: #475569;
  margin: 0 0 12px;
  line-height: 1.5;
}

.ucg-groups {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ucg-group {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
}

.ucg-section-label {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}

.ucg-items {
  margin: 0;
  padding: 0 0 0 16px;
  font-size: 13px;
  color: #1e293b;
  line-height: 1.6;
}

.ucg-actions {
  padding: 12px 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-top: 1px solid #e2e8f0;
}

.ucg-btn {
  width: 100%;
  padding: 10px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.ucg-btn-save {
  background: var(--accent, #4f46e5);
  color: #fff;
  border: none;
}
.ucg-btn-save:hover:not(:disabled) { filter: brightness(1.1); }
.ucg-btn-save:disabled { opacity: 0.5; cursor: not-allowed; }

.ucg-btn-discard {
  background: #fff;
  color: #dc2626;
  border: 1px solid #fecaca;
}
.ucg-btn-discard:hover { background: #fef2f2; }

.ucg-btn-cancel {
  background: #fff;
  color: #64748b;
  border: 1px solid #e2e8f0;
}
.ucg-btn-cancel:hover { background: #f8fafc; }
</style>
