"""Models for shared blog items and config."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, ConfigDict

from app.models.sections.common import BilingualText


class BlogItem(BaseModel):
    """A shared blog item (used across all blog sections)."""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    image_url: str = ""
    image_responsive_variants: list[dict[str, Any]] = Field(default_factory=list)
    image_author: str = ""
    image_zoom: float = Field(default=1.0, ge=1.0, le=4.0)
    image_focal_x: float = Field(default=50.0, ge=0.0, le=100.0)
    image_focal_y: float = Field(default=50.0, ge=0.0, le=100.0)
    image_rotation: float = Field(default=0.0, ge=-180.0, le=180.0)
    date: str = ""  # ISO date (YYYY-MM-DD)
    tag: BilingualText = Field(default_factory=BilingualText)  # Topic/scope
    title: BilingualText = Field(default_factory=BilingualText)
    text: BilingualText = Field(default_factory=BilingualText)
    page_slug: str = ""  # Optional detail page slug generated from this blog item
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BlogConfig(BaseModel):
    """Global blog config (tags list for picker)."""

    tags: list[BilingualText] = Field(default_factory=list)
