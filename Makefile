.PHONY: help start restart stop down ps kill logs shell psql dbshell dbshell_olap \
        db_restore db_restore_postgres db_restore_olap db_restore_s3 \
        db_backup db_backup_postgres db_backup_olap db_backup_s3 \
        clean_data clean_docker

.DEFAULT_GOAL	:= help
SHELL			:= /bin/bash

DOCKER_COMPOSE_LOCAL ?= docker-compose.local.yml
DOCKER_COMPOSE_FLAGS ?= -f $(DOCKER_COMPOSE_LOCAL)

# ---------------------------------------------------
#  Parameters (override: make db_restore OLAP_TABLE=foo ...)
# ---------------------------------------------------
DB_TYPE        ?= postgres
file           ?=

# * Containers (compose service names)
DB_CONTAINER   ?= db
OLAP_CONTAINER ?= olap
API_CONTAINER  ?= api
DB_CONTAINERS  ?= $(OLAP_CONTAINER) storage createbuckets $(DB_CONTAINER)

# * Postgres. The defaults are expanded INSIDE the container (single-quoted bash -c).
PG_USER        ?= $$POSTGRES_USER
PG_DB          ?= $$POSTGRES_DB
PG_JOBS_PERCENT ?= 90

# * ClickHouse. Same idea: defaults come from the container environment.
OLAP_USER      ?= $$CLICKHOUSE_USER
OLAP_PASSWORD  ?= $$CLICKHOUSE_PASSWORD
OLAP_DB        ?= metrics
OLAP_TABLE     ?= metrics_metricvalue
OLAP_FORMAT    ?= Native
# run Django ClickHouse migrations first (creates the tables)
OLAP_MIGRATE   ?= true
# empty the table before loading
OLAP_TRUNCATE  ?= false

# * Export Backup parameters
# Backups are written to ./backup, relative to where `make` is run.
BACKUP_DIR     ?= $(CURDIR)/backup
TIMESTAMP      := $(shell date +%Y%m%d_%H%M%S)
export TIMESTAMP
# zstd | gzip | none
OLAP_COMPRESS  ?= zstd

# * S3 (RustFS). Credentials are read from S3_ENV_FILE (RUSTFS_ACCESS_KEY / RUSTFS_SECRET_KEY).
S3_CONTAINER   ?= storage
S3_ENDPOINT    ?= http://metrics-storage:9000
S3_BUCKET      ?= metricvalues
S3_ENV_FILE    ?= .envs/.local/.s3.env
# Docker network of the compose project. Leave empty to detect it from the running storage container.
S3_NETWORK     ?=
# Create the bucket (with versioning and public-read policy) via `manage.py create_bucket` before importing
S3_CREATE_BUCKET ?= true

help: # http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'


# ===================================================
#  DEV ENVIRONMENT COMMANDS
# ===================================================

start:  ## Create and start containers.
	docker compose $(DOCKER_COMPOSE_FLAGS) up -d --force-recreate

restart:  ## Restart service containers.
	docker compose $(DOCKER_COMPOSE_FLAGS) restart

stop:  ## Stop all containers.
	docker compose $(DOCKER_COMPOSE_FLAGS) stop

down:  ## Stop and remove all containers.
	docker compose $(DOCKER_COMPOSE_FLAGS) down

ps:  ## List containers.
	docker compose $(DOCKER_COMPOSE_FLAGS) ps

kill:  ## Force stop of containers.
	docker compose $(DOCKER_COMPOSE_FLAGS) kill

logs:  ## Show all containers logs.
	docker compose $(DOCKER_COMPOSE_FLAGS) logs -f

shell:  ## Run shell inside django container.
	docker compose $(DOCKER_COMPOSE_FLAGS) run --rm $(API_CONTAINER) /bin/bash

psql:  ## Start postgres command-line client.
	docker compose $(DOCKER_COMPOSE_FLAGS) run --rm $(API_CONTAINER) python3 manage.py dbshell

dbshell:  ## Start database shell.
	@$(MAKE) psql

dbshell_olap:  ## Start OLAP database shell.
	docker compose $(DOCKER_COMPOSE_FLAGS) exec $(OLAP_CONTAINER) \
		sh -c 'clickhouse-client --user "$(OLAP_USER)" --password "$(OLAP_PASSWORD)" -d "$(OLAP_DB)"'


# ===================================================
#  DATABASE RESTORE
# ===================================================
db_restore: ## Restore data (DB_TYPE=postgres|olap|s3 file=<path> [OLAP_TABLE=.. OLAP_DB=.. OLAP_TRUNCATE=true])
	@case "$(DB_TYPE)" in \
		postgres|olap) \
			if [ -z "$(file)" ]; then echo "Error: Please specify a backup file using file=<path>"; exit 1; fi; \
			if [ ! -f "$(file)" ]; then echo "Error: Backup file '$(file)' does not exist"; exit 1; fi; \
			$(MAKE) --no-print-directory db_restore_$(DB_TYPE) file="$(file)" ;; \
		s3) \
			$(MAKE) --no-print-directory db_restore_s3 file="$(file)" ;; \
		*) echo "Error: Invalid DB_TYPE. Use postgres, olap or s3"; exit 1 ;; \
	esac

db_restore_postgres:
	@BACKUP_FILE_PATH=$$(realpath "$(file)"); \
	docker compose $(DOCKER_COMPOSE_FLAGS) cp "$$BACKUP_FILE_PATH" $(DB_CONTAINER):/backup.dump

	@CPU_CORES=$$(nproc); \
	NUM_JOBS=$$((CPU_CORES * $(PG_JOBS_PERCENT) / 100)); \
	if [ $$NUM_JOBS -lt 1 ]; then NUM_JOBS=1; fi; \
	docker compose $(DOCKER_COMPOSE_FLAGS) exec -T $(DB_CONTAINER) \
		bash -c 'while ! pg_isready -U "$(PG_USER)" -d "$(PG_DB)"; do sleep 1; done && pg_restore -Fc -U "$(PG_USER)" -d "$(PG_DB)" --clean --if-exists --no-owner --no-acl -j '"$$NUM_JOBS"' /backup.dump'

	@docker compose $(DOCKER_COMPOSE_FLAGS) exec -T $(DB_CONTAINER) rm -f /backup.dump

db_restore_olap:
	@set -euo pipefail; \
	if [ "$(OLAP_MIGRATE)" = "true" ]; then \
		echo ">> Creating ClickHouse schema (Django migrate)"; \
		docker compose $(DOCKER_COMPOSE_FLAGS) run --rm $(API_CONTAINER) \
			python manage.py migrate --database=clickhouse; \
	fi; \
	if [ "$(OLAP_TRUNCATE)" = "true" ]; then \
		echo ">> Truncating $(OLAP_DB).$(OLAP_TABLE)"; \
		docker compose $(DOCKER_COMPOSE_FLAGS) exec -T $(OLAP_CONTAINER) \
			sh -c 'clickhouse-client --user "$(OLAP_USER)" --password "$(OLAP_PASSWORD)" -q "TRUNCATE TABLE $(OLAP_DB).$(OLAP_TABLE)"'; \
	fi; \
	case "$(file)" in \
		*.zst) DECOMP="zstd -dc" ;; \
		*.gz)  DECOMP="gzip -dc" ;; \
		*)     DECOMP="cat" ;; \
	esac; \
	echo ">> Importing $(file) into $(OLAP_DB).$(OLAP_TABLE) ($(OLAP_FORMAT))"; \
	$$DECOMP "$(file)" | docker compose $(DOCKER_COMPOSE_FLAGS) exec -T $(OLAP_CONTAINER) \
		sh -c 'clickhouse-client --user "$(OLAP_USER)" --password "$(OLAP_PASSWORD)" -q "INSERT INTO $(OLAP_DB).$(OLAP_TABLE) FORMAT $(OLAP_FORMAT)"'; \
	echo ">> Rows now in $(OLAP_DB).$(OLAP_TABLE):"; \
	docker compose $(DOCKER_COMPOSE_FLAGS) exec -T $(OLAP_CONTAINER) \
		sh -c 'clickhouse-client --user "$(OLAP_USER)" --password "$(OLAP_PASSWORD)" -q "SELECT count() FROM $(OLAP_DB).$(OLAP_TABLE)"'

db_restore_s3:
	@set -euo pipefail; \
	SRC="$(file)"; \
	if [ -z "$$SRC" ]; then SRC="$(BACKUP_DIR)/s3/$(S3_BUCKET)"; fi; \
	[ -d "$$SRC" ] || { echo "Error: '$$SRC' is not a directory. Use file=<backup folder>"; exit 1; }; \
	SRC=$$(realpath "$$SRC"); \
	if [ "$(S3_CREATE_BUCKET)" = "true" ]; then \
		echo ">> Ensuring bucket exists (create_bucket)"; \
		docker compose $(DOCKER_COMPOSE_FLAGS) run --rm createbuckets; \
	fi; \
	NET="$(S3_NETWORK)"; \
	if [ -z "$$NET" ]; then \
		CID=$$(docker compose $(DOCKER_COMPOSE_FLAGS) ps -q $(S3_CONTAINER)); \
		[ -n "$$CID" ] || { echo "Error: '$(S3_CONTAINER)' is not running"; exit 1; }; \
		NET=$$(docker inspect "$$CID" --format '{{range $$k, $$v := .NetworkSettings.Networks}}{{$$k}} {{end}}' | awk '{print $$1}'); \
	fi; \
	echo ">> Uploading $$SRC to bucket '$(S3_BUCKET)' (network: $$NET)"; \
	docker run --rm --network "$$NET" -e HOME=/tmp \
		--env-file "$(S3_ENV_FILE)" -v "$$SRC:/restore:ro" --entrypoint sh rclone/rclone:latest -c ' \
		export RCLONE_CONFIG_DST_TYPE=s3 RCLONE_CONFIG_DST_PROVIDER=Other \
			RCLONE_CONFIG_DST_ENDPOINT="$(S3_ENDPOINT)" \
			RCLONE_CONFIG_DST_ACCESS_KEY_ID="$$RUSTFS_ACCESS_KEY" \
			RCLONE_CONFIG_DST_SECRET_ACCESS_KEY="$$RUSTFS_SECRET_KEY"; \
		rclone copy /restore DST:$(S3_BUCKET) --progress --transfers 8 --s3-no-check-bucket && \
		echo ">> Verifying" && \
		rclone check /restore DST:$(S3_BUCKET) --one-way --s3-no-check-bucket'; \
	echo ">> Done"

# ===================================================
#  DATABASE / STORAGE BACKUP (export to the host)
# ===================================================

db_backup: ## Export data to ./backup (DB_TYPE=postgres|olap|s3|all)
	@case "$(DB_TYPE)" in \
		postgres) $(MAKE) --no-print-directory db_backup_postgres ;; \
		olap)     $(MAKE) --no-print-directory db_backup_olap ;; \
		s3)       $(MAKE) --no-print-directory db_backup_s3 ;; \
		all)      $(MAKE) --no-print-directory db_backup_postgres && \
		          $(MAKE) --no-print-directory db_backup_olap && \
		          $(MAKE) --no-print-directory db_backup_s3 ;; \
		*) echo "Error: Invalid DB_TYPE. Use postgres, olap, s3 or all"; exit 1 ;; \
	esac

db_backup_postgres:
	@set -euo pipefail; \
	mkdir -p "$(BACKUP_DIR)"; \
	OUT="$(BACKUP_DIR)/postgres_$(TIMESTAMP).dump"; \
	trap 'rm -f "$$OUT.part"' EXIT; \
	echo ">> Dumping PostgreSQL to $$OUT"; \
	docker compose $(DOCKER_COMPOSE_FLAGS) exec -T $(DB_CONTAINER) \
		sh -c 'pg_dump -U "$(PG_USER)" -d "$(PG_DB)" -Fc --no-owner --no-acl' > "$$OUT.part"; \
	mv "$$OUT.part" "$$OUT"; \
	ls -lh "$$OUT"

db_backup_olap:
	@set -euo pipefail; \
	mkdir -p "$(BACKUP_DIR)"; \
	case "$(OLAP_COMPRESS)" in \
		zstd) command -v zstd >/dev/null || { echo "Error: zstd not installed (use OLAP_COMPRESS=gzip)"; exit 1; }; \
		      EXT=".zst"; COMP="zstd -T0 -3" ;; \
		gzip) EXT=".gz";  COMP="gzip -c" ;; \
		none) EXT="";     COMP="cat" ;; \
		*)    echo "Error: Invalid OLAP_COMPRESS. Use zstd, gzip or none"; exit 1 ;; \
	esac; \
	FMT=$$(echo "$(OLAP_FORMAT)" | tr '[:upper:]' '[:lower:]'); \
	OUT="$(BACKUP_DIR)/olap_$(OLAP_DB)_$(OLAP_TABLE)_$(TIMESTAMP).$$FMT$$EXT"; \
	trap 'rm -f "$$OUT.part"' EXIT; \
	echo ">> Exporting $(OLAP_DB).$(OLAP_TABLE) ($(OLAP_FORMAT)) to $$OUT"; \
	docker compose $(DOCKER_COMPOSE_FLAGS) exec -T $(OLAP_CONTAINER) \
		sh -c 'clickhouse-client --user "$(OLAP_USER)" --password "$(OLAP_PASSWORD)" -q "SELECT * FROM $(OLAP_DB).$(OLAP_TABLE) FORMAT $(OLAP_FORMAT)"' \
		| $$COMP > "$$OUT.part"; \
	mv "$$OUT.part" "$$OUT"; \
	ls -lh "$$OUT"; \
	echo ">> Rows in source table (compare after restoring):"; \
	docker compose $(DOCKER_COMPOSE_FLAGS) exec -T $(OLAP_CONTAINER) \
		sh -c 'clickhouse-client --user "$(OLAP_USER)" --password "$(OLAP_PASSWORD)" -q "SELECT count() FROM $(OLAP_DB).$(OLAP_TABLE)"'

db_backup_s3:
	@set -euo pipefail; \
	DEST="$(BACKUP_DIR)/s3/$(S3_BUCKET)"; \
	mkdir -p "$$DEST"; \
	NET="$(S3_NETWORK)"; \
	if [ -z "$$NET" ]; then \
		CID=$$(docker compose $(DOCKER_COMPOSE_FLAGS) ps -q $(S3_CONTAINER)); \
		[ -n "$$CID" ] || { echo "Error: '$(S3_CONTAINER)' is not running"; exit 1; }; \
		NET=$$(docker inspect "$$CID" --format '{{range $$k, $$v := .NetworkSettings.Networks}}{{$$k}} {{end}}' | awk '{print $$1}'); \
	fi; \
	echo ">> Copying bucket '$(S3_BUCKET)' to $$DEST (network: $$NET)"; \
	docker run --rm --network "$$NET" --user "$$(id -u):$$(id -g)" -e HOME=/tmp \
		--env-file "$(S3_ENV_FILE)" -v "$$DEST:/backup" --entrypoint sh rclone/rclone:latest -c ' \
		export RCLONE_CONFIG_SRC_TYPE=s3 RCLONE_CONFIG_SRC_PROVIDER=Other \
			RCLONE_CONFIG_SRC_ENDPOINT="$(S3_ENDPOINT)" \
			RCLONE_CONFIG_SRC_ACCESS_KEY_ID="$$RUSTFS_ACCESS_KEY" \
			RCLONE_CONFIG_SRC_SECRET_ACCESS_KEY="$$RUSTFS_SECRET_KEY"; \
		rclone copy SRC:$(S3_BUCKET) /backup --progress --transfers 8 --s3-no-check-bucket'; \
	echo ">> $$(find "$$DEST" -type f | wc -l) files, $$(du -sh "$$DEST" | cut -f1)"

# ===================================================
#  CLEANUP
# ===================================================

clean_data:  ## Remove any data
	docker compose $(DOCKER_COMPOSE_FLAGS) down $(DB_CONTAINERS) --volumes

clean_docker:  ## Remove all container and images.
	docker rm $$(docker ps -a -q)
	docker rmi $$(docker image ls -q)