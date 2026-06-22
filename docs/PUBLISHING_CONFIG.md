# Public Release Configuration

This repository is safe to publish only after replacing deployment-specific values with your own environment variables, GitHub variables, and GitHub secrets. Do not commit real secrets to the repository.

## GitHub Actions Variables

Set these under **Repository settings -> Secrets and variables -> Actions -> Variables**:

| Variable | Used by | Replaces |
| --- | --- | --- |
| `APP_DISPLAY_NAME` | Frontend Docker build fallback and runtime config | Hardcoded browser title/header/footer project name |
| `OIDC_URL` | Frontend Docker build and runtime OIDC config | Hardcoded production OIDC URL |
| `OIDC_REALM_NAME` | Frontend Docker build and runtime OIDC config | Hardcoded production realm |
| `OIDC_CLIENT_ID` | Frontend public SPA client | Hardcoded frontend OIDC client ID |

## GitHub Actions Secrets

Set these under **Repository settings -> Secrets and variables -> Actions -> Secrets**:

| Secret | Used by |
| --- | --- |
| `PORTAINER_WEBHOOK_FRONTEND` | Development frontend deployment webhook |
| `PORTAINER_WEBHOOK_BACKEND` | Development backend deployment webhook |
| `PORTAINER_WEBHOOK_FRONTEND_PROD` | Production frontend deployment webhook |
| `PORTAINER_WEBHOOK_BACKEND_PROD` | Production backend deployment webhook |

`GITHUB_TOKEN` is provided by GitHub Actions automatically for GHCR pushes.

## Docker And Portainer Environment

Use `docker/.env.example` as the template for local Docker Compose or Portainer stack variables.

| Variable | Purpose |
| --- | --- |
| `REGISTRY` | Image registry prefix, for example `ghcr.io/your-org/` |
| `TAG` | Image tag to deploy |
| `FRONTEND_PORT` | Public frontend port |
| `APP_DISPLAY_NAME` | Public display name shown in the browser title, header, and footer |
| `OIDC_URL` | Public OIDC issuer base URL used by the browser app |
| `OIDC_REALM_NAME` | Public OIDC realm name used by the browser app |
| `OIDC_CLIENT_ID` | Public SPA client ID |
| `OIDC_CLIENT_SECRET` | Optional server-side token proxy secret; never exposed to browser |
| `KEYCLOAK_SERVER_URL` | Backend Keycloak/OIDC base URL |
| `KEYCLOAK_REALM` | Backend realm name |
| `KEYCLOAK_CLIENT_ID` | Backend confidential client ID |
| `KEYCLOAK_CLIENT_SECRET` | Backend confidential client secret |
| `KEYCLOAK_ADMIN_ROLES` | Optional comma-separated admin roles |
| `MONGO_DB` | MongoDB database name |
| `MONGO_ROOT_USER` | MongoDB root username |
| `MONGO_ROOT_PASSWORD` | MongoDB root password |
| `MINIO_ROOT_USER` | MinIO root username |
| `MINIO_ROOT_PASSWORD` | MinIO root password |
| `MINIO_API_PORT` | Local MinIO API port |
| `MINIO_CONSOLE_PORT` | Local MinIO console port |
| `S3_BUCKET` | Asset bucket name |
| `S3_ACCESS_KEY_ID` | Optional least-privilege backend S3 access key |
| `S3_SECRET_ACCESS_KEY` | Optional least-privilege backend S3 secret key |
| `S3_REGION` | S3 region |
| `S3_PUBLIC_BASE_URL` | Public asset URL, usually `/storage` or your CDN URL |
| `KEYCLOAK_ADMIN` | Included Keycloak admin username |
| `KEYCLOAK_ADMIN_PASSWORD` | Included Keycloak admin password |
| `KC_DB_USER` | Included Keycloak database username |
| `KC_DB_PASSWORD` | Included Keycloak database password |
| `KC_HOSTNAME` | Included Keycloak external hostname |
| `KEYCLOAK_PORT` | Included Keycloak public port |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |

Timeout variables in `docker/.env.example` can usually keep their defaults: `API_PROXY_READ_TIMEOUT`, `API_PROXY_SEND_TIMEOUT`, `API_PROXY_CONNECT_TIMEOUT`, `BACKUP_UPLOAD_MAX_BODY_SIZE`, `BACKUP_PROXY_READ_TIMEOUT`, `BACKUP_PROXY_SEND_TIMEOUT`, and `BACKUP_CLIENT_BODY_TIMEOUT`.

## Frontend Local Development

For local Vite development, set this in a local, ignored frontend env file if you want the same display name without Docker runtime config:

| Variable | Purpose |
| --- | --- |
| `VITE_APP_DISPLAY_NAME` | Build-time fallback for the browser title, header, and footer |

Docker and GitHub Actions derive `VITE_APP_DISPLAY_NAME` from `APP_DISPLAY_NAME`; set `APP_DISPLAY_NAME` in deployment environments.

## Backend `.env`

Copy `backend/.env.example` to `backend/.env` for local or direct backend deployment. Required production values are:

| Variable | Purpose |
| --- | --- |
| `APP_NAME` | Display/application name |
| `SITE_SLUG` | Backup filename prefix |
| `ENVIRONMENT` | `dev`, `local-keycloak`, or `production` |
| `MONGO_URI` | MongoDB connection URI |
| `MONGO_DB` | MongoDB database name |
| `KEYCLOAK_SERVER_URL` | Backend Keycloak/OIDC base URL |
| `KEYCLOAK_REALM` | Backend realm name |
| `KEYCLOAK_CLIENT_ID` | Backend confidential client ID |
| `KEYCLOAK_CLIENT_SECRET` | Backend confidential client secret |
| `STORAGE_BACKEND` | `s3` or `ftp` |
| `S3_ENDPOINT_URL` | S3/MinIO endpoint |
| `S3_ACCESS_KEY_ID` | S3/MinIO access key |
| `S3_SECRET_ACCESS_KEY` | S3/MinIO secret key |
| `S3_BUCKET` | Asset bucket name |
| `S3_PUBLIC_BASE_URL` | Public asset base URL |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `BACKUP_API_TOKEN` | Server-to-server backup API token |
| `APP_TOKEN_SECRET` | Backend-issued app-token signing secret |

## Local Keycloak Fixture

The local-only Keycloak fixture uses generic demo values:

| Variable | Value |
| --- | --- |
| `KEYCLOAK_REALM` | `FstvlPressLocal` |
| `VITE_LOCAL_KEYCLOAK_REALM` | `FstvlPressLocal` |
| `VITE_LOCAL_KEYCLOAK_CLIENT_ID` | `fstvlpress-web` |
| `KEYCLOAK_CLIENT_ID` | `fstvlpress-api` |
| `KEYCLOAK_CLIENT_SECRET` | `local-dev-client-secret` |

The sample local users and passwords are for local development only and must not be reused in any hosted environment.
