"""
elasticapm.contrib.celery
~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from celery import signals

from elasticapm.utils import get_name_from_func


class CeleryFilter(object):
    def filter(self, record):
        if record.funcName in ('_log_error',):
            return 0
        else:
            return 1


def register_exception_tracking(client):
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


def register_instrumentation(client):
    def begin_transaction(*args, **kwargs):
        client.begin_transaction("celery")

    def end_transaction(task_id, task, *args, **kwargs):
        name = get_name_from_func(task)
        client.end_transaction(name, 200)
    signals.task_prerun.connect(begin_transaction, weak=False)
    signals.task_postrun.connect(end_transaction, weak=False)
