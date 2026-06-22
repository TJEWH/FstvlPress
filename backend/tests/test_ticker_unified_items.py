from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.sections.sections import get_default_type_data, validate_type_data  # noqa: E402
from app.routers.v1.program import _resolve_ticker_payload_from_sections  # noqa: E402
from app.routers.v1.sections import _normalize_section_type_data_for_response  # noqa: E402


class TickerUnifiedItemsTests(unittest.TestCase):
    def test_ticker_model_keeps_timestamp_on_items(self) -> None:
        parsed = validate_type_data(
            "ticker",
            {
                "items": [
                    {
                        "id": "item-1",
                        "timestamp": "2026-06-18T12:30",
                        "text": {"de": "Update", "en": "Update"},
                    }
                ]
            },
        ).model_dump()

        self.assertEqual("2026-06-18T12:30", parsed["items"][0]["timestamp"])

    def test_ticker_defaults_do_not_include_legacy_update_items(self) -> None:
        defaults = get_default_type_data("ticker")

        self.assertIn("items", defaults)
        self.assertNotIn("update_items", defaults)

    def test_updates_mode_prefers_legacy_update_items_and_removes_legacy_key(self) -> None:
        normalized = _normalize_section_type_data_for_response(
            "ticker",
            {
                "view_mode": "updates",
                "items": [
                    {
                        "id": "ticker-item",
                        "timestamp": "",
                        "text": {"de": "Ticker", "en": "Ticker"},
                    }
                ],
                "update_items": [
                    {
                        "id": "update-item",
                        "timestamp": "2026-06-18T14:00",
                        "text": {"de": "Update", "en": "Update"},
                    }
                ],
            },
        )

        self.assertNotIn("update_items", normalized)
        self.assertEqual("update-item", normalized["items"][0]["id"])
        self.assertEqual("2026-06-18T14:00", normalized["items"][0]["timestamp"])

    def test_ticker_mode_keeps_canonical_items_when_legacy_update_items_exist(self) -> None:
        normalized = _normalize_section_type_data_for_response(
            "ticker",
            {
                "view_mode": "ticker",
                "items": [
                    {
                        "id": "ticker-item",
                        "timestamp": "",
                        "text": {"de": "Ticker", "en": "Ticker"},
                    }
                ],
                "update_items": [
                    {
                        "id": "update-item",
                        "timestamp": "2026-06-18T14:00",
                        "text": {"de": "Update", "en": "Update"},
                    }
                ],
            },
        )

        self.assertNotIn("update_items", normalized)
        self.assertEqual("ticker-item", normalized["items"][0]["id"])

    def test_public_feed_reads_canonical_items(self) -> None:
        payload = _resolve_ticker_payload_from_sections(
            [
                {
                    "section_type": "ticker",
                    "type_data": {
                        "view_mode": "updates",
                        "items": [
                            {
                                "id": "canonical",
                                "timestamp": "2026-06-18T15:00",
                                "text": {"de": "Canonical", "en": "Canonical"},
                            }
                        ],
                    },
                }
            ]
        )

        self.assertEqual("canonical", payload["items"][0]["id"])

    def test_public_feed_prefers_legacy_update_items_when_both_raw_lists_exist(self) -> None:
        payload = _resolve_ticker_payload_from_sections(
            [
                {
                    "section_type": "ticker",
                    "type_data": {
                        "view_mode": "updates",
                        "items": [
                            {
                                "id": "canonical",
                                "timestamp": "2026-06-18T15:00",
                                "text": {"de": "Canonical", "en": "Canonical"},
                            }
                        ],
                        "update_items": [
                            {
                                "id": "legacy",
                                "timestamp": "2026-06-18T16:00",
                                "text": {"de": "Legacy", "en": "Legacy"},
                            }
                        ],
                    },
                }
            ]
        )

        self.assertEqual("legacy", payload["items"][0]["id"])


if __name__ == "__main__":
    unittest.main()
