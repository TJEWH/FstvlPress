<template>
  <!-- Loading indicator -->
  <div v-if="loading" class="loading-overlay">
    <div class="loading-spinner"></div>
    <p>{{ t.loading }}</p>
  </div>

  <!-- Under-construction state for public visitors -->
  <div v-else-if="showUnderConstruction" class="under-construction-overlay">
    <div class="under-construction-card">
      <h1 class="under-construction-title">{{ underConstructionTitle }}</h1>
      <p class="under-construction-message">
        {{ underConstructionMessage }}
      </p>
      <div class="under-construction-actions">
        <router-link to="/" class="btn">
          {{ state.lang === 'de' ? 'Zur Startseite' : 'Go to Homepage' }}
        </router-link>
      </div>
    </div>
  </div>

  <!-- 404/410 state (not found, removed, or not public for non-admin users) -->
  <NotFound v-else-if="showNotFound" :status-code="notFoundStatusCode" />

  <!-- Error state (only show for non-404 errors when not admin) -->
  <div v-else-if="error && !state.isAdmin && !isPageNotFound" class="error-overlay">
    <div class="error-card">
      <div class="error-icon"><font-awesome-icon :icon="faTriangleExclamation" /></div>
      <h2>{{ t.error }}</h2>
      <p>{{ error }}</p>
      <button class="btn" @click="loadPage">{{ t.retry || 'Retry' }}</button>
    </div>
  </div>

  <!-- Page content (also shown for admins when page doesn't exist) -->
  <template v-else>
    <div class="page-wrapper" :class="{ 'blog-page': isBlogGeneratedPage }">
    <div
      v-if="state.isAdmin && !state.previewMode && hasHeaderContent"
      v-show="headerEnabled"
      class="container hero-editor-tabs-wrap"
    >
      <HeaderAdminTabs
        v-model:active-tab="headerAdminActiveTab"
        :show-design="state.canDesign || isTemplateBuilder"
        :show-template="!isTemplateBuilder"
        class="hero-editor-tabs"
        :notes-label="headerOpenTodoCount > 0 ? `Notes (${headerOpenTodoCount})` : 'Notes'"
        :autosave-message="headerAutosaveMessage"
        :autosave-tone="headerAutosaveTone"
      >
        <template #design>
          <div class="header-admin-panel">
            <details v-if="!isPageTemplateStyleLocked" class="header-design-slider-panel" open>
              <summary class="header-design-slider-summary">Section Specific</summary>
              <div class="header-design-slider-content">
                <label class="header-design-slider-field">
                  <span class="header-design-slider-field__label">Blur Mode</span>
                  <div class="header-blur-mode-toggle" role="group" aria-label="Header blur mode">
                    <button
                      type="button"
                      class="header-blur-mode-toggle__btn"
                      :class="{ active: headerBlurMode === 'static' }"
                      @click="setHeaderBlurMode('static')"
                    >
                      Static
                    </button>
                    <button
                      type="button"
                      class="header-blur-mode-toggle__btn"
                      :class="{ active: headerBlurMode === 'scroll' }"
                      @click="setHeaderBlurMode('scroll')"
                    >
                      On Scroll
                    </button>
                  </div>
                </label>
                <Transition name="header-blur-slider-transition">
                  <div
                    v-if="showHeaderBlurStartControl"
                    class="header-design-slider-row"
                  >
                    <label class="header-design-slider-field">
                      <span class="header-design-slider-field__label">Blur Start</span>
                      <div class="header-design-slider-field__control">
                        <input
                          type="range"
                          :min="HEADER_BLUR_MIN"
                          :max="HEADER_BLUR_MAX"
                          step="0.5"
                          :value="headerBlurStartEditorValue"
                          @input="setHeaderBlurStartValue($event.target.value)"
                          @change="persistHeaderDesignOverrides"
                        />
                        <span class="header-design-slider-field__value">{{ formatHeaderBlurValue(headerBlurStartEditorValue) }}</span>
                      </div>
                    </label>
                    <label class="header-design-slider-field">
                      <span class="header-design-slider-field__label">Start Position</span>
                      <div class="header-design-slider-field__control">
                        <input
                          type="range"
                          :min="HEADER_BLUR_POSITION_MIN"
                          :max="HEADER_BLUR_POSITION_MAX"
                          step="1"
                          :value="headerBlurStartVhEditorValue"
                          @input="setHeaderBlurStartVhValue($event.target.value)"
                          @change="persistHeaderDesignOverrides"
                        />
                        <span class="header-design-slider-field__value">{{ formatHeaderBlurPositionValue(headerBlurStartVhEditorValue) }}</span>
                      </div>
                    </label>
                  </div>
                </Transition>
                <div v-if="showHeaderBlurStartControl" class="header-design-slider-row">
                  <label class="header-design-slider-field">
                    <span class="header-design-slider-field__label">Blur End</span>
                    <div class="header-design-slider-field__control">
                      <input
                        type="range"
                        :min="HEADER_BLUR_MIN"
                        :max="HEADER_BLUR_MAX"
                        step="0.5"
                        :value="headerBlurEndEditorValue"
                        @input="setHeaderBlurEndValue($event.target.value)"
                        @change="persistHeaderDesignOverrides"
                      />
                      <span class="header-design-slider-field__value">{{ formatHeaderBlurValue(headerBlurEndEditorValue) }}</span>
                    </div>
                  </label>
                  <label class="header-design-slider-field">
                    <span class="header-design-slider-field__label">End Position</span>
                    <div class="header-design-slider-field__control">
                      <input
                        type="range"
                        :min="HEADER_BLUR_POSITION_MIN"
                        :max="HEADER_BLUR_POSITION_MAX"
                        step="1"
                        :value="headerBlurEndVhEditorValue"
                        @input="setHeaderBlurEndVhValue($event.target.value)"
                        @change="persistHeaderDesignOverrides"
                      />
                      <span class="header-design-slider-field__value">{{ formatHeaderBlurPositionValue(headerBlurEndVhEditorValue) }}</span>
                    </div>
                  </label>
                </div>
                <label v-else class="header-design-slider-field">
                  <span class="header-design-slider-field__label">Blur</span>
                  <div class="header-design-slider-field__control">
                    <input
                      type="range"
                      :min="HEADER_BLUR_MIN"
                      :max="HEADER_BLUR_MAX"
                      step="0.5"
                      :value="headerBlurEndEditorValue"
                      @input="setHeaderBlurEndValue($event.target.value)"
                      @change="persistHeaderDesignOverrides"
                    />
                    <span class="header-design-slider-field__value">{{ formatHeaderBlurValue(headerBlurEndEditorValue) }}</span>
                  </div>
                </label>
              </div>
            </details>
            <div class="header-admin-panel__actions">
              <button
                v-if="!isPageTemplateStyleLocked"
                class="btn hero-design-btn"
                type="button"
                @click="openSectionDesignPanel('__header__')"
              >
                Open Design Overrides
              </button>
            </div>
            <p v-if="isPageTemplateStyleLocked" class="header-admin-panel__hint">
              Style is controlled by the linked page template. Header design overrides are disabled for this page.
            </p>
          </div>
        </template>

        <template #content>
          <div class="header-admin-panel">
            <div class="header-admin-panel__title">Header Fields (Drag to Order Layers)</div>
            <draggable
              v-model="headerFieldEditorItems"
              item-key="key"
              class="header-field-list"
              handle=".header-field-row__drag"
              ghost-class="header-field-row--ghost"
              chosen-class="header-field-row--chosen"
              drag-class="header-field-row--drag"
              @end="onHeaderFieldOrderChanged"
            >
              <template #item="{ element }">
                <label class="header-field-row" :class="{ muted: !headerFieldEnabled(element.key) }">
                  <span class="header-field-row__drag" title="Drag to reorder">⋮⋮</span>
                  <span class="header-field-row__label">{{ element.label }}</span>
                  <input
                    type="checkbox"
                    :checked="headerFieldEnabled(element.key)"
                    @change="setHeaderFieldEnabled(element.key, $event.target.checked)"
                  />
                </label>
              </template>
            </draggable>
            <p class="header-admin-panel__hint">
              Unchecked fields are hidden but keep their values. Reordering updates the stacking in the live preview.
            </p>

            <template v-if="headerFieldEnabled('background_image') || headerFieldEnabled('overlay_image')">
              <div class="header-admin-panel__title">Header Media</div>
              <div class="header-media-controls">
                <div v-if="headerFieldEnabled('background_image')" class="header-media-card">
                  <div class="header-media-card__head">
                    <span class="header-media-card__title">Background Image</span>
                  </div>
                  <div class="header-media-card__focus">
                    <ImageTransformEditor
                      :image-url="headerBackgroundPreviewUrl"
                      :zoom="headerBackgroundZoom"
                      :focal-x="headerBackgroundFocalX"
                      :focal-y="headerBackgroundFocalY"
                      :rotation="headerBackgroundRotation"
                      ratio="16:9"
                      view-context="header"
                      @update:image-url="(value) => setHeaderMediaUrl('background_image', value)"
                      @update:zoom="setHeaderBackgroundZoom"
                      @update:focal-x="setHeaderBackgroundFocalX"
                      @update:focal-y="setHeaderBackgroundFocalY"
                      @update:rotation="setHeaderBackgroundRotation"
                      @choose-image="openHeaderMediaPicker('background_image')"
                      @clear-image="clearHeaderMedia('background_image')"
                      @commit="commitHeaderMediaAdjustPatch"
                    />
                  </div>
                </div>

                <div v-if="headerFieldEnabled('overlay_image')" class="header-media-card header-media-card--overlay">
                  <div class="header-media-card__head">
                    <span class="header-media-card__title">Overlay Image</span>
                  </div>
                  <div class="header-media-card__focus">
                    <ImageTransformEditor
                      :image-url="headerOverlayPreviewUrl"
                      :zoom="headerOverlayZoom"
                      :focal-x="headerOverlayFocalX"
                      :focal-y="headerOverlayFocalY"
                      :rotation="headerOverlayRotation"
                      ratio="1:1"
                      view-context="header"
                      @update:image-url="(value) => setHeaderMediaUrl('overlay_image', value)"
                      @update:zoom="setHeaderOverlayZoom"
                      @update:focal-x="setHeaderOverlayFocalX"
                      @update:focal-y="setHeaderOverlayFocalY"
                      @update:rotation="setHeaderOverlayRotation"
                      @choose-image="openHeaderMediaPicker('overlay_image')"
                      @clear-image="clearHeaderMedia('overlay_image')"
                      @commit="commitHeaderMediaAdjustPatch"
                    />
                  </div>
                </div>
              </div>
            </template>

            <template v-if="headerFieldEnabled('cta_buttons')">
              <div class="header-admin-panel__title">CTA Buttons</div>
              <SectionListEditor
                :items="headerCtaDraft"
                :selected-index="headerCtaExpandedItem"
                :add-label="t.add"
                :save-label="t.save"
                :remove-label="t.remove"
                :add-disabled="headerCtaDraft.length >= HEADER_MAX_CTA_BUTTONS"
                :min-item-width="160"
                @select="headerCtaExpandedItem = $event"
                @add="addHeaderCtaItem"
                @save="saveHeaderCtaItems"
                @remove="removeHeaderCtaItem"
              >
                <template #item="{ item, index }">
                  <div class="item-thumb header-cta-thumb">
                    <span class="header-cta-thumb__title">
                      {{ item.text.de || item.text.en || `Button ${index + 1}` }}
                    </span>
                    <span class="header-cta-thumb__meta">{{ headerCtaStyleLabel(item.buttonType, index) }}</span>
                  </div>
                </template>

                <template #editor="{ item }">
                  <div class="header-cta-editor">
                    <div class="header-cta-editor__lang-grid">
                      <div class="header-cta-editor__lang">
                        <label class="header-cta-editor__label">{{ t.german }} (DE)</label>
                        <input
                          v-model="item.text.de"
                          class="header-cta-editor__field"
                          type="text"
                          placeholder="Button label..."
                        />
                      </div>
                      <div class="header-cta-editor__lang">
                        <label class="header-cta-editor__label">{{ t.english }} (EN)</label>
                        <input
                          v-model="item.text.en"
                          class="header-cta-editor__field"
                          type="text"
                          placeholder="Button label..."
                        />
                      </div>
                    </div>

                    <div class="header-cta-editor__meta-grid">
                      <div class="header-cta-editor__lang">
                        <label class="header-cta-editor__label">Link URL</label>
                        <input
                          v-model="item.url"
                          class="header-cta-editor__field"
                          type="url"
                          placeholder="https://..."
                        />
                      </div>
                      <div class="header-cta-editor__lang">
                        <label class="header-cta-editor__label">Button Style</label>
                        <select v-model="item.buttonType" class="header-cta-editor__field">
                          <option
                            v-for="opt in headerCtaButtonStyleOptions"
                            :key="opt.id"
                            :value="opt.id"
                          >
                            {{ opt.label }}
                          </option>
                        </select>
                      </div>
                    </div>
                    <p class="header-admin-panel__hint">
                      CTA buttons are saved to header content and shown in the live preview.
                    </p>
                  </div>
                </template>
              </SectionListEditor>
            </template>

            <p
              v-if="!headerFieldEnabled('background_image') && !headerFieldEnabled('overlay_image') && !headerFieldEnabled('cta_buttons')"
              class="header-admin-panel__hint"
            >
              Enable Background, Overlay, or Buttons in Header Fields to edit content here.
            </p>
          </div>
        </template>

        <template #history>
          <div class="section-admin-tabs__history">
            <div class="section-admin-tabs__history-head">
              <button type="button" class="btn section-admin-tabs__history-config-btn" @click="openHeaderRevisionSettings">
                Configure Revisions
              </button>
            </div>
            <div v-if="headerHistoryLoading" class="section-admin-tabs__history-empty">Loading history…</div>
            <div v-else-if="headerHistoryError" class="section-admin-tabs__history-empty">{{ headerHistoryError }}</div>
            <div
              v-else-if="!headerHistoryOptions.includeDesign && !headerHistoryOptions.includeContent"
              class="section-admin-tabs__history-empty"
            >
              Revisions are disabled for headers. Configure them in Admin Database.
            </div>
            <div v-else class="section-admin-tabs__history-grid" :class="{ 'single-column': !headerHistoryOptions.includeDesign || !headerHistoryOptions.includeContent }">
              <div v-if="headerHistoryOptions.includeDesign" class="section-admin-tabs__history-col">
                <div class="section-admin-tabs__history-title">Design</div>
                <button
                  v-for="entry in headerDesignHistoryEntries"
                  :key="`header-design-${entry.key}`"
                  type="button"
                  class="section-admin-tabs__history-item"
                  :class="{ active: selectedHeaderDesignRevisionKey === entry.key, current: entry.source === 'current' }"
                  @click="selectHeaderHistoryEntry('design', entry)"
                >
                  <div class="section-admin-tabs__history-item-head">
                    <AuthorBadge :name="entry.savedBy" :timestamp="entry.savedAt" />
                    <span class="section-admin-tabs__history-author">{{ entry.savedBy }}</span>
                  </div>
                  <div class="section-admin-tabs__history-date">{{ formatHeaderHistoryDate(entry.savedAt) }}</div>
                  <div v-if="entry.designParamDiffs?.length" class="section-admin-tabs__history-diff">
                    {{ summarizeParamDiffs(entry.designParamDiffs) }}
                  </div>
                </button>
                <p v-if="headerDesignHistoryEntries.length === 0" class="section-admin-tabs__history-empty">No design revisions.</p>
                <div class="section-admin-tabs__history-actions">
                  <button
                    type="button"
                    class="btn"
                    :disabled="!canRevertHeaderDesign || headerHistoryRevertingDesign"
                    @click="revertSelectedHeaderRevision('design')"
                  >
                    {{ headerHistoryRevertingDesign ? "Reverting…" : "Revert Design" }}
                  </button>
                </div>
              </div>

              <div v-if="headerHistoryOptions.includeContent" class="section-admin-tabs__history-col">
                <div class="section-admin-tabs__history-title">Content</div>
                <button
                  v-for="entry in headerContentHistoryEntries"
                  :key="`header-content-${entry.key}`"
                  type="button"
                  class="section-admin-tabs__history-item"
                  :class="{ active: selectedHeaderContentRevisionKey === entry.key, current: entry.source === 'current' }"
                  @click="selectHeaderHistoryEntry('content', entry)"
                >
                  <div class="section-admin-tabs__history-item-head">
                    <AuthorBadge :name="entry.savedBy" :timestamp="entry.savedAt" />
                    <span class="section-admin-tabs__history-author">{{ entry.savedBy }}</span>
                  </div>
                  <div class="section-admin-tabs__history-date">{{ formatHeaderHistoryDate(entry.savedAt) }}</div>
                  <div v-if="entry.contentParamDiffs?.length" class="section-admin-tabs__history-diff">
                    {{ summarizeParamDiffs(entry.contentParamDiffs) }}
                  </div>
                </button>
                <p v-if="headerContentHistoryEntries.length === 0" class="section-admin-tabs__history-empty">No content revisions.</p>
                <div class="section-admin-tabs__history-actions">
                  <button
                    type="button"
                    class="btn"
                    :disabled="!canRevertHeaderContent || headerHistoryRevertingContent"
                    @click="revertSelectedHeaderRevision('content')"
                  >
                    {{ headerHistoryRevertingContent ? "Reverting…" : "Revert Content" }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </template>

        <template #template>
          <div class="header-admin-panel header-admin-panel--template">
            <label class="header-template-share-check">
              <input
                type="checkbox"
                :checked="header.shared === true"
                :disabled="!header.headerId || headerSharingSaving"
                @change="setHeaderShared($event.target.checked)"
              />
              <span>Share current header</span>
            </label>
            <p class="header-admin-panel__hint">
              Shared headers appear in Manage Headers &gt; Shared Headers. Pages using the same header stay linked, so future edits affect every page using it.
            </p>
            <p v-if="headerSharingError" class="header-admin-panel__error">{{ headerSharingError }}</p>
          </div>
        </template>

        <template #notes>
          <div class="section-admin-tabs__notes">
            <label class="notes-label" for="header-admin-notes">Notes</label>
            <textarea
              id="header-admin-notes"
              v-model="headerNotesDraft"
              class="notes-textarea"
              rows="4"
              placeholder="Add notes for this header..."
              @input="persistHeaderNotes"
            />

            <div class="todo-board">
              <div class="todo-head">Todos</div>
              <div class="todo-add">
                <input
                  v-model="headerNewTodo"
                  class="todo-input"
                  type="text"
                  placeholder="Add todo..."
                  @keydown.enter.prevent="addHeaderTodo"
                />
                <TodoIconSelect
                  v-model="headerNewTodoTag"
                  :options="headerTodoTagSelectOptions"
                  aria-label="Todo type"
                />
                <TodoIconSelect
                  v-model="headerNewTodoPriority"
                  :options="headerTodoPrioritySelectOptions"
                  aria-label="Todo urgency"
                />
                <button class="btn" type="button" @click="addHeaderTodo">Add</button>
              </div>

              <div class="todo-list">
                <div class="todo-group">
                  <div class="todo-group-title">Open ({{ headerOpenTodos.length }})</div>
                  <label v-for="todo in headerOpenTodos" :key="todo.id" class="todo-item">
                    <input
                      type="checkbox"
                      :checked="todo.done"
                      @change="toggleHeaderTodo(todo.id, $event.target.checked)"
                    />
                    <div class="todo-main">
                      <span class="todo-text">{{ todo.text }}</span>
                      <div class="todo-meta-row">
                        <span
                          class="todo-chip todo-chip--tag"
                          :class="`area-${headerTodoTagArea(todo.tag)}`"
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
                    <AuthorBadge class="todo-author" :name="headerTodoAuthorName(todo)" :timestamp="headerTodoAuthorTime(todo)" />
                    <button class="todo-remove" type="button" @click.prevent="removeHeaderTodo(todo.id)">&times;</button>
                  </label>
                  <p v-if="headerOpenTodos.length === 0" class="todo-empty">No open todos.</p>
                </div>

                <div class="todo-group">
                  <div class="todo-group-title">Done ({{ headerDoneTodos.length }})</div>
                  <label v-for="todo in headerDoneTodos" :key="todo.id" class="todo-item">
                    <input
                      type="checkbox"
                      :checked="todo.done"
                      @change="toggleHeaderTodo(todo.id, $event.target.checked)"
                    />
                    <div class="todo-main">
                      <span class="todo-text done">{{ todo.text }}</span>
                      <div class="todo-meta-row">
                        <span
                          class="todo-chip todo-chip--tag"
                          :class="`area-${headerTodoTagArea(todo.tag)}`"
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
                    <AuthorBadge class="todo-author" :name="headerTodoAuthorName(todo)" :timestamp="headerTodoAuthorTime(todo)" />
                    <button class="todo-remove" type="button" @click.prevent="removeHeaderTodo(todo.id)">&times;</button>
                  </label>
                  <p v-if="headerDoneTodos.length === 0" class="todo-empty">No done todos.</p>
                </div>
              </div>
            </div>
          </div>
        </template>

      </HeaderAdminTabs>
      <MediaLibrary
        :is-open="headerMediaPickerOpen"
        :current-url="headerMediaPickerCurrentUrl"
        :source-context="headerMediaPickerSourceContext"
        :allow-clear-selection="true"
        @close="closeHeaderMediaPicker"
        @select="onHeaderMediaSelect"
      />
    </div>

    <!-- Hero Header (if page has one with content) -->
    <section
      v-if="hasHeaderContent"
      ref="heroSectionRef"
      v-show="headerEnabled"
      class="hero"
      :class="heroClasses"
      :style="heroOverrideStyle"
    >
      <EditableBgImage
          v-if="hasVisibleHeroBackground"
          :model-value="header.backgroundImage"
          :is-admin="false"
          @update:model-value="(v) => updateHeader({ backgroundImage: v })"
      >
        <div class="hero-bg" :class="{ 'hero-bg--video': isBackgroundVideo }" :style="heroBgStyle">
          <TransformedImage
            v-if="!isBackgroundVideo && heroBackgroundUrl"
            class="hero-bg-image"
            :src="heroBackgroundUrl"
            alt=""
            :zoom="headerBackgroundZoom"
            :focal-x="headerBackgroundFocalX"
            :focal-y="headerBackgroundFocalY"
            :rotation="headerBackgroundRotation"
            fit="cover"
            loading="eager"
            decoding="sync"
            :style="heroImageParallaxStyle"
          />
          <!-- Video background -->
          <video
            v-if="isBackgroundVideo"
            ref="heroVideoRef"
            class="hero-video"
            :class="{ 'hero-video--parallax': heroParallaxEnabled }"
            :style="videoParallaxStyle"
            :src="heroBackgroundUrl"
            autoplay
            muted
            loop
            playsinline
            @loadedmetadata="ensureVideoMuted"
          ></video>
          <div class="hero-overlay">
            <div v-if="showHeroInner" class="container hero-inner">
              <div class="hero-layout">
                <div class="hero-copy">
                  <EditableText
                      v-if="headerFieldEnabled('title')"
                      :model-value="state.pageTitle"
                      :is-admin="state.isAdmin"
                      as="h1"
                      :display-class="'hero-title'"
                      placeholder="Enter title..."
                      @update:modelValue="(v) => updatePageTitle(v)"
                  />
                  <EditableText
                      v-if="headerFieldEnabled('subtitle')"
                      :model-value="header.subtitle"
                      :is-admin="state.isAdmin"
                      multiline
                      as="p"
                      :display-class="'hero-subtitle'"
                      placeholder="Enter subtitle..."
                      @update:modelValue="(v) => updateHeader({ subtitle: v })"
                  />
                  <div
                    v-if="headerFieldEnabled('cta_buttons')"
                    class="hero-actions"
                    :class="{ 'hero-actions--readonly-admin': state.isAdmin }"
                  >
                    <EditableButton
                        v-for="(btn, index) in (header.ctaButtons || [])"
                        :key="index"
                        :model-value="btn"
                        :is-admin="false"
                        :button-class="ctaButtonClass(btn, index)"
                        :button-style="ctaButtonStyle(btn, index)"
                        :placeholder="index === 0 ? t.tickets : t.newsletter"
                    />
                  </div>
                </div>
              </div>
            </div>
            <div
              v-if="headerFieldEnabled('overlay_image') && header.overlayImage"
              ref="heroOverlayRef"
              class="hero-media"
              :class="[overlayUsesParabola ? 'hero-media--scroll-path' : overlayPositionClass, { 'hero-media--parallax': overlayParallaxEnabled }]"
              :style="overlayParallaxStyle"
            >
              <TransformedImage
                :src="header.overlayImage"
                alt="Hero overlay"
                class="hero-overlay-image"
                :zoom="headerOverlayZoom"
                :focal-x="headerOverlayFocalX"
                :focal-y="headerOverlayFocalY"
                :rotation="headerOverlayRotation"
                fit="contain"
                loading="lazy"
                decoding="async"
              />
            </div>
          </div>
        </div>
      </EditableBgImage>
      <div v-else class="hero-no-bg">
        <div v-if="showHeroInner" class="container hero-inner">
          <div class="hero-layout">
            <div class="hero-copy">
              <EditableText
                  v-if="headerFieldEnabled('title')"
                  :model-value="state.pageTitle"
                  :is-admin="state.isAdmin"
                  as="h1"
                  :display-class="'hero-title'"
                  placeholder="Enter title..."
                  @update:modelValue="(v) => updatePageTitle(v)"
              />
              <EditableText
                  v-if="headerFieldEnabled('subtitle')"
                  :model-value="header.subtitle"
                  :is-admin="state.isAdmin"
                  multiline
                  as="p"
                  :display-class="'hero-subtitle'"
                  placeholder="Enter subtitle..."
                  @update:modelValue="(v) => updateHeader({ subtitle: v })"
              />
              <div
                v-if="headerFieldEnabled('cta_buttons')"
                class="hero-actions"
                :class="{ 'hero-actions--readonly-admin': state.isAdmin }"
              >
                <EditableButton
                    v-for="(btn, index) in (header.ctaButtons || [])"
                    :key="index"
                    :model-value="btn"
                    :is-admin="false"
                    :button-class="ctaButtonClass(btn, index)"
                    :button-style="ctaButtonStyle(btn, index)"
                    :placeholder="index === 0 ? t.tickets : t.newsletter"
                />
              </div>
            </div>
          </div>
        </div>
        <div
          v-if="headerFieldEnabled('overlay_image') && header.overlayImage"
          ref="heroOverlayRef"
          class="hero-media"
          :class="[overlayUsesParabola ? 'hero-media--scroll-path' : overlayPositionClass, { 'hero-media--parallax': overlayParallaxEnabled }]"
          :style="overlayParallaxStyle"
        >
          <TransformedImage
            :src="header.overlayImage"
            alt="Hero overlay"
            class="hero-overlay-image"
            :zoom="headerOverlayZoom"
            :focal-x="headerOverlayFocalX"
            :focal-y="headerOverlayFocalY"
            :rotation="headerOverlayRotation"
            fit="contain"
            loading="lazy"
            decoding="async"
          />
        </div>
      </div>
      <div v-if="pinnedTickerSectionKey" class="hero-pinned-ticker">
        <TickerSection
          :section-key="pinnedTickerSectionKey"
          :section-data="state.sectionsData?.[pinnedTickerSectionKey]"
          :force-pinned-display="true"
        />
      </div>
      <div v-if="heroSeparatorType !== 'none'" class="hero-separator" :class="`hero-separator--${heroSeparatorType}`"></div>

    </section>

    <!-- Empty Header State (admin only, when header is enabled but not yet created) -->
    <section v-if="showEmptyHeaderState" class="hero hero-empty-state">
      <div class="hero-empty-content">
        <h2 class="hero-empty-title">No Header Yet</h2>
        <p class="hero-empty-text">
          Create a new header with configured fields, or reuse an existing header from the library.
        </p>
        <div class="hero-empty-actions">
          <button
            v-if="canManageHeaderForCurrentPage"
            class="btn hero-empty-btn"
            type="button"
            @click="openCreateHeader"
          >
            {{ isTemplateBuilder ? 'Create Header' : 'Manage Headers' }}
          </button>
          <button
            v-if="canManageHeaderForCurrentPage"
            class="btn hero-empty-btn hero-empty-btn--secondary"
            type="button"
            @click="handleToggleHeader(false)"
          >
            Deactivate Header
          </button>
        </div>
      </div>
    </section>

    <!-- Empty page state (for admin to create page or add sections) -->
    <section v-if="state.isAdmin && (isPageNotFound || !hasSections)" class="empty-page">
      <div class="container page-container">
        <div class="empty-card">
          <h2 v-if="isPageNotFound" class="hero-empty-title">{{ pageTitle || pageSlug || 'Coming Soon' }}</h2>
          <h2 v-else class="hero-empty-title">No Sections Yet</h2>
          <template v-if="isPageNotFound">
            <p class="hero-empty-text">
              This page doesn't exist yet. Create it manually as a static page or from a page template, or add a redirect to an existing page.
            </p>
            <div class="page-create-inline">
              <div class="page-create-inline__slug">
                <span class="page-create-inline__slug-label">URL</span>
                <span class="page-create-inline__slug-value">/{{ pageSlug }}</span>
              </div>
              <p v-if="existingRouteRedirectLoading" class="page-create-inline__hint">
                Checking existing redirects for this URL...
              </p>
              <p v-else-if="existingRouteRedirectMessage" class="page-create-inline__warning">
                {{ existingRouteRedirectMessage }}
              </p>
              <div class="page-create-inline__mode">
                <button
                  class="page-create-inline__mode-btn"
                  :class="{ active: missingPageAction === 'page' }"
                  type="button"
                  @click="setMissingPageAction('page')"
                >
                  Create Page
                </button>
                <button
                  class="page-create-inline__mode-btn"
                  :class="{ active: missingPageAction === 'redirect' }"
                  type="button"
                  @click="setMissingPageAction('redirect')"
                >
                  Create Redirect
                </button>
              </div>

              <template v-if="missingPageAction === 'page'">
                <p
                  v-if="pageCreationRouteKind === 'item_child'"
                  class="page-create-inline__error"
                >
                  This route is recognized as an item-child route (blog/program). Create the source item in the parent section to generate this page automatically.
                </p>
                <label v-else class="page-create-inline__field">
                  <span>Start From Template</span>
                  <select
                    v-model="createPageForm.templatePath"
                    class="page-create-inline__input"
                  >
                    <option value="">Empty page</option>
                    <option
                      v-for="template in staticPageTemplates"
                      :key="template.path"
                      :value="template.path"
                    >
                      {{ template.path }}
                    </option>
                  </select>
                </label>
                <div class="page-create-inline__grid">
                  <label class="page-create-inline__field" for="create-page-title-de">
                    <span>Title (DE)</span>
                    <input
                      id="create-page-title-de"
                      v-model="createPageForm.title.de"
                      type="text"
                      class="page-create-inline__input"
                      placeholder="German title"
                      autocomplete="off"
                    />
                  </label>
                  <label class="page-create-inline__field" for="create-page-title-en">
                    <span>Title (EN)</span>
                    <input
                      id="create-page-title-en"
                      v-model="createPageForm.title.en"
                      type="text"
                      class="page-create-inline__input"
                      placeholder="English title"
                      autocomplete="off"
                    />
                  </label>
                </div>
                <label class="page-create-inline__checkbox">
                  <input v-model="createPageForm.inMenu" type="checkbox" />
                  <span>Include in nav menu</span>
                </label>
                <p v-if="createPageSlugError" class="page-create-inline__error">{{ createPageSlugError }}</p>
                <p v-else-if="createPageError" class="page-create-inline__error">{{ createPageError }}</p>
                <button
                  class="btn hero-empty-btn"
                  type="button"
                  :disabled="isCreatingPage || Boolean(createPageSlugError) || pageCreationRouteKind === 'item_child'"
                  @click="createNewPage"
                >
                  {{ isCreatingPage ? 'Creating...' : 'Create Page' }}
                </button>
              </template>

              <template v-else>
                <label class="page-create-inline__field" for="create-redirect-target">
                  <span>Redirect To Page</span>
                  <select
                    id="create-redirect-target"
                    v-model="createRedirectForm.targetPath"
                    class="page-create-inline__input"
                    :disabled="!selectedCreateRedirectStatus.requiresTarget"
                  >
                    <option value="">Select a page</option>
                    <option
                      v-for="page in redirectTargetPageOptions"
                      :key="`missing-redirect-target-${page.slug}`"
                      :value="pagePathFromSlug(page.slug)"
                    >
                      {{ formatRedirectTargetPageOption(page) }}
                    </option>
                  </select>
                </label>
                <label class="page-create-inline__field" for="create-redirect-status">
                  <span>Redirect Status</span>
                  <select
                    id="create-redirect-status"
                    v-model.number="createRedirectForm.statusCode"
                    class="page-create-inline__input"
                  >
                    <option
                      v-for="statusOption in redirectStatusOptions"
                      :key="`missing-redirect-status-${statusOption.code}`"
                      :value="statusOption.code"
                    >
                      {{ statusOption.label }}
                    </option>
                  </select>
                </label>
                <p class="page-create-inline__hint">{{ selectedCreateRedirectStatus.description }}</p>
                <p v-if="redirectTargetPagesLoading" class="page-create-inline__hint">Loading pages...</p>
                <p
                  v-else-if="selectedCreateRedirectStatus.requiresTarget && redirectTargetPageOptions.length === 0"
                  class="page-create-inline__hint"
                >
                  No target pages are available right now.
                </p>
                <p v-else-if="!selectedCreateRedirectStatus.requiresTarget" class="page-create-inline__hint">
                  410 marks this URL as intentionally removed and does not redirect to another page.
                </p>
                <p v-if="createRedirectError" class="page-create-inline__error">{{ createRedirectError }}</p>
                <button
                  class="btn hero-empty-btn"
                  type="button"
                  :disabled="isCreatingRedirect || redirectTargetPagesLoading || (selectedCreateRedirectStatus.requiresTarget && !createRedirectForm.targetPath)"
                  @click="createMissingPageRedirect"
                >
                  {{ isCreatingRedirect ? 'Creating...' : 'Create Redirect' }}
                </button>
              </template>
            </div>
          </template>
          <template v-else>
            <p class="hero-empty-text">Create new sections from templates, or reuse existing sections from the section library.</p>
            <button class="btn hero-empty-btn" type="button" @click="openManageSections">
              add Section
            </button>
          </template>
        </div>
      </div>
    </section>

    <!-- Section Grid -->
    <SectionGrid 
      v-if="hasSections || showTemplatePreviewControl"
      :component-map="activeComponentMap" 
      :keys="sectionGridKeys"
      :preview-payload-available="showTemplatePreviewControl"
      :preview-payload-active="templatePreviewActive"
      :preview-payload-loading="templatePreviewLoading"
      :preview-payload-disabled="templatePreviewDisabled"
      :preview-payload-warnings="templatePreviewWarnings"
      @preview-payload-click="handleTemplatePreviewToggle"
    />

    <section
      v-if="isPageTemplateStyleLocked && state.isAdmin && !state.previewMode"
      class="page-template-style-lock-note"
    >
      <div class="container page-container">
        <p>
          Page style is controlled by template <code>{{ state.pageTemplateStyleRef || "template" }}</code>.
          Page/header/section design overrides are read-only on this page.
        </p>
      </div>
    </section>

    <!-- Section Manager Popup -->
      <SectionPanel 
      v-if="!isTemplateBuilder || props.templateBuilderContext?.kind !== 'section'"
      ref="sectionPanelRef"
      :page-slug="pageSlug"
      :template-mode="isTemplateBuilder"
      :template-builder-kind="templateBuilderKind"
      :show-header-toggle="!isTemplateBuilder || templateBuilderKind === 'page'"
      :allow-header-management="!isTemplateBuilder"
      :fixed-keys="fixedSectionKeys"
      :show-add-section="true"
      :available-section-types="availableSectionTypes"
      :available-section-templates="availableSectionTemplates"
      :available-container-templates="availableContainerTemplates"
      :has-header="headerEnabled"
      :current-header-id="header.headerId || null"
      :design-overrides-locked="isPageTemplateStyleLocked"
      :template-preview-active="templatePreviewActive"
      @add-section="handleAddSection"
      @section-removed="handleSectionRemoved"
      @template-updated="handleSectionPanelTemplateUpdated"
      @toggle-header="handleToggleHeader"
      @header-changed="handleHeaderChanged"
    />

    <aside
      v-if="state.isAdmin && !state.previewMode && !isPageNotFound && !isTemplateBuilder"
      class="page-edit-shortcut"
      :style="pageEditShortcutStyle"
    >
      <div class="container page-container page-edit-shortcut__actions">
        <button class="btn page-edit-shortcut__btn page-edit-shortcut__btn--secondary" type="button" @click="openManageSections">
          <font-awesome-icon :icon="faPlus" class="page-edit-shortcut__icon" aria-hidden="true" />
          New Section
        </button>
        <button
          v-if="showSyncTemplateButton"
          class="btn page-edit-shortcut__btn page-edit-shortcut__btn--secondary"
          type="button"
          :disabled="syncTemplateBusy"
          @click="syncCurrentPageFromTemplate"
        >
          <font-awesome-icon :icon="faRotateRight" class="page-edit-shortcut__icon" aria-hidden="true" />
          {{ syncTemplateBusy ? 'Syncing...' : 'Sync Template' }}
        </button>
        <button
          v-if="showOpenIntegrationReviewButton"
          class="btn page-edit-shortcut__btn page-edit-shortcut__btn--secondary"
          type="button"
          @click="openGeneratedIntegrationReviewItem"
        >
          <font-awesome-icon :icon="faPenToSquare" class="page-edit-shortcut__icon" aria-hidden="true" />
          Edit Data
        </button>
        <button
          v-if="showGeneratedProgramGigSyncButton"
          class="btn page-edit-shortcut__btn page-edit-shortcut__btn--secondary"
          type="button"
          :disabled="syncTemplateBusy || generatedProgramGigSyncConflictCheck.loading"
          @click="openGeneratedProgramGigSyncDialog"
        >
          <font-awesome-icon :icon="faRotateRight" class="page-edit-shortcut__icon" aria-hidden="true" />
          {{ syncTemplateBusy ? 'Syncing...' : generatedProgramGigSyncConflictCheck.loading ? 'Checking...' : 'Sync Page' }}
        </button>
        <button class="btn page-edit-shortcut__btn page-edit-shortcut__btn--edit" type="button" @click="openEditPageInSitemap">
          <font-awesome-icon :icon="faPenToSquare" class="page-edit-shortcut__icon" aria-hidden="true" />
          {{ pageEditShortcutLabel }}
        </button>
        <p
          v-if="syncTemplateStatus.message"
          class="page-edit-shortcut__status"
          :class="`page-edit-shortcut__status--${syncTemplateStatus.type || 'info'}`"
        >
          {{ syncTemplateStatus.message }}
        </p>
      </div>
    </aside>
    <div
      v-if="generatedProgramGigSyncDialog.open"
      class="generated-page-sync-dialog-backdrop"
      @click.self="closeGeneratedProgramGigSyncDialog"
    >
      <div class="generated-page-sync-dialog" role="dialog" aria-modal="true" aria-labelledby="generated-page-sync-dialog-title">
        <h3 id="generated-page-sync-dialog-title">Sync Page</h3>
        <div class="generated-page-sync-options">
          <label
            v-for="option in generatedProgramGigSyncOptions"
            :key="option.value"
            class="generated-page-sync-option"
            :class="{
              'is-selected': generatedProgramGigSyncDialog.mode === option.value,
              'generated-page-sync-option--destructive': option.destructive,
            }"
          >
            <input
              v-model="generatedProgramGigSyncDialog.mode"
              type="radio"
              name="generated-program-gig-sync-mode"
              :value="option.value"
            />
            <span>
              <strong>{{ option.label }}</strong>
              <small>{{ option.description }}</small>
            </span>
          </label>
        </div>
        <p
          v-if="generatedProgramGigSyncConflictCheck.error"
          class="generated-page-sync-dialog__warning"
        >
          {{ generatedProgramGigSyncConflictCheck.error }}
        </p>
        <div class="generated-page-sync-dialog__actions">
          <button
            class="generated-page-sync-dialog__button generated-page-sync-dialog__button--secondary"
            type="button"
            @click="closeGeneratedProgramGigSyncDialog"
          >
            Cancel
          </button>
          <button
            class="generated-page-sync-dialog__button generated-page-sync-dialog__button--primary"
            type="button"
            :disabled="syncTemplateBusy"
            @click="runGeneratedProgramGigSyncDialog"
          >
            {{ syncTemplateBusy ? 'Syncing...' : 'Sync' }}
          </button>
        </div>
      </div>
    </div>
    </div>

  </template>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, toRaw, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  faPenToSquare,
  faPlus,
  faRotateRight,
  faTriangleExclamation,
} from "@fortawesome/free-solid-svg-icons";
import draggable from "vuedraggable";
import { useStore } from "../store/store.js";
const { SECTION_TYPE_CONFIG, toCamelCase } = useStore();
import * as api from "../services/api.js";

import EditableText from "../components/ui/EditableText.vue";
import EditableBgImage from "../components/ui/EditableBgImage.vue";
import EditableButton from "../components/ui/EditableButton.vue";
import MediaLibrary from "../components/ui/MediaLibrary.vue";
import ImageTransformEditor from "../components/ui/ImageTransformEditor.vue";
import TransformedImage from "../components/ui/TransformedImage.vue";
import AuthorBadge from "../components/ui/AuthorBadge.vue";
import NotFound from "../components/NotFound.vue";
import HeaderAdminTabs from "../components/admin/section-editor/HeaderAdminTabs.vue";
import TodoIconSelect from "../components/admin/TodoIconSelect.vue";
import SectionListEditor from "../components/admin/section-editor/SectionListEditor.vue";

import SectionGrid from "../components/SectionGrid.vue";
import SectionPanel from "../components/admin/panels/SectionPanel.vue";
import { getUser, isAdmin as isAuthAdmin, initAuth as initPageAuth } from "../services/auth.js";
import {
  formatRevisionTimestampBerlin,
  getRevisionTimestampMs,
} from "../utils/revisionTime.js";
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
} from "../utils/adminTodos.js";
import { getButtonTypeInlineStyle } from "../utils/buttonTypeStyle.js";
import {
  HIGH_CONTRAST_LINK_KEY,
  HIGH_CONTRAST_TOKEN,
  resolveHighContrastColorForBackground,
  resolveLinkedColor,
} from "../utils/colorLinkOptions.js";
import {
  applyColorVariation,
  normalizeColorVariation,
} from "../utils/colorVariations.js";
import { isSectionHiddenInPublicBecauseEmptyList } from "../utils/sectionVisibilityRules.js";
import {
  buildSectionContainerMaps,
  buildSectionStructureFromEntries,
  buildSectionStructureFromOrder,
} from "../utils/sectionContainers.js";
import { buildCssSnippetsStyleText } from "../utils/cssSnippets.js";
import { getResponsivePreviewSize } from "../utils/responsiveViewport.js";

// Import all available section components
import TickerSection from "../components/sections/Ticker.vue"; // actual not a section
import BlogSection from "../components/sections/Blog.vue";
import VideoSection from "../components/sections/Video.vue";
import TextSection from "../components/sections/Text.vue";
import TextImageSection from "../components/sections/TextImage.vue";
import FaqSection from "../components/sections/Faq.vue";
import LinksSection from "../components/sections/Links.vue";
import MarkdownSection from "../components/sections/Markdown.vue";
import HtmlSection from "../components/sections/Html.vue";
import MapSection from "../components/sections/Map.vue";
import TilesSection from "../components/sections/Tiles.vue";
import GallerySection from "../components/sections/Gallery.vue";
import ProgramSection from "../components/sections/Program.vue";

// -------------------------
// Props
// -------------------------

const props = defineProps({
  slug: {
    type: String,
    default: null
  },
  fixedSectionKeys: {
    type: Array,
    default: () => []
  },
  customComponentMap: {
    type: Object,
    default: null
  },
  defaultHasHeader: {
    type: Boolean,
    default: true
  },
  templateBuilderContext: {
    type: Object,
    default: null,
  },
  templatePreviewPayload: {
    type: Object,
    default: null,
  },
  templatePreviewWarnings: {
    type: Array,
    default: () => [],
  },
  templatePreviewAvailable: {
    type: Boolean,
    default: false,
  },
  templatePreviewLoading: {
    type: Boolean,
    default: false,
  },
  templatePreviewDisabled: {
    type: Boolean,
    default: false,
  }
});

const emit = defineEmits(['template-updated', 'template-preview-toggle']);

// -------------------------
// Store Integration
// -------------------------

const route = useRoute();
const router = useRouter();
const {
  state,
  t,
  initPageState,
  logDebug,
  setTickerItems,
  refreshHeaderRevisionStatus,
  setPageSlug,
  setCurrentPageStatusMeta,
  fetchFaqSharedData,
  applyFaqSharedData,
  fetchBlogData,
  fetchProgramSharedData,
  applyProgramSharedData,
  applyMediaFallbacks,
  applyPublicDesignSettings,
  applyDesignCSS,
  transformSectionToBackendFormat,
  openSectionDesignPanel,
  saveSectionDesignOverrides,
  getEffectiveViewportDevice,
  loadDesignSettings,
  setPageTemplateStyleContext,
} = useStore();

function normalizeRoutePageSlug(value, fallback = "unknown") {
  const raw = Array.isArray(value) ? value.join("/") : String(value || "");
  const normalized = raw
    .split("?")[0]
    .split("#")[0]
    .replace(/\\/g, "/")
    .replace(/^\/+|\/+$/g, "")
    .trim();
  return normalized || fallback;
}

// Determine page slug from props or route
const pageSlug = computed(() => {
  const value = props.slug ?? route.params.slug ?? route.path;
  return normalizeRoutePageSlug(value);
});
const isTemplateBuilder = computed(() => {
  const context = props.templateBuilderContext;
  return Boolean(context && context.kind && context.path);
});
const templateBuilderKind = computed(() =>
  isTemplateBuilder.value ? String(props.templateBuilderContext?.kind || "").trim().toLowerCase() : null
);
function shouldLoadEditableDesignAfterPageLoad() {
  if (!state.canDesign) return false;
  if (isTemplateBuilder.value) return true;
  return Boolean(state.pageTemplateStyleLock) && Boolean(state.pageTemplateStyleRef);
}
const showTemplatePreviewControl = computed(() => (
  isTemplateBuilder.value
  && templateBuilderKind.value === "page"
  && props.templatePreviewAvailable
));
const templatePreviewActive = computed(() => isPreviewObject(props.templatePreviewPayload));
const templatePreviewWarnings = computed(() => (
  Array.isArray(props.templatePreviewWarnings)
    ? props.templatePreviewWarnings.filter((warning) => String(warning || "").trim())
    : []
));
const templatePreviewLoading = computed(() => Boolean(props.templatePreviewLoading));
const templatePreviewDisabled = computed(() => Boolean(props.templatePreviewDisabled));

function handleTemplatePreviewToggle() {
  if (
    isTemplateBuilder.value
    && templateBuilderKind.value === "page"
    && !templatePreviewActive.value
  ) {
    syncTemplateBuilderCanvasSectionsFromState();
    syncTemplateBuilderCanvasLayoutFromState();
  }
  emit("template-preview-toggle");
}
const isPageTemplateStyleLocked = computed(() =>
  Boolean(state.pageTemplateStyleLock) && !isTemplateBuilder.value
);
const canManageHeaderForCurrentPage = computed(() => {
  if (!isTemplateBuilder.value) return true;
  return templateBuilderKind.value === "page";
});

// -------------------------
// Default Section Component Map
// -------------------------

const DEFAULT_COMPONENT_MAP = {
  ticker: TickerSection,
  blog: BlogSection,
  video: VideoSection,
  text: TextSection,
  textImage: TextImageSection,
  text_image: TextImageSection,
  faq: FaqSection,
  links: LinksSection,
  markdown: MarkdownSection,
  html: HtmlSection,
  map: MapSection,
  tiles: TilesSection,
  gallery: GallerySection,
  program: ProgramSection,
};

// Map section_type to frontend key
const SECTION_TYPE_TO_KEY = {
  "blog": "blog",
  "text": "text",
  "text_image": "textImage",
  "video": "video",
  "faq": "faq",
  "links": "links",
  "ticker": "ticker",
  "markdown": "markdown",
  "html": "html",
  "map": "map",
  "tiles": "tiles",
  "gallery": "gallery",
  "program": "program",
};

function normalizeSectionTypeKey(value) {
  const text = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/-/g, "_");
  const normalized = text.replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
  return normalized || "text";
}

// -------------------------
// Local State
// -------------------------

const header = reactive({});
// headerEnabled: Whether the page wants a header (from pageData.has_header)
// header.hasHeader: Whether header content exists (from pageData.header being non-null)
// These are intentionally separate to support the empty header state where
// a page has header enabled but no content created yet (shows "No Header Yet" UI)
const headerEnabled = ref(false);
const sectionPanelRef = ref(null);
const heroVideoRef = ref(null);
const heroSectionRef = ref(null);
const heroOverlayRef = ref(null);
const loading = ref(false);
const error = ref(null);
const isSaving = ref(false);
const pendingHeaderSave = ref(false);
const headerAutosaveStatus = ref("idle");
const headerAutosaveError = ref("");
const availableSectionTypes = ref([]);
const availableSectionTemplates = ref([]);
const availableContainerTemplates = ref([]);
const staticPageTemplates = ref([]);
const pageCreationRouteKind = ref("static_route");
const SLUG_PATTERN = /^[a-z0-9]+(?:[-/][a-z0-9]+)*$/;
const isPageNotFound = ref(false);  // True when page doesn't exist in backend
const notFoundStatusCode = ref(404); // 404 by default, 410 for intentionally removed routes
const isPageVisible = ref(true);    // True when page content is publicly visible
const isPageUnderConstruction = ref(false); // True when page is publicly reachable but content is hidden
const isBlogGeneratedPage = ref(false); // True for pages generated from blog items
const isCreatingPage = ref(false);
const isCreatingRedirect = ref(false);
const createPageError = ref("");
const createRedirectError = ref("");
const existingRouteRedirect = ref(null);
const existingRouteRedirectLoading = ref(false);
const queuedPageReload = ref(false);
const missingPageAction = ref("page");
const redirectTargetPages = ref([]);
const redirectTargetPagesLoading = ref(false);
const currentPageMeta = ref(null);
const templateBuilderCanvasPayload = ref(null);
const syncTemplateBusy = ref(false);
const syncTemplateStatus = ref({ type: "", message: "" });
const generatedProgramGigSyncDialog = ref({
  open: false,
  mode: "keep_source",
});
const generatedProgramGigSyncConflictCheck = ref({
  loading: false,
  conflictCount: 0,
  error: "",
});
const generatedProgramGigSyncOptions = computed(() => {
  const options = [
    {
      value: "keep_source",
      label: "Sync mapped data",
      description: "Apply current item/review data to mapped fields.",
    },
  ];
  if (Number(generatedProgramGigSyncConflictCheck.value.conflictCount || 0) > 0) {
    options.push({
      value: "keep_local",
      label: "Keep page edits",
      description: "Only available because mapped fields differ from the last generated values.",
    });
  }
  options.push({
    value: "regenerate",
    label: "Regenerate page from template",
    description: "Rebuild from template and discard local generated-page changes.",
    destructive: true,
  });
  return options;
});
const createPageForm = reactive({
  title: { de: "", en: "" },
  inMenu: false,
  templatePath: "",
});
const createRedirectForm = reactive({
  targetPath: "",
  statusCode: 301,
});
const redirectStatusOptions = Object.freeze([
  {
    code: 301,
    label: "301 Permanent",
    requiresTarget: true,
    description: "Use when a URL has moved permanently. Search engines transfer ranking to the new target.",
  },
  {
    code: 302,
    label: "302 Temporary",
    requiresTarget: true,
    description: "Use for short-term redirects while content is temporarily available somewhere else.",
  },
  {
    code: 307,
    label: "307 Temporary",
    requiresTarget: true,
    description: "Use for temporary redirects when request method/body must be preserved.",
  },
  {
    code: 308,
    label: "308 Permanent",
    requiresTarget: true,
    description: "Use for permanent redirects when request method/body must be preserved.",
  },
  {
    code: 410,
    label: "410 Gone",
    requiresTarget: false,
    description: "Use when a page was intentionally removed and should disappear from search results.",
  },
]);
const headerAdminActiveTab = ref("content");
const headerNotesDraft = ref("");
const headerTodoDraft = ref([]);
const headerNewTodo = ref("");
const headerNewTodoTag = ref(DEFAULT_TODO_TAG_ID);
const headerNewTodoPriority = ref(DEFAULT_TODO_PRIORITY);
const headerTodoTagOptions = ref(normalizeTodoTags([]));
const headerHistoryLoading = ref(false);
const headerHistoryError = ref("");
const headerHistoryCurrent = ref(null);
const headerHistoryStack = ref([]);
const headerFutureStack = ref([]);
const headerHistoryOptions = ref({
  includeDesign: true,
  includeContent: true,
});
const selectedHeaderDesignRevisionKey = ref("current-design");
const selectedHeaderContentRevisionKey = ref("current-content");
const headerHistoryRevertingDesign = ref(false);
const headerHistoryRevertingContent = ref(false);
const headerMediaPickerOpen = ref(false);
const headerMediaPickerTarget = ref("background_image");
const headerFieldEditorItems = ref([]);
const headerCtaDraft = ref([]);
const headerCtaExpandedItem = ref(-1);
const headerSharingSaving = ref(false);
const headerSharingError = ref("");
const lastLoadUsedPrivatePageApi = ref(null);
const lastFocusedAdminTarget = ref("");
const hasAppliedTemplateEffectiveDesign = ref(false);
const heroSectionTopOffset = ref(0);
const heroSectionHeight = ref(0);
const heroOverlayWidth = ref(0);
const heroOverlayHeight = ref(0);
let headerHistoryLoadRequestId = 0;
let headerAutosaveStatusTimer = null;
let headerMediaAdjustDirty = false;
let heroOverlayResizeObserver = null;
const HEADER_MAX_CTA_BUTTONS = 4;
const headerRevisionSignature = computed(() => {
  const status = state.headerRevisionStatus || null;
  if (!status) return "";
  return [
    status.enabled === false ? "0" : "1",
    status.canUndo ? "1" : "0",
    status.canRedo ? "1" : "0",
    status.lastSavedAt || "",
    status.lastSavedBy || "",
  ].join("|");
});
const headerAutosaveTone = computed(() => {
  if (headerAutosaveError.value) return "error";
  return headerAutosaveStatus.value;
});
const headerAutosaveMessage = computed(() => {
  if (headerAutosaveError.value) return `Auto-save failed: ${headerAutosaveError.value}`;
  if (headerAutosaveStatus.value === "queued") return "Auto-save queued";
  if (headerAutosaveStatus.value === "saving") return "Saving changes...";
  if (headerAutosaveStatus.value === "saved") return "All changes saved";
  return "";
});

const HEADER_LAYER_OPTIONS = [
  { key: "title", label: "Title" },
  { key: "subtitle", label: "Subtitle" },
  { key: "cta_buttons", label: "Buttons" },
  { key: "overlay_image", label: "Overlay" },
  { key: "background_image", label: "Background" },
];

const HEADER_DEFAULT_LAYER_ORDER = HEADER_LAYER_OPTIONS.map((item) => item.key);
const TEMPLATE_SNIPPET_STYLE_ID = "template-css-snippets-style";
const CONTAINER_TEMPLATE_LOCK_KEY = "_templateContainerLock";
const CONTAINER_TEMPLATE_NAME_KEY = "_templateContainerName";
const SECTION_TYPE_FALLBACKS = [
  "text",
  "text_image",
  "video",
  "faq",
  "links",
  "ticker",
  "gallery",
  "blog",
  "markdown",
  "html",
  "map",
  "tiles",
  "program",
];

function buildFallbackSectionTypeList() {
  return SECTION_TYPE_FALLBACKS.map((type) => ({
    type,
    default_data: {},
  }));
}

function removeTemplateSnippetStyleElement() {
  if (typeof document === "undefined") return;
  const styleEl = document.getElementById(TEMPLATE_SNIPPET_STYLE_ID);
  if (styleEl?.parentNode) {
    styleEl.parentNode.removeChild(styleEl);
  }
}

let pageDesignBaseSnapshot = null;

function restorePageDesignOverrides() {
  if (!pageDesignBaseSnapshot || typeof pageDesignBaseSnapshot !== "object") return;
  state.design = JSON.parse(JSON.stringify(pageDesignBaseSnapshot));
  pageDesignBaseSnapshot = null;
}

function applyPageDesignOverrides(overrides) {
  if (!overrides || typeof overrides !== "object") {
    restorePageDesignOverrides();
    return;
  }
  if (!pageDesignBaseSnapshot || typeof pageDesignBaseSnapshot !== "object") {
    pageDesignBaseSnapshot = JSON.parse(JSON.stringify(state.design || {}));
  }
  const nextDesign = JSON.parse(JSON.stringify(pageDesignBaseSnapshot || {}));
  for (const [key, value] of Object.entries(overrides)) {
    nextDesign[key] = value;
  }
  state.design = nextDesign;
}

async function applyTemplateSnippetStyles() {
  if (!isTemplateBuilder.value) {
    removeTemplateSnippetStyleElement();
    return;
  }

  try {
    const response = await api.listCssSnippets();
    const snippets = Array.isArray(response?.snippets) ? response.snippets : [];
    const activeSnippets = snippets.filter((snippet) => snippet?.active && String(snippet?.css || "").trim());
    if (!activeSnippets.length) {
      removeTemplateSnippetStyleElement();
      return;
    }

    let styleEl = document.getElementById(TEMPLATE_SNIPPET_STYLE_ID);
    if (!styleEl) {
      styleEl = document.createElement("style");
      styleEl.id = TEMPLATE_SNIPPET_STYLE_ID;
      document.head.appendChild(styleEl);
    }

    const combined = buildCssSnippetsStyleText(activeSnippets, {
      responsiveConfig: state.adminDesignConfig?.responsive,
    });
    if (!combined) {
      removeTemplateSnippetStyleElement();
      return;
    }
    styleEl.textContent = combined;
  } catch (err) {
    console.error("Failed to apply template CSS snippets:", err);
  }
}

function handleTemplateSnippetsUpdated() {
  applyTemplateSnippetStyles();
}

watch(
  () => state.adminDesignConfig?.responsive,
  () => {
    applyTemplateSnippetStyles();
  },
  { deep: true }
);

// -------------------------
// Computed Properties
// -------------------------

const hasHeaderContent = computed(() => header.hasHeader === true);
const hasHeader = computed(() => headerEnabled.value && hasHeaderContent.value);
const showEmptyHeaderState = computed(() => state.isAdmin && headerEnabled.value && !hasHeaderContent.value);
const hasSections = computed(() => Object.keys(state.sectionIds || {}).length > 0);
const showHeroInner = computed(
  () =>
    headerFieldEnabled('title')
    || headerFieldEnabled('subtitle')
    || headerFieldEnabled('cta_buttons')
);
const headerCtaButtonStyleOptions = computed(() => {
  const options = new Map();
  const instances = Array.isArray(state.adminDesignConfig?.buttonInstances)
    ? state.adminDesignConfig.buttonInstances
    : [];
  instances
    .filter((item) => item?.enabled && String(item?.id || "").trim())
    .forEach((item) => {
      const id = String(item.id).trim();
      options.set(id, String(item.label || id));
    });

  if (!options.size) {
    options.set("primary", "Primary");
    options.set("secondary", "Secondary");
  }
  if (!options.has("ghost")) options.set("ghost", "Ghost");

  (headerCtaDraft.value || []).forEach((item, index) => {
    const type = normalizeCtaButtonType(item?.buttonType, index);
    if (!options.has(type)) options.set(type, formatButtonTypeLabel(type));
  });

  return Array.from(options.entries()).map(([id, label]) => ({ id, label }));
});

const showUnderConstruction = computed(() => {
  return !state.isAdmin && !isPageNotFound.value && !error.value && isPageUnderConstruction.value;
});

const underConstructionTitle = computed(() => {
  if (pageTitle.value) return pageTitle.value;
  return state.lang === 'de' ? 'Seite im Aufbau' : 'Page Under Construction';
});

const underConstructionMessage = computed(() => {
  return state.lang === 'de'
    ? 'Diese Seite befindet sich gerade im Umbau, versuch es später nochmal.'
    : 'This page is under construction, please come back later.';
});

// Show 404 page for non-admin users when page doesn't exist or has an error.
// Under-construction pages are handled by a dedicated state above.
const showNotFound = computed(() => {
  // Never show 404 in preview mode - admins are previewing as public visitors.
  if (state.previewMode) return false;
  return !state.isAdmin && (isPageNotFound.value || error.value || (!isPageVisible.value && !isPageUnderConstruction.value));
});

const pageLayout = computed(() => state.landingLayout || { order: [], hidden: {}, widths: {}, gridCols: 1, fullWidth: false });
const isPublicLikeView = computed(() => !state.isAdmin || state.previewMode);

function applyCurrentPageVisibilityStateFromStore() {
  const effectiveStatus = String(
    state.currentPageEffectiveStatus || state.currentPageStatus || ""
  ).trim().toLowerCase();
  if (!effectiveStatus) return;

  isPageUnderConstruction.value = effectiveStatus === "under_construction";
  if (state.currentPageIsVisible === true || state.currentPageIsVisible === false) {
    isPageVisible.value = state.currentPageIsVisible === true;
    return;
  }
  isPageVisible.value = effectiveStatus === "published";
}

function isPublicHiddenByEmptyListRule(sectionKey) {
  if (!isPublicLikeView.value) return false;
  return isSectionHiddenInPublicBecauseEmptyList(
    sectionKey,
    state,
    state.sectionsData?.[sectionKey] || null
  );
}

const pinnedTickerSectionKey = computed(() => {
  const order = Array.isArray(pageLayout.value?.order) ? pageLayout.value.order : [];
  for (const key of order) {
    if (pageLayout.value?.hidden?.[key] === true) continue;
    if (isPublicHiddenByEmptyListRule(key)) continue;
    const sectionType = state.sectionsData?.[key]?.sectionType;
    if (sectionType !== 'ticker') continue;
    if (state.sectionsData?.[key]?.pinToHeader === true) return key;
  }
  return null;
});

const sectionGridKeys = computed(() => {
  const sectionIds = state.sectionIds || {};
  const validSectionKeys = new Set(Object.keys(sectionIds));
  const order = Array.isArray(pageLayout.value?.order) && pageLayout.value.order.length > 0
    ? pageLayout.value.order
    : Object.keys(sectionIds);
  return order.filter((key) => {
    if (!validSectionKeys.has(key)) return false;
    if (hasHeader.value && key === pinnedTickerSectionKey.value) return false;
    if (isPublicHiddenByEmptyListRule(key)) return false;
    return true;
  });
});

const activeComponentMap = computed(() => {
  return props.customComponentMap || DEFAULT_COMPONENT_MAP;
});

const heroBackgroundUrl = computed(() => {
  return String(header.backgroundImage || "").trim();
});
const hasVisibleHeroBackground = computed(() => (
  headerFieldEnabled('background_image') && Boolean(heroBackgroundUrl.value)
));

// Helper to detect if URL is a video
function isVideoUrl(url) {
  if (!url) return false;
  const videoExtensions = ['.mp4', '.webm', '.mov', '.ogg', '.m4v'];
  const lowerUrl = url.toLowerCase();
  return videoExtensions.some(ext => lowerUrl.includes(ext));
}

const isBackgroundVideo = computed(() => isVideoUrl(heroBackgroundUrl.value));

function ensureVideoMuted() {
  if (heroVideoRef.value) {
    heroVideoRef.value.muted = true;
    heroVideoRef.value.volume = 0;
  }
}

const heroDesign = computed(() => state.design || {});

const headerOvRaw = computed(() => state.sectionDesignOverrides['__header__'] || {});

const headerOv = computed(() => {
  const ov = state.sectionDesignOverrides['__header__'];
  if (!ov || ov._active === false) return {};
  return ov;
});

const heroClasses = computed(() => {
  const cls = [];
  const baseParallax = headerOv.value.heroParallax ?? heroDesign.value.heroParallax;
  const parallax = getResponsiveDiscreteValue('heroParallax', baseParallax);
  if (parallax) cls.push('hero--parallax');
  const baseSep = headerOv.value.heroSeparator ?? heroDesign.value.heroSeparator;
  const sep = getResponsiveDiscreteValue('heroSeparator', baseSep);
  if (sep && sep !== 'none') cls.push(`hero--sep-${sep}`);
  if (!hasVisibleHeroBackground.value) cls.push('hero--no-background-image');
  return cls;
});

function normalizeHeaderZoom(value) {
  const raw = Number(value);
  if (!Number.isFinite(raw)) return 1;
  return Math.max(1, Math.min(4, raw));
}

function normalizeHeaderFocal(value) {
  const raw = Number(value);
  if (!Number.isFinite(raw)) return 50;
  return Math.max(0, Math.min(100, raw));
}

function normalizeHeaderRotation(value) {
  const raw = Number(value);
  if (!Number.isFinite(raw)) return 0;
  return Math.max(-180, Math.min(180, raw));
}

const headerBackgroundZoom = computed(() => normalizeHeaderZoom(header.backgroundZoom));
const headerBackgroundFocalX = computed(() => normalizeHeaderFocal(header.backgroundFocalX));
const headerBackgroundFocalY = computed(() => normalizeHeaderFocal(header.backgroundFocalY));
const headerBackgroundRotation = computed(() => normalizeHeaderRotation(header.backgroundRotation));
const headerOverlayZoom = computed(() => normalizeHeaderZoom(header.overlayZoom));
const headerOverlayFocalX = computed(() => normalizeHeaderFocal(header.overlayFocalX));
const headerOverlayFocalY = computed(() => normalizeHeaderFocal(header.overlayFocalY));
const headerOverlayRotation = computed(() => normalizeHeaderRotation(header.overlayRotation));

const heroBgStyle = computed(() => {
  const style = {};
  if (!heroBackgroundUrl.value) {
    style.background = "var(--bg, #ffffff)";
  }
  return style;
});

// Helper to get responsive value for discrete (non-CSS-variable) params
// Checks header override responsive values first, then global design responsive values
function getResponsiveDiscreteValue(paramKey, baseValue) {
  const device = getEffectiveViewportDevice();
  if (device === 'desktop') return baseValue;
  
  // Check header override responsive values first
  const ov = headerOv.value;
  if (hasMediaModeResponsive(ov, paramKey)) {
    const headerRv = ov._responsiveValues?.[paramKey];
    const deviceVal = headerRv?.media?.[device];
    if (deviceVal !== undefined) return deviceVal;
  }
  
  // Fall back to global design responsive values
  const paramRv = state.design.responsiveValues?.[paramKey];
  if (paramRv?.currentMode !== 'media') return baseValue;
  const deviceVal = paramRv.media?.[device];
  return deviceVal ?? baseValue;
}

// Header-editor-only discrete value (reads raw header overrides, independent of override _active flag).
function getHeaderOverrideDiscreteValue(paramKey, baseValue) {
  const device = getEffectiveViewportDevice();
  if (device === 'desktop') return baseValue;
  const ov = headerOvRaw.value;
  if (!hasMediaModeResponsive(ov, paramKey)) return baseValue;
  const headerRv = ov._responsiveValues?.[paramKey];
  const deviceVal = headerRv?.media?.[device];
  return deviceVal ?? baseValue;
}

const overlayPositionClass = computed(() => {
  const basePos = headerOv.value.heroOverlayPosition ?? (heroDesign.value.heroOverlayPosition || 'bottom-right');
  const pos = getResponsiveDiscreteValue('heroOverlayPosition', basePos);
  return `hero-media--${pos}`;
});

// Overlay scroll effect
const overlayParallaxEnabled = computed(() => {
  const baseVal = headerOv.value.heroOverlayParallax ?? heroDesign.value.heroOverlayParallax;
  return getResponsiveDiscreteValue('heroOverlayParallax', baseVal);
});

function normalizeOverlayParallaxDirection(rawValue) {
  return String(rawValue || "").trim().toLowerCase() === "parabola" ? "parabola" : "down";
}

const overlayParallaxDirection = computed(() => {
  const baseDirection = headerOv.value.heroOverlayParallaxDirection
    ?? heroDesign.value.heroOverlayParallaxDirection
    ?? "down";
  const resolved = getResponsiveDiscreteValue("heroOverlayParallaxDirection", baseDirection);
  return normalizeOverlayParallaxDirection(resolved);
});

const overlayUsesParabola = computed(
  () => overlayParallaxEnabled.value && overlayParallaxDirection.value === "parabola"
);

const overlayScrollOffset = ref(0);
const videoScrollOffset = ref(0);
const parallaxScrollY = ref(0);
const HEADER_BLUR_MIN = 0;
const HEADER_BLUR_MAX = 30;
const HEADER_BLUR_POSITION_MIN = 0;
const HEADER_BLUR_POSITION_MAX = 100;
const HEADER_BLUR_START_VH_DEFAULT = 0;
const HEADER_BLUR_END_VH_DEFAULT = 100;
const OVERLAY_PATH_VERTICAL_PADDING_PX = 24;

// Check if hero background parallax is enabled
const heroParallaxEnabled = computed(() => {
  const baseParallax = headerOv.value.heroParallax ?? heroDesign.value.heroParallax;
  return getResponsiveDiscreteValue('heroParallax', baseParallax);
});

function normalizeHeaderBlurValue(rawValue) {
  const numeric = Number(rawValue);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(HEADER_BLUR_MIN, Math.min(HEADER_BLUR_MAX, numeric));
}

function normalizeHeaderBlurPositionValue(rawValue, fallback = HEADER_BLUR_START_VH_DEFAULT) {
  const numeric = Number(rawValue);
  const resolved = Number.isFinite(numeric) ? numeric : fallback;
  return Math.max(HEADER_BLUR_POSITION_MIN, Math.min(HEADER_BLUR_POSITION_MAX, resolved));
}

function normalizeHeaderBlurMode(rawMode) {
  return String(rawMode || "").trim().toLowerCase() === "scroll" ? "scroll" : "static";
}

function hasExplicitHeaderBlurStart(rawValue) {
  return !(rawValue === undefined || rawValue === null || rawValue === "");
}

const headerBlurMode = computed(() => {
  const explicitMode = String(headerOvRaw.value?.heroBackgroundBlurMode || "").trim().toLowerCase();
  if (explicitMode === "static" || explicitMode === "scroll") return explicitMode;
  return hasExplicitHeaderBlurStart(headerOvRaw.value?.heroBackgroundBlurStart) ? "scroll" : "static";
});

const heroBackgroundBlurEnd = computed(() => {
  const baseBlur = headerOvRaw.value.heroBackgroundBlur ?? 0;
  return normalizeHeaderBlurValue(getHeaderOverrideDiscreteValue('heroBackgroundBlur', baseBlur));
});

const heroBackgroundBlurStart = computed(() => {
  const baseStart = headerOvRaw.value.heroBackgroundBlurStart;
  const responsiveStart = getHeaderOverrideDiscreteValue('heroBackgroundBlurStart', baseStart);
  if (responsiveStart === null || responsiveStart === undefined || responsiveStart === '') {
    return heroBackgroundBlurEnd.value;
  }
  return normalizeHeaderBlurValue(responsiveStart);
});

const heroBackgroundBlurStartVh = computed(() => {
  const baseStartVh = headerOvRaw.value.heroBackgroundBlurStartVh;
  const responsiveStartVh = getHeaderOverrideDiscreteValue('heroBackgroundBlurStartVh', baseStartVh);
  return normalizeHeaderBlurPositionValue(responsiveStartVh, HEADER_BLUR_START_VH_DEFAULT);
});

const heroBackgroundBlurEndVh = computed(() => {
  const baseEndVh = headerOvRaw.value.heroBackgroundBlurEndVh;
  const responsiveEndVh = getHeaderOverrideDiscreteValue('heroBackgroundBlurEndVh', baseEndVh);
  return normalizeHeaderBlurPositionValue(responsiveEndVh, HEADER_BLUR_END_VH_DEFAULT);
});

const heroBlurScrollProgress = computed(() => {
  if (!heroBackgroundUrl.value || isBackgroundVideo.value || headerBlurMode.value !== "scroll") {
    return 1;
  }
  const viewportHeight = typeof window !== 'undefined' ? window.innerHeight : 900;
  const startDistance = (heroBackgroundBlurStartVh.value / 100) * viewportHeight;
  const endDistance = (Math.max(heroBackgroundBlurEndVh.value, heroBackgroundBlurStartVh.value) / 100) * viewportHeight;
  if (endDistance <= startDistance) {
    return parallaxScrollY.value >= startDistance ? 1 : 0;
  }
  const progress = (parallaxScrollY.value - startDistance) / (endDistance - startDistance);
  return Math.max(0, Math.min(1, progress));
});

const heroBackgroundBlurCurrent = computed(() => {
  if (!heroBackgroundUrl.value || isBackgroundVideo.value) return 0;
  const endBlur = heroBackgroundBlurEnd.value;
  if (headerBlurMode.value !== "scroll") return endBlur;
  const startBlur = heroBackgroundBlurStart.value;
  if (startBlur <= 0 && endBlur <= 0) return 0;
  return startBlur + ((endBlur - startBlur) * heroBlurScrollProgress.value);
});

function measureHeroOverlayMetrics() {
  const heroEl = heroSectionRef.value;
  if (heroEl) {
    const rect = heroEl.getBoundingClientRect();
    heroSectionTopOffset.value = rect.top + (typeof window !== "undefined" ? window.scrollY : 0);
    heroSectionHeight.value = Math.max(0, Number(rect.height || heroEl.offsetHeight || 0));
  } else {
    heroSectionTopOffset.value = 0;
    heroSectionHeight.value = 0;
  }

  const overlayEl = heroOverlayRef.value;
  if (overlayEl) {
    const rect = overlayEl.getBoundingClientRect();
    heroOverlayWidth.value = Math.max(0, Number(rect.width || overlayEl.offsetWidth || 0));
    heroOverlayHeight.value = Math.max(0, Number(rect.height || overlayEl.offsetHeight || 0));
  } else {
    heroOverlayWidth.value = 0;
    heroOverlayHeight.value = 0;
  }
}

function disconnectHeroOverlayResizeObserver() {
  if (!heroOverlayResizeObserver) return;
  heroOverlayResizeObserver.disconnect();
  heroOverlayResizeObserver = null;
}

function setupHeroOverlayResizeObserver() {
  disconnectHeroOverlayResizeObserver();
  if (typeof window === "undefined" || typeof ResizeObserver === "undefined") return;
  const observer = new ResizeObserver(() => {
    measureHeroOverlayMetrics();
  });
  heroOverlayResizeObserver = observer;
  if (heroSectionRef.value) observer.observe(heroSectionRef.value);
  if (heroOverlayRef.value) observer.observe(heroOverlayRef.value);
}

function handleParallaxScroll() {
  const scrollY = window.scrollY;
  parallaxScrollY.value = scrollY;
  const heroEl = heroSectionRef.value;
  if (heroEl) {
    const rect = heroEl.getBoundingClientRect();
    heroSectionTopOffset.value = rect.top + scrollY;
    if (heroSectionHeight.value <= 0) {
      heroSectionHeight.value = Math.max(0, Number(rect.height || heroEl.offsetHeight || 0));
    }
  }
  if (overlayParallaxEnabled.value) {
    overlayScrollOffset.value = overlayUsesParabola.value ? 0 : (scrollY * 0.5);
  } else {
    overlayScrollOffset.value = 0;
  }
  if (heroParallaxEnabled.value) {
    videoScrollOffset.value = scrollY * 0.5;
  }
}

function handleViewportResize() {
  measureHeroOverlayMetrics();
  handleParallaxScroll();
}

const overlayPathProgress = computed(() => {
  if (!overlayUsesParabola.value || !header.overlayImage) return 0;
  const heroHeight = heroSectionHeight.value > 0
    ? heroSectionHeight.value
    : (typeof window !== "undefined" ? window.innerHeight : 900);
  // Finish movement while the header is still in view and scale travel to hero height.
  const travelDistance = Math.max(120, heroHeight * 0.72);
  const progressRaw = (parallaxScrollY.value - heroSectionTopOffset.value) / travelDistance;
  return Math.max(0, Math.min(1, progressRaw));
});

const overlayPathYOffset = computed(() => {
  if (!overlayUsesParabola.value || !header.overlayImage) return 0;
  const progress = overlayPathProgress.value;
  const heroHeight = heroSectionHeight.value > 0
    ? heroSectionHeight.value
    : (typeof window !== "undefined" ? window.innerHeight : 900);
  const overlayHeight = heroOverlayHeight.value > 0 ? heroOverlayHeight.value : 0;
  const availableUpward = Math.max(
    0,
    heroHeight - overlayHeight - (OVERLAY_PATH_VERTICAL_PADDING_PX * 2)
  );
  if (availableUpward <= 0) return 0;
  const preferredArc = Math.max(72, heroHeight * 0.34);
  const arcPeak = Math.min(availableUpward, preferredArc);
  return 4 * arcPeak * progress * (1 - progress);
});

const overlayParallaxStyle = computed(() => {
  if (!overlayParallaxEnabled.value) return {};
  if (!overlayUsesParabola.value) {
    return { "--parallax-offset": `${overlayScrollOffset.value.toFixed(2)}px` };
  }
  const style = {
    '--overlay-path-progress': overlayPathProgress.value.toFixed(4),
    '--overlay-path-y': `${overlayPathYOffset.value.toFixed(2)}px`,
  };
  if (heroOverlayWidth.value > 0) {
    style["--overlay-path-width"] = `${heroOverlayWidth.value.toFixed(2)}px`;
  }
  return style;
});

const videoParallaxStyle = computed(() => {
  if (!heroParallaxEnabled.value || !isBackgroundVideo.value) return {};
  // Scale video larger and shift based on scroll for parallax effect
  // Initial offset centers the extra height, scroll moves it slower than content
  const baseOffset = -50; // Start offset in pixels
  return { 
    transform: `translateY(${baseOffset + videoScrollOffset.value}px)`,
    height: '120%'
  };
});

const heroImageParallaxStyle = computed(() => {
  if (isBackgroundVideo.value) return {};
  const style = {};
  if (heroParallaxEnabled.value) {
    style.transform = `translateY(${videoScrollOffset.value * 0.5}px)`;
  }
  if (heroBackgroundBlurCurrent.value > 0) {
    style.filter = `blur(${heroBackgroundBlurCurrent.value.toFixed(2)}px)`;
  }
  return style;
});

const heroSeparatorType = computed(() => {
  const baseSep = headerOv.value.heroSeparator ?? (heroDesign.value.heroSeparator || 'none');
  return getResponsiveDiscreteValue('heroSeparator', baseSep);
});

// Helper to check if a param has media mode responsive values
function hasMediaModeResponsive(ov, key) {
  if (!ov || !key) return false;
  // Check _responsiveModes first (new way) - if explicitly set, use it
  if (ov._responsiveModes && key in ov._responsiveModes) {
    return ov._responsiveModes[key] === 'media';
  }
  // Check _responsiveValues.currentMode when available
  const respVal = ov._responsiveValues?.[key];
  if (respVal?.currentMode === 'media') return true;
  // Check if media values exist with actual data even without explicit mode
  const media = respVal?.media;
  if (media && typeof media === 'object' && Object.keys(media).length > 0) return true;
  return false;
}

// Convert viewport units (vw, vh) to pixels based on simulated viewport
function convertViewportUnits(value) {
  const sim = state.simulatedViewport;
  if (!sim || !value || typeof value !== 'string') return value;
  
  const viewport = getResponsivePreviewSize(state.adminDesignConfig?.responsive, sim);
  if (!viewport) return value;
  
  // Replace vw units with calculated pixel values
  let result = value.replace(/(\d+(?:\.\d+)?)\s*vw/gi, (match, num) => {
    const px = (parseFloat(num) / 100) * viewport.width;
    return `${px}px`;
  });
  
  // Replace vh units with calculated pixel values
  result = result.replace(/(\d+(?:\.\d+)?)\s*vh/gi, (match, num) => {
    const px = (parseFloat(num) / 100) * viewport.height;
    return `${px}px`;
  });
  
  return result;
}

function getHeaderOverrideColorVariation(paramKey) {
  const overrideMap = (headerOv.value?._colorVariations && typeof headerOv.value._colorVariations === "object")
    ? headerOv.value._colorVariations
    : {};
  const designMap = (state.design?.colorVariations && typeof state.design.colorVariations === "object")
    ? state.design.colorVariations
    : {};
  const adminMap = (state.adminDesignConfig?.colorVariations && typeof state.adminDesignConfig.colorVariations === "object")
    ? state.adminDesignConfig.colorVariations
    : {};

  if (Object.prototype.hasOwnProperty.call(overrideMap, paramKey)) {
    return normalizeColorVariation(overrideMap[paramKey]);
  }
  if (Object.prototype.hasOwnProperty.call(designMap, paramKey)) {
    return normalizeColorVariation(designMap[paramKey]);
  }
  if (Object.prototype.hasOwnProperty.call(adminMap, paramKey)) {
    return normalizeColorVariation(adminMap[paramKey]);
  }
  return 100;
}

function resolveHeaderOverrideColor(paramKey, overrideValue) {
  const linkKey = headerOv.value?._colorLinks?.[paramKey]
    || state.adminDesignConfig?.colorLinks?.[paramKey]
    || null;
  const linkedColor = linkKey
    ? resolveLinkedColor(state.design, linkKey, state.adminDesignConfig?.parameters)
    : null;
  let colorValue = linkedColor ?? overrideValue;
  if (colorValue === null || colorValue === undefined || colorValue === "") return null;

  if (colorValue === HIGH_CONTRAST_TOKEN || linkKey === HIGH_CONTRAST_LINK_KEY) {
    const highContrastBackground = (
      !hasVisibleHeroBackground.value
      && (paramKey === "heroTitleColor" || paramKey === "heroSubtitleColor")
    )
      ? {
          backgroundColor: resolvePageBackgroundColor(),
          backgroundBaseKey: "backgroundColor",
        }
      : {
          backgroundColor: state.design.sectionBackgroundColor || state.design.backgroundSecondaryColor || "#ffffff",
          backgroundBaseKey: "sectionBackgroundColor",
        };
    colorValue = resolveHighContrastColorForBackground(
      state.design,
      state.adminDesignConfig,
      highContrastBackground
    );
  }

  return applyColorVariation(colorValue, getHeaderOverrideColorVariation(paramKey));
}

function resolvePageBackgroundColor() {
  const fallback = state.design.backgroundPrimaryColor || "#f6f7fb";
  const linkKey = state.adminDesignConfig?.colorLinks?.backgroundColor || null;
  const linkedColor = linkKey
    ? resolveLinkedColor(state.design, linkKey, state.adminDesignConfig?.parameters)
    : null;
  const colorValue = linkedColor ?? state.design.backgroundColor ?? fallback;
  if (colorValue === "transparent" || colorValue === HIGH_CONTRAST_TOKEN) return fallback;
  return colorValue;
}

const pageEditShortcutStyle = computed(() => {
  const backgroundColor = resolvePageBackgroundColor();
  const highContrastColor = resolveHighContrastColorForBackground(
    state.design,
    state.adminDesignConfig,
    {
      backgroundColor,
      backgroundBaseKey: "backgroundColor",
    }
  );
  return {
    "--page-edit-shortcut-hover-bg": highContrastColor || "#0f172a",
    "--page-edit-shortcut-hover-color": backgroundColor || "#ffffff",
    "--page-edit-shortcut-edit-hover-bg": backgroundColor || "#ffffff",
    "--page-edit-shortcut-edit-hover-color": highContrastColor || "#0f172a",
  };
});

const heroOverrideStyle = computed(() => {
  const ov = headerOv.value;
  if (!ov || Object.keys(ov).length === 0) return {};
  const style = {};
  // CSS property mapping with the parameter's actual unit from admin config
  // Header overrides use the param's configured unit, not global selectedUnits
  const cssMap = {
    heroHeight: ['--hero-height', 'vh'],
    headerInner: ['--header-inner', 'px'],
    heroTitleFontSize: ['--hero-title-font-size', 'px'],
    heroTitleLineHeight: ['--hero-title-line-height', ''],
    heroTitleLetterSpacing: ['--hero-title-letter-spacing', 'em'],
    heroTitleColor: ['--hero-title-color', ''],
    heroSubtitleFontSize: ['--hero-subtitle-font-size', 'px'],
    heroSubtitleLineHeight: ['--hero-subtitle-line-height', ''],
    heroSubtitleLetterSpacing: ['--hero-subtitle-letter-spacing', 'em'],
    heroSubtitleColor: ['--hero-subtitle-color', ''],
    heroOverlaySize: ['--hero-overlay-size', 'px'],
  };
  const colorOverrideKeys = new Set(["heroTitleColor", "heroSubtitleColor"]);
  const alignMap = { left: 'flex-start', center: 'center', right: 'flex-end' };
  const device = getEffectiveViewportDevice();
  
  for (const [key, [cssProp, fallbackUnit]] of Object.entries(cssMap)) {
    // For header overrides, check override's selected unit first, then config unit
    // Don't use global selectedUnits (which may have a different unit for responsive modes)
    const overrideUnit = ov._selectedUnits?.[key];
    const paramConfig = state.adminDesignConfig?.parameters?.[key];
    const unit = overrideUnit ?? paramConfig?.unit ?? fallbackUnit;
    
    // Check for responsive override value first when simulating
    let value = ov[key];
    if (device !== 'desktop' && hasMediaModeResponsive(ov, key)) {
      const respVal = ov._responsiveValues?.[key];
      if (respVal?.media?.[device] !== undefined) {
        value = respVal.media[device];
      }
    }

    if (colorOverrideKeys.has(key)) {
      const resolvedColor = resolveHeaderOverrideColor(key, value);
      if (resolvedColor != null) style[cssProp] = resolvedColor;
      continue;
    }

    if (value != null) {
      // If value is already a string (e.g., from advanced input), use it directly
      let cssValue;
      if (typeof value === 'string') {
        cssValue = value;
      } else {
        cssValue = unit ? `${value}${unit}` : String(value);
      }
      // Convert viewport units (vw, vh) to pixels during simulation
      style[cssProp] = convertViewportUnits(cssValue);
    }
  }
  
  // Handle heroContentAlign (discrete, not CSS variable based)
  let alignValue = ov.heroContentAlign;
  if (device !== 'desktop' && hasMediaModeResponsive(ov, 'heroContentAlign')) {
    const respVal = ov._responsiveValues?.heroContentAlign;
    if (respVal?.media?.[device] !== undefined) {
      alignValue = respVal.media[device];
    }
  }
  if (alignValue) {
    style['--hero-content-align'] = alignMap[alignValue] || alignValue;
    const textMap = { left: 'left', center: 'center', right: 'right' };
    style['--hero-text-align'] = textMap[alignValue] || alignValue;
  }

  const z = headerLayerZIndices.value;
  style["--hero-z-title"] = String(z.title ?? 5);
  style["--hero-z-subtitle"] = String(z.subtitle ?? 4);
  style["--hero-z-buttons"] = String(z.cta_buttons ?? 3);
  style["--hero-z-overlay"] = String(z.overlay_image ?? 2);
  style["--hero-z-background"] = String(z.background_image ?? 1);
  
  return style;
});

const pageTitle = computed(() => {
  return state.pageTitle?.[state.lang] || state.pageTitle?.de || "";
});

function normalizeSeoSlug(slug) {
  const normalized = String(slug || "").trim().replace(/^\/+|\/+$/g, "");
  if (!normalized || normalized === "landing") return "";
  return normalized;
}

function publicPathForLang(lang, slug) {
  const normalized = normalizeSeoSlug(slug);
  if (lang === "en") return normalized ? `/en/${normalized}` : "/en";
  return normalized ? `/${normalized}` : "/";
}

function upsertHeadLink(id, rel, href, hreflang = null) {
  if (typeof document === "undefined") return;
  let el = document.head.querySelector(`link[data-seo-id="${id}"]`);
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("data-seo-id", id);
    document.head.appendChild(el);
  }
  el.setAttribute("rel", rel);
  el.setAttribute("href", href);
  if (hreflang) {
    el.setAttribute("hreflang", hreflang);
  } else {
    el.removeAttribute("hreflang");
  }
}

function clearSeoHeadLinks() {
  if (typeof document === "undefined") return;
  const nodes = document.head.querySelectorAll("link[data-seo-id]");
  nodes.forEach((node) => node.remove());
}

function applyPublicSeoHead() {
  if (typeof window === "undefined" || typeof document === "undefined") return;
  if (state.isAdmin || isTemplateBuilder.value || route.path.startsWith("/admin")) {
    clearSeoHeadLinks();
    return;
  }

  const origin = window.location.origin;
  const slug = pageSlug.value;
  const canonicalPath = publicPathForLang(state.lang, slug);
  const dePath = publicPathForLang("de", slug);
  const enPath = publicPathForLang("en", slug);

  upsertHeadLink("canonical", "canonical", `${origin}${canonicalPath}`);
  upsertHeadLink("alt-de", "alternate", `${origin}${dePath}`, "de");
  upsertHeadLink("alt-en", "alternate", `${origin}${enPath}`, "en");
  upsertHeadLink("alt-x-default", "alternate", `${origin}${dePath}`, "x-default");

  const normalizedTitle = String(pageTitle.value || "").trim();
  if (normalizedTitle) {
    document.title = normalizedTitle;
  }
}

function pagePathFromSlug(slug) {
  const normalized = String(slug || "").trim().replace(/^\/+|\/+$/g, "");
  if (!normalized || normalized === "landing") return "/";
  return `/${normalized}`;
}

function normalizeFocusQueryValue(value) {
  const first = Array.isArray(value) ? value[0] : value;
  return String(first || "").trim();
}

function escapeDataAttrValue(value) {
  const raw = String(value || "");
  if (typeof CSS !== "undefined" && typeof CSS.escape === "function") {
    return CSS.escape(raw);
  }
  return raw.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function resolveSectionKeyBySectionId(sectionId) {
  const targetId = String(sectionId || "").trim();
  if (!targetId) return "";
  const entries = Object.entries(state.sectionIds || {});
  const matched = entries.find(([, id]) => String(id || "").trim() === targetId);
  return matched?.[0] || "";
}

async function focusAdminTargetFromQuery() {
  if (!state.isAdmin || loading.value || isPageNotFound.value) return;

  const focusSectionId = normalizeFocusQueryValue(route.query.focus_section_id);
  const focusHeaderId = normalizeFocusQueryValue(route.query.focus_header_id);
  if (!focusSectionId && !focusHeaderId) {
    lastFocusedAdminTarget.value = "";
    return;
  }

  const signature = `${pageSlug.value}|${focusSectionId}|${focusHeaderId}`;
  if (lastFocusedAdminTarget.value === signature) return;

  await nextTick();
  if (typeof document === "undefined") return;

  if (focusSectionId) {
    const sectionKey = resolveSectionKeyBySectionId(focusSectionId);
    if (sectionKey) {
      const selectorValue = escapeDataAttrValue(sectionKey);
      const sectionEl = document.querySelector(`.grid-item-content[data-section-key="${selectorValue}"]`);
      if (sectionEl && typeof sectionEl.scrollIntoView === "function") {
        sectionEl.scrollIntoView({ behavior: "smooth", block: "center" });
        lastFocusedAdminTarget.value = signature;
        return;
      }
    }
  }

  if (focusHeaderId && String(header.headerId || "").trim() === focusHeaderId) {
    const heroEl = heroSectionRef.value;
    if (heroEl && typeof heroEl.scrollIntoView === "function") {
      heroEl.scrollIntoView({ behavior: "smooth", block: "start" });
      lastFocusedAdminTarget.value = signature;
    }
  }
}

function isGeneratedManagedPage(page) {
  if (!page || typeof page !== "object") return false;
  if (page.generated_from_blog === true) return true;
  if (page.template_managed === true) return true;
  const sourceType = String(page.template_source_type || "").trim().toLowerCase();
  if (
    sourceType === "blog"
    || sourceType === "tiles"
    || sourceType === "program"
    || sourceType === "program_stage"
    || sourceType === "program_gig"
  ) return true;
  const slug = String(page.slug || "").trim().toLowerCase();
  if (slug.startsWith("__template_")) return true;
  return false;
}

function generatedManagedPageActionAvailable(pageMeta) {
  if (!state.isAdmin || state.previewMode || isTemplateBuilder.value || isPageNotFound.value) return false;
  if (!isGeneratedManagedPage(pageMeta)) return false;
  return true;
}

function generatedTemplateSyncActionAvailable(pageMeta) {
  if (!generatedManagedPageActionAvailable(pageMeta)) return false;
  const status = String(
    state.currentPageStatus || pageMeta?.status || ""
  ).trim().toLowerCase();
  return Boolean(status) && status !== "init";
}

const isGeneratedProgramGigPage = computed(() =>
  String(currentPageMeta.value?.template_source_type || "").trim().toLowerCase() === "program_gig"
);

const showGeneratedProgramGigSyncButton = computed(() =>
  generatedManagedPageActionAvailable(currentPageMeta.value) && isGeneratedProgramGigPage.value
);

const showSyncTemplateButton = computed(() => {
  if (!generatedTemplateSyncActionAvailable(currentPageMeta.value)) return false;
  return !isGeneratedProgramGigPage.value;
});

const generatedIntegrationReviewRoute = computed(() => {
  const pageMeta = currentPageMeta.value || {};
  const integrationId = String(pageMeta.template_integration_id || "").trim();
  if (!integrationId) return null;
  const itemKey = String(pageMeta.template_integration_item_key || "").trim();
  return {
    path: "/admin/integrations/review",
    query: itemKey ? { integrationId, itemKey } : { integrationId },
  };
});

const showOpenIntegrationReviewButton = computed(() => {
  if (!state.isAdmin || state.previewMode || isTemplateBuilder.value || isPageNotFound.value) return false;
  return Boolean(generatedIntegrationReviewRoute.value);
});

function resolveGeneratedPageTemplatePath(pageMeta) {
  return String(
    pageMeta?.template_style_ref
    || state.pageTemplateStyleRef
    || ""
  )
    .trim()
    .replace(/^\/+|\/+$/g, "");
}

const pageEditShortcutLabel = computed(() => {
  const pageMeta = currentPageMeta.value;
  return isGeneratedManagedPage(pageMeta) && resolveGeneratedPageTemplatePath(pageMeta)
    ? "Edit Template"
    : "Edit Page";
});

function isAdminLikePagePath(path) {
  const normalized = String(path || "").trim().toLowerCase();
  return normalized === "/admin" || normalized.startsWith("/admin/");
}

function isRedirectTargetPageSelectable(page) {
  const path = pagePathFromSlug(page?.slug);
  if (isAdminLikePagePath(path)) return false;
  if (isGeneratedManagedPage(page)) return false;
  return true;
}

function formatRedirectTargetPageOption(page) {
  return pagePathFromSlug(page?.slug);
}

const createPageSlugError = computed(() => {
  const slug = String(pageSlug.value || "").trim();
  if (!slug || slug === "unknown") {
    return "Invalid URL slug. Please navigate to a valid page path first.";
  }
  if (!SLUG_PATTERN.test(slug)) {
    return "URL slug has an invalid format. Use lowercase letters, numbers, hyphens, and slashes.";
  }
  return "";
});

const missingPageSourcePath = computed(() => pagePathFromSlug(pageSlug.value));

const existingRouteRedirectMessage = computed(() => {
  const redirect = existingRouteRedirect.value;
  if (!redirect || !isPageNotFound.value) return "";
  const sourcePath = String(redirect.source_path || "");
  const currentPath = missingPageSourcePath.value;
  const statusCode = Number(redirect.status_code) || 301;
  const targetLabel = redirect.target_path || "410 Gone (Removed)";
  const activeLabel = redirect.is_active ? "Active" : "Inactive";
  if (sourcePath === currentPath) {
    return `${activeLabel} redirect already exists for this URL: ${sourcePath} -> ${targetLabel} (${statusCode}).`;
  }
  return `${activeLabel} wildcard redirect matches this URL: ${sourcePath} -> ${targetLabel} (${statusCode}).`;
});

const redirectTargetPageOptions = computed(() => {
  const sourcePath = missingPageSourcePath.value;
  return [...redirectTargetPages.value]
    .filter((page) => isRedirectTargetPageSelectable(page))
    .filter((page) => pagePathFromSlug(page?.slug) !== sourcePath)
    .sort((a, b) => {
      if (a.slug === "landing") return -1;
      if (b.slug === "landing") return 1;
      return String(a.slug || "").localeCompare(String(b.slug || ""));
    });
});

const selectedCreateRedirectStatus = computed(() => {
  return redirectStatusOptions.find((item) => item.code === Number(createRedirectForm.statusCode))
    || redirectStatusOptions[0];
});

const headerOpenTodos = computed(() => headerTodoDraft.value.filter((todo) => !todo.done));
const headerDoneTodos = computed(() => headerTodoDraft.value.filter((todo) => todo.done));
const headerOpenTodoCount = computed(() => headerOpenTodos.value.length);
const defaultHeaderTodoTagId = computed(() => {
  if (headerTodoTagOptions.value.some((tag) => tag.id === "text")) return "text";
  return headerTodoTagOptions.value[0]?.id || DEFAULT_TODO_TAG_ID;
});
const headerTodoPrioritySelectOptions = TODO_PRIORITY_VALUES.map((priority) => todoPrioritySelectOption(priority));
const headerTodoTagSelectOptions = computed(() =>
  headerTodoTagOptions.value.map((tag) => todoTagSelectOption(tag.id))
);
const headerBackgroundPreviewUrl = computed(() => String(header.backgroundImage || "").trim());
const headerOverlayPreviewUrl = computed(() => String(header.overlayImage || "").trim());
const headerMediaPickerCurrentUrl = computed(() =>
  headerMediaPickerTarget.value === "overlay_image"
    ? headerOverlayPreviewUrl.value
    : headerBackgroundPreviewUrl.value
);
const headerMediaPickerSourceContext = computed(() =>
  headerMediaPickerTarget.value === "overlay_image"
    ? "header.overlay"
    : "header.background"
);

function sanitizeHeaderLayerOrder(orderCandidate) {
  const allowed = new Set(HEADER_LAYER_OPTIONS.map((item) => item.key));
  const next = [];
  if (Array.isArray(orderCandidate)) {
    for (const key of orderCandidate) {
      if (typeof key !== "string") continue;
      if (!allowed.has(key) || next.includes(key)) continue;
      next.push(key);
    }
  }
  for (const key of HEADER_DEFAULT_LAYER_ORDER) {
    if (!next.includes(key)) next.push(key);
  }
  return next;
}

const headerLayerOrder = computed(() => {
  const ov = headerOv.value;
  return sanitizeHeaderLayerOrder(ov?.heroLayerOrder);
});

const headerBlurEndEditorValue = computed(() => {
  const explicitEnd = headerOvRaw.value?.heroBackgroundBlur;
  if (explicitEnd !== undefined && explicitEnd !== null && explicitEnd !== "") {
    return normalizeHeaderBlurValue(explicitEnd);
  }
  return normalizeHeaderBlurValue(heroBackgroundBlurEnd.value);
});

const headerBlurStartOverrideValue = computed(() => headerOvRaw.value?.heroBackgroundBlurStart);
const headerBlurStartEditorValue = computed(() => {
  if (!hasExplicitHeaderBlurStart(headerBlurStartOverrideValue.value)) return headerBlurEndEditorValue.value;
  return normalizeHeaderBlurValue(headerBlurStartOverrideValue.value);
});
const headerBlurStartVhEditorValue = computed(() => {
  return normalizeHeaderBlurPositionValue(headerOvRaw.value?.heroBackgroundBlurStartVh, HEADER_BLUR_START_VH_DEFAULT);
});
const headerBlurEndVhEditorValue = computed(() => {
  return normalizeHeaderBlurPositionValue(headerOvRaw.value?.heroBackgroundBlurEndVh, HEADER_BLUR_END_VH_DEFAULT);
});
const showHeaderBlurStartControl = computed(() => headerBlurMode.value === "scroll");

function buildHeaderFieldEditorItems(orderKeys) {
  const labels = Object.fromEntries(HEADER_LAYER_OPTIONS.map((item) => [item.key, item.label]));
  return sanitizeHeaderLayerOrder(orderKeys).map((key) => ({
    key,
    label: labels[key] || key,
  }));
}

watch(
  headerLayerOrder,
  (order) => {
    const nextItems = buildHeaderFieldEditorItems(order);
    const currentOrder = headerFieldEditorItems.value.map((item) => item.key);
    const nextOrder = nextItems.map((item) => item.key);
    if (JSON.stringify(currentOrder) === JSON.stringify(nextOrder)) return;
    headerFieldEditorItems.value = nextItems;
  },
  { immediate: true }
);

const headerLayerZIndices = computed(() => {
  const order = headerLayerOrder.value;
  // Keep default background layer at the same stacking level as .hero-overlay
  // so DOM order keeps copy/overlay above it, while still allowing reordering.
  const top = Math.max(order.length, 1);
  const z = {};
  order.forEach((key, index) => {
    z[key] = top - index;
  });
  return z;
});

function normalizeParamDiffs(value) {
  if (!Array.isArray(value)) return [];
  const cleaned = value
    .map((item) => String(item || "").trim())
    .filter(Boolean);
  return Array.from(new Set(cleaned));
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
  const snapshot = kind === "design" ? entry?.designSnapshot : entry?.contentSnapshot;
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

const headerRevisionEntries = computed(() => {
  const current = [];
  if (headerHistoryCurrent.value) {
    current.push({
      key: "current-design",
      source: "current",
      savedAt: headerHistoryCurrent.value.design_saved_at ?? null,
      savedBy: headerHistoryCurrent.value.design_saved_by || "unknown",
      changeKind: "design",
      designSnapshot: headerHistoryCurrent.value.design_snapshot || null,
      contentSnapshot: null,
      designParamDiffs: entryParamDiffs(
        {
          design_param_diffs: headerHistoryCurrent.value.design_param_diffs,
          content_param_diffs: [],
          param_diffs: headerHistoryCurrent.value.param_diffs,
          change_kind: "design",
          designSnapshot: headerHistoryCurrent.value.design_snapshot || null,
        },
        "design"
      ),
      contentParamDiffs: [],
    });
    current.push({
      key: "current-content",
      source: "current",
      savedAt: headerHistoryCurrent.value.content_saved_at ?? null,
      savedBy: headerHistoryCurrent.value.content_saved_by || "unknown",
      changeKind: "content",
      designSnapshot: null,
      contentSnapshot: headerHistoryCurrent.value.content_snapshot || null,
      designParamDiffs: [],
      contentParamDiffs: entryParamDiffs(
        {
          design_param_diffs: [],
          content_param_diffs: headerHistoryCurrent.value.content_param_diffs,
          param_diffs: headerHistoryCurrent.value.param_diffs,
          change_kind: "content",
          contentSnapshot: headerHistoryCurrent.value.content_snapshot || null,
        },
        "content"
      ),
    });
  }

  const historyItems = headerHistoryStack.value.map((entry, index) => ({
    key: `history-${index}`,
    source: "history",
    savedAt: entry.saved_at || null,
    savedBy: entry.saved_by || "unknown",
    changeKind: entry.change_kind || null,
    designSnapshot: entry.design_snapshot || null,
    contentSnapshot: entry.content_snapshot || null,
    designParamDiffs: entryParamDiffs(entry, "design"),
    contentParamDiffs: entryParamDiffs(entry, "content"),
  }));

  const futureItems = headerFutureStack.value.map((entry, index) => ({
    key: `future-${index}`,
    source: "future",
    savedAt: entry.saved_at || null,
    savedBy: entry.saved_by || "unknown",
    changeKind: entry.change_kind || null,
    designSnapshot: entry.design_snapshot || null,
    contentSnapshot: entry.content_snapshot || null,
    designParamDiffs: entryParamDiffs(entry, "design"),
    contentParamDiffs: entryParamDiffs(entry, "content"),
  }));

  const ordered = [...historyItems, ...futureItems].sort((left, right) => {
    const leftTs = getRevisionTimestampMs(left.savedAt);
    const rightTs = getRevisionTimestampMs(right.savedAt);
    return rightTs - leftTs;
  });

  return [...current, ...ordered];
});

const headerDesignHistoryEntries = computed(() =>
  headerRevisionEntries.value
    .filter((entry) =>
      entry.key === "current-design" ||
      entry.changeKind === "design" ||
      entry.changeKind === "both"
    )
    .slice(0, 5)
);

const headerContentHistoryEntries = computed(() =>
  headerRevisionEntries.value
    .filter((entry) =>
      entry.key === "current-content" ||
      entry.changeKind === "content" ||
      entry.changeKind === "both"
    )
    .slice(0, 5)
);

const selectedHeaderDesignRevisionEntry = computed(() =>
  headerRevisionEntries.value.find((entry) => entry.key === selectedHeaderDesignRevisionKey.value) || null
);

const selectedHeaderContentRevisionEntry = computed(() =>
  headerRevisionEntries.value.find((entry) => entry.key === selectedHeaderContentRevisionKey.value) || null
);

const canRevertHeaderDesign = computed(() => {
  const entry = selectedHeaderDesignRevisionEntry.value;
  return Boolean(entry && entry.source !== "current");
});

const canRevertHeaderContent = computed(() => {
  const entry = selectedHeaderContentRevisionEntry.value;
  return Boolean(entry && entry.source !== "current");
});

// -------------------------
// Data Mapping
// -------------------------

/**
 * Reset header state to defaults (no header)
 */
function resetHeader(preservedHeaderId = null) {
  header.hasHeader = false;
  header.headerId = preservedHeaderId;
  header.headerType = null;
  header.enabledFields = [];
  // Note: title is stored on the page (state.pageTitle), not the header
  header.subtitle = { de: "", en: "" };
  header.backgroundImage = "";
  header.backgroundZoom = 1;
  header.backgroundFocalX = 50;
  header.backgroundFocalY = 50;
  header.backgroundRotation = 0;
  header.overlayImage = "";
  header.overlayZoom = 1;
  header.overlayFocalX = 50;
  header.overlayFocalY = 50;
  header.overlayRotation = 0;
  header.ctaButtons = [];
  header.shared = false;
  header.adminNotes = "";
  header.adminTodos = [];
  state.headerId = preservedHeaderId;
  state.headerEnabledFields = [];
  delete state.sectionDesignOverrides['__header__'];
  headerNotesDraft.value = "";
  headerTodoDraft.value = [];
  headerNewTodo.value = "";
  headerNewTodoTag.value = DEFAULT_TODO_TAG_ID;
  headerNewTodoPriority.value = DEFAULT_TODO_PRIORITY;
  headerHistoryCurrent.value = null;
  headerHistoryStack.value = [];
  headerFutureStack.value = [];
  headerHistoryError.value = "";
  selectedHeaderDesignRevisionKey.value = "current-design";
  selectedHeaderContentRevisionKey.value = "current-content";
  headerAdminActiveTab.value = "design";
  headerMediaPickerOpen.value = false;
  headerCtaDraft.value = [];
  headerCtaExpandedItem.value = -1;
  headerSharingError.value = "";
}

/**
 * Map backend header data to local header state
 */
function mapBackendHeader(backendHeader) {
  if (!backendHeader) return;
  
  const enabled = backendHeader.enabled_fields || ["title", "subtitle", "cta_buttons", "overlay_image", "background_image"];
  
  header.headerId = backendHeader.id;
  state.headerId = backendHeader.id;
  header.headerType = backendHeader.header_type || "hero";
  header.enabledFields = enabled;
  state.headerEnabledFields = enabled;
  header.hasHeader = true;
  header.shared = backendHeader.shared === true;
  headerSharingError.value = "";
  // Note: Title is stored on the page (state.pageTitle), not the header
  // The header only controls whether the title field is enabled via enabled_fields
  header.subtitle = normalizeBilingualText(backendHeader.hero_subtitle);
  header.backgroundImage = backendHeader.background_media_url || "";
  header.backgroundZoom = normalizeHeaderZoom(backendHeader.background_zoom);
  header.backgroundFocalX = normalizeHeaderFocal(backendHeader.background_focal_x);
  header.backgroundFocalY = normalizeHeaderFocal(backendHeader.background_focal_y);
  header.backgroundRotation = normalizeHeaderRotation(backendHeader.background_rotation);
  header.overlayImage = backendHeader.overlay_image_url || "";
  header.overlayZoom = normalizeHeaderZoom(backendHeader.overlay_zoom);
  header.overlayFocalX = normalizeHeaderFocal(backendHeader.overlay_focal_x);
  header.overlayFocalY = normalizeHeaderFocal(backendHeader.overlay_focal_y);
  header.overlayRotation = normalizeHeaderRotation(backendHeader.overlay_rotation);
  
  if (backendHeader.cta_buttons && Array.isArray(backendHeader.cta_buttons)) {
    header.ctaButtons = backendHeader.cta_buttons.map(btn => ({
      text: normalizeBilingualText(btn.text),
      url: btn.url || "",
      buttonType: btn.button_type || null
    }));
  } else {
    header.ctaButtons = [];
  }
  syncHeaderCtaDraftFromHeader();

  header.adminNotes = String(backendHeader.admin_notes || "");
  header.adminTodos = Array.isArray(backendHeader.admin_todos) ? backendHeader.admin_todos : [];
  headerNotesDraft.value = header.adminNotes;
  headerTodoDraft.value = normalizeHeaderTodos(header.adminTodos);

  if (backendHeader.design_overrides) {
    const normalizedOverrides = normalizeSectionDesignOverridesForFrontend(
      cloneSerializable(backendHeader.design_overrides)
    );
    if (normalizedOverrides) {
      state.sectionDesignOverrides['__header__'] = normalizedOverrides;
    } else {
      delete state.sectionDesignOverrides['__header__'];
    }
  } else {
    delete state.sectionDesignOverrides['__header__'];
  }

  if (headerAdminActiveTab.value === "history") {
    loadHeaderHistory();
  }
}

/**
 * Map backend page sections to store state
 * Uses section ID as the key to support multiple sections of the same type
 */
function mapBackendSections(backendSections, backendStructure = null) {
  if (!backendSections || !Array.isArray(backendSections)) return;
  
  const order = [];
  const hidden = {};
  const widths = {};
  const sectionIds = {};
  const sectionMeta = {};
  const sectionsData = {};
  const designOverrides = {};
  let deviceVisibility = null;
  
  const sortedSections = [...backendSections].sort((a, b) => (a.order || 0) - (b.order || 0));

  // Track emitted frontend keys so repeated section types never produce duplicates.
  const usedFrontendKeys = new Set();
  const previousKeyBySectionId = new Map(
    Object.entries(state.sectionIds || {})
      .map(([key, id]) => [String(id || "").trim(), key])
      .filter(([id, key]) => id && key)
  );

  const buildUniqueFrontendKey = (baseKey, sectionId) => {
    const normalizedBase = String(baseKey || "").trim();
    if (!normalizedBase) return null;

    const normalizedId = String(sectionId || "").trim();
    const previousKey = normalizedId ? previousKeyBySectionId.get(normalizedId) : null;
    if (previousKey && !usedFrontendKeys.has(previousKey)) {
      usedFrontendKeys.add(previousKey);
      return previousKey;
    }

    if (!usedFrontendKeys.has(normalizedBase)) {
      usedFrontendKeys.add(normalizedBase);
      return normalizedBase;
    }

    if (normalizedId) {
      const idCandidate = `${normalizedBase}_${normalizedId}`;
      if (!usedFrontendKeys.has(idCandidate)) {
        usedFrontendKeys.add(idCandidate);
        return idCandidate;
      }
    }

    let suffix = 2;
    let candidate = `${normalizedBase}_${suffix}`;
    while (usedFrontendKeys.has(candidate)) {
      suffix += 1;
      candidate = `${normalizedBase}_${suffix}`;
    }
    usedFrontendKeys.add(candidate);
    return candidate;
  };
  
  for (const section of sortedSections) {
    const typeData = section.type_data || {};
    const normalizedSectionType = normalizeSectionTypeKey(section.section_type);
    const baseKey = SECTION_TYPE_TO_KEY[normalizedSectionType] || normalizedSectionType;
    
    if (!baseKey) continue;

    // Keep bare keys for the first section key (e.g. "links"),
    // and append IDs for additional instances to stay unique.
    const frontendKey = buildUniqueFrontendKey(baseKey, section._id);
    if (!frontendKey) continue;
    
    sectionIds[frontendKey] = section._id;
    const templateName = String(section.section_template_name || "default").trim() || "default";
    const templateRef = `${normalizedSectionType}/${templateName}`;

    sectionMeta[frontendKey] = {
      titlePlaceholder: section.title_placeholder || frontendKey,
      title_placeholder: section.title_placeholder || frontendKey,
      sectionType: normalizedSectionType,
      section_type: normalizedSectionType,
      sectionTemplateName: templateName,
      section_template_name: templateName,
      sectionTemplateRef: templateRef,
      section_template_ref: templateRef,
      shared: section.shared === true,
    };
    
    order.push(frontendKey);
    hidden[frontendKey] = section.visible === false;
    
    if (section.width_n !== undefined || section.width_d !== undefined) {
      widths[frontendKey] = {
        n: Number(section.width_n) || 1,
        d: Number(section.width_d) || 1
      };
    }
    
    if (section.device_visibility) {
      if (!deviceVisibility) deviceVisibility = {};
      deviceVisibility[frontendKey] = section.device_visibility;
    }
    
    if (section.design_overrides) {
      const normalizedOverrides = normalizeSectionDesignOverridesForFrontend(section.design_overrides);
      if (normalizedOverrides) {
        designOverrides[frontendKey] = normalizedOverrides;
      }
    }
    
    // Map section data and store by unique key
    const sectionData = mapSectionData(frontendKey, baseKey, section, typeData, normalizedSectionType);
    sectionsData[frontendKey] = sectionData;
  }
  
  const structureMaps = buildSectionContainerMaps(order, backendStructure, sectionIds);
  const resolvedOrder = structureMaps.flattenedKeys?.length ? structureMaps.flattenedKeys : order;
  const resolvedStructure = buildSectionStructureFromEntries(
    structureMaps.nodes,
    sectionIds,
    resolvedOrder,
  );

  if (resolvedOrder.length > 0) {
    state.landingLayout.order = resolvedOrder;
  } else {
    state.landingLayout.order = [];
  }
  state.landingLayout.structure = resolvedStructure.length
    ? resolvedStructure
    : buildSectionStructureFromOrder(resolvedOrder, sectionIds);
  state.landingLayout.hidden = hidden;
  state.landingLayout.widths = widths;
  if (deviceVisibility) {
    state.landingLayout.deviceVisibility = deviceVisibility;
  }
  state.sectionIds = sectionIds;
  state.sectionMeta = sectionMeta;
  state.sectionsData = sectionsData;
  const headerOvBackup = state.sectionDesignOverrides['__header__'];
  state.sectionDesignOverrides = designOverrides;
  if (headerOvBackup) state.sectionDesignOverrides['__header__'] = headerOvBackup;
}

function isPreviewObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

let templatePreviewDesignSnapshot = null;

function templatePreviewDesignJson(value = state.design) {
  try {
    return JSON.stringify(value || {});
  } catch {
    return "";
  }
}

function snapshotTemplatePreviewDesignState() {
  if (templatePreviewDesignSnapshot) return;
  templatePreviewDesignSnapshot = {
    design: cloneSerializable(state.design || {}),
    designId: state.designId,
    designDirty: Boolean(state.designDirty),
    designSnapshot: state._designSnapshot,
    designFontStylesheetUrls: cloneSerializable(state.designFontStylesheetUrls || []),
    adminDesignConfig: cloneSerializable(state.adminDesignConfig),
    templatePageDesignMeta: cloneSerializable(state.templatePageDesignMeta),
    designRevisionStatus: cloneSerializable(state.designRevisionStatus),
    previewDesignSnapshot: "",
    designEditedDuringPreview: false,
  };
}

function markTemplatePreviewDesignEditedIfNeeded() {
  const snapshot = templatePreviewDesignSnapshot;
  if (!snapshot?.previewDesignSnapshot) return false;
  const currentDesignSnapshot = templatePreviewDesignJson();
  if (currentDesignSnapshot && currentDesignSnapshot !== snapshot.previewDesignSnapshot) {
    snapshot.designEditedDuringPreview = true;
  }
  return Boolean(snapshot.designEditedDuringPreview);
}

function restoreTemplatePreviewDesignState() {
  const snapshot = templatePreviewDesignSnapshot;
  if (!snapshot) return;
  if (markTemplatePreviewDesignEditedIfNeeded()) {
    templatePreviewDesignSnapshot = null;
    applyDesignCSS();
    return;
  }
  state.design = cloneSerializable(snapshot.design || {});
  state.designId = snapshot.designId;
  state.designDirty = Boolean(snapshot.designDirty);
  state._designSnapshot = snapshot.designSnapshot;
  state.designFontStylesheetUrls = cloneSerializable(snapshot.designFontStylesheetUrls || []);
  state.adminDesignConfig = cloneSerializable(snapshot.adminDesignConfig);
  state.templatePageDesignMeta = cloneSerializable(snapshot.templatePageDesignMeta);
  state.designRevisionStatus = cloneSerializable(snapshot.designRevisionStatus);
  templatePreviewDesignSnapshot = null;
  applyDesignCSS();
}

function resolveTemplatePreviewDesignSettings(previewPayload) {
  if (!isPreviewObject(previewPayload)) return null;
  if (isPreviewObject(previewPayload.effective_design_settings)) {
    return previewPayload.effective_design_settings;
  }
  const pagePayload = isPreviewObject(previewPayload.page) ? previewPayload.page : null;
  if (isPreviewObject(pagePayload?.effective_design_settings)) {
    return pagePayload.effective_design_settings;
  }
  return null;
}

function applyTemplatePreviewDesignState(previewPayload) {
  const effectiveDesignSettings = resolveTemplatePreviewDesignSettings(previewPayload);
  if (!effectiveDesignSettings) {
    restoreTemplatePreviewDesignState();
    return;
  }
  snapshotTemplatePreviewDesignState();
  if (markTemplatePreviewDesignEditedIfNeeded()) {
    return;
  }
  applyPublicDesignSettings(effectiveDesignSettings);
  if (templatePreviewDesignSnapshot) {
    templatePreviewDesignSnapshot.previewDesignSnapshot = templatePreviewDesignJson();
  }
}

function normalizePreviewHeaderForCanvas(previewHeader) {
  if (!isPreviewObject(previewHeader)) return null;
  return {
    ...previewHeader,
    id: previewHeader.id || header.headerId || state.headerId || "__template_preview_header__",
  };
}

function normalizeTemplateBuilderSectionWidthPart(value, fallback = 1) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return fallback;
  return Math.max(1, Math.min(5, Math.trunc(numeric)));
}

function resolveTemplateBuilderSectionWidthFallback(sectionId) {
  const normalizedSectionId = String(sectionId || "").trim();
  if (!normalizedSectionId) return null;

  const cachedPayload = templateBuilderCanvasPayload.value;
  const cachedSection = Array.isArray(cachedPayload?.sections)
    ? cachedPayload.sections.find((section) =>
        String(section?._id || section?.id || "").trim() === normalizedSectionId
      )
    : null;
  if (cachedSection && (
    cachedSection.width_n !== undefined
    || cachedSection.width_d !== undefined
  )) {
    const d = normalizeTemplateBuilderSectionWidthPart(cachedSection.width_d, 1);
    return {
      n: Math.min(normalizeTemplateBuilderSectionWidthPart(cachedSection.width_n, 1), d),
      d,
    };
  }

  const sectionKey = Object.entries(state.sectionIds || {})
    .find(([, rawSectionId]) => String(rawSectionId || "").trim() === normalizedSectionId)?.[0];
  const currentWidth = sectionKey ? state.landingLayout?.widths?.[sectionKey] : null;
  if (currentWidth && typeof currentWidth === "object") {
    const d = normalizeTemplateBuilderSectionWidthPart(currentWidth.d, 1);
    return {
      n: Math.min(normalizeTemplateBuilderSectionWidthPart(currentWidth.n, 1), d),
      d,
    };
  }

  return null;
}

function normalizePreviewSectionsForCanvas(previewSections) {
  if (!Array.isArray(previewSections)) return [];
  return previewSections
    .map((section, index) => {
      if (!isPreviewObject(section)) return null;
      const sectionId = String(section._id || section.id || `__template_preview_section_${index + 1}__`).trim();
      if (!sectionId) return null;
      const fallbackWidth = resolveTemplateBuilderSectionWidthFallback(sectionId) || { n: 1, d: 1 };
      const widthD = normalizeTemplateBuilderSectionWidthPart(section.width_d, fallbackWidth.d);
      const widthN = Math.min(
        normalizeTemplateBuilderSectionWidthPart(section.width_n, fallbackWidth.n),
        widthD,
      );
      return {
        ...section,
        _id: sectionId,
        section_type: String(section.section_type || "text"),
        type_data: isPreviewObject(section.type_data) ? section.type_data : {},
        order: Number.isFinite(Number(section.order)) ? Number(section.order) : index,
        visible: section.visible !== false,
        width_n: widthN,
        width_d: widthD,
      };
    })
    .filter(Boolean);
}

function applyTemplatePreviewPayloadToCanvas(previewPayload) {
  if (!isPreviewObject(previewPayload)) return;
  applyTemplatePreviewDesignState(previewPayload);
  const pagePayload = isPreviewObject(previewPayload.page) ? previewPayload.page : {};
  const previewTitle = normalizeBilingualText(pagePayload.title);
  const previewHeaderSource = isPreviewObject(previewPayload.header) ? previewPayload.header : {};
  const mappedHeaderTitle = normalizeBilingualText(
    previewHeaderSource.hero_title
    || previewHeaderSource.heroTitle
    || previewHeaderSource.title
  );
  if (previewTitle.de || previewTitle.en) {
    state.pageTitle = previewTitle;
  }
  if (previewPayload.__mapped_header_title === true && (mappedHeaderTitle.de || mappedHeaderTitle.en)) {
    state.pageTitle = mappedHeaderTitle;
  }

  state.landingLayout.sectionBgPinnedStartKey = String(pagePayload.section_bg_pinned_start_key || "");
  state.landingLayout.sectionBgPinnedEndKey = String(pagePayload.section_bg_pinned_end_key || "");

  const previewHeader = normalizePreviewHeaderForCanvas(previewPayload.header);
  const hasPreviewHeader = previewPayload.has_header === true || Boolean(previewHeader);
  headerEnabled.value = hasPreviewHeader;
  if (hasPreviewHeader && previewHeader) {
    mapBackendHeader(previewHeader);
  } else if (!hasPreviewHeader) {
    resetHeader(header.headerId || state.headerId || null);
  }

  const previewSections = normalizePreviewSectionsForCanvas(previewPayload.sections);
  mapBackendSections(previewSections, pagePayload.section_structure);
}

function isTemplateBuilderFullPagePayload(pageData) {
  if (!isTemplateBuilder.value || !isPreviewObject(pageData)) return false;
  if (!Array.isArray(pageData.sections)) return false;
  return pageData.sections.every((section) => (
    isPreviewObject(section) && String(section.section_type || "").trim()
  ));
}

function rememberTemplateBuilderCanvasPayload(pageData) {
  if (!isTemplateBuilderFullPagePayload(pageData)) return;
  templateBuilderCanvasPayload.value = cloneSerializable(pageData);
}

async function applyTemplateBuilderPayload(pageData, options = {}) {
  if (!isTemplateBuilderFullPagePayload(pageData)) return false;
  const emitUpdate = options?.emitUpdate !== false;
  const remember = options?.remember !== false;

  if (isPreviewObject(pageData.title)) {
    state.pageTitle = pageData.title;
  }

  const linkedHeaderId = pageData.header?.id || pageData.header_id || null;
  headerEnabled.value = pageData.has_header === true;
  if (pageData.has_header && pageData.header) {
    mapBackendHeader(pageData.header);
  } else {
    resetHeader(linkedHeaderId);
  }

  mapBackendSections(pageData.sections, pageData.section_structure);
  state.landingLayout.sectionBgPinnedStartKey = pageData.section_bg_pinned_start_key || "";
  state.landingLayout.sectionBgPinnedEndKey = pageData.section_bg_pinned_end_key || "";
  isPageNotFound.value = false;
  error.value = null;
  state.initialized = true;
  if (remember) {
    rememberTemplateBuilderCanvasPayload(pageData);
  }
  if (emitUpdate) {
    emit("template-updated", pageData);
  }
  await nextTick();
  return true;
}

async function restoreTemplateBuilderCanvasAfterPreview() {
  if (!isTemplateBuilder.value || templateBuilderKind.value !== "page") return;
  const cachedPayload = cloneSerializable(templateBuilderCanvasPayload.value);
  if (cachedPayload && await applyTemplateBuilderPayload(cachedPayload, { emitUpdate: false, remember: false })) {
    return;
  }
  try {
    const pageData = await api.getPageFull(pageSlug.value, true);
    await applyTemplateBuilderPayload(pageData);
  } catch (err) {
    console.error("Failed to restore template builder canvas:", err);
  }
}

async function applyTemplateBuilderPayloadOrReload(pageData) {
  if (await applyTemplateBuilderPayload(pageData)) return true;
  await loadPage();
  return false;
}

async function handleSectionPanelTemplateUpdated(pageData) {
  if (!isTemplateBuilder.value) return;
  await applyTemplateBuilderPayloadOrReload(pageData);
}

function buildTemplateBuilderLayoutSignature() {
  if (!isTemplateBuilder.value || templateBuilderKind.value !== "page") return "";
  if (isPreviewObject(props.templatePreviewPayload)) return "";
  try {
    return JSON.stringify({
      sectionIds: state.sectionIds || {},
      order: state.landingLayout?.order || [],
      structure: state.landingLayout?.structure || [],
      hidden: state.landingLayout?.hidden || {},
      widths: state.landingLayout?.widths || {},
      deviceVisibility: state.landingLayout?.deviceVisibility || {},
      sectionBgPinnedStartKey: state.landingLayout?.sectionBgPinnedStartKey || "",
      sectionBgPinnedEndKey: state.landingLayout?.sectionBgPinnedEndKey || "",
    });
  } catch {
    return "";
  }
}

function buildTemplateBuilderSectionDataSignature() {
  if (!isTemplateBuilder.value || templateBuilderKind.value !== "page") return "";
  if (isPreviewObject(props.templatePreviewPayload)) return "";
  try {
    return JSON.stringify({
      sectionIds: state.sectionIds || {},
      sectionsData: state.sectionsData || {},
      designOverrides: state.sectionDesignOverrides || {},
    });
  } catch {
    return "";
  }
}

function syncTemplateBuilderCanvasSectionsFromState() {
  if (!isTemplateBuilder.value || templateBuilderKind.value !== "page") return;
  if (isPreviewObject(props.templatePreviewPayload)) return;
  if (typeof transformSectionToBackendFormat !== "function") return;

  const cachedPayload = cloneSerializable(templateBuilderCanvasPayload.value);
  if (!isTemplateBuilderFullPagePayload(cachedPayload)) return;

  const sectionIds = state.sectionIds || {};
  const sectionsData = state.sectionsData || {};
  const sectionById = new Map(
    cachedPayload.sections
      .map((section) => [String(section?._id || section?.id || "").trim(), section])
      .filter(([id]) => id)
  );
  let changed = false;

  for (const [key, rawSectionId] of Object.entries(sectionIds)) {
    const section = sectionById.get(String(rawSectionId || "").trim());
    const sectionData = sectionsData[key];
    if (!section || !sectionData || typeof sectionData !== "object") continue;

    const before = JSON.stringify(section);
    const backendData = transformSectionToBackendFormat(key, sectionData);

    if (Object.prototype.hasOwnProperty.call(backendData, "title")) {
      section.title = cloneSerializable(backendData.title);
    }
    if (Object.prototype.hasOwnProperty.call(backendData, "type_data")) {
      section.type_data = cloneSerializable(backendData.type_data);
    }
    if (Object.prototype.hasOwnProperty.call(backendData, "section_integration_mapping")) {
      section.section_integration_mapping = cloneSerializable(backendData.section_integration_mapping);
    }
    if (Object.prototype.hasOwnProperty.call(backendData, "section_output_mapping")) {
      section.section_output_mapping = cloneSerializable(backendData.section_output_mapping);
    }

    const normalizedOverrides = normalizeSectionDesignOverridesForBackend(state.sectionDesignOverrides?.[key]);
    section.design_overrides = normalizedOverrides ? cloneSerializable(normalizedOverrides) : null;

    if (JSON.stringify(section) !== before) {
      changed = true;
    }
  }

  if (!changed) return;
  templateBuilderCanvasPayload.value = cachedPayload;
  emit("template-updated", cachedPayload);
}

function syncTemplateBuilderCanvasLayoutFromState() {
  if (!isTemplateBuilder.value || templateBuilderKind.value !== "page") return;
  if (isPreviewObject(props.templatePreviewPayload)) return;
  const cachedPayload = cloneSerializable(templateBuilderCanvasPayload.value);
  if (!isTemplateBuilderFullPagePayload(cachedPayload)) return;

  const layout = state.landingLayout || {};
  const sectionIds = state.sectionIds || {};
  const order = Array.isArray(layout.order) ? layout.order : [];
  const hidden = layout.hidden || {};
  const widths = layout.widths || {};
  const deviceVisibility = layout.deviceVisibility || {};
  const sectionById = new Map(
    cachedPayload.sections
      .map((section) => [String(section?._id || section?.id || "").trim(), section])
      .filter(([id]) => id)
  );
  let changed = false;

  for (const [key, rawSectionId] of Object.entries(sectionIds)) {
    const section = sectionById.get(String(rawSectionId || "").trim());
    if (!section) continue;
    const before = JSON.stringify(section);

    const orderIndex = order.indexOf(key);
    if (orderIndex >= 0) {
      section.order = orderIndex;
    }

    const visible = hidden[key] !== true;
    section.visible = visible;

    const width = widths[key];
    if (width && typeof width === "object") {
      const d = normalizeTemplateBuilderSectionWidthPart(width.d, 1);
      section.width_d = d;
      section.width_n = Math.min(normalizeTemplateBuilderSectionWidthPart(width.n, 1), d);
    }

    if (deviceVisibility[key] && typeof deviceVisibility[key] === "object") {
      section.device_visibility = cloneSerializable(deviceVisibility[key]);
    }

    if (JSON.stringify(section) !== before) {
      changed = true;
    }
  }

  const nextStructure = Array.isArray(layout.structure) ? cloneSerializable(layout.structure) : [];
  if (JSON.stringify(cachedPayload.section_structure || []) !== JSON.stringify(nextStructure)) {
    cachedPayload.section_structure = nextStructure;
    changed = true;
  }

  const nextPinnedStartKey = String(layout.sectionBgPinnedStartKey || "");
  if (String(cachedPayload.section_bg_pinned_start_key || "") !== nextPinnedStartKey) {
    cachedPayload.section_bg_pinned_start_key = nextPinnedStartKey;
    changed = true;
  }

  const nextPinnedEndKey = String(layout.sectionBgPinnedEndKey || "");
  if (String(cachedPayload.section_bg_pinned_end_key || "") !== nextPinnedEndKey) {
    cachedPayload.section_bg_pinned_end_key = nextPinnedEndKey;
    changed = true;
  }

  if (!changed) return;
  templateBuilderCanvasPayload.value = cachedPayload;
  emit("template-updated", cachedPayload);
}

function normalizeSectionGenericForFrontend(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(
    Object.entries(value).map(([rawKey, rawValue]) => [
      toCamelCase(String(rawKey || "")),
      rawValue,
    ])
  );
}

function normalizeSectionCtaButtonsForFrontend(value) {
  if (!Array.isArray(value)) return [];
  return value.map((entry) => {
    const item = entry && typeof entry === "object" ? entry : {};
    const textSource = item.text && typeof item.text === "object" ? item.text : {};
    return {
      text: {
        de: String(textSource.de ?? ""),
        en: String(textSource.en ?? ""),
      },
      url: String(item.url || ""),
      buttonType: item.button_type == null ? null : String(item.button_type),
    };
  });
}

function normalizeProgramTileOverridesForFrontend(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const normalized = {};
  for (const [tileIdRaw, overrideRaw] of Object.entries(value)) {
    const tileId = String(tileIdRaw || "").trim();
    if (!tileId || !overrideRaw || typeof overrideRaw !== "object" || Array.isArray(overrideRaw)) continue;
    normalized[tileId] = Object.fromEntries(
      Object.entries(overrideRaw).map(([rawKey, rawValue]) => [
        toCamelCase(String(rawKey || "")),
        rawValue,
      ])
    );
  }
  return normalized;
}

function toSnakeCaseKey(rawKey) {
  return String(rawKey || "").replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

function toCamelCasePreserveUnderscorePrefixKey(rawKey) {
  const value = String(rawKey || "");
  if (!value.startsWith("_")) return toCamelCase(value);
  const match = value.match(/^_+/);
  const prefix = match ? match[0] : "_";
  const rest = value.slice(prefix.length);
  if (!rest) return value;
  return `${prefix}${toCamelCase(rest)}`;
}

function convertKeysToCamelDeep(value) {
  if (Array.isArray(value)) return value.map(convertKeysToCamelDeep);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value).map(([rawKey, rawValue]) => [
      toCamelCasePreserveUnderscorePrefixKey(rawKey),
      convertKeysToCamelDeep(rawValue),
    ])
  );
}

function convertKeysToSnakeDeep(value) {
  if (Array.isArray(value)) return value.map(convertKeysToSnakeDeep);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value).map(([rawKey, rawValue]) => [
      toSnakeCaseKey(String(rawKey || "")),
      convertKeysToSnakeDeep(rawValue),
    ])
  );
}

function normalizeSectionDesignOverridesForFrontend(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return convertKeysToCamelDeep(value);
}

function normalizeSectionDesignOverridesForBackend(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return convertKeysToSnakeDeep(value);
}

/**
 * Map individual section data to store state
 * Returns the section data object for storage by unique key
 * Uses SECTION_TYPE_CONFIG for automatic snake_case -> camelCase conversion
 */
function mapSectionData(frontendKey, baseKey, section, typeData, normalizedSectionType = null) {
  const sectionType = normalizeSectionTypeKey(normalizedSectionType || section.section_type);
  const config = SECTION_TYPE_CONFIG[sectionType] || {};
  
  // Start with base fields
  const sectionData = {
    title: section.title || { de: "", en: "" },
    body: typeData.body || { de: "", en: "" },
    sectionType: sectionType,
    sectionIntegrationMapping: section.section_integration_mapping || {},
  };
  if (Object.prototype.hasOwnProperty.call(section, "section_output_mapping")) {
    sectionData.sectionOutputMapping = section.section_output_mapping || { mode: "default", exposed_target_paths: [] };
  }
  
  // Handle passthrough sections (like markdown)
  if (config.passthrough) {
    sectionData.type_data = { ...typeData };
    delete sectionData.type_data.icon;
    delete sectionData.type_data.blocks;
    if (typeData.cta_buttons !== undefined) {
      sectionData.ctaButtons = normalizeSectionCtaButtonsForFrontend(typeData.cta_buttons);
    }
    if (typeData.section_generic !== undefined) {
      sectionData.sectionGeneric = normalizeSectionGenericForFrontend(typeData.section_generic);
    }
  } else {
    const arrayConfigs = config.arrays || {};
    const renames = config.renames || {};
    const defaults = config.defaults || {};
    
    // Build reverse renames map: backendKey -> frontendKey
    const reverseRenames = {};
    for (const [fKey, bKey] of Object.entries(renames)) {
      reverseRenames[bKey] = fKey;
    }
    
    // Build set of backend keys handled by arrays
    const arrayBackendKeys = new Set(Object.values(arrayConfigs).map(c => c.backendKey));
    
    // Process each field in type_data
    for (const [backendKey, value] of Object.entries(typeData)) {
      if (backendKey === 'body') continue; // Already handled
      if (sectionType === 'blog' && (backendKey === 'items' || backendKey === 'tags')) continue;
      if (
        backendKey === 'title'
        || backendKey === 'icon'
        || backendKey === 'blocks'
        || backendKey === 'stages'
        || backendKey === 'program_stages_integration_mapping'
        || backendKey === 'programStagesIntegrationMapping'
        || backendKey === 'program_stages_integration_mapping_cache_state'
        || backendKey === 'programStagesIntegrationMappingCacheState'
        || backendKey === 'program_gigs_integration_mapping'
        || backendKey === 'programGigsIntegrationMapping'
        || backendKey === 'program_gigs_integration_mapping_cache_state'
        || backendKey === 'programGigsIntegrationMappingCacheState'
      ) continue;
      if (backendKey === "section_generic") {
        sectionData.sectionGeneric = normalizeSectionGenericForFrontend(value);
        continue;
      }
      if (backendKey === "cta_buttons") {
        sectionData.ctaButtons = normalizeSectionCtaButtonsForFrontend(value);
        continue;
      }
      if (backendKey === "program_tile_overrides") {
        sectionData.programTileOverrides = normalizeProgramTileOverridesForFrontend(value);
        continue;
      }
      
      // Check if this is an array field with custom transformation
      const arrayEntry = Object.entries(arrayConfigs).find(([, cfg]) => cfg.backendKey === backendKey);
      if (arrayEntry && Array.isArray(value)) {
        const [frontendKey, arrConfig] = arrayEntry;
        sectionData[frontendKey] = value.map(arrConfig.toFrontend);
        continue;
      }
      
      // Check for reverse rename
      if (reverseRenames[backendKey]) {
        sectionData[reverseRenames[backendKey]] = value;
        continue;
      }
      
      // Skip keys handled by array configs
      if (arrayBackendKeys.has(backendKey)) continue;
      
      // Default: auto-convert key to camelCase
      const camelKey = toCamelCase(backendKey);
      sectionData[camelKey] = value;
    }
    
    // Apply defaults for missing fields
    for (const [key, defaultVal] of Object.entries(defaults)) {
      if (sectionData[key] === undefined || sectionData[key] === null) {
        sectionData[key] = defaultVal;
      }
    }
    
    // Run any side effects (like updating global state)
    if (config.onLoad) {
      config.onLoad(sectionData, typeData);
    }
  }
  
  // Special handling for blog limit (comes from section, not typeData)
  if (sectionType === "blog") {
    sectionData.limit = section.limit !== undefined ? section.limit : (typeData.limit ?? null);
  }
  
  if (
    section.section_type === "faq"
    && sectionData.faqItems
    && !state.faqSharedLoaded
    && (!Array.isArray(state.faqItems) || state.faqItems.length === 0)
  ) {
    state.faqItems = sectionData.faqItems;
  }

  return sectionData;
}

// -------------------------
// API Integration
// -------------------------

/**
 * Load page data from the backend
 */
function shouldSkipRedirect() {
  return route.query.noredirect === '1' || route.query.noredirect === 'true';
}

async function loadPage() {
  if (loading.value) {
    queuedPageReload.value = true;
    return;
  }
  
  setPageSlug(pageSlug.value);
  setCurrentPageStatusMeta(null);
  loading.value = true;
  error.value = null;
  isPageNotFound.value = false;
  notFoundStatusCode.value = 404;
  isPageVisible.value = true;
  isPageUnderConstruction.value = false;
  isBlogGeneratedPage.value = false;
  currentPageMeta.value = null;
  if (!syncTemplateBusy.value) {
    syncTemplateStatus.value = { type: "", message: "" };
  }
  isCreatingRedirect.value = false;
  createRedirectError.value = "";
  existingRouteRedirect.value = null;
  existingRouteRedirectLoading.value = false;
  restorePageDesignOverrides();
  state.publicCssSnippets = [];
  applyMediaFallbacks(null);
  logDebug("loadPage.start", { slug: pageSlug.value });
  
  try {
    const fetchComposedPage = async () => {
      if (isTemplateBuilder.value) {
        const page = await api.getPageFull(pageSlug.value, true);
        return { page, bundle: null, usePrivatePageApi: true };
      }

      const usePrivatePageApi = state.isAdmin || (Boolean(getUser()) && isAuthAdmin());
      if (usePrivatePageApi) {
        const page = await api.getPageFull(pageSlug.value, true);
        return { page, bundle: null, usePrivatePageApi };
      }

      const bundle = await api.getPublicPageBundle(pageSlug.value);
      state.publicCssSnippets = Array.isArray(bundle?.css_snippets) ? bundle.css_snippets : [];
      if (Array.isArray(bundle?.menu_items)) {
        window.__SSC_PUBLIC_MENU_ITEMS = bundle.menu_items;
        window.dispatchEvent(new Event("fstvlpress-public-menu-updated"));
      }
      if (Array.isArray(bundle?.footer_items)) {
        window.__SSC_PUBLIC_FOOTER_ITEMS = bundle.footer_items;
      }
      window.__SSC_PUBLIC_TOPBAR_LOGO_URL = bundle?.topbar_logo_url || null;
      window.__SSC_PUBLIC_TOPBAR_LOGO_RESPONSIVE_VARIANTS = Array.isArray(bundle?.topbar_logo_responsive_variants)
        ? bundle.topbar_logo_responsive_variants
        : [];
      window.dispatchEvent(new Event("fstvlpress-public-topbar-updated"));
      window.__SSC_PUBLIC_FOOTER_LOGO_URL = bundle?.footer_logo_url || null;
      window.__SSC_PUBLIC_FOOTER_LOGO_RESPONSIVE_VARIANTS = Array.isArray(bundle?.footer_logo_responsive_variants)
        ? bundle.footer_logo_responsive_variants
        : [];
      window.dispatchEvent(new Event("fstvlpress-public-footer-updated"));
      return { page: bundle?.page, bundle, usePrivatePageApi };
    };

    let pageData;
    let pageBundle = null;
    let usePrivatePageApi = false;
    try {
      const response = await fetchComposedPage();
      pageData = response?.page;
      pageBundle = response?.bundle || null;
      usePrivatePageApi = response?.usePrivatePageApi === true;
    } catch (err) {
      // Check if page doesn't exist (404) or was intentionally removed (410)
      const errMsg = (err.message || '').toLowerCase();
      const isNotFound = errMsg.includes("not found") || 
                         errMsg.includes("404") ||
                         errMsg.includes("page not found");
      const isGone = errMsg.includes("410") || errMsg.includes("gone");
      
      logDebug("loadPage.fetchError", { slug: pageSlug.value, error: err.message, isNotFound, isGone });
      
      if (isNotFound || isGone) {
        // If auth/store state is still settling, retry once via private endpoint
        // before treating the page as missing. This prevents false "create page"
        // states for existing draft pages.
        try {
          await initPageAuth();
          const canRetryPrivate = state.isAdmin || (Boolean(getUser()) && isAuthAdmin());
          if (canRetryPrivate) {
            pageData = await api.getPageFull(pageSlug.value, true);
            pageBundle = null;
            usePrivatePageApi = true;
          }
        } catch {
          // Keep original not-found flow below if private retry cannot load page.
        }

        if (pageData) {
          // Private retry succeeded, continue normal mapping flow.
        } else {
          let redirected = false;
          let resolvedNotFoundStatusCode = isGone ? 410 : 404;
          if (!isGone && !shouldSkipRedirect()) {
            // Route-level redirects (generated + custom) for moved paths.
            try {
              const currentPath = pageSlug.value === 'landing' ? '/' : `/${pageSlug.value}`;
              const resolved = await api.resolveSitemapRedirect(currentPath);
              const resolvedStatusCode = Number(resolved?.redirect?.status_code) || 0;
              const target = resolved?.redirect?.target_path;
              if (resolved?.found && resolvedStatusCode === 410) {
                resolvedNotFoundStatusCode = 410;
              } else if (resolved?.found && target) {
                const targetIsExternal = target.startsWith('http://') || target.startsWith('https://');
                if (targetIsExternal || target !== route.path) {
                  redirected = true;
                  loading.value = false;
                  if (targetIsExternal) {
                    window.location.href = target;
                  } else {
                    router.replace(target);
                  }
                  return;
                }
              }
            } catch (redirectResolveErr) {
              logDebug("loadPage.redirectResolveError", {
                slug: pageSlug.value,
                error: redirectResolveErr?.message || String(redirectResolveErr),
              });
            }
          }

          if (!redirected) {
            logDebug("loadPage.notFound", { slug: pageSlug.value });
            isPageNotFound.value = true;
            notFoundStatusCode.value = resolvedNotFoundStatusCode;
            error.value = null;
            isPageUnderConstruction.value = false;
            isBlogGeneratedPage.value = false;
            currentPageMeta.value = null;
            setCurrentPageStatusMeta(null);
            setPageTemplateStyleContext(null);
            if (hasAppliedTemplateEffectiveDesign.value && state.canContent) {
              await loadDesignSettings();
              hasAppliedTemplateEffectiveDesign.value = false;
            }
            restorePageDesignOverrides();
            await Promise.all([
              loadSectionTypes(),
              loadSectionTemplateLibraries(),
              loadStaticPageTemplates(),
              classifyUnknownPageRoute(),
              loadRedirectTargetPages(),
              loadExistingRouteRedirect(),
            ]);
            missingPageAction.value = pageCreationRouteKind.value === "item_child" ? "redirect" : "page";
            createRedirectForm.targetPath = "";
            createRedirectForm.statusCode = 301;
            state.initialized = true;
            loading.value = false;
            return;
          }
        }
      } else {
        throw err;
      }
    }
    if (!pageData) {
      throw new Error("Page not found");
    }
    applyMediaFallbacks(pageData?.media_fallbacks || pageBundle?.media_fallbacks || null);
    lastLoadUsedPrivatePageApi.value = usePrivatePageApi;
    if (!usePrivatePageApi && pageData?.is_visible === true) {
      api.recordPublicPageHit(pageData.slug || pageSlug.value);
    }

    const pageTemplateStyleRef = String(pageData.template_style_ref || "").trim() || null;
    const pageTemplateStyleLinked = pageData.template_style_linked === true || Boolean(pageTemplateStyleRef);
    const pageTemplateStyleLock = pageTemplateStyleLinked && pageData.template_style_lock === true;
    setPageTemplateStyleContext({
      ref: pageTemplateStyleRef,
      linked: pageTemplateStyleLinked,
      locked: pageTemplateStyleLock,
    });

    const effectiveDesignSettings = pageData?.effective_design_settings;
    if (pageTemplateStyleLock && effectiveDesignSettings && typeof effectiveDesignSettings === "object") {
      applyPublicDesignSettings(effectiveDesignSettings);
      hasAppliedTemplateEffectiveDesign.value = true;
    } else {
      const shouldHydrateReadonlyAdminDesign =
        usePrivatePageApi && state.canContent && !state.canDesign;
      if (hasAppliedTemplateEffectiveDesign.value && state.canContent) {
        await loadDesignSettings();
      } else if (shouldHydrateReadonlyAdminDesign) {
        // Content-only admins read pages via private endpoints but still need
        // current global design settings to render the editing canvas correctly.
        await loadDesignSettings();
      } else if (!usePrivatePageApi && pageBundle?.design_settings && !state.canContent) {
        // Public bundle design should only hydrate truly public visitors.
        // For authenticated editors, a later public response can race and
        // overwrite freshly loaded editable global design state.
        applyPublicDesignSettings(pageBundle.design_settings);
      }
      hasAppliedTemplateEffectiveDesign.value = false;
    }
    applyPageDesignOverrides(pageTemplateStyleLinked ? null : pageData.page_design_overrides);
    
    // Page exists - load its data
    isPageNotFound.value = false;
    notFoundStatusCode.value = 404;
    pageCreationRouteKind.value = "static_route";
    createPageForm.templatePath = "";
    isBlogGeneratedPage.value = pageData.generated_from_blog === true;
    currentPageMeta.value = {
      slug: String(pageData.slug || "").trim(),
      generated_from_blog: pageData.generated_from_blog === true,
      template_managed: pageData.template_managed === true,
      template_source_type: String(pageData.template_source_type || "").trim().toLowerCase(),
      template_source_id: String(pageData.template_source_id || "").trim(),
      template_integration_id: String(pageData.template_integration_id || "").trim(),
      template_integration_item_key: String(pageData.template_integration_item_key || "").trim(),
      template_style_ref: pageTemplateStyleRef,
      status: String(pageData.status || "").trim().toLowerCase(),
    };
    setPageSlug(pageSlug.value);
    setCurrentPageStatusMeta({
      status: pageData.status,
      effectiveStatus: pageData.effective_status,
      isVisible: pageData.is_visible,
    });
    
    // Track public visibility state and dedicated under-construction state.
    const effectiveStatus = String(pageData.effective_status || pageData.status || '').trim().toLowerCase();
    isPageUnderConstruction.value = effectiveStatus === 'under_construction';
    isPageVisible.value = pageData.is_visible !== false;
    
    // Handle redirect
    // Skip redirect if ?noredirect=1 is in URL (for admins editing the page)
    if (!isTemplateBuilder.value && pageData.redirect_to && !shouldSkipRedirect()) {
      logDebug("loadPage.redirect", { from: pageSlug.value, to: pageData.redirect_to });
      loading.value = false;
      
      // Check if it's an external URL or internal path
      if (pageData.redirect_to.startsWith('http://') || pageData.redirect_to.startsWith('https://')) {
        window.location.href = pageData.redirect_to;
      } else {
        // Internal redirect - use router
        router.replace(pageData.redirect_to);
      }
      return;
    }
    
    // Store page title
    state.pageTitle = pageData.title || { de: "", en: "" };

    const linkedHeaderId = pageData.header?.id || pageData.header_id || null;

    // Ensure brand-new empty pages default to header-enabled for admin editing UX
    const isCompletelyEmptyPage = (!pageData.header) && (!Array.isArray(pageData.sections) || pageData.sections.length === 0);
    if (
      state.isAdmin &&
      canManageHeaderForCurrentPage.value &&
      pageData.has_header !== true &&
      !linkedHeaderId &&
      isCompletelyEmptyPage
    ) {
      await api.updatePage(pageSlug.value, { has_header: true });
      pageData.has_header = true;
    }
    
    // Map header data
    headerEnabled.value = pageData.has_header === true;
    if (pageData.has_header && pageData.header) {
      mapBackendHeader(pageData.header);
    } else {
      resetHeader(linkedHeaderId);
    }
    
    // Map sections data
    if (pageData.sections && Array.isArray(pageData.sections)) {
      mapBackendSections(pageData.sections, pageData.section_structure);
      const hasFaq = pageData.sections.some((s) => s.section_type === "faq");
      const hasBlog = pageData.sections.some((s) => s.section_type === "blog");
      const hasProgram = pageData.sections.some((s) => {
        if (s?.section_type === "program") return true;
        if (s?.section_type !== "tiles") return false;
        const typeData = s?.type_data && typeof s.type_data === "object" ? s.type_data : {};
        return Boolean(typeData.use_program_gigs ?? true);
      });
      if (hasFaq) {
        if (!usePrivatePageApi && pageBundle?.faq) {
          applyFaqSharedData(pageBundle.faq, { source: "public" });
        } else {
          await fetchFaqSharedData();
        }
      }
      if (hasBlog) {
        if (!usePrivatePageApi && pageBundle?.blog) {
          const publicItems = Array.isArray(pageBundle.blog.items) ? pageBundle.blog.items : [];
          state.blogItems = publicItems.map((it) => ({
            id: it.id,
            imageUrl: it.image_url || "",
            imageZoom: Number.isFinite(Number(it.image_zoom)) ? Math.max(1, Math.min(4, Number(it.image_zoom))) : 1,
            imageFocalX: Number.isFinite(Number(it.image_focal_x)) ? Math.max(0, Math.min(100, Number(it.image_focal_x))) : 50,
            imageFocalY: Number.isFinite(Number(it.image_focal_y)) ? Math.max(0, Math.min(100, Number(it.image_focal_y))) : 50,
            imageRotation: Number.isFinite(Number(it.image_rotation)) ? Math.max(-180, Math.min(180, Number(it.image_rotation))) : 0,
            date: it.date || "",
            tag: it.tag || { de: "", en: "" },
            title: it.title || { de: "", en: "" },
            text: it.text || { de: "", en: "" },
            pageSlug: it.page_slug || "",
          }));
          state.blogTags = Array.isArray(pageBundle.blog.tags) ? pageBundle.blog.tags : [];
        } else {
          await fetchBlogData();
        }
      }
      if (hasProgram) {
        if (!usePrivatePageApi && pageBundle?.program) {
          applyProgramSharedData(pageBundle.program);
        } else {
          await fetchProgramSharedData();
        }
      }
    }
    
    // Load page-specific background pattern pin settings
    state.landingLayout.sectionBgPinnedStartKey = pageData.section_bg_pinned_start_key || '';
    state.landingLayout.sectionBgPinnedEndKey = pageData.section_bg_pinned_end_key || '';
    
    // Load available section types for the add section dialog
    await Promise.all([
      loadSectionTypes(),
      loadSectionTemplateLibraries(),
    ]);

    if (isTemplateBuilder.value) {
      rememberTemplateBuilderCanvasPayload(pageData);
      await applyTemplateSnippetStyles();
      emit('template-updated', pageData);
    }
    
    state.initialized = true;
    logDebug("loadPage.success", { slug: pageSlug.value });
  } catch (err) {
    error.value = err.message;
    isBlogGeneratedPage.value = false;
    currentPageMeta.value = null;
    setCurrentPageStatusMeta(null);
    restorePageDesignOverrides();
    logDebug("loadPage.error", { error: err.message });
    console.error("Failed to load page:", err);
  } finally {
    loading.value = false;
    if (queuedPageReload.value) {
      queuedPageReload.value = false;
      await loadPage();
    }
  }
}

/**
 * Create a new page in the backend
 */
async function createNewPage() {
  const slug = String(pageSlug.value || "").trim();
  if (!slug || slug === "unknown") return;
  if (pageCreationRouteKind.value === "item_child") {
    createPageError.value = "This route is managed by an item-page template. Create the source item instead.";
    return;
  }
  if (createPageSlugError.value) {
    createPageError.value = createPageSlugError.value;
    return;
  }

  createPageError.value = "";
  logDebug("createNewPage.directCreate.start", { slug, in_menu: createPageForm.inMenu });
  try {
    const selectedTemplatePath = String(createPageForm.templatePath || "").trim();
    const confirmMessage = selectedTemplatePath
      ? `Create "/${slug}" from template "${selectedTemplatePath}"?`
      : `Create "/${slug}" as a new empty page?`;
    if (!window.confirm(confirmMessage)) {
      return;
    }

    isCreatingPage.value = true;
    const title = {
      de: String(createPageForm.title.de || "").trim(),
      en: String(createPageForm.title.en || "").trim(),
    };
    if (createPageForm.templatePath) {
      await api.instantiatePageFromTemplate(createPageForm.templatePath, {
        slug,
        title,
        in_menu: createPageForm.inMenu,
        status: "hidden",
      });
    } else {
      await api.createPage({
        slug,
        title,
        has_header: props.defaultHasHeader,
        status: "hidden",
        in_menu: createPageForm.inMenu,
        menu_title: null,
      });
    }
    logDebug("createNewPage.directCreate.success", { slug });
    await loadPage();
  } catch (err) {
    console.error("Failed to create page:", err);
    createPageError.value = err?.message || "Failed to create page";
  } finally {
    isCreatingPage.value = false;
  }
}

async function createMissingPageRedirect() {
  const sourcePath = missingPageSourcePath.value;
  const statusCode = Number(createRedirectForm.statusCode) || 301;
  const requiresTarget = statusCode !== 410;
  const targetPath = requiresTarget ? String(createRedirectForm.targetPath || "").trim() : null;
  if (!sourcePath || (requiresTarget && !targetPath)) {
    createRedirectError.value = requiresTarget
      ? "Please select a redirect target page."
      : "Please provide a valid source path.";
    return;
  }
  if (targetPath && sourcePath === targetPath) {
    createRedirectError.value = "Redirect source and target cannot be identical.";
    return;
  }

  createRedirectError.value = "";
  const confirmMessage = requiresTarget
    ? `Create redirect "${sourcePath}" → "${targetPath}"?`
    : `Mark "${sourcePath}" as removed (410 Gone)?`;
  if (!window.confirm(confirmMessage)) {
    return;
  }

  isCreatingRedirect.value = true;
  logDebug("createMissingPageRedirect.start", { sourcePath, targetPath, status_code: statusCode });
  try {
    await api.createSitemapRedirect({
      source_path: sourcePath,
      target_path: targetPath,
      status_code: statusCode,
      is_active: true,
    });
    logDebug("createMissingPageRedirect.success", { sourcePath, targetPath });

    if (targetPath && shouldSkipRedirect()) {
      await router.replace(targetPath);
      return;
    }
    await loadPage();
  } catch (err) {
    console.error("Failed to create redirect:", err);
    createRedirectError.value = err?.message || "Failed to create redirect";
  } finally {
    isCreatingRedirect.value = false;
  }
}

async function openEditPageInSitemap() {
  if (isTemplateBuilder.value) return;
  const slug = String(pageSlug.value || "").trim();
  if (!slug || slug === "unknown") return;
  try {
    const pageMeta = currentPageMeta.value;
    const templatePath = resolveGeneratedPageTemplatePath(pageMeta);

    if (isGeneratedManagedPage(pageMeta) && templatePath) {
      const encodedTemplatePath = templatePath
        .split("/")
        .filter(Boolean)
        .map((segment) => encodeURIComponent(segment))
        .join("/");
      if (encodedTemplatePath) {
        await router.push(`/admin/templates/pages/${encodedTemplatePath}`);
        return;
      }
    }

    await router.push({
      path: "/admin/sitemap/pages",
      query: { edit: slug },
    });
  } catch (err) {
    console.error("Failed to open page editor in sitemap:", err);
  }
}

async function openGeneratedProgramGigSyncDialog(mode = "keep_source") {
  if (!showGeneratedProgramGigSyncButton.value || syncTemplateBusy.value || generatedProgramGigSyncConflictCheck.value.loading) return;
  const slug = String(pageSlug.value || "").trim();
  if (!slug || slug === "unknown") return;

  generatedProgramGigSyncConflictCheck.value = {
    loading: true,
    conflictCount: 0,
    error: "",
  };

  try {
    const report = await api.getPageTemplateSyncConflicts(slug);
    const conflictCount = Number(
      report?.conflict_count
      ?? report?.mapped_sync_report?.conflict_count
      ?? 0
    );
    generatedProgramGigSyncConflictCheck.value = {
      loading: false,
      conflictCount: Number.isFinite(conflictCount) ? Math.max(0, conflictCount) : 0,
      error: "",
    };
  } catch (err) {
    console.error("Failed to check generated page sync conflicts:", err);
    generatedProgramGigSyncConflictCheck.value = {
      loading: false,
      conflictCount: 0,
      error: err?.message || "Could not check mapped-field conflicts. Keep page edits is unavailable.",
    };
  }

  const normalizedMode = generatedProgramGigSyncOptions.value.some((option) => option.value === mode)
    ? mode
    : "keep_source";
  generatedProgramGigSyncDialog.value = {
    open: true,
    mode: normalizedMode,
  };
}

function closeGeneratedProgramGigSyncDialog() {
  generatedProgramGigSyncDialog.value = {
    open: false,
    mode: "keep_source",
  };
  generatedProgramGigSyncConflictCheck.value = {
    loading: false,
    conflictCount: 0,
    error: "",
  };
}

async function runGeneratedProgramGigSyncDialog() {
  if (!showGeneratedProgramGigSyncButton.value || syncTemplateBusy.value) return;
  const requestedMode = String(generatedProgramGigSyncDialog.value?.mode || "keep_source").trim();
  const mode = generatedProgramGigSyncOptions.value.some((option) => option.value === requestedMode)
    ? requestedMode
    : "keep_source";
  const forceRebuild = mode === "regenerate";
  await syncCurrentPageFromTemplate({
    syncMode: forceRebuild ? "" : mode,
    forceRebuild,
    successMessage: forceRebuild
      ? "Page regenerated from template."
      : mode === "keep_local"
        ? "Mapped data synced; page edits kept."
        : "Mapped data synced.",
  });
  if (!syncTemplateStatus.value.message || syncTemplateStatus.value.type !== "error") {
    closeGeneratedProgramGigSyncDialog();
  }
}

async function syncCurrentPageFromTemplate({
  syncMode = "",
  forceRebuild = false,
  successMessage = "",
} = {}) {
  if ((!showSyncTemplateButton.value && !showGeneratedProgramGigSyncButton.value) || syncTemplateBusy.value) return;
  const slug = String(pageSlug.value || "").trim();
  if (!slug || slug === "unknown") return;

  syncTemplateBusy.value = true;
  syncTemplateStatus.value = { type: "", message: "" };
  try {
    await api.syncPageFromTemplate(slug, { syncMode, forceRebuild });
    await loadPage();
    syncTemplateStatus.value = {
      type: "success",
      message: successMessage || "Template grid and mapping synced.",
    };
  } catch (err) {
    console.error("Failed to sync page from template:", err);
    syncTemplateStatus.value = {
      type: "error",
      message: err?.message || "Failed to sync page.",
    };
  } finally {
    syncTemplateBusy.value = false;
  }
}

async function openGeneratedIntegrationReviewItem() {
  const target = generatedIntegrationReviewRoute.value;
  if (!target) return;
  try {
    await router.push(target);
  } catch (err) {
    console.error("Failed to open integration review item:", err);
  }
}

/**
 * Load available section types
 */
async function loadSectionTypes() {
  if (!state.isAdmin) {
    availableSectionTypes.value = [];
    availableSectionTemplates.value = [];
    availableContainerTemplates.value = [];
    return;
  }
  try {
    const response = await api.getSectionTypes();
    const types = Array.isArray(response?.types) && response.types.length
      ? response.types
      : buildFallbackSectionTypeList();
    availableSectionTypes.value = types;
  } catch (err) {
    console.error("Failed to load section types:", err);
    availableSectionTypes.value = buildFallbackSectionTypeList();
  }
}

async function loadSectionTemplateLibraries() {
  if (!state.isAdmin) {
    availableSectionTemplates.value = [];
    availableContainerTemplates.value = [];
    return;
  }
  try {
    const [sectionRes, containerRes] = await Promise.all([
      api.listSectionTemplates(),
      api.listContainerTemplates(),
    ]);
    availableSectionTemplates.value = Array.isArray(sectionRes?.templates) ? sectionRes.templates : [];
    availableContainerTemplates.value = Array.isArray(containerRes?.templates) ? containerRes.templates : [];
  } catch (err) {
    console.error("Failed to load template libraries:", err);
    availableSectionTemplates.value = [];
    availableContainerTemplates.value = [];
  }
}

async function loadStaticPageTemplates() {
  if (!state.isAdmin) {
    staticPageTemplates.value = [];
    return;
  }
  try {
    const response = await api.listPageTemplates();
    const templates = Array.isArray(response?.templates) ? response.templates : [];
    staticPageTemplates.value = templates
      .filter((entry) => !entry?.parent_route)
      .map((entry) => ({
        path: String(entry?.path || entry?.template_name || ""),
        template_name: String(entry?.template_name || ""),
        title: entry?.title && typeof entry.title === "object"
          ? {
              de: String(entry.title.de || ""),
              en: String(entry.title.en || ""),
            }
          : null,
      }))
      .filter((entry) => entry.path);
    applySelectedStaticTemplateTitle({ force: true });
  } catch (err) {
    console.error("Failed to load static page templates:", err);
    staticPageTemplates.value = [];
  }
}

async function loadRedirectTargetPages() {
  if (!state.isAdmin) {
    redirectTargetPages.value = [];
    return;
  }
  redirectTargetPagesLoading.value = true;
  try {
    const pages = await api.listPages({ limit: 200, includeHidden: true });
    redirectTargetPages.value = Array.isArray(pages) ? pages : [];
  } catch (err) {
    console.error("Failed to load redirect target pages:", err);
    redirectTargetPages.value = [];
  } finally {
    redirectTargetPagesLoading.value = false;
  }
}

async function loadExistingRouteRedirect() {
  existingRouteRedirect.value = null;
  if (!state.isAdmin) return;

  const sourcePath = missingPageSourcePath.value;
  if (!sourcePath) return;

  const lookupPath = sourcePath;
  existingRouteRedirectLoading.value = true;
  try {
    const resolved = await api.resolveSitemapRedirect(lookupPath);
    // Ignore stale responses when route changed during lookup.
    if (missingPageSourcePath.value !== lookupPath) return;
    existingRouteRedirect.value = resolved?.found ? (resolved.redirect || null) : null;
  } catch (err) {
    console.error("Failed to resolve existing route redirect:", err);
    existingRouteRedirect.value = null;
  } finally {
    if (missingPageSourcePath.value === lookupPath) {
      existingRouteRedirectLoading.value = false;
    }
  }
}

async function classifyUnknownPageRoute() {
  const slugPath = `/${String(pageSlug.value || "").trim().replace(/^\/+/, "")}`;
  pageCreationRouteKind.value = "static_route";
  // Route classification uses admin template metadata and is only needed for admins.
  // Public visitors should never call admin template endpoints.
  if (!state.isAdmin) {
    return;
  }
  if (!slugPath || slugPath === "/unknown") {
    return;
  }
  try {
    const response = await api.listPageTemplates();
    const templates = Array.isArray(response?.templates) ? response.templates : [];
    const isItemChild = templates.some((entry) => {
      const parentRoute = String(entry?.parent_route || "").trim();
      if (!parentRoute) return false;
      const normalizedParent = parentRoute.startsWith("/") ? parentRoute : `/${parentRoute}`;
      if (slugPath === normalizedParent) return false;
      return slugPath.startsWith(`${normalizedParent}/`);
    });
    pageCreationRouteKind.value = isItemChild ? "item_child" : "static_route";
  } catch (err) {
    console.error("Failed to classify unknown route:", err);
    pageCreationRouteKind.value = "static_route";
  }
}

function applySelectedStaticTemplateTitle({ force = false } = {}) {
  const selectedPath = String(createPageForm.templatePath || "").trim();
  if (!selectedPath) {
    if (force) {
      createPageForm.title = { de: "", en: "" };
    }
    return;
  }
  const selectedTemplate = (Array.isArray(staticPageTemplates.value) ? staticPageTemplates.value : []).find(
    (entry) => String(entry?.path || "").trim() === selectedPath
  );
  const templateTitle = selectedTemplate?.title && typeof selectedTemplate.title === "object"
    ? selectedTemplate.title
    : null;
  if (!templateTitle) {
    if (force) {
      createPageForm.title = { de: "", en: "" };
    }
    return;
  }

  const nextTitle = {
    de: String(templateTitle.de || "").trim(),
    en: String(templateTitle.en || "").trim(),
  };
  if (!nextTitle.de && !nextTitle.en) {
    if (force) {
      createPageForm.title = { de: "", en: "" };
    }
    return;
  }

  if (!force) {
    const currentDe = String(createPageForm.title.de || "").trim();
    const currentEn = String(createPageForm.title.en || "").trim();
    if (currentDe || currentEn) return;
  }

  createPageForm.title = nextTitle;
}

function setMissingPageAction(nextAction) {
  missingPageAction.value = nextAction === "redirect" ? "redirect" : "page";
  createPageError.value = "";
  createRedirectError.value = "";
}

/**
 * Save header to backend
 */
function clearHeaderAutosaveStatusTimer() {
  if (headerAutosaveStatusTimer) {
    clearTimeout(headerAutosaveStatusTimer);
    headerAutosaveStatusTimer = null;
  }
}

function setHeaderAutosaveStatus(status) {
  clearHeaderAutosaveStatusTimer();
  headerAutosaveStatus.value = status;
}

function markHeaderAutosaveSaved() {
  headerAutosaveError.value = "";
  setHeaderAutosaveStatus("saved");
  headerAutosaveStatusTimer = setTimeout(() => {
    if (headerAutosaveStatus.value === "saved") {
      headerAutosaveStatus.value = "idle";
    }
    headerAutosaveStatusTimer = null;
  }, 3000);
}

function markHeaderAutosaveError(message = "Failed to save header") {
  headerAutosaveError.value = message;
  setHeaderAutosaveStatus("error");
  headerAutosaveStatusTimer = setTimeout(() => {
    if (headerAutosaveStatus.value === "error") {
      headerAutosaveStatus.value = "idle";
      headerAutosaveError.value = "";
    }
    headerAutosaveStatusTimer = null;
  }, 3000);
}

async function saveHeaderToBackend(options = null) {
  if (isSaving.value) {
    pendingHeaderSave.value = true;
    setHeaderAutosaveStatus("queued");
    return;
  }
  isSaving.value = true;
  headerAutosaveError.value = "";
  setHeaderAutosaveStatus("saving");
  const resolvedOptions =
    typeof options === "string" || options == null
      ? { revisionKind: options || null, revertedFromSavedAt: null }
      : options;
  const forcedRevisionKind = resolvedOptions?.revisionKind || null;
  const revertedFromSavedAt = resolvedOptions?.revertedFromSavedAt || null;

  try {
    do {
      pendingHeaderSave.value = false;
      setHeaderAutosaveStatus("saving");
      logDebug("saveHeader.start");

      const enabled = header.enabledFields || [];
      const revisionKind = forcedRevisionKind || "content";
      const headerData = {
        header_type: header.headerType || "hero",
        enabled_fields: enabled,
        background_media_url: String(header.backgroundImage || ""),
        background_zoom: headerBackgroundZoom.value,
        background_focal_x: headerBackgroundFocalX.value,
        background_focal_y: headerBackgroundFocalY.value,
        background_rotation: headerBackgroundRotation.value,
        overlay_image_url: String(header.overlayImage || ""),
        overlay_zoom: headerOverlayZoom.value,
        overlay_focal_x: headerOverlayFocalX.value,
        overlay_focal_y: headerOverlayFocalY.value,
        overlay_rotation: headerOverlayRotation.value,
        hero_subtitle: normalizeBilingualText(header.subtitle),
        cta_buttons: (header.ctaButtons || []).map(btn => ({
          text: normalizeBilingualText(btn.text),
          url: btn.url || "",
          button_type: btn.buttonType || null
        })),
        admin_notes: header.adminNotes || "",
        admin_todos: serializeTodoList(header.adminTodos || []),
        revision_change_kind: revisionKind,
      };
      if (revertedFromSavedAt) {
        headerData.revision_reverted_from_saved_at = String(revertedFromSavedAt);
      }

      const result = header.headerId
        ? await api.updateHeader(header.headerId, headerData)
        : await api.updatePageHeader(pageSlug.value, headerData);

      if (result.id && !header.headerId) {
        header.headerId = result.id;
      }
      if (Object.prototype.hasOwnProperty.call(result || {}, "shared")) {
        header.shared = result.shared === true;
      }
      header.adminNotes = String(result?.admin_notes || "");
      header.adminTodos = Array.isArray(result?.admin_todos) ? result.admin_todos : [];
      headerNotesDraft.value = header.adminNotes;
      headerTodoDraft.value = normalizeHeaderTodos(header.adminTodos);

      logDebug("saveHeader.success");
      headerMediaAdjustDirty = false;
      refreshHeaderRevisionStatus();
      if (headerAdminActiveTab.value === "history") {
        await loadHeaderHistory();
      }
    } while (pendingHeaderSave.value);
    markHeaderAutosaveSaved();
  } catch (err) {
    logDebug("saveHeader.error", { error: err.message });
    console.error("Failed to save header:", err);
    markHeaderAutosaveError(err?.message || "Failed to save header");
  } finally {
    isSaving.value = false;
    pendingHeaderSave.value = false;
  }
}

// -------------------------
// Header Update Functions
// -------------------------

function headerFieldEnabled(field) {
  const enabled = header.enabledFields;
  if (!enabled || !Array.isArray(enabled)) return true;
  return enabled.includes(field);
}

function updateHeader(patch, options = {}) {
  Object.assign(header, patch);
  logDebug("updateHeader", patch);
  saveHeaderToBackend(options);
}

function normalizeBilingualText(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return {
      de: String(value.de ?? ""),
      en: String(value.en ?? "")
    };
  }
  if (typeof value === "string") {
    return { de: value, en: value };
  }
  return { de: "", en: "" };
}

function createHeaderCtaDraftId() {
  return `cta-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function defaultCtaButtonType(index = 0) {
  return index === 0 ? "primary" : "secondary";
}

function normalizeCtaButtonType(type, index = 0) {
  const normalized = String(type || "").trim();
  return normalized || defaultCtaButtonType(index);
}

function formatButtonTypeLabel(type) {
  const normalized = String(type || "").trim();
  if (!normalized) return "Button";
  return normalized
    .replace(/[_-]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function normalizeHeaderCtaButtonForDraft(button, index = 0) {
  const item = button && typeof button === "object" ? button : {};
  return {
    id: String(item.id || createHeaderCtaDraftId()),
    text: normalizeBilingualText(item.text),
    url: String(item.url || ""),
    buttonType: normalizeCtaButtonType(item.buttonType, index),
  };
}

function syncHeaderCtaDraftFromHeader() {
  const source = Array.isArray(header.ctaButtons) ? header.ctaButtons : [];
  headerCtaDraft.value = source.map((item, index) => normalizeHeaderCtaButtonForDraft(item, index));
  if (headerCtaExpandedItem.value >= headerCtaDraft.value.length) {
    headerCtaExpandedItem.value = headerCtaDraft.value.length - 1;
  }
  if (!headerCtaDraft.value.length) {
    headerCtaExpandedItem.value = -1;
  }
}

function addHeaderCtaItem() {
  if (headerCtaDraft.value.length >= HEADER_MAX_CTA_BUTTONS) return;
  headerCtaDraft.value.push(
    normalizeHeaderCtaButtonForDraft(
      {
        text: { de: "", en: "" },
        url: "",
        buttonType: defaultCtaButtonType(headerCtaDraft.value.length),
      },
      headerCtaDraft.value.length
    )
  );
  headerCtaExpandedItem.value = headerCtaDraft.value.length - 1;
}

function removeHeaderCtaItem(index) {
  if (index < 0 || index >= headerCtaDraft.value.length) return;
  headerCtaDraft.value.splice(index, 1);
  if (headerCtaExpandedItem.value === index) {
    headerCtaExpandedItem.value = headerCtaDraft.value.length
      ? Math.min(index, headerCtaDraft.value.length - 1)
      : -1;
  } else if (headerCtaExpandedItem.value > index) {
    headerCtaExpandedItem.value -= 1;
  }
}

function saveHeaderCtaItems() {
  header.ctaButtons = headerCtaDraft.value.map((item, index) => ({
    text: normalizeBilingualText(item.text),
    url: String(item.url || ""),
    buttonType: normalizeCtaButtonType(item.buttonType, index),
  }));
  logDebug("saveHeaderCtaItems", {
    count: header.ctaButtons.length,
    buttonTypes: header.ctaButtons.map((btn) => btn.buttonType || null),
  });
  saveHeaderToBackend("content");
  syncHeaderCtaDraftFromHeader();
}

function headerCtaStyleLabel(type, index = 0) {
  const normalizedType = normalizeCtaButtonType(type, index);
  const fromOptions = headerCtaButtonStyleOptions.value.find((item) => item.id === normalizedType);
  return fromOptions?.label || formatButtonTypeLabel(normalizedType);
}

function currentHeaderEditorName() {
  const user = getUser?.();
  return user?.name || user?.username || "unknown";
}

function cloneSerializable(value) {
  if (value == null) return value;
  try {
    return JSON.parse(JSON.stringify(toRaw(value)));
  } catch {
    return value;
  }
}

function normalizeHeaderTodos(todos) {
  return normalizeTodoList(todos, { defaultTagId: defaultHeaderTodoTagId.value });
}

async function setHeaderShared(nextShared) {
  if (!header.headerId || headerSharingSaving.value) return;
  const previousShared = header.shared === true;
  const normalizedShared = nextShared === true;
  if (previousShared === normalizedShared) return;

  header.shared = normalizedShared;
  headerSharingSaving.value = true;
  headerSharingError.value = "";
  try {
    const updated = await api.updateHeader(header.headerId, { shared: normalizedShared });
    if (Object.prototype.hasOwnProperty.call(updated || {}, "shared")) {
      header.shared = updated.shared === true;
    }
  } catch (err) {
    header.shared = previousShared;
    headerSharingError.value = err instanceof Error
      ? (err.message || "Failed to update header sharing.")
      : "Failed to update header sharing.";
    console.error("Failed to update header sharing:", err);
  } finally {
    headerSharingSaving.value = false;
  }
}

async function persistHeaderNotes() {
  if (!header.headerId) return;
  try {
    const updated = await api.updateHeader(header.headerId, {
      admin_notes: headerNotesDraft.value,
      admin_todos: serializeTodoList(headerTodoDraft.value),
      revision_change_kind: "content",
    });
    header.adminNotes = String(updated?.admin_notes || "");
    header.adminTodos = Array.isArray(updated?.admin_todos) ? updated.admin_todos : [];
    refreshHeaderRevisionStatus();
    if (headerAdminActiveTab.value === "history") await loadHeaderHistory();
  } catch (err) {
    console.error("Failed to save header notes:", err);
  }
}

function addHeaderTodo() {
  const text = headerNewTodo.value.trim();
  if (!text) return;
  headerTodoDraft.value = [
    ...headerTodoDraft.value,
    {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      text,
      done: false,
      createdBy: currentHeaderEditorName(),
      createdAt: new Date().toISOString(),
      resolvedBy: null,
      resolvedAt: null,
      tag: headerNewTodoTag.value || defaultHeaderTodoTagId.value,
      priority: headerNewTodoPriority.value,
      priorityRank: null,
    },
  ];
  headerNewTodo.value = "";
  headerNewTodoTag.value = defaultHeaderTodoTagId.value;
  headerNewTodoPriority.value = DEFAULT_TODO_PRIORITY;
  persistHeaderNotes();
}

function toggleHeaderTodo(id, done) {
  headerTodoDraft.value = headerTodoDraft.value.map((todo) =>
    todo.id === id
      ? {
        ...todo,
        done: Boolean(done),
        resolvedBy: done ? currentHeaderEditorName() : null,
        resolvedAt: done ? new Date().toISOString() : null,
      }
      : todo
  );
  persistHeaderNotes();
}

function removeHeaderTodo(id) {
  headerTodoDraft.value = headerTodoDraft.value.filter((todo) => todo.id !== id);
  persistHeaderNotes();
}

function headerTodoAuthorName(todo) {
  if (todo?.done && todo?.resolvedBy) return todo.resolvedBy;
  return todo?.createdBy || "unknown";
}

function headerTodoAuthorTime(todo) {
  if (todo?.done && todo?.resolvedAt) return todo.resolvedAt;
  return todo?.createdAt || null;
}

function headerTodoTagArea(tagId) {
  return headerTodoTagOptions.value.find((tag) => tag.id === tagId)?.area || "content";
}

function setHeaderFieldEnabled(fieldKey, enabled) {
  const current = Array.isArray(header.enabledFields) ? header.enabledFields : [];
  const next = enabled
    ? Array.from(new Set([...current, fieldKey]))
    : current.filter((item) => item !== fieldKey);
  state.headerEnabledFields = next;
  updateHeader({ enabledFields: next }, { revisionKind: "content" });
}

function setHeaderBackgroundZoom(value) {
  applyHeaderMediaAdjustPatch({ backgroundZoom: normalizeHeaderZoom(value) });
}

function setHeaderBackgroundFocalX(value) {
  applyHeaderMediaAdjustPatch({ backgroundFocalX: normalizeHeaderFocal(value) });
}

function setHeaderBackgroundFocalY(value) {
  applyHeaderMediaAdjustPatch({ backgroundFocalY: normalizeHeaderFocal(value) });
}

function setHeaderBackgroundRotation(value) {
  applyHeaderMediaAdjustPatch({ backgroundRotation: normalizeHeaderRotation(value) });
}

function setHeaderOverlayZoom(value) {
  applyHeaderMediaAdjustPatch({ overlayZoom: normalizeHeaderZoom(value) });
}

function setHeaderOverlayFocalX(value) {
  applyHeaderMediaAdjustPatch({ overlayFocalX: normalizeHeaderFocal(value) });
}

function setHeaderOverlayFocalY(value) {
  applyHeaderMediaAdjustPatch({ overlayFocalY: normalizeHeaderFocal(value) });
}

function setHeaderOverlayRotation(value) {
  applyHeaderMediaAdjustPatch({ overlayRotation: normalizeHeaderRotation(value) });
}

function applyHeaderMediaAdjustPatch(patch) {
  Object.assign(header, patch);
  logDebug("updateHeader", patch);
  headerMediaAdjustDirty = true;
}

function commitHeaderMediaAdjustPatch() {
  if (!headerMediaAdjustDirty) return;
  headerMediaAdjustDirty = false;
  saveHeaderToBackend("content");
}

function setHeaderMediaUrl(targetField, value) {
  const nextUrl = String(value || "").trim();
  if (targetField === "overlay_image") {
    updateHeader({ overlayImage: nextUrl }, { revisionKind: "content" });
    return;
  }
  updateHeader({ backgroundImage: nextUrl }, { revisionKind: "content" });
}

function clearHeaderMedia(targetField) {
  if (targetField === "overlay_image") {
    updateHeader(
      { overlayImage: "", overlayZoom: 1, overlayFocalX: 50, overlayFocalY: 50, overlayRotation: 0 },
      { revisionKind: "content" }
    );
    return;
  }
  updateHeader(
    { backgroundImage: "", backgroundZoom: 1, backgroundFocalX: 50, backgroundFocalY: 50, backgroundRotation: 0 },
    { revisionKind: "content" }
  );
}

function openHeaderMediaPicker(targetField) {
  if (!state.isAdmin) return;
  if (targetField !== "background_image" && targetField !== "overlay_image") return;
  headerMediaPickerTarget.value = targetField;
  headerMediaPickerOpen.value = true;
}

function closeHeaderMediaPicker() {
  headerMediaPickerOpen.value = false;
}

function onHeaderMediaSelect(selection) {
  const url = String(selection?.url || "");
  if (headerMediaPickerTarget.value === "overlay_image") {
    updateHeader({ overlayImage: url }, { revisionKind: "content" });
  } else {
    updateHeader({ backgroundImage: url }, { revisionKind: "content" });
  }
  closeHeaderMediaPicker();
}

function patchHeaderDesignOverrides(mutator) {
  if (!state.sectionDesignOverrides || typeof state.sectionDesignOverrides !== "object") {
    state.sectionDesignOverrides = {};
  }
  const current = state.sectionDesignOverrides.__header__;
  const nextOverrides = current && typeof current === "object" ? cloneSerializable(current) : {};
  if (typeof mutator === "function") {
    mutator(nextOverrides);
  }
  const keys = Object.keys(nextOverrides);
  if (keys.length === 0) {
    delete state.sectionDesignOverrides.__header__;
    return;
  }
  state.sectionDesignOverrides.__header__ = nextOverrides;
}

function persistHeaderDesignOverrides() {
  saveSectionDesignOverrides("__header__", pageSlug.value);
}

function formatHeaderBlurValue(value) {
  const normalized = normalizeHeaderBlurValue(value);
  return `${normalized.toFixed(1)}px`;
}

function formatHeaderBlurPositionValue(value) {
  const normalized = normalizeHeaderBlurPositionValue(value);
  return `${Math.round(normalized)}vh`;
}

function setHeaderBlurMode(rawMode) {
  const nextMode = normalizeHeaderBlurMode(rawMode);
  patchHeaderDesignOverrides((nextOverrides) => {
    nextOverrides.heroBackgroundBlurMode = nextMode;
    if (nextMode !== "scroll") return;
    if (hasExplicitHeaderBlurStart(nextOverrides.heroBackgroundBlurStart)) return;
    const fallbackEnd = nextOverrides.heroBackgroundBlur ?? headerBlurEndEditorValue.value;
    nextOverrides.heroBackgroundBlurStart = normalizeHeaderBlurValue(fallbackEnd);
  });
  persistHeaderDesignOverrides();
}

function setHeaderBlurEndValue(rawValue) {
  const nextEnd = normalizeHeaderBlurValue(rawValue);
  patchHeaderDesignOverrides((nextOverrides) => {
    nextOverrides.heroBackgroundBlur = nextEnd;
  });
}

function setHeaderBlurStartValue(rawValue) {
  const nextStart = normalizeHeaderBlurValue(rawValue);
  patchHeaderDesignOverrides((nextOverrides) => {
    nextOverrides.heroBackgroundBlurStart = nextStart;
  });
}

function setHeaderBlurStartVhValue(rawValue) {
  const nextStartVh = normalizeHeaderBlurPositionValue(rawValue, HEADER_BLUR_START_VH_DEFAULT);
  patchHeaderDesignOverrides((nextOverrides) => {
    nextOverrides.heroBackgroundBlurStartVh = nextStartVh;
  });
}

function setHeaderBlurEndVhValue(rawValue) {
  const nextEndVh = normalizeHeaderBlurPositionValue(rawValue, HEADER_BLUR_END_VH_DEFAULT);
  patchHeaderDesignOverrides((nextOverrides) => {
    nextOverrides.heroBackgroundBlurEndVh = nextEndVh;
  });
}

function persistHeaderLayerOrder(orderCandidate) {
  const order = sanitizeHeaderLayerOrder(orderCandidate);
  patchHeaderDesignOverrides((nextOverrides) => {
    nextOverrides.heroLayerOrder = order;
  });
  persistHeaderDesignOverrides();
}

function onHeaderFieldOrderChanged() {
  const order = headerFieldEditorItems.value.map((item) => item.key);
  persistHeaderLayerOrder(order);
}

function formatHeaderHistoryDate(value) {
  return formatRevisionTimestampBerlin(value) || "Unknown date";
}

function getCurrentHeaderContentSnapshot() {
  return headerHistoryCurrent.value?.content_snapshot || null;
}

function getCurrentHeaderDesignSnapshot() {
  return headerHistoryCurrent.value?.design_snapshot || null;
}

function applyHeaderRevisionPreview({
  contentSnapshot = undefined,
  designSnapshot = undefined,
  applyContent = true,
  applyDesign = true,
} = {}) {
  if (applyContent && contentSnapshot && typeof contentSnapshot === "object") {
    const enabled = Array.isArray(contentSnapshot.enabled_fields)
      ? [...contentSnapshot.enabled_fields]
      : ["title", "subtitle", "cta_buttons", "overlay_image", "background_image"];
    header.headerType = contentSnapshot.header_type || "hero";
    header.enabledFields = enabled;
    state.headerEnabledFields = enabled;
    header.subtitle = normalizeBilingualText(contentSnapshot.hero_subtitle);
    header.backgroundImage = contentSnapshot.background_media_url || "";
    header.backgroundZoom = normalizeHeaderZoom(contentSnapshot.background_zoom);
    header.backgroundFocalX = normalizeHeaderFocal(contentSnapshot.background_focal_x);
    header.backgroundFocalY = normalizeHeaderFocal(contentSnapshot.background_focal_y);
    header.backgroundRotation = normalizeHeaderRotation(contentSnapshot.background_rotation);
    header.overlayImage = contentSnapshot.overlay_image_url || "";
    header.overlayZoom = normalizeHeaderZoom(contentSnapshot.overlay_zoom);
    header.overlayFocalX = normalizeHeaderFocal(contentSnapshot.overlay_focal_x);
    header.overlayFocalY = normalizeHeaderFocal(contentSnapshot.overlay_focal_y);
    header.overlayRotation = normalizeHeaderRotation(contentSnapshot.overlay_rotation);
    if (Array.isArray(contentSnapshot.cta_buttons)) {
      header.ctaButtons = contentSnapshot.cta_buttons.map((btn) => ({
        text: normalizeBilingualText(btn?.text),
        url: btn?.url || "",
        buttonType: btn?.button_type || null,
      }));
    } else {
      header.ctaButtons = [];
    }
    syncHeaderCtaDraftFromHeader();
    header.adminNotes = String(contentSnapshot.admin_notes || "");
    header.adminTodos = normalizeHeaderTodos(contentSnapshot.admin_todos || []);
    headerNotesDraft.value = header.adminNotes;
    headerTodoDraft.value = normalizeHeaderTodos(header.adminTodos);
  }

  if (applyDesign) {
    if (designSnapshot === null) {
      delete state.sectionDesignOverrides.__header__;
      return;
    }
    if (designSnapshot && typeof designSnapshot === "object") {
      if (Object.prototype.hasOwnProperty.call(designSnapshot, "design_overrides")) {
        const overrides = designSnapshot.design_overrides;
        const normalizedOverrides = normalizeSectionDesignOverridesForFrontend(
          cloneSerializable(overrides)
        );
        if (normalizedOverrides == null) delete state.sectionDesignOverrides.__header__;
        else state.sectionDesignOverrides.__header__ = normalizedOverrides;
      }
    }
  }
}

function applySelectedHeaderHistoryPreview() {
  const selectedDesign = selectedHeaderDesignRevisionEntry.value;
  const selectedContent = selectedHeaderContentRevisionEntry.value;
  const designSnapshot = selectedDesign?.source === "current"
    ? getCurrentHeaderDesignSnapshot()
    : (selectedDesign?.designSnapshot || null);
  const contentSnapshot = selectedContent?.source === "current"
    ? getCurrentHeaderContentSnapshot()
    : (selectedContent?.contentSnapshot || null);
  applyHeaderRevisionPreview({
    contentSnapshot,
    designSnapshot,
    applyContent: true,
    applyDesign: true,
  });
}

function resetHeaderHistorySelectionAndPreview() {
  selectedHeaderDesignRevisionKey.value = "current-design";
  selectedHeaderContentRevisionKey.value = "current-content";
  applySelectedHeaderHistoryPreview();
}

function selectHeaderHistoryEntry(kind, entry) {
  if (!entry?.key) return;
  if (kind === "design") selectedHeaderDesignRevisionKey.value = entry.key;
  else selectedHeaderContentRevisionKey.value = entry.key;
  applySelectedHeaderHistoryPreview();
}

function stableSnapshotString(value) {
  try {
    return JSON.stringify(value || null);
  } catch {
    return "";
  }
}

function isGenericDesignFallbackLabel(value) {
  const label = String(value || "").trim();
  if (!label) return false;
  return /^(Design: (value|unknown)|Override: designOverrides)$/i.test(label);
}

async function loadHeaderHistory() {
  const requestId = ++headerHistoryLoadRequestId;
  if (!header.headerId) {
    headerHistoryCurrent.value = null;
    headerHistoryStack.value = [];
    headerFutureStack.value = [];
    headerHistoryError.value = "Revision history not available yet.";
    resetHeaderHistorySelectionAndPreview();
    return;
  }

  headerHistoryLoading.value = true;
  headerHistoryError.value = "";
  try {
    const response = await api.getHeaderRevisions(header.headerId);
    if (requestId !== headerHistoryLoadRequestId || headerAdminActiveTab.value !== "history") return;
    if (response?.enabled === false) {
      headerHistoryCurrent.value = null;
      headerHistoryStack.value = [];
      headerFutureStack.value = [];
      headerHistoryOptions.value = {
        includeDesign: Boolean(response?.options?.include_design),
        includeContent: Boolean(response?.options?.include_content),
      };
      headerHistoryError.value = "Revisions are disabled for header.";
      resetHeaderHistorySelectionAndPreview();
      return;
    }

    headerHistoryCurrent.value = response?.current || null;
    headerHistoryStack.value = Array.isArray(response?.history) ? response.history : [];
    headerFutureStack.value = Array.isArray(response?.future) ? response.future : [];
    headerHistoryOptions.value = {
      includeDesign: response?.options?.include_design !== false,
      includeContent: response?.options?.include_content !== false,
    };
    if (!headerRevisionEntries.value.some((entry) => entry.key === selectedHeaderDesignRevisionKey.value)) {
      selectedHeaderDesignRevisionKey.value = "current-design";
    }
    if (!headerRevisionEntries.value.some((entry) => entry.key === selectedHeaderContentRevisionKey.value)) {
      selectedHeaderContentRevisionKey.value = "current-content";
    }
    applySelectedHeaderHistoryPreview();
  } catch (err) {
    if (requestId !== headerHistoryLoadRequestId || headerAdminActiveTab.value !== "history") return;
    headerHistoryCurrent.value = null;
    headerHistoryStack.value = [];
    headerFutureStack.value = [];
    headerHistoryError.value = "Failed to load header history.";
    resetHeaderHistorySelectionAndPreview();
    console.error("Failed to load header history:", err);
  } finally {
    if (requestId === headerHistoryLoadRequestId) headerHistoryLoading.value = false;
  }
}

async function revertSelectedHeaderRevision(kind) {
  const isDesign = kind === "design";
  const selected = isDesign ? selectedHeaderDesignRevisionEntry.value : selectedHeaderContentRevisionEntry.value;
  const canRevert = isDesign ? canRevertHeaderDesign.value : canRevertHeaderContent.value;
  if (!canRevert || !selected || selected.source === "current") return;

  if (isDesign) headerHistoryRevertingDesign.value = true;
  else headerHistoryRevertingContent.value = true;
  headerHistoryError.value = "";

  try {
    if (isDesign) {
      const hasDesignDiffs = Array.isArray(selected.designParamDiffs) && selected.designParamDiffs.length > 0;
      const onlyGenericDesignFallback =
        hasDesignDiffs
        && selected.designParamDiffs.length === 1
        && isGenericDesignFallbackLabel(selected.designParamDiffs[0]);
      const designSnapshotMatchesCurrent = (
        selected.designSnapshot
        && stableSnapshotString(selected.designSnapshot) === stableSnapshotString(getCurrentHeaderDesignSnapshot())
      );
      const canFallbackToContentRevert = Boolean(selected.contentSnapshot) && (
        !hasDesignDiffs
        || onlyGenericDesignFallback
        || designSnapshotMatchesCurrent
      );

      if (canFallbackToContentRevert) {
        applyHeaderRevisionPreview({
          contentSnapshot: selected.contentSnapshot,
          applyContent: true,
          applyDesign: false,
        });
        await saveHeaderToBackend({
          revisionKind: "content",
          revertedFromSavedAt: selected.savedAt || null,
        });
      } else {
        applyHeaderRevisionPreview({
          designSnapshot: selected.designSnapshot,
          applyContent: false,
          applyDesign: true,
        });
        await saveSectionDesignOverrides("__header__", pageSlug.value, {
          revertedFromSavedAt: selected.savedAt || null,
        });
      }
    } else {
      applyHeaderRevisionPreview({
        contentSnapshot: selected.contentSnapshot,
        applyContent: true,
        applyDesign: false,
      });
      await saveHeaderToBackend({
        revisionKind: "content",
        revertedFromSavedAt: selected.savedAt || null,
      });
    }

    await refreshHeaderRevisionStatus();
    await loadHeaderHistory();
    if (isDesign) selectedHeaderDesignRevisionKey.value = "current-design";
    else selectedHeaderContentRevisionKey.value = "current-content";
    applySelectedHeaderHistoryPreview();
  } catch (err) {
    headerHistoryError.value = `Failed to revert ${isDesign ? "design" : "content"} revision.`;
    console.error("Failed to revert header revision:", err);
  } finally {
    if (isDesign) headerHistoryRevertingDesign.value = false;
    else headerHistoryRevertingContent.value = false;
  }
}

/**
 * Update page title (displayed in hero section)
 * The title is stored on the page, not the header
 */
async function updatePageTitle(newTitle) {
  state.pageTitle = newTitle;
  logDebug("updatePageTitle", newTitle);
  
  try {
    await api.updatePage(pageSlug.value, { title: newTitle });
    logDebug("updatePageTitle.saved", { slug: pageSlug.value });
  } catch (err) {
    console.error("Failed to save page title:", err);
  }
}

function ctaButtonClass(btn, index) {
  const type = normalizeCtaButtonType(btn?.buttonType, index);
  if (type === 'secondary') return 'secondary';
  if (type === 'ghost') return 'ghost';
  return '';
}

function ctaButtonStyle(btn, index) {
  const type = normalizeCtaButtonType(btn?.buttonType, index);
  return getButtonTypeInlineStyle(type);
}

/**
 * Open the Manage Headers dialog to create a new header
 */
async function openCreateHeader() {
  if (isTemplateBuilder.value) {
    if (templateBuilderKind.value !== "page") {
      return;
    }
    try {
      await api.updatePageHeader(pageSlug.value, {
        header_type: "hero",
        enabled_fields: ["title", "subtitle", "cta_buttons", "overlay_image", "background_image"],
        hero_title: { de: "", en: "" },
        hero_subtitle: { de: "", en: "" },
        cta_buttons: [],
      });
      await loadPage();
    } catch (err) {
      console.error("Failed to create template header:", err);
    }
    return;
  }

  if (sectionPanelRef.value) {
    sectionPanelRef.value.openHeaderDialog('new');
  }
}

/**
 * Open the Sections manager dialog to add/reuse sections
 */
function openManageSections() {
  if (isPageNotFound.value) {
    createPageError.value = "Create the page first before managing sections.";
    return;
  }
  if (sectionPanelRef.value) {
    sectionPanelRef.value.openSectionsDialog('templates');
  }
}

function generateContainerTemplateInstanceId() {
  const stamp = Date.now().toString(36);
  const random = Math.random().toString(36).slice(2, 10);
  return `tplc_${stamp}_${random}`;
}

function resolveSectionTemplateDoc(sectionType, templateName) {
  const normalizedSectionType = normalizeSectionTypeKey(sectionType);
  const normalizedTemplateName = String(templateName || "").trim().toLowerCase();
  return (Array.isArray(availableSectionTemplates.value) ? availableSectionTemplates.value : []).find((entry) => {
    const entrySectionType = normalizeSectionTypeKey(entry?.section_type);
    const entryTemplateName = String(entry?.template_name || "").trim().toLowerCase();
    return entrySectionType === normalizedSectionType && entryTemplateName === normalizedTemplateName;
  });
}

function resolveContainerTemplateDoc(templateName) {
  const normalizedTemplateName = String(templateName || "").trim().toLowerCase();
  return (Array.isArray(availableContainerTemplates.value) ? availableContainerTemplates.value : []).find(
    (entry) => String(entry?.template_name || "").trim().toLowerCase() === normalizedTemplateName
  );
}

// -------------------------
// Section Management
// -------------------------

/**
 * Handle header visibility toggle from SectionPanel
 */
async function handleToggleHeader(show) {
  const prevEnabled = headerEnabled.value;
  headerEnabled.value = show;
  try {
    await api.updatePage(pageSlug.value, { has_header: show });
    if (show && !header.hasHeader && header.headerId) {
      // Header was hidden before load or linked while disabled: fetch once, avoid full page reload.
      const linkedHeader = await api.getHeader(header.headerId);
      if (linkedHeader) {
        mapBackendHeader(linkedHeader);
      }
    }
  } catch (err) {
    console.error("Failed to toggle header visibility:", err);
    headerEnabled.value = prevEnabled;
  }
}

/**
 * Handle header change from SectionPanel (new header selected/created)
 */
async function handleHeaderChanged(headerId) {
  await loadPage();
}

function openHeaderRevisionSettings() {
  router.push("/admin/database/revisions");
}

/**
 * Handle adding a new section to the page
 */
async function handleAddSection(sectionData) {
  logDebug("handleAddSection", sectionData);
  
  try {
    if (isPageNotFound.value) {
      createPageError.value = "Create the page first before adding sections.";
      return;
    }

    if (sectionData.templateKind === "container_template") {
      const templateName = String(sectionData.template_name || "").trim();
      if (!templateName) {
        throw new Error("Container template name is missing");
      }
      if (isTemplateBuilder.value) {
        let templateDoc = resolveContainerTemplateDoc(templateName);
        if (!templateDoc) {
          const response = await api.listContainerTemplates();
          availableContainerTemplates.value = Array.isArray(response?.templates) ? response.templates : [];
          templateDoc = resolveContainerTemplateDoc(templateName);
        }
        const templateSections = Array.isArray(templateDoc?.sections)
          ? [...templateDoc.sections].sort((left, right) => Number(left?.order || 0) - Number(right?.order || 0))
          : [];
        if (!templateSections.length) {
          throw new Error(`Container template "${templateName}" has no sections`);
        }

        const containerId = generateContainerTemplateInstanceId();
        const knownSectionIds = new Set(
          Object.values(state.sectionIds || {}).map((id) => String(id || "").trim()).filter(Boolean)
        );
        const createdSectionIds = [];
        for (const section of templateSections) {
          const existingOverrides = normalizeSectionDesignOverridesForFrontend(
            section?.design_overrides
          ) || {};
          const nextOverrides = {
            ...existingOverrides,
            [CONTAINER_TEMPLATE_LOCK_KEY]: true,
            [CONTAINER_TEMPLATE_NAME_KEY]: templateName,
          };
          const response = await api.createAndAddSection(pageSlug.value, {
            section_type: section?.section_type || "text",
            title_placeholder: section?.title_placeholder || section?.section_type || "section",
            title: section?.title && typeof section.title === "object" ? section.title : undefined,
            type_data: section?.type_data && typeof section.type_data === "object" ? section.type_data : {},
            design_overrides: normalizeSectionDesignOverridesForBackend(nextOverrides),
          });
          const responseSections = Array.isArray(response?.sections) ? response.sections : [];
          for (const entry of responseSections) {
            const sectionId = String(entry?._id || entry?.id || "").trim();
            if (!sectionId || knownSectionIds.has(sectionId)) continue;
            knownSectionIds.add(sectionId);
            createdSectionIds.push(sectionId);
          }
        }
        if (createdSectionIds.length >= 2) {
          const currentStructure = Array.isArray(state.landingLayout?.structure)
            ? state.landingLayout.structure
            : [];
          const nextStructure = [
            ...currentStructure,
            {
              type: "container",
              container_id: containerId,
              section_ids: createdSectionIds,
            },
          ];
          await api.updatePage(pageSlug.value, { section_structure: nextStructure });
        }
        await applyTemplateBuilderPayloadOrReload(await api.getPageFull(pageSlug.value, true));
        return;
      }
      await api.instantiateContainerTemplate(templateName, pageSlug.value);
      await loadPage();
      return;
    }

    if (sectionData.existingSectionId) {
      // Use existing section - add reference to page
      // Calculate order based on the current order array length
      const currentOrder = state.landingLayout?.order || [];
      const maxOrder = currentOrder.length;
      const response = await api.addSectionToPage(pageSlug.value, {
        section_id: sectionData.existingSectionId,
        order: maxOrder,
        visible: true
      });
      if (isTemplateBuilder.value) {
        await applyTemplateBuilderPayloadOrReload(response);
        logDebug("handleAddSection.success", { sectionType: sectionData.section_type });
        return;
      }
    } else {
      const sectionType = String(sectionData.section_type || "").trim() || "text";
      if (isTemplateBuilder.value && sectionData.template_name) {
        let templateDoc = resolveSectionTemplateDoc(sectionType, sectionData.template_name);
        if (!templateDoc) {
          const response = await api.listSectionTemplates({ sectionType });
          availableSectionTemplates.value = Array.isArray(response?.templates) ? response.templates : [];
          templateDoc = resolveSectionTemplateDoc(sectionType, sectionData.template_name);
        }
        if (templateDoc?.id) {
          const currentOrder = state.landingLayout?.order || [];
          const maxOrder = currentOrder.length;
          const response = await api.addSectionToPage(pageSlug.value, {
            section_id: `ts__${templateDoc.id}`,
            order: maxOrder,
            visible: true,
          });
          await applyTemplateBuilderPayloadOrReload(response);
          return;
        }
      }

      // Create new section from template and add to page in one call
      const payload = {
        section_type: sectionType,
        title_placeholder: sectionData.title_placeholder || sectionType,
      };
      if (!sectionData.template_name) {
        payload.type_data = sectionData.default_data || {};
      } else if (sectionData.type_data && typeof sectionData.type_data === "object") {
        payload.type_data = sectionData.type_data;
      }
      // Only include title if explicitly provided with content
      if (sectionData.title?.de || sectionData.title?.en) {
        payload.title = sectionData.title;
      }
      if (sectionData.design_overrides && typeof sectionData.design_overrides === "object") {
        payload.design_overrides = normalizeSectionDesignOverridesForBackend(
          sectionData.design_overrides
        );
      }
      if (sectionData.template_name) {
        payload.template_name = String(sectionData.template_name);
      }
      const response = await api.createAndAddSection(pageSlug.value, payload);
      if (isTemplateBuilder.value) {
        await applyTemplateBuilderPayloadOrReload(response);
        logDebug("handleAddSection.success", { sectionType: sectionData.section_type });
        return;
      }
    }
    
    // Reload page to get updated sections
    await loadPage();
    
    logDebug("handleAddSection.success", { sectionType: sectionData.section_type });
  } catch (err) {
    logDebug("handleAddSection.error", { error: err.message });
    console.error("Failed to add section:", err);
  }
}

/**
 * Handle section removal event from SectionPanel
 */
async function handleSectionRemoved({ key, id, keys, pageData }) {
  logDebug("handleSectionRemoved", { key, id });
  
  // Clear ticker items if ticker was removed
  const removedKeys = Array.isArray(keys) ? keys : [key];
  if (removedKeys.includes("ticker")) {
    state.tickerItems = [];
  }
  if (isTemplateBuilder.value) {
    await applyTemplateBuilderPayloadOrReload(pageData);
  }
}

// -------------------------
// Lifecycle
// -------------------------

// Initialize page state with defaults
initPageState({
  tickerItems: [],
  faqItems: [],
  faqTags: [],
  sections: {},
  landingLayout: {
    order: [],
    structure: [],
    hidden: {},
    widths: {},
    gridCols: 1,
    fullWidth: false
  },
  sectionIds: {},
  sectionMeta: {}
});

onMounted(async () => {
  if (isTemplateBuilder.value) {
    api.setTemplateBuilderContext(props.templateBuilderContext);
    window.addEventListener("fstvlpress-template-snippets-updated", handleTemplateSnippetsUpdated);
  } else {
    api.clearTemplateBuilderContext();
  }

  await loadPage();
  if (shouldLoadEditableDesignAfterPageLoad()) {
    // Always refresh design state for template builders:
    // - page templates: load template-scoped current design
    // - section/container templates: load global design
    // Locked page instances also load the linked template-scoped current design.
    await loadDesignSettings();
  }
  if (state.canAdminGeneral) {
    await loadTodoTagOptions();
  }
  await nextTick();
  setupHeroOverlayResizeObserver();
  measureHeroOverlayMetrics();
  window.addEventListener('scroll', handleParallaxScroll, { passive: true });
  window.addEventListener('resize', handleViewportResize, { passive: true });
  handleParallaxScroll();
});

onUnmounted(() => {
  window.removeEventListener('scroll', handleParallaxScroll);
  window.removeEventListener('resize', handleViewportResize);
  disconnectHeroOverlayResizeObserver();
  clearHeaderAutosaveStatusTimer();
  commitHeaderMediaAdjustPatch();
  restorePageDesignOverrides();
  setCurrentPageStatusMeta(null);
  setPageTemplateStyleContext(null);
  if (hasAppliedTemplateEffectiveDesign.value && state.canContent && !isTemplateBuilder.value) {
    hasAppliedTemplateEffectiveDesign.value = false;
    void loadDesignSettings();
  }
  if (isTemplateBuilder.value) {
    window.removeEventListener("fstvlpress-template-snippets-updated", handleTemplateSnippetsUpdated);
    removeTemplateSnippetStyleElement();
    api.clearTemplateBuilderContext();
    if (templateBuilderKind.value === "page" && state.canDesign) {
      void loadDesignSettings();
    }
  }
});

watch(
  () => [
    hasHeaderContent.value ? "1" : "0",
    headerEnabled.value ? "1" : "0",
    String(header.overlayImage || ""),
    overlayParallaxEnabled.value ? "1" : "0",
    overlayParallaxDirection.value,
    Array.isArray(header.enabledFields) ? header.enabledFields.join("|") : "",
  ],
  async () => {
    await nextTick();
    setupHeroOverlayResizeObserver();
    measureHeroOverlayMetrics();
  }
);

watch(
  [() => pageSlug.value, () => state.lang, () => state.isAdmin, () => route.path, () => pageTitle.value],
  () => {
    applyPublicSeoHead();
  },
  { immediate: true }
);

watch(
  () => [
    route.query.focus_section_id,
    route.query.focus_header_id,
    pageSlug.value,
    loading.value ? "1" : "0",
    state.isAdmin ? "1" : "0",
    Object.values(state.sectionIds || {}).map((id) => String(id || "")).join("|"),
    String(header.headerId || ""),
  ],
  async () => {
    await focusAdminTargetFromQuery();
  },
  { immediate: true }
);

watch(
  () => [state.currentPageStatus, state.currentPageEffectiveStatus, state.currentPageIsVisible],
  () => {
    applyCurrentPageVisibilityStateFromStore();
  }
);

watch(
  () => headerAdminActiveTab.value,
  async (tab, prevTab) => {
    if (tab === "history") {
      await loadHeaderHistory();
    }
    if (tab === "content") {
      syncHeaderCtaDraftFromHeader();
    }
    if (prevTab === "history" && tab !== "history") {
      resetHeaderHistorySelectionAndPreview();
    }
  }
);

watch(
  () => headerRevisionSignature.value,
  async (next, prev) => {
    if (!next || next === prev) return;
    if (headerAdminActiveTab.value !== "history" || !header.headerId) return;
    if (headerHistoryLoading.value) return;
    await loadHeaderHistory();
  }
);

// Watch for slug changes (dynamic routing)
watch(() => pageSlug.value, async (newSlug, oldSlug) => {
  if (newSlug !== oldSlug) {
    setPageSlug(newSlug);
    setCurrentPageStatusMeta(null);
    restorePageDesignOverrides();
    setPageTemplateStyleContext(null);
    // Reset state for new page
    state.sectionIds = {};
    state.sectionMeta = {};
    state.sections = {};
    templateBuilderCanvasPayload.value = null;
    state.landingLayout = { order: [], structure: [], hidden: {}, widths: {}, gridCols: 1, fullWidth: false, deviceVisibility: {}, sectionBgPinnedStartKey: '', sectionBgPinnedEndKey: '' };
    headerEnabled.value = false;
    resetHeader();
    isPageNotFound.value = false;
    notFoundStatusCode.value = 404;
    isPageVisible.value = true;
    isPageUnderConstruction.value = false;
    isBlogGeneratedPage.value = false;
    currentPageMeta.value = null;
    error.value = null;
    isCreatingPage.value = false;
    isCreatingRedirect.value = false;
    createPageError.value = "";
    createRedirectError.value = "";
    createPageForm.title = { de: "", en: "" };
    createPageForm.inMenu = false;
    createPageForm.templatePath = "";
    createRedirectForm.targetPath = "";
    createRedirectForm.statusCode = 301;
    pageCreationRouteKind.value = "static_route";
    missingPageAction.value = "page";
    redirectTargetPages.value = [];
    redirectTargetPagesLoading.value = false;
    
    await loadPage();
    if (shouldLoadEditableDesignAfterPageLoad()) {
      await loadDesignSettings();
    }
    if (state.canAdminGeneral) {
      await loadTodoTagOptions();
    }
  }
});

watch(
  () => buildTemplateBuilderLayoutSignature(),
  (nextSignature, previousSignature) => {
    if (!nextSignature || nextSignature === previousSignature) return;
    syncTemplateBuilderCanvasLayoutFromState();
  },
  { flush: "sync" }
);

watch(
  () => buildTemplateBuilderSectionDataSignature(),
  (nextSignature, previousSignature) => {
    if (!nextSignature || nextSignature === previousSignature) return;
    syncTemplateBuilderCanvasSectionsFromState();
  },
  { flush: "post" }
);

watch(
  () => props.templatePreviewPayload,
  (nextPayload, prevPayload) => {
    if (!isTemplateBuilder.value || templateBuilderKind.value !== "page") return;
    const hasNext = isPreviewObject(nextPayload);
    const hadPrev = isPreviewObject(prevPayload);
    if (hasNext) {
      applyTemplatePreviewPayloadToCanvas(nextPayload);
      return;
    }
    if (!hasNext && hadPrev) {
      restoreTemplatePreviewDesignState();
      void restoreTemplateBuilderCanvasAfterPreview();
    }
  }
);

watch(
  () => state.isAdmin,
  async (isAdmin, wasAdmin) => {
    // If admin auth becomes available, ensure we hydrate once with private API.
    // `lastLoadUsedPrivatePageApi` can still be null while the first load is in-flight,
    // so we must not skip in that state; `loadPage` will queue a follow-up reload.
    if (!isAdmin || wasAdmin === isAdmin) return;
    if (lastLoadUsedPrivatePageApi.value === true) return;
    await loadPage();
  }
);

watch(
  () => state.canAdminGeneral,
  async (canAdminGeneral, wasAdminGeneral) => {
    if (canAdminGeneral && !wasAdminGeneral) {
      await loadTodoTagOptions();
    }
  }
);

watch(
  () => createPageForm.templatePath,
  () => {
    applySelectedStaticTemplateTitle({ force: true });
  }
);

watch(
  () => missingPageAction.value,
  async (nextAction) => {
    if (nextAction !== "redirect") return;
    if (!isPageNotFound.value || !state.isAdmin) return;
    if (redirectTargetPages.value.length || redirectTargetPagesLoading.value) return;
    await loadRedirectTargetPages();
  }
);

watch(
  () => createRedirectForm.statusCode,
  (nextCode) => {
    if (Number(nextCode) === 410) {
      createRedirectForm.targetPath = "";
    }
  }
);

watch(
  () => [redirectTargetPageOptions.value, missingPageSourcePath.value],
  () => {
    const validPaths = new Set(redirectTargetPageOptions.value.map((page) => pagePathFromSlug(page?.slug)));
    if (createRedirectForm.targetPath && !validPaths.has(createRedirectForm.targetPath)) {
      createRedirectForm.targetPath = "";
    }
  }
);

watch(
  defaultHeaderTodoTagId,
  (tagId) => {
    if (!headerTodoTagOptions.value.some((tag) => tag.id === headerNewTodoTag.value)) {
      headerNewTodoTag.value = tagId;
    }
    headerTodoDraft.value = normalizeTodoList(headerTodoDraft.value, { defaultTagId: tagId });
  },
  { immediate: true }
);

async function loadTodoTagOptions() {
  if (!state.canAdminGeneral) {
    headerTodoTagOptions.value = normalizeTodoTags([]);
    return;
  }
  try {
    const config = await api.getAdminDevopsConfig();
    headerTodoTagOptions.value = normalizeTodoTags(config?.todo_tags || []);
  } catch (err) {
    console.error("Failed to load header todo tags:", err);
    headerTodoTagOptions.value = normalizeTodoTags([]);
  }
}

// -------------------------
// Expose
// -------------------------

defineExpose({
  loadPage,
  pageSlug,
  header,
  hasSections,
  hasHeader,
  hasHeaderContent
});
</script>

<style scoped>
.hero {
  position: relative;
  overflow: hidden;
}

.hero-bg {
  min-height: var(--hero-height, 400px);
  position: relative;
}

.hero-bg--video {
  background: #000;
  overflow: hidden;
}

.hero-bg-image {
  position: absolute;
  inset: 0;
  z-index: var(--hero-z-background, 0);
  pointer-events: none;
}

.hero-video {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: var(--hero-z-background, 0);
}

.hero--parallax .hero-bg {
  background-attachment: fixed;
}

.hero-overlay {
  min-height: var(--hero-height, 400px);
  background: linear-gradient(to bottom, rgba(15, 23, 42, 0.22), rgba(15, 23, 42, 0.74));
  display: flex;
  align-items: flex-end;
  position: relative;
  z-index: 1;
}

.hero-no-bg {
  position: relative;
}

.header-admin-panel {
  display: grid;
  gap: 10px;
}

.header-design-slider-panel {
  display: grid;
  width: 66.666%;
  max-width: 100%;
  border-radius: 8px;
  background: #fff;
}

.header-design-slider-summary {
  font-weight: 600;
  color: var(--admin-text, #374151);
  cursor: pointer;
  padding: 0.75rem;
  background: #fff;
  border-radius: 8px;
  list-style: none;
}

.header-design-slider-summary::-webkit-details-marker {
  display: none;
}

.header-design-slider-summary::before {
  content: "▸ ";
  color: var(--admin-text-muted, #9ca3af);
}

.header-design-slider-panel[open] > .header-design-slider-summary::before {
  content: "▾ ";
}

.header-design-slider-content {
  display: grid;
  gap: 10px;
  padding: 1rem;
  margin-top: -4px;
  border-radius: 0 0 8px 8px;
  background: #fff;
}

.header-design-slider-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  min-width: 0;
}

.header-design-slider-field {
  display: grid;
  align-items: start;
  gap: 6px;
  min-width: 0;
}

.header-design-slider-field__label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  color: var(--admin-text);
}

.header-blur-mode-toggle {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 3px;
  border: 0;
  border-radius: 999px;
  background: color-mix(in srgb, var(--admin-surface, #fff) 85%, rgba(148, 163, 184, 0.12));
  max-width: max-content;
}

.header-blur-mode-toggle__btn {
  appearance: none;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--admin-text-muted, #64748b);
  font-size: 12px;
  font-weight: 700;
  padding: 4px 10px;
  cursor: pointer;
  transition: background 0.16s ease, color 0.16s ease, box-shadow 0.16s ease;
}

.header-blur-mode-toggle__btn.active {
  background: var(--admin-accent, var(--accent, #4f46e5));
  color: #fff;
  box-shadow: none;
}

.header-design-slider-field__control {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  flex: 1 1 auto;
  min-width: 0;
}

.header-design-slider-field__control input[type="range"] {
  width: 100%;
}

@media (max-width: 820px) {
  .header-design-slider-panel {
    width: 100%;
  }

  .header-design-slider-row {
    grid-template-columns: minmax(0, 1fr);
  }
}

.header-design-slider-field__value {
  font-size: 12px;
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--admin-text-muted);
  min-width: 48px;
  text-align: right;
}

.header-blur-slider-transition-enter-active,
.header-blur-slider-transition-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.header-blur-slider-transition-enter-from,
.header-blur-slider-transition-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.header-admin-panel__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.header-admin-panel__hint {
  margin: 0;
  color: var(--admin-text-muted);
  font-size: 13px;
  line-height: 1.45;
}

.header-admin-panel__error {
  margin: 0;
  color: #b91c1c;
  font-size: 13px;
  line-height: 1.45;
}

.header-admin-panel__title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--admin-text-muted);
}

.header-template-share-check {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  font-size: 13px;
  font-weight: 700;
  color: var(--admin-text);
  cursor: pointer;
}

.header-template-share-check input {
  width: 16px;
  height: 16px;
  margin: 0;
}

.header-template-share-check:has(input:disabled) {
  cursor: default;
  opacity: 0.65;
}

.header-media-controls {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.header-media-card {
  display: grid;
  gap: 8px;
  border: 1px solid var(--admin-border);
  border-radius: 10px;
  padding: 10px;
  background: var(--admin-surface);
}

.header-media-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.header-media-card__title {
  font-size: 12px;
  font-weight: 700;
  color: var(--admin-text);
}

.header-media-card__status {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--admin-text-muted);
  background: rgba(148, 163, 184, 0.2);
  border-radius: 999px;
  padding: 2px 7px;
}

.header-media-card__focus {
  margin-top: 2px;
}

.header-cta-thumb {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
}

.header-cta-thumb__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--admin-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-cta-thumb__meta {
  font-size: 11px;
  color: var(--admin-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.header-cta-editor {
  display: grid;
  gap: 10px;
}

.header-cta-editor__lang-grid,
.header-cta-editor__meta-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.header-cta-editor__lang {
  display: grid;
  gap: 6px;
}

.header-cta-editor__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--admin-text-muted);
}

.header-cta-editor__field {
  width: 100%;
  border: 1px solid var(--admin-border);
  border-radius: 8px;
  background: var(--admin-surface);
  color: var(--admin-text);
  padding: 8px 10px;
  font-size: 13px;
  min-height: 36px;
}

.header-field-list {
  display: grid;
  gap: 8px;
}

.header-field-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--admin-border);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--admin-surface);
  color: var(--admin-text);
}

.header-field-row.muted {
  opacity: 0.55;
}

.header-field-row__drag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  color: var(--admin-text-muted);
  user-select: none;
  font-size: 14px;
  letter-spacing: -0.1em;
}

.header-field-row__drag:active {
  cursor: grabbing;
}

.header-field-row__label {
  min-width: 0;
  font-size: 13px;
}

.header-field-row input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--accent, #5b2fe3);
}

.header-field-row--ghost {
  opacity: 0.45;
}

.header-field-row--chosen {
  border-color: var(--accent, #5b2fe3);
}

.header-field-row--drag {
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.14);
}

.hero-empty-state {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
}

.hero-empty-content {
  text-align: center;
  padding: 40px 20px;
  max-width: 400px;
  text-wrap: balance;
}

.empty-card {
  border-radius: 16px;
  text-align: center;
  background: white;
  padding: 20px;
  text-wrap: balance;
}

.hero-empty-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text, #0f172a);
  margin: 0 0 12px;
}

.hero-empty-text {
  font-size: 14px;
  color: var(--muted, #64748b);
  line-height: 1.6;
  margin: 0 0 24px;
}

.hero-empty-btn {
  background: var(--accent, #4f46e5);
  color: #fff;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.hero-empty-btn:hover {
  filter: brightness(1.1);
  transform: translateY(-1px);
}

.hero-empty-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.hero-empty-btn--secondary {
  background: #fff;
  color: var(--text, #0f172a);
  border: 1px solid var(--border, #dbe3ef);
}

.hero-empty-btn--secondary:hover {
  background: #f8fafc;
  filter: none;
}

.page-create-inline {
  max-width: 520px;
  margin: 0 auto;
  display: grid;
  gap: 12px;
  text-align: left;
}

.page-create-inline__mode {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.page-create-inline__mode-btn {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #0f172a;
  border-radius: 8px;
  padding: 9px 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.page-create-inline__mode-btn:hover {
  background: #f8fafc;
}

.page-create-inline__mode-btn.active {
  border-color: #4f46e5;
  background: rgba(79, 70, 229, 0.08);
  color: #312e81;
}

.page-create-inline__slug {
  display: flex;
  align-items: baseline;
  gap: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
}

.page-create-inline__slug-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.page-create-inline__slug-value {
  color: #0f172a;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 13px;
}

.page-create-inline__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.page-create-inline__field {
  display: grid;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.page-create-inline__input {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 9px 10px;
  font-size: 14px;
  color: #0f172a;
  background: #fff;
}

.page-create-inline__input:focus {
  outline: 2px solid rgba(79, 70, 229, 0.24);
  outline-offset: 0;
  border-color: #818cf8;
}

.page-create-inline__checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #334155;
}

.page-create-inline__error {
  margin: 0;
  font-size: 13px;
  color: #b91c1c;
}

.page-create-inline__hint {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}

.page-create-inline__warning {
  margin: 0;
  font-size: 12px;
  color: #92400e;
}

@media (max-width: 640px) {
  .page-create-inline__mode {
    grid-template-columns: 1fr;
  }

  .page-create-inline__grid {
    grid-template-columns: 1fr;
  }
}

.page-template-style-lock-note {
  padding: 10px 0 0;
}

.page-template-style-lock-note .page-container {
  padding: 0;
}

.page-template-style-lock-note p {
  margin: 30px 0 0;
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1e3a8a;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
}

.page-edit-shortcut {
  padding: 28px 0 36px;
}

:global(.full-width) {
  width: 100%;
  max-width: none;
}

/* Full width mode non-section content (header, footer, hero) */
:global(.full-width .container) {
  width: 100%;
  max-width: none;
  padding-left: var(--outer-spacing-non-section, 0px);
  padding-right: var(--outer-spacing-non-section, 0px);
}

:global(.viewport-sim.full-width .container) {
  padding-left: var(--outer-spacing-non-section-desktop, var(--outer-spacing-non-section, 0px));
  padding-right: var(--outer-spacing-non-section-desktop, var(--outer-spacing-non-section, 0px));
}

/* section content */
:global(.full-width .page-container) {
  padding-left: var(--outer-spacing-section, 0px);
  padding-right: var(--outer-spacing-section, 0px);
}

.page-edit-shortcut .page-container {
  display: flex;
  justify-content: center;
}

.page-edit-shortcut__actions {
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.page-edit-shortcut__btn {
  background: #0f172a;
  color: #fff;
  border: 1px solid #0f172a;
  border-radius: 999px;
  padding: 11px 22px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.01em;
  z-index: 10;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease;
}

.page-edit-shortcut__btn:hover:not(:disabled) {
  background: var(--page-edit-shortcut-hover-bg, #0f172a);
  border-color: var(--page-edit-shortcut-hover-bg, #0f172a);
  color: var(--page-edit-shortcut-hover-color, #ffffff);
}

.page-edit-shortcut__btn:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.page-edit-shortcut__btn--secondary {
  background: #fff;
  color: #0f172a;
  border: 1px solid #cbd5e1;
}

.page-edit-shortcut__btn--edit:hover:not(:disabled) {
  background: var(--page-edit-shortcut-edit-hover-bg, #ffffff);
  border-color: var(--page-edit-shortcut-edit-hover-color, #0f172a);
  color: var(--page-edit-shortcut-edit-hover-color, #0f172a);
  box-shadow: inset 0 0 0 1px var(--page-edit-shortcut-edit-hover-color, #0f172a);
}

.page-edit-shortcut__icon {
  font-size: 0.95em;
}

.page-edit-shortcut__status {
  flex-basis: 100%;
  margin: 2px 0 0;
  color: #475569;
  font-size: 13px;
  font-weight: 600;
  text-align: center;
}

.page-edit-shortcut__status--success {
  color: #166534;
}

.page-edit-shortcut__status--error {
  color: #b91c1c;
}

.generated-page-sync-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(15, 23, 42, 0.45);
}

.generated-page-sync-dialog {
  width: min(560px, 100%);
  max-height: min(720px, calc(100vh - 2rem));
  overflow: auto;
  border-radius: 8px;
  background: #ffffff;
  padding: 1rem;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.24);
}

.generated-page-sync-dialog h3 {
  margin: 0 0 0.8rem;
  color: #111827;
  font-size: 1.05rem;
  line-height: 1.25;
}

.generated-page-sync-options {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.generated-page-sync-option {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.65rem;
  align-items: flex-start;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 0.75rem;
  background: #ffffff;
  cursor: pointer;
}

.generated-page-sync-option.is-selected {
  border-color: #2563eb;
  background: #eff6ff;
}

.generated-page-sync-option--destructive {
  border-color: #fecaca;
}

.generated-page-sync-option--destructive.is-selected {
  border-color: #dc2626;
  background: #fef2f2;
}

.generated-page-sync-option--destructive strong {
  color: #991b1b;
}

.generated-page-sync-option input {
  margin-top: 0.2rem;
}

.generated-page-sync-option strong,
.generated-page-sync-option small {
  display: block;
}

.generated-page-sync-option strong {
  color: #111827;
  font-size: 0.9rem;
}

.generated-page-sync-option small {
  margin-top: 0.2rem;
  color: #4b5563;
  font-size: 0.78rem;
  line-height: 1.35;
}

.generated-page-sync-dialog__warning {
  margin: 0.75rem 0 0;
  border: 1px solid #fde68a;
  border-radius: 8px;
  padding: 0.65rem 0.75rem;
  background: #fffbeb;
  color: #92400e;
  font-size: 0.82rem;
  line-height: 1.4;
}

.generated-page-sync-dialog__actions {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1rem;
}

.generated-page-sync-dialog__button {
  min-width: 118px;
  min-height: 42px;
  border-radius: 999px;
  padding: 0.65rem 1rem;
  font-size: 0.9rem;
  font-weight: 700;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #0f172a;
  cursor: pointer;
  transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease, opacity 0.16s ease;
}

.generated-page-sync-dialog__button--primary {
  background: #0f172a;
  color: #ffffff;
}

.generated-page-sync-dialog__button--secondary {
  background: #ffffff;
  color: #0f172a;
}

.generated-page-sync-dialog__button:hover:not(:disabled) {
  background: #1e293b;
  border-color: #1e293b;
  color: #ffffff;
}

.generated-page-sync-dialog__button:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.hero-inner {
  padding: var(--header-inner, 44px) 0 calc(var(--header-inner, 44px) * 0.55);
  position: relative;
}

.hero-layout {
  display: flex;
  position: relative;
  min-height: 100px;
}

.hero-copy {
  flex: 1;
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: var(--hero-content-align, flex-start);
  text-align: var(--hero-text-align, left);
  position: relative;
}

.hero-copy :deep(.hero-title) {
  color: var(--hero-title-color, inherit);
  position: relative;
  z-index: var(--hero-z-title, 5);
}

.hero-copy :deep(.hero-subtitle) {
  color: var(--hero-subtitle-color, rgba(255, 255, 255, 0.92));
  position: relative;
  z-index: var(--hero-z-subtitle, 4);
}

.hero--no-background-image .hero-copy :deep(.hero-title) {
  color: var(--hero-title-color, var(--hero-page-background-contrast-color, var(--primary-color, #0b1220)));
}

.hero--no-background-image .hero-copy :deep(.hero-subtitle) {
  color: var(--hero-subtitle-color, var(--hero-page-background-contrast-color, var(--primary-color, #0b1220)));
}

/* Overlay image: positioned relative to .slot (EditableBgImage) or .hero-no-bg,
   above background/gradient (z-index: 1) but under title text (z-index: 2) */
.hero-media {
  position: absolute;
  z-index: var(--hero-z-overlay, 2);
  width: var(--hero-overlay-size, 150px);
  --_pad-y: 24px;
  --_pad-x: var(--outer-spacing-non-section, 0px);
  --parallax-offset: 0px;
  --overlay-path-progress: 0;
  --overlay-path-y: 0px;
  --overlay-path-width: var(--hero-overlay-size, 150px);
}

.hero-media :deep(img) {
  width: 100%;
  height: auto;
  display: block;
}

.hero-media :deep(.transformed-image) {
  width: 100%;
  height: auto;
}

.hero-media :deep(.transformed-image__viewport) {
  height: auto;
}

.hero-media :deep(.transformed-image__viewport > img) {
  height: auto;
  object-fit: contain;
}

/* Special overlay scroll path: bottom-left -> top-center -> bottom-right */
.hero-media--scroll-path {
  will-change: left, bottom;
  top: auto;
  right: auto;
  left: max(
    var(--_pad-x),
    min(
      calc(
        var(--_pad-x) +
        (
          100% - (var(--_pad-x) * 2) - var(--overlay-path-width, var(--hero-overlay-size, 150px))
        ) * var(--overlay-path-progress, 0)
      ),
      calc(100% - var(--_pad-x) - var(--overlay-path-width, var(--hero-overlay-size, 150px)))
    )
  );
  bottom: calc(var(--_pad-y) + var(--overlay-path-y, 0px));
  transform: translateY(0);
}

/* Position variants with symmetric vertical padding - include parallax offset */
.hero-media--top-left       { top: var(--_pad-y); left: var(--_pad-x); transform: translateY(var(--parallax-offset)); }
.hero-media--top-center     { top: var(--_pad-y); left: 50%; transform: translateX(-50%) translateY(var(--parallax-offset)); }
.hero-media--top-right      { top: var(--_pad-y); right: var(--_pad-x); transform: translateY(var(--parallax-offset)); }
.hero-media--center-left    { top: 50%; left: var(--_pad-x); transform: translateY(calc(-50% + var(--parallax-offset))); }
.hero-media--center         { top: 50%; left: 50%; transform: translate(-50%, calc(-50% + var(--parallax-offset))); }
.hero-media--center-right   { top: 50%; right: var(--_pad-x); transform: translateY(calc(-50% + var(--parallax-offset))); }
.hero-media--bottom-left    { bottom: var(--_pad-y); left: var(--_pad-x); transform: translateY(var(--parallax-offset)); }
.hero-media--bottom-center  { bottom: var(--_pad-y); left: 50%; transform: translateX(-50%) translateY(var(--parallax-offset)); }
.hero-media--bottom-right   { bottom: var(--_pad-y); right: var(--_pad-x); transform: translateY(var(--parallax-offset)); }

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

.section-admin-tabs__history-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 2px;
}

.section-admin-tabs__history-empty {
  margin: 0;
  font-size: 12px;
  color: var(--admin-text-muted);
}

.section-admin-tabs__notes {
  display: grid;
  gap: 10px;
}

.notes-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--admin-text-muted);
}

.notes-textarea {
  width: 100%;
  min-height: 100px;
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
}

.todo-input {
  min-width: 0;
  border: 1px solid var(--admin-border);
  border-radius: 8px;
  background: var(--admin-surface);
  color: var(--admin-text);
  padding: 8px 10px;
}

.todo-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-items: start;
}

.todo-group {
  display: grid;
  gap: 8px;
}

.todo-group-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--admin-text-muted);
}

.todo-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  gap: 8px;
  align-items: center;
  min-height: 34px;
  border: 1px solid var(--admin-border);
  border-radius: 8px;
  background: var(--admin-surface);
  padding: 6px 8px;
}

.todo-main {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.todo-text {
  min-width: 0;
  color: var(--admin-text);
  font-size: 13px;
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

.todo-author.author-badge {
  width: 28px;
  height: 28px;
}

.todo-author.author-badge :deep(.author-icon) {
  font-size: 16px;
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

.todo-empty {
  margin: 0;
  font-size: 12px;
  color: var(--admin-text-muted);
}

.hero-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
  position: relative;
  z-index: var(--hero-z-buttons, 3);
}

/* Separator */
.hero-pinned-ticker {
  width: 100%;
}

.hero-pinned-ticker :deep(.ticker) {
  border-radius: 0;
}

.hero-separator {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 3;
  pointer-events: none;
}

.hero-separator--inward-shadow {
  height: 12px;
  box-shadow: inset 0 -8px 12px -4px rgba(0, 0, 0, 0.15);
}

.hero-separator--border {
  height: 0;
  border-bottom-width: max(1px, var(--section-border-width, 1px));
  border-bottom-style: var(--section-border-style, solid);
  border-bottom-color: var(--section-border-color, #0b1220);
}

@media (max-width: 860px) {
  .hero-layout {
    flex-direction: column;
  }

  .todo-add {
    grid-template-columns: minmax(0, 1fr);
  }

  .todo-list {
    grid-template-columns: 1fr;
  }

  .todo-item {
    grid-template-columns: auto minmax(0, 1fr) auto auto;
    min-height: 40px;
    align-items: start;
  }
}

/* Loading overlay */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  color: #fff;
  gap: 16px;
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(255, 255, 255, 0.2);
  border-top-color: var(--accent, #5b2fe3);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Error overlay */
.error-overlay {
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

.error-card {
  background: #fff;
  border-radius: 16px;
  padding: 40px;
  text-align: center;
  box-shadow: 0 8px 32px rgba(15, 23, 42, 0.1);
}

.error-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.error-card h2 {
  margin: 0 0 12px;
  color: var(--text);
}

.error-card p {
  color: var(--muted);
  margin: 0 0 24px;
}

.under-construction-overlay {
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

.under-construction-card {
  background: #fff;
  border-radius: 16px;
  padding: 40px;
  text-align: center;
  box-shadow: 0 8px 32px rgba(15, 23, 42, 0.1);
  max-width: 640px;
}

.under-construction-title {
  margin: 0 0 12px;
  color: var(--text);
  font-size: clamp(24px, 3vw, 34px);
  line-height: 1.2;
}

.under-construction-message {
  color: var(--muted);
  margin: 0 0 24px;
  line-height: 1.5;
}

.under-construction-actions {
  display: flex;
  justify-content: center;
}

/* Empty page state */
.empty-page {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}
</style>
