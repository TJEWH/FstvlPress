from __future__ import annotations

from typing import Any
import unicodedata


MEDIA_TAG_SEPARATOR = "::"


def media_tag_text_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("de") or value.get("en") or "").strip()
    if isinstance(value, (str, int, float, bool)):
        return str(value).strip()
    return ""


def normalize_media_tag_part(value: Any) -> str:
    raw = unicodedata.normalize("NFC", media_tag_text_value(value)).strip().lower()
    if not raw:
        return ""

    parts: list[str] = []
    previous_was_separator = False
    for char in raw:
        if char.isalnum():
            parts.append(char)
            previous_was_separator = False
        elif not previous_was_separator:
            parts.append("-")
            previous_was_separator = True
    return "".join(parts).strip("-")


def build_media_tag(prefix_value: Any, item_value: Any) -> str:
    prefix = normalize_media_tag_part(prefix_value)
    value = normalize_media_tag_part(item_value)
    if not prefix or not value:
        return ""
    return f"{prefix}{MEDIA_TAG_SEPARATOR}{value}"
