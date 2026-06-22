import { ref, reactive, computed, isRef, onBeforeUnmount } from "vue";
import {
  uploadImage,
  listAssets,
  deleteAsset,
  renameAsset,
  updateAssetTags,
  listAssetTags,
} from "../services/api.js";
import { selectResponsiveVariantUrl } from "../utils/responsiveImages.js";
import { getCurrentServerDateISO } from "../utils/revisionTime.js";

const MB_IN_BYTES = 1024 * 1024;
const ACCEPTED_FILE_EXTENSIONS = [".svg", ".pdf"];
const TAG_ALLOWED_CHAR_PATTERN = /[\p{L}\p{N}:_-]/u;
const DEFAULT_MEDIA_LIBRARY_PAGE_SIZE = 50;

function resolveAssetPreviewUrl(asset) {
  return selectResponsiveVariantUrl(asset?.responsive_variants) || String(asset?.url || "");
}

function bytesToMb(value) {
  const numeric = Number(value || 0);
  return Math.max(0.05, numeric / MB_IN_BYTES);
}

function createPreviewUrl(file) {
  if (typeof URL === "undefined" || typeof URL.createObjectURL !== "function") return "";
  if (!file || !(file.type || "").startsWith("image/")) return "";
  try {
    return URL.createObjectURL(file);
  } catch {
    return "";
  }
}

function todayIsoDay() {
  return getCurrentServerDateISO();
}

function normalizeTagInput(rawValue) {
  const normalized = String(rawValue || "")
    .normalize("NFC")
    .trim()
    .toLocaleLowerCase()
    .replace(/\s+/gu, "-");
  if (!normalized) return "";
  return [...normalized]
    .filter((char) => TAG_ALLOWED_CHAR_PATTERN.test(char))
    .join("");
}

export function useMediaLibraryManager(options = {}) {
  const pageSize = ref(Number(options.pageSize) > 0 ? Number(options.pageSize) : DEFAULT_MEDIA_LIBRARY_PAGE_SIZE);
  const sourceContext = computed(() => {
    const raw = options.sourceContext;
    if (isRef(raw)) return String(raw.value || "").trim();
    if (typeof raw === "function") return String(raw() || "").trim();
    return String(raw || "").trim();
  });

  const assets = ref([]);
  const loading = ref(false);
  const currentPage = ref(1);
  const total = ref(0);
  const hasMore = ref(false);
  const searchQuery = ref("");
  const activeTag = ref("");
  const allTags = ref([]);
  const selectedId = ref(null);
  const selectedAsset = ref(null);
  const isDragging = ref(false);
  const uploadQueue = ref([]);
  const uploading = ref([]);
  const uploadThroughputSamples = ref([]); // seconds per MB
  const deleteTarget = ref(null);
  const isRenaming = ref(false);
  const renameValue = ref("");
  const tagInput = ref("");

  let queueTickTimer = null;

  const totalPages = computed(() =>
    Math.max(1, Math.ceil(Math.max(0, total.value) / Math.max(1, pageSize.value)))
  );

  const averageUploadSecondsPerMb = computed(() => {
    const samples = uploadThroughputSamples.value || [];
    if (!samples.length) return null;
    const totalSecondsPerMb = samples.reduce((sum, value) => sum + Number(value || 0), 0);
    if (!Number.isFinite(totalSecondsPerMb) || totalSecondsPerMb <= 0) return null;
    return totalSecondsPerMb / samples.length;
  });

  const uploadedSessionItems = computed(() =>
    uploadQueue.value.filter((item) => item.status === "completed")
  );

  const queueFailedItems = computed(() =>
    uploadQueue.value.filter((item) => item.status === "failed")
  );

  const totalQueueEtaSeconds = computed(() => {
    const activeItems = uploadQueue.value.filter(
      (item) => item.status === "queued" || item.status === "uploading"
    );
    if (!activeItems.length) return 0;
    if (averageUploadSecondsPerMb.value == null) return null;
    let sum = 0;
    for (const item of activeItems) {
      const estimate = Number(item.estimated_remaining_seconds || 0);
      if (Number.isFinite(estimate) && estimate > 0) {
        sum += estimate;
      }
    }
    return Math.max(0, Math.round(sum));
  });

  const uploadedSessionCount = computed(() => uploadedSessionItems.value.length);

  function isVideoAsset(asset) {
    if (!asset) return false;
    const contentType = String(asset.content_type || "");
    if (contentType.startsWith("video/")) return true;
    const url = String(asset.url || "").toLowerCase();
    return [".mp4", ".webm", ".mov", ".ogg", ".m4v"].some((ext) => url.includes(ext));
  }

  function isPdfAsset(asset) {
    if (!asset) return false;
    const contentType = String(asset.content_type || "").toLowerCase();
    if (contentType === "application/pdf") return true;
    const filename = String(asset.filename || "").toLowerCase();
    if (filename.endsWith(".pdf")) return true;
    const url = String(asset.url || "").toLowerCase();
    return url.includes(".pdf");
  }

  async function fetchAssets() {
    loading.value = true;
    try {
      const response = await listAssets({
        page: currentPage.value,
        pageSize: pageSize.value,
        search: searchQuery.value,
        tag: activeTag.value,
      });
      assets.value = Array.isArray(response.items) ? response.items : [];
      total.value = Number(response.total || 0);
      hasMore.value = Boolean(response.has_more);
    } finally {
      loading.value = false;
    }
  }

  async function fetchTags() {
    const response = await listAssetTags();
    allTags.value = Array.isArray(response.tags) ? response.tags : [];
  }

  function setSearch(value) {
    searchQuery.value = String(value || "");
    currentPage.value = 1;
  }

  function filterByTag(tag) {
    activeTag.value = activeTag.value === tag ? "" : String(tag || "");
    currentPage.value = 1;
  }

  function clearTagFilter() {
    activeTag.value = "";
    currentPage.value = 1;
  }

  function goToPage(page) {
    const next = Number(page);
    if (!Number.isFinite(next)) return;
    currentPage.value = Math.max(1, next);
  }

  function clearSelection() {
    selectedId.value = null;
    selectedAsset.value = null;
    isRenaming.value = false;
    renameValue.value = "";
    tagInput.value = "";
  }

  function selectAsset(asset) {
    if (!asset) return;
    selectedId.value = asset.id || null;
    selectedAsset.value = asset;
    isRenaming.value = false;
  }

  function selectAssetByUrl(url) {
    const wanted = String(url || "").trim();
    if (!wanted) return;
    const found = assets.value.find((asset) => String(asset.url || "") === wanted);
    if (found) selectAsset(found);
  }

  function startRename() {
    renameValue.value = selectedAsset.value?.filename || "";
    isRenaming.value = true;
  }

  function cancelRename() {
    isRenaming.value = false;
    renameValue.value = "";
  }

  async function executeRename() {
    const target = selectedAsset.value;
    const newName = String(renameValue.value || "").trim();
    if (!target || !newName || newName === target.filename) {
      cancelRename();
      return;
    }
    await renameAsset(target.id, newName);
    target.filename = newName;
    const inList = assets.value.find((asset) => asset.id === target.id);
    if (inList) inList.filename = newName;
    isRenaming.value = false;
  }

  async function addTag() {
    const target = selectedAsset.value;
    const tag = normalizeTagInput(tagInput.value);
    if (!target || !tag) return;
    const currentTags = Array.isArray(target.tags) ? target.tags : [];
    if (currentTags.includes(tag)) {
      tagInput.value = "";
      return;
    }
    const result = await updateAssetTags(target.id, [...currentTags, tag]);
    target.tags = result.tags || [];
    const inList = assets.value.find((asset) => asset.id === target.id);
    if (inList) inList.tags = result.tags || [];
    tagInput.value = "";
    await fetchTags();
  }

  async function removeTag(tag) {
    const target = selectedAsset.value;
    if (!target) return;
    const currentTags = Array.isArray(target.tags) ? target.tags : [];
    const result = await updateAssetTags(
      target.id,
      currentTags.filter((entry) => entry !== tag)
    );
    target.tags = result.tags || [];
    const inList = assets.value.find((asset) => asset.id === target.id);
    if (inList) inList.tags = result.tags || [];
    await fetchTags();
  }

  function confirmDelete(asset) {
    deleteTarget.value = asset || null;
  }

  async function executeDelete() {
    if (!deleteTarget.value) return false;
    const targetId = deleteTarget.value.id;
    await deleteAsset(targetId);
    deleteTarget.value = null;
    if (selectedId.value === targetId) clearSelection();
    await fetchAssets();
    return true;
  }

  function setDragging(value) {
    isDragging.value = Boolean(value);
  }

  function extractAcceptedFiles(fileListLike) {
    return Array.from(fileListLike || []).filter((file) => {
      const name = String(file?.name || "").toLowerCase();
      const type = String(file?.type || "").toLowerCase();
      return (
        type.startsWith("image/")
        || type.startsWith("video/")
        || type === "application/pdf"
        || ACCEPTED_FILE_EXTENSIONS.some((ext) => name.endsWith(ext))
      );
    });
  }

  function revokeQueuePreview(item) {
    const url = String(item?.preview_url || "").trim();
    if (!url || typeof URL === "undefined" || typeof URL.revokeObjectURL !== "function") return;
    try {
      URL.revokeObjectURL(url);
    } catch {
      // ignore URL revocation errors
    }
  }

  function clearUploadQueue() {
    for (const item of uploadQueue.value) {
      revokeQueuePreview(item);
    }
    uploadQueue.value = [];
    uploading.value = [];
    uploadThroughputSamples.value = [];
    if (queueTickTimer) {
      clearInterval(queueTickTimer);
      queueTickTimer = null;
    }
  }

  function createQueueItem(file, sourceContextValue) {
    const now = Date.now();
    return {
      id: `${now}-${Math.random().toString(36).slice(2)}`,
      name: String(file?.name || "untitled"),
      size: Number(file?.size || 0),
      type: String(file?.type || ""),
      progress: 0,
      status: "queued", // queued | uploading | completed | failed
      preview_url: createPreviewUrl(file),
      started_at: null,
      finished_at: null,
      elapsed_ms: 0,
      elapsed_seconds: 0,
      estimated_remaining_seconds: null,
      error: "",
      source_context: String(sourceContextValue || ""),
      metadata: null,
      tags: [],
      asset_id: "",
      asset_url: "",
      asset_thumb_url: "",
      asset_filename: String(file?.name || ""),
      result: null,
      meta_edit: {
        filename: String(file?.name || "untitled"),
        manual_author: "",
        override_session_authorship: false,
        tagging_mode: "auto",
        manual_artist: "",
        manual_stage: "",
        manual_date: todayIsoDay(),
        manual_additional_info: "",
        caption_de: "",
        caption_en: "",
        program_artist_query: "",
        program_selected_gig_id: "",
      },
    };
  }

  function syncUploadingList() {
    uploading.value = uploadQueue.value.filter(
      (entry) => entry.status === "queued" || entry.status === "uploading"
    );
  }

  function ensureQueueTickTimer() {
    const hasActive = uploadQueue.value.some(
      (entry) => entry.status === "queued" || entry.status === "uploading"
    );
    if (hasActive && !queueTickTimer) {
      queueTickTimer = setInterval(() => {
        recomputeQueueTimingAndEta();
      }, 1000);
      return;
    }
    if (!hasActive && queueTickTimer) {
      clearInterval(queueTickTimer);
      queueTickTimer = null;
    }
  }

  function recomputeQueueTimingAndEta() {
    const now = Date.now();
    const average = averageUploadSecondsPerMb.value;

    for (const item of uploadQueue.value) {
      if (item.status === "uploading") {
        item.elapsed_ms = Math.max(0, now - Number(item.started_at || now));
        item.elapsed_seconds = Math.max(0, Math.round(item.elapsed_ms / 1000));
      } else if (item.status === "completed" || item.status === "failed") {
        const start = Number(item.started_at || 0);
        const finish = Number(item.finished_at || 0);
        if (start > 0 && finish >= start) {
          item.elapsed_ms = Math.max(0, finish - start);
          item.elapsed_seconds = Math.max(0, Math.round(item.elapsed_ms / 1000));
        }
      }

      if (item.status === "completed" || item.status === "failed") {
        item.estimated_remaining_seconds = 0;
        continue;
      }

      if (average == null || !Number.isFinite(average) || average <= 0) {
        item.estimated_remaining_seconds = null;
        continue;
      }

      const fullEstimateSeconds = average * bytesToMb(item.size);
      if (item.status === "queued") {
        item.estimated_remaining_seconds = Math.max(1, Math.round(fullEstimateSeconds));
        continue;
      }

      const progressRatio = Math.min(1, Math.max(0, Number(item.progress || 0) / 100));
      const progressRemaining = fullEstimateSeconds * (1 - progressRatio);
      const elapsedRemaining = Math.max(0, fullEstimateSeconds - Number(item.elapsed_seconds || 0));
      const remaining = Math.max(progressRemaining, elapsedRemaining);
      item.estimated_remaining_seconds = Math.max(0, Math.round(remaining));
    }

    syncUploadingList();
    ensureQueueTickTimer();
  }

  function addThroughputSample(sizeBytes, elapsedMs) {
    const safeElapsedMs = Number(elapsedMs || 0);
    if (!Number.isFinite(safeElapsedMs) || safeElapsedMs <= 0) return;
    const sample = (safeElapsedMs / 1000) / bytesToMb(sizeBytes);
    if (!Number.isFinite(sample) || sample <= 0) return;
    uploadThroughputSamples.value = [...uploadThroughputSamples.value.slice(-11), sample];
  }

  function resolveQueueAssetId(result) {
    return String(
      result?.asset_id
      || result?.id
      || result?.assetId
      || ""
    );
  }

  function enrichQueueWithLibraryAssets() {
    if (!Array.isArray(assets.value) || assets.value.length === 0) return;
    for (const item of uploadQueue.value) {
      if (!item || item.status !== "completed") continue;
      if (String(item.asset_id || "").trim()) continue;

      const byUrl = assets.value.find((asset) => {
        const itemUrl = String(item.asset_url || "").trim();
        if (itemUrl && String(asset?.url || "").trim() === itemUrl) return true;
        const itemThumb = String(item.asset_thumb_url || "").trim();
        if (itemThumb && resolveAssetPreviewUrl(asset) === itemThumb) return true;
        return false;
      });
      const byName = assets.value.find((asset) =>
        String(asset?.filename || "").trim() === String(item.asset_filename || "").trim()
      );
      const match = byUrl || byName || null;
      if (!match) continue;

      item.asset_id = String(match.id || "");
      if (!Array.isArray(item.tags) || item.tags.length === 0) {
        item.tags = Array.isArray(match.tags) ? match.tags : [];
      }
      if (!String(item.asset_url || "").trim()) item.asset_url = String(match.url || "");
      if (!String(item.asset_thumb_url || "").trim()) item.asset_thumb_url = resolveAssetPreviewUrl(match);
      if (!String(item.asset_filename || "").trim()) item.asset_filename = String(match.filename || item.name || "");
    }
  }

  async function uploadFiles(files, options = {}) {
    const safeFiles = extractAcceptedFiles(files);
    if (!safeFiles.length) return [];

    const results = [];
    const failures = [];
    const bypassAutocropTransparentPadding = Boolean(options?.bypassAutocropTransparentPadding);
    const deferRequiredMetadataValidation = Boolean(options?.deferRequiredMetadataValidation);
    const context = String(sourceContext.value || "").trim();

    const queueItems = safeFiles.map((file) => reactive(createQueueItem(file, context)));
    uploadQueue.value = [...uploadQueue.value, ...queueItems];
    recomputeQueueTimingAndEta();

    for (let index = 0; index < safeFiles.length; index += 1) {
      const file = safeFiles[index];
      const item = queueItems[index];
      if (!item) continue;

      item.status = "uploading";
      item.started_at = Date.now();
      item.error = "";
      item.progress = Math.max(5, Number(item.progress || 0));
      recomputeQueueTimingAndEta();

      const progressInterval = setInterval(() => {
        if (item.status !== "uploading") return;
        if (item.progress < 90) {
          item.progress = Math.min(90, item.progress + 7);
          recomputeQueueTimingAndEta();
        }
      }, 240);

      try {
        const result = await uploadImage(file, {
          sourceContext: context || undefined,
          bypassAutocropTransparentPadding,
          deferRequiredMetadataValidation,
        });

        const finishedAt = Date.now();
        const elapsedMs = Math.max(0, finishedAt - Number(item.started_at || finishedAt));
        addThroughputSample(file.size, elapsedMs);

        item.status = "completed";
        item.progress = 100;
        item.finished_at = finishedAt;
        item.elapsed_ms = elapsedMs;
        item.elapsed_seconds = Math.max(0, Math.round(elapsedMs / 1000));
        item.metadata = result?.metadata && typeof result.metadata === "object" ? result.metadata : null;
        item.tags = Array.isArray(result?.tags) ? result.tags : [];
        item.asset_id = resolveQueueAssetId(result);
        item.asset_url = String(result?.url || "");
        item.asset_thumb_url = selectResponsiveVariantUrl(result?.responsive_variants) || String(result?.url || "");
        item.asset_filename = String(file?.name || result?.key || item.name || "");
        item.result = result || null;
        item.estimated_remaining_seconds = 0;

        results.push({
          filename: file.name,
          queue_id: item.id,
          ...(result || {}),
        });
      } catch (error) {
        const finishedAt = Date.now();
        const elapsedMs = Math.max(0, finishedAt - Number(item.started_at || finishedAt));

        item.status = "failed";
        item.progress = 100;
        item.finished_at = finishedAt;
        item.elapsed_ms = elapsedMs;
        item.elapsed_seconds = Math.max(0, Math.round(elapsedMs / 1000));
        item.error = String(error?.message || error || "Upload failed");
        item.estimated_remaining_seconds = 0;

        failures.push(error);
      } finally {
        clearInterval(progressInterval);
        recomputeQueueTimingAndEta();
      }
    }

    await Promise.all([fetchAssets(), fetchTags()]);
    enrichQueueWithLibraryAssets();

    if (failures.length > 0 && results.length === 0) {
      throw failures[0];
    }

    return results;
  }

  onBeforeUnmount(() => {
    if (queueTickTimer) {
      clearInterval(queueTickTimer);
      queueTickTimer = null;
    }
    for (const item of uploadQueue.value) {
      revokeQueuePreview(item);
    }
  });

  return {
    pageSize,
    assets,
    loading,
    currentPage,
    total,
    hasMore,
    searchQuery,
    activeTag,
    allTags,
    selectedId,
    selectedAsset,
    isDragging,
    uploading,
    uploadQueue,
    uploadedSessionItems,
    uploadedSessionCount,
    queueFailedItems,
    uploadThroughputSamples,
    averageUploadSecondsPerMb,
    totalQueueEtaSeconds,
    deleteTarget,
    isRenaming,
    renameValue,
    tagInput,
    totalPages,
    isVideoAsset,
    isPdfAsset,
    fetchAssets,
    fetchTags,
    setSearch,
    filterByTag,
    clearTagFilter,
    goToPage,
    clearSelection,
    selectAsset,
    selectAssetByUrl,
    startRename,
    cancelRename,
    executeRename,
    addTag,
    removeTag,
    confirmDelete,
    executeDelete,
    setDragging,
    extractAcceptedFiles,
    uploadFiles,
    clearUploadQueue,
    recomputeQueueTimingAndEta,
  };
}
