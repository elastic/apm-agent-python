from collections import defaultdict
import contextlib
import threading
from datetime import datetime
from django.utils.functional import cached_property
import time
from opbeat import VERSION
from opbeat.contrib.django.models import get_client
import logging
from opbeat.utils.encoding import force_text

logger = logging.getLogger(__name__)


class TimedCall(object):
    def _decode(self, param):
        try:
            return force_text(param, strings_only=True)
        except UnicodeDecodeError:
            return '(encoded string)'

    def __init__(self, duration_list, start_time_list, name, call_id, parent, kind, params, extra):
        self.duration_list = duration_list
        self.start_time_list = start_time_list
        self.name = name
        self.call_id = call_id
        self.parent = parent
        self.kind = kind
        if params:
            self.params = tuple(map(self._decode, params))
        else:
            self.params = None
        self.extra = extra


    @cached_property
    def fingerprint(self):
        return (self.name, self.params, self.parent)


class RequestMetrics(object):
    # Create a threadlocal variable to store the session in for logging
    thread_local = threading.local()

    def __init__(self, client):
        self.client = client

    def request_start(self):
        self.thread_local.request_start = time.time()
        self.thread_local.timed_calls = []

    def set_view(self, view_name):
        self.thread_local.view_name = view_name

    def set_response_code(self, code):
        self.thread_local.response_code = code

    def request_end(self, response):
        if (hasattr(self.thread_local, "request_start")
                and hasattr(response, "status_code")):
            elapsed = (datetime.now() - self.thread_local.request_start)\
                .total_seconds()*1000

            view_name = getattr(self.thread_local, "view_name", None)

            status_code = response.status_code
            self.client.captureRequest(elapsed, status_code, view_name)
        #
        # request_timed_calls = self.thread_local.timed_calls
        #
        # # todo: use response code
        # # response_code = self.thread_local.response_code
        #
        # # needs to be in a critical section
        # view_name = getattr(self.thread_local, 'view_name', "Django")
        # self.view_calls[view_name].append(view_duration)
        #
        # for timed_call in request_timed_calls:
        #     view_calls = self.timed_calls[view_name]
        #
        #     if timed_call.fingerprint not in view_calls:
        #         view_calls[timed_call.fingerprint] = timed_call
        #         view_calls[timed_call.fingerprint].start_time_list = [
        #             (start_time - request_start)*1000
        #             for start_time in timed_call.start_time_list
        #         ]
        #     else:
        #         view_calls[timed_call.fingerprint].duration_list += \
        #             timed_call.duration_list
        #         # Add the start time offsets
        #         view_calls[timed_call.fingerprint].start_time_list += \
        #             [(start_time - request_start)*1000
        #              for start_time in timed_call.start_time_list]
        #
        # if not self.last_send or (datetime.now() - self.last_send).total_seconds() > 10:
        #     self.last_send = datetime.now()
        #     self.send()
        #     self.reset()

        # end of critical section

    def get(self):
        return self.timed_calls

    # noinspection PyAttributeOutsideInit
    def reset(self):
        self.timed_calls = defaultdict(dict)
        self.view_calls = defaultdict(list)

    @contextlib.contextmanager
    def time(self, name, kind, params=None, extra=None):
        start_time = time.time()
        if not hasattr(self.thread_local, 'call_stack'):
            self.thread_local.call_stack = []
            self.thread_local.last_call_id = 0
            parent = None
        else:
            if self.thread_local.call_stack:
                parent = self.thread_local.call_stack[-1]
            else:
                parent = None

        call_id = self.thread_local.last_call_id + 1
        self.thread_local.last_call_id = call_id

        self.thread_local.call_stack.append(call_id)

        yield

        self.thread_local.call_stack.pop()

        elapsed = time.time() - start_time

        self.add(elapsed, start_time, name, call_id, parent, kind, params, extra)

    def add(self, duration, start_time, name, call_id, parent, kind, params, extra):
        timed_call = TimedCall([duration], [start_time], name, call_id, parent, kind,
                               params, extra)

        self.thread_local.timed_calls.append(timed_call)

    def send(self):
        client = get_client()
        ts = datetime.now().isoformat() + "Z"

        metric_prefix = "opbeat.apm."
        metrics = []

        for view, durations in self.view_calls.items():
            metrics.extend([{
                "name": metric_prefix + "timed_transaction",
                "value": v,
                "timestamp": ts,
                "segments": {
                    "transaction_name": view,
                    "type": "view"
                }
            } for v in durations])

        for view_name, timed_calls in self.timed_calls.items():
            for calls in timed_calls.values():
                metrics.extend([
                {
                    "name": metric_prefix + "timed_call",
                    "value": v,
                    "timestamp": ts,
                    "segments": {
                        "transaction_name": view_name,
                        "call_name": calls.name,
                        # "call_id": calls.call_id,
                        "args": str(calls.params)[:1024],
                        "type": calls.kind,
                        # "parent": str(calls.parent)[:1024]
                    }
                }
                for v in calls.duration_list])

                metrics.extend([{
                    "name": metric_prefix + "timed_call.start",
                    "value": v,
                    "timestamp": ts,
                    "segments": {
                        "transaction_name": view_name,
                        "call_name": calls.name,
                        # "call_id": calls.call_id,
                        "type": calls.kind,
                        # "parent": str(calls.parent)[:1024]
                    }
                } for v in calls.duration_list])
        data = client.encode({"gauges": metrics})

        logger.warn("Sending %d metrics to Opbeat, size: %d kBytes",
                    len(metrics), float(len(data))/1024.0)
        # print metrics
        url = "http://localhost:8080/api/v1/organizations/{}/apps/{}/metrics/".format(
            client.organization_id,
            client.app_id
        )

        headers = {
                'Authorization': "Bearer %s" % (client.secret_token),
                'Content-Type': 'application/octet-stream',
                'User-Agent': 'opbeat/%s' % VERSION
        }
        client.send_remote(url, data, headers)


instrumentation = RequestMetrics()
