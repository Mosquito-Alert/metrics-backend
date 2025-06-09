import os

from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings.production')

app = Celery('anomaly_detection')

# You load any custom configuration from your project settings using the config_from_object()
# method. By setting the CELERY namespace, all Celery settings need to include
# the CELERY_ prefix in their name (for example, CELERY_BROKER_URL).
app.config_from_object('django.conf:settings', namespace='CELERY')

# Finally, you tell Celery to auto-discover asynchronous tasks for your applications. Celery will
# look for a tasks.py file in each application directory
app.autodiscover_tasks()
