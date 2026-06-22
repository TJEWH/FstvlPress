from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
from typing import Any

from pydantic import BaseModel
from pymongo import UpdateOne

from app.collection_names import PROGRAM_GIGS_COLLECTION, PROGRAM_SHARED_COLLECTION
from app.models.sections.sections import ProgramGig, ProgramStage


PROGRAM_SHARED_DOC_ID = "shared"
PROGRAM_GIG_INTERNAL_ID_PREFIX = "gig-ih-"
PROGRAM_ITEM_ID_HASH_LENGTH = 24
PROGRAM_SECTION_SHARED_CLEANUP_VERSION = 2

PROGRAM_GIG_STORAGE_VOLATILE_KEYS = frozenset(
    {
        "_id",
        "created_at",
        "updated_at",
        "item_page_template_outdated",
        "item_page_missing",
        "item_page_mapped_fields_synced",
        "day",
        "start_time",
        "end_time",
        "previous_day",
        "previous_start_time",
        "previous_end_time",
        "__source",
        "__base",
        "__change",
        "__canceled",
        "__changed",
    }
)


def _safe_datetime_utc() -> datetime:
    return datetime.utcnow()


def _coerce_program_identity_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value).strip()
    return ""


def _tokenize_data_path(path: Any) -> list[str | int]:
    normalized = str(path or "").strip()
    if not normalized:
        return []
    tokens: list[str | int] = []
    buffer = ""
    index = 0
    while index < len(normalized):
        char = normalized[index]
        if char == ".":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            index += 1
            continue
        if char == "[":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            end_index = normalized.find("]", index + 1)
            if end_index == -1:
                return []
            raw_token = normalized[index + 1:end_index].strip().strip("'\"")
            if raw_token.isdigit():
                tokens.append(int(raw_token))
            elif raw_token:
                tokens.append(raw_token)
            index = end_index + 1
            continue
        buffer += char
        index += 1
    if buffer:
        tokens.append(buffer)
    return tokens


def _deep_get_by_path(data: Any, path: Any) -> Any:
    tokens = _tokenize_data_path(path)
    if not tokens:
        return None
    current = data
    for token in tokens:
        if isinstance(token, int):
            if not isinstance(current, list) or token < 0 or token >= len(current):
                return None
            current = current[token]
            continue
        if not isinstance(current, dict):
            return None
        candidates = [token]
        if "_" in token:
            head, *tail = token.split("_")
            camel = head + "".join(part[:1].upper() + part[1:] for part in tail)
            candidates.append(camel)
        else:
            snake = ""
            for char in token:
                if char.isupper() and snake:
                    snake += "_"
                snake += char.lower()
            if snake and snake != token:
                candidates.append(snake)
        found = False
        for candidate in candidates:
            if candidate in current:
                current = current[candidate]
                found = True
                break
        if not found:
            return None
    return current


def integration_output_primary_key_path_from_cache_state(cache_state: Any) -> str:
    source = cache_state if isinstance(cache_state, dict) else {}
    return str(
        source.get("integration_output_primary_key_path")
        or source.get("integrationOutputPrimaryKeyPath")
        or ""
    ).strip()


def integration_selected_id_from_mapping(mapping: Any) -> str:
    source = mapping if isinstance(mapping, dict) else {}
    return str(
        source.get("selected_integration_id")
        or source.get("selectedIntegrationId")
        or ""
    ).strip()


def _is_internal_program_gig_id(value: Any) -> bool:
    normalized = str(value or "").strip()
    if not normalized.startswith(PROGRAM_GIG_INTERNAL_ID_PREFIX):
        return False
    digest = normalized[len(PROGRAM_GIG_INTERNAL_ID_PREFIX):]
    return len(digest) == PROGRAM_ITEM_ID_HASH_LENGTH and all(
        char in "0123456789abcdef"
        for char in digest
    )


def _is_index_fallback_program_id(value: Any, *, fallback_prefix: str) -> bool:
    normalized = str(value or "").strip()
    prefix = f"{fallback_prefix}-"
    return normalized.startswith(prefix) and normalized[len(prefix):].isdigit()


def _canonical_identity_payload(value: Any) -> Any:
    if isinstance(value, list):
        return [_canonical_identity_payload(entry) for entry in value]
    if not isinstance(value, dict):
        return value
    ignored_keys = {
        "_id",
        "id",
        "page_slug",
        "item_url",
        "created_at",
        "updated_at",
        "item_page_template_outdated",
        "item_page_missing",
        "item_page_mapped_fields_synced",
    }
    result: dict[str, Any] = {}
    for key, nested_value in value.items():
        normalized_key = str(key or "")
        if normalized_key in ignored_keys or normalized_key.startswith("item_page_"):
            continue
        result[normalized_key] = _canonical_identity_payload(nested_value)
    return result


def _program_gig_internal_id_from_seed(seed: dict[str, Any]) -> str:
    canonical = json.dumps(
        seed,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{PROGRAM_GIG_INTERNAL_ID_PREFIX}{digest[:PROGRAM_ITEM_ID_HASH_LENGTH]}"


def _resolve_program_external_item_key(
    source: dict[str, Any],
    normalized: dict[str, Any],
    *,
    primary_key_path: str | None = None,
) -> str:
    primary_path = str(primary_key_path or "").strip()
    for candidate in (
        _coerce_program_identity_value(_deep_get_by_path(source, primary_path)),
        _coerce_program_identity_value(_deep_get_by_path(normalized, primary_path)),
        _coerce_program_identity_value(source.get("integration_item_key")),
        _coerce_program_identity_value(source.get("integrationItemKey")),
        _coerce_program_identity_value(source.get("template_integration_item_key")),
        _coerce_program_identity_value(source.get("review_item_key")),
        _coerce_program_identity_value(source.get("reviewItemKey")),
        _coerce_program_identity_value(normalized.get("integration_item_key")),
        _coerce_program_identity_value(normalized.get("integrationItemKey")),
    ):
        if candidate:
            return candidate
    return ""


def _resolve_program_item_identity(
    source: dict[str, Any],
    normalized: dict[str, Any],
    *,
    index: int,
    fallback_prefix: str,
    primary_key_path: str | None = None,
    selected_integration_id: str | None = None,
    external_item_key: str | None = None,
) -> str:
    existing_id = (
        _coerce_program_identity_value(normalized.get("id"))
        or _coerce_program_identity_value(source.get("id"))
        or _coerce_program_identity_value(source.get("_id"))
    )
    if fallback_prefix == "gig":
        if _is_internal_program_gig_id(existing_id):
            return existing_id

        external_key = str(external_item_key or "").strip()
        if external_key:
            return _program_gig_internal_id_from_seed(
                {
                    "version": 1,
                    "kind": "program_gig",
                    "source": "integration",
                    "integration_id": str(selected_integration_id or "").strip(),
                    "primary_key_path": str(primary_key_path or "").strip(),
                    "external_item_key": external_key,
                }
            )

        if existing_id and not _is_index_fallback_program_id(
            existing_id,
            fallback_prefix=fallback_prefix,
        ):
            return _program_gig_internal_id_from_seed(
                {
                    "version": 1,
                    "kind": "program_gig",
                    "source": "legacy_id",
                    "legacy_id": existing_id,
                }
            )

        return _program_gig_internal_id_from_seed(
            {
                "version": 1,
                "kind": "program_gig",
                "source": "content",
                "content": _canonical_identity_payload(source or normalized),
            }
        )

    for candidate in (
        existing_id,
        _coerce_program_identity_value(_deep_get_by_path(source, primary_key_path)),
        _coerce_program_identity_value(_deep_get_by_path(normalized, primary_key_path)),
        _coerce_program_identity_value(source.get("item_key")),
        _coerce_program_identity_value(source.get("itemKey")),
        _coerce_program_identity_value(source.get("source_key")),
        _coerce_program_identity_value(source.get("sourceKey")),
        _coerce_program_identity_value(source.get("key")),
    ):
        if candidate:
            return candidate
    return f"{fallback_prefix}-{index + 1}"


def _normalize_program_stage_snapshot(
    raw_stage: Any,
    index: int,
    *,
    primary_key_path: str | None = None,
) -> dict[str, Any]:
    if isinstance(raw_stage, BaseModel):
        source = raw_stage.model_dump()
    elif isinstance(raw_stage, dict):
        source = raw_stage
    else:
        source = {}
    try:
        normalized = ProgramStage.model_validate(source).model_dump()
    except Exception:
        normalized = ProgramStage().model_dump()
    normalized["id"] = _resolve_program_item_identity(
        source,
        normalized,
        index=index,
        fallback_prefix="stage",
        primary_key_path=primary_key_path,
    )
    return normalized


def _normalize_program_gig_snapshot(
    raw_gig: Any,
    index: int,
    *,
    primary_key_path: str | None = None,
    selected_integration_id: str | None = None,
) -> dict[str, Any]:
    if isinstance(raw_gig, BaseModel):
        source = raw_gig.model_dump()
    elif isinstance(raw_gig, dict):
        source = raw_gig
    else:
        source = {}
    try:
        normalized = ProgramGig.model_validate(source).model_dump()
    except Exception:
        normalized = ProgramGig().model_dump()
    external_item_key = _resolve_program_external_item_key(
        source,
        normalized,
        primary_key_path=primary_key_path,
    )
    if external_item_key:
        normalized["integration_item_key"] = external_item_key
    normalized["id"] = _resolve_program_item_identity(
        source,
        normalized,
        index=index,
        fallback_prefix="gig",
        primary_key_path=primary_key_path,
        selected_integration_id=selected_integration_id,
        external_item_key=external_item_key,
    )
    return normalized


def _normalize_program_shared_metadata(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _normalize_gig_id_list(value: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw_id in value if isinstance(value, list) else []:
        gig_id = str(raw_id or "").strip()
        if not gig_id or gig_id in seen:
            continue
        seen.add(gig_id)
        result.append(gig_id)
    return result


def normalize_program_shared_content_snapshot(shared_content: Any) -> dict[str, Any]:
    source = shared_content if isinstance(shared_content, dict) else {}
    stage_integration_mapping = _normalize_program_shared_metadata(
        source.get("program_stages_integration_mapping")
        if source.get("program_stages_integration_mapping") is not None
        else source.get("programStagesIntegrationMapping")
    )
    stage_mapping_cache_state = _normalize_program_shared_metadata(
        source.get("program_stages_integration_mapping_cache_state")
        if source.get("program_stages_integration_mapping_cache_state") is not None
        else source.get("programStagesIntegrationMappingCacheState")
    )
    gig_integration_mapping = _normalize_program_shared_metadata(
        source.get("program_gigs_integration_mapping")
        if source.get("program_gigs_integration_mapping") is not None
        else source.get("programGigsIntegrationMapping")
    )
    gig_mapping_cache_state = _normalize_program_shared_metadata(
        source.get("program_gigs_integration_mapping_cache_state")
        if source.get("program_gigs_integration_mapping_cache_state") is not None
        else source.get("programGigsIntegrationMappingCacheState")
    )
    stage_primary_key_path = integration_output_primary_key_path_from_cache_state(
        stage_mapping_cache_state
    )
    gig_primary_key_path = integration_output_primary_key_path_from_cache_state(
        gig_mapping_cache_state
    )
    gig_selected_integration_id = integration_selected_id_from_mapping(gig_integration_mapping)
    normalized_stages: list[dict[str, Any]] = []
    normalized_gigs: list[dict[str, Any]] = []

    seen_stage_ids: set[str] = set()
    raw_stages = source.get("stages")
    if isinstance(raw_stages, list):
        for index, raw_stage in enumerate(raw_stages):
            normalized_stage = _normalize_program_stage_snapshot(
                raw_stage,
                index,
                primary_key_path=stage_primary_key_path,
            )
            stage_id = str(normalized_stage.get("id") or "").strip()
            if not stage_id or stage_id in seen_stage_ids:
                continue
            seen_stage_ids.add(stage_id)
            normalized_stages.append(normalized_stage)

    seen_gig_ids: set[str] = set()
    raw_gig_ids = _normalize_gig_id_list(source.get("gig_ids"))
    for gig_id in raw_gig_ids:
        if gig_id in seen_gig_ids:
            continue
        seen_gig_ids.add(gig_id)

    seen_gig_row_ids: set[str] = set()
    raw_gigs = source.get("gigs")
    if isinstance(raw_gigs, list):
        for index, raw_gig in enumerate(raw_gigs):
            normalized_gig = _normalize_program_gig_snapshot(
                raw_gig,
                index,
                primary_key_path=gig_primary_key_path,
                selected_integration_id=gig_selected_integration_id,
            )
            gig_id = str(normalized_gig.get("id") or "").strip()
            if not gig_id or gig_id in seen_gig_row_ids:
                continue
            seen_gig_row_ids.add(gig_id)
            if gig_id not in seen_gig_ids:
                seen_gig_ids.add(gig_id)
                raw_gig_ids.append(gig_id)
            normalized_gigs.append(normalized_gig)

    return {
        "stages": normalized_stages,
        "gig_ids": raw_gig_ids,
        "gigs": normalized_gigs,
        "program_stages_integration_mapping": stage_integration_mapping,
        "program_stages_integration_mapping_cache_state": stage_mapping_cache_state,
        "program_gigs_integration_mapping": gig_integration_mapping,
        "program_gigs_integration_mapping_cache_state": gig_mapping_cache_state,
    }


def _strip_program_gig_storage_metadata(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in row.items()
        if str(key) not in PROGRAM_GIG_STORAGE_VOLATILE_KEYS
    }


def normalize_program_gig_for_storage(
    raw_gig: Any,
    index: int = 0,
    *,
    primary_key_path: str | None = None,
    selected_integration_id: str | None = None,
) -> dict[str, Any]:
    normalized = _normalize_program_gig_snapshot(
        raw_gig,
        index,
        primary_key_path=primary_key_path,
        selected_integration_id=selected_integration_id,
    )
    normalized = _strip_program_gig_storage_metadata(normalized)
    gig_id = str(normalized.get("id") or "").strip()
    normalized["id"] = gig_id or f"gig-{index + 1}"
    return normalized


def _program_gig_storage_unset_payload() -> dict[str, str]:
    return {
        key: ""
        for key in PROGRAM_GIG_STORAGE_VOLATILE_KEYS
        if key not in {"_id", "created_at", "updated_at"}
    }


def normalize_program_gig_doc_for_response(
    raw_doc: Any,
    index: int = 0,
    *,
    primary_key_path: str | None = None,
    selected_integration_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(raw_doc, dict):
        return normalize_program_gig_for_storage(
            raw_doc,
            index,
            primary_key_path=primary_key_path,
            selected_integration_id=selected_integration_id,
        )
    source = {k: v for k, v in raw_doc.items() if k != "_id"}
    if not str(source.get("id") or "").strip():
        source["id"] = str(raw_doc.get("_id") or "").strip()
    return normalize_program_gig_for_storage(
        source,
        index,
        primary_key_path=primary_key_path,
        selected_integration_id=selected_integration_id,
    )


def _dedupe_rows_by_id(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        row_id = str(row.get("id") or "").strip()
        if not row_id or row_id in seen:
            continue
        seen.add(row_id)
        result.append(row)
    return result


def _append_unique_ids(target: list[str], source: list[str] | tuple[str, ...]) -> None:
    seen = set(target)
    for raw_id in source:
        item_id = str(raw_id or "").strip()
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        target.append(item_id)


async def _upsert_program_gig_docs(
    db,
    raw_gigs: list[Any],
    *,
    now: datetime | None = None,
    primary_key_path: str | None = None,
    selected_integration_id: str | None = None,
) -> list[str]:
    timestamp = now or _safe_datetime_utc()
    operations: list[UpdateOne] = []
    gig_ids: list[str] = []
    seen: set[str] = set()

    for index, raw_gig in enumerate(raw_gigs if isinstance(raw_gigs, list) else []):
        normalized = normalize_program_gig_for_storage(
            raw_gig,
            index,
            primary_key_path=primary_key_path,
            selected_integration_id=selected_integration_id,
        )
        gig_id = str(normalized.get("id") or "").strip()
        if not gig_id or gig_id in seen:
            continue
        seen.add(gig_id)
        gig_ids.append(gig_id)
        operations.append(
            UpdateOne(
                {"_id": gig_id},
                {
                    "$set": {
                        **deepcopy(normalized),
                        "updated_at": timestamp,
                    },
                    "$unset": _program_gig_storage_unset_payload(),
                    "$setOnInsert": {
                        "created_at": timestamp,
                    },
                },
                upsert=True,
            )
        )

    if operations:
        await db[PROGRAM_GIGS_COLLECTION].bulk_write(operations, ordered=False)
    return gig_ids


async def _load_all_program_gig_ids(db) -> list[str]:
    ids: list[str] = []
    async for doc in db[PROGRAM_GIGS_COLLECTION].find({}, {"_id": 1, "id": 1, "start": 1}).sort(
        [("start", 1), ("_id", 1)]
    ):
        gig_id = str(doc.get("id") or doc.get("_id") or "").strip()
        if gig_id:
            ids.append(gig_id)
    return ids


def _extract_program_date_part(value: Any) -> str:
    raw = str(value or "").strip().replace(" ", "T")
    if len(raw) >= 10:
        candidate = raw[:10]
        try:
            datetime.strptime(candidate, "%Y-%m-%d")
            return candidate
        except ValueError:
            return ""
    return ""


def _extract_program_time_part(value: Any) -> str:
    raw = str(value or "").strip().replace(" ", "T")
    if len(raw) >= 16:
        candidate = raw[11:16]
        try:
            datetime.strptime(candidate, "%H:%M")
            return candidate
        except ValueError:
            return ""
    return ""


def _subtract_days(day_value: str, days: int) -> str:
    try:
        parsed = datetime.strptime(day_value, "%Y-%m-%d")
    except ValueError:
        return day_value
    return (parsed - timedelta(days=days)).strftime("%Y-%m-%d")


def _add_days(day_value: str, days: int) -> str:
    try:
        parsed = datetime.strptime(day_value, "%Y-%m-%d")
    except ValueError:
        return day_value
    return (parsed + timedelta(days=days)).strftime("%Y-%m-%d")


def resolve_program_gig_logical_day(
    gig: dict[str, Any],
    *,
    day_start_hour: int = 10,
    day_end_hour: int = 6,
) -> str:
    gig_day = _extract_program_date_part(gig.get("start")) or str(gig.get("day") or "").strip()
    gig_start_time = _extract_program_time_part(gig.get("start")) or str(gig.get("start_time") or "").strip()
    if not gig_day or not gig_start_time:
        return gig_day

    try:
        gig_hour = int(gig_start_time.split(":", 1)[0])
    except ValueError:
        return gig_day

    effective_end_hour = day_end_hour - 24 if day_end_hour > 24 else day_end_hour
    day_wraps = day_end_hour > 24 or day_end_hour <= day_start_hour

    if day_wraps:
        if gig_hour < effective_end_hour:
            return _subtract_days(gig_day, 1)
        if gig_hour < day_start_hour and gig_hour >= effective_end_hour:
            return gig_day
    elif gig_hour < day_start_hour and day_start_hour > 0:
        return _subtract_days(gig_day, 1)

    return gig_day


async def load_program_gig_docs(
    db,
    *,
    ordered_gig_ids: list[str] | None = None,
    ids: list[str] | None = None,
    gig_id: str | None = None,
    stage_id: str | None = None,
    day: str | None = None,
    day_start_hour: int = 10,
    day_end_hour: int = 6,
    primary_key_path: str | None = None,
    selected_integration_id: str | None = None,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    id_filter = _normalize_gig_id_list(ids)
    normalized_gig_id = str(gig_id or "").strip()
    if normalized_gig_id:
        id_filter = [normalized_gig_id]
    elif ordered_gig_ids:
        id_filter = _normalize_gig_id_list(ordered_gig_ids)

    normalized_primary_key_path = str(primary_key_path or "").strip()
    if id_filter:
        id_query: dict[str, Any] = {
            "$or": [
                {"_id": {"$in": id_filter}},
                {"integration_item_key": {"$in": id_filter}},
            ]
        }
        if normalized_primary_key_path and normalized_primary_key_path != "_id":
            id_query = {
                "$or": [
                    {"_id": {"$in": id_filter}},
                    {"integration_item_key": {"$in": id_filter}},
                    {normalized_primary_key_path: {"$in": id_filter}},
                ]
            }
        query.update(id_query)

    normalized_stage_id = str(stage_id or "").strip()
    if normalized_stage_id:
        query["stage"] = normalized_stage_id

    normalized_day = str(day or "").strip()
    physical_day_candidates: list[str] = []
    if normalized_day:
        physical_day_candidates = [normalized_day, _add_days(normalized_day, 1)]
        query["start"] = {
            "$regex": f"^({'|'.join(physical_day_candidates)})"
        }

    docs = await db[PROGRAM_GIGS_COLLECTION].find(query).to_list(length=5000)
    response_rows = [
        normalize_program_gig_doc_for_response(
            doc,
            index,
            primary_key_path=normalized_primary_key_path,
            selected_integration_id=selected_integration_id,
        )
        for index, doc in enumerate(docs)
    ]

    if normalized_day:
        response_rows = [
            row
            for row in response_rows
            if resolve_program_gig_logical_day(
                row,
                day_start_hour=day_start_hour,
                day_end_hour=day_end_hour,
            ) == normalized_day
        ]

    if ordered_gig_ids:
        order = {gig_id: index for index, gig_id in enumerate(_normalize_gig_id_list(ordered_gig_ids))}
        response_rows.sort(
            key=lambda row: (
                order.get(str(row.get("id") or "").strip(), len(order)),
                str(row.get("start") or ""),
                str(row.get("id") or ""),
            )
        )
    else:
        response_rows.sort(key=lambda row: (str(row.get("start") or ""), str(row.get("id") or "")))

    return response_rows


async def _load_shared_doc(db) -> dict[str, Any]:
    doc = await db[PROGRAM_SHARED_COLLECTION].find_one({"_id": PROGRAM_SHARED_DOC_ID})
    return doc if isinstance(doc, dict) else {}


async def _derive_legacy_program_integration_state_from_sections(db) -> dict[str, Any]:
    cursor = db["sections"].find(
        {"section_type": "program"},
        {
            "type_data.program_stages_integration_mapping": 1,
            "type_data.program_stages_integration_mapping_cache_state": 1,
            "type_data.programStagesIntegrationMapping": 1,
            "type_data.programStagesIntegrationMappingCacheState": 1,
            "type_data.program_gigs_integration_mapping": 1,
            "type_data.program_gigs_integration_mapping_cache_state": 1,
            "type_data.programGigsIntegrationMapping": 1,
            "type_data.programGigsIntegrationMappingCacheState": 1,
            "updated_at": 1,
        },
    ).sort("updated_at", -1)
    stage_mapping: dict[str, Any] = {}
    stage_cache_state: dict[str, Any] = {}
    gig_mapping: dict[str, Any] = {}
    gig_cache_state: dict[str, Any] = {}
    async for section in cursor:
        type_data = section.get("type_data") if isinstance(section, dict) else {}
        if not isinstance(type_data, dict):
            continue
        next_stage_mapping = _normalize_program_shared_metadata(
            type_data.get("program_stages_integration_mapping")
            if type_data.get("program_stages_integration_mapping") is not None
            else type_data.get("programStagesIntegrationMapping")
        )
        next_stage_cache_state = _normalize_program_shared_metadata(
            type_data.get("program_stages_integration_mapping_cache_state")
            if type_data.get("program_stages_integration_mapping_cache_state") is not None
            else type_data.get("programStagesIntegrationMappingCacheState")
        )
        next_gig_mapping = _normalize_program_shared_metadata(
            type_data.get("program_gigs_integration_mapping")
            if type_data.get("program_gigs_integration_mapping") is not None
            else type_data.get("programGigsIntegrationMapping")
        )
        next_gig_cache_state = _normalize_program_shared_metadata(
            type_data.get("program_gigs_integration_mapping_cache_state")
            if type_data.get("program_gigs_integration_mapping_cache_state") is not None
            else type_data.get("programGigsIntegrationMappingCacheState")
        )
        if next_stage_mapping and not stage_mapping:
            stage_mapping = next_stage_mapping
        if next_stage_cache_state and not stage_cache_state:
            stage_cache_state = next_stage_cache_state
        if next_gig_mapping and not gig_mapping:
            gig_mapping = next_gig_mapping
        if next_gig_cache_state and not gig_cache_state:
            gig_cache_state = next_gig_cache_state
        if stage_mapping and stage_cache_state and gig_mapping and gig_cache_state:
            break
    return {
        "program_stages_integration_mapping": stage_mapping,
        "program_stages_integration_mapping_cache_state": stage_cache_state,
        "program_gigs_integration_mapping": gig_mapping,
        "program_gigs_integration_mapping_cache_state": gig_cache_state,
    }


async def _derive_program_shared_legacy_content_from_sections(db) -> dict[str, Any]:
    merged_stages: list[dict[str, Any]] = []
    merged_gigs: list[dict[str, Any]] = []
    seen_stage_ids: set[str] = set()
    seen_gig_ids: set[str] = set()

    async for section_doc in db["sections"].find({"section_type": "program"}):
        type_data = section_doc.get("type_data") if isinstance(section_doc.get("type_data"), dict) else {}
        stage_primary_key_path = integration_output_primary_key_path_from_cache_state(
            type_data.get("program_stages_integration_mapping_cache_state")
            if type_data.get("program_stages_integration_mapping_cache_state") is not None
            else type_data.get("programStagesIntegrationMappingCacheState")
        )
        gig_integration_mapping = (
            type_data.get("program_gigs_integration_mapping")
            if type_data.get("program_gigs_integration_mapping") is not None
            else type_data.get("programGigsIntegrationMapping")
        )
        gig_primary_key_path = integration_output_primary_key_path_from_cache_state(
            type_data.get("program_gigs_integration_mapping_cache_state")
            if type_data.get("program_gigs_integration_mapping_cache_state") is not None
            else type_data.get("programGigsIntegrationMappingCacheState")
        )
        gig_selected_integration_id = integration_selected_id_from_mapping(gig_integration_mapping)
        raw_stages = type_data.get("stages") if isinstance(type_data.get("stages"), list) else []
        raw_gigs = type_data.get("gigs") if isinstance(type_data.get("gigs"), list) else []
        for index, raw_stage in enumerate(raw_stages):
            stage = _normalize_program_stage_snapshot(
                raw_stage,
                index,
                primary_key_path=stage_primary_key_path,
            )
            stage_id = str(stage.get("id") or "").strip()
            if not stage_id or stage_id in seen_stage_ids:
                continue
            seen_stage_ids.add(stage_id)
            merged_stages.append(stage)
        for index, raw_gig in enumerate(raw_gigs):
            gig = normalize_program_gig_for_storage(
                raw_gig,
                index,
                primary_key_path=gig_primary_key_path,
                selected_integration_id=gig_selected_integration_id,
            )
            gig_id = str(gig.get("id") or "").strip()
            if not gig_id or gig_id in seen_gig_ids:
                continue
            seen_gig_ids.add(gig_id)
            merged_gigs.append(gig)

    integration_state = await _derive_legacy_program_integration_state_from_sections(db)
    return {
        "stages": merged_stages,
        "gigs": merged_gigs,
        "gig_ids": [str(gig.get("id") or "").strip() for gig in merged_gigs if str(gig.get("id") or "").strip()],
        **integration_state,
    }


async def backfill_program_catalog_links_from_generated_pages(db) -> None:
    pages_coll = db["pages"]
    link_by_stage_id: dict[str, dict[str, str]] = {}
    link_by_gig_id: dict[str, dict[str, str]] = {}

    async for page_doc in pages_coll.find(
        {
            "template_managed": True,
            "template_source_type": {"$in": ["program_stage", "program_gig"]},
        },
        {"template_source_type": 1, "template_source_id": 1, "slug": 1},
    ):
        source_type = str(page_doc.get("template_source_type") or "").strip().lower()
        source_id = str(page_doc.get("template_source_id") or "").strip()
        slug = str(page_doc.get("slug") or "").strip().strip("/")
        if not slug or not source_id.startswith("program:"):
            continue

        if source_type == "program_stage" and source_id.startswith("program:stage:"):
            item_id = str(source_id.removeprefix("program:stage:") or "").strip()
            if item_id and item_id not in link_by_stage_id:
                link_by_stage_id[item_id] = {"page_slug": slug, "item_url": f"/{slug}"}
            continue

        if source_type == "program_gig" and source_id.startswith("program:gig:"):
            item_id = str(source_id.removeprefix("program:gig:") or "").strip()
            if item_id and item_id not in link_by_gig_id:
                link_by_gig_id[item_id] = {"page_slug": slug, "item_url": f"/{slug}"}

    if link_by_stage_id:
        shared_doc = await _load_shared_doc(db)
        normalized = normalize_program_shared_content_snapshot(shared_doc)
        stages: list[dict[str, Any]] = []
        changed = False
        for stage in normalized.get("stages", []):
            next_stage = deepcopy(stage)
            stage_id = str(next_stage.get("id") or "").strip()
            link_payload = link_by_stage_id.get(stage_id)
            if link_payload and (
                not str(next_stage.get("page_slug") or "").strip()
                or not str(next_stage.get("item_url") or "").strip()
            ):
                next_stage["page_slug"] = link_payload["page_slug"]
                next_stage["item_url"] = link_payload["item_url"]
                changed = True
            stages.append(next_stage)
        if changed:
            await db[PROGRAM_SHARED_COLLECTION].update_one(
                {"_id": PROGRAM_SHARED_DOC_ID},
                {"$set": {"stages": stages, "updated_at": _safe_datetime_utc()}},
                upsert=True,
            )

    if link_by_gig_id:
        operations: list[UpdateOne] = []
        now = _safe_datetime_utc()
        for gig_id, link_payload in link_by_gig_id.items():
            operations.append(
                UpdateOne(
                    {
                        "_id": gig_id,
                        "$or": [
                            {"page_slug": {"$in": ["", None]}},
                            {"page_slug": {"$exists": False}},
                            {"item_url": {"$in": ["", None]}},
                            {"item_url": {"$exists": False}},
                        ],
                    },
                    {
                        "$set": {
                            "page_slug": link_payload["page_slug"],
                            "item_url": link_payload["item_url"],
                            "updated_at": now,
                        }
                    },
                )
            )
        if operations:
            await db[PROGRAM_GIGS_COLLECTION].bulk_write(operations, ordered=False)


async def migrate_program_gigs_to_collection(db) -> dict[str, Any]:
    now = _safe_datetime_utc()
    shared_doc = await _load_shared_doc(db)
    shared_snapshot = normalize_program_shared_content_snapshot(shared_doc)
    legacy_sections_snapshot = await _derive_program_shared_legacy_content_from_sections(db)
    shared_gig_primary_key_path = integration_output_primary_key_path_from_cache_state(
        shared_snapshot.get("program_gigs_integration_mapping_cache_state")
    )
    shared_gig_selected_integration_id = integration_selected_id_from_mapping(
        shared_snapshot.get("program_gigs_integration_mapping")
    )

    shared_gigs = shared_snapshot.get("gigs") if isinstance(shared_snapshot.get("gigs"), list) else []
    section_gigs = legacy_sections_snapshot.get("gigs") if isinstance(legacy_sections_snapshot.get("gigs"), list) else []
    shared_gig_ids = _normalize_gig_id_list(shared_snapshot.get("gig_ids"))
    _append_unique_ids(shared_gig_ids, [str(gig.get("id") or "").strip() for gig in shared_gigs])
    _append_unique_ids(shared_gig_ids, _normalize_gig_id_list(legacy_sections_snapshot.get("gig_ids")))

    upserted_gig_ids = await _upsert_program_gig_docs(
        db,
        [*shared_gigs, *section_gigs],
        now=now,
        primary_key_path=shared_gig_primary_key_path,
        selected_integration_id=shared_gig_selected_integration_id,
    )
    if upserted_gig_ids:
        shared_gig_ids = upserted_gig_ids

    if not shared_gig_ids:
        shared_gig_ids = await _load_all_program_gig_ids(db)

    shared_stages = shared_snapshot.get("stages") if isinstance(shared_snapshot.get("stages"), list) else []
    if not shared_stages:
        shared_stages = (
            legacy_sections_snapshot.get("stages")
            if isinstance(legacy_sections_snapshot.get("stages"), list)
            else []
        )
    shared_stages = _dedupe_rows_by_id(shared_stages)

    shared_stage_mapping = _normalize_program_shared_metadata(
        shared_snapshot.get("program_stages_integration_mapping")
    ) or _normalize_program_shared_metadata(
        legacy_sections_snapshot.get("program_stages_integration_mapping")
    )
    shared_stage_cache_state = _normalize_program_shared_metadata(
        shared_snapshot.get("program_stages_integration_mapping_cache_state")
    ) or _normalize_program_shared_metadata(
        legacy_sections_snapshot.get("program_stages_integration_mapping_cache_state")
    )

    shared_gig_mapping = _normalize_program_shared_metadata(
        shared_snapshot.get("program_gigs_integration_mapping")
    ) or _normalize_program_shared_metadata(
        legacy_sections_snapshot.get("program_gigs_integration_mapping")
    )
    shared_gig_cache_state = _normalize_program_shared_metadata(
        shared_snapshot.get("program_gigs_integration_mapping_cache_state")
    ) or _normalize_program_shared_metadata(
        legacy_sections_snapshot.get("program_gigs_integration_mapping_cache_state")
    )

    next_shared_core = {
        "stages": deepcopy(shared_stages),
        "gig_ids": deepcopy(shared_gig_ids),
        "program_stages_integration_mapping": deepcopy(shared_stage_mapping),
        "program_stages_integration_mapping_cache_state": deepcopy(shared_stage_cache_state),
        "program_gigs_integration_mapping": deepcopy(shared_gig_mapping),
        "program_gigs_integration_mapping_cache_state": deepcopy(shared_gig_cache_state),
    }
    current_shared_core = {
        "stages": shared_snapshot.get("stages", []),
        "gig_ids": _normalize_gig_id_list(shared_snapshot.get("gig_ids")),
        "program_stages_integration_mapping": shared_snapshot.get("program_stages_integration_mapping", {}),
        "program_stages_integration_mapping_cache_state": shared_snapshot.get(
            "program_stages_integration_mapping_cache_state",
            {},
        ),
        "program_gigs_integration_mapping": shared_snapshot.get("program_gigs_integration_mapping", {}),
        "program_gigs_integration_mapping_cache_state": shared_snapshot.get(
            "program_gigs_integration_mapping_cache_state",
            {},
        ),
    }
    if (
        not shared_doc
        or "gigs" in shared_doc
        or shared_doc.get("program_section_shared_cleanup_version") != PROGRAM_SECTION_SHARED_CLEANUP_VERSION
        or current_shared_core != next_shared_core
    ):
        await db[PROGRAM_SHARED_COLLECTION].update_one(
            {"_id": PROGRAM_SHARED_DOC_ID},
            {
                "$set": {
                    **next_shared_core,
                    "program_section_shared_cleanup_version": PROGRAM_SECTION_SHARED_CLEANUP_VERSION,
                    "updated_at": now,
                },
                "$unset": {"gigs": ""},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    async for section_doc in db["sections"].find({"section_type": "program"}, {"_id": 1, "type_data": 1}):
        type_data = section_doc.get("type_data") if isinstance(section_doc.get("type_data"), dict) else {}
        raw_local_stages = type_data.get("stages") if isinstance(type_data.get("stages"), list) else []
        raw_local_gigs = type_data.get("gigs") if isinstance(type_data.get("gigs"), list) else []
        local_ids = _normalize_gig_id_list(type_data.get("gig_ids"))
        if raw_local_gigs:
            local_snapshot = normalize_program_shared_content_snapshot(
                {
                    "gigs": raw_local_gigs,
                    "program_gigs_integration_mapping": (
                        type_data.get("program_gigs_integration_mapping")
                        if type_data.get("program_gigs_integration_mapping") is not None
                        else type_data.get("programGigsIntegrationMapping")
                    ),
                    "program_gigs_integration_mapping_cache_state": (
                        type_data.get("program_gigs_integration_mapping_cache_state")
                        if type_data.get("program_gigs_integration_mapping_cache_state") is not None
                        else type_data.get("programGigsIntegrationMappingCacheState")
                    ),
                }
            )
            _append_unique_ids(local_ids, _normalize_gig_id_list(local_snapshot.get("gig_ids")))
        patch: dict[str, Any] = {"updated_at": now}
        unset: dict[str, Any] = {}
        if raw_local_stages or "stages" in type_data:
            unset["type_data.stages"] = ""
        if raw_local_gigs or "gigs" in type_data:
            unset["type_data.gigs"] = ""
        for key in (
            "program_stages_integration_mapping",
            "programStagesIntegrationMapping",
            "program_stages_integration_mapping_cache_state",
            "programStagesIntegrationMappingCacheState",
            "program_gigs_integration_mapping",
            "programGigsIntegrationMapping",
            "program_gigs_integration_mapping_cache_state",
            "programGigsIntegrationMappingCacheState",
        ):
            if key in type_data:
                unset[f"type_data.{key}"] = ""
        if local_ids and local_ids != type_data.get("gig_ids"):
            patch["type_data.gig_ids"] = local_ids
        if patch.keys() != {"updated_at"} or unset:
            update_doc: dict[str, Any] = {"$set": patch}
            if unset:
                update_doc["$unset"] = unset
            await db["sections"].update_one({"_id": section_doc["_id"]}, update_doc)

    await backfill_program_catalog_links_from_generated_pages(db)
    return {
        "gig_count": await db[PROGRAM_GIGS_COLLECTION].count_documents({}),
        "shared_gig_ids": len(shared_gig_ids),
    }


async def capture_program_shared_content(
    db,
    *,
    ids: list[str] | None = None,
    gig_id: str | None = None,
    stage_id: str | None = None,
    day: str | None = None,
    day_start_hour: int = 10,
    day_end_hour: int = 6,
) -> dict[str, Any]:
    shared_doc = await _load_shared_doc(db)
    needs_migration = (
        not shared_doc
        or "gigs" in shared_doc
        or "gig_ids" not in shared_doc
        or shared_doc.get("program_section_shared_cleanup_version") != PROGRAM_SECTION_SHARED_CLEANUP_VERSION
    )
    if needs_migration:
        await migrate_program_gigs_to_collection(db)
        shared_doc = await _load_shared_doc(db)
    normalized = normalize_program_shared_content_snapshot(shared_doc)
    gig_primary_key_path = integration_output_primary_key_path_from_cache_state(
        normalized.get("program_gigs_integration_mapping_cache_state")
    )
    gig_selected_integration_id = integration_selected_id_from_mapping(
        normalized.get("program_gigs_integration_mapping")
    )
    gig_ids = _normalize_gig_id_list(normalized.get("gig_ids"))
    gigs = await load_program_gig_docs(
        db,
        ordered_gig_ids=gig_ids,
        ids=ids,
        gig_id=gig_id,
        stage_id=stage_id,
        day=day,
        day_start_hour=day_start_hour,
        day_end_hour=day_end_hour,
        primary_key_path=gig_primary_key_path,
        selected_integration_id=gig_selected_integration_id,
    )
    if not any([ids, gig_id, stage_id, day]):
        loaded_gig_ids = {
            str(gig.get("id") or "").strip()
            for gig in gigs
            if isinstance(gig, dict) and str(gig.get("id") or "").strip()
        }
        all_gigs = await load_program_gig_docs(
            db,
            primary_key_path=gig_primary_key_path,
            selected_integration_id=gig_selected_integration_id,
        )
        missing_gigs = [
            gig
            for gig in all_gigs
            if isinstance(gig, dict)
            and str(gig.get("id") or "").strip()
            and str(gig.get("id") or "").strip() not in loaded_gig_ids
        ]
        if missing_gigs:
            gigs = [*gigs, *missing_gigs]
            for gig in missing_gigs:
                gig_id_value = str(gig.get("id") or "").strip()
                if gig_id_value and gig_id_value not in gig_ids:
                    gig_ids.append(gig_id_value)

    if not gig_ids and not any([ids, gig_id, stage_id, day]):
        gig_ids = [
            str(gig.get("id") or "").strip()
            for gig in gigs
            if isinstance(gig, dict) and str(gig.get("id") or "").strip()
        ]
    elif (
        not any([ids, gig_id, stage_id, day])
        and len(gigs) == len(gig_ids)
    ):
        resolved_gig_ids = [
            str(gig.get("id") or "").strip()
            for gig in gigs
            if isinstance(gig, dict) and str(gig.get("id") or "").strip()
        ]
        if len(resolved_gig_ids) == len(gig_ids):
            gig_ids = resolved_gig_ids
    return {
        **normalized,
        "gig_ids": gig_ids,
        "gigs": gigs,
    }


async def apply_program_shared_content(db, shared_content: Any) -> bool:
    source = shared_content if isinstance(shared_content, dict) else {}
    has_incoming_gigs_payload = isinstance(source.get("gigs"), list)
    normalized = normalize_program_shared_content_snapshot(shared_content)
    gig_primary_key_path = integration_output_primary_key_path_from_cache_state(
        normalized.get("program_gigs_integration_mapping_cache_state")
    )
    gig_selected_integration_id = integration_selected_id_from_mapping(
        normalized.get("program_gigs_integration_mapping")
    )
    current = await capture_program_shared_content(db)
    current_gig_ids = _normalize_gig_id_list(current.get("gig_ids"))
    incoming_gigs = normalized.get("gigs") if isinstance(normalized.get("gigs"), list) else []
    incoming_gig_ids = _normalize_gig_id_list(normalized.get("gig_ids"))
    if has_incoming_gigs_payload:
        incoming_gig_ids = await _upsert_program_gig_docs(
            db,
            incoming_gigs,
            primary_key_path=gig_primary_key_path,
            selected_integration_id=gig_selected_integration_id,
        )
        removed_ids = sorted(set(current_gig_ids) - set(incoming_gig_ids))
        if removed_ids:
            await db[PROGRAM_GIGS_COLLECTION].delete_many({"_id": {"$in": removed_ids}})
    if not incoming_gig_ids and incoming_gigs:
        incoming_gig_ids = [
            str(gig.get("id") or "").strip()
            for gig in incoming_gigs
            if str(gig.get("id") or "").strip()
        ]

    next_shared = {
        "stages": normalized.get("stages", []),
        "gig_ids": incoming_gig_ids,
        "program_stages_integration_mapping": normalized.get("program_stages_integration_mapping", {}),
        "program_stages_integration_mapping_cache_state": normalized.get(
            "program_stages_integration_mapping_cache_state",
            {},
        ),
        "program_gigs_integration_mapping": normalized.get("program_gigs_integration_mapping", {}),
        "program_gigs_integration_mapping_cache_state": normalized.get(
            "program_gigs_integration_mapping_cache_state",
            {},
        ),
    }
    current_shared = {
        "stages": current.get("stages", []),
        "gig_ids": current_gig_ids,
        "program_stages_integration_mapping": current.get("program_stages_integration_mapping", {}),
        "program_stages_integration_mapping_cache_state": current.get(
            "program_stages_integration_mapping_cache_state",
            {},
        ),
        "program_gigs_integration_mapping": current.get("program_gigs_integration_mapping", {}),
        "program_gigs_integration_mapping_cache_state": current.get(
            "program_gigs_integration_mapping_cache_state",
            {},
        ),
    }
    if current_shared == next_shared and not incoming_gigs:
        return False

    now = _safe_datetime_utc()
    await db[PROGRAM_SHARED_COLLECTION].update_one(
        {"_id": PROGRAM_SHARED_DOC_ID},
        {
            "$set": {
                **deepcopy(next_shared),
                "program_section_shared_cleanup_version": PROGRAM_SECTION_SHARED_CLEANUP_VERSION,
                "updated_at": now,
            },
            "$unset": {"gigs": ""},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return True


async def replace_program_gig_catalog(db, raw_gigs: list[Any]) -> tuple[list[str], list[str]]:
    current_snapshot = await capture_program_shared_content(db)
    current_ids = set(_normalize_gig_id_list(current_snapshot.get("gig_ids")))
    gig_primary_key_path = integration_output_primary_key_path_from_cache_state(
        current_snapshot.get("program_gigs_integration_mapping_cache_state")
    )
    gig_selected_integration_id = integration_selected_id_from_mapping(
        current_snapshot.get("program_gigs_integration_mapping")
    )
    now = _safe_datetime_utc()
    next_ids = await _upsert_program_gig_docs(
        db,
        raw_gigs,
        now=now,
        primary_key_path=gig_primary_key_path,
        selected_integration_id=gig_selected_integration_id,
    )
    next_id_set = set(next_ids)
    removed_ids = sorted(current_ids - next_id_set)
    if removed_ids:
        await db[PROGRAM_GIGS_COLLECTION].delete_many({"_id": {"$in": removed_ids}})
    await db[PROGRAM_SHARED_COLLECTION].update_one(
        {"_id": PROGRAM_SHARED_DOC_ID},
        {
            "$set": {
                "gig_ids": next_ids,
                "updated_at": now,
            },
            "$unset": {"gigs": ""},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return next_ids, removed_ids


async def update_program_gig(db, gig_id: str, raw_gig: Any) -> dict[str, Any]:
    normalized_id = str(gig_id or "").strip()
    if not normalized_id:
        raise ValueError("Missing gig ID")
    normalized = normalize_program_gig_for_storage(raw_gig)
    normalized["id"] = normalized_id
    now = _safe_datetime_utc()
    await db[PROGRAM_GIGS_COLLECTION].update_one(
        {"_id": normalized_id},
        {
            "$set": {
                **deepcopy(normalized),
                "updated_at": now,
            },
            "$unset": _program_gig_storage_unset_payload(),
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    shared_doc = await _load_shared_doc(db)
    shared_ids = _normalize_gig_id_list(shared_doc.get("gig_ids"))
    if normalized_id not in shared_ids:
        shared_ids.append(normalized_id)
        await db[PROGRAM_SHARED_COLLECTION].update_one(
            {"_id": PROGRAM_SHARED_DOC_ID},
            {"$set": {"gig_ids": shared_ids, "updated_at": now}, "$unset": {"gigs": ""}},
            upsert=True,
        )
    return normalized


async def update_program_gig_link(db, gig_id: str, *, slug: str, item_url: str | None = None) -> None:
    normalized_id = str(gig_id or "").strip()
    if not normalized_id:
        return
    normalized_slug = str(slug or "").strip().strip("/")
    await db[PROGRAM_GIGS_COLLECTION].update_one(
        {"_id": normalized_id},
        {
            "$set": {
                "page_slug": normalized_slug,
                "item_url": str(item_url if item_url is not None else f"/{normalized_slug}" if normalized_slug else ""),
                "updated_at": _safe_datetime_utc(),
            }
        },
    )


async def clear_program_gig_links(
    db,
    gig_ids: set[str] | list[str],
    *,
    deleted_slugs: set[str] | None = None,
) -> None:
    ids = _normalize_gig_id_list(list(gig_ids))
    if not ids:
        return
    query: dict[str, Any] = {"_id": {"$in": ids}}
    normalized_slugs = {str(slug or "").strip().strip("/") for slug in (deleted_slugs or set()) if str(slug or "").strip()}
    if normalized_slugs:
        query["$or"] = [
            {"page_slug": {"$in": list(normalized_slugs)}},
            {"item_url": {"$in": [f"/{slug}" for slug in normalized_slugs]}},
            {"item_url": {"$in": list(normalized_slugs)}},
        ]
    await db[PROGRAM_GIGS_COLLECTION].update_many(
        query,
        {"$set": {"page_slug": "", "item_url": "", "updated_at": _safe_datetime_utc()}},
    )
