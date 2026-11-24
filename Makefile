.PHONY: help start restart stop down ps kill logs shell psql dbshell dbshell_olap \
        db_restore db_restore_postgres db_restore_olap \
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

# Containers (compose service names)
DB_CONTAINER   ?= db
OLAP_CONTAINER ?= olap
API_CONTAINER  ?= api
DB_CONTAINERS  ?= $(OLAP_CONTAINER) storage createbuckets $(DB_CONTAINER)

# Postgres. The defaults are expanded INSIDE the container (single-quoted bash -c).
PG_USER        ?= $$POSTGRES_USER
PG_DB          ?= $$POSTGRES_DB
PG_JOBS_PERCENT ?= 90

# ClickHouse. Same idea: defaults come from the container environment.
OLAP_USER      ?= $$CLICKHOUSE_USER
OLAP_PASSWORD  ?= $$CLICKHOUSE_PASSWORD
OLAP_DB        ?= metrics
OLAP_TABLE     ?= metrics_metricvalue
OLAP_FORMAT    ?= Native
OLAP_MIGRATE   ?= true     # run Django ClickHouse migrations first (creates the tables)
OLAP_TRUNCATE  ?= false    # empty the table before loading


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

db_restore: ## Restore database (DB_TYPE=postgres|olap file=<path> [OLAP_TABLE=.. OLAP_DB=.. OLAP_TRUNCATE=true])
	@if [ -z "$(file)" ]; then \
		echo "Error: Please specify a backup file using file=<path>"; \
		exit 1; \
	fi
	@if [ ! -f "$(file)" ]; then \
		echo "Error: Backup file '$(file)' does not exist"; \
		exit 1; \
	fi
	@case "$(DB_TYPE)" in \
		postgres) $(MAKE) --no-print-directory db_restore_postgres file="$(file)" ;; \
		olap)     $(MAKE) --no-print-directory db_restore_olap file="$(file)" ;; \
		*) echo "Error: Invalid DB_TYPE. Use postgres or olap"; exit 1 ;; \
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


# ===================================================
#  CLEANUP
# ===================================================

clean_data:  ## Remove any data
	docker compose $(DOCKER_COMPOSE_FLAGS) down $(DB_CONTAINERS) --volumes

clean_docker:  ## Remove all container and images.
	docker rm $$(docker ps -a -q)
	docker rmi $$(docker image ls -q)