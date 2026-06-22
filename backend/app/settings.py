from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field

# Load .env file into os.environ so dynamic keys (like integration API keys) are available
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Allow extra env vars (e.g., integration API keys like PRETALX_API_KEY)
    )

    app_name: str = "FstvlPress 2026"
    site_slug: str = "fstvlpress"  # Short identifier for backup filenames
    environment: str = "dev"  # dev | local-keycloak | production
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "2026"

    # Keycloak Configuration
    keycloak_server_url: str = ""
    keycloak_realm: str = ""
    keycloak_client_id: str = ""
    keycloak_client_secret: str = ""  # Only needed for confidential clients
    keycloak_jwt_audience: str = "account"  # Expected JWT audience claim

    # Legacy comma-separated Keycloak roles that resolve to internal admin_general.
    # Kept for deployment compatibility (for example KEYCLOAK_ADMIN_ROLES in docker envs).
    keycloak_admin_roles: str = ""
    
    # Preferred single Keycloak role that always resolves to internal admin_general.
    # Takes precedence over keycloak_admin_roles when set.
    keycloak_admin_role: str = ""
    
    # Optional: restrict admin access to specific usernames (comma-separated).
    # If set, only these usernames will have admin rights (takes precedence over roles).
    keycloak_admin_users: str = ""

    # Optional: Override auto-constructed URLs if needed
    keycloak_issuer_override: str | None = None
    keycloak_jwks_url_override: str | None = None

    @computed_field
    @property
    def keycloak_issuer(self) -> str:
        """Keycloak issuer URL (realm URL)."""
        if self.keycloak_issuer_override:
            return self.keycloak_issuer_override.rstrip("/")
        return f"{self.keycloak_server_url.rstrip('/')}/realms/{self.keycloak_realm}"

    @computed_field
    @property
    def keycloak_jwks_url(self) -> str:
        """Keycloak JWKS endpoint for token verification."""
        if self.keycloak_jwks_url_override:
            return self.keycloak_jwks_url_override
        return f"{self.keycloak_issuer}/protocol/openid-connect/certs"

    @computed_field
    @property
    def keycloak_token_url(self) -> str:
        """Keycloak token endpoint (for client credentials or token exchange)."""
        return f"{self.keycloak_issuer}/protocol/openid-connect/token"

    @computed_field
    @property
    def keycloak_auth_url(self) -> str:
        """Keycloak authorization endpoint (for OAuth2 flows)."""
        return f"{self.keycloak_issuer}/protocol/openid-connect/auth"

    @computed_field
    @property
    def keycloak_userinfo_url(self) -> str:
        """Keycloak userinfo endpoint."""
        return f"{self.keycloak_issuer}/protocol/openid-connect/userinfo"

    @computed_field
    @property
    def keycloak_logout_url(self) -> str:
        """Keycloak logout endpoint."""
        return f"{self.keycloak_issuer}/protocol/openid-connect/logout"

    # Storage
    storage_backend: str = "s3"  # "s3" or "ftp"

    # S3 (MinIO/AWS)
    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket: str = "fstvlpress-assets"
    s3_public_base_url: str | None = (
        "http://localhost:9000/fstvlpress-assets"  # Direct MinIO URL for local dev
    )

    # FTP (optional)
    ftp_host: str = "localhost"
    ftp_port: int = 21
    ftp_user: str = "user"
    ftp_password: str = ""
    ftp_base_dir: str = "/fstvlpress-assets"
    ftp_public_base_url: str = "https://static.example.com/fstvlpress-assets"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"

    # Static API token for backup server access (server-to-server auth)
    # Generate a secure token with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    backup_api_token: str = ""

    # Compact app token (issued by backend after successful auth check)
    # Used to avoid very large Keycloak role-heavy JWTs on every API request.
    app_token_secret: str = ""
    app_token_ttl_seconds: int = 43200  # 12 hours

    # Temp credential login protection (best-effort in-process rate limiting)
    temp_login_rate_limit_window_seconds: int = 300
    temp_login_max_attempts_per_ip: int = 30
    temp_login_max_attempts_per_username: int = 8
    temp_login_max_attempts_per_ip_username: int = 5


settings = Settings()
