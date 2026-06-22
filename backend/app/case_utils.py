from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from fastapi import HTTPException

_UPPERCASE_RE = re.compile(r"[A-Z]")
_FIELD_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_WORD_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Dicts whose keys are typically identifiers/domain IDs, not schema field names.
DEFAULT_IDENTIFIER_MAP_SUFFIXES = frozenset(
    {
        "program_tile_overrides",
        "program_stages_integration_mapping",
        "program_gigs_integration_mapping",
        "program_stages_integration_mapping_cache_state",
        "program_gigs_integration_mapping_cache_state",
        "page_overrides",
        "design_overrides",
        "button_type_styles",
        "responsive_values",
        "selected_units",
        "color_variations",
        "color_links",
        "base_color_high_contrast",
        "parameters",
        "param_order",
        "by_type",
    }
)


def camel_to_snake(value: str) -> str:
    text = str(value or "")
    if not text:
        return text
    # Keep acronyms stable (e.g. URLValue -> url_value)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return text.replace("-", "_").lower()


def snake_to_camel(value: str) -> str:
    text = str(value or "")
    if "_" not in text:
        return text
    head, *tail = text.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail if part)


def _is_field_key(value: str) -> bool:
    return bool(_FIELD_KEY_RE.fullmatch(value))


def _is_identifier_map_path(path: str, suffixes: set[str] | frozenset[str]) -> bool:
    if not path:
        return False
    for suffix in suffixes:
        if (
            path == suffix
            or path.startswith(f"{suffix}.")
            or path.endswith(f".{suffix}")
            or f".{suffix}." in path
        ):
            return True
    return False


def _join_path(path: str, token: str) -> str:
    if not path:
        return token
    return f"{path}.{token}"


def list_camelcase_key_paths(
    value: Any,
    *,
    root_path: str = "",
    identifier_map_suffixes: set[str] | frozenset[str] = DEFAULT_IDENTIFIER_MAP_SUFFIXES,
) -> list[str]:
    violations: list[str] = []

    def visit(node: Any, path: str) -> None:
        if isinstance(node, dict):
            preserve_keys = _is_identifier_map_path(path, identifier_map_suffixes)
            for raw_key, child in node.items():
                key = str(raw_key)
                key_path = _join_path(path, key)
                if (
                    not preserve_keys
                    and _is_field_key(key)
                    and _UPPERCASE_RE.search(key)
                ):
                    violations.append(key_path)
                visit(child, key_path)
            return

        if isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, f"{path}[{index}]")

    visit(value, root_path)
    return violations


def ensure_snake_case_keys(
    value: Any,
    *,
    root_label: str,
    identifier_map_suffixes: set[str] | frozenset[str] = DEFAULT_IDENTIFIER_MAP_SUFFIXES,
    max_paths_in_error: int = 20,
) -> None:
    violations = list_camelcase_key_paths(
        value,
        root_path=root_label,
        identifier_map_suffixes=identifier_map_suffixes,
    )
    if not violations:
        return

    shown = violations[:max_paths_in_error]
    suffix = "" if len(violations) <= max_paths_in_error else f" (+{len(violations) - max_paths_in_error} more)"
    raise HTTPException(
        status_code=422,
        detail=(
            "Payload keys must use snake_case. Offending key paths: "
            + ", ".join(shown)
            + suffix
        ),
    )


def normalize_mapping_path_to_snake(path_value: str) -> str:
    raw = str(path_value or "").strip()
    if not raw:
        return ""

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if _is_field_key(token) and _UPPERCASE_RE.search(token):
            return camel_to_snake(token)
        return token

    return _WORD_TOKEN_RE.sub(_replace, raw)


@dataclass
class KeyNormalizationStats:
    keys_renamed: int = 0
    path_values_rewritten: int = 0
    samples: list[dict[str, str]] | None = None

    def add_sample(self, sample: dict[str, str], *, sample_limit: int) -> None:
        if self.samples is None:
            self.samples = []
        if len(self.samples) < sample_limit:
            self.samples.append(sample)


def normalize_keys_to_snake(
    value: Any,
    *,
    identifier_map_suffixes: set[str] | frozenset[str] = DEFAULT_IDENTIFIER_MAP_SUFFIXES,
    sample_limit: int = 50,
) -> tuple[Any, KeyNormalizationStats]:
    stats = KeyNormalizationStats(samples=[])

    def visit(node: Any, path: str) -> Any:
        if isinstance(node, dict):
            preserve_keys = _is_identifier_map_path(path, identifier_map_suffixes)
            result: dict[str, Any] = {}
            for raw_key, child in node.items():
                key = str(raw_key)
                next_key = key
                if (
                    not preserve_keys
                    and _is_field_key(key)
                    and _UPPERCASE_RE.search(key)
                ):
                    converted = camel_to_snake(key)
                    if converted != key:
                        next_key = converted
                        stats.keys_renamed += 1
                        stats.add_sample(
                            {
                                "kind": "key",
                                "path": _join_path(path, key),
                                "normalized_path": _join_path(path, next_key),
                            },
                            sample_limit=sample_limit,
                        )

                child_path = _join_path(path, next_key)
                next_child = visit(child, child_path)
                if (
                    next_key in {"source_path", "target_path"}
                    and isinstance(next_child, str)
                ):
                    normalized_path_value = normalize_mapping_path_to_snake(next_child)
                    if normalized_path_value != next_child:
                        stats.path_values_rewritten += 1
                        stats.add_sample(
                            {
                                "kind": "path_value",
                                "path": child_path,
                                "from": next_child,
                                "to": normalized_path_value,
                            },
                            sample_limit=sample_limit,
                        )
                        next_child = normalized_path_value
                result[next_key] = next_child
            return result

        if isinstance(node, list):
            return [visit(child, f"{path}[{index}]") for index, child in enumerate(node)]

        return node

    return visit(value, ""), stats
