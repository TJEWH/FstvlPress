<template>
  <SectionBase
    :section-key="effectiveKey"
    :section-data="section"
    :admin-tabs-visible="state.isAdmin && (!state.previewMode || isTemplateBuilderPage)"
    :admin-show-integration-importer="!useProgramGigs"
  >
    <div @mouseenter="hover=true" @mouseleave="hover=false">
      <div
        v-if="publicVisibleFilters.length > 0"
        class="tile-filter-bar"
        :class="`tile-filter-bar--${tileFilterControlStyle}`"
        :style="tileFilterBarStyle"
      >
        <template v-for="control in publicFilterControls" :key="control.key">
          <TileFilterDropdown
            v-if="control.type === 'filter' && tileFilterControlStyle === 'dropdowns'"
            :label="formatPublicFilterLabel(control.filter)"
            :options="publicFilterOptionsById[control.filter.id] || []"
            :model-value="selectedPublicFilterValues[control.filter.id] || ''"
            @update:model-value="setPublicFilterValue(control.filter.id, $event)"
          />
          <div
            v-else-if="control.type === 'filter'"
            :class="[
              'tile-filter-choice-group',
              `tile-filter-choice-group--${tileFilterControlStyle}`,
            ]"
          >
            <div class="tile-filter-choice-label">{{ formatPublicFilterLabel(control.filter) }}</div>
            <div class="tile-filter-choice-options">
              <button
                type="button"
                class="tile-filter-choice"
                :class="{ 'tile-filter-choice--active': (selectedPublicFilterValues[control.filter.id] || '') === '' }"
                @click="setPublicFilterValue(control.filter.id, '')"
              >
                All
              </button>
              <button
                v-for="opt in publicFilterOptionsById[control.filter.id] || []"
                :key="`tile-filter-option-${control.filter.id}-${opt}`"
                type="button"
                class="tile-filter-choice"
                :class="{ 'tile-filter-choice--active': selectedPublicFilterValues[control.filter.id] === opt }"
                @click="setPublicFilterValue(control.filter.id, opt)"
              >
                {{ opt }}
              </button>
            </div>
          </div>
          <button
            v-else
            type="button"
            class="tile-filter-reset"
            :disabled="!hasActivePublicFilters"
            @click="clearPublicFilters"
          >
            Reset
          </button>
        </template>
      </div>

      <!-- Display grid -->
      <div
        ref="gridRef"
        class="tiles-grid"
        :class="{ 'tiles-grid--has-expanded': expandedIndex >= 0 }"
        :style="gridStyle"
      >
        <div
          v-for="(tile, i) in displayTiles"
          :key="tile.id || i"
          class="tile"
          :class="{
            'tile--expanded': expandedIndex === i,
            'tile--expanded-hovered': isTileOverlayActive(i) && hoveredIndex === i,
            'tile--has-image': !!resolveTileImageUrl(tile, i),
            'tile--dimmed': expandedIndex >= 0 && expandedIndex !== i,
            'tile--non-actionable': !canActivateTilePrimary && !tile._filler,
            'tile--single-row-overlay': treatTilesAsScaledOnHover && !tile._filler,
            'tile--filler': tile._filler,
          }"
          :style="tileStyle(i)"
          v-bind="tile._filler ? {} : {
            tabindex: 0,
            role: canActivateTilePrimary ? 'button' : 'group',
            'aria-label': localizedText(resolveTileTitle(tile)) || `Tile ${i + 1}`,
          }"
          @click="tile._filler ? undefined : handleTilePrimaryAction(i)"
          @keydown.enter.prevent.self="tile._filler ? undefined : handleTilePrimaryAction(i)"
          @keydown.space.prevent.self="tile._filler ? undefined : handleTilePrimaryAction(i)"
          @mouseenter="tile._filler ? undefined : handleTileMouseEnter(i, tile)"
          @mouseleave="tile._filler ? undefined : handleTileMouseLeave(i)"
          @focusin="tile._filler ? undefined : handleTileFocusIn(i, tile)"
          @focusout="tile._filler ? undefined : handleTileFocusOut(i, $event)"
        >
          <div v-if="checkerBg(i)" class="tile-checker" :style="{ background: checkerBg(i) }" />
          <TransformedImage
            v-if="resolveTileImageUrl(tile, i)"
            class="tile-img"
            :src="resolveTileImageUrl(tile, i)"
            alt=""
            :ratio="aspectRatio"
            :direction="direction"
            :zoom="resolveTileImageZoom(tile, i)"
            :focal-x="resolveTileImageFocalX(tile, i)"
            :focal-y="resolveTileImageFocalY(tile, i)"
            :rotation="resolveTileImageRotation(tile, i)"
            :responsive-variants="resolveTileResponsiveVariants(tile, i)"
            :slot-width="resolveTileImageSlotWidth()"
            :render-scale="resolveTileImageRenderScale(i)"
            :initial-render-scale="1"
            :lazy-render-scale-upgrade="canScaleTilesUp"
            fit="cover"
            loading="eager"
            decoding="async"
          />
          <div v-else-if="!checkerBg(i)" class="tile-placeholder" />

          <template v-if="!tile._filler">
            <div
              class="tile-top-info"
              :class="[
                {
                  'tile-top-info--visible': isTileOverlayActive(i),
                },
                `tile-top-info--align-${tileTopInfoAlign}`,
              ]"
            >
              <span v-if="resolveTileDateTime(tile)" class="tile-top-time">{{ resolveTileDateTime(tile) }}</span>
              <span v-if="showTileLocation(tile)" class="tile-top-stage">{{ resolveTileLocation(tile) }}</span>
            </div>

            <div
              class="tile-bottom-info"
              :class="[
                {
                  'tile-bottom-info--expanded': isTileOverlayActive(i),
                  'tile-bottom-info--visible': showTileBottomInfo(i, tile),
                  'tile-bottom-info--muted-title': alwaysShowTitle && expandedIndex >= 0 && expandedIndex !== i,
                },
                `tile-bottom-info--align-${tileBottomInfoAlign}`,
              ]"
            >
              <div v-if="hasTileTitle(tile)" class="tile-bottom-title-row">
                <span class="tile-bottom-title">{{ localizedText(resolveTileTitle(tile)) }}</span>
              </div>
              <transition name="tile-subtitle-scale">
                <div
                  v-if="isTileOverlayActive(i) && hasTileSubtitle(tile)"
                  class="tile-bottom-subtitle"
                >
                  <span class="tile-bottom-subtitle-inner">
                    {{ localizedText(resolveTileSubtitle(tile)) }}
                  </span>
                </div>
              </transition>
            </div>

            <router-link
              v-if="resolveTilePublicItemUrl(tile)"
              :to="resolveTilePublicItemUrl(tile)"
              class="tile-chevron-overlay"
              :class="{ 'tile-chevron-overlay--visible': showTileChevron(i, tile) }"
              :aria-label="tileMoreLabel"
              @click.stop
            >
              <span class="tile-chevron-overlay-label">{{ tileMoreLabel }}</span>
              <font-awesome-icon :icon="faChevronRight" class="tile-chevron-overlay-icon" aria-hidden="true" />
            </router-link>
          </template>
        </div>
      </div>

      <MediaLibrary
        :is-open="showMediaPicker"
        :current-url="''"
        source-context="section.tiles.image"
        @close="closeMediaPicker"
        @select="onMediaSelect"
      />
    </div>

    <template #admin-design-params>
      <div class="admin-actions tile-design-controls">
        <div class="tile-design-group">
          <div class="tile-design-group-title">Layout</div>
          <div class="tile-design-grid">
            <label class="grid-control">
              View Mode
              <select :value="gridMode" class="grid-input grid-input--select" @change="setGridMode($event.target.value)">
                <option value="auto">Auto Wrap</option>
                <option value="fixed">Fixed Grid</option>
                <option value="columns">Columns</option>
              </select>
            </label>
            <label class="grid-control">
              Ratio
              <select :value="aspectRatio" class="grid-input grid-input--select" @change="setAspectRatio($event.target.value)">
                <option value="1:1">1:1</option>
                <option value="3:2">3:2</option>
                <option value="4:3">4:3</option>
                <option value="16:9">16:9</option>
              </select>
            </label>
            <label class="grid-control">
              Direction
              <select :value="direction" class="grid-input grid-input--select" @change="setDirection($event.target.value)">
                <option value="landscape">Landscape</option>
                <option value="portrait">Portrait</option>
              </select>
            </label>
          </div>
        </div>

        <div v-if="isFixedMode || isColumnsMode || isAutoMode" class="tile-design-group">
          <div class="tile-design-group-title">Dimensions</div>
          <div class="tile-design-grid">
            <label v-if="isFixedMode || isColumnsMode" class="grid-control">
              Columns
              <input type="number" :value="columns" min="1" max="10" class="grid-input" @change="setColumns(+$event.target.value)" />
            </label>
            <label v-if="isFixedMode" class="grid-control">
              Rows
              <input type="number" :value="rows" min="1" max="10" class="grid-input" @change="setRows(+$event.target.value)" />
            </label>
            <label v-if="isAutoMode" class="grid-control">
              Min Width
              <input
                type="number"
                :value="tileMinWidth"
                min="80"
                max="1600"
                class="grid-input"
                @change="setTileMinWidth(+$event.target.value)"
              />
            </label>
            <label v-if="isAutoMode" class="grid-control">
              Max Width
              <input
                type="number"
                :value="tileMaxWidth"
                min="80"
                max="1600"
                class="grid-input"
                @change="setTileMaxWidth(+$event.target.value)"
              />
            </label>
          </div>
        </div>

        <div class="tile-design-group">
          <div class="tile-design-group-title">Filters</div>
          <div class="tile-design-grid">
            <label class="grid-control">
              Filter Controls
              <select :value="tileFilterControlStyle" class="grid-input grid-input--select" @change="setTileFilterControlStyle($event.target.value)">
                <option value="dropdowns">Dropdowns</option>
                <option value="pills">Pills</option>
                <option value="segmented">Segmented</option>
              </select>
            </label>
            <label class="grid-control grid-control--checkbox">
              <span>Filter Reset</span>
              <label class="field-checkbox-label">
                <input type="checkbox" :checked="tileShowResetButton" @change="setTileShowResetButton($event.target.checked)" />
                <span>Show reset button</span>
              </label>
            </label>
          </div>
        </div>

        <div class="tile-design-group">
          <div class="tile-design-group-title">Info</div>
          <div class="tile-design-grid">
            <label class="grid-control">
              Top Info Align
              <select :value="tileTopInfoAlign" class="grid-input grid-input--select" @change="setTileTopInfoAlign($event.target.value)">
                <option value="left">Left</option>
                <option value="right">Right</option>
              </select>
            </label>
            <label class="grid-control">
              Bottom Info Align
              <select :value="tileBottomInfoAlign" class="grid-input grid-input--select" @change="setTileBottomInfoAlign($event.target.value)">
                <option value="left">Left</option>
                <option value="center">Center</option>
                <option value="right">Right</option>
              </select>
            </label>
            <label class="grid-control grid-control--checkbox">
              <span>Title Visibility</span>
              <label class="field-checkbox-label">
                <input type="checkbox" :checked="alwaysShowTitle" @change="setAlwaysShowTitle($event.target.checked)" />
                <span>Always show tile title</span>
              </label>
            </label>
          </div>
        </div>
      </div>
    </template>

    <template #admin-design-colors>
      <div class="admin-actions">
        <div class="grid-control color-link-control">
          <span class="control-label">Color 1</span>
          <VueColorPicker
            :model-value="hexOrDefault(checkerColor1, '#ffffff')"
            fallback-color="#ffffff"
            :preview-style="swatchStyle(resolveCheckerColor(checkerColor1, checkerColor1Variation), { rawColor: checkerColor1, linkKey: checkerColor1Link, treatEmptyAsHighContrast: true, baseRefColor: state.design.sectionBackgroundColor || '#ffffff', baseRefKey: 'sectionBackgroundColor', adminConfig: state.adminDesignConfig })"
            :size="28"
            @update:model-value="setCheckerColor1($event)"
          />
          <ColorLinkPicker :model-value="checkerColor1Link" :options="baseColorOptions" :button-size="24" @link="applyColorLink(1, $event)" />
          <select
            class="variation-select"
            :value="checkerColor1Variation"
            @change="setCheckerColorVariation(1, $event.target.value)"
          >
            <option v-for="variation in colorVariationOptions" :key="`checker1-${variation}`" :value="variation">
              {{ variation }}%
            </option>
          </select>
          <button v-if="checkerColor1" class="clear-btn" type="button" title="Clear" @click="setCheckerColor1(null)">&times;</button>
        </div>
        <div class="grid-control color-link-control">
          <span class="control-label">Color 2</span>
          <VueColorPicker
            :model-value="hexOrDefault(checkerColor2, '#000000')"
            fallback-color="#000000"
            :preview-style="swatchStyle(resolveCheckerColor(checkerColor2, checkerColor2Variation), { rawColor: checkerColor2, linkKey: checkerColor2Link, treatEmptyAsHighContrast: true, baseRefColor: state.design.sectionBackgroundColor || '#ffffff', baseRefKey: 'sectionBackgroundColor', adminConfig: state.adminDesignConfig })"
            :size="28"
            @update:model-value="setCheckerColor2($event)"
          />
          <ColorLinkPicker :model-value="checkerColor2Link" :options="baseColorOptions" :button-size="24" @link="applyColorLink(2, $event)" />
          <select
            class="variation-select"
            :value="checkerColor2Variation"
            @change="setCheckerColorVariation(2, $event.target.value)"
          >
            <option v-for="variation in colorVariationOptions" :key="`checker2-${variation}`" :value="variation">
              {{ variation }}%
            </option>
          </select>
          <button v-if="checkerColor2" class="clear-btn" type="button" title="Clear" @click="setCheckerColor2(null)">&times;</button>
        </div>
        <div class="grid-control color-link-control">
          <span class="control-label">Title Gradient</span>
          <VueColorPicker
            :model-value="hexOrDefault(titleGradientColor, '#000000')"
            fallback-color="#000000"
            :preview-style="swatchStyle(titleGradientBaseColor)"
            :size="28"
            @update:model-value="setTitleGradientColor($event)"
          />
          <ColorLinkPicker
            :model-value="titleGradientColorLink"
            :options="baseColorOptions"
            :button-size="24"
            @link="applyTitleGradientColorLink"
          />
          <button
            v-if="titleGradientColor"
            class="clear-btn"
            type="button"
            title="Clear"
            @click="setTitleGradientColor(null)"
          >
            &times;
          </button>
        </div>
      </div>
    </template>

    <template #admin-content>
      <div v-if="editing" class="editor">
            <details v-if="state.canAdminGeneral && !useProgramGigs" class="integration-import-panel">
              <summary class="integration-import-title">Import Images by Media Tag</summary>
              <div class="integration-import-content">
                <div class="import-controls-row">
                  <div class="import-field">
                    <label class="field-label">Media Tag</label>
                    <select v-model="selectedMediaTag" class="integration-select">
                      <option value="">-- Select a media tag --</option>
                      <option v-for="tag in mediaTagOptions" :key="`media-tag-${tag}`" :value="tag">
                        {{ tag }}
                      </option>
                    </select>
                  </div>
                  <div class="import-field import-field--compact">
                    <label class="field-label">Mode</label>
                    <select v-model="mediaTagImportMode" class="integration-select">
                      <option value="replace">Replace Tiles</option>
                      <option value="append">Append Tiles</option>
                    </select>
                  </div>
                  <button
                    type="button"
                    class="btn-secondary small"
                    @click="loadMediaTags"
                    :disabled="loadingMediaTags"
                  >
                    {{ loadingMediaTags ? "Loading..." : "Refresh" }}
                  </button>
                </div>
                <div class="import-actions">
                  <button
                    class="btn"
                    type="button"
                    @click="importTilesFromMediaTag"
                    :disabled="!selectedMediaTag || importingFromMediaTag"
                  >
                    {{ importingFromMediaTag ? "Importing..." : "Import Images from Media Tag" }}
                  </button>
                  <span v-if="mediaTagImportStatus" class="import-status" :class="mediaTagImportStatus.type">
                    {{ mediaTagImportStatus.message }}
                  </span>
                </div>
              </div>
            </details>
            <details v-if="showTileFiltersPanel" class="tile-filters-panel">
              <summary class="tile-filters-title">Filters</summary>
              <div class="tile-filters-content">
                <div class="tile-filter-info tile-filter-info--tip">
                  <p class="tile-filter-info-title">Option Metadata</p>
                  <p class="tile-filter-info-text">
                    Filters use centralized integration option metadata only. Enable
                    <span class="tile-filter-code">Collect options</span>
                    for the source field in the integration schema, then run the tile import or, when Use Program Gigs is enabled, the program gig import.
                    The target key list shows those metadata entries; mapped entries filter the mapped item field,
                    while unmapped entries stay disabled until the source is mapped.
                  </p>
                </div>

                <div v-if="draftFilters.length === 0" class="item-page-route item-page-route--empty">
                  No metadata-backed filters configured.
                </div>

                <draggable
                  v-else
                  :model-value="draftFilterListItems"
                  item-key="id"
                  tag="div"
                  class="tile-filters-list"
                  handle=".tile-filter-drag-handle"
                  ghost-class="tile-filters-row--ghost"
                  chosen-class="tile-filters-row--chosen"
                  drag-class="tile-filters-row--drag"
                  :animation="150"
                  @update:model-value="onDraftFilterDraggableUpdate"
                >
                  <template #item="{ element: item }">
                    <div
                      class="tile-filters-row"
                      :class="{ 'tile-filters-row--reset': item.type === 'reset' }"
                    >
                      <button
                        type="button"
                        class="tile-filter-drag-handle"
                        title="Drag to reorder"
                        aria-label="Drag filter row to reorder"
                      >
                        <font-awesome-icon :icon="faGripVertical" aria-hidden="true" />
                      </button>
                      <template v-if="item.type === 'reset'">
                        <span class="tile-filter-reset-row-label">Reset</span>
                        <span class="tile-filter-reset-row-type">Static</span>
                      </template>
                      <template v-else>
                        <div class="tile-filters-field">
                          <label class="field-label">Filter Name</label>
                          <input
                            class="field tile-filter-name-input"
                            type="text"
                            :value="item.filter.name"
                            placeholder="Filter name"
                            @input="updateDraftFilter(item.filterIndex, { name: $event.target.value })"
                          />
                        </div>
                        <div class="tile-filters-field">
                          <label class="field-label">Option Metadata Key</label>
                          <select
                            class="integration-select"
                            :value="item.filter.targetPath"
                            @change="updateDraftFilter(item.filterIndex, { targetPath: $event.target.value })"
                          >
                            <option value="" disabled>Select target key</option>
                            <option
                              v-if="item.filter.targetPath && !availableFilterTargetPathSet.has(item.filter.targetPath)"
                              :value="item.filter.targetPath"
                            >
                              {{ formatFilterLabel(item.filter.targetPath) }} (missing)
                            </option>
                            <option
                              v-for="option in availableFilterTargetOptions"
                              :key="`tile-filter-target-${item.id}-${option.path}-${option.label}`"
                              :value="option.path"
                              :disabled="option.disabled === true"
                            >
                              {{ option.label }}
                            </option>
                          </select>
                        </div>
                        <button
                          type="button"
                          class="btn-secondary btn-sm tile-filter-remove"
                          @click="removeDraftFilter(item.filterIndex)"
                        >
                          Remove
                        </button>
                      </template>
                    </div>
                  </template>
                </draggable>

                <div class="import-actions">
                  <button
                    type="button"
                    class="btn-secondary btn-sm"
                    :disabled="availableFilterTargetOptions.length === 0"
                    @click="addDraftFilter"
                  >
                    Add Filter
                  </button>
                </div>
              </div>
            </details>

            <div class="admin-actions admin-actions--tile-content-params">
              <label class="field-checkbox-label">
                <input type="checkbox" :checked="useProgramGigs" @change="setUseProgramGigs($event.target.checked)" />
                <span>Use Program gigs (live shared source)</span>
              </label>
            </div>

            <SectionListEditor
              :items="draftTiles"
              :selected-index="expandedItem"
              :add-label="t.add"
              :save-label="t.save"
              :remove-label="t.remove"
              clear-label="Clear All"
              :show-clear="!useProgramGigs"
              :show-add="!useProgramGigs"
              :show-remove="!useProgramGigs"
              :show-reorder-toggle="false"
              :allow-reorder="tileSortMode === 'manual'"
              :force-reorder-mode="tileManualReorderModeActive"
              :add-disabled="useProgramGigs || !canAddDraftTile"
              @select="expandedItem = $event"
              @add="addDraftTile"
              @save="saveTiles"
              @remove="removeDraftTile"
              @clear="clearAllTiles"
            >
              <template #control-primary>
                <div class="tile-sort-controls">
                  <label class="tile-sort-control">
                    <span>Sort</span>
                    <select :value="tileSortMode" class="grid-input grid-input--select" @change="setTileSortMode($event.target.value)">
                      <option value="manual">Manual order</option>
                      <option value="title">Title (A-Z)</option>
                    </select>
                  </label>
                  <label v-if="tileSortMode === 'manual'" class="tile-sort-reorder-toggle">
                    <input
                      type="checkbox"
                      :checked="tileManualReorderActive"
                      @change="setTileManualReorderActive($event.target.checked)"
                    />
                    <span>Reorder</span>
                  </label>
                </div>
              </template>
              <template #item="{ item, index }">
                <div class="item-thumb item-thumb--media">
                  <div
                    class="thumb-img-wrap"
                    :style="thumbRatioStyle"
                    :title="useProgramGigs ? 'Image is managed by Program source' : 'Click to browse images'"
                  >
                    <TransformedImage
                      v-if="resolveTileImageUrl(item, index, { fallback: false })"
                      :src="resolveTileImageUrl(item, index, { fallback: false })"
                      alt=""
                      class="thumb-img"
                      :ratio="aspectRatio"
                      :direction="direction"
                      :zoom="normalizeTileZoom(item.zoom)"
                      :focal-x="normalizeTileFocal(item.focalX)"
                      :focal-y="normalizeTileFocal(item.focalY)"
                      :rotation="normalizeTileRotation(item.rotation)"
                      :responsive-variants="resolveTileResponsiveVariants(item, index, { fallback: false })"
                      fit="cover"
                      loading="lazy"
                      decoding="async"
                    />
                    <div v-else class="thumb-empty">{{ index + 1 }}</div>
                  </div>
                  <span class="thumb-label">{{ item.title.de || item.title.en || `Tile ${index + 1}` }}</span>
                </div>
              </template>

              <template #editor="{ item, index }">
                  <ImageTransformEditor
                    class="tile-image-transform-editor"
                    :class="{ 'tile-image-transform-editor--program-source': programGigTransformControlsDisabled }"
                    :image-url="item.imageUrl"
                    :zoom="item.zoom"
                    :focal-x="item.focalX"
                    :focal-y="item.focalY"
                    :rotation="item.rotation"
                    :ratio="aspectRatio"
                    :direction="direction"
                    view-context="section_item"
                    :show-url-field="!useProgramGigs"
                    :show-image-actions="!useProgramGigs"
                    :allow-manual-url-edit="!useProgramGigs"
                    :allow-clear-image="!useProgramGigs"
                    :image-url-disabled="!useProgramGigs && isTileItemFieldLocked(index, 'imageUrl')"
                    :zoom-disabled="programGigTransformControlsDisabled || (!useProgramGigs && isTileItemFieldLocked(index, 'zoom'))"
                    :focal-disabled="programGigTransformControlsDisabled || (!useProgramGigs && (isTileItemFieldLocked(index, 'focalX') || isTileItemFieldLocked(index, 'focalY')))"
                    :rotation-disabled="programGigTransformControlsDisabled || (!useProgramGigs && isTileItemFieldLocked(index, 'rotation'))"
                    @update:image-url="(value) => setDraftImageUrl(index, value)"
                    @update:zoom="(value) => setDraftTransform(index, { zoom: value })"
                    @update:focal-x="(value) => setDraftTransform(index, { focalX: value })"
                    @update:focal-y="(value) => setDraftTransform(index, { focalY: value })"
                    @update:rotation="(value) => setDraftTransform(index, { rotation: value })"
                    @choose-image="openMediaPicker(index, { direct: false })"
                    @clear-image="setDraftImageUrl(index, '')"
                  />
                  <template v-if="!useProgramGigs">
                    <div class="tile-bilingual-row">
                      <div class="lang-section">
                        <div class="lang-header">
                          Title (DE)
                        </div>
                        <input
                          v-model="item.title.de"
                          class="field"
                          placeholder="Title (DE)"
                          :disabled="isTileItemFieldLocked(index, 'title.de')"
                          :title="isTileItemFieldLocked(index, 'title.de') ? integrationLockedHint : undefined"
                        />
                      </div>
                      <div class="lang-section">
                        <div class="lang-header">
                          Title (EN)
                        </div>
                        <input
                          v-model="item.title.en"
                          class="field"
                          placeholder="Title (EN)"
                          :disabled="isTileItemFieldLocked(index, 'title.en')"
                          :title="isTileItemFieldLocked(index, 'title.en') ? integrationLockedHint : undefined"
                        />
                      </div>
                    </div>
                    <div class="tile-bilingual-row">
                      <div class="lang-section">
                        <div class="lang-header">
                          Subtitle (DE)
                        </div>
                        <input
                          v-model="item.subtitle.de"
                          class="field"
                          placeholder="Subtitle (DE)"
                          :disabled="isTileItemFieldLocked(index, 'subtitle.de')"
                          :title="isTileItemFieldLocked(index, 'subtitle.de') ? integrationLockedHint : undefined"
                        />
                      </div>
                      <div class="lang-section">
                        <div class="lang-header">
                          Subtitle (EN)
                        </div>
                        <input
                          v-model="item.subtitle.en"
                          class="field"
                          placeholder="Subtitle (EN)"
                          :disabled="isTileItemFieldLocked(index, 'subtitle.en')"
                          :title="isTileItemFieldLocked(index, 'subtitle.en') ? integrationLockedHint : undefined"
                        />
                      </div>
                    </div>
                    <div class="lang-section">
                      <div class="lang-header">
                        Location
                      </div>
                      <input
                        v-model="item.location"
                        class="field"
                        placeholder="Main Stage"
                        :disabled="isTileItemFieldLocked(index, 'location')"
                        :title="isTileItemFieldLocked(index, 'location') ? integrationLockedHint : undefined"
                      />
                    </div>
                    <div class="lang-section">
                      <div class="lang-header">
                        Date Time
                      </div>
                      <VueDatePicker
                        :model-value="tileDateTimeModel(item.dateTime)"
                        :enable-time-picker="true"
                        :is-24="true"
                        :minutes-increment="15"
                        :clearable="true"
                        :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
                        placeholder="Select date & time"
                        auto-apply
                        class="tile-datetime-picker"
                        :disabled="isTileItemFieldLocked(index, 'dateTime')"
                        @update:model-value="setDraftDateTime(index, $event)"
                      />
                    </div>
                  </template>
                  <template v-else>
                    <div class="field-row">
                      <label class="field-label">Program Item</label>
                      <div class="item-page-route">
                        <span>{{ localizedText(resolveTileTitle(item)) || `Tile ${index + 1}` }}</span>
                      </div>
                    </div>
                    <div class="item-field-actions">
                      <button
                        class="btn-secondary small"
                        type="button"
                        :disabled="!canOpenTileItemPage(item)"
                        @click.stop="openTileItemPage(item)"
                      >
                        Open Item Page
                      </button>
                      <button
                        class="btn-secondary small"
                        type="button"
                        :disabled="!canOpenTileIntegrationReviewItem(item)"
                        @click.stop="openTileIntegrationReviewItem(item)"
                      >
                        Open Review Item
                      </button>
                    </div>
                  </template>
              </template>
              <template #footer-actions="{ item }">
                <div v-if="!useProgramGigs" class="item-field-actions">
                  <button
                    class="btn-secondary small"
                    type="button"
                    :disabled="!canOpenTileItemPage(item)"
                    @click.stop="openTileItemPage(item)"
                  >
                    Open Item Page
                  </button>
                </div>
              </template>
            </SectionListEditor>

            <label class="field-checkbox-label tile-fallback-toggle">
              <input
                type="checkbox"
                :checked="tileFallbackOverrideEnabled"
                @change="setTileFallbackOverrideEnabled($event.target.checked)"
              />
              <span>Use custom fallback images for this tile section</span>
            </label>

            <FallbackImageSelector
              v-if="tileFallbackOverrideEnabled"
              :images="section?.filterFallbackImages || []"
              :media-tag="filterFallbackMediaTag"
              :legacy-image-url="section?.filterFallbackImageUrl || ''"
              :zoom="filterFallbackZoom"
              :focal-x="filterFallbackFocalX"
              :focal-y="filterFallbackFocalY"
              :rotation="filterFallbackRotation"
              :aspect-ratio="aspectRatio"
              :direction="direction"
              source-context="section.tiles.fallback.image"
              description="Images shown when tile item images are empty, and in empty slots when a filter leaves the last row incomplete."
              @apply-images="applyFallbackImages"
              @clear-images="clearFallbackImages"
              @update-transform="setFallbackTransform"
            />
      </div>
    </template>
  </SectionBase>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "../../store/store.js";
import * as api from "../../services/api.js";
import { useListEditorMediaPicker } from "../../composables/useListEditorMediaPicker.js";
import {
  buildColorLinkOptions,
  resolveLinkedColor,
  HIGH_CONTRAST_TOKEN,
  resolveHighContrastColorForBackground,
} from "../../utils/colorLinkOptions.js";
import {
  COLOR_VARIATION_OPTIONS,
  DEFAULT_COLOR_VARIATION,
  applyColorVariation,
  normalizeColorVariation,
} from "../../utils/colorVariations.js";
import { clamp, normalizeRatio, ratioToCss } from "../../utils/imageTransform.js";
import {
  resolveBackendResponsiveImagePayload,
  resolveBackendResponsiveImageVariants,
} from "../../utils/responsiveImages.js";
import {
  normalizeFallbackImageConfig,
  resolveEffectiveFallbackImageConfig,
  resolveFallbackImageForIndex,
} from "../../utils/fallbackImages.js";
import { isSectionIntegrationFieldLocked } from "../../utils/sectionIntegrationFieldState.js";
import {
  DATE_PICKER_DATE_TIME_DISPLAY_FORMATS,
  formatInstantInServerTimezone,
  formatServerDateOnly,
  formatServerWallTime,
  parseServerWallDateTimeParts,
  serverWallDateTimeToLocalDate,
} from "../../utils/revisionTime.js";
import { VueDatePicker } from "@vuepic/vue-datepicker";
import "@vuepic/vue-datepicker/dist/main.css";

import SectionBase from "./_BaseSection.vue";
import { getBaseSectionSwatchStyle } from "./_baseSectionSwatchStyle.js";
import SectionListEditor from "../admin/section-editor/SectionListEditor.vue";
import FallbackImageSelector from "../admin/section-editor/FallbackImageSelector.vue";
import MediaLibrary from "../ui/MediaLibrary.vue";
import ImageTransformEditor from "../ui/ImageTransformEditor.vue";
import TransformedImage from "../ui/TransformedImage.vue";
import ColorLinkPicker from "../ui/color/ColorLinkPicker.vue";
import VueColorPicker from "../ui/color/VueColorPicker.vue";
import TileFilterDropdown from "../ui/TileFilterDropdown.vue";
import draggable from "vuedraggable";
import { faChevronRight, faGripVertical } from "@fortawesome/free-solid-svg-icons";

const props = defineProps({
  sectionKey: { type: String, default: "tiles" },
  sectionData: { type: Object, default: null },
});

const {
  state,
  t,
  localizedText,
  updateSection,
  saveSectionByKey,
  fetchProgramSharedData,
  getEffectiveViewportDevice,
} = useStore();
const router = useRouter();
const FILTER_OPTION_COLLECTION_PREFIXES = ["$root", "tiles", "gigs", "items"];
const FILTER_RESET_CONTROL_ID = "__reset__";
const PROGRAM_IMPORT_SOURCE_KEY = "__integration_source_id";
const TILE_FILTER_CONTROL_STYLES = new Set(["dropdowns", "pills", "segmented"]);
const TILE_TOP_INFO_ALIGNS = new Set(["left", "right"]);
const TILE_BOTTOM_INFO_ALIGNS = new Set(["left", "center", "right"]);
const integrationLockedHint = "Managed by integration import.";

function normalizeTileFilterControlStyle(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return TILE_FILTER_CONTROL_STYLES.has(normalized) ? normalized : "dropdowns";
}

function normalizeTileTopInfoAlign(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return TILE_TOP_INFO_ALIGNS.has(normalized) ? normalized : "right";
}

function normalizeTileBottomInfoAlign(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return TILE_BOTTOM_INFO_ALIGNS.has(normalized) ? normalized : "left";
}

const effectiveKey = computed(() => props.sectionKey);
const currentAdminTab = computed(() => state.sectionAdminActiveTabs?.[effectiveKey.value] || "");

const section = computed(() => {
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});
function tileFieldPath(index, fieldPath) {
  const normalizedFieldPath = String(fieldPath || "").trim();
  const numericIndex = Number(index);
  const resolvedIndex = Number.isInteger(numericIndex) && numericIndex >= 0 ? numericIndex : 0;
  return normalizedFieldPath
    ? `tiles[${resolvedIndex}].${normalizedFieldPath}`
    : `tiles[${resolvedIndex}]`;
}

function isTileItemFieldLocked(index, fieldPath, options = {}) {
  return state.isAdmin && isSectionIntegrationFieldLocked(section.value, tileFieldPath(index, fieldPath), options);
}

function tokenizeObjectPath(path) {
  const tokens = [];
  String(path || "")
    .split(".")
    .forEach((rawPart) => {
      let part = String(rawPart || "");
      if (!part) return;
      while (part.includes("[")) {
        const bracketIndex = part.indexOf("[");
        const head = part.slice(0, bracketIndex);
        if (head) tokens.push(head);
        const rest = part.slice(bracketIndex + 1);
        const closeIndex = rest.indexOf("]");
        if (closeIndex < 0) {
          part = rest;
          break;
        }
        const indexText = rest.slice(0, closeIndex).trim();
        const indexValue = Number.parseInt(indexText, 10);
        if (Number.isFinite(indexValue)) tokens.push(indexValue);
        part = rest.slice(closeIndex + 1);
        if (part.startsWith(".")) part = part.slice(1);
      }
      if (part) tokens.push(part);
    });
  return tokens;
}

function deepGetPathValue(source, path) {
  if (!source || typeof source !== "object") return undefined;
  const tokens = tokenizeObjectPath(path);
  if (!tokens.length) return undefined;
  let current = source;
  for (const token of tokens) {
    if (typeof token === "number") {
      if (!Array.isArray(current) || token < 0 || token >= current.length) return undefined;
      current = current[token];
      continue;
    }
    if (!current || typeof current !== "object" || !(token in current)) return undefined;
    current = current[token];
  }
  return current;
}

function normalizeFilterValue(value, depth = 0) {
  if (depth > 4) return "";
  if (value == null) return "";
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value).trim();
  if (value && typeof value === "object" && ("de" in value || "en" in value)) {
    const de = String(value?.de || "").trim();
    const en = String(value?.en || "").trim();
    return de || en;
  }
  if (value && typeof value === "object") {
    const preferredObjectKeys = [
      "name",
      "title",
      "label",
      "text",
      "stage_name",
      "stageName",
      "value",
    ];
    for (const key of preferredObjectKeys) {
      if (!Object.prototype.hasOwnProperty.call(value, key)) continue;
      const nestedValue = normalizeFilterValue(value[key], depth + 1);
      if (nestedValue) return nestedValue;
    }
  }
  return "";
}

function normalizeFilterStringOptions(rawOptions) {
  if (!Array.isArray(rawOptions)) return [];
  const seen = new Set();
  const normalized = [];
  rawOptions.forEach((entry) => {
    const value = normalizeFilterValue(entry);
    if (!value || seen.has(value)) return;
    seen.add(value);
    normalized.push(value);
  });
  return normalized;
}

function normalizeIntegrationOptions(rawOptions) {
  if (!rawOptions || typeof rawOptions !== "object" || Array.isArray(rawOptions)) return {};
  const normalized = {};
  Object.entries(rawOptions).forEach(([key, value]) => {
    const normalizedKey = String(key || "").trim();
    if (!normalizedKey || !Array.isArray(value)) return;
    normalized[normalizedKey] = value;
  });
  return normalized;
}

function collectFilterOptionPathAliases(path) {
  const aliases = new Set();
  const addAlias = (candidate) => {
    const normalizedCandidate = String(candidate || "").trim();
    if (normalizedCandidate) aliases.add(normalizedCandidate);
  };

  const normalizedPath = String(path || "").trim();
  addAlias(normalizedPath);
  if (!normalizedPath) return [];

  FILTER_OPTION_COLLECTION_PREFIXES.forEach((prefix) => {
    if (normalizedPath.startsWith(`${prefix}.`)) {
      addAlias(normalizedPath.slice(prefix.length + 1));
    }
  });

  if (!normalizedPath.includes(".")) {
    FILTER_OPTION_COLLECTION_PREFIXES.forEach((prefix) => {
      addAlias(`${prefix}.${normalizedPath}`);
    });
  }

  return Array.from(aliases);
}

function stripFilterOptionCollectionPrefix(path) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return "";
  for (const prefix of FILTER_OPTION_COLLECTION_PREFIXES) {
    if (normalizedPath.startsWith(`${prefix}.`)) {
      return normalizedPath.slice(prefix.length + 1);
    }
  }
  return normalizedPath;
}

function filterOptionPathsMatch(leftPath, rightPath) {
  const leftAliases = new Set(collectFilterOptionPathAliases(leftPath));
  if (leftAliases.size === 0) return false;
  return collectFilterOptionPathAliases(rightPath).some((alias) => leftAliases.has(alias));
}

function resolveFirstObjectValue(values = []) {
  const objects = (Array.isArray(values) ? values : [])
    .filter((value) => value && typeof value === "object" && !Array.isArray(value));
  return objects.find((value) => Object.keys(value).length > 0) || objects[0] || {};
}

function hasImportedIntegrationCacheValue(value, depth = 0) {
  if (value == null || depth > 5) return false;
  if (Array.isArray(value)) {
    return value.some((entry) => hasImportedIntegrationCacheValue(entry, depth + 1));
  }
  if (typeof value === "object") {
    return Object.values(value).some((entry) => hasImportedIntegrationCacheValue(entry, depth + 1));
  }
  if (typeof value === "string") return value.trim().length > 0;
  return true;
}

function hasImportedIntegrationCacheOptions(rawOptions) {
  return Object.values(normalizeIntegrationOptions(rawOptions))
    .some((values) => Array.isArray(values) && values.length > 0);
}

function hasImportedIntegrationCacheData(cacheState) {
  if (!cacheState || typeof cacheState !== "object" || Array.isArray(cacheState)) return false;
  return (
    hasImportedIntegrationCacheValue(cacheState.applied_values)
    || hasImportedIntegrationCacheOptions(cacheState.options)
  );
}

function formatFilterLabel(path) {
  return String(path || "")
    .replace(/\[(\d+)\]/g, " $1 ")
    .replace(/[._]/g, " ")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/(^|\s)\S/g, (value) => value.toUpperCase());
}

function inferFilterOptionType(value) {
  if (value == null) return "empty";
  if (Array.isArray(value)) return "list";
  if (typeof value === "number") return "number";
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "string") {
    const normalized = value.trim();
    if (/^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$/.test(normalized)) {
      return "date";
    }
    return "text";
  }
  if (typeof value === "object") {
    if ("de" in value || "en" in value) return "text";
    return "object";
  }
  return "text";
}

function filterTypeLabel(type) {
  const normalized = String(type || "").trim().toLowerCase();
  if (normalized === "number") return "Number";
  if (normalized === "boolean") return "Boolean";
  if (normalized === "list") return "List";
  if (normalized === "date") return "Date";
  if (normalized === "object") return "Object";
  if (normalized === "empty") return "Empty";
  return "Text";
}

function addFilterFieldOption(collector, path, type) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath || !(collector instanceof Map)) return;
  const normalizedType = String(type || "").trim().toLowerCase() || "text";
  if (!collector.has(normalizedPath)) {
    collector.set(normalizedPath, normalizedType);
    return;
  }
  const existingType = String(collector.get(normalizedPath) || "").trim().toLowerCase();
  if (normalizedType === "list" && existingType !== "list") {
    collector.set(normalizedPath, normalizedType);
    return;
  }
  if (!existingType || existingType === "empty") {
    collector.set(normalizedPath, normalizedType);
  }
}

function collectFilterTargetPathsFromValue(value, pathPrefix, collector, depth = 0) {
  if (depth > 6 || value == null) {
    if (pathPrefix && value == null) {
      addFilterFieldOption(collector, pathPrefix, "empty");
    }
    return;
  }
  if (Array.isArray(value)) {
    if (pathPrefix) {
      addFilterFieldOption(collector, pathPrefix, "list");
    }
    return;
  }
  if (typeof value === "object") {
    if ("de" in value || "en" in value) {
      if (pathPrefix) addFilterFieldOption(collector, pathPrefix, "text");
      return;
    }
    Object.entries(value).forEach(([key, nested]) => {
      const normalizedKey = String(key || "").trim();
      if (!normalizedKey || normalizedKey.startsWith("_")) return;
      const nextPath = pathPrefix ? `${pathPrefix}.${normalizedKey}` : normalizedKey;
      collectFilterTargetPathsFromValue(nested, nextPath, collector, depth + 1);
    });
    return;
  }
  if (pathPrefix) addFilterFieldOption(collector, pathPrefix, inferFilterOptionType(value));
}

function collectFilterOptionPathsFromOptions(rawOptions, collector) {
  const normalizedOptions = normalizeIntegrationOptions(rawOptions);
  Object.keys(normalizedOptions).forEach((sourcePath) => {
    const normalizedSourcePath = String(sourcePath || "").trim();
    if (!normalizedSourcePath) return;
    addFilterFieldOption(collector, normalizedSourcePath, "list");
  });
}

function mapCollectorToFilterFieldOptions(collector) {
  if (!(collector instanceof Map)) return [];
  return Array.from(collector.entries())
    .map(([path, type]) => ({
      path: String(path || "").trim(),
      type: String(type || "").trim().toLowerCase() || "text",
      label: `${formatFilterLabel(path)} (${filterTypeLabel(type)})`,
    }))
    .filter((entry) => entry.path)
    .sort((left, right) => left.path.localeCompare(right.path));
}

function normalizeMappingRowsForCollection(mappingValue, preferredCollectionPaths = []) {
  const rawMappingsByCollection = mappingValue?.list_mappings_by_collection_path
    ?? {};
  if (!rawMappingsByCollection || typeof rawMappingsByCollection !== "object") return [];
  const normalizedPreferred = (Array.isArray(preferredCollectionPaths) ? preferredCollectionPaths : [])
    .map((entry) => String(entry || "").trim())
    .filter(Boolean);
  const matchedRows = [];
  Object.entries(rawMappingsByCollection).forEach(([collectionPath, rows]) => {
    if (!Array.isArray(rows)) return;
    const normalizedCollectionPath = String(collectionPath || "").trim();
    if (!normalizedCollectionPath) return;
    if (normalizedPreferred.length > 0) {
      const matchesPreferred = normalizedPreferred.some((preferredPath) =>
        normalizedCollectionPath === preferredPath || normalizedCollectionPath.endsWith(`.${preferredPath}`)
      );
      if (!matchesPreferred) return;
    }
    rows.forEach((row) => {
      const sourcePath = String(row?.source_path || "").trim();
      const targetPath = String(row?.target_path || "").trim();
      if (!sourcePath || !targetPath) return;
      matchedRows.push({ sourcePath: sourcePath, targetPath: targetPath });
    });
  });
  return matchedRows;
}

function resolveTargetPathFromMappingRows(mappingRows, sourcePath) {
  const normalizedSourcePath = String(sourcePath || "").trim();
  if (!normalizedSourcePath || !Array.isArray(mappingRows)) return "";
  const row = mappingRows.find((entry) =>
    String(entry?.sourcePath || "").trim() === normalizedSourcePath
    && String(entry?.targetPath || "").trim()
  );
  if (row) return String(row.targetPath || "").trim();

  const aliasRow = mappingRows.find((entry) =>
    filterOptionPathsMatch(entry?.sourcePath, normalizedSourcePath)
    && String(entry?.targetPath || "").trim()
  );
  return aliasRow ? String(aliasRow.targetPath || "").trim() : "";
}

function resolveSourcePathFromMappingRows(mappingRows, targetPath) {
  const normalizedTarget = String(targetPath || "").trim();
  if (!normalizedTarget || !Array.isArray(mappingRows)) return "";
  const row = mappingRows.find((entry) =>
    String(entry?.targetPath || "").trim() === normalizedTarget
    && String(entry?.sourcePath || "").trim()
  );
  if (row) return String(row.sourcePath || "").trim();

  const aliasRow = mappingRows.find((entry) =>
    filterOptionPathsMatch(entry?.targetPath, normalizedTarget)
    && String(entry?.sourcePath || "").trim()
  );
  return aliasRow ? String(aliasRow.sourcePath || "").trim() : "";
}

const isTemplateBuilderPage = computed(() =>
  String(state.pageSlug || "").startsWith("__template_")
);

const baseColorOptions = computed(() => {
  return buildColorLinkOptions(state.design, {
    parameterConfigs: state.adminDesignConfig?.parameters,
  });
});

const checkerColor1Link = computed(() => {
  const key = effectiveKey.value;
  return state.sectionsData?.[key]?.checkerColor1Link ?? section.value?.checkerColor1Link ?? null;
});
const checkerColor2Link = computed(() => {
  const key = effectiveKey.value;
  return state.sectionsData?.[key]?.checkerColor2Link ?? section.value?.checkerColor2Link ?? null;
});
const checkerColor1Variation = computed(() => {
  const key = effectiveKey.value;
  const fromState = state.sectionsData?.[key]?.checkerColor1Variation;
  const value = fromState !== undefined ? fromState : section.value?.checkerColor1Variation;
  return normalizeColorVariation(value);
});
const checkerColor2Variation = computed(() => {
  const key = effectiveKey.value;
  const fromState = state.sectionsData?.[key]?.checkerColor2Variation;
  const value = fromState !== undefined ? fromState : section.value?.checkerColor2Variation;
  return normalizeColorVariation(value);
});
const titleGradientColorLink = computed(() => {
  const key = effectiveKey.value;
  return state.sectionsData?.[key]?.titleGradientColorLink ?? section.value?.titleGradientColorLink ?? null;
});
const titleGradientColor = computed(() => {
  const key = effectiveKey.value;
  const fromState = state.sectionsData?.[key]?.titleGradientColor;
  if (fromState !== undefined) return fromState ?? null;
  return section.value?.titleGradientColor ?? null;
});
const colorVariationOptions = COLOR_VARIATION_OPTIONS;

function resolveBaseColor(linkKey) {
  return resolveLinkedColor(state.design, linkKey, state.adminDesignConfig?.parameters);
}

watch(() => [state.design.primaryColor, state.design.secondaryColor, state.design.backgroundColor, state.design.accentColor, state.design.sectionBackgroundColor, state.design.highContrastDark, state.design.highContrastLight], () => {
  const key = effectiveKey.value;
  const link1 = checkerColor1Link.value;
  const link2 = checkerColor2Link.value;
  const titleLink = titleGradientColorLink.value;
  if (link1) {
    const resolved = resolveBaseColor(link1);
    if (resolved !== null) updateSection(key, { checkerColor1: resolved });
  }
  if (link2) {
    const resolved = resolveBaseColor(link2);
    if (resolved !== null) updateSection(key, { checkerColor2: resolved });
  }
  if (titleLink) {
    const resolved = resolveBaseColor(titleLink);
    if (resolved !== null) updateSection(key, { titleGradientColor: resolved });
  }
});

function hexOrDefault(val, fallback) {
  if (val && /^#[0-9a-fA-F]{6}$/.test(val)) return val;
  return fallback;
}

function swatchStyle(previewColor, options = {}) {
  return getBaseSectionSwatchStyle(state.design, previewColor, options);
}

function contrastColor(bgHex, backgroundBaseKey = null) {
  return resolveHighContrastColorForBackground(
    state.design,
    state.adminDesignConfig,
    {
      backgroundColor: bgHex,
      backgroundBaseKey,
    }
  );
}

function resolveCheckerColor(val, variation = DEFAULT_COLOR_VARIATION) {
  let resolved;
  if (!val || val === HIGH_CONTRAST_TOKEN) {
    const sectionBg = state.design.sectionBackgroundColor || "#ffffff";
    resolved = contrastColor(sectionBg, "sectionBackgroundColor");
  } else {
    resolved = val;
  }
  return applyColorVariation(resolved, variation);
}

function hexToRgba(hex, alpha) {
  const normalized = String(hex || "").trim().replace("#", "");
  const safeAlpha = Number.isFinite(Number(alpha)) ? Number(alpha) : 1;
  if (!/^[0-9a-fA-F]{6}$/.test(normalized)) {
    return `rgba(0, 0, 0, ${safeAlpha})`;
  }
  const r = parseInt(normalized.slice(0, 2), 16);
  const g = parseInt(normalized.slice(2, 4), 16);
  const b = parseInt(normalized.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${safeAlpha})`;
}

const titleGradientBaseColor = computed(() => {
  if (titleGradientColor.value && titleGradientColor.value !== HIGH_CONTRAST_TOKEN) {
    return titleGradientColor.value;
  }
  const sectionBg = state.design.sectionBackgroundColor || "#ffffff";
  return contrastColor(sectionBg, "sectionBackgroundColor");
});

const tileTitleGradientBackground = computed(() => {
  const base = titleGradientBaseColor.value || "#000000";
  return `linear-gradient(to top, ${hexToRgba(base, 0.94)} 0%, ${hexToRgba(base, 0.38)} 60%, rgba(0, 0, 0, 0) 100%)`;
});

const tileTitleTextColor = computed(() => {
  const base = titleGradientBaseColor.value || "#000000";
  return contrastColor(base);
});

function applyColorLink(which, baseKey) {
  const resolved = resolveBaseColor(baseKey);
  if (which === 1) {
    updateSection(effectiveKey.value, { checkerColor1: resolved, checkerColor1Link: baseKey });
  } else if (which === 2) {
    updateSection(effectiveKey.value, { checkerColor2: resolved, checkerColor2Link: baseKey });
  }
}

function applyTitleGradientColorLink(baseKey) {
  const resolved = resolveBaseColor(baseKey);
  updateSection(
    effectiveKey.value,
    { titleGradientColor: resolved, titleGradientColorLink: baseKey },
    { revisionKind: "design" }
  );
}

function setCheckerColorVariation(which, variation) {
  const normalized = normalizeColorVariation(variation);
  const key = which === 1 ? "checkerColor1Variation" : "checkerColor2Variation";
  updateSection(effectiveKey.value, {
    [key]: normalized === DEFAULT_COLOR_VARIATION ? null : normalized,
  });
}

function normalizeTileZoom(value) {
  return clamp(value, 1, 4, 1);
}

function normalizeTileFocal(value) {
  return clamp(value, 0, 100, 50);
}

function normalizeTileRotation(value) {
  return clamp(value, -180, 180, 0);
}

const DEFAULT_TILE_IMAGE_TRANSFORM = {
  zoom: 1,
  focalX: 50,
  focalY: 50,
  rotation: 0,
};

function firstFiniteFieldValue(source, keys = []) {
  if (!source || typeof source !== "object") return undefined;
  for (const key of keys) {
    if (!Object.prototype.hasOwnProperty.call(source, key)) continue;
    const value = Number(source[key]);
    if (Number.isFinite(value)) return value;
  }
  return undefined;
}

function resolveProgramGigImageTransform(gig) {
  return {
    zoom: normalizeTileZoom(firstFiniteFieldValue(gig, ["image_zoom", "imageZoom"])),
    focalX: normalizeTileFocal(firstFiniteFieldValue(gig, ["image_focal_x", "imageFocalX"])),
    focalY: normalizeTileFocal(firstFiniteFieldValue(gig, ["image_focal_y", "imageFocalY"])),
    rotation: normalizeTileRotation(firstFiniteFieldValue(gig, ["image_rotation", "imageRotation"])),
  };
}

function resolveProgramTileImageTransform(gig) {
  return shouldUseProgramGigImageTransform.value
    ? resolveProgramGigImageTransform(gig)
    : { ...DEFAULT_TILE_IMAGE_TRANSFORM };
}

const TILE_GRID_MIN_WIDTH = 80;
const TILE_GRID_MAX_WIDTH = 1600;
const DEFAULT_TILE_MIN_WIDTH = 220;
const DEFAULT_TILE_MAX_WIDTH = 360;

function normalizeTileGridWidth(value, fallback = DEFAULT_TILE_MIN_WIDTH) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(TILE_GRID_MIN_WIDTH, Math.min(TILE_GRID_MAX_WIDTH, Math.round(parsed)));
}

function normalizeGridMode(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "fixed" || normalized === "columns" || normalized === "auto") return normalized;
  return "auto";
}

function normalizeTileSortMode(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return normalized === "manual" ? "manual" : "title";
}

const gridMode = computed(() => normalizeGridMode(section.value?.gridMode || "auto"));
const tileSortMode = computed(() =>
  normalizeTileSortMode(section.value?.tileSortMode || "title")
);
const isFixedMode = computed(() => gridMode.value === "fixed");
const isColumnsMode = computed(() => gridMode.value === "columns");
const isAutoMode = computed(() => gridMode.value === "auto");
const columns = computed(() => Math.max(1, Math.min(10, Number(section.value?.columns) || 3)));
const rows = computed(() => Math.max(1, Math.min(10, Number(section.value?.rows) || 2)));
const tileMinWidth = computed(() =>
  normalizeTileGridWidth(section.value?.tileMinWidth, DEFAULT_TILE_MIN_WIDTH)
);
const tileMaxWidth = computed(() =>
  Math.max(
    tileMinWidth.value,
    normalizeTileGridWidth(section.value?.tileMaxWidth, DEFAULT_TILE_MAX_WIDTH),
  )
);
const aspectRatio = computed(() => normalizeRatio(section.value?.aspectRatio || "1:1", "1:1"));
const shouldUseProgramGigImageTransform = computed(() => aspectRatio.value === "1:1");
const direction = computed(() => (section.value?.direction === "portrait" ? "portrait" : "landscape"));
const alwaysShowTitle = computed(() =>
  Boolean(section.value?.alwaysShowTitle ?? false)
);
const tileShowResetButton = computed(() =>
  Boolean(section.value?.tileShowResetButton ?? false)
);
const tileTopInfoAlign = computed(() =>
  normalizeTileTopInfoAlign(section.value?.tileTopInfoAlign)
);
const tileBottomInfoAlign = computed(() =>
  normalizeTileBottomInfoAlign(section.value?.tileBottomInfoAlign)
);
const checkerColor1 = computed(() => {
  const key = effectiveKey.value;
  const fromState = state.sectionsData?.[key]?.checkerColor1;
  if (fromState !== undefined) return fromState ?? null;
  return section.value?.checkerColor1 ?? null;
});
const checkerColor2 = computed(() => {
  const key = effectiveKey.value;
  const fromState = state.sectionsData?.[key]?.checkerColor2;
  if (fromState !== undefined) return fromState ?? null;
  return section.value?.checkerColor2 ?? null;
});

function checkerBg(index) {
  const r = tileRow(index);
  const c = tileCol(index);
  const isEven = (r + c) % 2 === 0;
  return isEven
    ? resolveCheckerColor(checkerColor1.value, checkerColor1Variation.value)
    : resolveCheckerColor(checkerColor2.value, checkerColor2Variation.value);
}

function setCheckerColor1(val) {
  updateSection(effectiveKey.value, { checkerColor1: val, checkerColor1Link: null });
}
function setCheckerColor2(val) {
  updateSection(effectiveKey.value, { checkerColor2: val, checkerColor2Link: null });
}

function setTitleGradientColor(val) {
  updateSection(
    effectiveKey.value,
    { titleGradientColor: val, titleGradientColorLink: null },
    { revisionKind: "design" }
  );
}

const useProgramGigs = computed(() =>
  Boolean(section.value?.useProgramGigs ?? true)
);
const programGigTransformControlsDisabled = computed(() =>
  useProgramGigs.value && shouldUseProgramGigImageTransform.value
);
const tileMoreLabel = computed(() => (state.lang === "de" ? "mehr" : "more"));
const tileFilterControlStyle = computed(() =>
  normalizeTileFilterControlStyle(section.value?.filterControlStyle)
);

const sectionIntegrationMapping = computed(() => {
  const mapping = section.value?.sectionIntegrationMapping;
  return mapping && typeof mapping === "object" ? mapping : {};
});
const sectionIntegrationCacheState = computed(() => {
  return resolveFirstObjectValue([
    section.value?.sectionIntegrationMappingCacheState,
    section.value?.section_integration_mapping_cache_state,
  ]);
});
const programSectionIntegrationMapping = computed(() => {
  return resolveFirstObjectValue([
    state.programSharedGigsIntegrationMapping,
  ]);
});
const programGigsIntegrationCacheState = computed(() => {
  return resolveFirstObjectValue([
    state.programSharedGigsIntegrationMappingCacheState,
  ]);
});
const tileIntegrationPreviewFieldOptions = ref([]);
const programIntegrationPreviewFieldOptions = ref([]);
const integrationFilterOptionsCache = new Map();

function resolveSelectedIntegrationIdFromMapping(mappingValue) {
  if (!mappingValue || typeof mappingValue !== "object") return "";
  return String(mappingValue.selected_integration_id || "").trim();
}

async function fetchIntegrationPreviewFieldOptions(integrationId) {
  const normalizedIntegrationId = String(integrationId || "").trim();
  if (!normalizedIntegrationId) return [];
  if (integrationFilterOptionsCache.has(normalizedIntegrationId)) {
    return integrationFilterOptionsCache.get(normalizedIntegrationId) || [];
  }
  try {
    const previewResponse = await api.getIntegrationDataPreview(normalizedIntegrationId);
    const collector = new Map();
    collectFilterTargetPathsFromValue(previewResponse?.preview_item, "", collector, 0);
    collectFilterOptionPathsFromOptions(previewResponse?.options, collector);
    const options = mapCollectorToFilterFieldOptions(collector);
    integrationFilterOptionsCache.set(normalizedIntegrationId, options);
    return options;
  } catch (error) {
    console.error("Failed to load integration preview fields for tile filters:", error);
    integrationFilterOptionsCache.set(normalizedIntegrationId, []);
    return [];
  }
}

async function loadFilterSourceIntegrationFieldOptions() {
  if (!state.canAdminGeneral) {
    tileIntegrationPreviewFieldOptions.value = [];
    programIntegrationPreviewFieldOptions.value = [];
    return;
  }

  const tileIntegrationId = resolveSelectedIntegrationIdFromMapping(sectionIntegrationMapping.value);
  const programIntegrationId = resolveSelectedIntegrationIdFromMapping(programSectionIntegrationMapping.value);
  const [tileOptions, programOptions] = await Promise.all([
    fetchIntegrationPreviewFieldOptions(tileIntegrationId),
    fetchIntegrationPreviewFieldOptions(programIntegrationId),
  ]);
  tileIntegrationPreviewFieldOptions.value = tileOptions;
  programIntegrationPreviewFieldOptions.value = programOptions;
}

function normalizeTileFilterDefinitions(rawFilters, { allowScope = false } = {}) {
  if (!Array.isArray(rawFilters)) return [];
  const seenIds = new Set();
  return rawFilters
    .map((entry, index) => {
      if (!entry || typeof entry !== "object") return null;
      let id = String(entry.id || "").trim();
      if (!id) id = `filter-${index + 1}`;
      if (seenIds.has(id)) {
        let suffix = 2;
        let candidate = `${id}-${suffix}`;
        while (seenIds.has(candidate)) {
          suffix += 1;
          candidate = `${id}-${suffix}`;
        }
        id = candidate;
      }
      seenIds.add(id);

      const hasTargetPathKey = Object.prototype.hasOwnProperty.call(entry, "targetPath");
      const targetPathRaw = hasTargetPathKey ? entry.targetPath : entry.target_path;
      const targetPath = String(targetPathRaw || "").trim();
      const rawName = String(entry.name || "").trim();
      const hasAdminScopeValueKey = Object.prototype.hasOwnProperty.call(entry, "adminScopeValue");
      const adminScopeValueRaw = hasAdminScopeValueKey ? entry.adminScopeValue : entry.admin_scope_value;
      const adminScopeValue = allowScope
        ? String(adminScopeValueRaw || "").trim()
        : "";
      return {
        id,
        name: rawName || targetPath,
        targetPath: targetPath,
        manualOptions: [],
        adminScopeValue: adminScopeValue || null,
      };
    })
    .filter(Boolean);
}

function normalizeTileFilterControlOrder(rawOrder, filters = [], { includeReset = true } = {}) {
  const filterIds = (Array.isArray(filters) ? filters : [])
    .map((filter) => String(filter?.id || "").trim())
    .filter(Boolean);
  if (filterIds.length === 0) return [];

  const knownFilterIds = new Set(filterIds);
  const allowReset = includeReset && filterIds.length > 1;
  const next = [];
  const addControlId = (rawId) => {
    const id = String(rawId || "").trim();
    if (!id || next.includes(id)) return;
    if ((allowReset && id === FILTER_RESET_CONTROL_ID) || knownFilterIds.has(id)) {
      next.push(id);
    }
  };

  if (Array.isArray(rawOrder)) {
    rawOrder.forEach(addControlId);
  }
  filterIds.forEach(addControlId);
  if (allowReset) addControlId(FILTER_RESET_CONTROL_ID);
  return next;
}

function formatPublicFilterLabel(filter) {
  return String(filter?.name || formatFilterLabel(filter?.targetPath) || "Filter").trim();
}

const configuredTileFiltersFromContent = computed(() =>
  normalizeTileFilterDefinitions(section.value?.filters)
);

const configuredTileFiltersFromIntegration = computed(() => {
  const rawFilters = sectionIntegrationMapping.value?.list_filters;
  return normalizeTileFilterDefinitions(rawFilters, { allowScope: true });
});

const configuredTileFilters = computed(() => {
  if (configuredTileFiltersFromContent.value.length > 0) {
    return configuredTileFiltersFromContent.value;
  }
  return configuredTileFiltersFromIntegration.value;
});

const activeTileFilters = computed(() =>
  configuredTileFilters.value.filter((filter) =>
    String(filter.targetPath || "").trim()
  )
);

const scopedTileFilters = computed(() =>
  activeTileFilters.value.filter((filter) => String(filter.adminScopeValue || "").trim())
);

const publicVisibleFilters = computed(() =>
  activeTileFilters.value.filter((filter) => !String(filter.adminScopeValue || "").trim())
);

const publicFilterControlOrder = computed(() =>
  normalizeTileFilterControlOrder(
    section.value?.filterControlOrder,
    publicVisibleFilters.value,
    { includeReset: tileShowResetButton.value }
  )
);

const publicFilterControls = computed(() => {
  const filtersById = new Map();
  publicVisibleFilters.value.forEach((filter) => {
    const id = String(filter?.id || "").trim();
    if (id) filtersById.set(id, filter);
  });
  return publicFilterControlOrder.value
    .map((id) => {
      if (id === FILTER_RESET_CONTROL_ID) {
        return {
          type: "reset",
          id,
          key: "tile-filter-control-reset",
        };
      }
      const filter = filtersById.get(id);
      if (!filter) return null;
      return {
        type: "filter",
        id,
        key: `tile-filter-control-${id}`,
        filter,
      };
    })
    .filter(Boolean);
});

const selectedPublicFilterValues = ref({});
const hasActivePublicFilters = computed(() =>
  publicVisibleFilters.value.some((filter) =>
    String(selectedPublicFilterValues.value?.[filter.id] || "").trim() !== ""
  )
);

function resolveProgramGigStageTitle(gig) {
  const stageId = String(gig?.stage || "").trim();
  if (!stageId) return "";
  const stage = (Array.isArray(state.programSharedStages) ? state.programSharedStages : []).find(
    (entry) => String(entry?.id || "").trim() === stageId
  );
  if (!stage || typeof stage !== "object") return stageId;
  const stageName = stage.name && typeof stage.name === "object" ? stage.name : {};
  return String(stageName?.[state.lang] || stageName?.de || stageName?.en || stageId).trim();
}

const programStageLookup = computed(() => {
  const byId = new Set();
  const byNormalizedLabel = new Map();
  const stages = Array.isArray(state.programSharedStages) ? state.programSharedStages : [];

  stages.forEach((stage) => {
    if (!stage || typeof stage !== "object") return;
    const stageId = String(stage?.id || "").trim();
    if (!stageId) return;
    byId.add(stageId);

    const stageName = stage?.name && typeof stage.name === "object" ? stage.name : {};
    const labelCandidates = [
      stageId,
      stageName?.de,
      stageName?.en,
      stage?.name,
      stage?.title,
      stage?.label,
      stage?.value,
    ];
    labelCandidates.forEach((candidate) => {
      const normalized = normalizeFilterValue(candidate);
      if (!normalized) return;
      const lookupKey = normalized.toLowerCase();
      if (!byNormalizedLabel.has(lookupKey)) {
        byNormalizedLabel.set(lookupKey, stageId);
      }
    });
  });

  return {
    byId,
    byNormalizedLabel,
  };
});

function resolveProgramStageMatchKey(value) {
  const normalizedValue = normalizeFilterValue(value);
  if (!normalizedValue) return "";
  const trimmedValue = String(normalizedValue).trim();
  if (!trimmedValue) return "";

  const lookup = programStageLookup.value;
  if (lookup.byId.has(trimmedValue)) {
    return `id:${trimmedValue}`;
  }

  const mappedStageId = lookup.byNormalizedLabel.get(trimmedValue.toLowerCase());
  if (mappedStageId) {
    return `id:${mappedStageId}`;
  }

  return `text:${trimmedValue.toLowerCase()}`;
}

function isStageComparableFilterTargetPath(path) {
  const normalizedPath = normalizeMappingPath(path);
  if (!normalizedPath) return false;
  if (isLocationTargetPath(normalizedPath) || isStageTargetPath(normalizedPath)) return true;
  if (normalizedPath === "stage_id") return true;
  if (normalizedPath.startsWith("stage_id.")) return true;
  if (normalizedPath.endsWith(".stage_id")) return true;
  return normalizedPath.includes(".stage_id.");
}

function resolveProgramGigResponsiveVariants(gig) {
  return resolveBackendResponsiveImageVariants(gig);
}

function mapProgramGigToTile(gig, index = 0) {
  const media = resolveBackendResponsiveImagePayload(gig, {
    urlKeys: ["image_url", "url", "src", "href"],
  });
  const titleSource = (
    gig?.title && typeof gig.title === "object"
      ? gig.title
      : gig?.artist_name && typeof gig.artist_name === "object"
        ? gig.artist_name
        : null
  );
  const artist = titleSource
    ? {
      de: String(titleSource.de || titleSource.en || "").trim(),
      en: String(titleSource.en || titleSource.de || "").trim(),
    }
    : { de: "", en: "" };
  const subtitle = gig?.genre && typeof gig.genre === "object"
    ? {
      de: String(gig.genre.de || gig.genre.en || "").trim(),
      en: String(gig.genre.en || gig.genre.de || "").trim(),
    }
    : { de: "", en: "" };
  const responsiveVariants = resolveProgramGigResponsiveVariants(gig);
  const fallbackVariantUrl = String(
    responsiveVariants.length ? responsiveVariants[responsiveVariants.length - 1]?.url : ""
  ).trim();
  const startDateTime = String(gig?.start || "").trim();
  const day = String(gig?.day || "").trim();
  const start = String(gig?.start_time || "").trim();
  const combinedDateTime = startDateTime || (day && start ? `${day}T${start}` : String(gig?.dateTime || gig?.time || "").trim());
  const imageTransform = resolveProgramTileImageTransform(gig);
  return {
    id: String(gig?.id || `program-gig-${index}`),
    program_source: gig,
    imageUrl: String(media.url || "").trim() || fallbackVariantUrl,
    responsiveVariants,
    zoom: imageTransform.zoom,
    focalX: imageTransform.focalX,
    focalY: imageTransform.focalY,
    rotation: imageTransform.rotation,
    title: artist,
    subtitle,
    location: resolveProgramGigStageTitle(gig),
    dateTime: combinedDateTime,
    time: combinedDateTime,
    pageSlug: String(gig?.page_slug || "").trim(),
    itemUrl: String(gig?.item_url || "").trim(),
  };
}

const programTileOrder = computed(() => {
  const raw = section.value?.programTileOrder;
  if (!Array.isArray(raw)) return [];
  return raw.map((entry) => String(entry || "").trim()).filter(Boolean);
});

function normalizeProgramTileOverrides(rawOverrides) {
  if (!rawOverrides || typeof rawOverrides !== "object") return {};
  const next = {};
  Object.entries(rawOverrides).forEach(([tileId, rawOverride]) => {
    const normalizedId = String(tileId || "").trim();
    if (!normalizedId || !rawOverride || typeof rawOverride !== "object") return;
    next[normalizedId] = {
      zoom: normalizeTileZoom(rawOverride.zoom),
      focalX: normalizeTileFocal(rawOverride.focalX),
      focalY: normalizeTileFocal(rawOverride.focalY),
      rotation: normalizeTileRotation(rawOverride.rotation),
    };
  });
  return next;
}

const programTileOverrides = computed(() =>
  normalizeProgramTileOverrides(section.value?.programTileOverrides)
);

const programBaseTiles = computed(() =>
  (Array.isArray(state.programSharedGigs) ? state.programSharedGigs : [])
    .map((gig, index) => mapProgramGigToTile(gig, index))
);

const programBaseTileMapById = computed(() => {
  const next = new Map();
  programBaseTiles.value.forEach((tile) => {
    const tileId = String(tile?.id || "").trim();
    if (!tileId || next.has(tileId)) return;
    next.set(tileId, tile);
  });
  return next;
});

const programTilesWithOverrides = computed(() => {
  const baseTiles = programBaseTiles.value;
  const byId = new Map();
  baseTiles.forEach((tile) => {
    const tileId = String(tile?.id || "").trim();
    if (!tileId || byId.has(tileId)) return;
    byId.set(tileId, tile);
  });

  const orderedIds = [];
  programTileOrder.value.forEach((tileId) => {
    if (!byId.has(tileId)) return;
    if (orderedIds.includes(tileId)) return;
    orderedIds.push(tileId);
  });
  baseTiles.forEach((tile) => {
    const tileId = String(tile?.id || "").trim();
    if (!tileId || orderedIds.includes(tileId)) return;
    orderedIds.push(tileId);
  });

  return orderedIds.map((tileId) => {
    const baseTile = byId.get(tileId);
    const override = shouldUseProgramGigImageTransform.value ? null : programTileOverrides.value?.[tileId];
    if (!override) return { ...baseTile };
    return {
      ...baseTile,
      zoom: normalizeTileZoom(override.zoom),
      focalX: normalizeTileFocal(override.focalX),
      focalY: normalizeTileFocal(override.focalY),
      rotation: normalizeTileRotation(override.rotation),
    };
  });
});

const sourceTiles = computed(() =>
  useProgramGigs.value
    ? programTilesWithOverrides.value
    : (Array.isArray(section.value?.tiles) ? section.value.tiles : [])
);

function resolveSortableTileTitle(tile) {
  const title = resolveTileTitle(tile);
  const localized = String(localizedText(title) || "").trim();
  if (localized) return localized;
  return String(title?.de || title?.en || "").trim();
}

function sortTilesByTitle(items) {
  const locale = state.lang === "de" ? "de-DE" : "en-US";
  return items
    .map((tile, index) => ({
      tile,
      index,
      title: resolveSortableTileTitle(tile),
    }))
    .sort((left, right) => {
      if (left.title && !right.title) return -1;
      if (!left.title && right.title) return 1;
      const titleDiff = left.title.localeCompare(right.title, locale, {
        sensitivity: "base",
        numeric: true,
      });
      if (titleDiff !== 0) return titleDiff;
      return left.index - right.index;
    })
    .map((entry) => entry.tile);
}

const sortedSourceTiles = computed(() => {
  const items = Array.isArray(sourceTiles.value) ? sourceTiles.value : [];
  if (tileSortMode.value !== "title") return items;
  return sortTilesByTitle(items);
});

const tileIntegrationMappingRows = computed(() =>
  normalizeMappingRowsForCollection(sectionIntegrationMapping.value, ["tiles"])
);
const programIntegrationMappingRows = computed(() =>
  normalizeMappingRowsForCollection(programSectionIntegrationMapping.value, ["gigs"])
);
const activeTileIntegrationMappingRows = computed(() =>
  useProgramGigs.value ? programIntegrationMappingRows.value : tileIntegrationMappingRows.value
);

function normalizeMappingPath(path) {
  return String(path || "")
    .trim()
    .replace(/\[(?:\d+|\*)\]/g, "")
    .toLowerCase();
}

function isLocationTargetPath(path) {
  const normalizedPath = normalizeMappingPath(path);
  if (!normalizedPath) return false;
  if (normalizedPath === "location") return true;
  if (normalizedPath.startsWith("location.")) return true;
  if (normalizedPath.endsWith(".location")) return true;
  return normalizedPath.includes(".location.");
}

function isStageTargetPath(path) {
  const normalizedPath = normalizeMappingPath(path);
  if (!normalizedPath) return false;
  if (normalizedPath === "stage") return true;
  if (normalizedPath.startsWith("stage.")) return true;
  if (normalizedPath.endsWith(".stage")) return true;
  return normalizedPath.includes(".stage.");
}

function hasLocationOrStageTargetMapping(mappingRows = []) {
  if (!Array.isArray(mappingRows) || mappingRows.length === 0) return false;
  return mappingRows.some((row) =>
    isLocationTargetPath(row?.targetPath) || isStageTargetPath(row?.targetPath)
  );
}

const shouldShowTileLocationFromMapping = computed(() =>
  hasLocationOrStageTargetMapping(activeTileIntegrationMappingRows.value)
);

function buildIntegrationFilterOptions(previewOptions, mappingRows, sourceLabel) {
  if (!Array.isArray(previewOptions)) return [];
  return previewOptions
    .flatMap((entry) => {
      const sourcePath = String(entry?.path || "").trim();
      if (!sourcePath) return [];
      const mappedTargetPath = resolveTargetPathFromMappingRows(mappingRows, sourcePath);
      const typeLabel = filterTypeLabel(entry?.type || "text");
      const normalizedType = String(entry?.type || "text").trim().toLowerCase() || "text";
      const options = [
        {
          path: sourcePath,
          type: normalizedType,
          label: `${formatFilterLabel(sourcePath)} (${typeLabel}) - source`,
          source: sourceLabel,
          sourcePath: sourcePath,
        },
      ];
      if (mappedTargetPath && mappedTargetPath !== sourcePath) {
        options.push({
          path: mappedTargetPath,
          type: normalizedType,
          label: `${formatFilterLabel(mappedTargetPath)} (${typeLabel}) - from ${sourcePath}`,
          source: sourceLabel,
          sourcePath: sourcePath,
        });
      }
      return options;
    })
    .filter(Boolean);
}

const tileIntegrationImportFilterOptions = computed(() =>
  buildIntegrationFilterOptions(
    tileIntegrationPreviewFieldOptions.value,
    tileIntegrationMappingRows.value,
    "Tiles Integration",
  )
);

const programIntegrationImportFilterOptions = computed(() =>
  buildIntegrationFilterOptions(
    programIntegrationPreviewFieldOptions.value,
    programIntegrationMappingRows.value,
    "Program Integration",
  )
);

const activeIntegrationImportFilterOptions = computed(() =>
  useProgramGigs.value
    ? programIntegrationImportFilterOptions.value
    : tileIntegrationImportFilterOptions.value
);

const activeIntegrationOptions = computed(() =>
  normalizeIntegrationOptions(
    useProgramGigs.value
      ? programGigsIntegrationCacheState.value?.options
      : sectionIntegrationCacheState.value?.options
  )
);

const cachedIntegrationOptionFilterOptions = computed(() => {
  const options = activeIntegrationOptions.value;
  const mappingRows = activeTileIntegrationMappingRows.value;
  const rowsByPath = new Map();

  function addOptionRow(path, sourcePath) {
    const normalizedPath = String(path || "").trim();
    const normalizedSourcePath = String(sourcePath || "").trim();
    if (!normalizedPath || rowsByPath.has(normalizedPath)) return;
    rowsByPath.set(normalizedPath, {
      path: normalizedPath,
      type: "list",
      label: `${formatFilterLabel(normalizedPath)} (List) - options`,
      source: useProgramGigs.value ? "Program Gig Option Metadata" : "Tile Option Metadata",
      sourcePath: normalizedSourcePath || normalizedPath,
    });
  }

  Object.entries(options).forEach(([sourcePath, rawValues]) => {
    const normalizedSourcePath = String(sourcePath || "").trim();
    if (!normalizedSourcePath || !Array.isArray(rawValues)) return;

    const mappedTargetPath = resolveMappedTargetPathForSourcePath(normalizedSourcePath, mappingRows);
    if (mappedTargetPath) {
      addOptionRow(mappedTargetPath, normalizedSourcePath);
      return;
    }
    addOptionRow(stripFilterOptionCollectionPrefix(normalizedSourcePath), normalizedSourcePath);
  });

  return Array.from(rowsByPath.values()).sort((left, right) => left.path.localeCompare(right.path));
});

function resolveCentralizedOptionSourceCandidates(targetPath, mappingRows = []) {
  const normalizedTargetPath = String(targetPath || "").trim();
  if (!normalizedTargetPath) return [];
  const candidates = new Set();
  const addCandidateAliases = (candidatePath) => {
    collectFilterOptionPathAliases(candidatePath).forEach((alias) => candidates.add(alias));
  };

  addCandidateAliases(normalizedTargetPath);
  const mappedSourcePath = resolveMappedSourcePathForTargetPath(normalizedTargetPath, mappingRows);
  if (mappedSourcePath) addCandidateAliases(mappedSourcePath);
  resolveIntegrationSourcePathCandidates(normalizedTargetPath).forEach((sourcePath) => {
    if (sourcePath) addCandidateAliases(sourcePath);
  });
  return Array.from(candidates).filter(Boolean);
}

const integrationSourcePathCandidatesByTargetPath = computed(() => {
  const byTargetPath = new Map();
  const options = Array.isArray(activeIntegrationImportFilterOptions.value)
    ? activeIntegrationImportFilterOptions.value
    : [];
  options.forEach((entry) => {
    const targetPath = String(entry?.path || "").trim();
    const sourcePath = String(entry?.sourcePath || "").trim();
    if (!targetPath || !sourcePath) return;
    if (!byTargetPath.has(targetPath)) byTargetPath.set(targetPath, new Set());
    byTargetPath.get(targetPath).add(sourcePath);
  });
  return byTargetPath;
});

const availableFilterTargetOptions = computed(() => {
  const merged = new Map();
  cachedIntegrationOptionFilterOptions.value.forEach((entry) => {
    const path = String(entry?.path || "").trim();
    if (!path) return;
    if (!merged.has(path)) {
      merged.set(path, {
        path,
        label: String(entry?.label || formatFilterLabel(path)).trim() || formatFilterLabel(path),
        disabled: entry?.disabled === true,
      });
    }
  });
  return Array.from(merged.values()).sort((left, right) => left.path.localeCompare(right.path));
});

const availableFilterTargetPathSet = computed(() =>
  new Set(availableFilterTargetOptions.value.map((entry) => String(entry?.path || "").trim()).filter(Boolean))
);

function resolveMappedSourcePathForTargetPath(targetPath, mappingRows = []) {
  const normalizedTargetPath = String(targetPath || "").trim();
  if (!normalizedTargetPath || !Array.isArray(mappingRows) || mappingRows.length === 0) return "";
  const strictMappedPath = resolveSourcePathFromMappingRows(mappingRows, normalizedTargetPath);
  if (strictMappedPath) return strictMappedPath;
  return "";
}

function resolveMappedTargetPathForSourcePath(sourcePath, mappingRows = []) {
  const normalizedSourcePath = String(sourcePath || "").trim();
  if (!normalizedSourcePath || !Array.isArray(mappingRows) || mappingRows.length === 0) return "";
  const strictMappedPath = resolveTargetPathFromMappingRows(mappingRows, normalizedSourcePath);
  if (strictMappedPath) return strictMappedPath;
  return "";
}

function resolveIntegrationSourcePathCandidates(targetPath) {
  const normalizedTargetPath = String(targetPath || "").trim();
  if (!normalizedTargetPath) return [];
  const mapping = integrationSourcePathCandidatesByTargetPath.value;
  if (!(mapping instanceof Map) || mapping.size === 0) return [];
  const candidates = new Set();
  collectFilterOptionPathAliases(normalizedTargetPath).forEach((targetAlias) => {
    const strict = mapping.get(targetAlias);
    if (!(strict instanceof Set)) return;
    strict.forEach((entry) => {
      const sourcePath = String(entry || "").trim();
      if (sourcePath) candidates.add(sourcePath);
    });
  });
  if (candidates.size === 0) {
    mapping.forEach((sourcePaths, mappedTargetPath) => {
      if (!(sourcePaths instanceof Set)) return;
      if (!filterOptionPathsMatch(mappedTargetPath, normalizedTargetPath)) return;
      sourcePaths.forEach((entry) => {
        const sourcePath = String(entry || "").trim();
        if (sourcePath) candidates.add(sourcePath);
      });
    });
  }
  return Array.from(candidates);
}

function resolveTileProgramSource(tile) {
  if (!tile || typeof tile !== "object") return null;
  if (tile.programSource && typeof tile.programSource === "object") {
    return tile.programSource;
  }
  if (tile.program_source && typeof tile.program_source === "object") {
    return tile.program_source;
  }
  return null;
}

function resolveRawTileFieldValue(tile, path, mappingRows = []) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return undefined;
  const programSource = resolveTileProgramSource(tile);

  const fromTile = deepGetPathValue(tile, normalizedPath);
  if (fromTile !== undefined) return fromTile;

  const fromProgramSource = deepGetPathValue(programSource, normalizedPath);
  if (fromProgramSource !== undefined) return fromProgramSource;

  if (Array.isArray(mappingRows) && mappingRows.length > 0) {
    const mappedTargetPath = resolveMappedTargetPathForSourcePath(normalizedPath, mappingRows);
    if (mappedTargetPath) {
      const fromMappedTileTarget = deepGetPathValue(tile, mappedTargetPath);
      if (fromMappedTileTarget !== undefined) return fromMappedTileTarget;

      const fromMappedProgramTarget = deepGetPathValue(programSource, mappedTargetPath);
      if (fromMappedProgramTarget !== undefined) return fromMappedProgramTarget;
    }

    const mappedSourcePath = resolveMappedSourcePathForTargetPath(normalizedPath, mappingRows);
    if (mappedSourcePath) {
      const fromMappedSource = deepGetPathValue(programSource, mappedSourcePath);
      if (fromMappedSource !== undefined) return fromMappedSource;
    }
  }

  const integrationSourceCandidates = resolveIntegrationSourcePathCandidates(normalizedPath);
  for (const sourcePath of integrationSourceCandidates) {
    const fromIntegrationSource = deepGetPathValue(programSource, sourcePath);
    if (fromIntegrationSource !== undefined) return fromIntegrationSource;
  }

  return undefined;
}

function getRawTileFieldValue(tile, path, mappingRows = []) {
  return resolveRawTileFieldValue(tile, path, mappingRows);
}

function resolveAutoFilterOptionsFromCache(targetPath, mappingRows = []) {
  const normalizedTargetPath = String(targetPath || "").trim();
  if (!normalizedTargetPath) return [];
  const centralizedOptions = activeIntegrationOptions.value;
  for (const sourcePath of resolveCentralizedOptionSourceCandidates(normalizedTargetPath, mappingRows)) {
    const normalizedOptions = normalizeFilterStringOptions(centralizedOptions[sourcePath]);
    if (normalizedOptions.length > 0) return normalizedOptions;
  }
  return [];
}

function resolveEffectiveFilterOptions(filter, mappingRows = []) {
  const targetPath = String(filter?.targetPath || "").trim();
  if (!targetPath) return [];
  return resolveAutoFilterOptionsFromCache(targetPath, mappingRows);
}

function applyTileFilters(items, filters, selectedValuesById = {}, mappingRows = []) {
  if (!Array.isArray(items) || !Array.isArray(filters) || filters.length === 0) return Array.isArray(items) ? items : [];
  return items.filter((tile) => {
    for (const filter of filters) {
      const targetPath = String(filter?.targetPath || "").trim();
      if (!targetPath) continue;
      const selectedValue = normalizeFilterValue(
        Object.prototype.hasOwnProperty.call(selectedValuesById || {}, filter.id)
          ? selectedValuesById[filter.id]
          : filter.adminScopeValue
      );
      if (!selectedValue) continue;
      const rawValue = getRawTileFieldValue(tile, targetPath, mappingRows);
      const shouldUseStageMatching = useProgramGigs.value && isStageComparableFilterTargetPath(targetPath);
      if (shouldUseStageMatching) {
        const selectedStageKey = resolveProgramStageMatchKey(selectedValue);
        if (!selectedStageKey) continue;
        if (Array.isArray(rawValue)) {
          const hasStageMatch = rawValue.some((entry) =>
            resolveProgramStageMatchKey(entry) === selectedStageKey
          );
          if (!hasStageMatch) return false;
          continue;
        }
        const tileStageKey = resolveProgramStageMatchKey(rawValue);
        if (tileStageKey !== selectedStageKey) return false;
        continue;
      }
      if (Array.isArray(rawValue)) {
        const normalizedValues = normalizeFilterStringOptions(rawValue);
        if (!normalizedValues.includes(selectedValue)) return false;
      } else {
        const tileValue = normalizeFilterValue(rawValue);
        if (tileValue !== selectedValue) return false;
      }
    }
    return true;
  });
}

const tilesAfterScopedFilters = computed(() =>
  applyTileFilters(sortedSourceTiles.value, scopedTileFilters.value, {}, activeTileIntegrationMappingRows.value)
);

const publicFilterOptionsById = computed(() => {
  const options = {};
  const mappingRows = activeTileIntegrationMappingRows.value;
  publicVisibleFilters.value.forEach((filter) => {
    if (!String(filter?.targetPath || "").trim()) {
      options[filter.id] = [];
      return;
    }
    options[filter.id] = resolveEffectiveFilterOptions(filter, mappingRows);
  });
  return options;
});

function syncSelectedPublicFilterValues() {
  const next = {};
  publicVisibleFilters.value.forEach((filter) => {
    const currentValue = String(selectedPublicFilterValues.value?.[filter.id] || "").trim();
    const options = Array.isArray(publicFilterOptionsById.value?.[filter.id])
      ? publicFilterOptionsById.value[filter.id]
      : [];
    // When options are empty (data still loading), preserve the current value.
    // Only reset when options are loaded and the current value is not among them.
    if (!currentValue || options.length === 0 || options.includes(currentValue)) {
      next[filter.id] = currentValue;
    } else {
      next[filter.id] = "";
    }
  });
  selectedPublicFilterValues.value = next;
}

function setPublicFilterValue(filterId, value) {
  const normalizedId = String(filterId || "").trim();
  if (!normalizedId) return;
  selectedPublicFilterValues.value = {
    ...selectedPublicFilterValues.value,
    [normalizedId]: String(value || "").trim(),
  };
}

function clearPublicFilters() {
  const next = {};
  publicVisibleFilters.value.forEach((filter) => {
    const filterId = String(filter?.id || "").trim();
    if (!filterId) return;
    next[filterId] = "";
  });
  selectedPublicFilterValues.value = next;
}

watch(
  () => JSON.stringify({
    filters: publicVisibleFilters.value.map((filter) => filter.id),
    options: publicFilterOptionsById.value,
  }),
  () => {
    syncSelectedPublicFilterValues();
  },
  { immediate: true },
);

const filteredSourceTiles = computed(() =>
  applyTileFilters(
    sortedSourceTiles.value,
    publicVisibleFilters.value,
    selectedPublicFilterValues.value,
    activeTileIntegrationMappingRows.value
  )
);

const isFilterActive = computed(() =>
  Object.values(selectedPublicFilterValues.value).some((v) => v !== "")
);

const tileFallbackOverrideEnabled = computed(() =>
  section.value?.tileFallbackOverrideEnabled === true
);

const tileSectionFallbackConfig = computed(() =>
  normalizeFallbackImageConfig({
    images: section.value?.filterFallbackImages,
    mediaTag: section.value?.filterFallbackMediaTag,
    legacyImageUrl: section.value?.filterFallbackImageUrl,
    zoom: section.value?.filterFallbackZoom,
    focalX: section.value?.filterFallbackFocalX,
    focalY: section.value?.filterFallbackFocalY,
    rotation: section.value?.filterFallbackRotation,
  })
);

const effectiveTileFallbackConfig = computed(() =>
  resolveEffectiveFallbackImageConfig({
    globalFallbacks: state.mediaFallbacks,
    sectionFallbacks: tileSectionFallbackConfig.value,
    useSectionFallbacks: tileFallbackOverrideEnabled.value,
  })
);

const filterFallbackImagePool = computed(() =>
  Array.isArray(effectiveTileFallbackConfig.value?.pool)
    ? effectiveTileFallbackConfig.value.pool
    : []
);

const filterFallbackMediaTag = computed(() =>
  String(section.value?.filterFallbackMediaTag || "").trim()
);

const filterFallbackZoom = computed(() =>
  normalizeTileZoom(section.value?.filterFallbackZoom)
);
const filterFallbackFocalX = computed(() =>
  normalizeTileFocal(section.value?.filterFallbackFocalX)
);
const filterFallbackFocalY = computed(() =>
  normalizeTileFocal(section.value?.filterFallbackFocalY)
);
const filterFallbackRotation = computed(() =>
  normalizeTileRotation(section.value?.filterFallbackRotation)
);

const fixedDisplayTileCount = computed(() => rows.value * columns.value);
const tileManualReorderModeActive = computed(() =>
  tileSortMode.value === "manual" && tileManualReorderActive.value
);

function createDynamicFillerTile(index, prefix = "filler") {
  const fallbackImage = resolveFallbackImageForIndex(effectiveTileFallbackConfig.value, index);
  return {
    id: `${prefix}-${index}`,
    _filler: true,
    imageUrl: fallbackImage?.imageUrl || "",
    responsiveVariants: Array.isArray(fallbackImage?.responsiveVariants)
      ? fallbackImage.responsiveVariants
      : [],
    zoom: fallbackImage?.zoom ?? 1,
    focalX: fallbackImage?.focalX ?? 50,
    focalY: fallbackImage?.focalY ?? 50,
    rotation: fallbackImage?.rotation ?? 0,
  };
}

function withRowFillers(sourceItems, cols, prefix = "filler") {
  const normalizedColumns = Math.max(1, Number(cols) || 1);
  const result = [...sourceItems];
  const remainder = result.length % normalizedColumns;
  if (remainder === 0) return result;
  const fillCount = normalizedColumns - remainder;
  for (let i = 0; i < fillCount; i += 1) {
    result.push(createDynamicFillerTile(i, prefix));
  }
  return result;
}

function withFixedSlotFillers(sourceItems, totalSlots, prefix = "filler-fixed") {
  const normalizedTotalSlots = Math.max(0, Math.floor(Number(totalSlots) || 0));
  const result = [];
  for (let index = 0; index < normalizedTotalSlots; index += 1) {
    result.push(sourceItems[index] || createDynamicFillerTile(index, prefix));
  }
  return result;
}

const displayTiles = computed(() => {
  const sourceItems = filteredSourceTiles.value;

  if (isFixedMode.value) {
    return withFixedSlotFillers(
      sourceItems,
      fixedDisplayTileCount.value,
      isFilterActive.value ? "filler-filter-fixed" : "filler-fixed",
    );
  }

  if (isFilterActive.value) {
    return withRowFillers(sourceItems, effectiveDisplayColumns.value, "filler-filter");
  }

  return withRowFillers(sourceItems, effectiveDisplayColumns.value, "filler-dynamic");
});

const hover = ref(false);
const hoveredIndex = ref(-1);
const focusedIndex = ref(-1);
const expandedIndex = ref(-1);
const isTouchLikeDevice = ref(false);
const isMobileViewport = computed(() => getEffectiveViewportDevice() === "mobile");
const editing = ref(false);
const expandedItem = ref(-1);
const tileManualReorderActive = ref(false);
const draftTiles = ref([]);
const draftFilters = ref([]);
const draftFilterControlOrder = ref([]);
const visibleTileChevronByIndex = ref({});
const tileItemPageAvailabilityByPath = ref({});
const mediaTagOptions = ref([]);
const loadingMediaTags = ref(false);
const selectedMediaTag = ref("");
const mediaTagImportMode = ref("replace");
const importingFromMediaTag = ref(false);
const mediaTagImportStatus = ref(null);
const {
  showMediaPicker,
  openMediaPicker,
  closeMediaPicker,
  consumeMediaPickerSelectionContext,
} = useListEditorMediaPicker();
const fixedDraftTileLimit = computed(() => rows.value * columns.value);
const hasFixedDraftTileLimit = computed(() => isFixedMode.value);
const canAddDraftTile = computed(() => {
  if (!hasFixedDraftTileLimit.value) return true;
  return draftTiles.value.length < fixedDraftTileLimit.value;
});
const thumbRatioStyle = computed(() => ({
  aspectRatio: ratioToCss(aspectRatio.value, direction.value),
  width: "80px",
  height: "auto",
}));

const TILE_CHEVRON_DELAY_MS = 300;
const tileChevronTimers = new Map();
let tileItemAvailabilitySyncToken = 0;
let touchMediaQueryList = null;
const MOBILE_TILE_COLUMNS = 2;

const hasTileImportedIntegrationData = computed(() =>
  hasImportedIntegrationCacheData(sectionIntegrationCacheState.value)
);

const hasProgramGigImportedIntegrationData = computed(() =>
  hasImportedIntegrationCacheData(programGigsIntegrationCacheState.value)
);

const showTileFiltersPanel = computed(() =>
  useProgramGigs.value
    ? hasProgramGigImportedIntegrationData.value
    : hasTileImportedIntegrationData.value
);

const normalizedDraftFilters = computed(() =>
  normalizeTileFilterDefinitions(draftFilters.value)
);

const draftFilterControlSourceFilters = computed(() =>
  normalizedDraftFilters.value
);

const normalizedDraftFilterControlOrder = computed(() =>
  normalizeTileFilterControlOrder(
    draftFilterControlOrder.value,
    draftFilterControlSourceFilters.value,
    { includeReset: tileShowResetButton.value }
  )
);

const draftFilterListItems = computed(() => {
  const filtersById = new Map();
  normalizedDraftFilters.value.forEach((filter, index) => {
    const id = String(filter?.id || "").trim();
    if (id) {
      filtersById.set(id, {
        type: "filter",
        id,
        filter,
        filterIndex: index,
      });
    }
  });
  return normalizedDraftFilterControlOrder.value
    .map((id) => {
      if (id === FILTER_RESET_CONTROL_ID) {
        return {
          id,
          type: "reset",
        };
      }
      return filtersById.get(id) || null;
    })
    .filter(Boolean);
});

function normalizedDraftFiltersForSave() {
  return normalizeTileFilterDefinitions(draftFilters.value);
}

function normalizedDraftFilterControlOrderForSave() {
  const draftFiltersForSave = normalizedDraftFiltersForSave();
  return normalizeTileFilterControlOrder(
    draftFilterControlOrder.value,
    draftFiltersForSave,
    { includeReset: tileShowResetButton.value }
  );
}

function clearTileChevronTimer(index) {
  if (!tileChevronTimers.has(index)) return;
  clearTimeout(tileChevronTimers.get(index));
  tileChevronTimers.delete(index);
}

function setTileChevronVisible(index, visible) {
  visibleTileChevronByIndex.value = {
    ...visibleTileChevronByIndex.value,
    [index]: Boolean(visible),
  };
}

function clearAllTileChevronTimers() {
  tileChevronTimers.forEach((timer) => clearTimeout(timer));
  tileChevronTimers.clear();
}

function scheduleTileChevron(index, tile) {
  if (!resolveTilePublicItemUrl(tile)) {
    setTileChevronVisible(index, false);
    return;
  }
  clearTileChevronTimer(index);
  const timer = setTimeout(() => {
    setTileChevronVisible(index, true);
    tileChevronTimers.delete(index);
  }, TILE_CHEVRON_DELAY_MS);
  tileChevronTimers.set(index, timer);
}

function hideTileChevron(index) {
  clearTileChevronTimer(index);
  setTileChevronVisible(index, false);
}

function handleTileMouseEnter(index, tile) {
  hoveredIndex.value = index;
  scheduleTileChevron(index, tile);
}

function handleTileMouseLeave(index) {
  if (hoveredIndex.value === index) hoveredIndex.value = -1;
  hideTileChevron(index);
}

function handleTileFocusIn(index, tile) {
  focusedIndex.value = index;
  scheduleTileChevron(index, tile);
}

function handleTileFocusOut(index, event) {
  const nextTarget = event?.relatedTarget;
  if (nextTarget && event?.currentTarget?.contains?.(nextTarget)) return;
  if (focusedIndex.value === index) focusedIndex.value = -1;
  hideTileChevron(index);
}

function showTileChevron(index, tile) {
  if (!resolveTilePublicItemUrl(tile)) return false;
  if (!isTileOverlayActive(index)) return false;
  if (!isTouchLikeDevice.value && hoveredIndex.value !== index && focusedIndex.value !== index) return false;
  return Boolean(visibleTileChevronByIndex.value?.[index]);
}

function updateTouchLikeDeviceState() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    isTouchLikeDevice.value = false;
    return;
  }
  isTouchLikeDevice.value = Boolean(window.matchMedia("(hover: none), (pointer: coarse)").matches);
}

function handleTouchMediaQueryChange(event) {
  isTouchLikeDevice.value = Boolean(event?.matches);
}

onMounted(() => {
  updateTouchLikeDeviceState();
  void nextTick(() => {
    updateGridContainerWidth();
    if (typeof ResizeObserver !== "undefined" && gridRef.value) {
      gridResizeObserver = new ResizeObserver(() => {
        updateGridContainerWidth();
      });
      gridResizeObserver.observe(gridRef.value);
    }
  });

  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    touchMediaQueryList = window.matchMedia("(hover: none), (pointer: coarse)");
    if (typeof touchMediaQueryList.addEventListener === "function") {
      touchMediaQueryList.addEventListener("change", handleTouchMediaQueryChange);
    } else if (typeof touchMediaQueryList.addListener === "function") {
      touchMediaQueryList.addListener(handleTouchMediaQueryChange);
    }
  }
});

onBeforeUnmount(() => {
  clearAllTileChevronTimers();
  if (gridResizeObserver) {
    gridResizeObserver.disconnect();
    gridResizeObserver = null;
  }
  if (touchMediaQueryList) {
    if (typeof touchMediaQueryList.removeEventListener === "function") {
      touchMediaQueryList.removeEventListener("change", handleTouchMediaQueryChange);
    } else if (typeof touchMediaQueryList.removeListener === "function") {
      touchMediaQueryList.removeListener(handleTouchMediaQueryChange);
    }
  }
});

watch(
  () => state.isAdmin,
  (val) => {
    if (!val) {
      // Keep draft values until unmount autosave has completed; clearing here
      // can race with SectionListEditor autosave and persist an empty list.
      editing.value = false;
    }
  }
);

watch(tileSortMode, (mode) => {
  if (mode !== "manual") {
    tileManualReorderActive.value = false;
  }
});

watch(
  () => [fixedDraftTileLimit.value, hasFixedDraftTileLimit.value],
  ([maxCount, hasFixedLimit]) => {
    if (!editing.value) return;
    if (useProgramGigs.value) {
      const sourceProgramTiles = programTilesWithOverrides.value;
      draftTiles.value = sourceProgramTiles
        .slice(0, hasFixedLimit ? maxCount : Number.POSITIVE_INFINITY)
        .map((existing, index) => createDraftTile(existing, index));
      if (expandedItem.value >= draftTiles.value.length) {
        expandedItem.value = draftTiles.value.length - 1;
      }
      return;
    }
    if (!hasFixedLimit) return;
    if (draftTiles.value.length > maxCount) {
      draftTiles.value.splice(maxCount);
      if (expandedItem.value >= draftTiles.value.length) {
        expandedItem.value = draftTiles.value.length - 1;
      }
      return;
    }

    if (draftTiles.value.length < maxCount) {
      const currentTiles = Array.isArray(section.value?.tiles) ? section.value.tiles : [];
      const nextDraft = [...draftTiles.value];
      for (let index = nextDraft.length; index < maxCount; index += 1) {
        nextDraft.push(createDraftTile(currentTiles[index], index));
      }
      draftTiles.value = nextDraft;
    }
  }
);

watch(currentAdminTab, (tab) => {
  if (!state.isAdmin) return;
  if (tab === "content") {
    startEdit();
    if (state.canAdminGeneral) {
      loadMediaTags();
    }
    if (useProgramGigs.value && !state.programSharedLoaded) {
      void fetchProgramSharedData();
    }
  }
  else editing.value = false;
}, { immediate: true });

watch(
  () => JSON.stringify(section.value?.tiles || []),
  () => {
    if (useProgramGigs.value) return;
    if (!state.isAdmin) return;
    if (currentAdminTab.value !== "content") return;
    const prevExpanded = expandedItem.value;
    startEdit();
    if (prevExpanded >= 0 && prevExpanded < draftTiles.value.length) {
      expandedItem.value = prevExpanded;
    }
  }
);

watch(
  () => JSON.stringify({
    enabled: useProgramGigs.value,
    shared: useProgramGigs.value ? (state.programSharedGigs || []) : [],
    order: section.value?.programTileOrder ?? [],
    overrides: section.value?.programTileOverrides ?? {},
    aspectRatio: aspectRatio.value,
  }),
  () => {
    if (!useProgramGigs.value) return;
    if (!state.isAdmin) return;
    if (currentAdminTab.value !== "content") return;
    const prevExpanded = expandedItem.value;
    startEdit();
    if (prevExpanded >= 0 && prevExpanded < draftTiles.value.length) {
      expandedItem.value = prevExpanded;
    }
  }
);

watch(useProgramGigs, (enabled) => {
  if (state.isAdmin && currentAdminTab.value === "content") {
    startEdit();
  }
  if (!enabled) return;
  if (!state.programSharedLoaded) {
    void fetchProgramSharedData();
  }
}, { immediate: true });

watch(
  () => [
    resolveSelectedIntegrationIdFromMapping(sectionIntegrationMapping.value),
    resolveSelectedIntegrationIdFromMapping(programSectionIntegrationMapping.value),
    useProgramGigs.value,
    currentAdminTab.value,
    state.isAdmin,
  ],
  () => {
    if (!state.isAdmin || currentAdminTab.value !== "content") return;
    void loadFilterSourceIntegrationFieldOptions();
  },
  { immediate: true },
);

const gridRef = ref(null);
const gridContainerWidth = ref(0);
const GAP = 0;
const TRANSITION_MS = 450;
const lastExpandedIndex = ref(-1);
let zIndexTimer = null;
let gridResizeObserver = null;

function resolveAutoWrapColumnCount({
  containerWidth,
  itemCount,
  minWidth,
  maxWidth,
  fallbackColumns = 3,
}) {
  const normalizedItemCount = Math.max(1, Math.floor(Number(itemCount) || 0));
  if (normalizedItemCount <= 1) return 1;

  const normalizedWidth = Math.max(0, Number(containerWidth) || 0);
  const normalizedMinWidth = Math.max(1, Number(minWidth) || DEFAULT_TILE_MIN_WIDTH);
  const normalizedMaxWidth = Math.max(
    normalizedMinWidth,
    Number(maxWidth) || DEFAULT_TILE_MAX_WIDTH,
  );
  if (normalizedWidth <= 0) {
    return Math.max(1, Math.min(normalizedItemCount, Math.round(fallbackColumns) || 1));
  }

  let bestInRange = 0;
  let nearestCount = 1;
  let nearestViolation = Number.POSITIVE_INFINITY;

  for (let candidate = 1; candidate <= normalizedItemCount; candidate += 1) {
    const tileWidth = normalizedWidth / candidate;
    if (tileWidth >= normalizedMinWidth && tileWidth <= normalizedMaxWidth) {
      bestInRange = candidate;
      continue;
    }
    const violation = tileWidth < normalizedMinWidth
      ? (normalizedMinWidth - tileWidth)
      : (tileWidth - normalizedMaxWidth);
    if (violation < nearestViolation || (violation === nearestViolation && candidate > nearestCount)) {
      nearestViolation = violation;
      nearestCount = candidate;
    }
  }

  return bestInRange || nearestCount;
}

function updateGridContainerWidth() {
  gridContainerWidth.value = Math.max(0, Number(gridRef.value?.clientWidth || 0));
}

const autoWrapSourceItemCount = computed(() => {
  if (isFilterActive.value) return filteredSourceTiles.value.length;
  return sourceTiles.value.length;
});

const effectiveDisplayColumns = computed(() => {
  if (isMobileViewport.value) return MOBILE_TILE_COLUMNS;
  if (!isAutoMode.value) return columns.value;
  return resolveAutoWrapColumnCount({
    containerWidth: gridContainerWidth.value,
    itemCount: autoWrapSourceItemCount.value,
    minWidth: tileMinWidth.value,
    maxWidth: tileMaxWidth.value,
    fallbackColumns: columns.value,
  });
});

const effectiveDisplayRows = computed(() => {
  if (!isMobileViewport.value && !isFilterActive.value && isFixedMode.value) {
    return rows.value;
  }
  const cols = Math.max(1, effectiveDisplayColumns.value);
  return Math.max(1, Math.ceil(displayTiles.value.length / cols));
});

const canScaleTilesUp = computed(() =>
  effectiveDisplayColumns.value >= 2 && effectiveDisplayRows.value >= 2
);

const isSingleRowFilterResults = computed(() =>
  isFilterActive.value && effectiveDisplayRows.value < 2
);

const canActivateTilePrimary = computed(() =>
  canScaleTilesUp.value || (isSingleRowFilterResults.value && isMobileViewport.value)
);

const treatTilesAsScaledOnHover = computed(() =>
  isSingleRowFilterResults.value && !canScaleTilesUp.value
);

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${effectiveDisplayColumns.value}, 1fr)`,
  gridTemplateRows: `repeat(${effectiveDisplayRows.value}, 1fr)`,
  "--tile-aspect-ratio": ratioToCss(aspectRatio.value, direction.value),
  "--tile-title-base-color": titleGradientBaseColor.value + "a0",
  "--tile-title-gradient-background": tileTitleGradientBackground.value,
  "--tile-title-color": tileTitleTextColor.value,
}));

const unfilteredDisplayColumns = computed(() => {
  if (isMobileViewport.value) return MOBILE_TILE_COLUMNS;
  if (!isAutoMode.value) return columns.value;
  return resolveAutoWrapColumnCount({
    containerWidth: gridContainerWidth.value,
    itemCount: sourceTiles.value.length,
    minWidth: tileMinWidth.value,
    maxWidth: tileMaxWidth.value,
    fallbackColumns: columns.value,
  });
});

const tileFilterBarStyle = computed(() => {
  const cols = Math.max(1, Number(unfilteredDisplayColumns.value) || 1);
  const containerWidth = Math.max(0, Number(gridContainerWidth.value) || 0);
  if (containerWidth <= 0) return {};
  const tileWidth = containerWidth / cols;
  const oneByOneTileHeight = tileWidth;
  const filterHeight = oneByOneTileHeight * 0.2;
  return {
    "--tile-filter-width": `${Math.max(0, tileWidth)}px`,
    "--tile-filter-height": `${Math.max(0, filterHeight)}px`,
    "--tile-filter-item-height": `${Math.max(0, filterHeight)}px`,
  };
});

watch(
  () => [effectiveDisplayColumns.value, effectiveDisplayRows.value],
  () => {
    expandedIndex.value = -1;
    clearAllTileChevronTimers();
    visibleTileChevronByIndex.value = {};
    hoveredIndex.value = -1;
    focusedIndex.value = -1;
  }
);

watch(
  () => displayTiles.value.length,
  () => {
    clearAllTileChevronTimers();
    visibleTileChevronByIndex.value = {};
    hoveredIndex.value = -1;
    focusedIndex.value = -1;
    void nextTick(() => {
      updateGridContainerWidth();
    });
  }
);

function tileRow(index) {
  return Math.floor(index / effectiveDisplayColumns.value);
}
function tileCol(index) {
  return index % effectiveDisplayColumns.value;
}

/**
 * Pick the 2x2 anchor that pulls the expansion toward the grid center.
 * The tile must be inside the 2x2 area ([anchor, anchor+1]).
 */
function expandAnchor(index) {
  const r = tileRow(index);
  const c = tileCol(index);
  const centerCol = (effectiveDisplayColumns.value - 1) / 2;
  const centerRow = (effectiveDisplayRows.value - 1) / 2;

  let ac = c < centerCol ? c : c > centerCol ? c - 1 : c;
  let ar = r < centerRow ? r : r > centerRow ? r - 1 : r;

  ac = Math.max(0, Math.min(effectiveDisplayColumns.value - 2, ac));
  ar = Math.max(0, Math.min(effectiveDisplayRows.value - 2, ar));

  return { anchorRow: ar, anchorCol: ac };
}

/**
 * Compute scale + translate so the tile covers exactly the 2x2 anchor area
 * while the animation visually moves toward the grid center.
 * Uses transform-origin 50% 50% so expand and collapse are symmetric.
 */
function expandTransform(index) {
  const { anchorRow, anchorCol } = expandAnchor(index);
  const r = tileRow(index);
  const c = tileCol(index);

  let s = 2;
  let stepX = 1; // (cellW + GAP) / cellW — ratio for translate units
  let stepY = 1;

  if (gridRef.value) {
    const cols = effectiveDisplayColumns.value;
    const rws = effectiveDisplayRows.value;
    const w = gridRef.value.clientWidth;
    const h = gridRef.value.clientHeight;
    const cellW = (w - (cols - 1) * GAP) / cols;
    const cellH = (h - (rws - 1) * GAP) / rws;
    if (cellW > 0) {
      s = (2 * cellW + GAP) / cellW;
      stepX = (cellW + GAP) / cellW;
    }
    if (cellH > 0) {
      stepY = (cellH + GAP) / cellH;
    }
  }

  const txPct = (anchorCol - c + 0.5) * stepX * 100;
  const tyPct = (anchorRow - r + 0.5) * stepY * 100;

  return { s, txPct, tyPct };
}

function resolveTileImageRenderScale(index) {
  if (!canScaleTilesUp.value) return 1;
  if (!Number.isFinite(index)) return 2;
  const { s } = expandTransform(index);
  return Number.isFinite(s) && s > 1 ? s : 2;
}

function resolveTileImageSlotWidth() {
  const cols = Math.max(1, Number(effectiveDisplayColumns.value) || 1);
  const containerFromGrid = Math.max(0, Number(gridContainerWidth.value) || 0);
  const containerFromViewport = Math.max(0, Number(state.viewportWidth) || 0);
  const containerWidth = containerFromGrid > 0 ? containerFromGrid : containerFromViewport;
  if (containerWidth <= 0) return 0;
  const cellWidth = (containerWidth - (cols - 1) * GAP) / cols;
  return cellWidth > 0 ? cellWidth : 0;
}

function tileStyle(index) {
  const isExpanded = expandedIndex.value === index;
  const isCollapsing = lastExpandedIndex.value === index;

  if (isExpanded && canScaleTilesUp.value) {
    const { s, txPct, tyPct } = expandTransform(index);
    return {
      transform: `translate(${txPct}%, ${tyPct}%) scale(${s})`,
      zIndex: 10,
    };
  }

  if (isExpanded) {
    return { zIndex: 10 };
  }

  if (isCollapsing) {
    return { zIndex: 10 };
  }

  return {};
}

function isTileOverlayActive(index) {
  if (expandedIndex.value === index) return true;
  if (!treatTilesAsScaledOnHover.value) return false;
  return hoveredIndex.value === index || focusedIndex.value === index;
}

function toggleExpand(index) {
  if (effectiveDisplayColumns.value < 2 || effectiveDisplayRows.value < 2) return;

  clearTimeout(zIndexTimer);

  if (expandedIndex.value === index) {
    lastExpandedIndex.value = index;
    expandedIndex.value = -1;
    hoveredIndex.value = -1;
    focusedIndex.value = -1;
    hideTileChevron(index);
    zIndexTimer = setTimeout(() => {
      lastExpandedIndex.value = -1;
    }, TRANSITION_MS + 50);
  } else {
    lastExpandedIndex.value = -1;
    expandedIndex.value = index;
    if (isTouchLikeDevice.value) {
      scheduleTileChevron(index, displayTiles.value[index]);
    }
  }
}

function toggleSingleRowMobileOverlay(index) {
  clearTimeout(zIndexTimer);

  if (expandedIndex.value === index) {
    lastExpandedIndex.value = index;
    expandedIndex.value = -1;
    hoveredIndex.value = -1;
    focusedIndex.value = -1;
    hideTileChevron(index);
    zIndexTimer = setTimeout(() => {
      lastExpandedIndex.value = -1;
    }, TRANSITION_MS + 50);
    return;
  }

  lastExpandedIndex.value = -1;
  expandedIndex.value = index;
  scheduleTileChevron(index, displayTiles.value[index]);
}

function handleTilePrimaryAction(index) {
  if (canScaleTilesUp.value) {
    toggleExpand(index);
    return;
  }
  if (isSingleRowFilterResults.value && isMobileViewport.value) {
    toggleSingleRowMobileOverlay(index);
  }
}

function setColumns(val) {
  updateSection(effectiveKey.value, { columns: Math.max(1, Math.min(10, val)) }, { revisionKind: "design" });
  expandedIndex.value = -1;
}

function setRows(val) {
  updateSection(effectiveKey.value, { rows: Math.max(1, Math.min(10, val)) }, { revisionKind: "design" });
  expandedIndex.value = -1;
}

function setGridMode(value) {
  const normalized = normalizeGridMode(value);
  updateSection(effectiveKey.value, { gridMode: normalized }, { revisionKind: "design" });
  expandedIndex.value = -1;
}

function setTileSortMode(value) {
  const normalized = normalizeTileSortMode(value);
  if (normalized !== "manual") {
    tileManualReorderActive.value = false;
  }
  updateSection(
    effectiveKey.value,
    { tileSortMode: normalized },
    { revisionKind: "content" }
  );
  expandedIndex.value = -1;
}

function setTileManualReorderActive(enabled) {
  tileManualReorderActive.value = tileSortMode.value === "manual" && Boolean(enabled);
}

function setTileMinWidth(value) {
  const normalizedMin = normalizeTileGridWidth(value, DEFAULT_TILE_MIN_WIDTH);
  const normalizedMax = Math.max(tileMaxWidth.value, normalizedMin);
  updateSection(
    effectiveKey.value,
    { tileMinWidth: normalizedMin, tileMaxWidth: normalizedMax },
    { revisionKind: "design" },
  );
  expandedIndex.value = -1;
}

function setTileMaxWidth(value) {
  const normalizedMax = Math.max(
    tileMinWidth.value,
    normalizeTileGridWidth(value, DEFAULT_TILE_MAX_WIDTH),
  );
  updateSection(effectiveKey.value, { tileMaxWidth: normalizedMax }, { revisionKind: "design" });
  expandedIndex.value = -1;
}

function setUseProgramGigs(enabled) {
  const next = Boolean(enabled);
  updateSection(
    effectiveKey.value,
    { useProgramGigs: next },
    { revisionKind: "content" }
  );
  if (next && !state.programSharedLoaded) {
    void fetchProgramSharedData();
  }
}

function setAspectRatio(value) {
  updateSection(effectiveKey.value, { aspectRatio: normalizeRatio(value, "1:1") }, { revisionKind: "design" });
}

function setDirection(value) {
  updateSection(effectiveKey.value, { direction: value === "portrait" ? "portrait" : "landscape" }, { revisionKind: "design" });
}

function setTileFilterControlStyle(value) {
  updateSection(
    effectiveKey.value,
    { filterControlStyle: normalizeTileFilterControlStyle(value) },
    { revisionKind: "design" }
  );
}

function setTileShowResetButton(enabled) {
  updateSection(
    effectiveKey.value,
    { tileShowResetButton: Boolean(enabled) },
    { revisionKind: "design" }
  );
}

function setTileTopInfoAlign(value) {
  updateSection(
    effectiveKey.value,
    { tileTopInfoAlign: normalizeTileTopInfoAlign(value) },
    { revisionKind: "design" }
  );
}

function setTileBottomInfoAlign(value) {
  updateSection(
    effectiveKey.value,
    { tileBottomInfoAlign: normalizeTileBottomInfoAlign(value) },
    { revisionKind: "design" }
  );
}

function setAlwaysShowTitle(enabled) {
  updateSection(
    effectiveKey.value,
    { alwaysShowTitle: Boolean(enabled) },
    { revisionKind: "design" }
  );
}

function resolveTileTitle(tile) {
  if (tile?.title && typeof tile.title === "object") return tile.title;
  return { de: "", en: "" };
}

function hasTileTitle(tile) {
  return Boolean(String(localizedText(resolveTileTitle(tile)) || "").trim());
}

function hasTileSubtitle(tile) {
  return Boolean(String(localizedText(resolveTileSubtitle(tile)) || "").trim());
}

function showTileBottomInfo(index, tile) {
  if (isTileOverlayActive(index)) return hasTileTitle(tile) || hasTileSubtitle(tile);
  if (!hasTileTitle(tile)) return false;
  return alwaysShowTitle.value || hoveredIndex.value === index || focusedIndex.value === index;
}

function shouldUseTileRenderFallback(tile, options = {}) {
  if (options?.fallback === false) return false;
  const rawUrl = String(tile?.imageUrl || "").trim();
  if (rawUrl) return false;
  return true;
}

function resolveTileFallbackMedia(index = 0) {
  const fallback = resolveFallbackImageForIndex(effectiveTileFallbackConfig.value, index);
  if (!fallback?.imageUrl) {
    return {
      url: "",
      responsiveVariants: [],
      zoom: 1,
      focalX: 50,
      focalY: 50,
      rotation: 0,
    };
  }
  return {
    url: fallback.imageUrl,
    responsiveVariants: Array.isArray(fallback.responsiveVariants)
      ? fallback.responsiveVariants
      : [],
    zoom: fallback.zoom,
    focalX: fallback.focalX,
    focalY: fallback.focalY,
    rotation: fallback.rotation,
  };
}

function resolveTileImagePayload(source, index = 0, options = {}) {
  const image = source && typeof source === "object" ? source : {};
  const media = {
    url: String(image.imageUrl || "").trim(),
    responsiveVariants: Array.isArray(image.responsiveVariants)
      ? image.responsiveVariants
      : [],
  };
  if (media.url || !shouldUseTileRenderFallback(image, options)) return media;
  return resolveTileFallbackMedia(index);
}

function resolveBackendTileImagePayload(source) {
  return resolveBackendResponsiveImagePayload(source, {
    urlKeys: ["image_url", "url", "src", "href"],
  });
}

function resolveTileImageUrl(tile, index = 0, options = {}) {
  const media = resolveTileImagePayload(tile, index, options);
  return media.url || "";
}

function resolveTileResponsiveVariants(tile, index = 0, options = {}) {
  return resolveTileImagePayload(tile, index, options).responsiveVariants;
}

function resolveTileImageZoom(tile, index = 0, options = {}) {
  if (String(tile?.imageUrl || "").trim()) return normalizeTileZoom(tile.zoom);
  if (!shouldUseTileRenderFallback(tile, options)) return normalizeTileZoom(tile?.zoom);
  return normalizeTileZoom(resolveTileFallbackMedia(index).zoom);
}

function resolveTileImageFocalX(tile, index = 0, options = {}) {
  if (String(tile?.imageUrl || "").trim()) return normalizeTileFocal(tile.focalX);
  if (!shouldUseTileRenderFallback(tile, options)) return normalizeTileFocal(tile?.focalX);
  return normalizeTileFocal(resolveTileFallbackMedia(index).focalX);
}

function resolveTileImageFocalY(tile, index = 0, options = {}) {
  if (String(tile?.imageUrl || "").trim()) return normalizeTileFocal(tile.focalY);
  if (!shouldUseTileRenderFallback(tile, options)) return normalizeTileFocal(tile?.focalY);
  return normalizeTileFocal(resolveTileFallbackMedia(index).focalY);
}

function resolveTileImageRotation(tile, index = 0, options = {}) {
  if (String(tile?.imageUrl || "").trim()) return normalizeTileRotation(tile.rotation);
  if (!shouldUseTileRenderFallback(tile, options)) return normalizeTileRotation(tile?.rotation);
  return normalizeTileRotation(resolveTileFallbackMedia(index).rotation);
}

function resolveTileSubtitle(tile) {
  if (tile?.subtitle && typeof tile.subtitle === "object") return tile.subtitle;
  return { de: "", en: "" };
}

function resolveTileItemUrl(tile) {
  const directUrl = String(tile?.itemUrl || "").trim();
  if (directUrl) {
    if (/^https?:\/\//i.test(directUrl)) return directUrl;
    return directUrl.startsWith("/") ? directUrl : `/${directUrl.replace(/^\/+/, "")}`;
  }
  const slug = String(tile?.pageSlug || "").trim();
  if (!slug) return "";
  return slug.startsWith("/") ? slug : `/${slug.replace(/^\/+/, "")}`;
}

function resolveTileEditorOpenUrl(tile) {
  const resolved = resolveTileItemUrl(tile);
  if (!resolved) return "";
  if (!isInternalRoutePath(resolved)) return resolved;
  if (/[?&]noredirect=1(?:&|$)/.test(resolved)) return resolved;
  return resolved.includes("?")
    ? `${resolved}&noredirect=1`
    : `${resolved}?noredirect=1`;
}

function canOpenTileItemPage(tile) {
  return Boolean(resolveTileEditorOpenUrl(tile));
}

function openTileItemPage(tile) {
  const targetUrl = resolveTileEditorOpenUrl(tile);
  if (!targetUrl || typeof window === "undefined") return;
  window.open(targetUrl, "_blank", "noopener,noreferrer");
}

function normalizeProgramIntegrationSourceId(value) {
  return String(value || "").trim();
}

function resolveTileProgramIntegrationId(tile) {
  const programSource = resolveTileProgramSource(tile);
  const directSourceId = normalizeProgramIntegrationSourceId(
    programSource?.[PROGRAM_IMPORT_SOURCE_KEY]
      ?? tile?.[PROGRAM_IMPORT_SOURCE_KEY]
  );
  if (directSourceId) return directSourceId;

  const cacheSourceId = normalizeProgramIntegrationSourceId(
    programGigsIntegrationCacheState.value?.integration_id
      ?? programGigsIntegrationCacheState.value?.integration_mapping?.selected_integration_id
  );
  if (cacheSourceId) return cacheSourceId;

  return normalizeProgramIntegrationSourceId(
    programSectionIntegrationMapping.value?.selected_integration_id
  );
}

function resolveTileProgramReviewItemKey(tile) {
  const programSource = resolveTileProgramSource(tile);
  return String(
    programSource?.integration_item_key
      ?? programSource?.integrationItemKey
      ?? programSource?.template_integration_item_key
      ?? programSource?.templateIntegrationItemKey
      ?? programSource?.review_item_key
      ?? programSource?.reviewItemKey
      ?? tile?.integration_item_key
      ?? tile?.integrationItemKey
      ?? tile?.template_integration_item_key
      ?? tile?.templateIntegrationItemKey
      ?? tile?.review_item_key
      ?? tile?.reviewItemKey
      ?? ""
  ).trim();
}

function resolveTileIntegrationReviewRoute(tile) {
  const integrationId = resolveTileProgramIntegrationId(tile);
  const itemKey = resolveTileProgramReviewItemKey(tile);
  if (!integrationId || !itemKey) return null;
  return {
    path: "/admin/integrations/review",
    query: { integrationId, itemKey },
  };
}

function canOpenTileIntegrationReviewItem(tile) {
  return Boolean(resolveTileIntegrationReviewRoute(tile));
}

function openTileIntegrationReviewItem(tile) {
  const route = resolveTileIntegrationReviewRoute(tile);
  if (!route) return;
  router.push(route);
}

function normalizeInternalTileItemPath(value) {
  const raw = String(value || "").trim();
  if (!isInternalRoutePath(raw)) return "";
  const pathWithoutHash = raw.split("#", 1)[0] || "";
  const pathWithoutQuery = pathWithoutHash.split("?", 1)[0] || "";
  const normalized = pathWithoutQuery.trim();
  if (!normalized || normalized === "/") return "/";
  return `/${normalized.replace(/^\/+/, "").replace(/\/+$/, "")}`;
}

function normalizePublicSlugFromInternalPath(path) {
  const normalizedPath = normalizeInternalTileItemPath(path);
  if (!normalizedPath) return "";
  return normalizedPath === "/" ? "landing" : normalizedPath.slice(1);
}

const internalTileItemPaths = computed(() => {
  const paths = new Set();
  displayTiles.value.forEach((tile) => {
    if (!tile || typeof tile !== "object" || tile._filler) return;
    const normalizedPath = normalizeInternalTileItemPath(resolveTileItemUrl(tile));
    if (!normalizedPath) return;
    paths.add(normalizedPath);
  });
  return Array.from(paths).sort((left, right) => left.localeCompare(right));
});

async function syncTileItemPageAvailability(paths) {
  const normalizedPaths = Array.isArray(paths) ? paths : [];
  const requestToken = ++tileItemAvailabilitySyncToken;
  if (normalizedPaths.length === 0) {
    tileItemPageAvailabilityByPath.value = {};
    return;
  }

  const uniqueSlugs = Array.from(
    new Set(
      normalizedPaths
        .map((path) => normalizePublicSlugFromInternalPath(path))
        .filter(Boolean)
    )
  );
  let availabilityBySlug = {};
  if (uniqueSlugs.length > 0) {
    try {
      availabilityBySlug = await api.getPublicPagesAvailability(uniqueSlugs);
    } catch {
      availabilityBySlug = {};
    }
  }

  const entries = normalizedPaths.map((path) => {
    const slug = normalizePublicSlugFromInternalPath(path);
    return [path, slug ? availabilityBySlug?.[slug] === true : false];
  });
  if (requestToken !== tileItemAvailabilitySyncToken) return;
  tileItemPageAvailabilityByPath.value = Object.fromEntries(entries);
}

function resolveTilePublicItemUrl(tile) {
  const normalizedPath = normalizeInternalTileItemPath(resolveTileItemUrl(tile));
  if (!normalizedPath) return "";
  return tileItemPageAvailabilityByPath.value?.[normalizedPath] === true ? normalizedPath : "";
}

watch(
  () => internalTileItemPaths.value.join("|"),
  () => {
    void syncTileItemPageAvailability(internalTileItemPaths.value);
  },
  { immediate: true },
);

function normalizeTileLocationValue(value, depth = 0) {
  if (depth > 5) return "";
  if (value == null) return "";
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value).trim();
  if (!value || typeof value !== "object") return "";

  if ("de" in value || "en" in value) {
    const localized = localizedText(value);
    const de = String(value?.de || "").trim();
    const en = String(value?.en || "").trim();
    return String(localized || de || en || "").trim();
  }

  const preferredKeys = ["name", "title", "label", "text", "stage_name", "stageName", "value", "id"];
  for (const key of preferredKeys) {
    if (!Object.prototype.hasOwnProperty.call(value, key)) continue;
    const nested = normalizeTileLocationValue(value[key], depth + 1);
    if (nested) return nested;
  }

  return "";
}

function resolveTileLocation(tile) {
  const explicitLocation = normalizeTileLocationValue(tile?.location);
  if (explicitLocation) return explicitLocation;
  return normalizeTileLocationValue(tile?.stage);
}

function showTileLocation(tile) {
  if (useProgramGigs.value) return Boolean(resolveTileLocation(tile));
  if (!shouldShowTileLocationFromMapping.value) return false;
  return Boolean(resolveTileLocation(tile));
}

function resolveTileDateTimeRaw(tile) {
  return String(
    tile?.dateTime
    || tile?.time
    || ""
  ).trim();
}

function parseTileDateTime(rawValue) {
  const raw = String(rawValue || "").trim();
  if (!raw) return null;
  const normalized = raw.includes("T")
    ? raw
    : (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}/.test(raw) ? raw.replace(/\s+/, "T") : raw);
  const serverWallDate = serverWallDateTimeToLocalDate(normalized);
  if (serverWallDate) return serverWallDate;
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

function formatTileDateTimeInputValue(value) {
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) return "";
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  const hour = String(value.getHours()).padStart(2, "0");
  const minute = String(value.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hour}:${minute}`;
}

function tileDateTimeModel(rawValue) {
  return parseTileDateTime(rawValue);
}

function setDraftDateTime(index, modelValue) {
  if (index < 0 || index >= draftTiles.value.length) return;
  if (!useProgramGigs.value && isTileItemFieldLocked(index, "dateTime")) return;
  let nextValue = "";
  if (modelValue instanceof Date) {
    nextValue = formatTileDateTimeInputValue(modelValue);
  } else if (Array.isArray(modelValue) && modelValue[0] instanceof Date) {
    nextValue = formatTileDateTimeInputValue(modelValue[0]);
  } else if (typeof modelValue === "string") {
    const parsed = parseTileDateTime(modelValue);
    nextValue = parsed ? formatTileDateTimeInputValue(parsed) : String(modelValue || "").trim();
  }

  const tile = draftTiles.value[index];
  tile.dateTime = nextValue;
  tile.time = nextValue;
}

function formatTileDateTime(rawValue) {
  const raw = String(rawValue || "").trim();
  if (!raw) return "";
  const locale = state.lang === "de" ? "de-DE" : "en-US";
  const wallParts = parseServerWallDateTimeParts(raw);
  if (!wallParts) {
    return formatInstantInServerTimezone(
      raw,
      {
        weekday: "short",
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      },
      { locale, fallback: raw }
    );
  }
  const dateKey = [
    String(wallParts.year).padStart(4, "0"),
    String(wallParts.month).padStart(2, "0"),
    String(wallParts.day).padStart(2, "0"),
  ].join("-");
  const weekdayShort = formatServerDateOnly(dateKey, { weekday: "short" }, { locale });
  const weekday = weekdayShort
    .replace(/[^A-Za-zÀ-ÖØ-öø-ÿ]/g, "")
    .slice(0, 2)
    .toLocaleUpperCase(locale);
  const datePart = formatServerDateOnly(dateKey, {
    day: "2-digit",
    month: "2-digit",
  }, { locale });
  const time = formatServerWallTime(raw, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    hourCycle: "h23",
  }, { locale });
  return `${weekday} ${datePart} ${time}`.trim();
}

function resolveTileDateTime(tile) {
  return formatTileDateTime(resolveTileDateTimeRaw(tile));
}

function isInternalRoutePath(value) {
  const path = String(value || "").trim();
  return Boolean(path.startsWith("/") && !path.startsWith("//"));
}

function createDraftTile(existing = null, index = 0) {
  const existingItem = (existing && typeof existing === "object") ? existing : {};
  const media = resolveTileImagePayload(existingItem, index, { fallback: false });
  const dateTime = resolveTileDateTimeRaw(existingItem);
  const title = resolveTileTitle(existingItem);
  const subtitle = resolveTileSubtitle(existingItem);
  const location = resolveTileLocation(existingItem);
  return {
    ...existingItem,
    id: existingItem?.id || String(Date.now() + Math.random() + index),
    imageUrl: media.url || "",
    responsiveVariants: media.responsiveVariants,
    zoom: normalizeTileZoom(existingItem?.zoom),
    focalX: normalizeTileFocal(existingItem?.focalX),
    focalY: normalizeTileFocal(existingItem?.focalY),
    rotation: normalizeTileRotation(existingItem?.rotation),
    title: {
      de: title?.de || "",
      en: title?.en || "",
    },
    subtitle: {
      de: subtitle?.de || "",
      en: subtitle?.en || "",
    },
    location,
    dateTime,
    time: dateTime,
    pageSlug: String(existingItem?.pageSlug || "").trim(),
    itemUrl: String(existingItem?.itemUrl || "").trim(),
  };
}

function normalizeTileFromBackend(tile, index) {
  if (!tile || typeof tile !== "object") return createDraftTile(null, index);
  return createDraftTile(
    {
      ...tile,
      imageUrl: resolveTileImagePayload(tile, index, { fallback: false }).url || "",
      focalX: tile.focalX,
      focalY: tile.focalY,
      title: tile.title || { de: "", en: "" },
      subtitle: tile.subtitle || { de: "", en: "" },
      location: resolveTileLocation(tile),
      dateTime: tile.dateTime || tile.time || "",
      time: tile.time || tile.dateTime || "",
      pageSlug: tile.pageSlug || "",
      itemUrl: tile.itemUrl || "",
    },
    index
  );
}

function addDraftFilter() {
  const nextIndex = draftFilters.value.length + 1;
  const nextFilter = {
    id: `filter-${Date.now()}-${nextIndex}`,
    name: "",
    targetPath: "",
    manualOptions: [],
  };
  const nextOrder = draftFilterControlOrder.value.filter((id) => id !== nextFilter.id);
  const resetIndex = nextOrder.indexOf(FILTER_RESET_CONTROL_ID);
  if (resetIndex === nextOrder.length - 1) {
    nextOrder.splice(resetIndex, 0, nextFilter.id);
  } else {
    nextOrder.push(nextFilter.id);
  }
  setDraftFiltersAndOrder([...draftFilters.value, nextFilter], nextOrder);
}

function updateDraftFilter(index, patch = {}) {
  if (index < 0 || index >= draftFilters.value.length || !patch || typeof patch !== "object") return;
  const next = [...draftFilters.value];
  next[index] = {
    ...(next[index] || {}),
    ...patch,
  };
  setDraftFiltersAndOrder(next, draftFilterControlOrder.value);
}

function removeDraftFilter(index) {
  if (index < 0 || index >= draftFilters.value.length) return;
  const next = [...draftFilters.value];
  const removedId = String(next[index]?.id || "").trim();
  next.splice(index, 1);
  const nextOrder = draftFilterControlOrder.value.filter((id) => id !== removedId);
  setDraftFiltersAndOrder(next, nextOrder);
}

function setDraftFiltersAndOrder(nextFilters, rawOrder = draftFilterControlOrder.value, { autosave = true } = {}) {
  draftFilters.value = normalizeTileFilterDefinitions(nextFilters);
  draftFilterControlOrder.value = normalizeTileFilterControlOrder(
    rawOrder,
    draftFilters.value,
    { includeReset: tileShowResetButton.value }
  );
  if (autosave) saveFilters();
}

function applyDraftFilterItemOrder(nextOrder, { autosave = true } = {}) {
  const normalizedOrder = normalizeTileFilterControlOrder(
    nextOrder,
    normalizedDraftFilters.value,
    { includeReset: tileShowResetButton.value }
  );
  const orderedFilterIds = normalizedOrder.filter((id) => id !== FILTER_RESET_CONTROL_ID);
  const orderedIdSet = new Set(orderedFilterIds);
  const filtersById = new Map();
  draftFilters.value.forEach((filter) => {
    const id = String(filter?.id || "").trim();
    if (id && !filtersById.has(id)) filtersById.set(id, filter);
  });
  const orderedFilters = orderedFilterIds
    .map((id) => filtersById.get(id))
    .filter(Boolean);
  const missingFilters = draftFilters.value.filter((filter) => {
    const id = String(filter?.id || "").trim();
    return !id || !orderedIdSet.has(id);
  });
  draftFilters.value = normalizeTileFilterDefinitions([...orderedFilters, ...missingFilters]);
  draftFilterControlOrder.value = normalizeTileFilterControlOrder(
    normalizedOrder,
    draftFilters.value,
    { includeReset: tileShowResetButton.value }
  );
  if (autosave) saveFilters();
}

function onDraftFilterDraggableUpdate(nextItems = []) {
  const nextOrder = (Array.isArray(nextItems) ? nextItems : [])
    .map((item) => String(item?.id || "").trim())
    .filter(Boolean);
  applyDraftFilterItemOrder(nextOrder);
}

function saveFilters() {
  updateSection(
    effectiveKey.value,
    {
      filters: normalizedDraftFiltersForSave(),
      filterControlOrder: normalizedDraftFilterControlOrderForSave(),
    },
    { revisionKind: "content" }
  );
}

function startEdit() {
  expandedItem.value = -1;
  draftFilters.value = configuredTileFiltersFromContent.value.map((entry) => ({ ...entry }));
  draftFilterControlOrder.value = normalizeTileFilterControlOrder(
    section.value?.filterControlOrder,
    draftFilterControlSourceFilters.value,
    { includeReset: tileShowResetButton.value }
  );
  void loadFilterSourceIntegrationFieldOptions();
  const maxDraftTiles = hasFixedDraftTileLimit.value ? fixedDraftTileLimit.value : Number.POSITIVE_INFINITY;
  if (useProgramGigs.value) {
    draftTiles.value = programTilesWithOverrides.value
      .slice(0, maxDraftTiles)
      .map((existing, index) => createDraftTile(existing, index));
  } else {
    const current = section.value?.tiles || [];
    draftTiles.value = current.slice(0, maxDraftTiles).map((existing, index) => createDraftTile(existing, index));
  }
  editing.value = true;
}

function addDraftTile() {
  if (useProgramGigs.value) return;
  if (!canAddDraftTile.value) return;
  draftTiles.value.push(createDraftTile(null, draftTiles.value.length));
  expandedItem.value = draftTiles.value.length - 1;
  void saveTiles({ flush: true });
}

function removeDraftTile(index) {
  if (useProgramGigs.value) return;
  if (index < 0 || index >= draftTiles.value.length) return;
  draftTiles.value.splice(index, 1);
  if (expandedItem.value === index) {
    expandedItem.value = draftTiles.value.length ? Math.min(index, draftTiles.value.length - 1) : -1;
  } else if (expandedItem.value > index) {
    expandedItem.value -= 1;
  }
}

async function saveTiles(options = {}) {
  if (useProgramGigs.value) {
    const normalizedOrder = draftTiles.value
      .map((tile) => String(tile?.id || "").trim())
      .filter(Boolean);
    const overrides = {};
    const transformsLockedToProgramGigs = shouldUseProgramGigImageTransform.value;
    if (!transformsLockedToProgramGigs) {
      draftTiles.value.forEach((tile) => {
        const tileId = String(tile?.id || "").trim();
        if (!tileId) return;
        const baseTile = programBaseTileMapById.value.get(tileId);
        if (!baseTile) return;
        const nextOverride = {
          zoom: normalizeTileZoom(tile?.zoom),
          focalX: normalizeTileFocal(tile?.focalX),
          focalY: normalizeTileFocal(tile?.focalY),
          rotation: normalizeTileRotation(tile?.rotation),
        };
        const baseTransform = {
          zoom: normalizeTileZoom(baseTile?.zoom),
          focalX: normalizeTileFocal(baseTile?.focalX),
          focalY: normalizeTileFocal(baseTile?.focalY),
          rotation: normalizeTileRotation(baseTile?.rotation),
        };
        if (
          nextOverride.zoom === baseTransform.zoom
          && nextOverride.focalX === baseTransform.focalX
          && nextOverride.focalY === baseTransform.focalY
          && nextOverride.rotation === baseTransform.rotation
        ) {
          return;
        }
        overrides[tileId] = {
          zoom: nextOverride.zoom,
          focalX: nextOverride.focalX,
          focalY: nextOverride.focalY,
          rotation: nextOverride.rotation,
        };
      });
    }
    updateSection(
      effectiveKey.value,
      {
        programTileOrder: normalizedOrder,
        programTileOverrides: transformsLockedToProgramGigs ? {} : overrides,
      },
      { revisionKind: "content" }
    );
    if (options?.flush) {
      await saveSectionByKey(effectiveKey.value, { revisionKind: "content" });
    }
    return;
  }
  const maxDraftTiles = hasFixedDraftTileLimit.value ? fixedDraftTileLimit.value : Number.POSITIVE_INFINITY;
  const normalizedTiles = draftTiles.value.slice(0, maxDraftTiles).map((tile) => {
    const dateTime = resolveTileDateTimeRaw(tile);
    const title = resolveTileTitle(tile);
    const subtitle = resolveTileSubtitle(tile);
    const location = resolveTileLocation(tile);
    return {
      ...tile,
      zoom: normalizeTileZoom(tile.zoom),
      focalX: normalizeTileFocal(tile.focalX),
      focalY: normalizeTileFocal(tile.focalY),
      rotation: normalizeTileRotation(tile.rotation),
      title: { de: String(title?.de || ""), en: String(title?.en || "") },
      subtitle: { de: String(subtitle?.de || ""), en: String(subtitle?.en || "") },
      location,
      dateTime,
      time: dateTime,
    };
  });
  updateSection(effectiveKey.value, { tiles: normalizedTiles });
  if (options?.flush) {
    await saveSectionByKey(effectiveKey.value, { revisionKind: "content" });
  }
}

function setFallbackTransform(patch) {
  const mapped = {};
  if (patch.zoom !== undefined) mapped.filterFallbackZoom = normalizeTileZoom(patch.zoom);
  if (patch.focalX !== undefined) mapped.filterFallbackFocalX = normalizeTileFocal(patch.focalX);
  if (patch.focalY !== undefined) mapped.filterFallbackFocalY = normalizeTileFocal(patch.focalY);
  if (patch.rotation !== undefined) mapped.filterFallbackRotation = normalizeTileRotation(patch.rotation);
  if (Object.keys(mapped).length) {
    updateSection(effectiveKey.value, mapped, { revisionKind: "content" });
  }
}

function onMediaSelect(selection) {
  if (useProgramGigs.value) {
    closeMediaPicker();
    return;
  }
  const { index, direct } = consumeMediaPickerSelectionContext();
  if (
    index >= 0 &&
    index < draftTiles.value.length
  ) {
    if (isTileItemFieldLocked(index, "imageUrl")) {
      closeMediaPicker();
      return;
    }
    const item = draftTiles.value[index];
    const media = resolveBackendTileImagePayload(selection);
    item.imageUrl = String(media.url || "").trim();
    item.responsiveVariants = media.responsiveVariants;
    item.zoom = normalizeTileZoom(item.zoom);
    item.focalX = normalizeTileFocal(item.focalX);
    item.focalY = normalizeTileFocal(item.focalY);
    item.rotation = normalizeTileRotation(item.rotation);
    if (direct) saveTiles();
  }
  closeMediaPicker();
}

function setDraftTransform(index, patch) {
  if (index < 0 || index >= draftTiles.value.length) return;
  const tile = draftTiles.value[index];
  const nextPatch = { ...(patch || {}) };
  if (!useProgramGigs.value) {
    Object.keys(nextPatch).forEach((key) => {
      if (isTileItemFieldLocked(index, key)) delete nextPatch[key];
    });
  }
  if (!Object.keys(nextPatch).length) return;
  draftTiles.value[index] = {
    ...tile,
    ...nextPatch,
    zoom: normalizeTileZoom((nextPatch && nextPatch.zoom !== undefined) ? nextPatch.zoom : tile.zoom),
    focalX: normalizeTileFocal((nextPatch && nextPatch.focalX !== undefined) ? nextPatch.focalX : tile.focalX),
    focalY: normalizeTileFocal((nextPatch && nextPatch.focalY !== undefined) ? nextPatch.focalY : tile.focalY),
    rotation: normalizeTileRotation((nextPatch && nextPatch.rotation !== undefined) ? nextPatch.rotation : tile.rotation),
  };
}

function setDraftImageUrl(index, value) {
  if (useProgramGigs.value) return;
  if (index < 0 || index >= draftTiles.value.length) return;
  if (isTileItemFieldLocked(index, "imageUrl")) return;
  const tile = draftTiles.value[index];
  const nextUrl = String(value || "").trim();
  const previousUrl = String(tile?.imageUrl || "").trim();
  draftTiles.value[index] = {
    ...tile,
    imageUrl: nextUrl,
    responsiveVariants: nextUrl === previousUrl
      ? (Array.isArray(tile?.responsiveVariants) ? tile.responsiveVariants : [])
      : [],
  };
}

async function loadMediaTags() {
  loadingMediaTags.value = true;
  try {
    const response = await api.listAssetTags();
    mediaTagOptions.value = Array.isArray(response?.tags)
      ? response.tags.map((tag) => String(tag || "").trim()).filter(Boolean)
      : [];
  } catch (err) {
    console.error("Failed to load media tags:", err);
    mediaTagOptions.value = [];
  } finally {
    loadingMediaTags.value = false;
  }
}

async function listAllAssetsByTag(tag) {
  const cleanTag = String(tag || "").trim();
  if (!cleanTag) return [];
  const maxPages = 40;
  const pageSize = 100;
  let page = 1;
  let hasMore = true;
  const collected = [];

  while (hasMore && page <= maxPages) {
    const response = await api.listAssets({ page, pageSize, tag: cleanTag });
    const items = Array.isArray(response?.items) ? response.items : [];
    collected.push(...items);
    hasMore = Boolean(response?.has_more);
    page += 1;
  }

  return collected;
}

function clearFallbackImages() {
  updateSection(
    effectiveKey.value,
    {
      filterFallbackImages: [],
      filterFallbackMediaTag: null,
      filterFallbackImageUrl: null,
    },
    { revisionKind: "content" }
  );
}

function setTileFallbackOverrideEnabled(enabled) {
  updateSection(
    effectiveKey.value,
    { tileFallbackOverrideEnabled: Boolean(enabled) },
    { revisionKind: "content" }
  );
}

function applyFallbackImages(payload = {}) {
  updateSection(
    effectiveKey.value,
    {
      filterFallbackImages: Array.isArray(payload.images) ? payload.images : [],
      filterFallbackMediaTag: String(payload.mediaTag || "").trim() || null,
      filterFallbackImageUrl: null,
    },
    { revisionKind: "content" }
  );
}

async function importTilesFromMediaTag() {
  if (!selectedMediaTag.value) return;

  importingFromMediaTag.value = true;
  mediaTagImportStatus.value = null;
  try {
    const assets = await listAllAssetsByTag(selectedMediaTag.value);
    const mappedTiles = assets
      .map((asset, index) => {
        const media = resolveBackendTileImagePayload(asset);
        const imageUrl = String(media.url || "").trim();
        if (!imageUrl) return null;
        return createDraftTile(
          {
            id: `tile-tag-${Date.now()}-${index}`,
            imageUrl,
            responsiveVariants: media.responsiveVariants,
            title: { de: "", en: "" },
            subtitle: { de: "", en: "" },
            location: "",
            time: "",
          },
          index
        );
      })
      .filter(Boolean);

    if (mappedTiles.length === 0) {
      mediaTagImportStatus.value = {
        type: "error",
        message: "No media assets with usable URLs found for this tag.",
      };
      return;
    }

    const existingTiles = Array.isArray(section.value?.tiles)
      ? section.value.tiles.map((tile, index) => createDraftTile(tile, index))
      : [];
    const seedTiles = mediaTagImportMode.value === "append" ? existingTiles : [];
    const combinedTiles = [...seedTiles, ...mappedTiles];

    let savedCount = combinedTiles.length;
    if (isFixedMode.value) {
      const fixedColumns = Math.max(1, Math.min(10, Number(columns.value) || 1));
      const maxTiles = fixedColumns * 10;
      const limitedTiles = combinedTiles.slice(0, maxTiles);
      const requiredRows = Math.max(1, Math.ceil(limitedTiles.length / fixedColumns));
      savedCount = limitedTiles.length;
      updateSection(
        effectiveKey.value,
        {
          tiles: limitedTiles,
          rows: Math.max(rows.value || 1, requiredRows),
        },
        { revisionKind: "both" }
      );
      mediaTagImportStatus.value = {
        type: "success",
        message: limitedTiles.length < combinedTiles.length
          ? `Imported ${limitedTiles.length} tiles (limited by max grid size of ${maxTiles}).`
          : `Imported ${mappedTiles.length} tiles from media tag "${selectedMediaTag.value}".`,
      };
    } else {
      updateSection(
        effectiveKey.value,
        { tiles: combinedTiles },
        { revisionKind: "content" }
      );
      mediaTagImportStatus.value = {
        type: "success",
        message: `Imported ${mappedTiles.length} tiles from media tag "${selectedMediaTag.value}" (total: ${savedCount}).`,
      };
    }
    startEdit();
  } catch (err) {
    console.error("Failed to import tiles from media tag:", err);
    mediaTagImportStatus.value = {
      type: "error",
      message: err?.message || "Failed to import tiles from media tag.",
    };
  } finally {
    importingFromMediaTag.value = false;
  }
}

function clearAllTiles() {
  if (useProgramGigs.value) return;
  draftTiles.value = [];
  expandedItem.value = -1;
  saveTiles();
}
</script>

<style scoped>
/* ---- Admin controls ---- */
.admin-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.tile-design-controls {
  display: grid;
  align-items: stretch;
  gap: 10px;
}

.tile-design-group {
  display: grid;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--admin-border, var(--border));
  border-radius: 8px;
  background: #fff;
}

.tile-design-group-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted, #64748b);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.tile-design-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
  align-items: start;
}

.admin-actions--tile-content-params {
  margin-top: 6px;
  align-items: flex-start;
}

.grid-control {
  display: grid;
  align-items: start;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
}

.grid-control--wide {
  min-width: 260px;
  flex: 1;
}

.grid-control--checkbox {
  display: grid;
  gap: 6px;
  align-items: start;
}

.field-checkbox-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text, #1f2937);
}

.grid-input {
  width: 70px;
  padding: 4px 8px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  text-align: center;
}

.grid-input--wide {
  width: 100%;
  min-width: 220px;
  text-align: left;
}

.grid-input--select {
  width: auto;
  min-width: 110px;
  text-align: left;
}

.tile-sort-controls {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.tile-sort-control,
.tile-sort-reorder-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text, #1f2937);
}

.tile-sort-reorder-toggle {
  cursor: pointer;
}

.tile-sort-reorder-toggle input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.color-input {
  width: 32px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  background: none;
}

.color-link-control {
  position: relative;
}

.variation-select {
  min-width: 68px;
  padding: 4px 6px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 12px;
}

.color-swatch {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 2px solid var(--border, rgba(15,23,42,0.14));
  cursor: pointer;
  flex-shrink: 0;
}

.color-input-hidden {
  position: absolute;
  width: 0;
  height: 0;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
}

.control-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
}

.tile-filter-bar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  row-gap: 8px;
  column-gap: 0;
  align-items: flex-end;
  margin-bottom: 24px;
}

.tile-filter-bar :deep(.tf-dropdown) {
  width: var(--tile-filter-width, 220px);
  min-width: 0;
  max-width: 100%;
  flex: 0 0 var(--tile-filter-width, 220px);
}

.tile-filter-bar--pills,
.tile-filter-bar--segmented {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  justify-content: stretch;
  align-items: stretch;
}

.tile-filter-choice-group {
  display: grid;
  gap: 6px;
  flex: 1 1 min(320px, 100%);
  min-width: min(260px, 100%);
  width: 100%;
}

.tile-filter-choice-label {
  color: var(--tile-title-base-color, #0f172a);
  font-size: 14px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.tile-filter-choice-options {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.tile-filter-choice {
  min-height: 36px;
  max-width: 100%;
  padding: 0 14px;
  border: none;
  color: var(--tile-title-base-color, #0f172a);
  font-weight: 700;
  cursor: pointer;
  overflow-wrap: anywhere;
}

.tile-filter-choice--active {
  background: var(--tile-title-base-color, #0f172a);
  color: var(--tile-title-color, #fff);
}

.tile-filter-choice--active:hover,
.tile-filter-choice--active:focus-visible {
  background: color-mix(in srgb, var(--tile-title-base-color, #0f172a) 88%, white 12%);
}

.tile-filter-choice-group--segmented .tile-filter-choice-options {
  flex-wrap: nowrap;
  gap: 0;
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
}

.tile-filter-choice-group--segmented .tile-filter-choice {
  min-height: var(--tile-filter-height, 50px);
  border: none;
  border-right: 1px solid color-mix(in srgb, var(--tile-title-base-color, #0f172a) 24%, transparent);
  background: transparent;
  flex: 0 0 auto;
}

.tile-filter-choice-group--segmented .tile-filter-choice--active {
  background: var(--tile-title-base-color, #0f172a);
  color: var(--tile-title-color, #fff);
}

.tile-filter-choice-group--segmented .tile-filter-choice--active:hover,
.tile-filter-choice-group--segmented .tile-filter-choice--active:focus-visible {
  background: color-mix(in srgb, var(--tile-title-base-color, #0f172a) 88%, white 12%);
  color: var(--tile-title-color, #fff);
}

.tile-filter-choice-group--segmented .tile-filter-choice:last-child {
  border-right: none;
}

.tile-filter-reset {
  width: var(--tile-filter-width, 220px);
  min-width: 0;
  max-width: 100%;
  flex: 0 0 var(--tile-filter-width, 220px);
  min-height: var(--tile-filter-height, 50px);
  border: none;
  background: var(--tile-title-base-color, #0f172a);
  color: var(--tile-title-color, #fff);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  cursor: pointer;
}

.tile-filter-reset:hover:not(:disabled),
.tile-filter-reset:focus-visible:not(:disabled) {
  background: color-mix(in srgb, var(--tile-title-base-color, #0f172a) 88%, white 12%);
  outline: none;
}

.tile-filter-reset:disabled {
  opacity: 0.45;
  cursor: default;
}


/* ---- Tiles grid ---- */
.tiles-grid {
  display: grid;
  gap: 0px;
  background: black;
}

.tile {
  position: relative;
  overflow: hidden;
  cursor: pointer;
  border: 0;
  aspect-ratio: var(--tile-aspect-ratio, 1 / 1);
  transform: scale(1);
  transition:
    transform 0.45s cubic-bezier(0.4, 0, 0.15, 1),
    opacity 0.35s ease,
    border-radius 0.45s ease;
}

.tile--non-actionable {
  cursor: default;
}

.tile:hover,
.tile:focus-visible,
.tile--dimmed {
  will-change: transform, opacity;
}

.tile:focus-visible {
  outline: 2px solid rgba(255, 255, 255, 0.9);
  outline-offset: -2px;
}

.tile--dimmed .tile-checker,
.tile--dimmed .tile-placeholder {
  filter: brightness(0.3);
  transition: filter 0.3s ease;
}

.tile--dimmed .tile-img :deep(img) {
  filter: brightness(0.3);
  transition: filter 0.3s ease;
}

.tile-checker {
  position: absolute;
  inset: 0;
  z-index: 0;
}

.tile-img {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
}

.tile-img :deep(img) { transition: filter 1s ease; }

.tile-placeholder {
  width: 100%;
  height: 100%;
  background: var(--surface-2, #eef2f7);
}

.tile-top-info {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 3;
  display: inline-flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  opacity: 0;
  transform: translateY(-8px);
  transition: opacity 0.2s ease, transform 0.2s ease;
  pointer-events: none;
  color: var(--tile-title-color, #fff);
}

.tile-top-info--align-left {
  left: 10px;
  right: auto;
  align-items: flex-start;
}

.tile-top-info--align-right {
  left: auto;
  right: 10px;
  align-items: flex-end;
}

.tile-top-info--visible {
  opacity: 1;
  transform: translateY(1px);
}

.tile-top-stage,
.tile-top-time {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  background: var(--tile-title-base-color, #0f172a);
  color: var(--tile-title-color, #fff);
  font-size: 11px;
  line-height: 1.25;
  letter-spacing: 0.03em;
}

/* ---- Bottom Title + Expanded Meta ---- */
.tile-bottom-info {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 10% 5% 7.5%;;
  background: var(
    --tile-title-gradient-background,
    linear-gradient(to top, rgba(0, 0, 0, 0.9) 0%, rgba(0, 0, 0, 0.6) 60%, rgba(0, 0, 0, 0) 100%)
  );
  transform: translateY(100%);
  opacity: 0;
  transition: padding 0.25s ease, gap 0.25s ease, transform 0.25s ease, opacity 0.25s ease;
  pointer-events: none;
}

.tile-bottom-info--align-left {
  align-items: flex-start;
  text-align: left;
}

.tile-bottom-info--align-center {
  align-items: center;
  text-align: center;
}

.tile-bottom-info--align-right {
  align-items: flex-end;
  text-align: right;
}

.tile-bottom-info--align-left .tile-bottom-title-row {
  justify-content: flex-start;
}

.tile-bottom-info--align-center .tile-bottom-title-row {
  justify-content: center;
}

.tile-bottom-info--align-right .tile-bottom-title-row {
  justify-content: flex-end;
}

.tile-bottom-info--align-left .tile-bottom-title {
  text-align: left;
}

.tile-bottom-info--align-center .tile-bottom-title {
  text-align: center;
}

.tile-bottom-info--align-right .tile-bottom-title {
  text-align: right;
}

.tile-bottom-info--visible {
  transform: translateY(1px);
  opacity: 1;
}

.tile-bottom-title {
  color: var(--tile-title-color, #fff);
  font-family: var(--header-font-family);
  font-weight: var(--header-font-weight, 800);
  font-size: clamp(14px, 1.45vw, 22px);
  text-align: left;
  line-height: 1.2;
  transition: opacity 0.2s ease;
}

.tile-bottom-info--muted-title .tile-bottom-title {
  opacity: 0.46;
}

.tile-bottom-title-row {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.tile-chevron-overlay {
  pointer-events: none;
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%) translateX(18px) rotate(27deg);
  z-index: 4;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 24px;
  padding: 3px 8px;
  border-radius: 4px;
  color: var(--tile-title-color, #fff);
  text-decoration: none;
  background: var(--tile-title-base-color, #0f172a);
  opacity: 0;
  transition: transform 0.22s ease, opacity 0.22s ease, background 0.16s ease;
}

.tile-chevron-overlay--visible {
  pointer-events: auto;
  opacity: 1;
  transform: translateY(-50%) translateX(0) rotate(0deg);
}

.tile--single-row-overlay .tile-bottom-info span,
.tile--single-row-overlay .tile-top-info span,
.tile--single-row-overlay .tile-chevron-overlay--visible span {
  font-size: 1.4em;
}

.tile-chevron-overlay:hover,
.tile-chevron-overlay:focus-visible {
  background: rgba(15, 23, 42, 0.9);
}

.tile-chevron-overlay-icon {
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
}

.tile-chevron-overlay-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  line-height: 1;
}

@media (max-width: 900px) {
  .tile-chevron-overlay {
    right: 6px;
    padding: 2px 7px;
    min-height: 22px;
    gap: 5px;
  }

  .tile-chevron-overlay-icon {
    font-size: 10px;
  }

  .tile-chevron-overlay-label {
    font-size: 10px;
    letter-spacing: 0.02em;
  }
}

.tile-bottom-subtitle {
  display: grid;
  grid-template-rows: 1fr;
  overflow: hidden;
  width: 100%;
  color: var(--tile-title-color);
  font-size: clamp(10px, 0.5vw, 14px);
  line-height: 1.2;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 1;
}

.tile-bottom-subtitle-inner {
  display: inline-block;
  min-height: 0;
}

.tile-subtitle-scale-enter-active {
  transition:
    grid-template-rows 0.28s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.08s ease 0.2s;
}

.tile-subtitle-scale-leave-active {
  transition:
    grid-template-rows 0.22s cubic-bezier(0.4, 0, 1, 1),
    opacity 0.1s ease;
}

.tile-subtitle-scale-enter-from,
.tile-subtitle-scale-leave-to {
  grid-template-rows: 0fr;
  opacity: 0;
}

.tile-subtitle-scale-enter-to,
.tile-subtitle-scale-leave-from {
  grid-template-rows: 1fr;
  opacity: 1;
}

.tile-image-transform-editor--program-source :deep(.transform-frame),
.tile-image-transform-editor--program-source :deep(.transform-controls) {
  opacity: 0.62;
}

.tile-image-transform-editor--program-source :deep(.transform-frame) {
  cursor: not-allowed;
}

.tile-image-transform-editor--program-source :deep(.transform-focus-hint) {
  display: none;
}

.item-pages-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.item-pages-status {
  font-size: 12px;
  color: var(--muted, #64748b);
}

.item-pages-status.success {
  color: #15803d;
}

.item-pages-status.warn {
  color: #b45309;
}

.item-pages-status.error {
  color: #b91c1c;
}

.item-field-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.field-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted, rgba(43, 12, 92, 0.55));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.lang-section {
  display: grid;
  gap: 3px;
}

.tile-bilingual-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.lang-header {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted, rgba(43, 12, 92, 0.55));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field {
  flex: 1;
  min-width: 0;
  border-radius: 8px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.2));
  background: #fff;
  padding: 6px 10px;
  outline: none;
  color: var(--text, #2b0c5c);
  font: inherit;
}

.tile-datetime-picker {
  width: 100%;
}

.tile-datetime-picker :deep(.dp__input_wrap) {
  width: 100%;
}

.tile-datetime-picker :deep(.dp__input) {
  width: 100%;
  border-radius: 8px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.2));
  background: #fff;
  outline: none;
  color: var(--text, #2b0c5c);
  font: inherit;
}

.tile-datetime-picker :deep(.dp__input:focus) {
  border-color: rgba(59, 130, 246, 0.55);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.item-page-route {
  min-height: 32px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.2));
  border-radius: 8px;
  background: #fff;
  padding: 6px 10px;
  font-size: 12px;
  color: var(--text, #2b0c5c);
  word-break: break-all;
}

.item-page-route--empty {
  color: var(--muted, #64748b);
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.integration-import-panel,
.tile-filters-panel {
  border: 0;
  border-radius: 8px;
  background: transparent;
}

.integration-import-title,
.tile-filters-title {
  font-weight: 600;
  color: #374151;
  cursor: pointer;
  padding: 0.75rem;
  background: white;
  border-radius: 8px;
  list-style: none;
}

.integration-import-title::-webkit-details-marker,
.tile-filters-title::-webkit-details-marker {
  display: none;
}

.integration-import-title::before,
.tile-filters-title::before {
  content: "▸ ";
  color: #9ca3af;
}

.integration-import-panel[open] .integration-import-title::before,
.tile-filters-panel[open] .tile-filters-title::before {
  content: "▾ ";
}

.integration-import-content,
.tile-filters-content {
  display: grid;
  gap: 10px;
  padding: 1rem;
  background: white;
  border-radius: 0 0 8px 8px;
  margin-top: -4px;
}

.tile-filter-info {
  display: grid;
  gap: 5px;
  margin: 0;
  padding: 10px 11px;
  border-radius: 8px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.2));
  border-left: 3px solid transparent;
  background: rgba(255, 255, 255, 0.82);
}

.tile-filter-info-title {
  margin: 0;
  font-size: 11px;
  line-height: 1.3;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--text, #2b0c5c);
}

.tile-filter-info-text {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--muted, #64748b);
}

.tile-filter-info--tip {
  border-color: rgba(37, 99, 235, 0.28);
  border-left-color: rgba(37, 99, 235, 0.45);
  background: rgba(37, 99, 235, 0.08);
}

.tile-filter-info--tip .tile-filter-info-title {
  color: #1d4ed8;
}

.tile-filter-info--tip .tile-filter-info-text {
  color: #1e40af;
}

.tile-filter-code {
  display: inline-block;
  margin: 0 2px;
  padding: 1px 6px;
  border-radius: 5px;
  border: 1px solid rgba(30, 64, 175, 0.22);
  background: rgba(255, 255, 255, 0.82);
  color: #1e3a8a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  font-size: 11px;
  line-height: 1.35;
  white-space: nowrap;
}

.tile-filters-list {
  display: grid;
  gap: 10px;
}

.tile-filters-row {
  display: grid;
  gap: 10px;
  grid-template-columns: auto minmax(160px, 0.9fr) minmax(240px, 1.4fr) auto;
  align-items: end;
  padding: 10px;
  border: 1px solid rgba(100, 116, 139, 0.18);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.68);
}

.tile-filters-row--ghost {
  opacity: 0.45;
  background: rgba(219, 234, 254, 0.78);
}

.tile-filters-row--chosen {
  border-color: rgba(37, 99, 235, 0.35);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
}

.tile-filters-row--drag {
  cursor: grabbing;
}

.tile-filters-row--reset {
  grid-template-columns: auto minmax(160px, 1fr) auto;
  align-items: center;
  background: rgba(248, 250, 252, 0.9);
}

.tile-filter-drag-handle {
  width: 32px;
  height: 36px;
  display: inline-grid;
  place-items: center;
  align-self: end;
  border: 1px solid rgba(100, 116, 139, 0.18);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
  color: #64748b;
  cursor: grab;
}

.tile-filter-drag-handle:active {
  cursor: grabbing;
}

.tile-filter-drag-handle:hover,
.tile-filter-drag-handle:focus-visible {
  color: #1d4ed8;
  border-color: rgba(37, 99, 235, 0.35);
  outline: none;
}

.tile-filters-row--reset .tile-filter-drag-handle {
  align-self: center;
}

.tile-filters-field {
  display: grid;
  gap: 4px;
}

.tile-filter-name-input {
  height: 36px;
  min-height: 36px;
  resize: none;
  overflow: hidden;
  white-space: nowrap;
}

.tile-filter-remove {
  justify-self: end;
  min-height: 36px;
}

.tile-filter-reset-row-label {
  min-width: 0;
  color: #0f172a;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tile-filter-reset-row-type {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.tile--filler {
  cursor: default;
  pointer-events: none;
}

.import-controls-row {
  display: flex;
  gap: 8px;
  align-items: end;
  flex-wrap: wrap;
}

.import-field {
  display: grid;
  gap: 4px;
  min-width: 260px;
  flex: 1;
}

.integration-select {
  border-radius: 8px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.2));
  background: #fff;
  padding: 7px 10px;
}

.integration-preview {
  border: 1px dashed var(--border, rgba(43, 12, 92, 0.2));
  border-radius: 8px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.8);
  overflow: hidden;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.preview-time {
  color: var(--muted, #64748b);
  font-size: 12px;
}

.preview-keys {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted, #64748b);
}

.preview-json {
  margin: 8px 0 0;
  max-height: 180px;
  overflow-x: hidden;
  white-space: pre-wrap;
  word-break: break-word;
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
  padding: 10px;
  font-size: 12px;
}

.import-field--compact {
  min-width: 180px;
  flex: 0 0 180px;
}

.integration-mapping {
  display: grid;
  gap: 8px;
}

.mapping-header {
  font-size: 13px;
  font-weight: 700;
  color: var(--text, #2b0c5c);
}

.mapping-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.mapping-row {
  display: grid;
  gap: 4px;
}

.mapping-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted, #64748b);
}

.mapping-select {
  border-radius: 8px;
  border: 1px solid var(--border, rgba(43, 12, 92, 0.2));
  background: #fff;
  padding: 7px 10px;
}

.import-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.import-status {
  font-size: 12px;
  font-weight: 600;
}

.import-status.success {
  color: #166534;
}

.import-status.error {
  color: #b91c1c;
}

/* ---- Responsive ---- */
@media (max-width: 600px) {
  .tile-editor-item {
    grid-template-columns: 1fr;
  }

  .mapping-grid {
    grid-template-columns: 1fr;
  }

  .tile-filters-row {
    grid-template-columns: auto minmax(0, 1fr);
    align-items: stretch;
  }

  .tile-filters-row--reset {
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
  }

  .tile-filters-row:not(.tile-filters-row--reset) .tile-filters-field,
  .tile-filters-row:not(.tile-filters-row--reset) .tile-filter-remove {
    grid-column: 1 / -1;
  }

  .tile-filter-drag-handle {
    align-self: start;
  }

  .tile-bilingual-row {
    grid-template-columns: 1fr;
  }
}
</style>
