from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Literal

from pymongo import ReturnDocument

from app.collection_names import ACCESS_CONTROL_CONFIG_COLLECTION
from app.db import get_client
from app.settings import settings

InternalRole = Literal[
    "no_access",
    "content",
    "design",
    "admin_design",
    "admin_general",
]

INTERNAL_ROLE_ORDER: tuple[InternalRole, ...] = (
    "no_access",
    "content",
    "design",
    "admin_design",
    "admin_general",
)
INTERNAL_ROLE_RANK = {role: index for index, role in enumerate(INTERNAL_ROLE_ORDER)}
EDITABLE_INTERNAL_ROLES: tuple[InternalRole, ...] = (
    "content",
    "design",
    "admin_design",
    "admin_general",
)

DEFAULT_MAPPING_ROLE: InternalRole = "content"
FALLBACK_INTERNAL_ROLE: InternalRole = "no_access"

ACCESS_CONTROL_CONFIG_KEY = ACCESS_CONTROL_CONFIG_COLLECTION
ACCESS_CONTROL_CONFIG_TTL_SECONDS = 15

CONTENT_PERMISSIONS = frozenset(
    {
        "assets:read",
        "assets:write",
        "pages:read",
        "pages:write",
        "sections:read",
        "sections:write",
        "content:read",
        "content:write",
        "content:publish",
    }
)
DESIGN_PERMISSIONS = frozenset({*CONTENT_PERMISSIONS, "design:write"})
ADMIN_DESIGN_PERMISSIONS = frozenset({*DESIGN_PERMISSIONS, "admin:design"})
ADMIN_GENERAL_PERMISSIONS = frozenset(
    {
        *ADMIN_DESIGN_PERMISSIONS,
        "content:admin",
        "admin:general",
    }
)

ROLE_PERMISSIONS: dict[InternalRole, frozenset[str]] = {
    "no_access": frozenset(),
    "content": CONTENT_PERMISSIONS,
    "design": DESIGN_PERMISSIONS,
    "admin_design": ADMIN_DESIGN_PERMISSIONS,
    "admin_general": ADMIN_GENERAL_PERMISSIONS,
}

ALL_PERMISSIONS = set(ADMIN_GENERAL_PERMISSIONS)

_access_config_cache: dict[str, Any] = {"value": None, "expires_at": None}


def _strip_wrapping_quotes(value: str | None) -> str:
    raw = str(value or "").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        raw = raw[1:-1].strip()
    return raw


def parse_csv(value: str) -> list[str]:
    raw_value = str(value or "")
    if not raw_value.strip():
        return []
    entries = re.split(r"[,;\n]+", raw_value)
    normalized_entries: list[str] = []
    for entry in entries:
        cleaned = _strip_wrapping_quotes(entry)
        if cleaned:
            normalized_entries.append(cleaned)
    return normalized_entries


def resolved_keycloak_admin_role() -> str:
    primary = (settings.keycloak_admin_role or "").strip()
    if primary:
        return primary
    legacy_roles = parse_csv(settings.keycloak_admin_roles)
    return legacy_roles[0] if legacy_roles else ""


def resolved_keycloak_admin_roles() -> set[str]:
    roles: set[str] = set()
    primary = normalize_keycloak_role(settings.keycloak_admin_role)
    if primary:
        roles.add(primary)
    for raw_role in parse_csv(settings.keycloak_admin_roles):
        normalized = normalize_keycloak_role(raw_role)
        if normalized:
            roles.add(normalized)
    return roles


def resolved_env_admin_users() -> set[str]:
    return {normalize_username(username) for username in parse_csv(settings.keycloak_admin_users)}


def normalize_internal_role(
    role: str | None,
    *,
    default: InternalRole = DEFAULT_MAPPING_ROLE,
    allow_no_access: bool = False,
) -> InternalRole:
    value = str(role or "").strip().lower()
    if allow_no_access and value == "no_access":
        return "no_access"
    if value in EDITABLE_INTERNAL_ROLES:
        return value  # type: ignore[return-value]
    return default


def normalize_username(value: str | None) -> str:
    return str(value or "").strip().lower()


def normalize_keycloak_role(value: str | None) -> str:
    return _strip_wrapping_quotes(value).lower()


def role_at_least(role: str | None, required: str) -> bool:
    return INTERNAL_ROLE_RANK.get(str(role or ""), -1) >= INTERNAL_ROLE_RANK.get(required, -1)


def highest_role(roles: list[InternalRole]) -> InternalRole:
    if not roles:
        return FALLBACK_INTERNAL_ROLE
    return max(roles, key=lambda role: INTERNAL_ROLE_RANK.get(role, -1))


def permissions_for_internal_role(role: str | None) -> set[str]:
    normalized = normalize_internal_role(
        str(role or ""),
        default=FALLBACK_INTERNAL_ROLE,
        allow_no_access=True,
    )
    return set(ROLE_PERMISSIONS.get(normalized, ROLE_PERMISSIONS[FALLBACK_INTERNAL_ROLE]))


def infer_internal_role_from_permissions(permissions: set[str] | None) -> InternalRole:
    perms = set(permissions or set())
    if "admin:general" in perms or "content:admin" in perms:
        return "admin_general"
    if "admin:design" in perms:
        return "admin_design"
    if "design:write" in perms:
        return "design"
    if "content:write" in perms:
        return "content"
    return "no_access"


def capabilities_for_internal_role(role: str | None) -> dict[str, bool]:
    return {
        "is_admin": role_at_least(role, "content"),
        "can_content": role_at_least(role, "content"),
        "can_design": role_at_least(role, "design"),
        "can_admin_design": role_at_least(role, "admin_design"),
        "can_admin_general": role_at_least(role, "admin_general"),
    }


def _default_access_control_doc(now: datetime | None = None) -> dict:
    timestamp = now or datetime.utcnow()
    return {
        "key": ACCESS_CONTROL_CONFIG_KEY,
        "username_mappings": [],
        "keycloak_role_mappings": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def _normalize_access_control_doc(doc: dict | None) -> dict:
    source = doc or _default_access_control_doc()

    username_seen: set[str] = set()
    username_mappings: list[dict[str, str]] = []
    for raw in source.get("username_mappings", []) or []:
        if not isinstance(raw, dict):
            continue
        username = normalize_username(raw.get("username"))
        if not username or username in username_seen:
            continue
        username_seen.add(username)
        username_mappings.append(
            {
                "username": username,
                "internal_role": normalize_internal_role(raw.get("internal_role")),
            }
        )
    username_mappings.sort(key=lambda entry: entry["username"])

    role_seen: set[str] = set()
    keycloak_role_mappings: list[dict[str, str]] = []
    env_admin_roles = resolved_keycloak_admin_roles()
    for raw in source.get("keycloak_role_mappings", []) or []:
        if not isinstance(raw, dict):
            continue
        keycloak_role = normalize_keycloak_role(raw.get("keycloak_role"))
        if not keycloak_role or keycloak_role in role_seen:
            continue
        if keycloak_role in env_admin_roles:
            # Keep env-defined admin roles immutable and outside editable mappings.
            continue
        role_seen.add(keycloak_role)
        keycloak_role_mappings.append(
            {
                "keycloak_role": keycloak_role,
                "internal_role": normalize_internal_role(raw.get("internal_role")),
            }
        )
    keycloak_role_mappings.sort(key=lambda entry: entry["keycloak_role"])

    return {
        "key": ACCESS_CONTROL_CONFIG_KEY,
        "username_mappings": username_mappings,
        "keycloak_role_mappings": keycloak_role_mappings,
        "created_at": source.get("created_at"),
        "updated_at": source.get("updated_at"),
    }


async def get_access_control_config(*, force_refresh: bool = False) -> dict:
    now = datetime.utcnow()
    if not force_refresh:
        cached_value = _access_config_cache.get("value")
        cached_expiry = _access_config_cache.get("expires_at")
        if cached_value and isinstance(cached_expiry, datetime) and now < cached_expiry:
            return cached_value

    db = get_client()[settings.mongo_db]
    coll = db[ACCESS_CONTROL_CONFIG_COLLECTION]

    doc = await coll.find_one({"key": ACCESS_CONTROL_CONFIG_KEY})
    if not doc:
        defaults = _default_access_control_doc(now=now)
        result = await coll.insert_one(defaults)
        defaults["_id"] = result.inserted_id
        doc = defaults

    normalized = _normalize_access_control_doc(doc)
    _access_config_cache["value"] = normalized
    _access_config_cache["expires_at"] = now + timedelta(seconds=ACCESS_CONTROL_CONFIG_TTL_SECONDS)
    return normalized


def invalidate_access_control_cache() -> None:
    _access_config_cache["value"] = None
    _access_config_cache["expires_at"] = None


def validate_access_control_payload(
    *,
    username_mappings: list[dict[str, Any]] | None,
    keycloak_role_mappings: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if username_mappings is not None and not isinstance(username_mappings, list):
        raise ValueError("username_mappings must be a list")
    if keycloak_role_mappings is not None and not isinstance(keycloak_role_mappings, list):
        raise ValueError("keycloak_role_mappings must be a list")

    seen_usernames: set[str] = set()
    for index, entry in enumerate(username_mappings or []):
        if not isinstance(entry, dict):
            raise ValueError(f"username_mappings[{index}] must be an object")
        username = normalize_username(entry.get("username"))
        if not username:
            raise ValueError(f"username_mappings[{index}].username is required")
        if username in seen_usernames:
            raise ValueError(f"Duplicate username mapping for '{username}'")
        seen_usernames.add(username)

    env_admin_roles = resolved_keycloak_admin_roles()
    seen_keycloak_roles: set[str] = set()
    for index, entry in enumerate(keycloak_role_mappings or []):
        if not isinstance(entry, dict):
            raise ValueError(f"keycloak_role_mappings[{index}] must be an object")
        keycloak_role = normalize_keycloak_role(entry.get("keycloak_role"))
        if not keycloak_role:
            raise ValueError(f"keycloak_role_mappings[{index}].keycloak_role is required")
        if keycloak_role in env_admin_roles:
            raise ValueError(
                f"The configured Keycloak admin role '{keycloak_role}' is immutable and cannot be edited"
            )
        if keycloak_role in seen_keycloak_roles:
            raise ValueError(f"Duplicate Keycloak role mapping for '{keycloak_role}'")
        seen_keycloak_roles.add(keycloak_role)

    normalized_doc = _normalize_access_control_doc(
        {
            "username_mappings": username_mappings if username_mappings is not None else [],
            "keycloak_role_mappings": keycloak_role_mappings if keycloak_role_mappings is not None else [],
        }
    )
    return normalized_doc["username_mappings"], normalized_doc["keycloak_role_mappings"]


async def save_access_control_config(
    *,
    username_mappings: list[dict[str, Any]] | None = None,
    keycloak_role_mappings: list[dict[str, Any]] | None = None,
) -> dict:
    current = await get_access_control_config()

    next_username_mappings = (
        username_mappings if username_mappings is not None else current["username_mappings"]
    )
    next_keycloak_role_mappings = (
        keycloak_role_mappings
        if keycloak_role_mappings is not None
        else current["keycloak_role_mappings"]
    )
    normalized_usernames, normalized_keycloak_roles = validate_access_control_payload(
        username_mappings=next_username_mappings,
        keycloak_role_mappings=next_keycloak_role_mappings,
    )

    now = datetime.utcnow()
    db = get_client()[settings.mongo_db]
    coll = db[ACCESS_CONTROL_CONFIG_COLLECTION]
    updated = await coll.find_one_and_update(
        {"key": ACCESS_CONTROL_CONFIG_KEY},
        {
            "$set": {
                "username_mappings": normalized_usernames,
                "keycloak_role_mappings": normalized_keycloak_roles,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    invalidate_access_control_cache()
    normalized = _normalize_access_control_doc(updated)
    _access_config_cache["value"] = normalized
    _access_config_cache["expires_at"] = now + timedelta(seconds=ACCESS_CONTROL_CONFIG_TTL_SECONDS)
    return normalized


async def resolve_internal_role_for_user(
    *,
    username: str | None,
    keycloak_roles: set[str] | None,
) -> tuple[InternalRole, str]:
    normalized_roles = {normalize_keycloak_role(role) for role in (keycloak_roles or set()) if role}
    env_admin_roles = resolved_keycloak_admin_roles()
    if env_admin_roles.intersection(normalized_roles):
        return "admin_general", "env_keycloak_admin_role"

    normalized_username = normalize_username(username)
    env_admin_users = resolved_env_admin_users()
    if normalized_username and normalized_username in env_admin_users:
        return "admin_general", "env_admin_user"

    config = await get_access_control_config()

    username_map = {
        normalize_username(entry.get("username")): normalize_internal_role(entry.get("internal_role"))
        for entry in config.get("username_mappings", [])
        if isinstance(entry, dict)
    }
    if normalized_username and normalized_username in username_map:
        return username_map[normalized_username], "username_mapping"

    matched_roles: list[InternalRole] = []
    for entry in config.get("keycloak_role_mappings", []):
        if not isinstance(entry, dict):
            continue
        mapped_role = normalize_keycloak_role(entry.get("keycloak_role"))
        if not mapped_role or mapped_role not in normalized_roles:
            continue
        matched_roles.append(normalize_internal_role(entry.get("internal_role")))

    if matched_roles:
        return highest_role(matched_roles), "keycloak_role_mapping"

    return FALLBACK_INTERNAL_ROLE, "fallback_no_access"
