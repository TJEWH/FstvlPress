from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from bson import ObjectId

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.collection_names import DESIGN_CONFIG_COLLECTION, DESIGN_VERSIONS_COLLECTION  # noqa: E402
from app.db import migrate_design_subversions_to_versions  # noqa: E402
from app.routers.v1 import admin_design  # noqa: E402
from app.security import KeycloakUser  # noqa: E402


class FakeResult:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


class FakeCursor:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = [deepcopy(doc) for doc in docs]

    def sort(self, key, direction=None):
        if isinstance(key, list):
            for field, order in reversed(key):
                self.docs.sort(key=lambda doc: doc.get(field) or datetime.min, reverse=order < 0)
        else:
            self.docs.sort(key=lambda doc: doc.get(key) or datetime.min, reverse=direction < 0)
        return self

    async def to_list(self, length=None):
        docs = self.docs if length is None else self.docs[:length]
        return [deepcopy(doc) for doc in docs]

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self.docs):
            raise StopAsyncIteration
        doc = self.docs[self._idx]
        self._idx += 1
        return deepcopy(doc)


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs = [deepcopy(doc) for doc in (docs or [])]

    def _matches(self, doc: dict, query: dict | None) -> bool:
        if not query:
            return True
        for key, expected in query.items():
            if key == "$or":
                if not any(self._matches(doc, candidate) for candidate in expected):
                    return False
                continue
            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$exists" in expected and (key in doc) is not bool(expected["$exists"]):
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                continue
            if actual != expected:
                return False
        return True

    def _project(self, doc: dict, projection: dict | None) -> dict:
        if not projection:
            return deepcopy(doc)
        projected = {"_id": doc["_id"]} if "_id" in doc and projection.get("_id", 1) else {}
        for key, include in projection.items():
            if include and key in doc:
                projected[key] = deepcopy(doc[key])
        return projected

    def _apply_update(self, doc: dict, update: dict) -> None:
        for key, value in update.get("$set", {}).items():
            doc[key] = deepcopy(value)
        for key in update.get("$unset", {}):
            doc.pop(key, None)

    async def find_one(self, query: dict | None = None, projection: dict | None = None, sort=None):
        docs = [doc for doc in self.docs if self._matches(doc, query)]
        if sort:
            cursor = FakeCursor(docs).sort(sort)
            docs = cursor.docs
        return self._project(docs[0], projection) if docs else None

    def find(self, query: dict | None = None, projection: dict | None = None):
        docs = [self._project(doc, projection) for doc in self.docs if self._matches(doc, query)]
        return FakeCursor(docs)

    async def insert_one(self, doc: dict):
        stored = deepcopy(doc)
        inserted_id = stored.get("_id") or ObjectId()
        stored["_id"] = inserted_id
        self.docs.append(stored)
        return FakeResult(inserted_id=inserted_id)

    async def update_one(self, query: dict, update: dict):
        for doc in self.docs:
            if self._matches(doc, query):
                self._apply_update(doc, update)
                return FakeResult(modified_count=1)
        return FakeResult(modified_count=0)

    async def update_many(self, query: dict, update: dict):
        count = 0
        for doc in self.docs:
            if self._matches(doc, query):
                self._apply_update(doc, update)
                count += 1
        return FakeResult(modified_count=count)

    async def find_one_and_update(self, query: dict, update: dict, return_document=None):
        for doc in self.docs:
            if self._matches(doc, query):
                self._apply_update(doc, update)
                return deepcopy(doc)
        return None

    async def delete_one(self, query: dict):
        before = len(self.docs)
        self.docs = [doc for doc in self.docs if not self._matches(doc, query)]
        return FakeResult(deleted_count=before - len(self.docs))


class DesignVersionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_db = admin_design._db
        self.versions = FakeCollection()
        self.design_config = FakeCollection()
        self.fake_db = {
            DESIGN_VERSIONS_COLLECTION: self.versions,
            DESIGN_CONFIG_COLLECTION: self.design_config,
        }
        admin_design._db = lambda: self.fake_db
        self.user = KeycloakUser(sub="user-1", username="editor", name="Design Editor")

    def tearDown(self) -> None:
        admin_design._db = self.original_db

    async def test_migration_flattens_legacy_subversion(self) -> None:
        parent_id = ObjectId()
        child_id = ObjectId()
        self.versions.docs = [
            {
                "_id": parent_id,
                "title": "Parent",
                "design_settings": {"colors": {"primary": "red", "secondary": "blue"}, "font": "A"},
            },
            {
                "_id": child_id,
                "title": "Variant",
                "parent_id": parent_id,
                "design_settings": {"colors": {"primary": "green"}},
                "changelog": {"changed_keys": ["colors.primary"]},
            },
        ]

        await migrate_design_subversions_to_versions(self.fake_db)

        child = await self.versions.find_one({"_id": child_id})
        self.assertIsNone(child["parent_id"])
        self.assertEqual(
            {"colors": {"primary": "green", "secondary": "blue"}, "font": "A"},
            child["design_settings"],
        )
        self.assertIn("hash", child)
        self.assertIn("flattened_at", child)
        self.assertEqual({"changed_keys": ["colors.primary"]}, child["changelog"])

    async def test_create_version_stores_full_snapshot_without_parent_id(self) -> None:
        self.design_config.docs = [{"_id": ObjectId(), "key": "global"}]

        version = await admin_design.create_design_version(
            {
                "title": "Flat",
                "rating": 12,
                "parent_id": None,
                "design_settings": {"colors": {"primary": "green"}},
            },
            user=self.user,
        )

        stored = self.versions.docs[0]
        self.assertNotIn("parent_id", stored)
        self.assertEqual({"colors": {"primary": "green"}}, stored["design_settings"])
        self.assertEqual(10, stored["rating"])
        self.assertNotIn("design_settings", version)
        self.assertNotIn("parent_id", version)
        self.assertEqual(version["id"], self.design_config.docs[0]["comparison_version_id"])

    async def test_update_version_replaces_snapshot_and_sanitizes_changelog(self) -> None:
        version_id = ObjectId()
        self.design_config.docs = [{"_id": ObjectId(), "key": "global"}]
        self.versions.docs = [
            {
                "_id": version_id,
                "title": "Current",
                "description": "",
                "rating": 3,
                "hash": "old",
                "parent_id": ObjectId(),
                "design_settings": {"colors": {"primary": "red"}},
            }
        ]

        updated = await admin_design.update_design_version(
            str(version_id),
            {
                "design_settings": {"colors": {"primary": "green"}},
                "changelog": {
                    "changed_keys": [" colors.primary ", "colors.primary", 1, ""],
                    "base_version_title": "Current",
                },
            },
            user=self.user,
        )

        stored = self.versions.docs[0]
        self.assertEqual({"colors": {"primary": "green"}}, stored["design_settings"])
        self.assertNotEqual("old", stored["hash"])
        self.assertEqual("Design Editor", stored["updated_by"])
        self.assertNotIn("parent_id", stored)
        self.assertEqual(["colors.primary"], stored["changelog"]["changed_keys"])
        self.assertEqual(1, stored["changelog"]["change_count"])
        self.assertNotIn("design_settings", updated)
        self.assertEqual(str(version_id), self.design_config.docs[0]["comparison_version_id"])

    async def test_load_version_persists_comparison_version_id(self) -> None:
        version_id = ObjectId()
        self.versions.docs = [
            {
                "_id": version_id,
                "title": "Loaded",
                "design_settings": {"colors": {"primary": "green"}, "font": "A"},
            }
        ]
        self.design_config.docs = [
            {
                "_id": ObjectId(),
                "key": "global",
                "created_at": datetime(2024, 1, 1),
                "colors": {"primary": "red"},
            }
        ]

        result = await admin_design.load_design_version(str(version_id))

        self.assertTrue(result["loaded"])
        self.assertEqual(str(version_id), self.design_config.docs[0]["comparison_version_id"])
        self.assertEqual({"primary": "green"}, self.design_config.docs[0]["colors"])

    async def test_list_versions_returns_persisted_comparison_baseline(self) -> None:
        version_id = ObjectId()
        self.versions.docs = [
            {
                "_id": version_id,
                "title": "Baseline",
                "created_at": datetime(2024, 1, 1),
                "is_published": True,
                "design_settings": {"colors": {"primary": "red"}, "font": "A"},
            }
        ]
        self.design_config.docs = [
            {
                "_id": ObjectId(),
                "key": "global",
                "comparison_version_id": str(version_id),
                "colors": {"primary": "green"},
                "font": "A",
            }
        ]

        result = await admin_design.list_design_versions(self.user)

        baseline = result["comparison_baseline"]
        self.assertEqual(str(version_id), baseline["id"])
        self.assertEqual("persisted", baseline["source"])
        self.assertEqual({"colors": {"primary": "red"}, "font": "A"}, baseline["design_settings"])
        self.assertEqual(["design_settings.colors"], baseline["changed_keys"])
        self.assertEqual(1, baseline["change_count"])

    async def test_list_versions_falls_back_to_most_similar_when_persisted_missing(self) -> None:
        farther_id = ObjectId()
        closest_id = ObjectId()
        missing_id = ObjectId()
        self.versions.docs = [
            {
                "_id": farther_id,
                "title": "Farther",
                "created_at": datetime(2024, 1, 2),
                "is_published": False,
                "design_settings": {"colors": {"primary": "red"}, "font": "B", "spacing": 12},
            },
            {
                "_id": closest_id,
                "title": "Closest",
                "created_at": datetime(2024, 1, 1),
                "is_published": True,
                "design_settings": {"colors": {"primary": "green"}, "font": "A", "spacing": 12},
            },
        ]
        self.design_config.docs = [
            {
                "_id": ObjectId(),
                "key": "global",
                "comparison_version_id": str(missing_id),
                "colors": {"primary": "green"},
                "font": "A",
                "spacing": 18,
            }
        ]

        result = await admin_design.list_design_versions(self.user)

        baseline = result["comparison_baseline"]
        self.assertEqual(str(closest_id), baseline["id"])
        self.assertEqual("similar", baseline["source"])
        self.assertEqual(["design_settings.spacing"], baseline["changed_keys"])
        self.assertNotIn("comparison_version_id", self.design_config.docs[0])

    async def test_delete_version_deletes_only_target_and_blocks_published(self) -> None:
        parent_id = ObjectId()
        child_id = ObjectId()
        published_id = ObjectId()
        self.design_config.docs = [{"_id": ObjectId(), "key": "global", "comparison_version_id": str(parent_id)}]
        self.versions.docs = [
            {"_id": parent_id, "title": "Parent", "is_published": False},
            {"_id": child_id, "title": "Legacy child", "parent_id": parent_id, "is_published": False},
            {"_id": published_id, "title": "Published", "is_published": True},
        ]

        await admin_design.delete_design_version(str(parent_id))

        remaining_ids = {doc["_id"] for doc in self.versions.docs}
        self.assertNotIn(parent_id, remaining_ids)
        self.assertIn(child_id, remaining_ids)
        self.assertNotIn("comparison_version_id", self.design_config.docs[0])

        with self.assertRaises(Exception):
            await admin_design.delete_design_version(str(published_id))


if __name__ == "__main__":
    unittest.main()
