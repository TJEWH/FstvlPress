<template>
  <aside id="section-panel" class="wrap" :class="[`corner-${panelCorner}`, { open }]" v-if="state.isAdmin">
    <div class="panel" role="dialog" aria-label="Sections Manager">
      <div class="head" @click="toggleOpen" role="button" tabindex="0">
        <div class="title">Sections</div>

        <div class="head-actions" @click.stop>
          <span v-if="!open" class="chev" aria-hidden="true">▴</span>
          <template v-else>
            <button
              class="head-toggle-btn"
              :class="{ active: showDeviceToggles }"
              type="button"
              :aria-pressed="showDeviceToggles"
              :title="showDeviceToggles ? 'Hide device toggles' : 'Show device toggles'"
              :aria-label="showDeviceToggles ? 'Hide device toggles' : 'Show device toggles'"
              @click="showDeviceToggles = !showDeviceToggles"
            >
              <font-awesome-icon :icon="faMobileScreenButton" />
            </button>
            <button class="icon-btn" type="button" @click="open = false" aria-label="Close">
              <font-awesome-icon :icon="faXmark" />
            </button>
          </template>
        </div>
      </div>

      <div class="body" aria-hidden="false">
        <!-- Manage buttons row -->
        <div class="manage-row">
          <button
            v-if="allowHeaderManagement"
            class="manage-btn"
            type="button"
            :disabled="isPreviewLocked"
            @click="openHeaderDialog()"
          >
            add Header
          </button>
          <button
            class="manage-btn"
            type="button"
            :disabled="isPreviewLocked"
            @click="openSectionsDialog()"
          >
            add Section
          </button>
        </div>

                <!-- Header visibility toggle -->
        <div v-if="showHeaderToggle" class="header-row" :class="{ 'header-hidden': !hasHeader }">
          <div class="item-left">
            <span class="section-icon"><font-awesome-icon :icon="faImage" /></span>
            <span class="name">Header</span>
          </div>
          <div class="item-actions">
            <label class="visibility-check" @click.stop>
              <input
                type="checkbox"
                :checked="hasHeader"
                :disabled="isPreviewLocked"
                @change="onToggleHeader"
              />
            </label>
          </div>
        </div>

        <!-- Section list -->
        <div class="list" role="list">
          <!-- Fixed sections (like ticker) - only toggle visibility -->
          <div v-for="section in fixedSections" :key="section.key" class="item fixed" :class="{ hidden: isHidden(section.key) }">
            <div class="item-left">
              <span class="pin-handle" aria-hidden="true">—</span>
              <span class="section-icon"><font-awesome-icon :icon="getSectionIcon(section.key)" /></span>
              <span class="section-name">{{ getSectionName(section.key) }}</span>
            </div>
            <div class="item-actions">
              <button 
                v-if="isHidden(section.key)"
                class="remove-btn"
                type="button"
                title="Remove from page"
                :disabled="isPreviewLocked || removingFromPage"
                @pointerdown.stop
                @mousedown.stop
                @click.stop.prevent="removeFromPage(section.key)"
              >
                <font-awesome-icon :icon="faXmark" />
              </button>
              <label class="visibility-check" @click.stop>
                <input
                  type="checkbox"
                  :checked="!isHidden(section.key)"
                  :disabled="isPreviewLocked || !state.isAdmin"
                  @change="toggleHidden(section.key)"
                />
              </label>
            </div>
          </div>

          <!-- Draggable sections -->
          <draggable
            v-model="draggableEntryDraft"
            item-key="id"
            handle=".drag-handle"
            ghost-class="drag-ghost"
            :animation="150"
            :disabled="isPreviewLocked"
            :move="onDragMove"
            @start="onDragStart"
            @end="onDragEnd"
            class="list-inner"
          >
            <template #item="{ element: entry }">
              <div
                class="item"
                :data-entry-id="entry.id"
                :class="{
                  hidden: isEntryHidden(entry),
                  'hidden-current-view': isEntryHiddenForCurrentView(entry),
                  'container-item': entry.type === 'container',
                  'drag-link-target': isLinkHover(entry),
                  'drop-split-visible': isDropSplitVisible(entry),
                }"
              >
                <div class="item-left">
                  <span v-if="!isPreviewLocked && !isEntryHidden(entry)" class="drag-handle" title="Drag to reorder">⋮⋮</span>
                  <span class="section-icon"><font-awesome-icon :icon="getEntryIcon(entry)" /></span>
                  <div class="entry-labels">
                    <span class="section-name">{{ getEntryName(entry) }}</span>
                    <div v-if="entry.type === 'container'" class="container-members">
                      <span
                        v-for="memberKey in entry.members"
                        :key="`${entry.id}_${memberKey}`"
                        class="container-member-chip"
                      >
                        {{ getSectionName(memberKey) }}
                      </span>
                    </div>
                  </div>
                </div>

                <div class="item-right">
                  <div v-if="!isEntryHidden(entry)" class="width-ratio" @click.stop>
                    <template v-if="entry.type === 'container'">
                      <button
                        v-if="entry.type === 'container' && !isContainerStructureLocked(entry)"
                        class="container-edit-btn"
                        type="button"
                        title="Edit container"
                        :disabled="isPreviewLocked"
                        @click.stop="openContainerEditor(entry)"
                      >
                        <font-awesome-icon :icon="faPenToSquare" />
                      </button>
                    </template>
                    <template v-else>
                      <select
                        class="ratio-select"
                        :value="getWidthN(entry.key)"
                        :disabled="isPreviewLocked"
                        @change="onWidthNChange(entry.key, +$event.target.value)"
                      >
                        <option v-for="n in getMaxN(entry.key)" :key="n" :value="n">{{ n }}</option>
                      </select>
                      <span class="ratio-slash">/</span>
                      <select
                        class="ratio-select"
                        :value="getWidthD(entry.key)"
                        :disabled="isPreviewLocked"
                        @change="onWidthDChange(entry.key, +$event.target.value)"
                      >
                        <option v-for="d in 5" :key="d" :value="d">{{ d }}</option>
                      </select>
                    </template>
                  </div>

                  <div v-if="showDeviceToggles && !isEntryHidden(entry)" class="device-toggles" @click.stop>
                    <button
                      type="button"
                      class="device-btn"
                      :class="{ active: getEntryDeviceVisibility(entry, 'mobile') }"
                      :disabled="isPreviewLocked"
                      @click="toggleEntryDevice(entry, 'mobile')"
                      title="Show on mobile"
                    >
                      <font-awesome-icon :icon="faMobileScreenButton" />
                    </button>
                    <button
                      type="button"
                      class="device-btn"
                      :class="{ active: getEntryDeviceVisibility(entry, 'tablet') }"
                      :disabled="isPreviewLocked"
                      @click="toggleEntryDevice(entry, 'tablet')"
                      title="Show on tablet"
                    >
                      <font-awesome-icon :icon="faTabletScreenButton" />
                    </button>
                    <button
                      type="button"
                      class="device-btn"
                      :class="{ active: getEntryDeviceVisibility(entry, 'desktop') }"
                      :disabled="isPreviewLocked"
                      @click="toggleEntryDevice(entry, 'desktop')"
                      title="Show on desktop"
                    >
                      <font-awesome-icon :icon="faDesktop" />
                    </button>
                  </div>

                  <div class="item-actions">
                    <button 
                      v-if="isEntryHidden(entry) && canRemoveEntryFromPage(entry)"
                      class="remove-btn"
                      type="button"
                      title="Remove from page"
                      :disabled="isPreviewLocked || removingFromPage"
                      @pointerdown.stop
                      @mousedown.stop
                      @click.stop.prevent="removeEntryFromPage(entry)"
                    >
                      <font-awesome-icon :icon="faXmark" />
                    </button>
                    <label class="visibility-check" @click.stop>
                      <input
                        type="checkbox"
                        :checked="!isEntryHidden(entry)"
                        :disabled="isPreviewLocked || !state.isAdmin"
                        @change="toggleEntryHidden(entry)"
                      />
                    </label>
                  </div>
                </div>
              </div>
            </template>
          </draggable>
          <div
            v-if="showResolveDropZone"
            class="resolve-drop-zone"
            :class="{ active: resolveDropActive }"
            @dragover.prevent.stop="onResolveDragOver"
            @dragleave.stop="onResolveDragLeave"
            @drop.prevent.stop="onResolveDrop"
          >
            Drop to resolve this container
          </div>
        </div>

        <div class="empty" v-if="allSections.length === 0 && !showAddSection">
          No sections found for this page.
        </div>
        
        <div class="empty add-hint" v-if="allSections.length === 0 && showAddSection">
          No sections yet. Click "Add Section" to get started.
        </div>

        <!-- Background pattern button at the bottom -->
        <button
          v-if="visibleSections.length > 0 && state.canDesign && !props.designOverridesLocked && !isContainerTemplateBuilderContext"
          class="pins-bottom-btn"
          type="button"
          :disabled="isPreviewLocked"
          @click="openPinDialog"
        >
          <span class="pins-bottom-icon"><font-awesome-icon :icon="faPaintbrush" /></span>
          <span>Background Pattern</span>
          <span v-if="state.design.sectionBgPattern !== 'none'" class="pins-bottom-badge">{{ state.design.sectionBgPattern === 'alternating' ? 'Alt' : 'Grad' }}</span>
        </button>

        <div class="panel-bottom-control">
          <PanelPositionControl
            v-model="panelCorner"
            aria-label="Choose section panel position"
            fallback="bottom-left"
          />
        </div>
      </div>
    </div>
    
    <!-- Gradient Pin Dialog -->
    <Teleport to="body">
      <div v-if="showPinDialog" class="dialog-overlay" @click.self="showPinDialog = false">
        <div class="dialog pin-dialog">
          <div class="dialog-header">
            <h3>Section Background Pattern</h3>
            <button class="icon-btn" type="button" @click="showPinDialog = false" aria-label="Close">
              <font-awesome-icon :icon="faXmark" />
            </button>
          </div>
          <div class="dialog-body">
            <!-- Pattern selector -->
            <div class="pin-field">
              <label class="pin-field-label">Pattern</label>
              <select class="pin-select" :value="state.design.sectionBgPattern" @change="updateDesignSetting('sectionBgPattern', $event.target.value)">
                <option value="none">None (uniform)</option>
                <option value="alternating">Alternating</option>
                <option value="gradient">Gradient</option>
                <option value="gradient_shuffled">Gradient Shuffled</option>
                <option value="alpha_gradient">Alpha Gradient</option>
                <option value="alpha_gradient_shuffled">Alpha Gradient Shuffled</option>
              </select>
            </div>

            <!-- Color pickers (for color-based patterns) -->
            <template v-if="isColorGradient">
              <div class="pin-field-row">
                <div class="pin-field">
                  <label class="pin-field-label">{{ state.design.sectionBgPattern === 'alternating' ? 'Even' : 'Start' }} Color</label>
                  <div class="pin-color-input">
                    <VueColorPicker
                      :model-value="state.design.sectionBgColor1 || '#ffffff'"
                      fallback-color="#ffffff"
                      :size="32"
                      @update:model-value="updateDesignSetting('sectionBgColor1', $event)"
                    />
                    <input type="text" :value="state.design.sectionBgColor1 || ''" class="pin-color-text" @change="updateDesignSetting('sectionBgColor1', $event.target.value)" />
                  </div>
                </div>
                <div class="pin-field">
                  <label class="pin-field-label">{{ state.design.sectionBgPattern === 'alternating' ? 'Odd' : 'End' }} Color</label>
                  <div class="pin-color-input">
                    <VueColorPicker
                      :model-value="state.design.sectionBgColor2 || '#f0f0f0'"
                      fallback-color="#f0f0f0"
                      :size="32"
                      @update:model-value="updateDesignSetting('sectionBgColor2', $event)"
                    />
                    <input type="text" :value="state.design.sectionBgColor2 || ''" class="pin-color-text" @change="updateDesignSetting('sectionBgColor2', $event.target.value)" />
                  </div>
                </div>
              </div>
            </template>

            <!-- Opacity sliders (for alpha patterns) -->
            <template v-if="isAlphaGradient">
              <div class="pin-field-row">
                <div class="pin-field">
                  <label class="pin-field-label">Start Opacity</label>
                  <div class="pin-range">
                    <input type="range" min="0" max="1" step="0.05" :value="state.design.sectionBgOpacity1 ?? 1" @input="updateDesignSetting('sectionBgOpacity1', parseFloat($event.target.value))" />
                    <span class="pin-range-val">{{ (state.design.sectionBgOpacity1 ?? 1).toFixed(2) }}</span>
                  </div>
                </div>
                <div class="pin-field">
                  <label class="pin-field-label">End Opacity</label>
                  <div class="pin-range">
                    <input type="range" min="0" max="1" step="0.05" :value="state.design.sectionBgOpacity2 ?? 0.3" @input="updateDesignSetting('sectionBgOpacity2', parseFloat($event.target.value))" />
                    <span class="pin-range-val">{{ (state.design.sectionBgOpacity2 ?? 0.3).toFixed(2) }}</span>
                  </div>
                </div>
              </div>
            </template>

            <!-- Section pins (for gradient patterns) -->
            <template v-if="isGradientPattern && visibleSections.length > 0">
              <div class="pin-divider"></div>
              <p class="pin-hint">
                <template v-if="!isShuffledPattern">Pin start/end sections. Sections before start keep the start color; after end keep the end color.</template>
                <template v-else>Pin start/end sections. They get fixed colors; the rest are shuffled.</template>
              </p>

              <div class="pin-section-list">
                <div class="pin-section-header">
                  <span class="pin-col-color"></span>
                  <span class="pin-col-name">Section</span>
                  <span class="pin-col-radio">Start</span>
                  <span class="pin-col-radio">End</span>
                </div>

                <div class="pin-section-row">
                  <span class="pin-col-color"></span>
                  <span class="pin-col-name pin-none-label">— None —</span>
                  <span class="pin-col-radio">
                    <input type="radio" name="pin-start" :checked="!state.landingLayout?.sectionBgPinnedStartKey" @change="setPin('start', '')" />
                  </span>
                  <span class="pin-col-radio">
                    <input type="radio" name="pin-end" :checked="!state.landingLayout?.sectionBgPinnedEndKey" @change="setPin('end', '')" />
                  </span>
                </div>

                <div v-for="(s, idx) in visibleSections" :key="s.key" class="pin-section-row">
                  <span class="pin-col-color">
                    <span class="pin-color-dot" :style="{ background: previewColors[idx] || '#eee' }"></span>
                  </span>
                  <span class="pin-col-name">{{ s.label }}</span>
                  <span class="pin-col-radio">
                    <input type="radio" name="pin-start" :checked="state.landingLayout?.sectionBgPinnedStartKey === s.key" @change="setPin('start', s.key)" />
                  </span>
                  <span class="pin-col-radio">
                    <input type="radio" name="pin-end" :checked="state.landingLayout?.sectionBgPinnedEndKey === s.key" @change="setPin('end', s.key)" />
                  </span>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Add Section Dialog -->
    <Teleport to="body">
      <div v-if="showAddDialog" class="dialog-overlay" @click.self="showAddDialog = false">
        <div class="dialog dialog--add-section">
          <div class="dialog-header">
            <h3>Add Section</h3>
            <button class="icon-btn" type="button" @click="showAddDialog = false" aria-label="Close">
              <font-awesome-icon :icon="faXmark" />
            </button>
          </div>
          
          <div class="dialog-body dialog-body--add-section">
            <!-- Tab navigation -->
            <div class="tabs">
              <button 
                class="tab" 
                :class="{ active: activeTab === 'templates' }"
                @click="activeTab = 'templates'"
              >
                Templates
              </button>
              <button 
                v-if="!templateMode"
                class="tab" 
                :class="{ active: activeTab === 'existing' }"
                @click="activeTab = 'existing'"
              >
                Shared Sections
              </button>
            </div>
            
            <!-- Templates tab -->
            <div v-if="activeTab === 'templates'" class="tab-content tab-content--templates">
              <p class="tab-hint">Create a new section from a section template, or insert a baked container template.</p>
              <div class="template-type-grid">
                <div
                  v-for="group in sectionTemplateGroups"
                  :key="`group-${group.sectionType}`"
                  class="template-type-card-wrap"
                >
                  <button
                    class="template-type-card"
                    type="button"
                    :class="{ expanded: isSectionTemplateTypeExpanded(group.sectionType) }"
                    @click="onSectionTemplateTypeClick(group)"
                  >
                    <div class="template-type-card-main">
                      <span class="template-type-icon"><font-awesome-icon :icon="getTypeIcon(group.sectionType)" /></span>
                      <span class="template-type-name">{{ formatTypeName(group.sectionType) }}</span>
                    </div>
                    <span
                      v-if="group.templates.length > 1"
                      class="template-version-count"
                      :title="`${group.templates.length} versions`"
                    >
                      <span class="template-version-info-icon">i</span>
                      <span>{{ group.templates.length }}</span>
                    </span>
                  </button>

                  <div v-if="isSectionTemplateTypeExpanded(group.sectionType)" class="template-version-collapse">
                    <button
                      v-for="template in group.templates"
                      :key="`${group.sectionType}:${template.template_name}`"
                      class="template-version-btn"
                      type="button"
                      @click="selectTemplate(template)"
                    >
                      {{ template.template_name }}
                    </button>
                  </div>
                </div>
              </div>

              <div v-if="containerTemplateCards.length" class="container-template-section">
                <p class="tab-hint">Container Templates</p>
                <div class="template-grid">
                  <button
                    v-for="template in containerTemplateCards"
                    :key="`container-${template.template_name}`"
                    class="template-card template-card--container"
                    @click="selectContainerTemplate(template)"
                  >
                    <div class="template-icon"><font-awesome-icon :icon="faPuzzlePiece" /></div>
                    <div class="template-name">{{ template.template_name }}</div>
                    <div class="template-meta">
                      {{ Array.isArray(template.sections) ? template.sections.length : 0 }} section(s)
                    </div>
                  </button>
                </div>
              </div>
            </div>
            
            <!-- Shared sections tab -->
            <div v-if="!templateMode && activeTab === 'existing'" class="tab-content tab-content--existing-sections">
              <p class="tab-hint">Shared sections can be reused across pages. Share a section from its Template tab to make it appear here.</p>
              
              <!-- Sort & Group options -->
              <div class="filter-bar">
                <div class="filter-option">
                  <span class="filter-label">Sort:</span>
                  <select v-model="sortField" class="filter-select">
                    <option
                      v-for="option in LIBRARY_SORT_FIELD_OPTIONS"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                  <select v-model="sortDirection" class="filter-select filter-select--direction">
                    <option
                      v-for="option in LIBRARY_SORT_DIRECTION_OPTIONS"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                </div>
                <div class="filter-option">
                  <span class="filter-label">Group:</span>
                  <select v-model="groupBy" class="filter-select">
                    <option
                      v-for="option in LIBRARY_GROUP_OPTIONS"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.sectionLabel || option.label }}
                    </option>
                  </select>
                </div>
              </div>
              
              <div v-if="loadingExisting" class="loading-hint">
                Loading sections...
              </div>
              
              <div v-else-if="sortedExistingSections.length === 0" class="empty-hint">
                No shared sections found. Share a page section from its Template tab to reuse it here.
              </div>
              
              <div v-else class="existing-sections-container">
                <!-- Ungrouped view -->
                <template v-if="groupBy === 'none'">
                  <div class="existing-list">
                    <div 
                      v-for="section in sortedExistingSections" 
                      :key="section._id"
                      class="existing-card-wrapper"
                    >
                      <div 
                        class="existing-card"
                        :class="{ 'is-on-page': isSectionOnCurrentPage(section._id) }"
                        @click="!isSectionOnCurrentPage(section._id) && selectExisting(section)"
                      >
                        <div class="existing-icon"><font-awesome-icon :icon="getTypeIcon(section.section_type)" /></div>
                        <div class="existing-info">
                          <div class="existing-name">{{ localizedText(section.title) || section.title_placeholder || formatTypeName(section.section_type) }}</div>
                          <div class="existing-meta">
                            <span class="existing-type">{{ formatTypeName(section.section_type) }}</span>
                            <span class="existing-usage" :class="{ 'no-usage': section.usage_count === 0 }">
                              {{ section.usage_count || 0 }} page(s)
                            </span>
                          </div>
                        </div>
                        <div class="existing-actions" @click.stop>
                          <button 
                            class="info-btn" 
                            type="button" 
                            title="View usage"
                            @click="showSectionInfo(section)"
                          >
                            <font-awesome-icon :icon="faCircleInfo" />
                          </button>
                          <button 
                            v-if="section.usage_count === 0"
                            class="delete-btn" 
                            type="button" 
                            title="Delete section"
                            @click="confirmDeleteSection(section)"
                          >
                            <font-awesome-icon :icon="faTrash" />
                          </button>
                        </div>
                      </div>
                      <div v-if="isSectionOnCurrentPage(section._id)" class="on-page-badge">Already on page</div>
                    </div>
                  </div>
                </template>
                
                <!-- Grouped by usage count -->
                <template v-else-if="groupBy === 'usage'">
                  <div v-for="(sections, count) in groupedByUsage" :key="count" class="group">
                    <div class="group-header">
                      <span class="group-title">{{ count === '0' ? 'Unused' : `Used on ${count} page(s)` }}</span>
                      <span class="group-count">{{ sections.length }}</span>
                    </div>
                    <div class="existing-list">
                      <div 
                        v-for="section in sections" 
                        :key="section._id"
                        class="existing-card-wrapper"
                      >
                        <div 
                          class="existing-card"
                          :class="{ 'is-on-page': isSectionOnCurrentPage(section._id) }"
                          @click="!isSectionOnCurrentPage(section._id) && selectExisting(section)"
                        >
                          <div class="existing-icon"><font-awesome-icon :icon="getTypeIcon(section.section_type)" /></div>
                          <div class="existing-info">
                            <div class="existing-name">{{ localizedText(section.title) || section.title_placeholder || formatTypeName(section.section_type) }}</div>
                            <div class="existing-type">{{ formatTypeName(section.section_type) }}</div>
                          </div>
                          <div class="existing-actions" @click.stop>
                            <button class="info-btn" type="button" title="View usage" @click="showSectionInfo(section)">
                              <font-awesome-icon :icon="faCircleInfo" />
                            </button>
                            <button v-if="section.usage_count === 0" class="delete-btn" type="button" title="Delete section" @click="confirmDeleteSection(section)">
                              <font-awesome-icon :icon="faTrash" />
                            </button>
                          </div>
                        </div>
                        <div v-if="isSectionOnCurrentPage(section._id)" class="on-page-badge">Already on page</div>
                      </div>
                    </div>
                  </div>
                </template>
                
                <!-- Grouped by page -->
                <template v-else-if="groupBy === 'page'">
                  <div v-for="(sections, pageName) in groupedByPage" :key="pageName" class="group">
                    <div class="group-header">
                      <span class="group-title">{{ pageName === '_unused' ? 'Unused (no page)' : `/${pageName}` }}</span>
                      <span class="group-count">{{ sections.length }}</span>
                    </div>
                    <div class="existing-list">
                      <div 
                        v-for="section in sections" 
                        :key="section._id"
                        class="existing-card-wrapper"
                      >
                        <div 
                          class="existing-card"
                          :class="{ 'is-on-page': isSectionOnCurrentPage(section._id) }"
                          @click="!isSectionOnCurrentPage(section._id) && selectExisting(section)"
                        >
                          <div class="existing-icon"><font-awesome-icon :icon="getTypeIcon(section.section_type)" /></div>
                          <div class="existing-info">
                            <div class="existing-name">{{ localizedText(section.title) || section.title_placeholder || formatTypeName(section.section_type) }}</div>
                            <div class="existing-type">{{ formatTypeName(section.section_type) }}</div>
                          </div>
                          <div class="existing-actions" @click.stop>
                            <button class="info-btn" type="button" title="View usage" @click="showSectionInfo(section)">
                              <font-awesome-icon :icon="faCircleInfo" />
                            </button>
                            <button v-if="section.usage_count === 0" class="delete-btn" type="button" title="Delete section" @click="confirmDeleteSection(section)">
                              <font-awesome-icon :icon="faTrash" />
                            </button>
                          </div>
                        </div>
                        <div v-if="isSectionOnCurrentPage(section._id)" class="on-page-badge">Already on page</div>
                      </div>
                    </div>
                  </div>
                </template>
                
                <!-- Grouped by type -->
                <template v-else-if="groupBy === 'type'">
                  <div v-for="(sections, typeName) in groupedByType" :key="typeName" class="group">
                    <div class="group-header">
                      <span class="group-icon"><font-awesome-icon :icon="getTypeIcon(typeName)" /></span>
                      <span class="group-title">{{ formatTypeName(typeName) }}</span>
                      <span class="group-count">{{ sections.length }}</span>
                    </div>
                    <div class="existing-list">
                      <div 
                        v-for="section in sections" 
                        :key="section._id"
                        class="existing-card-wrapper"
                      >
                        <div 
                          class="existing-card"
                          :class="{ 'is-on-page': isSectionOnCurrentPage(section._id) }"
                          @click="!isSectionOnCurrentPage(section._id) && selectExisting(section)"
                        >
                          <div class="existing-icon"><font-awesome-icon :icon="getTypeIcon(section.section_type)" /></div>
                          <div class="existing-info">
                            <div class="existing-name">{{ localizedText(section.title) || section.title_placeholder || formatTypeName(section.section_type) }}</div>
                            <div class="existing-meta">
                              <span class="existing-usage" :class="{ 'no-usage': section.usage_count === 0 }">
                                {{ section.usage_count || 0 }} page(s)
                              </span>
                            </div>
                          </div>
                          <div class="existing-actions" @click.stop>
                            <button class="info-btn" type="button" title="View usage" @click="showSectionInfo(section)">
                              <font-awesome-icon :icon="faCircleInfo" />
                            </button>
                            <button v-if="section.usage_count === 0" class="delete-btn" type="button" title="Delete section" @click="confirmDeleteSection(section)">
                              <font-awesome-icon :icon="faTrash" />
                            </button>
                          </div>
                        </div>
                        <div v-if="isSectionOnCurrentPage(section._id)" class="on-page-badge">Already on page</div>
                      </div>
                    </div>
                  </div>
                </template>

                <!-- Grouped by generated state -->
                <template v-else-if="groupBy === 'generated'">
                  <div v-for="group in groupedByGenerated" :key="group.key" class="group">
                    <div class="group-header">
                      <span class="group-title">{{ group.label }}</span>
                      <span class="group-count">{{ group.sections.length }}</span>
                    </div>
                    <div class="existing-list">
                      <div
                        v-for="section in group.sections"
                        :key="section._id"
                        class="existing-card-wrapper"
                      >
                        <div
                          class="existing-card"
                          :class="{ 'is-on-page': isSectionOnCurrentPage(section._id) }"
                          @click="!isSectionOnCurrentPage(section._id) && selectExisting(section)"
                        >
                          <div class="existing-icon"><font-awesome-icon :icon="getTypeIcon(section.section_type)" /></div>
                          <div class="existing-info">
                            <div class="existing-name">{{ localizedText(section.title) || section.title_placeholder || formatTypeName(section.section_type) }}</div>
                            <div class="existing-meta">
                              <span class="existing-type">{{ formatTypeName(section.section_type) }}</span>
                              <span class="existing-usage" :class="{ 'no-usage': section.usage_count === 0 }">
                                {{ section.usage_count || 0 }} page(s)
                              </span>
                            </div>
                          </div>
                          <div class="existing-actions" @click.stop>
                            <button class="info-btn" type="button" title="View usage" @click="showSectionInfo(section)">
                              <font-awesome-icon :icon="faCircleInfo" />
                            </button>
                            <button v-if="section.usage_count === 0" class="delete-btn" type="button" title="Delete section" @click="confirmDeleteSection(section)">
                              <font-awesome-icon :icon="faTrash" />
                            </button>
                          </div>
                        </div>
                        <div v-if="isSectionOnCurrentPage(section._id)" class="on-page-badge">Already on page</div>
                      </div>
                    </div>
                  </div>
                </template>

              </div>

              <div
                v-if="sortedExistingSections.length > 0 && existingSectionsTotal > MANAGE_LIBRARY_PAGE_SIZE"
                class="section-pagination"
              >
                <button
                  class="pagination-btn"
                  type="button"
                  :disabled="loadingExisting || existingSectionsPage <= 1"
                  @click="goToExistingSectionsPage(existingSectionsPage - 1)"
                >
                  Previous
                </button>
                <span class="pagination-status">
                  Page {{ existingSectionsPage }} of {{ existingSectionsPageCount }}
                  | {{ existingSectionsPageStart }}-{{ existingSectionsPageEnd }} of {{ existingSectionsTotal }}
                </span>
                <button
                  class="pagination-btn"
                  type="button"
                  :disabled="loadingExisting || existingSectionsPage >= existingSectionsPageCount"
                  @click="goToExistingSectionsPage(existingSectionsPage + 1)"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
    
    <!-- Section Info Popup -->
    <Teleport to="body">
      <div v-if="sectionInfoPopup" class="dialog-overlay" @click.self="sectionInfoPopup = null">
        <div class="dialog dialog-small">
          <div class="dialog-header">
            <h3>Section Usage</h3>
            <button class="icon-btn" type="button" @click="sectionInfoPopup = null" aria-label="Close">
              <font-awesome-icon :icon="faXmark" />
            </button>
          </div>
          <div class="dialog-body">
            <div class="info-section-name">
              <span class="info-icon"><font-awesome-icon :icon="getTypeIcon(sectionInfoPopup.section_type)" /></span>
              <span>{{ localizedText(sectionInfoPopup.title) || sectionInfoPopup.title_placeholder || formatTypeName(sectionInfoPopup.section_type) }}</span>
            </div>
            <div class="info-type">Type: {{ formatTypeName(sectionInfoPopup.section_type) }}</div>
            <div class="info-usage-header">Used on {{ sectionInfoPopup.usage?.length || 0 }} page(s):</div>
            <div v-if="sectionInfoPopup.usage?.length > 0" class="info-usage-list">
              <div v-for="usage in sectionInfoPopup.usage" :key="usage.slug" class="info-usage-item">
                <span class="info-route">/{{ usage.slug }}</span>
                <span class="info-visibility" :class="{ hidden: !usage.visible }">
                  {{ usage.visible ? 'visible' : 'hidden' }}
                </span>
              </div>
            </div>
            <div v-else class="info-no-usage">
              This section is not used on any page.
            </div>
          </div>
        </div>
      </div>
    </Teleport>
    
    <!-- Delete Section Confirmation -->
    <Teleport to="body">
      <div v-if="deleteSectionConfirm" class="dialog-overlay" @click.self="deleteSectionConfirm = null">
        <div class="dialog dialog-small">
          <div class="dialog-header">
            <h3>Delete Section</h3>
            <button class="icon-btn" type="button" @click="deleteSectionConfirm = null" aria-label="Close">
              <font-awesome-icon :icon="faXmark" />
            </button>
          </div>
          <div class="dialog-body">
            <p class="confirm-text">Are you sure you want to delete this section?</p>
            <div class="info-section-name">
              <span class="info-icon"><font-awesome-icon :icon="getTypeIcon(deleteSectionConfirm.section_type)" /></span>
              <span>{{ localizedText(deleteSectionConfirm.title) || deleteSectionConfirm.title_placeholder || formatTypeName(deleteSectionConfirm.section_type) }}</span>
            </div>
            <p class="confirm-warning">This action cannot be undone.</p>
            <div class="confirm-actions">
              <button class="btn-secondary" type="button" @click="deleteSectionConfirm = null">Cancel</button>
              <button class="btn-danger" type="button" @click="doDeleteSection">Delete</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
    
    <!-- Manage Headers Dialog -->
    <Teleport to="body">
      <div v-if="allowHeaderManagement && showHeaderDialog" class="dialog-overlay" @click.self="showHeaderDialog = false">
        <div class="dialog dialog--manage-headers">
          <div class="dialog-header">
            <h3>Manage Headers</h3>
            <button class="icon-btn" type="button" @click="showHeaderDialog = false" aria-label="Close">
              <font-awesome-icon :icon="faXmark" />
            </button>
          </div>
          <div class="dialog-body dialog-body--manage-headers">
            <div class="tabs">
              <button
                class="tab"
                :class="{ active: headerTab === 'new' }"
                @click="headerTab = 'new'"
              >
                Create New
              </button>
              <button
                class="tab"
                :class="{ active: headerTab === 'existing' }"
                @click="headerTab = 'existing'"
              >
                Shared Headers
              </button>
            </div>

            <!-- Create new header tab -->
            <div v-if="headerTab === 'new'" class="tab-content tab-content--header-create">
              <p class="tab-hint">Select which content the new header should include:</p>
              <div class="content-checklist">
                <label class="content-check" v-for="item in headerContentOptions" :key="item.key">
                  <input type="checkbox" v-model="item.checked" />
                  <span class="content-check-label">{{ item.label }}</span>
                </label>
              </div>
              <button
                class="btn create-header-btn"
                type="button"
                @click="createNewHeader"
                :disabled="creatingHeader"
              >
                {{ creatingHeader ? 'Creating...' : 'Create & Use on This Page' }}
              </button>
            </div>

            <!-- Shared headers tab -->
            <div v-if="headerTab === 'existing'" class="tab-content tab-content--existing-headers">
              <p class="tab-hint">Shared headers can be reused across pages. Share a header from its Template tab to make it appear here.</p>

              <div class="filter-bar">
                <div class="filter-option">
                  <span class="filter-label">Sort:</span>
                  <select v-model="headerSortField" class="filter-select">
                    <option
                      v-for="option in LIBRARY_SORT_FIELD_OPTIONS"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                  <select v-model="headerSortDirection" class="filter-select filter-select--direction">
                    <option
                      v-for="option in LIBRARY_SORT_DIRECTION_OPTIONS"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                </div>
                <div class="filter-option">
                  <span class="filter-label">Group:</span>
                  <select v-model="headerGroupBy" class="filter-select">
                    <option
                      v-for="option in HEADER_LIBRARY_GROUP_OPTIONS"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.headerLabel || option.label }}
                    </option>
                  </select>
                </div>
              </div>

              <div v-if="loadingHeaders" class="loading-hint">Loading headers...</div>

              <div v-else-if="sortedExistingHeaders.length === 0" class="empty-hint">
                No shared headers found. Share a page header from its Template tab to reuse it here.
              </div>

              <div v-else class="existing-sections-container">
                <div
                  v-for="group in headerDisplayGroups"
                  :key="group.key"
                  class="group"
                  :class="{ 'group--plain': !group.showHeader }"
                >
                  <div v-if="group.showHeader" class="group-header">
                    <span v-if="group.icon" class="group-icon"><font-awesome-icon :icon="group.icon" /></span>
                    <span class="group-title">{{ group.label }}</span>
                    <span class="group-count">{{ group.items.length }}</span>
                  </div>
                  <div class="existing-list">
                    <div
                      v-for="h in group.items"
                      :key="h.id"
                      class="existing-card-wrapper"
                    >
                      <div
                        class="existing-card"
                        :class="{ 'is-on-page': isCurrentHeader(h.id) }"
                        @click="!isCurrentHeader(h.id) && selectExistingHeader(h)"
                      >
                        <div class="header-thumb">
                          <img v-if="h.background_media_url" :src="h.background_media_url" alt="" class="thumb-img" loading="lazy" />
                          <span v-else class="thumb-placeholder"><font-awesome-icon :icon="faImage" /></span>
                        </div>
                        <div class="existing-info">
                          <div class="existing-name">{{ getHeaderLabel(h) }}</div>
                          <div class="existing-meta">
                            <span class="existing-type">{{ h.header_type || 'hero' }}</span>
                            <span class="existing-usage" :class="{ 'no-usage': h.usage_count === 0 }">
                              {{ h.usage_count || 0 }} page(s)
                            </span>
                            <span v-if="isCurrentHeader(h.id)" class="on-page-badge">Current</span>
                          </div>
                        </div>
                        <div class="existing-actions" @click.stop>
                          <button class="info-btn" type="button" title="View usage" @click="showHeaderInfo(h)">
                            <font-awesome-icon :icon="faCircleInfo" />
                          </button>
                          <button
                            v-if="h.usage_count === 0"
                            class="delete-btn"
                            type="button"
                            title="Delete header"
                            @click="confirmDeleteHeader(h)"
                          >
                            <font-awesome-icon :icon="faTrash" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div
                v-if="sortedExistingHeaders.length > 0 && existingHeadersTotal > MANAGE_LIBRARY_PAGE_SIZE"
                class="section-pagination"
              >
                <button
                  class="pagination-btn"
                  type="button"
                  :disabled="loadingHeaders || existingHeadersPage <= 1"
                  @click="goToExistingHeadersPage(existingHeadersPage - 1)"
                >
                  Previous
                </button>
                <span class="pagination-status">
                  Page {{ existingHeadersPage }} of {{ existingHeadersPageCount }}
                  | {{ existingHeadersPageStart }}-{{ existingHeadersPageEnd }} of {{ existingHeadersTotal }}
                </span>
                <button
                  class="pagination-btn"
                  type="button"
                  :disabled="loadingHeaders || existingHeadersPage >= existingHeadersPageCount"
                  @click="goToExistingHeadersPage(existingHeadersPage + 1)"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Header Info Popup -->
    <Teleport to="body">
      <div v-if="headerInfoPopup" class="dialog-overlay" @click.self="headerInfoPopup = null">
        <div class="dialog dialog-small">
          <div class="dialog-header">
            <h3>Header Usage</h3>
            <button class="icon-btn" type="button" @click="headerInfoPopup = null" aria-label="Close">
              <font-awesome-icon :icon="faXmark" />
            </button>
          </div>
          <div class="dialog-body">
            <div class="info-section-name">
              <span class="info-icon"><font-awesome-icon :icon="faImage" /></span>
              <span>{{ getHeaderLabel(headerInfoPopup) }}</span>
            </div>
            <div class="info-type">Type: {{ headerInfoPopup.header_type || 'hero' }}</div>
            <div class="info-usage-header">Used on {{ headerInfoPopup.usage?.length || 0 }} page(s):</div>
            <div v-if="headerInfoPopup.usage?.length > 0" class="info-usage-list">
              <div v-for="u in headerInfoPopup.usage" :key="u.slug" class="info-usage-item">
                <span class="info-route">/{{ u.slug }}</span>
                <span class="info-visibility" :class="{ hidden: !u.has_header }">
                  {{ u.has_header ? 'visible' : 'hidden' }}
                </span>
              </div>
            </div>
            <div v-else class="info-no-usage">This header is not used on any page.</div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Delete Header Confirmation -->
    <Teleport to="body">
      <div v-if="deleteHeaderConfirm" class="dialog-overlay" @click.self="deleteHeaderConfirm = null">
        <div class="dialog dialog-small">
          <div class="dialog-header">
            <h3>Delete Header</h3>
            <button class="icon-btn" type="button" @click="deleteHeaderConfirm = null" aria-label="Close">
              <font-awesome-icon :icon="faXmark" />
            </button>
          </div>
          <div class="dialog-body">
            <p class="confirm-text">Are you sure you want to delete this header?</p>
            <div class="info-section-name">
              <span class="info-icon"><font-awesome-icon :icon="faImage" /></span>
              <span>{{ getHeaderLabel(deleteHeaderConfirm) }}</span>
            </div>
            <p class="confirm-warning">This action cannot be undone.</p>
            <div class="confirm-actions">
              <button class="btn-secondary" type="button" @click="deleteHeaderConfirm = null">Cancel</button>
              <button class="btn-danger" type="button" @click="doDeleteHeader">Delete</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Container Editor -->
    <Teleport to="body">
      <div v-if="containerEditor" class="dialog-overlay" @click.self="closeContainerEditor">
        <div class="dialog dialog-small">
          <div class="dialog-header">
            <h3>Edit Container</h3>
            <button class="icon-btn" type="button" @click="closeContainerEditor" aria-label="Close">
              <font-awesome-icon :icon="faXmark" />
            </button>
          </div>
          <div class="dialog-body">
            <p class="tab-hint">{{ containerEditorHint }}</p>
            <draggable
              v-if="containerEditorDraftMembers.length > 0"
              v-model="containerEditorDraftMembers"
              item-key="key"
              handle=".container-editor-drag-handle"
              ghost-class="container-editor-ghost"
              :animation="150"
              :disabled="isPreviewLocked"
              @end="onContainerEditorDragEnd"
              class="container-editor-list"
            >
              <template #item="{ element: member, index }">
                <div class="container-editor-row">
                  <div class="container-editor-name">
                    <span class="container-editor-drag-handle" title="Drag to reorder">⋮⋮</span>
                    <span class="section-icon"><font-awesome-icon :icon="getSectionIcon(member.key)" /></span>
                    <span>{{ getSectionName(member.key) }}</span>
                  </div>
                  <div class="container-editor-controls">
                    <div v-if="index === 0" class="width-ratio container-width-ratio">
                      <span class="container-width-label">Width</span>
                      <select
                        class="ratio-select"
                        :value="getWidthN(member.key)"
                        :disabled="isPreviewLocked"
                        @change="onWidthNChange(member.key, +$event.target.value)"
                      >
                        <option v-for="n in getMaxN(member.key)" :key="`w_n_${member.key}_${n}`" :value="n">{{ n }}</option>
                      </select>
                      <span class="ratio-slash">/</span>
                      <select
                        class="ratio-select"
                        :value="getWidthD(member.key)"
                        :disabled="isPreviewLocked"
                        @change="onWidthDChange(member.key, +$event.target.value)"
                      >
                        <option v-for="d in 5" :key="`w_d_${member.key}_${d}`" :value="d">{{ d }}</option>
                      </select>
                    </div>
                    <button
                      class="container-unlink-btn"
                      type="button"
                      :title="isContainerTemplateBuilderContext ? 'Remove from template' : 'Unlink from container'"
                      :disabled="isPreviewLocked || isContainerStructureLocked(containerEditorDraftMembers.map((entry) => entry.key))"
                      @click="onContainerEditorMemberDetach(containerEditor.containerId, member.key)"
                    >
                      {{ isContainerTemplateBuilderContext ? "Remove" : "Unlink" }}
                    </button>
                  </div>
                </div>
              </template>
            </draggable>
            <div v-else class="info-no-usage">This container is empty.</div>
            <p class="confirm-note">When fewer than two sections remain, the container resolves automatically.</p>
          </div>
        </div>
      </div>
    </Teleport>
  </aside>
</template>

<script setup>
import { ref, watch, computed, onMounted, onBeforeUnmount, reactive } from "vue";
import {
  faAlignLeft,
  faBullhorn,
  faCalendarDays,
  faCode,
  faCircleInfo,
  faCircleQuestion,
  faDesktop,
  faFileLines,
  faShareNodes,
  faImage,
  faImages,
  faMap,
  faMobileScreenButton,
  faNewspaper,
  faPaintbrush,
  faPenToSquare,
  faPuzzlePiece,
  faTableCellsLarge,
  faTabletScreenButton,
  faTrash,
  faVideo,
  faXmark,
} from "@fortawesome/free-solid-svg-icons";
import draggable from "vuedraggable";
import { useStore } from "../../../store/store.js";
import * as api from "../../../services/api.js";
import { usePanelPosition } from "../../../composables/usePanelPosition.js";
import VueColorPicker from "../../ui/color/VueColorPicker.vue";
import PanelPositionControl from "./PanelPositionControl.vue";
import {
  buildSectionContainerMaps,
  buildSectionStructureFromEntries,
} from "../../../utils/sectionContainers.js";
import { parseRevisionTimestamp } from "../../../utils/revisionTime.js";

const CONTAINER_TEMPLATE_LOCK_KEY = "_templateContainerLock";
const CONTAINER_TEMPLATE_NAME_KEY = "_templateContainerName";
const MANAGE_LIBRARY_PAGE_SIZE = 50;
const LIBRARY_SORT_FIELD_OPTIONS = Object.freeze([
  { value: "created_at", label: "Created" },
  { value: "updated_at", label: "Updated" },
  { value: "name", label: "Name (A-Z)" },
]);
const LIBRARY_SORT_DIRECTION_OPTIONS = Object.freeze([
  { value: "asc", label: "Asc" },
  { value: "desc", label: "Desc" },
]);
const LIBRARY_GROUP_OPTIONS = Object.freeze([
  { value: "none", label: "None" },
  { value: "usage", label: "Usage Count" },
  { value: "page", label: "Page" },
  { value: "type", sectionLabel: "Section Type", headerLabel: "Header Type" },
  { value: "generated", label: "Is Generated" },
]);
const HEADER_LIBRARY_GROUP_OPTIONS = Object.freeze(
  LIBRARY_GROUP_OPTIONS.filter((option) => option.value !== "type")
);

// Props for page-specific configuration
const props = defineProps({
  pageSlug: {
    type: String,
    default: "landing"
  },
  fixedKeys: {
    type: Array,
    default: () => []
  },
  showAddSection: {
    type: Boolean,
    default: false
  },
  availableSectionTypes: {
    type: Array,
    default: () => []
  },
  availableSectionTemplates: {
    type: Array,
    default: () => []
  },
  availableContainerTemplates: {
    type: Array,
    default: () => []
  },
  hasHeader: {
    type: Boolean,
    default: false
  },
  currentHeaderId: {
    type: String,
    default: null
  },
  templateMode: {
    type: Boolean,
    default: false
  },
  templateBuilderKind: {
    type: String,
    default: null
  },
  showHeaderToggle: {
    type: Boolean,
    default: true
  },
  allowHeaderManagement: {
    type: Boolean,
    default: true
  },
  designOverridesLocked: {
    type: Boolean,
    default: false
  },
  templatePreviewActive: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['add-section', 'section-removed', 'toggle-header', 'header-changed', 'template-updated']);

const { state, t, localizedText, setSectionStructure, updateSectionLimit, setSectionWidth, updateDesignSetting, saveDesignSettings, computeSectionBgColor, setSectionDeviceVisibility, setSectionBgPinnedKey, updateSection, saveSectionByKey, saveSectionDesignOverrides } =
  useStore();

const isPreviewLocked = computed(() => Boolean(props.templatePreviewActive));
const resolvedTemplateBuilderKind = computed(() => {
  const directKind = String(props.templateBuilderKind || "").trim().toLowerCase();
  if (directKind) return directKind;
  const slug = String(props.pageSlug || "").trim();
  if (props.templateMode && slug.startsWith("__template_container__/")) return "container";
  return "";
});
const isContainerTemplateBuilderContext = computed(() =>
  props.templateMode && resolvedTemplateBuilderKind.value === "container"
);
const containerEditorHint = computed(() =>
  isContainerTemplateBuilderContext.value
    ? "Adjust section width, drag to reorder, or remove sections from this template."
    : "Adjust section width, drag to reorder, or unlink sections from this container."
);

function getSectionDeviceVisibility(sectionKey, device) {
  const visibility = state.landingLayout?.deviceVisibility?.[sectionKey];
  if (!visibility) return true;
  return visibility[device] !== false;
}

function toggleSectionDevice(sectionKey, device) {
  if (isPreviewLocked.value) return;
  const current = getSectionDeviceVisibility(sectionKey, device);
  setSectionDeviceVisibility(sectionKey, device, !current, props.pageSlug);
}

function isAllDevicesHidden(sectionKey) {
  const visibility = state.landingLayout?.deviceVisibility?.[sectionKey];
  if (!visibility) return false;
  return visibility.mobile === false && visibility.tablet === false && visibility.desktop === false;
}

function isHiddenForCurrentView(sectionKey) {
  const visibility = state.landingLayout?.deviceVisibility?.[sectionKey];
  if (!visibility) return false;
  
  // Check if all devices are hidden
  if (visibility.mobile === false && visibility.tablet === false && visibility.desktop === false) {
    return true;
  }
  
  // Check simulated viewport first
  const sim = state.simulatedViewport;
  if (sim) {
    if (sim === 'mobile' && visibility.mobile === false) return true;
    if (sim === 'tablet' && visibility.tablet === false) return true;
    if (sim === 'desktop' && visibility.desktop === false) return true;
    return false;
  }
  
  // No simulation - check current screen width
  // Desktop is default for admin view (typically >= 1120px)
  if (visibility.desktop === false) return true;
  
  return false;
}

const isGradientPattern = computed(() => {
  const p = state.design.sectionBgPattern;
  return p === 'gradient' || p === 'gradient_shuffled' || p === 'alpha_gradient' || p === 'alpha_gradient_shuffled';
});

const isShuffledPattern = computed(() => {
  const p = state.design.sectionBgPattern;
  return p === 'gradient_shuffled' || p === 'alpha_gradient_shuffled';
});

const isColorGradient = computed(() => {
  const p = state.design.sectionBgPattern;
  return p === 'alternating' || p === 'gradient' || p === 'gradient_shuffled';
});

const isAlphaGradient = computed(() => {
  const p = state.design.sectionBgPattern;
  return p === 'alpha_gradient' || p === 'alpha_gradient_shuffled';
});

const showPinDialog = ref(false);

const visibleSections = computed(() => {
  const order = state.landingLayout?.order || [];
  const hidden = state.landingLayout?.hidden || {};
  return order
    .filter(k => !hidden[k])
    .map(k => ({ key: k, label: getSectionLabel(k) }));
});

const pinCount = computed(() => {
  let n = 0;
  if (state.landingLayout?.sectionBgPinnedStartKey) n++;
  if (state.landingLayout?.sectionBgPinnedEndKey) n++;
  return n;
});

const previewColors = computed(() => {
  const sections = visibleSections.value;
  const total = sections.length;
  if (total === 0) return [];
  return sections.map((s, idx) => {
    const color = computeSectionBgColor(idx, total, s.key);
    return color || (state.design.sectionBackgroundColor || '#ffffff');
  });
});

function setPin(which, key) {
  if (isPreviewLocked.value) return;
  setSectionBgPinnedKey(which, key, props.pageSlug);
}

function openPinDialog() {
  if (isPreviewLocked.value || isContainerTemplateBuilderContext.value) return;
  showPinDialog.value = true;
}

// Add Section Dialog state
const showAddDialog = ref(false);
const activeTab = ref('templates');
const existingSections = ref([]);
const existingSectionsTotal = ref(0);
const existingSectionsPage = ref(1);
const loadingExisting = ref(false);
const expandedSectionTemplateType = ref("");

// New features state
const groupBy = ref('none');  // 'none', 'usage', 'page', 'type', 'generated'
const sortField = ref('created_at');  // 'created_at', 'updated_at', 'name'
const sortDirection = ref('desc');  // 'asc', 'desc'
const sectionInfoPopup = ref(null);
const deleteSectionConfirm = ref(null);
const removingFromPage = ref(false);

// Section type icons
const TYPE_ICONS = {
  text: faAlignLeft,
  text_image: faImage,
  video: faVideo,
  faq: faCircleQuestion,
  links: faShareNodes,
  ticker: faBullhorn,
  gallery: faImages,
  blog: faNewspaper,
  markdown: faFileLines,
  html: faCode,
  map: faMap,
  tiles: faTableCellsLarge,
  program: faCalendarDays,
};

function getTypeIcon(type) {
  return TYPE_ICONS[type] || faFileLines;
}

// Localized section type names
const TYPE_NAMES = {
  text: { de: 'Text', en: '' },
  text_image: { de: 'Text mit Bild', en: 'Text Image' },
  video: { de: 'Video', en: '' },
  faq: { de: 'FAQ', en: 'FAQ' },
  links: { de: 'Links', en: 'Links' },
  ticker: { de: 'Ticker', en: '' },
  gallery: { de: 'Galerie', en: 'Gallery' },
  blog: { de: 'Blog', en: '' },
  markdown: { de: 'Markdown', en: '' },
  html: { de: 'HTML', en: '' },
  map: { de: 'Karte', en: 'Map' },
  tiles: { de: 'Kacheln', en: 'Tiles' },
  program: { de: 'Programm', en: 'Program' }
};

function formatTypeName(type) {
  const names = TYPE_NAMES[type];
  if (names) {
    return names[state.lang] || names.de || type;
  }
  // Fallback: format the type name nicely
  return type
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, str => str.toUpperCase())
    .trim();
}

const normalizedSectionTypeOptions = computed(() => {
  const fromApi = Array.isArray(props.availableSectionTypes) ? props.availableSectionTypes : [];
  const normalized = fromApi
    .map((entry) => {
      if (typeof entry === "string") {
        return { type: entry, default_data: {} };
      }
      if (entry && typeof entry === "object" && entry.type) {
        return {
          type: String(entry.type),
          default_data: entry.default_data && typeof entry.default_data === "object"
            ? entry.default_data
            : {},
        };
      }
      return null;
    })
    .filter(Boolean);

  if (normalized.length) return normalized;
  return Object.keys(TYPE_NAMES).map((type) => ({ type, default_data: {} }));
});

const sectionTemplateGroups = computed(() => {
  const groups = new Map();
  for (const entry of normalizedSectionTypeOptions.value) {
    groups.set(String(entry.type), []);
  }

  const templates = Array.isArray(props.availableSectionTemplates) ? props.availableSectionTemplates : [];
  for (const entry of templates) {
    if (!entry || typeof entry !== "object") continue;
    const sectionType = String(entry.section_type || "").trim();
    const templateName = String(entry.template_name || "").trim();
    if (!sectionType || !templateName) continue;
    if (!groups.has(sectionType)) groups.set(sectionType, []);
    groups.get(sectionType).push(entry);
  }

  const result = [];
  for (const [sectionType, templatesForType] of groups.entries()) {
    const sorted = [...templatesForType].sort((left, right) => {
      const leftName = String(left.template_name || "");
      const rightName = String(right.template_name || "");
      if (leftName === "default" && rightName !== "default") return -1;
      if (rightName === "default" && leftName !== "default") return 1;
      return leftName.localeCompare(rightName);
    });
    if (!sorted.some((entry) => String(entry.template_name || "") === "default")) {
      sorted.unshift({ section_type: sectionType, template_name: "default" });
    }
    result.push({ sectionType, templates: sorted });
  }
  return result.sort((left, right) => String(left.sectionType).localeCompare(String(right.sectionType)));
});

const containerTemplateCards = computed(() => {
  const templates = Array.isArray(props.availableContainerTemplates) ? props.availableContainerTemplates : [];
  return [...templates]
    .filter((entry) => entry && typeof entry === "object" && entry.template_name)
    .sort((left, right) => String(left.template_name || "").localeCompare(String(right.template_name || "")));
});

// Check if a section is on the current page
function isSectionOnCurrentPage(sectionId) {
  const currentSectionIds = new Set(Object.values(state.sectionIds || {}));
  return currentSectionIds.has(sectionId);
}

function getDefaultDataForType(sectionType) {
  const normalized = String(sectionType || "").trim();
  const entry = normalizedSectionTypeOptions.value.find((item) => String(item.type) === normalized);
  if (!entry) return {};
  return entry.default_data && typeof entry.default_data === "object"
    ? JSON.parse(JSON.stringify(entry.default_data))
    : {};
}

function sortLibraryItems(items, sortFieldValue, sortDirectionValue, getName) {
  const direction = sortDirectionValue === 'asc' ? 1 : -1;
  return [...items].sort((a, b) => {
    if (sortFieldValue === 'name') {
      const nameA = String(getName(a) || '').toLowerCase();
      const nameB = String(getName(b) || '').toLowerCase();
      return nameA.localeCompare(nameB) * direction;
    }
    const field = sortFieldValue === 'created_at' ? 'created_at' : 'updated_at';
    const timeA = parseRevisionTimestamp(a?.[field])?.getTime() || 0;
    const timeB = parseRevisionTimestamp(b?.[field])?.getTime() || 0;
    return (timeA - timeB) * direction;
  });
}

function normalizePagedLibraryResponse(response) {
  const items = Array.isArray(response)
    ? response
    : (Array.isArray(response?.items) ? response.items : []);
  const total = Array.isArray(response) ? items.length : Number(response?.total || 0);
  return { items, total };
}

// Sorted sections computed
const sortedExistingSections = computed(() => {
  return sortLibraryItems(
    existingSections.value,
    sortField.value,
    sortDirection.value,
    (section) => localizedText(section.title) || section.title_placeholder || ''
  );
});

const existingSectionsPageCount = computed(() =>
  Math.max(1, Math.ceil(existingSectionsTotal.value / MANAGE_LIBRARY_PAGE_SIZE))
);

const existingSectionsPageStart = computed(() => {
  if (existingSectionsTotal.value === 0) return 0;
  return (existingSectionsPage.value - 1) * MANAGE_LIBRARY_PAGE_SIZE + 1;
});

const existingSectionsPageEnd = computed(() =>
  Math.min(existingSectionsTotal.value, existingSectionsPage.value * MANAGE_LIBRARY_PAGE_SIZE)
);

// Grouped computed properties
const groupedByUsage = computed(() => {
  const groups = {};
  for (const section of sortedExistingSections.value) {
    const count = String(section.usage_count || 0);
    if (!groups[count]) groups[count] = [];
    groups[count].push(section);
  }
  // Sort by usage count (unused first, then ascending)
  const sorted = {};
  const keys = Object.keys(groups).sort((a, b) => Number(a) - Number(b));
  for (const key of keys) {
    sorted[key] = groups[key];
  }
  return sorted;
});

const groupedByPage = computed(() => {
  const groups = { '_unused': [] };
  for (const section of sortedExistingSections.value) {
    if (!section.usage || section.usage.length === 0) {
      groups['_unused'].push(section);
    } else {
      // Add to each page it's used on
      for (const usage of section.usage) {
        const pageName = usage.slug || '_unknown';
        if (!groups[pageName]) groups[pageName] = [];
        // Avoid duplicates if section is on multiple pages
        if (!groups[pageName].find(s => s._id === section._id)) {
          groups[pageName].push(section);
        }
      }
    }
  }
  // Remove empty unused group
  if (groups['_unused'].length === 0) delete groups['_unused'];
  return groups;
});

const groupedByType = computed(() => {
  const groups = {};
  for (const section of sortedExistingSections.value) {
    const type = section.section_type || 'unknown';
    if (!groups[type]) groups[type] = [];
    groups[type].push(section);
  }
  return groups;
});

const groupedByGenerated = computed(() => {
  const notGenerated = [];
  const generated = [];
  for (const section of sortedExistingSections.value) {
    if (section?.is_generated === true) {
      generated.push(section);
    } else {
      notGenerated.push(section);
    }
  }
  return [
    { key: 'not_generated', label: 'Not Generated', sections: notGenerated },
    { key: 'generated', label: 'Generated', sections: generated },
  ].filter((group) => group.sections.length > 0);
});

// Load existing sections when dialog opens
watch(() => showAddDialog.value, async (isOpen) => {
  if (!isOpen) {
    expandedSectionTemplateType.value = "";
    return;
  }
  if (isOpen && activeTab.value === 'existing') {
    await loadExistingSections();
  }
});

watch(() => activeTab.value, async (tab) => {
  if (tab !== 'templates') {
    expandedSectionTemplateType.value = "";
  }
  if (props.templateMode && tab !== 'templates') {
    activeTab.value = 'templates';
    return;
  }
  if (tab === 'existing' && showAddDialog.value) {
    await loadExistingSections();
  }
});

watch([sortField, sortDirection], async () => {
  existingSectionsPage.value = 1;
  if (showAddDialog.value && activeTab.value === 'existing') {
    await loadExistingSections();
  }
});

watch(
  () => props.templateMode,
  (enabled) => {
    if (enabled && activeTab.value !== 'templates') {
      activeTab.value = 'templates';
    }
  },
  { immediate: true }
);

async function loadExistingSections() {
  loadingExisting.value = true;
  try {
    const offset = (existingSectionsPage.value - 1) * MANAGE_LIBRARY_PAGE_SIZE;
    const response = await api.listSectionsWithUsage({
      limit: MANAGE_LIBRARY_PAGE_SIZE,
      offset,
      sortBy: sortField.value,
      sortDirection: sortDirection.value,
      includeTotal: true,
      sharedOnly: true,
      typeData: 'none',
    });
    const { items: sections, total } = normalizePagedLibraryResponse(response);
    const pageCount = Math.max(1, Math.ceil(total / MANAGE_LIBRARY_PAGE_SIZE));
    if (existingSectionsPage.value > pageCount) {
      existingSectionsPage.value = pageCount;
      await loadExistingSections();
      return;
    }
    existingSections.value = sections;
    existingSectionsTotal.value = total;
  } catch (err) {
    console.error('Failed to load existing sections:', err);
    existingSections.value = [];
    existingSectionsTotal.value = 0;
  } finally {
    loadingExisting.value = false;
  }
}

async function goToExistingSectionsPage(page) {
  const nextPage = Math.min(
    Math.max(1, Number(page) || 1),
    existingSectionsPageCount.value
  );
  if (nextPage === existingSectionsPage.value) return;
  existingSectionsPage.value = nextPage;
  await loadExistingSections();
}

// Info popup
function showSectionInfo(section) {
  sectionInfoPopup.value = section;
}

// Delete section
function confirmDeleteSection(section) {
  if (isPreviewLocked.value) return;
  deleteSectionConfirm.value = section;
}

async function doDeleteSection() {
  if (isPreviewLocked.value) return;
  if (!deleteSectionConfirm.value) return;
  
  try {
    await api.deleteSection(deleteSectionConfirm.value._id);
    deleteSectionConfirm.value = null;
    await loadExistingSections();
  } catch (err) {
    console.error('Failed to delete section:', err);
    alert('Failed to delete section: ' + err.message);
  }
}

function removeSectionFromStructure(structure, sectionId) {
  const normalizedSectionId = String(sectionId || "").trim();
  if (!normalizedSectionId || !Array.isArray(structure)) return Array.isArray(structure) ? structure : [];

  return structure
    .map((node) => {
      if (!node || typeof node !== "object") return null;
      if (node.type === "section") {
        return String(node.section_id || "").trim() === normalizedSectionId ? null : node;
      }
      if (node.type !== "container") return node;
      const sectionIds = Array.isArray(node.section_ids)
        ? node.section_ids.filter((id) => String(id || "").trim() !== normalizedSectionId)
        : [];
      if (sectionIds.length === 0) return null;
      return { ...node, section_ids: sectionIds };
    })
    .filter(Boolean);
}

function removeSectionFromPanelState(sectionKey, sectionId) {
  if (!sectionKey) return;

  if (state.sectionIds) delete state.sectionIds[sectionKey];
  if (state.sectionMeta) delete state.sectionMeta[sectionKey];
  if (state.sectionsData) delete state.sectionsData[sectionKey];
  if (state.sectionDesignOverrides) delete state.sectionDesignOverrides[sectionKey];

  if (!state.landingLayout) {
    state.landingLayout = { order: [], structure: [], hidden: {}, widths: {}, gridCols: 1, fullWidth: false };
  }
  state.landingLayout.order = Array.isArray(state.landingLayout.order)
    ? state.landingLayout.order.filter((key) => key !== sectionKey)
    : [];
  state.landingLayout.structure = removeSectionFromStructure(state.landingLayout.structure, sectionId);
  if (state.landingLayout.hidden) delete state.landingLayout.hidden[sectionKey];
  if (state.landingLayout.widths) delete state.landingLayout.widths[sectionKey];
  if (state.landingLayout.deviceVisibility) delete state.landingLayout.deviceVisibility[sectionKey];
  if (state.landingLayout.sectionBgPinnedStartKey === sectionKey) {
    state.landingLayout.sectionBgPinnedStartKey = "";
  }
  if (state.landingLayout.sectionBgPinnedEndKey === sectionKey) {
    state.landingLayout.sectionBgPinnedEndKey = "";
  }

  refreshDraggableEntryDraft();
  if (containerEditor.value) {
    syncContainerEditorDraftFromSource();
  }
}

function isAlreadyRemovedError(err) {
  const message = String(err?.message || "").toLowerCase();
  return message.includes("section not found") || message.includes("not found in template") || message.includes("not found in page");
}

function buildSectionRemovalTargets(sectionKeys) {
  const seen = new Set();
  return (Array.isArray(sectionKeys) ? sectionKeys : [])
    .map((key) => String(key || "").trim())
    .filter((key) => key && !seen.has(key) && seen.add(key))
    .map((key) => ({
      key,
      sectionId: state.sectionIds?.[key],
    }));
}

function canRemoveEntryFromPage(entry) {
  if (!entry || entry.type === "section") return true;
  if (entry.type !== "container") return false;
  return getEntrySectionKeys(entry).some((key) => state.sectionIds?.[key]);
}

async function refreshExistingSectionsAfterRemove() {
  try {
    await loadExistingSections();
  } catch (refreshErr) {
    console.warn("Section was removed, but refreshing section usage failed:", refreshErr);
  }
}

async function removeTargetsFromPage(targets) {
  if (isPreviewLocked.value) return;
  if (!Array.isArray(targets) || targets.length === 0 || removingFromPage.value) return;

  const validTargets = targets.filter((target) => target?.key);
  if (!validTargets.length) return;

  const removableTargets = validTargets.filter((target) => target.sectionId);
  if (!removableTargets.length) {
    for (const target of validTargets) {
      removeSectionFromPanelState(target.key, null);
    }
    return;
  }
  
  removingFromPage.value = true;
  const removedTargets = [];
  let pageData = null;

  try {
    for (const target of removableTargets) {
      try {
        const nextPageData = await api.removeSectionFromPage(props.pageSlug, target.sectionId);
        pageData = nextPageData || pageData;
      } catch (err) {
        if (isAlreadyRemovedError(err)) {
          pageData = pageData || null;
        } else {
          throw err;
        }
      }
      removeSectionFromPanelState(target.key, target.sectionId);
      removedTargets.push(target);
    }
    
    // Emit event to parent so it can refresh if needed
    emit('section-removed', {
      key: removedTargets[0]?.key,
      id: removedTargets[0]?.sectionId,
      keys: removedTargets.map((target) => target.key),
      ids: removedTargets.map((target) => target.sectionId),
      pageData,
    });

    // Refresh usage counts in the library without holding up the editor update.
    void refreshExistingSectionsAfterRemove();
  } catch (err) {
    console.error('Failed to remove section from page:', err);
    alert('Failed to remove section: ' + err.message);
  } finally {
    removingFromPage.value = false;
  }
}

async function removeFromPage(sectionKey) {
  await removeTargetsFromPage(buildSectionRemovalTargets([sectionKey]));
}

async function removeEntryFromPage(entry) {
  await removeTargetsFromPage(buildSectionRemovalTargets(getEntrySectionKeys(entry)));
}

function selectTemplate(template) {
  if (isPreviewLocked.value) return;
  if (!template || typeof template !== "object") return;
  const sectionType = String(template.section_type || "").trim();
  const templateName = String(template.template_name || "default").trim() || "default";
  if (!sectionType) return;
  emit('add-section', {
    templateKind: "section_template",
    section_type: sectionType,
    template_name: templateName,
    title_placeholder: formatTypeName(sectionType),
    default_data: getDefaultDataForType(sectionType),
  });
  showAddDialog.value = false;
}

function isSectionTemplateTypeExpanded(sectionType) {
  return String(expandedSectionTemplateType.value || "") === String(sectionType || "");
}

function onSectionTemplateTypeClick(group) {
  if (isPreviewLocked.value) return;
  const sectionType = String(group?.sectionType || "").trim();
  if (!sectionType) return;
  const templates = Array.isArray(group?.templates) ? group.templates : [];
  if (templates.length <= 1) {
    selectTemplate(templates[0] || { section_type: sectionType, template_name: "default" });
    return;
  }
  expandedSectionTemplateType.value = isSectionTemplateTypeExpanded(sectionType) ? "" : sectionType;
}

function selectContainerTemplate(template) {
  if (isPreviewLocked.value) return;
  const templateName = String(template?.template_name || "").trim();
  if (!templateName) return;
  emit('add-section', {
    templateKind: "container_template",
    template_name: templateName,
    type: "container",
  });
  showAddDialog.value = false;
}

function selectExisting(section) {
  if (isPreviewLocked.value) return;
  emit('add-section', {
    existingSectionId: section._id,
    type: section.section_type
  });
  showAddDialog.value = false;
}

// -------------------------
// Header Management
// -------------------------

const showHeaderDialog = ref(false);
const headerTab = ref('new');
const existingHeaders = ref([]);
const existingHeadersTotal = ref(0);
const existingHeadersPage = ref(1);
const loadingHeaders = ref(false);
const headerSortField = ref('updated_at');
const headerSortDirection = ref('desc');
const headerGroupBy = ref('none');
const headerInfoPopup = ref(null);
const deleteHeaderConfirm = ref(null);
const creatingHeader = ref(false);

const headerContentOptions = reactive([
  { key: 'title', label: 'Title', checked: true },
  { key: 'subtitle', label: 'Subtitle', checked: true },
  { key: 'cta_buttons', label: 'Action Buttons', checked: false },
  { key: 'overlay_image', label: 'Image Overlay', checked: false },
  { key: 'background_image', label: 'Background Image', checked: false },
]);

function onToggleHeader(e) {
  if (isPreviewLocked.value) {
    if (e?.target) e.target.checked = props.hasHeader;
    return;
  }
  emit('toggle-header', e.target.checked);
}

function getHeaderLabel(header) {
  if (!header) return 'Untitled Header';
  if (header.name && header.name.trim()) return header.name;
  const title = header.hero_title;
  if (title) {
    const text = localizedText(title);
    if (text && text.trim()) return text;
  }
  return `Header ${(header.id || '').slice(-6)}`;
}

function isCurrentHeader(headerId) {
  return props.currentHeaderId === headerId;
}

const sortedExistingHeaders = computed(() => {
  return sortLibraryItems(
    existingHeaders.value,
    headerSortField.value,
    headerSortDirection.value,
    getHeaderLabel
  );
});

const existingHeadersPageCount = computed(() =>
  Math.max(1, Math.ceil(existingHeadersTotal.value / MANAGE_LIBRARY_PAGE_SIZE))
);

const existingHeadersPageStart = computed(() => {
  if (existingHeadersTotal.value === 0) return 0;
  return (existingHeadersPage.value - 1) * MANAGE_LIBRARY_PAGE_SIZE + 1;
});

const existingHeadersPageEnd = computed(() =>
  Math.min(existingHeadersTotal.value, existingHeadersPage.value * MANAGE_LIBRARY_PAGE_SIZE)
);

const headerDisplayGroups = computed(() => {
  const headers = sortedExistingHeaders.value;
  if (headerGroupBy.value === 'usage') {
    const groups = new Map();
    for (const header of headers) {
      const count = Number(header?.usage_count || 0);
      const key = String(count);
      if (!groups.has(key)) {
        groups.set(key, {
          key: `usage:${key}`,
          label: count === 0 ? 'Unused' : `Used on ${count} page(s)`,
          items: [],
          showHeader: true,
        });
      }
      groups.get(key).items.push(header);
    }
    return [...groups.values()].sort((left, right) => {
      const leftCount = Number(left.key.split(':')[1] || 0);
      const rightCount = Number(right.key.split(':')[1] || 0);
      return leftCount - rightCount;
    });
  }
  if (headerGroupBy.value === 'page') {
    const groups = new Map();
    for (const header of headers) {
      const usage = Array.isArray(header?.usage) ? header.usage : [];
      if (usage.length === 0) {
        if (!groups.has('_unused')) {
          groups.set('_unused', { key: 'page:_unused', label: 'Unused (no page)', items: [], showHeader: true });
        }
        groups.get('_unused').items.push(header);
        continue;
      }
      for (const entry of usage) {
        const slug = String(entry?.slug || '_unknown');
        const key = `page:${slug}`;
        if (!groups.has(key)) {
          groups.set(key, {
            key,
            label: slug === '_unknown' ? 'Unknown page' : `/${slug}`,
            items: [],
            showHeader: true,
          });
        }
        if (!groups.get(key).items.some((item) => item.id === header.id)) {
          groups.get(key).items.push(header);
        }
      }
    }
    const result = [...groups.values()];
    return result.sort((left, right) => {
      if (left.key === 'page:_unused') return -1;
      if (right.key === 'page:_unused') return 1;
      return left.label.localeCompare(right.label);
    });
  }
  if (headerGroupBy.value === 'generated') {
    const notGenerated = [];
    const generated = [];
    for (const header of headers) {
      if (header?.is_generated === true) {
        generated.push(header);
      } else {
        notGenerated.push(header);
      }
    }
    return [
      { key: 'generated:not_generated', label: 'Not Generated', items: notGenerated, showHeader: true },
      { key: 'generated:generated', label: 'Generated', items: generated, showHeader: true },
    ].filter((group) => group.items.length > 0);
  }
  return [{ key: 'all', items: headers, showHeader: false }];
});

watch(() => showHeaderDialog.value, async (isOpen) => {
  if (isOpen && headerTab.value === 'existing') {
    await loadExistingHeaders();
  }
});

watch(() => headerTab.value, async (tab) => {
  if (tab === 'existing' && showHeaderDialog.value) {
    await loadExistingHeaders();
  }
});

watch([headerSortField, headerSortDirection], async () => {
  existingHeadersPage.value = 1;
  if (showHeaderDialog.value && headerTab.value === 'existing') {
    await loadExistingHeaders();
  }
});

async function loadExistingHeaders() {
  loadingHeaders.value = true;
  try {
    const offset = (existingHeadersPage.value - 1) * MANAGE_LIBRARY_PAGE_SIZE;
    const response = await api.listHeadersWithUsage({
      limit: MANAGE_LIBRARY_PAGE_SIZE,
      offset,
      sortBy: headerSortField.value,
      sortDirection: headerSortDirection.value,
      sharedOnly: true,
      includeTotal: true,
    });
    const { items: headers, total } = normalizePagedLibraryResponse(response);
    const pageCount = Math.max(1, Math.ceil(total / MANAGE_LIBRARY_PAGE_SIZE));
    if (existingHeadersPage.value > pageCount) {
      existingHeadersPage.value = pageCount;
      await loadExistingHeaders();
      return;
    }
    existingHeaders.value = headers;
    existingHeadersTotal.value = total;
  } catch (err) {
    console.error('Failed to load headers:', err);
    existingHeaders.value = [];
    existingHeadersTotal.value = 0;
  } finally {
    loadingHeaders.value = false;
  }
}

async function goToExistingHeadersPage(page) {
  const nextPage = Math.min(
    Math.max(1, Number(page) || 1),
    existingHeadersPageCount.value
  );
  if (nextPage === existingHeadersPage.value) return;
  existingHeadersPage.value = nextPage;
  await loadExistingHeaders();
}

async function createNewHeader() {
  if (isPreviewLocked.value) return;
  if (creatingHeader.value) return;
  creatingHeader.value = true;

  try {
    const enabledFields = headerContentOptions
      .filter(item => item.checked)
      .map(item => item.key);

    const headerData = {
      name: props.pageSlug,
      header_type: 'hero',
      enabled_fields: enabledFields,
    };

    if (enabledFields.includes('title')) {
      headerData.hero_title = { de: '', en: '' };
    }
    if (enabledFields.includes('subtitle')) {
      headerData.hero_subtitle = { de: '', en: '' };
    }
    if (enabledFields.includes('cta_buttons')) {
      headerData.cta_buttons = [{ text: { de: 'Button', en: 'Button' }, url: '' }];
    }

    const created = await api.createHeader(headerData);
    await api.attachHeaderToPage(props.pageSlug, created.id);

    showHeaderDialog.value = false;
    emit('header-changed', created.id);
  } catch (err) {
    console.error('Failed to create header:', err);
    alert('Failed to create header: ' + err.message);
  } finally {
    creatingHeader.value = false;
  }
}

async function selectExistingHeader(header) {
  if (isPreviewLocked.value) return;
  try {
    await api.attachHeaderToPage(props.pageSlug, header.id);
    showHeaderDialog.value = false;
    emit('header-changed', header.id);
  } catch (err) {
    console.error('Failed to attach header:', err);
    alert('Failed to attach header: ' + err.message);
  }
}

function showHeaderInfo(header) {
  headerInfoPopup.value = header;
}

function confirmDeleteHeader(header) {
  if (isPreviewLocked.value) return;
  deleteHeaderConfirm.value = header;
}

async function doDeleteHeader() {
  if (isPreviewLocked.value) return;
  if (!deleteHeaderConfirm.value) return;
  try {
    await api.deleteHeader(deleteHeaderConfirm.value.id);
    deleteHeaderConfirm.value = null;
    await loadExistingHeaders();
  } catch (err) {
    console.error('Failed to delete header:', err);
    alert('Failed to delete header: ' + err.message);
  }
}

// -------------------------
// Section Panel State
// -------------------------

const SHARED_SECTION_GENERIC_KEYS = [
];

const open = ref(false);
const { panelPosition: panelCorner } = usePanelPosition("sectionPanelCorner", "bottom-left");
const showDeviceToggles = ref(false);
const draggableEntryDraft = ref([]);
const dragContext = ref(null);
const dragHoverIntent = ref(null);
const dragLastLinkEntryId = ref("");
const dragPointer = ref(null);
const dragStartOrder = ref([]);
const pendingDropAction = ref(null);
const resolveDropActive = ref(false);
const containerEditor = ref(null);
const containerEditorDraftMembers = ref([]);
const containerTemplateNameCache = ref({});

// Get page layout from state
const pageLayout = computed(() => state.landingLayout || { order: [], hidden: {}, widths: {}, gridCols: 1, fullWidth: false });

// Get all section keys from sectionIds (loaded from backend)
const allSections = computed(() => {
  const sectionIds = state.sectionIds || {};
  return Object.keys(sectionIds).map((key) => ({
    key,
    id: sectionIds[key],
    label: getSectionLabel(key),
    isFixed: props.fixedKeys.includes(key),
  }));
});

// Fixed sections (cannot be reordered)
const fixedSections = computed(() => allSections.value.filter((s) => s.isFixed));

// Draggable sections (can be reordered)
const draggableSections = computed(() => allSections.value.filter((s) => !s.isFixed));

// Get section keys for draggable sections
const draggableSectionKeys = computed(() => draggableSections.value.map((s) => s.key));
const showResolveDropZone = computed(() =>
  !isPreviewLocked.value && state.isAdmin && dragContext.value?.type === "container"
);
const containerEditorMembers = computed(() => getContainerMembersById(containerEditor.value?.containerId));

function getCanonicalDraggableOrder() {
  return getNormalizedDraggableOrder();
}

function normalizeContainerMemberKeys(keys = [], allowedOrder = []) {
  const allowed = new Set(Array.isArray(allowedOrder) ? allowedOrder : []);
  const result = [];
  for (const key of Array.isArray(keys) ? keys : []) {
    if (!key) continue;
    if (allowed.size > 0 && !allowed.has(key)) continue;
    if (!result.includes(key)) result.push(key);
  }
  return result;
}

function getContainerMembersById(containerId, explicitOrder = null) {
  const normalizedContainerId = String(containerId || "").trim();
  if (!normalizedContainerId) return [];

  const canonicalOrder = getCanonicalDraggableOrder();
  const order = Array.isArray(explicitOrder) && explicitOrder.length
    ? normalizeContainerMemberKeys(explicitOrder, canonicalOrder)
    : canonicalOrder;
  if (!order.length) return [];

  const maps = buildSectionContainerMaps(order, state.landingLayout?.structure || [], state.sectionIds || {});
  const fromMaps = normalizeContainerMemberKeys(
    maps.containersById?.[normalizedContainerId]?.members || [],
    order
  );
  return fromMaps;
}

function hasContainerById(containerId, explicitOrder = null) {
  const normalizedContainerId = String(containerId || "").trim();
  if (!normalizedContainerId) return false;

  const canonicalOrder = getCanonicalDraggableOrder();
  const order = Array.isArray(explicitOrder) && explicitOrder.length
    ? normalizeContainerMemberKeys(explicitOrder, canonicalOrder)
    : canonicalOrder;
  if (!order.length) return false;

  const maps = buildSectionContainerMaps(order, state.landingLayout?.structure || [], state.sectionIds || {});
  return Boolean(maps.containersById?.[normalizedContainerId]);
}

function getSectionOverride(sectionKey) {
  const overrides = state.sectionDesignOverrides?.[sectionKey];
  return overrides && typeof overrides === "object" ? overrides : null;
}

function isContainerStructureLocked(entryOrKeys) {
  const keys = Array.isArray(entryOrKeys)
    ? entryOrKeys
    : getEntrySectionKeys(entryOrKeys);
  if (!keys.length) return false;
  return keys.every((key) => Boolean(getSectionOverride(key)?.[CONTAINER_TEMPLATE_LOCK_KEY]));
}

function getContainerTemplateName(entryOrKeys) {
  if (entryOrKeys && typeof entryOrKeys === "object" && !Array.isArray(entryOrKeys)) {
    const direct = String(entryOrKeys.templateName || "").trim();
    if (direct) return direct;
  }

  const keys = Array.isArray(entryOrKeys)
    ? entryOrKeys
    : getEntrySectionKeys(entryOrKeys);
  for (const key of keys) {
    const name = String(getSectionOverride(key)?.[CONTAINER_TEMPLATE_NAME_KEY] || "").trim();
    if (name) {
      const containerId = String(entryOrKeys?.containerId || "").trim();
      if (containerId) {
        containerTemplateNameCache.value[containerId] = name;
      }
      return name;
    }
  }

  const containerId = String(entryOrKeys?.containerId || "").trim();
  if (containerId) {
    const cached = String(containerTemplateNameCache.value?.[containerId] || "").trim();
    if (cached) return cached;
  }
  return "";
}

function toContainerEditorDraft(memberKeys = []) {
  return (Array.isArray(memberKeys) ? memberKeys : []).map((key) => ({ key }));
}

function fromContainerEditorDraft(entries = containerEditorDraftMembers.value) {
  const keys = [];
  for (const entry of entries || []) {
    const key = String(entry?.key || "").trim();
    if (key && !keys.includes(key)) keys.push(key);
  }
  return keys;
}

function syncContainerEditorDraftFromSource(containerId = containerEditor.value?.containerId, fallbackMembers = null) {
  const normalizedContainerId = String(containerId || "").trim();
  if (!normalizedContainerId) {
    containerEditorDraftMembers.value = [];
    return;
  }
  const liveMembers = getContainerMembersById(normalizedContainerId);
  if (liveMembers.length > 0) {
    containerEditorDraftMembers.value = toContainerEditorDraft(liveMembers);
    return;
  }
  if (!Array.isArray(fallbackMembers)) {
    containerEditorDraftMembers.value = [];
    return;
  }
  const fallback = normalizeContainerMemberKeys(
    fallbackMembers,
    getCanonicalDraggableOrder()
  );
  containerEditorDraftMembers.value = toContainerEditorDraft(fallback);
}

// Get label for a section key
function getSectionName(key) {
  // Get section metadata
  const meta = state.sectionMeta?.[key];
  
  const section = state.sectionsData?.[key];
  
  // Get the section title
  if (section?.title) {
    const title = localizedText(section.title);
    if (title && title.trim()) {
      return title;
    }
  }
  
  // Fallback: use titlePlaceholder from metadata
  if (meta?.titlePlaceholder) {
    return meta.titlePlaceholder;
  }
  
  // Last resort: format key as readable label
  return key
    .replace(/_[a-f0-9]+$/i, '')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, str => str.toUpperCase())
    .trim();
}

// Get the section type icon
function getSectionIcon(key) {
  const meta = state.sectionMeta?.[key];
  const sectionType = meta?.sectionType;
  return getTypeIcon(sectionType || key);
}

function getSectionLabel(key) {
  return getSectionName(key);
}

function getSectionDataByKey(key) {
  return state.sectionsData?.[key] || null;
}

// Check if section is hidden
function isHidden(key) {
  return pageLayout.value.hidden?.[key] === true;
}

function getNormalizedDraggableOrder() {
  const keys = draggableSectionKeys.value;
  const currentOrder = Array.isArray(pageLayout.value.order) ? pageLayout.value.order : [];
  const normalized = currentOrder.filter((k) => keys.includes(k));
  for (const key of keys) {
    if (!normalized.includes(key)) normalized.push(key);
  }
  return normalized;
}

function buildEntriesFromOrder(order) {
  const safeOrder = Array.isArray(order) ? order : [];
  const maps = buildSectionContainerMaps(safeOrder, state.landingLayout?.structure || [], state.sectionIds || {});
  const entries = [];
  const nodes = Array.isArray(maps.nodes) ? maps.nodes : [];
  for (const node of nodes) {
    if (!node || typeof node !== "object") continue;
    if (node.type === "container") {
      const containerId = String(node.containerId || "").trim();
      const members = normalizeContainerMemberKeys(node.members || [], safeOrder);
      if (!containerId || members.length < 2) {
        for (const key of members) {
          entries.push({ id: `section:${key}`, type: "section", key });
        }
        continue;
      }
      const templateName = getContainerTemplateName({ type: "container", containerId, members });
      if (templateName) {
        containerTemplateNameCache.value[containerId] = templateName;
      }
      entries.push({
        id: `container:${containerId}`,
        type: "container",
        containerId,
        members,
        templateName: templateName || String(containerTemplateNameCache.value?.[containerId] || "").trim() || "",
      });
      continue;
    }
    const key = String(node.key || "").trim();
    if (!key) continue;
    entries.push({ id: `section:${key}`, type: "section", key });
  }
  return entries;
}

function flattenDraggableEntries(entries = draggableEntryDraft.value) {
  const keys = [];
  for (const entry of entries || []) {
    if (entry?.type === "container") {
      for (const member of entry.members || []) {
        if (!keys.includes(member)) keys.push(member);
      }
      continue;
    }
    if (entry?.key && !keys.includes(entry.key)) keys.push(entry.key);
  }
  return keys;
}

function buildStructureFromEntries(entries, fallbackOrder = null) {
  const normalizedFallbackOrder = Array.isArray(fallbackOrder) && fallbackOrder.length
    ? normalizeContainerMemberKeys(fallbackOrder, getCanonicalDraggableOrder())
    : getCanonicalDraggableOrder();
  return buildSectionStructureFromEntries(
    entries || [],
    state.sectionIds || {},
    normalizedFallbackOrder,
  );
}

async function persistDraggableEntries(entries, fallbackOrder = null) {
  if (isPreviewLocked.value) {
    refreshDraggableEntryDraft();
    return;
  }
  const structure = buildStructureFromEntries(entries, fallbackOrder);
  const pageData = await setSectionStructure(structure, props.pageSlug);
  emitTemplatePayloadUpdate(pageData);
  refreshDraggableEntryDraft();
}

function refreshDraggableEntryDraft() {
  draggableEntryDraft.value = buildEntriesFromOrder(getNormalizedDraggableOrder());
}

function getDraggableLayoutSignature() {
  return JSON.stringify({
    order: getNormalizedDraggableOrder(),
    structure: Array.isArray(state.landingLayout?.structure) ? state.landingLayout.structure : [],
    sectionIds: state.sectionIds || {},
  });
}

function getEntrySectionKeys(entry) {
  if (!entry) return [];
  if (entry.type === "container") return Array.isArray(entry.members) ? [...entry.members] : [];
  if (entry.type === "section" && entry.key) return [entry.key];
  return [];
}

function openContainerEditor(entry) {
  if (isPreviewLocked.value) return;
  if (!entry || entry.type !== "container" || !entry.containerId) return;
  if (isContainerStructureLocked(entry)) return;
  const memberFallback = normalizeContainerMemberKeys(
    Array.isArray(entry.members) ? entry.members : [],
    getCanonicalDraggableOrder()
  );
  containerEditor.value = { containerId: entry.containerId, memberFallback };
  syncContainerEditorDraftFromSource(entry.containerId, memberFallback);
}

function closeContainerEditor() {
  containerEditor.value = null;
  containerEditorDraftMembers.value = [];
}

async function unlinkSectionFromContainer(containerId, sectionKey) {
  if (isPreviewLocked.value) return;
  const normalizedContainerId = String(containerId || "").trim();
  if (!normalizedContainerId || !sectionKey) return;

  const order = flattenDraggableEntries(draggableEntryDraft.value);
  const maps = buildSectionContainerMaps(order, state.landingLayout?.structure || [], state.sectionIds || {});
  const members = (maps.containersById?.[normalizedContainerId]?.members || []).filter((key) => order.includes(key));
  if (!members.includes(sectionKey)) return;
  if (isContainerStructureLocked(members)) return;

  const remainingMembers = members.filter((key) => key !== sectionKey);
  const entries = cloneSerializable(draggableEntryDraft.value);
  const entryIndex = entries.findIndex(
    (entry) => entry?.type === "container" && String(entry.containerId || "").trim() === normalizedContainerId
  );
  if (entryIndex < 0) return;

  if (remainingMembers.length < 2) {
    entries.splice(
      entryIndex,
      1,
      ...members.map((key) => ({ id: `section:${key}`, type: "section", key }))
    );
  } else {
    entries[entryIndex] = {
      ...entries[entryIndex],
      members: remainingMembers,
    };
  }
  await persistDraggableEntries(entries, flattenDraggableEntries(entries));

  refreshDraggableEntryDraft();
  syncContainerEditorDraftFromSource(normalizedContainerId);
  if (remainingMembers.length < 2) {
    closeContainerEditor();
  }
}

async function removeSectionFromContainerTemplate(sectionKey) {
  if (isPreviewLocked.value) return;
  await removeFromPage(sectionKey);
  if (containerEditor.value) {
    const containerId = String(containerEditor.value.containerId || "").trim();
    syncContainerEditorDraftFromSource(containerId);
    if (containerId && !hasContainerById(containerId)) {
      closeContainerEditor();
    }
  }
}

async function onContainerEditorMemberDetach(containerId, sectionKey) {
  if (isContainerTemplateBuilderContext.value) {
    await removeSectionFromContainerTemplate(sectionKey);
    return;
  }
  await unlinkSectionFromContainer(containerId, sectionKey);
}

async function onContainerEditorDragEnd() {
  if (isPreviewLocked.value) {
    syncContainerEditorDraftFromSource();
    return;
  }
  if (!state.isAdmin) {
    syncContainerEditorDraftFromSource();
    return;
  }

  const containerId = String(containerEditor.value?.containerId || "").trim();
  if (!containerId) return;

  const currentMembers = getContainerMembersById(containerId);
  const nextMembers = fromContainerEditorDraft();
  if (currentMembers.length < 2 || nextMembers.length < 2) {
    syncContainerEditorDraftFromSource(containerId);
    return;
  }

  const sameSet = nextMembers.length === currentMembers.length
    && nextMembers.every((key) => currentMembers.includes(key));
  if (!sameSet) {
    syncContainerEditorDraftFromSource(containerId);
    return;
  }

  const unchanged = nextMembers.every((key, index) => key === currentMembers[index]);
  if (unchanged) return;

  const entries = cloneSerializable(draggableEntryDraft.value);
  const entryIndex = entries.findIndex(
    (entry) => entry?.type === "container" && String(entry.containerId || "").trim() === containerId
  );
  if (entryIndex < 0) {
    syncContainerEditorDraftFromSource(containerId);
    return;
  }
  entries[entryIndex] = {
    ...entries[entryIndex],
    members: [...nextMembers],
  };
  await persistDraggableEntries(entries, flattenDraggableEntries(entries));
  syncContainerEditorDraftFromSource(containerId);
}

function getEntryPrimaryKey(entry) {
  return getEntrySectionKeys(entry)[0] || null;
}

function getEntryName(entry) {
  if (!entry) return "";
  if (entry.type === "container") {
    const templateName = getContainerTemplateName(entry);
    if (templateName) return templateName;
    return "Container";
  }
  return getSectionName(entry.key);
}

function getEntryIcon(entry) {
  if (!entry) return faFileLines;
  if (entry.type === "container") return faPuzzlePiece;
  return getSectionIcon(entry.key);
}

function isEntryHidden(entry) {
  const primary = getEntryPrimaryKey(entry);
  if (!primary) return false;
  return isHidden(primary);
}

function isEntryHiddenForCurrentView(entry) {
  const primary = getEntryPrimaryKey(entry);
  if (!primary) return false;
  return isHiddenForCurrentView(primary);
}

function getEntryDeviceVisibility(entry, device) {
  const primary = getEntryPrimaryKey(entry);
  if (!primary) return true;
  return getSectionDeviceVisibility(primary, device);
}

async function setSectionVisible(sectionKey, visible) {
  if (isPreviewLocked.value) return null;
  if (!sectionKey) return null;
  if (!state.landingLayout.hidden) state.landingLayout.hidden = {};
  state.landingLayout.hidden[sectionKey] = !visible;
  const sectionId = state.sectionIds?.[sectionKey];
  if (!sectionId) return null;
  try {
    return await api.updatePageSectionRef(props.pageSlug, sectionId, { visible });
  } catch (err) {
    console.error(`Failed to update section visibility for ${sectionKey}:`, err);
    return null;
  }
}

function emitTemplatePayloadUpdate(pageData) {
  if (!props.templateMode || !pageData || typeof pageData !== "object") return;
  if (!Array.isArray(pageData.sections)) return;
  emit("template-updated", pageData);
}

async function toggleEntryHidden(entry) {
  if (isPreviewLocked.value) return;
  if (!state.isAdmin) return;
  const keys = getEntrySectionKeys(entry);
  if (!keys.length) return;
  const nextVisible = isEntryHidden(entry);
  let latestPageData = null;
  for (const key of keys) {
    const pageData = await setSectionVisible(key, nextVisible);
    if (pageData) latestPageData = pageData;
  }
  emitTemplatePayloadUpdate(latestPageData);
}

async function toggleEntryDevice(entry, device) {
  if (isPreviewLocked.value) return;
  const keys = getEntrySectionKeys(entry);
  if (!keys.length) return;
  const current = getEntryDeviceVisibility(entry, device);
  for (const key of keys) {
    await setSectionDeviceVisibility(key, device, !current, props.pageSlug);
  }
}

function cloneSerializable(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

function getSharedSectionGeneric(key) {
  const section = getSectionDataByKey(key);
  const generic = section?.sectionGeneric;
  if (!generic || typeof generic !== "object") return {};
  const shared = {};
  for (const constantKey of SHARED_SECTION_GENERIC_KEYS) {
    if (generic[constantKey] === true) shared[constantKey] = true;
  }
  return shared;
}

function getSharedContainerOverrideTemplate(sourceKey) {
  return cloneSerializable(state.sectionDesignOverrides?.[sourceKey] || {}) || {};
}

function getDeviceVisibilitySnapshot(sectionKey) {
  const source = state.landingLayout?.deviceVisibility?.[sectionKey];
  return {
    mobile: source?.mobile !== false,
    tablet: source?.tablet !== false,
    desktop: source?.desktop !== false,
  };
}

async function syncContainerSharedState(members, sourceKey) {
  if (!Array.isArray(members) || members.length === 0 || !sourceKey) return;
  if (!state.sectionDesignOverrides || typeof state.sectionDesignOverrides !== "object") {
    state.sectionDesignOverrides = {};
  }

  const sourceHidden = state.landingLayout?.hidden?.[sourceKey] === true;
  const sourceDeviceVisibility = getDeviceVisibilitySnapshot(sourceKey);
  const sharedGeneric = getSharedSectionGeneric(sourceKey);
  const sharedOverrideTemplate = getSharedContainerOverrideTemplate(sourceKey);
  const visibilitySaveTasks = [];
  const genericSaveKeys = [];
  const overrideSaveKeys = [];

  for (const key of members) {
    if (!state.landingLayout.hidden) state.landingLayout.hidden = {};
    state.landingLayout.hidden[key] = sourceHidden;
    visibilitySaveTasks.push(() => setSectionVisible(key, !sourceHidden));

    for (const device of ["mobile", "tablet", "desktop"]) {
      visibilitySaveTasks.push(() => setSectionDeviceVisibility(key, device, sourceDeviceVisibility[device], props.pageSlug));
    }

    const section = getSectionDataByKey(key);
    const currentGeneric = (section?.sectionGeneric && typeof section.sectionGeneric === "object")
      ? section.sectionGeneric
      : {};
    const nextGenericJson = JSON.stringify(sharedGeneric);
    if (JSON.stringify(currentGeneric) !== nextGenericJson) {
      updateSection(key, { sectionGeneric: { ...sharedGeneric } }, { revisionKind: "design" });
      genericSaveKeys.push(key);
    }

    state.sectionDesignOverrides[key] = cloneSerializable(sharedOverrideTemplate);
    overrideSaveKeys.push(key);
  }

  // Important: keep page-section writes sequential.
  // The backend updates section refs via read-modify-write on the entire page.sections array,
  // so parallel requests can overwrite each other and drop earlier container ids.
  for (const task of visibilitySaveTasks) {
    await task();
  }
  for (const key of genericSaveKeys) {
    await saveSectionByKey(key, { revisionKind: "design" });
  }
  for (const key of overrideSaveKeys) {
    await saveSectionDesignOverrides(key, props.pageSlug);
  }
}

function createContainerId() {
  return `container_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function canLinkToEntry(entry) {
  if (isPreviewLocked.value) return false;
  if (!state.isAdmin || !dragContext.value) return false;
  if (!entry || !entry.id) return false;
  if (entry.id === dragContext.value.id) return false;
  if (isContainerStructureLocked(entry) || isContainerStructureLocked(dragContext.value)) return false;
  if (entry.type === "container" && dragContext.value.type === "container" && entry.containerId === dragContext.value.containerId) {
    return false;
  }
  return true;
}

function isDropSplitVisible(entry) {
  if (isPreviewLocked.value) return false;
  if (!dragContext.value || !entry?.id) return false;
  if (entry.id === dragContext.value.id) return false;
  return true;
}

function isLinkHover(entry) {
  return dragHoverIntent.value?.mode === "link" && dragHoverIntent.value?.entryId === entry?.id;
}

function getEntryById(entryId) {
  if (!entryId) return null;
  return draggableEntryDraft.value.find((entry) => entry?.id === entryId) || null;
}

function getPointerCoordinates(rawEvent) {
  if (!rawEvent) return null;
  if (rawEvent.clientX != null && rawEvent.clientY != null) {
    return { clientX: rawEvent.clientX, clientY: rawEvent.clientY };
  }
  const touch = rawEvent.touches?.[0] || rawEvent.changedTouches?.[0];
  if (touch?.clientX != null && touch?.clientY != null) {
    return { clientX: touch.clientX, clientY: touch.clientY };
  }
  return null;
}

function trackDragPointer(rawEvent) {
  const point = getPointerCoordinates(rawEvent);
  if (point) dragPointer.value = point;
  return point;
}

function getDragTargetFromElement(element) {
  const targetEl = element?.closest?.("[data-entry-id]");
  if (!targetEl) return null;
  const entryId = targetEl.getAttribute("data-entry-id");
  const entry = getEntryById(entryId);
  if (!entry) return null;
  return { entry, el: targetEl };
}

function getDragTargetFromPointer(point) {
  if (!point || typeof document === "undefined" || typeof document.elementFromPoint !== "function") {
    return null;
  }
  const hoveredEl = document.elementFromPoint(point.clientX, point.clientY);
  return getDragTargetFromElement(hoveredEl);
}

function resolveDragTarget(evt, pointerPoint) {
  const relatedEntry = evt?.relatedContext?.element || null;
  const relatedEl = evt?.related || null;
  if (relatedEntry && relatedEl) return { entry: relatedEntry, el: relatedEl };
  const fromRelatedElement = getDragTargetFromElement(relatedEl);
  if (fromRelatedElement) return fromRelatedElement;
  return getDragTargetFromPointer(pointerPoint || dragPointer.value);
}

function getDragModeForTarget(point, targetEl) {
  if (point?.clientX == null || !targetEl?.getBoundingClientRect) return "reorder";
  const rect = targetEl.getBoundingClientRect();
  if (!rect?.width) return "reorder";
  const relativeX = (point.clientX - rect.left) / rect.width;
  return relativeX >= 0.5 ? "link" : "reorder";
}

function clearDragHover() {
  dragHoverIntent.value = null;
  dragLastLinkEntryId.value = "";
}

function updateDragIntentFromPointer(rawEvent) {
  if (isPreviewLocked.value) return "reorder";
  if (!dragContext.value || !state.isAdmin) return "reorder";
  const point = trackDragPointer(rawEvent);
  const target = getDragTargetFromPointer(point);
  if (!target) {
    clearDragHover();
    return "reorder";
  }
  const mode = getDragModeForTarget(point, target.el);
  if (mode === "link" && canLinkToEntry(target.entry)) {
    dragHoverIntent.value = { mode: "link", entryId: target.entry.id };
    dragLastLinkEntryId.value = target.entry.id;
    return "link";
  }
  clearDragHover();
  return "reorder";
}

function onGlobalDragPointerMove(event) {
  updateDragIntentFromPointer(event);
}

function bindDragPointerListeners() {
  if (typeof window === "undefined") return;
  window.addEventListener("pointermove", onGlobalDragPointerMove, true);
  window.addEventListener("dragover", onGlobalDragPointerMove, true);
}

function unbindDragPointerListeners() {
  if (typeof window === "undefined") return;
  window.removeEventListener("pointermove", onGlobalDragPointerMove, true);
  window.removeEventListener("dragover", onGlobalDragPointerMove, true);
}

function buildLinkActionFromTarget(targetEntry) {
  if (!dragContext.value || !targetEntry || !canLinkToEntry(targetEntry)) return null;
  return {
    type: "link",
    sourceEntry: cloneSerializable(dragContext.value),
    targetEntry: cloneSerializable(targetEntry),
  };
}

function onDragStart(evt) {
  if (isPreviewLocked.value) return;
  const oldIndex = Number(evt?.oldIndex);
  const sourceEntry = Number.isInteger(oldIndex) ? draggableEntryDraft.value[oldIndex] : null;
  dragContext.value = cloneSerializable(sourceEntry);
  dragStartOrder.value = flattenDraggableEntries(draggableEntryDraft.value);
  dragLastLinkEntryId.value = "";
  dragPointer.value = null;
  dragHoverIntent.value = null;
  resolveDropActive.value = false;
  pendingDropAction.value = null;
  bindDragPointerListeners();
}

function onDragMove(evt, originalEvent) {
  if (isPreviewLocked.value) return false;
  if (!dragContext.value || !state.isAdmin) return true;
  const pointerPoint = trackDragPointer(originalEvent || evt?.originalEvent || evt);
  const target = resolveDragTarget(evt, pointerPoint);
  if (!target) {
    clearDragHover();
    return true;
  }
  const relatedEntry = target.entry;
  const relatedEl = target.el;

  const mode = getDragModeForTarget(pointerPoint || dragPointer.value, relatedEl);

  if (mode === "link") {
    if (canLinkToEntry(relatedEntry)) {
      dragHoverIntent.value = { mode: "link", entryId: relatedEntry.id };
      dragLastLinkEntryId.value = relatedEntry.id;
    } else {
      dragHoverIntent.value = null;
      dragLastLinkEntryId.value = "";
    }
    // Right side is reserved for linking: cancel sortable move so order does not change.
    return false;
  }

  clearDragHover();
  return true;
}

function onResolveDragOver() {
  if (isPreviewLocked.value) return;
  if (!showResolveDropZone.value) return;
  resolveDropActive.value = true;
}

function onResolveDragLeave() {
  resolveDropActive.value = false;
}

function onResolveDrop() {
  if (isPreviewLocked.value) return;
  if (!showResolveDropZone.value || !dragContext.value?.containerId) return;
  pendingDropAction.value = {
    type: "resolve",
    containerId: dragContext.value.containerId,
  };
  resolveDropActive.value = false;
}

async function applyLinkAction(action) {
  if (isPreviewLocked.value) return;
  const sourceEntry = action?.sourceEntry;
  const targetEntry = action?.targetEntry;
  if (!sourceEntry || !targetEntry) return;

  const sourceKeys = getEntrySectionKeys(sourceEntry);
  const targetKeys = getEntrySectionKeys(targetEntry);
  if (!sourceKeys.length || !targetKeys.length) return;

  const uniqueSourceKeys = sourceKeys.filter((key) => !targetKeys.includes(key));
  if (!uniqueSourceKeys.length) return;

  let containerId = targetEntry.containerId || sourceEntry.containerId || "";
  if (!containerId) containerId = createContainerId();

  const linkedKeys = [...new Set([...targetKeys, ...uniqueSourceKeys])];
  const anchorKey = targetKeys[0] || linkedKeys[0];

  const entries = cloneSerializable(draggableEntryDraft.value);
  const sourceIndex = entries.findIndex((entry) => entry?.id === sourceEntry.id);
  const targetIndex = entries.findIndex((entry) => entry?.id === targetEntry.id);
  if (targetIndex < 0) return;

  if (sourceIndex >= 0) {
    entries.splice(sourceIndex, 1);
  }
  const adjustedTargetIndex = entries.findIndex((entry) => entry?.id === targetEntry.id);
  if (adjustedTargetIndex < 0) return;
  const templateName = getContainerTemplateName({
    type: "container",
    containerId,
    members: linkedKeys,
  });
  if (templateName) {
    containerTemplateNameCache.value[containerId] = templateName;
  }
  entries[adjustedTargetIndex] = {
    id: `container:${containerId}`,
    type: "container",
    containerId,
    members: linkedKeys,
    templateName: templateName || String(containerTemplateNameCache.value?.[containerId] || "").trim() || "",
  };
  await persistDraggableEntries(entries, flattenDraggableEntries(entries));

  try {
    await syncContainerSharedState(linkedKeys, anchorKey);
  } catch (err) {
    console.error("Failed to sync shared container state after merge:", err);
  }
}

async function applyResolveAction(action) {
  if (isPreviewLocked.value) return;
  const containerId = String(action?.containerId || "").trim();
  if (!containerId) return;
  const order = flattenDraggableEntries(draggableEntryDraft.value);
  const maps = buildSectionContainerMaps(order, state.landingLayout?.structure || [], state.sectionIds || {});
  const members = maps.containersById?.[containerId]?.members || [];
  if (members.length < 2) return;
  if (isContainerStructureLocked(members)) return;
  const entries = cloneSerializable(draggableEntryDraft.value);
  const entryIndex = entries.findIndex(
    (entry) => entry?.type === "container" && String(entry.containerId || "").trim() === containerId
  );
  if (entryIndex < 0) return;
  entries.splice(
    entryIndex,
    1,
    ...members.map((key) => ({ id: `section:${key}`, type: "section", key }))
  );
  await persistDraggableEntries(entries, flattenDraggableEntries(entries));
}

// Watch for panel open/close
watch(
  () => open.value,
  (isOpen) => {
    if (!isOpen) return;
    refreshDraggableEntryDraft();
  }
);

// Also watch for changes in draggable sections (when page data loads)
watch(
  () => draggableSectionKeys.value,
  () => {
    if (open.value) refreshDraggableEntryDraft();
  },
  { immediate: true }
);

watch(
  () => getDraggableLayoutSignature(),
  () => {
    if (!open.value || dragContext.value) return;
    refreshDraggableEntryDraft();
    if (containerEditor.value) {
      syncContainerEditorDraftFromSource();
      if (!hasContainerById(containerEditor.value.containerId)) {
        closeContainerEditor();
      }
    }
  },
  { flush: "post" }
);

watch(
  () => containerEditorMembers.value.length,
  (count) => {
    if (!containerEditor.value) return;
    if (count === 0) {
      syncContainerEditorDraftFromSource();
      if (!hasContainerById(containerEditor.value.containerId)) {
        closeContainerEditor();
      }
      return;
    }
    syncContainerEditorDraftFromSource();
  }
);

watch(isPreviewLocked, (locked) => {
  if (!locked) return;
  showPinDialog.value = false;
  showAddDialog.value = false;
  showHeaderDialog.value = false;
  closeContainerEditor();
  unbindDragPointerListeners();
  pendingDropAction.value = null;
  clearDragHover();
  dragPointer.value = null;
  resolveDropActive.value = false;
  dragContext.value = null;
  dragStartOrder.value = [];
  refreshDraggableEntryDraft();
});

function toggleOpen() {
  open.value = !open.value;
}

async function toggleHidden(k) {
  if (isPreviewLocked.value) return;
  if (!state.isAdmin) return;
  const pageData = await setSectionVisible(k, isHidden(k));
  emitTemplatePayloadUpdate(pageData);
}

function isBlog(k) {
  return state.sectionMeta?.[k]?.sectionType === "blog";
}

function getWidthN(k) {
  return state.landingLayout.widths?.[k]?.n ?? 1;
}

function getWidthD(k) {
  return state.landingLayout.widths?.[k]?.d ?? 1;
}

function getMaxN(k) {
  return getWidthD(k);
}

function onWidthNChange(k, n) {
  if (isPreviewLocked.value) return;
  const d = getWidthD(k);
  void setSectionWidth(k, { n: Math.min(n, d), d }, props.pageSlug);
}

function onWidthDChange(k, d) {
  if (isPreviewLocked.value) return;
  const n = Math.min(getWidthN(k), d);
  void setSectionWidth(k, { n, d }, props.pageSlug);
}

function getSectionLimit(k) {
  const section = state.sectionsData?.[k];
  if (!section) return null;
  const lim = Number(section.limit);
  return Number.isInteger(lim) && lim > 0 ? lim : null;
}

function setSectionLimit(k, limit) {
  if (isPreviewLocked.value) return;
  if (!state.isAdmin) return;
  const parsed = Number(limit);
  const normalizedLimit = Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  updateSectionLimit(props.pageSlug, k, normalizedLimit);
}

// Called when vuedraggable finishes reordering
async function onDragEnd(evt) {
  if (isPreviewLocked.value) {
    unbindDragPointerListeners();
    pendingDropAction.value = null;
    clearDragHover();
    dragPointer.value = null;
    resolveDropActive.value = false;
    dragContext.value = null;
    dragStartOrder.value = [];
    refreshDraggableEntryDraft();
    return;
  }
  let pendingAction = pendingDropAction.value;
  if (!pendingAction && dragHoverIntent.value?.mode === "link" && dragContext.value) {
    const targetEntry = getEntryById(dragHoverIntent.value.entryId);
    pendingAction = buildLinkActionFromTarget(targetEntry);
  }
  if (!pendingAction && dragLastLinkEntryId.value && dragContext.value) {
    const targetEntry = getEntryById(dragLastLinkEntryId.value);
    pendingAction = buildLinkActionFromTarget(targetEntry);
  }
  if (!pendingAction && dragContext.value) {
    const pointerPoint = trackDragPointer(evt?.originalEvent || evt);
    const target = resolveDragTarget(evt, pointerPoint);
    if (target) {
      const mode = getDragModeForTarget(pointerPoint || dragPointer.value, target.el);
      if (mode === "link") {
        pendingAction = buildLinkActionFromTarget(target.entry);
      }
    }
  }
  unbindDragPointerListeners();
  pendingDropAction.value = null;
  clearDragHover();
  dragPointer.value = null;
  resolveDropActive.value = false;
  dragContext.value = null;

  if (!state.isAdmin) {
    dragStartOrder.value = [];
    return;
  }
  if (pendingAction?.type === "link") {
    await applyLinkAction(pendingAction);
    dragStartOrder.value = [];
    refreshDraggableEntryDraft();
    return;
  }
  if (pendingAction?.type === "resolve") {
    await applyResolveAction(pendingAction);
    dragStartOrder.value = [];
    refreshDraggableEntryDraft();
    return;
  }

  const nextEntries = cloneSerializable(draggableEntryDraft.value);
  await persistDraggableEntries(nextEntries, flattenDraggableEntries(nextEntries));
  dragStartOrder.value = [];
  refreshDraggableEntryDraft();
}

// -------------------------
// Exposed Methods
// -------------------------

function openHeaderDialog(tab = 'new') {
  if (isPreviewLocked.value) return;
  headerTab.value = tab;
  showHeaderDialog.value = true;
}

function openSectionsDialog(tab = 'templates') {
  if (isPreviewLocked.value) return;
  open.value = true;
  activeTab.value = tab;
  showAddDialog.value = true;
}

onBeforeUnmount(() => {
  unbindDragPointerListeners();
});

defineExpose({
  openHeaderDialog,
  openSectionsDialog,
});
</script>

<style scoped>
.wrap {
  position: fixed;
  z-index: 80;
  max-width: calc(100vw - 10px);
}
.wrap.corner-bottom-left {
  left: 5px;
  bottom: 5px;
}
.wrap.corner-bottom-right {
  right: 5px;
  bottom: 5px;
}
.wrap.corner-top-left {
  left: 5px;
  top: 5px;
}
.wrap.corner-top-right {
  right: 5px;
  top: 5px;
}
.wrap.open {
  z-index: 300;
}

.wrap:not(.open) .body {
  display: none;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px;
  cursor: pointer;
  user-select: none;
}

.title {
  font-weight: 900;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.head-toggle-btn {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border, rgba(15, 23, 42, 0.18));
  border-radius: 8px;
  background: #fff;
  color: var(--muted, #64748b);
  cursor: pointer;
  transition: all 0.15s ease;
}

.head-toggle-btn:hover,
.head-toggle-btn.active {
  border-color: var(--accent, #4f46e5);
  background: color-mix(in srgb, var(--accent, #4f46e5) 10%, #fff);
  color: var(--accent, #4f46e5);
}

.chev {
  color: var(--muted);
  font-weight: 900;
}

/* Body smooth collapse */
.body {
  padding: 2px 12px 12px;
  max-height: 0;
  opacity: 0;
  transform: translateY(-4px);
  transition: max-height 220ms ease, opacity 180ms ease, transform 180ms ease;
}

.wrap.open .body {
  max-height: 70vh;
  opacity: 1;
  transform: translateY(0);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.hint {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.4;
}

/* List */
.list {
  display: grid;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
  overflow-y: auto;
  min-height: 0;
}

.list-inner {
  display: grid;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
}

.item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
  padding: 10px 10px;
  border-radius: 12px;
  background: var(--surface-2);
  user-select: none;
}

.item.dragging {
  opacity: 0.65;
}

.item.fixed {
  opacity: 1;
}

.item-left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1 1 0;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
}

.section-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.section-name {
  display: block;
  flex: 1 1 auto;
  min-width: 0;
  max-width: 100%;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.entry-labels {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1 1 auto;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
}

.container-item {
  background: color-mix(in srgb, var(--accent, #5b2fe3) 8%, var(--surface-2));
}

.container-members {
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
}

.container-member-chip {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  max-width: 100%;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 700;
  border-radius: 999px;
  background: rgba(79, 70, 229, 0.14);
  color: #4338ca;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pin-handle {
  color: rgba(15, 23, 42, 0.35);
  font-weight: 900;
  padding: 4px;
  flex-shrink: 0;
}

.name {
  font-weight: 700;
}

.item-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
  min-width: 0;
  max-width: 176px;
}

.visibility-check {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.visibility-check input {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--accent, #4f46e5);
}

.width-ratio {
  display: flex;
  align-items: center;
  gap: 2px;
}

.ratio-select {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: 1px solid var(--border, rgba(15, 23, 42, 0.2));
  background: #fff;
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
  text-align: center;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
}

.ratio-select:focus {
  outline: none;
  border-color: var(--accent, #4f46e5);
}

.ratio-slash {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted, #64748b);
  user-select: none;
}

.limit-toggle {
  display: flex;
  gap: 2px;
  align-items: center;
}

.limit-btn {
  padding: 2px 8px;
  font-size: 11px;
  border-radius: 6px;
  border: 1px solid var(--border, rgba(15, 23, 42, 0.2));
  background: rgba(255, 255, 255, 0.9);
  color: var(--muted, #64748b);
  cursor: pointer;
}

.limit-btn:hover {
  background: rgba(255, 255, 255, 1);
  color: var(--primary-color);
}

.limit-btn.active {
  background: var(--accent, #4f46e5);
  color: white;
  border-color: var(--accent);
}

.drag-handle {
  cursor: grab;
  color: rgba(15, 23, 42, 0.45);
  font-weight: 900;
  font-size: 14px;
  padding: 4px;
  letter-spacing: -2px;
  user-select: none;
  flex-shrink: 0;
}

.drag-handle:hover {
  color: rgba(15, 23, 42, 0.7);
}

.drag-handle:active {
  cursor: grabbing;
}

.drag-ghost {
  opacity: 0.5;
  background: rgba(79, 70, 229, 0.15) !important;
  border: 1px dashed rgba(79, 70, 229, 0.5);
}

.item.drop-split-visible {
  position: relative;
}

.item.drop-split-visible::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  background: linear-gradient(
    90deg,
    rgba(14, 116, 144, 0.07) 0%,
    rgba(14, 116, 144, 0.07) 50%,
    rgba(109, 40, 217, 0.07) 50%,
    rgba(109, 40, 217, 0.07) 100%
  );
}

.item.drag-link-target {
  outline: 2px dashed rgba(109, 40, 217, 0.65);
  outline-offset: 1px;
}

.resolve-drop-zone {
  margin-top: 8px;
  border: 1px dashed #f97316;
  border-radius: 10px;
  background: #fff7ed;
  color: #c2410c;
  font-size: 12px;
  font-weight: 700;
  padding: 10px;
  text-align: center;
}

.resolve-drop-zone.active {
  background: #ffedd5;
  border-style: solid;
}

.note {
  margin-top: 10px;
  font-size: 12px;
  color: var(--muted);
}

.empty {
  padding: 20px;
  text-align: center;
  color: var(--muted);
  font-size: 14px;
}

/* FLIP animation */
.reorder-move {
  transition: transform 170ms ease;
}

.add-hint {
  color: var(--accent, #5b2fe3);
}

/* Dialog Overlay */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
  animation: fadeIn 0.15s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.dialog {
  background: #fff;
  border-radius: 16px;
  width: 100%;
  max-width: 560px;
  max-height: 80vh;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.25);
  animation: slideUp 0.2s ease;
}

.dialog--add-section,
.dialog--manage-headers {
  display: flex;
  flex-direction: column;
}

@keyframes slideUp {
  from { 
    opacity: 0;
    transform: translateY(20px);
  }
  to { 
    opacity: 1;
    transform: translateY(0);
  }
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.dialog-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 900;
  color: var(--text);
}

.dialog-body {
  padding: 20px;
  max-height: calc(80vh - 80px);
  overflow-y: auto;
}

.dialog-body--add-section,
.dialog-body--manage-headers {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.tab {
  flex: 1;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  font-weight: 700;
  font-size: 14px;
  color: var(--text);
  cursor: pointer;
  transition: all 0.15s ease;
}

.tab:hover {
  background: var(--surface, #e5e7eb);
}

.tab.active {
  background: var(--accent, #5b2fe3);
  color: #fff;
  border-color: var(--accent, #5b2fe3);
}

.tab-content {
  animation: fadeIn 0.15s ease;
}

.dialog-body--add-section .tabs,
.dialog-body--manage-headers .tabs,
.tab-content--existing-sections > .tab-hint,
.tab-content--existing-sections > .filter-bar,
.tab-content--existing-sections > .loading-hint,
.tab-content--existing-sections > .empty-hint,
.tab-content--existing-sections > .section-pagination,
.tab-content--existing-headers > .tab-hint,
.tab-content--existing-headers > .filter-bar,
.tab-content--existing-headers > .loading-hint,
.tab-content--existing-headers > .empty-hint,
.tab-content--existing-headers > .section-pagination {
  flex-shrink: 0;
}

.tab-content--templates,
.tab-content--header-create {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.tab-content--existing-sections,
.tab-content--existing-headers {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.tab-hint {
  font-size: 14px;
  color: var(--muted);
  margin: 0 0 16px;
}

/* Template Grid */
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.template-type-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.template-type-card-wrap {
  display: grid;
  gap: 8px;
}

.template-type-card {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text);
  cursor: pointer;
  transition: all 0.15s ease;
}

.template-type-card:hover,
.template-type-card.expanded {
  border-color: var(--accent, #5b2fe3);
  background: color-mix(in srgb, var(--accent, #5b2fe3) 8%, white);
}

.template-type-card-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.template-type-icon {
  font-size: 17px;
}

.template-type-name {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
  text-align: left;
}

.template-version-count {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 2px 8px 2px 6px;
  border: 1px solid color-mix(in srgb, var(--accent, #5b2fe3) 25%, var(--border));
  color: color-mix(in srgb, var(--accent, #5b2fe3) 85%, #0f172a);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.template-version-info-icon {
  width: 14px;
  height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent, #5b2fe3) 12%, white);
  border: 1px solid color-mix(in srgb, var(--accent, #5b2fe3) 22%, var(--border));
  font-size: 10px;
  font-weight: 800;
  line-height: 1;
}

.template-version-collapse {
  display: grid;
  gap: 8px;
}

.template-version-btn {
  width: 100%;
  text-align: left;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
  padding: 8px 10px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.template-version-btn:hover {
  border-color: var(--accent, #5b2fe3);
  background: color-mix(in srgb, var(--accent, #5b2fe3) 10%, white);
}

.container-template-section {
  margin-top: 14px;
  display: grid;
  gap: 8px;
}

.template-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 16px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  cursor: pointer;
  transition: all 0.15s ease;
}

.template-card:hover {
  border-color: var(--accent, #5b2fe3);
  background: color-mix(in srgb, var(--accent, #5b2fe3) 8%, white);
  transform: translateY(-2px);
}

.template-icon {
  font-size: 32px;
}

.template-name {
  font-weight: 700;
  font-size: 13px;
  text-align: center;
  color: var(--text);
}

.template-card--container .template-name {
  font-size: 12px;
}

.template-meta {
  font-size: 11px;
  color: var(--muted);
}

/* Shared Sections List */
.existing-list {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.existing-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: left;
}

.existing-card:hover {
  border-color: var(--accent, #5b2fe3);
  background: color-mix(in srgb, var(--accent, #5b2fe3) 8%, white);
}

.existing-icon {
  font-size: 24px;
  flex: 0 0 28px;
  text-align: center;
}

.existing-info {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
}

.existing-name {
  font-weight: 700;
  font-size: 14px;
  color: var(--text);
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.existing-type {
  min-width: 0;
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.loading-hint,
.empty-hint {
  text-align: center;
  padding: 40px 20px;
  color: var(--muted);
  font-size: 14px;
}

/* Item actions (remove button, drag handle) */
.item-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.item.hidden {
  opacity: 0.6;
  background: var(--surface, #e5e7eb);
}

.item.hidden .name {
  text-decoration: line-through;
  color: var(--muted);
}

.item.hidden-current-view {
  opacity: 0.5;
  background: repeating-linear-gradient(
    45deg,
    var(--surface-2),
    var(--surface-2) 4px,
    var(--surface, #e5e7eb) 4px,
    var(--surface, #e5e7eb) 8px
  );
}

.item.hidden-current-view .name {
  color: var(--muted);
  font-style: italic;
}

/* Gradient Pins bottom button */
.pins-bottom-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px dashed #c7d2fe;
  background: #eef2ff;
  color: #4338ca;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.pins-bottom-btn:hover { background: #e0e7ff; border-style: solid; }
.pins-bottom-icon { font-size: 13px; }
.pins-bottom-badge {
  background: #4f46e5;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}

/* Pin dialog */
.pin-dialog { max-width: 480px; }

.pin-field {
  margin-bottom: 12px;
}

.pin-field-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--admin-text, #0f172a);
  margin-bottom: 5px;
}

.pin-select {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 13px;
  cursor: pointer;
}
.pin-select:focus { outline: none; border-color: #4f46e5; }

.pin-field-row {
  display: grid;
  margin-top: 12px;
  margin-bottom: 12px;
}

.pin-color-input {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pin-color-text {
  flex: 1;
  min-width: 0;
  padding: 6px 8px;
  border-radius: 6px;
  border: 1px solid var(--border);
  font-size: 12px;
  font-family: ui-monospace, monospace;
  text-transform: uppercase;
}
.pin-color-text:focus { outline: none; border-color: #4f46e5; }

.pin-range {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pin-range input[type="range"] {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--border);
  appearance: none;
  cursor: pointer;
}
.pin-range input[type="range"]::-webkit-slider-thumb {
  appearance: none;
  width: 16px; height: 16px;
  border-radius: 50%;
  background: #4f46e5;
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(0,0,0,0.15);
}
.pin-range input[type="range"]::-moz-range-thumb {
  width: 16px; height: 16px;
  border-radius: 50%;
  background: #4f46e5;
  cursor: pointer;
  border: none;
}

.pin-range-val {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  min-width: 36px;
  text-align: right;
  font-family: ui-monospace, monospace;
}

.pin-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 0 12px;
}

.pin-hint {
  font-size: 13px;
  color: var(--muted);
  margin: 0 0 16px;
  line-height: 1.5;
}

.pin-section-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pin-section-header {
  display: grid;
  grid-template-columns: 24px 1fr 50px 50px;
  gap: 8px;
  align-items: center;
  padding: 6px 8px;
  font-size: 11px;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.pin-section-row {
  display: grid;
  grid-template-columns: 24px 1fr 50px 50px;
  gap: 8px;
  align-items: center;
  padding: 7px 8px;
  border-radius: 6px;
  transition: background 0.1s;
}
.pin-section-row:hover { background: #f8fafc; }

.pin-col-color { display: flex; align-items: center; justify-content: center; }
.pin-col-name { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pin-col-radio { display: flex; align-items: center; justify-content: center; }
.pin-col-radio input[type="radio"] { width: 16px; height: 16px; cursor: pointer; accent-color: #4f46e5; }
.pin-none-label { color: var(--muted); font-style: italic; }

.pin-color-dot {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1px solid rgba(0,0,0,0.1);
}

.device-toggles {
  display: flex;
  gap: 2px;
}

.device-btn {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border, rgba(15, 23, 42, 0.2));
  border-radius: 4px;
  background: #fff;
  color: #cbd5e1;
  cursor: pointer;
  transition: all 0.15s;
  padding: 0;
}

.device-btn:hover {
  border-color: #94a3b8;
  color: #64748b;
}

.device-btn.active {
  background: #eef2ff;
  border-color: #4f46e5;
  color: #4f46e5;
}

.device-btn.active:hover {
  background: #e0e7ff;
}

.design-btn {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: #fff;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.design-btn:hover {
  background: #ede9fe;
  border-color: #c4b5fd;
}

.container-edit-btn {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid #c7d2fe;
  background: #eef2ff;
  color: #4338ca;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.container-edit-btn:hover {
  background: #e0e7ff;
  border-color: #a5b4fc;
}

.remove-btn {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: none;
  background: #fee2e2;
  color: #dc2626;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.remove-btn:hover {
  background: #fecaca;
}

.container-editor-list {
  display: grid;
  gap: 8px;
}

.container-editor-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface-2);
}

.container-editor-name {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
}

.container-editor-drag-handle {
  cursor: grab;
  color: rgba(15, 23, 42, 0.45);
  font-weight: 900;
  font-size: 13px;
  padding: 2px 4px;
  letter-spacing: -2px;
  user-select: none;
  flex-shrink: 0;
}

.container-editor-drag-handle:hover {
  color: rgba(15, 23, 42, 0.72);
}

.container-editor-drag-handle:active {
  cursor: grabbing;
}

.container-editor-ghost {
  opacity: 0.55;
  background: rgba(79, 70, 229, 0.13) !important;
  border: 1px dashed rgba(79, 70, 229, 0.45);
}

.container-editor-name > span:last-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.container-editor-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.container-width-ratio {
  gap: 4px;
}

.container-width-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted);
  margin-right: 2px;
}

.container-unlink-btn {
  border: 1px solid #fecaca;
  background: #fff1f2;
  color: #b91c1c;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s ease;
}

.container-unlink-btn:hover {
  border-color: #fda4af;
  background: #ffe4e6;
}

.container-unlink-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Sort & Group filter bar */
.filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.filter-option {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  background: var(--surface-2);
  border-radius: 10px;
}

.filter-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  white-space: nowrap;
}

.filter-select {
  flex: 1;
  padding: 6px 8px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
  cursor: pointer;
  min-width: 0;
}

.filter-select--direction {
  flex: 0 0 86px;
}

/* Groups */
.group {
  margin-bottom: 16px;
}

.group--plain {
  margin-bottom: 0;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--surface, #e5e7eb);
  border-radius: 8px;
  margin-bottom: 8px;
}

.group-icon {
  font-size: 16px;
}

.group-title {
  flex: 1;
  font-weight: 700;
  font-size: 13px;
  color: var(--text);
}

.group-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  background: rgba(0, 0, 0, 0.08);
  padding: 2px 8px;
  border-radius: 10px;
}

/* Existing sections container */
.existing-sections-container {
  max-height: 400px;
  overflow-y: auto;
}

.tab-content--existing-sections .existing-sections-container,
.tab-content--existing-headers .existing-sections-container {
  flex: 1;
  min-height: 180px;
  max-height: none;
}

.section-pagination {
  position: sticky;
  bottom: 0;
  z-index: 2;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 0 0;
  margin-top: 12px;
  border-top: 1px solid var(--border);
  background: var(--surface, #fff);
}

.pagination-status {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  white-space: nowrap;
}

.pagination-btn {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  color: var(--text);
  padding: 7px 10px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.pagination-btn:hover:not(:disabled) {
  border-color: var(--accent, #2563eb);
}

.pagination-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Existing card wrapper */
.existing-card-wrapper {
  position: relative;
  min-width: 0;
}

.existing-card.is-on-page {
  cursor: default;
  opacity: 0.6;
}

.existing-card.is-on-page:hover {
  opacity: 0.7;
}

.existing-card.is-on-page .existing-actions {
  opacity: 1;
}

.on-page-badge {
  font-size: 10px;
  font-weight: 600;
  color: var(--muted, #64748b);
  background: var(--surface, #e5e7eb);
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 4px;
}

/* Existing card actions */
.existing-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}

.info-btn,
.delete-btn {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.info-btn {
  background: #e0f2fe;
  color: #0284c7;
}

.info-btn:hover {
  background: #bae6fd;
}

.delete-btn {
  background: #fee2e2;
  color: #dc2626;
}

.delete-btn:hover {
  background: #fecaca;
}

.delete-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Existing meta */
.existing-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
  min-width: 0;
  overflow: hidden;
}

.existing-usage {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent, #5b2fe3);
  background: color-mix(in srgb, var(--accent, #5b2fe3) 12%, white);
  padding: 2px 6px;
  border-radius: 4px;
}

.existing-usage.no-usage {
  color: #dc2626;
  background: #fee2e2;
}

/* Dialog small variant */
.dialog.dialog-small {
  max-width: 400px;
}

/* Info popup styles */
.info-section-name {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 12px;
  background: var(--surface-2);
  border-radius: 10px;
  font-weight: 700;
  margin-bottom: 12px;
}

.info-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.info-section-name > span:last-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.info-type {
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 16px;
}

.info-usage-header {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 10px;
}

.info-usage-list {
  display: grid;
  gap: 6px;
}

.info-usage-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--surface-2);
  border-radius: 8px;
}

.info-route {
  font-weight: 600;
  font-size: 13px;
  color: var(--text);
}

.info-visibility {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  background: #dcfce7;
  color: #16a34a;
}

.info-visibility.hidden {
  background: #fef3c7;
  color: #d97706;
}

.info-no-usage {
  padding: 20px;
  text-align: center;
  color: var(--muted);
  font-size: 14px;
  background: var(--surface-2);
  border-radius: 10px;
}

/* Confirm dialog styles */
.confirm-text {
  font-size: 15px;
  margin: 0 0 16px;
}

.confirm-warning {
  font-size: 13px;
  color: #dc2626;
  margin: 12px 0 0;
}

.confirm-note {
  font-size: 13px;
  color: var(--muted);
  margin: 12px 0 0;
}

.confirm-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
}

.btn.danger {
  background: #dc2626;
  color: #fff;
}

.btn.danger:hover {
  background: #b91c1c;
}

/* Header row */
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px;
  border-radius: 12px;
  background: var(--surface-2);
  margin-bottom: 8px;
}

.header-row.header-hidden {
  opacity: 0.6;
  background: var(--surface, #e5e7eb);
}

.header-row.header-hidden .name {
  text-decoration: line-through;
  color: var(--muted);
}

/* Manage buttons row */
.manage-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.panel-bottom-control {
  display: flex;
  margin-top: 8px;
}

.manage-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 12px;
  border-radius: 10px;
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease;
  background: var(--admin-primary-color, var(--admin-accent, #4f46e5));
  color: #fff;
  border: none;
}

.manage-btn:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--accent, #5b2fe3) 35%, #ffffff);
  outline-offset: 1px;
}

/* Header content checklist */
.content-checklist {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}

.content-check {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  cursor: pointer;
  transition: all 0.15s ease;
}

.content-check:hover {
  border-color: var(--accent, #5b2fe3);
  background: color-mix(in srgb, var(--accent, #5b2fe3) 5%, white);
}

.content-check input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: var(--accent, #5b2fe3);
  cursor: pointer;
}

.content-check-label {
  font-weight: 700;
  font-size: 14px;
  color: var(--text);
}

.create-header-btn {
  width: 100%;
  padding: 14px;
  border-radius: 12px;
  background: var(--accent, #5b2fe3);
  color: #fff;
  border: none;
  font-weight: 700;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.create-header-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--accent, #5b2fe3) 85%, black);
}

.create-header-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Header thumb in existing list */
.header-thumb {
  width: 48px;
  height: 36px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--surface, #e5e7eb);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb-placeholder {
  font-size: 18px;
}

@media (min-width: 1000px) {
  .wrap.open {
    width: 400px;
  }
}

/* Real mobile view (not simulated) */
@media (max-width: 767px) {
  .wrap.corner-bottom-left,
  .wrap.corner-top-left {
    left: 2.5%;
    right: auto;
    width: calc(50% - 3.75%);
  }
  .wrap.corner-bottom-right,
  .wrap.corner-top-right {
    right: 2.5%;
    left: auto;
    width: calc(50% - 3.75%);
  }
  .wrap.open {
    right: 0;
    left: 0;
    width: auto;
  }
  .wrap.open .panel {
    width: calc(100vw - 5%);
    margin: 0 auto;
  }

  .wrap.open .body {
    max-height: 80vh;
  }

  .width-ratio { display: none; }
}

</style>
