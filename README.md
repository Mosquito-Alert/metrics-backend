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

- **API**: http://localhost:8000/api/v2/
- **Admin**: http://localhost:8000/admin/

### Available Commands

The `Makefile` provides convenient commands for development:

| Command                                        | Description                             |
| ---------------------------------------------- | --------------------------------------- |
| `make start`                                   | Create and start all containers         |
| `make stop`                                    | Stop all containers                     |
| `make restart`                                 | Restart all services                    |
| `make down`                                    | Stop and remove containers              |
| `make logs`                                    | Show container logs (follow mode)       |
| `make shell`                                   | Open bash shell in Django container     |
| `make psql`                                    | Start PostgreSQL command-line client    |
| `make dbshell`                                 | Start database shell                    |
| `make dbshell_olap`                            | Start OLAP database shell               |
| `make ps`                                      | List running containers                 |
| `make db_restore file=<path> DB_TYPE=postgres` | Restore PostgreSQL database from backup |
| `make db_restore file=<path> DB_TYPE=olap`     | Restore OLAP database from backup       |
| `make clean_data`                              | Remove all data volumes                 |
| `make clean_docker`                            | Remove all containers and images        |

## 📚 API Documentation & SDKs

### API Documentation

The API uses drf-spectacular for automatic OpenAPI schema generation:

- **ReDoc**: http://localhost:8000/api/v2/
- **OpenAPI Schema**: http://localhost:8000/api/v2/openapi.yml

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
