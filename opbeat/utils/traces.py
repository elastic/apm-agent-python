import contextlib
import threading
import time
from datetime import datetime
from collections import defaultdict

from opbeat.utils.encoding import force_text
from opbeat.utils.lru import LRUCache
from opbeat.utils.stacks import get_stack_info, iter_stack_frames


class AbstractTrace(object):
    def __init__(self, signature, kind, parents, frames, extra,
                 transaction=None, transaction_duration=True):
        self.transaction = transaction
        self.transaction_duration = transaction_duration
        self.signature = signature
        self.kind = kind
        self.parents = tuple(parents)
        self.frames = frames
        self.extra = extra

    @property
    def fingerprint(self):
        return self.transaction, self.parents, self.signature, self.kind


class Trace(AbstractTrace):
    def __init__(self, start_time, trace_duration, signature, kind, parents,
                 frames, extra,
                 transaction=None, transaction_duration=None):
        self.start_time = start_time
        self.trace_duration = trace_duration
        super(Trace, self).__init__(signature, kind, parents, frames, extra,
                                    transaction, transaction_duration)


class TraceGroup(AbstractTrace):
    def _decode(self, param):
        try:
            return force_text(param, strings_only=True)
        except UnicodeDecodeError:
            return '(encoded string)'

    def __init__(self, trace):
        self.traces = []
        super(TraceGroup, self).__init__(trace.signature, trace.kind,
                                         trace.parents, trace.frames,
                                         trace.extra, trace.transaction)

    def add(self, trace):
        self.traces.append(trace)

    def as_dict(self):
        # Merge frames into extra
        extra = dict(self.extra or {})
        if self.frames:
            extra['_frames'] = self.frames

        return {
            "transaction": self.transaction,
            "durations": [(t.trace_duration, t.transaction_duration)
                          for t in self.traces],
            "signature": self.signature,
            "kind": self.kind,
            "parents": self.parents,
            "extra": extra,
            "start_time": min([t.start_time for t in self.traces]),
        }


class _RequestGroup(object):
    def __init__(self, transaction, response_code, minute):
        self.transaction = transaction
        self.response_code = response_code
        self.minute = minute
        self.durations = []

    @property
    def fingerprint(self):
        return self.transaction, self.response_code, self.minute

    def add(self, elapsed):
        self.durations.append(elapsed)

    def as_dict(self):
        return {
            "transaction": self.transaction,
            "result": self.response_code,
            "timestamp": datetime.utcfromtimestamp(self.minute).isoformat() + "Z",
            "durations": self.durations
        }


class RequestsStore(object):
    def __init__(self, get_frames, collect_frequency):
        self.cond = threading.Condition()
        self._get_frames = get_frames
        self.thread_local = threading.local()
        self.thread_local.transaction_traces = []
        self._transactions = {}
        self._traces = defaultdict(list)
        self.collect_frequency = collect_frequency
        self._last_collect = time.time()
        self._lrucache = LRUCache(maxsize=1000)

    def _add_transaction(self, elapsed, transaction, response_code):
        with self.cond:
            requestgroup = _RequestGroup(transaction, response_code,
                                        int(time.time()/60)*60)

            if requestgroup.fingerprint not in self._transactions:
                self._transactions[requestgroup.fingerprint] = requestgroup

            self._transactions[requestgroup.fingerprint].add(elapsed)
            self.cond.notify()

    def get_all(self, blocking=False):
        with self.cond:
            # If blocking is true, always return at least 1 item
            while blocking and len(self._traces) == 0:
                self.cond.wait()
            transactions, self._transactions = self._transactions, {}
            traces, self._traces = self._traces, {}
        self._last_collect = time.time()
        return ([v.as_dict() for v in transactions.values()],
                [v.as_dict() for v in traces.values()],)

    def should_collect(self):
        return (
            (time.time() - self._last_collect)
            >= self.collect_frequency
        )

    def __len__(self):
        with self.cond:
            return sum([len(v.durations) for v in self._transactions.values()])

    def transaction_start(self):
        self.thread_local.transaction_start = time.time()
        self.thread_local.transaction_traces = []
        self.thread_local.signature_stack = []

    def _add_trace(self, trace):
        with self.cond:
            if trace.fingerprint not in self._traces:
                self._traces[trace.fingerprint] = TraceGroup(trace)
            self._traces[trace.fingerprint].add(trace)
            self.cond.notify()

    def transaction_end(self, response_code, transaction_name):
        if hasattr(self.thread_local, "transaction_start"):
            start = self.thread_local.transaction_start
            elapsed = (time.time() - start)*1000

            # Take all the traces accumulated during the transaction,
            # set the transaction name on them and merge them into the dict
            for trace in self.thread_local.transaction_traces:
                trace.transaction = transaction_name
                trace.transaction_duration = elapsed

                self._add_trace(trace)

            # Add the transaction itself
            transaction_trace = Trace(0.0, elapsed, "transaction",
                                      "transaction", [], [], None,
                                      transaction_name, elapsed)
            self._add_trace(transaction_trace)
            self.thread_local.transaction_traces = []
            self._add_transaction(elapsed, transaction_name,
                                  response_code)

    @contextlib.contextmanager
    def trace(self, signature, kind, extra, skip_frames=0):
        abs_start_time = time.time()

        if not hasattr(self.thread_local, 'signature_stack'):
            yield
            return

        signature_stack = self.thread_local.signature_stack

        if len(signature_stack):
            parent_start_time = signature_stack[-1][0]
        else:
            parent_start_time = self.thread_local.transaction_start

        rel_start_time = (abs_start_time - parent_start_time)*1000

        signature_stack.append((abs_start_time, signature))

        yield

        signature_stack.pop()
        parents = [s[1] for s in signature_stack]
        duration = (time.time() - abs_start_time)*1000

        self.add_trace(rel_start_time, duration,  signature, kind,
                       ("transaction", ) + tuple(parents), skip_frames,
                       extra)

    def add_trace(self, relative_start, duration, signature, kind, parents,
                  skip_frames, extra=None):

        skip_frames += 8

        trace = Trace(relative_start, duration, signature,
                      kind, parents, None, extra)

        if not self._lrucache.has_key(trace.fingerprint):
            self._lrucache.set(trace.fingerprint)
            frames = self._get_frames()[skip_frames:]
            trace.frames = frames

        self.thread_local.transaction_traces.append(trace)