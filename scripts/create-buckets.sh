#!/bin/sh
set -e

until mc alias set local http://metrics-storage:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; do
  echo "Waiting for MinIO..."
  sleep 2
done

mc mb --ignore-existing local/metricvalues
mc anonymous set download local/metricvalues
echo "Buckets ready"