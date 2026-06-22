"""Canonical MongoDB collection names used by the application."""

PAGES_COLLECTION = "pages"
SECTIONS_COLLECTION = "sections"
HEADERS_COLLECTION = "headers"
ASSETS_COLLECTION = "assets"
PAGE_REDIRECTS_COLLECTION = "page_redirects"
PAGE_HIT_DAYS_COLLECTION = "page_hit_days"
BLOG_SHARED_COLLECTION = "blog_shared"
BLOG_CONFIG_COLLECTION = "blog_config"
FAQ_SHARED_COLLECTION = "faq_shared"
PROGRAM_SHARED_COLLECTION = "program_shared"
PROGRAM_GIGS_COLLECTION = "program_gigs"

DESIGN_CONFIG_COLLECTION = "design_config"
DESIGN_EDITOR_CONFIG_COLLECTION = "design_editor_config"
DESIGN_VERSIONS_COLLECTION = "design_versions"
CSS_SNIPPETS_COLLECTION = "css_snippets"

TEMPLATE_SECTIONS_COLLECTION = "template_sections"
TEMPLATE_CONTAINERS_COLLECTION = "template_containers"
TEMPLATE_PAGES_COLLECTION = "template_pages"
SITEMAP_CONFIG_COLLECTION = "sitemap_config"
ITEM_PAGE_CONFIG_COLLECTION = "item_page_config"
ITEM_PAGE_ROUTES_COLLECTION = "item_page_routes"

INTEGRATION_CONFIG_COLLECTION = "integration_config"
INTEGRATION_DATA_COLLECTION = "integration_data"
INTEGRATION_EXPOSURE_CONFIG_COLLECTION = "integration_exposure_config"
INTEGRATION_ITEM_OVERRIDES_COLLECTION = "integration_item_overrides"
INTEGRATION_ITEM_REVIEWS_COLLECTION = "integration_item_reviews"
INTEGRATION_LOCAL_ITEMS_COLLECTION = "integration_local_items"
INTEGRATION_SCHEMAS_COLLECTION = "integration_schemas"
INTEGRATION_MEDIA_REGISTRY_COLLECTION = "integration_media_registry"
INTEGRATION_SECTION_CACHE_VERSIONS_COLLECTION = "integration_section_cache_versions"
INTEGRATION_JOBS_COLLECTION = "integration_jobs"
ITEM_PAGE_GENERATION_JOBS_COLLECTION = "item_page_generation_jobs"

ACCESS_CONTROL_CONFIG_COLLECTION = "access_control_config"
MEDIA_CONFIG_COLLECTION = "media_config"
DEVOPS_CONFIG_COLLECTION = "devops_config"
TEMPORARY_USERS_COLLECTION = "temporary_users"

REVISIONS_COLLECTION = "revisions"
REVISION_CONFIG_COLLECTION = "revision_config"
CHANGELOG_COLLECTION = "changelog"
BACKUP_LOG_COLLECTION = "backup_log"
BACKUP_STATE_COLLECTION = "backup_state"
FONT_CACHE_VARIANTS_COLLECTION = "font_cache_variants"
FONT_CACHE_FILES_COLLECTION = "font_cache_files"

LEGACY_ROUTE_REDIRECTS_COLLECTION = "route_redirects"
LEGACY_BLOG_ITEMS_COLLECTION = "blog_items"
LEGACY_INTEGRATIONS_COLLECTION = "integrations"
LEGACY_DESIGN_SETTINGS_COLLECTION = "design_settings"
LEGACY_TEMP_CREDENTIALS_COLLECTION = "temp_credentials"
LEGACY_ADMIN_DESIGN_CONFIG_COLLECTION = "admin_design_config"
LEGACY_ADMIN_MEDIA_CONFIG_COLLECTION = "admin_media_config"
LEGACY_ADMIN_SITEMAP_CONFIG_COLLECTION = "admin_sitemap_config"
LEGACY_ADMIN_ACCESS_CONTROL_CONFIG_COLLECTION = "admin_access_control_config"
LEGACY_ADMIN_DEVOPS_CONFIG_COLLECTION = "admin_devops_config"
LEGACY_INTEGRATION_CONNECTION_CONFIG_COLLECTION = "integration_connection_config"
LEGACY_TEMPORAL_USER_COLLECTION = "temporal_user"
LEGACY_GLOBAL_ITEM_PAGE_CONFIG_COLLECTION = "global_item_page_config"
LEGACY_SHARED_ITEM_PAGE_ROUTES_COLLECTION = "shared_item_page_routes"
LEGACY_SECTION_INTEGRATION_CACHE_VERSIONS_COLLECTION = "section_integration_cache_versions"
LEGACY_BACKUP_COUNTERS_COLLECTION = "backup_counters"


# Collections the application owns, initializes, and exposes for direct admin
# database operations. Legacy/obsolete collection aliases intentionally do not
# belong here.
MANAGED_COLLECTIONS: tuple[str, ...] = (
    PAGES_COLLECTION,
    SECTIONS_COLLECTION,
    REVISIONS_COLLECTION,
    REVISION_CONFIG_COLLECTION,
    CHANGELOG_COLLECTION,
    HEADERS_COLLECTION,
    ASSETS_COLLECTION,
    PAGE_REDIRECTS_COLLECTION,
    PAGE_HIT_DAYS_COLLECTION,
    TEMPLATE_SECTIONS_COLLECTION,
    TEMPLATE_CONTAINERS_COLLECTION,
    TEMPLATE_PAGES_COLLECTION,
    CSS_SNIPPETS_COLLECTION,
    BLOG_SHARED_COLLECTION,
    BLOG_CONFIG_COLLECTION,
    FAQ_SHARED_COLLECTION,
    PROGRAM_SHARED_COLLECTION,
    PROGRAM_GIGS_COLLECTION,
    INTEGRATION_CONFIG_COLLECTION,
    INTEGRATION_DATA_COLLECTION,
    INTEGRATION_ITEM_OVERRIDES_COLLECTION,
    INTEGRATION_ITEM_REVIEWS_COLLECTION,
    INTEGRATION_LOCAL_ITEMS_COLLECTION,
    INTEGRATION_SCHEMAS_COLLECTION,
    INTEGRATION_SECTION_CACHE_VERSIONS_COLLECTION,
    INTEGRATION_MEDIA_REGISTRY_COLLECTION,
    INTEGRATION_JOBS_COLLECTION,
    ITEM_PAGE_GENERATION_JOBS_COLLECTION,
    DESIGN_CONFIG_COLLECTION,
    DESIGN_EDITOR_CONFIG_COLLECTION,
    DESIGN_VERSIONS_COLLECTION,
    DEVOPS_CONFIG_COLLECTION,
    MEDIA_CONFIG_COLLECTION,
    SITEMAP_CONFIG_COLLECTION,
    ACCESS_CONTROL_CONFIG_COLLECTION,
    INTEGRATION_EXPOSURE_CONFIG_COLLECTION,
    ITEM_PAGE_CONFIG_COLLECTION,
    ITEM_PAGE_ROUTES_COLLECTION,
    TEMPORARY_USERS_COLLECTION,
    BACKUP_LOG_COLLECTION,
    BACKUP_STATE_COLLECTION,
    FONT_CACHE_VARIANTS_COLLECTION,
    FONT_CACHE_FILES_COLLECTION,
)

COLLECTION_GROUP_META: dict[str, dict[str, str | int]] = {
    "main_content": {"label": "Main Content", "order": 10},
    "styling": {"label": "Styling", "order": 20},
    "templates_routing": {"label": "Templates & Routing", "order": 30},
    "integrations": {"label": "Integrations", "order": 40},
    "admin_security": {"label": "Admin & Security", "order": 50},
    "internal_cache": {"label": "Internal Cache", "order": 60},
    "logs_jobs": {"label": "Logs & Jobs", "order": 70},
}

COLLECTION_GROUP_BY_NAME: dict[str, str] = {
    PAGES_COLLECTION: "main_content",
    SECTIONS_COLLECTION: "main_content",
    HEADERS_COLLECTION: "main_content",
    ASSETS_COLLECTION: "main_content",
    BLOG_SHARED_COLLECTION: "main_content",
    BLOG_CONFIG_COLLECTION: "main_content",
    FAQ_SHARED_COLLECTION: "main_content",
    PROGRAM_SHARED_COLLECTION: "main_content",
    PROGRAM_GIGS_COLLECTION: "main_content",
    DESIGN_CONFIG_COLLECTION: "styling",
    DESIGN_EDITOR_CONFIG_COLLECTION: "styling",
    DESIGN_VERSIONS_COLLECTION: "styling",
    CSS_SNIPPETS_COLLECTION: "styling",
    TEMPLATE_SECTIONS_COLLECTION: "templates_routing",
    TEMPLATE_CONTAINERS_COLLECTION: "templates_routing",
    TEMPLATE_PAGES_COLLECTION: "templates_routing",
    PAGE_REDIRECTS_COLLECTION: "templates_routing",
    SITEMAP_CONFIG_COLLECTION: "templates_routing",
    ITEM_PAGE_CONFIG_COLLECTION: "templates_routing",
    ITEM_PAGE_ROUTES_COLLECTION: "templates_routing",
    INTEGRATION_CONFIG_COLLECTION: "integrations",
    INTEGRATION_DATA_COLLECTION: "integrations",
    INTEGRATION_EXPOSURE_CONFIG_COLLECTION: "integrations",
    INTEGRATION_ITEM_OVERRIDES_COLLECTION: "integrations",
    INTEGRATION_ITEM_REVIEWS_COLLECTION: "integrations",
    INTEGRATION_LOCAL_ITEMS_COLLECTION: "integrations",
    INTEGRATION_SCHEMAS_COLLECTION: "integrations",
    INTEGRATION_MEDIA_REGISTRY_COLLECTION: "integrations",
    INTEGRATION_SECTION_CACHE_VERSIONS_COLLECTION: "integrations",
    ACCESS_CONTROL_CONFIG_COLLECTION: "admin_security",
    MEDIA_CONFIG_COLLECTION: "admin_security",
    DEVOPS_CONFIG_COLLECTION: "admin_security",
    TEMPORARY_USERS_COLLECTION: "admin_security",
    FONT_CACHE_VARIANTS_COLLECTION: "internal_cache",
    FONT_CACHE_FILES_COLLECTION: "internal_cache",
    BACKUP_STATE_COLLECTION: "internal_cache",
    REVISIONS_COLLECTION: "logs_jobs",
    REVISION_CONFIG_COLLECTION: "logs_jobs",
    CHANGELOG_COLLECTION: "logs_jobs",
    BACKUP_LOG_COLLECTION: "logs_jobs",
    INTEGRATION_JOBS_COLLECTION: "logs_jobs",
    ITEM_PAGE_GENERATION_JOBS_COLLECTION: "logs_jobs",
    PAGE_HIT_DAYS_COLLECTION: "logs_jobs",
}


def get_managed_collection_names() -> set[str]:
    return set(MANAGED_COLLECTIONS)


def humanize_collection_prefix_label(value: str) -> str:
    return " ".join(part.capitalize() for part in str(value or "other").split("_") if part) or "Other"


def get_collection_group_id(collection_name: str) -> str:
    normalized = str(collection_name or "").strip()
    mapped = COLLECTION_GROUP_BY_NAME.get(normalized)
    if mapped:
        return mapped
    if (
        "log" in normalized
        or "revision" in normalized
        or normalized.endswith("_jobs")
        or normalized == "changelog"
    ):
        return "logs_jobs"
    if "cache" in normalized or normalized.endswith("_state"):
        return "internal_cache"
    if normalized.startswith("integration_"):
        return "integrations"
    if (
        normalized.startswith("template_")
        or normalized.startswith("item_page_")
        or "redirect" in normalized
        or "sitemap" in normalized
    ):
        return "templates_routing"
    if "design" in normalized or normalized.endswith("_snippets"):
        return "styling"
    if (
        normalized.endswith("_shared")
        or normalized.endswith("_gigs")
        or normalized in {PAGES_COLLECTION, SECTIONS_COLLECTION, HEADERS_COLLECTION, ASSETS_COLLECTION}
        or normalized == BLOG_CONFIG_COLLECTION
    ):
        return "main_content"
    return "admin_security"


def get_collection_prefix_id(collection_name: str) -> str:
    normalized = str(collection_name or "").strip()
    parts = [part for part in normalized.split("_") if part]
    if len(parts) <= 1:
        return normalized or "other"
    if parts[:2] == ["font", "cache"]:
        return "font_cache"
    if parts[:2] == ["item", "page"]:
        return "item_page"
    return parts[0]


def build_collection_summary(collection_name: str, count: int, **extra) -> dict:
    group_id = get_collection_group_id(collection_name)
    group_meta = COLLECTION_GROUP_META.get(group_id, COLLECTION_GROUP_META["admin_security"])
    prefix_id = get_collection_prefix_id(collection_name)
    return {
        "name": collection_name,
        "count": int(count or 0),
        "collection_group": group_id,
        "collection_group_label": str(group_meta["label"]),
        "collection_group_order": int(group_meta["order"]),
        "collection_prefix": prefix_id,
        "collection_prefix_label": humanize_collection_prefix_label(prefix_id),
        **extra,
    }
