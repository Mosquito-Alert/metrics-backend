#!/bin/sh
sleep 10
mc alias set local http://storage:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing local/metricvalues
mc anonymous set download local/metricvalues