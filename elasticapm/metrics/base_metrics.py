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
from collections import defaultdict

from elasticapm.conf import constants
from elasticapm.utils import compat, is_master_process
from elasticapm.utils.module_import import import_string
from elasticapm.utils.threading import IntervalTimer

logger = logging.getLogger("elasticapm.metrics")


class MetricsRegistry(object):
    def __init__(self, collect_interval, queue_func, tags=None, ignore_patterns=None):
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
        self._ignore_patterns = ignore_patterns or ()
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
                self._metricsets[class_path] = class_obj(self)
            except ImportError as e:
                logger.warning("Could not register %s metricset: %s", class_path, compat.text_type(e))

    def get_metricset(self, class_path):
        try:
            return self._metricsets[class_path]
        except KeyError:
            raise MetricSetNotFound(class_path)

    def collect(self):
        """
        Collect metrics from all registered metric sets and queues them for sending
        :return:
        """
        logger.debug("Collecting metrics")

        for name, metricset in compat.iteritems(self._metricsets):
            for data in metricset.collect():
                self._queue_func(constants.METRICSET, data)

    def _start_collect_timer(self, timeout=None):
        timeout = timeout or self._collect_interval
        self._collect_timer = IntervalTimer(self.collect, timeout, name="eapm metrics collect timer", daemon=True)
        logger.debug("Starting metrics collect timer")
        self._collect_timer.start()

    def _stop_collect_timer(self):
        if self._collect_timer:
            logger.debug("Cancelling collect timer")
            self._collect_timer.cancel()


class MetricsSet(object):
    def __init__(self, registry):
        self._lock = threading.Lock()
        self._counters = defaultdict(dict)
        self._gauges = defaultdict(dict)
        self._timers = defaultdict(dict)
        self._registry = registry

    def counter(self, name, reset_on_collect=False, **labels):
        """
        Returns an existing or creates and returns a new counter
        :param name: name of the counter
        :param reset_on_collect: indicate if the counter should be reset to 0 when collecting
        :param labels: a flat key/value map of labels
        :return: the counter object
        """
        return self._metric(self._counters, Counter, name, reset_on_collect, labels)

    def gauge(self, name, reset_on_collect=False, **labels):
        """
        Returns an existing or creates and returns a new gauge
        :param name: name of the gauge
        :param reset_on_collect: indicate if the gouge should be reset to 0 when collecting
        :param labels: a flat key/value map of labels
        :return: the gauge object
        """
        return self._metric(self._gauges, Gauge, name, reset_on_collect, labels)

    def timer(self, name, reset_on_collect=False, **labels):
        """
        Returns an existing or creates and returns a new timer
        :param name: name of the timer
        :param reset_on_collect: indicate if the timer should be reset to 0 when collecting
        :param labels: a flat key/value map of labels
        :return: the timer object
        """
        return self._metric(self._timers, Timer, name, reset_on_collect, labels)

    def _metric(self, container, metric_class, name, reset_on_collect, labels):
        """
        Returns an existing or creates and returns a metric
        :param container: the container for the metric
        :param metric_class: the class of the metric
        :param name: name of the metric
        :param reset_on_collect: indicate if the metric should be reset to 0 when collecting
        :param labels: a flat key/value map of labels
        :return: the metric object
        """

        labels = self._labels_to_key(labels)
        key = (name, labels)
        with self._lock:
            if key not in container:
                if self._registry._ignore_patterns and any(
                    pattern.match(name) for pattern in self._registry._ignore_patterns
                ):
                    metric = noop_metric
                else:
                    metric = metric_class(name, reset_on_collect=reset_on_collect)
                container[key] = metric
            return container[key]

    def collect(self):
        """
        Collects all metrics attached to this metricset, and returns it as a generator
        with one or more elements. More than one element is returned if labels are used.

        The format of the return value should be

            {
                "samples": {"metric.name": {"value": some_float}, ...},
                "timestamp": unix epoch in microsecond precision
            }
        """
        self.before_collect()
        timestamp = int(time.time() * 1000000)
        samples = defaultdict(dict)
        if self._counters:
            for (name, labels), c in compat.iteritems(self._counters):
                if c is not noop_metric:
                    samples[labels].update({name: {"value": c.val}})
                    if c.reset_on_collect:
                        c.reset()
        if self._gauges:
            for (name, labels), g in compat.iteritems(self._gauges):
                if g is not noop_metric:
                    samples[labels].update({name: {"value": g.val}})
                    if g.reset_on_collect:
                        g.reset()
        if self._timers:
            for (name, labels), t in compat.iteritems(self._timers):
                if t is not noop_metric:
                    val, count = t.val
                    samples[labels].update({name + ".sum.us": {"value": int(val * 1000000)}})
                    samples[labels].update({name + ".count": {"value": count}})
                    if t.reset_on_collect:
                        t.reset()
        if samples:
            for labels, sample in compat.iteritems(samples):
                result = {"samples": sample, "timestamp": timestamp}
                if labels:
                    result["tags"] = {k: v for k, v in labels}
                yield self.before_yield(result)

    def before_collect(self):
        """
        A method that is called right before collection. Can be used to gather metrics.
        :return:
        """
        pass

    def before_yield(self, data):
        return data

    def _labels_to_key(self, labels):
        return tuple((k, compat.text_type(v)) for k, v in sorted(compat.iteritems(labels)))


class SpanBoundMetricSet(MetricsSet):
    def before_yield(self, data):
        tags = data.get("tags", None)
        if tags:
            span_type, span_subtype = tags.pop("span.type", None), tags.pop("span.subtype", "")
            if span_type or span_subtype:
                data["span"] = {"type": span_type, "subtype": span_subtype}
            transaction_name, transaction_type = tags.pop("transaction.name", None), tags.pop("transaction.type", None)
            if transaction_name or transaction_type:
                data["transaction"] = {"name": transaction_name, "type": transaction_type}
        return data


class Counter(object):
    __slots__ = ("name", "_lock", "_initial_value", "_val", "reset_on_collect")

    def __init__(self, name, initial_value=0, reset_on_collect=False):
        """
        Creates a new counter
        :param name: name of the counter
        :param initial_value: initial value of the counter, defaults to 0
        """
        self.name = name
        self._lock = threading.Lock()
        self._val = self._initial_value = initial_value
        self.reset_on_collect = reset_on_collect

    def inc(self, delta=1):
        """
        Increments the counter. If no delta is provided, it is incremented by one
        :param delta: the amount to increment the counter by
        :returns the counter itself
        """
        with self._lock:
            self._val += delta
        return self

    def dec(self, delta=1):
        """
        Decrements the counter. If no delta is provided, it is decremented by one
        :param delta: the amount to decrement the counter by
        :returns the counter itself
        """
        with self._lock:
            self._val -= delta
        return self

    def reset(self):
        """
        Reset the counter to the initial value
        :returns the counter itself
        """
        with self._lock:
            self._val = self._initial_value
        return self

    @property
    def val(self):
        """Returns the current value of the counter"""
        return self._val


class Gauge(object):
    __slots__ = ("name", "_val", "reset_on_collect")

    def __init__(self, name, reset_on_collect=False):
        """
        Creates a new gauge
        :param name: label of the gauge
        """
        self.name = name
        self._val = None
        self.reset_on_collect = reset_on_collect

    @property
    def val(self):
        return self._val

    @val.setter
    def val(self, value):
        self._val = value

    def reset(self):
        self._val = 0


class Timer(object):
    __slots__ = ("name", "_val", "_count", "_lock", "reset_on_collect")

    def __init__(self, name=None, reset_on_collect=False):
        self.name = name
        self._val = 0
        self._count = 0
        self._lock = threading.Lock()
        self.reset_on_collect = reset_on_collect

    def update(self, duration, count=1):
        with self._lock:
            self._val += duration
            self._count += count

    def reset(self):
        with self._lock:
            self._val = 0
            self._count = 0

    @property
    def val(self):
        with self._lock:
            return self._val, self._count


class NoopMetric(object):
    """
    A no-op metric that implements the "interface" of both Counter and Gauge.

    Note that even when using a no-op metric, the value itself will still be calculated.
    """

    def __init__(self, label, initial_value=0):
        return

    @property
    def val(self):
        return None

    @val.setter
    def val(self, value):
        return

    def inc(self, delta=1):
        return

    def dec(self, delta=-1):
        return

    def reset(self):
        return


noop_metric = NoopMetric("noop")


class MetricSetNotFound(LookupError):
    def __init__(self, class_path):
        super(MetricSetNotFound, self).__init__("%s metric set not found" % class_path)
