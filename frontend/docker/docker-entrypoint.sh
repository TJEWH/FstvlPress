#!/bin/sh
set -e

# Nginx config substitution
S3_BUCKET="${S3_BUCKET:-fstvlpress-assets}"
S3_SERVICE_HOST="${S3_SERVICE_HOST:-minio:9000}"
BACKEND_SERVICE_HOST="${BACKEND_SERVICE_HOST:-backend:8000}"
APP_DISPLAY_NAME="${APP_DISPLAY_NAME:-}"
OIDC_URL="${OIDC_URL:-}"
OIDC_HOST=$(echo "$OIDC_URL" | sed -e 's|^https\?://||' -e 's|/.*||')
OIDC_REALM_NAME="${OIDC_REALM_NAME:-}"
OIDC_CLIENT_ID="${OIDC_CLIENT_ID:-}"
OIDC_CLIENT_SECRET="${OIDC_CLIENT_SECRET:-}"
OIDC_TOKEN_CLIENT_ID="${OIDC_CLIENT_ID:-}"
OIDC_TOKEN_AUTHORIZATION=""
if [ -n "$OIDC_TOKEN_CLIENT_ID" ] && [ -n "$OIDC_CLIENT_SECRET" ]; then
    if command -v base64 >/dev/null 2>&1; then
        OIDC_TOKEN_AUTHORIZATION="Basic $(printf '%s:%s' "$OIDC_TOKEN_CLIENT_ID" "$OIDC_CLIENT_SECRET" | base64 | tr -d '\n')"
    elif command -v openssl >/dev/null 2>&1; then
        OIDC_TOKEN_AUTHORIZATION="Basic $(printf '%s:%s' "$OIDC_TOKEN_CLIENT_ID" "$OIDC_CLIENT_SECRET" | openssl base64 -A)"
    else
        echo "WARNING: Unable to set OIDC token authorization header (no base64 or openssl available)" >&2
    fi
fi
API_PROXY_READ_TIMEOUT="${API_PROXY_READ_TIMEOUT:-900s}"
API_PROXY_SEND_TIMEOUT="${API_PROXY_SEND_TIMEOUT:-900s}"
API_PROXY_CONNECT_TIMEOUT="${API_PROXY_CONNECT_TIMEOUT:-75s}"
BACKUP_UPLOAD_MAX_BODY_SIZE="${BACKUP_UPLOAD_MAX_BODY_SIZE:-1g}"
BACKUP_PROXY_READ_TIMEOUT="${BACKUP_PROXY_READ_TIMEOUT:-3600s}"
BACKUP_PROXY_SEND_TIMEOUT="${BACKUP_PROXY_SEND_TIMEOUT:-3600s}"
BACKUP_CLIENT_BODY_TIMEOUT="${BACKUP_CLIENT_BODY_TIMEOUT:-3600s}"
sed -e "s|__S3_BUCKET__|${S3_BUCKET}|g" \
    -e "s|__S3_SERVICE_HOST__|${S3_SERVICE_HOST}|g" \
    -e "s|__BACKEND_SERVICE_HOST__|${BACKEND_SERVICE_HOST}|g" \
    -e "s|__OIDC_URL__|${OIDC_URL}|g" \
    -e "s|__OIDC_HOST__|${OIDC_HOST}|g" \
    -e "s|__OIDC_TOKEN_AUTHORIZATION__|${OIDC_TOKEN_AUTHORIZATION}|g" \
    -e "s|__API_PROXY_READ_TIMEOUT__|${API_PROXY_READ_TIMEOUT}|g" \
    -e "s|__API_PROXY_SEND_TIMEOUT__|${API_PROXY_SEND_TIMEOUT}|g" \
    -e "s|__API_PROXY_CONNECT_TIMEOUT__|${API_PROXY_CONNECT_TIMEOUT}|g" \
    -e "s|__BACKUP_UPLOAD_MAX_BODY_SIZE__|${BACKUP_UPLOAD_MAX_BODY_SIZE}|g" \
    -e "s|__BACKUP_PROXY_READ_TIMEOUT__|${BACKUP_PROXY_READ_TIMEOUT}|g" \
    -e "s|__BACKUP_PROXY_SEND_TIMEOUT__|${BACKUP_PROXY_SEND_TIMEOUT}|g" \
    -e "s|__BACKUP_CLIENT_BODY_TIMEOUT__|${BACKUP_CLIENT_BODY_TIMEOUT}|g" \
    /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Generate runtime frontend config (public values only)
cat > /usr/share/nginx/html/config.js << EOF
window.APP_CONFIG = {
  APP_DISPLAY_NAME: "${APP_DISPLAY_NAME}",
  OIDC_URL: "${OIDC_URL}",
  OIDC_REALM_NAME: "${OIDC_REALM_NAME}",
  OIDC_CLIENT_ID: "${OIDC_CLIENT_ID}"
};
EOF

echo "Runtime config generated with APP_DISPLAY_NAME=${APP_DISPLAY_NAME}, OIDC_URL=${OIDC_URL}, OIDC_REALM_NAME=${OIDC_REALM_NAME}, OIDC_CLIENT_ID=${OIDC_CLIENT_ID}"

exec nginx -g "daemon off;"
