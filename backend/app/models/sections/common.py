from __future__ import annotations

from pydantic import BaseModel, Field, model_validator, ConfigDict
from typing import Literal


SchemaVersion = Literal["v1"]


class BilingualText(BaseModel):
    """Text content in both German and English."""

    model_config = ConfigDict(extra="allow")

    de: str = Field(default="")
    en: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _coerce_value(cls, value):
        # Accept plain string payloads and mirror them to both languages.
        if value is None:
            return {"de": "", "en": ""}
        if isinstance(value, str):
            return {"de": value, "en": value}
        if isinstance(value, dict):
            return {
                "de": str(value.get("de") or ""),
                "en": str(value.get("en") or ""),
            }
        if isinstance(value, (int, float, bool)):
            text = str(value)
            return {"de": text, "en": text}
        return value


class Link(BaseModel):
    url: str = ""  # URL string (can be empty or relative)
    text: BilingualText | None = None
    

class SectionBase(BaseModel):
    schema_version: SchemaVersion = "v1"
    title: BilingualText = Field(default_factory=BilingualText)
    section_generic: dict[str, bool | str | int | float | None] = Field(default_factory=dict)
    hide_section_header: bool = False
    hide_section_description: bool = False
    remove_section_padding: bool = False
    remove_section_background: bool = False


class ItemBase(BaseModel):
    id: str = Field(default="")  # uuid string, default empty for creation
