<template>
  <div class="admin-design admin-page">
    <AutosaveToast :message="designAutosaveToastMessage" :tone="designAutosaveToastTone" />

    <!-- Page Header -->
    <header class="page-header">
      <h1>Design Configuration</h1>
      <p class="page-subtitle">Configure which design parameters are visible in the design panel, their ranges, fonts, colors, and more.</p>
    </header>

    <div v-if="loading" class="loading-state">Loading configuration…</div>

    <template v-else-if="config">
      <AdminPageTabs
        :tabs="designTabs"
        :model-value="activeTab"
        @update:model-value="setActiveTab"
      />

      <!-- Responsive Settings -->
      <div v-if="activeTab === 'responsive'" class="config-card">
        <div class="card-header">
          <h2>Responsive Settings</h2>
          <p class="card-hint">Set media query ranges and mobile/tablet preview dimensions used by viewport simulation.</p>
        </div>

        <div class="responsive-settings-grid">
          <section class="responsive-device-panel">
            <div class="responsive-device-heading">
              <span class="responsive-device-icon">
                <font-awesome-icon :icon="responsiveDeviceIcon('mobile')" />
              </span>
              <div>
                <h3>Mobile</h3>
                <p>{{ responsiveDeviceLabel('mobile') }}</p>
              </div>
            </div>
            <div class="responsive-input-grid">
              <label class="responsive-field responsive-field--range">
                <span class="responsive-field__label">Max width</span>
                <span class="responsive-field__control">
                  <input
                    v-model.number="config.responsive.mobile.maxWidth"
                    class="field"
                    type="number"
                    min="240"
                    max="4094"
                    @change="normalizeResponsiveSettings"
                  />
                  <span>px</span>
                </span>
              </label>
              <label class="responsive-field">
                <span class="responsive-field__label">Preview width</span>
                <span class="responsive-field__control">
                  <input
                    v-model.number="config.responsive.mobile.previewWidth"
                    class="field"
                    type="number"
                    min="64"
                    max="4096"
                    @change="normalizeResponsiveSettings"
                  />
                  <span>px</span>
                </span>
              </label>
              <label class="responsive-field">
                <span class="responsive-field__label">Preview height</span>
                <span class="responsive-field__control">
                  <input
                    v-model.number="config.responsive.mobile.previewHeight"
                    class="field"
                    type="number"
                    min="64"
                    max="8192"
                    @change="normalizeResponsiveSettings"
                  />
                  <span>px</span>
                </span>
              </label>
            </div>
          </section>

          <section class="responsive-device-panel">
            <div class="responsive-device-heading">
              <span class="responsive-device-icon">
                <font-awesome-icon :icon="responsiveDeviceIcon('tablet')" />
              </span>
              <div>
                <h3>Tablet</h3>
                <p>{{ responsiveDeviceLabel('tablet') }}</p>
              </div>
            </div>
            <div class="responsive-input-grid">
              <div class="responsive-field responsive-field--range">
                <span class="responsive-field__label">Range</span>
                <span class="responsive-field__control responsive-field__control--readonly">
                  <strong>{{ config.responsive.tablet.minWidth }}-{{ config.responsive.tablet.maxWidth }}</strong>
                  <span>px</span>
                </span>
              </div>
              <label class="responsive-field">
                <span class="responsive-field__label">Preview width</span>
                <span class="responsive-field__control">
                  <input
                    v-model.number="config.responsive.tablet.previewWidth"
                    class="field"
                    type="number"
                    min="64"
                    max="4096"
                    @change="normalizeResponsiveSettings"
                  />
                  <span>px</span>
                </span>
              </label>
              <label class="responsive-field">
                <span class="responsive-field__label">Preview height</span>
                <span class="responsive-field__control">
                  <input
                    v-model.number="config.responsive.tablet.previewHeight"
                    class="field"
                    type="number"
                    min="64"
                    max="8192"
                    @change="normalizeResponsiveSettings"
                  />
                  <span>px</span>
                </span>
              </label>
            </div>
          </section>

          <section class="responsive-device-panel">
            <div class="responsive-device-heading">
              <span class="responsive-device-icon">
                <font-awesome-icon :icon="responsiveDeviceIcon('desktop')" />
              </span>
              <div>
                <h3>Desktop</h3>
                <p>{{ responsiveDeviceLabel('desktop') }}</p>
              </div>
            </div>
            <div class="responsive-input-grid">
              <label class="responsive-field responsive-field--range">
                <span class="responsive-field__label">Min width</span>
                <span class="responsive-field__control">
                  <input
                    v-model.number="config.responsive.desktop.minWidth"
                    class="field"
                    type="number"
                    :min="Number(config.responsive.mobile.maxWidth || 0) + 2"
                    max="4096"
                    @change="normalizeResponsiveSettings"
                  />
                  <span>px</span>
                </span>
              </label>
            </div>
          </section>
        </div>

        <div class="responsive-actions">
          <button class="btn-outline" type="button" @click="openMediaCroppingSettings">
            Media Cropping Settings
          </button>
          <button class="btn-danger" type="button" @click="resetResponsiveSettings">
            Reset Responsive Defaults
          </button>
        </div>
      </div>

      <!-- Design Panel Sections -->
      <div v-else-if="activeTab === 'sectionOrder'" class="config-card">
        <div class="card-header">
          <h2>Design Panel Sections</h2>
          <p class="card-hint">Drag to reorder design panel sections. Toggle visibility with the eye icon.</p>
        </div>
        <draggable
          v-model="config.sectionOrder"
          item-key="id"
          handle=".drag-handle"
          ghost-class="drag-ghost"
          :animation="150"
          class="section-order-list"
        >
          <template #item="{ element: sectionKey }">
            <div class="section-order-item" :class="{ 'is-hidden': isSectionHidden(sectionKey) }">
              <span class="drag-handle">⠿</span>
              <span class="section-name">{{ sectionLabels[sectionKey] || sectionKey }}</span>
              <button 
                type="button" 
                class="visibility-btn" 
                :class="{ hidden: isSectionHidden(sectionKey) }"
                @click="toggleSectionVisibility(sectionKey)"
                :title="isSectionHidden(sectionKey) ? 'Show section' : 'Hide section'"
              >
                <font-awesome-icon :icon="isSectionHidden(sectionKey) ? faEyeSlash : faEye" />
              </button>
            </div>
          </template>
        </draggable>
      </div>

      <!-- Design Panel Overrides -->
      <div v-else-if="activeTab === 'overrideParams' && config.sectionOverrideParams" class="config-card">
        <div class="card-header">
          <h2>Design Panel Overrides</h2>
          <p class="card-hint">Configure which design parameters can be overridden per section or in the header.</p>
        </div>
        <div class="override-config">
          <div class="override-group override-group-header">
            <h3 class="override-group-title">Header Override Parameters</h3>
            <p class="card-hint" style="margin: 0 0 8px;">Design params shown in the header override panel. Only visible when the header template includes the relevant feature.</p>
            <div class="override-param-groups">
              <div 
                v-for="group in headerOverrideParamsByGroup" 
                :key="group.key" 
                class="override-param-group"
              >
                <div class="override-param-group-label">{{ group.label }}</div>
                <div class="option-checks">
                  <label v-for="param in group.params" :key="`header_${param}`" class="mini-check">
                    <input
                      type="checkbox"
                      :checked="(config.sectionOverrideParams.header || []).includes(param)"
                      @change="toggleOverrideParam('header', param, $event.target.checked)"
                    />
                    <span>{{ getOverrideParamLabel(param) }}</span>
                  </label>
                </div>
              </div>
            </div>
          </div>
          <div class="override-group">
            <h3 class="override-group-title">Constant Section Parameters</h3>
            <p class="card-hint" style="margin: 0 0 8px;">Shown at the top of each section design tab in the section editor.</p>
            <div class="option-checks">
              <label v-for="param in constantSectionOverrideParams" :key="param.key" class="mini-check">
                <input
                  type="checkbox"
                  :checked="(config.sectionOverrideParams.constants || []).includes(param.key)"
                  @change="toggleOverrideParam('constants', param.key, $event.target.checked)"
                />
                <span>{{ param.label }}</span>
              </label>
            </div>
          </div>
          <div class="override-group">
            <h3 class="override-group-title">Shared Section Override Parameters</h3>
            <div class="override-param-groups">
              <div 
                v-for="group in overrideParamsByGroup" 
                :key="group.key" 
                class="override-param-group"
              >
                <div class="override-param-group-label">{{ group.label }}</div>
                <div class="option-checks">
                  <label v-for="param in group.params" :key="param" class="mini-check">
                    <input
                      type="checkbox"
                      :checked="(config.sectionOverrideParams.generic || []).includes(param)"
                      @change="toggleOverrideParam('generic', param, $event.target.checked)"
                    />
                    <span>{{ getOverrideParamLabel(param) }}</span>
                  </label>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Design Panel Parameters -->
      <div v-else-if="activeTab === 'designParameters'" class="config-card config-card-wide">
        <div class="card-header">
          <h2>Design Panel Parameters</h2>
          <p class="card-hint">Configure visibility, favorites, ranges, and options for each parameter shown in the design panel.</p>
        </div>

        <!-- Sticky Header with Column Labels and Filters -->
        <div class="params-sticky-header">
          <div class="params-header-row">
            <div class="col-drag"></div>
            <div class="col-param">Parameter</div>
            <div class="col-subsection">Subsection</div>
            <div class="col-type">Type</div>
            <div class="col-visible">Visible</div>
            <div class="col-fav" title="Favorite">
              <font-awesome-icon :icon="faStar" />
            </div>
            <div class="col-responsive">Responsive</div>
            <div class="col-config">Configuration</div>
          </div>
          <div class="params-filter-row">
            <div class="col-drag"></div>
            <div class="col-param">
              <input 
                type="text" 
                v-model="paramFilters.name" 
                placeholder="Filter name..." 
                class="filter-input"
              />
            </div>
            <div class="col-subsection">
              <input 
                type="text" 
                v-model="paramFilters.subsection" 
                placeholder="Filter..." 
                class="filter-input"
              />
            </div>
            <div class="col-type">
              <select v-model="paramFilters.type" class="filter-select">
                <option value="">All</option>
                <option v-for="t in availableParamTypes" :key="t" :value="t">{{ t }}</option>
              </select>
            </div>
            <div class="col-visible">
              <select v-model="paramFilters.visible" class="filter-select filter-select-sm">
                <option value="">All</option>
                <option value="true">✓</option>
                <option value="false">✗</option>
              </select>
            </div>
            <div class="col-fav">
              <select v-model="paramFilters.favorite" class="filter-select filter-select-sm">
                <option value="">All</option>
                <option value="true">Favorite</option>
                <option value="false">Not Fav</option>
              </select>
            </div>
            <div class="col-responsive"></div>
            <div class="col-config">
              <button 
                v-if="hasActiveFilters" 
                class="btn-reset-filters" 
                @click="resetParamFilters"
                title="Reset all filters"
              >
                <font-awesome-icon :icon="faFilter" />
                Reset
              </button>
            </div>
          </div>
        </div>

        <div class="params-sections">
          <div 
            v-for="sectionKey in config.sectionOrder" 
            :key="sectionKey" 
            class="params-section"
            :class="{ 'is-collapsed': collapsedParamSections[sectionKey] }"
            v-show="filteredParamsBySection[sectionKey]?.length > 0"
          >
            <div class="section-header-row" @click="toggleParamSectionCollapse(sectionKey)">
              <span class="section-collapse-icon">
                <font-awesome-icon :icon="collapsedParamSections[sectionKey] ? faChevronRight : faChevronDown" />
              </span>
              <span class="section-badge">{{ sectionLabels[sectionKey] || sectionKey }}</span>
              <span class="section-count">{{ filteredParamsBySection[sectionKey]?.length || 0 }} params</span>
            </div>
            <draggable
              v-show="!collapsedParamSections[sectionKey]"
              :model-value="filteredParamsBySection[sectionKey] || []"
              @update:model-value="(val) => updateParamOrder(sectionKey, val)"
              item-key="id"
              handle=".drag-handle"
              ghost-class="drag-ghost"
              :animation="150"
              :disabled="isMobile"
              class="params-list"
            >
              <template #item="{ element: paramKey }">
                <div
                  class="param-row"
                  :class="{ 'param-hidden': !config.parameters[paramKey]?.visible }"
                >
                  <div class="col-drag">
                    <span class="drag-handle" title="Drag to reorder">⋮⋮</span>
                  </div>
                  <div class="col-param">
                    <input
                      type="text"
                      class="param-label-input"
                      :value="config.parameters[paramKey]?.label ?? ''"
                      @input="updateParamLabel(paramKey, $event.target.value)"
                      @focus="$event.target.select()"
                      :placeholder="paramKey"
                    />
                    <div class="param-key">{{ paramKey }}</div>
                  </div>
                  <div class="col-subsection">
                    <input
                      type="text"
                      class="subsection-input"
                      :value="config.parameters[paramKey]?.subsection ?? ''"
                      @input="updateSubsection(paramKey, $event.target.value)"
                      @focus="$event.target.select()"
                      placeholder="—"
                    />
                  </div>
                  <div class="col-type">
                    <span class="type-badge" :class="config.parameters[paramKey]?.type">{{ config.parameters[paramKey]?.type }}</span>
                  </div>
                  <div class="col-visible">
                    <input type="checkbox" v-model="config.parameters[paramKey].visible" />
                  </div>
                  <div class="col-fav">
                    <font-awesome-icon :icon="faStar" class="fav-btn"
                      :class="{ active: config.parameters[paramKey].favorite }"
                      @click="config.parameters[paramKey].favorite = !config.parameters[paramKey].favorite"
                      title="Toggle favorite" />
                  </div>
                  <div class="col-responsive">
                    <select
                      v-if="config.parameters[paramKey]?.type === 'slider'"
                      :value="config.parameters[paramKey].responsive || ''"
                      @change="config.parameters[paramKey].responsive = $event.target.value || null"
                      class="responsive-select"
                    >
                      <option value="">None</option>
                      <option value="clamp">Clamp</option>
                      <option value="media">Media Query</option>
                    </select>
                    <select
                      v-else-if="['dropdown', 'buttongroup', 'positiongrid', 'checkbox'].includes(config.parameters[paramKey]?.type)"
                      :value="config.parameters[paramKey].responsive || ''"
                      @change="config.parameters[paramKey].responsive = $event.target.value || null"
                      class="responsive-select"
                    >
                      <option value="">None</option>
                      <option value="media">Media Query</option>
                    </select>
                    <span v-else class="no-config">—</span>
                  </div>
                  <div class="col-config">
                    <!-- Slider config with multi-unit support -->
                    <div v-if="config.parameters[paramKey]?.type === 'slider'" class="slider-config">
                      <div
                        v-for="(uc, ucIdx) in getUnitConfigs(paramKey)"
                        :key="ucIdx"
                        class="unit-config-row"
                        :class="{ 'is-default': isDefaultUnit(paramKey, uc.unit) }"
                      >
                        <label class="mini-field unit-field">
                          <span>Unit</span>
                          <select
                            :value="uc.unit"
                            @change="updateUnitConfig(paramKey, ucIdx, 'unit', $event.target.value)"
                            class="unit-select"
                          >
                            <optgroup label="Absolute">
                              <option value="px">px</option>
                              <option value="pt">pt</option>
                              <option value="cm">cm</option>
                              <option value="mm">mm</option>
                              <option value="in">in</option>
                            </optgroup>
                            <optgroup label="Relative">
                              <option value="%">%</option>
                              <option value="em">em</option>
                              <option value="rem">rem</option>
                              <option value="vw">vw</option>
                              <option value="vh">vh</option>
                              <option value="vmin">vmin</option>
                              <option value="vmax">vmax</option>
                              <option value="ch">ch</option>
                            </optgroup>
                            <optgroup label="Other">
                              <option value="">none</option>
                            </optgroup>
                          </select>
                        </label>
                        <label class="mini-field">
                          <span>Min</span>
                          <input
                            type="number"
                            :value="uc.min"
                            @input="updateUnitConfig(paramKey, ucIdx, 'min', parseFloat($event.target.value))"
                            step="any"
                          />
                        </label>
                        <label class="mini-field">
                          <span>Max</span>
                          <input
                            type="number"
                            :value="uc.max"
                            @input="updateUnitConfig(paramKey, ucIdx, 'max', parseFloat($event.target.value))"
                            step="any"
                          />
                        </label>
                        <label class="mini-field">
                          <span>Step</span>
                          <input
                            type="number"
                            :value="uc.step"
                            @input="updateUnitConfig(paramKey, ucIdx, 'step', parseFloat($event.target.value))"
                            step="any"
                          />
                        </label>
                        <font-awesome-icon :icon="faStar" v-if="!isDefaultUnit(paramKey, uc.unit)"
                          class="default-btn"
                          type="button"
                          @click="setDefaultUnit(paramKey, uc.unit)"
                          title="Set as default unit"/>
                        <button
                          v-if="getUnitConfigs(paramKey).length > 1"
                          class="remove-unit-btn"
                          type="button"
                          @click="removeUnitConfig(paramKey, ucIdx)"
                          title="Remove this unit config"
                        >✕</button>
                      </div>
                      <div class="slider-config-actions">
                        <button
                          class="add-unit-btn"
                          type="button"
                          @click="addUnitConfig(paramKey)"
                        >+ Add Unit</button>
                        <label class="mini-check allow-input-check">
                          <input
                            type="checkbox"
                            :checked="config.parameters[paramKey].allowInput"
                            @change="config.parameters[paramKey].allowInput = $event.target.checked"
                          />
                          <span>Allow text input</span>
                        </label>
                      </div>
                    </div>

                    <!-- Dropdown config -->
                    <div v-else-if="config.parameters[paramKey]?.type === 'dropdown' && config.parameters[paramKey].enabledOptions" class="inline-config">
                      <div class="option-checks">
                        <label v-for="opt in getAllDropdownOptions(paramKey)" :key="opt" class="mini-check">
                          <input
                            type="checkbox"
                            :checked="config.parameters[paramKey].enabledOptions.includes(opt)"
                            @change="toggleDropdownOption(paramKey, opt, $event.target.checked)"
                          />
                          <span>{{ formatOptionLabel(paramKey, opt) }}</span>
                        </label>
                      </div>
                    </div>

                    <!-- Button group config -->
                    <div v-else-if="config.parameters[paramKey]?.type === 'buttongroup' && config.parameters[paramKey].enabledOptions" class="inline-config">
                      <div class="option-checks">
                        <label v-for="opt in getAllButtonGroupOptions(paramKey)" :key="opt" class="mini-check">
                          <input
                            type="checkbox"
                            :checked="config.parameters[paramKey].enabledOptions.includes(opt)"
                            @change="toggleDropdownOption(paramKey, opt, $event.target.checked)"
                          />
                          <span>{{ opt }}</span>
                        </label>
                      </div>
                    </div>

                    <!-- Checkbox / other: no extra config -->
                    <span v-else class="no-config">—</span>
                  </div>
                </div>
              </template>
            </draggable>
          </div>
        </div>
      </div>

      <!-- Font Families Editor -->
      <div v-else-if="activeTab === 'fontFamilies'" class="config-card">
        <div class="card-header">
          <h2>Font Families</h2>
          <p class="card-hint">Set the font family name and fallback. Public pages only load cached font stylesheets.</p>
        </div>
        <p class="font-family-info">
          Use the exact family string (for example <code>Open Sans</code> or <code>Source Serif 4</code>) without fallback or variant suffixes.
          Health Check is read-only. Use Cache via browser to store Google font assets on this server. Public pages use fallback fonts when a family is not cached.
        </p>
        <label class="font-preview-sample-label">
          <span>Preview Sample String (local only)</span>
          <input
            v-model="fontPreviewSample"
            class="font-preview-sample-input"
            placeholder="Enter preview sample text"
          />
        </label>
        <div class="font-list">
          <div v-for="(font, idx) in config.fontFamilies" :key="idx" class="font-item">
            <div class="font-item-main">
              <div class="font-item-group font-item--wrapper">
                <input
                  v-model="font.label"
                  class="font-label-input"
                  placeholder="Font family (e.g. Noto Sans)"
                  @input="onFontFamilyLabelInput(font, idx)"
                  @blur="onFontFamilyLabelBlur(font, idx)"
                />
                <select v-model="font.fallback" class="font-fallback-select" @change="onFontFamilyFallbackChange(font, idx)">
                  <option value="sans-serif">sans-serif</option>
                  <option value="serif">serif</option>
                </select>
              </div>
              <div class="font-preview-pair">
                <div class="font-preview-card">
                  <span class="font-preview-title">Family</span>
                  <span class="font-preview-subtitle">{{ normalizeGoogleFontFamilyName(font.label) || "No family set" }}</span>
                  <span class="font-preview-text" :style="getFontFamilyPreviewStyle(font)">
                    {{ fontPreviewSampleText }}
                  </span>
                </div>
                <div class="font-preview-card">
                  <span class="font-preview-title">Fallback</span>
                  <span class="font-preview-subtitle">{{ normalizeFontFallback(font.fallback) }}</span>
                  <span class="font-preview-text" :style="getFontFallbackPreviewStyle(font)">
                    {{ fontPreviewSampleText }}
                  </span>
                </div>
              </div>
            </div>
            <div class="font-item-group font-item--sanity">
              <span
                v-if="getFontHealthMessage(idx)"
                class="font-health-status"
                :class="`is-${getFontHealthStatus(idx)}`"
              >
                {{ getFontHealthMessage(idx) }}
              </span>
              <button
                type="button"
                class="btn-outline btn-sm font-check-btn"
                :disabled="(isFontHealthChecking(idx) || isFontCacheNowBusy(idx)) || !font.label || !String(font.label).trim()"
                @click="checkFontFamilyHealth(font, idx)"
              >
                {{ isFontHealthChecking(idx) ? 'Checking…' : 'Health Check' }}
              </button>
              <button
                v-if="getFontHealthCanCacheViaBrowser(idx)"
                type="button"
                class="btn-outline btn-sm font-cache-btn"
                :disabled="isFontHealthChecking(idx) || isFontCacheNowBusy(idx)"
                @click="cacheFontFamilyNow(font, idx)"
              >
                {{ isFontCacheNowBusy(idx) ? 'Caching…' : 'Cache via browser' }}
              </button>
              <button class="btn-icon-danger" @click="removeFontFamily(idx)" title="Remove">✕</button>
            </div>
          </div>
          <button class="btn-outline btn-sm" @click="addFontFamily">+ Add Font</button>
        </div>
      </div>

      <!-- Button Instances -->
      <div v-else-if="activeTab === 'buttonInstances'" class="config-card">
        <div class="card-header">
          <h2>Button Instances</h2>
          <p class="card-hint">Define button types (e.g. primary, secondary, ghost, hero). Each enabled type gets its own per-type overrides in the design panel.</p>
        </div>
        <div class="button-instances">
          <div
            v-for="(btn, idx) in config.buttonInstances"
            :key="idx"
            class="button-instance-item"
            :class="{ 'is-hidden': !btn.enabled }"
          >
            <input
              v-model="btn.label"
              class="instance-name-input"
              placeholder="Button type name"
              @input="syncButtonInstanceId(idx)"
            />
            <button
              type="button"
              class="visibility-btn button-instance-visibility-btn"
              :class="{ hidden: !btn.enabled }"
              @click="toggleButtonInstanceVisibility(idx)"
              :title="btn.enabled ? 'Hide button type' : 'Show button type'"
              :aria-label="btn.enabled ? 'Hide button type' : 'Show button type'"
            >
              <font-awesome-icon :icon="btn.enabled ? faEye : faEyeSlash" />
            </button>
            <button class="btn-icon-danger" @click="config.buttonInstances.splice(idx, 1)" title="Remove">✕</button>
          </div>
          <button class="btn-outline btn-sm" @click="addButtonInstance">+ Add Button Type</button>
        </div>
        <div class="per-type-params">
          <div class="per-type-params-header">
            <h3 class="per-type-title">Button Parameters</h3>
            <p class="card-hint">Shared parameters use the same value for every button type. Individual parameters can differ per type in the design panel.</p>
          </div>
          <div class="button-param-groups">
            <div class="button-param-group">
              <div class="button-param-group-label">Shared Parameters</div>
              <div class="option-checks">
                <label v-for="param in sharedButtonParamBaseNames" :key="`shared_${param.key}`" class="mini-check">
                  <input
                    type="checkbox"
                    :checked="true"
                    @change="toggleButtonSharedParam(param.key, $event.target.checked)"
                  />
                  <span>{{ param.label }}</span>
                </label>
              </div>
              <div v-if="sharedButtonParamBaseNames.length === 0" class="button-param-empty">No shared parameters.</div>
            </div>
            <div class="button-param-group">
              <div class="button-param-group-label">Individual Parameters</div>
              <div class="option-checks">
                <label v-for="param in individualButtonParamBaseNames" :key="`individual_${param.key}`" class="mini-check">
                  <input
                    type="checkbox"
                    :checked="false"
                    @change="toggleButtonSharedParam(param.key, $event.target.checked)"
                  />
                  <span>{{ param.label }}</span>
                </label>
              </div>
              <div v-if="individualButtonParamBaseNames.length === 0" class="button-param-empty">No individual parameters.</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Color Links -->
      <div v-else-if="activeTab === 'colorLinks'" class="config-card">
        <div class="card-header">
          <h2>Color Linking</h2>
          <p class="card-hint">Link non-base color parameters to a base color as their default value. In the design panel, users can select a linked base color via a link button.</p>
        </div>
        <div class="base-colors-editor">
          <h3 class="base-colors-title">Base Colors</h3>
          <p class="card-hint">Names here are used in color-link pickers across admin design tabs.</p>
          <div class="base-colors-list">
            <div class="base-color-row base-color-row-header">
              <span>Current Value</span>
              <span>Base Color Label</span>
              <span>Specific High Contrast</span>
            </div>
            <div v-for="base in editableBaseColorParams" :key="base.key" class="base-color-row">
              <div class="base-color-preview">
                <VueColorPicker
                  :model-value="toColorInputValue(base.currentColor, '#94a3b8')"
                  :fallback-color="toColorInputValue(config.parameters?.[base.key]?.default, '#94a3b8')"
                  :size="24"
                  @update:model-value="setBaseColorValue(base.key, $event)"
                />
                <span class="base-color-value">{{ base.currentColorLabel }}</span>
              </div>
              <div class="base-color-label-row">
                <input
                  v-model="config.parameters[base.key].label"
                  class="base-color-name-input"
                  type="text"
                  :placeholder="base.defaultLabel"
                />
                <button
                  v-if="base.isCustom"
                  type="button"
                  class="base-color-remove-btn"
                  title="Remove custom base color"
                  @click="removeCustomBaseColor(base.key)"
                >✕</button>
              </div>
              <div class="base-color-contrast">
                <select
                  class="base-contrast-source-select"
                  :value="getBaseContrastSourceValue(base)"
                  @change="setBaseContrastSource(base.key, $event.target.value)"
                >
                  <option value="auto">Auto</option>
                  <option value="custom">Custom</option>
                  <option
                    v-for="target in base.contrastLinkTargets"
                    :key="`${base.key}_link_${target.key}`"
                    :value="`link:${target.key}`"
                  >
                    {{ target.label }}
                  </option>
                </select>
                <span class="base-contrast-slot">
                  <VueColorPicker
                    v-if="base.contrastMode === 'custom'"
                    class="base-contrast-picker-shell"
                    :model-value="toColorInputValue(base.specificContrastColor || base.autoContrastPreview)"
                    :fallback-color="toColorInputValue(base.autoContrastPreview)"
                    :size="26"
                    @update:model-value="setBaseSpecificContrast(base.key, $event)"
                  />
                  <span
                    v-else-if="base.contrastMode === 'baseLink'"
                    class="cl-preview-swatch base-contrast-linked-swatch"
                    :style="getColorPreviewStyle(base.linkedContrastPreview || '#cbd5e1')"
                  ></span>
                  <span v-else class="base-contrast-slot-placeholder"></span>
                </span>
                <span class="base-contrast-value">
                  {{ base.contrastDisplayLabel }}
                </span>
                <span
                  v-if="base.specificContrastStale"
                  class="base-contrast-warning"
                  title="Base color changed since this specific contrast color was set."
                >
                  !
                </span>
              </div>
            </div>
          </div>
          <button type="button" class="btn-outline btn-sm add-base-color-btn" @click="addCustomBaseColor">
            Add Custom Base Color
          </button>
        </div>
        <div class="fallback-contrast-editor">
          <h3 class="base-colors-title">Fallback High Contrast</h3>
          <p class="card-hint">Used when no specific base contrast is set, or when background context is arbitrary (for example images).</p>
          <div class="fallback-contrast-list">
            <div class="fallback-contrast-row">
              <span class="fallback-contrast-label">Dark</span>
              <VueColorPicker
                class="base-contrast-picker-shell"
                :model-value="toColorInputValue(state.design.highContrastDark, '#0b1220')"
                fallback-color="#0b1220"
                :size="26"
                @update:model-value="setFallbackHighContrast('highContrastDark', $event)"
              />
              <span class="base-contrast-value">{{ state.design.highContrastDark || '#0b1220' }}</span>
            </div>
            <div class="fallback-contrast-row">
              <span class="fallback-contrast-label">Light</span>
              <VueColorPicker
                class="base-contrast-picker-shell"
                :model-value="toColorInputValue(state.design.highContrastLight, '#f8fafc')"
                fallback-color="#f8fafc"
                :size="26"
                @update:model-value="setFallbackHighContrast('highContrastLight', $event)"
              />
              <span class="base-contrast-value">{{ state.design.highContrastLight || '#f8fafc' }}</span>
            </div>
          </div>
        </div>
        <div v-if="adminUiEditorColorParams.length" class="admin-ui-colors-editor">
          <h3 class="base-colors-title">Admin UI Colors</h3>
          <p class="card-hint">Admin-only colors used for editor actions, status, and favorite markers.</p>
          <div class="admin-ui-colors-list">
            <div v-for="param in adminUiEditorColorParams" :key="param.key" class="admin-ui-color-row">
              <span class="admin-ui-color-label">{{ param.label }}</span>
              <VueColorPicker
                class="base-contrast-picker-shell"
                :model-value="toColorInputValue(param.currentColor, '#4f46e5')"
                :fallback-color="toColorInputValue(param.defaultColor, '#4f46e5')"
                :size="26"
                @update:model-value="setAdminUiColorValue(param.key, $event)"
              />
              <span class="base-contrast-value">{{ param.currentColorLabel }}</span>
            </div>
          </div>
        </div>
        <div class="color-links-table">
          <label class="mini-check color-variation-toggle">
            <input type="checkbox" v-model="config.showColorVariationDropdowns" />
            <span>Show opacity variation dropdowns in Color Linking and Design Panel</span>
          </label>
          <div class="cl-sort-row">
            <span class="cl-sort-label">Sort / Group</span>
            <select v-model="colorLinkSortMode" class="cl-sort-select">
              <option
                v-for="opt in COLOR_LINK_SORT_OPTIONS"
                :key="`sort_${opt.value}`"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select>
          </div>
          <div v-for="group in groupedLinkableColorParams" :key="group.key" class="cl-group">
            <div class="cl-group-title">
              <span>{{ group.label }}</span>
              <span class="cl-group-count">{{ group.items.length }}</span>
            </div>
            <div class="cl-header">
              <span>Color Parameter</span>
              <span>Linked to Base Color</span>
            </div>
            <div v-for="param in group.items" :key="param.key" class="cl-row">
              <div class="cl-label-wrap">
                <span class="cl-label">{{ param.label }}</span>
                <span class="cl-context">{{ param.contextLabel }}</span>
              </div>
              <div class="cl-control">
                <div class="cl-select-row">
                  <select v-model="config.colorLinks[param.key]" class="cl-select">
                    <option value="">None (manual)</option>
                    <option v-for="bc in baseColorOptions" :key="bc.key" :value="bc.key">{{ bc.label }}</option>
                  </select>
                  <select
                    v-if="config.showColorVariationDropdowns !== false"
                    class="cl-variation-select"
                    :value="getColorVariationValue(param.key)"
                    @change="setColorVariation(param.key, $event.target.value)"
                  >
                    <option v-for="variation in COLOR_VARIATION_OPTIONS" :key="`var_${variation}`" :value="variation">
                      {{ variation }}%
                    </option>
                  </select>
                </div>
                <div class="cl-preview" :class="{ 'is-empty': !param.hasAssignedColor }">
                  <span class="cl-preview-swatch" :style="getColorPreviewStyle(param.assignedColor)"></span>
                  <span class="cl-preview-value">{{ param.assignedColorLabel }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Reset to Defaults -->
      <div v-else-if="activeTab === 'reset'" class="config-card">
        <div class="card-header">
          <h2>Reset</h2>
        </div>
        <div class="reset-actions">
          <button class="btn-danger" @click="resetDesignToDefaults">Reset Design Settings to Defaults</button>
          <button class="btn-outline" @click="resetConfigToDefaults">Reset Admin Configuration to Defaults</button>
        </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import draggable from "vuedraggable";
import {
  faChevronDown,
  faChevronRight,
  faDesktop,
  faEye,
  faEyeSlash,
  faFilter,
  faMobileScreenButton,
  faStar,
  faTabletScreenButton,
} from "@fortawesome/free-solid-svg-icons";
import * as api from "../../services/api.js";
import { useStore } from "../../store/store.js";
import { useAuth } from "../../services/auth.js";
import AdminPageTabs from "../../components/admin/AdminPageTabs.vue";
import AutosaveToast from "../../components/admin/AutosaveToast.vue";
import VueColorPicker from "../../components/ui/color/VueColorPicker.vue";
import {
  PARAM_CONFIGS,
  PARAMS_BY_SECTION,
  OVERRIDABLE_PARAMS,
  getParamOptionLabel,
  getParamOptionValues,
} from "../../designDefs.js";
import {
  BASE_VARS_SUBSECTION,
  DEFAULT_BASE_COLOR_KEYS,
  getAutoHighContrastColor,
  getBaseSpecificHighContrastEntry,
  isSpecificHighContrastStale,
} from "../../utils/colorLinkOptions.js";
import {
  COLOR_VARIATION_OPTIONS,
  DEFAULT_COLOR_VARIATION,
  applyColorVariation,
  normalizeColorVariation,
} from "../../utils/colorVariations.js";
import {
  DEFAULT_RESPONSIVE_CONFIG,
  getResponsiveDeviceLabel,
  normalizeResponsiveConfig,
} from "../../utils/responsiveViewport.js";

const { state, resetDesignSettings, loadDesignSettings, loadAdminDesignConfig, updateDesignSetting, saveDesignSettings, applyDesignCSS } = useStore();
const { state: authState, initAuth } = useAuth();
const route = useRoute();
const router = useRouter();
const CUSTOM_BASE_COLOR_PREFIX = "baseColorCustom_";
const ADMIN_UI_COLOR_KEYS = [
  "adminAccentColor",
  "adminPrimaryColor",
  "adminDangerColor",
  "adminWarningColor",
  "adminFavoriteColor",
];

const loading = ref(true);
const saving = ref(false);
const autoSaving = ref(false);
const lastSaved = ref(false);
const autoSaveError = ref("");
const config = ref(null);
const configBaselineSignature = ref("");
const configInitialized = ref(false);
let saveTimeout = null;
let savedMessageTimeout = null;
let fallbackContrastSaveTimeout = null;
let baseColorSaveTimeout = null;
let adminUiColorSaveTimeout = null;

// Mobile detection
const isMobile = ref(window.innerWidth < 768);
function handleResize() {
  isMobile.value = window.innerWidth < 768;
}

const designTabs = [
  { id: "sectionOrder", label: "Sections", to: "/admin/design/sections" },
  { id: "designParameters", label: "Parameters", to: "/admin/design/parameters" },
  { id: "overrideParams", label: "Overrides", to: "/admin/design/overrides" },
  { id: "fontFamilies", label: "Fonts", to: "/admin/design/fonts" },
  { id: "buttonInstances", label: "Buttons", to: "/admin/design/buttons" },
  { id: "colorLinks", label: "Colors", to: "/admin/design/colors" },
  { id: "responsive", label: "Responsive", to: "/admin/design/responsive" },
  { id: "reset", label: "Reset", to: "/admin/design/reset" },
];
const DESIGN_TAB_BY_SLUG = {
  sections: "sectionOrder",
  parameters: "designParameters",
  overrides: "overrideParams",
  fonts: "fontFamilies",
  buttons: "buttonInstances",
  colors: "colorLinks",
  responsive: "responsive",
  "panel-sections": "sectionOrder",
  "panel-parameters": "designParameters",
  "panel-overrides": "overrideParams",
  "section-order": "sectionOrder",
  "design-parameters": "designParameters",
  "design-overrides": "overrideParams",
  "font-families": "fontFamilies",
  "button-types": "buttonInstances",
  "color-linking": "colorLinks",
  reset: "reset",
};

const designAutosaveToastTone = computed(() => {
  if (autoSaving.value) return "saving";
  if (autoSaveError.value) return "error";
  if (lastSaved.value) return "saved";
  return "idle";
});

const designAutosaveToastMessage = computed(() => {
  if (autoSaving.value) return "Saving design configuration...";
  if (autoSaveError.value) return autoSaveError.value;
  if (lastSaved.value) return "Design configuration saved.";
  return "";
});

function clearDesignAutosaveStatusTimer() {
  if (savedMessageTimeout) {
    clearTimeout(savedMessageTimeout);
    savedMessageTimeout = null;
  }
}

function showDesignAutosaveSaved() {
  clearDesignAutosaveStatusTimer();
  autoSaveError.value = "";
  lastSaved.value = true;
  savedMessageTimeout = setTimeout(() => {
    lastSaved.value = false;
    savedMessageTimeout = null;
  }, 3000);
}

function showDesignAutosaveError(message = "Design configuration autosave failed.") {
  clearDesignAutosaveStatusTimer();
  lastSaved.value = false;
  autoSaveError.value = message;
  savedMessageTimeout = setTimeout(() => {
    autoSaveError.value = "";
    savedMessageTimeout = null;
  }, 3000);
}
const COLOR_LINK_SORT_STORAGE_KEY = "admin_design_color_link_sort_mode";
const COLOR_LINK_SORT_OPTIONS = [
  { value: "sectionAlpha", label: "Section / Subsection → A–Z" },
  { value: "baseReference", label: "Base Color Reference" },
];
const activeTab = computed(() => {
  const slug = String(route.path || "").split("/")[3] || "";
  return DESIGN_TAB_BY_SLUG[slug] || designTabs[0].id;
});

function responsiveDeviceLabel(device) {
  return getResponsiveDeviceLabel(device, config.value?.responsive);
}

function responsiveDeviceIcon(device) {
  if (device === "mobile") return faMobileScreenButton;
  if (device === "tablet") return faTabletScreenButton;
  return faDesktop;
}

function normalizeResponsiveSettings() {
  if (!config.value) return;
  config.value.responsive = normalizeResponsiveConfig(config.value.responsive);
  state.adminDesignConfig = config.value;
  applyDesignCSS();
}

function resetResponsiveSettings() {
  if (!config.value) return;
  config.value.responsive = normalizeResponsiveConfig(DEFAULT_RESPONSIVE_CONFIG);
  state.adminDesignConfig = config.value;
  applyDesignCSS();
}

function openMediaCroppingSettings() {
  router.push({ path: "/admin/media/config", hash: "#media-cropping-settings" });
}

const colorLinkSortMode = ref("sectionAlpha");
const DEFAULT_FONT_PREVIEW_SAMPLE = "Hamburgefontsiv 0123456789";
const fontPreviewSample = ref(DEFAULT_FONT_PREVIEW_SAMPLE);
const fontPreviewSampleText = computed(() => {
  const value = String(fontPreviewSample.value ?? "").trim();
  return value || DEFAULT_FONT_PREVIEW_SAMPLE;
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

const DEFAULT_DESIGN_PANEL_SECTION_ORDER = ["header", "layout", "sections", "colors", "buttons", "fonts", "versions", "customCss"];

function reorderKnownItems(items, preferred) {
  if (!Array.isArray(items)) return [...preferred];
  const preferredSet = new Set(preferred);
  const seen = new Set();
  const current = items.filter((item) => typeof item === "string");
  const currentSet = new Set(current);
  const ordered = [];
  for (const item of preferred) {
    if (!currentSet.has(item) || seen.has(item)) continue;
    seen.add(item);
    ordered.push(item);
  }
  for (const item of current) {
    if (preferredSet.has(item) || seen.has(item)) continue;
    seen.add(item);
    ordered.push(item);
  }
  return ordered;
}

function normalizeDesignPanelSectionOrder(targetConfig) {
  if (!targetConfig || typeof targetConfig !== "object") return;
  targetConfig.sectionOrder = reorderKnownItems(targetConfig.sectionOrder, DEFAULT_DESIGN_PANEL_SECTION_ORDER);
}

// Param filters state
const paramFilters = reactive({
  name: "",
  subsection: "",
  type: "",
  visible: "",
  favorite: "",
});

// Collapsed param sections state
const collapsedParamSections = reactive({});

// Get all unique param types from config
const availableParamTypes = computed(() => {
  if (!config.value?.parameters) return [];
  const types = new Set();
  Object.values(config.value.parameters).forEach(p => {
    if (p.type) types.add(p.type);
  });
  return Array.from(types).sort();
});

// Check if any filter is active
const hasActiveFilters = computed(() => {
  return paramFilters.name || paramFilters.subsection || paramFilters.type || paramFilters.visible || paramFilters.favorite;
});

// Reset all filters
function resetParamFilters() {
  paramFilters.name = "";
  paramFilters.subsection = "";
  paramFilters.type = "";
  paramFilters.visible = "";
  paramFilters.favorite = "";
}

// Toggle section collapse
function toggleParamSectionCollapse(sectionKey) {
  collapsedParamSections[sectionKey] = !collapsedParamSections[sectionKey];
}

// Filtered params by section (applies filters)
const filteredParamsBySection = computed(() => {
  if (!config.value) return {};
  const result = {};
  const paramOrder = config.value.paramOrder || {};
  
  for (const sKey of config.value.sectionOrder) {
    let params;
    if (paramOrder[sKey]) {
      params = paramOrder[sKey].filter(pKey => config.value.parameters[pKey]);
    } else {
      params = Object.keys(config.value.parameters).filter(
        (pKey) => config.value.parameters[pKey].section === sKey
      );
    }
    
    // Apply filters
    result[sKey] = params.filter(pKey => {
      const param = config.value.parameters[pKey];
      if (!param) return false;
      
      // Name filter (matches label or key)
      if (paramFilters.name) {
        const searchTerm = paramFilters.name.toLowerCase();
        const label = (param.label || "").toLowerCase();
        const key = pKey.toLowerCase();
        if (!label.includes(searchTerm) && !key.includes(searchTerm)) {
          return false;
        }
      }
      
      // Subsection filter
      if (paramFilters.subsection) {
        const searchTerm = paramFilters.subsection.toLowerCase();
        const subsection = (param.subsection || "").toLowerCase();
        if (!subsection.includes(searchTerm)) {
          return false;
        }
      }
      
      // Type filter
      if (paramFilters.type && param.type !== paramFilters.type) {
        return false;
      }
      
      // Visible filter
      if (paramFilters.visible === "true" && !param.visible) {
        return false;
      }
      if (paramFilters.visible === "false" && param.visible) {
        return false;
      }
      
      // Favorite filter
      if (paramFilters.favorite === "true" && !param.favorite) {
        return false;
      }
      if (paramFilters.favorite === "false" && param.favorite) {
        return false;
      }
      
      return true;
    });
  }
  return result;
});

function isSectionHidden(sectionKey) {
  if (!config.value?.hiddenSections) return false;
  return config.value.hiddenSections.includes(sectionKey);
}

function toggleSectionVisibility(sectionKey) {
  if (!config.value) return;
  if (!config.value.hiddenSections) {
    config.value.hiddenSections = [];
  }
  const idx = config.value.hiddenSections.indexOf(sectionKey);
  if (idx >= 0) {
    config.value.hiddenSections.splice(idx, 1);
  } else {
    config.value.hiddenSections.push(sectionKey);
  }
  // Update state immediately for DesignPanel reactivity
  state.adminDesignConfig = config.value;
}

const paramsBySection = computed(() => {
  if (!config.value) return {};
  const result = {};
  const paramOrder = config.value.paramOrder || {};
  for (const sKey of config.value.sectionOrder) {
    if (paramOrder[sKey]) {
      // Use explicit ordering from paramOrder, filter to params that actually exist
      result[sKey] = paramOrder[sKey].filter(pKey => config.value.parameters[pKey]);
    } else {
      // Fallback: filter params by section
      result[sKey] = Object.keys(config.value.parameters).filter(
        (pKey) => config.value.parameters[pKey].section === sKey
      );
    }
  }
  return result;
});

const linkableColorParams = computed(() => {
  if (!config.value) return [];
  return Object.entries(config.value.parameters)
    .filter(([, p]) => p.type === "color" && !p.isBase && p.linkable !== false)
    .map(([key, p]) => {
      const assignedColorRaw = resolveAssignedColorValue(key, p);
      const variation = getColorVariationValue(key);
      const assignedColor = applyColorVariation(assignedColorRaw, variation);
      const linkedBaseKey = config.value?.colorLinks?.[key] || "";
      const linkedBaseLabel = linkedBaseKey
        ? (config.value?.parameters?.[linkedBaseKey]?.label || PARAM_CONFIGS[linkedBaseKey]?.label || linkedBaseKey)
        : "None (manual)";
      return {
        key,
        label: p.label || key,
        section: p.section || "",
        subsection: p.subsection || "",
        contextLabel: formatParamContextLabel(p),
        linkedBaseKey,
        linkedBaseLabel,
        assignedColor,
        assignedColorLabel: assignedColor ? String(assignedColor) : "Not set",
        hasAssignedColor: Boolean(assignedColor),
      };
    });
});

const adminUiEditorColorParams = computed(() => {
  if (!config.value?.parameters) return [];
  return ADMIN_UI_COLOR_KEYS
    .map((key) => {
      const param = config.value.parameters[key] || PARAM_CONFIGS[key];
      if (!param || param.type !== "color") return null;
      const currentColor = resolveAssignedColorValue(key, param);
      const defaultColor = param.default ?? PARAM_CONFIGS[key]?.default ?? null;
      return {
        key,
        label: param.label || PARAM_CONFIGS[key]?.label || key,
        currentColor,
        currentColorLabel: currentColor || "Not set",
        defaultColor,
      };
    })
    .filter(Boolean);
});

function compareAlpha(a, b) {
  return String(a || "").localeCompare(String(b || ""), undefined, { sensitivity: "base" });
}

const groupedLinkableColorParams = computed(() => {
  const items = [...linkableColorParams.value];
  if (!items.length) return [];

  if (colorLinkSortMode.value === "baseReference") {
    const groupsByKey = new Map();
    for (const item of items) {
      const groupKey = item.linkedBaseKey || "__manual__";
      if (!groupsByKey.has(groupKey)) {
        const label = groupKey === "__manual__" ? "None (manual)" : `Base: ${item.linkedBaseLabel}`;
        groupsByKey.set(groupKey, { key: groupKey, label, items: [] });
      }
      groupsByKey.get(groupKey).items.push(item);
    }

    const orderedKeys = ["__manual__", ...baseColorOptions.value.map((base) => base.key)];
    for (const key of groupsByKey.keys()) {
      if (!orderedKeys.includes(key)) orderedKeys.push(key);
    }

    return orderedKeys
      .filter((key) => groupsByKey.has(key))
      .map((key) => {
        const group = groupsByKey.get(key);
        group.items.sort((a, b) => compareAlpha(a.label, b.label));
        return group;
      });
  }

  const sectionOrder = Array.isArray(config.value?.sectionOrder) ? config.value.sectionOrder : [];
  const sectionIndex = new Map(sectionOrder.map((section, idx) => [section, idx]));
  const groupsByKey = new Map();
  for (const item of items) {
    const groupKey = `${item.section}::${item.subsection}`;
    if (!groupsByKey.has(groupKey)) {
      groupsByKey.set(groupKey, {
        key: groupKey,
        label: item.contextLabel,
        section: item.section,
        subsection: item.subsection,
        items: [],
      });
    }
    groupsByKey.get(groupKey).items.push(item);
  }

  const groups = Array.from(groupsByKey.values());
  groups.sort((a, b) => {
    const aSectionIndex = sectionIndex.has(a.section) ? sectionIndex.get(a.section) : Number.MAX_SAFE_INTEGER;
    const bSectionIndex = sectionIndex.has(b.section) ? sectionIndex.get(b.section) : Number.MAX_SAFE_INTEGER;
    if (aSectionIndex !== bSectionIndex) return aSectionIndex - bSectionIndex;
    if (a.section !== b.section) return compareAlpha(a.section, b.section);
    return compareAlpha(a.subsection, b.subsection);
  });
  for (const group of groups) {
    group.items.sort((a, b) => compareAlpha(a.label, b.label));
  }
  return groups;
});

const editableBaseColorParams = computed(() => {
  if (!config.value?.parameters) return [];
  const baseColorEntries = Object.entries(config.value.parameters)
    .filter(([, p]) => p.type === "color" && p.isBase);

  return Object.entries(config.value.parameters)
    .filter(([, p]) => p.type === "color" && p.isBase)
    .map(([key, p]) => {
      const currentColor = resolveAssignedColorValue(key, p);
      const specificContrast = getBaseSpecificHighContrastEntry(config.value, key);
      const linkedBaseKey = specificContrast?.mode === "baseLink" ? specificContrast.linkedBaseColor : null;
      const linkedBaseLabel = linkedBaseKey
        ? (config.value.parameters?.[linkedBaseKey]?.label || PARAM_CONFIGS[linkedBaseKey]?.label || linkedBaseKey)
        : null;
      const linkedContrastPreview = linkedBaseKey
        ? resolveAssignedColorValue(
            linkedBaseKey,
            config.value.parameters?.[linkedBaseKey] || PARAM_CONFIGS[linkedBaseKey] || {}
          )
        : null;
      const autoContrastPreview = getAutoHighContrastColor(state.design, currentColor || p.default || null);
      const contrastMode = specificContrast?.mode || "auto";
      const specificContrastColor = contrastMode === "custom" ? specificContrast?.color || null : null;
      let contrastDisplayLabel = `Auto (${autoContrastPreview})`;
      if (contrastMode === "custom" && specificContrastColor) {
        contrastDisplayLabel = specificContrastColor;
      } else if (contrastMode === "baseLink" && linkedBaseLabel) {
        contrastDisplayLabel = `${linkedContrastPreview || "Not set"}`;
      }

      return {
        key,
        label: p.label || key,
        defaultLabel: PARAM_CONFIGS[key]?.label || key,
        isCustom: !DEFAULT_BASE_COLOR_KEYS.includes(key),
        currentColor,
        currentColorLabel: currentColor || "Not set",
        autoContrastPreview,
        specificContrastColor,
        hasSpecificContrast: contrastMode !== "auto",
        contrastMode,
        linkedBaseKey,
        linkedBaseLabel,
        linkedContrastPreview,
        contrastDisplayLabel,
        contrastLinkTargets: baseColorEntries
          .filter(([targetKey]) => targetKey !== key)
          .map(([targetKey, targetParam]) => ({
            key: targetKey,
            label: targetParam?.label || targetKey,
          })),
        specificContrastStale: isSpecificHighContrastStale(config.value, state.design, key),
      };
    });
});

const baseColorOptions = computed(() => {
  return editableBaseColorParams.value.map((base) => ({
    key: base.key,
    label: base.label,
  }));
});

function formatParamContextLabel(param) {
  const section = sectionLabels[param?.section] || param?.section || "General";
  if (param?.subsection) return `${section} / ${param.subsection}`;
  return section;
}

function resolveAssignedColorValue(paramKey, paramConfig) {
  const currentLink = config.value?.colorLinks?.[paramKey];
  if (currentLink) {
    const linkedValue = state.design?.[currentLink] ?? config.value?.parameters?.[currentLink]?.default;
    if (linkedValue !== undefined && linkedValue !== null && String(linkedValue).trim() !== "") {
      return String(linkedValue).trim();
    }
  }

  const currentValue = state.design?.[paramKey];
  if (currentValue !== undefined && currentValue !== null && String(currentValue).trim() !== "") {
    return String(currentValue).trim();
  }

  const defaultValue = paramConfig?.default;
  if (defaultValue !== undefined && defaultValue !== null && String(defaultValue).trim() !== "") {
    return String(defaultValue).trim();
  }

  return null;
}

function getColorPreviewStyle(colorValue) {
  if (!colorValue) {
    return {
      background:
        "repeating-linear-gradient(45deg, #e2e8f0 0, #e2e8f0 6px, #f8fafc 6px, #f8fafc 12px)",
    };
  }
  return { background: colorValue };
}

function toColorInputValue(colorValue, fallback = "#0b1220") {
  if (typeof colorValue !== "string") return fallback;
  const raw = colorValue.trim();
  if (/^#[0-9a-fA-F]{6}$/.test(raw)) return raw;
  if (/^#[0-9a-fA-F]{3}$/.test(raw)) {
    return `#${raw
      .slice(1)
      .split("")
      .map((c) => c + c)
      .join("")}`;
  }
  return fallback;
}

function ensureBaseHighContrastMap() {
  if (!config.value.baseColorHighContrast || typeof config.value.baseColorHighContrast !== "object") {
    config.value.baseColorHighContrast = {};
  }
  return config.value.baseColorHighContrast;
}

function syncCustomBaseColorsToRuntime() {
  if (!config.value?.parameters) return;
  for (const [key, param] of Object.entries(config.value.parameters)) {
    if (DEFAULT_BASE_COLOR_KEYS.includes(key)) continue;
    if (param?.type !== "color" || !param?.isBase) continue;
    const next = typeof param.default === "string" ? param.default.trim() : "";
    if (next) state.design[key] = next;
  }
}

function makeCustomBaseColorKey() {
  if (!config.value?.parameters) return `${CUSTOM_BASE_COLOR_PREFIX}1`;
  const used = new Set(Object.keys(config.value.parameters));
  let idx = 1;
  let candidate = `${CUSTOM_BASE_COLOR_PREFIX}${idx}`;
  while (used.has(candidate)) {
    idx += 1;
    candidate = `${CUSTOM_BASE_COLOR_PREFIX}${idx}`;
  }
  return candidate;
}

function normalizeBaseColorSubsections(targetConfig) {
  const params = targetConfig?.parameters;
  if (!params || typeof params !== "object") return;
  for (const param of Object.values(params)) {
    if (param?.type !== "color" || !param?.isBase) continue;
    if (param.subsection !== BASE_VARS_SUBSECTION) {
      param.subsection = BASE_VARS_SUBSECTION;
    }
  }
}

function normalizeTypographySubsections(targetConfig) {
  const params = targetConfig?.parameters;
  if (!params || typeof params !== "object") return;

  const setDefaultSubsection = (key, subsection, legacyValues) => {
    const param = params[key];
    if (!param || typeof param !== "object") return;
    const current = param.subsection ?? null;
    if (current === subsection || legacyValues.includes(current)) {
      param.subsection = subsection;
    }
  };

  for (const key of ["headerFontFamily", "headerTextDecoration", "headingLinearScaling"]) {
    setDefaultSubsection(key, "Headings", [null, "", "Headings (h1 – h6)"]);
  }
  for (const key of ["bodyFontFamily", "bodyFontWeight", "bodyLetterSpacing", "bodyLineHeight"]) {
    setDefaultSubsection(key, "Paragraph", [null, "", "Body Text", "Typography"]);
  }
  for (const key of ["heroTitleColor", "heroSubtitleColor"]) {
    setDefaultSubsection(key, "Header Titles", [null, "", "text header", "Text Header", "Header Text", "Hero Titles"]);
  }
  for (const key of ["sidebarBgColor", "sidebarItemColor", "sidebarItemHoverColor"]) {
    setDefaultSubsection(key, "Menus", [null, "", "Sidebar"]);
  }
  for (const key of ["hardBoxShadowEnabled", "hardBoxShadowOffsetSource", "hardBoxShadowOffsetCustom", "hardBoxShadowBrightness"]) {
    setDefaultSubsection(key, "Hardbox Shadow", [null, "", "Hard Box-Shadow"]);
  }
}

function addCustomBaseColor() {
  if (!config.value?.parameters) return;
  const key = makeCustomBaseColorKey();
  if (!config.value.paramOrder || typeof config.value.paramOrder !== "object") {
    config.value.paramOrder = {};
  }
  if (!Array.isArray(config.value.paramOrder.colors)) {
    config.value.paramOrder.colors = [];
  }

  config.value.parameters[key] = {
    visible: true,
    favorite: false,
    section: "colors",
    type: "color",
    label: `Custom Base ${editableBaseColorParams.value.filter((base) => base.isCustom).length + 1}`,
    isBase: true,
    default: "#94a3b8",
    subsection: BASE_VARS_SUBSECTION,
  };
  if (!config.value.paramOrder.colors.includes(key)) {
    config.value.paramOrder.colors.push(key);
  }
  state.design[key] = "#94a3b8";
}

function scheduleBaseColorDesignSave() {
  if (baseColorSaveTimeout) clearTimeout(baseColorSaveTimeout);
  baseColorSaveTimeout = setTimeout(async () => {
    try {
      await saveDesignSettings();
    } catch (err) {
      console.error("Failed to save base color value:", err);
    }
  }, 350);
}

function setBaseColorValue(baseKey, colorValue) {
  const param = config.value?.parameters?.[baseKey];
  if (!param || !param.isBase || param.type !== "color") return;
  const fallback = toColorInputValue(resolveAssignedColorValue(baseKey, param), "#94a3b8");
  const normalized = toColorInputValue(colorValue, fallback);
  param.default = normalized;
  if (DEFAULT_BASE_COLOR_KEYS.includes(baseKey)) {
    updateDesignSetting(baseKey, normalized);
    scheduleBaseColorDesignSave();
    return;
  }
  state.design[baseKey] = normalized;
}

function removeCustomBaseColor(baseKey) {
  if (!baseKey || DEFAULT_BASE_COLOR_KEYS.includes(baseKey)) return;
  if (!config.value?.parameters?.[baseKey]) return;

  delete config.value.parameters[baseKey];

  const colorOrder = config.value?.paramOrder?.colors;
  if (Array.isArray(colorOrder)) {
    config.value.paramOrder.colors = colorOrder.filter((key) => key !== baseKey);
  }

  if (config.value?.colorLinks && typeof config.value.colorLinks === "object") {
    for (const [paramKey, linkedBase] of Object.entries(config.value.colorLinks)) {
      if (linkedBase === baseKey) delete config.value.colorLinks[paramKey];
    }
  }

  if (config.value?.colorVariations && typeof config.value.colorVariations === "object") {
    delete config.value.colorVariations[baseKey];
  }

  if (config.value?.baseColorHighContrast && typeof config.value.baseColorHighContrast === "object") {
    delete config.value.baseColorHighContrast[baseKey];
    for (const [base, entry] of Object.entries(config.value.baseColorHighContrast)) {
      if (entry?.mode === "baseLink" && entry?.linkedBaseColor === baseKey) {
        delete config.value.baseColorHighContrast[base];
      }
    }
  }

  delete state.design[baseKey];
}

function ensureColorVariationMap() {
  if (!config.value.colorVariations || typeof config.value.colorVariations !== "object") {
    config.value.colorVariations = {};
  }
  return config.value.colorVariations;
}

function getColorVariationValue(paramKey) {
  const map = config.value?.colorVariations;
  if (!map || typeof map !== "object") return DEFAULT_COLOR_VARIATION;
  return normalizeColorVariation(map[paramKey]);
}

function setColorVariation(paramKey, variationValue) {
  if (!paramKey) return;
  const map = ensureColorVariationMap();
  const normalized = normalizeColorVariation(variationValue);
  if (normalized === DEFAULT_COLOR_VARIATION) {
    delete map[paramKey];
  } else {
    map[paramKey] = normalized;
  }
}

function setBaseSpecificContrast(baseKey, colorValue) {
  if (!config.value?.parameters?.[baseKey]) return;
  const map = ensureBaseHighContrastMap();
  const color = toColorInputValue(colorValue);
  const sourceBaseColor = resolveAssignedColorValue(baseKey, config.value.parameters[baseKey]);
  map[baseKey] = {
    mode: "custom",
    color,
    sourceBaseColor: sourceBaseColor || null,
  };
}

function clearBaseSpecificContrast(baseKey) {
  if (!config.value?.baseColorHighContrast || typeof config.value.baseColorHighContrast !== "object") return;
  delete config.value.baseColorHighContrast[baseKey];
}

function getBaseContrastSourceValue(base) {
  if (!base) return "auto";
  if (base.contrastMode === "baseLink" && base.linkedBaseKey) return `link:${base.linkedBaseKey}`;
  if (base.contrastMode === "custom") return "custom";
  return "auto";
}

function setBaseContrastSource(baseKey, sourceValue) {
  if (!config.value?.parameters?.[baseKey]) return;
  if (!sourceValue || sourceValue === "auto") {
    clearBaseSpecificContrast(baseKey);
    return;
  }

  const map = ensureBaseHighContrastMap();

  if (sourceValue === "custom") {
    const existing = getBaseSpecificHighContrastEntry(config.value, baseKey);
    const fallbackColor = existing?.mode === "custom" && existing?.color
      ? existing.color
      : getAutoHighContrastColor(
          state.design,
          resolveAssignedColorValue(baseKey, config.value.parameters[baseKey])
        );
    const sourceBaseColor = resolveAssignedColorValue(baseKey, config.value.parameters[baseKey]);
    map[baseKey] = {
      mode: "custom",
      color: toColorInputValue(fallbackColor),
      sourceBaseColor: sourceBaseColor || null,
    };
    return;
  }

  if (sourceValue.startsWith("link:")) {
    const linkedBaseColor = sourceValue.slice("link:".length);
    if (!linkedBaseColor || linkedBaseColor === baseKey) {
      clearBaseSpecificContrast(baseKey);
      return;
    }
    map[baseKey] = {
      mode: "baseLink",
      linkedBaseColor,
    };
  }
}

function setFallbackHighContrast(paramKey, colorValue) {
  const fallback = paramKey === "highContrastLight" ? "#f8fafc" : "#0b1220";
  const normalized = toColorInputValue(colorValue, fallback);
  updateDesignSetting(paramKey, normalized);
  if (fallbackContrastSaveTimeout) clearTimeout(fallbackContrastSaveTimeout);
  fallbackContrastSaveTimeout = setTimeout(async () => {
    try {
      await saveDesignSettings();
    } catch (err) {
      console.error("Failed to save fallback high contrast color:", err);
    }
  }, 350);
}

function scheduleAdminUiColorSave() {
  if (adminUiColorSaveTimeout) clearTimeout(adminUiColorSaveTimeout);
  adminUiColorSaveTimeout = setTimeout(async () => {
    try {
      await saveDesignSettings();
    } catch (err) {
      console.error("Failed to save admin UI color:", err);
    }
  }, 350);
}

function setAdminUiColorValue(paramKey, colorValue) {
  if (!ADMIN_UI_COLOR_KEYS.includes(paramKey)) return;
  const param = config.value?.parameters?.[paramKey] || PARAM_CONFIGS[paramKey];
  if (!param || param.type !== "color") return;
  const fallback = toColorInputValue(resolveAssignedColorValue(paramKey, param), "#4f46e5");
  const normalized = toColorInputValue(colorValue, fallback);
  updateDesignSetting(paramKey, normalized);
  scheduleAdminUiColorSave();
}

const DEFAULT_CONSTANT_SECTION_OVERRIDE_PARAMS = [
  "hideSectionHeader",
  "hideSectionDescription",
  "removeSectionPadding",
  "removeSectionBackground",
  "hideSectionIfListEmptyPublic",
];

const constantSectionOverrideParams = [
  { key: "hideSectionHeader", label: "Hide section header" },
  { key: "hideSectionDescription", label: "Hide section description" },
  { key: "removeSectionPadding", label: "Remove section padding" },
  { key: "removeSectionBackground", label: "Remove section background" },
  { key: "hideSectionIfListEmptyPublic", label: "Hide in public when list is empty" },
];

const BACKGROUND_PATTERN_PARAM_KEYS = [
  "sectionBgPattern",
  "sectionBgOpacity1",
  "sectionBgOpacity2",
  "sectionBgColor1",
  "sectionBgColor2",
];
const BACKGROUND_PATTERN_SUBSECTION = "Background Pattern";

function toCamelCaseParamKey(rawKey) {
  return String(rawKey || "").replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function getCanonicalOverrideParamKey(rawKey) {
  return toCamelCaseParamKey(rawKey);
}

function resolveOverrideParamConfig(paramKey) {
  const canonical = getCanonicalOverrideParamKey(paramKey);
  return (
    config.value?.parameters?.[paramKey]
    || config.value?.parameters?.[canonical]
    || PARAM_CONFIGS[paramKey]
    || PARAM_CONFIGS[canonical]
    || null
  );
}

const SHARED_OVERRIDE_MIGRATED_TO_CONSTANTS = new Set([
  "sectionPadding",
  "sectionBackgroundColor",
]);

const SHARED_OVERRIDE_PARAM_KEYS = Array.from(new Set([
  ...OVERRIDABLE_PARAMS,
  "hardBoxShadowMode",
  "headerColor",
  "headerFontFamily",
  "headerFontWeight",
  "h1FontSize",
  "h1LetterSpacing",
  "h1LineHeight",
  "h2FontSize",
  "h2LetterSpacing",
  "h2LineHeight",
  "h3FontSize",
  "h3LetterSpacing",
  "h3LineHeight",
  "h4FontSize",
  "h4LetterSpacing",
  "h4LineHeight",
  "textColor",
  "textFontFamily",
  "textFontSize",
  "textFontWeight",
])).filter((paramKey) => !SHARED_OVERRIDE_MIGRATED_TO_CONSTANTS.has(getCanonicalOverrideParamKey(paramKey)));

const HEADER_OVERRIDE_PARAM_KEYS = [
  "headerInner",
  "heroContentAlign",
  "heroSeparator",
  "heroParallax",
  "heroOverlayParallax",
  "heroOverlayParallaxDirection",
  "heroTitleFontSize",
  "heroTitleLineHeight",
  "heroTitleLetterSpacing",
  "heroTitleColor",
  "heroSubtitleFontSize",
  "heroSubtitleLineHeight",
  "heroSubtitleLetterSpacing",
  "heroSubtitleColor",
  "heroOverlayPosition",
  "heroOverlaySize",
];

function getOverrideParamGroupLabel(paramKey) {
  const cfg = resolveOverrideParamConfig(paramKey);
  const section = cfg?.section || "";
  const subsection = cfg?.subsection || "";
  const sectionLabel = sectionLabels[section] || section || "General";
  return subsection ? `${sectionLabel} / ${subsection}` : sectionLabel;
}

function buildOverrideParamGroups(paramKeys) {
  const grouped = new Map();
  for (const paramKey of paramKeys) {
    const groupLabel = getOverrideParamGroupLabel(paramKey);
    if (!grouped.has(groupLabel)) {
      grouped.set(groupLabel, { key: groupLabel, label: groupLabel, params: [] });
    }
    grouped.get(groupLabel).params.push(paramKey);
  }
  return Array.from(grouped.values());
}

const overrideParamsByGroup = computed(() => buildOverrideParamGroups(SHARED_OVERRIDE_PARAM_KEYS));
const headerOverrideParamsByGroup = computed(() => buildOverrideParamGroups(HEADER_OVERRIDE_PARAM_KEYS));

const overrideParamLabels = {
  hideSectionHeader: "Hide Section Header",
  hideSectionDescription: "Hide Section Description",
  removeSectionPadding: "Remove Section Padding",
  removeSectionBackground: "Remove Section Background",
  hideSectionIfListEmptyPublic: "Hide In Public When List Is Empty",
  sectionBackgroundColor: "Background Color",
  sectionBorderRadius: "Border Radius",
  sectionBorderWidth: "Border Width",
  sectionBorderColor: "Border Color",
  sectionBorderStyle: "Border Style",
  sectionContentAlign: "Content Align",
  sectionPadding: "Padding",
  sectionBoxShadow: "Box Shadow",
  hardBoxShadowMode: "Hardbox Shadow",
  sectionBgPattern: "Pattern",
  sectionBgOpacity1: "Start Opacity",
  sectionBgOpacity2: "End Opacity",
  sectionBgColor1: "Start Color",
  sectionBgColor2: "End Color",
  headerColor: "Heading Color",
  headerFontFamily: "Heading Font Family",
  headerFontWeight: "Heading Font Weight",
  h1FontSize: "H1 Font Size",
  h1LetterSpacing: "H1 Letter Spacing",
  h1LineHeight: "H1 Line Height",
  h2FontSize: "H2 Font Size",
  h2LetterSpacing: "H2 Letter Spacing",
  h2LineHeight: "H2 Line Height",
  h3FontSize: "H3 Font Size",
  h3LetterSpacing: "H3 Letter Spacing",
  h3LineHeight: "H3 Line Height",
  h4FontSize: "H4 Font Size",
  h4LetterSpacing: "H4 Letter Spacing",
  h4LineHeight: "H4 Line Height",
  textColor: "Text Color",
  textFontFamily: "Text Font Family",
  textFontSize: "Text Font Size",
  textFontWeight: "Text Font Weight",
  customCss: "Custom CSS",
  checkerColor1: "Checker Color 1",
  checkerColor2: "Checker Color 2",
  topbarBgColor: "Topbar Background",
  headerInner: "Header Inner",
  heroContentAlign: "Content Alignment",
  heroSeparator: "Bottom Separator",
  heroParallax: "Parallax Background",
  heroOverlayParallax: "Parallax Overlay",
  heroOverlayParallaxDirection: "Overlay Direction",
  heroTitleFontSize: "Title: Font Size",
  heroTitleLineHeight: "Title: Line Height",
  heroTitleLetterSpacing: "Title: Letter Spacing",
  heroTitleColor: "Title: Color",
  heroSubtitleFontSize: "Subtitle: Font Size",
  heroSubtitleLineHeight: "Subtitle: Line Height",
  heroSubtitleLetterSpacing: "Subtitle: Letter Spacing",
  heroSubtitleColor: "Subtitle: Color",
  heroOverlayPosition: "Overlay: Position",
  heroOverlaySize: "Overlay: Size",
  buttonBorderRadius: "Button: Border Radius",
  buttonBorderWidth: "Button: Border Width",
  buttonBorderColor: "Button: Border Color",
  buttonBgColor: "Button: Background",
  buttonColor: "Button: Text Color",
  buttonHoverBorderColor: "Button: Hover Border Color",
  buttonHoverBgColor: "Button: Hover Background",
  buttonHoverColor: "Button: Hover Text Color",
  buttonFontSize: "Button: Font Size",
  buttonPaddingX: "Button: Horizontal Padding",
  buttonPaddingY: "Button: Vertical Padding",
};

function getOverrideParamLabel(paramKey) {
  return resolveOverrideParamConfig(paramKey)?.label || overrideParamLabels[paramKey] || paramKey;
}

const allSectionSpecificParams = {
  tiles: ["checkerColor1", "checkerColor2"],
  video: [],
  text: [],
  text_image: [],
  faq: [],
  links: [],
  blog: [],
};

function toggleOverrideParam(group, param, checked) {
  if (!config.value?.sectionOverrideParams) return;
  if (group === "generic" || group === "header" || group === "constants") {
    const arr = config.value.sectionOverrideParams[group] || [];
    if (checked && !arr.includes(param)) arr.push(param);
    else if (!checked) {
      const idx = arr.indexOf(param);
      if (idx >= 0) arr.splice(idx, 1);
    }
    config.value.sectionOverrideParams[group] = arr;
  } else {
    const byType = config.value.sectionOverrideParams.byType || {};
    const arr = byType[group] || [];
    if (checked && !arr.includes(param)) arr.push(param);
    else if (!checked) {
      const idx = arr.indexOf(param);
      if (idx >= 0) arr.splice(idx, 1);
    }
    byType[group] = arr;
    config.value.sectionOverrideParams.byType = byType;
  }

  // Persist override checkbox changes immediately so quick page refreshes
  // do not lose updates before the debounced autosave runs.
  if (saveTimeout) clearTimeout(saveTimeout);
  void autoSave();
}

function normalizeSectionOverrideParams(loaded) {
  if (!loaded.sectionOverrideParams || typeof loaded.sectionOverrideParams !== "object") {
    loaded.sectionOverrideParams = {};
  }
  const params = loaded.sectionOverrideParams;

  if (!Array.isArray(params.header)) params.header = [];
  for (const paramKey of HEADER_OVERRIDE_PARAM_KEYS) {
    if (!params.header.includes(paramKey)) params.header.push(paramKey);
  }
  if (!Array.isArray(params.generic)) params.generic = [];
  const hasStoredConstants = Array.isArray(params.constants);
  if (!hasStoredConstants) params.constants = [...DEFAULT_CONSTANT_SECTION_OVERRIDE_PARAMS];
  if (!params.byType || typeof params.byType !== "object") params.byType = {};

  const constants = new Set(params.constants);
  for (const defaultConstant of DEFAULT_CONSTANT_SECTION_OVERRIDE_PARAMS) {
    constants.add(defaultConstant);
  }
  params.constants = Array.from(constants);
  if (Array.isArray(params.byType?.video)) {
    params.byType.video = params.byType.video.filter((key) => key !== "tvColor");
  }
}

function normalizeBackgroundPatternPlacement(targetConfig) {
  if (!targetConfig || typeof targetConfig !== "object") return;

  if (!targetConfig.paramOrder || typeof targetConfig.paramOrder !== "object") {
    targetConfig.paramOrder = {};
  }

  const paramOrder = targetConfig.paramOrder;
  let sectionsOrder = Array.isArray(paramOrder.sections) ? [...paramOrder.sections] : [];

  for (const [sectionKey, order] of Object.entries(paramOrder)) {
    if (!Array.isArray(order) || sectionKey === "sections") continue;
    paramOrder[sectionKey] = order.filter((paramKey) => !BACKGROUND_PATTERN_PARAM_KEYS.includes(paramKey));
  }

  // Remove duplicates while preserving order.
  const deduped = [];
  const seen = new Set();
  for (const paramKey of sectionsOrder) {
    if (seen.has(paramKey)) continue;
    seen.add(paramKey);
    deduped.push(paramKey);
  }
  sectionsOrder = deduped;

  const existingPatternOrder = sectionsOrder.filter((paramKey) => BACKGROUND_PATTERN_PARAM_KEYS.includes(paramKey));
  if (existingPatternOrder.length > 0) {
    // Preserve user-defined order and append only missing keys.
    const missing = BACKGROUND_PATTERN_PARAM_KEYS.filter((paramKey) => !existingPatternOrder.includes(paramKey));
    sectionsOrder.push(...missing);
  } else {
    const paramsToInsert = BACKGROUND_PATTERN_PARAM_KEYS;
    const insertAt = sectionsOrder.indexOf("sectionBorderWidth");
    if (insertAt >= 0) {
      sectionsOrder.splice(insertAt, 0, ...paramsToInsert);
    } else {
      sectionsOrder.push(...paramsToInsert);
    }
  }
  paramOrder.sections = sectionsOrder;

  if (targetConfig.parameters && typeof targetConfig.parameters === "object") {
    for (const paramKey of BACKGROUND_PATTERN_PARAM_KEYS) {
      const param = targetConfig.parameters[paramKey];
      if (!param || typeof param !== "object") continue;
      param.section = "sections";
      param.subsection = BACKGROUND_PATTERN_SUBSECTION;
    }
  }
}

const FONT_FALLBACK_OPTIONS = new Set(["serif", "sans-serif"]);
const FONT_HEALTH_GENERIC_FAMILIES = new Set([
  "serif",
  "sans-serif",
  "monospace",
  "cursive",
  "fantasy",
  "system-ui",
  "ui-serif",
  "ui-sans-serif",
  "ui-monospace",
  "ui-rounded",
  "emoji",
  "math",
  "fangsong",
]);
const FONT_HEALTH_LOCAL_FAMILIES = new Set([
  "-apple-system",
  "blinkmacsystemfont",
  "segoe ui",
  "arial",
  "helvetica",
  "helvetica neue",
  "times new roman",
  "georgia",
  "courier new",
  "menlo",
  "monaco",
  "consolas",
  "tahoma",
  "verdana",
]);
const FONT_HEALTH_SAMPLE_TEXT = "Hamburgefontsiv 0123456789";
const FONT_CACHE_CANONICAL_WEIGHTS = Object.freeze([100, 200, 300, 400, 500, 600, 700, 800, 900]);
const FONT_CACHE_URL_PATTERN = /url\((['"]?)([^)"']+)\1\)/gi;
const fontHealthByIndex = reactive({});
let fontHealthCanvas = null;
const fontHealthStylesheetLoadPromises = new Map();

function splitFontFamilyList(value) {
  const source = String(value || "").trim();
  if (!source) return [];
  const result = [];
  let current = "";
  let quote = null;
  for (const ch of source) {
    if (quote) {
      if (ch === quote) quote = null;
      current += ch;
      continue;
    }
    if (ch === '"' || ch === "'") {
      quote = ch;
      current += ch;
      continue;
    }
    if (ch === ",") {
      const trimmed = current.trim();
      if (trimmed) result.push(trimmed);
      current = "";
      continue;
    }
    current += ch;
  }
  const tail = current.trim();
  if (tail) result.push(tail);
  return result;
}

function unwrapQuotedFontFamily(token) {
  const raw = String(token || "").trim();
  if (!raw) return "";
  const first = raw[0];
  const last = raw[raw.length - 1];
  if ((first === '"' || first === "'") && last === first && raw.length >= 2) {
    return raw.slice(1, -1).trim();
  }
  return raw;
}

function getPrimaryFontFamilyName(cssValue) {
  const [first] = splitFontFamilyList(cssValue);
  return unwrapQuotedFontFamily(first);
}

function normalizeFontFallback(value) {
  return FONT_FALLBACK_OPTIONS.has(value) ? value : "sans-serif";
}

function normalizeGoogleFontFamilyName(value) {
  let normalized = unwrapQuotedFontFamily(value);
  if (!normalized) return "";

  const familyFromUrl = normalized.match(/[?&]family=([^&]+)/i);
  if (familyFromUrl?.[1]) {
    normalized = familyFromUrl[1];
  }

  try {
    normalized = decodeURIComponent(normalized);
  } catch (err) {
    // Keep raw value if it's not URI-decoded input.
  }

  normalized = normalized.replace(/\+/g, " ").trim();
  const [firstFamily] = splitFontFamilyList(normalized);
  const primary = String(firstFamily || normalized).split(":")[0];
  return unwrapQuotedFontFamily(primary).replace(/\s+/g, " ").trim();
}

function inferFontFallback(cssValue) {
  const lower = String(cssValue || "").toLowerCase();
  if (lower.includes("sans-serif")) return "sans-serif";
  if (lower.includes("serif")) return "serif";
  return "sans-serif";
}

function buildFontFamilyCssValue(fontFamilyName, fallback) {
  const name = String(fontFamilyName || "").trim();
  if (!name) return "";
  const safeFallback = normalizeFontFallback(fallback);
  const escaped = name.replace(/"/g, '\\"');
  const quotedName = /\s/.test(name) ? `"${escaped}"` : escaped;
  return `${quotedName}, ${safeFallback}`;
}

function buildSingleFontFamilyPreviewCss(fontFamilyName, fallback) {
  const primary = String(fontFamilyName || "").trim();
  const safeFallback = normalizeFontFallback(fallback);
  if (!primary) return safeFallback;
  const escaped = primary.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  const quoted = /[\s"',()]/.test(primary) ? `"${escaped}"` : escaped;
  return `${quoted}, ${safeFallback}`;
}

function getFontFamilyPreviewStyle(font) {
  const family = normalizeGoogleFontFamilyName(font?.label);
  const fallback = normalizeFontFallback(font?.fallback);
  return {
    fontFamily: buildSingleFontFamilyPreviewCss(family, fallback),
  };
}

function getFontFallbackPreviewStyle(font) {
  const fallback = normalizeFontFallback(font?.fallback);
  return {
    fontFamily: fallback,
  };
}

function syncFontFamilyEntry(font) {
  if (!font || typeof font !== "object") return;
  font.fallback = normalizeFontFallback(font.fallback);
  font.value = buildFontFamilyCssValue(font.label, font.fallback);
}

function normalizeFontFamilyEntry(font) {
  if (!font || typeof font !== "object") return;
  font.label = normalizeGoogleFontFamilyName(font.label);
  syncFontFamilyEntry(font);
}

function normalizeFontFamilies(targetConfig) {
  if (!targetConfig || typeof targetConfig !== "object") return;
  const source = Array.isArray(targetConfig.fontFamilies) ? targetConfig.fontFamilies : [];
  targetConfig.fontFamilies = source.map((font) => {
    const cssValue = String(font?.value || "");
    const familyFromValue = getPrimaryFontFamilyName(cssValue);
    const familyName = normalizeGoogleFontFamilyName(familyFromValue || font?.label);
    const fallback = normalizeFontFallback(font?.fallback || inferFontFallback(cssValue));
    return {
      ...font,
      label: familyName,
      fallback,
      value: buildFontFamilyCssValue(familyName, fallback),
    };
  });
}

function addFontFamily() {
  if (!config.value) return;
  config.value.fontFamilies.push({ label: "", fallback: "sans-serif", value: "" });
}

function removeFontFamily(index) {
  if (!config.value?.fontFamilies) return;
  config.value.fontFamilies.splice(index, 1);
  resetAllFontHealthStatuses();
}

function onFontFamilyLabelInput(font, index) {
  syncFontFamilyEntry(font);
  clearFontHealthStatus(index);
}

function onFontFamilyLabelBlur(font, index) {
  normalizeFontFamilyEntry(font);
  clearFontHealthStatus(index);
}

function onFontFamilyFallbackChange(font, index) {
  syncFontFamilyEntry(font);
  clearFontHealthStatus(index);
}

function resetAllFontHealthStatuses() {
  for (const key of Object.keys(fontHealthByIndex)) {
    delete fontHealthByIndex[key];
  }
}

function clearFontHealthStatus(index) {
  delete fontHealthByIndex[index];
}

function setFontHealthStatus(index, status, message, extras = {}) {
  const previous = fontHealthByIndex[index] || {};
  fontHealthByIndex[index] = {
    ...previous,
    status,
    message,
    canCacheViaBrowser: false,
    browserProbe: null,
    ...extras,
  };
}

function getFontHealthStatus(index) {
  return fontHealthByIndex[index]?.status || "";
}

function getFontHealthMessage(index) {
  return fontHealthByIndex[index]?.message || "";
}

function getFontHealthCanCacheViaBrowser(index) {
  return Boolean(fontHealthByIndex[index]?.canCacheViaBrowser);
}

function getFontHealthBrowserProbe(index) {
  const probe = fontHealthByIndex[index]?.browserProbe;
  if (!probe || typeof probe !== "object") return null;
  const sourceCssUrl = String(probe.sourceCssUrl || "").trim();
  const cssText = String(probe.cssText || "");
  const sourceUrls = Array.isArray(probe.sourceUrls)
    ? probe.sourceUrls.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
  if (!sourceCssUrl || !cssText.trim() || !sourceUrls.length) return null;
  return { sourceCssUrl, cssText, sourceUrls };
}

function isFontHealthChecking(index) {
  return getFontHealthStatus(index) === "checking";
}

function isFontCacheNowBusy(index) {
  return getFontHealthStatus(index) === "caching";
}

function shouldResolveServerCachedFamily(familyName) {
  const normalized = String(familyName || "").trim().toLowerCase();
  if (!normalized) return false;
  if (FONT_HEALTH_GENERIC_FAMILIES.has(normalized)) return false;
  if (FONT_HEALTH_LOCAL_FAMILIES.has(normalized)) return false;
  return true;
}

function hashString(value) {
  const source = String(value || "");
  let hash = 0;
  for (let i = 0; i < source.length; i += 1) {
    hash = (hash * 31 + source.charCodeAt(i)) | 0;
  }
  return String(Math.abs(hash));
}

function getLocalFontLinkId(url) {
  return `fstvlpress-cached-font-health-${hashString(url)}`;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function waitForStylesheetLoad(link, timeoutMs = 3500) {
  if (!link) return Promise.resolve(false);
  if (link.dataset.loaded === "true") return Promise.resolve(true);
  if (link.sheet) {
    link.dataset.loaded = "true";
    return Promise.resolve(true);
  }
  return new Promise((resolve) => {
    let done = false;
    let timeoutId = null;
    const finish = (loaded) => {
      if (done) return;
      done = true;
      if (timeoutId) clearTimeout(timeoutId);
      link.removeEventListener("load", onLoad);
      link.removeEventListener("error", onError);
      if (loaded) link.dataset.loaded = "true";
      resolve(Boolean(loaded));
    };
    const onLoad = () => finish(true);
    const onError = () => finish(false);

    link.addEventListener("load", onLoad, { once: true });
    link.addEventListener("error", onError, { once: true });
    timeoutId = setTimeout(() => finish(Boolean(link.sheet)), timeoutMs);
  });
}

async function ensureLocalFontStylesheet(url) {
  if (typeof document === "undefined") return false;
  const stylesheetUrl = String(url || "").trim();
  if (!stylesheetUrl) return false;

  const linkId = getLocalFontLinkId(stylesheetUrl);
  const pending = fontHealthStylesheetLoadPromises.get(linkId);
  if (pending) return pending;

  let link = document.getElementById(linkId);
  if (link && link.tagName !== "LINK") {
    link = null;
  }

  if (!link) {
    link = document.createElement("link");
    link.id = linkId;
    link.rel = "stylesheet";
    link.href = stylesheetUrl;
    link.setAttribute("data-fstvlpress-font-cache-health", "true");
    document.head.appendChild(link);
  }

  const loadPromise = waitForStylesheetLoad(link).finally(() => {
    fontHealthStylesheetLoadPromises.delete(linkId);
  });
  fontHealthStylesheetLoadPromises.set(linkId, loadPromise);
  return loadPromise;
}

function toPrimaryFontToken(familyName) {
  const name = String(familyName || "").trim();
  if (!name) return "";
  const escaped = name.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  return /[\s"',()]/.test(name) ? `"${escaped}"` : escaped;
}

function measureFontWidth(fontSpec) {
  if (typeof document === "undefined") return null;
  if (!fontHealthCanvas) {
    fontHealthCanvas = document.createElement("canvas");
  }
  const ctx = fontHealthCanvas.getContext("2d");
  if (!ctx) return null;
  ctx.font = `72px ${fontSpec}`;
  return ctx.measureText(FONT_HEALTH_SAMPLE_TEXT).width;
}

function isPrimaryFontApplied(familyName) {
  const primaryToken = toPrimaryFontToken(familyName);
  if (!primaryToken) return false;

  // Check the primary family only by comparing against fixed generic baselines.
  // If the primary family is missing, widths should match the chosen baseline.
  const baselines = ["monospace", "serif", "sans-serif"];
  for (const baseline of baselines) {
    const withPrimary = measureFontWidth(`${primaryToken}, ${baseline}`);
    const baselineOnly = measureFontWidth(baseline);
    if (withPrimary === null || baselineOnly === null) continue;
    if (Math.abs(withPrimary - baselineOnly) > 0.05) {
      return true;
    }
  }
  return false;
}

async function waitForPrimaryFontApplication(familyName, timeoutMs = 5000) {
  if (isPrimaryFontApplied(familyName)) return true;
  const startedAt = Date.now();
  const primaryToken = toPrimaryFontToken(familyName);
  while (Date.now() - startedAt <= timeoutMs) {
    if (typeof document !== "undefined" && document.fonts && typeof document.fonts.load === "function") {
      try {
        await Promise.race([
          document.fonts.load(`400 16px ${primaryToken}`),
          sleep(700),
        ]);
        if (document.fonts.ready && typeof document.fonts.ready.then === "function") {
          await Promise.race([
            document.fonts.ready,
            sleep(700),
          ]);
        }
      } catch (err) {
        // Continue with width checks and retries.
      }
    }
    if (isPrimaryFontApplied(familyName)) return true;
    await sleep(160);
  }
  return isPrimaryFontApplied(familyName);
}

function normalizeCssSourceUrl(url) {
  const normalized = String(url || "").trim();
  if (!normalized) return "";
  if (normalized.startsWith("//")) return `https:${normalized}`;
  return normalized;
}

function isGoogleFontSourceUrl(url) {
  const normalized = normalizeCssSourceUrl(url);
  if (!normalized) return false;
  try {
    const parsed = new URL(normalized);
    return parsed.protocol === "https:" && parsed.hostname === "fonts.gstatic.com";
  } catch {
    return false;
  }
}

function extractGoogleFontSourceUrls(cssText) {
  const source = String(cssText || "");
  const urls = [];
  const seen = new Set();
  FONT_CACHE_URL_PATTERN.lastIndex = 0;
  for (let match = FONT_CACHE_URL_PATTERN.exec(source); match; match = FONT_CACHE_URL_PATTERN.exec(source)) {
    const normalized = normalizeCssSourceUrl(match[2] || "");
    if (!normalized || seen.has(normalized)) continue;
    if (!isGoogleFontSourceUrl(normalized)) continue;
    seen.add(normalized);
    urls.push(normalized);
  }
  return urls;
}

function buildGoogleFontProbeUrls(familyName) {
  const normalizedFamily = normalizeGoogleFontFamilyName(familyName);
  if (!normalizedFamily) return [];
  const encodedFamily = encodeURIComponent(normalizedFamily).replace(/%20/g, "+");
  const canonicalWeights = FONT_CACHE_CANONICAL_WEIGHTS.join(";");
  return [
    `https://fonts.googleapis.com/css2?family=${encodedFamily}:wght@${canonicalWeights}&display=swap`,
    `https://fonts.googleapis.com/css2?family=${encodedFamily}&display=swap`,
  ];
}

async function probeGoogleFontInBrowser(familyName) {
  const probeUrls = buildGoogleFontProbeUrls(familyName);
  if (!probeUrls.length) {
    return { ok: false, message: "Enter a font family name first." };
  }

  const errors = [];
  for (const sourceCssUrl of probeUrls) {
    try {
      const response = await fetch(sourceCssUrl, {
        method: "GET",
        cache: "no-store",
      });
      const cssText = await response.text().catch(() => "");

      if (!response.ok) {
        if (response.status === 400 || response.status === 404) {
          continue;
        }
        errors.push(`${sourceCssUrl} -> HTTP ${response.status}`);
        continue;
      }

      const sourceUrls = extractGoogleFontSourceUrls(cssText);
      if (!sourceUrls.length) {
        errors.push(`${sourceCssUrl} -> no usable font URLs found`);
        continue;
      }

      return {
        ok: true,
        sourceCssUrl,
        cssText,
        sourceUrls,
      };
    } catch (err) {
      errors.push(`${sourceCssUrl} -> ${String(err?.message || err)}`);
    }
  }

  if (errors.length) {
    const preview = errors.slice(0, 2).join("; ");
    const suffix = errors.length > 2 ? `; +${errors.length - 2} more` : "";
    return {
      ok: false,
      message: `Google Fonts availability check failed in browser: ${preview}${suffix}`,
    };
  }

  return {
    ok: false,
    message: "Google Fonts does not recognize this font family string.",
  };
}

function fileNameFromSourceUrl(sourceUrl, index) {
  try {
    const parsed = new URL(sourceUrl);
    const part = parsed.pathname.split("/").filter(Boolean).pop() || "";
    if (part) return part;
  } catch {
    // Ignore parse issues and use fallback.
  }
  return `font-${index + 1}.woff2`;
}

async function downloadGoogleFontFiles(sourceUrls) {
  const files = [];
  for (let index = 0; index < sourceUrls.length; index += 1) {
    const sourceUrl = String(sourceUrls[index] || "").trim();
    if (!sourceUrl) continue;

    const response = await fetch(sourceUrl, {
      method: "GET",
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`Failed to download ${sourceUrl} (HTTP ${response.status})`);
    }

    const blob = await response.blob();
    files.push(
      new File(
        [blob],
        fileNameFromSourceUrl(sourceUrl, index),
        { type: blob.type || "application/octet-stream" }
      )
    );
  }
  return files;
}

async function pollFamilyCacheStatus(familyName, { attempts = 45, delayMs = 1100 } = {}) {
  let lastStatus = null;
  for (let i = 0; i < attempts; i += 1) {
    const status = await api.getFontFamilyCacheStatus({ family: familyName });
    lastStatus = status;
    const cacheStatus = String(status?.cache_status || "").toLowerCase();
    if (cacheStatus === "ready" || cacheStatus === "error" || cacheStatus === "not_cacheable") {
      return status;
    }
    await sleep(delayMs);
  }
  return lastStatus;
}

async function checkFontFamilyHealth(font, index) {
  if (!font || typeof font !== "object") return;
  normalizeFontFamilyEntry(font);

  const familyName = String(font.label || "").trim();
  if (!familyName) {
    setFontHealthStatus(index, "error", "Enter a font family name first.", {
      canCacheViaBrowser: false,
    });
    return;
  }
  setFontHealthStatus(index, "checking", "Checking font availability…", {
    canCacheViaBrowser: false,
  });

  try {
    const appliedLocally = await waitForPrimaryFontApplication(familyName, 1200);
    if (!shouldResolveServerCachedFamily(familyName)) {
      if (appliedLocally) {
        setFontHealthStatus(index, "cached", "Local/system font is available.", {
          canCacheViaBrowser: false,
        });
      } else {
        setFontHealthStatus(
          index,
          "fallback",
          "Font is not available locally. If this should be a Google font, run Health Check and then Cache via browser.",
          { canCacheViaBrowser: false }
        );
      }
      return;
    }

    const health = await api.getFontFamilyCacheStatus({ family: familyName });
    if (health?.ok === false) {
      setFontHealthStatus(
        index,
        "error",
        String(health?.message || "Health check backend error."),
        { canCacheViaBrowser: false }
      );
      return;
    }

    const cacheStatus = String(health?.cache_status || "").toLowerCase();
    const backendMessage = String(health?.message || "").trim();
    const stylesheetUrl = String(health?.stylesheet_url || "").trim();

    if (cacheStatus === "ready") {
      if (stylesheetUrl) {
        await ensureLocalFontStylesheet(stylesheetUrl);
      }
      const isApplied = await waitForPrimaryFontApplication(familyName, 3000);
      if (isApplied) {
        setFontHealthStatus(index, "cached", "Cached font is available and applied.", {
          canCacheViaBrowser: false,
        });
      } else {
        setFontHealthStatus(index, "cached", "Cached font is ready.", {
          canCacheViaBrowser: false,
        });
      }
      return;
    }

    if (cacheStatus === "pending") {
      setFontHealthStatus(
        index,
        "queued",
        backendMessage || "Font cache upload is still processing.",
        { canCacheViaBrowser: false }
      );
      return;
    }

    let probeResult = null;
    if (Boolean(health?.cacheable) && Boolean(health?.can_cache_via_browser)) {
      probeResult = await probeGoogleFontInBrowser(familyName);
    }

    if (probeResult?.ok) {
      const parts = [];
      if (appliedLocally) {
        parts.push("Font is available locally on this machine.");
      }
      if (backendMessage) {
        parts.push(backendMessage);
      }
      parts.push("Google font verified in browser. Click Cache via browser.");
      setFontHealthStatus(
        index,
        "queued",
        parts.join(" "),
        {
          canCacheViaBrowser: true,
          browserProbe: {
            sourceCssUrl: probeResult.sourceCssUrl,
            cssText: probeResult.cssText,
            sourceUrls: probeResult.sourceUrls,
          },
        }
      );
      return;
    }

    if (appliedLocally) {
      const localMessage = backendMessage
        ? `Font is available locally, but server cache is missing. ${backendMessage}`
        : "Font is available locally on this machine, but server cache is missing.";
      setFontHealthStatus(index, "fallback", localMessage, {
        canCacheViaBrowser: false,
      });
      return;
    }

    if (cacheStatus === "error") {
      setFontHealthStatus(
        index,
        "error",
        backendMessage || "Cached font failed previously. Run Health Check again and retry cache via browser.",
        { canCacheViaBrowser: false }
      );
      return;
    }

    setFontHealthStatus(index, "unavailable", probeResult?.message || backendMessage || "Fallback is being used.", {
      canCacheViaBrowser: false,
    });
  } catch (err) {
    console.error("Font health check failed:", err);
    const details = String(err?.message || "").trim();
    setFontHealthStatus(
      index,
      "error",
      details ? `Health check failed: ${details}` : "Health check failed.",
      { canCacheViaBrowser: false }
    );
  }
}

async function cacheFontFamilyNow(font, index) {
  if (!font || typeof font !== "object") return;
  normalizeFontFamilyEntry(font);

  const familyName = String(font.label || "").trim();
  if (!familyName) {
    setFontHealthStatus(index, "error", "Enter a font family name first.", {
      canCacheViaBrowser: false,
    });
    return;
  }

  let probe = getFontHealthBrowserProbe(index);
  if (!probe) {
    const probeResult = await probeGoogleFontInBrowser(familyName);
    if (!probeResult?.ok) {
      setFontHealthStatus(
        index,
        "unavailable",
        String(probeResult?.message || "Google Fonts could not be verified in browser."),
        { canCacheViaBrowser: false }
      );
      return;
    }
    probe = {
      sourceCssUrl: probeResult.sourceCssUrl,
      cssText: probeResult.cssText,
      sourceUrls: probeResult.sourceUrls,
    };
  }

  setFontHealthStatus(index, "caching", "Downloading from Google and uploading to cache…", {
    canCacheViaBrowser: false,
    browserProbe: probe,
  });

  try {
    const files = await downloadGoogleFontFiles(probe.sourceUrls);
    await api.cacheFontFamilyViaBrowser({
      family: familyName,
      sourceCssUrl: probe.sourceCssUrl,
      cssText: probe.cssText,
      sourceUrls: probe.sourceUrls,
      files,
    });

    const finalStatus = await pollFamilyCacheStatus(familyName);
    const cacheStatus = String(finalStatus?.cache_status || "").toLowerCase();
    const stylesheetUrl = String(finalStatus?.stylesheet_url || "").trim();
    if (cacheStatus === "ready") {
      if (stylesheetUrl) {
        await ensureLocalFontStylesheet(stylesheetUrl);
      }
      const isApplied = await waitForPrimaryFontApplication(familyName, 3000);
      if (isApplied) {
        setFontHealthStatus(index, "cached", "Cached font is available and applied.", {
          canCacheViaBrowser: false,
        });
      } else {
        setFontHealthStatus(index, "cached", "Font cached successfully.", {
          canCacheViaBrowser: false,
        });
      }
      return;
    }

    if (cacheStatus === "pending") {
      setFontHealthStatus(index, "queued", "Font cache upload is still processing. Please retry shortly.", {
        canCacheViaBrowser: false,
        browserProbe: probe,
      });
      return;
    }

    setFontHealthStatus(index, "error", String(finalStatus?.message || "Caching did not complete."), {
      canCacheViaBrowser: true,
      browserProbe: probe,
    });
  } catch (err) {
    console.error("Font cache now failed:", err);
    const details = String(err?.message || "").trim();
    setFontHealthStatus(
      index,
      "error",
      details ? `Cache via browser failed: ${details}` : "Cache via browser failed.",
      {
        canCacheViaBrowser: true,
        browserProbe: probe,
      }
    );
  }
}

async function preloadCachedFontFamilyStylesheets(fontFamilies) {
  const source = Array.isArray(fontFamilies) ? fontFamilies : [];
  const dedupedFamilies = [];
  const seen = new Set();

  for (const font of source) {
    const familyName = normalizeGoogleFontFamilyName(font?.label);
    if (!familyName || !shouldResolveServerCachedFamily(familyName)) continue;
    const key = familyName.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    dedupedFamilies.push(familyName);
  }

  for (const family of dedupedFamilies) {
    try {
      const status = await api.getFontFamilyCacheStatus({ family });
      if (status?.ok === false) continue;
      if (String(status?.cache_status || "").toLowerCase() !== "ready") continue;
      const stylesheetUrl = String(status?.stylesheet_url || "").trim();
      if (!stylesheetUrl) continue;
      await ensureLocalFontStylesheet(stylesheetUrl);
    } catch (err) {
      // Ignore preloading failures; manual Health Check still provides explicit feedback.
    }
  }
}

function setActiveTab(tab) {
  const target = designTabs.find((item) => item.id === tab) || designTabs[0];
  router.push(target.to);
}

onMounted(async () => {
  try {
    const savedSortMode = localStorage.getItem(COLOR_LINK_SORT_STORAGE_KEY);
    if (savedSortMode && COLOR_LINK_SORT_OPTIONS.some((opt) => opt.value === savedSortMode)) {
      colorLinkSortMode.value = savedSortMode;
    }
  } catch (err) {
    // Ignore storage failures (private mode, quota, etc.).
  }
  await initAuth();
  if (!authState.authenticated) {
    loading.value = false;
    return;
  }
  await loadConfig();
  await loadDesignSettings();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  if (saveTimeout) {
    clearTimeout(saveTimeout);
    saveTimeout = null;
  }
  clearDesignAutosaveStatusTimer();
  let shouldFlushDesignSave = false;
  if (fallbackContrastSaveTimeout) {
    clearTimeout(fallbackContrastSaveTimeout);
    fallbackContrastSaveTimeout = null;
    shouldFlushDesignSave = true;
  }
  if (baseColorSaveTimeout) {
    clearTimeout(baseColorSaveTimeout);
    baseColorSaveTimeout = null;
    shouldFlushDesignSave = true;
  }
  if (adminUiColorSaveTimeout) {
    clearTimeout(adminUiColorSaveTimeout);
    adminUiColorSaveTimeout = null;
    shouldFlushDesignSave = true;
  }
  if (shouldFlushDesignSave) {
    void saveDesignSettings().catch((err) => {
      console.error("Failed to flush pending design color save:", err);
    });
  }
});

watch(colorLinkSortMode, (mode) => {
  try {
    localStorage.setItem(COLOR_LINK_SORT_STORAGE_KEY, mode);
  } catch (err) {
    // Ignore storage failures (private mode, quota, etc.).
  }
});

// Auto-save with debounce
watch(
  () => config.value,
  () => {
    if (!config.value || loading.value || !configInitialized.value) return;
    const currentSignature = getConfigPayloadSignature(config.value);
    if (!currentSignature || currentSignature === configBaselineSignature.value) return;
    
    // Clear any pending save
    if (saveTimeout) clearTimeout(saveTimeout);
    clearDesignAutosaveStatusTimer();
    autoSaveError.value = "";
    
    // Debounce save by 1 second
    saveTimeout = setTimeout(async () => {
      await autoSave();
    }, 1000);
  },
  { deep: true }
);

async function autoSave() {
  if (!config.value || autoSaving.value) return;
  const payloadSignature = getConfigPayloadSignature(config.value);
  if (!payloadSignature || payloadSignature === configBaselineSignature.value) return;
  
  autoSaving.value = true;
  lastSaved.value = false;
  autoSaveError.value = "";
  
  try {
    const payload = getConfigPersistPayload(config.value);
    const saved = await api.updateAdminDesignConfig(payload);
    // Don't replace config to avoid infinite loop, just update state
    config.value.responsive = normalizeResponsiveConfig(config.value.responsive);
    state.adminDesignConfig = config.value;
    applyDesignCSS();
    configBaselineSignature.value = payloadSignature;
    
    autoSaving.value = false;
    showDesignAutosaveSaved();
  } catch (err) {
    console.error("Auto-save failed:", err);
    autoSaving.value = false;
    showDesignAutosaveError(err?.message || "Design configuration autosave failed.");
  }
}

function mergeNewParams(loaded) {
  // Merge any new parameters from PARAM_CONFIGS that aren't in the loaded config
  if (!loaded.parameters) loaded.parameters = {};
  if (!loaded.paramOrder) loaded.paramOrder = {};
  
  for (const [paramKey, paramConfig] of Object.entries(PARAM_CONFIGS)) {
    // Add missing parameters
    if (!loaded.parameters[paramKey]) {
      loaded.parameters[paramKey] = { ...paramConfig };
    }
    // Add to paramOrder if missing
    const section = paramConfig.section;
    if (section && loaded.paramOrder[section]) {
      if (!loaded.paramOrder[section].includes(paramKey)) {
        loaded.paramOrder[section].push(paramKey);
      }
    }
  }
  return loaded;
}

function getConfigPersistPayload(source) {
  if (!source || typeof source !== "object") return null;
  const { id, key, created_at, updated_at, ...rawPayload } = source;
  const payload = JSON.parse(JSON.stringify(rawPayload));
  normalizeFontFamilies(payload);
  payload.responsive = normalizeResponsiveConfig(payload.responsive);
  return payload;
}

function getConfigPayloadSignature(source) {
  const payload = getConfigPersistPayload(source);
  if (!payload) return "";
  try {
    return JSON.stringify(payload);
  } catch (err) {
    return "";
  }
}

async function loadConfig() {
  loading.value = true;
  configInitialized.value = false;
  try {
    const loaded = await api.getAdminDesignConfig();
    // Merge any new params from frontend definitions
    mergeNewParams(loaded);
    normalizeBaseColorSubsections(loaded);
    normalizeTypographySubsections(loaded);
    normalizeDesignPanelSectionOrder(loaded);
    normalizeBackgroundPatternPlacement(loaded);
    normalizeSectionOverrideParams(loaded);
    normalizeFontFamilies(loaded);
    loaded.responsive = normalizeResponsiveConfig(loaded.responsive);
    // Ensure hiddenSections array exists for reactivity
    if (!loaded.hiddenSections) {
      loaded.hiddenSections = [];
    }
    if (!loaded.baseColorHighContrast || typeof loaded.baseColorHighContrast !== "object") {
      loaded.baseColorHighContrast = {};
    }
    if (!loaded.colorVariations || typeof loaded.colorVariations !== "object") {
      loaded.colorVariations = {};
    }
    if (typeof loaded.showColorVariationDropdowns !== "boolean") {
      loaded.showColorVariationDropdowns = true;
    }
    // Wrap in reactive() so Vue tracks nested mutations (e.g., visibility changes)
    config.value = reactive(loaded);
    resetAllFontHealthStatuses();
    syncCustomBaseColorsToRuntime();
    state.adminDesignConfig = config.value;
    applyDesignCSS();
    configBaselineSignature.value = getConfigPayloadSignature(config.value);
    configInitialized.value = true;
    void preloadCachedFontFamilyStylesheets(config.value?.fontFamilies);
  } catch (err) {
    console.error("Failed to load admin design config:", err);
    configBaselineSignature.value = "";
    configInitialized.value = false;
  } finally {
    loading.value = false;
  }
}

async function saveConfig() {
  // Force immediate save (clears pending auto-save)
  if (saveTimeout) clearTimeout(saveTimeout);
  await autoSave();
}

async function resetDesignToDefaults() {
  if (!confirm("Reset all design settings to their defaults? This cannot be undone.")) return;
  try {
    await resetDesignSettings();
  } catch (err) {
    console.error("Failed to reset design settings:", err);
  }
}

async function resetConfigToDefaults() {
  if (!confirm("Reset admin configuration to defaults? This will restore all parameter ranges, visibility, and section order.")) return;
  try {
    const reset = await api.resetAdminDesignConfig();
    normalizeBaseColorSubsections(reset);
    normalizeBackgroundPatternPlacement(reset);
    normalizeSectionOverrideParams(reset);
    normalizeFontFamilies(reset);
    config.value = reset;
    resetAllFontHealthStatuses();
    syncCustomBaseColorsToRuntime();
    void preloadCachedFontFamilyStylesheets(config.value?.fontFamilies);
  } catch (err) {
    console.error("Failed to reset admin config:", err);
  }
}

const allButtonParamBaseNames = [
  { key: 'bgColor', label: 'Background Color' },
  { key: 'color', label: 'Text Color' },
  { key: 'borderColor', label: 'Border Color' },
  { key: 'hoverBgColor', label: 'Hover Background Color' },
  { key: 'hoverColor', label: 'Hover Text Color' },
  { key: 'hoverBorderColor', label: 'Hover Border Color' },
  { key: 'borderRadius', label: 'Border Radius' },
  { key: 'borderWidth', label: 'Border Width' },
  { key: 'fontSize', label: 'Font Size' },
  { key: 'paddingX', label: 'Horizontal Padding' },
  { key: 'paddingY', label: 'Vertical Padding' },
];

const individualButtonParamKeySet = computed(() => new Set(config.value?.buttonPerTypeParams || []));
const sharedButtonParamBaseNames = computed(() => (
  allButtonParamBaseNames.filter((param) => !individualButtonParamKeySet.value.has(param.key))
));
const individualButtonParamBaseNames = computed(() => (
  allButtonParamBaseNames.filter((param) => individualButtonParamKeySet.value.has(param.key))
));

function addButtonInstance() {
  const label = "New Button";
  const id = makeUniqueButtonInstanceId(slugifyButtonInstanceId(label));
  config.value.buttonInstances.push({ id, label, enabled: false });
}

function toggleButtonInstanceVisibility(index) {
  const instance = config.value?.buttonInstances?.[index];
  if (!instance) return;
  instance.enabled = !instance.enabled;
  state.adminDesignConfig = config.value;
}

function slugifyButtonInstanceId(label) {
  const base = String(label || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return base || "button";
}

function makeUniqueButtonInstanceId(baseId, currentIndex = -1) {
  if (!config.value?.buttonInstances) return baseId;
  const used = new Set(
    config.value.buttonInstances
      .map((btn, idx) => (idx === currentIndex ? null : String(btn?.id || "").trim()))
      .filter(Boolean)
  );
  if (!used.has(baseId)) return baseId;
  let n = 2;
  let nextId = `${baseId}_${n}`;
  while (used.has(nextId)) {
    n += 1;
    nextId = `${baseId}_${n}`;
  }
  return nextId;
}

function syncButtonInstanceId(index) {
  if (!config.value?.buttonInstances?.[index]) return;
  const instance = config.value.buttonInstances[index];
  const baseId = slugifyButtonInstanceId(instance.label);
  instance.id = makeUniqueButtonInstanceId(baseId, index);
}

function toggleButtonSharedParam(paramKey, isShared) {
  if (!config.value.buttonPerTypeParams) config.value.buttonPerTypeParams = [];
  const arr = config.value.buttonPerTypeParams;
  if (isShared) {
    // Shared = remove from per-type list
    const idx = arr.indexOf(paramKey);
    if (idx >= 0) arr.splice(idx, 1);
  } else {
    // Not shared = add to per-type list
    if (!arr.includes(paramKey)) arr.push(paramKey);
  }
}

function getAllDropdownOptions(paramKey) {
  return getParamOptionValues(paramKey, config.value.parameters[paramKey]?.enabledOptions || []);
}

function getAllButtonGroupOptions(paramKey) {
  return getParamOptionValues(paramKey, config.value.parameters[paramKey]?.enabledOptions || []);
}

function formatOptionLabel(paramKey, optValue) {
  return getParamOptionLabel(paramKey, optValue);
}

function toggleDropdownOption(paramKey, opt, checked) {
  const arr = config.value.parameters[paramKey].enabledOptions;
  if (checked && !arr.includes(opt)) {
    arr.push(opt);
  } else if (!checked) {
    const idx = arr.indexOf(opt);
    if (idx >= 0) arr.splice(idx, 1);
  }
}

// Update parameter order when dragged
function updateParamOrder(sectionKey, newFilteredOrder) {
  if (!config.value.paramOrder) config.value.paramOrder = {};
  
  // If no filters are active, just use the new order directly
  if (!hasActiveFilters.value) {
    config.value.paramOrder[sectionKey] = newFilteredOrder;
    return;
  }
  
  // When filters are active, we need to merge the new order with non-visible items
  const currentFullOrder = paramsBySection.value[sectionKey] || [];
  const filteredSet = new Set(newFilteredOrder);
  
  // Get items that weren't in the filtered view (they should keep their relative positions)
  const nonFilteredItems = currentFullOrder.filter(pKey => !filteredSet.has(pKey));
  
  // Rebuild the full order: insert filtered items at their new positions
  // For simplicity, place all filtered items first, then non-filtered
  // This maintains drag-drop behavior while preserving non-matching items
  config.value.paramOrder[sectionKey] = [...newFilteredOrder, ...nonFilteredItems];
}

// Parameter label editing
function updateParamLabel(paramKey, value) {
  if (!config.value.parameters[paramKey]) return;
  // Store empty string as empty, don't reset to paramKey
  config.value.parameters[paramKey].label = value;
}

// Subsection editing
function updateSubsection(paramKey, value) {
  if (!config.value.parameters[paramKey]) return;
  // Store empty string as empty, don't reset to undefined
  config.value.parameters[paramKey].subsection = value;
}

// Multi-unit slider config helpers
function getUnitConfigs(paramKey) {
  const param = config.value.parameters[paramKey];
  if (!param) return [];
  // Prefer explicit unitConfigs array when present.
  if (param.unitConfigs && param.unitConfigs.length > 0) {
    return param.unitConfigs;
  }
  // Derive a single config row from base slider fields.
  return [{
    unit: param.unit || 'px',
    min: param.min ?? 0,
    max: param.max ?? 100,
    step: param.step ?? 1
  }];
}

function isDefaultUnit(paramKey, unit) {
  const param = config.value.parameters[paramKey];
  if (!param) return false;
  // If defaultUnit is set, use it; otherwise first unit is default
  if (param.defaultUnit) return param.defaultUnit === unit;
  const configs = getUnitConfigs(paramKey);
  return configs.length > 0 && configs[0].unit === unit;
}

function setDefaultUnit(paramKey, unit) {
  if (!config.value.parameters[paramKey]) return;
  config.value.parameters[paramKey].defaultUnit = unit;
}

function updateUnitConfig(paramKey, idx, field, value) {
  const param = config.value.parameters[paramKey];
  if (!param) return;
  // Ensure unitConfigs array exists
  if (!param.unitConfigs) {
    param.unitConfigs = getUnitConfigs(paramKey);
  }
  if (param.unitConfigs[idx]) {
    param.unitConfigs[idx][field] = value;
  }
  // Keep base slider fields in sync with the first unit config.
  if (idx === 0) {
    param[field] = value;
  }
}

function addUnitConfig(paramKey) {
  const param = config.value.parameters[paramKey];
  if (!param) return;
  // Ensure unitConfigs array exists
  if (!param.unitConfigs) {
    param.unitConfigs = getUnitConfigs(paramKey);
  }
  // Find a unit not already used, default to %
  const usedUnits = new Set(param.unitConfigs.map(uc => uc.unit));
  const commonUnits = ['%', 'em', 'rem', 'vw', 'vh', 'pt'];
  const newUnit = commonUnits.find(u => !usedUnits.has(u)) || '%';
  param.unitConfigs.push({
    unit: newUnit,
    min: 0,
    max: 100,
    step: 1
  });
}

function removeUnitConfig(paramKey, idx) {
  const param = config.value.parameters[paramKey];
  if (!param || !param.unitConfigs) return;
  const removedUnit = param.unitConfigs[idx]?.unit;
  param.unitConfigs.splice(idx, 1);
  // If we removed the default unit, reset to first unit
  if (param.defaultUnit === removedUnit && param.unitConfigs.length > 0) {
    param.defaultUnit = param.unitConfigs[0].unit;
  }
  // Keep base slider fields in sync with the first unit config.
  if (param.unitConfigs.length > 0) {
    const first = param.unitConfigs[0];
    param.unit = first.unit;
    param.min = first.min;
    param.max = first.max;
    param.step = first.step;
  }
}

</script>

<style scoped>
/* Cards */
.config-card-wide {
  overflow-x: auto;
  overflow-y: visible;
  max-height: none;
}

.card-hint {
  font-size: 13px;
  color: #94a3b8;
  margin: 4px 0 0;
}

.responsive-settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}

.responsive-device-panel {
  display: grid;
  align-content: start;
  gap: 14px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.responsive-device-heading {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
}

.responsive-device-icon {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 15px;
}

.responsive-device-heading h3 {
  margin: 0;
  font-size: 14px;
  color: #0f172a;
}

.responsive-device-heading p {
  margin: 2px 0 0;
  font-size: 12px;
  line-height: 1.35;
  color: #64748b;
}

.responsive-input-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.responsive-field {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.responsive-field--range {
  grid-column: 1 / -1;
}

.responsive-field__label {
  font-size: 11px;
  font-weight: 700;
  line-height: 1.25;
  color: #475569;
  text-transform: uppercase;
}

.responsive-field__control {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.responsive-field__control:focus-within {
  border-color: var(--accent, #5b2fe3);
  box-shadow: 0 0 0 2px rgba(91, 47, 227, 0.1);
}

.responsive-field__control--readonly {
  background: #f8fafc;
}

.responsive-field__control--readonly strong {
  min-width: 0;
  padding: 1px 6px;
  text-align: right;
  color: #334155;
  font-size: 16px;
  font-weight: 400;
}

.responsive-field__control .field {
  width: 100%;
  min-width: 0;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  text-align: right;
}

.responsive-field__control > span {
  padding: 0 10px 0 2px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.responsive-actions {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
}

/* Section Order */
.section-order-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-order-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px 0 2px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: grab;
  user-select: none;
  transition: all 0.15s;
}

.section-order-item:hover {
  border-color: #cbd5e1;
}

.section-order-item.is-hidden {
  opacity: 0.5;
  background: #fff;
}

.section-order-item:active { cursor: grabbing; }

.section-name {
  flex: 1;
}

.visibility-btn {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}

.visibility-btn:hover {
  border-color: #94a3b8;
  color: #334155;
}

.visibility-btn.hidden {
  color: #cbd5e1;
  background: #f8fafc;
}

.visibility-btn.hidden:hover {
  color: #64748b;
  border-color: #94a3b8;
}

/* Font list */
.font-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.font-family-info {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.45;
  color: #475569;
}

.font-family-info a {
  color: #2563eb;
}

.font-preview-sample-label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0 0 12px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  max-width: 520px;
}

.font-preview-sample-input {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
  color: #1e293b;
  background: #fff;
}

.font-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.font-item-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.font-item-group {
  display: flex;
  gap: 10px;
  align-items: center;
}

.font-item--wrapper {
  flex-wrap: wrap;
}

.font-item--sanity {
  flex-shrink: 0;
}

.font-label-input {
  width: 180px;
  padding: 6px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
  min-height: 36px;
}

.font-fallback-select {
  width: 130px;
  padding: 6px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
  background: #ffffff;
  min-height: 36px;
}

.font-preview-pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  width: 100%;
  max-width: 640px;
}

.font-preview-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  border: 1px solid #dbe4ef;
  border-radius: 8px;
  background: #ffffff;
  min-width: 0;
}

.font-preview-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: #64748b;
}

.font-preview-subtitle {
  font-size: 12px;
  color: #334155;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.font-preview-text {
  font-size: 16px;
  line-height: 1.35;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.font-check-btn {
  white-space: nowrap;
}

.font-cache-btn {
  white-space: nowrap;
}

.font-health-status {
  font-size: 12px;
  font-weight: 600;
}

.font-health-status.is-checking {
  color: #475569;
}

.font-health-status.is-caching {
  color: #475569;
}

.font-health-status.is-cached {
  color: #15803d;
}

.font-health-status.is-queued {
  color: #1d4ed8;
}

.font-health-status.is-fallback {
  color: #b45309;
}

.font-health-status.is-error {
  color: #b91c1c;
}

.font-health-status.is-unavailable {
  color: #b91c1c;
}

/* Button instances */
.button-instances {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.button-instance-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.button-instance-item.is-hidden {
  opacity: 0.5;
  background: #fff;
}

.button-instance-visibility-btn {
  margin-left: auto;
}

.instance-name-input,
.instance-id-input {
  padding: 5px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  font-size: 13px;
  width: 120px;
}

.instance-id-input {
  font-family: ui-monospace, monospace;
  font-size: 12px;
  color: #64748b;
  width: 140px;
}

.per-type-params {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.per-type-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 4px;
}

.per-type-params-header {
  margin-bottom: 10px;
}

.button-param-groups {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.button-param-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
}

.button-param-group-label {
  padding-bottom: 6px;
  border-bottom: 1px solid #f1f5f9;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.button-param-group .option-checks {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.button-param-empty {
  color: #94a3b8;
  font-size: 12px;
  font-style: italic;
}

/* Color links */
.color-links-table {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.base-colors-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0 0 14px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.fallback-contrast-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0 0 14px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.admin-ui-colors-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0 0 14px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.admin-ui-colors-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.admin-ui-color-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) 26px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
}

.admin-ui-color-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.fallback-contrast-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fallback-contrast-row {
  display: grid;
  grid-template-columns: 64px 26px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
}

.fallback-contrast-label {
  font-size: 12px;
  font-weight: 700;
  color: #334155;
}

.base-colors-title {
  margin: 0;
  font-size: 14px;
  color: #0f172a;
}

.base-colors-list {
  display: grid;
  gap: 8px;
}

.base-color-row {
  display: grid;
  grid-template-columns: minmax(160px, 190px) minmax(200px, 1fr) minmax(360px, 1.5fr);
  gap: 10px;
  align-items: center;
}

.base-color-row-header {
  padding: 0 2px;
}

.base-color-row-header > span {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #475569;
  text-transform: uppercase;
}

.base-color-preview {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.base-color-value {
  font-size: 12px;
  color: #334155;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.base-color-name-input {
  width: 100%;
  padding: 5px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  font-size: 13px;
  min-height: 36px;
}

.base-color-label-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}

.base-color-remove-btn {
  width: 24px;
  height: 24px;
  border: 1px solid #fecaca;
  background: #fff1f2;
  color: #b91c1c;
  border-radius: 6px;
  cursor: pointer;
  line-height: 1;
  padding: 0;
}

.base-color-remove-btn:hover {
  background: #ffe4e6;
}

.add-base-color-btn {
  align-self: flex-start;
}

.base-color-contrast {
  display: grid;
  grid-template-columns: minmax(124px, 152px) 26px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.base-contrast-source-select {
  width: 100%;
  padding: 5px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  font-size: 12px;
  background: #fff;
  min-height: 36px;
}

.base-contrast-slot {
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.base-contrast-picker-shell {
  display: inline-flex;
}

.base-contrast-linked-swatch {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  flex: 0 0 26px;
}

.base-contrast-slot-placeholder {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: 1px dashed #cbd5e1;
  background: #f8fafc;
}

.base-contrast-value {
  font-size: 12px;
  color: #334155;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  min-width: 0;
  word-break: break-word;
}

.base-contrast-warning {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #facc15;
  color: #111827;
  font-size: 10px;
  font-weight: 900;
  line-height: 1;
  border: 1px solid #f59e0b;
  flex: 0 0 auto;
}

.cl-header {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.cl-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: center;
  padding: 8px 12px;
  border-radius: 6px;
}

.cl-row:nth-child(even) { background: #f8fafc; }

.color-variation-toggle {
  margin: 6px 12px 10px;
}

.cl-sort-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px 8px;
}

.cl-sort-label {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.cl-sort-select {
  min-width: 240px;
  padding: 5px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  font-size: 13px;
  background: #fff;
  color: #0f172a;
}

.cl-group {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.cl-group + .cl-group {
  margin-top: 10px;
}

.cl-group-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.cl-group-count {
  font-size: 11px;
  color: #64748b;
  font-weight: 600;
}

.cl-label-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cl-label {
  font-size: 13px;
  font-weight: 500;
}

.cl-context {
  font-size: 11px;
  color: #64748b;
}

.cl-control {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cl-select-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cl-select {
  min-width: 170px;
  padding: 5px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  font-size: 13px;
  cursor: pointer;
}

.cl-variation-select {
  min-width: 78px;
  padding: 5px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  font-size: 13px;
  background: #fff;
  cursor: pointer;
}

.cl-preview {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.cl-preview.is-empty {
  opacity: 0.72;
}

.cl-preview-swatch {
  width: 18px;
  height: 18px;
  border-radius: 5px;
  border: 1px solid #cbd5e1;
  flex: 0 0 auto;
}

.cl-preview-value {
  font-size: 12px;
  color: #334155;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  word-break: break-all;
}

/* Sticky Header for Parameters */
.params-sticky-header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: #fff;
  border-bottom: 2px solid #e2e8f0;
  margin: 0 -20px;
  padding: 0 20px;
}

.params-header-row {
  display: grid;
  grid-template-columns: 32px 1fr 140px 90px 60px 50px 110px minmax(280px, 1fr);
  align-items: center;
  padding: 10px 12px;
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.params-filter-row {
  display: grid;
  grid-template-columns: 32px 1fr 140px 90px 60px 50px 110px minmax(280px, 1fr);
  align-items: center;
  padding: 8px 12px;
  gap: 4px;
  background: #fff;
}

.filter-input {
  width: 100%;
  padding: 5px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  font-size: 12px;
  background: #fff;
  transition: border-color 0.15s;
}

.filter-input:focus {
  outline: none;
  border-color: #4f46e5;
}

.filter-input::placeholder {
  color: #94a3b8;
}

.filter-select {
  width: 100%;
  padding: 5px 6px;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  font-size: 12px;
  background: #fff;
  cursor: pointer;
}

.filter-select:focus {
  outline: none;
  border-color: #4f46e5;
}

.filter-select-sm {
  padding: 5px 2px;
  font-size: 11px;
}

.btn-reset-filters {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  background: #fff;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-reset-filters:hover {
  background: #fef2f2;
  border-color: #fecaca;
  color: #dc2626;
}

/* Parameters sections */
.params-sections {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
}

.params-section {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.params-section.is-collapsed {
  border-color: #f1f5f9;
}

.section-header-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.section-header-row:hover {
  background: #f1f5f9;
}

.is-collapsed .section-header-row {
  border-bottom: none;
  background: #fafbfc;
}

.section-collapse-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  color: #94a3b8;
  transition: color 0.15s;
}

.section-header-row:hover .section-collapse-icon {
  color: #64748b;
}

.section-count {
  margin-left: auto;
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
}

.params-list {
  min-height: 20px;
}

.param-row {
  display: grid;
  grid-template-columns: 32px 1fr 140px 90px 60px 50px 110px minmax(280px, 1fr);
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 13px;
  background: #fff;
}

.param-row:last-child {
  border-bottom: none;
}

.param-row.param-hidden {
  opacity: 0.45;
}
.param-row.param-hidden .col-visible {
  opacity: 1;
}

.col-drag { text-align: center; }
.col-param { min-width: 0; }
.col-visible { text-align: center; }
.col-fav { text-align: center; }

.drag-handle {
  cursor: grab;
  color: #94a3b8;
  font-size: 18px;
  padding: 6px 10px;
  user-select: none;
  letter-spacing: -2px;
}
.drag-handle:hover { color: #64748b; }
.drag-handle:active { cursor: grabbing; }

.drag-ghost {
  opacity: 0.5;
  background: #e0f2fe;
  border: 1px dashed #0ea5e9;
}

.subsection-input {
  width: 100%;
  padding: 4px 6px;
  border: 1px solid transparent;
  border-radius: 5px;
  font-size: 12px;
  background: transparent;
  color: #64748b;
}
.subsection-input:hover { border-color: #e2e8f0; background: #fff; }
.subsection-input:focus { outline: none; border-color: #4f46e5; background: #fff; color: #1e293b; }
.subsection-input::placeholder { color: #cbd5e1; }

.responsive-select {
  padding: 4px 6px;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  font-size: 12px;
  cursor: pointer;
  background: #fff;
}
.responsive-select:focus { outline: none; border-color: #4f46e5; }

.section-first td { border-top: 2px solid #e2e8f0; }

.section-badge {
  display: inline-block;
  padding: 3px 8px;
  background: #eef2ff;
  color: #4f46e5;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.param-label-input {
  width: 100%;
  padding: 4px 6px;
  border: 1px solid transparent;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 600;
  background: transparent;
  color: #0f172a;
}
.param-label-input:hover { border-color: #e2e8f0; background: #fff; }
.param-label-input:focus { outline: none; border-color: #4f46e5; background: #fff; }
.param-label-input::placeholder { color: #94a3b8; font-weight: 400; }

.param-key {
  font-size: 10px;
  color: #94a3b8;
  font-family: monospace;
  margin-top: 2px;
  padding-left: 6px;
}

.param-sub {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.type-badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: #f1f5f9;
  color: #64748b;
}

.type-badge.slider { background: #dbeafe; color: #1d4ed8; }
.type-badge.color { background: #fce7f3; color: #be185d; }
.type-badge.dropdown { background: #e0e7ff; color: #4338ca; }
.type-badge.checkbox { background: #d1fae5; color: #065f46; }
.type-badge.fontfamily { background: #fef3c7; color: #92400e; }
.type-badge.buttongroup { background: #ede9fe; color: #5b21b6; }
.type-badge.positiongrid { background: #f0fdf4; color: #166534; }

.fav-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 18px;
  color: #d1d5db;
  transition: color 0.15s;
  padding: 0;
  line-height: 1;
}

.fav-btn.active { color: #f59e0b; }
.fav-btn:hover { color: #fbbf24; }

.col-visible input,
.col-fav input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

/* Inline config for table cells */
.inline-config {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.mini-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mini-field span {
  font-size: 10px;
  color: #94a3b8;
  font-weight: 600;
  text-transform: uppercase;
}

.mini-field input {
  width: 70px;
  padding: 4px 6px;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  font-size: 12px;
  font-family: ui-monospace, monospace;
}

.unit-input {
  width: 40px !important;
}

.unit-select {
  width: 60px !important;
  padding: 4px 2px !important;
  font-size: 11px;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  min-height: 36px;
}

.unit-select:focus {
  outline: none;
  border-color: #4f46e5;
}

.unit-select optgroup {
  font-weight: 600;
  color: #64748b;
}

/* Multi-unit slider config */
.slider-config {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.unit-config-row {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  padding: 4px 6px;
  background: #f8fafc;
  border-radius: 6px;
  border: 1px solid transparent;
}

.unit-config-row.is-default {
  background: #eef2ff;
  border-color: #c7d2fe;
}

.unit-field {
  flex-shrink: 0;
}

.default-btn {
  padding: 2px 6px;
  border-radius: 4px;
  background: #fff;
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.default-btn:hover {
  color: #eab308;
  border-color: #eab308;
}

.default-indicator {
  padding: 2px 6px;
  color: #eab308;
  font-size: 12px;
}

.remove-unit-btn {
  padding: 2px 6px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.remove-unit-btn:hover {
  color: #ef4444;
  background: #fef2f2;
}

.add-unit-btn {
  align-self: flex-start;
  padding: 4px 10px;
  border: 1px dashed #cbd5e1;
  border-radius: 5px;
  background: transparent;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.add-unit-btn:hover {
  border-color: #4f46e5;
  color: #4f46e5;
  background: #eef2ff;
}

.slider-config-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 4px;
}

.allow-input-check {
  font-size: 11px !important;
  color: #64748b !important;
}

.mini-check {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #475569;
  cursor: pointer;
  white-space: nowrap;
}

.mini-check input {
  width: 14px;
  height: 14px;
  cursor: pointer;
}

.option-checks {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
}

.no-config {
  color: #d1d5db;
}

/* Override config */
.override-config {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.override-group {
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.override-group-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 12px;
}

.override-param-groups {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.override-param-group {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 12px;
}

.override-param-group-label {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #f1f5f9;
}

.override-param-group .option-checks {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* Reset actions */
.reset-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

/* Buttons */
.btn-icon {
  width: 32px;
  height: 32px;
  display: inline-grid;
  place-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
  color: #64748b;
}

.btn-icon:hover { background: #f1f5f9; }

.btn-icon-danger {
  width: 30px;
  height: 30px;
  display: inline-grid;
  place-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  color: #94a3b8;
  flex-shrink: 0;
  transition: all 0.15s;
}

.btn-icon-danger:hover { background: #fef2f2; border-color: #fecaca; color: #dc2626; }

/* Loading / empty */
.loading-state,
.empty-state {
  text-align: center;
  padding: 40px;
  color: #94a3b8;
  font-size: 14px;
}

/* ========== RESPONSIVE STYLES ========== */
@media (max-width: 767px) {
  /* Page header */
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .page-header-actions {
    justify-content: flex-start;
  }

  /* Font Families - stack vertically */
  .font-item {
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
    padding: 12px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
  }

  .font-item--wrapper {
    flex-direction: column;
    align-items: stretch;
  }

  .font-label-input,
  .font-fallback-select {
    width: 100%;
  }

  .font-preview-pair {
    grid-template-columns: 1fr;
    max-width: none;
  }

  .font-check-btn,
  .font-cache-btn {
    width: 100%;
  }

  .font-item .btn-icon-danger {
    align-self: flex-end;
  }

  /* Button Instances - stack vertically */
  .button-instance-item {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .instance-name-input,
  .instance-id-input {
    width: 100%;
  }

  .button-instance-item .btn-icon-danger {
    align-self: flex-end;
    order: 2;
  }

  /* Design Parameters - responsive layout */
  .params-sticky-header {
    display: none;
  }

  .params-section {
    border-radius: 8px;
  }

  .param-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
    border-bottom: 1px solid #e2e8f0;
  }

  .param-row:last-child {
    border-bottom: none;
  }

  .col-drag {
    display: none;
  }

  .col-param {
    width: 100%;
    order: 1;
  }

  .param-label-input {
    font-size: 14px;
    padding: 8px 10px;
    border: 1px solid #e2e8f0;
    background: #fff;
  }

  .param-key {
    margin-top: 4px;
  }

  .col-subsection {
    width: 100%;
    order: 2;
  }

  .col-subsection::before {
    content: "Subsection: ";
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
  }

  .subsection-input {
    border: 1px solid #e2e8f0;
    background: #fff;
    padding: 6px 8px;
  }

  .col-type {
    order: 3;
  }

  /* Controls row - inline on mobile */
  .col-visible,
  .col-fav,
  .col-responsive {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .col-visible {
    order: 4;
  }

  .col-visible::before {
    content: "Visible";
    font-size: 11px;
    color: #64748b;
  }

  .col-fav {
    order: 5;
  }

  .col-fav::before {
    content: "Favorite";
    font-size: 11px;
    color: #64748b;
  }

  .col-responsive {
    order: 6;
    width: 100%;
  }

  .col-responsive::before {
    content: "Responsive: ";
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
  }

  .responsive-select {
    flex: 1;
  }

  .col-config {
    order: 7;
    width: 100%;
  }

  /* Mobile param row with controls grouped */
  .param-row .mobile-controls {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    padding-top: 8px;
    border-top: 1px solid #f1f5f9;
  }

  /* Slider config on mobile */
  .slider-config {
    width: 100%;
  }

  .unit-config-row {
    flex-wrap: wrap;
  }

  .mini-field {
    min-width: 70px;
  }

  /* Option checks on mobile */
  .option-checks {
    flex-direction: column;
    gap: 8px;
  }

  /* Color links table on mobile */
  .cl-sort-row {
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
    padding: 0 0 8px;
  }

  .cl-sort-select {
    width: 100%;
    min-width: 0;
  }

  .cl-group {
    border-radius: 8px;
  }

  .cl-header {
    display: none;
  }

  .cl-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 12px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-bottom: 8px;
  }

  .cl-label {
    font-weight: 600;
  }

  .cl-control {
    width: 100%;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .cl-select {
    width: 100%;
    min-width: 0;
  }

  .cl-select-row {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .cl-variation-select {
    width: 100%;
    min-width: 0;
  }

  .cl-preview {
    width: 100%;
  }

  .base-color-row {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .base-color-row-header {
    display: none;
  }

  .base-color-contrast {
    grid-template-columns: minmax(120px, 1fr) 26px minmax(0, 1fr) auto;
  }

  .admin-ui-color-row {
    grid-template-columns: 1fr 26px minmax(0, 1fr);
  }

  /* Override config on mobile */
  .override-param-groups {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .override-config .option-checks {
    gap: 6px;
  }

  /* Section order on mobile - keep drag handles visible but less prominent */
  .section-order-item {
    padding: 8px 12px;
  }
}

/* Tablet adjustments */
@media (min-width: 768px) and (max-width: 1024px) {
  .param-row {
    grid-template-columns: 28px 1fr 100px 80px 50px 40px 90px minmax(200px, 1fr);
  }

  .params-header-row,
  .params-filter-row {
    grid-template-columns: 28px 1fr 100px 80px 50px 40px 90px minmax(200px, 1fr);
  }

  .instance-name-input {
    width: 100px;
  }

  .instance-id-input {
    width: 110px;
  }
}
</style>
