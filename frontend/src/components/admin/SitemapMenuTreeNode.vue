<template>
  <div class="menu-tree-node">
    <div
      class="tree-item page-item menu-item-draggable"
      :class="{
        'is-hidden': isHiddenStatus(node.page),
        'is-under-construction': isUnderConstructionStatus(node.page),
        'subpage-item': depth > 0,
        'subtree-drag-source': isSubtreeDragSource(node.page.slug),
        'subtree-drop-target': isSubtreeDropTarget(node.page.slug),
        'subtree-drop-invalid': isSubtreeDropInvalid(node.page.slug),
      }"
      :style="depth > 0 ? { paddingLeft: `${12 + depth * 20}px` } : null"
      :draggable="subtreeReorderEnabled && !migratingSubtree && node.page.slug !== 'landing'"
      @dragstart="onSubtreeDragStart(node.page.slug, $event)"
      @dragend="onSubtreeDragEnd"
      @dragover.prevent="onSubtreeTargetDragOver(node.page.slug)"
      @drop.prevent="onSubtreeDrop(node.page.slug)"
    >
      <span
        class="drag-handle"
        :class="{ disabled: subtreeReorderEnabled || migratingSubtree }"
        :title="subtreeReorderEnabled ? 'Migration mode: drag reordering is disabled' : 'Drag to reorder'"
      >⋮⋮</span>
      <span v-if="depth > 0" class="tree-indent">└</span>
      <span class="tree-icon">
        <font-awesome-icon :icon="depth > 0 ? faFileLines : faFolderTree" />
      </span>
      <span class="tree-path" :title="getMenuHierarchyPathTooltip(node.page)" @click="selectPage(node.page)">
        {{ getMenuHierarchyPath(node.page) }}
      </span>
      <span class="tree-name" @click="selectPage(node.page)">{{ getMenuTitle(node.page) }}</span>
      <div class="page-badges">
        <span v-if="isHiddenStatus(node.page)" class="badge hidden">
          Hidden
        </span>
        <span v-else-if="isUnderConstructionStatus(node.page)" class="badge under-construction">
          Under Construction
        </span>
        <span v-if="depth > 0" class="badge subpage" title="Subpage">Sub</span>
      </div>
    </div>

    <div v-if="node.children?.length" class="menu-children">
      <draggable
        :model-value="node.children"
        @update:model-value="(val) => emit('reorder', { nodes: val, parentSlug: node.page.slug })"
        :item-key="(item) => item.page.id"
        handle=".drag-handle"
        ghost-class="drag-ghost"
        :animation="150"
        :disabled="subtreeReorderEnabled || migratingSubtree"
      >
        <template #item="{ element: child }">
          <SitemapMenuTreeNode
            :node="child"
            :depth="depth + 1"
            :subtree-reorder-enabled="subtreeReorderEnabled"
            :migrating-subtree="migratingSubtree"
            :select-page="selectPage"
            :get-menu-title="getMenuTitle"
            :is-subtree-drag-source="isSubtreeDragSource"
            :is-subtree-drop-target="isSubtreeDropTarget"
            :is-subtree-drop-invalid="isSubtreeDropInvalid"
            :on-subtree-drag-start="onSubtreeDragStart"
            :on-subtree-drag-end="onSubtreeDragEnd"
            :on-subtree-target-drag-over="onSubtreeTargetDragOver"
            :on-subtree-drop="onSubtreeDrop"
            @reorder="emit('reorder', $event)"
          />
        </template>
      </draggable>
    </div>
  </div>
</template>

<script setup>
import draggable from 'vuedraggable';
import { faFileLines, faFolderTree } from "@fortawesome/free-solid-svg-icons";

defineOptions({ name: 'SitemapMenuTreeNode' });

const props = defineProps({
  node: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  subtreeReorderEnabled: { type: Boolean, default: false },
  migratingSubtree: { type: Boolean, default: false },
  selectPage: { type: Function, required: true },
  getMenuTitle: { type: Function, required: true },
  isSubtreeDragSource: { type: Function, required: true },
  isSubtreeDropTarget: { type: Function, required: true },
  isSubtreeDropInvalid: { type: Function, required: true },
  onSubtreeDragStart: { type: Function, required: true },
  onSubtreeDragEnd: { type: Function, required: true },
  onSubtreeTargetDragOver: { type: Function, required: true },
  onSubtreeDrop: { type: Function, required: true },
});

const emit = defineEmits(['reorder']);

function normalizeStatus(value) {
  const raw = String(value || '').trim().toLowerCase();
  if (raw === 'draft') return 'hidden';
  if (raw === 'init' || raw === 'published' || raw === 'under_construction' || raw === 'hidden') return raw;
  return 'hidden';
}

function effectiveStatus(page) {
  const normalized = normalizeStatus(page?.effective_status || page?.status);
  return normalized === 'init' ? 'hidden' : normalized;
}

function isHiddenStatus(page) {
  return effectiveStatus(page) === 'hidden';
}

function isUnderConstructionStatus(page) {
  return effectiveStatus(page) === 'under_construction';
}

function getMenuHierarchyPath(page) {
  const slug = String(page?.slug || '').trim();
  if (!slug || slug === 'landing') return '/';
  if (page?.menu_show_as_top_level) {
    const slugParts = slug.split('/').filter(Boolean);
    const leafSlug = slugParts[slugParts.length - 1] || slug;
    return `/${leafSlug}`;
  }
  return `/${slug}`;
}

function getMenuHierarchyPathTooltip(page) {
  const slug = String(page?.slug || '').trim();
  if (!slug || slug === 'landing') return '/';
  if (page?.menu_show_as_top_level) return `Full route: /${slug}`;
  return `/${slug}`;
}
</script>

<style scoped>
.menu-tree-node {
  margin-bottom: 2px;
}
.menu-children {
  margin-left: 16px;
  border-left: 1px solid #e2e8f0;
}
.tree-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  margin: 2px 0;
  border-radius: 6px;
  font-size: 13px;
  transition: background 0.15s;
}
.tree-item:hover {
  background: #f1f5f9;
}
.tree-path {
  font-family: ui-monospace, monospace;
  color: #64748b;
  font-size: 12px;
}
.tree-name {
  color: #0f172a;
  flex: 1;
}
.tree-indent {
  color: #cbd5e1;
  font-family: ui-monospace, monospace;
  margin-right: 4px;
}
.page-item {
  cursor: pointer;
  border: 1px solid transparent;
  position: relative;
}
.page-item:hover {
  border-color: #e2e8f0;
}
.page-item.is-hidden {
  opacity: 0.7;
}
.page-item.is-hidden:hover {
  opacity: 1;
}
.page-item.is-under-construction {
  border-color: #f59e0b;
}
.menu-item-draggable {
  display: flex;
  align-items: center;
}
.menu-item-draggable .tree-path,
.menu-item-draggable .tree-name {
  cursor: pointer;
}
.drag-handle {
  cursor: grab;
  color: #94a3b8;
  font-size: 12px;
  letter-spacing: -2px;
  padding: 0 4px;
  margin-right: 4px;
  user-select: none;
  opacity: 0.5;
  transition: opacity 0.15s, color 0.15s;
}
.drag-handle:hover {
  opacity: 1;
  color: #475569;
}
.drag-handle:active {
  cursor: grabbing;
}
.drag-handle.disabled {
  cursor: not-allowed;
  opacity: 0.25;
}
.drag-handle.disabled:hover {
  color: #94a3b8;
  opacity: 0.25;
}
.subtree-drag-source {
  opacity: 0.75;
  outline: 1px dashed #93c5fd;
}
.subtree-drop-target {
  background: #e0f2fe !important;
  border-color: #0284c7 !important;
}
.subtree-drop-invalid {
  background: #fef2f2 !important;
  border-color: #ef4444 !important;
}
.drag-ghost {
  opacity: 0.5;
  background: #e0f2fe;
  border: 1px dashed #0ea5e9 !important;
}
.badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.badge.hidden {
  background: #e2e8f0;
  color: #475569;
}
.badge.under-construction {
  background: #ffedd5;
  color: #9a3412;
}
.badge.subpage {
  background: #e0f2fe;
  color: #0369a1;
}
</style>
