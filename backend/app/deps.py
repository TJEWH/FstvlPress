from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.security import verify_keycloak_token, verify_app_token, is_app_token, KeycloakUser
from app.access_control import permissions_for_internal_role
from app.settings import settings

bearer = HTTPBearer(auto_error=False)


# Dev user with all permissions for local development
# Simulates an admin user from Keycloak
DEV_USER = KeycloakUser(
    sub="dev-user-00000000-0000-0000-0000-000000000000",
    username="dev-admin",
    email="dev@localhost",
    email_verified=True,
    name="Development Admin",
    given_name="Development",
    family_name="Admin",
    roles={"admin", "editor"},
    realm_roles={"admin", "editor"},
    client_roles={settings.keycloak_client_id: {"admin", "editor"}},
    groups={"/admins", "/editors"},
    permissions=permissions_for_internal_role("admin_general"),
    internal_role="admin_general",
    access_source="dev_mode",
)

# Service account for API token access (backup server, etc.)
API_TOKEN_USER = KeycloakUser(
    sub="api-token-00000000-0000-0000-0000-000000000000",
    username="api-service",
    email="api@localhost",
    email_verified=True,
    name="API Service Account",
    given_name="API",
    family_name="Service",
    roles={"admin"},
    realm_roles={"admin"},
    client_roles={},
    groups=set(),
    permissions=permissions_for_internal_role("admin_general"),
    internal_role="admin_general",
    access_source="api_token",
)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_api_token: str | None = Header(None, alias="X-API-Token"),
) -> KeycloakUser:
    """
    Get the current authenticated user from Keycloak JWT token or API token.

    Authentication methods (checked in order):
    1. X-API-Token header: Static API token for server-to-server auth (backup server, etc.)
    2. Bearer token: Keycloak JWT token for user auth

    Environment modes:
    - "dev": Returns DEV_USER without validating tokens (frontend dev bypass mode)
    - "local-keycloak": Validates tokens against local Keycloak instance
    - "production" or others: Validates tokens against production Keycloak

    In development mode (environment="dev"), always returns DEV_USER
    without validating tokens - this allows the frontend dev mode to work
    without a real Keycloak instance.

    In local-keycloak mode, tokens are validated against the local Keycloak
    instance configured in the environment. This allows testing the full
    authentication flow locally.
    """
    # Check for static API token first (works in all environments)
    if x_api_token and settings.backup_api_token:
        if x_api_token == settings.backup_api_token:
            return API_TOKEN_USER
        # Invalid API token provided - don't fall through, reject immediately
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )

    # In dev mode, skip all token validation and return dev user
    if settings.environment == "dev":
        return DEV_USER

    # local-keycloak and production: require valid Keycloak token
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if is_app_token(creds.credentials):
        return await verify_app_token(creds.credentials)
    return await verify_keycloak_token(creds.credentials)


async def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_api_token: str | None = Header(None, alias="X-API-Token"),
) -> KeycloakUser | None:
    """
    Optional auth dependency.

    Returns:
    - `None` when no auth credentials are provided
    - `KeycloakUser` when valid credentials are provided

    Invalid credentials still return 401.
    """
    # Check for static API token first (works in all environments)
    if x_api_token and settings.backup_api_token:
        if x_api_token == settings.backup_api_token:
            return API_TOKEN_USER
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )

    # In dev mode, treat all optional auth requests as authenticated dev user
    if settings.environment == "dev":
        return DEV_USER

    # No credentials provided -> anonymous/public request
    if creds is None:
        return None

    if creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if is_app_token(creds.credentials):
        return await verify_app_token(creds.credentials)
    return await verify_keycloak_token(creds.credentials)


def require_role(*required: str):
    """
    Dependency that requires the user to have ALL specified roles.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
        async def admin_only(): ...
    """

    async def _dep(user: KeycloakUser = Depends(get_current_user)) -> KeycloakUser:
        missing = set(required) - user.roles
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required roles: {', '.join(sorted(missing))}",
            )
        return user

    return _dep


def require_any_role(*required: str):
    """
    Dependency that requires the user to have AT LEAST ONE of the specified roles.

    Usage:
        @router.get("/content", dependencies=[Depends(require_any_role("admin", "editor"))])
        async def editors_or_admins(): ...
    """

    async def _dep(user: KeycloakUser = Depends(get_current_user)) -> KeycloakUser:
        if not set(required) & user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(sorted(required))}",
            )
        return user

    return _dep


def require_permission(*required: str):
    """
    Dependency that requires the user to have ALL specified permissions.

    Permissions are derived from Keycloak roles via the role-to-permission mapping
    in security.py, or from a custom 'permissions' claim in the token.

    Usage:
        @router.post("/upload", dependencies=[Depends(require_permission("assets:write"))])
        async def upload_file(): ...
    """

    async def _dep(user: KeycloakUser = Depends(get_current_user)) -> KeycloakUser:
        missing = set(required) - user.permissions
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(sorted(missing))}",
            )
        return user

    return _dep


def require_any_permission(*required: str):
    """
    Dependency that requires the user to have AT LEAST ONE of the specified permissions.

    Usage:
        @router.get("/data", dependencies=[Depends(require_any_permission("data:read", "data:admin"))])
        async def read_data(): ...
    """

    async def _dep(user: KeycloakUser = Depends(get_current_user)) -> KeycloakUser:
        if not set(required) & user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of permissions: {', '.join(sorted(required))}",
            )
        return user

    return _dep


def require_group(*required: str):
    """
    Dependency that requires the user to be a member of ALL specified Keycloak groups.

    Note: Requires the 'groups' claim to be included in the Keycloak token.
    Configure a Group Membership mapper in your Keycloak client.

    Usage:
        @router.get("/team", dependencies=[Depends(require_group("/team-leads"))])
        async def team_leads_only(): ...
    """

    async def _dep(user: KeycloakUser = Depends(get_current_user)) -> KeycloakUser:
        missing = set(required) - user.groups
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required group membership: {', '.join(sorted(missing))}",
            )
        return user

    return _dep
