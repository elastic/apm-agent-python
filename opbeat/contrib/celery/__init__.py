"""
opbeat.contrib.celery
~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
try:
    from celery.task import task
except ImportError:
    from celery.decorators import task
from celery import signals

from opbeat.base import Client


class CeleryMixin(object):
    def send_encoded(self, *args, **kwargs):
        "Errors through celery"
        self.send_raw.delay(*args, **kwargs)

    @task(routing_key='opbeat')
    def send_raw(self, *args, **kwargs):
        return super(CeleryMixin, self).send_encoded(*args, **kwargs)


class CeleryClient(CeleryMixin, Client):
    pass


class CeleryFilter(object):
    def filter(self, record):
        if record.funcName in ('_log_error',):
            return 0
        else:
            return 1


def register_signal(client):
    def process_failure_signal(sender, task_id, exception, args, kwargs,
                               traceback, einfo, **kw):
        client.capture_exception(
            extra={
                'task_id': task_id,
                'task': sender,
                'args': args,
                'kwargs': kwargs,
            })
    signals.task_failure.connect(process_failure_signal, weak=False)
