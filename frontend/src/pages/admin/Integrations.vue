<template>
  <div class="admin-integrations admin-page">
    <AutosaveToast :message="connectionAutosaveToastMessage" :tone="connectionAutosaveToastTone" />

    <header class="page-header">
      <h1>Integrations</h1>
      <p class="page-subtitle">Manage external API and crawler integrations for importing data into sections.</p>
    </header>

    <div v-if="loading" class="loading-state">Loading integrations...</div>

    <template v-else>
      <AdminPageTabs
        :tabs="tabs"
        :model-value="activeTab"
        @update:model-value="setActiveTab"
      />

      <template v-if="activeTab === 'create'">
        <div class="config-card">
          <div class="card-header">
            <h2>Create Integration</h2>
            <p class="card-hint">Configure API/crawler settings for a new integration.</p>
          </div>

          <form class="integration-form" @submit.prevent="saveIntegration">
            <div class="form-row">
              <div class="form-group">
                <label for="name">Name *</label>
                <input
                  id="name"
                  v-model="form.name"
                  type="text"
                  placeholder="e.g., Program API"
                  required
                />
              </div>
              <div class="form-group">
                <label for="url">URL *</label>
                <input
                  id="url"
                  v-model="form.url"
                  type="text"
                  placeholder="https://api.example.com/data"
                  required
                />
              </div>
            </div>

            <div class="form-row">
              <div class="form-group form-group-full">
                <label for="description">Description (optional)</label>
                <textarea
                  id="description"
                  v-model="form.description"
                  rows="2"
                  placeholder="Describe what this integration/crawler is intended to do."
                ></textarea>
              </div>
            </div>

            <div class="form-row form-row-four">
              <div class="form-group">
                <label for="type">Type</label>
                <select id="type" v-model="form.type" @change="onCreateTypeChange">
                  <option value="api">API</option>
                  <option value="crawler">Crawler</option>
                </select>
              </div>
              <div class="form-group">
                <label for="auth_type">Authentication</label>
                <select id="auth_type" v-model="form.auth_type">
                  <option value="none">None</option>
                  <option value="api_key">API Key (X-API-Key header)</option>
                  <option value="bearer">Bearer Token (Authorization: Bearer)</option>
                  <option value="token">Token (Authorization: Token)</option>
                  <option value="basic">Basic Auth</option>
                </select>
              </div>
              <div class="form-group">
                <label for="response_type">Response Format</label>
                <select id="response_type" v-model="form.response_type">
                  <option value="json">JSON</option>
                  <option value="csv">CSV</option>
                  <option value="xml">XML</option>
                </select>
              </div>
              <div class="form-group">
                <label for="response_path">Response Path</label>
                <input
                  id="response_path"
                  v-model="form.response_path"
                  type="text"
                  placeholder="e.g., results or data.items"
                />
                <span class="form-hint">Dot-separated path to data list (leave empty for root).</span>
              </div>
            </div>

            <div v-if="form.auth_type !== 'none'" class="form-row">
              <div class="form-group form-group-full">
                <label for="key_name">Environment Variable Name</label>
                <input
                  id="key_name"
                  v-model="form.key_name"
                  type="text"
                  placeholder="e.g., PROGRAM_API_KEY"
                />
                <span class="form-hint">Name of the env variable containing the credential.</span>
                <div class="env-info">
                  <span>Add credential to backend env:</span>
                  <code>{{ form.key_name || "KEY_NAME" }}=your_secret_value</code>
                </div>
              </div>
            </div>

            <div v-if="form.type === 'crawler'" class="transform-editor">
              <div class="transform-editor-header">
                <h3>Crawler Pagination</h3>
              </div>
              <div class="form-row form-row-four">
                <div class="form-group">
                  <label>Strategy</label>
                  <select v-model="form.crawler_pagination_strategy">
                    <option value="">None</option>
                    <option value="page_count">By Page Count Field</option>
                    <option value="next_page">By Next Page Field</option>
                  </select>
                </div>
                <div class="form-group">
                  <label>Max Page Visits</label>
                  <input
                    v-model="form.crawler_max_page_visits"
                    type="number"
                    min="1"
                    step="1"
                  />
                </div>
                <div class="form-group" v-if="form.type === 'crawler' && form.crawler_pagination_strategy === 'page_count'">
                  <label>Page Query Param</label>
                  <input v-model="form.crawler_page_query_param" type="text" placeholder="e.g., page" />
                </div>
                <div class="form-group">
                  <label>Query Loop Key (optional)</label>
                  <input v-model="form.crawler_query_loop_key" type="text" placeholder="e.g., category" />
                </div>
                <div class="form-group" v-if="form.type === 'crawler' && form.crawler_pagination_strategy === 'page_count'">
                  <label>Page Count Field</label>
                  <input v-model="form.crawler_page_count_field" type="text" placeholder="e.g., total_count" />
                </div>
                <div class="form-group form-group-full">
                  <label>Query Loop Values (comma-separated, optional)</label>
                  <input v-model="form.crawler_query_loop_values_input" type="text" placeholder="e.g., music,art,talk" />
                  <span class="form-hint">
                    Runs one request per value using <code>?&lt;key&gt;=&lt;value&gt;</code>.
                  </span>
                </div>
                <div class="form-group form-group-full" v-if="form.type === 'crawler' && form.crawler_pagination_strategy === 'next_page'">
                  <label>Next Page Field</label>
                  <input v-model="form.crawler_next_page_field" type="text" placeholder="e.g., next or paging.next_url" />
                </div>
              </div>
            </div>

            <TransformStepsEditor
              v-model="form.transform_steps"
              :path-rule-hint="INTEGRATION_PATH_RULE_HINT"
              :target-rule-hint="INTEGRATION_TARGET_RULE_HINT"
            />

            <div class="form-actions">
              <button type="button" class="btn-outline" :disabled="draftHealthChecking" @click="runDraftHealthCheck">
                {{ draftHealthChecking ? "Checking..." : "Health Check" }}
              </button>
              <button type="submit" class="btn-primary" :disabled="saving">
                {{ saving ? "Saving..." : "Create Integration" }}
              </button>
            </div>

            <div
              v-if="draftHealthResult"
              class="health-result"
              :class="draftHealthResult.ok ? 'success' : 'error'"
            >
              <span v-if="draftHealthResult.ok">
                OK ({{ draftHealthResult.status_code || 200 }})
                <template v-if="draftHealthResult.response_time_ms != null">
                  - {{ draftHealthResult.response_time_ms }}ms
                </template>
              </span>
              <span v-else>
                Failed: {{ draftHealthResult.error || `Status ${draftHealthResult.status_code}` }}
              </span>
            </div>
          </form>
        </div>
      </template>

      <template v-else-if="activeTab === 'manage'">
        <div class="manage-layout">
          <div class="manage-main">
            <div v-if="integrations.length > 0" class="config-card selected-integration-card">
              <div v-if="integrations.length > 0 && filteredIntegrations.length === 0" class="empty-state">
                No integrations match the selected filters.
              </div>

              <template v-else>
                <div
                  v-for="integration in selectedManageIntegrationList"
                  :key="integration.id"
                  class="integration-item selected-integration-item"
                  :class="{ 'selected-integration-item--editing': Boolean(getManageSubsection(integration)) }"
                  :ref="(el) => setIntegrationItemRef(integration.id, el)"
                >
                  <div class="integration-header">
                    <div class="integration-name">
                      {{ integration.name }}
                    </div>
                    <div class="integration-actions">
                      <button
                        class="btn-icon btn-favorite"
                        :class="{ active: Boolean(integration.favorite) }"
                        :disabled="favoriteSaving[integration.id]"
                        @click="toggleFavorite(integration)"
                        :title="integration.favorite ? 'Remove Favorite' : 'Add Favorite'"
                      >
                        <font-awesome-icon :icon="faStar" />
                      </button>
                      <button
                        class="btn-icon"
                        @click="cloneIntegration(integration)"
                        :disabled="cloning[integration.id]"
                        title="Clone Integration"
                      >
                        <font-awesome-icon :icon="faClone" />
                      </button>
                      <button class="btn-icon btn-danger-soft" @click="confirmDelete(integration)" title="Delete">
                        <font-awesome-icon :icon="faTrashCan" />
                      </button>
                    </div>
                  </div>

                <div class="integration-details">
                  <div v-if="getEffectiveIntegrationUrl(integration)" class="detail-row">
                    <span class="detail-label">URL:</span>
                    <span class="detail-value url">{{ getEffectiveIntegrationUrl(integration) }}</span>
                  </div>
                  <div class="detail-row">
                    <span class="detail-label">Return Type:</span>
                    <span
                      class="return-type-badge"
                      :class="`return-type-${normalizeReturnType(integration.return_type)}`"
                    >
                      {{ normalizeReturnType(integration.return_type) }}
                    </span>
                  </div>
                  <div class="detail-row">
                    <span class="detail-label">Integration Type:</span>
                    <span
                      class="type-badge"
                      :class="normalizeIntegrationType(integration.type)"
                    >
                      {{ getIntegrationTypeLabel(integration) }}
                    </span>
                  </div>
                  <div v-if="getIntegrationContainerTags(integration).length" class="detail-row">
                    <span class="detail-label">Hierarchy Tags:</span>
                    <div class="tag-list">
                      <span
                        v-for="tag in getIntegrationContainerTags(integration)"
                        :key="`${integration.id}-${tag}`"
                        class="container-tag"
                      >
                        {{ tag }}
                      </span>
                    </div>
                  </div>
                  <div class="detail-row">
                    <span class="detail-label">Last fetched:</span>
                    <span class="detail-value" :class="{ 'no-data': !integration.last_fetched }">
                      {{ integration.last_fetched ? formatDateTime(integration.last_fetched) : "Never" }}
                    </span>
                  </div>
                </div>

                <div class="inline-edit-card">
                  <form class="integration-form" @submit.prevent="saveInlineEdit">
                    <div class="manage-subsection-list">
                      <section class="manage-subsection">
                        <button
                          type="button"
                          class="manage-subsection-toggle"
                          :class="{ active: isManageSubsectionOpen(integration, 'config') }"
                      :ref="(el) => setManageSubsectionRef(integration.id, 'config', el)"
                      @click="setManageSubsection(integration, 'config')"
                        >
                          <font-awesome-icon :icon="getManageSubsectionIcon('config')" />
                          <span>Config</span>
                        </button>
                        <div v-if="isManageSubsectionOpen(integration, 'config')" class="manage-subsection-body">
                          <div class="form-row">
                            <div class="form-group">
                              <label>Name *</label>
                              <input v-model="inlineForm.name" type="text" required />
                            </div>
                            <div class="form-group">
                              <label>Type</label>
                              <div v-if="isComposableIntegration(integration)" class="readonly-field">Composable</div>
                              <select v-else v-model="inlineForm.type" @change="onInlineTypeChange">
                                <option value="api">API</option>
                                <option value="crawler">Crawler</option>
                              </select>
                            </div>
                          </div>

                          <div class="form-row">
                            <div class="form-group form-group-full">
                              <label>Description (optional)</label>
                              <textarea
                                v-model="inlineForm.description"
                                rows="2"
                                placeholder="Describe what this integration/crawler is intended to do."
                              ></textarea>
                            </div>
                          </div>

                          <template v-if="!isComposableIntegrationType(inlineForm.type)">
                            <div class="form-row form-row-four">
                              <div class="form-group form-group-full">
                                <label>URL *</label>
                                <input v-model="inlineForm.url" type="text" required />
                              </div>
                              <div class="form-group">
                                <label>Authentication</label>
                                <select v-model="inlineForm.auth_type">
                                  <option value="none">None</option>
                                  <option value="api_key">API Key (X-API-Key header)</option>
                                  <option value="bearer">Bearer Token (Authorization: Bearer)</option>
                                  <option value="token">Token (Authorization: Token)</option>
                                  <option value="basic">Basic Auth</option>
                                </select>
                              </div>
                              <div class="form-group">
                                <label>Response Format</label>
                                <select v-model="inlineForm.response_type">
                                  <option value="json">JSON</option>
                                  <option value="csv">CSV</option>
                                  <option value="xml">XML</option>
                                </select>
                              </div>
                              <div class="form-group form-group-full">
                                <label>Response Path</label>
                                <input v-model="inlineForm.response_path" type="text" placeholder="e.g., results or data.items" />
                              </div>
                            </div>

                            <div v-if="inlineForm.auth_type !== 'none'" class="form-row">
                              <div class="form-group form-group-full">
                                <label>Environment Variable Name</label>
                                <input v-model="inlineForm.key_name" type="text" placeholder="e.g., PROGRAM_API_KEY" />
                              </div>
                            </div>

                            <div v-if="inlineForm.type === 'crawler'" class="transform-editor">
                              <div class="transform-editor-header">
                                <h3>Crawler Pagination</h3>
                              </div>
                              <div class="form-row form-row-four">
                                <div class="form-group">
                                  <label>Strategy</label>
                                  <select v-model="inlineForm.crawler_pagination_strategy">
                                    <option value="">None</option>
                                    <option value="page_count">By Page Count Field</option>
                                    <option value="next_page">By Next Page Field</option>
                                  </select>
                                </div>
                                <div class="form-group">
                                  <label>Max Page Visits</label>
                                  <input
                                    v-model="inlineForm.crawler_max_page_visits"
                                    type="number"
                                    min="1"
                                    step="1"
                                  />
                                </div>
                                <div class="form-group" v-if="inlineForm.type === 'crawler' && inlineForm.crawler_pagination_strategy === 'page_count'">
                                  <label>Page Query Param</label>
                                  <input v-model="inlineForm.crawler_page_query_param" type="text" placeholder="e.g., page" />
                                </div>
                                <div class="form-group">
                                  <label>Query Loop Key (optional)</label>
                                  <input v-model="inlineForm.crawler_query_loop_key" type="text" placeholder="e.g., category" />
                                </div>
                                <div class="form-group" v-if="inlineForm.type === 'crawler' && inlineForm.crawler_pagination_strategy === 'page_count'">
                                  <label>Page Count Field</label>
                                  <input v-model="inlineForm.crawler_page_count_field" type="text" placeholder="e.g., total_count" />
                                </div>
                                <div class="form-group form-group-full">
                                  <label>Query Loop Values (comma-separated, optional)</label>
                                  <input v-model="inlineForm.crawler_query_loop_values_input" type="text" placeholder="e.g., music,art,talk" />
                                  <span class="form-hint">
                                    Runs one request per value using <code>?&lt;key&gt;=&lt;value&gt;</code>.
                                  </span>
                                </div>
                                <div class="form-group form-group-full" v-if="inlineForm.type === 'crawler' && inlineForm.crawler_pagination_strategy === 'next_page'">
                                  <label>Next Page Field</label>
                                  <input v-model="inlineForm.crawler_next_page_field" type="text" placeholder="e.g., next or paging.next_url" />
                                </div>
                              </div>
                            </div>
                          </template>

                          <template v-else>
                            <div class="transform-editor">
                              <div class="transform-editor-header">
                                <h3>Sources (Merge Order)</h3>
                              </div>
                              <p class="card-hint integration-case-hint">
                                {{ INTEGRATION_PATH_RULE_HINT }} {{ INTEGRATION_TARGET_RULE_HINT }}
                              </p>
                              <p class="card-hint">
                                Without target source, lists are concatenated. Set a target directly on a source row to merge non-target sources into it.
                              </p>
                              <draggable
                                v-model="inlineContainerForm.sources"
                                item-key="ui_id"
                                class="transform-step-list"
                                handle=".drag-handle"
                                ghost-class="transform-step--dragging"
                                chosen-class="transform-step--dragging"
                                :animation="150"
                              >
                                <template #item="{ element: source, index: sourceIndex }">
                                <div
                                  class="transform-step"
                                  :class="{
                                    'target-source-step': isTargetSource(source, inlineContainerForm.target_source_integration_id),
                                  }"
                                >
                                  <div class="transform-step-head">
                                    <div class="transform-step-title">
                                      <button
                                        type="button"
                                        class="drag-handle"
                                        title="Drag source"
                                        aria-label="Drag source"
                                      >
                                        <font-awesome-icon :icon="faGripVertical" />
                                      </button>
                                      <button
                                        type="button"
                                        class="transform-step-collapse"
                                        :title="source.collapsed ? 'Expand source' : 'Collapse source'"
                                        :aria-label="source.collapsed ? 'Expand source' : 'Collapse source'"
                                        @click="source.collapsed = !source.collapsed"
                                      >
                                        <font-awesome-icon :icon="source.collapsed ? faChevronRight : faChevronDown" />
                                      </button>
                                      <span class="step-index">
                                        {{ getContainerSourceRowLabel(source, sourceIndex) }}
                                      </span>
                                    </div>
                                    <div class="transform-step-actions">
                                      <button
                                        type="button"
                                        class="btn-outline btn-sm"
                                        :class="{ active: isTargetSource(source, inlineContainerForm.target_source_integration_id) }"
                                        :disabled="!source.integration_id"
                                        @click="toggleInlineContainerTargetSource(source)"
                                      >
                                        {{ isTargetSource(source, inlineContainerForm.target_source_integration_id) ? "Target" : "Set Target" }}
                                      </button>
                                      <button
                                        type="button"
                                        class="btn-outline btn-sm"
                                        :disabled="!source.integration_id"
                                        @click="previewSourceIntegration(source.integration_id)"
                                      >
                                        Preview
                                      </button>
                                      <button type="button" class="btn-outline btn-sm danger" :disabled="inlineContainerForm.sources.length <= 2" @click="removeInlineContainerSource(sourceIndex)">Remove</button>
                                    </div>
                                  </div>
                                  <div v-show="!source.collapsed" class="transform-step-body">
                                    <div class="form-row">
                                      <div class="form-group form-group-full">
                                        <label>Integration</label>
                                        <select v-model="source.integration_id" required>
                                          <option value="">-- Select integration --</option>
                                          <option
                                            v-for="candidate in getContainerSourceOptions(integration.id)"
                                            :key="candidate.id"
                                            :value="candidate.id"
                                          >
                                            {{ candidate.name }}
                                          </option>
                                        </select>
                                      </div>
                                    </div>
                                    <div
                                      v-if="inlineContainerForm.target_source_integration_id && source.integration_id !== inlineContainerForm.target_source_integration_id"
                                      class="form-row key-path-row"
                                    >
                                      <div class="form-group">
                                        <label>Target Key</label>
                                        <select v-model="source.target_key_path">
                                          <option value="">-- Select Target Key --</option>
                                          <option
                                            v-for="field in getIntegrationPrimeKeyOptionsWithCurrent(inlineContainerForm.target_source_integration_id, source.target_key_path)"
                                            :key="`inline-target-primekey-${source.ui_id}-${field}`"
                                            :value="field"
                                          >
                                            {{ field }}
                                          </option>
                                        </select>
                                        <span class="form-hint" v-if="isIntegrationPrimeKeyOptionsLoading(inlineContainerForm.target_source_integration_id)">
                                          Loading target fields...
                                        </span>
                                        <span class="form-hint" v-else-if="getIntegrationPrimeKeyOptionsWithCurrent(inlineContainerForm.target_source_integration_id, source.target_key_path).length === 0">
                                          No target keys available. Fetch/process the target integration first.
                                        </span>
                                      </div>
                                      <div class="form-group">
                                        <label>Source Key</label>
                                        <select v-model="source.source_key_path">
                                          <option value="">-- Select Source Key --</option>
                                          <option
                                            v-for="field in getIntegrationPrimeKeyOptionsWithCurrent(source.integration_id, source.source_key_path)"
                                            :key="`inline-source-primekey-${source.ui_id}-${field}`"
                                            :value="field"
                                          >
                                            {{ field }}
                                          </option>
                                        </select>
                                        <span class="form-hint" v-if="isIntegrationPrimeKeyOptionsLoading(source.integration_id)">
                                          Loading source fields...
                                        </span>
                                        <span class="form-hint" v-else-if="getIntegrationPrimeKeyOptionsWithCurrent(source.integration_id, source.source_key_path).length === 0">
                                          No source keys available. Fetch/process the source integration first.
                                        </span>
                                      </div>
                                    </div>
                                    <div
                                      v-if="inlineContainerForm.target_source_integration_id && source.integration_id !== inlineContainerForm.target_source_integration_id"
                                      class="form-row"
                                    >
                                      <div class="form-group">
                                        <label>Merge Style</label>
                                        <select v-model="source.merge_style">
                                          <option value="flat">Flat (top-level fields)</option>
                                          <option value="nested">Nested Object (replaces target key)</option>
                                        </select>
                                        <span class="form-hint">Applies when this source is merged into the selected target source.</span>
                                      </div>
                                      <div
                                        class="form-group"
                                        v-if="inlineContainerForm.target_source_integration_id && source.integration_id !== inlineContainerForm.target_source_integration_id"
                                      >
                                        <label class="checkbox-item">
                                          <input v-model="source.keep_target_key" type="checkbox" />
                                          <span>Keep Target Key</span>
                                        </label>
                                        <span class="form-hint">
                                          Keeps the target key value as <code>&lt;key&gt;_target</code> before flat or nested merge.
                                        </span>
                                      </div>
                                      <div
                                        class="form-group"
                                        v-if="inlineContainerForm.target_source_integration_id && source.integration_id !== inlineContainerForm.target_source_integration_id && source.merge_style === 'nested'"
                                      >
                                        <label>Nested Key</label>
                                        <input v-model="source.nested_key" type="text" placeholder="e.g., answer_data" />
                                      </div>
                                    </div>
                                  </div>
                                </div>
                                </template>
                              </draggable>
                              <div class="form-actions">
                                <button type="button" class="btn-outline btn-sm" @click="addInlineContainerSource">Add Source</button>
                                <button
                                  type="button"
                                  class="btn-outline btn-sm"
                                  :disabled="!inlineContainerForm.target_source_integration_id"
                                  @click="clearInlineContainerTargetSource"
                                >
                                  Clear Target
                                </button>
                              </div>
                            </div>
                          </template>

                          <div v-if="inlineDraftHealthResult" class="health-result" :class="inlineDraftHealthResult.ok ? 'success' : 'error'">
                            <span v-if="inlineDraftHealthResult.ok">
                              OK ({{ inlineDraftHealthResult.status_code || 200 }})
                              <template v-if="inlineDraftHealthResult.response_time_ms != null"> - {{ inlineDraftHealthResult.response_time_ms }}ms</template>
                            </span>
                            <span v-else>
                              Failed: {{ inlineDraftHealthResult.error || `Status ${inlineDraftHealthResult.status_code}` }}
                            </span>
                          </div>
                        </div>
                      </section>

                      <section class="manage-subsection">
                        <button
                          type="button"
                          class="manage-subsection-toggle"
                          :class="{ active: isManageSubsectionOpen(integration, 'transform') }"
                          :ref="(el) => setManageSubsectionRef(integration.id, 'transform', el)"
                          @click="setManageSubsection(integration, 'transform')"
                        >
                          <font-awesome-icon :icon="getManageSubsectionIcon('transform')" />
                          <span>Transformation</span>
                        </button>
                        <div v-if="isManageSubsectionOpen(integration, 'transform')" class="manage-subsection-body">
                          <TransformStepsEditor
                            v-model="inlineForm.transform_steps"
                            :path-rule-hint="INTEGRATION_PATH_RULE_HINT"
                            :target-rule-hint="INTEGRATION_TARGET_RULE_HINT"
                          />
                        </div>
                      </section>

                      <section class="manage-subsection">
                        <button
                          type="button"
                          class="manage-subsection-toggle"
                          :class="{ active: isManageSubsectionOpen(integration, 'schema') }"
                          :ref="(el) => setManageSubsectionRef(integration.id, 'schema', el)"
                          @click="setManageSubsection(integration, 'schema')"
                        >
                          <font-awesome-icon :icon="getManageSubsectionIcon('schema')" />
                          <span>Schema</span>
                        </button>
                        <div v-if="isManageSubsectionOpen(integration, 'schema')" class="manage-subsection-body manage-schema-panel">
                          <div v-if="manageSchemaStatus" class="health-result" :class="manageSchemaStatus.type === 'error' ? 'error' : 'success'">
                            {{ manageSchemaStatus.message }}
                          </div>

                          <div v-if="!integration.last_fetched" class="empty-state">
                            Fetch data before managing the schema.
                          </div>
                          <div v-else-if="manageSchemaLoading" class="loading-state compact">Loading schema...</div>
                          <div v-else-if="manageSchemaFields.length === 0" class="empty-state">
                            No schema fields detected yet. Run Processing after fetching data.
                          </div>
                          <div v-else class="review-field-table-wrap">
                            <table class="review-field-table schema-table">
                              <thead>
                                <tr>
                                  <th v-if="normalizeReturnType(integration.return_type) === 'list'">ID</th>
                                  <th>Item name</th>
                                  <th v-if="normalizeReturnType(integration.return_type) === 'list'">Page Slug</th>
                                  <th>Field</th>
                                  <th>Detected Type</th>
                                  <th>Manual</th>
                                  <th>Required</th>
                                  <th>Coverage</th>
                                  <th>Collect Options</th>
                                  <th>Cache media</th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr v-for="field in manageSchemaFields" :key="`manage-schema-field-${field.path}`">
                                  <td v-if="normalizeReturnType(integration.return_type) === 'list'">
                                    <input
                                      type="radio"
                                      :name="`manage-schema-output-key-${integration.id}`"
                                      :checked="Boolean(field.is_output_primary_key)"
                                      :disabled="manageSchemaSaving[field.path]"
                                      @change="setManageSchemaOutputPrimaryKeyPath(field.path)"
                                    />
                                  </td>
                                  <td>
                                    <input
                                      type="radio"
                                      :name="`manage-schema-item-label-${integration.id}`"
                                      :checked="Boolean(field.is_item_label)"
                                      :disabled="manageSchemaSaving[field.path]"
                                      @change="setManageSchemaItemLabelPath(field.path)"
                                    />
                                  </td>
                                  <td v-if="normalizeReturnType(integration.return_type) === 'list'">
                                    <input
                                      type="radio"
                                      :name="`manage-schema-page-slug-${integration.id}`"
                                      :checked="Boolean(field.is_page_slug)"
                                      :disabled="manageSchemaSaving[field.path]"
                                      @change="setManageSchemaPageSlugPath(field.path)"
                                    />
                                  </td>
                                  <td class="review-field-path">
                                    <code>{{ field.path }}</code>
                                    <div class="review-field-badges">
                                      <span v-if="field.inconsistent" class="review-badge conflict">Inconsistent</span>
                                    </div>
                                  </td>
                                  <td>{{ formatSchemaType(field.detected_type) }}</td>
                                  <td>
                                    <select
                                      :value="field.manual_type || ''"
                                      :disabled="manageSchemaSaving[field.path]"
                                      @change="setManageSchemaFieldType(field.path, $event.target.value)"
                                    >
                                      <option value="">Auto</option>
                                      <option v-for="type in REVIEW_SCHEMA_TYPES" :key="`manage-schema-type-${field.path}-${type}`" :value="type">
                                        {{ formatSchemaType(type) }}
                                      </option>
                                    </select>
                                  </td>
                                  <td>
                                    <label class="checkbox-item checkbox-item-compact">
                                      <input
                                        type="checkbox"
                                        :checked="Boolean(field.required)"
                                        :disabled="manageSchemaSaving[field.path]"
                                        @change="setManageSchemaFieldRequired(field.path, $event.target.checked)"
                                      />
                                    </label>
                                  </td>
                                  <td>{{ field.occurrence_count || 0 }} / {{ field.occurrence_count + field.missing_count || 0 }}</td>
                                  <td>
                                    <label class="checkbox-item checkbox-item-compact">
                                      <input
                                        type="checkbox"
                                        :checked="Boolean(field.collect_options)"
                                        :disabled="manageSchemaSaving[field.path]"
                                        @change="setManageSchemaFieldCollectOptions(field.path, $event.target.checked)"
                                      />
                                    </label>
                                  </td>
                                  <td>
                                    <label v-if="isManageSchemaImageField(field)" class="checkbox-item checkbox-item-compact">
                                      <input
                                        type="checkbox"
                                        :checked="Boolean(field.cache_media)"
                                        :disabled="manageSchemaSaving[field.path]"
                                        @change="setManageSchemaFieldCacheMedia(field.path, $event.target.checked)"
                                      />
                                    </label>
                                    <span v-else class="schema-muted-value">-</span>
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </section>
                    </div>
                  </form>
                </div>

                <div class="integration-buttons">
                  <div class="integration-actions-left">
                    <button
                      v-if="!isComposableIntegration(integration)"
                      class="btn-outline btn-sm"
                      @click="runHealthCheck(integration)"
                      :disabled="healthChecking[integration.id]"
                    >
                      <span v-if="healthChecking[integration.id]">Checking...</span>
                      <span v-else>Health Check</span>
                    </button>
                    <button 
                      class="btn-outline btn-sm" @click="fetchData(integration)" :disabled="fetching[integration.id]">
                      <span v-if="fetching[integration.id]">Fetching...</span>
                      <span v-else>Fetch Data</span>
                    </button>
                    <button
                      v-if="isComposableIntegration(integration)"
                      class="btn-primary btn-sm"
                      @click="deepFetchData(integration)"
                      :disabled="deepFetching[integration.id]"
                    >
                      <span v-if="deepFetching[integration.id]">Deep Fetching...</span>
                      <span v-else>Deep Fetch</span>
                    </button>
                    <button
                      class="btn-outline btn-sm"
                      @click="reprocessData(integration)"
                      :disabled="reprocessing[integration.id] || !integration.last_fetched"
                    >
                      <span v-if="reprocessing[integration.id]">Reprocessing...</span>
                      <span v-else>Run Processing</span>
                    </button>
                    <button
                      v-if="inlineEditHasChanges"
                      class="btn-primary btn-sm"
                      type="button"
                      :disabled="inlineSaving"
                      @click="saveInlineEdit"
                    >
                      {{ inlineSaving ? "Saving..." : "Save Changes" }}
                    </button>
                  </div>
                  <div class="integration-actions-right">
                    <button class="btn-outline btn-sm" @click="showPreview(integration)" :disabled="previewLoading || !integration.last_fetched">
                      <span v-if="previewLoading && previewIntegrationId === integration.id">Loading...</span>
                      <span v-else>Preview</span>
                    </button>
                  </div>
                </div>

                <div
                  v-if="processingStatusById[integration.id]"
                  class="processing-status-row health-result"
                  :class="processingStatusById[integration.id].type === 'error' ? 'error' : 'success'"
                >
                  {{ processingStatusById[integration.id].message }}
                </div>

                <div
                  v-if="!isComposableIntegration(integration) && healthResults[integration.id]"
                  class="health-result"
                  :class="healthResults[integration.id].ok ? 'success' : 'error'"
                >
                  <span v-if="healthResults[integration.id].ok">
                    OK ({{ healthResults[integration.id].status_code || 200 }})
                    <template v-if="healthResults[integration.id].response_time_ms != null">
                      - {{ healthResults[integration.id].response_time_ms }}ms
                    </template>
                  </span>
                  <span v-else>
                    Failed: {{ healthResults[integration.id].error || `Status ${healthResults[integration.id].status_code}` }}
                  </span>
                </div>

                </div>
              </template>
            </div>

            <div class="config-card manage-reference-card">
              <div class="card-header">
                <h2>Integration Glossar</h2>
              </div>

              <div class="manage-reference-section">
                <h3>Action Buttons</h3>
                <dl>
                  <div>
                    <dt>Save Changes</dt>
                    <dd>Persists config, sources, and transformation edits; fetch or process again to refresh schema output.</dd>
                  </div>
                  <div>
                    <dt>Health Check</dt>
                    <dd>Tests base API/crawler access without changing fetched data or schema columns.</dd>
                  </div>
                  <div>
                    <dt>Fetch Data</dt>
                    <dd>Pulls fresh source data and refreshes schema detection for Field, Detected Type, and Coverage.</dd>
                  </div>
                  <div>
                    <dt>Deep Fetch</dt>
                    <dd>Refreshes composable dependencies and updates merged schema, media cache, and item counts.</dd>
                  </div>
                  <div>
                    <dt>Run Processing</dt>
                    <dd>Reapplies transforms and updates Coverage, Collect Options, Cache media, and processed preview data.</dd>
                  </div>
                  <div>
                    <dt>Preview</dt>
                    <dd>Shows processed item and metadata previews, using Item name and ID when configured.</dd>
                  </div>
                </dl>
              </div>
              <div class="manage-reference-section">
                <h3>Transformation Steps</h3>
                <dl>
                  <div>
                    <dt>keep_keys</dt>
                    <dd>Keeps only the listed key paths on each processed item; nested paths are supported.</dd>
                  </div>
                  <div>
                    <dt>remove_keys</dt>
                    <dd>Removes listed key paths before schema detection and preview; nested paths are supported.</dd>
                  </div>
                  <div>
                    <dt>ensure_keys</dt>
                    <dd>Adds missing key paths with null values so every item exposes the same fields.</dd>
                  </div>
                  <div>
                    <dt>group_by</dt>
                    <dd>Groups items by one key path into entries with grouped documents.</dd>
                  </div>
                  <div>
                    <dt>replace_nested_item</dt>
                    <dd>Finds nested items by key/value, removes matched entries, and can map values into target paths.</dd>
                  </div>
                  <div>
                    <dt>filter_by_allowed_values</dt>
                    <dd>Keeps items only when a field matches one of the allowed values.</dd>
                  </div>
                  <div>
                    <dt>filter_by_disallowed_values</dt>
                    <dd>Removes items with disallowed values and always removes empty values at the selected field.</dd>
                  </div>
                  <div>
                    <dt>split_values_to_list</dt>
                    <dd>Splits one string value into a list using the configured separator substring.</dd>
                  </div>
                  <div>
                    <dt>rename_keys</dt>
                    <dd>Moves values from old key paths to new key paths on each item and removes the old keys.</dd>
                  </div>
                </dl>
              </div>
              <div class="manage-reference-section">
                <h3>Schema Columns</h3>
                <dl>
                  <div>
                    <dt>ID</dt>
                    <dd>Unique key used to match list items across fetches and reviews.</dd>
                  </div>
                  <div>
                    <dt>Item name</dt>
                    <dd>Display label used to identify an item in review and preview lists.</dd>
                  </div>
                  <div>
                    <dt>Page Slug</dt>
                    <dd>Field used as the generated page URL slug for list items.</dd>
                  </div>
                  <div>
                    <dt>Field</dt>
                    <dd>Detected source path for the value in the processed item.</dd>
                  </div>
                  <div>
                    <dt>Detected Type</dt>
                    <dd>Automatically inferred value type from the fetched data.</dd>
                  </div>
                  <div>
                    <dt>Manual</dt>
                    <dd>Optional override for the detected field type.</dd>
                  </div>
                  <div>
                    <dt>Required</dt>
                    <dd>Marks whether review/local items must provide this value.</dd>
                  </div>
                  <div>
                    <dt>Coverage</dt>
                    <dd>How often the field appears in the current data sample.</dd>
                  </div>
                  <div>
                    <dt>Collect Options</dt>
                    <dd>Collects distinct values for select-style review inputs.</dd>
                  </div>
                  <div>
                    <dt>Cache media</dt>
                    <dd>Caches image/media URLs into the media library during processing.</dd>
                  </div>
                </dl>
              </div>

              <div v-if="integrations.length === 0" class="empty-state">
                No integrations configured yet.
              </div>
            </div>
          </div>

          <AdminStickySidebar
            class="manage-side"
            title="Integration Navigator"
            :count-label="`${manageNavigatorVisibleIds.length} visible`"
          >
            <div v-if="integrations.length > 0" class="manage-navigator-controls">
              <div class="form-group">
                <label for="container-tag-filter">Hierachy Tag</label>
                <select id="container-tag-filter" v-model="selectedContainerTag">
                  <option value="">All tags</option>
                  <option v-for="tag in availableContainerTags" :key="tag" :value="tag">
                    {{ tag }}
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label for="return-type-filter">Return Type</label>
                <select id="return-type-filter" v-model="selectedReturnType">
                  <option value="">All return types</option>
                  <option v-for="returnType in availableReturnTypes" :key="`return-type-${returnType}`" :value="returnType">
                    {{ returnType }}
                  </option>
                </select>
              </div>
            </div>
            <div v-if="integrations.length === 0" class="manage-navigator-empty">
              No integrations available yet.
            </div>
            <div v-else-if="manageNavigatorVisibleIds.length === 0" class="manage-navigator-empty">
              No filtered integrations to navigate.
            </div>
            <div v-else class="manage-navigator-list">
              <div
                v-for="section in manageNavigatorSections"
                :key="`navigator-section-${section.key}`"
                class="manage-navigator-section"
              >
                <div class="manage-navigator-section-title">{{ section.label }}</div>
                <div
                  v-for="group in section.groups"
                  :key="`navigator-group-${section.key}-${group.key}`"
                  class="manage-navigator-group"
                >
                  <div class="manage-navigator-group-title">{{ group.label }}</div>
                  <template
                    v-for="integration in group.items"
                    :key="`navigator-integration-${integration.id}`"
                  >
                    <button
                      type="button"
                      class="manage-navigator-item"
                      :class="{ active: isNavigatorItemActive(integration.id) }"
                      @click="openIntegrationFromNavigator(integration)"
                    >
                      <span class="manage-navigator-item-name">{{ integration.name }}</span>
                      <span class="manage-navigator-item-badges">
                        <span v-if="integration.favorite" class="navigator-badge navigator-badge--favorite" title="Favorite">
                          <font-awesome-icon :icon="faStar" />
                        </span>
                        <span v-if="section.key !== 'composable'" class="navigator-badge navigator-badge--type">{{ getIntegrationTypeLabel(integration) }}</span>
                        <span class="navigator-badge navigator-badge--return">{{ normalizeReturnType(integration.return_type) }}</span>
                      </span>
                    </button>
                    <div
                      v-if="isNavigatorItemActive(integration.id)"
                      class="manage-navigator-subsections"
                    >
                      <button
                        v-for="subsection in MANAGE_SUBSECTIONS"
                        :key="`navigator-subsection-${integration.id}-${subsection.key}`"
                        type="button"
                        class="manage-navigator-subsection"
                        :class="{ active: isManageSubsectionOpen(integration, subsection.key) }"
                        @click="openIntegrationSubsectionFromNavigator(integration, subsection.key)"
                      >
                        <font-awesome-icon :icon="subsection.icon" />
                        <span>{{ subsection.label }}</span>
                      </button>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </AdminStickySidebar>
        </div>
      </template>

      <template v-else-if="activeTab === 'review'">
        <div class="manage-layout review-page-layout">
          <div class="manage-main">
            <div class="review-integration-selection config-card">
              <div class="card-header">
                <h2>Review Integration Items</h2>
                <p class="card-hint">Compare fetched versions, manage local field overrides, and track review progress.</p>
              </div>

              <div class="review-toolbar">
                <div class="form-group review-select-group">
                  <label for="review_integration">Integration</label>
                  <select id="review_integration" v-model="reviewIntegrationId">
                    <option value="">-- Select integration --</option>
                    <optgroup
                      v-for="group in reviewIntegrationGroups"
                      :key="`review-integration-group-${group.key}`"
                      :label="group.label"
                    >
                      <option
                        v-for="integration in group.items"
                        :key="`review-integration-${integration.id}`"
                        :value="integration.id"
                      >
                        {{ integration.name }} ({{ normalizeReturnType(integration.return_type) }}, {{ integration.data_count || 0 }} items)
                      </option>
                    </optgroup>
                  </select>
                </div>
              </div>

              <div v-if="reviewStatus" class="health-result" :class="reviewStatus.type === 'error' ? 'error' : 'success'">
                {{ reviewStatus.message }}
              </div>

              <div v-if="!reviewIntegrationId" class="empty-state">
                Select an integration to review fetched items.
              </div>

              <template v-else>
                <div v-if="reviewItemsSummary" class="review-summary">
                  <span>Fetched: {{ reviewItemsSummary.fetched_at ? formatDateTime(reviewItemsSummary.fetched_at) : "Never" }}</span>
                  <span v-if="reviewItemsSummary.previous_fetched_at">Previous: {{ formatDateTime(reviewItemsSummary.previous_fetched_at) }}</span>
                  <span>{{ reviewItemsSummary.reviewable_item_count || 0 }} reviewable item(s)</span>
                  <span v-if="reviewItemsSummary.changed_count">Changed paths: {{ reviewItemsSummary.changed_count }}</span>
                  <span v-if="reviewItemsSummary.missing_key_count">Missing keys: {{ reviewItemsSummary.missing_key_count }}</span>
                </div>

                <div
                  v-if="reviewItemsSummary && reviewItemsSummary.requires_primary_key && !reviewItemsSummary.output_primary_key_path"
                  class="review-warning"
                >
                  Set an ID in Edit before editing list item overrides.
                </div>
              </template>

              <div v-if="reviewIntegrationId" class="review-sync-settings">
                <label
                  class="review-sync-toggle"
                  :class="{ disabled: reviewItemPageSyncSaving }"
                  title="Prevent integration review changes and generated page mapped-field edits from syncing item page content."
                >
                  <input
                    type="checkbox"
                    :checked="reviewItemPageSyncBlocked"
                    :disabled="reviewItemPageSyncSaving"
                    @change="setReviewItemPageSyncBlocked"
                  />
                  <span>Block item page syncing</span>
                </label>
              </div>
            </div>

            <div v-if="reviewItemsLoading" class="loading-state compact">Loading review items...</div>
            <div v-else class="config-card">
              <div v-if="reviewItemLoading" class="loading-state compact">Loading item...</div>
              <template v-else-if="reviewAddItemOpen && reviewCanAddItem">
                <form class="review-add-editor" @submit.prevent="createReviewItem">
                  <div class="review-detail-header">
                    <div>
                      <h3>Add Custom Item</h3>
                      <p class="card-hint">Local-only schema item</p>
                    </div>
                    <div class="review-detail-header-actions">
                      <button type="button" class="btn-outline btn-sm" @click="toggleReviewOutputColumns">
                        {{ reviewShowOutputColumns ? "Show Local Values" : "Show Type & Output" }}
                      </button>
                      <button
                        type="submit"
                        class="btn-primary btn-sm"
                        :disabled="reviewAddItemSaving || reviewAddItemMissingRequiredPaths.length > 0"
                      >
                        {{ reviewAddItemSaving ? "Saving..." : "Save Local Item" }}
                      </button>
                      <button type="button" class="btn-outline btn-sm" @click="cancelReviewAddItem">
                        Cancel
                      </button>
                    </div>
                  </div>

                  <div class="review-field-table-wrap">
                    <table class="review-field-table review-add-table">
                      <thead>
                        <tr>
                          <th>Field</th>
                          <th v-if="reviewShowOutputColumns">Type</th>
                          <th v-if="!reviewShowOutputColumns">Local Value</th>
                          <th v-if="reviewShowOutputColumns">Effective</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="field in reviewSchemaFields"
                          :key="`review-add-field-${field.path}`"
                        >
                          <td class="review-field-path">
                            <code>{{ field.path }}</code>
                            <div class="review-field-badges">
                              <span v-if="isReviewAddFieldMissingForSave(field)" class="review-badge incomplete">Missing item name</span>
                            </div>
                          </td>
                          <td v-if="reviewShowOutputColumns">{{ formatSchemaType(field.effective_type) }}</td>
                          <td v-if="!reviewShowOutputColumns">
                            <select
                              v-if="shouldUseReviewOptionsSelect(field)"
                              v-model="reviewAddItemDrafts[field.path]"
                              class="review-value-input"
                              :class="{ 'review-value-input--multi-select': shouldUseReviewMultipleOptionsSelect(field) }"
                              :multiple="shouldUseReviewMultipleOptionsSelect(field)"
                              :size="getReviewOptionsSelectSize(field)"
                            >
                              <option v-if="!shouldUseReviewMultipleOptionsSelect(field)" value="">Select option</option>
                              <option
                                v-for="option in getReviewFieldOptions(field)"
                                :key="option.key"
                                :value="option.value"
                              >
                                {{ option.label }}
                              </option>
                            </select>
                            <VueDatePicker
                              v-else-if="isReviewDateField(field)"
                              :model-value="getReviewAddDatePickerModel(field)"
                              class="review-datetime-picker"
                              :enable-time-picker="false"
                              :clearable="true"
                              :text-input="DATE_PICKER_DATE_ONLY_TEXT_INPUT_OPTIONS"
                              :formats="DATE_PICKER_DATE_ONLY_DISPLAY_FORMATS"
                              :teleport="true"
                              auto-apply
                              placeholder="Select date"
                              @update:model-value="setReviewAddDatePickerValue(field, $event)"
                            />
                            <VueDatePicker
                              v-else-if="isReviewDatetimeField(field)"
                              :model-value="getReviewAddDateTimePickerModel(field)"
                              class="review-datetime-picker"
                              :enable-time-picker="true"
                              :enable-seconds="reviewDateTimeUsesSeconds(field)"
                              :is-24="true"
                              :minutes-increment="getReviewDateTimeMinuteIncrement(field)"
                              :seconds-increment="1"
                              :clearable="true"
                              :text-input="DATE_PICKER_TEXT_INPUT_OPTIONS"
                              :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
                              :teleport="true"
                              auto-apply
                              placeholder="Select date & time"
                              @update:model-value="setReviewAddDateTimePickerValue(field, $event)"
                            />
                            <input
                              v-else-if="!shouldUseReviewAddTextarea(field) && getSchemaInputType(field) !== 'checkbox'"
                              v-model="reviewAddItemDrafts[field.path]"
                              class="review-value-input"
                              :type="getSchemaInputType(field)"
                              :placeholder="getReviewAddFieldPlaceholder(field)"
                            />
                            <label v-else-if="getSchemaInputType(field) === 'checkbox'" class="checkbox-item checkbox-item-compact">
                              <input v-model="reviewAddItemDrafts[field.path]" type="checkbox" />
                              <span>True</span>
                            </label>
                            <textarea
                              v-else
                              v-model="reviewAddItemDrafts[field.path]"
                              class="review-value-input"
                              :class="{ 'review-value-input--long-text': getSchemaFieldType(field) === 'text' }"
                              :rows="getReviewAddComparisonRows(field)"
                              :placeholder="getReviewAddFieldPlaceholder(field)"
                            ></textarea>
                            <div v-if="getReviewImagePreviewUrl(reviewAddItemDrafts[field.path], field.effective_type)" class="review-image-preview">
                              <img :src="getReviewImagePreviewUrl(reviewAddItemDrafts[field.path], field.effective_type)" alt="" />
                            </div>
                          </td>
                          <td v-if="reviewShowOutputColumns">
                            <textarea
                              class="review-value-input review-value-input--disabled"
                              :class="{ 'review-value-input--long-text': getSchemaFieldType(field) === 'text' }"
                              :rows="getReviewAddComparisonRows(field)"
                              :value="getReviewAddEffectiveDisplayValue(field)"
                              disabled
                            ></textarea>
                            <div v-if="getReviewImagePreviewUrl(reviewAddItemDrafts[field.path], field.effective_type)" class="review-image-preview">
                              <img :src="getReviewImagePreviewUrl(reviewAddItemDrafts[field.path], field.effective_type)" alt="" />
                            </div>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div class="form-actions">
                    <button
                      type="submit"
                      class="btn-primary"
                      :disabled="reviewAddItemSaving || reviewAddItemMissingRequiredPaths.length > 0"
                    >
                      {{ reviewAddItemSaving ? "Saving..." : "Save Local Item" }}
                    </button>
                    <button type="button" class="btn-outline" :disabled="reviewAddItemSaving" @click="cancelReviewAddItem">
                      Cancel
                    </button>
                  </div>
                  <p v-if="reviewAddItemMissingRequiredPaths.length" class="review-field-note">
                    Missing item name: {{ reviewAddItemMissingRequiredPaths.join(", ") }}
                  </p>
                </form>
              </template>
              <template v-else-if="reviewItemDetail">
                <div class="review-detail-header">
                  <div>
                    <h3>{{ reviewItemDetail.label || reviewItemDetail.item_key }}</h3>
                    <p class="card-hint">
                      Item key: <code>{{ reviewItemDetail.item_key }}</code>
                      <span v-if="reviewItemDetail.is_incomplete" class="review-badge incomplete">Incomplete</span>
                    </p>
                    <div
                      v-if="getReviewItemGeneratedPages(reviewItemDetail).length"
                      class="review-generated-pages"
                    >
                      <span
                        v-for="(page, pageIndex) in getReviewItemGeneratedPages(reviewItemDetail)"
                        :key="`review-detail-page-${page.template_key || page.template_label || 'template'}-${page.slug || 'missing'}-${pageIndex}`"
                        class="review-generated-page-entry"
                      >
                        <span
                          class="review-generated-page-chip"
                          :class="getReviewGeneratedPageBadgeClass(page)"
                          :title="getReviewGeneratedPageTitle(page)"
                        >
                          <code v-if="canOpenReviewGeneratedPage(page)" class="review-generated-page-route">
                            {{ formatReviewGeneratedPageRoute(page) }}
                          </code>
                          <span v-else class="review-generated-page-status">
                            No page
                          </span>
                        </span>
                        <button
                          v-if="canOpenReviewGeneratedPage(page)"
                          type="button"
                          class="review-generated-page-open"
                          :title="`Open item page ${formatReviewGeneratedPageRoute(page)}`"
                          @click.stop="openReviewGeneratedPage(page)"
                        >
                          <font-awesome-icon :icon="faArrowUpRightFromSquare" />
                          <span>Open</span>
                        </button>
                      </span>
                    </div>
                  </div>
                  <div class="review-detail-header-actions">
                    <button type="button" class="btn-outline btn-sm" @click="reloadReviewItem">
                      Refresh
                    </button>
                    <button type="button" class="btn-primary btn-sm" @click="toggleReviewOutputColumns">
                      {{ reviewShowOutputColumns ? "Show Override" : "Show Output" }}
                    </button>
                  </div>
                </div>

                <div class="review-meta-panel">
                  <div class="form-group">
                    <label>Review State</label>
                    <select
                      :value="reviewItemDetail.state || 'open'"
                      :disabled="reviewMetaSaving"
                      @change="setReviewItemState($event.target.value)"
                    >
                      <option value="open">Open</option>
                      <option value="in_progress">In progress</option>
                      <option value="done">Done</option>
                    </select>
                  </div>
                  <div class="form-group review-tags-group">
                    <label>Tags</label>
                    <div class="review-tag-editor">
                      <span v-for="tag in reviewItemDetail.tags || []" :key="`review-detail-tag-${tag}`" class="review-tag editable">
                        {{ tag }}
                        <button type="button" :disabled="reviewMetaSaving" @click="removeReviewItemTag(tag)" title="Remove tag">
                          <font-awesome-icon :icon="faXmark" />
                        </button>
                      </span>
                      <input
                        v-model="reviewTagDraft"
                        type="text"
                        placeholder="Add tag"
                        :disabled="reviewMetaSaving"
                        @keydown.enter.prevent="addReviewItemTag"
                      />
                      <button type="button" class="btn-outline btn-sm" :disabled="reviewMetaSaving || !reviewTagDraft.trim()" @click="addReviewItemTag">
                        Add
                      </button>
                    </div>
                  </div>
                </div>

                <div class="review-field-table-wrap">
                  <table class="review-field-table">
                    <thead>
                      <tr>
                        <th>Field</th>
                        <th v-if="reviewShowOutputColumns">Type</th>
                        <th v-if="reviewHasPreviousFetchedDifferences">Previous Fetched</th>
                        <th v-if="reviewHasCurrentFetchedDifferences">Current Fetched</th>
                        <th v-if="!reviewShowOutputColumns">Local Override</th>
                        <th v-if="reviewShowOutputColumns">Effective</th>
                        <th v-if="!reviewShowOutputColumns">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="field in reviewItemFields"
                        :key="`review-field-${field.path}`"
                        :class="{ conflict: field.has_conflict, changed: isReviewFieldSourceChanged(field) }"
                      >
                        <td class="review-field-path">
                          <code>{{ field.path }}</code>
                          <div class="review-field-badges">
                            <span v-if="isReviewFieldSourceChanged(field)" class="review-badge changed">Changed</span>
                            <span v-if="field.missing_required" class="review-badge incomplete">Missing required</span>
                            <span v-if="field.has_conflict" class="review-badge conflict">Conflict</span>
                          </div>
                        </td>
                        <td v-if="reviewShowOutputColumns">{{ formatSchemaType(field.schema_type) }}</td>
                        <td v-if="reviewHasPreviousFetchedDifferences">
                          <template v-if="!isReviewPreviousMuted(field)">
                            <textarea
                              class="review-value-input review-value-input--disabled"
                              :class="{ 'review-value-input--long-text': isReviewLongTextField(field) }"
                              :rows="getReviewComparisonRows(field)"
                              :value="getReviewDisplayValue(field, 'previous')"
                              disabled
                            ></textarea>
                            <div v-if="getReviewImagePreviewUrl(field.previous_value, field.schema_type)" class="review-image-preview">
                              <img :src="getReviewImagePreviewUrl(field.previous_value, field.schema_type)" alt="" />
                            </div>
                          </template>
                        </td>
                        <td v-if="reviewHasCurrentFetchedDifferences">
                          <template v-if="!isReviewCurrentMuted(field)">
                            <textarea
                              class="review-value-input review-value-input--disabled"
                              :class="{ 'review-value-input--long-text': isReviewLongTextField(field) }"
                              :rows="getReviewComparisonRows(field)"
                              :value="getReviewDisplayValue(field, 'current')"
                              disabled
                            ></textarea>
                            <div v-if="getReviewImagePreviewUrl(field.current_value, field.schema_type)" class="review-image-preview">
                              <img :src="getReviewImagePreviewUrl(field.current_value, field.schema_type)" alt="" />
                            </div>
                          </template>
                        </td>
                        <td v-if="!reviewShowOutputColumns">
                          <select
                            v-if="shouldUseReviewOptionsSelect(field)"
                            v-model="reviewFieldDrafts[field.path]"
                            class="review-value-input"
                            :class="{
                              'review-value-input--multi-select': shouldUseReviewMultipleOptionsSelect(field),
                              'review-value-input--warning': isReviewLocalDifferentFromCurrent(field)
                            }"
                            :multiple="shouldUseReviewMultipleOptionsSelect(field)"
                            :size="getReviewOptionsSelectSize(field)"
                          >
                            <option v-if="!shouldUseReviewMultipleOptionsSelect(field)" value="">No local override</option>
                            <option
                              v-for="option in getReviewFieldOptions(field)"
                              :key="option.key"
                              :value="option.value"
                            >
                              {{ option.label }}
                            </option>
                          </select>
                          <VueDatePicker
                            v-else-if="isReviewDateField(field)"
                            :model-value="getReviewDatePickerModel(field)"
                            class="review-datetime-picker"
                            :class="{ 'review-value-input--warning': isReviewLocalDifferentFromCurrent(field) }"
                            :enable-time-picker="false"
                            :clearable="true"
                            :text-input="DATE_PICKER_DATE_ONLY_TEXT_INPUT_OPTIONS"
                            :formats="DATE_PICKER_DATE_ONLY_DISPLAY_FORMATS"
                            :teleport="true"
                            auto-apply
                            placeholder="No local override"
                            @update:model-value="setReviewDatePickerValue(field, $event)"
                          />
                          <VueDatePicker
                            v-else-if="isReviewDatetimeField(field)"
                            :model-value="getReviewDateTimePickerModel(field)"
                            class="review-datetime-picker"
                            :class="{ 'review-value-input--warning': isReviewLocalDifferentFromCurrent(field) }"
                            :enable-time-picker="true"
                            :enable-seconds="reviewDateTimeUsesSeconds(field)"
                            :is-24="true"
                            :minutes-increment="getReviewDateTimeMinuteIncrement(field)"
                            :seconds-increment="1"
                            :clearable="true"
                            :text-input="DATE_PICKER_TEXT_INPUT_OPTIONS"
                            :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
                            :teleport="true"
                            auto-apply
                            placeholder="No local override"
                            @update:model-value="setReviewDateTimePickerValue(field, $event)"
                          />
                          <div
                            v-else-if="isReviewImageField(field)"
                            class="review-image-picker-field"
                            :class="{ 'review-value-input--warning': isReviewLocalDifferentFromCurrent(field) }"
                          >
                            <div v-if="reviewFieldDrafts[field.path]" class="review-image-picker-url" :title="reviewFieldDrafts[field.path]">
                              {{ reviewFieldDrafts[field.path] }}
                            </div>
                            <div v-else class="review-image-picker-empty">No local override</div>
                            <div class="review-image-picker-preview-row">
                              <div v-if="getReviewImagePreviewUrl(reviewFieldDrafts[field.path], field.schema_type)" class="review-image-preview review-image-picker-preview">
                                <img :src="getReviewImagePreviewUrl(reviewFieldDrafts[field.path], field.schema_type)" alt="" />
                              </div>
                              <div v-else class="review-image-picker-preview-placeholder">
                                No preview
                              </div>
                              <button
                                type="button"
                                class="review-image-picker-button"
                                :disabled="reviewFieldSaving[field.path]"
                                @click="openReviewImagePicker(field)"
                              >
                                <font-awesome-icon :icon="faImage" />
                                <span>{{ reviewFieldDrafts[field.path] ? "Replace media" : "Select media" }}</span>
                              </button>
                            </div>
                          </div>
                          <textarea
                            v-else
                            v-model="reviewFieldDrafts[field.path]"
                            class="review-value-input"
                            :class="{
                              'review-value-input--long-text': isReviewLongTextField(field),
                              'review-value-input--warning': isReviewLocalDifferentFromCurrent(field)
                            }"
                            :rows="getReviewComparisonRows(field)"
                            :placeholder="field.has_override ? '' : 'No local override'"
                          ></textarea>
                          <div v-if="!isReviewImageField(field) && getReviewImagePreviewUrl(reviewFieldDrafts[field.path], field.schema_type)" class="review-image-preview">
                            <img :src="getReviewImagePreviewUrl(reviewFieldDrafts[field.path], field.schema_type)" alt="" />
                          </div>
                          <div v-if="field.override_updated_at" class="review-field-note">
                            Saved {{ formatDateTime(field.override_updated_at) }}
                          </div>
                          <details v-if="field.history?.length" class="review-history">
                            <summary>History ({{ field.history.length }})</summary>
                            <pre>{{ JSON.stringify(field.history, null, 2) }}</pre>
                          </details>
                        </td>
                        <td v-if="reviewShowOutputColumns">
                          <textarea
                            class="review-value-input review-value-input--disabled"
                            :class="{ 'review-value-input--long-text': isReviewLongTextField(field) }"
                            :rows="getReviewComparisonRows(field)"
                            :value="getReviewDisplayValue(field, 'effective')"
                            disabled
                          ></textarea>
                          <div v-if="getReviewImagePreviewUrl(field.effective_value, field.schema_type)" class="review-image-preview">
                            <img :src="getReviewImagePreviewUrl(field.effective_value, field.schema_type)" alt="" />
                          </div>
                        </td>
                        <td v-if="!reviewShowOutputColumns" class="review-actions-cell">
                          <button
                            type="button"
                            :class="[isReviewFieldDraftChanged(field) ? 'btn-primary' : 'btn-outline', 'btn-sm']"
                            :disabled="reviewFieldSaving[field.path] || !isReviewFieldDraftChanged(field)"
                            @click="saveReviewField(field)"
                          >
                            Save
                          </button>
                          <button
                            type="button"
                            :class="[field.has_override ? 'btn-danger' : 'btn-outline danger', 'btn-sm']"
                            :disabled="reviewFieldSaving[field.path] || !field.has_override"
                            @click="clearReviewField(field)"
                          >
                            Clear
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <MediaLibrary
                  :is-open="Boolean(reviewImagePickerFieldPath)"
                  :current-url="reviewImagePickerCurrentUrl"
                  source-context="admin.integration_review.image"
                  :allow-clear-selection="true"
                  @close="closeReviewImagePicker"
                  @select="onReviewImagePickerSelect"
                />
              </template>
              <div v-else class="empty-state">
                Select an item from the list to review field values.
              </div>
            </div>
          </div>

          <AdminStickySidebar
            class="manage-side review-item-panel"
            title="Item Navigator"
            :count-label="reviewAddItemOpen ? 'Adding item' : `${filteredReviewItems.length} visible`"
            aria-label="Integration items"
          >
            <template v-if="reviewIntegrationId && !reviewItemsLoading">
              <div class="review-sidebar-controls">
                <div class="review-item-search-row">
                  <input
                    v-model="reviewItemSearchQuery"
                    type="text"
                    class="review-item-search-input"
                    placeholder="Search item name..."
                    aria-label="Search review items by name"
                  />
                  <button
                    v-if="reviewItemSearchQuery"
                    type="button"
                    class="review-item-search-clear"
                    aria-label="Clear item search"
                    @click="reviewItemSearchQuery = ''"
                  >
                    Clear
                  </button>
                </div>
                <div class="review-filters">
                  <div class="form-group">
                    <label>State</label>
                    <select v-model="reviewStateFilter" @change="loadReviewItems({ preserveSelection: false })">
                      <option value="">All states</option>
                      <option value="open">Open ({{ reviewStateCounts.open || 0 }})</option>
                      <option value="in_progress">In progress ({{ reviewStateCounts.in_progress || 0 }})</option>
                      <option value="done">Done ({{ reviewStateCounts.done || 0 }})</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label>Tag</label>
                    <select v-model="reviewTagFilter" @change="loadReviewItems({ preserveSelection: false })">
                      <option value="">All tags</option>
                      <optgroup label="Badges">
                        <option
                          v-for="badgeFilter in REVIEW_BADGE_TAG_FILTERS"
                          :key="`review-filter-badge-${badgeFilter.value}`"
                          :value="badgeFilter.value"
                        >
                          {{ badgeFilter.label }}
                        </option>
                      </optgroup>
                      <optgroup v-if="reviewAvailablePageStateFilterOptions.length" label="Page State">
                        <option
                          v-for="pageFilter in reviewAvailablePageStateFilterOptions"
                          :key="`review-filter-page-${pageFilter.value}`"
                          :value="pageFilter.value"
                        >
                          {{ formatReviewFilterOptionLabel(pageFilter) }}
                        </option>
                      </optgroup>
                      <optgroup v-if="reviewAvailableTagOptions.length" label="Tags">
                        <option
                          v-for="tag in reviewAvailableTagOptions"
                          :key="`review-filter-tag-${tag}`"
                          :value="tag"
                        >
                          {{ tag }}
                        </option>
                      </optgroup>
                    </select>
                  </div>
                </div>

                <div>
                  <button
                    type="button"
                    class="btn-primary btn-sm add-item"
                    :disabled="!reviewCanAddItem"
                    @click="toggleReviewAddItem"
                  >
                    {{ reviewAddItemOpen ? "Close Add Item" : "Add Item" }}
                  </button>
                  <p v-if="!reviewCanAddItem" class="form-hint">
                    Detect a schema and configure an ID before adding local items.
                  </p>
                </div>
              </div>

              <div v-if="reviewAddItemOpen" class="manage-navigator-empty">
                Close Add Item to browse existing items.
              </div>
              <div v-else-if="reviewItems.length === 0" class="manage-navigator-empty">
                No reviewable items match the current filters.
              </div>
              <div v-else-if="filteredReviewItems.length === 0" class="manage-navigator-empty">
                No items match the current search.
              </div>
              <div v-else class="review-item-list">
                <button
                  v-for="item in filteredReviewItems"
                  :key="`review-item-${item.item_key}`"
                  type="button"
                  class="review-item-button"
                  :class="{ active: !reviewAddItemOpen && item.item_key === reviewSelectedItemKey }"
                  @click.stop.prevent="selectReviewItem(item.item_key)"
                >
                  <span class="review-item-title">{{ item.label || item.item_key }}</span>
                  <span class="review-item-meta">
                    <span class="review-badge state">{{ formatReviewState(item.state) }}</span>
                    <span v-if="item.is_local_item" class="review-badge local">Local</span>
                    <span v-if="item.is_incomplete" class="review-badge incomplete">Incomplete</span>
                    <span v-if="item.source_changed" class="review-badge changed">Changed</span>
                    <span v-if="item.has_override" class="review-badge override">Override</span>
                    <span v-if="item.has_conflict" class="review-badge conflict">Conflict</span>
                    <span
                      v-for="(page, pageIndex) in getReviewItemGeneratedPages(item)"
                      :key="`review-item-${item.item_key}-page-${page.template_key || page.template_label || 'template'}-${page.slug || 'missing'}-${pageIndex}`"
                      class="review-badge page"
                      :class="getReviewGeneratedPageBadgeClass(page)"
                      :title="getReviewGeneratedPageTitle(page)"
                    >
                      {{ formatReviewGeneratedPageBadge(page) }}
                    </span>
                  </span>
                  <span v-if="item.tags?.length" class="review-tag-row">
                    <span v-for="tag in item.tags" :key="`review-item-${item.item_key}-tag-${tag}`" class="review-tag">{{ tag }}</span>
                  </span>
                </button>
              </div>
            </template>
            <div v-else-if="reviewIntegrationId" class="manage-navigator-empty">
              Loading review items...
            </div>
            <div v-else class="manage-navigator-empty">
              Select an integration to show review items.
            </div>
          </AdminStickySidebar>
        </div>
      </template>

      <template v-else-if="activeTab === 'compose'">
        <div class="config-card">
          <div class="card-header">
            <h2>Compose Integrations</h2>
            <p class="card-hint">Combine multiple existing integrations into one merged result list.</p>
          </div>

          <form class="integration-form" @submit.prevent="saveContainerIntegration">
            <div class="form-row">
              <div class="form-group">
                <label for="container_name">Composable Name *</label>
                <input
                  id="container_name"
                  v-model="containerForm.name"
                  type="text"
                  placeholder="e.g., Unified Program Feed"
                  required
                />
              </div>
            </div>

            <div class="form-row">
              <div class="form-group form-group-full">
                <label for="container_description">Description (optional)</label>
                <textarea
                  id="container_description"
                  v-model="containerForm.description"
                  rows="2"
                  placeholder="Describe what this container composition is doing."
                ></textarea>
              </div>
            </div>

            <div class="transform-editor">
              <div class="transform-editor-header">
                <h3>Sources</h3>
              </div>
              <p class="card-hint integration-case-hint">
                {{ INTEGRATION_PATH_RULE_HINT }} {{ INTEGRATION_TARGET_RULE_HINT }}
              </p>
              <p class="card-hint">
                Without target source, lists are concatenated. Set a target directly on a source row to merge non-target sources into it.
              </p>
              <div v-if="containerForm.target_source_integration_id" class="target-chip-row">
                <span class="container-tag target-pill">
                  Target: {{ getIntegrationDisplayName(containerForm.target_source_integration_id) }}
                </span>
              </div>

              <draggable
                v-model="containerForm.sources"
                item-key="ui_id"
                class="transform-step-list"
                handle=".drag-handle"
                ghost-class="transform-step--dragging"
                chosen-class="transform-step--dragging"
                :animation="150"
              >
                <template #item="{ element: source, index }">
                <div
                  class="transform-step"
                  :class="{
                    'target-source-step': isTargetSource(source, containerForm.target_source_integration_id),
                  }"
                >
                  <div class="transform-step-head">
                    <div class="transform-step-title">
                      <button
                        type="button"
                        class="drag-handle"
                        title="Drag source"
                        aria-label="Drag source"
                      >
                        <font-awesome-icon :icon="faGripVertical" />
                      </button>
                      <button
                        type="button"
                        class="transform-step-collapse"
                        :title="source.collapsed ? 'Expand source' : 'Collapse source'"
                        :aria-label="source.collapsed ? 'Expand source' : 'Collapse source'"
                        @click="source.collapsed = !source.collapsed"
                      >
                        <font-awesome-icon :icon="source.collapsed ? faChevronRight : faChevronDown" />
                      </button>
                      <span class="step-index">
                        {{ getContainerSourceRowLabel(source, index) }}
                        <span
                          v-if="isTargetSource(source, containerForm.target_source_integration_id)"
                          class="container-tag target-pill"
                        >
                          Target
                        </span>
                      </span>
                    </div>
                    <div class="transform-step-actions">
                      <button
                        type="button"
                        class="btn-outline btn-sm"
                        :class="{ active: isTargetSource(source, containerForm.target_source_integration_id) }"
                        :disabled="!source.integration_id"
                        @click="toggleContainerTargetSource(source)"
                      >
                        {{ isTargetSource(source, containerForm.target_source_integration_id) ? "Target" : "Set Target" }}
                      </button>
                      <button
                        type="button"
                        class="btn-outline btn-sm"
                        :disabled="!source.integration_id"
                        @click="previewSourceIntegration(source.integration_id)"
                      >
                        Preview
                      </button>
                      <button type="button" class="btn-outline btn-sm danger" :disabled="containerForm.sources.length <= 2" @click="removeContainerSource(index)">Remove</button>
                    </div>
                  </div>
                  <div v-show="!source.collapsed" class="transform-step-body">
                  <div class="form-row">
                    <div class="form-group form-group-full">
                      <label>Integration</label>
                      <select
                        v-model="source.integration_id"
                        required
                      >
                        <option value="">-- Select integration --</option>
                        <option v-for="candidate in containerSourceOptions" :key="candidate.id" :value="candidate.id">
                          {{ candidate.name }}
                        </option>
                      </select>
                    </div>
                  </div>
                  <div
                    v-if="containerForm.target_source_integration_id && source.integration_id !== containerForm.target_source_integration_id"
                    class="form-row key-path-row"
                  >
                    <div
                      class="form-group"
                    >
                      <label>Target Key</label>
                      <select v-model="source.target_key_path">
                        <option value="">-- Select Target Key --</option>
                        <option
                          v-for="field in getIntegrationPrimeKeyOptionsWithCurrent(containerForm.target_source_integration_id, source.target_key_path)"
                          :key="`container-target-primekey-${source.ui_id}-${field}`"
                          :value="field"
                        >
                          {{ field }}
                        </option>
                      </select>
                      <span class="form-hint" v-if="isIntegrationPrimeKeyOptionsLoading(containerForm.target_source_integration_id)">
                        Loading target fields...
                      </span>
                      <span class="form-hint" v-else-if="getIntegrationPrimeKeyOptionsWithCurrent(containerForm.target_source_integration_id, source.target_key_path).length === 0">
                        No target keys available. Fetch/process the target integration first.
                      </span>
                    </div>
                    <div
                      class="form-group"
                    >
                      <label>Source Key</label>
                      <select v-model="source.source_key_path">
                        <option value="">-- Select Source Key --</option>
                        <option
                          v-for="field in getIntegrationPrimeKeyOptionsWithCurrent(source.integration_id, source.source_key_path)"
                          :key="`container-source-primekey-${source.ui_id}-${field}`"
                          :value="field"
                        >
                          {{ field }}
                        </option>
                      </select>
                      <span class="form-hint" v-if="isIntegrationPrimeKeyOptionsLoading(source.integration_id)">
                        Loading source fields...
                      </span>
                      <span class="form-hint" v-else-if="getIntegrationPrimeKeyOptionsWithCurrent(source.integration_id, source.source_key_path).length === 0">
                        No source keys available. Fetch/process the source integration first.
                      </span>
                    </div>
                  </div>
                  <div
                    v-if="containerForm.target_source_integration_id && source.integration_id !== containerForm.target_source_integration_id"
                    class="form-row"
                  >
                    <div
                      class="form-group"
                    >
                      <label>Merge Style</label>
                      <select v-model="source.merge_style">
                        <option value="flat">Flat (top-level fields)</option>
                        <option value="nested">Nested Object (replaces target key)</option>
                      </select>
                      <span class="form-hint">Applies when this source is merged into the selected target source.</span>
                    </div>
                    <div
                      class="form-group"
                      v-if="containerForm.target_source_integration_id && source.integration_id !== containerForm.target_source_integration_id"
                    >
                      <label class="checkbox-item">
                        <input v-model="source.keep_target_key" type="checkbox" />
                        <span>Keep Target Key</span>
                      </label>
                      <span class="form-hint">
                        Keeps the target key value as <code>&lt;key&gt;_target</code> before flat or nested merge.
                      </span>
                    </div>
                    <div
                      class="form-group"
                      v-if="containerForm.target_source_integration_id && source.integration_id !== containerForm.target_source_integration_id && source.merge_style === 'nested'"
                    >
                      <label>Nested Key</label>
                      <input
                        v-model="source.nested_key"
                        type="text"
                        placeholder="e.g., answer_data"
                      />
                    </div>
                  </div>
                  </div>
                </div>
                </template>
              </draggable>
              <div class="form-actions">
                <button type="button" class="btn-outline btn-sm" @click="addContainerSource">Add Source</button>
                <button
                  type="button"
                  class="btn-outline btn-sm"
                  :disabled="!containerForm.target_source_integration_id"
                  @click="clearContainerTargetSource"
                >
                  Clear Target
                </button>
              </div>
            </div>

            <TransformStepsEditor
              v-model="containerForm.transform_steps"
              :path-rule-hint="INTEGRATION_PATH_RULE_HINT"
              :target-rule-hint="INTEGRATION_TARGET_RULE_HINT"
            />

            <div class="form-actions">
              <button type="submit" class="btn-primary" :disabled="saving">
                {{ saving ? "Saving..." : "Create Composable" }}
              </button>
            </div>
          </form>
        </div>
      </template>

      <template v-else>
        <div class="connection-card-stack">
          <div class="config-card">
            <div class="card-header">
              <h2>Global Integration Exposure</h2>
              <p class="card-hint">
                Global exposure makes selected integrations available to admin workflows. Template rules can
                further narrow which templates may use them and which return shape they expect.
              </p>
            </div>

            <div class="connection-card-body">
              <div v-if="connectionIntegrations.length === 0" class="empty-state compact">
                No integrations available to expose yet.
              </div>
              <div v-else class="admin-list-tabs connection-exposure-groups">
                <section
                  v-for="group in connectionIntegrationGroups"
                  :key="`global-map-group-${group.key}`"
                  class="admin-list-tabs__group"
                >
                  <div class="admin-list-tabs__heading">
                    <span class="admin-list-tabs__heading-main">
                      <font-awesome-icon
                        class="admin-list-tabs__icon"
                        :icon="group.icon"
                        aria-hidden="true"
                      />
                      <span class="admin-list-tabs__heading-label">{{ group.label }}</span>
                    </span>
                    <span class="admin-list-tabs__count">{{ group.items.length }}</span>
                  </div>
                  <div class="admin-list-tabs__items">
                    <label
                      v-for="integration in group.items"
                      :key="`global-map-${integration.id}`"
                      class="admin-list-tabs__item connection-exposure-row"
                    >
                      <input
                        type="checkbox"
                        :checked="isIntegrationExposed(integration.id)"
                        @change="setIntegrationExposed(integration.id, $event.target.checked)"
                      />
                      <span class="admin-list-tabs__item-main">
                        <span class="admin-list-tabs__item-name">{{ integration.name }}</span>
                      </span>
                    </label>
                  </div>
                </section>
              </div>
              <div class="form-actions">
                <button
                  type="button"
                  class="btn-outline btn-sm"
                  @click="setAllIntegrationExposure(true)"
                >
                  Select All
                </button>
                <button
                  type="button"
                  class="btn-outline btn-sm"
                  @click="setAllIntegrationExposure(false)"
                >
                  Clear All
                </button>
              </div>
            </div>
          </div>

          <div class="config-card">
            <div class="card-header">
              <h2>Template Rules</h2>
              <p class="card-hint">
                Visibility controls whether a template can use no integrations, only template-specific mappings, or
                all globally exposed integrations. Expected format limits choices to integrations returning a list or
                a single object; auto keeps the template's default behavior.
              </p>
            </div>

            <div class="connection-card-body">
              <div class="connection-filter-row">
                <label class="template-return-select stacked">
                  <span>Visibility filter</span>
                  <select v-model="connectionVisibilityFilter">
                    <option
                      v-for="option in connectionVisibilityFilterOptions"
                      :key="`visibility-filter-${option.value}`"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                </label>
              </div>

              <div v-if="connectionTemplatesLoading" class="empty-state compact">
                Loading templates...
              </div>
              <div v-else-if="connectionRuleGroups.length === 0" class="empty-state compact">
                No templates found.
              </div>
              <div v-else-if="filteredConnectionRuleGroups.length === 0" class="empty-state compact">
                No templates match the selected visibility.
              </div>
              <div v-else class="admin-list-tabs connection-sections">
                <section
                  v-for="group in filteredConnectionRuleGroups"
                  :key="`template-group-${group.key}`"
                  class="admin-list-tabs__group"
                >
                  <div class="admin-list-tabs__heading">
                    <span class="admin-list-tabs__heading-main">
                      <font-awesome-icon
                        v-if="group.sectionType"
                        class="admin-list-tabs__icon"
                        :icon="getConnectionSectionTypeIcon(group.sectionType)"
                        aria-hidden="true"
                      />
                      <span class="admin-list-tabs__heading-label">{{ group.label }}</span>
                    </span>
                    <span class="admin-list-tabs__count">{{ group.templates.length }}</span>
                  </div>

                  <div class="admin-list-tabs__items connection-mapping-panel">
                    <div
                      v-for="template in group.templates"
                      :key="`template-row-${template.key}`"
                      class="admin-list-tabs__item admin-list-tabs__item--static connection-template-row"
                      :class="{ muted: !isTemplateIntegrationsEnabled(template.key) }"
                    >
                      <div class="admin-list-tabs__item-body connection-template-main">
                        <div class="connection-template-title">
                          <strong class="admin-list-tabs__item-name connection-template-name">{{ template.displayName }}</strong>
                          <span v-if="template.contextLabel" class="form-hint">{{ template.contextLabel }}</span>
                        </div>
                        <div class="connection-template-controls">
                          <label class="template-return-select stacked">
                            <span>Visibility</span>
                            <select
                              :value="getTemplateIntegrationVisibility(template.key)"
                              @change="setTemplateIntegrationVisibility(template.key, $event.target.value)"
                            >
                              <option
                                v-for="option in templateVisibilityOptions(template.key)"
                                :key="`template-visibility-${template.key}-${option.value}`"
                                :value="option.value"
                              >
                                {{ option.label }}
                              </option>
                            </select>
                          </label>
                          <label class="template-return-select stacked">
                            <span>Expected format</span>
                            <select
                              :value="getTemplateExpectedReturnType(template.key)"
                              @change="setTemplateExpectedReturnType(template.key, $event.target.value)"
                            >
                              <option value="auto">auto</option>
                              <option value="list">list</option>
                              <option value="object">object</option>
                            </select>
                          </label>
                        </div>
                        <div class="integration-buttons connection-template-actions">
                          <a
                            v-if="template.href"
                            class="btn-outline btn-sm"
                            :href="template.href"
                            target="_blank"
                            rel="noopener"
                          >
                            Open Template
                          </a>
                          <button
                            type="button"
                            class="btn-outline btn-sm"
                            @click="resetTemplateRule(template.key)"
                          >
                            Reset
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>
              </div>
            </div>
          </div>
        </div>
      </template>
    </template>

    <Teleport to="body">
      <div v-if="deleteConfirm" class="modal-overlay" @click.self="deleteConfirm = null">
        <div class="modal-dialog">
          <h3>Delete Integration</h3>
          <p>Are you sure you want to delete "{{ deleteConfirm.name }}"? This will also delete all fetched data.</p>
          <div class="modal-actions">
            <button class="btn-outline" @click="deleteConfirm = null">Cancel</button>
            <button class="btn-danger" @click="doDelete" :disabled="deleting">
              {{ deleting ? "Deleting..." : "Delete" }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="previewData" class="modal-overlay" @click.self="closePreview">
        <div class="modal-dialog modal-large">
          <div class="modal-header">
            <h3>Data Preview</h3>
            <button class="btn-icon" @click="closePreview">
              <font-awesome-icon :icon="faXmark" />
            </button>
          </div>
          <div class="preview-info">
            <span>Total items: {{ previewData.total_items }}</span>
            <span v-if="previewItemsTruncated">Showing first {{ previewItems.length }} items (max {{ PREVIEW_ITEM_LIMIT }}).</span>
            <span v-if="previewData.fetched_at">Fetched: {{ formatDateTime(previewData.fetched_at) }}</span>
            <span>ID: {{ previewData.output_primary_key_path_resolved || "-" }}</span>
          </div>
          <div v-if="previewItemOptions.length > 0" class="preview-selector">
            <select id="preview-item-select" v-model="previewSelectedItemIndex">
              <option
                v-for="option in previewItemOptions"
                :key="option.key"
                :value="option.index"
              >
                {{ option.label }}
              </option>
            </select>
          </div>
          <div class="preview-tabs">
            <button
              type="button"
              class="btn-outline btn-sm"
              :class="{ active: previewActiveTab === 'item' }"
              @click="previewActiveTab = 'item'"
            >
              <font-awesome-icon :icon="faFileLines" />
              <span>Item Preview</span>
            </button>
            <button
              v-if="previewMetadata"
              type="button"
              class="btn-outline btn-sm"
              :class="{ active: previewActiveTab === 'meta' }"
              @click="previewActiveTab = 'meta'"
            >
              <font-awesome-icon :icon="faFileLines" />
              <span>Meta Preview</span>
            </button>
          </div>
          <div class="preview-content">
            <pre>{{ JSON.stringify(previewActiveTab === 'meta' ? previewMetadata : previewSelectedItem, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  faAlignLeft,
  faArrowUpRightFromSquare,
  faBullhorn,
  faCalendarDays,
  faChevronDown,
  faChevronRight,
  faCircleQuestion,
  faClone,
  faCode,
  faFileLines,
  faGear,
  faGripVertical,
  faImage,
  faImages,
  faNewspaper,
  faShareNodes,
  faStar,
  faTableCellsLarge,
  faTrashCan,
  faVideo,
  faXmark,
} from "@fortawesome/free-solid-svg-icons";
import { VueDatePicker } from "@vuepic/vue-datepicker";
import draggable from "vuedraggable";
import AdminPageTabs from "../../components/admin/AdminPageTabs.vue";
import AdminStickySidebar from "../../components/admin/AdminStickySidebar.vue";
import AutosaveToast from "../../components/admin/AutosaveToast.vue";
import TransformStepsEditor from "../../components/admin/integrations/TransformStepsEditor.vue";
import MediaLibrary from "../../components/ui/MediaLibrary.vue";
import * as api from "../../services/api.js";
import { toSnakeCase } from "../../utils/caseConversion.js";
import {
  DATE_PICKER_DATE_ONLY_DISPLAY_FORMATS,
  DATE_PICKER_DATE_ONLY_TEXT_INPUT_OPTIONS,
  DATE_PICKER_DATE_TIME_DISPLAY_FORMATS,
  DATE_PICKER_TEXT_INPUT_OPTIONS,
  formatInstantInServerTimezone,
  localDateToServerDateOnly,
  serverDateOnlyToLocalDate,
} from "../../utils/revisionTime.js";
import "@vuepic/vue-datepicker/dist/main.css";

const route = useRoute();
const router = useRouter();
const tabs = [
  { id: "create", label: "Base", to: "/admin/integrations/base" },
  { id: "compose", label: "Compose", to: "/admin/integrations/compose" },
  { id: "manage", label: "Edit", to: "/admin/integrations/edit" },
  { id: "review", label: "Review", to: "/admin/integrations/review" },
  { id: "connection", label: "Expose", to: "/admin/integrations/expose" },
];
const INTEGRATION_TAB_BY_SLUG = {
  base: "create",
  compose: "compose",
  composable: "compose",
  manage: "manage",
  edit: "manage",
  review: "review",
  expose: "connection",
  export: "connection",
  connect: "connection",
};
const MANAGE_SUBSECTIONS = [
  { key: "config", label: "Config", icon: faGear },
  { key: "transform", label: "Transformation", icon: faCode },
  { key: "schema", label: "Schema", icon: faTableCellsLarge },
];
const MANAGE_SUBSECTION_KEYS = new Set(MANAGE_SUBSECTIONS.map((subsection) => subsection.key));
const REVIEW_BADGE_TAG_FILTERS = [
  { value: "__badge:local", label: "Local" },
  { value: "__badge:incomplete", label: "Incomplete" },
  { value: "__badge:override", label: "Override" },
];
const TEMPLATE_VISIBILITY_FILTER_OPTIONS = [
  { value: "enabled", label: "Enabled" },
  { value: "template_only", label: "Template only" },
  { value: "disabled", label: "Disabled" },
  { value: "all", label: "Show all" },
];

const activeTab = computed(() => {
  const slug = String(route.path || "").split("/")[3] || "";
  return INTEGRATION_TAB_BY_SLUG[slug] || tabs[0].id;
});
const loading = ref(true);
const saving = ref(false);
const deleting = ref(false);
const integrations = ref([]);
const deleteConfirm = ref(null);
const previewData = ref(null);
const previewLoading = ref(false);
const previewIntegrationId = ref("");
const previewSelectedItemIndex = ref(0);
const previewActiveTab = ref("item");

const healthChecking = reactive({});
const healthResults = reactive({});
const fetching = reactive({});
const reprocessing = reactive({});
const deepFetching = reactive({});
const processingStatusById = reactive({});
const cloning = reactive({});
const favoriteSaving = reactive({});

const draftHealthChecking = ref(false);
const draftHealthResult = ref(null);

const inlineEditId = ref(null);
const inlineBaselineSignature = ref("");
const lastNavigatedIntegrationId = ref("");
const inlineSaving = ref(false);
const inlineDraftHealthChecking = ref(false);
const inlineDraftHealthResult = ref(null);
const INSPECT_RESULT_LIMIT = 50;
const PREVIEW_ITEM_LIMIT = INSPECT_RESULT_LIMIT;
const previewMetadata = computed(() => buildResponseMetadata(previewData.value));
const previewItems = computed(() => normalizePreviewItems(previewData.value?.data, previewData.value?.preview_item));
const previewItemsTruncated = computed(() => Boolean(previewData.value?.items_truncated));
const previewSelectedItem = computed(() => {
  const items = previewItems.value;
  if (items.length === 0) return null;
  const selectedIndex = Number(previewSelectedItemIndex.value);
  if (Number.isInteger(selectedIndex) && selectedIndex >= 0 && selectedIndex < items.length) {
    return items[selectedIndex];
  }
  return items[0];
});
const previewItemOptions = computed(() => {
  const labelPath = String(previewData.value?.item_label_path || "").trim();
  if (!labelPath) return [];
  return previewItems.value.map((item, index) => ({
    key: `preview-item-${index}`,
    index,
    label: getPreviewItemLabel(item, index, labelPath),
  }));
});
const inlineEditSignature = computed(() => buildInlineEditSignature());
const inlineEditHasChanges = computed(() =>
  Boolean(
    inlineEditId.value
      && inlineBaselineSignature.value
      && inlineEditSignature.value !== inlineBaselineSignature.value
  )
);
const selectedContainerTag = ref("");
const selectedReturnType = ref("");
const connectionSaving = ref(false);
const connectionSaveQueued = ref(false);
const connectionAutosaveStatus = ref("idle");
const connectionAutosaveError = ref("");
const connectionTemplatesLoading = ref(false);
const connectionVisibilityFilter = ref("all");
const connectionVisibilityFilterOptions = TEMPLATE_VISIBILITY_FILTER_OPTIONS;
const connectionSectionTypes = ref([]);
const connectionSectionTemplates = ref([]);
const connectionPageTemplates = ref([]);
const reviewIntegrationId = ref("");
const reviewItemsSummary = ref(null);
const reviewItems = ref([]);
const reviewStateFilter = ref("");
const reviewTagFilter = ref("");
const reviewItemSearchQuery = ref("");
const reviewSelectedItemKey = ref("");
const reviewItemDetail = ref(null);
const reviewStatus = ref(null);
const reviewRouteIntegrationId = computed(() =>
  String(route.query.integrationId || "").trim()
);
let connectionAutosaveStatusTimer = null;

const connectionAutosaveToastTone = computed(() => {
  if (connectionAutosaveStatus.value === "queued") return "queued";
  if (connectionSaving.value || connectionAutosaveStatus.value === "saving") return "saving";
  if (connectionAutosaveStatus.value === "saved") return "saved";
  if (connectionAutosaveStatus.value === "error") return "error";
  return "idle";
});

const connectionAutosaveToastMessage = computed(() => {
  if (connectionAutosaveStatus.value === "queued") return "Connection settings save queued...";
  if (connectionSaving.value || connectionAutosaveStatus.value === "saving") return "Saving connection settings...";
  if (connectionAutosaveStatus.value === "saved") return "Connection settings saved.";
  if (connectionAutosaveStatus.value === "error") {
    return `Connection settings autosave failed: ${connectionAutosaveError.value || "unknown error"}`;
  }
  return "";
});

function clearConnectionAutosaveStatusTimer() {
  if (connectionAutosaveStatusTimer) {
    clearTimeout(connectionAutosaveStatusTimer);
    connectionAutosaveStatusTimer = null;
  }
}

function setConnectionAutosaveStatus(status, error = "") {
  clearConnectionAutosaveStatusTimer();
  connectionAutosaveStatus.value = status;
  connectionAutosaveError.value = error;
  if (status === "saved" || status === "error") {
    connectionAutosaveStatusTimer = setTimeout(() => {
      connectionAutosaveStatus.value = "idle";
      connectionAutosaveError.value = "";
      connectionAutosaveStatusTimer = null;
    }, 3000);
  }
}

const reviewRouteItemKey = computed(() =>
  String(route.query.itemKey || "").trim()
);
const manageRouteIntegrationId = computed(() =>
  String(route.query.integrationId || "").trim()
);
const manageRouteSubsection = computed(() => {
  const raw = String(route.query.subsection || route.query.section || "").trim();
  return MANAGE_SUBSECTION_KEYS.has(raw) ? raw : "";
});
const reviewItemsLoading = ref(false);
const reviewItemLoading = ref(false);
const reviewMetaSaving = ref(false);
const reviewItemPageSyncSaving = ref(false);
const reviewTagDraft = ref("");
const reviewAddItemOpen = ref(false);
const reviewShowOutputColumns = ref(false);
const reviewAddItemSaving = ref(false);
const reviewAddItemDrafts = reactive({});
const reviewFieldDrafts = reactive({});
const reviewFieldSaving = reactive({});
const reviewImagePickerFieldPath = ref("");
const manageSchemaIntegrationId = ref("");
const manageSchema = ref(null);
const manageSchemaStatus = ref(null);
const manageSchemaLoading = ref(false);
const manageSchemaSaving = reactive({});
const manageSubsectionById = reactive({});
const REVIEW_SCHEMA_TYPES = [
  "text",
  "number",
  "boolean",
  "date",
  "datetime",
  "url",
  "image",
  "list",
  "json",
  "null",
  "undefined",
];

const DEFAULT_SECTION_TYPES = [
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
  "tiles",
  "program",
];
const DEFAULT_DISABLED_INTEGRATION_SECTION_TYPES = new Set([
  "text",
  "text_image",
  "video",
  "blog",
  "markdown",
  "html",
]);
const CONNECTION_SECTION_TYPE_ICONS = {
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

const nextUiId = ref(1);
const integrationItemRefs = reactive({});
const manageSubsectionRefs = reactive({});
const INTEGRATION_PATH_RULE_HINT = "Use dot-separated key paths with letters, numbers, and underscores only. Optional list indexes like [0] are allowed. Hyphens, spaces, and special characters are not allowed.";
const INTEGRATION_TARGET_RULE_HINT = "Target keys are stored as snake_case.";
const INTEGRATION_IDENTIFIER_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
const INTEGRATION_SNAKE_RE = /^[a-z_][a-z0-9_]*$/;
const INTEGRATION_CAMEL_RE = /^[a-z][A-Za-z0-9]*$/;
const INTEGRATION_PATH_SEGMENT_RE = /^([A-Za-z_][A-Za-z0-9_]*)(.*)$/;
const INTEGRATION_PATH_INDEX_RE = /^(\[-?\d+\])(.*)$/;
const COMPOSABLE_INTEGRATION_TYPES = new Set(["composable", "container"]);

function normalizeIntegrationType(rawType) {
  const value = String(rawType || "api").trim().toLowerCase();
  if (value === "api" || value === "crawler" || value === "composable") {
    return value;
  }
  return "api";
}

function isComposableIntegrationType(rawType) {
  return COMPOSABLE_INTEGRATION_TYPES.has(String(rawType || "").trim().toLowerCase());
}

function isComposableIntegration(integration) {
  return isComposableIntegrationType(integration?.type);
}

function getIntegrationTypeLabel(integration) {
  const normalizedType = normalizeIntegrationType(integration?.type);
  if (normalizedType === "api") return "API";
  if (normalizedType === "crawler") return "Crawler";
  if (normalizedType === "composable") return "Composable";
  return "API";
}

const form = reactive({
  name: "",
  description: "",
  url: "",
  type: "api",
  auth_type: "none",
  key_name: "",
  response_type: "json",
  response_path: "",
  crawler_pagination_strategy: "",
  crawler_page_query_param: "page",
  crawler_page_count_field: "",
  crawler_next_page_field: "",
  crawler_query_loop_key: "",
  crawler_query_loop_values_input: "",
  crawler_max_page_visits: 25,
  transform_steps: [],
  output_primary_key_path: "",
});

const containerForm = reactive({
  name: "",
  description: "",
  target_source_integration_id: "",
  sources: [],
  transform_steps: [],
  output_primary_key_path: "",
});

const inlineForm = reactive({
  name: "",
  description: "",
  type: "api",
  url: "",
  auth_type: "none",
  key_name: "",
  response_type: "json",
  response_path: "",
  crawler_pagination_strategy: "",
  crawler_page_query_param: "page",
  crawler_page_count_field: "",
  crawler_next_page_field: "",
  crawler_query_loop_key: "",
  crawler_query_loop_values_input: "",
  crawler_max_page_visits: 25,
  transform_steps: [],
  output_primary_key_path: "",
});

const inlineContainerForm = reactive({
  target_source_integration_id: "",
  sources: [],
});

const connectionForm = reactive({
  exposed_integration_ids: [],
  template_integration_rules: {},
});

const integrationPrimeKeyOptionsById = reactive({});
const integrationPrimeKeyLoadingById = reactive({});
const integrationPrimeKeyRequestsById = new Map();

const containerSourceOptions = computed(() =>
  integrations.value
);

const parentContainersBySource = computed(() => {
  const map = new Map();
  integrations.value.forEach((integration) => {
    if (!isComposableIntegration(integration)) {
      return;
    }
    const sources = Array.isArray(integration.container_config?.sources)
      ? integration.container_config.sources
      : [];
    sources.forEach((sourceRow) => {
      const sourceId = String(sourceRow?.integration_id || "").trim();
      if (!sourceId) {
        return;
      }
      if (!map.has(sourceId)) {
        map.set(sourceId, new Set());
      }
      map.get(sourceId).add(integration.id);
    });
  });
  return map;
});

const integrationMapById = computed(() => {
  const map = new Map();
  integrations.value.forEach((integration) => map.set(integration.id, integration));
  return map;
});

const containerMembershipTagsByIntegration = computed(() => {
  const parents = parentContainersBySource.value;
  const integrationById = integrationMapById.value;
  const cache = new Map();

  const collectContainerAncestors = (integrationId, chain = new Set()) => {
    if (cache.has(integrationId)) {
      return new Set(cache.get(integrationId));
    }
    if (chain.has(integrationId)) {
      return new Set();
    }

    const result = new Set();
    const directParents = parents.get(integrationId);
    if (!directParents || directParents.size === 0) {
      cache.set(integrationId, result);
      return new Set();
    }

    chain.add(integrationId);
    directParents.forEach((containerId) => {
      result.add(containerId);
      const ancestors = collectContainerAncestors(containerId, chain);
      ancestors.forEach((ancestorId) => result.add(ancestorId));
    });
    chain.delete(integrationId);

    cache.set(integrationId, result);
    return new Set(result);
  };

  const tagsByIntegration = {};
  integrations.value.forEach((integration) => {
    const containerIdSet = new Set(collectContainerAncestors(integration.id));
    if (isComposableIntegration(integration)) {
      containerIdSet.add(integration.id);
    }
    const containerIds = Array.from(containerIdSet);
    tagsByIntegration[integration.id] = containerIds
      .map((containerId) => integrationById.get(containerId)?.name || containerId)
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b));
  });
  return tagsByIntegration;
});

const availableContainerTags = computed(() => {
  const allTags = new Set();
  Object.values(containerMembershipTagsByIntegration.value).forEach((tagList) => {
    (tagList || []).forEach((tag) => allTags.add(tag));
  });
  return Array.from(allTags).sort((a, b) => a.localeCompare(b));
});

function normalizeReturnType(rawValue) {
  const value = String(rawValue || "").trim().toLowerCase();
  if (value === "list" || value === "object") {
    return value;
  }
  return "unknown";
}

const availableReturnTypes = computed(() => {
  const values = new Set();
  integrations.value.forEach((integration) => {
    values.add(normalizeReturnType(integration?.return_type));
  });
  return Array.from(values).sort((a, b) => a.localeCompare(b));
});

const filteredIntegrations = computed(() => {
  const activeTag = String(selectedContainerTag.value || "").trim();
  const activeReturnType = String(selectedReturnType.value || "").trim().toLowerCase();
  return integrations.value.filter((integration) => {
    if (activeTag && !getIntegrationContainerTags(integration).includes(activeTag)) {
      return false;
    }
    if (activeReturnType && normalizeReturnType(integration?.return_type) !== activeReturnType) {
      return false;
    }
    return true;
  });
});

function sortByName(a, b) {
  return String(a?.name || "").localeCompare(String(b?.name || ""));
}

function sortByFavoriteThenName(a, b) {
  const favoriteDiff = Number(Boolean(b?.favorite)) - Number(Boolean(a?.favorite));
  if (favoriteDiff !== 0) {
    return favoriteDiff;
  }
  return sortByName(a, b);
}

const groupedManageIntegrations = computed(() => {
  const NO_DOMAIN_KEY = "__NO_DOMAIN__";

  const containerItems = filteredIntegrations.value
    .filter((integration) => isComposableIntegration(integration))
    .slice()
    .sort(sortByFavoriteThenName);

  const baseGroups = new Map();
  filteredIntegrations.value.forEach((integration) => {
    if (isComposableIntegration(integration)) {
      return;
    }
    const key = getEffectiveIntegrationDomain(integration) || NO_DOMAIN_KEY;
    if (!baseGroups.has(key)) {
      baseGroups.set(key, []);
    }
    baseGroups.get(key).push(integration);
  });

  const normalizedBaseGroups = Array.from(baseGroups.entries())
    .map(([key, items]) => {
      const sortedItems = items.slice().sort(sortByFavoriteThenName);
      return {
        key: `base-${key}`,
        displayUrl: key === NO_DOMAIN_KEY ? "(No Domain)" : key,
        items: sortedItems,
        hasFavorite: sortedItems.some((integration) => Boolean(integration.favorite)),
      };
    })
    .sort((a, b) => {
      const favoriteGroupDiff = Number(b.hasFavorite) - Number(a.hasFavorite);
      if (favoriteGroupDiff !== 0) {
        return favoriteGroupDiff;
      }
      if (a.displayUrl === "(No Domain)") return 1;
      if (b.displayUrl === "(No Domain)") return -1;
      return a.displayUrl.localeCompare(b.displayUrl);
    });

  const groups = [];
  if (containerItems.length > 0) {
    groups.push({
      key: "composable",
      label: "Composable Integrations",
      count: containerItems.length,
      groups: [
        {
          key: "composable-all",
          displayUrl: "All Composables",
          items: containerItems,
        },
      ],
    });
  }

  if (normalizedBaseGroups.length > 0) {
    const totalBaseCount = normalizedBaseGroups.reduce((sum, group) => sum + group.items.length, 0);
    groups.push({
      key: "base",
      label: "Base Integrations",
      count: totalBaseCount,
      groups: normalizedBaseGroups,
    });
  }

  return groups;
});

const manageNavigatorSections = computed(() =>
  groupedManageIntegrations.value
    .map((typeGroup) => ({
      key: String(typeGroup?.key || "").trim(),
      label: String(typeGroup?.label || "").trim() || "Integrations",
      groups: (Array.isArray(typeGroup?.groups) ? typeGroup.groups : [])
        .map((group) => ({
          key: String(group?.key || "").trim(),
          label: String(group?.displayUrl || "").trim() || "(No Group)",
          items: Array.isArray(group?.items) ? group.items : [],
        }))
        .filter((group) => group.items.length > 0),
    }))
    .filter((section) => section.groups.length > 0)
);

const manageNavigatorVisibleIds = computed(() =>
  manageNavigatorSections.value.flatMap((section) =>
    section.groups.flatMap((group) =>
      group.items
        .map((integration) => String(integration?.id || "").trim())
        .filter(Boolean)
    )
  )
);

const activeNavigatorIntegrationId = computed(() => {
  const visibleIds = new Set(manageNavigatorVisibleIds.value);
  const inlineId = String(inlineEditId.value || "").trim();
  const lastNavigatedId = String(lastNavigatedIntegrationId.value || "").trim();
  if (lastNavigatedId && visibleIds.has(lastNavigatedId)) return lastNavigatedId;
  if (inlineId && visibleIds.has(inlineId)) return inlineId;
  return manageNavigatorVisibleIds.value[0] || "";
});

const selectedManageIntegration = computed(() => {
  const selectedId = activeNavigatorIntegrationId.value;
  if (!selectedId) return null;
  return filteredIntegrations.value.find((integration) =>
    String(integration?.id || "").trim() === selectedId
  ) || null;
});

const selectedManageIntegrationList = computed(() =>
  selectedManageIntegration.value ? [selectedManageIntegration.value] : []
);

const connectionIntegrations = computed(() =>
  [...integrations.value].sort(sortByName)
);

const connectionIntegrationGroups = computed(() => {
  const composables = [];
  const baseIntegrations = [];
  connectionIntegrations.value.forEach((integration) => {
    if (isComposableIntegration(integration)) {
      composables.push(integration);
    } else {
      baseIntegrations.push(integration);
    }
  });
  return [
    {
      key: "composables",
      label: "Composables",
      icon: faShareNodes,
      items: composables,
    },
    {
      key: "base",
      label: "Base Integrations",
      icon: faCode,
      items: baseIntegrations,
    },
  ].filter((group) => group.items.length > 0);
});

const reviewIntegrationOptions = computed(() =>
  [...integrations.value].sort(sortByName)
);

const reviewIntegrationGroups = computed(() => {
  const exposedIds = new Set(normalizeIntegrationIdList(connectionForm.exposed_integration_ids));
  const exposed = [];
  const notExposed = [];
  reviewIntegrationOptions.value.forEach((integration) => {
    if (exposedIds.has(String(integration?.id || "").trim())) {
      exposed.push(integration);
    } else {
      notExposed.push(integration);
    }
  });
  return [
    { key: "exposed", label: "Exposed globally", items: exposed },
    { key: "not-exposed", label: "Not exposed", items: notExposed },
  ].filter((group) => group.items.length > 0);
});

const reviewSelectedIntegration = computed(() =>
  reviewIntegrationOptions.value.find((integration) =>
    String(integration?.id || "").trim() === String(reviewIntegrationId.value || "").trim()
  ) || null
);

const reviewItemPageSyncBlocked = computed(() =>
  Boolean(
    reviewSelectedIntegration.value?.item_page_sync_blocked
    ?? reviewItemsSummary.value?.item_page_sync_blocked
  )
);

const reviewItemFields = computed(() =>
  Array.isArray(reviewItemDetail.value?.fields) ? reviewItemDetail.value.fields : []
);

const reviewImagePickerField = computed(() => {
  const activePath = String(reviewImagePickerFieldPath.value || "").trim();
  if (!activePath) return null;
  return reviewItemFields.value.find((field) => getReviewFieldPath(field) === activePath) || null;
});

const reviewImagePickerCurrentUrl = computed(() => {
  const field = reviewImagePickerField.value;
  const path = getReviewFieldPath(field);
  return path ? String(reviewFieldDrafts[path] || "").trim() : "";
});

const reviewHasPreviousFetchedDifferences = computed(() =>
  !reviewItemDetail.value?.is_local_item
    && reviewItemFields.value.some((field) => !isReviewPreviousMuted(field))
);

const reviewHasCurrentFetchedDifferences = computed(() =>
  !reviewItemDetail.value?.is_local_item
    && reviewItemFields.value.some((field) => !isReviewCurrentMuted(field))
);

const reviewStateCounts = computed(() =>
  reviewItemsSummary.value?.state_counts && typeof reviewItemsSummary.value.state_counts === "object"
    ? reviewItemsSummary.value.state_counts
    : {}
);

const reviewAvailableTagOptions = computed(() =>
  Array.isArray(reviewItemsSummary.value?.available_tags)
    ? [...new Set(
        reviewItemsSummary.value.available_tags
          .map((tag) => String(tag || "").trim())
          .filter(Boolean)
      )].sort((left, right) => left.localeCompare(right))
    : []
);

const reviewAvailablePageStateFilterOptions = computed(() =>
  Array.isArray(reviewItemsSummary.value?.available_page_state_filters)
    ? reviewItemsSummary.value.available_page_state_filters
        .map((entry) => ({
          value: String(entry?.value || "").trim(),
          label: String(entry?.label || "").trim(),
          count: Number(entry?.count ?? 0),
        }))
        .filter((entry) => entry.value && entry.label)
    : []
);

const normalizedReviewItemSearchQuery = computed(() =>
  String(reviewItemSearchQuery.value || "").trim().toLowerCase()
);

function formatReviewFilterOptionLabel(option) {
  const label = String(option?.label || "").trim();
  const count = Number(option?.count);
  return Number.isFinite(count) && count > 0 ? `${label} (${count})` : label;
}

function getReviewItemSearchText(item) {
  return [
    item?.label,
    item?.name,
    item?.title,
    item?.display_name,
    item?.displayName,
    item?.item_key,
  ]
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

const filteredReviewItems = computed(() => {
  const query = normalizedReviewItemSearchQuery.value;
  if (!query) return reviewItems.value;
  return reviewItems.value.filter((item) => getReviewItemSearchText(item).includes(query));
});

const reviewSchemaFields = computed(() =>
  Array.isArray(reviewItemsSummary.value?.schema_fields)
    ? [...reviewItemsSummary.value.schema_fields].sort((a, b) => String(a?.path || "").localeCompare(String(b?.path || "")))
    : []
);

const reviewCanAddItem = computed(() =>
  Boolean(
    reviewItemsSummary.value?.requires_primary_key
      && reviewItemsSummary.value?.output_primary_key_path
      && reviewSchemaFields.value.length > 0
  )
);

const reviewAddItemNamePath = computed(() => {
  const summaryNamePath = String(reviewItemsSummary.value?.item_label_path || "").trim();
  if (summaryNamePath) return summaryNamePath;
  const labelField = reviewSchemaFields.value.find((field) => Boolean(field?.is_item_label));
  return String(labelField?.path || reviewItemsSummary.value?.output_primary_key_path || "").trim();
});

const reviewAddItemNameField = computed(() => {
  const namePath = reviewAddItemNamePath.value;
  if (!namePath) return null;
  return reviewSchemaFields.value.find((field) => String(field?.path || "").trim() === namePath) || null;
});

const reviewAddItemMissingRequiredPaths = computed(() =>
  reviewAddItemNamePath.value
    && (!reviewAddItemNameField.value || isReviewAddFieldMissingRequired(reviewAddItemNameField.value))
    ? [reviewAddItemNamePath.value]
    : []
);

const manageSchemaFields = computed(() =>
  Array.isArray(manageSchema.value?.fields)
    ? [...manageSchema.value.fields].sort((a, b) => String(a?.path || "").localeCompare(String(b?.path || "")))
    : []
);

function normalizeSectionTypeValue(rawValue, fallback = "text") {
  const normalized = String(rawValue || "")
    .trim()
    .toLowerCase()
    .replace(/-/g, "_")
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return normalized || fallback;
}

function normalizeTemplateNameValue(rawValue, fallback = "default") {
  const normalized = String(rawValue || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return normalized || fallback;
}

function normalizePageTemplatePathValue(rawValue) {
  const raw = String(rawValue || "").trim().replace(/^\/+|\/+$/g, "");
  if (!raw) return "";
  const segments = raw
    .split("/")
    .map((entry) =>
      String(entry || "")
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9_-]+/g, "-")
        .replace(/^-+|-+$/g, "")
    )
    .filter(Boolean);
  if (!segments.length) return "";
  return segments.join("/");
}

function composeSectionTemplateRuleKey(sectionType, templateName = "default") {
  return `section/${normalizeSectionTypeValue(sectionType)}/${normalizeTemplateNameValue(templateName)}`;
}

function composePageTemplateRuleKey(templatePath) {
  const normalizedPath = normalizePageTemplatePathValue(templatePath);
  if (!normalizedPath) return "";
  return `page/${normalizedPath}`;
}

function buildSectionTemplateAdminHref(sectionType, templateName = "default") {
  const normalizedSectionType = normalizeSectionTypeValue(sectionType, "");
  if (!normalizedSectionType) return "";
  const normalizedTemplateName = normalizeTemplateNameValue(templateName, "default");
  const basePath = `/admin/templates/sections/${normalizedSectionType}`;
  if (normalizedTemplateName === "default") return basePath;
  return `${basePath}/${normalizedTemplateName}`;
}

function buildPageTemplateAdminHref(templatePath) {
  const normalizedPath = normalizePageTemplatePathValue(templatePath);
  if (!normalizedPath) return "/admin/templates/pages";
  return `/admin/templates/pages/${normalizedPath}`;
}

function normalizeTemplateRuleKey(rawKey) {
  const normalized = String(rawKey || "")
    .trim()
    .toLowerCase()
    .replace(/\\/g, "/");
  if (!normalized) return "";

  if (normalized.startsWith("section:")) {
    const withSlash = normalized.replace("section:", "section/").replace(/:/g, "/");
    const parts = withSlash.split("/").filter(Boolean);
    if (parts.length >= 3) {
      return composeSectionTemplateRuleKey(parts[1], parts[2]);
    }
  }
  if (normalized.startsWith("section/")) {
    const parts = normalized.split("/").filter(Boolean);
    if (parts.length >= 3) {
      return composeSectionTemplateRuleKey(parts[1], parts[2]);
    }
    return "";
  }

  if (normalized.startsWith("page/")) {
    return composePageTemplateRuleKey(normalized.slice("page/".length));
  }
  if (normalized.startsWith("page:")) {
    const payload = normalized.slice("page:".length);
    const parts = payload.split(":").filter(Boolean);
    if (!parts.length) return "";
    const templateName = normalizeTemplateNameValue(parts[parts.length - 1], "");
    if (!templateName) return "";
    if (parts.length === 1) {
      return composePageTemplateRuleKey(templateName);
    }
    let parentRoute = parts.slice(0, -1).join("/").replace(/^\/+|\/+$/g, "");
    if (!parentRoute) {
      return composePageTemplateRuleKey(templateName);
    }
    return composePageTemplateRuleKey(`${parentRoute}/${templateName}`);
  }

  const parts = normalized.replace(/:/g, "/").split("/").filter(Boolean);
  if (parts.length === 2) {
    return composeSectionTemplateRuleKey(parts[0], parts[1]);
  }
  return "";
}

function normalizeExpectedReturnType(rawValue) {
  const value = String(rawValue || "").trim().toLowerCase();
  if (value === "list" || value === "object") {
    return value;
  }
  return "auto";
}

function normalizeIntegrationVisibility(rawValue, fallback = "template_only") {
  const value = String(rawValue || "").trim().toLowerCase().replace(/-/g, "_");
  if (value === "disabled" || value === "template_only" || value === "enabled") {
    return value;
  }
  return fallback;
}

function isProgramTemplateKey(templateKey) {
  const normalizedKey = normalizeTemplateRuleKey(templateKey);
  if (!normalizedKey) return false;
  if (normalizedKey.startsWith("section/program/")) return true;
  const entry = connectionTemplateEntries.value.find(
    (candidate) => String(candidate?.key || "").trim() === normalizedKey
  );
  return normalizeSectionTypeValue(entry?.sectionType, "") === "program";
}

function getDefaultTemplateIntegrationVisibility(templateKey) {
  const normalizedKey = normalizeTemplateRuleKey(templateKey);
  if (!normalizedKey) return "template_only";
  if (isProgramTemplateKey(normalizedKey)) return "template_only";
  if (normalizedKey.startsWith("section/")) {
    const sectionType = normalizeSectionTypeValue(normalizedKey.split("/")[1], "");
    if (DEFAULT_DISABLED_INTEGRATION_SECTION_TYPES.has(sectionType)) {
      return "disabled";
    }
  }
  return "template_only";
}

function buildDefaultTemplateRule(templateKey) {
  const visibility = getDefaultTemplateIntegrationVisibility(templateKey);
  return {
    integration_visibility: visibility,
    integrations_enabled: visibility !== "disabled",
    expected_return_type: "auto",
  };
}

function isDefaultTemplateRule(templateKey, rule) {
  const normalizedTemplateKey = normalizeTemplateRuleKey(templateKey);
  if (!normalizedTemplateKey) return false;
  const defaultRule = buildDefaultTemplateRule(normalizedTemplateKey);
  const visibility = normalizeTemplateVisibilityForRule(
    normalizedTemplateKey,
    rule?.integration_visibility,
    defaultRule.integration_visibility
  );
  return visibility === defaultRule.integration_visibility
    && normalizeExpectedReturnType(rule?.expected_return_type) === defaultRule.expected_return_type;
}

function normalizeTemplateVisibilityForRule(templateKey, visibility, fallback = null) {
  const effectiveFallback = fallback || getDefaultTemplateIntegrationVisibility(templateKey);
  const normalizedVisibility = normalizeIntegrationVisibility(visibility, effectiveFallback);
  return isProgramTemplateKey(templateKey) && normalizedVisibility === "disabled"
    ? "template_only"
    : normalizedVisibility;
}

function templateVisibilityOptions(templateKey) {
  if (isProgramTemplateKey(templateKey)) {
    return [
      { value: "template_only", label: "Template only" },
      { value: "enabled", label: "Enabled" },
    ];
  }
  return [
    { value: "disabled", label: "Disabled" },
    { value: "template_only", label: "Template only" },
    { value: "enabled", label: "Enabled" },
  ];
}

function coerceLegacyIntegrationEnabled(rawValue, fallback = true) {
  if (typeof rawValue === "boolean") return rawValue;
  if (rawValue == null) return fallback;
  if (typeof rawValue === "string") {
    const value = rawValue.trim().toLowerCase();
    if (["false", "0", "no", "off", "disabled"].includes(value)) return false;
    if (["true", "1", "yes", "on", "enabled"].includes(value)) return true;
  }
  return Boolean(rawValue);
}

function normalizeTemplateIntegrationRules(rawMap) {
  if (!rawMap || typeof rawMap !== "object" || Array.isArray(rawMap)) return {};
  const normalized = {};
  Object.entries(rawMap).forEach(([rawKey, rawRule]) => {
    const key = normalizeTemplateRuleKey(rawKey);
    if (!key) return;
    if (rawRule && typeof rawRule === "object" && !Array.isArray(rawRule)) {
      const fallbackVisibility = rawRule.integrations_enabled != null
        ? (
          coerceLegacyIntegrationEnabled(rawRule.integrations_enabled, true)
            ? "enabled"
            : "disabled"
        )
        : getDefaultTemplateIntegrationVisibility(key);
      const visibility = normalizeTemplateVisibilityForRule(
        key,
        rawRule.integration_visibility,
        fallbackVisibility
      );
      normalized[key] = {
        integration_visibility: visibility,
        integrations_enabled: visibility !== "disabled",
        expected_return_type: normalizeExpectedReturnType(rawRule.expected_return_type),
      };
      return;
    }
    if (Array.isArray(rawRule)) {
      const visibility = normalizeTemplateVisibilityForRule(key, rawRule.length > 0 ? "enabled" : "disabled");
      normalized[key] = {
        integration_visibility: visibility,
        integrations_enabled: visibility !== "disabled",
        expected_return_type: "auto",
      };
      return;
    }
    const visibility = normalizeTemplateVisibilityForRule(key, Boolean(rawRule) ? "enabled" : "disabled");
    normalized[key] = {
      integration_visibility: visibility,
      integrations_enabled: visibility !== "disabled",
      expected_return_type: "auto",
    };
  });
  return normalized;
}

function formatSectionTypeLabel(sectionType) {
  const normalized = normalizeSectionTypeValue(sectionType);
  return normalized
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function getConnectionSectionTypeIcon(sectionType) {
  const normalized = normalizeSectionTypeValue(sectionType, "");
  return CONNECTION_SECTION_TYPE_ICONS[normalized] || faFileLines;
}

const connectionTemplateEntries = computed(() => {
  const sectionEntries = [];
  const sectionTemplatesByType = new Map();

  const ensureSectionTypeEntry = (rawSectionType) => {
    const sectionType = normalizeSectionTypeValue(rawSectionType, "");
    if (!sectionType) return null;
    if (!sectionTemplatesByType.has(sectionType)) {
      sectionTemplatesByType.set(sectionType, new Set(["default"]));
    }
    return sectionType;
  };

  connectionSectionTypes.value.forEach((rawType) => {
    ensureSectionTypeEntry(rawType);
  });

  connectionSectionTemplates.value.forEach((templateDoc) => {
    const sectionType = ensureSectionTypeEntry(templateDoc?.section_type);
    if (!sectionType) return;
    const templateName = normalizeTemplateNameValue(templateDoc?.template_name, "default");
    sectionTemplatesByType.get(sectionType).add(templateName);
  });

  if (!sectionTemplatesByType.size) {
    DEFAULT_SECTION_TYPES.forEach((sectionType) => {
      ensureSectionTypeEntry(sectionType);
    });
  }

  Array.from(sectionTemplatesByType.keys())
    .sort((a, b) => a.localeCompare(b))
    .forEach((sectionType) => {
      const templateNames = Array.from(sectionTemplatesByType.get(sectionType) || []);
      templateNames.sort((a, b) => {
        if (a === "default") return -1;
        if (b === "default") return 1;
        return a.localeCompare(b);
      });
      templateNames.forEach((templateName) => {
        sectionEntries.push({
          scope: "section",
          sectionType,
          templateName,
          key: composeSectionTemplateRuleKey(sectionType, templateName),
          label: `${formatSectionTypeLabel(sectionType)} / ${templateName}`,
          displayName: templateName,
          contextLabel: formatSectionTypeLabel(sectionType),
          href: buildSectionTemplateAdminHref(sectionType, templateName),
        });
      });
    });

  const pageEntries = [];
  connectionPageTemplates.value.forEach((templateDoc) => {
    const sourceType = String(templateDoc?.source_type || "").trim().toLowerCase();
    const parentRoute = String(templateDoc?.parent_route || "").trim();
    if (!parentRoute || !["blog", "tiles", "program"].includes(sourceType)) {
      return;
    }
    const templateName = normalizeTemplateNameValue(templateDoc?.template_name, "template");
    const path = normalizePageTemplatePathValue(templateDoc?.path);
    const key = composePageTemplateRuleKey(path);
    if (!key) return;
    pageEntries.push({
      scope: "page",
      sourceType,
      templateName,
      path,
      key,
      label: `${sourceType} / ${templateName}`,
      displayName: templateName,
      contextLabel: `${formatSectionTypeLabel(sourceType)} item-page`,
      href: buildPageTemplateAdminHref(path),
    });
  });
  pageEntries.sort((a, b) => a.label.localeCompare(b.label));

  return [...sectionEntries, ...pageEntries];
});

const connectionRuleGroups = computed(() => {
  const sectionEntries = connectionTemplateEntries.value.filter((entry) => entry.scope === "section");
  const pageEntries = connectionTemplateEntries.value.filter((entry) => entry.scope === "page");

  const sectionGroupsMap = new Map();
  sectionEntries.forEach((entry) => {
    const groupKey = String(entry.sectionType || "");
    if (!sectionGroupsMap.has(groupKey)) {
      sectionGroupsMap.set(groupKey, []);
    }
    sectionGroupsMap.get(groupKey).push(entry);
  });

  const groups = [];
  Array.from(sectionGroupsMap.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .forEach(([sectionType, templates]) => {
      groups.push({
        key: `section-${sectionType}`,
        sectionType,
        label: `${formatSectionTypeLabel(sectionType)} templates`,
        templates,
      });
    });

  if (pageEntries.length > 0) {
    groups.push({
      key: "item-pages",
      label: "Item-Page Templates",
      templates: pageEntries,
    });
  }

  return groups;
});

const filteredConnectionRuleGroups = computed(() => {
  const filter = String(connectionVisibilityFilter.value || "enabled").trim().toLowerCase();
  if (filter === "all") {
    return connectionRuleGroups.value;
  }
  const normalizedFilter = normalizeIntegrationVisibility(filter, "enabled");
  return connectionRuleGroups.value
    .map((group) => ({
      ...group,
      templates: group.templates.filter((template) =>
        getTemplateIntegrationVisibility(template.key) === normalizedFilter
      ),
    }))
    .filter((group) => group.templates.length > 0);
});

function setIntegrationItemRef(integrationId, el) {
  const key = String(integrationId || "").trim();
  if (!key) return;
  if (el) {
    integrationItemRefs[key] = el;
  } else {
    delete integrationItemRefs[key];
  }
}

function getManageSubsectionRefKey(integrationId, subsection) {
  const key = String(integrationId || "").trim();
  const subsectionKey = String(subsection || "").trim();
  if (!key || !MANAGE_SUBSECTION_KEYS.has(subsectionKey)) return "";
  return `${key}:${subsectionKey}`;
}

function setManageSubsectionRef(integrationId, subsection, el) {
  const refKey = getManageSubsectionRefKey(integrationId, subsection);
  if (!refKey) return;
  if (el) {
    manageSubsectionRefs[refKey] = el;
  } else {
    delete manageSubsectionRefs[refKey];
  }
}

async function scrollToIntegrationTop(integrationId) {
  const key = String(integrationId || "").trim();
  if (!key) return;
  await nextTick();
  const target = integrationItemRefs[key];
  if (target && typeof target.getBoundingClientRect === "function") {
    const rect = target.getBoundingClientRect();
    const topOffset = getTopScrollOffset();
    const scrollTop = Math.max(0, window.scrollY + rect.top - topOffset);
    window.scrollTo({ top: scrollTop, behavior: "smooth" });
  }
}

async function scrollToManageSubsectionHeader(integrationId, subsection) {
  const refKey = getManageSubsectionRefKey(integrationId, subsection);
  if (!refKey) return;
  await nextTick();
  const target = manageSubsectionRefs[refKey];
  if (target && typeof target.getBoundingClientRect === "function") {
    const rect = target.getBoundingClientRect();
    const topOffset = getTopScrollOffset();
    const scrollTop = Math.max(0, window.scrollY + rect.top - topOffset);
    window.scrollTo({ top: scrollTop, behavior: "smooth" });
  }
}

function isNavigatorItemActive(integrationId) {
  const key = String(integrationId || "").trim();
  if (!key) return false;
  return activeNavigatorIntegrationId.value === key;
}

async function openIntegrationFromNavigator(integration) {
  const key = String(integration?.id || "").trim();
  if (!key) return;

  const resolvedIntegration = integrations.value.find(
    (entry) => String(entry?.id || "").trim() === key
  ) || integration;

  lastNavigatedIntegrationId.value = key;
  startInlineEdit(resolvedIntegration);
}

async function openIntegrationSubsectionFromNavigator(integration, subsection) {
  const key = String(integration?.id || "").trim();
  const subsectionKey = String(subsection || "").trim();
  if (!key || !MANAGE_SUBSECTION_KEYS.has(subsectionKey)) return;

  const resolvedIntegration = integrations.value.find(
    (entry) => String(entry?.id || "").trim() === key
  ) || integration;

  const wasInlineActive = String(inlineEditId.value || "").trim() === key;
  lastNavigatedIntegrationId.value = key;
  if (!wasInlineActive) {
    startInlineEdit(resolvedIntegration);
  }
  await setManageSubsection(resolvedIntegration, subsectionKey, {
    toggleActive: false,
    scroll: true,
  });
}

async function applyManageRouteSelection() {
  if (activeTab.value !== "manage") return;
  const key = manageRouteIntegrationId.value;
  if (!key || integrations.value.length === 0) return;
  const integration = integrations.value.find(
    (entry) => String(entry?.id || "").trim() === key
  );
  if (!integration) return;

  lastNavigatedIntegrationId.value = key;
  if (String(inlineEditId.value || "").trim() !== key) {
    startInlineEdit(integration);
  }

  const subsection = manageRouteSubsection.value;
  if (subsection) {
    await setManageSubsection(integration, subsection, {
      toggleActive: false,
      scroll: true,
    });
  } else {
    await scrollToIntegrationTop(key);
  }
}

function getTopScrollOffset() {
  // Keep a little extra space so the row title is visible below fixed chrome.
  const basePadding = 16;
  const minOffset = 88;
  const fixedSelectors = [".topbar", ".header-bar", ".site-header", ".admin-header"];
  const fixedHeight = fixedSelectors
    .map((selector) => document.querySelector(selector))
    .filter(Boolean)
    .reduce((height, el) => {
      const style = window.getComputedStyle(el);
      const position = String(style.position || "").toLowerCase();
      if (position !== "fixed" && position !== "sticky") return height;
      const top = Number.parseFloat(style.top || "0");
      if (!Number.isFinite(top) || top > 2) return height;
      return Math.max(height, el.getBoundingClientRect().height || 0);
    }, 0);
  return Math.max(minOffset, Math.ceil(fixedHeight + basePadding));
}

function normalizeUrl(urlValue) {
  const raw = String(urlValue || "").trim();
  if (!raw) return "";
  if (/^[a-zA-Z][a-zA-Z\d+\-.]*:\/\//.test(raw)) {
    return raw;
  }
  return `https://${raw}`;
}

function extractDomainFromUrl(urlValue) {
  const normalizedUrl = normalizeUrl(urlValue);
  if (!normalizedUrl) return "";
  try {
    return String(new URL(normalizedUrl).hostname || "").trim().toLowerCase();
  } catch {
    return "";
  }
}

function getEffectiveIntegrationUrl(integration, chain = new Set()) {
  if (!integration) return "";

  const directUrl = String(integration.url || "").trim();
  if (directUrl) return directUrl;
  if (!isComposableIntegration(integration)) return "";

  const integrationId = String(integration.id || "").trim();
  if (integrationId && chain.has(integrationId)) {
    return "";
  }
  const nextChain = new Set(chain);
  if (integrationId) {
    nextChain.add(integrationId);
  }

  const sources = Array.isArray(integration.container_config?.sources)
    ? integration.container_config.sources
    : [];
  const targetSourceId = String(integration.container_config?.target_source_integration_id || "").trim();
  const sourceOrder = [];
  if (targetSourceId) {
    sourceOrder.push(targetSourceId);
  }
  sources.forEach((source) => {
    const sourceId = String(source?.integration_id || "").trim();
    if (sourceId && !sourceOrder.includes(sourceId)) {
      sourceOrder.push(sourceId);
    }
  });

  for (const sourceId of sourceOrder) {
    const sourceIntegration = integrations.value.find((entry) => String(entry.id || "") === sourceId);
    if (!sourceIntegration) continue;
    const sourceUrl = getEffectiveIntegrationUrl(sourceIntegration, nextChain);
    if (sourceUrl) {
      return sourceUrl;
    }
  }

  return "";
}

function getEffectiveIntegrationDomain(integration) {
  return extractDomainFromUrl(getEffectiveIntegrationUrl(integration));
}

function normalizeIntegrationIdentifierToken(rawToken, { fieldLabel, mode = "reference" } = {}) {
  const token = String(rawToken || "").trim();
  if (!token) {
    throw new Error(`${fieldLabel} cannot be empty.`);
  }
  if (!INTEGRATION_IDENTIFIER_RE.test(token)) {
    throw new Error(`${fieldLabel} contains invalid token "${token}". ${INTEGRATION_PATH_RULE_HINT}`);
  }

  const hasUppercase = /[A-Z]/.test(token);
  const hasUnderscore = token.includes("_");
  if (hasUppercase && hasUnderscore) {
    throw new Error(
      `${fieldLabel} token "${token}" mixes snake_case and camelCase. Use either snake_case or lower camelCase per token.`
    );
  }

  const isSnake = INTEGRATION_SNAKE_RE.test(token);
  const isCamel = INTEGRATION_CAMEL_RE.test(token);
  if (!isSnake && !isCamel) {
    throw new Error(
      `${fieldLabel} token "${token}" must be snake_case or lower camelCase. ${INTEGRATION_PATH_RULE_HINT}`
    );
  }

  if (mode === "target") {
    return toSnakeCase(token);
  }
  return token;
}

function normalizeIntegrationPathSegment(rawSegment, { fieldLabel, mode = "reference" } = {}) {
  const segment = String(rawSegment || "").trim();
  const match = INTEGRATION_PATH_SEGMENT_RE.exec(segment);
  if (!match) {
    throw new Error(`${fieldLabel} contains invalid segment "${segment}". ${INTEGRATION_PATH_RULE_HINT}`);
  }

  const head = normalizeIntegrationIdentifierToken(match[1], { fieldLabel, mode });
  let tail = match[2];
  let rebuilt = head;
  while (tail) {
    const indexMatch = INTEGRATION_PATH_INDEX_RE.exec(tail);
    if (!indexMatch) {
      throw new Error(`${fieldLabel} contains invalid segment "${segment}". ${INTEGRATION_PATH_RULE_HINT}`);
    }
    rebuilt += indexMatch[1];
    tail = indexMatch[2];
  }
  return rebuilt;
}

function normalizeIntegrationPathInput(rawValue, {
  fieldLabel,
  mode = "reference",
  required = false,
} = {}) {
  let raw = String(rawValue || "").trim();
  if (raw.toLowerCase().startsWith("in ")) {
    raw = raw.slice(3).trim();
  }
  if (!raw) {
    if (required) {
      throw new Error(`${fieldLabel} is required.`);
    }
    return "";
  }

  const parts = raw.split(".");
  if (parts.some((part) => !String(part || "").trim())) {
    throw new Error(`${fieldLabel} contains empty path segments. ${INTEGRATION_PATH_RULE_HINT}`);
  }
  return parts
    .map((part) => normalizeIntegrationPathSegment(part, { fieldLabel, mode }))
    .join(".");
}

function normalizeIntegrationIdentifierInput(rawValue, {
  fieldLabel,
  mode = "reference",
  required = false,
} = {}) {
  const raw = String(rawValue || "").trim();
  if (!raw) {
    if (required) {
      throw new Error(`${fieldLabel} is required.`);
    }
    return "";
  }
  return normalizeIntegrationIdentifierToken(raw, { fieldLabel, mode });
}

function makeUiId(prefix) {
  nextUiId.value += 1;
  return `${prefix}-${nextUiId.value}`;
}

function createReplaceNestedMapping(mapping = {}) {
  return {
    ui_id: makeUiId("replace-map"),
    item_key_path: String(mapping.item_key_path || "").trim(),
    match_value_input: mapping.match_value == null ? "" : String(mapping.match_value),
    source_value_path: String(mapping.source_value_path || "").trim(),
    renamed_value: String(
      mapping.renamed_value
      || ""
    ).trim(),
    target_key: String(mapping.target_key || "").trim(),
  };
}

function createRenameKeyMapping(mapping = {}) {
  return {
    ui_id: makeUiId("rename-map"),
    source_key: String(
      mapping.source_key || mapping.old_key || ""
    ).trim(),
    target_key: String(
      mapping.target_key || mapping.new_key || ""
    ).trim(),
  };
}

function createTransformStep(op = "keep_keys") {
  if (op === "keep_keys" || op === "remove_keys" || op === "ensure_keys") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: true,
      keys_input: "",
    };
  }
  if (op === "group_by") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: true,
      key_path: "",
      items_key: "grouped_documents",
    };
  }
  if (op === "replace_nested_item") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: true,
      static_route: "",
      replace_mappings: [createReplaceNestedMapping()],
    };
  }
  if (op === "filter_by_allowed_values") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: true,
      allowed_key_path: "",
      allowed_values_input: "",
    };
  }
  if (op === "filter_by_disallowed_values") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: true,
      allowed_key_path: "",
      allowed_values_input: "",
    };
  }
  if (op === "split_values_to_list") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: true,
      split_key: "",
      split_separator: "",
    };
  }
  if (op === "rename_keys") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: true,
      rename_mappings: [createRenameKeyMapping()],
    };
  }
  return createTransformStep("remove_keys");
}

function normalizeTransformStepUi(step) {
  const op = step?.op || "keep_keys";
  if (op === "keep_keys" || op === "remove_keys" || op === "ensure_keys") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: step?.enabled !== false,
      keys_input: Array.isArray(step.keys) ? step.keys.join(",") : String(step.keys_input || ""),
    };
  }
  if (op === "group_by") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: step?.enabled !== false,
      key_path: step.key_path || "",
      items_key: String(step.items_key || "").trim() || "grouped_documents",
    };
  }
  if (op === "replace_nested_item") {
    const staticRoute = String(step.static_route || "").trim();
    const rawMappings = Array.isArray(step.mappings) ? step.mappings : [];
    const replaceMappings = rawMappings.map((mapping) => createReplaceNestedMapping(mapping));

    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: step?.enabled !== false,
      static_route: staticRoute,
      replace_mappings: replaceMappings.length > 0
        ? replaceMappings
        : [createReplaceNestedMapping()],
    };
  }
  if (op === "filter_by_allowed_values" || op === "filter_by_disallowed_values") {
    const keyName = op === "filter_by_allowed_values" ? "allowed_values" : "disallowed_values";
    const rawAllowedValues = step[keyName] && typeof step[keyName] === "object" && !Array.isArray(step[keyName])
      ? step[keyName]
      : {};
    const [firstEntry] = Object.entries(rawAllowedValues);
    const [keyPath, values] = firstEntry || ["", []];
    const normalizedValues = Array.isArray(values) ? values : [values];
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: step?.enabled !== false,
      allowed_key_path: String(keyPath || "").trim(),
      allowed_values_input: normalizedValues
        .map((value) => String(value ?? "").trim())
        .filter(Boolean)
        .join(","),
    };
  }
  if (op === "split_values_to_list") {
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: step?.enabled !== false,
      split_key: String(step.key || "").trim(),
      split_separator: String(step.separator || ""),
    };
  }
  if (op === "rename_keys") {
    const rawMappings = Array.isArray(step.mappings)
      ? step.mappings
      : (Array.isArray(step.rename_mappings) ? step.rename_mappings : []);
    const renameMappings = rawMappings.map((mapping) => createRenameKeyMapping(mapping));
    return {
      ui_id: makeUiId("transform"),
      op,
      enabled: step?.enabled !== false,
      rename_mappings: renameMappings.length > 0 ? renameMappings : [createRenameKeyMapping()],
    };
  }
  return createTransformStep("remove_keys");
}

function parseTransformStepsFrom(stepList) {
  const steps = [];

  (stepList || []).forEach((step, index) => {
    const enabled = step?.enabled !== false;
    const stepLabel = `Transform step ${index + 1}`;

    if (step.op === "keep_keys" || step.op === "remove_keys" || step.op === "ensure_keys") {
      const keys = String(step.keys_input || "")
        .split(",")
        .map((entry) => entry.trim())
        .filter(Boolean)
        .map((entry, keyIndex) => normalizeIntegrationPathInput(entry, {
          fieldLabel: `${stepLabel}: keys[${keyIndex + 1}]`,
          mode: "reference",
          required: true,
        }));
      steps.push({ op: step.op, enabled, keys });
      return;
    }

    if (step.op === "group_by") {
      const keyPath = normalizeIntegrationPathInput(step.key_path, {
        fieldLabel: `${stepLabel}: group key path`,
        mode: "reference",
        required: true,
      });
      const itemsKey = normalizeIntegrationIdentifierInput(
        String(step.items_key || "").trim() || "grouped_documents",
        {
          fieldLabel: `${stepLabel}: grouped items key`,
          mode: "target",
          required: true,
        }
      );
      steps.push({ op: "group_by", enabled, key_path: keyPath, items_key: itemsKey });
      return;
    }

    if (step.op === "replace_nested_item") {
      const staticRoute = String(step.static_route || "").trim();
      if (!staticRoute) {
        throw new Error(`Transform step ${index + 1}: static route is required.`);
      }

      const rawMappings = Array.isArray(step.replace_mappings) ? step.replace_mappings : [];
      const mappings = [];

      rawMappings.forEach((mapping, mappingIndex) => {
        const itemKeyPathRaw = String(mapping?.item_key_path || "").trim();
        const matchValueInput = String(mapping?.match_value_input ?? "").trim();
        const sourceValuePathRaw = String(mapping?.source_value_path || "").trim();
        const renamedValue = String(mapping?.renamed_value || "").trim();
        const targetKeyRaw = String(mapping?.target_key || "").trim();
        const mappingLabel = `${stepLabel}: mapping ${mappingIndex + 1}`;
        if (!itemKeyPathRaw && !matchValueInput) {
          return;
        }
        if (!matchValueInput) {
          throw new Error(`${mappingLabel} match value is required.`);
        }
        mappings.push({
          item_key_path: itemKeyPathRaw
            ? normalizeIntegrationPathInput(itemKeyPathRaw, {
                fieldLabel: `${mappingLabel} key path specification`,
                mode: "reference",
                required: true,
              })
            : null,
          match_value: matchValueInput,
          source_value_path: sourceValuePathRaw
            ? normalizeIntegrationPathInput(sourceValuePathRaw, {
                fieldLabel: `${mappingLabel} source value path`,
                mode: "reference",
                required: true,
              })
            : null,
          renamed_value: renamedValue || null,
          target_key: targetKeyRaw
            ? normalizeIntegrationPathInput(targetKeyRaw, {
                fieldLabel: `${mappingLabel} target key path`,
                mode: "target",
                required: true,
              })
            : null,
        });
      });

      if (mappings.length === 0) {
        throw new Error(`${stepLabel}: add at least one replace mapping.`);
      }

      steps.push({
        op: "replace_nested_item",
        enabled,
        static_route: staticRoute,
        mappings,
      });
      return;
    }

    if (step.op === "filter_by_allowed_values" || step.op === "filter_by_disallowed_values") {
      const valueFieldName = step.op === "filter_by_allowed_values" ? "allowed_values" : "disallowed_values";
      const valueFieldLabel = step.op === "filter_by_allowed_values" ? "allowed value" : "disallowed value";
      const isAllowedMode = step.op === "filter_by_allowed_values";
      const keyPath = normalizeIntegrationPathInput(step.allowed_key_path, {
        fieldLabel: `${stepLabel}: filter key path`,
        mode: "reference",
        required: true,
      });

      const filterValues = String(step.allowed_values_input || "")
        .split(",")
        .map((entry) => entry.trim())
        .filter(Boolean);
      if (isAllowedMode && filterValues.length === 0) {
        throw new Error(`${stepLabel}: provide at least one ${valueFieldLabel}.`);
      }

      steps.push({
        op: step.op,
        enabled,
        [valueFieldName]: {
          [keyPath]: filterValues,
        },
      });
      return;
    }

    if (step.op === "split_values_to_list") {
      const key = normalizeIntegrationPathInput(step.split_key, {
        fieldLabel: `${stepLabel}: split key`,
        mode: "reference",
        required: true,
      });
      const separator = String(step.split_separator || "");
      if (!separator) {
        throw new Error(`${stepLabel}: separator is required.`);
      }
      steps.push({ op: "split_values_to_list", enabled, key, separator });
      return;
    }

    if (step.op === "rename_keys") {
      const rawMappings = Array.isArray(step.rename_mappings) ? step.rename_mappings : [];
      const mappings = [];

      rawMappings.forEach((mapping, mappingIndex) => {
        const mappingLabel = `${stepLabel}: mapping ${mappingIndex + 1}`;
        const sourceKeyRaw = String(mapping?.source_key || mapping?.old_key || "").trim();
        const targetKeyRaw = String(mapping?.target_key || mapping?.new_key || "").trim();
        if (!sourceKeyRaw && !targetKeyRaw) {
          return;
        }
        const sourceKey = normalizeIntegrationPathInput(sourceKeyRaw, {
          fieldLabel: `${mappingLabel} old key`,
          mode: "reference",
          required: true,
        });
        const targetKey = normalizeIntegrationPathInput(targetKeyRaw, {
          fieldLabel: `${mappingLabel} new key`,
          mode: "target",
          required: true,
        });
        mappings.push({ source_key: sourceKey, target_key: targetKey });
      });

      if (mappings.length === 0) {
        throw new Error(`${stepLabel}: add at least one rename mapping.`);
      }

      steps.push({ op: "rename_keys", enabled, mappings });
      return;
    }

    throw new Error(`Transform step ${index + 1}: unsupported operation.`);
  });

  return steps;
}

function resetCrawlerPaginationUi(target) {
  target.crawler_pagination_strategy = "";
  target.crawler_page_query_param = "page";
  target.crawler_page_count_field = "";
  target.crawler_next_page_field = "";
  target.crawler_query_loop_key = "";
  target.crawler_query_loop_values_input = "";
  target.crawler_max_page_visits = 25;
}

function applyCrawlerPaginationUi(target, config) {
  resetCrawlerPaginationUi(target);
  if (!config || typeof config !== "object") {
    return;
  }

  const strategy = String(config.strategy || "").trim();
  target.crawler_pagination_strategy = ["page_count", "next_page"].includes(strategy)
    ? strategy
    : "";
  target.crawler_page_query_param = String(config.page_query_param || "page").trim() || "page";
  target.crawler_page_count_field = String(config.page_count_field || "").trim();
  target.crawler_next_page_field = String(config.next_page_field || "").trim();
  target.crawler_query_loop_key = String(config.query_loop_key || "").trim();
  target.crawler_query_loop_values_input = Array.isArray(config.query_loop_values)
    ? config.query_loop_values.map((entry) => String(entry || "").trim()).filter(Boolean).join(",")
    : "";
  const parsedMaxVisits = Number.parseInt(String(config.max_page_visits ?? 25), 10);
  target.crawler_max_page_visits = Number.isFinite(parsedMaxVisits) && parsedMaxVisits > 0
    ? parsedMaxVisits
    : 25;
}

function buildCrawlerPaginationPayloadFrom(target, stepLabel = "Crawler pagination") {
  const strategy = String(target.crawler_pagination_strategy || "").trim();
  const queryLoopKey = String(target.crawler_query_loop_key || "").trim();
  const queryLoopValues = String(target.crawler_query_loop_values_input || "")
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
  if (queryLoopValues.length > 0 && !queryLoopKey) {
    throw new Error(`${stepLabel}: query loop key is required when query loop values are set.`);
  }
  if (queryLoopKey && queryLoopValues.length === 0) {
    throw new Error(`${stepLabel}: query loop values are required when query loop key is set.`);
  }
  const hasQueryLoop = Boolean(queryLoopKey) && queryLoopValues.length > 0;

  if (!strategy && !hasQueryLoop) {
    return null;
  }

  const maxPageVisits = Number.parseInt(String(target.crawler_max_page_visits || 0), 10);
  const basePayload = hasQueryLoop
    ? {
        query_loop_key: queryLoopKey,
        query_loop_values: queryLoopValues,
      }
    : {};

  if (strategy === "page_count") {
    if (!Number.isFinite(maxPageVisits) || maxPageVisits <= 0) {
      throw new Error(`${stepLabel}: max page visits must be a positive number.`);
    }
    const pageQueryParam = String(target.crawler_page_query_param || "").trim();
    const pageCountField = String(target.crawler_page_count_field || "").trim();
    if (!pageQueryParam) {
      throw new Error(`${stepLabel}: page query param is required for page_count strategy.`);
    }
    if (!pageCountField) {
      throw new Error(`${stepLabel}: page count field is required for page_count strategy.`);
    }
    return {
      strategy: "page_count",
      page_query_param: pageQueryParam,
      page_count_field: pageCountField,
      max_page_visits: maxPageVisits,
      ...basePayload,
    };
  }

  if (strategy === "next_page") {
    if (!Number.isFinite(maxPageVisits) || maxPageVisits <= 0) {
      throw new Error(`${stepLabel}: max page visits must be a positive number.`);
    }
    const nextPageField = String(target.crawler_next_page_field || "").trim();
    if (!nextPageField) {
      throw new Error(`${stepLabel}: next page field is required for next_page strategy.`);
    }
    return {
      strategy: "next_page",
      next_page_field: nextPageField,
      max_page_visits: maxPageVisits,
      ...basePayload,
    };
  }

  if (!strategy && hasQueryLoop) {
    return {
      strategy: "query_loop",
      ...basePayload,
    };
  }

  throw new Error(`${stepLabel}: unsupported strategy.`);
}

function createContainerSource(source = {}) {
  return {
    ui_id: makeUiId("source"),
    integration_id: source.integration_id || "",
    source_key_path: source.source_key_path || "",
    target_key_path: source.target_key_path || "",
    merge_style: source.merge_style === "nested" ? "nested" : "flat",
    nested_key: source.nested_key || "",
    keep_target_key: Boolean(source.keep_target_key),
    collapsed: Boolean(source.collapsed),
  };
}

function resetForm() {
  form.name = "";
  form.description = "";
  form.url = "";
  form.type = "api";
  form.auth_type = "none";
  form.key_name = "";
  form.response_type = "json";
  form.response_path = "";
  resetCrawlerPaginationUi(form);
  form.transform_steps = [];
  form.output_primary_key_path = "";
  draftHealthResult.value = null;
}

function resetContainerForm() {
  containerForm.name = "";
  containerForm.description = "";
  containerForm.target_source_integration_id = "";
  containerForm.sources = [createContainerSource(), createContainerSource()];
  containerForm.transform_steps = [];
  containerForm.output_primary_key_path = "";
}

function resetInlineForm() {
  inlineForm.name = "";
  inlineForm.description = "";
  inlineForm.type = "api";
  inlineForm.url = "";
  inlineForm.auth_type = "none";
  inlineForm.key_name = "";
  inlineForm.response_type = "json";
  inlineForm.response_path = "";
  resetCrawlerPaginationUi(inlineForm);
  inlineForm.transform_steps = [];
  inlineForm.output_primary_key_path = "";
  inlineContainerForm.target_source_integration_id = "";
  inlineContainerForm.sources = [createContainerSource(), createContainerSource()];
  inlineDraftHealthResult.value = null;
  inlineBaselineSignature.value = "";
}

function normalizeTransformStepsUi(rawSteps) {
  const normalized = [];
  (rawSteps || []).forEach((step) => {
    const isAllowedStep = step?.op === "filter_by_allowed_values";
    const isDisallowedStep = step?.op === "filter_by_disallowed_values";
    const isFilterStep = isAllowedStep || isDisallowedStep;
    const valuesField = isAllowedStep ? "allowed_values" : "disallowed_values";
    const rawAllowedValues = isFilterStep && step[valuesField] && typeof step[valuesField] === "object" && !Array.isArray(step[valuesField])
      ? step[valuesField]
      : null;

    if (rawAllowedValues) {
      const entries = Object.entries(rawAllowedValues)
        .map(([rawKey, rawValue]) => [String(rawKey || "").trim(), rawValue])
        .filter(([keyPath]) => Boolean(keyPath));

      if (entries.length > 1) {
        entries.forEach(([keyPath, rawValue]) => {
          const values = Array.isArray(rawValue) ? rawValue : [rawValue];
          normalized.push(
            normalizeTransformStepUi({
              op: step.op,
              enabled: step?.enabled !== false,
              [valuesField]: {
                [keyPath]: values,
              },
            })
          );
        });
        return;
      }
    }

    normalized.push(normalizeTransformStepUi(step));
  });
  return normalized;
}

function getContainerSourceOptions(excludedIntegrationId = null) {
  if (!excludedIntegrationId) {
    return containerSourceOptions.value;
  }
  return containerSourceOptions.value.filter(
    (entry) => entry.id !== excludedIntegrationId
  );
}

function normalizePrimeKeyOptions(rawKeys = []) {
  if (!Array.isArray(rawKeys)) return [];
  const seen = new Set();
  return rawKeys
    .map((value) => String(value || "").trim())
    .filter((value) => {
      if (!value || seen.has(value)) return false;
      seen.add(value);
      return true;
    });
}

function getPreferredPrimeKey(options = []) {
  return options.includes("id") ? "id" : (options[0] || "");
}

function isIntegrationPrimeKeyOptionsLoading(integrationId) {
  const lookupId = String(integrationId || "").trim();
  if (!lookupId) return false;
  return Boolean(integrationPrimeKeyLoadingById[lookupId]);
}

function getIntegrationPrimeKeyOptions(integrationId) {
  const lookupId = String(integrationId || "").trim();
  if (!lookupId) return [];
  const options = integrationPrimeKeyOptionsById[lookupId];
  return Array.isArray(options) ? options : [];
}

function getIntegrationPrimeKeyOptionsWithCurrent(integrationId, currentValue = "") {
  const options = getIntegrationPrimeKeyOptions(integrationId);
  const normalizedCurrentValue = String(currentValue || "").trim();
  if (!normalizedCurrentValue || options.includes(normalizedCurrentValue)) {
    return options;
  }
  return [normalizedCurrentValue, ...options];
}

async function ensureIntegrationPrimeKeyOptions(integrationId) {
  const lookupId = String(integrationId || "").trim();
  if (!lookupId) return [];

  const cached = integrationPrimeKeyOptionsById[lookupId];
  if (Array.isArray(cached)) {
    return cached;
  }
  if (integrationPrimeKeyRequestsById.has(lookupId)) {
    return integrationPrimeKeyRequestsById.get(lookupId);
  }

  integrationPrimeKeyLoadingById[lookupId] = true;
  const request = api.getIntegrationDataPreview(lookupId)
    .then((preview) => {
      const options = normalizePrimeKeyOptions(preview?.available_keys);
      integrationPrimeKeyOptionsById[lookupId] = options;
      return options;
    })
    .catch((err) => {
      console.warn(`Failed to load available fields for integration ${lookupId}:`, err);
      integrationPrimeKeyOptionsById[lookupId] = [];
      return [];
    })
    .finally(() => {
      integrationPrimeKeyLoadingById[lookupId] = false;
      integrationPrimeKeyRequestsById.delete(lookupId);
    });

  integrationPrimeKeyRequestsById.set(lookupId, request);
  return request;
}

function applyPrimeKeyDefaultIfEmpty(sourceRow, fieldName, availableOptions = []) {
  const currentValue = String(sourceRow?.[fieldName] || "").trim();
  if (currentValue) return;
  const preferredField = getPreferredPrimeKey(availableOptions);
  if (preferredField) {
    sourceRow[fieldName] = preferredField;
  }
}

function autoSelectOutputPrimeKey(targetForm, availableOptions = []) {
  const currentValue = String(targetForm?.output_primary_key_path || "").trim();
  if (currentValue) return;
  if (availableOptions.includes("id")) {
    targetForm.output_primary_key_path = "id";
  }
}

async function ensureIntegrationOutputPrimeKeySelection(targetForm, integrationId) {
  const options = await ensureIntegrationPrimeKeyOptions(integrationId);
  autoSelectOutputPrimeKey(targetForm, options);
  return options;
}

async function autoApplyContainerPrimeKeys(sourceRows, targetSourceId) {
  const normalizedTargetId = String(targetSourceId || "").trim();
  if (!normalizedTargetId || !Array.isArray(sourceRows) || sourceRows.length === 0) {
    return;
  }

  const targetOptions = await ensureIntegrationPrimeKeyOptions(normalizedTargetId);
  for (const sourceRow of sourceRows) {
    const sourceId = String(sourceRow?.integration_id || "").trim();
    if (!sourceId || sourceId === normalizedTargetId) {
      continue;
    }
    const sourceOptions = await ensureIntegrationPrimeKeyOptions(sourceId);
    applyPrimeKeyDefaultIfEmpty(sourceRow, "source_key_path", sourceOptions);
    applyPrimeKeyDefaultIfEmpty(sourceRow, "target_key_path", targetOptions);
  }
}

function isTargetSource(source, targetSourceId) {
  const sourceId = String(source?.integration_id || "").trim();
  const targetId = String(targetSourceId || "").trim();
  return Boolean(sourceId) && Boolean(targetId) && sourceId === targetId;
}

function normalizeTargetSourceSelection(sourceRows, targetSourceId) {
  const targetId = String(targetSourceId || "").trim();
  if (!targetId) {
    return "";
  }
  const availableSourceIds = new Set(
    (sourceRows || [])
      .map((row) => String(row?.integration_id || "").trim())
      .filter(Boolean)
  );
  return availableSourceIds.has(targetId) ? targetId : "";
}

function toggleContainerTargetSource(source) {
  const sourceId = String(source?.integration_id || "").trim();
  if (!sourceId) {
    alert("Select an integration for this source first.");
    return;
  }
  containerForm.target_source_integration_id = isTargetSource(source, containerForm.target_source_integration_id)
    ? ""
    : sourceId;
}

function clearContainerTargetSource() {
  containerForm.target_source_integration_id = "";
}

function toggleInlineContainerTargetSource(source) {
  const sourceId = String(source?.integration_id || "").trim();
  if (!sourceId) {
    alert("Select an integration for this source first.");
    return;
  }
  inlineContainerForm.target_source_integration_id = isTargetSource(source, inlineContainerForm.target_source_integration_id)
    ? ""
    : sourceId;
}

function clearInlineContainerTargetSource() {
  inlineContainerForm.target_source_integration_id = "";
}

function getIntegrationContainerTags(integration) {
  if (!integration?.id) {
    return [];
  }
  return containerMembershipTagsByIntegration.value[integration.id] || [];
}

function getIntegrationDisplayName(integrationId) {
  const lookupId = String(integrationId || "").trim();
  if (!lookupId) return "-";
  const match = integrations.value.find((entry) => String(entry.id) === lookupId);
  return match?.name || lookupId;
}

function createCloneName(baseName) {
  const sourceName = String(baseName || "Integration").trim() || "Integration";
  const existingNames = new Set(
    integrations.value.map((entry) => String(entry.name || "").trim()).filter(Boolean)
  );
  let candidate = `${sourceName} (Copy)`;
  let counter = 2;
  while (existingNames.has(candidate)) {
    candidate = `${sourceName} (Copy ${counter})`;
    counter += 1;
  }
  return candidate;
}

function normalizeIntegrationIdList(rawList = []) {
  if (!Array.isArray(rawList)) return [];
  const seen = new Set();
  return rawList
    .map((value) => String(value || "").trim())
    .filter((value) => {
      if (!value || seen.has(value)) return false;
      seen.add(value);
      return true;
    });
}

function getDefaultExposedIntegrationIds() {
  return connectionIntegrations.value
    .map((integration) => String(integration.id || "").trim())
    .filter(Boolean);
}

function isIntegrationExposed(integrationId) {
  const lookupId = String(integrationId || "").trim();
  if (!lookupId) return false;
  return normalizeIntegrationIdList(connectionForm.exposed_integration_ids).includes(lookupId);
}

async function setIntegrationExposed(integrationId, enabled) {
  const lookupId = String(integrationId || "").trim();
  if (!lookupId) return;
  const current = new Set(normalizeIntegrationIdList(connectionForm.exposed_integration_ids));
  if (enabled) current.add(lookupId);
  else current.delete(lookupId);
  connectionForm.exposed_integration_ids = Array.from(current);
  await saveConnectionConfig();
}

async function setAllIntegrationExposure(enabled) {
  connectionForm.exposed_integration_ids = enabled ? getDefaultExposedIntegrationIds() : [];
  await saveConnectionConfig();
}

function buildExposedIntegrationsPayload() {
  const knownIntegrationIds = new Set(
    connectionIntegrations.value
      .map((integration) => String(integration.id || "").trim())
      .filter(Boolean)
  );
  return normalizeIntegrationIdList(connectionForm.exposed_integration_ids)
    .filter((integrationId) => knownIntegrationIds.has(integrationId));
}

function isTemplateRuleExplicit(templateKey) {
  const normalizedTemplateKey = normalizeTemplateRuleKey(templateKey);
  if (!normalizedTemplateKey) return false;
  const rules = normalizeTemplateIntegrationRules(connectionForm.template_integration_rules);
  return Object.prototype.hasOwnProperty.call(rules, normalizedTemplateKey);
}

function getTemplateRule(templateKey) {
  const normalizedTemplateKey = normalizeTemplateRuleKey(templateKey);
  if (!normalizedTemplateKey) {
    return buildDefaultTemplateRule(normalizedTemplateKey);
  }
  const rules = normalizeTemplateIntegrationRules(connectionForm.template_integration_rules);
  const rule = rules[normalizedTemplateKey];
  if (!rule) {
    return buildDefaultTemplateRule(normalizedTemplateKey);
  }
  const visibility = normalizeTemplateVisibilityForRule(normalizedTemplateKey, rule.integration_visibility);
  return {
    integration_visibility: visibility,
    integrations_enabled: visibility !== "disabled",
    expected_return_type: normalizeExpectedReturnType(rule.expected_return_type),
  };
}

function isTemplateIntegrationsEnabled(templateKey) {
  return getTemplateRule(templateKey).integration_visibility !== "disabled";
}

function getTemplateIntegrationVisibility(templateKey) {
  return getTemplateRule(templateKey).integration_visibility;
}

function getTemplateExpectedReturnType(templateKey) {
  return getTemplateRule(templateKey).expected_return_type;
}

function setTemplateRuleValue(templateKey, partialRule = {}) {
  const normalizedTemplateKey = normalizeTemplateRuleKey(templateKey);
  if (!normalizedTemplateKey) return;

  const rules = normalizeTemplateIntegrationRules(connectionForm.template_integration_rules);
  const baseRule = getTemplateRule(normalizedTemplateKey);
  const visibility = partialRule.integration_visibility != null
    ? normalizeTemplateVisibilityForRule(normalizedTemplateKey, partialRule.integration_visibility)
    : (
      partialRule.integrations_enabled != null
        ? normalizeTemplateVisibilityForRule(
          normalizedTemplateKey,
          coerceLegacyIntegrationEnabled(partialRule.integrations_enabled, true) ? "enabled" : "disabled"
        )
        : baseRule.integration_visibility
    );
  const nextRule = {
    integration_visibility: visibility,
    integrations_enabled: visibility !== "disabled",
    expected_return_type: normalizeExpectedReturnType(
      partialRule.expected_return_type ?? baseRule.expected_return_type
    ),
  };
  if (isDefaultTemplateRule(normalizedTemplateKey, nextRule)) {
    delete rules[normalizedTemplateKey];
  } else {
    rules[normalizedTemplateKey] = nextRule;
  }
  connectionForm.template_integration_rules = rules;
}

async function setTemplateIntegrationsEnabled(templateKey, enabled) {
  setTemplateRuleValue(templateKey, {
    integration_visibility: enabled ? "enabled" : "disabled",
  });
  await saveConnectionConfig();
}

async function setTemplateIntegrationVisibility(templateKey, visibility) {
  setTemplateRuleValue(templateKey, {
    integration_visibility: normalizeTemplateVisibilityForRule(templateKey, visibility),
  });
  await saveConnectionConfig();
}

async function setTemplateExpectedReturnType(templateKey, expectedReturnType) {
  setTemplateRuleValue(templateKey, {
    expected_return_type: normalizeExpectedReturnType(expectedReturnType),
  });
  await saveConnectionConfig();
}

async function resetTemplateRule(templateKey) {
  const normalizedTemplateKey = normalizeTemplateRuleKey(templateKey);
  if (!normalizedTemplateKey) return;
  const rules = normalizeTemplateIntegrationRules(connectionForm.template_integration_rules);
  if (!Object.prototype.hasOwnProperty.call(rules, normalizedTemplateKey)) return;
  delete rules[normalizedTemplateKey];
  connectionForm.template_integration_rules = rules;
  await saveConnectionConfig();
}

function buildTemplateIntegrationRulesPayload() {
  const knownTemplateKeys = new Set(
    connectionTemplateEntries.value.map((entry) => String(entry.key || "").trim()).filter(Boolean)
  );
  const normalizedRules = normalizeTemplateIntegrationRules(connectionForm.template_integration_rules);
  const payload = {};

  Object.entries(normalizedRules).forEach(([templateKey, rule]) => {
    if (!knownTemplateKeys.has(templateKey)) {
      return;
    }
    const visibility = normalizeTemplateVisibilityForRule(templateKey, rule.integration_visibility);
    payload[templateKey] = {
      integration_visibility: visibility,
      integrations_enabled: visibility !== "disabled",
      expected_return_type: normalizeExpectedReturnType(rule.expected_return_type),
    };
  });

  return payload;
}

function setActiveTab(tab) {
  const target = tabs.find((entry) => entry.id === tab) || tabs[0];
  router.push(target.to);
}

function updateReviewRouteQuery({ integrationId = reviewIntegrationId.value, itemKey = "" } = {}) {
  if (activeTab.value !== "review") return;
  const normalizedIntegrationId = String(integrationId || "").trim();
  const normalizedItemKey = String(itemKey || "").trim();
  const nextQuery = { ...route.query };
  delete nextQuery.integration_id;
  delete nextQuery.item_key;
  if (normalizedIntegrationId) {
    nextQuery.integrationId = normalizedIntegrationId;
  } else {
    delete nextQuery.integrationId;
  }
  if (normalizedItemKey) {
    nextQuery.itemKey = normalizedItemKey;
  } else {
    delete nextQuery.itemKey;
  }
  const currentIntegrationId = String(route.query.integrationId || "").trim();
  const currentItemKey = String(route.query.itemKey || "").trim();
  if (currentIntegrationId === normalizedIntegrationId && currentItemKey === normalizedItemKey) return;
  router.replace({ path: "/admin/integrations/review", query: nextQuery });
}

watch(
  () => activeTab.value,
  async (tab) => {
    if (tab === "manage") {
      await applyManageRouteSelection();
      return;
    }
    if (tab !== "review") return;
    ensureReviewIntegrationSelection();
    if (!reviewIntegrationId.value) return;
    await loadReviewItems();
  },
);

watch(
  () => `${activeTab.value}|${manageRouteIntegrationId.value}|${manageRouteSubsection.value}|${integrations.value.length}`,
  async () => {
    await applyManageRouteSelection();
  },
);

watch(
  () => reviewIntegrationId.value,
  async (nextValue, previousValue) => {
    if (nextValue === previousValue) return;
    resetReviewState({ keepIntegration: true });
    reviewStateFilter.value = "";
    reviewTagFilter.value = "";
    const requestedItemKey = String(
      nextValue && nextValue === reviewRouteIntegrationId.value ? reviewRouteItemKey.value : ""
    ).trim();
    updateReviewRouteQuery({ integrationId: nextValue, itemKey: requestedItemKey });
    if (requestedItemKey) {
      reviewSelectedItemKey.value = requestedItemKey;
    }
    if (!nextValue || activeTab.value !== "review") return;
    await loadReviewItems({ preserveSelection: false });
  },
);

watch(
  () => `${activeTab.value}|${reviewRouteIntegrationId.value}|${reviewRouteItemKey.value}`,
  async () => {
    if (activeTab.value !== "review") return;
    const requestedIntegrationId = reviewRouteIntegrationId.value;
    const requestedItemKey = reviewRouteItemKey.value;
    if (requestedIntegrationId && requestedIntegrationId !== String(reviewIntegrationId.value || "").trim()) {
      ensureReviewIntegrationSelection();
      return;
    }
    if (requestedItemKey && requestedItemKey !== String(reviewSelectedItemKey.value || "").trim()) {
      reviewSelectedItemKey.value = requestedItemKey;
      if (reviewIntegrationId.value) {
        await loadReviewItems({ preserveSelection: true });
      }
    }
  },
);

watch(
  () => reviewIntegrationOptions.value.map((integration) => String(integration?.id || "").trim()).join("|"),
  () => {
    if (activeTab.value !== "review") return;
    ensureReviewIntegrationSelection();
  },
);

watch(
  () => containerForm.sources.map((source) => String(source.integration_id || "").trim()).join("|"),
  () => {
    containerForm.target_source_integration_id = normalizeTargetSourceSelection(
      containerForm.sources,
      containerForm.target_source_integration_id,
    );
    void autoApplyContainerPrimeKeys(
      containerForm.sources,
      containerForm.target_source_integration_id,
    );
  },
);

watch(
  () => inlineContainerForm.sources.map((source) => String(source.integration_id || "").trim()).join("|"),
  () => {
    inlineContainerForm.target_source_integration_id = normalizeTargetSourceSelection(
      inlineContainerForm.sources,
      inlineContainerForm.target_source_integration_id,
    );
    void autoApplyContainerPrimeKeys(
      inlineContainerForm.sources,
      inlineContainerForm.target_source_integration_id,
    );
  },
);

watch(
  () => String(containerForm.target_source_integration_id || "").trim(),
  () => {
    void autoApplyContainerPrimeKeys(
      containerForm.sources,
      containerForm.target_source_integration_id,
    );
  },
);

watch(
  () => String(inlineContainerForm.target_source_integration_id || "").trim(),
  () => {
    void autoApplyContainerPrimeKeys(
      inlineContainerForm.sources,
      inlineContainerForm.target_source_integration_id,
    );
  },
);

watch(
  () => manageNavigatorVisibleIds.value.join("|"),
  () => {
    const visibleIds = new Set(manageNavigatorVisibleIds.value);

    const activeInlineId = String(inlineEditId.value || "").trim();
    if (activeInlineId && !visibleIds.has(activeInlineId)) {
      cancelInlineEdit(activeInlineId, { scroll: false });
    }

    const lastNavigatedId = String(lastNavigatedIntegrationId.value || "").trim();
    if (lastNavigatedId && !visibleIds.has(lastNavigatedId)) {
      lastNavigatedIntegrationId.value = "";
    }
  },
  { immediate: true },
);

watch(
  () => `${activeTab.value}|${selectedManageIntegration.value?.id || ""}`,
  () => {
    if (activeTab.value !== "manage") return;
    const integration = selectedManageIntegration.value;
    const selectedId = String(integration?.id || "").trim();
    if (!selectedId) return;
    if (String(inlineEditId.value || "").trim() === selectedId) return;
    startInlineEdit(integration);
  },
  { immediate: true },
);

async function loadIntegrations() {
  try {
    const loadedIntegrations = await api.listIntegrations();
    integrations.value = Array.isArray(loadedIntegrations)
      ? loadedIntegrations.map((integration) => ({
          ...integration,
          type: normalizeIntegrationType(integration?.type),
          favorite: Boolean(integration?.favorite),
          item_page_sync_blocked: Boolean(integration?.item_page_sync_blocked),
        }))
      : [];
    const knownIntegrationIds = new Set(
      integrations.value
        .map((integration) => String(integration?.id || "").trim())
        .filter(Boolean),
    );
    Object.keys(integrationPrimeKeyOptionsById).forEach((integrationId) => {
      if (knownIntegrationIds.has(integrationId)) return;
      delete integrationPrimeKeyOptionsById[integrationId];
      delete integrationPrimeKeyLoadingById[integrationId];
      integrationPrimeKeyRequestsById.delete(integrationId);
    });
    if (
      selectedContainerTag.value
      && !availableContainerTags.value.includes(selectedContainerTag.value)
    ) {
      selectedContainerTag.value = "";
    }
    if (
      selectedReturnType.value
      && !availableReturnTypes.value.includes(selectedReturnType.value)
    ) {
      selectedReturnType.value = "";
    }
  } catch (err) {
    console.error("Failed to load integrations:", err);
    integrations.value = [];
  } finally {
    loading.value = false;
  }
}

async function loadConnectionTemplates() {
  connectionTemplatesLoading.value = true;
  try {
    const [sectionTypesResult, sectionTemplatesResult, pageTemplatesResult] = await Promise.allSettled([
      api.getSectionTypes(),
      api.listSectionTemplates(),
      api.listPageTemplates(),
    ]);

    if (sectionTypesResult.status === "fulfilled") {
      const rawTypes = Array.isArray(sectionTypesResult.value?.types)
        ? sectionTypesResult.value.types
        : [];
      const normalizedTypes = rawTypes
        .map((entry) => normalizeSectionTypeValue(entry?.type, ""))
        .filter(Boolean);
      connectionSectionTypes.value = normalizedTypes.length
        ? Array.from(new Set(normalizedTypes)).sort((a, b) => a.localeCompare(b))
        : [...DEFAULT_SECTION_TYPES];
    } else {
      connectionSectionTypes.value = [...DEFAULT_SECTION_TYPES];
      console.error("Failed to load section types:", sectionTypesResult.reason);
    }

    if (sectionTemplatesResult.status === "fulfilled") {
      connectionSectionTemplates.value = Array.isArray(sectionTemplatesResult.value?.templates)
        ? sectionTemplatesResult.value.templates
        : [];
    } else {
      connectionSectionTemplates.value = [];
      console.error("Failed to load section templates:", sectionTemplatesResult.reason);
    }

    if (pageTemplatesResult.status === "fulfilled") {
      connectionPageTemplates.value = Array.isArray(pageTemplatesResult.value?.templates)
        ? pageTemplatesResult.value.templates
        : [];
    } else {
      connectionPageTemplates.value = [];
      console.error("Failed to load page templates:", pageTemplatesResult.reason);
    }
  } finally {
    connectionTemplatesLoading.value = false;
  }
}

async function loadConnectionConfig() {
  try {
    const config = await api.getIntegrationConnectionConfig();
    connectionForm.exposed_integration_ids = normalizeIntegrationIdList(
      config?.exposed_integration_ids,
    );
    connectionForm.template_integration_rules = normalizeTemplateIntegrationRules(
      config?.template_integration_rules,
    );
    setConnectionAutosaveStatus("idle");
  } catch (err) {
    console.error("Failed to load integration connection config:", err);
    connectionForm.exposed_integration_ids = [];
    connectionForm.template_integration_rules = {};
  }
}

async function saveConnectionConfig() {
  if (connectionSaving.value) {
    connectionSaveQueued.value = true;
    setConnectionAutosaveStatus("queued");
    return;
  }
  connectionSaving.value = true;
  setConnectionAutosaveStatus("saving");
  let saveFailed = false;
  try {
    do {
      connectionSaveQueued.value = false;
      try {
        const updated = await api.updateIntegrationConnectionConfig({
          exposed_integration_ids: buildExposedIntegrationsPayload(),
          template_integration_rules: buildTemplateIntegrationRulesPayload(),
        });
        if (!connectionSaveQueued.value) {
          connectionForm.exposed_integration_ids = normalizeIntegrationIdList(
            updated?.exposed_integration_ids,
          );
          connectionForm.template_integration_rules = normalizeTemplateIntegrationRules(
            updated?.template_integration_rules,
          );
        }
      } catch (err) {
        saveFailed = true;
        setConnectionAutosaveStatus("error", err?.message || "Failed to save connection settings");
        if (!connectionSaveQueued.value) {
          break;
        }
      }
    } while (connectionSaveQueued.value);
    if (!saveFailed) {
      setConnectionAutosaveStatus("saved");
    }
  } finally {
    connectionSaving.value = false;
  }
}

function resetReviewState({ keepIntegration = false } = {}) {
  reviewItemsSummary.value = null;
  reviewItems.value = [];
  reviewSelectedItemKey.value = "";
  reviewItemDetail.value = null;
  reviewStatus.value = null;
  reviewTagDraft.value = "";
  reviewItemSearchQuery.value = "";
  reviewAddItemOpen.value = false;
  reviewShowOutputColumns.value = false;
  Object.keys(reviewFieldDrafts).forEach((key) => delete reviewFieldDrafts[key]);
  Object.keys(reviewFieldSaving).forEach((key) => delete reviewFieldSaving[key]);
  Object.keys(reviewAddItemDrafts).forEach((key) => delete reviewAddItemDrafts[key]);
  if (!keepIntegration) {
    reviewIntegrationId.value = "";
    reviewStateFilter.value = "";
    reviewTagFilter.value = "";
  }
}

function ensureReviewIntegrationSelection() {
  const currentId = String(reviewIntegrationId.value || "").trim();
  const availableIds = new Set(
    reviewIntegrationOptions.value
      .map((integration) => String(integration?.id || "").trim())
      .filter(Boolean)
  );
  const requestedId = reviewRouteIntegrationId.value;
  if (requestedId && availableIds.has(requestedId)) {
    reviewIntegrationId.value = requestedId;
    return;
  }
  if (currentId && availableIds.has(currentId)) return;
  const exposedIds = normalizeIntegrationIdList(connectionForm.exposed_integration_ids);
  const firstExposedId = exposedIds.find((integrationId) => availableIds.has(integrationId));
  reviewIntegrationId.value = firstExposedId || reviewIntegrationOptions.value[0]?.id || "";
}

function syncReviewDrafts() {
  Object.keys(reviewFieldDrafts).forEach((key) => delete reviewFieldDrafts[key]);
  reviewItemFields.value.forEach((field) => {
    const path = String(field?.path || "").trim();
    if (!path) return;
    syncReviewFieldDraft(field);
  });
}

function getReviewFieldDraftSource(field) {
  if (field?.has_override) {
    return { value: field.local_value, hasValue: true };
  }
  if (field?.has_effective_value) {
    return { value: field.effective_value, hasValue: true };
  }
  if (field?.has_current_value) {
    return { value: field.current_value, hasValue: true };
  }
  return { value: undefined, hasValue: false };
}

function syncReviewFieldDraft(field) {
  const path = String(field?.path || "").trim();
  if (!path) return;
  const source = getReviewFieldDraftSource(field);
  if (!source.hasValue) {
    reviewFieldDrafts[path] = shouldUseReviewMultipleOptionsSelect(field) ? [] : "";
    return;
  }
  if (shouldUseReviewMultipleOptionsSelect(field)) {
    reviewFieldDrafts[path] = getReviewMultiOptionDraftValues(field, source.value);
    return;
  }
  reviewFieldDrafts[path] = isReviewDateField(field)
    ? (localDateToServerDateOnly(source.value) || stringifyReviewDraftValue(source.value))
    : (
      isReviewDatetimeField(field)
        ? (toDateTimeLocalDraft(source.value) || stringifyReviewDraftValue(source.value))
        : stringifyReviewDraftValue(source.value)
    );
}

function syncReviewAddDrafts() {
  const knownPaths = new Set(reviewSchemaFields.value.map((field) => String(field?.path || "").trim()).filter(Boolean));
  Object.keys(reviewAddItemDrafts).forEach((key) => {
    if (!knownPaths.has(key)) {
      delete reviewAddItemDrafts[key];
    }
  });
  reviewSchemaFields.value.forEach((field) => {
    const path = String(field?.path || "").trim();
    if (!path || Object.prototype.hasOwnProperty.call(reviewAddItemDrafts, path)) return;
    reviewAddItemDrafts[path] = shouldUseReviewMultipleOptionsSelect(field)
      ? []
      : (getSchemaInputType(field) === "checkbox" ? false : "");
  });
}

async function refreshReviewNavigator({ preserveSelection = true } = {}) {
  const integrationId = String(reviewIntegrationId.value || "").trim();
  if (!integrationId) return;
  const response = await api.listIntegrationReviewItems(integrationId, {
    state: reviewStateFilter.value,
    tag: reviewTagFilter.value,
  });
  reviewItemsSummary.value = response;
  reviewItems.value = Array.isArray(response?.items) ? response.items : [];
  if (reviewAddItemOpen.value) {
    syncReviewAddDrafts();
  }
  if (!preserveSelection) {
    reviewSelectedItemKey.value = String(reviewItems.value[0]?.item_key || "").trim();
  }
}

async function loadReviewItems({ preserveSelection = true } = {}) {
  const integrationId = String(reviewIntegrationId.value || "").trim();
  if (!integrationId) {
    resetReviewState({ keepIntegration: true });
    return;
  }
  reviewItemsLoading.value = true;
  reviewStatus.value = null;
  try {
    await refreshReviewNavigator({ preserveSelection: true });
    const existingKey = String(reviewSelectedItemKey.value || "").trim();
    const requestedItemKey = (
      reviewRouteIntegrationId.value === integrationId
      || !reviewRouteIntegrationId.value
    )
      ? reviewRouteItemKey.value
      : "";
    const nextKey = (
      preserveSelection && reviewItems.value.some((item) => String(item?.item_key || "") === existingKey)
        ? existingKey
        : requestedItemKey || String(reviewItems.value[0]?.item_key || "").trim()
    );
    reviewSelectedItemKey.value = nextKey;
    updateReviewRouteQuery({ integrationId, itemKey: nextKey });
    if (nextKey) {
      await loadReviewItem(nextKey);
    } else {
      reviewItemDetail.value = null;
      syncReviewDrafts();
    }
  } catch (err) {
    reviewItemsSummary.value = null;
    reviewItems.value = [];
    reviewItemDetail.value = null;
    reviewStatus.value = { type: "error", message: err.message || "Failed to load review items." };
  } finally {
    reviewItemsLoading.value = false;
  }
}

async function loadReviewItem(itemKey) {
  const integrationId = String(reviewIntegrationId.value || "").trim();
  const normalizedItemKey = String(itemKey || "").trim();
  if (!integrationId || !normalizedItemKey) {
    reviewItemDetail.value = null;
    syncReviewDrafts();
    return;
  }
  reviewItemLoading.value = true;
  reviewStatus.value = null;
  try {
    reviewItemDetail.value = await api.getIntegrationReviewItem(integrationId, normalizedItemKey);
    reviewSelectedItemKey.value = normalizedItemKey;
    reviewTagDraft.value = "";
    syncReviewDrafts();
  } catch (err) {
    reviewItemDetail.value = null;
    reviewStatus.value = { type: "error", message: err.message || "Failed to load review item." };
  } finally {
    reviewItemLoading.value = false;
  }
}

function mergeIntegrationIntoList(updatedIntegration) {
  const integrationId = String(updatedIntegration?.id || "").trim();
  if (!integrationId) return;
  const normalizedIntegration = {
    ...updatedIntegration,
    type: normalizeIntegrationType(updatedIntegration?.type),
    favorite: Boolean(updatedIntegration?.favorite),
    item_page_sync_blocked: Boolean(updatedIntegration?.item_page_sync_blocked),
  };
  const index = integrations.value.findIndex((integration) =>
    String(integration?.id || "").trim() === integrationId
  );
  if (index >= 0) {
    integrations.value.splice(index, 1, {
      ...integrations.value[index],
      ...normalizedIntegration,
    });
  } else {
    integrations.value.push(normalizedIntegration);
  }
}

async function setReviewItemPageSyncBlocked(event) {
  const integrationId = String(reviewIntegrationId.value || "").trim();
  const checked = Boolean(event?.target?.checked);
  const previous = reviewItemPageSyncBlocked.value;
  if (!integrationId || reviewItemPageSyncSaving.value) {
    if (event?.target) event.target.checked = previous;
    return;
  }

  reviewItemPageSyncSaving.value = true;
  reviewStatus.value = null;
  try {
    const updatedIntegration = await api.updateIntegrationReviewSyncSettings(integrationId, {
      item_page_sync_blocked: checked,
    });
    mergeIntegrationIntoList(updatedIntegration);
    if (reviewItemsSummary.value) {
      reviewItemsSummary.value.item_page_sync_blocked = Boolean(updatedIntegration?.item_page_sync_blocked);
    }
    await refreshReviewNavigator({ preserveSelection: true });
    if (reviewSelectedItemKey.value) {
      await loadReviewItem(reviewSelectedItemKey.value);
    }
    reviewStatus.value = {
      type: "success",
      message: checked ? "Item page syncing blocked." : "Item page syncing enabled.",
    };
  } catch (err) {
    if (event?.target) event.target.checked = previous;
    reviewStatus.value = { type: "error", message: err.message || "Failed to update item page sync setting." };
  } finally {
    reviewItemPageSyncSaving.value = false;
  }
}

async function selectReviewItem(itemKey) {
  const normalizedItemKey = String(itemKey || "").trim();
  if (!normalizedItemKey) return;
  if (
    !reviewAddItemOpen.value
    && normalizedItemKey === String(reviewSelectedItemKey.value || "").trim()
    && reviewItemDetail.value
  ) {
    return;
  }
  reviewAddItemOpen.value = false;
  reviewSelectedItemKey.value = normalizedItemKey;
  updateReviewRouteQuery({ integrationId: reviewIntegrationId.value, itemKey: normalizedItemKey });
  await loadReviewItem(normalizedItemKey);
}

async function reloadReviewItem() {
  if (reviewSelectedItemKey.value) {
    await loadReviewItem(reviewSelectedItemKey.value);
  }
}

function buildReviewNavigatorPatchFromDetail(detail, existing = {}) {
  const fields = Array.isArray(detail?.fields) ? detail.fields : [];
  const overrideCount = fields.filter((field) => Boolean(field?.has_override)).length;
  return {
    ...existing,
    item_key: detail?.item_key || existing.item_key,
    label: detail?.label || existing.label || detail?.item_key,
    is_local_item: Boolean(detail?.is_local_item ?? existing.is_local_item),
    is_incomplete: Boolean(detail?.is_incomplete),
    missing_required_paths: Array.isArray(detail?.missing_required_paths)
      ? detail.missing_required_paths
      : [],
    state: detail?.state || existing.state || "open",
    tags: Array.isArray(detail?.tags) ? detail.tags : (Array.isArray(existing.tags) ? existing.tags : []),
    review_updated_at: detail?.review_updated_at ?? existing.review_updated_at,
    has_override: overrideCount > 0,
    override_count: overrideCount,
    has_conflict: fields.some((field) => Boolean(field?.has_conflict)),
    generated_pages: Array.isArray(detail?.generated_pages)
      ? detail.generated_pages
      : (Array.isArray(existing.generated_pages) ? existing.generated_pages : []),
    has_generated_page: Boolean(detail?.has_generated_page ?? existing.has_generated_page),
    has_missing_generated_page: Boolean(detail?.has_missing_generated_page ?? existing.has_missing_generated_page),
    has_non_syncing_generated_page: Boolean(
      detail?.has_non_syncing_generated_page ?? existing.has_non_syncing_generated_page
    ),
  };
}

function updateReviewNavigatorItemFromDetail(detail) {
  const itemKey = String(detail?.item_key || "").trim();
  if (!itemKey) return;
  const index = reviewItems.value.findIndex((item) => String(item?.item_key || "").trim() === itemKey);
  if (index === -1) return;
  reviewItems.value.splice(index, 1, buildReviewNavigatorPatchFromDetail(detail, reviewItems.value[index]));
}

function applyReviewItemFieldResponse(nextDetail, fieldPath) {
  const normalizedPath = String(fieldPath || "").trim();
  if (!nextDetail || !normalizedPath) return;
  if (!reviewItemDetail.value || reviewItemDetail.value.item_key !== nextDetail.item_key) {
    reviewItemDetail.value = nextDetail;
    syncReviewDrafts();
    updateReviewNavigatorItemFromDetail(nextDetail);
    return;
  }

  const nextFields = Array.isArray(nextDetail.fields) ? nextDetail.fields : [];
  const nextField = nextFields.find((field) => String(field?.path || "").trim() === normalizedPath);
  const currentFields = Array.isArray(reviewItemDetail.value.fields) ? reviewItemDetail.value.fields : [];
  const mergedFields = currentFields.map((field) =>
    String(field?.path || "").trim() === normalizedPath && nextField ? nextField : field
  );
  if (nextField && !mergedFields.some((field) => String(field?.path || "").trim() === normalizedPath)) {
    mergedFields.push(nextField);
    mergedFields.sort((left, right) => String(left?.path || "").localeCompare(String(right?.path || "")));
  }

  reviewItemDetail.value = {
    ...reviewItemDetail.value,
    label: nextDetail.label,
    is_local_item: Boolean(nextDetail.is_local_item),
    is_incomplete: Boolean(nextDetail.is_incomplete),
    missing_required_paths: Array.isArray(nextDetail.missing_required_paths)
      ? nextDetail.missing_required_paths
      : [],
    state: nextDetail.state,
    tags: Array.isArray(nextDetail.tags) ? nextDetail.tags : [],
    review_updated_at: nextDetail.review_updated_at,
    output_primary_key_path: nextDetail.output_primary_key_path,
    fetched_at: nextDetail.fetched_at,
    previous_fetched_at: nextDetail.previous_fetched_at,
    current_item: nextDetail.current_item,
    previous_item: nextDetail.previous_item,
    effective_item: nextDetail.effective_item,
    item_page_template_count: nextDetail.item_page_template_count,
    item_page_templates_active: Boolean(nextDetail.item_page_templates_active),
    generated_pages: Array.isArray(nextDetail.generated_pages) ? nextDetail.generated_pages : [],
    has_generated_page: Boolean(nextDetail.has_generated_page),
    has_missing_generated_page: Boolean(nextDetail.has_missing_generated_page),
    has_non_syncing_generated_page: Boolean(nextDetail.has_non_syncing_generated_page),
    fields: mergedFields,
  };

  if (nextField) {
    syncReviewFieldDraft(nextField);
  }
  updateReviewNavigatorItemFromDetail(reviewItemDetail.value);
}

function toggleReviewAddItem() {
  reviewAddItemOpen.value = !reviewAddItemOpen.value;
  if (reviewAddItemOpen.value) {
    syncReviewAddDrafts();
  }
}

function toggleReviewOutputColumns() {
  reviewShowOutputColumns.value = !reviewShowOutputColumns.value;
}

function cancelReviewAddItem() {
  reviewAddItemOpen.value = false;
}

async function saveReviewItemMeta(nextMeta) {
  const integrationId = String(reviewIntegrationId.value || "").trim();
  const itemKey = String(reviewItemDetail.value?.item_key || reviewSelectedItemKey.value || "").trim();
  if (!integrationId || !itemKey) return;
  reviewMetaSaving.value = true;
  reviewStatus.value = null;
  try {
    const nextDetail = await api.updateIntegrationReviewItemMeta(integrationId, {
      item_key: itemKey,
      ...nextMeta,
    });
    reviewItemDetail.value = nextDetail;
    const updatedItemKey = nextDetail?.item_key != null
      ? String(nextDetail.item_key).trim()
      : itemKey;
    reviewSelectedItemKey.value = updatedItemKey;
    syncReviewDrafts();
    updateReviewNavigatorItemFromDetail(nextDetail);
    try {
      await refreshReviewNavigator({ preserveSelection: true });
    } catch (refreshErr) {
      console.error("Failed to refresh review navigator:", refreshErr);
    }
  } catch (err) {
    reviewStatus.value = { type: "error", message: err.message || "Failed to update review metadata." };
  } finally {
    reviewMetaSaving.value = false;
  }
}

async function setReviewItemState(state) {
  await saveReviewItemMeta({ state: String(state || "open").trim() || "open" });
}

async function addReviewItemTag() {
  const nextTag = String(reviewTagDraft.value || "").trim();
  if (!nextTag || !reviewItemDetail.value) return;
  const currentTags = Array.isArray(reviewItemDetail.value.tags) ? reviewItemDetail.value.tags : [];
  const seen = new Set(currentTags.map((tag) => String(tag || "").trim().toLowerCase()).filter(Boolean));
  if (seen.has(nextTag.toLowerCase())) {
    reviewTagDraft.value = "";
    return;
  }
  reviewTagDraft.value = "";
  await saveReviewItemMeta({ tags: [...currentTags, nextTag] });
}

async function removeReviewItemTag(tag) {
  if (!reviewItemDetail.value) return;
  const removeToken = String(tag || "").trim().toLowerCase();
  const nextTags = (Array.isArray(reviewItemDetail.value.tags) ? reviewItemDetail.value.tags : [])
    .filter((entry) => String(entry || "").trim().toLowerCase() !== removeToken);
  await saveReviewItemMeta({ tags: nextTags });
}

function formatReviewState(state) {
  const normalized = String(state || "open").trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (normalized === "in_progress") return "In progress";
  if (normalized === "done") return "Done";
  return "Open";
}

function getReviewItemGeneratedPages(item) {
  return Array.isArray(item?.generated_pages)
    ? item.generated_pages.filter((page) => page && typeof page === "object")
    : [];
}

function normalizeReviewGeneratedPageStatus(status) {
  const normalized = String(status || "").trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (["init", "hidden", "published", "under_construction", "unknown"].includes(normalized)) {
    return normalized;
  }
  return "unknown";
}

function formatReviewGeneratedPageStatus(status) {
  const normalized = normalizeReviewGeneratedPageStatus(status);
  if (normalized === "init") return "Init";
  if (normalized === "hidden") return "Hidden";
  if (normalized === "published") return "Published";
  if (normalized === "under_construction") return "Under construction";
  return "Unknown";
}

function formatReviewGeneratedPageBadge(page) {
  if (!page?.exists) return "No page";
  const statusLabel = formatReviewGeneratedPageStatus(page.status);
  if (page.syncs_with_review_overrides) return `Page: ${statusLabel}`;
  return page.item_page_sync_blocked
    ? `Page: ${statusLabel} / blocked`
    : `Page: ${statusLabel} / locked`;
}

function formatReviewGeneratedPageChipStatus(page) {
  if (!page?.exists) return "No generated page";
  const statusLabel = formatReviewGeneratedPageStatus(page.status);
  if (page.syncs_with_review_overrides) return `${statusLabel} / syncing`;
  return page.item_page_sync_blocked
    ? `${statusLabel} / blocked`
    : `${statusLabel} / locked`;
}

function getReviewGeneratedPageBadgeClass(page) {
  const status = normalizeReviewGeneratedPageStatus(page?.status);
  return {
    "page-missing": !page?.exists,
    "page-syncing": Boolean(page?.exists && page?.syncs_with_review_overrides),
    "page-locked": Boolean(page?.exists && !page?.syncs_with_review_overrides),
    [`page-status-${status}`]: Boolean(page?.exists),
  };
}

function getReviewGeneratedPageTitle(page) {
  const templateLabel = String(page?.template_label || page?.template_name || "Item page").trim();
  if (!page?.exists) {
    return `${templateLabel}: no generated page exists.`;
  }
  const slug = String(page?.slug || "").trim();
  const status = formatReviewGeneratedPageStatus(page.status);
  const effectiveStatus = page?.effective_status
    ? `, effective ${formatReviewGeneratedPageStatus(page.effective_status)}`
    : "";
  const syncability = page.item_page_sync_blocked
    ? "item page syncing is blocked"
    : page.syncs_with_review_overrides
      ? "review overrides sync to this item page"
      : "review overrides are locked";
  return `${templateLabel}${slug ? ` (${slug})` : ""}: ${status}${effectiveStatus}; ${syncability}.`;
}

function normalizeReviewGeneratedPageSlug(page) {
  return String(page?.slug || "").trim().replace(/^\/+|\/+$/g, "");
}

function formatReviewGeneratedPageRoute(page) {
  const slug = normalizeReviewGeneratedPageSlug(page);
  return slug ? `/${slug}` : "";
}

function canOpenReviewGeneratedPage(page) {
  return Boolean(page?.exists && normalizeReviewGeneratedPageSlug(page));
}

function getReviewGeneratedPageHref(page) {
  const slug = normalizeReviewGeneratedPageSlug(page);
  if (!slug) return "";
  return router.resolve({ path: `/${slug}` }).href;
}

function openReviewGeneratedPage(page) {
  const href = getReviewGeneratedPageHref(page);
  if (!href) return;
  window.open(href, "_blank", "noopener,noreferrer");
}

function getManageSubsectionKey(integration) {
  return String(integration?.id || inlineEditId.value || "").trim();
}

function getManageSubsectionIcon(subsection) {
  const key = String(subsection || "").trim();
  return MANAGE_SUBSECTIONS.find((entry) => entry.key === key)?.icon || faCircleQuestion;
}

function getManageSubsection(integration) {
  const key = getManageSubsectionKey(integration);
  const value = Object.prototype.hasOwnProperty.call(manageSubsectionById, key)
    ? String(manageSubsectionById[key] || "").trim()
    : "";
  return MANAGE_SUBSECTION_KEYS.has(value) ? value : "";
}

function isManageSubsectionOpen(integration, subsection) {
  return getManageSubsection(integration) === subsection;
}

async function setManageSubsection(integration, subsection, options = {}) {
  const key = getManageSubsectionKey(integration);
  const requestedSection = String(subsection || "").trim();
  if (!key || !MANAGE_SUBSECTION_KEYS.has(requestedSection)) return;
  const currentSection = getManageSubsection(integration);
  const shouldToggleActive = options.toggleActive !== false;
  const nextSection = shouldToggleActive && currentSection === requestedSection
    ? ""
    : requestedSection;
  if (key) {
    manageSubsectionById[key] = nextSection;
  }
  if (options.scroll !== false) {
    await scrollToManageSubsectionHeader(key, requestedSection);
  }
  if (nextSection === "schema") {
    const integrationId = String(integration?.id || "").trim();
    if (integrationId && manageSchemaIntegrationId.value !== integrationId) {
      await loadManageSchema(integrationId);
    }
  }
}

async function toggleManageSchema(integration) {
  const integrationId = String(integration?.id || "").trim();
  if (!integrationId) {
    manageSchemaIntegrationId.value = "";
    manageSchema.value = null;
    return;
  }
  if (manageSchemaIntegrationId.value === integrationId) {
    manageSchemaIntegrationId.value = "";
    manageSchema.value = null;
    manageSchemaStatus.value = null;
    return;
  }
  manageSchemaIntegrationId.value = integrationId;
  await loadManageSchema(integrationId);
}

async function loadManageSchema(integrationId = manageSchemaIntegrationId.value, options = {}) {
  const normalizedIntegrationId = String(integrationId || "").trim();
  if (!normalizedIntegrationId) {
    manageSchema.value = null;
    return;
  }
  manageSchemaIntegrationId.value = normalizedIntegrationId;
  manageSchemaLoading.value = true;
  if (!options.preserveStatus) {
    manageSchemaStatus.value = null;
  }
  try {
    manageSchema.value = await api.getIntegrationSchema(normalizedIntegrationId);
  } catch (err) {
    manageSchema.value = null;
    manageSchemaStatus.value = { type: "error", message: err.message || "Failed to load schema." };
  } finally {
    manageSchemaLoading.value = false;
  }
}

async function updateManageSchemaField(path, payload) {
  const integrationId = String(manageSchemaIntegrationId.value || "").trim();
  const normalizedPath = String(path || "").trim();
  if (!integrationId) return null;
  if (!normalizedPath) return null;
  manageSchemaSaving[normalizedPath] = true;
  manageSchemaStatus.value = null;
  try {
    manageSchema.value = await api.updateIntegrationSchema(integrationId, payload);
    return manageSchema.value;
  } catch (err) {
    manageSchemaStatus.value = { type: "error", message: err.message || "Failed to update schema field." };
    return null;
  } finally {
    manageSchemaSaving[normalizedPath] = false;
  }
}

function isManageSchemaImageField(field) {
  return getSchemaFieldType(field) === "image";
}

async function setManageSchemaItemLabelPath(path) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return;
  await updateManageSchemaField(normalizedPath, {
    item_label_path: normalizedPath,
  });
}

async function setManageSchemaOutputPrimaryKeyPath(path) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return;
  const updatedSchema = await updateManageSchemaField(normalizedPath, {
    output_primary_key_path: normalizedPath,
  });
  if (updatedSchema) {
    inlineForm.output_primary_key_path = normalizedPath;
    await loadIntegrations();
  }
}

async function setManageSchemaPageSlugPath(path) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return;
  await updateManageSchemaField(normalizedPath, {
    page_slug_path: normalizedPath,
  });
}

async function setManageSchemaFieldType(path, fieldType) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return;
  const normalizedType = String(fieldType || "").trim();
  await updateManageSchemaField(normalizedPath, {
    manual_types: {
      [normalizedPath]: normalizedType || null,
    },
  });
}

async function setManageSchemaFieldCollectOptions(path, enabled) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return;
  await updateManageSchemaField(normalizedPath, {
    collect_options: {
      [normalizedPath]: Boolean(enabled),
    },
  });
}

async function setManageSchemaFieldCacheMedia(path, enabled) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return;
  await updateManageSchemaField(normalizedPath, {
    cache_media: {
      [normalizedPath]: Boolean(enabled),
    },
  });
}

async function setManageSchemaFieldRequired(path, enabled) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return;
  const integrationId = String(manageSchemaIntegrationId.value || "").trim();
  const updatedSchema = await updateManageSchemaField(normalizedPath, {
    required_fields: {
      [normalizedPath]: Boolean(enabled),
    },
  });
  if (updatedSchema && integrationId && integrationId === String(reviewIntegrationId.value || "").trim()) {
    await loadReviewItems({ preserveSelection: true });
  }
}

function getSchemaFieldType(field) {
  return String(field?.schema_type || field?.effective_type || field?.detected_type || "undefined").trim().toLowerCase();
}

function getSchemaInputType(field) {
  const type = getSchemaFieldType(field);
  if (type === "number") return "number";
  if (type === "boolean") return "checkbox";
  if (type === "date" || type === "datetime") return "text";
  if (type === "url" || type === "image") return "url";
  if (type === "json" || type === "list") return "textarea";
  return "text";
}

function getReviewFieldPath(field) {
  return String(field?.path || "").trim();
}

function getReviewSchemaField(path) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return null;
  return reviewSchemaFields.value.find((field) => getReviewFieldPath(field) === normalizedPath) || null;
}

function getReviewOptionsMapValue(source, path) {
  const normalizedPath = String(path || "").trim();
  const options = source?.options;
  if (!normalizedPath || !options || typeof options !== "object" || Array.isArray(options)) return [];
  return Array.isArray(options[normalizedPath]) ? options[normalizedPath] : [];
}

function getReviewOptionTypeMapValue(source, path) {
  const normalizedPath = String(path || "").trim();
  const optionTypes = source?.option_types;
  if (!normalizedPath || !optionTypes || typeof optionTypes !== "object" || Array.isArray(optionTypes)) return "";
  return String(optionTypes[normalizedPath] || "").trim();
}

function normalizeReviewOptionType(rawValue) {
  const value = String(rawValue || "").trim().toLowerCase();
  if (["multi_choice", "multi", "list"].includes(value)) return "multi_choice";
  if (["single_choice", "single", "scalar"].includes(value)) return "single_choice";
  return "";
}

function reviewFieldCollectsOptions(field) {
  const path = getReviewFieldPath(field);
  const schemaField = getReviewSchemaField(path);
  return Boolean(field?.collect_options || schemaField?.collect_options);
}

function getRawReviewFieldOptions(field) {
  const path = getReviewFieldPath(field);
  if (!path || !reviewFieldCollectsOptions(field)) return [];
  if (Array.isArray(field?.options) && field.options.length > 0) return field.options;
  const schemaField = getReviewSchemaField(path);
  if (Array.isArray(schemaField?.options) && schemaField.options.length > 0) return schemaField.options;
  const detailOptions = getReviewOptionsMapValue(reviewItemDetail.value, path);
  if (detailOptions.length > 0) return detailOptions;
  return getReviewOptionsMapValue(reviewItemsSummary.value, path);
}

function getReviewFieldOptions(field) {
  const seen = new Set();
  return getRawReviewFieldOptions(field)
    .map((rawValue, index) => {
      const value = stringifyReviewDraftValue(rawValue);
      const token = `${typeof rawValue}:${value}`;
      if (rawValue === undefined || rawValue === null || value.trim() === "" || seen.has(token)) return null;
      seen.add(token);
      return {
        key: `${getReviewFieldPath(field)}-${index}-${token}`,
        value,
        label: formatReviewValue(rawValue, true),
        rawValue,
      };
    })
    .filter(Boolean);
}

function getReviewFieldOptionType(field) {
  const path = getReviewFieldPath(field);
  const schemaField = getReviewSchemaField(path);
  return normalizeReviewOptionType(field?.option_type)
    || normalizeReviewOptionType(schemaField?.option_type)
    || normalizeReviewOptionType(getReviewOptionTypeMapValue(reviewItemDetail.value, path))
    || normalizeReviewOptionType(getReviewOptionTypeMapValue(reviewItemsSummary.value, path))
    || "single_choice";
}

function shouldUseReviewMultipleOptionsSelect(field) {
  return shouldUseReviewOptionsSelect(field) && getReviewFieldOptionType(field) === "multi_choice";
}

function getReviewOptionsSelectSize(field) {
  if (!shouldUseReviewMultipleOptionsSelect(field)) return undefined;
  return Math.min(8, Math.max(3, getReviewFieldOptions(field).length));
}

function getReviewMatchedOption(field, rawValue) {
  const value = stringifyReviewDraftValue(rawValue);
  return getReviewFieldOptions(field).find((option) => option.value === value) || null;
}

function getReviewMatchedOptions(field, rawValue) {
  const selectedValues = Array.isArray(rawValue) ? rawValue : [rawValue];
  const selected = new Set(selectedValues.map((value) => stringifyReviewDraftValue(value)));
  if (selected.size === 0) return [];
  return getReviewFieldOptions(field).filter((option) => selected.has(option.value));
}

function shouldUseReviewOptionsSelect(field) {
  return getReviewFieldOptions(field).length > 0;
}

function getReviewMultiOptionDraftValues(field, rawValue) {
  const values = Array.isArray(rawValue) ? rawValue : [rawValue];
  const optionValues = new Set(getReviewFieldOptions(field).map((option) => option.value));
  return values
    .map((value) => stringifyReviewDraftValue(value))
    .filter((value) => value && optionValues.has(value));
}

function getReviewSelectedOptionValues(field, rawValue) {
  return getReviewMatchedOptions(field, rawValue).map((option) => cloneReviewOptionValue(option.rawValue));
}

function cloneReviewOptionValue(value) {
  if (Array.isArray(value) || (value && typeof value === "object")) {
    try {
      return JSON.parse(JSON.stringify(value));
    } catch {
      return value;
    }
  }
  return value;
}

function getAutoTextareaRows(value, {
  minRows = 3,
  maxRows = 18,
  charsPerRow = 64,
} = {}) {
  const raw = String(value ?? "");
  if (!raw) return minRows;
  const estimatedRows = raw
    .split(/\r?\n/)
    .reduce((total, line) => total + Math.max(1, Math.ceil(line.length / charsPerRow)), 0);
  return Math.min(maxRows, Math.max(minRows, estimatedRows));
}

function isReviewLongTextField(field) {
  return getSchemaFieldType(field) === "text";
}

function isReviewImageField(field) {
  return getSchemaFieldType(field) === "image";
}

function getReviewTextareaRows(field) {
  const path = String(field?.path || "").trim();
  const value = reviewFieldDrafts[path] ?? "";
  const type = getSchemaFieldType(field);
  if (type === "text") {
    return getAutoTextareaRows(value, { minRows: 3, maxRows: 24, charsPerRow: 58 });
  }
  if (type === "json" || type === "list") {
    return getAutoTextareaRows(value, { minRows: 4, maxRows: 20, charsPerRow: 68 });
  }
  return getAutoTextareaRows(value, { minRows: 3, maxRows: 10, charsPerRow: 62 });
}

function normalizeReviewComparableValue(value, { unorderedLists = false } = {}) {
  if (Array.isArray(value)) {
    const source = unorderedLists
      ? value.filter((entry) => !(typeof entry === "string" && entry.trim() === ""))
      : value;
    const normalized = source.map((entry) => normalizeReviewComparableValue(entry, { unorderedLists }));
    if (!unorderedLists) return normalized;
    return normalized.sort((left, right) =>
      stringifyReviewComparableToken(left).localeCompare(stringifyReviewComparableToken(right))
    );
  }
  if (value && typeof value === "object") {
    return Object.keys(value)
      .sort((left, right) => left.localeCompare(right))
      .reduce((acc, key) => {
        acc[key] = normalizeReviewComparableValue(value[key], { unorderedLists });
        return acc;
      }, {});
  }
  return value;
}

function stringifyReviewComparableToken(value) {
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function getReviewValueToken(value, hasValue = true) {
  if (!hasValue) return "__review_missing__";
  try {
    return JSON.stringify(normalizeReviewComparableValue(value, { unorderedLists: true }));
  } catch {
    return String(value);
  }
}

function reviewValuesEqual(leftValue, rightValue, leftHasValue = true, rightHasValue = true) {
  return getReviewValueToken(leftValue, leftHasValue) === getReviewValueToken(rightValue, rightHasValue);
}

function isReviewDraftEmpty(value) {
  if (Array.isArray(value)) return value.length === 0;
  return String(value ?? "").trim() === "";
}

function stringifyReviewDraftDisplayValue(value) {
  if (Array.isArray(value)) {
    return value.map((entry) => stringifyReviewDraftValue(entry)).filter(Boolean).join("\n");
  }
  return String(value ?? "");
}

function getReviewDisplayValue(field, slot) {
  if (slot === "previous") {
    return formatReviewValue(field?.previous_value, field?.has_previous_value);
  }
  if (slot === "current") {
    return formatReviewValue(field?.current_value, field?.has_current_value);
  }
  if (slot === "effective") {
    return formatReviewValue(field?.effective_value, field?.has_effective_value);
  }
  const path = String(field?.path || "").trim();
  return stringifyReviewDraftDisplayValue(reviewFieldDrafts[path]);
}

function getReviewComparisonRows(field) {
  const values = [
    getReviewDisplayValue(field, "previous"),
    getReviewDisplayValue(field, "current"),
    getReviewDisplayValue(field, "local"),
    getReviewDisplayValue(field, "effective"),
  ];
  const rows = values.map((value) =>
    getAutoTextareaRows(value, {
      minRows: 3,
      maxRows: isReviewLongTextField(field) ? 24 : 14,
      charsPerRow: isReviewLongTextField(field) ? 58 : 64,
    })
  );
  return Math.max(...rows);
}

function isReviewPreviousMuted(field) {
  return reviewValuesEqual(
    field?.previous_value,
    field?.current_value,
    field?.has_previous_value,
    field?.has_current_value,
  );
}

function isReviewCurrentMuted(field) {
  return reviewValuesEqual(
    field?.current_value,
    field?.effective_value,
    field?.has_current_value,
    field?.has_effective_value,
  );
}

function isReviewLocalDifferentFromCurrent(field) {
  if (!field?.has_current_value) return false;
  try {
    return !reviewValuesEqual(
      parseReviewDraftValue(field),
      field.current_value,
      true,
      true,
    );
  } catch {
    return true;
  }
}

function isReviewFieldDraftChanged(field) {
  const path = String(field?.path || "").trim();
  if (!path || !Object.prototype.hasOwnProperty.call(reviewFieldDrafts, path)) return false;
  const source = getReviewFieldDraftSource(field);
  const rawDraft = reviewFieldDrafts[path];
  const rawDraftDisplay = stringifyReviewDraftDisplayValue(rawDraft);
  if (!source.hasValue && isReviewDraftEmpty(rawDraft)) return false;
  try {
    return !reviewValuesEqual(
      parseReviewDraftValue(field),
      source.value,
      true,
      source.hasValue,
    );
  } catch {
    return rawDraftDisplay !== (source.hasValue ? stringifyReviewDraftValue(source.value) : "");
  }
}

function shouldUseReviewAddTextarea(field) {
  return getSchemaInputType(field) === "textarea" || getSchemaFieldType(field) === "text";
}

function isReviewFieldSourceChanged(field) {
  return !reviewItemDetail.value?.is_local_item && Boolean(field?.source_changed);
}

function getReviewAddFieldPlaceholder(field) {
  const samples = Array.isArray(field?.sample_values) ? field.sample_values : [];
  const sample = samples.find((entry) => {
    if (entry === undefined || entry === null) return false;
    if (typeof entry === "string") return entry.trim() !== "";
    if (Array.isArray(entry)) return entry.length > 0;
    if (typeof entry === "object") return Object.keys(entry).length > 0;
    return true;
  });
  if (sample === undefined) return "";
  return formatReviewValue(sample, true);
}

function isReviewRequiredValueMissing(value) {
  if (value === undefined || value === null) return true;
  if (typeof value === "string") return value.trim() === "";
  if (Array.isArray(value)) return value.length === 0;
  if (value && typeof value === "object") return Object.keys(value).length === 0;
  return false;
}

function isReviewAddFieldMissingRequired(field) {
  const path = String(field?.path || "").trim();
  if (!path) return false;
  try {
    return isReviewRequiredValueMissing(parseSchemaDraftValue(field, reviewAddItemDrafts[path]));
  } catch {
    return true;
  }
}

function isReviewAddFieldMissingForSave(field) {
  const path = String(field?.path || "").trim();
  return Boolean(path && path === reviewAddItemNamePath.value && isReviewAddFieldMissingRequired(field));
}

function getReviewAddEffectiveDisplayValue(field) {
  const path = String(field?.path || "").trim();
  try {
    return formatReviewValue(parseSchemaDraftValue(field, reviewAddItemDrafts[path]), true);
  } catch {
    return stringifyReviewDraftDisplayValue(reviewAddItemDrafts[path]);
  }
}

function getReviewAddComparisonRows(field) {
  const path = String(field?.path || "").trim();
  const values = [
    stringifyReviewDraftDisplayValue(reviewAddItemDrafts[path]),
    getReviewAddEffectiveDisplayValue(field),
  ];
  const isText = getSchemaFieldType(field) === "text";
  return Math.max(
    ...values.map((value) =>
      getAutoTextareaRows(value, {
        minRows: isText ? 3 : 2,
        maxRows: isText ? 24 : 14,
        charsPerRow: isText ? 58 : 64,
      })
    ),
  );
}

function parseSchemaDraftValue(field, rawValue) {
  const type = getSchemaFieldType(field);
  if (shouldUseReviewMultipleOptionsSelect(field)) {
    return getReviewSelectedOptionValues(field, rawValue);
  }
  const matchedOption = getReviewMatchedOption(field, rawValue);
  if (type === "boolean") {
    if (matchedOption && typeof matchedOption.rawValue === "boolean") return matchedOption.rawValue;
    const normalized = String(rawValue ?? "").trim().toLowerCase();
    if (["true", "1", "yes", "on"].includes(normalized)) return true;
    if (["false", "0", "no", "off"].includes(normalized)) return false;
    if (!normalized) return null;
    return Boolean(rawValue);
  }
  const raw = String(rawValue ?? "");
  const trimmed = raw.trim();
  if (type === "number") {
    if (matchedOption && typeof matchedOption.rawValue === "number" && Number.isFinite(matchedOption.rawValue)) {
      return matchedOption.rawValue;
    }
    if (!trimmed) return null;
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) {
      throw new Error(`Field ${field.path} expects a number.`);
    }
    return parsed;
  }
  if (type === "json" || type === "list") {
    if (matchedOption) {
      const value = cloneReviewOptionValue(matchedOption.rawValue);
      return type === "list" ? [value] : value;
    }
    if (!trimmed) return type === "list" ? [] : null;
    try {
      return JSON.parse(trimmed);
    } catch {
      throw new Error(`Field ${field.path} expects valid JSON.`);
    }
  }
  if (type === "null") return null;
  return raw;
}

async function createReviewItem() {
  const integrationId = String(reviewIntegrationId.value || "").trim();
  if (!integrationId || !reviewCanAddItem.value) return;
  if (reviewAddItemMissingRequiredPaths.value.length > 0) {
    reviewStatus.value = {
      type: "error",
      message: `Missing item name: ${reviewAddItemMissingRequiredPaths.value.join(", ")}`,
    };
    return;
  }
  reviewAddItemSaving.value = true;
  reviewStatus.value = null;
  try {
    const values = {};
    reviewSchemaFields.value.forEach((field) => {
      const path = String(field?.path || "").trim();
      if (!path) return;
      values[path] = parseSchemaDraftValue(field, reviewAddItemDrafts[path]);
    });
    reviewItemDetail.value = await api.createIntegrationReviewItem(integrationId, { values });
    reviewSelectedItemKey.value = String(reviewItemDetail.value?.item_key || "").trim();
    Object.keys(reviewAddItemDrafts).forEach((key) => delete reviewAddItemDrafts[key]);
    reviewAddItemOpen.value = false;
    syncReviewDrafts();
    reviewStateFilter.value = "";
    reviewTagFilter.value = "__badge:local";
    await loadReviewItems({ preserveSelection: true });
    reviewStatus.value = { type: "success", message: "Local review item added." };
  } catch (err) {
    reviewStatus.value = { type: "error", message: err.message || "Failed to add local item." };
  } finally {
    reviewAddItemSaving.value = false;
  }
}

function getReviewDateTimeReferenceValue(field) {
  if (field?.has_override) return field.local_value;
  if (field?.has_current_value) return field.current_value;
  if (field?.has_effective_value) return field.effective_value;
  if (field?.has_previous_value) return field.previous_value;
  return null;
}

function toDateTimeLocalDraft(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  const match = raw.match(/^(\d{4}-\d{2}-\d{2})[T\s](\d{2}:\d{2})(?::(\d{2}))?/);
  if (match) {
    return `${match[1]}T${match[2]}${match[3] ? `:${match[3]}` : ""}`;
  }
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (entry) => String(entry).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function isReviewDatetimeField(field) {
  return getSchemaFieldType(field) === "datetime";
}

function isReviewDateField(field) {
  return getSchemaFieldType(field) === "date";
}

function reviewDateTimeUsesSeconds(field) {
  const reference = String(getReviewDateTimeReferenceValue(field) ?? "");
  const path = String(field?.path || "").trim();
  const draft = path ? String(reviewFieldDrafts[path] ?? reviewAddItemDrafts[path] ?? "") : "";
  return /[T\s]\d{2}:\d{2}:\d{2}/.test(reference) || /[T\s]\d{2}:\d{2}:\d{2}/.test(draft);
}

function getReviewDateTimeMinuteIncrement() {
  return 1;
}

function parseReviewDateTimePickerDate(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return null;
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})(?::(\d{2}))?/);
  if (match) {
    const date = new Date(
      Number(match[1]),
      Number(match[2]) - 1,
      Number(match[3]),
      Number(match[4]),
      Number(match[5]),
      Number(match[6] || 0),
    );
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatReviewDateTimeDraftValue(value, referenceValue = null) {
  const date = value instanceof Date ? value : parseReviewDateTimePickerDate(value);
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "";
  const pad = (entry) => String(entry).padStart(2, "0");
  const includeSeconds = /[T\s]\d{2}:\d{2}:\d{2}/.test(String(referenceValue ?? "")) || date.getSeconds() !== 0;
  const seconds = includeSeconds ? `:${pad(date.getSeconds())}` : "";
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}${seconds}`;
}

function normalizeReviewDateTimePickerDraft(modelValue, referenceValue = null) {
  if (modelValue === null || modelValue === undefined || modelValue === "") return "";
  if (Array.isArray(modelValue)) {
    return normalizeReviewDateTimePickerDraft(modelValue[0], referenceValue);
  }
  return formatReviewDateTimeDraftValue(modelValue, referenceValue);
}

function normalizeReviewDatePickerDraft(modelValue) {
  if (modelValue === null || modelValue === undefined || modelValue === "") return "";
  if (Array.isArray(modelValue)) {
    return normalizeReviewDatePickerDraft(modelValue[0]);
  }
  return localDateToServerDateOnly(modelValue);
}

function getReviewDatePickerModel(field) {
  const path = String(field?.path || "").trim();
  return serverDateOnlyToLocalDate(reviewFieldDrafts[path]);
}

function setReviewDatePickerValue(field, modelValue) {
  const path = String(field?.path || "").trim();
  if (!path) return;
  reviewFieldDrafts[path] = normalizeReviewDatePickerDraft(modelValue);
}

function getReviewDateTimePickerModel(field) {
  const path = String(field?.path || "").trim();
  return parseReviewDateTimePickerDate(reviewFieldDrafts[path]);
}

function setReviewDateTimePickerValue(field, modelValue) {
  const path = String(field?.path || "").trim();
  if (!path) return;
  reviewFieldDrafts[path] = normalizeReviewDateTimePickerDraft(modelValue, getReviewDateTimeReferenceValue(field));
}

function getReviewAddDatePickerModel(field) {
  const path = String(field?.path || "").trim();
  return serverDateOnlyToLocalDate(reviewAddItemDrafts[path]);
}

function setReviewAddDatePickerValue(field, modelValue) {
  const path = String(field?.path || "").trim();
  if (!path) return;
  reviewAddItemDrafts[path] = normalizeReviewDatePickerDraft(modelValue);
}

function getReviewAddDateTimePickerModel(field) {
  const path = String(field?.path || "").trim();
  return parseReviewDateTimePickerDate(reviewAddItemDrafts[path]);
}

function setReviewAddDateTimePickerValue(field, modelValue) {
  const path = String(field?.path || "").trim();
  if (!path) return;
  reviewAddItemDrafts[path] = normalizeReviewDateTimePickerDraft(modelValue);
}

function serializeDateTimeLikeReference(localValue, referenceValue) {
  const raw = String(localValue || "").trim();
  const match = raw.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(?::(\d{2}))?/);
  if (!match) return raw;
  const reference = String(referenceValue ?? "");
  const separator = reference.includes(" ") && !reference.includes("T") ? " " : "T";
  const hasSeconds = /[T\s]\d{2}:\d{2}:\d{2}/.test(reference);
  const seconds = hasSeconds ? `:${match[3] || "00"}` : "";
  const suffix = reference.match(/(Z|[+-]\d{2}:?\d{2})$/)?.[1] || "";
  return `${match[1]}${separator}${match[2]}${seconds}${suffix}`;
}

function getReviewImagePreviewUrl(value, rawType) {
  const type = String(rawType || "").trim().toLowerCase();
  const raw = String(value ?? "").trim();
  if (type !== "image" || !raw) return "";
  if (/^(https?:\/\/|data:image\/|blob:)/i.test(raw)) return raw;
  return "";
}

function openReviewImagePicker(field) {
  const path = getReviewFieldPath(field);
  if (!path || !isReviewImageField(field)) return;
  reviewImagePickerFieldPath.value = path;
}

function closeReviewImagePicker() {
  reviewImagePickerFieldPath.value = "";
}

function onReviewImagePickerSelect(selection) {
  const path = String(reviewImagePickerFieldPath.value || "").trim();
  if (!path) {
    closeReviewImagePicker();
    return;
  }
  reviewFieldDrafts[path] = String(selection?.url || "").trim();
  closeReviewImagePicker();
}

function stringifyReviewDraftValue(value) {
  if (value === undefined) return "";
  if (typeof value === "string") return value;
  if (value === null) return "null";
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value ?? "");
  }
}

function parseReviewDraftValue(field) {
  const path = String(field?.path || "").trim();
  const rawDraft = reviewFieldDrafts[path];
  if (shouldUseReviewMultipleOptionsSelect(field)) {
    return getReviewSelectedOptionValues(field, rawDraft);
  }
  const raw = String(rawDraft ?? "");
  const matchedOption = getReviewMatchedOption(field, rawDraft);
  const schemaType = String(field?.schema_type || "").trim().toLowerCase();
  const trimmed = raw.trim();

  if (
    trimmed === "null"
    && (
      field?.local_value === null
      || field?.current_value === null
      || field?.effective_value === null
      || field?.previous_value === null
      || schemaType === "null"
    )
  ) {
    return null;
  }

  if (schemaType === "number") {
    if (matchedOption && typeof matchedOption.rawValue === "number" && Number.isFinite(matchedOption.rawValue)) {
      return matchedOption.rawValue;
    }
    const parsed = Number(trimmed);
    if (!trimmed || !Number.isFinite(parsed)) {
      throw new Error(`Field ${path} expects a number.`);
    }
    return parsed;
  }
  if (schemaType === "boolean") {
    if (matchedOption && typeof matchedOption.rawValue === "boolean") return matchedOption.rawValue;
    const normalized = trimmed.toLowerCase();
    if (["true", "1", "yes", "on"].includes(normalized)) return true;
    if (["false", "0", "no", "off"].includes(normalized)) return false;
    throw new Error(`Field ${path} expects true or false.`);
  }
  if (schemaType === "null") {
    if (!trimmed || trimmed === "null") return null;
    throw new Error(`Field ${path} expects null.`);
  }
  if (schemaType === "datetime" && isReviewDatetimeField(field)) {
    return serializeDateTimeLikeReference(trimmed, getReviewDateTimeReferenceValue(field));
  }
  if (schemaType === "json" || schemaType === "list") {
    if (matchedOption) {
      const value = cloneReviewOptionValue(matchedOption.rawValue);
      return schemaType === "list" ? [value] : value;
    }
    try {
      return JSON.parse(trimmed || (schemaType === "list" ? "[]" : "null"));
    } catch (err) {
      throw new Error(`Field ${path} expects valid JSON.`);
    }
  }
  return raw;
}

async function saveReviewField(field) {
  const integrationId = String(reviewIntegrationId.value || "").trim();
  const itemKey = String(reviewItemDetail.value?.item_key || "").trim();
  const path = String(field?.path || "").trim();
  if (!integrationId || !itemKey || !path) return;
  reviewFieldSaving[path] = true;
  reviewStatus.value = null;
  try {
    const value = parseReviewDraftValue(field);
    const nextDetail = await api.updateIntegrationReviewItem(integrationId, {
      item_key: itemKey,
      field_path: path,
      value,
    });
    applyReviewItemFieldResponse(nextDetail, path);
    reviewStatus.value = { type: "success", message: "Local override saved." };
  } catch (err) {
    reviewStatus.value = { type: "error", message: err.message || "Failed to save local override." };
  } finally {
    reviewFieldSaving[path] = false;
  }
}

async function clearReviewField(field) {
  const integrationId = String(reviewIntegrationId.value || "").trim();
  const itemKey = String(reviewItemDetail.value?.item_key || "").trim();
  const path = String(field?.path || "").trim();
  if (!integrationId || !itemKey || !path) return;
  reviewFieldSaving[path] = true;
  reviewStatus.value = null;
  try {
    const nextDetail = await api.deleteIntegrationReviewFieldOverride(integrationId, {
      item_key: itemKey,
      field_path: path,
    });
    applyReviewItemFieldResponse(nextDetail, path);
    reviewStatus.value = { type: "success", message: "Local override cleared." };
  } catch (err) {
    reviewStatus.value = { type: "error", message: err.message || "Failed to clear local override." };
  } finally {
    reviewFieldSaving[path] = false;
  }
}

function formatReviewValue(value, hasValue = true) {
  if (!hasValue) return "undefined";
  if (value === undefined) return "undefined";
  if (value === null) return "null";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function formatSchemaType(rawType) {
  const value = String(rawType || "undefined").trim().toLowerCase();
  if (value === "datetime") return "Date/Time";
  if (value === "url") return "URL";
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ") || "Undefined";
}

async function runDraftHealthCheck() {
  draftHealthChecking.value = true;
  draftHealthResult.value = null;
  try {
    draftHealthResult.value = await api.healthCheckIntegrationDraft({
      type: form.type,
      url: form.url,
      auth_type: form.auth_type,
      key_name: form.auth_type !== "none" ? form.key_name : null,
    });
  } catch (err) {
    draftHealthResult.value = { ok: false, error: err.message };
  } finally {
    draftHealthChecking.value = false;
  }
}

async function saveIntegration() {
  saving.value = true;
  try {
    const crawlerPaginationConfig = form.type === "crawler"
      ? buildCrawlerPaginationPayloadFrom(form, "Crawler pagination")
      : null;
    const outputPrimaryKeyPath = normalizeIntegrationPathInput(form.output_primary_key_path, {
      fieldLabel: "ID path",
      mode: "reference",
      required: false,
    });

    const payload = {
      name: form.name,
      description: form.description || null,
      url: form.url,
      type: form.type,
      auth_type: form.auth_type,
      key_name: form.auth_type !== "none" ? form.key_name : null,
      response_type: form.response_type,
      response_path: form.response_path || null,
      crawler_pagination_config: crawlerPaginationConfig,
      transform_steps: parseTransformStepsFrom(form.transform_steps),
      output_primary_key_path: outputPrimaryKeyPath || null,
      container_config: null,
    };

    await api.createIntegration(payload);
    resetForm();
    await loadIntegrations();
    setActiveTab("manage");
  } catch (err) {
    alert("Failed to save integration: " + err.message);
  } finally {
    saving.value = false;
  }
}

async function saveContainerIntegration() {
  saving.value = true;
  try {
    const targetSourceId = String(containerForm.target_source_integration_id || "").trim();
    const outputPrimaryKeyPath = normalizeIntegrationPathInput(containerForm.output_primary_key_path, {
      fieldLabel: "ID path",
      mode: "reference",
      required: false,
    });
    const configuredSources = containerForm.sources
      .map((source, sourceIndex) => {
        const sourceId = String(source.integration_id || "").trim();
        const isTargetSource = Boolean(targetSourceId) && sourceId === targetSourceId;
        const mergeStyle = isTargetSource
          ? "flat"
          : (String(source.merge_style || "flat").trim() === "nested" ? "nested" : "flat");
        const nestedKey = normalizeIntegrationIdentifierInput(source.nested_key, {
          fieldLabel: `Composable source ${sourceIndex + 1}: nested key`,
          mode: "target",
          required: false,
        });
        if (mergeStyle === "nested" && !nestedKey) {
          throw new Error(`Composable source ${sourceIndex + 1}: nested key is required when merge style is nested.`);
        }
        return {
          integration_id: sourceId,
          source_key_path: normalizeIntegrationPathInput(source.source_key_path, {
            fieldLabel: `Composable source ${sourceIndex + 1}: Source Key path`,
            mode: "reference",
            required: false,
          }) || null,
          target_key_path: normalizeIntegrationPathInput(source.target_key_path, {
            fieldLabel: `Composable source ${sourceIndex + 1}: Target Key path`,
            mode: "reference",
            required: false,
          }) || null,
          merge_style: mergeStyle,
          nested_key: mergeStyle === "nested" ? nestedKey : null,
          keep_target_key: Boolean(source.keep_target_key),
        };
      })
      .filter((source) => source.integration_id);

    if (configuredSources.length < 2) {
      throw new Error("Composable needs at least two source integrations.");
    }
    if (targetSourceId && !configuredSources.some((source) => source.integration_id === targetSourceId)) {
      throw new Error("Target source must be one of the configured sources.");
    }
    if (targetSourceId) {
      configuredSources.forEach((source, sourceIndex) => {
        if (source.integration_id === targetSourceId) return;
        if (!source.target_key_path) {
          throw new Error(`Composable source ${sourceIndex + 1}: Target Key path is required.`);
        }
        if (!source.source_key_path) {
          throw new Error(`Composable source ${sourceIndex + 1}: Source Key path is required.`);
        }
      });
    }
    const transformSteps = parseTransformStepsFrom(containerForm.transform_steps);

    const payload = {
      name: containerForm.name,
      description: containerForm.description || null,
      type: "composable",
      url: "",
      auth_type: "none",
      key_name: null,
      response_type: "json",
      response_path: null,
      crawler_pagination_config: null,
      transform_steps: transformSteps,
      output_primary_key_path: outputPrimaryKeyPath || null,
      container_config: {
        sources: configuredSources,
        target_source_integration_id: targetSourceId || null,
        merge_mode: "full_outer",
        conflict_mode: "last_wins",
      },
    };

    await api.createIntegration(payload);
    resetContainerForm();
    await loadIntegrations();
    setActiveTab("manage");
  } catch (err) {
    alert("Failed to save composable integration: " + err.message);
  } finally {
    saving.value = false;
  }
}

function onCreateTypeChange() {
  draftHealthResult.value = null;
  if (form.type !== "crawler") {
    resetCrawlerPaginationUi(form);
  }
}

function onInlineTypeChange() {
  inlineDraftHealthResult.value = null;
  if (inlineForm.type !== "crawler") {
    resetCrawlerPaginationUi(inlineForm);
  }
  if (isComposableIntegrationType(inlineForm.type) && inlineContainerForm.sources.length < 2) {
    inlineContainerForm.sources = [createContainerSource(), createContainerSource()];
  }
}

function startInlineEdit(integration) {
  inlineEditId.value = integration.id;
  manageSubsectionById[integration.id] = "config";
  if (manageSchemaIntegrationId.value !== integration.id) {
    manageSchemaIntegrationId.value = "";
    manageSchema.value = null;
    manageSchemaStatus.value = null;
  }
  inlineDraftHealthResult.value = null;

  inlineForm.name = integration.name || "";
  inlineForm.description = integration.description || "";
  inlineForm.type = normalizeIntegrationType(integration.type || "api");
  inlineForm.url = integration.url || "";
  inlineForm.auth_type = integration.auth_type || "none";
  inlineForm.key_name = integration.key_name || "";
  inlineForm.response_type = integration.response_type || "json";
  inlineForm.response_path = integration.response_path || "";
  inlineForm.output_primary_key_path = integration.output_primary_key_path || "";
  applyCrawlerPaginationUi(inlineForm, integration.crawler_pagination_config);
  inlineForm.transform_steps = Array.isArray(integration.transform_steps)
    ? normalizeTransformStepsUi(integration.transform_steps)
    : [];

  inlineContainerForm.target_source_integration_id = integration.container_config?.target_source_integration_id || "";
  const sourceRows = Array.isArray(integration.container_config?.sources)
    ? integration.container_config.sources
    : [];
  inlineContainerForm.sources = sourceRows.map((source) => createContainerSource(source));
  while (inlineContainerForm.sources.length < 2) {
    inlineContainerForm.sources.push(createContainerSource());
  }
  if (isComposableIntegrationType(inlineForm.type)) {
    void autoApplyContainerPrimeKeys(
      inlineContainerForm.sources,
      inlineContainerForm.target_source_integration_id,
    ).finally(() => {
      if (String(inlineEditId.value || "").trim() === String(integration.id || "").trim()) {
        inlineBaselineSignature.value = buildInlineEditSignature();
      }
    });
  } else {
    inlineBaselineSignature.value = buildInlineEditSignature();
  }
}

function resetInlineEditFromIntegration(integration) {
  if (!integration) return;
  startInlineEdit(integration);
}

function cancelInlineEdit(scrollToIntegrationId = null, options = {}) {
  const targetIntegrationId = String(
    scrollToIntegrationId || inlineEditId.value || "",
  ).trim();
  if (targetIntegrationId) {
    delete manageSubsectionById[targetIntegrationId];
  }
  inlineEditId.value = null;
  manageSchemaIntegrationId.value = "";
  manageSchema.value = null;
  manageSchemaStatus.value = null;
  resetInlineForm();
  if (targetIntegrationId && options.scroll !== false) {
    scrollToIntegrationTop(targetIntegrationId);
  }
}

function addInlineContainerSource() {
  inlineContainerForm.sources.push(createContainerSource());
}

function removeInlineContainerSource(index) {
  if (inlineContainerForm.sources.length <= 2) return;
  inlineContainerForm.sources.splice(index, 1);
}

async function runInlineDraftHealthCheck() {
  if (isComposableIntegrationType(inlineForm.type)) return;
  inlineDraftHealthChecking.value = true;
  inlineDraftHealthResult.value = null;
  try {
    inlineDraftHealthResult.value = await api.healthCheckIntegrationDraft({
      type: inlineForm.type,
      url: inlineForm.url,
      auth_type: inlineForm.auth_type,
      key_name: inlineForm.auth_type !== "none" ? inlineForm.key_name : null,
    });
  } catch (err) {
    inlineDraftHealthResult.value = { ok: false, error: err.message };
  } finally {
    inlineDraftHealthChecking.value = false;
  }
}

function buildResponseMetadata(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return null;
  }
  const rawItemCount = Object.prototype.hasOwnProperty.call(payload, "item_count")
    ? payload.item_count
    : payload.total_items;
  const itemCount = Number.isFinite(Number(rawItemCount)) ? Number(rawItemCount) : 0;
  return {
    integration_id: payload.integration_id ?? null,
    item_count: itemCount,
    fetched_at: payload.fetched_at ?? null,
    options: payload.options && typeof payload.options === "object" && !Array.isArray(payload.options)
      ? payload.options
      : {},
    option_types: payload.option_types && typeof payload.option_types === "object" && !Array.isArray(payload.option_types)
      ? payload.option_types
      : {},
  };
}

function normalizePreviewItems(data, previewItem) {
  const sourceItems = Array.isArray(data)
    ? data
    : (data == null ? [] : [data]);
  const fallbackItems = previewItem == null ? [] : [previewItem];
  const items = sourceItems.length > 0 ? sourceItems : fallbackItems;
  return items.slice(0, PREVIEW_ITEM_LIMIT);
}

function getSchemaItemLabelPath(schemaPayload) {
  const directPath = String(schemaPayload?.item_label_path || "").trim();
  if (directPath) return directPath;
  const field = Array.isArray(schemaPayload?.fields)
    ? schemaPayload.fields.find((entry) => Boolean(entry?.is_item_label))
    : null;
  return String(field?.path || "").trim();
}

function getPreviewItemLabel(item, index, labelPath) {
  const value = getIntegrationPathValue(item, labelPath);
  const formattedValue = formatPreviewLabelValue(value);
  return formattedValue ? `${index + 1}. ${formattedValue}` : `Item ${index + 1}`;
}

function formatPreviewLabelValue(value) {
  if (value == null) return "";
  if (Array.isArray(value)) {
    return value.map(formatPreviewLabelValue).filter(Boolean).join(", ");
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value).trim();
}

function getIntegrationPathValue(source, path) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return undefined;
  return normalizedPath.split(".").reduce((current, rawSegment) => {
    if (current == null) return undefined;
    const segment = String(rawSegment || "").trim();
    if (!segment) return current;
    const keyMatch = segment.match(/^([A-Za-z_][A-Za-z0-9_]*)(.*)$/);
    let nextValue = current;
    let bracketPart = segment;
    if (keyMatch) {
      nextValue = nextValue?.[keyMatch[1]];
      bracketPart = keyMatch[2] || "";
    }
    const indexMatches = [...bracketPart.matchAll(/\[(-?\d+)\]/g)];
    for (const match of indexMatches) {
      if (!Array.isArray(nextValue)) return undefined;
      const index = Number.parseInt(match[1], 10);
      const resolvedIndex = index < 0 ? nextValue.length + index : index;
      nextValue = nextValue[resolvedIndex];
    }
    return nextValue;
  }, source);
}

function getContainerSourceRowLabel(source, index) {
  const sourceName = getIntegrationDisplayName(source?.integration_id);
  return sourceName ? `Source ${index + 1} - ${sourceName}` : `Source ${index + 1}`;
}

function buildInlineEditSignature() {
  try {
    return JSON.stringify(normalizeReviewComparableValue(buildInlineEditSnapshot()));
  } catch {
    return "";
  }
}

function buildInlineEditSnapshot() {
  return {
    name: inlineForm.name,
    description: inlineForm.description,
    type: inlineForm.type,
    url: inlineForm.url,
    auth_type: inlineForm.auth_type,
    key_name: inlineForm.key_name,
    response_type: inlineForm.response_type,
    response_path: inlineForm.response_path,
    crawler_pagination_strategy: inlineForm.crawler_pagination_strategy,
    crawler_page_query_param: inlineForm.crawler_page_query_param,
    crawler_page_count_field: inlineForm.crawler_page_count_field,
    crawler_next_page_field: inlineForm.crawler_next_page_field,
    crawler_query_loop_key: inlineForm.crawler_query_loop_key,
    crawler_query_loop_values_input: inlineForm.crawler_query_loop_values_input,
    crawler_max_page_visits: inlineForm.crawler_max_page_visits,
    output_primary_key_path: inlineForm.output_primary_key_path,
    transform_steps: stripEditorUiState(inlineForm.transform_steps),
    container: {
      target_source_integration_id: inlineContainerForm.target_source_integration_id,
      sources: inlineContainerForm.sources.map((source) => ({
        integration_id: source.integration_id,
        source_key_path: source.source_key_path,
        target_key_path: source.target_key_path,
        merge_style: source.merge_style,
        nested_key: source.nested_key,
        keep_target_key: Boolean(source.keep_target_key),
      })),
    },
  };
}

function stripEditorUiState(value) {
  if (Array.isArray(value)) return value.map((entry) => stripEditorUiState(entry));
  if (value && typeof value === "object") {
    return Object.entries(value).reduce((acc, [key, entryValue]) => {
      if (key === "ui_id" || key === "collapsed") return acc;
      acc[key] = stripEditorUiState(entryValue);
      return acc;
    }, {});
  }
  return value;
}

async function saveInlineEdit() {
  if (!inlineEditId.value) return;

  const editedIntegrationId = inlineEditId.value;
  inlineSaving.value = true;
  try {
    const outputPrimaryKeyPath = normalizeIntegrationPathInput(inlineForm.output_primary_key_path, {
      fieldLabel: "ID path",
      mode: "reference",
      required: false,
    });
    const payload = {
      name: inlineForm.name,
      description: inlineForm.description || null,
      type: inlineForm.type,
      output_primary_key_path: outputPrimaryKeyPath || null,
    };

    if (isComposableIntegrationType(inlineForm.type)) {
      const targetSourceId = String(inlineContainerForm.target_source_integration_id || "").trim();
      const configuredSources = inlineContainerForm.sources
        .map((source, sourceIndex) => {
          const sourceId = String(source.integration_id || "").trim();
          const isTargetSource = Boolean(targetSourceId) && sourceId === targetSourceId;
        const mergeStyle = isTargetSource
          ? "flat"
          : (String(source.merge_style || "flat").trim() === "nested" ? "nested" : "flat");
          const nestedKey = normalizeIntegrationIdentifierInput(source.nested_key, {
            fieldLabel: `Composable source ${sourceIndex + 1}: nested key`,
            mode: "target",
            required: false,
          });
          if (mergeStyle === "nested" && !nestedKey) {
            throw new Error(`Composable source ${sourceIndex + 1}: nested key is required when merge style is nested.`);
          }
          return {
            integration_id: sourceId,
            source_key_path: normalizeIntegrationPathInput(source.source_key_path, {
              fieldLabel: `Composable source ${sourceIndex + 1}: Source Key path`,
              mode: "reference",
              required: false,
            }) || null,
            target_key_path: normalizeIntegrationPathInput(source.target_key_path, {
              fieldLabel: `Composable source ${sourceIndex + 1}: Target Key path`,
              mode: "reference",
              required: false,
            }) || null,
            merge_style: mergeStyle,
            nested_key: mergeStyle === "nested" ? nestedKey : null,
            keep_target_key: Boolean(source.keep_target_key),
          };
        })
        .filter((source) => source.integration_id);

      if (configuredSources.length < 2) {
        throw new Error("Composable needs at least two source integrations.");
      }
      if (targetSourceId && !configuredSources.some((source) => source.integration_id === targetSourceId)) {
        throw new Error("Target source must be one of the configured sources.");
      }
      if (targetSourceId) {
        configuredSources.forEach((source, sourceIndex) => {
          if (source.integration_id === targetSourceId) return;
          if (!source.target_key_path) {
            throw new Error(`Composable source ${sourceIndex + 1}: Target Key path is required.`);
          }
          if (!source.source_key_path) {
            throw new Error(`Composable source ${sourceIndex + 1}: Source Key path is required.`);
          }
        });
      }
      const transformSteps = parseTransformStepsFrom(inlineForm.transform_steps);

      payload.url = "";
      payload.auth_type = "none";
      payload.key_name = null;
      payload.response_type = "json";
      payload.response_path = null;
      payload.crawler_pagination_config = null;
      payload.transform_steps = transformSteps;
      payload.container_config = {
        sources: configuredSources,
        target_source_integration_id: targetSourceId || null,
        merge_mode: "full_outer",
        conflict_mode: "last_wins",
      };
    } else {
      const crawlerPaginationConfig = inlineForm.type === "crawler"
        ? buildCrawlerPaginationPayloadFrom(inlineForm, "Crawler pagination")
        : null;
      payload.url = inlineForm.url;
      payload.auth_type = inlineForm.auth_type;
      payload.key_name = inlineForm.auth_type !== "none" ? inlineForm.key_name : null;
      payload.response_type = inlineForm.response_type;
      payload.response_path = inlineForm.response_path || null;
      payload.crawler_pagination_config = crawlerPaginationConfig;
      payload.transform_steps = parseTransformStepsFrom(inlineForm.transform_steps);
      payload.container_config = null;
    }

    await api.updateIntegration(editedIntegrationId, payload);
    await loadIntegrations();
    const refreshedIntegration = integrations.value.find(
      (integration) => String(integration?.id || "").trim() === editedIntegrationId,
    );
    if (refreshedIntegration) {
      startInlineEdit(refreshedIntegration);
    }
  } catch (err) {
    alert("Failed to save integration: " + err.message);
  } finally {
    inlineSaving.value = false;
  }
}

function addContainerSource() {
  containerForm.sources.push(createContainerSource());
}

function removeContainerSource(index) {
  if (containerForm.sources.length <= 2) return;
  containerForm.sources.splice(index, 1);
}

async function cloneIntegration(integration) {
  cloning[integration.id] = true;
  try {
    const isComposable = isComposableIntegration(integration);
    const payload = {
      name: createCloneName(integration.name),
      description: integration.description || null,
      favorite: Boolean(integration.favorite),
      type: normalizeIntegrationType(integration.type),
      url: isComposable ? "" : (integration.url || ""),
      auth_type: isComposable ? "none" : (integration.auth_type || "none"),
      key_name: isComposable ? null : (integration.key_name || null),
      response_type: isComposable ? "json" : (integration.response_type || "json"),
      response_path: isComposable ? null : (integration.response_path || null),
      crawler_pagination_config: isComposable
        ? null
        : (integration.crawler_pagination_config || null),
      transform_steps: Array.isArray(integration.transform_steps) ? integration.transform_steps : [],
      output_primary_key_path: integration.output_primary_key_path || null,
      container_config: isComposable
        ? (
            integration.container_config
              ? {
                  sources: Array.isArray(integration.container_config.sources)
                    ? integration.container_config.sources.map((source) => ({
                        integration_id: String(source.integration_id || "").trim(),
                        source_key_path: source.source_key_path || null,
                        target_key_path: source.target_key_path || null,
                        merge_style: source.merge_style === "nested" ? "nested" : "flat",
                        nested_key: source.merge_style === "nested"
                          ? (String(source.nested_key || "").trim() || null)
                          : null,
                        keep_target_key: Boolean(source.keep_target_key),
                      }))
                    : [],
                  target_source_integration_id: integration.container_config.target_source_integration_id || null,
                  merge_mode: integration.container_config.merge_mode || "full_outer",
                  conflict_mode: integration.container_config.conflict_mode || "last_wins",
                }
              : null
          )
        : null,
    };

    const clonedIntegration = await api.createIntegration(payload);
    await loadIntegrations();
    const clonedId = String(
      clonedIntegration?.id
        ?? clonedIntegration?.integration?.id
        ?? clonedIntegration?.data?.id
        ?? "",
    ).trim();
    const clonedRecord = integrations.value.find((entry) =>
      String(entry?.id || "").trim() === clonedId
    ) || integrations.value.find((entry) =>
      String(entry?.name || "").trim() === payload.name
    );
    if (clonedRecord) {
      const selectedId = String(clonedRecord.id || "").trim();
      lastNavigatedIntegrationId.value = selectedId;
      startInlineEdit(clonedRecord);
      await scrollToIntegrationTop(selectedId);
    }
  } catch (err) {
    alert("Failed to clone integration: " + err.message);
  } finally {
    cloning[integration.id] = false;
  }
}

function confirmDelete(integration) {
  deleteConfirm.value = integration;
}

async function doDelete() {
  if (!deleteConfirm.value) return;
  deleting.value = true;
  try {
    await api.deleteIntegration(deleteConfirm.value.id);
    if (inlineEditId.value === deleteConfirm.value.id) {
      cancelInlineEdit("");
    }
    deleteConfirm.value = null;
    await loadIntegrations();
  } catch (err) {
    alert("Failed to delete integration: " + err.message);
  } finally {
    deleting.value = false;
  }
}

async function toggleFavorite(integration) {
  const integrationId = String(integration?.id || "").trim();
  if (!integrationId || favoriteSaving[integrationId]) {
    return;
  }
  const nextFavoriteState = !Boolean(integration.favorite);
  favoriteSaving[integrationId] = true;
  try {
    await api.updateIntegration(integrationId, { favorite: nextFavoriteState });
    integration.favorite = nextFavoriteState;
  } catch (err) {
    alert("Failed to update favorite state: " + err.message);
  } finally {
    favoriteSaving[integrationId] = false;
  }
}

async function runHealthCheck(integration) {
  if (isComposableIntegration(integration)) return;
  healthChecking[integration.id] = true;
  delete healthResults[integration.id];
  try {
    const result = await api.healthCheckIntegration(integration.id);
    healthResults[integration.id] = result;
  } catch (err) {
    healthResults[integration.id] = { ok: false, error: err.message };
  } finally {
    healthChecking[integration.id] = false;
  }
}

async function fetchData(integration) {
  fetching[integration.id] = true;
  delete processingStatusById[integration.id];
  try {
    const result = await api.fetchIntegrationData(integration.id);
    await loadIntegrations();
    const integrationId = String(integration?.id || "").trim();
    if (integrationId) {
      processingStatusById[integrationId] = {
        type: "success",
        message: `Data fetched. Schema updated. ${formatMediaCacheStatus(result)}`,
      };
    }
    if (integrationId && integrationId === String(manageSchemaIntegrationId.value || "").trim()) {
      await loadManageSchema(integrationId);
    }
    if (integrationId && integrationId === String(reviewIntegrationId.value || "").trim()) {
      await loadReviewItems({ preserveSelection: true });
    }
  } catch (err) {
    alert("Failed to fetch data: " + err.message);
  } finally {
    fetching[integration.id] = false;
  }
}

async function reprocessData(integration) {
  reprocessing[integration.id] = true;
  delete processingStatusById[integration.id];
  try {
    const result = await api.reprocessIntegrationData(integration.id);
    await loadIntegrations();
    const integrationId = String(integration?.id || "").trim();
    if (integrationId) {
      processingStatusById[integrationId] = {
        type: "success",
        message: `Processing completed. Schema updated. ${formatMediaCacheStatus(result)}`,
      };
    }
    if (integrationId && integrationId === String(manageSchemaIntegrationId.value || "").trim()) {
      await loadManageSchema(integrationId);
    }
    if (integrationId && integrationId === String(reviewIntegrationId.value || "").trim()) {
      await loadReviewItems({ preserveSelection: true });
    }
  } catch (err) {
    alert("Failed to reprocess data: " + err.message);
  } finally {
    reprocessing[integration.id] = false;
  }
}

async function deepFetchData(integration) {
  if (!isComposableIntegration(integration)) return;
  deepFetching[integration.id] = true;
  delete processingStatusById[integration.id];
  try {
    const startedJob = await api.startIntegrationDeepFetch(integration.id);
    const jobId = String(startedJob?.job_id || "").trim();
    if (!jobId) {
      throw new Error("Deep fetch job did not return a job ID");
    }

    const deadline = Date.now() + 30 * 60 * 1000;
    let status = String(startedJob?.status || "queued").trim();

    while (status === "queued" || status === "running") {
      if (Date.now() >= deadline) {
        throw new Error(
          "Deep fetch is still running in the background. Please refresh integration data in a few minutes."
        );
      }
      await new Promise((resolve) => setTimeout(resolve, 3000));
      const jobState = await api.getIntegrationDeepFetchJob(jobId);
      status = String(jobState?.status || "").trim();

      if (status === "failed") {
        throw new Error(String(jobState?.error || "Deep fetch failed"));
      }
    }

    if (status !== "succeeded") {
      throw new Error(`Deep fetch ended with unexpected status '${status || "unknown"}'`);
    }
    await loadIntegrations();
    const integrationId = String(integration?.id || "").trim();
    if (integrationId) {
      processingStatusById[integrationId] = {
        type: "success",
        message: "Deep fetch completed. Schema and media cache updated.",
      };
    }
    if (integrationId && integrationId === String(manageSchemaIntegrationId.value || "").trim()) {
      await loadManageSchema(integrationId);
    }
    if (integrationId && integrationId === String(reviewIntegrationId.value || "").trim()) {
      await loadReviewItems({ preserveSelection: true });
    }
  } catch (err) {
    alert("Failed to deep fetch data: " + err.message);
  } finally {
    deepFetching[integration.id] = false;
  }
}

async function showPreview(integration) {
  const integrationId = String(integration?.id || "").trim();
  if (!integrationId) return;
  previewLoading.value = true;
  previewIntegrationId.value = integrationId;
  previewSelectedItemIndex.value = 0;
  previewActiveTab.value = "item";
  try {
    const [rawPreview, storedData, schemaPayload] = await Promise.all([
      api.getIntegrationDataPreview(integrationId),
      api.getIntegrationData(integrationId),
      api.getIntegrationSchema(integrationId).catch(() => null),
    ]);
    const availableKeys = normalizePrimeKeyOptions(rawPreview?.available_keys);
    const savedOutputPrimeKey = String(integration?.output_primary_key_path || "").trim();
    const outputPrimeKeyResolved = savedOutputPrimeKey || (availableKeys.includes("id") ? "id" : "");
    const storedItems = Array.isArray(storedData?.data)
      ? storedData.data
      : (storedData?.data == null ? [] : [storedData.data]);
    const cappedItems = storedItems.slice(0, PREVIEW_ITEM_LIMIT);
    const previewItem = cappedItems[0] ?? rawPreview?.preview_item ?? null;
    previewData.value = {
      ...rawPreview,
      data: cappedItems.length > 0 ? cappedItems : rawPreview?.preview_item,
      item_count: storedData?.item_count ?? rawPreview?.total_items ?? cappedItems.length,
      total_items: rawPreview?.total_items ?? storedData?.item_count ?? cappedItems.length,
      fetched_at: rawPreview?.fetched_at ?? storedData?.fetched_at ?? null,
      options: rawPreview?.options ?? storedData?.options ?? {},
      option_types: rawPreview?.option_types ?? storedData?.option_types ?? {},
      preview_item: previewItem,
      item_label_path: getSchemaItemLabelPath(schemaPayload),
      items_truncated: storedItems.length > cappedItems.length,
      output_primary_key_path_resolved: outputPrimeKeyResolved,
    };
  } catch (err) {
    alert("Failed to load preview: " + err.message);
  } finally {
    previewLoading.value = false;
  }
}

function closePreview() {
  previewData.value = null;
  previewIntegrationId.value = "";
  previewSelectedItemIndex.value = 0;
  previewActiveTab.value = "item";
}

async function previewSourceIntegration(integrationId) {
  const sourceId = String(integrationId || "").trim();
  if (!sourceId) {
    alert("Select a source integration first.");
    return;
  }
  const integration = integrations.value.find((entry) => String(entry.id) === sourceId);
  if (!integration) {
    alert("Selected source integration was not found.");
    return;
  }
  await showPreview(integration);
}

function formatDateTime(dateStr) {
  return formatInstantInServerTimezone(dateStr);
}

function normalizeMediaCacheStats(result) {
  const raw = result?.media_cache_stats && typeof result.media_cache_stats === "object"
    ? result.media_cache_stats
    : {};
  const read = (key) => {
    const value = Number(raw[key] || 0);
    return Number.isFinite(value) ? value : 0;
  };
  return {
    found: read("found"),
    imported: read("imported"),
    reused: read("reused"),
    localized: read("localized"),
    skipped: read("skipped"),
    queued: read("queued"),
  };
}

function formatMediaCacheStatus(result) {
  const stats = normalizeMediaCacheStats(result);
  if (!stats.found) {
    return "Media cache: no cache-media URLs found.";
  }
  const details = [
    `found ${stats.found}`,
    `imported ${stats.imported}`,
    `reused ${stats.reused}`,
    `localized ${stats.localized}`,
    `skipped ${stats.skipped}`,
  ];
  if (stats.queued > 0) {
    details.push(`queued ${stats.queued}`);
  }
  return `Media cache: ${details.join(", ")}.`;
}

onMounted(() => {
  resetInlineForm();
  resetContainerForm();
  loadIntegrations();
  loadConnectionTemplates();
  loadConnectionConfig();
});

onUnmounted(() => {
  clearConnectionAutosaveStatusTimer();
});
</script>

<style scoped>
.loading-state {
  text-align: center;
  padding: 48px;
  color: #64748b;
}

.card-hint {
  color: #64748b;
  font-size: 13px;
  margin: 0;
}

.manage-reference-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

.manage-reference-section h3 {
  margin: 0 0 8px;
  font-size: 13px;
  color: #334155;
}

.manage-reference-section dl {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px 14px;
  margin: 0;
}

.manage-reference-section div {
  display: grid;
  grid-template-columns: minmax(96px, 0.42fr) minmax(0, 1fr);
  gap: 8px;
}

.manage-reference-section dt {
  color: #334155;
  font-size: 12px;
  font-weight: 800;
}

.manage-reference-section dd {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.35;
}

.integration-case-hint {
  margin-top: 6px;
}

.integration-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.form-row-four {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group-full {
  grid-column: 1 / -1;
}

.form-group label {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.form-group input,
.form-group select,
.form-group textarea {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.15s, box-shadow 0.15s;
  background: #fff;
}

.form-group textarea {
  resize: vertical;
  min-height: 80px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-hint {
  font-size: 12px;
  color: #64748b;
  margin: 0;
}

.checkbox-group {
  display: flex;
  gap: 12px;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.env-info {
  margin-top: 6px;
  display: inline-flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #0c4a6e;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  padding: 8px 10px;
}

.env-info code {
  background: #dbeafe;
  border-radius: 5px;
  padding: 2px 6px;
}

.transform-editor {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px;
  background: #f8fafc;
  gap: 10px;
  display: grid;
}

.transform-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.transform-step-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}

.transform-step {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.transform-step--dragging {
  opacity: 0.58;
  border-color: #93c5fd;
  background: #f8fbff;
}

.transform-step-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.transform-step-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.drag-handle,
.transform-step-collapse {
  width: 28px;
  height: 28px;
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  background: #f8fafc;
  color: #64748b;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.drag-handle {
  cursor: grab;
}

.drag-handle:active {
  cursor: grabbing;
}

.drag-handle:hover,
.transform-step-collapse:hover {
  border-color: #93c5fd;
  color: #2563eb;
  background: #eff6ff;
}

.transform-step-collapse {
  cursor: pointer;
}

.transform-step-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.step-index {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.transform-step-actions {
  display: flex;
  gap: 6px;
}

.form-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.empty-state {
  text-align: center;
  padding: 32px;
  color: #64748b;
}

.empty-state.compact {
  padding: 14px;
  text-align: left;
}

.manage-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 16px;
  align-items: start;
}

.manage-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.manage-side {
  position: sticky;
  top: 72px;
  align-self: start;
}

.manage-side :deep(.admin-sticky-sidebar__body) {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.manage-navigator-controls {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  flex: 0 0 auto;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.manage-navigator-controls .form-group {
  min-width: 0;
}

.manage-navigator-empty {
  margin-top: 12px;
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 10px;
  font-size: 13px;
  color: #64748b;
  background: #f8fafc;
}

.manage-navigator-list {
  min-height: 0;
  flex: 1 1 auto;
  overflow: auto;
  margin-top: 12px;
  padding-right: 4px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.manage-navigator-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.manage-navigator-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.manage-navigator-group-title {
  font-size: 11px;
  color: #64748b;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.manage-navigator-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  padding: 8px 10px;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.manage-navigator-item:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.manage-navigator-item:focus-visible {
  outline: none;
  border-color: var(--admin-accent, #4f46e5);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--admin-accent, #4f46e5) 18%, transparent);
}

.manage-navigator-item.active {
  border-color: color-mix(in srgb, var(--admin-accent, #4f46e5) 75%, #ffffff);
  background: color-mix(in srgb, var(--admin-accent, #4f46e5) 10%, #ffffff);
}

.manage-navigator-subsections {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: -2px 0 2px 16px;
  padding-left: 10px;
  border-left: 2px solid #e2e8f0;
}

.manage-navigator-subsection {
  width: 100%;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #475569;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 8px;
  text-align: left;
  font-size: 12px;
  font-weight: 700;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.manage-navigator-subsection:hover,
.manage-navigator-subsection.active {
  background: #eef2ff;
  color: #3730a3;
}

.manage-navigator-subsection:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--admin-accent, #4f46e5) 18%, transparent);
}

.manage-navigator-item-name {
  min-width: 0;
  flex: 1;
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.manage-navigator-item-badges {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.navigator-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  padding: 2px 7px;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  text-transform: uppercase;
}

.navigator-badge--favorite {
  background: color-mix(in srgb, var(--admin-favorite-color, #b45309) 15%, #ffffff);
  color: var(--admin-favorite-color, #b45309);
}

.navigator-badge--type {
  background: #e2e8f0;
  color: #334155;
}

.navigator-badge--return {
  background: #dbeafe;
  color: #1d4ed8;
}

.selected-integration-card {
  min-width: 0;
}

.selected-integration-item {
  padding: 0;
}

.integrations-list {
  display: flex;
  flex-direction: column;
}

.grouped-list {
  gap: 14px;
}

.integration-type-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.integration-type-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 4px 2px 0;
}

.type-group-label {
  font-size: 12px;
  color: #1e3a8a;
  font-weight: 700;
}

.integration-group {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  overflow: hidden;
}

.integration-group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 10px 14px;
  background: #eef2ff;
  border-bottom: 1px solid #dbeafe;
}

.group-url {
  font-size: 12px;
  color: #1e3a8a;
  word-break: break-all;
}

.group-count {
  margin-left: auto;
  font-size: 12px;
  color: #475569;
}

.integration-item {
  gap: 24px;
  display: flex;
  flex-direction: column;
}

.integration-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.integration-name {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.favorite-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  background: color-mix(in srgb, var(--admin-favorite-color, #b45309) 15%, #ffffff);
  color: var(--admin-favorite-color, #b45309);
}

.return-type-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.return-type-badge.return-type-list {
  background: #dbeafe;
  color: #1d4ed8;
}

.return-type-badge.return-type-object {
  background: #dcfce7;
  color: #166534;
}

.return-type-badge.return-type-unknown {
  background: #e2e8f0;
  color: #334155;
}

.integration-actions {
  display: flex;
  gap: 8px;
}

.btn-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  color: #64748b;
}

.btn-icon:hover {
  background: var(--admin-accent, #4f46e5);
  border-color: var(--admin-accent, #4f46e5);
  color: #fff;
}

.btn-icon:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-icon:disabled:hover {
  background: #f8fafc;
  border-color: #e2e8f0;
  color: #64748b;
}

.btn-icon.active {
  background: color-mix(in srgb, var(--admin-accent, #4f46e5) 88%, black);
  border-color: color-mix(in srgb, var(--admin-accent, #4f46e5) 88%, black);
  color: #fff;
}

.btn-icon.btn-favorite {
  background: color-mix(in srgb, var(--admin-favorite-color, #b45309) 12%, #ffffff);
  border-color: color-mix(in srgb, var(--admin-favorite-color, #b45309) 35%, #ffffff);
  color: var(--admin-favorite-color, #b45309);
}

.btn-icon.btn-favorite:hover {
  background: var(--admin-favorite-color, #b45309);
  border-color: var(--admin-favorite-color, #b45309);
  color: #fff;
}

.btn-icon.btn-favorite.active {
  background: var(--admin-favorite-color, #b45309);
  border-color: var(--admin-favorite-color, #b45309);
  color: #fff;
}

.integration-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 13px;
}

.detail-label {
  color: #64748b;
  font-weight: 600;
}

.detail-value {
  color: #0f172a;
}

.detail-value.url {
  word-break: break-all;
}

.detail-value.path-value,
.detail-value.key-name {
  color: #4f46e5;
}

.detail-value.no-data {
  color: #9ca3af;
}

.tag-list {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 6px;
}

.container-tag {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #c7d2fe;
  background: #eef2ff;
  color: #3730a3;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
}

.target-pill {
  border-color: #bfdbfe;
  background: #dbeafe;
  color: #1d4ed8;
}

.target-chip-row {
  margin-top: 8px;
}

.target-source-step {
  border-color: #93c5fd;
  background: #f0f9ff;
}

.connection-card-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.connection-card-body {
  display: grid;
  gap: 12px;
}

.connection-sections {
  margin-top: 0;
}

.connection-exposure-groups {
  margin-top: 0;
}

.connection-exposure-row input {
  flex: 0 0 auto;
}

.connection-exposure-row .admin-list-tabs__item-main {
  flex: 1 1 auto;
}

.connection-template-row.muted {
  opacity: 0.54;
}

.connection-template-row.muted .connection-template-name,
.connection-template-row.muted .template-return-select {
  color: #94a3b8;
}

.connection-filter-row {
  margin: 12px 0 4px;
  display: flex;
  justify-content: flex-end;
}

.connection-template-main {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(320px, auto) auto;
  align-items: end;
  gap: 12px;
}

.connection-template-title {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.connection-template-title .form-hint {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.connection-template-name {
  line-height: 1.25;
}

.connection-template-controls {
  display: grid;
  grid-template-columns: repeat(2, minmax(140px, 1fr));
  align-items: end;
  gap: 10px;
}

.template-return-select {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #334155;
}

.template-return-select.stacked {
  align-items: stretch;
  flex-direction: column;
  gap: 4px;
  font-weight: 600;
}

.template-return-select.stacked span {
  font-size: 11px;
  line-height: 1.2;
}

.template-return-select select {
  min-width: 140px;
  width: 100%;
}

.connection-template-actions {
  align-self: end;
  justify-content: flex-end;
  flex-wrap: nowrap;
}

.type-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.type-badge.api,
.type-badge.base {
  background: #dbeafe;
  color: #1d4ed8;
}

.type-badge.crawler {
  background: #fef3c7;
  color: #92400e;
}

.type-badge.composable,
.type-badge.container {
  width: unset;
  background: #dcfce7;
  color: #166534;
}

.integration-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
}

.selected-integration-item--editing .integration-buttons {
  position: sticky;
  bottom: 0;
  z-index: 8;
  margin-top: 4px;
  padding: 10px 0 14px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), #fff 36%);
  border-top: 1px solid #e2e8f0;
}

.integration-actions-left,
.integration-actions-right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.integration-actions-right {
  margin-left: auto;
}

.health-result {
  margin-top: 10px;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
}

.health-result.success {
  background: #ecfdf5;
  border: 1px solid #86efac;
  color: #166534;
}

.health-result.error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.processing-status-row {
  margin-top: 8px;
}

.integration-separator {
  margin-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.manage-subsection-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.manage-subsection {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  overflow: hidden;
}

.manage-subsection-toggle {
  width: 100%;
  border: 0;
  background: transparent;
  color: #0f172a;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 800;
  text-align: left;
}

.manage-subsection-toggle span {
  flex: 1;
}

.manage-subsection-toggle svg {
  margin-right: 6px;
}

.manage-subsection-toggle:hover,
.manage-subsection-toggle.active {
  background: #eef2ff;
  color: #3730a3;
}

.manage-subsection-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  border-top: 1px solid #e2e8f0;
  padding: 12px;
  background: #fff;
}

.readonly-field {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  color: #475569;
  font-size: 14px;
  font-weight: 600;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 999;
}

.modal-dialog {
  width: min(560px, 100%);
  max-height: calc(100vh - 40px);
  overflow: auto;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 40px rgba(15, 23, 42, 0.25);
  padding: 20px;
}

.modal-dialog.modal-large {
  width: min(900px, calc(100vw - 40px));
  max-width: calc(100vw - 40px);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.modal-header h3,
.modal-dialog h3,
.transform-editor-header h3 {
  margin: 0;
  font-size: 15px;
  color: var(--admin-text);
}

.modal-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 16px;
}

.preview-info {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 13px;
  color: #475569;
}

.preview-selector {
  margin-bottom: 10px;
}

.preview-selector select {
  width: 100%;
}

.preview-tabs {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}

.preview-tabs .btn-outline {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.preview-content {
  max-height: min(500px, 75vh);
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
}

.preview-content pre {
  margin: 0;
  font-size: 12px;
}

.preview-section-title {
  margin: 0 0 8px;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.review-toolbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.review-sync-settings {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.review-sync-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  user-select: none;
}

.review-sync-toggle input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.review-sync-toggle.disabled {
  color: #94a3b8;
  cursor: wait;
}

.review-sync-toggle.disabled input {
  cursor: wait;
}

.review-select-group {
  flex: 1;
  min-width: 260px;
}

.manage-schema-panel {
  padding: 0;
}

.manage-subsection-body.manage-schema-panel {
  margin-top: 0;
  border: 0;
  border-top: 1px solid #e2e8f0;
  border-radius: 0;
}

.schema-muted-value {
  color: #94a3b8;
}

.checkbox-item-compact {
  margin: 0;
}

.btn-outline.active {
  border-color: #2563eb;
  background: #eff6ff;
  color: #1d4ed8;
}

.review-summary {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  color: #475569;
  font-size: 13px;
}

.review-summary span {
  padding: 4px 8px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.review-warning {
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #fbbf24;
  background: #fffbeb;
  color: #92400e;
  font-size: 13px;
}

.review-filters,
.review-meta-panel {
  display: grid;
  gap: 12px;
  margin-bottom: 14px;
}

.review-filters {
  grid-template-columns: repeat(2, minmax(180px, 1fr));
}

.review-meta-panel {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.review-meta-panel .form-group {
  min-width: 0;
}

.review-item-panel .review-filters {
  gap: 10px;
  margin-bottom: 0;
  display: flex;
}

.review-item-panel .review-filters .form-group {
  width: 50%;
}

.review-item-panel .add-item {
  width: 100%;
}

.loading-state.compact {
  padding: 24px;
}

.review-item-panel {
  min-width: 0;
}

.review-sidebar-controls {
  display: grid;
  gap: 12px;
  margin-bottom: 12px;
}

.review-item-search-row {
  display: flex;
  gap: 8px;
}

.review-item-search-input {
  flex: 1;
  min-width: 0;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 7px 10px;
  font-size: 12px;
  background: #fff;
  color: #0f172a;
}

.review-item-search-input:focus {
  outline: none;
  border-color: var(--admin-accent, #4f46e5);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--admin-accent, #4f46e5) 16%, transparent);
}

.review-item-search-input::placeholder {
  color: #94a3b8;
}

.review-item-search-clear {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  padding: 0 10px;
  cursor: pointer;
}

.review-item-search-clear:hover {
  background: #f8fafc;
  color: #0f172a;
}

.review-item-section-title {
  margin-top: 14px;
  margin-bottom: 8px;
}

.review-item-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: clamp(220px, calc(100vh - 410px), 680px);
  overflow: auto;
  padding-right: 4px;
}

.review-item-button {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #1e293b;
  padding: 8px 10px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.review-item-button:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.review-item-button:focus-visible {
  outline: none;
  border-color: var(--admin-accent, #4f46e5);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--admin-accent, #4f46e5) 18%, transparent);
}

.review-item-button.active {
  border-color: color-mix(in srgb, var(--admin-accent, #4f46e5) 75%, #ffffff);
  background: color-mix(in srgb, var(--admin-accent, #4f46e5) 10%, #ffffff);
}

.review-item-title {
  display: block;
  width: 100%;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.review-item-meta,
.review-field-badges {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  margin-top: 0;
}

.review-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 800;
}

.review-badge.changed {
  background: #dbeafe;
  color: #1d4ed8;
}

.review-badge.override {
  background: #ecfdf5;
  color: #047857;
}

.review-badge.conflict {
  background: #fee2e2;
  color: #b91c1c;
}

.review-badge.local {
  background: #fef3c7;
  color: #92400e;
}

.review-badge.incomplete {
  background: #ffedd5;
  color: #9a3412;
}

.review-badge.state {
  background: #f1f5f9;
  color: #334155;
}

.review-badge.page {
  max-width: 100%;
  white-space: nowrap;
}

.review-badge.page-missing {
  background: #f1f5f9;
  color: #475569;
}

.review-badge.page-syncing {
  background: #e0f2fe;
  color: #0369a1;
}

.review-badge.page-locked {
  background: #fef3c7;
  color: #92400e;
}

.review-tag-row,
.review-tag-editor {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 0;
}

.review-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 100%;
  padding: 3px 7px;
  border-radius: 999px;
  background: #eef2ff;
  color: #3730a3;
  font-size: 11px;
  font-weight: 700;
  overflow-wrap: anywhere;
}

.review-tag.editable button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border: 0;
  border-radius: 999px;
  background: #c7d2fe;
  color: #312e81;
  cursor: pointer;
  font-size: 10px;
  line-height: 1;
}

.review-tag-editor input {
  min-width: 140px;
  flex: 1;
}

.review-add-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.review-add-table {
  min-width: 720px;
}

.review-add-table .review-value-input,
.review-add-table .review-value-display,
.review-add-table .review-datetime-picker {
  width: min(520px, 100%);
}

.review-detail {
  min-width: 0;
}

.review-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 12px;
}

.review-detail-header > div:first-child {
  min-width: 0;
}

.review-detail-header h3 {
  margin: 0 0 4px;
  color: #0f172a;
  font-size: 16px;
}

.review-detail-header .review-badge {
  margin-left: 10px;
}

.review-detail-header-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.review-generated-pages {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-width: 100%;
  margin-top: 8px;
}

.review-generated-page-entry {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  min-width: 0;
}

.review-generated-page-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
  min-width: 0;
  border: 1px solid #cbd5e1;
  border-radius: var(--admin-button-border-radius);
  background: #f8fafc;
  color: #334155;
  padding: var(--admin-button-padding-y) var(--admin-button-padding-x);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
}

.review-generated-page-chip.page-syncing {
  border-color: #bae6fd;
  background: #f0f9ff;
  color: #075985;
}

.review-generated-page-chip.page-locked {
  border-color: #fde68a;
  background: #fffbeb;
  color: #92400e;
}

.review-generated-page-chip.page-missing {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #64748b;
}

.review-generated-page-template,
.review-generated-page-chip code {
  min-width: 0;
  max-width: min(360px, 100%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.review-generated-page-status {
  white-space: nowrap;
}

.review-generated-page-route {
  border-radius: 5px;
  background: transparent;
  padding: 0;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.2;
}

.review-generated-page-open {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid #cbd5e1;
  border-radius: var(--admin-button-border-radius);
  background: #fff;
  color: #334155;
  padding: var(--admin-button-padding-y) var(--admin-button-padding-x);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
  cursor: pointer;
  white-space: nowrap;
}

.review-generated-page-open:hover {
  border-color: #94a3b8;
  background: #f8fafc;
}

.review-field-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.review-field-table th,
.review-field-table td {
  border-bottom: 1px solid #e2e8f0;
  padding: 8px;
  text-align: left;
}

.review-field-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #f8fafc;
  color: #334155;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0;
}

.review-field-table tr.conflict {
  background: #fff7f7;
}

.review-field-table tr.changed:not(.conflict) {
  background: #f8fbff;
}

.review-field-table pre {
  max-width: 220px;
  max-height: 140px;
  overflow: auto;
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 11px;
}

.review-field-path {
  min-width: 160px;
  max-width: 260px;
  overflow-wrap: anywhere;
}

.review-value-input,
.review-value-display,
.review-datetime-picker {
  width: min(360px, 100%);
}

.review-value-input,
.review-value-display {
  min-height: 72px;
  resize: vertical;
  border-radius: 8px;
  padding: 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
}

.review-value-input {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #0f172a;
}

.review-value-input:focus {
  outline: none;
  border-color: var(--admin-accent, #4f46e5);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--admin-accent, #4f46e5) 18%, transparent);
}

.review-datetime-picker :deep(.dp__input_wrap) {
  width: 100%;
}

.review-datetime-picker :deep(.dp__input) {
  width: 100%;
  min-height: 34px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
  font-size: 12px;
  line-height: 1.4;
}

.review-datetime-picker :deep(.dp__input:focus) {
  border-color: var(--admin-accent, #4f46e5);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--admin-accent, #4f46e5) 18%, transparent);
}

.review-value-input:disabled,
.review-value-input--disabled {
  cursor: default;
  opacity: 1;
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #475569;
  -webkit-text-fill-color: #475569;
}

.review-value-input::placeholder {
  color: #94a3b8;
  opacity: 1;
}

.review-value-display {
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #0f172a;
}

.review-value-display.muted {
  background: #f8fafc;
  color: #94a3b8;
  border-color: #e2e8f0;
}

.review-value-input--warning {
  border-color: #f59e0b !important;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.16);
}

.review-datetime-picker.review-value-input--warning :deep(.dp__input) {
  border-color: #f59e0b !important;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.16);
}

.review-value-input--long-text {
  width: min(520px, 100%);
}

input.review-value-input,
select.review-value-input {
  min-height: 0;
  height: 34px;
  resize: none;
}

select.review-value-input--multi-select {
  height: auto;
  min-height: 92px;
  padding: 6px 8px;
}

.review-image-preview {
  margin-bottom: 6px;
}

.review-image-preview img {
  display: block;
  max-width: 180px;
  max-height: 120px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  object-fit: contain;
  background: #fff;
}

.review-image-picker-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(360px, 100%);
  min-height: 72px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  padding: 8px;
}

.review-image-picker-preview-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.review-image-picker-preview {
  flex: 0 0 auto;
  margin-bottom: 0;
}

.review-image-picker-preview-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 180px;
  min-height: 80px;
  border: 1px dashed #cbd5e1;
  border-radius: 6px;
  background: #f8fafc;
  color: #94a3b8;
  font-size: 11px;
}

.review-image-picker-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  align-self: flex-start;
  min-height: 32px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #0f172a;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.review-image-picker-button:hover:not(:disabled),
.review-image-picker-button:focus-visible {
  border-color: var(--admin-accent, #4f46e5);
  background: color-mix(in srgb, var(--admin-accent, #4f46e5) 8%, #fff);
  outline: none;
}

.review-image-picker-button:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.review-image-picker-url,
.review-image-picker-empty {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 11px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.review-image-picker-empty {
  color: #94a3b8;
}

.review-field-note {
  margin-top: 4px;
  color: #64748b;
  font-size: 11px;
}

.review-history {
  margin-top: 6px;
}

.review-history summary {
  cursor: pointer;
  color: #475569;
  font-size: 11px;
}

.review-actions-cell {
  min-width: 92px;
}

.review-actions-cell .btn-sm {
  width: 100%;
  margin-bottom: 6px;
}

@media (max-width: 1024px) {
  .manage-layout {
    grid-template-columns: 1fr;
  }

  .manage-side {
    position: static;
  }

  .form-row-four {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .review-filters {
    grid-template-columns: 1fr;
  }

  .review-meta-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .connection-template-main {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .connection-template-actions {
    justify-content: flex-start;
  }

  .review-item-list {
    max-height: 260px;
  }
}

@media (max-width: 768px) {
  .form-row,
  .form-row-four {
    grid-template-columns: 1fr;
  }

  .connection-filter-row {
    justify-content: stretch;
  }

  .connection-filter-row .template-return-select,
  .connection-template-controls {
    width: 100%;
  }

  .connection-template-controls {
    grid-template-columns: 1fr;
  }

  .manage-reference-section dl,
  .manage-reference-section div {
    grid-template-columns: 1fr;
  }

  .manage-reference-section div {
    gap: 2px;
  }

  .integration-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .transform-step-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .review-toolbar,
  .review-detail-header {
    flex-direction: column;
    align-items: stretch;
  }

  .review-meta-panel {
    grid-template-columns: 1fr;
  }
}
</style>
