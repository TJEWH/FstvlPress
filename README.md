# FstvlPress Website

## Prerequisites

- Node.js, npm
- Python 3.12, [Poetry](https://python-poetry.org/)
- Docker (for MinIO; optional for MongoDB if not installed locally)
- MongoDB running (e.g. `mongod` or Docker)

---

## Development

### 1. MinIO (S3-compatible storage)

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

Create bucket `fstvlpress-assets`:

- **Web:** http://localhost:9001 → Buckets → Create Bucket → `fstvlpress-assets`
- **CLI:** `docker exec minio mc alias set local http://localhost:9000 local-minio local-minio-password` then `docker exec minio mc mb local/fstvlpress-assets`

Make bucket public (so image URLs don’t expire):

```bash
docker exec minio mc anonymous set download local/fstvlpress-assets
```

### 2. Backend

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

API: http://localhost:8000. Optional: copy `.env.example` to `.env` and adjust (MongoDB, OIDC, etc.).

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173.

---

## Production

### Backend

```bash
cd backend
poetry install --no-dev
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Set env vars or `.env`: `MONGO_URI`, `S3_*` or `FTP_*`, `OIDC_*`, `CORS_ORIGINS`, etc.

### Frontend

```bash
cd frontend
npm ci
npm run build
```

Serve the `dist/` folder with your web server (nginx, etc.), or run `npm run preview` for a quick check.

### CI/CD (GitHub Actions)

Automated deployment to Portainer via GitHub Actions. See [docker/DEPLOYMENT.md#cicd-setup](docker/DEPLOYMENT.md#cicd-setup).

### MinIO (production)

Use the same `docker run` as above, or deploy via Docker Compose (`docker/docker-compose.yml`). For production:

- Use strong credentials: `openssl rand -base64 32`
- Set `S3_PUBLIC_BASE_URL` to your domain (e.g. `https://your-domain.com/storage`) so image URLs in MongoDB resolve correctly
- Images are served via nginx proxy at `/storage/`; MinIO API/Console should not be exposed publicly
