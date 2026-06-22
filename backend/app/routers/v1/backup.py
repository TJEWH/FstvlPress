from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from urllib.parse import unquote, urlsplit

from bson import ObjectId
from botocore.exceptions import ClientError
from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from pymongo import ReturnDocument

from app.collection_names import (
    ASSETS_COLLECTION,
    BACKUP_LOG_COLLECTION,
    BACKUP_STATE_COLLECTION,
    CHANGELOG_COLLECTION,
    DESIGN_CONFIG_COLLECTION,
    HEADERS_COLLECTION,
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
    PAGES_COLLECTION,
    REVISIONS_COLLECTION,
    SECTIONS_COLLECTION,
    build_collection_summary,
)
from app.db import get_client, ensure_db_collections_and_indexes, seed_default_pages
from app.deps import require_permission
from app.revisioning import (
    get_or_create_revision_config,
    normalize_header_revision_options,
    normalize_section_revision_options,
    save_revision_config,
)
from app.settings import settings
from app.storage.s3 import S3Storage
from app.storage.ftp import FTPStorage

router = APIRouter(prefix="/backup", tags=["backup"])


async def _get_next_incremental_counter(db) -> int:
    """Get and increment the incremental backup counter."""
    counters = db[BACKUP_STATE_COLLECTION]
    result = await counters.find_one_and_update(
        {"_id": "incremental"},
        {"$inc": {"counter": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return result.get("counter", 1)


REVISION_HISTORY_COLLECTIONS = {
    CHANGELOG_COLLECTION,
    REVISIONS_COLLECTION,
}

OBSOLETE_COLLECTIONS: tuple[str, ...] = (
    LEGACY_ROUTE_REDIRECTS_COLLECTION,
    LEGACY_BLOG_ITEMS_COLLECTION,
    LEGACY_INTEGRATIONS_COLLECTION,
    LEGACY_DESIGN_SETTINGS_COLLECTION,
    LEGACY_TEMP_CREDENTIALS_COLLECTION,
    LEGACY_ADMIN_DESIGN_CONFIG_COLLECTION,
    LEGACY_ADMIN_MEDIA_CONFIG_COLLECTION,
    LEGACY_ADMIN_SITEMAP_CONFIG_COLLECTION,
    LEGACY_ADMIN_ACCESS_CONTROL_CONFIG_COLLECTION,
    LEGACY_ADMIN_DEVOPS_CONFIG_COLLECTION,
    LEGACY_INTEGRATION_CONNECTION_CONFIG_COLLECTION,
    LEGACY_TEMPORAL_USER_COLLECTION,
    LEGACY_GLOBAL_ITEM_PAGE_CONFIG_COLLECTION,
    LEGACY_SHARED_ITEM_PAGE_ROUTES_COLLECTION,
    LEGACY_SECTION_INTEGRATION_CACHE_VERSIONS_COLLECTION,
    LEGACY_BACKUP_COUNTERS_COLLECTION,
    "section_revisions",
    "unused_media_cleanup_scans",
)

COLLECTIONS_TO_EXCLUDE = [
    BACKUP_LOG_COLLECTION,
    BACKUP_STATE_COLLECTION,
    *REVISION_HISTORY_COLLECTIONS,
    *OBSOLETE_COLLECTIONS,
]

MIGRATION_SKIP_COLLECTIONS = {
    CHANGELOG_COLLECTION,
    REVISIONS_COLLECTION,
    BACKUP_LOG_COLLECTION,
    BACKUP_STATE_COLLECTION,
    *OBSOLETE_COLLECTIONS,
}

CHUNK_SIZE = 64 * 1024  # 64KB chunks for streaming


async def _get_collections_to_backup(db) -> list[str]:
    """Get all collection names except system and excluded collections."""
    all_collections = await db.list_collection_names()
    return [
        name for name in all_collections
        if not name.startswith("system.") and name not in COLLECTIONS_TO_EXCLUDE
    ]


async def _get_available_app_collections(db) -> list[str]:
    """Get existing app collection names admins may manage directly."""
    return await _get_existing_managed_collection_names(db)


async def _get_existing_managed_collection_names(db) -> list[str]:
    existing_names = set(await db.list_collection_names())
    return [
        collection_name
        for collection_name in MANAGED_COLLECTIONS
        if collection_name in existing_names and not collection_name.startswith("system.")
    ]


async def _build_collection_options(db) -> dict[str, Any]:
    collections: list[dict[str, Any]] = []
    total_documents = 0
    for collection_name in await _get_existing_managed_collection_names(db):
        count = await db[collection_name].count_documents({})
        collections.append(build_collection_summary(collection_name, count))
        total_documents += count

    return {
        "collections": collections,
        "total_documents": total_documents,
    }


def _is_backup_excluded_collection(collection_name: str) -> bool:
    return collection_name in COLLECTIONS_TO_EXCLUDE or collection_name.startswith("system.")


def _db():
    return get_client()[settings.mongo_db]


class SectionRevisionTypeConfig(BaseModel):
    include_design: bool = True
    include_content: bool = True


class RevisionConfigResponse(BaseModel):
    show_global_design_revisions: bool = True
    header: SectionRevisionTypeConfig = Field(default_factory=SectionRevisionTypeConfig)
    section_types: dict[str, SectionRevisionTypeConfig] = Field(default_factory=dict)


class RevisionConfigUpdate(BaseModel):
    show_global_design_revisions: bool | None = None
    header: SectionRevisionTypeConfig | None = None
    section_types: dict[str, SectionRevisionTypeConfig] | None = None


class MigrationOptionsRequest(BaseModel):
    source_db: str
    suggested_target_db: str
    collections: list[dict[str, Any]]
    bucket: dict[str, Any]


class MigrationRunRequest(BaseModel):
    target_db: str = Field(min_length=1)
    collections: dict[str, str] = Field(default_factory=dict)
    bucket_mode: str = "none"  # none | create_new | copy_existing
    target_bucket: str | None = None


class ResetAllStoredDataRequest(BaseModel):
    use_delete_collections: bool = False
    delete_collections: list[str] = Field(default_factory=list)
    exclude_collections: list[str] = Field(default_factory=list)
    delete_bucket_data: bool = False
    bucket_include_prefixes: list[str] = Field(default_factory=list)


class CleanupUnusedMediaRequest(BaseModel):
    asset_ids: list[str] = Field(default_factory=list)
    excluded_asset_ids: list[str] = Field(default_factory=list)
    scan_created_at: datetime | None = None


UNUSED_MEDIA_REFERENCE_EXCLUDED_COLLECTIONS = frozenset(
    {
        ASSETS_COLLECTION,
        BACKUP_LOG_COLLECTION,
        BACKUP_STATE_COLLECTION,
        # Ignore stale cache data from the removed DB-backed unused-media scan flow.
        *OBSOLETE_COLLECTIONS,
    }
)
UNUSED_MEDIA_ASSET_PROJECTION = {
    "_id": 1,
    "filename": 1,
    "content_type": 1,
    "key": 1,
    "url": 1,
    "variants": 1,
}


def _iter_possible_reference_strings(value: Any):
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, ObjectId):
        yield str(value)
        return
    if isinstance(value, dict):
        for nested in value.values():
            yield from _iter_possible_reference_strings(nested)
        return
    if isinstance(value, (list, tuple, set)):
        for nested in value:
            yield from _iter_possible_reference_strings(nested)


def _build_reference_candidates(value: str) -> set[str]:
    raw = str(value or "").strip()
    if not raw:
        return set()

    candidates: set[str] = set()

    def add(candidate: str) -> None:
        normalized = str(candidate or "").strip()
        if not normalized:
            return
        candidates.add(normalized)
        decoded = unquote(normalized)
        if decoded:
            candidates.add(decoded)
        if normalized.startswith("/"):
            candidates.add(normalized.lstrip("/"))
        if decoded.startswith("/"):
            candidates.add(decoded.lstrip("/"))

    add(raw)
    without_fragment = raw.split("#", 1)[0]
    add(without_fragment)
    without_query = without_fragment.split("?", 1)[0]
    add(without_query)

    try:
        parsed = urlsplit(without_query)
    except Exception:
        parsed = None

    if parsed:
        if parsed.scheme and parsed.netloc:
            add(f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path or ''}")
        if parsed.path:
            add(parsed.path)

    return candidates


def _collect_asset_reference_values(asset_doc: dict) -> set[str]:
    values: set[str] = set()
    for field_name in ("url", "key"):
        value = str(asset_doc.get(field_name) or "").strip()
        if value:
            values.add(value)

    variants = asset_doc.get("variants")
    if isinstance(variants, dict):
        for variant in variants.values():
            if not isinstance(variant, dict):
                continue
            for field_name in ("url", "key"):
                value = str(variant.get(field_name) or "").strip()
                if value:
                    values.add(value)

    return values


def _collect_asset_storage_keys(asset_doc: dict) -> list[str]:
    keys: set[str] = set()
    for field_name in ("key",):
        value = str(asset_doc.get(field_name) or "").strip()
        if value:
            keys.add(value)

    variants = asset_doc.get("variants")
    if isinstance(variants, dict):
        for variant in variants.values():
            if not isinstance(variant, dict):
                continue
            value = str(variant.get("key") or "").strip()
            if value:
                keys.add(value)

    return sorted(keys)


async def _find_used_asset_ids(db, *, known_asset_ids: set[str], reference_lookup: dict[str, set[str]]) -> tuple[set[str], list[str], int]:
    used_asset_ids: set[str] = set()
    scanned_collections: list[str] = []
    scanned_documents = 0

    collection_names = sorted(await db.list_collection_names())
    for collection_name in collection_names:
        if collection_name.startswith("system.") or collection_name in UNUSED_MEDIA_REFERENCE_EXCLUDED_COLLECTIONS:
            continue
        scanned_collections.append(collection_name)
        cursor = db[collection_name].find({})
        async for doc in cursor:
            scanned_documents += 1
            for raw_value in _iter_possible_reference_strings(doc):
                for candidate in _build_reference_candidates(raw_value):
                    if candidate in known_asset_ids:
                        used_asset_ids.add(candidate)
                    matched_ids = reference_lookup.get(candidate)
                    if matched_ids:
                        used_asset_ids.update(matched_ids)
                if len(used_asset_ids) >= len(known_asset_ids):
                    break
            if len(used_asset_ids) >= len(known_asset_ids):
                break
        if len(used_asset_ids) >= len(known_asset_ids):
            break

    return used_asset_ids, scanned_collections, scanned_documents


def _build_unused_asset_entry(asset_doc: dict) -> dict[str, Any] | None:
    asset_id = str(asset_doc.get("_id") or "").strip()
    if not asset_id:
        return None

    return {
        "asset_id": asset_id,
        "filename": str(asset_doc.get("filename") or "").strip(),
        "content_type": str(asset_doc.get("content_type") or "").strip(),
        "url": str(asset_doc.get("url") or "").strip(),
        "key": str(asset_doc.get("key") or "").strip(),
    }


def _build_unused_asset_entries(asset_ids: list[str], asset_docs_by_id: dict[str, dict]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for asset_id in asset_ids:
        doc = asset_docs_by_id.get(asset_id)
        if not doc:
            continue
        entry = _build_unused_asset_entry(doc)
        if entry:
            entries.append(entry)

    entries.sort(key=lambda item: ((item.get("filename") or "").lower(), item["asset_id"]))
    return entries


async def _scan_unused_media_assets(db) -> dict[str, Any]:
    assets_coll = db[ASSETS_COLLECTION]

    asset_docs: list[dict] = []
    async for doc in assets_coll.find({}, UNUSED_MEDIA_ASSET_PROJECTION):
        asset_docs.append(doc)

    known_asset_ids: set[str] = set()
    asset_docs_by_id: dict[str, dict] = {}
    reference_lookup: dict[str, set[str]] = {}

    for doc in asset_docs:
        asset_id = str(doc.get("_id") or "").strip()
        if not asset_id:
            continue
        known_asset_ids.add(asset_id)
        asset_docs_by_id[asset_id] = doc
        for value in _collect_asset_reference_values(doc):
            for candidate in _build_reference_candidates(value):
                if not candidate:
                    continue
                existing = reference_lookup.get(candidate)
                if existing is None:
                    reference_lookup[candidate] = {asset_id}
                else:
                    existing.add(asset_id)

    if not known_asset_ids:
        return {
            "known_asset_ids": set(),
            "used_asset_ids": set(),
            "unused_asset_ids": [],
            "unused_assets": [],
            "asset_docs_by_id": {},
            "scanned_collections": [],
            "scanned_documents": 0,
        }

    used_asset_ids, scanned_collections, scanned_documents = await _find_used_asset_ids(
        db,
        known_asset_ids=known_asset_ids,
        reference_lookup=reference_lookup,
    )
    unused_asset_ids = sorted(known_asset_ids - used_asset_ids)

    return {
        "known_asset_ids": known_asset_ids,
        "used_asset_ids": used_asset_ids,
        "unused_asset_ids": unused_asset_ids,
        "unused_assets": _build_unused_asset_entries(unused_asset_ids, asset_docs_by_id),
        "asset_docs_by_id": asset_docs_by_id,
        "scanned_collections": scanned_collections,
        "scanned_documents": scanned_documents,
    }


def _build_unused_media_scan_response(
    scan: dict[str, Any],
) -> dict[str, Any]:
    known_asset_ids = scan.get("known_asset_ids") or set()
    used_asset_ids = scan.get("used_asset_ids") or set()
    unused_asset_ids = scan.get("unused_asset_ids") or []
    scanned_collections = scan.get("scanned_collections") or []
    scanned_documents = int(scan.get("scanned_documents") or 0)
    unused_assets = scan.get("unused_assets") or []

    return {
        "ok": True,
        "scan_created_at": datetime.now(timezone.utc).isoformat(),
        "assets_total": len(known_asset_ids),
        "assets_used": len(used_asset_ids),
        "assets_unused": len(unused_asset_ids),
        "unused_assets": unused_assets,
        "scanned_collections": scanned_collections,
        "scanned_documents": scanned_documents,
    }


def _is_valid_db_name(name: str) -> bool:
    # Keep names predictable and filesystem-safe for tooling around Mongo dumps/backups.
    return bool(re.fullmatch(r"[A-Za-z0-9._-]{1,63}", name))


def _default_migration_mode(collection_name: str) -> str:
    if collection_name in MIGRATION_SKIP_COLLECTIONS:
        return "skip"
    return "copy"


def _is_valid_bucket_name(name: str) -> bool:
    # Basic S3-compatible validation (good enough for MinIO and AWS-style names).
    if len(name) < 3 or len(name) > 63:
        return False
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", name):
        return False
    if ".." in name or ".-" in name or "-." in name:
        return False
    return True


def _s3_bucket_exists(s3_client, bucket_name: str) -> bool:
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except ClientError:
        return False


def _s3_create_bucket(s3_client, bucket_name: str) -> None:
    if _s3_bucket_exists(s3_client, bucket_name):
        raise ValueError(f"Bucket '{bucket_name}' already exists")
    s3_client.create_bucket(Bucket=bucket_name)


def _s3_copy_bucket_contents(s3_client, source_bucket: str, target_bucket: str) -> int:
    if not _s3_bucket_exists(s3_client, source_bucket):
        raise ValueError(f"Source bucket '{source_bucket}' does not exist")
    if _s3_bucket_exists(s3_client, target_bucket):
        raise ValueError(f"Target bucket '{target_bucket}' already exists")

    s3_client.create_bucket(Bucket=target_bucket)

    copied_objects = 0
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=source_bucket):
        for entry in page.get("Contents", []) or []:
            key = entry.get("Key")
            if not key:
                continue
            s3_client.copy_object(
                Bucket=target_bucket,
                Key=key,
                CopySource={"Bucket": source_bucket, "Key": key},
            )
            copied_objects += 1
    return copied_objects


def _normalize_bucket_prefix(value: str) -> str:
    normalized = str(value or "").strip().strip("/")
    return normalized


def _s3_list_top_level_prefixes(s3_client, bucket_name: str) -> list[str]:
    if not _s3_bucket_exists(s3_client, bucket_name):
        raise ValueError(f"Bucket '{bucket_name}' does not exist")

    prefixes: set[str] = set()
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name, Delimiter="/"):
        for entry in page.get("CommonPrefixes", []) or []:
            prefix = _normalize_bucket_prefix(entry.get("Prefix"))
            if prefix:
                prefixes.add(prefix)
    return sorted(prefixes)


def _s3_delete_bucket_contents(
    s3_client,
    bucket_name: str,
    include_prefixes: list[str] | None = None,
) -> int:
    if not _s3_bucket_exists(s3_client, bucket_name):
        raise ValueError(f"Bucket '{bucket_name}' does not exist")

    normalized_prefixes = sorted(
        {
            _normalize_bucket_prefix(prefix)
            for prefix in (include_prefixes or [])
            if _normalize_bucket_prefix(prefix)
        }
    )
    if include_prefixes is not None and not normalized_prefixes:
        raise ValueError("No valid bucket prefixes provided for deletion")

    deleted_objects = 0
    paginator = s3_client.get_paginator("list_objects_v2")
    pages_iterators = (
        [paginator.paginate(Bucket=bucket_name, Prefix=f"{prefix}/") for prefix in normalized_prefixes]
        if normalized_prefixes
        else [paginator.paginate(Bucket=bucket_name)]
    )

    for pages in pages_iterators:
        for page in pages:
            keys = [
                {"Key": key}
                for key in (entry.get("Key") for entry in page.get("Contents", []) or [])
                if key
            ]
            if not keys:
                continue

            result = s3_client.delete_objects(
                Bucket=bucket_name,
                Delete={"Objects": keys, "Quiet": True},
            )
            errors = result.get("Errors") or []
            if errors:
                first = errors[0]
                code = first.get("Code") or "Unknown"
                message = first.get("Message") or "Unknown error"
                raise ValueError(
                    f"Failed to delete objects from bucket '{bucket_name}' ({code}: {message})"
                )
            deleted_objects += len(keys)

    return deleted_objects


def _normalize_requested_collection_names(names: list[str] | None) -> set[str]:
    return {
        str(name or "").strip()
        for name in (names or [])
        if str(name or "").strip() and not str(name or "").strip().startswith("system.")
    }


def _normalize_collection_query_values(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        for part in str(value or "").split(","):
            name = part.strip()
            if not name or name.startswith("system.") or name in seen:
                continue
            seen.add(name)
            normalized.append(name)
    return normalized


def _validate_requested_collections(
    requested_collections: list[str],
    available_collections: list[str],
    *,
    require_any: bool = True,
) -> list[str]:
    available = set(available_collections)
    invalid = [name for name in requested_collections if name not in available]
    if invalid:
        raise HTTPException(
            400,
            f"Unknown or unavailable collection(s): {', '.join(sorted(invalid))}",
        )
    if require_any and not requested_collections:
        raise HTTPException(400, "Select at least one collection")
    return requested_collections


def _resolve_collections_to_delete(
    *,
    existing_collections: list[str],
    manageable_collections: list[str] | None = None,
    payload: ResetAllStoredDataRequest,
) -> tuple[list[str], list[str], list[str], list[str]]:
    existing_collection_set = set(existing_collections)

    if payload.use_delete_collections:
        manageable = existing_collections if manageable_collections is None else manageable_collections
        manageable_collection_set = set(manageable)
        requested_deletions = _normalize_requested_collection_names(payload.delete_collections)
        collections_to_delete = [name for name in manageable if name in requested_deletions]
        deleted_not_found = sorted(name for name in requested_deletions if name not in manageable_collection_set)
        excluded_collections = sorted(name for name in manageable if name not in requested_deletions)
        excluded_not_found: list[str] = []
        return collections_to_delete, excluded_collections, excluded_not_found, deleted_not_found

    # Legacy fallback: delete all except explicit exclusions.
    requested_exclusions = _normalize_requested_collection_names(payload.exclude_collections)
    excluded_collections = sorted(name for name in requested_exclusions if name in existing_collection_set)
    excluded_not_found = sorted(name for name in requested_exclusions if name not in existing_collection_set)
    collections_to_delete = [name for name in existing_collections if name not in requested_exclusions]
    deleted_not_found: list[str] = []
    return collections_to_delete, excluded_collections, excluded_not_found, deleted_not_found


async def _copy_collection_indexes(source_coll, target_coll) -> None:
    index_info = await source_coll.index_information()
    for index_name, info in index_info.items():
        if index_name == "_id_":
            continue

        keys = info.get("key")
        if not keys:
            continue

        kwargs: dict[str, Any] = {"name": index_name}
        if "unique" in info:
            kwargs["unique"] = info["unique"]
        if "sparse" in info:
            kwargs["sparse"] = info["sparse"]
        if "expireAfterSeconds" in info:
            kwargs["expireAfterSeconds"] = info["expireAfterSeconds"]
        if "partialFilterExpression" in info:
            kwargs["partialFilterExpression"] = info["partialFilterExpression"]
        if "collation" in info:
            kwargs["collation"] = info["collation"]

        await target_coll.create_index(keys, **kwargs)


async def _copy_collection_documents(source_coll, target_coll, batch_size: int = 1000) -> int:
    copied_count = 0
    batch: list[dict[str, Any]] = []
    async for doc in source_coll.find({}):
        batch.append(doc)
        if len(batch) >= batch_size:
            await target_coll.insert_many(batch, ordered=False)
            copied_count += len(batch)
            batch = []

    if batch:
        await target_coll.insert_many(batch, ordered=False)
        copied_count += len(batch)

    return copied_count

def get_storage():
    if settings.storage_backend == "ftp":
        return FTPStorage()
    return S3Storage()


@router.get(
    "/revisions/config",
    response_model=RevisionConfigResponse,
    dependencies=[Depends(require_permission("admin:general"))],
)
async def get_revision_config():
    """Get revision feature visibility/configuration."""
    db = _db()
    return await get_or_create_revision_config(db)


@router.patch(
    "/revisions/config",
    response_model=RevisionConfigResponse,
    dependencies=[Depends(require_permission("admin:general"))],
)
async def update_revision_config(payload: RevisionConfigUpdate):
    """Update revision feature visibility/configuration."""
    db = _db()
    current = await get_or_create_revision_config(db)

    merged = {
        **current,
        "section_types": dict(current.get("section_types", {})),
    }

    if payload.show_global_design_revisions is not None:
        merged["show_global_design_revisions"] = bool(payload.show_global_design_revisions)

    if payload.header is not None:
        merged["header"] = normalize_header_revision_options(payload.header.model_dump())

    if payload.section_types is not None:
        merged["section_types"] = {
            section_type: normalize_section_revision_options(options.model_dump())
            for section_type, options in payload.section_types.items()
            if isinstance(section_type, str) and section_type.strip()
        }

    return await save_revision_config(db, merged)


@router.post(
    "/revisions/clear",
    dependencies=[Depends(require_permission("admin:general"))],
)
async def clear_all_revision_history():
    """Clear all revision history and reset revision references on core documents."""
    db = _db()

    revisions_deleted = (await db[REVISIONS_COLLECTION].delete_many({})).deleted_count
    changelog_deleted = (await db[CHANGELOG_COLLECTION].delete_many({})).deleted_count

    sections_reset = (
        await db[SECTIONS_COLLECTION].update_many({}, {"$set": {"revision_id": None}})
    ).modified_count
    headers_reset = (
        await db[HEADERS_COLLECTION].update_many({}, {"$set": {"revision_id": None}})
    ).modified_count
    design_reset = (
        await db[DESIGN_CONFIG_COLLECTION].update_many({}, {"$set": {"revision_id": None}})
    ).modified_count

    return {
        "ok": True,
        "revisions_deleted": revisions_deleted,
        "changelog_deleted": changelog_deleted,
        "sections_reset": sections_reset,
        "headers_reset": headers_reset,
        "design_config_reset": design_reset,
        "design_settings_reset": design_reset,
    }


@router.post(
    "/reset/all",
    dependencies=[Depends(require_permission("admin:general"))],
)
async def reset_all_stored_data(
    payload: ResetAllStoredDataRequest = Body(default_factory=ResetAllStoredDataRequest),
):
    """
    Delete selected persisted collections in the active DB and run initialization
    to recreate required collections/indexes plus default seed data.
    """
    mongo_client = get_client()
    db_name = settings.mongo_db
    db = mongo_client[db_name]

    delete_bucket_data = bool(payload.delete_bucket_data)
    if delete_bucket_data and settings.storage_backend != "s3":
        raise HTTPException(400, "Bucket cleanup is only supported for S3/MinIO storage.")

    existing_collections = [
        name
        for name in await db.list_collection_names()
        if not name.startswith("system.")
    ]
    manageable_collections = await _get_available_app_collections(db)

    (
        collections_to_delete,
        excluded_collections,
        excluded_not_found,
        deleted_not_found,
    ) = _resolve_collections_to_delete(
        existing_collections=existing_collections,
        manageable_collections=manageable_collections,
        payload=payload,
    )

    dropped_documents = 0
    for collection_name in collections_to_delete:
        try:
            dropped_documents += await db[collection_name].count_documents({})
        except Exception:
            # Best-effort count only; reset still proceeds.
            continue

    for collection_name in collections_to_delete:
        await db.drop_collection(collection_name)

    reset_db = db
    await ensure_db_collections_and_indexes(reset_db)
    if PAGES_COLLECTION not in excluded_collections:
        await seed_default_pages(reset_db)

    initialized_collections = sorted(
        name
        for name in await reset_db.list_collection_names()
        if not name.startswith("system.")
    )

    bucket_cleanup = {
        "requested": delete_bucket_data,
        "performed": False,
        "bucket": settings.s3_bucket if settings.storage_backend == "s3" else None,
        "deleted_objects": 0,
        "included_prefixes": [],
        "error": None,
    }
    if delete_bucket_data:
        requested_prefixes = sorted(
            {
                _normalize_bucket_prefix(prefix)
                for prefix in (payload.bucket_include_prefixes or [])
                if _normalize_bucket_prefix(prefix)
            }
        )
        if not requested_prefixes:
            raise HTTPException(
                400,
                "Select at least one top-level bucket directory to delete.",
            )

        storage = get_storage()
        if not isinstance(storage, S3Storage):
            raise HTTPException(400, "Configured storage backend does not support bucket cleanup.")
        try:
            deleted_objects = await asyncio.to_thread(
                _s3_delete_bucket_contents,
                storage.s3,
                storage.bucket,
                requested_prefixes,
            )
        except ValueError as e:
            bucket_cleanup["error"] = str(e)
        else:
            bucket_cleanup["performed"] = True
            bucket_cleanup["deleted_objects"] = deleted_objects
            bucket_cleanup["included_prefixes"] = requested_prefixes

    return {
        "ok": True,
        "database": db_name,
        "dropped_collections": len(collections_to_delete),
        "dropped_documents": dropped_documents,
        "deleted_collections": sorted(collections_to_delete),
        "deleted_not_found": deleted_not_found,
        "excluded_collections": excluded_collections,
        "excluded_not_found": excluded_not_found,
        "initialized_collections": initialized_collections,
        "bucket_cleanup": bucket_cleanup,
    }


@router.post(
    "/reset/media/find-unused",
    dependencies=[Depends(require_permission("admin:general"))],
)
async def find_unused_media_assets():
    """
    Find unreferenced media assets and return a full file list.

    The admin UI stores the returned asset list in browser session storage and
    sends the selected IDs back to the cleanup endpoint.
    """
    db = _db()
    scan = await _scan_unused_media_assets(db)
    return _build_unused_media_scan_response(scan)


@router.post(
    "/reset/media/cleanup-unused",
    dependencies=[Depends(require_permission("admin:general"))],
)
async def cleanup_unused_media_assets(payload: CleanupUnusedMediaRequest):
    """
    Delete unreferenced media assets from MongoDB and object storage.

    The client supplies asset IDs from its session-stored find result. The
    backend rescans immediately and only deletes assets that are still unused.
    """
    db = _db()
    requested_asset_ids = {
        str(asset_id or "").strip()
        for asset_id in (payload.asset_ids or [])
        if str(asset_id or "").strip()
    }
    scan_created_at = payload.scan_created_at or datetime.now(timezone.utc)
    if scan_created_at.tzinfo is None:
        scan_created_at = scan_created_at.replace(tzinfo=timezone.utc)

    excluded_asset_ids = {
        str(asset_id or "").strip()
        for asset_id in (payload.excluded_asset_ids or [])
        if str(asset_id or "").strip()
    }
    excluded_by_user_asset_ids = sorted(requested_asset_ids & excluded_asset_ids)
    requested_cleanup_asset_ids = sorted(requested_asset_ids - excluded_asset_ids)

    if not requested_asset_ids:
        return {
            "ok": True,
            "scan_created_at": scan_created_at.isoformat(),
            "assets_detected_by_scan": 0,
            "assets_requested_for_cleanup": 0,
            "assets_total": 0,
            "assets_used": 0,
            "assets_unused_current": 0,
            "deleted_assets": 0,
            "deleted_storage_objects": 0,
            "storage_delete_failures": 0,
            "storage_delete_errors": [],
            "excluded_assets_count": 0,
            "excluded_assets": [],
            "skipped_now_used_assets": [],
            "scanned_collections": [],
            "scanned_documents": 0,
        }

    current_scan = await _scan_unused_media_assets(db)
    current_unused_asset_ids = set(current_scan.get("unused_asset_ids") or [])
    current_asset_docs_by_id = current_scan.get("asset_docs_by_id") or {}
    deletable_asset_ids = sorted(set(requested_cleanup_asset_ids) & current_unused_asset_ids)
    skipped_now_used_asset_ids = sorted(set(requested_cleanup_asset_ids) - current_unused_asset_ids)

    assets_coll = db[ASSETS_COLLECTION]
    storage = get_storage()
    deleted_storage_objects = 0
    storage_delete_errors: list[dict[str, str]] = []
    mongo_object_ids_to_delete: list[ObjectId] = []

    for asset_id in deletable_asset_ids:
        doc = current_asset_docs_by_id.get(asset_id)
        if not doc:
            continue
        mongo_id = doc.get("_id")
        if isinstance(mongo_id, ObjectId):
            mongo_object_ids_to_delete.append(mongo_id)

        for key in _collect_asset_storage_keys(doc):
            try:
                await storage.delete(key=key)
                deleted_storage_objects += 1
            except Exception as e:
                storage_delete_errors.append(
                    {
                        "asset_id": asset_id,
                        "key": key,
                        "error": str(e),
                    }
                )

    deleted_assets = 0
    if mongo_object_ids_to_delete:
        delete_result = await assets_coll.delete_many({"_id": {"$in": mongo_object_ids_to_delete}})
        deleted_assets = int(delete_result.deleted_count or 0)

    return {
        "ok": True,
        "scan_created_at": scan_created_at.isoformat(),
        "assets_detected_by_scan": len(requested_asset_ids),
        "assets_requested_for_cleanup": len(requested_cleanup_asset_ids),
        "assets_total": len(current_scan.get("known_asset_ids") or set()),
        "assets_used": len(current_scan.get("used_asset_ids") or set()),
        "assets_unused_current": len(current_unused_asset_ids),
        "deleted_assets": deleted_assets,
        "deleted_storage_objects": deleted_storage_objects,
        "storage_delete_failures": len(storage_delete_errors),
        "storage_delete_errors": storage_delete_errors[:50],
        "excluded_assets_count": len(excluded_by_user_asset_ids),
        "excluded_assets": _build_unused_asset_entries(
            excluded_by_user_asset_ids,
            current_asset_docs_by_id,
        ),
        "skipped_now_used_assets": _build_unused_asset_entries(
            skipped_now_used_asset_ids,
            current_asset_docs_by_id,
        ),
        "scanned_collections": current_scan.get("scanned_collections") or [],
        "scanned_documents": int(current_scan.get("scanned_documents") or 0),
    }


@router.post(
    "/reset/media/remove-unused",
    dependencies=[Depends(require_permission("admin:general"))],
)
async def remove_unused_media_assets(
    dry_run: bool = Query(False, description="Deprecated: use /reset/media/find-unused and /reset/media/cleanup-unused"),
):
    """
    Backward-compatible wrapper.

    dry_run=true => find-unused
    dry_run=false is no longer supported because cleanup now uses a browser
    session-stored find result instead of a DB-backed scan collection.
    """
    if dry_run:
        result = await find_unused_media_assets()
        result["dry_run"] = True
        result["deleted_assets"] = 0
        result["deleted_storage_objects"] = 0
        result["storage_delete_failures"] = 0
        result["storage_delete_errors"] = []
        return result

    raise HTTPException(
        400,
        "Deprecated cleanup endpoint no longer supports cleanup. Use /backup/reset/media/find-unused, "
        "store the returned result in browser session storage, then POST selected asset_ids to "
        "/backup/reset/media/cleanup-unused.",
    )


def _serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = {"$oid": str(value)}
        elif isinstance(value, datetime):
            result[key] = {"$date": value.isoformat()}
        elif isinstance(value, dict):
            result[key] = _serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [_serialize_doc(v) if isinstance(v, dict) else v for v in value]
        else:
            result[key] = value
    return result


def _deserialize_doc(doc: dict) -> dict:
    """Convert JSON dict back to MongoDB-compatible document."""
    result = {}
    for key, value in doc.items():
        if isinstance(value, dict):
            if "$oid" in value:
                result[key] = ObjectId(value["$oid"])
            elif "$date" in value:
                result[key] = datetime.fromisoformat(value["$date"])
            else:
                result[key] = _deserialize_doc(value)
        elif isinstance(value, list):
            result[key] = [_deserialize_doc(v) if isinstance(v, dict) else v for v in value]
        else:
            result[key] = value
    return result


@dataclass
class ImportArchive:
    file_name: str
    temp_path: str
    manifest: dict[str, Any]
    backup_type: str
    created_at: datetime | None
    since: datetime | None
    incremental_counter: int | None


@dataclass
class CollectionImportPayload:
    file_name: str
    file_kind: str
    collection_name: str
    source_collection: str | None
    docs: list[dict[str, Any]]
    warnings: list[str]


def _parse_manifest_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _extract_incremental_counter(file_name: str) -> int | None:
    normalized_name = os.path.basename(file_name or "").strip()

    # New naming scheme: <slug>_<counter>_<YYYYMMDD>_<HHMMSS>.zip
    new_format = re.search(r"^[A-Za-z0-9._-]+_(\d{4})_\d{8}_\d{6}\.zip$", normalized_name)
    if new_format:
        try:
            return int(new_format.group(1))
        except ValueError:
            return None

    return None


def _sort_import_archives(archives: list[ImportArchive]) -> list[ImportArchive]:
    def datetime_sort_value(value: datetime | None) -> float:
        if not value:
            return float("inf")
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.timestamp()

    def sort_key(archive: ImportArchive):
        is_incremental = archive.backup_type == "incremental"
        counter = archive.incremental_counter if archive.incremental_counter is not None else 10**9
        timeline = datetime_sort_value(archive.since or archive.created_at)
        return (1 if is_incremental else 0, counter, timeline, archive.file_name.lower())

    return sorted(archives, key=sort_key)


def _build_backup_filename(counter: int, now: datetime | None = None) -> str:
    timestamp = now or datetime.utcnow()
    return f"{settings.site_slug}_{counter:04d}_{timestamp.strftime('%Y%m%d_%H%M%S')}.zip"


def _prevalidate_import_archive(archive: ImportArchive) -> None:
    """Validate archive structure and payload before any data is applied."""
    try:
        with zipfile.ZipFile(archive.temp_path, "r") as zf:
            all_files = set(zf.namelist())
            collections = archive.manifest.get("collections", [])
            if not isinstance(collections, list):
                raise HTTPException(400, f"Invalid backup '{archive.file_name}': manifest.collections must be a list")

            for coll_info in collections:
                if not isinstance(coll_info, dict):
                    raise HTTPException(400, f"Invalid backup '{archive.file_name}': collection entries must be objects")

                coll_name = coll_info.get("name")
                if not isinstance(coll_name, str) or not coll_name.strip():
                    raise HTTPException(400, f"Invalid backup '{archive.file_name}': collection name is missing")
                if _is_backup_excluded_collection(coll_name):
                    continue

                json_path = f"data/{coll_name}.json"
                if json_path not in all_files:
                    raise HTTPException(400, f"Invalid backup '{archive.file_name}': missing {json_path}")

                try:
                    docs_json = json.loads(zf.read(json_path))
                except json.JSONDecodeError:
                    raise HTTPException(400, f"Invalid backup '{archive.file_name}': {json_path} is not valid JSON")

                if not isinstance(docs_json, list):
                    raise HTTPException(400, f"Invalid backup '{archive.file_name}': {json_path} must contain a JSON array")

                for idx, doc in enumerate(docs_json):
                    if not isinstance(doc, dict):
                        raise HTTPException(
                            400,
                            f"Invalid backup '{archive.file_name}': {json_path} entry #{idx + 1} must be an object",
                        )
                    try:
                        _deserialize_doc(doc)
                    except Exception:
                        raise HTTPException(
                            400,
                            f"Invalid backup '{archive.file_name}': {json_path} entry #{idx + 1} has unsupported value format",
                        )

            has_media_manifest = "media/manifest.json" in all_files

            if has_media_manifest:
                try:
                    media_manifest = json.loads(zf.read("media/manifest.json"))
                except json.JSONDecodeError:
                    raise HTTPException(
                        400,
                        f"Invalid backup '{archive.file_name}': media/manifest.json is not valid JSON",
                    )

                if not isinstance(media_manifest, list):
                    raise HTTPException(
                        400,
                        f"Invalid backup '{archive.file_name}': media/manifest.json must contain a JSON array",
                    )

                for idx, media_item in enumerate(media_manifest):
                    if not isinstance(media_item, dict):
                        raise HTTPException(
                            400,
                            f"Invalid backup '{archive.file_name}': media entry #{idx + 1} must be an object",
                        )
                    key = media_item.get("key")
                    if not isinstance(key, str) or not key.strip():
                        raise HTTPException(
                            400,
                            f"Invalid backup '{archive.file_name}': media entry #{idx + 1} is missing key",
                        )
                    if f"media/{key}" not in all_files:
                        raise HTTPException(
                            400,
                            f"Invalid backup '{archive.file_name}': referenced media file media/{key} not found",
                        )
    except zipfile.BadZipFile:
        raise HTTPException(400, f"Invalid ZIP file: {archive.file_name}")


class StreamingZipBuffer:
    """Unseekable writer used by zipfile so responses can start immediately."""

    def __init__(self):
        self._chunks: list[bytes] = []
        self._pos = 0

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def tell(self) -> int:
        return self._pos

    def write(self, data: bytes) -> int:
        if not data:
            return 0
        chunk = bytes(data)
        self._chunks.append(chunk)
        self._pos += len(chunk)
        return len(chunk)

    def flush(self) -> None:
        return None

    def drain(self) -> list[bytes]:
        chunks = self._chunks
        self._chunks = []
        return chunks


async def _iter_storage_object_chunks(storage, key: str) -> AsyncGenerator[bytes, None]:
    """Yield storage object bytes without forcing S3 objects into memory."""
    if isinstance(storage, S3Storage):
        try:
            response = await asyncio.to_thread(
                storage.s3.get_object,
                Bucket=storage.bucket,
                Key=key,
            )
        except Exception:
            return

        body = response.get("Body")
        if body is None:
            return
        try:
            while True:
                chunk = await asyncio.to_thread(body.read, CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                await asyncio.to_thread(close)
        return

    data = await storage.get(key=key)
    if not data:
        return
    for index in range(0, len(data), CHUNK_SIZE):
        yield data[index:index + CHUNK_SIZE]


async def _write_json_collection_to_zip(
    zf: zipfile.ZipFile,
    zip_buffer: StreamingZipBuffer,
    db,
    coll_name: str,
    query: dict,
    backup_manifest: dict,
    include_empty: bool = False,
) -> AsyncGenerator[bytes, None]:
    coll = db[coll_name]
    entry = None
    count = 0

    try:
        async for doc in coll.find(query).batch_size(500):
            if entry is None:
                entry = zf.open(f"data/{coll_name}.json", "w", force_zip64=True)
                entry.write(b"[")
            else:
                entry.write(b",")

            serialized = json.dumps(_serialize_doc(doc), ensure_ascii=False).encode("utf-8")
            entry.write(serialized)
            count += 1
            for chunk in zip_buffer.drain():
                yield chunk

        if entry is not None:
            entry.write(b"]")
    finally:
        if entry is not None:
            entry.close()

    for chunk in zip_buffer.drain():
        yield chunk

    if count == 0 and include_empty:
        zf.writestr(f"data/{coll_name}.json", b"[]")
        for chunk in zip_buffer.drain():
            yield chunk

    if count or include_empty:
        backup_manifest["collections"].append({
            "name": coll_name,
            "count": count,
        })


async def _iter_backup_zip(
    db,
    storage,
    include_media: bool,
    since: datetime | None = None,
) -> AsyncGenerator[bytes, None]:
    """Stream a backup ZIP while it is generated to avoid gateway idle timeouts."""
    collections_to_backup = await _get_collections_to_backup(db)
    
    backup_manifest = {
        "version": "1.0",
        "created_at": datetime.utcnow().isoformat(),
        "backup_type": "incremental" if since else "full",
        "since": since.isoformat() if since else None,
        "collections": [],
        "media_included": include_media,
    }
    
    zip_buffer = StreamingZipBuffer()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for coll_name in collections_to_backup:
            # Build query - for incremental, filter by updated_at or created_at
            query = {}
            if since:
                query["$or"] = [
                    {"updated_at": {"$gte": since}},
                    {"created_at": {"$gte": since}},
                ]

            async for chunk in _write_json_collection_to_zip(
                zf,
                zip_buffer,
                db,
                coll_name,
                query,
                backup_manifest,
            ):
                yield chunk

            for chunk in zip_buffer.drain():
                yield chunk
        
        if include_media:
            assets_coll = db[ASSETS_COLLECTION]
            
            # Build query for assets
            asset_query = {}
            if since:
                asset_query["created_at"] = {"$gte": since}
            
            media_manifest = []
            
            # Process assets one at a time to minimize memory usage
            async for asset in assets_coll.find(asset_query):
                asset_id = str(asset["_id"])
                keys_to_download = []
                
                if asset.get("key"):
                    keys_to_download.append(("original", asset["key"]))
                variants = asset.get("variants")
                if isinstance(variants, dict):
                    for variant_id, variant_data in variants.items():
                        if not isinstance(variant_data, dict):
                            continue
                        variant_key = variant_data.get("key")
                        if variant_key:
                            keys_to_download.append((f"variant:{variant_id}", variant_key))
                
                for variant, key in keys_to_download:
                    try:
                        wrote_file = False
                        media_entry = None
                        try:
                            async for data in _iter_storage_object_chunks(storage, key):
                                if not data:
                                    continue
                                if media_entry is None:
                                    media_entry = zf.open(f"media/{key}", "w", force_zip64=True)
                                media_entry.write(data)
                                wrote_file = True
                                for chunk in zip_buffer.drain():
                                    yield chunk
                        finally:
                            if media_entry is not None:
                                media_entry.close()
                        for chunk in zip_buffer.drain():
                            yield chunk
                        if wrote_file:
                            media_manifest.append({
                                "asset_id": asset_id,
                                "variant": variant,
                                "key": key,
                                "content_type": asset.get("content_type", "application/octet-stream"),
                            })
                    except Exception:
                        pass
            
            if media_manifest:
                zf.writestr("media/manifest.json", json.dumps(media_manifest))
                backup_manifest["media_count"] = len(media_manifest)
                for chunk in zip_buffer.drain():
                    yield chunk
        
        zf.writestr("manifest.json", json.dumps(backup_manifest, indent=2))
        for chunk in zip_buffer.drain():
            yield chunk

    for chunk in zip_buffer.drain():
        yield chunk


async def _write_assets_media_to_zip(
    zf: zipfile.ZipFile,
    zip_buffer: StreamingZipBuffer,
    storage,
    assets_cursor,
    backup_manifest: dict[str, Any],
) -> AsyncGenerator[bytes, None]:
    media_manifest = []

    async for asset in assets_cursor:
        asset_id = str(asset["_id"])
        keys_to_download = []

        if asset.get("key"):
            keys_to_download.append(("original", asset["key"]))
        variants = asset.get("variants")
        if isinstance(variants, dict):
            for variant_id, variant_data in variants.items():
                if not isinstance(variant_data, dict):
                    continue
                variant_key = variant_data.get("key")
                if variant_key:
                    keys_to_download.append((f"variant:{variant_id}", variant_key))

        for variant, key in keys_to_download:
            try:
                wrote_file = False
                media_entry = None
                try:
                    async for data in _iter_storage_object_chunks(storage, key):
                        if not data:
                            continue
                        if media_entry is None:
                            media_entry = zf.open(f"media/{key}", "w", force_zip64=True)
                        media_entry.write(data)
                        wrote_file = True
                        for chunk in zip_buffer.drain():
                            yield chunk
                finally:
                    if media_entry is not None:
                        media_entry.close()
                for chunk in zip_buffer.drain():
                    yield chunk
                if wrote_file:
                    media_manifest.append({
                        "asset_id": asset_id,
                        "variant": variant,
                        "key": key,
                        "content_type": asset.get("content_type", "application/octet-stream"),
                    })
            except Exception:
                pass

    if media_manifest:
        zf.writestr("media/manifest.json", json.dumps(media_manifest))
        backup_manifest["media_count"] = len(media_manifest)
        for chunk in zip_buffer.drain():
            yield chunk


async def _iter_collections_zip(
    db,
    storage,
    collection_names: list[str],
    include_media: bool,
) -> AsyncGenerator[bytes, None]:
    """Stream selected collections in the same archive shape as backups."""
    media_requested = include_media and "assets" in collection_names
    backup_manifest = {
        "version": "1.0",
        "created_at": datetime.utcnow().isoformat(),
        "backup_type": "collections",
        "since": None,
        "collections": [],
        "media_included": media_requested,
    }

    zip_buffer = StreamingZipBuffer()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for coll_name in collection_names:
            async for chunk in _write_json_collection_to_zip(
                zf,
                zip_buffer,
                db,
                coll_name,
                {},
                backup_manifest,
                include_empty=True,
            ):
                yield chunk

            for chunk in zip_buffer.drain():
                yield chunk

        if media_requested:
            async for chunk in _write_assets_media_to_zip(
                zf,
                zip_buffer,
                storage,
                db[ASSETS_COLLECTION].find({}),
                backup_manifest,
            ):
                yield chunk

        zf.writestr("manifest.json", json.dumps(backup_manifest, indent=2))
        for chunk in zip_buffer.drain():
            yield chunk

    for chunk in zip_buffer.drain():
        yield chunk


def _deserialize_import_collection_docs(payload: Any, source_label: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = [payload]
    else:
        raise HTTPException(400, f"{source_label} must contain a JSON object or array of objects")

    docs: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise HTTPException(400, f"{source_label} entry #{index + 1} must be an object")
        try:
            docs.append(_deserialize_doc(row))
        except Exception:
            raise HTTPException(
                400,
                f"{source_label} entry #{index + 1} has unsupported value format",
            )
    return docs


async def _apply_collection_import_docs(
    db,
    collection_name: str,
    docs: list[dict[str, Any]],
    mode: str,
    replaced_collections: set[str],
) -> int:
    coll = db[collection_name]
    if mode == "replace" and collection_name not in replaced_collections:
        await coll.delete_many({})
        replaced_collections.add(collection_name)

    if not docs:
        return 0

    if mode == "replace":
        await coll.insert_many(docs)
        return len(docs)

    imported_count = 0
    for doc in docs:
        doc_id = doc.get("_id")
        if doc_id is not None:
            await coll.replace_one({"_id": doc_id}, doc, upsert=True)
        else:
            await coll.insert_one(doc)
        imported_count += 1
    return imported_count


def _normalize_target_collection_name(target_collection: str | None) -> str | None:
    normalized = str(target_collection or "").strip()
    if not normalized:
        return None
    if normalized.startswith("system."):
        raise HTTPException(400, "System collections cannot be imported here")
    return normalized


def _infer_collection_from_json_filename(file_name: str, available_collections: list[str]) -> str | None:
    stem = os.path.splitext(os.path.basename(file_name or ""))[0].strip()
    if stem and stem in set(available_collections):
        return stem
    return None


def _collection_import_id_key(value: Any) -> tuple[str, Any]:
    try:
        hash(value)
        return ("value", value)
    except TypeError:
        try:
            serialized = _serialize_doc({"_id": value}).get("_id")
            return ("json", json.dumps(serialized, sort_keys=True, default=str))
        except Exception:
            return ("repr", repr(value))


async def _write_upload_to_temp(uploaded: UploadFile, suffix: str) -> str:
    temp_fd, temp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(temp_fd, "wb") as temp_file:
            while chunk := await uploaded.read(CHUNK_SIZE):
                temp_file.write(chunk)
    except Exception:
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        raise
    return temp_path


async def _load_collection_import_json(
    uploaded: UploadFile,
    available_collections: list[str],
    target_collection: str | None,
) -> CollectionImportPayload:
    file_name = uploaded.filename or "collection.json"
    target_name = (
        _normalize_target_collection_name(target_collection)
        or _infer_collection_from_json_filename(file_name, available_collections)
    )
    if not target_name:
        raise HTTPException(
            400,
            "Select a target collection for raw JSON import or name the file after a known collection.",
        )
    _validate_requested_collections([target_name], available_collections)

    try:
        payload = json.loads((await uploaded.read()).decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(400, f"JSON file '{file_name}' must be UTF-8")
    except json.JSONDecodeError:
        raise HTTPException(400, f"JSON file '{file_name}' is not valid JSON")

    return CollectionImportPayload(
        file_name=file_name,
        file_kind="json",
        collection_name=target_name,
        source_collection=_infer_collection_from_json_filename(file_name, available_collections),
        docs=_deserialize_import_collection_docs(payload, file_name),
        warnings=[],
    )


def _load_collection_import_archive(
    file_name: str,
    temp_path: str,
    available_collections: list[str],
    target_collection: str | None,
) -> CollectionImportPayload:
    target_name = _normalize_target_collection_name(target_collection)
    try:
        with zipfile.ZipFile(temp_path, "r") as zf:
            all_files = set(zf.namelist())
            if "manifest.json" not in all_files:
                raise HTTPException(400, f"Invalid collection archive '{file_name}': missing manifest.json")
            try:
                manifest = json.loads(zf.read("manifest.json"))
            except json.JSONDecodeError:
                raise HTTPException(400, f"Invalid manifest.json in '{file_name}'")

            if not isinstance(manifest, dict):
                raise HTTPException(400, f"Invalid collection archive '{file_name}': manifest.json must be an object")
            collections = manifest.get("collections", [])
            if not isinstance(collections, list):
                raise HTTPException(400, f"Invalid collection archive '{file_name}': manifest.collections must be a list")

            collection_names: list[str] = []
            for coll_info in collections:
                if not isinstance(coll_info, dict):
                    raise HTTPException(400, f"Invalid collection archive '{file_name}': collection entries must be objects")
                coll_name = str(coll_info.get("name") or "").strip()
                if not coll_name:
                    raise HTTPException(400, f"Invalid collection archive '{file_name}': collection name is missing")
                if coll_name.startswith("system."):
                    raise HTTPException(400, f"Invalid collection archive '{file_name}': system collections cannot be imported here")
                collection_names.append(coll_name)

            collection_names = sorted(set(collection_names))
            if not collection_names:
                raise HTTPException(400, f"Collection archive '{file_name}' contains no importable collections")
            if len(collection_names) > 1:
                raise HTTPException(
                    400,
                    f"Collection archive '{file_name}' contains multiple collections. Use full backup import for multi-collection archives.",
                )

            source_collection = collection_names[0]
            if target_name and target_name != source_collection:
                raise HTTPException(
                    400,
                    f"Selected target collection '{target_name}' does not match archive collection '{source_collection}'.",
                )
            collection_name = target_name or source_collection
            _validate_requested_collections([collection_name], available_collections)

            json_path = f"data/{source_collection}.json"
            if json_path not in all_files:
                raise HTTPException(400, f"Invalid collection archive '{file_name}': missing {json_path}")

            try:
                docs_json = json.loads(zf.read(json_path))
            except json.JSONDecodeError:
                raise HTTPException(400, f"Invalid collection archive '{file_name}': {json_path} is not valid JSON")
            if not isinstance(docs_json, list):
                raise HTTPException(400, f"Invalid collection archive '{file_name}': {json_path} must contain a JSON array")

            return CollectionImportPayload(
                file_name=file_name,
                file_kind="zip",
                collection_name=collection_name,
                source_collection=source_collection,
                docs=_deserialize_import_collection_docs(docs_json, f"{file_name}:{json_path}"),
                warnings=[],
            )
    except zipfile.BadZipFile:
        raise HTTPException(400, f"Invalid ZIP file: {file_name}")


async def _load_collection_import_payload(
    uploaded: UploadFile,
    available_collections: list[str],
    target_collection: str | None,
) -> CollectionImportPayload:
    file_name = uploaded.filename or "<unnamed>"
    lower_name = file_name.lower()
    content_type = str(uploaded.content_type or "").lower()
    is_zip = lower_name.endswith(".zip") or content_type in {"application/zip", "application/x-zip-compressed"}
    is_json = lower_name.endswith(".json") or content_type == "application/json"

    if is_zip == is_json:
        raise HTTPException(400, "File must be either a ZIP archive or a raw JSON file")

    if is_json:
        return await _load_collection_import_json(uploaded, available_collections, target_collection)

    temp_path = await _write_upload_to_temp(uploaded, ".zip")
    try:
        return _load_collection_import_archive(file_name, temp_path, available_collections, target_collection)
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


async def _build_collection_import_dry_run(db, payload: CollectionImportPayload) -> dict[str, Any]:
    docs_with_id: list[Any] = []
    doc_id_keys: list[tuple[str, Any]] = []
    unique_ids: list[Any] = []
    unique_id_keys: set[tuple[str, Any]] = set()

    for doc in payload.docs:
        if "_id" not in doc or doc.get("_id") is None:
            continue
        doc_id = doc["_id"]
        doc_id_key = _collection_import_id_key(doc_id)
        docs_with_id.append(doc_id)
        doc_id_keys.append(doc_id_key)
        if doc_id_key not in unique_id_keys:
            unique_id_keys.add(doc_id_key)
            unique_ids.append(doc_id)

    existing_id_keys: set[tuple[str, Any]] = set()
    coll = db[payload.collection_name]
    for start in range(0, len(unique_ids), 500):
        batch = unique_ids[start:start + 500]
        if not batch:
            continue
        async for existing_doc in coll.find({"_id": {"$in": batch}}, {"_id": 1}):
            if "_id" in existing_doc:
                existing_id_keys.add(_collection_import_id_key(existing_doc["_id"]))

    existing_documents = sum(1 for doc_id_key in doc_id_keys if doc_id_key in existing_id_keys)
    document_count = len(payload.docs)
    documents_with_id = len(docs_with_id)
    documents_without_id = document_count - documents_with_id
    duplicate_ids_in_file = documents_with_id - len(unique_id_keys)
    warnings = list(payload.warnings)

    if documents_without_id:
        warnings.append(
            f"{documents_without_id} document{'s' if documents_without_id != 1 else ''} without _id will be inserted as new."
        )
    if duplicate_ids_in_file:
        warnings.append(
            f"{duplicate_ids_in_file} duplicate _id entr{'ies' if duplicate_ids_in_file != 1 else 'y'} found in the upload."
        )

    return {
        "ok": True,
        "dry_run": True,
        "file_name": payload.file_name,
        "file_kind": payload.file_kind,
        "collection": payload.collection_name,
        "target_collection": payload.collection_name,
        "detected_collection": payload.source_collection,
        "known_collection": True,
        "document_count": document_count,
        "known_documents": existing_documents,
        "existing_documents": existing_documents,
        "new_documents": document_count - existing_documents,
        "documents_with_id": documents_with_id,
        "documents_without_id": documents_without_id,
        "duplicate_ids_in_file": duplicate_ids_in_file,
        "warnings": warnings,
        "errors": [],
    }


@router.get("/collections/options", dependencies=[Depends(require_permission("admin:general"))])
async def get_collection_options():
    """Return existing app-managed collections available for admin database actions."""
    return await _build_collection_options(_db())


@router.get("/collections/export", dependencies=[Depends(require_permission("admin:general"))])
async def export_collections(
    collections: list[str] = Query(default=[]),
    include_media: bool = False,
):
    """Export selected MongoDB collections as a backup-shaped ZIP archive."""
    db = _db()
    available_collections = await _get_available_app_collections(db)
    requested_collections = _validate_requested_collections(
        _normalize_collection_query_values(collections),
        available_collections,
    )
    storage = get_storage()
    filename = f"{settings.site_slug}_collections_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"

    return StreamingResponse(
        _iter_collections_zip(db, storage, requested_collections, include_media),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )


def _get_single_collection_upload(file: UploadFile | None, files: list[UploadFile] | None) -> tuple[UploadFile, list[UploadFile]]:
    upload_files: list[UploadFile] = []
    if files:
        upload_files.extend(files)
    if file:
        upload_files.append(file)
    if not upload_files:
        raise HTTPException(400, "Provide one ZIP archive or JSON file")
    if len(upload_files) != 1:
        raise HTTPException(400, "Collection import supports exactly one file")
    return upload_files[0], upload_files


@router.post("/collections/import/dry-run", dependencies=[Depends(require_permission("admin:general"))])
async def dry_run_import_collection(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    target_collection: str | None = Query(None),
):
    """Preview a single collection import without changing stored data."""
    uploaded, upload_files = _get_single_collection_upload(file, files)
    try:
        db = _db()
        available_collections = await _get_available_app_collections(db)
        payload = await _load_collection_import_payload(uploaded, available_collections, target_collection)
        return await _build_collection_import_dry_run(db, payload)
    finally:
        for uploaded_file in upload_files:
            try:
                await uploaded_file.close()
            except Exception:
                pass


@router.post("/collections/import", dependencies=[Depends(require_permission("admin:general"))])
async def import_collections(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    mode: str = Query("merge"),
    target_collection: str | None = Query(None),
):
    """Import one collection from a backup-shaped ZIP or raw JSON file."""
    normalized_mode = str(mode or "merge").strip().lower()
    if normalized_mode not in {"merge", "replace"}:
        raise HTTPException(400, "mode must be 'merge' or 'replace'")

    uploaded, upload_files = _get_single_collection_upload(file, files)
    db = _db()
    available_collections = await _get_available_app_collections(db)
    replaced_collections: set[str] = set()

    try:
        payload = await _load_collection_import_payload(uploaded, available_collections, target_collection)
        dry_run_result = await _build_collection_import_dry_run(db, payload)
        imported_count = await _apply_collection_import_docs(
            db,
            payload.collection_name,
            payload.docs,
            normalized_mode,
            replaced_collections,
        )

        await ensure_db_collections_and_indexes(db)

        return {
            "status": "success",
            "mode": normalized_mode,
            "file_name": payload.file_name,
            "file_kind": payload.file_kind,
            "target_collection": payload.collection_name,
            "detected_collection": payload.source_collection,
            "collections_imported": [
                {"name": payload.collection_name, "count": imported_count}
            ],
            "collections_skipped": [],
            "documents_imported": imported_count,
            "dry_run": dry_run_result,
            "warnings": dry_run_result.get("warnings", []),
            "errors": dry_run_result.get("warnings", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Collection import failed: {str(e)}")
    finally:
        for uploaded_file in upload_files:
            try:
                await uploaded_file.close()
            except Exception:
                pass


@router.get("/export", dependencies=[Depends(require_permission("admin:general"))])
async def export_full_backup(include_media: bool = True):
    """Export a complete backup of all data and optionally media files as a ZIP.
    
    Streams ZIP bytes as they are generated so proxies do not see a long idle request.
    """
    db = _db()
    storage = get_storage()
    filename = _build_backup_filename(counter=0)

    return StreamingResponse(
        _iter_backup_zip(db, storage, include_media, since=None),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )


@router.get("/export/incremental", dependencies=[Depends(require_permission("admin:general"))])
async def export_incremental_backup(
    since: str = Query(..., description="ISO datetime - only include changes after this time"),
    include_media: bool = True,
):
    """Export an incremental backup containing only changes since the specified time.
    
    This is useful for scheduled backups where you only want to capture recent changes.
    The backup includes:
    - Documents with updated_at or created_at >= since
    - Media files created >= since (if include_media=true)
    
    Args:
        since: ISO datetime string (e.g., "2024-01-15T10:30:00")
        include_media: Whether to include new media files
    """
    try:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "Invalid datetime format. Use ISO format (e.g., 2024-01-15T10:30:00)")
    
    db = _db()
    storage = get_storage()

    # Generate filename using unified naming:
    # <slug>_<counter>_<YYYYMMDD>_<HHMMSS>.zip
    counter = await _get_next_incremental_counter(db)
    filename = _build_backup_filename(counter=counter)

    return StreamingResponse(
        _iter_backup_zip(db, storage, include_media, since=since_dt),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )


@router.post("/import", dependencies=[Depends(require_permission("admin:general"))])
async def import_full_backup(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    replace_existing: bool = True,
):
    """Import a complete backup from a ZIP file.
    
    For incremental backups, set replace_existing=false to merge changes
    instead of replacing all data.
    """
    upload_files: list[UploadFile] = []
    if files:
        upload_files.extend(files)
    if file:
        upload_files.append(file)
    if not upload_files:
        raise HTTPException(400, "Provide at least one ZIP file")

    for uploaded in upload_files:
        if not uploaded.filename or not uploaded.filename.lower().endswith(".zip"):
            raise HTTPException(400, f"File '{uploaded.filename or '<unnamed>'}' must be a ZIP archive")

    temp_paths: list[str] = []
    try:
        import_archives: list[ImportArchive] = []
        for uploaded in upload_files:
            temp_fd, temp_path = tempfile.mkstemp(suffix=".zip")
            temp_paths.append(temp_path)

            with os.fdopen(temp_fd, "wb") as temp_file:
                while chunk := await uploaded.read(CHUNK_SIZE):
                    temp_file.write(chunk)

            try:
                with zipfile.ZipFile(temp_path, "r") as zf:
                    if "manifest.json" not in zf.namelist():
                        raise HTTPException(400, f"Invalid backup '{uploaded.filename}': missing manifest.json")

                    manifest = json.loads(zf.read("manifest.json"))
            except zipfile.BadZipFile:
                raise HTTPException(400, f"Invalid ZIP file: {uploaded.filename}")
            except json.JSONDecodeError:
                raise HTTPException(400, f"Invalid manifest.json in '{uploaded.filename}'")

            backup_type = manifest.get("backup_type", "full")
            if backup_type not in {"full", "incremental"}:
                backup_type = "full"

            import_archives.append(ImportArchive(
                file_name=uploaded.filename or "backup.zip",
                temp_path=temp_path,
                manifest=manifest,
                backup_type=backup_type,
                created_at=_parse_manifest_datetime(manifest.get("created_at")),
                since=_parse_manifest_datetime(manifest.get("since")),
                incremental_counter=_extract_incremental_counter(uploaded.filename or ""),
            ))

        ordered_archives = _sort_import_archives(import_archives)
        full_backup_count = sum(1 for archive in ordered_archives if archive.backup_type == "full")
        if full_backup_count > 1:
            raise HTTPException(
                400,
                "Multiple full backups provided. Import exactly one full backup and optional incremental backups.",
            )

        # Prevalidation phase: fail fast before applying any DB/media mutation.
        for archive in ordered_archives:
            _prevalidate_import_archive(archive)

        db = _db()
        storage = get_storage()

        collections_totals: dict[str, int] = {}
        archives_imported: list[dict[str, Any]] = []
        import_stats = {
            "collections_imported": [],
            "collections_skipped": [],
            "revision_collections_cleared": [],
            "media_imported": 0,
            "documents_upserted": 0,
            "errors": [],
            "backup_type": ordered_archives[0].backup_type if len(ordered_archives) == 1 else "multi",
            "archives_imported": archives_imported,
        }

        should_clear_revision_history = (
            replace_existing
            and bool(ordered_archives)
            and ordered_archives[0].backup_type != "incremental"
        )
        if should_clear_revision_history:
            for coll_name in sorted(REVISION_HISTORY_COLLECTIONS):
                await db[coll_name].delete_many({})
                import_stats["revision_collections_cleared"].append(coll_name)

        for archive_index, archive in enumerate(ordered_archives):
            archive_stats = {
                "file_name": archive.file_name,
                "backup_type": archive.backup_type,
                "backup_created_at": archive.manifest.get("created_at"),
                "collections_imported": [],
                "collections_skipped": [],
                "media_imported": 0,
                "documents_upserted": 0,
                "errors": [],
            }
            archives_imported.append(archive_stats)

            with zipfile.ZipFile(archive.temp_path, "r") as zf:
                for coll_info in archive.manifest.get("collections", []):
                    coll_name = coll_info["name"]
                    if _is_backup_excluded_collection(coll_name):
                        archive_stats["collections_skipped"].append(coll_name)
                        continue
                    json_path = f"data/{coll_name}.json"

                    if json_path not in zf.namelist():
                        archive_stats["errors"].append(f"Missing data file: {json_path}")
                        continue

                    try:
                        docs_json = json.loads(zf.read(json_path))
                        docs = [_deserialize_doc(doc) for doc in docs_json]

                        if docs:
                            coll = db[coll_name]
                            should_replace_collection = (
                                replace_existing
                                and archive.backup_type != "incremental"
                                and archive_index == 0
                            )

                            if should_replace_collection:
                                await coll.delete_many({})
                                await coll.insert_many(docs)
                            else:
                                for doc in docs:
                                    doc_id = doc.get("_id")
                                    if doc_id:
                                        await coll.replace_one(
                                            {"_id": doc_id},
                                            doc,
                                            upsert=True,
                                        )
                                        archive_stats["documents_upserted"] += 1
                                    else:
                                        await coll.insert_one(doc)

                            imported_count = len(docs)
                            archive_stats["collections_imported"].append({
                                "name": coll_name,
                                "count": imported_count,
                            })
                            collections_totals[coll_name] = collections_totals.get(coll_name, 0) + imported_count
                    except Exception as e:
                        archive_stats["errors"].append(f"Error importing {coll_name}: {str(e)}")

                if archive.manifest.get("media_included") and "media/manifest.json" in zf.namelist():
                    media_manifest = json.loads(zf.read("media/manifest.json"))

                    for media_item in media_manifest:
                        key = media_item["key"]
                        media_path = f"media/{key}"

                        if media_path in zf.namelist():
                            try:
                                media_data = zf.read(media_path)
                                await storage.put(
                                    data=media_data,
                                    key=key,
                                    content_type=media_item.get("content_type", "application/octet-stream"),
                                    filename=key.split("/")[-1],
                                )
                                archive_stats["media_imported"] += 1
                            except Exception as e:
                                archive_stats["errors"].append(f"Error importing media {key}: {str(e)}")

            import_stats["media_imported"] += archive_stats["media_imported"]
            import_stats["documents_upserted"] += archive_stats["documents_upserted"]
            if archive_stats["collections_skipped"]:
                import_stats["collections_skipped"].extend(
                    f"{archive.file_name}: {coll_name}"
                    for coll_name in archive_stats["collections_skipped"]
                )
            if archive_stats["errors"]:
                import_stats["errors"].extend([f"{archive.file_name}: {err}" for err in archive_stats["errors"]])

        import_stats["collections_imported"] = [
            {"name": coll_name, "count": count}
            for coll_name, count in sorted(collections_totals.items())
        ]

        await ensure_db_collections_and_indexes(db)

        backup_log = db[BACKUP_LOG_COLLECTION]
        await backup_log.insert_one({
            "type": "import",
            "backup_type": import_stats["backup_type"],
            "backup_created_at": ordered_archives[-1].manifest.get("created_at"),
            "imported_at": datetime.utcnow(),
            "stats": import_stats,
        })

        return {
            "status": "success",
            "manifest_version": ordered_archives[-1].manifest.get("version"),
            "backup_created_at": ordered_archives[-1].manifest.get("created_at"),
            **import_stats,
        }
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid ZIP file")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Import failed: {str(e)}")
    finally:
        for uploaded in upload_files:
            try:
                await uploaded.close()
            except Exception:
                pass
        for temp_path in temp_paths:
            try:
                os.unlink(temp_path)
            except Exception:
                pass


@router.get("/info", dependencies=[Depends(require_permission("admin:general"))])
async def get_backup_info(
    since: str | None = Query(None, description="ISO datetime to preview incremental backup size"),
):
    """Get information about what would be included in a backup.
    
    Optionally pass 'since' parameter to see what an incremental backup would contain.
    """
    db = _db()
    
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, "Invalid datetime format")
    
    collections_to_backup = await _get_collections_to_backup(db)
    
    info = {
        "collections": [],
        "total_documents": 0,
        "media_info": None,
        "backup_type": "incremental" if since_dt else "full",
        "since": since,
    }
    
    for coll_name in collections_to_backup:
        coll = db[coll_name]
        
        if since_dt:
            query = {"$or": [
                {"updated_at": {"$gte": since_dt}},
                {"created_at": {"$gte": since_dt}},
            ]}
            count = await coll.count_documents(query)
        else:
            count = await coll.count_documents({})
        
        info["collections"].append(build_collection_summary(coll_name, count))
        info["total_documents"] += count
    
    assets_coll = db[ASSETS_COLLECTION]
    
    if since_dt:
        asset_query = {"created_at": {"$gte": since_dt}}
    else:
        asset_query = {}
    
    assets_count = await assets_coll.count_documents(asset_query)
    
    total_size = 0
    async for asset in assets_coll.find(asset_query, {"size": 1}):
        if asset.get("size"):
            total_size += asset["size"]
    
    info["media_info"] = {
        "asset_count": assets_count,
        "estimated_size_bytes": total_size,
        "estimated_size_mb": round(total_size / (1024 * 1024), 2),
    }
    
    return info


@router.get("/last-backup", dependencies=[Depends(require_permission("admin:general"))])
async def get_last_backup_time():
    """Get the timestamp of the last successful backup.
    
    Useful for determining the 'since' parameter for incremental backups.
    Returns both export and import history.
    """
    db = _db()
    backup_log = db[BACKUP_LOG_COLLECTION]
    
    # Get last export
    last_export = await backup_log.find_one(
        {"type": "export"},
        sort=[("exported_at", -1)]
    )
    
    # Get last import
    last_import = await backup_log.find_one(
        {"type": "import"},
        sort=[("imported_at", -1)]
    )
    
    return {
        "last_export": {
            "timestamp": last_export.get("exported_at").isoformat() if last_export and last_export.get("exported_at") else None,
            "type": last_export.get("backup_type") if last_export else None,
        } if last_export else None,
        "last_import": {
            "timestamp": last_import.get("imported_at").isoformat() if last_import and last_import.get("imported_at") else None,
            "backup_created_at": last_import.get("backup_created_at") if last_import else None,
        } if last_import else None,
        "suggested_incremental_since": (
            last_export.get("exported_at").isoformat() 
            if last_export and last_export.get("exported_at") 
            else None
        ),
    }


@router.post("/log-export", dependencies=[Depends(require_permission("admin:general"))])
async def log_backup_export(backup_type: str = "full"):
    """Log that a backup export was performed.
    
    Call this after successfully downloading a backup to track backup history.
    This helps determine the 'since' parameter for future incremental backups.
    """
    db = _db()
    backup_log = db[BACKUP_LOG_COLLECTION]
    
    now = datetime.utcnow()
    await backup_log.insert_one({
        "type": "export",
        "backup_type": backup_type,
        "exported_at": now,
    })
    
    return {
        "status": "logged",
        "exported_at": now.isoformat(),
        "backup_type": backup_type,
    }


@router.get("/incremental-counter", dependencies=[Depends(require_permission("admin:general"))])
async def get_incremental_counter():
    """Get the current incremental backup counter value."""
    db = _db()
    counters = db[BACKUP_STATE_COLLECTION]
    doc = await counters.find_one({"_id": "incremental"})
    return {"counter": doc.get("counter", 0) if doc else 0}


@router.post("/reset-incremental-counter", dependencies=[Depends(require_permission("admin:general"))])
async def reset_incremental_counter():
    """Reset the incremental backup counter and clear backup history.
    
    This clears both the counter and the last backup timestamp,
    so the next incremental backup will be numbered 0001 and
    will include all data (effectively a full backup).
    """
    db = _db()
    counters = db[BACKUP_STATE_COLLECTION]
    backup_log = db[BACKUP_LOG_COLLECTION]
    
    await counters.delete_one({"_id": "incremental"})
    await backup_log.delete_many({})
    
    return {"status": "reset", "counter": 0, "backup_history_cleared": True}


@router.get("/migration/options", dependencies=[Depends(require_permission("admin:general"))])
async def get_migration_options():
    """Get suggested database migration options for creating next year's database."""
    source_db_name = settings.mongo_db
    suggested_target_db = str(datetime.utcnow().year + 1)

    source_db = get_client()[source_db_name]
    collection_names = sorted(await source_db.list_collection_names())

    collections: list[dict[str, Any]] = []
    for collection_name in collection_names:
        if collection_name.startswith("system.") or collection_name in OBSOLETE_COLLECTIONS:
            continue

        doc_count = await source_db[collection_name].count_documents({})
        collections.append(
            build_collection_summary(
                collection_name,
                doc_count,
                default_mode=_default_migration_mode(collection_name),
            )
        )

    bucket_info: dict[str, Any] = {
        "available": settings.storage_backend == "s3",
        "current_bucket": settings.s3_bucket if settings.storage_backend == "s3" else None,
        "suggested_target_bucket": (
            f"{settings.s3_bucket}-{suggested_target_db}"
            if settings.storage_backend == "s3"
            else None
        ),
        "top_level_prefixes": [],
        "prefixes_error": None,
    }
    if settings.storage_backend == "s3":
        storage = get_storage()
        if isinstance(storage, S3Storage):
            try:
                bucket_info["top_level_prefixes"] = await asyncio.to_thread(
                    _s3_list_top_level_prefixes,
                    storage.s3,
                    storage.bucket,
                )
            except ValueError as e:
                bucket_info["prefixes_error"] = str(e)

    return MigrationOptionsRequest(
        source_db=source_db_name,
        suggested_target_db=suggested_target_db,
        collections=collections,
        bucket=bucket_info,
    )


@router.post("/migration/run", dependencies=[Depends(require_permission("admin:general"))])
async def run_database_migration(payload: MigrationRunRequest):
    """Create a new MongoDB database from the current database with collection-level strategy."""
    source_db_name = settings.mongo_db
    target_db_name = payload.target_db.strip()

    if not _is_valid_db_name(target_db_name):
        raise HTTPException(400, "Invalid target DB name. Use letters, numbers, ., _, and -.")
    if target_db_name == source_db_name:
        raise HTTPException(400, "Target DB must be different from current DB.")

    valid_collection_modes = {"copy", "empty", "skip"}
    if payload.bucket_mode not in {"none", "create_new", "copy_existing"}:
        raise HTTPException(400, "Invalid bucket_mode. Expected none, create_new, or copy_existing.")

    client = get_client()
    source_db = client[source_db_name]
    target_db = client[target_db_name]

    existing_target_collections = await target_db.list_collection_names()
    if existing_target_collections:
        raise HTTPException(
            400,
            f"Target DB '{target_db_name}' already contains collections. "
            "Please choose a new DB name.",
        )

    source_collection_names = sorted(await source_db.list_collection_names())
    copied_collections = 0
    empty_collections = 0
    skipped_collections = 0
    copied_documents = 0
    collection_results: list[dict[str, Any]] = []

    for collection_name in source_collection_names:
        if collection_name.startswith("system.") or collection_name in OBSOLETE_COLLECTIONS:
            continue

        mode = payload.collections.get(collection_name, _default_migration_mode(collection_name))
        if mode not in valid_collection_modes:
            raise HTTPException(
                400,
                f"Invalid collection mode '{mode}' for '{collection_name}'. "
                "Expected copy, empty, or skip.",
            )

        source_coll = source_db[collection_name]
        source_count = await source_coll.count_documents({})

        if mode == "skip":
            skipped_collections += 1
            collection_results.append(
                {
                    "name": collection_name,
                    "mode": mode,
                    "source_count": source_count,
                    "target_count": 0,
                }
            )
            continue

        await target_db.create_collection(collection_name)
        target_coll = target_db[collection_name]
        await _copy_collection_indexes(source_coll, target_coll)

        target_count = 0
        if mode == "copy":
            target_count = await _copy_collection_documents(source_coll, target_coll)
            copied_documents += target_count
            copied_collections += 1
        else:
            empty_collections += 1

        collection_results.append(
            {
                "name": collection_name,
                "mode": mode,
                "source_count": source_count,
                "target_count": target_count,
            }
        )

    bucket_result = {
        "mode": payload.bucket_mode,
        "performed": False,
        "target_bucket": None,
        "copied_objects": 0,
    }

    if payload.bucket_mode != "none":
        if settings.storage_backend != "s3":
            raise HTTPException(400, "Bucket migration is only supported for S3/MinIO storage.")

        target_bucket = (payload.target_bucket or "").strip()
        if not target_bucket:
            raise HTTPException(400, "target_bucket is required when bucket_mode is not 'none'.")
        if not _is_valid_bucket_name(target_bucket):
            raise HTTPException(400, "Invalid target bucket name.")

        storage = get_storage()
        if not isinstance(storage, S3Storage):
            raise HTTPException(400, "Configured storage backend does not support bucket operations.")

        if payload.bucket_mode == "create_new":
            try:
                await asyncio.to_thread(_s3_create_bucket, storage.s3, target_bucket)
            except ValueError as e:
                raise HTTPException(400, str(e))
            bucket_result.update(
                {
                    "performed": True,
                    "target_bucket": target_bucket,
                    "copied_objects": 0,
                }
            )
        else:
            try:
                copied_objects = await asyncio.to_thread(
                    _s3_copy_bucket_contents,
                    storage.s3,
                    storage.bucket,
                    target_bucket,
                )
            except ValueError as e:
                raise HTTPException(400, str(e))
            bucket_result.update(
                {
                    "performed": True,
                    "target_bucket": target_bucket,
                    "copied_objects": copied_objects,
                }
            )

    return {
        "status": "ok",
        "source_db": source_db_name,
        "target_db": target_db_name,
        "collections": collection_results,
        "summary": {
            "copied_collections": copied_collections,
            "empty_collections": empty_collections,
            "skipped_collections": skipped_collections,
            "copied_documents": copied_documents,
        },
        "bucket": bucket_result,
        "executed_at": datetime.utcnow().isoformat(),
    }

