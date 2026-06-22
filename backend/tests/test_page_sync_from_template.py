from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from fastapi import HTTPException

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routers.v1 import pages as pages_router  # noqa: E402


class FakePagesCollection:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = [dict(doc) for doc in docs]

    async def find_one(self, query: dict, *_args, **_kwargs) -> dict | None:
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return doc
        return None


class PageSyncFromTemplateTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_uses_default_keep_source_without_force_rebuild(self) -> None:
        page = {
            "_id": ObjectId(),
            "slug": "blog/item",
            "template_managed": True,
            "template_source_type": "blog",
        }
        db = {"pages": FakePagesCollection([page])}
        sync_mock = AsyncMock(return_value={"ok": True, "slug": page["slug"]})
        link_mock = AsyncMock()

        with patch("app.routers.v1.pages._db", return_value=db), patch(
            "app.routers.v1.pages.sync_generated_item_page_from_template_state",
            sync_mock,
        ), patch(
            "app.routers.v1.pages._sync_template_source_link_for_page_slug",
            link_mock,
        ):
            result = await pages_router.sync_page_from_template(
                "blog/item",
                sync_mode=None,
                force_rebuild=False,
            )

        self.assertEqual({"ok": True, "slug": page["slug"]}, result)
        sync_mock.assert_awaited_once_with(
            db,
            page,
            sync_mode="keep_source",
            force_rebuild=False,
        )
        link_mock.assert_not_awaited()

    async def test_conflict_check_is_read_only(self) -> None:
        page = {
            "_id": ObjectId(),
            "slug": "program/gig",
            "template_managed": True,
            "template_source_type": "program_gig",
        }
        db = {"pages": FakePagesCollection([page])}
        sync_mock = AsyncMock(return_value={"ok": True, "slug": page["slug"], "conflict_count": 2})
        link_mock = AsyncMock()

        with patch("app.routers.v1.pages._db", return_value=db), patch(
            "app.routers.v1.pages.sync_generated_item_page_from_template_state",
            sync_mock,
        ), patch(
            "app.routers.v1.pages._sync_template_source_link_for_page_slug",
            link_mock,
        ):
            result = await pages_router.get_page_template_sync_conflicts("program/gig")

        self.assertEqual({"ok": True, "slug": page["slug"], "conflict_count": 2}, result)
        sync_mock.assert_awaited_once_with(
            db,
            page,
            sync_mode="keep_source",
            check_conflicts_only=True,
        )
        link_mock.assert_not_awaited()

    async def test_program_gig_force_rebuild_refreshes_source_link(self) -> None:
        page = {
            "_id": ObjectId(),
            "slug": "program/gig",
            "template_managed": True,
            "template_source_type": "program_gig",
        }
        db = {"pages": FakePagesCollection([page])}
        sync_mock = AsyncMock(return_value={"ok": True, "slug": page["slug"]})
        link_mock = AsyncMock()

        with patch("app.routers.v1.pages._db", return_value=db), patch(
            "app.routers.v1.pages.sync_generated_item_page_from_template_state",
            sync_mock,
        ), patch(
            "app.routers.v1.pages._sync_template_source_link_for_page_slug",
            link_mock,
        ):
            result = await pages_router.sync_page_from_template(
                "program/gig",
                sync_mode="keep_source",
                force_rebuild=True,
            )

        self.assertEqual({"ok": True, "slug": page["slug"]}, result)
        sync_mock.assert_awaited_once_with(
            db,
            page,
            sync_mode="keep_source",
            force_rebuild=True,
        )
        link_mock.assert_awaited_once_with(db, page)

    async def test_non_managed_page_is_rejected(self) -> None:
        page = {
            "_id": ObjectId(),
            "slug": "plain",
            "template_managed": False,
        }
        db = {"pages": FakePagesCollection([page])}
        sync_mock = AsyncMock()

        with patch("app.routers.v1.pages._db", return_value=db), patch(
            "app.routers.v1.pages.sync_generated_item_page_from_template_state",
            sync_mock,
        ):
            with self.assertRaises(HTTPException) as raised:
                await pages_router.sync_page_from_template(
                    "plain",
                    sync_mode=None,
                    force_rebuild=False,
                )

        self.assertEqual(400, raised.exception.status_code)
        sync_mock.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
