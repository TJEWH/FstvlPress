<template>
  <aside
    id="design-panel"
    class="wrap"
    :class="[`corner-${panelCorner}`, { open, 'preview-mode': state.previewMode }]"
    v-if="(state.canDesign && !state.previewMode) || (state.canDesign && state.previewMode && state.designPanelVisibleInSim)"
  >
    <AutosaveToast :message="designPanelAutosaveToastMessage" :tone="designPanelAutosaveToastTone" />

    <div class="panel" role="dialog" aria-label="Design Settings">
      <!-- Header -->
      <div class="head" @click="toggleOpen" role="button" tabindex="0">
        <div class="head-main">
          <div class="head-row head-row-top">
            <div class="head-top">
              <div class="title">Design</div>
            </div>
            <div class="head-actions" @click.stop>
              <span v-if="!open" class="chev" aria-hidden="true">▴</span>
              <button v-else class="icon-btn" type="button" @click="open = false" aria-label="Close">✕</button>
            </div>
          </div>
          <div v-if="open && showDesignTabs" class="head-row design-tabs" :class="{ 'single-tab': !showOverrideTab }" @click.stop>
            <button
              type="button"
              class="design-tab-btn"
              :class="{ active: activePanelTab === 'global' }"
              @click="activePanelTab = 'global'"
            >
              Global
            </button>
            <button
              v-if="showOverrideTab"
              type="button"
              class="design-tab-btn"
              :class="{ active: activePanelTab === 'override' }"
              @click="activePanelTab = 'override'"
            >
              Override
            </button>
          </div>
          <div v-if="open && isLinkedPageStyleLocked" class="head-row head-lock-row" @click.stop>
            Style is controlled by template <code>{{ state.pageTemplateStyleRef || "template" }}</code>.
            Page/header/section overrides are disabled.
          </div>
          <div v-if="open && isTemplateDesignEditMode" class="head-row template-design-actions-row" @click.stop>
            <button
              class="btn-secondary btn-sm template-design-action-btn"
              type="button"
              :disabled="templateDesignMatchesGlobal || loadingGlobalTemplateDesign || loadingGlobalTemplateDesignSnapshot || publishingTemplateDesign || autoSaving"
              @click="loadGlobalTemplateDesign"
              title="Load current global design into this template draft"
            >{{ loadingGlobalTemplateDesign ? "Loading..." : "Load Global" }}</button>
            <button
              class="btn-primary btn-sm template-design-action-btn"
              type="button"
              :disabled="!templateDesignHasPublishChanges || publishingTemplateDesign || loadingGlobalTemplateDesign || autoSaving"
              @click="publishTemplateDesign"
              title="Publish template design"
            >{{ publishingTemplateDesign ? "Publishing…" : "Publish" }}</button>
          </div>
          <div v-if="open && !isTemplateDesignEditMode && state.designRevisionStatus?.enabled !== false" class="head-row head-undo-row" @click.stop>
            <button
              class="undo-btn"
              :disabled="!state.designRevisionStatus?.canUndo"
              @click="handleUndo"
              title="Undo"
            >
              <font-awesome-icon :icon="faRotateLeft" />
              Undo
            </button>
            <div class="head-author">
              <AuthorBadge
                :name="state.designRevisionStatus?.lastSavedBy"
                :timestamp="state.designRevisionStatus?.lastSavedAt"
              />
            </div>
            <button
              class="redo-btn"
              :disabled="!state.designRevisionStatus?.canRedo"
              @click="handleRedo"
              title="Redo"
            >
              Redo
              <font-awesome-icon :icon="faRotateRight" />
            </button>
          </div>
          <div v-if="open" class="head-row param-search-row" @click.stop>
            <input
              v-model="paramSearchQuery"
              type="text"
              class="param-search-input"
              placeholder="Search parameter or subsection..."
              aria-label="Search parameters by name or subsection"
            />
            <button
              v-if="paramSearchQuery"
              type="button"
              class="param-search-clear"
              @click="paramSearchQuery = ''"
              aria-label="Clear parameter search"
            >
              Clear
            </button>
          </div>
        </div>
      </div>

      <!-- Body -->
      <div class="body">
        <div class="body-scroll">
          <template v-if="activePanelTab === 'global'">

        <!-- Favorites Section (shown if any params are favorites) -->
        <div v-if="favoriteParams.length > 0" class="collapsible" :class="{ expanded: hasActiveParamSearch || expandedSections._favorites }">
          <div class="collapsible-header" @click="toggleSection('_favorites')">
            <span class="collapsible-icon">{{ (hasActiveParamSearch || expandedSections._favorites) ? '▾' : '▸' }}</span>
            <span class="collapsible-title">
              <font-awesome-icon :icon="faStar" />
              Favorites
            </span>
          </div>
          <div class="collapsible-content">
            <template v-for="(group, gIdx) in favoritesBySubsection" :key="group.key">
              <div class="subsection-collapsible" :class="{ expanded: isSubsectionExpanded('_favorites', group.key), 'first-sub': gIdx === 0 }">
                <div class="subsection-header" @click="toggleSubsection('_favorites', group.key)">
                  <span class="subsection-icon">{{ isSubsectionExpanded('_favorites', group.key) ? '▾' : '▸' }}</span>
                  <span class="subsection-title">{{ group.label }}</span>
                </div>
                <div class="subsection-content">
                  <template v-for="paramKey in group.params" :key="paramKey">
                    <DesignField
                      :param-key="paramKey"
                      :config="getParamConfig(paramKey)"
                      :value="designValues[paramKey]"
                      :design-values="designValues"
                      :responsive-values="responsiveValues"
                      :selected-units="selectedUnits"
                      :hide-responsive="state.hideResponsiveUI"
                      :font-families="activeFontFamilies"
                      :font-weights="activeFontWeights"
                      :base-colors="baseColorOptions"
                      :color-links="adminConfig?.colorLinks || {}"
                      :override-info="globalOverrideInfo(paramKey)"
                      :override-sources="globalOverrideSources(paramKey)"
                      @update="updateDesign"
                      @update-link="updateColorLink"
                      @update-color-variation="updateDesignColorVariation"
                      @update-responsive="updateResponsiveValue"
                      @update-responsive-mode="updateResponsiveMode"
                      @update-unit="updateSelectedUnit"
                      @open-override="openOverrideTarget"
                      @device-click="handleDeviceClick"
                    />
                  </template>
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- Dynamic sections from admin config -->
        <template v-for="sectionKey in activeSectionOrder" :key="sectionKey">
          <div v-if="showGlobalSection(sectionKey)" class="collapsible" :class="{ expanded: hasActiveParamSearch || expandedSections[sectionKey] }">
            <div class="collapsible-header" @click="toggleSection(sectionKey)">
              <span class="collapsible-icon">{{ (hasActiveParamSearch || expandedSections[sectionKey]) ? '▾' : '▸' }}</span>
              <span class="collapsible-title">{{ sectionLabels[sectionKey] || sectionKey }}</span>
            </div>
            <div class="collapsible-content">
              <!-- Standard section rendering with collapsible subsections -->
              <template v-if="sectionKey !== 'buttons' && sectionKey !== 'customCss' && sectionKey !== 'versions'">
                <template v-for="(group, gIdx) in paramsBySubsection[sectionKey]" :key="gIdx">
                  <!-- Subsection with title (collapsible) -->
                  <div v-if="group.subsection" class="subsection-collapsible" :class="{ expanded: isSubsectionExpanded(sectionKey, group.subsection), 'first-sub': gIdx === 0 }">
                    <div class="subsection-header" @click="toggleSubsection(sectionKey, group.subsection)">
                      <span class="subsection-icon">{{ isSubsectionExpanded(sectionKey, group.subsection) ? '▾' : '▸' }}</span>
                      <span class="subsection-title">{{ group.subsection }}</span>
                    </div>
                    <div class="subsection-content">
                      <template v-for="paramKey in group.params" :key="paramKey">
                        <DesignField
                          :param-key="paramKey"
                          :config="getParamConfig(paramKey)"
                          :value="designValues[paramKey]"
                          :design-values="designValues"
                          :responsive-values="responsiveValues"
                          :selected-units="selectedUnits"
                          :hide-responsive="state.hideResponsiveUI"
                          :font-families="activeFontFamilies"
                          :font-weights="activeFontWeights"
                          :base-colors="baseColorOptions"
                          :color-links="adminConfig?.colorLinks || {}"
                          :override-info="globalOverrideInfo(paramKey)"
                          :override-sources="globalOverrideSources(paramKey)"
                          @update="updateDesign"
                          @update-link="updateColorLink"
                          @update-color-variation="updateDesignColorVariation"
                          @update-responsive="updateResponsiveValue"
                          @update-responsive-mode="updateResponsiveMode"
                          @update-unit="updateSelectedUnit"
                          @open-override="openOverrideTarget"
                          @device-click="handleDeviceClick"
                        />
                      </template>
                    </div>
                  </div>
                  <!-- Params without subsection -->
                  <template v-else v-for="paramKey in group.params" :key="paramKey">
                    <DesignField
                      :param-key="paramKey"
                      :config="getParamConfig(paramKey)"
                      :value="designValues[paramKey]"
                      :design-values="designValues"
                      :responsive-values="responsiveValues"
                      :selected-units="selectedUnits"
                      :hide-responsive="state.hideResponsiveUI"
                      :font-families="activeFontFamilies"
                      :font-weights="activeFontWeights"
                      :base-colors="baseColorOptions"
                      :color-links="adminConfig?.colorLinks || {}"
                      :override-info="globalOverrideInfo(paramKey)"
                      :override-sources="globalOverrideSources(paramKey)"
                      @update="updateDesign"
                      @update-link="updateColorLink"
                      @update-color-variation="updateDesignColorVariation"
                      @update-responsive="updateResponsiveValue"
                      @update-responsive-mode="updateResponsiveMode"
                      @update-unit="updateSelectedUnit"
                      @open-override="openOverrideTarget"
                      @device-click="handleDeviceClick"
                    />
                  </template>
                </template>
              </template>

              <!-- Buttons section: shared params + per-type subsections -->
              <template v-else-if="sectionKey === 'buttons'">
                <div class="subsection-collapsible first-sub" :class="{ expanded: isSubsectionExpanded('buttons', 'Shared') }">
                  <div class="subsection-header" @click="toggleSubsection('buttons', 'Shared')">
                    <span class="subsection-icon">{{ isSubsectionExpanded('buttons', 'Shared') ? '▾' : '▸' }}</span>
                    <span class="subsection-title">Shared</span>
                  </div>
                  <div class="subsection-content">
                    <template v-for="paramKey in sharedButtonParams" :key="paramKey">
                      <DesignField
                        :param-key="paramKey"
                        :config="getParamConfig(paramKey)"
                        :value="designValues[paramKey]"
                        :design-values="designValues"
                        :responsive-values="responsiveValues"
                        :selected-units="selectedUnits"
                        :hide-responsive="state.hideResponsiveUI"
                        :font-families="activeFontFamilies"
                        :font-weights="activeFontWeights"
                        :base-colors="baseColorOptions"
                        :color-links="adminConfig?.colorLinks || {}"
                        :override-info="globalOverrideInfo(paramKey)"
                        :override-sources="globalOverrideSources(paramKey)"
                        @update="updateDesign"
                        @update-link="updateColorLink"
                        @update-color-variation="updateDesignColorVariation"
                        @update-responsive="updateResponsiveValue"
                        @update-responsive-mode="updateResponsiveMode"
                        @update-unit="updateSelectedUnit"
                        @open-override="openOverrideTarget"
                        @device-click="handleDeviceClick"
                      />
                    </template>
                  </div>
                </div>

                <template v-for="inst in enabledButtonInstances" :key="inst.id">
                  <div class="subsection-collapsible" :class="{ expanded: isSubsectionExpanded('buttons', inst.id) }">
                    <div class="subsection-header" @click="toggleSubsection('buttons', inst.id)">
                      <span class="subsection-icon">{{ isSubsectionExpanded('buttons', inst.id) ? '▾' : '▸' }}</span>
                      <span class="subsection-title">{{ inst.label }}</span>
                    </div>
                    <div class="subsection-content">
                      <template v-for="paramDef in perTypeButtonParamDefs" :key="`${inst.id}_${paramDef.key}`">
                        <DesignField
                          :param-key="`btnType_${inst.id}_${paramDef.key}`"
                          :config="paramDef.config"
                          :value="getButtonTypeValue(inst.id, paramDef.key)"
                          :design-values="designValues"
                          :selected-units="selectedUnits"
                          :font-families="activeFontFamilies"
                          :font-weights="activeFontWeights"
                          :base-colors="baseColorOptions"
                          :color-links="adminConfig?.colorLinks || {}"
                          :override-info="globalOverrideInfo(`btnType_${inst.id}_${paramDef.key}`)"
                          :override-sources="globalOverrideSources(`btnType_${inst.id}_${paramDef.key}`)"
                          @update="(_, val) => updateButtonTypeStyle(inst.id, paramDef.key, val)"
                          @update-link="(_, baseKey, resetOnUnlink) => updateButtonTypeLink(inst.id, paramDef.key, baseKey, resetOnUnlink)"
                          @update-color-variation="updateDesignColorVariation"
                          @update-unit="updateSelectedUnit"
                          @open-override="openOverrideTarget"
                          @device-click="handleDeviceClick"
                        />
                      </template>
                    </div>
                  </div>
                </template>
              </template>

              <!-- Versions section -->
              <template v-else-if="sectionKey === 'versions'">
                <!-- Save new version -->
                <div class="version-save-form" :class="{ 'is-disabled': saveInputsDisabled }">
                  <input
                    v-model="newVersionTitle"
                    class="version-input"
                    placeholder="Version title"
                    :disabled="saveInputsDisabled"
                  />
                  <textarea
                    v-model="newVersionDescription"
                    class="version-textarea"
                    placeholder="Description (optional)"
                    rows="2"
                    :disabled="saveInputsDisabled"
                  ></textarea>
                  <div class="version-rating-row">
                    <span class="version-rating-label">Rating</span>
                    <div class="version-rating-stars">
                      <button
                        v-for="n in 10"
                        :key="n"
                        type="button"
                        class="version-star-btn"
                        :class="{ active: n <= newVersionRating }"
                        :disabled="saveInputsDisabled"
                        @click="newVersionRating = n === newVersionRating ? 0 : n"
                        :title="`${n}/10`"
                      >
                        <font-awesome-icon :icon="faStar" />
                      </button>
                    </div>
                    <span class="version-rating-value">{{ newVersionRating }}/10</span>
                  </div>
                  <button
                    class="version-save-btn"
                    type="button"
                    :disabled="!canSaveCurrentVersion"
                    @click="saveVersion"
                  >{{ savingVersion ? 'Saving…' : 'Save Current as Version' }}</button>
                  <button
                    class="version-save-btn"
                    type="button"
                    :disabled="!canUpdateCurrentVersion"
                    @click="updateCurrentVersion"
                  >{{ savingVersion ? 'Saving…' : 'Update Current Version' }}</button>
                  <div v-if="saveInputsDisabled" class="version-save-hint">
                    Current state matches the current baseline version.
                  </div>
                  <div v-if="versionChangeAdvisory && !saveInputsDisabled" class="version-save-hint">
                    {{ versionChangeAdvisory }}
                  </div>
                </div>

                <!-- Version list -->
                <div class="sub-section first-sub" style="margin-top:12px">
                  <div class="sub-title">Saved Versions</div>
                </div>
                <div class="version-state-legend">
                  <span class="version-state-legend-item">
                    <span class="version-state-chip version-state-chip-clean"></span>
                    Solid border = current design state
                  </span>
                  <span class="version-state-legend-item">
                    <span class="version-state-chip version-state-chip-dirty"></span>
                    Dashed border = currently loaded version with changes
                  </span>
                </div>
                <div v-if="versionsLoading" class="snippet-hint">Loading…</div>
                <div v-else-if="sortedDesignVersions.length === 0" class="snippet-hint">No versions saved yet.</div>
                <template v-for="v in sortedDesignVersions" :key="v.id">
                  <div
                    class="version-card"
                    :class="{
                      'version-editing': editingVersionId === v.id,
                      'version-card-current-clean': editingVersionId !== v.id && isVersionCurrentClean(v),
                      'version-card-current-dirty': editingVersionId !== v.id && isVersionCurrentDirty(v),
                    }"
                  >
                    <!-- Display mode -->
                    <template v-if="editingVersionId !== v.id">
                      <div class="version-card-head">
                        <div class="version-card-info" @click="startEditVersion(v)">
                          <span class="version-card-title">{{ v.title }}</span>
                          <span class="version-card-meta">
                            {{ v.created_by }} · {{ formatDate(v.created_at) }}
                            <template v-if="isVersionCurrent(v)"> · Current</template>
                            <template v-if="isVersionPublished(v)"> · Public</template>
                            <template v-if="v.rating > 0">
                              · {{ v.rating }}/10 <font-awesome-icon :icon="faStar" />
                            </template>
                          </span>
                        </div>
                        <div class="version-card-tools">
                          <span v-if="hasVersionChangelog(v)" class="version-info-wrap">
                            <button class="version-info-btn" type="button" title="Changelog">i</button>
                            <span class="version-info-tooltip">
                              <span class="version-info-line">Compared to: {{ versionChangelogBase(v) }}</span>
                              <span class="version-info-line">Changed:</span>
                              <ul class="version-info-list">
                                <li v-for="(entry, idx) in versionChangelogItems(v)" :key="`chg-${v.id}-${idx}`">{{ entry }}</li>
                              </ul>
                            </span>
                          </span>
                          <button
                            class="snippet-del"
                            type="button"
                            :disabled="isVersionPublished(v)"
                            :title="isVersionPublished(v) ? 'Published versions cannot be deleted' : 'Delete'"
                            @click="removeVersion(v)"
                          >✕</button>
                        </div>
                      </div>
                      <div v-if="v.description" class="version-card-desc">{{ v.description }}</div>
                      <div class="version-card-actions">
                        <button class="version-action-btn" type="button" @click="applyVersion(v)">Load</button>
                        <button
                          class="version-action-btn version-action-publish"
                          :class="{ active: isVersionPublished(v) }"
                          type="button"
                          :disabled="isVersionPublished(v) || publishingVersionId === v.id"
                          @click="publishVersion(v)"
                        >{{ isVersionPublished(v) ? 'Published' : (publishingVersionId === v.id ? 'Publishing…' : 'Publish') }}</button>
                      </div>
                    </template>
                    <!-- Edit mode -->
                    <template v-else>
                      <input v-model="editVersionData.title" class="version-input" placeholder="Title" @keydown.enter="commitEditVersion" />
                      <textarea v-model="editVersionData.description" class="version-textarea" placeholder="Description" rows="2"></textarea>
                      <div class="version-rating-row">
                        <span class="version-rating-label">Rating</span>
                        <div class="version-rating-stars">
                          <button v-for="n in 10" :key="n" type="button" class="version-star-btn" :class="{ active: n <= editVersionData.rating }" @click="editVersionData.rating = n === editVersionData.rating ? 0 : n" :title="`${n}/10`">
                            <font-awesome-icon :icon="faStar" />
                          </button>
                        </div>
                        <span class="version-rating-value">{{ editVersionData.rating }}/10</span>
                      </div>
                      <div class="version-card-actions">
                        <button class="version-action-btn version-action-save" type="button" @click="commitEditVersion">Save</button>
                        <button class="version-action-btn" type="button" @click="editingVersionId = null">Cancel</button>
                      </div>
                    </template>
                  </div>
                </template>
              </template>

              <!-- Custom CSS section: live editor + snippets -->
              <template v-else-if="sectionKey === 'customCss'">
                <!-- Media query tabs -->
                <div class="css-media-tabs">
                  <button
                    class="css-media-tab"
                    :class="{ active: activeCssMediaTab === 'desktop' }"
                    @click="activeCssMediaTab = 'desktop'"
                    title="CSS applies globally"
                  >
                    <font-awesome-icon :icon="faDesktop" />
                    <span>All</span>
                  </button>
                  <button
                    class="css-media-tab"
                    :class="{ active: activeCssMediaTab === 'tablet' }"
                    @click="activeCssMediaTab = 'tablet'"
                    :title="responsiveCssMediaTitle('tablet')"
                  >
                    <font-awesome-icon :icon="faTabletScreenButton" />
                    <span>Tablet</span>
                  </button>
                  <button
                    class="css-media-tab"
                    :class="{ active: activeCssMediaTab === 'mobile' }"
                    @click="activeCssMediaTab = 'mobile'"
                    :title="responsiveCssMediaTitle('mobile')"
                  >
                    <font-awesome-icon :icon="faMobileScreenButton" />
                    <span>Mobile</span>
                  </button>
                </div>
                <div class="css-media-hint">{{ cssMediaTabHint }}</div>

                <!-- Desktop/All CSS -->
                <DesignField
                  v-if="activeCssMediaTab === 'desktop'"
                  param-key="globalCustomCss"
                  :config="getParamConfig('globalCustomCss')"
                  :value="designValues.globalCustomCss"
                  :design-values="designValues"
                  :override-info="globalOverrideInfo('globalCustomCss')"
                  :override-sources="globalOverrideSources('globalCustomCss')"
                  @update="updateDesign"
                  @open-override="openOverrideTarget"
                  @device-click="handleDeviceClick"
                />
                <!-- Tablet CSS -->
                <DesignField
                  v-else-if="activeCssMediaTab === 'tablet'"
                  param-key="globalCustomCssTablet"
                  :config="{ type: 'textarea', label: 'Tablet CSS' }"
                  :value="designValues.globalCustomCssTablet"
                  :design-values="designValues"
                  :override-info="globalOverrideInfo('globalCustomCssTablet')"
                  :override-sources="globalOverrideSources('globalCustomCssTablet')"
                  @update="updateDesign"
                  @open-override="openOverrideTarget"
                  @device-click="handleDeviceClick"
                />
                <!-- Mobile CSS -->
                <DesignField
                  v-else-if="activeCssMediaTab === 'mobile'"
                  param-key="globalCustomCssMobile"
                  :config="{ type: 'textarea', label: 'Mobile CSS' }"
                  :value="designValues.globalCustomCssMobile"
                  :design-values="designValues"
                  :override-info="globalOverrideInfo('globalCustomCssMobile')"
                  :override-sources="globalOverrideSources('globalCustomCssMobile')"
                  @update="updateDesign"
                  @open-override="openOverrideTarget"
                  @device-click="handleDeviceClick"
                />

                <div class="snippet-actions">
                  <button
                    class="snippet-save-btn"
                    type="button"
                    :disabled="!currentCssTabValue"
                    @click="saveAsSnippet"
                  >Save as Snippet</button>
                </div>

                <div class="sub-section" :class="{ 'first-sub': true }" style="margin-top:12px">
                  <div class="sub-title">Saved Snippets</div>
                </div>
                <div v-if="snippetsLoading" class="snippet-hint">Loading…</div>
                <div v-else-if="cssSnippets.length === 0" class="snippet-hint">No snippets saved yet.</div>
                <div v-for="s in cssSnippets" :key="s.id" class="snippet-card" :class="{ inactive: !s.active }">
                  <div class="snippet-head">
                    <label class="snippet-toggle">
                      <input type="checkbox" :checked="s.active" @change="toggleSnippet(s)">
                      <span class="snippet-label">{{ s.label }}</span>
                      <span v-if="s.media_scope" class="snippet-scope">{{ s.media_scope }}</span>
                      <span v-if="s.context_key" class="snippet-scope">{{ s.context_key }}</span>
                    </label>
                    <button class="snippet-del" type="button" @click="deleteSnippet(s)" title="Delete">✕</button>
                  </div>
                  <pre class="snippet-preview">{{ s.css.length > 120 ? s.css.slice(0, 120) + '…' : s.css }}</pre>
                  <div class="snippet-meta">{{ s.created_by }} · {{ formatDate(s.created_at) }}</div>
                </div>
              </template>
            </div>
          </div>
        </template>
          </template>

          <template v-else>
            <div v-if="visibleOverrideTargets.length === 0" class="snippet-hint">
              {{ hasActiveParamSearch ? 'No matching override parameters.' : 'No sections available for overrides.' }}
            </div>
            <template v-for="target in visibleOverrideTargets" :key="target.key">
              <div
                class="collapsible"
                :class="{ expanded: hasActiveParamSearch || isOverrideTargetExpanded(target.key), muted: !isOverrideEnabled(target.key) }"
                :ref="(el) => setOverrideTargetRef(target.key, el)"
              >
                <div class="collapsible-header" @click="toggleOverrideTarget(target.key)">
                  <span class="collapsible-icon">{{ (hasActiveParamSearch || isOverrideTargetExpanded(target.key)) ? '▾' : '▸' }}</span>
                  <span class="collapsible-title">{{ target.label }}</span>
                  <label class="override-active-toggle" title="Enable or disable overrides for this target" @click.stop>
                    <input
                      type="checkbox"
                      :checked="isOverrideEnabled(target.key)"
                      @change="toggleOverrideEnabled(target.key, $event.target.checked)"
                    />
                    <span>{{ isOverrideEnabled(target.key) ? 'On' : 'Off' }}</span>
                  </label>
                </div>
                <div class="collapsible-content override-target-content">
                  <template v-if="hasActiveParamSearch || isOverrideTargetExpanded(target.key)">
                    <template v-for="(group, gIdx) in overrideParamsByTarget[target.key] || []" :key="`${target.key}_${gIdx}`">
                      <div
                        v-if="group.subsection"
                        class="subsection-collapsible"
                        :class="{ expanded: isSubsectionExpanded(`override_${target.key}`, group.subsection), 'first-sub': gIdx === 0 }"
                      >
                        <div class="subsection-header" @click="toggleSubsection(`override_${target.key}`, group.subsection)">
                          <span class="subsection-icon">{{ isSubsectionExpanded(`override_${target.key}`, group.subsection) ? '▾' : '▸' }}</span>
                          <span class="subsection-title">{{ group.subsection }}</span>
                        </div>
                        <div class="subsection-content">
                          <template v-for="paramKey in group.params" :key="`${target.key}_${paramKey}`">
                            <DesignField
                              :param-key="paramKey"
                              :config="getOverrideParamConfig(target.key, paramKey)"
                              :value="getOverrideParamValue(target.key, paramKey)"
                              :design-values="designValues"
                              :responsive-values="getOverrideResponsiveValues(target.key)"
                              :selected-units="getOverrideSelectedUnits(target.key)"
                              :hide-responsive="state.hideResponsiveUI"
                              :font-families="activeFontFamilies"
                              :font-weights="activeFontWeights"
                              :base-colors="baseColorOptions"
                              :color-links="getOverrideColorLinks(target.key)"
                              :color-variations="getOverrideColorVariations(target.key)"
                              :force-nullable="true"
                              @update="(_, val) => setOverrideParamValue(target.key, paramKey, val)"
                              @update-link="(_, baseKey, resetOnUnlink) => updateOverrideColorLink(target.key, paramKey, baseKey, resetOnUnlink)"
                              @update-color-variation="(_, variation) => updateOverrideColorVariation(target.key, paramKey, variation)"
                              @update-responsive="(_, mode, values) => updateOverrideResponsiveValue(target.key, paramKey, mode, values)"
                              @update-responsive-mode="(_, mode) => updateOverrideResponsiveMode(target.key, paramKey, mode)"
                              @update-unit="(_, unit) => updateOverrideSelectedUnit(target.key, paramKey, unit)"
                              @device-click="handleDeviceClick"
                            />
                          </template>
                        </div>
                      </div>
                      <template v-else v-for="paramKey in group.params" :key="`${target.key}_${paramKey}`">
                        <DesignField
                          :param-key="paramKey"
                          :config="getOverrideParamConfig(target.key, paramKey)"
                          :value="getOverrideParamValue(target.key, paramKey)"
                          :design-values="designValues"
                          :responsive-values="getOverrideResponsiveValues(target.key)"
                          :selected-units="getOverrideSelectedUnits(target.key)"
                          :hide-responsive="state.hideResponsiveUI"
                          :font-families="activeFontFamilies"
                          :font-weights="activeFontWeights"
                          :base-colors="baseColorOptions"
                          :color-links="getOverrideColorLinks(target.key)"
                          :color-variations="getOverrideColorVariations(target.key)"
                          :force-nullable="true"
                          @update="(_, val) => setOverrideParamValue(target.key, paramKey, val)"
                          @update-link="(_, baseKey, resetOnUnlink) => updateOverrideColorLink(target.key, paramKey, baseKey, resetOnUnlink)"
                          @update-color-variation="(_, variation) => updateOverrideColorVariation(target.key, paramKey, variation)"
                          @update-responsive="(_, mode, values) => updateOverrideResponsiveValue(target.key, paramKey, mode, values)"
                          @update-responsive-mode="(_, mode) => updateOverrideResponsiveMode(target.key, paramKey, mode)"
                          @update-unit="(_, unit) => updateOverrideSelectedUnit(target.key, paramKey, unit)"
                          @device-click="handleDeviceClick"
                        />
                      </template>
                    </template>
                    <div class="override-target-footer">
                      <button
                        type="button"
                        class="override-clear-target-btn"
                        :disabled="!hasOverrideTargetData(target.key)"
                        @click.stop="clearOverrideTarget(target.key)"
                      >
                        Unset Override Parameters
                      </button>
                    </div>
                  </template>
                </div>
              </div>
            </template>
          </template>
        </div>

        <!-- Bottom controls -->
        <div class="bottom-controls">
          <!-- Simulation visibility toggle -->
          <label v-if="state.canDesign || state.previewMode" class="sim-vis-toggle" title="Show design panel during viewport simulation in preview mode">
            <input
              type="checkbox"
              :checked="state.designPanelVisibleInSim"
              @change="state.designPanelVisibleInSim = $event.target.checked"
            />
            <span class="sim-vis-label">Visible in preview</span>
          </label>

          <PanelPositionControl
            v-model="panelCorner"
            aria-label="Choose design panel position"
            fallback="bottom-right"
          />
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, reactive, computed, watch, defineAsyncComponent, onMounted, onBeforeUnmount, nextTick } from "vue";
import {
  faAlignLeft,
  faBullhorn,
  faCalendarDays,
  faCircleQuestion,
  faCode,
  faFileLines,
  faShareNodes,
  faImage,
  faImages,
  faMobileScreenButton,
  faNewspaper,
  faRotateLeft,
  faRotateRight,
  faStar,
  faTableCellsLarge,
  faTabletScreenButton,
  faVideo,
  faDesktop,
} from "@fortawesome/free-solid-svg-icons";
import { useStore } from "../../../store/store.js";
import { DEFAULT_DESIGN, mapBackendToFrontendDesign, mapDesignToBackendFull, PARAM_CONFIGS, PARAMS_BY_SECTION } from "../../../designDefs.js";
import AuthorBadge from "../../ui/AuthorBadge.vue";
import { usePanelPosition } from "../../../composables/usePanelPosition.js";
import * as api from "../../../services/api.js";
import {
  formatInstantInServerTimezone,
  formatRevisionTimestampBerlin,
  getRevisionTimestampMs,
  parseRevisionTimestamp,
} from "../../../utils/revisionTime.js";
import {
  DEFAULT_COLOR_VARIATION,
  normalizeColorVariation,
} from "../../../utils/colorVariations.js";
import {
  buildResponsiveMediaQuery,
  getResponsiveDeviceLabel,
} from "../../../utils/responsiveViewport.js";
import {
  createSectionContainerTargetKey,
  buildSectionContainerMaps,
  getContainerLeaderKey,
  parseSectionContainerTargetKey,
} from "../../../utils/sectionContainers.js";
import { buildCssSnippetsStyleText } from "../../../utils/cssSnippets.js";
import PanelPositionControl from "./PanelPositionControl.vue";
import AutosaveToast from "../AutosaveToast.vue";

const DesignField = defineAsyncComponent(() => import("./DesignField.vue"));

const { state, localizedText, updateDesignSetting, saveDesignSettings, saveSectionDesignOverrides, loadDesignSettings, loadGlobalDesignIntoTemplateDraft, loadAdminDesignConfig, undoDesignChange, redoDesignChange, setSimulatedViewport } = useStore();

const { panelPosition: panelCorner } = usePanelPosition("designPanelCorner", "bottom-right");

function handleDeviceClick(device) {
  if (device === null) {
    setSimulatedViewport(null);
  } else {
    setSimulatedViewport(device);
  }
}

const open = ref(false);
const activePanelTab = ref('global');
const expandedOverrideTargets = reactive({});
const overrideTargetRefs = ref({});
const publishingTemplateDesign = ref(false);
const loadingGlobalTemplateDesign = ref(false);
const globalTemplateDesign = ref(null);
const loadingGlobalTemplateDesignSnapshot = ref(false);
const autoSaving = ref(false);
const autoSaveError = ref("");
const autoSaveConflict = ref("");
const autoSaveSaved = ref(false);
const adminConfigDirty = ref(false);
const lastKnownDesignRevision = reactive({ at: null, by: null });
const dirtyOverrideKeys = reactive({});
const paramSearchQuery = ref('');
let autoSaveTimer = null;
let autoSaveStatusTimer = null;
const isTemplatePageDesignMode = computed(() =>
  String(state.pageSlug || "").startsWith("__template_page__/")
);
const isTemplateInstanceDesignMode = computed(() =>
  Boolean(state.pageTemplateStyleLock) && Boolean(state.pageTemplateStyleRef) && !isTemplatePageDesignMode.value
);
const isTemplateDesignEditMode = computed(() =>
  isTemplatePageDesignMode.value || isTemplateInstanceDesignMode.value
);
const isLinkedPageStyleLocked = computed(() =>
  Boolean(state.pageTemplateStyleLock) && !isTemplatePageDesignMode.value
);
const showOverrideTab = computed(() => !isTemplateDesignEditMode.value && !isLinkedPageStyleLocked.value);
const showDesignTabs = computed(() => !isTemplateDesignEditMode.value);

function activeTemplateDesignPath() {
  const context = api.getTemplateBuilderContext?.() || null;
  if (context?.kind === "page" && context.path) return String(context.path).trim();
  if (isTemplateInstanceDesignMode.value && state.pageTemplateStyleRef) {
    return String(state.pageTemplateStyleRef || "").trim();
  }
  return "";
}

const designPanelAutosaveToastTone = computed(() => {
  if (autoSaving.value) return "saving";
  if (autoSaveConflict.value || autoSaveError.value) return "error";
  if (autoSaveSaved.value) return "saved";
  return "idle";
});

const designPanelAutosaveToastMessage = computed(() => {
  if (autoSaving.value) return "Saving design changes...";
  if (autoSaveConflict.value) return autoSaveConflict.value;
  if (autoSaveError.value) return autoSaveError.value;
  if (autoSaveSaved.value) return "Design changes saved.";
  return "";
});

function clearAutoSaveStatusTimer() {
  if (autoSaveStatusTimer) {
    clearTimeout(autoSaveStatusTimer);
    autoSaveStatusTimer = null;
  }
}

function clearAutoSaveToastState() {
  clearAutoSaveStatusTimer();
  autoSaveError.value = "";
  autoSaveConflict.value = "";
  autoSaveSaved.value = false;
}

function showAutoSaveSaved() {
  clearAutoSaveStatusTimer();
  autoSaveError.value = "";
  autoSaveConflict.value = "";
  autoSaveSaved.value = true;
  autoSaveStatusTimer = setTimeout(() => {
    autoSaveSaved.value = false;
    autoSaveStatusTimer = null;
  }, 3000);
}

function showAutoSaveError(message, { conflict = false } = {}) {
  clearAutoSaveStatusTimer();
  autoSaveSaved.value = false;
  if (conflict) {
    autoSaveConflict.value = message;
    autoSaveError.value = "";
  } else {
    autoSaveError.value = message;
    autoSaveConflict.value = "";
  }
  autoSaveStatusTimer = setTimeout(() => {
    autoSaveConflict.value = "";
    autoSaveError.value = "";
    autoSaveStatusTimer = null;
  }, 3000);
}

function stableDesignValue(value) {
  if (Array.isArray(value)) return value.map(stableDesignValue);
  if (!value || typeof value !== "object") return value;
  return Object.keys(value).sort().reduce((acc, key) => {
    const nextValue = stableDesignValue(value[key]);
    if (nextValue !== undefined) acc[key] = nextValue;
    return acc;
  }, {});
}

function templateDesignPublishSignature(design) {
  try {
    return JSON.stringify(stableDesignValue(mapDesignToBackendFull(design || {})));
  } catch (err) {
    console.warn("Failed to compare template design publish state:", err);
    return "";
  }
}

const templateDesignHasPublishChanges = computed(() => {
  if (!isTemplateDesignEditMode.value) return false;
  const publishedDesign = state.templatePagePublishedDesign;
  if (!publishedDesign || typeof publishedDesign !== "object") return false;
  return templateDesignPublishSignature(state.design) !== templateDesignPublishSignature(publishedDesign);
});

const templateDesignMatchesGlobal = computed(() => {
  if (!isTemplateDesignEditMode.value) return false;
  if (!globalTemplateDesign.value || typeof globalTemplateDesign.value !== "object") return false;
  return templateDesignPublishSignature(state.design) === templateDesignPublishSignature(globalTemplateDesign.value);
});

const sectionLabels = {
  header: "Header",
  layout: "Layout",
  sections: "Sections",
  colors: "Colors",
  buttons: "Buttons",
  fonts: "Fonts",
  versions: "Versions",
  customCss: "Custom CSS",
};

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
  tiles: faTableCellsLarge,
  program: faCalendarDays,
};

function getTypeIcon(type) {
  return TYPE_ICONS[type] || faFileLines;
}

function getSectionDisplayName(sectionKey) {
  const meta = state.sectionMeta?.[sectionKey];
  const section = state.sectionsData?.[sectionKey];

  if (section?.title) {
    const title = localizedText(section.title);
    if (title && title.trim()) return title;
  }
  if (meta?.titlePlaceholder) return meta.titlePlaceholder;
  return sectionKey
    .replace(/_[a-f0-9]+$/i, '')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (s) => s.toUpperCase())
    .trim();
}

function getOverrideTargetLabel(sectionKey) {
  if (sectionKey === '__header__') return "Header";
  return getSectionDisplayName(sectionKey);
}

function getContainerTargetLabel(members) {
  const names = (members || []).map((key) => getSectionDisplayName(key));
  if (names.length === 0) return "Section Container";
  if (names.length <= 2) return `Section Container: ${names.join(" + ")}`;
  return `Section Container: ${names[0]} + ${names[1]} +${names.length - 2}`;
}

const defaultExpandedSections = {
  _favorites: false,
  layout: false,
  fonts: false,
  colors: false,
  sections: false,
  buttons: false,
  header: false,
  customCss: false,
  versions: false,
};

const expandedSections = reactive({ ...defaultExpandedSections });

// Track expanded subsections: { 'sectionKey:subsectionName': boolean }
const expandedSubsections = reactive({});

function toggleSubsection(sectionKey, subsection) {
  const key = `${sectionKey}:${subsection}`;
  // Default is collapsed (false), so toggle from current state.
  const currentState = expandedSubsections[key] ?? false;
  expandedSubsections[key] = !currentState;
}

function isSubsectionExpanded(sectionKey, subsection) {
  if (hasActiveParamSearch.value) return true;
  const key = `${sectionKey}:${subsection}`;
  // Default to collapsed
  return expandedSubsections[key] ?? false;
}

const adminConfig = computed(() => state.adminDesignConfig);
const defaultSectionOrder = ["header", "layout", "sections", "colors", "buttons", "fonts", "versions", "customCss"];

const activeSectionOrder = computed(() => {
  const cfg = state.adminDesignConfig;
  const order = cfg?.sectionOrder || defaultSectionOrder;
  const hidden = cfg?.hiddenSections || [];
  let resolved = order.filter(section => !hidden.includes(section));
  if (isTemplateDesignEditMode.value) {
    resolved = resolved.filter((section) => section !== "versions");
  }
  return resolved;
});

const sectionContainerMaps = computed(() => {
  const order = Array.isArray(state.landingLayout?.order) && state.landingLayout.order.length
    ? state.landingLayout.order
    : Object.keys(state.sectionIds || {});
  return buildSectionContainerMaps(
    order,
    state.landingLayout?.structure || [],
    state.sectionIds || {},
  );
});

const overrideTargets = computed(() => {
  const targets = [];
  if (state.headerId || state.sectionDesignOverrides?.__header__) {
    targets.push({ key: '__header__', label: getOverrideTargetLabel('__header__'), members: ['__header__'], isContainer: false });
  }

  const hiddenSections = state.landingLayout?.hidden || {};
  const order = Array.isArray(state.landingLayout?.order) && state.landingLayout.order.length
    ? state.landingLayout.order
    : Object.keys(state.sectionIds || {});
  const emittedContainers = new Set();

  for (const key of order) {
    if (hiddenSections[key] === true) continue;
    const containerId = sectionContainerMaps.value.sectionToContainerId?.[key];
    if (containerId) {
      if (emittedContainers.has(containerId)) continue;
      const members = (sectionContainerMaps.value.containersById?.[containerId]?.members || [])
        .filter((memberKey) => hiddenSections[memberKey] !== true);
      if (members.length >= 2) {
        const targetKey = createSectionContainerTargetKey(containerId);
        if (targetKey) {
          targets.push({
            key: targetKey,
            label: getContainerTargetLabel(members),
            members,
            containerId,
            isContainer: true,
          });
          emittedContainers.add(containerId);
          continue;
        }
      }
    }
    targets.push({ key, label: getOverrideTargetLabel(key), members: [key], isContainer: false });
  }
  return targets;
});

function setOverrideTargetRef(key, el) {
  if (el) {
    overrideTargetRefs.value[key] = el;
  } else {
    delete overrideTargetRefs.value[key];
  }
}

function scrollOverrideTargetIntoView(key) {
  const targetEl = overrideTargetRefs.value[key];
  if (!targetEl) return;
  const bodyEl = targetEl.closest('.panel')?.querySelector('.body-scroll');
  if (!bodyEl) return;

  const bodyRect = bodyEl.getBoundingClientRect();
  const targetRect = targetEl.getBoundingClientRect();

  const topOutside = targetRect.top < bodyRect.top + 8;
  const bottomOutside = targetRect.bottom > bodyRect.bottom - 8;
  if (!topOutside && !bottomOutside) return;

  const scrollDelta = targetRect.top - bodyRect.top - 8;
  bodyEl.scrollTo({
    top: bodyEl.scrollTop + scrollDelta,
    behavior: 'smooth',
  });
}

function isOverrideTargetExpanded(key) {
  return expandedOverrideTargets[key] === true;
}

function resolveSectionToOverrideTargetKey(sectionKey) {
  const containerId = sectionContainerMaps.value.sectionToContainerId?.[sectionKey];
  if (!containerId) return sectionKey;
  return createSectionContainerTargetKey(containerId) || sectionKey;
}

function openOverrideTarget(key, options = {}) {
  if (!showOverrideTab.value) return;
  const { scroll = false } = options;
  key = resolveSectionToOverrideTargetKey(key);
  const availableKeys = new Set(overrideTargets.value.map((target) => target.key));
  if (!availableKeys.has(key)) {
    key = overrideTargets.value[0]?.key || null;
  }
  if (!key) return;

  activePanelTab.value = 'override';
  open.value = true;
  state.activeSectionDesignKey = key;
  for (const k of Object.keys(expandedOverrideTargets)) {
    expandedOverrideTargets[k] = false;
  }
  expandedOverrideTargets[key] = true;

  if (scroll) {
    nextTick(() => {
      window.setTimeout(() => scrollOverrideTargetIntoView(key), 150);
    });
  }
}

function toggleOverrideTarget(key) {
  const currentlyExpanded = isOverrideTargetExpanded(key);
  for (const k of Object.keys(expandedOverrideTargets)) {
    expandedOverrideTargets[k] = false;
  }
  if (!currentlyExpanded) {
    openOverrideTarget(key);
  } else if (state.activeSectionDesignKey === key) {
    state.activeSectionDesignKey = null;
  }
}

function getTargetSectionKeys(targetKey) {
  if (targetKey === '__header__') return ['__header__'];
  const containerId = parseSectionContainerTargetKey(targetKey);
  if (!containerId) return targetKey ? [targetKey] : [];
  return sectionContainerMaps.value.containersById?.[containerId]?.members || [];
}

function getPrimarySectionKeyForTarget(targetKey) {
  if (targetKey === '__header__') return '__header__';
  const containerId = parseSectionContainerTargetKey(targetKey);
  if (!containerId) return targetKey;
  return getContainerLeaderKey(containerId, sectionContainerMaps.value) || null;
}

function pruneOverrideTargetEntry(targetKey) {
  const target = state.sectionDesignOverrides?.[targetKey];
  if (!target || typeof target !== 'object') return;
  if (Object.keys(target).length === 0) delete state.sectionDesignOverrides[targetKey];
}

function isOverrideEnabled(key) {
  if (key === '__header__') {
    const ov = state.sectionDesignOverrides?.__header__;
    return ov?._active !== false;
  }
  const sectionKeys = getTargetSectionKeys(key);
  if (sectionKeys.length === 0) return true;
  return sectionKeys.every((sectionKey) => {
    const ov = state.sectionDesignOverrides?.[sectionKey];
    return ov?._active !== false;
  });
}

function setOverrideEnabled(key, enabled) {
  if (!state.sectionDesignOverrides || typeof state.sectionDesignOverrides !== 'object') {
    state.sectionDesignOverrides = {};
  }
  const sectionKeys = key === '__header__' ? ['__header__'] : getTargetSectionKeys(key);
  for (const sectionKey of sectionKeys) {
    if (!state.sectionDesignOverrides[sectionKey]) state.sectionDesignOverrides[sectionKey] = {};
    if (enabled) {
      delete state.sectionDesignOverrides[sectionKey]._active;
      pruneOverrideTargetEntry(sectionKey);
    } else {
      state.sectionDesignOverrides[sectionKey]._active = false;
    }
  }
}

function toggleOverrideEnabled(key, enabled) {
  setOverrideEnabled(key, enabled);
  markOverrideDirty(key);
}

function clearOverrideTarget(targetKey) {
  if (!state.sectionDesignOverrides || typeof state.sectionDesignOverrides !== 'object') return;
  const sectionKeys = targetKey === '__header__' ? ['__header__'] : getTargetSectionKeys(targetKey);
  let changed = false;
  for (const sectionKey of sectionKeys) {
    if (!state.sectionDesignOverrides?.[sectionKey]) continue;
    delete state.sectionDesignOverrides[sectionKey];
    changed = true;
  }
  if (changed) markOverrideDirty(targetKey);
}

function hasOverrideTargetData(targetKey) {
  if (!state.sectionDesignOverrides || typeof state.sectionDesignOverrides !== 'object') return false;
  const sectionKeys = targetKey === '__header__' ? ['__header__'] : getTargetSectionKeys(targetKey);
  return sectionKeys.some((sectionKey) => Boolean(state.sectionDesignOverrides?.[sectionKey]));
}

const headerFieldToParamMap = {
  title: ['heroTitleFontSize', 'heroTitleLineHeight', 'heroTitleLetterSpacing', 'heroTitleColor'],
  subtitle: ['heroSubtitleFontSize', 'heroSubtitleLineHeight', 'heroSubtitleLetterSpacing', 'heroSubtitleColor'],
  overlay_image: ['heroOverlayPosition', 'heroOverlaySize', 'heroOverlayParallax', 'heroOverlayParallaxDirection'],
  background_image: ['heroParallax'],
};
const alwaysVisibleHeaderOverrideParams = new Set(['heroHeight', 'headerInner', 'heroContentAlign', 'heroSeparator']);

function toCamelCaseParamKey(rawKey) {
  return String(rawKey || "").replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function toSnakeCaseParamKey(rawKey) {
  return String(rawKey || "").replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

function getCanonicalOverrideParamKey(rawKey) {
  return toCamelCaseParamKey(rawKey);
}

const constantSectionOverrideAliases = new Set([
  'hideSectionHeader',
  'hideSectionDescription',
  'removeSectionPadding',
  'removeSectionBackground',
  'hideSectionIfListEmptyPublic',
  'customCss',
]);
const constantSectionResolvedParams = new Set(['sectionBackgroundColor']);

function hasDirtyOverrides() {
  return Object.keys(dirtyOverrideKeys).length > 0;
}

function markOverrideDirty(targetKey) {
  const dirtyKeys = targetKey === '__header__' ? ['__header__'] : getTargetSectionKeys(targetKey);
  if (dirtyKeys.length === 0 && targetKey) {
    dirtyOverrideKeys[targetKey] = true;
  } else {
    for (const key of dirtyKeys) {
      dirtyOverrideKeys[key] = true;
    }
  }
  queueAutoSave();
}

function getSectionOverrideRecord(sectionKey) {
  return state.sectionDesignOverrides?.[sectionKey] || {};
}

function ensureSectionOverrideRecord(sectionKey) {
  if (!state.sectionDesignOverrides || typeof state.sectionDesignOverrides !== 'object') {
    state.sectionDesignOverrides = {};
  }
  if (!state.sectionDesignOverrides[sectionKey]) {
    state.sectionDesignOverrides[sectionKey] = {};
  }
  return state.sectionDesignOverrides[sectionKey];
}

function pruneEmptySectionOverrideRecord(sectionKey) {
  const target = state.sectionDesignOverrides?.[sectionKey];
  if (!target) return;
  if (Object.keys(target).length === 0) delete state.sectionDesignOverrides[sectionKey];
}

function getTargetOverrides(targetKey) {
  const primaryKey = getPrimarySectionKeyForTarget(targetKey);
  if (!primaryKey) return {};
  return getSectionOverrideRecord(primaryKey);
}

function ensureTargetOverrides(targetKey) {
  const primaryKey = getPrimarySectionKeyForTarget(targetKey);
  if (!primaryKey) return {};
  return ensureSectionOverrideRecord(primaryKey);
}

function pruneEmptyTargetOverrides(targetKey) {
  const primaryKey = getPrimarySectionKeyForTarget(targetKey);
  if (!primaryKey) return;
  pruneEmptySectionOverrideRecord(primaryKey);
}

function getHeaderOverrideVisibleParams() {
  const cfg = state.adminDesignConfig?.sectionOverrideParams;
  const allowed = new Set(cfg?.header || []);
  const enabled = new Set(state.headerEnabledFields || []);
  const paramOrder = state.adminDesignConfig?.paramOrder?.header || [];
  const headerOverrides = getTargetOverrides('__header__');
  const overrideParallaxEnabled = getOverrideAliasValue(headerOverrides, 'heroOverlayParallax');
  const effectiveOverlayParallaxEnabled =
    overrideParallaxEnabled == null
      ? Boolean(state.design?.heroOverlayParallax)
      : Boolean(overrideParallaxEnabled);

  const ordered = paramOrder.filter((p) => allowed.has(p));
  for (const param of allowed) {
    if (!ordered.includes(param)) ordered.push(param);
  }

  const filtered = [];
  for (const param of ordered) {
    if (param === 'heroOverlayParallaxDirection' && !effectiveOverlayParallaxEnabled) {
      continue;
    }
    if (alwaysVisibleHeaderOverrideParams.has(param)) {
      filtered.push(param);
      continue;
    }
    let fieldMatch = false;
    for (const [field, params] of Object.entries(headerFieldToParamMap)) {
      if (params.includes(param)) {
        fieldMatch = true;
        if (enabled.has(field)) filtered.push(param);
        break;
      }
    }
    if (!fieldMatch) filtered.push(param);
  }
  return filtered;
}

function getSectionOverrideVisibleParams(targetKey) {
  const cfg = state.adminDesignConfig?.sectionOverrideParams;
  const generic = Array.isArray(cfg?.generic) ? cfg.generic : [];
  const baseSectionKey = getPrimarySectionKeyForTarget(targetKey);
  const sectionType = state.sectionMeta?.[baseSectionKey]?.sectionType;
  const typeSpecific = Array.isArray(cfg?.byType?.[sectionType]) ? cfg.byType[sectionType] : [];

  const resolveParamKey = (rawKey) => {
    if (!rawKey) return null;
    const camelKey = toCamelCaseParamKey(rawKey);
    const canonicalKey = getCanonicalOverrideParamKey(rawKey);
    const candidates = [canonicalKey, camelKey, rawKey].filter((candidate, index, list) =>
      Boolean(candidate) && list.indexOf(candidate) === index
    );

    for (const candidate of candidates) {
      if (adminConfig.value?.parameters?.[candidate] || defaultParamConfigs[candidate]) {
        return candidate;
      }
    }
    return null;
  };

  const allowed = [];
  for (const rawParam of [...generic, ...typeSpecific]) {
    if (constantSectionOverrideAliases.has(rawParam)) continue;
    const resolved = resolveParamKey(rawParam);
    if (resolved && !constantSectionResolvedParams.has(resolved) && !allowed.includes(resolved)) {
      allowed.push(resolved);
    }
  }

  if (!allowed.length) {
    return getVisibleParamsForSection('sections').filter((param) => !constantSectionResolvedParams.has(param));
  }

  const allowedSet = new Set(allowed);
  const ordered = [];
  const sectionOrder = state.adminDesignConfig?.paramOrder?.sections || [];

  for (const param of sectionOrder) {
    if (allowedSet.has(param)) ordered.push(param);
  }
  for (const param of allowed) {
    if (!ordered.includes(param)) ordered.push(param);
  }

  return ordered
    .filter((param) => !constantSectionResolvedParams.has(param))
    .filter((param) => !!(adminConfig.value?.parameters?.[param] || defaultParamConfigs[param]));
}

const defaultSubsectionOrder = {
  sections: ["Container", "Border", "Hardbox Shadow", "Hard Box-Shadow", "Background Pattern"],
  colors: ["Base Vars", "Topbar", "Header Titles", "text header", "Background", "Menus", "Sidebar", "Typography", "Links"],
  fonts: ["Hero Title", "Hero Subtitle", "Paragraph", "Typography", "Links", "Headings", "Headings (h1 – h6)", "H1", "H2", "H3", "H4", "H5", "H6"],
};

function sortSubsectionGroups(sectionKey, groups) {
  const order = defaultSubsectionOrder[sectionKey];
  if (!order) return groups;
  const orderIndex = new Map(order.map((label, index) => [label, index]));
  return groups
    .map((group, index) => ({ group, index }))
    .sort((a, b) => {
      const aOrder = orderIndex.has(a.group.subsection) ? orderIndex.get(a.group.subsection) : Number.MAX_SAFE_INTEGER;
      const bOrder = orderIndex.has(b.group.subsection) ? orderIndex.get(b.group.subsection) : Number.MAX_SAFE_INTEGER;
      if (aOrder !== bOrder) return aOrder - bOrder;
      return a.index - b.index;
    })
    .map(({ group }) => group);
}

function groupParamsBySubsection(params, configGetter, sectionKey = "") {
  const groups = [];
  const groupsBySubsection = new Map();
  for (const paramKey of params) {
    const cfg = configGetter(paramKey);
    const subsection = cfg.subsection || null;
    let group = groupsBySubsection.get(subsection);
    if (!group) {
      group = { subsection, params: [] };
      groupsBySubsection.set(subsection, group);
      groups.push(group);
    }
    group.params.push(paramKey);
  }
  return sortSubsectionGroups(sectionKey, groups);
}

function getOverrideGroupLabel(config) {
  const sectionKey = config?.section || "";
  const sectionLabel = sectionLabels[sectionKey] || sectionKey || "General";
  const subsection = config?.subsection || "";
  return subsection ? `${sectionLabel} / ${subsection}` : sectionLabel;
}

function groupOverrideParams(params, targetKey) {
  const groups = [];
  const byLabel = new Map();
  for (const paramKey of params) {
    const cfg = getOverrideParamConfig(targetKey, paramKey);
    const label = getOverrideGroupLabel(cfg);
    let group = byLabel.get(label);
    if (!group) {
      group = { subsection: label, params: [] };
      byLabel.set(label, group);
      groups.push(group);
    }
    group.params.push(paramKey);
  }
  return groups.sort((a, b) =>
    String(a.subsection || "").localeCompare(String(b.subsection || ""), undefined, {
      sensitivity: "base",
      numeric: true,
    })
  );
}

const overrideParamsByTarget = computed(() => {
  const result = {};
  for (const target of overrideTargets.value) {
    const params = (target.key === '__header__'
      ? getHeaderOverrideVisibleParams()
      : getSectionOverrideVisibleParams(target.key))
      .filter((paramKey) => {
        const cfg = getOverrideParamConfig(target.key, paramKey);
        return matchesParamSearch(paramKey, cfg.label, cfg.subsection, getOverrideGroupLabel(cfg));
      });
    result[target.key] = groupOverrideParams(params, target.key);
  }
  return result;
});

const visibleOverrideTargets = computed(() => {
  if (!hasActiveParamSearch.value) return overrideTargets.value;
  return overrideTargets.value.filter((target) => {
    const groups = overrideParamsByTarget.value[target.key] || [];
    return groups.some((group) => group.params.length > 0);
  });
});

function getOverrideParamConfig(targetKey, paramKey) {
  const canonicalParamKey = getCanonicalOverrideParamKey(paramKey);
  let config;

  if (adminConfig.value?.parameters?.[canonicalParamKey]) {
    config = { ...adminConfig.value.parameters[canonicalParamKey] };
  } else if (defaultParamConfigs[canonicalParamKey]) {
    config = { ...defaultParamConfigs[canonicalParamKey] };
  } else if (adminConfig.value?.parameters?.[paramKey]) {
    config = { ...adminConfig.value.parameters[paramKey] };
  } else if (defaultParamConfigs[paramKey]) {
    config = { ...defaultParamConfigs[paramKey] };
  } else {
    config = { visible: true, favorite: false, type: 'unknown', label: canonicalParamKey || paramKey };
  }

  // In overrides, keep base-color linking available for all color params.
  delete config.isBase;

  const targetOverrides = getTargetOverrides(targetKey);
  const responsiveModes = getOverrideMapWithAliases(targetOverrides._responsiveModes || {});
  const responsiveValues = getOverrideMapWithAliases(targetOverrides._responsiveValues || {});
  const hasExplicitMode = paramKey in responsiveModes;
  if (hasExplicitMode) {
    const mode = responsiveModes[paramKey];
    if (mode && typeof mode === 'string') config.responsive = mode;
    else delete config.responsive;
    return config;
  }

  const respVal = responsiveValues[paramKey];
  if (respVal) {
    if (respVal.currentMode && typeof respVal.currentMode === 'string') {
      config.responsive = respVal.currentMode;
      return config;
    }
    if (respVal.media && typeof respVal.media === 'object' && Object.keys(respVal.media).length > 0) {
      config.responsive = 'media';
      return config;
    }
    if (respVal.clamp && typeof respVal.clamp === 'object' && Object.keys(respVal.clamp).length > 0) {
      config.responsive = 'clamp';
      return config;
    }
  }

  delete config.responsive;
  return config;
}

function getOverrideAliasValue(source, paramKey) {
  if (!source || typeof source !== "object") return undefined;
  if (source[paramKey] !== undefined) return source[paramKey];
  const snakeKey = toSnakeCaseParamKey(paramKey);
  if (source[snakeKey] !== undefined) return source[snakeKey];
  const camelKey = toCamelCaseParamKey(paramKey);
  if (source[camelKey] !== undefined) return source[camelKey];
  return undefined;
}

function getOverrideMapWithAliases(source) {
  if (!source || typeof source !== "object") return {};
  const mapped = { ...source };
  for (const [rawKey, value] of Object.entries(source)) {
    const camelKey = toCamelCaseParamKey(rawKey);
    if (camelKey && mapped[camelKey] === undefined) {
      mapped[camelKey] = value;
    }
  }
  return mapped;
}

function getOverrideParamValue(targetKey, paramKey) {
  const value = getOverrideAliasValue(getTargetOverrides(targetKey), paramKey);
  return value === undefined ? null : value;
}

function getOverrideResponsiveValues(targetKey) {
  return getOverrideMapWithAliases(getTargetOverrides(targetKey)._responsiveValues || {});
}

function getOverrideSelectedUnits(targetKey) {
  return getOverrideMapWithAliases(getTargetOverrides(targetKey)._selectedUnits || {});
}

function getOverrideColorLinks(targetKey) {
  if (targetKey === '__header__') {
    return adminConfig.value?.colorLinks || {};
  }
  return getOverrideMapWithAliases(getTargetOverrides(targetKey)._colorLinks || {});
}

function getOverrideColorVariations(targetKey) {
  return getOverrideMapWithAliases(getTargetOverrides(targetKey)._colorVariations || {});
}

function setOverrideParamValue(targetKey, paramKey, value) {
  const sectionKeys = targetKey === '__header__' ? ['__header__'] : getTargetSectionKeys(targetKey);
  if (sectionKeys.length === 0) return;

  for (const sectionKey of sectionKeys) {
    if (value === null || value === undefined || value === '') {
      if (state.sectionDesignOverrides?.[sectionKey]) {
        delete state.sectionDesignOverrides[sectionKey][paramKey];
        pruneEmptySectionOverrideRecord(sectionKey);
      }
      continue;
    }
    const target = ensureSectionOverrideRecord(sectionKey);
    target[paramKey] = value;
  }
  markOverrideDirty(targetKey);
}

function getUnitMinForParam(paramKey, unit) {
  let cfg;
  if (paramKey.startsWith('btnType_')) {
    const withoutPrefix = paramKey.slice('btnType_'.length);
    const splitIdx = withoutPrefix.lastIndexOf('_');
    const buttonParamKey = splitIdx > 0 ? withoutPrefix.slice(splitIdx + 1) : withoutPrefix;
    cfg = buttonParamConfigs[buttonParamKey] || {};
  } else {
    cfg = getParamConfig(paramKey) || {};
  }

  const unitConfigs = Array.isArray(cfg.unitConfigs) ? cfg.unitConfigs : null;
  if (unitConfigs && unitConfigs.length > 0) {
    const matching = unitConfigs.find((uc) => uc.unit === unit);
    if (matching?.min != null) return matching.min;
    if (unitConfigs[0]?.min != null) return unitConfigs[0].min;
  }

  if (cfg.min != null) return cfg.min;
  return 0;
}

function updateOverrideSelectedUnit(targetKey, paramKey, unit) {
  const sourceTarget = ensureTargetOverrides(targetKey);
  const responsiveValues = getOverrideMapWithAliases(sourceTarget._responsiveValues || {});
  const responsiveModes = getOverrideMapWithAliases(sourceTarget._responsiveModes || {});
  const overrideRv = responsiveValues[paramKey];
  const mode = responsiveModes[paramKey]
    || overrideRv?.currentMode
    || (overrideRv?.media ? 'media' : null)
    || (overrideRv?.clamp ? 'clamp' : null);
  const sectionKeys = targetKey === '__header__' ? ['__header__'] : getTargetSectionKeys(targetKey);

  for (const sectionKey of sectionKeys) {
    const target = ensureSectionOverrideRecord(sectionKey);
    if (!target._selectedUnits) target._selectedUnits = {};
    target._selectedUnits[paramKey] = unit;

    if (mode === 'media') {
      if (!target._responsiveValues) target._responsiveValues = {};
      if (!target._responsiveValues[paramKey]) target._responsiveValues[paramKey] = {};
      target._responsiveValues[paramKey].currentMode = 'media';
      const minValue = getUnitMinForParam(paramKey, unit);
      target[paramKey] = minValue;
      target._responsiveValues[paramKey].media = {
        ...target._responsiveValues[paramKey].media,
        mobile: minValue,
        tablet: minValue,
        desktop: minValue,
      };
    }
  }

  if (mode === 'media') {
    markOverrideDirty(targetKey);
    return;
  }

  setOverrideParamValue(targetKey, paramKey, null);
}

function updateOverrideResponsiveValue(targetKey, paramKey, mode, values) {
  const sectionKeys = targetKey === '__header__' ? ['__header__'] : getTargetSectionKeys(targetKey);
  for (const sectionKey of sectionKeys) {
    const target = ensureSectionOverrideRecord(sectionKey);
    if (!target._responsiveValues) target._responsiveValues = {};
    if (!target._responsiveValues[paramKey]) target._responsiveValues[paramKey] = {};
    target._responsiveValues[paramKey][mode] = values;
  }
  markOverrideDirty(targetKey);
}

function updateOverrideResponsiveMode(targetKey, paramKey, mode) {
  const sectionKeys = targetKey === '__header__' ? ['__header__'] : getTargetSectionKeys(targetKey);
  for (const sectionKey of sectionKeys) {
    const target = ensureSectionOverrideRecord(sectionKey);
    if (!target._responsiveModes) target._responsiveModes = {};
    target._responsiveModes[paramKey] = mode || null;

    if (!mode) {
      if (target._responsiveValues?.[paramKey]) delete target._responsiveValues[paramKey];
      continue;
    }

    if (!target._responsiveValues) target._responsiveValues = {};
    if (!target._responsiveValues[paramKey]) target._responsiveValues[paramKey] = {};
    target._responsiveValues[paramKey].currentMode = mode;
  }
  markOverrideDirty(targetKey);
}

function updateOverrideColorLink(targetKey, paramKey, baseColorKey, resetOnUnlink = true) {
  if (targetKey === '__header__') {
    if (!state.adminDesignConfig) return;
    if (!state.adminDesignConfig.colorLinks) state.adminDesignConfig.colorLinks = {};
    if (!baseColorKey) {
      delete state.adminDesignConfig.colorLinks[paramKey];
      adminConfigDirty.value = true;
      if (resetOnUnlink) {
        setOverrideParamValue(targetKey, paramKey, null);
      }
      queueAutoSave();
      return;
    }
    state.adminDesignConfig.colorLinks[paramKey] = baseColorKey;
    adminConfigDirty.value = true;
    if (baseColorKey === 'transparent') setOverrideParamValue(targetKey, paramKey, 'transparent');
    else if (baseColorKey === 'highContrast') setOverrideParamValue(targetKey, paramKey, '__high_contrast__');
    else {
      const resolved = getLinkedBaseColorValue(baseColorKey);
      if (resolved !== null) setOverrideParamValue(targetKey, paramKey, resolved);
    }
    queueAutoSave();
    return;
  }

  const sectionKeys = getTargetSectionKeys(targetKey);
  for (const sectionKey of sectionKeys) {
    const target = ensureSectionOverrideRecord(sectionKey);
    if (!target._colorLinks) target._colorLinks = {};
    if (!baseColorKey) {
      delete target._colorLinks[paramKey];
      if (Object.keys(target._colorLinks).length === 0) delete target._colorLinks;
    } else {
      target._colorLinks[paramKey] = baseColorKey;
    }
  }
  if (!baseColorKey) {
    if (resetOnUnlink) {
      setOverrideParamValue(targetKey, paramKey, null);
    } else {
      markOverrideDirty(targetKey);
    }
    return;
  }
  if (baseColorKey === 'transparent') setOverrideParamValue(targetKey, paramKey, 'transparent');
  else if (baseColorKey === 'highContrast') setOverrideParamValue(targetKey, paramKey, '__high_contrast__');
  else {
    const resolved = getLinkedBaseColorValue(baseColorKey);
    if (resolved !== null) setOverrideParamValue(targetKey, paramKey, resolved);
  }
  markOverrideDirty(targetKey);
}

function updateOverrideColorVariation(targetKey, paramKey, variation) {
  const normalized = normalizeColorVariation(variation);
  const sectionKeys = targetKey === '__header__' ? ['__header__'] : getTargetSectionKeys(targetKey);
  for (const sectionKey of sectionKeys) {
    const target = ensureSectionOverrideRecord(sectionKey);
    if (!target._colorVariations) target._colorVariations = {};
    if (normalized === DEFAULT_COLOR_VARIATION) {
      delete target._colorVariations[paramKey];
      if (Object.keys(target._colorVariations).length === 0) delete target._colorVariations;
    } else {
      target._colorVariations[paramKey] = normalized;
    }
  }
  markOverrideDirty(targetKey);
}

const activeFontFamilies = computed(() => {
  if (adminConfig.value?.fontFamilies?.length) {
    return adminConfig.value.fontFamilies;
  }
  return [
    { value: 'system-ui, -apple-system, sans-serif', label: 'System UI' },
    { value: '"Inter", sans-serif', label: 'Inter' },
    { value: '"Roboto", sans-serif', label: 'Roboto' },
    { value: '"Open Sans", sans-serif', label: 'Open Sans' },
    { value: '"Lato", sans-serif', label: 'Lato' },
    { value: '"Montserrat", sans-serif', label: 'Montserrat' },
    { value: '"Poppins", sans-serif', label: 'Poppins' },
    { value: '"Playfair Display", serif', label: 'Playfair Display' },
    { value: '"Merriweather", serif', label: 'Merriweather' },
    { value: '"Georgia", serif', label: 'Georgia' },
    { value: '"Source Code Pro", monospace', label: 'Source Code Pro' },
  ];
});

const activeFontWeights = computed(() => {
  const allWeights = [
    { value: '300', label: 'Light (300)' },
    { value: '400', label: 'Regular (400)' },
    { value: '500', label: 'Medium (500)' },
    { value: '600', label: 'Semi-Bold (600)' },
    { value: '700', label: 'Bold (700)' },
    { value: '800', label: 'Extra-Bold (800)' },
    { value: '900', label: 'Black (900)' },
  ];
  return allWeights;
});

const hasActiveParamSearch = computed(() => paramSearchQuery.value.trim().length > 0);
const normalizedParamSearch = computed(() => paramSearchQuery.value.trim().toLowerCase());

function matchesParamSearch(...values) {
  const query = normalizedParamSearch.value;
  if (!query) return true;
  return values.some((value) => String(value || '').toLowerCase().includes(query));
}

const baseColorOptions = computed(() => {
  if (!adminConfig.value?.parameters) return [];
  return Object.entries(adminConfig.value.parameters)
    .filter(([, p]) => p.type === 'color' && p.isBase)
    .map(([key, p]) => ({ key, label: p.label }));
});

function getLinkedBaseColorValue(baseColorKey) {
  if (!baseColorKey) return null;
  const fromDesign = state.design?.[baseColorKey];
  if (fromDesign !== undefined && fromDesign !== null && String(fromDesign).trim() !== '') {
    return fromDesign;
  }
  const fromParamDefault = adminConfig.value?.parameters?.[baseColorKey]?.default;
  if (fromParamDefault !== undefined && fromParamDefault !== null && String(fromParamDefault).trim() !== '') {
    return fromParamDefault;
  }
  return null;
}

const visibleParamsBySection = computed(() => {
  // Track reactive dependencies used by isParamHidden()
  void [state.design.fullWidth, state.design.sectionBgPattern, state.design.hardBoxShadowEnabled,
        state.design.hardBoxShadowOffsetSource, state.design.sectionBorderWidth, state.design.headingLinearScaling,
        state.design.heroTitleTextShadowEnabled];
  
  const result = {};
  for (const sKey of activeSectionOrder.value) {
    result[sKey] = getVisibleParamsForSection(sKey).filter((k) => {
      const cfg = getParamConfig(k);
      return !isParamHidden(k) && matchesParamSearch(k, cfg.label, cfg.subsection);
    });
  }
  return result;
});

// Group params by subsection for each section
const paramsBySubsection = computed(() => {
  const result = {};
  for (const sKey of activeSectionOrder.value) {
    const params = visibleParamsBySection.value[sKey] || [];
    result[sKey] = groupParamsBySubsection(params, getParamConfig, sKey);
  }
  return result;
});

const favoriteParams = computed(() => {
  void [state.design.headingLinearScaling, state.design.heroTitleTextShadowEnabled]; // track dependencies for isParamHidden
  if (!adminConfig.value?.parameters) return [];
  return Object.entries(adminConfig.value.parameters)
    .filter(([key, p]) => p.favorite && p.visible && !isParamHidden(key) && matchesParamSearch(key, p.label, p.subsection))
    .map(([key]) => key);
});

// Group favorites by section/subsection for collapsible display
const favoritesBySubsection = computed(() => {
  const groups = [];
  const seen = new Set();
  for (const paramKey of favoriteParams.value) {
    if (seen.has(paramKey)) continue;
    seen.add(paramKey);
    const cfg = getParamConfig(paramKey);
    const sectionKey = cfg.section || '';
    const subsection = cfg.subsection || '';
    const groupKey = `${sectionKey}:${subsection}`;
    
    let group = groups.find(g => g.key === groupKey);
    if (!group) {
      const sectionLabel = sectionLabels[sectionKey] || sectionKey;
      group = {
        key: groupKey,
        label: subsection ? `${sectionLabel} / ${subsection}` : sectionLabel,
        params: []
      };
      groups.push(group);
    }
    group.params.push(paramKey);
  }
  return groups;
});

const designValues = computed(() => {
  const result = {};
  for (const [key, defaultVal] of Object.entries(DEFAULT_DESIGN)) {
    result[key] = state.design[key] ?? defaultVal;
  }
  if (adminConfig.value?.parameters) {
    for (const [key, param] of Object.entries(adminConfig.value.parameters)) {
      if (Object.prototype.hasOwnProperty.call(result, key)) continue;
      result[key] = state.design[key] ?? param?.default ?? null;
    }
  }
  for (const [key, value] of Object.entries(state.design || {})) {
    if (!Object.prototype.hasOwnProperty.call(result, key)) {
      result[key] = value;
    }
  }
  return result;
});

const responsiveValues = computed(() => state.design.responsiveValues || {});

const selectedUnits = computed(() => state.design.selectedUnits || {});

const overrideParamSources = computed(() => {
  const sourceMap = {};
  const overrides = state.sectionDesignOverrides || {};
  for (const [targetKey, targetOverrides] of Object.entries(overrides)) {
    if (targetKey !== '__header__' && state.landingLayout?.hidden?.[targetKey] === true) continue;
    if (!targetOverrides || targetOverrides._active === false) continue;
    const mappedKey = targetKey === '__header__'
      ? '__header__'
      : resolveSectionToOverrideTargetKey(targetKey);
    const mappedTarget = overrideTargets.value.find((target) => target.key === mappedKey);
    const sourceKey = mappedTarget?.key || mappedKey;
    const sourceLabel = mappedTarget?.label || getOverrideTargetLabel(targetKey);

    for (const [paramKey, value] of Object.entries(targetOverrides)) {
      if (paramKey.startsWith('_')) continue;
      if (value === null || value === undefined || value === '') continue;
      if (!sourceMap[paramKey]) sourceMap[paramKey] = new Map();
      sourceMap[paramKey].set(sourceKey, sourceLabel);
    }

    const responsive = targetOverrides._responsiveValues || {};
    for (const paramKey of Object.keys(responsive)) {
      if (!sourceMap[paramKey]) sourceMap[paramKey] = new Map();
      sourceMap[paramKey].set(sourceKey, sourceLabel);
    }
  }

  const result = {};
  for (const [paramKey, sources] of Object.entries(sourceMap)) {
    result[paramKey] = Array.from(sources.entries()).map(([key, label]) => ({ key, label }));
  }
  return result;
});

function globalOverrideInfo(paramKey) {
  const sources = overrideParamSources.value[paramKey] || [];
  if (!sources.length) return '';
  return `Overridden by: ${sources.map((s) => s.label).join(', ')}`;
}

function globalOverrideSources(paramKey) {
  return overrideParamSources.value[paramKey] || [];
}

function updateSelectedUnit(paramKey, unit) {
  if (!state.design.selectedUnits) state.design.selectedUnits = {};
  state.design.selectedUnits[paramKey] = unit;
  updateDesignSetting('selectedUnits', { ...state.design.selectedUnits });

  const globalRv = state.design.responsiveValues?.[paramKey];
  const mode = globalRv?.currentMode
    || state.adminDesignConfig?.parameters?.[paramKey]?.responsive
    || (globalRv?.media ? 'media' : null)
    || (globalRv?.clamp ? 'clamp' : null);

  if (mode === 'media') {
    if (!state.design.responsiveValues) state.design.responsiveValues = {};
    if (!state.design.responsiveValues[paramKey]) state.design.responsiveValues[paramKey] = {};
    state.design.responsiveValues[paramKey].currentMode = 'media';
    const minValue = getUnitMinForParam(paramKey, unit);
    if (paramKey in DEFAULT_DESIGN) {
      updateDesignSetting(paramKey, minValue);
    } else if (paramKey.startsWith('btnType_')) {
      const withoutPrefix = paramKey.slice('btnType_'.length);
      const splitIdx = withoutPrefix.lastIndexOf('_');
      if (splitIdx > 0) {
        const typeId = withoutPrefix.slice(0, splitIdx);
        const buttonParamKey = withoutPrefix.slice(splitIdx + 1);
        if (!state.design.buttonTypeStyles) state.design.buttonTypeStyles = {};
        if (!state.design.buttonTypeStyles[typeId]) state.design.buttonTypeStyles[typeId] = {};
        state.design.buttonTypeStyles[typeId][buttonParamKey] = minValue;
        updateDesignSetting('buttonTypeStyles', { ...state.design.buttonTypeStyles });
      }
    }
    state.design.responsiveValues[paramKey].media = {
      ...state.design.responsiveValues[paramKey].media,
      mobile: minValue,
      tablet: minValue,
      desktop: minValue,
    };
    updateDesignSetting('responsiveValues', { ...state.design.responsiveValues });
    queueAutoSave();
    return;
  }

  if (paramKey in DEFAULT_DESIGN) {
    updateDesignSetting(paramKey, null);
  } else if (paramKey.startsWith('btnType_')) {
    const withoutPrefix = paramKey.slice('btnType_'.length);
    const splitIdx = withoutPrefix.lastIndexOf('_');
    if (splitIdx > 0) {
      const typeId = withoutPrefix.slice(0, splitIdx);
      const buttonParamKey = withoutPrefix.slice(splitIdx + 1);
      if (!state.design.buttonTypeStyles) state.design.buttonTypeStyles = {};
      if (!state.design.buttonTypeStyles[typeId]) state.design.buttonTypeStyles[typeId] = {};
      state.design.buttonTypeStyles[typeId][buttonParamKey] = null;
      updateDesignSetting('buttonTypeStyles', { ...state.design.buttonTypeStyles });
    }
  }

  queueAutoSave();
}

// Button per-type system
const buttonParamBaseNameToDesignKey = {
  bgColor: 'buttonBgColor', color: 'buttonColor', borderColor: 'buttonBorderColor',
  hoverBgColor: 'buttonHoverBgColor', hoverColor: 'buttonHoverColor', hoverBorderColor: 'buttonHoverBorderColor',
  borderRadius: 'buttonBorderRadius', borderWidth: 'buttonBorderWidth',
  fontSize: 'buttonFontSize',
  paddingX: 'buttonPaddingX', paddingY: 'buttonPaddingY',
};

const buttonParamConfigs = {
  bgColor: { type: 'color', label: 'Background' },
  color: { type: 'color', label: 'Text Color' },
  borderColor: { type: 'color', label: 'Border Color' },
  hoverBgColor: { type: 'color', label: 'Hover Background' },
  hoverColor: { type: 'color', label: 'Hover Text Color' },
  hoverBorderColor: { type: 'color', label: 'Hover Border Color' },
  borderRadius: { type: 'slider', label: 'Border Radius', min: 0, max: 24, step: 1, unit: 'px' },
  borderWidth: { type: 'slider', label: 'Border Width', min: 0, max: 4, step: 1, unit: 'px' },
  fontSize: { type: 'slider', label: 'Font Size', min: 10, max: 32, step: 1, unit: 'px' },
  paddingX: { type: 'slider', label: 'Horizontal Padding', min: 8, max: 32, step: 2, unit: 'px' },
  paddingY: { type: 'slider', label: 'Vertical Padding', min: 4, max: 20, step: 2, unit: 'px' },
};

const perTypeParamNames = computed(() => adminConfig.value?.buttonPerTypeParams || ['bgColor', 'color', 'borderColor']);

const sharedButtonParams = computed(() => {
  const perType = new Set(perTypeParamNames.value);
  const sharedDesignKeys = new Set();
  for (const [baseName, designKey] of Object.entries(buttonParamBaseNameToDesignKey)) {
    if (!perType.has(baseName)) sharedDesignKeys.add(designKey);
  }
  return (visibleParamsBySection.value.buttons || []).filter(k => sharedDesignKeys.has(k));
});

const enabledButtonInstances = computed(() => {
  return (adminConfig.value?.buttonInstances || []).filter(b => b.enabled);
});

const perTypeButtonParamDefs = computed(() => {
  return perTypeParamNames.value
    .filter((key) => matchesParamSearch(key, buttonParamConfigs[key]?.label))
    .map(key => ({
      key,
      config: { visible: true, favorite: false, section: 'buttons', ...buttonParamConfigs[key] },
    }));
});

function showGlobalSection(sectionKey) {
  if (!hasActiveParamSearch.value) return true;
  if (sectionKey === 'customCss' || sectionKey === 'versions') return false;
  if (sectionKey === 'buttons') {
    return sharedButtonParams.value.length > 0 || (enabledButtonInstances.value.length > 0 && perTypeButtonParamDefs.value.length > 0);
  }
  return (visibleParamsBySection.value[sectionKey] || []).length > 0;
}

function getButtonTypeValue(typeId, paramKey) {
  const value = state.design.buttonTypeStyles?.[typeId]?.[paramKey];
  if (value === undefined || value === null) return null;
  if (typeof value === 'string' && value.trim() === '') return null;
  return value;
}

function updateButtonTypeStyle(typeId, paramKey, value) {
  if (!state.design.buttonTypeStyles) state.design.buttonTypeStyles = {};
  if (!state.design.buttonTypeStyles[typeId]) state.design.buttonTypeStyles[typeId] = {};
  const isCleared = value === null || value === undefined || (typeof value === 'string' && value.trim() === '');
  if (isCleared) {
    delete state.design.buttonTypeStyles[typeId][paramKey];
    if (Object.keys(state.design.buttonTypeStyles[typeId]).length === 0) {
      delete state.design.buttonTypeStyles[typeId];
    }
    const linkKey = `btnType_${typeId}_${paramKey}`;
    if (!isTemplateDesignEditMode.value && state.adminDesignConfig?.colorLinks && Object.prototype.hasOwnProperty.call(state.adminDesignConfig.colorLinks, linkKey)) {
      delete state.adminDesignConfig.colorLinks[linkKey];
      adminConfigDirty.value = true;
    }
  } else {
    state.design.buttonTypeStyles[typeId][paramKey] = value;
  }
  updateDesignSetting('buttonTypeStyles', { ...state.design.buttonTypeStyles });
  queueAutoSave();
}

function updateButtonTypeLink(typeId, paramKey, baseColorKey, resetOnUnlink = true) {
  if (isTemplateDesignEditMode.value) {
    return;
  }
  if (!state.adminDesignConfig) return;
  if (!state.adminDesignConfig.colorLinks) state.adminDesignConfig.colorLinks = {};
  const linkKey = `btnType_${typeId}_${paramKey}`;
  if (!baseColorKey) {
    delete state.adminDesignConfig.colorLinks[linkKey];
    adminConfigDirty.value = true;
    if (resetOnUnlink) {
      updateButtonTypeStyle(typeId, paramKey, null);
      return;
    }
    queueAutoSave();
    return;
  }
  state.adminDesignConfig.colorLinks[linkKey] = baseColorKey;
  adminConfigDirty.value = true;
  if (baseColorKey === 'transparent') {
    updateButtonTypeStyle(typeId, paramKey, 'transparent');
  } else if (baseColorKey === 'highContrast') {
    updateButtonTypeStyle(typeId, paramKey, '__high_contrast__');
  } else {
    const resolved = getLinkedBaseColorValue(baseColorKey);
    if (resolved !== null) updateButtonTypeStyle(typeId, paramKey, resolved);
  }
  queueAutoSave();
}

watch(() => state.design.fullWidth, (newValue) => {
  state.landingLayout.fullWidth = newValue;
});

function toggleOpen() { open.value = !open.value; }
function toggleSection(section) {
  const isCurrentlyOpen = expandedSections[section];
  // Close all sections first (accordion behavior)
  for (const key of Object.keys(expandedSections)) {
    expandedSections[key] = false;
  }
  // Open the clicked section if it was closed
  if (!isCurrentlyOpen) {
    expandedSections[section] = true;
  }
}

// UI configs for design parameters - derived from designDefs.js
const defaultParamConfigs = PARAM_CONFIGS;

function getParamConfig(paramKey) {
  if (adminConfig.value?.parameters?.[paramKey]) {
    return adminConfig.value.parameters[paramKey];
  }
  if (defaultParamConfigs[paramKey]) {
    return defaultParamConfigs[paramKey];
  }
  return { visible: true, favorite: false, type: 'unknown', label: paramKey };
}

function isParamHidden(paramKey) {
  const d = state.design;

  // Fallback high-contrast controls are configured in Admin Design > Color Linking.
  if (paramKey === 'highContrastDark' || paramKey === 'highContrastLight') {
    return true;
  }

  // Layout: outer spacing only applies in full-width mode
  if (paramKey === 'outerSpacingSection' || paramKey === 'outerSpacingNonSection') {
    return !d.fullWidth;
  }

  const pattern = d.sectionBgPattern || 'none';
  const isAlpha = pattern === 'alpha_gradient' || pattern === 'alpha_gradient_shuffled';
  const isColor = pattern === 'alternating' || pattern === 'gradient' || pattern === 'gradient_shuffled';

  // Background pattern: all children hidden when pattern is 'none'
  if (paramKey === 'sectionBgColor1' || paramKey === 'sectionBgColor2') {
    return pattern === 'none' || isAlpha;
  }
  if (paramKey === 'sectionBgOpacity1' || paramKey === 'sectionBgOpacity2') {
    return pattern === 'none' || isColor;
  }

  // Hard box-shadow: children hidden when not enabled
  if (paramKey === 'hardBoxShadowOffsetSource' || paramKey === 'hardBoxShadowBrightness') {
    return !d.hardBoxShadowEnabled;
  }
  if (paramKey === 'hardBoxShadowOffsetCustom') {
    return !d.hardBoxShadowEnabled || (d.hardBoxShadowOffsetSource || 'padding') !== 'custom';
  }

  // Hero title text-shadow: children hidden when not enabled
  if (paramKey === 'heroTitleTextShadowOffset' || paramKey === 'heroTitleTextShadowColor') {
    return !d.heroTitleTextShadowEnabled;
  }

  // Overlay parallax direction is only relevant when overlay parallax is enabled
  if (paramKey === 'heroOverlayParallaxDirection') {
    return !d.heroOverlayParallax;
  }

  // Section border: color/style hidden when border width is 0
  if (paramKey === 'sectionBorderColor' || paramKey === 'sectionBorderStyle') {
    return (d.sectionBorderWidth ?? 0) === 0;
  }

  // Heading linear scaling: hide h2-h5 font-size, letter-spacing, line-height when enabled
  if (d.headingLinearScaling) {
    const match = paramKey.match(/^h([2-5])(FontSize|LetterSpacing|LineHeight)$/);
    if (match) return true;
  }

  return false;
}

function getVisibleParamsForSection(sectionKey) {
  const fallback = fallbackParamsBySection[sectionKey] || [];
  if (!adminConfig.value?.parameters) {
    return fallback;
  }
  
  // Use paramOrder from config for ordering, fallback to section-based filter
  const paramOrder = adminConfig.value.paramOrder?.[sectionKey];
  let orderedParams;
  
  if (paramOrder && paramOrder.length > 0) {
    // Filter paramOrder to only visible params
    orderedParams = paramOrder.filter(key => {
      const param = adminConfig.value.parameters[key];
      return param && param.visible && param.showInPanel !== false;
    });
  } else {
    // Fallback: filter params by section
    orderedParams = Object.entries(adminConfig.value.parameters)
      .filter(([, p]) => p.section === sectionKey && p.visible && p.showInPanel !== false)
      .map(([key]) => key);
  }

  // Add fallback params from defaults when missing in config.
  const allConfigKeys = new Set(Object.keys(adminConfig.value.parameters));
  for (const key of fallback) {
    if (!allConfigKeys.has(key) && !orderedParams.includes(key)) {
      const cfg = defaultParamConfigs[key];
      if (cfg && cfg.section === sectionKey && cfg.visible && cfg.showInPanel !== false) {
        orderedParams.push(key);
      }
    }
  }

  return orderedParams;
}

// Params grouped by section - derived from designDefs.js
const fallbackParamsBySection = PARAMS_BY_SECTION;

function updateResponsiveValue(paramKey, mode, values) {
  if (!state.design.responsiveValues) state.design.responsiveValues = {};
  if (!state.design.responsiveValues[paramKey]) state.design.responsiveValues[paramKey] = {};
  state.design.responsiveValues[paramKey][mode] = values;
  updateDesignSetting('responsiveValues', { ...state.design.responsiveValues });
  queueAutoSave();
}

function updateResponsiveMode(paramKey, mode) {
  if (isTemplateDesignEditMode.value) {
    return;
  }
  if (!state.adminDesignConfig) return;
  if (!state.adminDesignConfig.parameters) state.adminDesignConfig.parameters = {};
  const existing = state.adminDesignConfig.parameters[paramKey]
    || defaultParamConfigs[paramKey]
    || { visible: true, favorite: false, type: getParamConfig(paramKey).type || 'slider', label: paramKey };
  const param = { ...existing };
  if (mode) {
    param.responsive = mode;
  } else {
    delete param.responsive;
  }
  state.adminDesignConfig.parameters[paramKey] = param;
  adminConfigDirty.value = true;
  
  // Update currentMode in responsiveValues to track which mode is active
  if (!state.design.responsiveValues) state.design.responsiveValues = {};
  if (!state.design.responsiveValues[paramKey]) state.design.responsiveValues[paramKey] = {};
  state.design.responsiveValues[paramKey].currentMode = mode || null;
  updateDesignSetting('responsiveValues', { ...state.design.responsiveValues });
  queueAutoSave();
}

function updateDesign(key, value) {
  const paramConfig = adminConfig.value?.parameters?.[key];
  const isCustomBaseColor = paramConfig?.type === 'color' && paramConfig?.isBase && !(key in DEFAULT_DESIGN);
  if (isCustomBaseColor) {
    if (isTemplateDesignEditMode.value) {
      updateDesignSetting(key, value);
      queueAutoSave();
      return;
    }
    state.design[key] = value;
    state.designDirty = true;
    if (paramConfig.default !== value) {
      paramConfig.default = value;
      adminConfigDirty.value = true;
    }
  } else {
    updateDesignSetting(key, value);
  }
  // When a base color changes, re-apply all linked colors that reference it
  const links = state.adminDesignConfig?.colorLinks;
  if (links) {
    const isBaseColor = adminConfig.value?.parameters?.[key]?.type === 'color' && adminConfig.value?.parameters?.[key]?.isBase;
    if (isBaseColor) {
      for (const [colorKey, baseKey] of Object.entries(links)) {
        if (baseKey === key) {
          const resolved = getLinkedBaseColorValue(baseKey);
          if (resolved !== null) updateDesignSetting(colorKey, resolved);
        }
      }
    }
  }
  queueAutoSave();
}

function updateDesignColorVariation(paramKey, variation) {
  const normalized = normalizeColorVariation(variation);
  const adminDefaults = (state.adminDesignConfig?.colorVariations && typeof state.adminDesignConfig.colorVariations === "object")
    ? state.adminDesignConfig.colorVariations
    : {};
  const defaultVariation = normalizeColorVariation(
    adminDefaults?.[paramKey] ?? DEFAULT_COLOR_VARIATION
  );
  const next = {
    ...((state.design?.colorVariations && typeof state.design.colorVariations === "object")
      ? state.design.colorVariations
      : {}),
  };
  if (normalized === defaultVariation) {
    delete next[paramKey];
  } else {
    next[paramKey] = normalized;
  }
  updateDesignSetting("colorVariations", next);
  queueAutoSave();
}

function getDesignParamDefaultValue(paramKey) {
  const configuredDefault = adminConfig.value?.parameters?.[paramKey]?.default;
  if (configuredDefault !== undefined) return configuredDefault;
  if (Object.prototype.hasOwnProperty.call(DEFAULT_DESIGN, paramKey)) {
    return DEFAULT_DESIGN[paramKey];
  }
  return null;
}

function updateColorLink(colorKey, baseColorKey, resetOnUnlink = true) {
  if (isTemplateDesignEditMode.value) {
    return;
  }
  if (!state.adminDesignConfig) return;
  if (!state.adminDesignConfig.colorLinks) state.adminDesignConfig.colorLinks = {};

  if (!baseColorKey) {
    delete state.adminDesignConfig.colorLinks[colorKey];
    adminConfigDirty.value = true;
    if (resetOnUnlink) {
      updateDesignSetting(colorKey, getDesignParamDefaultValue(colorKey));
    }
    queueAutoSave();
    return;
  }

  state.adminDesignConfig.colorLinks[colorKey] = baseColorKey;
  adminConfigDirty.value = true;

  if (baseColorKey === 'transparent') {
    updateDesignSetting(colorKey, 'transparent');
  } else if (baseColorKey === 'highContrast') {
    updateDesignSetting(colorKey, '__high_contrast__');
  } else {
    const resolved = getLinkedBaseColorValue(baseColorKey);
    if (resolved !== null) updateDesignSetting(colorKey, resolved);
  }
  queueAutoSave();
}

function reapplyColorLinks() {
  const links = state.adminDesignConfig?.colorLinks;
  if (!links) return;
  for (const [colorKey, baseKey] of Object.entries(links)) {
    if (baseKey === 'transparent') {
      if (state.design[colorKey] !== 'transparent') updateDesignSetting(colorKey, 'transparent');
    } else if (baseKey === 'highContrast') {
      if (state.design[colorKey] !== '__high_contrast__') updateDesignSetting(colorKey, '__high_contrast__');
    } else {
      const resolved = getLinkedBaseColorValue(baseKey);
      if (resolved !== null && state.design[colorKey] !== resolved) {
        updateDesignSetting(colorKey, resolved);
      }
    }
  }
}

// -------------------------
// CSS Media Tabs
// -------------------------

const activeCssMediaTab = ref('desktop');

function responsiveCssMediaTitle(device) {
  return getResponsiveDeviceLabel(device, state.adminDesignConfig?.responsive);
}

const cssMediaTabHint = computed(() => {
  switch (activeCssMediaTab.value) {
    case 'desktop': return 'CSS applies globally (no media query wrapper)';
    case 'tablet': return `CSS wrapped in @media ${buildResponsiveMediaQuery('tablet', state.adminDesignConfig?.responsive)}`;
    case 'mobile': return `CSS wrapped in @media ${buildResponsiveMediaQuery('mobile', state.adminDesignConfig?.responsive)}`;
    default: return '';
  }
});

const currentCssTabValue = computed(() => {
  switch (activeCssMediaTab.value) {
    case 'desktop': return state.design.globalCustomCss;
    case 'tablet': return state.design.globalCustomCssTablet;
    case 'mobile': return state.design.globalCustomCssMobile;
    default: return '';
  }
});

// -------------------------
// CSS Snippets
// -------------------------

const cssSnippets = ref([]);
const snippetsLoading = ref(false);

function normalizeCssSnippet(snippet) {
  return {
    ...snippet,
    active: snippet?.active !== false,
  };
}

async function loadSnippets() {
  snippetsLoading.value = true;
  try {
    const res = await api.listCssSnippets();
    cssSnippets.value = (res.snippets || []).map(normalizeCssSnippet);
    applyCssSnippets();
  } catch {
    cssSnippets.value = [];
    applyCssSnippets();
  }
  finally { snippetsLoading.value = false; }
}

async function saveAsSnippet() {
  const tab = activeCssMediaTab.value;
  const cssKey = tab === 'desktop' ? 'globalCustomCss' : tab === 'tablet' ? 'globalCustomCssTablet' : 'globalCustomCssMobile';
  const css = state.design[cssKey];
  if (!css) return;
  const scopeLabel = tab === 'desktop' ? '' : ` (${tab})`;
  const label = prompt('Snippet name:', `Snippet${scopeLabel} ${formatInstantInServerTimezone(new Date().toISOString())}`);
  if (label === null) return;
  try {
    const payload = { label: label || undefined, css, active: true };
    if (tab !== 'desktop') payload.media_scope = tab;
    const snippet = await api.createCssSnippet(payload);
    cssSnippets.value.unshift(normalizeCssSnippet(snippet));
    updateDesignSetting(cssKey, '');
    applyCssSnippets();
  } catch (err) { console.error('Failed to save snippet:', err); }
}

async function toggleSnippet(s) {
  try {
    const updated = await api.updateCssSnippet(s.id, { active: !s.active });
    const idx = cssSnippets.value.findIndex(x => x.id === s.id);
    if (idx >= 0) cssSnippets.value[idx] = normalizeCssSnippet(updated);
    applyCssSnippets();
  } catch (err) { console.error('Failed to toggle snippet:', err); }
}

async function deleteSnippet(s) {
  if (!confirm(`Delete snippet "${s.label}"?`)) return;
  try {
    await api.deleteCssSnippet(s.id);
    cssSnippets.value = cssSnippets.value.filter(x => x.id !== s.id);
    applyCssSnippets();
  } catch (err) { console.error('Failed to delete snippet:', err); }
}

function applyCssSnippets() {
  let el = document.getElementById('css-snippets-style');
  const combined = buildCssSnippetsStyleText(cssSnippets.value, {
    simulatedViewport: state.simulatedViewport,
    responsiveConfig: state.adminDesignConfig?.responsive,
  });
  if (combined) {
    if (!el) {
      el = document.createElement('style');
      el.id = 'css-snippets-style';
      document.head.appendChild(el);
    }
    el.textContent = combined;
  } else if (el) {
    el.textContent = '';
  }
}

function formatDate(iso) {
  return formatInstantInServerTimezone(iso, { dateStyle: 'medium' });
}

// -------------------------
// Design Versions
// -------------------------

const designVersions = ref([]);
const versionsLoading = ref(false);
const savingVersion = ref(false);
const newVersionTitle = ref('');
const newVersionDescription = ref('');
const newVersionRating = ref(0);
const editingVersionId = ref(null);
const publishingVersionId = ref(null);
const editVersionData = reactive({ title: '', description: '', rating: 0 });
const baselineVersionId = ref(null);
const baselineVersionTitle = ref('');
const baselinePayload = ref(null);
const baselineCarryChangedKeys = ref([]);
const sessionAnchorPayload = ref(null);

const VERSION_COMPARE_EXCLUDED_KEYS = new Set(["id", "_id", "key", "created_at", "updated_at", "revision_id", "comparison_version_id"]);
const VERSION_LARGE_CHANGE_THRESHOLD = 5;

function byNewestCreatedAt(a, b) {
  return (parseRevisionTimestamp(b?.created_at)?.getTime() || 0) - (parseRevisionTimestamp(a?.created_at)?.getTime() || 0);
}

const sortedDesignVersions = computed(() =>
  designVersions.value
    .slice()
    .sort(byNewestCreatedAt)
);

function isVersionPublished(version) {
  return Boolean(version?.is_published);
}

function clonePayload(value) {
  if (value == null) return value;
  return JSON.parse(JSON.stringify(value));
}

function normalizeComparableObject(source) {
  const raw = source && typeof source === "object" ? clonePayload(source) : {};
  const obj = raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
  for (const key of VERSION_COMPARE_EXCLUDED_KEYS) {
    delete obj[key];
  }
  return obj;
}

function normalizeVersionPayload(designData) {
  return {
    design_settings: normalizeComparableObject(designData),
  };
}

function computeTopLevelChangedKeys(basePayload, currentPayload) {
  const changed = [];
  const scopes = [
    ["design_settings", "design_settings"],
  ];

  for (const [payloadKey, label] of scopes) {
    const baseObj = basePayload?.[payloadKey] && typeof basePayload[payloadKey] === "object" ? basePayload[payloadKey] : {};
    const currentObj = currentPayload?.[payloadKey] && typeof currentPayload[payloadKey] === "object" ? currentPayload[payloadKey] : {};
    const keys = Array.from(new Set([...Object.keys(baseObj), ...Object.keys(currentObj)])).sort();
    for (const key of keys) {
      if (VERSION_COMPARE_EXCLUDED_KEYS.has(key)) continue;
      if (stableStringify(baseObj[key]) !== stableStringify(currentObj[key])) {
        changed.push(`${label}.${key}`);
      }
    }
  }
  return changed;
}

function setSessionAnchorPayloadFromCurrent() {
  if (sessionAnchorPayload.value) return;
  const { designData } = _getCurrentDesignPayload();
  sessionAnchorPayload.value = normalizeVersionPayload(designData);
}

function setBaselineVersion(version) {
  const { designData } = _getCurrentDesignPayload();
  baselineVersionId.value = version?.id || null;
  baselineVersionTitle.value = version?.title || "";
  baselinePayload.value = normalizeVersionPayload(designData);
  baselineCarryChangedKeys.value = [];
  setSessionAnchorPayloadFromCurrent();
}

function setBaselineVersionSnapshot(version, designSettings) {
  if (!version?.id || !designSettings || typeof designSettings !== "object") return false;
  baselineVersionId.value = version.id;
  baselineVersionTitle.value = version.title || "";
  baselinePayload.value = normalizeVersionPayload(designSettings);
  baselineCarryChangedKeys.value = [];
  setSessionAnchorPayloadFromCurrent();
  return true;
}

const activeComparisonPayload = computed(() =>
  baselinePayload.value || sessionAnchorPayload.value
);

const versionChangeInfo = computed(() => {
  const base = activeComparisonPayload.value;
  if (!base) return { changedKeys: [], changeCount: 0 };
  const { designData } = _getCurrentDesignPayload();
  const current = normalizeVersionPayload(designData);
  const computedKeys = computeTopLevelChangedKeys(base, current);
  const carryKeys = Array.isArray(baselineCarryChangedKeys.value) ? baselineCarryChangedKeys.value : [];
  const changedKeys = Array.from(new Set([...carryKeys, ...computedKeys]));
  return {
    changedKeys,
    changeCount: changedKeys.length,
  };
});

const saveInputsDisabled = computed(() =>
  Boolean(baselineVersionId.value) && versionChangeInfo.value.changeCount === 0
);

const canSaveCurrentVersion = computed(() =>
  !savingVersion.value && versionChangeInfo.value.changeCount > 0
);

const currentBaselineVersion = computed(() =>
  designVersions.value.find((version) => version.id === baselineVersionId.value) || null
);

const canUpdateCurrentVersion = computed(() =>
  !savingVersion.value && Boolean(currentBaselineVersion.value) && versionChangeInfo.value.changeCount > 0
);

const versionChangeAdvisory = computed(() => {
  if (!baselineVersionId.value) return "";
  const count = versionChangeInfo.value.changeCount;
  if (count <= VERSION_LARGE_CHANGE_THRESHOLD) return "";
  return `Current changes affect ${count} top-level design groups. A separate version may fit better than updating this baseline.`;
});

function isVersionCurrent(version) {
  return Boolean(version?.id && baselineVersionId.value && version.id === baselineVersionId.value);
}

function isVersionCurrentClean(version) {
  return isVersionCurrent(version) && versionChangeInfo.value.changeCount === 0;
}

function isVersionCurrentDirty(version) {
  return isVersionCurrent(version) && versionChangeInfo.value.changeCount > 0;
}

function titleCaseToken(value) {
  const raw = String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim();
  if (!raw) return "Unknown";
  return raw
    .split(" ")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatRoutePath(section, subsection, parameter) {
  return `${section} / ${subsection} / ${parameter}`;
}

function normalizeRoutePath(path) {
  return String(path || "")
    .split("/")
    .map((part) => part.trim())
    .filter(Boolean)
    .join(" / ");
}

function resolveChangelogParamConfig(rawKey) {
  const key = String(rawKey || "").trim();
  if (!key) return { resolvedKey: "", config: null };

  const candidates = [];
  const addCandidate = (candidate) => {
    const normalized = String(candidate || "").trim();
    if (!normalized || candidates.includes(normalized)) return;
    candidates.push(normalized);
  };

  addCandidate(key);
  addCandidate(key.replace(/_([a-zA-Z0-9])/g, (_, part) => part.toUpperCase()));
  addCandidate(toCamelCaseParamKey(key));

  for (const candidate of candidates) {
    if (adminConfig.value?.parameters?.[candidate] || defaultParamConfigs[candidate]) {
      return { resolvedKey: candidate, config: getParamConfig(candidate) };
    }
  }

  return { resolvedKey: candidates[0] || key, config: null };
}

function resolveDesignSettingRoute(paramKey) {
  if (!paramKey) return formatRoutePath("Design", "General", "Unknown");
  if (paramKey === "buttonTypeStyles") {
    return formatRoutePath("Buttons", "Button Types", "Style Overrides");
  }

  const btnTypeMatch = paramKey.match(/^btnType_([^_]+)_(.+)$/);
  if (btnTypeMatch) {
    const [, typeId, nestedKey] = btnTypeMatch;
    const typeLabel = buttonTypeInstances.value.find((entry) => entry.id === typeId)?.label || titleCaseToken(typeId);
    const nestedLabel = buttonParamConfigs[nestedKey]?.label || titleCaseToken(nestedKey);
    return formatRoutePath("Buttons", typeLabel, nestedLabel);
  }

  const { resolvedKey, config } = resolveChangelogParamConfig(paramKey);
  const cfg = config;
  const sectionLabel = sectionLabels[cfg?.section] || titleCaseToken(cfg?.section || "design");
  const subsectionLabel = cfg?.subsection || "General";
  const paramLabel = cfg?.label || titleCaseToken(resolvedKey || paramKey);
  return formatRoutePath(sectionLabel, subsectionLabel, paramLabel);
}

const adminConfigRouteLabels = {
  parameters: formatRoutePath("Design Config", "General", "Parameters"),
  paramOrder: formatRoutePath("Design Config", "General", "Parameter Order"),
  sectionOrder: formatRoutePath("Design Config", "General", "Sections"),
  hiddenSections: formatRoutePath("Design Config", "General", "Hidden Sections"),
  sectionOverrideParams: formatRoutePath("Design Config", "General", "Override Parameters"),
  buttonTypes: formatRoutePath("Design Config", "Buttons", "Button Type Definitions"),
  colorLinks: formatRoutePath("Design Config", "Colors", "Color Link Mapping"),
  fontFamilies: formatRoutePath("Design Config", "Fonts", "Font Families"),
  fontWeights: formatRoutePath("Design Config", "Fonts", "Font Weights"),
};

function resolveAdminConfigRoute(adminKey) {
  if (!adminKey) return formatRoutePath("Design Config", "General", "Settings");
  return adminConfigRouteLabels[adminKey] || formatRoutePath("Design Config", "General", titleCaseToken(adminKey));
}

function resolveChangelogRoute(rawKey) {
  const value = String(rawKey || "").trim();
  if (!value) return "Unknown";
  if (value.includes("/") && !value.startsWith("design_settings.") && !value.startsWith("admin_config.")) {
    return normalizeRoutePath(value);
  }
  if (!value.includes(".")) {
    if (value.includes(" ")) return value;
    return resolveDesignSettingRoute(value);
  }

  const [scope, ...tailParts] = value.split(".");
  const tail = tailParts.join(".");
  if (scope === "design_settings") {
    return resolveDesignSettingRoute(tail);
  }
  if (scope === "admin_config") {
    return resolveAdminConfigRoute(tail);
  }
  return titleCaseToken(value);
}

function getVersionChangelogDisplayKeys(version) {
  const keys = Array.isArray(version?.changelog?.changed_keys) ? version.changelog.changed_keys : [];
  return Array.from(new Set(keys.map(resolveChangelogRoute).filter(Boolean)));
}

function hasVersionChangelog(version) {
  const changed = getVersionChangelogDisplayKeys(version);
  return changed.length > 0 || Boolean(version?.changelog?.base_version_title);
}

function versionChangelogBase(version) {
  return version?.changelog?.base_version_title || "Unknown";
}

function versionChangelogItems(version) {
  const keys = getVersionChangelogDisplayKeys(version);
  if (!keys.length) return ["No parameter-level changes"];
  const limit = 6;
  if (keys.length <= limit) return keys;
  return [...keys.slice(0, limit), `…and ${keys.length - limit} more`];
}

function buildCurrentChangelog(baseVersion = null) {
  const changedKeys = versionChangeInfo.value.changedKeys;
  if (!changedKeys.length) return null;

  const baseId = baselineVersionId.value || baseVersion?.id || null;
  const baseTitle = baselineVersionTitle.value || baseVersion?.title || null;
  const changedRoutes = Array.from(new Set(changedKeys.map(resolveChangelogRoute).filter(Boolean)));
  return {
    base_version_id: baseId || undefined,
    base_version_title: baseTitle || undefined,
    changed_keys: changedRoutes,
    change_count: changedKeys.length,
  };
}

async function loadVersions() {
  versionsLoading.value = true;
  try {
    const res = await api.listDesignVersions();
    designVersions.value = res.versions || [];
    setSessionAnchorPayloadFromCurrent();
    const baseline = res.comparison_baseline;
    if (baseline?.id && baseline?.design_settings && typeof baseline.design_settings === "object") {
      const baselineVersion = designVersions.value.find((version) => version.id === baseline.id) || {
        id: baseline.id,
        title: baseline.title || "",
      };
      setBaselineVersionSnapshot(baselineVersion, baseline.design_settings);
    }
    if (baselineVersionId.value && !designVersions.value.some((version) => version.id === baselineVersionId.value)) {
      baselineVersionId.value = null;
      baselineVersionTitle.value = "";
      baselinePayload.value = null;
      baselineCarryChangedKeys.value = [];
    }
  } catch { designVersions.value = []; }
  finally { versionsLoading.value = false; }
}

function _getCurrentDesignPayload() {
  const designData = mapDesignToBackendFull(state.design);
  return { designData };
}

async function saveVersion() {
  if (!canSaveCurrentVersion.value) return;
  savingVersion.value = true;
  try {
    const { designData } = _getCurrentDesignPayload();
    const changelog = buildCurrentChangelog();
    const version = await api.createDesignVersion({
      title: newVersionTitle.value || undefined,
      description: newVersionDescription.value || undefined,
      rating: newVersionRating.value,
      design_settings: designData,
      changelog: changelog || undefined,
    });
    if (version.is_published) {
      designVersions.value = designVersions.value.map((entry) => ({ ...entry, is_published: false }));
    }
    designVersions.value.unshift(version);
    setBaselineVersion(version);
    newVersionTitle.value = '';
    newVersionDescription.value = '';
    newVersionRating.value = 0;
  } catch (err) { console.error('Failed to save version:', err); }
  finally { savingVersion.value = false; }
}

async function updateCurrentVersion() {
  if (!canUpdateCurrentVersion.value) return;
  const currentVersion = currentBaselineVersion.value;
  if (!currentVersion?.id) return;
  const msg = isVersionPublished(currentVersion)
    ? `Update published version "${currentVersion.title}"?\n\nThis can change the live public design immediately because this version is currently published.`
    : `Update current version "${currentVersion.title}" with the current design changes?`;
  if (!confirm(msg)) return;
  savingVersion.value = true;
  try {
    const { designData } = _getCurrentDesignPayload();
    const changelog = buildCurrentChangelog(currentVersion);
    const payload = {
      design_settings: designData,
      update_mode: 'current_version',
      changelog: changelog || undefined,
    };
    if (newVersionTitle.value.trim()) {
      payload.title = newVersionTitle.value.trim();
    }
    if (newVersionDescription.value.trim()) {
      payload.description = newVersionDescription.value.trim();
    }
    if (newVersionRating.value > 0) {
      payload.rating = newVersionRating.value;
    }
    const updated = await api.updateDesignVersion(currentVersion.id, payload);
    const idx = designVersions.value.findIndex(v => v.id === currentVersion.id);
    if (idx >= 0) {
      designVersions.value[idx] = { ...designVersions.value[idx], ...updated };
    }
    setBaselineVersion(updated);
    newVersionTitle.value = '';
    newVersionDescription.value = '';
    newVersionRating.value = 0;
  } catch (err) { console.error('Failed to update current version:', err); }
  finally { savingVersion.value = false; }
}

function startEditVersion(v) {
  editingVersionId.value = v.id;
  editVersionData.title = v.title || '';
  editVersionData.description = v.description || '';
  editVersionData.rating = v.rating || 0;
}

async function commitEditVersion() {
  const id = editingVersionId.value;
  if (!id) return;
  try {
    const updated = await api.updateDesignVersion(id, {
      title: editVersionData.title,
      description: editVersionData.description,
      rating: editVersionData.rating,
    });
    const idx = designVersions.value.findIndex(v => v.id === id);
    if (idx >= 0) {
      designVersions.value[idx] = { ...designVersions.value[idx], ...updated };
    }
    editingVersionId.value = null;
  } catch (err) { console.error('Failed to update version:', err); }
}

async function applyVersion(v) {
  if (!confirm(`Load version "${v.title}"? This will replace the current design settings.`)) return;
  try {
    await api.loadDesignVersion(v.id);
    await loadDesignSettings();
    await loadAdminDesignConfig();
    setBaselineVersion(v);
  } catch (err) { console.error('Failed to load version:', err); }
}

async function publishVersion(v) {
  if (!v?.id || isVersionPublished(v)) return;
  const msg = `Publish version "${v.title}"?\n\nThis will make this version live for all public visitors and unpublish every other version.`;
  if (!confirm(msg)) return;
  publishingVersionId.value = v.id;
  try {
    await api.publishDesignVersion(v.id);
    await loadVersions();
  } catch (err) {
    console.error('Failed to publish version:', err);
  } finally {
    publishingVersionId.value = null;
  }
}

async function removeVersion(v) {
  if (isVersionPublished(v)) return;
  const msg = `Delete version "${v.title}"?`;
  if (!confirm(msg)) return;
  try {
    await api.deleteDesignVersion(v.id);
    await loadVersions();
    if (baselineVersionId.value === v.id) {
      baselineVersionId.value = null;
      baselineVersionTitle.value = "";
      baselinePayload.value = null;
      baselineCarryChangedKeys.value = [];
    }
  } catch (err) { console.error('Failed to delete version:', err); }
}

// Load snippets & versions when panel opens
watch(open, (isOpen) => {
  if (isOpen && cssSnippets.value.length === 0) loadSnippets();
  if (isOpen && !isTemplateDesignEditMode.value && designVersions.value.length === 0) loadVersions();
  if (isOpen && isTemplateDesignEditMode.value) loadGlobalTemplateDesignSnapshot();
});

watch(
  () => [isTemplateDesignEditMode.value, state.pageTemplateStyleRef, state.templatePageDesignMeta?.path],
  ([enabled]) => {
    globalTemplateDesign.value = null;
    if (open.value && enabled) loadGlobalTemplateDesignSnapshot();
  }
);

// Re-apply CSS snippets when simulated viewport changes
watch(() => state.simulatedViewport, () => {
  if (cssSnippets.value.length > 0) applyCssSnippets();
});

watch(() => state.adminDesignConfig?.responsive, () => {
  if (cssSnippets.value.length > 0) applyCssSnippets();
}, { deep: true });

watch(cssSnippets, () => {
  applyCssSnippets();
}, { deep: true });

watch(activePanelTab, (tab) => {
  if (!showOverrideTab.value && tab === 'override') {
    activePanelTab.value = 'global';
    return;
  }
  if (tab !== 'override') return;
  if (state.activeSectionDesignKey) return;
  const first = overrideTargets.value[0];
  if (first) openOverrideTarget(first.key);
});

watch(showOverrideTab, (enabled) => {
  if (!enabled && activePanelTab.value === 'override') {
    activePanelTab.value = 'global';
  }
});

watch(overrideTargets, (targets) => {
  const available = new Set(targets.map((target) => target.key));

  if (state.activeSectionDesignKey && !available.has(state.activeSectionDesignKey)) {
    state.activeSectionDesignKey = null;
  }

  for (const key of Object.keys(expandedOverrideTargets)) {
    if (!available.has(key)) {
      delete expandedOverrideTargets[key];
    }
  }

  if (open.value && activePanelTab.value === 'override' && !state.activeSectionDesignKey) {
    const first = targets[0];
    if (first) openOverrideTarget(first.key);
  }
});

function handleOpenOverrideEvent(event) {
  if (!showOverrideTab.value) return;
  const sectionKey = event?.detail?.sectionKey;
  if (!sectionKey) return;
  openOverrideTarget(sectionKey, { scroll: true });
}

function handleOpenCustomCssEvent() {
  open.value = true;
  activePanelTab.value = 'global';
  for (const key of Object.keys(expandedSections)) {
    expandedSections[key] = false;
  }
  expandedSections.customCss = true;
}

function handleSnippetChangedEvent() {
  loadSnippets();
}

onMounted(() => {
  window.addEventListener('fstvlpress:open-design-override', handleOpenOverrideEvent);
  window.addEventListener('fstvlpress:open-design-custom-css', handleOpenCustomCssEvent);
  window.addEventListener('fstvlpress:css-snippet-created', handleSnippetChangedEvent);
  window.addEventListener('fstvlpress:css-snippet-changed', handleSnippetChangedEvent);
});

async function handleUndo() { await undoDesignChange(); }
async function handleRedo() { await redoDesignChange(); }

async function loadGlobalTemplateDesignSnapshot() {
  if (!isTemplateDesignEditMode.value || loadingGlobalTemplateDesignSnapshot.value) return;
  loadingGlobalTemplateDesignSnapshot.value = true;
  try {
    const result = await api.getDesignSettings();
    globalTemplateDesign.value = mapBackendToFrontendDesign(result || {});
  } catch (err) {
    console.error("Failed to load global design comparison:", err);
    globalTemplateDesign.value = null;
  } finally {
    loadingGlobalTemplateDesignSnapshot.value = false;
  }
}

async function loadGlobalTemplateDesign() {
  if (!isTemplateDesignEditMode.value || loadingGlobalTemplateDesign.value) return;
  const templatePath = activeTemplateDesignPath();
  if (!templatePath) return;
  const confirmed = window.confirm(
    `Replace this template design draft with the current global design? You can review and publish it afterward.`
  );
  if (!confirmed) return;

  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer);
    autoSaveTimer = null;
  }
  loadingGlobalTemplateDesign.value = true;
  clearAutoSaveToastState();
  try {
    await loadGlobalDesignIntoTemplateDraft();
    if (!globalTemplateDesign.value) {
      await loadGlobalTemplateDesignSnapshot();
    }
    clearAutoSaveToastState();
  } catch (err) {
    console.error("Failed to load global design into template draft:", err);
    showAutoSaveError(err?.message || "Failed to load global design");
  } finally {
    loadingGlobalTemplateDesign.value = false;
  }
}

async function publishTemplateDesign() {
  if (!isTemplateDesignEditMode.value || publishingTemplateDesign.value || autoSaving.value) return;
  const templatePath = activeTemplateDesignPath();
  if (!templatePath) return;
  if (!templateDesignHasPublishChanges.value) return;
  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer);
    autoSaveTimer = null;
  }
  publishingTemplateDesign.value = true;
  try {
    if (state.designDirty) {
      await saveDesignSettings();
    }
    const result = await api.publishPageTemplateDesign(templatePath);
    const updatedAtFromResult = result?.updated_at ?? null;
    const publishedAtFromResult = result?.published_at ?? null;
    const publishedPayload = (
      result?.published && typeof result.published === "object"
        ? result.published
        : result?.current && typeof result.current === "object"
          ? result.current
          : {}
    );
    state.templatePageDesignMeta = {
      path: String(result?.path || templatePath || ""),
      updatedAt: updatedAtFromResult || state.templatePageDesignMeta?.updatedAt || null,
      publishedAt: publishedAtFromResult || null,
      initializedFromGlobalVersionId:
        state.templatePageDesignMeta?.initializedFromGlobalVersionId || null,
    };
    state.templatePagePublishedDesign = mapBackendToFrontendDesign(publishedPayload);
    state.designRevisionStatus = {
      enabled: true,
      canUndo: false,
      canRedo: false,
      lastSavedBy: "template published",
      lastSavedAt: publishedAtFromResult || null,
    };
    state._designSnapshot = JSON.stringify(state.design || {});
    state.designDirty = false;
  } catch (err) {
    console.error("Failed to publish template design:", err);
    showAutoSaveError(err?.message || "Failed to publish template design");
  } finally {
    publishingTemplateDesign.value = false;
  }
}

watch(
  () => [state.designRevisionStatus?.lastSavedAt, state.designRevisionStatus?.lastSavedBy],
  ([savedAt, savedBy]) => {
    lastKnownDesignRevision.at = savedAt || null;
    lastKnownDesignRevision.by = savedBy || null;
  },
  { immediate: true }
);

function buildConfigPatch() {
  const configPatch = {};
  if (state.adminDesignConfig?.colorLinks) configPatch.colorLinks = state.adminDesignConfig.colorLinks;
  if (state.adminDesignConfig?.parameters) configPatch.parameters = state.adminDesignConfig.parameters;
  return configPatch;
}

function sortObjectDeep(value) {
  if (Array.isArray(value)) return value.map(sortObjectDeep);
  if (!value || typeof value !== "object") return value;
  const sorted = {};
  for (const key of Object.keys(value).sort()) {
    sorted[key] = sortObjectDeep(value[key]);
  }
  return sorted;
}

function stableStringify(value) {
  return JSON.stringify(sortObjectDeep(value ?? null));
}

async function hasConcurrentDesignUpdate() {
  if (isTemplateDesignEditMode.value) return null;
  if (!state.designDirty) return null;
  const status = await api.getDesignRevisionStatus();
  const remoteAt = status?.last_saved_at || null;
  const remoteBy = status?.last_saved_by || null;
  const localAt = lastKnownDesignRevision.at;
  if (!remoteAt || !localAt) return null;

  const remoteTs = getRevisionTimestampMs(remoteAt);
  const localTs = getRevisionTimestampMs(localAt);
  if (!Number.isFinite(remoteTs) || !Number.isFinite(localTs)) return null;
  if (remoteTs <= localTs) return null;
  if (remoteBy && remoteBy === lastKnownDesignRevision.by) return null;

  return {
    by: remoteBy || 'another user',
    at: formatRevisionTimestampBerlin(remoteAt) || String(remoteAt),
  };
}

function queueAutoSave() {
  if (autoSaving.value) return;
  if (!state.designDirty && !adminConfigDirty.value && !hasDirtyOverrides()) return;
  if (autoSaveTimer) clearTimeout(autoSaveTimer);
  if (autoSaveSaved.value) clearAutoSaveToastState();
  autoSaveTimer = setTimeout(() => {
    runAutoSave();
  }, 700);
}

async function runAutoSave() {
  if (autoSaving.value) return;
  if (!state.designDirty && !adminConfigDirty.value && !hasDirtyOverrides()) return;

  autoSaving.value = true;
  clearAutoSaveToastState();
  let completedWithoutError = false;
  try {
    const conflict = await hasConcurrentDesignUpdate();
    if (conflict) {
      showAutoSaveError(
        `Auto-save paused: ${conflict.by} saved newer design settings at ${conflict.at}.`,
        { conflict: true }
      );
      return;
    }

    if (state.designDirty) {
      await saveDesignSettings();
    }

    const overrideKeys = Object.keys(dirtyOverrideKeys);
    for (const key of overrideKeys) {
      await saveSectionDesignOverrides(key);
      delete dirtyOverrideKeys[key];
    }

    if (adminConfigDirty.value && !isTemplateDesignEditMode.value) {
      const configPatch = buildConfigPatch();
      if (Object.keys(configPatch).length) {
        await api.updateAdminDesignConfig(configPatch);
      }
      adminConfigDirty.value = false;
    } else if (adminConfigDirty.value && isTemplateDesignEditMode.value) {
      adminConfigDirty.value = false;
    }
    clearAutoSaveToastState();
    completedWithoutError = true;
  } catch (err) {
    showAutoSaveError(err?.message || "Auto-save failed");
    console.error("Auto-save failed:", err);
  } finally {
    autoSaving.value = false;
    if (completedWithoutError && (state.designDirty || adminConfigDirty.value || hasDirtyOverrides())) {
      queueAutoSave();
    } else if (completedWithoutError) {
      showAutoSaveSaved();
    }
  }
}

onBeforeUnmount(() => {
  window.removeEventListener('fstvlpress:open-design-override', handleOpenOverrideEvent);
  window.removeEventListener('fstvlpress:open-design-custom-css', handleOpenCustomCssEvent);
  window.removeEventListener('fstvlpress:css-snippet-created', handleSnippetChangedEvent);
  window.removeEventListener('fstvlpress:css-snippet-changed', handleSnippetChangedEvent);
  if (autoSaveTimer) clearTimeout(autoSaveTimer);
  clearAutoSaveStatusTimer();
});
</script>

<style scoped>
.wrap {
  position: fixed;
  z-index: 80;
  max-height: 85vh;
}
.panel {
  display: flex;
  flex-direction: column;
  max-height: 85vh;
  overflow: hidden;
}
.wrap.corner-bottom-right {
  right: 5px;
  bottom: 5px;
}
.wrap.corner-bottom-left {
  left: 5px;
  bottom: 5px;
}
.wrap.corner-top-right {
  right: 5px;
  top: 5px;
}
.wrap.corner-top-left {
  left: 5px;
  top: 5px;
}
.wrap.preview-mode:not(.open).corner-bottom-right,
.wrap.preview-mode:not(.open).corner-bottom-left {
  bottom: 50px;
}
.wrap.open { z-index: 300; }
.wrap:not(.open) .body { display: none; }

.wrap.open .panel {
  width: min(360px, calc(100vw - 28px));
  max-height: 85vh;
}

.head {
  display: flex;
  align-items: stretch;
  flex: 0 0 auto;
  padding: 12px;
  cursor: pointer;
  user-select: none;
}

.head-main {
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.head-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
}

.head-row-top {
  align-items: flex-start;
}

.head-top {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.title { font-weight: 900; }

.head-actions {
  display: flex;
  align-items: center;
  margin-left: auto;
  gap: 8px;
  flex-shrink: 0;
}

.design-tabs {
  display: flex;
  width: 100%;
  gap: 0;
  margin: 0;
}

.design-tab-btn {
  flex: 0 0 50%;
  max-width: 50%;
  border: 1px solid var(--border);
  border-radius: 0;
  background: #fff;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  padding: 8px 10px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.design-tab-btn:first-child {
  border-top-left-radius: 8px;
  border-bottom-left-radius: 8px;
  border-right: none;
}

.design-tab-btn:last-child {
  border-top-right-radius: 8px;
  border-bottom-right-radius: 8px;
}

.design-tab-btn:hover {
  background: var(--surface-2);
  color: var(--text);
}

.design-tab-btn.active {
  background: var(--accent, #4f46e5);
  border-color: var(--accent, #4f46e5);
  color: #fff;
}

.design-tabs.single-tab .design-tab-btn {
  flex: 1 1 auto;
  max-width: none;
  border-radius: 8px;
  border-right: 1px solid var(--border);
}

/* Bottom controls */
.bottom-controls {
  margin-top: 0;
  padding-top: 12px;
  border-top: 1px solid var(--border, #e2e8f0);
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}

.sim-vis-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 11px;
  user-select: none;
  white-space: nowrap;
}
.sim-vis-toggle input[type="checkbox"] {
  width: 14px;
  height: 14px;
  cursor: pointer;
  accent-color: var(--accent, #4f46e5);
}
.sim-vis-label {
  color: var(--muted, #64748b);
  font-weight: 500;
}

.chev { color: var(--muted); font-weight: 900; }

.body {
  flex: 0 1 auto;
  min-height: 0;
  padding: 0 12px 12px;
  max-height: 0;
  opacity: 0;
  transform: translateY(-4px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: max-height 220ms ease, opacity 180ms ease, transform 180ms ease;
}

.wrap.open .body {
  flex: 1 1 auto;
  max-height: 85vh;
  opacity: 1;
  transform: translateY(0);
}

.body-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.param-search-row {
  display: flex;
  gap: 8px;
  margin: 0;
}

.param-search-input {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 7px 10px;
  font-size: 12px;
  background: #fff;
  color: var(--text);
}

.param-search-input:focus {
  outline: none;
  border-color: var(--accent, #4f46e5);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent, #4f46e5) 16%, transparent);
}

.param-search-clear {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  color: var(--muted);
  font-size: 11px;
  font-weight: 600;
  padding: 0 10px;
  cursor: pointer;
}

.param-search-clear:hover {
  background: var(--surface-2);
  color: var(--text);
}

.head-undo-row {
  align-items: center;
}

.template-design-actions-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.template-design-action-btn {
  width: 100%;
  min-width: 0;
}

.head-author {
  flex: 1.2;
  min-width: 0;
  display: flex;
  justify-content: center;
}

.head-lock-row {
  font-size: 11px;
  line-height: 1.35;
  color: var(--muted);
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px 8px;
}

.undo-btn, .redo-btn {
  flex: 1;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.undo-btn:hover:not(:disabled), .redo-btn:hover:not(:disabled) { background: var(--surface-2); }
.undo-btn:disabled, .redo-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Collapsible sections */
.collapsible {
  border-radius: 10px;
  background: var(--surface-2);
  margin-bottom: 8px;
  overflow: hidden;
}

.collapsible.muted {
  opacity: 0.58;
}

.collapsible-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s ease;
}
.collapsible-header:hover { background: rgba(0, 0, 0, 0.03); }

.override-active-toggle {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
  cursor: pointer;
}

.override-active-toggle input[type="checkbox"] {
  width: 14px;
  height: 14px;
  cursor: pointer;
  accent-color: var(--accent, #4f46e5);
}

.collapsible-icon { font-size: 12px; color: var(--muted); width: 16px; }
.collapsible-title { font-weight: 700; font-size: 14px; }

.collapsible-content {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  transition: max-height 200ms ease, opacity 150ms ease;
}

.collapsible.expanded .collapsible-content {
  max-height: 5000px;
  opacity: 1;
  padding: 0 12px 12px;
  overflow: visible;
}

.override-target-footer {
  padding: 8px 12px 12px;
}

.override-clear-target-btn {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.override-clear-target-btn:hover:not(:disabled) {
  background: #fee2e2;
  border-color: #fecaca;
  color: #b91c1c;
}

.override-clear-target-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* Collapsible subsections */
.subsection-collapsible {
  margin-top: 8px;
  border-top: 1px solid var(--border);
  padding-top: 8px;
}
.subsection-collapsible.first-sub {
  border-top: none;
  margin-top: 0;
  padding-top: 0;
}

.subsection-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 4px;
  cursor: pointer;
  user-select: none;
  border-radius: 4px;
  transition: background 0.12s ease;
}
.subsection-header:hover { background: rgba(0, 0, 0, 0.03); }

.subsection-icon {
  font-size: 10px;
  color: var(--muted);
  width: 12px;
}

.subsection-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.subsection-content {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  transition: max-height 180ms ease, opacity 120ms ease;
}

.subsection-collapsible.expanded .subsection-content {
  max-height: 3000px;
  opacity: 1;
  padding: 8px 0 4px;
  overflow: visible;
}

/* Sub-section styles (for buttons section etc.) */
.sub-section { padding: 10px 0 0; border-top: 1px solid var(--border); }
.sub-section.first-sub { border-top: none; padding-top: 0; }
.sub-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 10px;
}

.icon-btn {
  width: 32px;
  height: 32px;
  display: inline-grid;
  place-items: center;
  border-radius: 8px;
  background: transparent;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: transform 120ms ease, background 140ms ease;
  font-size: 14px;
}
.icon-btn:hover { background: rgba(15, 23, 42, 0.05); }

/* CSS Media Tabs */
.css-media-tabs {
  display: flex;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border);
  margin-bottom: 8px;
}
.css-media-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 8px 6px;
  font-size: 11px;
  font-weight: 600;
  border: none;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s ease;
  color: var(--muted);
}
.css-media-tab svg { flex-shrink: 0; opacity: 0.7; }
.css-media-tab + .css-media-tab { border-left: 1px solid var(--border); }
.css-media-tab.active { background: var(--accent, #4f46e5); color: #fff; }
.css-media-tab.active svg { opacity: 1; }
.css-media-tab:hover:not(.active) { background: var(--surface-2, #f8fafc); color: var(--text); }
.css-media-hint {
  font-size: 10px;
  color: var(--muted);
  margin-bottom: 8px;
  padding: 4px 8px;
  background: var(--surface-2, #f8fafc);
  border-radius: 4px;
  border-left: 2px solid var(--accent, #4f46e5);
}

/* CSS Snippets */
.snippet-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.snippet-save-btn {
  padding: 6px 14px;
  border-radius: 7px;
  border: 1px solid var(--accent, #4f46e5);
  background: #fff;
  color: var(--accent, #4f46e5);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}
.snippet-save-btn:hover:not(:disabled) { background: #eef2ff; }
.snippet-save-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.snippet-hint {
  font-size: 12px;
  color: var(--muted);
  padding: 4px 0;
}

.snippet-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 8px;
  transition: opacity 0.15s ease;
}
.snippet-card.inactive { opacity: 0.5; }

.snippet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.snippet-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  min-width: 0;
}
.snippet-toggle input { width: 14px; height: 14px; cursor: pointer; accent-color: var(--accent, #4f46e5); }

.snippet-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.snippet-scope {
  font-size: 10px;
  font-weight: 500;
  padding: 2px 6px;
  border-radius: 4px;
  background: #e0e7ff;
  color: #4338ca;
  text-transform: capitalize;
  flex-shrink: 0;
}

.snippet-del {
  width: 20px;
  height: 20px;
  display: inline-grid;
  place-items: center;
  border-radius: 5px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 9px;
  cursor: pointer;
  color: var(--muted);
  flex-shrink: 0;
}
.snippet-del:hover { background: #fee2e2; border-color: #fecaca; color: #dc2626; }
.snippet-del:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  background: #f8fafc;
  border-color: var(--border);
  color: var(--muted);
}

.snippet-preview {
  margin: 4px 0 2px;
  padding: 4px 6px;
  background: #f8fafc;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 10px;
  color: var(--muted);
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.4;
  max-height: 48px;
  overflow: hidden;
}

.snippet-meta {
  font-size: 10px;
  color: var(--muted);
  opacity: 0.7;
}

/* Design Versions */
.version-save-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.version-save-form.is-disabled {
  opacity: 0.75;
}

.version-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 7px;
  font-size: 13px;
  font-weight: 600;
  background: #fff;
  color: var(--admin-text, #0f172a);
  box-sizing: border-box;
}

.version-textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 7px;
  font-size: 12px;
  background: #fff;
  color: var(--admin-text, #0f172a);
  resize: vertical;
  font-family: inherit;
  box-sizing: border-box;
}

.version-rating-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.version-rating-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  flex-shrink: 0;
}

.version-rating-stars {
  display: flex;
  gap: 1px;
}

.version-star-btn {
  width: 20px;
  height: 20px;
  display: inline-grid;
  place-items: center;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #d1d5db;
  padding: 0;
  transition: color 0.1s, transform 0.1s;
}

.version-star-btn.active { color: #f59e0b; }
.version-star-btn:hover { transform: scale(1.15); color: #f59e0b; }
.version-star-btn:disabled {
  cursor: not-allowed;
  transform: none;
  opacity: 0.5;
}

.version-rating-value {
  font-size: 11px;
  color: var(--muted);
  font-weight: 600;
  min-width: 32px;
}

.version-save-btn {
  padding: 7px 14px;
  border-radius: 7px;
  border: 1px solid var(--accent, #4f46e5);
  background: #fff;
  color: var(--accent, #4f46e5);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}
.version-save-btn:hover:not(:disabled) { background: #eef2ff; }
.version-save-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.version-save-hint {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.35;
}

.version-state-legend {
  display: grid;
  gap: 6px;
  margin-bottom: 8px;
}

.version-state-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  color: var(--muted);
}

.version-state-chip {
  width: 16px;
  height: 10px;
  border-radius: 4px;
}

.version-state-chip-clean {
  border: 2px solid var(--accent, #4f46e5);
}

.version-state-chip-dirty {
  border: 2px dashed var(--accent, #4f46e5);
}

.version-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 8px;
}
.version-card.version-card-current-clean {
  border: 2px solid var(--accent, #4f46e5);
}
.version-card.version-card-current-dirty {
  border: 2px dashed var(--accent, #4f46e5);
}

.version-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 6px;
}

.version-card-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.version-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--admin-text, #0f172a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.version-card-meta {
  font-size: 10px;
  color: var(--muted);
  opacity: 0.7;
}

.version-card-tools {
  display: flex;
  align-items: center;
  gap: 6px;
}

.version-card-desc {
  font-size: 11px;
  color: var(--muted);
  margin-top: 4px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.version-card-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.version-action-btn {
  flex: 1;
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.12s;
  color: var(--admin-text, #0f172a);
}
.version-action-btn:hover { background: var(--surface-2); border-color: #cbd5e1; }
.version-action-btn:disabled { cursor: default; opacity: 0.7; }

.version-action-save {
  border-color: var(--accent, #4f46e5);
  color: var(--accent, #4f46e5);
}
.version-action-save:hover { background: #eef2ff; }

.version-action-publish.active {
  border-color: #059669;
  background: #ecfdf5;
  color: #065f46;
}

.version-info-wrap {
  position: relative;
  display: inline-flex;
}
.version-info-btn {
  width: 20px;
  height: 20px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: #fff;
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  cursor: default;
}
.version-info-tooltip {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  width: 260px;
  max-width: min(260px, 70vw);
  background: #0f172a;
  color: #fff;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 11px;
  line-height: 1.4;
  box-shadow: 0 10px 24px rgba(2, 6, 23, 0.26);
  white-space: normal;
  z-index: 4;
  opacity: 0;
  transform: translateY(-2px);
  pointer-events: none;
  transition: opacity 0.14s ease, transform 0.14s ease;
}
.version-info-line {
  display: block;
}
.version-info-list {
  margin: 4px 0 0 16px;
  padding: 0;
}
.version-info-list li {
  margin: 1px 0;
}
.version-info-wrap:hover .version-info-tooltip {
  opacity: 1;
  transform: translateY(0);
}

.version-card.version-editing {
  border-color: var(--border);
  box-shadow: none;
}

.version-card-info {
  cursor: pointer;
}
.version-card-info:hover .version-card-title {
  color: var(--accent, #4f46e5);
}

.version-subcard {
  margin-left: 16px;
}

/* Real mobile view (not simulated) */
@media (max-width: 767px) {
  .wrap.corner-bottom-right,
  .wrap.corner-top-right {
    right: 2.5%;
    left: auto;
    width: calc(50% - 3.75%);
  }
  .wrap.corner-bottom-left,
  .wrap.corner-top-left {
    left: 2.5%;
    right: auto;
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
    box-shadow: none;
  }

  .wrap.open .body {
    max-height: 85vh;
  }
}
</style>
