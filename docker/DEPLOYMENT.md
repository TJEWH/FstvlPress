# FstvlPress - Production Deployment Guide

This guide explains how to deploy the FstvlPress stack using Docker and Portainer.

## Stack Components

| Service | Image | Description |
|---------|-------|-------------|
| **frontend** | nginx:1.27-alpine | Vue.js SPA served by nginx |
| **backend** | python:3.12-slim | FastAPI application |
| **mongodb** | mongo:7.0 | Document database |
| **minio** | minio/minio:latest | S3-compatible object storage |
| **keycloak** | keycloak:24.0 | Authentication server |
| **keycloak-db** | postgres:16-alpine | PostgreSQL for Keycloak |

## Resource Requirements

All services are configured with:
- **Reservations**: 0.0001 CPU, 128MB RAM (minimal footprint)
- **Limits**: Vary by service (256MB - 1GB RAM)

## Prerequisites

1. Docker Engine 24.0+ with Docker Compose v2
2. For Portainer: Portainer Business or Community Edition
3. Domain names configured (or local development setup)
4. SSL certificates (for production)

## Quick Start - Local Development

```bash
# Clone and navigate to project
cd fstvlpress

# Copy environment file
cp docker/.env.example docker/.env

# Edit .env with your settings
nano docker/.env

# Build and start all services (from project root)
docker-compose -f docker/docker-compose.yml up --build -d

# Or from docker directory
cd docker
docker-compose up --build -d

# View logs
docker-compose -f docker/docker-compose.yml logs -f
```

## Deployment Options

### Option 1: Docker Compose (Standard)

```bash
# Production deployment (without override file, from project root)
docker-compose -f docker/docker-compose.yml up -d

# With custom env file
docker-compose -f docker/docker-compose.yml --env-file docker/.env.prod up -d
```

### Option 2: Portainer Stack Deployment

1. **Build and push images** to your registry:
   ```bash
   # Build images (from project root)
   docker-compose -f docker/docker-compose.yml build

   # Tag for registry. Use prod for production or dev for development.
   docker tag fstvlpress-frontend:latest your-registry/fstvlpress-frontend:prod
   docker tag fstvlpress-backend:latest your-registry/fstvlpress-backend:prod

   # Push to registry
   docker push your-registry/fstvlpress-frontend:prod
   docker push your-registry/fstvlpress-backend:prod
   ```

2. **In Portainer**:
   - Navigate to **Stacks** → **Add Stack**
   - Choose **Web editor**
   - Paste contents of `docker/portainer-stack.yml`
   - Set **Environment variables** (see below)
   - Click **Deploy the stack**

### Option 3: Portainer with Git Repository

1. In Portainer: **Stacks** → **Add Stack** → **Repository**
2. Enter your Git repository URL
3. Set **Compose path**: `docker/portainer-stack.yml`
4. Configure environment variables
5. Enable automatic updates (optional)

### Option 4: CI/CD with GitHub Actions

Automated deployment via GitHub Actions. See [CI/CD Setup](#cicd-setup) below.

## CI/CD Setup

GitHub Actions workflows build images and push environment-specific tags to GitHub Container Registry. Do not point hosted Portainer stacks at a shared `latest` tag.

### Development (`deploy-development.yml`)

- **Triggers**:
  - Push to `dev` branch
  - Manual (`workflow_dispatch`)
- **Builds**: Frontend, Backend when their source files changed; manual runs build both
- **Registry**: `ghcr.io/<owner>/`
- **Tags**: `dev`, `dev-<commit-sha>`
- **Webhooks**: `PORTAINER_WEBHOOK_FRONTEND_DEV`, `PORTAINER_WEBHOOK_BACKEND_DEV`

### Production (`deploy-production.yml`)

- **Triggers**:
  - Push to `main` branch
- **Builds**: Frontend, Backend
- **Registry**: `ghcr.io/<owner>/`
- **Tags**: `prod`, `prod-<commit-sha>`
- **Webhooks**: `PORTAINER_WEBHOOK_FRONTEND_PROD`, `PORTAINER_WEBHOOK_BACKEND_PROD`

### Images

| Image | URL |
|-------|-----|
| Development frontend | `ghcr.io/<owner>/fstvlpress-frontend:dev` |
| Development backend | `ghcr.io/<owner>/fstvlpress-backend:dev` |
| Production frontend | `ghcr.io/<owner>/fstvlpress-frontend:prod` |
| Production backend | `ghcr.io/<owner>/fstvlpress-backend:prod` |

### GitHub Secrets (optional)

| Secret | Description |
|--------|-------------|
| `PORTAINER_WEBHOOK_FRONTEND_DEV` | Development frontend service webhook |
| `PORTAINER_WEBHOOK_BACKEND_DEV` | Development backend service webhook |
| `PORTAINER_WEBHOOK_FRONTEND_PROD` | Production frontend service webhook |
| `PORTAINER_WEBHOOK_BACKEND_PROD` | Production backend service webhook |

### Portainer Stack Configuration

`docker/portainer-stack.yml` defaults `REGISTRY` to a placeholder and requires `TAG`. Set both explicitly before deploying so Portainer pulls the intended images.

Recommended:
- Set `REGISTRY=ghcr.io/<owner>/` explicitly in Portainer
- Set `TAG=dev` in the development stack
- Set `TAG=prod` in the production stack
- Set `TAG` to an environment-prefixed build tag (for example `dev-<commit-sha>` or `prod-<commit-sha>`) when debugging/recovering
- In Portainer, enable image pulling on redeploy/service update

### Portainer Webhook Setup (Optional)

To auto-redeploy when new images are pushed:

1. In Portainer: **Stacks** → your stack → **Webhooks**
2. Click **Add webhook**
3. Copy the webhook URL
4. In GitHub: **Settings** → **Secrets and variables** → **Actions**
5. Add the matching GitHub secret with the webhook URL:
   - Development: `PORTAINER_WEBHOOK_FRONTEND_DEV` and `PORTAINER_WEBHOOK_BACKEND_DEV`
   - Production: `PORTAINER_WEBHOOK_FRONTEND_PROD` and `PORTAINER_WEBHOOK_BACKEND_PROD`

## Environment Variables

Configure these in Portainer or your `.env` file:

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MONGO_ROOT_PASSWORD` | MongoDB admin password | `secure_password_123` |
| `MINIO_ROOT_USER` | MinIO admin username | (no default in production) |
| `MINIO_ROOT_PASSWORD` | MinIO admin password | `secure_password_456` |
| `OIDC_URL` | Frontend OIDC base URL | `https://login.example.com/auth` |
| `OIDC_REALM_NAME` | Frontend OIDC realm name | `FstvlPress` |
| `OIDC_CLIENT_ID` | Frontend SPA client ID | `fstvlpress-web` |
| `APP_TOKEN_SECRET` | Backend app-token signing secret | `secure_password_app` |
| `KEYCLOAK_ADMIN_PASSWORD` | Keycloak admin password | `secure_password_789` |
| `KC_DB_PASSWORD` | Keycloak DB password | `secure_password_abc` |

**Security:** Generate strong passwords with `openssl rand -base64 32`. Never use defaults (`minioadmin`, `changeme`) in production.

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `S3_ACCESS_KEY_ID` | (uses root) | Service account for backend (least-privilege) |
| `S3_SECRET_ACCESS_KEY` | (uses root) | Secret for service account |
| `REGISTRY` | `ghcr.io/<owner>/` | Image registry prefix for frontend/backend images |
| `TAG` | `prod` in `.env.example` | Docker image tag; use `dev` for development and `prod` for production |
| `FRONTEND_PORT` | `80` | Frontend exposed port |
| `KEYCLOAK_PORT` | `8080` | Keycloak exposed port |
| `MONGO_DB` | `2026` | MongoDB database name |
| `OIDC_CLIENT_SECRET` | (empty) | Optional frontend nginx token-proxy client secret |
| `KEYCLOAK_ADMIN_ROLES` | (empty) | Optional comma-separated roles that grant internal admin access |
| `KC_HOSTNAME` | `localhost` | Keycloak external hostname |
| `CORS_ORIGINS` | (see .env.example) | Allowed CORS origins |

## Post-Deployment Setup

### 1. Create MinIO Bucket

The `minio-setup` service automatically creates the bucket. If manual setup is needed:

```bash
# Access MinIO console at http://localhost:9001
# Or use mc CLI:
docker exec -it fstvlpress-minio mc alias set local http://localhost:9000 minioadmin minioadmin
docker exec -it fstvlpress-minio mc mb local/fstvlpress-assets
docker exec -it fstvlpress-minio mc anonymous set download local/fstvlpress-assets
```

### 2. Configure Keycloak

Configure the frontend with your Keycloak/OIDC provider via environment variables.

Create a browser client in your realm:
- **fstvlpress-web** (public client for SPA)
  - Access Type: public
  - Valid Redirect URIs: `https://your-domain.com/*`
  - Web Origins: `https://your-domain.com`

The backend does not need Keycloak URL, realm, client ID, or client secret
deployment variables. It validates Keycloak access tokens against the issuer
carried by the token and uses `KEYCLOAK_ADMIN_ROLES` only for access mapping.

Note: If running your own Keycloak instance (included in docker-compose.yml), access it at `http://localhost:8080` and create a realm first.

### 3. Restore MongoDB Data (Optional)

```bash
# Copy backup to container
docker cp backend/dummy_data/mongo/2026 fstvlpress-mongodb:/tmp/backup

# Restore
docker exec fstvlpress-mongodb mongorestore --db 2026 /tmp/backup
```

## Networking

### Internal Network

All services communicate via the `fstvlpress-network` bridge network:
- Frontend → Backend: `http://backend:8000`
- Backend → MongoDB: `mongodb://mongodb:27017`
- Backend → MinIO: `http://minio:9000`
- Backend → Keycloak: `http://keycloak:8080`

### Exposed Ports (Default)

| Port | Service |
|------|---------|
| 80 | Frontend (nginx) |
| 8080 | Keycloak |

MinIO (9000/9001) is not exposed in production (Portainer stack). Images are served via nginx `/storage/` proxy. For admin access, use `docker exec` or port-forward to localhost.

## Health Checks

All services have health checks configured:

```bash
# Check service health (from project root)
docker-compose -f docker/docker-compose.yml ps

# View health status
docker inspect --format='{{.State.Health.Status}}' fstvlpress-frontend
```

## Scaling

To scale services in Portainer:
1. Navigate to **Stacks** → **your-stack**
2. Click on the service
3. Adjust **Replicas** count
4. Click **Update**

Note: MongoDB and MinIO should remain single-replica unless configured for clustering.

## Troubleshooting

### Startup Order / "Wrong order" concerns

When deployed as a Portainer stack (Docker Swarm), `depends_on` is not enforced on
a full stack reboot; tasks start in parallel. Services must tolerate peers
coming up later.

Mitigations in this repo:
- Frontend nginx resolves upstreams at request time (`resolver 127.0.0.11` and
  variable `proxy_pass` in `frontend/docker/nginx.conf.template`) so the frontend
  entrypoint does not need a wait-for-backend shell loop.
- `docker/portainer-stack.yml` lists `depends_on` (short form) and defines
  backend before frontend for readability; backend uses `restart_policy` until
  MongoDB and MinIO are reachable.
- Rolling updates use `order: start-first` in `docker/portainer-stack.yml`.
- CI/CD webhooks trigger backend rollout before frontend rollout.

### Services not starting

```bash
# Check logs (from project root)
docker-compose -f docker/docker-compose.yml logs backend
docker-compose -f docker/docker-compose.yml logs keycloak

# Check resource usage
docker stats
```

### Keycloak startup issues

Keycloak needs time to initialize (up to 2 minutes). Check:
```bash
docker-compose -f docker/docker-compose.yml logs -f keycloak
```

### MongoDB connection issues

Ensure MongoDB is healthy before backend starts:
```bash
docker exec fstvlpress-mongodb mongosh --eval "db.adminCommand('ping')"
```

### MinIO bucket not accessible

```bash
# Check bucket exists
docker exec fstvlpress-minio mc ls local/

# Recreate bucket with public access
docker exec fstvlpress-minio mc mb --ignore-existing local/fstvlpress-assets
docker exec fstvlpress-minio mc anonymous set download local/fstvlpress-assets
```

### Images not loading (404 on /storage/*)

1. Ensure `S3_PUBLIC_BASE_URL` matches your domain (e.g. `https://your-domain.com/storage` or `/storage` for same-origin)
2. Verify `S3_BUCKET` is set consistently for backend, minio-setup, and frontend (nginx proxies `/storage/` to the configured bucket)

### Frontend loads, but new API routes return 404

Symptoms:
- `GET /api/v1/pages/public/landing` returns 404
- `GET /api/v1/sitemap/redirects/resolve?path=/` returns 404
- `GET /openapi.json` lacks routes such as `/api/v1/auth/app-token`, `/api/v1/pages/public/{slug:path}`, `/api/v1/sitemap/redirects/resolve`

This indicates the deployed backend image is older than the frontend/API contract.

Checks:
```bash
curl -sS https://<your-domain>/openapi.json | grep -q '/api/v1/pages/public/' && echo "modern API" || echo "legacy API"
docker service inspect --format '{{.Spec.TaskTemplate.ContainerSpec.Image}}' <stack>_backend
```

Recovery:
1. Ensure Portainer stack env uses `REGISTRY=ghcr.io/<owner>/` (or your registry)
2. Set `TAG` to the expected build tag (prefer commit SHA during incident recovery)
3. Redeploy/update backend with image pull enabled
4. Recheck `/openapi.json` before validating frontend behavior

### 504 Gateway Time-out on long integration crawler fetches

If long-running crawler fetch requests work locally but fail in production with nginx `504 Gateway Time-out`, increase frontend API proxy timeouts:

```env
API_PROXY_READ_TIMEOUT=900s
API_PROXY_SEND_TIMEOUT=900s
API_PROXY_CONNECT_TIMEOUT=75s
```

Then redeploy the `frontend` service so the nginx config is regenerated.

If you run an additional external reverse proxy (for example Traefik, nginx-proxy, or Cloudflare), align its upstream timeout as well. The smallest timeout in the request chain wins.

### Large backup import upload fails in production

Backup restore uploads use `/api/v1/backup/import`, which has a dedicated frontend nginx location. For large ZIPs, keep these frontend service variables at least as high as your backup size and expected import duration:

```env
BACKUP_UPLOAD_MAX_BODY_SIZE=1g
BACKUP_PROXY_READ_TIMEOUT=3600s
BACKUP_PROXY_SEND_TIMEOUT=3600s
BACKUP_CLIENT_BODY_TIMEOUT=3600s
```

Redeploy the `frontend` service after changing them so `/etc/nginx/nginx.conf` is regenerated. The backup route streams request bodies to the backend (`proxy_request_buffering off`) to avoid buffering a 100s-of-MB ZIP inside the nginx container.

If the site is behind another proxy or CDN, configure that layer too. A smaller outer `client_max_body_size`, request body limit, or upstream timeout will still reject a 250 MB backup before it reaches this app.

### Font cache via browser

Font caching is client-assisted from Admin → Design → Font Families:

1. Run **Health Check** for a family.
2. If Google CSS is available in the admin browser, click **Cache via browser**.
3. The browser downloads Google assets and uploads them to backend storage.

The backend does not fetch Google Fonts directly anymore, so proxy/TLS setup inside the backend container is no longer required for font caching.

Public rendering is cache-only for remote families: if a family is not cached, configured fallback fonts are used.

## MinIO Security

- **Credentials:** Use strong passwords. `minio-setup` creates the bucket; provide `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` via env.
- **Service account (optional):** Set `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` to create a least-privilege access key for the backend (bucket Put/Get/Delete only). Otherwise the backend uses root credentials.
- **Network:** MinIO API/Console are not exposed in production. Images are served via nginx `/storage/` proxy.
- **Media upload limits:** Backend enforces 20 MB max file size and restricts content types (images, PDF).

## Backup Strategy

### MongoDB Backup

```bash
# Create backup
docker exec fstvlpress-mongodb mongodump --out /data/backup

# Copy to host
docker cp fstvlpress-mongodb:/data/backup ./mongo_backup_$(date +%Y%m%d)
```

### MinIO Backup

```bash
# Sync to local directory
docker exec fstvlpress-minio mc mirror local/fstvlpress-assets /data/backup

# Or use mc from host
mc mirror minio/fstvlpress-assets ./minio_backup_$(date +%Y%m%d)
```

## SSL/TLS Configuration

For production, use a reverse proxy (Traefik, nginx-proxy, or Cloudflare) to handle SSL:

1. **Traefik** (recommended with Portainer):
   - Add labels to services for automatic SSL
   - Configure Let's Encrypt

2. **External Load Balancer**:
   - Terminate SSL at load balancer
   - Forward to container ports

## Monitoring

### Prometheus Metrics

Keycloak exposes metrics at `/metrics` when `KC_METRICS_ENABLED=true`.

### Log Aggregation

Configure Docker logging driver for centralized logging:

```yaml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```
