from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.access_control import EDITABLE_INTERNAL_ROLES, normalize_internal_role, normalize_username
from app.collection_names import TEMPORARY_USERS_COLLECTION
from app.db import get_client
from app.settings import settings

TEMP_CREDENTIALS_COLLECTION = TEMPORARY_USERS_COLLECTION
TEMP_CREDENTIAL_PASSWORD_ALGORITHM = "pbkdf2_sha256"
TEMP_CREDENTIAL_PASSWORD_ITERATIONS = 390_000
TEMP_CREDENTIAL_PASSWORD_SALT_BYTES = 16
TEMP_CREDENTIAL_PASSWORD_BYTES = 18
TEMP_CREDENTIAL_DEFAULT_TTL_DAYS = 7
TEMP_CREDENTIAL_USERNAME_REGEX = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
TEMP_CREDENTIAL_DUMMY_SALT = b"fstvlpress-temp-credential-dummy-salt"


class TempCredentialError(ValueError):
    pass


class TempCredentialNotFoundError(LookupError):
    pass


class TempCredentialAuthError(TempCredentialError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _collection():
    return get_client()[settings.mongo_db][TEMP_CREDENTIALS_COLLECTION]


def _normalize_expires_at(expires_at: datetime | None) -> datetime:
    if expires_at is None:
        return _utcnow() + timedelta(days=TEMP_CREDENTIAL_DEFAULT_TTL_DAYS)
    if expires_at.tzinfo is None:
        # Treat naive timestamps as UTC to keep API behavior deterministic.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at.astimezone(timezone.utc)


def _normalize_temp_role(role: str | None) -> str:
    normalized = str(role or "").strip().lower()
    if normalized not in EDITABLE_INTERNAL_ROLES:
        raise TempCredentialError(f"internal_role must be one of: {', '.join(EDITABLE_INTERNAL_ROLES)}")
    return normalize_internal_role(normalized)


def _normalize_temp_username(username: str | None) -> str:
    normalized = normalize_username(username)
    if not normalized:
        raise TempCredentialError("username is required")
    if not TEMP_CREDENTIAL_USERNAME_REGEX.match(normalized):
        raise TempCredentialError(
            "username must be 3-64 chars and may only contain lowercase letters, numbers, dot, underscore, hyphen"
        )
    return normalized


def _generate_password() -> str:
    return secrets.token_urlsafe(TEMP_CREDENTIAL_PASSWORD_BYTES)


def _hash_password(password: str, *, salt_bytes: bytes | None = None) -> dict[str, Any]:
    salt = salt_bytes or secrets.token_bytes(TEMP_CREDENTIAL_PASSWORD_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        TEMP_CREDENTIAL_PASSWORD_ITERATIONS,
    )
    return {
        "algorithm": TEMP_CREDENTIAL_PASSWORD_ALGORITHM,
        "iterations": TEMP_CREDENTIAL_PASSWORD_ITERATIONS,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "hash_b64": base64.b64encode(digest).decode("ascii"),
    }


def _verify_password(password: str, *, salt_b64: str, hash_b64: str, iterations: int) -> bool:
    try:
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected_digest = base64.b64decode(hash_b64.encode("ascii"))
    except Exception:
        return False
    candidate_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        int(iterations),
    )
    return hmac.compare_digest(candidate_digest, expected_digest)


def _burn_password_check(password: str) -> None:
    # Keep failed-auth timing more uniform to reduce username/account enumeration signal.
    hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        TEMP_CREDENTIAL_DUMMY_SALT,
        TEMP_CREDENTIAL_PASSWORD_ITERATIONS,
    )


def _is_expired(expires_at: datetime | None) -> bool:
    if not isinstance(expires_at, datetime):
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= _utcnow()


def _to_public_doc(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc.get("_id")),
        "username": str(doc.get("username") or ""),
        "internal_role": str(doc.get("internal_role") or "content"),
        "active": bool(doc.get("active", False)),
        "is_expired": _is_expired(doc.get("expires_at")),
        "expires_at": doc.get("expires_at"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
        "revoked_at": doc.get("revoked_at"),
        "created_by_username": doc.get("created_by_username"),
        "created_by_sub": doc.get("created_by_sub"),
        "revoked_by_username": doc.get("revoked_by_username"),
        "revoked_by_sub": doc.get("revoked_by_sub"),
    }


async def list_temp_credentials() -> list[dict[str, Any]]:
    cursor = _collection().find({}, {"password": 0}).sort([("created_at", -1)])
    docs = await cursor.to_list(length=500)
    return [_to_public_doc(doc) for doc in docs]


async def create_temp_credential(
    *,
    username: str,
    internal_role: str,
    expires_at: datetime | None = None,
    created_by_username: str | None = None,
    created_by_sub: str | None = None,
) -> tuple[dict[str, Any], str]:
    normalized_username = _normalize_temp_username(username)
    normalized_role = _normalize_temp_role(internal_role)
    normalized_expires_at = _normalize_expires_at(expires_at)
    now = _utcnow()
    if normalized_expires_at <= now:
        raise TempCredentialError("expires_at must be in the future")

    generated_password = _generate_password()
    password_meta = _hash_password(generated_password)
    doc = {
        "username": normalized_username,
        "internal_role": normalized_role,
        "password": {
            "algorithm": password_meta["algorithm"],
            "iterations": password_meta["iterations"],
            "salt_b64": password_meta["salt_b64"],
            "hash_b64": password_meta["hash_b64"],
        },
        "active": True,
        "expires_at": normalized_expires_at,
        "created_at": now,
        "updated_at": now,
        "revoked_at": None,
        "created_by_username": normalize_username(created_by_username) or None,
        "created_by_sub": str(created_by_sub or "").strip() or None,
        "revoked_by_username": None,
        "revoked_by_sub": None,
    }

    try:
        result = await _collection().insert_one(doc)
    except DuplicateKeyError:
        raise TempCredentialError(f"username '{normalized_username}' already exists")

    doc["_id"] = result.inserted_id
    return _to_public_doc(doc), generated_password


def _parse_object_id(credential_id: str) -> ObjectId:
    raw = str(credential_id or "").strip()
    if not raw or not ObjectId.is_valid(raw):
        raise TempCredentialError("Invalid credential id")
    return ObjectId(raw)


async def revoke_temp_credential(
    *,
    credential_id: str,
    revoked_by_username: str | None = None,
    revoked_by_sub: str | None = None,
) -> dict[str, Any]:
    object_id = _parse_object_id(credential_id)
    now = _utcnow()
    updated = await _collection().find_one_and_update(
        {"_id": object_id},
        {
            "$set": {
                "active": False,
                "revoked_at": now,
                "updated_at": now,
                "revoked_by_username": normalize_username(revoked_by_username) or None,
                "revoked_by_sub": str(revoked_by_sub or "").strip() or None,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise TempCredentialNotFoundError("Temp credential not found")
    return _to_public_doc(updated)


_MISSING = object()


async def update_temp_credential(
    *,
    credential_id: str,
    username: Any = _MISSING,
    internal_role: Any = _MISSING,
    expires_at: Any = _MISSING,
) -> dict[str, Any]:
    object_id = _parse_object_id(credential_id)
    now = _utcnow()
    updates: dict[str, Any] = {}

    if username is not _MISSING:
        updates["username"] = _normalize_temp_username(username)
    if internal_role is not _MISSING:
        updates["internal_role"] = _normalize_temp_role(internal_role)
    if expires_at is not _MISSING:
        normalized_expires_at = _normalize_expires_at(expires_at)
        if normalized_expires_at <= now:
            raise TempCredentialError("expires_at must be in the future")
        updates["expires_at"] = normalized_expires_at

    if not updates:
        raise TempCredentialError("No fields to update")

    updates["updated_at"] = now

    try:
        updated = await _collection().find_one_and_update(
            {"_id": object_id},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        duplicate_username = updates.get("username")
        if duplicate_username:
            raise TempCredentialError(f"username '{duplicate_username}' already exists")
        raise

    if not updated:
        raise TempCredentialNotFoundError("Temp credential not found")
    return _to_public_doc(updated)


async def delete_temp_credential(*, credential_id: str) -> None:
    object_id = _parse_object_id(credential_id)
    result = await _collection().delete_one({"_id": object_id})
    if result.deleted_count == 0:
        raise TempCredentialNotFoundError("Temp credential not found")


async def authenticate_temp_credential(
    *,
    username: str,
    password: str,
) -> dict[str, Any]:
    invalid_auth_message = "Invalid username or password"
    normalized_username = _normalize_temp_username(username)
    raw_password = str(password or "")
    if not raw_password:
        raise TempCredentialAuthError("username and password are required")

    doc = await _collection().find_one({"username": normalized_username})
    if not doc:
        _burn_password_check(raw_password)
        raise TempCredentialAuthError(invalid_auth_message)
    if not bool(doc.get("active", False)):
        _burn_password_check(raw_password)
        raise TempCredentialAuthError(invalid_auth_message)
    if _is_expired(doc.get("expires_at")):
        _burn_password_check(raw_password)
        raise TempCredentialAuthError(invalid_auth_message)

    password_doc = doc.get("password") or {}
    algorithm = str(password_doc.get("algorithm") or "")
    if algorithm != TEMP_CREDENTIAL_PASSWORD_ALGORITHM:
        _burn_password_check(raw_password)
        raise TempCredentialAuthError(invalid_auth_message)
    try:
        iterations = int(password_doc.get("iterations") or 0)
    except Exception:
        _burn_password_check(raw_password)
        raise TempCredentialAuthError(invalid_auth_message)
    salt_b64 = str(password_doc.get("salt_b64") or "")
    hash_b64 = str(password_doc.get("hash_b64") or "")
    if not iterations or not salt_b64 or not hash_b64:
        _burn_password_check(raw_password)
        raise TempCredentialAuthError(invalid_auth_message)
    if not _verify_password(
        raw_password,
        salt_b64=salt_b64,
        hash_b64=hash_b64,
        iterations=iterations,
    ):
        raise TempCredentialAuthError(invalid_auth_message)

    return _to_public_doc(doc)


async def get_active_temp_credential_for_token(credential_id: str) -> dict[str, Any] | None:
    try:
        object_id = _parse_object_id(credential_id)
    except TempCredentialError:
        return None
    doc = await _collection().find_one({"_id": object_id}, {"password": 0})
    if not doc:
        return None
    public_doc = _to_public_doc(doc)
    if not public_doc["active"] or public_doc["is_expired"]:
        return None
    return public_doc
