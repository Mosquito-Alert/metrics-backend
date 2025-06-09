"""
Django 5.2 settings for the Bites Anomaly Detection project.
Base settings to build other settings files upon.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# * GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key")
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = os.environ.get("DEBUG", "False").lower() == 'true'
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = 'en-us'
# Local time zone.
TIME_ZONE = 'UTC'
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True


# * APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
    'drf_spectacular',
    'django_filters',
    # 'django_hosts',
    "corsheaders",
]

LOCAL_APPS = [
    'anomaly_detection.utils',
    'anomaly_detection.regions',
    'anomaly_detection.predictions',
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


# * MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    'lb_health_check.middleware.AliveCheck',
    # 'django_hosts.middleware.HostsRequestMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # 'django_hosts.middleware.HostsResponseMiddleware'
]


# * DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        'NAME': os.environ.get('POSTGRES_DB', 'anomaly_detection'),
        'USER': os.environ.get('POSTGRES_USER'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD'),
    }
}
# https://docs.djangoproject.com/en/stable/ref/settings/#std:setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# * URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = 'project.urls'
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = 'project.wsgi.application'


# * SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-trusted-origins
CSRF_TRUSTED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:8000").split(",")

# * TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# * AUTHENTICATION & PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# * STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / '../static'


# # For django-hsots
# ROOT_HOSTCONF = 'project.hosts'
# DEFAULT_HOST = 'api'


# * API Settings
# -------------------------------------------------------------------------------
# django-rest-framework - https://www.django-rest-framework.org/api-guide/settings/
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'anomaly_detection.utils.pagination.StandardPagination',
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
    ],
}

# Spectacular settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'Bites Anomaly Detection API',
    'DESCRIPTION': 'API for the Bites Anomaly Detection project',
    'VERSION': '1.0.0',
    'CONTACT': {
        'name': 'Bites Anomaly Detection',
        'email': None,
        'url': None,
    },
    'SERVERS': [
        {
            'url': 'http://localhost:8000/api/v1/',
            'description': 'Development API v1'
        },
    ],
    'SCHEMA_PATH_PREFIX': '/api/v[0-9]',
    'SCHEMA_PATH_PREFIX_TRIM': True,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
    },
    'OAS_VERSION': '3.0.3',
    'POSTPROCESSING_HOOKS': [],  # NOTE: needed for the openapi-generator and so we can upload files through the UI.
    'ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE': False,  # See: https://github.com/tfranzel/drf-spectacular/issues/235
    'ENUM_GENERATE_CHOICE_DESCRIPTION': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# django-lb-health-check settings
ALIVENESS_URL = "/ping/"
