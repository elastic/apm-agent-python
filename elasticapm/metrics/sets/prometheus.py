#  BSD 3-Clause License
#
#  Copyright (c) 2020, Elasticsearch BV
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
from __future__ import absolute_import

import itertools

import prometheus_client

from elasticapm.metrics.base_metrics import MetricsSet


class PrometheusMetrics(MetricsSet):
    def __init__(self, registry):
        super(PrometheusMetrics, self).__init__(registry)
        self._prometheus_registry = prometheus_client.REGISTRY

    def before_collect(self):
        for metric in self._prometheus_registry.collect():
            metric_type = self.METRIC_MAP.get(metric.type, None)
            if not metric_type:
                continue
            metric_type(self, metric.name, metric.samples, metric.unit)

    def _prom_counter_handler(self, name, samples, unit):
        # Counters can be converted 1:1 from Prometheus to our
        # format. Each pair of samples represents a distinct labelset for a
        # given name. The pair consists of the value, and a "created" timestamp.
        # We only use the former.
        for total_sample, _ in grouper(samples, 2):
            self.counter(
                self._registry.client.config.prometheus_metrics_prefix + name, **total_sample.labels
            ).val = total_sample.value

    def _prom_gauge_handler(self, name, samples, unit):
        # Counters can be converted 1:1 from Prometheus to our
        # format. Each sample represents a distinct labelset for a
        # given name
        for sample in samples:
            self.gauge(
                self._registry.client.config.prometheus_metrics_prefix + name, **sample.labels
            ).val = sample.value

    def _prom_summary_handler(self, name, samples, unit):
        # Prometheus Summaries are analogous to our Timers, having
        # a count and a sum. A prometheus summary is represented by
        # three values. The list of samples for a given name can be
        # grouped into 3-pairs of (count, sum, creation_timestamp).
        # Each 3-pair represents a labelset.
        for count_sample, sum_sample, _ in grouper(samples, 3):
            self.timer(self._registry.client.config.prometheus_metrics_prefix + name, **count_sample.labels).val = (
                sum_sample.value,
                count_sample.value,
            )

    def _prom_histogram_handler(self, name, samples, unit):
        # Prometheus histograms are structured as a series of counts
        # with an "le" label. The count of each label signifies all
        # observations with a lower-or-equal value with respect to
        # the "le" label value.
        # After the le-samples, 3 more samples follow, with an overall
        # count, overall sum, and creation timestamp.
        sample_pos = 0
        prev_val = 0
        counts = []
        values = []
        name = self._registry.client.config.prometheus_metrics_prefix + name
        while sample_pos < len(samples):
            sample = samples[sample_pos]
            if "le" in sample.labels:
                values.append(float(sample.labels["le"]))
                counts.append(sample.value - prev_val)
                prev_val = sample.value
                sample_pos += 1

            else:
                # we reached the end of one set of buckets/values, this is the "count" sample
                self.histogram(name, unit=unit, buckets=values, **sample.labels).val = counts
                prev_val = 0
                counts = []
                values = []
                sample_pos += 3  # skip sum/created samples

    METRIC_MAP = {
        "counter": _prom_counter_handler,
        "gauge": _prom_gauge_handler,
        "summary": _prom_summary_handler,
        "histogram": _prom_histogram_handler,
    }


def grouper(iterable, n, fillvalue=None):
    """Collect data into fixed-length chunks or blocks"""
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)
