<template>
  <div class="admin-devops admin-page">
    <header class="page-header">
      <h1>DevOps</h1>
      <p class="page-subtitle">Global todo planning across all section instances and headers.</p>
    </header>

    <AdminPageTabs
      :tabs="tabs"
      :model-value="activeTab"
      @update:model-value="setActiveTab"
    />

    <div v-if="loading" class="loading-state">Loading DevOps data…</div>
    <div v-else-if="error" class="status-message error">{{ error }}</div>

    <template v-else>
      <template v-if="activeTab === 'todos'">
        <div class="config-card">
          <div class="card-header">
            <h2>Todos</h2>
            <p class="card-hint">Open and done todos across sections and headers.</p>
          </div>

          <div class="all-todo-filters">
            <label class="all-todo-filter-field">
              <span class="all-todo-filter-label">Tag Type</span>
              <select v-model="allTodoTypeFilter" class="admin-control">
                <option value="all">All</option>
                <option value="it">IT</option>
                <option value="content">Content</option>
              </select>
            </label>
            <label class="all-todo-filter-field">
              <span class="all-todo-filter-label">Urgency</span>
              <TodoIconSelect
                v-model="allTodoPriorityFilter"
                :options="allTodoPriorityFilterOptions"
                aria-label="Filter todos by urgency"
              />
            </label>
            <label class="all-todo-filter-field">
              <span class="all-todo-filter-label">Status</span>
              <select v-model="allTodoDoneFilter" class="admin-control">
                <option value="all">All</option>
                <option value="open">Open</option>
                <option value="done">Done</option>
              </select>
            </label>
            <label class="all-todo-filter-field">
              <span class="all-todo-filter-label">Creator</span>
              <select v-model="allTodoCreatorFilter" class="admin-control">
                <option value="all">All</option>
                <option
                  v-for="option in allTodoCreatorFilterOptions"
                  :key="`creator-${option.value}`"
                  :value="option.value"
                >
                  {{ option.value }} ({{ option.count }})
                </option>
              </select>
            </label>
            <label class="all-todo-filter-field">
              <span class="all-todo-filter-label">Group By</span>
              <select v-model="allTodoGroupBy" class="admin-control">
                <option value="none">None</option>
                <option value="section">Section</option>
                <option value="page">Page</option>
              </select>
            </label>
          </div>

          <div v-if="allTodoTagFilterOptions.length > 0" class="all-todo-tag-filters">
            <span class="all-todo-filter-label">Tags</span>
            <div class="all-todo-tag-filter-list">
              <button
                v-for="option in allTodoTagFilterOptions"
                :key="`todo-filter-${option.id}`"
                type="button"
                class="chip chip-filter"
                :class="{ active: allTodoSelectedTags.includes(option.id) }"
                :title="todoTagIconLabel(option.id)"
                :aria-label="`${todoTagIconLabel(option.id)} (${option.count})`"
                @click="toggleAllTodoTagFilter(option.id)"
              >
                <span class="todo-tag-inline">
                  <font-awesome-icon
                    v-if="todoTagIcon(option.id)"
                    :icon="todoTagIcon(option.id)"
                    class="todo-tag-icon"
                    aria-hidden="true"
                  />
                  <span>{{ todoTagText(option.id) }}</span>
                </span>
                <span class="chip-filter-count">{{ option.count }}</span>
              </button>
              <button
                v-if="allTodoSelectedTags.length > 0"
                type="button"
                class="btn-outline btn-sm"
                @click="clearAllTodoTagFilters"
              >
                Clear
              </button>
            </div>
          </div>

          <div v-if="canManageDevops" class="all-todo-add">
            <div class="all-todo-add-title">Add Unassigned Todo</div>
            <div class="all-todo-add-row">
              <textarea
                v-model="newUnassignedTodoText"
                class="admin-control all-todo-add-textarea"
                rows="3"
                placeholder="Todo text"
                @keydown.ctrl.enter.prevent="addUnassignedTodo"
                @keydown.meta.enter.prevent="addUnassignedTodo"
              />
              <label class="all-todo-add-field">
                <span class="all-todo-add-label">Tag</span>
                <TodoIconSelect
                  v-model="newUnassignedTodoTag"
                  :options="todoTagSelectOptions"
                  aria-label="Todo type"
                />
              </label>
              <label class="all-todo-add-field">
                <span class="all-todo-add-label">Priority</span>
                <TodoIconSelect
                  v-model="newUnassignedTodoPriority"
                  :options="todoPrioritySelectOptions"
                  aria-label="Todo urgency"
                />
              </label>
              <button
                class="btn-primary btn-sm"
                :disabled="addingUnassignedTodo || !String(newUnassignedTodoText || '').trim()"
                @click="addUnassignedTodo"
              >
                {{ addingUnassignedTodo ? "Adding…" : "Add Unassigned Todo" }}
              </button>
            </div>
          </div>

          <div v-if="allTodoEntries.length === 0" class="empty-state">
            No todos created yet.
          </div>
          <div v-else-if="filteredAllTodoEntries.length === 0" class="empty-state">
            No todos match the selected filters.
          </div>
          <template v-else-if="allTodoGroupBy === 'none'">
            <div class="all-todos-list">
              <div
                v-for="entry in filteredAllTodoEntries"
                :key="entry.uid"
                class="all-todo-row"
                :class="[todoRowClasses(entry.todo), { 'has-open-link': Boolean(entry.source.openHref) }]"
              >
                <div class="all-todo-main">
                  <div class="all-todo-text" :class="{ done: entry.todo.done }">{{ entry.todo.text }}</div>
                  <div class="all-todo-source">{{ entry.source.label }}</div>
                  <div v-if="todoCommentList(entry.todo).length > 0" class="all-todo-comments">
                    <div
                      v-for="comment in todoCommentList(entry.todo)"
                      :key="`${entry.uid}-comment-${comment.id}`"
                      class="all-todo-comment"
                    >
                      <span class="all-todo-comment-author">{{ todoCommentMeta(comment) }}</span>
                      <span class="all-todo-comment-text">{{ comment.text }}</span>
                    </div>
                  </div>
                </div>
                <div class="all-todo-meta">
                  <span
                    class="chip todo-tag-chip"
                    :title="todoTagIconLabel(entry.todo.tag)"
                    :aria-label="todoTagIconLabel(entry.todo.tag)"
                  >
                    <font-awesome-icon
                      v-if="todoTagIcon(entry.todo.tag)"
                      :icon="todoTagIcon(entry.todo.tag)"
                      class="todo-tag-icon"
                      aria-hidden="true"
                    />
                    <span>{{ todoTagText(entry.todo.tag) }}</span>
                  </span>
                  <span class="chip chip-muted">{{ entry.tagArea }}</span>
                  <span
                    class="chip chip-muted chip-priority"
                    :class="`priority-${entry.todo.priority}`"
                    :title="priorityIconLabel(entry.todo.priority)"
                    :aria-label="priorityIconLabel(entry.todo.priority)"
                  >
                    <font-awesome-icon :icon="priorityIcon(entry.todo.priority)" aria-hidden="true" />
                  </span>
                  <span class="chip chip-muted chip-status" :class="entry.todo.done ? 'status-done' : 'status-open'">{{ entry.todo.done ? "done" : "open" }}</span>
                  <span class="chip chip-muted chip-creator">by {{ entry.todo.createdBy || "unknown" }}</span>
                </div>
                <div class="all-todo-actions">
                  <a
                    v-if="entry.source.openHref"
                    class="btn-outline btn-sm all-todo-open-link"
                    :href="entry.source.openHref"
                  >
                    {{ entry.source.openLabel }}
                  </a>
                  <template v-if="isTodoOwnedByCurrentUser(entry.todo)">
                    <button
                      v-if="editingTodoUid !== entry.uid"
                      type="button"
                      class="btn-outline btn-sm"
                      @click="startTodoEdit(entry)"
                    >
                      Edit Ticket
                    </button>
                    <div v-else class="all-todo-inline-form">
                      <textarea
                        v-model="editingTodoText"
                        class="admin-control all-todo-inline-input all-todo-inline-textarea"
                        rows="3"
                        placeholder="Edit ticket text"
                        @keydown.ctrl.enter.prevent="saveTodoEdit(entry)"
                        @keydown.meta.enter.prevent="saveTodoEdit(entry)"
                        @keydown.esc.prevent="cancelTodoEdit"
                      />
                      <button
                        type="button"
                        class="btn-primary btn-sm"
                        :disabled="isTodoSavePending(entry.uid) || !String(editingTodoText || '').trim()"
                        @click="saveTodoEdit(entry)"
                      >
                        {{ isTodoSavePending(entry.uid) ? "Saving…" : "Save" }}
                      </button>
                      <button type="button" class="btn-outline btn-sm" @click="cancelTodoEdit">
                        Cancel
                      </button>
                    </div>
                  </template>
                  <template v-else>
                    <div class="all-todo-inline-form">
                      <textarea
                        v-model="todoCommentDrafts[entry.uid]"
                        class="admin-control all-todo-inline-input all-todo-inline-textarea"
                        rows="3"
                        placeholder="Comment on ticket"
                        @keydown.ctrl.enter.prevent="addTodoComment(entry)"
                        @keydown.meta.enter.prevent="addTodoComment(entry)"
                      />
                      <button
                        type="button"
                        class="btn-primary btn-sm"
                        :disabled="isTodoSavePending(entry.uid) || !String(todoCommentDrafts[entry.uid] || '').trim()"
                        @click="addTodoComment(entry)"
                      >
                        {{ isTodoSavePending(entry.uid) ? "Saving…" : "Comment" }}
                      </button>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </template>
          <template v-else>
            <div class="todo-groups">
              <div v-for="group in groupedAllTodoEntries" :key="group.key" class="todo-group-card">
                <div class="todo-group-head">
                  <h3>{{ group.label }}</h3>
                  <span class="count-badge">{{ group.entries.length }}</span>
                </div>
                <div class="all-todos-list">
                  <div
                    v-for="entry in group.entries"
                    :key="`${group.key}:${entry.uid}`"
                    class="all-todo-row"
                    :class="[todoRowClasses(entry.todo), { 'has-open-link': Boolean(entry.source.openHref) }]"
                  >
                    <div class="all-todo-main">
                      <div class="all-todo-text" :class="{ done: entry.todo.done }">{{ entry.todo.text }}</div>
                      <div class="all-todo-source">{{ entry.source.label }}</div>
                      <div v-if="todoCommentList(entry.todo).length > 0" class="all-todo-comments">
                        <div
                          v-for="comment in todoCommentList(entry.todo)"
                          :key="`${entry.uid}-comment-${comment.id}`"
                          class="all-todo-comment"
                        >
                          <span class="all-todo-comment-author">{{ todoCommentMeta(comment) }}</span>
                          <span class="all-todo-comment-text">{{ comment.text }}</span>
                        </div>
                      </div>
                    </div>
                    <div class="all-todo-meta">
                      <span
                        class="chip todo-tag-chip"
                        :title="todoTagIconLabel(entry.todo.tag)"
                        :aria-label="todoTagIconLabel(entry.todo.tag)"
                      >
                        <font-awesome-icon
                          v-if="todoTagIcon(entry.todo.tag)"
                          :icon="todoTagIcon(entry.todo.tag)"
                          class="todo-tag-icon"
                          aria-hidden="true"
                        />
                        <span>{{ todoTagText(entry.todo.tag) }}</span>
                      </span>
                      <span class="chip chip-muted">{{ entry.tagArea }}</span>
                      <span
                        class="chip chip-muted chip-priority"
                        :class="`priority-${entry.todo.priority}`"
                        :title="priorityIconLabel(entry.todo.priority)"
                        :aria-label="priorityIconLabel(entry.todo.priority)"
                      >
                        <font-awesome-icon :icon="priorityIcon(entry.todo.priority)" aria-hidden="true" />
                      </span>
                      <span class="chip chip-muted chip-status" :class="entry.todo.done ? 'status-done' : 'status-open'">{{ entry.todo.done ? "done" : "open" }}</span>
                      <span class="chip chip-muted chip-creator">by {{ entry.todo.createdBy || "unknown" }}</span>
                    </div>
                    <div class="all-todo-actions">
                      <a
                        v-if="entry.source.openHref"
                        class="btn-outline btn-sm all-todo-open-link"
                        :href="entry.source.openHref"
                      >
                        {{ entry.source.openLabel }}
                      </a>
                      <template v-if="isTodoOwnedByCurrentUser(entry.todo)">
                        <button
                          v-if="editingTodoUid !== entry.uid"
                          type="button"
                          class="btn-outline btn-sm"
                          @click="startTodoEdit(entry)"
                        >
                          Edit Ticket
                        </button>
                        <div v-else class="all-todo-inline-form">
                          <textarea
                            v-model="editingTodoText"
                            class="admin-control all-todo-inline-input all-todo-inline-textarea"
                            rows="3"
                            placeholder="Edit ticket text"
                            @keydown.ctrl.enter.prevent="saveTodoEdit(entry)"
                            @keydown.meta.enter.prevent="saveTodoEdit(entry)"
                            @keydown.esc.prevent="cancelTodoEdit"
                          />
                          <button
                            type="button"
                            class="btn-primary btn-sm"
                            :disabled="isTodoSavePending(entry.uid) || !String(editingTodoText || '').trim()"
                            @click="saveTodoEdit(entry)"
                          >
                            {{ isTodoSavePending(entry.uid) ? "Saving…" : "Save" }}
                          </button>
                          <button type="button" class="btn-outline btn-sm" @click="cancelTodoEdit">
                            Cancel
                          </button>
                        </div>
                      </template>
                      <template v-else>
                        <div class="all-todo-inline-form">
                          <textarea
                            v-model="todoCommentDrafts[entry.uid]"
                            class="admin-control all-todo-inline-input all-todo-inline-textarea"
                            rows="3"
                            placeholder="Comment on ticket"
                            @keydown.ctrl.enter.prevent="addTodoComment(entry)"
                            @keydown.meta.enter.prevent="addTodoComment(entry)"
                          />
                          <button
                            type="button"
                            class="btn-primary btn-sm"
                            :disabled="isTodoSavePending(entry.uid) || !String(todoCommentDrafts[entry.uid] || '').trim()"
                            @click="addTodoComment(entry)"
                          >
                            {{ isTodoSavePending(entry.uid) ? "Saving…" : "Comment" }}
                          </button>
                        </div>
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </template>

      <template v-else-if="activeTab === 'changelog'">
        <div class="config-card changelog-panel">
          <div class="card-header changelog-header">
            <div>
              <h2>Changelog</h2>
              <p class="card-hint">{{ changelogCardHint }}</p>
            </div>
            <div class="changelog-header-actions">
              <label class="changelog-page-filter">
                <span class="changelog-page-filter-label">Page</span>
                <select
                  v-model="changelogPageSlug"
                  class="admin-control"
                  :disabled="loadingChangelog || changelogPageOptions.length === 0"
                >
                  <option value="">All pages</option>
                  <option
                    v-for="option in changelogPageOptions"
                    :key="`changelog-page-${option.slug}`"
                    :value="option.slug"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </label>
              <div v-if="changelogTotal > 0" class="changelog-pagination-summary">
                {{ changelogPaginationSummary }}
              </div>
              <div v-if="changelogTotalPages > 1" class="changelog-pagination-controls">
                <button
                  type="button"
                  class="btn-outline btn-sm"
                  :disabled="!canPreviousChangelogJump"
                  @click="loadChangelogPage(changelogCurrentPage - CHANGELOG_PAGE_JUMP_SIZE)"
                >
                  Previous 10
                </button>
                <button
                  type="button"
                  class="btn-outline btn-sm"
                  :disabled="!canPreviousChangelogPage"
                  @click="loadChangelogPage(changelogCurrentPage - 1)"
                >
                  Previous
                </button>
                <span class="changelog-page-count">
                  Page {{ changelogCurrentPage }} of {{ changelogTotalPages }}
                </span>
                <button
                  type="button"
                  class="btn-outline btn-sm"
                  :disabled="!canNextChangelogPage"
                  @click="loadChangelogPage(changelogCurrentPage + 1)"
                >
                  Next
                </button>
                <button
                  type="button"
                  class="btn-outline btn-sm"
                  :disabled="!canNextChangelogJump"
                  @click="loadChangelogPage(changelogCurrentPage + CHANGELOG_PAGE_JUMP_SIZE)"
                >
                  Next 10
                </button>
              </div>
              <button
                type="button"
                class="btn-outline btn-sm"
                :disabled="loadingChangelog"
                @click="refreshChangelog"
              >
                {{ loadingChangelog ? "Refreshing…" : "Refresh" }}
              </button>
            </div>
          </div>

          <div v-if="loadingChangelog" class="loading-state">Loading changelog…</div>
          <div v-else-if="changelogEntries.length === 0" class="empty-state">
            {{ changelogEmptyMessage }}
          </div>
          <div v-else class="changelog-list">
            <section
              v-for="group in changelogDayGroups"
              :key="group.key"
            >
              <div class="changelog-day-header">
                <h3>{{ group.label }}</h3>
                <span>{{ changelogDayEntryCountLabel(group) }}</span>
              </div>
              <div class="changelog-day-entries">
                <div
                  v-for="entry in group.entries"
                  :key="entry.id"
                  class="changelog-row"
                >
                  <div class="changelog-stamp">
                    <time class="changelog-time" :datetime="entry.savedAt || undefined">
                      {{ formatChangelogTime(entry.savedAt) }}
                    </time>
                    <span class="changelog-user">by {{ entry.savedBy || "unknown" }}</span>
                  </div>
                  <div class="changelog-main">
                    <div class="changelog-title">{{ changelogSectionLabel(entry) }}</div>
                    <div class="changelog-meta">
                      <span>{{ humanizeSectionType(entry.sectionType) }}</span>
                      <a
                        v-if="changelogPageHref(entry)"
                        class="changelog-page-link"
                        :href="changelogPageHref(entry)"
                      >
                        {{ changelogPageLabel(entry) }}
                      </a>
                      <span v-if="entry.revertedFromSavedAt">
                        reverted from {{ formatChangelogTime(entry.revertedFromSavedAt) }}
                      </span>
                    </div>
                  </div>
                  <div class="changelog-tags">
                    <span class="chip chip-muted">{{ changeKindLabel(entry.changeKind) }}</span>
                    <a
                      v-if="changelogOpenHref(entry)"
                      class="btn-outline btn-sm changelog-open-link"
                      :href="changelogOpenHref(entry)"
                    >
                      Open Section
                    </a>
                  </div>
                </div>
              </div>
            </section>
          </div>
          <div v-if="changelogTotalPages > 1" class="changelog-pagination-footer">
            <button
              type="button"
              class="btn-outline btn-sm"
              :disabled="!canPreviousChangelogJump"
              @click="loadChangelogPage(changelogCurrentPage - CHANGELOG_PAGE_JUMP_SIZE)"
            >
              Previous 10
            </button>
            <button
              type="button"
              class="btn-outline btn-sm"
              :disabled="!canPreviousChangelogPage"
              @click="loadChangelogPage(changelogCurrentPage - 1)"
            >
              Previous
            </button>
            <span class="changelog-page-count">
              Page {{ changelogCurrentPage }} of {{ changelogTotalPages }}
            </span>
            <button
              type="button"
              class="btn-outline btn-sm"
              :disabled="!canNextChangelogPage"
              @click="loadChangelogPage(changelogCurrentPage + 1)"
            >
              Next
            </button>
            <button
              type="button"
              class="btn-outline btn-sm"
              :disabled="!canNextChangelogJump"
              @click="loadChangelogPage(changelogCurrentPage + CHANGELOG_PAGE_JUMP_SIZE)"
            >
              Next 10
            </button>
          </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'tutorials'">
        <div class="config-card tutorials-panel">
          <div class="card-header tutorials-header">
            <div>
              <h2>Tutorials</h2>
              <p class="card-hint">Reusable tutorial checklists for admin knowledge transfer.</p>
            </div>
            <div class="tutorials-header-actions">
              <button type="button" class="btn-outline btn-sm" @click="openImportTutorialPicker">
                Import .md
              </button>
              <button type="button" class="btn-primary btn-sm" @click="openCreateTutorial">
                Create Tutorial
              </button>
              <input
                ref="tutorialImportInputRef"
                class="tutorial-import-input"
                type="file"
                accept=".md,text/markdown,text/plain"
                @change="importTutorialMarkdown"
              />
            </div>
          </div>

          <div v-if="tutorialMessage" class="status-message" :class="tutorialMessage.type">
            {{ tutorialMessage.text }}
          </div>

          <div v-if="tutorials.length > 0" class="tutorial-filters">
            <label class="tutorial-filter-field tutorial-filter-field--search">
              <span class="tutorial-filter-label">Search</span>
              <input
                v-model="tutorialSearchQuery"
                class="admin-control"
                type="search"
                autocomplete="off"
                placeholder="Title or description"
                aria-label="Search tutorials by title or description"
              />
            </label>
            <label class="tutorial-filter-field">
              <span class="tutorial-filter-label">Owner</span>
              <select
                v-model="tutorialOwnerFilter"
                class="admin-control"
                aria-label="Filter tutorials by owner"
              >
                <option value="all">All owners</option>
                <option
                  v-for="owner in tutorialOwnerFilterOptions"
                  :key="`tutorial-owner-${owner}`"
                  :value="owner"
                >
                  {{ owner }}
                </option>
              </select>
            </label>
            <label class="tutorial-filter-field">
              <span class="tutorial-filter-label">Scope</span>
              <select
                v-model="tutorialScopeFilter"
                class="admin-control"
                aria-label="Filter tutorials by scope"
              >
                <option value="all">All scopes</option>
                <option
                  v-for="option in tutorialScopeFilterOptions"
                  :key="`tutorial-scope-${option.value}`"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </label>
          </div>

          <div v-if="tutorials.length === 0" class="empty-state">
            No tutorials created yet.
          </div>

          <div v-else-if="filteredTutorials.length === 0" class="empty-state">
            No tutorials match the selected filters.
          </div>

          <div v-else class="tutorial-list">
            <div
              v-for="tutorial in filteredTutorials"
              :key="tutorial.id"
              class="tutorial-row"
              :class="{ 'is-active': isActiveTutorial(tutorial) }"
            >
              <div class="tutorial-main">
                <div class="tutorial-title">{{ tutorial.title }}</div>
                <p v-if="tutorial.description" class="tutorial-description">
                  {{ tutorial.description }}
                </p>
                <div class="tutorial-meta">
                  <span class="chip chip-muted">Owner: {{ tutorial.owner || "unknown" }}</span>
                  <span class="chip chip-muted">{{ tutorialScopeLabel(tutorial.scope) }}</span>
                  <span class="chip chip-muted">{{ tutorialStepCountLabel(tutorial) }}</span>
                  <span v-if="tutorial.updated_at" class="chip chip-muted">
                    Updated {{ formatTutorialTime(tutorial.updated_at) }}
                  </span>
                </div>
              </div>
              <div class="tutorial-actions">
                <button type="button" class="btn-primary btn-sm" @click="startTutorialFromList(tutorial)">
                  Start
                </button>
                <button
                  type="button"
                  class="btn-outline btn-sm"
                  @click="exportTutorial(tutorial)"
                >
                  Export
                </button>
                <button
                  v-if="tutorial.can_edit"
                  type="button"
                  class="btn-outline btn-sm"
                  @click="openEditTutorial(tutorial)"
                >
                  Edit
                </button>
                <button
                  v-if="tutorial.can_edit"
                  type="button"
                  class="btn-danger btn-sm"
                  :disabled="deletingTutorialId === tutorial.id"
                  @click="deleteTutorial(tutorial)"
                >
                  {{ deletingTutorialId === tutorial.id ? "Deleting..." : "Delete" }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'planning'">
        <div class="planning-toolbar">
          <label class="planning-area-field">
            <span class="all-todo-filter-label">Area</span>
            <select v-model="planningArea" class="admin-control">
              <option value="it">IT</option>
              <option value="content">Content</option>
            </select>
          </label>
        </div>
        <div class="planning-board">
          <div v-for="priority in priorities" :key="`${planningArea}-${priority}`" class="planning-column">
            <div class="planning-column-head">
              <h3 class="planning-priority-heading" :title="priorityIconLabel(priority)">
                <font-awesome-icon :icon="priorityIcon(priority)" aria-hidden="true" />
                <span class="sr-only">{{ priorityIconLabel(priority) }}</span>
              </h3>
              <span class="count-badge">{{ planningColumns[planningArea][priority].length }}</span>
            </div>
            <draggable
              :list="planningColumns[planningArea][priority]"
              item-key="uid"
              :group="{ name: `planning-${planningArea}` }"
              class="planning-dropzone"
              @end="onPlanningDragEnd(planningArea, $event)"
            >
              <template #item="{ element }">
                <div class="planning-card">
                  <div class="planning-card-text">{{ element.text }}</div>
                  <div class="planning-card-meta">
                    <span>{{ element.sourceLabel }}</span>
                    <span class="planning-card-tag" :title="todoTagIconLabel(element.tag)">
                      <font-awesome-icon
                        v-if="todoTagIcon(element.tag)"
                        :icon="todoTagIcon(element.tag)"
                        class="todo-tag-icon"
                        aria-hidden="true"
                      />
                      <span>{{ todoTagText(element.tag) }}</span>
                    </span>
                  </div>
                </div>
              </template>
            </draggable>
          </div>
        </div>
        <div class="planning-done-zone">
          <div class="planning-done-head">
            <h3>Done</h3>
            <p class="card-hint">Drag a ticket here to mark it done and remove it from planning.</p>
          </div>
          <draggable
            :list="doneDropBuckets[planningArea]"
            item-key="uid"
            :group="{ name: `planning-${planningArea}` }"
            :sort="false"
            class="planning-done-dropzone"
            data-done-dropzone="true"
            @change="onPlanningDoneDrop(planningArea, $event)"
          >
            <template #item="{ element }">
              <div class="planning-card">
                <div class="planning-card-text">{{ element.text }}</div>
                <div class="planning-card-meta">
                  <span>{{ element.sourceLabel }}</span>
                  <span class="planning-card-tag" :title="todoTagIconLabel(element.tag)">
                    <font-awesome-icon
                      v-if="todoTagIcon(element.tag)"
                      :icon="todoTagIcon(element.tag)"
                      class="todo-tag-icon"
                      aria-hidden="true"
                    />
                    <span>{{ todoTagText(element.tag) }}</span>
                  </span>
                </div>
              </div>
            </template>
          </draggable>
        </div>
      </template>

      <template v-else-if="activeTab === 'tags'">
        <div class="config-card">
          <div class="card-header">
            <h2>Todo Tags</h2>
            <p class="card-hint">Manage available tags and assign each to IT or Content planning.</p>
          </div>

          <div class="tag-create">
            <input
              v-model="newTagId"
              class="admin-control"
              type="text"
              placeholder="New tag id (e.g. seoTask)"
            />
            <select v-model="newTagArea" class="admin-control">
              <option value="it">IT</option>
              <option value="content">Content</option>
            </select>
            <button class="btn-primary btn-sm" :disabled="savingTags" @click="addTag">
              {{ savingTags ? "Saving…" : "Add Tag" }}
            </button>
          </div>

          <div v-if="tagMessage" class="status-message" :class="tagMessage.type">{{ tagMessage.text }}</div>

          <div class="tag-list todo-tag-edit-list">
            <div v-for="tag in todoTags" :key="`tag-${tag.id}`" class="tag-row">
              <div class="tag-label">
                <div class="tag-name" :title="todoTagIconLabel(tag.id)">
                  <font-awesome-icon
                    v-if="todoTagIcon(tag.id)"
                    :icon="todoTagIcon(tag.id)"
                    class="todo-tag-icon"
                    aria-hidden="true"
                  />
                  <span>{{ todoTagText(tag.id) }}</span>
                </div>
                <div class="tag-meta">
                  {{ isDefaultTodoTag(tag.id) ? "default" : "custom" }}
                </div>
              </div>
              <select
                class="admin-control tag-area-select"
                :value="tag.area"
                :disabled="isDefaultTodoTag(tag.id) || savingTags"
                @change="updateTagArea(tag.id, $event.target.value)"
              >
                <option value="it">IT</option>
                <option value="content">Content</option>
              </select>
              <button
                class="btn-danger btn-sm"
                :disabled="isDefaultTodoTag(tag.id) || savingTags"
                @click="removeTag(tag.id)"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import draggable from "vuedraggable";
import * as api from "../../services/api.js";
import AdminPageTabs from "../../components/admin/AdminPageTabs.vue";
import TodoIconSelect from "../../components/admin/TodoIconSelect.vue";
import { getInternalRole, getUser, hasInternalRole } from "../../services/auth.js";
import { useStore } from "../../store/store.js";
import {
  TUTORIAL_SCOPE_OPTIONS,
  useAdminTutorialOverlay,
} from "../../composables/useAdminTutorialOverlay.js";
import {
  downloadTutorialMarkdown,
  parseTutorialMarkdown,
} from "../../utils/adminTutorialMarkdown.js";
import {
  DEFAULT_TODO_TAG_ID,
  TODO_PRIORITY_VALUES,
  isDefaultTodoTag,
  normalizeTodoList,
  normalizeTodoTagId,
  normalizeTodoTags,
  serializeTodoList,
  todoPriorityIcon as priorityIcon,
  todoPriorityIconLabel as priorityIconLabel,
  todoPrioritySelectOption,
  todoTagIcon,
  todoTagIconLabel,
  todoTagSelectOption,
  todoTagText,
} from "../../utils/adminTodos.js";
import {
  formatInstantInServerTimezone,
  getServerTimezone,
  parseRevisionTimestamp,
} from "../../utils/revisionTime.js";
import { convertKeysToCamel } from "../../utils/caseConversion.js";

const { state } = useStore();
const route = useRoute();
const router = useRouter();
const {
  state: tutorialOverlayState,
  openTutorialBuilder,
  startTutorial,
  stopTutorial,
} = useAdminTutorialOverlay();

const canManageDevops = computed(() => Boolean(state.canAdminGeneral) || hasInternalRole("admin_general"));
const tabs = computed(() => {
  const available = [
    { id: "changelog", label: "Changelog", to: "/admin/devops/changelog" },
    { id: "todos", label: "Todos", to: "/admin/devops/todos" },
  ];
  if (canManageDevops.value) {
    available.push({ id: "planning", label: "Planning", to: "/admin/devops/planning" });
  }
  if (canManageDevops.value) {
    available.push({ id: "tags", label: "Tags", to: "/admin/devops/tags" });
  }
  available.push(
    { id: "tutorials", label: "Tutorials", to: "/admin/devops/tutorials" },
  );
  return available;
});
const DEVOPS_TAB_BY_SLUG = {
  changelog: "changelog",
  todos: "todos",
  "all-todos": "todos",
  planning: "planning",
  "planning-it": "planning",
  "planning-content": "planning",
  tutorials: "tutorials",
  tags: "tags",
};
const CHANGELOG_PAGE_SIZE = 50;
const CHANGELOG_PAGE_JUMP_SIZE = 10;

const priorities = [...TODO_PRIORITY_VALUES];
const todoPrioritySelectOptions = priorities.map((priority) => todoPrioritySelectOption(priority));
const activeTab = computed(() => {
  const routeTab = getRouteTab();
  const availableTabs = tabs.value;
  return availableTabs.some((entry) => entry.id === routeTab)
    ? routeTab
    : (availableTabs[0]?.id || "changelog");
});
const loading = ref(true);
const error = ref("");
const sources = ref([]);
const changelogEntries = ref([]);
const tutorials = ref([]);
const tutorialScopeOptions = ref([...TUTORIAL_SCOPE_OPTIONS]);
const loadingChangelog = ref(false);
const changelogPageSlug = ref("");
const changelogPageOptions = ref([]);
const changelogLimit = ref(CHANGELOG_PAGE_SIZE);
const changelogOffset = ref(0);
const changelogTotal = ref(0);
const changelogHasMore = ref(false);
const todoTags = ref(normalizeTodoTags([]));
const savingTags = ref(false);
const tagMessage = ref(null);
const newTagId = ref("");
const newTagArea = ref("content");
const allTodoTypeFilter = ref("all");
const allTodoPriorityFilter = ref("all");
const allTodoDoneFilter = ref("open");
const allTodoCreatorFilter = ref("all");
const allTodoGroupBy = ref("none");
const allTodoSelectedTags = ref([]);
const newUnassignedTodoText = ref("");
const newUnassignedTodoTag = ref(DEFAULT_TODO_TAG_ID);
const newUnassignedTodoPriority = ref("needed");
const addingUnassignedTodo = ref(false);
const editingTodoUid = ref("");
const editingTodoText = ref("");
const todoCommentDrafts = reactive({});
const todoSavePendingByUid = reactive({});
const tutorialMessage = ref(null);
const deletingTutorialId = ref("");
const tutorialImportInputRef = ref(null);
const tutorialSearchQuery = ref("");
const tutorialOwnerFilter = ref("all");
const tutorialScopeFilter = ref("all");
const planningArea = ref("it");
const planningColumns = reactive({
  it: { urgent: [], needed: [], optional: [] },
  content: { urgent: [], needed: [], optional: [] },
});
const doneDropBuckets = reactive({
  it: [],
  content: [],
});
const currentEditorName = computed(() => {
  const user = getUser?.();
  return user?.name || user?.username || "unknown";
});

const defaultTodoTagId = computed(() => {
  if (todoTags.value.some((tag) => tag.id === "text")) return "text";
  return todoTags.value[0]?.id || DEFAULT_TODO_TAG_ID;
});

const allTodoPriorityFilterOptions = computed(() => [
  { value: "all", label: "All", icon: null, iconLabel: "All urgencies" },
  ...todoPrioritySelectOptions,
]);

const todoTagSelectOptions = computed(() =>
  todoTags.value.map((tag) => todoTagSelectOption(tag.id))
);

const tagAreaById = computed(() => {
  const map = {};
  for (const tag of todoTags.value) {
    map[tag.id] = tag.area;
  }
  return map;
});

const sourceByKey = computed(() =>
  Object.fromEntries(sources.value.map((source) => [source.key, source]))
);

const selectedChangelogPageOption = computed(() => {
  const selected = String(changelogPageSlug.value || "").trim();
  if (!selected) return null;
  return changelogPageOptions.value.find((option) => option.slug === selected) || null;
});

const changelogSelectedPageLabel = computed(() => (
  selectedChangelogPageOption.value?.label || pagePathFromSlug(changelogPageSlug.value)
));

const changelogCardHint = computed(() => {
  if (!changelogPageSlug.value) return "Newest section revisions across the site.";
  return `Newest section revisions for ${changelogSelectedPageLabel.value}.`;
});

const changelogEmptyMessage = computed(() => {
  if (!changelogPageSlug.value) return "No section revisions have been logged yet.";
  return `No section revisions have been logged for ${changelogSelectedPageLabel.value}.`;
});

const changelogCurrentPage = computed(() => {
  const limit = Math.max(1, Number(changelogLimit.value) || CHANGELOG_PAGE_SIZE);
  return Math.floor(Math.max(0, Number(changelogOffset.value) || 0) / limit) + 1;
});

const changelogTotalPages = computed(() => {
  const limit = Math.max(1, Number(changelogLimit.value) || CHANGELOG_PAGE_SIZE);
  return Math.max(1, Math.ceil(Math.max(0, Number(changelogTotal.value) || 0) / limit));
});

const changelogRangeStart = computed(() => (
  changelogTotal.value > 0 ? changelogOffset.value + 1 : 0
));

const changelogRangeEnd = computed(() => {
  const fallbackEnd = changelogOffset.value + changelogEntries.value.length;
  if (changelogTotal.value <= 0) return fallbackEnd;
  return Math.min(fallbackEnd, changelogTotal.value);
});

const changelogPaginationSummary = computed(() => {
  if (changelogTotal.value <= 0) return "";
  return `${changelogRangeStart.value}-${changelogRangeEnd.value} of ${changelogTotal.value}`;
});

const canPreviousChangelogPage = computed(() => (
  changelogOffset.value > 0 && !loadingChangelog.value
));

const canNextChangelogPage = computed(() => (
  changelogHasMore.value && !loadingChangelog.value
));

const canPreviousChangelogJump = computed(() => (
  changelogCurrentPage.value > 1 && !loadingChangelog.value
));

const canNextChangelogJump = computed(() => (
  changelogCurrentPage.value < changelogTotalPages.value && !loadingChangelog.value
));

const changelogDayGroups = computed(() => {
  const groups = [];
  const groupByKey = new Map();

  for (const entry of changelogEntries.value) {
    const day = changelogDayMeta(entry.savedAt);
    let group = groupByKey.get(day.key);
    if (!group) {
      group = { ...day, entries: [] };
      groupByKey.set(day.key, group);
      groups.push(group);
    }
    group.entries.push(entry);
  }

  return groups;
});

const allTodoEntries = computed(() => {
  const entries = [];
  for (const source of sources.value) {
    for (const todo of source.todos) {
      const tagArea = tagAreaById.value[todo.tag] === "it" ? "it" : "content";
      entries.push({
        uid: `${source.key}:${todo.id}`,
        source,
        todo,
        tagArea,
      });
    }
  }
  return entries.sort(compareAllTodoEntries);
});

function sourceTodoSortRank(source) {
  return source?.type === "unassigned" || source?.key === "__unassigned__" ? 0 : 1;
}

function todoCreatedTime(todo) {
  return todo?.createdAt ? parseRevisionTimestamp(todo.createdAt)?.getTime() || 0 : 0;
}

function compareAllTodoEntries(left, right) {
  const sourceRankDiff = sourceTodoSortRank(left?.source) - sourceTodoSortRank(right?.source);
  if (sourceRankDiff !== 0) return sourceRankDiff;
  const sourceCmp = String(left?.source?.label || "").localeCompare(String(right?.source?.label || ""));
  if (sourceCmp !== 0) return sourceCmp;
  return todoCreatedTime(right?.todo) - todoCreatedTime(left?.todo);
}

function todoGroupSortRank(group) {
  const key = String(group?.key || "");
  return key === "__unassigned__" || key === "page:__unassigned__" ? 0 : 1;
}

function compareTodoGroups(left, right) {
  const rankDiff = todoGroupSortRank(left) - todoGroupSortRank(right);
  if (rankDiff !== 0) return rankDiff;
  return String(left?.label || "").localeCompare(String(right?.label || ""));
}

function normalizeCreator(value) {
  return String(value || "").trim() || "unknown";
}

function normalizeCreatorToken(value) {
  return normalizeCreator(value).toLowerCase();
}

function matchesTodoFilters(entry, { ignoreTags = false, ignoreCreator = false } = {}) {
  if (allTodoTypeFilter.value !== "all" && entry.tagArea !== allTodoTypeFilter.value) return false;
  if (allTodoPriorityFilter.value !== "all" && entry.todo.priority !== allTodoPriorityFilter.value) return false;
  if (allTodoDoneFilter.value === "open" && entry.todo.done) return false;
  if (allTodoDoneFilter.value === "done" && !entry.todo.done) return false;

  if (!ignoreTags) {
    const selectedTags = new Set(allTodoSelectedTags.value);
    if (selectedTags.size > 0 && !selectedTags.has(entry.todo.tag)) return false;
  }

  if (!ignoreCreator && allTodoCreatorFilter.value !== "all") {
    if (normalizeCreatorToken(entry.todo.createdBy) !== normalizeCreatorToken(allTodoCreatorFilter.value)) {
      return false;
    }
  }

  return true;
}

const allTodoTagFilterOptions = computed(() => {
  const counts = new Map();
  for (const entry of allTodoEntries.value) {
    if (!matchesTodoFilters(entry, { ignoreTags: true })) continue;
    counts.set(entry.todo.tag, (counts.get(entry.todo.tag) || 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([id, count]) => ({ id, count }))
    .sort((left, right) => left.id.localeCompare(right.id));
});

const allTodoCreatorFilterOptions = computed(() => {
  const counts = new Map();
  for (const entry of allTodoEntries.value) {
    if (!matchesTodoFilters(entry, { ignoreCreator: true })) continue;
    const creator = normalizeCreator(entry.todo.createdBy);
    counts.set(creator, (counts.get(creator) || 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([value, count]) => ({ value, count }))
    .sort((left, right) => left.value.localeCompare(right.value));
});

const filteredAllTodoEntries = computed(() => {
  return allTodoEntries.value.filter((entry) => matchesTodoFilters(entry));
});

const tutorialOwnerFilterOptions = computed(() => {
  return Array.from(new Set(tutorials.value.map((tutorial) => normalizeTutorialOwner(tutorial))))
    .sort((left, right) => left.localeCompare(right));
});

const tutorialScopeFilterOptions = computed(() => {
  const availableScopes = new Set(tutorials.value.map((tutorial) => normalizeTutorialScope(tutorial)));
  const knownValues = new Set(TUTORIAL_SCOPE_OPTIONS.map((option) => option.value));
  const knownOptions = TUTORIAL_SCOPE_OPTIONS.filter((option) => availableScopes.has(option.value));
  const customOptions = Array.from(availableScopes)
    .filter((scope) => scope && !knownValues.has(scope))
    .sort((left, right) => left.localeCompare(right))
    .map((scope) => ({ value: scope, label: scope }));
  return [...knownOptions, ...customOptions];
});

const filteredTutorials = computed(() => {
  const query = tutorialSearchQuery.value.trim().toLowerCase();
  const ownerFilter = tutorialOwnerFilter.value;
  const scopeFilter = tutorialScopeFilter.value;
  return tutorials.value.filter((tutorial) => {
    if (ownerFilter !== "all" && normalizeTutorialOwner(tutorial) !== ownerFilter) return false;
    if (scopeFilter !== "all" && normalizeTutorialScope(tutorial) !== scopeFilter) return false;
    if (!query) return true;
    const title = String(tutorial?.title || "").toLowerCase();
    const description = String(tutorial?.description || "").toLowerCase();
    return title.includes(query) || description.includes(query);
  });
});

const groupedAllTodoEntries = computed(() => {
  if (allTodoGroupBy.value === "none") return [];

  const groups = new Map();
  const pushGroupEntry = (key, label, entry) => {
    if (!groups.has(key)) {
      groups.set(key, { key, label, entries: [] });
    }
    groups.get(key).entries.push(entry);
  };

  if (allTodoGroupBy.value === "section") {
    for (const entry of filteredAllTodoEntries.value) {
      pushGroupEntry(entry.source.key, entry.source.label, entry);
    }
  } else {
    for (const entry of filteredAllTodoEntries.value) {
      const sourceUsage = Array.isArray(entry.source.usage) ? entry.source.usage : [];
      const slugs = sourceUsage
        .map((item) => String(item?.slug || "").trim())
        .filter(Boolean);
      if (slugs.length === 0) {
        pushGroupEntry("page:__unassigned__", "Unassigned Page", entry);
        continue;
      }
      for (const slug of new Set(slugs)) {
        pushGroupEntry(`page:${slug}`, `/${slug}`, entry);
      }
    }
  }

  const sortedGroups = Array.from(groups.values())
    .map((group) => ({
      ...group,
      entries: [...group.entries].sort(compareAllTodoEntries),
    }))
    .sort(compareTodoGroups);
  return sortedGroups;
});

function setActiveTab(tab) {
  const availableTabs = tabs.value;
  const target = availableTabs.find((item) => item.id === tab) || availableTabs[0];
  router.push(target?.to || "/admin/devops/changelog");
}

function getRouteTab() {
  const slug = String(route.path || "").split("/")[3] || "";
  return DEVOPS_TAB_BY_SLUG[slug] || "";
}

function normalizePlanningArea(value) {
  return String(value || "").trim().toLowerCase() === "content" ? "content" : "it";
}

function todoRowClasses(todo) {
  const priority = TODO_PRIORITY_VALUES.includes(todo?.priority) ? todo.priority : "needed";
  return [
    `ticket-priority-${priority}`,
    todo?.done ? "ticket-state-done" : "ticket-state-open",
  ];
}

function humanizeSectionType(sectionType) {
  return String(sectionType || "section")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function resolveSectionLabel(section) {
  const title = section?.title;
  const titleText = typeof title === "string"
    ? title
    : (title?.de || title?.en || "");
  if (titleText.trim()) return titleText.trim();
  const placeholder = String(section?.title_placeholder || "").trim();
  if (placeholder) return placeholder;
  return `${humanizeSectionType(section?.section_type)} (${String(section?._id || "").slice(-6)})`;
}

function resolveHeaderLabel(header) {
  const name = String(header?.name || "").trim();
  if (name) return name;
  const title = header?.hero_title;
  const titleText = typeof title === "string"
    ? title
    : (title?.de || title?.en || "");
  if (titleText.trim()) return titleText.trim();
  return `Header (${String(header?.id || "").slice(-6)})`;
}

function normalizeUsageSlug(value) {
  const normalized = String(value || "").trim().replace(/^\/+|\/+$/g, "");
  return normalized || "landing";
}

function pagePathFromSlug(slug) {
  const normalized = normalizeUsageSlug(slug);
  if (normalized === "landing") return "/";
  return `/${normalized}`;
}

function normalizePageHref(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
  const path = raw.replace(/^\/+/, "").trim();
  if (!path || path === "landing") return "/";
  return `/${path}`;
}

function resolvePageTitle(page) {
  const title = page?.title;
  if (typeof title === "string" && title.trim()) return title.trim();
  const titleText = String(title?.de || title?.en || "").trim();
  if (titleText) return titleText;
  const menuTitle = String(page?.menuTitle || "").trim();
  if (menuTitle) return menuTitle;
  return pagePathFromSlug(page?.slug);
}

function normalizeChangelogPageOptions(rawPages) {
  const optionsBySlug = new Map();
  for (const rawPage of Array.isArray(rawPages) ? rawPages : []) {
    const page = rawPage && typeof rawPage === "object" && !Array.isArray(rawPage)
      ? convertKeysToCamel(rawPage)
      : {};
    const slug = normalizeUsageSlug(page?.slug);
    if (optionsBySlug.has(slug)) continue;
    const path = pagePathFromSlug(slug);
    const title = resolvePageTitle(page);
    optionsBySlug.set(slug, {
      slug,
      path,
      title,
      label: title && title !== path ? `${path} · ${title}` : path,
    });
  }
  return Array.from(optionsBySlug.values()).sort((left, right) => {
    if (left.slug === "landing") return -1;
    if (right.slug === "landing") return 1;
    return left.path.localeCompare(right.path);
  });
}

function buildSourceOpenHref(type, id, usage) {
  if (type !== "section" && type !== "header") return "";
  const sourceUsage = Array.isArray(usage) ? usage : [];
  const firstUsage = sourceUsage.find((item) => String(item?.slug || "").trim());
  if (!firstUsage?.slug) return "";

  const params = new URLSearchParams({ from: "devops_todo" });
  if (type === "section") params.set("focus_section_id", String(id || "").trim());
  if (type === "header") params.set("focus_header_id", String(id || "").trim());
  const query = params.toString();
  const path = pagePathFromSlug(firstUsage.slug);
  return query ? `${path}?${query}` : path;
}

function buildSourceOpenLabel(type) {
  return type === "header" ? "Open Header" : "Open Section";
}

function buildPlanningColumns() {
  const next = {
    it: { urgent: [], needed: [], optional: [] },
    content: { urgent: [], needed: [], optional: [] },
  };
  doneDropBuckets.it.splice(0, doneDropBuckets.it.length);
  doneDropBuckets.content.splice(0, doneDropBuckets.content.length);

  for (const source of sources.value) {
    for (const todo of source.todos) {
      if (todo.done) continue;
      const area = tagAreaById.value[todo.tag];
      if (area !== "it" && area !== "content") continue;
      const priority = TODO_PRIORITY_VALUES.includes(todo.priority) ? todo.priority : "needed";
      next[area][priority].push({
        uid: `${source.key}:${todo.id}`,
        sourceKey: source.key,
        todoId: todo.id,
        sourceLabel: source.label,
        text: todo.text,
        tag: todo.tag,
        priorityRank: Number.isFinite(todo.priorityRank) ? todo.priorityRank : 0,
        createdAt: todo.createdAt || null,
      });
    }
  }

  for (const area of ["it", "content"]) {
    for (const priority of priorities) {
      next[area][priority].sort((left, right) => {
        const rankDiff = (left.priorityRank ?? 0) - (right.priorityRank ?? 0);
        if (rankDiff !== 0) return rankDiff;
        const sourceRankDiff =
          sourceTodoSortRank(sourceByKey.value[left.sourceKey]) -
          sourceTodoSortRank(sourceByKey.value[right.sourceKey]);
        if (sourceRankDiff !== 0) return sourceRankDiff;
        const leftTs = left.createdAt ? parseRevisionTimestamp(left.createdAt)?.getTime() || 0 : 0;
        const rightTs = right.createdAt ? parseRevisionTimestamp(right.createdAt)?.getTime() || 0 : 0;
        return rightTs - leftTs;
      });
      planningColumns[area][priority].splice(0, planningColumns[area][priority].length, ...next[area][priority]);
    }
  }
}

function currentUserIdentityTokens() {
  const user = getUser?.();
  const values = [
    String(user?.username || "").trim(),
    String(user?.name || "").trim(),
  ].filter(Boolean);
  return new Set(values.map((value) => value.toLowerCase()));
}

function isTodoOwnedByCurrentUser(todo) {
  const owner = String(todo?.createdBy || "").trim().toLowerCase();
  if (!owner) return false;
  return currentUserIdentityTokens().has(owner);
}

function isTodoSavePending(uid) {
  return Boolean(todoSavePendingByUid[uid]);
}

function todoCommentList(todo) {
  return Array.isArray(todo?.comments) ? todo.comments : [];
}

function todoCommentMeta(comment) {
  const creator = normalizeCreator(comment?.createdBy);
  const dateLabel = formatInstantInServerTimezone(comment?.createdAt, { hour12: false });
  if (!dateLabel) return creator;
  return `${creator} · ${dateLabel}`;
}

function normalizeChangelogEntry(raw) {
  return {
    id: String(raw?.id || `${raw?.entity_id || ""}:${raw?.saved_at || ""}`),
    sectionId: String(raw?.section_id || raw?.entity_id || ""),
    sectionType: String(raw?.section_type || ""),
    sectionLabel: String(raw?.section_label || "").trim(),
    pageSlug: String(raw?.page_slug || "").trim(),
    pageUrl: normalizePageHref(raw?.page_url),
    revisionId: String(raw?.revision_id || ""),
    savedAt: raw?.saved_at || null,
    savedBy: String(raw?.saved_by || "unknown").trim() || "unknown",
    changeKind: String(raw?.change_kind || "").trim(),
    revertedFromSavedAt: raw?.reverted_from_saved_at || null,
  };
}

function normalizeChangelogEntries(payload) {
  const rawItems = Array.isArray(payload?.items) ? payload.items : (Array.isArray(payload) ? payload : []);
  return rawItems
    .map((entry) => normalizeChangelogEntry(entry))
    .sort((left, right) => {
      const leftTs = left.savedAt ? parseRevisionTimestamp(left.savedAt)?.getTime() || 0 : 0;
      const rightTs = right.savedAt ? parseRevisionTimestamp(right.savedAt)?.getTime() || 0 : 0;
      return rightTs - leftTs;
    });
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
  const rawSteps = Array.isArray(raw?.steps) ? raw.steps : [];
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
    steps: rawSteps
      .map((step, index) => normalizeTutorialStep(step, index))
      .sort((left, right) => (left.order ?? 0) - (right.order ?? 0)),
  };
}

function normalizeTutorials(payload) {
  const rawItems = Array.isArray(payload?.items) ? payload.items : (Array.isArray(payload) ? payload : []);
  return rawItems
    .map((entry) => normalizeTutorial(entry))
    .filter((entry) => entry.id && entry.steps.length > 0)
    .sort((left, right) => left.title.localeCompare(right.title));
}

function applyChangelogPayload(payload) {
  changelogEntries.value = normalizeChangelogEntries(payload);

  const nextLimit = Number(payload?.limit);
  changelogLimit.value = Number.isFinite(nextLimit) && nextLimit > 0
    ? nextLimit
    : CHANGELOG_PAGE_SIZE;

  const nextOffset = Number(payload?.offset);
  changelogOffset.value = Number.isFinite(nextOffset) && nextOffset >= 0
    ? nextOffset
    : 0;

  const fallbackTotal = changelogOffset.value + changelogEntries.value.length;
  const nextTotal = Number(payload?.total);
  changelogTotal.value = Number.isFinite(nextTotal) && nextTotal >= 0
    ? nextTotal
    : fallbackTotal;

  changelogHasMore.value = typeof payload?.has_more === "boolean"
    ? payload.has_more
    : changelogOffset.value + changelogEntries.value.length < changelogTotal.value;
}

function applyTutorialPayload(payload) {
  tutorials.value = normalizeTutorials(payload);
  const rawScopeOptions = Array.isArray(payload?.scope_options) ? payload.scope_options : [];
  const allowed = rawScopeOptions
    .map((scope) => String(scope || "").trim())
    .filter(Boolean);
  tutorialScopeOptions.value = TUTORIAL_SCOPE_OPTIONS.filter((option) => (
    allowed.length === 0 || allowed.includes(option.value)
  ));
}

function formatChangelogTime(value) {
  return formatInstantInServerTimezone(value, { hour12: false }) || "Unknown time";
}

function changelogDayMeta(value) {
  const parsed = parseRevisionTimestamp(value);
  if (!parsed) {
    return {
      key: "unknown",
      label: "Unknown date",
    };
  }

  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: getServerTimezone(),
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(parsed);
    const getPart = (type) => parts.find((part) => part.type === type)?.value || "";
    const key = [getPart("year"), getPart("month"), getPart("day")].join("-");
    const label = parsed.toLocaleDateString("de-DE", {
      timeZone: getServerTimezone(),
      weekday: "long",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    return {
      key: key || "unknown",
      label: label || "Unknown date",
    };
  } catch {
    return {
      key: parsed.toISOString().slice(0, 10),
      label: parsed.toISOString().slice(0, 10),
    };
  }
}

function changelogDayEntryCountLabel(group) {
  const count = Array.isArray(group?.entries) ? group.entries.length : 0;
  return count === 1 ? "1 change" : `${count} changes`;
}

function formatTutorialTime(value) {
  return formatInstantInServerTimezone(value, { hour12: false }) || "unknown time";
}

function normalizeTutorialOwner(tutorial) {
  return String(tutorial?.owner || "unknown").trim() || "unknown";
}

function normalizeTutorialScope(tutorial) {
  return String(tutorial?.scope || "content").trim() || "content";
}

function tutorialScopeLabel(scope) {
  return TUTORIAL_SCOPE_OPTIONS.find((option) => option.value === scope)?.label || scope || "Content";
}

function tutorialStepCountLabel(tutorial) {
  const count = Array.isArray(tutorial?.steps) ? tutorial.steps.length : 0;
  return count === 1 ? "1 step" : `${count} steps`;
}

function changeKindLabel(kind) {
  if (kind === "content") return "Content";
  if (kind === "design") return "Design";
  if (kind === "both") return "Content + Design";
  return "Revision";
}

function changelogSource(entry) {
  return sourceByKey.value[`section:${entry?.sectionId || ""}`] || null;
}

function changelogSectionLabel(entry) {
  return changelogSource(entry)?.label || entry?.sectionLabel || `Section (${String(entry?.sectionId || "").slice(-6)})`;
}

function changelogPageHref(entry) {
  const entryHref = normalizePageHref(entry?.pageUrl);
  if (entryHref) return entryHref;
  const source = changelogSource(entry);
  const sourceUsage = Array.isArray(source?.usage) ? source.usage : [];
  const firstUsage = sourceUsage.find((item) => String(item?.slug || "").trim());
  return firstUsage?.slug ? pagePathFromSlug(firstUsage.slug) : "";
}

function changelogPageLabel(entry) {
  return changelogPageHref(entry);
}

function changelogOpenHref(entry) {
  const sourceHref = changelogSource(entry)?.openHref || "";
  if (sourceHref) return sourceHref;
  const pageHref = changelogPageHref(entry);
  const sectionId = String(entry?.sectionId || "").trim();
  if (!pageHref || !sectionId) return "";
  const params = new URLSearchParams({
    from: "devops_changelog",
    focus_section_id: sectionId,
  });
  return `${pageHref}${pageHref.includes("?") ? "&" : "?"}${params.toString()}`;
}

function startTodoEdit(entry) {
  if (!isTodoOwnedByCurrentUser(entry?.todo)) return;
  editingTodoUid.value = entry.uid;
  editingTodoText.value = String(entry?.todo?.text || "");
}

function cancelTodoEdit() {
  editingTodoUid.value = "";
  editingTodoText.value = "";
}

async function updateTodoEntry(entry, updater, fallbackMessage) {
  const source = sourceByKey.value[entry?.source?.key];
  if (!source || typeof updater !== "function") return false;
  const todoId = String(entry?.todo?.id || "").trim();
  if (!todoId) return false;

  const hasTodo = source.todos.some((todo) => String(todo?.id || "") === todoId);
  if (!hasTodo) return false;

  source.todos = normalizeSourceTodos(
    source.todos.map((todo) => (
      String(todo?.id || "") === todoId
        ? updater({ ...todo })
        : todo
    ))
  );

  todoSavePendingByUid[entry.uid] = true;
  try {
    await saveSource(source.key);
    buildPlanningColumns();
    return true;
  } catch (err) {
    console.error("Failed to update todo entry:", err);
    error.value = err?.message || fallbackMessage || "Failed to update todo.";
    await loadData();
    return false;
  } finally {
    delete todoSavePendingByUid[entry.uid];
  }
}

async function saveTodoEdit(entry) {
  if (!isTodoOwnedByCurrentUser(entry?.todo)) return;
  const nextText = String(editingTodoText.value || "").trim();
  if (!nextText) return;
  if (nextText === String(entry?.todo?.text || "").trim()) {
    cancelTodoEdit();
    return;
  }

  const saved = await updateTodoEntry(
    entry,
    (todo) => ({ ...todo, text: nextText }),
    "Failed to update todo text."
  );
  if (saved) cancelTodoEdit();
}

async function addTodoComment(entry) {
  if (isTodoOwnedByCurrentUser(entry?.todo)) return;
  const draft = String(todoCommentDrafts[entry.uid] || "").trim();
  if (!draft) return;
  const nowIso = new Date().toISOString();
  const nextComment = {
    id: `comment-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    text: draft,
    createdBy: currentEditorName.value,
    createdAt: nowIso,
  };

  const saved = await updateTodoEntry(
    entry,
    (todo) => ({
      ...todo,
      comments: [...todoCommentList(todo), nextComment],
    }),
    "Failed to add comment."
  );
  if (saved) {
    todoCommentDrafts[entry.uid] = "";
  }
}

function normalizeSourceTodos(rawTodos) {
  return normalizeTodoList(rawTodos, { defaultTagId: defaultTodoTagId.value });
}

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const [sections, headers, pages, config, changelog, tutorialPayload] = await Promise.all([
      api.listSectionsWithUsage({ limit: 500, typeData: "admin_todos" }),
      api.listHeadersWithUsage({ limit: 500 }),
      api.listPages({ limit: 5000, includeHidden: true }),
      api.getAdminDevopsConfig(),
      api.getAdminDevopsChangelog({
        limit: CHANGELOG_PAGE_SIZE,
        offset: 0,
        pageSlug: changelogPageSlug.value,
      }),
      api.getAdminDevopsTutorials(),
    ]);

    todoTags.value = normalizeTodoTags(config?.todo_tags || []);
    changelogPageOptions.value = normalizeChangelogPageOptions(pages);
    if (
      changelogPageSlug.value
      && !changelogPageOptions.value.some((option) => option.slug === changelogPageSlug.value)
    ) {
      changelogPageSlug.value = "";
    }
    applyChangelogPayload(changelog);
    applyTutorialPayload(tutorialPayload);

    const nextSources = [];
    for (const section of sections || []) {
      nextSources.push({
        key: `section:${section._id}`,
        type: "section",
        id: section._id,
        sectionType: section.section_type || "",
        label: resolveSectionLabel(section),
        usage: Array.isArray(section.usage) ? section.usage : [],
        openHref: buildSourceOpenHref("section", section._id, section?.usage),
        openLabel: buildSourceOpenLabel("section"),
        todos: normalizeSourceTodos(section?.type_data?.admin_todos || []),
      });
    }
    for (const header of headers || []) {
      nextSources.push({
        key: `header:${header.id}`,
        type: "header",
        id: header.id,
        sectionType: "header",
        label: resolveHeaderLabel(header),
        usage: Array.isArray(header.usage) ? header.usage : [],
        openHref: buildSourceOpenHref("header", header.id, header?.usage),
        openLabel: buildSourceOpenLabel("header"),
        todos: normalizeSourceTodos(header?.admin_todos || []),
      });
    }
    nextSources.push({
      key: "__unassigned__",
      type: "unassigned",
      id: "__unassigned__",
      sectionType: "unassigned",
      label: "Unassigned",
      usage: [],
      openHref: "",
      openLabel: "",
      todos: normalizeSourceTodos(config?.unassigned_todos || []),
    });

    sources.value = nextSources;
    if (!todoTags.value.some((tag) => tag.id === newUnassignedTodoTag.value)) {
      newUnassignedTodoTag.value = defaultTodoTagId.value;
    }
    buildPlanningColumns();
  } catch (err) {
    console.error("Failed to load devops data:", err);
    error.value = err?.message || "Failed to load data.";
  } finally {
    loading.value = false;
  }
}

async function loadTutorials() {
  tutorialMessage.value = null;
  try {
    const tutorialPayload = await api.getAdminDevopsTutorials();
    applyTutorialPayload(tutorialPayload);
  } catch (err) {
    console.error("Failed to load tutorials:", err);
    tutorialMessage.value = { type: "error", text: err?.message || "Failed to load tutorials." };
  }
}

async function refreshChangelog() {
  await loadChangelogPage(changelogCurrentPage.value);
}

async function loadChangelogPage(page = 1) {
  const normalizedPage = Math.min(
    Math.max(1, Number(page) || 1),
    changelogTotalPages.value
  );
  loadingChangelog.value = true;
  error.value = "";
  try {
    const changelog = await api.getAdminDevopsChangelog({
      limit: CHANGELOG_PAGE_SIZE,
      offset: (normalizedPage - 1) * CHANGELOG_PAGE_SIZE,
      pageSlug: changelogPageSlug.value,
    });
    applyChangelogPayload(changelog);
  } catch (err) {
    console.error("Failed to load devops changelog:", err);
    error.value = err?.message || "Failed to load changelog.";
  } finally {
    loadingChangelog.value = false;
  }
}

async function saveSource(sourceKey) {
  const source = sourceByKey.value[sourceKey];
  if (!source) return;
  if (source.type === "unassigned") {
    await saveUnassignedTodos(source.todos);
    return;
  }
  const serializedTodos = serializeTodoList(source.todos);
  if (source.type === "section") {
    const updated = await api.updateSection(source.id, {
      type_data: { admin_todos: serializedTodos },
      revision_change_kind: "content",
    });
    source.todos = normalizeSourceTodos(updated?.type_data?.admin_todos || []);
    return;
  }
  const updated = await api.updateHeader(source.id, {
    admin_todos: serializedTodos,
    revision_change_kind: "content",
  });
  source.todos = normalizeSourceTodos(updated?.admin_todos || []);
}

async function saveUnassignedTodos(unassignedTodos) {
  const payload = serializeTodoList(unassignedTodos || []);
  const updated = await api.updateAdminDevopsConfig({ unassigned_todos: payload });
  const source = sourceByKey.value.__unassigned__;
  if (source) {
    source.todos = normalizeSourceTodos(updated?.unassigned_todos || []);
  }
}

async function onPlanningDragEnd(area, event) {
  if (event?.to?.dataset?.doneDropzone === "true") {
    return;
  }
  const changedSources = new Set();
  for (const priority of priorities) {
    planningColumns[area][priority].forEach((card, index) => {
      const source = sourceByKey.value[card.sourceKey];
      if (!source) return;
      const todo = source.todos.find((item) => item.id === card.todoId);
      if (!todo) return;
      if (todo.priority !== priority || todo.priorityRank !== index) {
        todo.priority = priority;
        todo.priorityRank = index;
        changedSources.add(source.key);
      }
    });
  }

  if (changedSources.size === 0) return;
  try {
    for (const sourceKey of changedSources) {
      await saveSource(sourceKey);
    }
    buildPlanningColumns();
  } catch (err) {
    console.error("Failed to persist planning changes:", err);
    error.value = err?.message || "Failed to save planning changes.";
    await loadData();
  }
}

function toggleAllTodoTagFilter(tagId) {
  const selected = new Set(allTodoSelectedTags.value);
  if (selected.has(tagId)) selected.delete(tagId);
  else selected.add(tagId);
  allTodoSelectedTags.value = Array.from(selected).sort((left, right) => left.localeCompare(right));
}

function clearAllTodoTagFilters() {
  allTodoSelectedTags.value = [];
}

function areStringArraysEqual(left, right) {
  if (!Array.isArray(left) || !Array.isArray(right)) return false;
  if (left.length !== right.length) return false;
  for (let i = 0; i < left.length; i += 1) {
    if (left[i] !== right[i]) return false;
  }
  return true;
}

async function onPlanningDoneDrop(area, event) {
  const card = event?.added?.element;
  if (!card) return;

  const bucket = doneDropBuckets[area];
  const idx = bucket.findIndex((item) => item.uid === card.uid);
  if (idx >= 0) bucket.splice(idx, 1);

  const source = sourceByKey.value[card.sourceKey];
  const todo = source?.todos?.find((item) => item.id === card.todoId);
  if (!source || !todo || todo.done) {
    buildPlanningColumns();
    return;
  }

  todo.done = true;
  try {
    await saveSource(source.key);
    buildPlanningColumns();
  } catch (err) {
    console.error("Failed to persist done-state change:", err);
    error.value = err?.message || "Failed to mark todo as done.";
    await loadData();
  }
}

async function addUnassignedTodo() {
  if (addingUnassignedTodo.value) return;
  const text = String(newUnassignedTodoText.value || "").trim();
  if (!text) return;
  const source = sourceByKey.value.__unassigned__;
  if (!source) return;
  const selectedTag = todoTags.value.some((tag) => tag.id === newUnassignedTodoTag.value)
    ? newUnassignedTodoTag.value
    : defaultTodoTagId.value;
  const selectedPriority = priorities.includes(newUnassignedTodoPriority.value)
    ? newUnassignedTodoPriority.value
    : "needed";
  const nextRank = source.todos.filter((todo) => !todo.done && todo.priority === selectedPriority).length;
  const nowIso = new Date().toISOString();
  const nextTodo = {
    id: `unassigned-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    text,
    done: false,
    createdBy: currentEditorName.value,
    createdAt: nowIso,
    resolvedBy: null,
    resolvedAt: null,
    tag: selectedTag,
    priority: selectedPriority,
    priorityRank: nextRank,
  };

  source.todos = normalizeSourceTodos([...source.todos, nextTodo]);
  addingUnassignedTodo.value = true;
  try {
    await saveUnassignedTodos(source.todos);
    newUnassignedTodoText.value = "";
    newUnassignedTodoTag.value = defaultTodoTagId.value;
    newUnassignedTodoPriority.value = "needed";
    buildPlanningColumns();
  } catch (err) {
    console.error("Failed to add unassigned todo:", err);
    error.value = err?.message || "Failed to add unassigned todo.";
    await loadData();
  } finally {
    addingUnassignedTodo.value = false;
  }
}

async function saveTags(nextTags) {
  savingTags.value = true;
  tagMessage.value = null;
  try {
    const payloadTags = nextTags.map((tag) => ({ id: tag.id, area: tag.area }));
    const result = await api.updateAdminDevopsConfig({ todo_tags: payloadTags });
    todoTags.value = normalizeTodoTags(result?.todo_tags || []);
    buildPlanningColumns();
    tagMessage.value = { type: "success", text: "Tags saved." };
  } catch (err) {
    console.error("Failed to save todo tags:", err);
    tagMessage.value = { type: "error", text: err?.message || "Failed to save tags." };
  } finally {
    savingTags.value = false;
  }
}

async function addTag() {
  const normalizedId = normalizeTodoTagId(newTagId.value);
  if (!normalizedId) {
    tagMessage.value = { type: "error", text: "Tag id is required." };
    return;
  }
  if (!/^[A-Za-z][A-Za-z0-9_-]{0,39}$/.test(normalizedId)) {
    tagMessage.value = { type: "error", text: "Tag id must start with a letter and use only letters, numbers, _ or -." };
    return;
  }
  if (todoTags.value.some((tag) => tag.id === normalizedId)) {
    tagMessage.value = { type: "error", text: `Tag '${normalizedId}' already exists.` };
    return;
  }
  const nextTags = [...todoTags.value, { id: normalizedId, area: newTagArea.value === "it" ? "it" : "content" }];
  await saveTags(nextTags);
  newTagId.value = "";
  newTagArea.value = "content";
}

async function updateTagArea(tagId, area) {
  const normalizedArea = area === "it" ? "it" : "content";
  const nextTags = todoTags.value.map((tag) =>
    tag.id === tagId ? { ...tag, area: normalizedArea } : tag
  );
  await saveTags(nextTags);
}

async function removeTag(tagId) {
  if (isDefaultTodoTag(tagId)) {
    tagMessage.value = { type: "error", text: "Default tags cannot be deleted." };
    return;
  }
  const inUse = allTodoEntries.value.some((entry) => entry.todo.tag === tagId);
  if (inUse) {
    tagMessage.value = { type: "error", text: `Tag '${tagId}' is in use and cannot be deleted.` };
    return;
  }
  const nextTags = todoTags.value.filter((tag) => tag.id !== tagId);
  await saveTags(nextTags);
}

function openCreateTutorial() {
  tutorialMessage.value = null;
  openTutorialBuilder();
}

function tutorialAllowedScopeValues() {
  const values = tutorialScopeOptions.value
    .map((option) => option.value)
    .filter(Boolean);
  if (values.length > 0) return values;
  const role = String(getInternalRole?.() || "").trim();
  const roleIndex = TUTORIAL_SCOPE_OPTIONS.findIndex((option) => option.value === role);
  if (roleIndex >= 0) {
    return TUTORIAL_SCOPE_OPTIONS.slice(0, roleIndex + 1).map((option) => option.value);
  }
  return ["content"];
}

function defaultTutorialScope() {
  const role = String(getInternalRole?.() || "").trim();
  const allowed = tutorialAllowedScopeValues();
  return allowed.includes(role) ? role : (allowed[0] || "content");
}

function openImportTutorialPicker() {
  tutorialMessage.value = null;
  tutorialImportInputRef.value?.click();
}

async function importTutorialMarkdown(event) {
  const file = event?.target?.files?.[0];
  if (event?.target) event.target.value = "";
  if (!file) return;

  tutorialMessage.value = null;
  try {
    const markdown = await file.text();
    const imported = parseTutorialMarkdown(markdown, {
      defaultScope: defaultTutorialScope(),
      allowedScopes: tutorialAllowedScopeValues(),
    });
    openTutorialBuilder(imported);
    tutorialMessage.value = { type: "success", text: "Tutorial imported as a draft. Review and save it to publish." };
  } catch (err) {
    console.error("Failed to import tutorial markdown:", err);
    tutorialMessage.value = { type: "error", text: err?.message || "Failed to import tutorial markdown." };
  }
}

function exportTutorial(tutorial) {
  downloadTutorialMarkdown(tutorial);
}

function openEditTutorial(tutorial) {
  if (!tutorial?.can_edit) return;
  tutorialMessage.value = null;
  openTutorialBuilder(tutorial);
}

function startTutorialFromList(tutorial) {
  tutorialMessage.value = null;
  startTutorial(tutorial);
}

function isActiveTutorial(tutorial) {
  return Boolean(tutorial?.id && tutorialOverlayState.activeTutorial?.id === tutorial.id);
}

async function deleteTutorial(tutorial) {
  if (!tutorial?.id || deletingTutorialId.value) return;
  const confirmed = window.confirm(`Delete tutorial "${tutorial.title}"?`);
  if (!confirmed) return;

  deletingTutorialId.value = tutorial.id;
  tutorialMessage.value = null;
  try {
    await api.deleteAdminDevopsTutorial(tutorial.id);
    if (isActiveTutorial(tutorial)) {
      stopTutorial();
    }
    await loadTutorials();
    tutorialMessage.value = { type: "success", text: "Tutorial deleted." };
  } catch (err) {
    console.error("Failed to delete tutorial:", err);
    tutorialMessage.value = { type: "error", text: err?.message || "Failed to delete tutorial." };
  } finally {
    deletingTutorialId.value = "";
  }
}

watch(
  tabs,
  (availableTabs) => {
    if (!availableTabs.some((item) => item.id === getRouteTab())) {
      router.replace(availableTabs[0]?.to || "/admin/devops/changelog");
    }
  },
  { immediate: true }
);

watch(changelogPageSlug, (next, previous) => {
  if (next === previous) return;
  if (loading.value) return;
  void loadChangelogPage(1);
});

watch(
  () => route.query.area,
  (area) => {
    planningArea.value = normalizePlanningArea(area);
  },
  { immediate: true }
);

watch(defaultTodoTagId, () => {
  sources.value = sources.value.map((source) => ({
    ...source,
    todos: normalizeSourceTodos(source.todos),
  }));
  buildPlanningColumns();
});

watch(
  allTodoEntries,
  (entries) => {
    if (!editingTodoUid.value) return;
    const exists = entries.some((entry) => entry.uid === editingTodoUid.value);
    if (!exists) cancelTodoEdit();
  }
);

watch(
  () => tutorialOverlayState.listVersion,
  () => {
    if (!loading.value) {
      void loadTutorials();
    }
  }
);

watch(
  [
    allTodoTypeFilter,
    allTodoPriorityFilter,
    allTodoDoneFilter,
    allTodoTagFilterOptions,
    allTodoCreatorFilterOptions,
  ],
  () => {
    const allowed = new Set(allTodoTagFilterOptions.value.map((item) => item.id));
    const nextSelectedTags = allTodoSelectedTags.value.filter((id) => allowed.has(id));
    if (!areStringArraysEqual(nextSelectedTags, allTodoSelectedTags.value)) {
      allTodoSelectedTags.value = nextSelectedTags;
    }
    if (allTodoCreatorFilter.value !== "all") {
      const creatorAllowed = allTodoCreatorFilterOptions.value.some(
        (item) => normalizeCreatorToken(item.value) === normalizeCreatorToken(allTodoCreatorFilter.value)
      );
      if (!creatorAllowed) allTodoCreatorFilter.value = "all";
    }
  },
  { immediate: true }
);

onMounted(async () => {
  await loadData();
});
</script>

<style scoped>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.loading-state,
.empty-state {
  padding: 16px;
  border: 1px dashed #cbd5e1;
  border-radius: 12px;
  color: #64748b;
  background: #fff;
}

.status-message {
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
  border: 1px solid transparent;
}

.status-message.success {
  background: #ecfdf5;
  color: #166534;
  border: 1px solid #86efac;
}

.status-message.error {
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.config-card {
  display: grid;
  gap: 14px;
}

.card-hint {
  margin: 6px 0 0;
}

.all-todo-filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.all-todo-filter-field {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.all-todo-filter-label {
  font-size: 11px;
  font-weight: 600;
  color: #475569;
  letter-spacing: 0.01em;
  text-transform: uppercase;
}

.all-todo-tag-filters {
  display: grid;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid #e2e8f0;
}

.all-todo-tag-filter-list {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.chip-filter {
  border: 1px solid #bfdbfe;
  cursor: pointer;
  gap: 4px;
  transition: all 0.15s ease;
}

.todo-tag-inline,
.todo-tag-chip,
.planning-card-tag,
.tag-name {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.todo-tag-icon {
  flex: 0 0 auto;
  width: 0.95em;
  color: currentColor;
}

.chip-filter:hover {
  background: #bfdbfe;
}

.chip-filter.active {
  border-color: #1d4ed8;
  background: #1d4ed8;
  color: #ffffff;
}

.chip-filter-count {
  font-size: 10px;
  background: rgba(15, 23, 42, 0.12);
  border-radius: 999px;
  padding: 1px 5px;
}

.chip-filter.active .chip-filter-count {
  background: rgba(255, 255, 255, 0.25);
}

.all-todo-add {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  padding: 10px;
  display: grid;
  gap: 8px;
}

.all-todo-add-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--admin-text, #0f172a);
}

.all-todo-add-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 170px 150px auto;
  gap: 8px;
  align-items: start;
}

.all-todo-add-field {
  display: grid;
  gap: 5px;
}

.all-todo-add-label {
  color: #475569;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
  text-transform: uppercase;
}

.all-todo-add-row > .btn-primary {
  align-self: end;
}

.all-todo-add-textarea {
  min-height: 84px;
  resize: vertical;
}

.tag-create {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px auto;
  gap: 8px;
}

.tag-list {
  display: grid;
}

.tag-row {
  padding: 10px 8px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.todo-tag-edit-list .tag-row:not(:last-child) {
  border-bottom: 1px solid #dddd;
}

.tag-label {
  min-width: 0;
  flex: 1 1 auto;
  display: grid;
  gap: 3px;
}

.tag-name {
  color: #0f172a;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.tag-meta {
  color: #64748b;
  font-size: 12px;
  line-height: 1.35;
}

.tag-area-select {
  flex: 0 0 150px;
  min-width: 130px;
}

.changelog-panel {
  gap: 12px;
}

.changelog-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.changelog-header-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.changelog-page-filter {
  min-width: 220px;
  display: grid;
  gap: 4px;
}

.changelog-page-filter-label {
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
  line-height: 1.2;
  text-transform: uppercase;
}

.changelog-pagination-summary,
.changelog-page-count {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
  white-space: nowrap;
}

.changelog-pagination-controls,
.changelog-pagination-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.changelog-pagination-footer {
  justify-content: flex-end;
  padding-top: 2px;
}

.changelog-list {
  display: grid;
  gap: 16px;
}

.changelog-day-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  padding: 4px 0 8px;
  border-bottom: 1px solid #cbd5e1;
}

.changelog-day-header h3 {
  margin: 0;
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.35;
}

.changelog-day-header span {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.changelog-day-entries {
  display: grid;
}

.changelog-row {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr) minmax(160px, auto);
  gap: 12px;
  align-items: start;
  padding: 14px 0;
}

.changelog-row + .changelog-row {
  border-top: 1px solid #e2e8f0;
}

.changelog-stamp {
  display: grid;
  gap: 3px;
}

.changelog-time {
  color: #475569;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.5;
}

.changelog-user {
  color: #64748b;
  font-size: 12px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.changelog-main {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.changelog-title {
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.changelog-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.4;
}

.changelog-page-link {
  color: #2563eb;
  font-weight: 700;
  overflow-wrap: anywhere;
  text-decoration: none;
}

.changelog-page-link:hover {
  text-decoration: underline;
}

.changelog-tags {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.changelog-open-link {
  white-space: nowrap;
}

.tutorials-panel {
  gap: 12px;
}

.tutorials-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.tutorials-header-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.tutorial-import-input {
  display: none;
}

.tutorial-list {
  display: grid;
  gap: 10px;
}

.tutorial-filters {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) repeat(2, minmax(150px, 220px));
  gap: 10px;
  align-items: end;
}

.tutorial-filter-field {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.tutorial-filter-label {
  color: #475569;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.01em;
  text-transform: uppercase;
}

.tutorial-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-left: 4px solid #2563eb;
  border-radius: 10px;
  background: #ffffff;
}

.tutorial-row.is-active {
  border-left-color: #16a34a;
  background: #f0fdf4;
}

.tutorial-main {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.tutorial-title {
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.tutorial-description {
  margin: 0;
  color: #475569;
  font-size: 13px;
  line-height: 1.45;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.tutorial-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.tutorial-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.planning-toolbar {
  display: flex;
  justify-content: flex-end;
  align-items: end;
  gap: 10px;
  margin-bottom: 12px;
}

.planning-area-field {
  display: grid;
  gap: 6px;
  min-width: 180px;
}

.all-todo-text.done {
  text-decoration: line-through;
  color: #94a3b8;
}

.chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #eff6ff;
  color: #1e40af;
  font-size: 11px;
  padding: 2px 8px;
  line-height: 1.4;
  border: 1px solid #dbeafe;
}

.chip-muted {
  background: #f1f5f9;
  color: #475569;
  border-color: #e2e8f0;
}

.todo-groups {
  display: grid;
  gap: 10px;
}

.todo-group-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
  padding: 10px 12px;
  display: grid;
  gap: 8px;
}

.todo-group-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.todo-group-head h3 {
  margin: 0;
  font-size: 14px;
  color: var(--admin-text, #0f172a);
}

.planning-board {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.planning-column {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  min-height: 340px;
  display: grid;
  gap: 8px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.planning-column-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.planning-column-head h3 {
  margin: 0;
  font-size: 14px;
  color: var(--admin-text, #0f172a);
}

.planning-priority-heading {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.count-badge {
  font-size: 12px;
  color: #475569;
  background: #f1f5f9;
  border-radius: 999px;
  padding: 2px 8px;
}

.planning-dropzone {
  min-height: 260px;
  display: grid;
  align-content: start;
  gap: 8px;
  padding-top: 2px;
}

.planning-card {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 9px 10px;
  background: #ffffff;
  cursor: grab;
  box-shadow: 0 1px 1px rgba(15, 23, 42, 0.03);
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}

.planning-card:hover {
  border-color: #94a3b8;
  box-shadow: 0 3px 8px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.planning-card-text {
  font-size: 13px;
  color: #0f172a;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.planning-card-meta {
  margin-top: 4px;
  font-size: 11px;
  color: #64748b;
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  align-items: center;
}

.planning-card-meta > span + span::before {
  content: "·";
  margin-right: 5px;
  color: #94a3b8;
}

.planning-done-zone {
  margin-top: 12px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  display: grid;
  gap: 8px;
}

.planning-done-head h3 {
  margin: 0;
  font-size: 15px;
  color: #0f172a;
}

.planning-done-dropzone {
  min-height: 110px;
  border: 2px dashed #94a3b8;
  border-radius: 10px;
  background: #f8fafc;
  padding: 10px;
  display: grid;
  align-content: start;
  gap: 8px;
}

.planning-done-dropzone:empty::before {
  content: "Drop todo here to mark done";
  color: #64748b;
  font-size: 12px;
}

.all-todos-list {
  display: grid;
  gap: 10px;
}

.all-todo-row {
  --ticket-tone: #475569;
  --ticket-soft: #f8fafc;
  --ticket-glow: rgba(71, 85, 105, 0.1);
  border: 1px solid #e2e8f0;
  border-left: 4px solid var(--ticket-tone);
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, var(--ticket-soft) 100%);
  padding: 13px 15px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(240px, auto);
  grid-template-areas:
    "main meta"
    "main actions";
  gap: 10px 14px;
  align-items: flex-start;
  position: relative;
  overflow: hidden;
  isolation: isolate;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease, background 0.2s ease;
}

.all-todo-row::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(128deg, var(--ticket-glow) 0%, transparent 46%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.2) 0%, transparent 42%);
  pointer-events: none;
  z-index: 0;
}

.all-todo-open-link {
  white-space: nowrap;
  position: absolute;
  bottom: 10px;
  right: 12px;
  z-index: 2;
}

.all-todo-row.has-open-link {
  padding-bottom: 44px;
}

.all-todo-row:hover {
  border-color: #94a3b8;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.12);
  transform: translateY(-1px);
}

.all-todo-row.ticket-priority-urgent {
  --ticket-tone: #dc2626;
  --ticket-soft: #fff1f2;
  --ticket-glow: rgba(248, 113, 113, 0.2);
}

.all-todo-row.ticket-priority-needed {
  --ticket-tone: #b45309;
  --ticket-soft: #fff7ed;
  --ticket-glow: rgba(251, 191, 36, 0.2);
}

.all-todo-row.ticket-priority-optional {
  --ticket-tone: #0369a1;
  --ticket-soft: #f0f9ff;
  --ticket-glow: rgba(56, 189, 248, 0.2);
}

.all-todo-row.ticket-state-done {
  --ticket-tone: #64748b;
  --ticket-soft: #f8fafc;
  --ticket-glow: rgba(148, 163, 184, 0.14);
  opacity: 0.92;
}

.all-todo-main {
  grid-area: main;
  min-width: 0;
  display: grid;
  gap: 4px;
  position: relative;
  z-index: 1;
}

.all-todo-text {
  color: #0f172a;
  font-size: 14px;
  line-height: 1.5;
  font-weight: 600;
  letter-spacing: 0.005em;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.all-todo-source {
  margin-top: 1px;
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.all-todo-comments {
  margin-top: 10px;
  display: grid;
  gap: 6px;
}

.all-todo-comment {
  display: grid;
  gap: 3px;
  padding: 7px 9px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  border-left: 3px solid var(--ticket-tone);
  background: rgba(248, 250, 252, 0.95);
}

.all-todo-comment-author {
  font-size: 11px;
  color: #475569;
  font-weight: 600;
}

.all-todo-comment-text {
  font-size: 12px;
  color: #0f172a;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.all-todo-meta {
  grid-area: meta;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: flex-start;
  position: relative;
  z-index: 1;
}

.chip-priority {
  min-width: 28px;
  justify-content: center;
  padding: 4px 0;
}

.chip-priority svg {
  width: 0.9em;
  height: 0.9em;
}

.chip-priority.priority-urgent {
  background: #fef2f2;
  border-color: #fecaca;
  color: #991b1b;
}

.chip-priority.priority-needed {
  background: #fffbeb;
  border-color: #fde68a;
  color: #92400e;
}

.chip-priority.priority-optional {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1e40af;
}

.chip-status.status-open {
  background: #ecfdf5;
  border-color: #86efac;
  color: #166534;
}

.chip-status.status-done {
  background: #f1f5f9;
  border-color: #cbd5e1;
  color: #475569;
}

.chip-creator {
  background: #ffffff;
  border-style: dashed;
  border-color: #cbd5e1;
  color: #334155;
  font-weight: 600;
}

.all-todo-actions {
  grid-area: actions;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  min-width: 0;
  position: static;
}

.all-todo-actions .btn-outline,
.all-todo-actions .btn-primary {
  box-shadow: 0 1px 0 rgba(15, 23, 42, 0.06);
}

.all-todo-actions .btn-outline:hover,
.all-todo-actions .btn-primary:hover {
  transform: translateY(-1px);
}

.all-todo-inline-form {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto auto;
  gap: 6px;
  align-items: start;
  justify-content: end;
  width: min(100%, 720px);
}

.all-todo-inline-input {
  min-width: 220px;
}

.all-todo-inline-textarea {
  min-height: 78px;
  resize: vertical;
}

.all-todo-row:focus-within {
  border-color: color-mix(in srgb, var(--ticket-tone) 42%, #1d4ed8 58%);
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--ticket-tone) 16%, #dbeafe 84%),
    0 8px 20px rgba(15, 23, 42, 0.1);
}

@media (max-width: 980px) {
  .planning-board {
    grid-template-columns: minmax(0, 1fr);
  }
  .changelog-row {
    grid-template-columns: 150px minmax(0, 1fr);
  }
  .changelog-tags {
    grid-column: 2;
    justify-content: flex-start;
  }
  .all-todo-row {
    grid-template-columns: minmax(0, 1fr) minmax(200px, auto);
  }
}

@media (max-width: 760px) {
  .all-todo-add-row,
  .tag-create {
    grid-template-columns: minmax(0, 1fr);
  }
  .tag-row {
    justify-content: flex-start;
  }
  .tag-area-select {
    flex: 1 1 160px;
  }
  .changelog-day-header,
  .changelog-header,
  .changelog-row,
  .changelog-tags,
  .tutorials-header,
  .tutorial-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    justify-content: stretch;
  }
  .changelog-header-actions,
  .changelog-pagination-controls,
  .changelog-pagination-footer,
  .planning-toolbar,
  .tutorial-actions {
    justify-content: flex-start;
  }
  .planning-area-field {
    width: 100%;
  }
  .changelog-page-filter {
    width: 100%;
  }
  .tutorial-filters {
    grid-template-columns: minmax(0, 1fr);
  }
  .changelog-tags {
    grid-column: auto;
  }
  .all-todo-meta {
    justify-content: flex-start;
  }
  .all-todo-actions {
    justify-content: flex-start;
  }
  .all-todo-inline-form {
    justify-content: flex-start;
    grid-template-columns: minmax(0, 1fr);
    width: 100%;
  }
  .all-todo-inline-input {
    min-width: 0;
    width: 100%;
  }
  .all-todo-row {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      "main"
      "meta"
      "actions";
    gap: 8px;
  }
}
</style>
