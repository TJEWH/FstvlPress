from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

JOB_ACTIVE_RETENTION = timedelta(days=7)
JOB_SUCCESS_RETENTION = timedelta(hours=24)
JOB_FAILURE_RETENTION = timedelta(days=7)

JOB_SUCCESS_STATUSES = {"completed", "succeeded"}
JOB_FAILURE_STATUSES = {"failed"}
JOB_TERMINAL_STATUSES = JOB_SUCCESS_STATUSES | JOB_FAILURE_STATUSES


def normalize_job_status(status: Any) -> str:
    return str(status or "").strip().lower()


def job_expires_at(status: Any, reference_time: datetime | None = None) -> datetime | None:
    normalized_status = normalize_job_status(status)
    now = reference_time or datetime.utcnow()
    if normalized_status in JOB_SUCCESS_STATUSES:
        return now + JOB_SUCCESS_RETENTION
    if normalized_status in JOB_FAILURE_STATUSES:
        return now + JOB_FAILURE_RETENTION
    if normalized_status in {"queued", "running"}:
        return now + JOB_ACTIVE_RETENTION
    return None
