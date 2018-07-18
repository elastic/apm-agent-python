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
        if record.funcName in ("_log_error",):
            return 0
        else:
            return 1


def register_exception_tracking(client):
    dispatch_uid = "elasticapm-exc-tracking"

    def process_failure_signal(sender, task_id, exception, args, kwargs, traceback, einfo, **kw):
        client.capture_exception(
            extra={"task_id": task_id, "task": sender, "args": args, "kwargs": kwargs}, handled=False
        )

    signals.task_failure.disconnect(process_failure_signal, dispatch_uid=dispatch_uid)
    signals.task_failure.connect(process_failure_signal, weak=False, dispatch_uid=dispatch_uid)


def register_instrumentation(client):
    def begin_transaction(*args, **kwargs):
        client.begin_transaction("celery")

    def end_transaction(task_id, task, *args, **kwargs):
        name = get_name_from_func(task)
        client.end_transaction(name, kwargs.get("state", "None"))

    dispatch_uid = "elasticapm-tracing-%s"

    # unregister any existing clients
    signals.task_prerun.disconnect(begin_transaction, dispatch_uid=dispatch_uid % "prerun")
    signals.task_postrun.disconnect(end_transaction, dispatch_uid=dispatch_uid % "postrun")

    # register for this client
    signals.task_prerun.connect(begin_transaction, dispatch_uid=dispatch_uid % "prerun", weak=False)
    signals.task_postrun.connect(end_transaction, weak=False, dispatch_uid=dispatch_uid % "postrun")
