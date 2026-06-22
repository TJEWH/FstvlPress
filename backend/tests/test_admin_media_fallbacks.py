from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routers.v1.admin_media import _normalize_config  # noqa: E402


class AdminMediaFallbackTests(unittest.TestCase):
    def test_normalize_config_preserves_single_fallback_image_and_transform(self) -> None:
        normalized = _normalize_config(
            {
                "fallback_images": {
                    "images": [
                        {
                            "id": "hero",
                            "image_url": "/assets/hero.jpg",
                            "image_responsive_variants": [
                                {"name": "small", "url": "/assets/hero_small.jpg", "width": 320},
                                {"name": "mobile", "url": "/assets/hero_mobile.jpg", "width": 768},
                            ],
                        },
                        {"id": "dupe", "image_url": "/assets/hero.jpg"},
                        {"id": "second", "url": "/assets/second.jpg"},
                    ],
                    "mediaTag": "fallback::global",
                    "image_url": "/assets/hero.jpg",
                    "image_zoom": 1.75,
                    "image_focal_x": 0,
                    "image_focal_y": 100,
                    "image_rotation": -15,
                }
            },
            strict_custom_tags=False,
        )["fallback_images"]

        self.assertEqual("", normalized["media_tag"])
        self.assertEqual("/assets/hero.jpg", normalized["image_url"])
        self.assertEqual(1.75, normalized["image_zoom"])
        self.assertEqual(0, normalized["image_focal_x"])
        self.assertEqual(100, normalized["image_focal_y"])
        self.assertEqual(-15, normalized["image_rotation"])
        self.assertEqual(
            ["/assets/hero.jpg"],
            [entry["image_url"] for entry in normalized["images"]],
        )
        self.assertEqual(
            [{"name": "mobile", "url": "/assets/hero_mobile.jpg", "width": 768}],
            normalized["images"][0]["responsive_variants"],
        )

    def test_normalize_config_promotes_first_legacy_image_to_single_fallback(self) -> None:
        normalized = _normalize_config(
            {
                "fallback_images": {
                    "images": [
                        {"id": "first", "image_url": "/assets/first.jpg"},
                        {"id": "second", "image_url": "/assets/second.jpg"},
                    ],
                }
            },
            strict_custom_tags=False,
        )["fallback_images"]

        self.assertEqual("/assets/first.jpg", normalized["image_url"])
        self.assertEqual(
            ["/assets/first.jpg"],
            [entry["image_url"] for entry in normalized["images"]],
        )


if __name__ == "__main__":
    unittest.main()
