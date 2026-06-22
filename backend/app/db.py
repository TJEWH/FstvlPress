from __future__ import annotations

import hashlib
import json
import logging
from copy import deepcopy
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
from pymongo.errors import CollectionInvalid, DuplicateKeyError

from app.collection_names import (
    ACCESS_CONTROL_CONFIG_COLLECTION,
    ASSETS_COLLECTION,
    BACKUP_STATE_COLLECTION,
    BLOG_SHARED_COLLECTION,
    CHANGELOG_COLLECTION,
    CSS_SNIPPETS_COLLECTION,
    DESIGN_EDITOR_CONFIG_COLLECTION,
    DESIGN_CONFIG_COLLECTION,
    DESIGN_VERSIONS_COLLECTION,
    DEVOPS_CONFIG_COLLECTION,
    FAQ_SHARED_COLLECTION,
    FONT_CACHE_FILES_COLLECTION,
    FONT_CACHE_VARIANTS_COLLECTION,
    HEADERS_COLLECTION,
    INTEGRATION_CONFIG_COLLECTION,
    INTEGRATION_DATA_COLLECTION,
    INTEGRATION_EXPOSURE_CONFIG_COLLECTION,
    INTEGRATION_JOBS_COLLECTION,
    INTEGRATION_MEDIA_REGISTRY_COLLECTION,
    INTEGRATION_SECTION_CACHE_VERSIONS_COLLECTION,
    ITEM_PAGE_CONFIG_COLLECTION,
    ITEM_PAGE_GENERATION_JOBS_COLLECTION,
    ITEM_PAGE_ROUTES_COLLECTION,
    LEGACY_ADMIN_ACCESS_CONTROL_CONFIG_COLLECTION,
    LEGACY_ADMIN_DESIGN_CONFIG_COLLECTION,
    LEGACY_ADMIN_DEVOPS_CONFIG_COLLECTION,
    LEGACY_ADMIN_MEDIA_CONFIG_COLLECTION,
    LEGACY_ADMIN_SITEMAP_CONFIG_COLLECTION,
    LEGACY_BACKUP_COUNTERS_COLLECTION,
    LEGACY_BLOG_ITEMS_COLLECTION,
    LEGACY_DESIGN_SETTINGS_COLLECTION,
    LEGACY_GLOBAL_ITEM_PAGE_CONFIG_COLLECTION,
    LEGACY_INTEGRATIONS_COLLECTION,
    LEGACY_INTEGRATION_CONNECTION_CONFIG_COLLECTION,
    LEGACY_ROUTE_REDIRECTS_COLLECTION,
    LEGACY_SECTION_INTEGRATION_CACHE_VERSIONS_COLLECTION,
    LEGACY_SHARED_ITEM_PAGE_ROUTES_COLLECTION,
    LEGACY_TEMP_CREDENTIALS_COLLECTION,
    LEGACY_TEMPORAL_USER_COLLECTION,
    MANAGED_COLLECTIONS,
    PAGE_HIT_DAYS_COLLECTION,
    PAGE_REDIRECTS_COLLECTION,
    PAGES_COLLECTION,
    PROGRAM_GIGS_COLLECTION,
    PROGRAM_SHARED_COLLECTION,
    REVISIONS_COLLECTION,
    SECTIONS_COLLECTION,
    SITEMAP_CONFIG_COLLECTION,
    TEMPORARY_USERS_COLLECTION,
    TEMPLATE_CONTAINERS_COLLECTION,
    TEMPLATE_PAGES_COLLECTION,
    TEMPLATE_SECTIONS_COLLECTION,
    MEDIA_CONFIG_COLLECTION,
)
from app.settings import settings
from app.job_retention import JOB_TERMINAL_STATUSES, job_expires_at, normalize_job_status
from app.models.sections.sections import SECTION_TYPE_SCHEMAS, migrate_document_section_payload
from app.section_structure import (
    apply_section_order_from_structure,
    resolve_section_structure,
    strip_legacy_container_override,
)
from app.template_sync import (
    GLOBAL_ITEM_PAGE_CONFIG_DOC_ID,
    GLOBAL_ITEM_PAGE_ROUTING_VERSION,
    default_item_page_slug_field,
    normalize_section_template_doc,
)
from app.program_catalog import (
    migrate_program_gigs_to_collection,
)

client: AsyncIOMotorClient | None = None
logger = logging.getLogger(__name__)

FAQ_LEGACY_TYPE_DATA_KEYS: tuple[str, ...] = (
    "faqs",
    "faqItems",
    "faq_items",
    "faqTags",
    "faq_tags",
    "items",
    "tags",
    "scope",
)
FAQ_CACHE_STATE_KEYS: tuple[str, ...] = (
    "section_integration_mapping_cache_state",
    "sectionIntegrationMappingCacheState",
    "faq_integration_mapping_cache_state",
    "faqIntegrationMappingCacheState",
    "integration_mapping_cache_state",
    "integrationMappingCacheState",
)


def _normalize_faq_section_topic_value(value) -> dict[str, str]:
    source = value if isinstance(value, dict) else {}
    return {
        "de": str(source.get("de") or "").strip(),
        "en": str(source.get("en") or "").strip(),
    }


def _normalize_faq_section_scopes(value) -> list[dict[str, str]]:
    raw_items = value if isinstance(value, list) else [value]
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw_item in raw_items:
        scope = _normalize_faq_section_topic_value(raw_item)
        key = (scope["de"], scope["en"])
        if not key[0] and not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        normalized.append(scope)
    return normalized


def _normalize_faq_section_type_data_for_storage(type_data) -> dict:
    source = deepcopy(type_data) if isinstance(type_data, dict) else {}
    raw_scopes = (
        source.get("scopes")
        if isinstance(source.get("scopes"), list)
        else source.get("scope")
    )
    source["scopes"] = _normalize_faq_section_scopes(raw_scopes)
    for key in FAQ_LEGACY_TYPE_DATA_KEYS + FAQ_CACHE_STATE_KEYS:
        source.pop(key, None)
    return source


def _build_faq_section_cleanup_update(doc: dict) -> dict | None:
    if not isinstance(doc, dict) or str(doc.get("section_type") or "").lower() != "faq":
        return None

    update: dict[str, dict[str, object]] = {}
    current_type_data = doc.get("type_data")
    normalized_type_data = _normalize_faq_section_type_data_for_storage(current_type_data)
    if (
        not isinstance(current_type_data, dict)
        or normalized_type_data != current_type_data
    ):
        update.setdefault("$set", {})["type_data"] = normalized_type_data

    top_level_unset = {
        key: ""
        for key in FAQ_CACHE_STATE_KEYS
        if key in doc
    }
    if top_level_unset:
        update["$unset"] = top_level_unset

    return update or None


async def cleanup_legacy_faq_section_documents(db) -> None:
    """Remove legacy FAQ instance payload from stored section documents."""
    for collection_name in (SECTIONS_COLLECTION, TEMPLATE_SECTIONS_COLLECTION):
        collection = db[collection_name]
        modified_count = 0
        async for doc in collection.find({"section_type": "faq"}):
            update = _build_faq_section_cleanup_update(doc)
            if not update:
                continue
            result = await collection.update_one({"_id": doc.get("_id")}, update)
            modified_count += int(result.modified_count or 0)

        if modified_count:
            logger.info(
                "Cleaned legacy FAQ payload fields from %s %s documents",
                modified_count,
                collection_name,
            )


# Collections that should exist after initialization/reset.
REQUIRED_COLLECTIONS: tuple[str, ...] = MANAGED_COLLECTIONS


def get_client() -> AsyncIOMotorClient:
    """
    Returns the global MongoDB client initialized in init_db().
    """
    assert client is not None, "Mongo client not initialized"
    return client


RENAMED_COLLECTIONS: dict[str, str] = {
    LEGACY_ROUTE_REDIRECTS_COLLECTION: PAGE_REDIRECTS_COLLECTION,
    LEGACY_BLOG_ITEMS_COLLECTION: BLOG_SHARED_COLLECTION,
    LEGACY_INTEGRATIONS_COLLECTION: INTEGRATION_CONFIG_COLLECTION,
    LEGACY_TEMP_CREDENTIALS_COLLECTION: TEMPORARY_USERS_COLLECTION,
    LEGACY_ADMIN_DESIGN_CONFIG_COLLECTION: DESIGN_EDITOR_CONFIG_COLLECTION,
    LEGACY_ADMIN_MEDIA_CONFIG_COLLECTION: MEDIA_CONFIG_COLLECTION,
    LEGACY_ADMIN_SITEMAP_CONFIG_COLLECTION: SITEMAP_CONFIG_COLLECTION,
    LEGACY_ADMIN_ACCESS_CONTROL_CONFIG_COLLECTION: ACCESS_CONTROL_CONFIG_COLLECTION,
    LEGACY_ADMIN_DEVOPS_CONFIG_COLLECTION: DEVOPS_CONFIG_COLLECTION,
    LEGACY_INTEGRATION_CONNECTION_CONFIG_COLLECTION: INTEGRATION_EXPOSURE_CONFIG_COLLECTION,
    LEGACY_TEMPORAL_USER_COLLECTION: TEMPORARY_USERS_COLLECTION,
    LEGACY_GLOBAL_ITEM_PAGE_CONFIG_COLLECTION: ITEM_PAGE_CONFIG_COLLECTION,
    LEGACY_SHARED_ITEM_PAGE_ROUTES_COLLECTION: ITEM_PAGE_ROUTES_COLLECTION,
    LEGACY_SECTION_INTEGRATION_CACHE_VERSIONS_COLLECTION: INTEGRATION_SECTION_CACHE_VERSIONS_COLLECTION,
    LEGACY_BACKUP_COUNTERS_COLLECTION: BACKUP_STATE_COLLECTION,
}

DESIGN_SETTINGS_TARGET_BY_KEY: dict[str, str] = {
    "global": DESIGN_CONFIG_COLLECTION,
    LEGACY_ADMIN_DESIGN_CONFIG_COLLECTION: DESIGN_EDITOR_CONFIG_COLLECTION,
    DESIGN_EDITOR_CONFIG_COLLECTION: DESIGN_EDITOR_CONFIG_COLLECTION,
    LEGACY_ADMIN_MEDIA_CONFIG_COLLECTION: MEDIA_CONFIG_COLLECTION,
    MEDIA_CONFIG_COLLECTION: MEDIA_CONFIG_COLLECTION,
    LEGACY_ADMIN_SITEMAP_CONFIG_COLLECTION: SITEMAP_CONFIG_COLLECTION,
    SITEMAP_CONFIG_COLLECTION: SITEMAP_CONFIG_COLLECTION,
    LEGACY_ADMIN_ACCESS_CONTROL_CONFIG_COLLECTION: ACCESS_CONTROL_CONFIG_COLLECTION,
    ACCESS_CONTROL_CONFIG_COLLECTION: ACCESS_CONTROL_CONFIG_COLLECTION,
    LEGACY_ADMIN_DEVOPS_CONFIG_COLLECTION: DEVOPS_CONFIG_COLLECTION,
    DEVOPS_CONFIG_COLLECTION: DEVOPS_CONFIG_COLLECTION,
    "integrations_connection_config": INTEGRATION_EXPOSURE_CONFIG_COLLECTION,
    LEGACY_INTEGRATION_CONNECTION_CONFIG_COLLECTION: INTEGRATION_EXPOSURE_CONFIG_COLLECTION,
    INTEGRATION_EXPOSURE_CONFIG_COLLECTION: INTEGRATION_EXPOSURE_CONFIG_COLLECTION,
}

SINGLETON_CONFIG_KEYS_BY_COLLECTION: dict[str, tuple[str, ...]] = {
    DESIGN_EDITOR_CONFIG_COLLECTION: (
        LEGACY_ADMIN_DESIGN_CONFIG_COLLECTION,
        DESIGN_EDITOR_CONFIG_COLLECTION,
    ),
    MEDIA_CONFIG_COLLECTION: (
        LEGACY_ADMIN_MEDIA_CONFIG_COLLECTION,
        MEDIA_CONFIG_COLLECTION,
    ),
    SITEMAP_CONFIG_COLLECTION: (
        LEGACY_ADMIN_SITEMAP_CONFIG_COLLECTION,
        SITEMAP_CONFIG_COLLECTION,
    ),
    ACCESS_CONTROL_CONFIG_COLLECTION: (
        LEGACY_ADMIN_ACCESS_CONTROL_CONFIG_COLLECTION,
        ACCESS_CONTROL_CONFIG_COLLECTION,
    ),
    DEVOPS_CONFIG_COLLECTION: (
        LEGACY_ADMIN_DEVOPS_CONFIG_COLLECTION,
        DEVOPS_CONFIG_COLLECTION,
    ),
    INTEGRATION_EXPOSURE_CONFIG_COLLECTION: (
        "integrations_connection_config",
        LEGACY_INTEGRATION_CONNECTION_CONFIG_COLLECTION,
        INTEGRATION_EXPOSURE_CONFIG_COLLECTION,
    ),
}

CANONICAL_SINGLETON_KEY_BY_COLLECTION = {
    collection_name: keys[-1]
    for collection_name, keys in SINGLETON_CONFIG_KEYS_BY_COLLECTION.items()
}


async def _merge_legacy_collection(db, legacy_name: str, target_name: str) -> None:
    existing_names = set(await db.list_collection_names())
    if legacy_name not in existing_names:
        return

    if target_name not in existing_names:
        await db[legacy_name].rename(target_name)
        logger.info("Renamed legacy collection %s to %s", legacy_name, target_name)
        return

    target_coll = db[target_name]
    async for doc in db[legacy_name].find({}):
        if await target_coll.find_one({"_id": doc.get("_id")}, {"_id": 1}):
            continue
        try:
            await target_coll.insert_one(deepcopy(doc))
        except DuplicateKeyError:
            logger.warning(
                "Skipped legacy document from %s during merge into %s due to a duplicate key",
                legacy_name,
                target_name,
            )
    await db.drop_collection(legacy_name)
    logger.info("Merged and dropped legacy collection %s", legacy_name)


async def _split_legacy_design_settings_collection(db) -> None:
    existing_names = set(await db.list_collection_names())
    if LEGACY_DESIGN_SETTINGS_COLLECTION not in existing_names:
        return

    legacy_coll = db[LEGACY_DESIGN_SETTINGS_COLLECTION]
    async for doc in legacy_coll.find({}):
        key = str(doc.get("key") or "").strip()
        target_name = DESIGN_SETTINGS_TARGET_BY_KEY.get(key, DESIGN_CONFIG_COLLECTION)
        target_coll = db[target_name]
        migrated_doc = deepcopy(doc)
        canonical_key = CANONICAL_SINGLETON_KEY_BY_COLLECTION.get(target_name)
        if canonical_key:
            migrated_doc["key"] = canonical_key
            lookup = {"key": {"$in": SINGLETON_CONFIG_KEYS_BY_COLLECTION[target_name]}}
        else:
            lookup = {"key": key} if key else {"_id": doc.get("_id")}
        if await target_coll.find_one(lookup, {"_id": 1}):
            continue
        try:
            await target_coll.insert_one(migrated_doc)
        except DuplicateKeyError:
            logger.warning(
                "Skipped legacy design settings document with key %s during split into %s",
                key or "<missing>",
                target_name,
            )

    await db.drop_collection(LEGACY_DESIGN_SETTINGS_COLLECTION)
    logger.info("Split and dropped legacy collection %s", LEGACY_DESIGN_SETTINGS_COLLECTION)


async def migrate_renamed_collections(db) -> None:
    """Move legacy collection names to their current canonical names."""
    for legacy_name, target_name in RENAMED_COLLECTIONS.items():
        await _merge_legacy_collection(db, legacy_name, target_name)
    await _split_legacy_design_settings_collection(db)
    for collection_name, canonical_key in CANONICAL_SINGLETON_KEY_BY_COLLECTION.items():
        await db[collection_name].update_many(
            {"key": {"$in": SINGLETON_CONFIG_KEYS_BY_COLLECTION[collection_name]}},
            {"$set": {"key": canonical_key}},
        )


async def migrate_design_versions_to_design_only(db) -> None:
    """Ensure design versions store only visual design snapshots."""
    result = await db[DESIGN_VERSIONS_COLLECTION].update_many(
        {"admin_config": {"$exists": True}},
        {"$unset": {"admin_config": ""}},
    )
    if result.modified_count:
        logger.info(
            "Removed admin_config snapshots from %s design version documents",
            result.modified_count,
        )


def _compute_design_version_hash(design_settings: dict | None) -> str:
    payload = json.dumps({"d": design_settings}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def _merge_design_version_diff(base: dict | None, diff: dict | None) -> dict | None:
    if base is None:
        return deepcopy(diff) if isinstance(diff, dict) else diff
    if diff is None:
        return deepcopy(base) if isinstance(base, dict) else base

    merged = deepcopy(base) if isinstance(base, dict) else {}
    for key, value in diff.items():
        base_value = merged.get(key)
        if isinstance(value, dict) and isinstance(base_value, dict):
            merged[key] = _merge_design_version_diff(base_value, value)
        else:
            merged[key] = deepcopy(value)
    return merged


async def _resolve_legacy_design_version_snapshot(versions_coll, doc: dict, seen: set[ObjectId] | None = None) -> dict | None:
    parent_id = doc.get("parent_id")
    design_settings = doc.get("design_settings")
    if not parent_id:
        return deepcopy(design_settings) if isinstance(design_settings, dict) else design_settings

    seen = set(seen or set())
    doc_id = doc.get("_id")
    if isinstance(doc_id, ObjectId):
        if doc_id in seen:
            logger.warning("Cycle detected while flattening design version %s", doc_id)
            return deepcopy(design_settings) if isinstance(design_settings, dict) else design_settings
        seen.add(doc_id)

    try:
        parent_oid = parent_id if isinstance(parent_id, ObjectId) else ObjectId(parent_id)
    except Exception:
        logger.warning("Invalid parent_id on design version %s: %r", doc.get("_id"), parent_id)
        return deepcopy(design_settings) if isinstance(design_settings, dict) else design_settings

    parent_doc = await versions_coll.find_one({"_id": parent_oid})
    if not parent_doc:
        logger.warning("Missing parent design version %s for %s", parent_oid, doc.get("_id"))
        return deepcopy(design_settings) if isinstance(design_settings, dict) else design_settings

    parent_design = await _resolve_legacy_design_version_snapshot(versions_coll, parent_doc, seen)
    return _merge_design_version_diff(parent_design, design_settings)


async def migrate_design_subversions_to_versions(db) -> None:
    """Flatten legacy design subversions into standalone full snapshots."""
    versions = db[DESIGN_VERSIONS_COLLECTION]
    legacy_docs = await versions.find({"parent_id": {"$exists": True, "$ne": None}}).to_list(length=None)
    if not legacy_docs:
        return

    now = datetime.utcnow()
    for doc in legacy_docs:
        resolved_design = await _resolve_legacy_design_version_snapshot(versions, doc)
        await versions.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "design_settings": resolved_design,
                    "hash": _compute_design_version_hash(resolved_design),
                    "parent_id": None,
                    "flattened_at": now,
                },
                "$unset": {"admin_config": ""},
            },
        )

    logger.info("Flattened %s design subversion documents", len(legacy_docs))


def _job_expiry_reference_time(doc: dict) -> datetime:
    for field in ("finished_at", "updated_at", "started_at", "created_at"):
        value = doc.get(field)
        if isinstance(value, datetime):
            return value
    return datetime.utcnow()


async def backfill_job_expirations(db) -> None:
    """Add TTL expiration dates to existing operational job documents."""
    job_statuses = [*JOB_TERMINAL_STATUSES, "queued", "running"]
    for collection_name in (INTEGRATION_JOBS_COLLECTION, ITEM_PAGE_GENERATION_JOBS_COLLECTION):
        coll = db[collection_name]
        operations: list[UpdateOne] = []
        async for doc in coll.find(
            {
                "status": {"$in": job_statuses},
                "$or": [
                    {"expires_at": {"$exists": False}},
                    {"expires_at": None},
                ],
            },
            {
                "_id": 1,
                "status": 1,
                "created_at": 1,
                "started_at": 1,
                "updated_at": 1,
                "finished_at": 1,
            },
        ):
            expires_at = job_expires_at(
                normalize_job_status(doc.get("status")),
                _job_expiry_reference_time(doc),
            )
            if not expires_at:
                continue
            operations.append(
                UpdateOne(
                    {
                        "_id": doc.get("_id"),
                        "$or": [
                            {"expires_at": {"$exists": False}},
                            {"expires_at": None},
                        ],
                    },
                    {"$set": {"expires_at": expires_at}},
                )
            )
            if len(operations) >= 500:
                result = await coll.bulk_write(operations, ordered=False)
                if result.modified_count:
                    logger.info(
                        "Backfilled expires_at for %s %s documents",
                        result.modified_count,
                        collection_name,
                    )
                operations = []
        if operations:
            result = await coll.bulk_write(operations, ordered=False)
            if result.modified_count:
                logger.info(
                    "Backfilled expires_at for %s %s documents",
                    result.modified_count,
                    collection_name,
                )


async def init_db() -> None:
    """
    Initialize MongoDB client and create indexes for all collections used by the app.
    Called once on app startup via lifespan.

    Database name is year-based (e.g., "2026").
    """
    global client
    client = AsyncIOMotorClient(settings.mongo_uri)

    db = client[settings.mongo_db]
    await ensure_db_collections_and_indexes(db)
    await seed_default_pages(db)


async def ensure_db_collections_and_indexes(db) -> None:
    """
    Ensure required collections and indexes exist for a ready-to-run instance.
    Safe to call on startup and after destructive resets.
    """
    await migrate_renamed_collections(db)

    # Cleanup: these collections are no longer used.
    await db.drop_collection("section_revisions")
    await db.drop_collection("system_meta")
    await db.drop_collection("blog_migration_lock")
    await db.drop_collection("unused_media_cleanup_scans")

    existing_names = set(await db.list_collection_names())
    for collection_name in REQUIRED_COLLECTIONS:
        if collection_name in existing_names:
            continue
        try:
            await db.create_collection(collection_name)
        except CollectionInvalid:
            # Collection may have been created concurrently.
            pass

    # Collections (created implicitly by MongoDB on first insert)
    pages = db[PAGES_COLLECTION]
    sections = db[SECTIONS_COLLECTION]
    revisions = db[REVISIONS_COLLECTION]  # stores section, header, and design revisions
    changelog = db[CHANGELOG_COLLECTION]
    headers = db[HEADERS_COLLECTION]
    assets = db[ASSETS_COLLECTION]
    page_redirects = db[PAGE_REDIRECTS_COLLECTION]
    page_hit_days = db[PAGE_HIT_DAYS_COLLECTION]
    template_sections = db[TEMPLATE_SECTIONS_COLLECTION]
    template_containers = db[TEMPLATE_CONTAINERS_COLLECTION]
    template_pages = db[TEMPLATE_PAGES_COLLECTION]
    css_snippets = db[CSS_SNIPPETS_COLLECTION]
    font_cache_variants = db[FONT_CACHE_VARIANTS_COLLECTION]
    font_cache_files = db[FONT_CACHE_FILES_COLLECTION]

    await cleanup_legacy_faq_section_documents(db)

    # --- Indexes for performance and uniqueness

    # Pages
    await pages.create_index([("slug", 1)], unique=True)
    await pages.create_index([("updated_at", -1)])
    await pages.create_index([("header_id", 1)])  # for looking up pages by header
    await pages.create_index([("sections.section_id", 1)])
    await pages.create_index([("template_style_ref", 1)])
    await pages.create_index([("template_style_linked", 1), ("template_style_ref", 1)])
    await pages.create_index([
        ("template_managed", 1),
        ("template_integration_id", 1),
        ("template_integration_item_key", 1),
    ])

    # Sections (standalone, referenced by pages via sections array)
    await sections.create_index([("updated_at", -1)])
    await sections.create_index([("title_placeholder", 1)])
    await sections.create_index([("section_type", 1)])
    await sections.create_index([("section_type", 1), ("updated_at", -1)])

    # Revisions (undo/redo history for sections, headers, and global design)
    await revisions.create_index([("entity_type", 1), ("entity_id", 1)], unique=True)
    await revisions.create_index([("last_saved_at", -1)])
    await changelog.create_index([("saved_at", -1)])
    await changelog.create_index([("entity_type", 1), ("entity_id", 1), ("saved_at", -1)])

    # Headers
    await headers.create_index([("header_type", 1)])
    await headers.create_index([("updated_at", -1)])

    # Assets
    await assets.create_index([("key", 1)], unique=True)
    await assets.create_index([("media_hash", 1)], unique=True, sparse=True)
    await assets.create_index([("url", 1)])
    await assets.create_index([("source_url_hash", 1)], sparse=True)
    await assets.create_index([("resolved_source_url_hash", 1)], sparse=True)
    await assets.create_index([("created_at", -1)])

    # Page redirects (custom + generated by page moves)
    await page_redirects.create_index([("source_path", 1)], unique=True)
    await page_redirects.create_index([("kind", 1)])
    await page_redirects.create_index([("expires_at", 1)])
    await page_redirects.create_index([("updated_at", -1)])

    # Page hit daily buckets
    await page_hit_days.create_index([("page_id", 1), ("day", 1)], unique=True)
    await page_hit_days.create_index([("day", 1)])

    # Template sections
    await template_sections.create_index(
        [("section_type", 1), ("template_name", 1)],
        unique=True,
    )
    await template_sections.create_index([("updated_at", -1)])

    # Template containers
    await template_containers.create_index([("template_name", 1)], unique=True)
    await template_containers.create_index([("updated_at", -1)])

    # Template pages:
    # - Normal/unrouted page templates (parent_route = null): unique template_name
    # - Routed item-page templates: unique per (parent_route, template_name)
    async for index_doc in template_pages.list_indexes():
        key = index_doc.get("key") if isinstance(index_doc, dict) else None
        if dict(key or {}) == {"parent_route": 1} and bool(index_doc.get("unique")):
            await template_pages.drop_index(str(index_doc.get("name")))
    await template_pages.create_index(
        [("template_name", 1)],
        unique=True,
        partialFilterExpression={"parent_route": None},
    )
    await template_pages.create_index(
        [("parent_route", 1), ("template_name", 1)],
        unique=True,
        partialFilterExpression={"parent_route": {"$type": "string"}},
    )
    await template_pages.create_index([("source_type", 1)])
    await template_pages.create_index([("updated_at", -1)])

    # CSS snippets:
    # - Global snippets are filtered by scope=global
    # - Template snippets are filtered by (scope=template, template_key)
    await css_snippets.create_index([("scope", 1)])
    await css_snippets.create_index([("scope", 1), ("template_key", 1)])
    await css_snippets.create_index([("created_at", -1)])

    # Font cache variants/files
    await font_cache_variants.create_index([("variant_key", 1)], unique=True)
    await font_cache_variants.create_index([("family_normalized", 1), ("updated_at", -1)])
    await font_cache_variants.create_index([("status", 1), ("updated_at", -1)])
    await font_cache_files.create_index([("source_url_hash", 1)], unique=True)
    await font_cache_files.create_index([("content_sha256", 1)])
    await font_cache_files.create_index([("updated_at", -1)])

    # Blog shared items (shared across all blog sections)
    blog_shared = db[BLOG_SHARED_COLLECTION]
    await blog_shared.create_index([("date", -1)])
    await blog_shared.create_index([("created_at", -1)])

    # FAQ shared doc
    faq_shared = db[FAQ_SHARED_COLLECTION]
    await faq_shared.create_index([("updated_at", -1)])

    # Program shared catalog + canonical gig documents
    program_shared = db[PROGRAM_SHARED_COLLECTION]
    program_gigs = db[PROGRAM_GIGS_COLLECTION]
    await program_shared.create_index([("updated_at", -1)])
    await program_gigs.create_index([("stage", 1)])
    await program_gigs.create_index([("start", 1)])
    await program_gigs.create_index([("end", 1)])
    await program_gigs.create_index([("updated_at", -1)])

    # Integrations + fetched integration data
    integration_config = db[INTEGRATION_CONFIG_COLLECTION]
    integration_data = db[INTEGRATION_DATA_COLLECTION]
    integration_jobs = db[INTEGRATION_JOBS_COLLECTION]
    integration_media_registry = db[INTEGRATION_MEDIA_REGISTRY_COLLECTION]
    item_page_generation_jobs = db[ITEM_PAGE_GENERATION_JOBS_COLLECTION]
    temporary_users = db[TEMPORARY_USERS_COLLECTION]
    await integration_config.create_index([("name", 1)])
    await integration_config.create_index([("created_at", -1)])
    await integration_data.create_index([("integration_id", 1), ("fetched_at", -1)])
    await integration_data.create_index([("fetched_at", -1)])
    await integration_jobs.create_index([("integration_id", 1), ("created_at", -1)])
    await integration_jobs.create_index([("status", 1), ("created_at", -1)])
    await integration_jobs.create_index(
        [("expires_at", 1)],
        expireAfterSeconds=0,
        name="integration_jobs_expires_at_ttl",
    )
    await integration_media_registry.create_index([("original_url", 1), ("etag", 1)])
    await integration_media_registry.create_index([("updated_at", -1)])
    await item_page_generation_jobs.create_index([("source_key", 1), ("created_at", -1)])
    await item_page_generation_jobs.create_index([("status", 1), ("updated_at", -1)])
    await item_page_generation_jobs.create_index([("created_at", -1)])
    await item_page_generation_jobs.create_index(
        [("expires_at", 1)],
        expireAfterSeconds=0,
        name="item_page_generation_jobs_expires_at_ttl",
    )
    await temporary_users.create_index([("username", 1)], unique=True)
    await temporary_users.create_index([("active", 1), ("expires_at", 1)])
    await temporary_users.create_index([("expires_at", 1)])

    # Blog config: no extra indexes needed.
    # MongoDB automatically creates a unique index on _id for every collection.
    await migrate_legacy_document_sections(db)
    await migrate_legacy_section_structure(db)
    await migrate_template_owned_item_page_routing(db)
    await migrate_design_versions_to_design_only(db)
    await migrate_design_subversions_to_versions(db)
    await migrate_program_gigs_to_collection(db)
    await backfill_job_expirations(db)
    await ensure_default_section_templates(db)


async def migrate_template_owned_item_page_routing(db) -> None:
    """One-time move from global route authority to template-owned routing."""
    now = datetime.utcnow()
    cfg_coll = db[ITEM_PAGE_CONFIG_COLLECTION]
    cfg_doc = await cfg_coll.find_one({"_id": GLOBAL_ITEM_PAGE_CONFIG_DOC_ID})
    already_migrated = (
        isinstance(cfg_doc, dict)
        and int(cfg_doc.get("routing_version") or 0) >= GLOBAL_ITEM_PAGE_ROUTING_VERSION
    )
    if not already_migrated:
        await cfg_coll.update_one(
            {"_id": GLOBAL_ITEM_PAGE_CONFIG_DOC_ID},
            {
                "$set": {
                    "blog_item_parent_route": "",
                    "program_stage_parent_route": "",
                    "program_gig_parent_route": "",
                    "blog_item_template_path": "",
                    "program_stage_template_path": "",
                    "program_gig_template_path": "",
                    "blog_item_slug_field": "title",
                    "program_stage_slug_field": "name",
                    "program_gig_slug_field": "title",
                    "routing_version": GLOBAL_ITEM_PAGE_ROUTING_VERSION,
                    "template_owned_item_page_routing_migrated_at": now,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    template_pages = db[TEMPLATE_PAGES_COLLECTION]
    item_query = {
        "$or": [
            {"template_kind": "item_page"},
            {"source_type": {"$in": ["blog", "program", "tiles"]}},
            {"parent_route": {"$type": "string"}},
        ]
    }
    await template_pages.update_many(
        {**item_query, "item_page_subroute": {"$exists": False}},
        {"$set": {"item_page_subroute": ""}},
    )
    await template_pages.update_many(
        {**item_query, "item_page_source_section_id": {"$exists": False}},
        {"$set": {"item_page_source_section_id": None}},
    )
    for source_type, source_kind in (
        ("blog", "item"),
        ("program", "stage"),
        ("program", "gig"),
    ):
        query = {
            **item_query,
            "source_type": source_type,
            "source_kind": source_kind,
            "$or": [
                {"item_page_slug_field": {"$exists": False}},
                {"item_page_slug_field": ""},
                {"item_page_slug_field": None},
            ],
        }
        await template_pages.update_many(
            query,
            {"$set": {"item_page_slug_field": default_item_page_slug_field(source_type, source_kind)}},
        )


def _normalize_document_type_payload(section_type: object, type_data: object) -> tuple[str, dict]:
    resolved_type, resolved_type_data = migrate_document_section_payload(
        str(section_type or "").strip().lower(),
        type_data if isinstance(type_data, dict) else {},
    )
    if not isinstance(resolved_type_data, dict):
        resolved_type_data = {}
    return resolved_type, resolved_type_data


def _migrate_embedded_sections_array(raw_sections: object) -> tuple[list[dict], bool]:
    sections = raw_sections if isinstance(raw_sections, list) else []
    changed = False
    migrated: list[dict] = []

    for raw_entry in sections:
        if not isinstance(raw_entry, dict):
            migrated.append(raw_entry)
            continue
        entry = deepcopy(raw_entry)
        current_type = str(entry.get("section_type") or "").strip().lower()
        current_type_data = entry.get("type_data") if isinstance(entry.get("type_data"), dict) else {}
        next_type, next_type_data = _normalize_document_type_payload(current_type, current_type_data)
        if next_type != current_type or next_type_data != current_type_data:
            changed = True
            entry["section_type"] = next_type
            entry["type_data"] = next_type_data
        migrated.append(entry)

    return migrated, changed


async def migrate_legacy_document_sections(db) -> None:
    """Migrate legacy markdown/html mixed payloads to dedicated markdown/html section types."""
    now = datetime.utcnow()

    sections_coll = db[SECTIONS_COLLECTION]
    section_doc_cursor = sections_coll.find(
        {"section_type": {"$in": ["markdown", "html"]}},
        {"_id": 1, "section_type": 1, "type_data": 1},
    )
    async for doc in section_doc_cursor:
        current_type = str(doc.get("section_type") or "").strip().lower()
        current_type_data = doc.get("type_data") if isinstance(doc.get("type_data"), dict) else {}
        next_type, next_type_data = _normalize_document_type_payload(current_type, current_type_data)
        if next_type == current_type and next_type_data == current_type_data:
            continue
        await sections_coll.update_one(
            {"_id": doc["_id"]},
            {"$set": {"section_type": next_type, "type_data": next_type_data, "updated_at": now}},
        )

    template_sections = db[TEMPLATE_SECTIONS_COLLECTION]
    template_cursor = template_sections.find(
        {"section_type": {"$in": ["markdown", "html"]}},
    )
    async for template_doc in template_cursor:
        current_type = str(template_doc.get("section_type") or "").strip().lower()
        current_type_data = (
            template_doc.get("type_data")
            if isinstance(template_doc.get("type_data"), dict)
            else {}
        )
        next_type, next_type_data = _normalize_document_type_payload(current_type, current_type_data)
        if next_type == current_type and next_type_data == current_type_data:
            continue

        template_name = str(template_doc.get("template_name") or "default").strip().lower() or "default"
        if next_type != current_type:
            existing_target = await template_sections.find_one(
                {"section_type": next_type, "template_name": template_name},
                {"_id": 1},
            )
            if existing_target and existing_target.get("_id") != template_doc.get("_id"):
                await template_sections.update_one(
                    {"_id": existing_target["_id"]},
                    {
                        "$set": {
                            "title_placeholder": template_doc.get("title_placeholder"),
                            "title": deepcopy(template_doc.get("title"))
                            if isinstance(template_doc.get("title"), dict)
                            else {"de": "", "en": ""},
                            "type_data": next_type_data,
                            "design_overrides": deepcopy(template_doc.get("design_overrides"))
                            if isinstance(template_doc.get("design_overrides"), dict)
                            else None,
                            "section_integration_mapping": deepcopy(
                                template_doc.get("section_integration_mapping")
                            )
                            if isinstance(template_doc.get("section_integration_mapping"), dict)
                            else {},
                            "updated_at": now,
                        }
                    },
                )
                await template_sections.delete_one({"_id": template_doc["_id"]})
                continue

        await template_sections.update_one(
            {"_id": template_doc["_id"]},
            {
                "$set": {
                    "section_type": next_type,
                    "type_data": next_type_data,
                    "updated_at": now,
                }
            },
        )

    for collection_name in (TEMPLATE_CONTAINERS_COLLECTION, TEMPLATE_PAGES_COLLECTION):
        coll = db[collection_name]
        cursor = coll.find({}, {"_id": 1, "sections": 1})
        async for doc in cursor:
            migrated_sections, changed = _migrate_embedded_sections_array(doc.get("sections"))
            if not changed:
                continue
            await coll.update_one(
                {"_id": doc["_id"]},
                {"$set": {"sections": migrated_sections, "updated_at": now}},
            )


def _normalize_page_section_refs_and_structure(
    raw_sections: object,
    raw_structure: object,
) -> tuple[list[dict], list[dict], bool]:
    refs = [deepcopy(ref) for ref in (raw_sections if isinstance(raw_sections, list) else []) if isinstance(ref, dict)]
    refs.sort(key=lambda ref: int(ref.get("order", 0) or 0))
    changed = False
    for ref in refs:
        current_overrides = ref.get("design_overrides")
        normalized_overrides = strip_legacy_container_override(current_overrides)
        if normalized_overrides is None:
            if "design_overrides" in ref:
                ref.pop("design_overrides", None)
                changed = True
        elif normalized_overrides != current_overrides:
            ref["design_overrides"] = normalized_overrides
            changed = True

    ordered_ids = [
        str(ref.get("section_id") or "").strip()
        for ref in refs
        if str(ref.get("section_id") or "").strip()
    ]
    normalized_structure = resolve_section_structure(
        raw_structure,
        ordered_ids,
    )
    normalized_refs = apply_section_order_from_structure(
        refs,
        normalized_structure,
        section_id_field="section_id",
    )

    if normalized_refs != refs:
        changed = True
    if normalized_structure != (raw_structure if isinstance(raw_structure, list) else []):
        changed = True

    return normalized_refs, normalized_structure, changed


def _new_embedded_section_id() -> str:
    return f"sec_{ObjectId()}"


def _normalize_template_embedded_sections_and_structure(
    raw_sections: object,
    raw_structure: object,
) -> tuple[list[dict], list[dict], bool]:
    sections_input = raw_sections if isinstance(raw_sections, list) else []
    sections: list[dict] = []
    changed = False

    for index, entry in enumerate(sections_input):
        if not isinstance(entry, dict):
            continue
        section = deepcopy(entry)
        section_id = str(section.get("id") or "").strip()
        if not section_id:
            section_id = _new_embedded_section_id()
            section["id"] = section_id
            changed = True

        section["order"] = int(section.get("order", index) or 0)
        sections.append(section)

    sections.sort(key=lambda section: int(section.get("order", 0) or 0))
    for section in sections:
        current_overrides = section.get("design_overrides")
        normalized_overrides = strip_legacy_container_override(current_overrides)
        if normalized_overrides is None:
            if "design_overrides" in section:
                section.pop("design_overrides", None)
                changed = True
        elif normalized_overrides != current_overrides:
            section["design_overrides"] = normalized_overrides
            changed = True

    ordered_ids = [
        str(section.get("id") or "").strip()
        for section in sections
        if str(section.get("id") or "").strip()
    ]
    normalized_structure = resolve_section_structure(
        raw_structure,
        ordered_ids,
    )
    normalized_sections = apply_section_order_from_structure(
        sections,
        normalized_structure,
        section_id_field="id",
    )

    if normalized_sections != sections:
        changed = True
    if normalized_structure != (raw_structure if isinstance(raw_structure, list) else []):
        changed = True
    return normalized_sections, normalized_structure, changed


async def migrate_legacy_section_structure(db) -> None:
    """Migrate legacy override-based section container groups into section_structure."""
    now = datetime.utcnow()

    pages = db[PAGES_COLLECTION]
    async for doc in pages.find({}, {"_id": 1, "sections": 1, "section_structure": 1}):
        normalized_refs, normalized_structure, changed = _normalize_page_section_refs_and_structure(
            doc.get("sections"),
            doc.get("section_structure"),
        )
        if not changed:
            continue
        await pages.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "sections": normalized_refs,
                    "section_structure": normalized_structure,
                    "updated_at": now,
                }
            },
        )

    for collection_name in (TEMPLATE_PAGES_COLLECTION, TEMPLATE_CONTAINERS_COLLECTION):
        coll = db[collection_name]
        cursor = coll.find({}, {"_id": 1, "sections": 1, "section_structure": 1})
        async for doc in cursor:
            normalized_sections, normalized_structure, changed = _normalize_template_embedded_sections_and_structure(
                doc.get("sections"),
                doc.get("section_structure"),
            )
            if not changed:
                continue
            await coll.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "sections": normalized_sections,
                        "section_structure": normalized_structure,
                        "updated_at": now,
                    }
                },
            )


async def ensure_default_section_templates(db) -> None:
    """
    Ensure each known section type has a default section template.
    Required so normal page section creation with `template_name=default` works
    after fresh init/reset.
    """
    coll = db[TEMPLATE_SECTIONS_COLLECTION]
    now = datetime.utcnow()
    for section_type in SECTION_TYPE_SCHEMAS.keys():
        normalized = normalize_section_template_doc(
            section_type,
            "default",
            payload=None,
            seed_list_target_visibility_presets=True,
        )
        await coll.update_one(
            {"section_type": section_type, "template_name": "default"},
            {
                "$setOnInsert": {
                    **normalized,
                    "created_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
        )


async def seed_default_pages(db) -> None:
    """
    Seeds a minimal landing page if the pages collection is empty.
    This ensures the frontend has something to display on first load.
    """
    pages = db[PAGES_COLLECTION]
    headers = db[HEADERS_COLLECTION]

    page_count = await pages.count_documents({})
    if page_count > 0:
        return

    now = datetime.now(timezone.utc)

    # Create a default header for the landing page
    header_doc = {
        "header_type": "default",
        "title": {"de": "Willkommen", "en": "Welcome"},
        "subtitle": {"de": "", "en": ""},
        "date_text": {"de": "", "en": ""},
        "location_text": {"de": "", "en": ""},
        "background_video_url": "",
        "background_image_url": "",
        "logo_image_url": "",
        "created_at": now,
        "updated_at": now,
    }
    header_result = await headers.insert_one(header_doc)
    header_id = str(header_result.inserted_id)

    # Create the landing page
    landing_page = {
        "slug": "landing",
        "title": {"de": "Startseite", "en": "Home"},
        "has_header": True,
        "header_id": header_id,
        "sections": [],
        "section_structure": [],
        "created_at": now,
        "updated_at": now,
    }
    await pages.insert_one(landing_page)

    logger.info("Seeded default landing page with header (header_id=%s)", header_id)


async def close_db() -> None:
    """
    Close the MongoDB client on app shutdown.
    """
    global client
    if client is not None:
        client.close()
        client = None
