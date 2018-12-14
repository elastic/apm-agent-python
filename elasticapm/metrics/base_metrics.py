import logging
import threading
import time

from elasticapm.utils import compat
from elasticapm.utils.module_import import import_string

logger = logging.getLogger("elasticapm.metrics")


class MetricsRegistry(object):
    def __init__(self, collect_interval, queue_func, tags=None):
        self._collect_interval = collect_interval
        self._queue_func = queue_func
        self._metricsets = {}
        self._tags = tags or {}
        self._collect_timer = None
        if self._collect_interval:
            self._start_collect_timer()

    def register(self, class_path):
        if class_path in self._metricsets:
            return
        else:
            try:
                class_obj = import_string(class_path)
                self._metricsets[class_path] = class_obj()
            except ImportError as e:
                logger.warning("Could not register %s metricset: %s", class_path, compat.text_type(e))

    def collect(self, start_timer=True):
        logger.debug("Starting metrics collect timer")

        for name, metricset in compat.iteritems(self._metricsets):
            data = metricset.collect()
            if data:
                self._queue_func("metricset", data)

        if start_timer:
            self._start_collect_timer()

    def _start_collect_timer(self, timeout=None):
        timeout = timeout or self._collect_interval
        self._collect_timer = threading.Timer(timeout, self.collect)
        self._collect_timer.name = "elasticapm metrics collect timer"
        self._collect_timer.daemon = True
        logger.debug("Starting metrics collect timer")
        self._collect_timer.start()

    def _stop_collect_timer(self):
        if self._collect_timer:
            logger.debug("Cancelling collect timer")
            self._collect_timer.cancel()


class MetricsSet(object):
    def __init__(self):
        self._lock = threading.Lock()
        self._counters = {}
        self._gauges = {}

    def counter(self, name):
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name)
            return self._counters[name]

    def gauge(self, name):
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name)
            return self._gauges[name]

    def collect(self):
        samples = {}
        if self._counters:
            samples.update({label: {"value": c.val} for label, c in compat.iteritems(self._counters)})
        if self._gauges:
            samples.update({label: {"value": g.val} for label, g in compat.iteritems(self._gauges)})
        if samples:
            return {"samples": samples, "timestamp": int(time.time() * 1000000)}


class Counter(object):
    def __init__(self, label):
        self.label = label
        self._lock = threading.Lock()
        self._val = 0

    def inc(self, delta=1):
        with self._lock:
            self._val += delta

    def dec(self, delta=1):
        with self._lock:
            self._val += delta

    def reset(self):
        with self._lock:
            self._val = 0

    @property
    def val(self):
        return self._val


class Gauge(object):
    def __init__(self, label):
        self.label = label
        self._val = None

    @property
    def val(self):
        return self._val

    @val.setter
    def val(self, value):
        self._val = value
