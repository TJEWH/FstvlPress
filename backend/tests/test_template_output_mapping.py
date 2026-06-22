from __future__ import annotations

import asyncio
from copy import deepcopy
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from bson import ObjectId  # noqa: E402

from app.collection_names import (  # noqa: E402
    TEMPLATE_PAGES_COLLECTION,
    TEMPLATE_SECTIONS_COLLECTION,
)
from app.routers.v1 import admin_templates  # noqa: E402
from app.template_sync import (  # noqa: E402
    SECTION_TEMPLATE_SYNC_FIELDS,
    build_builder_section_id,
    normalize_embedded_section,
    normalize_page_template_doc,
    normalize_page_integration_mapping,
    normalize_section_template_doc,
    page_template_path_as_item_route,
    page_template_path_matches_item_effective_route,
    resolve_section_template_sync_context,
)


class FakeCollection:
    def __init__(self, docs: list[dict]):
        self.docs = docs

    def _matches(self, doc: dict, query: dict) -> bool:
        return all(doc.get(key) == value for key, value in query.items())

    async def find_one(self, query: dict, *_args, **_kwargs) -> dict | None:
        for doc in self.docs:
            if self._matches(doc, query):
                return doc
        return None

    async def update_one(self, query: dict, update: dict, *_args, **_kwargs):
        for doc in self.docs:
            if not self._matches(doc, query):
                continue
            for key, value in update.get("$set", {}).items():
                doc[key] = deepcopy(value)
            return type("FakeResult", (), {"modified_count": 1})()
        return type("FakeResult", (), {"modified_count": 0})()


class FakeDb:
    def __init__(
        self,
        sections: list[dict],
        *,
        pages: list[dict] | None = None,
    ):
        self.collections = {
            TEMPLATE_SECTIONS_COLLECTION: FakeCollection(sections),
            TEMPLATE_PAGES_COLLECTION: FakeCollection(pages or []),
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


class FakeUser:
    def has_permission(self, _permission: str) -> bool:
        return True


class TemplateOutputMappingTests(unittest.TestCase):
    def test_section_output_mapping_defaults_when_absent(self) -> None:
        normalized = normalize_section_template_doc(
            "text",
            "default",
            {
                "title": {"de": "Titel", "en": "Title"},
                "type_data": {"body": {"de": "Text", "en": "Copy"}},
            },
        )

        self.assertEqual(
            {"mode": "default", "exposed_target_paths": []},
            normalized["section_output_mapping"],
        )

    def test_section_output_mapping_preserves_empty_custom_exposed_list(self) -> None:
        normalized = normalize_section_template_doc(
            "text",
            "default",
            {
                "section_output_mapping": {
                    "mode": "custom",
                    "exposed_target_paths": [],
                },
            },
        )

        self.assertEqual(
            {"mode": "custom", "exposed_target_paths": []},
            normalized["section_output_mapping"],
        )

    def test_section_output_mapping_preserves_unique_exposed_paths(self) -> None:
        normalized = normalize_section_template_doc(
            "text",
            "default",
            {
                "sectionOutputMapping": {
                    "mode": "custom",
                    "exposedTargetPaths": [
                        "title.de",
                        "",
                        "title.de",
                        "type_data.body.en",
                    ],
                },
            },
        )

        self.assertEqual(
            {
                "mode": "custom",
                "exposed_target_paths": ["title.de", "type_data.body.en"],
            },
            normalized["section_output_mapping"],
        )

    def test_page_mapping_preserves_only_page_and_header_hidden_targets(self) -> None:
        normalized = normalize_page_integration_mapping(
            {
                "active_mode": "list",
                "hidden_list_target_paths_by_collection_path": {
                    "page": ["slug"],
                    "header": ["background_zoom"],
                    "sections[hero]": ["title.de"],
                    "sections[0]": ["type_data.body.en"],
                },
            }
        )

        self.assertEqual(
            {
                "page": ["slug"],
                "header": ["background_zoom"],
            },
            normalized["hidden_list_target_paths_by_collection_path"],
        )

    def test_page_mapping_preserves_shared_item_source_paths(self) -> None:
        normalized = normalize_page_integration_mapping(
            {
                "active_mode": "list",
                "source_provider": "shared_items",
                "selected_integration_id": "stale-integration",
                "list_mappings_by_collection_path": {
                    "page": [
                        {"source_path": "item.title.de", "target_path": "title.de"},
                        {"source_path": "text.en", "target_path": "title.en"},
                    ],
                },
            }
        )

        self.assertEqual("shared_items", normalized["source_provider"])
        self.assertIsNone(normalized["selected_integration_id"])
        self.assertEqual(
            [
                {"source_path": "item.title.de", "target_path": "title.de"},
                {"source_path": "item.text.en", "target_path": "title.en"},
            ],
            normalized["list_mappings_by_collection_path"]["page"],
        )

    def test_blog_item_page_mapping_infers_shared_items_provider(self) -> None:
        normalized = normalize_page_template_doc(
            "blog/detail",
            {
                "template_kind": "item_page",
                "source_type": "blog",
                "source_kind": "item",
                "page_integration_mapping": {
                    "active_mode": "list",
                    "list_mappings_by_collection_path": {
                        "page": [
                            {"source_path": "item.title.de", "target_path": "title.de"},
                        ],
                    },
                },
            },
        )

        page_mapping = normalized["page_integration_mapping"]
        self.assertEqual("shared_items", page_mapping["source_provider"])
        self.assertEqual(
            "item.title.de",
            page_mapping["list_mappings_by_collection_path"]["page"][0]["source_path"],
        )

    def test_parent_page_path_without_source_defaults_to_blog_item_template(self) -> None:
        normalized = normalize_page_template_doc("program/artists", None)

        self.assertEqual("artists", normalized["template_name"])
        self.assertEqual("/program", normalized["parent_route"])
        self.assertEqual("blog", normalized["source_type"])
        self.assertEqual("item", normalized["source_kind"])

    def test_page_template_path_as_item_route_ignores_static_template_names(self) -> None:
        self.assertIsNone(page_template_path_as_item_route("artists"))
        self.assertEqual(
            "/program/artists",
            page_template_path_as_item_route("program/artists"),
        )

    def test_page_template_path_matches_item_effective_route_for_blog_stage_and_gig(self) -> None:
        cases = [
            ("blog", "item", "/blog", "/posts", "blog/posts", "blog/default"),
            ("program", "stage", "/program", "/stages", "program/stages", "program/default"),
            ("program", "gig", "/program", "/artists", "program/artists", "program/default"),
        ]

        for source_type, source_kind, parent_route, subroute, route_path, template_path in cases:
            with self.subTest(source_type=source_type, source_kind=source_kind):
                template_doc = {
                    "template_name": "default",
                    "parent_route": parent_route,
                    "source_type": source_type,
                    "source_kind": source_kind,
                    "item_page_subroute": subroute,
                }

                self.assertTrue(
                    page_template_path_matches_item_effective_route(route_path, template_doc)
                )
                self.assertFalse(
                    page_template_path_matches_item_effective_route(template_path, template_doc)
                )

    def test_embedded_page_template_section_detects_source_template_changes(self) -> None:
        template_doc = normalize_section_template_doc(
            "text",
            "default",
            {
                "title_placeholder": "Template title",
                "title": {"de": "Vorlage", "en": "Template"},
                "type_data": {"body": {"de": "Neu", "en": "New"}},
                "section_integration_mapping": {
                    "active_mode": "object",
                    "selected_integration_id": "template-source",
                    "scalar_mappings": [
                        {"source_path": "headline", "target_path": "title.de"},
                    ],
                },
                "design_overrides": {"section": {"padding": 24}},
            },
        )
        embedded_section = normalize_embedded_section(
            {
                "section_type": "text",
                "section_template_name": "default",
                "title_placeholder": "Old title",
                "title": {"de": "Alt", "en": "Old"},
                "type_data": {"body": {"de": "Alt", "en": "Old"}},
                "section_integration_mapping": {
                    "active_mode": "object",
                    "selected_integration_id": "local-source",
                    "scalar_mappings": [
                        {"source_path": "name", "target_path": "title.de"},
                    ],
                },
                "design_overrides": {"section": {"padding": 12}},
            }
        )

        result = asyncio.run(
            resolve_section_template_sync_context(
                FakeDb([template_doc]),
                embedded_section,
            )
        )

        self.assertEqual("text", result[0])
        self.assertEqual("default", result[1])
        self.assertEqual(list(SECTION_TEMPLATE_SYNC_FIELDS), result[4])

    def test_embedded_page_template_section_reports_no_changes_when_synced(self) -> None:
        payload = {
            "title_placeholder": "Template title",
            "title": {"de": "Vorlage", "en": "Template"},
            "type_data": {"body": {"de": "Text", "en": "Copy"}},
            "section_integration_mapping": {
                "active_mode": "object",
                "selected_integration_id": "template-source",
                "scalar_mappings": [
                    {"source_path": "headline", "target_path": "title.de"},
                ],
            },
            "design_overrides": {"section": {"padding": 24}},
        }
        template_doc = normalize_section_template_doc("text", "default", payload)
        embedded_section = normalize_embedded_section(
            {
                **payload,
                "section_type": "text",
                "section_template_name": "default",
            }
        )

        result = asyncio.run(
            resolve_section_template_sync_context(
                FakeDb([template_doc]),
                embedded_section,
            )
        )

        self.assertEqual([], result[4])

    def test_page_template_embedded_section_sync_updates_template_section_copy(self) -> None:
        page_id = ObjectId()
        embedded_id = "hero"
        template_doc = normalize_section_template_doc(
            "text",
            "default",
            {
                "title_placeholder": "Template title",
                "title": {"de": "Vorlage", "en": "Template"},
                "type_data": {"body": {"de": "Neu", "en": "New"}},
            },
        )
        embedded_section = normalize_embedded_section(
            {
                "id": embedded_id,
                "section_type": "text",
                "section_template_name": "default",
                "title_placeholder": "Old title",
                "title": {"de": "Alt", "en": "Old"},
                "type_data": {"body": {"de": "Alt", "en": "Old"}},
                "order": 3,
                "visible": False,
                "width_n": 1,
                "width_d": 2,
            }
        )
        page_doc = {
            "_id": page_id,
            "sections": [embedded_section],
            "section_structure": [{"type": "section", "section_id": embedded_id}],
        }
        db = FakeDb([template_doc], pages=[page_doc])
        section_id = build_builder_section_id("page", str(page_id), embedded_id)

        async def noop_sync(*_args, **_kwargs):
            return None

        async def run_sync():
            original_db = admin_templates._db
            original_sync = admin_templates._sync_init_generated_pages_for_template_doc_scoped
            admin_templates._db = lambda: db
            admin_templates._sync_init_generated_pages_for_template_doc_scoped = noop_sync
            try:
                return await admin_templates.sync_builder_section_from_template(
                    "page",
                    section_id,
                    user=FakeUser(),
                )
            finally:
                admin_templates._db = original_db
                admin_templates._sync_init_generated_pages_for_template_doc_scoped = original_sync

        result = asyncio.run(run_sync())

        synced_section = page_doc["sections"][0]
        self.assertTrue(result["updated"])
        self.assertEqual(
            ["title_placeholder", "title", "type_data"],
            result["changed_fields"],
        )
        self.assertEqual("Template title", synced_section["title_placeholder"])
        self.assertEqual({"de": "Vorlage", "en": "Template"}, synced_section["title"])
        self.assertEqual({"body": {"de": "Neu", "en": "New"}}, synced_section["type_data"])
        self.assertEqual(0, synced_section["order"])
        self.assertFalse(synced_section["visible"])
        self.assertEqual(1, synced_section["width_n"])
        self.assertEqual(2, synced_section["width_d"])


if __name__ == "__main__":
    unittest.main()
