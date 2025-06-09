"""
WSGI config for project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
from pathlib import Path
import sys

from django.core.wsgi import get_wsgi_application

# This allows easy placement of apps within the interior
# anomaly_detection directory.
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent
sys.path.append(str(BASE_DIR / "anomaly_detection"))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings.production')

application = get_wsgi_application()
