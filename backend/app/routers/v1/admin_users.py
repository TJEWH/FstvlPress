from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.access_control import (
    DEFAULT_MAPPING_ROLE,
    EDITABLE_INTERNAL_ROLES,
    FALLBACK_INTERNAL_ROLE,
    get_access_control_config,
    resolved_keycloak_admin_role,
    save_access_control_config,
)
from app.deps import require_permission
from app.security import KeycloakUser
from app.temp_credentials import (
    TempCredentialError,
    TempCredentialNotFoundError,
    create_temp_credential,
    delete_temp_credential,
    list_temp_credentials,
    revoke_temp_credential,
    update_temp_credential,
)

router = APIRouter(prefix="/admin/users", tags=["admin"])


class UsernameRoleMapping(BaseModel):
    username: str = Field(min_length=1)
    internal_role: str = DEFAULT_MAPPING_ROLE


class KeycloakRoleMapping(BaseModel):
    keycloak_role: str = Field(min_length=1)
    internal_role: str = DEFAULT_MAPPING_ROLE


class AccessControlConfigResponse(BaseModel):
    keycloak_admin_role: str | None = None
    editable_internal_roles: list[str]
    default_internal_role: str
    fallback_internal_role: str
    username_mappings: list[UsernameRoleMapping]
    keycloak_role_mappings: list[KeycloakRoleMapping]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AccessControlConfigPatchRequest(BaseModel):
    username_mappings: list[UsernameRoleMapping] | None = None
    keycloak_role_mappings: list[KeycloakRoleMapping] | None = None


class AccessControlConfigPutRequest(BaseModel):
    username_mappings: list[UsernameRoleMapping] = Field(default_factory=list)
    keycloak_role_mappings: list[KeycloakRoleMapping] = Field(default_factory=list)


class TempCredentialSummary(BaseModel):
    id: str
    username: str
    internal_role: str
    active: bool
    is_expired: bool
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None = None
    created_by_username: str | None = None
    created_by_sub: str | None = None
    revoked_by_username: str | None = None
    revoked_by_sub: str | None = None


class TempCredentialListResponse(BaseModel):
    items: list[TempCredentialSummary]


class TempCredentialCreateRequest(BaseModel):
    username: str = Field(min_length=1)
    internal_role: str = DEFAULT_MAPPING_ROLE
    expires_at: datetime | None = None


class TempCredentialPatchRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1)
    internal_role: str | None = None
    expires_at: datetime | None = None


class TempCredentialCreateResponse(BaseModel):
    credential: TempCredentialSummary
    generated_password: str


def _set_no_store_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _format_response(config: dict) -> AccessControlConfigResponse:
    env_admin_role = resolved_keycloak_admin_role().strip() or None
    return AccessControlConfigResponse(
        keycloak_admin_role=env_admin_role,
        editable_internal_roles=list(EDITABLE_INTERNAL_ROLES),
        default_internal_role=DEFAULT_MAPPING_ROLE,
        fallback_internal_role=FALLBACK_INTERNAL_ROLE,
        username_mappings=[UsernameRoleMapping(**entry) for entry in config.get("username_mappings", [])],
        keycloak_role_mappings=[
            KeycloakRoleMapping(**entry) for entry in config.get("keycloak_role_mappings", [])
        ],
        created_at=config.get("created_at"),
        updated_at=config.get("updated_at"),
    )


@router.get("", response_model=AccessControlConfigResponse)
async def get_admin_users_access_config(
    _: KeycloakUser = Depends(require_permission("admin:general")),
):
    config = await get_access_control_config(force_refresh=True)
    return _format_response(config)


@router.patch("", response_model=AccessControlConfigResponse)
async def patch_admin_users_access_config(
    payload: AccessControlConfigPatchRequest = Body(...),
    _: KeycloakUser = Depends(require_permission("admin:general")),
):
    provided_fields = payload.model_fields_set
    if not provided_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    username_mappings = (
        [entry.model_dump() for entry in payload.username_mappings]
        if "username_mappings" in provided_fields
        else None
    )
    keycloak_role_mappings = (
        [entry.model_dump() for entry in payload.keycloak_role_mappings]
        if "keycloak_role_mappings" in provided_fields
        else None
    )

    try:
        config = await save_access_control_config(
            username_mappings=username_mappings,
            keycloak_role_mappings=keycloak_role_mappings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _format_response(config)


@router.put("", response_model=AccessControlConfigResponse)
async def put_admin_users_access_config(
    payload: AccessControlConfigPutRequest = Body(...),
    _: KeycloakUser = Depends(require_permission("admin:general")),
):
    try:
        config = await save_access_control_config(
            username_mappings=[entry.model_dump() for entry in payload.username_mappings],
            keycloak_role_mappings=[entry.model_dump() for entry in payload.keycloak_role_mappings],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _format_response(config)


@router.get("/temp-credentials", response_model=TempCredentialListResponse)
async def get_admin_temp_credentials(
    _: KeycloakUser = Depends(require_permission("admin:general")),
):
    items = await list_temp_credentials()
    return TempCredentialListResponse(items=[TempCredentialSummary(**item) for item in items])


@router.post("/temp-credentials", response_model=TempCredentialCreateResponse)
async def create_admin_temp_credential(
    response: Response,
    payload: TempCredentialCreateRequest = Body(...),
    user: KeycloakUser = Depends(require_permission("admin:general")),
):
    try:
        credential, generated_password = await create_temp_credential(
            username=payload.username,
            internal_role=payload.internal_role,
            expires_at=payload.expires_at,
            created_by_username=user.username,
            created_by_sub=user.sub,
        )
    except TempCredentialError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _set_no_store_headers(response)
    return TempCredentialCreateResponse(
        credential=TempCredentialSummary(**credential),
        generated_password=generated_password,
    )


@router.patch("/temp-credentials/{credential_id}", response_model=TempCredentialSummary)
async def patch_admin_temp_credential(
    credential_id: str,
    payload: TempCredentialPatchRequest = Body(...),
    _: KeycloakUser = Depends(require_permission("admin:general")),
):
    provided_fields = payload.model_fields_set
    if not provided_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates = {}
    if "username" in provided_fields:
        updates["username"] = payload.username
    if "internal_role" in provided_fields:
        updates["internal_role"] = payload.internal_role
    if "expires_at" in provided_fields:
        updates["expires_at"] = payload.expires_at

    try:
        credential = await update_temp_credential(
            credential_id=credential_id,
            **updates,
        )
    except TempCredentialNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TempCredentialError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return TempCredentialSummary(**credential)


@router.post("/temp-credentials/{credential_id}/revoke", response_model=TempCredentialSummary)
async def revoke_admin_temp_credential(
    credential_id: str,
    user: KeycloakUser = Depends(require_permission("admin:general")),
):
    try:
        credential = await revoke_temp_credential(
            credential_id=credential_id,
            revoked_by_username=user.username,
            revoked_by_sub=user.sub,
        )
    except TempCredentialNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TempCredentialError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return TempCredentialSummary(**credential)


@router.delete("/temp-credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_temp_credential(
    credential_id: str,
    _: KeycloakUser = Depends(require_permission("admin:general")),
):
    try:
        await delete_temp_credential(credential_id=credential_id)
    except TempCredentialNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TempCredentialError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
