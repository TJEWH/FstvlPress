from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.media_responsive import build_asset_responsive_variants  # noqa: E402


class MediaResponsiveTests(unittest.TestCase):
    def test_build_asset_responsive_variants_filters_legacy_small_entries(self) -> None:
        variants = build_asset_responsive_variants(
            {
                "small": {"name": "small", "url": "/media/photo_small.jpg", "width": 480},
                "mobile": {"name": "mobile", "url": "/media/photo_mobile.jpg", "width": 768},
                "tablet": {"name": "tablet", "url": "/media/photo_tablet.jpg", "width": 1024},
                "legacy": {"name": "legacy", "url": "/media/photo_small.png?cache=1", "width": 480},
            }
        )

        self.assertEqual(
            [
                ("mobile", "/media/photo_mobile.jpg", 768),
                ("tablet", "/media/photo_tablet.jpg", 1024),
            ],
            [(entry.get("name"), entry.get("url"), entry.get("width")) for entry in variants],
        )


if __name__ == "__main__":
    unittest.main()
