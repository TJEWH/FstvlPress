from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Literal

from app.models.sections.header import HeaderSection
from app.models.sections.sections import (
    BlogSection,
    TextSection,
    LinksSection,
    TickerSection,
    FAQSection,
    VideoSection,
    LayoutSettings,
)

HomepageStatus = Literal["draft", "published"]


class HomepageDraft(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: Literal["v1"] = "v1"
    year: int = Field(ge=2000, le=2100)
    status: HomepageStatus = "draft"
    header: HeaderSection = Field(default_factory=HeaderSection)
    ticker: TickerSection = Field(default_factory=TickerSection)
    blog: BlogSection = Field(default_factory=BlogSection)
    text: TextSection = Field(default_factory=TextSection)
    links: LinksSection = Field(default_factory=LinksSection)
    faq: FAQSection = Field(default_factory=FAQSection)
    video: VideoSection = Field(default_factory=VideoSection)
    layout: LayoutSettings = Field(default_factory=LayoutSettings)
    updated_at: datetime | None = None


class HomepagePublished(BaseModel):
    schema_version: Literal["v1"] = "v1"
    year: int
    published_at: datetime
    etag: str
    homepage: HomepageDraft
