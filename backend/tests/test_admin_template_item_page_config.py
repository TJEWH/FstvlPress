from __future__ import annotations

from copy import deepcopy
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.collection_names import (  # noqa: E402
    ITEM_PAGE_CONFIG_COLLECTION,
    TEMPLATE_PAGES_COLLECTION,
)
from app.routers.v1 import admin_templates  # noqa: E402
from app.template_sync import GLOBAL_ITEM_PAGE_CONFIG_DOC_ID  # noqa: E402


class FakeResult:
    def __init__(self, *, modified_count: int = 0, deleted_count: int = 0) -> None:
        self.modified_count = modified_count
        self.deleted_count = deleted_count


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None, *, count: int = 0) -> None:
        self.docs = [deepcopy(doc) for doc in docs or []]
        self.count = count

    def _matches(self, doc: dict, query: dict) -> bool:
        return all(doc.get(key) == value for key, value in query.items())

    async def find_one(self, query: dict, *_args, **_kwargs) -> dict | None:
        for doc in self.docs:
            if self._matches(doc, query):
                return doc
        return None

    async def update_one(self, query: dict, update: dict, *_args, upsert: bool = False, **_kwargs) -> FakeResult:
        for doc in self.docs:
            if not self._matches(doc, query):
                continue
            for key, value in update.get("$set", {}).items():
                doc[key] = deepcopy(value)
            return FakeResult(modified_count=1)
        if upsert:
            doc = deepcopy(query)
            for key, value in update.get("$setOnInsert", {}).items():
                doc[key] = deepcopy(value)
            for key, value in update.get("$set", {}).items():
                doc[key] = deepcopy(value)
            self.docs.append(doc)
            return FakeResult(modified_count=1)
        return FakeResult()

    async def delete_one(self, query: dict, *_args, **_kwargs) -> FakeResult:
        for index, doc in enumerate(self.docs):
            if not self._matches(doc, query):
                continue
            del self.docs[index]
            return FakeResult(deleted_count=1)
        return FakeResult()

    async def count_documents(self, _query: dict, *_args, **_kwargs) -> int:
        return self.count


class FakeDb:
    def __init__(self, *, item_config: list[dict], templates: list[dict], linked_pages_count: int = 0) -> None:
        self.collections = {
            ITEM_PAGE_CONFIG_COLLECTION: FakeCollection(item_config),
            TEMPLATE_PAGES_COLLECTION: FakeCollection(templates),
            "pages": FakeCollection(count=linked_pages_count),
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


def item_config_doc(**overrides) -> dict:
    return {
        "_id": GLOBAL_ITEM_PAGE_CONFIG_DOC_ID,
        "blog_item_template_path": "",
        "program_stage_template_path": "",
        "program_gig_template_path": "",
        **overrides,
    }


class AdminTemplateItemPageConfigTests(unittest.IsolatedAsyncioTestCase):
    async def test_global_item_page_config_clears_missing_blog_template_path(self) -> None:
        db = FakeDb(
            item_config=[item_config_doc(blog_item_template_path="toast/gugs")],
            templates=[],
        )

        with patch("app.routers.v1.admin_templates._db", return_value=db):
            result = await admin_templates.get_item_page_config_route()

        self.assertEqual("", result["blog_item_template_path"])
        stored = db[ITEM_PAGE_CONFIG_COLLECTION].docs[0]
        self.assertEqual("", stored["blog_item_template_path"])

    async def test_global_item_page_config_keeps_valid_blog_template_path(self) -> None:
        db = FakeDb(
            item_config=[item_config_doc(blog_item_template_path="toast/gugs")],
            templates=[
                {
                    "_id": "template-1",
                    "template_name": "gugs",
                    "parent_route": "/toast",
                    "source_type": "blog",
                    "source_kind": "item",
                }
            ],
        )

        with patch("app.routers.v1.admin_templates._db", return_value=db):
            result = await admin_templates.get_item_page_config_route()

        self.assertEqual("toast/gugs", result["blog_item_template_path"])
        stored = db[ITEM_PAGE_CONFIG_COLLECTION].docs[0]
        self.assertEqual("toast/gugs", stored["blog_item_template_path"])

    async def test_delete_active_item_page_template_clears_global_config_pointer(self) -> None:
        db = FakeDb(
            item_config=[item_config_doc(blog_item_template_path="toast/gugs")],
            templates=[
                {
                    "_id": "template-1",
                    "template_name": "gugs",
                    "parent_route": "/toast",
                    "source_type": "blog",
                    "source_kind": "item",
                }
            ],
        )
        cleanup_mock = AsyncMock(return_value={"removed_count": 0})

        with patch("app.routers.v1.admin_templates._db", return_value=db), patch(
            "app.routers.v1.admin_templates.cleanup_generated_item_pages_for_template",
            cleanup_mock,
        ):
            result = await admin_templates.delete_page_template("toast/gugs")

        self.assertEqual({"ok": True, "removed_item_pages_count": 0}, result)
        self.assertEqual([], db[TEMPLATE_PAGES_COLLECTION].docs)
        stored = db[ITEM_PAGE_CONFIG_COLLECTION].docs[0]
        self.assertEqual("", stored["blog_item_template_path"])
        cleanup_mock.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
