from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.cms import DesignSettingsBase  # noqa: E402
from app.routers.v1 import admin_design  # noqa: E402


class NavigationMenuDesignSettingTests(unittest.TestCase):
    def test_design_settings_default_to_sidebar_menu(self) -> None:
        self.assertEqual("sidebar", DesignSettingsBase().navigation_menu_view)

    def test_design_settings_default_admin_accent(self) -> None:
        self.assertEqual("#cb00e6", DesignSettingsBase().admin_accent_color)

    def test_admin_design_config_exposes_navigation_menu_view(self) -> None:
        config = admin_design._get_default_config()
        layout_order = config["paramOrder"]["layout"]
        param_config = config["parameters"]["navigationMenuView"]

        self.assertIn("navigationMenuView", layout_order)
        self.assertEqual("layout", param_config["section"])
        self.assertEqual("dropdown", param_config["type"])
        self.assertEqual(["sidebar", "below_topbar"], param_config["enabledOptions"])

    def test_admin_design_config_defaults_to_requested_panel_order(self) -> None:
        config = admin_design._get_default_config()
        self.assertEqual(
            ["header", "layout", "sections", "colors", "buttons", "fonts", "versions", "customCss"],
            config["sectionOrder"],
        )

        sections_order = config["paramOrder"]["sections"]
        self.assertLess(sections_order.index("sectionBorderWidth"), sections_order.index("hardBoxShadowEnabled"))
        self.assertLess(sections_order.index("hardBoxShadowEnabled"), sections_order.index("sectionBgPattern"))

        colors_order = config["paramOrder"]["colors"]
        self.assertLess(colors_order.index("topbarBgColor"), colors_order.index("heroTitleColor"))
        self.assertLess(colors_order.index("heroTitleColor"), colors_order.index("backgroundColor"))
        self.assertLess(colors_order.index("backgroundColor"), colors_order.index("sidebarBgColor"))

        fonts_order = config["paramOrder"]["fonts"]
        self.assertLess(fonts_order.index("heroTitleFontSize"), fonts_order.index("heroSubtitleFontSize"))
        self.assertLess(fonts_order.index("heroSubtitleFontSize"), fonts_order.index("bodyFontFamily"))
        self.assertLess(fonts_order.index("bodyFontFamily"), fonts_order.index("linkTextDecoration"))
        self.assertLess(fonts_order.index("linkTextDecoration"), fonts_order.index("headerFontFamily"))
        self.assertLess(fonts_order.index("headerFontFamily"), fonts_order.index("h1FontSize"))

        params = config["parameters"]
        self.assertEqual("#cb00e6", params["adminAccentColor"]["default"])
        self.assertEqual("Header Titles", params["heroTitleColor"]["subsection"])
        self.assertEqual("Menus", params["sidebarBgColor"]["subsection"])
        self.assertEqual("Paragraph", params["bodyFontFamily"]["subsection"])
        self.assertEqual("Headings", params["headerFontFamily"]["subsection"])
        self.assertEqual("Hardbox Shadow", params["hardBoxShadowEnabled"]["subsection"])

    def test_admin_design_config_migrates_legacy_panel_grouping(self) -> None:
        legacy = deepcopy(admin_design._get_default_config())
        legacy["sectionOrder"] = ["layout", "fonts", "colors", "sections", "buttons", "header", "customCss", "versions"]
        legacy["paramOrder"]["sections"] = [
            "sectionBorderRadius", "sectionPadding", "sectionContentAlign", "sectionBoxShadow",
            "sectionBgPattern", "sectionBgOpacity1", "sectionBgOpacity2", "sectionBgColor1", "sectionBgColor2",
            "sectionBorderWidth", "sectionBorderColor", "sectionBorderStyle",
            "hardBoxShadowEnabled", "hardBoxShadowOffsetSource", "hardBoxShadowOffsetCustom", "hardBoxShadowBrightness",
        ]
        legacy["parameters"]["bodyFontFamily"]["subsection"] = "Typography"
        legacy["parameters"]["heroTitleColor"]["subsection"] = "text header"
        legacy["parameters"]["sidebarBgColor"]["subsection"] = "Sidebar"
        legacy["parameters"]["hardBoxShadowEnabled"]["subsection"] = "Hard Box-Shadow"
        legacy["parameters"]["adminAccentColor"]["default"] = "#4f46e5"

        merged = admin_design._merge_defaults_into_config(legacy)

        self.assertEqual(
            ["header", "layout", "sections", "colors", "buttons", "fonts", "versions", "customCss"],
            merged["sectionOrder"],
        )
        sections_order = merged["paramOrder"]["sections"]
        self.assertLess(sections_order.index("sectionBorderWidth"), sections_order.index("hardBoxShadowEnabled"))
        self.assertLess(sections_order.index("hardBoxShadowEnabled"), sections_order.index("sectionBgPattern"))
        self.assertEqual("Paragraph", merged["parameters"]["bodyFontFamily"]["subsection"])
        self.assertEqual("Header Titles", merged["parameters"]["heroTitleColor"]["subsection"])
        self.assertEqual("Menus", merged["parameters"]["sidebarBgColor"]["subsection"])
        self.assertEqual("Hardbox Shadow", merged["parameters"]["hardBoxShadowEnabled"]["subsection"])
        self.assertEqual("#cb00e6", merged["parameters"]["adminAccentColor"]["default"])


if __name__ == "__main__":
    unittest.main()
