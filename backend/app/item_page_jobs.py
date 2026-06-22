from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta
import logging
import time
from typing import Any

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument

from app import program_catalog
from app.collection_names import ITEM_PAGE_GENERATION_JOBS_COLLECTION, PROGRAM_SHARED_COLLECTION
from app.job_retention import job_expires_at
from app.revisioning import PROGRAM_SHARED_DOC_ID
from app.template_sync import (
    resolve_active_item_page_template,
    sync_blog_item_page_by_id,
    sync_program_gig_section_pages_report,
    sync_program_stage_section_pages_report,
)

ITEM_PAGE_JOB_RUNNING_STATUSES = {"queued", "running"}
ITEM_PAGE_JOB_STALE_AFTER = timedelta(minutes=2)
ITEM_PAGE_JOB_HEARTBEAT_SECONDS = 30
_ITEM_PAGE_JOB_TASKS: set[asyncio.Task[Any]] = set()
_ITEM_PAGE_JOB_TASK_IDS: set[str] = set()
_PROGRAM_ITEM_PAGE_JOB_SEMAPHORE = asyncio.Semaphore(1)
_DEFAULT_ITEM_PAGE_JOB_SEMAPHORE = asyncio.Semaphore(2)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.utcnow()


def _safe_object_id(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _normalize_source_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"blog", "program_stage", "program_gig"}:
        return normalized
    return ""


def _normalize_source_key(value: Any) -> str:
    return str(value or "").strip()


def _format_job_response(doc: dict | None) -> dict | None:
    if not isinstance(doc, dict):
        return None
    status = str(doc.get("status") or "queued").strip().lower() or "queued"
    source_type = _normalize_source_type(doc.get("source_type"))
    source_id = str(doc.get("source_id") or "").strip()
    source_key = _normalize_source_key(doc.get("source_key"))
    slug = str(doc.get("result_slug") or "").strip() or None
    error = str(doc.get("error") or "").strip() or None

    return {
        "job_id": str(doc.get("_id") or ""),
        "status": status,
        "source_type": source_type,
        "source_id": source_id,
        "source_key": source_key,
        "slug": slug,
        "error": error,
        "attempts": int(doc.get("attempts") or 0),
        "created_at": doc.get("created_at"),
        "started_at": doc.get("started_at"),
        "finished_at": doc.get("finished_at"),
        "updated_at": doc.get("updated_at"),
    }


def _track_item_page_job_task(task: asyncio.Task[Any], job_id: str) -> None:
    _ITEM_PAGE_JOB_TASKS.add(task)

    def _cleanup(done_task: asyncio.Task[Any]) -> None:
        _ITEM_PAGE_JOB_TASKS.discard(done_task)
        _ITEM_PAGE_JOB_TASK_IDS.discard(job_id)

    task.add_done_callback(_cleanup)


def _is_item_page_job_task_scheduled(job_id: Any) -> bool:
    normalized_job_id = str(job_id or "").strip()
    return bool(normalized_job_id and normalized_job_id in _ITEM_PAGE_JOB_TASK_IDS)


def _select_item_page_job_semaphore(source_type: str) -> asyncio.Semaphore:
    if _normalize_source_type(source_type) in {"program_stage", "program_gig"}:
        return _PROGRAM_ITEM_PAGE_JOB_SEMAPHORE
    return _DEFAULT_ITEM_PAGE_JOB_SEMAPHORE


async def _heartbeat_running_item_page_job(jobs_coll, job_oid: ObjectId) -> None:
    while True:
        await asyncio.sleep(ITEM_PAGE_JOB_HEARTBEAT_SECONDS)
        try:
            await jobs_coll.update_one(
                {"_id": job_oid, "status": "running"},
                {"$set": {"updated_at": _now()}},
            )
        except Exception:
            logger.warning(
                "item_page_job.heartbeat_failed job_id=%s",
                str(job_oid),
                exc_info=True,
            )


def _derive_job_source_key(source_type: str, source_id: str) -> str:
    normalized_source_type = _normalize_source_type(source_type)
    normalized_source_id = str(source_id or "").strip()
    if not normalized_source_type or not normalized_source_id:
        return ""
    if normalized_source_type == "blog":
        return f"blog:{normalized_source_id}"
    if normalized_source_type == "program_stage":
        return f"program:stage:{normalized_source_id}"
    if normalized_source_type == "program_gig":
        return f"program:gig:{normalized_source_id}"
    return ""


async def _resolve_program_shared_item_slug(db, *, kind: str, item_id: str) -> str | None:
    normalized_kind = "stage" if str(kind or "").strip().lower() == "stage" else "gig"
    normalized_item_id = str(item_id or "").strip()
    if not normalized_item_id:
        return None

    if normalized_kind == "gig":
        shared_payload = await program_catalog.capture_program_shared_content(
            db,
            gig_id=normalized_item_id,
        )
        rows = shared_payload.get("gigs") if isinstance(shared_payload, dict) else []
    else:
        shared_doc = await db[PROGRAM_SHARED_COLLECTION].find_one({"_id": PROGRAM_SHARED_DOC_ID})
        if not isinstance(shared_doc, dict):
            return None
        rows = shared_doc.get("stages")
    if not isinstance(rows, list):
        return None

    for row in rows:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("id") or "").strip()
        row_external_key = str(row.get("integration_item_key") or "").strip()
        if row_id != normalized_item_id and row_external_key != normalized_item_id:
            continue
        slug = str(row.get("page_slug") or "").strip()
        return slug or None
    return None


async def _execute_item_page_generation_job(db, job_id: str) -> None:
    jobs_coll = db[ITEM_PAGE_GENERATION_JOBS_COLLECTION]
    job_oid = _safe_object_id(job_id)
    if job_oid is None:
        return

    pending = await jobs_coll.find_one(
        {"_id": job_oid},
        {"source_type": 1},
    )
    semaphore = _select_item_page_job_semaphore(
        pending.get("source_type") if isinstance(pending, dict) else ""
    )

    async with semaphore:
        now = _now()
        stale_cutoff = now - ITEM_PAGE_JOB_STALE_AFTER
        claimed = await jobs_coll.find_one_and_update(
            {
                "_id": job_oid,
                "$or": [
                    {"status": "queued"},
                    {"status": "running", "updated_at": {"$lt": stale_cutoff}},
                ],
            },
            {
                "$set": {
                    "status": "running",
                    "started_at": now,
                    "updated_at": now,
                    "expires_at": job_expires_at("running", now),
                    "error": None,
                },
                "$inc": {"attempts": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if not isinstance(claimed, dict):
            return

        source_type = _normalize_source_type(claimed.get("source_type"))
        source_id = str(claimed.get("source_id") or "").strip()
        source_key = str(claimed.get("source_key") or "").strip()
        source_context = claimed.get("source_context") if isinstance(claimed.get("source_context"), dict) else {}
        started_at = time.perf_counter()
        heartbeat_task = asyncio.create_task(_heartbeat_running_item_page_job(jobs_coll, job_oid))
        final_status = "running"
        generated_slug_for_log: str | None = None
        skipped_for_log = False
        error_for_log: str | None = None

        logger.info(
            "item_page_job.start job_id=%s source_type=%s source_id=%s source_key=%s attempts=%d",
            str(job_oid),
            source_type,
            source_id,
            source_key,
            int(claimed.get("attempts") or 0),
        )

        try:
            generated_slug: str | None = None
            skipped = False
            if source_type == "blog":
                force_parent_route = str(source_context.get("parent_route") or "").strip() or None
                force_slug_source_field = str(source_context.get("slug_source_field") or "").strip() or None
                generated_slug = await sync_blog_item_page_by_id(
                    db,
                    source_id,
                    force_parent_route=force_parent_route,
                    force_slug_source_field=force_slug_source_field,
                )
            elif source_type == "program_stage":
                report = await sync_program_stage_section_pages_report(
                    db,
                    {"_id": "program_shared_async", "section_type": "program", "type_data": {}},
                    item_id=source_id,
                )
                skipped = bool(report.get("skipped"))
                if int(report.get("generated_count", 0) or 0) > 0:
                    generated_slug = await _resolve_program_shared_item_slug(
                        db,
                        kind="stage",
                        item_id=source_id,
                    )
            elif source_type == "program_gig":
                report = await sync_program_gig_section_pages_report(
                    db,
                    {"_id": "program_shared_async", "section_type": "program", "type_data": {}},
                    item_id=source_id,
                )
                skipped = bool(report.get("skipped"))
                if int(report.get("generated_count", 0) or 0) > 0:
                    generated_slug = await _resolve_program_shared_item_slug(
                        db,
                        kind="gig",
                        item_id=source_id,
                    )
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported item-page job source type: {source_type}")

            finished_at = _now()
            completed_expires_at = job_expires_at("completed", finished_at)
            failed_expires_at = job_expires_at("failed", finished_at)
            if skipped:
                final_status = "completed"
                skipped_for_log = True
                await jobs_coll.update_one(
                    {"_id": job_oid},
                    {
                        "$set": {
                            "status": "completed",
                            "result_slug": None,
                            "error": None,
                            "finished_at": finished_at,
                            "updated_at": finished_at,
                            "expires_at": completed_expires_at,
                        }
                    },
                )
            elif generated_slug:
                final_status = "completed"
                generated_slug_for_log = str(generated_slug).strip()
                await jobs_coll.update_one(
                    {"_id": job_oid},
                    {
                        "$set": {
                            "status": "completed",
                            "result_slug": generated_slug_for_log,
                            "error": None,
                            "finished_at": finished_at,
                            "updated_at": finished_at,
                            "expires_at": completed_expires_at,
                        }
                    },
                )
            else:
                final_status = "failed"
                error_for_log = "No generated page was produced for this item."
                await jobs_coll.update_one(
                    {"_id": job_oid},
                    {
                        "$set": {
                            "status": "failed",
                            "result_slug": None,
                            "error": error_for_log,
                            "finished_at": finished_at,
                            "updated_at": finished_at,
                            "expires_at": failed_expires_at,
                        }
                    },
                )
        except HTTPException as exc:
            finished_at = _now()
            final_status = "failed"
            error_for_log = str(exc.detail)
            await jobs_coll.update_one(
                {"_id": job_oid},
                {
                    "$set": {
                        "status": "failed",
                        "result_slug": None,
                        "error": error_for_log,
                        "finished_at": finished_at,
                        "updated_at": finished_at,
                        "expires_at": job_expires_at("failed", finished_at),
                    }
                },
            )
        except Exception as exc:
            finished_at = _now()
            final_status = "failed"
            error_for_log = str(exc)
            logger.exception(
                "item_page_job.failed job_id=%s source_type=%s source_id=%s",
                str(job_oid),
                source_type,
                source_id,
            )
            await jobs_coll.update_one(
                {"_id": job_oid},
                {
                    "$set": {
                        "status": "failed",
                        "result_slug": None,
                        "error": error_for_log,
                        "finished_at": finished_at,
                        "updated_at": finished_at,
                        "expires_at": job_expires_at("failed", finished_at),
                    }
                },
            )
        finally:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
            logger.info(
                "item_page_job.finish job_id=%s source_type=%s source_id=%s status=%s skipped=%s slug=%s elapsed_ms=%d error=%s",
                str(job_oid),
                source_type,
                source_id,
                final_status,
                skipped_for_log,
                generated_slug_for_log or "",
                int((time.perf_counter() - started_at) * 1000),
                error_for_log or "",
            )


def _schedule_item_page_job_execution(db, job_id: str) -> None:
    normalized_job_id = str(job_id or "").strip()
    if not normalized_job_id:
        return
    if normalized_job_id in _ITEM_PAGE_JOB_TASK_IDS:
        return
    _ITEM_PAGE_JOB_TASK_IDS.add(normalized_job_id)
    task = asyncio.create_task(_execute_item_page_generation_job(db, normalized_job_id))
    _track_item_page_job_task(task, normalized_job_id)


async def enqueue_item_page_generation_job(
    db,
    *,
    source_type: str,
    source_id: str,
    source_key: str | None = None,
    source_context: dict | None = None,
) -> dict:
    jobs_coll = db[ITEM_PAGE_GENERATION_JOBS_COLLECTION]
    normalized_source_type = _normalize_source_type(source_type)
    normalized_source_id = str(source_id or "").strip()
    normalized_source_key = _normalize_source_key(source_key) or _derive_job_source_key(
        normalized_source_type,
        normalized_source_id,
    )
    if not normalized_source_type or not normalized_source_id or not normalized_source_key:
        raise HTTPException(status_code=400, detail="Invalid source payload for item-page generation job")

    now = _now()
    stale_cutoff = now - ITEM_PAGE_JOB_STALE_AFTER
    existing = await jobs_coll.find_one(
        {
            "source_key": normalized_source_key,
            "status": {"$in": list(ITEM_PAGE_JOB_RUNNING_STATUSES)},
            "$or": [
                {"expires_at": {"$exists": False}},
                {"expires_at": None},
                {"expires_at": {"$gt": now}},
            ],
        },
        sort=[("created_at", -1)],
    )
    if isinstance(existing, dict):
        existing_status = str(existing.get("status") or "").strip().lower()
        existing_updated_at = existing.get("updated_at")
        if (
            existing_status == "running"
            and isinstance(existing_updated_at, datetime)
            and existing_updated_at < stale_cutoff
            and not _is_item_page_job_task_scheduled(existing.get("_id"))
        ):
            requeued = await jobs_coll.find_one_and_update(
                {"_id": existing.get("_id")},
                {
                    "$set": {
                        "status": "queued",
                        "error": None,
                        "updated_at": now,
                        "finished_at": None,
                        "expires_at": job_expires_at("queued", now),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
            if isinstance(requeued, dict):
                _schedule_item_page_job_execution(db, str(requeued.get("_id")))
                return {
                    **(_format_job_response(requeued) or {}),
                    "deduped": False,
                }

        _schedule_item_page_job_execution(db, str(existing.get("_id")))
        return {
            **(_format_job_response(existing) or {}),
            "deduped": True,
        }

    insert_payload = {
        "source_type": normalized_source_type,
        "source_id": normalized_source_id,
        "source_key": normalized_source_key,
        "source_context": source_context if isinstance(source_context, dict) else {},
        "status": "queued",
        "result_slug": None,
        "error": None,
        "attempts": 0,
        "created_at": now,
        "started_at": None,
        "finished_at": None,
        "updated_at": now,
        "expires_at": job_expires_at("queued", now),
    }
    result = await jobs_coll.insert_one(insert_payload)
    created = await jobs_coll.find_one({"_id": result.inserted_id})
    if not isinstance(created, dict):
        raise HTTPException(status_code=500, detail="Failed to enqueue item-page generation job")
    _schedule_item_page_job_execution(db, str(created.get("_id")))
    return {
        **(_format_job_response(created) or {}),
        "deduped": False,
    }


async def get_item_page_generation_job(
    db,
    job_id: str,
    *,
    ensure_progress: bool = True,
) -> dict:
    jobs_coll = db[ITEM_PAGE_GENERATION_JOBS_COLLECTION]
    job_oid = _safe_object_id(job_id)
    if job_oid is None:
        raise HTTPException(status_code=400, detail="Invalid job ID")

    job_doc = await jobs_coll.find_one({"_id": job_oid})
    if not isinstance(job_doc, dict):
        raise HTTPException(status_code=404, detail="Item-page generation job not found")

    if ensure_progress:
        status = str(job_doc.get("status") or "").strip().lower()
        updated_at = job_doc.get("updated_at")
        has_scheduled_task = _is_item_page_job_task_scheduled(job_oid)
        is_stale_running = (
            status == "running"
            and isinstance(updated_at, datetime)
            and updated_at < (_now() - ITEM_PAGE_JOB_STALE_AFTER)
            and not has_scheduled_task
        )
        if status == "queued" or is_stale_running:
            if is_stale_running:
                now = _now()
                refreshed = await jobs_coll.find_one_and_update(
                    {"_id": job_oid},
                    {
                        "$set": {
                            "status": "queued",
                            "updated_at": now,
                            "expires_at": job_expires_at("queued", now),
                        }
                    },
                    return_document=ReturnDocument.AFTER,
                )
                if isinstance(refreshed, dict):
                    job_doc = refreshed
            _schedule_item_page_job_execution(db, str(job_oid))
            latest = await jobs_coll.find_one({"_id": job_oid})
            if isinstance(latest, dict):
                job_doc = latest

    formatted = _format_job_response(job_doc)
    if not isinstance(formatted, dict):
        raise HTTPException(status_code=500, detail="Failed to format item-page generation job")
    return formatted


async def enqueue_blog_item_page_generation(
    db,
    item_id: str,
    *,
    parent_route: str | None = None,
    slug_source_field: str | None = None,
) -> dict | None:
    normalized_item_id = str(item_id or "").strip()
    if not normalized_item_id:
        raise HTTPException(status_code=400, detail="Missing blog item id for item-page job")
    active_template = await resolve_active_item_page_template(db, "blog", "item")
    if not active_template:
        return None
    source_context = {}
    if parent_route:
        source_context["parent_route"] = str(parent_route or "").strip()
    if slug_source_field:
        source_context["slug_source_field"] = str(slug_source_field or "").strip()
    return await enqueue_item_page_generation_job(
        db,
        source_type="blog",
        source_id=normalized_item_id,
        source_key=f"blog:{normalized_item_id}",
        source_context=source_context,
    )


async def enqueue_program_item_page_generation(
    db,
    *,
    kind: str,
    item_id: str,
) -> dict | None:
    normalized_kind = "stage" if str(kind or "").strip().lower() == "stage" else "gig"
    normalized_item_id = str(item_id or "").strip()
    if not normalized_item_id:
        raise HTTPException(status_code=400, detail=f"Missing program {normalized_kind} id for item-page job")
    active_template = await resolve_active_item_page_template(db, "program", normalized_kind)
    if not active_template:
        return None
    source_type = "program_stage" if normalized_kind == "stage" else "program_gig"
    source_key = f"program:{normalized_kind}:{normalized_item_id}"
    return await enqueue_item_page_generation_job(
        db,
        source_type=source_type,
        source_id=normalized_item_id,
        source_key=source_key,
        source_context={},
    )
