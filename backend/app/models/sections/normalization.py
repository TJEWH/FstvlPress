from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.models.sections.common import BilingualText


RICH_TEXT_SECTION_TYPES = frozenset({"text", "text_image"})


def normalize_rich_text_value(value: Any) -> dict[str, str]:
    """Normalize plain or bilingual rich text payloads to {de, en}."""
    return BilingualText.model_validate(value).model_dump()


def normalize_section_description_payload(section_type: str, type_data: Any) -> Any:
    """Normalize text section body/description payload to a consistent shape."""
    if section_type not in RICH_TEXT_SECTION_TYPES:
        return type_data
    if not isinstance(type_data, dict):
        return type_data

    normalized = deepcopy(type_data)

    if "body" not in normalized and "description" in normalized:
        normalized["body"] = normalized.get("description")

    if "body" in normalized:
        normalized["body"] = normalize_rich_text_value(normalized.get("body"))

    # Keep storage consistent on `body` only.
    normalized.pop("description", None)
    return normalized
