from __future__ import annotations

from copy import deepcopy
from typing import Any

from bson import ObjectId

LEGACY_SECTION_CONTAINER_OVERRIDE_KEY = "_sectionContainerId"


def _normalize_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _dedupe_ordered_ids(values: list[Any]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in values:
        section_id = _normalize_text(raw)
        if not section_id or section_id in seen:
            continue
        seen.add(section_id)
        ordered.append(section_id)
    return ordered


def _new_container_id() -> str:
    return f"container_{ObjectId()}"


def flatten_section_structure(section_structure: Any) -> list[str]:
    """Flatten a normalized section_structure into section ids."""
    flattened: list[str] = []
    seen: set[str] = set()
    nodes = section_structure if isinstance(section_structure, list) else []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type") or "").strip().lower()
        if node_type == "section":
            section_id = _normalize_text(node.get("section_id"))
            if section_id and section_id not in seen:
                seen.add(section_id)
                flattened.append(section_id)
            continue
        if node_type != "container":
            continue
        raw_members = node.get("section_ids") if isinstance(node.get("section_ids"), list) else []
        for raw_member in raw_members:
            section_id = _normalize_text(raw_member)
            if not section_id or section_id in seen:
                continue
            seen.add(section_id)
            flattened.append(section_id)
    return flattened


def normalize_section_structure(
    section_structure: Any,
    ordered_section_ids: list[Any],
) -> list[dict[str, Any]]:
    """
    Normalize section_structure to a flat list of section/container nodes.

    The input `ordered_section_ids` is the source-of-truth set of section ids.
    Missing ids are dropped, unknown ids are ignored, and leftovers are appended
    as plain section nodes.
    """
    canonical_ids = _dedupe_ordered_ids(ordered_section_ids if isinstance(ordered_section_ids, list) else [])
    valid_ids = set(canonical_ids)
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []

    nodes = section_structure if isinstance(section_structure, list) else []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type") or "").strip().lower()
        if node_type == "section":
            section_id = _normalize_text(node.get("section_id"))
            if not section_id or section_id not in valid_ids or section_id in seen:
                continue
            seen.add(section_id)
            normalized.append({"type": "section", "section_id": section_id})
            continue

        if node_type != "container":
            continue

        raw_members = node.get("section_ids") if isinstance(node.get("section_ids"), list) else []
        members: list[str] = []
        member_seen: set[str] = set()
        for raw_member in raw_members:
            section_id = _normalize_text(raw_member)
            if (
                not section_id
                or section_id not in valid_ids
                or section_id in seen
                or section_id in member_seen
            ):
                continue
            member_seen.add(section_id)
            members.append(section_id)

        if len(members) >= 2:
            container_id = _normalize_text(node.get("container_id")) or _new_container_id()
            normalized.append(
                {
                    "type": "container",
                    "container_id": container_id,
                    "section_ids": members,
                }
            )
            seen.update(members)
        elif len(members) == 1:
            single_id = members[0]
            seen.add(single_id)
            normalized.append({"type": "section", "section_id": single_id})

    for section_id in canonical_ids:
        if section_id in seen:
            continue
        normalized.append({"type": "section", "section_id": section_id})

    return normalized


def build_section_structure_from_container_membership(
    ordered_section_ids: list[Any],
    section_to_container_id: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Build section_structure nodes from a flat ordered id list + container mapping.

    Container nodes are emitted when at least 2 members are present.
    """
    ordered_ids = _dedupe_ordered_ids(ordered_section_ids if isinstance(ordered_section_ids, list) else [])
    mapping = section_to_container_id if isinstance(section_to_container_id, dict) else {}

    members_by_container: dict[str, list[str]] = {}
    for section_id in ordered_ids:
        container_id = _normalize_text(mapping.get(section_id))
        if not container_id:
            continue
        members = members_by_container.setdefault(container_id, [])
        if section_id not in members:
            members.append(section_id)

    structure: list[dict[str, Any]] = []
    emitted: set[str] = set()
    for section_id in ordered_ids:
        container_id = _normalize_text(mapping.get(section_id))
        if not container_id:
            structure.append({"type": "section", "section_id": section_id})
            continue
        if container_id in emitted:
            continue
        members = members_by_container.get(container_id, [])
        if len(members) >= 2:
            structure.append(
                {
                    "type": "container",
                    "container_id": container_id,
                    "section_ids": members,
                }
            )
        else:
            structure.append({"type": "section", "section_id": section_id})
        emitted.add(container_id)

    return normalize_section_structure(structure, ordered_ids)


def extract_container_membership_from_structure(section_structure: Any) -> dict[str, str]:
    """Return {section_id: container_id} for members inside container nodes."""
    result: dict[str, str] = {}
    nodes = section_structure if isinstance(section_structure, list) else []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if str(node.get("type") or "").strip().lower() != "container":
            continue
        container_id = _normalize_text(node.get("container_id"))
        if not container_id:
            continue
        raw_members = node.get("section_ids") if isinstance(node.get("section_ids"), list) else []
        for raw_member in raw_members:
            section_id = _normalize_text(raw_member)
            if section_id:
                result[section_id] = container_id
    return result


def strip_legacy_container_override(overrides: Any) -> dict[str, Any] | None:
    if not isinstance(overrides, dict):
        return None
    normalized = deepcopy(overrides)
    if LEGACY_SECTION_CONTAINER_OVERRIDE_KEY in normalized:
        del normalized[LEGACY_SECTION_CONTAINER_OVERRIDE_KEY]
    return normalized or None


def resolve_section_structure(
    section_structure: Any,
    ordered_section_ids: list[Any],
) -> list[dict[str, Any]]:
    """Resolve canonical structure using stored structure only."""
    ordered_ids = _dedupe_ordered_ids(ordered_section_ids if isinstance(ordered_section_ids, list) else [])
    has_nodes = isinstance(section_structure, list) and len(section_structure) > 0
    if has_nodes:
        return normalize_section_structure(section_structure, ordered_ids)
    return normalize_section_structure([], ordered_ids)


def apply_section_order_from_structure(
    sections: list[Any],
    section_structure: Any,
    *,
    section_id_field: str,
) -> list[dict[str, Any]]:
    """
    Re-order section refs/embedded sections and rewrite their `order` fields from structure.
    """
    refs = [deepcopy(section) for section in sections if isinstance(section, dict)]
    order_ids = flatten_section_structure(section_structure)
    index_by_id = {section_id: index for index, section_id in enumerate(order_ids)}

    buckets: dict[str, list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for ref in refs:
        section_id = _normalize_text(ref.get(section_id_field))
        if not section_id:
            passthrough.append(ref)
            continue
        buckets.setdefault(section_id, []).append(ref)

    ordered_refs: list[dict[str, Any]] = []
    for section_id in order_ids:
        queued = buckets.get(section_id) or []
        if not queued:
            continue
        ordered_refs.append(queued.pop(0))

    for section_id, queued in buckets.items():
        if section_id in index_by_id:
            ordered_refs.extend(queued)
            continue
        ordered_refs.extend(queued)

    ordered_refs.extend(passthrough)

    for index, ref in enumerate(ordered_refs):
        ref["order"] = index
    return ordered_refs
