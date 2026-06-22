<template>
  <span ref="anchorEl" class="section-admin-tabs-anchor" aria-hidden="true"></span>
  <Teleport :to="teleportTarget" :disabled="!isTeleportEnabled">
    <div
      v-if="visible && tabs.length > 0"
      class="section-admin-tabs"
      :class="{
        'section-admin-tabs--editor-pinned': isEditorPinned,
        'section-admin-tabs--editor-pinned-inactive': isEditorPinned && !isPinnedInstanceActive,
      }"
      :style="pinnedContainerStyle"
      v-bind="attrs"
      @click.stop
    >
    <div
      v-if="isEditorPinned && isPinnedInstanceActive"
      class="section-admin-tabs__resize-handle"
      title="Drag to resize editor"
      @pointerdown="startPinnedResize"
      @dblclick="resetPinnedHeight"
    >
      <span class="section-admin-tabs__resize-grip" aria-hidden="true"></span>
    </div>
    <div
      v-if="showPinnedEditorSwitcher"
      class="section-admin-tabs__super-tabs"
      role="tablist"
      aria-label="Pinned section editors"
    >
      <button
        v-for="entry in pinnedEditors"
        :key="entry.id"
        type="button"
        class="section-admin-tabs__super-tab"
        :class="{ active: resolvedActivePinnedEditorId === entry.id }"
        :aria-selected="resolvedActivePinnedEditorId === entry.id"
        :aria-current="resolvedActivePinnedEditorId === entry.id ? 'page' : undefined"
        @click="selectPinnedEditor(entry.id)"
      >
        <span class="section-admin-tabs__super-tab-label">{{ entry.label }}</span>
      </button>
    </div>
    <div class="section-admin-tabs__head">
      <div class="section-admin-tabs__tabs" role="tablist" aria-label="Section admin tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          class="section-admin-tabs__tab"
          :class="{ active: active === tab.key }"
          role="tab"
          :aria-selected="active === tab.key"
          @click="setTab(tab.key)"
        >
          <font-awesome-icon :icon="getTabIcon(tab.key)" class="section-admin-tabs__tab-icon" />
          <span>{{ tab.label }}</span>
        </button>
      </div>
      <button
        v-if="isEditorPinned && isPinnedInstanceActive"
        type="button"
        class="section-admin-tabs__pin-btn section-admin-tabs__pin-all-btn"
        @click="pinAllSectionEditors"
      >
        Fix All
      </button>
      <button
        v-if="isEditorPinned && isPinnedInstanceActive"
        type="button"
        class="section-admin-tabs__pin-btn section-admin-tabs__pin-all-btn"
        @click="releaseAllSectionEditors"
      >
        Release All
      </button>
      <button
        type="button"
        class="section-admin-tabs__pin-btn"
        :class="{ active: isEditorPinned }"
        :aria-pressed="isEditorPinned ? 'true' : 'false'"
        @click="toggleEditorPinned"
      >
        <font-awesome-icon :icon="faThumbtack" class="section-admin-tabs__pin-icon" />
        <span>{{ isEditorPinned ? "Release editor" : "Fix editor" }}</span>
      </button>
    </div>
    <AutosaveToast :message="sectionAutosaveMessage" :tone="sectionAutosaveTone" />

    <Transition
      mode="out-in"
      @before-enter="onBodyBeforeEnter"
      @enter="onBodyEnter"
      @after-enter="onBodyAfterEnter"
      @before-leave="onBodyBeforeLeave"
      @leave="onBodyLeave"
      @after-leave="onBodyAfterLeave"
    >
    <div v-if="active" ref="bodyEl" :key="active" class="section-admin-tabs__body">
      <div v-if="active === 'design' && showDesign" class="section-admin-tabs__design">
        <div v-if="props.simpleDesignBody">
          <slot name="design" />
        </div>
        <template v-else>
          <details
            v-if="showTypeSpecificDesignControls()"
            class="section-admin-tabs__design-section section-admin-tabs__type-specific"
            :open="typeSpecificOpen"
            @toggle="typeSpecificOpen = $event.currentTarget.open"
          >
            <summary class="section-admin-tabs__design-summary">Section Type Specific</summary>
            <div class="section-admin-tabs__design-content">
              <div
                class="section-admin-tabs__type-specific-body"
                :class="{
                  'has-params': hasDesignParamsControls(),
                  'has-colors': hasDesignColorControls(),
                  'has-legacy': showLegacyDesignControls(),
                }"
              >
                <div v-if="hasDesignParamsControls()" class="section-admin-tabs__type-specific-params">
                  <slot name="design-params" />
                </div>
                <div v-if="hasDesignColorControls()" class="section-admin-tabs__type-specific-colors">
                  <slot name="design-colors" />
                </div>
                <div v-if="showLegacyDesignControls()" class="section-admin-tabs__type-specific-legacy">
                  <slot name="design" />
                </div>
              </div>
            </div>
          </details>
          <div
            v-if="showGenericCssGrid"
            class="section-admin-tabs__generic-css-grid"
            :class="{ 'is-single': genericCssGridSingle }"
          >
            <details
              v-if="props.showSectionGeneric"
              class="section-admin-tabs__design-section section-admin-tabs__constants"
              :open="constantsOpen"
              @toggle="constantsOpen = $event.currentTarget.open"
            >
              <summary class="section-admin-tabs__design-summary">Section Generic</summary>
              <div class="section-admin-tabs__design-content section-admin-tabs__constants-list">
                <div
                  v-if="isConstantParamEnabled('hideSectionHeader') && supportsHeaderDescriptionHideControls"
                  class="constant-choice"
                >
                  <select
                    class="constant-choice__select"
                    :value="String(sectionHeaderHideState)"
                    @change="onHideStateSelectChange('hideSectionHeader', $event.target.value)"
                  >
                    <option :value="String(HIDE_STATE_VISIBLE)">Show header</option>
                    <option :value="String(HIDE_STATE_MUTED)">Hide header (preview)</option>
                    <option :value="String(HIDE_STATE_HARD)">Hide header</option>
                  </select>
                </div>
                <div
                  v-if="isConstantParamEnabled('hideSectionDescription') && supportsHeaderDescriptionHideControls"
                  class="constant-choice"
                >
                  <select
                    class="constant-choice__select"
                    :value="String(sectionDescriptionHideState)"
                    @change="onHideStateSelectChange('hideSectionDescription', $event.target.value)"
                  >
                    <option :value="String(HIDE_STATE_VISIBLE)">Show description</option>
                    <option :value="String(HIDE_STATE_MUTED)">Hide description (preview)</option>
                    <option :value="String(HIDE_STATE_HARD)">Hide description</option>
                  </select>
                </div>
                <label v-if="isConstantParamEnabled('removeSectionPadding')" class="constant-check">
                  <input
                    type="checkbox"
                    :checked="isSectionPaddingRemoved"
                    @change="setConstantOverride('removeSectionPadding', $event.target.checked)"
                  />
                  <span>Remove section padding</span>
                </label>
                <label v-if="isConstantParamEnabled('removeSectionBackground')" class="constant-check">
                  <input
                    type="checkbox"
                    :checked="isSectionBackgroundRemoved"
                    @change="setConstantOverride('removeSectionBackground', $event.target.checked)"
                  />
                  <span>Remove section background</span>
                </label>
                <label
                  v-if="isConstantParamEnabled(LIST_EMPTY_PUBLIC_GENERIC_KEY) && supportsHideWhenListEmptyPublic"
                  class="constant-check"
                >
                  <input
                    type="checkbox"
                    :checked="isHideWhenListEmptyPublicEnabled"
                    @change="setConstantOverride(LIST_EMPTY_PUBLIC_GENERIC_KEY, $event.target.checked)"
                  />
                  <span>Hide in public when list is empty</span>
                </label>
                <label
                  v-if="supportsShowWhenVideoEmptyPublic"
                  class="constant-check"
                >
                  <input
                    type="checkbox"
                    :checked="isShowWhenVideoEmptyPublicEnabled"
                    @change="setConstantOverride(SHOW_VIDEO_EMPTY_PUBLIC_GENERIC_KEY, $event.target.checked)"
                  />
                  <span>Show in public when video link is empty</span>
                </label>
                <div
                  v-if="supportsSectionCtaButtonAlignment"
                  class="constant-choice"
                >
                  <label class="constant-choice__label">Button alignment</label>
                  <select
                    class="constant-choice__select"
                    :value="sectionCtaButtonAlignment"
                    @change="onSectionCtaButtonAlignmentChange($event.target.value)"
                  >
                    <option value="left">Left</option>
                    <option value="center">Center</option>
                    <option value="right">Right</option>
                  </select>
                </div>
              </div>
            </details>
            <details
              v-if="!pageDesignOverridesLocked"
              class="section-admin-tabs__design-section section-admin-tabs__custom-css"
              :open="customCssOpen"
              @toggle="customCssOpen = $event.currentTarget.open"
            >
              <summary class="section-admin-tabs__design-summary">Custom CSS</summary>
              <div class="section-admin-tabs__design-content section-admin-tabs__custom-css-body">
                <textarea
                  v-model="sectionCustomCssDraft"
                  class="section-admin-tabs__custom-css-textarea"
                  rows="5"
                  placeholder="p { display: none; }"
                  @input="onSectionCustomCssInput"
                />
                <div class="section-admin-tabs__custom-css-actions">
                  <button
                    class="btn"
                    type="button"
                    :disabled="!sectionCustomCssDraft.trim() || !sectionSnippetContextKey"
                    @click="saveSectionCustomCssSnippet"
                  >
                    Save as Snippet
                  </button>
                  <button
                    class="btn section-admin-tabs__custom-css-open-btn"
                    type="button"
                    @click="openCustomCssInDesignPanel"
                  >
                    Open CSS In Design Panel
                  </button>
                </div>
                <div class="section-admin-tabs__snippet-section">
                  <div class="section-admin-tabs__snippet-title">Saved snippets</div>
                  <div v-if="sectionSnippetsLoading" class="section-admin-tabs__snippet-hint">Loading…</div>
                  <div v-else-if="sectionCssSnippets.length === 0" class="section-admin-tabs__snippet-hint">No section snippets yet.</div>
                  <div v-for="snippet in sectionCssSnippets" :key="snippet.id" class="section-admin-tabs__snippet-card" :class="{ inactive: !snippet.active }">
                    <div class="section-admin-tabs__snippet-head">
                      <label class="section-admin-tabs__snippet-toggle">
                        <input type="checkbox" :checked="snippet.active" @change="toggleSectionCssSnippet(snippet)" />
                        <span class="section-admin-tabs__snippet-label">{{ snippet.label }}</span>
                        <span v-if="snippet.media_scope" class="section-admin-tabs__snippet-scope">{{ snippet.media_scope }}</span>
                      </label>
                      <button class="section-admin-tabs__snippet-del" type="button" title="Delete" @click="removeSectionCssSnippet(snippet)">✕</button>
                    </div>
                    <pre class="section-admin-tabs__snippet-preview">{{ snippet.css?.length > 120 ? snippet.css.slice(0, 120) + "…" : snippet.css }}</pre>
                  </div>
                </div>
              </div>
            </details>
          </div>
          <div v-if="showConstantDesignControls" class="section-admin-tabs__design-footer">
            <button
              v-if="!pageDesignOverridesLocked"
              class="btn section-admin-tabs__constants-btn"
              type="button"
              @click="openDesignOverrides"
            >
              Open Design Overrides
            </button>
            <p v-else class="section-admin-tabs__history-empty">
              Style is controlled by the linked page template. Design overrides are disabled.
            </p>
          </div>
        </template>
      </div>
      <div v-else-if="active === 'content' && showContent">
        <slot name="content" />
      </div>
      <div v-else-if="active === 'output' && props.showOutput">
        <slot name="output" />
      </div>
      <div v-else-if="active === 'history' && props.showHistory && hasAuxTabContext">
        <slot v-if="$slots.history" name="history" />
        <div v-else class="section-admin-tabs__history">
          <div class="section-admin-tabs__history-head">
            <button type="button" class="btn section-admin-tabs__history-config-btn" @click="openRevisionSettings">
              Configure Revisions
            </button>
          </div>
          <div v-if="historyLoading" class="section-admin-tabs__history-empty">Loading history…</div>
          <div v-else-if="historyError" class="section-admin-tabs__history-empty">{{ historyError }}</div>
          <div v-else-if="!showDesignHistory && !showContentHistory" class="section-admin-tabs__history-empty">
            Revisions are disabled for this section type. Configure them in Admin Database.
          </div>
          <div v-else class="section-admin-tabs__history-grid" :class="{ 'single-column': !showDesignHistory || !showContentHistory }">
            <div v-if="showDesignHistory" class="section-admin-tabs__history-col">
              <div class="section-admin-tabs__history-title">Design</div>
              <button
                v-for="entry in designHistoryEntries"
                :key="`design-${entry.key}`"
                type="button"
                class="section-admin-tabs__history-item"
                :class="{ active: selectedDesignRevisionKey === entry.key, current: entry.source === 'current' }"
                @click="selectHistoryEntry('design', entry)"
              >
                <div class="section-admin-tabs__history-item-head">
                  <AuthorBadge :name="entry.savedBy" :timestamp="entry.savedAt" />
                  <span class="section-admin-tabs__history-author">{{ entry.savedBy }}</span>
                </div>
                <div class="section-admin-tabs__history-date">{{ formatHistoryDate(entry.savedAt) }}</div>
                <div v-if="entry.designParamDiffs?.length" class="section-admin-tabs__history-diff">
                  {{ summarizeParamDiffs(entry.designParamDiffs) }}
                </div>
              </button>
              <p v-if="designHistoryEntries.length === 0" class="section-admin-tabs__history-empty">No design revisions.</p>
              <div class="section-admin-tabs__history-actions">
                <button
                  type="button"
                  class="btn"
                  :disabled="!canRevertDesign || historyRevertingDesign"
                  @click="revertSelectedRevision('design')"
                >
                  {{ historyRevertingDesign ? "Reverting…" : "Revert Design" }}
                </button>
              </div>
            </div>
            <div v-if="showContentHistory" class="section-admin-tabs__history-col">
              <div class="section-admin-tabs__history-title">Content</div>
              <button
                v-for="entry in contentHistoryEntries"
                :key="`content-${entry.key}`"
                type="button"
                class="section-admin-tabs__history-item"
                :class="{ active: selectedContentRevisionKey === entry.key, current: entry.source === 'current' }"
                @click="selectHistoryEntry('content', entry)"
              >
                <div class="section-admin-tabs__history-item-head">
                  <AuthorBadge :name="entry.savedBy" :timestamp="entry.savedAt" />
                  <span class="section-admin-tabs__history-author">{{ entry.savedBy }}</span>
                </div>
                <div class="section-admin-tabs__history-date">{{ formatHistoryDate(entry.savedAt) }}</div>
                <div v-if="entry.contentParamDiffs?.length" class="section-admin-tabs__history-diff">
                  {{ summarizeParamDiffs(entry.contentParamDiffs) }}
                </div>
              </button>
              <p v-if="contentHistoryEntries.length === 0" class="section-admin-tabs__history-empty">No content revisions.</p>
              <div class="section-admin-tabs__history-actions">
                <button
                  type="button"
                  class="btn"
                  :disabled="!canRevertContent || historyRevertingContent"
                  @click="revertSelectedRevision('content')"
                >
                  {{ historyRevertingContent ? "Reverting…" : "Revert Content" }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="active === 'template' && showAnyTemplateTab && hasAuxTabContext">
        <div v-if="showTemplateTab" class="section-admin-tabs__template">
          <div class="section-admin-tabs__template-share">
            <label class="section-admin-tabs__template-share-check">
              <input
                type="checkbox"
                :checked="currentSectionShared"
                :disabled="!currentSectionId || sectionSharingSaving"
                @change="toggleSectionShared"
              />
              <span>Share current section</span>
            </label>
            <p class="section-admin-tabs__template-summary">
              Shared sections appear in Manage Sections &gt; Shared Sections. Pages using the same section stay linked, so future edits affect every page using it.
            </p>
            <p v-if="sectionSharingError" class="section-admin-tabs__template-feedback section-admin-tabs__template-feedback--error">
              {{ sectionSharingError }}
            </p>
          </div>
          <div class="section-admin-tabs__template-head">
            <p class="section-admin-tabs__template-ref">
              This section is based on template
              <code>{{ sectionTemplateRef }}</code>.
            </p>
            <div class="section-admin-tabs__template-actions">
              <button
                type="button"
                class="btn"
                :disabled="!templateLinkTarget"
                @click="openSectionTemplate"
              >
                Open Template
              </button>
              <button
                type="button"
                class="btn-secondary"
                :disabled="templatePreviewLoading"
                @click="loadTemplateSyncPreview"
              >
                {{ templatePreviewLoading ? "Refreshing…" : "Refresh" }}
              </button>
            </div>
          </div>
          <div v-if="templatePreviewLoading" class="section-admin-tabs__history-empty">
            Comparing section with template…
          </div>
          <div v-else-if="templatePreviewError" class="section-admin-tabs__history-empty">
            {{ templatePreviewError }}
          </div>
          <div v-else-if="templatePreview" class="section-admin-tabs__template-body">
            <p v-if="templatePreview.has_changes" class="section-admin-tabs__template-summary">
              {{ templateChangedFields.length }} template-managed field{{ templateChangedFields.length === 1 ? "" : "s" }} differ from this section instance.
            </p>
            <p v-else class="section-admin-tabs__template-summary">
              This section instance is already in sync with its template.
            </p>
            <ul v-if="templateChangedFieldLabels.length > 0" class="section-admin-tabs__template-diff-list">
              <li v-for="label in templateChangedFieldLabels" :key="label">{{ label }}</li>
            </ul>
            <div class="section-admin-tabs__template-actions">
              <button
                type="button"
                class="btn"
                :disabled="templateSyncing || templateChangedFields.length === 0"
                @click="syncTemplateChanges"
              >
                {{ templateSyncing ? "Syncing…" : "Sync Template Changes" }}
              </button>
            </div>
            <p v-if="templateSyncError" class="section-admin-tabs__template-feedback section-admin-tabs__template-feedback--error">
              {{ templateSyncError }}
            </p>
            <p v-else-if="templateSyncMessage" class="section-admin-tabs__template-feedback">
              {{ templateSyncMessage }}
            </p>
          </div>
          <div v-if="showCustomTemplateTab" class="section-admin-tabs__template-extra">
            <slot name="template" />
          </div>
        </div>
        <div v-else-if="showCustomTemplateTab" class="section-admin-tabs__template section-admin-tabs__template--custom">
          <slot name="template" />
        </div>
      </div>
      <div v-else-if="active === 'notes' && showNotes && hasAuxTabContext">
        <slot v-if="$slots.notes" name="notes" />
        <div v-else class="section-admin-tabs__notes">
          <label class="notes-label" :for="notesInputId">Notes</label>
          <textarea
            :id="notesInputId"
            v-model="notesDraft"
            class="notes-textarea"
            rows="4"
            placeholder="Add notes for this section instance..."
            @input="persistNotes"
          />

          <div class="todo-board">
            <div class="todo-head">Todos</div>
            <div class="todo-add">
              <input
                v-model="newTodo"
                class="todo-input"
                type="text"
                placeholder="Add todo..."
                @keydown.enter.prevent="addTodo"
              />
              <TodoIconSelect
                v-model="newTodoTag"
                :options="todoTagSelectOptions"
                aria-label="Todo type"
              />
              <TodoIconSelect
                v-model="newTodoPriority"
                :options="todoPrioritySelectOptions"
                aria-label="Todo urgency"
              />
              <button class="btn" type="button" @click="addTodo">Add</button>
            </div>

            <div class="todo-list">
              <div class="todo-group">
                <div class="todo-group-title">Open ({{ openTodos.length }})</div>
                <label
                  v-for="todo in openTodos"
                  :key="todo.id"
                  class="todo-item"
                  :class="[`tone-${todoTagArea(todo.tag)}`, `prio-${todo.priority}`]"
                >
                  <input
                    type="checkbox"
                    :checked="todo.done"
                    @change="toggleTodo(todo.id, $event.target.checked)"
                  />
                  <div class="todo-main">
                    <span class="todo-text">{{ todo.text }}</span>
                    <div class="todo-meta-row">
                      <span
                        class="todo-chip todo-chip--tag"
                        :class="`area-${todoTagArea(todo.tag)}`"
                        :title="todoTagIconLabel(todo.tag)"
                        :aria-label="todoTagIconLabel(todo.tag)"
                      >
                        <font-awesome-icon
                          v-if="todoTagIcon(todo.tag)"
                          :icon="todoTagIcon(todo.tag)"
                          class="todo-chip-icon"
                          aria-hidden="true"
                        />
                        <span>{{ todoTagText(todo.tag) }}</span>
                      </span>
                      <span
                        class="todo-chip todo-chip--priority"
                        :class="`priority-${todo.priority}`"
                        :title="priorityIconLabel(todo.priority)"
                        :aria-label="priorityIconLabel(todo.priority)"
                      >
                        <font-awesome-icon :icon="priorityIcon(todo.priority)" aria-hidden="true" />
                      </span>
                    </div>
                  </div>
                  <AuthorBadge class="todo-author" :name="todoAuthorName(todo)" :timestamp="todoAuthorTime(todo)" />
                  <button class="todo-remove" type="button" @click.prevent="removeTodo(todo.id)">&times;</button>
                </label>
                <p v-if="openTodos.length === 0" class="todo-empty">No open todos.</p>
              </div>
              <div class="todo-group">
                <div class="todo-group-title">Done ({{ doneTodos.length }})</div>
                <label
                  v-for="todo in doneTodos"
                  :key="todo.id"
                  class="todo-item"
                  :class="[`tone-${todoTagArea(todo.tag)}`, `prio-${todo.priority}`]"
                >
                  <input
                    type="checkbox"
                    :checked="todo.done"
                    @change="toggleTodo(todo.id, $event.target.checked)"
                  />
                  <div class="todo-main">
                    <span class="todo-text done">{{ todo.text }}</span>
                    <div class="todo-meta-row">
                      <span
                        class="todo-chip todo-chip--tag"
                        :class="`area-${todoTagArea(todo.tag)}`"
                        :title="todoTagIconLabel(todo.tag)"
                        :aria-label="todoTagIconLabel(todo.tag)"
                      >
                        <font-awesome-icon
                          v-if="todoTagIcon(todo.tag)"
                          :icon="todoTagIcon(todo.tag)"
                          class="todo-chip-icon"
                          aria-hidden="true"
                        />
                        <span>{{ todoTagText(todo.tag) }}</span>
                      </span>
                      <span
                        class="todo-chip todo-chip--priority"
                        :class="`priority-${todo.priority}`"
                        :title="priorityIconLabel(todo.priority)"
                        :aria-label="priorityIconLabel(todo.priority)"
                      >
                        <font-awesome-icon :icon="priorityIcon(todo.priority)" aria-hidden="true" />
                      </span>
                    </div>
                  </div>
                  <AuthorBadge class="todo-author" :name="todoAuthorName(todo)" :timestamp="todoAuthorTime(todo)" />
                  <button class="todo-remove" type="button" @click.prevent="removeTodo(todo.id)">&times;</button>
                </label>
                <p v-if="doneTodos.length === 0" class="todo-empty">No done todos.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    </Transition>
    </div>
  </Teleport>
</template>

<script setup>
import { Comment, Fragment, Text, computed, nextTick, onBeforeUnmount, onMounted, ref, useAttrs, useSlots, watch } from "vue";
import {
  faClock,
  faFileLines,
  faPaintbrush,
  faPenToSquare,
  faThumbtack,
} from "@fortawesome/free-solid-svg-icons";
import { useRoute, useRouter } from "vue-router";
import { useStore } from "../../../store/store.js";
import * as api from "../../../services/api.js";
import { getUser } from "../../../services/auth.js";
import TodoIconSelect from "../TodoIconSelect.vue";
import { buildSectionContainerMaps } from "../../../utils/sectionContainers.js";
import { sectionSnippetContextKey as buildSectionSnippetContextKey } from "../../../utils/cssSnippets.js";
import {
  DEFAULT_TODO_PRIORITY,
  DEFAULT_TODO_TAG_ID,
  TODO_PRIORITY_VALUES,
  normalizeTodoList,
  normalizeTodoTags,
  serializeTodoList,
  todoPriorityIcon as priorityIcon,
  todoPriorityIconLabel as priorityIconLabel,
  todoPrioritySelectOption,
  todoTagIcon,
  todoTagIconLabel,
  todoTagSelectOption,
  todoTagText,
} from "../../../utils/adminTodos.js";
import {
  formatInstantInServerTimezone,
  formatRevisionTimestampBerlin,
  getRevisionTimestampMs,
} from "../../../utils/revisionTime.js";
import AutosaveToast from "../AutosaveToast.vue";
import AuthorBadge from "../../ui/AuthorBadge.vue";

const props = defineProps({
  visible: { type: Boolean, default: true },
  activeTab: { type: String, default: "" },
  allowCollapse: { type: Boolean, default: true },
  startCollapsed: { type: Boolean, default: true },
  sectionKey: { type: String, default: "" },
  editorLabel: { type: String, default: "" },
  sectionData: { type: Object, default: null },
  forceAuxTabs: { type: Boolean, default: false },
  simpleDesignBody: { type: Boolean, default: false },
  showSectionGeneric: { type: Boolean, default: true },
  showDesign: { type: Boolean, default: true },
  showContent: { type: Boolean, default: true },
  showHistory: { type: Boolean, default: true },
  showOutput: { type: Boolean, default: false },
  showTemplate: { type: Boolean, default: false },
  showNotes: { type: Boolean, default: true },
  designLabel: { type: String, default: "Design" },
  contentLabel: { type: String, default: "Content" },
  historyLabel: { type: String, default: "History" },
  outputLabel: { type: String, default: "Output" },
  templateLabel: { type: String, default: "Template" },
  notesLabel: { type: String, default: "Notes" },
  autosaveMessage: { type: String, default: "" },
  autosaveTone: { type: String, default: "idle" },
});

const emit = defineEmits(["update:activeTab", "tab-change"]);
const attrs = useAttrs();
const slots = useSlots();
const {
  state,
  updateSection,
  saveSectionByKey,
  applyBackendSectionByKey,
  openSectionDesignPanel,
  saveSectionDesignOverrides,
  refreshRevisionStatus,
  applySectionRevisionPreview,
  fetchFaqSharedData,
  fetchBlogData,
  fetchProgramSharedData,
  setSectionAdminActiveTab,
  upsertSectionAdminPinnedEditor,
  removeSectionAdminPinnedEditor,
  setSectionAdminPinnedActiveEditor,
  setSectionAdminPinnedSharedTab,
  setSectionAdminPinnedSharedHeightPx,
} = useStore();
const router = useRouter();
const route = useRoute();
const instanceId = `section-admin-tabs-${Math.random().toString(36).slice(2, 10)}-${Date.now().toString(36)}`;

const notesDraft = ref("");
const todoDraft = ref([]);
const newTodo = ref("");
const newTodoTag = ref(DEFAULT_TODO_TAG_ID);
const newTodoPriority = ref(DEFAULT_TODO_PRIORITY);
const todoTagOptions = ref(normalizeTodoTags([]));
const constantsOpen = ref(false);
const typeSpecificOpen = ref(true);
const customCssOpen = ref(false);
const sectionCustomCssDraft = ref("");
const sectionCssSnippets = ref([]);
const sectionSnippetsLoading = ref(false);
const historyLoading = ref(false);
const historyRevertingDesign = ref(false);
const historyRevertingContent = ref(false);
const historyError = ref("");
const historyCurrent = ref(null);
const historyStack = ref([]);
const futureStack = ref([]);
const historyOptions = ref({
  includeDesign: true,
  includeContent: true,
});
const selectedDesignRevisionKey = ref("current-design");
const selectedContentRevisionKey = ref("current-content");
const templatePreviewLoading = ref(false);
const templatePreviewError = ref("");
const templatePreview = ref(null);
const templateSyncing = ref(false);
const templateSyncError = ref("");
const templateSyncMessage = ref("");
const sectionSharingSaving = ref(false);
const sectionSharingError = ref("");
const DEFAULT_CONSTANT_SECTION_PARAMS = [
  "hideSectionHeader",
  "hideSectionDescription",
  "removeSectionPadding",
  "removeSectionBackground",
  "hideSectionIfListEmptyPublic",
];
const LIST_EMPTY_PUBLIC_GENERIC_KEY = "hideSectionIfListEmptyPublic";
const SHOW_VIDEO_EMPTY_PUBLIC_GENERIC_KEY = "showSectionIfVideoEmptyPublic";
const LIST_SECTION_TYPES_WITH_GENERIC_EMPTY_TOGGLE = new Set([
  "faq",
  "links",
  "gallery",
  "tiles",
  "program",
  "ticker",
]);
const VIDEO_SECTION_TYPES_WITH_GENERIC_EMPTY_TOGGLE = new Set([
  "video",
]);
const CTA_BUTTON_ALIGNMENT_DEFAULT = "center";
const HIDE_STATE_VISIBLE = 0;
const HIDE_STATE_MUTED = 1;
const HIDE_STATE_HARD = 2;
const HIDE_STATE_HARD_KEY_BY_CONSTANT = Object.freeze({
  hideSectionHeader: "hideSectionHeaderHard",
  hideSectionDescription: "hideSectionDescriptionHard",
});
const TEMPLATE_SYNC_FIELD_LABELS = Object.freeze({
  title_placeholder: "Title Placeholder",
  title: "Title",
  type_data: "Section Fields",
  section_integration_mapping: "Integration Import Mapping",
  design_overrides: "Design Overrides",
});
let historyLoadRequestId = 0;

const hasSectionContext = computed(() => Boolean(props.sectionKey));
const hasAuxTabContext = computed(() => hasSectionContext.value || props.forceAuxTabs);
const templateBuilderContext = computed(() => {
  const context = api.getTemplateBuilderContext?.();
  if (context) return context;
  const slug = String(state.pageSlug || "");
  if (slug.startsWith("__template_section__/")) return { kind: "section" };
  if (slug.startsWith("__template_container__/")) return { kind: "container" };
  if (slug.startsWith("__template_page__/")) return { kind: "page" };
  return null;
});
const hasTemplateBuilderContext = computed(() => Boolean(templateBuilderContext.value));
const isSectionTemplateBuilderContext = computed(() => templateBuilderContext.value?.kind === "section");
const pageDesignOverridesLocked = computed(() =>
  Boolean(state.pageTemplateStyleLock) && !hasTemplateBuilderContext.value
);
const showGenericCssGrid = computed(() =>
  showConstantDesignControls.value &&
  (props.showSectionGeneric || !pageDesignOverridesLocked.value)
);
const genericCssGridSingle = computed(() =>
  !props.showSectionGeneric || pageDesignOverridesLocked.value
);

function isRenderableSlotNode(node) {
  if (!node) return false;
  if (node.type === Comment) return false;
  if (node.type === Text) return String(node.children || "").trim().length > 0;
  if (node.type === Fragment && Array.isArray(node.children)) {
    return node.children.some(isRenderableSlotNode);
  }
  return true;
}

function hasRenderableSlot(slotName) {
  const slot = slots[slotName];
  if (!slot) return false;
  return slot().some(isRenderableSlotNode);
}

function hasDesignParamsControls() {
  return hasRenderableSlot("design-params");
}

function hasDesignColorControls() {
  return hasRenderableSlot("design-colors");
}

function showLegacyDesignControls() {
  return !hasDesignParamsControls() && !hasDesignColorControls() && hasRenderableSlot("design");
}

function showTypeSpecificDesignControls() {
  return hasDesignParamsControls() || hasDesignColorControls() || showLegacyDesignControls();
}

const section = computed(() => {
  if (!props.sectionKey) return null;
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});

const notesInputId = computed(() => {
  const suffix = String(props.sectionKey || "section").replace(/[^a-zA-Z0-9_-]/g, "-");
  return `section-admin-notes-${suffix}`;
});

const sectionOverrides = computed(() => {
  if (!props.sectionKey) return null;
  return state.sectionDesignOverrides?.[props.sectionKey] || null;
});

const enabledConstantSectionParams = computed(() => {
  const params = state.adminDesignConfig?.sectionOverrideParams?.constants;
  if (!Array.isArray(params)) return DEFAULT_CONSTANT_SECTION_PARAMS;
  return params;
});

const showConstantDesignControls = computed(() => hasSectionContext.value);
const currentSectionId = computed(() => state.sectionIds?.[props.sectionKey] || "");
const currentSectionShared = computed(() => state.sectionMeta?.[props.sectionKey]?.shared === true);
const sectionSnippetContextKey = computed(() => buildSectionSnippetContextKey(currentSectionId.value));
const sectionSnippetContextTag = computed(() => {
  const slug = state.pageSlug || "landing";
  const title = section.value?.title;
  const label = typeof title === "string"
    ? title
    : (title?.de || title?.en || props.sectionKey || "section");
  return `${slug}/${String(label || "section").trim()}`;
});
const sectionEditorLabel = computed(() => {
  const explicitLabel = String(props.editorLabel || "").trim();
  if (explicitLabel) return explicitLabel;
  const title = section.value?.title;
  const localizedTitle = typeof title === "string"
    ? title
    : (title?.[state.lang] || title?.de || title?.en || "");
  const normalizedTitle = String(localizedTitle || "").trim();
  if (normalizedTitle) return normalizedTitle;
  const placeholder = String(state.sectionMeta?.[props.sectionKey]?.titlePlaceholder || "").trim();
  if (placeholder) return placeholder;
  const fallback = String(props.sectionKey || "").trim();
  return fallback || "section";
});
const pinnedEditors = computed(() => (
  Array.isArray(state.sectionAdminPinnedEditors)
    ? state.sectionAdminPinnedEditors
    : []
));
const resolvedActivePinnedEditorId = computed(() => {
  const activeId = String(state.sectionAdminPinnedActiveId || "").trim();
  if (activeId && pinnedEditors.value.some((entry) => entry.id === activeId)) return activeId;
  return pinnedEditors.value[0]?.id || "";
});
const pinnedSharedTab = computed(() => String(state.sectionAdminPinnedSharedTab || "").trim());
const currentRevisionStatus = computed(() => {
  if (!props.sectionKey) return null;
  return state.revisionStatus?.[props.sectionKey] || null;
});
const currentSectionSaveStatus = computed(() => {
  if (!props.sectionKey) return null;
  return state.sectionSaveStatus?.[props.sectionKey] || null;
});
const sectionAutosaveTone = computed(() => {
  if (props.autosaveMessage) return props.autosaveTone || "idle";
  return currentSectionSaveStatus.value?.status || "idle";
});
const sectionAutosaveMessage = computed(() => {
  if (props.autosaveMessage) return props.autosaveMessage;
  const status = currentSectionSaveStatus.value;
  if (!status) return "";
  if (status.status === "queued") return "Auto-save queued";
  if (status.status === "saving") return "Saving changes...";
  if (status.status === "saved") return "All changes saved";
  if (status.status === "error") return `Auto-save failed: ${status.error || "unknown error"}`;
  return "";
});
const currentRevisionSignature = computed(() => {
  const status = currentRevisionStatus.value;
  if (!status) return "";
  return [
    status.enabled === false ? "0" : "1",
    status.canUndo ? "1" : "0",
    status.canRedo ? "1" : "0",
    status.lastSavedAt || "",
    status.lastSavedBy || "",
  ].join("|");
});

const sectionHeaderHideState = computed(() => getSectionHideState("hideSectionHeader"));
const sectionDescriptionHideState = computed(() => getSectionHideState("hideSectionDescription"));
const normalizedCurrentSectionType = computed(() =>
  normalizeSectionType(
    section.value?.sectionType
    || state.sectionMeta?.[props.sectionKey]?.sectionType
    || state.sectionMeta?.[props.sectionKey]?.section_type
    || props.sectionKey
  )
);
const sectionTemplateSectionType = computed(() =>
  normalizeSectionType(
    section.value?.sectionType
    || state.sectionMeta?.[props.sectionKey]?.sectionType
    || state.sectionMeta?.[props.sectionKey]?.section_type
  )
);
const sectionTemplateName = computed(() => {
  const fromMeta = state.sectionMeta?.[props.sectionKey]?.sectionTemplateName
    || state.sectionMeta?.[props.sectionKey]?.section_template_name;
  const normalized = normalizeTemplateName(fromMeta);
  return normalized || "";
});
const sectionTemplateRef = computed(() => {
  const sectionType = sectionTemplateSectionType.value;
  const templateName = sectionTemplateName.value;
  if (!sectionType || !templateName) return "";
  return `${sectionType}/${templateName}`;
});
const showTemplateTab = computed(() => (
  hasAuxTabContext.value &&
  hasSectionContext.value &&
  !isSectionTemplateBuilderContext.value &&
  Boolean(sectionTemplateSectionType.value) &&
  Boolean(sectionTemplateName.value)
));
const showCustomTemplateTab = computed(() => (
  hasAuxTabContext.value &&
  !isSectionTemplateBuilderContext.value &&
  props.showTemplate
));
const showAnyTemplateTab = computed(() => showTemplateTab.value || showCustomTemplateTab.value);
const templateLinkTarget = computed(() => {
  const sectionType = sectionTemplateSectionType.value;
  const templateName = sectionTemplateName.value;
  if (!sectionType || !templateName) return "";
  return `/admin/templates/sections/${encodeURIComponent(sectionType)}/${encodeURIComponent(templateName)}`;
});
const templateChangedFields = computed(() => (
  Array.isArray(templatePreview.value?.changed_fields)
    ? templatePreview.value.changed_fields
      .map((field) => String(field || "").trim())
      .filter(Boolean)
    : []
));
const templateChangedFieldLabels = computed(() => (
  templateChangedFields.value.map((field) => TEMPLATE_SYNC_FIELD_LABELS[field] || field)
));
const supportsHeaderDescriptionHideControls = computed(() =>
  normalizedCurrentSectionType.value !== "ticker"
);
const supportsHideWhenListEmptyPublic = computed(() => {
  return LIST_SECTION_TYPES_WITH_GENERIC_EMPTY_TOGGLE.has(normalizedCurrentSectionType.value);
});
const supportsShowWhenVideoEmptyPublic = computed(() => {
  return VIDEO_SECTION_TYPES_WITH_GENERIC_EMPTY_TOGGLE.has(normalizedCurrentSectionType.value);
});
const supportsSectionCtaButtonAlignment = computed(() => {
  const normalized = normalizedCurrentSectionType.value;
  if (normalized === "ticker") return false;
  const sectionKey = String(props.sectionKey || "").trim().toLowerCase();
  if (sectionKey === "ticker" || sectionKey.startsWith("ticker_")) return false;
  return true;
});
const sectionCtaButtonAlignment = computed(() =>
  normalizeSectionCtaButtonAlignment(section.value?.sectionGeneric?.buttonAlignment)
);
const isHideWhenListEmptyPublicEnabled = computed(() =>
  isSectionGenericEnabled(LIST_EMPTY_PUBLIC_GENERIC_KEY)
);
const isShowWhenVideoEmptyPublicEnabled = computed(() =>
  isSectionGenericEnabled(SHOW_VIDEO_EMPTY_PUBLIC_GENERIC_KEY)
);

const isSectionPaddingRemoved = computed(() => {
  if (isSectionGenericEnabled("removeSectionPadding")) return true;
  const ov = sectionOverrides.value;
  if (!ov || ov.sectionPadding == null) return false;
  return Number(ov.sectionPadding) === 0;
});

const isSectionBackgroundRemoved = computed(() => {
  if (isSectionGenericEnabled("removeSectionBackground")) return true;
  const ov = sectionOverrides.value;
  if (!ov || ov.sectionBackgroundColor == null) return false;
  return String(ov.sectionBackgroundColor).trim().toLowerCase() === "transparent";
});

const openTodos = computed(() => todoDraft.value.filter((todo) => !todo.done));
const doneTodos = computed(() => todoDraft.value.filter((todo) => todo.done));
const openTodoCount = computed(() => openTodos.value.length);
const currentEditorName = computed(() => {
  const user = getUser?.();
  return user?.name || user?.username || "unknown";
});

function normalizeParamDiffs(value) {
  if (!Array.isArray(value)) return [];
  const cleaned = value
    .map((item) => String(item || "").trim())
    .filter(Boolean);
  return Array.from(new Set(cleaned));
}

function toCamelCase(value) {
  return String(value || "")
    .replace(/[_\s]+([a-zA-Z0-9])/g, (_, char) => char.toUpperCase())
    .replace(/^[A-Z]/, (char) => char.toLowerCase());
}

function applyParamDiffContext(items, kind) {
  const normalized = normalizeParamDiffs(items);
  if (kind !== "design") {
    return normalized
      .map((label) =>
        String(label || "").replace(/^content:\s*/i, "").trim()
      )
      .filter(Boolean);
  }
  const context = "Design";
  return normalized.map((label) => {
    const text = String(label || "").trim();
    if (!text) return text;
    if (text.includes(":")) return text;
    return `${context}: ${text}`;
  });
}

function inferSnapshotFallbackDiff(entry, kind) {
  const context = kind === "design" ? "Design" : "";
  const snapshot = kind === "design"
    ? entry?.design_snapshot
    : entry?.content_snapshot;
  if (snapshot && typeof snapshot === "object") {
    if (kind === "design" && Object.prototype.hasOwnProperty.call(snapshot, "design_overrides")) {
      const overrides = snapshot.design_overrides;
      if (overrides && typeof overrides === "object") {
        const firstKey = Object.keys(overrides).find((key) => String(key || "").trim().length > 0);
        if (firstKey) return `Override: ${toCamelCase(String(firstKey))}`;
      }
      return "Override: designOverrides";
    }
    const firstKey = Object.keys(snapshot).find((key) => String(key || "").trim().length > 0);
    if (firstKey) {
      const param = toCamelCase(String(firstKey));
      return context ? `${context}: ${param}` : param;
    }
  }
  return context ? `${context}: unknown` : "unknown";
}

function entryParamDiffs(entry, kind) {
  const scopedRaw =
    kind === "design"
      ? normalizeParamDiffs(entry?.design_param_diffs)
      : normalizeParamDiffs(entry?.content_param_diffs);
  const scoped = applyParamDiffContext(scopedRaw, kind);
  if (scoped.length > 0) return scoped;
  const fallback = applyParamDiffContext(entry?.param_diffs, kind);
  if (fallback.length > 0) return fallback;
  if (entry?.change_kind === kind || entry?.change_kind === "both") {
    return [inferSnapshotFallbackDiff(entry, kind)];
  }
  return [];
}

function summarizeParamDiffs(items) {
  const diffs = normalizeParamDiffs(items);
  if (diffs.length === 0) return "";
  const preview = diffs.slice(0, 3).join(", ");
  return diffs.length > 3 ? `${preview} +${diffs.length - 3} more` : preview;
}

const revisionEntries = computed(() => {
  const current = [];
  if (historyCurrent.value) {
    if (historyCurrent.value.has_design !== false) {
      current.push({
        key: "current-design",
        source: "current",
        index: 0,
        steps: 0,
        savedAt: historyCurrent.value.design_saved_at ?? null,
        savedBy: historyCurrent.value.design_saved_by || "unknown",
        hasDesign: true,
        hasContent: false,
        designChanged: false,
        contentChanged: false,
        designSnapshot: historyCurrent.value.design_snapshot || null,
        contentSnapshot: null,
        changeKind: "design",
        designParamDiffs: entryParamDiffs(
          {
            design_param_diffs: historyCurrent.value.design_param_diffs,
            content_param_diffs: [],
            param_diffs: historyCurrent.value.param_diffs,
            change_kind: "design",
            design_snapshot: historyCurrent.value.design_snapshot || null,
          },
          "design"
        ),
        contentParamDiffs: [],
      });
    }
    if (historyCurrent.value.has_content !== false) {
      current.push({
        key: "current-content",
        source: "current",
        index: 0,
        steps: 0,
        savedAt: historyCurrent.value.content_saved_at ?? null,
        savedBy: historyCurrent.value.content_saved_by || "unknown",
        hasDesign: false,
        hasContent: true,
        designChanged: false,
        contentChanged: false,
        designSnapshot: null,
        contentSnapshot: historyCurrent.value.content_snapshot || null,
        changeKind: "content",
        designParamDiffs: [],
        contentParamDiffs: entryParamDiffs(
          {
            design_param_diffs: [],
            content_param_diffs: historyCurrent.value.content_param_diffs,
            param_diffs: historyCurrent.value.param_diffs,
            change_kind: "content",
            content_snapshot: historyCurrent.value.content_snapshot || null,
          },
          "content"
        ),
      });
    }
  }

  const historyItems = historyStack.value.map((entry, index) => ({
    key: `history-${index}`,
    source: "history",
    index,
    steps: index + 1,
    savedAt: entry.saved_at || null,
    savedBy: entry.saved_by || "unknown",
    hasDesign: Boolean(entry.has_design),
    hasContent: Boolean(entry.has_content),
    designChanged: Boolean(entry.design_changed),
    contentChanged: Boolean(entry.content_changed),
    designSnapshot: entry.design_snapshot || null,
    contentSnapshot: entry.content_snapshot || null,
    changeKind: entry.change_kind || null,
    designParamDiffs: entryParamDiffs(entry, "design"),
    contentParamDiffs: entryParamDiffs(entry, "content"),
  }));

  const futureItems = futureStack.value.map((entry, index) => ({
    key: `future-${index}`,
    source: "future",
    index,
    steps: index + 1,
    savedAt: entry.saved_at || null,
    savedBy: entry.saved_by || "unknown",
    hasDesign: Boolean(entry.has_design),
    hasContent: Boolean(entry.has_content),
    designChanged: Boolean(entry.design_changed),
    contentChanged: Boolean(entry.content_changed),
    designSnapshot: entry.design_snapshot || null,
    contentSnapshot: entry.content_snapshot || null,
    changeKind: entry.change_kind || null,
    designParamDiffs: entryParamDiffs(entry, "design"),
    contentParamDiffs: entryParamDiffs(entry, "content"),
  }));

  const orderedHistory = [...historyItems, ...futureItems].sort((left, right) => {
    const leftTs = getRevisionTimestampMs(left.savedAt);
    const rightTs = getRevisionTimestampMs(right.savedAt);
    return rightTs - leftTs;
  });

  return [...current, ...orderedHistory];
});

const designHistoryEntries = computed(() =>
  revisionEntries.value
    .filter((entry) =>
      entry.key === "current-design" ||
      entry.changeKind === "design" ||
      entry.changeKind === "both"
    )
    .slice(0, 5)
);

const contentHistoryEntries = computed(() =>
  revisionEntries.value
    .filter((entry) =>
      entry.key === "current-content" ||
      entry.changeKind === "content" ||
      entry.changeKind === "both"
    )
    .slice(0, 5)
);

const showDesignHistory = computed(() => Boolean(historyOptions.value.includeDesign));
const showContentHistory = computed(() => Boolean(historyOptions.value.includeContent));

const selectedDesignRevisionEntry = computed(() =>
  revisionEntries.value.find((entry) => entry.key === selectedDesignRevisionKey.value) || null
);

const selectedContentRevisionEntry = computed(() =>
  revisionEntries.value.find((entry) => entry.key === selectedContentRevisionKey.value) || null
);

const canRevertDesign = computed(() => {
  const entry = selectedDesignRevisionEntry.value;
  if (!entry) return false;
  return entry.source !== "current";
});

const canRevertContent = computed(() => {
  const entry = selectedContentRevisionEntry.value;
  if (!entry) return false;
  return entry.source !== "current";
});

function normalizeTodos(todos) {
  return normalizeTodoList(todos, { defaultTagId: defaultTodoTagId.value });
}

const todoPrioritySelectOptions = TODO_PRIORITY_VALUES.map((priority) => todoPrioritySelectOption(priority));

const defaultTodoTagId = computed(() => {
  if (todoTagOptions.value.some((tag) => tag.id === "text")) return "text";
  return todoTagOptions.value[0]?.id || DEFAULT_TODO_TAG_ID;
});

const todoTagSelectOptions = computed(() =>
  todoTagOptions.value.map((tag) => todoTagSelectOption(tag.id))
);

const todoTagAreaMap = computed(() => {
  const map = {};
  for (const tag of todoTagOptions.value) {
    map[tag.id] = tag.area;
  }
  return map;
});

const tabs = computed(() => {
  const list = [];
  if (props.showDesign) list.push({ key: "design", label: props.designLabel });
  if (props.showContent) list.push({ key: "content", label: props.contentLabel });
  if (props.showHistory && hasAuxTabContext.value) list.push({ key: "history", label: props.historyLabel });
  if (props.showOutput) list.push({ key: "output", label: props.outputLabel });
  if (showAnyTemplateTab.value) list.push({ key: "template", label: props.templateLabel });
  if (props.showNotes && hasAuxTabContext.value) {
    const count = openTodoCount.value;
    const label = count > 0 ? `${props.notesLabel} (${count})` : props.notesLabel;
    list.push({ key: "notes", label });
  }
  return list;
});

const localActive = ref("");
const hasInitializedActive = ref(false);
const anchorEl = ref(null);
const bodyEl = ref(null);
const teleportHost = ref(null);
const teleportHostIsDynamic = ref(false);
const globalTeleportHost = ref(null);
const shouldTeleport = ref(false);
const isEditorPinned = ref(false);
const pinnedBodyHeightPx = computed({
  get: () => {
    const value = state.sectionAdminPinnedSharedHeightPx;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  },
  set: (next) => {
    setSectionAdminPinnedSharedHeightPx(next);
  },
});
const pinnedChromeHeightPx = ref(0);
let pinnedResizeSession = null;
const teleportTarget = computed(() => {
  if (isEditorPinned.value && globalTeleportHost.value) return globalTeleportHost.value;
  if (!shouldTeleport.value) return null;
  return teleportHost.value || null;
});
const isTeleportEnabled = computed(() => Boolean(teleportTarget.value));
const pinnedContainerStyle = computed(() => {
  if (!isEditorPinned.value) return {};
  return {
    "--section-admin-tabs-pinned-body-height": pinnedBodyHeightPx.value != null
      ? `${Math.round(pinnedBodyHeightPx.value)}px`
      : "20vh",
    "--section-admin-tabs-pinned-min-height": `${Math.max(0, Math.round(pinnedChromeHeightPx.value || 0))}px`,
  };
});
const isPinnedInstanceActive = computed(() => {
  if (!isEditorPinned.value) return true;
  if (pinnedEditors.value.length <= 1) return true;
  return resolvedActivePinnedEditorId.value === instanceId;
});
const showPinnedEditorSwitcher = computed(() => (
  isEditorPinned.value &&
  isPinnedInstanceActive.value &&
  pinnedEditors.value.length > 1
));

function setupTeleportHost() {
  const anchor = anchorEl.value;
  if (!anchor) return;

  const contentHost = anchor.closest(".grid-item-content");
  if (contentHost) {
    const sectionKey = String(contentHost.getAttribute("data-section-key") || props.sectionKey || "").trim();
    let host = contentHost.previousElementSibling;
    if (!(host instanceof HTMLElement) || !host.classList.contains("section-admin-tabs-host")) {
      host = null;
    }

    if (!host && contentHost.parentElement && sectionKey) {
      host = Array.from(contentHost.parentElement.children).find((el) =>
        el instanceof HTMLElement
        && el.classList.contains("section-admin-tabs-host")
        && String(el.getAttribute("data-section-key") || "").trim() === sectionKey
      ) || null;
    }

    if (!host) {
      host = document.createElement("div");
      host.className = "section-admin-tabs-host";
      host.setAttribute("data-dynamic-host", "true");
      if (sectionKey) host.setAttribute("data-section-key", sectionKey);
    }

    if (contentHost.parentElement && contentHost.previousElementSibling !== host) {
      contentHost.parentElement.insertBefore(host, contentHost);
    }

    teleportHostIsDynamic.value = host.getAttribute("data-dynamic-host") === "true";
    teleportHost.value = host;
    shouldTeleport.value = true;
    return;
  }

  const hostParent = anchor.closest(".hero-pinned-ticker, .hero-editor-tabs-wrap") || anchor.closest(".grid-item");
  if (!hostParent) {
    shouldTeleport.value = false;
    teleportHost.value = null;
    teleportHostIsDynamic.value = false;
    return;
  }

  let host = hostParent.querySelector(":scope > .section-admin-tabs-host");
  if (!host) {
    host = document.createElement("div");
    host.className = "section-admin-tabs-host";
    host.setAttribute("data-dynamic-host", "true");
    hostParent.insertBefore(host, hostParent.firstChild || null);
  }
  teleportHostIsDynamic.value = host.getAttribute("data-dynamic-host") === "true";
  teleportHost.value = host;
  shouldTeleport.value = true;
}

function setupGlobalTeleportHost() {
  if (typeof document === "undefined") return;
  let host = document.getElementById("section-admin-tabs-global-host");
  if (!host) {
    host = document.createElement("div");
    host.id = "section-admin-tabs-global-host";
    document.body.appendChild(host);
  }
  globalTeleportHost.value = host;
}

function measurePinnedChromeHeight() {
  if (!isEditorPinned.value || !isPinnedInstanceActive.value) return;
  const body = bodyEl.value;
  const container = body?.closest(".section-admin-tabs");
  if (!body || !container) return;
  const containerRect = container.getBoundingClientRect();
  const bodyRect = body.getBoundingClientRect();
  const chromeHeight = Math.max(0, bodyRect.top - containerRect.top);
  pinnedChromeHeightPx.value = Math.round(chromeHeight);
}

function clampPinnedHeight(heightPx) {
  const minHeight = 0;
  const maxHeight = typeof window !== "undefined"
    ? Math.max(minHeight, Math.round(window.innerHeight * 0.85))
    : 720;
  return Math.min(maxHeight, Math.max(minHeight, Math.round(heightPx)));
}

function syncPinnedHeightToViewport() {
  measurePinnedChromeHeight();
  if (pinnedBodyHeightPx.value == null) return;
  pinnedBodyHeightPx.value = clampPinnedHeight(pinnedBodyHeightPx.value);
}

function cleanupPinnedResizeState() {
  window.removeEventListener("pointermove", onPinnedResizeMove);
  window.removeEventListener("pointerup", stopPinnedResize);
  window.removeEventListener("pointercancel", stopPinnedResize);
  pinnedResizeSession = null;
  if (typeof document !== "undefined" && document.body) {
    document.body.style.userSelect = "";
    document.body.style.cursor = "";
  }
}

function onPinnedResizeMove(event) {
  if (!pinnedResizeSession) return;
  event.preventDefault();
  const deltaY = event.clientY - pinnedResizeSession.startY;
  const nextHeight = pinnedResizeSession.startHeight - deltaY;
  pinnedBodyHeightPx.value = clampPinnedHeight(nextHeight);
}

function stopPinnedResize() {
  if (!pinnedResizeSession) return;
  cleanupPinnedResizeState();
}

function startPinnedResize(event) {
  if (!isEditorPinned.value || !isPinnedInstanceActive.value) return;
  if (event.button != null && event.button !== 0) return;
  event.preventDefault();
  const currentHeight = bodyEl.value?.getBoundingClientRect().height ?? clampPinnedHeight(window.innerHeight * 0.2);
  pinnedBodyHeightPx.value = clampPinnedHeight(currentHeight);
  pinnedResizeSession = {
    startY: event.clientY,
    startHeight: pinnedBodyHeightPx.value,
  };
  window.addEventListener("pointermove", onPinnedResizeMove);
  window.addEventListener("pointerup", stopPinnedResize);
  window.addEventListener("pointercancel", stopPinnedResize);
  if (typeof document !== "undefined" && document.body) {
    document.body.style.userSelect = "none";
    document.body.style.cursor = "ns-resize";
  }
}

function resetPinnedHeight() {
  pinnedBodyHeightPx.value = null;
  syncPinnedHeightToViewport();
}

function onPinAllSectionEditorsRequest() {
  if (!props.visible || tabs.value.length === 0) return;
  if (!isEditorPinned.value) isEditorPinned.value = true;
}

function pinAllSectionEditors() {
  window.dispatchEvent(new CustomEvent("fstvlpress:pin-all-section-editors"));
}

function onReleaseAllSectionEditorsRequest() {
  if (isEditorPinned.value) isEditorPinned.value = false;
}

function releaseAllSectionEditors() {
  window.dispatchEvent(new CustomEvent("fstvlpress:release-all-section-editors"));
}

function resolvePinnedTabPreference(preferredTab = "") {
  const allowed = tabs.value.map((tab) => tab.key);
  const preferred = String(preferredTab || "").trim();
  if (preferred && allowed.includes(preferred)) return preferred;
  const current = String(active.value || "").trim();
  if (current && allowed.includes(current)) return current;
  return allowed[0] || "";
}

function toggleEditorPinned() {
  const shouldPin = !isEditorPinned.value;
  if (shouldPin) {
    const desired = resolvePinnedTabPreference(pinnedSharedTab.value);
    if (desired && localActive.value !== desired) {
      localActive.value = desired;
      emit("update:activeTab", desired);
      emit("tab-change", desired);
    }
    if (desired) setSectionAdminPinnedSharedTab(desired);
  }
  isEditorPinned.value = shouldPin;
}

function selectPinnedEditor(editorId) {
  const desired = resolvePinnedTabPreference(pinnedSharedTab.value);
  if (desired) setSectionAdminPinnedSharedTab(desired);
  setSectionAdminPinnedActiveEditor(editorId);
}

function firstTab() {
  return tabs.value[0]?.key || "";
}

function getTabIcon(tabKey) {
  if (tabKey === "design") return faPaintbrush;
  if (tabKey === "content") return faFileLines;
  if (tabKey === "output") return faFileLines;
  if (tabKey === "history") return faClock;
  if (tabKey === "template") return faFileLines;
  if (tabKey === "notes") return faPenToSquare;
  return faFileLines;
}

watch(
  [() => props.activeTab, () => route.query.sectionEditorTab, tabs, shouldTeleport],
  (_, prevValues) => {
    const routeRequestedTab = String(route.query.sectionEditorTab || "").trim();
    const requested = routeRequestedTab || props.activeTab;
    const allowed = tabs.value.map((t) => t.key);
    const startCollapsed = props.startCollapsed || shouldTeleport.value;
    const hasRouteTabRequest = Boolean(routeRequestedTab && allowed.includes(routeRequestedTab));
    if (!hasInitializedActive.value && startCollapsed && props.allowCollapse && !hasRouteTabRequest) {
      localActive.value = "";
      if (requested && allowed.includes(requested)) {
        // Ensure parent v-model doesn't re-open a default tab on first render.
        emit("update:activeTab", "");
      }
      hasInitializedActive.value = true;
      return;
    }
    if (requested === "" && props.allowCollapse) {
      if (!hasInitializedActive.value) {
        localActive.value = startCollapsed ? "" : firstTab();
      } else {
        const prevRequested = Array.isArray(prevValues) ? String(prevValues[0] || prevValues[1] || "") : "";
        const requestedChanged = prevRequested !== requested;
        const activeBecameInvalid = Boolean(localActive.value) && !allowed.includes(localActive.value);
        if (requestedChanged || activeBecameInvalid) {
          localActive.value = activeBecameInvalid
            ? (startCollapsed ? "" : firstTab())
            : "";
        }
      }
    } else if (requested && allowed.includes(requested)) {
      localActive.value = requested;
    } else if (localActive.value && !allowed.includes(localActive.value)) {
      localActive.value = startCollapsed && props.allowCollapse ? "" : firstTab();
    } else if (!localActive.value && !props.allowCollapse) {
      localActive.value = firstTab();
    }
    hasInitializedActive.value = true;
  },
  { immediate: true }
);

onMounted(() => {
  setupGlobalTeleportHost();
  window.addEventListener("fstvlpress:pin-all-section-editors", onPinAllSectionEditorsRequest);
  window.addEventListener("fstvlpress:release-all-section-editors", onReleaseAllSectionEditorsRequest);
  nextTick(() => {
    setupTeleportHost();
  });
  loadTodoTagOptions();
});

watch(
  () => state.canAdminGeneral,
  (canAdminGeneral, wasAdminGeneral) => {
    if (canAdminGeneral && !wasAdminGeneral) {
      loadTodoTagOptions();
    }
  }
);

const active = computed(() => {
  if (isEditorPinned.value) return localActive.value || firstTab();
  if (!localActive.value && props.allowCollapse) return "";
  return localActive.value || firstTab();
});

watch(
  [active, () => props.sectionKey],
  ([tab, sectionKey], prevValues) => {
    const prevSectionKey = Array.isArray(prevValues) ? prevValues[1] : "";
    if (prevSectionKey && prevSectionKey !== sectionKey) {
      setSectionAdminActiveTab(prevSectionKey, "");
    }
    if (sectionKey) {
      setSectionAdminActiveTab(sectionKey, tab || "");
    }
  },
  { immediate: true }
);

function setTab(tab) {
  if (tab === active.value && isEditorPinned.value) return;
  if (tab === active.value && props.allowCollapse) {
    localActive.value = "";
    emit("update:activeTab", "");
    emit("tab-change", "");
    return;
  }
  if (tab === active.value) return;
  localActive.value = tab;
  emit("update:activeTab", tab);
  emit("tab-change", tab);
  if (isEditorPinned.value) setSectionAdminPinnedSharedTab(tab);
}

const TAB_BODY_TRANSITION = "height 220ms ease";

function clearBodyTransitionStyles(el) {
  el.classList.remove("is-collapsing");
  el.style.height = "";
  el.style.overflow = "";
  el.style.transition = "";
}

function onBodyBeforeEnter(el) {
  if (isEditorPinned.value) {
    clearBodyTransitionStyles(el);
    return;
  }
  el.classList.remove("is-collapsing");
  el.style.height = "0px";
  el.style.overflow = "hidden";
  el.style.transition = TAB_BODY_TRANSITION;
}

function onBodyEnter(el) {
  if (isEditorPinned.value) return;
  const targetHeight = `${el.scrollHeight}px`;
  requestAnimationFrame(() => {
    el.style.height = targetHeight;
  });
}

function onBodyAfterEnter(el) {
  if (isEditorPinned.value) {
    clearBodyTransitionStyles(el);
    return;
  }
  el.style.height = "auto";
  el.style.overflow = "visible";
  el.style.transition = "";
}

function onBodyBeforeLeave(el) {
  if (isEditorPinned.value) {
    clearBodyTransitionStyles(el);
    return;
  }
  el.classList.add("is-collapsing");
  el.style.height = `${el.scrollHeight}px`;
  el.style.overflow = "hidden";
  el.style.transition = TAB_BODY_TRANSITION;
}

function onBodyLeave(el) {
  if (isEditorPinned.value) return;
  requestAnimationFrame(() => {
    el.style.height = "0px";
  });
}

function onBodyAfterLeave(el) {
  clearBodyTransitionStyles(el);
}

watch(
  isEditorPinned,
  async (pinned) => {
    const entry = {
      id: instanceId,
      sectionKey: props.sectionKey,
      label: sectionEditorLabel.value,
    };
    if (pinned) {
      const desired = resolvePinnedTabPreference(pinnedSharedTab.value);
      if (desired && localActive.value !== desired) {
        localActive.value = desired;
        emit("update:activeTab", desired);
        emit("tab-change", desired);
      }
      if (desired) setSectionAdminPinnedSharedTab(desired);
      if (bodyEl.value) clearBodyTransitionStyles(bodyEl.value);
      upsertSectionAdminPinnedEditor(entry, { activate: true });
      window.addEventListener("resize", syncPinnedHeightToViewport);
      await nextTick();
      syncPinnedHeightToViewport();
      return;
    }
    removeSectionAdminPinnedEditor(instanceId);
    stopPinnedResize();
    window.removeEventListener("resize", syncPinnedHeightToViewport);
    pinnedChromeHeightPx.value = 0;
    if (bodyEl.value) {
      clearBodyTransitionStyles(bodyEl.value);
    }
  }
);

watch(
  [isEditorPinned, isPinnedInstanceActive, pinnedSharedTab, tabs, showPinnedEditorSwitcher],
  async ([pinned, pinnedActive, sharedTab]) => {
    if (!pinned || !pinnedActive) return;
    const desired = resolvePinnedTabPreference(sharedTab);
    if (!desired) return;
    if (localActive.value !== desired) {
      localActive.value = desired;
      emit("update:activeTab", desired);
      emit("tab-change", desired);
    }
    if (sharedTab !== desired) setSectionAdminPinnedSharedTab(desired);
    await nextTick();
    syncPinnedHeightToViewport();
  },
  { immediate: true }
);

watch(
  [isEditorPinned, sectionEditorLabel, () => props.sectionKey],
  ([pinned]) => {
    if (!pinned) return;
    upsertSectionAdminPinnedEditor(
      {
        id: instanceId,
        sectionKey: props.sectionKey,
        label: sectionEditorLabel.value,
      },
      { activate: false }
    );
  }
);

watch(
  section,
  (value) => {
    const source = value || {};
    notesDraft.value = String(
      source.adminNotes ??
      source.type_data?.admin_notes ??
      ""
    );
    todoDraft.value = normalizeTodos(
      source.adminTodos ??
      source.type_data?.admin_todos ??
      []
    );
  },
  { immediate: true, deep: true }
);

watch(
  defaultTodoTagId,
  (tagId) => {
    if (!todoTagOptions.value.some((tag) => tag.id === newTodoTag.value)) {
      newTodoTag.value = tagId;
    }
    todoDraft.value = normalizeTodoList(todoDraft.value, { defaultTagId: tagId });
  },
  { immediate: true }
);

watch(
  () => [props.sectionKey, state.sectionCustomCssDrafts],
  () => {
    const sectionKey = String(props.sectionKey || "");
    sectionCustomCssDraft.value = sectionKey
      ? String(state.sectionCustomCssDrafts?.[sectionKey] ?? "")
      : "";
  },
  { immediate: true, deep: true }
);

watch(
  [customCssOpen, sectionSnippetContextKey, sectionSnippetContextTag],
  ([open]) => {
    if (open) loadSectionCssSnippets();
  }
);

watch(
  [active, currentSectionId, () => props.sectionKey],
  ([tab], prevValues) => {
    const prevTab = Array.isArray(prevValues) ? prevValues[0] : "";
    if (tab === "history" && props.sectionKey) {
      loadSectionHistory();
    } else if (prevTab === "history") {
      resetHistorySelectionAndPreview();
    }
  },
  { immediate: true }
);

watch(
  () => currentRevisionSignature.value,
  async (next, prev) => {
    if (!next || next === prev) return;
    if (active.value !== "history" || !props.sectionKey || !currentSectionId.value) return;
    if (historyLoading.value) return;
    await loadSectionHistory();
  }
);

function resetTemplateSyncState() {
  templatePreviewLoading.value = false;
  templatePreviewError.value = "";
  templatePreview.value = null;
  templateSyncing.value = false;
  templateSyncError.value = "";
  templateSyncMessage.value = "";
}

function setSectionSharedLocal(sectionKey, shared) {
  if (!sectionKey) return;
  if (!state.sectionMeta || typeof state.sectionMeta !== "object") {
    state.sectionMeta = {};
  }
  const currentMeta = state.sectionMeta?.[sectionKey] && typeof state.sectionMeta[sectionKey] === "object"
    ? state.sectionMeta[sectionKey]
    : {};
  state.sectionMeta[sectionKey] = {
    ...currentMeta,
    shared: shared === true,
  };
}

async function toggleSectionShared(event) {
  const nextShared = event?.target?.checked === true;
  if (!currentSectionId.value || !props.sectionKey || sectionSharingSaving.value) return;
  const previousShared = currentSectionShared.value === true;
  if (previousShared === nextShared) return;

  sectionSharingSaving.value = true;
  sectionSharingError.value = "";
  setSectionSharedLocal(props.sectionKey, nextShared);
  try {
    const updated = await api.updateSection(currentSectionId.value, { shared: nextShared });
    if (Object.prototype.hasOwnProperty.call(updated || {}, "shared")) {
      setSectionSharedLocal(props.sectionKey, updated.shared === true);
    }
  } catch (err) {
    setSectionSharedLocal(props.sectionKey, previousShared);
    sectionSharingError.value = err instanceof Error
      ? (err.message || "Failed to update section sharing.")
      : "Failed to update section sharing.";
  } finally {
    sectionSharingSaving.value = false;
  }
}

async function loadTemplateSyncPreview() {
  if (!showTemplateTab.value || !currentSectionId.value) {
    templatePreview.value = null;
    templatePreviewError.value = "Template sync is not available for this section.";
    return;
  }

  templatePreviewLoading.value = true;
  templatePreviewError.value = "";
  templateSyncMessage.value = "";
  try {
    const response = await api.getSectionTemplateSyncPreview(currentSectionId.value);
    templatePreview.value = response && typeof response === "object" ? response : null;
  } catch (err) {
    templatePreview.value = null;
    templatePreviewError.value = err instanceof Error
      ? (err.message || "Failed to compare section with template.")
      : "Failed to compare section with template.";
  } finally {
    templatePreviewLoading.value = false;
  }
}

function openSectionTemplate() {
  const target = String(templateLinkTarget.value || "").trim();
  if (!target) return;
  router.push(target);
}

async function syncTemplateChanges() {
  if (!showTemplateTab.value || !currentSectionId.value || !props.sectionKey) return;

  templateSyncing.value = true;
  templateSyncError.value = "";
  templateSyncMessage.value = "";
  try {
    const response = await api.syncSectionFromTemplate(currentSectionId.value);
    const changedFields = Array.isArray(response?.changed_fields)
      ? response.changed_fields
      : [];
    const updatedSection = response?.section && typeof response.section === "object"
      ? response.section
      : null;
    if (updatedSection) {
      applyBackendSectionByKey(props.sectionKey, updatedSection);
    }
    if (String(updatedSection?.section_type || "").trim().toLowerCase() === "faq") {
      await fetchFaqSharedData();
    } else if (String(updatedSection?.section_type || "").trim().toLowerCase() === "blog") {
      await fetchBlogData();
    } else if (String(updatedSection?.section_type || "").trim().toLowerCase() === "program") {
      await fetchProgramSharedData();
    }
    await refreshRevisionStatus(props.sectionKey);
    await loadTemplateSyncPreview();
    if (response?.updated === false || changedFields.length === 0) {
      templateSyncMessage.value = "No template changes were pending.";
    } else {
      templateSyncMessage.value = "Template changes synced to this section.";
    }
  } catch (err) {
    templateSyncError.value = err instanceof Error
      ? (err.message || "Failed to sync template changes.")
      : "Failed to sync template changes.";
  } finally {
    templateSyncing.value = false;
  }
}

watch(
  [active, currentSectionId, () => props.sectionKey, showTemplateTab],
  ([tab, sectionId, sectionKey, isTemplateTabVisible], prevValues) => {
    const prevTab = Array.isArray(prevValues) ? prevValues[0] : "";
    const prevSectionId = Array.isArray(prevValues) ? prevValues[1] : "";
    const prevSectionKey = Array.isArray(prevValues) ? prevValues[2] : "";
    if (!isTemplateTabVisible) {
      if (templatePreview.value || templatePreviewError.value || templateSyncError.value || templateSyncMessage.value) {
        resetTemplateSyncState();
      }
      sectionSharingError.value = "";
      return;
    }
    const sectionChanged = prevSectionId !== sectionId || prevSectionKey !== sectionKey;
    if (sectionChanged) {
      resetTemplateSyncState();
      sectionSharingError.value = "";
    }
    if (tab === "template") {
      const hasPreview = templatePreview.value && typeof templatePreview.value === "object";
      if (!hasPreview || sectionChanged || prevTab !== "template") {
        loadTemplateSyncPreview();
      }
    } else if (prevTab === "template") {
      templateSyncError.value = "";
      templateSyncMessage.value = "";
      sectionSharingError.value = "";
    }
  },
  { immediate: true }
);

function persistNotes() {
  if (!props.sectionKey) return;
  updateSection(props.sectionKey, {
    adminNotes: notesDraft.value,
    adminTodos: serializeTodoList(todoDraft.value),
  });
}

function addTodo() {
  const text = newTodo.value.trim();
  if (!text) return;
  todoDraft.value = [
    ...todoDraft.value,
    {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      text,
      done: false,
      createdBy: currentEditorName.value,
      createdAt: new Date().toISOString(),
      resolvedBy: null,
      resolvedAt: null,
      tag: newTodoTag.value || defaultTodoTagId.value,
      priority: newTodoPriority.value,
      priorityRank: null,
    },
  ];
  newTodo.value = "";
  newTodoTag.value = defaultTodoTagId.value;
  newTodoPriority.value = DEFAULT_TODO_PRIORITY;
  persistNotes();
}

function toggleTodo(id, done) {
  todoDraft.value = todoDraft.value.map((todo) =>
    todo.id === id
      ? {
        ...todo,
        done: Boolean(done),
        resolvedBy: done ? currentEditorName.value : null,
        resolvedAt: done ? new Date().toISOString() : null,
      }
      : todo
  );
  persistNotes();
}

function removeTodo(id) {
  todoDraft.value = todoDraft.value.filter((todo) => todo.id !== id);
  persistNotes();
}

function todoAuthorName(todo) {
  if (todo?.done && todo?.resolvedBy) return todo.resolvedBy;
  return todo?.createdBy || "unknown";
}

function todoAuthorTime(todo) {
  if (todo?.done && todo?.resolvedAt) return todo.resolvedAt;
  return todo?.createdAt || null;
}

function todoTagArea(tagId) {
  return todoTagAreaMap.value[tagId] || "content";
}

async function loadTodoTagOptions() {
  if (!state.canAdminGeneral) {
    todoTagOptions.value = normalizeTodoTags([]);
    return;
  }
  try {
    const config = await api.getAdminDevopsConfig();
    todoTagOptions.value = normalizeTodoTags(config?.todo_tags || []);
  } catch (err) {
    console.error("Failed to load todo tags:", err);
    todoTagOptions.value = normalizeTodoTags([]);
  }
}

function isConstantParamEnabled(paramKey) {
  return enabledConstantSectionParams.value.includes(paramKey);
}

function normalizeSectionType(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/-/g, "_");
}

function normalizeTemplateName(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return normalized || "default";
}

function isSectionGenericEnabled(constantKey) {
  const generic = section.value?.sectionGeneric;
  return Boolean(generic && typeof generic === "object" && generic[constantKey] === true);
}

function normalizeSectionCtaButtonAlignment(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "left" || normalized === "right") return normalized;
  return CTA_BUTTON_ALIGNMENT_DEFAULT;
}

function onSectionCtaButtonAlignmentChange(rawValue) {
  if (!props.sectionKey) return;
  if (!supportsSectionCtaButtonAlignment.value) return;

  const nextAlignment = normalizeSectionCtaButtonAlignment(rawValue);
  const source = section.value?.sectionGeneric;
  const nextGeneric = {
    ...(source && typeof source === "object" ? source : {}),
  };
  if (nextAlignment === CTA_BUTTON_ALIGNMENT_DEFAULT) {
    delete nextGeneric.buttonAlignment;
  } else {
    nextGeneric.buttonAlignment = nextAlignment;
  }
  updateSection(props.sectionKey, { sectionGeneric: nextGeneric }, { revisionKind: "design" });
}

function getHideStateHardKey(constantKey) {
  return HIDE_STATE_HARD_KEY_BY_CONSTANT[constantKey] || "";
}

function getSectionHideState(constantKey) {
  const hardKey = getHideStateHardKey(constantKey);
  if (hardKey && isSectionGenericEnabled(hardKey)) return HIDE_STATE_HARD;
  if (isSectionGenericEnabled(constantKey)) return HIDE_STATE_MUTED;
  return HIDE_STATE_VISIBLE;
}

async function onHideStateSelectChange(constantKey, rawValue) {
  const parsed = Number.parseInt(String(rawValue), 10);
  const nextState = [HIDE_STATE_VISIBLE, HIDE_STATE_MUTED, HIDE_STATE_HARD].includes(parsed)
    ? parsed
    : HIDE_STATE_VISIBLE;
  await setConstantOverride(constantKey, nextState > HIDE_STATE_VISIBLE, { hideState: nextState });
}

function getMutableOverridesTarget(sectionKey = props.sectionKey) {
  if (!sectionKey) return null;
  if (!state.sectionDesignOverrides) state.sectionDesignOverrides = {};
  return state.sectionDesignOverrides[sectionKey]
    ? { ...state.sectionDesignOverrides[sectionKey] }
    : {};
}

function getSectionDataByKey(sectionKey) {
  if (!sectionKey) return null;
  return state.sectionsData?.[sectionKey] || null;
}

function getContainerSiblingSectionKeys(sectionKey) {
  if (!sectionKey) return [];
  const order = Array.isArray(state.landingLayout?.order) ? state.landingLayout.order : [];
  const maps = buildSectionContainerMaps(
    order,
    state.landingLayout?.structure || [],
    state.sectionIds || {},
  );
  const containerId = maps.sectionToContainerId?.[sectionKey];
  if (!containerId) return [sectionKey];
  const members = maps.containersById?.[containerId]?.members || [];
  return members.length > 0 ? members : [sectionKey];
}

function getConstantTargetSectionKeys(constantKey, sectionKey = props.sectionKey) {
  if (!sectionKey) return [];
  if (
    constantKey === "removeSectionPadding"
    || constantKey === "removeSectionBackground"
    || constantKey === "hideSectionHeader"
    || constantKey === "hideSectionDescription"
    || constantKey === SHOW_VIDEO_EMPTY_PUBLIC_GENERIC_KEY
  ) {
    return [sectionKey];
  }
  return getContainerSiblingSectionKeys(sectionKey);
}

function clearPaddingResponsiveOverrides(target) {
  if (!target) return;
  if (target._responsiveValues?.sectionPadding) {
    delete target._responsiveValues.sectionPadding;
    if (Object.keys(target._responsiveValues).length === 0) delete target._responsiveValues;
  }
  if (target._selectedUnits?.sectionPadding) {
    delete target._selectedUnits.sectionPadding;
    if (Object.keys(target._selectedUnits).length === 0) delete target._selectedUnits;
  }
}

function clearBackgroundResponsiveOverrides(target) {
  if (!target) return;
  if (target._responsiveValues?.sectionBackgroundColor) {
    delete target._responsiveValues.sectionBackgroundColor;
    if (Object.keys(target._responsiveValues).length === 0) delete target._responsiveValues;
  }
  if (target._selectedUnits?.sectionBackgroundColor) {
    delete target._selectedUnits.sectionBackgroundColor;
    if (Object.keys(target._selectedUnits).length === 0) delete target._selectedUnits;
  }
}

function clearBorderAndShadowResponsiveOverrides(target) {
  if (!target) return;
  const keys = [
    "sectionBorderRadius",
    "sectionBorderWidth",
    "sectionBorderColor",
    "sectionBorderStyle",
    "sectionBoxShadow",
    "hardBoxShadowMode",
    "hardBoxShadowBrightness",
    "hardBoxShadowOffsetSource",
    "hardBoxShadowOffsetCustom",
  ];
  for (const key of keys) {
    if (target._responsiveValues?.[key]) {
      delete target._responsiveValues[key];
    }
    if (target._selectedUnits?.[key]) {
      delete target._selectedUnits[key];
    }
  }
  if (target._responsiveValues && Object.keys(target._responsiveValues).length === 0) {
    delete target._responsiveValues;
  }
  if (target._selectedUnits && Object.keys(target._selectedUnits).length === 0) {
    delete target._selectedUnits;
  }
}

async function setConstantOverride(constantKey, checked, options = {}) {
  if (!props.sectionKey) return;
  const siblingKeys = getConstantTargetSectionKeys(constantKey, props.sectionKey);
  const hardKey = getHideStateHardKey(constantKey);
  const hideState = Number.isInteger(options.hideState)
    ? options.hideState
    : (checked ? HIDE_STATE_MUTED : HIDE_STATE_VISIBLE);

  for (const siblingKey of siblingKeys) {
    const siblingSection = getSectionDataByKey(siblingKey);
    const nextGeneric = {
      ...(siblingSection?.sectionGeneric && typeof siblingSection.sectionGeneric === "object"
        ? siblingSection.sectionGeneric
        : {}),
    };

    if (hardKey) {
      if (hideState > HIDE_STATE_VISIBLE) nextGeneric[constantKey] = true;
      else delete nextGeneric[constantKey];

      if (hideState === HIDE_STATE_HARD) nextGeneric[hardKey] = true;
      else delete nextGeneric[hardKey];
    } else if (checked) {
      nextGeneric[constantKey] = true;
    } else {
      delete nextGeneric[constantKey];
    }

    updateSection(siblingKey, { sectionGeneric: nextGeneric }, { revisionKind: "design" });

    const target = getMutableOverridesTarget(siblingKey);
    if (!target) continue;

    let changed = false;
    const clearKey = (key) => {
      if (!(key in target)) return;
      delete target[key];
      changed = true;
    };

    if (constantKey === "hideSectionHeader") {
      clearKey("hideSectionTitle");
    } else if (constantKey === "hideSectionDescription") {
      clearKey("hideDescription");
    } else if (constantKey === "removeSectionPadding") {
      if ("sectionPadding" in target) {
        delete target.sectionPadding;
        changed = true;
      }
      const before = JSON.stringify(target);
      clearPaddingResponsiveOverrides(target);
      if (before !== JSON.stringify(target)) changed = true;
    } else if (constantKey === "removeSectionBackground") {
      [
        "sectionBackgroundColor",
        "sectionBorderRadius",
        "sectionBorderWidth",
        "sectionBorderColor",
        "sectionBorderStyle",
        "sectionBoxShadow",
        "hardBoxShadowMode",
        "hardBoxShadowBrightness",
        "hardBoxShadowOffsetSource",
        "hardBoxShadowOffsetCustom",
      ].forEach(clearKey);
      const before = JSON.stringify(target);
      clearBackgroundResponsiveOverrides(target);
      clearBorderAndShadowResponsiveOverrides(target);
      if (before !== JSON.stringify(target)) changed = true;
    }

    if (!changed) continue;

    const keys = Object.keys(target);
    const hasOnlyInactiveFlag = keys.length === 1 && keys[0] === "_active";
    if (keys.length === 0 || hasOnlyInactiveFlag) {
      if (state.sectionDesignOverrides?.[siblingKey]) {
        delete state.sectionDesignOverrides[siblingKey];
      }
    } else {
      state.sectionDesignOverrides[siblingKey] = target;
    }
    await saveSectionDesignOverrides(siblingKey);
  }
}

function openDesignOverrides() {
  if (!props.sectionKey) return;
  openSectionDesignPanel(props.sectionKey);
}

function setSectionCustomCssOverride(cssValue) {
  const sectionKey = String(props.sectionKey || "");
  if (!sectionKey) return;
  const rawCss = String(cssValue ?? "");
  if (!state.sectionCustomCssDrafts || typeof state.sectionCustomCssDrafts !== "object") {
    state.sectionCustomCssDrafts = {};
  }
  if (rawCss.trim()) state.sectionCustomCssDrafts[sectionKey] = rawCss;
  else delete state.sectionCustomCssDrafts[sectionKey];
}

function onSectionCustomCssInput() {
  setSectionCustomCssOverride(sectionCustomCssDraft.value);
}

function normalizeSnippet(snippet) {
  return {
    ...snippet,
    active: snippet?.active !== false,
  };
}

async function loadSectionCssSnippets() {
  sectionSnippetsLoading.value = true;
  try {
    const response = await api.listCssSnippets();
    const snippets = Array.isArray(response?.snippets) ? response.snippets : [];
    const contextKey = sectionSnippetContextKey.value;
    sectionCssSnippets.value = snippets
      .filter((snippet) => {
        const snippetKey = String(snippet?.context_key || "").trim();
        return snippetKey === contextKey;
      })
      .map(normalizeSnippet);
  } catch {
    sectionCssSnippets.value = [];
  } finally {
    sectionSnippetsLoading.value = false;
  }
}

function notifySnippetChanged() {
  window.dispatchEvent(new CustomEvent("fstvlpress:css-snippet-changed"));
  window.dispatchEvent(new Event("fstvlpress-template-snippets-updated"));
}

async function saveSectionCustomCssSnippet() {
  const css = String(sectionCustomCssDraft.value || "");
  if (!css.trim()) return;
  const contextKey = sectionSnippetContextKey.value;
  if (!contextKey) return;

  const suggested = `${sectionSnippetContextTag.value} ${formatInstantInServerTimezone(new Date().toISOString())}`;
  const label = window.prompt("Snippet name:", suggested);
  if (label === null) return;

  try {
    await api.createCssSnippet({
      label: label || suggested,
      css,
      active: true,
      context_key: contextKey,
    });
    notifySnippetChanged();
    await loadSectionCssSnippets();
    sectionCustomCssDraft.value = "";
    setSectionCustomCssOverride("");
  } catch (err) {
    console.error("Failed to save section CSS snippet:", err);
  }
}

function openCustomCssInDesignPanel() {
  window.dispatchEvent(new CustomEvent("fstvlpress:open-design-custom-css"));
}

async function toggleSectionCssSnippet(snippet) {
  try {
    const updated = await api.updateCssSnippet(snippet.id, { active: !snippet.active });
    const idx = sectionCssSnippets.value.findIndex((item) => item.id === snippet.id);
    if (idx >= 0) sectionCssSnippets.value[idx] = normalizeSnippet(updated);
    notifySnippetChanged();
  } catch (err) {
    console.error("Failed to toggle section CSS snippet:", err);
  }
}

async function removeSectionCssSnippet(snippet) {
  if (!confirm(`Delete snippet "${snippet.label}"?`)) return;
  try {
    await api.deleteCssSnippet(snippet.id);
    sectionCssSnippets.value = sectionCssSnippets.value.filter((item) => item.id !== snippet.id);
    notifySnippetChanged();
  } catch (err) {
    console.error("Failed to delete section CSS snippet:", err);
  }
}

function formatHistoryDate(value) {
  return formatRevisionTimestampBerlin(value) || "Unknown date";
}

function openRevisionSettings() {
  router.push("/admin/database/revisions");
}

function getCurrentContentSnapshot() {
  return historyCurrent.value?.content_snapshot || null;
}

function getCurrentDesignSnapshot() {
  return historyCurrent.value?.design_snapshot || null;
}

function applyHistoryPreview() {
  if (!props.sectionKey) return;
  const selectedDesign = selectedDesignRevisionEntry.value;
  const selectedContent = selectedContentRevisionEntry.value;

  const designSnapshot = selectedDesign?.source === "current"
    ? getCurrentDesignSnapshot()
    : (selectedDesign?.designSnapshot || null);
  const contentSnapshot = selectedContent?.source === "current"
    ? getCurrentContentSnapshot()
    : (selectedContent?.contentSnapshot || null);

  applySectionRevisionPreview(props.sectionKey, {
    contentSnapshot,
    designSnapshot,
    applyContent: showContentHistory.value,
    applyDesign: showDesignHistory.value,
  });
}

function resetHistorySelectionAndPreview() {
  selectedDesignRevisionKey.value = "current-design";
  selectedContentRevisionKey.value = "current-content";
  applyHistoryPreview();
}

function selectHistoryEntry(kind, entry) {
  if (!entry?.key) return;
  if (kind === "design") selectedDesignRevisionKey.value = entry.key;
  else selectedContentRevisionKey.value = entry.key;
  applyHistoryPreview();
}

async function loadSectionHistory() {
  const requestId = ++historyLoadRequestId;
  const sectionId = currentSectionId.value;
  if (!sectionId) {
    historyCurrent.value = null;
    historyStack.value = [];
    futureStack.value = [];
    historyOptions.value = { includeDesign: false, includeContent: false };
    historyError.value = "Revision history not available yet.";
    resetHistorySelectionAndPreview();
    return;
  }

  historyLoading.value = true;
  historyError.value = "";
  try {
    const response = await api.getSectionRevisions(sectionId);
    if (requestId !== historyLoadRequestId || active.value !== "history") return;
    if (response?.enabled === false) {
      historyCurrent.value = null;
      historyStack.value = [];
      futureStack.value = [];
      historyOptions.value = {
        includeDesign: Boolean(response?.options?.include_design),
        includeContent: Boolean(response?.options?.include_content),
      };
      historyError.value = "Revisions are disabled for this section.";
      resetHistorySelectionAndPreview();
      return;
    }

    historyCurrent.value = response?.current || null;
    historyStack.value = Array.isArray(response?.history) ? response.history : [];
    futureStack.value = Array.isArray(response?.future) ? response.future : [];
    historyOptions.value = {
      includeDesign: response?.options?.include_design !== false,
      includeContent: response?.options?.include_content !== false,
    };

    if (!revisionEntries.value.some((entry) => entry.key === selectedDesignRevisionKey.value)) {
      selectedDesignRevisionKey.value = "current-design";
    }
    if (!revisionEntries.value.some((entry) => entry.key === selectedContentRevisionKey.value)) {
      selectedContentRevisionKey.value = "current-content";
    }
    applyHistoryPreview();
  } catch (err) {
    if (requestId !== historyLoadRequestId || active.value !== "history") return;
    historyCurrent.value = null;
    historyStack.value = [];
    futureStack.value = [];
    historyOptions.value = { includeDesign: false, includeContent: false };
    historyError.value = "Failed to load revision history.";
    resetHistorySelectionAndPreview();
    console.error("Failed to load section history:", err);
  } finally {
    if (requestId === historyLoadRequestId) historyLoading.value = false;
  }
}

async function revertSelectedRevision(kind) {
  const isDesign = kind === "design";
  const selected = isDesign ? selectedDesignRevisionEntry.value : selectedContentRevisionEntry.value;
  const canRevert = isDesign ? canRevertDesign.value : canRevertContent.value;
  if (!canRevert || !selected || selected.source === "current") return;

  if (isDesign) historyRevertingDesign.value = true;
  else historyRevertingContent.value = true;
  historyError.value = "";
  try {
    if (isDesign) {
      const designSnapshot = selected.designSnapshot;
      applySectionRevisionPreview(props.sectionKey, {
        designSnapshot,
        applyContent: false,
        applyDesign: true,
      });
      const saved = await saveSectionByKey(props.sectionKey, {
        revisionKind: "design",
        revertedFromSavedAt: selected.savedAt || null,
      });
      if (!saved) throw new Error("Failed to save design revision.");
      await saveSectionDesignOverrides(props.sectionKey, undefined, {
        revertedFromSavedAt: selected.savedAt || null,
      });
    } else {
      applySectionRevisionPreview(props.sectionKey, {
        contentSnapshot: selected.contentSnapshot,
        applyContent: true,
        applyDesign: false,
      });
      const saved = await saveSectionByKey(props.sectionKey, {
        revisionKind: "content",
        revertedFromSavedAt: selected.savedAt || null,
      });
      if (!saved) throw new Error("Failed to save content revision.");
      const sharedFaqData = selected.contentSnapshot?.shared_faq_data;
      if (sharedFaqData && typeof sharedFaqData === "object") {
        await fetchFaqSharedData();
      }
      const sharedBlogData = selected.contentSnapshot?.shared_blog_data;
      if (sharedBlogData && typeof sharedBlogData === "object") {
        await fetchBlogData();
      }
      const sharedProgramData = selected.contentSnapshot?.shared_program_data;
      if (sharedProgramData && typeof sharedProgramData === "object") {
        await fetchProgramSharedData();
      }
    }

    const previousDesignSelection = selectedDesignRevisionEntry.value;
    const previousContentSelection = selectedContentRevisionEntry.value;

    await loadSectionHistory();

    const findByIdentity = (prev, fallbackKey) => {
      if (!prev) return fallbackKey;
      if (prev.source === "current") return prev.key || fallbackKey;
      const match = revisionEntries.value.find(
        (entry) => entry.source === prev.source && entry.savedAt === prev.savedAt
      );
      return match?.key || fallbackKey;
    };
    selectedDesignRevisionKey.value = isDesign
      ? "current-design"
      : findByIdentity(previousDesignSelection, "current-design");
    selectedContentRevisionKey.value = isDesign
      ? findByIdentity(previousContentSelection, "current-content")
      : "current-content";
    applyHistoryPreview();
  } catch (err) {
    historyError.value = `Failed to revert ${isDesign ? "design" : "content"} revision.`;
    console.error("Failed to revert section revision:", err);
  } finally {
    if (isDesign) historyRevertingDesign.value = false;
    else historyRevertingContent.value = false;
  }
}

onBeforeUnmount(() => {
  removeSectionAdminPinnedEditor(instanceId);
  stopPinnedResize();
  window.removeEventListener("resize", syncPinnedHeightToViewport);
  window.removeEventListener("fstvlpress:pin-all-section-editors", onPinAllSectionEditorsRequest);
  window.removeEventListener("fstvlpress:release-all-section-editors", onReleaseAllSectionEditorsRequest);
  if (props.sectionKey) {
    setSectionAdminActiveTab(props.sectionKey, "");
  }
  if (teleportHost.value) {
    const host = teleportHost.value;
    teleportHost.value = null;
    shouldTeleport.value = false;
    const shouldRemoveHost = teleportHostIsDynamic.value || host.getAttribute("data-dynamic-host") === "true";
    teleportHostIsDynamic.value = false;
    if (shouldRemoveHost) {
      host.remove();
    }
  }
  globalTeleportHost.value = null;
  resetHistorySelectionAndPreview();
  resetTemplateSyncState();
});
</script>

<style scoped lang="scss">
.section-admin-tabs-anchor {
  display: none;
}

.section-admin-tabs {
  margin: 0;
  color: var(--admin-text);
  width: 100%;
  --text: var(--admin-text);
  --muted: var(--admin-muted);
  --surface: var(--admin-bg);
  --surface-2: var(--admin-surface);
  --card-bg: var(--admin-bg);
  --border: var(--admin-border);
  --primary-color: var(--admin-text);
  --secondary-color: var(--admin-muted);
  --heading-color: var(--admin-text);
  --accent: var(--admin-accent, #4f46e5);
  --admin-text-muted: var(--admin-muted);

  /* Force admin button tokens inside tabs so template button themes cannot leak in */
  --button-primary-bg-color: var(--admin-primary-color, var(--admin-accent, #4f46e5));
  --button-primary-color: var(--admin-primary-text-color, #fff);
  --button-primary-border-color: transparent;
  --button-primary-hover-bg-color: var(--admin-primary-hover-color, var(--admin-accent, #4f46e5));
  --button-primary-hover-color: var(--admin-primary-hover-text-color, var(--button-primary-color));
  --button-secondary-bg-color: var(--admin-surface);
  --button-secondary-color: var(--admin-text);
  --button-secondary-border-color: var(--admin-border);
  --button-ghost-bg-color: transparent;
  --button-ghost-color: var(--admin-text);
  --button-ghost-border-color: var(--admin-border);
  --button-padding-y: 8px;
  --button-padding-x: 12px;
  --button-border-radius: 10px;
  --button-border-width: 1px;
}

.section-admin-tabs__head {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 12px 0;
}

.section-admin-tabs__super-tabs {
  border-bottom: 1px solid currentColor;
}

.section-admin-tabs__resize-handle {
  height: 10px;
  cursor: ns-resize;
  touch-action: none;
  display: grid;
  place-items: center;
  border-bottom: 2px dashed #0003;
  background: color-mix(in srgb, var(--admin-surface) 90%, transparent);
}

.section-admin-tabs__resize-grip {
  width: 64px;
  height: 4px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--admin-text-muted) 55%, transparent);
}

.section-admin-tabs__super-tabs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 8px 12px 0;
}

.section-admin-tabs__super-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
  background: color-mix(in srgb, var(--admin-surface) 84%, transparent);
  color: var(--admin-text-muted);
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
  cursor: pointer;
  max-width: min(34ch, 48vw);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.section-admin-tabs__super-tab.active {
  color: var(--admin-text);
  border: 1px solid var(--admin-border);
  border-bottom: none;
  margin-bottom: -1px;
}

.section-admin-tabs--editor-pinned .section-admin-tabs__head, 
.section-admin-tabs__super-tab.active  {
  background: #eee;
}

.section-admin-tabs__super-tab-label {
  min-width: 0;
}

.section-admin-tabs__tabs {
  display: flex;
  flex: 1 1 auto;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 8px;
  min-width: 0;
}

.section-admin-tabs__tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid transparent;
  border-bottom: 0;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
  background: var(--admin-surface);
  color: var(--admin-text);
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  cursor: pointer;
}

.section-admin-tabs__tab-icon {
  font-size: 11px;
}

.section-admin-tabs__tab.active {
  background: var(--surface-2);
  position: relative;
  top: 1px;
  border: 1px solid black;
  border-bottom: 0;
}

.section-admin-tabs__pin-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  border: 1px solid currentColor;
  border-radius: 8px;
  background: none;
  color: white;
  padding: 4px 10px;
  margin-bottom: 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  cursor: pointer;
  white-space: nowrap;
}

.section-admin-tabs__pin-icon {
  font-size: 11px;
}

.section-admin-tabs__pin-btn.active {
  color: var(--admin-accent, var(--accent, #4f46e5));
}

.section-admin-tabs__pin-all-btn {
  margin-left: 0;
  color: var(--admin-accent);
}

.section-admin-tabs__body {
  box-shadow: none;
  border-top: 1px solid var(--admin-border);
  color: var(--admin-text);
  background: var(--surface-2);

  &> div {
    padding: 12px;
  }
}

.section-admin-tabs--editor-pinned {
  position: fixed;
  left: 0;
  right: 0;
  width: 100vw;
  max-width: 100vw;
  bottom: max(0px, env(safe-area-inset-bottom, 0px));
  z-index: var(--admin-z-pinned-section-editor, 9000);
  border: 1px solid var(--admin-border);
  border-bottom: none;
  border-radius: 12px 12px 0 0;
  background: var(--surface-2);
  box-shadow: 0 -12px 24px rgba(15, 23, 42, 0.28);
  overflow: hidden;
  min-height: var(--section-admin-tabs-pinned-min-height, 0px);
}

.section-admin-tabs--editor-pinned-inactive {
  display: none;
}

.section-admin-tabs--editor-pinned .section-admin-tabs__body {
  height: var(--section-admin-tabs-pinned-body-height, 20vh);
  min-height: -1px;
  max-height: 85vh;
  overflow: auto;
  resize: none;
  overscroll-behavior: contain;
}

.section-admin-tabs__body.is-collapsing > * {
  visibility: hidden;
}

.section-admin-tabs__body :deep(input),
.section-admin-tabs__body :deep(select),
.section-admin-tabs__body :deep(textarea) {
  color: var(--admin-text);
}

.section-admin-tabs__body :deep(input::placeholder),
.section-admin-tabs__body :deep(textarea::placeholder) {
  color: var(--admin-text-muted);
}

.section-admin-tabs__body :deep(.editor) {
  display: grid;
  gap: 16px;
}

.section-admin-tabs__body :deep(.editor-title) {
  font-weight: 900;
  color: var(--admin-text);
}

.section-admin-tabs__design {
  display: grid;
  gap: 12px;
}

.section-admin-tabs__design-section {
  display: block;
  min-width: 0;
  background: #fff;
  border-radius: 8px;
}

.section-admin-tabs__design-summary {
  font-weight: 600;
  color: var(--admin-text, #374151);
  cursor: pointer;
  padding: 0.75rem;
  background: #fff;
  border-radius: 8px;
  list-style: none;
  text-transform: capitalize;
}

.section-admin-tabs__design-summary::-webkit-details-marker {
  display: none;
}

.section-admin-tabs__design-summary::before {
  content: "▸ ";
  color: var(--admin-text-muted, #9ca3af);
}

.section-admin-tabs__design-section[open] > .section-admin-tabs__design-summary::before {
  content: "▾ ";
}

.section-admin-tabs__design-content {
  padding: 1rem;
  background: #fff;
  border-radius: 0 0 8px 8px;
  margin-top: -4px;
  gap: 10px;
  display: grid;
}

.section-admin-tabs__generic-css-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.section-admin-tabs__generic-css-grid.is-single {
  grid-template-columns: minmax(0, 1fr);
}

.section-admin-tabs__design-footer {
  display: flex;
  align-items: center;
  min-height: 32px;
}

.section-admin-tabs__constants-list {
  display: grid;
  gap: 8px;
}

.constant-check {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--admin-text);
  font-size: 13px;
}

.constant-choice {
  display: grid;
  gap: 6px;
}

.constant-choice__label {
  color: var(--admin-text);
  font-size: 13px;
}

.constant-choice__select {
  width: 100%;
  border: 1px solid var(--admin-border);
  border-radius: 8px;
  background: var(--admin-surface);
  color: var(--admin-text);
  padding: 6px 8px;
}

.section-admin-tabs__constants-btn {
  justify-self: start;
}

.section-admin-tabs__type-specific-body {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.section-admin-tabs__type-specific-body:not(.has-params),
.section-admin-tabs__type-specific-body:not(.has-colors),
.section-admin-tabs__type-specific-body.has-legacy {
  grid-template-columns: minmax(0, 1fr);
}

.section-admin-tabs__type-specific-params,
.section-admin-tabs__type-specific-colors,
.section-admin-tabs__type-specific-legacy {
  min-width: 0;
  display: grid;
  gap: 10px;
}

.section-admin-tabs__type-specific-colors :deep(.color-link-control),
.section-admin-tabs__type-specific-colors :deep(.color-ctrl),
.section-admin-tabs__type-specific-colors :deep(.tv-color-control),
.section-admin-tabs__type-specific-colors :deep(.color-control-row) {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.section-admin-tabs__type-specific-colors :deep(.ctrl-label),
.section-admin-tabs__type-specific-colors :deep(.control-label),
.section-admin-tabs__type-specific-colors :deep(.field-label),
.section-admin-tabs__type-specific-colors :deep(.ab-label),
.section-admin-tabs__type-specific-colors :deep(.stage-color-name) {
  flex: 0 0 100%;
  width: 100%;
  margin: 0;
}

.section-admin-tabs__type-specific-colors :deep(.ab-row),
.section-admin-tabs__type-specific-colors :deep(.design-field),
.section-admin-tabs__type-specific-colors :deep(.field-group),
.section-admin-tabs__type-specific-colors :deep(.stage-color-row) {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 6px;
  align-items: start;
}

.section-admin-tabs__type-specific-params :deep(.admin-controls-row),
.section-admin-tabs__type-specific-colors :deep(.admin-controls-row) {
  gap: 10px;
  margin-top: 0;
}

.section-admin-tabs__type-specific-params :deep(.ctrl-item),
.section-admin-tabs__type-specific-params :deep(.design-field),
.section-admin-tabs__type-specific-params :deep(.field-group),
.section-admin-tabs__type-specific-params :deep(.ctrl-field),
.section-admin-tabs__type-specific-params :deep(.grid-control:not(.grid-control--checkbox)),
.section-admin-tabs__type-specific-params :deep(.ab-row) {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: start;
  gap: 6px;
}

.section-admin-tabs__type-specific-colors > :deep(.admin-actions),
.section-admin-tabs__type-specific-colors > :deep(.admin-controls-row),
.section-admin-tabs__type-specific-colors > :deep(.admin-bar) {
  padding: 10px;
  border: 1px solid var(--admin-border, #e5e7eb);
  border-radius: 8px;
  background: #fff;
}

.section-admin-tabs__custom-css-body {
  display: grid;
  gap: 8px;
}

.section-admin-tabs__custom-css-textarea {
  width: 100%;
  min-height: 110px;
  border: 1px solid var(--admin-border);
  border-radius: 10px;
  background: var(--admin-surface);
  color: var(--admin-text);
  padding: 10px 12px;
  resize: vertical;
}

.section-admin-tabs__custom-css-textarea::placeholder {
  color: var(--admin-text-muted);
  opacity: 0.5;
}

.section-admin-tabs__custom-css-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

.section-admin-tabs__custom-css-open-btn {
  background: transparent;
  color: var(--admin-text);
}

.section-admin-tabs__snippet-section {
  display: grid;
  gap: 8px;
  margin-top: 4px;
}

.section-admin-tabs__snippet-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--admin-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.section-admin-tabs__snippet-hint {
  font-size: 12px;
  color: var(--admin-text-muted);
}

.section-admin-tabs__snippet-card {
  border: 1px solid var(--admin-border);
  border-radius: 10px;
  background: var(--admin-surface);
  padding: 8px;
  display: grid;
  gap: 6px;
}

.section-admin-tabs__snippet-card.inactive {
  opacity: 0.55;
}

.section-admin-tabs__snippet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.section-admin-tabs__snippet-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.section-admin-tabs__snippet-label {
  font-size: 12px;
  color: var(--admin-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.section-admin-tabs__snippet-scope {
  border: 1px solid var(--admin-border);
  border-radius: 999px;
  padding: 1px 6px;
  font-size: 10px;
  color: var(--admin-text-muted);
  text-transform: uppercase;
}

.section-admin-tabs__snippet-del {
  width: 22px;
  height: 22px;
  border: 1px solid var(--admin-border);
  border-radius: 6px;
  background: transparent;
  color: var(--admin-text-muted);
  cursor: pointer;
}

.section-admin-tabs__snippet-del:hover {
  color: #ef4444;
  border-color: #ef4444;
}

.section-admin-tabs__snippet-preview {
  margin: 0;
  font-size: 11px;
  color: var(--admin-text-muted);
  white-space: pre-wrap;
  word-break: break-word;
}

.section-admin-tabs__notes {
  display: grid;
  gap: 10px;
}

.section-admin-tabs__history {
  display: grid;
  gap: 10px;
}

.section-admin-tabs__history-head {
  display: flex;
  justify-content: flex-end;
}

.section-admin-tabs__history-config-btn {
  background: transparent;
  color: var(--admin-text);
}

.section-admin-tabs__history-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
}

.section-admin-tabs__history-grid.single-column {
  grid-template-columns: minmax(0, 1fr);
}

.section-admin-tabs__history-col {
  display: grid;
  gap: 6px;
  align-content: start;
}

.section-admin-tabs__history-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--admin-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.section-admin-tabs__history-item {
  width: 100%;
  border: 1px solid var(--admin-border);
  border-radius: 10px;
  background: var(--admin-surface);
  color: var(--admin-text);
  padding: 8px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 4px;
  cursor: pointer;
  text-align: left;
}

.section-admin-tabs__history-item.active {
  border-color: var(--admin-accent, var(--accent, #4f46e5));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--admin-accent, var(--accent, #4f46e5)) 40%, transparent);
}

.section-admin-tabs__history-item.current {
  opacity: 0.88;
}

.section-admin-tabs__history-item-head {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  grid-column: 1;
  grid-row: 1;
}

.section-admin-tabs__history-item-head :deep(.author-badge) {
  width: 28px;
  height: 28px;
}

.section-admin-tabs__history-item-head :deep(.author-icon) {
  font-size: 16px;
}

.section-admin-tabs__history-author {
  font-size: 13px;
  font-weight: 700;
  color: var(--admin-text);
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.section-admin-tabs__history-date {
  font-size: 11px;
  color: var(--admin-text-muted);
  grid-column: 2;
  grid-row: 1;
  justify-self: end;
  align-self: start;
  text-align: right;
  white-space: nowrap;
  padding-left: 8px;
}

.section-admin-tabs__history-diff {
  grid-column: 1 / -1;
}

.section-admin-tabs__history-empty {
  margin: 0;
  font-size: 12px;
  color: var(--admin-text-muted);
}

.section-admin-tabs__history-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 2px;
}

.section-admin-tabs__template {
  display: grid;
  gap: 10px;
}

.section-admin-tabs__template-extra {
  display: grid;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--admin-border);
}

.section-admin-tabs__template-head {
  display: grid;
  gap: 8px;
}

.section-admin-tabs__template-share {
  display: grid;
  gap: 6px;
  padding: 0 0 10px;
  border-bottom: 1px solid var(--admin-border);
}

.section-admin-tabs__template-share-check {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--admin-text);
}

.section-admin-tabs__template-share-check input {
  width: 16px;
  height: 16px;
}

.section-admin-tabs__template-share-check:has(input:disabled) {
  opacity: 0.7;
}

.section-admin-tabs__template-ref {
  margin: 0;
  font-size: 12px;
  color: var(--admin-text-muted);
}

.section-admin-tabs__template-body {
  display: grid;
  gap: 8px;
}

.section-admin-tabs__template-summary {
  margin: 0;
  font-size: 12px;
  color: var(--admin-text-muted);
}

.section-admin-tabs__template-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.section-admin-tabs__template-diff-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: var(--admin-text);
  display: grid;
  gap: 4px;
}

.section-admin-tabs__template-feedback {
  margin: 0;
  font-size: 12px;
  color: var(--admin-text-muted);
}

.section-admin-tabs__template-feedback--error {
  color: #b91c1c;
}

.notes-label,
.todo-head {
  font-size: 11px;
  font-weight: 700;
  color: var(--admin-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.notes-textarea {
  width: 100%;
  min-height: 90px;
  border: 1px solid var(--admin-border);
  border-radius: 10px;
  background: var(--admin-surface);
  color: var(--admin-text);
  padding: 10px 12px;
  resize: vertical;
}

.todo-add {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 120px 120px auto;
  gap: 8px;
  align-items: center;
}

.todo-board {
  display: grid;
  gap: 12px;
}

.todo-input {
  min-width: 0;
  width: 100%;
  border: 1px solid var(--admin-border);
  border-radius: 10px;
  background: var(--admin-surface);
  color: var(--admin-text);
  padding: 8px 10px;
}

.todo-input:focus {
  outline: none;
  border-color: color-mix(in srgb, var(--admin-accent, var(--accent, #4f46e5)) 60%, var(--admin-border));
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--admin-accent, var(--accent, #4f46e5)) 18%, transparent);
}

.todo-list {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  align-items: start;
  gap: 10px;
}

.todo-group {
  display: grid;
  gap: 6px;
  align-content: start;
  align-self: start;
  min-width: 0;
}

.todo-group-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--admin-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.todo-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  box-sizing: border-box;
  background: var(--admin-surface);
  border: 1px solid var(--admin-border);
  border-radius: 10px;
  padding: 6px 8px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}

.todo-item:hover {
  border-color: color-mix(in srgb, var(--admin-accent, var(--accent, #4f46e5)) 26%, var(--admin-border));
  box-shadow: 0 6px 14px rgba(15, 23, 42, 0.06);
  transform: translateY(-1px);
}

.todo-item.tone-it {
  border-left: 3px solid color-mix(in srgb, #2563eb 70%, transparent);
  background: color-mix(in srgb, var(--admin-surface) 92%, #eff6ff);
}

.todo-item.tone-content {
  border-left: 3px solid color-mix(in srgb, #16a34a 65%, transparent);
  background: color-mix(in srgb, var(--admin-surface) 93%, #f0fdf4);
}

.todo-item.prio-urgent {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, #ef4444 20%, transparent);
}

.todo-main {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.todo-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-text.done {
  text-decoration: line-through;
  color: var(--admin-text-muted);
}

.todo-meta-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 18px;
}

.todo-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 999px;
  padding: 2px 4px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  line-height: 1.4;
}

.todo-chip-icon {
  flex: 0 0 auto;
  width: 0.9em;
}

.todo-chip--tag.area-it {
  color: #1d4ed8;
  background: #dbeafe;
}

.todo-chip--tag.area-content {
  color: #166534;
  background: #dcfce7;
}

.todo-chip--priority {
  min-width: 24px;
  justify-content: center;
}

.todo-chip--priority.priority-urgent {
  color: #991b1b;
  background: #fee2e2;
}

.todo-chip--priority.priority-needed {
  color: #92400e;
  background: #fef3c7;
}

.todo-chip--priority.priority-optional {
  color: #334155;
  background: #e2e8f0;
}

.todo-remove {
  display: inline-grid;
  place-items: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--admin-text-muted);
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}

.todo-author {
  opacity: 0.9;
  font-size: 11px;
}

.todo-author.author-badge {
  width: 28px;
  height: 28px;
}

.todo-author.author-badge :deep(.author-icon) {
  font-size: 16px;
}

.todo-remove:hover {
  background: color-mix(in srgb, #ef4444 12%, transparent);
  color: #ef4444;
}

.todo-empty {
  margin: 0;
  font-size: 12px;
  color: var(--admin-text-muted);
}

.section-admin-tabs__body :deep(.btn) {
  border: 1px solid var(--button-primary-border-color, transparent);
  border-radius: var(--button-border-radius, 10px);
  background: var(--button-primary-bg-color, var(--admin-accent, #4f46e5));
  color: var(--button-primary-color, #fff);
  padding: var(--button-padding-y, 8px) var(--button-padding-x, 12px);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.2;
  cursor: pointer;
  transition: filter 140ms ease, transform 120ms ease, opacity 140ms ease;
}

.section-admin-tabs__body :deep(.btn:not(.secondary):not(.ghost):hover) {
  background: var(--button-primary-hover-bg-color, var(--button-primary-bg-color, var(--admin-accent, #4f46e5)));
  color: var(--button-primary-hover-color, var(--button-primary-color, #fff));
}

.section-admin-tabs__body :deep(.btn:active) {
  transform: translateY(1px);
}

.section-admin-tabs__body :deep(.btn.secondary) {
  background: var(--button-secondary-bg-color, var(--admin-surface));
  color: var(--button-secondary-color, var(--admin-text));
  border-color: var(--button-secondary-border-color, var(--admin-border));
}

.section-admin-tabs__body :deep(.btn.ghost) {
  background: var(--button-ghost-bg-color, transparent);
  color: var(--button-ghost-color, var(--admin-text));
  border-color: var(--button-ghost-border-color, var(--admin-border));
}

.section-admin-tabs__body :deep(.btn:disabled) {
  opacity: 0.45;
  cursor: not-allowed;
  filter: saturate(0.5);
}

@media (max-width: 820px) {
  .section-admin-tabs__head {
    align-items: stretch;
    flex-wrap: wrap;
  }

  .section-admin-tabs__pin-btn {
    margin-left: 0;
  }

  .section-admin-tabs__history-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .section-admin-tabs__generic-css-grid,
  .section-admin-tabs__type-specific-body {
    grid-template-columns: minmax(0, 1fr);
  }

  .todo-list {
    grid-template-columns: minmax(0, 1fr);
  }
  .todo-add {
    grid-template-columns: minmax(0, 1fr);
  }
  .todo-item {
    grid-template-columns: auto minmax(0, 1fr) auto auto;
    height: auto;
    align-items: start;
  }
}
</style>
