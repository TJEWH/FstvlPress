#!/usr/bin/env bash
set -euo pipefail

# Get the backend/ directory (parent of this script's directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
OUTPUT_BASE="${SCRIPT_DIR}/dummy_data/mongo"

# Load MONGO_URI and MONGO_DB from .env (handles values with = by taking everything after first =)
MONGO_URI=$(grep '^MONGO_URI=' "$ENV_FILE" | cut -d '=' -f2- | tr -d '\r')
MONGO_DB=$(grep '^MONGO_DB=' "$ENV_FILE" | cut -d '=' -f2- | tr -d '\r')

if [[ -z "$MONGO_URI" ]]; then
  echo "Error: MONGO_URI not found in ${ENV_FILE}" >&2
  exit 1
fi

if [[ -z "$MONGO_DB" ]]; then
  echo "Error: MONGO_DB not found in ${ENV_FILE}" >&2
  exit 1
fi

OUTPUT_DIR="${OUTPUT_BASE}/${MONGO_DB}"
mkdir -p "$OUTPUT_DIR"

echo "Dumping database '${MONGO_DB}' to ${OUTPUT_DIR}..."
mongodump --uri="$MONGO_URI" --db="$MONGO_DB" --out="$OUTPUT_BASE"

echo "Done. Dump saved to ${OUTPUT_DIR}"
