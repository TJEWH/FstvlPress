import { reactive } from "vue";
import { getInternalRole, getUser } from "../services/auth.js";

export const TUTORIAL_SCOPE_OPTIONS = Object.freeze([
  { value: "content", label: "Content" },
  { value: "design", label: "Design" },
  { value: "admin_design", label: "Admin Design" },
  { value: "admin_general", label: "Admin General" },
]);

const ROLE_RANK = Object.freeze({
  no_access: 0,
  content: 1,
  design: 2,
  admin_design: 3,
  admin_general: 4,
});

const ACTIVE_TUTORIAL_STORAGE_PREFIX = "fstvlpress-admin-tutorial:v1:";

const tutorialOverlayState = reactive({
  builderOpen: false,
  builderTutorial: null,
  activeTutorial: null,
  doneStepIds: [],
  listVersion: 0,
});

function cloneJson(value) {
  if (!value) return null;
  return JSON.parse(JSON.stringify(value));
}

function normalizeRole(value) {
  const role = String(value || "").trim();
  return Object.prototype.hasOwnProperty.call(ROLE_RANK, role) ? role : "no_access";
}

export function tutorialRoleRank(role) {
  return ROLE_RANK[normalizeRole(role)] ?? 0;
}

export function tutorialScopeOptionsForCurrentUser() {
  const role = normalizeRole(getInternalRole?.());
  const rank = tutorialRoleRank(role);
  return TUTORIAL_SCOPE_OPTIONS.filter((option) => tutorialRoleRank(option.value) <= rank);
}

function normalizeTutorialStep(step, index = 0) {
  return {
    id: String(step?.id || `step-${index + 1}`),
    url: String(step?.url || "/admin").trim() || "/admin",
    short_description: String(step?.short_description || "").trim(),
    long_description: String(step?.long_description || "").trim(),
    order: Number.isFinite(Number(step?.order)) ? Number(step.order) : index,
  };
}

function normalizeTutorial(tutorial) {
  if (!tutorial || typeof tutorial !== "object") return null;
  const steps = Array.isArray(tutorial.steps)
    ? tutorial.steps.map((step, index) => normalizeTutorialStep(step, index))
    : [];
  return {
    id: String(tutorial.id || ""),
    title: String(tutorial.title || "").trim(),
    description: String(tutorial.description || "").trim(),
    scope: normalizeRole(tutorial.scope) === "no_access" ? "content" : normalizeRole(tutorial.scope),
    owner: String(tutorial.owner || "unknown").trim() || "unknown",
    owner_id: String(tutorial.owner_id || "").trim(),
    created_at: tutorial.created_at || null,
    updated_at: tutorial.updated_at || null,
    can_edit: Boolean(tutorial.can_edit),
    steps: steps.sort((left, right) => (left.order ?? 0) - (right.order ?? 0)),
  };
}

function currentUserStorageKey() {
  if (typeof window === "undefined" || !window.sessionStorage) return "";
  const user = getUser?.();
  const identity = String(user?.sub || user?.username || user?.name || getInternalRole?.() || "anonymous").trim() || "anonymous";
  return `${ACTIVE_TUTORIAL_STORAGE_PREFIX}${identity}`;
}

function readStoredActiveTutorial() {
  const key = currentUserStorageKey();
  if (!key) return null;
  try {
    const raw = window.sessionStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const tutorial = normalizeTutorial(parsed?.tutorial);
    if (!tutorial?.id || tutorial.steps.length === 0) return null;
    const stepIds = new Set(tutorial.steps.map((step) => step.id));
    const doneStepIds = Array.isArray(parsed?.doneStepIds)
      ? parsed.doneStepIds.map((id) => String(id || "")).filter((id) => stepIds.has(id))
      : [];
    return { tutorial, doneStepIds };
  } catch {
    return null;
  }
}

function writeStoredActiveTutorial() {
  const key = currentUserStorageKey();
  if (!key) return;
  try {
    if (!tutorialOverlayState.activeTutorial) {
      window.sessionStorage.removeItem(key);
      return;
    }
    window.sessionStorage.setItem(
      key,
      JSON.stringify({
        tutorial: tutorialOverlayState.activeTutorial,
        doneStepIds: tutorialOverlayState.doneStepIds,
      })
    );
  } catch {
    // Ignore quota/privacy errors. Tutorial progress is convenience-only.
  }
}

export function restoreActiveTutorial() {
  if (tutorialOverlayState.activeTutorial) return;
  const stored = readStoredActiveTutorial();
  if (!stored) return;
  tutorialOverlayState.activeTutorial = stored.tutorial;
  tutorialOverlayState.doneStepIds = stored.doneStepIds;
}

export function openTutorialBuilder(tutorial = null) {
  tutorialOverlayState.builderTutorial = normalizeTutorial(cloneJson(tutorial));
  tutorialOverlayState.builderOpen = true;
}

export function closeTutorialBuilder() {
  tutorialOverlayState.builderOpen = false;
  tutorialOverlayState.builderTutorial = null;
}

export function startTutorial(tutorial, { resume = false } = {}) {
  const normalized = normalizeTutorial(cloneJson(tutorial));
  if (!normalized?.id || normalized.steps.length === 0) return;

  const stored = readStoredActiveTutorial();
  const stepIds = new Set(normalized.steps.map((step) => step.id));
  const doneStepIds = resume && stored?.tutorial?.id === normalized.id
    ? stored.doneStepIds.filter((id) => stepIds.has(id))
    : [];

  tutorialOverlayState.activeTutorial = normalized;
  tutorialOverlayState.doneStepIds = doneStepIds;
  writeStoredActiveTutorial();
}

export function updateTutorialProgress(doneStepIds) {
  const stepIds = new Set((tutorialOverlayState.activeTutorial?.steps || []).map((step) => step.id));
  tutorialOverlayState.doneStepIds = Array.isArray(doneStepIds)
    ? doneStepIds.map((id) => String(id || "")).filter((id) => stepIds.has(id))
    : [];
  writeStoredActiveTutorial();
}

export function stopTutorial() {
  tutorialOverlayState.activeTutorial = null;
  tutorialOverlayState.doneStepIds = [];
  writeStoredActiveTutorial();
}

export function notifyTutorialsChanged() {
  tutorialOverlayState.listVersion += 1;
}

export function useAdminTutorialOverlay() {
  return {
    state: tutorialOverlayState,
    closeTutorialBuilder,
    notifyTutorialsChanged,
    openTutorialBuilder,
    restoreActiveTutorial,
    startTutorial,
    stopTutorial,
    updateTutorialProgress,
  };
}
