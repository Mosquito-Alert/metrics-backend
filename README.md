# Metrics

[![Create and publish a Docker image](https://github.com/Mosquito-Alert/metrics-backend/actions/workflows/publish-api-image.yml/badge.svg)](https://github.com/Mosquito-Alert/metrics-backend/actions/workflows/publish-api-image.yml)
[![Django Version](https://img.shields.io/badge/django-5.2-green.svg)](https://www.djangoproject.com/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE.md)

This is the backend component of the metrics project. This project aims to show different metrics concerning the Mosquito Alert project, such as providing a map that that displays bite index anomalies.

**Live Server**: [https://metrics.mosquitoalert.com/v2/](https://metrics.mosquitoalert.com/v2/)

**Project Website**: [https://mosquitoalert.com](https://mosquitoalert.com)

## 📋 Table of Contents

- [Metrics](#metrics)
  - [📋 Table of Contents](#-table-of-contents)
  - [🦟 About the Project](#-about-the-project)
  - [🚀 Getting Started](#-getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Configuration](#configuration)
  - [💻 Usage](#-usage)
    - [Running the Application](#running-the-application)
    - [Available Commands](#available-commands)
  - [📚 API Documentation \& SDKs](#-api-documentation--sdks)
    - [API Documentation](#api-documentation)
    - [Official SDKs](#official-sdks)
  - [🧪 Testing](#-testing)
    - [Running Tests](#running-tests)
    - [Test Configuration](#test-configuration)
  - [🤝 Contributing](#-contributing)
    - [Contribution Guidelines](#contribution-guidelines)
    - [Reporting Issues](#reporting-issues)
    - [Development Workflow](#development-workflow)
  - [📄 License](#-license)
  - [👥 Contact](#-contact)
  - [🙏 Acknowledgments](#-acknowledgments)

## 🦟 About the Project

Mosquito Alert harnesses the power of citizen scientists and modern technology to investigate the spread of mosquito species, particularly tiger mosquitoes, across different regions. This Django-based server application:

- Receives and processes mosquito related metrics
- Generate rasterized geospatial data
- Handles geospatial data processing with PostGIS
- Implements robust authentication and authorization

## 🚀 Getting Started

### Prerequisites

- **Docker** and **Docker Compose**

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/Mosquito-Alert/metrics-backend.git
   cd metrics-backend
   ```

2. **Build and start containers**

   ```bash
   make start
   ```

   This will:
   - Build the Docker images
   - Start PostgreSQL and ClickHouse
   - Start the Django application on port 8000
   - Run database migrations

3. **Create a superuser** (optional)
   ```bash
   make shell
   python3 manage.py createsuperuser
   ```

### Configuration

The project uses Django settings modules:

- `project.settings.production` - Production settings
- `project.settings.local` - Development settings

Environment variables can be set for:

- Database connection
- Secret keys
- Storage backends

## 💻 Usage

### Running the Application

```bash
# Start all services
make start

# View logs
make logs

# Stop services
make stop

# Restart services
make restart
```

Access the application:

- **API**: http://localhost:8000/v2/
- **Admin**: http://localhost:8000/admin/

#### Available Commands

The `Makefile` provides convenient commands for development:

| Command             | Description                                                         |
| ------------------- | ------------------------------------------------------------------- |
| `make start`        | Create and start all containers                                     |
| `make stop`         | Stop all containers                                                 |
| `make restart`      | Restart all services                                                |
| `make down`         | Stop and remove containers                                          |
| `make kill`         | Force stop all containers                                           |
| `make logs`         | Show container logs (follow mode)                                   |
| `make ps`           | List running containers                                             |
| `make shell`        | Open bash shell in the Django container                             |
| `make psql`         | Start PostgreSQL command-line client                                |
| `make dbshell`      | Start database shell (alias of `make psql`)                         |
| `make dbshell_olap` | Start ClickHouse (OLAP) command-line client                         |
| `make db_restore`   | Restore PostgreSQL, ClickHouse or S3 data from a backup (see below) |
| `make db_backup`    | Export data to `./backup` (see below)                               |
| `make clean_data`   | Remove all data volumes                                             |
| `make clean_docker` | Remove all containers and images                                    |

Run `make help` to list the commands that have a description.

### Restoring a database

`make db_restore` restores either database from a backup file. Every parameter can be overridden on the command line.

```bash
# PostgreSQL (custom-format dump made with pg_dump -Fc)
make db_restore file=<path>

# ClickHouse (Native-format export; .zst, .gz or plain files are detected by extension)
make db_restore DB_TYPE=olap file=<path>
```

**Stop the services that write to the databases first** (`docker compose -f docker-compose.local.yml stop api worker worker_flower`), otherwise open connections can make the restore fail or leave inconsistent data.

#### S3 (RustFS) parameters (`DB_TYPE=s3`)

```bash
# Restore from the default folder (backup/s3/<bucket>)
make db_restore DB_TYPE=s3

# Restore from a specific folder
make db_restore DB_TYPE=s3 file=<path-to-folder>
```

For S3, `file` is a **folder**, not a file. Its contents are uploaded to the bucket root.

| Parameter          | Default                       | Description                                                           |
| ------------------ | ----------------------------- | --------------------------------------------------------------------- |
| `file`             | `./backup/s3/<S3_BUCKET>`     | Folder to upload                                                      |
| `S3_BUCKET`        | `metricvalues`                | Destination bucket                                                    |
| `S3_CREATE_BUCKET` | `true`                        | Run `manage.py create_bucket` first (bucket, versioning, public read) |
| `S3_ENDPOINT`      | `http://metrics-storage:9000` | S3 endpoint as seen from inside the compose network                   |
| `S3_ENV_FILE`      | `.envs/.local/.s3.env`        | Env file with `RUSTFS_ACCESS_KEY` and `RUSTFS_SECRET_KEY`             |
| `S3_NETWORK`       | _(auto-detected)_             | Docker network of the compose project                                 |

Existing objects are never deleted. Files that already exist with the same content are skipped, so the command can be repeated safely. After uploading, every file is verified against the backup.

```bash
# Production
make db_restore DB_TYPE=s3 file=<path> DOCKER_COMPOSE_LOCAL=docker-compose.yml S3_ENV_FILE=.envs/.production/.s3.env
```

### Backing up data

`make db_backup` exports data to the host, into a `backup/` folder created in the directory where you run the command. Files are timestamped, so backups are never overwritten.

```bash
make db_backup                    # PostgreSQL (default)
make db_backup DB_TYPE=olap       # ClickHouse
make db_backup DB_TYPE=s3         # RustFS bucket
make db_backup DB_TYPE=all        # all three
```

Result:

```
backup/
├── postgres_20261124_153000.dump
├── olap_metrics_metrics_metricvalue_20261124_153000.native.zst
└── s3/
    └── metricvalues/...
```

The PostgreSQL and ClickHouse files can be restored directly with `make db_restore` (see above).

| Parameter          | Default                       | Description                                               |
| ------------------ | ----------------------------- | --------------------------------------------------------- |
| `DB_TYPE`          | `postgres`                    | What to export: `postgres`, `olap`, `s3` or `all`         |
| `BACKUP_DIR`       | `./backup`                    | Destination folder                                        |
| `PG_USER`, `PG_DB` | from the container env        | PostgreSQL user and database                              |
| `OLAP_DB`          | `metrics`                     | ClickHouse database                                       |
| `OLAP_TABLE`       | `metrics_metricvalue`         | ClickHouse table (one per run)                            |
| `OLAP_FORMAT`      | `Native`                      | Export format                                             |
| `OLAP_COMPRESS`    | `zstd`                        | `zstd`, `gzip` or `none`                                  |
| `S3_BUCKET`        | `metricvalues`                | Bucket to copy                                            |
| `S3_ENDPOINT`      | `http://metrics-storage:9000` | S3 endpoint, as seen from inside the compose network      |
| `S3_ENV_FILE`      | `.envs/.local/.s3.env`        | Env file with `RUSTFS_ACCESS_KEY` and `RUSTFS_SECRET_KEY` |
| `S3_NETWORK`       | _(auto-detected)_             | Docker network of the compose project                     |

Examples:

```bash
# Another ClickHouse table, gzip instead of zstd
make db_backup DB_TYPE=olap OLAP_TABLE=other_table OLAP_COMPRESS=gzip

# Back up production (from the server)
make db_backup DB_TYPE=all DOCKER_COMPOSE_LOCAL=docker-compose.yml S3_ENV_FILE=.envs/.production/.s3.env
```

Notes:

- The three exports are taken one after another, not as one snapshot. For a consistent backup, stop the services that write first (`docker compose -f docker-compose.local.yml stop api worker worker_flower`).
- Only the current version of each S3 object is exported. Previous versions of a versioned bucket are not included.
- ClickHouse exports use a plain `SELECT *`, so rows not yet merged by the `ReplacingMergeTree` may include duplicates. They collapse again on merge after the restore.
- `zstd` must be installed on the host for the default `OLAP_COMPRESS`.
- Backups contain all your data and the production ones are sensitive. Don't commit them, and delete them from the server once copied.

#### Common parameters

| Parameter              | Default                    | Description                                                   |
| ---------------------- | -------------------------- | ------------------------------------------------------------- |
| `file`                 | _(required)_               | Path to the backup file                                       |
| `DB_TYPE`              | `postgres`                 | Database to restore: `postgres` or `olap`                     |
| `DOCKER_COMPOSE_LOCAL` | `docker-compose.local.yml` | Compose file to use (e.g. `docker-compose.yml` in production) |
| `DB_CONTAINER`         | `db`                       | PostgreSQL service name                                       |
| `OLAP_CONTAINER`       | `olap`                     | ClickHouse service name                                       |
| `API_CONTAINER`        | `api`                      | Django service name (used to run migrations)                  |

#### PostgreSQL parameters (`DB_TYPE=postgres`)

| Parameter         | Default          | Description                                         |
| ----------------- | ---------------- | --------------------------------------------------- |
| `PG_USER`         | `$POSTGRES_USER` | Database user (read from the container environment) |
| `PG_DB`           | `$POSTGRES_DB`   | Database name (read from the container environment) |
| `PG_JOBS_PERCENT` | `90`             | Percentage of CPU cores used for parallel restore   |

The restore uses `--clean --if-exists --no-owner --no-acl`, so it replaces existing objects and can be run repeatedly.

#### ClickHouse parameters (`DB_TYPE=olap`)

| Parameter       | Default                | Description                                                              |
| --------------- | ---------------------- | ------------------------------------------------------------------------ |
| `OLAP_USER`     | `$CLICKHOUSE_USER`     | ClickHouse user (read from the container environment)                    |
| `OLAP_PASSWORD` | `$CLICKHOUSE_PASSWORD` | ClickHouse password (read from the container environment)                |
| `OLAP_DB`       | `metrics`              | Target database                                                          |
| `OLAP_TABLE`    | `metrics_metricvalue`  | Target table                                                             |
| `OLAP_FORMAT`   | `Native`               | Format of the backup file                                                |
| `OLAP_MIGRATE`  | `true`                 | Run `manage.py migrate --database=clickhouse` first to create the tables |
| `OLAP_TRUNCATE` | `false`                | Empty the target table before loading                                    |

#### Examples

```bash
# Restore PostgreSQL
make db_restore file=../data/migrate_data/metrics_backup.dump

# Restore ClickHouse
make db_restore DB_TYPE=olap file=../data/migrate_data/metrics_metricvalue.native.zst

# Reload ClickHouse into a clean table
make db_restore DB_TYPE=olap file=<path> OLAP_TRUNCATE=true

# Another table, schema already exists
make db_restore DB_TYPE=olap file=other.native.zst OLAP_TABLE=other_table OLAP_MIGRATE=false

# Against the production compose file
make db_restore DB_TYPE=olap file=<path> DOCKER_COMPOSE_LOCAL=docker-compose.yml
```

#### Creating the backup files

```bash
# PostgreSQL
docker exec -i <db-container> sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl' > metrics_backup.dump

# ClickHouse (use -i, never -t, because a TTY corrupts binary output)
docker exec -i <olap-container> clickhouse-client --user <user> --password '<password>' \
  -q "SELECT * FROM metrics.metrics_metricvalue FORMAT Native" | zstd -T0 -3 > metrics_metricvalue.native.zst
```

`zstd` must be installed on the host for `.zst` files; use `gzip` otherwise.

## 📚 API Documentation & SDKs

### API Documentation

The API uses drf-spectacular for automatic OpenAPI schema generation:

- **ReDoc**: http://localhost:8000/v2/
- **OpenAPI Schema**: http://localhost:8000/v2/schema/openapi.yml

The schema server URL includes `/v2`, while schema paths, tags, and operation IDs
exclude the version prefix. For example, the metrics list link in ReDoc is
`http://localhost:8000/v2/#tag/metrics/operation/metrics_list`.

### Official SDKs

We provide official SDKs for the following programming languages to make integration easier:

| Language          | Repository                                                                         | Description               |
| ----------------- | ---------------------------------------------------------------------------------- | ------------------------- |
| 📘 **TypeScript** | [metrics-typescript-sdk](https://github.com/Mosquito-Alert/metrics-typescript-sdk) | TypeScript/JavaScript SDK |

Note: In the future we will support more languages

These SDKs provide type-safe interfaces, authentication handling, and convenient methods for interacting with the Metrics API.

## 🧪 Testing

The project uses pytest for testing with Django integration.

### Running Tests

```bash
# Using Docker
docker compose -f docker-compose-local.yml run --rm django pytest

# Or with the shell
make shell
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest api/tests/test_views.py

# Run specific test
pytest api/tests/test_views.py::TestReportViewSet::test_create_report
```

### Test Configuration

Tests are configured in `pytest.ini`:

- Uses `config.settings.local` for testing
- Database reuse enabled (`--reuse-db`)

## 🤝 Contributing

We welcome contributions to the Mosquito Alert project! Here's how you can help:

### Contribution Guidelines

1. **Fork the repository**

   ```bash
   git fork https://github.com/Mosquito-Alert/metrics.git
   ```

2. **Create a feature branch**

   ```bash
   git checkout -b feature/amazing-feature
   ```

3. **Make your changes**
   - Write clean, documented code
   - Add tests for new features
   - Update documentation as needed

4. **Run tests**

   ```bash
   pytest
   ```

5. **Commit your changes**

   ```bash
   git commit -m "Add amazing feature"
   ```

6. **Push to your fork**

   ```bash
   git push origin feature/amazing-feature
   ```

7. **Open a Pull Request**
   - Provide a clear description of changes
   - Reference any related issues
   - Ensure all tests pass

### Reporting Issues

- Use GitHub Issues to report bugs
- Include detailed reproduction steps
- Provide system information and logs
- Tag issues appropriately (bug, enhancement, question)

### Development Workflow

1. Discuss major changes by opening an issue first
2. Keep pull requests focused on single features/fixes
3. Update tests and documentation
4. Follow the existing code style
5. Be responsive to feedback during code review

## 📄 License

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE.md](LICENSE.md) file for details.

Metrics is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

## 👥 Contact

**Mosquito Alert Team**

- Website: [https://mosquitoalert.com](https://mosquitoalert.com)
- Email: it@mosquitoalert.com
- GitHub: [@Mosquito-Alert](https://github.com/Mosquito-Alert)

## 🙏 Acknowledgments

This project is part of a citizen science initiative to monitor and study mosquito populations. Special thanks to all contributors and citizen scientists who make this project possible.

---

**Related Projects**:

- ⚙️ **API**: [api](https://github.com/Mosquito-Alert/mosquito-alert)
- 🌍 **Map**: [map](https://github.com/Mosquito-Alert/map)
- 💻 **Frontend**: [mosquito_alert_frontend](https://github.com/Mosquito-Alert/mosquito_alert_frontend)
- 📱 **Mobile App**: [mosquito_alert_mobile_app](https://github.com/Mosquito-Alert/mosquito_alert_mobile_app)
