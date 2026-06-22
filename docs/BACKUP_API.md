# Backup API Documentation

This document describes how to use the backup API for automated backups.

## Environment Variables

### Backend Configuration

Add the following to your backend `.env` file:

```bash
# Generate a secure token with: python -c "import secrets; print(secrets.token_urlsafe(32))"
BACKUP_API_TOKEN=your_secure_token_here
```

This token enables server-to-server authentication for backup operations without requiring Keycloak OAuth.

## Authentication

The backup API supports two authentication methods:

| Method | Header | Use Case |
|--------|--------|----------|
| API Token | `X-API-Token: <token>` | Backup servers, cron jobs, automation |
| Bearer Token | `Authorization: Bearer <jwt>` | Interactive users via Keycloak |

**Note:** In `environment=dev` mode, no authentication is required.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/backup/info` | GET | Get backup size preview |
| `/api/v1/backup/export` | GET | Download full backup |
| `/api/v1/backup/export/incremental` | GET | Download incremental backup |
| `/api/v1/backup/import` | POST | Import/restore backup |
| `/api/v1/backup/last-backup` | GET | Get last backup timestamp |
| `/api/v1/backup/log-export` | POST | Log successful export |

### Query Parameters

**`/api/v1/backup/export`**
- `include_media` (bool, default: true) - Include media files in backup

**`/api/v1/backup/export/incremental`**
- `since` (string, required) - ISO datetime, only include changes after this time
- `include_media` (bool, default: true) - Include new media files

**`/api/v1/backup/info`**
- `since` (string, optional) - Preview incremental backup size

**`/api/v1/backup/import`**
- `replace_existing` (bool, default: true) - Replace or merge data
- form field `file` - Single ZIP import (backward compatible)
- form field `files` - One or more ZIPs in a single request (recommended for full + incrementals)

## Backup Server Workflow

### Initial Setup

1. Generate a secure API token:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Add the token to the backend `.env`:
   ```bash
   BACKUP_API_TOKEN=<generated_token>
   ```

3. Store the same token on your backup server:
   ```bash
   # /etc/backup/fstvlpress.env
   API_TOKEN="<generated_token>"
   API_URL="https://yoursite.com/api/v1"
   BACKUP_DIR="/var/backups/fstvlpress"
   ```

### Example: Incremental Backup Script

```bash
#!/bin/bash
# /opt/scripts/fstvlpress-backup.sh
# Run daily via cron: 0 2 * * * /opt/scripts/fstvlpress-backup.sh

set -e

# Load configuration
source /etc/backup/fstvlpress.env

# Create backup directory if needed
mkdir -p "$BACKUP_DIR"

# Get last backup timestamp
LAST_BACKUP=$(curl -sf -H "X-API-Token: $API_TOKEN" "$API_URL/backup/last-backup" | jq -r '.suggested_incremental_since // empty')

DATE=$(date +%Y%m%d_%H%M%S)

if [ -z "$LAST_BACKUP" ]; then
    echo "No previous backup found. Creating full backup..."
    FILENAME="fstvlpress_0000_${DATE}.zip"
    
    curl -sf -H "X-API-Token: $API_TOKEN" \
        "$API_URL/backup/export?include_media=true" \
        -o "$BACKUP_DIR/$FILENAME"
    
    BACKUP_TYPE="full"
else
    echo "Creating incremental backup since $LAST_BACKUP..."
    # Next incremental counter (export endpoint will use this counter for filename).
    NEXT_COUNTER=$(curl -sf -H "X-API-Token: $API_TOKEN" "$API_URL/backup/incremental-counter" | jq -r '.counter + 1')
    FILENAME="fstvlpress_$(printf '%04d' "$NEXT_COUNTER")_${DATE}.zip"
    
    # URL-encode the timestamp
    SINCE_ENCODED=$(echo -n "$LAST_BACKUP" | jq -sRr @uri)
    
    curl -sf -H "X-API-Token: $API_TOKEN" \
        "$API_URL/backup/export/incremental?since=${SINCE_ENCODED}&include_media=true" \
        -o "$BACKUP_DIR/$FILENAME"
    
    BACKUP_TYPE="incremental"
fi

# Verify the backup is a valid zip
if ! unzip -t "$BACKUP_DIR/$FILENAME" > /dev/null 2>&1; then
    echo "ERROR: Downloaded file is not a valid ZIP"
    rm -f "$BACKUP_DIR/$FILENAME"
    exit 1
fi

# Log the successful export (updates last backup timestamp)
curl -sf -X POST -H "X-API-Token: $API_TOKEN" \
    "$API_URL/backup/log-export?backup_type=$BACKUP_TYPE"

echo "Backup saved to $BACKUP_DIR/$FILENAME"

# Optional: Clean up old backups (keep last 30 days)
find "$BACKUP_DIR" -name "fstvlpress_*.zip" -mtime +30 -delete

# Optional: Copy to remote storage
# aws s3 cp "$BACKUP_DIR/$FILENAME" "s3://my-bucket/fstvlpress-backups/"
```

### Cron Configuration

```cron
# Daily incremental backup at 2 AM
0 2 * * * /opt/scripts/fstvlpress-backup.sh >> /var/log/fstvlpress-backup.log 2>&1

# Weekly full backup on Sunday at 3 AM
0 3 * * 0 FORCE_FULL=1 /opt/scripts/fstvlpress-backup.sh >> /var/log/fstvlpress-backup.log 2>&1
```

### Restore from Backup

To restore a backup:

```bash
# Restore full backup (replaces all data)
curl -X POST -H "X-API-Token: $API_TOKEN" \
    -F "file=@fstvlpress_0000_20240301_020000.zip" \
    "$API_URL/backup/import?replace_existing=true"

# Apply incremental backup (merges changes)
curl -X POST -H "X-API-Token: $API_TOKEN" \
    -F "file=@fstvlpress_0001_20240302_020000.zip" \
    "$API_URL/backup/import?replace_existing=false"

# Restore full + multiple incrementals in one request
curl -X POST -H "X-API-Token: $API_TOKEN" \
    -F "files=@fstvlpress_0000_20240301_020000.zip" \
    -F "files=@fstvlpress_0001_20240302_020000.zip" \
    -F "files=@fstvlpress_0002_20240303_020000.zip" \
    "$API_URL/backup/import?replace_existing=true"
```

### Full Restore Workflow

When restoring from multiple incremental backups, you can now do a single import call:

```bash
#!/bin/bash
# Restore from full backup + incrementals

API_TOKEN="your_token"
API_URL="https://yoursite.com/api/v1"
BACKUP_DIR="/var/backups/fstvlpress"

# 1. Find the most recent full backup (counter 0000)
FULL_BACKUP=$(ls -t "$BACKUP_DIR"/fstvlpress_0000_*.zip | head -1)
echo "Using full backup: $FULL_BACKUP"

# 2. Build a curl command with full backup + all incrementals
IMPORT_CMD=(curl -X POST -H "X-API-Token: $API_TOKEN")
IMPORT_CMD+=(-F "files=@$FULL_BACKUP")
for INCR in $(ls "$BACKUP_DIR"/fstvlpress_????_*.zip | grep -v "_0000_" | sort); do
    IMPORT_CMD+=(-F "files=@$INCR")
done
IMPORT_CMD+=("$API_URL/backup/import?replace_existing=true")
echo "Running single combined restore request..."
"${IMPORT_CMD[@]}"

echo "Restore complete!"
```

## Backup Contents

### Supported Formats (Import)

- Supported upload file format: `.zip`
- Expected filename format: `<site_slug>_<counter>_<YYYYMMDD>_<HHMMSS>.zip`
- Counter rules:
  - `0000` = full backup
  - `0001+` = incremental backups
- Required ZIP entries:
  - `manifest.json`
  - `data/<collection>.json` for each collection listed in manifest
- Optional media entries (only when media files are included/changed):
  - `media/manifest.json`
  - all files referenced by `media/manifest.json` (under `media/...`)

Each backup ZIP contains:

```
backup.zip
├── manifest.json           # Backup metadata
├── data/
│   ├── pages.json          # Page documents
│   ├── sections.json       # Section documents
│   ├── headers.json        # Header documents
│   ├── assets.json         # Asset metadata
│   ├── design_config.json
│   ├── design_editor_config.json
│   └── blog_shared.json
└── media/                  # (if include_media=true)
    ├── manifest.json       # Media file index
    └── <asset-files>       # Actual media files
```

Revision history collections, such as `revisions`, `changelog`, and legacy `section_revisions`, are intentionally excluded from backups. Restores preserve current site content but do not restore undo/redo history or the global revision changelog.

## Disaster Recovery

When the database is lost or corrupted, follow these steps to restore from backup.

### Prerequisites

1. **A backup file** - Either a full backup or a full backup + incremental backups
2. **Fresh MongoDB instance** - Running and accessible
3. **Fresh storage** (MinIO/S3/FTP) - Running and accessible
4. **Backend environment** - Configured with correct connection strings

### Step 1: Deploy Fresh Backend

```bash
# Clone the repository (if needed)
git clone <repo-url> fstvlpress
cd fstvlpress/backend

# Create .env with your configuration
cat > .env << 'EOF'
ENVIRONMENT=production
MONGO_URI=mongodb://localhost:27017
MONGO_DB=2026

# Storage configuration (MinIO example)
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=your_minio_access_key
S3_SECRET_ACCESS_KEY=your_minio_secret_key
S3_BUCKET=fstvlpress-assets
S3_PUBLIC_BASE_URL=http://localhost:9000/fstvlpress-assets

# API token for restore operations
BACKUP_API_TOKEN=your_secure_token
EOF

# Install dependencies and start
poetry install
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Step 2: Create Storage Bucket

If using MinIO/S3, ensure the bucket exists:

```bash
# Using MinIO client
mc alias set local http://localhost:9000 your_minio_access_key your_minio_secret_key
mc mb local/fstvlpress-assets --ignore-existing
mc anonymous set download local/fstvlpress-assets
```

### Step 3: Restore from Backup

**Option A: Using curl (recommended for automation)**

```bash
API_URL="http://localhost:8000/api/v1"
API_TOKEN="your_secure_token"
BACKUP_FILE="fstvlpress_0000_20240301_020000.zip"

# Import the backup
curl -X POST \
  -H "X-API-Token: $API_TOKEN" \
  -F "file=@$BACKUP_FILE" \
  "$API_URL/backup/import?replace_existing=true"
```

**Option B: Using the Admin UI**

1. Start the frontend: `cd frontend && npm run dev`
2. Navigate to `/admin/backup`
3. Upload the backup ZIP file
4. Click "Import Backup"

### Step 4: Restore Incremental Backups (if applicable)

If you have incremental backups after your full backup:

```bash
API_URL="http://localhost:8000/api/v1"
API_TOKEN="your_secure_token"

# Apply incrementals in chronological order
for backup in fstvlpress_????_*.zip; do
  [[ "$backup" == fstvlpress_0000_* ]] && continue
  echo "Applying $backup..."
  curl -X POST \
    -H "X-API-Token: $API_TOKEN" \
    -F "file=@$backup" \
    "$API_URL/backup/import?replace_existing=false"
done
```

### Step 5: Verify Restoration

```bash
# Check backup info to verify data was restored
curl -H "X-API-Token: $API_TOKEN" "$API_URL/backup/info"
```

Expected output shows document counts for each collection.

### Complete Disaster Recovery Script

Save this as `restore.sh` on your backup server:

```bash
#!/bin/bash
# Complete disaster recovery script
set -e

# Configuration
API_URL="${API_URL:-http://localhost:8000/api/v1}"
API_TOKEN="${API_TOKEN:-}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/fstvlpress}"

if [ -z "$API_TOKEN" ]; then
  echo "ERROR: API_TOKEN environment variable required"
  exit 1
fi

echo "=== FstvlPress Disaster Recovery ==="
echo "API URL: $API_URL"
echo "Backup Directory: $BACKUP_DIR"
echo ""

# Wait for API to be available
echo "Waiting for API to be available..."
until curl -sf "$API_URL/../health" > /dev/null 2>&1; do
  echo "  API not ready, waiting 5s..."
  sleep 5
done
echo "API is available!"

# Find the most recent full backup (counter 0000)
FULL_BACKUP=$(ls -t "$BACKUP_DIR"/fstvlpress_0000_*.zip 2>/dev/null | head -1)

if [ -z "$FULL_BACKUP" ]; then
  echo "ERROR: No full backup found in $BACKUP_DIR"
  exit 1
fi

echo ""
echo "=== Restoring Full Backup ==="
echo "File: $FULL_BACKUP"

RESULT=$(curl -sf -X POST \
  -H "X-API-Token: $API_TOKEN" \
  -F "file=@$FULL_BACKUP" \
  "$API_URL/backup/import?replace_existing=true")

echo "Result: $RESULT"

# Get the date from the full backup filename
FULL_DATE=$(basename "$FULL_BACKUP" | grep -oP '\d{8}_\d{6}' || echo "")

if [ -n "$FULL_DATE" ]; then
  echo ""
  echo "=== Applying Incremental Backups ==="
  
  # Find and apply incrementals newer than the full backup
  for INCR in $(ls "$BACKUP_DIR"/fstvlpress_????_*.zip 2>/dev/null | grep -v "_0000_" | sort); do
    INCR_DATE=$(basename "$INCR" | grep -oP '\d{8}_\d{6}' || echo "")
    
    if [ -n "$INCR_DATE" ] && [[ "$INCR_DATE" > "$FULL_DATE" ]]; then
      echo "Applying: $INCR"
      curl -sf -X POST \
        -H "X-API-Token: $API_TOKEN" \
        -F "file=@$INCR" \
        "$API_URL/backup/import?replace_existing=false" || echo "  Warning: Failed to apply $INCR"
    fi
  done
fi

echo ""
echo "=== Verifying Restoration ==="
curl -sf -H "X-API-Token: $API_TOKEN" "$API_URL/backup/info" | jq .

echo ""
echo "=== Disaster Recovery Complete ==="
```

Usage:
```bash
export API_TOKEN="your_secure_token"
export API_URL="http://localhost:8000/api/v1"
export BACKUP_DIR="/var/backups/fstvlpress"
./restore.sh
```

### Docker Compose Disaster Recovery

If using Docker Compose, here's a complete recovery workflow:

```bash
# 1. Start infrastructure only
docker-compose up -d mongodb minio

# 2. Wait for services
sleep 10

# 3. Create MinIO bucket
docker-compose exec minio mc alias set local http://localhost:9000 your_minio_access_key your_minio_secret_key
docker-compose exec minio mc mb local/fstvlpress-assets --ignore-existing

# 4. Start backend
docker-compose up -d backend

# 5. Wait for backend
sleep 5

# 6. Restore backup
curl -X POST \
  -H "X-API-Token: $BACKUP_API_TOKEN" \
  -F "file=@backup.zip" \
  "http://localhost:8000/api/v1/backup/import?replace_existing=true"

# 7. Start frontend
docker-compose up -d frontend
```

## Security Considerations

1. **Token Security**: Store `BACKUP_API_TOKEN` securely (e.g., in environment variables, not in scripts)
2. **HTTPS**: Always use HTTPS in production
3. **Network Isolation**: Consider restricting backup API access to specific IP addresses
4. **Token Rotation**: Rotate the API token periodically
5. **Backup Encryption**: Consider encrypting backup files at rest
