"""
Header Schemas

Defines header-related models for page headers, hero sections, and ticker.
"""

from __future__ import annotations

from pydantic import Field

from app.models.sections.common import SectionBase, ItemBase, Link, BilingualText


class CTAButton(ItemBase):
    """Call-to-action button for headers."""

    text: BilingualText = Field(default_factory=BilingualText)
    link: Link | None = None


class HeaderSection(SectionBase):
    """Hero header section with background, overlay, and CTAs."""

    background_image_url: str | None = None
    overlay_image_url: str | None = None
    subtitle: BilingualText = Field(default_factory=BilingualText)
    ctas: list[CTAButton] = Field(default_factory=list, max_length=3)
