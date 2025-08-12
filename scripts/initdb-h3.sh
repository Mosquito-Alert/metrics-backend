#!/bin/sh

set -e

# Perform all actions as $POSTGRES_USER
export PGUSER="$POSTGRES_USER"

"${psql[@]}" <<- 'EOSQL'
CREATE EXTENSION IF NOT EXISTS h3;
EOSQL
