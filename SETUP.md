# FstvlPress Development Setup

This guide provides an automated setup script to get the development environment running quickly.

## Quick Start

```bash
chmod +x setup.sh
./setup.sh
```

**On Windows:** Run the script in **Git Bash** or **WSL**. The repo uses LF line endings for `setup.sh` (via `.gitattributes`); if you see no output, re-checkout with LF: `git checkout -- setup.sh` or clone with `git config core.autocrlf input`. Windows is not officially supported; you can bypass the dependency check with `./setup.sh --skip-deps` to run the rest of the setup (Docker, MongoDB, MinIO, etc. still required).

## What the Setup Script Does

1. **Checks Prerequisites** - Verifies Node.js, npm, Python 3.12+, Poetry, and Docker are installed
2. **Starts MongoDB** - Launches a MongoDB container via Docker
3. **Restores Database** - Imports the backup from `backend/dummy_data/mongo`
4. **Starts MinIO** - Launches MinIO (S3-compatible storage) and creates the required bucket
5. **Installs Dependencies** - Runs `poetry install` and `npm install`
6. **Starts Services** - Launches backend (port 8080) and frontend (port 5173)

## Prerequisites

The script will check for these and provide installation instructions if missing:

| Tool | Required Version | Installation |
|------|------------------|--------------|
| Node.js | 18+ | https://nodejs.org or `brew install node` |
| npm | (comes with Node.js) | - |
| Python | 3.12+ | https://python.org or `brew install python@3.12` |
| Poetry | latest | `curl -sSL https://install.python-poetry.org \| python3 -` |
| Docker | latest | https://docker.com or `brew install --cask docker` |
| MongoDB Tools | latest | `brew tap mongodb/brew && brew install mongodb-database-tools` |

## Manual Setup (if script fails)

### 1. Start MongoDB

```bash
docker run -d \
  --name mongodb \
  -p 27017:27017 \
  -v mongodb-data:/data/db \
  mongo:7
```

### 2. Restore Database

```bash
mongorestore --uri="mongodb://localhost:27017" backend/dummy_data/mongo
```

### 3. Start MinIO

> **Security:** The credentials below are for local dev only. Never reuse them in production.

```bash
docker run -d \
  --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -v minio-data:/data \
  -e MINIO_ROOT_USER=local-minio \
  -e MINIO_ROOT_PASSWORD=local-minio-password \
  minio/minio server /data --console-address ":9001"
```

### 4. Create MinIO Bucket

```bash
# Wait for MinIO to start
sleep 5

# Create bucket and set public access
docker exec minio mc alias set local http://localhost:9000 local-minio local-minio-password
docker exec minio mc mb local/fstvlpress-assets --ignore-existing
docker exec minio mc anonymous set download local/fstvlpress-assets
```

### 5. Start Backend

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload --port 8080
```

### 6. Start Frontend

```bash
cd frontend
npm install
VITE_API_BASE=/api/v1 npm run dev
```

## Access Points

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8080 |
| API Docs | http://localhost:8080/docs |
| MinIO Console | http://localhost:9001 (local-minio/local-minio-password) |

## Keycloak Authentication (Production)

The backend is prepared for Keycloak SSO integration. In development mode (`ENVIRONMENT=dev`), authentication is bypassed with a dev user that has full permissions.

### Keycloak Configuration

For production deployment, configure these environment variables in `backend/.env`:

```bash
ENVIRONMENT=production
KEYCLOAK_SERVER_URL=https://your-keycloak-server.com
KEYCLOAK_REALM=your-realm
KEYCLOAK_CLIENT_ID=fstvlpress-api
KEYCLOAK_CLIENT_SECRET=  # Only for confidential clients
```

### Keycloak Client Setup

When setting up the Keycloak client:

1. **Create a new client** in your Keycloak realm with:
   - Client ID: `fstvlpress-api`
   - Client Protocol: `openid-connect`
   - Access Type: `confidential` (for backend) or `public` (for frontend SPA)

2. **Configure mappers** to include required claims in tokens:
   - `realm_access.roles` - Realm-level roles (included by default)
   - `resource_access` - Client-specific roles (included by default)
   - `groups` - Add a "Group Membership" mapper if using group-based access

3. **Define roles** in Keycloak that map to application permissions:
   - `admin` - Full access (all permissions)
   - `editor` - Content management (read/write, no publish)
   - `viewer` - Read-only access

### Role to Permission Mapping

The backend automatically maps Keycloak roles to fine-grained permissions:

| Role | Permissions |
|------|-------------|
| `admin` | assets:*, pages:*, sections:*, content:* (including publish) |
| `editor` | assets:*, pages:*, sections:*, content:read/write |
| `viewer` | assets:read, pages:read, sections:read, content:read |

This mapping can be customized in `backend/app/security.py` in the `_map_roles_to_permissions()` function.

### Frontend OIDC Configuration

The frontend uses `keycloak-js` for OIDC authentication. On localhost, authentication is bypassed with a mock admin user.

For production deployment, the frontend public settings are baked into the Docker image at build time via these environment variables:

```bash
VITE_APP_DISPLAY_NAME=FstvlPress
VITE_OIDC_URL=https://your-keycloak-server.com/auth
VITE_OIDC_REALM_NAME=your-realm
VITE_OIDC_CLIENT_ID=fstvlpress-web
```

**OIDC Client Setup:**

1. Create a **public** client in Keycloak:
   - Client ID: `fstvlpress-web`
   - Access Type: `public`
   - Standard Flow Enabled: `ON`
   - Valid Redirect URIs: `https://your-production-url/*`
   - Web Origins: `https://your-production-url`

2. The frontend will automatically:
   - Redirect to Keycloak login when user visits `/login`
   - Extract user info from the token
   - Pass the access token to API requests
   - Handle token refresh automatically

**Development Mode:**

When running on `localhost` or `127.0.0.1`, authentication is bypassed automatically. A mock admin user is created with full permissions.

## Stopping Services

```bash
# Stop all containers
docker stop mongodb minio

# Or remove them completely
docker rm -f mongodb minio
```

## Troubleshooting

### Port already in use
```bash
# Check what's using a port
lsof -i :27017  # MongoDB
lsof -i :9000   # MinIO
lsof -i :8080   # Backend
lsof -i :5173   # Frontend
```

### Reset everything
```bash
docker rm -f mongodb minio
docker volume rm mongodb-data minio-data
./setup.sh
```
