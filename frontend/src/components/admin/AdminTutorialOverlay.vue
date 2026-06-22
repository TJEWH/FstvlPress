<template>
  <Teleport v-if="launcherTargetReady" :to="launcherTargetSelector">
    <div class="admin-tutorial-launcher" :class="{ 'is-open': launcherOpen }">
      <button
        type="button"
        class="admin-tutorial-launcher__trigger"
        title="Tutorials"
        aria-label="Tutorials"
        :aria-expanded="launcherOpen"
        @click="toggleLauncher"
      >
        <font-awesome-icon :icon="faClipboardList" />
      </button>

      <section v-if="launcherOpen" class="admin-tutorial-launcher__panel" aria-label="Tutorial launcher">
        <header class="admin-tutorial-launcher__header">
          <div>
            <h2>Tutorials</h2>
            <span>{{ tutorials.length }} available</span>
          </div>
          <button type="button" class="admin-tutorial-icon-btn" title="Close" @click="launcherOpen = false">
            <font-awesome-icon :icon="faXmark" />
          </button>
        </header>

        <div class="admin-tutorial-launcher__actions">
          <button type="button" class="btn-primary btn-sm" @click="openCreateTutorial">
            Create
          </button>
        </div>

        <div v-if="launcherError" class="status-message error">{{ launcherError }}</div>
        <div v-else-if="launcherLoading" class="admin-tutorial-launcher__empty">Loading tutorials...</div>
        <div v-else-if="tutorials.length === 0" class="admin-tutorial-launcher__empty">No tutorials available.</div>
        <div v-else class="admin-tutorial-launcher__list">
          <article
            v-for="tutorial in tutorials"
            :key="tutorial.id"
            class="admin-tutorial-launcher__item"
            :class="{ active: isActiveTutorial(tutorial) }"
          >
            <div class="admin-tutorial-launcher__item-main">
              <h3>{{ tutorial.title }}</h3>
              <p v-if="tutorial.description">{{ tutorial.description }}</p>
            </div>
            <div class="admin-tutorial-launcher__item-actions">
              <button type="button" class="btn-primary btn-sm" @click="startTutorialFromLauncher(tutorial)">
                Start
              </button>
              <button
                v-if="isActiveTutorial(tutorial)"
                type="button"
                class="btn-outline btn-sm"
                @click="stopTutorialFromLauncher"
              >
                Stop
              </button>
            </div>
          </article>
        </div>
      </section>
    </div>
  </Teleport>

  <Teleport to="body">
    <section
      v-if="overlayState.builderOpen && !builderHidden"
      class="admin-tutorial-panel admin-tutorial-panel--builder"
      :style="builderPanelStyle"
      aria-label="Tutorial builder"
    >
      <header class="admin-tutorial-panel__header" @pointerdown="startPanelDrag('builder', $event)">
        <div class="admin-tutorial-panel__handle" aria-hidden="true">::</div>
        <div class="admin-tutorial-panel__title">
          <h2>{{ form.id ? "Edit Tutorial" : "Create Tutorial" }}</h2>
          <span>{{ builderLocationLabel }}</span>
        </div>
        <div class="admin-tutorial-panel__header-actions">
          <button
            type="button"
            class="btn-outline btn-sm"
            @pointerdown.stop
            @click="hideBuilder"
          >
            Hide
          </button>
        </div>
      </header>

      <form class="admin-tutorial-builder" @submit.prevent="saveBuilder">
        <aside class="admin-tutorial-builder__nav" aria-label="Tutorial sections">
          <button
            type="button"
            class="admin-tutorial-builder__nav-item"
            :class="{ active: builderActiveIndex === 0 }"
            @click="setBuilderActiveIndex(0)"
          >
            <span class="admin-tutorial-builder__nav-index">Config</span>
          </button>
          <button
            v-for="(step, index) in form.steps"
            :key="step.clientId"
            type="button"
            class="admin-tutorial-builder__nav-item"
            :class="{ active: builderActiveIndex === index + 1 }"
            @click="setBuilderActiveIndex(index + 1)"
          >
            <span class="admin-tutorial-builder__nav-index">{{ index + 1 }}</span>
          </button>
          <button type="button" class="btn-outline btn-sm admin-tutorial-builder__add" title="Add step" @click="addStep">
            +
          </button>
        </aside>

        <main class="admin-tutorial-builder__main">
          <section v-if="builderActiveIndex === 0" class="admin-tutorial-builder__page">
            <div class="admin-tutorial-builder__page-head">
              <div>
                <h3>Tutorial Config</h3>
                <p>Set the title, description, and role scope.</p>
              </div>
            </div>

            <label class="admin-tutorial-field">
              <span>Title</span>
              <input v-model="form.title" class="admin-control" type="text" maxlength="140" required />
            </label>

            <label class="admin-tutorial-field">
              <span>Description</span>
              <textarea v-model="form.description" class="admin-control" rows="6" maxlength="2000" />
            </label>

            <label class="admin-tutorial-field">
              <span>Scope</span>
              <select v-model="form.scope" class="admin-control">
                <option v-for="option in builderScopeOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
          </section>

          <section v-else-if="activeFormStep" class="admin-tutorial-builder__page">
            <div class="admin-tutorial-builder__page-head">
              <div>
                <h3>Step {{ activeStepIndex + 1 }} of {{ form.steps.length }}</h3>
                <p>{{ activeFormStep.short_description || "Describe what should happen here." }}</p>
              </div>
              <div class="admin-tutorial-builder__step-actions">
                <button type="button" class="btn-outline btn-sm" @click="useCurrentUrl(activeFormStep)">
                  Use Current URL
                </button>
                <button type="button" class="btn-outline btn-sm" :disabled="activeStepIndex <= 0" @click="moveStep(activeStepIndex, -1)">
                  Up
                </button>
                <button type="button" class="btn-outline btn-sm" :disabled="activeStepIndex >= form.steps.length - 1" @click="moveStep(activeStepIndex, 1)">
                  Down
                </button>
                <button type="button" class="btn-danger btn-sm" :disabled="form.steps.length <= 1" @click="removeStep(activeStepIndex)">
                  Remove
                </button>
              </div>
            </div>

            <label class="admin-tutorial-field">
              <span>URL</span>
              <input
                v-model="activeFormStep.url"
                class="admin-control"
                type="text"
                maxlength="500"
                required
              />
            </label>

            <label class="admin-tutorial-field">
              <span>Short Description</span>
              <input
                v-model="activeFormStep.short_description"
                class="admin-control"
                type="text"
                maxlength="280"
                required
              />
            </label>

            <label class="admin-tutorial-field">
              <span>Long Description</span>
              <textarea
                v-model="activeFormStep.long_description"
                class="admin-control"
                rows="10"
                maxlength="2400"
              />
            </label>
          </section>

          <div v-if="builderError" class="status-message error">{{ builderError }}</div>

          <footer class="admin-tutorial-builder__actions">
            <div class="admin-tutorial-builder__pager">
              <span>{{ builderLocationLabel }}</span>
            </div>
            <div class="admin-tutorial-builder__save-actions">
              <button type="button" class="btn-danger btn-sm" @click="cancelBuilder">
                Cancel
              </button>
              <button type="submit" class="btn-primary btn-sm" :disabled="builderSaving || !canSaveBuilder">
                {{ builderSaving ? "Saving..." : "Save Tutorial" }}
              </button>
            </div>
          </footer>
        </main>
      </form>
    </section>

    <section
      v-if="activeTutorial && !followerHidden"
      class="admin-tutorial-panel admin-tutorial-panel--follower"
      :style="followerPanelStyle"
      aria-label="Active tutorial"
    >
      <header class="admin-tutorial-panel__header" @pointerdown="startPanelDrag('follower', $event)">
        <div class="admin-tutorial-panel__handle" aria-hidden="true">::</div>
        <div class="admin-tutorial-panel__title">
          <h2>{{ activeTutorial.title }}</h2>
        </div>
        <div class="admin-tutorial-panel__header-actions">
          <button
            type="button"
            class="btn-outline btn-sm"
            @pointerdown.stop
            @click="hideFollower"
          >
            Hide
          </button>
        </div>
      </header>

      <div class="admin-tutorial-builder admin-tutorial-follower">
        <aside class="admin-tutorial-builder__nav" aria-label="Tutorial step navigator">
          <button
            v-for="entry in stepEntries"
            :key="entry.step.id"
            type="button"
            class="admin-tutorial-builder__nav-item admin-tutorial-follower__nav-item"
            :class="{
              active: selectedFollowerIndex === entry.index,
              'is-done': entry.done,
              'is-disabled': !canViewFollowerStep(entry.index),
            }"
            :disabled="!canViewFollowerStep(entry.index)"
            @click="setFollowerActiveIndex(entry.index)"
          >
            <span class="admin-tutorial-builder__nav-index">
              {{ entry.index + 1 }}
            </span>
          </button>
        </aside>

        <main class="admin-tutorial-builder__main">
          <section v-if="activeFollowerGroupEntries.length > 0" class="admin-tutorial-builder__page">
            <div class="admin-tutorial-url-row">
              <span>{{ formatUrlLabel(activeFollowerGroupUrl) }}</span>
              <a
                v-if="shouldShowOpenLink(activeFollowerGroupUrl)"
                class="btn-outline btn-sm"
                :href="activeFollowerGroupUrl"
              >
                Open
              </a>
            </div>

            <label
              v-for="entry in activeFollowerGroupEntries"
              :key="entry.step.id"
              class="admin-tutorial-step admin-tutorial-follower__current-step"
              :class="{
                'is-done': entry.done,
                'is-current': entry.index === currentOpenIndex,
                'is-disabled': !canToggleStep(entry.index),
              }"
            >
              <span class="admin-tutorial-step__main">
                <input
                  type="checkbox"
                  :checked="entry.done"
                  :disabled="!canToggleStep(entry.index)"
                  @change="toggleStep(entry.index, $event.target.checked)"
                />
                <span class="admin-tutorial-step__number">{{ entry.index + 1 }}</span>
                <span class="admin-tutorial-step__text">{{ entry.step.short_description }}</span>
              </span>
              <span
                v-if="!entry.done && entry.step.long_description"
                class="admin-tutorial-step__long"
              >
                {{ entry.step.long_description }}
              </span>
            </label>

            <p v-if="activeTutorial.description && selectedFollowerIndex === 0" class="admin-tutorial-follower__description">
              {{ activeTutorial.description }}
            </p>

            <div v-if="allStepsDone" class="admin-tutorial-complete">
              Tutorial complete.
            </div>
          </section>

          <footer class="admin-tutorial-builder__actions">
            <div class="admin-tutorial-builder__pager">
              <span>{{ doneCount }} / {{ activeSteps.length }} done</span>
            </div>
            <div class="admin-tutorial-builder__save-actions">
              <button type="button" class="btn-danger btn-sm" @click="resetActiveTutorial">
                Reset
              </button>
              <button
                type="button"
                :class="[allStepsDone ? 'btn-outline' : 'btn-danger', 'btn-sm']"
                @click="stopActiveTutorial"
              >
                {{ allStepsDone ? "Close" : "Stop" }}
              </button>
            </div>
          </footer>
        </main>
      </div>
    </section>

    <div
      v-if="(overlayState.builderOpen && builderHidden) || (activeTutorial && followerHidden)"
      class="admin-tutorial-sticky-stack"
    >
      <button
        v-if="overlayState.builderOpen && builderHidden"
        type="button"
        class="admin-tutorial-sticky-resume"
        @click="showBuilder"
      >
        Tutorial Draft
        <span>{{ form.title || (form.id ? "Edit tutorial" : "Create tutorial") }}</span>
      </button>
      <button
        v-if="activeTutorial && followerHidden"
        type="button"
        class="admin-tutorial-sticky-resume"
        @click="showFollower"
      >
        Current Tutorial
        <span>{{ activeTutorial.title }}</span>
      </button>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { faClipboardList, faXmark } from "@fortawesome/free-solid-svg-icons";
import * as api from "../../services/api.js";
import {
  TUTORIAL_SCOPE_OPTIONS,
  closeTutorialBuilder,
  notifyTutorialsChanged,
  openTutorialBuilder,
  restoreActiveTutorial,
  startTutorial,
  stopTutorial,
  tutorialRoleRank,
  tutorialScopeOptionsForCurrentUser,
  updateTutorialProgress,
  useAdminTutorialOverlay,
} from "../../composables/useAdminTutorialOverlay.js";
import { getInternalRole, getUser } from "../../services/auth.js";

const route = useRoute();
const { state: overlayState } = useAdminTutorialOverlay();
const LAUNCHER_TARGET_ID = "tutorial-launcher-slot";
const WINDOW_SESSION_PREFIX = "fstvlpress-admin-tutorial-window:v1:";

const PANEL_SIZES = Object.freeze({
  builder: { width: 760, height: 660 },
  follower: { width: 760, height: 660 },
});
const PANEL_STORAGE_KEYS = Object.freeze({
  builder: "fstvlpress-admin-tutorial-panel:builder:v1",
  follower: "fstvlpress-admin-tutorial-panel:follower:v1",
});

const builderPosition = reactive(loadPanelPosition("builder"));
const followerPosition = reactive(loadPanelPosition("follower"));
const builderSaving = ref(false);
const builderError = ref("");
const builderActiveIndex = ref(0);
const builderHidden = ref(false);
const followerActiveIndex = ref(0);
const followerHidden = ref(false);
const activeDrag = ref(null);
const launcherOpen = ref(false);
const launcherTargetReady = ref(false);
const launcherLoading = ref(false);
const launcherError = ref("");
const tutorials = ref([]);
const form = reactive({
  id: "",
  title: "",
  description: "",
  scope: defaultScope(),
  steps: [],
});
let restoringWindowSession = false;

const activeTutorial = computed(() => overlayState.activeTutorial);
const activeSteps = computed(() => activeTutorial.value?.steps || []);
const doneStepIds = computed(() => new Set(overlayState.doneStepIds || []));
const doneCount = computed(() => activeSteps.value.filter((step) => doneStepIds.value.has(step.id)).length);
const currentOpenIndex = computed(() => activeSteps.value.findIndex((step) => !doneStepIds.value.has(step.id)));
const allStepsDone = computed(() => activeSteps.value.length > 0 && currentOpenIndex.value < 0);
const activeStepIndex = computed(() => Math.max(0, builderActiveIndex.value - 1));
const activeFormStep = computed(() => builderActiveIndex.value > 0 ? form.steps[activeStepIndex.value] : null);
const launcherTargetSelector = computed(() => `#${LAUNCHER_TARGET_ID}`);

const builderLocationLabel = computed(() => {
  if (builderActiveIndex.value === 0) return "Config";
  return `Step ${builderActiveIndex.value} of ${form.steps.length}`;
});

const selectedFollowerIndex = computed(() => {
  const maxIndex = Math.max(0, activeSteps.value.length - 1);
  return Math.min(Math.max(0, Number(followerActiveIndex.value) || 0), maxIndex);
});

const activeFollowerEntry = computed(() => stepEntries.value[selectedFollowerIndex.value] || null);
const activeFollowerGroupEntries = computed(() => {
  const entries = stepEntries.value;
  const activeEntry = activeFollowerEntry.value;
  if (!activeEntry) return [];

  const activeUrl = normalizeComparableUrl(activeEntry.step.url);
  let startIndex = activeEntry.index;
  let endIndex = activeEntry.index;

  while (
    startIndex > 0
    && normalizeComparableUrl(entries[startIndex - 1]?.step?.url) === activeUrl
  ) {
    startIndex -= 1;
  }

  while (
    endIndex < entries.length - 1
    && normalizeComparableUrl(entries[endIndex + 1]?.step?.url) === activeUrl
  ) {
    endIndex += 1;
  }

  return entries.slice(startIndex, endIndex + 1);
});
const activeFollowerGroupUrl = computed(() => activeFollowerGroupEntries.value[0]?.step?.url || activeFollowerEntry.value?.step?.url || "");

const builderPanelStyle = computed(() => ({
  left: `${builderPosition.x}px`,
  top: `${builderPosition.y}px`,
}));

const followerPanelStyle = computed(() => ({
  left: `${followerPosition.x}px`,
  top: `${followerPosition.y}px`,
}));

const currentUrl = computed(() => route.fullPath || "/admin");
const currentComparableUrl = computed(() => normalizeComparableUrl(currentUrl.value));

const builderScopeOptions = computed(() => {
  const allowed = tutorialScopeOptionsForCurrentUser();
  if (allowed.some((option) => option.value === form.scope)) return allowed;
  const current = TUTORIAL_SCOPE_OPTIONS.find((option) => option.value === form.scope);
  return current
    ? [...allowed, current].sort((left, right) => tutorialRoleRank(left.value) - tutorialRoleRank(right.value))
    : allowed;
});

const canSaveBuilder = computed(() => {
  if (!String(form.title || "").trim()) return false;
  if (!form.steps.length) return false;
  return form.steps.every((step) => (
    String(step.url || "").trim()
    && String(step.short_description || "").trim()
  ));
});

const stepEntries = computed(() => activeSteps.value.map((step, index, steps) => ({
  step,
  index,
  done: doneStepIds.value.has(step.id),
  showUrl: index === 0 || normalizeComparableUrl(step.url) !== normalizeComparableUrl(steps[index - 1]?.url),
})));

function defaultScope() {
  const role = String(getInternalRole?.() || "content");
  return tutorialRoleRank(role) > 0 ? role : "content";
}

function normalizeTutorialStep(raw, index = 0) {
  return {
    id: String(raw?.id || `step-${index + 1}`),
    url: String(raw?.url || "/admin"),
    short_description: String(raw?.short_description || "").trim(),
    long_description: String(raw?.long_description || "").trim(),
    order: Number.isFinite(Number(raw?.order)) ? Number(raw.order) : index,
  };
}

function normalizeTutorial(raw) {
  const steps = Array.isArray(raw?.steps) ? raw.steps : [];
  return {
    id: String(raw?.id || ""),
    title: String(raw?.title || "").trim() || "Untitled Tutorial",
    description: String(raw?.description || "").trim(),
    scope: String(raw?.scope || "content").trim() || "content",
    owner: String(raw?.owner || "unknown").trim() || "unknown",
    owner_id: String(raw?.owner_id || "").trim(),
    created_at: raw?.created_at || null,
    updated_at: raw?.updated_at || null,
    can_edit: Boolean(raw?.can_edit),
    steps: steps
      .map((step, index) => normalizeTutorialStep(step, index))
      .sort((left, right) => (left.order ?? 0) - (right.order ?? 0)),
  };
}

function normalizeTutorialList(payload) {
  const rawItems = Array.isArray(payload?.items) ? payload.items : (Array.isArray(payload) ? payload : []);
  return rawItems
    .map((entry) => normalizeTutorial(entry))
    .filter((entry) => entry.id && entry.steps.length > 0)
    .sort((left, right) => left.title.localeCompare(right.title));
}

async function loadTutorials() {
  if (launcherLoading.value) return;
  launcherLoading.value = true;
  launcherError.value = "";
  try {
    const payload = await api.getAdminDevopsTutorials();
    tutorials.value = normalizeTutorialList(payload);
  } catch (err) {
    console.error("Failed to load tutorials:", err);
    launcherError.value = err?.message || "Failed to load tutorials.";
  } finally {
    launcherLoading.value = false;
  }
}

function toggleLauncher() {
  launcherOpen.value = !launcherOpen.value;
  if (launcherOpen.value) void loadTutorials();
}

function openCreateTutorial() {
  launcherOpen.value = false;
  openTutorialBuilder();
  builderHidden.value = false;
}

function startTutorialFromLauncher(tutorial) {
  startTutorial(tutorial);
  followerHidden.value = false;
  launcherOpen.value = false;
}

function stopTutorialFromLauncher() {
  if (stopActiveTutorial()) {
    launcherOpen.value = false;
  }
}

function isActiveTutorial(tutorial) {
  return Boolean(tutorial?.id && overlayState.activeTutorial?.id === tutorial.id);
}

function currentWindowSessionKey() {
  if (typeof window === "undefined" || !window.sessionStorage) return "";
  const user = getUser?.();
  const identity = String(user?.sub || user?.username || user?.name || getInternalRole?.() || "anonymous").trim() || "anonymous";
  return `${WINDOW_SESSION_PREFIX}${identity}`;
}

function readTutorialWindowSession() {
  const key = currentWindowSessionKey();
  if (!key) return null;
  try {
    const raw = window.sessionStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeTutorialWindowSession(payload) {
  const key = currentWindowSessionKey();
  if (!key) return;
  try {
    if (!payload?.builder && !payload?.follower) {
      window.sessionStorage.removeItem(key);
      return;
    }
    window.sessionStorage.setItem(key, JSON.stringify(payload));
  } catch {
    // Session persistence is best effort.
  }
}

function buildSessionTutorialDraft() {
  return {
    id: String(form.id || ""),
    title: String(form.title || ""),
    description: String(form.description || ""),
    scope: String(form.scope || defaultScope()),
    steps: form.steps.map((step, index) => ({
      id: String(step.id || ""),
      url: String(step.url || currentUrl.value || "/admin"),
      short_description: String(step.short_description || ""),
      long_description: String(step.long_description || ""),
      order: index,
    })),
  };
}

function persistTutorialWindowSession() {
  if (restoringWindowSession) return;

  const payload = {};
  if (overlayState.builderOpen) {
    payload.builder = {
      hidden: Boolean(builderHidden.value),
      activeIndex: Math.max(0, Number(builderActiveIndex.value) || 0),
      tutorial: buildSessionTutorialDraft(),
    };
  }
  if (activeTutorial.value) {
    payload.follower = {
      hidden: Boolean(followerHidden.value),
      activeIndex: Math.max(0, Number(followerActiveIndex.value) || 0),
    };
  }
  writeTutorialWindowSession(payload);
}

function restoreBuilderSession(builderSession) {
  if (!builderSession?.tutorial || typeof builderSession.tutorial !== "object") return;
  const steps = Array.isArray(builderSession.tutorial.steps) ? builderSession.tutorial.steps : [];
  if (steps.length === 0) return;

  openTutorialBuilder(builderSession.tutorial);
  resetBuilderForm();
  builderHidden.value = Boolean(builderSession.hidden);
  setBuilderActiveIndex(Number(builderSession.activeIndex) || 0);
}

function restoreFollowerSession(followerSession) {
  if (!activeTutorial.value) {
    followerHidden.value = false;
    followerActiveIndex.value = 0;
    return;
  }

  const maxIndex = Math.max(0, activeSteps.value.length - 1);
  const storedIndex = Number(followerSession?.activeIndex);
  if (Number.isFinite(storedIndex)) {
    followerActiveIndex.value = Math.min(Math.max(0, storedIndex), maxIndex);
  }
  if (!Number.isFinite(storedIndex) || !canViewFollowerStep(followerActiveIndex.value)) {
    syncFollowerActiveIndexToCurrent();
  }
  followerHidden.value = Boolean(followerSession?.hidden);
}

function restoreTutorialWindowSession() {
  const session = readTutorialWindowSession();
  restoreBuilderSession(session?.builder);
  restoreFollowerSession(session?.follower);
}

function refreshLauncherTarget() {
  launcherTargetReady.value = typeof document !== "undefined" && Boolean(document.getElementById(LAUNCHER_TARGET_ID));
}

function hideBuilder() {
  builderHidden.value = true;
}

function showBuilder() {
  builderHidden.value = false;
}

function hideFollower() {
  followerHidden.value = true;
}

function showFollower() {
  followerHidden.value = false;
}

function loadPanelPosition(kind) {
  const fallback = fallbackPanelPosition(kind);
  if (typeof window === "undefined") return fallback;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(PANEL_STORAGE_KEYS[kind]) || "{}");
    return clampPanelPosition(kind, {
      x: Number.isFinite(Number(parsed.x)) ? Number(parsed.x) : fallback.x,
      y: Number.isFinite(Number(parsed.y)) ? Number(parsed.y) : fallback.y,
    });
  } catch {
    return fallback;
  }
}

function fallbackPanelPosition(kind) {
  if (typeof window === "undefined") return { x: 24, y: 72 };
  const size = PANEL_SIZES[kind] || PANEL_SIZES.follower;
  return {
    x: Math.max(16, window.innerWidth - size.width - 24),
    y: kind === "builder" ? 72 : 88,
  };
}

function clampPanelPosition(kind, position) {
  if (typeof window === "undefined") return position;
  const size = PANEL_SIZES[kind] || PANEL_SIZES.follower;
  const maxX = Math.max(16, window.innerWidth - Math.min(size.width, window.innerWidth - 24) - 12);
  const maxY = Math.max(16, window.innerHeight - 96);
  return {
    x: Math.min(Math.max(12, Number(position.x) || 12), maxX),
    y: Math.min(Math.max(12, Number(position.y) || 12), maxY),
  };
}

function persistPanelPosition(kind) {
  if (typeof window === "undefined") return;
  const position = kind === "builder" ? builderPosition : followerPosition;
  try {
    window.localStorage.setItem(PANEL_STORAGE_KEYS[kind], JSON.stringify({ x: position.x, y: position.y }));
  } catch {
    // Panel position persistence is best effort.
  }
}

function assignPanelPosition(kind, position) {
  const clamped = clampPanelPosition(kind, position);
  const target = kind === "builder" ? builderPosition : followerPosition;
  target.x = clamped.x;
  target.y = clamped.y;
}

function startPanelDrag(kind, event) {
  if (event.button !== 0) return;
  const target = kind === "builder" ? builderPosition : followerPosition;
  activeDrag.value = {
    kind,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    initialX: target.x,
    initialY: target.y,
  };
  event.currentTarget?.setPointerCapture?.(event.pointerId);
  window.addEventListener("pointermove", onPanelDragMove);
  window.addEventListener("pointerup", finishPanelDrag, { once: true });
  event.preventDefault();
}

function onPanelDragMove(event) {
  const drag = activeDrag.value;
  if (!drag) return;
  assignPanelPosition(drag.kind, {
    x: drag.initialX + event.clientX - drag.startX,
    y: drag.initialY + event.clientY - drag.startY,
  });
}

function finishPanelDrag() {
  const drag = activeDrag.value;
  window.removeEventListener("pointermove", onPanelDragMove);
  if (drag) persistPanelPosition(drag.kind);
  activeDrag.value = null;
}

function clampPanelsToViewport() {
  assignPanelPosition("builder", builderPosition);
  assignPanelPosition("follower", followerPosition);
}

function makeFormStep(step = {}, index = 0) {
  return {
    clientId: String(step.id || `draft-${Date.now()}-${Math.random().toString(36).slice(2, 8)}-${index}`),
    id: String(step.id || ""),
    url: String(step.url || currentUrl.value || "/admin"),
    short_description: String(step.short_description || ""),
    long_description: String(step.long_description || ""),
  };
}

function resetBuilderForm() {
  const tutorial = overlayState.builderTutorial;
  form.id = String(tutorial?.id || "");
  form.title = String(tutorial?.title || "");
  form.description = String(tutorial?.description || "");
  form.scope = String(tutorial?.scope || defaultScope());
  form.steps = Array.isArray(tutorial?.steps) && tutorial.steps.length > 0
    ? tutorial.steps.map((step, index) => makeFormStep(step, index))
    : [makeFormStep({ url: currentUrl.value }, 0)];
  builderActiveIndex.value = 0;
  builderError.value = "";
}

function setBuilderActiveIndex(index) {
  builderActiveIndex.value = Math.max(0, Math.min(Number(index) || 0, form.steps.length));
}

function canViewFollowerStep(index) {
  const step = activeSteps.value[index];
  if (!step) return false;
  return allStepsDone.value || doneStepIds.value.has(step.id) || index === currentOpenIndex.value;
}

function setFollowerActiveIndex(index) {
  const normalized = Number(index) || 0;
  if (!canViewFollowerStep(normalized)) return;
  followerActiveIndex.value = normalized;
}

function syncFollowerActiveIndexToCurrent() {
  if (!activeSteps.value.length) {
    followerActiveIndex.value = 0;
    return;
  }
  if (currentOpenIndex.value >= 0) {
    followerActiveIndex.value = currentOpenIndex.value;
    return;
  }
  followerActiveIndex.value = activeSteps.value.length - 1;
}

function addStep() {
  form.steps.push(makeFormStep({ url: currentUrl.value }, form.steps.length));
  setBuilderActiveIndex(form.steps.length);
}

function removeStep(index) {
  if (form.steps.length <= 1) return;
  if (index < 0 || index >= form.steps.length) return;
  form.steps.splice(index, 1);
  setBuilderActiveIndex(Math.min(index + 1, form.steps.length));
}

function moveStep(index, direction) {
  const targetIndex = index + direction;
  if (index < 0 || targetIndex < 0 || index >= form.steps.length || targetIndex >= form.steps.length) return;
  const [step] = form.steps.splice(index, 1);
  form.steps.splice(targetIndex, 0, step);
  setBuilderActiveIndex(targetIndex + 1);
}

function useCurrentUrl(step) {
  step.url = currentUrl.value || "/admin";
}

function normalizeBuilderUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return currentUrl.value || "/admin";
  if (/^https?:\/\//i.test(raw) || raw.startsWith("/")) return raw;
  return `/${raw.replace(/^\/+/, "")}`;
}

function buildTutorialPayload() {
  return {
    title: String(form.title || "").trim(),
    description: String(form.description || "").trim(),
    scope: form.scope,
    steps: form.steps.map((step, index) => ({
      id: String(step.id || "").trim() || undefined,
      url: normalizeBuilderUrl(step.url),
      short_description: String(step.short_description || "").trim(),
      long_description: String(step.long_description || "").trim(),
      order: index,
    })),
  };
}

async function saveBuilder() {
  if (builderSaving.value || !canSaveBuilder.value) return;
  const confirmed = window.confirm("Save this tutorial?");
  if (!confirmed) return;
  builderSaving.value = true;
  builderError.value = "";
  try {
    const payload = buildTutorialPayload();
    const saved = form.id
      ? await api.updateAdminDevopsTutorial(form.id, payload)
      : await api.createAdminDevopsTutorial(payload);
    notifyTutorialsChanged();
    await loadTutorials();
    if (overlayState.activeTutorial?.id === saved?.id) {
      startTutorial(saved, { resume: true });
    }
    closeTutorialBuilder();
  } catch (err) {
    console.error("Failed to save tutorial:", err);
    builderError.value = err?.message || "Failed to save tutorial.";
  } finally {
    builderSaving.value = false;
  }
}

function cancelBuilder() {
  if (builderSaving.value) return;
  const confirmed = window.confirm("Cancel this tutorial draft? Unsaved changes will be lost.");
  if (!confirmed) return;
  builderHidden.value = false;
  closeTutorialBuilder();
}

function canToggleStep(index) {
  const step = activeSteps.value[index];
  if (!step) return false;
  return doneStepIds.value.has(step.id) || index === currentOpenIndex.value;
}

function toggleStep(index, checked) {
  if (!canToggleStep(index)) return;
  const steps = activeSteps.value;
  const step = steps[index];
  if (!step) return;
  const done = new Set(overlayState.doneStepIds || []);
  const isDone = done.has(step.id);

  if (isDone && !checked) {
    updateTutorialProgress(steps.slice(0, index).filter((item) => done.has(item.id)).map((item) => item.id));
    return;
  }
  if (!isDone && checked && index === currentOpenIndex.value) {
    updateTutorialProgress([...steps.slice(0, index).filter((item) => done.has(item.id)).map((item) => item.id), step.id]);
  }
}

function resetActiveTutorial() {
  updateTutorialProgress([]);
  followerHidden.value = false;
  followerActiveIndex.value = 0;
}

function stopActiveTutorial() {
  if (!allStepsDone.value) {
    const confirmed = window.confirm("Stop the active tutorial?");
    if (!confirmed) return false;
  }
  followerHidden.value = false;
  followerActiveIndex.value = 0;
  stopTutorial();
  return true;
}

function normalizeComparableUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (typeof window === "undefined") return raw;
  try {
    const url = new URL(raw, window.location.origin);
    if (url.origin === window.location.origin) {
      return `${url.pathname}${url.search}${url.hash}`;
    }
    return url.href;
  } catch {
    return raw;
  }
}

function formatUrlLabel(value) {
  const raw = String(value || "").trim();
  if (!raw) return "/";
  if (typeof window === "undefined") return raw;
  try {
    const url = new URL(raw, window.location.origin);
    if (url.origin === window.location.origin) {
      return `${url.pathname}${url.search}${url.hash}`;
    }
    return url.href;
  } catch {
    return raw;
  }
}

function shouldShowOpenLink(value) {
  return normalizeComparableUrl(value) !== currentComparableUrl.value;
}

watch(
  () => overlayState.builderOpen,
  (isOpen) => {
    if (restoringWindowSession) return;
    if (isOpen) {
      builderHidden.value = false;
      resetBuilderForm();
    }
  },
  { immediate: true }
);

watch(
  () => overlayState.builderTutorial,
  () => {
    if (restoringWindowSession) return;
    if (overlayState.builderOpen) {
      builderHidden.value = false;
      resetBuilderForm();
    }
  }
);

watch(
  () => overlayState.listVersion,
  () => {
    void loadTutorials();
  }
);

watch(
  () => form.steps.length,
  () => {
    setBuilderActiveIndex(builderActiveIndex.value);
  }
);

watch(
  () => route.fullPath,
  async () => {
    launcherTargetReady.value = false;
    await nextTick();
    refreshLauncherTarget();
  },
  { immediate: true }
);

watch(
  () => overlayState.activeTutorial?.id || "",
  () => {
    if (restoringWindowSession) return;
    followerHidden.value = false;
    syncFollowerActiveIndexToCurrent();
  }
);

watch(
  () => currentOpenIndex.value,
  () => {
    if (!activeTutorial.value || followerHidden.value) return;
    syncFollowerActiveIndexToCurrent();
  }
);

watch(
  () => [
    overlayState.builderOpen,
    builderHidden.value,
    builderActiveIndex.value,
    form.id,
    form.title,
    form.description,
    form.scope,
    JSON.stringify(form.steps.map((step, index) => ({
      id: step.id,
      url: step.url,
      short_description: step.short_description,
      long_description: step.long_description,
      order: index,
    }))),
    overlayState.activeTutorial?.id || "",
    followerHidden.value,
    followerActiveIndex.value,
  ],
  () => {
    persistTutorialWindowSession();
  },
  { flush: "sync" }
);

onMounted(async () => {
  restoringWindowSession = true;
  restoreActiveTutorial();
  restoreTutorialWindowSession();
  await nextTick();
  restoringWindowSession = false;
  persistTutorialWindowSession();
  refreshLauncherTarget();
  clampPanelsToViewport();
  void loadTutorials();
  window.addEventListener("resize", clampPanelsToViewport);
  window.addEventListener("pagehide", persistTutorialWindowSession);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", clampPanelsToViewport);
  window.removeEventListener("pagehide", persistTutorialWindowSession);
  window.removeEventListener("pointermove", onPanelDragMove);
});
</script>

<style scoped>
.admin-tutorial-launcher {
  position: relative;
  z-index: 1190;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--topbar-item-color, #0f172a);
}

.admin-tutorial-launcher__trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: inherit;
  width: 32px;
  height: 32px;
  padding: 0;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.admin-tutorial-launcher__trigger:hover,
.admin-tutorial-launcher.is-open .admin-tutorial-launcher__trigger {
  background: #eff6ff;
  color: #1d4ed8;
}

.admin-tutorial-launcher__panel {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  z-index: 1250;
  width: min(380px, calc(100vw - 24px));
  max-height: min(560px, calc(100vh - 92px));
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.22);
}

.admin-tutorial-launcher__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}

.admin-tutorial-launcher__header h2 {
  margin: 0;
  font-size: 15px;
}

.admin-tutorial-launcher__header span {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.admin-tutorial-launcher__actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
}

.admin-tutorial-launcher__empty {
  padding: 14px;
  color: #64748b;
  font-size: 13px;
}

.admin-tutorial-launcher__list {
  min-height: 0;
  overflow: auto;
  display: grid;
  gap: 8px;
  padding: 10px;
}

.admin-tutorial-launcher__item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 8px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-left: 4px solid #2563eb;
  border-radius: 8px;
  background: #ffffff;
}

.admin-tutorial-launcher__item.active {
  border-left-color: #16a34a;
  background: #f0fdf4;
}

.admin-tutorial-launcher__item-main {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.admin-tutorial-launcher__item-main h3 {
  margin: 0;
  font-size: 13px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.admin-tutorial-launcher__item-main p {
  margin: 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.admin-tutorial-launcher__item-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.admin-tutorial-panel {
  position: fixed;
  z-index: 1200;
  width: min(var(--admin-tutorial-panel-width), calc(100vw - 24px));
  max-height: calc(100vh - 24px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.22);
  color: #0f172a;
}

.admin-tutorial-panel--builder {
  --admin-tutorial-panel-width: 760px;
  max-height: 75vh;
}

.admin-tutorial-panel--follower {
  --admin-tutorial-panel-width: 760px;
  max-height: 75vh;
}

.admin-tutorial-sticky-stack {
  position: fixed;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  z-index: 1220;
  display: grid;
  gap: 8px;
  width: min(320px, calc(100vw - 36px));
}

.admin-tutorial-sticky-resume {
  display: grid;
  gap: 2px;
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #2563eb;
  border-radius: 8px;
  background: #1d4ed8;
  color: #ffffff;
  box-shadow: 0 14px 32px rgba(15, 23, 42, 0.24);
  cursor: pointer;
  text-align: left;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.25;
}

.admin-tutorial-sticky-resume:hover {
  background: #1e40af;
}

.admin-tutorial-sticky-resume span {
  min-width: 0;
  color: #dbeafe;
  font-size: 12px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-tutorial-panel__header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: move;
  user-select: none;
}

.admin-tutorial-panel__handle,
.admin-tutorial-icon-btn {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #475569;
  font-weight: 800;
  line-height: 1;
}

.admin-tutorial-panel__handle {
  display: none;
  background: #f8fafc;
  color: #64748b;
}

.admin-tutorial-icon-btn {
  cursor: pointer;
  font-size: 15px;
}

.admin-tutorial-icon-btn:hover {
  border-color: #94a3b8;
  color: #0f172a;
}

.admin-tutorial-panel__title {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.admin-tutorial-panel__title h2 {
  margin: 0;
  font-size: 15px;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.admin-tutorial-panel__title span {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.admin-tutorial-panel__header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.admin-tutorial-panel__header-actions .btn-sm {
  padding: 6px 10px;
}

.admin-tutorial-builder {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  overflow: hidden;
}

.admin-tutorial-builder__nav {
  min-height: 0;
  overflow: auto;
  display: grid;
  align-content: start;
  gap: 7px;
  padding: 12px;
  width: max-content;
  min-width: 58px;
  border-right: 1px solid #e2e8f0;
  background: #f8fafc;
}

.admin-tutorial-builder__nav-item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  min-width: 34px;
  padding: 8px 10px;
  cursor: pointer;
  text-align: center;
}

.admin-tutorial-builder__nav-item.active {
  border-color: #2563eb;
  background: #eff6ff;
  color: #1e40af;
}

.admin-tutorial-builder__nav-item:disabled {
  cursor: not-allowed;
}

.admin-tutorial-builder__nav-index {
  min-width: 0;
  height: auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 0;
  background: transparent;
  color: #334155;
  font-size: 11px;
  font-weight: 800;
}

.admin-tutorial-builder__nav-item.active .admin-tutorial-builder__nav-index {
  color: #1e40af;
}

.admin-tutorial-builder__add {
  justify-content: center;
}

.admin-tutorial-builder__main {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
}

.admin-tutorial-builder__page {
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
  display: grid;
  gap: 12px;
  align-content: start;
  padding: 14px;
}

.admin-tutorial-builder__page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.admin-tutorial-builder__page-head h3 {
  margin: 0;
  font-size: 15px;
}

.admin-tutorial-builder__page-head p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.4;
}

.admin-tutorial-builder__step-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.admin-tutorial-field {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.admin-tutorial-field span {
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}

.admin-tutorial-builder__actions {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
}

.admin-tutorial-builder__pager,
.admin-tutorial-builder__save-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.admin-tutorial-builder__pager span {
  color: #475569;
  font-size: 12px;
  font-weight: 800;
}

.status-message {
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
  border: 1px solid transparent;
}

.status-message.error {
  background: #fef2f2;
  color: #991b1b;
  border-color: #fecaca;
}

.admin-tutorial-follower {
  min-height: 0;
}

.admin-tutorial-follower__description {
  margin: 0;
  color: #475569;
  font-size: 13px;
  line-height: 1.45;
}

.admin-tutorial-follower__nav-item.is-done {
  border-color: #86efac;
  color: #166534;
  background: #ecfdf5;
}

.admin-tutorial-follower__nav-item.is-done .admin-tutorial-builder__nav-index {
  color: #166534;
}

.admin-tutorial-follower__nav-item.is-disabled {
  opacity: 0.58;
}

.admin-tutorial-follower__current-step {
  cursor: default;
}

.admin-tutorial-url-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 9px;
  border-radius: 6px;
  background: #eef2ff;
  color: #3730a3;
  font-size: 12px;
  font-weight: 800;
  overflow-wrap: anywhere;
}

.admin-tutorial-step {
  position: relative;
  display: grid;
  gap: 7px;
  padding: 10px 42px 10px 10px;
  border: 1px solid #dbeafe;
  border-left: 4px solid #2563eb;
  border-radius: 8px;
  background: #ffffff;
}

.admin-tutorial-step.is-current {
  background: #f8fafc;
  border-color: #93c5fd;
}

.admin-tutorial-step.is-done {
  border-color: #e2e8f0;
  border-left-color: #94a3b8;
  background: #f8fafc;
  color: #64748b;
}

.admin-tutorial-step.is-disabled {
  opacity: 0.62;
}

.admin-tutorial-step__main {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: start;
}

.admin-tutorial-step__main input {
  margin-top: 3px;
}

.admin-tutorial-step__number {
  position: absolute;
  top: 9px;
  right: 10px;
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #eff6ff;
  color: #1e40af;
  font-size: 11px;
  font-weight: 800;
}

.admin-tutorial-step.is-done .admin-tutorial-step__number {
  background: #e2e8f0;
  color: #475569;
}

.admin-tutorial-step__text {
  min-width: 0;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.admin-tutorial-step.is-done .admin-tutorial-step__text {
  text-decoration: line-through;
}

.admin-tutorial-step__long {
  margin: 0 0 0 30px;
  color: #475569;
  font-size: 13px;
  line-height: 1.45;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.admin-tutorial-complete {
  padding: 10px 12px;
  border: 1px solid #86efac;
  border-radius: 8px;
  background: #ecfdf5;
  color: #166534;
  font-size: 13px;
  font-weight: 800;
}

@media (max-width: 760px) {
  .admin-tutorial-panel {
    left: 12px !important;
    right: 12px;
    width: auto;
  }

  .admin-tutorial-builder {
    grid-template-columns: minmax(0, 1fr);
  }

  .admin-tutorial-builder__nav {
    max-height: 180px;
    border-right: 0;
    border-bottom: 1px solid #e2e8f0;
  }

  .admin-tutorial-builder__page-head,
  .admin-tutorial-builder__actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }

  .admin-tutorial-builder__step-actions {
    justify-content: flex-start;
  }

  .admin-tutorial-sticky-stack {
    left: 12px;
    right: 12px;
    bottom: 12px;
    transform: none;
    width: auto;
  }

  .admin-tutorial-step__long {
    margin-left: 0;
  }
}
</style>
