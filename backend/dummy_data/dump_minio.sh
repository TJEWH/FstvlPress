#!/usr/bin/env bash
set -euo pipefail

# Get the directory where this script lives (backend/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
OUTPUT_BASE="${SCRIPT_DIR}/dummy_data/minio"

# Load S3 vars from .env (handles values with = by taking everything after first =)
S3_ACCESS_KEY_ID=$(grep '^S3_ACCESS_KEY_ID=' "$ENV_FILE" | cut -d '=' -f2- | tr -d '\r')
S3_SECRET_ACCESS_KEY=$(grep '^S3_SECRET_ACCESS_KEY=' "$ENV_FILE" | cut -d '=' -f2- | tr -d '\r')
S3_BUCKET=$(grep '^S3_BUCKET=' "$ENV_FILE" | cut -d '=' -f2- | tr -d '\r')

# Default endpoint for local MinIO Docker container (override with S3_ENDPOINT_URL in .env if set)
S3_ENDPOINT_URL=$(grep '^S3_ENDPOINT_URL=' "$ENV_FILE" 2>/dev/null | cut -d '=' -f2- | tr -d '\r' || true)
S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-http://localhost:9000}"

if [[ -z "$S3_ACCESS_KEY_ID" ]]; then
  echo "Error: S3_ACCESS_KEY_ID not found in ${ENV_FILE}" >&2
  exit 1
fi

if [[ -z "$S3_SECRET_ACCESS_KEY" ]]; then
  echo "Error: S3_SECRET_ACCESS_KEY not found in ${ENV_FILE}" >&2
  exit 1
fi

if [[ -z "$S3_BUCKET" ]]; then
  echo "Error: S3_BUCKET not found in ${ENV_FILE}" >&2
  exit 1
fi

if ! command -v aws &>/dev/null; then
  echo "Error: AWS CLI (aws) is required. Install it with: brew install awscli" >&2
  exit 1
fi

OUTPUT_DIR="${OUTPUT_BASE}/${S3_BUCKET}"
mkdir -p "$OUTPUT_DIR"

echo "Dumping bucket '${S3_BUCKET}' from ${S3_ENDPOINT_URL} to ${OUTPUT_DIR}..."
export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$S3_SECRET_ACCESS_KEY"
aws s3 sync "s3://${S3_BUCKET}" "$OUTPUT_DIR" \
  --endpoint-url "$S3_ENDPOINT_URL" \
  --no-progress

echo "Done. Dump saved to ${OUTPUT_DIR}"
