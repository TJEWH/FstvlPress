from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

from bson import ObjectId

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import program_catalog  # noqa: E402
from app.collection_names import PROGRAM_GIGS_COLLECTION, PROGRAM_SHARED_COLLECTION  # noqa: E402
from app.template_sync import preview_item_page_mapping_from_template_state  # noqa: E402


def _get_path(doc: dict, path: str):
    current = doc
    for part in str(path or "").split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _matches_query(doc: dict, query: dict | None) -> bool:
    if not query:
        return True
    for key, expected in query.items():
        if key == "$or":
            return any(_matches_query(doc, nested) for nested in expected if isinstance(nested, dict))
        value = _get_path(doc, key)
        if isinstance(expected, dict) and "$in" in expected:
            if value not in expected["$in"]:
                return False
            continue
        if value != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, docs):
        self.docs = [deepcopy(doc) for doc in docs]

    def sort(self, *_args, **_kwargs):
        return self

    async def to_list(self, length=None):
        return deepcopy(self.docs[:length] if isinstance(length, int) else self.docs)

    def __aiter__(self):
        self._iter_index = 0
        return self

    async def __anext__(self):
        if self._iter_index >= len(self.docs):
            raise StopAsyncIteration
        doc = self.docs[self._iter_index]
        self._iter_index += 1
        return deepcopy(doc)


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = [deepcopy(doc) for doc in (docs or [])]
        self.write_count = 0

    async def find_one(self, query=None, *_args, **_kwargs):
        for doc in self.docs:
            if _matches_query(doc, query or {}):
                return deepcopy(doc)
        return None

    def find(self, query=None, *_args, **_kwargs):
        return FakeCursor([doc for doc in self.docs if _matches_query(doc, query or {})])

    async def update_one(self, *_args, **_kwargs):
        self.write_count += 1
        return None

    async def bulk_write(self, *_args, **_kwargs):
        self.write_count += 1
        return None


class FakeDb(dict):
    def __getitem__(self, name):
        if name not in self:
            self[name] = FakeCollection()
        return dict.__getitem__(self, name)

    @property
    def total_write_count(self):
        return sum(collection.write_count for collection in self.values())


def _integration_fixture(rows, *, output_primary_key_path="external_id"):
    integration_id = ObjectId()
    return str(integration_id), {
        "integration_config": FakeCollection(
            [
                {
                    "_id": integration_id,
                    "output_primary_key_path": output_primary_key_path,
                }
            ]
        ),
        "integration_data": FakeCollection(
            [
                {
                    "integration_id": str(integration_id),
                    "data": rows,
                }
            ]
        ),
        "integration_item_overrides": FakeCollection(),
        "integration_local_items": FakeCollection(),
        "integration_schemas": FakeCollection(),
    }


class ItemPageMappingPreviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_preview_maps_shared_blog_item_without_integration_data(self) -> None:
        blog_item_id = ObjectId()
        db = FakeDb(
            {
                "blog_shared": FakeCollection(
                    [
                        {
                            "_id": blog_item_id,
                            "date": "2026-06-21",
                            "title": {"de": "Geteilter Beitrag", "en": "Shared Post"},
                            "text": {"de": "Deutscher Text", "en": "English body"},
                            "tag": {"de": "News", "en": "News"},
                            "image_url": "/media/blog/shared.jpg",
                        }
                    ]
                )
            }
        )
        template_doc = {
            "_id": ObjectId(),
            "template_name": "detail",
            "parent_route": "/blog",
            "template_kind": "item_page",
            "source_type": "blog",
            "source_kind": "item",
            "title": {"de": "Default Page", "en": "Default Page"},
            "has_header": True,
            "header": {
                "header_type": "hero",
                "hero_title": {"de": "Default Header", "en": "Default Header"},
            },
            "sections": [],
            "section_structure": [],
            "page_integration_mapping": {
                "source_provider": "shared_items",
                "list_mappings_by_collection_path": {
                    "page": [
                        {"source_path": "item.title.de", "target_path": "title.de"}
                    ],
                    "header": [
                        {"source_path": "item.text.en", "target_path": "hero_title.en"}
                    ],
                },
            },
        }

        result = await preview_item_page_mapping_from_template_state(
            db,
            template_doc,
            preview_item_key=str(blog_item_id),
        )

        self.assertEqual("Geteilter Beitrag", result["page"]["title"]["de"])
        self.assertEqual("Default Page", result["page"]["title"]["en"])
        self.assertEqual("English body", result["header"]["hero_title"]["en"])
        self.assertEqual(str(blog_item_id), result["selected_preview_item"]["preview_item_key"])
        warning_codes = {
            warning.get("code")
            for warning in result.get("warnings", [])
            if isinstance(warning, dict)
        }
        self.assertNotIn("integration_missing_reference", warning_codes)
        self.assertEqual(0, db.total_write_count)

    async def test_preview_maps_page_and_header_title_with_current_design(self) -> None:
        integration_id, collections = _integration_fixture(
            [
                {
                    "external_id": "item-1",
                    "page_title": "Mapped Page",
                    "header_title": "Mapped Header",
                }
            ]
        )
        db = FakeDb(collections)
        template_doc = {
            "_id": ObjectId(),
            "template_name": "detail",
            "parent_route": "/items",
            "template_kind": "item_page",
            "source_type": "blog",
            "source_kind": "item",
            "title": {"de": "Default Page", "en": "Default Page"},
            "has_header": True,
            "header": {
                "header_type": "hero",
                "hero_title": {"de": "Default Header", "en": "Default Header"},
            },
            "sections": [],
            "section_structure": [],
            "template_design_current": {"colors": {"primary": "#123456"}},
            "template_design_published": {"colors": {"primary": "#654321"}},
            "page_integration_mapping": {
                "selected_integration_id": integration_id,
                "list_mappings_by_collection_path": {
                    "page": [
                        {"source_path": "integration.page_title", "target_path": "title"}
                    ],
                    "header": [
                        {"source_path": "integration.header_title", "target_path": "hero_title"}
                    ],
                },
            },
        }

        result = await preview_item_page_mapping_from_template_state(
            db,
            template_doc,
            preview_item_key="item-1",
        )

        self.assertEqual({"de": "Mapped Page", "en": "Mapped Page"}, result["page"]["title"])
        self.assertEqual({"de": "Mapped Header", "en": "Mapped Header"}, result["header"]["hero_title"])
        self.assertTrue(result["__mapped_header_title"])
        self.assertEqual({"colors": {"primary": "#123456"}}, result["effective_design_settings"])
        self.assertEqual(0, db.total_write_count)

    async def test_preview_resolves_program_fixed_gig_by_external_id(self) -> None:
        integration_id, collections = _integration_fixture(
            [
                {
                    "external_id": "ext-42",
                    "title": {"de": "Band X", "en": "Band X"},
                }
            ]
        )
        db = FakeDb(
            {
                **collections,
                PROGRAM_SHARED_COLLECTION: FakeCollection(
                    [
                        {
                            "_id": program_catalog.PROGRAM_SHARED_DOC_ID,
                            "program_section_shared_cleanup_version": program_catalog.PROGRAM_SECTION_SHARED_CLEANUP_VERSION,
                            "stages": [],
                            "gig_ids": ["gig-canonical"],
                            "program_gigs_integration_mapping": {
                                "selected_integration_id": integration_id,
                            },
                            "program_gigs_integration_mapping_cache_state": {
                                "integration_output_primary_key_path": "external_id",
                            },
                        }
                    ]
                ),
                PROGRAM_GIGS_COLLECTION: FakeCollection(
                    [
                        {
                            "_id": "gig-canonical",
                            "id": "gig-canonical",
                            "integration_item_key": "ext-42",
                            "external_id": "ext-42",
                            "title": {"de": "Band X", "en": "Band X"},
                            "start": "2026-07-01T20:00",
                            "end": "2026-07-01T21:00",
                        }
                    ]
                ),
            }
        )
        template_doc = _program_fixed_gig_template(integration_id, source_path="integration.external_id")
        expected_gig_id = program_catalog.normalize_program_gig_for_storage(
            {
                "_id": "gig-canonical",
                "id": "gig-canonical",
                "integration_item_key": "ext-42",
                "external_id": "ext-42",
                "title": {"de": "Band X", "en": "Band X"},
                "start": "2026-07-01T20:00",
                "end": "2026-07-01T21:00",
            },
            0,
            primary_key_path="external_id",
            selected_integration_id=integration_id,
        )["id"]

        result = await preview_item_page_mapping_from_template_state(
            db,
            template_doc,
            preview_item_key="ext-42",
        )

        self.assertEqual(expected_gig_id, result["sections"][0]["type_data"]["fixed_gig_id"])
        self.assertEqual(0, db.total_write_count)

    async def test_preview_resolves_program_fixed_gig_by_title_fallback(self) -> None:
        integration_id, collections = _integration_fixture(
            [
                {
                    "external_id": "different-external-id",
                    "title": {"de": "Band X", "en": "Band X"},
                }
            ]
        )
        db = FakeDb(
            {
                **collections,
                PROGRAM_SHARED_COLLECTION: FakeCollection(
                    [
                        {
                            "_id": program_catalog.PROGRAM_SHARED_DOC_ID,
                            "program_section_shared_cleanup_version": program_catalog.PROGRAM_SECTION_SHARED_CLEANUP_VERSION,
                            "stages": [],
                            "gig_ids": ["gig-canonical"],
                            "program_gigs_integration_mapping": {
                                "selected_integration_id": integration_id,
                            },
                            "program_gigs_integration_mapping_cache_state": {
                                "integration_output_primary_key_path": "external_id",
                            },
                        }
                    ]
                ),
                PROGRAM_GIGS_COLLECTION: FakeCollection(
                    [
                        {
                            "_id": "gig-canonical",
                            "id": "gig-canonical",
                            "integration_item_key": "ext-42",
                            "external_id": "ext-42",
                            "title": {"de": "Band X", "en": "Band X"},
                            "start": "2026-07-01T20:00",
                            "end": "2026-07-01T21:00",
                        }
                    ]
                ),
            }
        )
        template_doc = _program_fixed_gig_template(integration_id, source_path="integration.title")
        expected_gig_id = program_catalog.normalize_program_gig_for_storage(
            {
                "_id": "gig-canonical",
                "id": "gig-canonical",
                "integration_item_key": "ext-42",
                "external_id": "ext-42",
                "title": {"de": "Band X", "en": "Band X"},
                "start": "2026-07-01T20:00",
                "end": "2026-07-01T21:00",
            },
            0,
            primary_key_path="external_id",
            selected_integration_id=integration_id,
        )["id"]

        result = await preview_item_page_mapping_from_template_state(
            db,
            template_doc,
            preview_item_key="different-external-id",
        )

        self.assertEqual(expected_gig_id, result["sections"][0]["type_data"]["fixed_gig_id"])
        self.assertEqual(0, db.total_write_count)


def _program_fixed_gig_template(integration_id: str, *, source_path: str) -> dict:
    return {
        "_id": ObjectId(),
        "template_name": "gig-detail",
        "parent_route": "/gigs",
        "template_kind": "item_page",
        "source_type": "program",
        "source_kind": "gig",
        "title": {"de": "Gig", "en": "Gig"},
        "has_header": False,
        "sections": [
            {
                "id": "program-section",
                "section_type": "program",
                "section_template_name": "default",
                "title": {"de": "", "en": ""},
                "type_data": {
                    "view_mode": "fixed_gig",
                    "fixed_gig_id": "",
                    "fixed_day": "2026-07-01",
                },
                "order": 0,
                "visible": True,
                "width_n": 1,
                "width_d": 1,
            }
        ],
        "section_structure": [{"type": "section", "section_id": "program-section"}],
        "page_integration_mapping": {
            "selected_integration_id": integration_id,
            "list_mappings_by_collection_path": {
                "sections[program-section]": [
                    {
                        "source_path": source_path,
                        "target_path": "type_data.fixed_gig_id",
                        "template_section_id": "program-section",
                    }
                ]
            },
        },
    }


if __name__ == "__main__":
    unittest.main()
