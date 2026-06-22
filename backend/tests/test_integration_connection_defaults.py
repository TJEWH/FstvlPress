from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routers.v1.integrations import (  # noqa: E402
    _normalize_template_integration_rules,
    _resolve_template_rule,
)


class IntegrationConnectionDefaultTests(unittest.TestCase):
    def test_missing_rules_default_template_only_for_regular_templates(self) -> None:
        rule = _resolve_template_rule({}, "section/faq/default")

        self.assertEqual("template_only", rule["integration_visibility"])
        self.assertTrue(rule["integrations_enabled"])
        self.assertEqual("auto", rule["expected_return_type"])

    def test_missing_rules_default_disabled_for_named_section_types(self) -> None:
        for section_type in ("text", "text_image", "video", "blog", "markdown", "html"):
            with self.subTest(section_type=section_type):
                rule = _resolve_template_rule({}, f"section/{section_type}/default")

                self.assertEqual("disabled", rule["integration_visibility"])
                self.assertFalse(rule["integrations_enabled"])
                self.assertEqual("auto", rule["expected_return_type"])

    def test_missing_program_rule_stays_template_only(self) -> None:
        rule = _resolve_template_rule({}, "section/program/default")

        self.assertEqual("template_only", rule["integration_visibility"])
        self.assertTrue(rule["integrations_enabled"])

    def test_rule_without_visibility_uses_template_default(self) -> None:
        rules = _normalize_template_integration_rules(
            {
                "section/faq/default": {
                    "expected_return_type": "list",
                },
            },
        )

        rule = rules["section/faq/default"]
        self.assertEqual("template_only", rule["integration_visibility"])
        self.assertTrue(rule["integrations_enabled"])
        self.assertEqual("list", rule["expected_return_type"])

    def test_explicit_rule_overrides_default_disabled_section(self) -> None:
        rule = _resolve_template_rule(
            {
                "section/text/default": {
                    "integration_visibility": "enabled",
                    "expected_return_type": "object",
                },
            },
            "section/text/default",
        )

        self.assertEqual("enabled", rule["integration_visibility"])
        self.assertTrue(rule["integrations_enabled"])
        self.assertEqual("object", rule["expected_return_type"])


if __name__ == "__main__":
    unittest.main()
