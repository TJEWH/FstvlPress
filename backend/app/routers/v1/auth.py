"""
Authentication router - provides auth configuration endpoint.

Environment modes:
- dev: Backend accepts any token, frontend bypasses Keycloak
- local-keycloak: Keycloak tokens validated against local instance
- production: Keycloak tokens validated against production server
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.access_control import (
    capabilities_for_internal_role,
    normalize_internal_role,
    permissions_for_internal_role,
    resolved_keycloak_admin_role,
)
from app.deps import get_current_user
from app.security import KeycloakUser, create_app_token, verify_keycloak_token
from app.settings import settings
from app.temp_credentials import TempCredentialAuthError, TempCredentialError, authenticate_temp_credential

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class AuthCapabilitiesResponse(BaseModel):
    is_admin: bool
    can_content: bool
    can_design: bool
    can_admin_design: bool
    can_admin_general: bool


class AuthConfigResponse(BaseModel):
    mode: Literal["dev", "keycloak"]
    login_type: Literal["none", "redirect"]
    keycloak_admin_role: str | None = None
    internal_role: str
    capabilities: AuthCapabilitiesResponse
    access_source: str | None = None


class AppTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int


class AppTokenRequest(BaseModel):
    keycloak_token: str


class TempLoginRequest(BaseModel):
    username: str
    password: str


class TempLoginRateLimiter:
    _MAX_TRACKED_KEYS = 10_000

    def __init__(
        self,
        *,
        window_seconds: int,
        max_attempts_per_ip: int,
        max_attempts_per_username: int,
        max_attempts_per_ip_username: int,
    ):
        self.window_seconds = max(10, int(window_seconds))
        self.max_attempts_per_ip = max(1, int(max_attempts_per_ip))
        self.max_attempts_per_username = max(1, int(max_attempts_per_username))
        self.max_attempts_per_ip_username = max(1, int(max_attempts_per_ip_username))
        self._ip_failures: dict[str, deque[float]] = {}
        self._username_failures: dict[str, deque[float]] = {}
        self._pair_failures: dict[str, deque[float]] = {}

    def _prune(self, bucket: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

    def _count(self, mapping: dict[str, deque[float]], key: str, now: float) -> int:
        bucket = mapping.get(key)
        if not bucket:
            return 0
        self._prune(bucket, now)
        if not bucket:
            mapping.pop(key, None)
            return 0
        return len(bucket)

    def allow(self, *, ip: str, username: str) -> bool:
        now = time.time()
        by_ip = self._count(self._ip_failures, ip, now)
        if by_ip >= self.max_attempts_per_ip:
            return False
        by_username = self._count(self._username_failures, username, now)
        if by_username >= self.max_attempts_per_username:
            return False
        pair_key = f"{ip}|{username}"
        by_pair = self._count(self._pair_failures, pair_key, now)
        return by_pair < self.max_attempts_per_ip_username

    def _record(self, mapping: dict[str, deque[float]], key: str, now: float) -> None:
        bucket = mapping.setdefault(key, deque())
        self._prune(bucket, now)
        bucket.append(now)
        if len(mapping) > self._MAX_TRACKED_KEYS:
            self._cleanup_mapping(mapping, now)

    def _cleanup_mapping(self, mapping: dict[str, deque[float]], now: float) -> None:
        stale_keys = []
        for raw_key, bucket in mapping.items():
            self._prune(bucket, now)
            if not bucket:
                stale_keys.append(raw_key)
        for stale_key in stale_keys:
            mapping.pop(stale_key, None)

    def record_failure(self, *, ip: str, username: str) -> None:
        now = time.time()
        self._record(self._ip_failures, ip, now)
        self._record(self._username_failures, username, now)
        self._record(self._pair_failures, f"{ip}|{username}", now)

    def record_success(self, *, ip: str, username: str) -> None:
        self._pair_failures.pop(f"{ip}|{username}", None)
        self._username_failures.pop(username, None)


temp_login_rate_limiter = TempLoginRateLimiter(
    window_seconds=settings.temp_login_rate_limit_window_seconds,
    max_attempts_per_ip=settings.temp_login_max_attempts_per_ip,
    max_attempts_per_username=settings.temp_login_max_attempts_per_username,
    max_attempts_per_ip_username=settings.temp_login_max_attempts_per_ip_username,
)


def _set_no_store_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _resolve_client_identifier(request: Request) -> str:
    if request.client and request.client.host:
        return str(request.client.host)[:128]
    return "unknown"


@router.get("/config", response_model=AuthConfigResponse)
async def get_auth_config(
    user: KeycloakUser = Depends(get_current_user),
):
    """
    Authenticated endpoint returning frontend auth/access capabilities.
    """
    keycloak_admin_role = resolved_keycloak_admin_role() or None
    internal_role = user.internal_role or "no_access"
    capabilities = AuthCapabilitiesResponse(**capabilities_for_internal_role(internal_role))

    env = settings.environment
    if env == "dev":
        return AuthConfigResponse(
            mode="dev",
            login_type="none",
            keycloak_admin_role=keycloak_admin_role,
            internal_role=internal_role,
            capabilities=capabilities,
            access_source=user.access_source,
        )
    return AuthConfigResponse(
        mode="keycloak",
        login_type="redirect",
        keycloak_admin_role=keycloak_admin_role,
        internal_role=internal_role,
        capabilities=capabilities,
        access_source=user.access_source,
    )


@router.post("/app-token", response_model=AppTokenResponse)
async def issue_app_token(payload: AppTokenRequest, response: Response):
    """
    Issue a compact backend token after successful authentication/authorization.
    Accepts the Keycloak token in request body to avoid oversized Authorization headers.
    """
    token = (payload.keycloak_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="keycloak_token is required")
    user = await verify_keycloak_token(token)
    expires_in = int(settings.app_token_ttl_seconds)
    _set_no_store_headers(response)
    return AppTokenResponse(
        access_token=create_app_token(user, expires_in_seconds=expires_in),
        expires_in=expires_in,
    )


@router.post("/temp-login", response_model=AppTokenResponse)
async def temp_login(payload: TempLoginRequest, request: Request, response: Response):
    username = str(payload.username or "").strip()
    password = str(payload.password or "")
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password are required")

    client_id = _resolve_client_identifier(request)
    normalized_username = username.lower()
    limiter_username = normalized_username[:128]
    if not temp_login_rate_limiter.allow(ip=client_id, username=limiter_username):
        logger.warning("Temp login throttled for client=%s username=%s", client_id, normalized_username)
        raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")

    try:
        credential = await authenticate_temp_credential(
            username=normalized_username,
            password=password,
        )
    except (TempCredentialAuthError, TempCredentialError):
        temp_login_rate_limiter.record_failure(ip=client_id, username=limiter_username)
        await asyncio.sleep(0.2)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    internal_role = normalize_internal_role(
        credential.get("internal_role"),
        default="no_access",
        allow_no_access=True,
    )
    temp_user = KeycloakUser(
        sub=f"temp-credential:{credential['id']}",
        username=credential.get("username"),
        permissions=permissions_for_internal_role(internal_role),
        roles={"temp_user"},
        realm_roles={"temp_user"},
        client_roles={},
        groups=set(),
        internal_role=internal_role,
        access_source="temp_credential",
        temp_credential_id=credential["id"],
    )

    expires_in = int(settings.app_token_ttl_seconds)
    temp_login_rate_limiter.record_success(ip=client_id, username=limiter_username)
    _set_no_store_headers(response)
    return AppTokenResponse(
        access_token=create_app_token(temp_user, expires_in_seconds=expires_in),
        expires_in=expires_in,
    )
