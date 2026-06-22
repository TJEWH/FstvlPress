from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import HTTPException  # noqa: E402

from app.collection_names import CHANGELOG_COLLECTION, PAGES_COLLECTION  # noqa: E402
from app.routers.v1 import admin_devops as admin_devops_module  # noqa: E402
from app.routers.v1.admin_devops import (  # noqa: E402
    _can_manage_tutorial,
    _can_view_tutorial,
    _get_default_config,
    _normalize_tutorial_doc,
    _normalize_tutorials,
)
from app.security import KeycloakUser  # noqa: E402


class FakeCursor:
    def __init__(self, docs: list[dict]):
        self.docs = [dict(doc) for doc in docs]
        self.skip_count = 0
        self.limit_count: int | None = None

    def sort(self, key: str, direction: int):
        reverse = direction < 0
        self.docs.sort(key=lambda doc: doc.get(key) or datetime.min, reverse=reverse)
        return self

    def skip(self, count: int):
        self.skip_count = max(0, count)
        return self

    def limit(self, count: int):
        self.limit_count = max(0, count)
        return self

    async def to_list(self, length: int | None = None):
        end = None if self.limit_count is None else self.skip_count + self.limit_count
        docs = self.docs[self.skip_count:end]
        if length is not None:
            docs = docs[:length]
        return [dict(doc) for doc in docs]


class FakeCollection:
    def __init__(self, docs: list[dict]):
        self.docs = [dict(doc) for doc in docs]

    def _matches(self, doc: dict, query: dict | None) -> bool:
        for key, expected in (query or {}).items():
            actual = doc.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if actual not in set(expected["$in"]):
                    return False
            elif actual != expected:
                return False
        return True

    async def find_one(self, query: dict | None = None, *_args, **_kwargs):
        for doc in self.docs:
            if self._matches(doc, query):
                return dict(doc)
        return None

    def find(self, query: dict | None = None, *_args, **_kwargs):
        return FakeCursor([doc for doc in self.docs if self._matches(doc, query)])

    async def count_documents(self, query: dict | None = None):
        return len([doc for doc in self.docs if self._matches(doc, query)])


class FakeDb:
    def __init__(self, *, pages: list[dict], changelog: list[dict]):
        self.collections = {
            PAGES_COLLECTION: FakeCollection(pages),
            CHANGELOG_COLLECTION: FakeCollection(changelog),
        }

    def __getitem__(self, name: str):
        return self.collections[name]


def make_user(
    *,
    sub: str = "user-1",
    username: str = "editor",
    name: str = "Editor User",
    internal_role: str = "content",
) -> KeycloakUser:
    permissions = {"content:read", "content:write"}
    if internal_role in {"design", "admin_design", "admin_general"}:
        permissions.add("design:write")
    if internal_role in {"admin_design", "admin_general"}:
        permissions.add("admin:design")
    if internal_role == "admin_general":
        permissions.update({"admin:general", "content:admin"})
    return KeycloakUser(
        sub=sub,
        username=username,
        name=name,
        permissions=permissions,
        internal_role=internal_role,
    )


class AdminDevopsTutorialTests(unittest.TestCase):
    def test_default_config_contains_tutorials(self) -> None:
        defaults = _get_default_config()

        self.assertIn("tutorials", defaults)
        self.assertEqual([], defaults["tutorials"])

    def test_tutorial_normalization_keeps_definition_only(self) -> None:
        user = make_user(internal_role="design")
        normalized = _normalize_tutorial_doc(
            {
                "title": "Edit a hero",
                "description": "Learn the page header workflow.",
                "scope": "design",
                "steps": [
                    {
                        "url": "/admin/sitemap/pages",
                        "short_description": "Open the page tree.",
                        "long_description": "Choose the page that owns the header.",
                        "done": True,
                    },
                    {
                        "url": "/about?admin=1",
                        "shortDescription": "Edit the header.",
                    },
                ],
            },
            strict=True,
            user=user,
        )

        assert normalized is not None
        self.assertEqual("Edit a hero", normalized["title"])
        self.assertEqual("design", normalized["scope"])
        self.assertEqual("Editor User", normalized["owner"])
        self.assertEqual([0, 1], [step["order"] for step in normalized["steps"]])
        self.assertNotIn("done", normalized["steps"][0])

    def test_existing_tutorials_self_heal_invalid_entries(self) -> None:
        normalized = _normalize_tutorials(
            [
                {"title": "", "steps": []},
                {
                    "id": "same",
                    "title": "One",
                    "scope": "content",
                    "owner": "owner",
                    "steps": [{"url": "/one", "short_description": "One"}],
                },
                {
                    "id": "same",
                    "title": "Two",
                    "scope": "content",
                    "owner": "owner",
                    "steps": [{"url": "/two", "short_description": "Two"}],
                },
            ],
            strict=False,
        )

        self.assertEqual(2, len(normalized))
        self.assertEqual("same", normalized[0]["id"])
        self.assertEqual("same-3", normalized[1]["id"])

    def test_scope_visibility_uses_role_rank(self) -> None:
        content_user = make_user(internal_role="content")
        design_user = make_user(internal_role="design")
        design_tutorial = {
            "scope": "design",
            "owner": "owner",
            "steps": [{"url": "/admin/design/sections", "short_description": "Open design"}],
        }

        self.assertFalse(_can_view_tutorial(design_tutorial, content_user))
        self.assertTrue(_can_view_tutorial(design_tutorial, design_user))

    def test_owner_or_admin_general_can_manage(self) -> None:
        owner = make_user(sub="owner-sub", username="owner", name="Owner", internal_role="content")
        other = make_user(sub="other-sub", username="other", name="Other", internal_role="content")
        admin = make_user(sub="admin-sub", username="admin", name="Admin", internal_role="admin_general")
        tutorial = {
            "owner": "Owner",
            "owner_id": "owner-sub",
            "scope": "content",
            "steps": [{"url": "/admin/devops/tutorials", "short_description": "Open tutorials"}],
        }

        self.assertTrue(_can_manage_tutorial(tutorial, owner))
        self.assertFalse(_can_manage_tutorial(tutorial, other))
        self.assertTrue(_can_manage_tutorial(tutorial, admin))

    def test_invalid_scope_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _normalize_tutorial_doc(
                {
                    "title": "Bad scope",
                    "scope": "everyone",
                    "steps": [{"url": "/admin", "short_description": "Open admin"}],
                },
                strict=True,
                user=make_user(internal_role="admin_general"),
            )

        self.assertEqual(400, ctx.exception.status_code)

    def test_scope_above_user_role_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _normalize_tutorial_doc(
                {
                    "title": "Design only",
                    "scope": "design",
                    "steps": [{"url": "/admin/design/sections", "short_description": "Open design"}],
                },
                strict=True,
                user=make_user(internal_role="content"),
            )

        self.assertEqual(403, ctx.exception.status_code)

    def test_script_urls_are_rejected(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _normalize_tutorial_doc(
                {
                    "title": "Unsafe",
                    "scope": "content",
                    "steps": [{"url": "javascript:alert(1)", "short_description": "Do not run"}],
                },
                strict=True,
                user=make_user(internal_role="content"),
            )

        self.assertEqual(400, ctx.exception.status_code)


class AdminDevopsChangelogTests(unittest.IsolatedAsyncioTestCase):
    async def test_changelog_page_slug_filters_before_pagination(self) -> None:
        db = FakeDb(
            pages=[
                {
                    "slug": "about",
                    "sections": [
                        {"section_id": "section-a"},
                        {"section_id": "section-b"},
                    ],
                },
                {
                    "slug": "landing",
                    "sections": [{"section_id": "section-c"}],
                },
            ],
            changelog=[
                {
                    "_id": "change-1",
                    "entity_type": "section",
                    "entity_id": "section-a",
                    "section_label": "A",
                    "saved_at": datetime(2026, 1, 3, tzinfo=timezone.utc),
                },
                {
                    "_id": "change-2",
                    "entity_type": "section",
                    "entity_id": "section-c",
                    "section_label": "C",
                    "saved_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
                },
                {
                    "_id": "change-3",
                    "entity_type": "section",
                    "entity_id": "section-b",
                    "section_label": "B",
                    "saved_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                },
            ],
        )

        with patch.object(admin_devops_module, "_db", return_value=db):
            payload = await admin_devops_module.get_admin_devops_changelog(
                limit=1,
                offset=0,
                page_slug="about",
                _=make_user(),
            )

        self.assertEqual(2, payload["total"])
        self.assertTrue(payload["has_more"])
        self.assertEqual(["section-a"], [item["section_id"] for item in payload["items"]])
        self.assertEqual("/about", payload["items"][0]["page_url"])

    async def test_unknown_changelog_page_slug_returns_empty_scope(self) -> None:
        db = FakeDb(
            pages=[],
            changelog=[
                {
                    "_id": "change-1",
                    "entity_type": "section",
                    "entity_id": "section-a",
                    "saved_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                },
            ],
        )

        with patch.object(admin_devops_module, "_db", return_value=db):
            payload = await admin_devops_module.get_admin_devops_changelog(
                limit=10,
                offset=0,
                page_slug="missing",
                _=make_user(),
            )

        self.assertEqual(0, payload["total"])
        self.assertEqual([], payload["items"])
        self.assertFalse(payload["has_more"])


if __name__ == "__main__":
    unittest.main()
