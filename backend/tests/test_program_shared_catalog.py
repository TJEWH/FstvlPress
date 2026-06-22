from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routers.v1.program import _collect_duplicate_program_integration_item_keys  # noqa: E402
from app.program_catalog import normalize_program_shared_content_snapshot  # noqa: E402


class ProgramSharedCatalogTests(unittest.TestCase):
    def test_detects_duplicate_integration_item_key_with_different_gig_ids(self) -> None:
        duplicates = _collect_duplicate_program_integration_item_keys(
            [
                {"id": "gig-existing", "integration_item_key": "review-42"},
                {"id": "gig-copy", "integration_item_key": "review-42"},
                {"id": "gig-other", "integration_item_key": "review-43"},
            ]
        )

        self.assertEqual(
            [{"key": "review-42", "ids": ["gig-copy", "gig-existing"]}],
            duplicates,
        )

    def test_allows_same_integration_item_key_for_same_gig_id(self) -> None:
        duplicates = _collect_duplicate_program_integration_item_keys(
            [
                {"id": "gig-existing", "integration_item_key": "review-42"},
                {"id": "gig-existing", "integration_item_key": "review-42"},
            ]
        )

        self.assertEqual([], duplicates)

    def test_detects_supported_external_key_aliases(self) -> None:
        duplicates = _collect_duplicate_program_integration_item_keys(
            [
                {"id": "gig-existing", "template_integration_item_key": "review-42"},
                {"id": "gig-copy", "reviewItemKey": "review-42"},
            ]
        )

        self.assertEqual(
            [{"key": "review-42", "ids": ["gig-copy", "gig-existing"]}],
            duplicates,
        )

    def test_detects_schema_external_id_after_program_normalization(self) -> None:
        normalized = normalize_program_shared_content_snapshot(
            {
                "program_gigs_integration_mapping_cache_state": {
                    "integration_output_primary_key_path": "external.id",
                },
                "gigs": [
                    {
                        "id": "gig-ih-111111111111111111111111",
                        "external": {"id": "schema-42"},
                        "title": {"de": "Original", "en": ""},
                    },
                    {
                        "id": "gig-ih-222222222222222222222222",
                        "external": {"id": "schema-42"},
                        "title": {"de": "Copy", "en": ""},
                    },
                ],
            }
        )

        duplicates = _collect_duplicate_program_integration_item_keys(normalized["gigs"])

        self.assertEqual(
            [
                {
                    "key": "schema-42",
                    "ids": [
                        "gig-ih-111111111111111111111111",
                        "gig-ih-222222222222222222222222",
                    ],
                }
            ],
            duplicates,
        )


if __name__ == "__main__":
    unittest.main()
