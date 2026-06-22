#!/bin/sh
set -e

# Wait for MinIO to be ready (handles startup order in Swarm/Compose)
until mc alias set local "http://minio:9000" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" 2>/dev/null; do
  echo "Waiting for MinIO..."
  sleep 3
done

# Create bucket and set public read for objects
mc mb --ignore-existing "local/${S3_BUCKET}"
mc anonymous set download "local/${S3_BUCKET}"

# Create least-privilege service account when S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY are provided
if [ -n "${S3_ACCESS_KEY_ID}" ] && [ -n "${S3_SECRET_ACCESS_KEY}" ]; then
  echo "Creating service account with bucket-only access policy..."
  POLICY=$(cat <<POLICY_EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": ["arn:aws:s3:::${S3_BUCKET}/*"]
    }
  ]
}
POLICY_EOF
)
  echo "${POLICY}" > /tmp/fstvlpress-bucket-rw.json
  mc admin policy create local fstvlpress-bucket-rw /tmp/fstvlpress-bucket-rw.json 2>/dev/null || true
  mc admin accesskey create local/ \
    --access-key "${S3_ACCESS_KEY_ID}" \
    --secret-key "${S3_SECRET_ACCESS_KEY}" \
    --policy /tmp/fstvlpress-bucket-rw.json 2>/dev/null || echo "Service account may already exist, continuing."
  echo "Service account created (or already exists)."
else
  echo "S3_ACCESS_KEY_ID/S3_SECRET_ACCESS_KEY not set - using root credentials for backend."
fi

echo "MinIO bucket setup complete."
