from __future__ import annotations

import sys
import unittest
from pathlib import Path

from bson import ObjectId

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.template_sync import (  # noqa: E402
    ITEM_PAGE_MAPPED_TARGET_VALUES_KEY,
    ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
    _patch_existing_generated_page_mapped_targets,
    normalize_item_page_sync_mode,
)


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs = [dict(doc) for doc in docs or []]
        self.updates: list[tuple[dict, dict]] = []

    async def find_one(self, query: dict, *_args, **_kwargs) -> dict | None:
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return doc
        return None

    async def update_one(self, query: dict, update: dict, *_args, **_kwargs) -> None:
        self.updates.append((dict(query), dict(update)))


class ItemPageMappedConflictTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.template_doc = {
            "page_integration_mapping": {
                "active_mode": "list",
                "list_mappings_by_collection_path": {
                    "page": [
                        {
                            "source_path": "integration.title",
                            "target_path": "title",
                        }
                    ]
                },
            }
        }

    def _db(self, page: dict) -> dict[str, FakeCollection]:
        return {
            "pages": FakeCollection([page]),
            "headers": FakeCollection(),
            "sections": FakeCollection(),
        }

    async def test_dry_run_conflict_check_returns_zero_when_page_matches_last_generated_value(self) -> None:
        page = {
            "_id": ObjectId(),
            "title": "Old generated",
            ITEM_PAGE_MAPPED_TARGET_VALUES_KEY: {"page.title": "Old generated"},
        }
        db = self._db(page)

        report = await _patch_existing_generated_page_mapped_targets(
            db,
            existing_page=page,
            template_doc=self.template_doc,
            page_payload={"title": "Current review"},
            header_payload=None,
            sections_payload=[],
            dry_run=True,
        )

        self.assertEqual({"conflict_count": 0}, report)
        self.assertEqual([], db["pages"].updates)

    async def test_dry_run_conflict_check_counts_local_divergence(self) -> None:
        page = {
            "_id": ObjectId(),
            "title": "Locally edited page title",
            ITEM_PAGE_MAPPED_TARGET_VALUES_KEY: {"page.title": "Old generated"},
        }
        db = self._db(page)

        report = await _patch_existing_generated_page_mapped_targets(
            db,
            existing_page=page,
            template_doc=self.template_doc,
            page_payload={"title": "Current review"},
            header_payload=None,
            sections_payload=[],
            dry_run=True,
        )

        self.assertEqual({"conflict_count": 1}, report)
        self.assertEqual([], db["pages"].updates)

    def test_push_local_to_source_mode_falls_back_to_default_sync_mode(self) -> None:
        self.assertEqual(
            ITEM_PAGE_SYNC_MODE_KEEP_SOURCE,
            normalize_item_page_sync_mode("push_local_to_source"),
        )


if __name__ == "__main__":
    unittest.main()
