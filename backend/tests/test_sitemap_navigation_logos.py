from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.collection_names import DESIGN_CONFIG_COLLECTION, SITEMAP_CONFIG_COLLECTION  # noqa: E402
from app.sitemap import (  # noqa: E402
    get_navigation_links_config,
    normalize_footer_logo_url,
    normalize_topbar_logo_url,
)


class FakeCollection:
    def __init__(self, doc: dict | None = None) -> None:
        self.doc = doc

    async def find_one(self, *_args, **_kwargs) -> dict | None:
        return dict(self.doc) if isinstance(self.doc, dict) else None

    def find(self, *_args, **_kwargs):
        return FakeCursor([])


class FakeCursor:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def __aiter__(self):
        return self._iter_docs()

    async def _iter_docs(self):
        for doc in self.docs:
            yield doc


class FakeDb:
    def __init__(self, *, sitemap_doc: dict | None = None, design_doc: dict | None = None) -> None:
        self.collections = {
            SITEMAP_CONFIG_COLLECTION: FakeCollection(sitemap_doc),
            DESIGN_CONFIG_COLLECTION: FakeCollection(design_doc),
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections.get(name, FakeCollection())


class SitemapNavigationLogoTests(unittest.TestCase):
    def test_logo_url_normalizers_accept_root_relative_and_https(self) -> None:
        for normalizer in (normalize_topbar_logo_url, normalize_footer_logo_url):
            self.assertEqual("/media/logo.png", normalizer("/media/logo.png"))
            self.assertEqual("https://example.com/logo.webp", normalizer("https://example.com/logo.webp"))
            self.assertIsNone(normalizer(""))
            self.assertIsNone(normalizer(None))

    def test_logo_url_normalizers_reject_whitespace_and_relative_paths(self) -> None:
        for normalizer in (normalize_topbar_logo_url, normalize_footer_logo_url):
            with self.assertRaisesRegex(ValueError, "cannot contain whitespace"):
                normalizer("/media/logo file.png")
            with self.assertRaisesRegex(ValueError, "root-relative path"):
                normalizer("media/logo.png")

    def test_navigation_config_falls_back_to_legacy_design_topbar_logo_when_absent(self) -> None:
        payload = asyncio.run(
            get_navigation_links_config(
                FakeDb(
                    sitemap_doc={"nav_external_links": [], "footer_external_links": []},
                    design_doc={"topbar_logo_url": "/media/legacy-topbar.png"},
                )
            )
        )

        self.assertEqual("/media/legacy-topbar.png", payload["topbar_logo_url"])

    def test_navigation_config_explicit_null_topbar_logo_does_not_use_legacy_fallback(self) -> None:
        payload = asyncio.run(
            get_navigation_links_config(
                FakeDb(
                    sitemap_doc={
                        "nav_external_links": [],
                        "footer_external_links": [],
                        "topbar_logo_url": None,
                    },
                    design_doc={"topbar_logo_url": "/media/legacy-topbar.png"},
                )
            )
        )

        self.assertIsNone(payload["topbar_logo_url"])

    def test_navigation_config_enriches_topbar_and_footer_logo_variants(self) -> None:
        async def fake_fetch_asset_docs_by_urls(_db, image_urls):
            self.assertEqual(
                {"/media/footer.png", "/media/topbar.png"},
                set(image_urls),
            )
            return {
                "/media/topbar.png": {
                    "url": "/media/topbar.png",
                    "variants": {
                        "desktop": {
                            "name": "desktop",
                            "url": "/media/topbar-desktop.webp",
                            "width": 1280,
                        },
                    },
                },
                "/media/footer.png": {
                    "url": "/media/footer.png",
                    "variants": {
                        "desktop": {
                            "name": "desktop",
                            "url": "/media/footer-desktop.webp",
                            "width": 1280,
                        },
                    },
                },
            }

        with patch("app.sitemap.fetch_asset_docs_by_urls", new=fake_fetch_asset_docs_by_urls):
            payload = asyncio.run(
                get_navigation_links_config(
                    FakeDb(
                        sitemap_doc={
                            "nav_external_links": [],
                            "footer_external_links": [],
                            "topbar_logo_url": "/media/topbar.png",
                            "footer_logo_url": "/media/footer.png",
                        },
                    )
                )
            )

        self.assertEqual(
            "/media/topbar-desktop.webp",
            payload["topbar_logo_responsive_variants"][0]["url"],
        )
        self.assertEqual(
            "/media/footer-desktop.webp",
            payload["footer_logo_responsive_variants"][0]["url"],
        )


if __name__ == "__main__":
    unittest.main()
