<template>
  <div class="admin-database admin-page">
    <AutosaveToast :message="revisionConfigToastMessage" :tone="revisionConfigToastTone" />

    <header class="page-header">
      <h1>Database</h1>
      <p class="page-subtitle">Manage backups, revisions, and migration into the next database year.</p>
    </header>

    <AdminPageTabs
      :tabs="tabs"
      :model-value="activeTab"
      @update:model-value="setActiveTab"
    />

    <template v-if="activeTab === 'overview'">
      <div v-if="loading" class="loading-state">Loading database overview...</div>
      <template v-else>
        <div class="config-card">
          <div class="card-header">
            <h2>Current Data Overview</h2>
            <p class="card-hint">Summary of the current database and media store.</p>
          </div>

          <div class="info-grid">
            <div class="info-section">
              <div class="info-section-heading">
                <h3>Database Collections</h3>
                <div class="collection-list-controls">
                  <label class="overview-sort">
                    <span>Group by</span>
                    <select v-model="collectionGroupingMode">
                      <option
                        v-for="mode in COLLECTION_GROUPING_MODES"
                        :key="`overview-group-${mode.value}`"
                        :value="mode.value"
                      >
                        {{ mode.label }}
                      </option>
                    </select>
                  </label>
                  <label class="overview-sort">
                    <span>Sort by</span>
                    <select v-model="overviewCollectionSort">
                      <option value="name">Name</option>
                      <option value="items">Items</option>
                    </select>
                  </label>
                </div>
              </div>
              <div class="collection-list">
                <div v-for="group in overviewCollectionGroups" :key="`overview-${group.id}`" class="collection-group">
                  <div class="collection-group-header">
                    <span class="collection-group-title">{{ group.label }}</span>
                    <span class="collection-group-meta">
                      {{ group.collections.length }} {{ group.collections.length === 1 ? 'collection' : 'collections' }} /
                      {{ group.totalCount }} {{ group.totalCount === 1 ? 'document' : 'documents' }}
                    </span>
                  </div>
                  <div class="collection-group-items">
                    <div v-for="coll in group.collections" :key="coll.name" class="collection-item">
                      <span class="collection-name">{{ formatCollectionName(coll.name) }}</span>
                      <span class="collection-count">{{ coll.count }} {{ coll.count === 1 ? 'document' : 'documents' }}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div class="info-total">
                Total: {{ collectionOptions?.total_documents || 0 }} documents
              </div>
            </div>

            <div class="info-section">
              <h3>Media Files</h3>
              <div v-if="backupInfo?.media_info" class="media-info">
                <div class="media-stat">
                  <span class="stat-label">Assets</span>
                  <span class="stat-value">{{ backupInfo.media_info.asset_count }}</span>
                </div>
                <div class="media-stat">
                  <span class="stat-label">Estimated Size</span>
                  <span class="stat-value">{{ backupInfo.media_info.estimated_size_mb }} MB</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </template>

    <template v-else-if="activeTab === 'backup'">
      <div v-if="loading" class="loading-state">Loading backup information...</div>
      <template v-else>
      <!-- Import Card -->
      <div class="config-card">
        <div class="card-header">
          <h2>Import Backup</h2>
          <p class="card-hint">Restore your website from a previously exported backup file.</p>
        </div>

        <div class="import-warning">
          <font-awesome-icon :icon="faTriangleExclamation" class="warning-icon" />
          <div>
            <strong>Warning:</strong> Importing a backup will replace all existing data. This action cannot be undone.
            Make sure to export a backup of your current data first.
          </div>
        </div>

        <div class="import-options">
          <label class="checkbox-option">
            <input type="checkbox" v-model="replaceExisting" />
            <span>Replace existing data</span>
            <span class="option-hint">(uncheck to merge with existing)</span>
          </label>
        </div>

        <div class="import-format-hint">
          <strong>Expected format:</strong> `.zip` backups named like
          `<code>fstvlpress_0000_YYYYMMDD_HHMMSS.zip</code>` (full) or
          `<code>fstvlpress_0001_YYYYMMDD_HHMMSS.zip</code>` (incremental).
          Each ZIP must include `manifest.json` and `data/*.json`;
          if media changes exist, include `media/manifest.json` and referenced `media/*` files.
        </div>

        <div class="import-zone" 
             :class="{ 'drag-over': dragOver }"
             @dragover.prevent="dragOver = true"
             @dragleave="dragOver = false"
             @drop.prevent="handleDrop">
          <input type="file" ref="fileInput" accept=".zip" multiple @change="handleFileSelect" style="display: none" />
          
          <div v-if="!selectedFiles.length" class="import-placeholder" @click="$refs.fileInput.click()">
            <font-awesome-icon :icon="faUpload" class="import-placeholder-icon" />
            <p>Drop one or more backup ZIP files here or click to select</p>
          </div>

          <div v-else class="selected-files">
            <div class="selected-files-header">
              <span>{{ selectedFiles.length }} file{{ selectedFiles.length === 1 ? '' : 's' }} selected</span>
              <button class="btn-outline" @click="clearFiles">Remove all</button>
            </div>
            <div v-for="(file, index) in selectedFiles" :key="`${file.name}-${file.size}-${file.lastModified}`" class="selected-file">
              <div class="file-info">
                <font-awesome-icon :icon="faFileZipper" class="file-info-icon" />
                <div>
                  <span class="file-name">{{ file.name }}</span>
                  <span class="file-size">{{ formatFileSize(file.size) }}</span>
                </div>
              </div>
              <button class="btn-outline" @click="removeSelectedFile(index)">Remove</button>
            </div>
          </div>
        </div>

        <div class="import-actions">
          <button class="btn-danger" @click="importBackup" :disabled="!selectedFiles.length || importing">
            <span v-if="importing">Importing... Please wait</span>
            <span v-else>Import Backup{{ selectedFiles.length > 1 ? 's' : '' }}</span>
          </button>
        </div>

        <div v-if="importStatus" class="status-message" :class="importStatus.type">
          <template v-if="importStatus.type === 'success'">
            <strong>Import successful!</strong>
            <ul v-if="importStatus.details">
              <li v-for="coll in importStatus.details.collections_imported" :key="coll.name">
                {{ formatCollectionName(coll.name) }}: {{ coll.count }} documents
              </li>
              <li v-if="importStatus.details.media_imported">
                Media files: {{ importStatus.details.media_imported }} imported
              </li>
            </ul>
            <div v-if="importStatus.details?.errors?.length" class="import-errors">
              <strong>Warnings:</strong>
              <ul>
                <li v-for="(err, i) in importStatus.details.errors" :key="i">{{ err }}</li>
              </ul>
            </div>
          </template>
          <template v-else>
            {{ importStatus.message }}
          </template>
        </div>
      </div>

      <!-- Export Card -->
      <div class="config-card">
        <div class="card-header">
          <h2>Export Backup</h2>
          <p class="card-hint">Download a complete or incremental backup of your website as a ZIP file.</p>
        </div>

        <!-- Backup History -->
        <div v-if="lastBackupInfo" class="backup-history">
          <div class="history-item" v-if="lastBackupInfo.last_export">
            <span class="history-label">Last export:</span>
            <span class="history-value">{{ formatDateTime(lastBackupInfo.last_export.timestamp) }}</span>
            <span class="history-type">{{ lastBackupInfo.last_export.type }}</span>
          </div>
          <div v-else class="history-item history-none">
            <span class="history-label">No previous backups recorded</span>
          </div>
        </div>

        <!-- Backup Type Selection -->
        <div class="backup-type-selector">
          <label class="radio-option" :class="{ selected: backupType === 'full' }">
            <input type="radio" v-model="backupType" value="full" />
            <div class="radio-content">
              <span class="radio-title">Full Backup</span>
              <span class="radio-desc">Export all data and media</span>
            </div>
          </label>
          <label class="radio-option" :class="{ selected: backupType === 'incremental' }">
            <input type="radio" v-model="backupType" value="incremental" />
            <div class="radio-content">
              <span class="radio-title">Incremental Backup</span>
              <span class="radio-desc">Only changes since last backup</span>
            </div>
          </label>
        </div>

        <!-- Incremental Options -->
        <div v-if="backupType === 'incremental'" class="incremental-options">
          <div class="incremental-since">
            <label>Changes since:</label>
            <VueDatePicker
              v-model="incrementalSince"
              :enable-time-picker="true"
              :clearable="true"
              :text-input="DATE_PICKER_TEXT_INPUT_OPTIONS"
              :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
              placeholder="Select date & time"
              :teleport="true"
              auto-apply
              class="datetime-picker"
            />
            <button 
              v-if="lastBackupInfo?.suggested_incremental_since" 
              class="btn-outline" 
              @click="useLastBackupTime"
            >
              Use last backup time
            </button>
          </div>
          
          <!-- Incremental Preview -->
          <div v-if="incrementalInfo" class="incremental-preview">
            <h4>Incremental backup will include:</h4>
            <div class="preview-stats">
              <span>{{ incrementalInfo.total_documents }} changed documents</span>
              <span v-if="includeMedia">{{ incrementalInfo.media_info?.asset_count || 0 }} new media files</span>
              <span v-if="includeMedia">(~{{ incrementalInfo.media_info?.estimated_size_mb || 0 }} MB)</span>
            </div>
          </div>
          
          <!-- Incremental Counter Info -->
          <div class="counter-info">
            <span class="counter-label">Next backup number:</span>
            <span class="counter-value">#{{ String(incrementalCounter + 1).padStart(4, '0') }}</span>
            <button 
              class="btn-outline btn-danger" 
              @click="resetIncrementalCounter"
              :disabled="resettingCounter"
            >
              {{ resettingCounter ? 'Resetting...' : 'Reset' }}
            </button>
          </div>
        </div>

        <div class="export-options">
          <label class="checkbox-option">
            <input type="checkbox" v-model="includeMedia" />
            <span>Include media files</span>
            <span class="option-hint">(images, videos, documents)</span>
          </label>
        </div>

        <div class="export-actions">
          <button class="btn-primary" @click="exportBackup" :disabled="exporting">
            <font-awesome-icon v-if="!exporting" :icon="faFileExport" class="btn-action-icon" />
            <span v-if="exporting">Exporting... Please wait</span>
            <span v-else>Download {{ backupType === 'incremental' ? 'Incremental' : 'Full' }} Backup</span>
          </button>
        </div>

        <div v-if="exportStatus" class="status-message" :class="exportStatus.type">
          {{ exportStatus.message }}
        </div>
      </div>
      </template>
    </template>

    <template v-else-if="activeTab === 'collections'">
      <div class="config-card">
        <div class="card-header">
          <h2>Import Collections</h2>
          <p class="card-hint">Import selected collections from a backup-shaped ZIP or raw JSON file.</p>
        </div>

        <div class="import-warning">
          <font-awesome-icon :icon="faTriangleExclamation" class="warning-icon" />
          <div>
            <strong>Careful:</strong> Replace mode clears each imported collection before inserting documents. Merge mode upserts by <code>_id</code>.
          </div>
        </div>

        <div class="backup-type-selector">
          <label class="radio-option" :class="{ selected: collectionImportMode === 'merge' }">
            <input type="radio" v-model="collectionImportMode" value="merge" />
            <div class="radio-content">
              <span class="radio-title">Merge existing</span>
              <span class="radio-desc">Upsert documents by _id, insert documents without _id</span>
            </div>
          </label>
          <label class="radio-option" :class="{ selected: collectionImportMode === 'replace' }">
            <input type="radio" v-model="collectionImportMode" value="replace" />
            <div class="radio-content">
              <span class="radio-title">Replace selected/imported collections</span>
              <span class="radio-desc">Clear imported target collections before insert</span>
            </div>
          </label>
        </div>

        <div class="reset-selection">
          <div class="card-header card-header--compact">
            <h3>Target Collection</h3>
            <p class="card-hint">Import one collection at a time. Multi-collection ZIPs belong in full backup import.</p>
          </div>

          <label class="summary-input-row">
            <span class="summary-label">Import into</span>
            <select v-model="collectionImportTarget" class="select-input">
              <option value="">Auto-detect from upload</option>
              <option v-for="coll in collectionTransferOptions" :key="`collection-target-${coll.name}`" :value="coll.name">
                {{ formatCollectionName(coll.name) }} ({{ coll.count }} docs)
              </option>
            </select>
          </label>
          <p class="option-hint">
            ZIP files auto-detect from their manifest. Raw JSON auto-detects only when the filename exactly matches a known collection.
          </p>
        </div>

        <div
          class="import-zone"
          :class="{ 'drag-over': collectionImportDragOver }"
          @dragover.prevent="collectionImportDragOver = true"
          @dragleave="collectionImportDragOver = false"
          @drop.prevent="handleCollectionImportDrop"
        >
          <input
            type="file"
            ref="collectionImportFileInput"
            accept=".zip,.json,application/json,application/zip"
            @change="handleCollectionImportFileSelect"
            style="display: none"
          />

          <div v-if="!collectionImportFile" class="import-placeholder" @click="$refs.collectionImportFileInput.click()">
            <font-awesome-icon :icon="faUpload" class="import-placeholder-icon" />
            <p>Drop a collection ZIP or JSON file here or click to select</p>
          </div>

          <div v-else class="selected-files">
            <div class="selected-file">
              <div class="file-info">
                <font-awesome-icon :icon="faFileZipper" class="file-info-icon" />
                <div>
                  <span class="file-name">{{ collectionImportFile.name }}</span>
                  <span class="file-size">{{ formatFileSize(collectionImportFile.size) }} · {{ formatCollectionImportFileKind(collectionImportFile) }}</span>
                </div>
              </div>
              <button class="btn-outline" type="button" @click="clearCollectionImportFile">Remove</button>
            </div>
          </div>
        </div>

        <div v-if="collectionImportDryRunLoading" class="status-message">
          Checking import file...
        </div>

        <div v-else-if="collectionImportDryRun" class="migration-summary collection-dry-run-summary">
          <div class="summary-row">
            <span class="summary-label">Target collection</span>
            <span class="summary-value">{{ formatCollectionName(collectionImportDryRun.target_collection || collectionImportDryRun.collection) }}</span>
          </div>
          <div class="summary-row">
            <span class="summary-label">Uploaded documents</span>
            <span class="summary-value">{{ collectionImportDryRun.document_count || 0 }}</span>
          </div>
          <div class="summary-row">
            <span class="summary-label">Known documents</span>
            <span class="summary-value">{{ collectionImportDryRun.known_documents || collectionImportDryRun.existing_documents || 0 }}</span>
          </div>
          <div class="summary-row">
            <span class="summary-label">New documents</span>
            <span class="summary-value">{{ collectionImportDryRun.new_documents || 0 }}</span>
          </div>
          <div class="summary-row">
            <span class="summary-label">Without _id</span>
            <span class="summary-value">{{ collectionImportDryRun.documents_without_id || 0 }}</span>
          </div>
          <div class="summary-row">
            <span class="summary-label">Duplicate _id entries</span>
            <span class="summary-value">{{ collectionImportDryRun.duplicate_ids_in_file || 0 }}</span>
          </div>
          <div v-if="collectionImportDryRun.warnings?.length" class="import-errors collection-dry-run-warnings">
            <strong>Warnings:</strong>
            <ul>
              <li v-for="(warning, i) in collectionImportDryRun.warnings" :key="`dry-run-warning-${i}`">{{ warning }}</li>
            </ul>
          </div>
        </div>

        <div v-if="collectionImportDryRunError" class="status-message error">
          {{ collectionImportDryRunError }}
        </div>

        <div class="import-actions">
          <button
            class="btn-primary"
            type="button"
            :disabled="collectionImporting || !canImportCollections"
            @click="importCollections"
          >
            <span v-if="collectionImporting">Importing collection...</span>
            <span v-else>Import Collection</span>
          </button>
        </div>

        <div v-if="collectionImportStatus" class="status-message" :class="collectionImportStatus.type">
          <template v-if="collectionImportStatus.type === 'success'">
            <strong>Import successful!</strong>
            <ul v-if="collectionImportStatus.details?.collections_imported?.length">
              <li v-for="coll in collectionImportStatus.details.collections_imported" :key="coll.name">
                {{ formatCollectionName(coll.name) }}: {{ coll.count }} documents
              </li>
            </ul>
            <div v-if="collectionImportStatus.details?.collections_skipped?.length" class="import-errors">
              <strong>Skipped:</strong>
              <ul>
                <li v-for="(entry, i) in collectionImportStatus.details.collections_skipped" :key="`skipped-${i}`">{{ entry }}</li>
              </ul>
            </div>
            <div v-if="collectionImportStatus.details?.errors?.length" class="import-errors">
              <strong>Warnings:</strong>
              <ul>
                <li v-for="(err, i) in collectionImportStatus.details.errors" :key="`collection-error-${i}`">{{ err }}</li>
              </ul>
            </div>
          </template>
          <template v-else>
            {{ collectionImportStatus.message }}
          </template>
        </div>
      </div>

      <div class="config-card">
        <div class="card-header">
          <h2>Export Collections</h2>
          <p class="card-hint">Download selected database collections as a ZIP using the backup archive format.</p>
        </div>

        <div class="reset-selection">
          <div v-if="collectionTransferOptions.length" class="collection-group-toolbar">
            <div class="reset-selection-actions">
              <button class="btn-outline" type="button" @click="selectAllCollectionExports">Select all</button>
              <button class="btn-outline" type="button" @click="unselectAllCollectionExports">Unselect all</button>
            </div>
            <label class="overview-sort">
              <span>Group by</span>
              <select v-model="collectionGroupingMode">
                <option
                  v-for="mode in COLLECTION_GROUPING_MODES"
                  :key="`export-group-${mode.value}`"
                  :value="mode.value"
                >
                  {{ mode.label }}
                </option>
              </select>
            </label>
          </div>

          <div v-if="collectionTransferOptions.length" class="collection-group-list">
            <div
              v-for="group in collectionTransferGroups"
              :key="`collection-export-group-${group.id}`"
              class="collection-group"
            >
              <div class="collection-group-header">
                <div>
                  <span class="collection-group-title">{{ group.label }}</span>
                  <span class="collection-group-meta">
                    {{ group.collections.length }} {{ group.collections.length === 1 ? 'collection' : 'collections' }} /
                    {{ group.totalCount }} docs
                  </span>
                </div>
                <div class="collection-group-actions">
                  <button class="btn-outline" type="button" @click="selectCollectionExportGroup(group.collections)">Select all</button>
                  <button class="btn-outline" type="button" @click="unselectCollectionExportGroup(group.collections)">Unselect all</button>
                </div>
              </div>

              <div class="reset-selection-list collection-group-items">
                <label
                  v-for="coll in group.collections"
                  :key="`collection-export-${coll.name}`"
                  class="checkbox-option reset-selection-option"
                >
                  <input type="checkbox" :value="coll.name" v-model="collectionExportSelections" />
                  <span>
                    {{ formatCollectionName(coll.name) }}
                    <span class="option-hint">({{ coll.count }} docs)</span>
                  </span>
                </label>
              </div>
            </div>
          </div>
          <div v-else class="status-message">
            No collections available for export.
          </div>
        </div>

        <div class="export-options">
          <label class="checkbox-option" :class="{ disabled: !isAssetsCollectionSelectedForExport }">
            <input
              type="checkbox"
              v-model="collectionIncludeMedia"
              :disabled="!isAssetsCollectionSelectedForExport"
            />
            <span>Include media files</span>
            <span class="option-hint">(available when Assets is selected)</span>
          </label>
        </div>

        <div class="export-actions">
          <button
            class="btn-primary"
            type="button"
            :disabled="collectionExporting || !normalizedCollectionExportSelections.length"
            @click="exportCollections"
          >
            <font-awesome-icon v-if="!collectionExporting" :icon="faFileExport" class="btn-action-icon" />
            <span v-if="collectionExporting">Exporting collections...</span>
            <span v-else>Download Collections ZIP</span>
          </button>
        </div>

        <div v-if="collectionExportStatus" class="status-message" :class="collectionExportStatus.type">
          {{ collectionExportStatus.message }}
        </div>
      </div>

    </template>

    <template v-else-if="activeTab === 'revisions'">
      <div v-if="revisionConfigLoading" class="loading-state">Loading revision settings...</div>
      <template v-else>
        <div class="config-card">
          <div class="card-header">
            <h2>Global Design Revisions</h2>
            <p class="card-hint">Control whether undo/redo for global design settings is shown and tracked.</p>
          </div>
          <label class="checkbox-option">
            <input
              type="checkbox"
              :checked="revisionConfig.show_global_design_revisions"
              @change="setGlobalDesignRevisions($event.target.checked)"
            />
            <span>Show global design revisions</span>
          </label>
        </div>

        <div class="config-card">
          <div class="card-header">
            <h2>Section Revision Rules</h2>
            <p class="card-hint">Choose per section type whether revisions include content and/or design overrides.</p>
          </div>

          <div class="revision-table-wrap">
            <table class="revision-table">
              <thead>
                <tr>
                  <th>Section Type</th>
                  <th>
                    <div class="th-with-toggle">
                      <span>Design</span>
                      <input
                        type="checkbox"
                        :checked="allDesignChecked"
                        :indeterminate.prop="designIndeterminate"
                        @change="setAllSectionRevisionOptions('include_design', $event.target.checked)"
                      />
                    </div>
                  </th>
                  <th>
                    <div class="th-with-toggle">
                      <span>Content</span>
                      <input
                        type="checkbox"
                        :checked="allContentChecked"
                        :indeterminate.prop="contentIndeterminate"
                        @change="setAllSectionRevisionOptions('include_content', $event.target.checked)"
                      />
                    </div>
                  </th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td class="section-type-cell">Header</td>
                  <td>
                    <input
                      type="checkbox"
                      :checked="getHeaderRevisionOption('include_design')"
                      @change="setHeaderRevisionOption('include_design', $event.target.checked)"
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      :checked="getHeaderRevisionOption('include_content')"
                      @change="setHeaderRevisionOption('include_content', $event.target.checked)"
                    />
                  </td>
                  <td>
                    <span v-if="!isHeaderRevisionVisible()" class="status-badge hidden">Hidden</span>
                    <span v-else class="status-badge shown">Visible</span>
                  </td>
                </tr>
                <tr v-for="sectionType in sectionTypes" :key="sectionType">
                  <td class="section-type-cell">{{ formatSectionType(sectionType) }}</td>
                  <td>
                    <input
                      type="checkbox"
                      :checked="getSectionRevisionOption(sectionType, 'include_design')"
                      @change="setSectionRevisionOption(sectionType, 'include_design', $event.target.checked)"
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      :checked="getSectionRevisionOption(sectionType, 'include_content')"
                      @change="setSectionRevisionOption(sectionType, 'include_content', $event.target.checked)"
                    />
                  </td>
                  <td>
                    <span v-if="!isSectionRevisionVisible(sectionType)" class="status-badge hidden">Hidden</span>
                    <span v-else class="status-badge shown">Visible</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

        </div>

      </template>
    </template>

    <template v-else-if="activeTab === 'migration'">
      <div v-if="migrationLoading" class="loading-state">Loading migration options...</div>
      <template v-else>
        <div class="config-card">
          <div class="card-header">
            <h2>Target Database</h2>
            <p class="card-hint">Create a new MongoDB database from the current one. Suggested naming is next year.</p>
          </div>
          <div class="migration-summary">
            <div class="summary-row">
              <span class="summary-label">Current DB</span>
              <span class="summary-value">{{ migrationOptions?.source_db || 'unknown' }}</span>
            </div>
            <label class="summary-input-row">
              <span class="summary-label">Target DB</span>
              <input v-model.trim="migrationTargetDb" class="text-input" placeholder="e.g. 2027" />
            </label>
          </div>
        </div>

        <div class="config-card">
          <div class="card-header">
            <h2>Collection Strategy</h2>
            <p class="card-hint">Choose whether to copy data, create empty collections, or skip each collection.</p>
          </div>
          <div v-if="migrationCollections.length" class="collection-group-toolbar">
            <label class="overview-sort">
              <span>Group by</span>
              <select v-model="collectionGroupingMode">
                <option
                  v-for="mode in COLLECTION_GROUPING_MODES"
                  :key="`migration-group-${mode.value}`"
                  :value="mode.value"
                >
                  {{ mode.label }}
                </option>
              </select>
            </label>
          </div>
          <div class="collection-group-list">
            <div
              v-for="group in migrationCollectionGroups"
              :key="`migration-group-${group.id}`"
              class="collection-group"
            >
              <div class="collection-group-header">
                <div>
                  <span class="collection-group-title">{{ group.label }}</span>
                  <span class="collection-group-meta">
                    {{ group.collections.length }} {{ group.collections.length === 1 ? 'collection' : 'collections' }} /
                    {{ group.totalCount }} docs
                  </span>
                </div>
                <div class="collection-group-actions">
                  <button class="btn-outline" type="button" @click="setMigrationGroupMode(group.collections, 'copy')">Select all</button>
                  <button class="btn-outline" type="button" @click="setMigrationGroupMode(group.collections, 'empty')">Empty all</button>
                  <button class="btn-outline" type="button" @click="setMigrationGroupMode(group.collections, 'skip')">Unselect all</button>
                </div>
              </div>
              <div class="migration-table-wrap">
                <table class="migration-table">
                  <colgroup>
                    <col class="migration-table-col--collection" />
                    <col class="migration-table-col--documents" />
                    <col class="migration-table-col--action" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th>Collection</th>
                      <th>Documents</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="coll in group.collections" :key="coll.name">
                      <td>{{ formatCollectionName(coll.name) }}</td>
                      <td>{{ coll.count }}</td>
                      <td>
                        <select v-model="migrationSelections[coll.name]" class="select-input">
                          <option value="copy">Copy data</option>
                          <option value="empty">Create empty collection</option>
                          <option value="skip">Skip</option>
                        </select>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          <div class="migration-selected-summary">
            <span>Copy: {{ migrationSelectionSummary.copy }}</span>
            <span>Empty: {{ migrationSelectionSummary.empty }}</span>
            <span>Skip: {{ migrationSelectionSummary.skip }}</span>
          </div>
        </div>

        <div class="config-card">
          <div class="card-header">
            <h2>Bucket Strategy (MinIO/S3)</h2>
            <p class="card-hint">Optionally create a new bucket or copy current bucket contents.</p>
          </div>
          <template v-if="migrationOptions?.bucket?.available">
            <div class="migration-summary">
              <div class="summary-row">
                <span class="summary-label">Current bucket</span>
                <span class="summary-value">{{ migrationOptions.bucket.current_bucket }}</span>
              </div>
            </div>
            <div class="bucket-options">
              <label class="radio-option" :class="{ selected: migrationBucketMode === 'none' }">
                <input type="radio" v-model="migrationBucketMode" value="none" />
                <div class="radio-content">
                  <span class="radio-title">Keep current bucket</span>
                  <span class="radio-desc">No new bucket action.</span>
                </div>
              </label>
              <label class="radio-option" :class="{ selected: migrationBucketMode === 'create_new' }">
                <input type="radio" v-model="migrationBucketMode" value="create_new" />
                <div class="radio-content">
                  <span class="radio-title">Create new bucket</span>
                  <span class="radio-desc">Creates an empty bucket for the new DB.</span>
                </div>
              </label>
              <label class="radio-option" :class="{ selected: migrationBucketMode === 'copy_existing' }">
                <input type="radio" v-model="migrationBucketMode" value="copy_existing" />
                <div class="radio-content">
                  <span class="radio-title">Copy current bucket</span>
                  <span class="radio-desc">Creates target bucket and copies all current objects.</span>
                </div>
              </label>
            </div>
            <label v-if="migrationBucketMode !== 'none'" class="summary-input-row">
              <span class="summary-label">Target bucket</span>
              <input v-model.trim="migrationTargetBucket" class="text-input" :placeholder="migrationOptions.bucket.suggested_target_bucket || 'new-bucket-name'" />
            </label>
          </template>
          <div v-else class="status-message">
            Bucket migration is only available with S3/MinIO storage.
          </div>
        </div>

        <div class="config-card">
          <div class="card-header">
            <h2>Execute Migration</h2>
            <p class="card-hint">This creates a new database. Existing target DB names are rejected for safety.</p>
          </div>
          <div class="export-actions">
            <button class="btn-primary" @click="runMigration" :disabled="migrationSubmitting || !migrationTargetDb">
              <span v-if="migrationSubmitting">Creating database migration...</span>
              <span v-else>Create Migration</span>
            </button>
          </div>
          <div v-if="migrationStatus" class="status-message" :class="migrationStatus.type">
            {{ migrationStatus.message }}
          </div>
        </div>

      </template>
    </template>

    <template v-else-if="activeTab === 'reset'">
      <div class="config-card">
        <div class="card-header">
          <h2>Content Cleanup</h2>
          <p class="card-hint">Remove unreferenced content records, unused media, generated redirects, and revision history.</p>
        </div>

        <div class="cleanup-section">
          <div class="card-header card-header--compact">
            <h3>Internal</h3>
            <p class="card-hint">Remove generated internal records and revision history.</p>
          </div>

          <div class="cleanup-action-list">
            <div class="cleanup-action-row">
              <div>
                <div class="cleanup-action-title">Generated Redirects</div>
                <p class="option-hint">Generated sitemap redirects. Custom redirects are preserved.</p>
              </div>
              <div class="cleanup-action-meta">
                <span class="cleanup-count">
                  {{ loadingCleaningCounts ? 'Loading...' : cleanupCountLabel(generatedRedirectsCount, 'redirect') }}
                </span>
                <button
                  class="btn-danger"
                  type="button"
                  :disabled="loadingCleaningCounts || cleaningGeneratedRedirects || generatedRedirectsCount <= 0"
                  @click="cleanupGeneratedRedirects"
                >
                  <span v-if="cleaningGeneratedRedirects">Deleting...</span>
                  <span v-else>Delete Generated Redirects</span>
                </button>
              </div>
            </div>

            <div class="cleanup-action-row">
              <div>
                <div class="cleanup-action-title">Revision History</div>
                <p class="option-hint">Undo/redo history for sections, headers, design settings, and the DevOps changelog.</p>
              </div>
              <div class="cleanup-action-meta">
                <button
                  class="btn-danger"
                  type="button"
                  :disabled="clearingRevisionHistory"
                  @click="clearAllRevisionHistory"
                >
                  <span v-if="clearingRevisionHistory">Deleting...</span>
                  <span v-else>Delete All Revision History</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="cleanup-section">
          <div class="card-header card-header--compact">
            <h3>Unused</h3>
            <p class="card-hint">Find and delete content records or media files that are no longer used.</p>
          </div>

          <div class="cleanup-action-list">
            <div class="cleanup-action-row">
              <div>
                <div class="cleanup-action-title">Unused Headers</div>
                <p class="option-hint">Headers that are neither shared nor used on any page.</p>
              </div>
              <div class="cleanup-action-meta">
                <span class="cleanup-count">
                  {{ loadingCleaningCounts ? 'Loading...' : cleanupCountLabel(unusedHeadersCount, 'header') }}
                </span>
                <button
                  class="btn-danger"
                  type="button"
                  :disabled="loadingCleaningCounts || cleaningUnusedHeaders || unusedHeadersCount <= 0"
                  @click="cleanupUnusedHeaders"
                >
                  <span v-if="cleaningUnusedHeaders">Deleting...</span>
                  <span v-else>Delete Unused Headers</span>
                </button>
              </div>
            </div>

            <div class="cleanup-action-row">
              <div>
                <div class="cleanup-action-title">Unused Sections</div>
                <p class="option-hint">Sections that are neither shared nor used on any page.</p>
              </div>
              <div class="cleanup-action-meta">
                <span class="cleanup-count">
                  {{ loadingCleaningCounts ? 'Loading...' : cleanupCountLabel(unusedSectionsCount, 'section') }}
                </span>
                <button
                  class="btn-danger"
                  type="button"
                  :disabled="loadingCleaningCounts || cleaningUnusedSections || unusedSectionsCount <= 0"
                  @click="cleanupUnusedSections"
                >
                  <span v-if="cleaningUnusedSections">Deleting...</span>
                  <span v-else>Delete Unused Sections</span>
                </button>
              </div>
            </div>

            <div class="cleanup-action-row">
              <div>
                <div class="cleanup-action-title">Unused Media</div>
                <p class="option-hint">Step 1: find unused files. Step 2: clean up selected files. Find results stay in this browser session.</p>
              </div>
              <div class="cleanup-action-meta">
                <button class="btn-primary" type="button" :disabled="findingUnusedMedia || removingUnusedMedia" @click="findUnusedMediaFiles">
                  <span v-if="findingUnusedMedia">Finding unused media...</span>
                  <span v-else>Find Unused Media Files</span>
                </button>
                <button
                  class="btn-danger"
                  type="button"
                  :disabled="findingUnusedMedia || removingUnusedMedia || !canCleanupUnusedMedia"
                  @click="cleanupUnusedMediaFiles"
                >
                  <span v-if="removingUnusedMedia">Cleaning up unused media...</span>
                  <span v-else>Cleanup Unused Media Files</span>
                </button>
              </div>
            </div>
          </div>

          <div v-if="unusedMediaFindResult" class="unused-media-results">
            <p class="unused-media-summary">
              Detected {{ Number(unusedMediaFindResult.assets_unused || 0) }} unreferenced file(s)
              out of {{ Number(unusedMediaFindResult.assets_total || 0) }} total.
            </p>
            <p class="unused-media-summary" v-if="unusedMediaExcludedAssetIds.length > 0">
              Excluded {{ unusedMediaExcludedAssetIds.length }} file(s) from cleanup.
            </p>
            <p class="unused-media-summary" v-if="unusedMediaSelectedForCleanupCount > 0">
              {{ unusedMediaSelectedForCleanupCount }} file(s) currently selected for cleanup.
            </p>
            <p class="unused-media-scan-meta" v-if="unusedMediaFindResult.scan_created_at">
              Session result from {{ formatDateTime(unusedMediaFindResult.scan_created_at) }}.
            </p>

            <div v-if="Array.isArray(unusedMediaFindResult.unused_assets) && unusedMediaFindResult.unused_assets.length" class="unused-media-list-wrap">
              <div class="unused-media-selection-actions">
                <button class="btn-outline" type="button" @click="excludeAllUnusedMediaResults">Exclude all</button>
                <button class="btn-outline" type="button" @click="clearUnusedMediaExclusions">Include all</button>
              </div>
              <ul class="unused-media-list">
                <li
                  v-for="asset in unusedMediaFindResult.unused_assets"
                  :key="asset.asset_id"
                  :class="{ 'unused-media-list-item--excluded': isUnusedMediaAssetExcluded(asset.asset_id) }"
                >
                  <label class="unused-media-exclude-option">
                    <input
                      type="checkbox"
                      :value="asset.asset_id"
                      v-model="unusedMediaExcludedAssetIds"
                    />
                    <span>Exclude</span>
                  </label>
                  <code>{{ asset.filename || '(no filename)' }}</code>
                  <span> · {{ asset.content_type || 'unknown type' }} · id {{ asset.asset_id }}</span>
                </li>
              </ul>
            </div>
            <div v-else class="status-message success">
              No unused media files found in this scan.
            </div>
          </div>

          <div v-if="removeUnusedMediaStatus" class="status-message" :class="removeUnusedMediaStatus.type">
            {{ removeUnusedMediaStatus.message }}
          </div>
        </div>

        <div v-if="cleaningLoadError" class="status-message error">
          Failed to load cleaning counts: {{ cleaningLoadError }}
        </div>
        <div v-if="cleaningStatus" class="status-message" :class="cleaningStatus.type">
          {{ cleaningStatus.message }}
        </div>
        <div v-if="clearRevisionStatus" class="status-message" :class="clearRevisionStatus.type">
          {{ clearRevisionStatus.message }}
        </div>
      </div>

      <div class="config-card">
        <div class="card-header">
          <h2>Database Cleanup</h2>
          <p class="card-hint">Delete selected database collections and optionally remove object data from the configured bucket.</p>
        </div>

        <div class="import-warning reset-warning">
          <font-awesome-icon :icon="faTriangleExclamation" class="warning-icon" />
          <div>
            <strong>Danger:</strong> This removes data from the selected collections (for example pages, sections, headers, assets metadata, templates, revisions, integrations, and config docs).
            Baseline initialization runs afterward.
          </div>
        </div>

        <div class="cleanup-section">
          <div class="card-header card-header--compact">
            <h3>Collections To Delete</h3>
            <p class="card-hint">Only selected collections are cleared. Unselected collections are preserved.</p>
          </div>

          <div v-if="resetCollectionOptions.length" class="collection-group-toolbar">
            <div class="reset-selection-actions">
              <button class="btn-outline" type="button" @click="selectAllResetDeleteCollections">Select all</button>
              <button class="btn-outline" type="button" @click="clearResetDeleteCollections">Clear</button>
            </div>
            <label class="overview-sort">
              <span>Group by</span>
              <select v-model="collectionGroupingMode">
                <option
                  v-for="mode in COLLECTION_GROUPING_MODES"
                  :key="`reset-group-${mode.value}`"
                  :value="mode.value"
                >
                  {{ mode.label }}
                </option>
              </select>
            </label>
          </div>

          <div v-if="resetCollectionOptions.length" class="collection-group-list">
            <div
              v-for="group in resetCollectionGroups"
              :key="`reset-delete-group-${group.id}`"
              class="collection-group"
            >
              <div class="collection-group-header">
                <div>
                  <span class="collection-group-title">{{ group.label }}</span>
                  <span class="collection-group-meta">
                    {{ group.collections.length }} {{ group.collections.length === 1 ? 'collection' : 'collections' }} /
                    {{ group.totalCount }} docs
                  </span>
                </div>
                <div class="collection-group-actions">
                  <button class="btn-outline" type="button" @click="selectResetDeleteGroup(group.collections)">Select all</button>
                  <button class="btn-outline" type="button" @click="unselectResetDeleteGroup(group.collections)">Unselect all</button>
                </div>
              </div>

              <div class="reset-selection-list collection-group-items">
                <label
                  v-for="coll in group.collections"
                  :key="`reset-delete-${coll.name}`"
                  class="checkbox-option reset-selection-option"
                >
                  <input type="checkbox" :value="coll.name" v-model="resetDeleteCollections" />
                  <span>
                    {{ formatCollectionName(coll.name) }}
                    <span class="option-hint">({{ coll.count }} docs)</span>
                  </span>
                </label>
              </div>
            </div>
          </div>
          <div v-else class="status-message">
            No collections available for deletion.
          </div>
        </div>

        <div class="cleanup-section">
          <div class="card-header card-header--compact">
            <h3>Bucket Cleanup</h3>
            <p class="card-hint">Optionally remove object data from selected top-level directories in the configured S3/MinIO bucket.</p>
          </div>

          <template v-if="resetBucketCleanupAvailable">
            <label class="checkbox-option reset-bucket-option">
              <input type="checkbox" v-model="resetDeleteBucketData" />
              <span>
                Delete objects in bucket
                <code>{{ resetCurrentBucketName }}</code>.
              </span>
            </label>
            <p class="option-hint">This permanently deletes files under selected top-level directories.</p>

            <template v-if="resetDeleteBucketData">
              <div v-if="resetBucketPrefixOptions.length" class="reset-selection-actions reset-selection-actions--bucket">
                <button class="btn-outline" type="button" @click="selectAllResetBucketPrefixes">Select all</button>
                <button class="btn-outline" type="button" @click="clearResetBucketPrefixes">Clear</button>
              </div>
              <div v-if="resetBucketPrefixOptions.length" class="reset-selection-list">
                <label
                  v-for="prefix in resetBucketPrefixOptions"
                  :key="`reset-bucket-prefix-${prefix}`"
                  class="checkbox-option reset-selection-option"
                >
                  <input type="checkbox" :value="prefix" v-model="resetSelectedBucketPrefixes" />
                  <span><code>{{ prefix }}/</code></span>
                </label>
              </div>
              <div v-else class="status-message">
                No top-level directories found in this bucket.
              </div>
            </template>
            <div v-if="resetBucketPrefixesError" class="status-message error">
              Failed to list bucket directories: {{ resetBucketPrefixesError }}
            </div>
          </template>
          <div v-else class="status-message">
            Bucket cleanup is only available when S3/MinIO storage is enabled.
          </div>
        </div>

        <div class="export-options">
          <label class="checkbox-option">
            <input type="checkbox" v-model="resetAllConfirmChecked" />
            <span>I understand this is destructive and irreversible.</span>
          </label>
        </div>

        <div class="export-actions">
          <button class="btn-danger" :disabled="resettingAllData || !resetAllConfirmChecked" @click="resetAllStoredData">
            <span v-if="resettingAllData">Resetting database...</span>
            <span v-else>Delete Selected Stored Data</span>
          </button>
        </div>

        <div v-if="resetAllStatus" class="status-message" :class="resetAllStatus.type">
          {{ resetAllStatus.message }}
        </div>
      </div>

    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  faFileExport,
  faFileZipper,
  faTriangleExclamation,
  faUpload,
} from "@fortawesome/free-solid-svg-icons";
import { VueDatePicker } from '@vuepic/vue-datepicker';
import { getToken } from '../../services/auth.js';
import { resolveApiBase } from '../../services/apiBase.js';
import * as api from '../../services/api.js';
import AdminPageTabs from '../../components/admin/AdminPageTabs.vue';
import AutosaveToast from "../../components/admin/AutosaveToast.vue";
import {
  DATE_PICKER_DATE_TIME_DISPLAY_FORMATS,
  DATE_PICKER_TEXT_INPUT_OPTIONS,
  formatDateTimeLocalForServerTimezone,
  formatInstantInServerTimezone,
  serverWallDateTimeToInstantDate,
  serverWallDateTimeToLocalDate,
} from '../../utils/revisionTime.js';
import '@vuepic/vue-datepicker/dist/main.css';

const API_BASE = resolveApiBase();
const route = useRoute();
const router = useRouter();

function getAuthHeaders(existingHeaders = {}) {
  const headers = { ...existingHeaders };
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function authFetch(url, options = {}) {
  return fetch(url, {
    // API auth is Bearer-based; avoid sending cookie bloat on every request.
    credentials: 'omit',
    ...options,
    headers: getAuthHeaders(options.headers || {}),
  });
}

function formatBackupResponseDetail(payload, responseText, fallbackMessage) {
  const detail = payload && typeof payload === 'object' && Object.prototype.hasOwnProperty.call(payload, 'detail')
    ? payload.detail
    : payload?.message;
  if (typeof detail === 'string' && detail.trim()) return detail.trim();
  if (detail !== undefined && detail !== null) {
    try {
      return JSON.stringify(detail);
    } catch {
      return String(detail);
    }
  }

  const normalizedText = String(responseText || '')
    .replace(/<[^>]*>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (normalizedText) return normalizedText.slice(0, 300);
  return fallbackMessage;
}

async function readBackupJsonResponse(response, fallbackMessage = 'Backup request failed') {
  const responseText = await response.text();
  let payload = null;
  if (responseText.trim()) {
    try {
      payload = JSON.parse(responseText);
    } catch {
      payload = null;
    }
  }

  if (response.ok) {
    if (payload !== null) return payload;
    if (!responseText.trim()) return {};
    throw new Error(
      `Backup API returned a non-JSON response (${response.status}). ${formatBackupResponseDetail(null, responseText, 'No response details available')}`
    );
  }

  if (response.status === 413) {
    throw new Error(
      'Backup upload was rejected as too large. Increase BACKUP_UPLOAD_MAX_BODY_SIZE on the frontend service and align any external proxy/CDN request body limit.'
    );
  }

  if (response.status === 502 || response.status === 504) {
    throw new Error(
      'Backup import timed out or the gateway closed the connection. Increase BACKUP_PROXY_READ_TIMEOUT and any external proxy upstream timeout.'
    );
  }

  const detail = formatBackupResponseDetail(payload, responseText, fallbackMessage);
  throw new Error(detail);
}

async function readBackupImportResponse(response) {
  return readBackupJsonResponse(response, 'Import failed');
}

const loading = ref(true);
const backupInfo = ref(null);
const collectionOptions = ref(null);
const overviewCollectionSort = ref('name');
const collectionGroupingMode = ref('category');
const lastBackupInfo = ref(null);
const incrementalInfo = ref(null);
const includeMedia = ref(true);
const replaceExisting = ref(true);
const exporting = ref(false);
const importing = ref(false);
const exportStatus = ref(null);
const importStatus = ref(null);
const selectedFiles = ref([]);
const dragOver = ref(false);
const fileInput = ref(null);
const collectionExportSelections = ref([]);
const collectionExportSelectionsInitialized = ref(false);
const collectionIncludeMedia = ref(false);
const collectionExporting = ref(false);
const collectionExportStatus = ref(null);
const collectionImportTarget = ref('');
const collectionImportMode = ref('merge');
const collectionImportFile = ref(null);
const collectionImportFileInput = ref(null);
const collectionImportDragOver = ref(false);
const collectionImporting = ref(false);
const collectionImportStatus = ref(null);
const collectionImportDryRun = ref(null);
const collectionImportDryRunError = ref('');
const collectionImportDryRunLoading = ref(false);
let collectionImportDryRunToken = 0;
const backupType = ref('full');
const incrementalSince = ref(null);
const incrementalCounter = ref(0);
const resettingCounter = ref(false);
const tabs = [
  { id: 'overview', label: 'Overview', to: '/admin/database/overview' },
  { id: 'backup', label: 'Backups', to: '/admin/database/backups' },
  { id: 'collections', label: 'Collections', to: '/admin/database/collections' },
  { id: 'migration', label: 'Migration', to: '/admin/database/migration' },
  { id: 'revisions', label: 'Revisions', to: '/admin/database/revisions' },
  { id: 'reset', label: 'Cleaning', to: '/admin/database/cleaning' },
];
const DATABASE_TAB_BY_SLUG = {
  overview: 'overview',
  backups: 'backup',
  collections: 'collections',
  migration: 'migration',
  revisions: 'revisions',
  cleaning: 'reset',
  reset: 'reset',
};
const activeTab = computed(() => {
  const slug = String(route.path || '').split('/')[3] || '';
  return DATABASE_TAB_BY_SLUG[slug] || tabs[0].id;
});

const COLLECTION_GROUPING_MODES = [
  { value: 'none', label: 'No grouping' },
  { value: 'category', label: 'Group' },
  { value: 'prefix', label: 'Shared prefix' },
];

const revisionConfigLoading = ref(false);
const revisionConfigSaving = ref(false);
const revisionConfigDirty = ref(false);
const revisionConfigStatus = ref(null);
const clearingRevisionHistory = ref(false);
const clearRevisionStatus = ref(null);
const sectionTypes = ref([]);
const REVISION_AUTOSAVE_DELAY_MS = 500;
let revisionAutosaveTimer = null;
let revisionAutosaveQueued = false;
let revisionConfigStatusTimer = null;
const revisionConfig = ref({
  show_global_design_revisions: true,
  header: {
    include_design: true,
    include_content: true,
  },
  section_types: {},
});

const migrationLoading = ref(false);
const migrationSubmitting = ref(false);
const migrationOptions = ref(null);
const migrationTargetDb = ref('');
const migrationSelections = ref({});
const migrationBucketMode = ref('none');
const migrationTargetBucket = ref('');
const migrationStatus = ref(null);
const UNUSED_MEDIA_FIND_RESULT_STORAGE_KEY = 'admin_database_unused_media_find_result';
const resettingAllData = ref(false);
const resetAllConfirmChecked = ref(false);
const resetAllStatus = ref(null);
const resetDeleteCollections = ref([]);
const resetDeleteBucketData = ref(false);
const resetSelectedBucketPrefixes = ref([]);
const findingUnusedMedia = ref(false);
const removingUnusedMedia = ref(false);
const unusedMediaFindResult = ref(null);
const unusedMediaExcludedAssetIds = ref([]);
const removeUnusedMediaStatus = ref(null);
const loadingCleaningCounts = ref(false);
const cleaningLoadError = ref('');
const cleaningStatus = ref(null);
const cleaningUnusedHeaders = ref(false);
const cleaningUnusedSections = ref(false);
const cleaningGeneratedRedirects = ref(false);
const unusedHeadersCount = ref(0);
const unusedSectionsCount = ref(0);
const generatedRedirects = ref([]);
const generatedRedirectsCount = computed(() => generatedRedirects.value.length);

function normalizeSectionTypeOptions(options = {}) {
  return {
    include_design: options?.include_design !== false,
    include_content: options?.include_content !== false,
  };
}

function normalizeHeaderOptions(options = {}) {
  return {
    include_design: options?.include_design !== false,
    include_content: options?.include_content !== false,
  };
}

function ensureSectionConfig(sectionType) {
  if (!revisionConfig.value.section_types) {
    revisionConfig.value.section_types = {};
  }
  const current = revisionConfig.value.section_types[sectionType];
  const isValid =
    current &&
    typeof current.include_design === 'boolean' &&
    typeof current.include_content === 'boolean';
  if (isValid) {
    return current;
  }
  const normalized = normalizeSectionTypeOptions(current);
  revisionConfig.value.section_types[sectionType] = normalized;
  return normalized;
}

function getSectionRevisionOption(sectionType, option) {
  const config = ensureSectionConfig(sectionType);
  return option === 'include_design' ? config.include_design : config.include_content;
}

function setSectionRevisionOption(sectionType, option, checked) {
  const config = ensureSectionConfig(sectionType);
  if (option === 'include_design') config.include_design = !!checked;
  if (option === 'include_content') config.include_content = !!checked;
  queueRevisionConfigAutosave();
}

function ensureHeaderConfig() {
  const current = revisionConfig.value.header;
  const isValid =
    current &&
    typeof current.include_design === 'boolean' &&
    typeof current.include_content === 'boolean';
  if (isValid) {
    return current;
  }
  const normalized = normalizeHeaderOptions(current);
  revisionConfig.value.header = normalized;
  return normalized;
}

function getHeaderRevisionOption(option) {
  const config = ensureHeaderConfig();
  return option === 'include_design' ? config.include_design : config.include_content;
}

function setHeaderRevisionOption(option, checked) {
  const config = ensureHeaderConfig();
  if (option === 'include_design') config.include_design = !!checked;
  if (option === 'include_content') config.include_content = !!checked;
  queueRevisionConfigAutosave();
}

function isHeaderRevisionVisible() {
  const config = ensureHeaderConfig();
  return !!(config.include_design || config.include_content);
}

function setGlobalDesignRevisions(checked) {
  revisionConfig.value.show_global_design_revisions = !!checked;
  queueRevisionConfigAutosave();
}

function setAllSectionRevisionOptions(option, checked) {
  const header = ensureHeaderConfig();
  if (option === 'include_design') header.include_design = !!checked;
  if (option === 'include_content') header.include_content = !!checked;

  sectionTypes.value.forEach((sectionType) => {
    const config = ensureSectionConfig(sectionType);
    if (option === 'include_design') config.include_design = !!checked;
    if (option === 'include_content') config.include_content = !!checked;
  });
  queueRevisionConfigAutosave();
}

function isSectionRevisionVisible(sectionType) {
  const config = ensureSectionConfig(sectionType);
  return !!(config.include_design || config.include_content);
}

const allDesignChecked = computed(() =>
  [getHeaderRevisionOption('include_design'), ...sectionTypes.value.map((sectionType) =>
    getSectionRevisionOption(sectionType, 'include_design')
  )].every(Boolean)
);

const allContentChecked = computed(() =>
  [getHeaderRevisionOption('include_content'), ...sectionTypes.value.map((sectionType) =>
    getSectionRevisionOption(sectionType, 'include_content')
  )].every(Boolean)
);

const designIndeterminate = computed(() => {
  const values = [
    getHeaderRevisionOption('include_design'),
    ...sectionTypes.value.map((sectionType) => getSectionRevisionOption(sectionType, 'include_design')),
  ];
  const selected = values.filter(Boolean).length;
  return selected > 0 && selected < values.length;
});

const contentIndeterminate = computed(() => {
  const values = [
    getHeaderRevisionOption('include_content'),
    ...sectionTypes.value.map((sectionType) => getSectionRevisionOption(sectionType, 'include_content')),
  ];
  const selected = values.filter(Boolean).length;
  return selected > 0 && selected < values.length;
});

function markRevisionConfigDirty() {
  revisionConfigDirty.value = true;
  setRevisionConfigStatus(null);
}

const revisionConfigToastTone = computed(() => {
  if (revisionConfigSaving.value) return "saving";
  if (revisionConfigStatus.value?.type === "success") return "saved";
  if (revisionConfigStatus.value?.type === "error") return "error";
  return "idle";
});

const revisionConfigToastMessage = computed(() => {
  if (revisionConfigSaving.value) return "Saving revision settings...";
  if (revisionConfigStatus.value?.type === "success") {
    return revisionConfigStatus.value.message || "Revision settings saved.";
  }
  if (revisionConfigStatus.value?.type === "error") {
    return revisionConfigStatus.value.message || "Failed to save revision settings.";
  }
  return "";
});

function clearRevisionConfigStatusTimer() {
  if (revisionConfigStatusTimer) {
    clearTimeout(revisionConfigStatusTimer);
    revisionConfigStatusTimer = null;
  }
}

function setRevisionConfigStatus(status) {
  clearRevisionConfigStatusTimer();
  revisionConfigStatus.value = status;
  if (status?.type === "success" || status?.type === "error") {
    revisionConfigStatusTimer = setTimeout(() => {
      revisionConfigStatus.value = null;
      revisionConfigStatusTimer = null;
    }, 3000);
  }
}

function queueRevisionConfigAutosave() {
  markRevisionConfigDirty();
  if (revisionAutosaveTimer) {
    clearTimeout(revisionAutosaveTimer);
  }
  revisionAutosaveTimer = setTimeout(() => {
    saveRevisionConfig();
  }, REVISION_AUTOSAVE_DELAY_MS);
}

function formatSectionType(sectionType) {
  return sectionType
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function mergeSectionTypesWithConfig() {
  const configuredTypes = Object.keys(revisionConfig.value.section_types || {});
  sectionTypes.value = Array.from(new Set([...sectionTypes.value, ...configuredTypes])).sort();
}

async function loadRevisionConfig() {
  revisionConfigLoading.value = true;
  setRevisionConfigStatus(null);
  try {
    const [configRes, typesRes] = await Promise.all([
      authFetch(`${API_BASE}/backup/revisions/config`),
      authFetch(`${API_BASE}/sections/types`),
    ]);

    if (configRes.ok) {
      const data = await configRes.json();
      const normalizedSectionTypes = {};
      for (const [sectionType, options] of Object.entries(data.section_types || {})) {
        normalizedSectionTypes[sectionType] = normalizeSectionTypeOptions(options);
      }
      revisionConfig.value = {
        show_global_design_revisions: data.show_global_design_revisions !== false,
        header: normalizeHeaderOptions(data.header),
        section_types: normalizedSectionTypes,
      };
    }

    if (typesRes.ok) {
      const typesData = await typesRes.json();
      sectionTypes.value = (typesData.types || []).map((typeInfo) => typeInfo.type).sort();
    }

    mergeSectionTypesWithConfig();
    sectionTypes.value.forEach((sectionType) => ensureSectionConfig(sectionType));
    ensureHeaderConfig();
    revisionConfigDirty.value = false;
  } catch (err) {
    console.error('Failed to load revision config:', err);
    setRevisionConfigStatus({
      type: 'error',
      message: 'Failed to load revision settings.',
    });
  } finally {
    revisionConfigLoading.value = false;
  }
}

async function saveRevisionConfig() {
  if (!revisionConfigDirty.value) return;
  if (revisionConfigSaving.value) {
    revisionAutosaveQueued = true;
    return;
  }

  revisionConfigSaving.value = true;
  setRevisionConfigStatus(null);
  revisionAutosaveQueued = false;
  let saveFailed = false;

  try {
    const sectionTypeMap = {};
    for (const sectionType of sectionTypes.value) {
      sectionTypeMap[sectionType] = normalizeSectionTypeOptions(
        revisionConfig.value.section_types?.[sectionType]
      );
    }
    revisionConfigDirty.value = false;

    const response = await authFetch(`${API_BASE}/backup/revisions/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        show_global_design_revisions: !!revisionConfig.value.show_global_design_revisions,
        header: normalizeHeaderOptions(revisionConfig.value.header),
        section_types: sectionTypeMap,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to save revision settings');
    }

    const result = await response.json();
    const normalizedSectionTypes = {};
    for (const [sectionType, options] of Object.entries(result.section_types || {})) {
      normalizedSectionTypes[sectionType] = normalizeSectionTypeOptions(options);
    }
    if (!revisionConfigDirty.value) {
      revisionConfig.value = {
        show_global_design_revisions: result.show_global_design_revisions !== false,
        header: normalizeHeaderOptions(result.header),
        section_types: normalizedSectionTypes,
      };
      mergeSectionTypesWithConfig();
      sectionTypes.value.forEach((sectionType) => ensureSectionConfig(sectionType));
      ensureHeaderConfig();
      setRevisionConfigStatus({
        type: 'success',
        message: 'Revision settings saved.',
      });
    }
  } catch (err) {
    saveFailed = true;
    revisionConfigDirty.value = true;
    setRevisionConfigStatus({
      type: 'error',
      message: 'Failed to save revision settings: ' + err.message,
    });
  } finally {
    revisionConfigSaving.value = false;
    if (revisionAutosaveQueued || (!saveFailed && revisionConfigDirty.value)) {
      queueRevisionConfigAutosave();
    }
  }
}

async function clearAllRevisionHistory() {
  if (clearingRevisionHistory.value) return;
  const confirmed = confirm(
    'Delete all revision history now? This removes undo/redo history for sections, headers, design settings, and the DevOps changelog.'
  );
  if (!confirmed) return;

  clearingRevisionHistory.value = true;
  clearRevisionStatus.value = null;
  try {
    const response = await authFetch(`${API_BASE}/backup/revisions/clear`, {
      method: 'POST',
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(result?.detail || 'Failed to delete revision history');
    }

    clearRevisionStatus.value = {
      type: 'success',
      message: `Deleted ${result.revisions_deleted || 0} revisions and ${result.changelog_deleted || 0} changelog entries. Reset pointers: sections ${result.sections_reset || 0}, headers ${result.headers_reset || 0}, design ${result.design_config_reset ?? result.design_settings_reset ?? 0}.`,
    };
  } catch (err) {
    clearRevisionStatus.value = {
      type: 'error',
      message: `Failed to delete revision history: ${err.message}`,
    };
  } finally {
    clearingRevisionHistory.value = false;
  }
}

async function resetAllStoredData() {
  if (resettingAllData.value || !resetAllConfirmChecked.value) return;

  const selectedCollectionsToDelete = normalizedResetDeleteCollections.value;
  if (!selectedCollectionsToDelete.length) {
    resetAllStatus.value = {
      type: 'error',
      message: 'Select at least one collection to delete.',
    };
    return;
  }

  const deleteBucketData = resetBucketCleanupAvailable.value && resetDeleteBucketData.value;
  const collectionsLine = `\n\nCollections to delete (${selectedCollectionsToDelete.length}): ${selectedCollectionsToDelete.join(', ')}`;
  const selectedBucketPrefixes = normalizedResetBucketPrefixes.value;
  if (deleteBucketData && !selectedBucketPrefixes.length) {
    resetAllStatus.value = {
      type: 'error',
      message: 'Select at least one top-level S3 directory to delete.',
    };
    return;
  }
  const bucketLine = deleteBucketData
    ? `\n\nBucket cleanup (${selectedBucketPrefixes.length} top-level directories): ${selectedBucketPrefixes.join(', ')}`
    : '';

  const confirmed = confirm(
    'Delete selected stored data now?\n\nThis cannot be undone. The app will only keep freshly initialized baseline collections/data afterward.'
      + collectionsLine
      + bucketLine
  );
  if (!confirmed) return;

  const typed = window.prompt('Type RESET to confirm:');
  if (typed !== 'RESET') {
    resetAllStatus.value = {
      type: 'error',
      message: 'Reset cancelled: confirmation text did not match.',
    };
    return;
  }

  resettingAllData.value = true;
  resetAllStatus.value = null;
  try {
    const response = await authFetch(`${API_BASE}/backup/reset/all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        use_delete_collections: true,
        delete_collections: selectedCollectionsToDelete,
        delete_bucket_data: deleteBucketData,
        bucket_include_prefixes: selectedBucketPrefixes,
      }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(result?.detail || 'Failed to reset stored data');
    }

    const initializedCount = Array.isArray(result.initialized_collections)
      ? result.initialized_collections.length
      : 0;
    const deletedCount = Array.isArray(result.deleted_collections)
      ? result.deleted_collections.length
      : selectedCollectionsToDelete.length;
    const preservedCount = Array.isArray(result.excluded_collections)
      ? result.excluded_collections.length
      : Math.max(resetCollectionOptions.value.length - deletedCount, 0);
    const preservedMessage = preservedCount > 0
      ? ` Preserved ${preservedCount} unselected collection(s).`
      : '';
    const bucketCleanup = result?.bucket_cleanup || null;
    const bucketCleanupFailed = deleteBucketData && !bucketCleanup?.performed;
    const bucketMessage = deleteBucketData
      ? (
        bucketCleanup?.performed
          ? ` Deleted ${bucketCleanup.deleted_objects || 0} object(s) from bucket "${bucketCleanup.bucket || resetCurrentBucketName.value}" under ${Array.isArray(bucketCleanup.included_prefixes) ? bucketCleanup.included_prefixes.length : selectedBucketPrefixes.length} selected top-level directory(ies).`
          : ` Bucket cleanup failed: ${bucketCleanup?.error || 'unknown error'}.`
      )
      : '';
    resetAllStatus.value = {
      type: bucketCleanupFailed ? 'error' : 'success',
      message: `Reset complete. Removed ${result.dropped_documents || 0} document(s) across ${result.dropped_collections || 0} collection(s). Reinitialized ${initializedCount} collection(s).${preservedMessage}${bucketMessage}`,
    };
    resetAllConfirmChecked.value = false;
    resetDeleteCollections.value = [];
    resetDeleteBucketData.value = false;
    resetSelectedBucketPrefixes.value = [];
    unusedMediaFindResult.value = null;
    unusedMediaExcludedAssetIds.value = [];
    clearUnusedMediaFindResultFromSession();

    await Promise.all([
      loadBackupInfo(),
      loadRevisionConfig(),
      loadMigrationOptions(),
    ]);
  } catch (err) {
    resetAllStatus.value = {
      type: 'error',
      message: `Failed to reset stored data: ${err.message}`,
    };
  } finally {
    resettingAllData.value = false;
  }
}

function normalizeUnusedMediaAssetForSession(asset) {
  const assetId = String(asset?.asset_id || '').trim();
  if (!assetId) return null;
  return {
    asset_id: assetId,
    filename: String(asset?.filename || '').trim(),
    content_type: String(asset?.content_type || '').trim(),
    url: String(asset?.url || '').trim(),
    key: String(asset?.key || '').trim(),
  };
}

function normalizeUnusedMediaFindResultForSession(result) {
  if (!result || typeof result !== 'object') return null;
  const unusedAssets = Array.isArray(result.unused_assets)
    ? result.unused_assets
      .map((asset) => normalizeUnusedMediaAssetForSession(asset))
      .filter(Boolean)
    : [];

  return {
    ok: result.ok !== false,
    scan_created_at: String(result.scan_created_at || new Date().toISOString()).trim(),
    assets_total: Number(result.assets_total || 0),
    assets_used: Number(result.assets_used || 0),
    assets_unused: unusedAssets.length,
    unused_assets: unusedAssets,
    scanned_collections: Array.isArray(result.scanned_collections)
      ? result.scanned_collections.map((name) => String(name || '').trim()).filter(Boolean)
      : [],
    scanned_documents: Number(result.scanned_documents || 0),
  };
}

function clearUnusedMediaFindResultFromSession() {
  try {
    sessionStorage.removeItem(UNUSED_MEDIA_FIND_RESULT_STORAGE_KEY);
  } catch (err) {
    // Ignore storage errors; the in-memory result is still authoritative.
  }
}

function persistUnusedMediaFindResultToSession(result) {
  const normalized = normalizeUnusedMediaFindResultForSession(result);
  try {
    if (!normalized) {
      sessionStorage.removeItem(UNUSED_MEDIA_FIND_RESULT_STORAGE_KEY);
      return null;
    }
    sessionStorage.setItem(UNUSED_MEDIA_FIND_RESULT_STORAGE_KEY, JSON.stringify(normalized));
  } catch (err) {
    // Ignore storage quota/browser errors; cleanup still works in this tab until reload.
  }
  return normalized;
}

function loadUnusedMediaFindResultFromSession() {
  try {
    const raw = sessionStorage.getItem(UNUSED_MEDIA_FIND_RESULT_STORAGE_KEY);
    if (!raw) return;
    const normalized = normalizeUnusedMediaFindResultForSession(JSON.parse(raw));
    if (!normalized) {
      sessionStorage.removeItem(UNUSED_MEDIA_FIND_RESULT_STORAGE_KEY);
      return;
    }
    unusedMediaFindResult.value = normalized;
    unusedMediaExcludedAssetIds.value = [];
  } catch (err) {
    clearUnusedMediaFindResultFromSession();
  }
}

async function findUnusedMediaFiles() {
  if (findingUnusedMedia.value || removingUnusedMedia.value) return;

  findingUnusedMedia.value = true;
  removeUnusedMediaStatus.value = null;

  try {
    const response = await authFetch(`${API_BASE}/backup/reset/media/find-unused`, {
      method: 'POST',
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(result?.detail || 'Failed to scan unused media files');
    }

    const normalizedResult = persistUnusedMediaFindResultToSession(result) || result;
    unusedMediaFindResult.value = normalizedResult;
    unusedMediaExcludedAssetIds.value = [];

    const totalAssets = Number(normalizedResult.assets_total || 0);
    const unusedAssets = Number(normalizedResult.assets_unused || 0);
    const scannedCollections = Array.isArray(normalizedResult.scanned_collections)
      ? normalizedResult.scanned_collections.length
      : 0;

    removeUnusedMediaStatus.value = {
      type: 'success',
      message: `Detected ${unusedAssets} unreferenced media file(s) out of ${totalAssets} total. Scanned ${scannedCollections} collection(s).`,
    };
  } catch (err) {
    removeUnusedMediaStatus.value = {
      type: 'error',
      message: `Failed to find unused media files: ${err.message}`,
    };
  } finally {
    findingUnusedMedia.value = false;
  }
}

async function cleanupUnusedMediaFiles() {
  if (findingUnusedMedia.value || removingUnusedMedia.value) return;

  const detectedTotalAssets = Number(unusedMediaFindResult.value?.assets_total || 0);
  const detectedAssetIds = unusedMediaDetectedAssets.value
    .map((asset) => String(asset?.asset_id || '').trim())
    .filter(Boolean);
  const detectedUnusedAssets = detectedAssetIds.length;
  const excludedAssetIds = [...normalizedUnusedMediaExcludedAssetIds.value];
  const selectedForCleanupCount = unusedMediaSelectedForCleanupCount.value;

  if (!unusedMediaFindResult.value || detectedAssetIds.length <= 0) {
    removeUnusedMediaStatus.value = {
      type: 'error',
      message: 'Cleanup blocked: run "Find Unused Media Files" first in this browser session.',
    };
    return;
  }

  if (selectedForCleanupCount <= 0) {
    removeUnusedMediaStatus.value = {
      type: 'success',
      message: `Detected ${detectedUnusedAssets} unreferenced media files out of ${detectedTotalAssets} total, but all are excluded from cleanup.`,
    };
    return;
  }

  const confirmed = confirm(
    `Detected ${detectedUnusedAssets} unreferenced media file(s) out of ${detectedTotalAssets} total.\nExcluded: ${excludedAssetIds.length} file(s).\nWill be deleted: ${selectedForCleanupCount} file(s).\n\nDelete selected unused media files now?\n\nThis deletes assets from the media library and storage.`
  );
  if (!confirmed) {
    removeUnusedMediaStatus.value = {
      type: 'success',
      message: `Detected ${detectedUnusedAssets} unreferenced media file(s) out of ${detectedTotalAssets} total. No files were deleted.`,
    };
    return;
  }

  const typed = window.prompt('Type DELETE to confirm:');
  if (typed !== 'DELETE') {
    removeUnusedMediaStatus.value = {
      type: 'error',
      message: `Cleanup cancelled: confirmation text did not match. Detected ${detectedUnusedAssets} unreferenced file(s) out of ${detectedTotalAssets} total.`,
    };
    return;
  }

  removingUnusedMedia.value = true;
  removeUnusedMediaStatus.value = null;

  try {
    const response = await authFetch(`${API_BASE}/backup/reset/media/cleanup-unused`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        asset_ids: detectedAssetIds,
        excluded_asset_ids: excludedAssetIds,
        scan_created_at: unusedMediaFindResult.value?.scan_created_at || null,
      }),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(result?.detail || 'Failed to remove unused media files');
    }

    const deletedAssets = Number(result.deleted_assets || 0);
    const deletedStorageObjects = Number(result.deleted_storage_objects || 0);
    const failedStorageDeletes = Number(result.storage_delete_failures || 0);
    const totalAssets = Number(result.assets_total || detectedTotalAssets);
    const scanCandidates = Number(result.assets_detected_by_scan || detectedUnusedAssets);
    const requestedCleanupCount = Number(result.assets_requested_for_cleanup || selectedForCleanupCount);
    const excludedCount = Number(result.excluded_assets_count || excludedAssetIds.length);
    const scannedCollections = Array.isArray(result.scanned_collections)
      ? result.scanned_collections.length
      : 0;
    const skippedNowUsed = Array.isArray(result.skipped_now_used_assets)
      ? result.skipped_now_used_assets.length
      : 0;
    const baseMessage = deletedAssets > 0
      ? `Removed ${deletedAssets} unused asset(s) and deleted ${deletedStorageObjects} storage object(s).`
      : 'No unused media assets were deleted.';
    const detectionMessage = ` Scan contained ${scanCandidates} candidate file(s) out of ${totalAssets} total; ${requestedCleanupCount} selected for cleanup.`;
    const excludedMessage = excludedCount > 0
      ? ` Excluded ${excludedCount} file(s) by user selection.`
      : '';
    const scanMessage = ` Scanned ${scannedCollections} collection(s).`;
    const skippedMessage = skippedNowUsed > 0
      ? ` Skipped ${skippedNowUsed} file(s) that became referenced after the find step.`
      : '';
    const errorMessage = failedStorageDeletes > 0
      ? ` ${failedStorageDeletes} storage delete operation(s) reported errors.`
      : '';

    removeUnusedMediaStatus.value = {
      type: failedStorageDeletes > 0 ? 'error' : 'success',
      message: `${baseMessage}${detectionMessage}${excludedMessage}${scanMessage}${skippedMessage}${errorMessage}`,
    };

    unusedMediaFindResult.value = null;
    unusedMediaExcludedAssetIds.value = [];
    clearUnusedMediaFindResultFromSession();

    await Promise.all([
      loadBackupInfo(),
      loadMigrationOptions(),
    ]);
  } catch (err) {
    removeUnusedMediaStatus.value = {
      type: 'error',
      message: `Failed to remove unused media files: ${err.message}`,
    };
  } finally {
    removingUnusedMedia.value = false;
  }
}

function isUnusedMediaAssetExcluded(assetId) {
  const normalized = String(assetId || '').trim();
  if (!normalized) return false;
  return normalizedUnusedMediaExcludedAssetIds.value.includes(normalized);
}

function excludeAllUnusedMediaResults() {
  unusedMediaExcludedAssetIds.value = unusedMediaDetectedAssets.value
    .map((asset) => String(asset?.asset_id || '').trim())
    .filter(Boolean);
}

function clearUnusedMediaExclusions() {
  unusedMediaExcludedAssetIds.value = [];
}

function setActiveTab(tab) {
  const target = tabs.find((entry) => entry.id === tab) || tabs[0];
  router.push(target.to);
}

function selectAllResetDeleteCollections() {
  resetDeleteCollections.value = resetCollectionOptions.value.map((coll) => coll.name);
}

function clearResetDeleteCollections() {
  resetDeleteCollections.value = [];
}

function selectResetDeleteGroup(collections) {
  const selected = new Set(resetDeleteCollections.value || []);
  for (const coll of collections || []) {
    const name = String(coll?.name || '').trim();
    if (name) selected.add(name);
  }
  resetDeleteCollections.value = normalizeCollectionSelection(
    Array.from(selected),
    resetCollectionOptions.value,
  );
}

function unselectResetDeleteGroup(collections) {
  const groupNames = new Set(
    (collections || [])
      .map((coll) => String(coll?.name || '').trim())
      .filter(Boolean)
  );
  resetDeleteCollections.value = normalizeCollectionSelection(
    (resetDeleteCollections.value || []).filter((name) => !groupNames.has(name)),
    resetCollectionOptions.value,
  );
}

function selectAllCollectionExports() {
  collectionExportSelections.value = collectionTransferOptions.value.map((coll) => coll.name);
  collectionExportSelectionsInitialized.value = true;
}

function unselectAllCollectionExports() {
  collectionExportSelections.value = [];
  collectionExportSelectionsInitialized.value = true;
}

function selectCollectionExportGroup(collections) {
  const selected = new Set(collectionExportSelections.value || []);
  for (const coll of collections || []) {
    const name = String(coll?.name || '').trim();
    if (name) selected.add(name);
  }
  collectionExportSelections.value = normalizeCollectionSelection(
    Array.from(selected),
    collectionTransferOptions.value,
  );
  collectionExportSelectionsInitialized.value = true;
}

function unselectCollectionExportGroup(collections) {
  const groupNames = new Set(
    (collections || [])
      .map((coll) => String(coll?.name || '').trim())
      .filter(Boolean)
  );
  collectionExportSelections.value = normalizeCollectionSelection(
    (collectionExportSelections.value || []).filter((name) => !groupNames.has(name)),
    collectionTransferOptions.value,
  );
  collectionExportSelectionsInitialized.value = true;
}

function selectAllResetBucketPrefixes() {
  resetSelectedBucketPrefixes.value = [...resetBucketPrefixOptions.value];
}

function clearResetBucketPrefixes() {
  resetSelectedBucketPrefixes.value = [];
}

function cleanupCountLabel(count, noun) {
  const value = Math.max(0, Number(count) || 0);
  return `${value} ${noun}${value === 1 ? '' : 's'}`;
}

function isGeneratedRedirect(item) {
  return String(item?.kind || 'custom') === 'generated';
}

async function loadCleaningCounts() {
  loadingCleaningCounts.value = true;
  cleaningLoadError.value = '';
  try {
    const [headersResult, sectionsResult, redirectsResult] = await Promise.allSettled([
      api.getUnusedHeadersCount(),
      api.getUnusedSectionsCount(),
      api.listSitemapRedirects({ includeExpired: true }),
    ]);

    const errors = [];
    if (headersResult.status === 'fulfilled') {
      unusedHeadersCount.value = Math.max(0, Number(headersResult.value?.count || 0));
    } else {
      unusedHeadersCount.value = 0;
      errors.push(headersResult.reason?.message || 'headers');
    }

    if (sectionsResult.status === 'fulfilled') {
      unusedSectionsCount.value = Math.max(0, Number(sectionsResult.value?.count || 0));
    } else {
      unusedSectionsCount.value = 0;
      errors.push(sectionsResult.reason?.message || 'sections');
    }

    if (redirectsResult.status === 'fulfilled') {
      generatedRedirects.value = Array.isArray(redirectsResult.value)
        ? redirectsResult.value.filter(isGeneratedRedirect)
        : [];
    } else {
      generatedRedirects.value = [];
      errors.push(redirectsResult.reason?.message || 'redirects');
    }

    if (errors.length) {
      cleaningLoadError.value = errors.join('; ');
    }
  } finally {
    loadingCleaningCounts.value = false;
  }
}

async function cleanupUnusedHeaders() {
  if (cleaningUnusedHeaders.value || unusedHeadersCount.value <= 0) return;
  const total = unusedHeadersCount.value;
  const ok = window.confirm(
    `Delete ${cleanupCountLabel(total, 'unused header')}?\n\nThis removes headers that are neither shared nor used on any page. This action cannot be undone.`
  );
  if (!ok) return;

  cleaningUnusedHeaders.value = true;
  cleaningStatus.value = null;
  try {
    const result = await api.deleteUnusedHeaders();
    const deletedCount = Number(result?.deleted_count || 0);
    cleaningStatus.value = {
      type: 'success',
      message: deletedCount > 0
        ? `Deleted ${cleanupCountLabel(deletedCount, 'unused header')}.`
        : 'No unused headers found.',
    };
    await loadCleaningCounts();
  } catch (err) {
    cleaningStatus.value = {
      type: 'error',
      message: `Failed to delete unused headers: ${err?.message || 'Unknown error'}`,
    };
  } finally {
    cleaningUnusedHeaders.value = false;
  }
}

async function cleanupUnusedSections() {
  if (cleaningUnusedSections.value || unusedSectionsCount.value <= 0) return;
  const total = unusedSectionsCount.value;
  const ok = window.confirm(
    `Delete ${cleanupCountLabel(total, 'unused section')}?\n\nThis removes sections that are neither shared nor used on any page. This action cannot be undone.`
  );
  if (!ok) return;

  cleaningUnusedSections.value = true;
  cleaningStatus.value = null;
  try {
    const result = await api.deleteUnusedSections();
    const deletedCount = Number(result?.deleted_count || 0);
    cleaningStatus.value = {
      type: 'success',
      message: deletedCount > 0
        ? `Deleted ${cleanupCountLabel(deletedCount, 'unused section')}.`
        : 'No unused sections found.',
    };
    await loadCleaningCounts();
  } catch (err) {
    cleaningStatus.value = {
      type: 'error',
      message: `Failed to delete unused sections: ${err?.message || 'Unknown error'}`,
    };
  } finally {
    cleaningUnusedSections.value = false;
  }
}

async function cleanupGeneratedRedirects() {
  if (cleaningGeneratedRedirects.value || generatedRedirectsCount.value <= 0) return;
  const redirectItems = generatedRedirects.value.filter((item) => item?.id);
  const total = redirectItems.length;
  if (total <= 0) return;

  const ok = window.confirm(
    `Delete ${cleanupCountLabel(total, 'generated redirect')}?\n\nCustom sitemap redirects are preserved. This action cannot be undone.`
  );
  if (!ok) return;

  cleaningGeneratedRedirects.value = true;
  cleaningStatus.value = null;
  try {
    const results = await Promise.allSettled(
      redirectItems.map((item) => api.deleteSitemapRedirect(item.id))
    );
    const failedCount = results.filter((result) => result.status === 'rejected').length;
    const deletedCount = total - failedCount;
    cleaningStatus.value = {
      type: failedCount > 0 ? 'error' : 'success',
      message: failedCount > 0
        ? `Deleted ${deletedCount} of ${cleanupCountLabel(total, 'generated redirect')}; ${failedCount} failed.`
        : `Deleted ${cleanupCountLabel(deletedCount, 'generated redirect')}.`,
    };
    await loadCleaningCounts();
  } catch (err) {
    cleaningStatus.value = {
      type: 'error',
      message: `Failed to delete generated redirects: ${err?.message || 'Unknown error'}`,
    };
  } finally {
    cleaningGeneratedRedirects.value = false;
  }
}

watch(
  activeTab,
  (tab) => {
    if (tab === 'migration' && !migrationOptions.value) {
      loadMigrationOptions();
    }
    if (tab === 'reset') {
      loadCleaningCounts();
    }
  },
  { immediate: true }
);

function formatCollectionName(name) {
  return name;
}

function normalizeCollectionEntry(coll) {
  return {
    ...coll,
    name: String(coll?.name || '').trim(),
    count: Number(coll?.count) || 0,
    collection_group: String(coll?.collection_group || 'admin_security').trim() || 'admin_security',
    collection_group_label: String(coll?.collection_group_label || 'Admin & Security').trim() || 'Admin & Security',
    collection_group_order: Number(coll?.collection_group_order ?? 50),
    collection_prefix: String(coll?.collection_prefix || coll?.name || 'other').trim() || 'other',
    collection_prefix_label: String(coll?.collection_prefix_label || coll?.collection_prefix || coll?.name || 'Other').trim() || 'Other',
  };
}

function normalizeCollectionEntries(collections) {
  return (Array.isArray(collections) ? collections : [])
    .map((coll) => normalizeCollectionEntry(coll))
    .filter((coll) => coll.name);
}

function sortCollectionEntries(collections, sortMode = 'name') {
  return [...collections].sort((left, right) => {
    if (sortMode === 'items') {
      const countDiff = Number(right.count || 0) - Number(left.count || 0);
      if (countDiff !== 0) return countDiff;
    }
    return formatCollectionName(left.name).localeCompare(
      formatCollectionName(right.name),
      undefined,
      { sensitivity: 'base' },
    );
  });
}

function getCollectionGroupInfo(coll, mode) {
  if (mode === 'prefix') {
    const prefix = String(coll?.collection_prefix || coll?.name || 'other').trim() || 'other';
    return {
      id: prefix,
      label: String(coll?.collection_prefix_label || prefix).trim() || 'Other',
      order: 100,
    };
  }

  const category = String(coll?.collection_group || 'admin_security').trim() || 'admin_security';
  return {
    id: category,
    label: String(coll?.collection_group_label || category).trim() || 'Admin & Security',
    order: Number(coll?.collection_group_order ?? 50),
  };
}

function buildCollectionGroups(collections, { sortMode = 'name' } = {}) {
  const groupingMode = ['none', 'prefix'].includes(collectionGroupingMode.value)
    ? collectionGroupingMode.value
    : 'category';
  if (groupingMode === 'none') {
    const sortedCollections = sortCollectionEntries(collections, sortMode);
    return [
      {
        id: 'none:all',
        label: 'All collections',
        order: 0,
        totalCount: sortedCollections.reduce((sum, coll) => sum + Number(coll.count || 0), 0),
        collections: sortedCollections,
      },
    ];
  }

  const groupsById = new Map();

  for (const coll of collections) {
    const info = getCollectionGroupInfo(coll, groupingMode);
    const groupKey = `${groupingMode}:${info.id}`;
    if (!groupsById.has(groupKey)) {
      groupsById.set(groupKey, {
        id: groupKey,
        label: info.label,
        order: info.order,
        totalCount: 0,
        collections: [],
      });
    }
    const group = groupsById.get(groupKey);
    group.collections.push(coll);
    group.totalCount += Number(coll.count || 0);
  }

  const groups = Array.from(groupsById.values()).map((group) => ({
    ...group,
    collections: sortCollectionEntries(group.collections, sortMode),
  }));

  return groups.sort((left, right) => {
    if (groupingMode === 'category') {
      const orderDiff = Number(left.order || 0) - Number(right.order || 0);
      if (orderDiff !== 0) return orderDiff;
    }
    if (sortMode === 'items' && groupingMode === 'prefix') {
      const countDiff = Number(right.totalCount || 0) - Number(left.totalCount || 0);
      if (countDiff !== 0) return countDiff;
    }
    return left.label.localeCompare(right.label, undefined, { sensitivity: 'base' });
  });
}

const overviewCollections = computed(() => {
  const collections = Array.isArray(collectionOptions.value?.collections)
    ? collectionOptions.value.collections
    : [];
  return sortCollectionEntries(normalizeCollectionEntries(collections), overviewCollectionSort.value);
});

const overviewCollectionGroups = computed(() =>
  buildCollectionGroups(overviewCollections.value, { sortMode: overviewCollectionSort.value })
);

const migrationCollections = computed(() =>
  sortCollectionEntries(normalizeCollectionEntries(migrationOptions.value?.collections || []))
);

const migrationCollectionGroups = computed(() =>
  buildCollectionGroups(migrationCollections.value)
);

const resetCollectionOptions = computed(() => {
  const collections = Array.isArray(collectionOptions.value?.collections)
    ? collectionOptions.value.collections
    : [];
  return normalizeCollectionEntries(collections)
    .filter((coll) => coll.name && !coll.name.startsWith('system.'))
    .sort((a, b) => a.name.localeCompare(b.name));
});

const resetCollectionGroups = computed(() =>
  buildCollectionGroups(resetCollectionOptions.value)
);

const collectionTransferOptions = computed(() => {
  return resetCollectionOptions.value;
});

const collectionTransferGroups = computed(() =>
  buildCollectionGroups(collectionTransferOptions.value)
);

function normalizeCollectionSelection(selection, options) {
  const allowed = new Set(options.map((coll) => coll.name));
  return Array.from(
    new Set(
      (selection || [])
        .map((name) => String(name || '').trim())
        .filter((name) => name && allowed.has(name))
    )
  ).sort((a, b) => a.localeCompare(b));
}

const normalizedCollectionExportSelections = computed(() =>
  normalizeCollectionSelection(collectionExportSelections.value, collectionTransferOptions.value)
);

const isAssetsCollectionSelectedForExport = computed(() =>
  normalizedCollectionExportSelections.value.includes('assets')
);

const canImportCollections = computed(() => {
  if (!collectionImportFile.value) return false;
  if (collectionImportDryRunLoading.value) return false;
  if (collectionImportDryRunError.value) return false;
  return Boolean(collectionImportDryRun.value?.target_collection || collectionImportDryRun.value?.collection);
});

const resetBucketCleanupAvailable = computed(() =>
  Boolean(migrationOptions.value?.bucket?.available)
);

const resetCurrentBucketName = computed(() =>
  String(migrationOptions.value?.bucket?.current_bucket || '').trim() || 'unknown'
);

const resetBucketPrefixOptions = computed(() =>
  Array.from(
    new Set(
      (migrationOptions.value?.bucket?.top_level_prefixes || [])
        .map((prefix) => String(prefix || '').trim())
        .filter(Boolean)
    )
  ).sort((a, b) => a.localeCompare(b))
);

const resetBucketPrefixesError = computed(() =>
  String(migrationOptions.value?.bucket?.prefixes_error || '').trim()
);

const normalizedResetDeleteCollections = computed(() => {
  const allowed = new Set(resetCollectionOptions.value.map((coll) => coll.name));
  return Array.from(
    new Set(
      (resetDeleteCollections.value || [])
        .map((name) => String(name || '').trim())
        .filter((name) => name && allowed.has(name))
    )
  ).sort((a, b) => a.localeCompare(b));
});

const normalizedResetBucketPrefixes = computed(() => {
  const allowed = new Set(resetBucketPrefixOptions.value);
  return Array.from(
    new Set(
      (resetSelectedBucketPrefixes.value || [])
        .map((prefix) => String(prefix || '').trim())
        .filter((prefix) => prefix && allowed.has(prefix))
    )
  ).sort((a, b) => a.localeCompare(b));
});

const unusedMediaDetectedAssets = computed(() => {
  const assets = unusedMediaFindResult.value?.unused_assets;
  return (Array.isArray(assets) ? assets : [])
    .map((asset) => normalizeUnusedMediaAssetForSession(asset))
    .filter(Boolean);
});

const normalizedUnusedMediaExcludedAssetIds = computed(() => {
  const detectedIds = new Set(
    unusedMediaDetectedAssets.value
      .map((asset) => String(asset?.asset_id || '').trim())
      .filter(Boolean)
  );
  return Array.from(
    new Set(
      (unusedMediaExcludedAssetIds.value || [])
        .map((assetId) => String(assetId || '').trim())
        .filter((assetId) => assetId && detectedIds.has(assetId))
    )
  ).sort((a, b) => a.localeCompare(b));
});

const unusedMediaSelectedForCleanupCount = computed(() => {
  return Math.max(
    unusedMediaDetectedAssets.value.length - normalizedUnusedMediaExcludedAssetIds.value.length,
    0,
  );
});

const canCleanupUnusedMedia = computed(() => {
  return unusedMediaDetectedAssets.value.length > 0 && unusedMediaSelectedForCleanupCount.value > 0;
});

watch(resetCollectionOptions, (options) => {
  const allowed = new Set(options.map((coll) => coll.name));
  resetDeleteCollections.value = (resetDeleteCollections.value || []).filter((name) => allowed.has(name));
});

watch(collectionTransferOptions, (options) => {
  const allowed = new Set(options.map((coll) => coll.name));
  collectionExportSelections.value = (collectionExportSelections.value || [])
    .filter((name) => allowed.has(name));
  if (collectionImportTarget.value && !allowed.has(collectionImportTarget.value)) {
    collectionImportTarget.value = '';
  }

  if (!collectionExportSelectionsInitialized.value && options.length) {
    collectionExportSelections.value = [];
    collectionExportSelectionsInitialized.value = true;
  }
});

watch(isAssetsCollectionSelectedForExport, (selected) => {
  if (!selected) {
    collectionIncludeMedia.value = false;
  }
});

watch([collectionImportFile, collectionImportTarget], () => {
  runCollectionImportDryRun();
});

watch(unusedMediaDetectedAssets, () => {
  unusedMediaExcludedAssetIds.value = [...normalizedUnusedMediaExcludedAssetIds.value];
});

watch(resetBucketCleanupAvailable, (available) => {
  if (!available) {
    resetDeleteBucketData.value = false;
    resetSelectedBucketPrefixes.value = [];
  }
});

watch(resetBucketPrefixOptions, (prefixes) => {
  const allowed = new Set(prefixes);
  resetSelectedBucketPrefixes.value = (resetSelectedBucketPrefixes.value || [])
    .filter((prefix) => allowed.has(prefix));
});

watch(resetDeleteBucketData, (enabled) => {
  if (!enabled) {
    resetSelectedBucketPrefixes.value = [];
    return;
  }
  if (resetSelectedBucketPrefixes.value.length === 0 && resetBucketPrefixOptions.value.length > 0) {
    resetSelectedBucketPrefixes.value = [...resetBucketPrefixOptions.value];
  }
});

const migrationSelectionSummary = computed(() => {
  const summary = { copy: 0, empty: 0, skip: 0 };
  for (const coll of migrationCollections.value) {
    const mode = migrationSelections.value[coll.name] || coll.default_mode || 'copy';
    if (mode === 'empty') summary.empty += 1;
    else if (mode === 'skip') summary.skip += 1;
    else summary.copy += 1;
  }
  return summary;
});

function setMigrationGroupMode(collections, mode) {
  if (!['copy', 'empty', 'skip'].includes(mode)) return;
  const nextSelections = { ...migrationSelections.value };
  for (const coll of collections || []) {
    const name = String(coll?.name || '').trim();
    if (name) nextSelections[name] = mode;
  }
  migrationSelections.value = nextSelections;
}

function initializeMigrationSelections(optionsData) {
  const nextSelections = {};
  for (const coll of optionsData.collections || []) {
    nextSelections[coll.name] = coll.default_mode || 'copy';
  }
  migrationSelections.value = nextSelections;
}

async function loadMigrationOptions() {
  migrationLoading.value = true;
  migrationStatus.value = null;
  try {
    const response = await authFetch(`${API_BASE}/backup/migration/options`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to load migration options');
    }

    migrationOptions.value = data;
    migrationTargetDb.value = data.suggested_target_db || '';
    migrationBucketMode.value = 'none';
    migrationTargetBucket.value = data.bucket?.suggested_target_bucket || '';
    initializeMigrationSelections(data);
  } catch (err) {
    migrationStatus.value = {
      type: 'error',
      message: 'Failed to load migration options: ' + err.message,
    };
  } finally {
    migrationLoading.value = false;
  }
}

async function runMigration() {
  if (!migrationTargetDb.value) return;
  if (migrationBucketMode.value !== 'none' && !migrationTargetBucket.value.trim()) {
    migrationStatus.value = {
      type: 'error',
      message: 'Please provide a target bucket name.',
    };
    return;
  }

  if (!confirm(`Create new database "${migrationTargetDb.value}" from "${migrationOptions.value?.source_db}"?`)) {
    return;
  }

  migrationSubmitting.value = true;
  migrationStatus.value = null;
  try {
    const response = await authFetch(`${API_BASE}/backup/migration/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_db: migrationTargetDb.value.trim(),
        collections: migrationSelections.value,
        bucket_mode: migrationBucketMode.value,
        target_bucket: migrationBucketMode.value === 'none'
          ? null
          : migrationTargetBucket.value.trim(),
      }),
    });

    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(result.detail || 'Migration failed');
    }

    const bucketMessage = result.bucket?.performed
      ? ` Bucket: ${result.bucket.mode} -> ${result.bucket.target_bucket}.`
      : '';
    migrationStatus.value = {
      type: 'success',
      message: `Migration created DB ${result.target_db}. Copied ${result.summary?.copied_collections || 0} collections and ${result.summary?.copied_documents || 0} documents.${bucketMessage}`,
    };
    await loadMigrationOptions();
  } catch (err) {
    migrationStatus.value = {
      type: 'error',
      message: 'Migration failed: ' + err.message,
    };
  } finally {
    migrationSubmitting.value = false;
  }
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

function getDownloadFilename(response, fallback) {
  const contentDisposition = response.headers.get('content-disposition');
  if (!contentDisposition) return fallback;
  const match = contentDisposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';\n]+)["']?/i);
  return match ? decodeURIComponent(match[1].trim()) : fallback;
}

async function downloadResponseBlob(response, fallbackFilename) {
  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = downloadUrl;
  a.download = getDownloadFilename(response, fallbackFilename);
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(downloadUrl);
}

function isCollectionJsonFile(file) {
  if (!file) return false;
  const name = String(file.name || '').toLowerCase();
  return name.endsWith('.json') || file.type === 'application/json';
}

function isCollectionZipFile(file) {
  if (!file) return false;
  return String(file.name || '').toLowerCase().endsWith('.zip');
}

function isSupportedCollectionImportFile(file) {
  return isCollectionZipFile(file) || isCollectionJsonFile(file);
}

function formatCollectionImportFileKind(file) {
  if (isCollectionZipFile(file)) return 'ZIP archive';
  if (isCollectionJsonFile(file)) return 'Raw JSON';
  return 'Unsupported file';
}

function formatDateTime(isoStr) {
  return formatInstantInServerTimezone(isoStr, {}, { fallback: 'Never' });
}

function dateToISOString(date) {
  if (!date) return null;
  const d = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return null;
  const pad = n => String(n).padStart(2, '0');
  const wallValue = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return serverWallDateTimeToInstantDate(wallValue)?.toISOString() || null;
}

function useLastBackupTime() {
  if (lastBackupInfo.value?.suggested_incremental_since) {
    incrementalSince.value = serverWallDateTimeToLocalDate(
      formatDateTimeLocalForServerTimezone(lastBackupInfo.value.suggested_incremental_since)
    );
  }
}

async function loadBackupInfo() {
  loading.value = true;
  try {
    const [collectionOptionsResult, infoResult, lastResult, counterResult] = await Promise.allSettled([
      authFetch(`${API_BASE}/backup/collections/options`).then((response) =>
        readBackupJsonResponse(response, 'Failed to load collection options')
      ),
      authFetch(`${API_BASE}/backup/info`).then((response) =>
        readBackupJsonResponse(response, 'Failed to load backup information')
      ),
      authFetch(`${API_BASE}/backup/last-backup`).then((response) =>
        readBackupJsonResponse(response, 'Failed to load backup history')
      ),
      authFetch(`${API_BASE}/backup/incremental-counter`).then((response) =>
        readBackupJsonResponse(response, 'Failed to load incremental counter')
      ),
    ]);

    if (collectionOptionsResult.status === 'fulfilled') {
      collectionOptions.value = collectionOptionsResult.value;
    } else {
      console.error('Failed to load collection options:', collectionOptionsResult.reason);
    }

    if (infoResult.status === 'fulfilled') {
      backupInfo.value = infoResult.value;
    } else {
      console.error('Failed to load backup information:', infoResult.reason);
    }

    if (lastResult.status === 'fulfilled') {
      lastBackupInfo.value = lastResult.value;
      if (lastBackupInfo.value?.suggested_incremental_since) {
        incrementalSince.value = serverWallDateTimeToLocalDate(
          formatDateTimeLocalForServerTimezone(lastBackupInfo.value.suggested_incremental_since)
        );
      }
    } else {
      console.error('Failed to load backup history:', lastResult.reason);
    }

    if (counterResult.status === 'fulfilled') {
      const data = counterResult.value;
      incrementalCounter.value = data.counter;
    } else {
      console.error('Failed to load incremental counter:', counterResult.reason);
    }
  } catch (err) {
    console.error('Failed to load backup info:', err);
  } finally {
    loading.value = false;
  }
}

async function resetIncrementalCounter() {
  if (!confirm('Are you sure you want to reset incremental backups?\n\nThis will reset the counter to #0001 and clear the backup history. The next incremental backup will include all data.')) {
    return;
  }
  
  resettingCounter.value = true;
  try {
    const response = await authFetch(`${API_BASE}/backup/reset-incremental-counter`, {
      method: 'POST',
    });
    
    if (response.ok) {
      incrementalCounter.value = 0;
      incrementalSince.value = null;
      incrementalInfo.value = null;
      if (lastBackupInfo.value) {
        lastBackupInfo.value.suggested_incremental_since = null;
        lastBackupInfo.value.last_export = null;
      }
      exportStatus.value = {
        type: 'success',
        message: 'Incremental backup counter and history have been reset.',
      };
    } else {
      throw new Error('Failed to reset');
    }
  } catch (err) {
    exportStatus.value = {
      type: 'error',
      message: 'Failed to reset: ' + err.message,
    };
  } finally {
    resettingCounter.value = false;
  }
}

async function loadIncrementalInfo() {
  if (!incrementalSince.value) {
    incrementalInfo.value = null;
    return;
  }
  
  try {
    const since = dateToISOString(incrementalSince.value);
    if (!since) return;
    const response = await authFetch(`${API_BASE}/backup/info?since=${encodeURIComponent(since)}`);
    incrementalInfo.value = await readBackupJsonResponse(response, 'Failed to load incremental backup preview');
  } catch (err) {
    console.error('Failed to load incremental info:', err);
  }
}

watch(incrementalSince, loadIncrementalInfo);
watch(backupType, (newType) => {
  if (newType === 'incremental') {
    loadIncrementalInfo();
  } else {
    incrementalInfo.value = null;
  }
});

async function exportBackup() {
  exporting.value = true;
  exportStatus.value = null;
  
  try {
    let url;
    if (backupType.value === 'incremental' && incrementalSince.value) {
      const since = dateToISOString(incrementalSince.value);
      if (!since) throw new Error('Invalid incremental backup date.');
      url = `${API_BASE}/backup/export/incremental?since=${encodeURIComponent(since)}&include_media=${includeMedia.value}`;
    } else {
      url = `${API_BASE}/backup/export?include_media=${includeMedia.value}`;
    }
    
    const response = await authFetch(url);
    
    if (!response.ok) {
      throw new Error('Export failed');
    }
    
    const blob = await response.blob();
    const contentDisposition = response.headers.get('content-disposition');
    let filename = 'backup.zip';
    if (contentDisposition) {
      // Handle both quoted and unquoted filenames
      const match = contentDisposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';\n]+)["']?/i);
      if (match) filename = decodeURIComponent(match[1].trim());
    }
    
    const downloadUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(downloadUrl);
    
    // Log the export for future incremental backups
    await authFetch(`${API_BASE}/backup/log-export?backup_type=${backupType.value}`, {
      method: 'POST',
    });
    
    exportStatus.value = {
      type: 'success',
      message: `${backupType.value === 'incremental' ? 'Incremental' : 'Full'} backup downloaded successfully!`,
    };
    
    // Reload backup info to update last backup time
    await loadBackupInfo();
  } catch (err) {
    exportStatus.value = {
      type: 'error',
      message: 'Failed to export backup: ' + err.message,
    };
  } finally {
    exporting.value = false;
  }
}

async function exportCollections() {
  if (!normalizedCollectionExportSelections.value.length) {
    collectionExportStatus.value = {
      type: 'error',
      message: 'Select at least one collection to export.',
    };
    return;
  }

  collectionExporting.value = true;
  collectionExportStatus.value = null;

  try {
    const params = new URLSearchParams();
    normalizedCollectionExportSelections.value.forEach((name) => {
      params.append('collections', name);
    });
    params.set('include_media', String(collectionIncludeMedia.value && isAssetsCollectionSelectedForExport.value));

    const response = await authFetch(`${API_BASE}/backup/collections/export?${params.toString()}`);
    if (!response.ok) {
      await readBackupJsonResponse(response, 'Failed to export collections');
      throw new Error('Failed to export collections');
    }

    await downloadResponseBlob(response, 'collections.zip');
    collectionExportStatus.value = {
      type: 'success',
      message: `Exported ${normalizedCollectionExportSelections.value.length} collection${normalizedCollectionExportSelections.value.length === 1 ? '' : 's'}.`,
    };
  } catch (err) {
    collectionExportStatus.value = {
      type: 'error',
      message: 'Failed to export collections: ' + err.message,
    };
  } finally {
    collectionExporting.value = false;
  }
}

function resetCollectionImportDryRun() {
  collectionImportDryRunToken += 1;
  collectionImportDryRun.value = null;
  collectionImportDryRunError.value = '';
  collectionImportDryRunLoading.value = false;
}

async function runCollectionImportDryRun() {
  const file = collectionImportFile.value;
  const token = ++collectionImportDryRunToken;
  collectionImportDryRun.value = null;
  collectionImportDryRunError.value = '';

  if (!file) {
    collectionImportDryRunLoading.value = false;
    return;
  }
  if (!isSupportedCollectionImportFile(file)) {
    collectionImportDryRunError.value = 'Select a ZIP archive or JSON file.';
    collectionImportDryRunLoading.value = false;
    return;
  }

  collectionImportDryRunLoading.value = true;
  try {
    const params = new URLSearchParams();
    if (collectionImportTarget.value) {
      params.set('target_collection', collectionImportTarget.value);
    }

    const formData = new FormData();
    formData.append('file', file);

    const response = await authFetch(`${API_BASE}/backup/collections/import/dry-run?${params.toString()}`, {
      method: 'POST',
      body: formData,
    });
    const result = await readBackupJsonResponse(response, 'Collection import dry-run failed');
    if (token !== collectionImportDryRunToken) return;
    collectionImportDryRun.value = result;
    collectionImportStatus.value = null;
  } catch (err) {
    if (token !== collectionImportDryRunToken) return;
    collectionImportDryRunError.value = err.message;
  } finally {
    if (token === collectionImportDryRunToken) {
      collectionImportDryRunLoading.value = false;
    }
  }
}

function setCollectionImportFile(file) {
  collectionImportStatus.value = null;
  resetCollectionImportDryRun();
  if (!file) return;
  if (!isSupportedCollectionImportFile(file)) {
    collectionImportStatus.value = {
      type: 'error',
      message: 'Select a ZIP archive or JSON file.',
    };
    return;
  }
  collectionImportFile.value = file;
}

function handleCollectionImportFileSelect(event) {
  const file = event.target?.files?.[0] || null;
  setCollectionImportFile(file);
}

function handleCollectionImportDrop(event) {
  collectionImportDragOver.value = false;
  const file = event.dataTransfer?.files?.[0] || null;
  setCollectionImportFile(file);
}

function clearCollectionImportFile({ keepStatus = false } = {}) {
  collectionImportFile.value = null;
  resetCollectionImportDryRun();
  if (!keepStatus) {
    collectionImportStatus.value = null;
  }
  if (collectionImportFileInput.value) {
    collectionImportFileInput.value.value = '';
  }
}

async function importCollections() {
  if (!collectionImportFile.value) return;
  const resolvedTarget = String(
    collectionImportDryRun.value?.target_collection ||
    collectionImportDryRun.value?.collection ||
    ''
  ).trim();
  if (!resolvedTarget || collectionImportDryRunError.value) {
    collectionImportStatus.value = {
      type: 'error',
      message: 'Run a successful collection import dry-run first.',
    };
    return;
  }

  if (
    collectionImportMode.value === 'replace'
    && !confirm('Replace selected/imported collections? This clears each imported target collection before inserting documents.')
  ) {
    return;
  }

  collectionImporting.value = true;
  collectionImportStatus.value = null;

  try {
    const params = new URLSearchParams();
    params.set('mode', collectionImportMode.value);
    params.set('target_collection', resolvedTarget);

    const formData = new FormData();
    formData.append('file', collectionImportFile.value);

    const response = await authFetch(`${API_BASE}/backup/collections/import?${params.toString()}`, {
      method: 'POST',
      body: formData,
    });
    const result = await readBackupImportResponse(response);

    collectionImportStatus.value = {
      type: 'success',
      message: 'Collection import completed successfully!',
      details: result,
    };
    unusedMediaFindResult.value = null;
    unusedMediaExcludedAssetIds.value = [];
    clearUnusedMediaFindResultFromSession();
    clearCollectionImportFile({ keepStatus: true });
    await Promise.all([
      loadBackupInfo(),
      loadMigrationOptions(),
    ]);
  } catch (err) {
    collectionImportStatus.value = {
      type: 'error',
      message: 'Failed to import collections: ' + err.message,
    };
  } finally {
    collectionImporting.value = false;
  }
}

function handleFileSelect(event) {
  const files = Array.from(event.target.files || []).filter((file) => file.name.endsWith('.zip'));
  if (!files.length) return;
  selectedFiles.value = files;
  importStatus.value = null;
}

function handleDrop(event) {
  dragOver.value = false;
  const files = Array.from(event.dataTransfer?.files || []).filter((file) => file.name.endsWith('.zip'));
  if (!files.length) return;
  selectedFiles.value = files;
  importStatus.value = null;
}

function clearFiles() {
  selectedFiles.value = [];
  importStatus.value = null;
  if (fileInput.value) {
    fileInput.value.value = '';
  }
}

function removeSelectedFile(index) {
  selectedFiles.value.splice(index, 1);
  importStatus.value = null;
  if (!selectedFiles.value.length && fileInput.value) {
    fileInput.value.value = '';
  }
}

async function importBackup() {
  if (!selectedFiles.value.length) return;
  
  if (!confirm(`Are you sure you want to import ${selectedFiles.value.length} backup file${selectedFiles.value.length === 1 ? '' : 's'}? This will replace all existing data and cannot be undone.`)) {
    return;
  }
  
  importing.value = true;
  importStatus.value = null;
  
  try {
    const formData = new FormData();
    selectedFiles.value.forEach((backupFile) => {
      formData.append('files', backupFile);
    });
    
    const response = await authFetch(`${API_BASE}/backup/import?replace_existing=${replaceExisting.value}`, {
      method: 'POST',
      body: formData,
    });
    const result = await readBackupImportResponse(response);
    
    importStatus.value = {
      type: 'success',
      message: 'Import completed successfully!',
      details: result,
    };
    unusedMediaFindResult.value = null;
    unusedMediaExcludedAssetIds.value = [];
    clearUnusedMediaFindResultFromSession();
    
    await loadBackupInfo();
    
  } catch (err) {
    importStatus.value = {
      type: 'error',
      message: 'Failed to import backup: ' + err.message,
    };
  } finally {
    importing.value = false;
  }
}

onMounted(() => {
  loadUnusedMediaFindResultFromSession();
  loadBackupInfo();
  loadRevisionConfig();
  loadMigrationOptions();
});

onUnmounted(() => {
  clearRevisionConfigStatusTimer();
  if (revisionAutosaveTimer) {
    clearTimeout(revisionAutosaveTimer);
    revisionAutosaveTimer = null;
  }
});
</script>

<style scoped>
.loading-state {
  padding: 40px;
  text-align: center;
  color: #64748b;
}

.card-hint {
  font-size: 13px;
  color: #94a3b8;
  margin: 4px 0 0;
}

.revision-table-wrap {
  overflow-x: auto;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.revision-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 520px;
}

.revision-table th,
.revision-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
  font-size: 13px;
  color: #334155;
}

.revision-table th {
  background: #f8fafc;
  font-weight: 700;
  color: #0f172a;
}

.th-with-toggle {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
}

.th-with-toggle input {
  width: 14px;
  height: 14px;
  accent-color: #4f46e5;
}

.revision-table tbody tr:last-child td {
  border-bottom: none;
}

.section-type-cell {
  font-weight: 600;
  color: #0f172a;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.status-badge.shown {
  background: #dcfce7;
  color: #166534;
}

.status-badge.hidden {
  background: #f1f5f9;
  color: #475569;
}

/* Info Grid */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
}

.info-section h3 {
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 12px;
}

.info-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.info-section-heading h3 {
  margin-bottom: 0;
}

.collection-list-controls,
.collection-group-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.collection-group-toolbar {
  justify-content: space-between;
  margin-bottom: 12px;
}

.collection-group-toolbar .reset-selection-actions {
  margin-bottom: 0;
}

.overview-sort {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.overview-sort select {
  min-width: 88px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  padding: 5px 8px;
}

.collection-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.collection-group-list {
  display: grid;
  gap: 16px;
}

.collection-group {
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 12px;
}

.collection-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.collection-group-title {
  display: block;
  font-size: 12px;
  font-weight: 800;
  color: #0f172a;
  text-transform: uppercase;
  letter-spacing: 0;
}

.collection-group-meta {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: #64748b;
}

.collection-group-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.collection-group-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.reset-selection-list.collection-group-items {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin-top: 0;
}

.collection-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 6px;
}

.collection-name {
  font-size: 13px;
  font-weight: 500;
  color: #334155;
}

.collection-count {
  font-size: 12px;
  color: #64748b;
}

.info-total {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.media-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.media-stat {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 6px;
}

.stat-label {
  font-size: 13px;
  color: #64748b;
}

.stat-value {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

/* Backup History */
.backup-history {
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 16px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.history-label {
  color: #64748b;
}

.history-value {
  font-weight: 500;
  color: #334155;
}

.history-type {
  padding: 2px 8px;
  background: #e0e7ff;
  color: #4338ca;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.history-none {
  color: #94a3b8;
  font-style: italic;
}

/* Backup Type Selector */
.backup-type-selector {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}

.radio-option {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
}

.radio-option:hover {
  border-color: #c7d2fe;
  background: #f8fafc;
}

.radio-option.selected {
  border-color: #4f46e5;
  background: #f5f3ff;
}

.radio-option input {
  margin-top: 2px;
  accent-color: #4f46e5;
}

.radio-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.radio-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.radio-desc {
  font-size: 12px;
  color: #64748b;
}

/* Incremental Options */
.incremental-options {
  padding: 16px;
  background: #f5f3ff;
  border: 1px solid #e0e7ff;
  border-radius: 8px;
  margin-bottom: 16px;
}

.incremental-since {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.incremental-since label {
  font-size: 13px;
  font-weight: 500;
  color: #334155;
}

.datetime-picker {
  flex: 1;
  min-width: 200px;
}

.datetime-picker :deep(.dp__input) {
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 13px;
  color: #334155;
}

.datetime-picker :deep(.dp__input:focus) {
  border-color: #4f46e5;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.incremental-preview {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e0e7ff;
}

.incremental-preview h4 {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin: 0 0 8px;
}

.preview-stats {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #4338ca;
}

.counter-info {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e0e7ff;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.counter-label {
  color: #64748b;
}

.counter-value {
  font-weight: 600;
  color: #334155;
  font-family: 'SF Mono', Monaco, Consolas, monospace;
}

/* Export Options */
.export-options,
.import-options {
  margin-bottom: 16px;
}

.import-format-hint {
  margin-bottom: 16px;
  padding: 10px 12px;
  border: 1px solid #dbeafe;
  background: #f8fbff;
  border-radius: 8px;
  font-size: 12px;
  color: #334155;
  line-height: 1.45;
}

.import-format-hint code {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  background: #eef2ff;
  color: #3730a3;
  padding: 1px 4px;
  border-radius: 4px;
}

.checkbox-option {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #334155;
}

.checkbox-option input {
  width: 16px;
  height: 16px;
  accent-color: #4f46e5;
}

.reset-selection {
  margin-bottom: 16px;
}

.card-header--compact {
  margin-bottom: 8px;
}

.card-header--compact h3 {
  margin: 0;
  font-size: 15px;
  color: #0f172a;
}

.reset-selection-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.reset-selection-actions--bucket {
  margin-top: 8px;
}

.reset-selection-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 6px 12px;
}

.reset-selection-option {
  align-items: flex-start;
}

.cleanup-action-list {
  display: grid;
  gap: 14px;
  margin-top: 10px;
}

.cleanup-section {
  margin-top: 16px;
}

.cleanup-action-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0;
  border-top: 1px solid #e2e8f0;
}

.cleanup-action-row:first-child {
  border-top: 0;
  padding-top: 0;
}

.cleanup-action-list + .cleanup-section,
.cleanup-section + .cleanup-section {
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.cleanup-section + .export-options {
  margin-top: 16px;
}

.cleanup-action-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.cleanup-action-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.cleanup-count {
  font-size: 13px;
  font-weight: 700;
  color: #475569;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .reset-selection-list.collection-group-items {
    grid-template-columns: 1fr;
  }

  .cleanup-action-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .cleanup-action-meta {
    justify-content: flex-start;
  }
}

@media (min-width: 641px) and (max-width: 980px) {
  .reset-selection-list.collection-group-items {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.reset-bucket-option {
  align-items: flex-start;
}

.reset-bucket-option code {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  background: #eef2ff;
  color: #3730a3;
  padding: 1px 4px;
  border-radius: 4px;
}

.option-hint {
  font-size: 12px;
  color: #94a3b8;
}

.export-actions,
.import-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.collection-dry-run-summary {
  margin-bottom: 16px;
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}

.collection-dry-run-warnings {
  border-top-color: #bfdbfe;
}

.unused-media-results {
  margin-top: 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
  padding: 10px 12px;
}

.unused-media-summary,
.unused-media-scan-meta {
  margin: 0;
  font-size: 12px;
  color: #1e3a8a;
}

.unused-media-scan-meta {
  margin-top: 6px;
}

.unused-media-scan-meta code {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  background: #eef2ff;
  color: #3730a3;
  padding: 1px 4px;
  border-radius: 4px;
}

.unused-media-list-wrap {
  margin-top: 10px;
  max-height: 220px;
  overflow: auto;
  border-top: 1px solid #dbeafe;
  padding-top: 8px;
}

.unused-media-selection-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.unused-media-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: #334155;
}

.unused-media-list li {
  margin: 3px 0;
}

.unused-media-list-item--excluded {
  opacity: 0.7;
}

.unused-media-exclude-option {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-right: 8px;
  font-size: 11px;
  color: #475569;
}

/* Import Warning */
.import-warning {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  background: color-mix(in srgb, var(--admin-warning-color, #d97706) 16%, #ffffff);
  border: 1px solid color-mix(in srgb, var(--admin-warning-color, #d97706) 38%, #ffffff);
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  color: color-mix(in srgb, var(--admin-warning-color, #d97706) 90%, #0f172a);
}

.warning-icon {
  flex-shrink: 0;
  color: var(--admin-warning-color, #d97706);
  font-size: 20px;
}

/* Import Zone */
.import-zone {
  border: 2px dashed #e2e8f0;
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 16px;
  transition: all 0.15s;
}

.import-zone.drag-over {
  border-color: #4f46e5;
  background: #f5f3ff;
}

.import-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  color: #64748b;
}

.import-placeholder-icon {
  opacity: 0.5;
  font-size: 40px;
}

.import-placeholder p {
  margin: 0;
  font-size: 14px;
}

.selected-file {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.selected-files {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.selected-files-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-info-icon {
  color: #4f46e5;
  font-size: 22px;
}

.btn-action-icon {
  font-size: 16px;
}

.file-name {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #334155;
}

.file-size {
  display: block;
  font-size: 12px;
  color: #64748b;
}

/* Status Messages */
.status-message {
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
}

.status-message.success {
  background: #ecfdf5;
  border: 1px solid #6ee7b7;
  color: #065f46;
}

.status-message.error {
  background: #fef2f2;
  border: 1px solid #fca5a5;
  color: #991b1b;
}

.status-message ul {
  margin: 8px 0 0;
  padding-left: 20px;
}

.status-message li {
  margin: 4px 0;
}

.import-errors {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #fca5a5;
}

.migration-summary {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.summary-row,
.summary-input-row {
  display: grid;
  grid-template-columns: 140px 1fr;
  align-items: center;
  gap: 12px;
}

.summary-label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.summary-value {
  font-size: 13px;
  color: #0f172a;
}

.text-input,
.select-input {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 9px 10px;
  font-size: 13px;
  color: #1e293b;
  background: #fff;
}

.text-input:focus,
.select-input:focus {
  outline: none;
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12);
}

.migration-table-wrap {
  overflow-x: auto;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.migration-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  min-width: 560px;
}

.migration-table-col--collection {
  width: 48%;
}

.migration-table-col--documents {
  width: 18%;
}

.migration-table-col--action {
  width: 34%;
}

.migration-table th,
.migration-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
  font-size: 13px;
  color: #334155;
}

.migration-table th {
  background: #f8fafc;
  font-weight: 700;
  color: #0f172a;
}

.migration-table tbody tr:last-child td {
  border-bottom: none;
}

.migration-selected-summary {
  margin-top: 12px;
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #64748b;
}

.bucket-options {
  display: grid;
  gap: 10px;
  margin: 12px 0;
}
</style>
