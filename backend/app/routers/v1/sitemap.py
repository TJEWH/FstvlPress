from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from app.collection_names import PAGE_HIT_DAYS_COLLECTION, PAGES_COLLECTION, SITEMAP_CONFIG_COLLECTION
from app.db import get_client
from app.deps import require_permission
from app.security import KeycloakUser
from app.settings import settings
from app.sitemap import (
    ADMIN_SITEMAP_CONFIG_KEY,
    HTACCESS_CLIENT_CACHING_FIELD,
    REDIRECT_ANONYMOUS_HIT_COUNT_FIELD,
    REDIRECT_LAST_TRIGGERED_AT_FIELD,
    REDIRECTS_COLLECTION,
    build_htaccess_client_caching_payload,
    build_public_robots_payload,
    build_public_sitemap_payload,
    find_active_redirect_doc,
    get_custom_robots_text,
    get_navigation_links_config,
    increment_redirect_anonymous_hit_count,
    is_external_url,
    normalize_custom_robots_text,
    normalize_external_nav_links,
    normalize_htaccess_client_cache_rules,
    normalize_footer_logo_url,
    normalize_internal_path,
    normalize_redirect_source_path,
    normalize_redirect_status_code,
    normalize_redirect_target,
    normalize_topbar_logo_url,
    _compute_effective_page_status,
    request_has_auth_credentials,
    resolve_public_base_url_from_request,
    serialize_redirect_doc,
    slug_to_path,
)

router = APIRouter(prefix="/sitemap", tags=["sitemap"])


def _db():
    return get_client()[settings.mongo_db]


class RedirectCreatePayload(BaseModel):
    source_path: str = Field(min_length=1, max_length=500)
    target_path: str | None = Field(default=None, max_length=2000)
    status_code: int = Field(default=301)
    is_active: bool = True
    expires_at: datetime | None = None


class RedirectPatchPayload(BaseModel):
    source_path: str | None = None
    target_path: str | None = None
    status_code: int | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None


class RobotsPatchPayload(BaseModel):
    custom_robots_txt: str = ""


class NavigationLinksPatchPayload(BaseModel):
    nav_external_links: list[dict] = Field(default_factory=list)
    footer_external_links: list[dict] = Field(default_factory=list)
    topbar_logo_url: str | None = None
    footer_logo_url: str | None = None


class HtaccessCachingPatchPayload(BaseModel):
    rules: list[dict] = Field(default_factory=list)


def _normalize_non_negative_int(value) -> int:
    try:
        numeric = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, numeric)


def _stats_day_range(days: int) -> list[str]:
    total_days = max(1, min(int(days or 30), 366))
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=total_days - 1)
    return [
        (start_date + timedelta(days=offset)).isoformat()
        for offset in range(total_days)
    ]


def _parse_stats_days(value) -> int | None:
    raw = str(value or "30").strip().lower()
    if raw in {"all", "all-time", "all_time"}:
        return None
    try:
        return max(1, min(int(raw), 366))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="days must be a number or 'all'")


def _parse_stats_day_key(value) -> datetime.date | None:
    raw = str(value or "").strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _stats_day_range_from_dates(start_date, end_date) -> list[str]:
    if not start_date or not end_date or start_date > end_date:
        return []
    total_days = (end_date - start_date).days + 1
    return [
        (start_date + timedelta(days=offset)).isoformat()
        for offset in range(total_days)
    ]


def _resolve_stats_parent_slug(slug: str, known_slugs: set[str]) -> str | None:
    if not slug or slug == "landing":
        return None
    parts = slug.split("/")
    for index in range(len(parts) - 1, 0, -1):
        parent_slug = "/".join(parts[:index])
        if parent_slug in known_slugs:
            return parent_slug
    if "landing" in known_slugs:
        return "landing"
    return None


def _format_stats_title(value) -> dict:
    if not isinstance(value, dict):
        return {"de": "", "en": ""}
    return {
        "de": str(value.get("de") or ""),
        "en": str(value.get("en") or ""),
    }


@router.get(
    "/summary",
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_sitemap_summary(request: Request):
    db = _db()
    payload = await build_public_sitemap_payload(
        db,
        public_base_url=resolve_public_base_url_from_request(request),
    )

    now = datetime.now(timezone.utc)
    redirect_docs = await db[REDIRECTS_COLLECTION].find({}).to_list(length=5000)
    redirects = [serialize_redirect_doc(doc, now=now) for doc in redirect_docs]
    return {
        "sitemap_url": "/sitemap.xml",
        "enabled": payload.get("enabled", True),
        "disabled_reason": payload.get("disabled_reason"),
        "disabled_host": payload.get("disabled_host"),
        "public_base_url": payload["public_base_url"],
        "generated_at": payload["generated_at"],
        "page_count": payload["page_count"],
        "entry_count": payload["entry_count"],
        "hidden_subtree_roots": payload["hidden_subtree_roots"],
        "redirect_count": len(redirects),
        "active_redirect_count": sum(1 for item in redirects if item["is_active"]),
        "generated_redirect_count": sum(
            1 for item in redirects if item.get("kind") == "generated"
        ),
    }


@router.get(
    "/stats",
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_sitemap_stats(days: str = Query(default="30")):
    db = _db()
    requested_days = _parse_stats_days(days)
    day_keys = _stats_day_range(requested_days or 30) if requested_days is not None else []
    start_day = day_keys[0] if day_keys else None
    end_day = day_keys[-1] if day_keys else None

    page_docs = await db[PAGES_COLLECTION].find(
        {},
        {
            "_id": 1,
            "slug": 1,
            "title": 1,
            "status": 1,
            "publish_at": 1,
            "unpublish_at": 1,
            "hide_in_admin_sitemap": 1,
            "generated_from_blog": 1,
            "template_managed": 1,
            "template_source_type": 1,
            "anonymous_hit_count": 1,
        },
    ).to_list(length=5000)
    page_docs = [
        doc for doc in page_docs
        if _compute_effective_page_status(doc) == "published"
    ]
    page_docs.sort(key=lambda doc: (str(doc.get("slug") or "") != "landing", str(doc.get("slug") or "")))

    known_slugs = {
        str(doc.get("slug") or "").strip()
        for doc in page_docs
        if str(doc.get("slug") or "").strip()
    }
    page_id_by_slug = {
        str(doc.get("slug") or "").strip(): str(doc.get("_id"))
        for doc in page_docs
        if str(doc.get("slug") or "").strip()
    }

    pages: list[dict] = []
    raw_page_ids = []
    page_id_set: set[str] = set()
    for doc in page_docs:
        slug = str(doc.get("slug") or "").strip()
        if not slug:
            continue
        raw_id = doc.get("_id")
        page_id = str(raw_id)
        raw_page_ids.append(raw_id)
        page_id_set.add(page_id)
        parent_slug = _resolve_stats_parent_slug(slug, known_slugs)
        pages.append(
            {
                "id": page_id,
                "slug": slug,
                "path": slug_to_path(slug),
                "title": _format_stats_title(doc.get("title")),
                "status": str(doc.get("status") or ""),
                "effective_status": _compute_effective_page_status(doc),
                "is_visible": True,
                "parent_id": page_id_by_slug.get(parent_slug) if parent_slug else None,
                "parent_slug": parent_slug,
                "hide_in_admin_sitemap": bool(doc.get("hide_in_admin_sitemap", False)),
                "generated_from_blog": bool(doc.get("generated_from_blog", False)),
                "template_managed": bool(doc.get("template_managed", False)),
                "template_source_type": str(doc.get("template_source_type") or "").strip() or None,
                "anonymous_hit_count": _normalize_non_negative_int(doc.get("anonymous_hit_count")),
                "descendant_ids": [],
            }
        )

    for page in pages:
        slug = page["slug"]
        page["descendant_ids"] = [
            candidate["id"]
            for candidate in pages
            if candidate["slug"] == slug
            or slug == "landing"
            or candidate["slug"].startswith(f"{slug}/")
        ]

    daily_hits: list[dict] = []
    if raw_page_ids:
        page_filter = {
            "$or": [
                {"page_id": {"$in": raw_page_ids}},
                {"page_id": {"$in": list(page_id_set)}},
            ]
        }
        daily_query = page_filter if requested_days is None else {
            "$and": [
                {"day": {"$gte": start_day, "$lte": end_day}},
                page_filter,
            ]
        }
        daily_docs = await db[PAGE_HIT_DAYS_COLLECTION].find(daily_query).to_list(length=200000)
        filtered_daily_docs = []
        for doc in daily_docs:
            day = str(doc.get("day") or "")
            page_id = str(doc.get("page_id") or "")
            if page_id not in page_id_set:
                continue
            filtered_daily_docs.append(doc)

        if requested_days is None:
            valid_day_dates = [
                parsed_day
                for parsed_day in (_parse_stats_day_key(doc.get("day")) for doc in filtered_daily_docs)
                if parsed_day is not None
            ]
            if valid_day_dates:
                end_date = datetime.now(timezone.utc).date()
                day_keys = _stats_day_range_from_dates(min(valid_day_dates), end_date)
                start_day = day_keys[0] if day_keys else None
                end_day = day_keys[-1] if day_keys else None

        day_set = set(day_keys)
        for doc in filtered_daily_docs:
            day = str(doc.get("day") or "")
            if day not in day_set:
                continue
            daily_hits.append(
                {
                    "page_id": str(doc.get("page_id") or ""),
                    "slug": str(doc.get("slug") or ""),
                    "day": day,
                    "count": _normalize_non_negative_int(doc.get("count")),
                }
            )

    total_hit_count = sum(page["anonymous_hit_count"] for page in pages)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "range": {
            "days": len(day_keys),
            "start_day": start_day,
            "end_day": end_day,
            "all_time": requested_days is None,
        },
        "days": day_keys,
        "pages": pages,
        "daily_hits": daily_hits,
        "totals": {
            "page_count": len(pages),
            "tracked_page_count": sum(1 for page in pages if page["anonymous_hit_count"] > 0),
            "total_hit_count": total_hit_count,
        },
    }


@router.post(
    "/stats/reset",
    dependencies=[Depends(require_permission("content:write"))],
)
async def reset_sitemap_stats():
    db = _db()
    page_result = await db[PAGES_COLLECTION].update_many(
        {},
        {
            "$set": {"anonymous_hit_count": 0},
            "$unset": {"anonymous_last_hit_at": ""},
        },
    )
    day_result = await db[PAGE_HIT_DAYS_COLLECTION].delete_many({})
    return {
        "ok": True,
        "pages_matched": int(getattr(page_result, "matched_count", 0) or 0),
        "pages_modified": int(getattr(page_result, "modified_count", 0) or 0),
        "daily_buckets_deleted": int(getattr(day_result, "deleted_count", 0) or 0),
    }


@router.post(
    "/regenerate",
    dependencies=[Depends(require_permission("content:write"))],
)
async def regenerate_sitemap(
    request: Request,
):
    payload = await build_public_sitemap_payload(
        _db(),
        public_base_url=resolve_public_base_url_from_request(request),
    )
    return {
        "ok": payload.get("enabled", True),
        "enabled": payload.get("enabled", True),
        "disabled_reason": payload.get("disabled_reason"),
        "disabled_host": payload.get("disabled_host"),
        "generated_at": payload["generated_at"],
        "entry_count": payload["entry_count"],
        "hidden_subtree_roots": payload["hidden_subtree_roots"],
    }


@router.get(
    "/robots",
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_robots_config(request: Request):
    db = _db()
    custom_text = await get_custom_robots_text(db)
    payload = await build_public_robots_payload(
        db,
        public_base_url=resolve_public_base_url_from_request(request),
        custom_robots_txt=custom_text,
    )
    return payload


@router.patch(
    "/robots",
    dependencies=[Depends(require_permission("content:write"))],
)
async def update_robots_config(
    payload: RobotsPatchPayload,
    request: Request,
):
    db = _db()
    coll = db[SITEMAP_CONFIG_COLLECTION]
    now = datetime.now(timezone.utc)
    custom_text = normalize_custom_robots_text(payload.custom_robots_txt)
    existing = await coll.find_one({"key": ADMIN_SITEMAP_CONFIG_KEY})
    if existing:
        await coll.update_one(
            {"_id": existing["_id"]},
            {"$set": {"custom_robots_txt": custom_text, "updated_at": now}},
        )
    else:
        await coll.insert_one(
            {
                "key": ADMIN_SITEMAP_CONFIG_KEY,
                "custom_robots_txt": custom_text,
                "created_at": now,
                "updated_at": now,
            }
        )

    result = await build_public_robots_payload(
        db,
        public_base_url=resolve_public_base_url_from_request(request),
        custom_robots_txt=custom_text,
    )
    cleaned_custom_text = str(result.get("custom_text") or "")
    if cleaned_custom_text != custom_text:
        await coll.update_one(
            {"key": ADMIN_SITEMAP_CONFIG_KEY},
            {
                "$set": {
                    "custom_robots_txt": cleaned_custom_text,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
    return result


@router.get(
    "/navigation-links",
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_navigation_links():
    return await get_navigation_links_config(_db())


@router.patch(
    "/navigation-links",
    dependencies=[Depends(require_permission("content:write"))],
)
async def update_navigation_links(
    payload: NavigationLinksPatchPayload,
):
    try:
        nav_external_links = normalize_external_nav_links(
            payload.nav_external_links,
            allow_generate_ids=True,
            drop_invalid=False,
        )
        footer_external_links = normalize_external_nav_links(
            payload.footer_external_links,
            allow_generate_ids=True,
            drop_invalid=False,
        )
        topbar_logo_url = normalize_topbar_logo_url(payload.topbar_logo_url)
        footer_logo_url = normalize_footer_logo_url(payload.footer_logo_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    now = datetime.now(timezone.utc)
    coll = _db()[SITEMAP_CONFIG_COLLECTION]
    await coll.update_one(
        {"key": ADMIN_SITEMAP_CONFIG_KEY},
        {
            "$set": {
                "nav_external_links": nav_external_links,
                "footer_external_links": footer_external_links,
                "topbar_logo_url": topbar_logo_url,
                "footer_logo_url": footer_logo_url,
                "updated_at": now,
            },
            "$setOnInsert": {
                "key": ADMIN_SITEMAP_CONFIG_KEY,
                "created_at": now,
            },
        },
        upsert=True,
    )
    return await get_navigation_links_config(_db())


@router.get(
    "/caching",
    dependencies=[Depends(require_permission("content:read"))],
)
async def get_htaccess_client_caching():
    doc = await _db()[SITEMAP_CONFIG_COLLECTION].find_one(
        {"key": ADMIN_SITEMAP_CONFIG_KEY},
        {HTACCESS_CLIENT_CACHING_FIELD: 1},
    )
    return build_htaccess_client_caching_payload(
        (doc or {}).get(HTACCESS_CLIENT_CACHING_FIELD)
    )


@router.patch(
    "/caching",
    dependencies=[Depends(require_permission("content:write"))],
)
async def update_htaccess_client_caching(payload: HtaccessCachingPatchPayload):
    try:
        rules = normalize_htaccess_client_cache_rules(payload.rules)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    now = datetime.now(timezone.utc)
    coll = _db()[SITEMAP_CONFIG_COLLECTION]
    await coll.update_one(
        {"key": ADMIN_SITEMAP_CONFIG_KEY},
        {
            "$set": {
                HTACCESS_CLIENT_CACHING_FIELD: {"rules": rules},
                "updated_at": now,
            },
            "$setOnInsert": {
                "key": ADMIN_SITEMAP_CONFIG_KEY,
                "created_at": now,
            },
        },
        upsert=True,
    )
    return build_htaccess_client_caching_payload({"rules": rules})


@router.get("/redirects/resolve")
async def resolve_redirect(
    request: Request,
    path: str = Query(..., min_length=1, description="Internal path, e.g. /old/path"),
):
    try:
        source_path = normalize_internal_path(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    doc = await find_active_redirect_doc(_db(), source_path=source_path)
    if not doc:
        return {"found": False}

    if (
        str(doc.get("kind") or "custom") == "custom"
        and not request_has_auth_credentials(request)
    ):
        now = datetime.now(timezone.utc)
        await increment_redirect_anonymous_hit_count(_db(), redirect_doc=doc, now=now)
        try:
            hit_count = max(0, int(doc.get(REDIRECT_ANONYMOUS_HIT_COUNT_FIELD) or 0))
        except Exception:
            hit_count = 0
        doc[REDIRECT_ANONYMOUS_HIT_COUNT_FIELD] = hit_count + 1
        doc[REDIRECT_LAST_TRIGGERED_AT_FIELD] = now

    return {"found": True, "redirect": serialize_redirect_doc(doc)}


@router.get(
    "/redirects",
    dependencies=[Depends(require_permission("content:read"))],
)
async def list_redirects(
    include_expired: bool = Query(default=True),
):
    now = datetime.now(timezone.utc)
    docs = (
        await _db()[REDIRECTS_COLLECTION]
        .find({})
        .sort([("source_path", 1), ("updated_at", -1)])
        .to_list(length=5000)
    )
    redirects = [serialize_redirect_doc(doc, now=now) for doc in docs]
    if not include_expired:
        redirects = [item for item in redirects if not item["is_expired"]]
    return redirects


@router.post(
    "/redirects",
)
async def create_redirect(
    payload: RedirectCreatePayload,
    user: KeycloakUser = Depends(require_permission("content:write")),
):
    now = datetime.now(timezone.utc)
    expires_at = payload.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at:
        expires_at = expires_at.astimezone(timezone.utc)

    try:
        status_code = normalize_redirect_status_code(payload.status_code)
        source_path = normalize_redirect_source_path(payload.source_path)
        target_path = normalize_redirect_target(
            payload.target_path,
            allow_empty=status_code == 410,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if status_code == 410 and target_path is not None:
        raise HTTPException(status_code=400, detail="410 redirects must not define a target path")
    if status_code != 410 and not target_path:
        raise HTTPException(status_code=400, detail="Target is required for redirect status codes 301/302/307/308")
    if target_path and not is_external_url(target_path) and source_path == target_path:
        raise HTTPException(status_code=400, detail="Redirect source and target are identical")
    if expires_at and expires_at <= now:
        raise HTTPException(status_code=400, detail="expires_at must be in the future")

    coll = _db()[REDIRECTS_COLLECTION]
    existing = await coll.find_one({"source_path": source_path})
    if existing and existing.get("kind") == "custom":
        raise HTTPException(status_code=409, detail="A custom redirect for this source already exists")

    update_payload = {
        "source_path": source_path,
        "target_path": target_path,
        "status_code": status_code,
        "kind": "custom",
        "generated_reason": None,
        "generated_from_path": None,
        "generated_to_path": None,
        "is_active": payload.is_active,
        "expires_at": expires_at,
        "updated_at": now,
        "created_by": user.username,
    }

    if existing:
        doc = await coll.find_one_and_update(
            {"_id": existing["_id"]},
            {"$set": update_payload},
            return_document=ReturnDocument.AFTER,
        )
    else:
        to_insert = {
            **update_payload,
            REDIRECT_ANONYMOUS_HIT_COUNT_FIELD: 0,
            "created_at": now,
        }
        res = await coll.insert_one(to_insert)
        doc = {**to_insert, "_id": res.inserted_id}

    return serialize_redirect_doc(doc, now=now)


@router.patch(
    "/redirects/{redirect_id}",
    dependencies=[Depends(require_permission("content:write"))],
)
async def update_redirect(
    redirect_id: str,
    payload: RedirectPatchPayload,
):
    try:
        oid = ObjectId(redirect_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid redirect id")

    coll = _db()[REDIRECTS_COLLECTION]
    current = await coll.find_one({"_id": oid})
    if not current:
        raise HTTPException(status_code=404, detail="Redirect not found")

    provided = payload.model_fields_set
    if not provided:
        raise HTTPException(status_code=400, detail="No fields to update")

    patch: dict = {}
    try:
        if "source_path" in provided:
            patch["source_path"] = normalize_redirect_source_path(payload.source_path or "")
        if "status_code" in provided:
            patch["status_code"] = normalize_redirect_status_code(payload.status_code or 0)
        effective_status = patch.get("status_code", int(current.get("status_code", 301)))
        if "target_path" in provided:
            patch["target_path"] = normalize_redirect_target(
                payload.target_path,
                allow_empty=effective_status == 410,
            )
        elif effective_status == 410:
            patch["target_path"] = None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if "is_active" in provided:
        patch["is_active"] = bool(payload.is_active)
    if "expires_at" in provided:
        expires_at = payload.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        patch["expires_at"] = expires_at.astimezone(timezone.utc) if expires_at else None

    effective_source = patch.get("source_path", current.get("source_path", "/"))
    effective_status = patch.get("status_code", int(current.get("status_code", 301)))
    effective_target = patch.get("target_path", current.get("target_path"))

    if effective_status == 410 and effective_target is not None:
        raise HTTPException(status_code=400, detail="410 redirects must not define a target path")
    if effective_status != 410 and not effective_target:
        raise HTTPException(status_code=400, detail="Target is required for redirect status codes 301/302/307/308")
    if effective_target and not is_external_url(effective_target) and effective_source == effective_target:
        raise HTTPException(status_code=400, detail="Redirect source and target are identical")

    if "source_path" in patch:
        conflict = await coll.find_one(
            {
                "_id": {"$ne": oid},
                "source_path": patch["source_path"],
            }
        )
        if conflict:
            raise HTTPException(status_code=409, detail="Another redirect already uses this source path")

    patch["updated_at"] = datetime.now(timezone.utc)
    updated = await coll.find_one_and_update(
        {"_id": oid},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    return serialize_redirect_doc(updated)


@router.delete(
    "/redirects/{redirect_id}",
    dependencies=[Depends(require_permission("content:write"))],
)
async def delete_redirect(
    redirect_id: str,
):
    try:
        oid = ObjectId(redirect_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid redirect id")

    res = await _db()[REDIRECTS_COLLECTION].delete_one({"_id": oid})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Redirect not found")
    return {"ok": True}
