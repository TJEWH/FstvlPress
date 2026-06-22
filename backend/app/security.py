from __future__ import annotations

import logging
import time

import httpx
from fastapi import HTTPException, status
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError
from pydantic import BaseModel, Field

from app.access_control import (
    infer_internal_role_from_permissions,
    normalize_internal_role,
    permissions_for_internal_role,
    resolve_internal_role_for_user,
    role_at_least,
)
from app.settings import settings
from app.temp_credentials import get_active_temp_credential_for_token

logger = logging.getLogger(__name__)


class JWKSCache:
    """Cache for Keycloak JWKS (JSON Web Key Set) to avoid fetching on every request."""

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self._jwks: dict | None = None
        self._exp: float = 0.0

    async def get(self) -> dict:
        now = time.time()
        if self._jwks and now < self._exp:
            return self._jwks
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(settings.keycloak_jwks_url)
                response.raise_for_status()
                self._jwks = response.json()
                self._exp = now + self.ttl
                return self._jwks
        except Exception as exc:
            logger.error("Failed to fetch JWKS from %s: %s", settings.keycloak_jwks_url, exc)
            raise

    def invalidate(self) -> None:
        """Force refresh of JWKS on next request (useful when keys rotate)."""
        self._jwks = None
        self._exp = 0.0


jwks_cache = JWKSCache()


class KeycloakUser(BaseModel):
    """User model populated from Keycloak/app token claims."""

    sub: str
    username: str | None = None
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    roles: set[str] = Field(default_factory=set)
    realm_roles: set[str] = Field(default_factory=set)
    client_roles: dict[str, set[str]] = Field(default_factory=dict)
    groups: set[str] = Field(default_factory=set)
    permissions: set[str] = Field(default_factory=set)
    internal_role: str = "no_access"
    access_source: str | None = None
    temp_credential_id: str | None = None

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_realm_role(self, role: str) -> bool:
        return role in self.realm_roles

    def has_client_role(self, client_id: str, role: str) -> bool:
        return role in self.client_roles.get(client_id, set())

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def has_internal_role_at_least(self, required_role: str) -> bool:
        return role_at_least(self.internal_role, required_role)

    def is_in_group(self, group: str) -> bool:
        return group in self.groups

def _extract_keycloak_claims(claims: dict) -> KeycloakUser:
    """
    Extract user information from Keycloak JWT claims.

    Keycloak token structure:
    - realm_access.roles: Realm-level roles
    - resource_access.<client_id>.roles: Client-specific roles
    - groups: User's group memberships (if mapper configured)
    """
    realm_access = claims.get("realm_access") or {}
    realm_roles = set(realm_access.get("roles", []) or [])

    resource_access = claims.get("resource_access") or {}
    client_roles: dict[str, set[str]] = {}
    all_client_roles: set[str] = set()
    for client_id, access in resource_access.items():
        if not isinstance(access, dict):
            continue
        roles = set(access.get("roles", []) or [])
        client_roles[client_id] = roles
        all_client_roles |= roles

    all_roles = realm_roles | all_client_roles
    groups = set(claims.get("groups", []) or [])
    explicit_permissions = set(claims.get("permissions", []) or [])

    return KeycloakUser(
        sub=claims["sub"],
        username=claims.get("preferred_username"),
        email=claims.get("email"),
        email_verified=claims.get("email_verified", False),
        name=claims.get("name"),
        given_name=claims.get("given_name"),
        family_name=claims.get("family_name"),
        roles=all_roles,
        realm_roles=realm_roles,
        client_roles=client_roles,
        groups=groups,
        permissions=explicit_permissions,
    )


async def _apply_internal_access(user: KeycloakUser) -> KeycloakUser:
    resolved_role, source = await resolve_internal_role_for_user(
        username=user.username,
        keycloak_roles=user.roles,
    )
    base_permissions = permissions_for_internal_role(resolved_role)
    extra_permissions = set(user.permissions or set())
    merged_permissions = base_permissions | extra_permissions

    # If token carries stronger explicit permissions, keep role consistent.
    inferred_from_permissions = infer_internal_role_from_permissions(merged_permissions)
    if role_at_least(inferred_from_permissions, resolved_role):
        resolved_role = inferred_from_permissions

    user.internal_role = resolved_role
    user.permissions = merged_permissions
    user.access_source = source
    return user


async def verify_keycloak_token(token: str) -> KeycloakUser:
    """
    Verify a Keycloak JWT token and extract user information.

    Raises HTTPException 401 if token is invalid.
    """
    try:
        jwks = await jwks_cache.get()

        unverified = jwt.get_unverified_claims(token)
        token_aud = unverified.get("aud")
        token_iss = unverified.get("iss")
        expected_aud = settings.keycloak_jwt_audience
        expected_iss = settings.keycloak_issuer

        logger.debug(
            "JWT verification: token aud=%r (expected=%r), iss=%r (expected=%r)",
            token_aud,
            expected_aud,
            token_iss,
            expected_iss,
        )

        aud_matches = False
        if isinstance(token_aud, str):
            aud_matches = token_aud == expected_aud
        elif isinstance(token_aud, list):
            aud_matches = expected_aud in token_aud

        if not aud_matches:
            logger.warning("Audience mismatch: token has %r, expected %r", token_aud, expected_aud)
        if token_iss != expected_iss:
            logger.warning("Issuer mismatch: token has %r, expected %r", token_iss, expected_iss)

        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            issuer=settings.keycloak_issuer,
            options={
                "verify_aud": False,
                "verify_iss": True,
                "verify_exp": True,
                "verify_nbf": True,
            },
        )
        if not aud_matches:
            raise JWTClaimsError(f"Audience mismatch: {token_aud!r} vs {expected_aud!r}")

        user = _extract_keycloak_claims(claims)
        user = await _apply_internal_access(user)
        logger.debug(
            "Resolved access: username=%r internal_role=%r permissions=%r source=%r",
            user.username,
            user.internal_role,
            sorted(user.permissions),
            user.access_source,
        )
        return user

    except ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTClaimsError as exc:
        logger.warning(
            "JWT claims validation failed: %s (expected aud=%r, iss=%r)",
            exc,
            settings.keycloak_jwt_audience,
            settings.keycloak_issuer,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token claims invalid: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch JWKS: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication service unavailable",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as exc:
        logger.error("Unexpected error during token verification: %s: %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

APP_TOKEN_ISSUER = "fstvlpress-backend"
APP_TOKEN_TYPE = "fstvlpress-app"
APP_TOKEN_ALGORITHM = "HS256"


def _app_token_secret() -> str:
    secret = settings.app_token_secret or settings.keycloak_client_secret or settings.backup_api_token
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="App token secret is not configured",
        )
    return secret


def is_app_token(token: str) -> bool:
    """Best-effort check whether token is a compact app token."""
    try:
        claims = jwt.get_unverified_claims(token)
        return claims.get("typ") == APP_TOKEN_TYPE and claims.get("iss") == APP_TOKEN_ISSUER
    except Exception:
        return False


def create_app_token(user: KeycloakUser, expires_in_seconds: int | None = None) -> str:
    """Create a compact backend-issued token with minimal claims."""
    ttl = expires_in_seconds if expires_in_seconds is not None else settings.app_token_ttl_seconds
    now = int(time.time())
    payload = {
        "typ": APP_TOKEN_TYPE,
        "iss": APP_TOKEN_ISSUER,
        "sub": user.sub,
        "preferred_username": user.username,
        "email": user.email,
        "permissions": sorted(user.permissions),
        "internal_role": user.internal_role,
        "access_source": user.access_source,
        "temp_credential_id": user.temp_credential_id,
        "iat": now,
        "exp": now + int(ttl),
    }
    return jwt.encode(payload, _app_token_secret(), algorithm=APP_TOKEN_ALGORITHM)


async def verify_app_token(token: str) -> KeycloakUser:
    """Validate compact backend-issued token and return a KeycloakUser-compatible object."""
    try:
        claims = jwt.decode(
            token,
            _app_token_secret(),
            algorithms=[APP_TOKEN_ALGORITHM],
            issuer=APP_TOKEN_ISSUER,
            options={
                "verify_aud": False,
                "verify_iss": True,
                "verify_exp": True,
                "verify_nbf": False,
            },
        )
        if claims.get("typ") != APP_TOKEN_TYPE:
            raise JWTClaimsError("Not an app token")

        permissions = set(claims.get("permissions", []) or [])
        access_source = str(claims.get("access_source") or "app_token")
        temp_credential_id = str(claims.get("temp_credential_id") or "").strip() or None
        username = (claims.get("preferred_username") or None)
        email = claims.get("email")

        if access_source == "temp_credential":
            if not temp_credential_id:
                raise JWTClaimsError("Temp credential id is missing")
            credential = await get_active_temp_credential_for_token(temp_credential_id)
            if not credential:
                raise JWTClaimsError("Temp credential is inactive or expired")
            internal_role = normalize_internal_role(
                credential.get("internal_role"),
                allow_no_access=True,
                default="no_access",
            )
            permissions = permissions_for_internal_role(internal_role)
            username = credential.get("username") or username
        else:
            claim_role = claims.get("internal_role")
            internal_role = (
                normalize_internal_role(claim_role, allow_no_access=True, default="no_access")
                if isinstance(claim_role, str) and claim_role
                else infer_internal_role_from_permissions(permissions)
            )
            if not permissions:
                permissions = permissions_for_internal_role(internal_role)

        roles: set[str] = set()
        if role_at_least(internal_role, "admin_general"):
            roles.add("admin")
        elif role_at_least(internal_role, "content"):
            roles.add("editor")

        return KeycloakUser(
            sub=claims["sub"],
            username=username,
            email=email,
            permissions=permissions,
            roles=roles,
            realm_roles=roles,
            client_roles={},
            groups=set(),
            internal_role=internal_role,
            access_source=access_source,
            temp_credential_id=temp_credential_id,
        )
    except (ExpiredSignatureError, JWTClaimsError, JWTError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid app token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
