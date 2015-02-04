import threading
import time

from opbeat.utils.compat import atexit_register


class MetricsStore(object):
    def __init__(self, client):
        self.cond = threading.Condition()
        self.items = []
        self.client = client
        self._thread = threading.Thread(target=self._consume)
        self._thread.daemon = True
        atexit_register(self.client._metrics_collect)

    def add(self, item):
        with self.cond:
            self.items.append(item)
            self.cond.notify()
        if not self._thread.is_alive():
            self._thread.start()

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

    def _consume(self):
        _last_sent = time.time()
        while 1:
            with self.cond:
                wait_time = max(
                    0,
                    self.client.metrics_send_freq_secs - (time.time() - _last_sent)
                )
                if wait_time:
                    self.cond.wait(wait_time)
                else:
                    self.client._metrics_collect()
                    _last_sent = time.time()
