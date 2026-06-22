<template>
  <section class="admin-media admin-page">
    <AutosaveToast :message="mediaAutosaveToastMessage" :tone="mediaAutosaveToastTone" />

    <header class="page-header">
      <h1>Media</h1>
      <p class=page-subtitle>Manage uploaded media assets, tag rules, and responsive variants.</p>
    </header>

    <AdminPageTabs
      :tabs="visibleTabs"
      :model-value="activeTab"
      @update:model-value="setActiveTab"
    />

    <div v-if="activeTab === 'import'" class="import-layout">
      <div class="config-card import-card">
        <div class="card-header">
          <h2>Import by Upload</h2>
          <p class="card-hint">Drag files here or browse to add media assets.</p>
        </div>
        <div
          class="drop-zone"
          :class="{ 'drop-zone--active': isDragging }"
          @dragenter.prevent="onDragEnter"
          @dragover.prevent="onDragOver"
          @dragleave.prevent="onDragLeave"
          @drop.prevent="onDrop"
        >
          <input
            ref="fileInput"
            class="file-input"
            type="file"
            accept="image/*,image/svg+xml,.svg,video/*,application/pdf,.pdf"
            multiple
            @change="onFileSelect"
          />
          <div class="drop-zone__content">
            <strong>Drag &amp; drop files</strong>
            <span>or</span>
            <button class="btn-outline btn-sm" type="button" @click="openFilePicker">Browse Files</button>
          </div>
        </div>
        <div v-if="uploadQueue.length > 0" class="upload-queue">
          <div class="upload-queue__head">
            <h3>Import Queue</h3>
            <button class="btn-outline btn-sm" type="button" @click="clearImportQueue">Clear Session Queue</button>
          </div>
          <p class="card-hint">
            Total ETA:
            <strong>{{ formatEta(totalQueueEtaSeconds) }}</strong>
            <span v-if="averageUploadSecondsPerMb != null">
              · {{ Number(averageUploadSecondsPerMb).toFixed(1) }}s / MB
            </span>
          </p>
          <div class="upload-list">
            <div v-for="item in uploadQueue" :key="item.id" class="upload-item">
              <div class="upload-item__head">
                <strong>{{ item.name }}</strong>
                <span class="upload-status" :class="`upload-status--${item.status}`">{{ item.status }}</span>
              </div>
              <p class="tag-value">
                {{ formatFileSize(item.size) }}
                · elapsed {{ formatDuration(item.elapsed_seconds) }}
                · ETA {{ formatEta(item.estimated_remaining_seconds) }}
              </p>
              <div class="upload-track">
                <div class="upload-bar" :style="{ width: item.progress + '%' }"></div>
              </div>
              <p v-if="item.error" class="error-text">{{ item.error }}</p>
            </div>
          </div>
        </div>
        <div v-if="showRawMetadata && importMetadataResults.length > 0" class="import-meta-output">
          <div class="import-meta-output__head">
            <h3>Raw Meta Data</h3>
            <button class="btn-outline btn-sm" type="button" @click="clearImportMetadataOutput">Clear</button>
          </div>
          <div
            v-for="entry in importMetadataResults"
            :key="entry.id"
            class="import-meta-output__item"
          >
            <p class="tag-name">{{ entry.label }}</p>
            <pre>{{ entry.pretty }}</pre>
          </div>
        </div>
      </div>

      <div v-if="uploadedSessionCount > 0" class="upload-session-layout">
        <div class="upload-session-main">
          <div class="upload-session-main__head">
            <div class="card-header">
              <h2>Session Upload</h2>
              <p class="card-hint">Edit scoped author/date meta data and apply tags to uploaded assets.</p>
            </div>
            <div class="session-summary-pill session-summary-pill--count">
              <span class="session-summary-pill__label">Uploaded</span>
              <strong>{{ uploadedSessionCount }}</strong>
            </div>
          </div>
          <div class="session-upload-list">
            <div v-for="item in uploadedSessionItems" :key="`session-upload-${item.id}`" class="session-upload-card">
              <div class="session-upload-card__body">
                <div class="session-upload-card__preview">
                  <img
                    v-if="isImageUploadItem(item)"
                    :src="item.asset_thumb_url || item.preview_url || item.asset_url"
                    :alt="item.asset_filename || item.name"
                    loading="lazy"
                  />
                  <div v-else class="session-upload-card__file">{{ item.asset_filename || item.name }}</div>
                </div>
                <div class="field-grid session-filename-grid">
                  <label>
                    <span>Filename</span>
                    <input
                      v-model="item.meta_edit.filename"
                      class="field"
                      type="text"
                      placeholder="filename.ext"
                    />
                  </label>
                </div>

              <div class="session-upload-section">
                <p class="session-upload-section__title">Caption</p>
                <div class="field-grid session-meta-grid">
                  <label>
                    <span>Caption (DE, optional)</span>
                    <input
                      v-model="item.meta_edit.caption_de"
                      class="field"
                      type="text"
                      placeholder="Bildunterschrift"
                    />
                  </label>
                  <label>
                    <span>Caption (EN, optional)</span>
                    <input
                      v-model="item.meta_edit.caption_en"
                      class="field"
                      type="text"
                      placeholder="Caption"
                    />
                  </label>
                </div>
              </div>

              <div class="session-upload-section">
                <p class="session-upload-section__title">Tagging &amp; Metadata</p>
                <div class="session-tagging-tabs">
                  <button
                    class="session-tagging-tabs__btn"
                    :class="{ active: getItemTaggingMode(item) === 'auto' }"
                    type="button"
                    @click="setItemTaggingMode(item, 'auto')"
                  >
                    Auto Tagging
                  </button>
                  <button
                    class="session-tagging-tabs__btn"
                    :class="{ active: getItemTaggingMode(item) === 'manual' }"
                    type="button"
                    @click="setItemTaggingMode(item, 'manual')"
                  >
                    Manual Tagging
                  </button>
                </div>

                <div v-if="getItemTaggingMode(item) === 'auto'" class="program-item-integration">
                  <div class="inline-form program-item-integration__row">
                    <input
                      v-model="item.meta_edit.program_artist_query"
                      class="field"
                      type="text"
                      placeholder="Search artist by substring..."
                    />
                  </div>

                  <div v-if="resolveEffectiveGigForItem(item)" class="program-selection">
                    <div class="program-selection__head">
                      <p class="tag-value">
                        {{ resolveSelectedGigForItem(item) ? "Selected" : "Session default" }}:
                        <strong>{{ resolveGigArtistLabel(resolveEffectiveGigForItem(item)) || resolveEffectiveGigForItem(item)?.id }}</strong>
                        · {{ resolveGigStageLabel(resolveEffectiveGigForItem(item)) || "Unknown stage" }}
                        · {{ resolveGigIsoDay(resolveEffectiveGigForItem(item)) || "No date" }}
                      </p>
                      <button
                        v-if="resolveSelectedGigForItem(item)"
                        class="btn-outline btn-sm"
                        type="button"
                        @click="clearProgramSelectionForItem(item)"
                      >
                        Clear
                      </button>
                    </div>
                    <p class="tag-value">
                      Auto tags:
                      <strong>{{ buildProgramTagsForGig(resolveEffectiveGigForItem(item)).join(", ") || "none" }}</strong>
                    </p>
                  </div>

                  <div v-if="shouldShowProgramMatchesForItem(item)" class="program-match-list">
                    <button
                      v-for="gig in getProgramArtistMatchesForItem(item)"
                      :key="`program-match-${item.id}-${gig.id}`"
                      class="program-match-btn"
                      type="button"
                      @click="selectProgramGigForItem(item, gig)"
                    >
                      <span class="tag-name">{{ resolveGigArtistLabel(gig) || gig.id }}</span>
                      <span class="tag-value">{{ resolveGigStageLabel(gig) || "Unknown stage" }} · {{ resolveGigIsoDay(gig) || "No date" }}</span>
                    </button>
                  </div>
                  <p
                    v-else-if="String(item?.meta_edit?.program_artist_query || '').trim().length > 0"
                    class="empty-text"
                  >
                    No matching artists found.
                  </p>
                </div>
                <div v-else class="field-grid session-manual-grid">
                  <label>
                    <span>Artist</span>
                    <input
                      v-model="item.meta_edit.manual_artist"
                      class="field"
                      type="text"
                      placeholder="Artist / Gig title"
                    />
                  </label>
                  <label>
                    <span>Stage</span>
                    <input
                      v-model="item.meta_edit.manual_stage"
                      class="field"
                      type="text"
                      placeholder="Stage name"
                    />
                  </label>
                  <label>
                    <span>Date Tag (ISO)</span>
                    <VueDatePicker
                      :model-value="serverDateOnlyToLocalDate(item.meta_edit.manual_date)"
                      class="admin-date-picker"
                      :enable-time-picker="false"
                      :clearable="true"
                      :text-input="DATE_PICKER_DATE_ONLY_TEXT_INPUT_OPTIONS"
                      :formats="DATE_PICKER_DATE_ONLY_DISPLAY_FORMATS"
                      :teleport="true"
                      auto-apply
                      placeholder="Select date"
                      @update:model-value="item.meta_edit.manual_date = localDateToServerDateOnly($event)"
                    />
                  </label>
                  <label class="session-manual-wide">
                    <span>Additional Information</span>
                    <input
                      v-model="item.meta_edit.manual_additional_info"
                      class="field"
                      type="text"
                      placeholder="Additional information"
                    />
                  </label>
                </div>

                <div class="session-authorship-item">
                  <label class="variant-toggle">
                    <input v-model="item.meta_edit.override_session_authorship" type="checkbox" />
                    <span>Override session authorship for this image</span>
                  </label>
                  <div v-if="item.meta_edit.override_session_authorship" class="field-grid session-author-override-grid">
                    <label>
                      <span>Manual author</span>
                      <input
                        v-model="item.meta_edit.manual_author"
                        class="field"
                        type="text"
                        placeholder="Firstname Lastname"
                      />
                    </label>
                  </div>
                </div>
              </div>

              <div class="session-preview-row">
                <span class="tag-value">Preview:</span>
                <div class="session-preview-tags">
                  <span
                    v-for="entry in buildSessionMetadataPreviewEntries(item)"
                    :key="entry.label"
                    class="session-preview-tag"
                    :class="{ 'session-preview-tag--missing': entry.missing }"
                  >
                    {{ entry.label }}
                  </span>
                </div>
              </div>
              <p v-if="getSessionItemError(item.id)" class="error-text">{{ getSessionItemError(item.id) }}</p>
            </div>
          </div>
        </div>
        </div>

        <aside class="upload-session-side">
          <div class="session-authorship">
            <div class="session-authorship__head">
              <h3>Session Defaults</h3>
              <span class="session-authorship__badge">Applied to all uploads</span>
            </div>
            <p class="session-authorship__info">
              Global author, caption, and tagging are applied to all uploaded images by default and can be overridden per image below. Author is required; global caption and global tagging are optional.
            </p>
            <div class="field-grid session-authorship__manual-row">
              <label>
                <span>Session Author</span>
                <input
                  v-model="sessionManualAuthor"
                  class="field"
                  type="text"
                  placeholder="Firstname Lastname"
                />
              </label>
            </div>
            <div class="session-upload-section">
              <p class="session-upload-section__title">Global Caption</p>
              <div class="field-grid session-meta-grid">
                <label>
                  <span>Caption (DE, optional)</span>
                  <input
                    v-model="sessionGlobalCaptionDe"
                    class="field"
                    type="text"
                    placeholder="Bildunterschrift"
                  />
                </label>
                <label>
                  <span>Caption (EN, optional)</span>
                  <input
                    v-model="sessionGlobalCaptionEn"
                    class="field"
                    type="text"
                    placeholder="Caption"
                  />
                </label>
              </div>
            </div>
            <div class="session-upload-section">
              <p class="session-upload-section__title">Global Tagging</p>
              <div class="session-tagging-tabs">
                <button
                  class="session-tagging-tabs__btn"
                  :class="{ active: getSessionGlobalTaggingMode() === 'auto' }"
                  type="button"
                  @click="setSessionGlobalTaggingMode('auto')"
                >
                  Auto Tagging
                </button>
                <button
                  class="session-tagging-tabs__btn"
                  :class="{ active: getSessionGlobalTaggingMode() === 'manual' }"
                  type="button"
                  @click="setSessionGlobalTaggingMode('manual')"
                >
                  Manual Tagging
                </button>
              </div>

              <div v-if="getSessionGlobalTaggingMode() === 'auto'" class="program-item-integration">
                <div class="inline-form program-item-integration__row">
                  <input
                    v-model="sessionGlobalProgramArtistQuery"
                    class="field"
                    type="text"
                    placeholder="Search artist by substring..."
                  />
                </div>

                <div v-if="selectedSessionGlobalGig" class="program-selection">
                  <div class="program-selection__head">
                    <p class="tag-value">
                      Selected:
                      <strong>{{ resolveGigArtistLabel(selectedSessionGlobalGig) || selectedSessionGlobalGig?.id }}</strong>
                      · {{ resolveGigStageLabel(selectedSessionGlobalGig) || "Unknown stage" }}
                      · {{ resolveGigIsoDay(selectedSessionGlobalGig) || "No date" }}
                    </p>
                    <button class="btn-outline btn-sm" type="button" @click="clearProgramSelectionForSessionGlobal">Clear</button>
                  </div>
                  <p class="tag-value">
                    Auto tags:
                    <strong>{{ buildProgramTagsForGig(selectedSessionGlobalGig).join(", ") || "none" }}</strong>
                  </p>
                </div>

                <div v-if="shouldShowProgramMatchesForSessionGlobal()" class="program-match-list">
                  <button
                    v-for="gig in getProgramArtistMatchesForSessionGlobal()"
                    :key="`session-global-program-match-${gig.id}`"
                    class="program-match-btn"
                    type="button"
                    @click="selectProgramGigForSessionGlobal(gig)"
                  >
                    <span class="tag-name">{{ resolveGigArtistLabel(gig) || gig.id }}</span>
                    <span class="tag-value">{{ resolveGigStageLabel(gig) || "Unknown stage" }} · {{ resolveGigIsoDay(gig) || "No date" }}</span>
                  </button>
                </div>
                <p
                  v-else-if="String(sessionGlobalProgramArtistQuery || '').trim().length > 0"
                  class="empty-text"
                >
                  No matching artists found.
                </p>
              </div>
              <div v-else class="field-grid session-manual-grid">
                <label>
                  <span>Artist</span>
                  <input
                    v-model="sessionGlobalManualArtist"
                    class="field"
                    type="text"
                    placeholder="Artist / Gig title"
                  />
                </label>
                <label>
                  <span>Stage</span>
                  <input
                    v-model="sessionGlobalManualStage"
                    class="field"
                    type="text"
                    placeholder="Stage name"
                  />
                </label>
                <label>
                  <span>Date Tag (ISO)</span>
                  <VueDatePicker
                    :model-value="serverDateOnlyToLocalDate(sessionGlobalManualDate)"
                    class="admin-date-picker"
                    :enable-time-picker="false"
                    :clearable="true"
                    :text-input="DATE_PICKER_DATE_ONLY_TEXT_INPUT_OPTIONS"
                    :formats="DATE_PICKER_DATE_ONLY_DISPLAY_FORMATS"
                    :teleport="true"
                    auto-apply
                    placeholder="Select date"
                    @update:model-value="sessionGlobalManualDate = localDateToServerDateOnly($event)"
                  />
                </label>
                <label class="session-manual-wide">
                  <span>Additional Information</span>
                  <input
                    v-model="sessionGlobalManualAdditionalInfo"
                    class="field"
                    type="text"
                    placeholder="Additional information"
                  />
                </label>
              </div>
            </div>
            <div class="session-authorship__preview">
              <p class="tag-value">
                Default author tag:
                <strong :class="{ 'session-preview-tag--missing': isMissingAuthorPreviewLabel(sessionAuthorTagPreview) }">{{ sessionAuthorTagPreview }}</strong>
              </p>
              <div class="session-preview-row">
                <span class="tag-value">Global tag preview:</span>
                <div class="session-preview-tags">
                  <span v-if="sessionGlobalTaggingPreview.length === 0" class="tag-value">none</span>
                  <span
                    v-for="label in sessionGlobalTaggingPreview"
                    :key="label"
                    class="session-preview-tag"
                  >
                    {{ label }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </div>

      <div v-if="!hasActiveUploadSession" class="config-card import-card">
        <div class="card-header">
          <h2>Import by URL</h2>
          <p class="card-hint">Fetch remote media and add it directly to the library.</p>
        </div>
        <div class="import-row">
          <input
            v-model="importUrl"
            class="field"
            type="url"
            placeholder="https://example.com/image.jpg"
            @keydown.enter.prevent="importByUrl"
          />
          <input
            v-model="importFilename"
            class="field import-filename"
            type="text"
            placeholder="Optional filename"
            @keydown.enter.prevent="importByUrl"
          />
          <button
            class="btn-primary"
            type="button"
            :disabled="!canImport || importing"
            @click="importByUrl"
          >
            {{ importing ? "Importing..." : "Import" }}
          </button>
        </div>
        <p v-if="importError" class="error-text">{{ importError }}</p>
      </div>

    </div>

    <div v-else-if="activeTab === 'config'" class="tags-layout">
      <div class="config-card">
        <div class="card-header">
          <h2>Import Settings</h2>
          <p class="card-hint">Configure upload/import behavior and diagnostics.</p>
        </div>
        <div class="import-settings-list">
          <div v-if="canSeeAdvancedImportOptions" class="import-settings-group">
            <h3>Cropping</h3>
            <div class="import-setting-row">
              <label class="variant-toggle import-setting-toggle">
                <input v-model="bypassAutocropTransparentPadding" type="checkbox" />
                <span>Bypass auto-cropping transparent padding (PNG)</span>
              </label>
              <p class="import-setting-description">
                Keeps transparent PNG margins intact instead of trimming them during uploads or URL imports.
              </p>
            </div>
          </div>

          <div class="import-settings-group">
            <h3>Meta Data</h3>
            <div class="import-setting-row">
              <label class="variant-toggle import-setting-toggle">
                <input v-model="showRawMetadata" type="checkbox" />
                <span>Show raw meta data</span>
              </label>
              <p class="import-setting-description">
                Shows the latest extracted meta data payloads in the Import tab for troubleshooting mappings.
              </p>
            </div>
            <div class="import-setting-row">
              <label class="variant-toggle import-setting-toggle">
                <input v-model="metadataEnabledInput" type="checkbox" />
                <span>Extract + auto tag meta data</span>
              </label>
              <p class="import-setting-description">
                Reads embedded image meta data and turns configured fields into media tags.
              </p>
              <div v-if="metadataEnabledInput" class="metadata-rules-panel">
                <div v-if="canSeeAdvancedImportOptions" class="metadata-rules-panel__option">
                  <label class="variant-toggle import-setting-toggle">
                    <input v-model="metadataRequireAuthorInput" type="checkbox" />
                    <span>Require author meta data</span>
                  </label>
                  <p class="import-setting-description">
                    Flags missing authorship during meta data checks so imports can be completed with a session author.
                  </p>
                </div>

                <div class="metadata-rules-panel__rules">
                  <div class="card-header">
                    <h3>Meta Extraction Rules</h3>
                    <p class="card-hint">Map raw meta data keys to semantic fields (author/rights/keyword/tool/credit).</p>
                  </div>

                  <div class="inline-form">
                    <input
                      v-model="metadataSourceKeyInput"
                      class="field"
                      type="text"
                      placeholder="raw_exif.exif:copyright"
                    />
                    <select v-model="metadataTargetFieldInput" class="field">
                      <option value="author">Author</option>
                      <option value="rights">Rights</option>
                      <option value="keyword">Keyword</option>
                      <option value="tool">Tool</option>
                      <option value="credit">Credit</option>
                    </select>
                    <button class="btn-primary" type="button" :disabled="configSaving" @click="addMetadataKeyMappingRule">Add</button>
                  </div>

                  <div class="tag-list">
                    <div
                      v-for="entry in metadataKeyMappingEntries"
                      :key="`meta-key-map-${entry.source_key}-${entry.target_field}`"
                      class="tag-row"
                    >
                      <div>
                        <div class="tag-name">{{ entry.source_key }}</div>
                        <div class="tag-value">→ {{ entry.target_field }}</div>
                      </div>
                      <button class="btn-danger btn-sm" type="button" :disabled="configSaving" @click="removeMetadataKeyMappingRule(entry)">
                        Delete
                      </button>
                    </div>
                    <p v-if="metadataKeyMappingEntries.length === 0" class="empty-text">No key mapping rules yet.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div id="media-cropping-settings" class="config-card">
        <div class="card-header">
          <h2>Image Variant Cropping</h2>
          <p class="card-hint">
            Configure responsive image sizes generated on upload/import.
            Device variant widths mirror Design &gt; Responsive preview widths.
          </p>
          <p class="card-hint">
            Rows are sorted by width from min to max.
            Changes save when a field loses focus or Enter is pressed.
            Regeneration deletes stale generated variants and rebuilds all image assets with the current settings.
          </p>
        </div>
        <div class="variant-table">
          <div
            v-for="row in uploadVariantRows"
            :key="row.key"
            class="variant-table-row"
            :class="`variant-table-row--${row.kind}`"
          >
            <div class="variant-table-main">
              <label v-if="row.kind === 'device'" class="variant-toggle">
                <input
                  type="checkbox"
                  :checked="row.enabled"
                  @change="setUploadDeviceEnabled(row.device, $event.target.checked)"
                />
                <span>{{ row.label }}</span>
              </label>
              <label v-else-if="row.kind === 'fixed'" class="variant-toggle">
                <input
                  type="checkbox"
                  :checked="row.enabled"
                  @change="setUploadThumbEnabled($event.target.checked)"
                />
                <span>{{ row.label }}</span>
              </label>
              <div v-else-if="row.kind === 'custom'" class="variant-custom-main">
                <div class="variant-toggle variant-toggle--editable">
                  <input
                    v-model="uploadCustomVariants[row.index].enabled"
                    type="checkbox"
                    :aria-label="`Enable ${row.label}`"
                    @change="saveUploadVariantsConfig"
                  />
                  <input
                    v-model="uploadCustomVariants[row.index].label"
                    class="field variant-toggle-label-input"
                    type="text"
                    placeholder="Variant"
                    aria-label="Variant label"
                    @blur="commitUploadCustomVariant(row.index)"
                    @keydown.enter.prevent="$event.target.blur()"
                  />
                </div>
              </div>
              <div v-else class="variant-static-label">{{ row.label }}</div>
              <span class="variant-row-detail">{{ row.detail }}</span>
            </div>

            <div v-if="row.kind === 'custom'" class="variant-width-cell">
              <input
                v-model.number="uploadCustomVariants[row.index].width"
                class="field variant-width"
                type="number"
                min="64"
                max="4096"
                aria-label="Variant width"
                @blur="saveUploadVariantsConfig"
                @keydown.enter.prevent="$event.target.blur()"
              />
            </div>

            <div v-else-if="row.kind === 'fixed'" class="variant-width-cell">
              <input
                v-model.number="uploadThumbWidth"
                class="field variant-width"
                type="number"
                min="64"
                max="4096"
                aria-label="Thumbnail width"
                @blur="saveUploadVariantsConfig"
                @keydown.enter.prevent="$event.target.blur()"
              />
            </div>

            <div v-else-if="row.kind === 'max'" class="variant-width-cell">
              <input
                v-model.number="uploadMaxOriginalWidth"
                class="field variant-width"
                type="number"
                min="256"
                max="4096"
                aria-label="Max original width"
                @blur="saveUploadVariantsConfig"
                @keydown.enter.prevent="$event.target.blur()"
              />
            </div>

            <span v-else class="variant-width-readonly">{{ row.width }}px</span>
            <div v-if="row.kind === 'custom'" class="variant-remove-cell">
              <button class="btn-danger btn-sm" type="button" title="Remove variant" @click="removeUploadCustomVariant(row.index)">Remove</button>
            </div>
            <span v-if="row.kind !== 'custom'" class="variant-remove-cell" aria-hidden="true"></span>
          </div>
        </div>

        <div class="cropping-actions">
          <div class="cropping-actions__primary">
            <button class="btn-primary btn-sm" type="button" @click="addUploadCustomVariant">Add Variant</button>
          </div>
          <div class="cropping-actions__secondary">
            <button class="btn-outline btn-sm" type="button" @click="openResponsiveSettings">
              Responsive Settings
            </button>
            <button
              class="btn-danger"
              type="button"
              :disabled="regenerateCroppingRunning"
              @click="regenerateCroppingVariants"
            >
              {{ regenerateCroppingRunning ? "Regenerating..." : "Regenerate Cropping" }}
            </button>
          </div>
        </div>
        <p v-if="regenerateCroppingResult" class="regenerate-summary">
          Processed {{ regenerateCroppingResult.processed || 0 }},
          regenerated {{ regenerateCroppingResult.regenerated || 0 }},
          skipped {{ regenerateCroppingResult.skipped || 0 }},
          failed {{ regenerateCroppingResult.failed || 0 }}.
        </p>
        <div v-if="regenerateCroppingResult?.errors?.length" class="regenerate-errors">
          <p v-for="entry in regenerateCroppingResult.errors.slice(0, 5)" :key="`${entry.asset_id}-${entry.error}`">
            {{ entry.filename || entry.asset_id }}: {{ entry.error }}
          </p>
        </div>
      </div>

      <div class="config-card fallback-image-card">
        <div class="card-header">
          <h2>Fallback Image</h2>
          <p class="card-hint">Image used publicly when an item image field is empty.</p>
        </div>
        <div class="fallback-image-card__body">
          <ImageTransformEditor
            :image-url="globalFallbackPreviewUrl"
            :zoom="globalFallbackZoomDraft"
            :focal-x="globalFallbackFocalXDraft"
            :focal-y="globalFallbackFocalYDraft"
            :rotation="globalFallbackRotationDraft"
            ratio="1:1"
            direction="landscape"
            view-context="section_item"
            :allow-manual-url-edit="false"
            :allow-clear-image="true"
            :disabled="configSaving"
            select-image-label="Select"
            replace-image-label="Replace"
            clear-image-label="Clear"
            @update:zoom="(value) => setGlobalFallbackTransformDraft({ zoom: value })"
            @update:focal-x="(value) => setGlobalFallbackTransformDraft({ focalX: value })"
            @update:focal-y="(value) => setGlobalFallbackTransformDraft({ focalY: value })"
            @update:rotation="(value) => setGlobalFallbackTransformDraft({ rotation: value })"
            @choose-image="openGlobalFallbackMediaLibrary"
            @clear-image="clearGlobalFallbackImage"
            @commit="commitGlobalFallbackTransform"
          />
        </div>

        <MediaLibrary
          :is-open="showGlobalFallbackMediaPicker"
          :current-url="globalFallbackPreviewUrl"
          source-context="media.config.fallback.image"
          allow-clear-selection
          @close="closeGlobalFallbackMediaLibrary"
          @select="applyGlobalFallbackSelection"
        />
      </div>
    </div>

    <div v-else-if="activeTab === 'library'" class="library-layout">
      <div class="library-main">
        <div class="search-row">
          <input
            :value="searchQuery"
            class="field"
            type="text"
            placeholder="Search media..."
            @input="onSearchInput"
          />
        </div>

        <div class="library-filters">
          <div class="library-filters__head">
            <h3>Filters</h3>
            <button class="btn-outline btn-sm" type="button" @click="toggleFilterGrouping">
              {{ filtersFlattened ? "Show Groups" : "Collapse Groups" }}
            </button>
          </div>
          <div class="tag-filter-list">
            <button
              class="tag-filter-btn"
              :class="{ active: !activeTag }"
              type="button"
              @click="clearTagFilterAndFetch"
            >
              All
            </button>
          </div>
          <div v-if="!filtersFlattened" class="tag-filter-groups">
            <div v-for="group in groupedTagFilters" :key="group.key" class="tag-filter-group">
              <h4>{{ group.label }}</h4>
              <div class="tag-filter-list">
                <button
                  v-for="tag in group.tags"
                  :key="tag"
                  class="tag-filter-btn"
                  :class="{ active: activeTag === tag }"
                  type="button"
                  @click="filterByTagAndFetch(tag)"
                >
                  {{ tag }}
                </button>
              </div>
            </div>
          </div>
          <div v-else class="tag-filter-list">
            <button
              v-for="tag in flatTagFilters"
              :key="tag"
              class="tag-filter-btn"
              :class="{ active: activeTag === tag }"
              type="button"
              @click="filterByTagAndFetch(tag)"
            >
              {{ tag }}
            </button>
          </div>
        </div>

        <div ref="assetGridRef" class="asset-grid">
          <template v-for="(asset, index) in assets" :key="asset.id">
            <button
              class="asset-card"
              :class="{
                selected: !bulkEditMode && selectedId === asset.id,
                'asset-card--bulk-selected': bulkEditMode && isAssetBulkSelected(asset.id),
              }"
              type="button"
              @click="onAssetCardClick(asset)"
            >
              <span
                v-if="bulkEditMode"
                class="asset-card__bulk-indicator"
                :class="{ active: isAssetBulkSelected(asset.id) }"
              >
                {{ isAssetBulkSelected(asset.id) ? "Selected" : "Select" }}
              </span>
              <video
                v-if="isVideoAsset(asset)"
                :src="asset.url"
                class="asset-card__media"
                muted
                preload="metadata"
              ></video>
              <div v-else-if="isPdfAsset(asset)" class="asset-card__pdf" aria-label="PDF file">
                <svg
                  class="asset-card__pdf-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  aria-hidden="true"
                >
                  <path
                    d="M7 3H13.5L19 8.5V21H7V3Z"
                    stroke="currentColor"
                    stroke-width="1.5"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                  <path
                    d="M13 3V9H19"
                    stroke="currentColor"
                    stroke-width="1.5"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
                <span class="asset-card__pdf-label">PDF</span>
              </div>
              <div v-else class="asset-card__media-surface">
                <img
                  :src="assetPreviewUrl(asset)"
                  :alt="asset.filename"
                  class="asset-card__media"
                  loading="lazy"
                />
              </div>
            </button>

            <transition
              @before-enter="onInlineEditorBeforeEnter"
              @enter="onInlineEditorEnter"
              @after-enter="onInlineEditorAfterEnter"
              @before-leave="onInlineEditorBeforeLeave"
              @leave="onInlineEditorLeave"
            >
              <div
                v-if="!bulkEditMode && selectedAsset && selectedEditorInsertIndex === index"
                class="asset-inline-editor"
              >
                <div class="asset-inline-editor__content">
                  <div class="asset-inline-editor__media-column">
                    <div class="selected-preview">
                      <video
                        v-if="isVideoAsset(selectedAsset)"
                        :src="selectedAsset.url"
                        controls
                        muted
                        preload="metadata"
                      ></video>
                      <div v-else-if="isPdfAsset(selectedAsset)" class="selected-preview__pdf" aria-label="PDF file">
                        <svg
                          class="selected-preview__pdf-icon"
                          viewBox="0 0 24 24"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                          aria-hidden="true"
                        >
                          <path
                            d="M7 3H13.5L19 8.5V21H7V3Z"
                            stroke="currentColor"
                            stroke-width="1.5"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                          />
                          <path
                            d="M13 3V9H19"
                            stroke="currentColor"
                            stroke-width="1.5"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                          />
                        </svg>
                        <strong>PDF</strong>
                        <span class="selected-preview__pdf-name">{{ selectedAsset.filename }}</span>
                      </div>
                      <img
                        v-else
                        :src="selectedAsset.url"
                        :alt="selectedAsset.filename"
                        loading="lazy"
                      />
                    </div>

                    <div class="selected-actions asset-inline-editor__toolbar">
                      <template v-if="!isRenaming">
                        <p class="selected-name" :title="selectedAsset.filename">{{ selectedAsset.filename }}</p>
                        <button class="btn-outline btn-sm" type="button" @click="startRenameWithFocus">Rename</button>
                      </template>
                      <template v-else>
                        <input
                          ref="renameInput"
                          v-model="renameValue"
                          class="field"
                          type="text"
                          @keydown.enter="executeRenameSafe"
                          @keydown.escape="cancelRename"
                        />
                        <div class="inline-actions">
                          <button class="btn-primary btn-sm" type="button" @click="executeRenameSafe">Save</button>
                          <button class="btn-outline btn-sm" type="button" @click="cancelRename">Cancel</button>
                        </div>
                      </template>
                      <button class="btn-danger btn-sm" type="button" @click="executeDeleteSafe">Delete</button>
                    </div>

                    <div class="author-edit asset-inline-editor__section">
                      <h4>Author</h4>
                      <div class="inline-form author-edit__row">
                        <input
                          v-model="authorInput"
                          class="field"
                          type="text"
                          placeholder="Author name"
                          @keydown.enter.prevent="saveAuthorSafe"
                        />
                        <button
                          class="btn-primary btn-sm"
                          type="button"
                          :disabled="authorSaving"
                          @click="saveAuthorSafe"
                        >
                          {{ authorSaving ? "Saving..." : "Save Author" }}
                        </button>
                      </div>
                      <p class="tag-value">Tag preview: {{ authorTagPreview }}</p>
                    </div>
                  </div>

                  <div class="asset-inline-editor__controls">
                    <div class="caption-edit asset-inline-editor__section">
                      <h4>Image Text</h4>
                      <div class="field-grid caption-grid">
                        <label>
                          <span>Caption (DE)</span>
                          <input
                            v-model="captionDeInput"
                            class="field"
                            type="text"
                            placeholder="Bildunterschrift"
                            @blur="saveAssetTextSafe"
                            @keydown.enter.prevent="saveAssetTextSafe"
                          />
                        </label>
                        <label>
                          <span>Caption (EN)</span>
                          <input
                            v-model="captionEnInput"
                            class="field"
                            type="text"
                            placeholder="Caption"
                            @blur="saveAssetTextSafe"
                            @keydown.enter.prevent="saveAssetTextSafe"
                          />
                        </label>
                        <label>
                          <span>Alt Text (DE)</span>
                          <input
                            v-model="altDeInput"
                            class="field"
                            type="text"
                            placeholder="Alternativtext"
                            @blur="saveAssetTextSafe"
                            @keydown.enter.prevent="saveAssetTextSafe"
                          />
                        </label>
                        <label>
                          <span>Alt Text (EN)</span>
                          <input
                            v-model="altEnInput"
                            class="field"
                            type="text"
                            placeholder="Alt text"
                            @blur="saveAssetTextSafe"
                            @keydown.enter.prevent="saveAssetTextSafe"
                          />
                        </label>
                      </div>
                    </div>

                    <div class="tag-edit asset-inline-editor__section">
                      <h4>Tags</h4>
                      <div class="chip-row">
                        <span v-for="tag in (selectedAsset.tags || [])" :key="tag" class="chip">
                          {{ tag }}
                          <button type="button" @click="removeTagSafe(tag)">×</button>
                        </span>
                      </div>
                      <input
                        v-model="tagInput"
                        class="field"
                        type="text"
                        placeholder="Add tag and press Enter"
                        @keydown.enter="addTagSafe"
                      />
                    </div>

                    <div class="download-edit asset-inline-editor__section">
                      <h4>Download</h4>
                      <div class="download-edit__rows">
                        <label class="download-edit__field">
                          <span>Storage URL</span>
                          <a
                            class="download-link"
                            :href="selectedAsset.url"
                            target="_blank"
                            rel="noopener"
                          >
                            {{ selectedAsset.url }}
                          </a>
                        </label>
                        <label class="variant-toggle download-edit__toggle">
                          <input
                            v-model="downloadableInput"
                            type="checkbox"
                            :disabled="downloadableSaving"
                            @change="saveDownloadableSafe"
                          />
                          <span>Downloadable</span>
                        </label>
                        <label v-if="selectedAsset.downloadable && selectedAsset.download_url" class="download-edit__field">
                          <span>Download URL</span>
                          <div class="download-link-row">
                            <a
                              class="download-link"
                              :href="selectedAsset.download_url"
                              target="_blank"
                              rel="noopener"
                            >
                              {{ selectedAsset.download_url }}
                            </a>
                            <button
                              class="btn-outline btn-sm"
                              type="button"
                              @click="copyDownloadUrlSafe"
                            >
                              {{ downloadUrlCopied ? "Copied" : "Copy" }}
                            </button>
                          </div>
                        </label>
                        <p v-else class="tag-value">Enable "Downloadable" to expose the public download proxy URL.</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </transition>
          </template>
          <p v-if="!loading && assets.length === 0" class="empty-text">No media found.</p>
          <p v-if="loading" class="empty-text">Loading...</p>
        </div>

        <div class="library-bottom-bar" :class="{ 'library-bottom-bar--no-pagination': totalPages <= 1 }">
          <div class="pagination" v-if="totalPages > 1">
            <button class="btn-outline btn-sm" type="button" :disabled="currentPage === 1" @click="goToPageAndFetch(currentPage - 1)">
              Previous
            </button>
            <span>{{ currentPage }} / {{ totalPages }}</span>
            <button class="btn-outline btn-sm" type="button" :disabled="!hasMore" @click="goToPageAndFetch(currentPage + 1)">
              Next
            </button>
          </div>
          <button class="admin-btn admin-btn-primary" type="button" :disabled="bulkActionRunning" @click="toggleBulkEditMode">
            {{ bulkEditMode ? "Exit Bulk Edit" : "Bulk Edit Mode" }}
          </button>
        </div>

        <div v-if="bulkEditMode" class="bulk-edit-panel">
          <div class="bulk-edit-panel__head">
            <p class="tag-value">
              Selected:
              <strong>{{ bulkSelectedAssetCount }}</strong>
            </p>
            <div class="inline-actions bulk-edit-panel__quick-actions">
              <button class="btn-outline btn-sm" type="button" @click="selectAllVisibleForBulk">Select all on page</button>
              <button class="btn-outline btn-sm" type="button" @click="clearBulkSelection">Clear</button>
            </div>
          </div>
          <div class="inline-form bulk-edit-panel__form">
            <input
              v-model="bulkTagInput"
              class="field"
              type="text"
              placeholder="Common tag (e.g. homepage)"
              @keydown.enter.prevent="applyBulkCommonTagSafe"
            />
            <button
              class="btn-primary btn-sm"
              type="button"
              :disabled="bulkActionRunning || bulkSelectedAssetCount === 0 || !normalizedBulkCommonTag"
              @click="applyBulkCommonTagSafe"
            >
              {{ bulkActionKind === "add-tag" ? "Applying..." : "Add Common Tag" }}
            </button>
            <button
              class="btn-danger btn-sm"
              type="button"
              :disabled="bulkActionRunning || bulkSelectedAssetCount === 0"
              @click="executeBulkDeleteSafe"
            >
              {{ bulkActionKind === "delete" ? "Deleting..." : "Delete Selected" }}
            </button>
          </div>
          <div v-if="bulkSelectedAssetCount > 0" class="bulk-edit-panel__shared-tags">
            <p class="tag-value">Shared tags</p>
            <div v-if="bulkSharedTags.length > 0" class="bulk-shared-tags">
              <button
                v-for="tag in bulkSharedTags"
                :key="`bulk-shared-${tag}`"
                class="bulk-shared-tag"
                type="button"
                :disabled="bulkActionRunning"
                @click="removeBulkSharedTagSafe(tag)"
              >
                <span class="bulk-shared-tag__label">{{ tag }}</span>
                <span class="bulk-shared-tag__action">
                  {{ bulkActionKind === `remove-tag:${tag}` ? "Removing..." : "Remove" }}
                </span>
              </button>
            </div>
            <p v-else class="empty-text bulk-edit-panel__empty">No tags are shared by all selected items.</p>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="tags-layout">
      <div class="config-card">
        <div class="card-header">
          <h2>Custom Tags</h2>
          <p class="card-hint">Manage custom tags for editorial use.</p>
        </div>

        <div class="inline-form">
          <input v-model="newCustomTag" class="field" type="text" placeholder="New tag label" />
          <button class="btn-primary" type="button" :disabled="configSaving" @click="addCustomTag">Add</button>
        </div>

        <div class="tag-list custom-tag-edit-list">
          <div v-for="tag in mediaConfig.custom_tags" :key="`custom-${tag}`" class="tag-row">
            <input
              class="field custom-tag-input"
              type="text"
              :value="tag"
              aria-label="Custom tag"
              @change="commitCustomTagLabel(tag, $event.target.value)"
              @keydown.enter.prevent="$event.target.blur()"
            />
            <button class="btn-danger btn-sm" type="button" :disabled="configSaving" @click="removeCustomTag(tag)">Delete</button>
          </div>
          <p v-if="mediaConfig.custom_tags.length === 0" class="empty-text">No custom tags yet.</p>
        </div>
      </div>

      <div class="config-card">
        <div class="card-header">
          <h2>Tag Type Prefixes</h2>
          <p class="card-hint">Set prefixes for automatic source tags and author tags.</p>
        </div>

        <div class="field-grid">
          <label>
            <span>Source tag prefix</span>
            <input
              ref="sourceTagPrefixField"
              v-model="sourceTagPrefixInput"
              class="field"
              type="text"
              placeholder="source"
              @blur="saveTagPrefixes"
              @keydown.enter.prevent="$event.target.blur()"
            />
          </label>
          <label>
            <span>Author tag prefix</span>
            <input
              ref="authorTagPrefixField"
              v-model="authorTagPrefixInput"
              class="field"
              type="text"
              placeholder="author"
              @blur="saveTagPrefixes"
              @keydown.enter.prevent="$event.target.blur()"
            />
          </label>
        </div>
        
        <p class="card-hint">Prefixes related to gig items.</p>
        <div class="field-grid">
          <label>
            <span>Gig tag prefix</span>
            <input
              ref="programArtistTagPrefixField"
              v-model="programArtistTagPrefixInput"
              class="field"
              type="text"
              placeholder="artist"
              @blur="saveTagPrefixes"
              @keydown.enter.prevent="$event.target.blur()"
            />
          </label>
          <label>
            <span>Stage tag prefix</span>
            <input
              ref="programStageTagPrefixField"
              v-model="programStageTagPrefixInput"
              class="field"
              type="text"
              placeholder="stage"
              @blur="saveTagPrefixes"
              @keydown.enter.prevent="$event.target.blur()"
            />
          </label>
          <label>
            <span>Date tag prefix</span>
            <input
              ref="programDateTagPrefixField"
              v-model="programDateTagPrefixInput"
              class="field"
              type="text"
              placeholder="date"
              @blur="saveTagPrefixes"
              @keydown.enter.prevent="$event.target.blur()"
            />
          </label>
        </div>
      </div>

    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useMediaLibraryManager } from "../../composables/useMediaLibraryManager.js";
import {
  deleteAsset,
  importAssetFromUrl,
  renameAsset,
  updateAssetTags,
  updateAssetText,
  updateAssetDownloadable,
  getProgramShared,
  regenerateAssetVariants,
  renameAssetTag,
  deleteAssetTag,
  getAdminMediaConfig,
  updateAdminMediaConfig,
} from "../../services/api.js";
import AdminPageTabs from "../../components/admin/AdminPageTabs.vue";
import AutosaveToast from "../../components/admin/AutosaveToast.vue";
import ImageTransformEditor from "../../components/ui/ImageTransformEditor.vue";
import MediaLibrary from "../../components/ui/MediaLibrary.vue";
import { useStore } from "../../store/store.js";
import { authState, getInternalRole, hasInternalRole } from "../../services/auth.js";
import {
  DATE_PICKER_DATE_ONLY_DISPLAY_FORMATS,
  DATE_PICKER_DATE_ONLY_TEXT_INPUT_OPTIONS,
  getCurrentServerDateISO,
  localDateToServerDateOnly,
  serverDateOnlyToLocalDate,
} from "../../utils/revisionTime.js";
import { VueDatePicker } from "@vuepic/vue-datepicker";
import "@vuepic/vue-datepicker/dist/main.css";
import {
  getResponsivePreviewSize,
  normalizeResponsiveConfig,
} from "../../utils/responsiveViewport.js";
import { buildMediaTag, normalizeMediaTagPart } from "../../utils/mediaTags.js";
import { selectResponsiveVariantUrl } from "../../utils/responsiveImages.js";
import {
  normalizeFallbackImageConfig,
  normalizeFallbackFocal,
  normalizeFallbackRotation,
  normalizeFallbackZoom,
} from "../../utils/fallbackImages.js";

const { state, loadAdminDesignConfig } = useStore();
const route = useRoute();
const router = useRouter();

const allTabs = [
  { id: "import", label: "Import", to: "/admin/media/import" },
  { id: "library", label: "Library", to: "/admin/media/library" },
  { id: "config", label: "Config", to: "/admin/media/config" },
  { id: "tags", label: "Tags", to: "/admin/media/tags" },
];
const contentOnlyTabs = allTabs.filter((entry) => ["import", "library", "config"].includes(entry.id));
const MEDIA_TAB_BY_SLUG = {
  import: "import",
  config: "config",
  library: "library",
  tags: "tags",
};
const IMPORT_UI_SETTINGS_STORAGE_KEY = "admin_media_import_ui_settings";
const activeTab = computed(() => {
  const routeTab = getRouteTab();
  const allowedTabs = visibleTabs.value;
  return allowedTabs.some((entry) => entry.id === routeTab)
    ? routeTab
    : (allowedTabs[0]?.id || "library");
});

const importUrl = ref("");
const importFilename = ref("");
const importError = ref("");
const importing = ref(false);
const importMetadataResults = ref([]);
const bypassAutocropTransparentPadding = ref(false);
const showRawMetadata = ref(false);
const fileInput = ref(null);
const renameInput = ref(null);
const draggingDepth = ref(0);
const filtersFlattened = ref(false);
const importSettingsReady = ref(false);
let importSettingsAutosaveTimer = null;

function assetPreviewUrl(asset) {
  return selectResponsiveVariantUrl(asset?.responsive_variants) || String(asset?.url || "");
}

const configSaving = ref(false);
const configError = ref("");
const configSaveStatus = ref("idle");
const configSaveStatusScope = ref("");
const regenerateCroppingRunning = ref(false);
const regenerateCroppingResult = ref(null);
const showGlobalFallbackMediaPicker = ref(false);
const globalFallbackZoomDraft = ref(1);
const globalFallbackFocalXDraft = ref(50);
const globalFallbackFocalYDraft = ref(50);
const globalFallbackRotationDraft = ref(0);
const mediaConfig = ref({
  custom_tags: [],
  source_tag_prefix: "source",
  upload_variants: {
    mobile: { enabled: true, width: 375 },
    thumb: { enabled: true, width: 150 },
    tablet: { enabled: true, width: 768 },
    desktop: { enabled: true, width: 1120 },
    custom: [],
    max_original_width: 2000,
  },
  metadata_mappings: {
    enabled: true,
    author_tag_prefix: "author",
    rights_tag_prefix: "rights",
    keyword_tag_prefix: "meta",
    require_author: false,
    require_rights: false,
    key_mappings: [
      { source_key: "raw_exif.exif:copyright", target_field: "author" },
    ],
    value_mappings: [],
  },
  program_tagging: {
    artist_tag_prefix: "artist",
    stage_tag_prefix: "stage",
    date_tag_prefix: "date",
  },
  cropping_tags: {
    base_tags: ["cropped", "auto"],
    profile_tag_pattern: "profile-{profile_id}",
    profile_overrides: {},
  },
  fallback_images: {
    images: [],
    media_tag: "",
    image_url: "",
    image_zoom: 1,
    image_focal_x: 50,
    image_focal_y: 50,
    image_rotation: 0,
  },
});

const newCustomTag = ref("");
const renameTagFrom = ref("");
const renameTagTo = ref("");

const sourceTagPrefixInput = ref("source");
const authorTagPrefixInput = ref("author");
const programArtistTagPrefixInput = ref("artist");
const programStageTagPrefixInput = ref("stage");
const programDateTagPrefixInput = ref("date");
const sourceTagPrefixField = ref(null);
const authorTagPrefixField = ref(null);
const programArtistTagPrefixField = ref(null);
const programStageTagPrefixField = ref(null);
const programDateTagPrefixField = ref(null);
const uploadMobileEnabled = ref(true);
const uploadMobileWidth = ref(375);
const uploadThumbEnabled = ref(true);
const uploadThumbWidth = ref(150);
const uploadTabletEnabled = ref(true);
const uploadTabletWidth = ref(768);
const uploadDesktopEnabled = ref(true);
const uploadDesktopWidth = ref(1120);
const uploadCustomVariants = ref([]);
const uploadMaxOriginalWidth = ref(2000);
const metadataEnabledInput = ref(true);
const metadataRequireAuthorInput = ref(false);
const metadataSourceKeyInput = ref("raw_exif.exif:copyright");
const metadataTargetFieldInput = ref("author");
const authorInput = ref("");
const authorSaving = ref(false);
const captionDeInput = ref("");
const captionEnInput = ref("");
const altDeInput = ref("");
const altEnInput = ref("");
const assetTextSaving = ref(false);
const assetTextSaveQueued = ref(false);
const assetTextLastSavedSignature = ref("");
const assetEditorAutosaveStatus = ref("idle");
const assetEditorAutosaveError = ref("");
const downloadableInput = ref(false);
const downloadableSaving = ref(false);
const downloadUrlCopied = ref(false);
const sessionItemSaving = ref({});
const sessionItemError = ref({});
const sessionItemAutosaveQueued = ref({});
const sessionManualAuthor = ref("");
const sessionGlobalTaggingMode = ref("auto");
const sessionGlobalProgramArtistQuery = ref("");
const sessionGlobalProgramSelectedGigId = ref("");
const sessionGlobalManualArtist = ref("");
const sessionGlobalManualStage = ref("");
const sessionGlobalManualDate = ref(todayIsoDay());
const sessionGlobalManualAdditionalInfo = ref("");
const sessionGlobalCaptionDe = ref("");
const sessionGlobalCaptionEn = ref("");
const programSharedGigs = ref([]);
const programSharedStages = ref([]);
const bulkEditMode = ref(false);
const bulkSelectedAssetIds = ref([]);
const bulkTagInput = ref("");
const bulkActionRunning = ref(false);
const bulkActionKind = ref("");
const assetGridRef = ref(null);
const assetGridColumns = ref(1);
let assetGridResizeObserver = null;
const sessionItemAutosaveTimers = new Map();

const MANUAL_INFO_TAG_PREFIX = "info";
const SESSION_ITEM_AUTOSAVE_MS = 900;

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
  uploadQueue,
  uploadedSessionItems,
  uploadedSessionCount,
  averageUploadSecondsPerMb,
  totalQueueEtaSeconds,
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
  clearUploadQueue,
  recomputeQueueTimingAndEta,
} = useMediaLibraryManager({ pageSize: 50 });

let searchTimeout = null;
let uploadVariantsSaveQueue = Promise.resolve();
let tagPrefixesSaveQueue = Promise.resolve();
let downloadUrlCopiedTimer = null;
let configSaveStatusTimer = null;
let assetEditorAutosaveStatusTimer = null;

const canImport = computed(() => String(importUrl.value || "").trim().length > 0);
const hasActiveUploadSession = computed(
  () => (uploadQueue.value?.length || 0) > 0 || Number(uploadedSessionCount.value || 0) > 0
);
const isAuthenticatedContentOnlyUser = computed(
  () => Boolean(authState.authenticated) && String(getInternalRole() || "") === "content"
);
const visibleTabs = computed(() => (isAuthenticatedContentOnlyUser.value ? contentOnlyTabs : allTabs));
function getRouteTab() {
  const slug = String(route.path || "").split("/")[3] || "";
  return MEDIA_TAB_BY_SLUG[slug] || "";
}
const canSeeAdvancedImportOptions = computed(() => hasInternalRole("admin_general"));
const currentUiLanguage = computed(() => (String(state.lang || "de").toLowerCase() === "en" ? "en" : "de"));

const effectiveSourcePrefix = computed(() => {
  const value = normalizeTag(sourceTagPrefixInput.value || mediaConfig.value?.source_tag_prefix || "source");
  return value || "source";
});
const effectiveAuthorPrefix = computed(
  () =>
    normalizeTag(
      mediaConfig.value?.metadata_mappings?.author_tag_prefix
      || authorTagPrefixInput.value
      || "author"
    ) || "author"
);
const effectiveProgramArtistPrefix = computed(
  () =>
    normalizeTag(
      mediaConfig.value?.program_tagging?.artist_tag_prefix
      || programArtistTagPrefixInput.value
      || "artist"
    ) || "artist"
);
const effectiveProgramStagePrefix = computed(
  () =>
    normalizeTag(
      mediaConfig.value?.program_tagging?.stage_tag_prefix
      || programStageTagPrefixInput.value
      || "stage"
    ) || "stage"
);
const effectiveProgramDatePrefix = computed(
  () =>
    normalizeTag(
      mediaConfig.value?.program_tagging?.date_tag_prefix
      || programDateTagPrefixInput.value
      || "date"
    ) || "date"
);
const sessionDefaultAuthorSlug = computed(() => slugifyAuthorName(sessionManualAuthor.value));
const sessionAuthorTagPreview = computed(
  () => buildTag(effectiveAuthorPrefix.value, sessionDefaultAuthorSlug.value) || `${effectiveAuthorPrefix.value}::missing`
);
const selectedSessionGlobalGig = computed(() => resolveSelectedGlobalGig());
const sessionGlobalTaggingPreview = computed(() => buildSessionGlobalTaggingPreview());

const metadataKeyMappingEntries = computed(() =>
  Array.isArray(mediaConfig.value?.metadata_mappings?.key_mappings)
    ? mediaConfig.value.metadata_mappings.key_mappings
    : []
);

const authorTagPreview = computed(() => {
  const prefix = getAuthorTagPrefix();
  const slug = slugifyAuthorName(authorInput.value);
  return `${prefix}::${slug || "missing"}`;
});
const groupedTagFilters = computed(() => {
  const groups = new Map();
  for (const rawTag of allTags.value || []) {
    const tag = String(rawTag || "").trim();
    if (!tag) continue;
    const hasPrefix = tag.includes("::");
    const groupKey = hasPrefix ? tag.split("::", 1)[0] : "__no_prefix__";
    const list = groups.get(groupKey) || [];
    list.push(tag);
    groups.set(groupKey, list);
  }
  return [...groups.entries()]
    .map(([key, values]) => ({
      key,
      label: key === "__no_prefix__" ? "Other" : key,
      tags: [...new Set(values)].sort((a, b) => a.localeCompare(b)),
    }))
    .sort((a, b) => {
      if (a.key === "__no_prefix__") return 1;
      if (b.key === "__no_prefix__") return -1;
      return a.label.localeCompare(b.label);
    });
});
const flatTagFilters = computed(() =>
  [...new Set((allTags.value || []).map((entry) => String(entry || "").trim()).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b))
);
const selectedEditorInsertIndex = computed(() => {
  const selected = selectedAsset.value;
  if (!selected) return -1;
  const list = assets.value || [];
  const selectedIndex = list.findIndex((entry) => entry?.id === selected?.id);
  if (selectedIndex < 0) return -1;
  const columns = Math.max(1, Number(assetGridColumns.value || 1));
  const row = Math.floor(selectedIndex / columns);
  return Math.min(list.length - 1, (row + 1) * columns - 1);
});
const visibleAssetIds = computed(() =>
  (assets.value || [])
    .map((asset) => String(asset?.id || "").trim())
    .filter(Boolean)
);
const normalizedBulkSelectedAssetIds = computed(() => {
  const allowed = new Set(visibleAssetIds.value);
  return Array.from(
    new Set(
      (bulkSelectedAssetIds.value || [])
        .map((assetId) => String(assetId || "").trim())
        .filter((assetId) => assetId && allowed.has(assetId))
    )
  );
});
const bulkSelectedAssetIdSet = computed(() => new Set(normalizedBulkSelectedAssetIds.value));
const bulkSelectedAssetCount = computed(() => normalizedBulkSelectedAssetIds.value.length);
const normalizedBulkCommonTag = computed(() => normalizeTag(bulkTagInput.value));
const bulkSelectedAssets = computed(() => {
  const selectedIds = bulkSelectedAssetIdSet.value;
  return (assets.value || []).filter((asset) => selectedIds.has(String(asset?.id || "").trim()));
});
const bulkSharedTags = computed(() => {
  const selectedAssets = bulkSelectedAssets.value;
  if (!selectedAssets.length) return [];
  const counts = new Map();
  for (const asset of selectedAssets) {
    const tags = new Set(
      (Array.isArray(asset?.tags) ? asset.tags : [])
        .map((tag) => String(tag || "").trim())
        .filter(Boolean)
    );
    for (const tag of tags) counts.set(tag, (counts.get(tag) || 0) + 1);
  }
  return [...counts.entries()]
    .filter(([, count]) => count === selectedAssets.length)
    .map(([tag]) => tag)
    .sort((a, b) => a.localeCompare(b));
});
const TAG_ALLOWED_CHAR_PATTERN = /[\p{L}\p{N}:_-]/u;

function normalizeTag(raw) {
  const normalized = String(raw || "")
    .normalize("NFC")
    .trim()
    .toLocaleLowerCase()
    .replace(/\s+/gu, "-");
  if (!normalized) return "";
  return [...normalized]
    .filter((char) => TAG_ALLOWED_CHAR_PATTERN.test(char))
    .join("");
}

function updateAssetGridColumns() {
  const el = assetGridRef.value;
  if (!el) {
    assetGridColumns.value = 1;
    return;
  }
  const styles = typeof window !== "undefined" ? window.getComputedStyle(el) : null;
  const gap = Number.parseFloat(styles?.columnGap || styles?.gap || "10") || 10;
  const minCardWidth = 120;
  const width = el.clientWidth || 0;
  const columns = Math.floor((width + gap) / (minCardWidth + gap));
  assetGridColumns.value = Math.max(1, columns || 1);
}

function setupAssetGridObserver() {
  if (typeof window === "undefined") return;
  updateAssetGridColumns();
  if (assetGridResizeObserver) {
    assetGridResizeObserver.disconnect();
    assetGridResizeObserver = null;
  }
  if (!assetGridRef.value || typeof ResizeObserver === "undefined") return;
  assetGridResizeObserver = new ResizeObserver(() => updateAssetGridColumns());
  assetGridResizeObserver.observe(assetGridRef.value);
}

function toggleFilterGrouping() {
  filtersFlattened.value = !filtersFlattened.value;
}

function getAuthorTagPrefix() {
  return effectiveAuthorPrefix.value;
}

function slugifyAuthorName(raw) {
  return normalizeTagValue(raw);
}

function deriveAuthorInputValue(asset) {
  if (!asset) return "";
  const extractedAuthors = Array.isArray(asset.authors) ? asset.authors : [];
  const extracted = extractedAuthors.find((value) => String(value || "").trim().length > 0);
  if (extracted) return String(extracted).trim();

  const prefix = getAuthorTagPrefix();
  const tags = Array.isArray(asset.tags) ? asset.tags : [];
  const authorTag = tags.find((tag) => {
    const normalized = normalizeTag(tag);
    return normalized.startsWith(`${prefix}::`) && normalized !== `${prefix}::missing`;
  });
  if (!authorTag) return "";
  const slug = String(authorTag).split("::").slice(1).join("::");
  return slug.replace(/-/g, " ").trim();
}

function resolveMetadataMappingsConfig(raw, fallback = mediaConfig.value?.metadata_mappings || {}) {
  const defaultKeyMappings = [{ source_key: "raw_exif.exif:copyright", target_field: "author" }];
  const keyMappingsSource = Array.isArray(raw?.key_mappings)
    ? raw.key_mappings
    : Array.isArray(fallback?.key_mappings)
      ? fallback.key_mappings
      : defaultKeyMappings;
  const seenKeyMappings = new Set();
  const keyMappings = keyMappingsSource
    .map((entry) => ({
      source_key: String(entry?.source_key || "").trim().toLowerCase(),
      target_field: String(entry?.target_field || "").trim().toLowerCase(),
    }))
    .filter((entry) => entry.source_key && ["author", "rights", "keyword", "tool", "credit"].includes(entry.target_field))
    .filter((entry) => {
      const key = `${entry.source_key}::${entry.target_field}`;
      if (seenKeyMappings.has(key)) return false;
      seenKeyMappings.add(key);
      return true;
    });
  const valueMappings = Array.isArray(raw?.value_mappings)
    ? raw.value_mappings
        .map((entry) => ({
          field: String(entry?.field || "").trim().toLowerCase(),
          match: String(entry?.match || "").trim().toLowerCase(),
          tag: normalizeTag(entry?.tag || ""),
        }))
        .filter((entry) => entry.field && entry.match && entry.tag)
    : Array.isArray(fallback?.value_mappings)
      ? fallback.value_mappings
      : [];
  return {
    enabled: Boolean(raw?.enabled ?? fallback?.enabled ?? true),
    author_tag_prefix: normalizeTag(raw?.author_tag_prefix || fallback?.author_tag_prefix || "author") || "author",
    rights_tag_prefix: normalizeTag(raw?.rights_tag_prefix || fallback?.rights_tag_prefix || "rights") || "rights",
    keyword_tag_prefix: normalizeTag(raw?.keyword_tag_prefix || fallback?.keyword_tag_prefix || "meta") || "meta",
    require_author: Boolean(raw?.require_author ?? fallback?.require_author ?? false),
    require_rights: Boolean(raw?.require_rights ?? fallback?.require_rights ?? false),
    key_mappings: keyMappings,
    value_mappings: valueMappings,
  };
}

function resolveProgramTaggingConfig(raw, fallback = mediaConfig.value?.program_tagging || {}) {
  return {
    artist_tag_prefix:
      normalizeTag(raw?.artist_tag_prefix || fallback?.artist_tag_prefix || "artist") || "artist",
    stage_tag_prefix:
      normalizeTag(raw?.stage_tag_prefix || fallback?.stage_tag_prefix || "stage") || "stage",
    date_tag_prefix:
      normalizeTag(raw?.date_tag_prefix || fallback?.date_tag_prefix || "date") || "date",
  };
}

function resolveFallbackImagesConfig(raw, fallback = mediaConfig.value?.fallback_images || {}) {
  const source = raw && typeof raw === "object"
    ? raw
    : (fallback && typeof fallback === "object" ? fallback : {});
  const normalized = normalizeFallbackImageConfig(source);
  const primaryImage = normalized.legacyImageUrl
    ? normalized.images.find((image) => image.imageUrl === normalized.legacyImageUrl) || {
      id: "fallback-global",
      imageUrl: normalized.legacyImageUrl,
      responsiveVariants: [],
    }
    : normalized.images[0] || null;
  return {
    images: primaryImage ? [
      {
        id: String(primaryImage?.id || "fallback-global").trim() || "fallback-global",
        image_url: String(primaryImage?.imageUrl || "").trim(),
        responsive_variants: Array.isArray(primaryImage?.responsiveVariants)
          ? primaryImage.responsiveVariants
          : [],
      },
    ] : [],
    media_tag: "",
    image_url: String(primaryImage?.imageUrl || "").trim(),
    image_zoom: normalized.zoom,
    image_focal_x: normalized.focalX,
    image_focal_y: normalized.focalY,
    image_rotation: normalized.rotation,
  };
}

const responsiveConfig = computed(() => normalizeResponsiveConfig(state.adminDesignConfig?.responsive));
const globalFallbackConfig = computed(() => resolveFallbackImagesConfig(mediaConfig.value?.fallback_images));
const globalFallbackImage = computed(() => {
  const config = globalFallbackConfig.value;
  const firstImage = Array.isArray(config.images) ? config.images[0] : null;
  return {
    imageUrl: String(config.image_url || firstImage?.image_url || "").trim(),
    responsiveVariants: Array.isArray(firstImage?.responsive_variants)
      ? firstImage.responsive_variants
      : [],
  };
});
const globalFallbackPreviewUrl = computed(() => globalFallbackImage.value.imageUrl);

function syncGlobalFallbackTransformDraft(source = mediaConfig.value?.fallback_images) {
  const config = resolveFallbackImagesConfig(source);
  globalFallbackZoomDraft.value = config.image_zoom;
  globalFallbackFocalXDraft.value = config.image_focal_x;
  globalFallbackFocalYDraft.value = config.image_focal_y;
  globalFallbackRotationDraft.value = config.image_rotation;
}

function clampInt(value, fallback, min, max) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, Math.round(parsed)));
}

function responsivePreviewWidth(device) {
  return getResponsivePreviewSize(responsiveConfig.value, device)?.width || 0;
}

const UPLOAD_VARIANT_ROW_ORDER = {
  thumb: 0,
  mobile: 1,
  tablet: 2,
  desktop: 3,
  custom: 4,
  max: 5,
};

const uploadVariantRows = computed(() => {
  const rows = [
    {
      key: "mobile",
      kind: "device",
      device: "mobile",
      label: "Mobile",
      detail: "Design responsive width",
      width: responsivePreviewWidth("mobile") || clampInt(uploadMobileWidth.value, 375, 64, 4096),
      enabled: Boolean(uploadMobileEnabled.value),
      order: UPLOAD_VARIANT_ROW_ORDER.mobile,
    },
    {
      key: "thumb",
      kind: "fixed",
      label: "Thumbnail",
      detail: "Variant id: thumb",
      width: clampInt(uploadThumbWidth.value, 150, 64, 4096),
      enabled: Boolean(uploadThumbEnabled.value),
      order: UPLOAD_VARIANT_ROW_ORDER.thumb,
    },
    {
      key: "tablet",
      kind: "device",
      device: "tablet",
      label: "Tablet",
      detail: "Design responsive width",
      width: responsivePreviewWidth("tablet") || clampInt(uploadTabletWidth.value, 768, 64, 4096),
      enabled: Boolean(uploadTabletEnabled.value),
      order: UPLOAD_VARIANT_ROW_ORDER.tablet,
    },
    {
      key: "desktop",
      kind: "device",
      device: "desktop",
      label: "Desktop",
      detail: "Design responsive width",
      width: responsivePreviewWidth("desktop") || clampInt(uploadDesktopWidth.value, 1120, 64, 4096),
      enabled: Boolean(uploadDesktopEnabled.value),
      order: UPLOAD_VARIANT_ROW_ORDER.desktop,
    },
    {
      key: "max",
      kind: "max",
      label: "Max Original",
      detail: "Stored source max size",
      width: clampInt(uploadMaxOriginalWidth.value, 2000, 256, 4096),
      order: UPLOAD_VARIANT_ROW_ORDER.max,
    },
  ];

  uploadCustomVariants.value.forEach((variant, index) => {
    rows.push({
      key: `custom-${variant.id || index}-${index}`,
      kind: "custom",
      label: variant.label || variant.id || `Custom ${index + 1}`,
      detail: `Variant id: ${variant.id || "custom"}`,
      width: clampInt(variant.width, 640, 64, 4096),
      enabled: Boolean(variant.enabled),
      index,
      order: UPLOAD_VARIANT_ROW_ORDER.custom,
    });
  });

  return rows.sort((a, b) => {
    if (a.width !== b.width) return a.width - b.width;
    return a.order - b.order;
  });
});

async function setUploadDeviceEnabled(device, enabled) {
  if (device === "mobile") {
    uploadMobileEnabled.value = Boolean(enabled);
  } else if (device === "tablet") {
    uploadTabletEnabled.value = Boolean(enabled);
  } else if (device === "desktop") {
    uploadDesktopEnabled.value = Boolean(enabled);
  }
  await saveUploadVariantsConfig();
}

async function setUploadThumbEnabled(enabled) {
  uploadThumbEnabled.value = Boolean(enabled);
  await saveUploadVariantsConfig();
}

function normalizeVariantId(value, fallback = "") {
  const normalized = String(value || "")
    .normalize("NFKD")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return normalized || fallback;
}

function variantLabelFromId(id, fallback = "Custom") {
  const label = String(id || "")
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .trim();
  return label || fallback;
}

function uniqueUploadVariantId(label, indexToIgnore = -1) {
  const fixedIds = new Set(["mobile", "thumb", "tablet", "desktop", "small"]);
  const existing = new Set(
    uploadCustomVariants.value
      .map((entry, index) => (index === indexToIgnore ? "" : normalizeVariantId(entry?.id)))
      .filter(Boolean)
  );
  const base = normalizeVariantId(label, "custom");
  let candidate = base;
  let suffix = 2;
  while (fixedIds.has(candidate) || existing.has(candidate)) {
    candidate = `${base}-${suffix}`;
    suffix += 1;
  }
  return candidate;
}

function normalizeUploadCustomVariants(rawVariants) {
  const seen = new Set();
  const source = Array.isArray(rawVariants) ? rawVariants : [];
  const normalized = [];
  for (const entry of source) {
    const label = String(entry?.label || variantLabelFromId(entry?.id)).trim();
    const baseId = normalizeVariantId(entry?.id) || normalizeVariantId(label);
    if (!baseId || ["mobile", "thumb", "tablet", "desktop", "small"].includes(baseId)) continue;
    let id = baseId;
    let suffix = 2;
    while (seen.has(id)) {
      id = `${baseId}-${suffix}`;
      suffix += 1;
    }
    seen.add(id);
    normalized.push({
      id,
      label: (label || variantLabelFromId(id)).slice(0, 80),
      enabled: Boolean(entry?.enabled ?? true),
      width: clampInt(entry?.width, 640, 64, 4096),
    });
  }
  return normalized;
}

async function addUploadCustomVariant() {
  let index = uploadCustomVariants.value.length + 1;
  let label = `Custom ${index}`;
  let id = uniqueUploadVariantId(label);
  while (uploadCustomVariants.value.some((entry) => entry.label === label)) {
    index += 1;
    label = `Custom ${index}`;
    id = uniqueUploadVariantId(label);
  }
  uploadCustomVariants.value.push({ id, label, enabled: true, width: 640 });
  await saveUploadVariantsConfig();
}

async function removeUploadCustomVariant(index) {
  uploadCustomVariants.value.splice(index, 1);
  uploadCustomVariants.value = normalizeUploadCustomVariants(uploadCustomVariants.value);
  await saveUploadVariantsConfig();
}

function syncUploadCustomVariantLabel(index) {
  const entry = uploadCustomVariants.value[index];
  if (!entry) return;
  const fallbackLabel = variantLabelFromId(entry.id, `Custom ${index + 1}`);
  entry.label = String(entry.label || fallbackLabel).trim() || fallbackLabel;
  entry.id = uniqueUploadVariantId(entry.label, index);
  uploadCustomVariants.value = normalizeUploadCustomVariants(uploadCustomVariants.value);
}

async function commitUploadCustomVariant(index) {
  syncUploadCustomVariantLabel(index);
  await saveUploadVariantsConfig();
}

function resolveUploadVariantsConfig(raw, fallback = mediaConfig.value?.upload_variants || {}) {
  const source = raw && typeof raw === "object" ? raw : {};
  const fallbackSource = fallback && typeof fallback === "object" ? fallback : {};
  const customSource = Array.isArray(source.custom)
    ? source.custom
    : Array.isArray(fallbackSource.custom)
      ? fallbackSource.custom
      : null;
  const customThumb = Array.isArray(customSource)
    ? customSource.find((entry) => normalizeVariantId(entry?.id) === "thumb")
    : null;
  const thumbSource = source?.thumb || fallbackSource?.thumb || customThumb || {};
  return {
    mobile: {
      enabled: Boolean(source?.mobile?.enabled ?? fallbackSource?.mobile?.enabled ?? true),
      width: responsivePreviewWidth("mobile") || Number(source?.mobile?.width || fallbackSource?.mobile?.width || 375),
    },
    thumb: {
      enabled: Boolean(thumbSource?.enabled ?? true),
      width: Number(thumbSource?.width || 150),
    },
    tablet: {
      enabled: Boolean(source?.tablet?.enabled ?? fallbackSource?.tablet?.enabled ?? true),
      width: responsivePreviewWidth("tablet") || Number(source?.tablet?.width || fallbackSource?.tablet?.width || 768),
    },
    desktop: {
      enabled: Boolean(source?.desktop?.enabled ?? fallbackSource?.desktop?.enabled ?? true),
      width: responsivePreviewWidth("desktop") || Number(source?.desktop?.width || fallbackSource?.desktop?.width || 1120),
    },
    custom: normalizeUploadCustomVariants(customSource),
    max_original_width: Number(source?.max_original_width || fallbackSource?.max_original_width || 2000),
  };
}

function setActiveTab(tab) {
  const allowedTabs = visibleTabs.value;
  const target = allowedTabs.find((entry) => entry.id === tab) || allowedTabs[0] || allTabs[1];
  router.push(target?.to || "/admin/media/library");
}

function openResponsiveSettings() {
  router.push("/admin/design/responsive");
}

function openFilePicker() {
  fileInput.value?.click?.();
}

async function fetchAll() {
  await Promise.all([fetchAssets(), fetchTags()]);
}

async function fetchMediaConfig() {
  try {
    const cfg = await getAdminMediaConfig();
    mediaConfig.value = {
      custom_tags: Array.isArray(cfg?.custom_tags) ? cfg.custom_tags : [],
      source_tag_prefix: String(cfg?.source_tag_prefix || "source"),
      upload_variants: resolveUploadVariantsConfig(cfg?.upload_variants),
      metadata_mappings: resolveMetadataMappingsConfig(cfg?.metadata_mappings),
      program_tagging: resolveProgramTaggingConfig(cfg?.program_tagging),
      cropping_tags: {
        base_tags: Array.isArray(cfg?.cropping_tags?.base_tags)
          ? cfg.cropping_tags.base_tags
          : ["cropped", "auto"],
        profile_tag_pattern: String(cfg?.cropping_tags?.profile_tag_pattern || "profile-{profile_id}"),
        profile_overrides:
          cfg?.cropping_tags?.profile_overrides && typeof cfg.cropping_tags.profile_overrides === "object"
            ? cfg.cropping_tags.profile_overrides
            : {},
      },
      fallback_images: resolveFallbackImagesConfig(cfg?.fallback_images),
    };
    syncCroppingInputs();
    syncSourcePrefixInput();
    syncUploadVariantInputs();
    syncMetadataInputs();
    syncGlobalFallbackTransformDraft();
  } catch (error) {
    markConfigError("settings", error.message || "Failed to load media config");
  }
}

function syncCroppingInputs() {
  // no-op: cropping tags UI removed from Tags tab
}

function getFocusedTagPrefixDraft() {
  if (typeof document === "undefined") return null;
  const activeElement = document.activeElement;
  const entries = [
    ["source", sourceTagPrefixField, sourceTagPrefixInput],
    ["author", authorTagPrefixField, authorTagPrefixInput],
    ["artist", programArtistTagPrefixField, programArtistTagPrefixInput],
    ["stage", programStageTagPrefixField, programStageTagPrefixInput],
    ["date", programDateTagPrefixField, programDateTagPrefixInput],
  ];
  const activeEntry = entries.find(([, fieldRef]) => fieldRef.value === activeElement);
  if (!activeEntry) return null;
  const [key, , valueRef] = activeEntry;
  return { key, value: valueRef.value };
}

function syncSourcePrefixInput(focusedDraft = null) {
  sourceTagPrefixInput.value = String(mediaConfig.value?.source_tag_prefix || "source");
  authorTagPrefixInput.value = String(mediaConfig.value?.metadata_mappings?.author_tag_prefix || "author");
  programArtistTagPrefixInput.value = String(mediaConfig.value?.program_tagging?.artist_tag_prefix || "artist");
  programStageTagPrefixInput.value = String(mediaConfig.value?.program_tagging?.stage_tag_prefix || "stage");
  programDateTagPrefixInput.value = String(mediaConfig.value?.program_tagging?.date_tag_prefix || "date");
  if (focusedDraft?.key === "source") sourceTagPrefixInput.value = focusedDraft.value;
  if (focusedDraft?.key === "author") authorTagPrefixInput.value = focusedDraft.value;
  if (focusedDraft?.key === "artist") programArtistTagPrefixInput.value = focusedDraft.value;
  if (focusedDraft?.key === "stage") programStageTagPrefixInput.value = focusedDraft.value;
  if (focusedDraft?.key === "date") programDateTagPrefixInput.value = focusedDraft.value;
}

function syncUploadVariantInputs() {
  const uploadVariants = resolveUploadVariantsConfig(mediaConfig.value?.upload_variants);
  uploadMobileEnabled.value = Boolean(uploadVariants?.mobile?.enabled ?? true);
  uploadMobileWidth.value = responsivePreviewWidth("mobile") || Number(uploadVariants?.mobile?.width || 375);
  uploadThumbEnabled.value = Boolean(uploadVariants?.thumb?.enabled ?? true);
  uploadThumbWidth.value = Number(uploadVariants?.thumb?.width || 150);
  uploadTabletEnabled.value = Boolean(uploadVariants?.tablet?.enabled ?? true);
  uploadTabletWidth.value = responsivePreviewWidth("tablet") || Number(uploadVariants?.tablet?.width || 768);
  uploadDesktopEnabled.value = Boolean(uploadVariants?.desktop?.enabled ?? true);
  uploadDesktopWidth.value = responsivePreviewWidth("desktop") || Number(uploadVariants?.desktop?.width || 1120);
  uploadCustomVariants.value = normalizeUploadCustomVariants(uploadVariants?.custom);
  uploadMaxOriginalWidth.value = Number(uploadVariants?.max_original_width || 2000);
}

function syncMetadataInputs() {
  const metadata = mediaConfig.value?.metadata_mappings || {};
  metadataEnabledInput.value = Boolean(metadata?.enabled ?? true);
  metadataRequireAuthorInput.value = Boolean(metadata?.require_author ?? false);
}

function clearConfigSaveStatusTimer() {
  if (configSaveStatusTimer) {
    clearTimeout(configSaveStatusTimer);
    configSaveStatusTimer = null;
  }
}

function setConfigSaveStatus(status, scope = "") {
  clearConfigSaveStatusTimer();
  configSaveStatus.value = status;
  configSaveStatusScope.value = scope;
}

function markConfigSaved(scope = "") {
  setConfigSaveStatus("saved", scope);
  configSaveStatusTimer = setTimeout(() => {
    if (configSaveStatus.value === "saved" && configSaveStatusScope.value === scope) {
      configSaveStatus.value = "idle";
      configSaveStatusScope.value = "";
    }
    configSaveStatusTimer = null;
  }, 3000);
}

function markConfigError(scope = "", message = "Failed to save media config") {
  configError.value = message;
  setConfigSaveStatus("error", scope);
  configSaveStatusTimer = setTimeout(() => {
    if (configSaveStatus.value === "error" && configSaveStatusScope.value === scope) {
      configSaveStatus.value = "idle";
      configSaveStatusScope.value = "";
      configError.value = "";
    }
    configSaveStatusTimer = null;
  }, 3000);
}

const configAutosaveToastTone = computed(() => {
  if (configError.value) return "error";
  return configSaveStatus.value;
});

const configAutosaveToastMessage = computed(() => {
  if (configError.value) return `Auto-save failed: ${configError.value}`;
  if (configSaveStatus.value === "saving") return "Saving changes...";
  if (configSaveStatus.value === "saved") return "All changes saved";
  if (configSaveStatus.value === "error") return "Auto-save failed";
  return "";
});

function clearAssetEditorAutosaveStatusTimer() {
  if (assetEditorAutosaveStatusTimer) {
    clearTimeout(assetEditorAutosaveStatusTimer);
    assetEditorAutosaveStatusTimer = null;
  }
}

function setAssetEditorAutosaveStatus(status, error = "") {
  clearAssetEditorAutosaveStatusTimer();
  assetEditorAutosaveStatus.value = status;
  assetEditorAutosaveError.value = error;
  if (status === "saved" || status === "error") {
    assetEditorAutosaveStatusTimer = setTimeout(() => {
      assetEditorAutosaveStatus.value = "idle";
      assetEditorAutosaveError.value = "";
      assetEditorAutosaveStatusTimer = null;
    }, 3000);
  }
}

const assetEditorAutosaveToastTone = computed(() => assetEditorAutosaveStatus.value);

const assetEditorAutosaveToastMessage = computed(() => {
  if (assetEditorAutosaveStatus.value === "saving") return "Saving image editor changes...";
  if (assetEditorAutosaveStatus.value === "saved") return "Image editor changes saved.";
  if (assetEditorAutosaveStatus.value === "error") {
    return `Image editor autosave failed: ${assetEditorAutosaveError.value || "unknown error"}`;
  }
  return "";
});

const mediaAutosaveToastTone = computed(() => (
  assetEditorAutosaveToastMessage.value
    ? assetEditorAutosaveToastTone.value
    : configAutosaveToastTone.value
));

const mediaAutosaveToastMessage = computed(() => (
  assetEditorAutosaveToastMessage.value || configAutosaveToastMessage.value
));

async function saveMediaConfig(patch, options = {}) {
  const scope = options.scope || "settings";
  configSaving.value = true;
  configError.value = "";
  setConfigSaveStatus("saving", scope);
  try {
    const updated = await updateAdminMediaConfig(patch);
    mediaConfig.value = {
      custom_tags: Array.isArray(updated?.custom_tags) ? updated.custom_tags : [],
      source_tag_prefix: String(updated?.source_tag_prefix || "source"),
      upload_variants: resolveUploadVariantsConfig(updated?.upload_variants),
      metadata_mappings: resolveMetadataMappingsConfig(updated?.metadata_mappings),
      program_tagging: resolveProgramTaggingConfig(updated?.program_tagging),
      cropping_tags: {
        base_tags: Array.isArray(updated?.cropping_tags?.base_tags)
          ? updated.cropping_tags.base_tags
          : ["cropped", "auto"],
        profile_tag_pattern: String(updated?.cropping_tags?.profile_tag_pattern || "profile-{profile_id}"),
        profile_overrides:
          updated?.cropping_tags?.profile_overrides && typeof updated.cropping_tags.profile_overrides === "object"
            ? updated.cropping_tags.profile_overrides
            : {},
      },
      fallback_images: resolveFallbackImagesConfig(updated?.fallback_images, mediaConfig.value?.fallback_images),
    };
    const focusedTagPrefixDraft = options.preserveFocusedTagPrefixDraft ? getFocusedTagPrefixDraft() : null;
    syncCroppingInputs();
    syncSourcePrefixInput(focusedTagPrefixDraft);
    syncUploadVariantInputs();
    syncMetadataInputs();
    syncGlobalFallbackTransformDraft();
    markConfigSaved(scope);
  } catch (error) {
    markConfigError(scope, error.message || "Failed to save media config");
  } finally {
    configSaving.value = false;
  }
}

function openGlobalFallbackMediaLibrary() {
  showGlobalFallbackMediaPicker.value = true;
}

function closeGlobalFallbackMediaLibrary() {
  showGlobalFallbackMediaPicker.value = false;
}

async function applyGlobalFallbackSelection(selection = {}) {
  const imageUrl = String(selection?.url || selection?.imageUrl || selection?.image_url || "").trim();
  if (!imageUrl) {
    await clearGlobalFallbackImage();
    return;
  }

  const current = resolveFallbackImagesConfig(mediaConfig.value?.fallback_images);
  const responsiveVariants = Array.isArray(selection?.responsive_variants)
    ? selection.responsive_variants
    : Array.isArray(selection?.responsiveVariants)
      ? selection.responsiveVariants
      : [];
  const imageId = String(selection?.id || selection?.filename || "fallback-global").trim() || "fallback-global";
  await saveMediaConfig({
    fallback_images: {
      ...current,
      images: [
        {
          id: imageId,
          image_url: imageUrl,
          responsive_variants: responsiveVariants,
        },
      ],
      media_tag: "",
      image_url: imageUrl,
    },
  }, { scope: "fallback" });
  closeGlobalFallbackMediaLibrary();
}

async function clearGlobalFallbackImage() {
  const current = resolveFallbackImagesConfig(mediaConfig.value?.fallback_images);
  await saveMediaConfig({
    fallback_images: {
      ...current,
      images: [],
      media_tag: "",
      image_url: "",
    },
  }, { scope: "fallback" });
}

function setGlobalFallbackTransformDraft(patch = {}) {
  if (patch.zoom !== undefined) {
    globalFallbackZoomDraft.value = normalizeFallbackZoom(patch.zoom);
  }
  if (patch.focalX !== undefined) {
    globalFallbackFocalXDraft.value = normalizeFallbackFocal(patch.focalX);
  }
  if (patch.focalY !== undefined) {
    globalFallbackFocalYDraft.value = normalizeFallbackFocal(patch.focalY);
  }
  if (patch.rotation !== undefined) {
    globalFallbackRotationDraft.value = normalizeFallbackRotation(patch.rotation);
  }
}

async function commitGlobalFallbackTransform() {
  const current = resolveFallbackImagesConfig(mediaConfig.value?.fallback_images);
  const next = {
    ...current,
    image_zoom: normalizeFallbackZoom(globalFallbackZoomDraft.value),
    image_focal_x: normalizeFallbackFocal(globalFallbackFocalXDraft.value),
    image_focal_y: normalizeFallbackFocal(globalFallbackFocalYDraft.value),
    image_rotation: normalizeFallbackRotation(globalFallbackRotationDraft.value),
  };
  if (
    next.image_zoom === current.image_zoom
    && next.image_focal_x === current.image_focal_x
    && next.image_focal_y === current.image_focal_y
    && next.image_rotation === current.image_rotation
  ) {
    return;
  }
  await saveMediaConfig({ fallback_images: next }, { scope: "fallback" });
}

function onSearchInput(event) {
  setSearch(event?.target?.value || "");
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    fetchAssets().catch((error) => console.error("Failed to search assets:", error));
  }, 250);
}

async function filterByTagAndFetch(tag) {
  filterByTag(tag);
  await fetchAssets();
}

async function clearTagFilterAndFetch() {
  clearTagFilter();
  await fetchAssets();
}

async function goToPageAndFetch(page) {
  goToPage(page);
  await fetchAssets();
}

function onAssetCardClick(asset) {
  if (!asset) return;
  if (bulkEditMode.value) {
    toggleBulkSelection(asset.id);
    return;
  }
  if (selectedId.value === asset.id) {
    clearSelection();
    return;
  }
  selectAsset(asset);
}

function toggleBulkEditMode() {
  if (bulkActionRunning.value) return;
  bulkEditMode.value = !bulkEditMode.value;
  if (bulkEditMode.value) {
    clearSelection();
    return;
  }
  bulkSelectedAssetIds.value = [];
  bulkTagInput.value = "";
  bulkActionKind.value = "";
}

function selectAllVisibleForBulk() {
  bulkSelectedAssetIds.value = [...visibleAssetIds.value];
}

function clearBulkSelection() {
  bulkSelectedAssetIds.value = [];
}

function isAssetBulkSelected(assetId) {
  const id = String(assetId || "").trim();
  return Boolean(id) && bulkSelectedAssetIdSet.value.has(id);
}

function toggleBulkSelection(assetId) {
  const id = String(assetId || "").trim();
  if (!id) return;
  const next = new Set(normalizedBulkSelectedAssetIds.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  bulkSelectedAssetIds.value = [...next];
}

async function applyBulkCommonTagSafe() {
  if (!bulkEditMode.value || bulkActionRunning.value) return;
  const selectedIds = normalizedBulkSelectedAssetIds.value;
  if (!selectedIds.length) {
    alert("Select at least one media item first.");
    return;
  }
  const commonTag = normalizedBulkCommonTag.value;
  if (!commonTag) {
    alert("Enter a valid common tag first.");
    return;
  }

  bulkActionRunning.value = true;
  bulkActionKind.value = "add-tag";
  try {
    let updatedCount = 0;
    for (const assetId of selectedIds) {
      const localAsset = (assets.value || []).find((entry) => String(entry?.id || "").trim() === assetId);
      if (!localAsset) continue;
      const currentTags = Array.isArray(localAsset.tags) ? localAsset.tags : [];
      if (currentTags.includes(commonTag)) continue;
      const nextTags = [...new Set([...currentTags, commonTag])].sort((a, b) => a.localeCompare(b));
      const result = await updateAssetTags(assetId, nextTags);
      const resolvedTags = Array.isArray(result?.tags) ? result.tags : nextTags;
      localAsset.tags = resolvedTags;
      if (selectedAsset.value && String(selectedAsset.value.id || "").trim() === assetId) {
        selectedAsset.value.tags = resolvedTags;
      }
      updatedCount += 1;
    }
    bulkTagInput.value = "";
    await fetchTags();
    if (updatedCount > 0) {
      alert(`Added "${commonTag}" to ${updatedCount} selected asset(s).`);
    } else {
      alert(`"${commonTag}" is already present on all selected assets.`);
    }
  } catch (error) {
    console.error("Bulk tag update failed:", error);
    alert(`Failed to apply common tag: ${error.message || error}`);
  } finally {
    bulkActionRunning.value = false;
    bulkActionKind.value = "";
  }
}

async function removeBulkSharedTagSafe(tagValue) {
  if (!bulkEditMode.value || bulkActionRunning.value) return;
  const selectedIds = normalizedBulkSelectedAssetIds.value;
  if (!selectedIds.length) {
    alert("Select at least one media item first.");
    return;
  }
  const sharedTag = String(tagValue || "").trim();
  if (!sharedTag || !bulkSharedTags.value.includes(sharedTag)) {
    alert("Choose a tag shared by all selected media items.");
    return;
  }

  bulkActionRunning.value = true;
  bulkActionKind.value = `remove-tag:${sharedTag}`;
  try {
    let updatedCount = 0;
    for (const assetId of selectedIds) {
      const localAsset = (assets.value || []).find((entry) => String(entry?.id || "").trim() === assetId);
      if (!localAsset) continue;
      const currentTags = Array.isArray(localAsset.tags)
        ? localAsset.tags.map((entry) => String(entry || "").trim()).filter(Boolean)
        : [];
      if (!currentTags.includes(sharedTag)) continue;
      const nextTags = currentTags.filter((entry) => entry !== sharedTag);
      const result = await updateAssetTags(assetId, nextTags);
      const resolvedTags = Array.isArray(result?.tags) ? result.tags : nextTags;
      localAsset.tags = resolvedTags;
      if (selectedAsset.value && String(selectedAsset.value.id || "").trim() === assetId) {
        selectedAsset.value.tags = resolvedTags;
      }
      updatedCount += 1;
    }
    await fetchTags();
    if (updatedCount > 0) {
      alert(`Removed "${sharedTag}" from ${updatedCount} selected asset(s).`);
    } else {
      alert(`"${sharedTag}" is no longer present on all selected assets.`);
    }
  } catch (error) {
    console.error("Bulk tag removal failed:", error);
    alert(`Failed to remove shared tag: ${error.message || error}`);
  } finally {
    bulkActionRunning.value = false;
    bulkActionKind.value = "";
  }
}

async function executeBulkDeleteSafe() {
  if (!bulkEditMode.value || bulkActionRunning.value) return;
  const selectedIds = normalizedBulkSelectedAssetIds.value;
  if (!selectedIds.length) {
    alert("Select at least one media item first.");
    return;
  }

  const selectedNames = (assets.value || [])
    .filter((asset) => selectedIds.includes(String(asset?.id || "").trim()))
    .map((asset) => String(asset?.filename || asset?.id || "").trim())
    .filter(Boolean);
  const preview = selectedNames.slice(0, 6).join(", ");
  const more = selectedNames.length > 6 ? ` and ${selectedNames.length - 6} more` : "";
  const shouldDelete = typeof window !== "undefined"
    ? window.confirm(
      `Delete ${selectedIds.length} selected asset(s)?`
        + (preview ? `\n\n${preview}${more}` : "")
    )
    : true;
  if (!shouldDelete) return;

  bulkActionRunning.value = true;
  bulkActionKind.value = "delete";
  try {
    let deletedCount = 0;
    let failedCount = 0;
    let firstError = "";
    for (const assetId of selectedIds) {
      try {
        await deleteAsset(assetId);
        deletedCount += 1;
      } catch (error) {
        failedCount += 1;
        if (!firstError) firstError = String(error?.message || error || "Delete failed");
      }
    }

    if (selectedId.value && selectedIds.includes(String(selectedId.value || "").trim())) {
      clearSelection();
    }
    clearBulkSelection();
    await Promise.all([fetchAssets(), fetchTags()]);

    if (failedCount > 0) {
      alert(`Deleted ${deletedCount} asset(s). ${failedCount} failed (${firstError}).`);
    } else {
      alert(`Deleted ${deletedCount} selected asset(s).`);
    }
  } catch (error) {
    console.error("Bulk delete failed:", error);
    alert(`Bulk delete failed: ${error.message || error}`);
  } finally {
    bulkActionRunning.value = false;
    bulkActionKind.value = "";
  }
}

function onInlineEditorBeforeEnter(el) {
  if (!el) return;
  el.style.transition = "none";
  el.style.height = "0px";
  el.style.opacity = "0";
  el.style.overflow = "hidden";
}

function onInlineEditorEnter(el, done) {
  if (!el) {
    done?.();
    return;
  }
  const targetHeight = `${el.scrollHeight}px`;
  let finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    done?.();
  };

  const onEnd = (event) => {
    if (event.target !== el) return;
    if (event.propertyName !== "height") return;
    el.removeEventListener("transitionend", onEnd);
    finish();
  };

  el.addEventListener("transitionend", onEnd);

  requestAnimationFrame(() => {
    el.style.transition = "height 260ms cubic-bezier(0.2, 0.8, 0.2, 1), opacity 180ms ease";
    el.style.height = targetHeight;
    el.style.opacity = "1";
  });
  window.setTimeout(() => {
    el.removeEventListener("transitionend", onEnd);
    finish();
  }, 380);
}

function onInlineEditorAfterEnter(el) {
  if (!el) return;
  el.style.transition = "";
  el.style.height = "";
  el.style.opacity = "";
  el.style.overflow = "";
}

function onInlineEditorBeforeLeave(el) {
  if (!el) return;
  el.style.transition = "none";
  el.style.height = `${el.scrollHeight}px`;
  el.style.opacity = "1";
  el.style.overflow = "hidden";
  // Force reflow so the browser has a concrete start height before collapsing.
  void el.offsetHeight;
}

function onInlineEditorLeave(el, done) {
  if (!el) {
    done?.();
    return;
  }
  let finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    done?.();
  };

  const onEnd = (event) => {
    if (event.target !== el) return;
    if (event.propertyName !== "height") return;
    el.removeEventListener("transitionend", onEnd);
    finish();
  };

  el.addEventListener("transitionend", onEnd);

  el.style.transition = "height 240ms cubic-bezier(0.4, 0, 0.2, 1), opacity 150ms ease";
  requestAnimationFrame(() => {
    el.style.height = "0px";
    el.style.opacity = "0";
  });
  window.setTimeout(() => {
    el.removeEventListener("transitionend", onEnd);
    finish();
  }, 380);
}

function onDragEnter() {
  draggingDepth.value += 1;
  setDragging(true);
}

function onDragOver() {
  setDragging(true);
}

function onDragLeave() {
  draggingDepth.value = Math.max(0, draggingDepth.value - 1);
  if (!draggingDepth.value) setDragging(false);
}

function getBypassAutocropOption() {
  return canSeeAdvancedImportOptions.value
    ? Boolean(bypassAutocropTransparentPadding.value)
    : false;
}

async function onDrop(event) {
  draggingDepth.value = 0;
  setDragging(false);
  const files = extractAcceptedFiles(event?.dataTransfer?.files || []);
  if (!files.length) return;
  importError.value = "";
  try {
    const results = await uploadFiles(files, {
      bypassAutocropTransparentPadding: getBypassAutocropOption(),
      deferRequiredMetadataValidation: true,
    });
    applyImportMetadataResults(results, "Upload");
  } catch (error) {
    console.error("Upload failed:", error);
    alert(`Upload failed: ${error.message || error}`);
  }
}

async function onFileSelect(event) {
  const files = extractAcceptedFiles(event?.target?.files || []);
  if (event?.target) event.target.value = "";
  if (!files.length) return;
  importError.value = "";
  try {
    const results = await uploadFiles(files, {
      bypassAutocropTransparentPadding: getBypassAutocropOption(),
      deferRequiredMetadataValidation: true,
    });
    applyImportMetadataResults(results, "Upload");
  } catch (error) {
    console.error("Upload failed:", error);
    alert(`Upload failed: ${error.message || error}`);
  }
}

async function importByUrl() {
  if (!canImport.value || importing.value) return;
  importError.value = "";
  importing.value = true;
  try {
    const requestedFilename = importFilename.value.trim();
    const result = await importAssetFromUrl(
      importUrl.value.trim(),
      requestedFilename,
      {
        bypassAutocropTransparentPadding: getBypassAutocropOption(),
        deferRequiredMetadataValidation: true,
      }
    );
    const resolvedFilename = requestedFilename || String(result?.key || importUrl.value.trim() || "Imported file");
    applyImportMetadataResults(
      [{ filename: resolvedFilename, metadata: result?.metadata }],
      "Import"
    );
    appendUrlImportSessionItem(result, resolvedFilename);
    importUrl.value = "";
    importFilename.value = "";
    await fetchAll();
  } catch (error) {
    importError.value = error.message || "Failed to import URL";
  } finally {
    importing.value = false;
  }
}

function applyImportMetadataResults(results, labelPrefix = "Import") {
  const source = Array.isArray(results) ? results : [];
  const now = Date.now();
  const nextEntries = source
    .map((entry, index) => {
      const fallbackLabel = `${labelPrefix} ${index + 1}`;
      const label = String(entry?.filename || entry?.key || fallbackLabel).trim() || fallbackLabel;
      const hasRawMetadata = entry?.metadata && typeof entry.metadata === "object";
      const rawMetaOnly = hasRawMetadata
        ? extractRawMetadataPayload(entry.metadata)
        : null;
      return {
        id: `${labelPrefix}-${now}-${index}-${label}`,
        label,
        pretty: hasRawMetadata
          ? JSON.stringify(rawMetaOnly, null, 2)
          : "No metadata found for this file.",
      };
    })
    .filter((entry) => Boolean(entry));
  if (!nextEntries.length) return;
  importMetadataResults.value = [...nextEntries, ...importMetadataResults.value];
}

function extractRawMetadataPayload(metadata) {
  const rawPayload = {};
  if (metadata?.raw_exif && typeof metadata.raw_exif === "object") rawPayload.raw_exif = metadata.raw_exif;
  if (metadata?.raw_xmp && typeof metadata.raw_xmp === "object") rawPayload.raw_xmp = metadata.raw_xmp;
  if (metadata?.raw_info && typeof metadata.raw_info === "object") rawPayload.raw_info = metadata.raw_info;
  if (Object.keys(rawPayload).length > 0) return rawPayload;
  return metadata;
}

function clearImportMetadataOutput() {
  importMetadataResults.value = [];
}

function formatFileSize(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  if (value < 1024) return `${Math.round(value)} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDuration(seconds) {
  const value = Number(seconds || 0);
  if (!Number.isFinite(value) || value <= 0) return "0s";
  if (value < 60) return `${Math.round(value)}s`;
  const mins = Math.floor(value / 60);
  const secs = Math.round(value % 60);
  return `${mins}m ${secs}s`;
}

function formatEta(seconds) {
  if (seconds == null) return "estimating...";
  return formatDuration(seconds);
}

function normalizeIsoDay(raw) {
  const value = String(raw || "").trim();
  if (!value) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const fromIso = value.slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(fromIso)) return fromIso;
  return "";
}

function resolveGigIsoDay(gig) {
  const startDay = String(gig?.start || "").trim().slice(0, 10);
  return normalizeIsoDay(startDay || gig?.day);
}

function todayIsoDay() {
  return getCurrentServerDateISO();
}

function localizedBilingual(value) {
  if (typeof value === "string") return value.trim();
  if (!value || typeof value !== "object") return "";
  const preferGerman = currentUiLanguage.value === "de";
  return String(preferGerman ? value.de || value.en : value.en || value.de || "").trim();
}

function normalizeTagValue(value) {
  return normalizeMediaTagPart(value);
}

function isImageUploadItem(item) {
  if (!item) return false;
  const type = String(item.type || "").toLowerCase();
  if (type.startsWith("image/")) return true;
  const url = String(item.asset_url || item.preview_url || "").toLowerCase();
  return [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"].some((ext) => url.includes(ext));
}

function clearSessionItemAutosaveTimer(itemId) {
  const key = String(itemId || "").trim();
  if (!key) return;
  const timer = sessionItemAutosaveTimers.get(key);
  if (timer) {
    clearTimeout(timer);
    sessionItemAutosaveTimers.delete(key);
  }
}

function clearAllSessionItemAutosaveTimers() {
  for (const timer of sessionItemAutosaveTimers.values()) {
    clearTimeout(timer);
  }
  sessionItemAutosaveTimers.clear();
}

function buildSessionAutosaveFingerprint(item) {
  const override = Boolean(item?.meta_edit?.override_session_authorship);
  const globalContext = buildSessionGlobalTaggingContext();
  return JSON.stringify({
    filename: String(item?.meta_edit?.filename || "").trim(),
    caption_de: String(item?.meta_edit?.caption_de || "").trim(),
    caption_en: String(item?.meta_edit?.caption_en || "").trim(),
    tagging_mode: getItemTaggingMode(item),
    manual_artist: String(item?.meta_edit?.manual_artist || "").trim(),
    manual_stage: String(item?.meta_edit?.manual_stage || "").trim(),
    manual_date: normalizeIsoDay(item?.meta_edit?.manual_date),
    manual_additional_info: String(item?.meta_edit?.manual_additional_info || "").trim(),
    program_selected_gig_id: String(item?.meta_edit?.program_selected_gig_id || "").trim(),
    override_session_authorship: override,
    manual_author: override ? String(item?.meta_edit?.manual_author || "").trim() : "",
    session_manual_author: override ? "" : String(sessionManualAuthor.value || "").trim(),
    session_global_tagging_mode: getSessionGlobalTaggingMode(),
    session_global_program_selected_gig_id: String(sessionGlobalProgramSelectedGigId.value || "").trim(),
    session_global_manual_artist: String(sessionGlobalManualArtist.value || "").trim(),
    session_global_manual_stage: String(sessionGlobalManualStage.value || "").trim(),
    session_global_manual_date: normalizeIsoDay(sessionGlobalManualDate.value),
    session_global_manual_additional_info: String(sessionGlobalManualAdditionalInfo.value || "").trim(),
    session_global_artist_value: String(globalContext.artistValue || "").trim(),
    session_global_stage_value: String(globalContext.stageValue || "").trim(),
    session_global_date_value: normalizeIsoDay(globalContext.dateValue),
    session_global_info_value: String(globalContext.additionalInfoValue || "").trim(),
    session_global_caption_de: String(sessionGlobalCaptionDe.value || "").trim(),
    session_global_caption_en: String(sessionGlobalCaptionEn.value || "").trim(),
  });
}

function scheduleSessionItemAutosave(itemId, delayMs = SESSION_ITEM_AUTOSAVE_MS) {
  const key = String(itemId || "").trim();
  if (!key) return;
  clearSessionItemAutosaveTimer(key);
  const timer = setTimeout(async () => {
    sessionItemAutosaveTimers.delete(key);
    const item = (uploadedSessionItems.value || []).find((entry) => String(entry?.id || "").trim() === key);
    if (!item) return;
    if (isSessionItemSaving(key)) {
      sessionItemAutosaveQueued.value = {
        ...sessionItemAutosaveQueued.value,
        [key]: true,
      };
      return;
    }
    await applySessionMetadataTags(item, { auto: true });
  }, Math.max(200, Number(delayMs || SESSION_ITEM_AUTOSAVE_MS)));
  sessionItemAutosaveTimers.set(key, timer);
}

function clearImportQueue() {
  clearAllSessionItemAutosaveTimers();
  clearUploadQueue();
  sessionItemSaving.value = {};
  sessionItemError.value = {};
  sessionItemAutosaveQueued.value = {};
  sessionManualAuthor.value = "";
  sessionGlobalTaggingMode.value = "auto";
  sessionGlobalProgramArtistQuery.value = "";
  sessionGlobalProgramSelectedGigId.value = "";
  sessionGlobalManualArtist.value = "";
  sessionGlobalManualStage.value = "";
  sessionGlobalManualDate.value = todayIsoDay();
  sessionGlobalManualAdditionalInfo.value = "";
  sessionGlobalCaptionDe.value = "";
  sessionGlobalCaptionEn.value = "";
}

function resolveSessionAssetId(item) {
  const direct = String(item?.asset_id || "").trim();
  if (direct) return direct;
  const match = assets.value.find((asset) => {
    const itemUrl = String(item?.asset_url || "").trim();
    if (itemUrl && String(asset?.url || "").trim() === itemUrl) return true;
    const itemThumb = String(item?.asset_thumb_url || "").trim();
    if (itemThumb && assetPreviewUrl(asset) === itemThumb) return true;
    return String(asset?.filename || "").trim() === String(item?.asset_filename || item?.name || "").trim();
  });
  if (!match) return "";
  item.asset_id = String(match.id || "");
  if (!String(item.asset_filename || "").trim()) {
    item.asset_filename = String(match.filename || item.name || "");
  }
  if (item.meta_edit && typeof item.meta_edit === "object" && !String(item.meta_edit.filename || "").trim()) {
    item.meta_edit.filename = String(item.asset_filename || item.name || "").trim();
  }
  if (!Array.isArray(item.tags) || item.tags.length === 0) {
    item.tags = Array.isArray(match.tags) ? match.tags : [];
  }
  return String(item.asset_id || "").trim();
}

function appendUrlImportSessionItem(result, fallbackFilename = "") {
  const assetId = String(result?.asset_id || result?.id || "").trim();
  if (!assetId) return;
  const filename = String(fallbackFilename || result?.key || "imported-file").trim();
  uploadQueue.value.push({
    id: `url-import-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    name: filename,
    size: Number(result?.size || 0),
    type: String(result?.content_type || ""),
    progress: 100,
    status: "completed",
    preview_url: "",
    started_at: Date.now(),
    finished_at: Date.now(),
    elapsed_ms: 0,
    elapsed_seconds: 0,
    estimated_remaining_seconds: 0,
    error: "",
    source_context: "",
    metadata: result?.metadata && typeof result.metadata === "object" ? result.metadata : null,
    tags: Array.isArray(result?.tags) ? result.tags : [],
    asset_id: assetId,
    asset_url: String(result?.url || ""),
    asset_thumb_url: selectResponsiveVariantUrl(result?.responsive_variants) || String(result?.url || ""),
    asset_filename: filename,
    result: result || null,
    meta_edit: {
      filename,
      manual_author: "",
      override_session_authorship: false,
      tagging_mode: "auto",
      manual_artist: "",
      manual_stage: "",
      manual_date: todayIsoDay(),
      manual_additional_info: "",
      caption_de: "",
      caption_en: "",
      program_artist_query: "",
      program_selected_gig_id: "",
    },
  });
  recomputeQueueTimingAndEta();
}

async function fetchProgramSharedCatalog() {
  try {
    const shared = await getProgramShared();
    programSharedGigs.value = Array.isArray(shared?.gigs) ? shared.gigs : [];
    programSharedStages.value = Array.isArray(shared?.stages) ? shared.stages : [];
  } catch (error) {
    console.error("Failed to fetch shared program data:", error);
    programSharedGigs.value = [];
    programSharedStages.value = [];
  }
}

function resolveStageFromGig(gig) {
  const stageKey = String(gig?.stage || "").trim();
  if (!stageKey) return null;
  const normalized = stageKey.toLowerCase();
  return (programSharedStages.value || []).find((stage) => {
    const stageId = String(stage?.id || "").trim().toLowerCase();
    if (stageId && stageId === normalized) return true;
    const stageName = localizedBilingual(stage?.name).toLowerCase();
    return Boolean(stageName && stageName === normalized);
  }) || null;
}

function resolveGigArtistLabel(gig) {
  return localizedBilingual(gig?.title)
    || localizedBilingual(gig?.artist_name)
    || String(gig?.id || "").trim();
}

function resolveGigStageLabel(gig) {
  const stage = resolveStageFromGig(gig);
  if (stage) return localizedBilingual(stage?.name) || String(stage?.id || "").trim();
  return String(gig?.stage || "").trim();
}

function buildProgramTagsForGig(gig) {
  if (!gig) return [];
  const artistValue = normalizeTagValue(resolveGigArtistLabel(gig));
  const stageValue = normalizeTagValue(resolveGigStageLabel(gig));
  const dayValue = resolveGigIsoDay(gig);
  const tags = [];
  if (artistValue) tags.push(`${effectiveProgramArtistPrefix.value}::${artistValue}`);
  if (stageValue) tags.push(`${effectiveProgramStagePrefix.value}::${stageValue}`);
  if (dayValue) tags.push(`${effectiveProgramDatePrefix.value}::${dayValue}`);
  return [...new Set(tags)];
}

function getSessionGlobalTaggingMode() {
  return String(sessionGlobalTaggingMode.value || "").trim().toLowerCase() === "manual" ? "manual" : "auto";
}

function setSessionGlobalTaggingMode(mode) {
  const normalizedMode = String(mode || "").trim().toLowerCase() === "manual" ? "manual" : "auto";
  sessionGlobalTaggingMode.value = normalizedMode;
}

function resolveSelectedGlobalGig() {
  const wanted = String(sessionGlobalProgramSelectedGigId.value || "").trim();
  if (!wanted) return null;
  return (programSharedGigs.value || []).find((gig) => String(gig?.id || "").trim() === wanted) || null;
}

function getProgramArtistMatchesForSessionGlobal() {
  if (getSessionGlobalTaggingMode() !== "auto") return [];
  const all = Array.isArray(programSharedGigs.value) ? programSharedGigs.value : [];
  const query = String(sessionGlobalProgramArtistQuery.value || "").trim().toLowerCase();
  if (!query) return [];
  return all
    .filter((gig) => resolveGigArtistLabel(gig).toLowerCase().includes(query))
    .slice(0, 30);
}

function shouldShowProgramMatchesForSessionGlobal() {
  if (getSessionGlobalTaggingMode() !== "auto") return false;
  if (!String(sessionGlobalProgramArtistQuery.value || "").trim()) return false;
  return getProgramArtistMatchesForSessionGlobal().length > 0;
}

function selectProgramGigForSessionGlobal(gig) {
  if (!gig) return;
  setSessionGlobalTaggingMode("auto");
  sessionGlobalProgramSelectedGigId.value = String(gig?.id || "").trim();
  sessionGlobalProgramArtistQuery.value = "";
}

function clearProgramSelectionForSessionGlobal() {
  sessionGlobalProgramSelectedGigId.value = "";
  sessionGlobalProgramArtistQuery.value = "";
}

function buildSessionGlobalTaggingContext() {
  const mode = getSessionGlobalTaggingMode();
  const selectedGig = resolveSelectedGlobalGig();
  if (mode === "manual") {
    return {
      artistValue: String(sessionGlobalManualArtist.value || ""),
      stageValue: String(sessionGlobalManualStage.value || ""),
      dateValue: normalizeIsoDay(sessionGlobalManualDate.value),
      additionalInfoValue: String(sessionGlobalManualAdditionalInfo.value || ""),
    };
  }
  return {
    artistValue: selectedGig ? resolveGigArtistLabel(selectedGig) : "",
    stageValue: selectedGig ? resolveGigStageLabel(selectedGig) : "",
    dateValue: resolveGigIsoDay(selectedGig),
    additionalInfoValue: "",
  };
}

function buildSessionGlobalTaggingPreview() {
  const globalContext = buildSessionGlobalTaggingContext();
  return [
    buildTag(effectiveProgramArtistPrefix.value, globalContext.artistValue),
    buildTag(effectiveProgramStagePrefix.value, globalContext.stageValue),
    buildTag(effectiveProgramDatePrefix.value, globalContext.dateValue),
    buildTag(MANUAL_INFO_TAG_PREFIX, globalContext.additionalInfoValue),
  ].filter(Boolean);
}

function resolveSelectedGigForItem(item) {
  const wanted = String(item?.meta_edit?.program_selected_gig_id || "").trim();
  if (!wanted) return null;
  return (programSharedGigs.value || []).find((gig) => String(gig?.id || "").trim() === wanted) || null;
}

function resolveEffectiveGigForItem(item) {
  return resolveSelectedGigForItem(item) || resolveSelectedGlobalGig();
}

function getItemTaggingMode(item) {
  return String(item?.meta_edit?.tagging_mode || "").trim().toLowerCase() === "manual" ? "manual" : "auto";
}

function setItemTaggingMode(item, mode) {
  if (!item?.meta_edit) return;
  const normalizedMode = String(mode || "").trim().toLowerCase() === "manual" ? "manual" : "auto";
  item.meta_edit.tagging_mode = normalizedMode;
}

function getProgramArtistMatchesForItem(item) {
  if (getItemTaggingMode(item) !== "auto") return [];
  const all = Array.isArray(programSharedGigs.value) ? programSharedGigs.value : [];
  const query = String(item?.meta_edit?.program_artist_query || "").trim().toLowerCase();
  if (!query) return [];
  return all
    .filter((gig) => resolveGigArtistLabel(gig).toLowerCase().includes(query))
    .slice(0, 30);
}

function shouldShowProgramMatchesForItem(item) {
  if (getItemTaggingMode(item) !== "auto") return false;
  if (!String(item?.meta_edit?.program_artist_query || "").trim()) return false;
  return getProgramArtistMatchesForItem(item).length > 0;
}

function selectProgramGigForItem(item, gig) {
  if (!item?.meta_edit || !gig) return;
  item.meta_edit.tagging_mode = "auto";
  const nextId = String(gig?.id || "").trim();
  item.meta_edit.program_selected_gig_id = nextId;
  item.meta_edit.program_artist_query = "";

  applyProgramContextTags(item).catch((error) => {
    console.error("Failed to auto-apply program tags:", error);
  });
}

function clearProgramSelectionForItem(item) {
  if (!item?.meta_edit) return;
  item.meta_edit.program_selected_gig_id = "";
  item.meta_edit.program_artist_query = "";
}

function isSessionItemSaving(itemId) {
  return Boolean(sessionItemSaving.value[itemId]);
}

function getSessionItemError(itemId) {
  return String(sessionItemError.value[itemId] || "");
}

function buildTag(prefix, value) {
  return buildMediaTag(prefix, value);
}

function replaceScopedTag(tags, prefix, value) {
  const normalizedPrefix = normalizeTag(prefix);
  if (!normalizedPrefix) return [...tags];
  const prefixPattern = `${normalizedPrefix}::`;
  const filtered = (Array.isArray(tags) ? tags : []).filter((tag) => {
    const normalizedTag = normalizeTag(tag);
    return !normalizedTag.startsWith(prefixPattern);
  });
  const next = buildTag(normalizedPrefix, value);
  if (next) filtered.push(next);
  return [...new Set(filtered)];
}

function resolveAuthorSlugForItem(item) {
  const override = Boolean(item?.meta_edit?.override_session_authorship);
  const manual = override
    ? String(item?.meta_edit?.manual_author || "")
    : String(sessionManualAuthor.value || "");
  return slugifyAuthorName(manual);
}

function buildSessionMetadataResult(item, baseTags, options = {}) {
  const seed = Array.isArray(baseTags)
    ? baseTags.map((tag) => normalizeTag(tag)).filter(Boolean)
    : [];
  const mode = getItemTaggingMode(item);
  const selectedGig = resolveSelectedGigForItem(item);
  const globalContext = buildSessionGlobalTaggingContext();
  const includeAuthor = options.includeAuthor !== false;
  const authorValue = includeAuthor ? resolveAuthorSlugForItem(item) : "";
  let nextTags = includeAuthor
    ? replaceScopedTag(seed, effectiveAuthorPrefix.value, authorValue)
    : [...seed];

  let artistValue = "";
  let stageValue = "";
  let dateValue = "";
  let additionalInfoValue = "";

  if (mode === "manual") {
    artistValue = String(item?.meta_edit?.manual_artist || "") || String(globalContext.artistValue || "");
    stageValue = String(item?.meta_edit?.manual_stage || "") || String(globalContext.stageValue || "");
    dateValue = normalizeIsoDay(item?.meta_edit?.manual_date) || normalizeIsoDay(globalContext.dateValue);
    additionalInfoValue = String(item?.meta_edit?.manual_additional_info || "") || String(globalContext.additionalInfoValue || "");
  } else {
    artistValue = selectedGig ? resolveGigArtistLabel(selectedGig) : String(globalContext.artistValue || "");
    stageValue = selectedGig ? resolveGigStageLabel(selectedGig) : String(globalContext.stageValue || "");
    dateValue = selectedGig ? resolveGigIsoDay(selectedGig) : normalizeIsoDay(globalContext.dateValue);
    additionalInfoValue = String(globalContext.additionalInfoValue || "");
  }

  nextTags = replaceScopedTag(nextTags, effectiveProgramArtistPrefix.value, artistValue);
  nextTags = replaceScopedTag(nextTags, effectiveProgramStagePrefix.value, stageValue);
  nextTags = replaceScopedTag(nextTags, effectiveProgramDatePrefix.value, dateValue);
  nextTags = replaceScopedTag(nextTags, MANUAL_INFO_TAG_PREFIX, additionalInfoValue);

  const authorPreviewTag = includeAuthor
    ? (buildTag(effectiveAuthorPrefix.value, authorValue) || `${effectiveAuthorPrefix.value}::missing`)
    : "";
  const scopedPreview = [
    authorPreviewTag,
    buildTag(effectiveProgramArtistPrefix.value, artistValue),
    buildTag(effectiveProgramStagePrefix.value, stageValue),
    buildTag(effectiveProgramDatePrefix.value, dateValue),
    buildTag(MANUAL_INFO_TAG_PREFIX, additionalInfoValue),
  ].filter(Boolean);

  return {
    nextTags: [...new Set(nextTags)].sort((a, b) => a.localeCompare(b)),
    scopedPreview,
  };
}

function buildSessionMetadataPreview(item) {
  return buildSessionMetadataResult(item, item?.tags || []).scopedPreview;
}

function isMissingAuthorPreviewLabel(label) {
  return normalizeTag(label) === `${effectiveAuthorPrefix.value}::missing`;
}

function buildSessionMetadataPreviewEntries(item) {
  return buildSessionMetadataPreview(item).map((label) => ({
    label,
    missing: isMissingAuthorPreviewLabel(label),
  }));
}

async function applySessionFilename(item, assetId) {
  const requested = String(item?.meta_edit?.filename || "").trim();
  const current = String(item?.asset_filename || item?.name || "").trim();
  if (!requested || requested === current) return;

  const result = await renameAsset(assetId, requested);
  const nextFilename = String(result?.filename || requested);
  item.asset_filename = nextFilename;
  item.meta_edit.filename = nextFilename;

  const inLibrary = assets.value.find((entry) => String(entry?.id || "") === assetId);
  if (inLibrary) inLibrary.filename = nextFilename;
}

async function applySessionCaptionText(item, assetId) {
  const localCaptionDe = String(item?.meta_edit?.caption_de || "").trim();
  const localCaptionEn = String(item?.meta_edit?.caption_en || "").trim();
  const globalCaptionDe = String(sessionGlobalCaptionDe.value || "").trim();
  const globalCaptionEn = String(sessionGlobalCaptionEn.value || "").trim();
  const captionDe = localCaptionDe || globalCaptionDe;
  const captionEn = localCaptionEn || globalCaptionEn;
  if (!captionDe && !captionEn) return;

  const result = await updateAssetText(assetId, {
    caption: {
      de: captionDe,
      en: captionEn,
    },
  });

  const inLibrary = assets.value.find((entry) => String(entry?.id || "") === assetId);
  if (inLibrary) {
    inLibrary.caption = {
      de: String(result?.caption?.de || captionDe),
      en: String(result?.caption?.en || captionEn),
    };
  }
}

async function applyProgramContextTags(item) {
  const itemId = String(item?.id || "").trim();
  const assetId = resolveSessionAssetId(item);
  if (!itemId || !assetId || getItemTaggingMode(item) !== "auto" || !resolveSelectedGigForItem(item)) return;

  sessionItemSaving.value = {
    ...sessionItemSaving.value,
    [itemId]: true,
  };
  sessionItemError.value = {
    ...sessionItemError.value,
    [itemId]: "",
  };

  try {
    const { nextTags } = buildSessionMetadataResult(item, item?.tags || [], { includeAuthor: false });
    const result = await updateAssetTags(assetId, nextTags);
    const updatedTags = Array.isArray(result?.tags) ? result.tags : nextTags;
    item.tags = updatedTags;

    const inLibrary = assets.value.find((entry) => String(entry?.id || "") === assetId);
    if (inLibrary) inLibrary.tags = updatedTags;
    await fetchTags();
  } catch (error) {
    sessionItemError.value = {
      ...sessionItemError.value,
      [itemId]: String(error?.message || error || "Failed to apply program tags"),
    };
  } finally {
    sessionItemSaving.value = {
      ...sessionItemSaving.value,
      [itemId]: false,
    };
  }
}

async function applySessionMetadataTags(item, options = {}) {
  const itemId = String(item?.id || "").trim();
  const assetId = resolveSessionAssetId(item);
  if (!itemId || !assetId) {
    if (itemId) {
      sessionItemError.value = {
        ...sessionItemError.value,
        [itemId]: "Could not resolve uploaded asset ID. Refresh library and try again.",
      };
    }
    return;
  }
  const isAuto = Boolean(options?.auto);
  clearSessionItemAutosaveTimer(itemId);
  if (isSessionItemSaving(itemId)) {
    if (isAuto) {
      sessionItemAutosaveQueued.value = {
        ...sessionItemAutosaveQueued.value,
        [itemId]: true,
      };
    }
    return;
  }

  sessionItemSaving.value = {
    ...sessionItemSaving.value,
    [itemId]: true,
  };
  sessionItemError.value = {
    ...sessionItemError.value,
    [itemId]: "",
  };

  try {
    await applySessionFilename(item, assetId);
    const { nextTags } = buildSessionMetadataResult(item, item?.tags || []);
    const result = await updateAssetTags(assetId, nextTags);
    const updatedTags = Array.isArray(result?.tags) ? result.tags : nextTags;
    item.tags = updatedTags;

    const inLibrary = assets.value.find((entry) => String(entry?.id || "") === assetId);
    if (inLibrary) inLibrary.tags = updatedTags;

    await applySessionCaptionText(item, assetId);
    await fetchTags();
  } catch (error) {
    sessionItemError.value = {
      ...sessionItemError.value,
      [itemId]: String(error?.message || error || "Failed to update tags"),
    };
  } finally {
    sessionItemSaving.value = {
      ...sessionItemSaving.value,
      [itemId]: false,
    };
    if (sessionItemAutosaveQueued.value[itemId]) {
      sessionItemAutosaveQueued.value = {
        ...sessionItemAutosaveQueued.value,
        [itemId]: false,
      };
      scheduleSessionItemAutosave(itemId, 200);
    }
  }
}

async function startRenameWithFocus() {
  startRename();
  await nextTick();
  renameInput.value?.focus?.();
  renameInput.value?.select?.();
}

async function executeRenameSafe() {
  setAssetEditorAutosaveStatus("saving");
  try {
    await executeRename();
    setAssetEditorAutosaveStatus("saved");
  } catch (error) {
    console.error("Rename failed:", error);
    setAssetEditorAutosaveStatus("error", error.message || "Rename failed");
  }
}

async function executeDeleteSafe() {
  if (!selectedAsset.value) return;
  const shouldDelete = typeof window !== "undefined"
    ? window.confirm(`Delete "${selectedAsset.value.filename}"?`)
    : true;
  if (!shouldDelete) return;
  setAssetEditorAutosaveStatus("saving");
  try {
    confirmDelete(selectedAsset.value);
    await executeDelete();
    setAssetEditorAutosaveStatus("saved");
  } catch (error) {
    console.error("Delete failed:", error);
    setAssetEditorAutosaveStatus("error", error.message || "Failed to delete");
  }
}

async function addTagSafe() {
  setAssetEditorAutosaveStatus("saving");
  try {
    await addTag();
    await Promise.all([fetchTags(), fetchMediaConfig()]);
    setAssetEditorAutosaveStatus("saved");
  } catch (error) {
    console.error("Failed to add tag:", error);
    setAssetEditorAutosaveStatus("error", error.message || "Failed to add tag");
  }
}

async function removeTagSafe(tag) {
  setAssetEditorAutosaveStatus("saving");
  try {
    await removeTag(tag);
    await fetchTags();
    setAssetEditorAutosaveStatus("saved");
  } catch (error) {
    console.error("Failed to remove tag:", error);
    setAssetEditorAutosaveStatus("error", error.message || "Failed to remove tag");
  }
}

function buildUploadVariantsPayload() {
  const mobileWidth = responsivePreviewWidth("mobile") || 375;
  const tabletWidth = responsivePreviewWidth("tablet") || 768;
  const desktopWidth = responsivePreviewWidth("desktop") || 1120;
  return {
    mobile: {
      enabled: Boolean(uploadMobileEnabled.value),
      width: mobileWidth,
    },
    thumb: {
      enabled: Boolean(uploadThumbEnabled.value),
      width: clampInt(uploadThumbWidth.value, 150, 64, 4096),
    },
    tablet: {
      enabled: Boolean(uploadTabletEnabled.value),
      width: tabletWidth,
    },
    desktop: {
      enabled: Boolean(uploadDesktopEnabled.value),
      width: desktopWidth,
    },
    custom: normalizeUploadCustomVariants(uploadCustomVariants.value),
    max_original_width: clampInt(uploadMaxOriginalWidth.value, 2000, 256, 4096),
  };
}

function uploadVariantsSignature(config) {
  return JSON.stringify(resolveUploadVariantsConfig(config));
}

async function saveUploadVariantsConfig() {
  const payload = buildUploadVariantsPayload();
  if (uploadVariantsSignature(payload) === uploadVariantsSignature(mediaConfig.value?.upload_variants)) {
    return uploadVariantsSaveQueue;
  }
  uploadVariantsSaveQueue = uploadVariantsSaveQueue
    .catch(() => {})
    .then(() => saveMediaConfig({ upload_variants: payload }, { scope: "cropping" }));
  return uploadVariantsSaveQueue;
}

async function regenerateCroppingVariants() {
  if (regenerateCroppingRunning.value) return;
  if (!confirm("Regenerate cropping variants for all image assets? This replaces generated thumbnails and responsive variants.")) return;
  regenerateCroppingRunning.value = true;
  regenerateCroppingResult.value = null;
  try {
    regenerateCroppingResult.value = await regenerateAssetVariants({
      bypass_autocrop_transparent_padding: getBypassAutocropOption(),
    });
    await fetchAssets();
  } catch (error) {
    regenerateCroppingResult.value = {
      processed: 0,
      regenerated: 0,
      skipped: 0,
      failed: 1,
      errors: [
        {
          asset_id: "request",
          filename: "Regenerate request",
          error: error?.message || "Failed to regenerate cropping variants",
        },
      ],
    };
  } finally {
    regenerateCroppingRunning.value = false;
  }
}

async function saveMetadataMappingsConfig() {
  await saveMediaConfig({
    metadata_mappings: {
      enabled: Boolean(metadataEnabledInput.value),
      author_tag_prefix:
        normalizeTag(mediaConfig.value?.metadata_mappings?.author_tag_prefix || authorTagPrefixInput.value || "author")
        || "author",
      rights_tag_prefix:
        normalizeTag(mediaConfig.value?.metadata_mappings?.rights_tag_prefix || "rights") || "rights",
      keyword_tag_prefix:
        normalizeTag(mediaConfig.value?.metadata_mappings?.keyword_tag_prefix || "meta")
        || "meta",
      require_author: Boolean(metadataRequireAuthorInput.value),
      require_rights: Boolean(mediaConfig.value?.metadata_mappings?.require_rights ?? false),
      key_mappings: metadataKeyMappingEntries.value,
      value_mappings: Array.isArray(mediaConfig.value?.metadata_mappings?.value_mappings)
        ? mediaConfig.value.metadata_mappings.value_mappings
        : [],
    },
  }, { scope: "import" });
}

async function saveImportSettings() {
  persistImportUiSettings();

  const current = resolveMetadataMappingsConfig(mediaConfig.value?.metadata_mappings);
  const nextEnabled = Boolean(metadataEnabledInput.value);
  const nextRequireAuthor = canSeeAdvancedImportOptions.value
    ? Boolean(metadataRequireAuthorInput.value)
    : Boolean(current.require_author);
  if (current.enabled === nextEnabled && current.require_author === nextRequireAuthor) {
    markConfigSaved("import");
    return;
  }

  await saveMediaConfig({
    metadata_mappings: {
      ...current,
      enabled: nextEnabled,
      require_author: nextRequireAuthor,
    },
  }, { scope: "import" });
}

function queueImportSettingsAutosave() {
  if (!importSettingsReady.value) return;
  if (importSettingsAutosaveTimer) clearTimeout(importSettingsAutosaveTimer);
  importSettingsAutosaveTimer = setTimeout(() => {
    saveImportSettings().catch((error) => {
      console.error("Failed to auto-save import settings:", error);
    });
  }, 260);
}

function restoreImportUiSettings() {
  if (typeof window === "undefined") return;
  try {
    const parsed = JSON.parse(localStorage.getItem(IMPORT_UI_SETTINGS_STORAGE_KEY) || "{}");
    if (canSeeAdvancedImportOptions.value && typeof parsed?.bypass_autocrop_transparent_padding === "boolean") {
      bypassAutocropTransparentPadding.value = parsed.bypass_autocrop_transparent_padding;
    } else if (!canSeeAdvancedImportOptions.value) {
      bypassAutocropTransparentPadding.value = false;
    }
    if (typeof parsed?.show_raw_metadata === "boolean") {
      showRawMetadata.value = parsed.show_raw_metadata;
    }
  } catch {
    // ignore malformed storage entries
  }
}

function persistImportUiSettings() {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(
      IMPORT_UI_SETTINGS_STORAGE_KEY,
      JSON.stringify({
        bypass_autocrop_transparent_padding: getBypassAutocropOption(),
        show_raw_metadata: Boolean(showRawMetadata.value),
      })
    );
  } catch {
    // ignore storage errors
  }
}

async function saveAuthorSafe() {
  const asset = selectedAsset.value;
  if (!asset || authorSaving.value) return;

  const prefix = getAuthorTagPrefix();
  const name = String(authorInput.value || "").trim();
  const slug = slugifyAuthorName(name);
  const nextAuthorTag = `${prefix}::${slug || "missing"}`;
  const currentTags = Array.isArray(asset.tags) ? asset.tags : [];
  const filteredTags = currentTags.filter((tag) => !normalizeTag(tag).startsWith(`${prefix}::`));
  const nextTags = [...filteredTags, nextAuthorTag];

  authorSaving.value = true;
  setAssetEditorAutosaveStatus("saving");
  try {
    const result = await updateAssetTags(asset.id, nextTags);
    const updatedTags = Array.isArray(result?.tags) ? result.tags : nextTags;
    asset.tags = updatedTags;

    const listEntry = assets.value.find((entry) => entry.id === asset.id);
    if (listEntry) listEntry.tags = updatedTags;

    const nextAuthors = slug ? [name] : [];
    asset.authors = nextAuthors;
    if (listEntry) listEntry.authors = nextAuthors;

    await fetchTags();
    setAssetEditorAutosaveStatus("saved");
  } catch (error) {
    console.error("Failed to save author:", error);
    setAssetEditorAutosaveStatus("error", error.message || "Failed to save author");
  } finally {
    authorSaving.value = false;
  }
}

function normalizeBilingualAssetText(value, fallback = "") {
  const fallbackText = String(fallback || "");
  return {
    de: String(value?.de || fallbackText),
    en: String(value?.en || fallbackText),
  };
}

function buildAssetTextPayload() {
  return {
    caption: {
      de: String(captionDeInput.value || "").trim(),
      en: String(captionEnInput.value || "").trim(),
    },
    alt: {
      de: String(altDeInput.value || "").trim(),
      en: String(altEnInput.value || "").trim(),
    },
  };
}

function assetTextPayloadSignature(payload = buildAssetTextPayload()) {
  try {
    return JSON.stringify(payload || {});
  } catch {
    return "";
  }
}

async function saveDownloadableSafe() {
  const asset = selectedAsset.value;
  if (!asset || downloadableSaving.value) return;

  const nextValue = Boolean(downloadableInput.value);
  downloadableSaving.value = true;
  setAssetEditorAutosaveStatus("saving");
  try {
    const result = await updateAssetDownloadable(asset.id, nextValue);
    const resolvedDownloadable = Boolean(result?.downloadable ?? nextValue);
    const resolvedHash = String(result?.media_hash || asset.media_hash || "").trim();
    const resolvedDownloadUrl = resolvedDownloadable
      ? String(result?.download_url || asset.download_url || "").trim()
      : "";

    asset.downloadable = resolvedDownloadable;
    asset.media_hash = resolvedHash || null;
    asset.download_url = resolvedDownloadUrl || null;
    downloadableInput.value = resolvedDownloadable;

    const listEntry = assets.value.find((entry) => entry.id === asset.id);
    if (listEntry) {
      listEntry.downloadable = resolvedDownloadable;
      listEntry.media_hash = resolvedHash || null;
      listEntry.download_url = resolvedDownloadUrl || null;
    }
    setAssetEditorAutosaveStatus("saved");
  } catch (error) {
    downloadableInput.value = Boolean(asset.downloadable);
    console.error("Failed to save downloadable setting:", error);
    setAssetEditorAutosaveStatus("error", error.message || "Failed to save downloadable setting");
  } finally {
    downloadableSaving.value = false;
  }
}

async function copyDownloadUrlSafe() {
  const downloadUrl = String(selectedAsset.value?.download_url || "").trim();
  if (!downloadUrl) return;

  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(downloadUrl);
    } else if (typeof document !== "undefined") {
      const probe = document.createElement("textarea");
      probe.value = downloadUrl;
      probe.setAttribute("readonly", "");
      probe.style.position = "absolute";
      probe.style.left = "-9999px";
      document.body.appendChild(probe);
      probe.select();
      document.execCommand("copy");
      document.body.removeChild(probe);
    }

    downloadUrlCopied.value = true;
    if (downloadUrlCopiedTimer) clearTimeout(downloadUrlCopiedTimer);
    downloadUrlCopiedTimer = setTimeout(() => {
      downloadUrlCopied.value = false;
      downloadUrlCopiedTimer = null;
    }, 1400);
  } catch (error) {
    console.error("Failed to copy download URL:", error);
    alert(`Failed to copy download URL: ${error.message || error}`);
  }
}

async function saveAssetTextSafe() {
  const asset = selectedAsset.value;
  if (!asset) return;
  if (assetTextSaving.value) {
    assetTextSaveQueued.value = true;
    return;
  }
  const payload = buildAssetTextPayload();
  const signature = assetTextPayloadSignature(payload);
  if (signature && signature === assetTextLastSavedSignature.value) return;

  assetTextSaving.value = true;
  setAssetEditorAutosaveStatus("saving");
  try {
    const result = await updateAssetText(asset.id, payload);
    const nextCaption = normalizeBilingualAssetText(result?.caption);
    const nextAlt = normalizeBilingualAssetText(result?.alt, asset.filename || "");
    asset.caption = nextCaption;
    asset.alt = nextAlt;

    const listEntry = assets.value.find((entry) => entry.id === asset.id);
    if (listEntry) {
      listEntry.caption = nextCaption;
      listEntry.alt = nextAlt;
    }
    assetTextLastSavedSignature.value = signature;
    setAssetEditorAutosaveStatus("saved");
  } catch (error) {
    console.error("Failed to save image text:", error);
    setAssetEditorAutosaveStatus("error", error.message || "Failed to save image text");
  } finally {
    assetTextSaving.value = false;
    if (assetTextSaveQueued.value) {
      assetTextSaveQueued.value = false;
      void saveAssetTextSafe();
    }
  }
}

async function addMetadataKeyMappingRule() {
  const sourceKey = String(metadataSourceKeyInput.value || "").trim().toLowerCase();
  const targetField = String(metadataTargetFieldInput.value || "").trim().toLowerCase();
  if (!sourceKey || !["author", "rights", "keyword", "tool", "credit"].includes(targetField)) return;
  const next = [...metadataKeyMappingEntries.value];
  if (!next.some((entry) => entry.source_key === sourceKey && entry.target_field === targetField)) {
    next.push({ source_key: sourceKey, target_field: targetField });
  }
  mediaConfig.value = {
    ...mediaConfig.value,
    metadata_mappings: {
      ...resolveMetadataMappingsConfig(mediaConfig.value?.metadata_mappings),
      key_mappings: next,
    },
  };
  await saveMetadataMappingsConfig();
}

async function removeMetadataKeyMappingRule(entry) {
  const next = metadataKeyMappingEntries.value.filter(
    (item) => !(item.source_key === entry.source_key && item.target_field === entry.target_field)
  );
  mediaConfig.value = {
    ...mediaConfig.value,
    metadata_mappings: {
      ...resolveMetadataMappingsConfig(mediaConfig.value?.metadata_mappings),
      key_mappings: next,
    },
  };
  await saveMetadataMappingsConfig();
}

function prepareRenameCustomTag(tag) {
  renameTagFrom.value = tag;
  renameTagTo.value = tag;
}

function cancelRenameCustomTag() {
  renameTagFrom.value = "";
  renameTagTo.value = "";
}

async function addCustomTag() {
  const tag = normalizeTag(newCustomTag.value);
  if (!tag) return;
  if (mediaConfig.value.custom_tags.includes(tag)) {
    newCustomTag.value = "";
    return;
  }
  const next = [...mediaConfig.value.custom_tags, tag].sort();
  await saveMediaConfig({ custom_tags: next }, { scope: "tags" });
  newCustomTag.value = "";
}

async function renameCustomTagValue(fromTagValue, toTagValue) {
  const fromTag = normalizeTag(fromTagValue);
  const toTag = normalizeTag(toTagValue);
  if (!fromTag || !toTag || fromTag === toTag) {
    return;
  }
  configSaving.value = true;
  configError.value = "";
  setConfigSaveStatus("saving", "tags");
  try {
    await renameAssetTag(fromTag, toTag);
    const custom = mediaConfig.value.custom_tags
      .map((entry) => (entry === fromTag ? toTag : entry))
      .sort();

    const overridesRaw = mediaConfig.value.cropping_tags?.profile_overrides || {};
    const overrides = Object.fromEntries(
      Object.entries(overridesRaw).map(([key, value]) => [key, value === fromTag ? toTag : value])
    );

    const updated = await updateAdminMediaConfig({
      custom_tags: custom,
      source_tag_prefix: mediaConfig.value.source_tag_prefix || "source",
      cropping_tags: {
        ...mediaConfig.value.cropping_tags,
        profile_overrides: overrides,
      },
    });
    mediaConfig.value = {
      custom_tags: Array.isArray(updated?.custom_tags) ? updated.custom_tags : [],
      source_tag_prefix: String(updated?.source_tag_prefix || "source"),
      upload_variants: resolveUploadVariantsConfig(updated?.upload_variants, mediaConfig.value?.upload_variants),
      metadata_mappings: resolveMetadataMappingsConfig(
        updated?.metadata_mappings,
        mediaConfig.value?.metadata_mappings
      ),
      program_tagging: resolveProgramTaggingConfig(
        updated?.program_tagging,
        mediaConfig.value?.program_tagging
      ),
      cropping_tags: updated?.cropping_tags || mediaConfig.value.cropping_tags,
      fallback_images: resolveFallbackImagesConfig(updated?.fallback_images, mediaConfig.value?.fallback_images),
    };
    syncSourcePrefixInput();
    syncUploadVariantInputs();
    syncMetadataInputs();
    syncGlobalFallbackTransformDraft();
    await fetchTags();
    await fetchAssets();
    markConfigSaved("tags");
  } catch (error) {
    markConfigError("tags", error.message || "Failed to rename custom tag");
  } finally {
    configSaving.value = false;
  }
}

async function commitCustomTagLabel(tag, label) {
  await renameCustomTagValue(tag, label);
}

async function commitRenameCustomTag() {
  await renameCustomTagValue(renameTagFrom.value, renameTagTo.value);
  cancelRenameCustomTag();
}

async function removeCustomTag(tagValue) {
  const tag = normalizeTag(tagValue);
  if (!tag) return;
  configSaving.value = true;
  configError.value = "";
  setConfigSaveStatus("saving", "tags");
  try {
    await deleteAssetTag(tag);
    const custom = mediaConfig.value.custom_tags.filter((entry) => entry !== tag);

    const overridesRaw = mediaConfig.value.cropping_tags?.profile_overrides || {};
    const overrides = Object.fromEntries(
      Object.entries(overridesRaw).filter(([, value]) => value !== tag)
    );

    const updated = await updateAdminMediaConfig({
      custom_tags: custom,
      source_tag_prefix: mediaConfig.value.source_tag_prefix || "source",
      cropping_tags: {
        ...mediaConfig.value.cropping_tags,
        profile_overrides: overrides,
      },
    });
    mediaConfig.value = {
      custom_tags: Array.isArray(updated?.custom_tags) ? updated.custom_tags : [],
      source_tag_prefix: String(updated?.source_tag_prefix || "source"),
      upload_variants: resolveUploadVariantsConfig(updated?.upload_variants, mediaConfig.value?.upload_variants),
      metadata_mappings: resolveMetadataMappingsConfig(
        updated?.metadata_mappings,
        mediaConfig.value?.metadata_mappings
      ),
      program_tagging: resolveProgramTaggingConfig(
        updated?.program_tagging,
        mediaConfig.value?.program_tagging
      ),
      cropping_tags: updated?.cropping_tags || mediaConfig.value.cropping_tags,
      fallback_images: resolveFallbackImagesConfig(updated?.fallback_images, mediaConfig.value?.fallback_images),
    };
    syncSourcePrefixInput();
    syncUploadVariantInputs();
    syncMetadataInputs();
    syncGlobalFallbackTransformDraft();
    await fetchTags();
    await fetchAssets();
    markConfigSaved("tags");
  } catch (error) {
    markConfigError("tags", error.message || "Failed to delete custom tag");
  } finally {
    configSaving.value = false;
  }
}

function buildTagPrefixesPayload() {
  const sourcePrefix = normalizeTag(sourceTagPrefixInput.value) || "source";
  const authorPrefix = normalizeTag(authorTagPrefixInput.value) || "author";
  const artistPrefix = normalizeTag(programArtistTagPrefixInput.value) || "artist";
  const stagePrefix = normalizeTag(programStageTagPrefixInput.value) || "stage";
  const datePrefix = normalizeTag(programDateTagPrefixInput.value) || "date";
  return {
    source_tag_prefix: sourcePrefix,
    metadata_mappings: {
      ...resolveMetadataMappingsConfig(mediaConfig.value?.metadata_mappings),
      author_tag_prefix: authorPrefix,
    },
    program_tagging: {
      ...resolveProgramTaggingConfig(mediaConfig.value?.program_tagging),
      artist_tag_prefix: artistPrefix,
      stage_tag_prefix: stagePrefix,
      date_tag_prefix: datePrefix,
    },
  };
}

function tagPrefixesSignature(config) {
  const metadata = resolveMetadataMappingsConfig(config?.metadata_mappings);
  const programTagging = resolveProgramTaggingConfig(config?.program_tagging);
  return JSON.stringify({
    source_tag_prefix: normalizeTag(config?.source_tag_prefix) || "source",
    author_tag_prefix: normalizeTag(metadata?.author_tag_prefix) || "author",
    artist_tag_prefix: normalizeTag(programTagging?.artist_tag_prefix) || "artist",
    stage_tag_prefix: normalizeTag(programTagging?.stage_tag_prefix) || "stage",
    date_tag_prefix: normalizeTag(programTagging?.date_tag_prefix) || "date",
  });
}

async function saveTagPrefixes() {
  tagPrefixesSaveQueue = tagPrefixesSaveQueue
    .catch(() => {})
    .then(async () => {
      const payload = buildTagPrefixesPayload();
      if (tagPrefixesSignature(payload) === tagPrefixesSignature(mediaConfig.value)) {
        syncSourcePrefixInput(getFocusedTagPrefixDraft());
        markConfigSaved("tags");
        return;
      }
      await saveMediaConfig(payload, { preserveFocusedTagPrefixDraft: true, scope: "tags" });
    });
  return tagPrefixesSaveQueue;
}

onMounted(async () => {
  restoreImportUiSettings();
  if (state.canAdminDesign && !state.adminDesignConfig) {
    await loadAdminDesignConfig();
  }
  await Promise.all([fetchAll(), fetchMediaConfig(), fetchProgramSharedCatalog()]);
  if (!canSeeAdvancedImportOptions.value) {
    bypassAutocropTransparentPadding.value = false;
  }
  recomputeQueueTimingAndEta();
  await nextTick();
  setupAssetGridObserver();
  importSettingsReady.value = true;
});

watch(
  () => selectedAsset.value?.id || "",
  () => {
    authorInput.value = deriveAuthorInputValue(selectedAsset.value);
    captionDeInput.value = String(selectedAsset.value?.caption?.de || "");
    captionEnInput.value = String(selectedAsset.value?.caption?.en || "");
    altDeInput.value = String(selectedAsset.value?.alt?.de || "");
    altEnInput.value = String(selectedAsset.value?.alt?.en || "");
    assetTextSaveQueued.value = false;
    assetTextLastSavedSignature.value = assetTextPayloadSignature();
    setAssetEditorAutosaveStatus("idle");
    downloadableInput.value = Boolean(selectedAsset.value?.downloadable);
    downloadUrlCopied.value = false;
    if (downloadUrlCopiedTimer) {
      clearTimeout(downloadUrlCopiedTimer);
      downloadUrlCopiedTimer = null;
    }
  },
  { immediate: true }
);

watch(
  visibleTabs,
  (tabs) => {
    if (!Array.isArray(tabs) || tabs.length === 0) return;
    if (!tabs.some((entry) => entry.id === getRouteTab())) {
      router.replace(tabs[0]?.to || "/admin/media/library");
    }
  },
  { immediate: true }
);

watch(
  () => assets.value?.length || 0,
  async () => {
    await nextTick();
    setupAssetGridObserver();
  }
);

watch(
  visibleAssetIds,
  (ids) => {
    const allowed = new Set(Array.isArray(ids) ? ids : []);
    bulkSelectedAssetIds.value = (bulkSelectedAssetIds.value || [])
      .map((assetId) => String(assetId || "").trim())
      .filter((assetId) => assetId && allowed.has(assetId));
  },
  { immediate: true }
);

watch(
  () => activeTab.value,
  async (tab) => {
    if (tab !== "library") {
      bulkEditMode.value = false;
      bulkSelectedAssetIds.value = [];
      bulkTagInput.value = "";
      bulkActionRunning.value = false;
      bulkActionKind.value = "";
      return;
    }
    await nextTick();
    setupAssetGridObserver();
  }
);

watch(
  () => state.adminDesignConfig?.responsive,
  () => {
    syncUploadVariantInputs();
  },
  { deep: true }
);

watch(
  () => [
    metadataEnabledInput.value,
    metadataRequireAuthorInput.value,
    bypassAutocropTransparentPadding.value,
    showRawMetadata.value,
  ],
  () => {
    queueImportSettingsAutosave();
  }
);

watch(
  () => canSeeAdvancedImportOptions.value,
  (allowed) => {
    if (!allowed) bypassAutocropTransparentPadding.value = false;
  },
  { immediate: true }
);

watch(
  uploadedSessionItems,
  (items) => {
    for (const item of items || []) {
      if (!item) continue;
      if (!item.meta_edit || typeof item.meta_edit !== "object") {
        const initialFilename = String(item.asset_filename || item.name || "").trim();
        item.meta_edit = {
          filename: initialFilename,
          manual_author: "",
          override_session_authorship: false,
          tagging_mode: "auto",
          manual_artist: "",
          manual_stage: "",
          manual_date: todayIsoDay(),
          manual_additional_info: "",
          caption_de: "",
          caption_en: "",
          program_artist_query: "",
          program_selected_gig_id: "",
        };
      } else {
        if (typeof item.meta_edit.filename !== "string") item.meta_edit.filename = String(item.asset_filename || item.name || "").trim();
        if (!String(item.meta_edit.filename || "").trim()) item.meta_edit.filename = String(item.asset_filename || item.name || "").trim();
        if (typeof item.meta_edit.manual_author !== "string") item.meta_edit.manual_author = "";
        if (typeof item.meta_edit.override_session_authorship !== "boolean") item.meta_edit.override_session_authorship = false;
        if (!["auto", "manual"].includes(String(item.meta_edit.tagging_mode || ""))) item.meta_edit.tagging_mode = "auto";
        if (typeof item.meta_edit.manual_artist !== "string") item.meta_edit.manual_artist = "";
        if (typeof item.meta_edit.manual_stage !== "string") item.meta_edit.manual_stage = "";
        if (typeof item.meta_edit.manual_date !== "string") item.meta_edit.manual_date = todayIsoDay();
        if (!String(item.meta_edit.manual_date || "").trim()) item.meta_edit.manual_date = todayIsoDay();
        if (typeof item.meta_edit.manual_additional_info !== "string") item.meta_edit.manual_additional_info = "";
        if (typeof item.meta_edit.caption_de !== "string") item.meta_edit.caption_de = "";
        if (typeof item.meta_edit.caption_en !== "string") item.meta_edit.caption_en = "";
        if (typeof item.meta_edit.program_artist_query !== "string") item.meta_edit.program_artist_query = "";
        if (typeof item.meta_edit.program_selected_gig_id !== "string") item.meta_edit.program_selected_gig_id = "";
      }
    }
  },
  { immediate: true }
);

watch(
  () =>
    (uploadedSessionItems.value || []).map((item) => ({
      id: String(item?.id || "").trim(),
      fingerprint: buildSessionAutosaveFingerprint(item),
    })),
  (next, prev) => {
    const previous = new Map(
      (Array.isArray(prev) ? prev : [])
        .filter((entry) => String(entry?.id || "").trim())
        .map((entry) => [String(entry.id), String(entry.fingerprint || "")])
    );
    const nextIds = new Set();

    for (const entry of Array.isArray(next) ? next : []) {
      const id = String(entry?.id || "").trim();
      if (!id) continue;
      nextIds.add(id);
      const nextFingerprint = String(entry?.fingerprint || "");
      const previousFingerprint = previous.get(id);
      if (previousFingerprint == null) continue;
      if (previousFingerprint !== nextFingerprint) {
        scheduleSessionItemAutosave(id);
      }
    }

    for (const id of [...sessionItemAutosaveTimers.keys()]) {
      if (!nextIds.has(id)) {
        clearSessionItemAutosaveTimer(id);
      }
    }
  }
);

onBeforeUnmount(() => {
  clearAllSessionItemAutosaveTimers();
  if (importSettingsAutosaveTimer) {
    clearTimeout(importSettingsAutosaveTimer);
    importSettingsAutosaveTimer = null;
  }
  if (downloadUrlCopiedTimer) {
    clearTimeout(downloadUrlCopiedTimer);
    downloadUrlCopiedTimer = null;
  }
  clearConfigSaveStatusTimer();
  clearAssetEditorAutosaveStatusTimer();
  if (assetGridResizeObserver) {
    assetGridResizeObserver.disconnect();
    assetGridResizeObserver = null;
  }
});
</script>

<style scoped>
.import-layout {
  display: grid;
  gap: 12px;
}

.library-layout {
  display: grid;
  gap: 12px;
}

.library-main {
  min-width: 0;
}

.library-filters {
  margin-top: 12px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 12px;
  padding: 12px;
  background: #fff;
  display: grid;
  gap: 10px;
}

.library-filters h3 {
  margin: 0;
  font-size: 0.95rem;
  color: var(--admin-text, #0f172a);
}

.library-filters__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.library-bottom-bar {
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.library-bottom-bar--no-pagination {
  justify-content: flex-end;
}

.bulk-edit-panel {
  margin-top: 12px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 12px;
  padding: 12px;
  background: #fff;
  display: grid;
  gap: 8px;
}

.bulk-edit-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.bulk-edit-panel__quick-actions {
  margin: 0;
}

.bulk-edit-panel__form {
  margin: 0;
}

.bulk-edit-panel__form .field {
  min-width: 220px;
}

.bulk-edit-panel__shared-tags {
  display: grid;
  gap: 8px;
}

.bulk-edit-panel__shared-tags .tag-value {
  margin: 0;
}

.bulk-shared-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.bulk-shared-tag {
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-radius: 999px;
  padding: 6px 8px 6px 10px;
  background: #f8fafc;
  color: #0f172a;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.2;
}

.bulk-shared-tag:hover:not(:disabled) {
  border-color: rgba(239, 68, 68, 0.55);
  background: #fef2f2;
  color: #991b1b;
}

.bulk-shared-tag:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.bulk-shared-tag__label {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bulk-shared-tag__action {
  color: #dc2626;
  font-weight: 800;
}

.bulk-edit-panel__empty {
  margin: 0;
}

.tag-filter-groups {
  display: grid;
  gap: 10px;
}

.tag-filter-group {
  display: grid;
  gap: 6px;
}

.tag-filter-group h4 {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #64748b;
}

.drop-zone {
  position: relative;
  border: 1px dashed rgba(71, 85, 105, 0.5);
  border-radius: 12px;
  padding: 16px;
  background: rgba(148, 163, 184, 0.08);
}

.drop-zone--active {
  border-color: #0f172a;
  background: rgba(15, 23, 42, 0.08);
}

.file-input {
  position: absolute;
  inset: 0;
  opacity: 0;
  pointer-events: none;
}

.drop-zone__content {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  color: #334155;
}

.upload-list {
  margin-top: 10px;
  display: grid;
  gap: 8px;
}

.upload-item {
  display: grid;
  gap: 6px;
  font-size: 12px;
}

.upload-item__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.upload-queue {
  margin-top: 12px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 10px;
  padding: 10px;
  background: #fff;
  display: grid;
  gap: 8px;
}

.upload-queue__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.upload-queue__head h3 {
  margin: 0;
  font-size: 0.9rem;
}

.upload-status {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.45);
  color: #334155;
  background: #f8fafc;
}

.upload-status--uploading {
  border-color: rgba(2, 132, 199, 0.4);
  color: #075985;
  background: rgba(186, 230, 253, 0.5);
}

.upload-status--completed {
  border-color: rgba(16, 185, 129, 0.4);
  color: #065f46;
  background: rgba(209, 250, 229, 0.7);
}

.upload-status--failed {
  border-color: rgba(239, 68, 68, 0.35);
  color: #991b1b;
  background: rgba(254, 226, 226, 0.8);
}

.upload-track {
  height: 6px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.35);
  overflow: hidden;
}

.upload-bar {
  height: 100%;
  background: #0f172a;
  transition: width 0.2s ease;
}

.import-row,
.search-row,
.inline-form,
.field-grid {
  display: flex;
  gap: 8px;
  margin: 12px 0;
}

.search-row {
  align-items: center;
  flex-wrap: wrap;
}

.search-row .field {
  flex: 1 1 260px;
}

.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.field-grid label {
  display: grid;
  gap: 6px;
  font-size: 12px;
  color: #334155;
}

.field,
.ctrl-select {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-radius: 9px;
  padding: 8px 10px;
  font-size: 13px;
  background: #fff;
  color: #0f172a;
}

.admin-date-picker {
  width: 100%;
}

.admin-date-picker :deep(.dp__input_wrap) {
  width: 100%;
}

.admin-date-picker :deep(.dp__input) {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-radius: 9px;
  font-size: 13px;
  background: #fff;
  color: #0f172a;
  font: inherit;
}

.admin-date-picker :deep(.dp__input:focus) {
  border-color: rgba(59, 130, 246, 0.55);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.import-filename {
  max-width: 200px;
}

.asset-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
}

.asset-inline-editor {
  grid-column: 1 / -1;
  border: 1px solid rgba(148, 163, 184, 0.34);
  border-radius: 14px;
  padding: 14px;
  background: #fff;
  display: grid;
  gap: 14px;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
}

.asset-inline-editor h3 {
  margin: 0;
  font-size: 0.95rem;
  color: var(--admin-text, #0f172a);
}

.asset-inline-editor__content {
  display: grid;
  grid-template-columns: minmax(260px, 420px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.asset-inline-editor__media-column {
  display: grid;
  gap: 12px;
  align-self: start;
}

.asset-inline-editor__controls {
  display: grid;
  gap: 12px;
}

.asset-card {
  position: relative;
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
  padding: 0;
  cursor: pointer;
}

.asset-card.selected {
  border-color: #0f172a;
  box-shadow: 0 0 0 1px #0f172a;
}

.asset-card--bulk-selected {
  border-color: #0369a1;
  box-shadow: 0 0 0 1px #0369a1;
}

.asset-card__bulk-indicator {
  position: absolute;
  top: 6px;
  left: 6px;
  z-index: 2;
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.35);
  background: rgba(248, 250, 252, 0.95);
  color: #334155;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.01em;
  line-height: 1;
  padding: 4px 7px;
}

.asset-card__bulk-indicator.active {
  border-color: #0369a1;
  background: #0369a1;
  color: #fff;
}

.asset-card__media-surface {
  width: 100%;
  aspect-ratio: 1 / 1;
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

.asset-card__media {
  width: 100%;
  height: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  display: block;
  background: transparent;
}

.asset-card__media-surface > .asset-card__media {
  aspect-ratio: auto;
}

.asset-card__pdf {
  width: 100%;
  aspect-ratio: 1 / 1;
  display: grid;
  place-content: center;
  gap: 8px;
  background: #f8fafc;
  color: #b91c1c;
}

.asset-card__pdf-icon {
  width: 42px;
  height: 42px;
}

.asset-card__pdf-label {
  justify-self: center;
  border-radius: 999px;
  border: 1px solid rgba(185, 28, 28, 0.35);
  background: rgba(254, 226, 226, 0.9);
  color: #991b1b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 2px 9px;
}

.pagination {
  margin-top: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.tag-filter-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-filter-btn {
  border: 1px solid rgba(148, 163, 184, 0.5);
  border-radius: 999px;
  background: #fff;
  font-size: 11px;
  padding: 4px 10px;
  cursor: pointer;
}

.tag-filter-btn.active {
  border-color: #0f172a;
  color: #fff;
  background: #0f172a;
}

.selected-preview {
  border: 1px solid rgba(148, 163, 184, 0.32);
  border-radius: 10px;
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

.selected-preview img,
.selected-preview video {
  width: 100%;
  max-height: 520px;
  object-fit: contain;
  background: transparent;
  display: block;
}

.selected-preview__pdf {
  min-height: 220px;
  padding: 22px;
  display: grid;
  justify-items: center;
  align-content: center;
  gap: 8px;
  color: #991b1b;
  text-align: center;
}

.selected-preview__pdf-icon {
  width: 52px;
  height: 52px;
}

.selected-preview__pdf-name {
  max-width: 100%;
  color: #334155;
  font-size: 12px;
  word-break: break-word;
}

.selected-name {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  word-break: break-all;
}

.selected-actions,
.inline-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.asset-inline-editor__toolbar {
  margin: 0;
  padding: 10px 12px;
  border: 1px solid rgba(148, 163, 184, 0.32);
  border-radius: 10px;
  background: #f8fafc;
  justify-content: space-between;
}

.inline-form.rename-form {
  margin-top: 12px;
}

.rename-label {
  font-size: 12px;
  color: #334155;
  display: inline-flex;
  align-items: center;
}

.tag-edit {
  display: grid;
  gap: 8px;
}

.download-edit {
  display: grid;
  gap: 8px;
}

.download-edit__rows {
  display: grid;
  gap: 10px;
}

.download-edit__field {
  display: grid;
  gap: 6px;
  font-size: 12px;
  color: #334155;
}

.download-link {
  color: #0f172a;
  font-size: 12px;
  text-decoration: underline;
  text-decoration-thickness: 1px;
  word-break: break-all;
}

.download-link-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.download-link-row .download-link {
  flex: 1 1 auto;
  min-width: 0;
}

.download-edit__toggle {
  margin: 0;
}

.author-edit {
  display: grid;
  gap: 8px;
}

.caption-edit {
  display: grid;
  gap: 8px;
}

.asset-inline-editor__section {
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 10px;
  background: #fff;
  padding: 10px;
}

.caption-grid {
  grid-template-columns: 1fr 1fr;
  margin: 0;
}

.author-edit__row {
  margin-top: 0;
}

.tag-edit h4,
.download-edit h4,
.author-edit h4,
.caption-edit h4 {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #64748b;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
  background: #f8fafc;
}

.chip button {
  border: none;
  background: transparent;
  cursor: pointer;
  color: #475569;
  padding: 0;
  line-height: 1;
}

.tags-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
}

.card-hint,
.empty-text,
.error-text,
.tag-value {
  margin: 0;
  color: #64748b;
  font-size: 12px;
}

.tag-list {
  display: grid
}

.custom-tag-edit-list .tag-row {
  padding: 10px 8px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.custom-tag-edit-list .tag-row:not(:last-child) {
  border-bottom: 1px solid #dddd;
}

.tag-name {
  font-size: 12px;
  color: #0f172a;
  font-weight: 700;
}

.tag-edit h4,
.author-edit h4,
.caption-edit h4 {
  color: var(--admin-text, #0f172a);
}

.variant-list {
  display: grid;
  gap: 8px;
  margin-top: 6px;
}

.variant-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 140px;
  gap: 8px;
  align-items: center;
}

.variant-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #334155;
}

.variant-toggle--editable {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  width: 100%;
}

.variant-toggle-label-input {
  min-width: max-content;
  padding: 2px 6px;
  max-width: 20%;
}

.variant-width {
  width: 100%;
  text-align: right;
}

.variant-width-readonly {
  justify-self: end;
  min-width: 96px;
  border-radius: 8px;
  padding: 6px 10px;
  text-align: right;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.variant-table {
  display: grid;
  gap: 8px;
}

.variant-table-row {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 128px 86px;
  gap: 12px;
  align-items: center;
  padding: 10px;
  border-radius: 8px;
  background: #fff;
}

.variant-table-row--device {
  background: #f8fafc;
}

.variant-table-main {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.variant-custom-main {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.variant-static-label {
  font-size: 13px;
  color: #334155;
}

.variant-row-detail {
  font-size: 12px;
  line-height: 1.35;
  color: #64748b;
}

.variant-width-cell {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-width: 0;
  font-weight: 700;
}

.variant-remove-cell {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-height: 32px;
}

.variant-remove-btn {
  min-width: 74px;
}

.cropping-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 14px;
}

.cropping-actions__primary,
.cropping-actions__secondary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cropping-actions__secondary {
  justify-content: flex-end;
  margin-left: auto;
}

.custom-tag-input {
  font-weight: 400;
  text-transform: lowercase;
  max-width: min-content;
  border-radius: 5px;
}

.regenerate-summary {
  margin: 10px 0 0;
  color: #166534;
  font-size: 13px;
  font-weight: 700;
}

.regenerate-errors {
  display: grid;
  gap: 4px;
  margin-top: 8px;
  padding: 8px 10px;
  border: 1px solid rgba(239, 68, 68, 0.28);
  border-radius: 8px;
  background: #fef2f2;
  color: #991b1b;
  font-size: 12px;
}

.regenerate-errors p {
  margin: 0;
}

.custom-variant-section {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.custom-variant-section__head,
.custom-variant-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.custom-variant-section__head {
  justify-content: space-between;
}

.custom-variant-section__head h3 {
  margin: 0;
  font-size: 14px;
}

.custom-variant-list {
  display: grid;
  gap: 8px;
}

.custom-variant-row {
  display: grid;
  grid-template-columns: 110px minmax(100px, 0.8fr) minmax(120px, 1fr) 120px 32px;
  padding: 8px;
  border: 1px solid rgba(148, 163, 184, 0.32);
  border-radius: 8px;
  background: #fff;
}

.custom-variant-row label {
  min-width: 0;
}

.import-meta-output {
  margin-top: 12px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 10px;
  padding: 10px;
  background: #fff;
  display: grid;
  gap: 10px;
}

.import-meta-output h3 {
  margin: 0;
  font-size: 0.9rem;
  color: var(--admin-text, #0f172a);
}

.import-meta-output__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.import-option-toggle {
  margin-top: 10px;
}

.import-settings-list {
  display: grid;
  gap: 14px;
  margin-top: 8px;
}

.import-settings-group {
  display: grid;
  gap: 8px;
}

.import-settings-group h3 {
  margin: 0;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.import-setting-row {
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 10px;
  background: #fff;
  padding: 10px;
  display: grid;
  gap: 4px;
}

.import-setting-toggle {
  align-items: flex-start;
  font-weight: 600;
  color: #0f172a;
}

.import-setting-toggle input {
  margin-top: 2px;
}

.import-setting-description {
  margin: 0 0 0 24px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
}

.metadata-rules-panel {
  border-top: 1px dashed rgba(148, 163, 184, 0.45);
  display: grid;
  gap: 12px;
  margin-top: 8px;
  padding-top: 12px;
}

.metadata-rules-panel__option,
.metadata-rules-panel__rules {
  display: grid;
  gap: 8px;
}

.metadata-rules-panel__rules .card-header {
  margin: 0;
}

.metadata-rules-panel__rules h3 {
  color: #0f172a;
  font-size: 0.9rem;
  letter-spacing: 0;
  text-transform: none;
}

.program-match-list {
  display: grid;
  gap: 6px;
}

.program-match-btn {
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-radius: 10px;
  background: #fff;
  text-align: left;
  padding: 8px 10px;
  display: grid;
  gap: 4px;
  cursor: pointer;
}

.program-selection {
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 10px;
  padding: 8px;
  background: rgba(248, 250, 252, 0.8);
  display: grid;
  gap: 6px;
}

.program-selection__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.program-selection__head .tag-value {
  flex: 1 1 auto;
}

.program-item-integration {
  display: grid;
  gap: 8px;
}

.program-item-integration__row {
  margin: 0;
}

.upload-session-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 20px;
  align-items: start;
}

.upload-session-main {
  min-width: 0;
  display: grid;
  gap: 14px;
}

.upload-session-main__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.upload-session-main__head .card-header {
  margin: 0;
}

.upload-session-side {
  position: sticky;
  top: 72px;
  min-width: 0;
}

.upload-session-side .session-authorship {
  border-color: #e2e8f0;
  border-radius: 16px;
  max-height: calc(100vh - 90px);
  overflow-y: auto;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
}

.upload-session-side .session-authorship__manual-row,
.upload-session-side .session-manual-grid,
.upload-session-side .session-meta-grid {
  grid-template-columns: 1fr;
}

.session-summary-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.session-summary-pill {
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 999px;
  background: #f8fafc;
  color: #0f172a;
  padding: 5px 10px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.session-summary-pill__label {
  color: #64748b;
}

.session-summary-pill--count {
  background: #fff;
  flex-shrink: 0;
  margin: auto 0;
}

.session-authorship {
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 10px;
  background: #fff;
  padding: 12px;
  display: grid;
  gap: 10px;
}

.session-authorship h3 {
  margin: 0;
  font-size: 1rem;
}

.session-authorship__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.session-authorship__badge {
  border-radius: 5px;
  color: #0f172a;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.01em;
  padding: 4px 10px;
}

.session-authorship__info {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: #475569;
}

.session-authorship__preview {
  border-top: 1px dashed rgba(148, 163, 184, 0.55);
  padding-top: 10px;
  display: grid;
  gap: 6px;
}

.session-authorship__manual-row {
  margin: 0;
  max-width: none;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.session-upload-list {
  display: grid;
  gap: 14px;
}

.session-upload-card {
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 12px;
  background: #fff;
  padding: 14px;
  display: grid;
  gap: 0;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
}

.session-upload-card + .session-upload-card {
  margin-top: 2px;
}

.session-upload-card__preview {
  justify-self: center;
  width: 100%;
  max-width: none;
  border-radius: 10px;
  overflow: hidden;
  background: #f8fafc;
  border: 1px solid rgba(148, 163, 184, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.session-upload-card__preview img {
  width: 100%;
  height: auto;
  max-height: 420px;
  object-fit: contain;
  display: block;
}

.session-upload-card__file {
  padding: 8px;
  font-size: 12px;
  text-align: center;
  color: #64748b;
  word-break: break-word;
}

.session-upload-card__body {
  display: grid;
  gap: 14px;
}

.session-upload-section {
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 10px;
  background: #f8fafc;
  padding: 10px;
  display: grid;
  gap: 8px;
}

.session-upload-section__title {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #334155;
}

.session-tagging-tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.session-tagging-tabs__btn {
  border: 1px solid rgba(148, 163, 184, 0.5);
  border-radius: 999px;
  background: #fff;
  font-size: 12px;
  padding: 5px 12px;
  cursor: pointer;
}

.session-tagging-tabs__btn.active {
  border-color: #0f172a;
  color: #fff;
  background: #0f172a;
}

.session-filename-grid {
  margin: 0;
}

.session-manual-grid {
  grid-template-columns: 1fr 1fr;
  margin: 0;
}

.session-manual-wide {
  grid-column: 1 / -1;
}

.session-authorship-item {
  display: grid;
  gap: 8px;
}

.session-preview-row {
  display: grid;
  gap: 6px;
}

.session-preview-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.session-preview-tag {
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-radius: 999px;
  background: #f8fafc;
  color: #334155;
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  padding: 5px 8px;
}

.session-preview-tag--missing {
  border-color: rgba(220, 38, 38, 0.45);
  background: rgba(254, 226, 226, 0.85);
  color: #991b1b;
}

.session-author-override-grid {
  grid-template-columns: 1fr;
  margin: 0;
}

.session-meta-grid {
  grid-template-columns: 1fr 1fr;
  margin: 0;
}

.source-tags-subheader {
  margin-top: 10px;
}

.import-meta-output__item {
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  padding: 8px;
  background: #f8fafc;
}

.import-meta-output__item pre {
  margin: 6px 0 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 12px;
  line-height: 1.45;
  color: #0f172a;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 1080px) {
  .asset-inline-editor__content {
    grid-template-columns: 1fr;
  }

  .import-row,
  .inline-form {
    flex-direction: column;
  }

  .import-filename {
    max-width: none;
  }

  .field-grid {
    grid-template-columns: 1fr;
  }

  .variant-row {
    grid-template-columns: 1fr;
  }

  .variant-table-row,
  .custom-tag-edit-row {
    grid-template-columns: 1fr;
  }

  .variant-width-cell {
    justify-content: stretch;
  }

  .variant-remove-cell {
    justify-content: flex-start;
  }

  .cropping-actions,
  .cropping-actions__secondary {
    align-items: stretch;
    justify-content: flex-start;
  }

  .cropping-actions {
    flex-direction: column;
  }

  .cropping-actions__primary,
  .cropping-actions__secondary {
    width: 100%;
  }

  .cropping-actions__secondary {
    margin-left: 0;
  }

  .custom-variant-row {
    grid-template-columns: 1fr;
  }

  .upload-session-layout {
    grid-template-columns: 1fr;
  }

  .upload-session-side {
    position: static;
    order: -1;
  }

  .upload-session-side .session-authorship {
    max-height: none;
  }

  .upload-session-main__head {
    flex-direction: column;
  }

  .session-upload-card {
    grid-template-columns: 1fr;
  }

  .session-upload-card__preview {
    max-width: 100%;
  }

  .session-authorship__head {
    align-items: flex-start;
    flex-direction: column;
  }

  .session-manual-grid,
  .session-author-override-grid,
  .session-meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>
