"""
ASGI config for project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from pathlib import Path
import sys

from django.core.asgi import get_asgi_application

# This allows easy placement of apps within the interior
# anomaly_detection directory.
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent
sys.path.append(str(BASE_DIR / "anomaly_detection"))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings.production')

application = get_asgi_application()
