FROM python:3.13.3-slim-bookworm

LABEL maintainer="guillermo.sanz@ceab.csic.es"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE 1

EXPOSE 8000

# This will be overridden by the docker-compose.yml file
ARG DEV=false
ARG APP_HOME=/usr/app

RUN addgroup --system django && \
    adduser --system  --disabled-password --no-create-home --ingroup django django-user

COPY ./requirements.txt /tmp/requirements.txt
COPY --chmod=+x ./scripts /scripts
COPY --chown=django-user:django . ${APP_HOME}
WORKDIR ${APP_HOME}

# Install required system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    # dependencies for building Python packages
    build-essential \
    # Needed for docker healthcheck
    curl \
    # psycopg2 dependencies
    libpq-dev \
    # TODO: Translations dependencies
    # gettext \
    # GIS dependencies. See: https://docs.djangoproject.com/en/5.2/ref/contrib/gis/install/geolibs/
    binutils libproj-dev gdal-bin \
    # cleaning up unused files
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# Update pip, set up the virtual environment and install python requirements
RUN python -m venv /py && \
    /py/bin/pip install --upgrade pip && \
    /py/bin/pip install -r /tmp/requirements.txt && \
    # Cleaning
    rm -rf /tmp


ENV PATH="/scripts:/py/bin:$PATH"

USER django-user

CMD ["start_prod"]
