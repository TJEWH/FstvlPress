from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bson import ObjectId

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.collection_names import PAGE_REDIRECTS_COLLECTION  # noqa: E402
from app.routers.v1.pages import delete_page  # noqa: E402


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs = [dict(doc) for doc in (docs or [])]

    async def find_one(self, query: dict, *_args, **_kwargs) -> dict | None:
        for doc in self.docs:
            if self._matches(doc, query):
                return doc
        return None

    async def insert_one(self, doc: dict):
        to_insert = dict(doc)
        to_insert.setdefault("_id", ObjectId())
        self.docs.append(to_insert)
        return SimpleNamespace(inserted_id=to_insert["_id"])

    async def update_one(self, query: dict, update: dict, *_args, **_kwargs):
        doc = await self.find_one(query)
        if not doc:
            return SimpleNamespace(modified_count=0)
        if "$set" in update:
            doc.update(update["$set"])
        return SimpleNamespace(modified_count=1)

    async def delete_one(self, query: dict):
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                self.docs.pop(index)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    @staticmethod
    def _matches(doc: dict, query: dict) -> bool:
        return all(doc.get(key) == value for key, value in query.items())


class FakeDb:
    def __init__(
        self,
        *,
        pages: list[dict],
        redirects: list[dict] | None = None,
    ) -> None:
        self.collections = {
            "pages": FakeCollection(pages),
            PAGE_REDIRECTS_COLLECTION: FakeCollection(redirects),
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


class PageDeletedRedirectTests(unittest.TestCase):
    def test_deleting_published_page_creates_generated_410_redirect(self) -> None:
        db = FakeDb(
            pages=[
                {
                    "_id": ObjectId(),
                    "slug": "public-page",
                    "status": "published",
                }
            ]
        )

        with patch("app.routers.v1.pages._db", return_value=db):
            result = asyncio.run(delete_page("public-page"))

        self.assertEqual({"created": 1, "updated": 0, "skipped_custom": 0}, result["gone_redirect"])
        self.assertEqual([], db["pages"].docs)
        self.assertEqual(1, len(db[PAGE_REDIRECTS_COLLECTION].docs))
        redirect = db[PAGE_REDIRECTS_COLLECTION].docs[0]
        self.assertEqual("/public-page", redirect["source_path"])
        self.assertIsNone(redirect["target_path"])
        self.assertEqual(410, redirect["status_code"])
        self.assertEqual("generated", redirect["kind"])
        self.assertEqual("deleted_public_page", redirect["generated_reason"])

    def test_deleting_public_under_construction_page_creates_410_redirect(self) -> None:
        db = FakeDb(
            pages=[
                {
                    "_id": ObjectId(),
                    "slug": "preview-live",
                    "status": "under_construction",
                }
            ]
        )

        with patch("app.routers.v1.pages._db", return_value=db):
            result = asyncio.run(delete_page("preview-live"))

        self.assertEqual({"created": 1, "updated": 0, "skipped_custom": 0}, result["gone_redirect"])
        self.assertEqual(410, db[PAGE_REDIRECTS_COLLECTION].docs[0]["status_code"])

    def test_deleting_hidden_page_does_not_create_redirect(self) -> None:
        db = FakeDb(
            pages=[
                {
                    "_id": ObjectId(),
                    "slug": "draft-page",
                    "status": "hidden",
                }
            ]
        )

        with patch("app.routers.v1.pages._db", return_value=db):
            result = asyncio.run(delete_page("draft-page"))

        self.assertIsNone(result["gone_redirect"])
        self.assertEqual([], db[PAGE_REDIRECTS_COLLECTION].docs)

    def test_deleting_scheduled_hidden_page_after_publish_time_creates_redirect(self) -> None:
        db = FakeDb(
            pages=[
                {
                    "_id": ObjectId(),
                    "slug": "scheduled-public",
                    "status": "hidden",
                    "publish_at": datetime.now(timezone.utc) - timedelta(minutes=5),
                }
            ]
        )

        with patch("app.routers.v1.pages._db", return_value=db):
            result = asyncio.run(delete_page("scheduled-public"))

        self.assertEqual({"created": 1, "updated": 0, "skipped_custom": 0}, result["gone_redirect"])
        self.assertEqual("/scheduled-public", db[PAGE_REDIRECTS_COLLECTION].docs[0]["source_path"])

    def test_deleting_public_page_keeps_existing_custom_redirect(self) -> None:
        custom_redirect = {
            "_id": ObjectId(),
            "source_path": "/public-page",
            "target_path": "/elsewhere",
            "status_code": 301,
            "kind": "custom",
        }
        db = FakeDb(
            pages=[
                {
                    "_id": ObjectId(),
                    "slug": "public-page",
                    "status": "published",
                }
            ],
            redirects=[custom_redirect],
        )

        with patch("app.routers.v1.pages._db", return_value=db):
            result = asyncio.run(delete_page("public-page"))

        self.assertEqual({"created": 0, "updated": 0, "skipped_custom": 1}, result["gone_redirect"])
        self.assertEqual([custom_redirect], db[PAGE_REDIRECTS_COLLECTION].docs)


if __name__ == "__main__":
    unittest.main()
