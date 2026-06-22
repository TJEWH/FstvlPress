from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routers.v1.integrations import (  # noqa: E402
    _compute_cache_payload_diff,
    _compute_review_data_change_metadata,
    _is_review_override_conflicted,
    _remove_empty_string_list_items,
)


class IntegrationReviewChangeDetectionTests(unittest.TestCase):
    def test_review_diff_ignores_list_order(self) -> None:
        previous = {
            "id": "artist-1",
            "genres": ["Rock", "Hip-Hop/Rap/RnB", "Punk"],
        }
        current = {
            "id": "artist-1",
            "genres": ["Hip-Hop/Rap/RnB", "Rock", "Punk"],
        }

        changed_paths, changed_entries = _compute_cache_payload_diff(
            previous,
            current,
            unordered_lists=True,
        )

        self.assertEqual([], changed_paths)
        self.assertEqual([], changed_entries)

    def test_review_metadata_does_not_mark_reordered_list_item_changed(self) -> None:
        previous_data = [
            {
                "id": "artist-1",
                "genres": ["Rock", "Hip-Hop/Rap/RnB", "Punk"],
            }
        ]
        current_data = [
            {
                "id": "artist-1",
                "genres": ["Hip-Hop/Rap/RnB", "Rock", "Punk"],
            }
        ]

        metadata = _compute_review_data_change_metadata(previous_data, current_data, "id")

        self.assertEqual([], metadata["changed_paths"])
        self.assertEqual([], metadata["changed_entries"])
        self.assertEqual([], metadata["changed_item_keys"])
        self.assertEqual(0, metadata["changed_count"])

    def test_review_metadata_marks_list_membership_change(self) -> None:
        previous_data = [
            {
                "id": "artist-1",
                "genres": ["Rock", "Hip-Hop/Rap/RnB", "Punk"],
            }
        ]
        current_data = [
            {
                "id": "artist-1",
                "genres": ["Hip-Hop/Rap/RnB", "Rock", "Jazz"],
            }
        ]

        metadata = _compute_review_data_change_metadata(previous_data, current_data, "id")

        self.assertEqual(["artist-1.genres"], metadata["changed_paths"])
        self.assertEqual(["artist-1"], metadata["changed_item_keys"])
        self.assertEqual(1, metadata["changed_count"])

    def test_override_conflict_ignores_list_order(self) -> None:
        override_doc = {
            "field_path": "genres",
            "base_fetched_value": ["Rock", "Hip-Hop/Rap/RnB", "Punk"],
            "base_missing": False,
        }
        current_item = {
            "genres": ["Hip-Hop/Rap/RnB", "Rock", "Punk"],
        }

        self.assertFalse(_is_review_override_conflicted(override_doc, current_item))

    def test_fetch_cleanup_removes_empty_string_list_items(self) -> None:
        payload = {
            "title": "",
            "genres": ["", "Rock", "  ", {"tags": ["", "Punk"]}],
        }

        cleaned = _remove_empty_string_list_items(payload)

        self.assertEqual(
            {
                "title": "",
                "genres": ["Rock", {"tags": ["Punk"]}],
            },
            cleaned,
        )

    def test_review_metadata_treats_empty_string_list_items_as_absent(self) -> None:
        previous_data = [{"id": "artist-1", "genres": [""]}]
        current_data = [{"id": "artist-1", "genres": []}]

        metadata = _compute_review_data_change_metadata(previous_data, current_data, "id")

        self.assertEqual([], metadata["changed_paths"])
        self.assertEqual([], metadata["changed_item_keys"])
        self.assertEqual(0, metadata["changed_count"])


if __name__ == "__main__":
    unittest.main()
