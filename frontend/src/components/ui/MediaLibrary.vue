<template>
  <Teleport to="body">
    <div
      v-if="isOpen"
      class="media-library-overlay"
      :class="{ 'media-library-overlay--dragging': isDragging }"
      @click.self="close"
    >
      <div class="media-library" @dragover.prevent="onOverlayDragOver" @drop.prevent="onOverlayDrop">
        <header class="header">
          <h2 class="title">Media Library</h2>
          <div class="header-actions">
            <button
              v-if="allowClearSelection"
              class="clear-btn"
              type="button"
              :disabled="!canClearSelection"
              @click="clearAssignedImage"
            >
              Clear
            </button>
            <button class="btn-secondary admin-media-btn" type="button" @click="openAdminMedia">
              Open Admin Media
            </button>
            <button class="close-btn" @click="close" aria-label="Close">
              <font-awesome-icon :icon="faXmark" class="close-icon" />
            </button>
          </div>
        </header>

        <div class="filter-row">
          <input
            :value="searchQuery"
            type="text"
            placeholder="Search media..."
            class="search-input"
            @input="onSearchInput"
          />
          <div v-if="allTags.length > 0" class="tag-filters">
            <button
              v-for="tag in allTags"
              :key="tag"
              type="button"
              class="tag-filter-btn"
              :class="{ 'tag-filter-btn--active': activeTag === tag }"
              @click="filterByTagAndFetch(tag)"
            >
              {{ tag }}
            </button>
            <button
              v-if="activeTag"
              type="button"
              class="tag-filter-clear"
              @click="clearTagFilterAndFetch"
            >
              <font-awesome-icon :icon="faXmark" class="tag-filter-clear-icon" />
            </button>
          </div>
        </div>

        <div class="image-grid" ref="gridRef">
          <template v-for="(row, rowIndex) in assetRows" :key="assetRowKey(row, rowIndex)">
            <div
              class="image-row"
              :style="{ '--media-picker-columns': mediaGridColumns }"
            >
              <div
                v-for="asset in row"
                :key="asset.id"
                class="image-card"
                :class="{
                  'image-card--selected': selectedId === asset.id,
                  'image-card--video': isVideoAsset(asset),
                  'image-card--pdf': isPdfAsset(asset),
                }"
                @click="onAssetClick(asset)"
              >
                <template v-if="isVideoAsset(asset)">
                  <video
                    :src="asset.url"
                    class="image-thumb"
                    muted
                    preload="metadata"
                  ></video>
                  <div class="video-badge">Play</div>
                </template>
                <div v-else-if="isPdfAsset(asset)" class="file-thumb">
                  <span class="file-thumb__badge">PDF</span>
                  <span class="file-thumb__name">{{ asset.filename }}</span>
                </div>
                <div v-else class="image-thumb-surface">
                  <img
                    :src="assetPreviewUrl(asset)"
                    :alt="asset.filename"
                    class="image-thumb image-thumb--image"
                    loading="lazy"
                  />
                </div>
              </div>
            </div>

            <div
              v-if="selectedAsset && selectedAssetRowIndex === rowIndex"
              class="selection-inline-editor"
            >
              <div class="selection-inline-editor__name">
                <div v-if="!isRenaming" class="selection-filename" :title="selectedAsset.filename">
                  {{ selectedAsset.filename }}
                </div>
                <input
                  v-else
                  ref="renameInput"
                  v-model="renameValue"
                  class="rename-input"
                  @keydown.enter="executeRenameSafe"
                  @keydown.escape="cancelRename"
                />
              </div>

              <div class="selection-actions">
                <template v-if="!isRenaming">
                  <button type="button" class="sel-action-btn" @click="startRenameWithFocus">
                    <font-awesome-icon :icon="faPenToSquare" class="sel-action-icon" />
                    Edit Name
                  </button>
                  <button type="button" class="sel-action-btn sel-action-btn--danger" @click="confirmDelete(selectedAsset)">
                    <font-awesome-icon :icon="faTrashCan" class="sel-action-icon" />
                    Delete
                  </button>
                  <button type="button" class="sel-action-btn sel-action-btn--muted" @click="clearSelection">
                    <font-awesome-icon :icon="faXmark" class="sel-action-icon" />
                    Close
                  </button>
                </template>
                <template v-else>
                  <button type="button" class="sel-action-btn sel-action-btn--confirm" @click="executeRenameSafe">
                    <font-awesome-icon :icon="faCheck" class="sel-action-icon" />
                    Save
                  </button>
                  <button type="button" class="sel-action-btn" @click="cancelRename">
                    Cancel
                  </button>
                </template>
              </div>

              <div class="selection-tags">
                <span
                  v-for="tag in (selectedAsset.tags || [])"
                  :key="tag"
                  class="tag-chip"
                >
                  {{ tag }}
                  <button type="button" class="tag-chip-remove" @click="removeTagSafe(tag)">
                    <font-awesome-icon :icon="faXmark" class="tag-chip-remove-icon" />
                  </button>
                </span>
                <input
                  v-model="tagInput"
                  type="text"
                  class="tag-add-input"
                  placeholder="+ tag"
                  @keydown.enter.prevent="addTagSafe"
                />
              </div>
            </div>
          </template>

          <div v-if="assets.length === 0 && !loading" class="empty-state">
            <p>No media found. Upload some!</p>
          </div>

          <div v-if="loading" class="loading-state">
            <div class="spinner"></div>
          </div>
        </div>

        <div
          v-if="isDragging"
          class="drag-upload-overlay"
          @dragenter.prevent.stop="onLocalDragEnter"
          @dragover.prevent.stop="onLocalDragOver"
          @dragleave.prevent.stop="onLocalDragLeave"
          @drop.prevent.stop="onLocalDrop"
        >
          <div class="upload-zone upload-zone--active">
            <font-awesome-icon :icon="faUpload" class="upload-icon" />
            <p class="upload-text">Drop files to upload</p>
          </div>
        </div>

        <div v-if="uploading.length > 0" class="upload-progress">
          <div v-for="item in uploading" :key="item.id" class="upload-item">
            <span class="upload-name">{{ item.name }}</span>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: item.progress + '%' }"></div>
            </div>
          </div>
        </div>

        <footer class="footer">
          <div class="footer-left">
            <button class="btn-secondary" @click="close">Cancel</button>
            <button
              class="btn-primary"
              :disabled="!selectedId"
              @click="confirmSelection"
            >
              Select Media
            </button>
          </div>
          <div v-if="totalPages > 1" class="pagination">
            <button
              class="page-btn"
              :disabled="currentPage === 1"
              @click="goToPageAndFetch(currentPage - 1)"
            >
              <font-awesome-icon :icon="faChevronLeft" class="page-btn-icon" />
            </button>
            <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
            <button
              class="page-btn"
              :disabled="!hasMore"
              @click="goToPageAndFetch(currentPage + 1)"
            >
              <font-awesome-icon :icon="faChevronRight" class="page-btn-icon" />
            </button>
          </div>
        </footer>

        <div v-if="deleteTarget" class="delete-modal" @click.self="confirmDelete(null)">
          <div class="delete-dialog">
            <h3>Delete Image?</h3>
            <p>Are you sure you want to delete "{{ deleteTarget.filename }}"? This cannot be undone.</p>
            <div class="delete-actions">
              <button class="btn-secondary" @click="confirmDelete(null)">Cancel</button>
              <button class="btn-danger" @click="executeDeleteSafe">Delete</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount, nextTick } from "vue";
import {
  faCheck,
  faChevronLeft,
  faChevronRight,
  faPenToSquare,
  faTrashCan,
  faUpload,
  faXmark,
} from "@fortawesome/free-solid-svg-icons";
import { useRoute, useRouter } from "vue-router";
import { useMediaLibraryManager } from "../../composables/useMediaLibraryManager.js";
import { selectResponsiveVariantUrl } from "../../utils/responsiveImages.js";

const props = defineProps({
  isOpen: { type: Boolean, default: false },
  currentUrl: { type: String, default: "" },
  sourceContext: { type: String, default: "" },
  allowClearSelection: { type: Boolean, default: false },
});

const emit = defineEmits(["close", "select"]);

const router = useRouter();
const route = useRoute();
const sourceContextRef = computed(() => String(props.sourceContext || "").trim());
const MEDIA_PICKER_PAGE_SIZE = 21;

const {
  assets,
  loading,
  currentPage,
  hasMore,
  searchQuery,
  activeTag,
  allTags,
  selectedId,
  selectedAsset,
  isDragging,
  uploading,
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
} = useMediaLibraryManager({ pageSize: MEDIA_PICKER_PAGE_SIZE, sourceContext: sourceContextRef });

const renameInput = ref(null);
const gridRef = ref(null);
const canClearSelection = computed(() => String(props.currentUrl || "").trim().length > 0);
const mediaGridColumns = ref(7);
const assetRows = computed(() => {
  const columns = Math.max(1, Number(mediaGridColumns.value || 1));
  const rows = [];
  const list = assets.value || [];
  for (let index = 0; index < list.length; index += columns) {
    rows.push(list.slice(index, index + columns));
  }
  return rows;
});
const selectedAssetRowIndex = computed(() => {
  const selected = selectedAsset.value;
  if (!selected) return -1;
  const list = assets.value || [];
  const selectedIndex = list.findIndex((asset) => asset?.id === selected?.id);
  if (selectedIndex < 0) return -1;
  const columns = Math.max(1, Number(mediaGridColumns.value || 1));
  return Math.floor(selectedIndex / columns);
});

let searchTimeout = null;
let dragDepth = 0;
let mediaGridResizeObserver = null;

function emitSelection(asset) {
  if (!asset) return;
  const normalizedAuthors = Array.isArray(asset?.authors)
    ? asset.authors.map((entry) => String(entry || "").trim()).filter(Boolean)
    : [];
  emit("select", {
    url: String(asset.url || ""),
    id: asset.id || null,
    filename: asset.filename || "",
    alt: {
      de: String(asset?.alt?.de || ""),
      en: String(asset?.alt?.en || ""),
    },
    caption: {
      de: String(asset?.caption?.de || ""),
      en: String(asset?.caption?.en || ""),
    },
    author: normalizedAuthors[0] || "",
    authors: normalizedAuthors,
    responsive_variants: Array.isArray(asset.responsive_variants) ? asset.responsive_variants : [],
  });
}

function assetPreviewUrl(asset) {
  return selectResponsiveVariantUrl(asset?.responsive_variants) || String(asset?.url || "");
}

function onAssetClick(asset) {
  if (selectedId.value === asset?.id) {
    clearSelection();
    return;
  }
  selectAsset(asset);
}

function confirmSelection() {
  if (!selectedAsset.value) return;
  emitSelection(selectedAsset.value);
  close();
}

function openAdminMedia() {
  const returnTo = route?.fullPath || "/";
  close();
  router.push({ path: "/admin/media/library", query: { returnTo } }).catch(() => {});
}

function assetRowKey(row, rowIndex) {
  return `${rowIndex}:${row.map((asset) => asset?.id || asset?.url || asset?.filename || "asset").join("|")}`;
}

function onLocalDragEnter(event) {
  if (!hasFileDrag(event)) return;
  setDragging(true);
}

function onLocalDragOver(event) {
  if (!hasFileDrag(event)) return;
  setDragging(true);
}

function onLocalDragLeave(event) {
  if (!hasFileDrag(event)) return;
  if (!dragDepth) setDragging(false);
}

async function onLocalDrop(event) {
  setDragging(false);
  const files = extractAcceptedFiles(event?.dataTransfer?.files || []);
  if (!files.length) return;
  try {
    await uploadFiles(files);
  } catch (error) {
    console.error("Upload failed:", error);
    alert(`Upload failed: ${error.message || error}`);
  }
}

function hasFileDrag(event) {
  const items = event?.dataTransfer?.items;
  if (!items) return false;
  return Array.from(items).some((item) => item.kind === "file");
}

function isUploadZoneDropTarget(event) {
  const path = typeof event?.composedPath === "function" ? event.composedPath() : [];
  const nodes = path.length ? path : [event?.target];
  return nodes.some(
    (node) => node instanceof Element && node.classList.contains("upload-zone")
  );
}

function onGlobalDragEnter(event) {
  if (!props.isOpen || !hasFileDrag(event)) return;
  event.preventDefault();
  dragDepth += 1;
  setDragging(true);
}

function onGlobalDragOver(event) {
  if (!props.isOpen || !hasFileDrag(event)) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "copy";
  setDragging(true);
}

function onGlobalDragLeave(event) {
  if (!props.isOpen || !hasFileDrag(event)) return;
  event.preventDefault();
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) setDragging(false);
}

async function onGlobalDrop(event) {
  if (!props.isOpen) return;
  if (isUploadZoneDropTarget(event)) return;
  event.preventDefault();
  dragDepth = 0;
  setDragging(false);
  const files = extractAcceptedFiles(event?.dataTransfer?.files || []);
  if (!files.length) return;
  try {
    await uploadFiles(files);
  } catch (error) {
    console.error("Upload failed:", error);
    alert(`Upload failed: ${error.message || error}`);
  }
}

function onOverlayDragOver(event) {
  if (!props.isOpen || !hasFileDrag(event)) return;
  event.preventDefault();
  setDragging(true);
}

function onOverlayDrop(event) {
  if (!props.isOpen) return;
  event.preventDefault();
  event.stopPropagation();
}

function bindGlobalDragEvents() {
  window.addEventListener("dragenter", onGlobalDragEnter, true);
  window.addEventListener("dragover", onGlobalDragOver, true);
  window.addEventListener("dragleave", onGlobalDragLeave, true);
  window.addEventListener("drop", onGlobalDrop, true);
}

function unbindGlobalDragEvents() {
  window.removeEventListener("dragenter", onGlobalDragEnter, true);
  window.removeEventListener("dragover", onGlobalDragOver, true);
  window.removeEventListener("dragleave", onGlobalDragLeave, true);
  window.removeEventListener("drop", onGlobalDrop, true);
  dragDepth = 0;
  setDragging(false);
}

function onSearchInput(event) {
  setSearch(event?.target?.value || "");
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(async () => {
    try {
      await fetchAssets();
      await nextTick();
      updateMediaGridColumns();
    } catch (error) {
      console.error("Failed to search assets:", error);
    }
  }, 250);
}

async function filterByTagAndFetch(tag) {
  filterByTag(tag);
  await fetchAssets();
  await nextTick();
  updateMediaGridColumns();
}

async function clearTagFilterAndFetch() {
  clearTagFilter();
  await fetchAssets();
  await nextTick();
  updateMediaGridColumns();
}

async function goToPageAndFetch(page) {
  goToPage(page);
  await fetchAssets();
  await nextTick();
  updateMediaGridColumns();
}

async function startRenameWithFocus() {
  startRename();
  await nextTick();
  const input = Array.isArray(renameInput.value)
    ? renameInput.value.find(Boolean)
    : renameInput.value;
  input?.focus?.();
  input?.select?.();
}

async function executeRenameSafe() {
  try {
    await executeRename();
  } catch (error) {
    console.error("Rename failed:", error);
    alert(`Rename failed: ${error.message || error}`);
  }
}

async function addTagSafe() {
  try {
    await addTag();
  } catch (error) {
    console.error("Failed to add tag:", error);
  }
}

async function removeTagSafe(tag) {
  try {
    await removeTag(tag);
  } catch (error) {
    console.error("Failed to remove tag:", error);
  }
}

async function executeDeleteSafe() {
  try {
    await executeDelete();
  } catch (error) {
    console.error("Delete failed:", error);
    alert(`Failed to delete: ${error.message || error}`);
  }
}

function close() {
  emit("close");
  clearSelection();
}

function clearAssignedImage() {
  emit("select", {
    url: "",
    id: null,
    filename: "",
    author: "",
    authors: [],
    responsive_variants: [],
  });
  close();
}

function updateMediaGridColumns() {
  if (typeof window === "undefined") {
    mediaGridColumns.value = 7;
    return;
  }
  const width = Number(window.innerWidth || 0);
  if (width <= 520) {
    mediaGridColumns.value = 2;
  } else if (width <= 700) {
    mediaGridColumns.value = 3;
  } else if (width <= 900) {
    mediaGridColumns.value = 5;
  } else {
    mediaGridColumns.value = 7;
  }
}

function disconnectMediaGridObserver() {
  if (!mediaGridResizeObserver) return;
  mediaGridResizeObserver.disconnect();
  mediaGridResizeObserver = null;
}

function setupMediaGridObserver() {
  disconnectMediaGridObserver();
  updateMediaGridColumns();
  if (typeof ResizeObserver === "undefined" || !gridRef.value) return;
  mediaGridResizeObserver = new ResizeObserver(() => updateMediaGridColumns());
  mediaGridResizeObserver.observe(gridRef.value);
}

watch(
  () => props.isOpen,
  async (isOpen) => {
    if (!isOpen) {
      unbindGlobalDragEvents();
      disconnectMediaGridObserver();
      return;
    }

    bindGlobalDragEvents();
    clearSelection();

    try {
      await Promise.all([fetchAssets(), fetchTags()]);
      if (props.currentUrl) {
        selectAssetByUrl(props.currentUrl);
      }
      await nextTick();
      setupMediaGridObserver();
    } catch (error) {
      console.error("Failed to initialize media library:", error);
    }
  }
);

watch(
  () => props.currentUrl,
  (url) => {
    if (!props.isOpen) return;
    if (!url) {
      clearSelection();
      return;
    }
    selectAssetByUrl(url);
  }
);

onBeforeUnmount(() => {
  clearTimeout(searchTimeout);
  unbindGlobalDragEvents();
  disconnectMediaGridObserver();
});
</script>

<style scoped>
.media-library-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  z-index: var(--admin-z-modal, 10000);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  transition: background 0.2s ease;
}

.media-library-overlay--dragging {
  background: rgba(15, 23, 42, 0.62);
}

.media-library {
  --media-popup-text: var(--admin-text, #0f172a);
  --media-popup-muted: var(--admin-muted, #64748b);
  --media-popup-surface: var(--admin-surface, #f8fafc);
  --media-popup-bg: var(--admin-bg, #ffffff);
  --media-popup-border: #e2e8f0;
  --media-popup-border-strong: rgba(148, 163, 184, 0.45);
  --media-popup-accent: var(--admin-primary-color, var(--admin-accent, #4f46e5));
  --media-popup-danger: var(--admin-danger-color, #dc2626);
  background: var(--media-popup-surface);
  color: var(--media-popup-text);
  border: 1px solid var(--media-popup-border);
  border-radius: 12px;
  width: 100%;
  max-width: 900px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.28);
  overflow: hidden;
  position: relative;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--media-popup-border);
  background: var(--media-popup-bg);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.clear-btn {
  padding: 8px 12px;
  border-radius: var(--admin-button-border-radius, 8px);
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
  cursor: pointer;
  transition: all 0.15s;
}

.clear-btn:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #94a3b8;
  color: #0f172a;
}

.clear-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.admin-media-btn {
  padding: 8px 11px;
  font-size: 0.75rem;
  line-height: 1;
}

.title {
  margin: 0;
  font-size: 1.125rem;
  color: var(--media-popup-text);
  font-weight: 700;
  line-height: 1.25;
}

.close-btn {
  background: none;
  border: none;
  color: var(--media-popup-muted);
  cursor: pointer;
  padding: 5px;
  border-radius: 8px;
  transition: all 0.15s;
}

.close-btn:hover {
  color: var(--media-popup-text);
  background: #f1f5f9;
}

.close-icon {
  font-size: 22px;
}

.drag-upload-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border-radius: inherit;
  background: rgba(248, 250, 252, 0.9);
  backdrop-filter: blur(3px);
}

.upload-zone {
  width: 100%;
  height: 100%;
  border: 2px dashed rgba(71, 85, 105, 0.5);
  border-radius: inherit;
  padding: 28px 24px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  transition: all 0.25s ease;
  position: relative;
  min-height: 0;
  background: var(--media-popup-surface);
  box-shadow: none;
}

.upload-zone--active {
  border-color: var(--media-popup-accent);
  background: color-mix(in srgb, var(--media-popup-accent) 8%, #ffffff);
}

.upload-icon {
  color: #334155;
  margin-bottom: 10px;
  font-size: 36px;
}

.upload-text {
  color: #334155;
  margin: 0;
  font-weight: 700;
}

.selection-filename {
  font-size: 13px;
  font-weight: 700;
  color: var(--media-popup-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rename-input {
  width: min(280px, 100%);
  padding: 8px 10px;
  border: 1px solid var(--media-popup-border-strong);
  border-radius: 9px;
  background: #fff;
  color: var(--media-popup-text);
  font-size: 13px;
  outline: none;
}

.rename-input:focus {
  border-color: var(--media-popup-accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--media-popup-accent) 16%, transparent);
}

.selection-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.sel-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 9px;
  border: 1px solid #cbd5e1;
  border-radius: var(--admin-button-border-radius, 8px);
  background: #fff;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.sel-action-icon {
  font-size: 12px;
}

.sel-action-btn:hover {
  background: #f8fafc;
  border-color: #94a3b8;
  color: #0f172a;
}

.sel-action-btn--confirm {
  border-color: var(--media-popup-accent);
  background: var(--media-popup-accent);
  color: #fff;
}

.sel-action-btn--confirm:hover {
  background: color-mix(in srgb, var(--media-popup-accent) 88%, #000000);
  border-color: color-mix(in srgb, var(--media-popup-accent) 88%, #000000);
  color: #fff;
}

.sel-action-btn--danger {
  border-color: rgba(220, 38, 38, 0.28);
  color: var(--media-popup-danger);
}

.sel-action-btn--danger:hover {
  color: #991b1b;
  background: #fef2f2;
  border-color: rgba(220, 38, 38, 0.38);
}

.sel-action-btn--muted {
  color: var(--media-popup-muted);
}

.sel-action-btn--muted:hover {
  color: var(--media-popup-text);
}

.selection-tags {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  align-items: center;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid rgba(148, 163, 184, 0.45);
  color: #334155;
  font-size: 11px;
  line-height: 1.2;
}

.tag-chip-remove {
  background: none;
  border: none;
  color: #475569;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  transition: color 0.15s;
}

.tag-chip-remove:hover {
  color: var(--media-popup-danger);
}

.tag-chip-remove-icon {
  font-size: 10px;
}

.tag-add-input {
  width: 110px;
  padding: 4px 9px;
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-radius: 999px;
  background: #fff;
  color: var(--media-popup-text);
  font-size: 11px;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.tag-add-input:focus {
  border-color: var(--media-popup-accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--media-popup-accent) 14%, transparent);
}

.tag-add-input::placeholder {
  color: #94a3b8;
}

.upload-progress {
  padding: 0 20px 12px;
}

.upload-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.upload-name {
  color: var(--media-popup-text);
  font-size: 0.875rem;
  flex-shrink: 0;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: rgba(148, 163, 184, 0.35);
  border-radius: 999px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--media-popup-accent);
  transition: width 0.2s;
}

.filter-row {
  padding: 12px 20px 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.search-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--media-popup-border-strong);
  border-radius: 9px;
  background: #fff;
  color: var(--media-popup-text);
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.search-input:focus {
  border-color: var(--media-popup-accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--media-popup-accent) 14%, transparent);
}

.search-input::placeholder {
  color: #94a3b8;
}

.tag-filters {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  align-items: center;
}

.tag-filter-btn {
  padding: 4px 10px;
  border: 1px solid rgba(148, 163, 184, 0.5);
  border-radius: 999px;
  background: #fff;
  color: #334155;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}

.tag-filter-btn:hover {
  background: #f8fafc;
  border-color: #94a3b8;
  color: #0f172a;
}

.tag-filter-btn--active {
  background: var(--media-popup-accent);
  border-color: var(--media-popup-accent);
  color: #fff;
}

.tag-filter-clear {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  transition: color 0.15s;
}

.tag-filter-clear:hover {
  color: #0f172a;
}

.tag-filter-clear-icon {
  font-size: 12px;
}

.image-grid {
  flex: 1;
  overflow-y: auto;
  padding: 0 20px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}

.image-row {
  display: grid;
  grid-template-columns: repeat(var(--media-picker-columns, 7), minmax(0, 1fr));
  gap: 10px;
}

.image-card {
  aspect-ratio: 1 / 1;
  min-width: 0;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid rgba(148, 163, 184, 0.4);
  display: flex;
  flex-direction: column;
}

.image-card:hover {
  border-color: #94a3b8;
}

.image-card--selected {
  border-color: var(--media-popup-accent);
  box-shadow: 0 0 0 1px var(--media-popup-accent);
  background: #fff;
}

.selection-inline-editor {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px 14px;
  align-items: center;
  padding: 14px;
  border: 1px solid color-mix(in srgb, var(--media-popup-accent) 32%, #e2e8f0);
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
}

.selection-inline-editor__name {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.selection-label {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.selection-inline-editor .selection-tags {
  grid-column: 1 / -1;
}

.image-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.image-thumb-surface {
  width: 100%;
  height: 100%;
  overflow: hidden;
  background-color: #f8fafc;
  background-image:
    linear-gradient(45deg, rgba(148, 163, 184, 0.24) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(148, 163, 184, 0.24) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(148, 163, 184, 0.24) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(148, 163, 184, 0.24) 75%);
  background-size: 12px 12px;
  background-position: 0 0, 0 6px, 6px -6px, -6px 0;
}

.image-thumb--image {
  background: transparent;
}

.image-card--video {
  position: relative;
}

.image-card--pdf {
  border-color: rgba(185, 28, 28, 0.35);
}

.video-badge {
  position: absolute;
  bottom: 6px;
  right: 6px;
  border: 1px solid rgba(15, 23, 42, 0.35);
  border-radius: 999px;
  background: rgba(248, 250, 252, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  color: #334155;
  line-height: 1;
  padding: 4px 7px;
}

.file-thumb {
  width: 100%;
  height: 100%;
  background: #f8fafc;
  color: #334155;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 8px;
  gap: 8px;
}

.file-thumb__badge {
  align-self: flex-start;
  font-size: 11px;
  letter-spacing: 0.08em;
  font-weight: 700;
  color: #991b1b;
  background: rgba(254, 226, 226, 0.9);
  border: 1px solid rgba(185, 28, 28, 0.35);
  border-radius: 999px;
  padding: 2px 7px;
}

.file-thumb__name {
  font-size: 12px;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.empty-state,
.loading-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--media-popup-muted);
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(148, 163, 184, 0.28);
  border-top-color: var(--media-popup-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 20px;
  border-top: 1px solid var(--media-popup-border);
  background: var(--media-popup-bg);
}

.footer-left {
  display: flex;
  gap: 10px;
}

.pagination {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-btn {
  padding: 7px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  border-radius: var(--admin-button-border-radius, 8px);
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.page-btn-icon {
  font-size: 15px;
}

.page-btn:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #94a3b8;
  color: #0f172a;
}

.page-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.page-info {
  color: var(--media-popup-muted);
  font-size: 12px;
  min-width: 40px;
  text-align: center;
}

.delete-modal {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.delete-dialog {
  background: #fff;
  border: 1px solid var(--media-popup-border);
  border-radius: 12px;
  padding: 24px;
  max-width: 400px;
  width: 90%;
  box-shadow: 0 20px 40px rgba(15, 23, 42, 0.2);
}

.delete-dialog h3 {
  margin: 0 0 8px;
  color: var(--media-popup-text);
  font-size: 1.125rem;
}

.delete-dialog p {
  margin: 0 0 20px;
  color: var(--media-popup-muted);
  font-size: 0.875rem;
  line-height: 1.5;
}

.delete-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 900px) {
  .drag-upload-overlay {
    left: 16px;
    right: 16px;
  }
}

@media (max-width: 700px) {
  .media-library {
    max-height: 95vh;
  }

  .selection-inline-editor {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 520px) {
  .media-library-overlay {
    padding: 8px;
  }

  .header,
  .filter-row,
  .image-grid,
  .footer,
  .upload-progress {
    padding-left: 12px;
    padding-right: 12px;
  }

  .drag-upload-overlay {
    inset: 64px 12px 64px;
  }
}
</style>
