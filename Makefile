.PHONY: help start restart stop down ps kill logs shell psql \
        db_restore db_restore_postgres db_restore_olap \
        clean_data clean_docker

.DEFAULT_GOAL	:= help
SHELL			:= /bin/bash

DOCKER_COMPOSE_LOCAL=docker-compose.local.yml

DOCKER_COMPOSE_FLAGS := -f $(DOCKER_COMPOSE_LOCAL)

DB_CONTAINER = db
DB_CONTAINERS = olap storage createbuckets $(DB_CONTAINER)
DB_TYPE ?= postgres

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

down:  ## Stop all containers.
	docker compose $(DOCKER_COMPOSE_FLAGS) down

ps:  ## List containers.
	docker compose $(DOCKER_COMPOSE_FLAGS) ps

kill:  # Force stop of containers.
	docker compose $(DOCKER_COMPOSE_FLAGS) kill

logs:  ## Show all containers logs.
	docker compose $(DOCKER_COMPOSE_FLAGS) logs -f

shell:  ## Run shell inside django container.
	docker compose $(DOCKER_COMPOSE_FLAGS) run --rm api /bin/bash

psql:  ## Start postgres command-line client.
	docker compose $(DOCKER_COMPOSE_FLAGS) run --rm api python3 manage.py dbshell

dbshell:  ## Start database shell.
	@$(MAKE) psql

dbshell_olap:  ## Start OLAP database shell.
	docker compose $(DOCKER_COMPOSE_FLAGS) exec -T olap clickhouse-client

db_restore: ## Restore database (DB_TYPE=postgres|olap file=backup_path)
	@if [ -z "$(file)" ]; then \
		echo "Error: Please specify a backup file using file=<path>"; \
		exit 1; \
	fi
	@if [ ! -f "$(file)" ]; then \
		echo "Error: Backup file '$(file)' does not exist"; \
		exit 1; \
	fi
	@case "$(DB_TYPE)" in \
		postgres) $(MAKE) db_restore_postgres file="$(file)" ;; \
		olap) $(MAKE) db_restore_olap file="$(file)" ;; \
		*) echo "Error: Invalid DB_TYPE. Use postgres or olap"; exit 1 ;; \
	esac

db_restore_postgres:
	@BACKUP_FILE_PATH=$$(realpath "$(file)"); \
	docker compose $(DOCKER_COMPOSE_FLAGS) cp "$$BACKUP_FILE_PATH" $(DB_CONTAINER):/backup.dump

	@CPU_CORES=$$(nproc); \
	PERCENTAGE=90; \
	NUM_JOBS=$$((CPU_CORES * PERCENTAGE / 100)); \
	if [ $$NUM_JOBS -lt 1 ]; then NUM_JOBS=1; fi; \
	docker compose $(DOCKER_COMPOSE_FLAGS) exec -T $(DB_CONTAINER) \
		bash -c "while ! pg_isready -U postgres -d postgres; do sleep 1; done && pg_restore -Fc -U postgres -d postgres -j $$NUM_JOBS /backup.dump"

	@docker compose $(DOCKER_COMPOSE_FLAGS) exec -T $(DB_CONTAINER) rm -f /backup.dump

db_restore_olap:
	@BACKUP_FILE_PATH=$$(realpath "$(file)"); \
	docker compose $(DOCKER_COMPOSE_FLAGS) cp "$$BACKUP_FILE_PATH" olap:/tmp/backup.sql

	@docker compose $(DOCKER_COMPOSE_FLAGS) exec -T olap \
		clickhouse-client --multiquery --queries-file=/tmp/backup.sql

	@docker compose $(DOCKER_COMPOSE_FLAGS) exec -T olap rm -f /tmp/backup.sql

clean_data:  ## Remove any data
	docker compose $(DOCKER_COMPOSE_FLAGS) down $(DB_CONTAINERS) --volumes

clean_docker:  ## Remove all container and images.
	docker rm $(docker ps -a -q)
	docker rmi $(docker image ls -q)

