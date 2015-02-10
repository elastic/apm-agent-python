import contextlib
import threading
import time
from datetime import datetime
from opbeat.utils.encoding import force_text


class Trace(object):
    def _decode(self, param):
        try:
            return force_text(param, strings_only=True)
        except UnicodeDecodeError:
            return '(encoded string)'

    def __init__(self, duration_list, start_time_list, transaction, signature,
                 kind, parents, collateral):
        self.duration_list = duration_list
        self.start_time_list = start_time_list
        self.transaction = transaction
        self.signature = signature
        self.kind = kind
        self.parents = tuple(parents)
        self.collateral = collateral

    def merge(self, trace):
        self.duration_list.extend(trace.duration_list)
        self.start_time_list.extend(trace.start_time_list)

    @property
    def fingerprint(self):
        return (self.transaction, self.parents, self.signature, self.kind)


class TracesStore(object):
    thread_local = threading.local()

    def __init__(self, collect_frequency):
        self.cond = threading.Condition()
        self._traces = {}
        self.collect_frequency = collect_frequency
        self._last_collect = time.time()


    def get_all(self, blocking=False):
        with self.cond:
            # If blocking is true, always return at least 1 item
            while blocking and len(self._traces) == 0:
                self.cond.wait()
            traces, self._traces = self._traces, {}
        self._last_collect = time.time()
        return traces.values()

    def should_collect(self):
        return (
            (time.time() - self._last_collect)
            >= self.collect_frequency
        )

    def __len__(self):
        with self.cond:
            return len(self._traces)

    def request_start(self):
        self.thread_local.transaction_start = time.time()
        self.thread_local.transaction_name = "Web Request"
        self.thread_local.sig_stack = []

    def set_transaction_name(self, transaction_name):
        self.thread_local.transaction_name = transaction_name

    def set_response_code(self, code):
        self.thread_local.response_code = code

    def request_end(self):
        if hasattr(self.thread_local, "transaction_start"):
            start = self.thread_local.transaction_start
            elapsed = (time.time() - start)*1000

            self.add(elapsed, 0, "request", "transaction.web", [], None)

    @contextlib.contextmanager
    def trace(self, signature, kind, collateral):
        abs_start_time = time.time()
        sig_stack = self.thread_local.sig_stack

        if len(sig_stack):
            parent_start_time, parent_signature = sig_stack[-1]
        else:
            parent_start_time, parent_signature = self.thread_local.transaction_start, "request"

        rel_start_time = (abs_start_time - parent_start_time)*1000

        sig_stack.append((abs_start_time, signature))

        yield

        sig_stack.pop()
        parents = [s[1] for s in sig_stack]
        elapsed = (time.time() - abs_start_time)*1000

        self.add(elapsed, rel_start_time, signature, kind,
                               ("request", ) + tuple(parents), collateral)

    def add(self, duration, relative_start, signature, kind, parents,
            collateral):
        transaction = getattr(self.thread_local, 'transaction_name', None)
        print signature[:20], relative_start, duration
        trace = Trace([duration], [relative_start], transaction, signature,
                      kind, parents, collateral)

        with self.cond:
            if trace.fingerprint in self._traces:
                self._traces[trace.fingerprint].merge(trace)
            else:
                self._traces[trace.fingerprint] = trace

            self.cond.notify()