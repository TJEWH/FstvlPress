from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.media_variant_migration import (  # noqa: E402
    migrate_asset_document,
    migrate_content_media_fields,
    migrate_media_config_document,
)


class MediaVariantMigrationTests(unittest.TestCase):
    def test_asset_migration_removes_duplicate_thumb(self) -> None:
        doc = {
            "_id": "asset-1",
            "url_thumb": "/media/thumb.jpg",
            "key_thumb": "media/thumb.jpg",
            "variants": {
                "thumb": {
                    "name": "thumb",
                    "url": "/media/thumb.jpg",
                    "key": "media/thumb.jpg",
                    "width": 150,
                }
            },
        }

        migrated, changed = migrate_asset_document(doc)

        self.assertTrue(changed)
        self.assertNotIn("url_thumb", migrated)
        self.assertNotIn("key_thumb", migrated)
        self.assertEqual(["thumb"], list(migrated["variants"].keys()))

    def test_asset_migration_folds_unique_thumb(self) -> None:
        doc = {
            "_id": "asset-1",
            "url_thumb": "/media/thumb.jpg",
            "key_thumb": "media/thumb.jpg",
            "variants": {},
        }

        migrated, changed = migrate_asset_document(doc)

        self.assertTrue(changed)
        self.assertEqual(migrated["variants"]["thumb"]["url"], "/media/thumb.jpg")
        self.assertEqual(migrated["variants"]["thumb"]["key"], "media/thumb.jpg")
        self.assertEqual(migrated["variants"]["thumb"]["width"], 150)

    def test_asset_migration_folds_half_without_duplicate(self) -> None:
        doc = {
            "_id": "asset-1",
            "url_half": "/media/tablet.jpg",
            "key_half": "media/tablet.jpg",
            "variants": {
                "tablet": {
                    "name": "tablet",
                    "url": "/media/tablet.jpg",
                    "key": "media/tablet.jpg",
                    "width": 768,
                }
            },
        }

        migrated, changed = migrate_asset_document(doc)

        self.assertTrue(changed)
        self.assertNotIn("url_half", migrated)
        self.assertNotIn("key_half", migrated)
        self.assertEqual(["tablet"], list(migrated["variants"].keys()))

    def test_content_migration_moves_legacy_fields_into_sorted_variants(self) -> None:
        doc = {
            "image_url": "/media/original.jpg",
            "image_url_half": "/media/half.jpg",
            "image_url_thumb": "/media/thumb.jpg",
            "image_responsive_variants": [
                {"name": "desktop", "url": "/media/desktop.jpg", "width": 1440},
                {"name": "thumb", "url": "/media/thumb.jpg", "width": 150},
            ],
        }

        migrated, changed = migrate_content_media_fields(doc)

        self.assertTrue(changed)
        self.assertNotIn("image_url_half", migrated)
        self.assertNotIn("image_url_thumb", migrated)
        self.assertEqual(
            [
                ("thumb", "/media/thumb.jpg", 150),
                ("half", "/media/half.jpg", 1024),
                ("desktop", "/media/desktop.jpg", 1440),
            ],
            [
                (entry.get("name"), entry.get("url"), entry.get("width"))
                for entry in migrated["image_responsive_variants"]
            ],
        )

    def test_media_config_migration_moves_thumb_width_to_fixed_variant(self) -> None:
        doc = {
            "upload_variants": {
                "small": {"enabled": True, "width": 480},
                "mobile": {"enabled": True, "width": 375},
                "tablet": {"enabled": True, "width": 768},
                "desktop": {"enabled": True, "width": 1120},
                "custom": [
                    {"id": "thumb", "label": "Thumbnail", "enabled": True, "width": 120},
                    {"id": "small", "label": "Small", "enabled": True, "width": 480},
                    {"id": "square", "label": "Square", "enabled": True, "width": 640},
                ],
                "thumb_width": 180,
                "max_original_width": 2000,
            }
        }

        migrated, changed = migrate_media_config_document(doc)

        self.assertTrue(changed)
        self.assertNotIn("thumb_width", migrated["upload_variants"])
        self.assertNotIn("small", migrated["upload_variants"])
        self.assertEqual({"enabled": True, "width": 180}, migrated["upload_variants"]["thumb"])
        self.assertEqual(
            [{"id": "square", "label": "Square", "enabled": True, "width": 640}],
            migrated["upload_variants"]["custom"],
        )


if __name__ == "__main__":
    unittest.main()
