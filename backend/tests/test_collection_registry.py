from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.collection_names import (  # noqa: E402
    ASSETS_COLLECTION,
    COLLECTION_GROUP_BY_NAME,
    COLLECTION_GROUP_META,
    MANAGED_COLLECTIONS,
    PAGES_COLLECTION,
    build_collection_summary,
)
from app.db import REQUIRED_COLLECTIONS  # noqa: E402
from app.routers.v1.backup import (  # noqa: E402
    ResetAllStoredDataRequest,
    _build_collection_options,
    _resolve_collections_to_delete,
)


class FakeCollection:
    def __init__(self, count: int) -> None:
        self.count = count

    async def count_documents(self, *_args, **_kwargs) -> int:
        return self.count


class FakeDb:
    def __init__(self, collections: dict[str, int]) -> None:
        self.collections = {
            name: FakeCollection(count)
            for name, count in collections.items()
        }

    async def list_collection_names(self) -> list[str]:
        return list(self.collections.keys())

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


class CollectionRegistryTests(unittest.TestCase):
    def test_required_collections_share_single_registry_without_duplicates(self) -> None:
        self.assertIs(REQUIRED_COLLECTIONS, MANAGED_COLLECTIONS)
        self.assertEqual(len(MANAGED_COLLECTIONS), len(set(MANAGED_COLLECTIONS)))

    def test_every_managed_collection_has_explicit_group_metadata(self) -> None:
        managed = set(MANAGED_COLLECTIONS)
        self.assertEqual(managed, set(COLLECTION_GROUP_BY_NAME))
        self.assertTrue(set(COLLECTION_GROUP_BY_NAME.values()) <= set(COLLECTION_GROUP_META))

        for collection_name in MANAGED_COLLECTIONS:
            summary = build_collection_summary(collection_name, 0)
            self.assertIn(summary["collection_group"], COLLECTION_GROUP_META)

    def test_collection_options_include_only_existing_managed_collections(self) -> None:
        db = FakeDb({
            PAGES_COLLECTION: 3,
            ASSETS_COLLECTION: 2,
            "manual_collection": 99,
            "system.profile": 1,
        })

        result = asyncio.run(_build_collection_options(db))

        self.assertEqual(5, result["total_documents"])
        self.assertEqual(
            [PAGES_COLLECTION, ASSETS_COLLECTION],
            [entry["name"] for entry in result["collections"]],
        )

    def test_selected_reset_delete_uses_only_manageable_collections(self) -> None:
        result = _resolve_collections_to_delete(
            existing_collections=[PAGES_COLLECTION, "manual_collection"],
            manageable_collections=[PAGES_COLLECTION],
            payload=ResetAllStoredDataRequest(
                use_delete_collections=True,
                delete_collections=[PAGES_COLLECTION, "manual_collection"],
            ),
        )

        collections_to_delete, excluded_collections, excluded_not_found, deleted_not_found = result
        self.assertEqual([PAGES_COLLECTION], collections_to_delete)
        self.assertEqual([], excluded_collections)
        self.assertEqual([], excluded_not_found)
        self.assertEqual(["manual_collection"], deleted_not_found)


if __name__ == "__main__":
    unittest.main()
