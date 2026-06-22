<template>
  <SectionBase
    :section-key="effectiveKey"
    :section-data="section"
    :admin-tabs-visible="state.isAdmin && (!state.previewMode || isTemplateBuilderPage)"
    :admin-show-integration-importer="false"
  >
    <div class="program-container" :class="containerClasses" :style="programStyleVars">
      <div v-if="showProgramSelectionBar" class="program-selection-bar">
        <div class="program-selection-left">
          <!-- Day tabs (shown when grouping by day) -->
          <div v-if="showDaySelectionTabs" class="day-tabs">
            <button
              v-for="(day, idx) in sortedDays"
              :key="day"
              type="button"
              class="day-tab"
              :class="{ active: selectedDay === day }"
              @click="selectProgramDay(day)"
            >
              <span class="day-name">{{ formatDayName(day) }}</span>
              <span class="day-date">{{ formatDayDate(day) }}</span>
            </button>
          </div>
        </div>

        <div
          class="program-selection-right"
          :class="{ 'program-selection-right--centered': effectiveViewMode === 'timeline' && showStageSelectionTabs }"
        >
          <!-- Stage tabs (shown when grouping by stage) -->
          <div v-if="showStageSelectionTabs" class="stage-tabs">
            <button
              v-for="stage in stages"
              :key="stage.id"
              type="button"
              class="stage-tab"
              :class="{ active: selectedStage === stage.id }"
              :style="{ '--stage-color': getStageVisualColor(stage) }"
              @click="selectedStage = stage.id"
            >
              {{ localizedText(stage.name) }}
            </button>
          </div>

          <!-- Stage pills (shown when grouping by day) -->
          <div v-if="showStageFilterPills" class="stage-pills">
            <button
              type="button"
              class="stage-pill clear-filter"
              :class="{ active: !filterStage }"
              @click="filterStage = null"
            >
              {{ t.showAll }}
            </button>
            <button
              v-for="stage in stages"
              :key="stage.id"
              type="button"
              class="stage-pill"
              :class="{ active: filterStage === stage.id }"
              :style="{ '--stage-color': getStageVisualColor(stage) }"
              @click="toggleStageFilter(stage.id)"
            >
              {{ localizedText(stage.name) }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="isChangesView" class="program-changes-view">
        <div v-if="changedGigGroups.length === 0" class="empty-state compact">
          No changed gigs available.
        </div>
        <div v-for="dayGroup in changedGigGroups" :key="`changes-day-${dayGroup.day}`" class="changes-day-group">
          <h3 class="changes-day-title">{{ formatDayName(dayGroup.day) }} · {{ formatDayDate(dayGroup.day) }}</h3>
          <div
            v-for="stageGroup in dayGroup.stages"
            :key="`changes-stage-${dayGroup.day}-${stageGroup.stageId}`"
            class="changes-stage-group"
          >
            <h4 class="changes-stage-title">{{ stageGroup.stageName }}</h4>
            <div class="changes-gig-list">
              <article
                v-for="gig in stageGroup.gigs"
                :key="`changes-gig-${gig.id}`"
                class="changes-gig-card"
              >
                <div class="changes-gig-time">
                  <template v-if="hasGigTimeChange(gig)">
                    <span class="changed-old">{{ oldGigTimeRange(gig) }}</span>
                  </template>
                  {{ gig.start_time }} - {{ gig.end_time }}
                  <span v-if="hasGigDayChange(gig)" class="change-badge badge-warning">{{ t.dayChanged }}</span>
                  <span v-if="hasGigPureTimeChange(gig)" class="change-badge badge-warning">{{ t.timeChanged }}</span>
                </div>
                <div class="changes-gig-title">
	                  {{ localizedText(gigTitle(gig)) }}
                  <span v-if="isGigNew(gig)" class="change-badge badge-success">{{ t.newGig }}</span>
                  <span v-if="gig.__canceled" class="change-badge badge-danger">{{ t.canceled }}</span>
                </div>
                <div v-if="hasGigStageChange(gig)" class="changes-gig-stage">
                  <span class="changed-old">{{ oldGigStageName(gig) }}</span>
                  {{ getStageName(getGigStage(gig)) }}
                  <span class="change-badge badge-warning">{{ t.stageChanged }}</span>
                </div>
              </article>
            </div>
          </div>
        </div>
      </div>

      <!-- Now Playing View -->
      <div v-if="isNowView" class="program-now-view">
        <div class="now-view-columns">
          <div
            v-for="col in nowViewData"
            :key="`now-stage-${col.stage.id}`"
            class="now-stage-column"
            :style="{ '--stage-color': getStageVisualColor(col.stage) }"
          >
            <div class="now-stage-header">
              {{ localizedText(col.stage.name) }}
            </div>
            <div v-if="col.current" class="now-gig-card now-gig-card--playing">
              <span class="now-badge">{{ state.lang === 'de' ? 'Jetzt' : 'Now' }}</span>
	              <div class="now-gig-title">{{ localizedText(gigTitle(col.current)) }}</div>
              <div class="now-gig-time">{{ col.current.start_time }} – {{ col.current.end_time }}</div>
            </div>
            <div v-else class="now-gig-card now-gig-card--empty">
              <template v-if="col.next">
                <span class="now-next-label">{{ state.lang === 'de' ? 'Nächstes' : 'Next up' }}</span>
	                <div class="now-gig-title">{{ localizedText(gigTitle(col.next)) }}</div>
                <div class="now-gig-time">{{ col.next.start_time }} – {{ col.next.end_time }}</div>
              </template>
              <span v-else class="now-empty-label">{{ state.lang === 'de' ? 'Keine weiteren Acts' : 'No more acts' }}</span>
            </div>
            <div v-if="col.current && col.next" class="now-next-up">
              <span class="now-next-label">{{ state.lang === 'de' ? 'Danach' : 'Up next' }}</span>
	              <div class="now-next-title">{{ localizedText(gigTitle(col.next)) }}</div>
              <div class="now-next-time">{{ col.next.start_time }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Stage Detail Panel (shown when a stage is selected in stage view) -->
      <div v-if="!isChangesView && !isNowView && groupBy === 'stage' && selectedStageData" class="stage-detail-panel">
        <div class="stage-detail-header" :style="{ '--stage-color': getStageVisualColor(selectedStageData) }">
          <div class="stage-detail-info">
            <h3 class="stage-detail-name">{{ localizedText(selectedStageData.name) }}</h3>
            <p v-if="localizedText(selectedStageData.description)" class="stage-detail-description">
              {{ localizedText(selectedStageData.description) }}
            </p>
          </div>
        </div>
      </div>

      <!-- Grid View (Timetable) - By Day -->
      <div class="grid-view" v-show="!isChangesView && !isNowView && effectiveViewMode === 'gantt' && groupBy === 'day'">
        <div class="grid-layout">
          <!-- Fixed labels column -->
          <div class="labels-column">
            <div class="stage-labels">
              <div
                v-for="stage in stagesWithGigs"
                :key="'label-' + stage.id"
                class="stage-label"
                :class="{ 'stage-hidden': !isStageVisible(stage.id), 'stage-solo': isSoloStage && isStageVisible(stage.id) }"
                :style="{ '--lane-color': getStageVisualColor(stage) }"
                @click="openStageDetail(stage)"
              >
                <div class="stage-label-text">
                  <span class="stage-name">{{ localizedText(stage.name) }}</span>
                  <span class="stage-gig-count">{{ getGigsForStage(stage.id).length }} {{ t.acts }}</span>
                </div>
                <span class="stage-expand-icon">→</span>
              </div>
            </div>
          </div>
          <!-- Scrollable tracks -->
          <div class="tracks-scroll-container" ref="dayGanttScrollContainer">
            <div class="tracks-scroll-content" :style="{ width: ganttShouldScroll ? ganttWidthPercent + '%' : '100%' }">
              <!-- Gigs tracks -->
              <div class="gigs-tracks">
                <div
                  v-if="currentTimeMarkerLeftDay !== null"
                  class="current-time-marker current-time-marker--full"
                  :style="{ left: `${currentTimeMarkerLeftDay}%` }"
                  aria-hidden="true"
                >
                  <span class="current-time-dot current-time-dot--start"></span>
                  <span class="current-time-line"></span>
                  <span class="current-time-dot current-time-dot--end"></span>
                </div>
                <div
                  v-for="stage in stagesWithGigs"
                  :key="'track-' + stage.id"
                  class="gigs-track"
                  :class="{ 'stage-hidden': !isStageVisible(stage.id), 'stage-solo': isSoloStage && isStageVisible(stage.id) }"
                  :style="{ '--lane-color': getStageVisualColor(stage) }"
                >
                  <!-- Time grid lines -->
                  <div class="time-grid-lines">
                    <div
                      v-for="marker in quarterHourMarkers"
                      :key="marker.time"
                      class="time-grid-line"
                      :class="{ 'hour-line': marker.isHour, 'quarter-line': !marker.isHour }"
                      :style="{ left: `${getHourPosition(marker.time)}%` }"
                    >
                      <span v-if="marker.isHour" class="time-grid-label">{{ formatHour(marker.time) }}</span>
                    </div>
                  </div>
                  <template v-for="gig in getGigsForStage(stage.id)" :key="gig.id">
                    <div
                      v-if="isGigInTimeRange(gig)"
                      class="gig-bubble"
                      :class="{ expanded: expandedGig === gig.id && !usesDetachedGigPopup, closing: closingGig === gig.id && !usesDetachedGigPopup, 'gig-canceled': gig.__canceled, 'gig-description-visible': isGigDescriptionVisible(gig) && !usesDetachedGigPopup, 'gig-muted': isMutedFixedGig(gig), 'gig-fixed-focus': isFixedGigFocus(gig) }"
                      :style="getGigBubbleStyle(gig)"
                      @click="toggleGig(gig.id)"
                    >
                      <div class="gig-bubble-content">
                        <div class="gig-bubble-main">
                          <Transition name="gig-overlay-replace" mode="out-in">
                            <div v-if="isGigDescriptionVisible(gig) && !usesDetachedGigPopup" :key="`description-${gig.id}`" class="gig-description-panel" @click.stop>
	                              <h3 class="gig-description-title">{{ localizedText(gigTitle(gig)) }}</h3>
                              <p class="gig-description-text">{{ getGigDescriptionText(gig) }}</p>
                            </div>
                            <div v-else :key="`summary-${gig.id}`" class="gig-bubble-summary">
                              <span class="gig-time">
                                <template v-if="showChanges && hasGigTimeChange(gig)">
                                  <span class="changed-old">{{ oldGigStartTime(gig) }}</span>
                                </template>
                                {{ gig.start_time }}
                              </span>
                              <span class="gig-title">
	                                <template v-if="showChanges && hasGigFieldChange(gig, 'title')">
                                  <span class="changed-old">{{ oldGigTitle(gig) }}</span>
                                </template>
	                                {{ localizedText(gigTitle(gig)) }}
                                <span v-if="showChanges && isGigNew(gig)" class="change-badge badge-success">{{ t.newGig }}</span>
                                <span v-if="gig.__canceled" class="change-badge">{{ t.canceled }}</span>
                              </span>
                              <span v-if="localizedText(gig.genre) || (showChanges && hasGigFieldChange(gig, 'genre'))" class="gig-overlay-genre">
                                <template v-if="showChanges && hasGigFieldChange(gig, 'genre')">
                                  <span class="changed-old">{{ oldGigGenre(gig) }}</span>
                                </template>
                                {{ localizedText(gig.genre) }}
                              </span>
                            </div>
                          </Transition>
                        </div>
                        <div class="gig-bubble-details" :class="{ open: expandedGig === gig.id && !usesDetachedGigPopup }">
                          <TransformedImage
                            v-if="resolveProgramGigImageUrl(gig)"
                            :src="resolveProgramGigImageUrl(gig)"
                            :responsive-variants="resolveProgramGigResponsiveVariants(gig)"
	                            :alt="localizedText(gigTitle(gig))"
                            class="gig-image"
                            ratio="1:1"
                            direction="landscape"
                            :zoom="resolveProgramGigImageZoom(gig)"
                            :focal-x="resolveProgramGigImageFocalX(gig)"
                            :focal-y="resolveProgramGigImageFocalY(gig)"
                            :rotation="resolveProgramGigImageRotation(gig)"
                            fit="cover"
                            loading="lazy"
                            decoding="async"
                          />
                          <div class="gig-detail-meta-row">
                            <span v-if="localizedText(gig.genre) || (showChanges && hasGigFieldChange(gig, 'genre'))" class="gig-meta-chip gig-genre-tag">
                              <template v-if="showChanges && hasGigFieldChange(gig, 'genre')">
                                <span class="changed-old">{{ oldGigGenre(gig) }}</span>
                              </template>
                              {{ localizedText(gig.genre) }}
                            </span>
                            <span class="gig-meta-chip gig-day-time-tag">
                              <template v-if="showChanges && hasGigTimeChange(gig)">
                                <span class="changed-old">{{ formatGigOverlayDateTime(gig, true) }}</span>
                              </template>
                              {{ formatGigOverlayDateTime(gig) }}
                            </span>
                            <span class="gig-meta-chip gig-stage-tag">
                              <template v-if="showChanges && hasGigStageChange(gig)">
                                <span class="changed-old">{{ oldGigStageName(gig) }}</span>
                              </template>
                              {{ getStageName(getGigStage(gig)) }}
                              <span v-if="showChanges && hasGigStageChange(gig)" class="change-badge badge-warning">{{ t.stageChanged }}</span>
                            </span>
                          </div>
                        </div>
                      </div>
                      <div class="gig-details-actions">
                        <button
                          class="gig-popup-chevron gig-popup-chevron--previous"
                          type="button"
                          :aria-label="t.previousGig"
                          :title="t.previousGig"
                          :disabled="!canNavigateExpandedGig(gig, -1)"
                          @click.stop="navigateExpandedGig(-1)"
                        >
                          <font-awesome-icon :icon="faChevronLeft" />
                        </button>
                        <div class="gig-popup-primary-actions" :class="{ 'gig-popup-primary-actions--single': !showGigDescriptionButton }">
                          <button
                            class="gig-popup-action gig-more-btn"
                            type="button"
                            :aria-label="getGigPopupMoreButtonAriaLabel(gig)"
                            :title="getGigPopupMoreButtonTitle(gig)"
                            :disabled="!isGigPopupMoreButtonEnabled(gig)"
                            @click.stop="openGeneratedItemPage(gig)"
                          >
                            {{ getGigPopupMoreButtonLabel(gig) }}
                          </button>
                          <button
                            v-if="showGigDescriptionButton"
                            class="gig-popup-action gig-description-btn"
                            type="button"
                            :class="{ active: isGigDescriptionVisible(gig) }"
                            :disabled="!hasGigDescription(gig)"
                            @click.stop="toggleGigDescription(gig)"
                          >
                            {{ isGigDescriptionVisible(gig) ? t.info : t.description }}
                          </button>
                        </div>
                        <button
                          class="gig-popup-chevron gig-popup-chevron--next"
                          type="button"
                          :aria-label="t.nextGig"
                          :title="t.nextGig"
                          :disabled="!canNavigateExpandedGig(gig, 1)"
                          @click.stop="navigateExpandedGig(1)"
                        >
                          <font-awesome-icon :icon="faChevronRight" />
                        </button>
                      </div>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Grid View (Timetable) - By Stage -->
      <div class="grid-view" v-show="!isChangesView && !isNowView && effectiveViewMode === 'gantt' && groupBy === 'stage'">
        <div class="grid-layout">
          <!-- Fixed labels column -->
          <div class="labels-column">
            <div class="stage-labels day-labels">
              <div
                v-for="(day, idx) in stageViewDays"
                :key="'label-' + day"
                class="stage-label day-label"
                :class="{ 'stage-view-day-muted': isStageViewDayMuted(day) }"
                :style="{ '--lane-color': getStageVisualColor(selectedStageData) }"
              >
                <span class="day-label-name">{{ formatDayName(day) }}</span>
                <span class="day-label-date">{{ formatDayDate(day) }}</span>
              </div>
            </div>
          </div>
          <!-- Scrollable tracks -->
          <div class="tracks-scroll-container" ref="stageGanttScrollContainer">
            <div class="tracks-scroll-content" :style="{ width: ganttShouldScroll ? ganttWidthPercent + '%' : '100%' }">
              <!-- Day tracks -->
              <div class="gigs-tracks day-tracks">
                <div
                  v-if="currentTimeMarkerLeftStage !== null"
                  class="current-time-marker current-time-marker--full"
                  :style="{ left: `${currentTimeMarkerLeftStage}%` }"
                  aria-hidden="true"
                >
                  <span class="current-time-dot current-time-dot--start"></span>
                  <span class="current-time-line"></span>
                  <span class="current-time-dot current-time-dot--end"></span>
                </div>
                <div
                  v-for="(day, idx) in stageViewDays"
                  :key="'track-' + day"
                  class="gigs-track"
                  :class="{ 'stage-view-day-muted': isStageViewDayMuted(day) }"
                  :style="{ '--lane-color': getStageVisualColor(selectedStageData) }"
                >
                  <!-- Time grid lines -->
                  <div class="time-grid-lines">
                    <div
                      v-for="marker in quarterHourMarkersForStage"
                      :key="marker.time"
                      class="time-grid-line"
                      :class="{ 'hour-line': marker.isHour, 'quarter-line': !marker.isHour }"
                      :style="{ left: `${getHourPositionForStage(marker.time)}%` }"
                    >
                      <span v-if="marker.isHour" class="time-grid-label">{{ formatHour(marker.time) }}</span>
                    </div>
                  </div>
                  <template v-for="gig in getGigsForStageAndDay(activeStageForStageGrouping, day)" :key="gig.id">
                    <div
                      v-if="isGigInTimeRangeForStage(gig)"
                      class="gig-bubble"
                      :class="{ expanded: expandedGig === gig.id && !usesDetachedGigPopup, closing: closingGig === gig.id && !usesDetachedGigPopup, 'gig-canceled': gig.__canceled, 'gig-description-visible': isGigDescriptionVisible(gig) && !usesDetachedGigPopup, 'gig-muted': isMutedFixedGig(gig), 'gig-fixed-focus': isFixedGigFocus(gig) }"
                      :style="getGigBubbleStyleForStage(gig)"
                      @click="toggleGig(gig.id)"
                    >
                      <div class="gig-bubble-content">
                        <div class="gig-bubble-main">
                          <Transition name="gig-overlay-replace" mode="out-in">
                            <div v-if="isGigDescriptionVisible(gig) && !usesDetachedGigPopup" :key="`description-${gig.id}`" class="gig-description-panel" @click.stop>
	                              <h3 class="gig-description-title">{{ localizedText(gigTitle(gig)) }}</h3>
                              <p class="gig-description-text">{{ getGigDescriptionText(gig) }}</p>
                            </div>
                            <div v-else :key="`summary-${gig.id}`" class="gig-bubble-summary">
                              <span class="gig-time">
                                <template v-if="showChanges && hasGigTimeChange(gig)">
                                  <span class="changed-old">{{ oldGigStartTime(gig) }}</span>
                                </template>
                                {{ gig.start_time }}
                              </span>
                              <span class="gig-title">
	                                <template v-if="showChanges && hasGigFieldChange(gig, 'title')">
                                  <span class="changed-old">{{ oldGigTitle(gig) }}</span>
                                </template>
	                                {{ localizedText(gigTitle(gig)) }}
                                <span v-if="showChanges && isGigNew(gig)" class="change-badge badge-success">{{ t.newGig }}</span>
                                <span v-if="gig.__canceled" class="change-badge">{{ t.canceled }}</span>
                              </span>
                              <span v-if="localizedText(gig.genre) || (showChanges && hasGigFieldChange(gig, 'genre'))" class="gig-overlay-genre">
                                <template v-if="showChanges && hasGigFieldChange(gig, 'genre')">
                                  <span class="changed-old">{{ oldGigGenre(gig) }}</span>
                                </template>
                                {{ localizedText(gig.genre) }}
                              </span>
                            </div>
                          </Transition>
                        </div>
                        <div class="gig-bubble-details" :class="{ open: expandedGig === gig.id && !usesDetachedGigPopup }">
                          <TransformedImage
                            v-if="resolveProgramGigImageUrl(gig)"
                            :src="resolveProgramGigImageUrl(gig)"
                            :responsive-variants="resolveProgramGigResponsiveVariants(gig)"
	                            :alt="localizedText(gigTitle(gig))"
                            class="gig-image"
                            ratio="1:1"
                            direction="landscape"
                            :zoom="resolveProgramGigImageZoom(gig)"
                            :focal-x="resolveProgramGigImageFocalX(gig)"
                            :focal-y="resolveProgramGigImageFocalY(gig)"
                            :rotation="resolveProgramGigImageRotation(gig)"
                            fit="cover"
                            loading="lazy"
                            decoding="async"
                          />
                          <div class="gig-detail-meta-row">
                            <span v-if="localizedText(gig.genre) || (showChanges && hasGigFieldChange(gig, 'genre'))" class="gig-meta-chip gig-genre-tag">
                              <template v-if="showChanges && hasGigFieldChange(gig, 'genre')">
                                <span class="changed-old">{{ oldGigGenre(gig) }}</span>
                              </template>
                              {{ localizedText(gig.genre) }}
                            </span>
                            <span class="gig-meta-chip gig-day-time-tag">
                              <template v-if="showChanges && hasGigTimeChange(gig)">
                                <span class="changed-old">{{ formatGigOverlayDateTime(gig, true) }}</span>
                              </template>
                              {{ formatGigOverlayDateTime(gig) }}
                            </span>
                            <span class="gig-meta-chip gig-stage-tag">
                              <template v-if="showChanges && hasGigStageChange(gig)">
                                <span class="changed-old">{{ oldGigStageName(gig) }}</span>
                              </template>
                              {{ getStageName(getGigStage(gig)) }}
                              <span v-if="showChanges && hasGigStageChange(gig)" class="change-badge badge-warning">{{ t.stageChanged }}</span>
                            </span>
                          </div>
                        </div>
                      </div>
                      <div class="gig-details-actions">
                        <button
                          class="gig-popup-chevron gig-popup-chevron--previous"
                          type="button"
                          :aria-label="t.previousGig"
                          :title="t.previousGig"
                          :disabled="!canNavigateExpandedGig(gig, -1)"
                          @click.stop="navigateExpandedGig(-1)"
                        >
                          <font-awesome-icon :icon="faChevronLeft" />
                        </button>
                        <div class="gig-popup-primary-actions" :class="{ 'gig-popup-primary-actions--single': !showGigDescriptionButton }">
                          <button
                            class="gig-popup-action gig-more-btn"
                            type="button"
                            :aria-label="getGigPopupMoreButtonAriaLabel(gig)"
                            :title="getGigPopupMoreButtonTitle(gig)"
                            :disabled="!isGigPopupMoreButtonEnabled(gig)"
                            @click.stop="openGeneratedItemPage(gig)"
                          >
                            {{ getGigPopupMoreButtonLabel(gig) }}
                          </button>
                          <button
                            v-if="showGigDescriptionButton"
                            class="gig-popup-action gig-description-btn"
                            type="button"
                            :class="{ active: isGigDescriptionVisible(gig) }"
                            :disabled="!hasGigDescription(gig)"
                            @click.stop="toggleGigDescription(gig)"
                          >
                            {{ isGigDescriptionVisible(gig) ? t.info : t.description }}
                          </button>
                        </div>
                        <button
                          class="gig-popup-chevron gig-popup-chevron--next"
                          type="button"
                          :aria-label="t.nextGig"
                          :title="t.nextGig"
                          :disabled="!canNavigateExpandedGig(gig, 1)"
                          @click.stop="navigateExpandedGig(1)"
                        >
                          <font-awesome-icon :icon="faChevronRight" />
                        </button>
                      </div>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- List View (Timeline) -->
      <div class="list-view" v-show="!isChangesView && !isNowView && effectiveViewMode === 'timeline'">
        <div class="list-container">
          <div
            v-for="dayGroup in listGigDayGroups"
            :key="dayGroup.key"
            class="list-day-group"
            :class="{ 'stage-view-day-muted': isStageViewDayMuted(dayGroup.day) }"
          >
            <h3 v-if="dayGroup.date" class="list-day-title">{{ dayGroup.weekday }}, {{ dayGroup.date }}</h3>
            <h3 v-else class="list-day-title">{{ dayGroup.weekday }}</h3>
            <div class="list-day-items">
              <div
                v-for="gig in dayGroup.gigs"
                :key="gig.id"
                class="list-card"
                :class="{ 'list-card-canceled': gig.__canceled }"
                :style="{
                  '--card-color': getStageColor(getGigStage(gig)),
                  '--list-card-bg-image': resolveListCardBackgroundImage(gig),
                }"
                role="button"
                tabindex="0"
                @click="openGigPopup(gig.id)"
                @keydown.enter.prevent="openGigPopup(gig.id)"
                @keydown.space.prevent="openGigPopup(gig.id)"
              >
                <div class="list-card-header">
                  <div class="list-card-time">
                    <template v-if="showChanges && hasGigTimeChange(gig)">
                      <span class="list-card-time-value changed-old">{{ oldGigStartTime(gig) }}</span>
                    </template>
                    <span class="list-card-time-value">{{ gig.start_time }}</span>
                    <span class="list-card-time-secondary">
                      <template v-if="showChanges && hasGigTimeChange(gig)">
                        <span class="changed-old">{{ oldGigEndTime(gig) }}</span>
                      </template>
                      {{ gig.end_time }}
                    </span>
                  </div>
                  <div class="list-card-info">
                    <div class="list-card-title">
	                      <template v-if="showChanges && hasGigFieldChange(gig, 'title')">
                        <span class="changed-old">{{ oldGigTitle(gig) }}</span>
                      </template>
	                      {{ localizedText(gigTitle(gig)) }}
                      <span v-if="showChanges && isGigNew(gig)" class="change-badge badge-success">{{ t.newGig }}</span>
                      <span v-if="gig.__canceled" class="change-badge">{{ t.canceled }}</span>
                    </div>
                    <div class="list-card-meta">
                      <div class="list-card-stage-genre">
                        <span class="list-card-stage">
                          <template v-if="showChanges && hasGigFieldChange(gig, 'stage')">
                            <span class="changed-old">{{ oldGigStageName(gig) }}</span>
                          </template>
                          {{ getStageName(getGigStage(gig)) }}
                          <span v-if="showChanges && hasGigFieldChange(gig, 'stage')" class="change-badge badge-warning">{{ t.stageChanged }}</span>
                        </span>
                        <span v-if="localizedText(gig.genre) || (showChanges && hasGigFieldChange(gig, 'genre'))" class="list-card-genre">
                          <template v-if="showChanges && hasGigFieldChange(gig, 'genre')">
                            <span class="changed-old">{{ oldGigGenre(gig) }}</span>
                          </template>
                          {{ localizedText(gig.genre) }}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div class="list-card-chevron">
                    <font-awesome-icon :icon="faChevronRight" />
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div v-if="filteredGigsSorted.length === 0" class="list-empty">
            <span class="list-empty-icon"><font-awesome-icon :icon="faMusic" /></span>
            <span class="list-empty-text">{{ t.noGigs }}</span>
          </div>
        </div>
      </div>

      <div v-if="showProgramControlBar" class="program-controls-bar">
        <div v-if="allowGroupToggle && !isNowView" class="group-toggle">
          <button
            type="button"
            class="group-btn"
            :class="{ active: groupBy === 'day' }"
            @click="setGroupBy('day')"
          >
            {{ t.byDay }}
          </button>
          <button
            type="button"
            class="group-btn"
            :class="{ active: groupBy === 'stage' }"
            @click="setGroupBy('stage')"
          >
            {{ t.byStage }}
          </button>
        </div>

        <div v-if="showViewToggle" class="view-toggle">
          <button
            v-if="showGanttViewButton"
            type="button"
            class="view-btn"
            :class="{ active: effectiveViewMode === 'gantt' }"
            @click="setViewMode('gantt')"
            title="Grid View"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
              <rect x="3" y="3" width="7" height="7" rx="2"/>
              <rect x="14" y="3" width="7" height="7" rx="2"/>
              <rect x="3" y="14" width="7" height="7" rx="2"/>
              <rect x="14" y="14" width="7" height="7" rx="2"/>
            </svg>
          </button>
          <button
            type="button"
            class="view-btn"
            :class="{ active: effectiveViewMode === 'timeline' }"
            @click="setViewMode('timeline')"
            title="List View"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
              <line x1="8" y1="6" x2="21" y2="6"/>
              <line x1="8" y1="12" x2="21" y2="12"/>
              <line x1="8" y1="18" x2="21" y2="18"/>
              <circle cx="4" cy="6" r="1.5" fill="currentColor"/>
              <circle cx="4" cy="12" r="1.5" fill="currentColor"/>
              <circle cx="4" cy="18" r="1.5" fill="currentColor"/>
            </svg>
          </button>
          <button
            type="button"
            class="view-btn"
            :class="{ active: effectiveViewMode === 'now' }"
            @click="setViewMode('now')"
            title="Now Playing"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="9"/>
              <polyline points="12 7 12 12 15 15"/>
            </svg>
          </button>
        </div>
      </div>

      <div
        v-if="detachedPopupGig"
        :key="`detached-popup-${detachedPopupGig.id}`"
        class="gig-bubble gig-bubble--detached-popup"
        :class="{ expanded: true, closing: closingGig === detachedPopupGig.id, 'gig-canceled': detachedPopupGig.__canceled, 'gig-description-visible': isGigDescriptionVisible(detachedPopupGig) }"
        :style="{ '--lane-color': getStageColor(getGigStage(detachedPopupGig)) }"
        @click="toggleGig(detachedPopupGig.id)"
      >
        <div class="gig-bubble-content">
          <div class="gig-bubble-main">
            <Transition name="gig-overlay-replace" mode="out-in">
              <div v-if="isGigDescriptionVisible(detachedPopupGig)" :key="`description-${detachedPopupGig.id}`" class="gig-description-panel" @click.stop>
	                <h3 class="gig-description-title">{{ localizedText(gigTitle(detachedPopupGig)) }}</h3>
                <p class="gig-description-text">{{ getGigDescriptionText(detachedPopupGig) }}</p>
              </div>
              <div v-else :key="`summary-${detachedPopupGig.id}`" class="gig-bubble-summary">
                <span class="gig-time">
                  <template v-if="showChanges && hasGigTimeChange(detachedPopupGig)">
                    <span class="changed-old">{{ oldGigStartTime(detachedPopupGig) }}</span>
                  </template>
                  {{ detachedPopupGig.start_time }}
                </span>
                <span class="gig-title">
	                  <template v-if="showChanges && hasGigFieldChange(detachedPopupGig, 'title')">
                    <span class="changed-old">{{ oldGigTitle(detachedPopupGig) }}</span>
                </template>
	                {{ localizedText(gigTitle(detachedPopupGig)) }}
                <span v-if="showChanges && isGigNew(detachedPopupGig)" class="change-badge badge-success">{{ t.newGig }}</span>
                <span v-if="detachedPopupGig.__canceled" class="change-badge">{{ t.canceled }}</span>
              </span>
                <span v-if="localizedText(detachedPopupGig.genre) || (showChanges && hasGigFieldChange(detachedPopupGig, 'genre'))" class="gig-overlay-genre">
                  <template v-if="showChanges && hasGigFieldChange(detachedPopupGig, 'genre')">
                    <span class="changed-old">{{ oldGigGenre(detachedPopupGig) }}</span>
                  </template>
                  {{ localizedText(detachedPopupGig.genre) }}
                </span>
              </div>
            </Transition>
          </div>
          <div class="gig-bubble-details open">
            <TransformedImage
              v-if="resolveProgramGigImageUrl(detachedPopupGig)"
              :src="resolveProgramGigImageUrl(detachedPopupGig)"
              :responsive-variants="resolveProgramGigResponsiveVariants(detachedPopupGig)"
	              :alt="localizedText(gigTitle(detachedPopupGig))"
              class="gig-image"
              ratio="1:1"
              direction="landscape"
              :zoom="resolveProgramGigImageZoom(detachedPopupGig)"
              :focal-x="resolveProgramGigImageFocalX(detachedPopupGig)"
              :focal-y="resolveProgramGigImageFocalY(detachedPopupGig)"
              :rotation="resolveProgramGigImageRotation(detachedPopupGig)"
              fit="cover"
              loading="lazy"
              decoding="async"
            />
            <div class="gig-detail-meta-row">
              <span v-if="localizedText(detachedPopupGig.genre) || (showChanges && hasGigFieldChange(detachedPopupGig, 'genre'))" class="gig-meta-chip gig-genre-tag">
                <template v-if="showChanges && hasGigFieldChange(detachedPopupGig, 'genre')">
                  <span class="changed-old">{{ oldGigGenre(detachedPopupGig) }}</span>
                </template>
                {{ localizedText(detachedPopupGig.genre) }}
              </span>
              <span class="gig-meta-chip gig-day-time-tag">
                <template v-if="showChanges && hasGigTimeChange(detachedPopupGig)">
                  <span class="changed-old">{{ formatGigOverlayDateTime(detachedPopupGig, true) }}</span>
                </template>
                {{ formatGigOverlayDateTime(detachedPopupGig) }}
              </span>
              <span class="gig-meta-chip gig-stage-tag">
                <template v-if="showChanges && hasGigStageChange(detachedPopupGig)">
                  <span class="changed-old">{{ oldGigStageName(detachedPopupGig) }}</span>
                </template>
                {{ getStageName(getGigStage(detachedPopupGig)) }}
                <span v-if="showChanges && hasGigStageChange(detachedPopupGig)" class="change-badge badge-warning">{{ t.stageChanged }}</span>
              </span>
            </div>
          </div>
        </div>
        <div class="gig-details-actions">
          <button
            class="gig-popup-chevron gig-popup-chevron--previous"
            type="button"
            :aria-label="t.previousGig"
            :title="t.previousGig"
            :disabled="!canNavigateExpandedGig(detachedPopupGig, -1)"
            @click.stop="navigateExpandedGig(-1)"
          >
            <font-awesome-icon :icon="faChevronLeft" />
          </button>
          <div class="gig-popup-primary-actions" :class="{ 'gig-popup-primary-actions--single': !showGigDescriptionButton }">
            <button
              class="gig-popup-action gig-more-btn"
              type="button"
              :aria-label="getGigPopupMoreButtonAriaLabel(detachedPopupGig)"
              :title="getGigPopupMoreButtonTitle(detachedPopupGig)"
              :disabled="!isGigPopupMoreButtonEnabled(detachedPopupGig)"
              @click.stop="openGeneratedItemPage(detachedPopupGig)"
            >
              {{ getGigPopupMoreButtonLabel(detachedPopupGig) }}
            </button>
            <button
              v-if="showGigDescriptionButton"
              class="gig-popup-action gig-description-btn"
              type="button"
              :class="{ active: isGigDescriptionVisible(detachedPopupGig) }"
              :disabled="!hasGigDescription(detachedPopupGig)"
              @click.stop="toggleGigDescription(detachedPopupGig)"
            >
              {{ isGigDescriptionVisible(detachedPopupGig) ? t.info : t.description }}
            </button>
          </div>
          <button
            class="gig-popup-chevron gig-popup-chevron--next"
            type="button"
            :aria-label="t.nextGig"
            :title="t.nextGig"
            :disabled="!canNavigateExpandedGig(detachedPopupGig, 1)"
            @click.stop="navigateExpandedGig(1)"
          >
            <font-awesome-icon :icon="faChevronRight" />
          </button>
        </div>
      </div>

      <!-- Backdrop for expanded gig -->
      <Transition name="gig-backdrop-fade">
        <div v-if="showGigPopupBackdrop" class="gig-backdrop" @click="closeExpandedGig"></div>
      </Transition>

      <!-- Stage Detail Modal -->
      <div v-if="stageDetailOpen" class="stage-modal-overlay" @click="stageDetailOpen = null">
        <div class="stage-modal" :style="{ '--stage-color': getStageVisualColor(stageDetailOpen) }" @click.stop>
          <button class="stage-modal-close" @click="stageDetailOpen = null">×</button>
          <div class="stage-modal-header">
            <h2 class="stage-modal-name">{{ localizedText(stageDetailOpen.name) }}</h2>
            <p v-if="localizedText(stageDetailOpen.description)" class="stage-modal-description">
              {{ localizedText(stageDetailOpen.description) }}
            </p>
          </div>
          <div class="stage-modal-gigs">
            <h3 class="stage-modal-gigs-title">{{ t.gigsOnStage }}</h3>
            <div class="stage-modal-gig-list">
              <div
                v-for="gig in getGigsForStage(stageDetailOpen.id)"
                :key="gig.id"
                class="stage-modal-gig"
                :class="{ 'stage-modal-gig-canceled': gig.__canceled }"
              >
                <span class="stage-modal-gig-time">
                  <template v-if="showChanges && hasGigTimeChange(gig)">
                    <span class="changed-old">{{ oldGigTimeRange(gig) }}</span>
                  </template>
                  {{ gig.start_time }} - {{ gig.end_time }}
                </span>
                <span class="stage-modal-gig-title">
	                  <template v-if="showChanges && hasGigFieldChange(gig, 'title')">
                    <span class="changed-old">{{ oldGigTitle(gig) }}</span>
                  </template>
	                  {{ localizedText(gigTitle(gig)) }}
                  <span v-if="showChanges && isGigNew(gig)" class="change-badge badge-success">{{ t.newGig }}</span>
                  <span v-if="gig.__canceled" class="change-badge">{{ t.canceled }}</span>
                </span>
                <span v-if="localizedText(gig.genre) || (showChanges && hasGigFieldChange(gig, 'genre'))" class="stage-modal-gig-genre">
                  <template v-if="showChanges && hasGigFieldChange(gig, 'genre')">
                    <span class="changed-old">{{ oldGigGenre(gig) }}</span>
                  </template>
                  {{ localizedText(gig.genre) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>

      <!-- Admin Panel -->
    <template #admin-design-colors>
      <div class="program-design-panel">
        <div class="field-group program-stage-colors-group program-color-group">
          <label class="field-label">Stage Colors</label>
          <div v-if="stages.length === 0" class="field-hint">No stages available.</div>
          <div v-for="stage in stages" :key="'design-stage-color-' + stage.id" class="stage-color-row">
            <span class="stage-color-name">{{ localizedText(stage.name) }}</span>
            <div class="color-link-control">
              <VueColorPicker
                :model-value="hexOrDefault(getStagePickerColor(stage), '#4f46e5')"
                fallback-color="#4f46e5"
                :preview-style="swatchStyle(getStageVisualColor(stage), { rawColor: getStageCustomColor(stage), linkKey: getStageColorLink(stage), baseRefColor: state.design.sectionBackgroundColor || '#ffffff', baseRefKey: 'sectionBackgroundColor', adminConfig: state.adminDesignConfig })"
                :size="28"
                @update:model-value="setStageColor(stage.id, $event)"
              />
              <ColorLinkPicker :model-value="getStageColorLink(stage)" :options="designColorOptions" :button-size="24" @link="applyStageColorLink(stage.id, $event)" />
              <select
                class="variation-select"
                :value="getStageColorVariation(stage)"
                @change="setStageColorVariation(stage.id, $event.target.value)"
              >
                <option v-for="variation in colorVariationOptions" :key="`program-stage-${stage.id}-${variation}`" :value="variation">
                  {{ variation }}%
                </option>
              </select>
              <button
                v-if="hasStageColorOverride(stage)"
                class="clear-btn"
                type="button"
                title="Reset"
                @click="clearStageColor(stage.id)"
              >&times;</button>
            </div>
          </div>
        </div>

        <div class="field-group program-color-group">
          <label class="field-label">Date Selection Color</label>
          <div class="color-link-control">
            <VueColorPicker
              :model-value="hexOrDefault(dateSelectionColor, '#4f46e5')"
              fallback-color="#4f46e5"
              :preview-style="swatchStyle(resolvedDateSelectionColor, { rawColor: dateSelectionColor, linkKey: dateSelectionColorLink, treatEmptyAsHighContrast: true, baseRefColor: state.design.sectionBackgroundColor || '#ffffff', baseRefKey: 'sectionBackgroundColor', adminConfig: state.adminDesignConfig })"
              :size="28"
              @update:model-value="setDateSelectionColor($event)"
            />
            <ColorLinkPicker :model-value="dateSelectionColorLink" :options="designColorOptions" :button-size="24" @link="applyDesignColorLink('date', $event)" />
            <select
              class="variation-select"
              :value="dateSelectionColorVariation"
              @change="setDateSelectionColorVariation($event.target.value)"
            >
              <option v-for="variation in colorVariationOptions" :key="`program-date-${variation}`" :value="variation">
                {{ variation }}%
              </option>
            </select>
            <button v-if="dateSelectionColor || dateSelectionColorLink" class="clear-btn" type="button" title="Clear" @click="clearDesignColor('date')">&times;</button>
          </div>
        </div>
      </div>
    </template>

    <template #admin-design-params>
      <div class="program-design-panel program-design-panel--params">
        <div class="field-group program-view-config-group">
          <label class="field-label">View</label>
          <div class="program-view-config-grid">
            <div class="field-group">
              <label class="field-label">Default View Mode</label>
              <select class="field" :value="defaultViewMode" @change="setDefaultViewMode($event.target.value)">
                <option value="gantt">Grid (Gantt)</option>
                <option value="timeline">List (Timeline)</option>
                <option value="changes">Changes</option>
                <option value="now">Now Playing</option>
              </select>
            </div>

            <div v-if="showViewConfigScopeControls" class="field-group">
              <label class="field-label">Default Group By</label>
              <select class="field" :value="defaultGrouping" @change="setDefaultGrouping($event.target.value)">
                <option value="day">Day</option>
                <option value="stage">Stage</option>
              </select>
            </div>
          </div>
        </div>

        <div v-if="showViewConfigScopeControls || showFixedGigConfig" class="field-group program-view-config-group">
          <label class="field-label">Scope</label>
          <div class="program-view-config-grid">
            <template v-if="showViewConfigScopeControls && defaultGrouping === 'day'">
              <div class="field-group">
                <label class="field-label">Day</label>
                <select class="field" :value="viewConfigDayValue" @change="setFixedDay($event.target.value)">
                  <option v-if="fixedDayOptions.length === 0" value="">No days available</option>
                  <option v-else value="">All days</option>
                  <option v-for="day in fixedDayOptions" :key="`view-config-day-${day}`" :value="day">
                    {{ formatDayName(day) }} - {{ formatDayDate(day) }}
                  </option>
                </select>
              </div>
              <div class="field-group">
                <label class="field-label">Stage</label>
                <select class="field" :value="fixedStageId" @change="setFixedStageId($event.target.value)">
                  <option value="">All stages</option>
                  <option v-for="stageOption in stageSelectionOptions" :key="`view-config-stage-${stageOption.value}`" :value="stageOption.value">
                    {{ stageOption.label }}
                  </option>
                </select>
              </div>
            </template>

            <template v-else-if="showViewConfigScopeControls">
              <div class="field-group">
                <label class="field-label">Stage</label>
                <select class="field" :value="viewConfigStageValue" @change="setFixedStageId($event.target.value)">
                  <option v-if="stageSelectionOptions.length === 0" value="">No stages available</option>
                  <option v-else value="">All stages</option>
                  <option v-for="stageOption in stageSelectionOptions" :key="`view-config-stage-${stageOption.value}`" :value="stageOption.value">
                    {{ stageOption.label }}
                  </option>
                </select>
              </div>
              <div class="field-group">
                <label class="field-label">Day</label>
                <select class="field" :value="fixedDay" @change="setFixedDay($event.target.value)">
                  <option value="">All days</option>
                  <option v-for="day in fixedDayOptions" :key="`view-config-day-${day}`" :value="day">
                    {{ formatDayName(day) }} - {{ formatDayDate(day) }}
                  </option>
                </select>
              </div>
            </template>

            <div v-if="showFixedGigConfig" class="field-group">
              <label class="field-label">Fixed Gig</label>
              <select class="field" :value="fixedGigId" @change="setFixedGigId($event.target.value)">
                <option value="">No fixed gig</option>
                <option v-for="gigOption in fixedGigOptions" :key="`view-config-gig-${gigOption.value}`" :value="gigOption.value">
                  {{ gigOption.label }}
                </option>
              </select>
              <span v-if="fixedGigId && fixedGigOptions.length === 0" class="field-hint">No gigs match the selected day/stage scope.</span>
            </div>
          </div>
        </div>

        <div v-if="showViewConfigScopeControls" class="field-group program-view-config-group program-public-controls-group">
          <label class="field-label">Public Controls</label>
          <div class="program-public-toggle-grid">
            <label class="constant-check">
              <input type="checkbox" :checked="allowDaySelection" @change="setAllowDaySelection($event.target.checked)" />
              <span>Day Filter</span>
            </label>
            <label class="constant-check">
              <input type="checkbox" :checked="allowStageFilter" @change="setAllowStageFilter($event.target.checked)" />
              <span>Stage Filter</span>
            </label>
            <label class="constant-check">
              <input type="checkbox" :checked="allowGroupToggle" @change="setAllowGroupToggle($event.target.checked)" />
              <span>Grouping Toggle</span>
            </label>
            <label class="constant-check">
              <input type="checkbox" :checked="showViewToggle" @change="setShowViewToggle($event.target.checked)" />
              <span>View Toggle</span>
            </label>
            <label class="constant-check">
              <input type="checkbox" :checked="showGigDescriptionButton" @change="setShowGigDescriptionButton($event.target.checked)" />
              <span>Show Gig Description</span>
            </label>
            <label class="constant-check">
              <input type="checkbox" :checked="showListItemBackgroundImages" @change="setShowListItemBackgroundImages($event.target.checked)" />
              <span>List Item Background Images</span>
            </label>
          </div>
        </div>

        <div v-if="defaultViewMode === 'gantt'" class="field-group program-view-config-group">
          <label class="field-label">Gantt Layout</label>
          <div class="program-view-config-grid">
            <div v-if="defaultViewMode === 'gantt'" class="field-group">
              <label class="field-label">Stage Height</label>
              <input type="range" min="100" max="220" step="5" :value="stageRowHeight" @input="setStageRowHeight($event.target.value)" />
              <span class="field-hint">{{ stageRowHeight }}px</span>
            </div>

            <div v-if="defaultViewMode === 'gantt'" class="field-group">
              <label class="field-label">Max Visible Hours</label>
              <input type="range" min="2" max="24" step="1" :value="maxVisibleHours" @input="setMaxVisibleHours($event.target.value)" />
              <span class="field-hint">{{ maxVisibleHours }}h before horizontal scrolling</span>
            </div>
          </div>
        </div>
      </div>
    </template>
    <template #admin-content>
      <div class="admin-panel">
        <MediaLibrary
          :is-open="showStageMediaPicker"
          :current-url="stageMediaPickerCurrentUrl"
          source-context="section.program.stage.image"
          :allow-clear-selection="true"
          @close="closeStageMediaPicker"
          @select="applyStageMediaSelection"
        />

        <div
          v-if="programDuplicateIdWarning.message"
          class="program-validation-banner program-validation-banner--error"
        >
          {{ programDuplicateIdWarning.message }}
        </div>

        <details class="admin-section program-stages-section">
          <summary class="admin-section-title">Stages</summary>
          <div class="admin-section-content">
            <div class="program-stage-options-panel">
              <div class="program-stage-options-header">
                <strong>Gig Metadata Stages</strong>
                <span v-if="selectedStageMetadataOptionEntries.length">
                  {{ selectedStageMetadataOptionEntries.length }} option{{ selectedStageMetadataOptionEntries.length === 1 ? "" : "s" }}
                </span>
              </div>
              <div v-if="programStageMetadataOptionSources.length === 0" class="empty-state compact">
                Run the gig import with option metadata to select stages from imported gig options.
              </div>
              <div v-else class="program-stage-options-controls">
                <div class="field-group">
                  <label class="field-label">Metadata Source</label>
                  <select v-model="selectedStageOptionsSourcePath" class="field">
                    <option
                      v-for="source in programStageMetadataOptionSources"
                      :key="`stage-option-source-${source.path}`"
                      :value="source.path"
                    >
                      {{ source.label }}
                    </option>
                  </select>
                </div>
                <div class="field-group">
                  <label class="field-label">Stage Option</label>
                  <select v-model="selectedStageOptionValue" class="field">
                    <option value="">Select an option</option>
                    <option
                      v-for="option in selectedStageMetadataOptionEntries"
                      :key="`stage-option-entry-${option.value}`"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                </div>
                <div class="program-stage-options-actions">
                  <button
                    class="btn-secondary"
                    type="button"
                    :disabled="!selectedStageOptionValue"
                    @click="addSelectedStageFromMetadataOptions"
                  >
                    Add Selected
                  </button>
                  <button
                    class="btn-secondary"
                    type="button"
                    :disabled="selectedStageMetadataOptionEntries.length === 0"
                    @click="addAllMissingStagesFromMetadataOptions"
                  >
                    Add All Missing
                  </button>
                </div>
              </div>
              <p v-if="programStageMetadataOptionsHint" class="field-hint">
                {{ programStageMetadataOptionsHint }}
              </p>
            </div>

            <SectionListEditor
              :items="stageDraft"
              :selected-index="selectedStageDraftIndex"
              add-label="Add Stage"
              save-label="Save Stage"
              remove-label="Remove Stage"
              clear-label="Clear All"
              :show-clear="false"
              :show-dismiss="false"
              @select="setSelectedStageDraftIndex"
              @add="addStageDraft"
              @save="saveStageDraft"
              @remove="removeStageDraft"
              @clear="clearAllStageItems"
            >
              <template #item="{ item, index }">
                <div class="item-thumb item-thumb--text">
                  <span class="thumb-num">{{ index + 1 }}</span>
                  <span class="thumb-label">{{ localizedText(item.name) || item.id || `#${index + 1}` }}</span>
                </div>
              </template>
              <template #editor="{ item, index }">
                  <div class="field-group">
                    <label class="field-label">
                      Stage ID
                    </label>
                    <input v-model="item.id" type="text" class="field" placeholder="stage-main" />
                    <div v-if="isDuplicateStageId(item.id)" class="field-hint field-hint--error">
                      Duplicate stage ID. Use a unique ID before saving.
                    </div>
                  </div>
                  <div class="bilingual-row">
                    <div class="field-group">
                      <label class="field-label">
                        Title (DE)
                      </label>
                      <input v-model="item.name.de" type="text" class="field" placeholder="Bühne" />
                    </div>
                    <div class="field-group">
                      <label class="field-label">
                        Title (EN)
                      </label>
                      <input v-model="item.name.en" type="text" class="field" placeholder="Stage" />
                    </div>
                  </div>
                  <div class="bilingual-row">
                    <div class="field-group">
                      <label class="field-label">
                        Description (DE)
                      </label>
                      <textarea v-model="item.description.de" class="field field-textarea" rows="2" />
                    </div>
                    <div class="field-group">
                      <label class="field-label">
                        Description (EN)
                      </label>
                      <textarea v-model="item.description.en" class="field field-textarea" rows="2" />
                    </div>
                  </div>
                  <div class="field-group">
                    <label class="field-label">
                      Image
                    </label>
                    <div class="stage-image-picker">
                      <button class="btn-secondary" type="button" @click="openStageMediaPicker(index)">
                        {{ item.image_url ? "Change Image" : "Select From Media Library" }}
                      </button>
                      <button
                        v-if="item.image_url"
                        class="btn-secondary"
                        type="button"
                        @click="clearStageImage(index)"
                      >
                        Clear Image
                      </button>
                      <span class="stage-image-picker__status" :title="item.image_url || ''">
                        {{ item.image_url ? "Image selected" : "No image selected" }}
                      </span>
                    </div>
                  </div>
                  <div class="field-group">
                    <label class="field-label">
                      Color
                    </label>
                    <input v-model="item.color" type="text" class="field" placeholder="#3b82f6" />
                  </div>
                  <div
                    v-if="programItemPageInfoMessage('stage', item)"
                    :class="[
                      'item-page-info',
                      programItemPageInfoTone('stage', item) === 'warning'
                        ? 'item-page-info--warning'
                        : 'item-page-info--info',
                    ]"
                  >
                    {{ programItemPageInfoMessage('stage', item) }}
                  </div>
              </template>
              <template #footer-actions="{ item }">
                <div class="item-page-actions">
                  <button
                    class="btn-secondary"
                    type="button"
                    :disabled="!resolveGeneratedItemUrl(item)"
                    @click.stop="openGeneratedItemPage(item)"
                  >
                    Open Item Page
                  </button>
                  <button
                    v-if="showProgramItemRegenerateButton('stage', item)"
                    class="btn-secondary"
                    type="button"
                    :disabled="isProgramItemTemplateRegenerationBusy('stage', item) || isProgramItemPageGenerationPending('stage', item)"
                    @click.stop="regenerateProgramItemPage('stage', item)"
                  >
                    {{ isProgramItemTemplateRegenerationBusy('stage', item) ? "Regenerating..." : "Regenerate Item Page" }}
                  </button>
                  <span v-if="isProgramItemPageGenerationPending('stage', item)" class="field-hint">
                    Item page is being generated. The open button will activate automatically.
                  </span>
                  <span v-else-if="programItemPageGenerationError('stage', item)" class="field-hint field-hint--error">
                    {{ programItemPageGenerationError('stage', item) }}
                  </span>
                </div>
              </template>
            </SectionListEditor>
          </div>
        </details>

        <details class="admin-section program-gigs-section">
          <summary class="admin-section-title">Gigs</summary>
          <div class="admin-section-content">
            <SectionIntegrationImporter
              :section-key="effectiveKey"
              :section-data="sectionForIntegrationImport"
              :section-type="section?.sectionType"
              panel-title="Import Gigs from Integration"
              forced-mode="list"
              mapping-storage-key="programGigsIntegrationMapping"
              :fixed-collection-paths="['gigs']"
              :apply-content-patch="applyProgramGigsImportPatch"
              :persist-mapping-patch="persistProgramGigsIntegrationMappingPatch"
              :show-clear-button="false"
            />

            <div class="event-filter-row">
              <div class="field-group">
                <label class="field-label">Filter By Day</label>
                <select v-model="gigEditorDayFilter" class="field">
                  <option value="">All days</option>
                  <option v-for="day in gigEditorDayOptions" :key="`gig-filter-day-${day}`" :value="day">
                    {{ day }}
                  </option>
                </select>
              </div>
              <div class="field-group">
                <label class="field-label">Filter By Stage</label>
                <select v-model="gigEditorStageFilter" class="field">
                  <option value="">All stages</option>
                  <option v-for="stageOption in stageSelectionOptions" :key="`gig-filter-stage-${stageOption.value}`" :value="stageOption.value">
                    {{ stageOption.label }}
                  </option>
                </select>
              </div>
              <div class="field-group">
                <label class="field-label">Filter By Gig Type</label>
                <select v-model="gigEditorTypeFilter" class="field">
                  <option value="">All types</option>
                  <option v-for="option in gigEditorTypeOptions" :key="`gig-filter-type-${option.value}`" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
              </div>
              <div class="field-group">
                <label class="field-label">Filter By Item Page</label>
                <select v-model="gigEditorItemPageFilter" class="field">
                  <option value="">All statuses</option>
                  <option value="not_created">Not created</option>
                  <option value="hidden">Hidden</option>
                  <option value="published">Published</option>
                </select>
              </div>
            </div>

            <SectionListEditor
              :items="filteredGigDraft"
              :selected-index="selectedFilteredGigDraftIndex"
              add-label="Add Gig"
              save-label="Save Gig"
              remove-label="Remove Gig"
              clear-label="Clear All"
              :show-clear="isTemplateBuilderPage"
              :show-remove="false"
              :show-dismiss="false"
              :add-disabled="true"
              item-fields-class="item-fields--source-locked"
              @select="selectGigDraftFromFiltered"
              @save="saveGigDraft"
              @reorder="reorderGigDraftFromFiltered"
              @remove="removeGigDraftFromFiltered"
              @clear="clearAllGigItems"
            >
              <template #item="{ item, index }">
                <div class="item-thumb item-thumb--media">
                  <div
                    class="thumb-img-wrap"
                    title="Image is managed in integration review"
                  >
                    <TransformedImage
                      v-if="item.image_url"
                      :src="item.image_url"
                      :responsive-variants="resolveProgramItemResponsiveVariants(item)"
                      alt=""
                      class="thumb-img"
                      ratio="1:1"
                      direction="landscape"
                      :zoom="normalizeGigImageZoom(item.image_zoom)"
                      :focal-x="normalizeGigImageFocal(item.image_focal_x)"
                      :focal-y="normalizeGigImageFocal(item.image_focal_y)"
                      :rotation="normalizeGigImageRotation(item.image_rotation)"
                      fit="cover"
                      loading="lazy"
                      decoding="async"
                    />
                    <div v-else class="thumb-empty">{{ index + 1 }}</div>
                  </div>
	                  <span class="thumb-label">{{ localizedText(gigTitle(item)) || item.id || `#${index + 1}` }}</span>
                </div>
              </template>
              <template #editor="{ item, index }">
                  <div class="field-group program-gig-image-transform-field">
                    <label class="field-label">
                      Image
                    </label>
                    <ImageTransformEditor
                      :image-url="item.image_url"
                      :zoom="item.image_zoom"
                      :focal-x="item.image_focal_x"
                      :focal-y="item.image_focal_y"
                      :rotation="item.image_rotation"
                      ratio="1:1"
                      direction="landscape"
                      view-context="section_item"
                      :image-url-disabled="true"
                      :allow-manual-url-edit="false"
                      :show-url-field="false"
                      :show-image-actions="false"
                      :allow-clear-image="false"
                      @update:zoom="(value) => setGigImageTransform(item, { image_zoom: value })"
                      @update:focal-x="(value) => setGigImageTransform(item, { image_focal_x: value })"
                      @update:focal-y="(value) => setGigImageTransform(item, { image_focal_y: value })"
                      @update:rotation="(value) => setGigImageTransform(item, { image_rotation: value })"
                    />
                    <div class="field-hint">Image source is managed by integration; transform is saved for this Program gig.</div>
                  </div>
                  <div class="gig-meta">
                    <div class="field-group field-group--disabled">
                      <label class="field-label">
                        Gig ID
                      </label>
                      <input v-model="item.id" type="text" class="field" placeholder="gig-123" disabled />
                      <div v-if="isDuplicateGigId(item.id)" class="field-hint field-hint--error">
                        Duplicate gig ID. Use a unique ID before saving.
                      </div>
                    </div>
                    <div class="field-group field-group--disabled">
                      <label class="field-label">
                        Gig Type
                      </label>
                      <select
                        v-if="programGigTypeOptions.length > 0"
                        class="field"
                        :value="item.gig_type || ''"
                        disabled
                        @change="setGigType(item, $event.target.value)"
                      >
                        <option value="">Select gig type</option>
                        <option
                          v-for="option in programGigTypeSelectOptions(item)"
                          :key="`gig-type-option-${option.value}`"
                          :value="option.value"
                        >
                          {{ option.label }}
                        </option>
                      </select>
                      <input v-else v-model="item.gig_type" type="text" class="field" placeholder="DJ Set" disabled />
                    </div>
                  </div>
	                  <div class="bilingual-row">
	                    <div class="field-group field-group--disabled">
	                      <label class="field-label">
	                        Gig Title (DE)
	                      </label>
	                      <input
	                        :value="gigTitleValue(item, 'de')"
	                        type="text"
	                        class="field"
	                        placeholder="Gig title"
                        disabled
                        @pointerdown.stop
                        @mousedown.stop
                        @click.stop
                        @keydown.stop
                        @input="setGigTitleValue(item, 'de', $event.target.value)"
                      />
                    </div>
	                    <div class="field-group field-group--disabled">
	                      <label class="field-label">
	                        Gig Title (EN)
	                      </label>
	                      <input
	                        :value="gigTitleValue(item, 'en')"
	                        type="text"
	                        class="field"
	                        placeholder="Gig title"
                        disabled
                        @pointerdown.stop
                        @mousedown.stop
                        @click.stop
                        @keydown.stop
                        @input="setGigTitleValue(item, 'en', $event.target.value)"
                      />
	                    </div>
	                  </div>
	                  <div class="field-group field-group--disabled">
	                    <label class="field-label">
	                      Stage
	                    </label>
	                    <select class="field" :value="item.stage || ''" disabled @change="setGigStage(item, $event.target.value)">
	                      <option value="">Select stage</option>
	                      <option v-for="stageOption in stageSelectionOptions" :key="`gig-stage-option-${stageOption.value}`" :value="stageOption.value">
	                        {{ stageOption.label }}
	                      </option>
	                    </select>
	                  </div>
	                  <div class="bilingual-row">
	                    <div class="field-group field-group--disabled">
	                      <label class="field-label">
	                        Start
	                      </label>
	                      <VueDatePicker
	                        :model-value="gigDateTimeModel(item.start)"
	                        :enable-time-picker="true"
	                        :is-24="true"
	                        :minutes-increment="5"
	                        :clearable="true"
	                        :disabled="true"
	                        :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
	                        auto-apply
	                        placeholder="Select start datetime"
	                        class="program-datetime-picker"
	                        @update:model-value="setGigDateTime(item, 'start', $event)"
	                      />
	                    </div>
	                    <div class="field-group field-group--disabled">
	                      <label class="field-label">
	                        End
	                      </label>
	                      <VueDatePicker
	                        :model-value="gigDateTimeModel(item.end)"
	                        :enable-time-picker="true"
	                        :is-24="true"
	                        :minutes-increment="5"
	                        :clearable="true"
	                        :disabled="true"
	                        :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
	                        auto-apply
	                        placeholder="Select end datetime"
	                        class="program-datetime-picker"
	                        @update:model-value="setGigDateTime(item, 'end', $event)"
	                      />
	                    </div>
	                  </div>
	                  <div class="bilingual-row">
	                    <div class="field-group field-group--disabled">
                      <label class="field-label">
                        Subtitle / Genre (DE)
                      </label>
                      <input v-model="item.genre.de" type="text" class="field" placeholder="Genre" disabled />
                    </div>
                    <div class="field-group field-group--disabled">
                      <label class="field-label">
                        Subtitle / Genre (EN)
                      </label>
                      <input v-model="item.genre.en" type="text" class="field" placeholder="Genre" disabled />
                    </div>
                  </div>
                  <div class="field-group field-group--disabled program-genre-selection-field">
                    <label class="field-label">
                      Genre Selection
                    </label>
                    <div
                      class="program-genre-selection-options"
                      :class="{ 'is-disabled': true }"
                    >
                      <label
                        v-for="option in programGenreSelectionOptions"
                        :key="`gig-genre-selection-${option.value}`"
                        class="program-genre-selection-option"
                        :class="{ 'is-selected': isGigGenreSelected(item, option.value) }"
                      >
                        <input
                          type="checkbox"
                          :checked="isGigGenreSelected(item, option.value)"
                          disabled
                          @change="toggleGigGenreSelection(item, option.value, $event.target.checked)"
                        />
                        {{ option.label }}
                      </label>
                    </div>
                    <div class="field-hint">{{ programGenreSelectionHint }}</div>
                  </div>
                  <div class="bilingual-row">
                    <div class="field-group field-group--disabled">
                      <label class="field-label">
                        Description (DE)
                      </label>
	                      <textarea v-model="item.description.de" class="field field-textarea" rows="5" disabled />
                    </div>
                    <div class="field-group field-group--disabled">
                      <label class="field-label">
                        Description (EN)
                      </label>
	                      <textarea v-model="item.description.en" class="field field-textarea" rows="5" disabled />
	                    </div>
	                  </div>
                  <div class="field-group field-group-checkbox field-group--editable">
                    <label class="field-checkbox-label">
                      <input :checked="isGigRegisterChangesEnabled(item)" type="checkbox" @change="setGigRegisterChanges(item, $event.target.checked)" />
                      <span>Register changes</span>
                    </label>
                    <p class="field-hint">
                      Stores the current imported schedule and stage as the previous values used for public change labels.
                    </p>
                  </div>
                  <div v-if="isGigRegisterChangesEnabled(item)" class="program-gig-change-fields">
                    <div class="bilingual-row">
                      <div class="field-group field-group--editable" :class="{ 'field-group--disabled': isGigChangeDetailsDisabled(item) }">
                        <label class="field-label">
                          Changed Start
                        </label>
                        <VueDatePicker
                          :model-value="gigDateTimeModel(item.previous_start)"
                          :enable-time-picker="true"
                          :is-24="true"
                          :minutes-increment="5"
                          :clearable="true"
                          :disabled="isGigChangeDetailsDisabled(item)"
                          :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
                          auto-apply
                          placeholder="Select previous start datetime"
                          class="program-datetime-picker"
                          @update:model-value="setGigDateTime(item, 'previous_start', $event)"
                        />
                      </div>
                      <div class="field-group field-group--editable" :class="{ 'field-group--disabled': isGigChangeDetailsDisabled(item) }">
                        <label class="field-label">
                          Changed End
                        </label>
                        <VueDatePicker
                          :model-value="gigDateTimeModel(item.previous_end)"
                          :enable-time-picker="true"
                          :is-24="true"
                          :minutes-increment="5"
                          :clearable="true"
                          :disabled="isGigChangeDetailsDisabled(item)"
                          :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
                          auto-apply
                          placeholder="Select previous end datetime"
                          class="program-datetime-picker"
                          @update:model-value="setGigDateTime(item, 'previous_end', $event)"
                        />
                      </div>
                    </div>
                    <div class="field-group field-group--editable" :class="{ 'field-group--disabled': isGigChangeDetailsDisabled(item) }">
                      <label class="field-label">
                        Changed Stage
                      </label>
                      <select class="field" :value="item.previous_stage || ''" :disabled="isGigChangeDetailsDisabled(item)" @change="setGigPreviousStage(item, $event.target.value)">
                        <option value="">Select stage</option>
                        <option v-for="stageOption in stageSelectionOptions" :key="`gig-previous-stage-option-${stageOption.value}`" :value="stageOption.value">
                          {{ stageOption.label }}
                        </option>
                      </select>
                    </div>
                    <div class="program-gig-change-flags">
                      <div class="field-group field-group-checkbox field-group--editable" :class="{ 'field-group--disabled': isGigNewDisabled(item) }">
                        <label class="field-checkbox-label">
                          <input
                            :checked="Boolean(item.highlight_changes)"
                            type="checkbox"
                            :disabled="isGigNewDisabled(item)"
                            @change="setGigHighlightChanges(item, $event.target.checked)"
                          />
                          <span>is new</span>
                        </label>
                      </div>
                      <div class="field-group field-group-checkbox field-group--editable" :class="{ 'field-group--disabled': isGigCanceledDisabled(item) }">
                        <label class="field-checkbox-label">
                          <input
                            :checked="Boolean(item.canceled)"
                            type="checkbox"
                            :disabled="isGigCanceledDisabled(item)"
                            @change="setGigCanceled(item, $event.target.checked)"
                          />
                          <span>
                            is canceled
                          </span>
                        </label>
                      </div>
                    </div>
                  </div>
                  <div
                    v-if="programItemPageInfoMessage('gig', item)"
                    :class="[
                      'item-page-info',
                      programItemPageInfoTone('gig', item) === 'warning'
                        ? 'item-page-info--warning'
                        : 'item-page-info--info',
                    ]"
                  >
                    {{ programItemPageInfoMessage('gig', item) }}
                  </div>
                  <div class="gig-editor-footer-actions">
                    <div class="item-page-actions item-page-actions--source">
                      <button
                        class="btn-secondary"
                        type="button"
                        :disabled="!resolveProgramGigIntegrationReviewHref(item)"
                        @click="openProgramGigIntegrationReview(item)"
                      >
                        Edit Data
                      </button>
                      <button
                        v-if="canManageGigItemPage(item)"
                        class="btn-secondary"
                        type="button"
                        :disabled="!resolveGeneratedItemUrl(item)"
                        @click="openGeneratedItemPage(item)"
                      >
                        Open Item Page
                      </button>
                      <span v-if="!resolveProgramGigIntegrationReviewHref(item)" class="field-hint">
                        No source integration is recorded for this gig.
                      </span>
                    </div>
                    <div
                      v-if="canManageGigItemPage(item) && (isProgramItemPageGenerationPending('gig', item) || programItemPageGenerationError('gig', item))"
                      class="item-page-actions item-page-actions--page"
                    >
                      <span v-if="isProgramItemPageGenerationPending('gig', item)" class="field-hint">
                        Item page is being generated. The open button will activate automatically.
                      </span>
                      <span v-else-if="programItemPageGenerationError('gig', item)" class="field-hint field-hint--error">
                        {{ programItemPageGenerationError('gig', item) }}
                      </span>
                    </div>
                  </div>
              </template>
            </SectionListEditor>

            <label class="field-checkbox-label program-fallback-toggle">
              <input
                type="checkbox"
                :checked="programFallbackOverrideEnabled"
                @change="setProgramFallbackOverrideEnabled($event.target.checked)"
              />
              <span>Use custom fallback images for this program section</span>
            </label>

            <FallbackImageSelector
              v-if="programFallbackOverrideEnabled"
              :images="section?.programGigFallbackImages || []"
              :media-tag="programGigFallbackMediaTag"
              :legacy-image-url="section?.programGigFallbackImageUrl || ''"
              :zoom="programGigFallbackZoom"
              :focal-x="programGigFallbackFocalX"
              :focal-y="programGigFallbackFocalY"
              :rotation="programGigFallbackRotation"
              aspect-ratio="1:1"
              direction="landscape"
              source-context="section.program.fallback.image"
              description="Images used when program gig or stage images are empty. Imported gigs can also receive these images when no image is mapped."
              @apply-images="applyProgramGigFallbackImages"
              @clear-images="clearProgramGigFallbackImages"
              @update-transform="setProgramGigFallbackTransform"
            />
          </div>
        </details>

        <details class="admin-section">
          <summary class="admin-section-title">Day Range Settings</summary>
          <div class="admin-section-content">
            <p class="field-hint">Configure when a "day" starts and ends. Useful for festivals where events run past midnight.</p>
            <div class="day-range-inputs">
              <div class="field-group">
                <label class="field-label">Day Starts At</label>
                <select
                  :value="dayStartHour"
                  class="day-range-select"
                  @change="updateSection(effectiveKey, { dayStartHour: parseInt($event.target.value) })"
                >
                  <option v-for="h in 24" :key="h-1" :value="h-1">{{ String(h-1).padStart(2, '0') }}:00</option>
                </select>
              </div>
              <div class="field-group">
                <label class="field-label">Day Ends At</label>
                <select
                  :value="dayEndHour"
                  class="day-range-select"
                  @change="updateSection(effectiveKey, { dayEndHour: parseInt($event.target.value) })"
                >
                  <option v-for="h in 30" :key="h" :value="h">
                    {{ String(h <= 24 ? h : h - 24).padStart(2, '0') }}:00{{ h > 24 ? ' (+1 next day)' : '' }}
                  </option>
                </select>
                <span class="field-hint">Select 25-30 for times past midnight (01:00 - 06:00 next day)</span>
              </div>
            </div>
            <div v-if="dayEndHour <= dayStartHour" class="day-range-info">
              Events from {{ String(dayStartHour).padStart(2, '0') }}:00 to {{ String(dayEndHour <= 24 ? dayEndHour : dayEndHour - 24).padStart(2, '0') }}:00 (next day) will be shown under the starting day.
            </div>
            <div class="day-range-debug-actions">
              <button
                class="btn-secondary"
                type="button"
                :disabled="settingTodayAsProgramDay || sortedDays.length === 0"
                @click="setTodayAsProgramDayForDebug"
              >
                {{ settingTodayAsProgramDay ? "Applying..." : "Set Today as Program Day" }}
              </button>
              <div class="field-hint">
                Debug: temporarily shifts displayed gig dates for this page session only.
              </div>
              <span v-if="dayRangeDebugStatus.message" class="import-status" :class="dayRangeDebugStatus.type">
                {{ dayRangeDebugStatus.message }}
              </span>
            </div>
          </div>
        </details>
      </div>
    </template>

  </SectionBase>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue";
import { useRouter } from "vue-router";
import { faChevronLeft, faChevronRight, faMusic } from "@fortawesome/free-solid-svg-icons";
import { VueDatePicker } from "@vuepic/vue-datepicker";
import "@vuepic/vue-datepicker/dist/main.css";
import { useStore } from "../../store/store.js";
import * as api from "../../services/api.js";
import {
  resolveBackendResponsiveImagePayload,
  resolveBackendResponsiveImageVariants,
} from "../../utils/responsiveImages.js";
import {
  normalizeFallbackImageConfig,
  resolveEffectiveFallbackImageConfig,
  resolveFallbackImageForIndex,
  resolveFallbackImagePool,
} from "../../utils/fallbackImages.js";
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
import { getBaseSectionSwatchStyle } from "./_baseSectionSwatchStyle.js";
import {
  DATE_PICKER_DATE_TIME_DISPLAY_FORMATS,
  formatServerDateOnly,
  getCurrentServerWallDate,
  parseServerDateOnlyParts,
  serverWallDateTimeToLocalDate,
} from "../../utils/revisionTime.js";

import SectionBase from "./_BaseSection.vue";
import SectionListEditor from "../admin/section-editor/SectionListEditor.vue";
import SectionIntegrationImporter from "../admin/section-editor/SectionIntegrationImporter.vue";
import FallbackImageSelector from "../admin/section-editor/FallbackImageSelector.vue";
import ImageTransformEditor from "../ui/ImageTransformEditor.vue";
import MediaLibrary from "../ui/MediaLibrary.vue";
import TransformedImage from "../ui/TransformedImage.vue";
import ColorLinkPicker from "../ui/color/ColorLinkPicker.vue";
import VueColorPicker from "../ui/color/VueColorPicker.vue";

const props = defineProps({
  sectionKey: { type: String, default: "program" },
  sectionData: { type: Object, default: null },
});

const {
  state,
  updateSection,
  saveSectionByKey,
  fetchProgramSharedData,
  saveProgramSharedData,
  saveProgramSharedGig,
  getEffectiveViewportDevice,
} = useStore();
const router = useRouter();

const effectiveKey = computed(() => props.sectionKey);
const currentAdminTab = computed(() => state.sectionAdminActiveTabs?.[effectiveKey.value] || "");

// Screen width tracking for responsive classes
const screenWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1024);
const updateScreenWidth = () => { screenWidth.value = window.innerWidth; };
const effectiveResponsiveDevice = computed(() => getEffectiveViewportDevice());
const nowTimestamp = ref(Date.now());
const dayGanttScrollContainer = ref(null);
const stageGanttScrollContainer = ref(null);
let nowTickTimer = null;
let fixedGigScrollFrame = null;
let programSharedFullFetchPromise = null;
const updateNowTimestamp = () => {
  nowTimestamp.value = Date.now();
};

const editableProgramCatalogContext = computed(() =>
  Boolean(state.isAdmin || state.canContent) && !state.previewMode
);

async function ensureFullProgramSharedData() {
  if (state.programSharedLoaded && state.programSharedScope === "full") return;
  if (!programSharedFullFetchPromise) {
    programSharedFullFetchPromise = fetchProgramSharedData()
      .finally(() => {
        programSharedFullFetchPromise = null;
      });
  }
  await programSharedFullFetchPromise;
}

onMounted(async () => {
  window.addEventListener('resize', updateScreenWidth);
  updateNowTimestamp();
  nowTickTimer = window.setInterval(updateNowTimestamp, 30 * 1000);
  if (editableProgramCatalogContext.value) {
    await ensureFullProgramSharedData();
  } else if (!state.programSharedLoaded) {
    await fetchProgramSharedData();
  }
  scheduleFixedGigScrollIntoView();
});
onUnmounted(() => {
  window.removeEventListener('resize', updateScreenWidth);
  if (nowTickTimer) {
    clearInterval(nowTickTimer);
    nowTickTimer = null;
  }
  if (fixedGigScrollFrame !== null) {
    window.cancelAnimationFrame(fixedGigScrollFrame);
    fixedGigScrollFrame = null;
  }
  flushStageColorDesignPersist();
});

// Unified mobile view class (works for both real mobile and simulation)
const containerClasses = computed(() => ({
  'is-mobile-view': effectiveResponsiveDevice.value === 'mobile',
  'is-xs-view': screenWidth.value <= 480,
}));

const section = computed(() => {
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});
const isTemplateBuilderPage = computed(() =>
  String(state.pageSlug || "").startsWith("__template_")
);

const sectionForIntegration = computed(() => {
  const base = section.value && typeof section.value === "object"
    ? { ...section.value }
    : {};
  base.stages = Array.isArray(state.programSharedStages) ? state.programSharedStages : [];
  base.gigs = Array.isArray(state.programSharedGigs) ? state.programSharedGigs : [];
  base.programStagesIntegrationMapping = state.programSharedStagesIntegrationMapping || {};
  base.programStagesIntegrationMappingCacheState = state.programSharedStagesIntegrationMappingCacheState || {};
  base.programGigsIntegrationMapping = state.programSharedGigsIntegrationMapping || {};
  base.programGigsIntegrationMappingCacheState = state.programSharedGigsIntegrationMappingCacheState || {};
  return base;
});

const sectionForIntegrationImport = computed(() => {
  return cloneValue(sectionForIntegration.value || {});
});

function clampNumber(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function readSectionValue(frontKey, fallback = null) {
  if (section.value?.[frontKey] !== undefined) return section.value[frontKey];
  return fallback;
}

const dateSelectionColor = computed(() => readSectionValue("dateSelectionColor", null));
const dateSelectionColorLink = computed(() => readSectionValue("dateSelectionColorLink", null));
const dateSelectionColorVariation = computed(() =>
  normalizeColorVariation(readSectionValue("dateSelectionColorVariation", null))
);
const MIN_PROGRAM_STAGE_ROW_HEIGHT = 100;
const DEFAULT_PROGRAM_STAGE_ROW_HEIGHT = 120;
const MAX_PROGRAM_STAGE_ROW_HEIGHT = 220;
const stageRowHeight = computed(() => {
  const raw = Number(readSectionValue("stageRowHeight", DEFAULT_PROGRAM_STAGE_ROW_HEIGHT));
  if (!Number.isFinite(raw)) return DEFAULT_PROGRAM_STAGE_ROW_HEIGHT;
  return clampNumber(Math.round(raw), MIN_PROGRAM_STAGE_ROW_HEIGHT, MAX_PROGRAM_STAGE_ROW_HEIGHT);
});
const colorVariationOptions = COLOR_VARIATION_OPTIONS;

const designColorOptions = computed(() =>
  buildColorLinkOptions(state.design, {
    includeHighContrast: true,
    parameterConfigs: state.adminDesignConfig?.parameters,
  })
);

function resolveBaseColor(linkKey) {
  return resolveLinkedColor(state.design, linkKey, state.adminDesignConfig?.parameters);
}

watch(
  () => [
    state.design.primaryColor,
    state.design.secondaryColor,
    state.design.backgroundColor,
    state.design.accentColor,
    state.design.sectionBackgroundColor,
    state.design.highContrastDark,
    state.design.highContrastLight,
  ],
  () => {
    const patch = {};
    if (dateSelectionColorLink.value) {
      const resolved = resolveBaseColor(dateSelectionColorLink.value);
      if (resolved !== null && resolved !== dateSelectionColor.value) patch.dateSelectionColor = resolved;
    }
    if (Object.keys(patch).length > 0) {
      updateSection(effectiveKey.value, patch, { revisionKind: "design" });
    }
  }
);

function setDateSelectionColor(value) {
  updateSection(
    effectiveKey.value,
    { dateSelectionColor: value, dateSelectionColorLink: null },
    { revisionKind: "design" }
  );
}

function setDateSelectionColorVariation(value) {
  const normalized = normalizeColorVariation(value);
  updateSection(
    effectiveKey.value,
    { dateSelectionColorVariation: normalized === DEFAULT_COLOR_VARIATION ? null : normalized },
    { revisionKind: "design" }
  );
}

function normalizeResolvedColor(value, backgroundBaseKey = null, backgroundColor = null) {
  if (!value || value === HIGH_CONTRAST_TOKEN) {
    return resolveHighContrastColorForBackground(
      state.design,
      state.adminDesignConfig,
      {
        backgroundColor: backgroundColor || state.design.sectionBackgroundColor || "#ffffff",
        backgroundBaseKey: backgroundBaseKey || "sectionBackgroundColor",
      }
    );
  }
  return value;
}

function getStageColorLink(stage) {
  return stage?.color_link ?? null;
}

function getStageColorVariation(stage) {
  return normalizeColorVariation(stage?.color_variation);
}

function getStageCustomColor(stage) {
  const raw = stage?.color;
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return trimmed || null;
}

function hasStageColorOverride(stage) {
  return Boolean(getStageColorLink(stage) || getStageCustomColor(stage));
}

function applyDesignColorLink(which, baseKey) {
  const resolved = resolveBaseColor(baseKey);
  if (resolved === null) return;
  if (which === "date") {
    updateSection(
      effectiveKey.value,
      { dateSelectionColor: resolved, dateSelectionColorLink: baseKey },
      { revisionKind: "design" }
    );
  }
}

function clearDesignColor(which) {
  if (which === "date") {
    updateSection(
      effectiveKey.value,
      { dateSelectionColor: null, dateSelectionColorLink: null, dateSelectionColorVariation: null },
      { revisionKind: "design" }
    );
  }
}

function updateStageColorDesignState(stageId, mutateStage) {
  const normalizedStageId = String(stageId || "").trim();
  if (!normalizedStageId || typeof mutateStage !== "function") return;

  const applyStageMutation = (rows) => {
    let changed = false;
    const nextRows = (Array.isArray(rows) ? rows : []).map((stage) => {
      if (String(stage?.id || "").trim() !== normalizedStageId) return stage;
      const nextStage = mutateStage({ ...stage });
      if (nextStage !== stage) changed = true;
      return nextStage;
    });
    return { nextRows, changed };
  };

  const catalog = getCurrentSharedProgramCatalog();
  const { nextRows, changed } = applyStageMutation(catalog.stages);
  if (!changed) return;
  applyStageColorDesignLocally(nextRows, catalog.gigs);
  queueStageColorDesignPersist();
}

function setStageColor(stageId, color) {
  const normalized = typeof color === "string" && color.trim() ? color.trim() : null;
  if (!normalized) return;
  updateStageColorDesignState(stageId, (stage) => ({ ...stage, color: normalized, color_link: null }));
}

function applyStageColorLink(stageId, baseKey) {
  const resolved = normalizeResolvedColor(
    resolveBaseColor(baseKey),
    "sectionBackgroundColor",
    state.design.sectionBackgroundColor
  );
  if (resolved === null) return;
  updateStageColorDesignState(stageId, (stage) => ({ ...stage, color_link: baseKey }));
}

function clearStageColor(stageId) {
  updateStageColorDesignState(stageId, (stage) => {
    const next = { ...stage, color: null, color_link: null };
    delete next.color_variation;
    return next;
  });
}

function setStageColorVariation(stageId, value) {
  const normalized = normalizeColorVariation(value);
  updateStageColorDesignState(stageId, (stage) => {
    const next = { ...stage };
    if (normalized === DEFAULT_COLOR_VARIATION) {
      delete next.color_variation;
    } else {
      next.color_variation = normalized;
    }
    return next;
  });
}

function setStageRowHeight(value) {
  const next = clampNumber(
    Math.round(Number(value) || DEFAULT_PROGRAM_STAGE_ROW_HEIGHT),
    MIN_PROGRAM_STAGE_ROW_HEIGHT,
    MAX_PROGRAM_STAGE_ROW_HEIGHT
  );
  updateSection(effectiveKey.value, { stageRowHeight: next }, { revisionKind: "design" });
}

function setMaxVisibleHours(value) {
  const next = clampNumber(Math.round(Number(value) || 6), 2, 24);
  updateSection(effectiveKey.value, { maxVisibleHours: next }, { revisionKind: "design" });
}

function swatchStyle(previewColor, options = {}) {
  return getBaseSectionSwatchStyle(state.design, previewColor, options);
}

function hexOrDefault(colorValue, fallback) {
  return typeof colorValue === "string" && colorValue.startsWith("#") ? colorValue : fallback;
}

const resolvedDateSelectionColor = computed(() => {
  const resolved = normalizeResolvedColor(
    dateSelectionColor.value,
    "sectionBackgroundColor",
    state.design.sectionBackgroundColor
  );
  return applyColorVariation(resolved, dateSelectionColorVariation.value);
});
const resolvedDateSelectionTextColor = computed(() =>
  resolveHighContrastColorForBackground(
    state.design,
    state.adminDesignConfig,
    {
      backgroundColor: resolvedDateSelectionColor.value,
      backgroundBaseKey: null,
    }
  )
);

const programStyleVars = computed(() => {
  const baseHeight = stageRowHeight.value;
  const mobileHeight = Math.round(Math.max(64, baseHeight * 0.8));
  const soloHeight = Math.round(baseHeight * 1.5);
  const soloMobileHeight = Math.round(Math.max(mobileHeight + 24, baseHeight * 1.2));
  return {
    "--program-stage-row-height": `${baseHeight}px`,
    "--program-stage-row-height-solo": `${soloHeight}px`,
    "--program-stage-row-height-mobile": `${mobileHeight}px`,
    "--program-stage-row-height-solo-mobile": `${soloMobileHeight}px`,
    "--program-date-selection-color": resolvedDateSelectionColor.value,
    "--program-date-selection-text-color": resolvedDateSelectionTextColor.value,
  };
});

const t = computed(() =>
  state.lang === "de"
    ? {
        noGigs: "Keine Acts an diesem Tag",
        noDescription: "Keine Beschreibung verfügbar",
        byDay: "Nach Tag",
        byStage: "Nach Stage",
        showAll: "Alle anzeigen",
        acts: "Acts",
        gigsOnStage: "Acts auf dieser Stage",
        more: "Mehr",
        moreHiddenAdmin: "Mehr (Hidden)",
        moreHiddenPublic: "Mehr (öffentlich deaktiviert)",
        moreUnavailable: "Mehr nicht verfügbar",
        moreHiddenAdminLabel: "Act-Seite ist nicht öffentlich. Im Admin trotzdem öffnen.",
        moreHiddenPublicLabel: "Mehr ist in der öffentlichen Ansicht deaktiviert, weil diese Act-Seite nicht öffentlich ist.",
        moreUnavailableLabel: "Keine Act-Seite verfügbar.",
        description: "Info",
        info: "Info",
        previousGig: "Vorheriger Act",
        nextGig: "Nächster Act",
        canceled: "Abgesagt",
        newGig: "Neu",
        dayChanged: "Tag geändert",
        timeChanged: "Zeit geändert",
        stageChanged: "Stage geändert",
      }
    : {
        noGigs: "No acts on this day",
        noDescription: "No description available",
        byDay: "By Day",
        byStage: "By Stage",
        showAll: "Show All",
        acts: "acts",
        gigsOnStage: "Acts on this stage",
        more: "More",
        moreHiddenAdmin: "More (hidden)",
        moreHiddenPublic: "More (public disabled)",
        moreUnavailable: "More unavailable",
        moreHiddenAdminLabel: "Act page is not public. Open it as admin anyway.",
        moreHiddenPublicLabel: "More is disabled in public view because this act page is not public.",
        moreUnavailableLabel: "No act page is available.",
        description: "Info",
        info: "Info",
        previousGig: "Previous act",
        nextGig: "Next act",
        canceled: "Canceled",
        newGig: "New",
        dayChanged: "Day changed",
        timeChanged: "Time changed",
        stageChanged: "Stage changed",
      }
);

const localizedText = (obj) => {
  if (!obj) return "";
  if (typeof obj === "string") return obj;
  return state.lang === "de" ? obj.de || obj.en : obj.en || obj.de;
};

const getGigStage = (gig) => normalizeStageLookupText(gig?.stage);

function normalizeStageLookupText(value) {
  if (value == null) return "";
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value).trim();
  if (Array.isArray(value)) {
    for (const entry of value) {
      const resolved = normalizeStageLookupText(entry);
      if (resolved) return resolved;
    }
    return "";
  }
  if (typeof value === "object") {
    if (value && (typeof value.id === "string" || typeof value.id === "number" || typeof value.id === "boolean")) {
      const idValue = String(value.id).trim();
      if (idValue) return idValue;
    }
    if (value && (typeof value.value === "string" || typeof value.value === "number" || typeof value.value === "boolean")) {
      const optionValue = String(value.value).trim();
      if (optionValue) return optionValue;
    }
    if (value && (typeof value.name === "string" || typeof value.name === "number" || typeof value.name === "boolean")) {
      const nameValue = String(value.name).trim();
      if (nameValue) return nameValue;
    }
    if (value && (typeof value.title === "string" || typeof value.title === "number" || typeof value.title === "boolean")) {
      const titleValue = String(value.title).trim();
      if (titleValue) return titleValue;
    }
    if (value && (typeof value.label === "string" || typeof value.label === "number" || typeof value.label === "boolean")) {
      const labelValue = String(value.label).trim();
      if (labelValue) return labelValue;
    }
    if (value && (typeof value.stage === "string" || typeof value.stage === "number" || typeof value.stage === "boolean")) {
      const stageValue = String(value.stage).trim();
      if (stageValue) return stageValue;
    }
    if (value && typeof value.stage === "object") {
      const nestedStageValue = normalizeStageLookupText(value.stage);
      if (nestedStageValue) return nestedStageValue;
    }
    if (value && typeof value.name === "object") {
      const localizedName = normalizeStageLookupText(value.name);
      if (localizedName) return localizedName;
    }
    if (value && (Object.prototype.hasOwnProperty.call(value, "de") || Object.prototype.hasOwnProperty.call(value, "en"))) {
      return String(value.de || value.en || "").trim();
    }
  }
  return String(value || "").trim();
}

function normalizeStageLookupKey(value) {
  const raw = normalizeStageLookupText(value);
  if (!raw) return "";
  return raw
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function buildGigStageIdResolver(stageRows = []) {
  const normalizedStages = normalizeStageDraftRows(stageRows);
  const byId = new Set();
  const byLookup = new Map();
  normalizedStages.forEach((stage) => {
    const stageId = String(stage?.id || "").trim();
    if (!stageId) return;
    byId.add(stageId);
    const stageNameDE = String(stage?.name?.de || "").trim();
    const stageNameEN = String(stage?.name?.en || "").trim();
    [stageId, stageNameDE, stageNameEN].forEach((entry) => {
      const key = normalizeStageLookupKey(entry);
      if (key && !byLookup.has(key)) {
        byLookup.set(key, stageId);
      }
    });
  });

  return (rawValue) => {
    const directValue = normalizeStageLookupText(rawValue);
    if (!directValue) return "";
    if (byId.has(directValue)) return directValue;
    const lookupKey = normalizeStageLookupKey(directValue);
    if (lookupKey && byLookup.has(lookupKey)) {
      return byLookup.get(lookupKey) || "";
    }
    return directValue;
  };
}

function cloneValue(value) {
  if (value === undefined) return undefined;
  if (value === null) return null;
  if (typeof value === "object") {
    return JSON.parse(JSON.stringify(value));
  }
  return value;
}

function normalizeBilingual(value) {
  if (!value) return { de: "", en: "" };
  if (typeof value === "string") {
    return { de: value, en: value };
  }
  const source = typeof value === "object" ? { ...value } : {};
  return {
    ...source,
    de: source.de || "",
    en: source.en || "",
  };
}

function normalizeProgramGenreSelection(value) {
  const values = [];
  const seen = new Set();
  const visit = (entry) => {
    if (Array.isArray(entry)) {
      entry.forEach((nested) => visit(nested));
      return;
    }
    if (entry == null) return;
    const normalized = String(entry).trim();
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    values.push(normalized);
  };
  visit(value);
  return values;
}

function normalizeGigImageZoom(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return 1;
  return clampNumber(numericValue, 1, 4);
}

function normalizeGigImageFocal(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return 50;
  return clampNumber(numericValue, 0, 100);
}

function normalizeGigImageRotation(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return 0;
  return clampNumber(numericValue, -180, 180);
}

function normalizeGigResponsiveVariants(value) {
  return resolveBackendResponsiveImageVariants(value);
}

function resolveProgramItemResponsiveVariants(value) {
  return resolveBackendResponsiveImageVariants(value);
}

const programGigFallbackImagePool = computed(() =>
  resolveFallbackImagePool(
    section.value?.programFallbackImages || section.value?.programGigFallbackImages,
    section.value?.programFallbackImageUrl || section.value?.programGigFallbackImageUrl
  )
);

const programFallbackOverrideEnabled = computed(() =>
  section.value?.programFallbackOverrideEnabled === true
  || section.value?.programGigFallbackOverrideEnabled === true
);

const programSectionFallbackConfig = computed(() =>
  normalizeFallbackImageConfig({
    images: section.value?.programFallbackImages || section.value?.programGigFallbackImages,
    mediaTag: section.value?.programFallbackMediaTag || section.value?.programGigFallbackMediaTag,
    legacyImageUrl: section.value?.programFallbackImageUrl || section.value?.programGigFallbackImageUrl,
    zoom: section.value?.programFallbackZoom ?? section.value?.programGigFallbackZoom,
    focalX: section.value?.programFallbackFocalX ?? section.value?.programGigFallbackFocalX,
    focalY: section.value?.programFallbackFocalY ?? section.value?.programGigFallbackFocalY,
    rotation: section.value?.programFallbackRotation ?? section.value?.programGigFallbackRotation,
  })
);

const effectiveProgramFallbackConfig = computed(() =>
  resolveEffectiveFallbackImageConfig({
    globalFallbacks: state.mediaFallbacks,
    sectionFallbacks: programSectionFallbackConfig.value,
    useSectionFallbacks: programFallbackOverrideEnabled.value,
  })
);

function resolveProgramFallbackImageMedia(index = 0) {
  const fallback = resolveFallbackImageForIndex(effectiveProgramFallbackConfig.value, index);
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

function resolveProgramGigFallbackIndex(gig, index = null) {
  const numericIndex = Number(index);
  if (Number.isInteger(numericIndex) && numericIndex >= 0) return numericIndex;
  const gigId = String(gig?.id || "").trim();
  if (gigId) {
    const foundIndex = gigs.value.findIndex((entry) => String(entry?.id || "").trim() === gigId);
    if (foundIndex >= 0) return foundIndex;
  }
  return 0;
}

function resolveProgramGigImageMedia(gig, index = null) {
  const imageUrl = String(gig?.image_url || "").trim();
  if (imageUrl) {
    return {
      url: imageUrl,
      responsiveVariants: resolveProgramItemResponsiveVariants(gig),
      zoom: normalizeGigImageZoom(gig?.image_zoom),
      focalX: normalizeGigImageFocal(gig?.image_focal_x),
      focalY: normalizeGigImageFocal(gig?.image_focal_y),
      rotation: normalizeGigImageRotation(gig?.image_rotation),
    };
  }
  return resolveProgramFallbackImageMedia(resolveProgramGigFallbackIndex(gig, index));
}

function resolveProgramGigImageUrl(gig, index = null) {
  return resolveProgramGigImageMedia(gig, index).url;
}

function resolveProgramGigResponsiveVariants(gig, index = null) {
  return resolveProgramGigImageMedia(gig, index).responsiveVariants;
}

function resolveProgramGigImageZoom(gig, index = null) {
  return resolveProgramGigImageMedia(gig, index).zoom;
}

function resolveProgramGigImageFocalX(gig, index = null) {
  return resolveProgramGigImageMedia(gig, index).focalX;
}

function resolveProgramGigImageFocalY(gig, index = null) {
  return resolveProgramGigImageMedia(gig, index).focalY;
}

function resolveProgramGigImageRotation(gig, index = null) {
  return resolveProgramGigImageMedia(gig, index).rotation;
}

const programGigFallbackMediaTag = computed(() =>
  String(section.value?.programGigFallbackMediaTag || "").trim()
);
const programGigFallbackZoom = computed(() =>
  normalizeGigImageZoom(section.value?.programGigFallbackZoom)
);
const programGigFallbackFocalX = computed(() =>
  normalizeGigImageFocal(section.value?.programGigFallbackFocalX)
);
const programGigFallbackFocalY = computed(() =>
  normalizeGigImageFocal(section.value?.programGigFallbackFocalY)
);
const programGigFallbackRotation = computed(() =>
  normalizeGigImageRotation(section.value?.programGigFallbackRotation)
);

function parseGigDateTime(rawValue) {
  return serverWallDateTimeToLocalDate(rawValue);
}

function formatGigDateTimeInputValue(value) {
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) return "";
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  const hour = String(value.getHours()).padStart(2, "0");
  const minute = String(value.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hour}:${minute}`;
}

function normalizeGigDateTimeValue(rawValue) {
  const parsed = parseGigDateTime(rawValue);
  if (!parsed) return "";
  return formatGigDateTimeInputValue(parsed);
}

function composeGigDateTimeValue(dayValue, timeValue) {
  const day = String(dayValue || "").trim();
  const time = String(timeValue || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return "";
  if (!/^\d{2}:\d{2}$/.test(time)) return "";
  return `${day}T${time}`;
}

function extractGigDatePart(dateTimeValue) {
  const normalized = normalizeGigDateTimeValue(dateTimeValue);
  return normalized ? normalized.slice(0, 10) : "";
}

function extractGigTimePart(dateTimeValue) {
  const normalized = normalizeGigDateTimeValue(dateTimeValue);
  return normalized ? normalized.slice(11, 16) : "";
}

function syncGigLegacyScheduleFields(item) {
  if (!item || typeof item !== "object") return;
  const currentStart = normalizeGigDateTimeValue(item.start);
  const currentEnd = normalizeGigDateTimeValue(item.end);
  const previousStart = normalizeGigDateTimeValue(item.previous_start);
  const previousEnd = normalizeGigDateTimeValue(item.previous_end);

  item.start = currentStart;
  item.end = currentEnd;
  item.previous_start = previousStart;
  item.previous_end = previousEnd;
  item.day = extractGigDatePart(currentStart) || String(item.day || "").trim();
  item.start_time = extractGigTimePart(currentStart) || String(item.start_time || "").trim();
  item.end_time = extractGigTimePart(currentEnd) || String(item.end_time || "").trim();
  item.previous_day = extractGigDatePart(previousStart) || String(item.previous_day || "").trim();
  item.previous_start_time = extractGigTimePart(previousStart) || String(item.previous_start_time || "").trim();
  item.previous_end_time = extractGigTimePart(previousEnd) || String(item.previous_end_time || "").trim();
}

function normalizeGig(gig = {}) {
  const source = gig && typeof gig === "object" ? { ...gig } : {};
  const titleSource = (
    source.title
    ?? source.artist_name
    ?? source.artistName
    ?? source.gig_title
    ?? source.gigTitle
    ?? source.name
  );
  const startDateTime = normalizeGigDateTimeValue(source.start || composeGigDateTimeValue(source.day, source.start_time));
  const endDateTime = normalizeGigDateTimeValue(source.end || composeGigDateTimeValue(source.day, source.end_time));
  const previousStartDateTime = normalizeGigDateTimeValue(
    source.previous_start
      || composeGigDateTimeValue(
        source.previous_day || extractGigDatePart(startDateTime) || source.day,
        source.previous_start_time
      )
  );
  const previousEndDateTime = normalizeGigDateTimeValue(
    source.previous_end
      || composeGigDateTimeValue(
        source.previous_day || extractGigDatePart(startDateTime) || source.day,
        source.previous_end_time
      )
  );
  const dayValue = extractGigDatePart(startDateTime) || String(source.day || "").trim();
  const hasLegacyChangeData = Boolean(
    source.highlight_changes
    || source.canceled
    || String(source.previous_start || source.previous_start_time || "").trim()
    || String(source.previous_end || source.previous_end_time || "").trim()
    || normalizeStageLookupText(source.previous_stage)
  );
  return {
	    ...source,
	    id: String(gig.id || "").trim(),
	    title: normalizeBilingual(titleSource),
	    start: startDateTime,
    end: endDateTime,
    day: dayValue,
    start_time: extractGigTimePart(startDateTime) || String(source.start_time || "").trim(),
    end_time: extractGigTimePart(endDateTime) || String(source.end_time || "").trim(),
    stage: getGigStage(gig),
    genre: normalizeBilingual(source.genre),
    genre_selection: normalizeProgramGenreSelection(source.genre_selection),
    description: normalizeBilingual(source.description),
    image_url: String(source.image_url || "").trim(),
    image_responsive_variants: normalizeGigResponsiveVariants(source.image_responsive_variants),
    image_zoom: normalizeGigImageZoom(source.image_zoom),
    image_focal_x: normalizeGigImageFocal(source.image_focal_x),
    image_focal_y: normalizeGigImageFocal(source.image_focal_y),
    image_rotation: normalizeGigImageRotation(source.image_rotation),
    register_changes: source.register_changes != null
      ? Boolean(source.register_changes)
      : hasLegacyChangeData,
    highlight_changes: Boolean(source.highlight_changes ?? false),
    canceled: Boolean(source.canceled ?? false),
    previous_start: previousStartDateTime,
    previous_end: previousEndDateTime,
    previous_day: (
      extractGigDatePart(previousStartDateTime)
      || String(source.previous_day ?? "").trim()
      || dayValue
    ),
    previous_start_time: (
      extractGigTimePart(previousStartDateTime)
      || String(source.previous_start_time ?? "").trim()
    ),
    previous_end_time: (
      extractGigTimePart(previousEndDateTime)
      || String(source.previous_end_time ?? "").trim()
    ),
    previous_stage: normalizeStageLookupText(source.previous_stage),
    page_slug: String(source.page_slug ?? "").trim(),
    item_url: String(source.item_url ?? "").trim(),
  };
}

function gigTitle(gig) {
  return normalizeBilingual(
    gig?.title
    ?? gig?.artist_name
    ?? gig?.artistName
    ?? gig?.gig_title
    ?? gig?.gigTitle
    ?? gig?.name
  );
}

function normalizeStageDraftItem(stage = {}) {
  const source = stage && typeof stage === "object" ? { ...stage } : {};
  return {
    ...source,
    id: String(stage.id || "").trim(),
    name: normalizeBilingual(stage.name),
    description: normalizeBilingual(stage.description),
    image_url: String(stage.image_url || "").trim(),
    image_responsive_variants: normalizeGigResponsiveVariants(stage.image_responsive_variants),
    color: String(stage.color || "").trim(),
    color_link: stage.color_link ?? null,
    color_variation: stage.color_variation ?? null,
    page_slug: String(stage.page_slug ?? "").trim(),
    item_url: String(stage.item_url ?? "").trim(),
  };
}

function normalizeGigDraftItem(gig = {}) {
  const normalized = normalizeGig(gig);
  delete normalized.artist_name;
  delete normalized.artistName;
  delete normalized.gig_title;
  delete normalized.gigTitle;
  delete normalized.__source;
  delete normalized.__base;
  delete normalized.__change;
  delete normalized.__canceled;
  delete normalized.__changed;
  return normalized;
}

function gigTitleValue(item, lang) {
  const normalizedLang = lang === "en" ? "en" : "de";
  return String(gigTitle(item)[normalizedLang] || "");
}

function setGigTitleValue(item, lang, value) {
  if (!item || typeof item !== "object") return;
  const normalizedLang = lang === "en" ? "en" : "de";
  const nextTitle = gigTitle(item);
  nextTitle[normalizedLang] = String(value ?? "");
  item.title = nextTitle;
}

function canManageGigItemPage(item) {
  return (
    Boolean(resolveProgramItemId(item))
    || Boolean(resolveGeneratedItemUrl(item))
    || Boolean(item?.item_page_missing)
    || Boolean(item?.item_page_template_outdated)
  );
}

const PROGRAM_IMPORT_SOURCE_KEY = "__integration_source_id";
const PROGRAM_GIGS_MAPPING_KEY = "programGigsIntegrationMapping";
const PROGRAM_GIGS_CACHE_STATE_KEY = "programGigsIntegrationMappingCacheState";
const PROGRAM_STAGE_TARGET_PATH = "stage";
const PROGRAM_GIG_TYPE_TARGET_PATH = "gig_type";
const PROGRAM_GENRE_SELECTION_TARGET_PATH = "genre_selection";

function normalizeProgramMappingPathSignature(path) {
  return String(path || "").trim()
    .replace(/\[(?:\d+|\*)\]/g, "")
    .replace(/^[$]root\./i, "")
    .replace(/^gigs\./i, "")
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/-/g, "_")
    .toLowerCase()
    .trim();
}

function normalizeProgramMappingRowsForCollection(mapping, collectionPath) {
  if (!mapping || typeof mapping !== "object") return [];
  const mappingsByCollection = mapping.list_mappings_by_collection_path
    || {};
  if (!mappingsByCollection || typeof mappingsByCollection !== "object") return [];
  const rawRows = mappingsByCollection[collectionPath];
  if (!Array.isArray(rawRows)) return [];
  return rawRows
    .map((row) => {
      if (!row || typeof row !== "object") return null;
      const sourcePath = String(row.source_path ?? "").trim();
      const targetPath = String(row.target_path ?? "").trim();
      if (!sourcePath || !targetPath) return null;
      return { sourcePath, targetPath };
    })
    .filter(Boolean);
}

function collectProgramOptionPathAliases(path) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return [];
  const aliases = new Set([normalizedPath]);
  const strippedPath = normalizedPath
    .replace(/^[$]root\./i, "")
    .replace(/^gigs\./i, "");
  if (strippedPath) {
    aliases.add(strippedPath);
    aliases.add(`gigs.${strippedPath}`);
    aliases.add(`$root.gigs.${strippedPath}`);
  }
  return Array.from(aliases);
}

function resolveProgramRawOptionsForSourcePath(options, sourcePath) {
  if (!options || typeof options !== "object") return [];
  for (const alias of collectProgramOptionPathAliases(sourcePath)) {
    const value = options[alias];
    if (Array.isArray(value)) return value;
  }
  return [];
}

function resolveProgramOptionsForSourcePath(options, sourcePath) {
  return normalizeProgramGenreSelection(resolveProgramRawOptionsForSourcePath(options, sourcePath));
}

const programGigIntegrationMappingForSelection = computed(() => {
  return state.programSharedGigsIntegrationMapping || {};
});

const programGigIntegrationCacheStateForSelection = computed(() => {
  return state.programSharedGigsIntegrationMappingCacheState || {};
});

function normalizeProgramIntegrationMappingPayload(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
}

function resolveProgramGigIntegrationMappingFromPatch(patch) {
  const directMapping = normalizeProgramIntegrationMappingPayload(patch?.[PROGRAM_GIGS_MAPPING_KEY]);
  if (Object.prototype.hasOwnProperty.call(patch || {}, PROGRAM_GIGS_MAPPING_KEY)) {
    return directMapping;
  }

  const cacheState = patch?.[PROGRAM_GIGS_CACHE_STATE_KEY];
  const cacheMapping = normalizeProgramIntegrationMappingPayload(cacheState?.integration_mapping);
  if (Object.prototype.hasOwnProperty.call(cacheState || {}, "integration_mapping")) {
    return cacheMapping;
  }

  return programGigIntegrationMappingForSelection.value || {};
}

const programGigIntegrationMappingRowsForSelection = computed(() =>
  normalizeProgramMappingRowsForCollection(programGigIntegrationMappingForSelection.value, "gigs")
);

function resolveProgramGigSourcePathForTarget(targetPath) {
  const targetSignature = normalizeProgramMappingPathSignature(targetPath);
  const row = programGigIntegrationMappingRowsForSelection.value.find((entry) =>
    normalizeProgramMappingPathSignature(entry?.targetPath) === targetSignature
  );
  return row?.sourcePath || "";
}

function programOptionSourcePathsMatch(leftPath, rightPath) {
  const leftAliases = new Set(collectProgramOptionPathAliases(leftPath));
  if (leftAliases.size === 0) return false;
  return collectProgramOptionPathAliases(rightPath).some((alias) => leftAliases.has(alias));
}

const programStageSourcePaths = computed(() =>
  programGigIntegrationMappingRowsForSelection.value
    .filter((entry) =>
      normalizeProgramMappingPathSignature(entry?.targetPath) === PROGRAM_STAGE_TARGET_PATH
    )
    .map((entry) => String(entry?.sourcePath || "").trim())
    .filter(Boolean)
);

const programGigTypeSourcePath = computed(() =>
  resolveProgramGigSourcePathForTarget(PROGRAM_GIG_TYPE_TARGET_PATH)
);

const programGenreSelectionSourcePath = computed(() =>
  resolveProgramGigSourcePathForTarget(PROGRAM_GENRE_SELECTION_TARGET_PATH)
);

const programGigTypeOptions = computed(() => {
  const sourcePath = programGigTypeSourcePath.value;
  if (!sourcePath) return [];
  const options = programGigIntegrationCacheStateForSelection.value?.options;
  return resolveProgramOptionsForSourcePath(options, sourcePath).map((value) => ({
    value,
    label: value,
  }));
});

const programGenreSelectionOptions = computed(() => {
  const sourcePath = programGenreSelectionSourcePath.value;
  if (!sourcePath) return [];
  const options = programGigIntegrationCacheStateForSelection.value?.options;
  return resolveProgramOptionsForSourcePath(options, sourcePath).map((value) => ({
    value,
    label: value,
  }));
});

const programGenreSelectionHint = computed(() => {
  if (!programGenreSelectionSourcePath.value) {
    return "Map an integration option field to genre_selection to enable genre filters.";
  }
  if (programGenreSelectionOptions.value.length === 0) {
    return "The mapped genre_selection source has no centralized options yet.";
  }
  return "Values are used by tile filters while subtitle genre text stays unchanged.";
});

function formatProgramMetadataPathLabel(path) {
  const normalizedPath = String(path || "").trim()
    .replace(/^[$]root\./i, "")
    .replace(/^gigs\./i, "")
    .trim();
  if (!normalizedPath) return "Option Metadata";
  return normalizedPath
    .replace(/\[(?:\d+|\*)\]/g, "")
    .replace(/[_-]+/g, " ")
    .replace(/\./g, " / ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .split(" ")
    .map((part) => {
      const text = String(part || "").trim();
      return text ? `${text.charAt(0).toUpperCase()}${text.slice(1)}` : "";
    })
    .filter(Boolean)
    .join(" ");
}

function resolveProgramStageOptionDisplayText(entry, fallback = "") {
  if (entry == null) return String(fallback || "").trim();
  if (typeof entry === "string" || typeof entry === "number" || typeof entry === "boolean") {
    return String(entry).trim();
  }
  if (Array.isArray(entry)) {
    for (const nestedEntry of entry) {
      const nestedValue = resolveProgramStageOptionDisplayText(nestedEntry, "");
      if (nestedValue) return nestedValue;
    }
    return String(fallback || "").trim();
  }
  if (typeof entry !== "object") return String(fallback || "").trim();

  const source = entry || {};
  const candidates = [
    source.label,
    source.title,
    source.name,
    source.value,
    source.id,
  ];
  for (const candidate of candidates) {
    if (candidate && typeof candidate === "object" && !Array.isArray(candidate)) {
      const localized = String(candidate.de || candidate.en || "").trim();
      if (localized) return localized;
    }
    if (candidate != null && typeof candidate !== "object") {
      const text = String(candidate).trim();
      if (text) return text;
    }
  }
  return String(fallback || "").trim();
}

function normalizeProgramStageMetadataOptionEntries(rawOptions) {
  const entries = [];
  const seen = new Set();
  const visit = (entry) => {
    if (Array.isArray(entry)) {
      entry.forEach((nestedEntry) => visit(nestedEntry));
      return;
    }
    if (entry == null) return;

    const value = normalizeStageLookupText(entry);
    if (!value) return;
    const key = normalizeStageLookupKey(value) || value.toLowerCase();
    if (!key || seen.has(key)) return;
    seen.add(key);

    const label = resolveProgramStageOptionDisplayText(entry, value) || value;
    entries.push({ value, label });
  };
  visit(rawOptions);
  return entries.sort((left, right) => left.label.localeCompare(right.label));
}

function buildProgramStageMetadataOptionLookup(cacheState = null) {
  const options = (
    cacheState && typeof cacheState === "object" && cacheState.options && typeof cacheState.options === "object"
      ? cacheState.options
      : programGigIntegrationCacheStateForSelection.value?.options
  );
  if (!options || typeof options !== "object") return new Map();

  const lookup = new Map();
  programStageSourcePaths.value.forEach((sourcePath) => {
    normalizeProgramStageMetadataOptionEntries(
      resolveProgramRawOptionsForSourcePath(options, sourcePath)
    ).forEach((option) => {
      [
        option?.value,
        option?.label,
      ].forEach((candidate) => {
        const key = normalizeStageLookupKey(candidate);
        if (key && !lookup.has(key)) {
          lookup.set(key, option);
        }
      });
    });
  });
  return lookup;
}

const programStageMetadataOptionSources = computed(() => {
  const options = programGigIntegrationCacheStateForSelection.value?.options;
  if (!options || typeof options !== "object") return [];
  const stageSourcePaths = programStageSourcePaths.value;
  if (stageSourcePaths.length === 0) return [];
  const rows = [];
  Object.entries(options).forEach(([rawSourcePath, rawValues]) => {
    if (!Array.isArray(rawValues)) return;
    const sourcePath = String(rawSourcePath || "").trim();
    if (!sourcePath) return;
    const matchedStageSourcePath = stageSourcePaths.find((stageSourcePath) =>
      programOptionSourcePathsMatch(sourcePath, stageSourcePath)
    );
    if (!matchedStageSourcePath) return;
    const optionEntries = normalizeProgramStageMetadataOptionEntries(rawValues);
    if (optionEntries.length === 0) return;
    rows.push({
      path: String(rawSourcePath || "").trim(),
      canonicalPath: sourcePath,
      label: `${formatProgramMetadataPathLabel(matchedStageSourcePath || sourcePath)} (${optionEntries.length})`,
      sourcePath: matchedStageSourcePath,
      count: optionEntries.length,
    });
  });
  return rows.sort((left, right) => left.label.localeCompare(right.label));
});

const selectedStageOptionsSourcePath = ref("");
const selectedStageOptionValue = ref("");

const selectedStageMetadataOptionEntries = computed(() => {
  const options = programGigIntegrationCacheStateForSelection.value?.options;
  const sourcePath = selectedStageOptionsSourcePath.value;
  if (!sourcePath || !options || typeof options !== "object") return [];
  return normalizeProgramStageMetadataOptionEntries(
    resolveProgramRawOptionsForSourcePath(options, sourcePath)
  );
});

const programStageMetadataOptionsHint = computed(() => {
  if (programStageSourcePaths.value.length === 0) {
    return "Map a gig integration source field to the gig Stage target. Missing stages are created from imported gig stage values.";
  }
  if (programStageMetadataOptionSources.value.length === 0) {
    return "No option metadata was found for the source field mapped to gig Stage. Imported gig stage values still create missing stages.";
  }
  return "Imported gig stage values create missing stage records automatically; selected entries can still be added before import.";
});

watch(programStageMetadataOptionSources, (sources) => {
  const currentSourcePath = selectedStageOptionsSourcePath.value;
  if (sources.some((source) => source.path === currentSourcePath)) return;
  selectedStageOptionsSourcePath.value = sources[0]?.path || "";
}, { immediate: true });

watch(selectedStageOptionsSourcePath, () => {
  const currentValue = selectedStageOptionValue.value;
  if (
    currentValue
    && selectedStageMetadataOptionEntries.value.some((entry) => entry.value === currentValue)
  ) return;
  selectedStageOptionValue.value = "";
});

function programGigTypeSelectOptions(item) {
  const rows = Array.isArray(programGigTypeOptions.value)
    ? [...programGigTypeOptions.value]
    : [];
  const currentValue = String(item?.gig_type || "").trim();
  if (currentValue && !rows.some((entry) => entry.value === currentValue)) {
    rows.unshift({
      value: currentValue,
      label: currentValue,
    });
  }
  return rows;
}

function normalizeProgramIntegrationSourceId(value) {
  return String(value || "").trim();
}

function normalizeProgramScalarIdentifier(value) {
  if (value == null) return "";
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function normalizeProgramIntegrationPrimaryKeyPath(value) {
  const normalized = String(value || "").trim();
  return normalized.toLowerCase().startsWith("in ")
    ? normalized.slice(3).trim()
    : normalized;
}

function tokenizeProgramObjectPath(path) {
  const normalized = String(path || "").trim();
  if (!normalized) return [];
  const tokens = [];
  let buffer = "";
  let index = 0;
  while (index < normalized.length) {
    const char = normalized[index];
    if (char === ".") {
      if (buffer) {
        tokens.push(buffer);
        buffer = "";
      }
      index += 1;
      continue;
    }
    if (char === "[") {
      if (buffer) {
        tokens.push(buffer);
        buffer = "";
      }
      const endIndex = normalized.indexOf("]", index + 1);
      if (endIndex < 0) return [];
      const rawToken = normalized.slice(index + 1, endIndex).trim().replace(/^['"]|['"]$/g, "");
      tokens.push(/^\d+$/.test(rawToken) ? Number.parseInt(rawToken, 10) : rawToken);
      index = endIndex + 1;
      continue;
    }
    buffer += char;
    index += 1;
  }
  if (buffer) tokens.push(buffer);
  return tokens;
}

function programPathTokenCandidates(token) {
  const normalized = String(token || "").trim();
  if (!normalized) return [];
  const candidates = [normalized];
  const camel = normalized
    .toLowerCase()
    .replace(/[_-]+([a-z0-9])/g, (_, char) => char.toUpperCase());
  if (camel && camel !== normalized) candidates.push(camel);
  const snake = normalized
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/-/g, "_")
    .toLowerCase();
  if (snake && snake !== normalized) candidates.push(snake);
  return Array.from(new Set(candidates));
}

function deepGetProgramPathValue(source, path) {
  if (!source || typeof source !== "object") return undefined;
  const tokens = tokenizeProgramObjectPath(path);
  if (!tokens.length) return undefined;
  let current = source;
  for (const token of tokens) {
    if (current == null) return undefined;
    if (typeof token === "number") {
      if (!Array.isArray(current) || token < 0 || token >= current.length) return undefined;
      current = current[token];
      continue;
    }
    if (typeof current !== "object") return undefined;
    let found = false;
    for (const candidate of programPathTokenCandidates(token)) {
      if (Object.prototype.hasOwnProperty.call(current, candidate)) {
        current = current[candidate];
        found = true;
        break;
      }
    }
    if (!found) return undefined;
  }
  return current;
}

function isInternalProgramGigId(value) {
  const normalized = String(value || "").trim();
  return /^gig-ih-[0-9a-f]{24}$/i.test(normalized);
}

function resolveProgramGigPrimaryKeyPaths(cacheState = programGigIntegrationCacheStateForSelection.value) {
  const source = cacheState && typeof cacheState === "object" ? cacheState : {};
  const listPrimaryKeyPaths = (
    source.list_primary_key_paths
    || source.listPrimaryKeyPaths
    || {}
  );
  return Array.from(new Set([
    normalizeProgramIntegrationPrimaryKeyPath(source.integration_output_primary_key_path),
    normalizeProgramIntegrationPrimaryKeyPath(source.integrationOutputPrimaryKeyPath),
    normalizeProgramIntegrationPrimaryKeyPath(listPrimaryKeyPaths?.gigs),
    normalizeProgramIntegrationPrimaryKeyPath(listPrimaryKeyPaths?.["typeData.gigs"]),
    normalizeProgramIntegrationPrimaryKeyPath(listPrimaryKeyPaths?.["type_data.gigs"]),
  ].filter(Boolean)));
}

function resolveProgramGigPrimaryKeyValue(item, cacheState = programGigIntegrationCacheStateForSelection.value) {
  if (!item || typeof item !== "object") return "";
  for (const path of resolveProgramGigPrimaryKeyPaths(cacheState)) {
    const value = normalizeProgramScalarIdentifier(deepGetProgramPathValue(item, path));
    if (!value || isInternalProgramGigId(value)) continue;
    return value;
  }
  return "";
}

function getProgramItemImportSourceId(item) {
  if (!item || typeof item !== "object") return "";
  return normalizeProgramIntegrationSourceId(item[PROGRAM_IMPORT_SOURCE_KEY]);
}

function getProgramGigExternalItemKey(item, cacheState = programGigIntegrationCacheStateForSelection.value) {
  if (!item || typeof item !== "object") return "";
  const primaryKeyValue = resolveProgramGigPrimaryKeyValue(item, cacheState);
  if (primaryKeyValue) return primaryKeyValue;
  return normalizeProgramScalarIdentifier(
    item.integration_item_key
    ?? item.integrationItemKey
    ?? item.template_integration_item_key
    ?? item.templateIntegrationItemKey
    ?? item.review_item_key
    ?? item.reviewItemKey
    ?? item.external_id
    ?? item.externalId
    ?? ""
  );
}

function getProgramImportedRowMergeKey(item, cacheState = programGigIntegrationCacheStateForSelection.value) {
  const externalKey = getProgramGigExternalItemKey(item, cacheState);
  if (externalKey) return `external:${externalKey}`;
  const itemId = String(item?.id || "").trim();
  return itemId ? `id:${itemId}` : "";
}

function getProgramImportedRowExternalMergeKey(item, cacheState = programGigIntegrationCacheStateForSelection.value) {
  const externalKey = getProgramGigExternalItemKey(item, cacheState);
  return externalKey ? `external:${externalKey}` : "";
}

function resolveProgramGigIntegrationId(item) {
  const directSourceId = getProgramItemImportSourceId(item);
  if (directSourceId) return directSourceId;
  const cacheSourceId = normalizeProgramIntegrationSourceId(
    programGigIntegrationCacheStateForSelection.value?.integration_id
  );
  if (cacheSourceId) return cacheSourceId;
  return normalizeProgramIntegrationSourceId(
    programGigIntegrationMappingForSelection.value?.selected_integration_id
  );
}

function resolveProgramGigIntegrationReviewItemKey(item) {
  return getProgramGigExternalItemKey(item) || String(item?.id || "").trim();
}

function resolveProgramGigIntegrationReviewRoute(item) {
  const integrationId = resolveProgramGigIntegrationId(item);
  if (!integrationId) return null;
  const itemKey = resolveProgramGigIntegrationReviewItemKey(item);
  return {
    path: "/admin/integrations/review",
    query: itemKey ? { integrationId, itemKey } : { integrationId },
  };
}

function resolveProgramGigIntegrationReviewHref(item) {
  const route = resolveProgramGigIntegrationReviewRoute(item);
  if (!route) return "";
  return router.resolve(route).href;
}

function openProgramGigIntegrationReview(item) {
  const route = resolveProgramGigIntegrationReviewRoute(item);
  if (!route) return;
  router.push(route);
}

function withProgramItemImportSource(item, sourceId) {
  if (!item || typeof item !== "object") return item;
  const normalizedSourceId = normalizeProgramIntegrationSourceId(sourceId);
  const nextItem = { ...item };
  if (!normalizedSourceId) {
    delete nextItem[PROGRAM_IMPORT_SOURCE_KEY];
    return nextItem;
  }
  nextItem[PROGRAM_IMPORT_SOURCE_KEY] = normalizedSourceId;
  return nextItem;
}

function collectProgramImportedRowPreservedFields(existingRow) {
  if (!existingRow || typeof existingRow !== "object") return {};
  const preserved = {};
  const pageSlug = String(existingRow.page_slug || "").trim();
  if (pageSlug) preserved.page_slug = pageSlug;
  const itemUrl = String(existingRow.item_url || "").trim();
  if (itemUrl) preserved.item_url = itemUrl;
  preserved.register_changes = Boolean(existingRow.register_changes ?? false);
  const previousStart = normalizeGigDateTimeValue(existingRow.previous_start);
  if (previousStart) preserved.previous_start = previousStart;
  const previousEnd = normalizeGigDateTimeValue(existingRow.previous_end);
  if (previousEnd) preserved.previous_end = previousEnd;
  const previousStage = normalizeStageLookupText(existingRow.previous_stage);
  if (previousStage) preserved.previous_stage = previousStage;
  preserved.canceled = Boolean(existingRow.canceled ?? false);
  preserved.highlight_changes = Boolean(existingRow.highlight_changes ?? false);
  if (existingRow.item_page_template_outdated !== undefined) {
    preserved.item_page_template_outdated = existingRow.item_page_template_outdated;
  }
  if (existingRow.item_page_missing !== undefined) {
    preserved.item_page_missing = existingRow.item_page_missing;
  }
  if (existingRow.item_page_mapped_fields_synced !== undefined) {
    preserved.item_page_mapped_fields_synced = existingRow.item_page_mapped_fields_synced;
  }
  return preserved;
}

function mergeProgramImportedRow(existingRow, importedRow, sourceId) {
  const normalizedSourceId = normalizeProgramIntegrationSourceId(sourceId);
  const importedWithSource = withProgramItemImportSource(importedRow, normalizedSourceId);
  if (!existingRow || typeof existingRow !== "object") {
    return importedWithSource;
  }
  const existingId = String(existingRow.id || "").trim();
  const importedId = String(importedWithSource?.id || "").trim();
  const merged = {
    ...importedWithSource,
    id: existingId || importedId,
    ...collectProgramImportedRowPreservedFields(existingRow),
  };
  if (normalizedSourceId) {
    merged[PROGRAM_IMPORT_SOURCE_KEY] = normalizedSourceId;
  } else {
    delete merged[PROGRAM_IMPORT_SOURCE_KEY];
  }
  return merged;
}

function ensureUniqueProgramGigIds(rows = []) {
  const seenIds = new Set();
  return (Array.isArray(rows) ? rows : []).map((gig) => {
    const nextGig = normalizeGigDraftItem(gig);
    let candidateId = String(nextGig?.id || "").trim();
    if (!candidateId) {
      candidateId = createGigId();
    }
    while (seenIds.has(candidateId)) {
      candidateId = createGigId();
    }
    seenIds.add(candidateId);
    return {
      ...nextGig,
      id: candidateId,
    };
  });
}

function scoreProgramGigDuplicateCanonicalCandidate(gig) {
  if (!gig || typeof gig !== "object") return 0;
  let score = 0;
  if (String(gig.page_slug || "").trim() || String(gig.item_url || "").trim()) {
    score += 1000;
  }
  if (gig.item_page_missing === false) {
    score += 700;
  } else if (gig.item_page_missing === true) {
    score -= 200;
  }
  if (
    gig.item_page_template_outdated !== undefined
    || gig.item_page_mapped_fields_synced !== undefined
  ) {
    score += 100;
  }
  if (String(gig.id || "").trim()) score += 10;
  if (getProgramItemImportSourceId(gig)) score += 5;
  return score;
}

function resolveProgramGigDuplicateCanonicalIndex(rows, indices) {
  let bestIndex = indices[0];
  let bestScore = scoreProgramGigDuplicateCanonicalCandidate(rows[bestIndex]);
  indices.forEach((index) => {
    const score = scoreProgramGigDuplicateCanonicalCandidate(rows[index]);
    if (score > bestScore) {
      bestScore = score;
      bestIndex = index;
    }
  });
  return bestIndex;
}

function collapseDuplicateProgramGigsByExternalKey(
  rows = [],
  stageRows = stageDraft.value,
  cacheState = programGigIntegrationCacheStateForSelection.value
) {
  const normalizedRows = normalizeGigDraftRows(rows, stageRows);
  const indicesByExternalKey = new Map();
  normalizedRows.forEach((row, index) => {
    const mergeKey = getProgramImportedRowExternalMergeKey(row, cacheState);
    if (!mergeKey) return;
    if (!indicesByExternalKey.has(mergeKey)) {
      indicesByExternalKey.set(mergeKey, []);
    }
    indicesByExternalKey.get(mergeKey).push(index);
  });

  const canonicalIndexByExternalKey = new Map();
  const mergedRowByExternalKey = new Map();
  indicesByExternalKey.forEach((indices, mergeKey) => {
    if (!Array.isArray(indices) || indices.length < 2) return;
    const distinctIds = new Set(
      indices
        .map((index) => String(normalizedRows[index]?.id || "").trim())
        .filter(Boolean)
    );
    if (distinctIds.size < 2) return;

    const canonicalIndex = resolveProgramGigDuplicateCanonicalIndex(normalizedRows, indices);
    const canonicalRow = normalizedRows[canonicalIndex];
    const latestImportedRow = normalizedRows[indices[indices.length - 1]] || canonicalRow;
    const sourceId = (
      getProgramItemImportSourceId(latestImportedRow)
      || getProgramItemImportSourceId(canonicalRow)
      || ""
    );
    const mergedRow = normalizeGigDraftItem(
      mergeProgramImportedRow(canonicalRow, latestImportedRow, sourceId)
    );
    canonicalIndexByExternalKey.set(mergeKey, canonicalIndex);
    mergedRowByExternalKey.set(mergeKey, mergedRow);
  });

  if (canonicalIndexByExternalKey.size === 0) {
    return { rows: normalizedRows, changed: false };
  }

  const collapsedRows = [];
  normalizedRows.forEach((row, index) => {
    const mergeKey = getProgramImportedRowExternalMergeKey(row, cacheState);
    if (!mergeKey || !canonicalIndexByExternalKey.has(mergeKey)) {
      collapsedRows.push(row);
      return;
    }
    if (canonicalIndexByExternalKey.get(mergeKey) !== index) return;
    collapsedRows.push(mergedRowByExternalKey.get(mergeKey) || row);
  });

  return {
    rows: normalizeGigDraftRows(collapsedRows, stageRows),
    changed: true,
  };
}

function resolveProgramGigImportSourceIdFromPatch(patch) {
  const sourceFromPatchCache = normalizeProgramIntegrationSourceId(
    patch?.[PROGRAM_GIGS_CACHE_STATE_KEY]?.integration_id
  );
  if (sourceFromPatchCache) return sourceFromPatchCache;

  const sourceFromPatchMapping = normalizeProgramIntegrationSourceId(
    patch?.[PROGRAM_GIGS_MAPPING_KEY]?.selected_integration_id
      ?? patch?.[PROGRAM_GIGS_CACHE_STATE_KEY]?.integration_mapping?.selected_integration_id
  );
  if (sourceFromPatchMapping) return sourceFromPatchMapping;

  const sourceFromSharedCache = normalizeProgramIntegrationSourceId(
    state.programSharedGigsIntegrationMappingCacheState?.integration_id
  );
  if (sourceFromSharedCache) return sourceFromSharedCache;

  return normalizeProgramIntegrationSourceId(
    state.programSharedGigsIntegrationMapping?.selected_integration_id
  );
}

function mergeProgramImportedRowsBySource({
  existingRows = [],
  importedRows = [],
  sourceId = "",
  cacheState = programGigIntegrationCacheStateForSelection.value,
  normalizeRow = (row) => row,
  ensureUniqueIds = (rows) => rows,
} = {}) {
  const normalizedSourceId = normalizeProgramIntegrationSourceId(sourceId);
  const normalizedImportedRows = (Array.isArray(importedRows) ? importedRows : [])
    .map((row) => withProgramItemImportSource(normalizeRow(row), normalizedSourceId));
  if (!normalizedSourceId) {
    return ensureUniqueIds(normalizedImportedRows);
  }

  const importedRowsByKey = new Map();
  const importedRowsWithoutKey = [];
  normalizedImportedRows.forEach((row) => {
    const rowKey = getProgramImportedRowMergeKey(row, cacheState);
    if (!rowKey || importedRowsByKey.has(rowKey)) {
      importedRowsWithoutKey.push(row);
      return;
    }
    importedRowsByKey.set(rowKey, row);
  });

  const currentRows = Array.isArray(existingRows) ? existingRows : [];
  const mergedRows = [];
  let lastInsertedImportedIndex = -1;

  currentRows.forEach((row) => {
    const normalizedExistingRow = normalizeRow(row);
    const rowKey = getProgramImportedRowMergeKey(normalizedExistingRow, cacheState);
    const existingSourceId = getProgramItemImportSourceId(normalizedExistingRow);
    const shouldTreatAsLegacyImported = (
      !existingSourceId
      && Boolean(rowKey)
      && importedRowsByKey.has(rowKey)
    );
    if (existingSourceId === normalizedSourceId || shouldTreatAsLegacyImported) {
      if (!rowKey || !importedRowsByKey.has(rowKey)) {
        return;
      }
      const importedRow = importedRowsByKey.get(rowKey);
      importedRowsByKey.delete(rowKey);
      mergedRows.push(
        mergeProgramImportedRow(normalizedExistingRow, importedRow, normalizedSourceId)
      );
      lastInsertedImportedIndex = mergedRows.length - 1;
      return;
    }
    mergedRows.push(normalizedExistingRow);
  });

  const remainingImportedRows = [
    ...Array.from(importedRowsByKey.values()).map((row) =>
      mergeProgramImportedRow(null, row, normalizedSourceId)
    ),
    ...importedRowsWithoutKey.map((row) =>
      mergeProgramImportedRow(null, row, normalizedSourceId)
    ),
  ];
  if (remainingImportedRows.length > 0) {
    const insertAt = lastInsertedImportedIndex >= 0
      ? lastInsertedImportedIndex + 1
      : mergedRows.length;
    mergedRows.splice(insertAt, 0, ...remainingImportedRows);
  }

  return ensureUniqueIds(mergedRows);
}

function mergeProgramGigImportsBySource({
  existingGigs = [],
  importedGigs = [],
  sourceId = "",
  cacheState = programGigIntegrationCacheStateForSelection.value,
} = {}) {
  return mergeProgramImportedRowsBySource({
    existingRows: existingGigs,
    importedRows: importedGigs,
    sourceId,
    cacheState,
    normalizeRow: normalizeGigDraftItem,
    ensureUniqueIds: ensureUniqueProgramGigIds,
  });
}

function normalizeProgramGigPageSlugValue(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const withoutQuery = raw.split("?")[0]?.split("#")[0] || "";
  return withoutQuery.replace(/^\/+|\/+$/g, "");
}

function resolveProgramGigPageSlug(gig) {
  const slugFromPageSlug = normalizeProgramGigPageSlugValue(gig?.page_slug);
  if (slugFromPageSlug) return slugFromPageSlug;

  const itemUrl = String(gig?.item_url || "").trim();
  if (!itemUrl) return "";

  if (/^https?:\/\//i.test(itemUrl)) {
    try {
      const parsed = new URL(itemUrl);
      return normalizeProgramGigPageSlugValue(parsed.pathname);
    } catch {
      return "";
    }
  }

  return normalizeProgramGigPageSlugValue(itemUrl);
}

function collectProgramGigPageSlugs(rows = []) {
  const unique = new Set(
    (Array.isArray(rows) ? rows : [])
      .map((gig) => resolveProgramGigPageSlug(gig))
      .filter(Boolean)
  );
  return Array.from(unique).sort();
}

function buildProgramGigPageAvailabilitySignature(rows = []) {
  return collectProgramGigPageSlugs(rows).join("|");
}

function parseDayTime(day, time) {
  return parseGigDateTime(composeGigDateTimeValue(day, time));
}

function parseDateOnlyValue(rawValue) {
  const parts = parseServerDateOnlyParts(rawValue);
  if (!parts) return null;
  const parsed = new Date(parts.year, parts.month - 1, parts.day);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

function formatDateOnlyValue(dateValue) {
  if (!(dateValue instanceof Date) || Number.isNaN(dateValue.getTime())) return "";
  const year = dateValue.getFullYear();
  const month = String(dateValue.getMonth() + 1).padStart(2, "0");
  const day = String(dateValue.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function shiftDateByDays(dateValue, dayOffset) {
  if (!(dateValue instanceof Date) || Number.isNaN(dateValue.getTime())) return null;
  return new Date(
    dateValue.getFullYear(),
    dateValue.getMonth(),
    dateValue.getDate() + dayOffset,
    dateValue.getHours(),
    dateValue.getMinutes(),
    dateValue.getSeconds(),
    dateValue.getMilliseconds()
  );
}

function gigDateTimeModel(rawValue) {
  return parseGigDateTime(rawValue);
}

function ensureGigChangeBaseline(item) {
  if (!item || typeof item !== "object") return;
  syncGigLegacyScheduleFields(item);
}

function clearGigChangeDetailFields(item) {
  if (!item || typeof item !== "object") return;
  item.previous_start = "";
  item.previous_end = "";
  item.previous_stage = "";
  item.previous_day = "";
  item.previous_start_time = "";
  item.previous_end_time = "";
}

function queueSaveGigDraftForItem(item, { delay = PROGRAM_GIG_DRAFT_SAVE_DELAY_MS } = {}) {
  if (!item || typeof item !== "object") return Promise.resolve();
  const itemId = String(item.id || "").trim();
  const rawIndex = gigDraft.value.findIndex((gig) => gig === item || (itemId && String(gig?.id || "").trim() === itemId));
  if (rawIndex < 0) return Promise.resolve();
  return queueSaveGigDraftByRawIndex(rawIndex, { delay });
}

function resolveProgramGigDraftSaveKey(rawIndex) {
  const numericIndex = Number.parseInt(rawIndex, 10);
  if (!Number.isFinite(numericIndex) || numericIndex < 0 || numericIndex >= gigDraft.value.length) return "";
  const item = gigDraft.value[numericIndex];
  const itemId = String(item?.id || "").trim();
  return itemId ? `id:${itemId}` : `index:${numericIndex}`;
}

function resolveProgramGigDraftIndexForSaveKey(saveKey) {
  const key = String(saveKey || "").trim();
  if (!key) return -1;
  if (key.startsWith("id:")) {
    const itemId = key.slice(3);
    if (!itemId) return -1;
    return gigDraft.value.findIndex((gig) => String(gig?.id || "").trim() === itemId);
  }
  if (key.startsWith("index:")) {
    const index = Number.parseInt(key.slice(6), 10);
    return Number.isFinite(index) && index >= 0 && index < gigDraft.value.length ? index : -1;
  }
  return -1;
}

function getProgramGigDraftSaveState(saveKey) {
  const key = String(saveKey || "").trim();
  if (!key) return null;
  let entry = programGigDraftSaveStates.get(key);
  if (!entry) {
    entry = {
      timer: null,
      version: 0,
      promise: Promise.resolve(),
      waiters: [],
    };
    programGigDraftSaveStates.set(key, entry);
  }
  return entry;
}

function queueSaveGigDraftByRawIndex(rawIndex, { delay = 0 } = {}) {
  const saveKey = resolveProgramGigDraftSaveKey(rawIndex);
  const entry = getProgramGigDraftSaveState(saveKey);
  if (!entry) return Promise.resolve();
  entry.version += 1;
  const scheduledDelay = Math.max(0, Number(delay) || 0);
  if (entry.timer) {
    clearTimeout(entry.timer);
    entry.timer = null;
  }

  const queuedPromise = new Promise((resolve, reject) => {
    entry.waiters.push({ resolve, reject });
  });

  const flush = () => {
    entry.timer = null;
    const waiters = entry.waiters.splice(0);
    const version = entry.version;
    const run = () => performQueuedGigDraftSave(saveKey, version);
    entry.promise = entry.promise.then(run, run);
    entry.promise.then(
      (result) => waiters.forEach((waiter) => waiter.resolve(result)),
      (err) => waiters.forEach((waiter) => waiter.reject(err)),
    );
  };

  if (scheduledDelay > 0) {
    entry.timer = setTimeout(flush, scheduledDelay);
  } else {
    flush();
  }

  return queuedPromise;
}

async function performQueuedGigDraftSave(saveKey, version) {
  const entry = programGigDraftSaveStates.get(saveKey);
  let rawGigIndex = resolveProgramGigDraftIndexForSaveKey(saveKey);
  if (rawGigIndex < 0) return null;
  const originalTargetGig = normalizeGigDraftItem(gigDraft.value[rawGigIndex]);
  const collapsed = collapseDuplicateProgramGigsByExternalKey(gigDraft.value, stageDraft.value);
  const normalizedGigs = collapsed.rows;
  if (collapsed.changed) {
    gigDraft.value = normalizedGigs;
    syncProgramItemPageJobsWithDraft();
    const targetMergeKey = getProgramImportedRowExternalMergeKey(originalTargetGig);
    rawGigIndex = targetMergeKey
      ? normalizedGigs.findIndex((gig) => getProgramImportedRowExternalMergeKey(gig) === targetMergeKey)
      : resolveProgramGigDraftIndexForSaveKey(saveKey);
  }
  const targetGig = normalizedGigs[rawGigIndex];
  if (!targetGig || !String(targetGig.id || "").trim()) return null;

  programCatalogSaveDepth.value += 1;
  try {
    const saveResult = await saveProgramSharedGig(targetGig);
    if (entry && entry.version !== version) {
      return saveResult;
    }
    registerProgramItemPageGenerationJobs(saveResult?.itemPageGenerationJobs);
    if (saveResult?.gig && typeof saveResult.gig === "object") {
      const savedGigId = String(saveResult.gig.id || targetGig.id || "").trim();
      const currentIndex = gigDraft.value.findIndex((gig) =>
        savedGigId && String(gig?.id || "").trim() === savedGigId
      );
      if (currentIndex >= 0) {
        const nextGigs = gigDraft.value.slice();
        nextGigs[currentIndex] = normalizeGigDraftItem(saveResult.gig);
        gigDraft.value = normalizeGigDraftRows(nextGigs, stageDraft.value);
      }
      syncProgramItemPageJobsWithDraft();
    }
    return saveResult;
  } finally {
    programCatalogSaveDepth.value = Math.max(0, programCatalogSaveDepth.value - 1);
  }
}

function clearQueuedGigDraftSaveTimers() {
  programGigDraftSaveStates.forEach((entry) => {
    if (entry?.timer) {
      clearTimeout(entry.timer);
      entry.timer = null;
    }
  });
}

function setGigDateTime(item, fieldName, modelValue) {
  if (!item || typeof item !== "object") return;
  const normalizedFieldName = String(fieldName || "").trim();
  if (!normalizedFieldName) return;
  if (
    isGigChangeDetailsDisabled(item)
    && (normalizedFieldName === "previous_start" || normalizedFieldName === "previous_end")
  ) return;
  let nextValue = "";
  if (modelValue instanceof Date) {
    nextValue = formatGigDateTimeInputValue(modelValue);
  } else if (Array.isArray(modelValue) && modelValue[0] instanceof Date) {
    nextValue = formatGigDateTimeInputValue(modelValue[0]);
  } else if (typeof modelValue === "string") {
    const parsed = parseGigDateTime(modelValue);
    nextValue = parsed ? formatGigDateTimeInputValue(parsed) : normalizeGigDateTimeValue(modelValue);
  }
  item[normalizedFieldName] = nextValue;
  if (normalizedFieldName === "start" && !nextValue) {
    item.day = "";
    item.start_time = "";
  }
  if (normalizedFieldName === "end" && !nextValue) {
    item.end_time = "";
  }
  if (normalizedFieldName === "previous_start" && !nextValue) {
    item.previous_day = "";
    item.previous_start_time = "";
  }
  if (normalizedFieldName === "previous_end" && !nextValue) {
    item.previous_end_time = "";
  }
  syncGigLegacyScheduleFields(item);
  queueSaveGigDraftForItem(item).catch((err) => {
    console.error("Failed to persist gig schedule update:", err);
  });
}

function setGigImageTransform(item, patch = {}) {
  if (!item || typeof item !== "object" || !patch || typeof patch !== "object") return;
  const nextPatch = {};
  if (Object.prototype.hasOwnProperty.call(patch, "image_zoom")) {
    nextPatch.image_zoom = normalizeGigImageZoom(patch.image_zoom);
  }
  if (Object.prototype.hasOwnProperty.call(patch, "image_focal_x")) {
    nextPatch.image_focal_x = normalizeGigImageFocal(patch.image_focal_x);
  }
  if (Object.prototype.hasOwnProperty.call(patch, "image_focal_y")) {
    nextPatch.image_focal_y = normalizeGigImageFocal(patch.image_focal_y);
  }
  if (Object.prototype.hasOwnProperty.call(patch, "image_rotation")) {
    nextPatch.image_rotation = normalizeGigImageRotation(patch.image_rotation);
  }
  if (Object.keys(nextPatch).length === 0) return;
  Object.assign(item, nextPatch);
  queueSaveGigDraftForItem(item).catch((err) => {
    console.error("Failed to persist gig image transform update:", err);
  });
}

function setGigStage(item, rawValue) {
  if (!item || typeof item !== "object") return;
  item.stage = normalizeStageLookupText(rawValue);
}

function setGigPreviousStage(item, rawValue) {
  if (!item || typeof item !== "object") return;
  if (isGigChangeDetailsDisabled(item)) return;
  item.previous_stage = normalizeStageLookupText(rawValue);
  syncGigLegacyScheduleFields(item);
  queueSaveGigDraftForItem(item).catch((err) => {
    console.error("Failed to persist gig previous stage update:", err);
  });
}

function setGigType(item, rawValue) {
  if (!item || typeof item !== "object") return;
  item.gig_type = String(rawValue ?? "").trim();
}

function setGigHighlightChanges(item, checked) {
  if (!item || typeof item !== "object") return;
  if (isGigNewDisabled(item)) return;
  const enabled = Boolean(checked);
  if (enabled) {
    clearGigChangeDetailFields(item);
    item.canceled = false;
  }
  item.highlight_changes = enabled;
  queueSaveGigDraftForItem(item, { delay: 0 }).catch((err) => {
    console.error("Failed to persist gig new-change marker update:", err);
  });
}

function setGigCanceled(item, checked) {
  if (!item || typeof item !== "object") return;
  if (isGigCanceledDisabled(item)) return;
  const enabled = Boolean(checked);
  if (enabled) {
    item.highlight_changes = false;
  }
  item.canceled = enabled;
  queueSaveGigDraftForItem(item, { delay: 0 }).catch((err) => {
    console.error("Failed to persist gig cancellation update:", err);
  });
}

function isGigRegisterChangesEnabled(gig) {
  return Boolean(gig?.register_changes ?? false);
}

function isGigCanceled(gig) {
  return Boolean(gig?.canceled);
}

function isGigNewDisabled(gig) {
  return isGigCanceled(gig);
}

function isGigCanceledDisabled(gig) {
  return isGigNew(gig);
}

function isGigChangeDetailsDisabled(gig) {
  return isGigCanceled(gig) || isGigNew(gig);
}

function setGigRegisterChanges(item, checked) {
  if (!item || typeof item !== "object") return;
  const enabled = Boolean(checked);
  const wasEnabled = isGigRegisterChangesEnabled(item);
  if (enabled) {
    if (!wasEnabled) {
      clearGigChangeDetailFields(item);
    }
    ensureGigChangeBaseline(item);
  } else {
    item.canceled = false;
    item.highlight_changes = false;
    clearGigChangeDetailFields(item);
  }
  item.register_changes = enabled;
  queueSaveGigDraftForItem(item, { delay: 0 }).catch((err) => {
    console.error("Failed to persist gig change-registration update:", err);
  });
}

function getGigDateRange(gig) {
  let start = (
    parseGigDateTime(gig?.start)
    || parseDayTime(gig?.day, gig?.start_time)
  );
  let end = (
    parseGigDateTime(gig?.end)
    || parseDayTime(extractGigDatePart(gig?.start) || gig?.day, gig?.end_time)
  );
  if (!start || !end) return null;
  const debugOffset = Number(programDayDebugOffsetDays.value) || 0;
  if (debugOffset !== 0) {
    start = shiftDateByDays(start, debugOffset);
    end = shiftDateByDays(end, debugOffset);
    if (!start || !end) return null;
  }
  const normalizedEnd = new Date(end.getTime());
  if (normalizedEnd <= start) {
    normalizedEnd.setDate(normalizedEnd.getDate() + 1);
  }
  return { start, end: normalizedEnd };
}

function compareGigStart(a, b) {
  const rangeA = getGigDateRange(a);
  const rangeB = getGigDateRange(b);
  if (!rangeA && !rangeB) return (a.id || "").localeCompare(b.id || "");
  if (!rangeA) return 1;
  if (!rangeB) return -1;
  return rangeA.start.getTime() - rangeB.start.getTime();
}

const sharedProgramHasData = computed(() =>
  Boolean(state.programSharedLoaded)
  || (Array.isArray(state.programSharedStages) && state.programSharedStages.length > 0)
  || (Array.isArray(state.programSharedGigs) && state.programSharedGigs.length > 0)
);
const stages = computed(() => {
  const stageRows = Array.isArray(state.programSharedStages) ? state.programSharedStages : [];
  return stageRows.map((stage) => normalizeStageDraftItem(stage));
});
const gigs = computed(() => {
  const rows = sharedProgramHasData.value
    ? (Array.isArray(state.programSharedGigs) ? state.programSharedGigs : [])
    : (Array.isArray(section.value?.gigs) ? section.value.gigs : []);
  const resolveStageId = buildGigStageIdResolver(stages.value);
  return rows
    .map((row) => normalizeGig(row))
    .map((gig) => ({
      ...gig,
      stage: resolveStageId(gig.stage),
      __source: "shared",
      __base: cloneValue(gig),
      __change: null,
      __canceled: Boolean(gig.canceled),
      __changed: isGigChanged(gig),
    }));
});
const showChanges = computed(() =>
  gigs.value.some((gig) => Boolean(gig.__changed))
);

// Day range settings (e.g., 10:00 to 06:00 next day means events until 6am count as previous day)
const dayStartHour = computed(() => section.value?.dayStartHour ?? 10);
const dayEndHour = computed(() => section.value?.dayEndHour ?? 6);

// Max visible hours before scrolling kicks in (default 6 hours)
const maxVisibleHours = computed(() => section.value?.maxVisibleHours ?? 6);
const defaultGrouping = computed(() => {
  const value = String(readSectionValue("defaultGrouping", "day") || "").trim().toLowerCase();
  return value === "stage" ? "stage" : "day";
});
const fixedStageId = computed(() => String(readSectionValue("fixedStageId", "") || "").trim());
const fixedDay = computed(() => String(readSectionValue("fixedDay", "") || "").trim());
const fixedGigId = computed(() => String(readSectionValue("fixedGigId", "") || "").trim());

function fixedGigLookupTextValues(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return [
      String(value.de || "").trim(),
      String(value.en || "").trim(),
    ].filter(Boolean);
  }
  if (Array.isArray(value)) {
    return value.flatMap((entry) => fixedGigLookupTextValues(entry));
  }
  const text = String(value ?? "").trim();
  return text ? [text] : [];
}

function slugifyFixedGigLookupValue(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .normalize("NFC")
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function fixedGigLookupTokens(value) {
  const tokens = new Set();
  fixedGigLookupTextValues(value).forEach((text) => {
    const normalized = String(text || "").trim().toLowerCase();
    if (normalized) tokens.add(normalized);
    const slug = slugifyFixedGigLookupValue(text);
    if (slug) tokens.add(slug);
  });
  return tokens;
}

function gigFixedLookupTokens(gig) {
  const tokens = new Set();
	  [
	    gig?.id,
	    gig?.integration_item_key,
	    gig?.integrationItemKey,
	    gig?.template_integration_item_key,
	    gig?.templateIntegrationItemKey,
	    gig?.review_item_key,
	    gig?.reviewItemKey,
	    gig?.external_id,
	    gig?.externalId,
	    gig?.title,
	    gig?.artist_name,
	    gig?.artistName,
	    gig?.gig_title,
	    gig?.gigTitle,
	    gig?.name,
	  ].forEach((value) => {
    fixedGigLookupTokens(value).forEach((token) => tokens.add(token));
  });
  return tokens;
}

const selectedFixedGig = computed(() => {
  const wanted = fixedGigId.value;
  if (!wanted) return null;
  const exact = gigs.value.find((gig) => String(gig?.id || "").trim() === wanted);
  if (exact) return exact;
  const wantedTokens = fixedGigLookupTokens(wanted);
  if (wantedTokens.size === 0) return null;
  const matches = gigs.value.filter((gig) => {
    const gigTokens = gigFixedLookupTokens(gig);
    return Array.from(wantedTokens).some((token) => gigTokens.has(token));
  });
  return matches.length === 1 ? matches[0] : null;
});
const fixedGigDay = computed(() => {
  const gig = selectedFixedGig.value;
  if (!gig) return "";
  return String(getLogicalDay(gig) || gig?.day || "").trim();
});
const fixedGigStageId = computed(() => {
  const gig = selectedFixedGig.value;
  if (!gig) return "";
  return String(getGigStage(gig) || "").trim();
});
const effectiveFixedDay = computed(() => fixedGigDay.value || fixedDay.value);
const effectiveFixedStageId = computed(() => fixedGigStageId.value || fixedStageId.value);
const allowGroupToggle = computed(() => readSectionValue("allowGroupToggle", true) !== false);
const allowDaySelection = computed(() => readSectionValue("allowDaySelection", true) !== false);
const allowStageFilter = computed(() => readSectionValue("allowStageFilter", true) !== false);
const showViewToggle = computed(() => readSectionValue("showViewToggle", true) !== false);
const showListItemBackgroundImages = computed(() => readSectionValue("showListItemBackgroundImages", true) !== false);
const showDaySelectionTabs = computed(() => (
  !isNowView.value && groupBy.value === "day" && allowDaySelection.value && !hasFixedDaySelection.value
));
const showStageSelectionTabs = computed(() => (
  !isNowView.value && groupBy.value === "stage" && !hasFixedStageSelection.value
));
const showStageFilterPills = computed(() => (
  !isNowView.value && groupBy.value === "day" && allowStageFilter.value && !hasFixedStageSelection.value
));
const showProgramSelectionBar = computed(() => (
  !isChangesView.value && (
    showDaySelectionTabs.value
    || showStageSelectionTabs.value
    || showStageFilterPills.value
  )
));
const showProgramControlBar = computed(() => (
  !isChangesView.value && (
    (allowGroupToggle.value && !isNowView.value)
    || showViewToggle.value
  )
));
const showGigDescriptionButton = computed(() => readSectionValue("showGigDescriptionButton", false) === true);
const defaultViewMode = computed(() => {
  const value = String(readSectionValue("defaultViewMode", "gantt") || "").trim().toLowerCase();
  if (value === "timeline") return "timeline";
  if (value === "changes") return "changes";
  if (value === "now") return "now";
  return "gantt";
});
const showViewConfigScopeControls = computed(() =>
  defaultViewMode.value !== "changes" && defaultViewMode.value !== "now"
);
const showFixedGigConfig = computed(() =>
  showViewConfigScopeControls.value && defaultViewMode.value === "gantt"
);
const hasFixedGigFocus = computed(() => Boolean(selectedFixedGig.value));
const showGanttViewButton = computed(() => !isMobileView.value || hasFixedGigFocus.value);
const hasFixedStageSelection = computed(() => Boolean(effectiveFixedStageId.value));
const hasFixedDaySelection = computed(() => Boolean(effectiveFixedDay.value));
const viewMode = ref("gantt");

// Check if we're in mobile view
const isMobileView = computed(() => effectiveResponsiveDevice.value === 'mobile');

// Mobile visitors only render gantt for fixed gig focus views.
const effectiveViewMode = computed(() => {
  const normalized = String(viewMode.value || "").trim().toLowerCase();
  if (normalized !== "gantt" && normalized !== "timeline" && normalized !== "now" && normalized !== "changes") {
    return "timeline";
  }
  if (isMobileView.value && normalized === "gantt" && !hasFixedGigFocus.value) return "timeline";
  return normalized;
});
const isChangesView = computed(() => effectiveViewMode.value === "changes");
const isNowView = computed(() => effectiveViewMode.value === "now");
const isGigPopupMode = computed(() => (
  effectiveViewMode.value === "gantt" || effectiveViewMode.value === "timeline"
));

// Effective visible hours follows section config; longer ranges scroll horizontally.
const effectiveVisibleHours = computed(() => maxVisibleHours.value);

// Calculate total hours in the current visible range (based on actual events)
const totalDayHours = computed(() => {
  const range = groupBy.value === "stage" ? timeRangeForStage.value : timeRange.value;
  return range.end - range.start;
});

// Whether the gantt chart should scroll
const ganttShouldScroll = computed(() => totalDayHours.value > effectiveVisibleHours.value);

// Width multiplier for scrollable content
const ganttWidthPercent = computed(() => {
  if (!ganttShouldScroll.value) return 100;
  return (totalDayHours.value / effectiveVisibleHours.value) * 100;
});

// Helper to format a date as YYYY-MM-DD without timezone conversion
function formatDateLocal(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// Helper to subtract days from a date string (YYYY-MM-DD) without timezone issues
function subtractDays(dateStr, days) {
  const [year, month, day] = dateStr.split('-').map(Number);
  const date = new Date(year, month - 1, day); // month is 0-indexed
  date.setDate(date.getDate() - days);
  return formatDateLocal(date);
}

const currentProgramDay = computed(() => {
  nowTimestamp.value;
  const now = getCurrentServerWallDate();
  const calendarDay = formatDateLocal(now);
  const startHour = dayStartHour.value;
  const endHour = dayEndHour.value;
  const effectiveEndHour = endHour > 24 ? endHour - 24 : endHour;
  const dayWraps = endHour > 24 || endHour <= startHour;
  if (dayWraps && now.getHours() < effectiveEndHour) {
    return subtractDays(calendarDay, 1);
  }
  return calendarDay;
});

function applyProgramDayDebugOffset(dayValue) {
  const day = String(dayValue || "").trim();
  const offset = Number(programDayDebugOffsetDays.value) || 0;
  if (!day || offset === 0) return day;
  return shiftDateOnlyValueByDays(day, offset);
}

// Helper to get the stored "logical day" for a gig based on day range settings.
function getBaseLogicalDay(gig) {
  const gigDay = extractGigDatePart(gig?.start) || String(gig?.day || "").trim();
  const gigStartTime = extractGigTimePart(gig?.start) || String(gig?.start_time || "").trim();
  if (!gigDay || !gigStartTime) return gigDay;
  
  const startHour = dayStartHour.value;
  const endHour = dayEndHour.value;
  
  // Parse the gig's start time
  const [hourStr] = gigStartTime.split(":");
  const gigHour = parseInt(hourStr, 10);
  
  // Calculate effective end hour (accounting for next-day values > 24)
  const effectiveEndHour = endHour > 24 ? endHour - 24 : endHour;
  const dayWraps = endHour > 24 || endHour <= startHour;
  
  // If day wraps past midnight (e.g., 12:00 to 06:00 or using 30 for 06:00+1)
  if (dayWraps) {
    // If gig is in the early morning hours (before effective end hour), it belongs to previous day
    if (gigHour < effectiveEndHour) {
      return subtractDays(gigDay, 1);
    }
    // If gig is before start hour but after effective end hour, it's in a gap - use original day
    if (gigHour < startHour && gigHour >= effectiveEndHour) {
      return gigDay;
    }
  } else {
    // Normal day range (e.g., 00:00 to 24:00 or 08:00 to 20:00)
    // If gig is before start hour, it might belong to previous day
    if (gigHour < startHour && startHour > 0) {
      return subtractDays(gigDay, 1);
    }
  }
  
  return gigDay;
}

function getLogicalDay(gig) {
  return applyProgramDayDebugOffset(getBaseLogicalDay(gig));
}

// Local state
const selectedDay = ref(null);
const selectedDayManuallySelected = ref(false);
const selectedStage = ref(null);
const expandedGig = ref(null);
const closingGig = ref(null);
const filterStage = ref(null);
const groupBy = ref("day");
const stageDetailOpen = ref(null);
const expandedGigDescriptionOpen = ref(false);
let closeGigTimer = null;

const PROGRAM_GIG_POPUP_BODY_CLASS = "program-gig-popup-open";

function syncProgramGigPopupBodyClass(isOpen) {
  if (typeof document === "undefined") return;
  document.body.classList.toggle(PROGRAM_GIG_POPUP_BODY_CLASS, Boolean(isOpen));
}

const showGigPopupBackdrop = computed(() => Boolean(expandedGig.value && isGigPopupMode.value));

watch(showGigPopupBackdrop, (isOpen) => syncProgramGigPopupBodyClass(isOpen), { immediate: true });

onUnmounted(() => {
  syncProgramGigPopupBodyClass(false);
  if (closeGigTimer) clearTimeout(closeGigTimer);
  clearQueuedGigDraftSaveTimers();
  clearGigPageAvailabilityTimer();
  for (const timer of programItemPagePollTimers.values()) {
    clearTimeout(timer);
  }
  programItemPagePollTimers.clear();
});

// Data management state
const stageItemPagesBusy = ref(false);
const gigItemPagesBusy = ref(false);
const stageItemPagesStatus = ref({ type: "", message: "" });
const gigItemPagesStatus = ref({ type: "", message: "" });
const programDuplicateIdWarning = ref({ message: "", stages: [], gigs: [] });
const programGlobalConfig = ref({});
const programStageTemplateInfo = ref(null);
const programGigTemplateInfo = ref(null);
const programItemPageJobs = ref({
  stage: {},
  gig: {},
});
const programItemTemplateRegenerationBusy = ref({
  stage: {},
  gig: {},
});
const settingTodayAsProgramDay = ref(false);
const dayRangeDebugStatus = ref({ type: "", message: "" });
const programDayDebugOffsetDays = ref(0);
const programItemPagePollTimers = new Map();
const PROGRAM_ITEM_JOB_POLL_INTERVAL_MS = 1200;
const PROGRAM_ITEM_JOB_POLL_MAX_ATTEMPTS = 90;

// List editor state
const stageDraft = ref([]);
const selectedStageDraftIndex = ref(-1);
const showStageMediaPicker = ref(false);
const stageMediaPickerTargetIndex = ref(-1);
const stageMediaPickerCurrentUrl = computed(() => {
  const index = stageMediaPickerTargetIndex.value;
  if (index < 0 || index >= stageDraft.value.length) return "";
  return String(stageDraft.value[index]?.image_url || "").trim();
});
const gigDraft = ref([]);
const selectedGigDraftIndex = ref(-1);
const programCatalogSaveDepth = ref(0);
let programCatalogSaveQueue = Promise.resolve();
let programCatalogSaveRequestId = 0;
const PROGRAM_GIG_DRAFT_SAVE_DELAY_MS = 220;
const programGigDraftSaveStates = new Map();
const PROGRAM_STAGE_COLOR_SAVE_DELAY_MS = 220;
let stageColorDesignSaveTimer = null;
let stageColorDesignSaveRunId = 0;
const gigEditorDayFilter = ref("");
const gigEditorStageFilter = ref("");
const gigEditorTypeFilter = ref("");
const gigEditorItemPageFilter = ref("");
const gigPagePublicAvailability = ref({});
let gigPageAvailabilityTimer = null;
let gigPageAvailabilityRequestSeq = 0;
watch(
  [stageDraft, gigDraft],
  ([nextStages, nextGigs]) => {
    const duplicates = resolveProgramDuplicateIds(nextStages, nextGigs);
    if (duplicates.stages.length || duplicates.gigs.length) {
      setProgramDuplicateIdWarning(duplicates.stages, duplicates.gigs);
      return;
    }
    clearProgramDuplicateIdWarning();
  },
  { deep: true }
);

function setGroupBy(value) {
  if (!allowGroupToggle.value) return;
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized !== "day" && normalized !== "stage") return;
  groupBy.value = normalized;
}

function selectProgramDay(day) {
  selectedDayManuallySelected.value = true;
  selectedDay.value = day;
}

function normalizeParentRoutePath(value, fallback = "/") {
  const raw = String(value || "").trim();
  if (!raw) return fallback;
  const normalized = raw.replace(/^\/+|\/+$/g, "");
  if (!normalized) return "/";
  return `/${normalized}`;
}

function normalizeItemPageSubroutePath(value) {
  const raw = String(value || "").trim();
  if (!raw || raw === "/") return "";
  const normalized = raw.replace(/^\/+|\/+$/g, "");
  return normalized ? `/${normalized}` : "";
}

function composeEffectiveItemRoute(parentRoute, subroute = "") {
  const parent = normalizeParentRoutePath(parentRoute, "");
  if (!parent) return "";
  const child = normalizeItemPageSubroutePath(subroute);
  return child ? `${parent}${child}` : parent;
}

function resolveProgramTemplateInfoForKind(kind) {
  const normalizedKind = normalizeProgramItemPageKind(kind);
  return normalizedKind === "stage" ? programStageTemplateInfo.value : programGigTemplateInfo.value;
}

function resolveProgramParentRouteForKind(kind) {
  const info = resolveProgramTemplateInfoForKind(kind);
  return normalizeParentRoutePath(info?.effectiveRoute || info?.parentRoute || "", "/");
}

async function loadProgramItemTemplateInfo() {
  try {
    const config = await api.getGlobalItemPageConfig();
    programGlobalConfig.value = config || {};
    const loadOne = async (key) => {
      const path = String(config?.[key] || "").trim();
      if (!path) return null;
      const template = await api.getPageTemplate(path);
      const parentRoute = normalizeParentRoutePath(template?.parent_route || "", "");
      const effectiveRoute = composeEffectiveItemRoute(parentRoute, template?.item_page_subroute || "");
      return {
        path: String(template?.path || path).trim(),
        parentRoute,
        effectiveRoute,
      };
    };
    programStageTemplateInfo.value = await loadOne("program_stage_template_path");
    programGigTemplateInfo.value = await loadOne("program_gig_template_path");
  } catch (err) {
    console.error("Failed to load program item template info:", err);
    programStageTemplateInfo.value = null;
    programGigTemplateInfo.value = null;
  }
}

function resolveGeneratedItemUrl(item) {
  const direct = String(item?.item_url || "").trim();
  if (direct) {
    return direct.startsWith("/") ? direct : `/${direct.replace(/^\/+/, "")}`;
  }
  const slug = String(item?.page_slug || "").trim().replace(/^\/+/, "");
  if (!slug) return "";
  return `/${slug}`;
}

function openGeneratedItemPage(item) {
  const resolvedUrl = resolveGeneratedItemUrl(item);
  if (!resolvedUrl) return;
  if (typeof window === "undefined") return;
  window.open(resolvedUrl, "_blank", "noopener,noreferrer");
}

function resolveGigItemPageStatus(gig) {
  const slug = resolveProgramGigPageSlug(gig);
  if (!slug) return "not_created";
  return gigPagePublicAvailability.value[slug] === true ? "published" : "hidden";
}

function hasGeneratedGigItemPage(gig) {
  return Boolean(resolveGeneratedItemUrl(gig));
}

function isGeneratedGigItemPagePublic(gig) {
  return resolveGigItemPageStatus(gig) === "published";
}

function isGigPopupMoreButtonEnabled(gig) {
  if (!hasGeneratedGigItemPage(gig)) return false;
  if (isGeneratedGigItemPagePublic(gig)) return true;
  return Boolean(state.isAdmin);
}

function getGigPopupMoreButtonLabel(gig) {
  if (!hasGeneratedGigItemPage(gig)) return t.value.moreUnavailable;
  if (isGeneratedGigItemPagePublic(gig)) return t.value.more;
  return state.isAdmin ? t.value.moreHiddenAdmin : t.value.moreHiddenPublic;
}

function getGigPopupMoreButtonAriaLabel(gig) {
  if (!hasGeneratedGigItemPage(gig)) return t.value.moreUnavailableLabel;
  if (isGeneratedGigItemPagePublic(gig)) return t.value.more;
  return state.isAdmin ? t.value.moreHiddenAdminLabel : t.value.moreHiddenPublicLabel;
}

function getGigPopupMoreButtonTitle(gig) {
  return getGigPopupMoreButtonAriaLabel(gig);
}

function showGigPopupMoreButton(gig) {
  return isGigPopupMoreButtonEnabled(gig);
}

function clearGigPageAvailabilityTimer() {
  if (gigPageAvailabilityTimer) {
    clearTimeout(gigPageAvailabilityTimer);
    gigPageAvailabilityTimer = null;
  }
}

async function refreshGigPageAvailability(slugs = []) {
  const normalizedSlugs = Array.isArray(slugs)
    ? slugs.map((slug) => normalizeProgramGigPageSlugValue(slug)).filter(Boolean)
    : [];
  const requestSeq = gigPageAvailabilityRequestSeq + 1;
  gigPageAvailabilityRequestSeq = requestSeq;

  if (!normalizedSlugs.length) {
    gigPagePublicAvailability.value = {};
    return;
  }

  try {
    const availability = await api.getPublicPagesAvailability(normalizedSlugs);
    if (requestSeq !== gigPageAvailabilityRequestSeq) return;
    gigPagePublicAvailability.value = availability && typeof availability === "object"
      ? availability
      : {};
  } catch (err) {
    if (requestSeq !== gigPageAvailabilityRequestSeq) return;
    console.error("Failed to load program gig item-page availability:", err);
    gigPagePublicAvailability.value = {};
  }
}

function queueGigPageAvailabilityRefresh(slugs = []) {
  clearGigPageAvailabilityTimer();
  const normalizedSlugs = Array.isArray(slugs)
    ? slugs.map((slug) => normalizeProgramGigPageSlugValue(slug)).filter(Boolean)
    : [];
  gigPageAvailabilityTimer = setTimeout(() => {
    gigPageAvailabilityTimer = null;
    void refreshGigPageAvailability(normalizedSlugs);
  }, 120);
}

function resolveProgramSectionId() {
  return String(
    state.sectionIds?.[effectiveKey.value]
    || section.value?._id
    || section.value?.id
    || ""
  ).trim();
}

function normalizeProgramItemPageKind(kind) {
  const normalized = String(kind || "").trim().toLowerCase();
  return normalized === "stage" ? "stage" : "gig";
}

function collectDuplicateIdsFromRows(rows = []) {
  const seen = new Set();
  const duplicates = new Set();
  for (const row of Array.isArray(rows) ? rows : []) {
    const itemId = String(row?.id || "").trim();
    if (!itemId) continue;
    if (seen.has(itemId)) {
      duplicates.add(itemId);
      continue;
    }
    seen.add(itemId);
  }
  return Array.from(duplicates.values()).sort();
}

function resolveProgramDuplicateIds(stagesRows = [], gigsRows = []) {
  return {
    stages: collectDuplicateIdsFromRows(stagesRows),
    gigs: collectDuplicateIdsFromRows(gigsRows),
  };
}

function buildProgramDuplicateIdWarningMessage(stages = [], gigs = []) {
  const stageIds = Array.isArray(stages) ? stages : [];
  const gigIds = Array.isArray(gigs) ? gigs : [];
  if (!stageIds.length && !gigIds.length) return "";
  const parts = [];
  if (stageIds.length) {
    parts.push(`Stages: ${stageIds.join(", ")}`);
  }
  if (gigIds.length) {
    parts.push(`Gigs: ${gigIds.join(", ")}`);
  }
  return `Duplicate item IDs block saving. ${parts.join(" | ")}`;
}

function setProgramDuplicateIdWarning(stages = [], gigs = []) {
  programDuplicateIdWarning.value = {
    message: buildProgramDuplicateIdWarningMessage(stages, gigs),
    stages: Array.isArray(stages) ? stages : [],
    gigs: Array.isArray(gigs) ? gigs : [],
  };
}

function clearProgramDuplicateIdWarning() {
  programDuplicateIdWarning.value = { message: "", stages: [], gigs: [] };
}

function parseProgramDuplicateIdError(err) {
  const detail = err?.detail_payload;
  if (!detail || typeof detail !== "object") return null;
  if (String(detail.code || "").trim() !== "duplicate_program_item_ids") return null;
  const stages = Array.isArray(detail.stages)
    ? detail.stages.map((id) => String(id || "").trim()).filter(Boolean)
    : [];
  const gigs = Array.isArray(detail.gigs)
    ? detail.gigs.map((id) => String(id || "").trim()).filter(Boolean)
    : [];
  return { stages, gigs };
}

function isDuplicateStageId(value) {
  const itemId = String(value || "").trim();
  if (!itemId) return false;
  return (programDuplicateIdWarning.value.stages || []).includes(itemId);
}

function isDuplicateGigId(value) {
  const itemId = String(value || "").trim();
  if (!itemId) return false;
  return (programDuplicateIdWarning.value.gigs || []).includes(itemId);
}

function setProgramItemTemplateRegenerationBusy(kind, itemId, isBusy) {
  const normalizedKind = normalizeProgramItemPageKind(kind);
  const normalizedItemId = String(itemId || "").trim();
  if (!normalizedItemId) return;
  const nextState = {
    stage: { ...(programItemTemplateRegenerationBusy.value.stage || {}) },
    gig: { ...(programItemTemplateRegenerationBusy.value.gig || {}) },
  };
  if (isBusy) {
    nextState[normalizedKind][normalizedItemId] = true;
  } else {
    delete nextState[normalizedKind][normalizedItemId];
  }
  programItemTemplateRegenerationBusy.value = nextState;
}

function isProgramItemTemplateRegenerationBusy(kind, item) {
  const normalizedKind = normalizeProgramItemPageKind(kind);
  const itemId = resolveProgramItemId(item);
  if (!itemId) return false;
  return Boolean(programItemTemplateRegenerationBusy.value?.[normalizedKind]?.[itemId]);
}

function showProgramItemRegenerateButton(kind, item) {
  return Boolean(resolveProgramItemId(item)) && Boolean(item?.item_page_template_outdated);
}

function programItemPageInfoMessage(kind, item) {
  const normalizedKind = normalizeProgramItemPageKind(kind);
  const label = normalizedKind === "stage" ? "stage" : "gig";
  if (item?.item_page_missing) {
    return `Linked ${label} item page is missing. Save to auto-regenerate it.`;
  }
  if (item?.item_page_template_outdated && item?.item_page_mapped_fields_synced) {
    return "Mapped fields are synced. Regenerate to include non-mapped template updates.";
  }
  if (item?.item_page_template_outdated && !item?.item_page_mapped_fields_synced) {
    return "Mapped fields are still stale. Saving will queue an async mapped-field refresh.";
  }
  return "";
}

function programItemPageInfoTone(kind, item) {
  void kind;
  if (item?.item_page_missing) return "warning";
  if (item?.item_page_template_outdated && !item?.item_page_mapped_fields_synced) return "warning";
  return "info";
}

async function regenerateProgramItemPage(kind, item) {
  const normalizedKind = normalizeProgramItemPageKind(kind);
  const itemId = resolveProgramItemId(item);
  if (!itemId) return;
  if (isProgramItemTemplateRegenerationBusy(normalizedKind, item)) return;

  const sectionId = resolveProgramSectionId();
  if (!sectionId) {
    const statusRef = normalizedKind === "stage" ? stageItemPagesStatus : gigItemPagesStatus;
    statusRef.value = {
      type: "error",
      message: "Section ID not found. Please reload the page.",
    };
    return;
  }

  const statusRef = normalizedKind === "stage" ? stageItemPagesStatus : gigItemPagesStatus;
  const itemKind = normalizedKind === "stage" ? "stage" : "gig";
  setProgramItemTemplateRegenerationBusy(normalizedKind, itemId, true);
  try {
    await persistProgramCatalog({
      stages: normalizeStageDraftRows(stageDraft.value),
      gigs: normalizeGigDraftRows(gigDraft.value, stageDraft.value),
    });
    await api.generateSectionItemPages(sectionId, {
      itemKind,
      itemId,
      forceRebuild: true,
    });
    const result = await fetchProgramSharedData();
    registerProgramItemPageGenerationJobs(result?.itemPageGenerationJobs);
    statusRef.value = {
      type: "success",
	      message: `Regenerated item page for "${localizedText(gigTitle(item)) || localizedText(item?.name) || itemId}".`,
    };
  } catch (err) {
    console.error("Failed to regenerate program item page:", err);
    statusRef.value = {
      type: "error",
      message: err?.message || "Failed to regenerate item page.",
    };
  } finally {
    setProgramItemTemplateRegenerationBusy(normalizedKind, itemId, false);
  }
}

function resolveProgramItemId(item) {
  return String(item?.id || "").trim();
}

function resolveProgramJobItemId(job) {
  const sourceId = String(job?.source_id || "").trim();
  if (sourceId) {
    if (sourceId.startsWith("program:stage:")) return sourceId.replace("program:stage:", "").trim();
    if (sourceId.startsWith("program:gig:")) return sourceId.replace("program:gig:", "").trim();
    return sourceId;
  }
  const sourceKey = String(job?.source_key || "").trim();
  if (sourceKey.startsWith("program:stage:")) return sourceKey.replace("program:stage:", "").trim();
  if (sourceKey.startsWith("program:gig:")) return sourceKey.replace("program:gig:", "").trim();
  return "";
}

function resolveProgramJobKind(job) {
  const sourceType = String(job?.source_type || "").trim().toLowerCase();
  return sourceType === "program_stage" ? "stage" : "gig";
}

function clearProgramItemPagePollTimer(kind, itemId) {
  const normalizedKind = normalizeProgramItemPageKind(kind);
  const normalizedItemId = String(itemId || "").trim();
  if (!normalizedItemId) return;
  const key = `${normalizedKind}:${normalizedItemId}`;
  const timer = programItemPagePollTimers.get(key);
  if (timer) {
    clearTimeout(timer);
    programItemPagePollTimers.delete(key);
  }
}

function setProgramItemPageJob(kind, itemId, job) {
  const normalizedKind = normalizeProgramItemPageKind(kind);
  const normalizedItemId = String(itemId || "").trim();
  if (!normalizedItemId) return;
  const nextState = {
    stage: { ...(programItemPageJobs.value.stage || {}) },
    gig: { ...(programItemPageJobs.value.gig || {}) },
  };
  nextState[normalizedKind][normalizedItemId] = {
    ...(nextState[normalizedKind][normalizedItemId] || {}),
    ...(job || {}),
  };
  programItemPageJobs.value = nextState;
}

function getProgramItemPageJob(kind, item) {
  const normalizedKind = normalizeProgramItemPageKind(kind);
  const itemId = resolveProgramItemId(item);
  if (!itemId) return null;
  return programItemPageJobs.value?.[normalizedKind]?.[itemId] || null;
}

function isProgramItemPageGenerationPending(kind, item) {
  const job = getProgramItemPageJob(kind, item);
  const status = String(job?.status || "").trim().toLowerCase();
  return status === "queued" || status === "running";
}

function programItemPageGenerationError(kind, item) {
  const job = getProgramItemPageJob(kind, item);
  const status = String(job?.status || "").trim().toLowerCase();
  if (status !== "failed") return "";
  return String(job?.error || "Item page generation failed.").trim();
}

function applyProgramItemPageSlug(kind, itemId, slug) {
  const normalizedKind = normalizeProgramItemPageKind(kind);
  const normalizedItemId = String(itemId || "").trim();
  const normalizedSlug = String(slug || "").trim();
  if (!normalizedItemId || !normalizedSlug) return;
  const rows = normalizedKind === "stage" ? stageDraft.value : gigDraft.value;
  for (const row of rows) {
    if (String(row?.id || "").trim() !== normalizedItemId) continue;
    row.page_slug = normalizedSlug;
    row.item_url = `/${normalizedSlug}`;
  }
}

async function pollProgramItemPageGenerationJob(kind, itemId, jobId, attempt = 0) {
  const normalizedKind = normalizeProgramItemPageKind(kind);
  const normalizedItemId = String(itemId || "").trim();
  const normalizedJobId = String(jobId || "").trim();
  if (!normalizedItemId || !normalizedJobId) return;
  try {
    const result = await api.getSectionItemPageGenerationJob(normalizedJobId);
    setProgramItemPageJob(normalizedKind, normalizedItemId, result);
    const status = String(result?.status || "").trim().toLowerCase();
    const slug = String(result?.slug || "").trim();
    if (slug) {
      applyProgramItemPageSlug(normalizedKind, normalizedItemId, slug);
    }
    if (status === "completed" || status === "failed") {
      clearProgramItemPagePollTimer(normalizedKind, normalizedItemId);
      return;
    }
  } catch (err) {
    console.error("Failed to poll program item-page generation job:", err);
  }

  if (attempt >= PROGRAM_ITEM_JOB_POLL_MAX_ATTEMPTS) {
    clearProgramItemPagePollTimer(normalizedKind, normalizedItemId);
    return;
  }
  clearProgramItemPagePollTimer(normalizedKind, normalizedItemId);
  const key = `${normalizedKind}:${normalizedItemId}`;
  const timer = setTimeout(() => {
    programItemPagePollTimers.delete(key);
    void pollProgramItemPageGenerationJob(normalizedKind, normalizedItemId, normalizedJobId, attempt + 1);
  }, PROGRAM_ITEM_JOB_POLL_INTERVAL_MS);
  programItemPagePollTimers.set(key, timer);
}

function registerProgramItemPageGenerationJobs(jobs = []) {
  const rows = Array.isArray(jobs) ? jobs : [];
  for (const job of rows) {
    const itemId = resolveProgramJobItemId(job);
    const kind = resolveProgramJobKind(job);
    const jobId = String(job?.job_id || "").trim();
    if (!itemId || !jobId) continue;
    setProgramItemPageJob(kind, itemId, job);
    const slug = String(job?.slug || "").trim();
    if (slug) {
      applyProgramItemPageSlug(kind, itemId, slug);
    }
    void pollProgramItemPageGenerationJob(kind, itemId, jobId, 0);
  }
}

function syncProgramItemPageJobsWithDraft() {
  const stageIds = new Set(stageDraft.value.map((row) => String(row?.id || "").trim()).filter(Boolean));
  const gigIds = new Set(gigDraft.value.map((row) => String(row?.id || "").trim()).filter(Boolean));
  const nextJobs = {
    stage: {},
    gig: {},
  };
  const nextTemplateRegenerationBusy = {
    stage: {},
    gig: {},
  };

  for (const [itemId, job] of Object.entries(programItemPageJobs.value.stage || {})) {
    const normalizedId = String(itemId || "").trim();
    if (!stageIds.has(normalizedId)) {
      clearProgramItemPagePollTimer("stage", normalizedId);
      continue;
    }
    nextJobs.stage[normalizedId] = job;
    if (programItemTemplateRegenerationBusy.value.stage?.[normalizedId]) {
      nextTemplateRegenerationBusy.stage[normalizedId] = true;
    }
  }
  for (const [itemId, job] of Object.entries(programItemPageJobs.value.gig || {})) {
    const normalizedId = String(itemId || "").trim();
    if (!gigIds.has(normalizedId)) {
      clearProgramItemPagePollTimer("gig", normalizedId);
      continue;
    }
    nextJobs.gig[normalizedId] = job;
    if (programItemTemplateRegenerationBusy.value.gig?.[normalizedId]) {
      nextTemplateRegenerationBusy.gig[normalizedId] = true;
    }
  }
  programItemPageJobs.value = nextJobs;
  programItemTemplateRegenerationBusy.value = nextTemplateRegenerationBusy;
}

function hasGigPublicSlugTitle(gig) {
  const title = gigTitle(gig);
  const titleDe = String(title.de || "").trim();
  const titleEn = String(title.en || "").trim();
  return Boolean(titleDe || titleEn);
}

async function runProgramItemPageAction(kind, action) {
  void action;
  const normalizedKind = String(kind || "").trim().toLowerCase();
  if (normalizedKind !== "stage" && normalizedKind !== "gig") return;
  const busyRef = normalizedKind === "stage" ? stageItemPagesBusy : gigItemPagesBusy;
  const statusRef = normalizedKind === "stage" ? stageItemPagesStatus : gigItemPagesStatus;
  if (busyRef.value) return;

  const sectionId = resolveProgramSectionId();
  if (!sectionId) {
    statusRef.value = {
      type: "error",
      message: "Section ID not found. Please reload the page.",
    };
    return;
  }

  busyRef.value = true;
  statusRef.value = { type: "", message: "" };
  try {
    await saveSectionByKey(effectiveKey.value, { revisionKind: "content" });
    const itemKind = normalizedKind === "gig" ? "gig" : "stage";
    const result = await api.cleanupSectionItemPages(sectionId, { itemKind });
    await fetchProgramSharedData();
    const removedCount = Number(result?.removed_count || 0);
    const parentRoute = normalizeParentRoutePath(
      result?.parent_route || resolveProgramParentRouteForKind(normalizedKind),
      "/"
    );
    statusRef.value = {
      type: "success",
      message: `Cleaned up ${removedCount} generated page${removedCount === 1 ? "" : "s"} under route "${parentRoute}".`,
    };
  } catch (err) {
    console.error("Failed to run program item-page action:", err);
    statusRef.value = {
      type: "error",
      message: err?.message || "Failed to run item-page action.",
    };
  } finally {
    busyRef.value = false;
  }
}

function setViewMode(value) {
  if (!showViewToggle.value) return;
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized !== "gantt" && normalized !== "timeline" && normalized !== "now") return;
  viewMode.value = normalized;
}

function setDefaultGrouping(value) {
  const normalized = String(value || "").trim().toLowerCase();
  const nextGrouping = normalized === "stage" ? "stage" : "day";
  const patch = {
    defaultGrouping: nextGrouping,
    fixedGigId: "",
  };
  if (nextGrouping === "day") {
    patch.fixedStageId = "";
  } else {
    patch.fixedDay = "";
  }
  updateSection(
    effectiveKey.value,
    patch,
    { revisionKind: "design" }
  );
}

function setFixedStageId(value) {
  updateSection(
    effectiveKey.value,
    { fixedStageId: String(value || "").trim(), fixedGigId: "" },
    { revisionKind: "design" }
  );
}

function setFixedDay(modelValue, options = {}) {
  let next = "";
  if (modelValue instanceof Date) {
    next = formatDateOnlyValue(modelValue);
  } else if (Array.isArray(modelValue) && modelValue[0] instanceof Date) {
    next = formatDateOnlyValue(modelValue[0]);
  } else if (typeof modelValue === "string") {
    const parsed = parseDateOnlyValue(modelValue);
    next = parsed ? formatDateOnlyValue(parsed) : "";
  }
  const patch = { fixedDay: next };
  if (options.clearFixedGig !== false) patch.fixedGigId = "";
  updateSection(
    effectiveKey.value,
    patch,
    { revisionKind: "design" }
  );
}

function setFixedGigId(value) {
  const nextId = String(value || "").trim();
  const patch = { fixedGigId: nextId };
  if (nextId) {
    patch.fixedDay = "";
    patch.fixedStageId = "";
  }
  updateSection(
    effectiveKey.value,
    patch,
    { revisionKind: "design" }
  );
}

function fixedGigOptionLabel(gig) {
  const value = String(gig?.id || "").trim();
  const day = String(getLogicalDay(gig) || gig?.day || "").trim();
  const stageLabel = getStageName(getGigStage(gig));
  const gigLabel = localizedText(gigTitle(gig)) || value;
  const timeLabel = [formatDayName(day), gig?.start_time].filter(Boolean).join(" ");
  const contextLabel = [timeLabel, stageLabel].filter(Boolean).join(" - ");
  return contextLabel ? `${gigLabel} (${contextLabel})` : gigLabel;
}

function setAllowGroupToggle(checked) {
  updateSection(
    effectiveKey.value,
    { allowGroupToggle: Boolean(checked) },
    { revisionKind: "design" }
  );
}

function setAllowDaySelection(checked) {
  updateSection(
    effectiveKey.value,
    { allowDaySelection: Boolean(checked) },
    { revisionKind: "design" }
  );
}

function setAllowStageFilter(checked) {
  updateSection(
    effectiveKey.value,
    { allowStageFilter: Boolean(checked) },
    { revisionKind: "design" }
  );
}

function setShowViewToggle(checked) {
  updateSection(
    effectiveKey.value,
    { showViewToggle: Boolean(checked) },
    { revisionKind: "design" }
  );
}

function setShowGigDescriptionButton(checked) {
  const next = Boolean(checked);
  if (!next) {
    expandedGigDescriptionOpen.value = false;
  }
  updateSection(
    effectiveKey.value,
    { showGigDescriptionButton: next },
    { revisionKind: "design" }
  );
}

function setShowListItemBackgroundImages(checked) {
  updateSection(
    effectiveKey.value,
    { showListItemBackgroundImages: Boolean(checked) },
    { revisionKind: "design" }
  );
}

function setDefaultViewMode(value) {
  const normalized = String(value || "").trim().toLowerCase();
  const nextMode = normalized === "timeline"
    ? "timeline"
    : normalized === "changes"
      ? "changes"
      : normalized === "now"
        ? "now"
        : "gantt";
  updateSection(
    effectiveKey.value,
    { defaultViewMode: nextMode },
    { revisionKind: "design" }
  );
}

// Computed: unique sorted days (using logical day based on day range settings)
const sortedDays = computed(() => {
  const days = new Set(gigs.value.map((g) => getLogicalDay(g)).filter(Boolean));
  return Array.from(days).sort();
});

const firstDay = computed(() => sortedDays.value[0] || "");

const currentSelectableProgramDay = computed(() => {
  if (!allowDaySelection.value || hasFixedDaySelection.value) return "";
  const day = currentProgramDay.value;
  return sortedDays.value.includes(day) ? day : "";
});

const fixedDayOptions = computed(() => {
  const days = Array.isArray(sortedDays.value) ? [...sortedDays.value] : [];
  const currentFixedDay = String(fixedDay.value || "").trim();
  if (currentFixedDay && !days.includes(currentFixedDay)) {
    days.push(currentFixedDay);
  }
  return days.sort();
});

const viewConfigDayValue = computed(() => {
  return fixedDay.value;
});

const changedGigGroups = computed(() => {
  const stageLabelById = new Map(
    stages.value.map((stage) => {
      const stageId = String(stage?.id || "").trim();
      const stageLabel = localizedText(stage?.name) || stageId || "Unknown stage";
      return [stageId, stageLabel];
    })
  );

  const dayMap = new Map();
  gigs.value
    .filter((gig) => isGigChanged(gig))
    .forEach((gig) => {
      const day = String(getLogicalDay(gig) || gig?.day || "").trim() || "unknown";
      const stageId = String(getGigStage(gig) || "").trim() || "__unassigned";

      let dayEntry = dayMap.get(day);
      if (!dayEntry) {
        dayEntry = { day, stageMap: new Map() };
        dayMap.set(day, dayEntry);
      }

      let stageEntry = dayEntry.stageMap.get(stageId);
      if (!stageEntry) {
        stageEntry = {
          stageId,
          stageName: stageLabelById.get(stageId) || stageId || "Unassigned stage",
          gigs: [],
        };
        dayEntry.stageMap.set(stageId, stageEntry);
      }
      stageEntry.gigs.push(gig);
    });

  return Array.from(dayMap.values())
    .sort((left, right) => String(left.day || "").localeCompare(String(right.day || "")))
    .map((dayEntry) => ({
      day: dayEntry.day,
      stages: Array.from(dayEntry.stageMap.values())
        .map((stageEntry) => ({
          ...stageEntry,
          gigs: [...stageEntry.gigs].sort(compareGigStart),
        }))
        .sort((left, right) => String(left.stageName || "").localeCompare(String(right.stageName || ""))),
    }));
});

// Now view: current and next gig per stage
const nowViewData = computed(() => {
  // Keep this computed tied to the interval tick while using the synced server clock.
  nowTimestamp.value;
  const now = getCurrentServerWallDate();
  const nowMs = now.getTime();
  return stages.value.map((stage) => {
    const stageGigs = gigs.value
      .filter((g) => !g.__canceled && getGigStage(g) === stage.id)
      .sort(compareGigStart);

    let current = null;
    let next = null;
    for (const gig of stageGigs) {
      const range = getGigDateRange(gig);
      if (!range) continue;
      if (range.start.getTime() <= nowMs && nowMs < range.end.getTime()) {
        current = gig;
      } else if (range.start.getTime() > nowMs && !next) {
        next = gig;
      }
    }
    return { stage, current, next };
  });
});

// Auto-select current program day when available, otherwise keep the first-day fallback.
watch([sortedDays, currentSelectableProgramDay, effectiveFixedDay], ([days, currentDay, forcedDay]) => {
  if (days.length === 0) {
    selectedDay.value = null;
    selectedDayManuallySelected.value = false;
    return;
  }
  if (forcedDay) {
    selectedDay.value = forcedDay;
    selectedDayManuallySelected.value = false;
    return;
  }
  if (currentDay && (!selectedDayManuallySelected.value || !days.includes(selectedDay.value))) {
    selectedDay.value = currentDay;
    selectedDayManuallySelected.value = false;
    return;
  }
  if (!selectedDay.value || !days.includes(selectedDay.value)) {
    selectedDay.value = days[0];
    selectedDayManuallySelected.value = false;
  }
}, { immediate: true });

watch(defaultGrouping, (nextGrouping) => {
  groupBy.value = nextGrouping;
}, { immediate: true });

watch(defaultViewMode, (nextMode) => {
  viewMode.value = nextMode;
}, { immediate: true });

watch(showViewToggle, (canToggle) => {
  if (canToggle) return;
  viewMode.value = defaultViewMode.value;
}, { immediate: true });

watch(showGigDescriptionButton, (isVisible) => {
  if (isVisible) return;
  expandedGigDescriptionOpen.value = false;
});

watch(currentAdminTab, (tab) => {
  if (!state.isAdmin) return;
  if (tab === "content") {
    void loadProgramItemTemplateInfo();
  }
}, { immediate: true });

watch(
  () => [
    editableProgramCatalogContext.value,
    state.programSharedLoaded,
    state.programSharedScope,
  ],
  ([isEditableCatalog]) => {
    if (!isEditableCatalog) return;
    if (state.programSharedLoaded && state.programSharedScope === "full") return;
    void ensureFullProgramSharedData();
  },
  { immediate: true }
);


// Auto-select first stage when switching to stage view
watch([stages, groupBy], ([stageList, mode]) => {
  if (mode === 'stage' && stageList.length > 0 && !selectedStage.value) {
    selectedStage.value = stageList[0].id;
  }
}, { immediate: true });

watch(stages, (stageList) => {
  if (programCatalogSaveDepth.value > 0) return;
  stageDraft.value = stageList.map((stage) => normalizeStageDraftItem(stage));
  if (selectedStageDraftIndex.value >= stageDraft.value.length) {
    selectedStageDraftIndex.value = stageDraft.value.length - 1;
  }
  syncProgramItemPageJobsWithDraft();
}, { immediate: true });

watch(
  () => gigs.value,
  (nextGigs) => {
    if (programCatalogSaveDepth.value > 0) return;
    gigDraft.value = nextGigs.map((gig) => normalizeGigDraftItem(gig));
    if (selectedGigDraftIndex.value >= gigDraft.value.length) {
      selectedGigDraftIndex.value = gigDraft.value.length - 1;
    }
    syncProgramItemPageJobsWithDraft();
  },
  { immediate: true, deep: true }
);

watch(stageDraft, (nextDraft) => {
  const resolveStageId = buildGigStageIdResolver(nextDraft);
  gigDraft.value = gigDraft.value.map((gig) => {
    const next = normalizeGigDraftItem(gig);
    next.stage = resolveStageId(next.stage);
    return next;
  });
}, { deep: true });

const stageSelectionOptions = computed(() =>
  stageDraft.value
    .map((stage) => {
      const value = String(stage?.id || "").trim();
      if (!value) return null;
      const label = localizedText(stage.name) || value;
      return { value, label };
    })
    .filter(Boolean)
);

const firstStageId = computed(() => stageSelectionOptions.value[0]?.value || "");

const viewConfigStageValue = computed(() => {
  return fixedStageId.value;
});

const viewConfigScopeDay = computed(() => (
  defaultGrouping.value === "day"
    ? viewConfigDayValue.value
    : fixedDay.value
));

const viewConfigScopeStage = computed(() => (
  defaultGrouping.value === "stage"
    ? viewConfigStageValue.value
    : fixedStageId.value
));

const fixedGigOptions = computed(() =>
  gigs.value
    .filter((gig) => {
      if (selectedFixedGig.value) return true;
      const day = String(getLogicalDay(gig) || gig?.day || "").trim();
      const stageId = String(getGigStage(gig) || "").trim();
      if (viewConfigScopeDay.value && day !== viewConfigScopeDay.value) return false;
      if (viewConfigScopeStage.value && stageId !== viewConfigScopeStage.value) return false;
      return true;
    })
    .sort(compareGigStart)
    .map((gig) => {
      const value = String(gig?.id || "").trim();
      if (!value) return null;
      return {
        value,
        label: fixedGigOptionLabel(gig),
      };
    })
    .filter(Boolean)
);

watch([fixedGigId, fixedGigOptions], ([gigId, options]) => {
  if (!gigId) return;
  if (selectedFixedGig.value) return;
  // Avoid clearing persisted fixedGigId before shared gigs have loaded.
  if (!state.programSharedLoaded) return;
  const optionSet = new Set(
    (Array.isArray(options) ? options : [])
      .map((entry) => String(entry?.value || "").trim())
      .filter(Boolean)
  );
  if (optionSet.has(gigId)) return;
  updateSection(
    effectiveKey.value,
    { fixedGigId: "" },
    { revisionKind: "design" }
  );
}, { immediate: true });

watch(stageSelectionOptions, (options) => {
  const optionSet = new Set(
    options
      .map((entry) => String(entry?.value || "").trim())
      .filter(Boolean)
  );
  if (!options.length) {
    selectedStage.value = null;
    filterStage.value = null;
    return;
  }

  if (hasFixedStageSelection.value) {
    const forcedStage = effectiveFixedStageId.value;
    filterStage.value = optionSet.has(forcedStage) ? forcedStage : null;
    selectedStage.value = optionSet.has(forcedStage) ? forcedStage : options[0].value;
    return;
  }

  if (filterStage.value && !optionSet.has(String(filterStage.value || "").trim())) {
    filterStage.value = null;
  }
  if (selectedStage.value && !optionSet.has(String(selectedStage.value || "").trim())) {
    selectedStage.value = options[0].value;
  }
}, { immediate: true });

watch([effectiveFixedStageId, stageSelectionOptions], ([stageId, options]) => {
  const optionSet = new Set(
    (Array.isArray(options) ? options : [])
      .map((entry) => String(entry?.value || "").trim())
      .filter(Boolean)
  );
  if (stageId && optionSet.has(stageId)) {
    filterStage.value = stageId;
    if (groupBy.value === "stage") selectedStage.value = stageId;
    return;
  }
  // When fixed stage is cleared ("All stages"), always remove the forced filter.
  filterStage.value = null;
}, { immediate: true });

watch(effectiveFixedDay, (day) => {
  if (!day) return;
  selectedDay.value = day;
  selectedDayManuallySelected.value = false;
}, { immediate: true });

const gigEditorDayOptions = computed(() =>
  Array.from(
    new Set(
      gigDraft.value
        .map((gig) => String(gig?.day || "").trim())
        .filter(Boolean)
    )
  ).sort()
);

const gigEditorTypeOptions = computed(() => {
  const byValue = new Map();
  const addType = (value) => {
    const normalizedValue = String(value || "").trim();
    if (!normalizedValue || byValue.has(normalizedValue)) return;
    byValue.set(normalizedValue, {
      value: normalizedValue,
      label: normalizedValue,
    });
  };
  programGigTypeOptions.value.forEach((option) => addType(option?.value));
  gigDraft.value.forEach((gig) => addType(gig?.gig_type));
  return Array.from(byValue.values()).sort((left, right) => left.label.localeCompare(right.label));
});

const filteredGigDraftRows = computed(() =>
  gigDraft.value
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => {
      const itemDay = String(item?.day || "").trim();
      const itemStage = getGigStage(item);
      const itemType = String(item?.gig_type || "").trim();
      if (gigEditorDayFilter.value && itemDay !== gigEditorDayFilter.value) return false;
      if (gigEditorStageFilter.value && itemStage !== gigEditorStageFilter.value) return false;
      if (gigEditorTypeFilter.value && itemType !== gigEditorTypeFilter.value) return false;
      if (gigEditorItemPageFilter.value && resolveGigItemPageStatus(item) !== gigEditorItemPageFilter.value) return false;
      return true;
    })
);

const filteredGigDraft = computed(() =>
  filteredGigDraftRows.value.map((row) => row.item)
);

const selectedFilteredGigDraftIndex = computed(() =>
  filteredGigDraftRows.value.findIndex((row) => row.index === selectedGigDraftIndex.value)
);

watch(filteredGigDraftRows, (rows) => {
  if (!rows.length) {
    selectedGigDraftIndex.value = -1;
    return;
  }
  if (!rows.some((row) => row.index === selectedGigDraftIndex.value)) {
    selectedGigDraftIndex.value = -1;
  }
}, { immediate: true });

watch(
  () => buildProgramGigPageAvailabilitySignature(gigDraft.value),
  (signature) => {
    const slugs = signature
      ? signature.split("|").map((slug) => normalizeProgramGigPageSlugValue(slug)).filter(Boolean)
      : [];
    queueGigPageAvailabilityRefresh(slugs);
  },
  { immediate: true },
);

function normalizeListEditorIndex(index) {
  const numericIndex = Number.parseInt(index, 10);
  return Number.isFinite(numericIndex) ? numericIndex : -1;
}

function setSelectedStageDraftIndex(index) {
  selectedStageDraftIndex.value = normalizeListEditorIndex(index);
}

function selectGigDraftFromFiltered(filteredIndex) {
  const numericIndex = normalizeListEditorIndex(filteredIndex);
  if (numericIndex < 0) {
    selectedGigDraftIndex.value = -1;
    return;
  }
  const row = filteredGigDraftRows.value[numericIndex];
  selectedGigDraftIndex.value = row ? normalizeListEditorIndex(row.index) : -1;
}

function resolveGigDraftIndexFromSaveIndex(saveIndex) {
  const numericIndex = Number.parseInt(saveIndex, 10);
  if (Number.isFinite(numericIndex) && numericIndex >= 0) {
    const filteredRow = filteredGigDraftRows.value[numericIndex];
    if (filteredRow && Number.isFinite(Number(filteredRow.index))) {
      return Number(filteredRow.index);
    }
    if (numericIndex < gigDraft.value.length) {
      return numericIndex;
    }
  }
  const selectedIndex = Number.parseInt(selectedGigDraftIndex.value, 10);
  return Number.isFinite(selectedIndex) && selectedIndex >= 0 ? selectedIndex : -1;
}

function resolveGigDraftSaveIndexForItem(item) {
  if (!item || typeof item !== "object") return -1;
  const itemId = String(item.id || "").trim();
  const rawIndex = gigDraft.value.findIndex((gig) => {
    if (gig === item) return true;
    return itemId && String(gig?.id || "").trim() === itemId;
  });
  if (rawIndex < 0) return -1;
  return filteredGigDraftRows.value.findIndex((row) => row.index === rawIndex);
}

function removeGigDraftFromFiltered(filteredIndex) {
  const row = filteredGigDraftRows.value[filteredIndex];
  if (!row) return;
  removeGigDraft(row.index);
}

function reorderGigDraftFromFiltered(payload) {
  const oldFilteredIndex = Number.parseInt(payload?.oldIndex, 10);
  const newFilteredIndex = Number.parseInt(payload?.newIndex, 10);
  if (!Number.isFinite(oldFilteredIndex) || !Number.isFinite(newFilteredIndex)) return;
  if (oldFilteredIndex < 0 || newFilteredIndex < 0 || oldFilteredIndex === newFilteredIndex) return;

  const rows = filteredGigDraftRows.value;
  const sourceRow = rows[oldFilteredIndex];
  const targetRow = rows[newFilteredIndex];
  if (!sourceRow || !targetRow) return;

  const fromIndex = Number.parseInt(sourceRow.index, 10);
  const toIndex = Number.parseInt(targetRow.index, 10);
  if (!Number.isFinite(fromIndex) || !Number.isFinite(toIndex)) return;
  if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return;

  const movedItem = gigDraft.value.splice(fromIndex, 1)[0];
  if (!movedItem) return;
  gigDraft.value.splice(toIndex, 0, movedItem);
  selectedGigDraftIndex.value = toIndex;
}

function getGigDraftIndexFromFilteredIndex(filteredIndex) {
  const total = Array.isArray(gigDraft.value) ? gigDraft.value.length : 0;
  if (total <= 0) return -1;

  const target = filteredIndex && typeof filteredIndex === "object"
    ? filteredIndex
    : null;

  const targetGigId = String(target?.gigId || "").trim();
  if (targetGigId) {
    const indexById = gigDraft.value.findIndex((item) => String(item?.id || "").trim() === targetGigId);
    if (indexById >= 0) return indexById;
  }

  const filteredSource = target && Object.prototype.hasOwnProperty.call(target, "filteredIndex")
    ? target.filteredIndex
    : filteredIndex;
  const numericIndex = Number.parseInt(filteredSource, 10);
  if (Number.isFinite(numericIndex) && numericIndex >= 0) {
    const row = filteredGigDraftRows.value[numericIndex];
    if (row && Number.isInteger(row.index) && row.index >= 0 && row.index < total) {
      return row.index;
    }
    if (numericIndex < total) {
      return numericIndex;
    }
  }

  if (
    Number.isInteger(selectedGigDraftIndex.value)
    && selectedGigDraftIndex.value >= 0
    && selectedGigDraftIndex.value < total
  ) {
    return selectedGigDraftIndex.value;
  }

  return -1;
}

// Selected stage data
const activeDayForDayGrouping = computed(() => effectiveFixedDay.value || selectedDay.value || firstDay.value);
const activeStageFilterForDay = computed(() => effectiveFixedStageId.value || filterStage.value || "");
const activeStageForStageGrouping = computed(() => effectiveFixedStageId.value || selectedStage.value || firstStageId.value);
const activeDayFilterForStage = computed(() => effectiveFixedDay.value || "");

const selectedStageData = computed(() => {
  const stageId = activeStageForStageGrouping.value;
  if (!stageId) return null;
  return stages.value.find(s => s.id === stageId);
});

// Computed: gigs for selected day (when grouping by day, using logical day)
const gigsForSelectedDay = computed(() => {
  const day = activeDayForDayGrouping.value;
  if (!day) return [];
  return gigs.value.filter((g) => getLogicalDay(g) === day);
});

// Computed: gigs for selected stage (when grouping by stage)
const gigsForSelectedStage = computed(() => {
  const stageId = activeStageForStageGrouping.value;
  if (!stageId) return [];
  return gigs.value.filter((gig) => {
    if (getGigStage(gig) !== stageId) return false;
    if (activeDayFilterForStage.value && getLogicalDay(gig) !== activeDayFilterForStage.value) return false;
    return true;
  });
});

const daysForSelectedStage = computed(() => {
  const stageId = activeStageForStageGrouping.value;
  if (!stageId) return [];
  return sortedDays.value.filter((day) =>
    gigs.value.some((gig) => getLogicalDay(gig) === day && getGigStage(gig) === stageId)
  );
});

const stageViewDays = computed(() => {
  const day = activeDayFilterForStage.value;
  if (day) return [day];
  return daysForSelectedStage.value;
});

const stageViewCurrentDay = computed(() => {
  const day = currentProgramDay.value;
  return stageViewDays.value.includes(day) ? day : "";
});

function isStageViewDayMuted(day) {
  const currentDay = stageViewCurrentDay.value;
  return groupBy.value === "stage" && Boolean(currentDay) && String(day || "").trim() !== currentDay;
}

// Computed: filtered gigs based on current mode
const filteredGigs = computed(() => {
  if (groupBy.value === 'day') {
    let filtered = gigsForSelectedDay.value;
    if (activeStageFilterForDay.value) {
      filtered = filtered.filter((gig) => getGigStage(gig) === activeStageFilterForDay.value);
    }
    return filtered;
  } else {
    return gigsForSelectedStage.value;
  }
});

// Computed: filtered and sorted gigs for list view
const filteredGigsSorted = computed(() => {
  return [...filteredGigs.value].sort(compareGigStart);
});

const listGigDayGroups = computed(() => {
  const groups = new Map();
  filteredGigsSorted.value.forEach((gig) => {
    const day = String(getLogicalDay(gig) || gig?.day || "").trim();
    const key = day || "__no-day";
    if (!groups.has(key)) {
      const weekday = formatDayName(day);
      const date = formatDayDate(day);
      groups.set(key, {
        key,
        day,
        weekday: weekday || (state.lang === "de" ? "Ohne Tag" : "No day"),
        date: date && date !== weekday ? date : "",
        gigs: [],
      });
    }
    groups.get(key).gigs.push(gig);
  });
  return Array.from(groups.values());
});

const expandedGigItem = computed(() => {
  const gigId = String(expandedGig.value || "").trim();
  if (!gigId) return null;
  return gigs.value.find((gig) => String(gig?.id || "").trim() === gigId) || null;
});

const usesDetachedGigPopup = computed(() => (
  effectiveViewMode.value === "timeline"
  || (effectiveViewMode.value === "gantt" && isMobileView.value)
));

const detachedPopupGig = computed(() => (
  usesDetachedGigPopup.value ? expandedGigItem.value : null
));

// Computed: stages that have gigs on the selected day
const stagesWithGigs = computed(() => {
  return stages.value.filter((stage) => {
    return gigsForSelectedDay.value.some((gig) => getGigStage(gig) === stage.id);
  });
});

// Computed: filtered stages (only those with gigs on selected day)
const filteredStages = computed(() => {
  if (activeStageFilterForDay.value) {
    return stagesWithGigs.value.filter((s) => s.id === activeStageFilterForDay.value);
  }
  return stagesWithGigs.value;
});

// Computed: check if a stage is visible (has gigs and passes filter)
function isStageVisible(stageId) {
  const hasGigs = stagesWithGigs.value.some(s => s.id === stageId);
  if (!hasGigs) return false;
  if (!activeStageFilterForDay.value) return true;
  return activeStageFilterForDay.value === stageId;
}

// Computed: whether we're showing a single stage (solo mode)
const isSoloStage = computed(() => {
  return Boolean(activeStageFilterForDay.value) && filteredStages.value.length === 1;
});

const visiblePopupNavigationGigs = computed(() => {
  if (effectiveViewMode.value === "timeline") {
    return filteredGigsSorted.value;
  }
  if (groupBy.value === "stage") {
    return stageViewDays.value.flatMap((day) =>
      getGigsForStageAndDay(activeStageForStageGrouping.value, day)
        .filter((gig) => isGigInTimeRangeForStage(gig))
    );
  }
  return filteredStages.value.flatMap((stage) =>
    getGigsForStage(stage.id)
      .filter((gig) => isGigInTimeRange(gig))
  );
});

// Computed: absolute time bounds from day range settings
const absoluteTimeBounds = computed(() => {
  const startH = dayStartHour.value;
  const endH = dayEndHour.value;
  
  // endH > 24 means explicit next-day time (25=01:00, 30=06:00)
  // endH <= startH (and endH <= 24) means wrap to next day
  const minHour = startH;
  const maxHour = endH > 24 ? endH : (endH <= startH ? endH + 24 : endH);

  return { min: minHour, max: maxHour };
});

function buildConfiguredGanttTimeRange() {
  const bounds = absoluteTimeBounds.value;
  if (bounds.max <= bounds.min) return { start: bounds.min, end: bounds.min + 1 };
  return { start: bounds.min, end: bounds.max };
}

function buildTimeRangeForGigs(sourceGigs, options = {}) {
  const bounds = absoluteTimeBounds.value;
  if (options.useConfiguredRange) return buildConfiguredGanttTimeRange();

  const scopedGigs = Array.isArray(sourceGigs) ? sourceGigs : [];
  if (scopedGigs.length === 0) {
    return { start: bounds.min, end: bounds.max };
  }

  // Find earliest start and latest end from actual events
  let earliestStart = bounds.max;
  let latestEnd = bounds.min;

  scopedGigs.forEach(gig => {
    const startMinutes = adjustTimeForDayRange(gig.start_time);
    const endMinutes = adjustTimeForDayRange(gig.end_time);
    const startHour = startMinutes / 60;
    const endHour = endMinutes / 60;
    
    if (startHour < earliestStart) earliestStart = startHour;
    if (endHour > latestEnd) latestEnd = endHour;
  });
  
  // Clamp to absolute bounds and round to full hours
  const rangeStart = Math.max(bounds.min, Math.floor(earliestStart));
  const rangeEnd = Math.min(bounds.max, Math.ceil(latestEnd));
  
  // Ensure at least 1 hour range
  if (rangeEnd <= rangeStart) {
    return { start: rangeStart, end: rangeStart + 1 };
  }

  return { start: rangeStart, end: rangeEnd };
}

// Computed: time range for selected day (based on actual events, clamped to day range)
const timeRange = computed(() =>
  buildTimeRangeForGigs(gigsForSelectedDay.value, { useConfiguredRange: hasFixedGigFocus.value })
);

// Computed: time range for selected stage (based on actual events, clamped to day range)
const timeRangeForStage = computed(() =>
  buildTimeRangeForGigs(gigsForSelectedStage.value, { useConfiguredRange: hasFixedGigFocus.value })
);

// Computed: quarter hour markers for grid lines (includes hours and quarter hours)
const quarterHourMarkers = computed(() => {
  const markers = [];
  const start = timeRange.value.start;
  const end = timeRange.value.end;
  for (let h = start; h <= end; h += 0.25) {
    markers.push({
      time: h,
      isHour: h === Math.floor(h)
    });
  }
  return markers;
});

const quarterHourMarkersForStage = computed(() => {
  const markers = [];
  const start = timeRangeForStage.value.start;
  const end = timeRangeForStage.value.end;
  for (let h = start; h <= end; h += 0.25) {
    markers.push({
      time: h,
      isHour: h === Math.floor(h)
    });
  }
  return markers;
});

const currentTimeMinutesInRange = computed(() => {
  // Keep this computed tied to the interval tick while using the synced server clock.
  nowTimestamp.value;
  const now = getCurrentServerWallDate();
  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  const startHour = dayStartHour.value;
  const endHour = dayEndHour.value;
  const effectiveEndHour = endHour > 24 ? endHour - 24 : endHour;
  const dayWraps = endHour > 24 || endHour <= startHour;
  if (dayWraps && now.getHours() < effectiveEndHour) {
    return nowMinutes + (24 * 60);
  }
  return nowMinutes;
});

function getCurrentTimeMarkerPercent(range) {
  if (!range || typeof range !== "object") return null;
  const rangeStartMinutes = Number(range.start) * 60;
  const rangeEndMinutes = Number(range.end) * 60;
  if (!Number.isFinite(rangeStartMinutes) || !Number.isFinite(rangeEndMinutes) || rangeEndMinutes <= rangeStartMinutes) {
    return null;
  }
  const nowMinutes = currentTimeMinutesInRange.value;
  if (!Number.isFinite(nowMinutes)) return null;
  if (nowMinutes < rangeStartMinutes || nowMinutes > rangeEndMinutes) return null;
  const percent = ((nowMinutes - rangeStartMinutes) / (rangeEndMinutes - rangeStartMinutes)) * 100;
  return Math.max(0, Math.min(100, percent));
}

const currentTimeMarkerLeftDay = computed(() => {
  return getCurrentTimeMarkerPercent(timeRange.value);
});

const currentTimeMarkerLeftStage = computed(() => {
  return getCurrentTimeMarkerPercent(timeRangeForStage.value);
});

function isFixedGigFocus(gig) {
  const selectedId = String(selectedFixedGig.value?.id || "").trim();
  const gigId = String(gig?.id || "").trim();
  return Boolean(selectedId && gigId && gigId === selectedId);
}

function isMutedFixedGig(gig) {
  return hasFixedGigFocus.value && !isFixedGigFocus(gig);
}

function getFixedGigFocusPercent(range) {
  const gig = selectedFixedGig.value;
  if (!gig || !range || typeof range !== "object") return null;

  const rangeStart = Number(range.start) * 60;
  const rangeEnd = Number(range.end) * 60;
  if (!Number.isFinite(rangeStart) || !Number.isFinite(rangeEnd) || rangeEnd <= rangeStart) {
    return null;
  }

  const startMinutes = adjustTimeForDayRange(gig.start_time);
  const endMinutes = adjustTimeForDayRange(gig.end_time);
  if (!Number.isFinite(startMinutes) || !Number.isFinite(endMinutes)) return null;

  const midpoint = (startMinutes + Math.max(endMinutes, startMinutes)) / 2;
  const clampedMidpoint = Math.max(rangeStart, Math.min(rangeEnd, midpoint));
  return (clampedMidpoint - rangeStart) / (rangeEnd - rangeStart);
}

function scrollFixedGigIntoView() {
  if (!hasFixedGigFocus.value || effectiveViewMode.value !== "gantt") return;
  const container = groupBy.value === "stage"
    ? stageGanttScrollContainer.value
    : dayGanttScrollContainer.value;
  if (!container) return;

  const maxScrollLeft = container.scrollWidth - container.clientWidth;
  if (!Number.isFinite(maxScrollLeft) || maxScrollLeft <= 0) return;

  const range = groupBy.value === "stage" ? timeRangeForStage.value : timeRange.value;
  const focusPercent = getFixedGigFocusPercent(range);
  if (!Number.isFinite(focusPercent)) return;

  const targetCenter = container.scrollWidth * focusPercent;
  const nextScrollLeft = Math.max(0, Math.min(maxScrollLeft, targetCenter - (container.clientWidth / 2)));
  container.scrollLeft = nextScrollLeft;
}

function scheduleFixedGigScrollIntoView() {
  if (typeof window === "undefined") return;
  if (!hasFixedGigFocus.value || effectiveViewMode.value !== "gantt") return;
  if (fixedGigScrollFrame !== null) {
    window.cancelAnimationFrame(fixedGigScrollFrame);
    fixedGigScrollFrame = null;
  }
  nextTick(() => {
    fixedGigScrollFrame = window.requestAnimationFrame(() => {
      fixedGigScrollFrame = null;
      scrollFixedGigIntoView();
    });
  });
}

watch(
  [hasFixedGigFocus, fixedGigId, effectiveViewMode, groupBy, timeRange, timeRangeForStage, ganttWidthPercent],
  () => scheduleFixedGigScrollIntoView(),
  { immediate: true }
);

// Utility functions
function timeToMinutes(timeStr) {
  if (!timeStr) return 0;
  const [h, m] = timeStr.split(":").map(Number);
  return h * 60 + (m || 0);
}

// Adjust time for display when day wraps past midnight
// e.g., if day is 12:00-06:00, a gig at 02:00 should display at 26:00 (02+24)
function adjustTimeForDayRange(timeStr) {
  if (!timeStr) return 0;
  const [h, m] = timeStr.split(":").map(Number);
  const minutes = h * 60 + (m || 0);
  
  const startHour = dayStartHour.value;
  const endHour = dayEndHour.value;
  
  // Calculate effective end hour (accounting for next-day values > 24)
  const effectiveEndHour = endHour > 24 ? endHour - 24 : endHour;
  const dayWraps = endHour > 24 || endHour <= startHour;
  
  // If day wraps past midnight and this time is in the early morning portion
  if (dayWraps && h < effectiveEndHour) {
    return minutes + 24 * 60; // Add 24 hours
  }
  
  return minutes;
}

function formatHour(hour) {
  // Format hour for display, handling hours > 24 (e.g., 25 → "1:00")
  const displayHour = hour % 24;
  return `${displayHour}:00`;
}

function formatDayName(day) {
  if (!day) return "";
  return formatServerDateOnly(
    day,
    { weekday: "short" },
    { locale: state.lang === "de" ? "de-DE" : "en-US", fallback: String(day || "") }
  );
}

function formatDayDate(day) {
  if (!day) return "";
  return formatServerDateOnly(
    day,
    { day: "2-digit", month: "2-digit" },
    { locale: state.lang === "de" ? "de-DE" : "en-US", fallback: String(day || "") }
  );
}

function formatGigOverlayDateTime(gig, previous = false) {
  const rawDay = previous
    ? extractGigDatePart(gig?.previous_start) || String(gig?.previous_day || "").trim() || getBaseLogicalDay(gig) || gig?.day
    : getLogicalDay(gig) || gig?.day;
  const day = previous ? applyProgramDayDebugOffset(rawDay) : rawDay;
  const dayLabel = [formatDayName(day), formatDayDate(day)].filter(Boolean).join(" ");
  const start = previous ? oldGigStartTime(gig) : String(gig?.start_time || "").trim();
  // const end = previous ? oldGigEndTime(gig) : String(gig?.end_time || "").trim();
  // const timeLabel = start && end ? `${start} - ${end}` : start || end;
  return [dayLabel, start].filter(Boolean).join(" · ");
}

const AUTO_STAGE_COLOR_PALETTE = [
  "#ef4444",
  "#3b82f6",
  "#8b5cf6",
  "#10b981",
  "#f59e0b",
  "#ec4899",
  "#06b6d4",
  "#84cc16",
];

function getAutoStageColor(stage) {
  const seedSource = String(stage?.id || stage?.name?.en || stage?.name?.de || "stage");
  let hash = 0;
  for (let i = 0; i < seedSource.length; i += 1) {
    hash = ((hash << 5) - hash + seedSource.charCodeAt(i)) | 0;
  }
  const idx = Math.abs(hash) % AUTO_STAGE_COLOR_PALETTE.length;
  return AUTO_STAGE_COLOR_PALETTE[idx];
}

function getStagePickerColor(stage) {
  const linkKey = getStageColorLink(stage);
  if (linkKey) {
    const resolved = normalizeResolvedColor(
      resolveBaseColor(linkKey),
      "sectionBackgroundColor",
      state.design.sectionBackgroundColor
    );
    if (resolved) return resolved;
  }
  const customColor = getStageCustomColor(stage);
  if (customColor) {
    const resolvedCustom = normalizeResolvedColor(
      customColor,
      "sectionBackgroundColor",
      state.design.sectionBackgroundColor
    );
    if (resolvedCustom) return resolvedCustom;
  }
  return normalizeResolvedColor(
    getAutoStageColor(stage),
    "sectionBackgroundColor",
    state.design.sectionBackgroundColor
  );
}

function getStageVisualColor(stage) {
  const variation = getStageColorVariation(stage);
  return applyColorVariation(getStagePickerColor(stage), variation);
}

function getStageColor(stageName) {
  const stage = stages.value.find(
    (s) => s.name?.de === stageName || s.name?.en === stageName || s.id === stageName
  );
  return getStageVisualColor(stage);
}

function getStageName(stageName) {
  const stage = stages.value.find(
    (s) => s.name?.de === stageName || s.name?.en === stageName || s.id === stageName
  );
  return stage ? localizedText(stage.name) : stageName;
}

const LIST_CARD_BACKGROUND_MOBILE_WIDTH_PX = 768;

function escapeCssUrl(value) {
  return String(value || "")
    .trim()
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/[\r\n]/g, "");
}

function resolveListCardBackgroundVariantUrl(gig) {
  const media = resolveProgramGigImageMedia(gig);
  const variants = (Array.isArray(media.responsiveVariants) ? media.responsiveVariants : [])
    .filter((entry) => String(entry?.url || "").trim())
    .filter((entry) => {
      const width = Number(entry?.width);
      return Number.isFinite(width) && width > 0;
    })
    .sort((left, right) => Number(left.width) - Number(right.width));

  const namedMobile = variants.find((entry) => String(entry?.name || "").trim().toLowerCase() === "mobile");
  if (namedMobile) return String(namedMobile.url || "").trim();

  const mobileWidthMatch = variants.find((entry) => Number(entry.width) >= LIST_CARD_BACKGROUND_MOBILE_WIDTH_PX);
  if (mobileWidthMatch) return String(mobileWidthMatch.url || "").trim();

  const largestAvailableVariant = variants[variants.length - 1];
  if (largestAvailableVariant) return String(largestAvailableVariant.url || "").trim();

  return String(media.url || "").trim();
}

function resolveListCardBackgroundImage(gig) {
  if (!showListItemBackgroundImages.value) return "none";
  const rawUrl = resolveListCardBackgroundVariantUrl(gig);
  if (!rawUrl) return "none";
  const safeUrl = escapeCssUrl(rawUrl);
  return `url("${safeUrl}")`;
}

function getGigsForStage(stageId) {
  return gigsForSelectedDay.value
    .filter((gig) => getGigStage(gig) === stageId)
    .sort(compareGigStart);
}

function getGigsForStageAndDay(stageId, day) {
  return gigs.value
    .filter((gig) => {
      return getLogicalDay(gig) === day &&
             getGigStage(gig) === stageId;
    })
    .sort(compareGigStart);
}

function getHourPosition(hour) {
  const range = timeRange.value.end - timeRange.value.start;
  return ((hour - timeRange.value.start) / range) * 100;
}

function getHourPositionForStage(hour) {
  const range = timeRangeForStage.value.end - timeRangeForStage.value.start;
  return ((hour - timeRangeForStage.value.start) / range) * 100;
}

function isGigInTimeRange(gig) {
  const startMinutes = adjustTimeForDayRange(gig.start_time);
  const endMinutes = adjustTimeForDayRange(gig.end_time);
  const rangeStart = timeRange.value.start * 60;
  const rangeEnd = timeRange.value.end * 60;
  
  // Gig is visible if it overlaps with the time range
  return endMinutes > rangeStart && startMinutes < rangeEnd;
}

function getGigBubbleStyle(gig) {
  const startMinutes = adjustTimeForDayRange(gig.start_time);
  const endMinutes = adjustTimeForDayRange(gig.end_time);
  const rangeStart = timeRange.value.start * 60;
  const rangeEnd = timeRange.value.end * 60;
  const totalRange = rangeEnd - rangeStart;

  // Clamp to visible range
  const clampedStart = Math.max(startMinutes, rangeStart);
  const clampedEnd = Math.min(endMinutes, rangeEnd);
  
  const left = ((clampedStart - rangeStart) / totalRange) * 100;
  const width = ((clampedEnd - clampedStart) / totalRange) * 100;

  return {
    "--gig-left": `${Math.max(0, Math.min(100, left))}%`,
    "--gig-width": `${Math.max(width, 3)}%`,
  };
}

function isGigInTimeRangeForStage(gig) {
  const startMinutes = adjustTimeForDayRange(gig.start_time);
  const endMinutes = adjustTimeForDayRange(gig.end_time);
  const rangeStart = timeRangeForStage.value.start * 60;
  const rangeEnd = timeRangeForStage.value.end * 60;
  
  return endMinutes > rangeStart && startMinutes < rangeEnd;
}

function getGigBubbleStyleForStage(gig) {
  const startMinutes = adjustTimeForDayRange(gig.start_time);
  const endMinutes = adjustTimeForDayRange(gig.end_time);
  const rangeStart = timeRangeForStage.value.start * 60;
  const rangeEnd = timeRangeForStage.value.end * 60;
  const totalRange = rangeEnd - rangeStart;

  // Clamp to visible range
  const clampedStart = Math.max(startMinutes, rangeStart);
  const clampedEnd = Math.min(endMinutes, rangeEnd);
  
  const left = ((clampedStart - rangeStart) / totalRange) * 100;
  const width = ((clampedEnd - clampedStart) / totalRange) * 100;

  return {
    "--gig-left": `${Math.max(0, Math.min(100, left))}%`,
    "--gig-width": `${Math.max(width, 3)}%`,
  };
}

function createStageId() {
  return `stage-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

function createGigId() {
  return `gig-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

function normalizeStageDraftRows(rows) {
  return (Array.isArray(rows) ? rows : [])
    .map((stage) => normalizeStageDraftItem(stage))
    .map((stage) => ({
      ...stage,
      id: String(stage.id || "").trim() || createStageId(),
    }));
}

function normalizeGigDraftRows(rows, stageRows = stageDraft.value) {
  const resolveStageId = buildGigStageIdResolver(stageRows);
  return (Array.isArray(rows) ? rows : [])
    .map((gig) => normalizeGigDraftItem(gig))
    .map((gig) => {
      const normalizedStage = resolveStageId(gig.stage);
      const nextGig = {
        ...gig,
        id: String(gig.id || "").trim() || createGigId(),
        start: String(gig.start || "").trim(),
        end: String(gig.end || "").trim(),
        day: String(gig.day || "").trim(),
        start_time: String(gig.start_time || "").trim(),
        end_time: String(gig.end_time || "").trim(),
        image_url: String(gig.image_url || "").trim(),
        image_responsive_variants: normalizeGigResponsiveVariants(gig.image_responsive_variants),
        image_zoom: normalizeGigImageZoom(gig.image_zoom),
        image_focal_x: normalizeGigImageFocal(gig.image_focal_x),
        image_focal_y: normalizeGigImageFocal(gig.image_focal_y),
        image_rotation: normalizeGigImageRotation(gig.image_rotation),
        stage: normalizedStage,
        genre_selection: normalizeProgramGenreSelection(gig.genre_selection),
        register_changes: Boolean(gig.register_changes ?? false),
        highlight_changes: Boolean(gig.highlight_changes ?? false),
        canceled: Boolean(gig.canceled ?? false),
        previous_start: String(gig.previous_start ?? "").trim(),
        previous_end: String(gig.previous_end ?? "").trim(),
        previous_day: String(gig.previous_day ?? "").trim(),
        previous_start_time: String(gig.previous_start_time ?? "").trim(),
        previous_end_time: String(gig.previous_end_time ?? "").trim(),
        previous_stage: normalizeStageLookupText(gig.previous_stage),
        page_slug: String(gig.page_slug ?? "").trim(),
        item_url: String(gig.item_url ?? "").trim(),
      };
      syncGigLegacyScheduleFields(nextGig);
      return nextGig;
    });
}

function getCurrentSharedProgramCatalog() {
  const currentStages = state.programSharedLoaded
    ? (Array.isArray(state.programSharedStages) ? state.programSharedStages : [])
    : stages.value;
  const currentGigs = state.programSharedLoaded
    ? (Array.isArray(state.programSharedGigs) ? state.programSharedGigs : [])
    : gigs.value;
  return {
    stages: normalizeStageDraftRows(currentStages),
    gigs: normalizeGigDraftRows(currentGigs, currentStages),
  };
}

function applyStageColorDesignLocally(nextStages, nextGigs) {
  const normalizedStages = normalizeStageDraftRows(nextStages);
  const normalizedGigs = normalizeGigDraftRows(nextGigs, normalizedStages);
  state.programSharedStages = normalizedStages.map((stage) => cloneValue(stage));
  state.programSharedGigs = normalizedGigs.map((gig) => cloneValue(gig));
  state.programSharedLoaded = true;
  stageDraft.value = normalizedStages;
  gigDraft.value = normalizedGigs;
}

function clearStageColorDesignSaveTimer() {
  if (!stageColorDesignSaveTimer) return;
  clearTimeout(stageColorDesignSaveTimer);
  stageColorDesignSaveTimer = null;
}

function persistCurrentStageColorDesign(runId) {
  if (runId !== stageColorDesignSaveRunId) return;
  const catalog = getCurrentSharedProgramCatalog();
  persistProgramCatalog({
    stages: catalog.stages,
    gigs: catalog.gigs,
  }).catch((err) => {
    console.error("Failed to persist stage color design update:", err);
  });
}

function queueStageColorDesignPersist() {
  const runId = stageColorDesignSaveRunId + 1;
  stageColorDesignSaveRunId = runId;
  clearStageColorDesignSaveTimer();
  stageColorDesignSaveTimer = setTimeout(() => {
    stageColorDesignSaveTimer = null;
    persistCurrentStageColorDesign(runId);
  }, PROGRAM_STAGE_COLOR_SAVE_DELAY_MS);
}

function flushStageColorDesignPersist() {
  if (!stageColorDesignSaveTimer) return;
  const runId = stageColorDesignSaveRunId;
  clearStageColorDesignSaveTimer();
  persistCurrentStageColorDesign(runId);
}

function stripProgramItemRuntimeFlags(row) {
  if (!row || typeof row !== "object") return row;
  const next = { ...row };
  delete next.item_page_template_outdated;
  delete next.item_page_missing;
  delete next.item_page_mapped_fields_synced;
  delete next.day;
  delete next.start_time;
  delete next.end_time;
  delete next.previous_day;
  delete next.previous_start_time;
  delete next.previous_end_time;
  delete next.__source;
  delete next.__base;
  delete next.__change;
  delete next.__canceled;
  delete next.__changed;
  return next;
}

async function performProgramCatalogPersist(
  requestId,
  {
    stages: nextStages,
    gigs: nextGigs,
    programGigsIntegrationMapping = undefined,
    programGigsIntegrationMappingCacheState = undefined,
  } = {}
) {
  const normalizedStages = normalizeStageDraftRows(nextStages);
  const collapsedGigs = collapseDuplicateProgramGigsByExternalKey(nextGigs, normalizedStages);
  const normalizedGigs = collapsedGigs.rows;
  const localDuplicates = resolveProgramDuplicateIds(normalizedStages, normalizedGigs);
  if (localDuplicates.stages.length || localDuplicates.gigs.length) {
    setProgramDuplicateIdWarning(localDuplicates.stages, localDuplicates.gigs);
    throw new Error(buildProgramDuplicateIdWarningMessage(localDuplicates.stages, localDuplicates.gigs));
  }
  clearProgramDuplicateIdWarning();

  const sectionSnapshot = section.value && typeof section.value === "object"
    ? cloneValue(section.value)
    : {};
  sectionSnapshot.stages = cloneValue(normalizedStages);
  sectionSnapshot.gigs = cloneValue(normalizedGigs);
  const stagesForSave = Array.isArray(sectionSnapshot.stages)
    ? sectionSnapshot.stages
    : normalizedStages;
  const gigsForSave = Array.isArray(sectionSnapshot.gigs)
    ? sectionSnapshot.gigs
    : normalizedGigs;
  programCatalogSaveDepth.value += 1;
  try {
    let saveResult = null;
    try {
      const sharedSavePayload = {
        stages: stagesForSave.map((row) => stripProgramItemRuntimeFlags(row)),
        gigs: gigsForSave.map((row) => stripProgramItemRuntimeFlags(row)),
      };
      if (programGigsIntegrationMapping !== undefined) {
        sharedSavePayload.programGigsIntegrationMapping = cloneValue(programGigsIntegrationMapping || {});
      }
      if (programGigsIntegrationMappingCacheState !== undefined) {
        sharedSavePayload.programGigsIntegrationMappingCacheState = cloneValue(programGigsIntegrationMappingCacheState || {});
      }
      saveResult = await saveProgramSharedData(sharedSavePayload);
    } catch (err) {
      const duplicateError = parseProgramDuplicateIdError(err);
      if (duplicateError) {
        setProgramDuplicateIdWarning(duplicateError.stages, duplicateError.gigs);
      }
      throw err;
    }
    clearProgramDuplicateIdWarning();
    registerProgramItemPageGenerationJobs(saveResult?.itemPageGenerationJobs);
    if (requestId !== programCatalogSaveRequestId) return;
    // Keep editor drafts in sync immediately; shared-catalog watchers are paused while saving.
    const syncedStages = Array.isArray(state.programSharedStages)
      ? state.programSharedStages
      : stagesForSave;
    const syncedGigs = Array.isArray(state.programSharedGigs)
      ? state.programSharedGigs
      : gigsForSave;
    stageDraft.value = normalizeStageDraftRows(syncedStages);
    gigDraft.value = normalizeGigDraftRows(syncedGigs, stageDraft.value);
    if (selectedStageDraftIndex.value >= stageDraft.value.length) {
      selectedStageDraftIndex.value = stageDraft.value.length - 1;
    }
    if (selectedGigDraftIndex.value >= gigDraft.value.length) {
      selectedGigDraftIndex.value = gigDraft.value.length - 1;
    }
    syncProgramItemPageJobsWithDraft();
  } finally {
    programCatalogSaveDepth.value = Math.max(0, programCatalogSaveDepth.value - 1);
  }
}

function persistProgramCatalog(payload) {
  const requestId = ++programCatalogSaveRequestId;
  const runPersist = () => performProgramCatalogPersist(requestId, payload);
  programCatalogSaveQueue = programCatalogSaveQueue.then(runPersist, runPersist);
  return programCatalogSaveQueue;
}

function dateOnlyUtcMs(dayValue) {
  const parts = parseServerDateOnlyParts(dayValue);
  if (!parts) return null;
  return Date.UTC(parts.year, parts.month - 1, parts.day);
}

function dayOffsetBetweenDateOnlyValues(fromDay, toDay) {
  const fromMs = dateOnlyUtcMs(fromDay);
  const toMs = dateOnlyUtcMs(toDay);
  if (fromMs == null || toMs == null) return null;
  return Math.round((toMs - fromMs) / (24 * 60 * 60 * 1000));
}

function shiftDateOnlyValueByDays(dayValue, dayOffset) {
  const parsed = parseDateOnlyValue(dayValue);
  if (!parsed) return String(dayValue || "").trim();
  const shifted = new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate() + dayOffset);
  return formatDateOnlyValue(shifted);
}

async function setTodayAsProgramDayForDebug() {
  if (settingTodayAsProgramDay.value) return;
  settingTodayAsProgramDay.value = true;
  dayRangeDebugStatus.value = { type: "", message: "" };

  try {
    await ensureFullProgramSharedData();
    const fallbackCatalog = getCurrentSharedProgramCatalog();
    const stageRows = normalizeStageDraftRows(
      stageDraft.value.length ? stageDraft.value : fallbackCatalog.stages
    );
    const gigRows = normalizeGigDraftRows(
      gigDraft.value.length ? gigDraft.value : fallbackCatalog.gigs,
      stageRows
    );
    const availableDays = Array.from(
      new Set(gigRows.map((gig) => getBaseLogicalDay(gig)).filter(Boolean))
    ).sort();
    const targetDay = currentProgramDay.value;

    if (!targetDay) {
      dayRangeDebugStatus.value = {
        type: "error",
        message: "Could not resolve today's program day.",
      };
      return;
    }
    if (!availableDays.length) {
      dayRangeDebugStatus.value = {
        type: "warn",
        message: "No gigs available to shift.",
      };
      return;
    }
    if (availableDays.includes(targetDay)) {
      programDayDebugOffsetDays.value = 0;
      selectedDayManuallySelected.value = false;
      selectedDay.value = targetDay;
      dayRangeDebugStatus.value = {
        type: "success",
        message: "Today is already an available program day. No saved changes made.",
      };
      return;
    }

    const dayOffset = dayOffsetBetweenDateOnlyValues(availableDays[0], targetDay);
    if (!Number.isFinite(dayOffset)) {
      dayRangeDebugStatus.value = {
        type: "error",
        message: "Could not calculate date shift for program days.",
      };
      return;
    }

    programDayDebugOffsetDays.value = dayOffset;
    selectedDayManuallySelected.value = false;
    selectedDay.value = targetDay;
    dayRangeDebugStatus.value = {
      type: "success",
      message: `Temporarily shifted displayed program dates by ${dayOffset} day${Math.abs(dayOffset) === 1 ? "" : "s"}. Refresh resets it.`,
    };
  } catch (err) {
    console.error("Failed to set today as program day:", err);
    dayRangeDebugStatus.value = {
      type: "error",
      message: err?.message || "Failed to set today as program day.",
    };
  } finally {
    settingTodayAsProgramDay.value = false;
  }
}

async function persistProgramGigsIntegrationMappingPatch(patch) {
  const nextGigMapping = resolveProgramGigIntegrationMappingFromPatch(patch);
  await saveProgramSharedData({
    programGigsIntegrationMapping: nextGigMapping,
  });
  state.programSharedGigsIntegrationMapping = cloneValue(nextGigMapping);
}

function setProgramFallbackOverrideEnabled(enabled) {
  updateSection(
    effectiveKey.value,
    { programFallbackOverrideEnabled: Boolean(enabled) },
    { revisionKind: "content" }
  );
}

function applyProgramGigFallbackImages(payload = {}) {
  updateSection(
    effectiveKey.value,
    {
      programGigFallbackImages: Array.isArray(payload.images) ? payload.images : [],
      programGigFallbackMediaTag: String(payload.mediaTag || "").trim() || null,
      programGigFallbackImageUrl: null,
    },
    { revisionKind: "content" }
  );
}

function clearProgramGigFallbackImages() {
  updateSection(
    effectiveKey.value,
    {
      programGigFallbackImages: [],
      programGigFallbackMediaTag: null,
      programGigFallbackImageUrl: null,
    },
    { revisionKind: "content" }
  );
}

function setProgramGigFallbackTransform(patch) {
  const mapped = {};
  if (patch.zoom !== undefined) mapped.programGigFallbackZoom = normalizeGigImageZoom(patch.zoom);
  if (patch.focalX !== undefined) mapped.programGigFallbackFocalX = normalizeGigImageFocal(patch.focalX);
  if (patch.focalY !== undefined) mapped.programGigFallbackFocalY = normalizeGigImageFocal(patch.focalY);
  if (patch.rotation !== undefined) mapped.programGigFallbackRotation = normalizeGigImageRotation(patch.rotation);
  if (Object.keys(mapped).length) {
    updateSection(effectiveKey.value, mapped, { revisionKind: "content" });
  }
}

function applyProgramGigFallbacksToImportedGigs(importedGigs = []) {
  if (!programFallbackOverrideEnabled.value) return importedGigs;
  const fallbackPool = programGigFallbackImagePool.value;
  if (!Array.isArray(importedGigs) || fallbackPool.length === 0) return importedGigs;

  return importedGigs.map((gig, index) => {
    if (!gig || typeof gig !== "object") return gig;
    if (String(gig.image_url || "").trim()) return gig;

    const fallbackImage = fallbackPool[index % fallbackPool.length];
    const imageUrl = String(fallbackImage?.imageUrl || "").trim();
    if (!imageUrl) return gig;

    return {
      ...gig,
      image_url: imageUrl,
      image_responsive_variants: Array.isArray(fallbackImage?.responsiveVariants)
        ? fallbackImage.responsiveVariants
        : [],
      image_zoom: programGigFallbackZoom.value,
      image_focal_x: programGigFallbackFocalX.value,
      image_focal_y: programGigFallbackFocalY.value,
      image_rotation: programGigFallbackRotation.value,
    };
  });
}

async function applyProgramGigsImportPatch(patch) {
  const catalog = getCurrentSharedProgramCatalog();
  const currentStageRows = Array.isArray(catalog.stages) && catalog.stages.length > 0
    ? catalog.stages
    : stageDraft.value;
  const hasImportedGigs = Array.isArray(patch?.gigs);
  const nextGigCacheState = patch?.[PROGRAM_GIGS_CACHE_STATE_KEY];
  const nextGigMapping = resolveProgramGigIntegrationMappingFromPatch(patch);
  const hasGigCacheStatePatch = Object.prototype.hasOwnProperty.call(
    patch || {},
    PROGRAM_GIGS_CACHE_STATE_KEY
  );
  if (!hasImportedGigs) {
    const metadataPayload = {
      programGigsIntegrationMapping: nextGigMapping,
    };
    if (hasGigCacheStatePatch) {
      metadataPayload.programGigsIntegrationMappingCacheState = (
        nextGigCacheState && typeof nextGigCacheState === "object"
          ? nextGigCacheState
          : {}
      );
    }
    await saveProgramSharedData(metadataPayload);
    state.programSharedGigsIntegrationMapping = cloneValue(nextGigMapping);
    if (hasGigCacheStatePatch) {
      state.programSharedGigsIntegrationMappingCacheState = cloneValue(
        metadataPayload.programGigsIntegrationMappingCacheState
      );
    }
    return;
  }
  const effectiveGigCacheState = nextGigCacheState && typeof nextGigCacheState === "object"
    ? nextGigCacheState
    : state.programSharedGigsIntegrationMappingCacheState;
  const rawImportedGigRows = hasImportedGigs ? patch.gigs : catalog.gigs;
  const importedGigsForStageDerivation = (Array.isArray(rawImportedGigRows) ? rawImportedGigRows : [])
    .map((gig) => normalizeGigDraftItem(gig));
  const stageRows = deriveProgramStagesFromGigRows(
    currentStageRows,
    importedGigsForStageDerivation,
    nextGigCacheState
  );
  const existingGigs = normalizeGigDraftRows(catalog.gigs, stageRows);
  const importedGigs = normalizeGigDraftRows(
    rawImportedGigRows,
    stageRows
  );
  const importedGigsWithFallbacks = hasImportedGigs
    ? applyProgramGigFallbacksToImportedGigs(importedGigs)
    : importedGigs;
  const sourceId = resolveProgramGigImportSourceIdFromPatch(patch);
  const normalizedGigs = mergeProgramGigImportsBySource({
    existingGigs,
    importedGigs: importedGigsWithFallbacks,
    sourceId,
    cacheState: effectiveGigCacheState,
  });
  await persistProgramCatalog({
    stages: stageRows,
    gigs: normalizedGigs,
    programGigsIntegrationMapping: nextGigMapping,
    programGigsIntegrationMappingCacheState: effectiveGigCacheState,
  });
  if (nextGigCacheState && typeof nextGigCacheState === "object") {
    state.programSharedGigsIntegrationMappingCacheState = cloneValue(nextGigCacheState);
  }
  state.programSharedGigsIntegrationMapping = cloneValue(nextGigMapping);
}

async function clearAllStageItems() {
  selectedStageDraftIndex.value = -1;
  stageDraft.value = [];
  await saveStageDraft();
}

async function clearAllGigItems() {
  selectedGigDraftIndex.value = -1;
  gigDraft.value = [];
  await saveGigDraft();
}

function openStageMediaPicker(index) {
  stageMediaPickerTargetIndex.value = Number.isInteger(index) ? index : -1;
  showStageMediaPicker.value = true;
}

function closeStageMediaPicker() {
  showStageMediaPicker.value = false;
  stageMediaPickerTargetIndex.value = -1;
}

function applyStageMediaSelection(selection) {
  const index = stageMediaPickerTargetIndex.value;
  if (index >= 0 && index < stageDraft.value.length) {
    const stage = stageDraft.value[index];
    const media = resolveBackendResponsiveImagePayload(selection, {
      urlKeys: ["url", "src", "href"],
    });
    stage.image_url = String(media.url || "").trim();
    stage.image_responsive_variants = media.responsiveVariants;
  }
  closeStageMediaPicker();
}

function clearStageImage(index) {
  if (index < 0 || index >= stageDraft.value.length) return;
  stageDraft.value[index].image_url = "";
  stageDraft.value[index].image_responsive_variants = [];
}

function addStageDraft() {
  stageDraft.value.push(normalizeStageDraftItem({
    id: createStageId(),
    name: { de: "", en: "" },
    description: { de: "", en: "" },
    image_url: "",
    color: "",
  }));
  selectedStageDraftIndex.value = stageDraft.value.length - 1;
  void saveStageDraft();
}

function slugifyProgramStageId(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function findStageDraftIndexForMetadataOption(rows, option) {
  const optionKey = normalizeStageLookupKey(option?.value);
  if (!optionKey) return -1;
  return (Array.isArray(rows) ? rows : []).findIndex((stage) => {
    const stageId = String(stage?.id || "").trim();
    const stageNameDE = String(stage?.name?.de || "").trim();
    const stageNameEN = String(stage?.name?.en || "").trim();
    return [stageId, stageNameDE, stageNameEN].some((candidate) =>
      normalizeStageLookupKey(candidate) === optionKey
    );
  });
}

function createProgramStageIdFromMetadataOption(option, usedIds) {
  const base = slugifyProgramStageId(option?.value || option?.label) || createStageId();
  let candidate = base;
  let suffix = 2;
  while (usedIds.has(candidate)) {
    candidate = `${base}-${suffix}`;
    suffix += 1;
  }
  usedIds.add(candidate);
  return candidate;
}

function mergeMetadataOptionIntoStageDraft(stage, option) {
  const nextStage = normalizeStageDraftItem(stage);
  const label = String(option?.label || option?.value || "").trim();
  if (!label) return nextStage;
  if (!String(nextStage.name?.de || "").trim()) {
    nextStage.name = { ...nextStage.name, de: label };
  }
  if (!String(nextStage.name?.en || "").trim()) {
    nextStage.name = { ...nextStage.name, en: label };
  }
  return nextStage;
}

function deriveProgramStagesFromGigRows(stageRows = [], gigRows = [], cacheState = null) {
  const nextStages = normalizeStageDraftRows(stageRows);
  if (programStageSourcePaths.value.length === 0) {
    return nextStages;
  }
  const usedIds = new Set(nextStages.map((stage) => String(stage?.id || "").trim()).filter(Boolean));
  const metadataOptionsByLookup = buildProgramStageMetadataOptionLookup(cacheState);

  (Array.isArray(gigRows) ? gigRows : []).forEach((gig) => {
    const rawStage = gig?.stage;
    const stageValue = normalizeStageLookupText(rawStage);
    if (!stageValue) return;

    const stageKey = normalizeStageLookupKey(stageValue);
    const metadataOption = stageKey ? metadataOptionsByLookup.get(stageKey) : null;
    const option = {
      value: normalizeStageLookupText(metadataOption?.value) || stageValue,
      label: String(
        metadataOption?.label
          || resolveProgramStageOptionDisplayText(rawStage, stageValue)
          || stageValue
      ).trim(),
    };
    if (!option.value) return;

    const existingIndex = findStageDraftIndexForMetadataOption(nextStages, option);
    if (existingIndex >= 0) {
      const mergedStage = mergeMetadataOptionIntoStageDraft(nextStages[existingIndex], option);
      if (JSON.stringify(mergedStage) !== JSON.stringify(nextStages[existingIndex])) {
        nextStages[existingIndex] = mergedStage;
      }
      return;
    }

    nextStages.push(normalizeStageDraftItem({
      id: createProgramStageIdFromMetadataOption(option, usedIds),
      name: {
        de: option.label || option.value,
        en: option.label || option.value,
      },
      description: { de: "", en: "" },
      image_url: "",
      color: "",
    }));
  });

  return nextStages;
}

async function addStageMetadataOptions(options, { selectLastAdded = false } = {}) {
  const normalizedOptions = (Array.isArray(options) ? options : [])
    .map((option) => ({
      value: normalizeStageLookupText(option?.value),
      label: String(option?.label || option?.value || "").trim(),
    }))
    .filter((option) => option.value);
  if (normalizedOptions.length === 0) return;

  const nextStages = normalizeStageDraftRows(stageDraft.value);
  const usedIds = new Set(nextStages.map((stage) => String(stage?.id || "").trim()).filter(Boolean));
  let changed = false;
  let lastAddedIndex = -1;

  normalizedOptions.forEach((option) => {
    const existingIndex = findStageDraftIndexForMetadataOption(nextStages, option);
    if (existingIndex >= 0) {
      const mergedStage = mergeMetadataOptionIntoStageDraft(nextStages[existingIndex], option);
      if (JSON.stringify(mergedStage) !== JSON.stringify(nextStages[existingIndex])) {
        nextStages[existingIndex] = mergedStage;
        changed = true;
      }
      return;
    }

    nextStages.push(normalizeStageDraftItem({
      id: createProgramStageIdFromMetadataOption(option, usedIds),
      name: {
        de: option.label || option.value,
        en: option.label || option.value,
      },
      description: { de: "", en: "" },
      image_url: "",
      color: "",
    }));
    changed = true;
    lastAddedIndex = nextStages.length - 1;
  });

  if (!changed) return;
  stageDraft.value = nextStages;
  if (selectLastAdded && lastAddedIndex >= 0) {
    selectedStageDraftIndex.value = lastAddedIndex;
  }
  await saveStageDraft();
}

async function addSelectedStageFromMetadataOptions() {
  const selectedValue = String(selectedStageOptionValue.value || "").trim();
  if (!selectedValue) return;
  const selectedOption = selectedStageMetadataOptionEntries.value.find((option) =>
    option.value === selectedValue
  );
  if (!selectedOption) return;
  await addStageMetadataOptions([selectedOption], { selectLastAdded: true });
}

async function addAllMissingStagesFromMetadataOptions() {
  await addStageMetadataOptions(selectedStageMetadataOptionEntries.value);
}

function removeStageDraft(index) {
  if (index < 0 || index >= stageDraft.value.length) return;
  const removed = stageDraft.value[index];
  stageDraft.value.splice(index, 1);
  const removedId = String(removed?.id || "").trim();
  if (removedId) {
    clearProgramItemPagePollTimer("stage", removedId);
    const nextJobs = {
      stage: { ...(programItemPageJobs.value.stage || {}) },
      gig: { ...(programItemPageJobs.value.gig || {}) },
    };
    const nextTemplateRegenerationBusy = {
      stage: { ...(programItemTemplateRegenerationBusy.value.stage || {}) },
      gig: { ...(programItemTemplateRegenerationBusy.value.gig || {}) },
    };
    delete nextJobs.stage[removedId];
    delete nextTemplateRegenerationBusy.stage[removedId];
    programItemPageJobs.value = nextJobs;
    programItemTemplateRegenerationBusy.value = nextTemplateRegenerationBusy;
  }
  if (selectedStageDraftIndex.value === index) selectedStageDraftIndex.value = -1;
  if (selectedStageDraftIndex.value > index) selectedStageDraftIndex.value -= 1;
}

async function saveStageDraft() {
  const normalizedStages = normalizeStageDraftRows(stageDraft.value);
  const normalizedGigs = normalizeGigDraftRows(gigDraft.value, normalizedStages);
  await persistProgramCatalog({
    stages: normalizedStages,
    gigs: normalizedGigs,
  });
}

function isGigGenreSelected(item, value) {
  const normalizedValue = String(value ?? "").trim();
  if (!normalizedValue) return false;
  return normalizeProgramGenreSelection(item?.genre_selection).includes(normalizedValue);
}

function setGigGenreSelection(item, values) {
  if (!item || typeof item !== "object") return;
  item.genre_selection = normalizeProgramGenreSelection(values);
}

function toggleGigGenreSelection(item, value, selected) {
  if (!item || typeof item !== "object") return;
  const normalizedValue = String(value ?? "").trim();
  if (!normalizedValue) return;
  const currentValues = normalizeProgramGenreSelection(item.genre_selection);
  const nextValues = selected
    ? [...currentValues, normalizedValue]
    : currentValues.filter((entry) => entry !== normalizedValue);
  setGigGenreSelection(item, nextValues);
}

function removeGigDraft(index) {
  if (index < 0 || index >= gigDraft.value.length) return;
  const removed = gigDraft.value[index];
  gigDraft.value.splice(index, 1);
  const removedId = String(removed?.id || "").trim();
  if (removedId) {
    clearProgramItemPagePollTimer("gig", removedId);
    const nextJobs = {
      stage: { ...(programItemPageJobs.value.stage || {}) },
      gig: { ...(programItemPageJobs.value.gig || {}) },
    };
    const nextTemplateRegenerationBusy = {
      stage: { ...(programItemTemplateRegenerationBusy.value.stage || {}) },
      gig: { ...(programItemTemplateRegenerationBusy.value.gig || {}) },
    };
    delete nextJobs.gig[removedId];
    delete nextTemplateRegenerationBusy.gig[removedId];
    programItemPageJobs.value = nextJobs;
    programItemTemplateRegenerationBusy.value = nextTemplateRegenerationBusy;
  }
  if (selectedGigDraftIndex.value === index) selectedGigDraftIndex.value = -1;
  if (selectedGigDraftIndex.value > index) selectedGigDraftIndex.value -= 1;
}

async function saveGigDraft(saveIndex = null) {
  const normalizedGigs = normalizeGigDraftRows(gigDraft.value, stageDraft.value);
  const normalizedStages = normalizeStageDraftRows(stageDraft.value);
  const rawGigIndex = resolveGigDraftIndexFromSaveIndex(saveIndex);
  const targetGig = rawGigIndex >= 0 && rawGigIndex < normalizedGigs.length
    ? normalizedGigs[rawGigIndex]
    : null;

  if (targetGig && String(targetGig.id || "").trim()) {
    await queueSaveGigDraftByRawIndex(rawGigIndex, { delay: 0 });
    return;
  }

  await persistProgramCatalog({
    stages: normalizedStages,
    gigs: normalizedGigs,
  });
}

function hasGigFieldChange(gig, fieldName = "") {
  const field = String(fieldName || "").trim();
  if (!field) return false;
  if (field === "stage") return hasGigStageChange(gig);
  return false;
}

function hasGigTimeChange(gig) {
  if (!isGigRegisterChangesEnabled(gig)) return false;
  if (isGigChangeDetailsDisabled(gig)) return false;
  const previousStart = normalizeGigDateTimeValue(
    gig?.previous_start || composeGigDateTimeValue(gig?.previous_day, gig?.previous_start_time)
  );
  const previousEnd = normalizeGigDateTimeValue(
    gig?.previous_end || composeGigDateTimeValue(gig?.previous_day, gig?.previous_end_time)
  );
  const currentStart = normalizeGigDateTimeValue(
    gig?.start || composeGigDateTimeValue(gig?.day, gig?.start_time)
  );
  const currentEnd = normalizeGigDateTimeValue(
    gig?.end || composeGigDateTimeValue(gig?.day, gig?.end_time)
  );
  const previousDay = extractGigDatePart(previousStart);
  const currentDay = extractGigDatePart(currentStart);
  return (
    (previousDay && previousDay !== currentDay)
    || (previousStart && previousStart !== currentStart)
    || (previousEnd && previousEnd !== currentEnd)
  );
}

function hasGigDayChange(gig) {
  if (!isGigRegisterChangesEnabled(gig)) return false;
  if (isGigChangeDetailsDisabled(gig)) return false;
  const previousDay = extractGigDatePart(
    gig?.previous_start || composeGigDateTimeValue(gig?.previous_day, gig?.previous_start_time)
  );
  const currentDay = extractGigDatePart(
    gig?.start || composeGigDateTimeValue(gig?.day, gig?.start_time)
  );
  return Boolean(previousDay && previousDay !== currentDay);
}

function hasGigPureTimeChange(gig) {
  if (!isGigRegisterChangesEnabled(gig)) return false;
  if (isGigChangeDetailsDisabled(gig)) return false;
  const previousStart = extractGigTimePart(
    gig?.previous_start || composeGigDateTimeValue(gig?.previous_day, gig?.previous_start_time)
  );
  const previousEnd = extractGigTimePart(
    gig?.previous_end || composeGigDateTimeValue(gig?.previous_day, gig?.previous_end_time)
  );
  const currentStart = extractGigTimePart(
    gig?.start || composeGigDateTimeValue(gig?.day, gig?.start_time)
  );
  const currentEnd = extractGigTimePart(
    gig?.end || composeGigDateTimeValue(gig?.day, gig?.end_time)
  );
  return (
    (previousStart && previousStart !== currentStart)
    || (previousEnd && previousEnd !== currentEnd)
  );
}

function hasGigStageChange(gig) {
  if (!isGigRegisterChangesEnabled(gig)) return false;
  if (isGigChangeDetailsDisabled(gig)) return false;
  const previousStage = normalizeStageLookupText(gig?.previous_stage);
  const currentStage = normalizeStageLookupText(gig?.stage);
  return Boolean(previousStage && previousStage !== currentStage);
}

function isGigNew(gig) {
  if (isGigCanceled(gig)) return false;
  return Boolean(isGigRegisterChangesEnabled(gig) && gig?.highlight_changes);
}

function isGigChanged(gig) {
  if (!gig || typeof gig !== "object") return false;
  if (!isGigRegisterChangesEnabled(gig)) return false;
  if (Boolean(gig.canceled)) return true;
  if (hasGigTimeChange(gig)) return true;
  if (hasGigStageChange(gig)) return true;
  return Boolean(gig.highlight_changes);
}

function oldGigStartTime(gig) {
  return (
    extractGigTimePart(
      gig?.previous_start || composeGigDateTimeValue(gig?.previous_day, gig?.previous_start_time)
    )
    || extractGigTimePart(gig?.start || composeGigDateTimeValue(gig?.day, gig?.start_time))
    || ""
  );
}

function oldGigEndTime(gig) {
  return (
    extractGigTimePart(
      gig?.previous_end || composeGigDateTimeValue(gig?.previous_day, gig?.previous_end_time)
    )
    || extractGigTimePart(gig?.end || composeGigDateTimeValue(gig?.day, gig?.end_time))
    || ""
  );
}

function oldGigTimeRange(gig) {
  return `${oldGigStartTime(gig)} - ${oldGigEndTime(gig)}`;
}

function oldGigTitle(gig) {
  return localizedText(gigTitle(gig));
}

function oldGigGenre(gig) {
  return localizedText(gig?.genre);
}

function oldGigStageName(gig) {
  const previousStage = normalizeStageLookupText(gig?.previous_stage);
  return getStageName(previousStage || getGigStage(gig));
}

function clearCloseGigTimer() {
  if (closeGigTimer) {
    clearTimeout(closeGigTimer);
    closeGigTimer = null;
  }
}

function closeExpandedGig() {
  if (!expandedGig.value) return;
  if (!isGigPopupMode.value) {
    expandedGig.value = null;
    closingGig.value = null;
    expandedGigDescriptionOpen.value = false;
    clearCloseGigTimer();
    return;
  }

  const gigId = expandedGig.value;
  closingGig.value = gigId;
  expandedGigDescriptionOpen.value = false;
  clearCloseGigTimer();
  closeGigTimer = setTimeout(() => {
    if (closingGig.value === gigId) {
      expandedGig.value = null;
      closingGig.value = null;
    }
    closeGigTimer = null;
  }, 130);
}

function normalizeGigId(value) {
  return String(value || "").trim();
}

function openGigPopup(gigId) {
  const normalizedGigId = normalizeGigId(gigId);
  if (!normalizedGigId) return;
  clearCloseGigTimer();
  closingGig.value = null;
  expandedGigDescriptionOpen.value = false;
  expandedGig.value = normalizedGigId;
}

function toggleGig(gigId) {
  const normalizedGigId = normalizeGigId(gigId);
  if (!normalizedGigId) return;
  if (expandedGig.value === normalizedGigId) {
    closeExpandedGig();
    return;
  }
  openGigPopup(normalizedGigId);
}

function getGigDescriptionText(gig) {
  return String(localizedText(gig?.description) || "").trim();
}

function hasGigDescription(gig) {
  return Boolean(getGigDescriptionText(gig));
}

function isGigDescriptionVisible(gig) {
  const gigId = String(gig?.id || "").trim();
  return Boolean(
    gigId &&
    expandedGig.value === gigId &&
    expandedGigDescriptionOpen.value &&
    hasGigDescription(gig)
  );
}

function toggleGigDescription(gig) {
  const gigId = String(gig?.id || "").trim();
  if (!gigId || expandedGig.value !== gigId || !hasGigDescription(gig)) return;
  expandedGigDescriptionOpen.value = !expandedGigDescriptionOpen.value;
}

function getAdjacentPopupGig(gigOrId, direction) {
  const gigId = String(typeof gigOrId === "object" ? gigOrId?.id : gigOrId || "").trim();
  if (!gigId) return null;
  const items = visiblePopupNavigationGigs.value;
  const currentIndex = items.findIndex((gig) => String(gig?.id || "").trim() === gigId);
  if (currentIndex < 0) return null;
  const nextIndex = currentIndex + (direction < 0 ? -1 : 1);
  if (nextIndex < 0 || nextIndex >= items.length) return null;
  return items[nextIndex] || null;
}

function canNavigateExpandedGig(gig, direction) {
  return Boolean(getAdjacentPopupGig(gig, direction));
}

function navigateExpandedGig(direction) {
  const nextGig = getAdjacentPopupGig(expandedGig.value, direction);
  if (!nextGig?.id) return;
  clearCloseGigTimer();
  closingGig.value = null;
  expandedGigDescriptionOpen.value = false;
  expandedGig.value = normalizeGigId(nextGig.id);
}

function toggleStageFilter(stageId) {
  if (hasFixedStageSelection.value) return;
  filterStage.value = filterStage.value === stageId ? null : stageId;
}

function openStageDetail(stage) {
  stageDetailOpen.value = stage;
}

</script>

<style scoped>
.program-container {
  --program-stage-row-height: 100px;
  --program-stage-row-height-solo: 150px;
  --program-stage-row-height-mobile: 80px;
  --program-stage-row-height-solo-mobile: 120px;
  --program-date-selection-color: #4f46e5;
  --program-date-selection-text-color: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* Debug */
.debug-info {
  font-size: 10px;
  color: #888;
  padding: 6px 10px;
  background: linear-gradient(135deg, #f5f5f5, #ebebeb);
  border-radius: 20px;
  font-family: monospace;
}

/* Program selection and controls */
.program-selection-bar,
.program-controls-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.program-selection-bar {
  align-items: flex-start;
}

.program-selection-left,
.program-selection-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.program-selection-left {
  flex: 1 1 260px;
  justify-content: flex-start;
}

.program-selection-right {
  flex: 1 1 260px;
  justify-content: flex-end;
}

.program-selection-right--centered {
  flex-basis: 100%;
  justify-content: center;
}

.program-selection-right .stage-tabs,
.program-selection-right .stage-pills {
  justify-content: flex-end;
}

.program-selection-right--centered .stage-tabs,
.program-selection-right--centered .stage-pills {
  justify-content: center;
}

.program-controls-bar .view-toggle {
  margin-left: auto;
}

.program-changes-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.changes-day-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.9rem;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
}

.changes-day-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  color: #0f172a;
}

.changes-stage-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.changes-stage-title {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: #334155;
}

.changes-gig-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.changes-gig-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-start;
  gap: 0.75rem;
  padding: 0.625rem 0.75rem;
  border: 1px solid #dbeafe;
  border-radius: 10px;
  background: #ffffff;
}

.changes-gig-time {
  font-size: 0.85rem;
  color: #1e293b;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.changes-gig-title {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: #0f172a;
}

.changes-gig-stage {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.82rem;
  color: #334155;
}

/* Now Playing View */
.program-now-view {
  padding: 0.5rem 0;
}

.now-view-columns {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.now-stage-column {
  flex: 1 1 160px;
  min-width: 140px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-radius: 14px;
  overflow: hidden;
  border: 3px solid rgba(0, 0, 0, 0.07);
}

.now-stage-header {
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #fff;
  background: var(--stage-color, #6366f1);
}

.now-gig-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.625rem 0.75rem;
  background: #fff;
}

.now-gig-card--playing {
  background: #f5f3ff;
}

.now-gig-card--empty {
  background: #f8fafc;
}

.now-badge {
  display: inline-block;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #fff;
  background: var(--stage-color, #6366f1);
  border-radius: 4px;
  padding: 0.15em 0.45em;
  width: fit-content;
}

.now-next-label {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #94a3b8;
}

.now-empty-label {
  font-size: 0.82rem;
  color: #94a3b8;
}

.now-gig-title {
  font-size: 0.9rem;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.2;
}

.now-gig-time {
  font-size: 0.78rem;
  color: #64748b;
}

.now-next-up {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.5rem 0.75rem;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  background: #f8fafc;
}

.now-next-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: #334155;
}

.now-next-time {
  font-size: 0.75rem;
  color: #94a3b8;
}

/* Group Toggle */
.group-toggle {
  display: flex;
  gap: 0.25rem;
  padding: 0.25rem;
  background: linear-gradient(135deg, #f0f4f8, #e4e8ec);
  border-radius: 14px;
}

.group-btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 12px;
  background: transparent;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s ease;
}

.group-btn:hover {
  background: rgba(255, 255, 255, 0.6);
  color: #334155;
}

.group-btn.active {
  background: white;
  color: #4f46e5;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* Day Tabs */
.day-tabs {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.day-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.625rem 1rem;
  border: none;
  border-radius: 5px;
  background: linear-gradient(135deg, #f0f4f8, #e4e8ec);
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
  min-width: 70px;
}

.day-tab:hover {
  transform: translateY(-1px);
}

.day-tab.active {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--program-date-selection-color) 88%, white),
    var(--program-date-selection-color)
  );
  color: var(--program-date-selection-text-color, #ffffff);
  transform: translateY(-1px);
}

.day-name {
  font-size: 0.6875rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.7;
}

.day-tab.active .day-name {
  opacity: 0.9;
}

.day-date {
  font-size: 0.9375rem;
  font-weight: 600;
  margin-top: 2px;
}

/* Stage Tabs */
.stage-tabs {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.stage-tab {
  padding: 0.625rem 1.25rem;
  border: 2px solid var(--stage-color, #e2e8f0);
  border-radius: 20px;
  background: transparent;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--stage-color, #64748b);
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.stage-tab:hover {
  background: color-mix(in srgb, var(--stage-color) 15%, transparent);
  transform: translateY(-2px);
}

.stage-tab.active {
  background: var(--stage-color, #4f46e5);
  color: white;
  border-color: var(--stage-color, #4f46e5);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px color-mix(in srgb, var(--stage-color) 40%, transparent);
}

/* View Toggle */
.view-toggle {
  display: flex;
  gap: 0.25rem;
  padding: 0.25rem;
  background: linear-gradient(135deg, #f0f4f8, #e4e8ec);
  border-radius: 14px;
}

.view-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s ease;
}

.view-btn:hover {
  background: rgba(255, 255, 255, 0.6);
  color: #334155;
}

.view-btn.active {
  background: white;
  color: #4f46e5;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* Stage Pills */
.stage-pills {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: center;
}

.stage-pill {
  padding: 0.5rem 1rem;
  border: 2px solid var(--stage-color, #e2e8f0);
  border-radius: 20px;
  background: transparent;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--stage-color, #64748b);
  cursor: pointer;
  transition: all 0.2s ease;
}

.stage-pill:hover {
  background: var(--stage-color, #e2e8f0);
  color: white;
}

.stage-pill.active {
  background: var(--stage-color, #4f46e5);
  color: white;
  border-color: var(--stage-color, #4f46e5);
}

.stage-pill.clear-filter {
  border-color: #94a3b8;
  color: #64748b;
  font-weight: 500;
}

.stage-pill.clear-filter.active {
  background: #64748b;
  border-color: #64748b;
  color: #ffffff;
}

.stage-pill.clear-filter:hover {
  background: #94a3b8;
  color: white;
}

/* Stage Detail Panel */
.stage-detail-panel {
  margin-bottom: 1rem;
}

.stage-detail-header {
  display: flex;
  gap: 1.5rem;
  padding: 1.5rem;
  background: linear-gradient(135deg, 
    color-mix(in srgb, var(--stage-color) 12%, white),
    color-mix(in srgb, var(--stage-color) 6%, white)
  );
  border-left: 4px solid var(--stage-color);
}

.stage-detail-info {
  flex: 1;
}

.stage-detail-name {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--stage-color);
  margin: 0 0 0.5rem 0;
}

.stage-detail-description {
  font-size: 0.9375rem;
  color: #4b5563;
  margin: 0;
  line-height: 1.6;
}

/* Grid View */
.grid-view {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

/* Grid Layout - Fixed labels + Scrollable tracks */
.grid-layout {
  display: flex;
  gap: 0;
}

.labels-column {
  flex-shrink: 0;
  width: 140px;
  display: flex;
  flex-direction: column;
}


.stage-labels {
  display: flex;
  flex-direction: column;
  gap: 0; /* Using margin for animated gaps */
}

.stage-labels .stage-label {
  margin-bottom: 1rem;
}

.stage-labels .stage-label:last-child {
  margin-bottom: 0;
}

.tracks-scroll-container {
  flex: 1;
  overflow-x: auto;
  overflow-y: visible;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none; /* Firefox */
}

.tracks-scroll-container::-webkit-scrollbar {
  display: none; /* Chrome, Safari */
}

.tracks-scroll-content {
  min-width: 100%;
}

.gigs-tracks {
  display: flex;
  flex-direction: column;
  gap: 0; /* Using margin for animated gaps */
  overflow: visible;
  position: relative;
}

.gigs-tracks .gigs-track {
  margin-bottom: 1rem;
}

.gigs-tracks .gigs-track:last-child {
  margin-bottom: 0;
}

/* Time Grid Lines */
.time-grid-lines {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.time-grid-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  transform: translateX(-50%);
}

.time-grid-line.hour-line {
  background: rgba(0, 0, 0, 0.25);;
}

.time-grid-line.quarter-line {
  background: rgba(0, 0, 0, 0.05);;
}

.time-grid-label {
  position: absolute;
  top: 4px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.625rem;
  font-weight: 600;
  color: #94a3b8;
  white-space: nowrap;
  pointer-events: none;
  display: none;
}

.current-time-marker {
  position: absolute;
  top: 8px;
  bottom: 8px;
  width: 0;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  pointer-events: none;
  z-index: 0;
}

.current-time-marker--full {
  top: 0;
  bottom: 0;
}

.current-time-line {
  width: 2px;
  flex: 1;
  background: #dc2626;
  margin: -3px 0;
}

.current-time-dot {
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
}

.current-time-dot--start {
  border-top: 8px solid #dc2626;
}

.current-time-dot--end {
  border-bottom: 8px solid #dc2626;
}

/* Stage lanes layout */
.stage-lanes {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.stage-label {
  width: 140px;
  min-width: 140px;
  min-height: var(--program-stage-row-height);
  max-height: var(--program-stage-row-height-mobile);
  padding: 1rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--lane-color, #64748b);
  background: linear-gradient(135deg, 
    color-mix(in srgb, var(--lane-color) 12%, white),
    color-mix(in srgb, var(--lane-color) 6%, white)
  );
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  justify-content: center;
  align-items: center;
  line-height: 1.2;
  text-align: center;
}

.stage-label:hover {
  background: linear-gradient(135deg, 
    color-mix(in srgb, var(--lane-color) 20%, white),
    color-mix(in srgb, var(--lane-color) 12%, white)
  );
}

.stage-label:hover .stage-expand-icon {
  opacity: 1;
  transform: translateX(4px);
}

.stage-label-text {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.stage-name {
  font-size: 0.9375rem;
  font-weight: 700;
}

.stage-gig-count {
  font-size: 0.6875rem;
  font-weight: 500;
  opacity: 0.7;
}

.stage-expand-icon {
  position: absolute;
  right: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  font-size: 1rem;
  opacity: 0.3;
  transition: all 0.2s ease;
}

/* Day lanes in stage view */
.day-lanes .stage-lane {
  min-height: var(--program-stage-row-height);
}

.day-label {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--lane-color) 12%, white),
    color-mix(in srgb, var(--lane-color) 6%, white)
  );
  color: var(--lane-color, #64748b);
  cursor: default;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.day-label:hover {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--lane-color) 20%, white),
    color-mix(in srgb, var(--lane-color) 12%, white)
  );
}

.day-label-name {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.9;
}

.day-label-date {
  font-size: 1rem;
  font-weight: 600;
}

.gigs-track {
  position: relative;
  background: #fff4;
  min-height: var(--program-stage-row-height);
  padding: 12px 0;
  transition: min-height 0.4s cubic-bezier(0.4, 0, 0.2, 1),
              max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1),
              opacity 0.3s ease,
              margin 0.4s cubic-bezier(0.4, 0, 0.2, 1),
              padding 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: visible;
}

/* Stage visibility transitions */
.stage-label,
.gigs-track {
  transition: min-height 0.4s cubic-bezier(0.4, 0, 0.2, 1),
              max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1),
              opacity 0.3s ease,
              margin 0.4s cubic-bezier(0.4, 0, 0.2, 1),
              padding 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.stage-label.stage-view-day-muted,
.gigs-track.stage-view-day-muted,
.list-day-group.stage-view-day-muted {
  opacity: 0.42;
}

.stage-label.stage-hidden,
.gigs-track.stage-hidden {
  min-height: 0 !important;
  max-height: 0 !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  margin-top: 0 !important;
  margin-bottom: 0 !important;
  opacity: 0;
  pointer-events: none;
  overflow: hidden;
}

.stage-label.stage-solo,
.gigs-track.stage-solo {
  min-height: var(--program-stage-row-height-solo);
  margin-bottom: 0;
}

.program-container.is-mobile-view .stage-label.stage-solo,
.program-container.is-mobile-view .gigs-track.stage-solo {
  min-height: var(--program-stage-row-height-solo-mobile);
}

/* Gig Bubbles */
.gig-bubble {
  position: absolute;
  top: 12px;
  bottom: 12px;
  left: var(--gig-left, 0%);
  width: var(--gig-width, 100%);
  min-height: 76px;
  background: linear-gradient(135deg, 
    var(--lane-color, #4f46e5),
    color-mix(in srgb, var(--lane-color) 85%, black)
  );
  border-radius: 5px;
  cursor: pointer;
  transition:
    border-radius 0.14s ease,
    box-shadow 0.14s ease,
    opacity 0.14s ease;
  overflow: hidden;
  z-index: 1;
}

.gig-bubble:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 22px color-mix(in srgb, var(--lane-color) 30%, transparent);
  z-index: 10;
}

.gig-bubble.gig-muted:not(.expanded) {
  opacity: 0.36;
  filter: saturate(0.42) brightness(1.04);
}

.gig-bubble.gig-muted:not(.expanded):hover {
  opacity: 0.58;
}

.gig-bubble.gig-fixed-focus:not(.expanded) {
  z-index: 3;
  box-shadow:
    0 0 0 2px rgba(255, 255, 255, 0.9),
    0 10px 26px color-mix(in srgb, var(--lane-color) 34%, transparent);
}

.gig-bubble.expanded {
  position: fixed;
  top: 50%;
  bottom: auto;
  left: 50%;
  right: auto;
  transform: translate(-50%, -50%) scale(1);
  width: min(520px, 92vw, calc(78vh - 4.75rem));
  max-width: 90vw;
  max-height: none;
  min-height: auto;
  height: auto;
  z-index: 2147483500;
  border-radius: 0;
  overflow: visible;
  box-shadow: 0 25px 70px rgba(0, 0, 0, 0.35);
  animation: gig-popup-in 0.14s ease-out both;
  isolation: isolate;
}

.gig-bubble.expanded:hover {
  transform: translate(-50%, -50%) scale(1);
}

.gig-bubble.expanded.closing {
  pointer-events: none;
  animation: gig-popup-out 0.13s ease-in forwards;
}

@keyframes gig-popup-in {
  from {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.985);
  }
  to {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
  }
}

@keyframes gig-popup-out {
  from {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
  }
  to {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.985);
  }
}

@keyframes gig-popup-in-mobile {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes gig-popup-out-mobile {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}

.gig-bubble-content {
  padding: 0.25rem 0.5rem;
  color: white;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.gig-bubble.expanded .gig-bubble-content {
  position: relative;
  padding: 0;
  width: 100%;
  height: auto;
  min-height: 0;
  aspect-ratio: 1 / 1;
  overflow: hidden;
}

.gig-bubble.expanded .gig-bubble-content::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.88) 0%, rgba(0, 0, 0, 0.58) 34%, rgba(0, 0, 0, 0.08) 70%, rgba(0, 0, 0, 0.14) 100%);
}

.gig-bubble.expanded .gig-bubble-details {
  position: static;
  display: block;
  flex: 0 0 auto;
  min-height: 0;
  padding: 0;
  border: 0;
}

.gig-bubble-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.gig-bubble.expanded .gig-bubble-main {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.45rem;
  padding: 6rem 1.5rem 1.5rem;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.86) 0%, rgba(0, 0, 0, 0.58) 54%, rgba(0, 0, 0, 0) 100%);
  pointer-events: none;
}

.gig-bubble.expanded.gig-description-visible .gig-bubble-main {
  top: 0;
  justify-content: flex-end;
  padding: 2.5rem 1.5rem 1.5rem;
}

.gig-bubble-summary {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.45rem;
  min-width: 0;
  width: 100%;
}

.gig-description-panel {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 1rem;
  width: 100%;
  min-height: 0;
  max-height: 100%;
  color: #ffffff;
  pointer-events: auto;
  overflow: hidden;
}

.gig-description-title {
  flex: 0 0 auto;
  margin: 0;
  color: #ffffff;
  font-family: var(--header-font-family);
  font-size: clamp(1.25rem, 4vw, 2rem);
  font-weight: var(--header-font-weight, 800);
  line-height: 1.08;
  text-align: center;
  text-shadow: 0 2px 14px rgba(0, 0, 0, 0.45);
  overflow-wrap: anywhere;
}

.gig-description-text {
  flex: 1 1 auto;
  width: 100%;
  min-height: 0;
  margin: 0;
  max-height: none;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  color: rgba(255, 255, 255, 0.96);
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.45;
  text-shadow: 0 2px 14px rgba(0, 0, 0, 0.4);
  white-space: pre-line;
  overflow-wrap: anywhere;
  padding-right: 0.35rem;
}

.gig-overlay-replace-enter-active,
.gig-overlay-replace-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.gig-overlay-replace-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.gig-overlay-replace-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.gig-time {
  font-size: 0.6875rem;
  font-weight: 600;
  opacity: 0.8;
}

.gig-bubble.expanded .gig-time {
  display: none;
}

.gig-title {
  font-size: 0.9375rem;
  font-weight: 700;
  line-height: 1.2;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.gig-bubble.expanded .gig-title {
  font-family: var(--header-font-family);
  font-size: 2rem;
  font-weight: var(--header-font-weight, 800);
  line-height: 1.08;
  max-width: min(100%, 18ch);
}

.gig-overlay-genre {
  display: none;
}

.gig-bubble.expanded .gig-overlay-genre {
  display: block;
  max-width: min(100%, 32ch);
  color: rgba(255, 255, 255, 0.9);
  font-size: clamp(0.8125rem, 4vw, 1.4em);
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0;
  text-transform: uppercase;
  overflow-wrap: anywhere;
}

.gig-bubble-details {
  padding-top: 0;
  border-top: 1px solid transparent;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  transition:
    max-height 0.22s ease,
    opacity 0.18s ease,
    margin-top 0.22s ease,
    padding-top 0.22s ease,
    border-color 0.18s ease;
}

.gig-bubble-details.open {
  padding-top: 1rem;
  max-height: none;
  opacity: 1;
  min-height: 0;
  overflow: hidden;
}

.gig-bubble.expanded .gig-bubble-details.open {
  padding-top: 0;
  overflow: visible;
}

.gig-detail-meta-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: nowrap;
  overflow-x: auto;
  white-space: nowrap;
}

.gig-bubble.expanded .gig-detail-meta-row {
  position: absolute;
  top: 0.875rem;
  right: 0.875rem;
  z-index: 3;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  max-width: calc(100% - 4.75rem);
  overflow: visible;
  white-space: normal;
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.gig-bubble.expanded.gig-description-visible .gig-detail-meta-row {
  opacity: 0;
  pointer-events: none;
  transform: translateY(-6px);
}

.gig-meta-chip {
  padding: 0.325rem 0.65rem;
}

.gig-genre-tag {
  background: rgba(255, 255, 255, 0.24);
}

.gig-bubble.expanded .gig-genre-tag {
  display: none;
}

.gig-day-time-tag {
  margin-left: auto;
}

.gig-bubble.expanded .gig-stage-tag,
.gig-bubble.expanded .gig-day-time-tag {
  display: inline-flex;
  align-items: center;
  margin-left: 0;
  padding: 2px 8px;
  background: rgba(15, 23, 42, 0.63);
  color: #ffffff;
  font-size: clamp(0.8125rem, 4vw, 1.4em);
  font-weight: inherit;
  line-height: 1.25;
  letter-spacing: 0.03em;
  text-align: right;
  max-width: 100%;
  overflow-wrap: anywhere;
}

.gig-details-actions {
  display: none;
  margin-top: 0.25rem;
}

.gig-bubble.expanded .gig-details-actions {
  display: grid;
  grid-template-columns: 2.75rem minmax(0, 1fr) 2.75rem;
  gap: 0.5rem;
  align-items: stretch;
  position: absolute;
  top: calc(100% + 0.75rem);
  left: 0;
  right: auto;
  width: 100%;
  z-index: 4;
  margin: 0;
  transform: none;
}

.gig-popup-primary-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
  min-width: 0;
}

.gig-popup-primary-actions--single {
  grid-template-columns: minmax(0, 1fr);
}

.gig-more-btn {
  border: 1px solid rgba(255, 255, 255, 0.45);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  color: #ffffff;
  font-size: 0.8125rem;
  font-weight: 700;
  padding: 0.45rem 0.9rem;
  cursor: pointer;
  transition: background-color 0.2s ease, transform 0.2s ease;
  white-space: nowrap;
}

.gig-popup-action,
.gig-popup-chevron,
.gig-bubble.expanded .gig-more-btn {
  appearance: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-width: 0;
  min-height: 2.75rem;
  border: none;
  border-radius: 0;
  background: rgba(15, 23, 42, 0.88);
  color: #ffffff;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
  cursor: pointer;
  transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease, opacity 0.18s ease, transform 0.18s ease;
}

.gig-popup-action,
.gig-bubble.expanded .gig-more-btn {
  padding: 0.5rem 0.65rem;
  font-size: 0.72rem;
  font-weight: 700;
  line-height: 1.08;
  letter-spacing: 0;
  text-align: center;
  text-transform: uppercase;
  white-space: normal;
  overflow-wrap: anywhere;
}

.gig-popup-chevron {
  padding: 0;
  font-size: 1rem;
  line-height: 1;
}

.gig-popup-chevron svg {
  width: 0.8rem;
  height: 0.8rem;
}

.gig-popup-action:hover:not(:disabled),
.gig-popup-chevron:hover:not(:disabled),
.gig-bubble.expanded .gig-more-btn:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.86);
  background: rgba(15, 23, 42, 1);
}

.gig-popup-action:focus-visible,
.gig-popup-chevron:focus-visible,
.gig-bubble.expanded .gig-more-btn:focus-visible {
  outline: 2px solid rgba(255, 255, 255, 0.82);
  outline-offset: 2px;
}

.gig-popup-action:active:not(:disabled),
.gig-popup-chevron:active:not(:disabled),
.gig-bubble.expanded .gig-more-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.gig-popup-action:disabled,
.gig-popup-chevron:disabled,
.gig-bubble.expanded .gig-more-btn:disabled {
  cursor: not-allowed;
  opacity: 0.38;
}

.gig-popup-action:disabled,
.gig-bubble.expanded .gig-more-btn:disabled {
  background: rgba(15, 23, 42, 0.52);
  color: rgba(255, 255, 255, 0.72);
}

.gig-more-btn:hover {
  background: rgba(255, 255, 255, 0.26);
}

.gig-description-btn.active,
.gig-description-btn.active:hover:not(:disabled) {
  border-color: #ffffff;
  background: #ffffff;
  color: #0f172a;
}

.gig-more-btn:active {
  transform: translateY(1px);
}

.changed-old {
  text-decoration: line-through;
  opacity: 0.65;
}

.change-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.625rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  padding: 0.125rem 0.375rem;
  border-radius: 999px;
}

.badge-danger {
  background: rgba(220, 38, 38, 0.15);
  color: #b91c1c;
}

.badge-warning {
  background: rgba(220, 187, 38, 0.15);
  color: #b9941c;
}

.badge-success {
  background: rgba(22, 163, 74, 0.16);
  color: #15803d;
}

.gig-bubble .change-badge {
  background: rgba(255, 255, 255, 0.2);
  color: #ffffff;
}

.gig-bubble .change-badge.badge-success {
  background: #16a34a;
  color: #ffffff;
}

.gig-bubble .change-badge.badge-warning {
  background: #f59e0b;
  color: #111827;
}

.gig-bubble.gig-canceled {
  opacity: 0.68;
}

.gig-image {
  width: 100%;
  max-width: none;
  height: auto;
  border-radius: 8px;
  margin-bottom: 0;
  object-fit: cover;
}

.gig-bubble.expanded .gig-image {
  position: absolute;
  inset: 0;
  z-index: 0;
  width: 100%;
  height: 100%;
  border-radius: 0;
  transition: transform 0.24s ease;
}

.gig-bubble.expanded .gig-image :deep(.transformed-image__viewport),
.gig-bubble.expanded .gig-image :deep(img) {
  width: 100%;
  height: 100%;
}

.gig-bubble.expanded .gig-image :deep(img) {
  transition: filter 0.24s ease;
}

.gig-bubble.expanded.gig-description-visible .gig-image {
  transform: scale(1.035);
}

.gig-bubble.expanded.gig-description-visible .gig-image :deep(img) {
  filter: blur(9px) brightness(0.58) saturate(0.9);
}

/* List View */
.list-view {
  padding: 0;
}

.list-container {
  display: flex;
  flex-direction: column;
  gap: 1.35rem;
}

.list-day-group {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.list-day-title {
  margin: 0;
  padding: 0 0.25rem;
  font-family: var(--header-font-family);
  font-weight: var(--header-font-weight, 800);
  text-align: center;
  text-transform: uppercase;
}

.list-day-items {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.list-card {
  --list-card-title-color: #1f2937;
  background: white;
  position: relative;
  isolation: isolate;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s ease;
  border-left: 4px solid var(--card-color, #6B7280);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.list-card::before {
  content: "";
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  left: 4px;
  z-index: 0;
  pointer-events: none;
  background-image: var(--list-card-bg-image, none);
  background-size: cover;
  background-position: center;
  filter: blur(2px) grayscale(1);
  transform: scale(1.08);
  transform-origin: center;
  opacity: 0.1;
}

.list-card > * {
  position: relative;
  z-index: 1;
}

.list-card:hover {
  transform: translateX(4px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.list-card:focus-visible {
  outline: 2px solid var(--card-color, #6b7280);
  outline-offset: 2px;
  transform: translateX(4px);
}

.list-card.list-card-canceled {
  opacity: 0.72;
}

.list-card-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.25rem;
}

.list-card-time {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 60px;
  color: var(--card-color, #374151);
}

.list-card-time-value {
  font-size: 1.125rem;
  font-weight: 700;
  line-height: 1.15;
}

.list-card-time-secondary {
  font-size: 0.6875rem;
  font-weight: 500;
  color: #9ca3af;
  margin-top: 2px;
  white-space: nowrap;
}

.list-card-info {
  flex: 1;
  min-width: 0;
}

.list-card-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--list-card-title-color);
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.list-card-meta {
  display: flex;
  flex-wrap: nowrap;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.75rem;
  min-width: 0;
}

.list-card-stage-genre {
  display: flex;
  align-items: baseline;
  min-width: 0;
  flex: 1 1 auto;
}

.list-card-stage {
  color: var(--card-color, #374151);
  font-weight: 600;
  white-space: nowrap;
  flex: 0 0 auto;
}

.list-card-genre {
  color: color-mix(in srgb, var(--list-card-title-color) 80%, transparent);
  font-weight: 600;
  min-width: 0;
  overflow-wrap: anywhere;
  line-height: 1.25;
}

.list-card-stage + .list-card-genre {
  margin-left: 0.5rem;
  padding-left: 0.5rem;
  border-left: 1px solid #d1d5db;
}

.list-card-chevron {
  color: #4b5563;
  align-items: center;
  display: flex;
  justify-content: center;
  flex: 0 0 auto;
  width: 1.25rem;
  font-size: 0.875rem;
  transition: transform 0.2s ease, color 0.2s ease;
}

.list-card:hover .list-card-chevron,
.list-card:focus-visible .list-card-chevron {
  color: var(--card-color, #374151);
  transform: translateX(2px);
}

.list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  color: #9ca3af;
}

.list-empty-icon {
  font-size: 2.5rem;
  margin-bottom: 0.75rem;
}

.list-empty-text {
  font-size: 1rem;
}

/* Gig Backdrop */
.gig-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(2px);
  z-index: 2147483490;
}

:global(body.program-gig-popup-open .section-admin-tabs) {
  opacity: 0;
  pointer-events: none;
}

.gig-backdrop-fade-enter-active,
.gig-backdrop-fade-leave-active {
  transition: opacity 0.16s ease;
}

.gig-backdrop-fade-enter-from,
.gig-backdrop-fade-leave-to {
  opacity: 0;
}

/* Stage Modal */
.stage-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.stage-modal {
  background: white;
  border-radius: 24px;
  width: 100%;
  max-width: 500px;
  max-height: 80vh;
  overflow: auto;
  position: relative;
}

.stage-modal-close {
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 1.5rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  transition: all 0.2s ease;
}

.stage-modal-close:hover {
  background: #e5e7eb;
  color: #374151;
}

.stage-modal-header {
  padding: 2rem;
  background: linear-gradient(135deg, 
    color-mix(in srgb, var(--stage-color) 15%, white),
    color-mix(in srgb, var(--stage-color) 8%, white)
  );
}

.stage-modal-name {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--stage-color);
  margin: 0 0 0.5rem 0;
}

.stage-modal-description {
  font-size: 0.9375rem;
  color: #4b5563;
  line-height: 1.6;
  margin: 0;
}

.stage-modal-gigs {
  padding: 1.5rem 2rem 2rem;
}

.stage-modal-gigs-title {
  font-size: 0.875rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #6b7280;
  margin: 0 0 1rem 0;
}

.stage-modal-gig-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.stage-modal-gig {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.875rem;
  background: #f9fafb;
  border-radius: 12px;
}

.stage-modal-gig.stage-modal-gig-canceled {
  opacity: 0.68;
}

.stage-modal-gig-time {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--stage-color);
  min-width: 100px;
}

.stage-modal-gig-title {
  flex: 1;
  font-size: 0.9375rem;
  font-weight: 600;
  color: #1f2937;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.stage-modal-gig-genre {
  font-size: 0.75rem;
  color: #9ca3af;
}

.admin-empty-hint {
  margin: 0;
  color: var(--admin-text-muted, #64748b);
  font-size: 12px;
}

.program-design-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.program-design-panel--params {
  grid-template-columns: minmax(0, 1fr);
}

.program-stage-colors-group {
  grid-column: 1 / -1;
}

.program-view-config-group {
  grid-column: 1 / -1;
  padding: 10px 12px;
  border: 1px solid var(--admin-border, #e5e7eb);
  border-radius: 8px;
  background: #fff;
}

.program-view-config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px;
}

.program-public-controls-group {
  grid-column: 1 / -1;
}

.program-public-toggle-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.5rem 1rem;
}

.program-color-group {
  padding: 10px;
  border: 1px solid var(--admin-border, #e5e7eb);
  border-radius: 8px;
  background: #fff;
}

.stage-color-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.stage-color-row:last-child {
  border-bottom: none;
}

.stage-color-name {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #374151;
  min-width: 120px;
}

.color-link-control {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.variation-select {
  min-width: 68px;
  padding: 4px 6px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  background: #fff;
  font-size: 12px;
}

.color-swatch {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  cursor: pointer;
  flex-shrink: 0;
}

.color-input-hidden {
  position: absolute;
  opacity: 0;
  pointer-events: none;
  width: 0;
  height: 0;
}

.admin-panel {
  display: grid;
  gap: 1rem;
}

.admin-panel > * {
  order: 10;
}

.program-gigs-section {
  order: 1;
}

.program-stages-section {
  order: 2;
}

.program-stage-options-panel {
  display: grid;
  gap: 0.75rem;
  padding: 0.875rem;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}

.program-stage-options-header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: center;
  color: #1f2937;
}

.program-stage-options-header span {
  color: #64748b;
  font-size: 0.8125rem;
}

.program-stage-options-controls {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) auto;
  gap: 0.75rem;
  align-items: end;
}

.program-stage-options-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.admin-section:not(:last-child) {
  margin-bottom: 0;
}

.admin-section-title {
  font-weight: 600;
  color: #374151;
  cursor: pointer;
  padding: 0.75rem;
  background: white;
  border-radius: 8px;
  list-style: none;
}

.admin-section-title::-webkit-details-marker {
  display: none;
}

.admin-section-title::before {
  content: "▸ ";
  color: #9ca3af;
}

details[open] .admin-section-title::before {
  content: "▾ ";
}

.admin-section-content {
  padding: 1rem;
  background: white;
  border-radius: 0 0 8px 8px;
  margin-top: -4px;
  gap: 10px;
  display: grid;
}

.item-pages-inline {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.item-pages-inline .field {
  flex: 1;
}

.item-pages-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.item-pages-status {
  display: inline-block;
  margin-top: 0.5rem;
  font-size: 0.8125rem;
  color: #475569;
}

.item-pages-status.success {
  color: #047857;
}

.item-pages-status.warn {
  color: #b45309;
}

.item-pages-status.error {
  color: #b91c1c;
}

.program-gig-change-fields {
  display: grid;
  gap: 12px;
  padding: 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
}

.program-gig-change-fields .field-group--disabled {
  opacity: 0.68;
}

.program-gig-change-fields .field-group--disabled .field-label,
.program-gig-change-fields .field-group--disabled .field-checkbox-label {
  color: #64748b;
  cursor: not-allowed;
}

.program-gig-change-fields .field-group--disabled .field:disabled,
.program-gig-change-fields .field-group--disabled input:disabled,
.program-gig-change-fields .field-group--disabled select:disabled {
  border-color: #cbd5e1;
  background: #f1f5f9;
  color: #64748b;
  cursor: not-allowed;
  -webkit-text-fill-color: #64748b;
}

.program-gig-change-fields .field-group--disabled .program-datetime-picker :deep(.dp__input) {
  border-color: #cbd5e1;
  background: #f1f5f9;
  color: #64748b;
  cursor: not-allowed;
}

.program-gig-change-flags {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
}

.gig-editor-footer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
  justify-content: space-between;
  padding-top: 4px;
}

.gig-editor-footer-actions .item-page-actions--page {
  justify-content: flex-end;
  margin-left: auto;
}

.gig-editor-footer-actions .item-page-actions--source {
  justify-content: flex-start;
}

.bilingual-row, .gig-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.lang-section {
  display: grid;
  gap: 8px;
}

.lang-header {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field-label {
  display: block;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #4b5563;
  margin-bottom: 0.375rem;
}

.field-label--small {
  font-size: 0.75rem;
}

.field,
.field-textarea {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #d6dce6;
  background: rgba(255, 255, 255, 0.92);
  padding: 10px 12px;
  outline: none;
  color: #1f2937;
}

.field-textarea {
  min-height: 118px;
  resize: vertical;
}

.program-datetime-picker {
  width: 100%;
}

.program-datetime-picker :deep(.dp__input_wrap) {
  width: 100%;
}

.program-datetime-picker :deep(.dp__input) {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #d6dce6;
  background: rgba(255, 255, 255, 0.92);
  color: #1f2937;
  font: inherit;
}

.program-datetime-picker :deep(.dp__input:focus) {
  border-color: rgba(59, 130, 246, 0.55);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.json-input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  font-family: monospace;
  font-size: 0.8125rem;
  resize: vertical;
}

.mapping-section {
  margin-top: 1rem;
}

.mapping-section summary {
  font-size: 0.8125rem;
  color: #6b7280;
  cursor: pointer;
  padding: 0.5rem 0;
}

.mapping-grid {
  display: grid;
  gap: 0.5rem;
  padding: 0.5rem 0;
}

.mapping-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.mapping-label {
  font-size: 0.75rem;
  color: #6b7280;
  min-width: 100px;
}

.mapping-input {
  flex: 1;
  padding: 0.375rem 0.5rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 0.8125rem;
}

.import-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 1rem;
}

.import-status {
  font-size: 0.8125rem;
}

.import-status.success {
  color: #059669;
}

.import-status.error {
  color: #dc2626;
}

/* Integration Import */
.integration-select {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 0.875rem;
}

.integration-preview {
  margin-top: 1rem;
  padding: 1rem;
  background: #f9fafb;
  border-radius: 8px;
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
  font-size: 0.8125rem;
}

.preview-time {
  color: #6b7280;
  font-size: 0.75rem;
}

.preview-keys {
  font-size: 0.75rem;
  color: #6b7280;
  margin-bottom: 0.75rem;
}

.preview-json {
  margin: 0;
  padding: 0.75rem;
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 6px;
  font-size: 0.75rem;
  overflow-x: hidden;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
}

.integration-mapping {
  margin-top: 1rem;
}

.mapping-header {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #374151;
  margin-bottom: 0.5rem;
}

.mapping-mode-tabs {
  display: inline-flex;
  gap: 0.35rem;
  background: #f3f4f6;
  border-radius: 8px;
  padding: 0.25rem;
  margin-bottom: 0.75rem;
}

.mapping-mode-tab {
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #374151;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.35rem 0.65rem;
  cursor: pointer;
}

.mapping-mode-tab.active {
  background: #111827;
  color: #fff;
}

.mapping-select {
  flex: 1;
  padding: 0.375rem 0.5rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 0.8125rem;
}

.mapping-section-group {
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: #f9fafb;
  border-radius: 8px;
}

.mapping-section-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-bottom: 0.5rem;
}

.mapping-or-divider {
  text-align: center;
  color: #9ca3af;
  font-size: 0.75rem;
  margin: 0.5rem 0;
}

.warning-text {
  color: #dc2626;
  font-size: 0.875rem;
  margin-bottom: 1rem;
}

.data-management-row {
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
}

.data-action {
  flex: 1;
  min-width: 200px;
}

.data-action-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
  margin: 0 0 0.25rem 0;
}

.data-action-title--danger {
  color: #dc2626;
}

.changes-toggle {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin-bottom: 1rem;
  font-size: 0.875rem;
  color: #374151;
}

.changes-toggle input[type="checkbox"] {
  width: 16px;
  height: 16px;
}

.event-editor-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

.event-editor-card {
  padding: 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #f8fafc;
}

.event-filter-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.event-datetime-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
}

.event-row {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 0.75rem;
  margin-top: 0.75rem;
}

.event-row-canceled {
  opacity: 0.75;
}

.dummy-data-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin: 0.35rem 0 0.5rem;
}

.program-fixate-panel {
  margin-top: 1rem;
  padding: 0.85rem 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
}

.program-fixate-panel .field-group {
  margin-bottom: 0.45rem;
}

.program-fixate-panel .field-hint {
  margin: 0;
}

.event-row-main {
  margin-bottom: 0.5rem;
}

.event-row-title {
  font-size: 0.875rem;
  font-weight: 700;
  color: #1f2937;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.event-source {
  font-size: 0.6875rem;
  font-weight: 600;
  color: #4f46e5;
  background: #e0e7ff;
  border-radius: 999px;
  padding: 0.125rem 0.375rem;
}

.event-row-meta {
  font-size: 0.75rem;
  color: #4b5563;
}

.event-row-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.event-edit-panel {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px dashed #d1d5db;
}

.image-field-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.field-row {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.item-page-route {
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  padding: 0.5rem 0.65rem;
  font-size: 0.78rem;
  color: #334155;
  background: #f8fafc;
  word-break: break-all;
}

.item-page-route--empty {
  color: #94a3b8;
}

.item-page-actions {
  display: flex;
  flex-direction: row;
  gap: 0.35rem;
}

.stage-image-picker {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.stage-image-picker__status {
  font-size: 0.78rem;
  color: #64748b;
}

.field-hint--error {
  color: #b91c1c;
}

.item-page-title-info {
  border: 1px solid #f59e0b;
  background: #fffbeb;
  color: #92400e;
  border-radius: 8px;
  padding: 0.5rem 0.65rem;
  font-size: 0.78rem;
}

.item-page-info {
  border-radius: 8px;
  padding: 0.5rem 0.65rem;
  font-size: 0.78rem;
}

.item-page-info--warning {
  border: 1px solid #f59e0b;
  background: #fffbeb;
  color: #92400e;
}

.item-page-info--info {
  border: 1px solid #93c5fd;
  background: #eff6ff;
  color: #1e3a8a;
}

.program-validation-banner {
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
  margin-bottom: 0.75rem;
  font-size: 0.82rem;
}

.program-validation-banner--error {
  border: 1px solid #fca5a5;
  background: #fef2f2;
  color: #991b1b;
}

.event-image-preview {
  width: 100%;
  max-width: 280px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  object-fit: cover;
}

.day-range-inputs {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.day-range-select {
  padding: 0.5rem 0.75rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 0.875rem;
  min-width: 100px;
}

.day-range-info {
  margin-top: 1rem;
  padding: 0.75rem;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  font-size: 0.875rem;
  color: #1e40af;
}

.day-range-debug-actions {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.35rem;
}

.day-range-debug-actions .import-status {
  margin-top: 0.15rem;
}

.field-hint {
  font-size: 0.75rem;
  color: #6b7280;
  margin-top: 0.25rem;
}

.field-group {
  display: flex;
  flex-direction: column;
}

.program-genre-selection-options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  min-height: 2.75rem;
  padding: 0.5rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
}

.program-genre-selection-options.is-disabled {
  background: #f9fafb;
}

.program-genre-selection-option {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.55rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  color: #374151;
  font-size: 0.85rem;
  line-height: 1.2;
}

.program-genre-selection-option.is-selected {
  border-color: #2563eb;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
}

.program-genre-selection-option input {
  margin: 0;
}

@media (max-width: 900px) {
  .bilingual-row {
    grid-template-columns: 1fr;
  }
}

.field-group:has(.integration-select) {
  flex-direction: row;
  align-items: center;
  gap: 0.75rem;
}

.field-group:has(.integration-select) .field-label {
  white-space: nowrap;
}

/* Stage Admin */
.stage-admin-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.stage-admin-row {
  padding: 1rem;
  background: #f9fafb;
  border-radius: 12px;
}

.stage-admin-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.stage-color-picker,
.stage-color-dot {
  width: 32px;
  height: 32px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  display: inline-block;
  flex-shrink: 0;
}

.stage-admin-name {
  font-weight: 600;
  color: #374151;
}

.stage-admin-fields {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.stage-desc-input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 0.8125rem;
  resize: vertical;
}

.stage-url-input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 0.8125rem;
}

/* =============================================
   Mobile View Styles (unified)
   Applied via .is-mobile-view class for both:
   - Real mobile devices (screen <= 768px)
   - Topbar mobile simulation
   ============================================= */
.program-container.is-mobile-view {
  gap: 1rem;
}

.program-container.is-mobile-view .program-selection-bar,
.program-container.is-mobile-view .program-controls-bar {
  flex-wrap: wrap;
  gap: 0.5rem;
}

.program-container.is-mobile-view .program-selection-left,
.program-container.is-mobile-view .program-selection-right {
  flex: 1 1 100%;
  width: 100%;
}

.program-container.is-mobile-view .program-selection-right {
  justify-content: flex-end;
}

.program-container.is-mobile-view .program-selection-right .stage-tabs,
.program-container.is-mobile-view .program-selection-right .stage-pills {
  justify-content: flex-end;
}

.program-container.is-mobile-view .program-selection-right.program-selection-right--centered {
  justify-content: center;
}

.program-container.is-mobile-view .program-selection-right.program-selection-right--centered .stage-tabs,
.program-container.is-mobile-view .program-selection-right.program-selection-right--centered .stage-pills {
  justify-content: center;
}

.program-container.is-mobile-view .group-toggle {
  order: -2;
  padding: 0.125rem;
  gap: 0.125rem;
}

.program-container.is-mobile-view .group-btn {
  padding: 0.375rem 0.625rem;
  font-size: 0.6875rem;
  border-radius: 10px;
}

.program-container.is-mobile-view .view-toggle {
  order: -1;
  margin-left: auto;
  padding: 0.125rem;
  gap: 0.125rem;
}

.program-container.is-mobile-view .view-btn {
  width: 34px;
  height: 34px;
  border-radius: 10px;
}

.program-container.is-mobile-view .view-btn svg {
  width: 16px;
  height: 16px;
}

.program-container.is-mobile-view .day-tabs {
  width: 100%;
  justify-content: flex-start;
  gap: 0.25rem;
  flex-wrap: nowrap;
}

.program-container.is-mobile-view .day-tab {
  min-width: 0;
  flex: 1;
  max-width: 72px;
  padding: 0.375rem 0.25rem;
  border-radius: 12px;
}

.program-container.is-mobile-view .day-name {
  font-size: 0.5rem;
  letter-spacing: 0;
}

.program-container.is-mobile-view .day-date {
  font-size: 0.6875rem;
}

.program-container.is-mobile-view .stage-tabs {
  width: 100%;
  justify-content: flex-start;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  padding-bottom: 0.25rem;
  gap: 0.375rem;
}

.program-container.is-mobile-view .stage-tabs::-webkit-scrollbar {
  display: none;
}

.program-container.is-mobile-view .stage-tab {
  flex-shrink: 0;
  white-space: nowrap;
  padding: 0.5rem 0.875rem;
  font-size: 0.8125rem;
}

.program-container.is-mobile-view .stage-pills {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  flex-wrap: nowrap;
  padding-bottom: 0.25rem;
}

.program-container.is-mobile-view .stage-pills::-webkit-scrollbar {
  display: none;
}

.program-container.is-mobile-view .stage-pill {
  flex-shrink: 0;
  white-space: nowrap;
}

.program-container.is-mobile-view .stage-labels .stage-label,
.program-container.is-mobile-view .gigs-tracks .gigs-track {
  margin-bottom: 0.5rem;
}

.program-container.is-mobile-view .stage-labels .stage-label:last-child,
.program-container.is-mobile-view .gigs-tracks .gigs-track:last-child {
  margin-bottom: 0;
}

.program-container.is-mobile-view .stage-label {
  width: 50px;
  min-width: 50px;
  min-height: var(--program-stage-row-height-mobile);
  padding: 0.5rem;
  border-radius: 0;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  transform: rotate(180deg);
  justify-content: center;
  align-items: center;
}

.program-container.is-mobile-view .labels-column {
  width: max-content;
}

.program-container.is-mobile-view .stage-label-text {
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.program-container.is-mobile-view .time-grid-label {
  font-size: 0.5rem;
  top: 2px;
}

.program-container.is-mobile-view .current-time-dot {
  border-left-width: 5px;
  border-right-width: 5px;
}

.program-container.is-mobile-view .current-time-dot--start {
  border-top-width: 7px;
}

.program-container.is-mobile-view .current-time-dot--end {
  border-bottom-width: 7px;
}

.program-container.is-mobile-view .stage-name {
  font-size: 0.75rem;
  white-space: wrap;
}

.program-container.is-mobile-view .stage-gig-count,
.program-container.is-mobile-view .stage-expand-icon {
  display: none;
}

.program-container.is-mobile-view .gigs-track {
  min-height: var(--program-stage-row-height-mobile);
  min-width: 600px;
  padding: 8px 0;
}

.program-container.is-mobile-view .gig-bubble {
  min-height: 64px;
  top: 8px;
  bottom: 8px;
}

.program-container.is-mobile-view .gig-bubble-content {
  padding: 0.5rem 0.625rem;
}

.program-container.is-mobile-view .gig-title {
  font-size: 0.75rem;
}

.program-container.is-mobile-view .gig-time {
  font-size: 0.5625rem;
}

.program-container.is-mobile-view .gig-bubble.expanded {
  position: fixed;
  top: 50%;
  bottom: auto;
  left: 50%;
  right: auto;
  margin: 0;
  transform: translate(-50%, -50%);
  width: min(92vw, 460px, calc(80vh - 4.25rem));
  max-width: calc(100vw - 1rem);
  max-height: none;
  overflow: visible;
  z-index: 2147483500;
  animation: gig-popup-in-mobile 0.14s ease-out both;
}

.program-container.is-mobile-view .gig-bubble.expanded:hover {
  transform: translate(-50%, -50%);
}

.program-container.is-mobile-view .gig-bubble.expanded.closing {
  transform: translate(-50%, -50%);
  animation: gig-popup-out-mobile 0.13s ease-in forwards;
}

.program-container.is-mobile-view .gig-bubble.expanded .gig-bubble-content {
  padding: 0;
}

.program-container.is-mobile-view .gig-bubble.expanded .gig-bubble-main {
  padding: 5rem 1rem 1.15rem;
}

.program-container.is-mobile-view .gig-bubble.expanded.gig-description-visible .gig-bubble-main {
  padding: 2rem 1rem 1rem;
}

.program-container.is-mobile-view .gig-bubble.expanded .gig-details-actions {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-auto-rows: minmax(2.5rem, auto);
  gap: 0.4rem;
  top: calc(100% + 0.5rem);
}

.program-container.is-mobile-view .gig-popup-primary-actions {
  grid-column: 1 / -1;
  grid-row: 1;
  gap: 0.4rem;
}

.program-container.is-mobile-view .gig-popup-chevron--previous {
  grid-column: 1;
  grid-row: 2;
}

.program-container.is-mobile-view .gig-popup-chevron--next {
  grid-column: 2;
  grid-row: 2;
}

.program-container.is-mobile-view .gig-popup-action,
.program-container.is-mobile-view .gig-bubble.expanded .gig-more-btn {
  font-size: 0.66rem;
  min-height: 2.5rem;
  padding: 0.45rem 0.45rem;
}

.program-container.is-mobile-view .gig-popup-chevron {
  min-height: 2.5rem;
}

.program-container.is-mobile-view .gig-description-text {
  max-height: min(15rem, 52vh);
  font-size: 0.875rem;
}

.program-container.is-mobile-view .gig-bubble.expanded .gig-title {
  font-size: 1.125rem;
}

.program-container.is-mobile-view .gig-backdrop {
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.program-container.is-mobile-view .day-lanes .stage-lane {
  min-height: var(--program-stage-row-height-mobile);
}

.program-container.is-mobile-view .day-label {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  transform: rotate(180deg);
  width: 50px;
  min-width: 50px;
  min-height: var(--program-stage-row-height-mobile);
  padding: 0.5rem;
  border-radius: 12px 0 0 12px;
}

.program-container.is-mobile-view .day-label-name {
  font-size: 0.625rem;
}

.program-container.is-mobile-view .day-label-date {
  font-size: 0.75rem;
}

.program-container.is-mobile-view .stage-detail-panel {
  margin-bottom: 0.75rem;
}

.program-container.is-mobile-view .stage-detail-header {
  flex-direction: column;
  padding: 1rem;
  gap: 1rem;
}

.program-container.is-mobile-view .stage-detail-name {
  font-size: 1.25rem;
}

.program-container.is-mobile-view .stage-detail-description {
  font-size: 0.875rem;
}

.program-container.is-mobile-view .list-card-header {
  padding: 0.875rem 1rem;
  gap: 0.75rem;
}

.program-container.is-mobile-view .list-card-time {
  min-width: 50px;
}

.program-container.is-mobile-view .list-card-title {
  font-size: 0.9375rem;
}

.program-container.is-mobile-view .list-card-time-value {
  font-size: 1rem;
}

.program-container.is-mobile-view .list-card-time-secondary {
  font-size: 0.625rem;
}

.program-container.is-mobile-view .stage-modal-overlay {
  padding: 0;
  align-items: flex-end;
}

.program-container.is-mobile-view .stage-modal {
  max-width: 100%;
  max-height: 85vh;
  border-radius: 24px 24px 0 0;
}

.program-container.is-mobile-view .stage-modal-header {
  padding: 1.25rem;
}

.program-container.is-mobile-view .stage-modal-name {
  font-size: 1.25rem;
}

.program-container.is-mobile-view .stage-modal-gigs {
  padding: 1rem 1.25rem 1.5rem;
}

.program-container.is-mobile-view .stage-modal-gig {
  flex-wrap: wrap;
  gap: 0.5rem;
}

.program-container.is-mobile-view .stage-modal-gig-time {
  min-width: auto;
}

.program-container.is-mobile-view .stage-modal-gig-title {
  flex-basis: 100%;
  order: -1;
}

.program-container.is-mobile-view .event-editor-grid {
  grid-template-columns: 1fr;
}

.program-container.is-mobile-view .event-row-actions {
  width: 100%;
}

.program-container.is-mobile-view .event-filter-row,
.program-container.is-mobile-view .event-datetime-row {
  grid-template-columns: 1fr;
}

.program-container.is-mobile-view .program-stage-options-controls {
  grid-template-columns: 1fr;
}

/* Extra small view adjustments */
.program-container.is-xs-view .day-tab {
  max-width: 60px;
  padding: 0.25rem 0.125rem;
}

.program-container.is-xs-view .day-name {
  font-size: 0.4375rem;
}

.program-container.is-xs-view .day-date {
  font-size: 0.5625rem;
}

.program-container.is-xs-view .group-btn {
  padding: 0.25rem 0.5rem;
  font-size: 0.625rem;
}

.program-container.is-xs-view .view-btn {
  width: 30px;
  height: 30px;
}

.program-container.is-xs-view .view-btn svg {
  width: 14px;
  height: 14px;
}

.program-container.is-xs-view .stage-label {
  width: 40px;
  min-width: 40px;
}

.program-container.is-xs-view .stage-name {
  font-size: 0.625rem;
}

.program-container.is-xs-view .time-grid-label {
  font-size: 0.5rem;
}

.program-container.is-xs-view .gig-bubble.expanded .gig-bubble-content {
  padding: 0;
}

.program-container.is-xs-view .gig-bubble.expanded .gig-title {
  font-size: 1rem;
}
</style>
