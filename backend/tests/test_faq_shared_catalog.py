from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.sections.sections import get_default_type_data  # noqa: E402
from app.db import _build_faq_section_cleanup_update  # noqa: E402
from app.revisioning import normalize_faq_shared_content_snapshot  # noqa: E402
from app.routers.v1.sections import _normalize_section_type_data_for_response  # noqa: E402


class FaqSharedCatalogTests(unittest.TestCase):
    def test_shared_snapshot_keeps_blank_draft_item_with_id(self) -> None:
        normalized = normalize_faq_shared_content_snapshot(
            {
                "items": [
                    {
                        "id": "faq-draft-1",
                        "question": {"de": "", "en": ""},
                        "answer": {"de": "", "en": ""},
                        "tag": {"de": "Allgemein", "en": "General"},
                    }
                ],
                "tags": [{"de": "Allgemein", "en": "General"}],
            }
        )

        self.assertEqual(1, len(normalized["items"]))
        self.assertEqual("faq-draft-1", normalized["items"][0]["id"])
        self.assertEqual({"de": "", "en": ""}, normalized["items"][0]["question"])

    def test_shared_snapshot_dedupes_duplicate_item_ids(self) -> None:
        normalized = normalize_faq_shared_content_snapshot(
            {
                "items": [
                    {"id": "same-id", "question": {"de": "One", "en": ""}},
                    {"id": "same-id", "question": {"de": "Two", "en": ""}},
                ]
            }
        )

        self.assertEqual(1, len(normalized["items"]))
        self.assertEqual("One", normalized["items"][0]["question"]["de"])

    def test_faq_section_legacy_scope_becomes_scopes_and_items_are_stripped(self) -> None:
        normalized = _normalize_section_type_data_for_response(
            "faq",
            {
                "body": {"de": "", "en": ""},
                "scope": {"de": "Tickets", "en": "Tickets"},
                "faqs": [{"id": "legacy-item"}],
                "faqItems": [{"id": "camel-item"}],
                "faqTags": [{"de": "Tickets", "en": "Tickets"}],
                "section_integration_mapping_cache_state": {"old": True},
            },
        )

        self.assertEqual([{"de": "Tickets", "en": "Tickets"}], normalized["scopes"])
        self.assertNotIn("scope", normalized)
        self.assertNotIn("faqs", normalized)
        self.assertNotIn("faqItems", normalized)
        self.assertNotIn("faqTags", normalized)
        self.assertNotIn("section_integration_mapping_cache_state", normalized)

    def test_faq_section_scopes_are_canonical_over_legacy_scope(self) -> None:
        normalized = _normalize_section_type_data_for_response(
            "faq",
            {
                "scope": {"de": "Legacy", "en": "Legacy"},
                "scopes": [
                    {"de": "Tickets", "en": "Tickets"},
                    {"de": "Tickets", "en": "Tickets"},
                    {"de": "", "en": ""},
                ],
            },
        )

        self.assertEqual([{"de": "Tickets", "en": "Tickets"}], normalized["scopes"])
        self.assertNotIn("scope", normalized)

    def test_faq_default_type_data_uses_scopes_only(self) -> None:
        defaults = get_default_type_data("faq")

        self.assertEqual([], defaults["scopes"])
        self.assertNotIn("faqs", defaults)
        self.assertNotIn("scope", defaults)

    def test_faq_db_cleanup_migrates_scope_and_removes_cache_state(self) -> None:
        update = _build_faq_section_cleanup_update(
            {
                "section_type": "faq",
                "section_integration_mapping_cache_state": {"stale": True},
                "type_data": {
                    "schema_version": "v1",
                    "scope": {"de": "Tickets", "en": "Tickets"},
                    "faqs": [],
                    "section_integration_mapping_cache_state": {"stale": True},
                    "border_width": 1,
                },
            }
        )

        self.assertIsNotNone(update)
        assert update is not None
        next_type_data = update["$set"]["type_data"]
        self.assertEqual([{"de": "Tickets", "en": "Tickets"}], next_type_data["scopes"])
        self.assertEqual(1, next_type_data["border_width"])
        self.assertNotIn("scope", next_type_data)
        self.assertNotIn("faqs", next_type_data)
        self.assertNotIn("section_integration_mapping_cache_state", next_type_data)
        self.assertIn("section_integration_mapping_cache_state", update["$unset"])


if __name__ == "__main__":
    unittest.main()
