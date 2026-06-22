<template>
  <div class="admin-sitemap admin-page">
    <AutosaveToast :message="pageAutosaveMessage" :tone="pageAutosaveTone" />

    <header class="page-header">
      <h1>Pages</h1>
      <p class="page-subtitle">Manage page routes, crawler visibility, sitemap.xml, and redirect rules.</p>
    </header>

    <AdminPageTabs
      :tabs="pageTabs"
      :model-value="activeTab"
      @update:model-value="setActiveTab"
    />

    <template v-if="activeTab === 'sitemap'">
      <div v-if="!loading" class="subtree-migration-toggle" @click.stop>
        <label class="toggle-label">
          <input type="checkbox" v-model="subtreeReorderEnabled" />
          <span v-if="subtreeReorderEnabled">Migration mode</span>
          <span v-else>Sibling mode</span>
        </label>
        <p class="toggle-hint">
          <span v-if="subtreeReorderEnabled">Drag any page to another page route (or root) to move its full subtree.</span>
          <span v-else>Reorder only within sibling lists.</span>
        </p>
        <p v-if="subtreeMoveError" class="subtree-move-error">{{ subtreeMoveError }}</p>
      </div>

      <div v-if="loading" class="loading-state">Loading pages...</div>

      <template v-else>
      <div class="sitemap-layout">
        <!-- Tree Structure -->
        <div class="sitemap-tree">
        <div class="tree-section">
          <div class="tree-header" @click="toggleSection('pages')">
            <span class="tree-chevron" :class="{ expanded: expandedSections.pages }">
              <font-awesome-icon :icon="faChevronRight" />
            </span>
            <span class="tree-icon">
              <font-awesome-icon :icon="faGlobe" />
            </span>
            <span class="tree-label">Pages</span>
            <span class="tree-count">
              {{ sortedPages.length }} pages
              <template v-if="collapsedGeneratedPageCount > 0">
                ({{ collapsedGeneratedPageCount }} generated hidden)
              </template>
            </span>
            <button class="add-page-btn" @click.stop="openCreateDialog()" title="Create new page">+</button>
          </div>
          <div v-show="expandedSections.pages" class="tree-children pages-list">
            <div
              v-if="subtreeReorderEnabled"
              class="subtree-drop-root subtree-drop-root--section"
              :class="{ active: isSubtreeDropTarget('__root__'), invalid: isSubtreeDropInvalid('__root__') }"
              @dragover.prevent="onSubtreeTargetDragOver('__root__')"
              @drop.prevent="onSubtreeDrop('__root__')"
            >
              Drop here to move subtree to root path `/`
            </div>
            <div 
              v-for="page in sortedPages" 
              :key="page.id" 
              class="tree-item page-item"
              :class="{
                'is-hidden': isPageHidden(page),
                'is-under-construction': isPageUnderConstruction(page),
                'is-scheduled': hasSchedule(page),
                'subtree-drag-source': isSubtreeDragSource(page.slug),
                'subtree-drop-target': isSubtreeDropTarget(page.slug),
                'subtree-drop-invalid': isSubtreeDropInvalid(page.slug),
              }"
              :style="{ paddingLeft: (12 + getPageDepth(page.slug) * 20) + 'px' }"
              :draggable="subtreeReorderEnabled && !migratingSubtree && page.slug !== 'landing'"
              @dragstart="onSubtreeDragStart(page.slug, $event)"
              @dragend="onSubtreeDragEnd"
              @dragover.prevent="onSubtreeTargetDragOver(page.slug)"
              @drop.prevent="onSubtreeDrop(page.slug)"
              @click="selectPage(page)"
            >
              <span v-if="getPageDepth(page.slug) > 0" class="tree-indent">└</span>
              <span class="tree-icon">
                <font-awesome-icon :icon="getPageDepth(page.slug) > 0 ? faFileLines : faHouse" />
              </span>
              <span class="tree-path">/{{ page.slug === 'landing' ? '' : page.slug }}</span>
              <span class="tree-name">{{ getPageTitle(page) }}</span>
              <button
                v-if="hasGeneratedChildren(page)"
                class="generated-toggle-btn"
                @click.stop="toggleGeneratedChildren(page.slug)"
                :title="
                  areGeneratedChildrenExpanded(page.slug)
                    ? 'Hide generated item pages for this parent route'
                    : 'Load generated item pages for this parent route'
                "
              >
                {{
                  areGeneratedChildrenExpanded(page.slug)
                    ? `Hide generated (${getGeneratedChildCount(page.slug)})`
                    : `Load generated (${getGeneratedChildCount(page.slug)})`
                }}
              </button>
              <div class="page-badges">
                <span v-if="isPageHidden(page)" class="badge hidden" :title="getVisibilityTooltip(page)">
                  Hidden
                </span>
                <span v-else-if="isPageUnderConstruction(page)" class="badge under-construction" :title="getVisibilityTooltip(page)">
                  Under Construction
                </span>
                <span v-else class="badge published">Live</span>
                <span
                  v-if="page.is_visible"
                  class="badge hits"
                  :title="`${formatAnonymousHitCount(page.anonymous_hit_count)} anonymous public page hits`"
                >
                  {{ formatAnonymousHitCount(page.anonymous_hit_count) }} hits
                </span>
                <span
                  v-if="isGeneratedManagedPage(page)"
                  class="badge generated"
                  title="Auto-generated from a template/source item"
                >
                  Generated
                </span>
                <span v-if="page.in_menu" class="badge menu" title="Included in menu">Menu</span>
                <span v-if="page.in_footer" class="badge footer" title="Included in footer links">Footer</span>
                <span v-if="page.redirect_to" class="badge redirect" title="Redirects to another page">
                  <font-awesome-icon :icon="faArrowUpRightFromSquare" />
                </span>
                <span v-if="hasActiveSchedule(page)" class="badge scheduled" :title="getScheduleTooltip(page)">
                  <font-awesome-icon :icon="faClock" />
                </span>
                <span
                  v-if="page.hide_from_sitemap || page.hide_subtree_from_sitemap"
                  class="badge crawler"
                  :title="getCrawlerVisibilityTooltip(page)"
                >
                  NoCrawl
                </span>
              </div>
              <button 
                class="add-subpage-btn" 
                @click.stop="startCreateSubpage(page)"
                :title="'Add subpage to /' + page.slug"
              >+</button>
            </div>
            <div v-if="sortedPages.length === 0" class="empty-pages">
              No pages yet. Create your first page!
            </div>
          </div>
        </div>

        <div class="tree-section">
          <div class="tree-header" @click="toggleSection('menusGroup')">
            <span class="tree-chevron" :class="{ expanded: expandedSections.menusGroup }">
              <font-awesome-icon :icon="faChevronRight" />
            </span>
            <span class="tree-icon">
              <font-awesome-icon :icon="faBars" />
            </span>
            <span class="tree-label">Menus</span>
            <span class="tree-count">{{ menuPages.length + navExternalLinks.length + footerPages.length + footerExternalLinks.length }} items</span>
          </div>
          <div v-show="expandedSections.menusGroup" class="tree-children tree-group-children">
        <!-- Navigation Menu -->
        <div class="tree-section">
          <div class="tree-header" @click="toggleSection('menu')">
            <span class="tree-chevron" :class="{ expanded: expandedSections.menu }">
              <font-awesome-icon :icon="faChevronRight" />
            </span>
            <span class="tree-icon">
              <font-awesome-icon :icon="faBars" />
            </span>
            <span class="tree-label">Nav Menu</span>
            <span class="tree-count">{{ menuPages.length + navExternalLinks.length }} items</span>
            <button class="add-page-btn" @click.stop="openMenuItemDialog('menu')" title="Add nav menu item">+</button>
          </div>
          <div v-show="expandedSections.menu" class="tree-children pages-list menu-draggable">
            <div
              v-if="subtreeReorderEnabled"
              class="subtree-drop-root subtree-drop-root--section"
              :class="{ active: isSubtreeDropTarget('__root__'), invalid: isSubtreeDropInvalid('__root__') }"
              @dragover.prevent="onSubtreeTargetDragOver('__root__')"
              @drop.prevent="onSubtreeDrop('__root__')"
            >
              Drop here to move subtree to root path `/`
            </div>
            <div class="site-logo-section menu-link-group">
              <div class="link-group-title">Topbar Logo</div>
              <div class="site-logo-actions">
                <button
                  type="button"
                  class="btn-secondary btn-sm"
                  :disabled="navigationLinksSaving"
                  @click="openTopbarLogoPicker"
                >
                  {{ topbarLogoUrl ? 'Replace' : 'Select' }}
                </button>
                <button
                  v-if="topbarLogoUrl"
                  type="button"
                  class="btn-secondary btn-sm"
                  :disabled="navigationLinksSaving"
                  @click="clearTopbarLogo"
                >
                  Clear
                </button>
              </div>
              <div v-if="topbarLogoUrl" class="site-logo-preview">
                <img :src="topbarLogoUrl" alt="Topbar logo preview" class="site-logo-preview-image" />
                <span class="tree-path site-logo-preview-url">{{ topbarLogoUrl }}</span>
              </div>
              <p v-else class="field-hint site-logo-hint">
                No topbar logo selected. Topbar uses text fallback.
              </p>
            </div>
            <div class="internal-links-section menu-link-group">
              <div class="internal-links-title">Internal Links</div>
              <!-- Top-level menu items (draggable among siblings) -->
              <draggable 
                :model-value="topLevelMenuItems"
                @update:model-value="(val) => onMenuReorderNodes({ nodes: val, parentSlug: null })"
                :item-key="item => item.page.id"
                handle=".drag-handle"
                ghost-class="drag-ghost"
                :animation="150"
                :disabled="subtreeReorderEnabled || migratingSubtree"
              >
                <template #item="{ element: item }">
                  <SitemapMenuTreeNode
                    :node="item"
                    :depth="0"
                    :subtree-reorder-enabled="subtreeReorderEnabled"
                    :migrating-subtree="migratingSubtree"
                    :select-page="selectPage"
                    :get-menu-title="getMenuTitle"
                    :is-subtree-drag-source="isSubtreeDragSource"
                    :is-subtree-drop-target="isSubtreeDropTarget"
                    :is-subtree-drop-invalid="isSubtreeDropInvalid"
                    :on-subtree-drag-start="onSubtreeDragStart"
                    :on-subtree-drag-end="onSubtreeDragEnd"
                    :on-subtree-target-drag-over="onSubtreeTargetDragOver"
                    :on-subtree-drop="onSubtreeDrop"
                    @reorder="onMenuReorderNodes"
                  />
                </template>
              </draggable>
              <div v-if="topLevelMenuItems.length === 0" class="empty-pages">
                No internal pages in nav menu.
              </div>
            </div>

            <div class="external-links-section menu-link-group">
              <div class="external-links-title">External Links</div>
              <draggable
                :model-value="sortedNavExternalLinks"
                @update:model-value="(val) => onExternalLinksReorder('menu', val)"
                :item-key="(item) => item.id"
                handle=".drag-handle"
                ghost-class="drag-ghost"
                :animation="150"
                :disabled="navigationLinksSaving"
              >
                <template #item="{ element: link }">
                  <div
                    class="tree-item menu-item-draggable external-link-item"
                    @click="openMenuItemDialog('menu', { mode: 'external', editingLink: link })"
                  >
                    <span class="drag-handle" :class="{ disabled: navigationLinksSaving }" @click.stop>⋮⋮</span>
                    <span class="tree-icon">
                      <font-awesome-icon
                        v-if="link.icon && link.icon !== 'other'"
                        :icon="['fab', resolveExternalIconName(link.icon)]"
                      />
                      <font-awesome-icon v-else :icon="faArrowUpRightFromSquare" />
                    </span>
                    <span class="tree-path">{{ link.url }}</span>
                    <span class="tree-name">{{ getExternalLinkDisplayTitle(link) }}</span>
                  </div>
                </template>
              </draggable>
              <div v-if="sortedNavExternalLinks.length === 0" class="empty-pages">
                No external nav links configured.
              </div>
            </div>
          </div>
        </div>

        <!-- Footer Links -->
        <div class="tree-section">
          <div class="tree-header" @click="toggleSection('footer')">
            <span class="tree-chevron" :class="{ expanded: expandedSections.footer }">
              <font-awesome-icon :icon="faChevronRight" />
            </span>
            <span class="tree-icon">
              <font-awesome-icon :icon="faBars" />
            </span>
            <span class="tree-label">Footer Menu</span>
            <span class="tree-count">{{ footerPages.length + footerExternalLinks.length }} items</span>
            <button class="add-page-btn" @click.stop="openMenuItemDialog('footer')" title="Add footer item">+</button>
          </div>
          <div v-show="expandedSections.footer" class="tree-children pages-list menu-draggable">
            <div class="site-logo-section menu-link-group">
              <div class="link-group-title">Footer Logo</div>
              <div class="site-logo-actions">
                <button
                  type="button"
                  class="btn-secondary btn-sm"
                  :disabled="navigationLinksSaving"
                  @click="openFooterLogoPicker"
                >
                  {{ footerLogoUrl ? 'Replace' : 'Select' }}
                </button>
                <button
                  v-if="footerLogoUrl"
                  type="button"
                  class="btn-secondary btn-sm"
                  :disabled="navigationLinksSaving"
                  @click="clearFooterLogo"
                >
                  Clear
                </button>
              </div>
              <div v-if="footerLogoUrl" class="site-logo-preview">
                <img :src="footerLogoUrl" alt="Footer logo preview" class="site-logo-preview-image" />
                <span class="tree-path site-logo-preview-url">{{ footerLogoUrl }}</span>
              </div>
              <p v-else class="field-hint site-logo-hint">
                No footer logo selected. Footer uses text fallback.
              </p>
            </div>
            <div class="external-links-section menu-link-group">
              <div class="external-links-title">External Links</div>
              <draggable
                :model-value="sortedFooterExternalLinks"
                @update:model-value="(val) => onExternalLinksReorder('footer', val)"
                :item-key="(item) => item.id"
                handle=".drag-handle"
                ghost-class="drag-ghost"
                :animation="150"
                :disabled="navigationLinksSaving"
              >
                <template #item="{ element: link }">
                  <div
                    class="tree-item menu-item-draggable external-link-item"
                    @click="openMenuItemDialog('footer', { mode: 'external', editingLink: link })"
                  >
                    <span class="drag-handle" :class="{ disabled: navigationLinksSaving }" @click.stop>⋮⋮</span>
                    <span class="tree-icon">
                      <font-awesome-icon
                        v-if="link.icon && link.icon !== 'other'"
                        :icon="['fab', resolveExternalIconName(link.icon)]"
                      />
                      <font-awesome-icon v-else :icon="faArrowUpRightFromSquare" />
                    </span>
                    <span class="tree-path">{{ link.url }}</span>
                    <span class="tree-name">{{ getExternalLinkDisplayTitle(link) }}</span>
                  </div>
                </template>
              </draggable>
              <div v-if="sortedFooterExternalLinks.length === 0" class="empty-pages">
                No external footer links configured.
              </div>
            </div>
            <div class="internal-links-section menu-link-group">
              <div class="internal-links-title">Internal Links</div>
              <draggable
                :model-value="footerPages"
                @update:model-value="onFooterReorder"
                :item-key="(item) => item.slug"
                handle=".drag-handle"
                ghost-class="drag-ghost"
                :animation="150"
                :disabled="subtreeReorderEnabled || migratingSubtree"
              >
                <template #item="{ element: page }">
                  <div
                    class="tree-item page-item menu-item-draggable"
                    :class="{
                      'is-hidden': isPageHidden(page),
                      'is-under-construction': isPageUnderConstruction(page),
                    }"
                  >
                    <span
                      class="drag-handle"
                      :class="{ disabled: subtreeReorderEnabled || migratingSubtree }"
                      :title="subtreeReorderEnabled ? 'Migration mode: drag reordering is disabled' : 'Drag to reorder'"
                    >⋮⋮</span>
                    <span class="tree-icon">
                      <font-awesome-icon :icon="faFileLines" />
                    </span>
                    <span class="tree-path" @click="selectPage(page)">/{{ page.slug === 'landing' ? '' : page.slug }}</span>
                    <span class="tree-name" @click="selectPage(page)">{{ getMenuTitle(page) }}</span>
                    <div class="page-badges">
                      <span v-if="isPageHidden(page)" class="badge hidden">
                        Hidden
                      </span>
                      <span v-else-if="isPageUnderConstruction(page)" class="badge under-construction">
                        Under Construction
                      </span>
                      <span v-else class="badge published">Live</span>
                    </div>
                  </div>
                </template>
              </draggable>
              <div v-if="footerPages.length === 0" class="empty-pages">
                No internal pages in footer.
              </div>
            </div>
          </div>
        </div>

          <p v-if="navigationLinksError" class="field-error navigation-links-error">
            {{ navigationLinksError }}
          </p>
          </div>
        </div>

        <div class="tree-section">
          <div class="tree-header" @click="toggleSection('endpointsGroup')">
            <span class="tree-chevron" :class="{ expanded: expandedSections.endpointsGroup }">
              <font-awesome-icon :icon="faChevronRight" />
            </span>
            <span class="tree-icon">
              <font-awesome-icon :icon="faPlug" />
            </span>
            <span class="tree-label">Endpoints</span>
            <span class="tree-count">{{ adminRoutes.length + totalApiRoutes }} endpoints</span>
          </div>
          <div v-show="expandedSections.endpointsGroup" class="tree-children tree-group-children">
        <!-- Admin Routes -->
        <div class="tree-section">
          <div class="tree-header" @click="toggleSection('admin')">
            <span class="tree-chevron" :class="{ expanded: expandedSections.admin }">
              <font-awesome-icon :icon="faChevronRight" />
            </span>
            <span class="tree-icon">
              <font-awesome-icon :icon="faGear" />
            </span>
            <span class="tree-label">Private Admin Routes</span>
            <span class="tree-count">{{ adminRoutes.length }} routes</span>
          </div>
          <div v-show="expandedSections.admin" class="tree-children">
            <div v-for="route in adminRoutes" :key="route.path" class="tree-item">
              <span class="tree-icon">
                <font-awesome-icon :icon="faFileLines" />
              </span>
              <span class="tree-path">/{{ route.path }}</span>
              <span class="tree-name">{{ route.name }}</span>
            </div>
          </div>
        </div>

        <!-- API Routes -->
        <div class="tree-section">
          <div class="tree-header" @click="toggleSection('api')">
            <span class="tree-chevron" :class="{ expanded: expandedSections.api }">
              <font-awesome-icon :icon="faChevronRight" />
            </span>
            <span class="tree-icon">
              <font-awesome-icon :icon="faPlug" />
            </span>
            <span class="tree-label">API Routes</span>
            <span v-if="apiRoutesLoading" class="tree-count">Loading...</span>
            <span v-else class="tree-count">{{ totalApiRoutes }} endpoints</span>
          </div>
          <div v-show="expandedSections.api" class="tree-children api-routes">
            <div v-if="apiRoutesLoading" class="api-loading">Loading API schema...</div>
            <div v-else-if="apiRoutes.length === 0" class="api-loading">No API routes found</div>
            <div v-else v-for="route in apiRoutes" :key="route.path" class="api-group">
              <div 
                class="tree-item api-parent" 
                @click="toggleApiGroup(route.path)"
              >
                <span class="tree-chevron small" :class="{ expanded: expandedApiGroups[route.path] }">
                  <font-awesome-icon :icon="faChevronRight" />
                </span>
                <span class="tree-icon">
                  <font-awesome-icon :icon="route.icon" />
                </span>
                <span class="tree-path">/api/v1{{ route.path }}</span>
                <span class="tree-name">{{ route.name }}</span>
                <span class="api-access-summary">
                  <span v-if="route.public_count" class="access-tag public">Public {{ route.public_count }}</span>
                  <span v-if="route.private_count" class="access-tag private">Private {{ route.private_count }}</span>
                </span>
                <span class="tree-count">{{ route.subroutes?.length || 0 }}</span>
              </div>
              <div v-show="expandedApiGroups[route.path]" class="api-subroutes">
                <div 
                  v-for="sub in route.subroutes" 
                  :key="sub.method + sub.path" 
                  class="tree-item api-subroute"
                >
                  <span class="http-method" :class="sub.method.toLowerCase()">{{ sub.method }}</span>
                  <span class="tree-path">{{ sub.path || '/' }}</span>
                  <span class="tree-name">{{ sub.name }}</span>
                  <span class="access-tag" :class="sub.access">{{ sub.access === 'public' ? 'Public' : 'Private' }}</span>
                </div>
              </div>
            </div>
          </div>
          </div>
        </div>
        </div>
      </div>

      <!-- Right Editor Panel -->
      <AdminStickySidebar class="sitemap-side" bare collapse="wide">
        <div v-if="selectedPage" class="page-editor page-editor--inline">
          <div class="editor-header">
            <div class="editor-header-left">
              <h2>Edit Page</h2>
              <span class="header-page-state" :class="resolveStatusClass(editForm.status)">
                {{ formatPageStatusLabel(editForm.status) }}
              </span>
            </div>
            <a
              :href="'/' + (selectedPage.slug === 'landing' ? '' : selectedPage.slug) + '?noredirect=1'"
              target="_blank"
              rel="noopener"
              class="btn-secondary btn-sm"
            >
              Open
              <font-awesome-icon :icon="faArrowUpRightFromSquare" />
            </a>
          </div>

          <div class="editor-body">
            <div class="edit-sections">
              <section class="edit-section" :class="{ expanded: openEditSection === 'identifier' }">
                <button type="button" class="edit-section-header" @click="setOpenEditSection('identifier')">
                  <span class="edit-section-title">Page Identifier</span>
                  <span class="edit-section-summary">{{ pagePathFromSlug(selectedPage.slug) }}</span>
                  <span class="edit-section-chevron" :class="{ expanded: openEditSection === 'identifier' }">
                    <font-awesome-icon :icon="faChevronRight" />
                  </span>
                </button>
                <div v-show="openEditSection === 'identifier'" class="edit-section-body">
                  <div class="field-group">
                    <label>Slug (URL path)</label>
                    <div class="slug-input-wrap">
                      <span class="slug-prefix">/</span>
                      <input
                        type="text"
                        v-model="editForm.slug"
                        placeholder="parent/child or my-page"
                        class="text-input slug-input"
                        @input="validateEditSlug"
                        :disabled="selectedPage.slug === 'landing'"
                      />
                    </div>
                    <p class="field-hint">
                      Renaming updates descendant routes and creates permanent redirects from old routes to the new routes.
                    </p>
                    <p v-if="editSlugError" class="field-error">{{ editSlugError }}</p>
                    <div class="inline-actions">
                      <button
                        class="btn-secondary btn-sm"
                        type="button"
                        @click="renameSelectedPage"
                        :disabled="renaming || selectedPage.slug === 'landing' || !canRenameSelectedPage || !!editSlugError"
                      >
                        {{ renaming ? 'Renaming...' : 'Rename Route' }}
                      </button>
                    </div>
                  </div>

                  <div class="field-group">
                    <label>Page Title</label>
                    <div class="title-inputs">
                      <div class="lang-input">
                        <span class="lang-label">DE</span>
                        <input
                          type="text"
                          v-model="editForm.title_de"
                          placeholder="German title"
                          class="text-input"
                          @blur="autoSavePageChanges"
                        />
                      </div>
                      <div class="lang-input">
                        <span class="lang-label">EN</span>
                        <input
                          type="text"
                          v-model="editForm.title_en"
                          placeholder="English title"
                          class="text-input"
                          @blur="autoSavePageChanges"
                        />
                      </div>
                    </div>
                    <p class="field-hint">Displayed in sitemap and used as fallback in navigation menus.</p>
                  </div>
                </div>
              </section>

              <section class="edit-section" :class="{ expanded: openEditSection === 'visibility' }">
                <button type="button" class="edit-section-header" @click="setOpenEditSection('visibility')">
                  <span class="edit-section-title">Visibility</span>
                  <span class="edit-section-summary">{{ formatPageStatusLabel(editForm.status) }}</span>
                  <span class="edit-section-chevron" :class="{ expanded: openEditSection === 'visibility' }">
                    <font-awesome-icon :icon="faChevronRight" />
                  </span>
                </button>
                <div v-show="openEditSection === 'visibility'" class="edit-section-body">
                  <div class="field-group">
                    <label>Status</label>
                    <div class="status-toggle">
                      <button
                        v-for="option in editPageStatusOptions"
                        :key="`edit-status-${option.value}`"
                        type="button"
                        class="toggle-btn"
                        :class="{ active: editForm.status === option.value }"
                        @click="setEditPageStatus(option.value)"
                      >
                        {{ option.label }}
                      </button>
                    </div>
                  </div>

                  <div class="field-group">
                    <label id="bulk-child-visibility-label">Child Page Visibility</label>
                    <div
                      ref="bulkChildVisibilityDropdownRef"
                      class="bulk-visibility-dropdown"
                    >
                      <button
                        type="button"
                        class="select-input bulk-visibility-dropdown__button"
                        :disabled="bulkChildVisibilitySaving || selectedPageSubpages.length === 0"
                        aria-haspopup="listbox"
                        :aria-expanded="bulkChildVisibilityMenuOpen ? 'true' : 'false'"
                        aria-labelledby="bulk-child-visibility-label"
                        @click="toggleBulkChildVisibilityMenu"
                        @keydown.escape.prevent="closeBulkChildVisibilityMenu"
                      >
                        <span>{{ bulkChildVisibilityDropdownLabel }}</span>
                      </button>
                      <div
                        v-if="bulkChildVisibilityMenuOpen"
                        class="bulk-visibility-dropdown__menu"
                        role="listbox"
                        aria-labelledby="bulk-child-visibility-label"
                      >
                        <button
                          v-for="option in bulkChildVisibilityStatusOptions"
                          :key="`bulk-child-status-${option.value}`"
                          type="button"
                          class="bulk-visibility-dropdown__option"
                          role="option"
                          @click="onBulkChildVisibilityStatusSelect(option.value)"
                        >
                          {{ option.label }}
                        </button>
                      </div>
                    </div>
                    <p class="field-hint">
                      Applies to all descendant pages under {{ pagePathFromSlug(selectedPage.slug) }} after confirmation.
                    </p>
                  </div>

                  <div class="field-group">
                    <label>Schedule</label>
                    <div class="schedule-row">
                      <div class="schedule-item">
                        <span class="schedule-label">Publish</span>
                        <VueDatePicker
                          v-model="editForm.publish_at"
                          :enable-time-picker="true"
                          :clearable="true"
                          :text-input="DATE_PICKER_TEXT_INPUT_OPTIONS"
                          :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
                          placeholder="Select date & time"
                          :teleport="true"
                          auto-apply
                          :min-date="minScheduleDate"
                          class="schedule-picker"
                          @update:model-value="queuePageAutosave"
                        />
                      </div>
                      <div class="schedule-item">
                        <span class="schedule-label">Unpublish</span>
                        <VueDatePicker
                          v-model="editForm.unpublish_at"
                          :enable-time-picker="true"
                          :clearable="true"
                          :text-input="DATE_PICKER_TEXT_INPUT_OPTIONS"
                          :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
                          placeholder="Select date & time"
                          :teleport="true"
                          auto-apply
                          :min-date="minScheduleDate"
                          class="schedule-picker"
                          @update:model-value="queuePageAutosave"
                        />
                      </div>
                    </div>
                    <p class="field-hint">Schedule when the page becomes visible or hidden. Only future dates can be selected.</p>
                  </div>

                  <div class="status-info-box">
                    <p v-if="editForm.status === 'init'"><strong>Init (new):</strong> Initial generated state; behaves like Hidden until first status change.</p>
                    <p><strong>Published:</strong> Page is publicly reachable and visible.</p>
                    <p><strong>Under Construction:</strong> URL stays reachable, but content is hidden for visitors.</p>
                    <p><strong>Hidden:</strong> Page is not publicly visible.</p>
                  </div>
                </div>
              </section>

              <section class="edit-section" :class="{ expanded: openEditSection === 'nav-menu' }">
                <button type="button" class="edit-section-header" @click="setOpenEditSection('nav-menu')">
                  <span class="edit-section-title">Menus</span>
                  <span class="edit-section-summary">{{ navMenuSectionSummary }}</span>
                  <span class="edit-section-chevron" :class="{ expanded: openEditSection === 'nav-menu' }">
                    <font-awesome-icon :icon="faChevronRight" />
                  </span>
                </button>
                <div v-show="openEditSection === 'nav-menu'" class="edit-section-body">
                  <div class="field-group">
                    <label class="checkbox-label">
                      <input type="checkbox" v-model="editForm.in_menu" @change="queuePageAutosave" />
                      <span>Include in nav menu</span>
                    </label>
                    <p class="field-hint">Show this page in the main navigation of the website.</p>
                    <div v-if="editForm.in_menu" class="menu-suboption">
                      <label class="checkbox-label">
                        <input type="checkbox" v-model="editForm.menu_show_as_top_level" @change="queuePageAutosave" />
                        <span>Show as top-level menu item</span>
                      </label>
                      <p class="field-hint">
                        Nested routes like <code>/page/route/name</code> are shown as top-level menu item
                        <strong>name</strong> in menu hierarchy.
                      </p>
                    </div>
                  </div>

                  <div v-if="editForm.in_menu" class="field-group">
                    <label>Alternative Page Link Title (optional)</label>
                    <div class="title-inputs">
                      <div class="lang-input">
                        <span class="lang-label">DE</span>
                        <input
                          type="text"
                          v-model="editForm.menu_title_de"
                          placeholder="Alternative German page link title"
                          class="text-input"
                          @blur="autoSavePageChanges"
                        />
                      </div>
                      <div class="lang-input">
                        <span class="lang-label">EN</span>
                        <input
                          type="text"
                          v-model="editForm.menu_title_en"
                          placeholder="Alternative English page link title"
                          class="text-input"
                          @blur="autoSavePageChanges"
                        />
                      </div>
                    </div>
                    <p class="field-hint">Renames only the page link entry (for example <code>/my/my</code>), not the parent node label.</p>
                  </div>

                  <div v-if="editForm.in_menu && selectedPageIsMenuParentNode" class="field-group">
                    <label>Alternative Parent Node Label (optional)</label>
                    <div class="title-inputs">
                      <div class="lang-input">
                        <span class="lang-label">DE</span>
                        <input
                          type="text"
                          v-model="editForm.menu_parent_title_de"
                          placeholder="Alternative German parent node title"
                          class="text-input"
                          @blur="autoSavePageChanges"
                        />
                      </div>
                      <div class="lang-input">
                        <span class="lang-label">EN</span>
                        <input
                          type="text"
                          v-model="editForm.menu_parent_title_en"
                          placeholder="Alternative English parent node title"
                          class="text-input"
                          @blur="autoSavePageChanges"
                        />
                      </div>
                    </div>
                    <p class="field-hint">Renames only the parent node label (for example <code>/my/</code>), not the page link entry.</p>
                  </div>

                  <div class="field-group">
                    <label class="checkbox-label">
                      <input type="checkbox" v-model="editForm.in_footer" @change="queuePageAutosave" />
                      <span>Include in footer menu</span>
                    </label>
                    <p class="field-hint">Show this page in the website footer links list.</p>
                  </div>
                </div>
              </section>

              <section class="edit-section" :class="{ expanded: openEditSection === 'sitemap' }">
                <button type="button" class="edit-section-header" @click="setOpenEditSection('sitemap')">
                  <span class="edit-section-title">Sitemap & SEO</span>
                  <span class="edit-section-summary">
                    {{ sitemapSectionSummary }}
                  </span>
                  <span class="edit-section-chevron" :class="{ expanded: openEditSection === 'sitemap' }">
                    <font-awesome-icon :icon="faChevronRight" />
                  </span>
                </button>
                <div v-show="openEditSection === 'sitemap'" class="edit-section-body">
                  <div class="field-group">
                    <label for="redirect-to">Redirect To</label>
                    <select
                      id="redirect-to"
                      v-model="editForm.redirect_to"
                      class="select-input"
                      @change="queuePageAutosave"
                    >
                      <option value="">No redirect</option>
                      <option
                        v-for="page in redirectPageOptions"
                        :key="page.slug"
                        :value="pagePathFromSlug(page.slug)"
                      >
                        {{ formatRedirectTargetOptionLabel(page) }}
                      </option>
                    </select>
                    <p class="field-hint">Redirect visitors to another page when they visit this one.</p>
                  </div>

                  <div class="field-group">
                    <label class="checkbox-label">
                      <input
                        type="checkbox"
                        :checked="robotsDisallowActive"
                        @change="setRobotsDisallowActive($event.target.checked)"
                      />
                      <span>Disallow subtree in robots.txt</span>
                    </label>
                    <p class="field-hint">Add automatic robots.txt rules for this route.</p>
                    <div v-if="robotsDisallowActive" class="crawler-suboption">
                      <label class="checkbox-label">
                        <input
                          type="checkbox"
                          :checked="robotsPageOnlyDisallow"
                          @change="setRobotsPageOnlyDisallow($event.target.checked)"
                        />
                        <span>Disallow page, allow children in robots.txt</span>
                      </label>
                    </div>
                  </div>

                  <div class="field-group">
                    <label for="sitemap-priority">Sitemap Priority</label>
                    <input
                      id="sitemap-priority"
                      v-model.number="editForm.sitemap_priority"
                      type="number"
                      class="text-input"
                      min="0"
                      max="1"
                      step="0.1"
                      placeholder="Auto"
                      @blur="autoSavePageChanges"
                    />
                    <p class="field-hint">
                      Default is depth-based: root 1.0, first level 0.8, second level 0.5, deeper 0.2.
                      Effective now:
                      <strong>
                        {{
                          editForm.sitemap_priority === '' || editForm.sitemap_priority === null
                            ? defaultSitemapPriority(selectedPage.slug).toFixed(1)
                            : Number(editForm.sitemap_priority).toFixed(1)
                        }}
                      </strong>
                    </p>
                  </div>

                  <div class="field-group">
                    <label for="sitemap-changefreq">Sitemap Change Frequency (optional)</label>
                    <select
                      id="sitemap-changefreq"
                      v-model="editForm.sitemap_changefreq"
                      class="select-input"
                      @change="queuePageAutosave"
                    >
                      <option
                        v-for="opt in sitemapChangefreqOptions"
                        :key="opt.value || 'unset'"
                        :value="opt.value"
                      >
                        {{ opt.label }}
                      </option>
                    </select>
                    <p class="field-hint">Used as `&lt;changefreq&gt;` in sitemap.xml for this page URL.</p>
                  </div>
                </div>
              </section>

              <section class="edit-section edit-section--danger" :class="{ expanded: openEditSection === 'delete' }">
                <button type="button" class="edit-section-header" @click="setOpenEditSection('delete')">
                  <span class="edit-section-title">Delete</span>
                  <span class="edit-section-summary">Danger zone</span>
                  <span class="edit-section-chevron" :class="{ expanded: openEditSection === 'delete' }">
                    <font-awesome-icon :icon="faChevronRight" />
                  </span>
                </button>
                <div v-show="openEditSection === 'delete'" class="edit-section-body">
                  <p class="delete-help">
                    Delete this page, or remove all descendant subpages under
                    <strong>{{ pagePathFromSlug(selectedPage.slug) }}</strong>.
                  </p>
                  <div class="delete-actions">
                    <button class="btn-danger" type="button" @click="confirmDelete(selectedPage)" :disabled="deletingSubpages || deleting">
                      Delete Page
                    </button>
                    <button
                      class="btn-danger btn-danger-secondary"
                      type="button"
                      @click="deleteSelectedSubpages"
                      :disabled="deletingSubpages || deleting || selectedPageSubpages.length === 0"
                    >
                      {{
                        deletingSubpages
                          ? 'Deleting Subpages...'
                          : `Delete Subpages (${selectedPageSubpages.length})`
                      }}
                    </button>
                  </div>
                  <p class="field-hint">
                    Delete subpages removes all descendants only. The current page stays in place.
                  </p>
                </div>
              </section>
            </div>
          </div>
        </div>

        <div v-else-if="showCreateDialog" class="page-editor page-editor--inline page-create">
          <div class="editor-header">
            <h2>Create New Page</h2>
            <button class="close-btn" @click="closeCreateDialog">
              <font-awesome-icon :icon="faXmark" />
            </button>
          </div>

          <div class="editor-body">
            <div class="field-group">
              <label for="new-slug">Slug (URL path) *</label>
              <div class="slug-input-wrap">
                <span class="slug-prefix">/</span>
                <input
                  id="new-slug"
                  ref="createSlugInput"
                  type="text"
                  v-model="createForm.slug"
                  placeholder="parent/child or my-page"
                  class="text-input slug-input"
                  @input="validateSlug"
                />
              </div>
              <p class="field-hint">Use lowercase letters, numbers, hyphens, and slashes for subpages.</p>
              <p v-if="createSlugRedirectConflictMessage" class="field-warning">
                {{ createSlugRedirectConflictMessage }}
              </p>
              <p v-if="slugError" class="field-error">{{ slugError }}</p>
            </div>

            <div class="field-group">
              <label for="new-title-de">Title (German)</label>
              <input
                id="new-title-de"
                ref="createTitleDeInput"
                type="text"
                v-model="createForm.title.de"
                placeholder="Page title in German"
                class="text-input"
              />
            </div>

            <div class="field-group">
              <label for="new-title-en">Title (English)</label>
              <input
                id="new-title-en"
                type="text"
                v-model="createForm.title.en"
                placeholder="Page title in English"
                class="text-input"
              />
            </div>

            <div class="field-group">
              <label>Initial Status</label>
              <div class="status-toggle">
                <button
                  v-for="option in createPageStatusOptions"
                  :key="`create-status-${option.value}`"
                  type="button"
                  class="toggle-btn"
                  :class="{ active: createForm.status === option.value }"
                  @click="createForm.status = option.value"
                >
                  {{ option.label }}
                </button>
              </div>
            </div>

            <div class="field-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="createForm.in_menu" />
                <span>Include in nav menu</span>
              </label>
            </div>

            <div class="field-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="createForm.in_footer" />
                <span>Include in footer menu</span>
              </label>
            </div>

            <div v-if="createForm.in_menu" class="field-group">
              <label>Alternative Page Link Title (optional)</label>
              <div class="title-inputs">
                <div class="lang-input">
                  <span class="lang-label">DE</span>
                  <input
                    type="text"
                    v-model="createForm.menu_title.de"
                    placeholder="Alternative German page link title"
                    class="text-input"
                  />
                </div>
                <div class="lang-input">
                  <span class="lang-label">EN</span>
                  <input
                    type="text"
                    v-model="createForm.menu_title.en"
                    placeholder="Alternative English page link title"
                    class="text-input"
                  />
                </div>
              </div>
              <p class="field-hint">Renames the page link label. Parent node labels can be set later on parent menu pages.</p>
            </div>
          </div>

          <div class="editor-actions">
            <button class="btn-secondary" @click="closeCreateDialog">Cancel</button>
            <button
              class="btn-primary"
              @click="createPage"
              :disabled="!canCreatePage"
            >
              {{ creating ? 'Creating...' : 'Create Page' }}
            </button>
          </div>
        </div>

        <div v-else-if="showMenuItemDialog" class="page-editor page-editor--inline page-create">
          <div class="editor-header">
            <h2>
              {{
                isEditingExternalMenuItem
                  ? (menuItemDialogTarget === 'menu' ? 'Edit Nav Menu Link' : 'Edit Footer Link')
                  : (menuItemDialogTarget === 'menu' ? 'Nav Menu Item' : 'Footer Item')
              }}
            </h2>
            <button class="close-btn" @click="closeMenuItemDialog">
              <font-awesome-icon :icon="faXmark" />
            </button>
          </div>

          <div class="editor-body">
            <div v-if="!isEditingExternalMenuItem" class="field-group">
              <label>Action</label>
              <div class="status-toggle">
                <button
                  type="button"
                  class="toggle-btn"
                  :class="{ active: menuItemDialogMode === 'create_page' }"
                  @click="menuItemDialogMode = 'create_page'"
                >
                  Create New Page
                </button>
                <button
                  type="button"
                  class="toggle-btn"
                  :class="{ active: menuItemDialogMode === 'link_internal' }"
                  @click="menuItemDialogMode = 'link_internal'"
                >
                  Link Existing Page
                </button>
                <button
                  type="button"
                  class="toggle-btn"
                  :class="{ active: menuItemDialogMode === 'external' }"
                  @click="menuItemDialogMode = 'external'"
                >
                  Add External Link
                </button>
              </div>
            </div>

            <div v-if="menuItemDialogMode === 'create_page'" class="field-group">
              <p class="field-hint">
                Continue to create a new page and automatically place it in
                {{ menuItemDialogTarget === 'menu' ? 'the nav menu' : 'the footer' }}.
              </p>
            </div>

            <div v-if="menuItemDialogMode === 'link_internal'" class="field-group">
              <label for="link-existing-page">Existing Page</label>
              <select id="link-existing-page" v-model="menuItemDialogInternalSlug" class="select-input">
                <option value="">Select page</option>
                <option
                  v-for="page in menuItemDialogLinkablePages"
                  :key="`menu-link-existing-${page.slug}`"
                  :value="page.slug"
                >
                  {{ pagePathFromSlug(page.slug) }} · {{ getPageTitle(page) }}
                </option>
              </select>
              <p class="field-hint">Pages already linked in this menu are excluded.</p>
            </div>

            <template v-if="menuItemDialogMode === 'external'">
              <div class="field-group">
                <label for="external-link-url">External URL</label>
                <input
                  id="external-link-url"
                  v-model="menuItemDialogExternal.url"
                  type="text"
                  class="text-input"
                  placeholder="https://example.com"
                />
              </div>

              <div class="field-group">
                <label>Display Type</label>
                <div class="status-toggle">
                  <button
                    type="button"
                    class="toggle-btn"
                    :class="{ active: menuItemDialogExternal.display_type === 'text' }"
                    @click="menuItemDialogExternal.display_type = 'text'"
                  >
                    Text
                  </button>
                  <button
                    type="button"
                    class="toggle-btn"
                    :class="{ active: menuItemDialogExternal.display_type === 'icon' }"
                    @click="menuItemDialogExternal.display_type = 'icon'"
                  >
                    Icon
                  </button>
                </div>
              </div>

              <div v-if="menuItemDialogExternal.display_type === 'text'" class="field-group">
                <label>Label</label>
                <div class="title-inputs">
                  <div class="lang-input">
                    <span class="lang-label">DE</span>
                    <input
                      v-model="menuItemDialogExternal.label.de"
                      type="text"
                      class="text-input"
                      placeholder="German label"
                    />
                  </div>
                  <div class="lang-input">
                    <span class="lang-label">EN</span>
                    <input
                      v-model="menuItemDialogExternal.label.en"
                      type="text"
                      class="text-input"
                      placeholder="English label"
                    />
                  </div>
                </div>
              </div>

              <div v-else class="field-group">
                <label for="external-link-icon">Icon</label>
                <select id="external-link-icon" v-model="menuItemDialogExternal.icon" class="select-input">
                  <option value="other">Other (Generic Link Icon)</option>
                  <option value="facebook">Facebook</option>
                  <option value="instagram">Instagram</option>
                  <option value="twitter">Twitter</option>
                  <option value="youtube">YouTube</option>
                  <option value="tiktok">TikTok</option>
                </select>
              </div>
            </template>

            <p v-if="menuItemDialogError" class="field-error">{{ menuItemDialogError }}</p>
          </div>

          <div class="editor-actions">
            <button
              v-if="isEditingExternalMenuItem"
              type="button"
              class="btn-danger btn-danger-secondary"
              @click="deleteEditingExternalMenuItem"
              :disabled="menuItemDialogSaving"
            >
              Delete External Link
            </button>
            <button type="button" class="btn-secondary" @click="closeMenuItemDialog">Cancel</button>
            <button type="button" class="btn-primary" @click="saveMenuItemDialog" :disabled="menuItemDialogSaving">
              {{ menuItemDialogSaving ? 'Saving...' : menuItemDialogPrimaryActionLabel }}
            </button>
          </div>
        </div>

        <div v-else class="page-editor-empty">
          <h2>Page Editor</h2>
          <p>Select a page from the sitemap to edit it, or click the + button to create a new page.</p>
        </div>
      </AdminStickySidebar>
      </div>

      <!-- Delete Confirmation -->
      <Teleport to="body">
        <div v-if="deleteConfirm" class="page-editor-overlay" @click.self="deleteConfirm = null">
          <div class="page-editor page-delete">
            <div class="editor-header">
              <h2>Delete Page</h2>
              <button class="close-btn" @click="deleteConfirm = null">
                <font-awesome-icon :icon="faXmark" />
              </button>
            </div>
            
            <div class="editor-body">
              <p class="confirm-text">Are you sure you want to delete this page?</p>
              <div class="delete-page-info">
                <span class="tree-icon">
                  <font-awesome-icon :icon="faFileLines" />
                </span>
                <span class="tree-path">{{ pagePathFromSlug(deleteConfirm.slug) }}</span>
                <span class="tree-name">{{ getPageTitle(deleteConfirm) }}</span>
              </div>
              <p class="confirm-warning">This action cannot be undone. The page content and all its sections will be removed.</p>
            </div>

            <div class="editor-actions">
              <button class="btn-secondary" @click="deleteConfirm = null">Cancel</button>
              <button class="btn-danger" @click="doDeletePage" :disabled="deleting">
                {{ deleting ? 'Deleting...' : 'Delete Page' }}
              </button>
            </div>
          </div>
        </div>
      </Teleport>

      <MediaLibrary
        :is-open="topbarLogoPickerOpen"
        :current-url="topbarLogoUrl || ''"
        source-context="sitemap-topbar-logo"
        :allow-clear-selection="Boolean(topbarLogoUrl)"
        @close="closeTopbarLogoPicker"
        @select="onTopbarLogoSelected"
      />

      <MediaLibrary
        :is-open="footerLogoPickerOpen"
        :current-url="footerLogoUrl || ''"
        source-context="sitemap-footer-logo"
        :allow-clear-selection="Boolean(footerLogoUrl)"
        @close="closeFooterLogoPicker"
        @select="onFooterLogoSelected"
      />
      </template>
    </template>

    <template v-else-if="activeTab === 'redirects'">
      <div class="redirects-layout">
        <div class="redirects-card sitemap-meta-card">
          <div class="redirects-card__header">
            <h2>Sitemap.xml</h2>
            <button class="btn-secondary btn-sm" @click="refreshSitemapSummary" :disabled="summaryRefreshing">
              {{ summaryRefreshing ? 'Refreshing…' : 'Refresh' }}
            </button>
          </div>
          <div class="sitemap-meta-grid" v-if="sitemapSummary">
            <div class="meta-item">
              <span class="meta-label">Public URLs</span>
              <strong class="meta-value">{{ sitemapSummary.entry_count }}</strong>
            </div>
            <div class="meta-item">
              <span class="meta-label">Hidden Subtrees</span>
              <strong class="meta-value">{{ sitemapSummary.hidden_subtree_roots?.length || 0 }}</strong>
            </div>
            <div class="meta-item">
              <span class="meta-label">Redirects</span>
              <strong class="meta-value">{{ sitemapSummary.redirect_count || 0 }}</strong>
            </div>
          </div>
          <p v-if="sitemapSummary?.generated_at" class="field-hint">
            Last generated: {{ formatTimestamp(sitemapSummary.generated_at) }}
          </p>
          <p
            v-if="sitemapSummary && sitemapSummary.enabled === false"
            class="field-error"
          >
            Sitemap is disabled on subdomain instances (host: {{ sitemapSummary.disabled_host || 'unknown' }}).
          </p>
          <div class="redirects-actions">
            <a
              v-if="sitemapSummary?.enabled !== false"
              class="btn-primary"
              href="/sitemap.xml"
              target="_blank"
              rel="noopener"
            >
              Open /sitemap.xml
            </a>
            <button
              class="btn-secondary"
              @click="regenerateSitemapXml"
              :disabled="summaryRefreshing || sitemapSummary?.enabled === false"
            >
              Regenerate Now
            </button>
          </div>
          <p v-if="summaryError" class="field-error">{{ summaryError }}</p>
        </div>

        <div class="redirects-card">
          <div class="redirects-card__header">
            <h2>Add Redirect</h2>
          </div>
          <div class="redirect-form-grid">
            <label class="field-group">
              <span>From Path</span>
              <input
                v-model="redirectForm.source_path"
                type="text"
                class="text-input"
                placeholder="/old/path or /old-*"
              />
              <p class="field-hint">Supports wildcards: <code>*</code> for any number of characters, <code>?</code> for one character.</p>
            </label>
            <label class="field-group">
              <span>To Page</span>
              <select
                v-model="redirectForm.target_path"
                class="select-input"
                :disabled="!redirectStatusSelection.requiresTarget"
              >
                <option value="">Select target page</option>
                <option
                  v-for="page in redirectTargetPageOptions"
                  :key="`redirect-target-${page.slug}`"
                  :value="pagePathFromSlug(page.slug)"
                >
                  {{ formatRedirectTargetOptionLabel(page) }}
                </option>
              </select>
            </label>
            <label class="field-group">
              <span>Status</span>
              <select v-model.number="redirectForm.status_code" class="select-input">
                <option
                  v-for="statusOption in redirectStatusOptions"
                  :key="`redirect-status-${statusOption.code}`"
                  :value="statusOption.code"
                >
                  {{ statusOption.label }}
                </option>
              </select>
              <p class="field-hint">{{ redirectStatusSelection.description }}</p>
            </label>
            <label class="field-group">
              <span>Expires At (optional)</span>
              <VueDatePicker
                :model-value="serverWallDateTimeToLocalDate(redirectForm.expires_at)"
                :enable-time-picker="true"
                :is-24="true"
                :clearable="true"
                :text-input="DATE_PICKER_TEXT_INPUT_OPTIONS"
                :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
                placeholder="Select date & time"
                :teleport="true"
                auto-apply
                class="schedule-picker"
                @update:model-value="redirectForm.expires_at = localDateToServerWallDateTime($event)"
              />
            </label>
          </div>
          <p
            v-if="redirectStatusSelection.requiresTarget && redirectTargetPageOptions.length === 0"
            class="field-hint"
          >
            No target pages available yet.
          </p>
          <p
            v-else-if="!redirectStatusSelection.requiresTarget"
            class="field-hint"
          >
            410 marks this URL as intentionally removed (Gone) and does not redirect to another page.
          </p>
          <div class="redirects-actions">
            <button
              class="btn-primary"
              @click="createRedirect"
              :disabled="creatingRedirect || (redirectStatusSelection.requiresTarget && !redirectForm.target_path)"
            >
              {{ creatingRedirect ? 'Creating…' : 'Create Redirect' }}
            </button>
            <button class="btn-secondary" @click="resetRedirectForm">
              Reset
            </button>
          </div>
          <p v-if="redirectCreateError" class="field-error">{{ redirectCreateError }}</p>
        </div>

        <div class="redirects-card">
          <div class="redirects-card__header">
            <h2>Redirects</h2>
            <div class="redirects-header-controls">
              <label class="checkbox-label">
                <input type="checkbox" v-model="redirectMultiSelectMode" />
                <span>Multi select</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="showExpiredRedirects" />
                <span>Show expired</span>
              </label>
            </div>
          </div>
          <div class="redirect-controls">
            <label class="field-group redirect-controls__field">
              <span>Sort By</span>
              <select v-model="redirectSortBy" class="select-input">
                <option
                  v-for="option in redirectSortOptions"
                  :key="`redirect-sort-${option.value}`"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label class="field-group redirect-controls__field">
              <span>Type Tag</span>
              <select v-model="redirectKindFilter" class="select-input">
                <option
                  v-for="option in redirectKindFilterOptions"
                  :key="`redirect-kind-filter-${option.value}`"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label class="field-group redirect-controls__field">
              <span>Status Tag</span>
              <select v-model="redirectStatusFilter" class="select-input">
                <option
                  v-for="option in redirectStatusFilterOptions"
                  :key="`redirect-status-filter-${option.value}`"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </label>
          </div>
          <div v-if="filteredRedirects.length > 0" class="redirect-bulk-actions">
            <button
              class="btn-secondary btn-sm"
              type="button"
              :disabled="selectedRedirectCount === 0 || deletingRedirects"
              @click="clearRedirectSelection"
            >
              Clear Selection
            </button>
            <button
              class="btn-secondary btn-sm"
              type="button"
              :disabled="redirectsLoading || deletingRedirects"
              @click="toggleSelectAllFilteredRedirects"
            >
              {{ allFilteredRedirectsSelected ? 'Clear Filter Selection' : 'Select All' }}
            </button>
            <button
              class="btn-danger btn-sm redirect-bulk-actions__delete"
              type="button"
              :disabled="selectedRedirectCount === 0 || deletingRedirects"
              @click="deleteSelectedRedirects"
            >
              {{ deletingRedirects ? 'Deleting…' : `Delete Selected (${selectedRedirectCount})` }}
            </button>
          </div>
          <div v-if="redirectsLoading" class="loading-state loading-state--compact">Loading redirects...</div>
          <div v-else-if="filteredRedirects.length === 0" class="empty-pages">No redirects yet.</div>
          <div v-else class="redirect-list">
            <template v-for="(item, index) in filteredRedirects" :key="item.id">
              <div v-if="isFirstGeneratedRedirect(index)" class="generated-group-header">
                <strong>Generated Redirects</strong>
              </div>
              <div
                class="redirect-item"
                :class="{
                  'redirect-item--inactive': !item.is_active,
                  'redirect-item--selected': isRedirectSelected(item),
                  'redirect-item--editing': isRedirectEditing(item),
                }"
                role="button"
                tabindex="0"
                :aria-pressed="isRedirectSelected(item) ? 'true' : 'false'"
                @click="handleRedirectItemClick(item)"
                @keydown.enter.prevent="handleRedirectItemClick(item)"
                @keydown.space.prevent="handleRedirectItemClick(item)"
              >
              <div class="redirect-row">
                <div class="redirect-main">
                  <div class="redirect-paths">
                    <span class="tree-path">{{ item.source_path }}</span>
                    <span class="redirect-arrow">→</span>
                    <span class="tree-path">{{ item.target_path || '410 Gone (Removed)' }}</span>
                  </div>
                  <div class="redirect-meta">
                    <span class="badge" :class="item.kind === 'generated' ? 'generated' : 'menu'">
                      {{ item.kind === 'generated' ? 'Generated' : 'Custom' }}
                    </span>
                    <span class="badge protocol" :class="`protocol-${resolveRedirectProtocolTag(item)}`">
                      {{ formatRedirectProtocolLabel(item) }}
                    </span>
                    <span class="badge status">{{ item.status_code }}</span>
                    <span
                      class="badge"
                      :class="item.is_active ? 'published' : 'draft'"
                    >
                      {{ item.is_active ? 'Active' : 'Inactive' }}
                    </span>
                    <span v-if="item.is_expired" class="badge draft">Expired</span>
                    <div v-if="item.kind === 'custom'" class="redirect-custom-meta">
                      <span class="redirect-kv">
                        <span class="redirect-kv__label">Hits</span>
                        <strong class="redirect-kv__value">{{ formatRedirectHitCount(item.anonymous_hit_count) }}</strong>
                      </span>
                      <span v-if="item.created_at" class="redirect-kv">
                        <span class="redirect-kv__label">Created</span>
                        <strong class="redirect-kv__value">{{ formatRedirectMetaTimestamp(item.created_at) }}</strong>
                      </span>
                    </div>
                    <span v-if="item.expires_at" class="redirect-expiry">
                      Expires: {{ formatTimestamp(item.expires_at) }}
                    </span>
                    <span v-if="item.kind !== 'custom' && item.created_at" class="redirect-expiry">
                      Created: {{ formatTimestamp(item.created_at) }}
                    </span>
                  </div>
                </div>
                <div class="redirect-actions" @click.stop>
                  <button
                    class="btn-secondary btn-sm"
                    type="button"
                    :disabled="deletingRedirects || savingRedirectEdit"
                    @click="startRedirectEdit(item)"
                  >
                    Edit
                  </button>
                </div>
              </div>
              <div v-if="isRedirectEditing(item)" class="redirect-edit-panel" @click.stop>
                <div class="redirect-form-grid redirect-form-grid--edit">
                  <template v-if="item.kind === 'custom'">
                    <label class="field-group">
                      <span>From Path</span>
                      <input
                        v-model="redirectEditForm.source_path"
                        type="text"
                        class="text-input"
                        placeholder="/old/path or /old-*"
                      />
                    </label>
                    <label class="field-group">
                      <span>To Path</span>
                      <input
                        v-model="redirectEditForm.target_path"
                        type="text"
                        class="text-input"
                        placeholder="/new/path or https://example.com"
                        :disabled="!redirectEditStatusSelection.requiresTarget"
                      />
                      <p class="field-hint">
                        Use internal paths or absolute <code>http(s)</code> URLs.
                      </p>
                    </label>
                    <label class="field-group">
                      <span>Quick Select Target Page</span>
                      <select
                        :value="redirectEditForm.target_path"
                        class="select-input"
                        :disabled="!redirectEditStatusSelection.requiresTarget"
                        @change="redirectEditForm.target_path = $event.target.value"
                      >
                        <option value="">Select target page</option>
                        <option
                          v-for="page in redirectEditTargetPageOptions"
                          :key="`redirect-edit-target-${item.id}-${page.slug}`"
                          :value="pagePathFromSlug(page.slug)"
                        >
                          {{ formatRedirectTargetOptionLabel(page) }}
                        </option>
                      </select>
                    </label>
                    <label class="field-group">
                      <span>Status</span>
                      <select v-model.number="redirectEditForm.status_code" class="select-input">
                        <option
                          v-for="statusOption in redirectStatusOptions"
                          :key="`redirect-edit-status-${item.id}-${statusOption.code}`"
                          :value="statusOption.code"
                        >
                          {{ statusOption.label }}
                        </option>
                      </select>
                      <p class="field-hint">{{ redirectEditStatusSelection.description }}</p>
                    </label>
                    <label class="field-group">
                      <span>Expires At (optional)</span>
                      <VueDatePicker
                        :model-value="serverWallDateTimeToLocalDate(redirectEditForm.expires_at)"
                        :enable-time-picker="true"
                        :is-24="true"
                        :clearable="true"
                        :text-input="DATE_PICKER_TEXT_INPUT_OPTIONS"
                        :formats="DATE_PICKER_DATE_TIME_DISPLAY_FORMATS"
                        placeholder="Select date & time"
                        :teleport="true"
                        auto-apply
                        class="schedule-picker"
                        @update:model-value="redirectEditForm.expires_at = localDateToServerWallDateTime($event)"
                      />
                    </label>
                  </template>
                  <div class="field-group redirect-enabled-field">
                    <label class="checkbox-label">
                      <input
                        :checked="redirectEditForm.is_active"
                        :disabled="savingRedirectEdit || deletingRedirects"
                        type="checkbox"
                        @change="onRedirectEnabledChange(item, $event.target.checked)"
                      />
                      <span>Enable redirect</span>
                    </label>
                  </div>
                </div>
                <div v-if="item.kind === 'custom'" class="redirects-actions">
                  <button
                    class="btn-primary btn-sm"
                    type="button"
                    :disabled="savingRedirectEdit || deletingRedirects"
                    @click="saveRedirectEdit"
                  >
                    {{ savingRedirectEdit ? 'Saving…' : 'Save Redirect' }}
                  </button>
                  <button
                    class="btn-secondary btn-sm"
                    type="button"
                    :disabled="savingRedirectEdit"
                    @click="cancelRedirectEdit"
                  >
                    Cancel
                  </button>
                </div>
                <p v-if="redirectEditError" class="field-error">{{ redirectEditError }}</p>
              </div>
            </div>
            </template>
          </div>
          <p v-if="redirectListError" class="field-error">{{ redirectListError }}</p>
        </div>
      </div>
    </template>

    <template v-else-if="activeTab === 'stats'">
      <div class="stats-layout">
        <div class="redirects-card stats-overview-card">
          <div class="redirects-card__header">
            <h2>Stats</h2>
            <div class="redirects-actions">
              <button
                class="btn-secondary btn-sm"
                type="button"
                :disabled="sitemapStatsLoading || sitemapStatsResetting"
                @click="loadSitemapStats"
              >
                {{ sitemapStatsLoading ? 'Refreshing…' : 'Refresh' }}
              </button>
              <button
                class="btn-danger btn-sm"
                type="button"
                :disabled="sitemapStatsLoading || sitemapStatsResetting || sitemapStatsPublicPages.length === 0"
                @click="resetSitemapStats"
              >
                {{ sitemapStatsResetting ? 'Resetting…' : 'Reset Page Hits' }}
              </button>
            </div>
          </div>
          <div class="stats-summary-grid">
            <div class="meta-item">
              <span class="meta-label">Total Hits</span>
              <strong class="meta-value">{{ formatAnonymousHitCount(sitemapStatsTotalHits) }}</strong>
            </div>
            <div class="meta-item">
              <span class="meta-label">Tracked Pages</span>
              <strong class="meta-value">{{ formatAnonymousHitCount(sitemapStatsTrackedPageCount) }}</strong>
            </div>
            <div class="meta-item">
              <span class="meta-label">Selected Hits</span>
              <strong class="meta-value">{{ formatAnonymousHitCount(sitemapStatsSelectedHits) }}</strong>
            </div>
            <div class="meta-item stats-scope-item">
              <span class="meta-label">Scope</span>
              <strong class="meta-value stats-scope-value">{{ sitemapStatsScopeLabel }}</strong>
            </div>
          </div>
          <p v-if="sitemapStatsRangeLabel" class="field-hint">{{ sitemapStatsRangeLabel }}</p>
          <p v-if="sitemapStatsError" class="field-error">{{ sitemapStatsError }}</p>
        </div>

        <div class="redirects-card stats-card">
          <div class="redirects-card__header">
            <h2>Daily Hits</h2>
            <div class="redirects-actions stats-range-actions">
              <span class="field-hint">{{ sitemapStatsScopeLabel }}</span>
              <select
                v-model="selectedSitemapStatsRange"
                class="select-input stats-range-select"
                :disabled="sitemapStatsLoading || sitemapStatsResetting"
                aria-label="Daily hits range"
                @change="loadSitemapStats"
              >
                <option
                  v-for="option in sitemapStatsRangeOptions"
                  :key="`stats-range-${option.value}`"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </div>
          </div>
          <div v-if="sitemapStatsLoading && !sitemapStatsPayload" class="loading-state loading-state--compact">Loading timeline...</div>
          <div v-else-if="sitemapStatsDailySeries.length === 0" class="empty-pages">No timeline range available.</div>
          <div v-else-if="sitemapStatsDailyTotal === 0" class="empty-pages">
            No daily hits recorded for this range yet.
          </div>
          <div v-else ref="statsTimelineScrollRef" class="stats-chart-scroll">
            <svg
              class="stats-timeline-svg"
              :viewBox="`0 0 ${sitemapStatsTimelineLayout.width} ${sitemapStatsTimelineLayout.height}`"
              :style="{
                width: `${sitemapStatsTimelineLayout.width}px`,
                height: `${sitemapStatsTimelineLayout.height}px`,
              }"
              role="img"
              aria-label="Daily page hits"
            >
              <g
                v-for="tick in sitemapStatsTimelineLayout.yTicks"
                :key="`stats-y-${tick.value}`"
              >
                <line
                  :class="tick.value === 0 ? 'stats-timeline-axis' : 'stats-timeline-grid'"
                  :x1="sitemapStatsTimelineLayout.left"
                  :x2="sitemapStatsTimelineLayout.left + sitemapStatsTimelineLayout.plotWidth"
                  :y1="tick.y"
                  :y2="tick.y"
                />
                <text
                  class="stats-timeline-y-label"
                  :x="sitemapStatsTimelineLayout.left - 8"
                  :y="tick.y + 4"
                  text-anchor="end"
                  :font-size="sitemapStatsTimelineLayout.yLabelFontSize"
                >
                  {{ formatAnonymousHitCount(tick.value) }}
                </text>
              </g>
              <g
                v-for="bar in sitemapStatsTimelineLayout.bars"
                :key="bar.day"
              >
                <rect
                  class="stats-timeline-bar"
                  :x="bar.x"
                  :y="bar.y"
                  :width="bar.width"
                  :height="bar.height"
                  rx="3"
                />
                <title>{{ bar.day }}: {{ formatAnonymousHitCount(bar.count) }} hits</title>
                <text
                  v-if="bar.showLabel"
                  class="stats-timeline-label"
                  :x="bar.x + bar.width / 2"
                  :y="sitemapStatsTimelineLayout.height - 12"
                  text-anchor="middle"
                  :font-size="sitemapStatsTimelineLayout.xLabelFontSize"
                >
                  {{ bar.label }}
                </text>
              </g>
            </svg>
          </div>
        </div>

        <div class="redirects-card stats-card">
          <div class="redirects-card__header">
            <h2>Page Hits</h2>
            <div class="redirects-actions">
              <span class="field-hint">{{ formatAnonymousHitCount(sitemapStatsVisiblePages.length) }} public pages</span>
              <button
                v-if="sitemapStatsGeneratedPageCount > 0"
                type="button"
                class="btn-secondary btn-sm"
                @click="toggleStatsGeneratedPagesExpanded"
              >
                {{ statsGeneratedPagesExpanded ? 'Collapse Generated' : `Show Generated (${formatAnonymousHitCount(sitemapStatsGeneratedPageCount)})` }}
              </button>
            </div>
          </div>
          <div v-if="sitemapStatsLoading && !sitemapStatsPayload" class="loading-state loading-state--compact">Loading stats...</div>
          <div v-else-if="sitemapStatsVisiblePages.length === 0" class="empty-pages">No public pages available.</div>
          <div v-else class="stats-chart-scroll">
            <svg
              class="stats-tree-svg"
              :viewBox="`0 0 ${sitemapStatsTreeLayout.width} ${sitemapStatsTreeLayout.height}`"
              role="img"
              aria-label="Page hit dendrogram"
            >
              <path
                v-for="link in sitemapStatsTreeLayout.links"
                :key="link.key"
                class="stats-tree-link"
                :d="getStatsLinkPath(link)"
              />
              <g
                v-for="node in sitemapStatsTreeLayout.nodes"
                :key="node.id || 'stats-root'"
                class="stats-tree-node"
                :class="{
                  selected: isStatsNodeSelected(node),
                  'stats-tree-node--generated-group': node.kind === 'generated_group',
                }"
                :transform="`translate(${node.x}, ${node.y})`"
                tabindex="0"
                role="button"
                :aria-pressed="isStatsNodeSelected(node) ? 'true' : 'false'"
                @click="selectStatsNode(node)"
                @keydown.enter.prevent="selectStatsNode(node)"
                @keydown.space.prevent="selectStatsNode(node)"
              >
                <circle
                  :r="getStatsNodeRadius(node)"
                  :fill="getStatsNodeFill(node)"
                />
                <text class="stats-tree-node__label" x="20" y="-3">{{ getStatsNodeLabel(node) }}</text>
                <text class="stats-tree-node__value" x="20" y="14">
                  {{ formatAnonymousHitCount(node.hitCount) }} hits
                </text>
              </g>
            </svg>
          </div>
        </div>
      </div>
    </template>

    <template v-else-if="activeTab === 'robots'">
      <div class="robots-layout">
        <div class="redirects-card">
          <div class="redirects-card__header">
            <h2>robots.txt</h2>
            <a class="btn-secondary btn-sm" href="/robots.txt" target="_blank" rel="noopener">Open /robots.txt</a>
          </div>
          <p class="field-hint">
            Automatic rules are read-only and always generated by the system to prevent overwrite conflicts.
          </p>
          <p
            v-if="robotsPayload?.subdomain_disallow_all"
            class="field-error"
          >
            Subdomain instance detected ({{ robotsPayload?.subdomain_host || 'unknown' }}): automatic rules disallow all crawling.
          </p>
          <p v-if="robotsError" class="field-error">{{ robotsError }}</p>
        </div>

        <div class="redirects-card">
          <div class="redirects-card__header">
            <h2>Automatic (Read-Only)</h2>
          </div>
          <div v-if="robotsLoading" class="loading-state loading-state--compact">Loading robots rules...</div>
          <textarea
            v-else
            class="robots-textarea robots-textarea--readonly"
            :value="robotsPayload?.automatic_text || ''"
            readonly
          />
          <p class="field-hint">
            Includes subdomain behavior and disallow rules for pages hidden from sitemap.
          </p>
        </div>

        <div class="redirects-card">
          <div class="redirects-card__header">
            <h2>Custom Rules</h2>
          </div>
          <textarea
            v-model="robotsCustomText"
            class="robots-textarea"
            placeholder="Add custom robots.txt directives here..."
          />
          <div class="redirects-actions">
            <button class="btn-primary" @click="saveRobots" :disabled="robotsSaving">
              {{ robotsSaving ? 'Saving…' : 'Save Custom Rules' }}
            </button>
          </div>
        </div>

        <div class="redirects-card">
          <div class="redirects-card__header">
            <h2>Effective robots.txt Preview</h2>
          </div>
          <textarea
            class="robots-textarea robots-textarea--readonly"
            :value="robotsPayload?.merged_text || ''"
            readonly
          />
        </div>
      </div>
    </template>

    <template v-else-if="activeTab === 'caching'">
      <div class="caching-layout">
        <div class="redirects-card">
          <div class="redirects-card__header">
            <h2>.htaccess Client Caching</h2>
          </div>
          <div
            v-if="cachingLoading || (!cachingPayload && !cachingError)"
            class="loading-state loading-state--compact"
          >
            Loading caching rules...
          </div>
          <template v-else>
            <div class="caching-table-wrap">
              <table class="caching-table">
                <thead>
                  <tr>
                    <th>Enabled</th>
                    <th>Data Type</th>
                    <th>Lifetime</th>
                    <th>Extensions</th>
                    <th>MIME Types</th>
                    <th>Cache-Control</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="rule in cachingRules"
                    :key="rule.id"
                    :class="{ 'is-disabled': !rule.enabled }"
                  >
                    <td>
                      <label class="caching-toggle">
                        <input type="checkbox" v-model="rule.enabled" />
                      </label>
                    </td>
                    <td>
                      <strong>{{ rule.label }}</strong>
                      <span v-if="rule.immutable" class="badge generated">Immutable</span>
                    </td>
                    <td>
                      <div class="caching-duration">
                        <input
                          v-model.number="rule.amount"
                          type="number"
                          min="0"
                          step="1"
                          class="text-input caching-duration__amount"
                          :max="getCachingMaxForUnit(rule.unit)"
                          :disabled="!rule.enabled"
                        />
                        <select
                          :value="rule.unit"
                          class="select-input caching-duration__unit"
                          :disabled="!rule.enabled"
                          @change="onCachingUnitChange(rule, $event.target.value)"
                        >
                          <option
                            v-for="option in cachingUnitOptions"
                            :key="`caching-unit-${rule.id}-${option.value}`"
                            :value="option.value"
                          >
                            {{ option.label }}
                          </option>
                        </select>
                      </div>
                    </td>
                    <td>
                      <span class="caching-code-list">{{ formatCachingList(rule.extensions, '.') }}</span>
                    </td>
                    <td>
                      <span class="caching-code-list">{{ formatCachingList(rule.mime_types) }}</span>
                    </td>
                    <td>
                      <code class="caching-cache-control">{{ formatCachingCacheControl(rule) }}</code>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="redirects-actions caching-actions">
              <button
                class="btn-primary"
                @click="saveCachingRules"
                :disabled="cachingSaving || cachingLoading || cachingSaveDisabled"
              >
                {{ cachingSaving ? 'Saving...' : 'Save Rules' }}
              </button>
              <button
                class="btn-secondary"
                @click="resetCachingRulesToDefaults"
                :disabled="cachingSaving || cachingLoading || cachingResetDisabled"
              >
                Reset to Default
              </button>
              <button
                class="btn-secondary"
                @click="copyHtaccessCachingRules"
                :disabled="cachingSaving || cachingLoading || cachingHasUnsavedChanges || !cachingPreviewText"
              >
                Copy .htaccess
              </button>
            </div>
            <p v-if="cachingHasUnsavedChanges" class="field-warning">
              Save rules before copying the updated .htaccess snippet.
            </p>
            <p v-if="cachingError" class="field-error">{{ cachingError }}</p>
            <p v-else-if="cachingStatus" class="field-success">{{ cachingStatus }}</p>
          </template>
        </div>

        <div class="redirects-card">
          <div class="redirects-card__header">
            <h2>.htaccess Preview</h2>
          </div>
          <textarea
            class="robots-textarea robots-textarea--readonly htaccess-textarea"
            :value="cachingPreviewText"
            readonly
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  faArrowUpRightFromSquare,
  faBars,
  faChevronRight,
  faClock,
  faFileLines,
  faFlask,
  faFolder,
  faGear,
  faGlobe,
  faHardDrive,
  faHouse,
  faLink,
  faNewspaper,
  faPaintbrush,
  faPlug,
  faPuzzlePiece,
  faShieldHalved,
  faXmark,
} from '@fortawesome/free-solid-svg-icons';
import draggable from 'vuedraggable';
import { VueDatePicker } from '@vuepic/vue-datepicker';
import '@vuepic/vue-datepicker/dist/main.css';
import * as api from '../../services/api.js';
import { resolveApiBase } from '../../services/apiBase.js';
import {
  DATE_PICKER_DATE_TIME_DISPLAY_FORMATS,
  DATE_PICKER_TEXT_INPUT_OPTIONS,
  formatDateTimeLocalForServerTimezone,
  formatInstantInServerTimezone,
  getCurrentServerDate,
  localDateToServerWallDateTime,
  parseRevisionTimestamp,
  serverWallDateTimeToInstantDate,
  serverWallDateTimeToLocalDate,
} from '../../utils/revisionTime.js';
import AdminPageTabs from '../../components/admin/AdminPageTabs.vue';
import AutosaveToast from '../../components/admin/AutosaveToast.vue';
import AdminStickySidebar from '../../components/admin/AdminStickySidebar.vue';
import SitemapMenuTreeNode from '../../components/admin/SitemapMenuTreeNode.vue';
import MediaLibrary from '../../components/ui/MediaLibrary.vue';

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const pages = ref([]);
const selectedPage = ref(null);
const showCreateDialog = ref(false);
const showMenuItemDialog = ref(false);
const deleteConfirm = ref(null);
const saving = ref(false);
const pageAutosavePending = ref(false);
const pageAutosaveStatus = ref('idle');
const pageAutosaveError = ref('');
const lastSavedEditSnapshot = ref('');
const bulkChildVisibilityStatus = ref('');
const bulkChildVisibilityMenuOpen = ref(false);
const bulkChildVisibilityInteracting = ref(false);
const bulkChildVisibilitySaving = ref(false);
const creating = ref(false);
const renaming = ref(false);
const deleting = ref(false);
const deletingSubpages = ref(false);
const subtreeReorderEnabled = ref(false);
const migratingSubtree = ref(false);
const subtreeMoveError = ref('');
const subtreeDrag = reactive({
  sourceSlug: '',
  hoveredTargetSlug: '',
});
const minScheduleDate = computed(() => getCurrentServerDate());
const pageAutosaveTone = computed(() => {
  if (pageAutosaveError.value) return 'error';
  return pageAutosaveStatus.value;
});
const pageAutosaveMessage = computed(() => {
  if (pageAutosaveError.value) return `Auto-save failed: ${pageAutosaveError.value}`;
  if (pageAutosaveStatus.value === 'saving') return 'Saving changes...';
  if (pageAutosaveStatus.value === 'queued') return 'Saving latest changes...';
  if (pageAutosaveStatus.value === 'saved') return 'All changes saved';
  return '';
});
let bulkChildVisibilityInteractionTimer = null;
let pageAutosaveStatusTimer = null;
let statsTimelineResizeObserver = null;
let statsTimelineObservedElement = null;
const createSlugInput = ref(null);
const createTitleDeInput = ref(null);
const bulkChildVisibilityDropdownRef = ref(null);
const statsTimelineScrollRef = ref(null);
const pageTabs = Object.freeze([
  { id: 'sitemap', label: 'Pages', to: '/admin/sitemap/pages' },
  { id: 'redirects', label: 'Redirects', to: '/admin/sitemap/redirects' },
  { id: 'robots', label: 'Robots', to: '/admin/sitemap/robots' },
  { id: 'caching', label: 'Caching', to: '/admin/sitemap/caching' },
  { id: 'stats', label: 'Stats', to: '/admin/sitemap/stats' },
]);
const SITEMAP_TAB_BY_SLUG = {
  pages: 'sitemap',
  sitemap: 'sitemap',
  redirects: 'redirects',
  stats: 'stats',
  robots: 'robots',
  caching: 'caching',
};
const activeTab = computed(() => {
  const slug = String(route.path || '').split('/')[3] || '';
  return SITEMAP_TAB_BY_SLUG[slug] || 'sitemap';
});
const sitemapSummary = ref(null);
const summaryRefreshing = ref(false);
const summaryError = ref('');
const redirects = ref([]);
const redirectsLoading = ref(false);
const redirectListError = ref('');
const creatingRedirect = ref(false);
const deletingRedirects = ref(false);
const selectedRedirectIds = ref([]);
const redirectMultiSelectMode = ref(false);
const redirectCreateError = ref('');
const editingRedirectId = ref('');
const savingRedirectEdit = ref(false);
const redirectEditError = ref('');
const showExpiredRedirects = ref(false);
const sitemapStatsPayload = ref(null);
const sitemapStatsLoading = ref(false);
const sitemapStatsError = ref('');
const sitemapStatsResetting = ref(false);
const selectedStatsPageId = ref('');
const selectedSitemapStatsRange = ref('30');
const statsTimelineContainerWidth = ref(720);
const statsGeneratedPagesExpanded = ref(false);
const robotsPayload = ref(null);
const robotsLoading = ref(false);
const robotsSaving = ref(false);
const robotsError = ref('');
const robotsCustomText = ref('');
const cachingPayload = ref(null);
const cachingRules = ref([]);
const cachingLoading = ref(false);
const cachingSaving = ref(false);
const cachingError = ref('');
const cachingStatus = ref('');
const cachingLastSavedSnapshot = ref('');
const navExternalLinks = ref([]);
const footerExternalLinks = ref([]);
const topbarLogoUrl = ref(null);
const topbarLogoPickerOpen = ref(false);
const footerLogoUrl = ref(null);
const footerLogoPickerOpen = ref(false);
const navigationLinksSaving = ref(false);
const navigationLinksError = ref('');
const menuItemDialogTarget = ref('menu');
const menuItemDialogMode = ref('create_page');
const menuItemDialogInternalSlug = ref('');
const menuItemDialogEditingExternalId = ref('');
const menuItemDialogSaving = ref(false);
const menuItemDialogError = ref('');
const menuItemDialogExternal = reactive({
  url: '',
  display_type: 'text',
  label: { de: '', en: '' },
  icon: 'instagram',
});
const ALLOWED_EXTERNAL_SOCIAL_ICONS = Object.freeze(['other', 'facebook', 'instagram', 'twitter', 'youtube', 'tiktok']);
const redirectForm = reactive({
  source_path: '',
  target_path: '',
  status_code: 301,
  expires_at: '',
});
const redirectEditForm = reactive({
  source_path: '',
  target_path: '',
  status_code: 301,
  expires_at: '',
  is_active: true,
});
const redirectStatusOptions = Object.freeze([
  {
    code: 301,
    label: '301 Permanent',
    requiresTarget: true,
    description: 'Use when a URL has moved permanently. Search engines transfer ranking to the new target.',
  },
  {
    code: 302,
    label: '302 Temporary',
    requiresTarget: true,
    description: 'Use for short-term redirects while content is temporarily available somewhere else.',
  },
  {
    code: 307,
    label: '307 Temporary',
    requiresTarget: true,
    description: 'Use for temporary redirects when request method/body must be preserved (method-safe temporary move).',
  },
  {
    code: 308,
    label: '308 Permanent',
    requiresTarget: true,
    description: 'Use for permanent redirects when request method/body must be preserved (method-safe permanent move).',
  },
  {
    code: 410,
    label: '410 Gone',
    requiresTarget: false,
    description: 'Use when a page was intentionally removed and should disappear from search results instead of redirecting.',
  },
]);
const redirectSortOptions = Object.freeze([
  { value: 'anonymous_hit_count', label: 'Anonymous Hits' },
  { value: 'source_path', label: 'Source Route' },
  { value: 'target_path', label: 'Target Route' },
  { value: 'created_at', label: 'Created Date' },
]);
const redirectKindFilterOptions = Object.freeze([
  { value: 'all', label: 'All Types' },
  { value: 'custom', label: 'Custom' },
  { value: 'generated', label: 'Generated' },
]);
const redirectStatusFilterOptions = computed(() => ([
  { value: 'all', label: 'All Status Codes' },
  ...redirectStatusOptions.map((option) => ({
    value: String(option.code),
    label: option.label,
  })),
]));
const CACHING_MAX_TTL_SECONDS = 31536000;
const CACHING_UNIT_SECONDS = Object.freeze({
  seconds: 1,
  minutes: 60,
  hours: 3600,
  days: 86400,
  years: 31536000,
});
const cachingUnitOptions = Object.freeze([
  { value: 'seconds', label: 'seconds' },
  { value: 'minutes', label: 'minutes' },
  { value: 'hours', label: 'hours' },
  { value: 'days', label: 'days' },
  { value: 'years', label: 'years' },
]);
const cachingPreviewText = computed(() => String(cachingPayload.value?.htaccess_text || ''));
const cachingCurrentSnapshot = computed(() => serializeCachingRulesForSnapshot(cachingRules.value));
const cachingDefaultSnapshot = computed(() => {
  const defaultRules = cachingPayload.value?.defaults?.rules;
  return Array.isArray(defaultRules) && defaultRules.length > 0
    ? serializeCachingRulesForSnapshot(defaultRules.map(hydrateCachingRule))
    : '';
});
const cachingHasUnsavedChanges = computed(() => (
  Boolean(cachingLastSavedSnapshot.value)
  && cachingCurrentSnapshot.value !== cachingLastSavedSnapshot.value
));
const cachingHasInvalidRules = computed(() => (
  cachingRules.value.length === 0
  || cachingRules.value.some((rule) => !isCachingRuleValid(rule))
));
const cachingSaveDisabled = computed(() => (
  cachingHasInvalidRules.value
  || !cachingHasUnsavedChanges.value
));
const cachingResetDisabled = computed(() => (
  !cachingDefaultSnapshot.value
  || cachingCurrentSnapshot.value === cachingDefaultSnapshot.value
));
const redirectSortBy = ref('created_at');
const redirectKindFilter = ref('all');
const redirectStatusFilter = ref('all');
const sitemapStatsRangeOptions = Object.freeze([
  { value: '30', label: '30 days' },
  { value: '90', label: '90 days' },
  { value: '365', label: '1 year' },
  { value: 'all', label: 'All time' },
]);
const sitemapChangefreqOptions = Object.freeze([
  { value: '', label: 'Not set' },
  { value: 'always', label: 'always' },
  { value: 'hourly', label: 'hourly' },
  { value: 'daily', label: 'daily' },
  { value: 'weekly', label: 'weekly' },
  { value: 'monthly', label: 'monthly' },
  { value: 'yearly', label: 'yearly' },
  { value: 'never', label: 'never' },
]);

function setActiveTab(nextTab) {
  const target = pageTabs.find((entry) => entry.id === nextTab) || pageTabs[0];
  router.push({ path: target.to, query: route.query });
}

function formatTimestamp(value) {
  return formatInstantInServerTimezone(value, { hour12: false }, { fallback: '—' });
}

function formatRedirectHitCount(value) {
  return formatAnonymousHitCount(value);
}

function formatAnonymousHitCount(value) {
  const normalized = Number(value);
  if (!Number.isFinite(normalized) || normalized < 0) return '0';
  return Math.trunc(normalized).toLocaleString('de-DE');
}

function formatRedirectMetaTimestamp(value) {
  return formatInstantInServerTimezone(value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }, { fallback: '—' });
}

function dateToUTCISOString(date) {
  if (!date) return null;
  const d = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return null;
  const pad = (value) => String(value).padStart(2, '0');
  const wallValue = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return serverWallDateTimeToInstantDate(wallValue)?.toISOString() || null;
}

function parseUTCToLocal(isoString) {
  if (!isoString) return null;
  return serverWallDateTimeToLocalDate(formatDateTimeLocalForServerTimezone(isoString));
}
const slugError = ref('');
const editSlugError = ref('');
const openEditSection = ref('visibility');
const allowedEditSections = Object.freeze(['identifier', 'visibility', 'nav-menu', 'sitemap', 'delete']);

const expandedSections = reactive({
  admin: false,
  api: false,
  endpointsGroup: true,
  footer: true,
  menu: true,
  menusGroup: true,
  pages: true,
});

const expandedApiGroups = reactive({});
const generatedChildrenExpandedByParent = reactive({});

const editForm = reactive({
  slug: '',
  title_de: '',
  title_en: '',
  menu_title_de: '',
  menu_title_en: '',
  menu_parent_title_de: '',
  menu_parent_title_en: '',
  menu_show_as_top_level: false,
  status: 'hidden',
  publish_at: null,
  unpublish_at: null,
  in_menu: false,
  in_footer: false,
  redirect_to: '',
  hide_from_sitemap: false,
  hide_subtree_from_sitemap: false,
  sitemap_priority: '',
  sitemap_changefreq: '',
});

const createForm = reactive({
  slug: '',
  title: { de: '', en: '' },
  menu_title: { de: '', en: '' },
  status: 'hidden',
  in_menu: false,
  in_footer: false,
  hide_from_sitemap: false,
  hide_subtree_from_sitemap: false,
});

const BASE_PAGE_STATUS_OPTIONS = Object.freeze([
  { value: 'hidden', label: 'Hidden' },
  { value: 'under_construction', label: 'Under Construction' },
  { value: 'published', label: 'Published' },
]);
const INIT_PAGE_STATUS_OPTION = Object.freeze({ value: 'init', label: 'Init (new)' });
const createPageStatusOptions = BASE_PAGE_STATUS_OPTIONS;
const bulkChildVisibilityStatusOptions = BASE_PAGE_STATUS_OPTIONS;
const bulkChildVisibilityDropdownLabel = computed(() => {
  if (bulkChildVisibilitySaving.value) return 'Updating child pages...';
  if (selectedPageSubpages.value.length === 0) return 'No child pages';
  const option = bulkChildVisibilityStatusOptions.find((item) => item.value === bulkChildVisibilityStatus.value);
  return option?.label || 'Bulk edit child page state';
});
const editPageStatusOptions = computed(() => {
  const normalized = normalizePageStatus(editForm.status || selectedPage.value?.status || '');
  if (normalized !== 'init') return BASE_PAGE_STATUS_OPTIONS;
  const regularOptions = isGeneratedManagedPage(selectedPage.value)
    ? BASE_PAGE_STATUS_OPTIONS.filter((option) => option.value !== 'hidden')
    : BASE_PAGE_STATUS_OPTIONS;
  return [INIT_PAGE_STATUS_OPTION, ...regularOptions];
});
const SLUG_PATTERN = /^[a-z0-9]+(?:[-/][a-z0-9]+)*$/;

const adminRoutes = computed(() => {
  const routes = router.getRoutes();
  
  return routes
    .filter(r => r.path.startsWith('/admin/') && r.name) // Admin routes with a name (excludes redirects)
    .map(r => ({
      path: r.path.slice(1), // Remove leading slash
      name: formatRouteName(r.name),
      fullPath: r.path
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
});

function formatRouteName(name) {
  if (!name) return '';
  return name
    .replace('admin-', '')
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

const apiRoutes = ref([]);
const apiRoutesLoading = ref(false);

const tagIcons = {
  pages: faFileLines,
  sections: faPuzzlePiece,
  headers: faFolder,
  assets: faFolder,
  design: faPaintbrush,
  'admin-design': faFlask,
  blog: faNewspaper,
  auth: faShieldHalved,
  integrations: faLink,
  backup: faHardDrive,
  system: faGear,
  default: faPlug,
};

function getApiAccess(operationDetails = null, openApiGlobalSecurity = []) {
  const hasOperationSecurity = Object.prototype.hasOwnProperty.call(operationDetails || {}, 'security');
  const operationSecurity = Array.isArray(operationDetails?.security) ? operationDetails.security : [];
  const globalSecurity = Array.isArray(openApiGlobalSecurity) ? openApiGlobalSecurity : [];
  const effectiveSecurity = hasOperationSecurity ? operationSecurity : globalSecurity;
  return effectiveSecurity.length > 0 ? 'private' : 'public';
}

function deriveApiGroupPath(apiPath) {
  const parts = String(apiPath || '/')
    .split('/')
    .filter(Boolean)
    .filter((part) => !part.startsWith('{'));
  if (parts.length === 0) return '/';
  if (parts[0] === 'admin' && parts.length > 1) {
    return `/${parts[0]}/${parts[1]}`;
  }
  return `/${parts[0]}`;
}

async function loadApiRoutes() {
  apiRoutesLoading.value = true;
  try {
    // OpenAPI schema is served by FastAPI at the root
    // In dev: proxied by Vite, in production: same origin or reverse proxy
    const apiBase = resolveApiBase();
    const url = new URL(apiBase, window.location.origin);
    const openApiUrl = `${url.origin}/openapi.json`;
    
    const response = await fetch(openApiUrl, { credentials: 'omit' });
    if (!response.ok) throw new Error(`Failed to fetch OpenAPI schema: ${response.status}`);
    const schema = await response.json();
    
    const groupedRoutes = {};
    const openApiGlobalSecurity = Array.isArray(schema.security) ? schema.security : [];
    const paths = schema.paths || {};
    
    for (const [path, methods] of Object.entries(paths)) {
      // Skip health endpoint and system routes
      if (path === '/health') continue;
      
      // Normalize path - remove /api/v1 prefix if present
      let apiPath = path;
      if (path.startsWith('/api/v1')) {
        apiPath = path.replace('/api/v1', '') || '/';
      }
      
      for (const [method, details] of Object.entries(methods)) {
        // Skip non-HTTP methods
        if (!['get', 'post', 'put', 'patch', 'delete'].includes(method)) continue;
        
        const tags = details.tags || ['other'];
        const tag = tags[0].toLowerCase();
        const groupPath = deriveApiGroupPath(apiPath);
        const access = getApiAccess(details, openApiGlobalSecurity);
        
        if (!groupedRoutes[tag]) {
          groupedRoutes[tag] = {
            path: groupPath,
            name: tags[0].charAt(0).toUpperCase() + tags[0].slice(1),
            icon: tagIcons[tag] || tagIcons.default,
            subroutes: [],
            public_count: 0,
            private_count: 0,
          };
        } else if (!groupedRoutes[tag].path || groupedRoutes[tag].path === `/${tag}`) {
          groupedRoutes[tag].path = groupPath;
        }
        
        // For display, show the path relative to the tag's base path
        const basePath = groupedRoutes[tag].path;
        let subPath = apiPath;
        if (apiPath.startsWith(basePath)) {
          subPath = apiPath.slice(basePath.length) || '/';
        }
        
        groupedRoutes[tag].subroutes.push({
          method: method.toUpperCase(),
          path: subPath,
          fullPath: path,
          name: details.summary || details.operationId || `${method.toUpperCase()} ${subPath}`,
          access,
        });
        if (access === 'public') groupedRoutes[tag].public_count += 1;
        else groupedRoutes[tag].private_count += 1;
      }
    }
    
    // Sort subroutes within each group
    for (const group of Object.values(groupedRoutes)) {
      group.subroutes.sort((a, b) => {
        const methodOrder = { GET: 0, POST: 1, PUT: 2, PATCH: 3, DELETE: 4 };
        const methodDiff = (methodOrder[a.method] || 5) - (methodOrder[b.method] || 5);
        if (methodDiff !== 0) return methodDiff;
        return a.path.localeCompare(b.path);
      });
    }
    
    apiRoutes.value = Object.values(groupedRoutes).sort((a, b) => a.name.localeCompare(b.name));
  } catch (err) {
    console.error('Failed to load API routes:', err);
    apiRoutes.value = [];
  } finally {
    apiRoutesLoading.value = false;
  }
}

const visiblePageBySlug = computed(() => {
  const map = new Map();
  for (const page of visibleSitemapPages.value) {
    const slug = String(page?.slug || '').trim();
    if (!slug) continue;
    map.set(slug, page);
  }
  return map;
});

const generatedChildCountsByParent = computed(() => {
  const counts = Object.create(null);
  const pageBySlug = visiblePageBySlug.value;
  for (const page of visibleSitemapPages.value) {
    if (!isGeneratedManagedPage(page)) continue;
    const slug = String(page?.slug || '').trim();
    if (!slug) continue;
    const parentSlug = resolveGeneratedOwnerParentSlug(slug, pageBySlug);
    if (!parentSlug) continue;
    counts[parentSlug] = (counts[parentSlug] || 0) + 1;
  }
  return counts;
});

const sortedPages = computed(() => {
  return [...visibleSitemapPages.value]
    .filter((page) => isGeneratedPageVisibleInTree(page))
    .sort((a, b) => {
    if (a.slug === 'landing') return -1;
    if (b.slug === 'landing') return 1;
    return a.slug.localeCompare(b.slug);
  });
});

const collapsedGeneratedPageCount = computed(() => {
  let hiddenCount = 0;
  for (const page of visibleSitemapPages.value) {
    if (isGeneratedPageVisibleInTree(page)) continue;
    hiddenCount += 1;
  }
  return hiddenCount;
});

const visibleSitemapPages = computed(() => {
  return pages.value.filter((page) => {
    if (!page) return false;
    if (!page.hide_in_admin_sitemap) return true;
    return isGeneratedManagedPage(page);
  });
});

const menuPages = computed(() => {
  // Only include pages that have in_menu: true
  return [...visibleSitemapPages.value]
    .filter(page => page.in_menu)
    .sort((a, b) => {
      // Sort by menu_order first, then by slug
      const orderA = a.menu_order ?? 0;
      const orderB = b.menu_order ?? 0;
      if (orderA !== orderB) return orderA - orderB;
      if (a.slug === 'landing') return -1;
      if (b.slug === 'landing') return 1;
      return a.slug.localeCompare(b.slug);
    });
});

const footerPages = computed(() => {
  return [...visibleSitemapPages.value]
    .filter((page) => page.in_footer)
    .sort((a, b) => {
      const orderA = a.footer_order ?? 0;
      const orderB = b.footer_order ?? 0;
      if (orderA !== orderB) return orderA - orderB;
      if (a.slug === 'landing') return -1;
      if (b.slug === 'landing') return 1;
      return a.slug.localeCompare(b.slug);
    });
});

const sortedNavExternalLinks = computed(() => {
  return [...navExternalLinks.value].sort((a, b) => {
    const orderA = Number(a?.order ?? 0);
    const orderB = Number(b?.order ?? 0);
    if (orderA !== orderB) return orderA - orderB;
    return String(a?.id || '').localeCompare(String(b?.id || ''));
  });
});

const sortedFooterExternalLinks = computed(() => {
  return [...footerExternalLinks.value].sort((a, b) => {
    const orderA = Number(a?.order ?? 0);
    const orderB = Number(b?.order ?? 0);
    if (orderA !== orderB) return orderA - orderB;
    return String(a?.id || '').localeCompare(String(b?.id || ''));
  });
});

const menuItemDialogLinkablePages = computed(() => {
  const target = menuItemDialogTarget.value;
  const linkedSlugSet = new Set(
    pages.value
      .filter((page) => target === 'menu' ? page.in_menu : page.in_footer)
      .map((page) => page.slug),
  );
  return [...visibleSitemapPages.value]
    .filter((page) => page && page.slug)
    .filter((page) => !linkedSlugSet.has(page.slug))
    .sort((a, b) => {
      if (a.slug === 'landing') return -1;
      if (b.slug === 'landing') return 1;
      return a.slug.localeCompare(b.slug);
    });
});

const menuItemDialogPrimaryActionLabel = computed(() => {
  if (menuItemDialogMode.value === 'create_page') return 'Continue';
  if (menuItemDialogMode.value === 'link_internal') return 'Link Page';
  return menuItemDialogEditingExternalId.value ? 'Save External Link' : 'Add External Link';
});

const isEditingExternalMenuItem = computed(() => {
  return menuItemDialogMode.value === 'external'
    && Boolean(String(menuItemDialogEditingExternalId.value || '').trim());
});

const redirectPageOptions = computed(() => {
  // Return all pages except the currently selected page
  return [...pages.value]
    .filter((page) => (!selectedPage.value || page.slug !== selectedPage.value.slug))
    .filter((page) => isRedirectTargetPageSelectable(page))
    .sort((a, b) => {
      if (a.slug === 'landing') return -1;
      if (b.slug === 'landing') return 1;
      return a.slug.localeCompare(b.slug);
    });
});

const redirectTargetPageOptions = computed(() => {
  const sourcePath = normalizeRedirectSourceInput(redirectForm.source_path);
  return [...pages.value]
    .filter((page) => isRedirectTargetPageSelectable(page))
    .filter((page) => pagePathFromSlug(page.slug) !== sourcePath)
    .sort((a, b) => {
      if (a.slug === 'landing') return -1;
      if (b.slug === 'landing') return 1;
      return a.slug.localeCompare(b.slug);
    });
});

const redirectEditTargetPageOptions = computed(() => {
  const sourcePath = normalizeRedirectSourceInput(redirectEditForm.source_path);
  return [...pages.value]
    .filter((page) => isRedirectTargetPageSelectable(page))
    .filter((page) => pagePathFromSlug(page.slug) !== sourcePath)
    .sort((a, b) => {
      if (a.slug === 'landing') return -1;
      if (b.slug === 'landing') return 1;
      return a.slug.localeCompare(b.slug);
    });
});

const createSlugPath = computed(() => (
  isSlugDraftIncomplete(createForm.slug)
    ? ''
    : normalizeInternalPathInput(createForm.slug)
));
const canCreatePage = computed(() => (
  !creating.value
  && Boolean(normalizeSlugInput(createForm.slug))
  && !isSlugDraftIncomplete(createForm.slug)
  && !slugError.value
));

function redirectSourceContainsWildcards(sourcePath) {
  const source = String(sourcePath || '');
  return source.includes('*') || source.includes('?');
}

function redirectSourceMatchesPath(sourcePattern, path) {
  const pattern = String(sourcePattern || '');
  const candidatePath = String(path || '');
  if (!pattern || !candidatePath) return false;
  if (!redirectSourceContainsWildcards(pattern)) {
    return pattern === candidatePath;
  }
  const escaped = pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const wildcardRegex = `^${escaped.replace(/\\\*/g, '.*').replace(/\\\?/g, '.')}$`;
  return new RegExp(wildcardRegex).test(candidatePath);
}

const createSlugMatchingRedirects = computed(() => {
  const path = createSlugPath.value;
  if (!path) return [];
  const matches = (Array.isArray(redirects.value) ? redirects.value : [])
    .filter((item) => redirectSourceMatchesPath(item?.source_path, path));
  matches.sort((left, right) => {
    const leftExact = String(left?.source_path || '') === path ? 1 : 0;
    const rightExact = String(right?.source_path || '') === path ? 1 : 0;
    if (leftExact !== rightExact) return rightExact - leftExact;
    const leftActive = left?.is_active ? 1 : 0;
    const rightActive = right?.is_active ? 1 : 0;
    if (leftActive !== rightActive) return rightActive - leftActive;
    const leftUpdated = parseRevisionTimestamp(left?.updated_at || left?.created_at)?.getTime() || 0;
    const rightUpdated = parseRevisionTimestamp(right?.updated_at || right?.created_at)?.getTime() || 0;
    return rightUpdated - leftUpdated;
  });
  return matches;
});

const createSlugRedirectConflictMessage = computed(() => {
  const path = createSlugPath.value;
  const match = createSlugMatchingRedirects.value[0];
  if (!path || !match) return '';

  const sourcePath = String(match.source_path || '');
  const targetPath = match.target_path || '410 Gone (Removed)';
  const statusCode = Number(match.status_code) || 301;
  const activeLabel = match.is_active ? 'Active' : 'Inactive';

  if (sourcePath === path) {
    return `${activeLabel} redirect already exists for ${path}: ${targetPath} (${statusCode}).`;
  }
  return `${activeLabel} wildcard redirect matches ${path}: ${sourcePath} → ${targetPath} (${statusCode}).`;
});

const redirectStatusSelection = computed(() => {
  return redirectStatusOptions.find((item) => item.code === Number(redirectForm.status_code))
    || redirectStatusOptions[0];
});

const redirectEditStatusSelection = computed(() => {
  return redirectStatusOptions.find((item) => item.code === Number(redirectEditForm.status_code))
    || redirectStatusOptions[0];
});

function isSameOrDescendantSlug(candidateSlug, rootSlug) {
  return candidateSlug === rootSlug || candidateSlug.startsWith(rootSlug + '/');
}

function isTopLevelMenuOverridePage(page) {
  const slug = String(page?.slug || '').trim();
  if (!slug || slug === 'landing') return false;
  return Boolean(page?.menu_show_as_top_level);
}

function findClosestMenuParentSlug(page, menuPageBySlug) {
  const slug = String(page?.slug || '').trim();
  if (!slug || isTopLevelMenuOverridePage(page)) return null;
  const parts = slug.split('/');
  for (let i = parts.length - 1; i > 0; i -= 1) {
    const parentSlug = parts.slice(0, i).join('/');
    if (menuPageBySlug.has(parentSlug)) return parentSlug;
  }
  return null;
}

const menuChildCountsByParentSlug = computed(() => {
  const counts = new Map();
  const menuPagesList = visibleSitemapPages.value.filter((page) => page.in_menu);
  const menuPageBySlug = new Map(menuPagesList.map((page) => [page.slug, page]));
  for (const page of menuPagesList) {
    const parentSlug = findClosestMenuParentSlug(page, menuPageBySlug);
    if (!parentSlug) continue;
    counts.set(parentSlug, (counts.get(parentSlug) || 0) + 1);
  }
  return counts;
});

const topLevelMenuItems = computed(() => {
  // Get all menu pages
  const menuPagesList = visibleSitemapPages.value.filter(page => page.in_menu);
  const menuPageBySlug = new Map(menuPagesList.map((page) => [page.slug, page]));

  const nodeBySlug = new Map(
    menuPagesList.map((page) => [page.slug, { page, children: [] }])
  );

  const roots = [];
  for (const page of menuPagesList) {
    const node = nodeBySlug.get(page.slug);
    const parentSlug = findClosestMenuParentSlug(page, menuPageBySlug);
    if (!parentSlug) {
      roots.push(node);
      continue;
    }
    const parentNode = nodeBySlug.get(parentSlug);
    if (parentNode) parentNode.children.push(node);
    else roots.push(node);
  }

  const sortNodes = (nodes) => {
    nodes.sort((a, b) => {
      const orderA = a.page.menu_order ?? 0;
      const orderB = b.page.menu_order ?? 0;
      if (orderA !== orderB) return orderA - orderB;
      if (a.page.slug === 'landing') return -1;
      if (b.page.slug === 'landing') return 1;
      return a.page.slug.localeCompare(b.page.slug);
    });
    nodes.forEach((node) => sortNodes(node.children));
  };

  sortNodes(roots);
  return roots;
});

const totalApiRoutes = computed(() => {
  return apiRoutes.value.reduce((sum, group) => sum + (group.subroutes?.length || 0), 0);
});

function resolveRedirectKindSortRank(item) {
  const kind = String(item?.kind || 'custom');
  if (kind === 'custom') return 0;
  if (kind === 'generated') return 1;
  return 2;
}

function isGeneratedRedirect(item) {
  return String(item?.kind || 'custom') === 'generated';
}

function isFirstGeneratedRedirect(index) {
  const list = filteredRedirects.value;
  const current = list[index];
  if (!isGeneratedRedirect(current)) return false;
  if (index <= 0) return true;
  return !isGeneratedRedirect(list[index - 1]);
}

function resolveRedirectAnonymousHitCount(item) {
  const numeric = Number(item?.anonymous_hit_count);
  if (!Number.isFinite(numeric) || numeric <= 0) return 0;
  return Math.trunc(numeric);
}

const filteredRedirects = computed(() => {
  let items = showExpiredRedirects.value
    ? [...redirects.value]
    : redirects.value.filter((item) => !item.is_expired);

  if (redirectKindFilter.value !== 'all') {
    items = items.filter((item) => String(item?.kind || 'custom') === redirectKindFilter.value);
  }

  if (redirectStatusFilter.value !== 'all') {
    const requiredCode = Number(redirectStatusFilter.value);
    items = items.filter((item) => Number(item?.status_code) === requiredCode);
  }

  const sorted = [...items];
  sorted.sort((left, right) => {
    // Always group by redirect type first: custom, then generated.
    const kindCmp = resolveRedirectKindSortRank(left) - resolveRedirectKindSortRank(right);
    if (kindCmp !== 0) return kindCmp;

    if (redirectSortBy.value === 'anonymous_hit_count') {
      const leftHits = resolveRedirectAnonymousHitCount(left);
      const rightHits = resolveRedirectAnonymousHitCount(right);
      if (leftHits !== rightHits) return rightHits - leftHits;
      return String(left?.source_path || '').localeCompare(String(right?.source_path || ''));
    }

    if (redirectSortBy.value === 'created_at') {
      const leftTs = parseRevisionTimestamp(left?.created_at || left?.updated_at)?.getTime() || 0;
      const rightTs = parseRevisionTimestamp(right?.created_at || right?.updated_at)?.getTime() || 0;
      return rightTs - leftTs; // newest first
    }

    if (redirectSortBy.value === 'target_path') {
      const leftTarget = String(left?.target_path || '');
      const rightTarget = String(right?.target_path || '');
      const targetCmp = leftTarget.localeCompare(rightTarget);
      if (targetCmp !== 0) return targetCmp;
      return String(left?.source_path || '').localeCompare(String(right?.source_path || ''));
    }

    // default: source_path
    const sourceCmp = String(left?.source_path || '').localeCompare(String(right?.source_path || ''));
    if (sourceCmp !== 0) return sourceCmp;
    return String(left?.target_path || '').localeCompare(String(right?.target_path || ''));
  });
  return sorted;
});

const selectedRedirectIdSet = computed(() => new Set(selectedRedirectIds.value));

const selectedRedirectCount = computed(() => selectedRedirectIds.value.length);

const allFilteredRedirectsSelected = computed(() => {
  if (filteredRedirects.value.length === 0) return false;
  const selectedIds = selectedRedirectIdSet.value;
  return filteredRedirects.value.every((item) => {
    const id = redirectSelectionKey(item);
    return id && selectedIds.has(id);
  });
});

function normalizeStatsHitCount(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return 0;
  return Math.trunc(numeric);
}

function getStatsPageTitle(page) {
  const title = page?.title && typeof page.title === 'object' ? page.title : null;
  return String(title?.de || title?.en || page?.path || page?.slug || '').trim();
}

function formatStatsDayLabel(day) {
  const date = new Date(`${String(day || '').trim()}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return String(day || '');
  return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
}

const sitemapStatsPages = computed(() => {
  const list = Array.isArray(sitemapStatsPayload.value?.pages)
    ? sitemapStatsPayload.value.pages
    : [];
  return list.filter((page) => page && page.id);
});

function isStatsPublicPage(page) {
  if (page?.is_visible === true) return true;
  const effectiveStatus = String(page?.effective_status || page?.status || '').trim().toLowerCase();
  return effectiveStatus === 'published';
}

const sitemapStatsPublicPages = computed(() => sitemapStatsPages.value.filter((page) => isStatsPublicPage(page)));

const sitemapStatsVisiblePages = computed(() => sitemapStatsPublicPages.value);

function isStatsGeneratedPage(page) {
  return isGeneratedManagedPage(page);
}

const sitemapStatsPageById = computed(() => {
  const map = new Map();
  for (const page of sitemapStatsPublicPages.value) {
    map.set(String(page.id), page);
  }
  return map;
});

const sitemapStatsPageBySlug = computed(() => {
  const map = new Map();
  for (const page of sitemapStatsPublicPages.value) {
    const slug = String(page?.slug || '').trim();
    if (slug) map.set(slug, page);
  }
  return map;
});

const sitemapStatsGeneratedPages = computed(() => (
  sitemapStatsVisiblePages.value.filter((page) => isStatsGeneratedPage(page))
));

const sitemapStatsGeneratedPageCount = computed(() => sitemapStatsGeneratedPages.value.length);

const sitemapStatsVisiblePageIds = computed(() => (
  sitemapStatsVisiblePages.value.map((page) => String(page.id))
));

function resolveStatsGeneratedOwnerSlug(page) {
  const slug = String(page?.slug || '').trim();
  if (!slug || !isStatsGeneratedPage(page)) return null;
  const pageBySlug = sitemapStatsPageBySlug.value;
  let parentSlug = getParentSlug(slug);
  while (parentSlug) {
    const parent = pageBySlug.get(parentSlug);
    if (parent && !isStatsGeneratedPage(parent)) return parentSlug;
    parentSlug = getParentSlug(parentSlug);
  }
  return pageBySlug.has('landing') ? 'landing' : null;
}

const sitemapStatsGeneratedGroups = computed(() => {
  const groups = new Map();
  for (const page of sitemapStatsGeneratedPages.value) {
    const ownerSlug = resolveStatsGeneratedOwnerSlug(page);
    const owner = ownerSlug ? sitemapStatsPageBySlug.value.get(ownerSlug) : null;
    const ownerId = owner?.id ? String(owner.id) : '';
    const groupId = `generated:${ownerId || 'root'}`;
    if (!groups.has(groupId)) {
      groups.set(groupId, {
        id: groupId,
        kind: 'generated_group',
        ownerId,
        ownerSlug,
        label: 'Generated pages',
        pageIds: [],
        pageCount: 0,
        hitCount: 0,
      });
    }
    const group = groups.get(groupId);
    group.pageIds.push(String(page.id));
    group.pageCount += 1;
    group.hitCount += normalizeStatsHitCount(page?.anonymous_hit_count);
  }
  return groups;
});

const sitemapStatsSelectedPage = computed(() => {
  const id = String(selectedStatsPageId.value || '').trim();
  return id ? sitemapStatsPageById.value.get(id) || null : null;
});

const sitemapStatsSelectedGeneratedGroup = computed(() => {
  const id = String(selectedStatsPageId.value || '').trim();
  return id ? sitemapStatsGeneratedGroups.value.get(id) || null : null;
});

const sitemapStatsSelectedPageIds = computed(() => {
  const selectedGroup = sitemapStatsSelectedGeneratedGroup.value;
  if (selectedGroup) return selectedGroup.pageIds;
  const selected = sitemapStatsSelectedPage.value;
  if (!selected) return sitemapStatsVisiblePageIds.value;
  const ids = Array.isArray(selected.descendant_ids) && selected.descendant_ids.length > 0
    ? selected.descendant_ids
    : [selected.id];
  const visibleSet = new Set(sitemapStatsVisiblePageIds.value);
  return ids.map((id) => String(id)).filter((id) => visibleSet.has(id));
});

const sitemapStatsSelectedIdSet = computed(() => new Set(sitemapStatsSelectedPageIds.value));

const sitemapStatsScopeLabel = computed(() => {
  const selectedGroup = sitemapStatsSelectedGeneratedGroup.value;
  if (selectedGroup) {
    const owner = selectedGroup.ownerId ? sitemapStatsPageById.value.get(selectedGroup.ownerId) : null;
    const ownerPath = owner?.path || '/';
    return `${ownerPath} · Generated pages`;
  }
  const selected = sitemapStatsSelectedPage.value;
  if (!selected) return 'All public pages';
  const title = getStatsPageTitle(selected);
  return title && title !== selected.path
    ? `${selected.path} · ${title}`
    : selected.path;
});

const sitemapStatsTotalHits = computed(() => {
  const payloadTotal = Number(sitemapStatsPayload.value?.totals?.total_hit_count);
  if (Number.isFinite(payloadTotal) && payloadTotal >= 0) return Math.trunc(payloadTotal);
  return sitemapStatsVisiblePages.value.reduce(
    (sum, page) => sum + normalizeStatsHitCount(page?.anonymous_hit_count),
    0,
  );
});

const sitemapStatsTrackedPageCount = computed(() => {
  const payloadCount = Number(sitemapStatsPayload.value?.totals?.tracked_page_count);
  if (Number.isFinite(payloadCount) && payloadCount >= 0) return Math.trunc(payloadCount);
  return sitemapStatsVisiblePages.value.filter((page) => normalizeStatsHitCount(page?.anonymous_hit_count) > 0).length;
});

const sitemapStatsSelectedHits = computed(() => {
  const selectedIds = sitemapStatsSelectedIdSet.value;
  return sitemapStatsVisiblePages.value.reduce((sum, page) => {
    if (!selectedIds.has(String(page.id))) return sum;
    return sum + normalizeStatsHitCount(page?.anonymous_hit_count);
  }, 0);
});

const sitemapStatsDailySeries = computed(() => {
  const days = Array.isArray(sitemapStatsPayload.value?.days)
    ? sitemapStatsPayload.value.days.map((day) => String(day || '')).filter(Boolean)
    : [];
  const byDay = new Map(days.map((day) => [day, 0]));
  const selectedIds = sitemapStatsSelectedIdSet.value;
  const rows = Array.isArray(sitemapStatsPayload.value?.daily_hits)
    ? sitemapStatsPayload.value.daily_hits
    : [];
  rows.forEach((row) => {
    const day = String(row?.day || '');
    const pageId = String(row?.page_id || '');
    if (!byDay.has(day) || !selectedIds.has(pageId)) return;
    byDay.set(day, byDay.get(day) + normalizeStatsHitCount(row?.count));
  });
  return days.map((day) => ({
    day,
    count: byDay.get(day) || 0,
  }));
});

const sitemapStatsDailyTotal = computed(() => (
  sitemapStatsDailySeries.value.reduce((sum, item) => sum + normalizeStatsHitCount(item?.count), 0)
));

const sitemapStatsRangeLabel = computed(() => {
  const range = sitemapStatsPayload.value?.range;
  if (!range) return '';
  if (range.all_time && (!range.start_day || !range.end_day)) {
    return 'Timeline: all time, no daily buckets yet';
  }
  if (!range.start_day || !range.end_day) return '';
  const prefix = range.all_time ? 'Timeline: all time' : 'Timeline';
  return `${prefix}: ${range.start_day} - ${range.end_day}`;
});

function getTimelineAxisProfile(seriesLength) {
  if (seriesLength > 366) {
    return { xLabelCount: 5, yLabelCount: 4, xLabelFontSize: 8, yLabelFontSize: 9 };
  }
  if (seriesLength > 92) {
    return { xLabelCount: 6, yLabelCount: 4, xLabelFontSize: 9, yLabelFontSize: 10 };
  }
  if (seriesLength > 31) {
    return { xLabelCount: 7, yLabelCount: 5, xLabelFontSize: 10, yLabelFontSize: 10 };
  }
  return { xLabelCount: 7, yLabelCount: 5, xLabelFontSize: 11, yLabelFontSize: 11 };
}

function buildNiceTimelineTicks(maxValue, targetCount) {
  const safeMax = normalizeStatsHitCount(maxValue);
  if (safeMax <= 0) return [0];
  if (safeMax <= targetCount - 1) {
    return Array.from({ length: safeMax + 1 }, (_item, index) => index);
  }
  const rawStep = safeMax / Math.max(1, targetCount - 1);
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalizedStep = rawStep / magnitude;
  const niceStep = normalizedStep <= 1
    ? 1
    : normalizedStep <= 2
      ? 2
      : normalizedStep <= 5
        ? 5
        : 10;
  const step = niceStep * magnitude;
  const niceMax = Math.ceil(safeMax / step) * step;
  const ticks = [];
  for (let value = 0; value <= niceMax; value += step) {
    ticks.push(value);
  }
  return ticks;
}

const sitemapStatsTreeLayout = computed(() => {
  const pagesForTree = [...sitemapStatsVisiblePages.value]
    .filter((page) => statsGeneratedPagesExpanded.value || !isStatsGeneratedPage(page))
    .sort((left, right) => String(left?.path || '').localeCompare(String(right?.path || '')));
  const nodeById = new Map();
  const generatedGroups = statsGeneratedPagesExpanded.value
    ? []
    : Array.from(sitemapStatsGeneratedGroups.value.values());
  const maxPageHits = [...pagesForTree, ...generatedGroups].reduce(
    (maxValue, page) => Math.max(
      maxValue,
      normalizeStatsHitCount(page?.anonymous_hit_count ?? page?.hitCount),
    ),
    0,
  );
  const rootPage = pagesForTree.find((page) => String(page?.slug || '').trim() === 'landing') || null;
  const rootPageId = rootPage?.id ? String(rootPage.id) : '';
  const root = {
    id: rootPageId,
    kind: 'root',
    page: rootPage,
    depth: 0,
    x: 24,
    y: 24,
    label: '/',
    path: '/',
    hitCount: sitemapStatsTotalHits.value,
    children: [],
  };
  if (rootPageId) {
    nodeById.set(rootPageId, root);
  }

  pagesForTree.forEach((page) => {
    const pageId = String(page.id);
    if (pageId === rootPageId) return;
    nodeById.set(pageId, {
      id: pageId,
      kind: 'page',
      page,
      label: page.path,
      path: page.path,
      hitCount: normalizeStatsHitCount(page.anonymous_hit_count),
      children: [],
      depth: 1,
      x: 0,
      y: 0,
    });
  });

  generatedGroups.forEach((group) => {
    nodeById.set(group.id, {
      id: group.id,
      kind: 'generated_group',
      label: `Generated pages (${group.pageCount})`,
      path: `Generated pages (${group.pageCount})`,
      hitCount: group.hitCount,
      pageIds: group.pageIds,
      pageCount: group.pageCount,
      ownerId: group.ownerId,
      ownerSlug: group.ownerSlug,
      children: [],
      depth: 1,
      x: 0,
      y: 0,
    });
  });

  nodeById.forEach((node) => {
    if (node === root) return;
    const parentId = String(node.kind === 'generated_group' ? node.ownerId : node.page?.parent_id || '');
    const parent = parentId ? nodeById.get(parentId) : null;
    if (parent) parent.children.push(node);
    else root.children.push(node);
  });

  const sortNodes = (nodes) => {
    nodes.sort((left, right) => String(left.path || '').localeCompare(String(right.path || '')));
    nodes.forEach((node) => sortNodes(node.children));
  };
  sortNodes(root.children);

  const rowHeight = 46;
  const columnWidth = 210;
  let leafIndex = 0;
  let maxDepth = 0;
  const layoutNode = (node, depth) => {
    node.depth = depth;
    node.x = 24 + depth * columnWidth;
    maxDepth = Math.max(maxDepth, depth);
    if (!node.children.length) {
      node.y = 28 + leafIndex * rowHeight;
      leafIndex += 1;
      return node.y;
    }
    const childYValues = node.children.map((child) => layoutNode(child, depth + 1));
    node.y = childYValues.reduce((sum, value) => sum + value, 0) / childYValues.length;
    return node.y;
  };
  layoutNode(root, 0);

  const nodes = [];
  const links = [];
  const collect = (node) => {
    nodes.push(node);
    node.children.forEach((child) => {
      links.push({
        key: `${node.id || 'root'}-${child.id}`,
        source: node,
        target: child,
      });
      collect(child);
    });
  };
  collect(root);

  return {
    nodes,
    links,
    width: Math.max(720, 360 + maxDepth * columnWidth),
    height: Math.max(180, 64 + Math.max(1, leafIndex) * rowHeight),
    maxHits: Math.max(1, maxPageHits),
  };
});

const sitemapStatsTimelineLayout = computed(() => {
  const series = sitemapStatsDailySeries.value;
  const rawMaxValue = Math.max(1, ...series.map((item) => normalizeStatsHitCount(item.count)));
  const axisProfile = getTimelineAxisProfile(series.length);
  const yTickValues = buildNiceTimelineTicks(rawMaxValue, axisProfile.yLabelCount);
  const maxValue = Math.max(1, yTickValues[yTickValues.length - 1] || rawMaxValue);
  const labelInterval = series.length <= axisProfile.xLabelCount
    ? 1
    : Math.ceil((series.length - 1) / (axisProfile.xLabelCount - 1));
  const width = Math.max(720, Math.floor(Number(statsTimelineContainerWidth.value) || 720));
  const height = 220;
  const left = Math.max(48, 22 + String(maxValue).length * 7);
  const right = 14;
  const top = 20;
  const bottom = 38;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const slotWidth = series.length > 0 ? plotWidth / series.length : plotWidth;
  const barGap = series.length > 180 ? 1 : series.length > 90 ? 2 : 5;
  const maxBarWidth = series.length > 180 ? 2 : series.length > 90 ? 4 : 18;
  const yTicks = yTickValues.map((value) => ({
    value,
    y: top + plotHeight - (normalizeStatsHitCount(value) / maxValue) * plotHeight,
  }));
  const bars = series.map((item, index) => {
    const count = normalizeStatsHitCount(item.count);
    const barWidth = Math.max(1, Math.min(maxBarWidth, slotWidth - barGap));
    const barHeight = count > 0 ? Math.max(2, (count / maxValue) * plotHeight) : 0;
    return {
      ...item,
      count,
      x: left + index * slotWidth + (slotWidth - barWidth) / 2,
      y: top + plotHeight - barHeight,
      width: barWidth,
      height: barHeight,
      label: formatStatsDayLabel(item.day),
      showLabel: index === 0 || index === series.length - 1 || index % labelInterval === 0,
    };
  });
  return {
    width,
    height,
    left,
    top,
    plotWidth,
    plotHeight,
    maxValue,
    yTicks,
    xLabelFontSize: axisProfile.xLabelFontSize,
    yLabelFontSize: axisProfile.yLabelFontSize,
    bars,
    baselineY: top + plotHeight,
  };
});

function isStatsNodeSelected(node) {
  if (!node) return false;
  if (node.kind === 'root') return !selectedStatsPageId.value;
  return String(node.id || '') === String(selectedStatsPageId.value || '');
}

function selectStatsNode(node) {
  if (!node) return;
  selectedStatsPageId.value = node.kind === 'root' ? '' : String(node.id || '');
}

function toggleStatsGeneratedPagesExpanded() {
  statsGeneratedPagesExpanded.value = !statsGeneratedPagesExpanded.value;
  if (String(selectedStatsPageId.value || '').startsWith('generated:')) {
    selectedStatsPageId.value = '';
  }
}

function getStatsLinkPath(link) {
  const startX = Number(link?.source?.x || 0) + 12;
  const startY = Number(link?.source?.y || 0);
  const endX = Number(link?.target?.x || 0) - 12;
  const endY = Number(link?.target?.y || 0);
  const midX = startX + Math.max(24, (endX - startX) / 2);
  return `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`;
}

function getStatsNodeRadius(node) {
  if (node?.kind === 'root') return 10;
  const ratio = Math.sqrt(normalizeStatsHitCount(node?.hitCount) / sitemapStatsTreeLayout.value.maxHits);
  return Math.max(5, Math.min(15, 5 + ratio * 10));
}

function getStatsNodeFill(node) {
  if (node?.kind === 'root') return '#0f172a';
  const ratio = Math.sqrt(normalizeStatsHitCount(node?.hitCount) / sitemapStatsTreeLayout.value.maxHits);
  const alpha = Math.max(0.24, Math.min(0.92, 0.24 + ratio * 0.68));
  if (node?.kind === 'generated_group') return `rgba(15, 118, 110, ${alpha})`;
  return `rgba(37, 99, 235, ${alpha})`;
}

function getStatsNodeLabel(node) {
  if (node?.kind === 'root') return '/';
  if (node?.kind === 'generated_group') return node?.label || 'Generated pages';
  const title = getStatsPageTitle(node?.page);
  if (!title || title === node?.path) return node?.path || '';
  return `${node.path} · ${title}`;
}

const canRenameSelectedPage = computed(() => {
  if (!selectedPage.value) return false;
  const nextSlug = normalizeSlugInput(editForm.slug);
  return Boolean(nextSlug) && nextSlug !== selectedPage.value.slug;
});

const sitemapSectionSummary = computed(() => {
  const hasCustomRules = (
    Boolean(editForm.redirect_to)
    || editForm.hide_from_sitemap
    || editForm.hide_subtree_from_sitemap
    || (editForm.sitemap_priority !== '' && editForm.sitemap_priority !== null)
    || Boolean(editForm.sitemap_changefreq)
  );
  return hasCustomRules ? 'Custom SEO rules' : 'Default SEO rules';
});

const robotsDisallowActive = computed(() => (
  Boolean(editForm.hide_subtree_from_sitemap) || Boolean(editForm.hide_from_sitemap)
));

const robotsPageOnlyDisallow = computed(() => (
  Boolean(editForm.hide_from_sitemap) && !Boolean(editForm.hide_subtree_from_sitemap)
));

const navMenuSectionSummary = computed(() => {
  const nav = editForm.in_menu ? 'In navigation' : 'Not in navigation';
  const footer = editForm.in_footer ? 'In footer' : 'Not in footer';
  return `${nav} · ${footer}`;
});

const selectedPageIsMenuParentNode = computed(() => {
  if (!selectedPage.value || !editForm.in_menu) return false;
  const slug = String(selectedPage.value.slug || '').trim();
  if (!slug) return false;
  return (menuChildCountsByParentSlug.value.get(slug) || 0) > 0;
});

const selectedPageSubpages = computed(() => {
  if (!selectedPage.value) return [];
  const selectedSlug = String(selectedPage.value.slug || '').trim();
  if (!selectedSlug) return [];

  const descendants = selectedSlug === 'landing'
    ? pages.value.filter((page) => page.slug !== 'landing')
    : pages.value.filter((page) => isSameOrDescendantSlug(page.slug, selectedSlug) && page.slug !== selectedSlug);

  return [...descendants].sort((left, right) => {
    const depthDiff = getPageDepth(right.slug) - getPageDepth(left.slug);
    if (depthDiff !== 0) return depthDiff;
    return right.slug.localeCompare(left.slug);
  });
});

function getPageDepth(slug) {
  if (slug === 'landing') return 0;
  return (slug.match(/\//g) || []).length;
}

function defaultSitemapPriority(slug) {
  const depth = getPageDepth(slug);
  if (depth === 0) return 1.0;
  if (depth === 1) return 0.8;
  if (depth === 2) return 0.5;
  return 0.2;
}

function getMenuPageDepth(slug) {
  // Find the parent menu item for this page
  const page = pages.value.find(p => p.slug === slug);
  if (page?.in_menu) return 0; // Top-level menu items have depth 0
  
  // Find the closest parent that is in_menu
  const menuSlugs = pages.value
    .filter(p => p.in_menu)
    .map(p => p.slug)
    .sort((a, b) => b.length - a.length); // Longest first to find closest parent
  
  for (const menuSlug of menuSlugs) {
    if (slug.startsWith(menuSlug + '/')) {
      // Calculate depth relative to parent menu item
      const relativePath = slug.slice(menuSlug.length + 1);
      return (relativePath.match(/\//g) || []).length + 1;
    }
  }
  
  return 0;
}

function getPageDisplaySlug(slug) {
  if (slug === 'landing') return '/';
  const parts = slug.split('/');
  return parts[parts.length - 1];
}

function setOpenEditSection(section) {
  if (!allowedEditSections.includes(section)) return;
  openEditSection.value = openEditSection.value === section ? null : section;
}

function toggleSection(section) {
  expandedSections[section] = !expandedSections[section];
}

function toggleApiGroup(path) {
  expandedApiGroups[path] = !expandedApiGroups[path];
}

async function onMenuReorder(newOrder, parentSlug) {
  // newOrder: the reordered array of pages (or tree items for top-level)
  // parentSlug: null for top-level menu items, or the parent's slug for subpages
  
  if (subtreeReorderEnabled.value || migratingSubtree.value) return;

  const updates = [];
  const extractPage = (item) => item?.page ?? item;
  const applyLocalMenuOrder = (slug, menuOrder) => {
    const localPage = pages.value.find(p => p.slug === slug);
    if (localPage) {
      localPage.menu_order = menuOrder;
    }
  };
  
  if (parentSlug === null) {
    // Reordering top-level menu items only (default behavior).
    newOrder.forEach((item, index) => {
      const page = extractPage(item);
      if (!page?.slug) return;
      if (page.menu_order !== index) {
        updates.push({ slug: page.slug, menu_order: index });
        applyLocalMenuOrder(page.slug, index);
      }
    });
  } else {
    // Reordering subpages within a parent
    newOrder.forEach((item, index) => {
      const page = extractPage(item);
      if (!page?.slug) return;
      if (page.menu_order !== index) {
        updates.push({ slug: page.slug, menu_order: index });
        applyLocalMenuOrder(page.slug, index);
      }
    });
  }
  
  // Save to backend
  if (updates.length > 0) {
    try {
      await Promise.all(
        updates.map(({ slug, menu_order }) => 
          api.updatePage(slug, { menu_order })
        )
      );
    } catch (err) {
      console.error('Failed to save menu order:', err);
      // Reload pages to restore correct order
      await loadPages();
    }
  }
}

function onMenuReorderNodes({ nodes, parentSlug }) {
  const orderedPages = (nodes || []).map((node) => node.page);
  return onMenuReorder(orderedPages, parentSlug ?? null);
}

async function onFooterReorder(newOrder) {
  if (subtreeReorderEnabled.value || migratingSubtree.value) return;

  const updates = [];
  const applyLocalFooterOrder = (slug, footerOrder) => {
    const localPage = pages.value.find((page) => page.slug === slug);
    if (localPage) {
      localPage.footer_order = footerOrder;
    }
  };

  (newOrder || []).forEach((page, index) => {
    if (!page?.slug) return;
    if ((page.footer_order ?? 0) !== index) {
      updates.push({ slug: page.slug, footer_order: index });
      applyLocalFooterOrder(page.slug, index);
    }
  });

  if (updates.length > 0) {
    try {
      await Promise.all(
        updates.map(({ slug, footer_order }) =>
          api.updatePage(slug, { footer_order }),
        ),
      );
    } catch (err) {
      console.error('Failed to save footer order:', err);
      await loadPages();
    }
  }
}

function normalizeExternalLinksForSave(items) {
  const list = Array.isArray(items) ? items : [];
  return list.map((item, index) => {
    const icon = String(item?.icon || '').trim().toLowerCase();
    const useIcon = ALLOWED_EXTERNAL_SOCIAL_ICONS.includes(icon);
    const de = String(item?.label?.de || '').trim();
    const en = String(item?.label?.en || '').trim();
    return {
      id: String(item?.id || `ext-${Date.now()}-${index}`).trim(),
      url: String(item?.url || '').trim(),
      label: useIcon ? null : { de, en },
      icon: useIcon ? icon : null,
      order: index,
    };
  });
}

function normalizeLogoUrlForSave(value) {
  const normalized = String(value || '').trim();
  return normalized || null;
}

function openTopbarLogoPicker() {
  topbarLogoPickerOpen.value = true;
}

function closeTopbarLogoPicker() {
  topbarLogoPickerOpen.value = false;
}

function openFooterLogoPicker() {
  footerLogoPickerOpen.value = true;
}

function closeFooterLogoPicker() {
  footerLogoPickerOpen.value = false;
}

async function onTopbarLogoSelected(selection) {
  if (!selection || typeof selection !== 'object') return;
  const url = normalizeLogoUrlForSave(selection?.url);
  try {
    await persistNavigationLinks(navExternalLinks.value, footerExternalLinks.value, { topbarLogoUrl: url });
    closeTopbarLogoPicker();
  } catch (_) {
    // Error state is surfaced by persistNavigationLinks/navigationLinksError.
  }
}

async function clearTopbarLogo() {
  try {
    await persistNavigationLinks(navExternalLinks.value, footerExternalLinks.value, { topbarLogoUrl: null });
  } catch (_) {
    // Error state is surfaced by persistNavigationLinks/navigationLinksError.
  }
}

async function onFooterLogoSelected(selection) {
  if (!selection || typeof selection !== 'object') return;
  const url = normalizeLogoUrlForSave(selection?.url);
  try {
    await persistNavigationLinks(navExternalLinks.value, footerExternalLinks.value, { footerLogoUrl: url });
    closeFooterLogoPicker();
  } catch (_) {
    // Error state is surfaced by persistNavigationLinks/navigationLinksError.
  }
}

async function clearFooterLogo() {
  try {
    await persistNavigationLinks(navExternalLinks.value, footerExternalLinks.value, { footerLogoUrl: null });
  } catch (_) {
    // Error state is surfaced by persistNavigationLinks/navigationLinksError.
  }
}

async function loadNavigationLinks() {
  try {
    const payload = await api.getSitemapNavigationLinks();
    navExternalLinks.value = normalizeExternalLinksForSave(payload?.nav_external_links || []);
    footerExternalLinks.value = normalizeExternalLinksForSave(payload?.footer_external_links || []);
    topbarLogoUrl.value = normalizeLogoUrlForSave(payload?.topbar_logo_url);
    footerLogoUrl.value = normalizeLogoUrlForSave(payload?.footer_logo_url);
    navigationLinksError.value = '';
  } catch (err) {
    console.error('Failed to load sitemap navigation links:', err);
    navigationLinksError.value = err?.message || 'Failed to load navigation links';
    navExternalLinks.value = [];
    footerExternalLinks.value = [];
    topbarLogoUrl.value = null;
    footerLogoUrl.value = null;
  }
}

async function persistNavigationLinks(nextNavLinks, nextFooterLinks, options = {}) {
  navigationLinksSaving.value = true;
  const hasTopbarLogo = Object.prototype.hasOwnProperty.call(options, 'topbarLogoUrl');
  const hasFooterLogo = Object.prototype.hasOwnProperty.call(options, 'footerLogoUrl');
  const nextTopbarLogoUrl = hasTopbarLogo ? options.topbarLogoUrl : topbarLogoUrl.value;
  const nextFooterLogoUrl = hasFooterLogo ? options.footerLogoUrl : footerLogoUrl.value;
  try {
    const payload = await api.updateSitemapNavigationLinks({
      nav_external_links: normalizeExternalLinksForSave(nextNavLinks),
      footer_external_links: normalizeExternalLinksForSave(nextFooterLinks),
      topbar_logo_url: normalizeLogoUrlForSave(nextTopbarLogoUrl),
      footer_logo_url: normalizeLogoUrlForSave(nextFooterLogoUrl),
    });
    navExternalLinks.value = normalizeExternalLinksForSave(payload?.nav_external_links || []);
    footerExternalLinks.value = normalizeExternalLinksForSave(payload?.footer_external_links || []);
    topbarLogoUrl.value = normalizeLogoUrlForSave(payload?.topbar_logo_url);
    footerLogoUrl.value = normalizeLogoUrlForSave(payload?.footer_logo_url);
    navigationLinksError.value = '';
  } catch (err) {
    console.error('Failed to save sitemap navigation links:', err);
    navigationLinksError.value = err?.message || 'Failed to save navigation links';
    await loadNavigationLinks();
    throw err;
  } finally {
    navigationLinksSaving.value = false;
  }
}

async function onExternalLinksReorder(location, newOrder) {
  const reordered = normalizeExternalLinksForSave(newOrder);
  if (location === 'menu') {
    await persistNavigationLinks(reordered, footerExternalLinks.value);
    return;
  }
  await persistNavigationLinks(navExternalLinks.value, reordered);
}

async function deleteExternalLink(location, linkId) {
  const id = String(linkId || '').trim();
  if (!id) return;

  if (location === 'menu') {
    const nextNavLinks = navExternalLinks.value.filter((item) => String(item?.id || '').trim() !== id);
    await persistNavigationLinks(nextNavLinks, footerExternalLinks.value);
    return;
  }
  const nextFooterLinks = footerExternalLinks.value.filter((item) => String(item?.id || '').trim() !== id);
  await persistNavigationLinks(navExternalLinks.value, nextFooterLinks);
}

async function deleteEditingExternalMenuItem() {
  const id = String(menuItemDialogEditingExternalId.value || '').trim();
  if (!id) return;
  menuItemDialogError.value = '';
  menuItemDialogSaving.value = true;
  try {
    await deleteExternalLink(menuItemDialogTarget.value, id);
    closeMenuItemDialog();
  } catch (err) {
    menuItemDialogError.value = err?.message || 'Failed to delete external link.';
  } finally {
    menuItemDialogSaving.value = false;
  }
}

function clearSubtreeDragState() {
  subtreeDrag.sourceSlug = '';
  subtreeDrag.hoveredTargetSlug = '';
}

function computeMovedRootSlug(sourceSlug, targetSlug) {
  const sourceLeaf = sourceSlug.split('/').pop() || sourceSlug;
  return targetSlug ? `${targetSlug}/${sourceLeaf}` : sourceLeaf;
}

function isValidSubtreeDropTarget(targetSlugRaw) {
  const sourceSlug = subtreeDrag.sourceSlug;
  if (!sourceSlug) return false;

  const targetSlug = targetSlugRaw === '__root__' || targetSlugRaw === 'landing' ? '' : targetSlugRaw;
  if (!targetSlug) {
    // Root drop is valid only if it changes the slug.
    return computeMovedRootSlug(sourceSlug, '') !== sourceSlug;
  }

  if (targetSlug === sourceSlug || isSameOrDescendantSlug(targetSlug, sourceSlug)) {
    return false;
  }

  return computeMovedRootSlug(sourceSlug, targetSlug) !== sourceSlug;
}

function isSubtreeDragSource(slug) {
  return subtreeDrag.sourceSlug === slug;
}

function isSubtreeDropTarget(slugOrRoot) {
  if (!subtreeReorderEnabled.value) return false;
  if (!subtreeDrag.sourceSlug) return false;
  return subtreeDrag.hoveredTargetSlug === slugOrRoot && isValidSubtreeDropTarget(slugOrRoot);
}

function isSubtreeDropInvalid(slugOrRoot) {
  if (!subtreeReorderEnabled.value) return false;
  if (!subtreeDrag.sourceSlug) return false;
  return subtreeDrag.hoveredTargetSlug === slugOrRoot && !isValidSubtreeDropTarget(slugOrRoot);
}

function onSubtreeDragStart(sourceSlug, event) {
  if (!subtreeReorderEnabled.value || migratingSubtree.value) return;
  if (!sourceSlug || sourceSlug === 'landing') return;
  subtreeMoveError.value = '';
  subtreeDrag.sourceSlug = sourceSlug;
  subtreeDrag.hoveredTargetSlug = '';
  if (event?.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', sourceSlug);
  }
}

function onSubtreeDragEnd() {
  clearSubtreeDragState();
}

function onSubtreeTargetDragOver(targetSlug) {
  if (!subtreeReorderEnabled.value || !subtreeDrag.sourceSlug || migratingSubtree.value) return;
  subtreeDrag.hoveredTargetSlug = targetSlug;
}

async function onSubtreeDrop(targetSlugRaw) {
  if (!subtreeReorderEnabled.value || migratingSubtree.value) return;
  const sourceSlug = subtreeDrag.sourceSlug;
  if (!sourceSlug) return;

  const targetSlug = targetSlugRaw === '__root__' || targetSlugRaw === 'landing' ? '' : targetSlugRaw;
  if (!isValidSubtreeDropTarget(targetSlugRaw)) {
    return;
  }

  subtreeMoveError.value = '';
  try {
    migratingSubtree.value = true;
    await api.movePageSubtree(sourceSlug, { target_parent_slug: targetSlug || null });
    await loadPages();

    if (selectedPage.value && isSameOrDescendantSlug(selectedPage.value.slug, sourceSlug)) {
      selectedPage.value = null;
    }
  } catch (err) {
    console.error('Failed to migrate subtree:', err);
    subtreeMoveError.value = err?.message || 'Failed to migrate subtree';
  } finally {
    migratingSubtree.value = false;
    clearSubtreeDragState();
  }
}

function pagePathFromSlug(slug) {
  const normalized = String(slug || '').trim().replace(/^\/+|\/+$/g, '');
  if (!normalized || normalized === 'landing') return '/';
  return `/${normalized}`;
}

function getParentSlug(slug) {
  const normalized = String(slug || '').trim().replace(/^\/+|\/+$/g, '');
  if (!normalized || normalized === 'landing') return null;
  const parts = normalized.split('/').filter(Boolean);
  if (parts.length <= 1) return 'landing';
  return parts.slice(0, -1).join('/');
}

function resolveGeneratedOwnerParentSlug(slug, pageBySlug) {
  let parentSlug = getParentSlug(slug);
  while (parentSlug) {
    const parentPage = pageBySlug.get(parentSlug);
    if (parentPage && !isGeneratedManagedPage(parentPage)) return parentSlug;
    parentSlug = getParentSlug(parentSlug);
  }
  const landingPage = pageBySlug.get('landing');
  if (landingPage && !isGeneratedManagedPage(landingPage)) return 'landing';
  return null;
}

function getGeneratedChildCount(parentSlug) {
  const key = String(parentSlug || '').trim();
  if (!key) return 0;
  return Number(generatedChildCountsByParent.value[key] || 0);
}

function hasGeneratedChildren(page) {
  const slug = String(page?.slug || '').trim();
  if (!slug) return false;
  return getGeneratedChildCount(slug) > 0;
}

function areGeneratedChildrenExpanded(parentSlug) {
  const key = String(parentSlug || '').trim();
  if (!key) return false;
  return generatedChildrenExpandedByParent[key] === true;
}

function toggleGeneratedChildren(parentSlug) {
  const key = String(parentSlug || '').trim();
  if (!key) return;
  generatedChildrenExpandedByParent[key] = !areGeneratedChildrenExpanded(key);
}

function isGeneratedPageVisibleInTree(page) {
  if (!isGeneratedManagedPage(page)) return true;
  const slug = String(page?.slug || '').trim();
  if (!slug) return false;
  const ownerParentSlug = resolveGeneratedOwnerParentSlug(slug, visiblePageBySlug.value);
  if (!ownerParentSlug) return true;
  return areGeneratedChildrenExpanded(ownerParentSlug);
}

function isGeneratedManagedPage(page) {
  if (!page || typeof page !== 'object') return false;
  if (page.generated_from_blog === true) return true;
  if (page.template_managed === true) return true;
  const sourceType = String(page.template_source_type || '').trim().toLowerCase();
  if (
    sourceType === 'blog'
    || sourceType === 'tiles'
    || sourceType === 'program'
    || sourceType === 'program_stage'
    || sourceType === 'program_gig'
  ) return true;
  const slug = String(page.slug || '').trim().toLowerCase();
  if (slug.startsWith('__template_')) return true;
  return false;
}

function isAdminLikePagePath(path) {
  const normalized = String(path || '').trim().toLowerCase();
  return normalized === '/admin' || normalized.startsWith('/admin/');
}

function isRedirectTargetPageSelectable(page) {
  const path = pagePathFromSlug(page?.slug);
  if (isAdminLikePagePath(path)) return false;
  if (isGeneratedManagedPage(page)) return false;
  return true;
}

function formatRedirectTargetOptionLabel(page) {
  return pagePathFromSlug(page?.slug);
}

function resolveRedirectProtocolTag(item) {
  const statusCode = Number(item?.status_code) || 301;
  const target = String(item?.target_path || '').trim().toLowerCase();
  if (statusCode === 410 || !target) return 'gone';
  if (target.startsWith('https://')) return 'https';
  if (target.startsWith('http://')) return 'http';
  return 'internal';
}

function formatRedirectProtocolLabel(item) {
  const protocol = resolveRedirectProtocolTag(item);
  if (protocol === 'https') return 'HTTPS';
  if (protocol === 'http') return 'HTTP';
  if (protocol === 'gone') return 'Gone';
  return 'Internal';
}

function getPageTitle(page) {
  return page.title?.de || page.title?.en || page.slug;
}

function getMenuTitle(page) {
  const slug = String(page?.slug || '').trim();
  if (slug && (menuChildCountsByParentSlug.value.get(slug) || 0) > 0) {
    const parentTitle = page.menu_parent_title;
    if (parentTitle?.de || parentTitle?.en) {
      return parentTitle.de || parentTitle.en;
    }
  }
  return page.menu_title?.de || page.menu_title?.en || getPageTitle(page);
}

function buildMenuTitle(titleSource, enabled) {
  if (!enabled) return null;
  const de = titleSource?.de?.trim?.() || '';
  const en = titleSource?.en?.trim?.() || '';
  return de || en ? { de, en } : null;
}

function buildMenuParentTitle(titleSource, enabled) {
  if (!enabled) return null;
  const de = titleSource?.de?.trim?.() || '';
  const en = titleSource?.en?.trim?.() || '';
  return de || en ? { de, en } : null;
}

function resolveExternalIconName(iconName) {
  const normalized = String(iconName || '').trim().toLowerCase();
  if (normalized === 'twitter') return 'x-twitter';
  return normalized || 'x-twitter';
}

function getExternalLinkDisplayTitle(link) {
  const icon = String(link?.icon || '').trim().toLowerCase();
  if (icon === 'other') return 'External Link';
  if (icon === 'facebook') return 'Facebook';
  if (icon === 'instagram') return 'Instagram';
  if (icon === 'twitter') return 'Twitter';
  if (icon === 'youtube') return 'YouTube';
  if (icon === 'tiktok') return 'TikTok';

  const label = link?.label && typeof link.label === 'object' ? link.label : null;
  const localized = String(label?.de || label?.en || '').trim();
  if (localized) return localized;
  return String(link?.url || '').trim();
}

function resetMenuItemDialogExternal() {
  menuItemDialogExternal.url = '';
  menuItemDialogExternal.display_type = 'text';
  menuItemDialogExternal.label = { de: '', en: '' };
  menuItemDialogExternal.icon = 'instagram';
}

function resetCreateForm() {
  createForm.slug = '';
  createForm.title = { de: '', en: '' };
  createForm.menu_title = { de: '', en: '' };
  createForm.status = 'hidden';
  createForm.in_menu = false;
  createForm.in_footer = false;
  createForm.hide_from_sitemap = false;
  createForm.hide_subtree_from_sitemap = false;
  slugError.value = '';
}

function normalizeSlugInput(value) {
  return String(value || '').trim().replace(/^\/+|\/+$/g, '');
}

function normalizeSlugDraftInput(value) {
  return String(value || '').trim().replace(/^\/+/, '');
}

function isSlugDraftIncomplete(value) {
  return normalizeSlugDraftInput(value).endsWith('/');
}

function focusCreateDialogInput(focusTitleDe = false) {
  nextTick(() => {
    const target = focusTitleDe ? createTitleDeInput.value : createSlugInput.value;
    target?.focus?.();
    if (!focusTitleDe && isSlugDraftIncomplete(createForm.slug)) {
      const end = String(createForm.slug || '').length;
      target?.setSelectionRange?.(end, end);
      return;
    }
    target?.select?.();
  });
}

function openCreateDialog(options = {}) {
  const { slug = '', focusTitleDe = false, inMenu = false, inFooter = false } = options;
  selectedPage.value = null;
  showMenuItemDialog.value = false;
  resetCreateForm();
  if (slug) {
    createForm.slug = slug;
  }
  createForm.in_menu = inMenu;
  createForm.in_footer = inFooter;
  validateSlug();
  showCreateDialog.value = true;
  focusCreateDialogInput(focusTitleDe);
}

function closeCreateDialog() {
  showCreateDialog.value = false;
}

function openMenuItemDialog(target, options = {}) {
  showCreateDialog.value = false;
  selectedPage.value = null;
  menuItemDialogTarget.value = target === 'footer' ? 'footer' : 'menu';
  menuItemDialogMode.value = options.mode || 'create_page';
  menuItemDialogInternalSlug.value = '';
  menuItemDialogEditingExternalId.value = '';
  menuItemDialogError.value = '';
  resetMenuItemDialogExternal();

  if (options.editingLink && typeof options.editingLink === 'object') {
    const link = options.editingLink;
    menuItemDialogMode.value = 'external';
    menuItemDialogEditingExternalId.value = String(link.id || '').trim();
    menuItemDialogExternal.url = String(link.url || '').trim();
    if (link.icon) {
      menuItemDialogExternal.display_type = 'icon';
      menuItemDialogExternal.icon = String(link.icon || 'instagram').trim().toLowerCase();
      menuItemDialogExternal.label = { de: '', en: '' };
    } else {
      menuItemDialogExternal.display_type = 'text';
      menuItemDialogExternal.icon = 'instagram';
      menuItemDialogExternal.label = {
        de: String(link?.label?.de || '').trim(),
        en: String(link?.label?.en || '').trim(),
      };
    }
  }

  showMenuItemDialog.value = true;
}

function closeMenuItemDialog() {
  showMenuItemDialog.value = false;
  menuItemDialogError.value = '';
  menuItemDialogSaving.value = false;
  menuItemDialogEditingExternalId.value = '';
}

async function saveMenuItemDialog() {
  menuItemDialogError.value = '';
  menuItemDialogSaving.value = true;

  try {
    if (menuItemDialogMode.value === 'create_page') {
      const target = menuItemDialogTarget.value;
      closeMenuItemDialog();
      openCreateDialog({
        inMenu: target === 'menu',
        inFooter: target === 'footer',
      });
      return;
    }

    if (menuItemDialogMode.value === 'link_internal') {
      const slug = String(menuItemDialogInternalSlug.value || '').trim();
      if (!slug) {
        menuItemDialogError.value = 'Please select an existing page.';
        return;
      }
      if (menuItemDialogTarget.value === 'menu') {
        const maxMenuOrder = pages.value
          .filter((page) => page?.in_menu)
          .reduce(
          (maxValue, page) => Math.max(maxValue, Number(page?.menu_order ?? 0)),
          -1,
        );
        await api.updatePage(slug, { in_menu: true, menu_order: maxMenuOrder + 1 });
      } else {
        const maxFooterOrder = pages.value
          .filter((page) => page?.in_footer)
          .reduce(
          (maxValue, page) => Math.max(maxValue, Number(page?.footer_order ?? 0)),
          -1,
        );
        await api.updatePage(slug, { in_footer: true, footer_order: maxFooterOrder + 1 });
      }
      await loadPages();
      closeMenuItemDialog();
      return;
    }

    const url = String(menuItemDialogExternal.url || '').trim();
    if (!url) {
      menuItemDialogError.value = 'External URL is required.';
      return;
    }
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        menuItemDialogError.value = 'External URL must start with http:// or https://.';
        return;
      }
    } catch (_) {
      menuItemDialogError.value = 'Please enter a valid external URL.';
      return;
    }
    const displayType = menuItemDialogExternal.display_type === 'icon' ? 'icon' : 'text';

    let icon = null;
    let label = null;
    if (displayType === 'icon') {
      const normalizedIcon = String(menuItemDialogExternal.icon || '').trim().toLowerCase();
      if (!ALLOWED_EXTERNAL_SOCIAL_ICONS.includes(normalizedIcon)) {
        menuItemDialogError.value = 'Please select one of the allowed icons.';
        return;
      }
      icon = normalizedIcon;
    } else {
      const de = String(menuItemDialogExternal.label.de || '').trim();
      const en = String(menuItemDialogExternal.label.en || '').trim();
      if (!de && !en) {
        menuItemDialogError.value = 'At least one label (DE or EN) is required for text links.';
        return;
      }
      label = { de, en };
    }

    const editingId = String(menuItemDialogEditingExternalId.value || '').trim();
    const location = menuItemDialogTarget.value;
    const nextLink = {
      id: editingId || `ext-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
      url,
      label,
      icon,
    };

    if (location === 'menu') {
      const nextNavLinks = normalizeExternalLinksForSave(navExternalLinks.value);
      const existingIndex = nextNavLinks.findIndex((item) => String(item.id || '').trim() === nextLink.id);
      if (existingIndex >= 0) nextNavLinks[existingIndex] = { ...nextNavLinks[existingIndex], ...nextLink };
      else nextNavLinks.push(nextLink);
      await persistNavigationLinks(nextNavLinks, footerExternalLinks.value);
    } else {
      const nextFooterLinks = normalizeExternalLinksForSave(footerExternalLinks.value);
      const existingIndex = nextFooterLinks.findIndex((item) => String(item.id || '').trim() === nextLink.id);
      if (existingIndex >= 0) nextFooterLinks[existingIndex] = { ...nextFooterLinks[existingIndex], ...nextLink };
      else nextFooterLinks.push(nextLink);
      await persistNavigationLinks(navExternalLinks.value, nextFooterLinks);
    }

    closeMenuItemDialog();
  } catch (err) {
    menuItemDialogError.value = err?.message || 'Failed to save menu item.';
  } finally {
    menuItemDialogSaving.value = false;
  }
}

function normalizePageStatus(value) {
  const raw = String(value || '').trim().toLowerCase();
  if (raw === 'draft') return 'hidden';
  if (raw === 'init' || raw === 'published' || raw === 'under_construction' || raw === 'hidden') return raw;
  return 'hidden';
}

function getStoredPageStatus(page) {
  return normalizePageStatus(page?.status);
}

function getEffectivePageStatus(page) {
  const normalized = normalizePageStatus(page?.effective_status || page?.status);
  return normalized === 'init' ? 'hidden' : normalized;
}

function isHiddenLikeStoredStatus(status) {
  const normalized = normalizePageStatus(status);
  return normalized === 'hidden' || normalized === 'init';
}

function isPageUnderConstruction(page) {
  return getEffectivePageStatus(page) === 'under_construction';
}

function isPageHidden(page) {
  return getEffectivePageStatus(page) === 'hidden';
}

function formatPageStatusLabel(status) {
  const normalized = normalizePageStatus(status);
  if (normalized === 'init') return 'Init (new)';
  if (normalized === 'published') return 'Published';
  if (normalized === 'under_construction') return 'Under Construction';
  return 'Hidden';
}

function resolveStatusClass(status) {
  const normalized = normalizePageStatus(status);
  if (normalized === 'published') return 'published';
  if (normalized === 'under_construction') return 'under-construction';
  if (normalized === 'init') return 'hidden';
  return 'hidden';
}

function resolveEffectiveStatusClass(page) {
  return resolveStatusClass(getEffectivePageStatus(page));
}

function hasSchedule(page) {
  return page.publish_at || page.unpublish_at;
}

function hasActiveSchedule(page) {
  const now = getCurrentServerDate();
  // Has future publish date or future unpublish date
  if (page.publish_at && parseRevisionTimestamp(page.publish_at) > now) return true;
  if (page.unpublish_at && parseRevisionTimestamp(page.unpublish_at) > now) return true;
  return false;
}

function getVisibilityTooltip(page) {
  const effectiveStatus = getEffectivePageStatus(page);
  const storedStatus = getStoredPageStatus(page);
  const now = getCurrentServerDate();
  if (page.publish_at && parseRevisionTimestamp(page.publish_at) > now) {
    return `Scheduled to publish: ${formatDateTime(page.publish_at)}`;
  }
  if (page.unpublish_at && parseRevisionTimestamp(page.unpublish_at) <= now) {
    return `Hidden at: ${formatDateTime(page.unpublish_at)}`;
  }
  if (effectiveStatus === 'published' && isHiddenLikeStoredStatus(storedStatus) && page.publish_at) {
    return `Published by schedule: ${formatDateTime(page.publish_at)}`;
  }
  if (effectiveStatus === 'under_construction') {
    return 'Page is publicly reachable, but content is hidden while construction is in progress.';
  }
  if (effectiveStatus === 'published') {
    return 'Page is fully published and publicly visible.';
  }
  return 'Page is hidden from public visitors.';
}

function getScheduleTooltip(page) {
  const parts = [];
  const now = getCurrentServerDate();
  if (page.publish_at) {
    const pubDate = parseRevisionTimestamp(page.publish_at);
    if (pubDate > now) {
      parts.push(`Publishes: ${formatDateTime(page.publish_at)}`);
    } else {
      parts.push(`Published: ${formatDateTime(page.publish_at)}`);
    }
  }
  if (page.unpublish_at) {
    const unpubDate = parseRevisionTimestamp(page.unpublish_at);
    if (unpubDate > now) {
      parts.push(`Unpublishes: ${formatDateTime(page.unpublish_at)}`);
    } else {
      parts.push(`Unpublished: ${formatDateTime(page.unpublish_at)}`);
    }
  }
  return parts.join('\n');
}

function getCrawlerVisibilityTooltip(page) {
  if (page.hide_subtree_from_sitemap) {
    return 'This page subtree is disallowed in robots.txt';
  }
  if (page.hide_from_sitemap) {
    return 'This page is disallowed in robots.txt while child routes are allowed';
  }
  return '';
}

function setRobotsDisallowActive(checked) {
  const isChecked = Boolean(checked);
  if (!isChecked) {
    editForm.hide_subtree_from_sitemap = false;
    editForm.hide_from_sitemap = false;
    autoSavePageChanges();
    return;
  }
  if (!editForm.hide_subtree_from_sitemap && !editForm.hide_from_sitemap) {
    editForm.hide_subtree_from_sitemap = true;
  }
  autoSavePageChanges();
}

function setRobotsPageOnlyDisallow(checked) {
  const isChecked = Boolean(checked);
  editForm.hide_from_sitemap = isChecked;
  editForm.hide_subtree_from_sitemap = !isChecked;
  autoSavePageChanges();
}

function resetBulkChildVisibilitySelection() {
  bulkChildVisibilityStatus.value = '';
  bulkChildVisibilityMenuOpen.value = false;
}

function beginBulkChildVisibilityInteraction() {
  if (bulkChildVisibilityInteractionTimer) {
    clearTimeout(bulkChildVisibilityInteractionTimer);
    bulkChildVisibilityInteractionTimer = null;
  }
  bulkChildVisibilityInteracting.value = true;
}

function endBulkChildVisibilityInteraction({ delay = 0 } = {}) {
  if (bulkChildVisibilityInteractionTimer) {
    clearTimeout(bulkChildVisibilityInteractionTimer);
    bulkChildVisibilityInteractionTimer = null;
  }

  if (delay > 0) {
    bulkChildVisibilityInteractionTimer = setTimeout(() => {
      bulkChildVisibilityInteracting.value = false;
      bulkChildVisibilityInteractionTimer = null;
    }, delay);
    return;
  }

  bulkChildVisibilityInteracting.value = false;
}

function openBulkChildVisibilityMenu() {
  beginBulkChildVisibilityInteraction();
  bulkChildVisibilityMenuOpen.value = true;
}

function closeBulkChildVisibilityMenu({ delay = 0 } = {}) {
  bulkChildVisibilityMenuOpen.value = false;
  endBulkChildVisibilityInteraction({ delay });
}

function toggleBulkChildVisibilityMenu() {
  if (bulkChildVisibilitySaving.value || selectedPageSubpages.value.length === 0) return;
  if (bulkChildVisibilityMenuOpen.value) {
    closeBulkChildVisibilityMenu();
    return;
  }
  openBulkChildVisibilityMenu();
}

function handleBulkChildVisibilityDocumentPointerDown(event) {
  if (!bulkChildVisibilityMenuOpen.value) return;
  const root = bulkChildVisibilityDropdownRef.value;
  if (root && event?.target && root.contains(event.target)) return;
  closeBulkChildVisibilityMenu();
}

async function onBulkChildVisibilityStatusSelect(value) {
  beginBulkChildVisibilityInteraction();
  bulkChildVisibilityMenuOpen.value = false;
  const nextStatus = String(value || '').trim();
  bulkChildVisibilityStatus.value = nextStatus;

  const option = bulkChildVisibilityStatusOptions.find((item) => item.value === nextStatus);
  if (!option || !selectedPage.value) {
    resetBulkChildVisibilitySelection();
    endBulkChildVisibilityInteraction();
    return;
  }

  const descendants = selectedPageSubpages.value;
  if (descendants.length === 0) {
    resetBulkChildVisibilitySelection();
    endBulkChildVisibilityInteraction();
    return;
  }

  const directoryPath = pagePathFromSlug(selectedPage.value.slug);
  const previewLimit = 8;
  const previewPaths = descendants
    .slice(0, previewLimit)
    .map((page) => pagePathFromSlug(page.slug));
  const remainingCount = descendants.length - previewPaths.length;
  const suffix = descendants.length === 1 ? '' : 's';
  const previewText = previewPaths.length > 0
    ? `\n\nExamples:\n${previewPaths.join('\n')}${remainingCount > 0 ? `\n...and ${remainingCount} more.` : ''}`
    : '';
  const ok = window.confirm(
    `Set ${descendants.length} child page${suffix} under "${directoryPath}" to "${option.label}"?${previewText}`
  );
  if (!ok) {
    resetBulkChildVisibilitySelection();
    endBulkChildVisibilityInteraction();
    return;
  }

  bulkChildVisibilitySaving.value = true;
  try {
    const updatedPages = [];
    for (const page of descendants) {
      updatedPages.push(await api.updatePage(page.slug, { status: nextStatus }));
    }
    const updatedById = new Map(updatedPages.map((page) => [page.id, page]));
    const updatedBySlug = new Map(updatedPages.map((page) => [page.slug, page]));
    pages.value = pages.value.map((page) => (
      updatedById.get(page.id) || updatedBySlug.get(page.slug) || page
    ));
    await refreshSitemapSummary();
  } catch (err) {
    console.error('Failed to update child page visibility:', err);
    alert('Failed to update child page visibility: ' + (err?.message || 'Unknown error'));
  } finally {
    bulkChildVisibilitySaving.value = false;
    resetBulkChildVisibilitySelection();
    endBulkChildVisibilityInteraction();
  }
}

function setEditPageStatus(status) {
  const normalized = normalizePageStatus(status);
  if (editForm.status === normalized) return;
  editForm.status = normalized;
  autoSavePageChanges();
}

function formatDateTime(isoString) {
  return formatInstantInServerTimezone(isoString);
}

function selectPage(page) {
  showCreateDialog.value = false;
  showMenuItemDialog.value = false;
  selectedPage.value = page;
  openEditSection.value = 'visibility';
  editForm.slug = page.slug || '';
  editForm.title_de = page.title?.de || '';
  editForm.title_en = page.title?.en || '';
  editForm.menu_title_de = page.menu_title?.de || '';
  editForm.menu_title_en = page.menu_title?.en || '';
  editForm.menu_parent_title_de = page.menu_parent_title?.de || '';
  editForm.menu_parent_title_en = page.menu_parent_title?.en || '';
  editForm.menu_show_as_top_level = page.menu_show_as_top_level || false;
  editForm.status = normalizePageStatus(page.status || 'hidden');
  // Parse ISO strings (UTC) to Date objects for datepicker (displays in local time)
  editForm.publish_at = parseUTCToLocal(page.publish_at);
  editForm.unpublish_at = parseUTCToLocal(page.unpublish_at);
  editForm.in_menu = page.in_menu || false;
  editForm.in_footer = page.in_footer || false;
  editForm.hide_from_sitemap = page.hide_from_sitemap || false;
  editForm.hide_subtree_from_sitemap = page.hide_subtree_from_sitemap || false;
  editForm.sitemap_priority = page.sitemap_priority ?? '';
  editForm.sitemap_changefreq = page.sitemap_changefreq || '';
  // Normalize redirect_to to match dropdown format (leading slash)
  let redirect = page.redirect_to || '';
  if (redirect && !redirect.startsWith('/') && !redirect.startsWith('http')) {
    redirect = '/' + redirect;
  }
  editForm.redirect_to = redirect;
  validateEditSlug();
  syncLastSavedEditSnapshot();
}

function startCreateSubpage(parentPage) {
  // Pre-fill the slug with the parent's slug as prefix
  const parentSlug = parentPage.slug === 'landing' ? '' : parentPage.slug;
  openCreateDialog({
    slug: parentSlug ? `${parentSlug}/` : '',
    focusTitleDe: false,
    inMenu: parentPage.in_menu || false,
    inFooter: parentPage.in_footer || false,
  });
}

async function renameSelectedPage() {
  if (!selectedPage.value) return;

  const currentSlug = selectedPage.value.slug;
  const nextSlug = normalizeSlugInput(editForm.slug);
  if (!nextSlug || nextSlug === currentSlug) return;

  validateEditSlug();
  if (editSlugError.value) return;

  const ok = window.confirm(
    `Rename "/${currentSlug}" to "/${nextSlug}"?\n\nPermanent redirects will be generated from old routes to the new routes.`
  );
  if (!ok) return;

  renaming.value = true;
  try {
    const result = await api.renamePageRoute(currentSlug, { new_slug: nextSlug });
    await Promise.all([loadPages(), loadRedirects(), refreshSitemapSummary()]);
    const renamedSlug = String(result?.new_root_slug || nextSlug);
    const renamedPage = pages.value.find((page) => page.slug === renamedSlug);
    if (renamedPage) {
      selectPage(renamedPage);
    } else {
      selectedPage.value = null;
    }
  } catch (err) {
    console.error('Failed to rename page:', err);
    alert('Failed to rename page: ' + (err?.message || 'Unknown error'));
  } finally {
    renaming.value = false;
  }
}

function validateSlug() {
  const draftSlug = normalizeSlugDraftInput(createForm.slug);
  createForm.slug = draftSlug;
  const slug = normalizeSlugInput(draftSlug);
  if (!slug) {
    slugError.value = '';
    return;
  }
  if (isSlugDraftIncomplete(draftSlug)) {
    slugError.value = '';
    return;
  }
  if (!SLUG_PATTERN.test(slug)) {
    slugError.value = 'Invalid format. Use lowercase letters, numbers, hyphens, and slashes.';
    return;
  }
  if (pages.value.some(p => p.slug === slug)) {
    slugError.value = 'This slug is already taken.';
    return;
  }
  slugError.value = '';
}

function validateEditSlug() {
  if (!selectedPage.value) {
    editSlugError.value = '';
    return;
  }

  const slug = normalizeSlugInput(editForm.slug);
  editForm.slug = slug;

  if (!slug) {
    editSlugError.value = 'Slug is required.';
    return;
  }
  if (!SLUG_PATTERN.test(slug)) {
    editSlugError.value = 'Invalid format. Use lowercase letters, numbers, hyphens, and slashes.';
    return;
  }
  if (slug === 'landing' && selectedPage.value.slug !== 'landing') {
    editSlugError.value = 'Slug "landing" is reserved for the root page.';
    return;
  }
  if (pages.value.some((p) => p.slug === slug && p.id !== selectedPage.value.id)) {
    editSlugError.value = 'This slug is already taken.';
    return;
  }

  editSlugError.value = '';
}

async function loadPages() {
  try {
    loading.value = true;
    const result = await api.listPages({ limit: 5000, includeHidden: true });
    pages.value = result;
  } catch (err) {
    console.error('Failed to load pages:', err);
  } finally {
    loading.value = false;
  }
}

function toIsoFromLocalInput(localDateTimeValue) {
  if (!localDateTimeValue) return null;
  const date = serverWallDateTimeToInstantDate(localDateTimeValue);
  if (!date || Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function toLocalInputFromIso(isoValue) {
  return formatDateTimeLocalForServerTimezone(isoValue);
}

function normalizeInternalPathInput(path) {
  const raw = String(path || '').trim();
  if (!raw) return '';
  const withoutQuery = raw.split('?')[0].split('#')[0];
  const withLeadingSlash = withoutQuery.startsWith('/') ? withoutQuery : `/${withoutQuery}`;
  const collapsed = withLeadingSlash.replace(/\/{2,}/g, '/');
  return collapsed.length > 1 ? collapsed.replace(/\/+$/, '') : collapsed;
}

function normalizeRedirectSourceInput(path) {
  const raw = String(path || '').trim();
  if (!raw) return '';
  const withoutHash = raw.split('#')[0];
  const withLeadingSlash = withoutHash.startsWith('/') ? withoutHash : `/${withoutHash}`;
  const collapsed = withLeadingSlash.replace(/\/{2,}/g, '/');
  return collapsed.length > 1 ? collapsed.replace(/\/+$/, '') : collapsed;
}

function normalizeRedirectTargetInput(target) {
  const raw = String(target || '').trim();
  if (!raw) return '';
  if (raw.startsWith('http://') || raw.startsWith('https://')) return raw;
  return normalizeInternalPathInput(raw);
}

function sortRedirects(items) {
  return [...items].sort((a, b) => {
    const sourceCmp = String(a.source_path || '').localeCompare(String(b.source_path || ''));
    if (sourceCmp !== 0) return sourceCmp;
    return String(a.kind || '').localeCompare(String(b.kind || ''));
  });
}

function redirectSelectionKey(item) {
  if (!item || item.id === undefined || item.id === null) return '';
  return String(item.id);
}

function isRedirectEditing(item) {
  const id = redirectSelectionKey(item);
  return Boolean(id) && id === editingRedirectId.value;
}

function startRedirectEdit(item) {
  const id = redirectSelectionKey(item);
  if (!id || deletingRedirects.value || savingRedirectEdit.value) return;

  editingRedirectId.value = id;
  redirectEditForm.source_path = String(item?.source_path || '');
  redirectEditForm.target_path = String(item?.target_path || '');
  redirectEditForm.status_code = Number(item?.status_code) || 301;
  redirectEditForm.expires_at = toLocalInputFromIso(item?.expires_at);
  redirectEditForm.is_active = item?.is_enabled !== false;
  redirectEditError.value = '';
}

function cancelRedirectEdit() {
  editingRedirectId.value = '';
  redirectEditError.value = '';
}

function isRedirectSelected(item) {
  const id = redirectSelectionKey(item);
  return Boolean(id) && selectedRedirectIdSet.value.has(id);
}

function toggleRedirectSelection(item, checked) {
  const id = redirectSelectionKey(item);
  if (!id) return;
  const selected = new Set(selectedRedirectIds.value);
  if (checked) selected.add(id);
  else selected.delete(id);
  selectedRedirectIds.value = [...selected];
}

function handleRedirectItemClick(item) {
  if (deletingRedirects.value) return;
  const id = redirectSelectionKey(item);
  if (!id) return;

  if (redirectMultiSelectMode.value) {
    toggleRedirectSelection(item, !isRedirectSelected(item));
    return;
  }

  selectedRedirectIds.value = (
    selectedRedirectIds.value.length === 1
    && selectedRedirectIds.value[0] === id
  )
    ? []
    : [id];
}

function clearRedirectSelection() {
  selectedRedirectIds.value = [];
}

function toggleSelectAllFilteredRedirects() {
  const filteredIds = filteredRedirects.value
    .map((item) => redirectSelectionKey(item))
    .filter(Boolean);
  if (filteredIds.length === 0) return;

  const selected = new Set(selectedRedirectIds.value);
  if (allFilteredRedirectsSelected.value) {
    filteredIds.forEach((id) => selected.delete(id));
  } else {
    filteredIds.forEach((id) => selected.add(id));
  }
  selectedRedirectIds.value = [...selected];
}

function syncRedirectSelectionWithLoadedItems() {
  const availableIds = new Set(
    redirects.value
      .map((item) => redirectSelectionKey(item))
      .filter(Boolean),
  );
  selectedRedirectIds.value = selectedRedirectIds.value.filter((id) => availableIds.has(id));
  if (editingRedirectId.value && !availableIds.has(editingRedirectId.value)) {
    cancelRedirectEdit();
  }
}

function resetRedirectForm() {
  redirectForm.source_path = '';
  redirectForm.target_path = '';
  redirectForm.status_code = 301;
  redirectForm.expires_at = '';
  redirectCreateError.value = '';
}

async function refreshSitemapSummary() {
  summaryRefreshing.value = true;
  summaryError.value = '';
  try {
    sitemapSummary.value = await api.getSitemapSummary();
  } catch (err) {
    summaryError.value = err?.message || 'Failed to load sitemap summary';
  } finally {
    summaryRefreshing.value = false;
  }
}

async function loadSitemapStats() {
  sitemapStatsLoading.value = true;
  sitemapStatsError.value = '';
  try {
    sitemapStatsPayload.value = await api.getSitemapStats({ days: selectedSitemapStatsRange.value });
    const pageIds = new Set(sitemapStatsPages.value.map((page) => String(page.id)));
    for (const groupId of sitemapStatsGeneratedGroups.value.keys()) {
      pageIds.add(groupId);
    }
    if (selectedStatsPageId.value && !pageIds.has(selectedStatsPageId.value)) {
      selectedStatsPageId.value = '';
    }
  } catch (err) {
    sitemapStatsError.value = err?.message || 'Failed to load sitemap stats';
    sitemapStatsPayload.value = null;
  } finally {
    sitemapStatsLoading.value = false;
  }
}

async function resetSitemapStats() {
  if (sitemapStatsResetting.value) return;
  const ok = window.confirm('Reset all page hit stats? This clears total hits and daily timeline data.');
  if (!ok) return;

  sitemapStatsResetting.value = true;
  sitemapStatsError.value = '';
  try {
    await api.resetSitemapStats();
    selectedStatsPageId.value = '';
    await Promise.all([loadSitemapStats(), loadPages()]);
  } catch (err) {
    sitemapStatsError.value = err?.message || 'Failed to reset sitemap stats';
  } finally {
    sitemapStatsResetting.value = false;
  }
}

function updateStatsTimelineContainerWidth() {
  const element = statsTimelineScrollRef.value;
  if (!element) return;
  const width = Math.floor(element.clientWidth || 0);
  if (width > 0) {
    statsTimelineContainerWidth.value = width;
  }
}

function setupStatsTimelineResizeObserver() {
  const element = statsTimelineScrollRef.value;
  if (!element || typeof ResizeObserver === 'undefined') {
    updateStatsTimelineContainerWidth();
    return;
  }
  if (statsTimelineResizeObserver && statsTimelineObservedElement !== element) {
    teardownStatsTimelineResizeObserver();
  }
  if (statsTimelineResizeObserver) {
    updateStatsTimelineContainerWidth();
    return;
  }
  statsTimelineResizeObserver = new ResizeObserver(() => {
    updateStatsTimelineContainerWidth();
  });
  statsTimelineResizeObserver.observe(element);
  statsTimelineObservedElement = element;
  updateStatsTimelineContainerWidth();
}

function teardownStatsTimelineResizeObserver() {
  if (!statsTimelineResizeObserver) return;
  statsTimelineResizeObserver.disconnect();
  statsTimelineResizeObserver = null;
  statsTimelineObservedElement = null;
}

async function loadRobots() {
  robotsLoading.value = true;
  robotsError.value = '';
  try {
    const payload = await api.getSitemapRobots();
    robotsPayload.value = payload;
    robotsCustomText.value = payload?.custom_text || '';
  } catch (err) {
    robotsError.value = err?.message || 'Failed to load robots.txt configuration';
  } finally {
    robotsLoading.value = false;
  }
}

async function saveRobots() {
  robotsSaving.value = true;
  robotsError.value = '';
  try {
    const payload = await api.updateSitemapRobots(robotsCustomText.value);
    robotsPayload.value = payload;
    robotsCustomText.value = payload?.custom_text || '';
  } catch (err) {
    robotsError.value = err?.message || 'Failed to save robots.txt configuration';
  } finally {
    robotsSaving.value = false;
  }
}

function normalizeCachingUnit(value) {
  const unit = String(value || '').trim();
  return Object.prototype.hasOwnProperty.call(CACHING_UNIT_SECONDS, unit) ? unit : 'seconds';
}

function getCachingUnitSeconds(unit) {
  return CACHING_UNIT_SECONDS[normalizeCachingUnit(unit)] || 1;
}

function getCachingMaxForUnit(unit) {
  return Math.floor(CACHING_MAX_TTL_SECONDS / getCachingUnitSeconds(unit));
}

function getCachingRuleTtlSeconds(rule) {
  const amount = Math.trunc(Number(rule?.amount ?? 0));
  if (!Number.isFinite(amount) || amount < 0) return -1;
  return amount * getCachingUnitSeconds(rule?.unit);
}

function hydrateCachingRule(rule) {
  const ttlSeconds = Math.max(0, Number(rule?.ttl_seconds || 0));
  let unit = normalizeCachingUnit(rule?.unit);
  let divisor = getCachingUnitSeconds(unit);
  if (ttlSeconds % divisor !== 0) {
    unit = 'seconds';
    divisor = 1;
  }
  return {
    id: String(rule?.id || ''),
    label: String(rule?.label || ''),
    enabled: Boolean(rule?.enabled),
    amount: Math.trunc(ttlSeconds / divisor),
    unit,
    extensions: Array.isArray(rule?.extensions) ? rule.extensions : [],
    mime_types: Array.isArray(rule?.mime_types) ? rule.mime_types : [],
    immutable: Boolean(rule?.immutable),
    cache_control: String(rule?.cache_control || ''),
  };
}

function serializeCachingRuleForApi(rule) {
  return {
    id: String(rule?.id || ''),
    enabled: Boolean(rule?.enabled),
    ttl_seconds: getCachingRuleTtlSeconds(rule),
    immutable: Boolean(rule?.immutable),
  };
}

function serializeCachingRulesForSnapshot(rules) {
  return JSON.stringify((Array.isArray(rules) ? rules : []).map(serializeCachingRuleForApi));
}

function isCachingRuleValid(rule) {
  const ttlSeconds = getCachingRuleTtlSeconds(rule);
  return Boolean(rule?.id)
    && Number.isInteger(ttlSeconds)
    && ttlSeconds >= 0
    && ttlSeconds <= CACHING_MAX_TTL_SECONDS;
}

function formatCachingList(values, prefix = '') {
  const list = Array.isArray(values) ? values : [];
  if (list.length === 0) return '—';
  return list.map((item) => `${prefix}${item}`).join(', ');
}

function formatCachingCacheControl(rule) {
  if (String(rule?.id || '') === 'html' && rule?.cache_control) {
    return rule.cache_control;
  }
  const ttlSeconds = Math.max(0, getCachingRuleTtlSeconds(rule));
  return `public, max-age=${ttlSeconds}${rule?.immutable ? ', immutable' : ''}`;
}

function applyCachingPayload(payload) {
  cachingPayload.value = payload || {};
  cachingRules.value = Array.isArray(payload?.rules)
    ? payload.rules.map(hydrateCachingRule)
    : [];
  cachingLastSavedSnapshot.value = serializeCachingRulesForSnapshot(cachingRules.value);
}

async function loadCachingRules() {
  cachingLoading.value = true;
  cachingError.value = '';
  try {
    const payload = await api.getSitemapCaching();
    applyCachingPayload(payload);
  } catch (err) {
    cachingError.value = err?.message || 'Failed to load caching rules';
  } finally {
    cachingLoading.value = false;
  }
}

async function saveCachingRules() {
  if (cachingHasInvalidRules.value) {
    cachingError.value = `Caching lifetimes must be between 0 and ${CACHING_MAX_TTL_SECONDS} seconds.`;
    return;
  }
  if (!cachingHasUnsavedChanges.value) return;

  cachingSaving.value = true;
  cachingError.value = '';
  cachingStatus.value = '';
  try {
    const payload = await api.updateSitemapCaching({
      rules: cachingRules.value.map(serializeCachingRuleForApi),
    });
    applyCachingPayload(payload);
    cachingStatus.value = 'Caching rules saved.';
  } catch (err) {
    cachingError.value = err?.message || 'Failed to save caching rules';
  } finally {
    cachingSaving.value = false;
  }
}

function resetCachingRulesToDefaults() {
  const defaultRules = cachingPayload.value?.defaults?.rules;
  if (!Array.isArray(defaultRules) || defaultRules.length === 0 || cachingResetDisabled.value) return;
  cachingRules.value = defaultRules.map(hydrateCachingRule);
  cachingError.value = '';
  cachingStatus.value = 'Balanced defaults restored locally. Save rules to update the preview.';
}

function onCachingUnitChange(rule, nextUnit) {
  if (!rule) return;
  const currentTtl = Math.max(0, getCachingRuleTtlSeconds(rule));
  const unit = normalizeCachingUnit(nextUnit);
  const divisor = getCachingUnitSeconds(unit);
  rule.unit = unit;
  rule.amount = currentTtl === 0 ? 0 : Math.max(1, Math.round(currentTtl / divisor));
}

async function writeTextToClipboard(text) {
  if (navigator?.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', 'readonly');
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand('copy');
  document.body.removeChild(textarea);
  if (!copied) {
    throw new Error('Clipboard copy failed');
  }
}

async function copyHtaccessCachingRules() {
  const text = cachingPreviewText.value;
  if (!text || cachingHasUnsavedChanges.value) return;
  cachingError.value = '';
  cachingStatus.value = '';
  try {
    await writeTextToClipboard(text);
    cachingStatus.value = 'Copied .htaccess rules.';
  } catch (err) {
    cachingError.value = err?.message || 'Failed to copy .htaccess rules';
  }
}

async function regenerateSitemapXml() {
  summaryRefreshing.value = true;
  summaryError.value = '';
  try {
    await api.regenerateSitemap();
    sitemapSummary.value = await api.getSitemapSummary();
  } catch (err) {
    summaryError.value = err?.message || 'Failed to regenerate sitemap.xml';
  } finally {
    summaryRefreshing.value = false;
  }
}

async function loadRedirects() {
  redirectsLoading.value = true;
  redirectListError.value = '';
  try {
    const list = await api.listSitemapRedirects({ includeExpired: true });
    redirects.value = sortRedirects(list || []);
    syncRedirectSelectionWithLoadedItems();
  } catch (err) {
    redirectListError.value = err?.message || 'Failed to load redirects';
  } finally {
    redirectsLoading.value = false;
  }
}

async function createRedirect() {
  const sourcePath = normalizeRedirectSourceInput(redirectForm.source_path);
  const statusCode = Number(redirectForm.status_code) || 301;
  const requiresTarget = statusCode !== 410;
  const targetPath = requiresTarget
    ? normalizeRedirectTargetInput(redirectForm.target_path)
    : null;
  if (!sourcePath || (requiresTarget && !targetPath)) {
    redirectCreateError.value = requiresTarget
      ? 'Please provide both source and target.'
      : 'Please provide a source path.';
    return;
  }
  if (targetPath && sourcePath === targetPath) {
    redirectCreateError.value = 'Redirect source and target cannot be identical.';
    return;
  }

  creatingRedirect.value = true;
  redirectCreateError.value = '';
  try {
    await api.createSitemapRedirect({
      source_path: sourcePath,
      target_path: targetPath,
      status_code: statusCode,
      expires_at: toIsoFromLocalInput(redirectForm.expires_at),
      is_active: true,
    });
    resetRedirectForm();
    await Promise.all([loadRedirects(), refreshSitemapSummary()]);
  } catch (err) {
    redirectCreateError.value = err?.message || 'Failed to create redirect';
  } finally {
    creatingRedirect.value = false;
  }
}

function onRedirectEnabledChange(item, checked) {
  if (isGeneratedRedirect(item)) {
    saveGeneratedRedirectEnabled(item, checked);
    return;
  }
  redirectEditForm.is_active = Boolean(checked);
  redirectEditError.value = '';
}

async function saveGeneratedRedirectEnabled(item, checked) {
  const redirectId = redirectSelectionKey(item);
  if (!redirectId || deletingRedirects.value || savingRedirectEdit.value) return;

  const previousEnabled = item?.is_enabled !== false;
  redirectEditForm.is_active = Boolean(checked);
  savingRedirectEdit.value = true;
  redirectEditError.value = '';
  try {
    const updated = await api.updateSitemapRedirect(redirectId, {
      is_active: Boolean(checked),
    });
    redirects.value = sortRedirects(
      redirects.value.map((existing) => (
        redirectSelectionKey(existing) === redirectId ? updated : existing
      )),
    );
    if (editingRedirectId.value === redirectId) {
      redirectEditForm.is_active = updated?.is_enabled !== false;
    }
    await refreshSitemapSummary();
  } catch (err) {
    redirectEditForm.is_active = previousEnabled;
    redirectEditError.value = err?.message || 'Failed to update redirect';
  } finally {
    savingRedirectEdit.value = false;
  }
}

async function saveRedirectEdit() {
  const redirectId = String(editingRedirectId.value || '').trim();
  if (!redirectId || deletingRedirects.value) return;

  const sourcePath = normalizeRedirectSourceInput(redirectEditForm.source_path);
  const statusCode = Number(redirectEditForm.status_code) || 301;
  const requiresTarget = statusCode !== 410;
  const targetPath = requiresTarget
    ? normalizeRedirectTargetInput(redirectEditForm.target_path)
    : null;

  if (!sourcePath || (requiresTarget && !targetPath)) {
    redirectEditError.value = requiresTarget
      ? 'Please provide both source and target.'
      : 'Please provide a source path.';
    return;
  }
  if (targetPath && sourcePath === targetPath) {
    redirectEditError.value = 'Redirect source and target cannot be identical.';
    return;
  }

  savingRedirectEdit.value = true;
  redirectEditError.value = '';
  try {
    await api.updateSitemapRedirect(redirectId, {
      source_path: sourcePath,
      target_path: targetPath,
      status_code: statusCode,
      expires_at: toIsoFromLocalInput(redirectEditForm.expires_at),
      is_active: Boolean(redirectEditForm.is_active),
    });
    cancelRedirectEdit();
    await Promise.all([loadRedirects(), refreshSitemapSummary()]);
  } catch (err) {
    redirectEditError.value = err?.message || 'Failed to update redirect';
  } finally {
    savingRedirectEdit.value = false;
  }
}

async function deleteSelectedRedirects() {
  const selectedSet = new Set(selectedRedirectIds.value);
  const selectedItems = redirects.value.filter((item) => selectedSet.has(redirectSelectionKey(item)));
  const total = selectedItems.length;

  if (total === 0) {
    selectedRedirectIds.value = [];
    return;
  }

  const ok = window.confirm(`Delete ${total} selected redirect${total === 1 ? '' : 's'}?`);
  if (!ok) return;

  deletingRedirects.value = true;
  redirectListError.value = '';
  try {
    const results = await Promise.allSettled(
      selectedItems.map((item) => api.deleteSitemapRedirect(item.id)),
    );

    const failedItems = [];
    let firstErrorMessage = '';
    results.forEach((result, idx) => {
      if (result.status === 'rejected') {
        failedItems.push(selectedItems[idx]);
        if (!firstErrorMessage) {
          firstErrorMessage = result.reason?.message || 'Failed to delete redirect';
        }
      }
    });

    await Promise.all([loadRedirects(), refreshSitemapSummary()]);

    if (failedItems.length > 0) {
      selectedRedirectIds.value = failedItems
        .map((item) => redirectSelectionKey(item))
        .filter(Boolean);
      if (failedItems.length === total) {
        redirectListError.value = firstErrorMessage;
      } else {
        redirectListError.value = `Deleted ${total - failedItems.length} of ${total} redirects. ${failedItems.length} failed. ${firstErrorMessage}`;
      }
      return;
    }

    selectedRedirectIds.value = [];
  } catch (err) {
    redirectListError.value = err?.message || 'Failed to delete selected redirects';
  } finally {
    deletingRedirects.value = false;
  }
}

function buildPageEditPayload() {
  const menuTitle = buildMenuTitle(
    { de: editForm.menu_title_de, en: editForm.menu_title_en },
    editForm.in_menu,
  );
  const menuParentTitle = buildMenuParentTitle(
    { de: editForm.menu_parent_title_de, en: editForm.menu_parent_title_en },
    editForm.in_menu && selectedPageIsMenuParentNode.value,
  );
  return {
    title: { de: editForm.title_de, en: editForm.title_en },
    status: normalizePageStatus(editForm.status),
    in_menu: editForm.in_menu,
    in_footer: editForm.in_footer,
    menu_title: menuTitle,
    menu_parent_title: menuParentTitle,
    menu_show_as_top_level: editForm.in_menu ? editForm.menu_show_as_top_level : false,
    publish_at: dateToUTCISOString(editForm.publish_at),
    unpublish_at: dateToUTCISOString(editForm.unpublish_at),
    hide_from_sitemap: robotsPageOnlyDisallow.value,
    hide_subtree_from_sitemap: robotsDisallowActive.value && !robotsPageOnlyDisallow.value,
    sitemap_priority:
      editForm.sitemap_priority === '' || editForm.sitemap_priority === null
        ? null
        : Math.max(0, Math.min(1, Number(editForm.sitemap_priority))),
    sitemap_changefreq: editForm.sitemap_changefreq || null,
    redirect_to: editForm.redirect_to || null
  };
}

function serializePageEditPayload(payload) {
  return JSON.stringify(payload || {});
}

function syncLastSavedEditSnapshot() {
  if (!selectedPage.value) {
    lastSavedEditSnapshot.value = '';
    return;
  }
  lastSavedEditSnapshot.value = serializePageEditPayload(buildPageEditPayload());
}

function clearPageAutosaveStatusTimer() {
  if (pageAutosaveStatusTimer) {
    clearTimeout(pageAutosaveStatusTimer);
    pageAutosaveStatusTimer = null;
  }
}

function setPageAutosaveStatus(status) {
  clearPageAutosaveStatusTimer();
  pageAutosaveStatus.value = status;
}

function markPageAutosaveSaved() {
  pageAutosaveError.value = '';
  setPageAutosaveStatus('saved');
  pageAutosaveStatusTimer = setTimeout(() => {
    if (pageAutosaveStatus.value === 'saved') {
      pageAutosaveStatus.value = 'idle';
    }
    pageAutosaveStatusTimer = null;
  }, 3000);
}

function markPageAutosaveError(message = 'Failed to save page') {
  pageAutosaveError.value = message;
  setPageAutosaveStatus('error');
  pageAutosaveStatusTimer = setTimeout(() => {
    if (pageAutosaveStatus.value === 'error') {
      pageAutosaveStatus.value = 'idle';
      pageAutosaveError.value = '';
    }
    pageAutosaveStatusTimer = null;
  }, 3000);
}

function queuePageAutosave() {
  if (saving.value) {
    pageAutosavePending.value = true;
    setPageAutosaveStatus('queued');
    return;
  }
  nextTick(() => {
    autoSavePageChanges();
  });
}

function autoSavePageChanges() {
  return savePageChanges();
}

async function savePageChanges({ force = false } = {}) {
  if (!selectedPage.value) return;
  if (saving.value) {
    pageAutosavePending.value = true;
    setPageAutosaveStatus('queued');
    return;
  }

  const pageId = selectedPage.value.id;
  const pageSlug = selectedPage.value.slug;
  const data = buildPageEditPayload();
  const snapshot = serializePageEditPayload(data);
  if (!force && snapshot === lastSavedEditSnapshot.value) {
    if (pageAutosaveStatus.value === 'saving' || pageAutosaveStatus.value === 'queued') {
      markPageAutosaveSaved();
    }
    return;
  }
  
  try {
    saving.value = true;
    pageAutosavePending.value = false;
    pageAutosaveError.value = '';
    setPageAutosaveStatus('saving');
    const updatedPage = await api.updatePage(pageSlug, data);
    
    const idx = pages.value.findIndex(p => p.id === pageId);
    if (idx !== -1) {
      pages.value[idx] = updatedPage;
      if (selectedPage.value?.id === pageId) {
        if (!bulkChildVisibilityInteracting.value && !bulkChildVisibilitySaving.value) {
          selectedPage.value = pages.value[idx];
        }
        lastSavedEditSnapshot.value = snapshot;
      }
    }
    markPageAutosaveSaved();
  } catch (err) {
    console.error('Failed to save page:', err);
    markPageAutosaveError(err?.message || 'Failed to save page');
    alert('Failed to save: ' + err.message);
  } finally {
    saving.value = false;
    if (pageAutosavePending.value && selectedPage.value?.id === pageId) {
      pageAutosavePending.value = false;
      queuePageAutosave();
    }
  }
}

async function createPage() {
  const slug = normalizeSlugInput(createForm.slug);
  if (!slug || isSlugDraftIncomplete(createForm.slug) || slugError.value) return;
  createForm.slug = slug;
  validateSlug();
  if (slugError.value) return;
  
  try {
    creating.value = true;
    const menuTitle = buildMenuTitle(createForm.menu_title, createForm.in_menu);
    const data = {
      slug,
      title: createForm.title,
      has_header: true,
      status: normalizePageStatus(createForm.status),
      in_menu: createForm.in_menu,
      in_footer: createForm.in_footer,
      menu_title: menuTitle,
      hide_from_sitemap: createForm.hide_from_sitemap,
      hide_subtree_from_sitemap: createForm.hide_subtree_from_sitemap,
    };
    
    const newPage = await api.createPage(data);
    pages.value.push(newPage);
    
    closeCreateDialog();
    resetCreateForm();
  } catch (err) {
    console.error('Failed to create page:', err);
    alert('Failed to create page: ' + err.message);
  } finally {
    creating.value = false;
  }
}

async function deleteSelectedSubpages() {
  if (!selectedPage.value) return;
  const descendants = selectedPageSubpages.value;
  if (descendants.length === 0) return;

  const directoryPath = pagePathFromSlug(selectedPage.value.slug);
  const previewLimit = 8;
  const previewPaths = descendants
    .slice(0, previewLimit)
    .map((page) => pagePathFromSlug(page.slug));
  const remainingCount = descendants.length - previewPaths.length;
  const suffix = descendants.length === 1 ? '' : 's';
  const previewText = previewPaths.length > 0
    ? `\n\nExamples:\n${previewPaths.join('\n')}${remainingCount > 0 ? `\n...and ${remainingCount} more.` : ''}`
    : '';
  const ok = window.confirm(
    `Delete ${descendants.length} subpage${suffix} under "${directoryPath}"? This action cannot be undone.${previewText}`
  );
  if (!ok) return;

  deletingSubpages.value = true;
  try {
    for (const page of descendants) {
      await api.deletePage(page.slug);
    }
    const removedSlugSet = new Set(descendants.map((page) => page.slug));
    pages.value = pages.value.filter((page) => !removedSlugSet.has(page.slug));
    await Promise.all([loadRedirects(), refreshSitemapSummary()]);
  } catch (err) {
    console.error('Failed to delete subpages:', err);
    alert('Failed to delete subpages: ' + (err?.message || 'Unknown error'));
  } finally {
    deletingSubpages.value = false;
  }
}

function confirmDelete(page) {
  deleteConfirm.value = page;
  selectedPage.value = null;
}

async function doDeletePage() {
  if (!deleteConfirm.value) return;
  
  try {
    deleting.value = true;
    await api.deletePage(deleteConfirm.value.slug);
    pages.value = pages.value.filter(p => p.id !== deleteConfirm.value.id);
    deleteConfirm.value = null;
  } catch (err) {
    console.error('Failed to delete page:', err);
    alert('Failed to delete: ' + err.message);
  } finally {
    deleting.value = false;
  }
}

watch(selectedPage, (newVal, oldVal) => {
  const nextId = String(newVal?.id || '');
  const previousId = String(oldVal?.id || '');
  if (nextId === previousId) return;

  resetBulkChildVisibilitySelection();
  clearPageAutosaveStatusTimer();
  pageAutosaveStatus.value = 'idle';
  pageAutosaveError.value = '';
  if (newVal) return;

  pageAutosavePending.value = false;
  lastSavedEditSnapshot.value = '';
});

watch(subtreeReorderEnabled, () => {
  subtreeMoveError.value = '';
  clearSubtreeDragState();
});

watch(
  generatedChildCountsByParent,
  (counts) => {
    const validParentSlugs = new Set(Object.keys(counts || {}));
    for (const slug of Object.keys(generatedChildrenExpandedByParent)) {
      if (!validParentSlugs.has(slug)) {
        delete generatedChildrenExpandedByParent[slug];
      }
    }
  },
  { immediate: true },
);

function consumeCreateDialogQuery() {
  if (route.query.create !== '1') return;

  const querySlug = typeof route.query.slug === 'string' ? route.query.slug.trim() : '';
  openCreateDialog({
    slug: querySlug,
    focusTitleDe: Boolean(querySlug),
  });

  const nextQuery = { ...route.query };
  delete nextQuery.tab;
  delete nextQuery.create;
  delete nextQuery.slug;
  router.replace({ path: '/admin/sitemap/pages', query: nextQuery });
}

function consumeEditPageQuery() {
  const queryEdit = typeof route.query.edit === 'string' ? route.query.edit.trim() : '';
  if (!queryEdit) return;
  if (loading.value) return;

  const target = pages.value.find((p) => p.slug === queryEdit);
  if (target) {
    selectPage(target);
  }

  const nextQuery = { ...route.query };
  delete nextQuery.tab;
  delete nextQuery.edit;
  router.replace({ path: '/admin/sitemap/pages', query: nextQuery });
}

watch(
  () => [route.query.create, route.query.slug, route.query.edit, loading.value, pages.value.length],
  () => {
    consumeCreateDialogQuery();
    consumeEditPageQuery();
  },
);

watch(
  () => redirectForm.status_code,
  (nextCode) => {
    if (Number(nextCode) === 410) {
      redirectForm.target_path = '';
    }
  },
);

watch(
  () => redirectEditForm.status_code,
  (nextCode) => {
    if (Number(nextCode) === 410) {
      redirectEditForm.target_path = '';
    }
  },
);

watch(
  () => filteredRedirects.value
    .map((item) => redirectSelectionKey(item))
    .filter(Boolean),
  (filteredIds) => {
    const allowed = new Set(filteredIds);
    selectedRedirectIds.value = selectedRedirectIds.value.filter((id) => allowed.has(id));
  },
);

watch(cachingCurrentSnapshot, (nextSnapshot, previousSnapshot) => {
  if (!previousSnapshot || nextSnapshot === previousSnapshot) return;
  if (cachingStatus.value === 'Caching rules saved.' || cachingStatus.value === 'Copied .htaccess rules.') {
    cachingStatus.value = '';
  }
});

watch(activeTab, (tab) => {
  if (tab === 'redirects') {
    if (!sitemapSummary.value) {
      void refreshSitemapSummary();
    }
    if (redirects.value.length === 0) {
      void loadRedirects();
    }
    return;
  }
  if (tab === 'stats') {
    nextTick(() => {
      setupStatsTimelineResizeObserver();
    });
    if (!sitemapStatsPayload.value && !sitemapStatsLoading.value) {
      void loadSitemapStats();
    }
    return;
  }
  if (tab === 'robots' && !robotsPayload.value && !robotsLoading.value) {
    void loadRobots();
    return;
  }
  if (tab === 'caching' && !cachingPayload.value && !cachingLoading.value) {
    void loadCachingRules();
  }
});

watch(
  () => [activeTab.value, sitemapStatsDailySeries.value.length, sitemapStatsDailyTotal.value],
  () => {
    if (activeTab.value !== 'stats') return;
    nextTick(() => {
      setupStatsTimelineResizeObserver();
    });
  },
  { flush: 'post' },
);

onMounted(async () => {
  document.addEventListener('pointerdown', handleBulkChildVisibilityDocumentPointerDown);
  const initialTasks = [loadPages(), loadNavigationLinks(), refreshSitemapSummary(), loadRedirects(), loadRobots()];
  if (activeTab.value === 'stats') {
    initialTasks.push(loadSitemapStats());
  }
  if (activeTab.value === 'caching') {
    initialTasks.push(loadCachingRules());
  }
  await Promise.all(initialTasks);
  void loadApiRoutes();
  consumeCreateDialogQuery();
  consumeEditPageQuery();
  if (activeTab.value === 'stats') {
    await nextTick();
    setupStatsTimelineResizeObserver();
  }
});

onUnmounted(() => {
  document.removeEventListener('pointerdown', handleBulkChildVisibilityDocumentPointerDown);
  teardownStatsTimelineResizeObserver();
  if (bulkChildVisibilityInteractionTimer) {
    clearTimeout(bulkChildVisibilityInteractionTimer);
    bulkChildVisibilityInteractionTimer = null;
  }
  clearPageAutosaveStatusTimer();
});
</script>

<style scoped>
.admin-sitemap {
  max-width: 1400px;
}

.sitemap-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 20px;
  align-items: start;
}

.page-editor-empty {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px;
  color: #64748b;
}

.page-editor-empty h2 {
  margin: 0 0 8px 0;
  font-size: 18px;
  color: #0f172a;
}

.page-editor-empty p {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 800;
  color: var(--admin-text, #0f172a);
  margin: 0;
}

.page-subtitle {
  font-size: 14px;
  color: #64748b;
}

.loading-state {
  padding: 40px;
  text-align: center;
  color: #64748b;
}

.loading-state--compact {
  padding: 16px 0;
  text-align: left;
}

/* Tree Structure */
.sitemap-tree {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.tree-section {
  border-bottom: 1px solid #e2e8f0;
}
.tree-section:last-child {
  border-bottom: none;
}

.tree-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  cursor: pointer;
  transition: background 0.15s;
  user-select: none;
}
.tree-header:hover {
  background: #f8fafc;
}

.tree-chevron {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 12px;
  font-size: 10px;
  color: #94a3b8;
  transition: transform 0.2s;
}
.tree-chevron.expanded {
  transform: rotate(90deg);
}

.tree-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  font-size: 14px;
}

.tree-label {
  font-weight: 600;
  font-size: 14px;
  color: #0f172a;
}

.tree-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.tree-badge.system {
  background: #f1f5f9;
  color: #64748b;
}

.tree-count {
  font-size: 12px;
  color: #64748b;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 10px;
}

.add-page-btn {
  margin-left: auto;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 6px;
  background: #4f46e5;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.add-page-btn:hover {
  background: #4338ca;
  transform: scale(1.1);
}

.tree-children {
  padding: 0 18px;
}

.tree-group-children {
  padding-left: 10px;
  padding-right: 10px;
  background: #f8fafc;
}

.tree-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  margin: 2px 0;
  border-radius: 6px;
  font-size: 13px;
  transition: background 0.15s;
}
.tree-item:hover {
  background: #f1f5f9;
}

.tree-path {
  font-family: ui-monospace, monospace;
  color: #64748b;
  font-size: 12px;
}

/* API Routes */
.api-routes {
  padding: 0 12px 14px 12px;
}

.api-group {
  margin-bottom: 2px;
}

.api-parent {
  cursor: pointer;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}
.api-parent:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.tree-chevron.small {
  font-size: 8px;
  width: 12px;
}

.api-subroutes {
  margin-left: 24px;
  border-left: 2px solid #e2e8f0;
  padding-left: 8px;
}

.api-subroute {
  padding: 5px 10px;
  font-size: 12px;
  gap: 8px;
}
.api-subroute:hover {
  background: #f8fafc;
}

.api-loading {
  padding: 12px 16px;
  font-size: 13px;
  color: #64748b;
  font-style: italic;
}

.http-method {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  min-width: 50px;
  text-align: center;
  font-family: ui-monospace, monospace;
}
.http-method.get {
  background: #dbeafe;
  color: #1d4ed8;
}
.http-method.post {
  background: #dcfce7;
  color: #166534;
}
.http-method.patch {
  background: #fef3c7;
  color: #92400e;
}
.http-method.put {
  background: #e0e7ff;
  color: #4338ca;
}
.http-method.delete {
  background: #fee2e2;
  color: #dc2626;
}

.api-access-summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.access-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.access-tag.public {
  background: #dcfce7;
  color: #166534;
}

.access-tag.private {
  background: #fee2e2;
  color: #991b1b;
}

.tree-indent {
  color: #cbd5e1;
  font-family: ui-monospace, monospace;
  margin-right: 4px;
}

.tree-name {
  color: #0f172a;
  flex: 1;
}

/* Page Items */
.page-item {
  cursor: pointer;
  border: 1px solid transparent;
  position: relative;
}
.page-item:hover {
  border-color: #e2e8f0;
}
.page-item.is-hidden {
  opacity: 0.7;
}
.page-item.is-hidden:hover {
  opacity: 1;
}
.page-item.is-under-construction {
  border-color: #f59e0b;
}

/* Drag and Drop */
.menu-draggable {
  min-height: 20px;
}
.subtree-migration-toggle {
  display: flex;
  gap: 12px;
  padding: 8px 10px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #eee;
}
.toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #0f172a;
  font-weight: 600;
}
.toggle-label input[type="checkbox"] {
  margin: 0;
}
.toggle-hint {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}
.subtree-drop-root {
  margin-top: 8px;
  padding: 7px 10px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  font-size: 12px;
  color: #475569;
  background: #ffffff;
}
.subtree-drop-root--section {
  margin: 0 0 8px;
}
.subtree-drop-root.active {
  border-color: #0284c7;
  background: #e0f2fe;
  color: #0c4a6e;
}
.subtree-drop-root.invalid {
  border-color: #fca5a5;
  background: #fef2f2;
  color: #991b1b;
}
.subtree-move-error {
  margin: 0;
  font-size: 12px;
  color: #b91c1c;
}
.menu-tree-item {
  margin-bottom: 2px;
}
.menu-children {
  margin-left: 0;
  border-left: 1px solid #e2e8f0;
  margin-left: 16px;
}
.subpage-item {
  border-left: none;
}
.drag-handle {
  cursor: grab;
  color: #94a3b8;
  font-size: 12px;
  letter-spacing: -2px;
  padding: 0 4px;
  margin-right: 4px;
  user-select: none;
  opacity: 0.5;
  transition: opacity 0.15s, color 0.15s;
}
.drag-handle:hover {
  opacity: 1;
  color: #475569;
}
.drag-handle:active {
  cursor: grabbing;
}
.drag-handle.disabled {
  cursor: not-allowed;
  opacity: 0.25;
}
.drag-handle.disabled:hover {
  color: #94a3b8;
  opacity: 0.25;
}
.menu-item-draggable {
  display: flex;
  align-items: center;
}
.menu-item-draggable .tree-path,
.menu-item-draggable .tree-name {
  cursor: pointer;
}

.menu-link-group:last-child {
  padding-top: 12px;
  padding-bottom: 24px;
}

.site-logo-section {
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 12px;
}

.site-logo-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.site-logo-preview {
  display: flex;
  align-items: center;
  gap: 10px;
}

.site-logo-preview-image {
  max-height: 40px;
  max-width: 180px;
  width: auto;
  object-fit: contain;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #fff;
  padding: 4px;
}

.site-logo-preview-url {
  max-width: 260px;
}

.site-logo-hint {
  margin: 0;
}

.external-links-title,
.internal-links-title, 
.link-group-title {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
  margin-bottom: 6px;
}

.external-link-item .tree-path {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.external-link-item {
  cursor: pointer;
}

.navigation-links-error {
  margin: 8px 0 0;
  padding: 0 8px 8px;
}
.subtree-drag-source {
  opacity: 0.75;
  outline: 1px dashed #93c5fd;
}
.subtree-drop-target {
  background: #e0f2fe !important;
  border-color: #0284c7 !important;
}
.subtree-drop-invalid {
  background: #fef2f2 !important;
  border-color: #ef4444 !important;
}
.drag-ghost {
  opacity: 0.5;
  background: #e0f2fe;
  border: 1px dashed #0ea5e9 !important;
}

.add-subpage-btn {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 5px;
  background: #10b981;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease, transform 0.15s ease, background 0.15s ease;
}
.page-item:hover .add-subpage-btn {
  opacity: 1;
  pointer-events: auto;
}
.add-subpage-btn:hover {
  background: #059669;
  transform: translateY(-50%) scale(1.1);
}

.generated-toggle-btn {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  cursor: pointer;
  line-height: 1.2;
  white-space: nowrap;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
.generated-toggle-btn:hover {
  background: #dbeafe;
  border-color: #93c5fd;
}

.page-badges {
  display: flex;
  gap: 6px;
  margin-right: 28px;
  flex-wrap: wrap;
  align-items: center;
}

.badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}
.badge.draft {
  background: #fef3c7;
  color: #92400e;
}
.badge.hidden {
  background: #fef3c7;
  color: #92400e;
}
.badge.under-construction {
  background: #ffedd5;
  color: #9a3412;
}
.badge.published {
  background: #dcfce7;
  color: #166534;
}
.badge.menu {
  background: #e0e7ff;
  color: #3730a3;
}
.badge.footer {
  background: #dcfce7;
  color: #166534;
}
.badge.subpage {
  background: #f3e8ff;
  color: #7c3aed;
}
.badge.redirect {
  background: #fef3c7;
  color: #b45309;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.badge.scheduled {
  background: #f3e8ff;
  color: #7c3aed;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.badge.crawler {
  background: #fee2e2;
  color: #991b1b;
}
.badge.generated {
  background: #dbeafe;
  color: #1d4ed8;
}
.badge.hits {
  background: #ecfeff;
  color: #155e75;
}
.badge.status {
  background: #f1f5f9;
  color: #334155;
}

.empty-pages {
  text-align: center;
  padding: 12px;
  color: #94a3b8;
  font-size: 14px;
}

/* Redirects Tab */
.redirects-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.robots-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.stats-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.caching-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.redirects-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 18px;
}

.redirects-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.redirects-card__header h2 {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}

.redirects-header-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.redirects-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.redirects-actions .btn-primary {
  margin-left: 0;
}

.redirect-form-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-bottom: 12px;
}

.redirect-controls {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 12px;
}

.redirect-controls__field {
  margin: 0;
}

.redirect-bulk-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.redirect-bulk-actions__delete {
  margin-left: auto;
}

.sitemap-meta-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 12px;
}

.meta-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-label {
  font-size: 12px;
  color: #64748b;
}

.meta-value {
  font-size: 20px;
  color: #0f172a;
}

.stats-summary-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 12px;
}

.stats-scope-item {
  min-width: 0;
}

.stats-scope-value {
  font-size: 14px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.stats-range-actions {
  justify-content: flex-end;
  min-width: 0;
}

.stats-range-actions .field-hint {
  overflow-wrap: anywhere;
}

.stats-range-select {
  width: auto;
  min-width: 130px;
}

.stats-chart-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  border-top: 1px solid #e2e8f0;
  background: #fff;
}

.stats-tree-svg,
.stats-timeline-svg {
  display: block;
  width: 100%;
  min-width: 720px;
  height: auto;
}

.stats-tree-link {
  fill: none;
  stroke: #cbd5e1;
  stroke-width: 1.5;
}

.stats-tree-node {
  cursor: pointer;
  outline: none;
}

.stats-tree-node circle {
  stroke: #fff;
  stroke-width: 2;
  transition: stroke 0.15s ease, stroke-width 0.15s ease, filter 0.15s ease;
}

.stats-tree-node:hover circle,
.stats-tree-node:focus-visible circle,
.stats-tree-node.selected circle {
  stroke: #1d4ed8;
  stroke-width: 3;
  filter: drop-shadow(0 2px 5px rgba(37, 99, 235, 0.2));
}

.stats-tree-node--generated-group:hover circle,
.stats-tree-node--generated-group:focus-visible circle,
.stats-tree-node--generated-group.selected circle {
  stroke: #0f766e;
  filter: drop-shadow(0 2px 5px rgba(15, 118, 110, 0.2));
}

.stats-tree-node__label,
.stats-tree-node__value {
  pointer-events: none;
  dominant-baseline: middle;
}

.stats-tree-node__label {
  fill: #0f172a;
  font-size: 12px;
  font-weight: 700;
}

.stats-tree-node--generated-group .stats-tree-node__label {
  fill: #0f766e;
}

.stats-tree-node__value {
  fill: #64748b;
  font-size: 11px;
  font-weight: 600;
}

.stats-timeline-axis {
  stroke: #cbd5e1;
  stroke-width: 1.5;
}

.stats-timeline-grid {
  stroke: #e2e8f0;
  stroke-width: 1;
}

.stats-timeline-bar {
  fill: #2563eb;
}

.stats-timeline-label,
.stats-timeline-y-label {
  fill: #64748b;
  font-weight: 600;
}

.redirect-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  border-top: 1px solid #e2e8f0;
}

.generated-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 0;
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #334155;
}

.redirect-item {
  border: 0;
  border-bottom: 1px solid #e2e8f0;
  border-radius: 0;
  background: #fff;
  transition: background-color 0.15s ease, box-shadow 0.15s ease;
}

.redirect-item[role="button"] {
  cursor: pointer;
}

.redirect-item:hover .redirect-row {
  background: #f8fafc;
}

.redirect-item:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: -2px;
}

.redirect-item--selected {
  background: #eff6ff;
  box-shadow: inset 4px 0 0 #2563eb;
}

.redirect-item--selected .redirect-row {
  background: #dbeafe;
}

.redirect-item--selected:hover .redirect-row {
  background: #dbeafe;
}

.redirect-item--editing .redirect-row {
  background: #f8fafc;
}

.redirect-item--selected.redirect-item--editing .redirect-row {
  background: #dbeafe;
}

.redirect-item--inactive {
  background:
    repeating-linear-gradient(
      -45deg,
      rgba(148, 163, 184, 0.08),
      rgba(148, 163, 184, 0.08) 8px,
      rgba(148, 163, 184, 0.02) 8px,
      rgba(148, 163, 184, 0.02) 16px
    ),
    #f8fafc;
}

.redirect-item--inactive.redirect-item--selected {
  background:
    linear-gradient(0deg, rgba(239, 246, 255, 0.78), rgba(239, 246, 255, 0.78)),
    repeating-linear-gradient(
      -45deg,
      rgba(148, 163, 184, 0.08),
      rgba(148, 163, 184, 0.08) 8px,
      rgba(148, 163, 184, 0.02) 8px,
      rgba(148, 163, 184, 0.02) 16px
    ),
    #f8fafc;
}

.redirect-item--inactive .redirect-main {
  opacity: 0.58;
  filter: grayscale(0.7);
}

.redirect-item--inactive .redirect-paths .tree-path {
  text-decoration: line-through;
  text-decoration-color: #94a3b8;
  text-decoration-thickness: 1px;
}

.redirect-item--inactive .tree-path {
  color: #475569;
}

.redirect-item--inactive .redirect-expiry,
.redirect-item--inactive .redirect-kv__label,
.redirect-item--inactive .redirect-kv__value {
  color: #64748b;
}

.redirect-item--inactive .badge {
  opacity: 0.62;
}

.redirect-item--inactive .redirect-actions {
  opacity: 0.82;
}

.redirect-row {
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.redirect-main {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.redirect-paths {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.redirect-arrow {
  color: #94a3b8;
}

.redirect-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.badge.protocol {
  background: #eef2ff;
  color: #3730a3;
}

.badge.protocol.protocol-internal {
  background: #ecfeff;
  color: #155e75;
}

.badge.protocol.protocol-http {
  background: #fff7ed;
  color: #9a3412;
}

.badge.protocol.protocol-https {
  background: #ecfdf5;
  color: #166534;
}

.badge.protocol.protocol-gone {
  background: #fef2f2;
  color: #991b1b;
}

.redirect-expiry {
  color: #64748b;
  font-size: 12px;
}

.redirect-custom-meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.redirect-kv {
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  padding: 1px 7px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  border-radius: 999px;
}

.redirect-kv__label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: #64748b;
}

.redirect-kv__value {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.redirect-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.redirect-edit-panel {
  border-top: 1px solid #e2e8f0;
  padding: 12px;
  background: #f8fafc;
}

.redirect-form-grid--edit {
  margin-bottom: 10px;
}

.redirect-enabled-field {
  grid-column: 1 / -1;
  margin-bottom: 0;
}

.robots-textarea {
  width: 100%;
  min-height: 180px;
  padding: 12px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.5;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  resize: vertical;
}

.robots-textarea:focus {
  outline: none;
  border-color: #4f46e5;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15);
}

.robots-textarea--readonly {
  background: #f8fafc;
}

.htaccess-textarea {
  min-height: 320px;
}

.caching-table-wrap {
  width: 100%;
  overflow-x: auto;
  margin-bottom: 14px;
}

.caching-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
  font-size: 13px;
}

.caching-table th,
.caching-table td {
  padding: 10px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: top;
}

.caching-table th {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: #64748b;
  background: #f8fafc;
}

.caching-table tr.is-disabled td {
  color: #94a3b8;
  background: #f8fafc;
}

.caching-table td:first-child,
.caching-table th:first-child {
  width: 74px;
  text-align: center;
}

.caching-toggle {
  display: inline-flex;
  justify-content: center;
  width: 100%;
}

.caching-duration {
  display: grid;
  grid-template-columns: minmax(70px, 92px) minmax(110px, 1fr);
  gap: 8px;
  align-items: center;
}

.caching-duration__amount,
.caching-duration__unit {
  min-width: 0;
}

.caching-code-list,
.caching-cache-control {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  line-height: 1.5;
  color: #334155;
  word-break: break-word;
}

.caching-cache-control {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.caching-actions {
  margin-top: 4px;
}

/* Editor Overlay */
.page-editor-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.page-editor {
  background: #fff;
  border-radius: 16px;
  width: 100%;
  max-width: 520px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.page-editor--inline {
  max-width: none;
  max-height: calc(100vh - 90px);
  border: 1px solid #e2e8f0;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
}

.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 18px;
  border-bottom: 1px solid #e2e8f0;
}

.editor-header h2 {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
}

.close-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s;
}
.close-btn:hover {
  background: #e2e8f0;
  color: #0f172a;
}

.editor-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-page-state {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.header-page-state.published {
  background: #dcfce7;
  color: #166534;
}

.header-page-state.hidden {
  background: #fef3c7;
  color: #92400e;
}

.header-page-state.under-construction {
  background: #ffedd5;
  color: #9a3412;
}

.edit-sections {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.edit-section {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}

.edit-section--danger {
  border-color: #fecaca;
}

.edit-section-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: none;
  background: #f8fafc;
  color: #0f172a;
  cursor: pointer;
  text-align: left;
}

.edit-section.expanded .edit-section-header {
  background: #f1f5f9;
}

.edit-section-title {
  font-size: 13px;
  font-weight: 700;
}

.edit-section-summary {
  margin-left: auto;
  font-size: 12px;
  color: #64748b;
}

.edit-section-chevron {
  color: #94a3b8;
  transition: transform 0.15s ease;
}

.edit-section-chevron.expanded {
  transform: rotate(90deg);
}

.edit-section-body {
  padding: 14px;
  border-top: 1px solid #e2e8f0;
  animation: fadeIn 0.15s ease-out;
}

.status-info-box {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.status-info-box p {
  margin: 0;
  font-size: 12px;
  color: #475569;
}

.delete-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.btn-danger-secondary {
  background: #fee2e2;
  color: #991b1b;
}

.btn-danger-secondary:hover {
  background: #fecaca;
}

.delete-help {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: #7f1d1d;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.status-toggle {
  display: flex;
  gap: 8px;
}

.toggle-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 16px;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  color: #64748b;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.toggle-btn:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.toggle-btn.active {
  border-color: #4f46e5;
  background: #eef2ff;
  color: #4f46e5;
}

.toggle-btn svg {
  opacity: 0.7;
}

.toggle-btn.active svg {
  opacity: 1;
}

.editor-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.field-group {
  margin-bottom: 20px;
}
.field-group:last-child {
  margin-bottom: 0;
}

.field-group > label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 6px;
}

.menu-suboption {
  margin-top: 10px;
  margin-left: 28px;
  padding-left: 10px;
  border-left: 2px solid #e2e8f0;
}

.crawler-suboption {
  margin-top: 10px;
  margin-left: 28px;
  padding-left: 10px;
  border-left: 2px solid #e2e8f0;
}

.text-input,
.datetime-input,
.select-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  color: #0f172a;
  transition: all 0.15s;
  background: #fff;
}
.text-input:focus,
.datetime-input:focus,
.select-input:focus {
  outline: none;
  border-color: #4f46e5;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.select-input {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 36px;
}

.bulk-visibility-dropdown {
  position: relative;
}

.bulk-visibility-dropdown__button {
  text-align: left;
  justify-content: flex-start;
}

.bulk-visibility-dropdown__button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.bulk-visibility-dropdown__menu {
  position: absolute;
  z-index: 20;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  padding: 4px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.16);
}

.bulk-visibility-dropdown__option {
  width: 100%;
  display: flex;
  align-items: center;
  padding: 9px 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #0f172a;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
}

.bulk-visibility-dropdown__option:hover,
.bulk-visibility-dropdown__option:focus-visible {
  outline: none;
  background: #eef2ff;
  color: #4f46e5;
}

.schedule-row {
  display: flex;
  gap: 12px;
}

.schedule-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  position: relative;
}

.schedule-label {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.schedule-picker {
  width: 100%;
}

.schedule-picker :deep(.dp__input) {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
  height: auto;
}

.schedule-picker :deep(.dp__input:focus) {
  border-color: #4f46e5;
  box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.1);
}

.schedule-picker :deep(.dp__input_icon) {
  color: #64748b;
}

.schedule-picker :deep(.dp__clear_icon) {
  color: #64748b;
}

.field-hint {
  font-size: 12px;
  color: #94a3b8;
  margin: 6px 0 0 0;
}

.inline-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.field-error {
  font-size: 12px;
  color: #dc2626;
  margin: 6px 0 0 0;
}

.field-success {
  font-size: 12px;
  color: #15803d;
  margin: 6px 0 0 0;
}

.field-warning {
  font-size: 12px;
  color: #92400e;
  margin: 6px 0 0 0;
}

.slug-display {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.title-inputs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.lang-input {
  display: flex;
  align-items: center;
  gap: 8px;
}

.lang-label {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  background: #f1f5f9;
  padding: 4px 8px;
  border-radius: 4px;
  min-width: 28px;
  text-align: center;
}

.lang-input .text-input {
  flex: 1;
}

.title-value {
  color: #0f172a;
}

.slug-prefix {
  color: #94a3b8;
  font-family: ui-monospace, monospace;
}

.slug-value {
  color: #0f172a;
  font-family: ui-monospace, monospace;
}

.slug-input-wrap {
  display: flex;
  align-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}
.slug-input-wrap .slug-prefix {
  padding: 10px 0 10px 12px;
  background: #f8fafc;
}
.slug-input-wrap .slug-input {
  border: none;
  border-radius: 0;
  padding-left: 4px;
}
.slug-input-wrap:focus-within {
  border-color: #4f46e5;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-size: 14px;
  color: #374151;
}
.checkbox-label input {
  accent-color: #4f46e5;
}

.clear-btn {
  margin-top: 6px;
  padding: 4px 10px;
  border: none;
  border-radius: 4px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.clear-btn:hover {
  background: #e2e8f0;
  color: #374151;
}

.editor-actions {
  display: flex;
  gap: 12px;
  padding: 10px 18px;
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
}

/* Delete Confirmation */
.confirm-text {
  font-size: 15px;
  color: #374151;
  margin: 0 0 16px 0;
}

.delete-page-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 16px;
}

.confirm-warning {
  font-size: 13px;
  color: #dc2626;
  margin: 0;
}

@media (max-width: 1180px) {
  .sitemap-layout {
    grid-template-columns: 1fr;
  }

  .sitemap-side {
    position: static;
  }

  .page-editor--inline {
    max-height: none;
  }

  .redirect-form-grid {
    grid-template-columns: 1fr;
  }

  .redirect-controls {
    grid-template-columns: 1fr;
  }

  .sitemap-meta-grid {
    grid-template-columns: 1fr;
  }

  .stats-summary-grid {
    grid-template-columns: 1fr;
  }

  .redirect-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
