from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from typing import Any

from bson import ObjectId


REVIEW_ROOT_ITEM_KEY = "$root"
_REVIEW_MISSING = object()


class IntegrationReviewError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _safe_object_id(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _normalize_path(path: Any) -> list[str]:
    raw = str(path or "").strip()
    if raw.lower().startswith("in "):
        raw = raw[3:].strip()
    return [segment for segment in raw.split(".") if segment]


def normalize_review_field_path(raw_path: Any) -> str:
    path = str(raw_path or "").strip()
    if path.lower().startswith("in "):
        path = path[3:].strip()
    return path


def normalize_review_item_key(raw_value: Any) -> str:
    if raw_value is None:
        return ""
    if isinstance(raw_value, str):
        return raw_value.strip()
    if isinstance(raw_value, (int, float, bool)):
        return str(raw_value).strip()
    return ""


def extract_value_from_path(data: Any, path: Any) -> Any:
    parts = _normalize_path(path)
    if not parts:
        return None

    current = data
    for key in parts:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def _extract_value_from_path_with_missing(data: Any, path: Any, missing: Any) -> Any:
    parts = _normalize_path(path)
    if not parts:
        return missing

    current = data
    for key in parts:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return missing
    return current


def set_value_at_path(data: Any, path: Any, value: Any) -> None:
    parts = _normalize_path(path)
    if not parts or not isinstance(data, dict):
        return

    current: Any = data
    for key in parts[:-1]:
        if not isinstance(current, dict):
            return
        next_value = current.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
            current[key] = next_value
        current = next_value

    if isinstance(current, dict):
        current[parts[-1]] = deepcopy(value)


def cache_hash_payload(value: Any) -> str:
    try:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        serialized = json.dumps(str(value), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def review_item_key_for_row(row: Any, output_primary_key_path: str | None) -> str:
    normalized_path = str(output_primary_key_path or "").strip()
    if not normalized_path or not isinstance(row, dict):
        return ""
    return normalize_review_item_key(extract_value_from_path(row, normalized_path))


def review_value_from_item(item: Any, field_path: Any) -> tuple[bool, Any]:
    normalized_path = normalize_review_field_path(field_path)
    if not normalized_path:
        return False, None
    if normalized_path == "$":
        return True, item
    value = _extract_value_from_path_with_missing(item, normalized_path, _REVIEW_MISSING)
    if value is _REVIEW_MISSING:
        return False, None
    return True, value


def review_set_value_on_item(item: Any, field_path: Any, value: Any) -> bool:
    normalized_path = normalize_review_field_path(field_path)
    if not normalized_path or normalized_path == "$" or not isinstance(item, dict):
        return False
    set_value_at_path(item, normalized_path, value)
    return True


def _review_rows_for_data(
    data: Any,
    output_primary_key_path: str | None,
    *,
    local_item_keys: set[str] | None = None,
) -> tuple[list[dict[str, Any]], int, bool]:
    local_keys = local_item_keys if isinstance(local_item_keys, set) else set()
    if isinstance(data, list):
        normalized_primary_key = str(output_primary_key_path or "").strip()
        if not normalized_primary_key:
            return [], len(data), False

        rows: list[dict[str, Any]] = []
        missing_key_count = 0
        seen: set[str] = set()
        for index, item in enumerate(data):
            item_key = review_item_key_for_row(item, normalized_primary_key)
            if not item_key or item_key in seen:
                missing_key_count += 1
                continue
            seen.add(item_key)
            rows.append(
                {
                    "item_key": item_key,
                    "index": index,
                    "item": item,
                    "is_local_item": item_key in local_keys,
                }
            )
        return rows, missing_key_count, True

    if isinstance(data, dict):
        return [
            {
                "item_key": REVIEW_ROOT_ITEM_KEY,
                "index": 0,
                "item": data,
                "is_local_item": False,
            }
        ], 0, True

    return [], 0, False


def review_row_map_for_data(
    data: Any,
    output_primary_key_path: str | None,
    *,
    local_item_keys: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    rows, _missing_key_count, _can_review = _review_rows_for_data(
        data,
        output_primary_key_path,
        local_item_keys=local_item_keys,
    )
    return {row["item_key"]: row for row in rows}


async def load_review_overrides(db, integration_id: Any) -> list[dict[str, Any]]:
    overrides: list[dict[str, Any]] = []
    async for doc in db["integration_item_overrides"].find({"integration_id": str(integration_id or "").strip()}):
        if isinstance(doc, dict):
            overrides.append(doc)
    return overrides


def _schema_field_paths(schema_doc: dict[str, Any] | None) -> set[str]:
    if not isinstance(schema_doc, dict):
        return set()
    paths: set[str] = set()
    for key in ("detected_fields", "manual_types", "collect_options", "cache_media", "required_fields"):
        raw_map = schema_doc.get(key)
        if not isinstance(raw_map, dict):
            continue
        paths.update(
            path
            for path in (normalize_review_field_path(raw_path) for raw_path in raw_map.keys())
            if path
        )
    return paths


async def filter_legacy_page_slug_overrides(db, integration_id: Any, overrides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_integration_id = str(integration_id or "").strip()
    if not normalized_integration_id or not overrides:
        return overrides
    schema_doc = await db["integration_schemas"].find_one(
        {"integration_id": normalized_integration_id},
        {
            "detected_fields": 1,
            "manual_types": 1,
            "collect_options": 1,
            "cache_media": 1,
            "required_fields": 1,
        },
    )
    schema_paths = _schema_field_paths(schema_doc)
    return [
        override
        for override in overrides
        if not (
            normalize_review_field_path(override.get("field_path")) == "page_slug"
            and "page_slug" not in schema_paths
        )
    ]


async def load_local_review_items(db, integration_id: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    async for doc in db["integration_local_items"].find({"integration_id": str(integration_id or "").strip()}).sort("created_at", 1):
        if isinstance(doc, dict):
            items.append(doc)
    return items


def _local_review_items_as_data(local_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for doc in local_docs:
        item = doc.get("item")
        if isinstance(item, dict):
            data.append(deepcopy(item))
    return data


def combine_fetched_and_local_review_data(data: Any, local_docs: list[dict[str, Any]]) -> Any:
    if not isinstance(data, list):
        return data
    local_items = _local_review_items_as_data(local_docs)
    if not local_items:
        return data
    return [*deepcopy(data), *local_items]


def apply_review_overrides_to_data(
    data: Any,
    output_primary_key_path: str | None,
    overrides: list[dict[str, Any]],
) -> Any:
    effective_data = deepcopy(data)
    if not overrides:
        return effective_data

    if isinstance(effective_data, list):
        index_by_key: dict[str, int] = {}
        normalized_primary_key = str(output_primary_key_path or "").strip()
        if not normalized_primary_key:
            return effective_data
        for index, row in enumerate(effective_data):
            item_key = review_item_key_for_row(row, normalized_primary_key)
            if item_key and item_key not in index_by_key:
                index_by_key[item_key] = index
        for override in overrides:
            item_key = str(override.get("item_key") or "").strip()
            if item_key not in index_by_key:
                continue
            row = effective_data[index_by_key[item_key]]
            review_set_value_on_item(row, override.get("field_path"), override.get("local_value"))
        return effective_data

    if isinstance(effective_data, dict):
        for override in overrides:
            if str(override.get("item_key") or "").strip() != REVIEW_ROOT_ITEM_KEY:
                continue
            review_set_value_on_item(
                effective_data,
                override.get("field_path"),
                override.get("local_value"),
            )
    return effective_data


async def get_effective_integration_data_doc(
    db,
    integration_id: Any,
    *,
    integration_doc: dict[str, Any] | None = None,
    data_doc: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Any]:
    normalized_integration_id = str(integration_id or "").strip()
    integration = integration_doc
    if not isinstance(integration, dict):
        integration_oid = _safe_object_id(normalized_integration_id)
        if integration_oid is None:
            raise IntegrationReviewError("Invalid integration ID", status_code=400)
        integration = await db["integration_config"].find_one({"_id": integration_oid})
    if not isinstance(integration, dict):
        raise IntegrationReviewError("Integration not found", status_code=404)

    current_data_doc = data_doc
    if not isinstance(current_data_doc, dict):
        current_data_doc = await db["integration_data"].find_one(
            {"integration_id": normalized_integration_id},
            sort=[("fetched_at", -1)],
        )
    if not isinstance(current_data_doc, dict):
        raise IntegrationReviewError("No data fetched yet", status_code=404)

    overrides = await filter_legacy_page_slug_overrides(
        db,
        normalized_integration_id,
        await load_review_overrides(db, normalized_integration_id),
    )
    local_docs = await load_local_review_items(db, normalized_integration_id)
    base_data = combine_fetched_and_local_review_data(current_data_doc.get("data"), local_docs)
    effective_data = apply_review_overrides_to_data(
        base_data,
        str(integration.get("output_primary_key_path") or "").strip(),
        overrides,
    )
    return integration, current_data_doc, effective_data


async def upsert_integration_review_override(
    db,
    *,
    integration_id: Any,
    item_key: Any,
    field_path: Any,
    value: Any,
    integration_doc: dict[str, Any] | None = None,
    data_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_integration_id = str(integration_id or "").strip()
    normalized_item_key = str(item_key or "").strip()
    normalized_field_path = normalize_review_field_path(field_path)
    if not normalized_integration_id or not normalized_item_key or not normalized_field_path or normalized_field_path == "$":
        raise IntegrationReviewError("integration_id, item_key, and editable field_path are required", status_code=400)

    integration, current_data_doc, _effective_data = await get_effective_integration_data_doc(
        db,
        normalized_integration_id,
        integration_doc=integration_doc,
        data_doc=data_doc,
    )
    output_primary_key_path = str(integration.get("output_primary_key_path") or "").strip()
    local_docs = await load_local_review_items(db, normalized_integration_id)
    review_data = combine_fetched_and_local_review_data(current_data_doc.get("data"), local_docs)
    current_rows = review_row_map_for_data(review_data, output_primary_key_path)
    current_row = current_rows.get(normalized_item_key)
    if current_row is None:
        raise IntegrationReviewError("Review item not found in current review data", status_code=404)

    has_base_value, base_value = review_value_from_item(current_row.get("item"), normalized_field_path)
    overrides_coll = db["integration_item_overrides"]
    existing = await overrides_coll.find_one(
        {
            "integration_id": normalized_integration_id,
            "item_key": normalized_item_key,
            "field_path": normalized_field_path,
        }
    )
    now = datetime.utcnow()
    history_entry = None
    if isinstance(existing, dict):
        history_entry = {
            "local_value": deepcopy(existing.get("local_value")),
            "base_fetched_value": deepcopy(existing.get("base_fetched_value")),
            "base_missing": bool(existing.get("base_missing", False)),
            "base_fetched_at": existing.get("base_fetched_at"),
            "updated_at": existing.get("updated_at"),
        }

    update_doc = {
        "integration_id": normalized_integration_id,
        "item_key": normalized_item_key,
        "field_path": normalized_field_path,
        "local_value": deepcopy(value),
        "local_value_hash": cache_hash_payload(value),
        "base_fetched_value": deepcopy(base_value) if has_base_value else None,
        "base_value_hash": cache_hash_payload(base_value) if has_base_value else None,
        "base_missing": not has_base_value,
        "base_fetched_at": current_data_doc.get("fetched_at"),
        "base_data_hash": current_data_doc.get("data_hash"),
        "updated_at": now,
    }
    update_ops: dict[str, Any] = {
        "$set": update_doc,
        "$setOnInsert": {"created_at": now},
    }
    if history_entry is not None:
        update_ops["$push"] = {"history": {"$each": [history_entry], "$slice": -5}}

    await overrides_coll.update_one(
        {
            "integration_id": normalized_integration_id,
            "item_key": normalized_item_key,
            "field_path": normalized_field_path,
        },
        update_ops,
        upsert=True,
    )
    return update_doc
