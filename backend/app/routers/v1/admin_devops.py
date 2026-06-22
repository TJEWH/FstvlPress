from __future__ import annotations

from datetime import datetime
import re
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pymongo import ReturnDocument

from app.access_control import INTERNAL_ROLE_ORDER, INTERNAL_ROLE_RANK, normalize_internal_role, role_at_least
from app.collection_names import CHANGELOG_COLLECTION, DEVOPS_CONFIG_COLLECTION, PAGES_COLLECTION
from app.db import get_client
from app.deps import require_permission
from app.security import KeycloakUser
from app.settings import settings

router = APIRouter(prefix="/admin/devops-config", tags=["admin"])

DEVOPS_CONFIG_KEY = DEVOPS_CONFIG_COLLECTION
TAG_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
TODO_PRIORITY_VALUES = {"urgent", "needed", "optional"}
DEFAULT_TODO_TAG_ID = "text"
DEFAULT_TODO_PRIORITY = "needed"
TUTORIAL_TITLE_MAX_LENGTH = 140
TUTORIAL_DESCRIPTION_MAX_LENGTH = 2000
TUTORIAL_STEP_TEXT_MAX_LENGTH = 280
TUTORIAL_STEP_LONG_TEXT_MAX_LENGTH = 2400
TUTORIAL_URL_MAX_LENGTH = 500
TUTORIAL_SCOPE_VALUES = tuple(role for role in INTERNAL_ROLE_ORDER if role != "no_access")
DEFAULT_TODO_TAGS = [
    {"id": "bug", "area": "it"},
    {"id": "feature", "area": "it"},
    {"id": "improve", "area": "it"},
    {"id": "media", "area": "content"},
    {"id": "text", "area": "content"},
]


def _db():
    return get_client()[settings.mongo_db]


def _get_default_config() -> dict:
    return {
        "key": DEVOPS_CONFIG_KEY,
        "todo_tags": [dict(tag) for tag in DEFAULT_TODO_TAGS],
        "unassigned_todos": [],
        "tutorials": [],
    }


def _build_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _normalize_current_user_label(user: KeycloakUser) -> str:
    return (
        str(user.name or "").strip()
        or str(user.username or "").strip()
        or str(user.email or "").strip()
        or str(user.sub or "").strip()
        or "unknown"
    )


def _current_user_identity_tokens(user: KeycloakUser) -> set[str]:
    return {
        str(value or "").strip().lower()
        for value in [
            user.sub,
            user.username,
            user.email,
            user.name,
        ]
        if str(value or "").strip()
    }


def _normalize_tutorial_scope(value: Any, *, default: str = "content", strict: bool = False) -> str:
    raw = str(value or "").strip().lower()
    if strict and raw and raw not in TUTORIAL_SCOPE_VALUES:
        allowed = ", ".join(TUTORIAL_SCOPE_VALUES)
        raise HTTPException(400, f"scope must be one of: {allowed}")
    normalized = normalize_internal_role(
        raw,
        default=default if default in TUTORIAL_SCOPE_VALUES else "content",
        allow_no_access=False,
    )
    if normalized not in TUTORIAL_SCOPE_VALUES:
        return "content"
    return normalized


def _tutorial_scope_options_for_role(role: str | None) -> list[str]:
    normalized_role = _normalize_tutorial_scope(role, default="content")
    role_rank = INTERNAL_ROLE_RANK.get(normalized_role, 0)
    return [
        scope
        for scope in TUTORIAL_SCOPE_VALUES
        if INTERNAL_ROLE_RANK.get(scope, 0) <= role_rank
    ]


def _ensure_scope_allowed_for_user(scope: str, user: KeycloakUser) -> str:
    normalized_scope = _normalize_tutorial_scope(scope, default=user.internal_role or "content", strict=True)
    if role_at_least(user.internal_role, "admin_general"):
        return normalized_scope
    if INTERNAL_ROLE_RANK.get(normalized_scope, 0) > INTERNAL_ROLE_RANK.get(_normalize_tutorial_scope(user.internal_role), 0):
        raise HTTPException(403, "Tutorial scope exceeds current user's role")
    return normalized_scope


def _normalize_tutorial_url(value: Any, *, index_label: str = "url") -> str:
    url = str(value or "").strip()
    if not url:
        raise HTTPException(400, f"{index_label} is required")
    if len(url) > TUTORIAL_URL_MAX_LENGTH:
        raise HTTPException(400, f"{index_label} must be {TUTORIAL_URL_MAX_LENGTH} characters or fewer")
    if any(ord(char) < 32 for char in url):
        raise HTTPException(400, f"{index_label} contains invalid control characters")

    lowered = url.lower()
    if lowered.startswith(("javascript:", "data:", "vbscript:")):
        raise HTTPException(400, f"{index_label} must not use a script or data URL")
    if url.startswith("/"):
        if url.startswith("//"):
            raise HTTPException(400, f"{index_label} must be a site path or http(s) URL")
        return url
    if lowered.startswith(("http://", "https://")):
        return url
    raise HTTPException(400, f"{index_label} must be a site path or http(s) URL")


def _normalize_tutorial_steps(raw_steps: Any, *, strict: bool) -> list[dict]:
    if not isinstance(raw_steps, list):
        if strict:
            raise HTTPException(400, "steps must be a list")
        return []

    normalized: list[dict] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            if strict:
                raise HTTPException(400, f"steps[{index}] must be an object")
            continue

        short_description = str(raw.get("short_description", raw.get("shortDescription", "")) or "").strip()
        if not short_description:
            if strict:
                raise HTTPException(400, f"steps[{index}].short_description is required")
            continue
        if len(short_description) > TUTORIAL_STEP_TEXT_MAX_LENGTH:
            raise HTTPException(
                400,
                f"steps[{index}].short_description must be {TUTORIAL_STEP_TEXT_MAX_LENGTH} characters or fewer",
            )

        try:
            url = _normalize_tutorial_url(raw.get("url"), index_label=f"steps[{index}].url")
        except HTTPException:
            if strict:
                raise
            continue

        long_description = str(raw.get("long_description", raw.get("longDescription", "")) or "").strip()
        if len(long_description) > TUTORIAL_STEP_LONG_TEXT_MAX_LENGTH:
            raise HTTPException(
                400,
                f"steps[{index}].long_description must be {TUTORIAL_STEP_LONG_TEXT_MAX_LENGTH} characters or fewer",
            )

        step_id = str(raw.get("id", "") or "").strip() or (
            _build_id("step") if strict else f"step-{index + 1}"
        )
        if step_id in seen_ids:
            step_id = _build_id("step") if strict else f"{step_id}-{index + 1}"
        seen_ids.add(step_id)

        normalized.append(
            {
                "id": step_id,
                "url": url,
                "short_description": short_description,
                "long_description": long_description,
                "order": len(normalized),
            }
        )

    if strict and not normalized:
        raise HTTPException(400, "tutorial must contain at least one step")
    return normalized


def _normalize_tutorial_doc(raw: Any, *, strict: bool, user: KeycloakUser | None = None, existing: dict | None = None) -> dict | None:
    if not isinstance(raw, dict):
        if strict:
            raise HTTPException(400, "tutorial must be an object")
        return None

    base = existing or {}
    title = str(raw.get("title", base.get("title", "")) or "").strip()
    if not title:
        if strict:
            raise HTTPException(400, "title is required")
        return None
    if len(title) > TUTORIAL_TITLE_MAX_LENGTH:
        raise HTTPException(400, f"title must be {TUTORIAL_TITLE_MAX_LENGTH} characters or fewer")

    description = str(raw.get("description", base.get("description", "")) or "").strip()
    if len(description) > TUTORIAL_DESCRIPTION_MAX_LENGTH:
        raise HTTPException(400, f"description must be {TUTORIAL_DESCRIPTION_MAX_LENGTH} characters or fewer")

    raw_scope = raw.get("scope", base.get("scope"))
    default_scope = user.internal_role if user else str(base.get("scope") or "content")
    scope = _normalize_tutorial_scope(raw_scope, default=default_scope, strict=strict)
    if user:
        scope = _ensure_scope_allowed_for_user(scope, user)

    steps_source = raw.get("steps", base.get("steps", []))
    steps = _normalize_tutorial_steps(steps_source, strict=strict)
    if not steps:
        if strict:
            raise HTTPException(400, "tutorial must contain at least one step")
        return None

    now = datetime.utcnow()
    tutorial_id = str(raw.get("id", base.get("id", "")) or "").strip() or (
        _build_id("tutorial") if strict else ""
    )
    if not tutorial_id:
        return None

    owner = str(base.get("owner", raw.get("owner", "")) or "").strip()
    owner_id = str(base.get("owner_id", raw.get("owner_id", "")) or "").strip()
    if user and not existing:
        owner = _normalize_current_user_label(user)
        owner_id = str(user.sub or "").strip()
    if not owner:
        owner = "unknown"

    created_at = base.get("created_at") or (raw.get("created_at") if user is None else None) or now
    updated_at = raw.get("updated_at") or base.get("updated_at") or now
    if strict:
        updated_at = now

    return {
        "id": tutorial_id,
        "title": title,
        "description": description,
        "scope": scope,
        "owner": owner,
        "owner_id": owner_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "steps": steps,
    }


def _normalize_tutorials(raw_tutorials: Any, *, strict: bool = False) -> list[dict]:
    if raw_tutorials is None:
        return []
    if not isinstance(raw_tutorials, list):
        if strict:
            raise HTTPException(400, "tutorials must be a list")
        return []

    normalized: list[dict] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_tutorials):
        tutorial = _normalize_tutorial_doc(raw, strict=False)
        if not tutorial:
            continue
        if tutorial["id"] in seen_ids:
            tutorial["id"] = f"{tutorial['id']}-{index + 1}"
        seen_ids.add(tutorial["id"])
        normalized.append(tutorial)
    return normalized


def _can_view_tutorial(tutorial: dict, user: KeycloakUser) -> bool:
    scope = _normalize_tutorial_scope(tutorial.get("scope"), default="content")
    return INTERNAL_ROLE_RANK.get(scope, 0) <= INTERNAL_ROLE_RANK.get(_normalize_tutorial_scope(user.internal_role), 0)


def _can_manage_tutorial(tutorial: dict, user: KeycloakUser) -> bool:
    if role_at_least(user.internal_role, "admin_general"):
        return True
    tokens = _current_user_identity_tokens(user)
    owner_tokens = {
        str(tutorial.get("owner_id") or "").strip().lower(),
        str(tutorial.get("owner") or "").strip().lower(),
    }
    owner_tokens.discard("")
    return bool(tokens & owner_tokens)


def _serialize_tutorial(tutorial: dict, user: KeycloakUser | None = None) -> dict:
    payload = {
        "id": str(tutorial.get("id") or ""),
        "title": str(tutorial.get("title") or ""),
        "description": str(tutorial.get("description") or ""),
        "scope": _normalize_tutorial_scope(tutorial.get("scope"), default="content"),
        "owner": str(tutorial.get("owner") or "unknown"),
        "owner_id": str(tutorial.get("owner_id") or ""),
        "created_at": tutorial.get("created_at"),
        "updated_at": tutorial.get("updated_at"),
        "steps": [
            {
                "id": str(step.get("id") or ""),
                "url": str(step.get("url") or ""),
                "short_description": str(step.get("short_description") or ""),
                "long_description": str(step.get("long_description") or ""),
                "order": int(step.get("order") or index),
            }
            for index, step in enumerate(tutorial.get("steps") or [])
            if isinstance(step, dict)
        ],
    }
    if user is not None:
        payload["can_edit"] = _can_manage_tutorial(tutorial, user)
    return payload


async def _ensure_devops_config_doc() -> dict:
    coll = _db()[DEVOPS_CONFIG_COLLECTION]
    doc = await coll.find_one({"key": DEVOPS_CONFIG_KEY})
    now = datetime.utcnow()
    if not doc:
        defaults = _get_default_config()
        doc = {
            **defaults,
            "created_at": now,
            "updated_at": now,
        }
        res = await coll.insert_one(doc)
        doc["_id"] = res.inserted_id
        return doc

    patch: dict[str, Any] = {"updated_at": now}
    current_tags = doc.get("todo_tags", [])
    if not isinstance(current_tags, list):
        current_tags = []
    merged_tags = _ensure_default_tags(current_tags)
    if merged_tags != current_tags:
        patch["todo_tags"] = merged_tags

    current_unassigned_todos = _normalize_unassigned_todos(
        doc.get("unassigned_todos"),
        strict=False,
    )
    if current_unassigned_todos != (doc.get("unassigned_todos") or []):
        patch["unassigned_todos"] = current_unassigned_todos

    current_tutorials = _normalize_tutorials(doc.get("tutorials"), strict=False)
    if current_tutorials != (doc.get("tutorials") or []):
        patch["tutorials"] = current_tutorials

    if len(patch) > 1:
        doc = await coll.find_one_and_update(
            {"key": DEVOPS_CONFIG_KEY},
            {"$set": patch},
            return_document=ReturnDocument.AFTER,
        )
    return doc


def _normalize_todo_tags(raw_tags: Any) -> list[dict]:
    if not isinstance(raw_tags, list):
        raise HTTPException(400, "todo_tags must be a list")

    seen: set[str] = set()
    normalized: list[dict] = []
    for index, raw in enumerate(raw_tags):
        if not isinstance(raw, dict):
            raise HTTPException(400, f"todo_tags[{index}] must be an object")

        tag_id = str(raw.get("id", "")).strip()
        if not tag_id:
            raise HTTPException(400, f"todo_tags[{index}].id is required")
        if not TAG_ID_PATTERN.match(tag_id):
            raise HTTPException(
                400,
                f"todo_tags[{index}].id must match {TAG_ID_PATTERN.pattern}",
            )
        if tag_id in seen:
            raise HTTPException(400, f"Duplicate todo tag id '{tag_id}'")
        seen.add(tag_id)

        area = str(raw.get("area", "")).strip().lower()
        if area not in {"it", "content"}:
            raise HTTPException(
                400,
                f"todo_tags[{index}].area must be one of: it, content",
            )
        normalized.append({"id": tag_id, "area": area})

    return normalized


def _normalize_priority(value: Any) -> str:
    priority = str(value or "").strip().lower()
    return priority if priority in TODO_PRIORITY_VALUES else DEFAULT_TODO_PRIORITY


def _normalize_priority_rank(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        rank = int(value)
    except (TypeError, ValueError):
        return None
    if rank < 0:
        return None
    return rank


def _normalize_todo_comments(raw_comments: Any) -> list[dict]:
    if raw_comments is None:
        return []
    if not isinstance(raw_comments, list):
        return []

    normalized: list[dict] = []
    for index, raw in enumerate(raw_comments):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        comment_id = str(raw.get("id", "")).strip() or f"comment-{int(datetime.utcnow().timestamp() * 1000)}-{index}"
        created_by = str(raw.get("created_by", "unknown")).strip() or "unknown"
        created_at = str(raw.get("created_at", "")).strip() or None
        normalized.append(
            {
                "id": comment_id,
                "text": text,
                "created_by": created_by,
                "created_at": created_at,
            }
        )

    return normalized


def _normalize_unassigned_todos(raw_todos: Any, *, strict: bool) -> list[dict]:
    if raw_todos is None:
        return []
    if not isinstance(raw_todos, list):
        if strict:
            raise HTTPException(400, "unassigned_todos must be a list")
        return []

    normalized: list[dict] = []
    for index, raw in enumerate(raw_todos):
        if not isinstance(raw, dict):
            if strict:
                raise HTTPException(400, f"unassigned_todos[{index}] must be an object")
            continue

        text = str(raw.get("text", "")).strip()
        if not text:
            continue

        todo_id = str(raw.get("id", "")).strip() or f"unassigned-{int(datetime.utcnow().timestamp() * 1000)}-{index}"
        done = bool(raw.get("done", False))
        created_by = str(raw.get("created_by", "unknown")).strip() or "unknown"
        created_at = str(raw.get("created_at", "")).strip() or None
        resolved_by = str(raw.get("resolved_by", "")).strip() or None
        resolved_at = str(raw.get("resolved_at", "")).strip() or None
        tag = str(raw.get("tag", "")).strip() or DEFAULT_TODO_TAG_ID
        priority = _normalize_priority(raw.get("priority"))
        priority_rank = _normalize_priority_rank(raw.get("priority_rank"))
        comments = _normalize_todo_comments(raw.get("comments"))

        normalized.append(
            {
                "id": todo_id,
                "text": text,
                "done": done,
                "created_by": created_by,
                "created_at": created_at,
                "resolved_by": resolved_by,
                "resolved_at": resolved_at,
                "tag": tag,
                "priority": priority,
                "priority_rank": priority_rank,
                "comments": comments,
            }
        )

    counters = {"urgent": 0, "needed": 0, "optional": 0}
    for todo in normalized:
        priority = todo["priority"]
        rank = todo.get("priority_rank")
        if rank is None:
            todo["priority_rank"] = counters[priority]
        else:
            todo["priority_rank"] = rank
        counters[priority] = max(counters[priority], int(todo["priority_rank"]) + 1)

    return normalized


def _ensure_default_tags(todo_tags: list[dict]) -> list[dict]:
    by_id = {}
    for tag in todo_tags:
        tag_id = str(tag.get("id", "")).strip()
        if not tag_id or tag_id in by_id:
            continue
        area = str(tag.get("area", "")).strip().lower()
        if area not in {"it", "content"}:
            continue
        by_id[tag_id] = {"id": tag_id, "area": area}

    ordered: list[dict] = []
    default_map = {tag["id"]: tag["area"] for tag in DEFAULT_TODO_TAGS}
    for default in DEFAULT_TODO_TAGS:
        current = by_id.get(default["id"])
        if not current:
            ordered.append(dict(default))
            continue
        # Default tags keep their canonical planning area.
        ordered.append({"id": default["id"], "area": default["area"]})

    for tag in todo_tags:
        tag_id = str(tag.get("id", "")).strip()
        if not tag_id or tag_id in default_map:
            continue
        existing = by_id.get(tag_id)
        if existing:
            ordered.append(existing)
            by_id.pop(tag_id, None)

    return ordered


def _find_tags_in_todo_list(todos: list[dict], tag_ids: set[str]) -> set[str]:
    if not tag_ids:
        return set()
    used: set[str] = set()
    for todo in todos:
        tag = str((todo or {}).get("tag", "")).strip()
        if tag in tag_ids:
            used.add(tag)
    return used


def _normalize_page_slug(value: Any) -> str:
    normalized = str(value or "").strip().strip("/")
    return normalized or "landing"


def _page_url_from_slug(value: Any) -> str:
    normalized = _normalize_page_slug(value)
    if normalized == "landing":
        return "/"
    return f"/{normalized}"


def _normalize_optional_page_slug(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.split("?", 1)[0].split("#", 1)[0].strip("/")
    return normalized or "landing"


def _changelog_page_context_from_doc(page: dict | None) -> tuple[set[str], dict[str, dict]]:
    if not isinstance(page, dict):
        return set(), {}
    page_slug = _normalize_page_slug(page.get("slug"))
    page_context = {
        "page_slug": page_slug,
        "page_url": _page_url_from_slug(page_slug),
    }
    section_ids: set[str] = set()
    page_context_by_section_id: dict[str, dict] = {}
    for ref in page.get("sections") or []:
        if not isinstance(ref, dict):
            continue
        section_id = str(ref.get("section_id") or "").strip()
        if not section_id:
            continue
        section_ids.add(section_id)
        page_context_by_section_id.setdefault(section_id, page_context)
    return section_ids, page_context_by_section_id


async def _get_changelog_page_context_for_slug(page_slug: str) -> tuple[set[str], dict[str, dict]]:
    page = await _db()[PAGES_COLLECTION].find_one(
        {"slug": page_slug},
        {"slug": 1, "sections": 1},
    )
    return _changelog_page_context_from_doc(page)


async def _get_changelog_page_url_by_section_id(section_ids: set[str]) -> dict[str, dict]:
    normalized_section_ids = {
        str(section_id or "").strip()
        for section_id in section_ids
        if str(section_id or "").strip()
    }
    if not normalized_section_ids:
        return {}

    cursor = (
        _db()[PAGES_COLLECTION]
        .find(
            {"sections.section_id": {"$in": sorted(normalized_section_ids)}},
            {"slug": 1, "sections": 1},
        )
        .sort("slug", 1)
    )

    page_by_section_id: dict[str, dict] = {}
    async for page in cursor:
        page_slug = _normalize_page_slug(page.get("slug"))
        page_url = _page_url_from_slug(page_slug)
        for ref in page.get("sections") or []:
            if not isinstance(ref, dict):
                continue
            section_id = str(ref.get("section_id") or "").strip()
            if section_id in normalized_section_ids and section_id not in page_by_section_id:
                page_by_section_id[section_id] = {
                    "page_slug": page_slug,
                    "page_url": page_url,
                }
    return page_by_section_id


def _serialize_changelog_doc(doc: dict, page_context_by_section_id: dict[str, dict] | None = None) -> dict:
    entity_id = str(doc.get("entity_id") or "")
    page_context = (page_context_by_section_id or {}).get(entity_id) or {}
    return {
        "id": str(doc.get("_id") or ""),
        "entry_type": str(doc.get("entry_type") or "section_revision"),
        "entity_type": str(doc.get("entity_type") or "section"),
        "entity_id": entity_id,
        "section_id": entity_id,
        "section_type": str(doc.get("section_type") or ""),
        "section_label": str(doc.get("section_label") or "").strip() or "Section",
        "page_slug": str(page_context.get("page_slug") or ""),
        "page_url": str(page_context.get("page_url") or ""),
        "revision_id": str(doc.get("revision_id") or ""),
        "saved_at": doc.get("saved_at"),
        "saved_by": str(doc.get("saved_by") or "unknown"),
        "change_kind": str(doc.get("change_kind") or ""),
        "reverted_from_saved_at": doc.get("reverted_from_saved_at"),
        "created_at": doc.get("created_at"),
    }


async def _find_tags_in_sections_and_headers(tag_ids: set[str]) -> set[str]:
    if not tag_ids:
        return set()

    normalized_tag_ids = {
        str(tag_id).strip()
        for tag_id in tag_ids
        if str(tag_id).strip()
    }
    if not normalized_tag_ids:
        return set()

    db = _db()
    sections = db["sections"]
    headers = db["headers"]
    tag_list = sorted(normalized_tag_ids)

    used: set[str] = set()
    section_docs = sections.find(
        {"type_data.admin_todos.tag": {"$in": tag_list}},
        {"type_data.admin_todos": 1},
    )
    header_docs = headers.find(
        {"admin_todos.tag": {"$in": tag_list}},
        {"admin_todos": 1},
    )
    async for doc in section_docs:
        todos = (doc.get("type_data") or {}).get("admin_todos") or []
        for todo in todos:
            tag = str((todo or {}).get("tag", "")).strip()
            if tag in normalized_tag_ids:
                used.add(tag)

    async for doc in header_docs:
        todos = doc.get("admin_todos") or []
        for todo in todos:
            tag = str((todo or {}).get("tag", "")).strip()
            if tag in normalized_tag_ids:
                used.add(tag)

    return used


@router.get("/changelog")
async def get_admin_devops_changelog(
    limit: int = Query(default=50, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    page_slug: str | None = Query(default=None),
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    normalized_page_slug = _normalize_optional_page_slug(page_slug)
    query = {"entity_type": "section"}
    page_context_by_section_id = None
    if normalized_page_slug:
        page_section_ids, scoped_page_context = await _get_changelog_page_context_for_slug(normalized_page_slug)
        page_context_by_section_id = scoped_page_context
        query["entity_id"] = {"$in": sorted(page_section_ids)}

    coll = _db()[CHANGELOG_COLLECTION]
    cursor = (
        coll
        .find(query)
        .sort("saved_at", -1)
        .skip(offset)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    if page_context_by_section_id is None:
        section_ids = {str(doc.get("entity_id") or "").strip() for doc in docs}
        page_context_by_section_id = await _get_changelog_page_url_by_section_id(section_ids)
    total = await coll.count_documents(query)
    items = [
        _serialize_changelog_doc(doc, page_context_by_section_id)
        for doc in docs
    ]
    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "total": total,
        "has_more": offset + len(items) < total,
    }


@router.get("")
async def get_devops_config(
    _: KeycloakUser = Depends(require_permission("content:read")),
):
    doc = await _ensure_devops_config_doc()

    return {
        "id": str(doc["_id"]),
        "todo_tags": doc.get("todo_tags", []),
        "unassigned_todos": _normalize_unassigned_todos(doc.get("unassigned_todos"), strict=False),
        "updated_at": doc.get("updated_at"),
        "created_at": doc.get("created_at"),
    }


@router.get("/tutorials")
async def get_devops_tutorials(
    user: KeycloakUser = Depends(require_permission("content:read")),
):
    doc = await _ensure_devops_config_doc()
    tutorials = [
        _serialize_tutorial(tutorial, user)
        for tutorial in _normalize_tutorials(doc.get("tutorials"), strict=False)
        if _can_view_tutorial(tutorial, user)
    ]
    tutorials.sort(
        key=lambda tutorial: (
            str(tutorial.get("title") or "").lower(),
            str(tutorial.get("id") or ""),
        )
    )
    return {
        "items": tutorials,
        "scope_options": _tutorial_scope_options_for_role(user.internal_role),
    }


@router.post("/tutorials")
async def create_devops_tutorial(
    payload: dict = Body(...),
    user: KeycloakUser = Depends(require_permission("content:write")),
):
    coll = _db()[DEVOPS_CONFIG_COLLECTION]
    doc = await _ensure_devops_config_doc()
    current_tutorials = _normalize_tutorials(doc.get("tutorials"), strict=False)
    tutorial = _normalize_tutorial_doc(payload, strict=True, user=user)
    if tutorial is None:
        raise HTTPException(400, "tutorial payload is invalid")
    next_tutorials = [*current_tutorials, tutorial]
    updated = await coll.find_one_and_update(
        {"key": DEVOPS_CONFIG_KEY},
        {
            "$set": {
                "tutorials": next_tutorials,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    created = next(
        item
        for item in _normalize_tutorials(updated.get("tutorials"), strict=False)
        if item.get("id") == tutorial.get("id")
    )
    return _serialize_tutorial(created, user)


@router.patch("/tutorials/{tutorial_id}")
async def update_devops_tutorial(
    tutorial_id: str,
    payload: dict = Body(...),
    user: KeycloakUser = Depends(require_permission("content:write")),
):
    normalized_id = str(tutorial_id or "").strip()
    if not normalized_id:
        raise HTTPException(400, "tutorial id is required")

    coll = _db()[DEVOPS_CONFIG_COLLECTION]
    doc = await _ensure_devops_config_doc()
    current_tutorials = _normalize_tutorials(doc.get("tutorials"), strict=False)
    tutorial_index = next(
        (index for index, item in enumerate(current_tutorials) if item.get("id") == normalized_id),
        -1,
    )
    if tutorial_index < 0:
        raise HTTPException(404, "Tutorial not found")

    existing = current_tutorials[tutorial_index]
    if not _can_manage_tutorial(existing, user):
        raise HTTPException(403, "Only the tutorial owner or admin_general can edit this tutorial")

    next_payload = dict(payload or {})
    next_payload["id"] = normalized_id
    updated_tutorial = _normalize_tutorial_doc(
        next_payload,
        strict=True,
        user=user,
        existing=existing,
    )
    if updated_tutorial is None:
        raise HTTPException(400, "tutorial payload is invalid")

    next_tutorials = [*current_tutorials]
    next_tutorials[tutorial_index] = updated_tutorial
    updated = await coll.find_one_and_update(
        {"key": DEVOPS_CONFIG_KEY},
        {
            "$set": {
                "tutorials": next_tutorials,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    saved = next(
        item
        for item in _normalize_tutorials(updated.get("tutorials"), strict=False)
        if item.get("id") == normalized_id
    )
    return _serialize_tutorial(saved, user)


@router.delete("/tutorials/{tutorial_id}")
async def delete_devops_tutorial(
    tutorial_id: str,
    user: KeycloakUser = Depends(require_permission("content:write")),
):
    normalized_id = str(tutorial_id or "").strip()
    if not normalized_id:
        raise HTTPException(400, "tutorial id is required")

    coll = _db()[DEVOPS_CONFIG_COLLECTION]
    doc = await _ensure_devops_config_doc()
    current_tutorials = _normalize_tutorials(doc.get("tutorials"), strict=False)
    tutorial = next((item for item in current_tutorials if item.get("id") == normalized_id), None)
    if not tutorial:
        raise HTTPException(404, "Tutorial not found")
    if not _can_manage_tutorial(tutorial, user):
        raise HTTPException(403, "Only the tutorial owner or admin_general can delete this tutorial")

    next_tutorials = [item for item in current_tutorials if item.get("id") != normalized_id]
    await coll.find_one_and_update(
        {"key": DEVOPS_CONFIG_KEY},
        {
            "$set": {
                "tutorials": next_tutorials,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    return {"ok": True, "id": normalized_id}


@router.patch(
    "",
    dependencies=[Depends(require_permission("admin:general"))],
)
async def update_devops_config(payload: dict = Body(...)):
    coll = _db()[DEVOPS_CONFIG_COLLECTION]
    current = await coll.find_one({"key": DEVOPS_CONFIG_KEY})
    now = datetime.utcnow()
    if not current:
        defaults = _get_default_config()
        current = {
            **defaults,
            "created_at": now,
            "updated_at": now,
        }
        res = await coll.insert_one(current)
        current["_id"] = res.inserted_id

    if "todo_tags" not in payload and "unassigned_todos" not in payload:
        raise HTTPException(400, "No valid fields to update")

    current_tags = _ensure_default_tags(
        current.get("todo_tags") if isinstance(current.get("todo_tags"), list) else []
    )
    current_unassigned_todos = _normalize_unassigned_todos(
        current.get("unassigned_todos"),
        strict=False,
    )

    next_tags = current_tags
    if "todo_tags" in payload:
        normalized_tags = _normalize_todo_tags(payload.get("todo_tags"))
        next_tags = _ensure_default_tags(normalized_tags)

    next_unassigned_todos = current_unassigned_todos
    if "unassigned_todos" in payload:
        next_unassigned_todos = _normalize_unassigned_todos(
            payload.get("unassigned_todos"),
            strict=True,
        )

    removed_tag_ids = {
        tag.get("id")
        for tag in current_tags
        if isinstance(tag.get("id"), str)
    } - {
        tag.get("id")
        for tag in next_tags
        if isinstance(tag.get("id"), str)
    }
    tags_in_use = await _find_tags_in_sections_and_headers(removed_tag_ids)
    tags_in_use.update(_find_tags_in_todo_list(next_unassigned_todos, removed_tag_ids))
    if tags_in_use:
        sorted_tags = ", ".join(sorted(tags_in_use))
        raise HTTPException(400, f"Cannot delete todo tag(s) still in use: {sorted_tags}")

    patch: dict[str, Any] = {"updated_at": now}
    if "todo_tags" in payload:
        patch["todo_tags"] = next_tags
    if "unassigned_todos" in payload:
        patch["unassigned_todos"] = next_unassigned_todos

    doc = await coll.find_one_and_update(
        {"key": DEVOPS_CONFIG_KEY},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    return {
        "id": str(doc["_id"]),
        "todo_tags": doc.get("todo_tags", []),
        "unassigned_todos": _normalize_unassigned_todos(doc.get("unassigned_todos"), strict=False),
        "updated_at": doc.get("updated_at"),
        "created_at": doc.get("created_at"),
    }
