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
    _register_worker_signals(client)


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
    _register_worker_signals(client)


def _register_worker_signals(client):
    def worker_startup(*args, **kwargs):
        client._transport._start_event_processor()

    def worker_shutdown(*args, **kwargs):
        client.close()

    def connect_worker_process_init(*args, **kwargs):
        signals.worker_process_init.connect(worker_startup, dispatch_uid="elasticapm-start-worker", weak=False)
        signals.worker_process_shutdown.connect(worker_shutdown, dispatch_uid="elasticapm-shutdown-worker", weak=False)

    signals.worker_init.connect(
        connect_worker_process_init, dispatch_uid="elasticapm-connect-start-threads", weak=False
    )
