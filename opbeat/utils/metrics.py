import threading
import time


class MetricsStore(object):
    def __init__(self):
        self.cond = threading.Condition()
        self.items = []

    def add(self, item):
        with self.cond:
            self.items.append(item)
            self.cond.notify()

    def get_all(self, blocking=False):
        with self.cond:
            # If blocking is true, always return at least 1 item
            while blocking and len(self.items) == 0:
                self.cond.wait()
            items, self.items = self.items, []
        return items

    def __len__(self):
        with self.cond:
            return len(self.items)


class Aggregator(object):
    interval = 0
    gauge_name = None
    aggregate_over_gauges = ()
    _last_read = None
    _value = None

    def __init__(self):
        self._value = self.init_value()

    def init_value(self):
        return 0

    def add(self, *points):
        raise NotImplementedError()

    def prepare(self, value):
        raise NotImplementedError()

    def get(self):
        if not self._last_read:
            self._last_read = time.time()
        if time.time() - self._last_read >= self.interval:
            value, self._value = self._value, None
            return value

