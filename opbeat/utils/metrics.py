import threading
import time

from opbeat.conf import defaults

class MetricsStore(object):
    def __init__(self, client):
        self.cond = threading.Condition()
        self.items = []
        self.client = client
        self._last_collect = time.time()

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
        self._last_collect = time.time()
        return items

    def should_collect(self):
        return (
            (time.time() - self._last_collect)
            >= defaults.METRICS_SEND_FREQ_SECS
        )

    def __len__(self):
        with self.cond:
            return len(self.items)
