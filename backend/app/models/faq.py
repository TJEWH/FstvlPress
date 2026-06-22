"""Models for shared FAQ items and config."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.sections.common import BilingualText


class FAQSharedItem(BaseModel):
    """A shared FAQ item (used across all FAQ sections)."""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    question: BilingualText = Field(default_factory=BilingualText)
    answer: BilingualText = Field(default_factory=BilingualText)
    tag: BilingualText = Field(default_factory=BilingualText)
    start_date: str = ""  # Optional YYYY-MM-DD
    end_date: str = ""  # Optional YYYY-MM-DD
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FAQSharedResponse(BaseModel):
    items: list[FAQSharedItem] = Field(default_factory=list)
    tags: list[BilingualText] = Field(default_factory=list)


class FAQSharedUpdate(BaseModel):
    items: list[FAQSharedItem] | None = None
    tags: list[BilingualText] | None = None
