"""FAQ shared catalog API (global items + topics)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db import get_client
from app.deps import get_current_user, require_permission
from app.models.faq import FAQSharedResponse, FAQSharedUpdate
from app.public_cache import invalidate_ttl_cache_key, invalidate_ttl_cache_prefix
from app.revisioning import (
    apply_faq_shared_content,
    capture_faq_shared_content,
    normalize_faq_shared_content_snapshot,
    push_faq_shared_content_revisions,
    snapshots_equal,
)
from app.security import KeycloakUser
from app.settings import settings

router = APIRouter(prefix="/faq", tags=["faq"])


def _db():
    return get_client()[settings.mongo_db]


@router.get(
    "/shared",
    response_model=FAQSharedResponse,
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_faq_shared():
    snapshot = await capture_faq_shared_content(_db())
    normalized = normalize_faq_shared_content_snapshot(snapshot)
    return FAQSharedResponse(**normalized)


@router.put(
    "/shared",
    response_model=FAQSharedResponse,
    dependencies=[Depends(require_permission("content:write"))],
)
async def put_faq_shared(
    payload: FAQSharedUpdate,
    user: KeycloakUser = Depends(get_current_user),
):
    db = _db()
    current_snapshot = normalize_faq_shared_content_snapshot(
        await capture_faq_shared_content(db)
    )

    incoming_items = (
        [
            entry.model_dump() if isinstance(entry, BaseModel) else entry
            for entry in (payload.items or [])
        ]
        if payload.items is not None
        else None
    )
    incoming_tags = (
        [
            entry.model_dump() if isinstance(entry, BaseModel) else entry
            for entry in (payload.tags or [])
        ]
        if payload.tags is not None
        else None
    )

    merged_snapshot = normalize_faq_shared_content_snapshot(
        {
            "items": incoming_items if incoming_items is not None else current_snapshot.get("items", []),
            "tags": incoming_tags if incoming_tags is not None else current_snapshot.get("tags", []),
        }
    )

    if not snapshots_equal(current_snapshot, merged_snapshot):
        await push_faq_shared_content_revisions(
            db,
            saved_by=user.username,
        )
        await apply_faq_shared_content(db, merged_snapshot)
        invalidate_ttl_cache_key("public:faq-bundle")
        invalidate_ttl_cache_prefix("public:page-bundle:")

    latest_snapshot = normalize_faq_shared_content_snapshot(
        await capture_faq_shared_content(db)
    )
    return FAQSharedResponse(**latest_snapshot)
