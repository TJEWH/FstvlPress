<template>
  <div class="templates-page admin-page">
    <AutosaveToast :message="mappingAutosaveToastMessage" :tone="mappingAutosaveStatus" />

    <header class="page-header">
      <h1>Templates</h1>
      <p class="page-subtitle">Build section, container, and page templates in a dedicated template workspace.</p>
    </header>

    <AdminPageTabs
      :tabs="tabs"
      :model-value="activeTab"
      @update:model-value="setActiveTab"
    />

    <section v-if="builderContext" class="templates-builder-shell">
      <p v-if="builderContext.kind === 'page'" class="builder-hint">
        Use the Design panel to edit this template design draft and publish it for all linked pages.
      </p>

      <BasePage
        :key="builderKey"
        :slug="builderSlug"
        :template-builder-context="builderContext"
        :template-preview-payload="mappingPreviewDoc"
        :template-preview-warnings="mappingPreviewWarnings"
        :template-preview-available="showPageMappingEditor"
        :template-preview-loading="previewingMappings"
        :template-preview-disabled="loadingPageTemplateSettings"
        @template-updated="handleTemplateBuilderPayloadUpdated"
        @template-preview-toggle="toggleMappingPreview"
      />

      <div v-if="showPageMappingEditor" class="mapping-card config-card">
        <h3>Page Data Mapping</h3>
        <div v-if="activePageIsItemPageTemplate" class="mapping-heuristics">
          <p>
            <strong>Create:</strong> item pages are generated for each matched item and start as init/hidden so mapped content can be reviewed first.
          </p>
          <p>
            <strong>Source:</strong> mapped fields read the matched integration review row; local review overrides win over fetched integration data.
          </p>
          <p>
            <strong>Sync:</strong> while a generated page is non-public, mapped page edits write back to review overrides and review changes write back to the page.
          </p>
          <p>
            <strong>Publish:</strong> public pages are treated as stable; review changes stop overwriting page values until the page is non-public again or regenerated.
          </p>
        </div>
        <details class="mapping-section">
          <summary class="mapping-section-title">Base</summary>
          <div class="mapping-section-content">
            <div class="mapping-base-grid">
              <div v-if="activePageIsItemPageTemplate" class="mapping-base-panel mapping-base-panel--wide">
                <span class="mapping-base-label">Item Page Routing</span>
                <div class="mapping-routing-grid">
                  <label class="mapping-routing-field">
                    <span>Parent Page</span>
                    <select
                      v-model="pageRoutingDraft.parentCandidateKey"
                      class="admin-control"
                      :disabled="savingTemplateRouting"
                      @change="handleParentCandidateChange"
                    >
                      <option value="">None</option>
                      <optgroup
                        v-for="group in groupedItemPageParentCandidateOptions"
                        :key="group.key"
                        :label="group.label"
                      >
                        <option
                          v-for="candidate in group.options"
                          :key="candidate.value"
                          :value="candidate.value"
                        >
                          {{ candidate.label }}
                        </option>
                      </optgroup>
                    </select>
                  </label>
                  <label class="mapping-routing-field">
                    <span>Subroute</span>
                    <input
                      v-model="pageRoutingDraft.itemPageSubroute"
                      class="admin-control"
                      type="text"
                      placeholder="/gigs"
                      :disabled="savingTemplateRouting"
                    />
                  </label>
                  <label class="mapping-routing-field">
                    <span>Slug Source</span>
                    <code class="mapping-routing-readonly">
                      {{ itemPageSchemaSlugPathLabel }}
                    </code>
                  </label>
                  <div class="mapping-routing-field mapping-routing-preview">
                    <span>Preview</span>
                    <code>{{ pageRoutingEffectivePreview }}</code>
                  </div>
                </div>
                <div
                  v-if="itemPageSlugSourceWarning"
                  class="mapping-routing-warning"
                >
                  <span>{{ itemPageSlugSourceWarning }}</span>
                  <button
                    v-if="mappingUsesIntegration && mappingDraft.primaryIntegrationId"
                    class="btn-secondary btn-sm"
                    type="button"
                    @click="openSelectedIntegrationSchema"
                  >
                    Open Integration Schema
                  </button>
                </div>
                <div class="mapping-routing-actions">
                  <button
                    class="btn-primary btn-sm"
                    type="button"
                    :disabled="savingTemplateRouting"
                    @click="savePageTemplateRouting"
                  >
                    {{ savingTemplateRouting ? "Saving..." : "Save Routing" }}
                  </button>
                  <span
                    v-if="templateRoutingStatus.message"
                    :class="['mapping-routing-status', templateRoutingStatus.type]"
                  >
                    {{ templateRoutingStatus.message }}
                  </span>
                </div>
              </div>

              <div class="mapping-base-panel">
                <span class="mapping-base-label">{{ mappingSupportsSharedItemsProvider ? "Data Source" : "Integration Source" }}</span>
                <div
                  v-if="mappingSupportsSharedItemsProvider"
                  class="mapping-inline"
                >
                  <select
                    v-model="mappingDraft.sourceProvider"
                    class="admin-control"
                    @change="handleMappingSourceProviderChange"
                  >
                    <option :value="PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS">Shared Blog Items</option>
                    <option :value="PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION">Integration Source</option>
                  </select>
                </div>
                <div
                  v-if="mappingUsesIntegration"
                  class="mapping-inline"
                >
                  <select
                    v-model="mappingDraft.primaryIntegrationId"
                    class="admin-control"
                    :disabled="!mappingIntegrationsEnabled"
                  >
                    <option value="">No integration</option>
                    <option
                      v-for="integration in mappingAvailableIntegrations"
                      :key="`mapping-integration-${integration.id}`"
                      :value="integration.id"
                    >
                      {{ integration.name }} ({{ integration.return_type || "unknown" }}, {{ integration.data_count || 0 }} items)
                    </option>
                  </select>
                  <button
                    class="btn-secondary btn-sm"
                    type="button"
                    :disabled="!mappingDraft.primaryIntegrationId"
                    @click="openSelectedIntegrationReviewList"
                  >
                    Review Items
                  </button>
                </div>
                <p v-if="mappingUsesIntegration && !mappingIntegrationsEnabled" class="mapping-disabled-hint">
                  Integrations are disabled for this page template in Admin → Integrations → Expose.
                </p>
              </div>

              <div v-if="mappingPreviewItemOptions.length > 1" class="mapping-base-panel">
                <span class="mapping-base-label">Preview Item</span>
                <select
                  v-model="mappingPreviewItemSelection"
                  class="admin-control"
                  :disabled="previewingMappings"
                >
                  <option
                    v-for="option in mappingPreviewItemOptions"
                    :key="`mapping-preview-item-${option.value}`"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </div>

              <div class="mapping-base-panel">
                <span class="mapping-base-label">Template Type</span>
                <div class="mapping-base-meta">
                  <span>Type <code>{{ activePageIsItemPageTemplate ? mappingSourceType : "static_page" }}</code></span>
                  <span>Kind <code>{{ activePageIsItemPageTemplate ? formatSourceKindLabel(mappingSourceKind) : "page" }}</code></span>
                </div>
              </div>
            </div>
          </div>
        </details>

        <details class="mapping-section">
          <summary class="mapping-section-title">Target Field Visibility</summary>
          <div class="mapping-section-content">
            <label
              v-if="editableVisibilityGroups.length > 0"
              class="create-checkbox mapping-checkbox mapping-visibility-defaults-toggle"
            >
              <input v-model="showDefaultHiddenVisibilityTargets" type="checkbox" />
              <span>Show image transform parameters</span>
            </label>
            <div
              v-if="editableVisibilityGroups.length === 0 && sectionOutputReferenceGroups.length === 0"
              class="mapping-preview"
            >
              <p class="mapping-preview-body">No target fields are available for this template.</p>
            </div>
            <div v-if="editableVisibilityGroups.length > 0" class="mapping-list-groups">
              <div
                v-for="group in editableVisibilityGroups"
                :key="`editable-visibility-${group.path}`"
                class="mapping-group-card"
              >
                <div class="mapping-group-head">
                  <div class="mapping-group-title">
                    <strong>{{ group.label }}</strong>
                    <small>Toggle target fields available in this page template mapping.</small>
                  </div>
                </div>
                <div class="mapping-visibility-grid">
                  <label
                    v-for="option in group.options"
                    :key="`visibility-${group.path}-${option.path}`"
                    class="mapping-visibility-option"
                  >
                    <input
                      type="checkbox"
                      :checked="!option.hidden"
                      @change="setPageTemplateTargetPathHidden(group.path, option.path, !$event.target.checked)"
                    />
                    <span>{{ option.label }}</span>
                  </label>
                </div>
              </div>
            </div>
            <div v-if="sectionOutputReferenceGroups.length > 0" class="mapping-list-groups mapping-output-reference-groups">
              <div
                v-for="group in sectionOutputReferenceGroups"
                :key="`section-output-ref-${group.path}`"
                class="mapping-group-card mapping-output-reference"
              >
                <div class="mapping-group-head">
                  <div class="mapping-group-title">
                    <strong>{{ group.label }}</strong>
                    <small>
                      {{ group.outputModeLabel }} · {{ group.outputFieldCount }} field{{ group.outputFieldCount === 1 ? "" : "s" }}
                    </small>
                  </div>
                  <button
                    class="btn-secondary btn-sm"
                    type="button"
                    @click="openSectionTemplateOutput(group.sectionType, group.sectionTemplateName)"
                  >
                    Open Output
                  </button>
                </div>
              </div>
            </div>
          </div>
        </details>

        <details class="mapping-section" open>
          <summary class="mapping-section-title">Field Mapping</summary>
              <div class="mapping-section-content">
                <div class="mapping-field">
                  <small class="mapping-hint">
                    {{ mappingFieldHint }}
                  </small>
                </div>
            <div v-if="pageListMappingGroups.length === 0" class="mapping-preview">
              <p class="mapping-preview-body">No scoped targets are available for this template.</p>
            </div>
            <IntegrationFieldMappingGroups
              v-else
              :groups="pageListMappingGroups"
              :source-options="mappingComponentSourceOptions"
              :source-column-label="mappingSourceColumnLabel"
              :target-column-label-for-group="mappingTargetColumnLabelForGroup"
              :target-options-for-group="mappingComponentTargetOptionsForGroup"
              @add-mapping="handlePageListMappingAdd"
              @remove-mapping="handlePageListMappingRemove"
            >
              <template #group-actions="{ group }">
                <button
                  v-if="group.kind === 'section'"
                  class="btn-secondary btn-sm"
                  type="button"
                  @click="jumpToSectionTemplate(group.sectionType, group.sectionTemplateName)"
                >
                  Jump To Template
                </button>
              </template>
            </IntegrationFieldMappingGroups>
          </div>
        </details>

      </div>
      <div v-if="showRegenerateAllItemPagesButton" class="template-regenerate-footer">
        <button
          :class="[generatedItemPagesExistForTemplate ? 'btn-danger' : 'btn-primary', 'btn-sm']"
          type="button"
          :disabled="regeneratingPageTemplateItems || !canRegenerateAllItemPagesForTemplate"
          @click="regenerateAllItemPagesForTemplate"
        >
          {{ regenerateAllItemPagesButtonLabel }}
        </button>
        <span
          class="template-regenerate-hint"
          :class="{ 'template-regenerate-hint--blocked': !canRegenerateAllItemPagesForTemplate }"
        >
          {{ regenerateAllItemPagesHint }}
        </span>
        <span
          v-if="pageTemplateRegenerateStatus.message"
          class="template-regenerate-status"
          :class="`template-regenerate-status--${pageTemplateRegenerateStatus.type || 'info'}`"
        >
          {{ pageTemplateRegenerateStatus.message }}
        </span>
      </div>
    </section>

    <section v-else class="templates-list-shell">
      <div v-if="activeTab === 'sections'" class="templates-section-layout">
        <div class="templates-card templates-section-main config-card">
          <div class="card-header">
            <h2>Section Templates</h2>
            <p class="card-hint">Each section type has a built-in <code>default</code> template and optional named variants.</p>
          </div>

          <div class="template-list">
            <div
              v-for="group in groupedSectionTemplates"
              :id="sectionTemplateGroupDomId(group.sectionType)"
              :key="group.sectionType"
              class="template-group"
            >
              <div class="template-group-head">
                <div class="template-group-title">
                  <strong>
                    <font-awesome-icon class="template-row-icon" :icon="getTypeIcon(group.sectionType)" />
                    {{ formatTypeName(group.sectionType) }}
                  </strong>
                  <small>{{ group.templates.length }} template<span v-if="group.templates.length !== 1">s</span></small>
                </div>
                <form class="template-group-create" @submit.prevent="createSectionTemplate(group.sectionType)">
                  <input
                    v-model="sectionCreateDrafts[group.sectionType]"
                    class="admin-control create-control--name"
                    type="text"
                    placeholder="new template name"
                    :aria-label="`New ${formatTypeName(group.sectionType)} template name`"
                  />
                  <button
                    class="btn-primary btn-sm"
                    type="submit"
                    :disabled="!canCreateSectionTemplate(group.sectionType)"
                  >
                    Create
                  </button>
                </form>
              </div>
              <div class="template-group-items admin-list">
                <div
                  v-for="tpl in group.templates"
                  :key="`${tpl.section_type}:${tpl.template_name}`"
                  class="template-row admin-list-item"
                >
                  <div class="template-row-main admin-list-item-main">
                    <div class="template-name-edit">
                      <span v-if="tpl.template_name === 'default'" class="template-name-static">default</span>
                      <input
                        v-else
                        v-model="sectionRenameDrafts[sectionTemplateKey(tpl.section_type, tpl.template_name)]"
                        class="admin-control admin-inline-input"
                        type="text"
                        placeholder="template name"
                        :disabled="Boolean(sectionRenaming[sectionTemplateKey(tpl.section_type, tpl.template_name)])"
                        @blur="submitSectionTemplateRename(tpl)"
                        @keydown.enter.prevent="submitSectionTemplateRename(tpl)"
                        @keydown.esc.prevent="resetSectionTemplateDraft(tpl)"
                      />
                      <small class="template-name-hint">/{{ tpl.section_type }}/{{ tpl.template_name }}</small>
                    </div>
                  </div>
                  <div class="template-row-actions admin-list-item-actions">
                    <button
                      class="template-favorite-button"
                      :class="{ active: isSectionTemplateFavorite(tpl) }"
                      type="button"
                      :disabled="isSectionTemplateFavoriteSaving(tpl)"
                      :aria-pressed="isSectionTemplateFavorite(tpl)"
                      :title="isSectionTemplateFavorite(tpl) ? 'Remove Favorite' : 'Add Favorite'"
                      @click="toggleSectionTemplateFavorite(tpl)"
                    >
                      <font-awesome-icon :icon="faStar" />
                    </button>
                    <button class="btn-primary btn-sm" type="button" @click="openSectionTemplate(tpl.section_type, tpl.template_name)">
                      Edit
                    </button>
                    <button class="btn-secondary btn-sm" type="button" @click="promptDuplicateSectionTemplate(tpl)">
                      Duplicate
                    </button>
                    <button
                      class="btn-danger btn-sm"
                      type="button"
                      :disabled="tpl.template_name === 'default'"
                      @click="deleteSectionTemplate(tpl)"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <AdminStickySidebar
          class="templates-section-side"
          title="Section Navigator"
          :count-label="`${filteredSectionTemplateNavigatorCount} visible`"
          aria-label="Section templates"
        >
          <div class="section-template-sidebar-controls">
            <div class="section-template-search-row">
              <input
                v-model="sectionTemplateSearchQuery"
                type="text"
                class="section-template-search-input"
                placeholder="Search templates..."
                aria-label="Search section templates"
              />
              <button
                v-if="sectionTemplateSearchQuery"
                type="button"
                class="section-template-search-clear"
                aria-label="Clear section template search"
                @click="sectionTemplateSearchQuery = ''"
              >
                Clear
              </button>
            </div>
          </div>

          <div v-if="filteredFavoriteSectionTemplates.length" class="section-template-favorites">
            <div class="section-template-favorites-title">
              <font-awesome-icon :icon="faStar" />
              <span>Favorites</span>
            </div>
            <div class="section-template-favorites-list">
              <button
                v-for="tpl in filteredFavoriteSectionTemplates"
                :key="`section-nav-favorite-${sectionTemplateKey(tpl.section_type, tpl.template_name)}`"
                type="button"
                class="section-template-nav-item section-template-nav-item--favorite"
                @click="openSectionTemplate(tpl.section_type, tpl.template_name)"
              >
                <span class="section-template-nav-item-name">{{ formatSectionTemplateLinkLabel(tpl) }}</span>
              </button>
            </div>
          </div>

          <div v-if="groupedSectionTemplates.length === 0" class="section-template-nav-empty">
            No section templates available.
          </div>
          <div v-else-if="filteredSectionTemplateNavigatorGroups.length === 0" class="section-template-nav-empty">
            No templates match the current search.
          </div>
          <div v-else class="section-template-nav-list">
            <div
              v-for="group in filteredSectionTemplateNavigatorGroups"
              :key="`section-nav-${group.sectionType}`"
              class="section-template-nav-group"
            >
              <button
                type="button"
                class="section-template-nav-heading"
                :class="{ active: activeSectionNavigatorType === group.sectionType }"
                @click="scrollToSectionTemplateGroup(group.sectionType)"
              >
                <span class="section-template-nav-heading-main">
                  <font-awesome-icon class="section-template-nav-icon" :icon="getTypeIcon(group.sectionType)" />
                  <span>{{ formatTypeName(group.sectionType) }}</span>
                </span>
                <span class="section-template-nav-count">{{ group.templates.length }}</span>
              </button>

              <div class="section-template-nav-items">
                <button
                  v-for="tpl in group.templates"
                  :key="`section-nav-template-${tpl.section_type}-${tpl.template_name}`"
                  type="button"
                  class="section-template-nav-item"
                  @click="openSectionTemplate(tpl.section_type, tpl.template_name)"
                >
                  <span class="section-template-nav-item-main">
                    <span class="section-template-nav-item-name">{{ tpl.template_name || "default" }}</span>
                    <font-awesome-icon
                      v-if="isSectionTemplateFavorite(tpl)"
                      class="section-template-nav-item-star"
                      :icon="faStar"
                      title="Favorite"
                    />
                  </span>
                </button>
              </div>
            </div>
          </div>
        </AdminStickySidebar>
      </div>

      <div v-else-if="activeTab === 'containers'" class="templates-card config-card">
        <div class="card-header">
          <h2>Container Templates</h2>
          <p class="card-hint">Container templates are compositions of customized sections.</p>
        </div>

        <form class="create-row create-row--inline" @submit.prevent="createContainerTemplate">
          <div class="create-row-fields create-row-fields--single">
            <input v-model="containerCreateName" class="admin-control create-control--name" type="text" placeholder="new template name" />
          </div>
          <div class="create-row-actions">
            <button
              class="btn-primary btn-sm"
              type="submit"
              :disabled="!canCreateContainerTemplate"
            >
              Create
            </button>
          </div>
        </form>

        <div class="template-list template-list--flat">
          <div v-for="tpl in containerTemplates" :key="tpl.template_name" class="template-row admin-list-item">
            <div class="template-row-main admin-list-item-main">
              <font-awesome-icon class="template-row-icon" :icon="faPuzzlePiece" />
              <input
                v-model="containerRenameDrafts[tpl.template_name]"
                class="admin-control admin-inline-input"
                type="text"
                placeholder="template name"
                :disabled="Boolean(containerRenaming[tpl.template_name])"
                @blur="submitContainerTemplateRename(tpl.template_name)"
                @keydown.enter.prevent="submitContainerTemplateRename(tpl.template_name)"
                @keydown.esc.prevent="resetContainerTemplateDraft(tpl.template_name)"
              />
            </div>
            <div class="template-row-actions admin-list-item-actions">
              <button class="btn-primary btn-sm" type="button" @click="openContainerTemplate(tpl.template_name)">Edit</button>
              <button class="btn-secondary btn-sm" type="button" @click="promptDuplicateContainerTemplate(tpl.template_name)">Duplicate</button>
              <button class="btn-danger btn-sm" type="button" @click="deleteContainerTemplate(tpl)">Delete</button>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="templates-card config-card">
        <div class="card-header">
          <h2>Page Templates</h2>
          <p class="card-hint">Page templates can be standalone or item-page templates used by generated content pages.</p>
        </div>

        <div class="template-list">
          <div
            v-for="group in groupedPageTemplates"
            :key="group.key"
            class="template-group"
          >
            <div class="template-group-head">
              <div class="template-group-title">
                <strong>
                  <font-awesome-icon class="template-row-icon" :icon="group.icon" />
                  {{ group.label }}
                </strong>
                <small>{{ group.templates.length }} template<span v-if="group.templates.length !== 1">s</span></small>
              </div>
              <form class="template-group-create" @submit.prevent="createPageTemplate(group.key)">
                <input
                  v-model="pageCreateDrafts[group.key]"
                  class="admin-control create-control--name"
                  type="text"
                  placeholder="new template name"
                  :aria-label="`New ${group.label} page template name`"
                />
                <button
                  class="btn-primary btn-sm"
                  type="submit"
                  :disabled="!canCreatePageTemplate(group.key)"
                >
                  Create
                </button>
              </form>
            </div>
            <div class="template-group-items admin-list">
              <div
                v-for="tpl in group.templates"
                :key="tpl.id || templatePath(tpl)"
                :class="[
                  'template-row',
                  'admin-list-item',
                  { 'template-row--muted': group.itemPage && !isActiveItemTemplate(tpl, group.itemPage) },
                ]"
              >
                <div class="template-row-main admin-list-item-main">
                  <label v-if="group.itemPage" class="template-active-radio">
                    <input
                      type="radio"
                      :name="`active-page-template-${group.key}`"
                      :checked="isActiveItemTemplate(tpl, group.itemPage)"
                      :disabled="Boolean(savingActiveItemTemplate[group.itemPage.key])"
                      @change="setActiveItemTemplateFromRow(group.itemPage, tpl)"
                    />
                    <span>{{ isActiveItemTemplate(tpl, group.itemPage) ? "Active" : "Set active" }}</span>
                  </label>
                  <font-awesome-icon class="template-row-icon" :icon="faFileLines" />
                  <div class="template-name-edit">
                    <div class="template-name-inline">
                      <span
                        v-if="pageTemplatePrefix(tpl) && !isItemPageTemplateEntry(tpl)"
                        class="template-path-prefix"
                      >
                        {{ pageTemplatePrefix(tpl) }}/
                      </span>
                      <input
                        v-model="pageRenameDrafts[templatePath(tpl)]"
                        class="admin-control admin-inline-input"
                        type="text"
                        placeholder="page template name"
                        :disabled="Boolean(pageRenaming[templatePath(tpl)])"
                        @blur="submitPageTemplateRename(tpl)"
                        @keydown.enter.prevent="submitPageTemplateRename(tpl)"
                        @keydown.esc.prevent="resetPageTemplateDraft(tpl)"
                      />
                    </div>
                    <small v-if="isItemPageTemplateEntry(tpl)">
                      ROUTE: {{ pageTemplateEffectiveItemRoute(tpl) || "not configured" }}
                    </small>
                  </div>
                </div>
                <div class="template-row-actions admin-list-item-actions">
                  <button class="btn-primary btn-sm" type="button" @click="openPageTemplate(templatePath(tpl))">Edit</button>
                  <button class="btn-secondary btn-sm" type="button" @click="promptDuplicatePageTemplate(tpl)">Duplicate</button>
                  <button class="btn-danger btn-sm" type="button" @click="deletePageTemplate(tpl)">Delete</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  faAlignLeft,
  faBullhorn,
  faCalendarDays,
  faCode,
  faCircleQuestion,
  faFileLines,
  faShareNodes,
  faImage,
  faImages,
  faNewspaper,
  faPuzzlePiece,
  faTableCellsLarge,
  faStar,
  faVideo,
} from "@fortawesome/free-solid-svg-icons";

import AdminPageTabs from "../../components/admin/AdminPageTabs.vue";
import AdminStickySidebar from "../../components/admin/AdminStickySidebar.vue";
import AutosaveToast from "../../components/admin/AutosaveToast.vue";
import IntegrationFieldMappingGroups from "../../components/admin/mapping/IntegrationFieldMappingGroups.vue";
import BasePage from "../BasePage.vue";
import * as api from "../../services/api.js";
import { mapDesignToBackendFull } from "../../designDefs.js";
import { buildIntegrationMappingKeys } from "../../utils/integrationMappingKeys.js";
import { convertKeysToCamel } from "../../utils/caseConversion.js";
import {
  effectiveSectionOutputFieldOptions,
  normalizeSectionOutputMapping,
} from "../../utils/sectionOutputMapping.js";
import { useStore } from "../../store/store.js";

const route = useRoute();
const router = useRouter();
const { state } = useStore();

const tabs = [
  { id: "sections", label: "Sections", to: "/admin/templates/sections" },
  { id: "containers", label: "Containers", to: "/admin/templates/containers" },
  { id: "pages", label: "Pages", to: "/admin/templates/pages" },
];

const ITEM_PAGE_TEMPLATE_TYPES = [
  { key: "blog:item", prefix: "blog_item", label: "Blog", sourceType: "blog", sourceKind: "item" },
  { key: "program:stage", prefix: "program_stage", label: "Stage", sourceType: "program", sourceKind: "stage" },
  { key: "program:gig", prefix: "program_gig", label: "Gigs", sourceType: "program", sourceKind: "gig" },
];
const PAGE_TEMPLATE_GROUPS = [
  { key: "static", label: "Static", createType: "static", itemPageKey: "", icon: faFileLines },
  { key: "gig", label: "Gig", createType: "program:gig", itemPageKey: "program:gig", icon: faCalendarDays },
  { key: "stage", label: "Stage", createType: "program:stage", itemPageKey: "program:stage", icon: faCalendarDays },
  { key: "blog", label: "Blog", createType: "blog:item", itemPageKey: "blog:item", icon: faNewspaper },
];
const PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS = "shared_items";
const PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION = "integration";
const PAGE_MAPPING_SOURCE_PROVIDERS = new Set([
  PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS,
  PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION,
]);
const BLOG_SHARED_SOURCE_FIELD_OPTIONS = [
  { path: "item.id", kind: "text" },
  { path: "item.date", kind: "datetime" },
  { path: "item.title.de", kind: "text" },
  { path: "item.title.en", kind: "text" },
  { path: "item.text.de", kind: "text" },
  { path: "item.text.en", kind: "text" },
  { path: "item.tag.de", kind: "text" },
  { path: "item.tag.en", kind: "text" },
  { path: "item.image_url", kind: "image" },
  { path: "item.image_zoom", kind: "number" },
  { path: "item.image_focal_x", kind: "number" },
  { path: "item.image_focal_y", kind: "number" },
  { path: "item.image_rotation", kind: "number" },
  { path: "item.page_slug", kind: "text" },
];

const sectionTypes = ref([]);
const sectionTemplates = ref([]);
const containerTemplates = ref([]);
const pageTemplates = ref([]);
const itemPageSourceRoutes = ref([]);
const globalItemPageConfig = ref({});
const itemPageParentCandidates = ref([]);
const sectionTemplateSearchQuery = ref("");
const activeSectionNavigatorType = ref("");

const sectionCreateDrafts = reactive({});
const sectionTemplateFavoriteSaving = reactive({});
const containerCreateName = ref("");
const pageCreateDrafts = reactive(
  Object.fromEntries(PAGE_TEMPLATE_GROUPS.map((group) => [group.key, ""]))
);

const mappingDraft = reactive({
  sourceRouteRef: "",
  sectionTemplateRef: "blog/default",
  sourceProvider: PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION,
  primaryIntegrationId: "",
  listMappingsByCollectionPath: {},
  hiddenListTargetPathsByCollectionPath: {},
});
const pageRoutingDraft = reactive({
  parentCandidateKey: "",
  parentRoute: "",
  sourceSectionId: "",
  itemPageSubroute: "",
});
const mappingAvailableIntegrations = ref([]);
const mappingIntegrationsContext = ref({
  template_key: "",
  integration_visibility: "template_only",
  integrations_enabled: true,
  expected_return_type: "auto",
});
const mappingIntegrationSchema = ref(null);
const mappingIntegrationSchemaLoading = ref(false);
const mappingIntegrationSchemaError = ref("");
const mappingLoadingIntegrations = ref(false);
const mappingIntegrationPreview = ref(null);
const mappingPreviewItemIndex = ref(null);
const mappingPreviewItemKey = ref("");
const mappingPreviewItemIndexHydrating = ref(false);
const mappingItemPreviewOptions = ref([]);
const mappingPreviewItemOptionsRequestId = ref(0);
const mappingPreviewEnabled = ref(false);
const previewingMappings = ref(false);
const mappingPreviewDoc = ref(null);
const mappingPreviewWarnings = ref([]);
const loadingPageTemplateSettings = ref(false);
const savingMappings = ref(false);
const mappingAutosaveStatus = ref("idle");
const mappingAutosaveError = ref("");
const mappingAutosaveReady = ref(false);
const mappingLastSavedSignature = ref("");
const mappingAutosaveTimerId = ref(null);
const mappingAutosaveQueued = ref(false);
let mappingAutosaveStatusTimer = null;
const mappingPreviewRefreshTimerId = ref(null);
const mappingPreviewAdminSnapshot = ref(null);
const mappingDefaultHiddenTargetClears = ref(new Set());
const showDefaultHiddenVisibilityTargets = ref(false);
const currentPageTemplateDoc = ref(null);
const sectionRenameDrafts = reactive({});
const sectionRenaming = reactive({});
const containerRenameDrafts = reactive({});
const containerRenaming = reactive({});
const pageRenameDrafts = reactive({});
const pageRenaming = reactive({});
const regeneratingPageTemplateItems = ref(false);
const pageTemplateRegenerateStatus = ref({ type: "", message: "" });
const savingActiveItemTemplate = reactive({});
const savingTemplateRouting = ref(false);
const templateRoutingStatus = ref({ type: "", message: "" });

const mappingAutosaveToastMessage = computed(() => {
  if (mappingAutosaveStatus.value === "saving") return "Saving template mappings...";
  if (mappingAutosaveStatus.value === "saved") return "Template mappings saved.";
  if (mappingAutosaveStatus.value === "error") {
    return `Template mapping autosave failed: ${mappingAutosaveError.value || "unknown error"}`;
  }
  return "";
});

const mappingIntegrationsEnabled = computed(
  () => mappingIntegrationsContext.value?.integrations_enabled !== false
);

const mappingIntegrationById = computed(() => {
  const index = new Map();
  (Array.isArray(mappingAvailableIntegrations.value) ? mappingAvailableIntegrations.value : []).forEach((integration) => {
    const id = String(integration?.id || "").trim();
    if (id) index.set(id, integration);
  });
  return index;
});

const activePageMappingIntegrationLabel = computed(() => {
  const integrationId = String(mappingDraft.primaryIntegrationId || "").trim();
  if (!integrationId) return "no integration";
  const integration = mappingIntegrationById.value.get(integrationId);
  const name = String(integration?.name || "").trim();
  return `${name || integrationId}`;
});

const activePageMappingIntegrationPrimaryKeyPath = computed(() => {
  const integrationId = String(mappingDraft.primaryIntegrationId || "").trim();
  if (!integrationId) return "";
  const integration = mappingIntegrationById.value.get(integrationId);
  return String(integration?.output_primary_key_path || "").trim();
});

const activePageMappingIntegrationPageSlugPath = computed(() =>
  String(mappingIntegrationSchema.value?.page_slug_path || "").trim()
);

const itemPageSchemaSlugPathLabel = computed(() => {
  if (mappingUsesSharedItems.value) return sharedBlogSlugSourcePath.value;
  if (mappingIntegrationSchemaLoading.value) return "Loading schema...";
  if (mappingIntegrationSchemaError.value) return "Schema unavailable";
  const slugPath = activePageMappingIntegrationPageSlugPath.value;
  return slugPath ? `integration.${slugPath}` : "Not configured";
});

const itemPageSlugSourceWarning = computed(() => {
  if (!activePageIsItemPageTemplate.value) return "";
  if (!mappingUsesIntegration.value) return "";
  if (!String(mappingDraft.primaryIntegrationId || "").trim()) {
    return "Select an integration source, then set its Page Slug field in the integration schema.";
  }
  if (mappingIntegrationSchemaLoading.value) return "";
  if (mappingIntegrationSchemaError.value) {
    return mappingIntegrationSchemaError.value;
  }
  if (!activePageMappingIntegrationPageSlugPath.value) {
    return "No Page Slug field is selected for this integration. Item-page slugs are configured in the integration schema.";
  }
  return "";
});

function fixedGigMappingSourcePath() {
  if (mappingSourceProvider.value !== PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION) return "";
  const primaryKeyPath = activePageMappingIntegrationPrimaryKeyPath.value;
  return primaryKeyPath ? `integration.${primaryKeyPath}` : "";
}

function fixedGigMappingNeedsPrimaryKeyFallback(sourcePath) {
  const raw = String(sourcePath || "").trim();
  return !raw || raw === "id" || raw === "item.id" || raw === "integration.id";
}

function isGigTitleIntegrationSourcePath(sourcePath) {
  const normalized = normalizeOutputMappingSourcePath(
    sourcePath,
    PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION,
  );
  const integrationPath = normalized.startsWith("integration.")
    ? normalized.slice(12).trim()
    : normalized;
  if (!integrationPath) return false;
  const tokens = integrationPath
    .replace(/\[(\d+)\]/g, ".$1")
    .split(".")
    .map((token) => token.trim().toLowerCase().replace(/-/g, "_"))
    .filter(Boolean);
  if (!tokens.length) return false;
  const titleTokens = new Set(["title", "name", "artist_name", "gig_title"]);
  const last = tokens[tokens.length - 1];
  const previous = tokens.length > 1 ? tokens[tokens.length - 2] : "";
  return titleTokens.has(last) || (["de", "en"].includes(last) && titleTokens.has(previous));
}

function isSupportedFixedGigSourcePath(sourcePath, primaryKeyPath = activePageMappingIntegrationPrimaryKeyPath.value) {
  const normalized = normalizeOutputMappingSourcePath(
    sourcePath,
    PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION,
  );
  const normalizedPrimary = String(primaryKeyPath || "").trim();
  if (normalizedPrimary && normalized === `integration.${normalizedPrimary}`) return true;
  return isGigTitleIntegrationSourcePath(normalized);
}

const mappingPreviewItemOptions = computed(() => {
  const itemOptions = Array.isArray(mappingItemPreviewOptions.value)
    ? mappingItemPreviewOptions.value
    : [];
  if (activePageIsItemPageTemplate.value) {
    return itemOptions
      .map((option, index) => {
        const itemKey = normalizeMappingPreviewItemKey(option?.item_key || option?.value);
        if (!itemKey) return null;
        const optionIndex = normalizeMappingPreviewItemIndex(option?.index);
        return {
          ...option,
          index: optionIndex != null ? optionIndex : index,
          item_key: itemKey,
          value: itemKey,
          label: stripPreviewRoutePrefixesFromLabel(
            option?.label || itemKey,
            mappingItemPreviewRoutePrefixes.value,
          ) || itemKey,
        };
      })
      .filter(Boolean);
  }
  const options = Array.isArray(mappingIntegrationPreview.value?.preview_options)
    ? mappingIntegrationPreview.value.preview_options
    : [];
  return options
    .map((option, index) => {
      const optionIndex = Number(option?.index);
      return {
        index: Number.isFinite(optionIndex) ? optionIndex : index,
        value: Number.isFinite(optionIndex) ? optionIndex : index,
        label: String(option?.label || `Item #${index + 1}`).trim() || `Item #${index + 1}`,
      };
    })
    .filter((option) => Number.isFinite(option.index));
});

const mappingPreviewItemSelection = computed({
  get() {
    if (activePageIsItemPageTemplate.value) {
      return normalizeMappingPreviewItemKey(mappingPreviewItemKey.value);
    }
    const index = normalizeMappingPreviewItemIndex(mappingPreviewItemIndex.value);
    return index == null ? "" : index;
  },
  set(value) {
    if (activePageIsItemPageTemplate.value) {
      mappingPreviewItemKey.value = normalizeMappingPreviewItemKey(value);
      return;
    }
    mappingPreviewItemIndex.value = normalizeMappingPreviewItemIndex(value);
  },
});

const canCreateContainerTemplate = computed(() =>
  String(containerCreateName.value || "").trim().length > 0
);

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

const TYPE_NAMES = {
  text: { de: "Text", en: "" },
  text_image: { de: "Text mit Bild", en: "Text Image" },
  video: { de: "Video", en: "" },
  faq: { de: "FAQ", en: "" },
  links: { de: "Links", en: "" },
  ticker: { de: "Ticker", en: "" },
  gallery: { de: "Galerie", en: "Gallery" },
  blog: { de: "Blog", en: "" },
  markdown: { de: "Markdown", en: "" },
  html: { de: "HTML", en: "" },
  tiles: { de: "Kacheln", en: "Tiles" },
  program: { de: "Programm", en: "Program" },
};

const DEFAULT_SECTION_TEMPLATE_TYPES = [
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
const HIDDEN_SECTION_TEMPLATE_TYPES = new Set();
const LINKS_SECTION_TYPE = "links";
const LINKS_SOCIAL_ITEM_INDEX_PATH_RE = /^type_data\.items\[(\d+)\](\..+)?$/;
const LINKS_SOCIAL_ITEM_KEY_PATH_RE = /^type_data\.items\.([^.]+)(\..+)?$/;
const INHERITED_SECTION_MAPPING_SOURCES = [
  {
    key: "section_integration_mapping",
    label: "Section Integration Import",
    paths: [
      ["section_integration_mapping"],
      ["sectionIntegrationMapping"],
    ],
  },
];

function normalizePathSegment(value, fallback = "") {
  const text = String(value || "").trim().toLowerCase();
  const slug = text.replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "");
  return slug || fallback;
}

function normalizeSectionType(value, fallback = "text") {
  const text = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/-/g, "_");
  const normalized = text.replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
  return normalized || fallback;
}

function normalizeTemplateName(value, fallback = "default") {
  const text = String(value || "").trim().toLowerCase();
  const slug = text.replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "");
  return slug || fallback;
}

function normalizeVisibleSectionTemplateTypes(types) {
  const next = [];
  const seen = new Set();
  for (const rawType of Array.isArray(types) ? types : []) {
    const normalized = normalizeSectionType(rawType, "");
    if (!normalized || HIDDEN_SECTION_TEMPLATE_TYPES.has(normalized) || seen.has(normalized)) continue;
    seen.add(normalized);
    next.push(normalized);
  }
  return next;
}

function getTypeIcon(type) {
  return TYPE_ICONS[String(type || "").trim()] || faFileLines;
}

function formatTypeName(type) {
  const normalized = String(type || "").trim();
  const names = TYPE_NAMES[normalized];
  if (names) return names.de || names.en || normalized;
  return normalized
    .replace(/_/g, " ")
    .replace(/(^|\s)\S/g, (value) => value.toUpperCase());
}

function normalizeParentRoute(value) {
  const raw = String(value || "").trim();
  if (!raw || raw === "/") return null;
  const parts = raw
    .split("/")
    .map((part) => normalizePathSegment(part, ""))
    .filter(Boolean);
  return parts.length ? `/${parts.join("/")}` : null;
}

function normalizeItemPageSubroute(value) {
  const raw = String(value || "").trim();
  if (!raw || raw === "/") return "";
  const parts = raw
    .split("/")
    .map((part) => normalizePathSegment(part, ""))
    .filter(Boolean);
  return parts.length ? `/${parts.join("/")}` : "";
}

function composeEffectiveItemPageRoute(parentRoute, subroute = "") {
  const parent = normalizeParentRoute(parentRoute);
  if (!parent) return "";
  const child = normalizeItemPageSubroute(subroute);
  if (!child) return parent;
  return normalizeParentRoute(`${parent}/${child}`) || parent;
}

function composePageTemplatePath(templateName, parentRoute = null) {
  const normalizedName = normalizeTemplateName(templateName);
  const normalizedParent = normalizeParentRoute(parentRoute);
  if (!normalizedParent) return normalizedName;
  return `${normalizedParent.replace(/^\/+/, "")}/${normalizedName}`;
}

function parsePageTemplatePath(path) {
  const segments = String(path || "")
    .split("/")
    .map((segment) => String(segment || "").trim())
    .filter(Boolean);
  if (!segments.length) {
    return { templateName: "", parentRoute: null, path: "" };
  }
  const templateName = normalizeTemplateName(segments[segments.length - 1]);
  const parentSegments = segments
    .slice(0, -1)
    .map((segment) => normalizePathSegment(segment, ""))
    .filter(Boolean);
  const parentRoute = parentSegments.length ? `/${parentSegments.join("/")}` : null;
  return {
    templateName,
    parentRoute,
    path: composePageTemplatePath(templateName, parentRoute),
  };
}

function pageTemplatePrefix(template) {
  const info = parsePageTemplatePath(templatePath(template));
  return info.parentRoute ? info.parentRoute.replace(/^\/+/, "") : "";
}

function inferItemPageTemplateSourceContext(template) {
  if (!isItemPageTemplateEntry(template)) return null;

  let sourceType = String(template?.source_type || "").trim().toLowerCase();
  if (sourceType !== "blog" && sourceType !== "program") {
    const sectionTemplateRef = String(template?.section_template_ref || "").trim().toLowerCase();
    if (sectionTemplateRef.startsWith("blog/")) sourceType = "blog";
    else if (sectionTemplateRef.startsWith("program/")) sourceType = "program";
  }
  if (sourceType !== "blog" && sourceType !== "program") return null;

  let sourceKind = String(template?.source_kind || "").trim().toLowerCase();
  if (sourceType === "blog") {
    sourceKind = "item";
  } else if (sourceKind !== "stage" && sourceKind !== "gig") {
    sourceKind = "gig";
  }

  return { sourceType, sourceKind };
}

function pageTemplateParentRoute(template) {
  const direct = normalizeParentRoute(template?.parent_route || "");
  if (direct) return direct;
  return parsePageTemplatePath(templatePath(template)).parentRoute || "";
}

function pageTemplateEffectiveItemRoute(template) {
  return composeEffectiveItemPageRoute(
    pageTemplateParentRoute(template),
    template?.item_page_subroute || "",
  );
}

function isItemPageTemplateEntry(template) {
  const templateKind = String(template?.template_kind || "").trim().toLowerCase();
  if (templateKind === "item_page") return true;
  return Boolean(String(template?.source_type || "").trim());
}

function formatItemPageTemplateSourceLabel(template) {
  const sourceContext = inferItemPageTemplateSourceContext(template);
  const sourceType = sourceContext?.sourceType || "blog";
  const sourceKind = sourceContext?.sourceKind || "item";
  return `${formatSourceKindLabel(sourceKind)} (${sourceType})`;
}

function formatSourceKindLabel(sourceKind) {
  const normalized = String(sourceKind || "").trim().toLowerCase();
  if (normalized === "gig") return "gigs";
  if (normalized === "stage") return "stage";
  return "blog";
}

function sectionTemplateKey(sectionType, templateName = "default") {
  return `${normalizeSectionType(sectionType, "text")}:${normalizeTemplateName(templateName, "default")}`;
}

function sectionTemplateFavoriteSavingKey(template) {
  return sectionTemplateKey(template?.section_type, template?.template_name || "default");
}

function isSectionTemplateFavorite(template) {
  return Boolean(template?.favorite);
}

function isSectionTemplateFavoriteSaving(template) {
  const key = sectionTemplateFavoriteSavingKey(template);
  return Boolean(sectionTemplateFavoriteSaving[key]);
}

function formatSectionTemplateLinkLabel(template) {
  const sectionType = normalizeSectionType(template?.section_type, "text");
  const templateName = normalizeTemplateName(template?.template_name || "default", "default");
  return `${formatTypeName(sectionType)} / ${templateName}`;
}

function sectionTemplateGroupDomId(sectionType) {
  return `section-template-group-${normalizeSectionType(sectionType, "text").replace(/_/g, "-")}`;
}

function normalizeSectionTemplateRef(value, fallback = "blog/default") {
  const raw = String(value || "").trim().replace(/^\/+|\/+$/g, "");
  if (!raw) return fallback;
  const parts = raw.split("/").map((part) => String(part || "").trim()).filter(Boolean);
  if (!parts.length) return fallback;
  const sectionType = normalizeSectionType(parts[0], "");
  if (sectionType !== "blog" && sectionType !== "tiles" && sectionType !== "program") return fallback;
  const templateName = normalizeTemplateName(parts[1] || "default", "default");
  return `${sectionType}/${templateName}`;
}

function resetDraftMap(target, values) {
  for (const key of Object.keys(target)) {
    delete target[key];
  }
  for (const [key, value] of Object.entries(values || {})) {
    target[key] = value;
  }
}

function ensureSectionCreateDraft(sectionType) {
  const key = normalizeSectionType(sectionType, "");
  if (key && sectionCreateDrafts[key] == null) {
    sectionCreateDrafts[key] = "";
  }
}

const activeTab = computed(() => {
  const matched = String(route.path || "").split("/")[3] || "sections";
  if (["sections", "containers", "pages"].includes(matched)) return matched;
  return "sections";
});

const activeTabLabel = computed(() => {
  const tab = tabs.find((item) => item.id === activeTab.value);
  return tab?.label || "Templates";
});

function setActiveTab(tabId) {
  const target = tabs.find((entry) => entry.id === tabId);
  router.push(target?.to || "/admin/templates/sections");
}

const sectionTypeParam = computed(() => normalizeSectionType(route.params.sectionType, ""));
const sectionTemplateNameParam = computed(() => normalizeTemplateName(route.params.templateName || "default", "default"));
const containerTemplateNameParam = computed(() => normalizeTemplateName(route.params.templateName || "", ""));

const rawPageSegments = computed(() => {
  const raw = route.params.pathMatch;
  if (Array.isArray(raw)) return raw.filter(Boolean).map((entry) => String(entry));
  if (typeof raw === "string" && raw.trim()) return raw.split("/").filter(Boolean);
  return [];
});

const pageTemplateInfo = computed(() => {
  const segments = rawPageSegments.value.map((segment) => String(segment || "").trim()).filter(Boolean);
  if (segments.length === 0) {
    return {
      isList: true,
      templateName: "",
      parentRoute: null,
      path: "",
      templateKey: null,
    };
  }

  const templateName = normalizeTemplateName(segments[segments.length - 1]);
  const parentSegments = segments
    .slice(0, -1)
    .map((segment) => normalizePathSegment(segment, ""))
    .filter(Boolean);
  const parentRoute = parentSegments.length ? `/${parentSegments.join("/")}` : null;
  const path = composePageTemplatePath(templateName, parentRoute);
  const templateKey = parentRoute ? `page:${parentRoute}:${templateName}` : `page:${templateName}`;

  return {
    isList: false,
    templateName,
    parentRoute,
    path,
    templateKey,
  };
});

const builderContext = computed(() => {
  if (activeTab.value === "sections" && sectionTypeParam.value) {
    const templateName = sectionTemplateNameParam.value || "default";
    const path = `${sectionTypeParam.value}/${templateName}`;
    return {
      kind: "section",
      path,
      template_key: `section:${sectionTypeParam.value}:${templateName}`,
    };
  }

  if (activeTab.value === "containers" && containerTemplateNameParam.value) {
    const templateName = containerTemplateNameParam.value;
    return {
      kind: "container",
      path: templateName,
      template_key: `container:${templateName}`,
    };
  }

  if (activeTab.value === "pages" && !pageTemplateInfo.value.isList) {
    return {
      kind: "page",
      path: pageTemplateInfo.value.path,
      template_key: pageTemplateInfo.value.templateKey,
    };
  }

  return null;
});

const builderSlug = computed(() => {
  if (!builderContext.value) return "";
  if (builderContext.value.kind === "section") return `__template_section__/${builderContext.value.path}`;
  if (builderContext.value.kind === "container") return `__template_container__/${builderContext.value.path}`;
  return `__template_page__/${builderContext.value.path}`;
});

const builderKey = computed(() => (builderContext.value ? `${builderContext.value.kind}:${builderContext.value.path}` : "list"));

const activePageTemplateListEntry = computed(() => {
  if (builderContext.value?.kind !== "page") return null;
  const activePath = String(pageTemplateInfo.value.path || "").trim();
  if (!activePath) return null;
  return (
    (Array.isArray(pageTemplates.value) ? pageTemplates.value : []).find(
      (entry) => String(templatePath(entry) || "").trim() === activePath
    ) || null
  );
});

const activePageIsItemPageTemplate = computed(() =>
  isItemPageTemplateEntry(currentPageTemplateDoc.value || activePageTemplateListEntry.value || {})
);

const showPageMappingEditor = computed(() => {
  return builderContext.value?.kind === "page" && !pageTemplateInfo.value.isList;
});

const showRegenerateAllItemPagesButton = computed(() => {
  return builderContext.value?.kind === "page"
    && !pageTemplateInfo.value.isList
    && activePageIsItemPageTemplate.value;
});

const activePageItemTemplateType = computed(() => {
  const template = currentPageTemplateDoc.value || activePageTemplateListEntry.value || {};
  const sourceContext = inferItemPageTemplateSourceContext(template);
  if (!sourceContext) return null;
  return ITEM_PAGE_TEMPLATE_TYPES.find((row) =>
    row.sourceType === sourceContext.sourceType
    && row.sourceKind === sourceContext.sourceKind
  ) || null;
});

const activePageTemplatePath = computed(() => {
  const explicitPath = String(pageTemplateInfo.value.path || "").trim();
  if (explicitPath) return explicitPath;
  const template = currentPageTemplateDoc.value || activePageTemplateListEntry.value || {};
  return String(templatePath(template) || "").trim();
});

const activeItemPageTemplatePathForCurrentType = computed(() => {
  const row = activePageItemTemplateType.value;
  return row ? activeItemTemplatePath(row) : "";
});

const activePageTemplateIsActiveItemPageTemplate = computed(() => {
  const path = activePageTemplatePath.value;
  return Boolean(path && activeItemPageTemplatePathForCurrentType.value === path);
});

const canRegenerateAllItemPagesForTemplate = computed(() =>
  showRegenerateAllItemPagesButton.value
  && activePageTemplateIsActiveItemPageTemplate.value
);

const generatedItemPageCountForTemplate = computed(() => {
  const candidates = [
    currentPageTemplateDoc.value,
    activePageTemplateListEntry.value,
  ];
  for (const candidate of candidates) {
    const count = Number(candidate?.generated_item_page_count);
    if (Number.isFinite(count) && count >= 0) return Math.trunc(count);
  }
  return 0;
});

const generatedItemPagesExistForTemplate = computed(() =>
  generatedItemPageCountForTemplate.value > 0
);

const regenerateAllItemPagesButtonLabel = computed(() => {
  if (regeneratingPageTemplateItems.value) {
    return generatedItemPagesExistForTemplate.value ? "Regenerating..." : "Generating...";
  }
  return generatedItemPagesExistForTemplate.value ? "Regenerate All" : "Generate Pages";
});

const regenerateAllItemPagesHint = computed(() => {
  const row = activePageItemTemplateType.value;
  if (!row) return "Only active item-page templates can regenerate pages.";
  if (activePageTemplateIsActiveItemPageTemplate.value) {
    if (generatedItemPagesExistForTemplate.value) {
      return `Regenerates existing pages for the active ${row.label} item-page template.`;
    }
    return `Generates pages for the active ${row.label} item-page template.`;
  }
  return `Set this ${row.label} item-page template active before regenerating pages.`;
});

function normalizeSourceRouteRef(value) {
  return String(value || "").trim();
}

function normalizeItemPageDefaultStatus(value, fallback = "hidden") {
  const normalizedFallback = String(fallback || "").trim().toLowerCase() === "published"
    ? "published"
    : "hidden";
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "published") return "published";
  if (normalized === "hidden" || normalized === "draft") return "hidden";
  return normalizedFallback;
}

function normalizeItemPageSourceType(value, fallback = "blog") {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "program") return "program";
  if (normalized === "blog") return "blog";
  return fallback === "program" ? "program" : "blog";
}

function normalizeItemPageSourceKind(sourceType, value, fallback = "item") {
  const normalizedSource = normalizeItemPageSourceType(sourceType, "blog");
  const normalizedKind = String(value || "").trim().toLowerCase();
  if (normalizedSource === "program") {
    if (normalizedKind === "stage") return "stage";
    if (normalizedKind === "gig") return "gig";
    return fallback === "stage" ? "stage" : "gig";
  }
  return "item";
}

function itemPageConfigKeyPrefix(sourceType, sourceKind) {
  const normalizedSource = normalizeItemPageSourceType(sourceType, "blog");
  const normalizedKind = normalizeItemPageSourceKind(normalizedSource, sourceKind, "item");
  if (normalizedSource === "program") {
    return normalizedKind === "stage" ? "program_stage" : "program_gig";
  }
  return "blog_item";
}

function itemPageTypeRow(sourceType, sourceKind) {
  const prefix = itemPageConfigKeyPrefix(sourceType, sourceKind);
  return ITEM_PAGE_TEMPLATE_TYPES.find((row) => row.prefix === prefix) || ITEM_PAGE_TEMPLATE_TYPES[0];
}

function parsePageCreateTemplateType(value) {
  const normalized = String(value || "static").trim().toLowerCase();
  if (normalized === "program:stage") return { isItemPage: true, sourceType: "program", sourceKind: "stage" };
  if (normalized === "program:gig") return { isItemPage: true, sourceType: "program", sourceKind: "gig" };
  if (normalized === "blog:item") return { isItemPage: true, sourceType: "blog", sourceKind: "item" };
  return { isItemPage: false, sourceType: "blog", sourceKind: "item" };
}

function pageTemplateGroupDefinition(groupKey) {
  return PAGE_TEMPLATE_GROUPS.find((group) => group.key === groupKey)
    || PAGE_TEMPLATE_GROUPS.find((group) => group.key === "static")
    || PAGE_TEMPLATE_GROUPS[0];
}

function itemPageRowForGroup(group) {
  const itemPageKey = String(group?.itemPageKey || "").trim();
  if (!itemPageKey) return null;
  return ITEM_PAGE_TEMPLATE_TYPES.find((row) => row.key === itemPageKey) || null;
}

function templateMatchesItemPageType(template, row) {
  const sourceContext = inferItemPageTemplateSourceContext(template);
  return sourceContext?.sourceType === row.sourceType
    && sourceContext?.sourceKind === row.sourceKind;
}

function activeItemTemplatePath(row) {
  return String(globalItemPageConfig.value?.[`${row.prefix}_template_path`] || "").trim();
}

function isActiveItemTemplate(template, row) {
  const path = templatePath(template);
  return Boolean(path && activeItemTemplatePath(row) === path);
}

async function setActiveItemTemplateFromRow(row, template) {
  const value = templatePath(template);
  if (!row || !value || activeItemTemplatePath(row) === value) return;
  savingActiveItemTemplate[row.key] = true;
  try {
    globalItemPageConfig.value = await api.setGlobalItemPageConfig({
      [`${row.prefix}_template_path`]: value,
    });
  } catch (err) {
    console.error("Failed to save active item template:", err);
    window.alert(err?.message || "Failed to save active item template.");
  } finally {
    delete savingActiveItemTemplate[row.key];
  }
}

function parentCandidateKey(parentRoute) {
  const route = normalizeParentRoute(parentRoute) || "";
  return route;
}

function formatParentCandidateLabel(parentRoute, pageTitle = "") {
  const route = normalizeParentRoute(parentRoute) || "";
  const title = String(pageTitle || "").trim() || route;
  return route ? `${route} (${title})` : title;
}

const itemPageParentCandidateOptions = computed(() => {
  const options = (Array.isArray(itemPageParentCandidates.value) ? itemPageParentCandidates.value : [])
    .map((candidate) => {
      const parentRoute = normalizeParentRoute(candidate?.parent_route) || "";
      const value = parentCandidateKey(parentRoute);
      if (!value) return null;
      const sourceSectionId = String(candidate?.section_id || "").trim();
      return {
        value,
        parentRoute,
        sourceSectionId,
        hasRelatedSection: Boolean(candidate?.has_related_section || sourceSectionId),
        isFallback: false,
        label: formatParentCandidateLabel(parentRoute, candidate?.page_title),
      };
    })
    .filter(Boolean);
  const currentKey = parentCandidateKey(pageRoutingDraft.parentRoute);
  if (currentKey && !options.some((option) => option.value === currentKey)) {
    options.unshift({
      value: currentKey,
      parentRoute: pageRoutingDraft.parentRoute,
      sourceSectionId: pageRoutingDraft.sourceSectionId,
      hasRelatedSection: Boolean(pageRoutingDraft.sourceSectionId),
      isFallback: true,
      label: formatParentCandidateLabel(pageRoutingDraft.parentRoute, "current selection"),
    });
  }
  return options.sort((a, b) => String(a.label || "").localeCompare(String(b.label || ""), undefined, { sensitivity: "base" }));
});

const groupedItemPageParentCandidateOptions = computed(() => {
  const groups = [
    {
      key: "with-related-section",
      label: "Pages with related section",
      options: itemPageParentCandidateOptions.value.filter((option) => option.hasRelatedSection),
    },
    {
      key: "without-related-section",
      label: "Pages without related section",
      options: itemPageParentCandidateOptions.value.filter((option) => !option.hasRelatedSection),
    },
  ];
  return groups.filter((group) => group.options.length > 0);
});

function handleParentCandidateChange() {
  const option = itemPageParentCandidateOptions.value.find(
    (entry) => entry.value === pageRoutingDraft.parentCandidateKey
  );
  if (!option) {
    pageRoutingDraft.parentRoute = "";
    pageRoutingDraft.sourceSectionId = "";
    return;
  }
  pageRoutingDraft.parentRoute = option.parentRoute;
  pageRoutingDraft.sourceSectionId = option.sourceSectionId;
  if (showPageMappingEditor.value) {
    void loadMappingIntegrations();
  }
}

const pageRoutingEffectivePreview = computed(() => {
  const route = composeEffectiveItemPageRoute(
    pageRoutingDraft.parentRoute,
    pageRoutingDraft.itemPageSubroute,
  );
  return route ? `${route}/<slug>` : "Not configured";
});

function hydratePageRoutingDraft(template) {
  pageRoutingDraft.parentRoute = normalizeParentRoute(template?.parent_route || "") || "";
  pageRoutingDraft.sourceSectionId = String(template?.item_page_source_section_id || "").trim();
  pageRoutingDraft.parentCandidateKey = parentCandidateKey(pageRoutingDraft.parentRoute);
  pageRoutingDraft.itemPageSubroute = normalizeItemPageSubroute(template?.item_page_subroute || "");
}

async function loadItemPageParentCandidatesForTemplate(template) {
  if (!isItemPageTemplateEntry(template)) {
    itemPageParentCandidates.value = [];
    return;
  }
  const sourceContext = inferItemPageTemplateSourceContext(template);
  if (!sourceContext) {
    itemPageParentCandidates.value = [];
    return;
  }
  try {
    const response = await api.listItemPageParentCandidates({
      sourceType: sourceContext.sourceType,
      sourceKind: sourceContext.sourceKind,
    });
    itemPageParentCandidates.value = Array.isArray(response?.candidates) ? response.candidates : [];
  } catch (err) {
    console.error("Failed to load item-page parent candidates:", err);
    itemPageParentCandidates.value = [];
  }
}

async function savePageTemplateRouting() {
  if (!activePageIsItemPageTemplate.value || savingTemplateRouting.value) return;
  const path = String(pageTemplateInfo.value.path || "").trim();
  if (!path) return;
  savingTemplateRouting.value = true;
  templateRoutingStatus.value = { type: "", message: "" };
  try {
    const result = await api.updatePageTemplateRouting(path, {
      parent_route: pageRoutingDraft.parentRoute || "",
      item_page_source_section_id: pageRoutingDraft.sourceSectionId || "",
      item_page_subroute: pageRoutingDraft.itemPageSubroute || "",
    });
    const nextTemplate = result?.template || null;
    if (nextTemplate) {
      currentPageTemplateDoc.value = nextTemplate;
      hydratePageRoutingDraft(nextTemplate);
    }
    await Promise.all([loadPageTemplates(), loadGlobalItemPageConfig()]);
    templateRoutingStatus.value = {
      type: "success",
      message: "Routing saved.",
    };
    const nextPath = String(result?.path || path).trim();
    if (nextPath && nextPath !== path) {
      openPageTemplate(nextPath);
    }
  } catch (err) {
    console.error("Failed to save page template routing:", err);
    templateRoutingStatus.value = {
      type: "error",
      message: err?.message || "Failed to save routing.",
    };
  } finally {
    savingTemplateRouting.value = false;
  }
}

function openSelectedIntegrationSchema() {
  const integrationId = String(mappingDraft.primaryIntegrationId || "").trim();
  if (!integrationId) return;
  router.push({
    path: "/admin/integrations/edit",
    query: {
      integrationId,
      subsection: "schema",
    },
  });
}

function openSelectedIntegrationReviewList() {
  const integrationId = String(mappingDraft.primaryIntegrationId || "").trim();
  if (!integrationId) return;
  router.push({
    path: "/admin/integrations/review",
    query: { integrationId },
  });
}

function normalizeSourceRouteEntry(entry) {
  if (!entry || typeof entry !== "object") return null;
  const sourceRouteRef = normalizeSourceRouteRef(entry.source_route_ref || entry.id || "");
  if (!sourceRouteRef) return null;
  const sourceType = String(entry.source_type || "").trim().toLowerCase();
  if (sourceType !== "blog" && sourceType !== "program") return null;
  const sourceKind = String(entry.source_kind || "").trim().toLowerCase()
    || (sourceType === "blog" ? "item" : "gig");
  const parentRoute = normalizeParentRoute(entry.parent_route || "");
  const sectionTemplateRef = normalizeSectionTemplateRef(
    entry.section_template_ref || `${sourceType}/default`,
    `${sourceType}/default`,
  );
  const explicitLabel = String(entry.label || "").trim();
  const label = explicitLabel || `${parentRoute || "/"} -- ${sourceType}:${sourceKind}`;
  return {
    source_route_ref: sourceRouteRef,
    parent_route: parentRoute,
    source_type: sourceType,
    source_kind: sourceKind,
    section_template_ref: sectionTemplateRef,
    label,
  };
}

const normalizedSourceRoutes = computed(() => {
  const seen = new Set();
  const rows = [];
  (Array.isArray(itemPageSourceRoutes.value) ? itemPageSourceRoutes.value : []).forEach((entry) => {
    const normalized = normalizeSourceRouteEntry(entry);
    if (!normalized) return;
    if (seen.has(normalized.source_route_ref)) return;
    seen.add(normalized.source_route_ref);
    rows.push(normalized);
  });
  return rows.sort((a, b) => {
    const routeCompare = String(a.parent_route || "").localeCompare(String(b.parent_route || ""));
    if (routeCompare !== 0) return routeCompare;
    const sourceCompare = String(a.source_type || "").localeCompare(String(b.source_type || ""));
    if (sourceCompare !== 0) return sourceCompare;
    return String(a.source_kind || "").localeCompare(String(b.source_kind || ""));
  });
});

const itemPageSourceRouteOptions = computed(() =>
  normalizedSourceRoutes.value.map((entry) => ({
    value: entry.source_route_ref,
    label: entry.label || `${entry.parent_route || "/"} -- ${entry.source_type}:${entry.source_kind}`,
  }))
);

function resolveSectionTemplateRefForItemPage(sourceType, sourceKind, parentRoute) {
  const normalizedSourceType = normalizeItemPageSourceType(sourceType, "blog");
  const normalizedSourceKind = normalizeItemPageSourceKind(
    normalizedSourceType,
    sourceKind,
    normalizedSourceType === "program" ? "gig" : "item",
  );
  const normalizedParentRoute = normalizeParentRoute(parentRoute || "");
  const match = normalizedSourceRoutes.value.find((entry) => {
    if (String(entry.source_type || "").trim().toLowerCase() !== normalizedSourceType) return false;
    if (String(entry.source_kind || "").trim().toLowerCase() !== normalizedSourceKind) return false;
    if (normalizedParentRoute && String(entry.parent_route || "") !== normalizedParentRoute) return false;
    return true;
  });
  return normalizeSectionTemplateRef(
    match?.section_template_ref || `${normalizedSourceType}/default`,
    `${normalizedSourceType}/default`,
  );
}

function routeEntryByRef(sourceRouteRef) {
  const normalizedRef = normalizeSourceRouteRef(sourceRouteRef);
  if (!normalizedRef) return null;
  return normalizedSourceRoutes.value.find(
    (entry) => String(entry.source_route_ref || "") === normalizedRef
  ) || null;
}

const mappingSourceRouteEntry = computed(() => routeEntryByRef(mappingDraft.sourceRouteRef));
const mappingTemplateParentRoute = computed(() => {
  const fromDoc = normalizeParentRoute(currentPageTemplateDoc.value?.parent_route || "");
  if (fromDoc) return fromDoc;
  const fromList = normalizeParentRoute(activePageTemplateListEntry.value?.parent_route || "");
  if (fromList) return fromList;
  return parsePageTemplatePath(pageTemplateInfo.value.path).parentRoute || "";
});
const mappingItemPreviewRoutePrefixes = computed(() => {
  if (!activePageIsItemPageTemplate.value) return [];
  const template = currentPageTemplateDoc.value || activePageTemplateListEntry.value || {};
  const draftSubroute = pageRoutingDraft.itemPageSubroute;
  const templateSubroute = template.item_page_subroute;
  const candidates = [
    composeEffectiveItemPageRoute(
      pageRoutingDraft.parentRoute || mappingTemplateParentRoute.value,
      draftSubroute || templateSubroute || "",
    ),
    pageTemplateEffectiveItemRoute(template),
    mappingTemplateParentRoute.value,
  ];
  const seen = new Set();
  return candidates
    .map((entry) => normalizeParentRoute(entry || ""))
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .filter((entry) => {
      const key = entry.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
});
const mappingSourceType = computed(() => {
  const routeType = String(mappingSourceRouteEntry.value?.source_type || "").trim().toLowerCase();
  if (routeType === "blog" || routeType === "program") return routeType;
  const templateType = String(
    currentPageTemplateDoc.value?.source_type
    || activePageTemplateListEntry.value?.source_type
    || "blog"
  ).trim().toLowerCase();
  if (templateType === "tiles" || templateType === "program" || templateType === "blog") {
    return templateType;
  }
  return "blog";
});

const mappingSourceKind = computed(() => {
  const routeKind = String(mappingSourceRouteEntry.value?.source_kind || "").trim().toLowerCase();
  if (routeKind === "stage" || routeKind === "gig" || routeKind === "item") return routeKind;
  const templateKind = String(
    currentPageTemplateDoc.value?.source_kind
    || activePageTemplateListEntry.value?.source_kind
    || ""
  ).trim().toLowerCase();
  if (templateKind === "stage" || templateKind === "gig" || templateKind === "item") return templateKind;
  if (mappingSourceType.value === "program") return "gig";
  return "item";
});

const mappingSupportsSharedItemsProvider = computed(() =>
  activePageIsItemPageTemplate.value && mappingSourceType.value === "blog"
);

const mappingSourceProvider = computed(() => {
  if (!mappingSupportsSharedItemsProvider.value) {
    return PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
  }
  return normalizeMappingSourceProvider(mappingDraft.sourceProvider)
    || PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS;
});

const mappingUsesSharedItems = computed(() =>
  mappingSourceProvider.value === PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS
);

const mappingUsesIntegration = computed(() =>
  mappingSourceProvider.value === PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
);

const mappingSourceColumnLabel = computed(() =>
  mappingUsesSharedItems.value
    ? "Source (Shared Blog Items)"
    : `Source (${activePageMappingIntegrationLabel.value})`
);

const mappingFieldHint = computed(() =>
  mappingUsesSharedItems.value
    ? "Item-page mappings read from shared blog items and keep generated-page edits as local overrides."
    : "Item-page mappings use integration review fields, so local review overrides update generated pages without relying on cached item data."
);

const sharedBlogSlugSourcePath = computed(() => {
  const template = currentPageTemplateDoc.value || activePageTemplateListEntry.value || {};
  const rawField = String(template?.item_page_slug_field || "").trim() || "title.de";
  if (rawField.startsWith("item.")) return rawField;
  return `item.${rawField}`;
});

function tokenizePath(value) {
  return String(value || "")
    .split(".")
    .map((part) => String(part || "").trim())
    .filter(Boolean);
}

function deepGetValue(source, path) {
  if (!source || typeof source !== "object") return null;
  const parts = tokenizePath(path);
  if (!parts.length) return null;
  let current = source;
  for (const part of parts) {
    if (!current || typeof current !== "object" || !(part in current)) {
      return null;
    }
    current = current[part];
  }
  return current;
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
  if (!source || typeof source !== "object") return null;
  const tokens = tokenizeObjectPath(path);
  if (!tokens.length) return null;
  let current = source;
  for (const token of tokens) {
    if (typeof token === "number") {
      if (!Array.isArray(current) || token < 0 || token >= current.length) return null;
      current = current[token];
      continue;
    }
    if (!current || typeof current !== "object" || !(token in current)) return null;
    current = current[token];
  }
  return current;
}

function clonePlain(value) {
  if (value == null) return value;
  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    return value;
  }
}

function ensureArraySize(target, index) {
  while (target.length <= index) {
    target.push({});
  }
}

function deepSetPathValue(target, path, value) {
  const tokens = tokenizeObjectPath(path);
  if (!tokens.length) return;
  let current = target;
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    const isLast = index === tokens.length - 1;
    if (typeof token === "number") {
      if (!Array.isArray(current)) return;
      ensureArraySize(current, token);
      if (isLast) {
        current[token] = JSON.parse(JSON.stringify(value));
        return;
      }
      const nextToken = tokens[index + 1];
      if (!current[token] || (typeof current[token] !== "object")) {
        current[token] = typeof nextToken === "number" ? [] : {};
      }
      current = current[token];
      continue;
    }

    if (!current || typeof current !== "object") return;
    if (isLast) {
      current[token] = JSON.parse(JSON.stringify(value));
      return;
    }
    const nextToken = tokens[index + 1];
    if (!current[token] || (typeof current[token] !== "object")) {
      current[token] = typeof nextToken === "number" ? [] : {};
    }
    current = current[token];
  }
}

function formatPathLabel(path) {
  return String(path || "")
    .replace(/\[(\d+)\]/g, " $1 ")
    .replace(/[._]/g, " ")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/(^|\s)\S/g, (value) => value.toUpperCase());
}

function formatPathTokenLabel(token) {
  if (typeof token === "number") return `#${token + 1}`;
  return String(token || "")
    .replace(/[_-]/g, " ")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/(^|\s)\S/g, (value) => value.toUpperCase());
}

function formatHierarchicalPathLabel(path) {
  const tokens = tokenizeObjectPath(path);
  if (!tokens.length) return formatPathLabel(path);
  return tokens.map((token) => formatPathTokenLabel(token)).join(" > ");
}

function formatSourceOptionLabel(path, kind) {
  return `${formatHierarchicalPathLabel(path)} (${fieldKindLabel(kind)})`;
}

function formatSourcePathLabel(path) {
  const normalized = String(path || "").trim();
  if (normalized.startsWith("integration.")) {
    return `Integration > ${formatHierarchicalPathLabel(normalized.slice(12))}`;
  }
  if (normalized.startsWith("item.")) {
    return `Item > ${formatHierarchicalPathLabel(normalized.slice(5))}`;
  }
  return `Integration > ${formatHierarchicalPathLabel(normalized)}`;
}

function normalizeLinksSocialPlatformKey(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) return "";
  return raw
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "");
}

function buildLinksSocialPlatformContext(section) {
  if (!section || typeof section !== "object") return null;
  if (normalizeSectionType(section.section_type, "") !== LINKS_SECTION_TYPE) return null;
  const typeData = (
    section.type_data
    && typeof section.type_data === "object"
    && !Array.isArray(section.type_data)
  ) ? section.type_data : null;
  if (!typeData || !Boolean(typeData.social_mode)) return null;
  const items = Array.isArray(typeData.items) ? typeData.items : [];
  const platformIndexByKey = {};
  const platformKeyByIndex = {};
  items.forEach((entry, index) => {
    if (!entry || typeof entry !== "object") return;
    const platformKey = normalizeLinksSocialPlatformKey(entry.icon);
    if (!platformKey || platformIndexByKey[platformKey] != null) return;
    platformIndexByKey[platformKey] = index;
    platformKeyByIndex[index] = platformKey;
  });
  return {
    platformIndexByKey,
    platformKeyByIndex,
  };
}

function toLinksSocialKeyPath(path, context) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath || !context) return normalizedPath;
  const match = normalizedPath.match(LINKS_SOCIAL_ITEM_INDEX_PATH_RE);
  if (!match) return normalizedPath;
  const index = Number.parseInt(match[1], 10);
  const platformKey = context.platformKeyByIndex[index];
  if (!platformKey) return normalizedPath;
  const suffix = String(match[2] || "");
  return `type_data.items.${platformKey}${suffix}`;
}

function resolveLinksSocialKeyPath(path, context) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath || !context) return normalizedPath;
  const match = normalizedPath.match(LINKS_SOCIAL_ITEM_KEY_PATH_RE);
  if (!match) return normalizedPath;
  const platformKey = normalizeLinksSocialPlatformKey(match[1]);
  const index = context.platformIndexByKey[platformKey];
  if (!Number.isFinite(index)) return "";
  const suffix = String(match[2] || "");
  return `type_data.items[${index}]${suffix}`;
}

function targetPathForGroupStorage(group, targetPath) {
  const normalized = normalizePageTargetPathForCollection(group?.path, targetPath);
  if (!normalized) return "";
  if (group?.kind !== "section" || !group?.linksSocialContext) return normalized;
  return toLinksSocialKeyPath(normalized, group.linksSocialContext);
}

function targetPathForGroupStorageWithFallback(group, targetPath, fallbackCollectionPath = "") {
  if (!group || !group.path) return "";
  const candidateCollectionPaths = [
    group.path,
    group.indexPath,
    fallbackCollectionPath,
  ].filter(Boolean);
  const seen = new Set();
  for (const collectionPath of candidateCollectionPaths) {
    const normalizedCollectionPath = normalizePageMappingCollectionPath(collectionPath);
    if (!normalizedCollectionPath || seen.has(normalizedCollectionPath)) continue;
    seen.add(normalizedCollectionPath);
    const normalized = normalizePageTargetPathForCollection(normalizedCollectionPath, targetPath);
    if (!normalized) continue;
    if (group.kind === "section" && group.linksSocialContext) {
      return toLinksSocialKeyPath(normalized, group.linksSocialContext);
    }
    return normalized;
  }
  return "";
}

function targetPathForGroupResolution(group, targetPath) {
  const normalized = normalizePageTargetPathForCollection(group?.path, targetPath);
  if (!normalized) return "";
  if (group?.kind !== "section" || !group?.linksSocialContext) return normalized;
  return resolveLinksSocialKeyPath(normalized, group.linksSocialContext);
}

function normalizeSectionTargetOptionsForLinksSocial(options, context) {
  if (!context) return Array.isArray(options) ? options : [];
  const seen = new Set();
  const next = [];
  (Array.isArray(options) ? options : []).forEach((entry) => {
    const path = toLinksSocialKeyPath(entry?.path, context);
    if (!path || seen.has(path)) return;
    seen.add(path);
    const kind = String(entry?.kind || "text");
    next.push({
      path,
      kind,
      label: `${formatPathLabel(path)} (${fieldKindLabel(kind)})`,
    });
  });
  return next;
}

function isImagePath(path) {
  const normalized = String(path || "").toLowerCase();
  return (
    normalized.includes("image")
    || normalized.includes("photo")
    || normalized.includes("thumbnail")
    || normalized.includes("cover")
    || normalized.includes("logo")
    || normalized.includes("avatar")
    || normalized.includes("background_media_url")
  );
}

function inferFieldKind(path, value) {
  if (isImagePath(path)) return "image";
  if (typeof value === "number") return "number";
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "string" && isIsoDateTimeString(value)) return "datetime";
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const hasDE = Object.prototype.hasOwnProperty.call(value, "de");
    const hasEN = Object.prototype.hasOwnProperty.call(value, "en");
    if (hasDE || hasEN) return "text";
  }
  return "text";
}

function integrationSchemaFieldKind(field) {
  const type = String(field?.effective_type || field?.manual_type || field?.detected_type || "")
    .trim()
    .toLowerCase();
  if (type === "json" || type === "undefined" || type === "null") return "";
  if (type === "image") return "image";
  if (type === "number") return "number";
  if (type === "boolean") return "boolean";
  if (type === "datetime" || type === "date") return "datetime";
  if (type === "color") return "color";
  if (type === "url") return "url";
  if (type === "json") return "json";
  if (type === "list") return "list";
  return "text";
}

function isIsoDateTimeString(value) {
  const text = String(value || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:?\d{2})?$/.test(text)) {
    return false;
  }
  return Number.isFinite(Date.parse(text));
}

function fieldKindLabel(kind) {
  if (kind === "image") return "Image";
  if (kind === "number") return "Number";
  if (kind === "boolean") return "Boolean";
  if (kind === "datetime") return "Datetime";
  if (kind === "color") return "Color";
  if (kind === "url") return "URL";
  if (kind === "json") return "JSON";
  if (kind === "list") return "List";
  return "Text";
}

function compatibleKinds(sourceKind, targetKind) {
  if (!sourceKind || !targetKind) return true;
  if (sourceKind === "image") return targetKind === "image" || targetKind === "text" || targetKind === "url";
  if (sourceKind === "number") return targetKind === "number" || targetKind === "text";
  if (sourceKind === "boolean") return targetKind === "boolean" || targetKind === "text";
  if (sourceKind === "datetime") return targetKind === "datetime" || targetKind === "date" || targetKind === "text";
  if (sourceKind === "color") return targetKind === "color" || targetKind === "text";
  return ["text", "number", "boolean", "datetime", "date", "color", "url", "json", "list"].includes(targetKind);
}

function normalizeMappingSourceProvider(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return PAGE_MAPPING_SOURCE_PROVIDERS.has(normalized) ? normalized : "";
}

function rawMappingHasIntegrationSourcePaths(rawMapping) {
  const raw = rawMapping && typeof rawMapping === "object" && !Array.isArray(rawMapping)
    ? convertKeysToCamel(rawMapping)
    : {};
  const rowsByCollection = raw.listMappingsByCollectionPath;
  if (!rowsByCollection || typeof rowsByCollection !== "object" || Array.isArray(rowsByCollection)) {
    return false;
  }
  return Object.values(rowsByCollection).some((rows) =>
    Array.isArray(rows) && rows.some((row) =>
      String(row?.sourcePath || "").trim().startsWith("integration.")
    )
  );
}

function inferMappingSourceProvider(rawMapping, template = currentPageTemplateDoc.value || activePageTemplateListEntry.value || {}) {
  const raw = rawMapping && typeof rawMapping === "object" && !Array.isArray(rawMapping)
    ? convertKeysToCamel(rawMapping)
    : {};
  const explicitProvider = normalizeMappingSourceProvider(raw.sourceProvider);
  if (explicitProvider) return explicitProvider;
  if (String(raw.selectedIntegrationId || "").trim()) {
    return PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
  }
  if (rawMappingHasIntegrationSourcePaths(rawMapping)) {
    return PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
  }
  const templatePayload = template && typeof template === "object" && !Array.isArray(template)
    ? convertKeysToCamel(template)
    : {};
  const sourceType = String(templatePayload.sourceType || mappingSourceType.value || "").trim().toLowerCase();
  if (sourceType === "blog") return PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS;
  return PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
}

function normalizeOutputMappingSourcePath(path, sourceProvider = mappingSourceProvider.value) {
  const normalized = String(path || "").trim();
  if (!normalized) return "";
  const provider = normalizeMappingSourceProvider(sourceProvider) || PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
  if (provider === PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS) {
    if (normalized.startsWith("item.") || normalized.startsWith("integration.")) return normalized;
    return `item.${normalized}`;
  }
  if (normalized.startsWith("integration.")) return normalized;
  if (normalized.startsWith("item.")) {
    const itemPath = normalized.slice(5).trim();
    return itemPath ? `integration.${itemPath}` : "";
  }
  return `integration.${normalized}`;
}

const PAGE_MAPPING_SECTION_COLLECTION_RE = /^sections\[([^\]]+)\]$/;
const PAGE_MAPPING_SECTION_TARGET_RE = /^sections\[([^\]]+)\]\.(.+)$/;
const PAGE_MAPPING_SECTION_TOKEN_RE = /^[A-Za-z0-9_.:-]+$/;
const PAGE_TEMPLATE_DEFAULT_HIDDEN_IMAGE_TRANSFORM_FIELDS = new Set([
  "zoom",
  "rotation",
  "focalx",
  "focaly",
]);
const PAGE_TEMPLATE_FRONTEND_PAGE_TARGET_PATTERNS = [
  "slug",
  "title.*",
  "menu_title.*",
  "in_menu",
  "menu_order",
  "redirect_to",
  "section_bg_pinned_start_key",
  "section_bg_pinned_end_key",
];
const PAGE_TEMPLATE_FRONTEND_HEADER_TARGET_PATTERNS = [
  "background_media_url",
  "background_zoom",
  "background_focal_x",
  "background_focal_y",
  "background_rotation",
  "overlay_image_url",
  "overlay_zoom",
  "overlay_focal_x",
  "overlay_focal_y",
  "overlay_rotation",
  "hero_title.*",
  "hero_subtitle.*",
  "cta_buttons[*].text.*",
  "cta_buttons[*].url",
  "cta_buttons[*].button_type",
];
const PAGE_TEMPLATE_FRONTEND_SECTION_TARGET_PATTERNS_BY_TYPE = {
  text: [
    "title.*",
    "type_data.body.*",
  ],
  text_image: [
    "title.*",
    "type_data.body.*",
    "type_data.image_url",
    "type_data.image_author",
    "type_data.image_click_url",
    "type_data.image_interaction",
    "type_data.image_layout",
    "type_data.image_layout_responsive.*",
    "type_data.image_align_x",
    "type_data.image_max_width_percent",
    "type_data.image_max_width_percent_responsive.*",
    "type_data.image_max_height_vh",
    "type_data.image_max_height_vh_responsive.*",
    "type_data.image_width_px",
    "type_data.image_min_width_px",
    "type_data.image_target_width_percent",
    "type_data.image_max_width_px",
    "type_data.image_height_px",
    "type_data.image_text_gap",
    "type_data.image_text_gap_responsive.*",
    "type_data.image_border_radius",
    "type_data.image_border_radius_responsive.*",
    "type_data.image_bg_opacity",
    "type_data.image_aspect_ratio",
    "type_data.image_aspect_ratio_responsive.*",
    "type_data.image_bg_zoom",
    "type_data.image_bg_focal_x",
    "type_data.image_bg_focal_y",
    "type_data.image_bg_rotation",
  ],
  video: [
    "title.*",
    "type_data.body.*",
    "type_data.video_id",
    "type_data.wrapper",
    "type_data.tv_color",
    "type_data.tv_color_link",
  ],
  faq: [
    "title.*",
    "type_data.body.*",
    "type_data.faqs[*].question.*",
    "type_data.faqs[*].answer.*",
    "type_data.faqs[*].tag.*",
    "type_data.faqs[*].start_date",
    "type_data.faqs[*].end_date",
    "type_data.scope.*",
    "type_data.more_link",
    "type_data.question_color",
    "type_data.question_color_link",
    "type_data.answer_color",
    "type_data.answer_color_link",
    "type_data.separator_color",
    "type_data.separator_color_link",
  ],
  links: [
    "title.*",
    "type_data.body.*",
    "type_data.items[*].title.*",
    "type_data.items[*].image_url",
    "type_data.items[*].icon",
    "type_data.items[*].icon_pack",
    "type_data.items[*].link_url",
    "type_data.items.*.title.*",
    "type_data.items.*.image_url",
    "type_data.items.*.icon",
    "type_data.items.*.icon_pack",
    "type_data.items.*.link_url",
    "type_data.hide_item_title",
    "type_data.alignment",
    "type_data.item_max_height",
    "type_data.non_social_item_max_width",
    "type_data.item_spacing",
    "type_data.social_mode",
    "type_data.hide_icons_without_links",
    "type_data.icon_color",
    "type_data.icon_color_link",
  ],
  ticker: [
    "title.*",
    "type_data.items[*].text.*",
    "type_data.items[*].timestamp",
    "type_data.separator_image_url",
    "type_data.pin_to_header",
  ],
  gallery: [
    "title.*",
    "type_data.body.*",
    "type_data.images[*].image_url",
    "type_data.images[*].image_author",
    "type_data.images[*].zoom",
    "type_data.images[*].focal_x",
    "type_data.images[*].focal_y",
    "type_data.images[*].rotation",
    "type_data.images[*].alt.*",
    "type_data.images[*].caption.*",
    "type_data.show_captions",
    "type_data.layout",
    "type_data.aspect_ratio",
    "type_data.orientation",
  ],
  blog: [
    "title.*",
    "type_data.body.*",
    "type_data.video_url",
    "type_data.scope.*",
    "type_data.access",
  ],
  markdown: [
    "title.*",
    "type_data.raw_markdown",
  ],
  html: [
    "title.*",
    "type_data.mode",
    "type_data.fetch_url",
    "type_data.fetch_selector",
    "type_data.raw_html",
    "type_data.raw_css",
    "type_data.raw_js",
    "type_data.embed_code",
    "type_data.embed_provider",
  ],
  tiles: [
    "title.*",
    "type_data.body.*",
    "type_data.parent_route",
    "type_data.grid_mode",
    "type_data.rows",
    "type_data.columns",
    "type_data.tile_min_width",
    "type_data.tile_max_width",
    "type_data.aspect_ratio",
    "type_data.direction",
    "type_data.checker_color1",
    "type_data.checker_color2",
    "type_data.title_gradient_color",
    "type_data.title_gradient_color_link",
    "type_data.artist_button_type",
    "type_data.always_show_title",
    "type_data.tile_show_reset_button",
    "type_data.tile_top_info_align",
    "type_data.tile_bottom_info_align",
    "type_data.tile_sort_mode",
    "type_data.use_program_gigs",
    "type_data.filters[*].name",
    "type_data.filters[*].target_path",
    "type_data.filters[*].manual_options[*]",
    "type_data.filters[*].enabled",
    "type_data.filter_control_style",
    "type_data.filter_control_order[*]",
    "type_data.tiles[*].image_url",
    "type_data.tiles[*].zoom",
    "type_data.tiles[*].focal_x",
    "type_data.tiles[*].focal_y",
    "type_data.tiles[*].rotation",
    "type_data.tiles[*].title.*",
    "type_data.tiles[*].subtitle.*",
    "type_data.tiles[*].location",
    "type_data.tiles[*].time",
  ],
  program: [
    "title.*",
    "type_data.body.*",
    "type_data.gigs[*].title.*",
    "type_data.gigs[*].start",
    "type_data.gigs[*].end",
    "type_data.gigs[*].stage",
    "type_data.gigs[*].gig_type",
    "type_data.gigs[*].genre.*",
    "type_data.gigs[*].genre_selection[*]",
    "type_data.gigs[*].description.*",
    "type_data.gigs[*].image_url",
    "type_data.gigs[*].image_zoom",
    "type_data.gigs[*].image_focal_x",
    "type_data.gigs[*].image_focal_y",
    "type_data.gigs[*].image_rotation",
    "type_data.gigs[*].highlight_changes",
    "type_data.gigs[*].canceled",
    "type_data.gigs[*].previous_start",
    "type_data.gigs[*].previous_end",
    "type_data.gigs[*].page_slug",
    "type_data.gigs[*].item_url",
    "type_data.route_view_configs[*].route_pattern",
    "type_data.route_view_configs[*].grouping_mode",
    "type_data.route_view_configs[*].view_mode",
    "type_data.route_view_configs[*].stage_filter_mode",
    "type_data.route_view_configs[*].stage_filter_value",
    "type_data.route_view_configs[*].day_filter",
    "type_data.default_grouping",
    "type_data.fixed_stage_id",
    "type_data.fixed_day",
    "type_data.fixed_gig_id",
    "type_data.stage_parent_route",
    "type_data.gig_parent_route",
    "type_data.allow_group_toggle",
    "type_data.allow_day_selection",
    "type_data.allow_stage_filter",
    "type_data.show_view_toggle",
    "type_data.default_view_mode",
    "type_data.time_slot_minutes",
    "type_data.show_genre",
    "type_data.show_description",
    "type_data.show_changes",
    "type_data.day_start_hour",
    "type_data.day_end_hour",
    "type_data.max_visible_hours",
    "type_data.date_selection_color",
    "type_data.date_selection_color_link",
    "type_data.stage_row_height",
  ],
};

function normalizePageMappingSectionToken(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (/^\d+$/.test(raw)) return String(Number.parseInt(raw, 10));
  if (!PAGE_MAPPING_SECTION_TOKEN_RE.test(raw)) return "";
  return raw;
}

function isNumericPageMappingSectionToken(value) {
  const token = String(value || "").trim();
  return Boolean(token && /^\d+$/.test(token));
}

function composePageMappingSectionCollectionPath(token) {
  const normalizedToken = normalizePageMappingSectionToken(token);
  return normalizedToken ? `sections[${normalizedToken}]` : "";
}

function pageMappingSectionTokenFromCollectionPath(path) {
  const normalized = String(path || "").trim();
  const match = normalized.match(PAGE_MAPPING_SECTION_COLLECTION_RE);
  return match ? normalizePageMappingSectionToken(match[1]) : "";
}

function templateSectionIdFromMappingRow(row, collectionPath = "") {
  const sourceRow = row && typeof row === "object" && !Array.isArray(row)
    ? convertKeysToCamel(row)
    : {};
  const direct = normalizePageMappingSectionToken(
    sourceRow.templateSectionId
    || sourceRow.templateEmbeddedSectionId
    || ""
  );
  if (direct && !isNumericPageMappingSectionToken(direct)) return direct;
  const collectionToken = pageMappingSectionTokenFromCollectionPath(collectionPath);
  return collectionToken && !isNumericPageMappingSectionToken(collectionToken)
    ? collectionToken
    : "";
}

function templateEmbeddedSectionId(section) {
  if (!section || typeof section !== "object") return "";
  const direct = normalizePageMappingSectionToken(
    section.template_embedded_section_id
    || section.templateEmbeddedSectionId
    || section.embedded_section_id
    || section.embeddedSectionId
    || ""
  );
  if (direct && !isNumericPageMappingSectionToken(direct)) return direct;
  const rawId = String(section.id || section._id || "").trim();
  const parts = rawId.split("__").filter(Boolean);
  const candidate = normalizePageMappingSectionToken(parts[parts.length - 1] || "");
  return candidate && !isNumericPageMappingSectionToken(candidate) ? candidate : "";
}

function currentTemplateSections() {
  const sections = currentPageTemplateDoc.value?.sections;
  return Array.isArray(sections) ? sections : [];
}

function stableCollectionPathForCurrentTemplate(collectionPath) {
  const normalized = normalizePageMappingCollectionPath(collectionPath);
  const token = pageMappingSectionTokenFromCollectionPath(normalized);
  if (!token || !isNumericPageMappingSectionToken(token)) return normalized;
  const section = currentTemplateSections()[Number.parseInt(token, 10)];
  const embeddedId = templateEmbeddedSectionId(section);
  return embeddedId ? composePageMappingSectionCollectionPath(embeddedId) : normalized;
}

function normalizePageMappingCollectionPath(path) {
  const normalized = String(path || "").trim();
  if (normalized === "page" || normalized === "header") return normalized;
  const match = normalized.match(PAGE_MAPPING_SECTION_COLLECTION_RE);
  if (!match) return "";
  return composePageMappingSectionCollectionPath(match[1]);
}

function splitPageMappingTargetPath(path) {
  const normalized = String(path || "").trim();
  if (!normalized) return [null, null];
  if (normalized.startsWith("page.")) {
    const targetPath = normalized.slice(5).trim();
    return targetPath ? ["page", targetPath] : [null, null];
  }
  if (normalized.startsWith("header.")) {
    const targetPath = normalized.slice(7).trim();
    return targetPath ? ["header", targetPath] : [null, null];
  }
  const sectionMatch = normalized.match(PAGE_MAPPING_SECTION_TARGET_RE);
  if (sectionMatch) {
    const sectionToken = normalizePageMappingSectionToken(sectionMatch[1]);
    const targetPath = String(sectionMatch[2] || "").trim();
    return sectionToken && targetPath
      ? [composePageMappingSectionCollectionPath(sectionToken), targetPath]
      : [null, null];
  }
  return ["page", normalized];
}

function normalizePageTargetPathForCollection(collectionPath, targetPath) {
  const normalizedCollectionPath = normalizePageMappingCollectionPath(collectionPath);
  if (!normalizedCollectionPath) return "";

  const rawTargetPath = canonicalizePageMappingTargetPath(targetPath);
  if (!rawTargetPath) return "";

  if (
    !rawTargetPath.startsWith("page.")
    && !rawTargetPath.startsWith("header.")
    && !rawTargetPath.startsWith("sections[")
  ) {
    return rawTargetPath;
  }

  const [targetCollectionPath, normalizedTargetPath] = splitPageMappingTargetPath(rawTargetPath);
  if (!targetCollectionPath || !normalizedTargetPath) return "";
  if (targetCollectionPath !== normalizedCollectionPath) return "";
  return normalizedTargetPath;
}

function canonicalizePageMappingTargetPath(path) {
  const normalized = String(path || "").trim();
  if (!normalized) return "";
  const parts = normalized.split(".");
  const last = parts[parts.length - 1];
  if (last === "fixedGigId" || last === "fixed_gig_id") {
    const previous = parts.length > 1 ? parts[parts.length - 2] : "";
    if (previous === "typeData" || previous === "type_data") {
      parts.splice(parts.length - 2, 2, "type_data", "fixed_gig_id");
    } else {
      parts.splice(parts.length - 1, 1, "type_data", "fixed_gig_id");
    }
    return parts.join(".");
  }
  return normalized;
}

function isFixedGigMappingTargetPath(path) {
  const normalized = canonicalizePageMappingTargetPath(path);
  return normalized === "type_data.fixed_gig_id" || normalized.endsWith(".type_data.fixed_gig_id");
}

function groupSupportsTargetPath(group, targetPath, fallbackCollectionPath = "") {
  if (!group || !group.path) return false;
  const normalizedTargetPath = targetPathForGroupStorageWithFallback(
    group,
    targetPath,
    fallbackCollectionPath,
  );
  if (!normalizedTargetPath) return false;
  if (group.kind === "page" || group.kind === "header") return true;
  const options = Array.isArray(group.targetOptions) ? group.targetOptions : [];
  return options.some((option) => String(option?.path || "").trim() === normalizedTargetPath);
}

function resolveMappingGroupForTargetPath(baseCollectionPath, targetPath, groups = mappingTargetGroups.value) {
  const normalizedCollectionPath = normalizePageMappingCollectionPath(baseCollectionPath);
  if (!normalizedCollectionPath) return null;
  const availableGroups = Array.isArray(groups) ? groups : [];
  const exactGroup = availableGroups.find((group) => group?.path === normalizedCollectionPath) || null;

  if (normalizedCollectionPath === "page" || normalizedCollectionPath === "header") {
    return exactGroup;
  }

  const sectionToken = pageMappingSectionTokenFromCollectionPath(normalizedCollectionPath);
  if (sectionToken && !isNumericPageMappingSectionToken(sectionToken)) {
    return availableGroups.find((group) => group?.templateSectionId === sectionToken) || exactGroup;
  }

  const sameIndexGroup = availableGroups.find(
    (group) => group?.kind === "section" && group?.indexPath === normalizedCollectionPath
  ) || exactGroup;
  if (sameIndexGroup && groupSupportsTargetPath(sameIndexGroup, targetPath, normalizedCollectionPath)) {
    return sameIndexGroup;
  }

  const matchingGroups = availableGroups.filter(
    (group) => group?.kind === "section" && groupSupportsTargetPath(
      group,
      targetPath,
      normalizedCollectionPath,
    )
  );
  if (matchingGroups.length === 1) {
    return matchingGroups[0];
  }

  return sameIndexGroup || matchingGroups[0] || exactGroup;
}

function resolveMappingGroupForRow(baseCollectionPath, row, groups = mappingTargetGroups.value) {
  const normalizedCollectionPath = normalizePageMappingCollectionPath(baseCollectionPath);
  if (!normalizedCollectionPath) return null;
  const sourceRow = row && typeof row === "object" && !Array.isArray(row)
    ? convertKeysToCamel(row)
    : {};
  const templateSectionId = templateSectionIdFromMappingRow(sourceRow, normalizedCollectionPath);
  if (templateSectionId) {
    const directGroup = (Array.isArray(groups) ? groups : []).find(
      (group) => group?.templateSectionId === templateSectionId
    );
    if (directGroup) return directGroup;
  }
  return resolveMappingGroupForTargetPath(
    normalizedCollectionPath,
    sourceRow.targetPath,
    groups,
  );
}

function normalizePageListMappingsByCollectionPath(
  rawMap,
  groups = mappingTargetGroups.value,
  sourceProvider = mappingSourceProvider.value,
) {
  const next = {};
  if (!rawMap || typeof rawMap !== "object" || Array.isArray(rawMap)) return next;
  const provider = normalizeMappingSourceProvider(sourceProvider) || PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
  Object.entries(rawMap).forEach(([rawCollectionPath, rawRows]) => {
    const baseCollectionPath = normalizePageMappingCollectionPath(rawCollectionPath);
    if (!baseCollectionPath || !Array.isArray(rawRows)) return;
    rawRows.forEach((row) => {
      const sourceRow = (
        row
        && typeof row === "object"
        && !Array.isArray(row)
      ) ? convertKeysToCamel(row) : {};
      let sourcePath = normalizeOutputMappingSourcePath(sourceRow.sourcePath, provider);
      const templateSectionId = templateSectionIdFromMappingRow(sourceRow, baseCollectionPath);
      const targetGroup = resolveMappingGroupForRow(baseCollectionPath, sourceRow, groups);
      const collectionPath = targetGroup?.path || (
        templateSectionId
          ? composePageMappingSectionCollectionPath(templateSectionId)
          : stableCollectionPathForCurrentTemplate(baseCollectionPath)
      );
      let targetPath = targetGroup
        ? targetPathForGroupStorageWithFallback(targetGroup, sourceRow.targetPath, baseCollectionPath)
        : normalizePageTargetPathForCollection(collectionPath, sourceRow.targetPath);
      if (!targetPath && collectionPath !== baseCollectionPath) {
        targetPath = normalizePageTargetPathForCollection(baseCollectionPath, sourceRow.targetPath);
      }
      if (
        isFixedGigMappingTargetPath(targetPath)
        && provider === PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
        && fixedGigMappingNeedsPrimaryKeyFallback(sourceRow.sourcePath)
      ) {
        sourcePath = fixedGigMappingSourcePath() || sourcePath;
      }
      if (!sourcePath || !targetPath || !collectionPath) return;
      const nextRow = {
        source_path: sourcePath,
        target_path: targetPath,
      };
      const stableSectionId = targetGroup?.templateSectionId
        || templateSectionIdFromMappingRow(sourceRow, collectionPath);
      if (stableSectionId) nextRow.template_section_id = stableSectionId;
      if (!next[collectionPath]) next[collectionPath] = [];
      next[collectionPath].push(nextRow);
    });
  });
  return next;
}

function normalizePageHiddenTargetPathsByCollectionPath(rawMap, groups = mappingTargetGroups.value) {
  const next = {};
  if (!rawMap || typeof rawMap !== "object" || Array.isArray(rawMap)) return next;
  Object.entries(rawMap).forEach(([rawCollectionPath, rawHiddenPaths]) => {
    const baseCollectionPath = normalizePageMappingCollectionPath(rawCollectionPath);
    if (!baseCollectionPath || !Array.isArray(rawHiddenPaths)) return;
    rawHiddenPaths.forEach((rawHiddenPath) => {
      const targetGroup = resolveMappingGroupForTargetPath(
        baseCollectionPath,
        rawHiddenPath,
        groups,
      );
      if (targetGroup?.kind === "section") return;
      const collectionPath = targetGroup?.path || stableCollectionPathForCurrentTemplate(baseCollectionPath);
      if (!collectionPath) return;
      if (!["page", "header"].includes(collectionPath)) return;
      let hiddenPath = targetGroup
        ? targetPathForGroupStorageWithFallback(targetGroup, rawHiddenPath, baseCollectionPath)
        : normalizePageTargetPathForCollection(collectionPath, rawHiddenPath);
      if (!hiddenPath && collectionPath !== baseCollectionPath) {
        hiddenPath = normalizePageTargetPathForCollection(baseCollectionPath, rawHiddenPath);
      }
      if (!hiddenPath) return;
      if (targetGroup && !groupHasTargetOption(targetGroup, hiddenPath)) return;
      if (!next[collectionPath]) next[collectionPath] = [];
      if (next[collectionPath].includes(hiddenPath)) return;
      next[collectionPath].push(hiddenPath);
    });
  });
  return next;
}

function defaultHiddenTargetClearKey(collectionPath, targetPath) {
  return `${normalizePageMappingCollectionPath(collectionPath)}::${String(targetPath || "").trim()}`;
}

function normalizeTargetPathTokenForVisibility(value) {
  return String(value || "").trim().toLowerCase().replace(/[^a-z0-9]/g, "");
}

function isPageTemplateImageTransformTargetPath(path) {
  const normalized = String(path || "").trim();
  if (!normalized) return false;
  const stringTokens = tokenizeObjectPath(normalized).filter((token) => typeof token === "string");
  const lastToken = normalizeTargetPathTokenForVisibility(stringTokens[stringTokens.length - 1] || "");
  for (const field of PAGE_TEMPLATE_DEFAULT_HIDDEN_IMAGE_TRANSFORM_FIELDS) {
    if (lastToken === field || lastToken.endsWith(field)) return true;
  }
  return false;
}

function isDefaultHiddenTargetForVisibilityGroup(group, targetPath) {
  const normalizedTargetPath = targetPathForGroupStorage(group, targetPath);
  if (!group || !normalizedTargetPath) return false;
  return isPageTemplateImageTransformTargetPath(normalizedTargetPath);
}

function defaultHiddenTargetPathsForGroup(group) {
  if (!group || !["page", "header"].includes(group.kind)) return [];
  const next = [];
  const seen = new Set();
  (Array.isArray(group.targetOptions) ? group.targetOptions : []).forEach((option) => {
    const targetPath = targetPathForGroupStorage(group, option?.path);
    if (!targetPath || seen.has(targetPath)) return;
    if (!isDefaultHiddenTargetForVisibilityGroup(group, targetPath)) return;
    seen.add(targetPath);
    next.push(targetPath);
  });
  return next;
}

function applyDefaultPageTemplateHiddenTargetPaths() {
  if (!showPageMappingEditor.value) return false;
  const current = normalizePageHiddenTargetPathsByCollectionPath(
    mappingDraft.hiddenListTargetPathsByCollectionPath
  );
  let changed = false;
  const next = { ...current };
  mappingTargetGroups.value.forEach((group) => {
    if (!group?.path || !["page", "header"].includes(group.kind)) return;
    const defaults = defaultHiddenTargetPathsForGroup(group);
    if (!defaults.length) return;
    const existing = Array.isArray(next[group.path]) ? [...next[group.path]] : [];
    const seen = new Set(existing);
    defaults.forEach((targetPath) => {
      if (seen.has(targetPath)) return;
      if (mappingDefaultHiddenTargetClears.value.has(defaultHiddenTargetClearKey(group.path, targetPath))) {
        return;
      }
      seen.add(targetPath);
      existing.push(targetPath);
      changed = true;
    });
    if (existing.length) {
      next[group.path] = existing;
    }
  });
  if (changed) {
    mappingDraft.hiddenListTargetPathsByCollectionPath = next;
  }
  return changed;
}

function normalizeMappingPreviewItemIndex(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  const normalized = Math.trunc(parsed);
  return normalized >= 0 ? normalized : null;
}

function normalizeMappingPreviewItemKey(value) {
  return String(value || "").trim();
}

function normalizePageIntegrationMappingPayload(rawMapping, { sourceProvider = "" } = {}) {
  const hasStructuredMapping = Boolean(
    rawMapping
    && typeof rawMapping === "object"
    && !Array.isArray(rawMapping)
  );
  const raw = hasStructuredMapping ? convertKeysToCamel(rawMapping) : {};
  const activeMode = String(raw.activeMode || "list").trim().toLowerCase();
  const normalizedActiveMode = ["auto", "list", "object"].includes(activeMode) ? activeMode : "list";
  const selectedIntegrationId = String(
    raw.selectedIntegrationId
    || ""
  ).trim();
  let normalizedSourceProvider = normalizeMappingSourceProvider(sourceProvider || raw.sourceProvider);
  if (!normalizedSourceProvider && selectedIntegrationId) {
    normalizedSourceProvider = PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
  }
  if (!normalizedSourceProvider && mappingSupportsSharedItemsProvider.value) {
    normalizedSourceProvider = PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS;
  }
  const effectiveSelectedIntegrationId = normalizedSourceProvider === PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS
    ? ""
    : selectedIntegrationId;
  const sourcePathProvider = normalizedSourceProvider || PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;

  const rawListMap = raw.listMappingsByCollectionPath;
  const listMappingsByCollectionPath = normalizePageListMappingsByCollectionPath(
    rawListMap,
    mappingTargetGroups.value,
    sourcePathProvider,
  );
  const hiddenListTargetPathsByCollectionPath = normalizePageHiddenTargetPathsByCollectionPath(
    raw.hiddenListTargetPathsByCollectionPath
  );
  const previewItemIndex = normalizeMappingPreviewItemIndex(raw.previewItemIndex);
  const previewItemKey = normalizeMappingPreviewItemKey(raw.previewItemKey);

  if (
    !effectiveSelectedIntegrationId
    && Object.keys(listMappingsByCollectionPath).length === 0
    && Object.keys(hiddenListTargetPathsByCollectionPath).length === 0
    && previewItemIndex == null
    && !previewItemKey
    && !normalizedSourceProvider
    && normalizedActiveMode === "list"
  ) {
    return {};
  }

  const normalized = {
    active_mode: normalizedActiveMode,
    selected_integration_id: effectiveSelectedIntegrationId || null,
    list_mappings_by_collection_path: listMappingsByCollectionPath,
    hidden_list_target_paths_by_collection_path: hiddenListTargetPathsByCollectionPath,
  };
  if (normalizedSourceProvider) {
    normalized.source_provider = normalizedSourceProvider;
  }
  if (previewItemIndex != null) {
    normalized.preview_item_index = previewItemIndex;
  }
  if (previewItemKey) {
    normalized.preview_item_key = previewItemKey;
  }
  return normalized;
}

function formatMappingOptionLabel(path, kind) {
  const normalizedPath = String(path || "").trim();
  if (normalizedPath.endsWith("fixed_gig_id")) {
    return `Fixed Gig ID (${fieldKindLabel(kind)})`;
  }
  if (normalizedPath.endsWith("highlight_changes")) {
    return `New Gig (${fieldKindLabel(kind)})`;
  }
  return `${formatPathLabel(normalizedPath)} (${fieldKindLabel(kind)})`;
}

function ensureOption(optionsMap, path, kind) {
  const normalizedPath = canonicalizePageMappingTargetPath(path);
  if (!normalizedPath) return;
  if (!optionsMap.has(normalizedPath)) {
    const normalizedKind = String(kind || "text");
    optionsMap.set(normalizedPath, {
      path: normalizedPath,
      kind: normalizedKind,
      label: formatMappingOptionLabel(normalizedPath, normalizedKind),
    });
  }
}

function collectScalarTargetOptions(node, basePath, optionsMap, depth = 0) {
  if (depth > 6) return;
  if (node == null) {
    ensureOption(optionsMap, basePath, inferFieldKind(basePath, node));
    return;
  }

  if (Array.isArray(node)) {
    node.slice(0, 12).forEach((entry, index) => {
      collectScalarTargetOptions(entry, `${basePath}[${index}]`, optionsMap, depth + 1);
    });
    return;
  }

  if (typeof node === "object") {
    const hasDE = Object.prototype.hasOwnProperty.call(node, "de");
    const hasEN = Object.prototype.hasOwnProperty.call(node, "en");
    if (hasDE || hasEN) {
      if (hasDE) ensureOption(optionsMap, `${basePath}.de`, inferFieldKind(`${basePath}.de`, node.de));
      if (hasEN) ensureOption(optionsMap, `${basePath}.en`, inferFieldKind(`${basePath}.en`, node.en));
      return;
    }
    Object.entries(node).forEach(([key, value]) => {
      const nextPath = basePath ? `${basePath}.${key}` : key;
      collectScalarTargetOptions(value, nextPath, optionsMap, depth + 1);
    });
    return;
  }

  ensureOption(optionsMap, basePath, inferFieldKind(basePath, node));
}

function stripPreviewRoutePrefixFromText(value, routePrefixes = []) {
  const text = String(value || "").trim();
  if (!text) return "";
  const pathText = text.replace(/^https?:\/\/[^/]+/i, "");
  const candidate = `/${pathText.replace(/^\/+/, "")}`;
  const normalizedPrefixes = (Array.isArray(routePrefixes) ? routePrefixes : [])
    .map((entry) => normalizeParentRoute(entry || ""))
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);
  for (const prefix of normalizedPrefixes) {
    const normalizedPrefix = `/${String(prefix).replace(/^\/+|\/+$/g, "")}/`;
    if (!candidate.toLowerCase().startsWith(normalizedPrefix.toLowerCase())) continue;
    const stripped = candidate.slice(normalizedPrefix.length).replace(/^\/+/, "").trim();
    return stripped || text;
  }
  return text;
}

function stripPreviewRoutePrefixesFromLabel(value, routePrefixes = []) {
  const text = String(value || "").trim();
  if (!text) return "";
  const whole = stripPreviewRoutePrefixFromText(text, routePrefixes);
  return whole.replace(/\(([^()]*)\)/g, (match, inner) => {
    const cleaned = String(inner || "")
      .split(",")
      .map((part) => stripPreviewRoutePrefixFromText(part.trim(), routePrefixes) || part.trim())
      .filter(Boolean)
      .join(", ");
    return cleaned ? `(${cleaned})` : match;
  });
}

function buildReviewPreviewOptionsFromItems(items, { routePrefixes = [] } = {}) {
  return (Array.isArray(items) ? items : [])
    .map((item, index) => {
      const itemKey = normalizeMappingPreviewItemKey(item?.item_key || item?.value);
      if (!itemKey) return null;
      const optionIndex = normalizeMappingPreviewItemIndex(item?.index);
      const label = stripPreviewRoutePrefixesFromLabel(
        item?.label || itemKey,
        routePrefixes,
      ) || itemKey;
      return {
        index: optionIndex != null ? optionIndex : index,
        item_key: itemKey,
        value: itemKey,
        label,
      };
    })
    .filter(Boolean)
    .sort((left, right) => {
      const labelOrder = String(left.label || "").localeCompare(String(right.label || ""), undefined, {
        sensitivity: "base",
        numeric: true,
      });
      if (labelOrder !== 0) return labelOrder;
      return String(left.item_key || "").localeCompare(String(right.item_key || ""), undefined, {
        sensitivity: "base",
        numeric: true,
      });
    });
}

function resolvePreviewReviewItemKey(options) {
  const rows = Array.isArray(options) ? options : [];
  if (!rows.length) return "";
  const requestedKey = normalizeMappingPreviewItemKey(mappingPreviewItemKey.value);
  if (requestedKey && rows.some((option) => option.item_key === requestedKey)) {
    return requestedKey;
  }
  const legacyIndex = normalizeMappingPreviewItemIndex(mappingPreviewItemIndex.value);
  if (legacyIndex != null) {
    const originalIndexMatch = rows.find((option) => option.index === legacyIndex);
    if (originalIndexMatch?.item_key) return originalIndexMatch.item_key;
    if (rows[legacyIndex]?.item_key) return rows[legacyIndex].item_key;
  }
  return rows[0]?.item_key || "";
}

function hydrateMappingPreviewItemIndex(index) {
  mappingPreviewItemIndexHydrating.value = true;
  mappingPreviewItemIndex.value = Number.isFinite(Number(index)) ? Number(index) : null;
  Promise.resolve().then(() => {
    mappingPreviewItemIndexHydrating.value = false;
  });
}

function hydrateMappingPreviewItemKey(itemKey) {
  mappingPreviewItemIndexHydrating.value = true;
  mappingPreviewItemKey.value = normalizeMappingPreviewItemKey(itemKey);
  Promise.resolve().then(() => {
    mappingPreviewItemIndexHydrating.value = false;
  });
}

const mappingIntegrationFieldOptions = computed(() => {
  const previewItem = mappingIntegrationPreview.value?.preview_item;
  const optionsByPath = new Map();
  buildIntegrationMappingKeys(mappingIntegrationPreview.value, { leafOnly: true })
    .forEach((path) => {
      const value = deepGetValue(previewItem, path);
      const kind = inferFieldKind(path, value);
      optionsByPath.set(path, {
        path,
        kind,
        label: formatSourceOptionLabel(path, kind),
        required: false,
      });
    });

  const schemaFields = Array.isArray(mappingIntegrationSchema.value?.fields)
    ? mappingIntegrationSchema.value.fields
    : [];
  schemaFields.forEach((field) => {
    const path = String(field?.path || "").trim();
    if (!path) return;
    const kind = integrationSchemaFieldKind(field);
    if (!kind) return;
    optionsByPath.set(path, {
      ...(optionsByPath.get(path) || {}),
      path,
      kind,
      label: formatSourceOptionLabel(path, kind),
      required: Boolean(field?.required),
      collectsOptions: Boolean(field?.collect_options),
    });
  });

  return Array.from(optionsByPath.values())
    .sort((a, b) => a.path.localeCompare(b.path));
});

const mappingSharedBlogFieldOptions = computed(() =>
  BLOG_SHARED_SOURCE_FIELD_OPTIONS.map((entry) => {
    const path = String(entry.path || "").trim();
    const itemPath = path.startsWith("item.") ? path.slice(5) : path;
    const kind = String(entry.kind || "text");
    return {
      path,
      kind,
      label: formatSourceOptionLabel(itemPath, kind),
      required: false,
    };
  })
);

const mappingComponentSourceOptions = computed(() =>
  (mappingUsesSharedItems.value
    ? mappingSharedBlogFieldOptions.value
    : mappingIntegrationFieldOptions.value.map((entry) => ({
      ...entry,
      path: `integration.${entry.path}`,
    }))
  ).map((entry) => ({
    ...entry,
    value: entry.path,
  }))
);

const mappingSourceFieldOptions = computed(() => {
  if (mappingUsesSharedItems.value) {
    return mappingSharedBlogFieldOptions.value.map((entry) => ({
      path: entry.path,
      kind: entry.kind,
      label: `Shared Blog Items: ${entry.label}`,
      scope: PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS,
    }));
  }
  const integrationOptions = mappingIntegrationFieldOptions.value.map((entry) => ({
    path: `integration.${entry.path}`,
    kind: entry.kind,
    label: `Integration: ${entry.label}`,
    scope: "integration",
  }));
  return integrationOptions;
});

const mappingSourceFieldKinds = computed(() => {
  const kinds = new Map();
  mappingSourceFieldOptions.value.forEach((entry) => {
    kinds.set(entry.path, entry.kind);
  });
  return kinds;
});

const mappingIntegrationFieldPathSet = computed(
  () => new Set(mappingIntegrationFieldOptions.value.map((entry) => entry.path))
);

const mappingSharedBlogFieldPathSet = computed(
  () => new Set(mappingSharedBlogFieldOptions.value.map((entry) => entry.path))
);

function collectScopedOptionsForNode(node, optionsMap) {
  if (!node || typeof node !== "object") return;
  Object.entries(node).forEach(([key, value]) => {
    collectScalarTargetOptions(value, key, optionsMap);
  });
}

function buildHeaderMappingTargetSnapshot(header) {
  const source = header && typeof header === "object" && !Array.isArray(header)
    ? header
    : {};
  const title = source.hero_title && typeof source.hero_title === "object"
    ? source.hero_title
    : {};
  const subtitle = source.hero_subtitle && typeof source.hero_subtitle === "object"
    ? source.hero_subtitle
    : {};
  return {
    background_media_url: source.background_media_url || "",
    background_zoom: source.background_zoom ?? 1,
    background_focal_x: source.background_focal_x ?? 50,
    background_focal_y: source.background_focal_y ?? 50,
    background_rotation: source.background_rotation ?? 0,
    overlay_image_url: source.overlay_image_url || "",
    overlay_zoom: source.overlay_zoom ?? 1,
    overlay_focal_x: source.overlay_focal_x ?? 50,
    overlay_focal_y: source.overlay_focal_y ?? 50,
    overlay_rotation: source.overlay_rotation ?? 0,
    hero_title: {
      de: title.de || "",
      en: title.en || "",
    },
    hero_subtitle: {
      de: subtitle.de || "",
      en: subtitle.en || "",
    },
    cta_buttons: Array.isArray(source.cta_buttons) ? source.cta_buttons : [],
  };
}

function escapeRegExp(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeTargetPatternPath(value) {
  return String(value || "").trim().toLowerCase().replace(/[_-]/g, "");
}

function targetPathMatchesPattern(path, pattern) {
  const normalizedPath = normalizeTargetPatternPath(path);
  const normalizedPattern = normalizeTargetPatternPath(pattern);
  if (!normalizedPath || !normalizedPattern) return false;
  const regexSource = escapeRegExp(normalizedPattern)
    .replace(/\\\[\\\*\\\]/g, "\\[[^\\]]+\\]")
    .replace(/\\\*/g, "[^.\\[]+");
  return new RegExp(`^${regexSource}$`).test(normalizedPath);
}

function filterFrontendTargetOptions(options, patterns = []) {
  const targetPatterns = Array.isArray(patterns) ? patterns : [];
  if (!targetPatterns.length) return [];
  return (Array.isArray(options) ? options : []).filter((option) => {
    const path = String(option?.path || "").trim();
    return path && targetPatterns.some((pattern) => targetPathMatchesPattern(path, pattern));
  });
}

function sectionFrontendTargetPatterns(sectionType) {
  const normalizedSectionType = normalizeSectionType(sectionType, "text");
  return PAGE_TEMPLATE_FRONTEND_SECTION_TARGET_PATTERNS_BY_TYPE[normalizedSectionType]
    || PAGE_TEMPLATE_FRONTEND_SECTION_TARGET_PATTERNS_BY_TYPE.text;
}

function resolvePathCandidate(source, pathParts) {
  if (!source || typeof source !== "object" || !Array.isArray(pathParts)) return null;
  let current = source;
  for (const pathPart of pathParts) {
    if (!current || typeof current !== "object" || !(pathPart in current)) return null;
    current = current[pathPart];
  }
  return current && typeof current === "object" && !Array.isArray(current)
    ? current
    : null;
}

function resolveNestedMappingPayload(templateDoc, sourceConfig) {
  const rawDoc = templateDoc && typeof templateDoc === "object" ? templateDoc : {};
  const camelDoc = convertKeysToCamel(rawDoc);
  for (const pathParts of sourceConfig.paths || []) {
    const rawMatch = resolvePathCandidate(rawDoc, pathParts);
    if (rawMatch) return rawMatch;
    const camelMatch = resolvePathCandidate(camelDoc, pathParts);
    if (camelMatch) return camelMatch;
  }
  return null;
}

function normalizeSectionMappingDisplayRows(rawRows, collectionPath = "") {
  const rows = [];
  (Array.isArray(rawRows) ? rawRows : []).forEach((row) => {
    const sourceRow = row && typeof row === "object" && !Array.isArray(row)
      ? convertKeysToCamel(row)
      : {};
    const sourcePath = String(sourceRow.sourcePath || "").trim();
    const targetPath = String(sourceRow.targetPath || "").trim();
    if (!sourcePath || !targetPath) return;
    rows.push({
      sourceLabel: formatSourcePathLabel(sourcePath),
      targetLabel: collectionPath
        ? `${formatHierarchicalPathLabel(collectionPath)} > ${formatHierarchicalPathLabel(targetPath)}`
        : formatHierarchicalPathLabel(targetPath),
    });
  });
  return rows;
}

function normalizeSectionMappingPayloadForDisplay(rawMapping) {
  if (!rawMapping || typeof rawMapping !== "object" || Array.isArray(rawMapping)) {
    return { selectedIntegrationId: "", rows: [] };
  }
  const mappingPayload = convertKeysToCamel(rawMapping);
  const rows = [
    ...normalizeSectionMappingDisplayRows(mappingPayload.scalarMappings),
  ];
  const rawListMap = mappingPayload.listMappingsByCollectionPath;
  if (rawListMap && typeof rawListMap === "object" && !Array.isArray(rawListMap)) {
    Object.entries(rawListMap).forEach(([collectionPath, listRows]) => {
      rows.push(...normalizeSectionMappingDisplayRows(listRows, String(collectionPath || "").trim()));
    });
  }
  return {
    selectedIntegrationId: String(mappingPayload.selectedIntegrationId || "").trim(),
    rows,
  };
}

function resolveIntegrationDisplayLabel(integrationId, fallbackLabel = "Section import") {
  const normalizedId = String(integrationId || "").trim();
  if (!normalizedId) return fallbackLabel;
  const integration = mappingIntegrationById.value.get(normalizedId);
  const name = String(integration?.name || "").trim();
  return name || normalizedId || fallbackLabel;
}

function inheritedMappingSourcesForActivePage() {
  const sourceContext = inferItemPageTemplateSourceContext(
    currentPageTemplateDoc.value || activePageTemplateListEntry.value || {}
  );
  if (!sourceContext) return INHERITED_SECTION_MAPPING_SOURCES;
  if (sourceContext.sourceType === "blog") {
    return INHERITED_SECTION_MAPPING_SOURCES.filter((source) => source.key === "section_integration_mapping");
  }
  if (sourceContext.sourceType === "program" && sourceContext.sourceKind === "stage") {
    return [];
  }
  if (sourceContext.sourceType === "program" && sourceContext.sourceKind === "gig") {
    return [];
  }
  return INHERITED_SECTION_MAPPING_SOURCES;
}

const sectionTemplateIndex = computed(() => {
  const index = new Map();
  (Array.isArray(sectionTemplates.value) ? sectionTemplates.value : []).forEach((template) => {
    const sectionType = normalizeSectionType(template?.section_type, "text");
    const templateName = normalizeTemplateName(template?.template_name || "default", "default");
    index.set(`${sectionType}/${templateName}`, template);
  });
  return index;
});

const mappingTargetGroups = computed(() => {
  const doc = currentPageTemplateDoc.value;
  if (!doc || typeof doc !== "object") return [];
  const groups = [];

  const pageOptionsMap = new Map();
  const pageSnapshot = {
    slug: String(doc.slug || "").trim(),
    title: doc.title && typeof doc.title === "object" ? doc.title : { de: "", en: "" },
    status: "hidden",
    in_menu: Boolean(doc.in_menu),
    hide_in_admin_sitemap: Boolean(doc.hide_in_admin_sitemap),
    hide_from_sitemap: Boolean(doc.hide_from_sitemap),
    hide_subtree_from_sitemap: Boolean(doc.hide_subtree_from_sitemap),
    sitemap_priority: doc.sitemap_priority ?? null,
    sitemap_changefreq: doc.sitemap_changefreq ?? null,
    menu_title: doc.menu_title && typeof doc.menu_title === "object" ? doc.menu_title : { de: "", en: "" },
    menu_order: Number(doc.menu_order || 0),
    redirect_to: String(doc.redirect_to || "").trim(),
    section_bg_pinned_start_key: String(doc.section_bg_pinned_start_key || ""),
    section_bg_pinned_end_key: String(doc.section_bg_pinned_end_key || ""),
  };
  collectScopedOptionsForNode(pageSnapshot, pageOptionsMap);
  groups.push({
    path: "page",
    label: "Page",
    kind: "page",
    targetOptions: filterFrontendTargetOptions(
      Array.from(pageOptionsMap.values()),
      PAGE_TEMPLATE_FRONTEND_PAGE_TARGET_PATTERNS,
    ).sort((a, b) => a.path.localeCompare(b.path)),
  });

  if (doc.header && typeof doc.header === "object") {
    const headerOptionsMap = new Map();
    collectScopedOptionsForNode(buildHeaderMappingTargetSnapshot(doc.header), headerOptionsMap);
    groups.push({
      path: "header",
      label: "Header",
      kind: "header",
      targetOptions: filterFrontendTargetOptions(
        Array.from(headerOptionsMap.values()),
        PAGE_TEMPLATE_FRONTEND_HEADER_TARGET_PATTERNS,
      ).sort((a, b) => a.path.localeCompare(b.path)),
    });
  }

  const sections = Array.isArray(doc.sections) ? doc.sections : [];
  sections.forEach((section, sectionIndex) => {
    if (!section || typeof section !== "object") return;
    const sectionType = normalizeSectionType(section.section_type || "text", "text");
    const embeddedSectionId = templateEmbeddedSectionId(section);
    const sectionCollectionPath = embeddedSectionId
      ? composePageMappingSectionCollectionPath(embeddedSectionId)
      : composePageMappingSectionCollectionPath(sectionIndex);
    const sectionTemplateName = normalizeTemplateName(section.section_template_name || "default", "default");
    const sectionTemplateDoc = sectionTemplateIndex.value.get(`${sectionType}/${sectionTemplateName}`) || null;
    const outputSource = sectionTemplateDoc || section;
    const sectionOutput = effectiveSectionOutputFieldOptions(
      outputSource,
      sectionTemplateDoc?.section_output_mapping || null,
    );
    const linksSocialContext = sectionOutput.linksSocialContext || buildLinksSocialPlatformContext(section);
    const sectionTargetOptions = Array.isArray(sectionOutput.targetOptions)
      ? sectionOutput.targetOptions
      : [];
    const sectionHiddenInTemplate = isTemplateSectionHiddenForListMapping(section);
    groups.push({
      path: sectionCollectionPath,
      indexPath: `sections[${sectionIndex}]`,
      label: `Section ${sectionIndex + 1}: ${formatTypeName(section.section_type || "section")}`,
      kind: "section",
      sectionIndex,
      templateSectionId: embeddedSectionId || "",
      sectionType,
      sectionTemplateName,
      hiddenInTemplate: sectionHiddenInTemplate,
      linksSocialContext,
      targetOptions: sectionTargetOptions,
    });
  });

  return groups;
});

function isTemplateSectionHiddenForListMapping(section) {
  if (!section || typeof section !== "object") return false;
  if (section.visible === false) return true;
  const deviceVisibility = section.device_visibility;
  if (!deviceVisibility || typeof deviceVisibility !== "object") return false;
  return ["mobile", "tablet", "desktop"].every((device) => deviceVisibility[device] === false);
}

const mappingTargetGroupByPath = computed(() => {
  const index = new Map();
  mappingTargetGroups.value.forEach((group) => {
    if (!group?.path) return;
    index.set(group.path, group);
  });
  return index;
});

function buildInheritedSectionMappingGroups(group) {
  if (!group || group.kind !== "section") return [];
  const ref = `${group.sectionType}/${group.sectionTemplateName}`;
  const templateDoc = sectionTemplateIndex.value.get(ref);
  if (!templateDoc || typeof templateDoc !== "object") return [];
  return inheritedMappingSourcesForActivePage()
    .map((sourceConfig) => {
      const rawMapping = resolveNestedMappingPayload(templateDoc, sourceConfig);
      const normalized = normalizeSectionMappingPayloadForDisplay(rawMapping);
      if (!normalized.rows.length) return null;
      return {
        key: sourceConfig.key,
        label: sourceConfig.label,
        integrationLabel: resolveIntegrationDisplayLabel(normalized.selectedIntegrationId, sourceConfig.label),
        sourceColumnLabel: "Source (section import)",
        targetColumnLabel: "Target (Section Template)",
        mappings: normalized.rows,
      };
    })
    .filter(Boolean);
}

function normalizeEditableHiddenTargetsForCollectionPath(collectionPath) {
  const normalizedCollectionPath = normalizePageMappingCollectionPath(collectionPath);
  if (!normalizedCollectionPath) return [];
  const hidden = mappingDraft.hiddenListTargetPathsByCollectionPath?.[normalizedCollectionPath];
  if (!Array.isArray(hidden)) return [];
  const next = [];
  const seen = new Set();
  hidden.forEach((path) => {
    const normalized = normalizePageTargetPathForCollection(normalizedCollectionPath, path);
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    next.push(normalized);
  });
  return next;
}

const hiddenTargetPathSetsByCollectionPath = computed(() => {
  const index = new Map();
  const rawMap = mappingDraft.hiddenListTargetPathsByCollectionPath;
  if (!rawMap || typeof rawMap !== "object" || Array.isArray(rawMap)) {
    return index;
  }
  Object.entries(rawMap).forEach(([collectionPath, hiddenPaths]) => {
    const normalizedCollectionPath = normalizePageMappingCollectionPath(collectionPath);
    if (!normalizedCollectionPath || !Array.isArray(hiddenPaths)) return;
    const targets = new Set();
    hiddenPaths.forEach((path) => {
      const normalized = normalizePageTargetPathForCollection(normalizedCollectionPath, path);
      if (normalized) targets.add(normalized);
    });
    if (targets.size) {
      index.set(normalizedCollectionPath, targets);
    }
  });
  return index;
});

function isTargetPathHiddenForGroup(group, targetPath) {
  if (group?.kind === "section") return false;
  const normalizedTargetPath = targetPathForGroupStorage(group, targetPath);
  if (!normalizedTargetPath) return false;
  const hiddenTargets = hiddenTargetPathSetsByCollectionPath.value.get(group.path);
  return Boolean(hiddenTargets?.has(normalizedTargetPath));
}

function groupHasTargetOption(group, targetPath) {
  const normalizedTargetPath = targetPathForGroupStorage(group, targetPath);
  if (!group || !normalizedTargetPath) return false;
  return (Array.isArray(group.targetOptions) ? group.targetOptions : []).some((option) =>
    targetPathForGroupStorage(group, option?.path) === normalizedTargetPath
  );
}

function outputTargetOptionsForGroup(group, sourcePath, currentTargetPath = "") {
  const normalizedSourcePath = normalizeOutputMappingSourcePath(sourcePath);
  const sourceKind = mappingSourceFieldKinds.value.get(normalizedSourcePath) || "text";
  const allOptions = Array.isArray(group?.targetOptions) ? group.targetOptions : [];
  let options = allOptions.filter((entry) => compatibleKinds(sourceKind, entry.kind));
  if (!options.length) {
    options = [...allOptions];
  }

  const visibleOptions = options.filter((option) => !isTargetPathHiddenForGroup(group, option.path));
  const selectedPath = targetPathForGroupStorage(group, currentTargetPath);
  if (selectedPath && !visibleOptions.some((entry) => entry.path === selectedPath)) {
    const selectedOption = allOptions.find((entry) => entry.path === selectedPath);
    const optionKind = selectedOption?.kind || "text";
    const isKnownTarget = Boolean(selectedOption);
    const baseLabel = selectedOption?.label || `${formatPathLabel(selectedPath)} (${fieldKindLabel(optionKind)})`;
    visibleOptions.push({
      path: selectedPath,
      kind: optionKind,
      label: isKnownTarget
        ? isTargetPathHiddenForGroup(group, selectedPath) ? `${baseLabel} [Hidden]` : baseLabel
        : `${baseLabel} [Unavailable]`,
      disabled: !isKnownTarget,
    });
  }
  return visibleOptions;
}

function mappingTargetColumnLabelForGroup(group) {
  if (group?.kind === "section") return "Target (Section)";
  if (group?.kind === "header") return "Target (Header)";
  return "Target (Page)";
}

function mappingComponentTargetOptionsForGroup(group, sourcePath = "", currentTargetPath = "") {
  return outputTargetOptionsForGroup(group, sourcePath, currentTargetPath);
}

const groupedSectionTemplates = computed(() => {
  const grouped = new Map();
  for (const sectionType of sectionTypes.value) {
    grouped.set(String(sectionType), []);
  }
  for (const template of sectionTemplates.value) {
    const sectionType = String(template.section_type || "text");
    if (!grouped.has(sectionType)) {
      grouped.set(sectionType, []);
    }
    grouped.get(sectionType).push(template);
  }

  return Array.from(grouped.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([sectionType, templates]) => ({
      sectionType,
      templates: (() => {
        const normalized = [...templates].sort((a, b) => String(a.template_name || "").localeCompare(String(b.template_name || "")));
        if (!normalized.some((entry) => String(entry.template_name || "") === "default")) {
          normalized.unshift({
            section_type: sectionType,
            template_name: "default",
            id: `default-${sectionType}`,
          });
        }
        return normalized;
      })(),
    }));
});

const normalizedSectionTemplateSearchQuery = computed(() =>
  String(sectionTemplateSearchQuery.value || "").trim().toLowerCase()
);

function sectionTemplateNavigatorSearchText(group, template) {
  const rawSectionType = group?.sectionType ? group.sectionType : template?.section_type;
  const sectionType = String(rawSectionType || "").trim();
  const templateName = String(template?.template_name || "default").trim();
  return [
    sectionType,
    formatTypeName(sectionType),
    templateName,
    `${sectionType}/${templateName}`,
  ].join(" ").toLowerCase();
}

function compareSectionTemplateLinks(a, b) {
  return formatSectionTemplateLinkLabel(a).localeCompare(
    formatSectionTemplateLinkLabel(b),
    undefined,
    { sensitivity: "base" }
  );
}

const favoriteSectionTemplates = computed(() => {
  const seen = new Set();
  const rows = [];
  groupedSectionTemplates.value.forEach((group) => {
    group.templates.forEach((template) => {
      const key = sectionTemplateKey(template?.section_type, template?.template_name || "default");
      if (!isSectionTemplateFavorite(template) || seen.has(key)) return;
      seen.add(key);
      rows.push(template);
    });
  });
  return rows.sort(compareSectionTemplateLinks);
});

const filteredFavoriteSectionTemplates = computed(() => {
  const query = normalizedSectionTemplateSearchQuery.value;
  if (!query) return favoriteSectionTemplates.value;
  return favoriteSectionTemplates.value.filter((template) =>
    sectionTemplateNavigatorSearchText({ sectionType: template?.section_type }, template).includes(query)
  );
});

const filteredSectionTemplateNavigatorGroups = computed(() => {
  const query = normalizedSectionTemplateSearchQuery.value;
  return groupedSectionTemplates.value
    .map((group) => {
      const sectionType = String(group.sectionType || "").trim();
      const groupMatches = !query || [
        sectionType,
        formatTypeName(sectionType),
      ].join(" ").toLowerCase().includes(query);
      const templates = groupMatches
        ? group.templates
        : group.templates.filter((template) => sectionTemplateNavigatorSearchText(group, template).includes(query));
      return templates.length
        ? { ...group, templates }
        : null;
    })
    .filter(Boolean);
});

const filteredSectionTemplateNavigatorCount = computed(() =>
  filteredSectionTemplateNavigatorGroups.value.reduce((total, group) => total + group.templates.length, 0)
);

const groupedPageTemplates = computed(() => {
  const groups = PAGE_TEMPLATE_GROUPS.map((group) => ({
    ...group,
    itemPage: itemPageRowForGroup(group),
    templates: [],
  }));
  const staticGroup = groups.find((group) => group.key === "static") || groups[groups.length - 1];

  for (const template of pageTemplates.value) {
    const matchingGroup = groups.find((group) =>
      group.itemPage && templateMatchesItemPageType(template, group.itemPage)
    );
    (matchingGroup || staticGroup).templates.push(template);
  }

  return groups.map((group) => ({
    ...group,
    templates: [...group.templates].sort((a, b) =>
      templatePath(a).localeCompare(templatePath(b))
    ),
  }));
});

function templatePath(template) {
  if (template?.path) return String(template.path);
  const templateName = normalizeTemplateName(template?.template_name || "default");
  const parentRoute = normalizeParentRoute(template?.parent_route);
  return composePageTemplatePath(templateName, parentRoute);
}

function refreshSectionRenameDrafts() {
  const next = {};
  for (const sectionType of sectionTypes.value) {
    next[sectionTemplateKey(sectionType, "default")] = "default";
  }
  for (const template of sectionTemplates.value) {
    const key = sectionTemplateKey(template?.section_type, template?.template_name || "default");
    next[key] = normalizeTemplateName(template?.template_name || "default", "default");
  }
  resetDraftMap(sectionRenameDrafts, next);
}

function refreshContainerRenameDrafts() {
  const next = {};
  for (const template of containerTemplates.value) {
    const name = normalizeTemplateName(template?.template_name, "container");
    next[name] = name;
  }
  resetDraftMap(containerRenameDrafts, next);
}

function refreshPageRenameDrafts() {
  const next = {};
  for (const template of pageTemplates.value) {
    const path = templatePath(template);
    const info = parsePageTemplatePath(path);
    if (!info.path) continue;
    next[info.path] = info.templateName;
  }
  resetDraftMap(pageRenameDrafts, next);
}

function resetSectionTemplateDraft(template) {
  const key = sectionTemplateKey(template?.section_type, template?.template_name || "default");
  sectionRenameDrafts[key] = normalizeTemplateName(template?.template_name || "default", "default");
}

function resetContainerTemplateDraft(templateName) {
  const normalized = normalizeTemplateName(templateName, "container");
  containerRenameDrafts[normalized] = normalized;
}

function resetPageTemplateDraft(template) {
  const path = templatePath(template);
  const info = parsePageTemplatePath(path);
  if (info.path) {
    pageRenameDrafts[info.path] = info.templateName;
  }
}

async function loadSectionTypes() {
  try {
    const response = await api.getSectionTypes();
    sectionTypes.value = normalizeVisibleSectionTemplateTypes(
      (response?.types || []).map((entry) => entry?.type)
    );
    if (!sectionTypes.value.length) {
      sectionTypes.value = [...DEFAULT_SECTION_TEMPLATE_TYPES];
    }
  } catch {
    sectionTypes.value = [...DEFAULT_SECTION_TEMPLATE_TYPES];
  }
  sectionTypes.value.forEach((sectionType) => ensureSectionCreateDraft(sectionType));
  refreshSectionRenameDrafts();
}

async function loadSectionTemplates() {
  const response = await api.listSectionTemplates();
  const rawTemplates = Array.isArray(response?.templates) ? response.templates : [];
  sectionTemplates.value = rawTemplates.filter((template) => {
    const sectionType = normalizeSectionType(template?.section_type, "text");
    return !HIDDEN_SECTION_TEMPLATE_TYPES.has(sectionType);
  });
  refreshSectionRenameDrafts();
}

async function loadContainerTemplates() {
  const response = await api.listContainerTemplates();
  containerTemplates.value = Array.isArray(response?.templates) ? response.templates : [];
  refreshContainerRenameDrafts();
}

async function loadPageTemplates() {
  const response = await api.listPageTemplates();
  pageTemplates.value = Array.isArray(response?.templates) ? response.templates : [];
  refreshPageRenameDrafts();
}

async function loadItemPageSourceRoutes() {
  try {
    const response = await api.listItemPageSourceRoutes();
    itemPageSourceRoutes.value = Array.isArray(response?.routes) ? response.routes : [];
  } catch (err) {
    console.error("Failed to load item-page source routes:", err);
    itemPageSourceRoutes.value = [];
  }
}

async function loadGlobalItemPageConfig() {
  try {
    globalItemPageConfig.value = await api.getGlobalItemPageConfig();
  } catch (err) {
    console.error("Failed to load global item-page config:", err);
    globalItemPageConfig.value = {};
  }
}

async function loadActiveTabData() {
  if (activeTab.value === "sections") {
    await Promise.all([loadSectionTypes(), loadSectionTemplates()]);
    return;
  }
  if (activeTab.value === "containers") {
    await loadContainerTemplates();
    return;
  }
  await Promise.all([
    loadPageTemplates(),
    loadSectionTemplates(),
    loadGlobalItemPageConfig(),
  ]);
}

function openSectionTemplate(sectionType, templateName = "default") {
  const type = normalizeSectionType(sectionType, "text");
  const name = normalizeTemplateName(templateName, "default");
  if (name === "default") {
    router.push(`/admin/templates/sections/${type}`);
    return;
  }
  router.push(`/admin/templates/sections/${type}/${name}`);
}

function openSectionTemplateOutput(sectionType, templateName = "default") {
  const type = normalizeSectionType(sectionType, "");
  const name = normalizeTemplateName(templateName, "default");
  if (!type) return;
  router.push({
    path: `/admin/templates/sections/${type}/${name}`,
    query: { sectionEditorTab: "output" },
  });
}

function updateSectionTemplateListEntry(updatedTemplate) {
  if (!updatedTemplate || typeof updatedTemplate !== "object") return;
  const updatedKey = sectionTemplateKey(updatedTemplate.section_type, updatedTemplate.template_name || "default");
  const index = sectionTemplates.value.findIndex((template) =>
    sectionTemplateKey(template?.section_type, template?.template_name || "default") === updatedKey
  );
  if (index >= 0) {
    sectionTemplates.value.splice(index, 1, {
      ...sectionTemplates.value[index],
      ...updatedTemplate,
    });
    return;
  }
  sectionTemplates.value.push(updatedTemplate);
}

async function toggleSectionTemplateFavorite(template) {
  const sectionType = normalizeSectionType(template?.section_type, "");
  const templateName = normalizeTemplateName(template?.template_name || "default", "default");
  if (!sectionType || !templateName) return;

  const savingKey = sectionTemplateKey(sectionType, templateName);
  if (sectionTemplateFavoriteSaving[savingKey]) return;

  const nextFavorite = !isSectionTemplateFavorite(template);
  sectionTemplateFavoriteSaving[savingKey] = true;
  try {
    const updated = await api.updateSectionTemplateMetadata(sectionType, templateName, {
      favorite: nextFavorite,
    });
    updateSectionTemplateListEntry(updated || { ...template, favorite: nextFavorite });
  } catch (err) {
    window.alert(`Failed to update favorite state: ${err?.message || "Unknown error"}`);
  } finally {
    delete sectionTemplateFavoriteSaving[savingKey];
  }
}

function scrollToSectionTemplateGroup(sectionType) {
  const normalizedSectionType = normalizeSectionType(sectionType, "");
  if (!normalizedSectionType) return;
  activeSectionNavigatorType.value = normalizedSectionType;
  const target = typeof document !== "undefined"
    ? document.getElementById(sectionTemplateGroupDomId(normalizedSectionType))
    : null;
  target?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function openContainerTemplate(templateName) {
  const name = normalizeTemplateName(templateName, "container");
  router.push(`/admin/templates/containers/${name}`);
}

function openPageTemplate(path) {
  const rawSegments = String(path || "").split("/").filter(Boolean);
  if (!rawSegments.length) {
    router.push("/admin/templates/pages");
    return;
  }
  const templateName = normalizeTemplateName(rawSegments[rawSegments.length - 1]);
  const parent = rawSegments
    .slice(0, -1)
    .map((segment) => normalizePathSegment(segment, ""))
    .filter(Boolean);
  const cleanPath = [...parent, templateName].join("/");
  router.push(`/admin/templates/pages/${cleanPath}`);
}

function canCreateSectionTemplate(sectionType) {
  const key = normalizeSectionType(sectionType, "");
  return Boolean(key && String(sectionCreateDrafts[key] || "").trim());
}

function canCreatePageTemplate(groupKey) {
  const group = pageTemplateGroupDefinition(groupKey);
  return Boolean(group?.key && String(pageCreateDrafts[group.key] || "").trim());
}

async function createSectionTemplate(sectionType) {
  const normalizedSectionType = normalizeSectionType(sectionType, "text");
  if (!canCreateSectionTemplate(normalizedSectionType)) return;
  const templateName = normalizeTemplateName(sectionCreateDrafts[normalizedSectionType], "template");
  const created = await api.createSectionTemplate({
    section_type: normalizedSectionType,
    template_name: templateName,
  });
  sectionCreateDrafts[normalizedSectionType] = "";
  await loadSectionTemplates();
  const createdSectionTypeRaw = String(created?.section_type ?? "").trim();
  const createdTemplateNameRaw = String(created?.template_name ?? "").trim();
  openSectionTemplate(
    createdSectionTypeRaw || normalizedSectionType,
    createdTemplateNameRaw || templateName,
  );
}

async function deleteSectionTemplate(template) {
  const sectionType = String(template?.section_type || "");
  const templateName = String(template?.template_name || "");
  if (!sectionType || !templateName || templateName === "default") return;
  if (!window.confirm(`Delete section template "${sectionType}/${templateName}"?`)) return;
  await api.deleteSectionTemplate(sectionType, templateName);
  await loadSectionTemplates();
}

async function duplicateSectionTemplate(
  sectionType,
  sourceTemplateName,
  targetTemplateName,
  { openAfter = true } = {}
) {
  const normalizedSectionType = normalizeSectionType(sectionType, "text");
  const sourceName = normalizeTemplateName(sourceTemplateName, "default");
  const targetName = normalizeTemplateName(targetTemplateName, "");
  if (!normalizedSectionType || !sourceName || !targetName) return;
  const created = await api.duplicateSectionTemplate(normalizedSectionType, sourceName, targetName);
  await loadSectionTemplates();
  if (openAfter) {
    openSectionTemplate(created?.section_type || normalizedSectionType, created?.template_name || targetName);
  }
}

async function promptDuplicateSectionTemplate(template) {
  const sectionType = normalizeSectionType(template?.section_type, "text");
  const sourceName = normalizeTemplateName(template?.template_name || "default", "default");
  if (!sectionType || !sourceName) return;
  const defaultName = normalizeTemplateName(`${sourceName}-copy`, "section-copy");
  const nextRaw = window.prompt(`Duplicate section template "${sectionType}/${sourceName}" as:`, defaultName);
  if (nextRaw === null) return;
  const targetName = normalizeTemplateName(nextRaw, "");
  if (!targetName || targetName === "default") {
    window.alert("Please enter a valid non-default section template name.");
    return;
  }
  try {
    await duplicateSectionTemplate(sectionType, sourceName, targetName, { openAfter: true });
  } catch (err) {
    window.alert(err?.message || "Failed to duplicate section template");
  }
}

async function renameSectionTemplate(
  sectionType,
  sourceTemplateName,
  targetTemplateName,
  { openAfter = false } = {}
) {
  const normalizedSectionType = normalizeSectionType(sectionType, "text");
  const sourceName = normalizeTemplateName(sourceTemplateName, "default");
  const targetName = normalizeTemplateName(targetTemplateName, sourceName);
  if (!sourceName || sourceName === "default") return;
  if (!targetName || targetName === sourceName) return;
  const updated = await api.renameSectionTemplate(normalizedSectionType, sourceName, targetName);
  await loadSectionTemplates();
  if (openAfter) {
    openSectionTemplate(updated?.section_type || normalizedSectionType, updated?.template_name || targetName);
  }
}

async function submitSectionTemplateRename(template) {
  const sectionType = normalizeSectionType(template?.section_type, "text");
  const sourceName = normalizeTemplateName(template?.template_name || "default", "default");
  if (sourceName === "default") return;

  const key = sectionTemplateKey(sectionType, sourceName);
  const targetName = normalizeTemplateName(sectionRenameDrafts[key], sourceName);
  sectionRenameDrafts[key] = targetName;
  if (targetName === sourceName) return;

  sectionRenaming[key] = true;
  try {
    const openAfter = builderContext.value?.kind === "section"
      && sectionTypeParam.value === sectionType
      && sectionTemplateNameParam.value === sourceName;
    await renameSectionTemplate(sectionType, sourceName, targetName, { openAfter });
  } catch (err) {
    sectionRenameDrafts[key] = sourceName;
    window.alert(err?.message || "Failed to rename section template");
  } finally {
    delete sectionRenaming[key];
  }
}

async function createContainerTemplate() {
  if (!canCreateContainerTemplate.value) return;
  const templateName = normalizeTemplateName(containerCreateName.value, "container");
  const created = await api.createContainerTemplate({ template_name: templateName });
  containerCreateName.value = "";
  await loadContainerTemplates();
  const createdTemplateNameRaw = String(created?.template_name ?? "").trim();
  openContainerTemplate(createdTemplateNameRaw || templateName);
}

async function deleteContainerTemplate(template) {
  const templateName = String(template?.template_name || "");
  if (!templateName) return;
  if (!window.confirm(`Delete container template "${templateName}"?`)) return;
  await api.deleteContainerTemplate(templateName);
  await loadContainerTemplates();
}

async function renameContainerTemplate(sourceTemplateName, targetTemplateName, { openAfter = false } = {}) {
  const sourceName = normalizeTemplateName(sourceTemplateName, "container");
  const targetName = normalizeTemplateName(targetTemplateName, "");
  if (!sourceName || !targetName || sourceName === targetName) return;
  const updated = await api.renameContainerTemplate(sourceName, targetName);
  await loadContainerTemplates();
  if (openAfter) {
    openContainerTemplate(updated?.template_name || targetName);
  }
}

async function submitContainerTemplateRename(templateName) {
  const sourceName = normalizeTemplateName(templateName, "container");
  const targetName = normalizeTemplateName(containerRenameDrafts[sourceName], sourceName);
  containerRenameDrafts[sourceName] = targetName;
  if (!sourceName || !targetName || sourceName === targetName) return;

  containerRenaming[sourceName] = true;
  try {
    await renameContainerTemplate(sourceName, targetName, {
      openAfter: builderContext.value?.kind === "container" && containerTemplateNameParam.value === sourceName,
    });
  } catch (err) {
    containerRenameDrafts[sourceName] = sourceName;
    window.alert(err?.message || "Failed to rename container template");
  } finally {
    delete containerRenaming[sourceName];
  }
}

async function duplicateContainerTemplate(sourceTemplateName, targetTemplateName, { openAfter = true } = {}) {
  const sourceName = normalizeTemplateName(sourceTemplateName, "container");
  const targetName = normalizeTemplateName(targetTemplateName, "");
  if (!sourceName || !targetName) return;
  const created = await api.duplicateContainerTemplate(sourceName, targetName);
  await loadContainerTemplates();
  if (openAfter) {
    openContainerTemplate(created?.template_name || targetName);
  }
}

async function promptRenameContainerTemplate(templateName) {
  const sourceName = normalizeTemplateName(templateName, "container");
  if (!sourceName) return;
  const nextRaw = window.prompt("Rename container template to:", sourceName);
  if (nextRaw === null) return;
  const targetName = normalizeTemplateName(nextRaw, "");
  if (!targetName) {
    window.alert("Please enter a valid container template name.");
    return;
  }
  if (targetName === sourceName) return;
  try {
    await renameContainerTemplate(sourceName, targetName, { openAfter: containerTemplateNameParam.value === sourceName });
  } catch (err) {
    window.alert(err?.message || "Failed to rename container template");
  }
}

async function promptDuplicateContainerTemplate(templateName) {
  const sourceName = normalizeTemplateName(templateName, "container");
  if (!sourceName) return;
  const defaultName = normalizeTemplateName(`${sourceName}-copy`, "container-copy");
  const nextRaw = window.prompt("Duplicate container template as:", defaultName);
  if (nextRaw === null) return;
  const targetName = normalizeTemplateName(nextRaw, "");
  if (!targetName) {
    window.alert("Please enter a valid container template name.");
    return;
  }
  try {
    await duplicateContainerTemplate(sourceName, targetName, { openAfter: true });
  } catch (err) {
    window.alert(err?.message || "Failed to duplicate container template");
  }
}

async function promptRenameActiveContainerTemplate() {
  const currentName = containerTemplateNameParam.value;
  if (!currentName) return;
  await promptRenameContainerTemplate(currentName);
}

async function promptDuplicateActiveContainerTemplate() {
  const currentName = containerTemplateNameParam.value;
  if (!currentName) return;
  await promptDuplicateContainerTemplate(currentName);
}

async function createPageTemplate(groupKey) {
  const group = pageTemplateGroupDefinition(groupKey);
  if (!canCreatePageTemplate(group.key)) return;
  const templateName = normalizeTemplateName(pageCreateDrafts[group.key], "template");
  const createContext = parsePageCreateTemplateType(group.createType);
  const isItemPage = Boolean(createContext.isItemPage);
  const resolvedSourceType = createContext.sourceType;
  const resolvedSourceKind = createContext.sourceKind;
  const resolvedSectionTemplateRef = normalizeSectionTemplateRef(
    `${resolvedSourceType}/default`,
    `${resolvedSourceType}/default`,
  );
  const payload = isItemPage
    ? {
      path: composePageTemplatePath(templateName, null),
      template_name: templateName,
      template_kind: "item_page",
      source_type: resolvedSourceType,
      source_kind: resolvedSourceKind,
      section_template_ref: resolvedSectionTemplateRef,
    }
    : {
      template_name: templateName,
      template_kind: "static_page",
    };

  const created = await api.createPageTemplate(payload);
  pageCreateDrafts[group.key] = "";
  await loadPageTemplates();
  openPageTemplate(
    created.path
    || composePageTemplatePath(templateName, null)
  );
}

async function renamePageTemplate(path, targetTemplateName, { openAfter = false } = {}) {
  const sourceInfo = parsePageTemplatePath(path);
  if (!sourceInfo.path || !sourceInfo.templateName) return;
  const targetName = normalizeTemplateName(targetTemplateName, sourceInfo.templateName);
  if (targetName === sourceInfo.templateName) return;

  const updated = await api.renamePageTemplate(sourceInfo.path, targetName);
  await loadPageTemplates();
  if (openAfter) {
    openPageTemplate(updated?.path || composePageTemplatePath(targetName, sourceInfo.parentRoute));
  }
}

async function duplicatePageTemplate(path, targetTemplateName, { openAfter = true } = {}) {
  const sourceInfo = parsePageTemplatePath(path);
  if (!sourceInfo.path || !sourceInfo.templateName) return;
  const targetName = normalizeTemplateName(targetTemplateName, "");
  if (!targetName) return;
  const created = await api.duplicatePageTemplate(sourceInfo.path, targetName);
  await loadPageTemplates();
  if (openAfter) {
    openPageTemplate(created?.path || composePageTemplatePath(targetName, sourceInfo.parentRoute));
  }
}

async function promptDuplicatePageTemplate(template) {
  const path = templatePath(template);
  const sourceInfo = parsePageTemplatePath(path);
  if (!sourceInfo.path || !sourceInfo.templateName) return;
  const defaultName = normalizeTemplateName(`${sourceInfo.templateName}-copy`, "page-copy");
  const nextRaw = window.prompt(`Duplicate page template "${sourceInfo.path}" as:`, defaultName);
  if (nextRaw === null) return;
  const targetName = normalizeTemplateName(nextRaw, "");
  if (!targetName) {
    window.alert("Please enter a valid page template name.");
    return;
  }
  try {
    await duplicatePageTemplate(sourceInfo.path, targetName, { openAfter: true });
  } catch (err) {
    window.alert(err?.message || "Failed to duplicate page template");
  }
}

async function submitPageTemplateRename(template) {
  const path = templatePath(template);
  const sourceInfo = parsePageTemplatePath(path);
  if (!sourceInfo.path || !sourceInfo.templateName) return;

  const key = sourceInfo.path;
  const targetName = normalizeTemplateName(pageRenameDrafts[key], sourceInfo.templateName);
  pageRenameDrafts[key] = targetName;
  if (targetName === sourceInfo.templateName) return;

  pageRenaming[key] = true;
  try {
    await renamePageTemplate(sourceInfo.path, targetName, {
      openAfter: builderContext.value?.kind === "page" && pageTemplateInfo.value.path === sourceInfo.path,
    });
  } catch (err) {
    pageRenameDrafts[key] = sourceInfo.templateName;
    window.alert(err?.message || "Failed to rename page template");
  } finally {
    delete pageRenaming[key];
  }
}

async function deletePageTemplate(template) {
  const path = templatePath(template);
  if (!path) return;
  if (!window.confirm(`Delete page template "${path}"?`)) return;
  await api.deletePageTemplate(path);
  await loadPageTemplates();
}

function normalizeDraftListMappingsByCollectionPath(groups = mappingTargetGroups.value) {
  const sourceProvider = mappingSourceProvider.value;
  const migratedRowsByCollectionPath = normalizePageListMappingsByCollectionPath(
    mappingDraft.listMappingsByCollectionPath,
    groups,
    sourceProvider,
  );
  const normalized = {};
  (Array.isArray(groups) ? groups : []).forEach((group) => {
    const collectionPath = normalizePageMappingCollectionPath(group.path);
    if (!collectionPath) return;
    const existingRows = Array.isArray(migratedRowsByCollectionPath?.[collectionPath])
      ? migratedRowsByCollectionPath[collectionPath]
      : [];
    const normalizedRows = existingRows
      .map((row) => {
        const targetPath = targetPathForGroupStorageWithFallback(group, row?.target_path, collectionPath);
        const normalizedRow = {
          source_path: (
            isFixedGigMappingTargetPath(targetPath)
            && sourceProvider === PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
            && fixedGigMappingNeedsPrimaryKeyFallback(row?.source_path)
          )
            ? fixedGigMappingSourcePath() || normalizeOutputMappingSourcePath(row?.source_path, sourceProvider)
            : normalizeOutputMappingSourcePath(row?.source_path, sourceProvider),
          target_path: targetPath,
        };
        if (group.templateSectionId) {
          normalizedRow.template_section_id = group.templateSectionId;
        }
        return normalizedRow;
      })
      .filter((row) => row.source_path || row.target_path);
    normalized[collectionPath] = normalizedRows.length
      ? normalizedRows
      : [{ source_path: "", target_path: "" }];
  });
  mappingDraft.listMappingsByCollectionPath = normalized;
}

const pageListMappingGroups = computed(() =>
  mappingTargetGroups.value.map((group) => ({
    ...group,
    muted: group.kind === "section" && group.hiddenInTemplate === true,
    mappings: Array.isArray(mappingDraft.listMappingsByCollectionPath?.[group.path])
      ? mappingDraft.listMappingsByCollectionPath[group.path]
      : [{ source_path: "", target_path: "" }],
    inheritedMappingGroups: buildInheritedSectionMappingGroups(group),
  }))
);

const editableVisibilityGroups = computed(() =>
  mappingTargetGroups.value
    .filter((group) => ["page", "header"].includes(group?.kind))
    .map((group) => {
      const hiddenTargets = hiddenTargetPathSetsByCollectionPath.value.get(group.path) || new Set();
      return {
        ...group,
        options: (Array.isArray(group.targetOptions) ? group.targetOptions : [])
          .map((option) => {
            const targetPath = targetPathForGroupStorage(group, option.path);
            const defaultHidden = isDefaultHiddenTargetForVisibilityGroup(group, option.path);
            return {
              ...option,
              hidden: Boolean(targetPath && hiddenTargets.has(targetPath)),
              defaultHidden,
            };
          })
          .filter((option) => showDefaultHiddenVisibilityTargets.value || !option.defaultHidden)
          .sort((a, b) => {
            if (a.defaultHidden !== b.defaultHidden) return a.defaultHidden ? 1 : -1;
            return String(a.label || a.path || "").localeCompare(String(b.label || b.path || ""));
          }),
      };
    })
    .filter((group) => group.options.length > 0)
);

const sectionOutputReferenceGroups = computed(() =>
  mappingTargetGroups.value
    .filter((group) => group?.kind === "section")
    .map((group) => {
      const templateDoc = sectionTemplateIndex.value.get(`${group.sectionType}/${group.sectionTemplateName}`);
      const outputMapping = normalizeSectionOutputMapping(
        templateDoc?.section_output_mapping || null,
      );
      return {
        ...group,
        outputFieldCount: Array.isArray(group.targetOptions) ? group.targetOptions.length : 0,
        outputModeLabel: outputMapping.mode === "custom" ? "Custom output" : "Default output",
      };
    })
);

function addListMappingRow(collectionPath, row = null) {
  const normalizedCollectionPath = normalizePageMappingCollectionPath(collectionPath);
  if (!normalizedCollectionPath) return;
  const existingRows = Array.isArray(mappingDraft.listMappingsByCollectionPath?.[normalizedCollectionPath])
    ? mappingDraft.listMappingsByCollectionPath[normalizedCollectionPath]
    : [];
  const nextRow = row && typeof row === "object" && !Array.isArray(row)
    ? {
        source_path: normalizeOutputMappingSourcePath(row.source_path, mappingSourceProvider.value),
        target_path: String(row.target_path || "").trim(),
      }
    : { source_path: "", target_path: "" };
  const rowsForAppend = nextRow.source_path && nextRow.target_path
    ? existingRows.filter((mapping) =>
        String(mapping?.source_path || "").trim()
        && String(mapping?.target_path || "").trim()
      )
    : existingRows;
  mappingDraft.listMappingsByCollectionPath = {
    ...(mappingDraft.listMappingsByCollectionPath || {}),
    [normalizedCollectionPath]: [
      ...rowsForAppend,
      nextRow,
    ],
  };
  handleMappingDraftChanged();
}

function handlePageListMappingAdd(payload) {
  addListMappingRow(payload?.groupPath, {
    source_path: payload?.source_path,
    target_path: payload?.target_path,
  });
}

function handlePageListMappingRemove(payload) {
  removeListMappingRow(payload?.groupPath, Number(payload?.index));
}

function removeListMappingRow(collectionPath, index) {
  const normalizedCollectionPath = normalizePageMappingCollectionPath(collectionPath);
  if (!normalizedCollectionPath) return;
  const existingRows = Array.isArray(mappingDraft.listMappingsByCollectionPath?.[normalizedCollectionPath])
    ? [...mappingDraft.listMappingsByCollectionPath[normalizedCollectionPath]]
    : [];
  if (index < 0 || index >= existingRows.length) return;
  existingRows.splice(index, 1);
  mappingDraft.listMappingsByCollectionPath = {
    ...(mappingDraft.listMappingsByCollectionPath || {}),
    [normalizedCollectionPath]: existingRows.length
      ? existingRows
      : [{ source_path: "", target_path: "" }],
  };
  handleMappingDraftChanged();
}

function setPageTemplateTargetPathHidden(collectionPath, targetPath, hidden = true) {
  const normalizedCollectionPath = normalizePageMappingCollectionPath(collectionPath);
  if (!normalizedCollectionPath) return;
  const normalizedTargetPath = normalizePageTargetPathForCollection(
    normalizedCollectionPath,
    targetPath,
  );
  if (!normalizedTargetPath) return;

  const rawCurrent = (
    mappingDraft.hiddenListTargetPathsByCollectionPath
    && typeof mappingDraft.hiddenListTargetPathsByCollectionPath === "object"
    && !Array.isArray(mappingDraft.hiddenListTargetPathsByCollectionPath)
  )
    ? mappingDraft.hiddenListTargetPathsByCollectionPath
    : {};
  const existingTargets = normalizeEditableHiddenTargetsForCollectionPath(normalizedCollectionPath);
  const nextTargets = existingTargets.filter((entry) => entry !== normalizedTargetPath);
  if (hidden) nextTargets.push(normalizedTargetPath);
  const targetGroup = mappingTargetGroupByPath.value.get(normalizedCollectionPath);
  const clearKey = defaultHiddenTargetClearKey(normalizedCollectionPath, normalizedTargetPath);
  if (!hidden && isDefaultHiddenTargetForVisibilityGroup(targetGroup, normalizedTargetPath)) {
    mappingDefaultHiddenTargetClears.value.add(clearKey);
  } else if (hidden) {
    mappingDefaultHiddenTargetClears.value.delete(clearKey);
  }
  const next = { ...rawCurrent };
  if (nextTargets.length > 0) {
    next[normalizedCollectionPath] = Array.from(new Set(nextTargets));
  } else {
    delete next[normalizedCollectionPath];
  }
  mappingDraft.hiddenListTargetPathsByCollectionPath = next;
  handleMappingDraftChanged();
}

function handleMappingDraftChanged() {
  nextTick(() => {
    queueMappingPreviewRefreshIfEnabled();
    queueMappingsAutosave();
  });
}

function jumpToSectionTemplate(sectionType, templateName = "default") {
  openSectionTemplate(sectionType, templateName || "default");
}

function clearMappingPreview() {
  clearMappingPreviewRefreshTimer();
  mappingPreviewDoc.value = null;
  mappingPreviewWarnings.value = [];
}

function enterMappingPreviewAdminState() {
  if (mappingPreviewAdminSnapshot.value) return;
  mappingPreviewAdminSnapshot.value = {
    isAdmin: Boolean(state.isAdmin),
    previewMode: Boolean(state.previewMode),
  };
  state.previewMode = true;
  state.isAdmin = false;
}

function exitMappingPreviewAdminState() {
  const snapshot = mappingPreviewAdminSnapshot.value;
  if (!snapshot) return;
  state.previewMode = Boolean(snapshot.previewMode);
  state.isAdmin = Boolean(snapshot.isAdmin);
  mappingPreviewAdminSnapshot.value = null;
}

function disableMappingPreview() {
  mappingPreviewEnabled.value = false;
  clearMappingPreview();
  exitMappingPreviewAdminState();
}

function clearMappingsAutosaveTimer() {
  if (mappingAutosaveTimerId.value != null) {
    clearTimeout(mappingAutosaveTimerId.value);
    mappingAutosaveTimerId.value = null;
  }
}

function clearMappingAutosaveStatusTimer() {
  if (mappingAutosaveStatusTimer) {
    clearTimeout(mappingAutosaveStatusTimer);
    mappingAutosaveStatusTimer = null;
  }
}

function clearMappingPreviewRefreshTimer() {
  if (mappingPreviewRefreshTimerId.value != null) {
    clearTimeout(mappingPreviewRefreshTimerId.value);
    mappingPreviewRefreshTimerId.value = null;
  }
}

function resetMappingsAutosaveState() {
  clearMappingsAutosaveTimer();
  clearMappingAutosaveStatusTimer();
  mappingAutosaveQueued.value = false;
  mappingAutosaveReady.value = false;
  mappingLastSavedSignature.value = "";
  mappingAutosaveStatus.value = "idle";
  mappingAutosaveError.value = "";
}

function buildMappingsPatchPayload() {
  const sourceProvider = mappingSourceProvider.value;
  const listMappingsByCollectionPath = normalizePageListMappingsByCollectionPath(
    mappingDraft.listMappingsByCollectionPath,
    mappingTargetGroups.value,
    sourceProvider,
  );
  const hiddenListTargetPathsByCollectionPath = normalizePageHiddenTargetPathsByCollectionPath(
    mappingDraft.hiddenListTargetPathsByCollectionPath
  );
  const integrationId = String(mappingDraft.primaryIntegrationId || "").trim();
  const sourceType = String(mappingSourceType.value || "blog").trim().toLowerCase();
  const sectionTemplateRef = normalizeSectionTemplateRef(
    mappingDraft.sectionTemplateRef,
    `${sourceType}/default`,
  );
  const pageMappingPayload = normalizePageIntegrationMappingPayload({
    active_mode: "list",
    source_provider: sourceProvider,
    selected_integration_id: mappingUsesIntegration.value ? integrationId || null : null,
    list_mappings_by_collection_path: listMappingsByCollectionPath,
    hidden_list_target_paths_by_collection_path: hiddenListTargetPathsByCollectionPath,
    preview_item_index: activePageIsItemPageTemplate.value
      ? null
      : normalizeMappingPreviewItemIndex(mappingPreviewItemIndex.value),
    preview_item_key: activePageIsItemPageTemplate.value
      ? normalizeMappingPreviewItemKey(mappingPreviewItemKey.value)
      : "",
  }, { sourceProvider });
  const payload = {
    page_integration_mapping: pageMappingPayload,
  };
  if (activePageIsItemPageTemplate.value) {
    payload.template_kind = "item_page";
    payload.source_type = sourceType;
    payload.source_kind = mappingSourceKind.value;
    payload.source_route_ref = "";
    payload.section_template_ref = sectionTemplateRef;
  }
  return payload;
}

function validateMappingsPatchPayload(payload) {
  const pageMapping = payload?.page_integration_mapping;
  const rowsByCollection = pageMapping?.list_mappings_by_collection_path;
  if (!rowsByCollection || typeof rowsByCollection !== "object" || Array.isArray(rowsByCollection)) {
    return [];
  }

  const errors = [];
  const sourceProvider = normalizeMappingSourceProvider(pageMapping?.source_provider)
    || mappingSourceProvider.value;
  const integrationId = sourceProvider === PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION
    ? String(pageMapping?.selected_integration_id || mappingDraft.primaryIntegrationId || "").trim()
    : "";
  const availableIntegrationPaths = mappingIntegrationFieldPathSet.value;
  const availableSharedPaths = mappingSharedBlogFieldPathSet.value;
  const primaryKeyPath = activePageMappingIntegrationPrimaryKeyPath.value;

  Object.entries(rowsByCollection).forEach(([collectionPath, rows]) => {
    if (!Array.isArray(rows)) return;
    rows.forEach((row, index) => {
      const sourcePath = normalizeOutputMappingSourcePath(row?.source_path, sourceProvider);
      const targetPath = String(row?.target_path || "").trim();
      if (!sourcePath && !targetPath) return;
      const label = `${collectionPath} #${index + 1}`;
      if (!sourcePath) {
        errors.push(`${label}: select a source field.`);
        return;
      }
      if (!targetPath) {
        errors.push(`${label}: select a target field.`);
        return;
      }
      if (sourceProvider === PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS) {
        if (!sourcePath.startsWith("item.")) {
          errors.push(`${label}: source "${sourcePath}" must be a shared blog item field.`);
          return;
        }
        if (!availableSharedPaths.has(sourcePath)) {
          errors.push(`${label}: shared blog item field "${sourcePath}" is not available.`);
        }
        return;
      }
      if (!integrationId) {
        errors.push(`${label}: select an integration before saving mapped fields.`);
        return;
      }
      if (!sourcePath.startsWith("integration.")) {
        errors.push(`${label}: source "${sourcePath}" must be an integration field.`);
        return;
      }
      const integrationPath = sourcePath.slice(12).trim();
      if (isFixedGigMappingTargetPath(targetPath)) {
        if (!isSupportedFixedGigSourcePath(sourcePath, primaryKeyPath)) {
          const primaryHint = primaryKeyPath ? `"${primaryKeyPath}" or ` : "";
          errors.push(`${label}: fixed gig mappings must use integration field ${primaryHint}a gig title field.`);
          return;
        }
      }
      if (!availableIntegrationPaths.has(integrationPath)) {
        errors.push(`${label}: integration field "${integrationPath}" is not available.`);
      }
    });
  });

  return errors;
}

function mappingPayloadSignature(payload) {
  try {
    return JSON.stringify(payload || {});
  } catch {
    return "";
  }
}

function markMappingsAutosaveBaseline() {
  if (!showPageMappingEditor.value) {
    resetMappingsAutosaveState();
    return;
  }
  const payload = buildMappingsPatchPayload();
  mappingLastSavedSignature.value = mappingPayloadSignature(payload);
  mappingAutosaveReady.value = true;
  mappingAutosaveQueued.value = false;
  clearMappingAutosaveStatusTimer();
  mappingAutosaveStatus.value = "idle";
  mappingAutosaveError.value = "";
}

async function persistMappingsPayload(payload, signature, { manual = false } = {}) {
  if (!showPageMappingEditor.value) return false;
  if (!signature) return false;

  const validationErrors = validateMappingsPatchPayload(payload);
  if (validationErrors.length) {
    mappingAutosaveStatus.value = "error";
    mappingAutosaveError.value = validationErrors.slice(0, 5).join("\n");
    if (manual) {
      window.alert(mappingAutosaveError.value);
    }
    return false;
  }

  if (savingMappings.value) {
    if (!manual) mappingAutosaveQueued.value = true;
    return false;
  }

  const shouldSkipBecauseUnchanged = signature === mappingLastSavedSignature.value;
  if (shouldSkipBecauseUnchanged) {
    if (mappingAutosaveStatus.value !== "error") {
      mappingAutosaveStatus.value = "saved";
    }
    return true;
  }

  savingMappings.value = true;
  mappingAutosaveStatus.value = "saving";
  mappingAutosaveError.value = "";
  try {
    await api.patchPageTemplate(pageTemplateInfo.value.path, payload);
    mappingLastSavedSignature.value = signature;
    mappingAutosaveReady.value = true;
    mappingAutosaveStatus.value = "saved";
    if (mappingPreviewEnabled.value) {
      await refreshMappingPreviewIfEnabled();
    }
    return true;
  } catch (err) {
    mappingAutosaveStatus.value = "error";
    mappingAutosaveError.value = err?.message || "Failed to save mapping";
    console.error("Failed to save template mappings:", err);
    if (manual) {
      window.alert(mappingAutosaveError.value);
    }
    return false;
  } finally {
    savingMappings.value = false;
    if (mappingAutosaveQueued.value) {
      mappingAutosaveQueued.value = false;
      void queueMappingsAutosave({ immediate: true });
    }
  }
}

function queueMappingsAutosave({ immediate = false, delayMs = 800 } = {}) {
  if (!showPageMappingEditor.value) return;
  if (loadingPageTemplateSettings.value) return;
  if (!mappingAutosaveReady.value) return;

  const runSave = () => {
    mappingAutosaveTimerId.value = null;
    const payload = buildMappingsPatchPayload();
    const signature = mappingPayloadSignature(payload);
    if (!signature || signature === mappingLastSavedSignature.value) return;
    void persistMappingsPayload(payload, signature, { manual: false });
  };

  clearMappingsAutosaveTimer();
  if (immediate) {
    runSave();
    return;
  }
  mappingAutosaveTimerId.value = setTimeout(runSave, delayMs);
}

async function loadMappingIntegrations() {
  if (!showPageMappingEditor.value) return;
  if (!mappingUsesIntegration.value) {
    mappingLoadingIntegrations.value = false;
    mappingAvailableIntegrations.value = [];
    mappingIntegrationsContext.value = {
      template_key: "",
      integration_visibility: "template_only",
      integrations_enabled: true,
      expected_return_type: "auto",
    };
    return;
  }
  mappingLoadingIntegrations.value = true;
  try {
    const response = await api.listIntegrationsForSection(mappingSourceType.value, {
      sectionId: null,
      itemPageTemplatePath: pageTemplateInfo.value.path || null,
    });
    mappingIntegrationsContext.value = {
      template_key: String(response?.context?.template_key || ""),
      integration_visibility: ["disabled", "template_only", "enabled"].includes(response?.context?.integration_visibility)
        ? response.context.integration_visibility
        : "template_only",
      integrations_enabled: response?.context?.integrations_enabled !== false,
      expected_return_type: ["auto", "list", "object"].includes(response?.context?.expected_return_type)
        ? response.context.expected_return_type
        : "auto",
    };
    mappingAvailableIntegrations.value = mappingIntegrationsContext.value.integrations_enabled
      ? (Array.isArray(response?.integrations) ? response.integrations : [])
      : [];
    if (!mappingIntegrationsContext.value.integrations_enabled) {
      mappingIntegrationPreview.value = null;
      mappingIntegrationSchema.value = null;
      mappingIntegrationSchemaError.value = "";
      mappingIntegrationSchemaLoading.value = false;
      mappingPreviewItemIndex.value = null;
      mappingPreviewItemKey.value = "";
      return;
    }
    const validIds = new Set(mappingAvailableIntegrations.value.map((entry) => String(entry?.id || "")));
    if (!validIds.has(String(mappingDraft.primaryIntegrationId || ""))) {
      mappingDraft.primaryIntegrationId = "";
      mappingIntegrationPreview.value = null;
      mappingIntegrationSchema.value = null;
      mappingIntegrationSchemaError.value = "";
      mappingIntegrationSchemaLoading.value = false;
      mappingPreviewItemIndex.value = null;
      mappingPreviewItemKey.value = "";
    }
  } catch (err) {
    console.error("Failed to load mapping integrations:", err);
    mappingAvailableIntegrations.value = [];
    mappingIntegrationsContext.value = {
      template_key: "",
      integration_visibility: "template_only",
      integrations_enabled: true,
      expected_return_type: "auto",
    };
    mappingIntegrationPreview.value = null;
    mappingIntegrationSchema.value = null;
    mappingIntegrationSchemaError.value = "";
    mappingIntegrationSchemaLoading.value = false;
    mappingPreviewItemIndex.value = null;
    mappingPreviewItemKey.value = "";
  } finally {
    mappingLoadingIntegrations.value = false;
  }
}

async function loadMappingIntegrationPreview() {
  if (!mappingUsesIntegration.value) {
    mappingIntegrationPreview.value = null;
    mappingPreviewItemIndex.value = null;
    return;
  }
  if (!mappingIntegrationsEnabled.value) {
    mappingIntegrationPreview.value = null;
    mappingPreviewItemIndex.value = null;
    mappingPreviewItemKey.value = "";
    return;
  }
  const integrationId = String(mappingDraft.primaryIntegrationId || "").trim();
  if (!integrationId) {
    mappingIntegrationPreview.value = null;
    mappingPreviewItemIndex.value = null;
    mappingPreviewItemKey.value = "";
    return;
  }
  try {
    const itemKey = activePageIsItemPageTemplate.value
      ? normalizeMappingPreviewItemKey(mappingPreviewItemKey.value)
      : "";
    if (activePageIsItemPageTemplate.value && !itemKey) {
      await loadMappingPreviewItemOptions();
    }
    const resolvedItemKey = activePageIsItemPageTemplate.value
      ? normalizeMappingPreviewItemKey(mappingPreviewItemKey.value)
      : "";
    if (activePageIsItemPageTemplate.value && !resolvedItemKey) {
      mappingIntegrationPreview.value = null;
      return;
    }
    const requestedIndex = Number(mappingPreviewItemIndex.value);
    const itemIndex = activePageIsItemPageTemplate.value
      ? null
      : Number.isFinite(requestedIndex)
        ? requestedIndex
        : null;
    const preview = await api.getIntegrationDataPreview(integrationId, {
      itemIndex,
      itemKey: resolvedItemKey,
    });
    mappingIntegrationPreview.value = preview;
    const selectedIndex = Number(preview?.selected_index);
    if (!activePageIsItemPageTemplate.value) {
      hydrateMappingPreviewItemIndex(Number.isFinite(selectedIndex) ? selectedIndex : null);
    }
  } catch (err) {
    console.error("Failed to load mapping integration preview:", err);
    mappingIntegrationPreview.value = null;
    mappingPreviewItemIndex.value = null;
    mappingPreviewItemKey.value = "";
    mappingPreviewItemIndexHydrating.value = false;
  }
}

async function loadMappingIntegrationSchema() {
  const integrationId = String(mappingDraft.primaryIntegrationId || "").trim();
  mappingIntegrationSchema.value = null;
  mappingIntegrationSchemaError.value = "";
  if (!mappingUsesIntegration.value || !integrationId) {
    mappingIntegrationSchemaLoading.value = false;
    return;
  }
  mappingIntegrationSchemaLoading.value = true;
  try {
    mappingIntegrationSchema.value = await api.getIntegrationSchema(integrationId);
  } catch (err) {
    console.error("Failed to load mapping integration schema:", err);
    mappingIntegrationSchema.value = null;
    mappingIntegrationSchemaError.value = err?.message || "Failed to load integration schema.";
  } finally {
    mappingIntegrationSchemaLoading.value = false;
  }
}

async function loadMappingPreviewItemOptions() {
  if (!showPageMappingEditor.value) {
    mappingItemPreviewOptions.value = [];
    return;
  }

  const requestId = mappingPreviewItemOptionsRequestId.value + 1;
  mappingPreviewItemOptionsRequestId.value = requestId;
  const integrationId = String(mappingDraft.primaryIntegrationId || "").trim();

  let nextOptions = [];
  let nextSelectedKey = "";
  const previewRoutePrefixes = mappingItemPreviewRoutePrefixes.value;
  try {
    if (activePageIsItemPageTemplate.value && mappingUsesSharedItems.value) {
      const response = await api.listBlogItems();
      const items = Array.isArray(response?.items) ? response.items : [];
      nextOptions = items
        .map((item, index) => {
          const itemKey = normalizeMappingPreviewItemKey(item?.id || item?._id);
          if (!itemKey) return null;
          const title = item?.title && typeof item.title === "object"
            ? String(item.title.de || item.title.en || "").trim()
            : "";
          const date = String(item?.date || "").trim();
          const label = [date, title || itemKey].filter(Boolean).join(" · ");
          return {
            index,
            item_key: itemKey,
            value: itemKey,
            label,
          };
        })
        .filter(Boolean);
      nextSelectedKey = resolvePreviewReviewItemKey(nextOptions);
    } else if (activePageIsItemPageTemplate.value && mappingUsesIntegration.value && integrationId) {
      const response = await api.listIntegrationReviewItems(integrationId);
      nextOptions = buildReviewPreviewOptionsFromItems(response?.items, {
        routePrefixes: previewRoutePrefixes,
      });
      nextSelectedKey = resolvePreviewReviewItemKey(nextOptions);
    }
  } catch (err) {
    console.error("Failed to load mapping preview item options:", err);
  } finally {
    if (mappingPreviewItemOptionsRequestId.value === requestId) {
      mappingItemPreviewOptions.value = nextOptions;
      if (activePageIsItemPageTemplate.value) {
        hydrateMappingPreviewItemKey(nextSelectedKey);
      }
    }
  }
}

function clearMappingProviderPreviewState() {
  mappingIntegrationPreview.value = null;
  mappingIntegrationSchema.value = null;
  mappingIntegrationSchemaError.value = "";
  mappingIntegrationSchemaLoading.value = false;
  mappingPreviewItemIndex.value = null;
  mappingPreviewItemKey.value = "";
  mappingItemPreviewOptions.value = [];
  clearMappingPreview();
}

function blankIncompatibleMappingSourcesForProvider(sourceProvider) {
  const provider = normalizeMappingSourceProvider(sourceProvider) || PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
  const next = {};
  Object.entries(mappingDraft.listMappingsByCollectionPath || {}).forEach(([collectionPath, rows]) => {
    const normalizedCollectionPath = normalizePageMappingCollectionPath(collectionPath);
    if (!normalizedCollectionPath || !Array.isArray(rows)) return;
    next[normalizedCollectionPath] = rows.map((row) => {
      const rawSourcePath = String(row?.source_path || "").trim();
      const incompatible = provider === PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS
        ? rawSourcePath.startsWith("integration.")
        : rawSourcePath.startsWith("item.");
      return {
        ...row,
        source_path: incompatible
          ? ""
          : normalizeOutputMappingSourcePath(rawSourcePath, provider),
        target_path: String(row?.target_path || "").trim(),
      };
    });
  });
  mappingDraft.listMappingsByCollectionPath = next;
}

function handleMappingSourceProviderChange() {
  if (!mappingSupportsSharedItemsProvider.value) {
    mappingDraft.sourceProvider = PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
    return;
  }
  mappingDraft.sourceProvider = normalizeMappingSourceProvider(mappingDraft.sourceProvider)
    || PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS;
}

function resolveSourceRouteRefForTemplate(template) {
  if (!isItemPageTemplateEntry(template)) return "";
  const explicitRef = normalizeSourceRouteRef(template?.source_route_ref || "");
  if (explicitRef && routeEntryByRef(explicitRef)) return explicitRef;

  const sourceType = String(template?.source_type || "").trim().toLowerCase();
  const sourceKind = String(template?.source_kind || "").trim().toLowerCase();
  const parentRoute = normalizeParentRoute(template?.parent_route || "");
  const candidates = normalizedSourceRoutes.value.filter((entry) => {
    if (sourceType && String(entry.source_type || "").trim().toLowerCase() !== sourceType) return false;
    if (parentRoute && String(entry.parent_route || "") !== parentRoute) return false;
    return true;
  });
  if (sourceKind) {
    const kindMatch = candidates.find(
      (entry) => String(entry.source_kind || "").trim().toLowerCase() === sourceKind
    );
    if (kindMatch) return String(kindMatch.source_route_ref || "");
  }
  if (candidates.length > 0) return String(candidates[0].source_route_ref || "");
  return "";
}

async function loadPageTemplateSettings() {
  disableMappingPreview();
  resetMappingsAutosaveState();
  mappingDefaultHiddenTargetClears.value = new Set();
  pageTemplateRegenerateStatus.value = { type: "", message: "" };
  templateRoutingStatus.value = { type: "", message: "" };
  loadingPageTemplateSettings.value = true;
  try {
    if (builderContext.value?.kind !== "page") {
      mappingDraft.sourceRouteRef = "";
      mappingDraft.sectionTemplateRef = normalizeSectionTemplateRef(
        "blog/default",
        "blog/default",
      );
      mappingDraft.sourceProvider = PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
      mappingDraft.primaryIntegrationId = "";
      mappingDraft.listMappingsByCollectionPath = {};
      mappingDraft.hiddenListTargetPathsByCollectionPath = {};
      mappingAvailableIntegrations.value = [];
      mappingIntegrationsContext.value = {
        template_key: "",
        integration_visibility: "template_only",
        integrations_enabled: true,
        expected_return_type: "auto",
      };
      mappingIntegrationPreview.value = null;
      mappingIntegrationSchema.value = null;
      mappingIntegrationSchemaError.value = "";
      mappingIntegrationSchemaLoading.value = false;
      mappingPreviewItemIndex.value = null;
      mappingPreviewItemKey.value = "";
      mappingItemPreviewOptions.value = [];
      itemPageParentCandidates.value = [];
      hydratePageRoutingDraft({});
      clearMappingPreview();
      currentPageTemplateDoc.value = null;
      resetMappingsAutosaveState();
      return;
    }

    const template = await api.getPageTemplate(pageTemplateInfo.value.path);
    currentPageTemplateDoc.value = template;

    if (!showPageMappingEditor.value) {
      mappingDraft.sourceRouteRef = "";
      mappingDraft.sectionTemplateRef = normalizeSectionTemplateRef(
        "blog/default",
        "blog/default",
      );
      mappingDraft.sourceProvider = PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
      mappingDraft.primaryIntegrationId = "";
      mappingDraft.listMappingsByCollectionPath = {};
      mappingDraft.hiddenListTargetPathsByCollectionPath = {};
      mappingAvailableIntegrations.value = [];
      mappingIntegrationsContext.value = {
        template_key: "",
        integration_visibility: "template_only",
        integrations_enabled: true,
        expected_return_type: "auto",
      };
      mappingIntegrationPreview.value = null;
      mappingIntegrationSchema.value = null;
      mappingIntegrationSchemaError.value = "";
      mappingIntegrationSchemaLoading.value = false;
      mappingPreviewItemIndex.value = null;
      mappingPreviewItemKey.value = "";
      mappingItemPreviewOptions.value = [];
      itemPageParentCandidates.value = [];
      hydratePageRoutingDraft(template);
      clearMappingPreview();
      resetMappingsAutosaveState();
      return;
    }

    await loadItemPageParentCandidatesForTemplate(template);
    hydratePageRoutingDraft(template);
    mappingDraft.sourceRouteRef = "";
    mappingDraft.sectionTemplateRef = normalizeSectionTemplateRef(
      template?.section_template_ref,
      `${template?.source_type || "blog"}/default`,
    );
    const normalizedPageMapping = normalizePageIntegrationMappingPayload(
      template?.page_integration_mapping,
      {
        sourceProvider: inferMappingSourceProvider(template?.page_integration_mapping, template),
      },
    );
    mappingDraft.sourceProvider = normalizeMappingSourceProvider(normalizedPageMapping?.source_provider)
      || inferMappingSourceProvider(template?.page_integration_mapping, template);
    mappingDraft.primaryIntegrationId = String(
      normalizedPageMapping?.selected_integration_id
      || ""
    ).trim();
    mappingPreviewItemIndex.value = normalizeMappingPreviewItemIndex(
      normalizedPageMapping?.preview_item_index
    );
    mappingPreviewItemKey.value = normalizeMappingPreviewItemKey(
      normalizedPageMapping?.preview_item_key
    );
    mappingDraft.listMappingsByCollectionPath = normalizePageListMappingsByCollectionPath(
      normalizedPageMapping?.list_mappings_by_collection_path
    );
    mappingDraft.hiddenListTargetPathsByCollectionPath = normalizePageHiddenTargetPathsByCollectionPath(
      normalizedPageMapping?.hidden_list_target_paths_by_collection_path
    );
    normalizeDraftListMappingsByCollectionPath();
    applyDefaultPageTemplateHiddenTargetPaths();
    await loadMappingIntegrations();
    await Promise.all([
      loadMappingIntegrationSchema(),
      loadMappingPreviewItemOptions(),
    ]);
    await loadMappingIntegrationPreview();
    clearMappingPreview();
    markMappingsAutosaveBaseline();
  } finally {
    loadingPageTemplateSettings.value = false;
  }
}

function formatMappingPreviewWarning(warning) {
  if (typeof warning === "string") return warning.trim();
  if (!warning || typeof warning !== "object") return "";
  const message = String(warning.message || "").trim();
  const code = String(warning.code || "").trim();
  const sourcePath = String(warning.source_path || "").trim();
  if (message && sourcePath) return `${message} (${sourcePath})`;
  if (message) return message;
  if (code) return code.replace(/_/g, " ");
  return "";
}

function currentTemplatePreviewDesignPayload() {
  if (!state.design || typeof state.design !== "object") return null;
  try {
    return mapDesignToBackendFull(clonePlain(state.design));
  } catch (err) {
    console.warn("Failed to serialize current template design for preview:", err);
    return null;
  }
}

function buildMappingPreviewRequestPayload(mappingPatchPayload) {
  const templateDoc = clonePlain(currentPageTemplateDoc.value || {});
  const currentDesign = currentTemplatePreviewDesignPayload();
  if (currentDesign && typeof currentDesign === "object") {
    templateDoc.template_design_current = currentDesign;
  }
  const pageMapping = normalizePageIntegrationMappingPayload(
    mappingPatchPayload?.page_integration_mapping,
    { sourceProvider: mappingSourceProvider.value },
  );
  return {
    template: {
      ...templateDoc,
      ...clonePlain(mappingPatchPayload || {}),
      page_integration_mapping: pageMapping,
    },
    page_integration_mapping: pageMapping,
    preview_item_key: activePageIsItemPageTemplate.value
      ? normalizeMappingPreviewItemKey(mappingPreviewItemKey.value)
      : "",
    preview_item_index: normalizeMappingPreviewItemIndex(mappingPreviewItemIndex.value),
  };
}

async function previewMappings() {
  if (!showPageMappingEditor.value) return false;
  if (!currentPageTemplateDoc.value || typeof currentPageTemplateDoc.value !== "object") return false;

  previewingMappings.value = true;
  try {
    await loadMappingPreviewItemOptions();
    if (mappingUsesIntegration.value && !mappingIntegrationPreview.value && mappingDraft.primaryIntegrationId) {
      await loadMappingIntegrationPreview();
    }

    const mappingPatchPayload = buildMappingsPatchPayload();
    const previewPayload = await api.previewPageTemplateMapping(
      pageTemplateInfo.value.path,
      buildMappingPreviewRequestPayload(mappingPatchPayload),
    );
    if (!mappingPreviewEnabled.value) return false;
    mappingPreviewWarnings.value = Array.isArray(previewPayload?.warnings)
      ? previewPayload.warnings.map(formatMappingPreviewWarning).filter(Boolean)
      : [];
    mappingPreviewDoc.value = previewPayload && typeof previewPayload === "object"
      ? previewPayload
      : null;
    return true;
  } catch (err) {
    if (!mappingPreviewEnabled.value) return false;
    console.error("Failed to build mapping preview:", err);
    mappingPreviewWarnings.value = [err?.message || "Failed to build mapping preview."];
    mappingPreviewDoc.value = null;
    return true;
  } finally {
    previewingMappings.value = false;
  }
}

async function refreshMappingPreviewIfEnabled() {
  if (!mappingPreviewEnabled.value) return;
  enterMappingPreviewAdminState();
  const success = await previewMappings();
  if (!success) {
    disableMappingPreview();
  }
}

function queueMappingPreviewRefreshIfEnabled({ delayMs = 0 } = {}) {
  if (!mappingPreviewEnabled.value) return;
  clearMappingPreviewRefreshTimer();
  mappingPreviewRefreshTimerId.value = setTimeout(() => {
    mappingPreviewRefreshTimerId.value = null;
    void refreshMappingPreviewIfEnabled();
  }, delayMs);
}

function toggleMappingPreview() {
  mappingPreviewEnabled.value = !mappingPreviewEnabled.value;
}

function setGeneratedItemPageCountForCurrentTemplate(count) {
  const normalizedCount = Math.max(0, Math.trunc(Number(count) || 0));
  const path = activePageTemplatePath.value;
  if (currentPageTemplateDoc.value && typeof currentPageTemplateDoc.value === "object") {
    currentPageTemplateDoc.value = {
      ...currentPageTemplateDoc.value,
      generated_item_page_count: normalizedCount,
    };
  }
  if (!path) return;
  pageTemplates.value = (Array.isArray(pageTemplates.value) ? pageTemplates.value : []).map((template) => {
    if (String(templatePath(template) || "").trim() !== path) return template;
    return {
      ...template,
      generated_item_page_count: normalizedCount,
    };
  });
}

async function saveMappings() {
  if (!showPageMappingEditor.value) return;
  clearMappingsAutosaveTimer();
  if (mappingUsesIntegration.value && mappingDraft.primaryIntegrationId && !mappingIntegrationPreview.value) {
    await loadMappingIntegrationPreview();
  }
  const payload = buildMappingsPatchPayload();
  const signature = mappingPayloadSignature(payload);
  await persistMappingsPayload(payload, signature, { manual: true });
}

async function regenerateAllItemPagesForTemplate() {
  if (!showRegenerateAllItemPagesButton.value || regeneratingPageTemplateItems.value) return;
  if (!canRegenerateAllItemPagesForTemplate.value) {
    pageTemplateRegenerateStatus.value = {
      type: "error",
      message: "Set this item-page template active before regenerating pages.",
    };
    return;
  }
  const path = String(pageTemplateInfo.value.path || "").trim();
  if (!path) return;
  const isInitialGeneration = !generatedItemPagesExistForTemplate.value;
  const confirmed = window.confirm(
    isInitialGeneration
      ? `Generate item pages for "${path}"?`
      : `Regenerate all item pages for "${path}" from scratch and set them back to init?`
  );
  if (!confirmed) return;

  regeneratingPageTemplateItems.value = true;
  pageTemplateRegenerateStatus.value = { type: "", message: "" };
  try {
    if (showPageMappingEditor.value) {
      await saveMappings();
    }
    const result = await api.regeneratePageTemplateItemPages(path);
    const count = Number(result?.generated_count || 0);
    setGeneratedItemPageCountForCurrentTemplate(count);
    pageTemplateRegenerateStatus.value = {
      type: "success",
      message: isInitialGeneration
        ? `Generated ${count} item page${count === 1 ? "" : "s"}.`
        : `Regenerated ${count} item page${count === 1 ? "" : "s"} and reset them to init.`,
    };
  } catch (err) {
    console.error("Failed to regenerate item pages for template:", err);
    pageTemplateRegenerateStatus.value = {
      type: "error",
      message: err?.message || "Failed to regenerate item pages.",
    };
  } finally {
    regeneratingPageTemplateItems.value = false;
  }
}

async function handleTemplateBuilderPayloadUpdated(payload) {
  if (builderContext.value?.kind !== "page") return;
  if (!payload || typeof payload !== "object") return;
  const previousGroups = mappingTargetGroups.value;
  const stabilizedListMappingsByCollectionPath = showPageMappingEditor.value
    ? normalizePageListMappingsByCollectionPath(
      mappingDraft.listMappingsByCollectionPath,
      previousGroups,
    )
    : {};
  const stabilizedHiddenTargetPathsByCollectionPath = showPageMappingEditor.value
    ? normalizePageHiddenTargetPathsByCollectionPath(
      mappingDraft.hiddenListTargetPathsByCollectionPath,
      previousGroups,
    )
    : {};
  currentPageTemplateDoc.value = payload;
  if (!showPageMappingEditor.value) return;
  mappingDraft.listMappingsByCollectionPath = stabilizedListMappingsByCollectionPath;
  mappingDraft.hiddenListTargetPathsByCollectionPath = stabilizedHiddenTargetPathsByCollectionPath;
  normalizeDraftListMappingsByCollectionPath();
  applyDefaultPageTemplateHiddenTargetPaths();
  await refreshMappingPreviewIfEnabled();
  queueMappingsAutosave({ immediate: true });
}

watch(
  () => activeTab.value,
  async () => {
    await loadActiveTabData();
  },
  { immediate: true }
);

watch(
  () => builderContext.value?.path,
  async () => {
    await loadPageTemplateSettings();
  },
  { immediate: true }
);

watch(
  () => itemPageSourceRouteOptions.value.map((entry) => entry.value).join("|"),
  () => {
    if (!showPageMappingEditor.value) return;
    if (loadingPageTemplateSettings.value) return;
    const template = currentPageTemplateDoc.value || activePageTemplateListEntry.value;
    const resolvedSourceRouteRef = resolveSourceRouteRefForTemplate(template);
    if (resolvedSourceRouteRef !== mappingDraft.sourceRouteRef) {
      mappingDraft.sourceRouteRef = resolvedSourceRouteRef;
    }
  },
  { immediate: true }
);

watch(
  () => mappingDraft.sourceRouteRef,
  async (nextValue, previousValue) => {
    if (!showPageMappingEditor.value) return;
    if (loadingPageTemplateSettings.value) return;
    if (nextValue === previousValue) return;
    const sourceRoute = routeEntryByRef(mappingDraft.sourceRouteRef);
    if (sourceRoute) {
      mappingDraft.sectionTemplateRef = normalizeSectionTemplateRef(
        sourceRoute.section_template_ref,
        `${sourceRoute.source_type || "blog"}/default`,
      );
    }
    mappingDraft.sourceProvider = mappingSupportsSharedItemsProvider.value
      ? PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS
      : PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
    mappingDraft.primaryIntegrationId = "";
    clearMappingProviderPreviewState();
    await loadMappingPreviewItemOptions();
    await loadMappingIntegrations();
    if (mappingUsesIntegration.value) {
      await Promise.all([
        loadMappingIntegrationSchema(),
        loadMappingPreviewItemOptions(),
      ]);
      await loadMappingIntegrationPreview();
    }
    await refreshMappingPreviewIfEnabled();
    queueMappingsAutosave({ immediate: true });
  }
);

watch(
  () => mappingDraft.sourceProvider,
  async (nextValue, previousValue) => {
    if (!showPageMappingEditor.value) return;
    if (loadingPageTemplateSettings.value) return;
    const normalizedNext = mappingSupportsSharedItemsProvider.value
      ? normalizeMappingSourceProvider(nextValue) || PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS
      : PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
    const normalizedPrevious = normalizeMappingSourceProvider(previousValue)
      || PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION;
    if (String(nextValue || "") !== normalizedNext) {
      mappingDraft.sourceProvider = normalizedNext;
      return;
    }
    if (normalizedNext === normalizedPrevious) return;

    if (normalizedNext === PAGE_MAPPING_SOURCE_PROVIDER_SHARED_ITEMS) {
      mappingDraft.primaryIntegrationId = "";
    }
    blankIncompatibleMappingSourcesForProvider(normalizedNext);
    clearMappingProviderPreviewState();
    normalizeDraftListMappingsByCollectionPath();
    if (normalizedNext === PAGE_MAPPING_SOURCE_PROVIDER_INTEGRATION) {
      await loadMappingIntegrations();
      await Promise.all([
        loadMappingIntegrationSchema(),
        loadMappingPreviewItemOptions(),
      ]);
      await loadMappingIntegrationPreview();
    } else {
      await loadMappingPreviewItemOptions();
    }
    await refreshMappingPreviewIfEnabled();
    queueMappingsAutosave({ immediate: true });
  }
);

watch(
  () => mappingDraft.primaryIntegrationId,
  async (nextValue, previousValue) => {
    if (!showPageMappingEditor.value) return;
    if (loadingPageTemplateSettings.value) return;
    if (!mappingUsesIntegration.value) return;
    if (nextValue === previousValue) return;
    mappingIntegrationPreview.value = null;
    mappingIntegrationSchema.value = null;
    mappingIntegrationSchemaError.value = "";
    mappingPreviewItemIndex.value = null;
    mappingPreviewItemKey.value = "";
    clearMappingPreview();
    await Promise.all([
      loadMappingIntegrationSchema(),
      loadMappingPreviewItemOptions(),
    ]);
    await loadMappingIntegrationPreview();
    await refreshMappingPreviewIfEnabled();
    queueMappingsAutosave({ immediate: true });
  }
);

watch(
  () => [
    mappingDraft.listMappingsByCollectionPath,
    mappingDraft.hiddenListTargetPathsByCollectionPath,
  ],
  () => {
    queueMappingPreviewRefreshIfEnabled();
    queueMappingsAutosave();
  },
  { deep: true }
);

watch(
  () => mappingTargetGroups.value
    .map((group) => {
      const optionSignature = Array.isArray(group?.targetOptions)
        ? group.targetOptions.map((entry) => entry.path).join(",")
        : "";
      return `${group.path}:${optionSignature}`;
    })
    .join("|"),
  () => {
    if (!showPageMappingEditor.value) return;
    normalizeDraftListMappingsByCollectionPath();
    applyDefaultPageTemplateHiddenTargetPaths();
  },
  { immediate: true }
);

watch(
  () => mappingPreviewItemSelection.value,
  async (nextValue, previousValue) => {
    if (!showPageMappingEditor.value) return;
    if (loadingPageTemplateSettings.value) return;
    if (mappingPreviewItemIndexHydrating.value) return;
    if (nextValue === previousValue) return;
    await loadMappingPreviewItemOptions();
    if (mappingUsesIntegration.value && mappingDraft.primaryIntegrationId) {
      await loadMappingIntegrationPreview();
    }
    await refreshMappingPreviewIfEnabled();
    queueMappingsAutosave({ immediate: true });
  }
);

watch(
  () => mappingPreviewEnabled.value,
  async (enabled) => {
    if (!showPageMappingEditor.value) {
      disableMappingPreview();
      return;
    }
    if (!enabled) {
      clearMappingPreview();
      exitMappingPreviewAdminState();
      return;
    }
    enterMappingPreviewAdminState();
    const success = await previewMappings();
    if (!success) {
      disableMappingPreview();
    }
  }
);

watch(
  () => mappingAutosaveStatus.value,
  (status) => {
    clearMappingAutosaveStatusTimer();
    if (status === "saved" || status === "error") {
      mappingAutosaveStatusTimer = setTimeout(() => {
        mappingAutosaveStatus.value = "idle";
        mappingAutosaveError.value = "";
        mappingAutosaveStatusTimer = null;
      }, 3000);
    }
  }
);

onMounted(async () => {
  await loadSectionTypes();
});

onUnmounted(() => {
  disableMappingPreview();
  clearMappingsAutosaveTimer();
  clearMappingPreviewRefreshTimer();
  clearMappingAutosaveStatusTimer();
});
</script>

<style scoped>
.templates-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.templates-section-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 16px;
  align-items: start;
}

.templates-section-main {
  min-width: 0;
}

.templates-section-side {
  min-width: 0;
}

.templates-section-side :deep(.admin-sticky-sidebar__body) {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.section-template-sidebar-controls {
  display: grid;
  gap: 12px;
  flex: 0 0 auto;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.section-template-search-row {
  display: flex;
  gap: 8px;
}

.section-template-search-input {
  flex: 1;
  min-width: 0;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 7px 10px;
  font-size: 12px;
  background: #fff;
  color: #0f172a;
}

.section-template-search-input:focus {
  outline: none;
  border-color: var(--admin-accent, #4f46e5);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--admin-accent, #4f46e5) 16%, transparent);
}

.section-template-search-input::placeholder {
  color: #94a3b8;
}

.section-template-search-clear {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  padding: 0 10px;
}

.section-template-search-clear:hover {
  background: #f8fafc;
  color: #0f172a;
}

.section-template-favorites {
  flex: 0 0 auto;
  margin-top: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.section-template-favorites-title {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 8px;
  color: var(--admin-favorite-color, #b45309);
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.section-template-favorites-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-template-nav-empty {
  margin-top: 12px;
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 10px;
  font-size: 13px;
  color: #64748b;
  background: #f8fafc;
}

.section-template-nav-list {
  min-height: 0;
  flex: 1 1 auto;
  overflow: auto;
  margin-top: 12px;
  padding-right: 4px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-template-nav-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-template-nav-heading {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
  cursor: pointer;
  padding: 8px 10px;
  text-align: left;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.section-template-nav-heading:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.section-template-nav-heading:focus-visible {
  outline: none;
  border-color: var(--admin-accent, #4f46e5);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--admin-accent, #4f46e5) 18%, transparent);
}

.section-template-nav-heading.active {
  border-color: color-mix(in srgb, var(--admin-accent, #4f46e5) 75%, #ffffff);
  background: color-mix(in srgb, var(--admin-accent, #4f46e5) 10%, #ffffff);
}

.section-template-nav-heading-main {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 12px;
  font-weight: 700;
}

.section-template-nav-heading-main span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.section-template-nav-icon {
  flex: 0 0 auto;
  font-size: 14px;
}

.section-template-nav-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  min-width: 24px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
}

.section-template-nav-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: -2px 0 2px 16px;
  padding-left: 10px;
  border-left: 2px solid #e2e8f0;
}

.section-template-nav-item {
  width: 100%;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #475569;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
  text-align: left;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.section-template-nav-item:hover {
  background: #eef2ff;
  color: #3730a3;
}

.section-template-nav-item--favorite {
  border: 1px solid color-mix(in srgb, var(--admin-favorite-color, #b45309) 24%, #ffffff);
  background: color-mix(in srgb, var(--admin-favorite-color, #b45309) 8%, #ffffff);
}

.section-template-nav-item--favorite:hover {
  background: color-mix(in srgb, var(--admin-favorite-color, #b45309) 14%, #ffffff);
  color: #7c2d12;
}

.section-template-nav-item:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--admin-accent, #4f46e5) 18%, transparent);
}

.section-template-nav-item-main {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
  max-width: 100%;
}

.section-template-nav-item-name {
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 700;
}

.section-template-nav-item-star {
  flex: 0 0 auto;
  color: var(--admin-favorite-color, #b45309);
  font-size: 11px;
}

.create-row {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
  max-width: 640px;
  margin-bottom: 12px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.create-row--inline {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  max-width: 520px;
}

.create-row-fields {
  display: grid;
  grid-template-columns: minmax(220px, 340px) minmax(180px, 240px);
  align-items: center;
  gap: 8px;
  max-width: 590px;
}

.create-row-fields--single {
  grid-template-columns: minmax(220px, 340px);
  max-width: 340px;
}

.create-row--inline .create-row-fields--single {
  flex: 1 1 260px;
  max-width: none;
}

.create-control--name {
  max-width: 340px;
}

.create-control--type {
  max-width: 240px;
}

.create-row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
}

.create-row-actions .btn-sm {
  min-width: 86px;
}

.template-regenerate-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 16px 0 8px;
  text-align: center;
}

.template-regenerate-status {
  color: #475569;
  font-size: 13px;
  font-weight: 700;
}

.template-regenerate-hint {
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
}

.template-regenerate-hint--blocked {
  color: #b45309;
}

.template-regenerate-status--success {
  color: #166534;
}

.template-regenerate-status--error {
  color: #b91c1c;
}

.create-row-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  max-width: 590px;
  color: #64748b;
  font-size: 12px;
}

.btn-success {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid #16a34a;
  border-radius: var(--admin-button-border-radius);
  background: #fff;
  color: #15803d;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
  padding: var(--admin-button-padding-y) var(--admin-button-padding-x);
  transition: all 0.15s;
}

.btn-success:hover:not(:disabled) {
  background: #f0fdf4;
  border-color: #15803d;
  color: #166534;
}

.btn-success:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-danger-outline {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid #dc2626;
  border-radius: var(--admin-button-border-radius);
  background: #fff;
  color: #b91c1c;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
  padding: var(--admin-button-padding-y) var(--admin-button-padding-x);
  transition: all 0.15s;
}

.btn-danger-outline:hover:not(:disabled) {
  background: #fef2f2;
  border-color: #b91c1c;
  color: #991b1b;
}

.btn-danger-outline:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.create-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #334155;
  white-space: nowrap;
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.template-list--flat {
  gap: 0;
}

.template-row {
  min-width: 0;
}

.template-row.admin-list-item {
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 12px;
}

.template-group-items .template-row.admin-list-item,
.template-list--flat .template-row.admin-list-item {
  border-bottom: 1px solid #e2e8f0;
}

.template-group-items .template-row.admin-list-item:last-child,
.template-list--flat .template-row.admin-list-item:last-child {
  border-bottom: 0;
}

.template-row-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1 1 auto;
}

.template-row-main small {
  color: #64748b;
}

.template-row-actions {
  flex-shrink: 0;
  min-width: 0;
}

.template-row-actions .btn-sm {
  min-width: 86px;
}

.template-favorite-button {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 32px;
  border: 1px solid color-mix(in srgb, var(--admin-favorite-color, #b45309) 35%, #ffffff);
  border-radius: var(--admin-button-border-radius, 6px);
  background: color-mix(in srgb, var(--admin-favorite-color, #b45309) 12%, #ffffff);
  color: var(--admin-favorite-color, #b45309);
  cursor: pointer;
  font-size: 13px;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, opacity 0.15s ease;
}

.template-favorite-button:hover:not(:disabled),
.template-favorite-button.active {
  background: var(--admin-favorite-color, #b45309);
  border-color: var(--admin-favorite-color, #b45309);
  color: #fff;
}

.template-favorite-button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--admin-favorite-color, #b45309) 20%, transparent);
}

.template-favorite-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.template-row-icon {
  font-size: 16px;
  line-height: 1;
}

.template-name-edit {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  flex: 1 1 auto;
}

.template-name-inline {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.template-path-prefix {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

.template-name-static {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.template-name-hint {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.2;
}

.template-group {
  min-width: 0;
  scroll-margin-top: 76px;
}

.template-group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 0;
  padding: 10px 12px;
  border-bottom: 1px solid #cbd5e1;
  background: #f8fafc;
}

.template-group-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.template-group-title strong {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.template-group-head small {
  color: #64748b;
  font-size: 12px;
}

.template-group-create {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex: 1 1 320px;
  gap: 8px;
  min-width: 240px;
}

.template-group-create .create-control--name {
  width: min(100%, 260px);
}

.template-group-items {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.template-group-items.admin-list {
  gap: 0;
}

.template-active-radio {
  display: inline-flex;
  align-items: center;
  flex: 0 0 96px;
  gap: 6px;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.template-active-radio input {
  margin: 0;
  accent-color: var(--admin-accent, #4f46e5);
}

.template-row--muted .template-name-edit,
.template-row--muted .template-row-main > .template-row-icon {
  opacity: 0.55;
}

.template-row--muted .template-row-actions {
  opacity: 0.78;
}

.builder-hint {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.mapping-card {
  margin: 0;
}

.mapping-card h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.mapping-card p {
  color: #64748b;
}

.mapping-card code {
  color: #0f172a;
}

.mapping-card {
  --mapping-row-action-width: 86px;
}

.mapping-section {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  overflow: hidden;
}

.mapping-section + .mapping-section {
  margin-top: 10px;
}

.mapping-section-title {
  cursor: pointer;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  background: #f8fafc;
}

.mapping-section-content {
  padding: 12px;
}

.mapping-base-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 16px;
}

.mapping-base-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding: 10px;
  border: none;
  background: #fff;
}

.mapping-base-panel--wide {
  grid-column: 1 / -1;
}

.mapping-base-label {
  color: #334155;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.mapping-base-meta {
  display: flex;
  gap: 24px;
  color: #64748b;
  font-size: 12px;
}

.mapping-routing-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.mapping-routing-field {
  display: grid;
  gap: 5px;
  color: #64748b;
  font-size: 12px;
}

.mapping-routing-preview code,
.mapping-routing-readonly,
.mapping-base-meta code {
  word-break: break-word;
}

.mapping-routing-readonly {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 8px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #f8fafc;
  color: #334155;
  font-size: 13px;
}

.mapping-routing-warning {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
  padding: 10px 12px;
  border: 1px solid #fbbf24;
  border-radius: 6px;
  background: #fffbeb;
  color: #92400e;
  font-size: 13px;
  font-weight: 600;
}

.mapping-routing-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.mapping-routing-status {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
}

.mapping-routing-status.success {
  color: #166534;
}

.mapping-routing-status.error {
  color: #b91c1c;
}

.mapping-base-meta span {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.mapping-base-switch-field {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 420px;
}

.mapping-base-switch-field span {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.mapping-base-switch-select {
  min-width: 0;
  max-width: 280px;
}

.mapping-base-link {
  align-self: flex-start;
}

.mapping-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}

.mapping-field--inline {
  flex-direction: row;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.mapping-hint {
  color: #64748b;
  font-size: 12px;
}

.mapping-heuristics {
  display: grid;
  gap: 6px;
  margin: 8px 0 12px;
  padding: 10px 12px;
  border: 1px solid #c7d2fe;
  border-radius: 8px;
  background: #eef2ff;
  color: #3730a3;
  font-size: 12px;
  line-height: 1.45;
}

.mapping-heuristics p {
  margin: 0;
}

.mapping-heuristics strong {
  color: #312e81;
}

.mapping-checkbox {
  margin-top: 6px;
}

.mapping-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mapping-list-groups {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mapping-group-card {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 10px;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mapping-group-card--readonly {
  background: #f8fafc;
}

.mapping-group-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.mapping-group-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mapping-group-title small {
  color: #64748b;
  font-size: 12px;
}

.mapping-group-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.mapping-row-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) var(--mapping-row-action-width);
  gap: 8px;
  font-size: 12px;
  color: #334155;
  font-weight: 600;
}

.mapping-row-head > span:last-child {
  width: var(--mapping-row-action-width);
}

.mapping-row-head--readonly {
  color: #64748b;
}

.mapping-inherited-groups {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.mapping-inherited-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mapping-inherited-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mapping-inherited-title small {
  color: #64748b;
  font-size: 12px;
}

.mapping-row--readonly {
  opacity: 0.72;
}

.mapping-readonly-value {
  min-height: 34px;
  display: flex;
  align-items: center;
  color: #64748b;
  background: #f1f5f9;
  border-color: #cbd5e1;
  pointer-events: none;
}

.mapping-visibility-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px;
}

.mapping-visibility-defaults-toggle {
  margin: 0 0 10px;
}

.mapping-visibility-option {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #0f172a;
}

.mapping-fixed-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mapping-fixed-row {
  display: grid;
  grid-template-columns: minmax(160px, 220px) minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}

.mapping-fixed-label {
  font-size: 12px;
  color: #334155;
}

.mapping-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) var(--mapping-row-action-width);
  gap: 8px;
}

.mapping-row > .btn-sm {
  width: var(--mapping-row-action-width);
}

.mapping-group-footer {
  display: flex;
  justify-content: flex-start;
  margin-top: 2px;
}

.mapping-group-footer .btn-sm {
  min-width: var(--mapping-row-action-width);
}

.mapping-inline {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}

.mapping-disabled-hint {
  margin: 6px 0 0;
  color: #b45309;
  font-size: 12px;
}

.mapping-preview {
  margin: 0 0 10px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.mapping-preview-body {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}

.visually-hidden {
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

@media (max-width: 1024px) {
  .templates-section-layout {
    grid-template-columns: 1fr;
  }

  .section-template-nav-list {
    max-height: 300px;
  }
}

@media (max-width: 900px) {
  .create-row--inline,
  .template-group-head {
    flex-direction: column;
    align-items: stretch;
  }

  .create-row-fields,
  .mapping-row,
  .mapping-row-head,
  .mapping-fixed-row {
    grid-template-columns: minmax(0, 1fr);
  }

  .template-group-create {
    justify-content: flex-start;
    min-width: 0;
  }

  .template-group-create .create-control--name,
  .create-control--name {
    max-width: 100%;
  }

  .mapping-group-head {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
