from __future__ import absolute_import

from celery import Celery

from django.conf import settings

app = Celery('testapp')

app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


# hook up Opbeat

from opbeat.contrib.django.models import client, logger, register_handlers
from opbeat.contrib.celery import register_signal

try:
    register_signal(client)
except Exception as e:
    logger.exception('Failed installing celery hook: %s' % e)

if 'opbeat.contrib.django' in settings.INSTALLED_APPS:
    register_handlers()
