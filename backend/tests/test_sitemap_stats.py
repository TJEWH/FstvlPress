from __future__ import annotations

import asyncio
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bson import ObjectId
from fastapi import Response

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.collection_names import PAGE_HIT_DAYS_COLLECTION, PAGES_COLLECTION  # noqa: E402
from app.routers.v1.pages import record_public_page_hit  # noqa: E402
from app.routers.v1.sitemap import get_sitemap_stats, reset_sitemap_stats  # noqa: E402


class FakeCursor:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        docs = [deepcopy(doc) for doc in self.docs]
        return docs if length is None else docs[:length]


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs = [deepcopy(doc) for doc in (docs or [])]

    async def find_one(self, query: dict, *_args, **_kwargs) -> dict | None:
        for doc in self.docs:
            if self._matches(doc, query):
                return doc
        return None

    def find(self, query: dict | None = None, *_args, **_kwargs) -> FakeCursor:
        query = query or {}
        return FakeCursor([doc for doc in self.docs if self._matches(doc, query)])

    async def update_one(self, query: dict, update: dict, *_args, upsert: bool = False, **_kwargs):
        doc = await self.find_one(query)
        if not doc and upsert:
            doc = {key: value for key, value in query.items() if not isinstance(value, dict)}
            self.docs.append(doc)
            if "$setOnInsert" in update:
                doc.update(deepcopy(update["$setOnInsert"]))
        if not doc:
            return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None)
        self._apply_update(doc, update)
        return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)

    async def update_many(self, query: dict, update: dict, *_args, **_kwargs):
        matched = 0
        for doc in self.docs:
            if not self._matches(doc, query):
                continue
            matched += 1
            self._apply_update(doc, update)
        return SimpleNamespace(matched_count=matched, modified_count=matched)

    async def delete_many(self, query: dict):
        original = len(self.docs)
        self.docs = [doc for doc in self.docs if not self._matches(doc, query)]
        return SimpleNamespace(deleted_count=original - len(self.docs))

    def _apply_update(self, doc: dict, update: dict) -> None:
        if "$inc" in update:
            for key, value in update["$inc"].items():
                doc[key] = int(doc.get(key) or 0) + int(value)
        if "$set" in update:
            doc.update(deepcopy(update["$set"]))
        if "$unset" in update:
            for key in update["$unset"].keys():
                doc.pop(key, None)

    @classmethod
    def _matches(cls, doc: dict, query: dict) -> bool:
        return all(cls._matches_key(doc, key, value) for key, value in query.items())

    @classmethod
    def _matches_key(cls, doc: dict, key: str, value) -> bool:
        if key == "$and":
            return all(cls._matches(doc, item) for item in value)
        if key == "$or":
            return any(cls._matches(doc, item) for item in value)
        actual = doc.get(key)
        if isinstance(value, dict):
            if "$in" in value and actual not in value["$in"]:
                return False
            if "$gte" in value and actual < value["$gte"]:
                return False
            if "$lte" in value and actual > value["$lte"]:
                return False
            return True
        return actual == value


class FakeDb:
    def __init__(self, *, pages: list[dict], hit_days: list[dict] | None = None) -> None:
        self.collections = {
            PAGES_COLLECTION: FakeCollection(pages),
            PAGE_HIT_DAYS_COLLECTION: FakeCollection(hit_days),
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


class SitemapStatsTests(unittest.TestCase):
    def test_public_hit_increments_total_and_daily_bucket(self) -> None:
        page_id = ObjectId()
        db = FakeDb(
            pages=[
                {
                    "_id": page_id,
                    "slug": "landing",
                    "status": "published",
                    "anonymous_hit_count": 0,
                }
            ],
        )
        request = SimpleNamespace(headers={})

        with patch("app.routers.v1.pages._db", return_value=db):
            asyncio.run(record_public_page_hit("landing", request, Response()))
            asyncio.run(record_public_page_hit("landing", request, Response()))

        self.assertEqual(2, db[PAGES_COLLECTION].docs[0]["anonymous_hit_count"])
        self.assertEqual(1, len(db[PAGE_HIT_DAYS_COLLECTION].docs))
        bucket = db[PAGE_HIT_DAYS_COLLECTION].docs[0]
        self.assertEqual(page_id, bucket["page_id"])
        self.assertEqual("landing", bucket["slug"])
        self.assertEqual(datetime.now(timezone.utc).date().isoformat(), bucket["day"])
        self.assertEqual(2, bucket["count"])

    def test_public_hit_ignores_authenticated_requests(self) -> None:
        db = FakeDb(
            pages=[
                {
                    "_id": ObjectId(),
                    "slug": "landing",
                    "status": "published",
                    "anonymous_hit_count": 0,
                }
            ],
        )
        request = SimpleNamespace(headers={"authorization": "Bearer token"})

        with patch("app.routers.v1.pages._db", return_value=db):
            asyncio.run(record_public_page_hit("landing", request, Response()))

        self.assertEqual(0, db[PAGES_COLLECTION].docs[0]["anonymous_hit_count"])
        self.assertEqual([], db[PAGE_HIT_DAYS_COLLECTION].docs)

    def test_stats_endpoint_returns_hierarchy_and_daily_buckets(self) -> None:
        landing_id = ObjectId()
        about_id = ObjectId()
        team_id = ObjectId()
        hidden_id = ObjectId()
        construction_id = ObjectId()
        today = datetime.now(timezone.utc).date().isoformat()
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        db = FakeDb(
            pages=[
                {"_id": landing_id, "slug": "landing", "title": {"en": "Home"}, "status": "published", "anonymous_hit_count": 3},
                {"_id": about_id, "slug": "about", "title": {"en": "About"}, "status": "published", "anonymous_hit_count": 2},
                {"_id": team_id, "slug": "about/team", "title": {"en": "Team"}, "status": "published", "anonymous_hit_count": 5},
                {"_id": hidden_id, "slug": "hidden", "title": {"en": "Hidden"}, "status": "hidden", "anonymous_hit_count": 9},
                {"_id": construction_id, "slug": "preview", "title": {"en": "Preview"}, "status": "under_construction", "anonymous_hit_count": 7},
            ],
            hit_days=[
                {"page_id": about_id, "slug": "about", "day": today, "count": 2},
                {"page_id": team_id, "slug": "about/team", "day": yesterday, "count": 4},
                {"page_id": hidden_id, "slug": "hidden", "day": today, "count": 9},
            ],
        )

        with patch("app.routers.v1.sitemap._db", return_value=db):
            payload = asyncio.run(get_sitemap_stats(days=30))

        self.assertEqual(30, len(payload["days"]))
        self.assertEqual(10, payload["totals"]["total_hit_count"])
        pages_by_slug = {page["slug"]: page for page in payload["pages"]}
        self.assertEqual({"landing", "about", "about/team"}, set(pages_by_slug))
        self.assertIsNone(pages_by_slug["landing"]["parent_id"])
        self.assertEqual(str(landing_id), pages_by_slug["about"]["parent_id"])
        self.assertEqual(str(about_id), pages_by_slug["about/team"]["parent_id"])
        self.assertEqual(
            {str(landing_id), str(about_id), str(team_id)},
            set(pages_by_slug["landing"]["descendant_ids"]),
        )
        self.assertEqual(
            {str(about_id), str(team_id)},
            set(pages_by_slug["about"]["descendant_ids"]),
        )
        self.assertEqual(2, len(payload["daily_hits"]))

    def test_stats_endpoint_all_time_includes_older_daily_buckets(self) -> None:
        landing_id = ObjectId()
        today = datetime.now(timezone.utc).date()
        old_day = (today - timedelta(days=45)).isoformat()
        today_key = today.isoformat()
        db = FakeDb(
            pages=[
                {
                    "_id": landing_id,
                    "slug": "landing",
                    "title": {"en": "Home"},
                    "status": "published",
                    "anonymous_hit_count": 8,
                },
            ],
            hit_days=[
                {"page_id": landing_id, "slug": "landing", "day": old_day, "count": 3},
                {"page_id": landing_id, "slug": "landing", "day": today_key, "count": 5},
            ],
        )

        with patch("app.routers.v1.sitemap._db", return_value=db):
            recent_payload = asyncio.run(get_sitemap_stats(days=30))
            all_time_payload = asyncio.run(get_sitemap_stats(days="all"))

        self.assertEqual([today_key], [row["day"] for row in recent_payload["daily_hits"]])
        self.assertTrue(all_time_payload["range"]["all_time"])
        self.assertEqual(old_day, all_time_payload["range"]["start_day"])
        self.assertEqual(today_key, all_time_payload["range"]["end_day"])
        self.assertEqual(46, all_time_payload["range"]["days"])
        self.assertEqual(
            [old_day, today_key],
            [row["day"] for row in all_time_payload["daily_hits"]],
        )

    def test_reset_stats_clears_totals_and_daily_buckets(self) -> None:
        db = FakeDb(
            pages=[
                {
                    "_id": ObjectId(),
                    "slug": "landing",
                    "status": "published",
                    "anonymous_hit_count": 4,
                    "anonymous_last_hit_at": datetime.now(timezone.utc),
                }
            ],
            hit_days=[
                {
                    "page_id": ObjectId(),
                    "slug": "landing",
                    "day": datetime.now(timezone.utc).date().isoformat(),
                    "count": 4,
                }
            ],
        )

        with patch("app.routers.v1.sitemap._db", return_value=db):
            payload = asyncio.run(reset_sitemap_stats())

        self.assertTrue(payload["ok"])
        self.assertEqual(0, db[PAGES_COLLECTION].docs[0]["anonymous_hit_count"])
        self.assertNotIn("anonymous_last_hit_at", db[PAGES_COLLECTION].docs[0])
        self.assertEqual([], db[PAGE_HIT_DAYS_COLLECTION].docs)


if __name__ == "__main__":
    unittest.main()
