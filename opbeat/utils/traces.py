from collections import defaultdict
import threading
import time
from datetime import datetime


class _RequestList(object):
    def __init__(self, transaction, response_code, minute):
        self.transaction = transaction
        self.response_code = response_code
        self.minute = minute
        self.durations = []

    @property
    def fingerprint(self):
        return (self.transaction, self.response_code, self.minute)

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
    def __init__(self, collect_frequency):
        self.cond = threading.Condition()
        self.items = {}
        self.collect_frequency = collect_frequency
        self._last_collect = time.time()

    def add(self, elapsed, transaction, response_code):
        with self.cond:
            requestlist = _RequestList(transaction, response_code,
                                       int(time.time()/60)*60)

            if requestlist.fingerprint not in self.items:
                self.items[requestlist.fingerprint] = requestlist

            self.items[requestlist.fingerprint].add(elapsed)
            self.cond.notify()

    def get_all(self, blocking=False):
        with self.cond:
            # If blocking is true, always return at least 1 item
            while blocking and len(self.items) == 0:
                self.cond.wait()
            items, self.items = self.items, {}
        self._last_collect = time.time()
        return [v.as_dict() for v in items.values()]

    def should_collect(self):
        return (
            (time.time() - self._last_collect)
            >= self.collect_frequency
        )

    def __len__(self):
        with self.cond:
            return sum([len(v.durations) for v in self.items.values()])
