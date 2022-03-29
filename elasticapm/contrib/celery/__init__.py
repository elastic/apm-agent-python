#  BSD 3-Clause License
#
#  Copyright (c) 2012, the Sentry Team, see AUTHORS for more details
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
from contextlib import suppress

from celery import signals, states

import elasticapm
from elasticapm.conf import constants
from elasticapm.traces import execution_context
from elasticapm.utils import get_name_from_func
from elasticapm.utils.disttracing import TraceParent


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
    _register_worker_signals(client)


def set_celery_headers(headers=None, **kwargs):
    """
    Add elasticapm specific information to celery headers
    """
    headers = {} if headers is None else headers

    transaction = execution_context.get_transaction()
    if transaction is not None:
        trace_parent = transaction.trace_parent

        # Customize parent span id (if provided)
        apm_headers = headers.get("elasticapm", dict())
        if "parent_span_id" in apm_headers:
            trace_parent = trace_parent.copy_from()
            trace_parent.span_id = apm_headers["parent_span_id"]

        apm_headers["trace_parent_string"] = trace_parent.to_string()
        headers.update(elasticapm=apm_headers)


def get_trace_parent(celery_task):
    """
    Return a trace parent contained in the request headers of a Celery Task object or None
    """
    read_from_inner_headers = lambda: celery_task.request.headers["elasticapm"]["trace_parent_string"]
    read_from_request = lambda: celery_task.request.elasticapm["trace_parent_string"]

    for read_fun in (read_from_request, read_from_inner_headers):
        with suppress(AttributeError, KeyError, TypeError):
            trace_parent_string = read_fun()
            return TraceParent.from_string(trace_parent_string)

    return None


def register_instrumentation(client):
    def begin_transaction(*args, **kwargs):
        task = kwargs["task"]

        trace_parent = get_trace_parent(task)
        client.begin_transaction("celery", trace_parent=trace_parent)

    def end_transaction(task_id, task, *args, **kwargs):
        name = get_name_from_func(task)
        state = kwargs.get("state", "None")
        if state == states.SUCCESS:
            outcome = constants.OUTCOME.SUCCESS
        elif state in states.EXCEPTION_STATES:
            outcome = constants.OUTCOME.FAILURE
        else:
            outcome = constants.OUTCOME.UNKNOWN
        elasticapm.set_transaction_outcome(outcome, override=False)
        client.end_transaction(name, state)

    dispatch_uid = "elasticapm-tracing-%s"

    # unregister any existing clients
    signals.before_task_publish.disconnect(set_celery_headers, dispatch_uid=dispatch_uid % "before-publish")
    signals.task_prerun.disconnect(begin_transaction, dispatch_uid=dispatch_uid % "prerun")
    signals.task_postrun.disconnect(end_transaction, dispatch_uid=dispatch_uid % "postrun")

    # register for this client
    signals.before_task_publish.connect(set_celery_headers, dispatch_uid=dispatch_uid % "before-publish")
    signals.task_prerun.connect(begin_transaction, dispatch_uid=dispatch_uid % "prerun", weak=False)
    signals.task_postrun.connect(end_transaction, weak=False, dispatch_uid=dispatch_uid % "postrun")
    _register_worker_signals(client)


def _register_worker_signals(client):
    def worker_shutdown(*args, **kwargs):
        client.close()

    def connect_worker_process_init(*args, **kwargs):
        signals.worker_process_shutdown.connect(worker_shutdown, dispatch_uid="elasticapm-shutdown-worker", weak=False)

    signals.worker_init.connect(
        connect_worker_process_init, dispatch_uid="elasticapm-connect-start-threads", weak=False
    )
