from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.sections.sections import (  # noqa: E402
    get_default_title,
    get_default_type_data,
    validate_type_data,
)


class MapSectionTypeTests(unittest.TestCase):
    def test_map_default_type_data(self) -> None:
        defaults = get_default_type_data("map")

        self.assertEqual({"de": "", "en": ""}, defaults["body"])
        self.assertEqual("", defaults["svg_url"])
        self.assertEqual("", defaults["asset_id"])
        self.assertEqual({"de": "", "en": ""}, defaults["alt"])

    def test_map_default_title(self) -> None:
        self.assertEqual({"de": "Karte", "en": "Map"}, get_default_title("map"))

    def test_map_type_data_validation(self) -> None:
        parsed = validate_type_data(
            "map",
            {
                "body": "Festival grounds",
                "svg_url": "/assets/map.svg",
                "asset_id": "asset-123",
                "alt": "Festival map",
            },
        ).model_dump()

        self.assertEqual({"de": "Festival grounds", "en": "Festival grounds"}, parsed["body"])
        self.assertEqual("/assets/map.svg", parsed["svg_url"])
        self.assertEqual("asset-123", parsed["asset_id"])
        self.assertEqual({"de": "Festival map", "en": "Festival map"}, parsed["alt"])


if __name__ == "__main__":
    unittest.main()
