#  BSD 3-Clause License
#
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
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import logging
import threading
import time

from elasticapm.utils import compat, is_master_process
from elasticapm.utils.module_import import import_string

logger = logging.getLogger("elasticapm.metrics")


class MetricsRegistry(object):
    def __init__(self, collect_interval, queue_func, tags=None):
        """
        Creates a new metric registry

        :param collect_interval: the interval to collect metrics from registered metric sets
        :param queue_func: the function to call with the collected metrics
        :param tags:
        """
        self._collect_interval = collect_interval
        self._queue_func = queue_func
        self._metricsets = {}
        self._tags = tags or {}
        self._collect_timer = None
        if self._collect_interval:
            # we only start the thread if we are not in a uwsgi master process
            if not is_master_process():
                self._start_collect_timer()
            else:
                # If we _are_ in a uwsgi master process, we use the postfork hook to start the thread after the fork
                compat.postfork(lambda: self._start_collect_timer())

    def register(self, class_path):
        """
        Register a new metric set
        :param class_path: a string with the import path of the metricset class
        """
        if class_path in self._metricsets:
            return
        else:
            try:
                class_obj = import_string(class_path)
                self._metricsets[class_path] = class_obj()
            except ImportError as e:
                logger.warning("Could not register %s metricset: %s", class_path, compat.text_type(e))

    def collect(self, start_timer=True):
        """
        Collect metrics from all registered metric sets
        :param start_timer: if True, restarts the collect timer after collection
        :return:
        """
        if start_timer:
            self._start_collect_timer()

        logger.debug("Collecting metrics")

        for name, metricset in compat.iteritems(self._metricsets):
            data = metricset.collect()
            if data:
                self._queue_func("metricset", data)

    def _start_collect_timer(self, timeout=None):
        timeout = timeout or self._collect_interval
        self._collect_timer = threading.Timer(timeout, self.collect, kwargs={"start_timer": True})
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
        """
        Returns an existing or creates and returns a new counter
        :param name: name of the counter
        :return: the counter object
        """
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name)
            return self._counters[name]

    def gauge(self, name):
        """
        Returns an existing or creates and returns a new gauge
        :param name: name of the gauge
        :return: the gauge object
        """
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name)
            return self._gauges[name]

    def collect(self):
        """
        Collects all metrics attached to this metricset, and returns it as a list, together with a timestamp
        in microsecond precision.

        The format of the return value should be

            {
                "samples": {"metric.name": {"value": some_float}, ...},
                "timestamp": unix epoch in microsecond precision
            }
        """
        samples = {}
        if self._counters:
            samples.update({label: {"value": c.val} for label, c in compat.iteritems(self._counters)})
        if self._gauges:
            samples.update({label: {"value": g.val} for label, g in compat.iteritems(self._gauges)})
        if samples:
            return {"samples": samples, "timestamp": int(time.time() * 1000000)}


class Counter(object):
    __slots__ = ("label", "_lock", "_initial_value", "_val")

    def __init__(self, label, initial_value=0):
        """
        Creates a new counter
        :param label: label of the counter
        :param initial_value: initial value of the counter, defaults to 0
        """
        self.label = label
        self._lock = threading.Lock()
        self._val = self._initial_value = initial_value

    def inc(self, delta=1):
        """
        Increments the counter. If no delta is provided, it is incremented by one
        :param delta: the amount to increment the counter by
        """
        with self._lock:
            self._val += delta

    def dec(self, delta=1):
        """
        Decrements the counter. If no delta is provided, it is decremented by one
        :param delta: the amount to decrement the counter by
        """
        with self._lock:
            self._val -= delta

    def reset(self):
        """
        Reset the counter to the initial value
        """
        with self._lock:
            self._val = self._initial_value

    @property
    def val(self):
        """Returns the current value of the counter"""
        return self._val


class Gauge(object):
    __slots__ = ("label", "_val")

    def __init__(self, label):
        """
        Creates a new gauge
        :param label: label of the gauge
        """
        self.label = label
        self._val = None

    @property
    def val(self):
        return self._val

    @val.setter
    def val(self, value):
        self._val = value
